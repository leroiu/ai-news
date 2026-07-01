"""
AI News - 趋势报告生成器（周报 / 月报）

读取过去 N 天的日报，调用 AI 分析趋势，生成周报/月报。
V5.4: 增加 DB 存储、index 自动生成、知识卡片上下文注入。
"""

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .utils import log, ensure_dir, ROOT_DIR
from .ai_client import call_ai
from .database import insert_report, get_entities


def _find_daily_reports(reports_dir: Path, days: int) -> list[tuple[str, str]]:
    """
    找到最近 N 天的日报文件。
    返回 [(date_str, content), ...]，按日期升序。
    """
    today = datetime.now()
    results: list[tuple[str, str]] = []

    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        path = reports_dir / f"{date_str}.md"
        if path.exists():
            try:
                content = path.read_text(encoding="utf-8")
                results.append((date_str, content))
            except OSError:
                log.warning(f"无法读取日报: {path}")

    return results


def _build_knowledge_context() -> str:
    """构建知识卡片上下文摘要，注入趋势分析 prompt。"""
    entities = get_entities()
    if not entities:
        return ""

    by_type: dict[str, list[dict]] = {}
    for e in entities:
        by_type.setdefault(e["type"], []).append(e)

    lines = ["## 知识库摘要\n"]
    lines.append(f"知识库共有 {len(entities)} 个已跟踪实体，按类型分布：\n")
    for t, items in sorted(by_type.items()):
        names = ", ".join(item["name"] for item in items[:12])
        more = f" (+{len(items) - 12})" if len(items) > 12 else ""
        lines.append(f"- **{t}** ({len(items)}): {names}{more}")

    lines.append("\n请在分析趋势时关联知识库中已有的实体。")
    return "\n".join(lines)


def _build_trend_prompt(reports: list[tuple[str, str]], period: str) -> tuple[str, str]:
    """构建趋势分析的 system + user prompt（含知识卡片上下文）。"""
    template = (ROOT_DIR / "prompts" / "trend.md").read_text(encoding="utf-8")

    # 注入变量
    count = len(reports)
    if period == "week":
        count_label = "7"
        period_label = "一周"
    else:
        count_label = str(count)
        period_label = "一个月"

    system = (
        template
        .replace("$PERIOD", period_label)
        .replace("$COUNT", count_label)
    )

    # 汇总日报内容
    parts = []
    for date_str, content in reports:
        truncated = content[:3000]
        parts.append(f"### {date_str}\n\n{truncated}")

    # 附加知识卡片上下文
    knowledge_ctx = _build_knowledge_context()
    parts.append(knowledge_ctx)

    user = "\n\n---\n\n".join(parts)

    return system, user


def _format_top5(top5: list[dict]) -> str:
    lines = []
    for i, item in enumerate(top5, 1):
        stars = "★" * item.get("importance", 3)
        lines.append(f"{i}. **{stars} {item.get('title', '')}**")
        lines.append(f"   > {item.get('why', '')}")
        lines.append("")
    return "\n".join(lines)


def _format_trends(trends: list[dict]) -> str:
    if not trends:
        return "_本周无明显新趋势_"
    lines = []
    for t in trends:
        lines.append(f"### {t.get('trend', '')}")
        lines.append(f"{t.get('description', '')}")
        evidence = t.get("evidence", [])
        if evidence:
            lines.append("")
            for e in evidence:
                lines.append(f"- {e}")
        lines.append("")
    return "\n".join(lines)


def _format_signals(signals: list[dict]) -> str:
    if not signals:
        return "_本周无特殊信号_"
    lines = []
    for s in signals:
        lines.append(f"- **{s.get('signal', '')}** — {s.get('why_matters', '')}")
    lines.append("")
    return "\n".join(lines)


def _format_new_players(players: list[dict]) -> str:
    if not players:
        return "_本周无值得关注的新玩家_"
    lines = []
    for p in players:
        lines.append(
            f"- **{p.get('name', '')}**: {p.get('what', '')} "
            f"— {p.get('why_worth_watching', '')}"
        )
    lines.append("")
    return "\n".join(lines)


def _format_daily_index(reports: list[tuple[str, str]], reports_dir: Path) -> str:
    """生成日报索引链接。"""
    if not reports:
        return "_无日报_"
    lines = []
    for date_str, _ in reports:
        lines.append(f"- [{date_str}]({date_str}.md)")
    return "\n".join(lines)


