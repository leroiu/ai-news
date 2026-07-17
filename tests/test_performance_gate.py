from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import subprocess

import pytest

import tools.performance_gate as performance_gate
from tools.browser_gate import CORE_ROUTES
from tools.performance_gate import (
    API_ENDPOINTS,
    API_SAMPLES,
    MEASUREMENT,
    PAGE_SAMPLES,
    build_budgets,
    budget_value,
    compare_budgets,
    confirmed_violations,
    create_baseline,
    validate_audit,
    validate_baseline,
)


def metric(value: float) -> dict:
    return {"min": value, "p50": value, "p95": value, "max": value}


def page_sample(route: str, index: int) -> dict:
    return {
        "route": route,
        "sample": index,
        "status": 200,
        "navigationError": "",
        "wallMs": 40,
        "ttfbMs": 10,
        "domContentLoadedMs": 20,
        "loadMs": 30,
        "fcpMs": 25,
        "lcpMs": 35,
        "cls": 0,
        "longTaskCount": 0,
        "longTaskTotalMs": 0,
        "longTaskMaxMs": 0,
        "domNodes": 100,
        "bodyTextLength": 200,
        "requestCount": 4,
        "encodedBytes": 9000,
        "decodedBytes": 10000,
        "badResponses": [],
        "ignoredResponses": [],
        "failedRequests": [],
        "externalRequests": [],
        "webSockets": [],
        "nonGetRequests": [],
        "responses": [
            {
                "url": f"http://127.0.0.1:8765{route}",
                "status": 200,
                "method": "GET",
                "resourceType": "document",
                "bodyBytes": 2500,
            }
            for _ in range(4)
        ],
    }


def api_sample(index: int) -> dict:
    return {
        "sample": index,
        "url": "http://127.0.0.1:8766/api/health",
        "method": "GET",
        "durationMs": 5,
        "status": 200,
        "bodyBytes": 1000,
        "error": "",
    }


def sample_audit() -> dict:
    page_metrics = {
        "ttfbMs": metric(10),
        "domContentLoadedMs": metric(20),
        "loadMs": metric(30),
        "fcpMs": metric(25),
        "lcpMs": metric(35),
        "cls": metric(0),
        "longTaskCount": metric(0),
        "longTaskTotalMs": metric(0),
        "longTaskMaxMs": metric(0),
        "requestCount": metric(4),
        "encodedBytes": metric(9000),
        "decodedBytes": metric(10000),
        "domNodes": metric(100),
        "bodyTextLength": metric(200),
        "wallMs": metric(40),
    }
    pages = [
        {
            "route": route,
            "warmup": page_sample(route, 0),
            "warmupErrors": 0,
            "samples": [
                page_sample(route, index + 1) for index in range(PAGE_SAMPLES)
            ],
            "aggregate": {
                "route": route,
                "samples": PAGE_SAMPLES,
                "statusErrors": 0,
                "navigationErrors": 0,
                "failedRequests": 0,
                "badResponses": 0,
                "externalRequests": 0,
                "webSockets": 0,
                "nonGetRequests": 0,
                **deepcopy(page_metrics),
            },
        }
        for route in CORE_ROUTES
    ]
    apis = [
        {
            "endpoint": endpoint,
            "warmup": {
                **api_sample(0),
                "url": f"http://127.0.0.1:8766{endpoint}",
            },
            "samples": [
                {
                    **api_sample(index + 1),
                    "url": f"http://127.0.0.1:8766{endpoint}",
                }
                for index in range(API_SAMPLES)
            ],
            "aggregate": {
                "samples": API_SAMPLES,
                "warmupErrors": 0,
                "errors": 0,
                "durationMs": metric(5),
                "bodyBytes": metric(1000),
            },
        }
        for endpoint in API_ENDPOINTS
    ]
    return {
        "schemaVersion": 1,
        "ruleVersion": 4,
        "mode": "merged",
        "origins": {
            "pages": "http://127.0.0.1:8765",
            "apis": "http://127.0.0.1:8766",
        },
        "environment": {
            "node": "v24.0.0",
            "playwright": "1.58.0",
            "chromium": "140.0.0",
            "platform": "win32-x64",
        },
        "measurement": deepcopy(MEASUREMENT),
        "routes": CORE_ROUTES,
        "apiEndpoints": API_ENDPOINTS,
        "pageSamples": PAGE_SAMPLES,
        "apiSamples": API_SAMPLES,
        "pages": pages,
        "apis": apis,
        "summary": {
            "pageRoutes": len(CORE_ROUTES),
            "pageSamples": len(CORE_ROUTES) * PAGE_SAMPLES,
            "apiEndpoints": len(API_ENDPOINTS),
            "apiSamples": len(API_ENDPOINTS) * API_SAMPLES,
            "pageErrors": 0,
            "apiErrors": 0,
        },
    }


def test_budget_value_uses_noise_margin_and_absolute_cap():
    assert budget_value(10, 500, 20, 1.35) == 30
    assert budget_value(400, 500, 20, 1.35) == 500


