"""只读部署后门禁：绑定目标、环境和版本，并保存可审计 HTTP 证据。"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import time
from typing import Callable, Mapping, Sequence
from urllib.parse import urlsplit

import httpx


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "output" / "postdeploy-gate"
SCHEMA_VERSION = 1
ALLOWED_ENVIRONMENTS = {"local", "dev"}
RELEASE_PATTERN = re.compile(r"^[0-9a-fA-F]{7,64}$")
REQUIRED_SECURITY_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": None,
    "content-security-policy": None,
}
PAGE_PATHS = (
    "/",
    "/library",
    "/timeline",
    "/events",
    "/reports",
    "/research",
    "/my",
)
API_CHECKS = (
    ("/api/health", "health"),
    ("/api/articles?limit=1&min_score=0", "list"),
    ("/api/reports?type=daily&limit=1", "list"),
    ("/api/stats", "object"),
)


@dataclass(frozen=True)
class HttpEvidence:
    method: str
    url: str
    status_code: int | None
    elapsed_ms: float
    headers: dict[str, str]
    body_bytes: int
    body_sha256: str | None
    body: bytes
    error: str | None = None


Requester = Callable[[str, float, int], HttpEvidence]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def stable_fingerprint(message: str) -> str:
    normalized = re.sub(r"\s+", " ", message).strip()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    return f"{digest}:{normalized}"


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)


def git_value(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def normalized_target(
    base_url: str, environment: str, allowed_hosts: Sequence[str]
) -> tuple[str | None, list[str]]:
    errors: list[str] = []
    if environment not in ALLOWED_ENVIRONMENTS:
        errors.append("environment 只允许 local 或 dev")
    try:
        parsed = urlsplit(base_url)
        _ = parsed.port
    except ValueError as error:
        return None, [f"base_url 无效：{error}"]
    if parsed.scheme not in {"http", "https"}:
        errors.append("base_url 只允许 http 或 https")
    if not parsed.hostname:
        errors.append("base_url 缺少 hostname")
    if parsed.username is not None or parsed.password is not None:
        errors.append("base_url 禁止包含 URL 凭据")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        errors.append("base_url 禁止包含业务 path、query 或 fragment")

    netloc = parsed.netloc.lower()
    hostname = (parsed.hostname or "").lower()
    if environment == "local" and hostname:
        is_loopback = hostname == "localhost"
        try:
            is_loopback = is_loopback or ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            pass
        if not is_loopback:
            errors.append("local 环境只允许 localhost 或 loopback IP")
    if environment == "dev":
        normalized_allowlist = {item.strip().lower() for item in allowed_hosts if item.strip()}
        if not normalized_allowlist:
            errors.append("dev 环境必须显式提供 --allowed-host")
        elif netloc not in normalized_allowlist:
            errors.append(f"dev 目标 {netloc} 不在精确 host 白名单中")

    if errors:
        return None, errors
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return origin, []


def default_request(url: str, timeout: float, max_response_bytes: int) -> HttpEvidence:
    started = time.monotonic()
    try:
        with httpx.Client(
            follow_redirects=False,
            timeout=timeout,
            verify=True,
            trust_env=False,
            headers={
                "Accept": "application/json,text/html;q=0.9",
                "User-Agent": "ai-news-postdeploy-gate/1",
            },
        ) as client:
            with client.stream("GET", url) as response:
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > max_response_bytes:
                        raise RuntimeError(
                            f"响应超过 {max_response_bytes} bytes 安全上限"
                        )
                    chunks.append(chunk)
                body = b"".join(chunks)
                headers = {key.lower(): value for key, value in response.headers.items()}
                return HttpEvidence(
                    method="GET",
                    url=url,
                    status_code=response.status_code,
                    elapsed_ms=round((time.monotonic() - started) * 1000, 3),
                    headers=headers,
                    body_bytes=len(body),
                    body_sha256=hashlib.sha256(body).hexdigest(),
                    body=body,
                )
    except (httpx.HTTPError, OSError, RuntimeError) as error:
        return HttpEvidence(
            method="GET",
            url=url,
            status_code=None,
            elapsed_ms=round((time.monotonic() - started) * 1000, 3),
            headers={},
            body_bytes=0,
            body_sha256=None,
            body=b"",
            error=f"{type(error).__name__}: {error}",
        )


def public_evidence(evidence: HttpEvidence) -> dict:
    payload = asdict(evidence)
    payload.pop("body")
    payload["headers"] = {
        key: value
        for key, value in evidence.headers.items()
        if key in {*REQUIRED_SECURITY_HEADERS, "content-type", "location"}
    }
    return payload


def validate_common(evidence: HttpEvidence) -> list[str]:
    errors: list[str] = []
    if evidence.method != "GET":
        errors.append("检测到非 GET 请求")
    if evidence.error:
        errors.append(evidence.error)
        return errors
    if evidence.status_code != 200:
        errors.append(f"HTTP {evidence.status_code}，期望 200")
    if evidence.status_code is not None and 300 <= evidence.status_code < 400:
        errors.append("禁止重定向")
    for header, expected in REQUIRED_SECURITY_HEADERS.items():
        actual = evidence.headers.get(header, "")
        if not actual:
            errors.append(f"缺少安全响应头 {header}")
        elif expected is not None and actual.lower() != expected.lower():
            errors.append(f"安全响应头 {header}={actual!r} 不符合 {expected!r}")
    return errors


def parse_json(evidence: HttpEvidence) -> tuple[object | None, list[str]]:
    content_type = evidence.headers.get("content-type", "").lower()
    if "application/json" not in content_type:
        return None, [f"Content-Type 不是 application/json：{content_type or '<missing>'}"]
    try:
        return json.loads(evidence.body.decode("utf-8")), []
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        return None, [f"JSON 响应无效：{error}"]


def validate_health(
    evidence: HttpEvidence, expected_environment: str, expected_release: str
) -> list[str]:
    errors = validate_common(evidence)
    payload, json_errors = parse_json(evidence)
    errors.extend(json_errors)
    if isinstance(payload, dict):
        if payload.get("status") != "ok":
            errors.append("health.status 不是 ok")
        if payload.get("environment") != expected_environment:
            errors.append("health.environment 与预期环境不一致")
        if payload.get("release") != expected_release:
            errors.append("health.release 与预期版本不一致")
        if not isinstance(payload.get("db"), dict):
            errors.append("health.db 证据缺失")
    elif not json_errors:
        errors.append("health JSON 顶层不是对象")
    return errors


def validate_page(evidence: HttpEvidence) -> list[str]:
    errors = validate_common(evidence)
    content_type = evidence.headers.get("content-type", "").lower()
    if "text/html" not in content_type:
        errors.append(f"Content-Type 不是 text/html：{content_type or '<missing>'}")
    text = evidence.body.decode("utf-8", errors="replace").lower()
    if "<html" not in text or "</html>" not in text:
        errors.append("HTML 文档结构不完整")
    return errors


def validate_api(evidence: HttpEvidence, expected_type: str) -> list[str]:
    errors = validate_common(evidence)
    payload, json_errors = parse_json(evidence)
    errors.extend(json_errors)
    if not json_errors:
        if expected_type == "list" and not isinstance(payload, list):
            errors.append("API JSON 顶层不是数组")
        if expected_type == "object" and not isinstance(payload, dict):
            errors.append("API JSON 顶层不是对象")
    return errors


def run_check(
    *,
    base_url: str,
    environment: str,
    allowed_hosts: Sequence[str],
    expected_environment: str,
    expected_release: str,
    output_root: Path = DEFAULT_OUTPUT,
    attempts: int = 6,
    retry_interval: float = 5.0,
    timeout: float = 10.0,
    max_response_bytes: int = 2 * 1024 * 1024,
    requester: Requester = default_request,
    sleeper: Callable[[float], None] = time.sleep,
) -> tuple[int, Path, dict]:
    started_at = utc_now()
    run_id = make_run_id()
    run_dir = output_root.resolve() / f"{run_id}-check"
    run_dir.mkdir(parents=True, exist_ok=False)
    origin, policy_errors = normalized_target(base_url, environment, allowed_hosts)
    if expected_environment != environment:
        policy_errors.append("expected_environment 必须与 environment 完全一致")
    if not RELEASE_PATTERN.fullmatch(expected_release or ""):
        policy_errors.append("expected_release 必须是 7..64 位十六进制版本标识")
    if not 1 <= attempts <= 30:
        policy_errors.append("attempts 必须在 1..30")
    if not 0 <= retry_interval <= 60:
        policy_errors.append("retry_interval 必须在 0..60 秒")
    if not 0.1 <= timeout <= 30:
        policy_errors.append("timeout 必须在 0.1..30 秒")
    if not 1024 <= max_response_bytes <= 10 * 1024 * 1024:
        policy_errors.append("max_response_bytes 必须在 1KiB..10MiB")

    readiness: list[dict] = []
    cases: list[dict] = []
    if not policy_errors and origin is not None:
        health_url = origin + "/api/health"
        health_evidence = None
        health_errors: list[str] = []
        for attempt in range(1, attempts + 1):
            health_evidence = requester(health_url, timeout, max_response_bytes)
            health_errors = validate_health(
                health_evidence, expected_environment, expected_release
            )
            readiness.append(
                {
                    "attempt": attempt,
                    "evidence": public_evidence(health_evidence),
                    "validation_errors": health_errors,
                }
            )
            if not health_errors:
                break
            if attempt < attempts:
                sleeper(retry_interval)
        assert health_evidence is not None
        cases.append(
            {
                "name": "health",
                "path": "/api/health",
                "kind": "health",
                "evidence": public_evidence(health_evidence),
                "validation_errors": health_errors,
                "passed": not health_errors,
            }
        )
        if not health_errors:
            for path in PAGE_PATHS:
                evidence = requester(origin + path, timeout, max_response_bytes)
                errors = validate_page(evidence)
                cases.append(
                    {
                        "name": f"page:{path}",
                        "path": path,
                        "kind": "page",
                        "evidence": public_evidence(evidence),
                        "validation_errors": errors,
                        "passed": not errors,
                    }
                )
            for path, expected_type in API_CHECKS[1:]:
                evidence = requester(origin + path, timeout, max_response_bytes)
                errors = validate_api(evidence, expected_type)
                cases.append(
                    {
                        "name": f"api:{path}",
                        "path": path,
                        "kind": "api",
                        "evidence": public_evidence(evidence),
                        "validation_errors": errors,
                        "passed": not errors,
                    }
                )

    failures = [
        f"{case['name']}: {'; '.join(case['validation_errors'])}"
        for case in cases
        if not case["passed"]
    ]
    failures = [*policy_errors, *failures]
    status = "passed" if not failures and len(cases) == 11 else "failed"
    finished_at = utc_now()
    summary = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "command": "check",
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "target": {
            "base_url": origin or base_url,
            "environment": environment,
            "allowed_hosts": list(allowed_hosts),
            "expected_environment": expected_environment,
            "expected_release": expected_release,
            "policy_errors": policy_errors,
        },
        "policy": {
            "methods": ["GET"],
            "follow_redirects": False,
            "trust_environment_proxy": False,
            "tls_verify": True,
            "attempts": attempts,
            "retry_interval_seconds": retry_interval,
            "request_timeout_seconds": timeout,
            "max_response_bytes": max_response_bytes,
        },
        "matrix": {
            "expected_cases": 11,
            "actual_cases": len(cases),
            "pages": len([case for case in cases if case["kind"] == "page"]),
            "apis": len([case for case in cases if case["kind"] in {"api", "health"}]),
        },
        "readiness": readiness,
        "cases": cases,
        "failure_fingerprints": [stable_fingerprint(item) for item in failures],
        "git": {
            "head": git_value("rev-parse", "HEAD"),
            "branch": git_value("branch", "--show-current"),
        },
        "result": {
            "passed": status == "passed",
            "failure_count": len(failures),
        },
        "run_dir": str(run_dir),
    }
    atomic_write_json(run_dir / "summary.json", summary)
    return (0 if status == "passed" else 1), run_dir, summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check")
    check.add_argument("--base-url", required=True)
    check.add_argument("--environment", required=True)
    check.add_argument("--allowed-host", action="append", default=[])
    check.add_argument("--expected-environment", required=True)
    check.add_argument("--expected-release", required=True)
    check.add_argument("--attempts", type=int, default=6)
    check.add_argument("--retry-interval", type=float, default=5.0)
    check.add_argument("--timeout", type=float, default=10.0)
    check.add_argument("--max-response-bytes", type=int, default=2 * 1024 * 1024)
    check.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    code, run_dir, summary = run_check(
        base_url=args.base_url,
        environment=args.environment,
        allowed_hosts=args.allowed_host,
        expected_environment=args.expected_environment,
        expected_release=args.expected_release,
        output_root=args.output_dir,
        attempts=args.attempts,
        retry_interval=args.retry_interval,
        timeout=args.timeout,
        max_response_bytes=args.max_response_bytes,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"postdeploy evidence: {run_dir}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
