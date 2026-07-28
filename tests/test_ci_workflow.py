from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "quality-gate.yml"
CHECKOUT_ACTION = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
SETUP_NODE_ACTION = "actions/setup-node@48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e"
SETUP_UV_ACTION = "astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b"
UPLOAD_ACTION = "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
DOWNLOAD_ACTION = "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c"


def load_workflow() -> dict:
    # BaseLoader 避免 YAML 1.1 把键名 on 解析成布尔值。
    payload = yaml.load(WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(payload, dict)
    return payload


def steps(job: str) -> list[dict]:
    return load_workflow()["jobs"][job]["steps"]


def test_quality_workflow_has_bounded_non_collector_triggers():
    workflow = load_workflow()
    triggers = workflow["on"]

    assert set(triggers) == {"pull_request", "push", "workflow_dispatch"}
    assert triggers["push"]["branches"] == ["master"]
    assert "data/inbox.jsonl" in triggers["push"]["paths-ignore"]
    assert workflow["concurrency"]["cancel-in-progress"] == "true"


def test_workflow_uses_minimum_permissions_and_windows_only_performance():
    workflow = load_workflow()
    text = WORKFLOW_PATH.read_text(encoding="utf-8").lower()

    assert workflow["permissions"] == {"contents": "read"}
    assert "contents: write" not in text
    assert "secrets." not in text
    assert "deploy" not in text
    assert "git push" not in text
    for job in ("quality", "performance", "performance-arbitration"):
        assert workflow["jobs"][job]["runs-on"] == "windows-latest"
        assert workflow["jobs"][job]["env"]["PYTHONUTF8"] == "1"


def test_quality_keeps_non_performance_gates_serial_and_mandatory():
    commands = [step.get("run", "") for step in steps("quality")]
    expected = [
        "tools/quality_gate.py checkpoint",
        "tools/browser_gate.py --profile core",
        "tools/accessibility_gate.py check",
    ]
    positions = [
        next(index for index, command in enumerate(commands) if marker in command)
        for marker in expected
    ]

    assert positions == sorted(positions)
    assert all("uv run --frozen" in commands[index] for index in positions)
    assert not any("tools/performance_gate.py" in command for command in commands)
    assert any("uv run --frozen ruff check ." in command for command in commands)


def test_each_performance_measurement_uses_frozen_toolchain_and_three_runners():
    workflow = load_workflow()
    performance = workflow["jobs"]["performance"]
    matrix = performance["strategy"]["matrix"]
    commands = [step.get("run", "") for step in steps("performance")]
    uses = [step.get("uses") for step in steps("performance") if step.get("uses")]

    assert performance["needs"] == "quality"
    assert performance["strategy"]["fail-fast"] == "false"
    assert matrix["runner"] == ["one", "two", "three"]
    assert CHECKOUT_ACTION in uses
    assert SETUP_UV_ACTION in uses
    assert SETUP_NODE_ACTION in uses
    assert any("uv sync --frozen --all-groups" in command for command in commands)
    assert any("npm ci" in command for command in commands)
    assert any("playwright install chromium" in command for command in commands)
    assert any("uv run --frozen python tools/performance_gate.py check" in command for command in commands)
    assert any("exit 0" in command for command in commands)


def test_arbitration_downloads_three_runner_evidence_and_is_final_performance_decision():
    workflow = load_workflow()
    arbitration = workflow["jobs"]["performance-arbitration"]
    download = next(
        step for step in steps("performance-arbitration") if str(step.get("uses", "")).startswith("actions/download-artifact@")
    )
    commands = [step.get("run", "") for step in steps("performance-arbitration")]

    assert arbitration["needs"] == ["quality", "performance"]
    assert arbitration["if"] == "${{ always() }}"
    assert download["uses"] == DOWNLOAD_ACTION
    assert download["continue-on-error"] == "true"
    assert "performance-gate-" in download["with"]["pattern"]
    assert any("tools/performance_arbitration.py" in command for command in commands)
    assert any("--input-dir performance-evidence" in command for command in commands)


def test_all_gate_evidence_is_immutable_and_uploaded_on_failure():
    workflow = load_workflow()
    uploads = [
        step
        for job in workflow["jobs"].values()
        for step in job["steps"]
        if str(step.get("uses", "")).startswith("actions/upload-artifact@")
    ]

    assert len(uploads) == 3
    for upload in uploads:
        assert upload["uses"] == UPLOAD_ACTION
        assert upload["if"] == "${{ always() }}"
        assert upload["with"]["retention-days"] == "14"
        assert "github.run_id" in upload["with"]["name"]
        assert "github.run_attempt" in upload["with"]["name"]

    performance_upload = next(
        upload for upload in uploads if "performance-gate-" in upload["with"]["name"]
    )
    assert "matrix.runner" in performance_upload["with"]["name"]
    assert performance_upload["with"]["path"] == "output/performance-gate/"


def test_toolchain_versions_are_pinned_and_actions_use_immutable_commits():
    workflow = load_workflow()
    action_uses = [
        step["uses"]
        for job in workflow["jobs"].values()
        for step in job["steps"]
        if "uses" in step
    ]

    assert all(
        use.rsplit("@", 1)[-1].isalnum() and len(use.rsplit("@", 1)[-1]) == 40
        for use in action_uses
    )
    for job_name in ("quality", "performance"):
        uv_step = next(step for step in steps(job_name) if step.get("uses") == SETUP_UV_ACTION)
        node_step = next(
            step for step in steps(job_name) if step.get("uses") == SETUP_NODE_ACTION
        )
        assert uv_step["with"]["version"] == "0.11.32"
        assert uv_step["with"]["python-version"] == "3.13.14"
        assert node_step["with"]["node-version"] == "24.17.0"
        assert any(
            step.get("run") == "npm install --global npm@11.16.0"
            for step in steps(job_name)
        )


def test_python_314_compatibility_is_visible_but_non_blocking():
    job = load_workflow()["jobs"]["python-314-compatibility"]
    setup = next(step for step in job["steps"] if step.get("uses") == SETUP_UV_ACTION)

    assert job["runs-on"] == "ubuntu-latest"
    assert job["continue-on-error"] == "true"
    assert setup["with"]["version"] == "0.11.32"
    assert setup["with"]["python-version"] == "3.14.6"
    assert any(
        step.get("run") == "uv run --frozen pytest tests -q --tb=short"
        for step in job["steps"]
    )


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
