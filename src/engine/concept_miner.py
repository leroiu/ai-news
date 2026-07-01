"""
AI News — Concept Miner (概念发现器)

从文章流中自动发现新兴概念、方法论、Agent 模式。
维护候选池，根据出现次数和来源权威性自动升级为 Knowledge Card。

准入规则:
  1 次出现 → 候选池 (candidate_concepts.json)
  2 次出现 → 生成草稿卡片 (data/knowledge/methodology/<id>.yaml)
  3 次出现 / 高权威源 → 日志提醒人工审查
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .fetcher import Article
from .utils import log, load_config, ROOT_DIR, ensure_dir
from .ai_client import call_ai

POOL_PATH = ROOT_DIR / "data" / "candidate_concepts.json"

# 高权威来源
HIGH_AUTHORITY_SOURCES = {
    "Anthropic Research", "OpenAI Blog", "DeepMind Blog",
    "Google AI Blog", "ArXiv AI",
}

# 已知卡片 ID（避免重复发现）
def _known_card_ids() -> set[str]:
    """返回所有已知的 Knowledge Card ID。"""
    from .knowledge import load_cards
    return {c.id for c in load_cards()}

# 已知卡片名称和别名（避免重复发现）
def _known_card_names() -> dict[str, set[str]]:
    """返回 {normalized_name: {aliases}} 用于去重。"""
    from .knowledge import load_cards
    result: dict[str, set[str]] = {}
    for c in load_cards():
        key = c.name.lower().strip()
        aliases = {a.lower().strip() for a in c.aliases}
        aliases.add(key)
        result[key] = aliases
    return result


# ============================================================
# 候选池管理
# ============================================================

def _load_pool() -> dict:
    if POOL_PATH.exists():
        try:
            with open(POOL_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"candidates": {}, "last_updated": ""}


def _save_pool(pool: dict):
    pool["last_updated"] = datetime.now(timezone.utc).isoformat()
    POOL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(POOL_PATH, "w", encoding="utf-8") as f:
        json.dump(pool, f, ensure_ascii=False, indent=2, default=str)


# ============================================================
# 概念抽取
# ============================================================

def _build_prompt(articles: list[Article]) -> tuple[str, str]:
    system = (ROOT_DIR / "prompts" / "mine-concepts.md").read_text(encoding="utf-8")
    lines = ["请分析以下文章，发现新概念：\n"]
    for a in articles:
        content = (a.content_raw or "")[:500]
        lines.append(f"---\n标题: {a.title}\n来源: {a.source}\n内容: {content}\n")
    return system, "\n".join(lines)


def mine_concepts(articles: list[Article], batch_size: int = 30) -> list[dict]:
    """
    从文章批次中抽取候选概念。

    Returns: list of candidate concept dicts
    """
    all_candidates: list[dict] = []

    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        system, user = _build_prompt(batch)

        log.info(f"概念挖掘 {i//batch_size + 1}/{(len(articles)-1)//batch_size + 1} ({len(batch)}篇)")
        results = call_ai(system, user, max_tokens=4096)

        if results is None:
            log.warning("概念挖掘失败，跳过本批")
            continue

        for item in results:
            if not isinstance(item, dict):
                continue
            name = item.get("name", "").strip()
            if not name:
                continue
            all_candidates.append(item)

    return all_candidates


# ============================================================
# 候选池更新 + 准入规则
# ============================================================

def _slugify(name: str) -> str:
    """Name → kebab-case ID"""
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug)
    return slug[:50]


def _is_already_known(name: str, known_names: dict[str, set[str]]) -> bool:
    """检查概念是否已被已有卡片覆盖。"""
    key = name.lower().strip()
    for card_name, aliases in known_names.items():
        if key in aliases:
            return True
        # 模糊匹配：概念名包含卡片名或反之
        if key in card_name or card_name in key:
            return True
    return False


def update_pool(
    candidates: list[dict],
    source_articles: list[Article],
    dry_run: bool = False,
) -> dict[str, str]:
    """
    更新候选池并执行准入规则。

    Returns: {concept_name: action} — 记录每项操作
    """
    pool = _load_pool()
    known_names = _known_card_names()

    actions: dict[str, str] = {}
    now = datetime.now(timezone.utc).isoformat()

    for c in candidates:
        name = c.get("name", "").strip()
        if not name:
            continue

        # 跳过已知概念
        if _is_already_known(name, known_names):
            log.debug(f"跳过已知概念: {name}")
            continue

        slug = _slugify(name)
        source_name = c.get("source_url", "") or source_articles[0].source if source_articles else ""
        is_high_auth = source_name in HIGH_AUTHORITY_SOURCES
        confidence = c.get("confidence", 0.5)

        if slug not in pool["candidates"]:
            # 首次出现 → 候选池
            pool["candidates"][slug] = {
                "name": name,
                "type": c.get("type", "technique"),
                "occurrences": 1,
                "confidence_sum": confidence,
                "first_seen": now,
                "last_seen": now,
                "sources": [source_name] if source_name else [],
                "evidence": [c.get("evidence", "")[:200]],
                "should_create_card": c.get("should_create_card", False),
                "status": "candidate",
            }
            actions[name] = "新增候选"
        else:
            # 已存在 → 累加
            entry = pool["candidates"][slug]
            entry["occurrences"] += 1
            entry["confidence_sum"] += confidence
            entry["last_seen"] = now
            if source_name and source_name not in entry["sources"]:
                entry["sources"].append(source_name)
            if c.get("evidence"):
                ev = c["evidence"][:200]
                if ev not in entry["evidence"]:
                    entry["evidence"].append(ev)

            occ = entry["occurrences"]
            avg_conf = entry["confidence_sum"] / occ

            # 准入规则
            if occ >= 3 or (occ >= 2 and is_high_auth) or (occ >= 1 and is_high_auth and avg_conf >= 0.8):
                if entry["status"] != "confirmed":
                    entry["status"] = "confirmed"
                    actions[name] = f"✅ 确认 (出现{occ}次, 置信度{avg_conf:.1f})"
                    # 生成草稿卡片
                    if not dry_run:
                        _generate_draft_card(entry, slug)
            elif occ >= 2:
                if entry["status"] == "candidate":
                    entry["status"] = "draft"
                    actions[name] = f"📝 生成草稿 (出现{occ}次)"
                    if not dry_run:
                        _generate_draft_card(entry, slug)

    if not dry_run:
        _save_pool(pool)

    return actions


def _generate_draft_card(entry: dict, slug: str):
    """根据候选池条目生成草稿 Knowledge Card。"""
    card_dir = ROOT_DIR / "data" / "knowledge" / "methodology"
    ensure_dir(card_dir)
    card_path = card_dir / f"{slug}.yaml"

    # 不覆盖已有卡片
    if card_path.exists():
        return

    avg_conf = entry["confidence_sum"] / max(1, entry["occurrences"])
    evidence_text = " | ".join(entry.get("evidence", [])[:3])

    content = f"""# Auto-generated draft — Concept Miner
id: {slug}
name: {entry['name']}
type: methodology
tags:
  - auto-generated
  - candidate
importance: 2
confidence: speculative

summary: |
  候选概念。置信度 {avg_conf:.1f}，出现 {entry['occurrences']} 次。
  证据: {evidence_text[:200]}

significance: |
  自动发现的概念。需要人工审查和补充 significance、related、timeline 等字段。

domain: "待分类"
source_articles:
{chr(10).join(f'  - "{s}"' for s in entry.get('sources', [])[:5])}

related: []
"""
    card_path.write_text(content, encoding="utf-8")
    log.info(f"草稿卡片已生成: {card_path.name}")


def get_pool_summary() -> dict:
    """返回候选池摘要。"""
    pool = _load_pool()
    by_status: dict[str, int] = {}
    for entry in pool.get("candidates", {}).values():
        status = entry.get("status", "candidate")
        by_status[status] = by_status.get(status, 0) + 1
    return {
        "total": len(pool.get("candidates", {})),
        "by_status": by_status,
        "last_updated": pool.get("last_updated", ""),
    }