def _format_weekly_index(reports_dir: Path) -> str:
    """找到已有的周报文件。"""
    existing = sorted(reports_dir.glob("weekly-*.md"), reverse=True)
    if not existing:
        return "_暂无历史周报_"
    lines = []
    for p in existing[:4]:  # 最近 4 期
        name = p.stem.replace("weekly-", "")
        lines.append(f"- [周报 {name}]({p.name})")
    return "\n".join(lines)


def generate_trend_report(
    period: str = "week",
    reports_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
) -> Optional[Path]:
    """
    生成趋势报告。

    Args:
        period: "week" 或 "month"
        reports_dir: 日报所在目录
        output_dir: 输出目录（默认与日报同目录）
    """
    if reports_dir is None:
        reports_dir = ROOT_DIR / "reports"
    if output_dir is None:
        output_dir = reports_dir

    ensure_dir(output_dir)
    days = 7 if period == "week" else 30

    # 1. 找到日报
    reports = _find_daily_reports(reports_dir, days)
    if len(reports) < 2:
        log.warning(f"日报不足（仅 {len(reports)} 篇），跳过{period}报生成")
        return None

    log.info(f"加载 {len(reports)} 篇日报用于{period}报分析")

    # 2. 构建 prompt 并调 AI
    system, user = _build_trend_prompt(reports, period)
    log.info(f"AI 趋势分析: {len(reports)} 篇日报, prompt ~{len(user)} chars")

    result = call_ai(system, user, max_tokens=8192)

    if not result or not isinstance(result, dict):
        log.error(f"{period}报 AI 分析失败")
        return None

    # result should be the trend analysis JSON (call_ai returns list[dict],
    # but for trend we expect a single dict)
    if isinstance(result, list):
        if not result:
            log.error(f"{period}报 AI 返回空列表")
            return None
        result = result[0]

    # 3. 按模板组装报告
    today = datetime.now()

    if period == "week":
        # 计算周范围
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

    report_path = output_dir / filename
    report_path.write_text(report, encoding="utf-8")
    log.info(f"{period}报已生成: {report_path}")

    # 4. 保存到数据库 + 刷新索引
    _save_report_to_db(
        date=(
            week_start.strftime("%Y-%m-%d") if period == "week"
            else today.strftime("%Y-%m-%d")
        ),
        report_type=period + "ly" if period == "week" else "monthly",
        path=str(report_path),
    )
    _generate_reports_index(output_dir)

    return report_path


def _save_report_to_db(date: str, report_type: str, path: str):
    """将周报/月报元数据存入 SQLite。"""
    try:
        insert_report(
            date=date,
            report_type=report_type,
            path=path,
            fetched=0,
            filtered=0,
        )
        log.info(f"报告已记录到 DB: {report_type} {date}")
    except Exception as e:
        log.warning(f"报告 DB 写入失败: {e}")


def _generate_reports_index(reports_dir: Path):
    """自动生成 reports/index.md 索引文件。"""
    report_files = sorted(
        [f for f in reports_dir.glob("*.md")
         if f.name != "index.md"],
        reverse=True,
    )

    daily = [f for f in report_files if f.name.count("-") == 2 and not f.name.startswith(("weekly-", "monthly-"))]
    weekly = [f for f in report_files if f.name.startswith("weekly-")]
    monthly = [f for f in report_files if f.name.startswith("monthly-")]
    other = [f for f in report_files if f not in daily and f not in weekly and f not in monthly]

    lines = [
        "# AI News 报告索引",
        "",
        f"> 共 {len(report_files)} 期报告，自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    for title, files in [("📆 日报", daily), ("📊 周报", weekly), ("📈 月报", monthly)]:
        if files:
            lines.append(f"## {title}（{len(files)} 期）")
            lines.append("")
            for f in files:
                label = f.stem
                if title == "📆 日报":
                    label = f.stem
                elif title == "📊 周报":
                    label = f"周报 {f.stem.replace('weekly-', '')}"
                else:
                    label = f"月报 {f.stem.replace('monthly-', '')}"
                lines.append(f"- [{label}]({f.name})")
            lines.append("")

    if other:
        lines.append(f"## 📄 其他（{len(other)} 个）")
        lines.append("")
        for f in other:
            lines.append(f"- [{f.stem}]({f.name})")

    index_path = reports_dir / "index.md"
    index_path.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"索引已更新: {index_path}")
