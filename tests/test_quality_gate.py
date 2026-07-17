"""quality_gate 的标准库单元测试；pytest 与 unittest 均可执行。"""

from __future__ import annotations

from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from tools.quality_gate import (
    CommandResult,
    EXIT_GIT_POLLUTION,
    EXIT_INFRA_ERROR,
    EXIT_PASS,
    EXIT_TEST_FAILURE,
    EXIT_TIMEOUT,
    GateRunner,
    execute,
    failure_fingerprints,
    parse_test_counts,
)


class FakeExecutor:
    def __init__(
        self,
        pytest_result: CommandResult | None = None,
        before: str = " M existing.py\n",
        after: str | None = None,
        before_diff: str = "old diff",
        after_diff: str | None = None,
        untracked: str = "",
        on_pytest=None,
        coverage_percent: float = 75.0,
    ) -> None:
        self.pytest_result = pytest_result or CommandResult(0, "350 passed in 1.00s\n")
        self.before = before
        self.after = before if after is None else after
        self.before_diff = before_diff
        self.after_diff = before_diff if after_diff is None else after_diff
        self.untracked = untracked
        self.on_pytest = on_pytest
        self.coverage_percent = coverage_percent
        self.status_calls = 0
        self.diff_calls = 0
        self.commands: list[list[str]] = []

    def __call__(self, command, cwd: Path, timeout: float) -> CommandResult:
        command = list(command)
        self.commands.append(command)
        if command[:2] == ["git", "rev-parse"]:
            return CommandResult(0, "abc123\n")
        if command[:2] == ["git", "branch"]:
            return CommandResult(0, "master\n")
        if command[:2] == ["git", "status"]:
            self.status_calls += 1
            return CommandResult(0, self.before if self.status_calls == 1 else self.after)
        if command[:2] == ["git", "diff"]:
            self.diff_calls += 1
            return CommandResult(0, self.before_diff if self.diff_calls == 1 else self.after_diff)
        if command[:2] == ["git", "ls-files"]:
            return CommandResult(0, self.untracked)
        if command[1:4] == ["-m", "coverage", "json"]:
            output = Path(command[command.index("-o") + 1])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps({
                "totals": {
                    "percent_covered": self.coverage_percent,
                    "num_statements": 100,
                    "covered_lines": 75,
                    "missing_lines": 25,
                    "num_branches": 40,
                    "covered_branches": 30,
                    "missing_branches": 10,
                },
            }), encoding="utf-8")
            return CommandResult(0)
        if command[1:4] == ["-m", "coverage", "xml"]:
            output = Path(command[command.index("-o") + 1])
            output.write_text("<coverage />", encoding="utf-8")
            return CommandResult(0)
        if command[1:4] == ["-m", "coverage", "report"]:
            return CommandResult(0, "TOTAL 100 25 75%\n")
        if "pytest" in command:
            if self.on_pytest:
                self.on_pytest(cwd)
            return self.pytest_result
        return CommandResult(2, stderr=f"unexpected command: {command}")


