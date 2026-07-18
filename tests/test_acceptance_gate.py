from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from tools.acceptance_gate import (
    GATE_SPECS,
    finalize_acceptance,
    gate_specs_for_task,
    run_verification,
    sha256_file,
    utc_now,
    validate_task_contract,
)
from tools.quality_gate import CommandResult


CRITERIA = ["标准一可测试", "标准二可测试"]
WORKSPACE = {
    "git_head": "a" * 40,
    "tracked_diff_sha256": "b" * 64,
    "untracked_files": [],
}


def fake_workspace(_excluded: set[str]) -> dict:
    return deepcopy(WORKSPACE)


def task_contract(**overrides) -> dict:
    payload = {
        "task_id": "TASK-001",
        "project_id": "ai-news",
        "goal": "验证统一完成检查",
        "target_environment": "local",
        "max_iteration_rounds": 2,
        "issue_status": "ready",
        "execution_gate": "allowed",
        "acceptance_criteria": CRITERIA,
        "status": "in_progress",
    }
    payload.update(overrides)
    return payload


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def quality_summary() -> dict:
    return {
        "profile": "checkpoint",
        "result": "pass",
        "exit_code": 0,
        "pytest_returncode": 0,
        "coverage_enabled": True,
        "coverage_summary": {"percent_covered": 56.55},
        "git_content_changed": False,
        "runtime_content_changed": False,
    }


def browser_summary() -> dict:
    cases = [
        {
            "passed": True,
            "failures": [],
            "screenshots": {
                "full": f"full-{index}.png",
                "top": f"top-{index}.png",
                "bottom": f"bottom-{index}.png",
            },
        }
        for index in range(20)
    ]
    return {
        "status": "passed",
        "profile": "core",
        "prepare_only": False,
        "network": {
            "policy": "loopback-only",
            "allowed_external_origins": [],
        },
        "pollution": {"detected": False},
        "browser": {"exit_code": 0, "audit": {"cases": cases}},
    }


def accessibility_summary() -> dict:
    return {
        "status": "passed",
        "command": "check",
        "cases": ["desktop-dark", "desktop-light", "mobile-dark"],
        "pollution": {"detected": False},
        "audit": {
            "exit_code": 0,
            "summary": {
                "checks": 30,
                "violations": 39,
                "infrastructureFailures": 0,
            },
        },
        "comparison": {"known_count": 39, "new_count": 0, "resolved_count": 0},
    }


def performance_summary() -> dict:
    return {
        "status": "passed",
        "command": "check",
        "pollution": {"detected": False},
        "audit": {
            "exit_codes": {"pages": 0, "apis": 0},
            "summary": {
                "pageRoutes": 10,
                "pageSamples": 30,
                "apiEndpoints": 5,
                "apiSamples": 100,
                "pageErrors": 0,
                "apiErrors": 0,
            },
        },
        "violations": [],
    }


def postdeploy_summary() -> dict:
    cases = [
        {
            "passed": True,
            "validation_errors": [],
            "evidence": {"method": "GET"},
        }
        for _ in range(11)
    ]
    return {
        "status": "passed",
        "command": "check",
        "target": {
            "environment": "dev",
            "expected_environment": "dev",
            "policy_errors": [],
        },
        "policy": {
            "methods": ["GET"],
            "follow_redirects": False,
            "trust_environment_proxy": False,
            "tls_verify": True,
        },
        "matrix": {
            "expected_cases": 11,
            "actual_cases": 11,
            "pages": 7,
            "apis": 4,
        },
        "cases": cases,
        "result": {"passed": True, "failure_count": 0},
    }


SUMMARIES = {
    "quality_gate.py": quality_summary,
    "browser_gate.py": browser_summary,
    "accessibility_gate.py": accessibility_summary,
    "performance_gate.py": performance_summary,
    "postdeploy_gate.py": postdeploy_summary,
}


