"""
AI News - 知识图谱数据层

纯数据逻辑：TYPE_COLORS、EDGE_STYLES、build_graph、_compute_stats。
不依赖任何渲染或 i18n 模块。
"""
from collections import defaultdict
from typing import Optional

from .knowledge import load_cards, KnowledgeCard

# ============================================================
# 图数据模型
# ============================================================

# 节点颜色（按 type）
TYPE_COLORS = {
    "model":    "#4C78A8",  # 蓝色
    "company":  "#F58518",  # 橙色
    "tech":     "#72B7B2",  # 青色
    "concept":  "#E45756",  # 红色
    "product":  "#54A24B",  # 绿色
    "person":      "#B279A2",  # 紫色
    "methodology": "#D4A017",  # 金色
    "event":       "#FF9DA6",  # 粉色
}

EDGE_STYLES = {
    "related":     {"color": "#999", "dash": "5,5",  "label": "关联"},
    "depends_on":  {"color": "#E45756", "dash": "",  "label": "依赖"},
    "influenced":  {"color": "#4C78A8", "dash": "",  "label": "影响"},
}


# ============================================================
# 图构建
# ============================================================

def build_graph(cards: Optional[list[KnowledgeCard]] = None) -> dict:
    """
    从知识卡片构建图结构。

    返回:
      {
        "nodes": [{"id", "name", "type", "importance", "summary", "color"}],
        "edges": [{"source", "target", "type", "color", "label"}],
        "stats": {"total_nodes", "total_edges", "components", "most_connected", ...}
      }
    """
    if cards is None:
        cards = load_cards()

    card_map: dict[str, KnowledgeCard] = {c.id: c for c in cards}

    nodes = []
    for c in cards:
        nodes.append({
            "id": c.id,
            "name": c.name,
            "type": c.type,
            "importance": c.importance,
            "summary": c.summary,
            "significance": c.significance,
            "release_date": c._raw.get("release_date", ""),
            "company": c.company,
            "timeline": c.timeline,
            "aliases": c.aliases,
            "tags": c.tags,
            "color": TYPE_COLORS.get(c.type, "#999"),
        })

    # 构建边（去重）
    seen_edges: set[tuple[str, str, str]] = set()
    edges = []

    def add_edge(source: str, target: str, edge_type: str):
        if source == target:
            return
        # 如果目标卡片不存在，跳过
        if target not in card_map:
            return
        key = (source, target, edge_type)
        if key in seen_edges:
            return
        seen_edges.add(key)
        style = EDGE_STYLES.get(edge_type, EDGE_STYLES["related"])
        edges.append({
            "source": source,
            "target": target,
            "type": edge_type,
            "color": style["color"],
            "dash": style["dash"],
            "label": style["label"],
        })

    for c in cards:
        for target in c.related:
            add_edge(c.id, target, "related")
        for target in c.depends_on:
            add_edge(c.id, target, "depends_on")
        for target in c.influenced:
            add_edge(c.id, target, "influenced")

    # 统计信息
    stats = _compute_stats(cards, card_map, nodes, edges)

    return {"nodes": nodes, "edges": edges, "stats": stats}


def _compute_stats(
    cards: list[KnowledgeCard],
    card_map: dict[str, KnowledgeCard],
    nodes: list[dict],
    edges: list[dict],
) -> dict:
    """计算图统计信息。"""
    # 度中心性
    degree: dict[str, int] = defaultdict(int)
    for e in edges:
        degree[e["source"]] += 1
        degree[e["target"]] += 1

    most_connected = sorted(degree.items(), key=lambda x: -x[1])[:5]
    most_connected_display = [
        {"id": cid, "name": card_map[cid].name if cid in card_map else cid, "degree": d}
        for cid, d in most_connected
    ]

    # 连通分量
    adj: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        adj[e["source"]].add(e["target"])
        adj[e["target"]].add(e["source"])
    visited: set[str] = set()
    components = 0
    for n in nodes:
        if n["id"] not in visited:
            components += 1
            stack = [n["id"]]
            while stack:
                v = stack.pop()
                if v not in visited:
                    visited.add(v)
                    stack.extend(adj.get(v, set()))

    # 按边类型统计
    edge_types: dict[str, int] = defaultdict(int)
    for e in edges:
        edge_types[e["type"]] += 1

    # 孤立节点
    isolated = [n["name"] for n in nodes if degree[n["id"]] == 0]

    # 按类型统计节点数
    node_types: dict[str, int] = defaultdict(int)
    for n in nodes:
        node_types[n["type"]] += 1

    return {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "components": components,
        "isolated_nodes": isolated,
        "node_types": node_types,
        "edge_types": dict(edge_types),
        "most_connected": most_connected_display,
    }
