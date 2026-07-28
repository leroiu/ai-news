from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from tools.claude_checkpoint import build_checkpoint, write_checkpoint


def fake_git(arguments: Sequence[str], root: Path) -> tuple[int, str]:
    values = {
        ("branch", "--show-current"): "codex/example",
        ("rev-parse", "HEAD"): "abc123",
        ("log", "-1", "--oneline"): "abc123 test commit",
        ("status", "--short"): " M src/example.py",
        ("diff", "--stat", "HEAD"): "1 file changed",
    }
    return 0, values[tuple(arguments)]


def test_checkpoint_keeps_only_safe_hook_metadata(tmp_path: Path) -> None:
    checkpoint = build_checkpoint(
        tmp_path,
        "precompact",
        {
            "session_id": "session-1",
            "hook_event_name": "PreCompact",
            "transcript_path": "C:/secret/transcript.jsonl",
            "prompt": "do not persist this",
        },
        fake_git,
    )

    assert checkpoint["branch"] == "codex/example"
    assert checkpoint["status"] == " M src/example.py"
    assert checkpoint["hook"] == {
        "session_id": "session-1",
        "hook_event_name": "PreCompact",
    }
    assert "transcript_path" not in json.dumps(checkpoint)
    assert "do not persist this" not in json.dumps(checkpoint)


def test_write_checkpoint_updates_event_and_latest_files(tmp_path: Path) -> None:
    event_path, latest_path = write_checkpoint(
        tmp_path,
        tmp_path / "checkpoints",
        "stop",
        {"session_id": "session-2"},
        fake_git,
    )

    assert event_path.is_file()
    assert latest_path.is_file()
    assert json.loads(event_path.read_text(encoding="utf-8"))["event"] == "stop"
    assert json.loads(latest_path.read_text(encoding="utf-8"))["hook"]["session_id"] == "session-2"
