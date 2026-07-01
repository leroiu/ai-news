#!/usr/bin/env python3
"""数据迁移：Knowledge Cards + Inbox → SQLite"""

import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.engine.database import init_db, upsert_entity, upsert_relationship, insert_articles
from src.engine.knowledge import load_cards
from src.engine.utils import ROOT_DIR, log

TYPE_COLORS = {
    "model": "#4C78A8", "company": "#F58518", "tech": "#72B7B2",
    "concept": "#E45756", "product": "#54A24B", "person": "#B279A2",
    "methodology": "#D4A017", "event": "#FF9DA6",
}


def migrate_cards():
    cards = load_cards()
    log.info(f"迁移 {len(cards)} 张卡片 → SQLite...")

    for c in cards:
        entity = {
            "id": c.id, "name": c.name, "type": c.type,
            "importance": c.importance, "summary": c.summary,
            "significance": c.significance,
            "release_date": str(c._raw.get("release_date", "")),
            "company": c.company, "tags": c.tags, "aliases": c.aliases,
            "timeline": c.timeline,
            "color": TYPE_COLORS.get(c.type, "#999"),
        }
        upsert_entity(entity)

    # Relationships — only if both sides exist
    entity_ids = {c.id for c in cards}
    rel_count = skipped = 0
    for c in cards:
        for target in c.related:
            if target in entity_ids:
                upsert_relationship(c.id, target, "related", "关联"); rel_count += 1
            else: skipped += 1
        for target in c.depends_on:
            if target in entity_ids:
                upsert_relationship(c.id, target, "depends_on", "依赖"); rel_count += 1
            else: skipped += 1
        for target in c.influenced:
            if target in entity_ids:
                upsert_relationship(c.id, target, "influenced", "影响"); rel_count += 1
            else: skipped += 1

    log.info(f"  {len(cards)} entities, {rel_count} relationships ({skipped} skipped)")


def migrate_inbox():
    inbox_path = ROOT_DIR / "data" / "inbox.jsonl"
    if not inbox_path.exists():
        log.info("无 inbox 数据")
        return

    articles = []
    with open(inbox_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                a = json.loads(line)
                articles.append(a)
            except json.JSONDecodeError:
                pass

    if articles:
        insert_articles(articles)
        log.info(f"迁移 {len(articles)} 篇文章 → SQLite")


if __name__ == "__main__":
    init_db()
    migrate_cards()
    migrate_inbox()
    log.info("迁移完成")
