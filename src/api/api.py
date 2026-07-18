"""
AI Intelligence Platform — FastAPI 统一入口

启动:
  uv run uvicorn src.api.api:app --reload --port 8765

打开 http://127.0.0.1:8765 进入 Dashboard。
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from src.engine.database import (
    init_db, get_entities, get_entity, get_relationships,
    get_articles, get_article, get_reports, search, get_stats, get_health,
    get_articles_by_entity, get_similar_entities,
    upsert_entity, delete_entity, upsert_relationship, delete_relationship,
    save_entity_version, get_entity_versions,
    get_entities_paginated, get_articles_paginated,
    get_entities_cursor, get_articles_cursor,
    run_migrations,
)
from src.engine.db_core import get_db
from src.engine.utils import ROOT_DIR
from src.interfaces.schemas import (
    EntityCreate, EntityUpdate, RelationshipCreate,
    PipelineRunRequest, ResearchRequest,
)
from src.api.auth import router as auth_router
from src.api.middleware import (
    RateLimitMiddleware, register_error_handlers,
    get_current_user, get_optional_user, require_admin,
)

REPORTS_DIR = ROOT_DIR / "reports"


@asynccontextmanager
async def lifespan(application: FastAPI):
    init_db()
    # 初次启动时重建 FTS5 索引
    try:
        from src.engine.db_core import rebuild_fts
        rebuild_fts()
    except Exception:
        pass
    yield


app = FastAPI(title="AI Intelligence Platform", version="1.6", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Rate limit + 统一错误处理
app.add_middleware(RateLimitMiddleware, max_requests=120, window_seconds=60)
register_error_handlers(app)

# Auth router
app.include_router(auth_router)

# 静态文件 — reports files (日报、周报等 .md 文件)
if REPORTS_DIR.exists():
    app.mount("/report-files", StaticFiles(directory=str(REPORTS_DIR)), name="report-files")


# ── 页面入口 ──

@app.get("/")
def home():
    """Dashboard 首页"""
    return FileResponse(str(REPORTS_DIR / "dashboard.html"))


@app.get("/library")
def library_page():
    return FileResponse(str(REPORTS_DIR / "library.html"))


@app.get("/graph")
def graph_page():
    return FileResponse(str(REPORTS_DIR / "knowledge-graph.html"))


@app.get("/graph3d")
def graph_3d_page():
    return FileResponse(str(REPORTS_DIR / "knowledge-graph-3d.html"))


@app.get("/timeline")
def timeline_page():
    return FileResponse(str(REPORTS_DIR / "timeline.html"))


@app.get("/events")
def events_page():
    return FileResponse(str(REPORTS_DIR / "events.html"))


@app.get("/reports")
def reports_page():
    return FileResponse(str(REPORTS_DIR / "reports.html"))


@app.get("/research")
def research_page():
    """深度研究助手页面"""
    return FileResponse(str(REPORTS_DIR / "research.html"))


@app.get("/my")
def my_page():
    """我的收藏与个人沉淀入口"""
    return FileResponse(str(REPORTS_DIR / "my.html"))


@app.get("/login")
def login_page():
    """登录/注册页面"""
    return FileResponse(str(REPORTS_DIR / "auth.html"))


@app.get("/register")
def register_page():
    """注册页面（与登录同一页面，tab 切换）"""
    return FileResponse(str(REPORTS_DIR / "auth.html"))


@app.get("/entity/{entity_id}")
def entity_page(entity_id: str):
    """所有实体共用的详情页，entity_id 由前端 JS 从 URL 提取"""
    return FileResponse(str(REPORTS_DIR / "entity.html"))


@app.get("/article/{article_id}")
def article_page(article_id: str):
    return FileResponse(str(REPORTS_DIR / "article.html"))


@app.get("/report/{filename}")
def report_reader_page(filename: str):
    return FileResponse(str(REPORTS_DIR / "report-reader.html"))


# ── Auth override ──

@app.get("/api/auth/me")
def api_auth_me(user: dict = Depends(get_current_user)):
    """获取当前登录用户信息。"""
    return {
        "id": user["id"], "username": user["username"],
        "email": user.get("email", ""), "role": user["role"],
        "created_at": user.get("created_at", ""),
    }


# ── Favorites API ──

class FavoriteToggle(BaseModel):
    item_type: str
    item_id: str


@app.get("/api/favorites")
def api_get_favorites(user: dict = Depends(get_current_user)):
    conn = get_db()
    rows = conn.execute(
        "SELECT item_type, item_id, created_at FROM favorites WHERE user_id=? ORDER BY created_at DESC",
        (user["id"],)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/favorites", status_code=201)
def api_add_favorite(payload: FavoriteToggle, user: dict = Depends(get_current_user)):
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO favorites (user_id, item_type, item_id) VALUES (?,?,?)",
        (user["id"], payload.item_type, payload.item_id),
    )
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.delete("/api/favorites")
def api_remove_favorite(payload: FavoriteToggle, user: dict = Depends(get_current_user)):
    conn = get_db()
    conn.execute(
        "DELETE FROM favorites WHERE user_id=? AND item_type=? AND item_id=?",
        (user["id"], payload.item_type, payload.item_id),
    )
    conn.commit()
    conn.close()
    return {"status": "ok"}


# ── Reading History API ──

class ReadingRecord(BaseModel):
    article_id: str


@app.get("/api/reading-history")
def api_get_history(limit: int = Query(50), user: dict = Depends(get_current_user)):
    conn = get_db()
    rows = conn.execute(
        "SELECT article_id, read_at FROM reading_history WHERE user_id=? ORDER BY read_at DESC LIMIT ?",
        (user["id"], limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/reading-history", status_code=201)
def api_record_read(payload: ReadingRecord, user: dict = Depends(get_current_user)):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO reading_history (user_id, article_id, read_at) VALUES (?,?,datetime('now'))",
        (user["id"], payload.article_id),
    )
    conn.commit()
    conn.close()
    return {"status": "ok"}


# ── API ──

@app.get("/api/entities")
def api_entities(type: str = Query(None), page: int = Query(0), page_size: int = Query(0),
                 cursor: str = Query(None), limit: int = Query(50)):
    """获取实体列表。支持 page 分页或 cursor 分页。cursor 参数优先。"""
    if cursor:
        return get_entities_cursor(type or None, limit=limit, cursor=cursor)
    if page > 0:
        return get_entities_paginated(type or None, page=page, page_size=page_size or 50)
    return get_entities(type or None)


@app.get("/api/entities/{entity_id}")
def api_entity(entity_id: str):
    e = get_entity(entity_id)
    if not e:
        raise HTTPException(status_code=404, detail="Entity not found")
    e["relationships"] = get_relationships(entity_id)
    return e


@app.get("/api/entities/{entity_id}/articles")
def api_entity_articles(entity_id: str, limit: int = Query(20)):
    """Get articles related to a specific entity."""
    e = get_entity(entity_id)
    if not e:
        raise HTTPException(status_code=404, detail="Entity not found")
    aliases = e.get("aliases", [])
    if isinstance(aliases, str):
        try:
            aliases = json.loads(aliases)
        except (json.JSONDecodeError, TypeError):
            aliases = []
    return get_articles_by_entity(
        entity_id, e.get("name", ""), aliases, limit=limit
    )


@app.get("/api/entities/{entity_id}/similar")
def api_entity_similar(entity_id: str, limit: int = Query(6)):
    """Get similar entities based on embedding similarity."""
    e = get_entity(entity_id)
    if not e:
        raise HTTPException(status_code=404, detail="Entity not found")
    return get_similar_entities(entity_id, limit=limit)


@app.get("/api/relationships")
def api_relationships(entity_id: str = Query(None)):
    return get_relationships(entity_id or None)


@app.get("/api/articles")
def api_articles(limit: int = 50, min_score: int = 0, page: int = Query(0),
                 cursor: str = Query(None)):
    """获取文章列表。支持 page 分页或 cursor 分页。cursor 参数优先。"""
    if cursor:
        return get_articles_cursor(limit=limit, min_score=min_score, cursor=cursor)
    if page > 0:
        return get_articles_paginated(limit=limit, min_score=min_score, page=page, page_size=limit or 50)
    return get_articles(limit=limit, min_score=min_score)


@app.get("/api/articles/{article_id}")
def api_article(article_id: str):
    article = get_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    from src.engine.provenance import enrich_article
    return enrich_article(article, get_entities())


@app.get("/api/reports")
def api_reports(type: str = "daily", limit: int = 30):
    return get_reports(report_type=type, limit=limit)


@app.get("/api/report-content/{filename}")
def api_report_content(filename: str):
    """安全读取 reports 根目录内的 Markdown 报告。"""
    if Path(filename).name != filename or not filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="Invalid report filename")
    path = (REPORTS_DIR / filename).resolve()
    if path.parent != REPORTS_DIR.resolve() or not path.is_file():
        raise HTTPException(status_code=404, detail="Report not found")
    return {"filename": filename, "content": path.read_text(encoding="utf-8")}


@app.get("/api/search")
def api_search(q: str = Query(...), limit: int = 20, semantic: bool = False):
    return search(q, limit=limit, semantic=semantic)


@app.get("/api/embeddings/status")
def api_embeddings_status():
    """返回嵌入向量就绪状态。"""
    from src.engine.embeddings import get_all_embeddings
    vecs = get_all_embeddings()
    entities = get_entities()
    return {
        "embedded": len(vecs),
        "total_entities": len(entities),
        "ready": len(vecs) == len(entities) and len(vecs) > 0,
    }


@app.post("/api/embeddings/rebuild")
def api_rebuild_embeddings(force: bool = False,
                            admin: dict = Depends(require_admin)):
    """重建所有知识卡片的嵌入向量。POST 防止误触发。"""
    from src.engine.embeddings import rebuild_card_embeddings
    return rebuild_card_embeddings(force=force)


@app.get("/api/stats")
def api_stats():
    return get_stats()


@app.get("/api/health")
def api_health():
    """系统健康检查：DB 状态 + 最后 pipeline/collector 运行记录。"""
    health = get_health()
    # 部署系统可注入这两个非敏感标识，供 post-deploy 门禁确认目标环境和版本。
    # 未配置时显式返回 unknown，避免把“能访问”误判成“部署了预期版本”。
    health["environment"] = os.environ.get("AI_NEWS_ENVIRONMENT", "unknown")
    health["release"] = os.environ.get("AI_NEWS_RELEASE_SHA", "unknown")
    return health


@app.post("/api/research")
def api_research(payload: ResearchRequest):
    """深度研究 — 输入话题，生成结构化研究报告。"""
    use_agent = payload.agent

    if use_agent:
        from src.engine.research_agent import research_agent
        return research_agent(payload.topic, depth=payload.depth, lang=payload.lang)

    from src.research import generate_research_report
    return generate_research_report(payload.topic, depth=payload.depth, lang=payload.lang)


# ── Entity Version History API ──

@app.get("/api/entities/{entity_id}/versions")
def api_entity_versions(entity_id: str):
    """获取知识卡片的历史版本列表。"""
    e = get_entity(entity_id)
    if not e:
        raise HTTPException(status_code=404, detail="Entity not found")
    return get_entity_versions(entity_id)


# ── Migration API ──

@app.get("/api/migrations")
def api_get_migrations():
    """列出已应用的数据库迁移。"""
    from src.engine.database import get_applied_migrations
    return {"applied": sorted(get_applied_migrations())}


@app.post("/api/migrations/run")
def api_run_migrations():
    """运行所有待执行的数据库迁移。"""
    new = run_migrations()
    return {"status": "ok", "applied": new, "count": len(new)}


# ── Entity Write API ──

@app.post("/api/entities", status_code=201)
def api_create_entity(payload: EntityCreate, admin: dict = Depends(require_admin)):
    """创建新知识卡片。id 和 name 必填。"""
    existing = get_entity(payload.id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Entity '{payload.id}' already exists")

    entity = {
        "id": payload.id,
        "name": payload.name,
        "type": payload.type,
        "importance": payload.importance,
        "summary": payload.summary,
        "significance": payload.significance,
        "release_date": payload.release_date,
        "company": payload.company,
        "tags": payload.tags,
        "aliases": payload.aliases,
        "timeline": payload.timeline,
        "color": payload.color,
    }
    upsert_entity(entity)
    return get_entity(payload.id)


@app.put("/api/entities/{entity_id}")
def api_update_entity(entity_id: str, payload: EntityUpdate,
                      admin: dict = Depends(require_admin)):
    """更新知识卡片。只更新传入的字段。自动保存历史版本。"""
    existing = get_entity(entity_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Entity not found")

    # 保存历史版本
    changed = {k: v for k, v in payload.model_dump(exclude_none=True).items() if k != "id"}
    if changed:
        save_entity_version(entity_id, existing, changed_fields=", ".join(changed.keys()))

    update_data = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    update_data.pop("id", None)
    updated = {**existing, **update_data, "id": entity_id}
    upsert_entity(updated)
    return get_entity(entity_id)


@app.delete("/api/entities/{entity_id}")
def api_delete_entity(entity_id: str, admin: dict = Depends(require_admin)):
    """删除知识卡片及其关联关系和嵌入向量。"""
    if not delete_entity(entity_id):
        raise HTTPException(status_code=404, detail="Entity not found")
    return {"deleted": entity_id}


# ── Relationship Write API ──

@app.post("/api/relationships", status_code=201)
def api_create_relationship(payload: RelationshipCreate,
                             admin: dict = Depends(require_admin)):
    """创建实体间关系。source_id, target_id, rel_type 必填。"""
    if not get_entity(payload.source_id):
        raise HTTPException(status_code=404, detail=f"Source entity '{payload.source_id}' not found")
    if not get_entity(payload.target_id):
        raise HTTPException(status_code=404, detail=f"Target entity '{payload.target_id}' not found")

    upsert_relationship(payload.source_id, payload.target_id, payload.rel_type, payload.label)
    return {"source_id": payload.source_id, "target_id": payload.target_id,
            "rel_type": payload.rel_type, "label": payload.label}


@app.delete("/api/relationships/{rel_id}")
def api_delete_relationship(rel_id: int, admin: dict = Depends(require_admin)):
    """删除关系。"""
    if not delete_relationship(rel_id):
        raise HTTPException(status_code=404, detail="Relationship not found")
    return {"deleted": rel_id}


# ── Pipeline Trigger API ──

@app.post("/api/pipeline/run")
def api_run_pipeline(payload: PipelineRunRequest = PipelineRunRequest(),
                     admin: dict = Depends(require_admin)):
    """手动触发流水线。支持 daily/weekly/monthly 模式，可选 Agent 模式。"""
    concept_agent = payload.concept_agent or payload.agent
    trend_agent = payload.trend_agent or payload.agent

    env = os.environ.copy()
    env["CONCEPT_AGENT"] = "1" if concept_agent else "0"
    env["TREND_AGENT"] = "1" if trend_agent else "0"

    args = [sys.executable, "-m", "pipeline"]
    if payload.mode == "weekly":
        args.append("--weekly")
    elif payload.mode == "monthly":
        args.append("--monthly")

    # 后台启动流水线，立即返回
    project_dir = str(Path(__file__).resolve().parent.parent.parent)
    try:
        subprocess.Popen(args, cwd=project_dir, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {
            "status": "started",
            "mode": payload.mode,
            "concept_agent": concept_agent,
            "trend_agent": trend_agent,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start pipeline: {e}")


# ── Data Export API ──

@app.get("/api/export")
def api_export(format: str = "json"):
    """导出全部数据（entities, articles, relationships）。format=json (准备 yaml/csv 扩展)。"""
    if format not in ("json", "yaml"):
        raise HTTPException(status_code=400, detail="format must be json or yaml")

    entities = get_entities()
    articles = get_articles(limit=10000)
    relationships = get_relationships()

    export = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "version": "1.0",
        "entities": entities,
        "articles": articles,
        "relationships": relationships,
    }

    if format == "yaml":
        import yaml
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(
            yaml.dump(export, allow_unicode=True, default_flow_style=False),
            media_type="application/x-yaml",
            headers={"Content-Disposition": "attachment; filename=ai-news-export.yaml"},
        )

    return export
