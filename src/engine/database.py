"""
AI Intelligence Platform — 统一数据层 (SQLite)

所有模块共享此数据库。本文件是 re-export shim — 实际实现在 db_*.py 子模块中。

拆分结构:
  db_core.py        — get_db, init_db, _row_to_entity, _row_to_article, DB_PATH
  db_entities.py    — Entity CRUD + 版本历史 + 分页
  db_relationships.py — Relationship CRUD + 图谱查询
  db_articles.py    — Article CRUD + 相似实体 + 分页
  db_pipeline.py    — Pipeline/Collector 追踪 + Health
  db_queries.py     — 报告 + 搜索 + 统计
  db_migrations.py  — 迁移系统

外部调用方无需修改 — 所有 import 路径保持不变。
"""

# ── Core ──
from .db_core import (
    DB_PATH, get_db, init_db, _row_to_entity, _row_to_article,
)

# ── Entities ──
from .db_entities import (
    upsert_entity, get_entities, get_entity, delete_entity,
    save_entity_version, get_entity_versions, get_entities_paginated,
    get_entities_cursor,
)

# ── Relationships ──
from .db_relationships import (
    upsert_relationship, get_relationships, delete_relationship,
    get_entity_neighbors, get_entity_relation_graph, verify_entity_ids,
)

# ── Articles ──
from .db_articles import (
    insert_articles, get_articles, get_article,
    get_articles_by_entity, get_similar_entities, get_articles_paginated,
    get_articles_cursor,
)

# ── Pipeline / Collector ──
from .db_pipeline import (
    start_pipeline_run, finish_pipeline_run, log_collector_run,
    get_pipeline_runs, update_pipeline_run, get_health,
)

# ── Queries ──
from .db_queries import (
    insert_report, get_reports, search, get_stats,
)

# ── Migrations ──
from .db_migrations import (
    get_applied_migrations, record_migration, run_migrations,
)