class FakeExecutor:
    def __init__(self, mutate=None):
        self.commands: list[list[str]] = []
        self.mutate = mutate

    def __call__(self, command, cwd, timeout):
        command = list(command)
        self.commands.append(command)
        script = Path(command[1]).name
        payload = SUMMARIES[script]()
        output_root = Path(command[command.index("--output-dir") + 1])
        fake_run = output_root / "fake-run"
        if script == "browser_gate.py":
            payload["run_dir"] = str(fake_run.resolve())
            for index, case in enumerate(payload["browser"]["audit"]["cases"]):
                screenshots = {}
                for name in ("full", "top", "bottom"):
                    screenshot = fake_run / "screenshots" / f"{index}-{name}.png"
                    screenshot.parent.mkdir(parents=True, exist_ok=True)
                    screenshot.write_bytes(b"fake image")
                    screenshots[name] = str(screenshot.resolve())
                case["screenshots"] = screenshots
        if self.mutate:
            payload = self.mutate(script, payload)
        write_json(output_root / "fake-run" / "raw-evidence.json", {"ok": True})
        write_json(output_root / "fake-run" / "summary.json", payload)
        return CommandResult(0, "fake stdout", "", 0.01)


def create_verified_run(tmp_path: Path):
    task_path = tmp_path / "task.json"
    write_json(task_path, task_contract())
    executor = FakeExecutor()
    code, run_dir, summary = run_verification(
        task_path,
        tmp_path / "acceptance",
        executor=executor,
        workspace_provider=fake_workspace,
    )
    assert code == 0
    return task_path, run_dir, summary


