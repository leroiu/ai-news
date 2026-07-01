"""
AI Intelligence Platform — 知识卡片同步脚本

将 data/knowledge/ 下的 YAML 卡片同步到 SQLite entities 和 relationships 表。
过滤掉 auto-generated 草稿卡，只同步人工策展的卡片。
"""

import sys
from pathlib import Path
from typing import Optional

import yaml

# 允许直接运行此脚本
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.engine.database import (
    init_db, get_db, upsert_entity, upsert_relationship,
    get_entities, get_relationships,
)
from src.engine.knowledge import load_cards, KnowledgeCard
from src.engine.utils import log, ROOT_DIR

CARDS_DIR = ROOT_DIR / "data" / "knowledge"

# 实体类型 → 颜色映射
TYPE_COLORS = {
    "model": "#4C78A8",
    "company": "#F58518",
    "tech": "#72B7B2",
    "concept": "#E45756",
    "product": "#54A24B",
    "person": "#B279A2",
    "methodology": "#D4A017",
    "event": "#B279A2",
    "paper": "#4C78A8",
    "dataset": "#72B7B2",
    "benchmark": "#E45756",
    "opensource": "#54A24B",
}


def sync_cards(include_drafts: bool = False):
    """将所有 YAML 卡片同步到 SQLite 数据库。

    参数:
        include_drafts: 是否包含自动生成的草稿卡（默认 False，只同步人工策展的卡片）
    """
    # 初始化数据库
    init_db()

    # 加载所有 YAML 卡片
    all_cards = load_cards(CARDS_DIR)
    log.info(f"从磁盘加载 {len(all_cards)} 张卡片")

    # 分离人工策展 vs 自动生成
    curated: list[KnowledgeCard] = []
    drafts: list[KnowledgeCard] = []
    for card in all_cards:
        if "auto-generated" in card.tags or "candidate" in card.tags:
            drafts.append(card)
        else:
            curated.append(card)

    log.info(f"人工策展: {len(curated)} 张, 自动生成草稿: {len(drafts)} 张")

    # 决定同步哪些
    cards_to_sync = curated.copy()
    if include_drafts:
        cards_to_sync.extend(drafts)
        log.info("包含自动生成草稿卡")

    # 同步实体
    synced = 0
    skipped = 0
    for card in cards_to_sync:
        try:
            entity = {
                "id": card.id,
                "name": card.name,
                "type": card.type,
                "importance": card.importance if card.importance > 0 else 2,
                "summary": card.summary or "",
                "significance": card.significance or "",
                "release_date": card._raw.get("release_date", ""),
                "company": card.company or "",
                "tags": card.tags,
                "aliases": card.aliases,
                "timeline": card.timeline,
                "color": TYPE_COLORS.get(card.type, "#999"),
            }
            upsert_entity(entity)
            synced += 1
        except Exception as e:
            log.error(f"同步失败 [{card.id}]: {e}")
            skipped += 1

    log.info(f"实体同步: {synced} 张成功, {skipped} 张失败")

    # 同步关系
    rel_added = 0
    rel_skipped = 0

    # 收集所有有效的卡片 ID（只包含已同步的）
    valid_ids = {c.id for c in cards_to_sync}
    existing_rels = get_relationships()
    existing_pairs = {(r["source_id"], r["target_id"], r["rel_type"]) for r in existing_rels}

    for card in cards_to_sync:
        # related → general relation
        for target in card.related:
            if target in valid_ids:
                key = (card.id, target, "related_to")
                if key not in existing_pairs:
                    try:
                        upsert_relationship(card.id, target, "related_to")
                        rel_added += 1
                        existing_pairs.add(key)
                    except Exception as e:
                        rel_skipped += 1

        # depends_on → depends_on
        for target in card.depends_on:
            if target in valid_ids:
                key = (card.id, target, "depends_on")
                if key not in existing_pairs:
                    try:
                        upsert_relationship(card.id, target, "depends_on")
                        rel_added += 1
                        existing_pairs.add(key)
                    except Exception as e:
                        rel_skipped += 1

        # influenced → influences
        for target in card.influenced:
            if target in valid_ids:
                key = (card.id, target, "influences")
                if key not in existing_pairs:
                    try:
                        upsert_relationship(card.id, target, "influences")
                        rel_added += 1
                        existing_pairs.add(key)
                    except Exception as e:
                        rel_skipped += 1

    log.info(f"关系同步: {rel_added} 条新增, {rel_skipped} 条跳过(已存在/失败)")

    # 输出摘要
    conn = get_db()
    total_entities = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    total_rels = conn.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
    conn.close()

    print(f"\n{'='*60}")
    print(f"同步完成！")
    print(f"  实体: {total_entities} 张 (新增 {synced})")
    print(f"  关系: {total_rels} 条 (新增 {rel_added})")
    print(f"  草稿卡: {len(drafts)} 张未同步 (使用 --include-drafts 以包含)")
    print(f"{'='*60}")

    # 重建嵌入向量
    from src.engine.embeddings import rebuild_card_embeddings
    log.info("重建卡片嵌入向量...")
    emb_result = rebuild_card_embeddings()
    log.info(f"嵌入: {emb_result['embedded']} 新建, "
             f"{emb_result['skipped']} 跳过, {emb_result['failed']} 失败")
    if emb_result["errors"]:
        for e in emb_result["errors"]:
            log.warning(f"  ⚠ {e}")

    return {"entities": total_entities, "relationships": total_rels}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="同步 YAML 知识卡片到 SQLite 数据库")
    parser.add_argument("--include-drafts", action="store_true",
                        help="包含自动生成的草稿卡")
    parser.add_argument("--dry-run", action="store_true",
                        help="只显示将要同步的内容，不实际写入")
    args = parser.parse_args()

    if args.dry_run:
        cards = load_cards(CARDS_DIR)
        curated = [c for c in cards if "auto-generated" not in c.tags]
        drafts = [c for c in cards if "auto-generated" in c.tags]
        print(f"将要同步 {len(curated)} 张人工策展卡片:")
        for c in sorted(curated, key=lambda x: (x.type, x.id)):
            print(f"  [{c.type}] {c.id} (importance={c.importance})")
        if args.include_drafts:
            print(f"\n以及 {len(drafts)} 张自动生成草稿卡")
        print(f"\n(使用 --include-drafts 包含草稿卡)")
    else:
        sync_cards(include_drafts=args.include_drafts)
