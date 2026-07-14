#!/usr/bin/env python3
"""
AI News — 新闻收集器（无 AI 依赖）

每小时由 Windows Task Scheduler 触发运行：
  - 抓取所有 RSS 源
  - 去重（含历史缓存）
  - 追加写入 data/inbox.jsonl

用法:
  python collector.py                # 正常运行
  python collector.py --no-cache     # 不使用去重缓存（调试用）
"""

import asyncio
import sys
import time
from pathlib import Path

# 确保项目根在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.engine.utils import log, setup_logging, load_config, append_inbox
from src.engine.fetcher import fetch_all
from src.engine.dedup import deduplicate
from src.engine.db_core import init_db


def _safe_log_collector_run(fetched: int, new_articles: int, duration: float) -> None:
    """安全记录 collector 运行 — DB 不可用时静默跳过。"""
    try:
        from src.engine.database import log_collector_run
        log_collector_run(fetched=fetched, new_articles=new_articles, duration=duration)
    except Exception as e:
        log.warning(f"无法记录 collector 运行 (DB 不可用): {e}")


def main() -> int:
    setup_logging("INFO")
    start = time.time()

    # CI 环境中 DB 文件不存在，需要先初始化 schema
    try:
        init_db()
    except Exception as e:
        log.warning(f"DB 初始化失败 (非致命): {e}")

    skip_cache = "--no-cache" in sys.argv
    if skip_cache:
        log.info("⚠ 跳过去重缓存（--no-cache）")

    # ---- 1. 抓取 ----
    articles = asyncio.run(fetch_all())
    fetched_count = len(articles)
    if not articles:
        log.warning("没有抓取到任何文章")
        _safe_log_collector_run(fetched=0, new_articles=0, duration=time.time() - start)
        return 0
    log.info(f"抓取: {fetched_count} 篇")

    # ---- 2. 去重 ----
    articles = deduplicate(articles, skip_cache=skip_cache)
    log.info(f"去重后: {len(articles)} 篇新文章")

    if not articles:
        log.info("无新文章，跳过写入")
        elapsed = time.time() - start
        log.info(f"收集器完成 ({elapsed:.1f}s)")
        _safe_log_collector_run(fetched=fetched_count, new_articles=0, duration=elapsed)
        return 0

    # ---- 3. 写入 inbox ----
    inbox_path = append_inbox(articles)
    log.info(f"已写入 inbox: {inbox_path}")

    # ---- 4. 统计 ----
    sources = {}
    for a in articles:
        sources[a.source] = sources.get(a.source, 0) + 1
    log.info(f"来源分布: {sources}")

    elapsed = time.time() - start
    log.info(f"收集器完成 ({elapsed:.1f}s) — {len(articles)} 篇新文章入 inbox")
    _safe_log_collector_run(fetched=fetched_count, new_articles=len(articles), duration=elapsed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
