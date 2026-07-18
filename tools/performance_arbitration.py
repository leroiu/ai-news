"""仲裁多个独立 GitHub Runner 的性能门禁审计结果。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_RUNS = 3


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify_summary(path: Path) -> dict[str, Any]:
    """把一个性能 summary 归类为通过、预算失败或基础设施失败。"""
    result: dict[str, Any] = {
        "summary_path": str(path),
        "summary_sha256": sha256(path),
        "classification": "infrastructure_error",
        "fingerprints": [],
    }
    try:
        summary = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        result["error"] = f"无法读取性能 summary：{exc}"
        return result

    if not isinstance(summary, dict):
        result["error"] = "性能 summary 必须是 JSON 对象"
        return result

    result["run_id"] = summary.get("run_id")
    result["status"] = summary.get("status")
    result["error"] = summary.get("error", "")
    if summary.get("schema_version") != 1 or summary.get("command") != "check":
        result["error"] = "性能 summary schema 或命令无效"
        return result

    audit = summary.get("audit")
    pollution = summary.get("pollution")
    violations = summary.get("violations")
    exit_codes = audit.get("exit_codes") if isinstance(audit, dict) else None
    valid_audit = (
        isinstance(exit_codes, dict)
        and exit_codes == {"pages": 0, "apis": 0}
        and isinstance(pollution, dict)
        and pollution.get("detected") is False
    )
    if summary.get("status") == "passed":
        if valid_audit and violations == []:
            result["classification"] = "passed"
            return result
        result["error"] = "通过的性能 summary 缺少完整、无污染审计"
        return result
    if (
        summary.get("status") == "failed"
        and valid_audit
        and isinstance(violations, list)
        and violations
        and all(isinstance(item, dict) and item.get("fingerprint") for item in violations)
    ):
        result["classification"] = "budget_regression"
        result["fingerprints"] = [item["fingerprint"] for item in violations]
        return result

    result["error"] = result["error"] or "性能门禁未产生可仲裁的稳定预算失败"
    return result


def arbitrate(summaries: list[Path], expected_runs: int = EXPECTED_RUNS) -> dict[str, Any]:
    """按 0/1/2+ 预算失败规则返回可审计的跨 Runner 结论。"""
    runs = [classify_summary(path) for path in sorted(summaries)]
    result: dict[str, Any] = {
        "schema_version": 1,
        "expected_runs": expected_runs,
        "found_runs": len(runs),
        "runs": runs,
        "status": "failed",
        "verdict": "infrastructure_error",
        "error": "",
    }
    if len(runs) != expected_runs:
        result["error"] = f"性能仲裁需要 {expected_runs} 份审计，实际找到 {len(runs)} 份"
        return result

    infrastructure = [
        run for run in runs if run["classification"] == "infrastructure_error"
    ]
    if infrastructure:
        result["error"] = f"{len(infrastructure)} 个性能 Runner 的审计不完整或基础设施异常"
        return result

    failed = [run for run in runs if run["classification"] == "budget_regression"]
    result["budget_regression_runs"] = len(failed)
    if not failed:
        result.update(status="passed", verdict="passed")
    elif len(failed) == 1:
        result.update(
            status="passed",
            verdict="passed_with_environment_noise",
            error="1 个独立 Runner 出现稳定预算失败，按仲裁策略记录为环境噪声",
        )
    else:
        result.update(
            verdict="inconclusive_budget_regression",
            error=f"{len(failed)} 个独立 Runner 出现稳定预算失败，拒绝自动放行",
        )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-runs", type=int, default=EXPECTED_RUNS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.expected_runs < 1:
        raise ValueError("expected-runs 必须至少为 1")
    summaries = list(args.input_dir.rglob("summary.json"))
    result = arbitrate(summaries, args.expected_runs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
