from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "quality-gate.yml"


def load_workflow() -> dict:
    # BaseLoader 避免 YAML 1.1 把键名 on 解析成布尔值。
    payload = yaml.load(WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(payload, dict)
    return payload


def test_quality_workflow_has_bounded_non_collector_triggers():
    workflow = load_workflow()
    triggers = workflow["on"]

    assert set(triggers) == {"pull_request", "push", "workflow_dispatch"}
    assert triggers["push"]["branches"] == ["master"]
    assert "data/inbox.jsonl" in triggers["push"]["paths-ignore"]
    assert workflow["concurrency"]["cancel-in-progress"] == "true"


def test_quality_workflow_uses_minimum_permissions_and_no_deploy_or_secrets():
    workflow = load_workflow()
    text = WORKFLOW_PATH.read_text(encoding="utf-8").lower()

    assert workflow["permissions"] == {"contents": "read"}
    assert "contents: write" not in text
    assert "secrets." not in text
    assert "deploy" not in text
    assert "git push" not in text
    assert workflow["jobs"]["quality"]["timeout-minutes"] == "45"
    assert workflow["jobs"]["quality"]["runs-on"] == "windows-latest"
    assert workflow["jobs"]["quality"]["env"]["PYTHONUTF8"] == "1"


def test_quality_workflow_restores_frozen_python_and_node_dependencies():
    steps = load_workflow()["jobs"]["quality"]["steps"]
    uses = [step.get("uses") for step in steps if step.get("uses")]
    runs = [step.get("run", "") for step in steps]

    assert "actions/checkout@v7" in uses
    assert "astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b" in uses
    assert "actions/setup-node@v6" in uses
    setup_uv = next(step for step in steps if str(step.get("uses", "")).startswith("astral-sh/setup-uv@"))
    assert setup_uv["with"]["version"] == "0.11.24"
    assert setup_uv["with"]["python-version"] == "3.13.14"
    setup_node = next(step for step in steps if step.get("uses") == "actions/setup-node@v6")
    assert setup_node["with"]["node-version"] == "24.17.0"
    assert any("uv sync --frozen --all-groups" in command for command in runs)
    assert any("npm ci" in command for command in runs)
    assert any("playwright install chromium" in command for command in runs)


def test_quality_workflow_runs_gate_matrix_serially_in_fixed_order():
    steps = load_workflow()["jobs"]["quality"]["steps"]
    commands = [step.get("run", "") for step in steps]
    expected = [
        "tools/quality_gate.py checkpoint",
        "tools/browser_gate.py --profile core",
        "tools/accessibility_gate.py check",
        "tools/performance_gate.py check",
    ]
    positions = [
        next(index for index, command in enumerate(commands) if marker in command)
        for marker in expected
    ]

    assert positions == sorted(positions)
    assert len(set(positions)) == 4
    assert all("uv run --frozen" in commands[index] for index in positions)


def test_quality_workflow_always_uploads_unique_full_evidence():
    steps = load_workflow()["jobs"]["quality"]["steps"]
    upload = next(
        step for step in steps if str(step.get("uses", "")).startswith("actions/upload-artifact@")
    )

    assert upload["uses"] == "actions/upload-artifact@v7"
    assert upload["if"] == "${{ always() }}"
    assert upload["with"]["path"] == "output/"
    assert upload["with"]["if-no-files-found"] == "error"
    assert "github.run_id" in upload["with"]["name"]
    assert "github.run_attempt" in upload["with"]["name"]


def test_portable_baselines_bind_repo_relative_raw_evidence():
    for name in ("accessibility", "performance"):
        baseline_path = ROOT / ".quality" / f"{name}-baseline.json"
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        evidence_value = baseline["evidence"]
        evidence_path = Path(evidence_value)

        assert not evidence_path.is_absolute()
        resolved = ROOT / evidence_path
        assert resolved.is_file()
        assert hashlib.sha256(resolved.read_bytes()).hexdigest() == baseline[
            "evidence_sha256"
        ]
