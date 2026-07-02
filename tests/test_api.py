"""
Tests for api.py — FastAPI 服务端点。

使用 FastAPI TestClient + mock 数据库函数，不触碰生产数据。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch


# ── Helper: build a fresh test client with mocked DB ─────


@pytest.fixture
def client():
    """Provide a TestClient with all DB functions mocked."""
    with patch("src.api.api.get_entities", return_value=[]) as ge, \
         patch("src.api.api.get_entity", return_value=None) as g1, \
         patch("src.api.api.get_relationships", return_value=[]) as gr, \
         patch("src.api.api.get_articles", return_value=[]) as ga, \
         patch("src.api.api.get_reports", return_value=[]) as gre, \
         patch("src.api.api.search", return_value={"entities": [], "articles": []}) as gs, \
         patch("src.api.api.get_stats", return_value={
             "entities": 0, "articles": 0, "relationships": 0, "by_type": {},
         }) as gst, \
         patch("src.api.api.init_db", return_value=None):
        from src.api import app
        yield TestClient(app), {
            "entities": ge, "entity": g1, "relationships": gr,
            "articles": ga, "reports": gre, "search": gs, "stats": gst,
        }


# ── Health ───────────────────────────────────────────────


class TestHealth:
    def test_health_ok(self, client):
        c, _ = client
        resp = c.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "db" in data
        assert "last_pipeline" in data
        assert "last_collector" in data


# ── Entities API ─────────────────────────────────────────


class TestEntitiesApi:
    def test_get_all(self, client):
        c, m = client
        m["entities"].return_value = [
            {"id": "a", "name": "GPT", "type": "model", "importance": 5},
        ]
        resp = c.get("/api/entities")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_filter_by_type(self, client):
        c, m = client
        resp = c.get("/api/entities?type=model")
        assert resp.status_code == 200
        m["entities"].assert_called_once_with("model")

    def test_empty_list(self, client):
        c, _ = client
        resp = c.get("/api/entities")
        assert resp.status_code == 200
        assert resp.json() == []


class TestEntityDetailApi:
    def test_found(self, client):
        c, m = client
        m["entity"].return_value = {
            "id": "gpt-4", "name": "GPT-4", "type": "model", "importance": 5,
        }
        m["relationships"].return_value = [
            {"source_id": "openai", "target_id": "gpt-4", "rel_type": "develops"},
        ]
        resp = c.get("/api/entities/gpt-4")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "GPT-4"
        assert len(data["relationships"]) == 1

    def test_not_found(self, client):
        c, m = client
        m["entity"].return_value = None
        resp = c.get("/api/entities/nonexistent")
        assert resp.status_code == 404
        assert "detail" in resp.json()


# ── Relationships API ────────────────────────────────────


class TestRelationshipsApi:
    def test_get_all(self, client):
        c, m = client
        m["relationships"].return_value = [
            {"source_id": "a", "target_id": "b", "rel_type": "depends_on"},
        ]
        resp = c.get("/api/relationships")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_filter_by_entity(self, client):
        c, m = client
        resp = c.get("/api/relationships?entity_id=openai")
        assert resp.status_code == 200
        m["relationships"].assert_called_once_with("openai")


# ── Articles API ─────────────────────────────────────────


class TestArticlesApi:
    def test_get_with_defaults(self, client):
        c, m = client
        resp = c.get("/api/articles")
        assert resp.status_code == 200
        m["articles"].assert_called_once_with(limit=50, min_score=0)

    def test_with_limit_and_score(self, client):
        c, m = client
        resp = c.get("/api/articles?limit=10&min_score=4")
        assert resp.status_code == 200
        m["articles"].assert_called_once_with(limit=10, min_score=4)

    def test_returns_data(self, client):
        c, m = client
        m["articles"].return_value = [
            {"id": "art-1", "title": "News", "score": 5, "categories": ["AI"]},
        ]
        resp = c.get("/api/articles?limit=3")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# ── Reports API ──────────────────────────────────────────


class TestReportsApi:
    def test_get_daily_reports(self, client):
        c, m = client
        resp = c.get("/api/reports")
        assert resp.status_code == 200
        m["reports"].assert_called_once_with(report_type="daily", limit=30)

    def test_get_weekly_reports(self, client):
        c, m = client
        resp = c.get("/api/reports?type=weekly&limit=5")
        assert resp.status_code == 200
        m["reports"].assert_called_once_with(report_type="weekly", limit=5)


# ── Search API ───────────────────────────────────────────


class TestSearchApi:
    def test_search_requires_query(self, client):
        c, _ = client
        resp = c.get("/api/search")
        assert resp.status_code == 422

    def test_search_with_query(self, client):
        c, m = client
        resp = c.get("/api/search?q=GPT")
        assert resp.status_code == 200
        m["search"].assert_called_once_with("GPT", limit=20, semantic=False)

    def test_search_with_limit(self, client):
        c, m = client
        resp = c.get("/api/search?q=AI&limit=10")
        assert resp.status_code == 200
        m["search"].assert_called_once_with("AI", limit=10, semantic=False)

    def test_returns_results(self, client):
        c, m = client
        m["search"].return_value = {
            "entities": [{"id": "gpt", "name": "GPT-4", "type": "model"}],
            "articles": [{"id": "a1", "title": "GPT-4 released"}],
        }
        resp = c.get("/api/search?q=GPT")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["entities"]) == 1
        assert len(data["articles"]) == 1


# ── Stats API ────────────────────────────────────────────


class TestStatsApi:
    def test_stats(self, client):
        c, m = client
        m["stats"].return_value = {
            "entities": 28, "articles": 280, "relationships": 128,
            "by_type": {"model": 5, "company": 3},
        }
        resp = c.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entities"] == 28
        assert data["by_type"]["model"] == 5


# ── Page Routes ──────────────────────────────────────────


class TestPageRoutes:
    def test_dashboard_route(self, client):
        c, _ = client
        resp = c.get("/")
        assert resp.status_code in (200, 404)

    def test_library_route(self, client):
        c, _ = client
        resp = c.get("/library")
        assert resp.status_code in (200, 404)

    def test_graph_route(self, client):
        c, _ = client
        resp = c.get("/graph")
        assert resp.status_code in (200, 404)

    def test_my_route(self, client):
        c, _ = client
        resp = c.get("/my")
        assert resp.status_code in (200, 404)
