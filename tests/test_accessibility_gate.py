from __future__ import annotations

import json
from pathlib import Path

from tools.accessibility_gate import (
    EXPECTED_CASES,
    compare_baseline,
    create_baseline,
    load_baseline,
    validate_audit,
    validate_violation_records,
)
from tools.browser_gate import CORE_ROUTES


def sample_audit(*fingerprints: str) -> dict:
    violations = []
    for fingerprint in fingerprints:
        rule, route, case, selector = fingerprint.split("|", 3)
        violations.append(
            {
                "fingerprint": fingerprint,
                "rule": rule,
                "route": route,
                "case": case,
                "selector": selector,
                "detail": "fixture",
            }
        )
    return {
        "schemaVersion": 1,
        "ruleVersion": 3,
        "routes": CORE_ROUTES,
        "cases": EXPECTED_CASES,
        "results": [
            {
                "route": route,
                "case": case,
                "violations": [
                    item
                    for item in violations
                    if item["route"] == route and item["case"] == case
                ],
            }
            for route in CORE_ROUTES
            for case in EXPECTED_CASES
        ],
        "infrastructureFailures": [],
        "summary": {
            "checks": len(CORE_ROUTES) * len(EXPECTED_CASES),
            "violations": len(violations),
            "infrastructureFailures": 0,
        },
        "violations": violations,
    }


def test_validate_audit_requires_complete_matrix():
    audit = sample_audit()
    assert validate_audit(audit) == ""

    audit["summary"]["checks"] -= 1
    assert "数量不完整" in validate_audit(audit)

    forged = sample_audit()
    forged["results"] = []
    assert "route×case" in validate_audit(forged)


def test_compare_baseline_finds_known_new_and_resolved():
    baseline = {
        "violations": sample_audit(
            "single-main|/|desktop-dark|body",
            "control-name|/library|mobile-dark|#search",
        )["violations"]
    }
    audit = sample_audit(
        "single-main|/|desktop-dark|body",
        "link-name|/reports|desktop-light|a:nth-of-type(1)",
    )

    result = compare_baseline(audit, baseline)

    assert [item["rule"] for item in result["known"]] == ["single-main"]
    assert [item["rule"] for item in result["new"]] == ["link-name"]
    assert [item["rule"] for item in result["resolved"]] == ["control-name"]


def test_create_and_load_baseline_is_explicit(tmp_path: Path):
    path = tmp_path / "baseline.json"
    audit = sample_audit("single-main|/|desktop-dark|body")
    evidence = tmp_path / "audit.json"
    evidence.write_text(json.dumps(audit), encoding="utf-8")

    created = create_baseline(path, audit, evidence, force=False)
    loaded, error = load_baseline(path, audit)

    assert error == ""
    assert loaded == created
    assert created["violation_count"] == 1

    try:
        create_baseline(path, audit, evidence, force=False)
    except RuntimeError as exc:
        assert "--force" in str(exc)
    else:
        raise AssertionError("已有基线必须拒绝静默覆盖")


def test_load_baseline_rejects_missing_or_tampered_raw_evidence(tmp_path: Path):
    path = tmp_path / "baseline.json"
    audit = sample_audit("single-main|/|desktop-dark|body")
    evidence = tmp_path / "audit.json"
    evidence.write_text(json.dumps(audit), encoding="utf-8")
    create_baseline(path, audit, evidence, force=False)

    evidence.write_text("{}", encoding="utf-8")
    loaded, error = load_baseline(path, audit)

    assert loaded is None
    assert "SHA-256 不匹配" in error


def test_load_baseline_rejects_rule_or_matrix_drift(tmp_path: Path):
    audit = sample_audit()
    path = tmp_path / "baseline.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "rule_version": 4,
                "routes": CORE_ROUTES,
                "cases": EXPECTED_CASES,
                "violations": [],
            }
        ),
        encoding="utf-8",
    )

    loaded, error = load_baseline(path, audit)

    assert loaded is None
    assert "规则版本变化" in error


def test_violation_records_reject_forged_or_duplicate_fingerprints():
    violation = sample_audit("single-main|/|desktop-dark|body")["violations"][0]
    forged = {**violation, "fingerprint": "forged"}

    assert "指纹与字段不一致" in validate_violation_records([forged])
    assert "重复指纹" in validate_violation_records([violation, violation])

    missing_detail = {key: value for key, value in violation.items() if key != "detail"}
    assert "缺少稳定字段" in validate_violation_records([missing_detail])
    outside = {**violation, "route": "/outside"}
    outside["fingerprint"] = "|".join(
        [outside["rule"], outside["route"], outside["case"], outside["selector"]]
    )
    assert "route 不属于" in validate_violation_records(
        [outside], routes=CORE_ROUTES, cases=EXPECTED_CASES
    )
