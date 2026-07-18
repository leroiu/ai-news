from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.agent_failure_diagnosis import SAFE_COMMANDS, diagnose


def write_summary(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name / "summary.json"
    path.parent.mkdir()
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def quality_summary(*, result: str = "pass", exit_code: int = 0) -> dict:
    return {"result": result, "exit_code": exit_code, "test_counts": {}, "failure_fingerprints": [], "git_content_changed": False, "runtime_content_changed": False}


def browser_summary(*, status: str = "passed", exit_code: int | None = 0, pollution: bool = False) -> dict:
    return {"schema_version": 1, "status": status, "browser": {"exit_code": exit_code}, "pollution": {"detected": pollution}, "error": ""}


def accessibility_summary(*, status: str = "passed", new: list | None = None) -> dict:
    return {"schema_version": 1, "status": status, "audit": {"exit_code": 0}, "pollution": {"detected": False}, "comparison": {"new": new or []}, "error": ""}


def performance_summary(*, status: str = "passed", violations: list | None = None) -> dict:
    return {"schema_version": 1, "command": "check", "status": status, "audit": {"exit_codes": {"pages": 0, "apis": 0}}, "pollution": {"detected": False}, "violations": violations or [], "error": ""}


def arbitration_summary(*, status: str = "passed", verdict: str = "passed", failures: int = 0, found: int = 3) -> dict:
    return {"schema_version": 1, "status": status, "verdict": verdict, "expected_runs": 3, "found_runs": found, "runs": [{}, {}, {}], "budget_regression_runs": failures, "error": ""}


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


def test_one_runner_noise_is_continue_without_human_escalation(tmp_path: Path):
    result = diagnose(
        "performance-arbitration",
        write_summary(tmp_path, "noise", arbitration_summary(verdict="passed_with_environment_noise", failures=1)),
    )
    assert result["classification"] == "environment_noise"
    assert result["needs_human"] is False


def test_arbitration_infrastructure_error_requires_human_even_when_three_artifacts_exist(tmp_path: Path):
    result = diagnose(
        "performance-arbitration",
        write_summary(tmp_path, "infra", arbitration_summary(status="failed", verdict="infrastructure_error")),
    )
    assert result["classification"] == "infrastructure_error"
    assert result["needs_human"] is True


@pytest.mark.parametrize(
    ("gate", "payload"),
    [
        ("quality", quality_summary(result="pass", exit_code=1)),
        ("browser", browser_summary(pollution=True)),
        ("accessibility", {"schema_version": 1, "status": "passed"}),
        ("performance", performance_summary(violations=[{"fingerprint": "forged"}])),
        ("performance-arbitration", arbitration_summary(found=2)),
    ],
)
def test_forged_or_incomplete_passing_evidence_fails_closed(tmp_path: Path, gate: str, payload: dict):
    with pytest.raises(ValueError):
        diagnose(gate, write_summary(tmp_path, gate, payload))


def test_invalid_json_fails_closed(tmp_path: Path):
    path = tmp_path / "invalid.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError):
        diagnose("quality", path)


def test_suggested_commands_are_local_and_non_mutating():
    forbidden = ("deploy", "git ", "gh ", "curl", "wget", "ssh", "http://", "https://")
    for command in SAFE_COMMANDS.values():
        assert not any(token in command.lower() for token in forbidden)
