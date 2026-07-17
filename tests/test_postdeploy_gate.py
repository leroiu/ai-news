from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit

import pytest

from tools.postdeploy_gate import (
    HttpEvidence,
    normalized_target,
    run_check,
)


RELEASE = "a" * 40
SECURITY_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "strict-origin-when-cross-origin",
    "content-security-policy": "default-src 'self'",
}


def evidence(url: str, *, environment: str = "local", release: str = RELEASE) -> HttpEvidence:
    path = urlsplit(url).path
    if path == "/api/health":
        payload: object = {
            "status": "ok",
            "environment": environment,
            "release": release,
            "db": {"entities": 1, "articles": 1, "reports": 1},
        }
        content_type = "application/json"
    elif path in {"/api/articles", "/api/reports"}:
        payload = []
        content_type = "application/json"
    elif path == "/api/stats":
        payload = {"articles": 1}
        content_type = "application/json"
    else:
        payload = "<!doctype html><html><main>ok</main></html>"
        content_type = "text/html; charset=utf-8"
    body = (
        json.dumps(payload).encode("utf-8")
        if content_type == "application/json"
        else str(payload).encode("utf-8")
    )
    return HttpEvidence(
        method="GET",
        url=url,
        status_code=200,
        elapsed_ms=1.25,
        headers={**SECURITY_HEADERS, "content-type": content_type},
        body_bytes=len(body),
        body_sha256=hashlib.sha256(body).hexdigest(),
        body=body,
    )


@pytest.mark.parametrize(
    ("base_url", "environment", "allowed_hosts", "message"),
    [
        ("ftp://127.0.0.1", "local", [], "http 或 https"),
        ("http://user:pass@127.0.0.1", "local", [], "URL 凭据"),
        ("http://127.0.0.1/api?x=1", "local", [], "path、query"),
        ("http://example.test", "local", [], "loopback"),
        ("https://dev.example.test", "dev", [], "--allowed-host"),
        ("https://dev.example.test", "dev", ["other.example.test"], "不在精确 host"),
        ("https://prod.example.test", "production", ["prod.example.test"], "local 或 dev"),
    ],
)
def test_target_policy_rejects_unsafe_or_unapproved_targets(
    base_url, environment, allowed_hosts, message
):
    origin, errors = normalized_target(base_url, environment, allowed_hosts)

    assert origin is None
    assert any(message in error for error in errors)


def test_target_policy_accepts_loopback_and_exact_dev_host():
    assert normalized_target("http://127.0.0.1:8765", "local", [])[0] == (
        "http://127.0.0.1:8765"
    )
    assert normalized_target(
        "https://dev.example.test:8443",
        "dev",
        ["dev.example.test:8443"],
    )[0] == "https://dev.example.test:8443"


def test_check_passes_exact_read_only_matrix_and_writes_summary(tmp_path: Path):
    calls: list[str] = []

    def requester(url, _timeout, _limit):
        calls.append(url)
        return evidence(url)

    code, run_dir, summary = run_check(
        base_url="http://127.0.0.1:8765",
        environment="local",
        allowed_hosts=[],
        expected_environment="local",
        expected_release=RELEASE,
        output_root=tmp_path,
        attempts=2,
        retry_interval=0,
        requester=requester,
    )

    assert code == 0
    assert summary["status"] == "passed"
    assert summary["matrix"] == {
        "expected_cases": 11,
        "actual_cases": 11,
        "pages": 7,
        "apis": 4,
    }
    assert len(calls) == 11
    assert {case["evidence"]["method"] for case in summary["cases"]} == {"GET"}
    assert all("body" not in case["evidence"] for case in summary["cases"])
    assert json.loads((run_dir / "summary.json").read_text(encoding="utf-8")) == summary


def test_readiness_retries_are_bounded_and_preserved(tmp_path: Path):
    health_calls = 0
    sleeps: list[float] = []

    def requester(url, _timeout, _limit):
        nonlocal health_calls
        result = evidence(url)
        if url.endswith("/api/health"):
            health_calls += 1
            if health_calls == 1:
                return HttpEvidence(
                    **{**result.__dict__, "status_code": 503}
                )
        return result

    code, _, summary = run_check(
        base_url="http://localhost:8765",
        environment="local",
        allowed_hosts=[],
        expected_environment="local",
        expected_release=RELEASE,
        output_root=tmp_path,
        attempts=3,
        retry_interval=0.25,
        requester=requester,
        sleeper=sleeps.append,
    )

    assert code == 0
    assert len(summary["readiness"]) == 2
    assert summary["readiness"][0]["validation_errors"]
    assert summary["readiness"][1]["validation_errors"] == []
    assert sleeps == [0.25]


@pytest.mark.parametrize("mutation", ["redirect", "release", "headers", "content_type", "oversize"])
def test_semantic_and_transport_failures_cannot_pass(tmp_path: Path, mutation: str):
    def requester(url, _timeout, _limit):
        result = evidence(url)
        if not url.endswith("/api/health"):
            return result
        values = dict(result.__dict__)
        if mutation == "redirect":
            values.update(status_code=302, headers={**result.headers, "location": "https://evil.test"})
        elif mutation == "release":
            return evidence(url, release="b" * 40)
        elif mutation == "headers":
            values.update(headers={"content-type": "application/json"})
        elif mutation == "content_type":
            values.update(headers={**result.headers, "content-type": "text/html"})
        else:
            values.update(
                status_code=None,
                body=b"",
                body_bytes=0,
                body_sha256=None,
                error="RuntimeError: 响应超过安全上限",
            )
        return HttpEvidence(**values)

    code, _, summary = run_check(
        base_url="http://127.0.0.1:8765",
        environment="local",
        allowed_hosts=[],
        expected_environment="local",
        expected_release=RELEASE,
        output_root=tmp_path,
        attempts=1,
        retry_interval=0,
        requester=requester,
    )

    assert code == 1
    assert summary["status"] == "failed"
    assert summary["failure_fingerprints"]
    assert len(summary["cases"]) == 1


def test_invalid_contract_never_sends_request(tmp_path: Path):
    def requester(*_args):
        raise AssertionError("策略失败后不应发送请求")

    code, _, summary = run_check(
        base_url="https://production.example.test",
        environment="production",
        allowed_hosts=["production.example.test"],
        expected_environment="production",
        expected_release=RELEASE,
        output_root=tmp_path,
        requester=requester,
    )

    assert code == 1
    assert summary["cases"] == []
    assert summary["target"]["policy_errors"]


def test_real_loopback_http_round_trip_uses_only_get(tmp_path: Path):
    class Handler(BaseHTTPRequestHandler):
        methods: list[str] = []

        def log_message(self, *_args):
            pass

        def do_GET(self):
            self.methods.append("GET")
            url = f"http://127.0.0.1:{self.server.server_port}{self.path}"
            result = evidence(url)
            self.send_response(200)
            for key, value in result.headers.items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(result.body)))
            self.end_headers()
            self.wfile.write(result.body)

        def do_POST(self):
            self.methods.append("POST")
            self.send_error(405)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        code, _, summary = run_check(
            base_url=f"http://127.0.0.1:{server.server_port}",
            environment="local",
            allowed_hosts=[],
            expected_environment="local",
            expected_release=RELEASE,
            output_root=tmp_path,
            attempts=1,
            retry_interval=0,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert code == 0
    assert summary["status"] == "passed"
    assert Handler.methods == ["GET"] * 11
