"""把门禁 summary 转换为供长程 Agent 消费的只读诊断计划。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

try:  # 支持 `python tools/...py` 与作为 tests 中模块导入两种入口。
    from tools.performance_arbitration import classify_summary as classify_performance_summary
except ModuleNotFoundError:  # pragma: no cover - 仅脚本直接执行时触发。
    from performance_arbitration import classify_summary as classify_performance_summary


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


def _nonempty_string(value: Any, message: str) -> str:
    _require(isinstance(value, str) and value.strip(), message)
    return value


def _nonnegative_number(value: Any, message: str) -> float:
    _require(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0,
        message,
    )
    return float(value)


def _require_keys(mapping: Any, keys: tuple[str, ...], message: str) -> dict:
    _require(isinstance(mapping, dict) and all(key in mapping for key in keys), message)
    return mapping


def _complete_pollution(pollution: Any, gate: str) -> dict:
    evidence = _require_keys(
        pollution,
        ("detected", "before_digest", "after_digest", "before_counts", "after_counts"),
        f"{gate} 缺少完整污染审计",
    )
    _require(isinstance(evidence["detected"], bool), f"{gate} 污染状态无效")
    _nonempty_string(evidence["before_digest"], f"{gate} 缺少污染前摘要")
    _nonempty_string(evidence["after_digest"], f"{gate} 缺少污染后摘要")
    _require(
        isinstance(evidence["before_counts"], dict)
        and isinstance(evidence["after_counts"], dict),
        f"{gate} 污染计数无效",
    )
    return evidence


def _require_run_metadata(summary: dict, gate: str) -> None:
    for key in ("run_id", "generated_at", "run_dir"):
        _nonempty_string(summary.get(key), f"{gate} 缺少 {key}")


def _resolve_runner_summary(source_summary: Path, reported_path: str, evidence_root: Path | None) -> Path:
    root = (evidence_root or source_summary.parent).resolve()
    candidate = (root / reported_path).resolve()
    _require(candidate.is_relative_to(root) and candidate.is_file(), "performance-arbitration Runner summary 不在受控证据目录中")
    return candidate


def _complete_arbitration_run(run: Any, source_summary: Path, evidence_root: Path | None) -> dict:
    evidence = _require_keys(
        run,
        ("summary_path", "summary_sha256", "classification", "fingerprints", "run_id", "status", "error"),
        "performance-arbitration Runner 缺少完整证据",
    )
    reported_path = _nonempty_string(evidence["summary_path"], "performance-arbitration Runner 缺少 summary_path")
    digest = _nonempty_string(evidence["summary_sha256"], "performance-arbitration Runner 缺少 summary_sha256")
    _require(len(digest) == 64 and all(char in "0123456789abcdef" for char in digest.lower()), "performance-arbitration Runner SHA-256 无效")
    _nonempty_string(evidence["run_id"], "performance-arbitration Runner 缺少 run_id")
    _require(evidence["classification"] in {"passed", "budget_regression", "infrastructure_error"}, "performance-arbitration Runner 分类无效")
    _require(evidence["status"] in {"passed", "failed"}, "performance-arbitration Runner 状态无效")
    _require(isinstance(evidence["error"], str), "performance-arbitration Runner error 无效")
    fingerprints = _string_fingerprints(evidence["fingerprints"])
    if evidence["classification"] == "passed":
        _require(evidence["status"] == "passed" and not fingerprints and not evidence["error"], "performance-arbitration 通过 Runner 包含失败证据")
    elif evidence["classification"] == "budget_regression":
        _require(evidence["status"] == "failed" and fingerprints, "performance-arbitration 预算回归 Runner 缺少指纹")
    else:
        _require(evidence["status"] == "failed" and evidence["error"], "performance-arbitration 基础设施异常 Runner 缺少错误")
    runner_summary = _resolve_runner_summary(source_summary, reported_path, evidence_root)
    _require(_sha256(runner_summary) == digest, "performance-arbitration Runner SHA-256 与内容不匹配")
    classified = classify_performance_summary(runner_summary)
    _require(classified.get("classification") == evidence["classification"], "performance-arbitration Runner 分类与原始证据不一致")
    _require(classified.get("run_id") == evidence["run_id"] and classified.get("status") == evidence["status"], "performance-arbitration Runner 身份或状态与原始证据不一致")
    _require(classified.get("fingerprints", []) == fingerprints, "performance-arbitration Runner 指纹与原始证据不一致")
    if evidence["classification"] == "passed":
        _require(diagnose("performance", runner_summary)["classification"] == "continue", "performance-arbitration 通过 Runner 未通过完整性能诊断")
    return evidence


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
    for key in (
        "run_id", "profile", "started_at", "finished_at", "working_directory",
        "python_executable", "git_branch", "git_head", "git_digest_before",
        "git_digest_after", "runtime_digest_before", "runtime_digest_after",
        "coverage_baseline_path", "evidence_directory",
    ):
        _nonempty_string(summary.get(key), f"quality 缺少 {key}")
    for key in ("duration_seconds", "pytest_duration_seconds"):
        _nonnegative_number(summary.get(key), f"quality {key} 无效")
    for key in ("initial_status_count", "pytest_returncode"):
        _require(isinstance(summary.get(key), int), f"quality {key} 无效")
    _require(summary.get("process_tree_cleaned") is None or isinstance(summary.get("process_tree_cleaned"), bool), "quality process_tree_cleaned 无效")
    _require(isinstance(summary.get("exit_code"), int), "quality 缺少 exit_code")
    counts = summary.get("test_counts")
    _require(isinstance(counts, dict) and counts and all(isinstance(value, int) and value >= 0 for value in counts.values()), "quality test_counts 无效")
    _require(isinstance(summary.get("git_status_added"), list) and isinstance(summary.get("git_status_removed"), list), "quality Git 审计无效")
    _require(isinstance(summary.get("protected_runtime_paths"), list), "quality 受保护路径审计无效")
    _require(isinstance(summary.get("coverage_enabled"), bool), "quality coverage_enabled 无效")
    coverage = _require_keys(summary.get("coverage_summary"), ("percent_covered",), "quality 缺少 coverage_summary")
    _nonnegative_number(coverage["percent_covered"], "quality coverage 百分比无效")
    baseline = _require_keys(summary.get("coverage_baseline"), ("minimum_percent",), "quality 缺少 coverage_baseline")
    _nonnegative_number(baseline["minimum_percent"], "quality coverage 基线无效")
    fingerprints = _string_fingerprints(summary.get("failure_fingerprints"))
    passed = summary["result"] == "pass"
    _require(passed == (summary["exit_code"] == 0), "quality result 与 exit_code 不一致")
    if passed:
        _require(counts.get("passed", 0) > 0, "quality 通过结果缺少通过测试计数")
        outcomes = sum(counts.get(key, 0) for key in ("passed", "failed", "errors", "skipped", "xfailed", "xpassed"))
        _require("collected" not in counts or counts["collected"] == outcomes, "quality 测试计数不一致")
        _require(not counts.get("failed", 0) and not counts.get("errors", 0) and not counts.get("xpassed", 0), "quality 通过结果包含失败测试计数")
        _require(summary["git_digest_before"] == summary["git_digest_after"] and summary["runtime_digest_before"] == summary["runtime_digest_after"], "quality 通过结果的摘要发生变化")
        _require(not summary["git_status_added"] and not summary["git_status_removed"], "quality 通过结果包含 Git 状态变化")
        _require(not fingerprints and not summary.get("git_content_changed") and not summary.get("runtime_content_changed"), "quality 通过结果包含失败证据")
        result.update(classification="continue", reason="质量门禁通过")
        return result
    classification = str(summary["result"])
    return _failed(result, classification, "质量门禁失败", fingerprints, needs_human=classification in {"infra_error", "timeout", "git_pollution"})


def _diagnose_browser(result: dict, summary: dict) -> dict:
    _require(summary.get("schema_version") == 1 and summary.get("status") in {"passed", "failed"}, "browser summary 无效")
    _require_run_metadata(summary, "browser")
    _require(summary.get("profile") == "core" and summary.get("prepare_only") is False, "browser 不是完整 core 审计")
    _require(isinstance(summary.get("routes"), list) and summary["routes"], "browser 缺少路由证据")
    _require(isinstance(summary.get("viewports"), list) and len(summary["viewports"]) >= 2, "browser 缺少视口证据")
    network = _require_keys(summary.get("network"), ("policy", "allowed_external_origins"), "browser 缺少网络策略证据")
    _require(network["policy"] == "loopback-only" and network["allowed_external_origins"] == [], "browser 网络策略不安全")
    _nonempty_string(summary.get("fixed_browser_time"), "browser 缺少固定时间证据")
    _require(isinstance(summary.get("runtime"), dict), "browser 缺少隔离运行时证据")
    browser = summary.get("browser")
    pollution = _complete_pollution(summary.get("pollution"), "browser")
    _require(isinstance(browser, dict), "browser 缺少审计证据")
    exit_code = browser.get("exit_code")
    _require(isinstance(exit_code, int) or exit_code is None, "browser exit_code 无效")
    _require(isinstance(browser.get("stdout"), str) and isinstance(browser.get("stderr"), str), "browser 缺少进程证据")
    audit = _require_keys(browser.get("audit"), ("cases",), "browser 缺少浏览器 audit")
    cases = audit["cases"]
    _require(isinstance(cases, list) and cases, "browser 浏览器 audit 不完整")
    for case in cases:
        item = _require_keys(case, ("passed", "failures", "screenshots"), "browser case 证据不完整")
        _require(isinstance(item["passed"], bool) and isinstance(item["failures"], list), "browser case 状态无效")
        screenshots = _require_keys(item["screenshots"], ("full", "top", "bottom"), "browser case 缺少截图证据")
        for screenshot in screenshots.values():
            _nonempty_string(screenshot, "browser 截图证据无效")
    if summary["status"] == "passed":
        _require(all(case["passed"] and not case["failures"] for case in cases), "browser 通过结果包含失败 case")
        _require(exit_code == 0 and pollution.get("detected") is False and not summary.get("error"), "browser 通过结果包含失败证据")
        result.update(classification="continue", reason="浏览器门禁通过")
        return result
    return _failed(result, "browser_failure", str(summary.get("error") or "浏览器门禁失败"), needs_human=pollution.get("detected") is True or exit_code is None)


def _diagnose_accessibility(result: dict, summary: dict) -> dict:
    _require(summary.get("schema_version") == 1 and summary.get("status") in {"passed", "failed"}, "accessibility summary 无效")
    _require_run_metadata(summary, "accessibility")
    _require(summary.get("command") == "check", "accessibility command 无效")
    _require(isinstance(summary.get("routes"), list) and summary["routes"], "accessibility 缺少路由证据")
    _require(isinstance(summary.get("cases"), list) and summary["cases"], "accessibility 缺少 case 证据")
    audit = summary.get("audit")
    pollution = _complete_pollution(summary.get("pollution"), "accessibility")
    comparison = summary.get("comparison")
    _require(isinstance(audit, dict) and isinstance(comparison, dict), "accessibility 缺少审计或比较证据")
    exit_code = audit.get("exit_code")
    _require(isinstance(exit_code, int) or exit_code is None, "accessibility exit_code 无效")
    audit_summary = _require_keys(audit.get("summary"), ("checks", "violations", "infrastructureFailures"), "accessibility 缺少 audit 汇总")
    _require(all(isinstance(value, int) and value >= 0 for value in audit_summary.values()), "accessibility audit 汇总无效")
    baseline = _require_keys(summary.get("baseline"), ("path", "violation_count"), "accessibility 缺少基线证据")
    _nonempty_string(baseline["path"], "accessibility baseline path 无效")
    new = comparison.get("new")
    known, resolved = comparison.get("known"), comparison.get("resolved")
    _require(isinstance(new, list) and isinstance(known, list) and isinstance(resolved, list), "accessibility comparison 明细无效")
    _require(
        comparison.get("new_count") == len(new)
        and comparison.get("known_count") == len(known)
        and comparison.get("resolved_count") == len(resolved),
        "accessibility comparison 计数不一致",
    )
    fingerprints = _fingerprints(new)
    if summary["status"] == "passed":
        _require(audit_summary["checks"] > 0 and audit_summary["infrastructureFailures"] == 0, "accessibility 通过结果的 audit 不完整")
        _require(audit_summary["violations"] == len(known) + len(new), "accessibility audit 与比较明细不一致")
        _require(baseline["violation_count"] == len(known) + len(resolved), "accessibility 基线与比较明细不一致")
        _require(exit_code == 0 and not fingerprints and pollution.get("detected") is False and not summary.get("error"), "accessibility 通过结果包含失败证据")
        result.update(classification="continue", reason="可访问性门禁通过")
        return result
    return _failed(result, "accessibility_failure", str(summary.get("error") or "可访问性门禁失败"), fingerprints, needs_human=not fingerprints)


def _diagnose_performance(result: dict, summary: dict) -> dict:
    _require(summary.get("schema_version") == 1 and summary.get("command") == "check" and summary.get("status") in {"passed", "failed"}, "performance summary 无效")
    _require_run_metadata(summary, "performance")
    _nonempty_string(summary.get("generated_at"), "performance 缺少 generated_at")
    audit = summary.get("audit")
    pollution = _complete_pollution(summary.get("pollution"), "performance")
    _require(isinstance(audit, dict), "performance 缺少审计证据")
    _require(audit.get("exit_codes") == {"pages": 0, "apis": 0}, "performance 审计退出码无效")
    audit_summary = _require_keys(audit.get("summary"), ("pageRoutes", "pageSamples", "apiEndpoints", "apiSamples", "pageErrors", "apiErrors"), "performance 缺少 audit 汇总")
    _require(all(isinstance(value, int) and value >= 0 for value in audit_summary.values()), "performance audit 汇总无效")
    _require(audit_summary["pageRoutes"] > 0 and audit_summary["pageSamples"] > 0 and audit_summary["apiEndpoints"] > 0 and audit_summary["apiSamples"] > 0, "performance 样本证据不完整")
    baseline = _require_keys(summary.get("baseline"), ("path", "rule_version"), "performance 缺少基线证据")
    _nonempty_string(baseline["path"], "performance baseline path 无效")
    _require(isinstance(baseline["rule_version"], int), "performance baseline rule_version 无效")
    _require("recheck" in summary and (summary["recheck"] is None or isinstance(summary["recheck"], dict)), "performance 复测证据无效")
    _require(isinstance(summary.get("fixture"), dict), "performance 缺少夹具证据")
    fingerprints = _fingerprints(summary.get("violations"))
    if summary["status"] == "passed":
        _require(audit_summary["pageErrors"] == 0 and audit_summary["apiErrors"] == 0, "performance 通过结果包含审计错误")
        _require(not fingerprints and pollution.get("detected") is False and not summary.get("error"), "performance 通过结果包含失败证据")
        result.update(classification="continue", reason="性能门禁通过")
        return result
    if not fingerprints:
        return _failed(result, "performance_infrastructure_error", str(summary.get("error") or "性能门禁缺少可仲裁的预算违规证据"), needs_human=True)
    return _failed(result, "stable_performance_regression", str(summary.get("error") or "稳定性能预算回归"), fingerprints, needs_human=True)


def _diagnose_arbitration(result: dict, summary: dict, source_summary: Path, evidence_root: Path | None) -> dict:
    _require(summary.get("schema_version") == 1 and summary.get("status") in {"passed", "failed"}, "performance-arbitration summary 无效")
    expected, found = summary.get("expected_runs"), summary.get("found_runs")
    verdict = summary.get("verdict")
    runs = summary.get("runs")
    _require(expected == 3 and found == 3 and isinstance(runs, list) and len(runs) == found, "performance-arbitration Runner 证据无效")
    validated_runs = [_complete_arbitration_run(run, source_summary, evidence_root) for run in runs]
    _require(len({run["run_id"] for run in validated_runs}) == found, "performance-arbitration Runner run_id 不唯一")
    if summary["status"] == "passed":
        failures = summary.get("budget_regression_runs")
        _require(isinstance(failures, int) and failures >= 0, "performance-arbitration 失败计数无效")
        _require(found == 3 and verdict in {"passed", "passed_with_environment_noise"}, "performance-arbitration 通过结果无效")
        _require((verdict == "passed") == (failures == 0), "performance-arbitration 通过计数不一致")
        _require((verdict == "passed_with_environment_noise") == (failures == 1), "performance-arbitration 噪声计数不一致")
        observed_failures = sum(run["classification"] == "budget_regression" for run in validated_runs)
        _require(observed_failures == failures and all(run["classification"] != "infrastructure_error" for run in validated_runs), "performance-arbitration Runner 结论不一致")
        result.update(classification="continue" if failures == 0 else "environment_noise", reason="性能仲裁通过")
        return result
    _require(verdict in {"infrastructure_error", "inconclusive_budget_regression"}, "performance-arbitration 失败结论无效")
    if verdict == "inconclusive_budget_regression":
        failures = summary.get("budget_regression_runs")
        _require(isinstance(failures, int) and failures >= 0, "performance-arbitration 失败计数无效")
        _require(found == 3 and failures >= 2, "performance-arbitration 回归计数不一致")
        _require(sum(run["classification"] == "budget_regression" for run in validated_runs) == failures, "performance-arbitration Runner 回归计数不一致")
    else:
        _require(any(run["classification"] == "infrastructure_error" for run in validated_runs), "performance-arbitration 基础设施结论缺少 Runner 证据")
    return _failed(result, verdict, str(summary.get("error") or "性能仲裁阻断"), needs_human=True)


DIAGNOSERS = {
    "quality": _diagnose_quality,
    "browser": _diagnose_browser,
    "accessibility": _diagnose_accessibility,
    "performance": _diagnose_performance,
    "performance-arbitration": _diagnose_arbitration,
}


def diagnose(gate: str, summary_path: Path, *, evidence_root: Path | None = None) -> dict[str, Any]:
    _require(gate in DIAGNOSERS, f"未知门禁：{gate}")
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取 summary：{exc}") from exc
    _require(isinstance(summary, dict), "summary 必须是 JSON 对象")
    result = _base(gate, summary_path, summary)
    if gate == "performance-arbitration":
        result = _diagnose_arbitration(result, summary, summary_path, evidence_root)
    else:
        result = DIAGNOSERS[gate](result, summary)
    for command in result["suggested_commands"]:
        _require(not any(token in command.lower() for token in UNSAFE_TOKENS), "诊断命令违反只读策略")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", choices=GATES, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, help="仲裁 Runner 摘要所在的受控根目录")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        diagnosis = diagnose(args.gate, args.summary, evidence_root=args.evidence_root)
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
