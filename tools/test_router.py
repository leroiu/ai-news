"""基于阶段快照和 coverage 测试上下文的安全增量测试路由。"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.quality_gate import (
    CommandResult,
    EXIT_GIT_POLLUTION,
    EXIT_INFRA_ERROR,
    execute,
    GateRunner,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT = ROOT / ".quality" / "test-router-snapshot.json"
DEFAULT_OUTPUT = ROOT / "output" / "test-router"
MAX_SELECTED_TEST_FILES = 8

TRACKED_DIRECTORIES = ("src", "tests", "tools", "templates", "prompts", "docs")
TRACKED_ROOT_FILES = (
    "collector.py",
    "pipeline.py",
    "pipeline_stages.py",
    "pipeline_utils.py",
    "config.yaml",
    "pyproject.toml",
    "uv.lock",
    "Makefile",
)
FULL_SUITE_FILES = {
    "tests/conftest.py",
    "pyproject.toml",
    "uv.lock",
    "config.yaml",
    "tools/quality_gate.py",
    "tools/test_router.py",
}


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect_project_files(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for directory in TRACKED_DIRECTORIES:
        base = root / directory
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                files[path.relative_to(root).as_posix()] = _hash_file(path)
    for relative in TRACKED_ROOT_FILES:
        path = root / relative
        if path.is_file():
            files[relative] = _hash_file(path)
    return files


def latest_passed_coverage(root: Path) -> Path | None:
    output = root / "output" / "quality-gate"
    candidates: list[tuple[str, Path]] = []
    if not output.exists():
        return None
    for summary_path in output.glob("*-checkpoint/summary.json"):
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        coverage_path = summary_path.parent / "coverage.json"
        if summary.get("result") == "pass" and coverage_path.is_file():
            candidates.append((str(summary.get("finished_at", "")), coverage_path))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def create_snapshot(root: Path, output: Path, coverage_path: Path | None = None) -> dict:
    coverage_path = coverage_path or latest_passed_coverage(root)
    if coverage_path is None or not coverage_path.is_file():
        raise RuntimeError("没有可用的通过态 coverage.json；请先运行完整 checkpoint。")
    payload = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "coverage_path": str(coverage_path.resolve()),
        "coverage_sha256": _hash_file(coverage_path),
        "files": collect_project_files(root),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def changed_files(root: Path, snapshot: dict) -> list[str]:
    before = snapshot.get("files", {})
    after = collect_project_files(root)
    return sorted(
        relative
        for relative in set(before) | set(after)
        if before.get(relative) != after.get(relative)
    )


def _context_to_test_file(context: str) -> str | None:
    if not context:
        return None
    module = context.split(".", 1)[0]
    if module.startswith("tests/"):
        relative = module
    elif module.startswith("test_"):
        relative = f"tests/{module}.py"
    else:
        return None
    return relative.replace("\\", "/")


def coverage_test_map(coverage_path: Path) -> dict[str, set[str]]:
    payload = json.loads(coverage_path.read_text(encoding="utf-8"))
    mapping: dict[str, set[str]] = {}
    for filename, file_data in payload.get("files", {}).items():
        normalized = filename.replace("\\", "/")
        tests: set[str] = set()
        for contexts in file_data.get("contexts", {}).values():
            for context in contexts:
                test_file = _context_to_test_file(context)
                if test_file:
                    tests.add(test_file)
        mapping[normalized] = tests
    return mapping


def build_plan(root: Path, snapshot: dict, coverage_path: Path | None = None) -> dict:
    changes = changed_files(root, snapshot)
    coverage_path = coverage_path or Path(snapshot["coverage_path"])
    coverage_hash_matches = (
        coverage_path.is_file()
        and _hash_file(coverage_path) == snapshot.get("coverage_sha256")
    )
    if not coverage_hash_matches:
        return {
            "mode": "full",
            "changed_files": changes,
            "selected_tests": ["tests"],
            "reasons": ["快照引用的 coverage 证据缺失或内容已变化"],
            "coverage_path": str(coverage_path),
        }
    if not changes:
        return {
            "mode": "none",
            "changed_files": [],
            "selected_tests": [],
            "reasons": ["相对阶段快照没有文件内容变化"],
            "coverage_path": str(coverage_path),
        }

    non_docs = [
        path for path in changes
        if not path.startswith("docs/") and not path.startswith(".workspace/")
    ]
    if not non_docs:
        return {
            "mode": "none",
            "changed_files": changes,
            "selected_tests": [],
            "reasons": ["仅文档或任务协议发生变化"],
            "coverage_path": str(coverage_path),
        }

    full_triggers = sorted(path for path in non_docs if path in FULL_SUITE_FILES)
    asset_changes = sorted(
        path for path in non_docs
        if path.startswith(("templates/", "prompts/"))
    )
    if full_triggers or asset_changes:
        reasons = []
        if full_triggers:
            reasons.append("核心测试/依赖/门禁配置变化: " + ", ".join(full_triggers))
        if asset_changes:
            reasons.append("模板或提示词影响面无法由 Python coverage 完整表达")
        return {
            "mode": "full",
            "changed_files": changes,
            "selected_tests": ["tests"],
            "reasons": reasons,
            "coverage_path": str(coverage_path),
        }

    mapping = coverage_test_map(coverage_path)
    selected: set[str] = set()
    reasons: list[str] = []
    unknown: list[str] = []
    for relative in non_docs:
        if relative.startswith("tests/test_") and relative.endswith(".py"):
            selected.add(relative)
            reasons.append(f"测试文件直接变化: {relative}")
            continue
        if relative.endswith(".py"):
            tests = set(mapping.get(relative, set()))
            if relative.startswith("src/engine/"):
                conventional = f"tests/test_{Path(relative).stem}.py"
                if (root / conventional).is_file():
                    tests.add(conventional)
            if tests:
                selected.update(tests)
                reasons.append(f"coverage 上下文映射 {relative} -> {len(tests)} 个测试文件")
            else:
                unknown.append(relative)
        else:
            unknown.append(relative)

    if unknown:
        return {
            "mode": "full",
            "changed_files": changes,
            "selected_tests": ["tests"],
            "reasons": ["存在无可靠测试映射的变化: " + ", ".join(sorted(unknown))],
            "coverage_path": str(coverage_path),
        }

    selected_list = sorted(selected)
    total_tests = len(list((root / "tests").glob("test_*.py")))
    if not selected_list:
        return {
            "mode": "full",
            "changed_files": changes,
            "selected_tests": ["tests"],
            "reasons": ["变化未选择到任何测试，安全回退全量"],
            "coverage_path": str(coverage_path),
        }
    if (
        len(selected_list) > MAX_SELECTED_TEST_FILES
        or (total_tests >= 4 and len(selected_list) * 2 >= total_tests)
    ):
        return {
            "mode": "full",
            "changed_files": changes,
            "selected_tests": ["tests"],
            "reasons": [f"相关测试达到 {len(selected_list)}/{total_tests}，全量执行更可靠"],
            "coverage_path": str(coverage_path),
        }
    return {
        "mode": "selected",
        "changed_files": changes,
        "selected_tests": selected_list,
        "reasons": reasons,
        "coverage_path": str(coverage_path),
    }


def load_snapshot(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_plan(
    root: Path,
    plan: dict,
    output_root: Path,
    python_executable: str,
    timeout: float,
) -> tuple[int, Path, dict]:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    runner = GateRunner(root=root, coverage_enabled=False)
    git_before, git_before_error = runner._workspace_digest()
    runtime_before, runtime_before_error = runner._runtime_digest()
    command: Sequence[str] = []
    result = CommandResult(0)
    started = time.monotonic()

    if git_before_error or runtime_before_error:
        result = CommandResult(
            EXIT_INFRA_ERROR,
            stderr="\n".join(item for item in (git_before_error, runtime_before_error) if item),
            infra_error=True,
        )
        result_type = "infra_error"
    elif plan["mode"] == "none":
        result_type = "pass"
    else:
        targets = plan["selected_tests"]
        command = [python_executable, "-m", "pytest", *targets, "-q", "--tb=short"]
        result = execute(command, root, timeout)
        if result.infra_error:
            result_type = "infra_error"
        elif result.timed_out:
            result_type = "timeout"
        elif result.returncode == 0:
            result_type = "pass"
        else:
            result_type = "test_failure"

    git_after, git_after_error = runner._workspace_digest()
    runtime_after, runtime_after_error = runner._runtime_digest()
    if git_after_error or runtime_after_error:
        result_type = "infra_error"
    elif git_before != git_after or runtime_before != runtime_after:
        result_type = "workspace_pollution"

    exit_code = {
        "pass": 0,
        "test_failure": 1,
        "infra_error": EXIT_INFRA_ERROR,
        "timeout": 3,
        "workspace_pollution": EXIT_GIT_POLLUTION,
    }[result_type]
    summary = {
        "run_id": run_id,
        "result": result_type,
        "exit_code": exit_code,
        "duration_seconds": round(time.monotonic() - started, 3),
        "plan": plan,
        "command": list(command),
        "pytest_returncode": result.returncode,
        "git_digest_before": git_before,
        "git_digest_after": git_after,
        "runtime_digest_before": runtime_before,
        "runtime_digest_after": runtime_after,
        "workspace_content_changed": git_before != git_after,
        "runtime_content_changed": runtime_before != runtime_after,
        "evidence_directory": str(run_dir),
    }
    (run_dir / "plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (run_dir / "stdout.log").write_text(result.stdout, encoding="utf-8")
    (run_dir / "stderr.log").write_text(result.stderr, encoding="utf-8")
    (run_dir / "commands.txt").write_text(
        (subprocess.list2cmdline(list(command)) if command else "<no pytest required>") + "\n",
        encoding="utf-8",
    )
    return exit_code, run_dir, summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("snapshot", "plan", "run"))
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--coverage", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout", type=float, default=300)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    snapshot_path = args.snapshot.resolve()
    if args.command == "snapshot":
        payload = create_snapshot(ROOT, snapshot_path, args.coverage)
        print(f"[snapshot] {snapshot_path}")
        print(f"文件：{len(payload['files'])}，coverage：{payload['coverage_path']}")
        return 0
    if not snapshot_path.is_file():
        print(f"缺少快照：{snapshot_path}", file=sys.stderr)
        return EXIT_INFRA_ERROR
    snapshot = load_snapshot(snapshot_path)
    plan = build_plan(ROOT, snapshot, args.coverage)
    if args.command == "plan":
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0
    code, run_dir, summary = run_plan(
        ROOT,
        plan,
        args.output_dir,
        sys.executable,
        args.timeout,
    )
    print(f"[{summary['result']}] 证据：{run_dir}")
    print(f"模式：{plan['mode']}，变更：{len(plan['changed_files'])}，测试目标：{plan['selected_tests']}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
