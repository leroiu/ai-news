"""
Tests for database.py — the unified SQLite data layer.

Uses a temporary in-memory database to avoid touching production data.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from src.engine.database import (
    init_db, get_db,
    upsert_entity, get_entities, get_entity,
    upsert_relationship, get_relationships,
    insert_articles, get_articles,
    insert_report, get_reports,
    search, get_stats,
    DB_PATH,
)


# ── Helpers ──────────────────────────────────────────────


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Redirect DB_PATH to a temp file, then clean up."""
    tmp_db = tmp_path / "test_platform.db"
    monkeypatch.setattr("src.engine.database.DB_PATH", tmp_db)
    init_db()
    yield
    # cleanup
    if tmp_db.exists():
        tmp_db.unlink()


def _sample_entity(**overrides):
    return {
        "id": "test-gpt",
        "name": "GPT-5 Test",
        "type": "model",
        "importance": 5,
        "summary": "A test model",
        "significance": "Test significance",
        "release_date": "2026-01-15",
        "company": "OpenAI",
        "tags": ["llm", "test"],
        "aliases": ["gpt5"],
        "timeline": [{"date": "2026-01", "event": "Released"}],
        "color": "#4C78A8",
        **overrides,
    }


def _sample_article(**overrides):
    return {
        "id": "art-001",
        "title": "Test Article",
        "url": "https://example.com/1",
        "source": "Test Source",
        "published": "2026-06-29T10:00:00Z",
        "content_raw": "Some raw content",
        "categories": ["大模型发布"],
        "title_cn": "测试文章",
        "one_liner": "一句话总结",
        "summary_points": ["点1", "点2", "点3"],
        "score": 5,
        "score_reason": "很重要",
        "cluster_id": "",
        **overrides,
    }


# ── init_db ──────────────────────────────────────────────


class TestInitDb:
    def test_creates_all_tables(self):
        """init_db should create entities, relationships, articles, reports tables."""
        conn = get_db()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {r["name"] for r in tables}
        for t in ("entities", "relationships", "articles", "reports"):
            assert t in table_names, f"Missing table: {t}"
        conn.close()

    def test_idempotent(self):
        """Calling init_db twice should not error."""
        init_db()  # second call
        conn = get_db()
        count = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        assert count == 0  # still empty
        conn.close()

    def test_wal_mode(self):
        """Database should use WAL journal mode."""
        conn = get_db()
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"
        conn.close()

    def test_foreign_keys_enabled(self):
        """Foreign keys should be enabled."""
        conn = get_db()
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1
        conn.close()


# ── Entity CRUD ──────────────────────────────────────────


class TestEntityUpsert:
    def test_insert_new_entity(self):
        upsert_entity(_sample_entity())
        entities = get_entities()
        assert len(entities) == 1
        assert entities[0]["name"] == "GPT-5 Test"

    def test_update_existing_entity(self):
        upsert_entity(_sample_entity())
        upsert_entity(_sample_entity(name="GPT-5 Updated", importance=4))
        entities = get_entities()
        assert len(entities) == 1
        assert entities[0]["name"] == "GPT-5 Updated"
        assert entities[0]["importance"] == 4

    def test_json_fields_roundtrip(self):
        """tags, aliases, timeline should be stored as JSON and returned as lists."""
        upsert_entity(_sample_entity(
            tags=["a", "b"],
            aliases=["alias1"],
            timeline=[{"date": "2026", "event": "Released"}],
        ))
        e = get_entities()[0]
        assert e["tags"] == ["a", "b"]
        assert e["aliases"] == ["alias1"]
        assert e["timeline"] == [{"date": "2026", "event": "Released"}]

    def test_empty_json_fields(self):
        """Empty lists should survive roundtrip."""
        upsert_entity(_sample_entity(tags=[], aliases=[]))
        e = get_entities()[0]
        assert e["tags"] == []
        assert e["aliases"] == []


class TestGetEntities:
    def test_get_all(self):
        upsert_entity(_sample_entity(id="a", type="model"))
        upsert_entity(_sample_entity(id="b", type="company", name="Test Co"))
        assert len(get_entities()) == 2

    def test_filter_by_type(self):
        upsert_entity(_sample_entity(id="a", type="model"))
        upsert_entity(_sample_entity(id="b", type="company", name="Test Co"))
        models = get_entities("model")
        assert len(models) == 1
        assert models[0]["type"] == "model"

    def test_ordered_by_importance(self):
        upsert_entity(_sample_entity(id="a", importance=2, name="Low"))
        upsert_entity(_sample_entity(id="b", importance=5, name="High"))
        entities = get_entities()
        assert entities[0]["name"] == "High"
        assert entities[1]["name"] == "Low"


