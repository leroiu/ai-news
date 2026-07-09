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

MOCK_ADMIN = {"id": 0, "username": "admin", "email": "", "role": "admin", "created_at": ""}


@pytest.fixture
def client():
    """Provide a TestClient with all DB functions mocked."""
    with patch("src.api.api.get_entities", return_value=[]) as ge, \
         patch("src.api.api.get_entity", return_value=None) as g1, \
         patch("src.api.api.get_relationships", return_value=[]) as gr, \
         patch("src.api.api.get_articles", return_value=[]) as ga, \
         patch("src.api.api.get_article", return_value=None) as gad, \
         patch("src.api.api.get_reports", return_value=[]) as gre, \
         patch("src.api.api.search", return_value={"entities": [], "articles": []}) as gs, \
         patch("src.api.api.get_stats", return_value={
             "entities": 0, "articles": 0, "relationships": 0, "by_type": {},
         }) as gst, \
         patch("src.api.api.init_db", return_value=None), \
         patch("src.api.api.upsert_entity") as ue, \
         patch("src.api.api.delete_entity", return_value=True) as de, \
         patch("src.api.api.upsert_relationship") as ur, \
         patch("src.api.api.delete_relationship", return_value=True) as dr, \
         patch("src.api.api.save_entity_version") as sev, \
         patch("src.api.api.get_entity_versions", return_value=[]) as gev, \
         patch("src.api.api.run_migrations", return_value=[]) as rm, \
         patch("src.engine.database.get_applied_migrations", return_value=set()) as gam:
        from src.api import app
        # Bypass auth for tests
        from src.api.middleware import get_current_user, require_admin
        app.dependency_overrides[get_current_user] = lambda: MOCK_ADMIN
        app.dependency_overrides[require_admin] = lambda: MOCK_ADMIN
        yield TestClient(app), {
            "entities": ge, "entity": g1, "relationships": gr,
            "articles": ga, "article": gad, "reports": gre, "search": gs, "stats": gst,
            "upsert_entity": ue, "delete_entity": de,
            "upsert_relationship": ur, "delete_relationship": dr,
            "save_entity_version": sev, "get_entity_versions": gev,
            "run_migrations": rm,
        }
        # Clean up overrides
        app.dependency_overrides.clear()


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
        data = resp.json()
        assert data["error"]["code"] == "NOT_FOUND"


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
        m["articles"].assert_called_once_with(limit=50, min_score=0, since=None)

    def test_with_limit_and_score(self, client):
        c, m = client
        resp = c.get("/api/articles?limit=10&min_score=4")
        assert resp.status_code == 200
        m["articles"].assert_called_once_with(limit=10, min_score=4, since=None)

    def test_returns_data(self, client):
        c, m = client
        m["articles"].return_value = [
            {"id": "art-1", "title": "News", "score": 5, "categories": ["AI"]},
        ]
        resp = c.get("/api/articles?limit=3")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_article_detail_found(self, client):
        c, m = client
        m["article"].return_value = {"id": "art-1", "title": "News", "source": "OpenAI"}
        resp = c.get("/api/articles/art-1")
        assert resp.status_code == 200
        assert resp.json()["provenance"]["credibility"] == "high"

    def test_article_detail_not_found(self, client):
        c, _ = client
        assert c.get("/api/articles/missing").status_code == 404


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

    def test_report_content_rejects_invalid_filename(self, client):
        c, _ = client
        assert c.get("/api/report-content/not-markdown.txt").status_code == 400


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

    def test_article_and_report_reader_routes(self, client):
        c, _ = client
        assert c.get("/article/demo").status_code in (200, 404)
        assert c.get("/report/demo.md").status_code in (200, 404)


# ── Entity Write API ─────────────────────────────────────


class TestEntityCreate:
    def test_create_success(self, client):
        c, m = client
        m["entity"].return_value = None  # doesn't exist yet
        m["entity"].return_value = None
        m["entity"].side_effect = [None, {  # get_entity: first None, then created
            "id": "new-card", "name": "New Card", "type": "concept", "importance": 3,
        }]
        payload = {"id": "new-card", "name": "New Card", "type": "concept"}
        resp = c.post("/api/entities", json=payload)
        assert resp.status_code == 201
        assert resp.json()["id"] == "new-card"

    def test_create_missing_id(self, client):
        c, _ = client
        resp = c.post("/api/entities", json={"name": "No ID"})
        assert resp.status_code in (400, 422)

    def test_create_missing_name(self, client):
        c, _ = client
        resp = c.post("/api/entities", json={"id": "no-name"})
        assert resp.status_code in (400, 422)

    def test_create_duplicate(self, client):
        c, m = client
        m["entity"].return_value = {"id": "exists", "name": "Exists"}
        resp = c.post("/api/entities", json={"id": "exists", "name": "Exists"})
        assert resp.status_code == 409


