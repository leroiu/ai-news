"""
数据库迁移系统 — 扫描 + 幂等执行 SQL 迁移脚本。

从 database.py 拆分出来。
"""

from pathlib import Path
from typing import Optional

from .db_core import get_db
from .utils import log, ROOT_DIR


def get_applied_migrations() -> set[str]:
    """返回已应用的 migration 版本号集合。"""
    conn = get_db()
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    conn.close()
    return {r["version"] for r in rows}


def record_migration(version: str):
    """记录一个 migration 已应用。"""
    conn = get_db()
    conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
    conn.commit()
    conn.close()


def run_migrations(migrations_dir: Optional[str] = None) -> list[str]:
    """运行所有待执行的 SQL 迁移。返回新应用的迁移列表。"""
    if migrations_dir is None:
        migrations_dir = str(ROOT_DIR / "migrations")

    mig_path = Path(migrations_dir)
    if not mig_path.exists():
        return []

    applied = get_applied_migrations()
    new_migrations = []

    for sql_file in sorted(mig_path.glob("*.sql")):
        version = sql_file.stem
        if version in applied:
            continue
        conn = get_db()
        try:
            sql = sql_file.read_text(encoding="utf-8")
            conn.executescript(sql)
            conn.commit()
            record_migration(version)
            new_migrations.append(version)
            log.info(f"Migration applied: {version}")
        except Exception as e:
            log.error(f"Migration {version} failed: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    return new_migrations
