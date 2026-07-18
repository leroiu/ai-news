"""每日 pipeline 的 inbox 去重契约。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pipeline_stages


COMPLETED_AFTER_FETCH = [
    "classify",
    "knowledge_match",
    "summarize",
    "score",
    "concept_mine",
    "write_report",
    "update_db",
    "render_pages",
]


def run_pipeline_from_inbox(monkeypatch, articles):
    """只执行读取 inbox 的第一阶段，隔离后续外部依赖。"""
    save_checkpoint = Mock()
    monkeypatch.setattr(
        pipeline_stages,
        "load_config",
        lambda: {"degradation": {}, "fetch": {"max_age_hours": 72}},
    )
    monkeypatch.setattr(pipeline_stages, "read_inbox", lambda **_: articles)
    monkeypatch.setattr(pipeline_stages, "apply_cache", lambda _: 0)
    monkeypatch.setattr(pipeline_stages, "save_results", lambda _: None)
    monkeypatch.setattr(pipeline_stages, "save_checkpoint", save_checkpoint)
    monkeypatch.setattr(pipeline_stages, "clear_checkpoint", Mock())
    monkeypatch.setattr(pipeline_stages, "_log_stage", lambda *_: None)
    monkeypatch.setattr(pipeline_stages, "_failed_articles", {})

    result, report_path, status = pipeline_stages.run_daily_pipeline(
        articles=[],
        run_id=42,
        checkpoint={
            "completed_stages": COMPLETED_AFTER_FETCH,
            "report_path": "reports/daily.md",
        },
        limit=None,
        only_unprocessed=False,
        fetch_direct=False,
        concurrency=1,
        fetched_count=len(articles),
    )
    return result, report_path, status, save_checkpoint


def test_pipeline_inbox_stage_keeps_first_article_for_duplicate_id(monkeypatch):
    first = SimpleNamespace(id="same-id")
    duplicate = SimpleNamespace(id="same-id")
    distinct = SimpleNamespace(id="distinct-id")

    result, report_path, status, save_checkpoint = run_pipeline_from_inbox(
        monkeypatch, [first, duplicate, distinct]
    )

    assert result == [first, distinct]
    assert report_path.name == "daily.md"
    assert status == "success"
    save_checkpoint.assert_called_once_with(
        "fetch+dedup", ["same-id", "distinct-id"], 42
    )


def test_pipeline_inbox_stage_preserves_all_distinct_article_ids(monkeypatch):
    first = SimpleNamespace(id="first-id")
    second = SimpleNamespace(id="second-id")

    result, _, status, save_checkpoint = run_pipeline_from_inbox(
        monkeypatch, [first, second]
    )

    assert result == [first, second]
    assert status == "success"
    save_checkpoint.assert_called_once_with(
        "fetch+dedup", ["first-id", "second-id"], 42
    )
