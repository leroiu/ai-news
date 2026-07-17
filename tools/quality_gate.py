"""AI News 本地质量门禁：运行隔离测试并持久化可审计证据。"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from typing import Callable, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "output" / "quality-gate"
PROTECTED_RUNTIME_PATHS = ("data", "reports", "cache", "logs")
COVERAGE_SOURCE = "src,pipeline,pipeline_stages,pipeline_utils,collector"

EXIT_PASS = 0
EXIT_TEST_FAILURE = 1
EXIT_INFRA_ERROR = 2
EXIT_TIMEOUT = 3
EXIT_GIT_POLLUTION = 4


@dataclass
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    timed_out: bool = False
    infra_error: bool = False
    process_tree_cleaned: bool | None = None


Executor = Callable[[Sequence[str], Path, float], CommandResult]


def execute(command: Sequence[str], cwd: Path, timeout: float) -> CommandResult:
    started = time.monotonic()
    try:
        options: dict[str, object] = {"start_new_session": True}
        if os.name == "nt":
            options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        process = subprocess.Popen(
            list(command),
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            **options,
        )
        stdout, stderr = process.communicate(timeout=timeout)
        return CommandResult(
            process.returncode,
            stdout,
            stderr,
            time.monotonic() - started,
        )
    except subprocess.TimeoutExpired:
        cleaned = terminate_process_tree(process)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                stdout, stderr = process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                if process.stdout:
                    process.stdout.close()
                if process.stderr:
                    process.stderr.close()
                stdout, stderr = "", "子进程树清理失败，输出管道已强制关闭。"
            cleaned = False
        return CommandResult(
            EXIT_TIMEOUT,
            stdout,
            stderr,
            time.monotonic() - started,
            timed_out=True,
            process_tree_cleaned=cleaned,
        )
    except OSError as error:
        return CommandResult(
            EXIT_INFRA_ERROR,
            "",
            f"{type(error).__name__}: {error}",
            time.monotonic() - started,
            infra_error=True,
        )


def terminate_process_tree(process: subprocess.Popen[str]) -> bool:
    """终止门禁启动的整个进程组，不触碰其他系统进程。"""
    if process.poll() is not None:
        return True
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                timeout=10,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return result.returncode == 0
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        return True
    except (OSError, subprocess.SubprocessError):
        try:
            process.kill()
        except OSError:
            pass
        return False


def parse_test_counts(output: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key in ("passed", "failed", "skipped", "error", "errors", "xfailed", "xpassed"):
        matches = re.findall(rf"(\d+)\s+{key}\b", output)
        if matches:
            normalized = "errors" if key in {"error", "errors"} else key
            counts[normalized] = max(counts.get(normalized, 0), int(matches[-1]))
    collected = re.findall(r"collected\s+(\d+)\s+items?", output)
    if collected:
        counts["collected"] = int(collected[-1])
    return counts


def failure_fingerprints(output: str, limit: int = 20) -> list[str]:
    candidates: list[str] = []
    patterns = (
        r"^(FAILED\s+\S+(?:\s+-\s+.+)?)$",
        r"^(ERROR\s+\S+(?:\s+-\s+.+)?)$",
        r"^E\s+([A-Za-z_][\w.]*?(?:Error|Exception):\s*.+)$",
    )
    for line in output.splitlines():
        clean = line.strip()
        for pattern in patterns:
            match = re.match(pattern, clean)
            if match:
                candidates.append(match.group(1))
                break
    unique: list[str] = []
    for item in candidates:
        fingerprint = stable_fingerprint(item)
        if fingerprint not in unique:
            unique.append(fingerprint)
        if len(unique) >= limit:
            break
    return unique


def stable_fingerprint(message: str) -> str:
    normalized = re.sub(r"\s+", " ", message).strip()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    return f"{digest}:{normalized}"


class GateRunner:
    def __init__(
        self,
        root: Path = ROOT,
        output_root: Path = DEFAULT_OUTPUT,
        executor: Executor = execute,
        python_executable: str = sys.executable,
        pytest_available: Callable[[], bool] | None = None,
        coverage_available: Callable[[], bool] | None = None,
        coverage_enabled: bool = True,
        coverage_baseline_path: Path | None = None,
    ) -> None:
        self.root = root
        self.output_root = output_root
        self.executor = executor
        self.python_executable = python_executable
        self.pytest_available = pytest_available or (
            lambda: importlib.util.find_spec("pytest") is not None
        )
        self.coverage_available = coverage_available or (
            lambda: importlib.util.find_spec("coverage") is not None
        )
        self.coverage_enabled = coverage_enabled
        self.coverage_baseline_path = (
            coverage_baseline_path or self.root / ".quality" / "coverage-baseline.json"
        )

    def _git(self, *args: str) -> CommandResult:
        return self.executor(["git", *args], self.root, 15)

    def _workspace_digest(self) -> tuple[str, str]:
        """覆盖 tracked diff 和未跟踪文件内容，发现脏工作树内部变化。"""
        diff = self._git("diff", "--binary", "--no-ext-diff", "HEAD")
        untracked = self._git("ls-files", "--others", "--exclude-standard", "-z")
        if diff.returncode != 0 or untracked.returncode != 0:
            return "", "无法生成 Git 工作区内容指纹。"
        digest = hashlib.sha256(diff.stdout.encode("utf-8", "surrogatepass"))
        for relative in sorted(path for path in untracked.stdout.split("\0") if path):
            path = self.root / relative
            try:
                content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError as error:
                return "", f"无法读取未跟踪文件 {relative}：{error}"
            digest.update(relative.encode("utf-8", "surrogatepass"))
            digest.update(content_hash.encode("ascii"))
        return digest.hexdigest(), ""

    def _runtime_digest(self) -> tuple[str, str]:
        """覆盖 Git 忽略目录，检测测试前后的任意内容变化。"""
        digest = hashlib.sha256()
        for relative_root in PROTECTED_RUNTIME_PATHS:
            root = self.root / relative_root
            digest.update(f"{relative_root}\0".encode("utf-8"))
            if not root.exists():
                digest.update(b"<missing>")
                continue
            try:
                entries = sorted(root.rglob("*"), key=lambda path: path.as_posix())
                for path in entries:
                    relative = path.relative_to(self.root).as_posix()
                    digest.update(relative.encode("utf-8", "surrogatepass"))
                    if path.is_symlink():
                        digest.update(b"<symlink>")
                        digest.update(os.readlink(path).encode("utf-8", "surrogatepass"))
                    elif path.is_file():
                        digest.update(b"<file>")
                        digest.update(hashlib.sha256(path.read_bytes()).digest())
                    elif path.is_dir():
                        digest.update(b"<dir>")
            except OSError as error:
                return "", f"无法读取受保护运行时目录 {relative_root}：{error}"
        return digest.hexdigest(), ""

    def _load_coverage_baseline(self) -> tuple[dict[str, object] | None, str]:
        if not self.coverage_baseline_path.exists():
            return None, ""
        try:
            baseline = json.loads(self.coverage_baseline_path.read_text(encoding="utf-8"))
            baseline["minimum_percent"] = float(baseline["minimum_percent"])
            baseline["tolerance"] = float(baseline.get("tolerance", 0.1))
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
            return None, f"覆盖率基线无效：{error}"
        return baseline, ""

    @staticmethod
    def _read_coverage_summary(path: Path) -> tuple[dict[str, object] | None, str]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            totals = payload["totals"]
            files = payload.get("files", {})
            measured_contexts = {
                context
                for file_data in files.values()
                for contexts in file_data.get("contexts", {}).values()
                for context in contexts
                if context
            }
            return {
                "percent_covered": round(float(totals["percent_covered"]), 4),
                "num_statements": int(totals["num_statements"]),
                "covered_lines": int(totals["covered_lines"]),
                "missing_lines": int(totals["missing_lines"]),
                "num_branches": int(totals["num_branches"]),
                "covered_branches": int(totals["covered_branches"]),
                "missing_branches": int(totals["missing_branches"]),
                "files_with_contexts": sum(
                    bool(file_data.get("contexts")) for file_data in files.values()
                ),
                "measured_test_contexts": len(measured_contexts),
            }, ""
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
            return None, f"无法解析 coverage.json：{error}"

    def run(self, profile: str, timeout: float) -> tuple[int, Path, dict[str, object]]:
        started_at = datetime.now(timezone.utc)
        run_id = started_at.strftime("%Y%m%dT%H%M%S.%fZ")
        run_dir = self.output_root / f"{run_id}-{profile}"
        run_dir.mkdir(parents=True, exist_ok=False)

        head = self._git("rev-parse", "HEAD")
        branch = self._git("branch", "--show-current")
        before = self._git("status", "--porcelain=v1", "--untracked-files=all")
        before_digest, before_digest_error = self._workspace_digest()
        runtime_before, runtime_before_error = self._runtime_digest()

        coverage_data = run_dir / ".coverage"
        coverage_json = run_dir / "coverage.json"
        coverage_xml = run_dir / "coverage.xml"
        if self.coverage_enabled:
            test_command = [
                self.python_executable,
                "-m",
                "coverage",
                "run",
                "--branch",
                f"--data-file={coverage_data}",
                f"--source={COVERAGE_SOURCE}",
                "-m",
                "pytest",
                "tests",
                "-q",
                "--durations=10",
            ]
        else:
            test_command = [
                self.python_executable,
                "-m",
                "pytest",
                "tests",
                "-q",
                "--durations=10",
            ]
        commands: list[Sequence[str]] = [test_command]
        result = CommandResult(EXIT_INFRA_ERROR, stderr="pytest 未执行。")
        result_type = "infra_error"
        coverage_summary: dict[str, object] | None = None
        coverage_baseline: dict[str, object] | None = None
        coverage_results: list[CommandResult] = []

        if (
            any(item.returncode != 0 for item in (head, branch, before))
            or before_digest_error
            or runtime_before_error
        ):
            result.stderr = "无法读取运行前基线；质量门禁拒绝继续。"
            if before_digest_error:
                result.stderr += f"\n{before_digest_error}"
            if runtime_before_error:
                result.stderr += f"\n{runtime_before_error}"
        elif not self.pytest_available():
            result.stderr = f"当前 Python 缺少 pytest：{self.python_executable}"
        elif self.coverage_enabled and not self.coverage_available():
            result.stderr = f"当前 Python 缺少 coverage：{self.python_executable}"
        else:
            result = self.executor(test_command, self.root, timeout)
            if result.infra_error:
                result_type = "infra_error"
            elif result.timed_out and result.process_tree_cleaned:
                result_type = "timeout"
            elif result.timed_out:
                result_type = "infra_error"
                result.stderr += "\n超时后未能确认子进程树已清理。"
            elif result.returncode == 0:
                result_type = "pass"
            elif "No module named pytest" in result.stderr:
                result_type = "infra_error"
            else:
                result_type = "test_failure"

            if self.coverage_enabled and not result.infra_error and not result.timed_out:
                coverage_commands = [
                    [
                        self.python_executable,
                        "-m",
                        "coverage",
                        "json",
                        f"--data-file={coverage_data}",
                        "-o",
                        str(coverage_json),
                    ],
                    [
                        self.python_executable,
                        "-m",
                        "coverage",
                        "xml",
                        f"--data-file={coverage_data}",
                        "-o",
                        str(coverage_xml),
                    ],
                    [
                        self.python_executable,
                        "-m",
                        "coverage",
                        "report",
                        f"--data-file={coverage_data}",
                    ],
                ]
                commands.extend(coverage_commands)
                for coverage_command in coverage_commands:
                    coverage_results.append(
                        self.executor(coverage_command, self.root, min(timeout, 120))
                    )
                if any(item.returncode != 0 or item.infra_error for item in coverage_results):
                    result_type = "infra_error"
                    result.stderr += "\ncoverage 报告生成失败。"
                else:
                    coverage_summary, coverage_error = self._read_coverage_summary(coverage_json)
                    coverage_baseline, baseline_error = self._load_coverage_baseline()
                    if coverage_error or baseline_error:
                        result_type = "infra_error"
                        result.stderr += f"\n{coverage_error or baseline_error}"
                    elif result_type == "pass" and coverage_baseline is not None:
                        actual = float(coverage_summary["percent_covered"])
                        minimum = float(coverage_baseline["minimum_percent"])
                        tolerance = float(coverage_baseline["tolerance"])
                        if actual + tolerance < minimum:
                            result_type = "coverage_regression"

        after = self._git("status", "--porcelain=v1", "--untracked-files=all")
        after_digest, after_digest_error = self._workspace_digest()
        runtime_after, runtime_after_error = self._runtime_digest()
        before_lines = set(before.stdout.splitlines()) if before.returncode == 0 else set()
        after_lines = set(after.stdout.splitlines()) if after.returncode == 0 else set()
        status_added = sorted(after_lines - before_lines)
        status_removed = sorted(before_lines - after_lines)
        runtime_content_changed = runtime_before != runtime_after

        if after.returncode != 0 or after_digest_error or runtime_after_error:
            result_type = "infra_error"
            result.stderr += "\n无法读取测试后的工作区状态。"
            if after_digest_error:
                result.stderr += f"\n{after_digest_error}"
            if runtime_after_error:
                result.stderr += f"\n{runtime_after_error}"
        elif (
            status_added
            or status_removed
            or before_digest != after_digest
            or runtime_content_changed
        ):
            result_type = "git_pollution"

        combined = "\n".join((result.stdout, result.stderr))
        exit_code = {
            "pass": EXIT_PASS,
            "test_failure": EXIT_TEST_FAILURE,
            "coverage_regression": EXIT_TEST_FAILURE,
            "infra_error": EXIT_INFRA_ERROR,
            "timeout": EXIT_TIMEOUT,
            "git_pollution": EXIT_GIT_POLLUTION,
        }[result_type]

        fingerprints = failure_fingerprints(combined)
        fingerprint_gate = "pytest"
        if result_type == "git_pollution":
            fingerprint_gate = "runtime" if runtime_content_changed else "git"
            detail = (
                "受保护运行时目录内容发生变化"
                if runtime_content_changed
                else "; ".join(status_added + status_removed)
                or "工作区内容指纹发生变化"
            )
            fingerprints = [stable_fingerprint(detail)]
        elif result_type == "coverage_regression":
            fingerprint_gate = "coverage"
            detail = (
                f"branch coverage {coverage_summary['percent_covered']:.4f}% "
                f"< baseline {coverage_baseline['minimum_percent']:.4f}%"
            )
            fingerprints = [stable_fingerprint(detail)]
        elif result_type != "pass" and not fingerprints:
            detail = next(
                (line.strip() for line in reversed(combined.splitlines()) if line.strip()),
                result_type,
            )
            fingerprints = [stable_fingerprint(detail)]
        fingerprints = [f"{profile}/{fingerprint_gate}:{item}" for item in fingerprints]

        finished_at = datetime.now(timezone.utc)
        metadata = {
            "run_id": run_id,
            "profile": profile,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": round((finished_at - started_at).total_seconds(), 3),
            "working_directory": str(self.root),
            "python_executable": self.python_executable,
            "git_branch": branch.stdout.strip(),
            "git_head": head.stdout.strip(),
            "initial_status_count": len(before_lines),
        }
        summary: dict[str, object] = {
            **metadata,
            "result": result_type,
            "exit_code": exit_code,
            "pytest_returncode": result.returncode,
            "pytest_duration_seconds": round(result.duration_seconds, 3),
            "process_tree_cleaned": result.process_tree_cleaned,
            "test_counts": parse_test_counts(combined),
            "failure_fingerprints": fingerprints,
            "git_status_added": status_added,
            "git_status_removed": status_removed,
            "git_digest_before": before_digest,
            "git_digest_after": after_digest,
            "git_content_changed": before_digest != after_digest,
            "protected_runtime_paths": list(PROTECTED_RUNTIME_PATHS),
            "runtime_digest_before": runtime_before,
            "runtime_digest_after": runtime_after,
            "runtime_content_changed": runtime_content_changed,
            "coverage_enabled": self.coverage_enabled,
            "coverage_summary": coverage_summary,
            "coverage_baseline": coverage_baseline,
            "coverage_baseline_path": str(self.coverage_baseline_path),
            "evidence_directory": str(run_dir),
        }
        self._write_evidence(
            run_dir,
            metadata,
            summary,
            commands,
            result,
            coverage_results,
            before,
            after,
        )
        return exit_code, run_dir, summary

    @staticmethod
    def _write_evidence(
        run_dir: Path,
        metadata: dict[str, object],
        summary: dict[str, object],
        commands: Sequence[Sequence[str]],
        result: CommandResult,
        coverage_results: Sequence[CommandResult],
        before: CommandResult,
        after: CommandResult,
    ) -> None:
        options = {"ensure_ascii": False, "indent": 2}
        (run_dir / "metadata.json").write_text(
            json.dumps(metadata, **options) + "\n",
            encoding="utf-8",
        )
        (run_dir / "summary.json").write_text(
            json.dumps(summary, **options) + "\n",
            encoding="utf-8",
        )
        (run_dir / "commands.txt").write_text(
            "\n".join(subprocess.list2cmdline(list(command)) for command in commands) + "\n",
            encoding="utf-8",
        )
        (run_dir / "stdout.log").write_text(result.stdout, encoding="utf-8")
        (run_dir / "stderr.log").write_text(result.stderr, encoding="utf-8")
        (run_dir / "coverage-report.txt").write_text(
            "\n".join(item.stdout for item in coverage_results),
            encoding="utf-8",
        )
        (run_dir / "git-status-before.txt").write_text(before.stdout, encoding="utf-8")
        (run_dir / "git-status-after.txt").write_text(after.stdout, encoding="utf-8")
        (run_dir / "command-result.json").write_text(
            json.dumps(asdict(result), **options) + "\n",
            encoding="utf-8",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=("baseline", "checkpoint"))
    parser.add_argument("--timeout", type=float, default=900, help="pytest 超时秒数")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    code, run_dir, summary = GateRunner(output_root=args.output_dir).run(
        args.profile,
        args.timeout,
    )
    print(f"[{summary['result']}] 证据：{run_dir}")
    counts = summary["test_counts"]
    if counts:
        print("测试：" + ", ".join(f"{key}={value}" for key, value in counts.items()))
    coverage = summary["coverage_summary"]
    if coverage:
        print(
            "分支覆盖率："
            f"{coverage['percent_covered']:.2f}% "
            f"({coverage['covered_branches']}/{coverage['num_branches']} branches)"
        )
    if summary["failure_fingerprints"]:
        print("失败指纹：")
        for fingerprint in summary["failure_fingerprints"]:
            print(f"- {fingerprint}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
