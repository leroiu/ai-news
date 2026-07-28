"""为 Claude 长会话写入不含提示词与密钥的轻量恢复检查点。"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Callable, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "output" / "claude-checkpoints"
GitRunner = Callable[[Sequence[str], Path], tuple[int, str]]


def run_git(arguments: Sequence[str], root: Path) -> tuple[int, str]:
    result = subprocess.run(
        ["git", *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=5,
        check=False,
    )
    output = result.stdout.strip() or result.stderr.strip()
    return result.returncode, output


def git_value(
    runner: GitRunner,
    root: Path,
    *arguments: str,
) -> str:
    code, output = runner(arguments, root)
    return output if code == 0 else f"<unavailable: {output}>"


def build_checkpoint(
    root: Path,
    event: str,
    hook_payload: dict[str, object] | None = None,
    runner: GitRunner = run_git,
) -> dict[str, object]:
    payload = hook_payload or {}
    safe_hook_fields = {
        key: payload[key]
        for key in ("session_id", "hook_event_name", "trigger")
        if key in payload and isinstance(payload[key], (str, int, float, bool))
    }
    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "repository": str(root),
        "branch": git_value(runner, root, "branch", "--show-current"),
        "head": git_value(runner, root, "rev-parse", "HEAD"),
        "last_commit": git_value(runner, root, "log", "-1", "--oneline"),
        "status": git_value(runner, root, "status", "--short"),
        "diff_stat": git_value(runner, root, "diff", "--stat", "HEAD"),
        "hook": safe_hook_fields,
    }


def atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def read_hook_payload() -> dict[str, object]:
    if sys.stdin.isatty():
        return {}
    raw = sys.stdin.read(1_000_000)
    if not raw.strip():
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def write_checkpoint(
    root: Path,
    output: Path,
    event: str,
    hook_payload: dict[str, object] | None = None,
    runner: GitRunner = run_git,
) -> tuple[Path, Path]:
    checkpoint = build_checkpoint(root, event, hook_payload, runner)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    event_path = output / f"{stamp}-{event}.json"
    latest_path = output / "latest.json"
    atomic_write_json(event_path, checkpoint)
    atomic_write_json(latest_path, checkpoint)
    return event_path, latest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", choices=("precompact", "stop", "manual"), required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        event_path, latest_path = write_checkpoint(
            ROOT,
            args.output,
            args.event,
            read_hook_payload(),
        )
    except (OSError, subprocess.SubprocessError) as error:
        print(f"checkpoint warning: {error}", file=sys.stderr)
        return 0
    print(json.dumps({"checkpoint": str(event_path), "latest": str(latest_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
