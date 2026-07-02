"""Trend Reporter Agent：将单次趋势分析升级为 Scan → Enrich → Synthesize 迭代流程。

Phase 1: SCAN — 分批扫描日报，每 5 篇一批提取候选趋势，跨批去重合并
Phase 2: ENRICH — 每个趋势语义搜索知识库，关联实体和文章
Phase 3: SYNTHESIZE — 知识库增强上下文 + 趋势自评 + 合成最终报告
Phase 4: FORMAT — 复用 trend_reporter 的格式化/存储函数

复用 trend_reporter: _find_daily_reports, _build_knowledge_context, _format_*,
                      _save_report_to_db, _generate_reports_index
"""

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .utils import log, ensure_dir, ROOT_DIR

PROMPT_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


# ── Prompt 加载 ──

def _load_prompt(name: str) -> str:
    path = PROMPT_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    log.warning(f"Prompt not found: {path}")
    return ""


# ── Phase 1: Scan ──

def _scan_reports(
    reports: list[tuple[str, str]],
    period: str,
    batch_size: int = 5,
) -> list[dict]:
    """分批扫描日报，提取候选趋势并跨批去重合并。

    Args:
        reports: [(date_str, content), ...]
        period: "week" | "month"
        batch_size: 每批日报数量

    Returns:
        去重合并后的候选趋势列表
    """
    from .ai_client import call_ai

    prompt_template = _load_prompt("trend-agent-scan.md")
    if not prompt_template:
        return []

    period_label = "一周" if period == "week" else "一个月"
    all_trends: list[dict] = []

    # 分批扫描
    for i in range(0, len(reports), batch_size):
        batch = reports[i:i + batch_size]
        batch_text = "\n\n---\n\n".join(
            f"### {date_str}\n{content[:2000]}"
            for date_str, content in batch
        )

        prompt = prompt_template.replace("$DAILY_REPORTS", batch_text)
        user = f"从 {len(batch)} 篇日报（{period_label}第{i//batch_size + 1}批）中识别趋势"

        result = call_ai(prompt, user, temperature=0.3, max_tokens=2048)
        if not result:
            continue

        batch_trends = result if isinstance(result, list) else []
        log.info(
            f"Trend Scan batch {i//batch_size + 1}: "
            f"{len(batch_trends)} trends from {len(batch)} reports"
        )
        all_trends.extend(t for t in batch_trends if isinstance(t, dict))

    # 跨批去重合并：相似趋势名合并 evidence
    merged = _merge_trends(all_trends)
    log.info(f"Trend Scan: {len(all_trends)} raw → {len(merged)} merged trends")
    return merged


def _normalize_name(name: str) -> str:
    """Normalize trend name for dedup comparison."""
    return re.sub(r'[^a-z一-鿿]', '', name.lower().strip())


def _merge_trends(trends: list[dict]) -> list[dict]:
    """合并相似趋势：名称相似度判断 + evidence 合并。"""
    if len(trends) <= 1:
        return trends

    merged: list[dict] = []
    used: set[int] = set()

    for i, t in enumerate(trends):
        if i in used:
            continue
        name = t.get("trend", "")
        norm = _normalize_name(name)
        if not norm:
            continue

        combined = {
            "trend": name,
            "description": t.get("description", ""),
            "evidence": list(t.get("evidence", [])),
            "importance": t.get("importance", 3),
            "direction": t.get("direction", "rising"),
        }

        # 找相似趋势合并
        for j, other in enumerate(trends):
            if j <= i or j in used:
                continue
            other_norm = _normalize_name(other.get("trend", ""))
            if not other_norm:
                continue
            # 完全包含或高度重叠
            if norm in other_norm or other_norm in norm:
                combined["evidence"].extend(other.get("evidence", []))
                combined["importance"] = max(
                    combined["importance"], other.get("importance", 3)
                )
                if len(other.get("description", "")) > len(combined["description"]):
                    combined["description"] = other.get("description", "")
                used.add(j)

        # 去重 evidence
        combined["evidence"] = list(dict.fromkeys(combined["evidence"]))
        merged.append(combined)
        used.add(i)

    # 按 importance 降序
    merged.sort(key=lambda x: x.get("importance", 0), reverse=True)
    return merged