def test_validate_audit_rejects_missing_and_zero_samples():
    audit = sample_audit()
    assert validate_audit(audit) == ""

    audit["pages"][0]["samples"].pop()
    assert "样本数不足" in validate_audit(audit)

    audit = sample_audit()
    audit["pages"][0]["samples"][0]["lcpMs"] = 0
    assert "lcpMs 必须为有限正数" in validate_audit(audit)


def test_validate_audit_rejects_aggregate_tampering():
    audit = sample_audit()
    audit["pages"][0]["aggregate"]["decodedBytes"]["max"] = 1

    assert "与原始样本不一致" in validate_audit(audit)


def test_validate_audit_rejects_hidden_external_or_bad_response():
    audit = sample_audit()
    audit["pages"][0]["samples"][0]["responses"][0]["url"] = (
        "https://evil.example/payload.js"
    )
    assert "不是隔离 loopback origin" in validate_audit(audit)

    audit = sample_audit()
    audit["pages"][0]["samples"][0]["responses"][0]["status"] = 500
    assert "badResponses 与响应明细不一致" in validate_audit(audit)

    audit = sample_audit()
    audit["pages"][0]["samples"][0]["responses"][0]["bodyBytes"] = 1
    assert "decodedBytes 与响应明细不一致" in validate_audit(audit)

    audit = sample_audit()
    audit["apis"][0]["samples"][0]["method"] = "POST"
    assert "不是隔离 loopback GET" in validate_audit(audit)

    audit = sample_audit()
    audit["apis"][0]["warmup"]["status"] = 500
    assert "样本包含请求错误" in validate_audit(audit)


def write_evidence(path: Path, audit: dict) -> None:
    import json

    path.write_text(json.dumps(audit, ensure_ascii=False), encoding="utf-8")


def test_build_and_validate_baseline(tmp_path: Path):
    audit = sample_audit()
    path = tmp_path / "baseline.json"
    evidence = tmp_path / "audit.json"
    write_evidence(evidence, audit)

    baseline = create_baseline(path, audit, evidence, force=False)

    assert validate_baseline(baseline, audit) == ""
    assert baseline["budgets"]["pages"]["/"]["lcpMs"]["limit"] == 110
    assert baseline["budgets"]["apis"]["/api/health"]["durationMs"]["limit"] == 25


def test_validate_baseline_rejects_manual_limit_relaxation(tmp_path: Path):
    audit = sample_audit()
    evidence = tmp_path / "audit.json"
    write_evidence(evidence, audit)
    baseline = create_baseline(
        tmp_path / "baseline.json", audit, evidence, force=False
    )
    baseline["budgets"]["pages"]["/"]["lcpMs"]["limit"] = 999999

    assert "limit 未按策略生成" in validate_baseline(baseline, audit)


def test_validate_baseline_binds_policy_and_original_evidence(tmp_path: Path):
    audit = sample_audit()
    evidence = tmp_path / "audit.json"
    write_evidence(evidence, audit)
    baseline = create_baseline(
        tmp_path / "baseline.json", audit, evidence, force=False
    )

    tampered = deepcopy(baseline)
    tampered["strategy"]["timing"] = "放宽"
    assert "strategy 被修改" in validate_baseline(tampered, audit)

    tampered = deepcopy(baseline)
    tampered["policy"] = "允许静默放宽"
    assert "policy 被修改" in validate_baseline(tampered, audit)

    tampered = deepcopy(baseline)
    budget = tampered["budgets"]["pages"]["/"]["ttfbMs"]
    budget["observed"] = 100
    budget["limit"] = budget_value(100, 500, 20, 1.35)
    assert "与原始证据不一致" in validate_baseline(tampered, audit)

    evidence.write_text("{}", encoding="utf-8")
    assert "证据摘要不匹配" in validate_baseline(baseline, audit)


def test_create_baseline_rejects_absolute_cap_violation(tmp_path: Path):
    audit = sample_audit()
    for sample in audit["pages"][0]["samples"]:
        sample["domNodes"] = 3000
    audit["pages"][0]["aggregate"]["domNodes"] = metric(3000)
    evidence = tmp_path / "audit.json"
    write_evidence(evidence, audit)

    with pytest.raises(RuntimeError, match="超过绝对上限"):
        create_baseline(
            tmp_path / "baseline.json",
            audit,
            evidence,
            force=False,
        )


def test_compare_budgets_reports_stable_violation():
    audit = sample_audit()
    baseline = {"budgets": build_budgets(audit)}
    audit["pages"][0]["aggregate"]["domNodes"]["max"] = 999
    audit["apis"][0]["aggregate"]["durationMs"]["p95"] = 999

    violations = compare_budgets(audit, baseline)

    assert [item["fingerprint"] for item in violations] == [
        "page|/|domNodes|max",
        "api|/api/health|durationMs|p95",
    ]