class TestEntityUpdate:
    def test_update_success(self, client):
        c, m = client
        m["entity"].return_value = {
            "id": "card-1", "name": "Old", "type": "concept", "importance": 3,
            "summary": "", "significance": "", "release_date": "",
            "company": "", "tags": [], "aliases": [], "timeline": [], "color": "#999",
        }
        payload = {"summary": "Updated summary", "importance": 5}
        resp = c.put("/api/entities/card-1", json=payload)
        assert resp.status_code == 200
        m["upsert_entity"].assert_called_once()

    def test_update_not_found(self, client):
        c, m = client
        m["entity"].return_value = None
        resp = c.put("/api/entities/nope", json={"summary": "x"})
        assert resp.status_code == 404

    def test_update_preserves_id(self, client):
        """id 字段不可变更"""
        c, m = client
        existing = {"id": "card-1", "name": "Old", "type": "concept", "importance": 3,
                    "summary": "", "significance": "", "release_date": "",
                    "company": "", "tags": [], "aliases": [], "timeline": [], "color": "#999"}
        m["entity"].return_value = existing
        resp = c.put("/api/entities/card-1", json={"id": "hijacked", "summary": "x"})
        assert resp.status_code == 200
        called = m["upsert_entity"].call_args[0][0]
        assert called["id"] == "card-1"  # original id preserved


class TestEntityDelete:
    def test_delete_success(self, client):
        c, m = client
        m["delete_entity"].return_value = True
        resp = c.delete("/api/entities/card-1")
        assert resp.status_code == 200
        assert resp.json() == {"deleted": "card-1"}

    def test_delete_not_found(self, client):
        c, m = client
        m["delete_entity"].return_value = False
        resp = c.delete("/api/entities/nope")
        assert resp.status_code == 404


# ── Relationship Write API ───────────────────────────────


class TestRelationshipCreate:
    def test_create_success(self, client):
        c, m = client
        m["entity"].side_effect = [
            {"id": "a", "name": "A"},
            {"id": "b", "name": "B"},
        ]
        payload = {"source_id": "a", "target_id": "b", "rel_type": "depends_on"}
        resp = c.post("/api/relationships", json=payload)
        assert resp.status_code == 201
        assert resp.json()["rel_type"] == "depends_on"

    def test_create_missing_fields(self, client):
        c, _ = client
        resp = c.post("/api/relationships", json={"source_id": "a"})
        assert resp.status_code in (400, 422)

    def test_create_source_not_found(self, client):
        c, m = client
        m["entity"].return_value = None
        payload = {"source_id": "ghost", "target_id": "b", "rel_type": "x"}
        resp = c.post("/api/relationships", json=payload)
        assert resp.status_code == 404


class TestRelationshipDelete:
    def test_delete_success(self, client):
        c, m = client
        resp = c.delete("/api/relationships/1")
        assert resp.status_code == 200
        assert resp.json() == {"deleted": 1}

    def test_delete_not_found(self, client):
        c, m = client
        m["delete_relationship"].return_value = False
        resp = c.delete("/api/relationships/999")
        assert resp.status_code == 404


# ── Pipeline Trigger API ─────────────────────────────────