class TestGetEntity:
    def test_get_existing(self):
        upsert_entity(_sample_entity(id="test-id"))
        e = get_entity("test-id")
        assert e is not None
        assert e["id"] == "test-id"

    def test_get_nonexistent(self):
        assert get_entity("no-such-id") is None


# ── Relationship CRUD ────────────────────────────────────


class TestRelationshipCrud:
    def test_insert_relationship(self):
        upsert_entity(_sample_entity(id="src"))
        upsert_entity(_sample_entity(id="tgt", name="Target"))
        upsert_relationship("src", "tgt", "depends_on", "relies on")
        rels = get_relationships()
        assert len(rels) == 1
        assert rels[0]["source_id"] == "src"
        assert rels[0]["target_id"] == "tgt"

    def test_ignore_duplicate(self):
        upsert_entity(_sample_entity(id="src"))
        upsert_entity(_sample_entity(id="tgt", name="Target"))
        upsert_relationship("src", "tgt", "depends_on")
        upsert_relationship("src", "tgt", "depends_on")  # duplicate
        assert len(get_relationships()) == 1

    def test_filter_by_entity(self):
        upsert_entity(_sample_entity(id="src"))
        upsert_entity(_sample_entity(id="tgt", name="Target"))
        upsert_entity(_sample_entity(id="other", name="Other"))
        upsert_relationship("src", "tgt", "depends_on")
        upsert_relationship("other", "tgt", "uses")

        # tgt is in both relationships
        tgts = get_relationships("tgt")
        assert len(tgts) == 2

        # src is only in one
        srcs = get_relationships("src")
        assert len(srcs) == 1

    def test_no_duplicate_relationship_types(self):
        """Same source/target but different type = two rows."""
        upsert_entity(_sample_entity(id="src"))
        upsert_entity(_sample_entity(id="tgt", name="Target"))
        upsert_relationship("src", "tgt", "depends_on")
        upsert_relationship("src", "tgt", "competes_with")
        assert len(get_relationships()) == 2


# ── Article CRUD ─────────────────────────────────────────


class TestArticleCrud:
    def test_insert_and_get(self):
        insert_articles([_sample_article()])
        articles = get_articles()
        assert len(articles) == 1
        assert articles[0]["title"] == "Test Article"

    def test_ignore_duplicate_id(self):
        insert_articles([_sample_article()])
        insert_articles([_sample_article()])  # same ID
        assert len(get_articles()) == 1

    def test_score_filter(self):
        insert_articles([
            _sample_article(id="a", score=5),
            _sample_article(id="b", score=2),
            _sample_article(id="c", score=4),
        ])
        high = get_articles(min_score=4)
        assert len(high) == 2

    def test_limit(self):
        insert_articles([
            _sample_article(id=f"a{i}", title=f"Article {i}")
            for i in range(10)
        ])
        assert len(get_articles(limit=3)) == 3

    def test_order_by_score_then_date(self):
        insert_articles([
            _sample_article(id="a", score=3, published="2026-06-28T00:00:00Z"),
            _sample_article(id="b", score=5, published="2026-06-27T00:00:00Z"),
            _sample_article(id="c", score=5, published="2026-06-29T00:00:00Z"),
        ])
        articles = get_articles()
        # Both score-5, c has later date
        assert articles[0]["id"] == "c"
        assert articles[1]["id"] == "b"
        assert articles[2]["id"] == "a"

    def test_since_filter(self):
        insert_articles([
            _sample_article(id="old", published="2026-06-01T00:00:00Z"),
            _sample_article(id="new", published="2026-06-28T00:00:00Z"),
        ])
        recent = get_articles(since="2026-06-15")
        assert len(recent) == 1
        assert recent[0]["id"] == "new"

    def test_json_fields_roundtrip(self):
        insert_articles([_sample_article(
            categories=["大模型发布", "Agent"],
            summary_points=["点1", "点2"],
        )])
        a = get_articles()[0]
        assert a["categories"] == ["大模型发布", "Agent"]
        assert a["summary_points"] == ["点1", "点2"]


# ── Report CRUD ──────────────────────────────────────────


