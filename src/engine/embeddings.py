"""
AI Intelligence Platform — Embeddings & Semantic Search

基于 Kimi/OpenAI Embeddings API 的语义搜索层。
卡片嵌入存储在 SQLite embeddings 表中，零新依赖。
"""

import json
import math
import yaml
from pathlib import Path
from typing import Optional

from .utils import log, ROOT_DIR
from .database import get_db


# ============================================================
# 配置
# ============================================================

def _load_emb_cfg() -> dict:
    cfg_path = ROOT_DIR / "config.yaml"
    if cfg_path.exists():
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        return cfg.get("embeddings", {})
    return {}


def get_alpha() -> float:
    """混合搜索权重：alpha 为关键词权重，1-alpha 为语义权重。"""
    return float(_load_emb_cfg().get("alpha", 0.3))


# ============================================================
# 嵌入文本构建
# ============================================================

def build_card_embedding_text(card: dict) -> str:
    """构建单张卡片的嵌入文本：name + summary + significance。"""
    parts = [card.get("name", "")]
    summary = card.get("summary", "")
    if summary:
        parts.append(summary)
    significance = card.get("significance", "")
    if significance:
        parts.append(significance)
    return "\n".join(parts)


# ============================================================
# 余弦相似度（纯 Python）
# ============================================================

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """纯 Python 余弦相似度，返回 [-1, 1]。"""
    if len(v1) != len(v2) or len(v1) == 0:
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


# ============================================================
# 嵌入向量存储 (SQLite)
# ============================================================

