from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest

from tools.agent_failure_diagnosis import SAFE_COMMANDS, diagnose


def write_summary(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name / "summary.json"
    path.parent.mkdir()
    runner_classifications = payload.pop("__runner_classifications", None)
    if runner_classifications is not None and len(payload.get("runs", [])) == len(runner_classifications):
        for index, classification in enumerate(runner_classifications, start=1):
            runner_path = path.parent / f"runner-{index}" / "summary.json"
            runner_payload = performance_summary(
                status="passed" if classification == "passed" else "failed",
                violations=[{"fingerprint": f"page|/{index}|metric|max"}]
                if classification == "budget_regression"
                else [],
            )
            runner_payload["run_id"] = f"runner-{index}"
            if classification == "infrastructure_error":
                runner_payload["audit"] = {"exit_codes": {"pages": 1, "apis": 0}}
            runner_path.parent.mkdir()
            runner_path.write_text(json.dumps(runner_payload), encoding="utf-8")
            runner = payload["runs"][index - 1]
            if "summary_path" in runner:
                runner["summary_path"] = str(runner_path.relative_to(path.parent))
            if "summary_sha256" in runner:
                runner["summary_sha256"] = hashlib.sha256(runner_path.read_bytes()).hexdigest()
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def pollution() -> dict:
    return {
        "detected": False,
        "before_digest": "before",
        "after_digest": "after",
        "before_counts": {"data": 1},
        "after_counts": {"data": 1},
    }


def quality_summary(*, result: str = "pass", exit_code: int = 0) -> dict:
    return {
        "run_id": "quality-run",
        "profile": "checkpoint",
        "started_at": "2026-07-19T00:00:00+00:00",
        "finished_at": "2026-07-19T00:01:00+00:00",
        "duration_seconds": 60.0,
        "working_directory": "C:/repo",
        "python_executable": "C:/python.exe",
        "git_branch": "codex/test",
        "git_head": "a" * 40,
        "initial_status_count": 0,
        "result": result,
        "exit_code": exit_code,
        "pytest_returncode": exit_code,
        "pytest_duration_seconds": 42.0,
        "process_tree_cleaned": True,
        "test_counts": {"passed": 5, "collected": 5},
        "failure_fingerprints": [],
        "git_status_added": [],
        "git_status_removed": [],
        "git_digest_before": "before",
        "git_digest_after": "before",
        "git_content_changed": False,
        "protected_runtime_paths": ["data"],
        "runtime_digest_before": "before",
        "runtime_digest_after": "before",
        "runtime_content_changed": False,
        "coverage_enabled": True,
        "coverage_summary": {"percent_covered": 56.5},
        "coverage_baseline": {"minimum_percent": 56.0},
        "coverage_baseline_path": ".quality/coverage-baseline.json",
        "evidence_directory": "output/quality-gate/quality-run",
    }


def browser_summary(*, status: str = "passed", exit_code: int | None = 0, polluted: bool = False) -> dict:
    pollute = pollution()
    pollute["detected"] = polluted
    return {
        "schema_version": 1,
        "run_id": "browser-run",
        "generated_at": "2026-07-19T00:00:00Z",
        "status": status,
        "profile": "core",
        "prepare_only": False,
        "routes": ["/"],
        "viewports": [{"name": "desktop"}, {"name": "mobile"}],
        "network": {"policy": "loopback-only", "allowed_external_origins": []},
        "fixed_browser_time": "2026-07-16T12:00:00.000Z",
        "runtime": {"runtime": "output/browser-run/runtime"},
        "browser": {
            "exit_code": exit_code,
            "stdout": "",
            "stderr": "",
            "audit": {
                "cases": [{
                    "passed": status == "passed",
                    "failures": [],
                    "screenshots": {"full": "full.png", "top": "top.png", "bottom": "bottom.png"},
                }],
            },
        },
        "pollution": pollute,
        "error": "" if status == "passed" else "browser failed",
        "run_dir": "output/browser-gate/browser-run",
    }


def accessibility_summary(*, status: str = "passed", new: list | None = None) -> dict:
    new = new or []
    return {
        "schema_version": 1,
        "run_id": "accessibility-run",
        "command": "check",
        "status": status,
        "generated_at": "2026-07-19T00:00:00Z",
        "routes": ["/"],
        "cases": ["desktop-dark"],
        "fixture": {"runtime": "output/accessibility-run/runtime"},
        "audit": {"exit_code": 0, "summary": {"checks": 1, "violations": 0, "infrastructureFailures": 0}},
        "baseline": {"path": ".quality/accessibility-baseline.json", "violation_count": 0},
        "comparison": {"known_count": 0, "new_count": len(new), "resolved_count": 0, "known": [], "new": new, "resolved": []},
        "pollution": pollution(),
        "error": "" if status == "passed" else "accessibility failed",
        "run_dir": "output/accessibility-gate/accessibility-run",
    }


def performance_summary(*, status: str = "passed", violations: list | None = None) -> dict:
    return {
        "schema_version": 1,
        "run_id": "performance-run",
        "command": "check",
        "status": status,
        "generated_at": "2026-07-19T00:00:00Z",
        "audit": {
            "exit_codes": {"pages": 0, "apis": 0},
            "summary": {"pageRoutes": 1, "pageSamples": 3, "apiEndpoints": 1, "apiSamples": 20, "pageErrors": 0, "apiErrors": 0},
        },
        "baseline": {"path": ".quality/performance-baseline.json", "rule_version": 1},
        "violations": violations or [],
        "recheck": {},
        "pollution": pollution(),
        "fixture": {"runtime": "output/performance-run/runtime"},
        "error": "" if status == "passed" else "performance failed",
        "run_dir": "output/performance-gate/performance-run",
    }


def arbitration_run(index: int, classification: str = "passed") -> dict:
    status = "passed" if classification == "passed" else "failed"
    return {
        "summary_path": f"performance-evidence/runner-{index}/summary.json",
        "summary_sha256": f"{index:x}" * 64,
        "classification": classification,
        "fingerprints": [f"page|/{index}|metric|max"] if classification == "budget_regression" else [],
        "run_id": f"runner-{index}",
        "status": status,
        "error": "runner infrastructure error" if classification == "infrastructure_error" else "",
    }


def arbitration_summary(*, status: str = "passed", verdict: str = "passed", failures: int = 0, found: int = 3) -> dict:
    classifications = ["budget_regression"] * failures + ["passed"] * (found - failures)
    return {
        "schema_version": 1,
        "status": status,
        "verdict": verdict,
        "expected_runs": 3,
        "found_runs": found,
        "runs": [arbitration_run(index + 1, value) for index, value in enumerate(classifications)],
        "budget_regression_runs": failures,
        "error": "" if status == "passed" else "arbitration blocked",
        "__runner_classifications": classifications,
    }


@pytest.mark.parametrize(
    ("gate", "payload"),
    [
        ("quality", quality_summary()),
        ("browser", browser_summary()),
        ("accessibility", accessibility_summary()),
        ("performance", performance_summary()),
        ("performance-arbitration", arbitration_summary()),
    ],
)
def test_each_gate_has_a_deterministic_continue_diagnosis(tmp_path: Path, gate: str, payload: dict):
    result = diagnose(gate, write_summary(tmp_path, gate, payload))
    assert result["classification"] == "continue"
    assert result["needs_human"] is False
    assert result["suggested_commands"] == []


def test_failed_quality_and_accessibility_preserve_fingerprints_and_safe_rechecks(tmp_path: Path):
    quality = quality_summary(result="test_failure", exit_code=1)
    quality["failure_fingerprints"] = ["tests/test_api.py::test_health"]
    accessibility = accessibility_summary(status="failed", new=[{"fingerprint": "single-main|/|desktop-dark|body"}])

    for gate, payload in (("quality", quality), ("accessibility", accessibility)):
        result = diagnose(gate, write_summary(tmp_path, gate, payload))
        assert result["fingerprints"]
        assert result["suggested_commands"] == [SAFE_COMMANDS[gate]]
        assert result["needs_human"] is False


def test_performance_and_arbitration_signal_human_attention_only_for_stable_or_quorum_failure(tmp_path: Path):
    performance = performance_summary(status="failed", violations=[{"fingerprint": "page|/events|longTaskMaxMs|max"}])
    arbitration = arbitration_summary(status="failed", verdict="inconclusive_budget_regression", failures=2)

    for gate, payload in (("performance", performance), ("performance-arbitration", arbitration)):
        result = diagnose(gate, write_summary(tmp_path, gate, payload))
        assert result["needs_human"] is True
        assert result["suggested_commands"] == [SAFE_COMMANDS[gate]]


def test_performance_failure_without_a_budget_fingerprint_is_infrastructure_error(tmp_path: Path):
    result = diagnose(
        "performance",
        write_summary(tmp_path, "performance-infra", performance_summary(status="failed")),
    )
    assert result["classification"] == "performance_infrastructure_error"
    assert result["needs_human"] is True


def test_one_runner_noise_is_continue_without_human_escalation(tmp_path: Path):
    result = diagnose(
        "performance-arbitration",
        write_summary(tmp_path, "noise", arbitration_summary(verdict="passed_with_environment_noise", failures=1)),
    )
    assert result["classification"] == "environment_noise"
    assert result["needs_human"] is False


def test_arbitration_infrastructure_error_requires_human_even_when_three_artifacts_exist(tmp_path: Path):
    payload = arbitration_summary(status="failed", verdict="infrastructure_error")
    payload.pop("budget_regression_runs")
    payload["runs"][0] = arbitration_run(1, "infrastructure_error")
    payload["__runner_classifications"][0] = "infrastructure_error"
    result = diagnose("performance-arbitration", write_summary(tmp_path, "infra", payload))
    assert result["classification"] == "infrastructure_error"
    assert result["needs_human"] is True


@pytest.mark.parametrize(
    ("gate", "payload"),
    [
        ("quality", {key: value for key, value in quality_summary().items() if key != "coverage_summary"}),
        ("browser", {**browser_summary(), "browser": {"exit_code": 0, "stdout": "", "stderr": "", "audit": {"cases": []}}}),
        ("accessibility", {"schema_version": 1, "status": "passed"}),
        ("performance", {**performance_summary(), "audit": {"exit_codes": {"pages": 0, "apis": 0}}}),
        ("performance-arbitration", {**arbitration_summary(), "runs": []}),
    ],
)
def test_forged_or_incomplete_passing_evidence_fails_closed(tmp_path: Path, gate: str, payload: dict):
    with pytest.raises(ValueError):
        diagnose(gate, write_summary(tmp_path, gate, payload))


def test_arbitration_rejects_runner_entries_without_auditable_evidence(tmp_path: Path):
    payload = arbitration_summary()
    payload["runs"][1].pop("summary_sha256")
    with pytest.raises(ValueError):
        diagnose("performance-arbitration", write_summary(tmp_path, "forged-run", payload))


@pytest.mark.parametrize(
    ("gate", "payload"),
    [
        ("quality", {**quality_summary(), "test_counts": {"passed": 5, "collected": 1}}),
        ("browser", {**browser_summary(), "browser": {**browser_summary()["browser"], "audit": {"cases": [{"passed": False, "failures": ["bad"], "screenshots": {"full": "full.png", "top": "top.png", "bottom": "bottom.png"}}]}}}),
        ("accessibility", {**accessibility_summary(), "audit": {"exit_code": 0, "summary": {"checks": 1, "violations": 1, "infrastructureFailures": 0}}}),
        ("performance", {**performance_summary(), "audit": {"exit_codes": {"pages": 0, "apis": 0}, "summary": {"pageRoutes": 1, "pageSamples": 3, "apiEndpoints": 1, "apiSamples": 20, "pageErrors": 1, "apiErrors": 0}}}),
    ],
)
def test_internally_contradictory_passing_evidence_fails_closed(tmp_path: Path, gate: str, payload: dict):
    with pytest.raises(ValueError):
        diagnose(gate, write_summary(tmp_path, f"contradictory-{gate}", payload))


def test_arbitration_rejects_runner_path_or_hash_that_cannot_be_verified(tmp_path: Path):
    payload = arbitration_summary()
    payload.pop("__runner_classifications")
    payload["runs"][0]["summary_path"] = "missing/summary.json"
    with pytest.raises(ValueError):
        diagnose("performance-arbitration", write_summary(tmp_path, "missing-runner", payload))


def test_invalid_json_fails_closed(tmp_path: Path):
    path = tmp_path / "invalid.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError):
        diagnose("quality", path)


def test_suggested_commands_are_local_and_non_mutating():
    forbidden = ("deploy", "git ", "gh ", "curl", "wget", "ssh", "http://", "https://")
    for command in SAFE_COMMANDS.values():
        assert not any(token in command.lower() for token in forbidden)
