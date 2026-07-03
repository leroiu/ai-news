-- V001: 实体版本历史表 (已通过 init_db() 创建，此处为幂等迁移)
CREATE TABLE IF NOT EXISTS entity_versions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id   TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    data        TEXT NOT NULL DEFAULT '{}',
    changed_fields TEXT DEFAULT '',
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_entity_versions_entity_id ON entity_versions(entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_versions_created ON entity_versions(created_at);

-- V001: 迁移记录表
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    applied_at  TEXT DEFAULT (datetime('now'))
);
