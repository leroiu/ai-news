"""
Pipeline / Collector 运行追踪 + 健康检查。

从 database.py 拆分出来。
"""

from typing import Optional

from .db_core import get_db


# ═══════════════════════════════════════════════════════════════
# Pipeline Runs
# ═══════════════════════════════════════════════════════════════

def start_pipeline_run(run_type: str = "daily", articles_total: int = 0) -> int:
    """开始一次 pipeline 运行，返回 run_id。"""
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO pipeline_runs (run_type, status, articles_total) "
        "VALUES (?, 'running', ?)",
        (run_type, articles_total)
    )
    conn.commit()
    run_id = cur.lastrowid
    conn.close()
    return run_id


def finish_pipeline_run(run_id: int, status: str = "success",
                        articles_processed: int = 0, duration: float = 0,
                        error: str = ""):
    """结束一次 pipeline 运行。"""
    conn = get_db()
    conn.execute("""
        UPDATE pipeline_runs
        SET status=?, articles_processed=?, duration_seconds=?,
            error_message=?, ended_at=datetime('now')
        WHERE id=?
    """, (status, articles_processed, duration, error, run_id))
    conn.commit()
    conn.close()


def get_pipeline_runs(limit: int = 10) -> list[dict]:
    """获取最近的 pipeline 运行记录。"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_pipeline_run(run_id: int, articles_processed: int = 0,
                         error_message: str = ""):
    """增量更新 pipeline 运行状态（用于长时间运行的 pipeline）。"""
    conn = get_db()
    if error_message:
        conn.execute(
            "UPDATE pipeline_runs SET articles_processed=?, error_message=? WHERE id=?",
            (articles_processed, error_message, run_id)
        )
    else:
        conn.execute(
            "UPDATE pipeline_runs SET articles_processed=? WHERE id=?",
            (articles_processed, run_id)
        )
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════
# Collector Runs
# ═══════════════════════════════════════════════════════════════

def log_collector_run(fetched: int = 0, new_articles: int = 0,
                      duration: float = 0, error: str = ""):
    """记录一次 collector 运行。"""
    status = "error" if error else "success"
    conn = get_db()
    conn.execute("""
        INSERT INTO collector_runs (status, fetched, new_articles,
            duration_seconds, error_message)
        VALUES (?, ?, ?, ?, ?)
    """, (status, fetched, new_articles, duration, error))
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════
# Health
# ═══════════════════════════════════════════════════════════════

def get_health() -> dict:
    """健康检查：DB 状态 + 最后运行时间 + 基本统计。"""
    try:
        conn = get_db()
        # 基本统计
        entities = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        reports = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]

        # 最后一次 pipeline 运行
        last_pipeline = conn.execute("""
            SELECT run_type, status, articles_total, articles_processed,
                   duration_seconds, error_message, started_at, ended_at
            FROM pipeline_runs ORDER BY id DESC LIMIT 1
        """).fetchone()

        # 最后一次 collector 运行
        last_collector = conn.execute("""
            SELECT status, fetched, new_articles, duration_seconds, started_at
            FROM collector_runs ORDER BY id DESC LIMIT 1
        """).fetchone()

        # 最近 24 小时 pipeline 成功率
        success_rate = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as ok
            FROM pipeline_runs
            WHERE started_at > datetime('now', '-1 day')
        """).fetchone()

        conn.close()

        return {
            "status": "ok",
            "db": {"entities": entities, "articles": articles, "reports": reports},
            "last_pipeline": dict(last_pipeline) if last_pipeline else None,
            "last_collector": dict(last_collector) if last_collector else None,
            "recent_success_rate": {
                "total": success_rate["total"],
                "success": success_rate["ok"],
            } if success_rate["total"] > 0 else None,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
