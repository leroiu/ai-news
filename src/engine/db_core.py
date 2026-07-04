"""
数据库核心 — 连接管理 + Schema 初始化 + Row 转换器。

从 database.py 拆分出来，所有数据库子模块共享此文件。
"""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from .utils import log, ROOT_DIR

DB_PATH = ROOT_DIR / "data" / "platform.db"


def get_db() -> sqlite3.Connection:
    """获取数据库连接（自动创建表）。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化所有表。"""
    conn = get_db()
    conn.executescript("""
    -- 实体 (Knowledge Cards)
    CREATE TABLE IF NOT EXISTS entities (
        id          TEXT PRIMARY KEY,
        name        TEXT NOT NULL,
        type        TEXT NOT NULL,
        importance  INTEGER DEFAULT 3,
        summary     TEXT DEFAULT '',
        significance TEXT DEFAULT '',
        release_date TEXT DEFAULT '',
        company     TEXT DEFAULT '',
        tags        TEXT DEFAULT '[]',
        aliases     TEXT DEFAULT '[]',
        timeline    TEXT DEFAULT '[]',
        color       TEXT DEFAULT '#999',
        created_at  TEXT DEFAULT (datetime('now')),
        updated_at  TEXT DEFAULT (datetime('now'))
    );

    -- 关系
    CREATE TABLE IF NOT EXISTS relationships (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id   TEXT NOT NULL,
        target_id   TEXT NOT NULL,
        rel_type    TEXT NOT NULL,
        label       TEXT DEFAULT '',
        FOREIGN KEY (source_id) REFERENCES entities(id),
        FOREIGN KEY (target_id) REFERENCES entities(id),
        UNIQUE(source_id, target_id, rel_type)
    );

    -- 文章
    CREATE TABLE IF NOT EXISTS articles (
        id          TEXT PRIMARY KEY,
        title       TEXT NOT NULL,
        url         TEXT NOT NULL,
        source      TEXT DEFAULT '',
        published   TEXT DEFAULT '',
        content_raw TEXT DEFAULT '',
        categories  TEXT DEFAULT '[]',
        title_cn    TEXT DEFAULT '',
        one_liner   TEXT DEFAULT '',
        summary_points TEXT DEFAULT '[]',
        score       INTEGER DEFAULT 0,
        score_reason TEXT DEFAULT '',
        cluster_id  TEXT DEFAULT '',
        created_at  TEXT DEFAULT (datetime('now'))
    );

    -- 报告
    CREATE TABLE IF NOT EXISTS reports (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        date        TEXT NOT NULL UNIQUE,
        report_type TEXT DEFAULT 'daily',
        path        TEXT NOT NULL,
        fetched     INTEGER DEFAULT 0,
        filtered    INTEGER DEFAULT 0,
        star5       INTEGER DEFAULT 0,
        star4       INTEGER DEFAULT 0,
        star3       INTEGER DEFAULT 0,
        created_at  TEXT DEFAULT (datetime('now'))
    );

    -- 嵌入向量（语义搜索）
    CREATE TABLE IF NOT EXISTS embeddings (
        id          TEXT PRIMARY KEY,
        dims        INTEGER NOT NULL,
        vector      TEXT NOT NULL,
        updated_at  TEXT DEFAULT (datetime('now'))
    );

    -- 用户
    CREATE TABLE IF NOT EXISTS users (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        username     TEXT NOT NULL UNIQUE,
        email        TEXT DEFAULT '',
        password_hash TEXT NOT NULL,
        role         TEXT NOT NULL DEFAULT 'user',
        created_at   TEXT DEFAULT (datetime('now'))
    );

    -- 收藏
    CREATE TABLE IF NOT EXISTS favorites (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL,
        item_type   TEXT NOT NULL,
        item_id     TEXT NOT NULL,
        created_at  TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id),
        UNIQUE(user_id, item_type, item_id)
    );

    -- 阅读历史
    CREATE TABLE IF NOT EXISTS reading_history (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL,
        article_id  TEXT NOT NULL,
        read_at     TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id),
        UNIQUE(user_id, article_id)
    );

    -- Pipeline 运行日志
    CREATE TABLE IF NOT EXISTS pipeline_runs (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        run_type    TEXT NOT NULL DEFAULT 'daily',
        status      TEXT NOT NULL DEFAULT 'running',
        articles_total  INTEGER DEFAULT 0,
        articles_processed INTEGER DEFAULT 0,
        duration_seconds REAL DEFAULT 0,
        error_message TEXT DEFAULT '',
        started_at  TEXT DEFAULT (datetime('now')),
        ended_at    TEXT DEFAULT ''
    );

    -- Collector 运行日志
    CREATE TABLE IF NOT EXISTS collector_runs (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        status      TEXT NOT NULL DEFAULT 'success',
        fetched     INTEGER DEFAULT 0,
        new_articles INTEGER DEFAULT 0,
        duration_seconds REAL DEFAULT 0,
        error_message TEXT DEFAULT '',
        started_at  TEXT DEFAULT (datetime('now'))
    );

    -- 实体版本历史
    CREATE TABLE IF NOT EXISTS entity_versions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_id   TEXT NOT NULL,
        version_number INTEGER NOT NULL,
        data        TEXT NOT NULL DEFAULT '{}',
        changed_fields TEXT DEFAULT '',
        created_at  TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE
    );

    -- 数据库迁移记录
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version     TEXT PRIMARY KEY,
        applied_at  TEXT DEFAULT (datetime('now'))
    );

    -- 索引
    CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started ON pipeline_runs(started_at);
    CREATE INDEX IF NOT EXISTS idx_collector_runs_started ON collector_runs(started_at);
    CREATE INDEX IF NOT EXISTS idx_embeddings_id ON embeddings(id);
    CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
    CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source_id);
    CREATE INDEX IF NOT EXISTS idx_relationships_target ON relationships(target_id);
    CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published);
    CREATE INDEX IF NOT EXISTS idx_articles_score ON articles(score);
    CREATE INDEX IF NOT EXISTS idx_reports_date ON reports(date);
    CREATE INDEX IF NOT EXISTS idx_entity_versions_entity_id ON entity_versions(entity_id);
    CREATE INDEX IF NOT EXISTS idx_entity_versions_created ON entity_versions(created_at);

    -- FTS5 全文搜索（实体）
    CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts USING fts5(
        entity_id UNINDEXED, name, summary, significance
    );

    -- FTS5 全文搜索（文章）
    CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
        article_id UNINDEXED, title, title_cn, one_liner
    );
    """)
    conn.commit()
    conn.close()
    log.debug(f"数据库已初始化: {DB_PATH}")


