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

import asyncio
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

# 确保项目根在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.engine.utils import log, setup_logging, load_config, read_inbox, ROOT_DIR
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
from src.engine.concept_agent import update_pool_with_agent
from src.frontend.dashboard import generate_dashboard
from src.frontend.library import generate_library
from src.timeline import generate_timeline
from src.frontend.reports_page import generate_reports_page
from src.frontend.my_page import generate_my_page
from src.research import generate_research_page
from src.engine.database import (
    init_db, insert_articles, insert_report,
    start_pipeline_run, finish_pipeline_run, update_pipeline_run,
)
from src.engine.cache import apply_cache, save_results

# ── Checkpoint 文件 ──
CHECKPOINT_FILE = ROOT_DIR / "data" / ".pipeline_checkpoint.json"

# ── 计时工具 ──
_stage_times: dict[str, float] = {}
_failed_articles: dict[str, list[str]] = {}  # stage → [article_ids]


def _tick() -> float:
    return time.time()


def _log_stage(name: str, elapsed: float):
    _stage_times[name] = elapsed
    log.info(f"  ⏱ {name}: {elapsed:.1f}s")


# ═══════════════════════════════════════════════════════════════
# Checkpoint 系统
# ═══════════════════════════════════════════════════════════════

def _save_checkpoint(stage: str, article_ids: list[str], run_id: int,
                     extra: dict | None = None) -> None:
    """保存断点：当前阶段 + 文章列表 + 已完成阶段 + 失败记录。"""
    try:
        existing = {}
        if CHECKPOINT_FILE.exists():
            existing = json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8"))
        completed = existing.get("completed_stages", [])
        if stage not in completed:
            completed.append(stage)
        data = {
            "run_id": run_id,
            "stage": stage,
            "article_ids": article_ids,
            "completed_stages": completed,
            "failed_articles": _failed_articles,
            "stage_times": _stage_times,
            "started_at": existing.get("started_at", datetime.now().isoformat()),
            "updated_at": datetime.now().isoformat(),
        }
        if extra:
            data.update(extra)
        CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
        CHECKPOINT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:
        log.warning(f"保存断点失败: {e}")


def _load_checkpoint() -> dict | None:
    """加载断点文件。"""
    if not CHECKPOINT_FILE.exists():
        return None
    try:
        data = json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8"))
        # 恢复全局状态
        global _stage_times, _failed_articles
        _stage_times = data.get("stage_times", {})
        _failed_articles = data.get("failed_articles", {})
        return data
    except (json.JSONDecodeError, OSError) as e:
        log.warning(f"断点文件损坏，忽略: {e}")
        return None


def _clear_checkpoint() -> None:
    """清除断点文件。"""
    try:
        if CHECKPOINT_FILE.exists():
            CHECKPOINT_FILE.unlink()
    except OSError:
        pass


# ═══════════════════════════════════════════════════════════════
# 容错执行器
# ═══════════════════════════════════════════════════════════════

class StageError(Exception):
    """阶段级错误（非致命，可跳过继续）。"""
    pass


class FatalError(Exception):
    """致命错误（无法继续，需中止 pipeline）。"""
    pass


def _run_stage(name: str, articles: list, run_id: int,
               checkpoint: bool = True,
               allow_partial: bool = False) -> list:
    """执行一个阶段，带错误恢复和断点保存。

    - 非致命异常：记录到 _failed_articles，继续执行
    - 致命异常：保存断点后重新抛出
    - allow_partial: True 时，部分失败不影响后续阶段
    """
    article_ids = [a.id for a in articles] if articles else []
    if checkpoint and article_ids:
        _save_checkpoint(name, article_ids, run_id)

    try:
        yield  # 让调用方执行阶段逻辑
    except FatalError:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        log.error(f"阶段 [{name}] 异常: {e}")
        log.debug(tb)
        if allow_partial:
            log.warning(f"  → [{name}] 部分失败，继续执行后续阶段")
            _failed_articles.setdefault(name, []).append(str(e))
            update_pipeline_run(run_id, error_message=f"[{name}] {e}")
        else:
            _save_checkpoint(name, article_ids, run_id)
            update_pipeline_run(run_id, error_message=f"[{name}] {e}")
            raise StageError(f"阶段 [{name}] 失败: {e}")