def reviewer_report(run_dir: Path, summary: dict, **overrides) -> dict:
    payload = {
        "task_id": summary["task"]["task_id"],
        "acceptance_run_id": summary["run_id"],
        "acceptance_summary_sha256": sha256_file(run_dir / "summary.json"),
        "reviewed_at": utc_now(),
        "reviewer_role": "independent Reviewer",
        "verdict": "PASS",
        "acceptance_criteria": [
            {"criterion": criterion, "result": "PASS", "evidence": "独立证据"}
            for criterion in CRITERIA
        ],
        "findings": [],
        "blocking_issues": [],
        "residual_risks": ["仅覆盖本地环境"],
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("issue_status", ["draft", "blocked", "completed"])
def test_issue_gate_rejects_non_ready_status(issue_status: str):
    errors = validate_task_contract(task_contract(issue_status=issue_status))
    assert any("issue_status 必须是 ready" in error for error in errors)


def test_issue_gate_rejects_missing_execution_gate_and_criteria():
    errors = validate_task_contract(
        task_contract(execution_gate="blocked", acceptance_criteria=[])
    )
    assert "execution_gate 必须是 allowed" in errors
    assert any("acceptance_criteria" in error for error in errors)


def test_dev_issue_gate_requires_complete_postdeploy_contract():
    errors = validate_task_contract(task_contract(target_environment="dev"))
    assert "dev Task Contract 必须包含 postdeploy 配置" in errors

    errors = validate_task_contract(
        task_contract(
            target_environment="dev",
            postdeploy={
                "base_url": "https://dev.example.test",
                "allowed_host": "dev.example.test",
                "expected_environment": "stage",
                "expected_release": "a" * 40,
            },
        )
    )
    assert "dev postdeploy.expected_environment 必须是 dev" in errors


def test_dev_gate_matrix_appends_bound_postdeploy_command():
    task = task_contract(
        target_environment="dev",
        postdeploy={
            "base_url": "https://dev.example.test",
            "allowed_host": "dev.example.test",
            "expected_environment": "dev",
            "expected_release": "a" * 40,
        },
    )
    specs = gate_specs_for_task(task)

    assert [spec.name for spec in specs] == [
        "quality",
        "browser",
        "accessibility",
        "performance",
        "postdeploy",
    ]
    assert "https://dev.example.test" in specs[-1].command
    assert "dev.example.test" in specs[-1].command
    assert "a" * 40 in specs[-1].command


def test_blocked_issue_or_exhausted_round_never_starts_gates(tmp_path: Path):
    task_path = tmp_path / "task.json"
    write_json(task_path, task_contract(issue_status="draft"))
    executor = FakeExecutor()

    code, _, summary = run_verification(
        task_path,
        tmp_path / "draft",
        executor=executor,
        workspace_provider=fake_workspace,
    )

    assert code == 1
    assert summary["status"] == "escalated"
    assert executor.commands == []

    write_json(task_path, task_contract(max_iteration_rounds=2))
    code, _, summary = run_verification(
        task_path,
        tmp_path / "rounds",
        executor=executor,
        iteration_round=3,
        workspace_provider=fake_workspace,
    )
    assert code == 1
    assert "iteration_round" in summary["task"]["validation_errors"][0]
    assert executor.commands == []


def test_verify_runs_fixed_matrix_and_waits_for_review(tmp_path: Path):
    task_path = tmp_path / "task.json"
    write_json(task_path, task_contract())
    executor = FakeExecutor()

    code, run_dir, summary = run_verification(
        task_path,
        tmp_path / "acceptance",
        executor=executor,
        workspace_provider=fake_workspace,
    )

    assert code == 0
    assert summary["status"] == "awaiting_review"
    assert summary["acceptance"] == {
        "local_gates_passed": True,
        "review_required": True,
        "accepted": False,
    }
    assert [gate["name"] for gate in summary["gates"]] == [
        spec.name for spec in GATE_SPECS
    ]
    assert len(executor.commands) == 4
    assert all(gate["summary_sha256"] for gate in summary["gates"])
    assert all(gate["evidence_manifest"] for gate in summary["gates"])
    assert (run_dir / "summary.json").is_file()


def test_dev_verify_runs_postdeploy_after_all_local_gates(tmp_path: Path):
    task_path = tmp_path / "task.json"
    write_json(
        task_path,
        task_contract(
            target_environment="dev",
            postdeploy={
                "base_url": "https://dev.example.test",
                "allowed_host": "dev.example.test",
                "expected_environment": "dev",
                "expected_release": "a" * 40,
            },
        ),
    )
    executor = FakeExecutor()

    code, _, summary = run_verification(
        task_path,
        tmp_path / "acceptance",
        executor=executor,
        workspace_provider=fake_workspace,
    )

    assert code == 0
    assert [gate["name"] for gate in summary["gates"]] == [
        "quality",
        "browser",
        "accessibility",
        "performance",
        "postdeploy",
    ]
    assert len(executor.commands) == 5
    assert Path(executor.commands[-1][1]).name == "postdeploy_gate.py"
    assert executor.commands[-1][executor.commands[-1].index("--base-url") + 1] == (
        "https://dev.example.test"
    )


def test_verify_exit_zero_cannot_hide_semantic_failure(tmp_path: Path):
    task_path = tmp_path / "task.json"
    write_json(task_path, task_contract())

    def mutate(script: str, payload: dict) -> dict:
        if script == "performance_gate.py":
            payload["audit"]["summary"]["apiSamples"] = 99
        return payload

    executor = FakeExecutor(mutate=mutate)
    code, _, summary = run_verification(
        task_path,
        tmp_path / "acceptance",
        executor=executor,
        workspace_provider=fake_workspace,
    )

    assert code == 1
    assert summary["status"] == "escalated"
    assert len(executor.commands) == 4
    performance = next(
        gate for gate in summary["gates"] if gate["name"] == "performance"
    )
    assert performance["status"] == "failed"
    assert "样本矩阵" in performance["validation_errors"][0]

    def break_screenshot(script: str, payload: dict) -> dict:
        if script == "browser_gate.py":
            payload["browser"]["audit"]["cases"][0]["screenshots"]["full"] = (
                str(tmp_path / "missing.png")
            )
        return payload

    code, _, summary = run_verification(
        task_path,
        tmp_path / "missing-screenshot",
        executor=FakeExecutor(mutate=break_screenshot),
        workspace_provider=fake_workspace,
    )
    assert code == 1
    browser = next(gate for gate in summary["gates"] if gate["name"] == "browser")
    assert "截图不存在" in browser["validation_errors"][0]


def test_workspace_change_blocks_verify_and_finalize(tmp_path: Path):
    task_path = tmp_path / "task.json"
    write_json(task_path, task_contract())
    calls = 0

    def changing_workspace(_excluded: set[str]) -> dict:
        nonlocal calls
        calls += 1
        payload = deepcopy(WORKSPACE)
        if calls > 1:
            payload["tracked_diff_sha256"] = "c" * 64
        return payload

    code, _, summary = run_verification(
        task_path,
        tmp_path / "changed",
        executor=FakeExecutor(),
        workspace_provider=changing_workspace,
    )
    assert code == 1
    assert summary["status"] == "escalated"
    assert summary["workspace_binding"]["changed"] is True

    _, run_dir, summary = create_verified_run(tmp_path / "finalize")
    review_path = tmp_path / "finalize-review.json"
    write_json(review_path, reviewer_report(run_dir, summary))

    def changed_after_verify(_excluded: set[str]) -> dict:
        payload = deepcopy(WORKSPACE)
        payload["tracked_diff_sha256"] = "d" * 64
        return payload

    with pytest.raises(RuntimeError, match="工作区实现内容发生变化"):
        finalize_acceptance(
            run_dir, review_path, workspace_provider=changed_after_verify
        )


def test_finalize_accepts_only_bound_reviewer_evidence(tmp_path: Path):
    _, run_dir, summary = create_verified_run(tmp_path)
    review_path = tmp_path / "review.json"
    write_json(review_path, reviewer_report(run_dir, summary))

    code, accepted = finalize_acceptance(
        run_dir, review_path, workspace_provider=fake_workspace
    )

    assert code == 0
    assert accepted["status"] == "accepted"
    assert accepted["task_id"] == "TASK-001"
    assert len(accepted["gates"]) == 4
    assert (run_dir / "accepted.json").is_file()


def test_finalize_rejects_task_or_gate_evidence_tampering(tmp_path: Path):
    task_path, run_dir, summary = create_verified_run(tmp_path)
    review_path = tmp_path / "review.json"
    write_json(review_path, reviewer_report(run_dir, summary))
    write_json(task_path, task_contract(goal="被修改"))

    with pytest.raises(RuntimeError, match="Task Contract"):
        finalize_acceptance(
            run_dir, review_path, workspace_provider=fake_workspace
        )

    task_path, run_dir, summary = create_verified_run(tmp_path / "second")
    review_path = tmp_path / "second-review.json"
    write_json(review_path, reviewer_report(run_dir, summary))
    evidence = Path(summary["gates"][0]["summary_path"])
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    payload["result"] = "failed"
    write_json(evidence, payload)

    with pytest.raises(RuntimeError, match="子门禁.*证据"):
        finalize_acceptance(
            run_dir, review_path, workspace_provider=fake_workspace
        )

    _, run_dir, summary = create_verified_run(tmp_path / "third")
    review_path = tmp_path / "third-review.json"
    write_json(review_path, reviewer_report(run_dir, summary))
    evidence_root = Path(summary["gates"][1]["evidence_root"])
    write_json(evidence_root / "injected.json", {"unexpected": True})

    with pytest.raises(RuntimeError, match="完整证据目录"):
        finalize_acceptance(
            run_dir, review_path, workspace_provider=fake_workspace
        )


def test_finalize_rejects_gate_command_not_bound_to_task_contract(tmp_path: Path):
    _, run_dir, summary = create_verified_run(tmp_path)
    summary["gates"][0]["command"][1] = "tools/fake_quality_gate.py"
    write_json(run_dir / "summary.json", summary)
    review_path = tmp_path / "review.json"
    write_json(review_path, reviewer_report(run_dir, summary))

    with pytest.raises(RuntimeError, match="命令与 Task Contract 不匹配"):
        finalize_acceptance(
            run_dir, review_path, workspace_provider=fake_workspace
        )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"acceptance_run_id": "other"}, "acceptance_run_id"),
        ({"acceptance_summary_sha256": "0" * 64}, "summary SHA-256"),
        ({"verdict": "BLOCKED"}, "verdict"),
        ({"reviewer_role": "Builder"}, "Reviewer 角色"),
        (
            {
                "findings": [
                    {"id": "REV-1", "status": "open", "title": "未关闭"}
                ]
            },
            "未关闭 finding",
        ),
        (
            {
                "acceptance_criteria": [
                    {
                        "criterion": CRITERIA[0],
                        "result": "PASS",
                        "evidence": "证据",
                    }
                ]
            },
            "逐项覆盖",
        ),
    ],
)
def test_finalize_rejects_unbound_or_incomplete_review(
    tmp_path: Path, overrides: dict, message: str
):
    _, run_dir, summary = create_verified_run(tmp_path)
    review_path = tmp_path / "review.json"
    write_json(review_path, reviewer_report(run_dir, summary, **overrides))

    with pytest.raises(RuntimeError, match=message):
        finalize_acceptance(
            run_dir, review_path, workspace_provider=fake_workspace
        )
