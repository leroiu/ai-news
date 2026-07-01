"""
AI Intelligence Platform — 统一数据层 (SQLite)

所有模块共享此数据库。替换之前的文件散读模式。
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .utils import log, ROOT_DIR

DB_PATH = ROOT_DIR / "data" / "platform.db"


def get_db() -> sqlite3.Connection:
    """获取数据库连接（自动创建表）。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化所有表。"""
    conn = get_db()
    conn.executescript("""
    -- 实体 (Knowledge Cards)
    CREATE TABLE IF NOT EXISTS entities (
        id          TEXT PRIMARY KEY,
        name        TEXT NOT NULL,
        type        TEXT NOT NULL,
        importance  INTEGER DEFAULT 3,
        summary     TEXT DEFAULT '',
        significance TEXT DEFAULT '',
        release_date TEXT DEFAULT '',
        company     TEXT DEFAULT '',
        tags        TEXT DEFAULT '[]',
        aliases     TEXT DEFAULT '[]',
        timeline    TEXT DEFAULT '[]',
        color       TEXT DEFAULT '#999',
        created_at  TEXT DEFAULT (datetime('now')),
        updated_at  TEXT DEFAULT (datetime('now'))
    );

    -- 关系
    CREATE TABLE IF NOT EXISTS relationships (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id   TEXT NOT NULL,
        target_id   TEXT NOT NULL,
        rel_type    TEXT NOT NULL,
        label       TEXT DEFAULT '',
        FOREIGN KEY (source_id) REFERENCES entities(id),
        FOREIGN KEY (target_id) REFERENCES entities(id),
        UNIQUE(source_id, target_id, rel_type)
    );

    -- 文章
    CREATE TABLE IF NOT EXISTS articles (
        id          TEXT PRIMARY KEY,
        title       TEXT NOT NULL,
        url         TEXT NOT NULL,
        source      TEXT DEFAULT '',
        published   TEXT DEFAULT '',
        content_raw TEXT DEFAULT '',
        categories  TEXT DEFAULT '[]',
        title_cn    TEXT DEFAULT '',
        one_liner   TEXT DEFAULT '',
        summary_points TEXT DEFAULT '[]',
        score       INTEGER DEFAULT 0,
        score_reason TEXT DEFAULT '',
        cluster_id  TEXT DEFAULT '',
        created_at  TEXT DEFAULT (datetime('now'))
    );

    -- 报告
    CREATE TABLE IF NOT EXISTS reports (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        date        TEXT NOT NULL UNIQUE,
        report_type TEXT DEFAULT 'daily',
        path        TEXT NOT NULL,
        fetched     INTEGER DEFAULT 0,
        filtered    INTEGER DEFAULT 0,
        star5       INTEGER DEFAULT 0,
        star4       INTEGER DEFAULT 0,
        star3       INTEGER DEFAULT 0,
        created_at  TEXT DEFAULT (datetime('now'))
    );

    -- 嵌入向量（语义搜索）
    CREATE TABLE IF NOT EXISTS embeddings (
        id          TEXT PRIMARY KEY,
        dims        INTEGER NOT NULL,
        vector      TEXT NOT NULL,
        updated_at  TEXT DEFAULT (datetime('now'))
    );

    -- Pipeline 运行日志
    CREATE TABLE IF NOT EXISTS pipeline_runs (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        run_type    TEXT NOT NULL DEFAULT 'daily',
        status      TEXT NOT NULL DEFAULT 'running',
        articles_total  INTEGER DEFAULT 0,
        articles_processed INTEGER DEFAULT 0,
        duration_seconds REAL DEFAULT 0,
        error_message TEXT DEFAULT '',
        started_at  TEXT DEFAULT (datetime('now')),
        ended_at    TEXT DEFAULT ''
    );

    -- Collector 运行日志
    CREATE TABLE IF NOT EXISTS collector_runs (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        status      TEXT NOT NULL DEFAULT 'success',
        fetched     INTEGER DEFAULT 0,
        new_articles INTEGER DEFAULT 0,
        duration_seconds REAL DEFAULT 0,
        error_message TEXT DEFAULT '',
        started_at  TEXT DEFAULT (datetime('now'))
    );

    -- 索引
    CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started ON pipeline_runs(started_at);
    CREATE INDEX IF NOT EXISTS idx_collector_runs_started ON collector_runs(started_at);
    CREATE INDEX IF NOT EXISTS idx_embeddings_id ON embeddings(id);
    CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
    CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source_id);
    CREATE INDEX IF NOT EXISTS idx_relationships_target ON relationships(target_id);
    CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published);
    CREATE INDEX IF NOT EXISTS idx_articles_score ON articles(score);
    CREATE INDEX IF NOT EXISTS idx_reports_date ON reports(date);
    """)
    conn.commit()
    conn.close()
    log.debug(f"数据库已初始化: {DB_PATH}")


# ============================================================
# Entity CRUD
# ============================================================

def upsert_entity(entity: dict):
    """插入或更新实体。"""
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO entities (id, name, type, importance, summary, significance,
              release_date, company, tags, aliases, timeline, color, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name, type=excluded.type, importance=excluded.importance,
            summary=excluded.summary, significance=excluded.significance,
            release_date=excluded.release_date, company=excluded.company,
            tags=excluded.tags, aliases=excluded.aliases, timeline=excluded.timeline,
            color=excluded.color, updated_at=excluded.updated_at
    """, (
        entity["id"], entity["name"], entity["type"], entity.get("importance", 3),
        entity.get("summary", ""), entity.get("significance", ""),
        entity.get("release_date", ""), entity.get("company", ""),
        json.dumps(entity.get("tags", []), default=str), json.dumps(entity.get("aliases", []), default=str),
        json.dumps(entity.get("timeline", []), default=str), entity.get("color", "#999"), now,
    ))
    conn.commit()
    conn.close()


