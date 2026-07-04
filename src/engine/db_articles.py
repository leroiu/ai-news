"""
Article CRUD + 实体关联搜索 + 相似实体 + 文章分页。

从 database.py 拆分出来。
"""

import base64
import json
from typing import Optional

from .db_core import get_db, _row_to_article, _row_to_entity, rebuild_fts


# ═══════════════════════════════════════════════════════════════
# Article CRUD
# ═══════════════════════════════════════════════════════════════

def insert_articles(articles: list[dict]):
    """批量插入文章。"""
    conn = get_db()
    for a in articles:
        conn.execute("""
            INSERT OR REPLACE INTO articles (id, title, url, source, published,
                content_raw, categories, title_cn, one_liner, summary_points,
                score, score_reason, cluster_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            a["id"], a["title"], a["url"], a.get("source", ""),
            a.get("published", ""), a.get("content_raw", ""),
            json.dumps(a.get("categories", []), default=str),
            a.get("title_cn", ""),
            a.get("one_liner", ""),
            json.dumps(a.get("summary_points", []), default=str),
            a.get("score", 0), a.get("score_reason", ""), a.get("cluster_id", ""),
        ))
    conn.commit()
    conn.close()
    # 重建 FTS5 索引
    try:
        rebuild_fts()
    except Exception:
        pass


def get_articles(limit: int = 50, min_score: int = 0,
                 since: Optional[str] = None) -> list[dict]:
    """查询文章列表，按评分+发布时间降序。"""
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


def get_article(article_id: str) -> Optional[dict]:
    """按稳定 ID 返回单篇文章。"""
    conn = get_db()
    row = conn.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
    conn.close()
    return _row_to_article(row) if row else None


def get_articles_by_entity(entity_id: str, entity_name: str = "",
                           aliases: list[str] | None = None,
                           limit: int = 20) -> list[dict]:
    """按实体名称/别名在文章标题、分类、摘要中模糊搜索。"""
    terms = [entity_id, entity_name] + (aliases or [])
    conditions = []
    params = []
    for t in terms:
        if not t:
            continue
        p = f"%{t}%"
        conditions.append(
            "(title LIKE ? OR title_cn LIKE ? OR categories LIKE ? OR one_liner LIKE ?)"
        )
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
    """使用嵌入向量余弦相似度查找相似实体。"""
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
        row = conn.execute(
            "SELECT * FROM entities WHERE id = ?", (eid,)
        ).fetchone()
        if row:
            d = _row_to_entity(row)
            d["similarity"] = round(score, 3)
            result.append(d)
    conn.close()
    return result


# ═══════════════════════════════════════════════════════════════
# Article Pagination
# ═══════════════════════════════════════════════════════════════

def get_articles_paginated(limit: int = 50, min_score: int = 0, page: int = 1,
                           page_size: int = 50,
                           since: Optional[str] = None) -> dict:
    """分页获取文章列表。"""
    conn = get_db()
    q = "SELECT COUNT(*) FROM articles WHERE score >= ?"
    params = [min_score]
    if since:
        q += " AND published >= ?"
        params.append(since)
    total = conn.execute(q, params).fetchone()[0]

    q2 = "SELECT * FROM articles WHERE score >= ?"
    if since:
        q2 += " AND published >= ?"
    q2 += " ORDER BY score DESC, published DESC LIMIT ? OFFSET ?"
    rows = conn.execute(q2, params + [page_size, (page - 1) * page_size]).fetchall()
    conn.close()
    return {
        "data": [_row_to_article(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": (page * page_size) < total,
    }


# ═══════════════════════════════════════════════════════════════
# Cursor Pagination
# ═══════════════════════════════════════════════════════════════

def _encode_cursor(values: dict) -> str:
    """将游标值编码为 opaque token。"""
    return base64.urlsafe_b64encode(
        json.dumps(values, sort_keys=True).encode()
    ).decode().rstrip("=")


def _decode_cursor(cursor: str) -> dict | None:
    """解码 opaque cursor token。"""
    try:
        # 补齐 base64 padding
        padded = cursor + "=" * (4 - len(cursor) % 4)
        return json.loads(base64.urlsafe_b64decode(padded).decode())
    except Exception:
        return None


def get_articles_cursor(limit: int = 50, min_score: int = 0,
                         since: Optional[str] = None,
                         cursor: Optional[str] = None) -> dict:
    """
    基于游标的分页获取文章。游标 = (score, published, id)。
    向后兼容: cursor=None 时等同于首页。
    """
    conn = get_db()
    where = ["score >= ?"]
    params: list = [min_score]

    if since:
        where.append("published >= ?")
        params.append(since)

    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded:
            # (score DESC, published DESC, id): 用 < 翻页
            where.append(
                "(score < ? OR (score = ? AND published < ?) "
                "OR (score = ? AND published = ? AND id < ?))"
            )
            params.extend([
                decoded["score"], decoded["score"], decoded["published"],
                decoded["score"], decoded["published"], decoded["id"],
            ])

    where_clause = " AND ".join(where)
    rows = conn.execute(
        f"SELECT * FROM articles WHERE {where_clause} "
        "ORDER BY score DESC, published DESC, id DESC LIMIT ?",
        params + [limit + 1]  # 多取一条判断 has_next
    ).fetchall()

    has_next = len(rows) > limit
    items = rows[:limit]

    conn.close()

    next_cursor = None
    if has_next and items:
        last = items[-1]
        next_cursor = _encode_cursor({
            "score": last["score"],
            "published": last["published"] or "",
            "id": last["id"],
        })

    return {
        "items": [_row_to_article(r) for r in items],
        "next_cursor": next_cursor,
        "has_next": has_next,
        "count": len(items),
    }
