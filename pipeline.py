#!/usr/bin/env python3
"""
AI News — 主控管道

每天运行一次，从 inbox 读取文章并生成日报：
  Fetcher → Dedup → Classify → Summarize → Score → Reporter

用法:
  python pipeline.py                      # 从 inbox 读取，生成日报（默认）
  python pipeline.py --fetch-direct       # 直接从 RSS 抓取（回退模式）
  python pipeline.py --dry-run            # 只抓取+去重，不调 AI
  python pipeline.py --no-cache           # 不使用去重缓存（开发调试用）
  python pipeline.py --hours 24           # 只处理 inbox 中近 24 小时的文章
  python pipeline.py --limit 10           # 只处理 10 篇（默认不限制）
  python pipeline.py --only-unprocessed   # 跳过已有评分/摘要的文章
  python pipeline.py --concurrency 3      # AI 摘要并发数（默认 3）
  python pipeline.py --weekly             # 生成周报（汇总过去 7 天日报）
  python pipeline.py --monthly            # 生成月报（汇总过去 30 天日报）
  python pipeline.py --graph              # 生成知识图谱（Mermaid + HTML）
  python pipeline.py --dashboard          # 生成平台 Dashboard 首页
  python pipeline.py --library            # 生成知识资产库 Library
  python pipeline.py --timeline           # 生成 AI 时间线页面
"""

import asyncio
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# 确保项目根在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.engine.utils import log, setup_logging, load_config, read_inbox
from src.engine.fetcher import fetch_all
from src.engine.dedup import deduplicate
from src.engine.classifier import classify
from src.engine.summarizer import summarize
from src.engine.scorer import score
from src.engine.reporter import generate_report
from src.engine.knowledge import load_cards, match_cards, build_context
from src.engine.trend_reporter import generate_trend_report
from src.knowledge_graph import build_graph, generate_mermaid_report, generate_html
from src.engine.concept_miner import mine_concepts, update_pool, get_pool_summary
from src.frontend.dashboard import generate_dashboard
from src.frontend.library import generate_library
from src.timeline import generate_timeline
from src.frontend.reports_page import generate_reports_page
from src.research import generate_research_page
from src.engine.database import init_db, insert_articles, insert_report, start_pipeline_run, finish_pipeline_run
from src.engine.cache import apply_cache, save_results

# ── 计时工具 ──
_stage_times: dict[str, float] = {}

def _tick() -> float:
    return time.time()

def _log_stage(name: str, elapsed: float):
    _stage_times[name] = elapsed
    log.info(f"  ⏱ {name}: {elapsed:.1f}s")


