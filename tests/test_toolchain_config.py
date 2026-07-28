from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CHECKOUT_ACTION = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
SETUP_UV_ACTION = "astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b"


def load_yaml(path: Path) -> dict:
    payload = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(payload, dict)
    return payload


def test_collector_uses_frozen_runtime_only_environment():
    workflow = load_yaml(ROOT / ".github" / "workflows" / "collector.yml")
    steps = workflow["jobs"]["collect"]["steps"]

    assert steps[0]["uses"] == CHECKOUT_ACTION
    setup = next(step for step in steps if step.get("uses") == SETUP_UV_ACTION)
    assert setup["with"]["version"] == "0.11.32"
    assert setup["with"]["python-version"] == "3.13.14"
    commands = [step.get("run", "") for step in steps]
    assert "uv sync --frozen --no-dev" in commands
    assert "uv run --frozen --no-dev python collector.py" in commands


def test_security_audit_is_scheduled_and_frozen():
    workflow = load_yaml(ROOT / ".github" / "workflows" / "security-audit.yml")
    steps = workflow["jobs"]["audit"]["steps"]

    assert set(workflow["on"]) == {"schedule", "workflow_dispatch"}
    assert steps[0]["uses"] == CHECKOUT_ACTION
    assert any(
        step.get("run") == "uv run --frozen pip-audit --local" for step in steps
    )


def test_dependabot_covers_every_package_ecosystem_with_cooldown():
    config = load_yaml(ROOT / ".github" / "dependabot.yml")
    updates = config["updates"]

    assert {update["package-ecosystem"] for update in updates} == {
        "uv",
        "npm",
        "github-actions",
        "docker",
    }
    assert all(update["cooldown"]["default-days"] == "7" for update in updates)