class TestPipelineTrigger:
    def test_trigger_daily(self, client):
        """触发 daily pipeline 返回 started。使用 mock 避免实际启动子进程。"""
        c, _ = client
        with patch("src.api.api.subprocess.Popen") as popen_mock:
            resp = c.post("/api/pipeline/run", json={"mode": "daily"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "started"
            assert data["mode"] == "daily"

    def test_trigger_with_agent(self, client):
        c, _ = client
        with patch("src.api.api.subprocess.Popen") as popen_mock:
            resp = c.post("/api/pipeline/run", json={
                "mode": "weekly", "concept_agent": True, "trend_agent": True,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["concept_agent"] is True
            assert data["trend_agent"] is True

    def test_trigger_invalid_mode(self, client):
        c, _ = client
        resp = c.post("/api/pipeline/run", json={"mode": "hourly"})
        assert resp.status_code in (400, 422)

    def test_trigger_default_mode(self, client):
        """空 body 默认 daily"""
        c, _ = client
        with patch("src.api.api.subprocess.Popen") as popen_mock:
            resp = c.post("/api/pipeline/run")
            assert resp.status_code == 200
            assert resp.json()["mode"] == "daily"


# ── Export API ───────────────────────────────────────────


class TestExport:
    def test_export_json(self, client):
        c, m = client
        m["entities"].return_value = [{"id": "a", "name": "Test"}]
        m["articles"].return_value = [{"id": "art-1", "title": "News"}]
        m["relationships"].return_value = [{"source_id": "a", "target_id": "b"}]
        resp = c.get("/api/export")
        assert resp.status_code == 200
        data = resp.json()
        assert "exported_at" in data
        assert data["version"] == "1.0"
        assert len(data["entities"]) == 1
        assert len(data["articles"]) == 1
        assert len(data["relationships"]) == 1

    def test_export_empty(self, client):
        """空数据库也能导出。"""
        c, _ = client
        resp = c.get("/api/export")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entities"] == []
        assert data["articles"] == []

    def test_export_invalid_format(self, client):
        c, _ = client
        resp = c.get("/api/export?format=csv")
        assert resp.status_code in (400, 422)


# ── Pagination API ──────────────────────────────────────


class TestPagination:
    def test_entities_paginated(self, client):
        c, _ = client
        resp = c.get("/api/entities?page=1&page_size=10")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        assert "page" in data
        assert "has_next" in data
        assert data["page"] == 1
        assert data["page_size"] == 10

    def test_articles_paginated(self, client):
        c, _ = client
        resp = c.get("/api/articles?page=1&limit=20")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        assert "has_next" in data

    def test_entities_no_pagination_backward_compat(self, client):
        """不传 page 参数时保持原有数组格式。"""
        c, _ = client
        resp = c.get("/api/entities")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_articles_no_pagination_backward_compat(self, client):
        c, _ = client
        resp = c.get("/api/articles")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


# ── Entity Version History ──────────────────────────────


class TestEntityVersions:
    def test_versions_empty(self, client):
        c, m = client
        m["entity"].return_value = {"id": "card-1", "name": "Test"}
        m["get_entity_versions"].return_value = []
        resp = c.get("/api/entities/card-1/versions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_versions_not_found(self, client):
        c, m = client
        m["entity"].return_value = None
        resp = c.get("/api/entities/nonexistent/versions")
        assert resp.status_code == 404

    def test_versions_with_data(self, client):
        c, m = client
        m["entity"].return_value = {"id": "card-1", "name": "Test"}
        m["get_entity_versions"].return_value = [
            {"version_id": 2, "entity_id": "card-1", "version_number": 2,
             "data": {"name": "Updated"}, "created_at": "2026-07-02T00:00:00"},
            {"version_id": 1, "entity_id": "card-1", "version_number": 1,
             "data": {"name": "Original"}, "created_at": "2026-07-01T00:00:00"},
        ]
        resp = c.get("/api/entities/card-1/versions")
        assert resp.status_code == 200
        assert len(resp.json()) == 2
        assert resp.json()[0]["version_number"] == 2


# ── Migration API ───────────────────────────────────────


class TestMigrations:
    def test_get_migrations(self, client):
        c, _ = client
        resp = c.get("/api/migrations")
        assert resp.status_code == 200
        assert "applied" in resp.json()

    def test_run_migrations(self, client):
        c, m = client
        m["run_migrations"].return_value = []
        resp = c.post("/api/migrations/run")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ── Security Controls ───────────────────────────────────


class TestSecurityControls:
    def test_security_headers_present(self, client):
        c, _ = client
        resp = c.get("/api/health")
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert resp.headers["x-frame-options"] == "DENY"
        assert "frame-ancestors 'none'" in resp.headers["content-security-policy"]
        assert resp.headers["referrer-policy"] == "strict-origin-when-cross-origin"

    def test_sensitive_endpoints_require_auth_without_overrides(self):
        from src.api import app

        app.dependency_overrides.clear()
        c = TestClient(app)

        assert c.post("/api/migrations/run").status_code == 401
        assert c.get("/api/export").status_code == 401
        assert c.post(
            "/api/research",
            json={"topic": "transformer", "depth": "standard", "lang": "zh"},
        ).status_code == 401

        app.dependency_overrides.clear()