class TestReportCrud:
    def test_insert_and_get(self):
        insert_report("2026-06-29", "daily", "reports/daily-2026-06-29.md",
                       fetched=100, filtered=20, star5=3, star4=10, star3=7)
        reports = get_reports()
        assert len(reports) == 1
        assert reports[0]["date"] == "2026-06-29"
        assert reports[0]["star5"] == 3

    def test_replace_on_same_date(self):
        insert_report("2026-06-29", "daily", "reports/v1.md", star5=3)
        insert_report("2026-06-29", "daily", "reports/v2.md", star5=7)
        reports = get_reports()
        assert len(reports) == 1
        assert reports[0]["star5"] == 7  # updated

    def test_filter_by_type(self):
        insert_report("2026-06-22", "weekly", "reports/weekly.md")
        insert_report("2026-06-29", "daily", "reports/daily.md")
        dailies = get_reports("daily")
        assert len(dailies) == 1
        weeklies = get_reports("weekly")
        assert len(weeklies) == 1

    def test_order_by_date_desc(self):
        insert_report("2026-06-25", "daily", "reports/25.md")
        insert_report("2026-06-29", "daily", "reports/29.md")
        insert_report("2026-06-27", "daily", "reports/27.md")
        reports = get_reports()
        assert reports[0]["date"] == "2026-06-29"
        assert reports[2]["date"] == "2026-06-25"

    def test_limit(self):
        for i in range(10):
            insert_report(f"2026-06-{20+i:02d}", "daily", f"reports/{i}.md")
        assert len(get_reports(limit=5)) == 5


# ── Search ───────────────────────────────────────────────


class TestSearch:
    def test_finds_entity_by_name(self):
        upsert_entity(_sample_entity(name="DeepSeek-V3"))
        result = search("DeepSeek")
        assert len(result["entities"]) == 1
        assert result["entities"][0]["name"] == "DeepSeek-V3"

    def test_finds_article_by_title(self):
        insert_articles([_sample_article(title="OpenAI releases GPT-6")])
        result = search("GPT-6")
        assert len(result["articles"]) == 1

    def test_finds_article_by_cn_title(self):
        insert_articles([_sample_article(title_cn="OpenAI 发布新模型")])
        result = search("OpenAI")
        assert len(result["articles"]) == 1

    def test_finds_article_by_one_liner(self):
        insert_articles([_sample_article(one_liner="AI Agent 取得重大突破")])
        result = search("Agent")
        assert len(result["articles"]) == 1

    def test_no_match_returns_empty(self):
        result = search("nonexistentxyz123")
        assert result["entities"] == []
        assert result["articles"] == []

    def test_limit_respected(self):
        for i in range(30):
            upsert_entity(_sample_entity(id=f"e{i}", name=f"Entity {i}"))
        result = search("Entity")
        assert len(result["entities"]) <= 20  # default limit

    def test_case_insensitive(self):
        upsert_entity(_sample_entity(name="GPT"))
        assert len(search("gpt")["entities"]) == 1


class TestSearchSemantic:
    """search() with semantic=True — falls back to keyword when no embeddings."""

    def test_semantic_falls_back_to_keyword(self):
        """Without embeddings, semantic=True should return keyword results."""
        upsert_entity(_sample_entity(name="DeepSeek-V3"))
        result = search("DeepSeek", semantic=True)
        # Should return results (keyword fallback)
        assert result["entities"] or result["articles"]
        assert result["mode"] == "keyword"

    def test_semantic_param_accepted(self):
        """Keyword mode (semantic=False) works as before."""
        upsert_entity(_sample_entity(name="GPT-4"))
        result = search("GPT", semantic=False, limit=20)
        assert isinstance(result["entities"], list)
        assert isinstance(result["articles"], list)


# ── Stats ────────────────────────────────────────────────


class TestGetStats:
    def test_empty_db(self):
        stats = get_stats()
        assert stats["entities"] == 0
        assert stats["articles"] == 0
        assert stats["relationships"] == 0

    def test_counts(self):
        upsert_entity(_sample_entity(id="a", type="model"))
        upsert_entity(_sample_entity(id="b", type="company", name="Co"))
        upsert_entity(_sample_entity(id="c", type="model", name="GPT-4"))
        upsert_relationship("a", "b", "develops")
        insert_articles([_sample_article()])

        stats = get_stats()
        assert stats["entities"] == 3
        assert stats["articles"] == 1
        assert stats["relationships"] == 1

    def test_by_type(self):
        upsert_entity(_sample_entity(id="a", type="model"))
        upsert_entity(_sample_entity(id="b", type="model", name="M2"))
        upsert_entity(_sample_entity(id="c", type="company", name="Co"))
        stats = get_stats()
        assert stats["by_type"]["model"] == 2
        assert stats["by_type"]["company"] == 1
