"""
AI News - 报告生成器

将评分后的文章组装为 Markdown 日报。
支持同事件多源聚类合并。
"""

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from .fetcher import Article
from .utils import log, ensure_dir, ROOT_DIR

_STAR_MAP = {5: "★★★★★", 4: "★★★★", 3: "★★★", 2: "★★", 1: "★"}


def _format_one(a: Article, is_primary: bool = True) -> str:
    """格式化单篇文章为 Markdown 片段。"""
    stars = _STAR_MAP.get(a.score, "★★★")
    cats = " · ".join(a.categories) if a.categories else ""
    title = a.title_cn or a.title

    lines = [f"## {stars} {title}", ""]

    if a.one_liner:
        lines.append(f"> {a.one_liner}")
        lines.append("")

    if a.summary_points:
        for point in a.summary_points:
            lines.append(f"- {point}")
        lines.append("")

    meta_parts = []
    if cats:
        meta_parts.append(f"分类：{cats}")
    meta_parts.append(f"来源：[{a.source}]({a.url})")
    if a.score_reason:
        meta_parts.append(f"评分理由：{a.score_reason}")
    lines.append(" · ".join(meta_parts))

    lines.extend(["", f"[详情](/article/{a.id})", "", "---", ""])
    return "\n".join(lines)


def _format_cluster(primary: Article, others: list[Article]) -> str:
    """格式化一个事件聚类。primary 为主报道，others 为同事件其他来源。"""
    result = _format_one(primary, is_primary=True)

    if others:
        sources = []
        for o in others:
            sources.append(f"[{o.source}]({o.url})")
        result += f"> 📰 同时报道：{' · '.join(sources)}\n\n---\n\n"

    return result


def _cluster_articles(articles: list[Article]) -> list[tuple[Article, list[Article]]]:
    """
    按 cluster_id 聚类。返回 [(primary, [others])] 列表，按 primary.score 降序。
    无 cluster_id 的文章各自独立。
    """
    groups: dict[str, list[Article]] = defaultdict(list)
    unclustered: list[Article] = []

    for a in articles:
        if a.cluster_id:
            groups[a.cluster_id].append(a)
        else:
            unclustered.append(a)

    result: list[tuple[Article, list[Article]]] = []

    # 聚类组：最高分 = primary，其余 = others
    for cluster_id, group in groups.items():
        group.sort(key=lambda x: x.score, reverse=True)
        primary = group[0]
        others = group[1:]
        result.append((primary, others))

    # 未聚类：各自独立
    for a in unclustered:
        result.append((a, []))

    result.sort(key=lambda x: x[0].score, reverse=True)
    return result


def generate_report(
    articles: list[Article],
    fetched_count: int = 0,
    output_dir: Optional[Path] = None,
    min_score: int = 3,
    report_date: str | None = None,
) -> Path:
    """生成日报 Markdown 文件。"""
    if output_dir is None:
        output_dir = ROOT_DIR / "reports"
    ensure_dir(output_dir)

    sorted_articles = sorted(articles, key=lambda a: a.score, reverse=True)
    filtered = [a for a in sorted_articles if a.score >= min_score]

    def count(s): return sum(1 for a in filtered if a.score == s)

    clusters = _cluster_articles(filtered)
    clustered_count = sum(1 for _, others in clusters if others)

    article_md = []
    for primary, others in clusters:
        article_md.append(_format_cluster(primary, others))

    template_path = ROOT_DIR / "templates" / "daily-report.md"
    template = template_path.read_text(encoding="utf-8")

    today = report_date if report_date else datetime.now().strftime("%Y-%m-%d")
    report = template.format(
        date=today,
        fetched=fetched_count,
        filtered=len(filtered),
        star5=count(5),
        star4=count(4),
        star3=count(3),
        articles="\n".join(article_md),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

    report_path = output_dir / f"{today}.md"
    report_path.write_text(report, encoding="utf-8")
    log.info(f"日报已生成: {report_path} ({len(filtered)} 篇, {clustered_count} 组聚类)")

    _update_index(output_dir, today)
    return report_path


def _update_index(reports_dir: Path, today: str):
    """更新 reports/index.md 索引。"""
    files = sorted(reports_dir.glob("*.md"), reverse=True)
    lines = ["# AI News 日报索引", "", f"> 共 {len(files)} 期", ""]
    for f in files:
        if f.name == "index.md":
            continue
        lines.append(f"- [{f.stem}]({f.name})")

    index_path = reports_dir / "index.md"
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.debug(f"索引已更新: {index_path}")
