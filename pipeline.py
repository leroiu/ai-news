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
  python pipeline.py --resume             # 从上次中断处续跑（断点续跑）
  python pipeline.py --reset-checkpoint   # 清除断点，从头开始
"""

import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

# 确保项目根在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.engine.utils import log, setup_logging
from src.engine.database import (
    init_db, start_pipeline_run, finish_pipeline_run, update_pipeline_run,
)
from src.frontend.dashboard import generate_dashboard
from src.frontend.library import generate_library
from src.timeline import generate_timeline
from pipeline_utils import (
    _tick, _log_stage, _stage_times, _failed_articles,
    load_checkpoint, clear_checkpoint,
)
from pipeline_stages import (
    run_trend_report, run_daily_pipeline,
)


# ═══════════════════════════════════════════════════════════════
# 单页面生成
# ═══════════════════════════════════════════════════════════════

def _run_single_page(mode: str) -> tuple[bool, str]:
    """运行单页面生成模式，返回 (success, message)。"""
    generators = {
        "timeline": ("Timeline", generate_timeline),
        "library": ("Library", generate_library),
        "dashboard": ("Dashboard", generate_dashboard),
    }

    if mode in generators:
        label, fn = generators[mode]
        t1 = _tick()
        path = fn()
        _log_stage(mode, _tick() - t1)
        return True, f"{label} 生成完成: {path}"

    if mode == "graph":
        from src.knowledge_graph import build_graph, generate_mermaid_report, generate_html
        t1 = _tick()
        graph = build_graph()
        stats = graph["stats"]
        log.info(f"  节点: {stats['total_nodes']}, 边: {stats['total_edges']}, "
                 f"连通分量: {stats['components']}")
        generate_mermaid_report(graph)
        generate_html(graph)
        _log_stage("graph", _tick() - t1)
        return True, "图谱生成完成"

    return False, f"未知模式: {mode}"


# ═══════════════════════════════════════════════════════════════
# 参数解析
# ═══════════════════════════════════════════════════════════════

def _parse_args() -> dict:
    """解析 CLI 参数，返回 dict。"""
    args = {
        "dry_run": "--dry-run" in sys.argv,
        "fetch_direct": "--fetch-direct" in sys.argv,
        "weekly": "--weekly" in sys.argv,
        "monthly": "--monthly" in sys.argv,
        "gen_graph": "--graph" in sys.argv,
        "gen_dashboard": "--dashboard" in sys.argv,
        "gen_library": "--library" in sys.argv,
        "gen_timeline": "--timeline" in sys.argv,
        "only_unprocessed": "--only-unprocessed" in sys.argv,
        "do_resume": "--resume" in sys.argv,
        "reset_checkpoint": "--reset-checkpoint" in sys.argv,
        "report_date": None,
        "limit": None,
        "concurrency": 3,
    }

    # --date YYYY-MM-DD
    for i, arg in enumerate(sys.argv):
        if arg.startswith("--date="):
            args["report_date"] = arg.split("=")[1]
        elif arg == "--date" and i + 1 < len(sys.argv):
            args["report_date"] = sys.argv[i + 1]

    # --limit N
    for i, arg in enumerate(sys.argv):
        if arg.startswith("--limit="):
            try:
                args["limit"] = int(arg.split("=")[1])
            except ValueError:
                pass
        elif arg == "--limit" and i + 1 < len(sys.argv):
            try:
                args["limit"] = int(sys.argv[i + 1])
            except ValueError:
                pass

    # --concurrency N
    for i, arg in enumerate(sys.argv):
        if arg.startswith("--concurrency="):
            try:
                args["concurrency"] = int(arg.split("=")[1])
            except ValueError:
                pass
        elif arg == "--concurrency" and i + 1 < len(sys.argv):
            try:
                args["concurrency"] = int(sys.argv[i + 1])
            except ValueError:
                pass

    return args


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

def main() -> int:
    setup_logging("INFO")
    t0 = _tick()
    log.info("=" * 50)
    log.info("AI News Pipeline 启动")
    log.info("=" * 50)

    args = _parse_args()

    if args["reset_checkpoint"]:
        clear_checkpoint()
        log.info("断点已清除，从头开始")

    # ── 断点续跑 ──
    checkpoint = None
    if args["do_resume"] and not args["reset_checkpoint"]:
        checkpoint = load_checkpoint()
        if checkpoint:
            log.info(f"📌 断点续跑: 已完成 {checkpoint['completed_stages']}, "
                     f"从 [{checkpoint['stage']}] 恢复")
            log.info(f"   原始启动: {checkpoint.get('started_at', 'unknown')}")
        else:
            log.warning("未找到断点文件，从头开始")

    # ── 单页面生成分支 ──
    for mode in ["timeline", "library", "dashboard", "graph"]:
        if args[f"gen_{mode}"]:
            log.info(f"模式: {mode.title()} 生成")
            try:
                ok, msg = _run_single_page(mode)
                log.info(f"{msg} ({_tick() - t0:.1f}s)")
                return 0 if ok else 1
            except Exception as e:
                log.error(f"{mode.title()} 生成失败: {e}")
                return 1

    # ── 周报/月报分支 ──
    if args["weekly"] or args["monthly"]:
        period = "week" if args["weekly"] else "month"
        log.info(f"模式: {'周报' if args['weekly'] else '月报'}")
        t1 = _tick()
        try:
            ok, msg = run_trend_report(period)
            _log_stage("trend_report", _tick() - t1)
            total = _tick() - t0
            if ok:
                log.info(f"{'周报' if args['weekly'] else '月报'}完成 ({total:.1f}s): {msg}")
                return 0
            else:
                log.error(msg)
                return 1
        except Exception as e:
            log.error(f"{'周报' if args['weekly'] else '月报'}生成失败: {e}")
            return 1

    # ── Dry Run ──
    if args["dry_run"]:
        log.info("模式: DRY RUN (不调用 AI)")
        # Fall through to fetch+dedup only, then exit early in run_daily_pipeline

    # ── Pipeline 运行追踪 ──
    run_id = start_pipeline_run("daily")
    articles = []
    fetched_count = 0

    try:
        # ── 运行每日管道 ──
        articles, report_path, status = run_daily_pipeline(
            articles=articles,
            run_id=run_id,
            checkpoint=checkpoint,
            limit=args["limit"],
            only_unprocessed=args["only_unprocessed"],
            fetch_direct=args["fetch_direct"],
            concurrency=args["concurrency"],
            fetched_count=fetched_count,
            report_date=args["report_date"],
        )

        total = _tick() - t0

        # ── 处理 dry-run 提前退出 ──
        if "无文章" in status:
            clear_checkpoint()
            finish_pipeline_run(run_id, "success", 0, total)
            return 0

        if "error:" in status:
            error_msg = status.replace("error: ", "")
            finish_pipeline_run(run_id, "error", 0, total, error_msg)
            return 1

        if not articles:
            clear_checkpoint()
            finish_pipeline_run(run_id, "success", 0, total)
            return 0

        # ── 完成汇总 ──
        def count(s):
            return sum(1 for a in articles if a.score == s)

        log.info("=" * 50)
        log.info(f"管道完成 ({total:.1f}s)")
        log.info(f"  文章: {len(articles)} 条 | "
                 f"★5:{count(5)} ★4:{count(4)} ★3:{count(3)} "
                 f"★2:{count(2)} ★1:{count(1)}")
        if _failed_articles:
            failed_stages = len(_failed_articles)
            total_failures = sum(len(v) for v in _failed_articles.values())
            log.warning(f"  ⚠ 部分失败: {failed_stages} 个阶段, {total_failures} 个错误")
            for stage, errs in _failed_articles.items():
                log.warning(f"    [{stage}]: {'; '.join(errs[:3])}")
        if report_path:
            log.info(f"  日报: {report_path}")
        log.info(f"  耗时明细: {' | '.join(f'{k}={v:.1f}s' for k, v in _stage_times.items())}")

        clear_checkpoint()
        finish_pipeline_run(run_id, status, len(articles), total,
                            error="; ".join(
                                f"[{s}]: {e}"
                                for s, errs in _failed_articles.items()
                                for e in errs[:2]
                            ) if _failed_articles else "")
        log.info("=" * 50)
        return 0

    except Exception as e:
        # ── 致命错误处理 ──
        total = _tick() - t0
        log.error("=" * 50)
        log.error(f"管道中止: {e}")
        log.error(traceback.format_exc())
        log.error("=" * 50)
        log.info("💡 修复问题后运行: python pipeline.py --resume")
        finish_pipeline_run(run_id, "error", len(articles), total, str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
