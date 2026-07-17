"""隔离可访问性回归门禁：真实 Chromium + 显式历史违规基线。"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.browser_gate import (  # noqa: E402
    CORE_ROUTES,
    FIXED_BROWSER_TIME,
    free_port,
    prepare_runtime,
    protected_digest,
    start_server,
    stop_server,
)


DEFAULT_OUTPUT = ROOT / "output" / "accessibility-gate"
DEFAULT_BASELINE = ROOT / ".quality" / "accessibility-baseline.json"
EXPECTED_CASES = ["desktop-dark", "desktop-light", "mobile-dark"]
RULE_VERSION = 3


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def run_audit(base_url: str, run_dir: Path) -> subprocess.CompletedProcess[str]:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("未找到 Node.js，无法运行可访问性 Chromium 审计")
    env = os.environ.copy()
    env.update(
        {
            "ACCESSIBILITY_BASE_URL": base_url,
            "ACCESSIBILITY_ROUTES": json.dumps(CORE_ROUTES, ensure_ascii=False),
            "ACCESSIBILITY_OUTPUT_DIR": str(run_dir / "audit"),
            "ACCESSIBILITY_FIXED_TIME": FIXED_BROWSER_TIME,
        }
    )
    return subprocess.run(
        [node, "tools/accessibility_audit.mjs"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=240,
        check=False,
    )


def validate_audit(audit: dict) -> str:
    if audit.get("schemaVersion") != 1:
        return "audit schemaVersion 无效"
    if audit.get("ruleVersion") != RULE_VERSION:
        return "audit ruleVersion 无效"
    if audit.get("routes") != CORE_ROUTES:
        return "audit 路由矩阵与核心路由不一致"
    if audit.get("cases") != EXPECTED_CASES:
        return "audit case 矩阵无效"
    if audit.get("summary", {}).get("checks") != len(CORE_ROUTES) * len(EXPECTED_CASES):
        return "audit 案例数量不完整"
    results = audit.get("results")
    if not isinstance(results, list):
        return "audit results 无效"
    expected_matrix = {
        (route, case) for route in CORE_ROUTES for case in EXPECTED_CASES
    }
    actual_matrix = []
    result_violations = []
    for index, result in enumerate(results):
        if not isinstance(result, dict):
            return f"audit result {index} 不是对象"
        route = result.get("route")
        case = result.get("case")
        if route not in CORE_ROUTES or case not in EXPECTED_CASES:
            return f"audit result {index} 不属于声明矩阵"
        if not isinstance(result.get("violations"), list):
            return f"audit result {index} violations 无效"
        actual_matrix.append((route, case))
        result_violations.extend(result["violations"])
    if len(actual_matrix) != len(expected_matrix) or set(actual_matrix) != expected_matrix:
        return "audit results 缺少、重复或包含额外 route×case"
    violations = audit.get("violations")
    if not isinstance(violations, list):
        return "audit violations 无效"
    records_error = validate_violation_records(
        violations, routes=CORE_ROUTES, cases=EXPECTED_CASES
    )
    if records_error:
        return f"audit 违规记录无效：{records_error}"
    if audit.get("summary", {}).get("violations") != len(violations):
        return "audit 违规计数与记录数量不一致"
    top_fingerprints = sorted(item["fingerprint"] for item in violations)
    result_fingerprints = sorted(
        item.get("fingerprint")
        for item in result_violations
        if isinstance(item, dict)
    )
    if top_fingerprints != result_fingerprints:
        return "audit 顶层 violations 与逐案例结果不一致"
    infrastructure = audit.get("infrastructureFailures")
    if not isinstance(infrastructure, list):
        return "audit infrastructureFailures 无效"
    if audit.get("summary", {}).get("infrastructureFailures") != len(infrastructure):
        return "audit 基础设施失败计数不一致"
    return ""


def violation_map(audit: dict) -> dict[str, dict]:
    return {
        item["fingerprint"]: item
        for item in audit.get("violations", [])
        if isinstance(item, dict) and item.get("fingerprint")
    }


def validate_violation_records(
    violations: list,
    *,
    routes: list[str] | None = None,
    cases: list[str] | None = None,
) -> str:
    fingerprints = []
    for index, item in enumerate(violations):
        if not isinstance(item, dict):
            return f"违规记录 {index} 不是对象"
        required = ("rule", "route", "case", "selector", "detail", "fingerprint")
        if any(not isinstance(item.get(key), str) or not item[key] for key in required):
            return f"违规记录 {index} 缺少稳定字段"
        expected = "|".join(
            [item["rule"], item["route"], item["case"], item["selector"]]
        )
        if item["fingerprint"] != expected:
            return f"违规记录 {index} 指纹与字段不一致"
        if routes is not None and item["route"] not in routes:
            return f"违规记录 {index} route 不属于审计矩阵"
        if cases is not None and item["case"] not in cases:
            return f"违规记录 {index} case 不属于审计矩阵"
        fingerprints.append(item["fingerprint"])
    if len(fingerprints) != len(set(fingerprints)):
        return "违规记录包含重复指纹"
    return ""


def compare_baseline(audit: dict, baseline: dict) -> dict:
    current = violation_map(audit)
    expected = {
        item["fingerprint"]: item
        for item in baseline.get("violations", [])
        if isinstance(item, dict) and item.get("fingerprint")
    }
    current_keys = set(current)
    expected_keys = set(expected)
    return {
        "known": [current[key] for key in sorted(current_keys & expected_keys)],
        "new": [current[key] for key in sorted(current_keys - expected_keys)],
        "resolved": [expected[key] for key in sorted(expected_keys - current_keys)],
    }


def load_baseline(path: Path, audit: dict) -> tuple[dict | None, str]:
    try:
        baseline = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"缺少可访问性基线：{path}"
    except (OSError, json.JSONDecodeError) as error:
        return None, f"无法读取可访问性基线：{error}"
    if baseline.get("schema_version") != 1:
        return None, "可访问性基线 schema_version 无效"
    if baseline.get("rule_version") != audit.get("ruleVersion"):
        return None, "可访问性规则版本变化，必须显式重建基线"
    if baseline.get("routes") != audit.get("routes"):
        return None, "可访问性基线路由矩阵不匹配"
    if baseline.get("cases") != audit.get("cases"):
        return None, "可访问性基线 case 矩阵不匹配"
    violations = baseline.get("violations")
    if not isinstance(violations, list):
        return None, "可访问性基线 violations 无效"
    records_error = validate_violation_records(
        violations,
        routes=baseline.get("routes"),
        cases=baseline.get("cases"),
    )
    if records_error:
        return None, f"可访问性基线无效：{records_error}"
    if baseline.get("violation_count") != len(violations):
        return None, "可访问性基线 violation_count 与记录数量不一致"
    evidence_value = baseline.get("evidence")
    evidence_digest = baseline.get("evidence_sha256")
    if not isinstance(evidence_value, str) or not evidence_value:
        return None, "可访问性基线缺少 evidence 路径"
    if (
        not isinstance(evidence_digest, str)
        or len(evidence_digest) != 64
        or any(char not in "0123456789abcdef" for char in evidence_digest)
    ):
        return None, "可访问性基线 evidence_sha256 无效"
    evidence_path = Path(evidence_value)
    if not evidence_path.is_absolute():
        evidence_path = ROOT / evidence_path
    try:
        if file_sha256(evidence_path) != evidence_digest:
            return None, "可访问性基线原始证据 SHA-256 不匹配"
        evidence_audit = json.loads(evidence_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"可访问性基线证据不存在：{evidence_path}"
    except (OSError, json.JSONDecodeError) as error:
        return None, f"无法读取可访问性基线证据：{error}"
    evidence_error = validate_audit(evidence_audit)
    if evidence_error:
        return None, f"可访问性基线原始证据无效：{evidence_error}"
    if evidence_audit.get("violations") != violations:
        return None, "可访问性基线 violations 与原始证据不一致"
    return baseline, ""


def create_baseline(path: Path, audit: dict, evidence: Path, force: bool) -> dict:
    if path.exists() and not force:
        raise RuntimeError(f"基线已存在：{path}；如需明确替换请使用 --force")
    resolved_evidence = evidence.resolve()
    if not resolved_evidence.is_file():
        raise RuntimeError(f"可访问性基线原始证据不存在：{resolved_evidence}")
    try:
        evidence_audit = json.loads(resolved_evidence.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"无法读取可访问性基线原始证据：{error}") from error
    if evidence_audit != audit:
        raise RuntimeError("可访问性基线原始证据与待保存 audit 不一致")
    try:
        stored_evidence = resolved_evidence.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        stored_evidence = str(resolved_evidence)
    payload = {
        "schema_version": 1,
        "rule_version": audit["ruleVersion"],
        "created_at": utc_now(),
        "routes": audit["routes"],
        "cases": audit["cases"],
        "violation_count": len(audit.get("violations", [])),
        "violations": audit.get("violations", []),
        "evidence": stored_evidence,
        "evidence_sha256": file_sha256(resolved_evidence),
        "policy": "普通 check 只读取基线；新增违规失败，已修复违规列为 resolved。基线变更必须显式 baseline --force。",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("baseline", "check"):
        command = subparsers.add_parser(name)
        command.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
        command.add_argument("--baseline-path", type=Path, default=DEFAULT_BASELINE)
        if name == "baseline":
            command.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_id = make_run_id()
    run_dir = args.output_dir.resolve() / f"{run_id}-{args.command}"
    run_dir.mkdir(parents=True, exist_ok=False)
    before_digest, before_counts = protected_digest()
    process = None
    fixture = None
    audit_result = None
    audit = None
    baseline = None
    comparison = {"known": [], "new": [], "resolved": []}
    error = ""
    try:
        fixture = prepare_runtime(run_dir)
        port = free_port()
        process = start_server(Path(fixture["runtime"]), port, run_dir)
        audit_result = run_audit(f"http://127.0.0.1:{port}", run_dir)
        (run_dir / "audit.stdout.log").write_text(
            audit_result.stdout, encoding="utf-8"
        )
        (run_dir / "audit.stderr.log").write_text(
            audit_result.stderr, encoding="utf-8"
        )
        audit_path = run_dir / "audit" / "audit.json"
        if not audit_path.is_file():
            raise RuntimeError("Chromium 未生成 audit.json")
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        validation_error = validate_audit(audit)
        if validation_error:
            raise RuntimeError(validation_error)
        if audit_result.returncode:
            raise RuntimeError(
                f"Chromium 可访问性审计基础设施失败，退出码 {audit_result.returncode}"
            )
        if args.command == "baseline":
            if args.baseline_path.resolve().exists() and not args.force:
                raise RuntimeError(
                    f"基线已存在：{args.baseline_path.resolve()}；"
                    "如需明确替换请使用 --force"
                )
        else:
            baseline, baseline_error = load_baseline(
                args.baseline_path.resolve(), audit
            )
            if baseline_error:
                raise RuntimeError(baseline_error)
            comparison = compare_baseline(audit, baseline)
            if comparison["new"]:
                error = f"发现 {len(comparison['new'])} 个新增可访问性违规"
    except (
        OSError,
        RuntimeError,
        subprocess.SubprocessError,
        json.JSONDecodeError,
    ) as exc:
        error = str(exc)
    finally:
        stop_server(process)

    after_digest, after_counts = protected_digest()
    pollution = before_digest != after_digest
    if pollution and not error:
        error = "可访问性门禁修改了受保护业务运行目录"
    if args.command == "baseline" and not error and audit:
        try:
            baseline = create_baseline(
                args.baseline_path.resolve(),
                audit,
                run_dir / "audit" / "audit.json",
                args.force,
            )
            comparison["known"] = audit.get("violations", [])
        except (OSError, RuntimeError) as exc:
            error = str(exc)
    status = "passed" if not error else "failed"
    summary = {
        "schema_version": 1,
        "run_id": run_id,
        "command": args.command,
        "status": status,
        "generated_at": utc_now(),
        "routes": CORE_ROUTES,
        "cases": EXPECTED_CASES,
        "fixture": fixture,
        "audit": {
            "exit_code": audit_result.returncode if audit_result else None,
            "summary": audit.get("summary") if audit else None,
            "rule_version": audit.get("ruleVersion") if audit else None,
            "path": str(run_dir / "audit" / "audit.json"),
        },
        "baseline": {
            "path": str(args.baseline_path.resolve()),
            "violation_count": baseline.get("violation_count") if baseline else None,
        },
        "comparison": {
            "known_count": len(comparison["known"]),
            "new_count": len(comparison["new"]),
            "resolved_count": len(comparison["resolved"]),
            **comparison,
        },
        "pollution": {
            "detected": pollution,
            "before_digest": before_digest,
            "after_digest": after_digest,
            "before_counts": before_counts,
            "after_counts": after_counts,
        },
        "error": error,
        "run_dir": str(run_dir),
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": status,
                "run_dir": str(run_dir),
                "checks": (audit or {}).get("summary", {}).get("checks", 0),
                "known": len(comparison["known"]),
                "new": len(comparison["new"]),
                "resolved": len(comparison["resolved"]),
                "pollution": pollution,
                "error": error,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
