#!/usr/bin/env python3
"""
AI News — 冷数据归档脚本

将 90 天前的旧文章从主数据库归档到压缩 JSONL 文件。
归档后清理元数据 - 只保留 URL/标题/来源/评分，清除原文正文。
归档文件存储在 data/archive/YYYY-MM/articles.jsonl.gz。

幂等：已归档的月份不会重复归档。
安全：默认 dry-run 模式，预览待归档数据。
"""

import argparse
import json
import gzip
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 确保项目根在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.engine.utils import log, setup_logging, ROOT_DIR
from src.engine.db_core import get_db


ARCHIVE_DIR = ROOT_DIR / "data" / "archive"
DRY_RUN = False


def _get_old_articles(days: int = 90):
    """查询超过 N 天的旧文章。只返回元数据字段，不返回 content_raw。"""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    conn = get_db()
    rows = conn.execute("""
        SELECT id, title, url, source, published, categories,
               title_cn, one_liner, summary_points, score, score_reason
        FROM articles
        WHERE published < ?
        ORDER BY published ASC
    """, (cutoff,)).fetchall()
    conn.close()

    articles = []
    for r in rows:
        articles.append({
            "id": r[0],
            "title": r[1],
            "url": r[2],
            "source": r[3],
            "published": r[4],
            "categories": r[5],
            "title_cn": r[6],
            "one_liner": r[7],
            "summary_points": r[8],
            "score": r[9],
            "score_reason": r[10],
        })
    return articles


def _group_by_month(articles: list[dict]) -> dict[str, list[dict]]:
    """按 YYYY-MM 分组。"""
    groups: dict[str, list[dict]] = {}
    for a in articles:
        pub = a.get("published", "")
        month = pub[:7] if len(pub) >= 7 else "unknown"
        if month not in groups:
            groups[month] = []
        groups[month].append(a)
    return groups


def _archive_month(month: str, articles: list[dict]) -> Path:
    """将一个月的数据归档为 JSONL.GZ 文件。返回路径。"""
    month_dir = ARCHIVE_DIR / month
    month_dir.mkdir(parents=True, exist_ok=True)
    archive_path = month_dir / "articles.jsonl.gz"

    with gzip.open(archive_path, "wt", encoding="utf-8") as f:
        for a in articles:
            f.write(json.dumps(a, ensure_ascii=False, default=str) + "\n")

    return archive_path


def _cleanup_db(article_ids: list[str]) -> int:
    """清除已归档文章的 content_raw，释放空间。返回清理条数。"""
    if not article_ids:
        return 0

    conn = get_db()
    # 分批更新，避免 SQL 过长
    batch_size = 100
    total = 0
    for i in range(0, len(article_ids), batch_size):
        batch = article_ids[i:i + batch_size]
        placeholders = ",".join("?" * len(batch))
        conn.execute(f"""
            UPDATE articles
            SET content_raw = ''
            WHERE id IN ({placeholders})
              AND content_raw != ''
        """, batch)
        total += conn.total_changes
    conn.commit()
    conn.close()
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description="归档 90 天前的旧文章")
    parser.add_argument("--days", type=int, default=90, help="归档阈值（天，默认 90）")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不执行")
    args = parser.parse_args()

    setup_logging("INFO")
    global DRY_RUN
    DRY_RUN = args.dry_run

    articles = _get_old_articles(args.days)
    if not articles:
        log.info(f"无超过 {args.days} 天的旧文章需要归档")
        return 0

    groups = _group_by_month(articles)
    total = len(articles)
    log.info(f"待归档: {total} 篇，覆盖 {len(groups)} 个月")

    if DRY_RUN:
        log.info("DRY RUN — 不执行实际归档")
        for month in sorted(groups):
            log.info(f"  {month}: {len(groups[month])} 篇 → {ARCHIVE_DIR / month / 'articles.jsonl.gz'}")
        return 0

    all_ids: list[str] = []
    for month in sorted(groups):
        month_articles = groups[month]
        archive_path = _archive_month(month, month_articles)

        # 检查是否已有归档（幂等）
        existing_size = archive_path.stat().st_size if archive_path.exists() else 0
        if existing_size > 0:
            log.info(f"  {month}: 归档已存在({existing_size // 1024}KB)，跳过")
            continue

        log.info(f"  {month}: {len(month_articles)} 篇 → {archive_path}")
        all_ids.extend(a["id"] for a in month_articles)

    if all_ids:
        cleaned = _cleanup_db(all_ids)
        log.info(f"已清理 {cleaned} 篇正文（保留元数据+摘要）")

    log.info(f"归档完成: {total} 篇 → {ARCHIVE_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