def main() -> int:
    setup_logging("INFO")
    t0 = _tick()
    log.info("=" * 50)
    log.info("AI News Pipeline 启动")
    log.info("=" * 50)

    # ── 参数解析 ──
    dry_run = "--dry-run" in sys.argv
    fetch_direct = "--fetch-direct" in sys.argv
    weekly = "--weekly" in sys.argv
    monthly = "--monthly" in sys.argv
    gen_graph = "--graph" in sys.argv
    gen_dashboard = "--dashboard" in sys.argv
    gen_library = "--library" in sys.argv
    gen_timeline = "--timeline" in sys.argv
    only_unprocessed = "--only-unprocessed" in sys.argv

    # --limit N (支持 --limit=10 和 --limit 10 两种格式)
    limit: int | None = None
    for i, arg in enumerate(sys.argv):
        if arg.startswith("--limit="):
            try: limit = int(arg.split("=")[1])
            except ValueError: pass
        elif arg == "--limit" and i + 1 < len(sys.argv):
            try: limit = int(sys.argv[i + 1])
            except ValueError: pass

    # --concurrency N (默认 3)
    concurrency = 3
    for i, arg in enumerate(sys.argv):
        if arg.startswith("--concurrency="):
            try: concurrency = int(arg.split("=")[1])
            except ValueError: pass
        elif arg == "--concurrency" and i + 1 < len(sys.argv):
            try: concurrency = int(sys.argv[i + 1])
            except ValueError: pass

    # ---- Timeline 分支 ----
    if gen_timeline:
        log.info("模式: Timeline 生成")
        t1 = _tick()
        path = generate_timeline()
        _log_stage("timeline", _tick() - t1)
        log.info(f"Timeline 生成完成 ({_tick() - t0:.1f}s): {path}")
        return 0

    # ---- Library 分支 ----
    if gen_library:
        log.info("模式: Library 生成")
        t1 = _tick()
        path = generate_library()
        _log_stage("library", _tick() - t1)
        log.info(f"Library 生成完成 ({_tick() - t0:.1f}s): {path}")
        return 0

    # ---- Dashboard 分支 ----
    if gen_dashboard:
        log.info("模式: Dashboard 生成")
        t1 = _tick()
        path = generate_dashboard()
        _log_stage("dashboard", _tick() - t1)
        log.info(f"Dashboard 生成完成 ({_tick() - t0:.1f}s): {path}")
        return 0

    # ---- 知识图谱分支 ----
    if gen_graph:
        log.info("模式: 知识图谱生成")
        t1 = _tick()
        graph = build_graph()
        stats = graph["stats"]
        log.info(f"  节点: {stats['total_nodes']}, 边: {stats['total_edges']}, 连通分量: {stats['components']}")
        md_path = generate_mermaid_report(graph)
        html_path = generate_html(graph)
        _log_stage("graph", _tick() - t1)
        log.info(f"图谱生成完成 ({_tick() - t0:.1f}s)")
        return 0

    # ---- 周报/月报分支 ----
    if weekly or monthly:
        period = "week" if weekly else "month"
        log.info(f"模式: {'周报' if weekly else '月报'}")
        if not os.getenv("DEEPSEEK_API_KEY"):
            log.error("未设置 DEEPSEEK_API_KEY")
            return 1
        t1 = _tick()
        report_path = generate_trend_report(period=period)
        _log_stage("trend_report", _tick() - t1)
        if report_path:
            init_db()
            from datetime import date as dt_date
            today = dt_date.today()
            report_date = today.isoformat() if weekly else today.replace(day=1).isoformat()
            insert_report(date=report_date, report_type=period, path=str(report_path))
            log.info(f"{'周报' if weekly else '月报'}完成 ({_tick() - t0:.1f}s): {report_path}")
            return 0
        else:
            log.error("生成失败")
            return 1

    if dry_run:
        log.info("模式: DRY RUN (不调用 AI)")

    # ── Pipeline 运行追踪 ──
    run_id = start_pipeline_run("daily")
    pipeline_error = ""

    # ── 数据获取 ──
    t_fetch = _tick()
    if fetch_direct:
        log.info("数据源: RSS 直接抓取")
        if not dry_run and not os.getenv("DEEPSEEK_API_KEY"):
            log.error("未设置 DEEPSEEK_API_KEY")
            return 1
        articles = asyncio.run(fetch_all())
        fetched_count = len(articles)
        if not articles:
            log.warning("没有抓取到文章")
            return 0
        log.info(f"  → {len(articles)} 篇原始文章")
        articles = deduplicate(articles, skip_cache="--no-cache" in sys.argv)
        log.info(f"  → {len(articles)} 篇去重后")
    else:
        config = load_config()
        max_hours = config.get("fetch", {}).get("max_age_hours", 72)
        for arg in sys.argv:
            if arg.startswith("--hours="):
                try: max_hours = int(arg.split("=")[1])
                except ValueError: pass
        log.info(f"数据源: inbox.jsonl (近 {max_hours}h)")
        articles = read_inbox(since_hours=max_hours)
        fetched_count = len(articles)
        log.info(f"  → inbox 中 {len(articles)} 篇待分析")

    _log_stage("fetch+dedup", _tick() - t_fetch)

    if not articles:
        log.warning("没有文章，管道终止")
        finish_pipeline_run(run_id, "success", 0, _tick() - t0)
        return 0

    if dry_run:
        log.info(f"Dry run 完成 ({_tick() - t0:.1f}s)，共 {len(articles)} 篇待处理")
        for a in sorted(articles, key=lambda x: x.published or "", reverse=True)[:10]:
            log.info(f"  [{a.source}] {a.title[:80]}")
        finish_pipeline_run(run_id, "dry_run", len(articles), _tick() - t0)
        return 0

    # ── 跳过已处理文章 ──
    if only_unprocessed:
        before = len(articles)
        articles = [a for a in articles if not (a.score > 0 and a.title_cn)]
        skipped = before - len(articles)
        if skipped:
            log.info(f"  ⏭ 跳过 {skipped} 篇已处理 (score>0 & has title_cn)")

    # ── --limit 截断 ──
    if limit and len(articles) > limit:
        log.info(f"  🔢 --limit={limit}: {len(articles)} → {limit} 篇")
        articles = articles[:limit]

    # ── 缓存恢复 ──
    cache_hits = apply_cache(articles)
    if cache_hits:
        log.info(f"  📦 缓存命中: {cache_hits}/{len(articles)} 篇")

    # ── Classify (只处理未分类的) ──
    t1 = _tick()
    unclassified = [a for a in articles if not a.categories]
    if unclassified:
        classify(unclassified)
    _log_stage("classify", _tick() - t1)

    # ── Concept Miner ──
    t1 = _tick()
    candidates = mine_concepts(articles, batch_size=20)
    if candidates:
        actions = update_pool(candidates, articles)
        log.info(f"  → {len(candidates)} 个候选, {len(actions)} 项操作")
    _log_stage("concept_mine", _tick() - t1)

    # ── Knowledge Match ──
    t1 = _tick()
    cards = load_cards()
    knowledge_context = ""
    if cards:
        matched = match_cards(articles, cards, use_semantic=True)
        knowledge_context = build_context(matched)
        hits = sum(1 for v in matched.values() if v)
        log.info(f"  → {hits}/{len(articles)} 篇匹配到卡片")
    _log_stage("knowledge_match", _tick() - t1)

    # ── Summarize (只处理无摘要的，可并发) ──
    t1 = _tick()
    unsummarized = [a for a in articles if not a.title_cn]
    if unsummarized:
        log.info(f"  需摘要: {len(unsummarized)}/{len(articles)} 篇")
        summarize(unsummarized, knowledge_context=knowledge_context, concurrency=concurrency)
    else:
        log.info(f"  摘要: 全部已缓存，跳过")
    _log_stage("summarize", _tick() - t1)

    # ── Score (只处理未评分的) ──
    t1 = _tick()
    unscored = [a for a in articles if a.score == 0]
    if unscored:
        log.info(f"  需评分: {len(unscored)}/{len(articles)} 篇")
        score(unscored)
    else:
        log.info(f"  评分: 全部已缓存，跳过")
    _log_stage("score", _tick() - t1)

    # ── 保存缓存 ──
    save_results(articles)

    # ── Generate Report ──
    t1 = _tick()
    config = load_config()
    min_score = config.get("output", {}).get("min_score", 3)
    report_path = generate_report(articles, fetched_count=fetched_count, min_score=min_score)
    _log_stage("write_report", _tick() - t1)

    # ── Sync DB ──
    t1 = _tick()
    init_db()
    article_dicts = [a.to_dict() for a in articles]
    insert_articles(article_dicts)
    insert_report(
        date=datetime.now().strftime("%Y-%m-%d"),
        report_type="daily", path=str(report_path),
        fetched=fetched_count, filtered=len(articles),
        star5=sum(1 for a in articles if a.score == 5),
        star4=sum(1 for a in articles if a.score == 4),
        star3=sum(1 for a in articles if a.score == 3),
    )
    _log_stage("update_db", _tick() - t1)

    # ── Render Pages ──
    t1 = _tick()
    generate_dashboard()
    generate_library()
    generate_timeline()
    generate_reports_page()
    generate_research_page()
    _log_stage("render_pages", _tick() - t1)

    # ── 完成 ──
    total = _tick() - t0

    def count(s): return sum(1 for a in articles if a.score == s)
    log.info("=" * 50)
    log.info(f"管道完成 ({total:.1f}s)")
    log.info(f"  文章: {len(articles)} 条 | ★5:{count(5)} ★4:{count(4)} ★3:{count(3)} ★2:{count(2)} ★1:{count(1)}")
    log.info(f"  日报: {report_path}")
    log.info(f"  耗时明细: {' | '.join(f'{k}={v:.1f}s' for k, v in _stage_times.items())}")

    finish_pipeline_run(run_id, "success", len(articles), total)
    log.info("=" * 50)

    return 0


if __name__ == "__main__":
    sys.exit(main())
