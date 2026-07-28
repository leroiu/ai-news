from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_longrun_mode_is_noninteractive_without_bypass() -> None:
    longrun = load_json(".claude/settings.longrun.json")
    launcher = (ROOT / "scripts/start-claude-longrun.ps1").read_text(encoding="utf-8")

    assert "bypassPermissions" not in json.dumps(longrun)
    assert '"--permission-mode", "dontAsk"' in launcher
    assert "worktree add" in launcher
    assert '"codex/$runName"' in launcher
    assert "--max-budget-usd" in launcher


def test_shared_rules_block_external_and_self_modifying_actions() -> None:
    settings = load_json(".claude/settings.json")
    denied = set(settings["permissions"]["deny"])

    assert {
        "Read(.env)",
        "Read(.private/**)",
        "Edit(.claude/**)",
        "Edit(AGENTS.md)",
        "Edit(docs/LONG_RUNNING_AGENT_MODE.md)",
        "PowerShell(git push *)",
        "PowerShell(ssh *)",
        "Bash(git push *)",
        "Bash(ssh *)",
    } <= denied


def test_checkpoint_hooks_use_existing_versioned_tool() -> None:
    settings = load_json(".claude/settings.json")
    precompact = settings["hooks"]["PreCompact"][0]["hooks"][0]
    stop = settings["hooks"]["Stop"][0]["hooks"][0]

    assert "tools/claude_checkpoint.py" in precompact["command"]
    assert "tools/claude_checkpoint.py" in stop["command"]
    assert (ROOT / "tools/claude_checkpoint.py").is_file()


def test_agent_instructions_remain_concise() -> None:
    lines = (ROOT / "AGENTS.md").read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 60
