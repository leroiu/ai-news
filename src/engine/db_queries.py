"""
报告 CRUD + 全文搜索 + 统计查询。

从 database.py 拆分出来。
"""

from typing import Optional

from .db_core import get_db


# ═══════════════════════════════════════════════════════════════
# Report CRUD
# ═══════════════════════════════════════════════════════════════

def insert_report(date: str, report_type: str, path: str, fetched: int = 0,
                  filtered: int = 0, star5: int = 0, star4: int = 0,
                  star3: int = 0):
    """插入或更新报告记录。"""
    conn = get_db()
    conn.execute("""
        INSERT OR REPLACE INTO reports (date, report_type, path, fetched,
            filtered, star5, star4, star3)
        VALUES (?,?,?,?,?,?,?,?)
    """, (date, report_type, path, fetched, filtered, star5, star4, star3))
    conn.commit()
    conn.close()


def get_reports(report_type: str = "daily", limit: int = 30) -> list[dict]:
    """查询报告列表。"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM reports WHERE report_type=? ORDER BY date DESC LIMIT ?",
        (report_type, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════
# Search
# ═══════════════════════════════════════════════════════════════

def search(query: str, limit: int = 20, semantic: bool = False) -> dict:
    """全文搜索实体 + 文章。优先 FTS5 + bm25 排序，fallback 到 LIKE。semantic=True 时启用混合检索。"""
    if semantic:
        from .embeddings import search_hybrid
        return search_hybrid(query, limit=limit)

    conn = get_db()

    # ── FTS5 搜索（实体） ──
    entities = []
    try:
        # FTS5 需要转义特殊字符
        escaped = query.replace('"', '""')
        rows = conn.execute(
            "SELECT e.id, e.name, e.type, e.summary, e.importance, e.color "
            "FROM entities_fts f JOIN entities e ON e.id = f.entity_id "
            "WHERE entities_fts MATCH ? ORDER BY bm25(entities_fts) LIMIT ?",
            (f'"{escaped}"', limit)
        ).fetchall()
        entities = [dict(r) for r in rows]
    except Exception:
        entities = []

    # FTS5 无结果时 fallback 到 LIKE
    if not entities:
        q = f"%{query}%"
        rows = conn.execute(
            "SELECT id, name, type, summary, importance, color FROM entities "
            "WHERE name LIKE ? OR summary LIKE ? LIMIT ?",
            (q, q, limit)
        ).fetchall()
        entities = [dict(r) for r in rows]

    # ── FTS5 搜索（文章） ──
    articles = []
    try:
        escaped = query.replace('"', '""')
        rows = conn.execute(
            "SELECT a.id, a.title, a.source, a.title_cn, a.one_liner, a.score, a.published "
            "FROM articles_fts f JOIN articles a ON a.id = f.article_id "
            "WHERE articles_fts MATCH ? ORDER BY bm25(articles_fts) LIMIT ?",
            (f'"{escaped}"', limit)
        ).fetchall()
        articles = [dict(r) for r in rows]
    except Exception:
        articles = []

    if not articles:
        q = f"%{query}%"
        rows = conn.execute(
            "SELECT id, title, source, title_cn, one_liner, score, published "
            "FROM articles "
            "WHERE title LIKE ? OR title_cn LIKE ? OR one_liner LIKE ? LIMIT ?",
            (q, q, q, limit)
        ).fetchall()
        articles = [dict(r) for r in rows]

    conn.close()
    return {
        "entities": entities,
        "articles": articles,
    }


# ═══════════════════════════════════════════════════════════════
# Stats
# ═══════════════════════════════════════════════════════════════

def get_stats() -> dict:
    """获取平台基本统计。"""
    conn = get_db()
    entity_count = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    article_count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    rel_count = conn.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
    by_type = {}
    for r in conn.execute(
        "SELECT type, COUNT(*) as cnt FROM entities GROUP BY type"
    ).fetchall():
        by_type[r["type"]] = r["cnt"]
    conn.close()
    return {
        "entities": entity_count,
        "articles": article_count,
        "relationships": rel_count,
        "by_type": by_type,
    }
