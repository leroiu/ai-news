"""长程 Agent 统一完成检查：本地/部署后门禁、Reviewer 与 accepted 证据链。"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import sys
import time
from typing import Any, Callable, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.quality_gate import CommandResult, execute  # noqa: E402


DEFAULT_OUTPUT = ROOT / "output" / "acceptance-gate"
SCHEMA_VERSION = 1
PASS_REVIEW_VALUES = {"PASS"}
BLOCKING_FINDING_STATES = {"open", "unresolved", "blocked", "blocking", "failed"}


@dataclass(frozen=True)
class GateSpec:
    name: str
    command: tuple[str, ...]
    timeout: float


GATE_SPECS = (
    GateSpec(
        "quality",
        (
            sys.executable,
            "tools/quality_gate.py",
            "checkpoint",
            "--output-dir",
            "{output}",
        ),
        960,
    ),
    GateSpec(
        "browser",
        (
            sys.executable,
            "tools/browser_gate.py",
            "--profile",
            "core",
            "--output-dir",
            "{output}",
        ),
        300,
    ),
    GateSpec(
        "accessibility",
        (
            sys.executable,
            "tools/accessibility_gate.py",
            "check",
            "--output-dir",
            "{output}",
        ),
        300,
    ),
    GateSpec(
        "performance",
        (
            sys.executable,
            "tools/performance_gate.py",
            "check",
            "--output-dir",
            "{output}",
        ),
        600,
    ),
)


Executor = Callable[[Sequence[str], Path, float], CommandResult]
WorkspaceProvider = Callable[[set[str]], dict]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON 顶层必须是对象：{path}")
    return payload


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def build_evidence_manifest(root: Path) -> list[dict]:
    resolved_root = root.resolve(strict=True)
    manifest = []
    for path in sorted(
        (item for item in resolved_root.rglob("*") if item.is_file()),
        key=lambda item: item.relative_to(resolved_root).as_posix(),
    ):
        manifest.append(
            {
                "path": path.relative_to(resolved_root).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    if not manifest:
        raise RuntimeError(f"子门禁没有生成任何证据文件：{resolved_root}")
    return manifest


def capture_workspace_binding(excluded_paths: set[str] | None = None) -> dict:
    excluded = {Path(item).as_posix() for item in (excluded_paths or set())}
    head = execute(["git", "rev-parse", "HEAD"], ROOT, 15)
    diff = execute(
        ["git", "diff", "--binary", "--no-ext-diff", "HEAD"], ROOT, 30
    )
    untracked = execute(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"], ROOT, 15
    )
    if any(result.returncode != 0 for result in (head, diff, untracked)):
        raise RuntimeError("无法生成 acceptance 工作区绑定")
    manifest = []
    for relative in sorted(item for item in untracked.stdout.split("\0") if item):
        normalized = Path(relative).as_posix()
        if normalized in excluded:
            continue
        path = ROOT / relative
        try:
            manifest.append(
                {
                    "path": normalized,
                    "size": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
        except OSError as error:
            raise RuntimeError(f"无法读取未跟踪文件 {relative}：{error}") from error
    return {
        "git_head": head.stdout.strip(),
        "tracked_diff_sha256": hashlib.sha256(
            diff.stdout.encode("utf-8", "surrogatepass")
        ).hexdigest(),
        "untracked_files": manifest,
    }


def parse_time(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"{label} 缺少 ISO 时间")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise RuntimeError(f"{label} ISO 时间无效：{error}") from error
    if parsed.tzinfo is None:
        raise RuntimeError(f"{label} 必须包含时区")
    return parsed


def validate_task_contract(task: dict) -> list[str]:
    errors = []
    for field in ("task_id", "project_id", "goal"):
        if not isinstance(task.get(field), str) or not task[field].strip():
            errors.append(f"缺少非空 {field}")
    issue_status = task.get("issue_status")
    if issue_status != "ready":
        errors.append(
            "issue_status 必须是 ready；draft、blocked、completed 均禁止执行"
        )
    if task.get("execution_gate") != "allowed":
        errors.append("execution_gate 必须是 allowed")
    target_environment = task.get("target_environment")
    if target_environment not in {"local", "dev"}:
        errors.append("target_environment 必须是 local 或 dev")
    if target_environment == "dev":
        postdeploy = task.get("postdeploy")
        required = (
            "base_url",
            "allowed_host",
            "expected_environment",
            "expected_release",
        )
        if not isinstance(postdeploy, dict):
            errors.append("dev Task Contract 必须包含 postdeploy 配置")
        else:
            for field in required:
                if not isinstance(postdeploy.get(field), str) or not postdeploy[field].strip():
                    errors.append(f"dev postdeploy 缺少非空 {field}")
            if postdeploy.get("expected_environment") != "dev":
                errors.append("dev postdeploy.expected_environment 必须是 dev")
    criteria = task.get("acceptance_criteria")
    if (
        not isinstance(criteria, list)
        or not criteria
        or any(not isinstance(item, str) or not item.strip() for item in criteria)
    ):
        errors.append("acceptance_criteria 必须是非空、可测试的字符串列表")
    max_rounds = task.get("max_iteration_rounds", 2)
    if not isinstance(max_rounds, int) or isinstance(max_rounds, bool) or max_rounds < 1:
        errors.append("max_iteration_rounds 必须是正整数")
    if task.get("status") in {"draft", "blocked", "completed"}:
        errors.append(f"任务 status={task.get('status')} 不允许开始 verify")
    return errors


def validate_quality(summary: dict) -> list[str]:
    errors = []
    if summary.get("profile") != "checkpoint":
        errors.append("quality profile 不是 checkpoint")
    if summary.get("result") != "pass" or summary.get("exit_code") != 0:
        errors.append("quality checkpoint 未通过")
    if summary.get("pytest_returncode") != 0:
        errors.append("quality pytest_returncode 非零")
    if not summary.get("coverage_enabled") or not isinstance(
        summary.get("coverage_summary"), dict
    ):
        errors.append("quality 缺少 coverage 证据")
    if summary.get("git_content_changed"):
        errors.append("quality 检测到 Git 内容污染")
    if summary.get("runtime_content_changed"):
        errors.append("quality 检测到受保护运行目录污染")
    return errors


def validate_browser(summary: dict) -> list[str]:
    errors = []
    if (
        summary.get("status") != "passed"
        or summary.get("profile") != "core"
        or summary.get("prepare_only") is not False
    ):
        errors.append("browser 不是通过的 core 完整门禁")
    if summary.get("network") != {
        "policy": "loopback-only",
        "allowed_external_origins": [],
    }:
        errors.append("browser 网络策略不是纯 loopback")
    if summary.get("pollution", {}).get("detected"):
        errors.append("browser 检测到受保护运行目录污染")
    browser = summary.get("browser")
    audit = browser.get("audit") if isinstance(browser, dict) else None
    cases = audit.get("cases") if isinstance(audit, dict) else None
    if not isinstance(browser, dict) or browser.get("exit_code") != 0:
        errors.append("browser Chromium 退出码非零")
    if not isinstance(cases, list) or len(cases) != 20:
        errors.append("browser 必须包含 20 个核心案例")
    else:
        browser_run_dir = Path(summary.get("run_dir", "")).resolve()
        for case in cases:
            if case.get("passed") is not True or case.get("failures") != []:
                errors.append("browser 包含未通过案例")
                break
            screenshots = case.get("screenshots")
            if (
                not isinstance(screenshots, dict)
                or set(screenshots) != {"full", "top", "bottom"}
                or any(
                    not isinstance(value, str) or not value
                    for value in screenshots.values()
                )
            ):
                errors.append("browser 案例截图矩阵不完整")
                break
            for value in screenshots.values():
                screenshot = Path(value)
                if (
                    not screenshot.is_file()
                    or not screenshot.resolve().is_relative_to(browser_run_dir)
                ):
                    errors.append("browser 截图不存在或不属于本次门禁目录")
                    break
            if errors:
                break
    return errors


def validate_accessibility(summary: dict) -> list[str]:
    errors = []
    if summary.get("status") != "passed" or summary.get("command") != "check":
        errors.append("accessibility check 未通过")
    if summary.get("pollution", {}).get("detected"):
        errors.append("accessibility 检测到受保护运行目录污染")
    audit = summary.get("audit")
    audit_summary = audit.get("summary") if isinstance(audit, dict) else None
    if not isinstance(audit, dict) or audit.get("exit_code") != 0:
        errors.append("accessibility Chromium 退出码非零")
    if not isinstance(audit_summary, dict) or (
        audit_summary.get("checks") != 30
        or audit_summary.get("infrastructureFailures") != 0
    ):
        errors.append("accessibility 必须包含 30 个无基础设施错误的案例")
    comparison = summary.get("comparison")
    if not isinstance(comparison, dict) or comparison.get("new_count") != 0:
        errors.append("accessibility 存在新增违规或比较证据缺失")
    if summary.get("cases") != ["desktop-dark", "desktop-light", "mobile-dark"]:
        errors.append("accessibility case 矩阵漂移")
    return errors


def validate_performance(summary: dict) -> list[str]:
    errors = []
    if summary.get("status") != "passed" or summary.get("command") != "check":
        errors.append("performance check 未通过")
    if summary.get("pollution", {}).get("detected"):
        errors.append("performance 检测到受保护运行目录污染")
    audit = summary.get("audit")
    exit_codes = audit.get("exit_codes") if isinstance(audit, dict) else None
    audit_summary = audit.get("summary") if isinstance(audit, dict) else None
    if exit_codes != {"pages": 0, "apis": 0}:
        errors.append("performance 页面/API 阶段退出码无效")
    expected = {
        "pageRoutes": 10,
        "pageSamples": 30,
        "apiEndpoints": 5,
        "apiSamples": 100,
        "pageErrors": 0,
        "apiErrors": 0,
    }
    if audit_summary != expected:
        errors.append("performance 样本矩阵或错误计数无效")
    if summary.get("violations") != []:
        errors.append("performance 存在预算违规")
    return errors


def validate_postdeploy(summary: dict) -> list[str]:
    errors = []
    if summary.get("status") != "passed" or summary.get("command") != "check":
        errors.append("postdeploy check 未通过")
    target = summary.get("target")
    if not isinstance(target, dict) or target.get("policy_errors") != []:
        errors.append("postdeploy 目标策略未通过")
    elif (
        target.get("environment") != "dev"
        or target.get("expected_environment") != "dev"
        or target.get("environment") != target.get("expected_environment")
    ):
        errors.append("postdeploy 环境绑定无效")
    policy = summary.get("policy")
    if not isinstance(policy, dict) or (
        policy.get("methods") != ["GET"]
        or policy.get("follow_redirects") is not False
        or policy.get("trust_environment_proxy") is not False
        or policy.get("tls_verify") is not True
    ):
        errors.append("postdeploy 只读或网络安全策略无效")
    if summary.get("matrix") != {
        "expected_cases": 11,
        "actual_cases": 11,
        "pages": 7,
        "apis": 4,
    }:
        errors.append("postdeploy 检查矩阵漂移")
    cases = summary.get("cases")
    if (
        not isinstance(cases, list)
        or len(cases) != 11
        or any(
            not isinstance(case, dict)
            or case.get("passed") is not True
            or case.get("validation_errors") != []
            or case.get("evidence", {}).get("method") != "GET"
            for case in cases
        )
    ):
        errors.append("postdeploy 包含失败、缺失或非 GET 案例")
    if summary.get("result") != {"passed": True, "failure_count": 0}:
        errors.append("postdeploy 结果摘要无效")
    return errors


VALIDATORS = {
    "quality": validate_quality,
    "browser": validate_browser,
    "accessibility": validate_accessibility,
    "performance": validate_performance,
    "postdeploy": validate_postdeploy,
}


def gate_specs_for_task(task: dict) -> tuple[GateSpec, ...]:
    if task.get("target_environment") != "dev":
        return GATE_SPECS
    postdeploy = task["postdeploy"]
    return (
        *GATE_SPECS,
        GateSpec(
            "postdeploy",
            (
                sys.executable,
                "tools/postdeploy_gate.py",
                "check",
                "--base-url",
                postdeploy["base_url"],
                "--environment",
                "dev",
                "--allowed-host",
                postdeploy["allowed_host"],
                "--expected-environment",
                postdeploy["expected_environment"],
                "--expected-release",
                postdeploy["expected_release"],
                "--output-dir",
                "{output}",
            ),
            180,
        ),
    )


def render_command(spec: GateSpec, output_root: Path) -> list[str]:
    return [
        str(output_root) if item == "{output}" else item for item in spec.command
    ]


def locate_summary(output_root: Path) -> Path:
    candidates = sorted(output_root.rglob("summary.json"))
    if len(candidates) != 1:
        raise RuntimeError(
            f"子门禁必须生成且只生成一个 summary.json，实际 {len(candidates)} 个"
        )
    resolved_root = output_root.resolve()
    resolved_summary = candidates[0].resolve()
    if not resolved_summary.is_relative_to(resolved_root):
        raise RuntimeError("子门禁 summary.json 越出本次证据目录")
    return resolved_summary


def run_gate(spec: GateSpec, run_dir: Path, executor: Executor) -> dict:
    step_dir = run_dir / "steps" / spec.name
    evidence_root = step_dir / "evidence"
    evidence_root.mkdir(parents=True, exist_ok=False)
    command = render_command(spec, evidence_root)
    started_at = utc_now()
    result = executor(command, ROOT, spec.timeout)
    finished_at = utc_now()
    (step_dir / "stdout.log").write_text(result.stdout, encoding="utf-8")
    (step_dir / "stderr.log").write_text(result.stderr, encoding="utf-8")
    atomic_write_json(
        step_dir / "command-result.json",
        {
            "command": command,
            "command_display": shlex.join(command),
            "started_at": started_at,
            "finished_at": finished_at,
            **asdict(result),
        },
    )

    summary_path = None
    summary_sha256 = None
    summary = None
    validation_errors = []
    evidence_manifest = []
    try:
        summary_path = locate_summary(evidence_root)
        summary_sha256 = sha256_file(summary_path)
        summary = load_json(summary_path)
        validation_errors.extend(VALIDATORS[spec.name](summary))
        evidence_manifest = build_evidence_manifest(evidence_root)
    except (OSError, RuntimeError, json.JSONDecodeError) as error:
        validation_errors.append(str(error))
    if result.returncode != 0:
        validation_errors.append(f"子门禁退出码非零：{result.returncode}")
    if result.timed_out:
        validation_errors.append("子门禁超时")
    if result.infra_error:
        validation_errors.append("子门禁基础设施错误")

    return {
        "name": spec.name,
        "status": "passed" if not validation_errors else "failed",
        "command": command,
        "timeout_seconds": spec.timeout,
        "returncode": result.returncode,
        "duration_seconds": round(result.duration_seconds, 3),
        "timed_out": result.timed_out,
        "infra_error": result.infra_error,
        "process_tree_cleaned": result.process_tree_cleaned,
        "summary_path": str(summary_path) if summary_path else None,
        "summary_sha256": summary_sha256,
        "evidence_root": str(evidence_root.resolve()),
        "evidence_manifest": evidence_manifest,
        "validation_errors": validation_errors,
        "stdout_path": str(step_dir / "stdout.log"),
        "stderr_path": str(step_dir / "stderr.log"),
        "command_result_path": str(step_dir / "command-result.json"),
    }


def run_verification(
    task_path: Path,
    output_root: Path = DEFAULT_OUTPUT,
    executor: Executor = execute,
    gate_specs: Sequence[GateSpec] | None = None,
    iteration_round: int = 1,
    workspace_provider: WorkspaceProvider = capture_workspace_binding,
) -> tuple[int, Path, dict]:
    run_id = make_run_id()
    run_dir = output_root.resolve() / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    started_at = utc_now()
    states = [{"state": "intake", "at": started_at}]
    workspace_before = None
    workspace_error = ""
    try:
        workspace_before = workspace_provider(set())
    except RuntimeError as error:
        workspace_error = str(error)
    task = None
    task_errors = []
    try:
        resolved_task = task_path.resolve(strict=True)
        task = load_json(resolved_task)
        task_errors = validate_task_contract(task)
        max_rounds = task.get("max_iteration_rounds", 2)
        if (
            not isinstance(iteration_round, int)
            or isinstance(iteration_round, bool)
            or iteration_round < 1
            or iteration_round > max_rounds
        ):
            task_errors.append(
                f"iteration_round 必须在 1..{max_rounds} 范围内"
            )
        if workspace_error:
            task_errors.append(workspace_error)
    except (OSError, RuntimeError, json.JSONDecodeError) as error:
        resolved_task = task_path.resolve()
        task_errors = [str(error)]

    if task_errors:
        states.append(
            {
                "state": "escalated",
                "at": utc_now(),
                "reason": "issue gate blocked",
            }
        )
        summary = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "status": "escalated",
            "started_at": started_at,
            "finished_at": utc_now(),
            "target_environment": (task or {}).get("target_environment"),
            "iteration_round": iteration_round,
            "task": {
                "path": str(resolved_task),
                "sha256": (
                    sha256_file(resolved_task) if resolved_task.is_file() else None
                ),
                "task_id": (task or {}).get("task_id"),
                "acceptance_criteria": (task or {}).get("acceptance_criteria"),
                "validation_errors": task_errors,
            },
            "states": states,
            "gates": [],
            "open_risks": ["Task Contract 未通过执行门"],
            "need_human_input": "修复 Task Contract 的状态、执行门或验收标准。",
            "run_dir": str(run_dir),
        }
        atomic_write_json(run_dir / "summary.json", summary)
        return 1, run_dir, summary

    states.append({"state": "issue-gated", "at": utc_now()})
    states.append({"state": "executing", "at": utc_now()})
    effective_gate_specs = (
        tuple(gate_specs) if gate_specs is not None else gate_specs_for_task(task)
    )
    gates = [run_gate(spec, run_dir, executor) for spec in effective_gate_specs]
    try:
        workspace_after = workspace_provider(set())
    except RuntimeError as error:
        workspace_after = None
        workspace_error = str(error)
    workspace_changed = (
        workspace_before is None
        or workspace_after is None
        or workspace_before != workspace_after
    )
    all_passed = (
        all(gate["status"] == "passed" for gate in gates)
        and not workspace_changed
    )
    status = "awaiting_review" if all_passed else "escalated"
    states.append(
        {
            "state": status,
            "at": utc_now(),
            **(
                {}
                if all_passed
                else {"reason": "一个或多个本地完成门禁失败"}
            ),
        }
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "status": status,
        "started_at": started_at,
        "finished_at": utc_now(),
        "target_environment": task["target_environment"],
        "max_iteration_rounds": task.get("max_iteration_rounds", 2),
        "iteration_round": iteration_round,
        "task": {
            "path": str(resolved_task),
            "sha256": sha256_file(resolved_task),
            "task_id": task["task_id"],
            "project_id": task["project_id"],
            "goal": task["goal"],
            "acceptance_criteria": task["acceptance_criteria"],
            "validation_errors": [],
        },
        "states": states,
        "gates": gates,
        "workspace_binding": {
            "before": workspace_before,
            "after": workspace_after,
            "changed": workspace_changed,
            "error": workspace_error,
            "policy": (
                "finalize 必须保持 git HEAD、tracked diff 与未跟踪文件内容不变；"
                "仅允许新增本次精确 Reviewer 报告路径。"
            ),
        },
        "acceptance": {
            "local_gates_passed": all_passed,
            "review_required": True,
            "accepted": False,
        },
        "open_risks": (
            ["等待独立 Reviewer 绑定本次证据并逐项确认验收标准。"]
            if all_passed
            else [
                f"{gate['name']}: {'; '.join(gate['validation_errors'])}"
                for gate in gates
                if gate["status"] != "passed"
            ]
            + (
                [workspace_error or "verify 期间工作区内容发生变化"]
                if workspace_changed
                else []
            )
        ),
        "need_human_input": (
            "需要独立 Reviewer 报告；报告不能由 Builder 自行代签。"
            if all_passed
            else "修复失败门禁后重新运行 verify；最多迭代两轮。"
        ),
        "run_dir": str(run_dir),
    }
    atomic_write_json(run_dir / "summary.json", summary)
    return (0 if all_passed else 1), run_dir, summary


def validate_reviewer(
    review: dict, summary: dict, summary_sha256: str
) -> list[str]:
    errors = []
    if review.get("task_id") != summary.get("task", {}).get("task_id"):
        errors.append("Reviewer task_id 未绑定当前 Task Contract")
    if review.get("acceptance_run_id") != summary.get("run_id"):
        errors.append("Reviewer acceptance_run_id 未绑定当前 verify")
    if review.get("acceptance_summary_sha256") != summary_sha256:
        errors.append("Reviewer 未绑定当前 acceptance summary SHA-256")
    if str(review.get("verdict", "")).upper() not in PASS_REVIEW_VALUES:
        errors.append("Reviewer verdict 不是 PASS")
    if review.get("reviewer_role") != "independent Reviewer":
        errors.append("Reviewer 角色不是 independent Reviewer")
    try:
        reviewed_at = parse_time(review.get("reviewed_at"), "Reviewer reviewed_at")
        finished_at = parse_time(summary.get("finished_at"), "verify finished_at")
        if reviewed_at < finished_at:
            errors.append("Reviewer 时间早于 verify 完成时间")
    except RuntimeError as error:
        errors.append(str(error))
    criteria = summary.get("task", {}).get("acceptance_criteria", [])
    reviewed_criteria = review.get("acceptance_criteria")
    if not isinstance(reviewed_criteria, list) or len(reviewed_criteria) != len(
        criteria
    ):
        errors.append("Reviewer 未逐项覆盖全部 acceptance criteria")
    else:
        for expected, item in zip(criteria, reviewed_criteria, strict=True):
            if (
                not isinstance(item, dict)
                or item.get("criterion") != expected
                or str(item.get("result", "")).upper() != "PASS"
                or not item.get("evidence")
            ):
                errors.append(f"Reviewer 验收项未通过或缺少证据：{expected}")
    findings = review.get("findings", [])
    if not isinstance(findings, list):
        errors.append("Reviewer findings 必须是列表")
    else:
        for finding in findings:
            if not isinstance(finding, dict):
                errors.append("Reviewer finding 结构无效")
                continue
            state = str(finding.get("status", "")).lower()
            if state in BLOCKING_FINDING_STATES:
                errors.append(
                    f"Reviewer 存在未关闭 finding：{finding.get('id', '<unknown>')}"
                )
    blocking_issues = review.get("blocking_issues", [])
    if blocking_issues not in (None, []):
        errors.append("Reviewer 报告仍包含 blocking_issues")
    return errors


def finalize_acceptance(
    run_dir: Path,
    review_path: Path,
    workspace_provider: WorkspaceProvider = capture_workspace_binding,
) -> tuple[int, dict]:
    resolved_run = run_dir.resolve(strict=True)
    summary_path = resolved_run / "summary.json"
    accepted_path = resolved_run / "accepted.json"
    if accepted_path.exists():
        raise RuntimeError(f"accepted 证据已存在，禁止覆盖：{accepted_path}")
    summary = load_json(summary_path)
    if summary.get("status") != "awaiting_review":
        raise RuntimeError("只有 awaiting_review 的 verify 才能 finalize")
    if summary.get("run_dir") != str(resolved_run):
        raise RuntimeError("acceptance summary 的 run_dir 不匹配")

    summary_sha256 = sha256_file(summary_path)
    task_info = summary.get("task")
    if not isinstance(task_info, dict):
        raise RuntimeError("acceptance summary 缺少 task 绑定")
    task_path = Path(task_info.get("path", ""))
    if not task_path.is_file() or sha256_file(task_path) != task_info.get("sha256"):
        raise RuntimeError("Task Contract 已缺失或发生变化")
    task = load_json(task_path)
    task_errors = validate_task_contract(task)
    if task_errors:
        raise RuntimeError(f"Task Contract 不再满足执行门：{'; '.join(task_errors)}")
    if task.get("acceptance_criteria") != task_info.get("acceptance_criteria"):
        raise RuntimeError("Task Contract acceptance criteria 已变化")

    expected_gate_specs = gate_specs_for_task(task)
    gates = summary.get("gates")
    if not isinstance(gates, list) or [gate.get("name") for gate in gates] != [
        spec.name for spec in expected_gate_specs
    ]:
        raise RuntimeError("acceptance gate 矩阵缺失或顺序漂移")
    for gate, spec in zip(gates, expected_gate_specs, strict=True):
        if gate.get("status") != "passed":
            raise RuntimeError(f"子门禁未通过：{gate.get('name')}")
        evidence_root = Path(gate.get("evidence_root", ""))
        if gate.get("command") != render_command(spec, evidence_root):
            raise RuntimeError(f"子门禁命令与 Task Contract 不匹配：{gate.get('name')}")
        try:
            current_manifest = build_evidence_manifest(evidence_root)
        except (OSError, RuntimeError) as error:
            raise RuntimeError(
                f"子门禁完整证据无法读取：{gate.get('name')}: {error}"
            ) from error
        if current_manifest != gate.get("evidence_manifest"):
            raise RuntimeError(
                f"子门禁完整证据目录已发生新增、删除或内容变化：{gate.get('name')}"
            )
        evidence_path = Path(gate.get("summary_path", ""))
        if (
            not evidence_path.is_file()
            or sha256_file(evidence_path) != gate.get("summary_sha256")
        ):
            raise RuntimeError(f"子门禁证据已缺失或篡改：{gate.get('name')}")
        evidence = load_json(evidence_path)
        validation_errors = VALIDATORS[gate["name"]](evidence)
        if validation_errors:
            raise RuntimeError(
                f"子门禁证据不再有效：{gate['name']}: "
                + "; ".join(validation_errors)
            )

    resolved_review = review_path.resolve(strict=True)
    excluded_paths = set()
    if resolved_review.is_relative_to(ROOT.resolve()):
        excluded_paths.add(resolved_review.relative_to(ROOT.resolve()).as_posix())
    expected_workspace = summary.get("workspace_binding", {}).get("after")
    if not isinstance(expected_workspace, dict):
        raise RuntimeError("acceptance summary 缺少工作区绑定")
    current_workspace = workspace_provider(excluded_paths)
    if current_workspace != expected_workspace:
        raise RuntimeError(
            "verify 后工作区实现内容发生变化；必须重新运行完整 verify"
        )
    review = load_json(resolved_review)
    review_errors = validate_reviewer(review, summary, summary_sha256)
    if review_errors:
        raise RuntimeError("Reviewer 报告无效：" + "; ".join(review_errors))

    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "accepted",
        "accepted_at": utc_now(),
        "task_id": task["task_id"],
        "acceptance_run_id": summary["run_id"],
        "target_environment": summary["target_environment"],
        "acceptance_summary": {
            "path": str(summary_path),
            "sha256": summary_sha256,
        },
        "task_contract": {
            "path": str(task_path),
            "sha256": task_info["sha256"],
        },
        "gates": [
            {
                "name": gate["name"],
                "summary_path": gate["summary_path"],
                "summary_sha256": gate["summary_sha256"],
            }
            for gate in gates
        ],
        "review": {
            "path": str(resolved_review),
            "sha256": sha256_file(resolved_review),
            "reviewed_at": review["reviewed_at"],
            "verdict": review["verdict"],
        },
        "workspace_binding": expected_workspace,
        "acceptance_criteria": review["acceptance_criteria"],
        "open_risks": review.get("residual_risks", []),
        "need_human_input": None,
        "policy": (
            "accepted 仅证明绑定证据所覆盖的本地 DoD；不授权部署、提交、"
            "推送、合并或修改 Task Contract 状态。"
        ),
    }
    atomic_write_json(accepted_path, payload)
    return 0, payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--task", type=Path, required=True)
    verify.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    verify.add_argument("--round", type=int, default=1)
    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--run-dir", type=Path, required=True)
    finalize.add_argument("--review", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "verify":
        code, run_dir, summary = run_verification(
            args.task, args.output_dir, iteration_round=args.round
        )
        summary_path = run_dir / "summary.json"
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "run_id": summary["run_id"],
                    "run_dir": str(run_dir),
                    "summary_sha256": sha256_file(summary_path),
                    "gates": {
                        gate["name"]: gate["status"]
                        for gate in summary.get("gates", [])
                    },
                    "need_human_input": summary["need_human_input"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return code
    try:
        code, payload = finalize_acceptance(args.run_dir, args.review)
    except (OSError, RuntimeError, json.JSONDecodeError) as error:
        print(
            json.dumps(
                {"status": "escalated", "error": str(error)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    print(
        json.dumps(
            {
                "status": payload["status"],
                "task_id": payload["task_id"],
                "acceptance_run_id": payload["acceptance_run_id"],
                "evidence": str(args.run_dir.resolve() / "accepted.json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
