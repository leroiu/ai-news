"""
Entity CRUD + 版本历史 + 分页。

从 database.py 拆分出来。
"""

import base64
import json
from datetime import datetime, timezone
from typing import Optional

from .db_core import get_db, _row_to_entity, _normalize_timeline, rebuild_fts


# ═══════════════════════════════════════════════════════════════
# Entity CRUD
# ═══════════════════════════════════════════════════════════════

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
        json.dumps(entity.get("tags", []), default=str),
        json.dumps(entity.get("aliases", []), default=str),
        json.dumps(_normalize_timeline(entity.get("timeline", [])), default=str),
        entity.get("color", "#999"), now,
    ))
    conn.commit()
    conn.close()
    # 重建 FTS5 索引
    try:
        rebuild_fts()
    except Exception:
        pass


def get_entities(entity_type: Optional[str] = None) -> list[dict]:
    """查询实体列表。"""
    conn = get_db()
    if entity_type:
        rows = conn.execute(
            "SELECT * FROM entities WHERE type=? ORDER BY importance DESC",
            (entity_type,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM entities ORDER BY type, importance DESC"
        ).fetchall()
    conn.close()
    return [_row_to_entity(r) for r in rows]


def get_entity(entity_id: str) -> Optional[dict]:
    """按 ID 查询单个实体。"""
    conn = get_db()
    r = conn.execute("SELECT * FROM entities WHERE id=?", (entity_id,)).fetchone()
    conn.close()
    return _row_to_entity(r) if r else None


def delete_entity(entity_id: str) -> bool:
    """删除实体及其关联关系和嵌入向量。返回是否成功删除。"""
    conn = get_db()
    conn.execute("DELETE FROM relationships WHERE source_id=? OR target_id=?",
                 (entity_id, entity_id))
    conn.execute("DELETE FROM embeddings WHERE id=?", (entity_id,))
    cur = conn.execute("DELETE FROM entities WHERE id=?", (entity_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


# ═══════════════════════════════════════════════════════════════
# Entity Version History
# ═══════════════════════════════════════════════════════════════

def save_entity_version(entity_id: str, data: dict, changed_fields: str = ""):
    """保存实体的一个历史版本。"""
    conn = get_db()
    cur = conn.execute(
        "SELECT COALESCE(MAX(version_number), 0) FROM entity_versions WHERE entity_id=?",
        (entity_id,)
    )
    next_version = cur.fetchone()[0] + 1
    conn.execute(
        "INSERT INTO entity_versions (entity_id, version_number, data, changed_fields) "
        "VALUES (?, ?, ?, ?)",
        (entity_id, next_version, json.dumps(data, default=str), changed_fields)
    )
    conn.commit()
    conn.close()


def get_entity_versions(entity_id: str) -> list[dict]:
    """获取实体的所有历史版本。"""
    conn = get_db()
    rows = conn.execute(
        "SELECT id as version_id, entity_id, version_number, data, created_at "
        "FROM entity_versions WHERE entity_id=? ORDER BY version_number DESC",
        (entity_id,)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["data"] = json.loads(d.get("data", "{}"))
        except (json.JSONDecodeError, TypeError):
            d["data"] = {}
        result.append(d)
    return result


# ═══════════════════════════════════════════════════════════════
# Entity Pagination
# ═══════════════════════════════════════════════════════════════

def get_entities_paginated(entity_type: Optional[str] = None,
                           page: int = 1, page_size: int = 50) -> dict:
    """分页获取实体列表。"""
    conn = get_db()
    if entity_type:
        total = conn.execute(
            "SELECT COUNT(*) FROM entities WHERE type=?", (entity_type,)
        ).fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM entities WHERE type=? ORDER BY importance DESC "
            "LIMIT ? OFFSET ?",
            (entity_type, page_size, (page - 1) * page_size)
        ).fetchall()
    else:
        total = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM entities ORDER BY type, importance DESC "
            "LIMIT ? OFFSET ?",
            (page_size, (page - 1) * page_size)
        ).fetchall()
    conn.close()
    return {
        "data": [_row_to_entity(r) for r in rows],
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
        padded = cursor + "=" * (4 - len(cursor) % 4)
        return json.loads(base64.urlsafe_b64decode(padded).decode())
    except Exception:
        return None


def get_entities_cursor(entity_type: Optional[str] = None,
                         limit: int = 50, cursor: Optional[str] = None) -> dict:
    """
    基于游标的分页获取实体。游标 = (importance, type, id)。
    """
    conn = get_db()
    where = []
    params: list = []

    if entity_type:
        where.append("type = ?")
        params.append(entity_type)

    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded:
            where.append(
                "(importance < ? OR (importance = ? AND type > ?) "
                "OR (importance = ? AND type = ? AND id > ?))"
            )
            params.extend([
                decoded["importance"], decoded["importance"], decoded["type"],
                decoded["importance"], decoded["type"], decoded["id"],
            ])

    where_clause = (" WHERE " + " AND ".join(where)) if where else ""
    order = "ORDER BY importance DESC, type ASC, id ASC" if entity_type else "ORDER BY type ASC, importance DESC, id ASC"

    rows = conn.execute(
        f"SELECT * FROM entities{where_clause} {order} LIMIT ?",
        params + [limit + 1]
    ).fetchall()

    has_next = len(rows) > limit
    items = rows[:limit]
    conn.close()

    next_cursor = None
    if has_next and items:
        last = items[-1]
        next_cursor = _encode_cursor({
            "importance": last["importance"],
            "type": last["type"],
            "id": last["id"],
        })

    return {
        "items": [_row_to_entity(r) for r in items],
        "next_cursor": next_cursor,
        "has_next": has_next,
        "count": len(items),
    }