class QualityGateTests(unittest.TestCase):
    def run_gate(
        self,
        executor: FakeExecutor,
        pytest_available: bool = True,
        coverage_enabled: bool = False,
        baseline_percent: float | None = None,
    ):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        output = root / "output"
        baseline_path = root / ".quality" / "coverage-baseline.json"
        if baseline_percent is not None:
            baseline_path.parent.mkdir(parents=True)
            baseline_path.write_text(json.dumps({
                "minimum_percent": baseline_percent,
                "tolerance": 0.1,
            }), encoding="utf-8")
        runner = GateRunner(
            root=root,
            output_root=output,
            executor=executor,
            python_executable="python-test",
            pytest_available=lambda: pytest_available,
            coverage_available=lambda: True,
            coverage_enabled=coverage_enabled,
            coverage_baseline_path=baseline_path,
        )
        return runner.run("checkpoint", 30)

    def test_pass_writes_complete_evidence(self):
        code, run_dir, summary = self.run_gate(FakeExecutor())

        self.assertEqual(EXIT_PASS, code)
        self.assertEqual("pass", summary["result"])
        self.assertEqual(350, summary["test_counts"]["passed"])
        for name in (
            "metadata.json", "summary.json", "commands.txt", "stdout.log",
            "stderr.log", "git-status-before.txt", "git-status-after.txt",
            "command-result.json",
        ):
            self.assertTrue((run_dir / name).is_file(), name)

    def test_test_failure_has_stable_fingerprint(self):
        result = CommandResult(
            1,
            "FAILED tests/test_api.py::test_health - AssertionError: bad\n"
            "1 failed, 349 passed in 2.00s\n",
        )
        code, _, summary = self.run_gate(FakeExecutor(result))

        self.assertEqual(EXIT_TEST_FAILURE, code)
        self.assertEqual("test_failure", summary["result"])
        self.assertEqual(1, summary["test_counts"]["failed"])
        self.assertIn("tests/test_api.py::test_health", summary["failure_fingerprints"][0])

    def test_missing_pytest_is_infrastructure_error(self):
        executor = FakeExecutor()
        code, run_dir, summary = self.run_gate(executor, pytest_available=False)

        self.assertEqual(EXIT_INFRA_ERROR, code)
        self.assertEqual("infra_error", summary["result"])
        self.assertIn("缺少 pytest", (run_dir / "stderr.log").read_text(encoding="utf-8"))
        self.assertIn("checkpoint/pytest:", summary["failure_fingerprints"][0])
        self.assertFalse(any("pytest" in command for command in executor.commands))

    def test_timeout_is_distinct_result(self):
        result = CommandResult(
            EXIT_TIMEOUT, stderr="slow", timed_out=True, process_tree_cleaned=True,
        )
        code, _, summary = self.run_gate(FakeExecutor(result))

        self.assertEqual(EXIT_TIMEOUT, code)
        self.assertEqual("timeout", summary["result"])
        self.assertTrue(summary["process_tree_cleaned"])

    def test_process_launch_oserror_is_infrastructure_error(self):
        result = CommandResult(
            EXIT_INFRA_ERROR, stderr="PermissionError: denied", infra_error=True,
        )
        code, _, summary = self.run_gate(FakeExecutor(result))

        self.assertEqual(EXIT_INFRA_ERROR, code)
        self.assertEqual("infra_error", summary["result"])

    def test_execute_marks_popen_oserror_as_infrastructure(self):
        with patch("tools.quality_gate.subprocess.Popen", side_effect=PermissionError("denied")):
            result = execute(["missing-command"], Path.cwd(), 1)

        self.assertTrue(result.infra_error)
        self.assertIn("PermissionError", result.stderr)

    def test_execute_timeout_invokes_process_tree_cleanup(self):
        class FakeProcess:
            pid = 123
            returncode = -1
            stdout = None
            stderr = None

            def __init__(self):
                self.calls = 0

            def communicate(self, timeout=None):
                self.calls += 1
                if self.calls == 1:
                    raise subprocess.TimeoutExpired(["pytest"], timeout)
                return "partial", "timed out"

            def kill(self):
                return None

        process = FakeProcess()
        with patch("tools.quality_gate.subprocess.Popen", return_value=process), \
             patch("tools.quality_gate.terminate_process_tree", return_value=True) as cleanup:
            result = execute(["pytest"], Path.cwd(), 1)

        cleanup.assert_called_once_with(process)
        self.assertTrue(result.timed_out)
        self.assertTrue(result.process_tree_cleaned)

    @unittest.skipUnless(
        os.environ.get("AI_NEWS_RUN_PROCESS_TREE_TEST") == "1",
        "显式宿主机进程树测试；设置 AI_NEWS_RUN_PROCESS_TREE_TEST=1 启用",
    )
    def test_execute_timeout_cleans_child_process_tree(self):
        with tempfile.TemporaryDirectory() as td:
            pid_file = Path(td) / "child.pid"
            child_code = "import time; time.sleep(60)"
            parent_code = (
                "import pathlib,subprocess,sys,time;"
                f"p=subprocess.Popen([sys.executable,'-c',{child_code!r}]);"
                f"pathlib.Path({str(pid_file)!r}).write_text(str(p.pid));"
                "time.sleep(60)"
            )
            result = execute([sys.executable, "-c", parent_code], Path(td), 1.5)

            self.assertTrue(result.timed_out)
            self.assertTrue(result.process_tree_cleaned)
            child_pid = int(pid_file.read_text(encoding="utf-8"))
            deadline = time.monotonic() + 3
            while self.process_exists(child_pid) and time.monotonic() < deadline:
                time.sleep(0.1)
            self.assertFalse(self.process_exists(child_pid), f"子进程 {child_pid} 仍存活")

    @staticmethod
    def process_exists(pid: int) -> bool:
        if os.name == "nt":
            import ctypes
            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False

    def test_new_git_change_has_highest_priority(self):
        executor = FakeExecutor(after=" M existing.py\n?? generated.txt\n")
        code, _, summary = self.run_gate(executor)

        self.assertEqual(EXIT_GIT_POLLUTION, code)
        self.assertEqual("git_pollution", summary["result"])
        self.assertEqual(["?? generated.txt"], summary["git_status_added"])
        self.assertIn("checkpoint/git:", summary["failure_fingerprints"][0])

    def test_existing_dirty_worktree_is_not_pollution(self):
        dirty = " M user-change.py\n?? user-note.md\n"
        code, _, summary = self.run_gate(FakeExecutor(before=dirty, after=dirty))

        self.assertEqual(EXIT_PASS, code)
        self.assertEqual([], summary["git_status_added"])
        self.assertEqual([], summary["git_status_removed"])
        self.assertFalse(summary["git_content_changed"])

    def test_content_change_inside_existing_dirty_file_is_pollution(self):
        dirty = " M user-change.py\n"
        executor = FakeExecutor(
            before=dirty, after=dirty,
            before_diff="old content", after_diff="new content",
        )
        code, _, summary = self.run_gate(executor)

        self.assertEqual(EXIT_GIT_POLLUTION, code)
        self.assertEqual("git_pollution", summary["result"])
        self.assertTrue(summary["git_content_changed"])

    def test_content_change_inside_existing_untracked_file_is_pollution(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            note = root / "note.txt"
            note.write_text("before", encoding="utf-8")
            executor = FakeExecutor(
                before="?? note.txt\n",
                after="?? note.txt\n",
                untracked="note.txt\0",
                on_pytest=lambda cwd: (cwd / "note.txt").write_text("after", encoding="utf-8"),
            )
            runner = GateRunner(
                root=root,
                output_root=root / "output",
                executor=executor,
                python_executable="python-test",
                pytest_available=lambda: True,
                coverage_enabled=False,
            )
            code, _, summary = runner.run("checkpoint", 30)

        self.assertEqual(EXIT_GIT_POLLUTION, code)
        self.assertEqual([], summary["git_status_added"])
        self.assertTrue(summary["git_content_changed"])

    def test_runtime_change_in_git_ignored_directory_is_pollution(self):
        executor = FakeExecutor(
            on_pytest=lambda cwd: (cwd / "data" / "state.json").write_text(
                '{"changed": true}',
                encoding="utf-8",
            ),
        )
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / "data").mkdir()
        (root / "data" / "state.json").write_text('{"changed": false}', encoding="utf-8")
        runner = GateRunner(
            root=root,
            output_root=root / "output",
            executor=executor,
            python_executable="python-test",
            pytest_available=lambda: True,
            coverage_enabled=False,
        )

        code, _, summary = runner.run("checkpoint", 30)

        self.assertEqual(EXIT_GIT_POLLUTION, code)
        self.assertTrue(summary["runtime_content_changed"])
        self.assertIn("checkpoint/runtime:", summary["failure_fingerprints"][0])

    def test_coverage_regression_fails_gate(self):
        executor = FakeExecutor(coverage_percent=74.5)

        code, run_dir, summary = self.run_gate(
            executor,
            coverage_enabled=True,
            baseline_percent=75.0,
        )

        self.assertEqual(EXIT_TEST_FAILURE, code)
        self.assertEqual("coverage_regression", summary["result"])
        self.assertEqual(74.5, summary["coverage_summary"]["percent_covered"])
        self.assertTrue((run_dir / "coverage.json").is_file())
        self.assertTrue((run_dir / "coverage.xml").is_file())
        self.assertIn("checkpoint/coverage:", summary["failure_fingerprints"][0])

    def test_coverage_within_tolerance_passes_gate(self):
        code, _, summary = self.run_gate(
            FakeExecutor(coverage_percent=74.95),
            coverage_enabled=True,
            baseline_percent=75.0,
        )

        self.assertEqual(EXIT_PASS, code)
        self.assertEqual("pass", summary["result"])

    def test_parsers_handle_pytest_summary_and_deduplicate_failures(self):
        output = (
            "collected 12 items\n"
            "FAILED tests/test_x.py::test_a - ValueError: x\n"
            "FAILED tests/test_x.py::test_a - ValueError: x\n"
            "1 failed, 10 passed, 1 skipped in 1.0s\n"
        )

        self.assertEqual(
            {"passed": 10, "failed": 1, "skipped": 1, "collected": 12},
            parse_test_counts(output),
        )
        self.assertEqual(1, len(failure_fingerprints(output)))


if __name__ == "__main__":
    unittest.main()