def rebuild_fts():
    """重建所有 FTS5 索引。在批量数据变更后调用。"""
    conn = get_db()
    # 实体 FTS
    conn.execute("DELETE FROM entities_fts")
    conn.executescript("""
        INSERT INTO entities_fts(entity_id, name, summary, significance)
        SELECT id, name, summary, significance FROM entities;
    """)
    # 文章 FTS
    conn.execute("DELETE FROM articles_fts")
    conn.executescript("""
        INSERT INTO articles_fts(article_id, title, title_cn, one_liner)
        SELECT id, title, title_cn, one_liner FROM articles;
    """)
    conn.commit()
    conn.close()


def _normalize_timeline(timeline: list) -> list:
    """归一化 timeline 中的 date 字段为字符串。

    YAML 中 date: 2024 会被解析为 int，需统一转为 str。
    支持 YYYY / YYYY-MM / YYYY-MM-DD 三种格式。
    """
    if not timeline:
        return timeline
    for event in timeline:
        if isinstance(event, dict):
            d = event.get("date")
            if d is not None and not isinstance(d, str):
                event["date"] = str(d)
    return timeline


def _row_to_entity(r: sqlite3.Row) -> dict:
    """将 SQLite Row 转换为 entity dict，自动解析 JSON 字段并归一化 timeline 日期。"""
    d = dict(r)
    for f in ("tags", "aliases", "timeline"):
        try:
            d[f] = json.loads(d.get(f, "[]"))
        except (json.JSONDecodeError, TypeError):
            d[f] = []
    # 归一化 timeline date 类型 (int → str)
    d["timeline"] = _normalize_timeline(d["timeline"])
    return d


def _row_to_article(r: sqlite3.Row) -> dict:
    """将 SQLite Row 转换为 article dict，自动解析 JSON 字段。"""
    d = dict(r)
    for f in ("categories", "summary_points"):
        try:
            d[f] = json.loads(d.get(f, "[]"))
        except (json.JSONDecodeError, TypeError):
            d[f] = []
    return d