# ── Phase 2: Enrich ──

def _enrich_trends(trends: list[dict]) -> list[dict]:
    """对每个趋势做语义搜索，关联知识库实体和文章。

    每个趋势附加 _entities 和 _articles 字段。
    """
    from .database import search, init_db

    init_db()

    for t in trends:
        name = t.get("trend", "")
        if not name:
            t["_entities"] = []
            t["_articles"] = []
            continue

        try:
            result = search(name, limit=5, semantic=True)
            t["_entities"] = result.get("entities", [])[:5]
            t["_articles"] = result.get("articles", [])[:5]
            log.debug(
                f"Enrich '{name}': "
                f"{len(t['_entities'])} entities, {len(t['_articles'])} articles"
            )
        except Exception as e:
            log.warning(f"Enrich failed for '{name}': {e}")
            t["_entities"] = []
            t["_articles"] = []

    return trends


# ── Phase 3: Synthesize ──

def _synthesize_report(
    trends: list[dict],
    reports: list[tuple[str, str]],
    period: str,
    lang: str = "zh",
) -> dict:
    """知识库增强 + 趋势自评 + 合成最终 JSON 报告。"""
    from .ai_client import call_ai

    prompt = _load_prompt("trend-agent-synthesize.md")
    if not prompt:
        return {}

    # 候选趋势摘要
    trend_lines = []
    for t in trends:
        evidence_count = len(t.get("evidence", []))
        entities = t.get("_entities", [])
        articles = t.get("_articles", [])
        trend_lines.append(
            f"### {t.get('trend', '')} (重要性: {t.get('importance', 3)}/5)\n"
            f"描述: {t.get('description', '')}\n"
            f"证据: {evidence_count} 条\n"
            f"关联实体: {', '.join(e.get('name', '') for e in entities[:3]) or '无'}\n"
            f"关联文章: {', '.join(a.get('title', '')[:60] for a in articles[:3]) or '无'}\n"
        )
    trends_text = "\n".join(trend_lines) if trend_lines else "（未发现明显趋势）"

    # 知识库增强上下文
    enrich_lines = []
    for t in trends:
        for e in t.get("_entities", [])[:2]:
            enrich_lines.append(
                f"- {e.get('name', '')} ({e.get('type', '')}): "
                f"{(e.get('summary') or '')[:120]}"
            )
        for a in t.get("_articles", [])[:2]:
            enrich_lines.append(
                f"- 文章: {a.get('title', a.get('title_cn', ''))} "
                f"(来源: {a.get('source', '')})"
            )
    enrich_text = "\n".join(dict.fromkeys(enrich_lines)) if enrich_lines else "（无增强上下文）"

    # 日报摘要
    summary_lines = []
    for date_str, content in reports:
        summary_lines.append(f"### {date_str}\n{content[:500]}")
    daily_text = "\n\n---\n\n".join(summary_lines)

    period_label = "一周" if period == "week" else "一个月"

    prompt = prompt.replace("$CANDIDATE_TRENDS", trends_text)
    prompt = prompt.replace("$ENRICHED_CONTEXT", enrich_text)
    prompt = prompt.replace("$DAILY_SUMMARY", daily_text)
    prompt = prompt.replace("$PERIOD_LABEL", period_label)
    prompt = prompt.replace("$REPORT_COUNT", str(len(reports)))

    user = (
        f"基于 {len(trends)} 个候选趋势和知识库增强数据，"
        f"生成{'周报' if period == 'week' else '月报'}。"
        f"语言: {'中文' if lang == 'zh' else 'English'}"
    )

    result = call_ai(prompt, user, temperature=0.3, max_tokens=8192)
    if not result:
        return {}

    if isinstance(result, list):
        report = result[0] if result else {}
    elif isinstance(result, dict):
        report = result
    else:
        report = {}

    quality = report.get("_quality", {})
    log.info(
        f"Trend Synthesize: {len(report.get('trends', []))} trends, "
        f"quality={quality.get('trend_score', '?')}/10, "
        f"evidence={quality.get('evidence_quality', '?')}"
    )
    return report