def init_embeddings_table():
    """在数据库中创建 embeddings 表（幂等）。"""
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS embeddings (
            id          TEXT PRIMARY KEY,
            dims        INTEGER NOT NULL,
            vector      TEXT NOT NULL,
            updated_at  TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_id ON embeddings(id)")
    conn.commit()
    conn.close()


def store_embedding(entity_id: str, vector: list[float]):
    """存储单个实体的嵌入向量。"""
    conn = get_db()
    conn.execute("""
        INSERT OR REPLACE INTO embeddings (id, dims, vector, updated_at)
        VALUES (?, ?, ?, datetime('now'))
    """, (entity_id, len(vector), json.dumps(vector)))
    conn.commit()
    conn.close()


def get_embedding(entity_id: str) -> list[float] | None:
    """获取单个实体的嵌入向量。"""
    conn = get_db()
    r = conn.execute("SELECT vector FROM embeddings WHERE id=?", (entity_id,)).fetchone()
    conn.close()
    if r:
        try:
            return json.loads(r["vector"])
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def get_all_embeddings() -> dict[str, list[float]]:
    """返回所有已存储的嵌入向量 {entity_id: vector}。表不存在时返回空 dict。"""
    conn = get_db()
    try:
        rows = conn.execute("SELECT id, vector FROM embeddings").fetchall()
    except Exception:
        conn.close()
        return {}
    conn.close()
    result: dict[str, list[float]] = {}
    for r in rows:
        try:
            result[r["id"]] = json.loads(r["vector"])
        except (json.JSONDecodeError, TypeError):
            pass
    return result


# ============================================================
# 嵌入重建
# ============================================================

def rebuild_card_embeddings(force: bool = False) -> dict:
    """嵌入所有 entities 表中的卡片，返回统计信息。"""
    from .database import get_entities
    from .ai_client import embed_texts

    init_embeddings_table()

    cards = get_entities()
    existing = get_all_embeddings() if not force else {}
    to_embed: list[dict] = []
    for c in cards:
        cid = c["id"]
        if not force and cid in existing:
            continue
        text = build_card_embedding_text(c)
        if not text.strip():
            continue
        to_embed.append({"id": cid, "text": text})

    if not to_embed:
        log.info(f"所有 {len(cards)} 张卡片已有嵌入，跳过重建")
        return {"embedded": 0, "skipped": len(cards), "failed": 0, "errors": []}

    # 分批嵌入（每批 20 张）
    BATCH = 20
    embedded = 0
    failed = 0
    errors: list[str] = []

    for i in range(0, len(to_embed), BATCH):
        batch = to_embed[i:i + BATCH]
        texts = [b["text"] for b in batch]
        vectors = embed_texts(texts)
        if vectors is None:
            msg = f"批次 {i // BATCH + 1} 嵌入失败"
            log.error(msg)
            failed += len(batch)
            errors.append(msg)
            continue
        for j, b in enumerate(batch):
            if j < len(vectors):
                store_embedding(b["id"], vectors[j])
                embedded += 1
            else:
                failed += 1
                errors.append(f"{b['id']}: API 返回向量不足")

    log.info(f"嵌入完成: {embedded} 新建, {len(cards) - embedded - failed} 跳过, {failed} 失败")
    return {"embedded": embedded, "skipped": len(cards) - embedded - failed,
            "failed": failed, "errors": errors}


# ============================================================
# 语义搜索
# ============================================================

def search_semantic(query: str, limit: int = 20) -> list[dict]:
    """嵌入查询文本，计算与所有卡片的 cosine 相似度，返回 top-N。"""
    from .ai_client import embed_texts
    from .database import get_entities

    stored = get_all_embeddings()
    if not stored:
        return []

    vecs = embed_texts([query])
    if not vecs or len(vecs) == 0:
        return []
    query_vec = vecs[0]

    cards = get_entities()
    scored: list[dict] = []
    for c in cards:
        card_vec = stored.get(c["id"])
        if card_vec is None:
            continue
        sim = cosine_similarity(query_vec, card_vec)
        scored.append({**c, "_semantic_score": round(sim, 4)})

    scored.sort(key=lambda x: x["_semantic_score"], reverse=True)
    return scored[:limit]


def _keyword_search(query: str, limit: int = 20) -> dict:
    """纯关键词搜索（内部用，避免循环导入）。"""
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


def search_hybrid(query: str, limit: int = 20, alpha: float | None = None) -> dict:
    """混合检索：关键词 + 语义加权融合。

    alpha: 关键词权重 (0.0=纯语义, 1.0=纯关键词)，默认从 config.yaml 读取。
    """
    if alpha is None:
        alpha = get_alpha()

    kw = _keyword_search(query, limit=limit * 2)
    sem = search_semantic(query, limit=limit * 2)

    # 如果语义搜索失败，降级为纯关键词
    if not sem:
        kw["mode"] = "keyword"
        return kw

    # 构建关键词分数映射 (归一化 rank score)
    kw_scores: dict[str, float] = {}
    max_kw = max(len(kw["entities"]), 1)
    for i, e in enumerate(kw["entities"]):
        kw_scores[e["id"]] = 1.0 - (i / max_kw)

    # 合并：hybrid_score = alpha * keyword_norm + (1-alpha) * semantic_score
    merged: dict[str, dict] = {}
    for e in kw["entities"]:
        eid = e["id"]
        kw_norm = kw_scores.get(eid, 0.0)
        sem_score = 0.0
        merged[eid] = {**e, "_keyword_score": round(kw_norm, 4),
                       "_semantic_score": sem_score}

    for e in sem:
        eid = e["id"]
        if eid in merged:
            merged[eid]["_semantic_score"] = e["_semantic_score"]
        else:
            merged[eid] = {**e, "_keyword_score": 0.0}

    # 计算最终混合分数
    for eid, e in merged.items():
        kw_norm = e["_keyword_score"]
        sem_score = e["_semantic_score"]
        e["_score"] = round(alpha * kw_norm + (1 - alpha) * sem_score, 4)

    # 排序 + 去重
    sorted_entities = sorted(merged.values(), key=lambda x: x["_score"], reverse=True)[:limit]

    return {
        "entities": sorted_entities,
        "articles": kw["articles"][:limit],
        "mode": "hybrid",
        "alpha": alpha,
    }


# ============================================================
# 语义卡片匹配（升级 knowledge.py 的 match_cards）
# ============================================================

def match_cards_semantic(
    articles: list,
    cards: list,
    min_score: float = 0.3,
    max_per_article: int = 3,
) -> dict[str, list]:
    """语义版卡片匹配：将文章标题+分类嵌入后与卡片做 cosine 相似度匹配。

    无嵌入时返回空 dict，调用方应 fallback 到 Jaccard。
    """
    from .ai_client import embed_texts

    stored = get_all_embeddings()
    if not stored:
        log.info("嵌入表为空，跳过语义匹配")
        return {}

    # 预构建文章查询文本
    queries: list[tuple[str, str]] = []  # [(article_id, query_text)]
    for a in articles:
        if hasattr(a, "id"):
            aid = a.id
            title = getattr(a, "title", "")
            cats = getattr(a, "categories", [])
        else:
            aid = a.get("id", "")
            title = a.get("title", "")
            cats = a.get("categories", [])
        cat_str = " ".join(cats) if cats else ""
        text = f"{title} {cat_str}".strip()
        if text:
            queries.append((aid, text))

    if not queries:
        return {}

    # 批量嵌入文章查询
    query_texts = [q[1] for q in queries]
    query_vecs = embed_texts(query_texts)
    if query_vecs is None:
        log.warning("语义匹配：嵌入 API 失败，回退到 Jaccard")
        return {}

    # 匹配每篇文章
    result: dict[str, list] = {}
    for idx, (aid, _) in enumerate(queries):
        if idx >= len(query_vecs):
            break
        qv = query_vecs[idx]
        scored: list[tuple] = []
        for card in cards:
            card_vec = stored.get(card.id)
            if card_vec is None:
                continue
            sim = cosine_similarity(qv, card_vec)
            if sim >= min_score:
                scored.append((card, sim))
        scored.sort(key=lambda x: x[1], reverse=True)
        result[aid] = [c for c, _ in scored[:max_per_article]]

    return result
