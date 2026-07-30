"""Pipeline 核心阶段 — 9 阶段每日管道 + 趋势报告。从 pipeline.py 拆分出来。"""

import asyncio
import os
from datetime import datetime
from pathlib import Path

from src.engine.utils import log, load_config, read_inbox
from src.engine.fetcher import fetch_all
from src.engine.dedup import deduplicate
from src.engine.classifier import classify
from src.engine.summarizer import summarize
from src.engine.scorer import score
from src.engine.reporter import generate_report
from src.engine.knowledge import load_cards, match_cards, build_context
from src.engine.concept_miner import mine_concepts, update_pool
from src.engine.concept_agent import update_pool_with_agent
from src.engine.cache import apply_cache, save_results
from src.engine.database import (
    init_db,
    insert_articles,
    insert_report,
    record_article_stage_results,
)
from src.engine.processing_errors import ProcessingError, StageProcessingError
from pipeline_utils import (
    _tick, _log_stage, _failed_articles,
    save_checkpoint, clear_checkpoint,
)

CRITICAL_AI_STAGES = {"classify", "summarize", "score"}


def _failure_details(error: Exception | None) -> dict[str, tuple[str, str]]:
    """把结构化阶段错误展开为 article_id -> (kind, message)。"""
    details: dict[str, tuple[str, str]] = {}
    failures = error.failures if isinstance(error, StageProcessingError) else [error]
    for failure in failures:
        if not isinstance(failure, ProcessingError):
            continue
        for article_id in failure.article_ids:
            details[article_id] = (failure.failure_kind, str(failure))
    return details


def _finish_processing_stage(
    stage: str,
    candidates: list,
    articles: list,
    run_id: int,
    success_predicate,
    error: Exception | None,
    *,
    extra: dict | None = None,
    blocked_predicate=None,
) -> bool:
    """记录文章级结果，并仅在全部候选成功时完成阶段断点。"""
    details = _failure_details(error)
    outcomes: dict[str, tuple[str, str, str]] = {}
    failed_ids: list[str] = []
    for article in candidates:
        if success_predicate(article):
            outcomes[article.id] = ("success", "", "")
            continue
        failed_ids.append(article.id)
        if blocked_predicate and blocked_predicate(article):
            outcomes[article.id] = (
                "blocked", "incomplete_prior_stage",
                f"{stage} 被前置阶段未完成阻塞",
            )
            continue
        kind, message = details.get(
            article.id,
            (
                "unexpected_error" if error else "incomplete_output",
                str(error) if error else f"{stage} 未生成完整结果",
            ),
        )
        outcomes[article.id] = ("failed", kind, message)

    record_article_stage_results(run_id, stage, outcomes)
    if failed_ids:
        _failed_articles[stage] = [
            f"{article_id}: {outcomes[article_id][1]}"
            for article_id in failed_ids
        ]
    else:
        _failed_articles.pop(stage, None)

    save_checkpoint(
        stage,
        [article.id for article in articles],
        run_id,
        extra=extra,
        articles=articles,
        completed=not failed_ids,
    )
    return not failed_ids


def _has_critical_failures() -> bool:
    return any(stage in _failed_articles for stage in CRITICAL_AI_STAGES)


def _is_publishable(article) -> bool:
    return bool(article.categories and article.title_cn and 1 <= article.score <= 5)


def run_trend_report(period: str) -> tuple[bool, str]:
    """运行周报/月报趋势分析。

    返回 (success, message)。
    """
    from src.engine.trend_reporter import generate_trend_report
    from src.engine.trend_agent import generate_trend_report_agent

    if not os.getenv("DEEPSEEK_API_KEY"):
        return False, "未设置 DEEPSEEK_API_KEY"

    use_agent = os.getenv("TREND_AGENT") == "1"
    if use_agent:
        report_path = generate_trend_report_agent(period=period)
    else:
        report_path = generate_trend_report(period=period)

    if report_path:
        init_db()
        from datetime import date as dt_date
        today = dt_date.today()
        report_date = today.isoformat() if period == "week" else today.replace(day=1).isoformat()
        insert_report(date=report_date, report_type=period, path=str(report_path))
        return True, str(report_path)

    return False, "生成失败"


