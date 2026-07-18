"""把门禁 summary 转换为供长程 Agent 消费的只读诊断计划。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SAFE_COMMANDS = {
    "quality": "uv run --frozen python tools/quality_gate.py checkpoint",
    "browser": "uv run --frozen python tools/browser_gate.py --profile core",
    "accessibility": "uv run --frozen python tools/accessibility_gate.py check",
    "performance": "uv run --frozen python tools/performance_gate.py check",
    "performance-arbitration": (
        "uv run --frozen pytest tests/test_performance_arbitration.py "
        "tests/test_ci_workflow.py -q"
    ),
}
GATES = tuple(SAFE_COMMANDS)
UNSAFE_TOKENS = ("deploy", "git ", "gh ", "curl", "wget", "ssh", "http://", "https://")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _fingerprints(items: Any) -> list[str]:
    _require(isinstance(items, list), "违规记录必须是列表")
    values = []
    for item in items:
        _require(isinstance(item, dict) and isinstance(item.get("fingerprint"), str), "违规记录缺少 fingerprint")
        values.append(item["fingerprint"])
    return values


def _string_fingerprints(items: Any) -> list[str]:
    _require(isinstance(items, list) and all(isinstance(item, str) and item for item in items), "质量失败指纹必须是非空字符串列表")
    return list(items)


def _base(gate: str, path: Path, summary: dict) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "gate": gate,
        "source": {"summary_path": str(path), "summary_sha256": _sha256(path)},
        "status": summary.get("status", summary.get("result")),
        "classification": "",
        "fingerprints": [],
        "suggested_commands": [],
        "needs_human": False,
        "reason": "",
    }


def _failed(result: dict, classification: str, reason: str, fingerprints: list[str] | None = None, *, needs_human: bool = False) -> dict:
    result.update(
        classification=classification,
        reason=reason,
        fingerprints=fingerprints or [],
        suggested_commands=[SAFE_COMMANDS[result["gate"]]],
        needs_human=needs_human,
    )
    return result


def _diagnose_quality(result: dict, summary: dict) -> dict:
    _require(summary.get("result") in {"pass", "test_failure", "coverage_regression", "timeout", "infra_error", "git_pollution"}, "quality result 无效")
    _require(isinstance(summary.get("exit_code"), int), "quality 缺少 exit_code")
    _require(isinstance(summary.get("test_counts"), dict), "quality 缺少 test_counts")
    fingerprints = _string_fingerprints(summary.get("failure_fingerprints"))
    passed = summary["result"] == "pass"
    _require(passed == (summary["exit_code"] == 0), "quality result 与 exit_code 不一致")
    if passed:
        _require(not fingerprints and not summary.get("git_content_changed") and not summary.get("runtime_content_changed"), "quality 通过结果包含失败证据")
        result.update(classification="continue", reason="质量门禁通过")
        return result
    classification = str(summary["result"])
    return _failed(result, classification, "质量门禁失败", fingerprints, needs_human=classification in {"infra_error", "timeout", "git_pollution"})


def _diagnose_browser(result: dict, summary: dict) -> dict:
    _require(summary.get("schema_version") == 1 and summary.get("status") in {"passed", "failed"}, "browser summary 无效")
    browser = summary.get("browser")
    pollution = summary.get("pollution")
    _require(isinstance(browser, dict) and isinstance(pollution, dict), "browser 缺少审计或污染证据")
    exit_code = browser.get("exit_code")
    _require(isinstance(exit_code, int) or exit_code is None, "browser exit_code 无效")
    if summary["status"] == "passed":
        _require(exit_code == 0 and pollution.get("detected") is False and not summary.get("error"), "browser 通过结果包含失败证据")
        result.update(classification="continue", reason="浏览器门禁通过")
        return result
    return _failed(result, "browser_failure", str(summary.get("error") or "浏览器门禁失败"), needs_human=pollution.get("detected") is True or exit_code is None)


def _diagnose_accessibility(result: dict, summary: dict) -> dict:
    _require(summary.get("schema_version") == 1 and summary.get("status") in {"passed", "failed"}, "accessibility summary 无效")
    audit = summary.get("audit")
    pollution = summary.get("pollution")
    comparison = summary.get("comparison")
    _require(isinstance(audit, dict) and isinstance(pollution, dict) and isinstance(comparison, dict), "accessibility 缺少审计、比较或污染证据")
    exit_code = audit.get("exit_code")
    _require(isinstance(exit_code, int) or exit_code is None, "accessibility exit_code 无效")
    new = comparison.get("new")
    _require(isinstance(new, list), "accessibility comparison.new 无效")
    fingerprints = _fingerprints(new)
    if summary["status"] == "passed":
        _require(exit_code == 0 and not fingerprints and pollution.get("detected") is False and not summary.get("error"), "accessibility 通过结果包含失败证据")
        result.update(classification="continue", reason="可访问性门禁通过")
        return result
    return _failed(result, "accessibility_failure", str(summary.get("error") or "可访问性门禁失败"), fingerprints, needs_human=not fingerprints)


def _diagnose_performance(result: dict, summary: dict) -> dict:
    _require(summary.get("schema_version") == 1 and summary.get("command") == "check" and summary.get("status") in {"passed", "failed"}, "performance summary 无效")
    audit = summary.get("audit")
    pollution = summary.get("pollution")
    _require(isinstance(audit, dict) and isinstance(pollution, dict), "performance 缺少审计或污染证据")
    _require(audit.get("exit_codes") == {"pages": 0, "apis": 0}, "performance 审计退出码无效")
    fingerprints = _fingerprints(summary.get("violations"))
    if summary["status"] == "passed":
        _require(not fingerprints and pollution.get("detected") is False and not summary.get("error"), "performance 通过结果包含失败证据")
        result.update(classification="continue", reason="性能门禁通过")
        return result
    return _failed(result, "stable_performance_regression", str(summary.get("error") or "稳定性能预算回归"), fingerprints, needs_human=True)


def _diagnose_arbitration(result: dict, summary: dict) -> dict:
    _require(summary.get("schema_version") == 1 and summary.get("status") in {"passed", "failed"}, "performance-arbitration summary 无效")
    expected, found = summary.get("expected_runs"), summary.get("found_runs")
    verdict = summary.get("verdict")
    _require(expected == 3 and isinstance(found, int) and isinstance(summary.get("runs"), list), "performance-arbitration Runner 证据无效")
    failures = summary.get("budget_regression_runs")
    _require(isinstance(failures, int) and failures >= 0, "performance-arbitration 失败计数无效")
    if summary["status"] == "passed":
        _require(found == 3 and verdict in {"passed", "passed_with_environment_noise"}, "performance-arbitration 通过结果无效")
        _require((verdict == "passed") == (failures == 0), "performance-arbitration 通过计数不一致")
        _require((verdict == "passed_with_environment_noise") == (failures == 1), "performance-arbitration 噪声计数不一致")
        result.update(classification="continue" if failures == 0 else "environment_noise", reason="性能仲裁通过")
        return result
    _require(verdict in {"infrastructure_error", "inconclusive_budget_regression"}, "performance-arbitration 失败结论无效")
    if verdict == "inconclusive_budget_regression":
        _require(found == 3 and failures >= 2, "performance-arbitration 回归计数不一致")
    return _failed(result, verdict, str(summary.get("error") or "性能仲裁阻断"), needs_human=True)


DIAGNOSERS = {
    "quality": _diagnose_quality,
    "browser": _diagnose_browser,
    "accessibility": _diagnose_accessibility,
    "performance": _diagnose_performance,
    "performance-arbitration": _diagnose_arbitration,
}


def diagnose(gate: str, summary_path: Path) -> dict[str, Any]:
    _require(gate in DIAGNOSERS, f"未知门禁：{gate}")
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取 summary：{exc}") from exc
    _require(isinstance(summary, dict), "summary 必须是 JSON 对象")
    result = _base(gate, summary_path, summary)
    result = DIAGNOSERS[gate](result, summary)
    for command in result["suggested_commands"]:
        _require(not any(token in command.lower() for token in UNSAFE_TOKENS), "诊断命令违反只读策略")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", choices=GATES, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        diagnosis = diagnose(args.gate, args.summary)
    except ValueError as exc:
        diagnosis = {"schema_version": 1, "status": "failed", "classification": "invalid_evidence", "reason": str(exc), "needs_human": True}
        exit_code = 1
    else:
        diagnosis["status"] = "passed"
        exit_code = 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(diagnosis, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(diagnosis, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
