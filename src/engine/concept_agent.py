"""Concept Miner Agent：将简单规则升级为语义相似度 + AI 决策闭环。

对每个候选概念执行:
  1. Semantic Lookup — 嵌入概念名，cosine 相似度匹配已有卡片
  2. AI Decision — 调用轻量 prompt 判断 NEW/MERGE/SKIP/DRAFT
  3. Execute — 按决策结果更新候选池，记录理由

复用: embed_texts / call_ai (ai_client), get_all_embeddings / cosine_similarity (embeddings),
      _load_pool / _save_pool / _slugify (concept_miner)
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .utils import log

PROMPT_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


# ── Prompt 加载 ──

def _load_prompt(name: str) -> str:
    path = PROMPT_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    log.warning(f"Prompt not found: {path}")
    return ""


# ── Step 1: Semantic Lookup ──

def _semantic_lookup(concept_name: str, top_k: int = 5) -> list[dict]:
    """嵌入候选概念名，返回 top-k 最相似的已有卡片。

    嵌入表为空或 API 失败时返回空列表，调用方应 fallback 到纯文本匹配。
    """
    from .embeddings import get_all_embeddings, cosine_similarity
    from .ai_client import embed_texts
    from .database import get_entities

    stored = get_all_embeddings()
    if not stored:
        return []

    vecs = embed_texts([concept_name])
    if not vecs or len(vecs) == 0:
        log.warning(f"Semantic lookup: embed API failed for '{concept_name}'")
        return []

    query_vec = vecs[0]
    cards = get_entities()
    scored: list[dict] = []

    for c in cards:
        card_vec = stored.get(c["id"])
        if card_vec is None:
            continue
        sim = cosine_similarity(query_vec, card_vec)
        if sim > 0.0:
            scored.append({
                "id": c["id"],
                "name": c.get("name", ""),
                "type": c.get("type", ""),
                "summary": (c.get("summary") or "")[:200],
                "_similarity": round(sim, 4),
            })

    scored.sort(key=lambda x: x["_similarity"], reverse=True)
    return scored[:top_k]


# ── Step 2: AI Decision ──

def _decide_concept(candidate: dict, similar_cards: list[dict]) -> dict:
    """AI 判断候选概念应如何处理：NEW / MERGE / SKIP / DRAFT。

    AI 调用失败或 prompt 缺失时，用相似度阈值做 fallback 决策。
    """
    from .ai_client import call_ai

    # 构建相似卡片摘要
    if similar_cards:
        card_lines = []
        for c in similar_cards:
            card_lines.append(
                f"- {c['name']} ({c.get('type', '')}) "
                f"相似度={c['_similarity']:.2f}: {c.get('summary', '')[:120]}"
            )
        cards_text = "\n".join(card_lines)
    else:
        cards_text = "（无相似卡片）"

    prompt = _load_prompt("concept-decide.md")
    if not prompt:
        return _fallback_decide(candidate, similar_cards)

    prompt = prompt.replace("$CONCEPT_NAME", candidate.get("name", ""))
    prompt = prompt.replace("$CONCEPT_TYPE", candidate.get("type", "technique"))
    prompt = prompt.replace(
        "$CONCEPT_CONFIDENCE",
        str(round(candidate.get("confidence", 0.5), 2)),
    )
    prompt = prompt.replace(
        "$CONCEPT_EVIDENCE",
        (candidate.get("evidence") or "")[:300],
    )
    prompt = prompt.replace("$SIMILAR_CARDS", cards_text)

    user = (
        f"判断候选概念 '{candidate.get('name', '')}' 应如何处理: "
        f"NEW（新建）/ MERGE（合并）/ SKIP（跳过）/ DRAFT（待定）"
    )

    result = call_ai(prompt, user, temperature=0.1, max_tokens=256)
    if not result:
        return _fallback_decide(candidate, similar_cards)

    decision = result[0] if isinstance(result, list) else result
    if not isinstance(decision, dict):
        return _fallback_decide(candidate, similar_cards)

    valid = {"NEW", "MERGE", "SKIP", "DRAFT"}
    if decision.get("decision") not in valid:
        decision["decision"] = "DRAFT"

    log.info(
        f"Agent Decide: '{candidate.get('name', '')}' → {decision.get('decision', '?')}"
    )
    return decision


def _fallback_decide(candidate: dict, similar_cards: list[dict]) -> dict:
    """AI 不可用时的简单规则 fallback：最高相似度 <0.5 → NEW，否则 → DRAFT。"""
    max_sim = max((c["_similarity"] for c in similar_cards), default=0.0)
    if max_sim < 0.5:
        return {
            "decision": "NEW",
            "target_card_id": None,
            "reason": f"最高相似度 {max_sim:.2f} < 0.5，判定为新概念（fallback 模式）",
        }
    return {
        "decision": "DRAFT",
        "target_card_id": None,
        "reason": f"最高相似度 {max_sim:.2f} ≥ 0.5，需人工审查（fallback 模式）",
    }


# ── Step 3: Batch Assessment ──

def assess_concepts(candidates: list[dict]) -> list[dict]:
    """批量评估候选概念，返回带决策的结果列表。

    Returns:
        [{candidate, decision, target_card_id, reason, similar_cards}, ...]
    """
    results: list[dict] = []
    for c in candidates:
        name = c.get("name", "").strip()
        if not name:
            continue
        similar = _semantic_lookup(name)
        decision = _decide_concept(c, similar)
        results.append({
            "candidate": c,
            "decision": decision.get("decision", "DRAFT"),
            "target_card_id": decision.get("target_card_id"),
            "reason": decision.get("reason", ""),
            "similar_cards": similar,
        })
    return results


# ── Step 4: Agent-enhanced Pool Update ──

def update_pool_with_agent(
    candidates: list[dict],
    source_articles: list,
    dry_run: bool = False,
) -> dict[str, str]:
    """Agent 增强的候选池更新。

    用语义相似度 + AI 决策替代原有的简单出现次数计数规则。
    每个候选概念经过: 语义查找 → AI 决策 → 执行（入库/记录/丢弃）。

    Returns:
        {concept_name: "NEW: <reason>" | "DRAFT: <reason>" | "SKIP: <reason>" | ...}
    """
    from .concept_miner import _load_pool, _save_pool, _slugify, _is_already_known, _known_card_names

    pool = _load_pool()
    known_names = _known_card_names()
    assessments = assess_concepts(candidates)

    actions: dict[str, str] = {}
    now = datetime.now(timezone.utc).isoformat()

    for a in assessments:
        c = a["candidate"]
        name = c.get("name", "").strip()
        if not name:
            continue

        decision = a["decision"]
        reason = a.get("reason", "")
        target_id = a.get("target_card_id")

        # 仍做文本兜底：已知概念直接跳过
        if _is_already_known(name, known_names):
            actions[name] = f"SKIP: 文本匹配已知卡片"
            continue

        slug = _slugify(name)

        if decision == "NEW":
            # 入库：加入候选池
            pool["candidates"][slug] = {
                "name": name,
                "type": c.get("type", "technique"),
                "occurrences": 1,
                "confidence_sum": c.get("confidence", 0.5),
                "first_seen": now,
                "last_seen": now,
                "sources": [],
                "evidence": [(c.get("evidence") or "")[:200]],
                "should_create_card": c.get("should_create_card", False),
                "status": "candidate",
                "_agent_decision": "NEW",
                "_agent_reason": reason,
                "_similar_cards": [
                    {"id": s["id"], "name": s["name"], "sim": s["_similarity"]}
                    for s in a.get("similar_cards", [])[:5]
                ],
            }
            actions[name] = f"NEW: {reason}"

        elif decision == "MERGE":
            # 记录合并建议（不自动执行合并）
            pool["candidates"][slug] = {
                "name": name,
                "type": c.get("type", "technique"),
                "occurrences": 1,
                "confidence_sum": c.get("confidence", 0.5),
                "first_seen": now,
                "last_seen": now,
                "sources": [],
                "evidence": [(c.get("evidence") or "")[:200]],
                "should_create_card": False,
                "status": "candidate",
                "_agent_decision": "MERGE",
                "_agent_reason": reason,
                "_merge_target": target_id,
                "_similar_cards": [
                    {"id": s["id"], "name": s["name"], "sim": s["_similarity"]}
                    for s in a.get("similar_cards", [])[:5]
                ],
            }
            actions[name] = f"MERGE → {target_id}: {reason}"

        elif decision == "SKIP":
            # 丢弃：不加入候选池，但记录决策
            actions[name] = f"SKIP: {reason}"

        elif decision == "DRAFT":
            # 暂存：加入候选池，标记待人工审查
            pool["candidates"][slug] = {
                "name": name,
                "type": c.get("type", "technique"),
                "occurrences": 1,
                "confidence_sum": c.get("confidence", 0.5),
                "first_seen": now,
                "last_seen": now,
                "sources": [],
                "evidence": [(c.get("evidence") or "")[:200]],
                "should_create_card": c.get("should_create_card", False),
                "status": "candidate",
                "_agent_decision": "DRAFT",
                "_agent_reason": reason,
                "_similar_cards": [
                    {"id": s["id"], "name": s["name"], "sim": s["_similarity"]}
                    for s in a.get("similar_cards", [])[:5]
                ],
            }
            actions[name] = f"DRAFT: {reason}"

    if not dry_run:
        _save_pool(pool)

    log.info(
        f"Agent Pool Update: {len(assessments)} assessed → "
        f"{len(actions)} actions"
    )
    return actions
