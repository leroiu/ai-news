"""Pipeline 失败语义、断点恢复和逐文章状态的回归测试。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pipeline
import pipeline_stages
import pipeline_utils
from src.engine import db_core
from src.engine.database import (
    finish_pipeline_run,
    get_article_stage_results,
    init_db,
    record_article_stage_results,
    start_pipeline_run,
)
from src.engine.fetcher import Article


def make_article(article_id: str = "a1") -> Article:
    return Article(
        id=article_id,
        title="AI update",
        url=f"https://example.com/{article_id}",
        source="Example",
        content_raw="article body",
    )


def test_incomplete_stage_is_not_added_to_completed_checkpoint(monkeypatch, tmp_path):
    checkpoint_file = tmp_path / "checkpoint.json"
    monkeypatch.setattr(pipeline_utils, "CHECKPOINT_FILE", checkpoint_file)
    pipeline_utils.reset_runtime_state()
    article = make_article()

    pipeline_utils.save_checkpoint(
        "fetch+dedup", [article.id], 7, articles=[article]
    )
    pipeline_utils.save_checkpoint(
        "summarize", [article.id], 7, articles=[article], completed=False
    )

    data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
    assert data["completed_stages"] == ["fetch+dedup"]
    assert data["stage"] == "summarize"
    assert data["articles"][0]["content_raw"] == "article body"


def test_load_checkpoint_mutates_exported_runtime_state(monkeypatch, tmp_path):
    checkpoint_file = tmp_path / "checkpoint.json"
    monkeypatch.setattr(pipeline_utils, "CHECKPOINT_FILE", checkpoint_file)
    failures_ref = pipeline_utils._failed_articles
    times_ref = pipeline_utils._stage_times
    checkpoint_file.write_text(
        json.dumps({
            "failed_articles": {"score": ["a1: ai_unavailable"]},
            "stage_times": {"score": 1.5},
        }),
        encoding="utf-8",
    )

    pipeline_utils.load_checkpoint()

    assert failures_ref == {"score": ["a1: ai_unavailable"]}
    assert times_ref == {"score": 1.5}


def test_article_stage_results_are_upserted(monkeypatch, tmp_path):
    monkeypatch.setattr(db_core, "DB_PATH", tmp_path / "platform.db")
    init_db()
    run_id = start_pipeline_run("daily", 2)

    record_article_stage_results(
        run_id,
        "summarize",
        {
            "a1": ("success", "", ""),
            "a2": ("failed", "ai_unavailable", "provider timeout"),
        },
    )
    record_article_stage_results(
        run_id,
        "summarize",
        {"a2": ("success", "", "")},
    )
    rows = get_article_stage_results(run_id)
    finish_pipeline_run(run_id)

    by_id = {row["article_id"]: row for row in rows}
    assert by_id["a1"]["status"] == "success"
    assert by_id["a1"]["attempt_count"] == 1
    assert by_id["a2"]["status"] == "success"
    assert by_id["a2"]["attempt_count"] == 2


def test_incomplete_article_is_not_persisted(monkeypatch):
    article = make_article()
    article.categories = ["Agent"]
    article.score = 4
    insert_articles = Mock()
    save_checkpoint = Mock()
    record_results = Mock()
    monkeypatch.setattr(pipeline_stages, "summarize", lambda *_args, **_kwargs: [article])
    monkeypatch.setattr(pipeline_stages, "insert_articles", insert_articles)
    monkeypatch.setattr(pipeline_stages, "insert_report", Mock())
    monkeypatch.setattr(pipeline_stages, "init_db", Mock())
    monkeypatch.setattr(pipeline_stages, "save_results", Mock())
    monkeypatch.setattr(pipeline_stages, "save_checkpoint", save_checkpoint)
    monkeypatch.setattr(pipeline_stages, "record_article_stage_results", record_results)
    monkeypatch.setattr(pipeline_stages, "_log_stage", Mock())
    monkeypatch.setattr(pipeline_stages, "_failed_articles", {})

    result, _, status = pipeline_stages.run_daily_pipeline(
        articles=[article],
        run_id=9,
        checkpoint={
            "completed_stages": [
                "fetch+dedup", "classify", "knowledge_match", "score",
                "concept_mine", "write_report", "render_pages",
            ],
            "report_path": "reports/daily.md",
        },
        limit=None,
        only_unprocessed=False,
        fetch_direct=False,
        concurrency=1,
        fetched_count=1,
    )

    assert result == [article]
    assert status == "partial"
    insert_articles.assert_called_once_with([])
    summarize_checkpoint = next(
        call for call in save_checkpoint.call_args_list
        if call.args[0] == "summarize"
    )
    assert summarize_checkpoint.kwargs["completed"] is False


def test_database_failure_does_not_complete_update_db(monkeypatch):
    article = make_article()
    article.categories = ["Agent"]
    article.title_cn = "AI 更新"
    article.score = 4
    save_checkpoint = Mock()
    monkeypatch.setattr(
        pipeline_stages, "init_db", Mock(side_effect=RuntimeError("db unavailable"))
    )
    monkeypatch.setattr(pipeline_stages, "save_results", Mock())
    monkeypatch.setattr(pipeline_stages, "save_checkpoint", save_checkpoint)
    monkeypatch.setattr(pipeline_stages, "record_article_stage_results", Mock())
    monkeypatch.setattr(pipeline_stages, "_log_stage", Mock())
    monkeypatch.setattr(pipeline_stages, "_failed_articles", {})

    _, _, status = pipeline_stages.run_daily_pipeline(
        articles=[article],
        run_id=10,
        checkpoint={
            "completed_stages": [
                "fetch+dedup", "classify", "knowledge_match", "summarize",
                "score", "concept_mine", "write_report", "render_pages",
            ],
            "report_path": "reports/daily.md",
        },
        limit=None,
        only_unprocessed=False,
        fetch_direct=False,
        concurrency=1,
        fetched_count=1,
    )

    assert status == "partial"
    update_checkpoint = next(
        call for call in save_checkpoint.call_args_list
        if call.args[0] == "update_db"
    )
    assert update_checkpoint.kwargs["completed"] is False


def test_partial_main_returns_nonzero_and_keeps_checkpoint(monkeypatch):
    article = make_article()
    article.score = 4
    clear_checkpoint = Mock()
    finish_run = Mock()
    monkeypatch.setattr(pipeline, "setup_logging", Mock())
    monkeypatch.setattr(pipeline, "_parse_args", lambda: {
        "dry_run": False, "fetch_direct": False, "weekly": False,
        "monthly": False, "gen_graph": False, "gen_dashboard": False,
        "gen_library": False, "gen_timeline": False,
        "only_unprocessed": False, "do_resume": False,
        "reset_checkpoint": False, "report_date": None, "limit": None,
        "concurrency": 1,
    })
    monkeypatch.setattr(pipeline, "init_db", Mock())
    monkeypatch.setattr(pipeline, "start_pipeline_run", lambda *_: 11)
    monkeypatch.setattr(
        pipeline, "run_daily_pipeline",
        lambda **_: ([article], Path("reports/daily.md"), "partial"),
    )
    monkeypatch.setattr(pipeline, "clear_checkpoint", clear_checkpoint)
    monkeypatch.setattr(pipeline, "finish_pipeline_run", finish_run)

    assert pipeline.main() == 2
    clear_checkpoint.assert_not_called()
    assert finish_run.call_args.args[1] == "partial"


def test_resume_reconstructs_articles_and_fetched_count(monkeypatch):
    article = make_article()
    article.categories = ["Agent"]
    article.title_cn = "AI 更新"
    article.score = 4
    captured = {}
    checkpoint = {
        "completed_stages": ["fetch+dedup"],
        "stage": "fetch+dedup",
        "articles": [article.to_dict()],
        "fetched_count": 12,
    }
    monkeypatch.setattr(pipeline, "setup_logging", Mock())
    monkeypatch.setattr(pipeline, "_parse_args", lambda: {
        "dry_run": False, "fetch_direct": False, "weekly": False,
        "monthly": False, "gen_graph": False, "gen_dashboard": False,
        "gen_library": False, "gen_timeline": False,
        "only_unprocessed": False, "do_resume": True,
        "reset_checkpoint": False, "report_date": None, "limit": None,
        "concurrency": 1,
    })
    monkeypatch.setattr(pipeline, "load_checkpoint", lambda: checkpoint)
    monkeypatch.setattr(pipeline, "init_db", Mock())
    monkeypatch.setattr(pipeline, "start_pipeline_run", lambda *_: 12)
    monkeypatch.setattr(pipeline, "finish_pipeline_run", Mock())
    monkeypatch.setattr(pipeline, "clear_checkpoint", Mock())

    def fake_run(**kwargs):
        captured.update(kwargs)
        return kwargs["articles"], Path("reports/daily.md"), "success"

    monkeypatch.setattr(pipeline, "run_daily_pipeline", fake_run)

    assert pipeline.main() == 0
    assert captured["articles"][0].id == article.id
    assert captured["articles"][0].title_cn == "AI 更新"
    assert captured["fetched_count"] == 12