def run_daily_pipeline(
    articles: list,
    run_id: int,
    checkpoint: dict | None,
    limit: int | None,
    only_unprocessed: bool,
    fetch_direct: bool,
    concurrency: int,
    fetched_count: int,
    report_date: str | None = None,
) -> tuple[list, Path | None, str]:
    """执行 9 阶段每日管道。

    返回 (articles, report_path, status) — status 为 "success" | "partial" | "error"。
    """
    report_path = None
    completed_stages = set(checkpoint.get("completed_stages", [])) if checkpoint else set()

    # ── 降级模式检查 ──
    _deg = load_config().get("degradation", {})
    if _deg.get("skip_all_llm"):
        log.warning("⚠️ 降级模式: skip_all_llm=true，所有 LLM 调用将被跳过")
        log.warning("   将生成基础日报（标题 + 来源 + 时间 + 链接 + 规则评分）")

    # ── Stage 1: 数据获取 ──
    if "fetch+dedup" not in completed_stages:
        t_fetch = _tick()
        if fetch_direct:
            log.info("数据源: RSS 直接抓取")
            if not os.getenv("DEEPSEEK_API_KEY"):
                return articles, None, "error: 未设置 API Key"
            articles = asyncio.run(fetch_all())
            if not articles:
                log.warning("没有抓取到文章")
                return articles, None, "success: 无文章"
            log.info(f"  → {len(articles)} 篇原始文章")
            fetched_count = len(articles)
            articles = deduplicate(articles, skip_cache="--no-cache" in __import__("sys").argv)
            log.info(f"  → {len(articles)} 篇去重后")
        else:
            config = load_config()
            max_hours = config.get("fetch", {}).get("max_age_hours", 72)
            for arg in __import__("sys").argv:
                if arg.startswith("--hours="):
                    try:
                        max_hours = int(arg.split("=")[1])
                    except ValueError:
                        pass
            log.info(f"数据源: inbox.jsonl (近 {max_hours}h)")
            articles = read_inbox(since_hours=max_hours)
            # 按 article_id 去重（防止 inbox 跨 Action 运行累积重复）
            before = len(articles)
            seen_ids: set[str] = set()
            unique: list = []
            for a in articles:
                if a.id not in seen_ids:
                    seen_ids.add(a.id)
                    unique.append(a)
            articles = unique
            if before > len(articles):
                log.info(f"  → 去重: {before} → {len(articles)} 篇 (移除 {before - len(articles)} 篇重复)")
            log.info(f"  → inbox 中 {len(articles)} 篇待分析")
            fetched_count = len(articles)  # 修正：inbox 模式下也记录实际读取数

        _log_stage("fetch+dedup", _tick() - t_fetch)
        save_checkpoint(
            "fetch+dedup", [a.id for a in articles], run_id,
            extra={"fetched_count": fetched_count}, articles=articles,
        )
    else:
        log.info("⏭ [fetch+dedup] 已完成，跳过")

    if not articles:
        clear_checkpoint()
        return articles, None, "success: 无文章"

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
        stage_error = None
        if unclassified:
            try:
                classify(unclassified)
            except Exception as e:
                stage_error = e
                log.warning(f"  ⚠ 分类阶段部分失败: {e}，继续处理已分类的文章")
        _log_stage("classify", _tick() - t1)
        _finish_processing_stage(
            "classify", articles, articles, run_id,
            lambda article: bool(article.categories), stage_error,
        )
    else:
        log.info("⏭ [classify] 已完成，跳过")

    # ── Stage 3: Knowledge Match ──
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
        save_checkpoint(
            "knowledge_match", [a.id for a in articles], run_id,
            extra={"knowledge_context": knowledge_context}, articles=articles,
        )
    else:
        log.info("⏭ [knowledge_match] 已完成，跳过")
        knowledge_context = (checkpoint or {}).get("knowledge_context", "")

    # ── Stage 5: Summarize ──
    if "summarize" not in completed_stages:
        t1 = _tick()
        unsummarized = [a for a in articles if not a.title_cn]
        stage_error = None
        if unsummarized:
            log.info(f"  需摘要: {len(unsummarized)}/{len(articles)} 篇")
            try:
                summarize(unsummarized, knowledge_context=knowledge_context,
                          concurrency=concurrency)
            except Exception as e:
                stage_error = e
                log.warning(f"  ⚠ 摘要阶段异常: {e}")
                succeeded = sum(1 for a in unsummarized if a.title_cn)
                log.info(f"  → {succeeded}/{len(unsummarized)} 摘要成功（其余跳过）")
        else:
            log.info(f"  摘要: 全部已缓存，跳过")
        _log_stage("summarize", _tick() - t1)
        _finish_processing_stage(
            "summarize", articles, articles, run_id,
            lambda article: bool(article.title_cn), stage_error,
            extra={"knowledge_context": knowledge_context},
        )
    else:
        log.info("⏭ [summarize] 已完成，跳过")

    # ── Stage 6: Score ──
    if "score" not in completed_stages:
        t1 = _tick()
        unscored = [a for a in articles if a.score == 0 and a.title_cn]
        stage_error = None
        if unscored:
            log.info(f"  需评分: {len(unscored)}/{len(articles)} 篇")
            try:
                score(unscored)
            except Exception as e:
                stage_error = e
                log.warning(f"  ⚠ 评分阶段异常: {e}")
                succeeded = sum(1 for a in unscored if a.score > 0)
                log.info(f"  → {succeeded}/{len(unscored)} 评分成功（其余保留0分）")
        else:
            log.info(f"  评分: 全部已缓存，跳过")
        _log_stage("score", _tick() - t1)
        _finish_processing_stage(
            "score", articles, articles, run_id,
            lambda article: 1 <= article.score <= 5, stage_error,
            blocked_predicate=lambda article: not article.title_cn,
        )
    else:
        log.info("⏭ [score] 已完成，跳过")

    # ── 保存缓存 ──
    save_results(articles)

    # ── Stage 7: Concept Miner (★3+, 已处理跳过, Top-N, 跳过低权威来源) ──
    if "concept_mine" not in completed_stages:
        t1 = _tick()
        concept_ok = True
        try:
            cm_cfg = load_config().get("concept_miner", {})
            min_cm_score = cm_cfg.get("min_score", 3)
            high_score = [a for a in articles if a.score >= min_cm_score]
            if high_score:
                from src.engine.concept_miner import get_mined_ids
                mined = get_mined_ids()
                fresh = [a for a in high_score if a.id not in mined]
                skipped = len(high_score) - len(fresh)
                if skipped:
                    log.info(f"  ⏭ 跳过 {skipped} 篇已挖掘")
                if fresh:
                    candidates = mine_concepts(
                        fresh,
                        batch_size=cm_cfg.get("batch_size", 20),
                        concurrency=concurrency,
                        top_n=cm_cfg.get("top_n", 10),
                        skip_low_authority=cm_cfg.get("skip_low_authority", True),
                    )
                    if candidates:
                        use_agent = os.getenv("CONCEPT_AGENT") == "1"
                        if use_agent:
                            actions = update_pool_with_agent(candidates, fresh)
                            log.info(f"  → {len(candidates)} 个候选, {len(actions)} 项操作 (Agent)")
                        else:
                            actions = update_pool(candidates, fresh)
                            log.info(f"  → {len(candidates)} 个候选, {len(actions)} 项操作")
                    # 标记为已挖掘
                    from src.engine.concept_miner import mark_mined
                    mark_mined([a.id for a in fresh])
                else:
                    log.info(f"  → 所有 ★3+ 文章均已挖掘过")
            else:
                log.info(f"  → 无 ★3+ 文章 (需 ≥3 分)")
        except Exception as e:
            concept_ok = False
            log.warning(f"  ⚠ Concept Miner 失败: {e}，跳过")
            _failed_articles["concept_mine"] = [str(e)]
        if concept_ok:
            _failed_articles.pop("concept_mine", None)
        _log_stage("concept_mine", _tick() - t1)
        save_checkpoint(
            "concept_mine", [a.id for a in articles], run_id,
            articles=articles,
            completed=concept_ok and not _has_critical_failures(),
        )
    else:
        log.info("⏭ [concept_mine] 已完成，跳过")

    # ── Stage 8: Generate Report ──
    if "write_report" not in completed_stages:
        t1 = _tick()
        config = load_config()
        min_score = config.get("output", {}).get("min_score", 3)
        publishable_articles = [a for a in articles if _is_publishable(a)]
        blocked_count = len(articles) - len(publishable_articles)
        if blocked_count:
            log.warning(f"  ⚠ {blocked_count} 篇处理不完整，不写入日报")
        report_path = generate_report(publishable_articles, fetched_count=fetched_count,
                                      min_score=min_score, report_date=report_date)
        _log_stage("write_report", _tick() - t1)
        save_checkpoint(
            "write_report", [a.id for a in articles], run_id,
            extra={"report_path": str(report_path)}, articles=articles,
            completed=not blocked_count and not _has_critical_failures(),
        )
    else:
        log.info("⏭ [write_report] 已完成，跳过")
        report_path = Path(checkpoint.get("report_path", ""))

    # ── Stage 8: Sync DB ──
    if "update_db" not in completed_stages:
        t1 = _tick()
        publishable_articles = [a for a in articles if _is_publishable(a)]
        blocked_articles = [a for a in articles if not _is_publishable(a)]
        db_ok = True
        db_error = ""
        try:
            init_db()
            article_dicts = [a.to_dict() for a in publishable_articles]
            insert_articles(article_dicts)
            report_date_str = report_date if report_date else datetime.now().strftime("%Y-%m-%d")
            insert_report(
                date=report_date_str,
                report_type="daily", path=str(report_path),
                fetched=fetched_count, filtered=len(publishable_articles),
                star5=sum(1 for a in publishable_articles if a.score == 5),
                star4=sum(1 for a in publishable_articles if a.score == 4),
                star3=sum(1 for a in publishable_articles if a.score == 3),
            )
        except Exception as e:
            db_ok = False
            db_error = str(e)
            log.warning(f"  ⚠ DB 同步失败: {e}")
            _failed_articles["update_db"] = [str(e)]
        if db_ok:
            _failed_articles.pop("update_db", None)
        db_outcomes = {
            article.id: (
                ("success", "", "")
                if db_ok else ("failed", "database_error", db_error)
            )
            for article in publishable_articles
        }
        db_outcomes.update({
            article.id: (
                "blocked", "incomplete_prior_stage",
                "摘要、分类或评分结果不完整，未写入数据库",
            )
            for article in blocked_articles
        })
        record_article_stage_results(run_id, "update_db", db_outcomes)
        _log_stage("update_db", _tick() - t1)
        save_checkpoint(
            "update_db", [a.id for a in articles], run_id,
            articles=articles,
            completed=db_ok and not blocked_articles and not _has_critical_failures(),
        )
    else:
        log.info("⏭ [update_db] 已完成，跳过")

    # ── Stage 9: Render Pages ──
    if "render_pages" not in completed_stages:
        from src.frontend.dashboard import generate_dashboard
        from src.frontend.library import generate_library
        from src.timeline import generate_timeline
        from src.frontend.reports_page import generate_reports_page
        from src.frontend.my_page import generate_my_page
        from src.frontend.article_page import generate_article_page
        from src.frontend.report_reader import generate_report_reader
        from src.research import generate_research_page
        from src.frontend.auth_page import generate_auth_page

        t1 = _tick()
        pages_ok = 0
        pages_total = 9
        for name, fn in [
            ("dashboard", generate_dashboard),
            ("library", generate_library),
            ("timeline", generate_timeline),
            ("reports", generate_reports_page),
            ("research", generate_research_page),
            ("my", generate_my_page),
            ("article", generate_article_page),
            ("report_reader", generate_report_reader),
            ("auth", generate_auth_page),
        ]:
            try:
                fn()
                pages_ok += 1
            except Exception as e:
                log.warning(f"  ⚠ 页面 [{name}] 生成失败: {e}")
                _failed_articles.setdefault(f"render_{name}", []).append(str(e))
        log.info(f"  → 页面生成: {pages_ok}/{pages_total} 成功")
        _log_stage("render_pages", _tick() - t1)
        render_ok = pages_ok == pages_total
        if render_ok:
            for key in [key for key in _failed_articles if key.startswith("render_")]:
                _failed_articles.pop(key, None)
        save_checkpoint(
            "render_pages", [a.id for a in articles], run_id,
            articles=articles,
            completed=(
                render_ok
                and not _has_critical_failures()
                and "update_db" not in _failed_articles
            ),
        )
    else:
        log.info("⏭ [render_pages] 已完成，跳过")

    # ── 确定返回状态 ──
    status = "partial" if _failed_articles else "success"
    return articles, report_path, status
