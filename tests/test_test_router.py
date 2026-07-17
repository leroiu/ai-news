"""变更感知测试路由的单元测试。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools.test_router import build_plan, collect_project_files, create_snapshot


def _coverage(path: Path, files: dict) -> Path:
    target = path / "coverage.json"
    target.write_text(json.dumps({"files": files}), encoding="utf-8")
    return target


def _snapshot(root: Path, coverage: Path) -> dict:
    return {
        "coverage_path": str(coverage),
        "coverage_sha256": hashlib.sha256(coverage.read_bytes()).hexdigest(),
        "files": collect_project_files(root),
    }


def test_source_change_uses_coverage_context(tmp_path: Path):
    (tmp_path / "src" / "engine").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    source = tmp_path / "src" / "engine" / "classifier.py"
    test = tmp_path / "tests" / "test_classifier.py"
    source.write_text("before", encoding="utf-8")
    test.write_text("def test_x(): pass", encoding="utf-8")
    coverage = _coverage(tmp_path, {
        "src\\engine\\classifier.py": {
            "contexts": {"1": ["test_classifier.TestClassify.test_x"]},
        },
    })
    snapshot = _snapshot(tmp_path, coverage)
    source.write_text("after", encoding="utf-8")

    plan = build_plan(tmp_path, snapshot)

    assert plan["mode"] == "selected"
    assert plan["selected_tests"] == ["tests/test_classifier.py"]


def test_changed_test_file_selects_itself(tmp_path: Path):
    (tmp_path / "tests").mkdir()
    test = tmp_path / "tests" / "test_api.py"
    test.write_text("before", encoding="utf-8")
    coverage = _coverage(tmp_path, {})
    snapshot = _snapshot(tmp_path, coverage)
    test.write_text("after", encoding="utf-8")

    plan = build_plan(tmp_path, snapshot)

    assert plan["mode"] == "selected"
    assert plan["selected_tests"] == ["tests/test_api.py"]


def test_docs_only_change_needs_no_pytest(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    doc = tmp_path / "docs" / "TESTING.md"
    doc.write_text("before", encoding="utf-8")
    coverage = _coverage(tmp_path, {})
    snapshot = _snapshot(tmp_path, coverage)
    doc.write_text("after", encoding="utf-8")

    plan = build_plan(tmp_path, snapshot)

    assert plan["mode"] == "none"


def test_unknown_source_change_falls_back_full(tmp_path: Path):
    (tmp_path / "src").mkdir()
    source = tmp_path / "src" / "new_module.py"
    source.write_text("before", encoding="utf-8")
    coverage = _coverage(tmp_path, {})
    snapshot = _snapshot(tmp_path, coverage)
    source.write_text("after", encoding="utf-8")

    plan = build_plan(tmp_path, snapshot)

    assert plan["mode"] == "full"
    assert plan["selected_tests"] == ["tests"]


def test_core_config_change_falls_back_full(tmp_path: Path):
    config = tmp_path / "pyproject.toml"
    config.write_text("before", encoding="utf-8")
    coverage = _coverage(tmp_path, {})
    snapshot = _snapshot(tmp_path, coverage)
    config.write_text("after", encoding="utf-8")

    plan = build_plan(tmp_path, snapshot)

    assert plan["mode"] == "full"


def test_coverage_evidence_change_falls_back_full(tmp_path: Path):
    (tmp_path / "tests").mkdir()
    test = tmp_path / "tests" / "test_api.py"
    test.write_text("before", encoding="utf-8")
    coverage = _coverage(tmp_path, {})
    snapshot = _snapshot(tmp_path, coverage)
    coverage.write_text('{"files": {"changed": {}}}', encoding="utf-8")
    test.write_text("after", encoding="utf-8")

    plan = build_plan(tmp_path, snapshot)

    assert plan["mode"] == "full"


def test_create_snapshot_requires_passed_coverage(tmp_path: Path):
    coverage = _coverage(tmp_path, {})
    output = tmp_path / ".quality" / "snapshot.json"

    payload = create_snapshot(tmp_path, output, coverage)

    assert output.is_file()
    assert payload["coverage_path"] == str(coverage.resolve())


def test_unchanged_snapshot_selects_no_tests(tmp_path: Path):
    coverage = _coverage(tmp_path, {})
    snapshot = _snapshot(tmp_path, coverage)

    plan = build_plan(tmp_path, snapshot)

    assert plan["mode"] == "none"
    assert plan["selected_tests"] == []
