from __future__ import annotations

import json
from pathlib import Path

from tools.performance_arbitration import arbitrate, classify_summary


def write_summary(
    directory: Path,
    *,
    status: str = "passed",
    violations: list[dict] | None = None,
    audit_exit_codes: dict | None = None,
    pollution: bool = False,
) -> Path:
    directory.mkdir(parents=True)
    path = directory / "summary.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "command": "check",
                "run_id": directory.name,
                "status": status,
                "error": "budget regression" if status == "failed" else "",
                "audit": {"exit_codes": audit_exit_codes or {"pages": 0, "apis": 0}},
                "pollution": {"detected": pollution},
                "violations": violations or [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def stable_failure(directory: Path) -> Path:
    return write_summary(
        directory,
        status="failed",
        violations=[{"fingerprint": "page|/events|longTaskMaxMs|max"}],
    )


def test_classify_summary_requires_a_complete_clean_audit_for_budget_vote(tmp_path: Path):
    valid = stable_failure(tmp_path / "valid")
    assert classify_summary(valid)["classification"] == "budget_regression"

    polluted = stable_failure(tmp_path / "polluted")
    payload = json.loads(polluted.read_text(encoding="utf-8"))
    payload["pollution"]["detected"] = True
    polluted.write_text(json.dumps(payload), encoding="utf-8")
    assert classify_summary(polluted)["classification"] == "infrastructure_error"


def test_arbitrate_passes_clean_three_runner_results(tmp_path: Path):
    summaries = [write_summary(tmp_path / f"runner-{index}") for index in range(3)]

    result = arbitrate(summaries)

    assert result["status"] == "passed"
    assert result["verdict"] == "passed"


def test_arbitrate_allows_one_stable_budget_failure_as_environment_noise(tmp_path: Path):
    summaries = [
        stable_failure(tmp_path / "runner-1"),
        write_summary(tmp_path / "runner-2"),
        write_summary(tmp_path / "runner-3"),
    ]

    result = arbitrate(summaries)

    assert result["status"] == "passed"
    assert result["verdict"] == "passed_with_environment_noise"
    assert result["budget_regression_runs"] == 1


def test_arbitrate_blocks_two_or_more_budget_failures(tmp_path: Path):
    summaries = [
        stable_failure(tmp_path / "runner-1"),
        stable_failure(tmp_path / "runner-2"),
        write_summary(tmp_path / "runner-3"),
    ]

    result = arbitrate(summaries)

    assert result["status"] == "failed"
    assert result["verdict"] == "inconclusive_budget_regression"


def test_arbitrate_fails_closed_for_missing_or_invalid_runner_evidence(tmp_path: Path):
    missing = [write_summary(tmp_path / f"runner-{index}") for index in range(2)]
    assert arbitrate(missing)["verdict"] == "infrastructure_error"

    summaries = [
        stable_failure(tmp_path / "valid"),
        write_summary(tmp_path / "passed-1"),
        write_summary(tmp_path / "passed-2", pollution=True),
    ]
    result = arbitrate(summaries)
    assert result["status"] == "failed"
    assert result["verdict"] == "infrastructure_error"