def _skip_failed(articles: list, stage: str) -> list:
    """从文章列表中移除之前阶段已失败的。"""
    failed_ids: set[str] = set()
    for stage_name, errs in _failed_articles.items():
        if stage_name != stage:
            # 收集之前阶段失败的 article id
            pass  # per-article tracking done inside stages
    return articles


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

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
    do_resume = "--resume" in sys.argv
    reset_checkpoint = "--reset-checkpoint" in sys.argv

    if reset_checkpoint:
        _clear_checkpoint()
        log.info("断点已清除，从头开始")

    # --limit N
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

    # ── 断点续跑 ──
    checkpoint = None
    if do_resume and not reset_checkpoint:
        checkpoint = _load_checkpoint()
        if checkpoint:
            log.info(f"📌 断点续跑: 已完成 {checkpoint['completed_stages']}, "
                     f"从 [{checkpoint['stage']}] 恢复")
            log.info(f"   原始启动: {checkpoint.get('started_at', 'unknown')}")
        else:
            log.warning("未找到断点文件，从头开始")

    # ── 单页面生成分支（不需要 checkpoint） ──
    if gen_timeline:
        log.info("模式: Timeline 生成")
        t1 = _tick()
        try:
            path = generate_timeline()
            _log_stage("timeline", _tick() - t1)
            log.info(f"Timeline 生成完成 ({_tick() - t0:.1f}s): {path}")
            return 0
        except Exception as e:
            log.error(f"Timeline 生成失败: {e}")
            return 1

    if gen_library:
        log.info("模式: Library 生成")
        t1 = _tick()
        try:
            path = generate_library()
            _log_stage("library", _tick() - t1)
            log.info(f"Library 生成完成 ({_tick() - t0:.1f}s): {path}")
            return 0
        except Exception as e:
            log.error(f"Library 生成失败: {e}")
            return 1

    if gen_dashboard:
        log.info("模式: Dashboard 生成")
        t1 = _tick()
        try:
            path = generate_dashboard()
            _log_stage("dashboard", _tick() - t1)
            log.info(f"Dashboard 生成完成 ({_tick() - t0:.1f}s): {path}")
            return 0
        except Exception as e:
            log.error(f"Dashboard 生成失败: {e}")
            return 1

    if gen_graph:
        log.info("模式: 知识图谱生成")
        t1 = _tick()
        try:
            graph = build_graph()
            stats = graph["stats"]
            log.info(f"  节点: {stats['total_nodes']}, 边: {stats['total_edges']}, "
                     f"连通分量: {stats['components']}")
            md_path = generate_mermaid_report(graph)
            html_path = generate_html(graph)
            _log_stage("graph", _tick() - t1)
            log.info(f"图谱生成完成 ({_tick() - t0:.1f}s)")
            return 0
        except Exception as e:
            log.error(f"图谱生成失败: {e}")
            return 1

    if weekly or monthly:
        period = "week" if weekly else "month"
        log.info(f"模式: {'周报' if weekly else '月报'}")
        if not os.getenv("DEEPSEEK_API_KEY"):
            log.error("未设置 DEEPSEEK_API_KEY")
            return 1
        t1 = _tick()
        try:
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
        except Exception as e:
            log.error(f"{'周报' if weekly else '月报'}生成失败: {e}")
            return 1

    if dry_run:
        log.info("模式: DRY RUN (不调用 AI)")

    # ── Pipeline 运行追踪 ──
    run_id = start_pipeline_run("daily")
    pipeline_error = ""
    articles = []

    # ── 跳过的阶段（来自断点恢复） ──
    completed_stages = set(checkpoint.get("completed_stages", [])) if checkpoint else set()

    try:
        # ── Stage 1: 数据获取 ──
        if "fetch+dedup" not in completed_stages:
            t_fetch = _tick()
            if fetch_direct:
                log.info("数据源: RSS 直接抓取")
                if not dry_run and not os.getenv("DEEPSEEK_API_KEY"):
                    log.error("未设置 DEEPSEEK_API_KEY")
                    finish_pipeline_run(run_id, "error", 0, _tick() - t0, "未设置 API Key")
                    return 1
                articles = asyncio.run(fetch_all())
                fetched_count = len(articles)
                if not articles:
                    log.warning("没有抓取到文章")
                    finish_pipeline_run(run_id, "success", 0, _tick() - t0)
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
            _save_checkpoint("fetch+dedup", [a.id for a in articles], run_id)
        else:
            log.info("⏭ [fetch+dedup] 已完成，跳过")

        if not articles:
            log.warning("没有文章，管道终止")
            _clear_checkpoint()
            finish_pipeline_run(run_id, "success", 0, _tick() - t0)
            return 0

        if dry_run:
            log.info(f"Dry run 完成 ({_tick() - t0:.1f}s)，共 {len(articles)} 篇待处理")
            for a in sorted(articles, key=lambda x: x.published or "", reverse=True)[:10]:
                log.info(f"  [{a.source}] {a.title[:80]}")
            finish_pipeline_run(run_id, "dry_run", len(articles), _tick() - t0)
            _clear_checkpoint()
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

        # ── Stage 2: Classify ──
        if "classify" not in completed_stages:
            t1 = _tick()
            unclassified = [a for a in articles if not a.categories]
            if unclassified:
                try:
                    classify(unclassified)
                except Exception as e:
                    log.warning(f"  ⚠ 分类阶段部分失败: {e}，继续处理已分类的文章")
                    _failed_articles.setdefault("classify", []).append(str(e))
            _log_stage("classify", _tick() - t1)
            _save_checkpoint("classify", [a.id for a in articles], run_id)
        else:
            log.info("⏭ [classify] 已完成，跳过")

        # ── Stage 3: Concept Miner ──
        if "concept_mine" not in completed_stages:
            t1 = _tick()
            try:
                candidates = mine_concepts(articles, batch_size=20)
                if candidates:
                    use_agent = os.getenv("CONCEPT_AGENT") == "1"
                    if use_agent:
                        actions = update_pool_with_agent(candidates, articles)
                        log.info(f"  → {len(candidates)} 个候选, {len(actions)} 项操作 (Agent)")
                    else:
                        actions = update_pool(candidates, articles)
                        log.info(f"  → {len(candidates)} 个候选, {len(actions)} 项操作")
            except Exception as e:
                log.warning(f"  ⚠ Concept Miner 失败: {e}，跳过")
                _failed_articles.setdefault("concept_mine", []).append(str(e))
            _log_stage("concept_mine", _tick() - t1)
            _save_checkpoint("concept_mine", [a.id for a in articles], run_id)
        else:
            log.info("⏭ [concept_mine] 已完成，跳过")

        # ── Stage 4: Knowledge Match ──
        if "knowledge_match" not in completed_stages:
            t1 = _tick()
            cards = load_cards()
            knowledge_context = ""
            if cards:
                try:
                    matched = match_cards(articles, cards, use_semantic=True)
                    knowledge_context = build_context(matched)
                    hits = sum(1 for v in matched.values() if v)
                    log.info(f"  → {hits}/{len(articles)} 篇匹配到卡片")
                except Exception as e:
                    log.warning(f"  ⚠ 知识卡片匹配失败: {e}，使用空上下文")
            _log_stage("knowledge_match", _tick() - t1)
            _save_checkpoint("knowledge_match", [a.id for a in articles], run_id,
                             extra={"knowledge_context": knowledge_context})
        else:
            log.info("⏭ [knowledge_match] 已完成，跳过")
            knowledge_context = (checkpoint or {}).get("knowledge_context", "")

        # ── Stage 5: Summarize ──
        if "summarize" not in completed_stages:
            t1 = _tick()
            unsummarized = [a for a in articles if not a.title_cn]
            if unsummarized:
                log.info(f"  需摘要: {len(unsummarized)}/{len(articles)} 篇")
                try:
                    summarize(unsummarized, knowledge_context=knowledge_context,
                              concurrency=concurrency)
                except Exception as e:
                    log.warning(f"  ⚠ 摘要阶段异常: {e}")
                    _failed_articles.setdefault("summarize", []).append(str(e))
                    # 检查哪些成功（有 title_cn 表示成功）
                    succeeded = sum(1 for a in unsummarized if a.title_cn)
                    log.info(f"  → {succeeded}/{len(unsummarized)} 摘要成功（其余跳过）")
            else:
                log.info(f"  摘要: 全部已缓存，跳过")
            _log_stage("summarize", _tick() - t1)
            _save_checkpoint("summarize", [a.id for a in articles], run_id)
        else:
            log.info("⏭ [summarize] 已完成，跳过")

        # ── Stage 6: Score ──
        if "score" not in completed_stages:
            t1 = _tick()
            unscored = [a for a in articles if a.score == 0]
            if unscored:
                log.info(f"  需评分: {len(unscored)}/{len(articles)} 篇")
                try:
                    score(unscored)
                except Exception as e:
                    log.warning(f"  ⚠ 评分阶段异常: {e}")
                    _failed_articles.setdefault("score", []).append(str(e))
                    succeeded = sum(1 for a in unscored if a.score > 0)
                    log.info(f"  → {succeeded}/{len(unscored)} 评分成功（其余保留0分）")
            else:
                log.info(f"  评分: 全部已缓存，跳过")
            _log_stage("score", _tick() - t1)
            _save_checkpoint("score", [a.id for a in articles], run_id)
        else:
            log.info("⏭ [score] 已完成，跳过")

        # ── 保存缓存 ──
        save_results(articles)

        # ── Stage 7: Generate Report ──
        if "write_report" not in completed_stages:
            t1 = _tick()
            config = load_config()
            min_score = config.get("output", {}).get("min_score", 3)
            report_path = generate_report(articles, fetched_count=fetched_count,
                                          min_score=min_score)
            _log_stage("write_report", _tick() - t1)
            _save_checkpoint("write_report", [a.id for a in articles], run_id,
                             extra={"report_path": str(report_path)})
        else:
            log.info("⏭ [write_report] 已完成，跳过")
            report_path = Path(checkpoint.get("report_path", ""))

        # ── Stage 8: Sync DB ──
        if "update_db" not in completed_stages:
            t1 = _tick()
            try:
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
            except Exception as e:
                log.warning(f"  ⚠ DB 同步失败: {e}")
                _failed_articles.setdefault("update_db", []).append(str(e))
            _log_stage("update_db", _tick() - t1)
            _save_checkpoint("update_db", [a.id for a in articles], run_id)
        else:
            log.info("⏭ [update_db] 已完成，跳过")

        # ── Stage 9: Render Pages ──
        if "render_pages" not in completed_stages:
            t1 = _tick()
            pages_ok = 0
            pages_total = 6
            for name, fn in [
                ("dashboard", generate_dashboard),
                ("library", generate_library),
                ("timeline", generate_timeline),
                ("reports", generate_reports_page),
                ("research", generate_research_page),
                ("my", generate_my_page),
            ]:
                try:
                    fn()
                    pages_ok += 1
                except Exception as e:
                    log.warning(f"  ⚠ 页面 [{name}] 生成失败: {e}")
                    _failed_articles.setdefault(f"render_{name}", []).append(str(e))
            log.info(f"  → 页面生成: {pages_ok}/{pages_total} 成功")
            _log_stage("render_pages", _tick() - t1)
            _save_checkpoint("render_pages", [a.id for a in articles], run_id)
        else:
            log.info("⏭ [render_pages] 已完成，跳过")

        # ── 完成 ──
        total = _tick() - t0

        def count(s): return sum(1 for a in articles if a.score == s)
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
        log.info(f"  日报: {report_path}")
        log.info(f"  耗时明细: {' | '.join(f'{k}={v:.1f}s' for k, v in _stage_times.items())}")

        _clear_checkpoint()
        status = "partial" if _failed_articles else "success"
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
