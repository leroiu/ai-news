"""
AI Intelligence Platform — FastAPI 统一入口

启动:
  uv run uvicorn src.api.api:app --reload --port 8765

打开 http://127.0.0.1:8765 进入 Dashboard。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from src.engine.database import (
    init_db, get_entities, get_entity, get_relationships,
    get_articles, get_reports, search, get_stats, get_health,
    get_articles_by_entity, get_similar_entities,
)
from src.engine.utils import ROOT_DIR

REPORTS_DIR = ROOT_DIR / "reports"


@asynccontextmanager
async def lifespan(application: FastAPI):
    init_db()
    yield


app = FastAPI(title="AI Intelligence Platform", version="1.6", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

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


@app.get("/entity/{entity_id}")
def entity_page(entity_id: str):
    """所有实体共用的详情页，entity_id 由前端 JS 从 URL 提取"""
    return FileResponse(str(REPORTS_DIR / "entity.html"))


# ── API ──

@app.get("/api/entities")
def api_entities(type: str = Query(None)):
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
def api_articles(limit: int = 50, min_score: int = 0):
    return get_articles(limit=limit, min_score=min_score)


@app.get("/api/reports")
def api_reports(type: str = "daily", limit: int = 30):
    return get_reports(report_type=type, limit=limit)


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
def api_rebuild_embeddings(force: bool = False):
    """重建所有知识卡片的嵌入向量。POST 防止误触发。"""
    from src.engine.embeddings import rebuild_card_embeddings
    return rebuild_card_embeddings(force=force)


@app.get("/api/stats")
def api_stats():
    return get_stats()


@app.get("/api/health")
def api_health():
    """系统健康检查：DB 状态 + 最后 pipeline/collector 运行记录。"""
    return get_health()


@app.post("/api/research")
def api_research(payload: dict):
    """深度研究 — 输入话题，生成结构化研究报告。"""
    from src.research import generate_research_report
    topic = (payload.get("topic") or "").strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Topic is required")
    depth = payload.get("depth", "standard")
    if depth not in ("standard", "deep"):
        depth = "standard"
    lang = payload.get("lang", "zh")
    if lang not in ("zh", "en"):
        lang = "zh"
    return generate_research_report(topic, depth=depth, lang=lang)