def test_confirmed_violations_only_keeps_reproducible_fingerprints():
    initial = [
        {"fingerprint": "page|/events|longTaskMaxMs|max", "actual": 52},
        {"fingerprint": "api|/api/health|durationMs|p95", "actual": 90},
    ]
    recheck = [
        {"fingerprint": "api|/api/health|durationMs|p95", "actual": 95},
    ]

    confirmed, transient = confirmed_violations(initial, recheck)

    assert confirmed == [initial[1]]
    assert transient == [initial[0]]


def _baseline_for_main_test(tmp_path: Path, audit: dict) -> Path:
    evidence = tmp_path / "evidence.json"
    write_evidence(evidence, audit)
    baseline_path = tmp_path / "baseline.json"
    create_baseline(baseline_path, audit, evidence, force=False)
    return baseline_path


def _audit_result() -> dict[str, subprocess.CompletedProcess[str]]:
    return {
        mode: subprocess.CompletedProcess([mode], 0, "", "")
        for mode in ("pages", "apis")
    }


def test_main_allows_a_transient_violation_only_after_clean_recheck(tmp_path: Path, monkeypatch):
    baseline_audit = sample_audit()
    baseline_path = _baseline_for_main_test(tmp_path, baseline_audit)
    initial = deepcopy(baseline_audit)
    events = next(item for item in initial["pages"] if item["route"] == "/events")
    events["aggregate"]["longTaskMaxMs"] = metric(52)
    recheck = deepcopy(baseline_audit)
    calls = []

    def fake_collect(runtime, audit_root):
        calls.append(audit_root)
        return (initial if len(calls) == 1 else recheck), _audit_result()

    monkeypatch.setattr(
        performance_gate,
        "parse_args",
        lambda: SimpleNamespace(
            command="check", output_dir=tmp_path / "output", baseline_path=baseline_path
        ),
    )
    monkeypatch.setattr(performance_gate, "prepare_runtime", lambda _: {"runtime": str(tmp_path)})
    monkeypatch.setattr(performance_gate, "collect_audit", fake_collect)
    monkeypatch.setattr(performance_gate, "protected_digest", lambda: ("same", {}))

    assert performance_gate.main() == 0
    summary = next((tmp_path / "output").glob("*-check/summary.json"))
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert len(calls) == 2
    assert payload["status"] == "passed"
    assert payload["violations"] == []
    assert payload["recheck"]["confirmed_violations"] == []
    assert payload["recheck"]["transient_violations"][0]["fingerprint"] == (
        "page|/events|longTaskMaxMs|max"
    )


def test_main_fails_closed_when_recheck_cannot_be_collected(tmp_path: Path, monkeypatch):
    baseline_audit = sample_audit()
    baseline_path = _baseline_for_main_test(tmp_path, baseline_audit)
    initial = deepcopy(baseline_audit)
    events = next(item for item in initial["pages"] if item["route"] == "/events")
    events["aggregate"]["longTaskMaxMs"] = metric(52)
    calls = []

    def fake_collect(runtime, audit_root):
        calls.append(audit_root)
        if len(calls) == 1:
            return initial, _audit_result()
        raise RuntimeError("recheck infrastructure failure")

    monkeypatch.setattr(
        performance_gate,
        "parse_args",
        lambda: SimpleNamespace(
            command="check", output_dir=tmp_path / "output", baseline_path=baseline_path
        ),
    )
    monkeypatch.setattr(performance_gate, "prepare_runtime", lambda _: {"runtime": str(tmp_path)})
    monkeypatch.setattr(performance_gate, "collect_audit", fake_collect)
    monkeypatch.setattr(performance_gate, "protected_digest", lambda: ("same", {}))

    assert performance_gate.main() == 1
    summary = next((tmp_path / "output").glob("*-check/summary.json"))
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert len(calls) == 2
    assert payload["status"] == "failed"
    assert "recheck infrastructure failure" in payload["error"]


def test_main_rejects_a_reproducible_violation(tmp_path: Path, monkeypatch):
    baseline_audit = sample_audit()
    baseline_path = _baseline_for_main_test(tmp_path, baseline_audit)
    violating = deepcopy(baseline_audit)
    events = next(item for item in violating["pages"] if item["route"] == "/events")
    events["aggregate"]["longTaskMaxMs"] = metric(52)

    monkeypatch.setattr(
        performance_gate,
        "parse_args",
        lambda: SimpleNamespace(
            command="check", output_dir=tmp_path / "output", baseline_path=baseline_path
        ),
    )
    monkeypatch.setattr(performance_gate, "prepare_runtime", lambda _: {"runtime": str(tmp_path)})
    monkeypatch.setattr(
        performance_gate,
        "collect_audit",
        lambda *_: (deepcopy(violating), _audit_result()),
    )
    monkeypatch.setattr(performance_gate, "protected_digest", lambda: ("same", {}))

    assert performance_gate.main() == 1
    summary = next((tmp_path / "output").glob("*-check/summary.json"))
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["violations"][0]["fingerprint"] == "page|/events|longTaskMaxMs|max"
