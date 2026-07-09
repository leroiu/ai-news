#!/usr/bin/env python3
"""从数据库直接读取已处理文章，回溯生成历史日报。
用法:  uv run python tools/gen_history_reports.py 2026-07-01 2026-07-02
不加参数则自动查找所有文章日期并生成。
"""
import json, sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE if (_HERE / "src").exists() else _HERE.parent
sys.path.insert(0, str(ROOT))

from src.engine.db_core import get_db
from src.engine.fetcher import Article
from src.engine.reporter import generate_report
from src.engine.database import init_db, insert_report
from src.engine.utils import setup_logging, log


def dict_to_article(d: dict) -> Article:
    a = Article(
        id=d["id"], title=d.get("title", ""), url=d.get("url", ""),
        source=d.get("source", ""), published=d.get("published"),
        content_raw=d.get("content_raw", ""),
    )
    a.title_cn = d.get("title_cn", "") or ""
    a.one_liner = d.get("one_liner", "") or ""
    a.score = d.get("score", 0) or 0
    a.categories = d.get("categories", []) or []
    a.summary_points = d.get("summary_points", []) or []
    a.score_reason = d.get("score_reason", "") or ""
    return a


def backfill_daily(date_str: str):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM articles WHERE date(published)=? AND score>=3",
        (date_str,)
    ).fetchall()
    conn.close()

    articles = []
    for r in rows:
        d = dict(r)
        for f in ("categories", "summary_points"):
            try:
                d[f] = json.loads(d.get(f, "[]"))
            except (json.JSONDecodeError, TypeError):
                d[f] = []
        articles.append(dict_to_article(d))

    log.info(f"  {date_str}: {len(articles)} 篇 score>=3")
    if not articles:
        log.warning(f"  {date_str}: 无文章，跳过")
        return None

    report_path = generate_report(articles, fetched_count=0, report_date=date_str)
    init_db()
    insert_report(
        date=date_str, report_type="daily", path=str(report_path),
        fetched=0, filtered=len(articles),
        star5=sum(1 for a in articles if a.score == 5),
        star4=sum(1 for a in articles if a.score == 4),
        star3=sum(1 for a in articles if a.score == 3),
    )
    log.info(f"  ✅ 日报 {date_str}: {report_path}")
    return report_path


if __name__ == "__main__":
    setup_logging("INFO")

    if len(sys.argv) > 1:
        dates = sys.argv[1:]
    else:
        conn = get_db()
        rows = conn.execute(
            "SELECT DISTINCT date(published) as d FROM articles ORDER BY d"
        ).fetchall()
        conn.close()
        dates = [r["d"] for r in rows if r["d"]]

    log.info(f"回溯 {len(dates)} 天: {dates}")
    for d in dates:
        backfill_daily(d)

    # 尝试周报/月报
    from src.engine.trend_reporter import generate_trend_report
    for period in ["week", "month"]:
        log.info(f"生成{period}报...")
        try:
            path = generate_trend_report(period)
            if path:
                log.info(f"  ✅ {period}: {path}")
            else:
                log.warning(f"  ⏭ {period}: 日报不足，跳过")
        except Exception as e:
            log.error(f"  ❌ {period}: {e}")

    log.info("全部完成!")
