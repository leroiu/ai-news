"""全局 pytest 隔离层的契约测试。"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import socket

import pytest


def test_external_network_is_blocked():
    with pytest.raises(RuntimeError, match="测试禁止外部网络连接"):
        socket.create_connection(("203.0.113.1", 80), timeout=0.01)
    with pytest.raises(RuntimeError, match="测试禁止外部网络连接"):
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(
            b"test",
            ("203.0.113.1", 53),
        )
    with pytest.raises(RuntimeError, match="测试禁止外部网络解析"):
        socket.getaddrinfo("example.com", 443)


def test_ai_clients_are_stubbed():
    from src.engine import ai_client
    from src.engine import classifier, concept_miner, summarizer, trend_reporter

    assert ai_client.call_ai("system", "user") is None
    assert ai_client.embed_texts(["hello"]) is None
    for module in (classifier, concept_miner, summarizer, trend_reporter):
        assert module.call_ai("system", "user") is None


def test_runtime_writes_are_redirected(isolated_test_runtime: Path):
    from src.engine import (
        cache,
        concept_miner,
        db_core,
        fetcher,
        kg_mermaid,
        reporter,
        trend_agent,
        trend_reporter,
    )
    import pipeline_utils
    import src.engine.card_writer as card_writer

    redirected = (
        db_core.DB_PATH,
        cache.CACHE_PATH,
        concept_miner.POOL_PATH,
        concept_miner.MINED_CACHE_PATH,
        fetcher.HEALTH_FILE,
        card_writer.ROOT_DIR,
        reporter.ROOT_DIR,
        concept_miner.ROOT_DIR,
        trend_agent.ROOT_DIR,
        trend_reporter.ROOT_DIR,
        kg_mermaid.ROOT_DIR,
        pipeline_utils.CHECKPOINT_FILE,
    )
    for path in redirected:
        assert Path(path).is_relative_to(isolated_test_runtime)


def test_knowledge_cards_and_pages_are_controlled(
    isolated_cards_dir: Path,
    isolated_test_runtime: Path,
):
    from src.engine import knowledge
    import src.api.api as api_module

    assert knowledge.CARDS_DIR == isolated_cards_dir
    assert len(list(isolated_cards_dir.rglob("*.yaml"))) == 4
    assert api_module.REPORTS_DIR == isolated_test_runtime / "reports"
    assert (api_module.REPORTS_DIR / "dashboard.html").is_file()


def test_default_writers_only_touch_temporary_runtime(
    isolated_test_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from src.engine import (
        concept_miner,
        kg_mermaid,
        reporter,
        trend_agent,
        trend_reporter,
    )
    from src.engine.fetcher import Article
    import pipeline_utils

    daily = reporter.generate_report(
        [
            Article(
                id="one",
                title="One",
                url="https://example.test/one",
                source="test",
                score=3,
            )
        ],
        report_date="2026-07-16",
    )
    graph = {
        "nodes": [],
        "edges": [],
        "stats": {
            "total_nodes": 0,
            "total_edges": 0,
            "components": 0,
            "node_types": {},
            "edge_types": {},
            "most_connected": [],
            "isolated_nodes": [],
        },
    }
    mermaid = kg_mermaid.generate_mermaid_report(graph)
    pipeline_utils.save_checkpoint("isolated", ["one"], 1)
    concept_miner._generate_draft_card(
        {
            "name": "Isolated Concept",
            "confidence_sum": 0.9,
            "occurrences": 1,
            "evidence": ["fixture"],
            "sources": ["test"],
        },
        "isolated-concept",
    )

    today = datetime.now()
    for days_ago in (0, 1):
        date_str = (today - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        (isolated_test_runtime / "reports" / f"{date_str}.md").write_text(
            f"# {date_str}",
            encoding="utf-8",
        )
    monkeypatch.setattr(
        trend_reporter,
        "call_ai",
        lambda *args, **kwargs: {
            "headline": "fixture",
            "top5": [],
            "trends": [],
            "signals": [],
            "new_players": [],
        },
    )
    weekly = trend_reporter.generate_trend_report()
    monkeypatch.setattr(
        trend_agent,
        "_scan_reports",
        lambda reports, period: [{"trend": "fixture", "importance": 3}],
    )
    monkeypatch.setattr(trend_agent, "_enrich_trends", lambda trends: trends)
    monkeypatch.setattr(
        trend_agent,
        "_synthesize_report",
        lambda trends, reports, period, lang: {
            "headline": "agent fixture",
            "top5": [],
            "trends": [],
            "signals": [],
            "new_players": [],
        },
    )
    agent_weekly = trend_agent.generate_trend_report_agent()

    generated = (
        daily,
        mermaid,
        pipeline_utils.CHECKPOINT_FILE,
        isolated_test_runtime
        / "data"
        / "knowledge"
        / "methodology"
        / "isolated-concept.yaml",
        weekly,
        agent_weekly,
    )
    for path in generated:
        assert path is not None
        assert Path(path).is_relative_to(isolated_test_runtime)
        assert Path(path).is_file()


def test_declared_coverage_modules_are_importable():
    import collector
    import pipeline
    import pipeline_stages
    import pipeline_utils

    assert all((collector, pipeline, pipeline_stages, pipeline_utils))
