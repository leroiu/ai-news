from __future__ import annotations

from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import shutil
import sqlite3
import subprocess
import threading

import pytest

from tools.browser_gate import (
    CORE_ROUTES,
    EXTENDED_ROUTES,
    FIXED_BROWSER_TIME,
    GRAPH_EXTERNAL_ORIGINS,
    audit_pages,
    build_summary,
    fixture_entities,
    prepare_runtime,
    protected_digest,
)


def test_fixture_entities_are_unique_and_cover_core_types():
    entities = fixture_entities()
    ids = [entity["id"] for entity in entities]

    assert len(ids) == len(set(ids))
    assert {"company", "product", "model", "tech", "concept", "person", "event", "methodology"} == {
        entity["type"] for entity in entities
    }
    assert "openai" in ids


def test_prepare_runtime_builds_isolated_database_and_core_pages(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    fixture = prepare_runtime(run_dir)
    runtime = Path(fixture["runtime"])
    page_names = {Path(item["path"]).name for item in fixture["pages"]}

    assert fixture["failures"] == []
    assert fixture["entities"] == 8
    assert "dashboard.html" in page_names
    assert "entity.html" in page_names
    assert "knowledge-graph.html" not in page_names
    assert (runtime / "reports" / "2026-07-16.md").is_file()

    with sqlite3.connect(runtime / "data" / "platform.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0] == 8
        assert conn.execute("SELECT COUNT(*) FROM relationships").fetchone()[0] == 7
        assert conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 2
        timestamps = conn.execute(
            "SELECT DISTINCT created_at, updated_at FROM entities"
        ).fetchall()
        article_timestamps = conn.execute(
            "SELECT DISTINCT created_at FROM articles"
        ).fetchall()
    assert timestamps == [
        ("2026-07-16T08:00:00+00:00", "2026-07-16T08:00:00+00:00")
    ]
    assert article_timestamps == [("2026-07-16T08:00:00+00:00",)]


def test_audit_pages_reports_duplicate_ids(tmp_path: Path):
    page = tmp_path / "duplicate.html"
    page.write_text(
        "<html><body><div id='same'></div><span id='same'></span></body></html>",
        encoding="utf-8",
    )

    result = audit_pages([page])

    assert result[0]["duplicate_ids"] == ["same"]
    assert result[0]["has_document"] is True


def test_protected_digest_detects_runtime_content_change(tmp_path: Path):
    for name in ("data", "reports", "cache", "logs"):
        (tmp_path / name).mkdir()
    before, before_counts = protected_digest(tmp_path)

    (tmp_path / "reports" / "changed.txt").write_text("changed", encoding="utf-8")
    after, after_counts = protected_digest(tmp_path)

    assert before != after
    assert before_counts["reports"] == 0
    assert after_counts["reports"] == 1


def test_build_summary_supports_prepare_only_and_detects_pollution(tmp_path: Path):
    common = {
        "run_id": "fixture",
        "run_dir": tmp_path,
        "fixture": {"runtime": str(tmp_path / "runtime")},
        "routes": ["/"],
        "profile": "core",
        "allowed_origins": [],
        "before_counts": {},
        "after_counts": {},
        "browser_result": None,
        "prepare_only": True,
    }

    passed = build_summary(
        **common,
        before_digest="same",
        after_digest="same",
    )
    polluted = build_summary(
        **common,
        before_digest="before",
        after_digest="after",
    )

    assert passed["status"] == "passed"
    assert polluted["status"] == "failed"
    assert polluted["pollution"]["detected"] is True


def test_route_profiles_keep_cdn_pages_explicit():
    assert "/graph" not in CORE_ROUTES
    assert "/graph3d" not in CORE_ROUTES
    assert "/graph" in EXTENDED_ROUTES
    assert "/graph3d" in EXTENDED_ROUTES
    assert GRAPH_EXTERNAL_ORIGINS == ["https://d3js.org", "https://unpkg.com"]
    assert FIXED_BROWSER_TIME == "2026-07-16T12:00:00.000Z"


def test_browser_audit_blocks_non_application_websocket(tmp_path: Path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js 不可用")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = (
                b"<!doctype html><html><body>"
                b"browser gate websocket policy fixture"
                b"</body></html>"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    output = tmp_path / "browser"
    env = os.environ.copy()
    env.update(
        {
            "FRONTEND_BASE_URL": f"http://127.0.0.1:{server.server_port}",
            "FRONTEND_ROUTES": '["/"]',
            "FRONTEND_OUTPUT_DIR": str(output),
            "FRONTEND_ALLOWED_ORIGINS": "[]",
            "FRONTEND_WEBSOCKET_PROBE_URL": "ws://0.0.0.0:9/leak",
        }
    )
    try:
        result = subprocess.run(
            [node, "tools/browser_audit.spec.js"],
            cwd=Path(__file__).resolve().parent.parent,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    audit = json.loads((output / "audit.json").read_text(encoding="utf-8"))
    assert result.returncode == 1
    assert audit["summary"]["failed"] == 2
    assert all(
        case["webSocketRequests"] == [
            {
                "url": "ws://0.0.0.0:9/leak",
                "origin": "ws://0.0.0.0:9",
                "allowed": False,
            }
        ]
        for case in audit["cases"]
    )
    assert all(
        any(failure.startswith("blocked-websockets:") for failure in case["failures"])
        for case in audit["cases"]
    )