def get_entities(entity_type: Optional[str] = None) -> list[dict]:
    """查询实体列表。"""
    conn = get_db()
    if entity_type:
        rows = conn.execute("SELECT * FROM entities WHERE type=? ORDER BY importance DESC", (entity_type,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM entities ORDER BY type, importance DESC").fetchall()
    conn.close()
    return [_row_to_entity(r) for r in rows]


def get_entity(entity_id: str) -> Optional[dict]:
    conn = get_db()
    r = conn.execute("SELECT * FROM entities WHERE id=?", (entity_id,)).fetchone()
    conn.close()
    return _row_to_entity(r) if r else None


def _row_to_entity(r: sqlite3.Row) -> dict:
    d = dict(r)
    for f in ("tags", "aliases", "timeline"):
        try: d[f] = json.loads(d.get(f, "[]"))
        except (json.JSONDecodeError, TypeError): d[f] = []
    return d


# ============================================================
# Relationship CRUD
# ============================================================

def upsert_relationship(source: str, target: str, rel_type: str, label: str = ""):
    conn = get_db()
    conn.execute("""
        INSERT OR IGNORE INTO relationships (source_id, target_id, rel_type, label)
        VALUES (?,?,?,?)
    """, (source, target, rel_type, label))
    conn.commit()
    conn.close()


def get_relationships(entity_id: Optional[str] = None) -> list[dict]:
    conn = get_db()
    if entity_id:
        rows = conn.execute(
            "SELECT * FROM relationships WHERE source_id=? OR target_id=?",
            (entity_id, entity_id)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM relationships").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
# Article CRUD
# ============================================================

def insert_articles(articles: list[dict]):
    """批量插入文章。"""
    conn = get_db()
    for a in articles:
        conn.execute("""
            INSERT OR REPLACE INTO articles (id, title, url, source, published, content_raw,
                categories, title_cn, one_liner, summary_points, score, score_reason, cluster_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            a["id"], a["title"], a["url"], a.get("source", ""),
            a.get("published", ""), a.get("content_raw", ""),
            json.dumps(a.get("categories", []), default=str), a.get("title_cn", ""),
            a.get("one_liner", ""), json.dumps(a.get("summary_points", []), default=str),
            a.get("score", 0), a.get("score_reason", ""), a.get("cluster_id", ""),
        ))
    conn.commit()
    conn.close()


def get_articles(limit: int = 50, min_score: int = 0, since: Optional[str] = None) -> list[dict]:
    conn = get_db()
    q = "SELECT * FROM articles WHERE score >= ?"
    params = [min_score]
    if since:
        q += " AND published >= ?"
        params.append(since)
    q += " ORDER BY score DESC, published DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [_row_to_article(r) for r in rows]


def get_articles_by_entity(entity_id: str, entity_name: str = "",
                           aliases: list[str] | None = None,
                           limit: int = 20) -> list[dict]:
    """Find articles related to an entity by name/alias match in title/categories/content."""
    terms = [entity_id, entity_name] + (aliases or [])
    conditions = []
    params = []
    for t in terms:
        if not t:
            continue
        p = f"%{t}%"
        conditions.append("(title LIKE ? OR title_cn LIKE ? OR categories LIKE ? OR one_liner LIKE ?)")
        params.extend([p, p, p, p])
    if not conditions:
        return []
    where = " OR ".join(conditions)
    conn = get_db()
    rows = conn.execute(
        f"SELECT * FROM articles WHERE {where} ORDER BY published DESC LIMIT ?",
        params + [limit]
    ).fetchall()
    conn.close()
    return [_row_to_article(r) for r in rows]


def get_similar_entities(entity_id: str, limit: int = 6) -> list[dict]:
    """Find similar entities using embedding cosine similarity."""
    try:
        from .embeddings import get_embedding, get_all_embeddings, cosine_similarity
    except ImportError:
        return []
    target_emb = get_embedding(entity_id)
    if not target_emb:
        return []
    all_embs = get_all_embeddings()
    scores = []
    for eid, emb in all_embs.items():
        if eid == entity_id:
            continue
        scores.append((eid, cosine_similarity(target_emb, emb)))
    scores.sort(key=lambda x: x[1], reverse=True)
    conn = get_db()
    result = []
    for eid, score in scores[:limit]:
        row = conn.execute("SELECT * FROM entities WHERE id = ?", (eid,)).fetchone()
        if row:
            d = _row_to_entity(row)
            d["similarity"] = round(score, 3)
            result.append(d)
    conn.close()
    return result


def _row_to_article(r: sqlite3.Row) -> dict:
    d = dict(r)
    for f in ("categories", "summary_points"):
        try: d[f] = json.loads(d.get(f, "[]"))
        except (json.JSONDecodeError, TypeError): d[f] = []
    return d


# ============================================================
# Report CRUD
# ============================================================

def insert_report(date: str, report_type: str, path: str, fetched: int = 0,
                  filtered: int = 0, star5: int = 0, star4: int = 0, star3: int = 0):
    conn = get_db()
    conn.execute("""
        INSERT OR REPLACE INTO reports (date, report_type, path, fetched, filtered, star5, star4, star3)
        VALUES (?,?,?,?,?,?,?,?)
    """, (date, report_type, path, fetched, filtered, star5, star4, star3))
    conn.commit()
    conn.close()


def get_reports(report_type: str = "daily", limit: int = 30) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM reports WHERE report_type=? ORDER BY date DESC LIMIT ?",
        (report_type, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
# Search
# ============================================================

def search(query: str, limit: int = 20, semantic: bool = False) -> dict:
    """全文搜索实体 + 文章。semantic=True 时启用混合检索（关键词+语义）。"""
    if semantic:
        from .embeddings import search_hybrid
        return search_hybrid(query, limit=limit)

    conn = get_db()
    q = f"%{query}%"
    entities = conn.execute(
        "SELECT id, name, type, summary, importance, color FROM entities "
        "WHERE name LIKE ? OR summary LIKE ? LIMIT ?",
        (q, q, limit)).fetchall()
    articles = conn.execute(
        "SELECT id, title, source, title_cn, one_liner, score, published FROM articles "
        "WHERE title LIKE ? OR title_cn LIKE ? OR one_liner LIKE ? LIMIT ?",
        (q, q, q, limit)).fetchall()
    conn.close()
    return {
        "entities": [dict(r) for r in entities],
        "articles": [dict(r) for r in articles],
    }


# ============================================================
# 统计
# ============================================================

def get_stats() -> dict:
    conn = get_db()
    entity_count = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    article_count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    rel_count = conn.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
    by_type = {}
    for r in conn.execute("SELECT type, COUNT(*) as cnt FROM entities GROUP BY type").fetchall():
        by_type[r["type"]] = r["cnt"]
    conn.close()
    return {
        "entities": entity_count,
        "articles": article_count,
        "relationships": rel_count,
        "by_type": by_type,
    }


# ============================================================
# Pipeline / Collector Run Tracking
# ============================================================

def start_pipeline_run(run_type: str = "daily", articles_total: int = 0) -> int:
    """开始一次 pipeline 运行，返回 run_id。"""
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO pipeline_runs (run_type, status, articles_total) VALUES (?, 'running', ?)",
        (run_type, articles_total)
    )
    conn.commit()
    run_id = cur.lastrowid
    conn.close()
    return run_id


def finish_pipeline_run(run_id: int, status: str = "success",
                        articles_processed: int = 0, duration: float = 0,
                        error: str = ""):
    """结束一次 pipeline 运行。"""
    conn = get_db()
    conn.execute("""
        UPDATE pipeline_runs
        SET status=?, articles_processed=?, duration_seconds=?,
            error_message=?, ended_at=datetime('now')
        WHERE id=?
    """, (status, articles_processed, duration, error, run_id))
    conn.commit()
    conn.close()


def log_collector_run(fetched: int = 0, new_articles: int = 0,
                      duration: float = 0, error: str = ""):
    """记录一次 collector 运行。"""
    status = "error" if error else "success"
    conn = get_db()
    conn.execute("""
        INSERT INTO collector_runs (status, fetched, new_articles, duration_seconds, error_message)
        VALUES (?, ?, ?, ?, ?)
    """, (status, fetched, new_articles, duration, error))
    conn.commit()
    conn.close()


def get_entity_neighbors(entity_id: str, max_depth: int = 1) -> list[dict]:
    """遍历关系图谱，返回与指定实体关联的邻居实体及关系信息。

    返回 [{"entity": {...}, "relation": "uses", "direction": "out", "depth": 1}, ...]
    depth=1 为直接邻居，depth=2 包含邻居的邻居。
    """
    conn = get_db()
    visited: set[str] = {entity_id}
    current_layer = {entity_id}
    neighbors: list[dict] = []

    for d in range(1, max_depth + 1):
        next_layer: set[str] = set()
        for eid in current_layer:
            rows = conn.execute(
                "SELECT source_id, target_id, rel_type, label FROM relationships "
                "WHERE source_id=? OR target_id=?",
                (eid, eid)
            ).fetchall()
            for r in rows:
                src, tgt = r["source_id"], r["target_id"]
                neighbor_id = tgt if src == eid else src
                direction = "out" if src == eid else "in"
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    next_layer.add(neighbor_id)
                    entity_row = conn.execute(
                        "SELECT * FROM entities WHERE id=?", (neighbor_id,)
                    ).fetchone()
                    if entity_row:
                        neighbors.append({
                            "entity": _row_to_entity(entity_row),
                            "relation": r["rel_type"],
                            "label": r["label"],
                            "direction": direction,
                            "depth": d,
                            "via": eid if d > 1 else None,
                        })
        current_layer = next_layer
        if not current_layer:
            break

    conn.close()
    return neighbors


def get_entity_relation_graph(entity_ids: list[str]) -> dict:
    """获取多个实体之间的子图关系。

    返回 {"relations": [...], "entities": [...]}
    """
    if not entity_ids:
        return {"relations": [], "entities": []}
    conn = get_db()
    placeholders = ",".join("?" for _ in entity_ids)
    relations = conn.execute(
        f"SELECT * FROM relationships WHERE source_id IN ({placeholders}) AND target_id IN ({placeholders})",
        entity_ids * 2
    ).fetchall()
    all_ids = set(entity_ids)
    for r in relations:
        all_ids.add(r["source_id"])
        all_ids.add(r["target_id"])
    entities = []
    for eid in all_ids:
        row = conn.execute("SELECT * FROM entities WHERE id=?", (eid,)).fetchone()
        if row:
            entities.append(_row_to_entity(row))
    conn.close()
    return {
        "relations": [dict(r) for r in relations],
        "entities": entities,
    }


def verify_entity_ids(entity_ids: list[str]) -> dict[str, dict | None]:
    """批量验证实体 ID 是否存在，返回 {id: entity_dict | None}。"""
    if not entity_ids:
        return {}
    conn = get_db()
    placeholders = ",".join("?" for _ in entity_ids)
    rows = conn.execute(
        f"SELECT * FROM entities WHERE id IN ({placeholders})",
        entity_ids
    ).fetchall()
    conn.close()
    found = {r["id"]: _row_to_entity(r) for r in rows}
    return {eid: found.get(eid) for eid in entity_ids}


def get_pipeline_runs(limit: int = 10) -> list[dict]:
    """获取最近的 pipeline 运行记录。"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_pipeline_run(run_id: int, articles_processed: int = 0,
                         error_message: str = ""):
    """增量更新 pipeline 运行状态（用于长时间运行的 pipeline）。"""
    conn = get_db()
    if error_message:
        conn.execute(
            "UPDATE pipeline_runs SET articles_processed=?, error_message=? WHERE id=?",
            (articles_processed, error_message, run_id)
        )
    else:
        conn.execute(
            "UPDATE pipeline_runs SET articles_processed=? WHERE id=?",
            (articles_processed, run_id)
        )
    conn.commit()
    conn.close()


def get_health() -> dict:
    """健康检查：DB 状态 + 最后运行时间 + 基本统计。"""
    try:
        conn = get_db()
        # 基本统计
        entities = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        reports = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]

        # 最后一次 pipeline 运行
        last_pipeline = conn.execute("""
            SELECT run_type, status, articles_total, articles_processed,
                   duration_seconds, error_message, started_at, ended_at
            FROM pipeline_runs ORDER BY id DESC LIMIT 1
        """).fetchone()

        # 最后一次 collector 运行
        last_collector = conn.execute("""
            SELECT status, fetched, new_articles, duration_seconds, started_at
            FROM collector_runs ORDER BY id DESC LIMIT 1
        """).fetchone()

        # 最近 24 小时 pipeline 成功率
        success_rate = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as ok
            FROM pipeline_runs
            WHERE started_at > datetime('now', '-1 day')
        """).fetchone()

        conn.close()

        return {
            "status": "ok",
            "db": {"entities": entities, "articles": articles, "reports": reports},
            "last_pipeline": dict(last_pipeline) if last_pipeline else None,
            "last_collector": dict(last_collector) if last_collector else None,
            "recent_success_rate": {
                "total": success_rate["total"],
                "success": success_rate["ok"],
            } if success_rate["total"] > 0 else None,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
