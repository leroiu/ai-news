"""
Relationship CRUD + 图谱邻居遍历 + 子图查询 + 批量验证。

从 database.py 拆分出来。
"""

from typing import Optional

from .db_core import get_db, _row_to_entity


# ═══════════════════════════════════════════════════════════════
# Relationship CRUD
# ═══════════════════════════════════════════════════════════════

def upsert_relationship(source: str, target: str, rel_type: str, label: str = ""):
    """插入关系（幂等）。"""
    conn = get_db()
    conn.execute("""
        INSERT OR IGNORE INTO relationships (source_id, target_id, rel_type, label)
        VALUES (?,?,?,?)
    """, (source, target, rel_type, label))
    conn.commit()
    conn.close()


def get_relationships(entity_id: Optional[str] = None) -> list[dict]:
    """查询关系列表，可按实体过滤。"""
    conn = get_db()
    if entity_id:
        rows = conn.execute(
            "SELECT * FROM relationships WHERE source_id=? OR target_id=?",
            (entity_id, entity_id)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM relationships").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_relationship(rel_id: int) -> bool:
    """删除关系。返回是否成功删除。"""
    conn = get_db()
    cur = conn.execute("DELETE FROM relationships WHERE id=?", (rel_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


# ═══════════════════════════════════════════════════════════════
# Graph Queries
# ═══════════════════════════════════════════════════════════════

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
        f"SELECT * FROM relationships WHERE source_id IN ({placeholders}) "
        f"AND target_id IN ({placeholders})",
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