# ── Main Entry Point ──

def generate_trend_report_agent(
    period: str = "week",
    reports_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    lang: str = "zh",
) -> Optional[Path]:
    """Agent 增强的趋势报告生成。

    Scan → Enrich → Synthesize → Format，复用 trend_reporter 的格式化/存储。
    """
    # 延迟导入避免循环依赖
    from .trend_reporter import (
        _find_daily_reports,
        _format_top5,
        _format_trends,
        _format_signals,
        _format_new_players,
        _format_daily_index,
        _format_weekly_index,
        _save_report_to_db,
        _generate_reports_index,
    )

    if reports_dir is None:
        reports_dir = ROOT_DIR / "reports"
    if output_dir is None:
        output_dir = reports_dir

    ensure_dir(output_dir)
    days = 7 if period == "week" else 30

    # 1. 查找日报
    reports = _find_daily_reports(reports_dir, days)
    if len(reports) < 2:
        log.warning(f"日报不足（仅 {len(reports)} 篇），跳过 Agent {period}报")
        return None

    log.info(f"Agent Trend: {len(reports)} reports for {period}")

    # Phase 1: Scan — 分批提取候选趋势
    trends = _scan_reports(reports, period)

    # Phase 2: Enrich — 每个趋势关联知识库
    if trends:
        trends = _enrich_trends(trends)

    # Phase 3: Synthesize — 合成最终报告
    result = _synthesize_report(trends, reports, period, lang)
    if not result:
        log.error(f"Agent {period}报合成失败")
        return None

    # Phase 4: Format — 复用现有模板和格式化
    today = datetime.now()

    if period == "week":
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        week_range = f"{week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d')}"

        template_path = ROOT_DIR / "templates" / "weekly-report.md"
        template = template_path.read_text(encoding="utf-8")

        report = template.format(
            week_range=week_range,
            headline=result.get("headline", ""),
            top5=_format_top5(result.get("top5", [])),
            trends=_format_trends(result.get("trends", [])),
            signals=_format_signals(result.get("signals", [])),
            new_players=_format_new_players(result.get("new_players", [])),
            daily_index=_format_daily_index(reports, reports_dir),
            generated_at=today.strftime("%Y-%m-%d %H:%M"),
        )
        filename = f"weekly-{week_start.strftime('%Y-%m-%d')}.md"
        report_date = week_start.strftime("%Y-%m-%d")
        report_type = "weekly"
    else:
        month_label = today.strftime("%Y年%m月")
        template_path = ROOT_DIR / "templates" / "monthly-report.md"
        template = template_path.read_text(encoding="utf-8")

        report = template.format(
            month=month_label,
            headline=result.get("headline", ""),
            top5=_format_top5(result.get("top5", [])),
            trends=_format_trends(result.get("trends", [])),
            signals=_format_signals(result.get("signals", [])),
            new_players=_format_new_players(result.get("new_players", [])),
            weekly_index=_format_weekly_index(reports_dir),
            daily_index=_format_daily_index(reports, reports_dir),
            generated_at=today.strftime("%Y-%m-%d %H:%M"),
        )
        filename = f"monthly-{today.strftime('%Y-%m')}.md"
        report_date = today.strftime("%Y-%m-%d")
        report_type = "monthly"

    report_path = output_dir / filename
    report_path.write_text(report, encoding="utf-8")
    log.info(f"Agent {period}报已生成: {report_path}")

    # 保存到 DB + 刷新索引
    _save_report_to_db(date=report_date, report_type=report_type, path=str(report_path))
    _generate_reports_index(output_dir)

    return report_path
