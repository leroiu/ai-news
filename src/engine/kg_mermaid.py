"""
AI News - Mermaid 图谱导出

从图数据生成 Mermaid flowchart 语法和 Markdown 报告文件。
"""
from datetime import datetime
from pathlib import Path
from typing import Optional

from .utils import log, ensure_dir, ROOT_DIR
from .kg_data import TYPE_COLORS, EDGE_STYLES


def to_mermaid(graph: dict) -> str:
    """将图导出为 Mermaid flowchart 语法。"""
    lines = [
        "```mermaid",
        "graph LR",
        "",
    ]

    # 节点样式定义
    lines.append("  %% --- 样式定义 ---")
    for t, color in TYPE_COLORS.items():
        lines.append(f"  classDef {t} fill:{color},stroke:#fff,stroke-width:2px,color:#fff")

    lines.append("")
    lines.append("  %% --- 节点 ---")

    # 节点
    for n in graph["nodes"]:
        # 用方括号括起来，Mermaid 支持中文
        label = n["name"].replace('"', "'")
        lines.append(f'  {n["id"]}["{label}"]:::{n["type"]}')

    lines.append("")
    lines.append("  %% --- 边 ---")

    # 边
    for e in graph["edges"]:
        src = e["source"]
        tgt = e["target"]
        label = e["label"]

        if e["type"] == "related":
            # 虚线无箭头
            lines.append(f'  {src} -.->|"{label}"| {tgt}')
        elif e["type"] == "depends_on":
            # 实线箭头
            lines.append(f'  {src} -->|"{label}"| {tgt}')
        else:  # influenced
            # 实线箭头
            lines.append(f'  {src} -->|"{label}"| {tgt}')

    lines.append("")
    lines.append("```")

    return "\n".join(lines)


def generate_mermaid_report(graph: dict, output_dir: Optional[Path] = None) -> Path:
    """生成 Mermaid 图谱 Markdown 文件。"""
    if output_dir is None:
        output_dir = ROOT_DIR / "reports"
    ensure_dir(output_dir)

    stats = graph["stats"]
    mermaid = to_mermaid(graph)

    # 生成 Markdown
    lines = [
        "# 🕸️ AI News 知识图谱",
        "",
        f"> 节点: {stats['total_nodes']} | 边: {stats['total_edges']} | 连通分量: {stats['components']}",
        f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "---",
        "",
        "## 📊 统计概览",
        "",
        "### 节点分布",
        "",
    ]

    for t, count in sorted(stats["node_types"].items()):
        color = TYPE_COLORS.get(t, "#999")
        lines.append(f"- <span style='color:{color}'>●</span> **{t}**: {count}")

    lines.extend([
        "",
        "### 边分布",
        "",
    ])
    for t, count in sorted(stats["edge_types"].items()):
        style = EDGE_STYLES.get(t, {})
        lines.append(f"- **{style.get('label', t)}**: {count}")

    lines.extend([
        "",
        "### 核心节点（度中心性 Top 5）",
        "",
    ])
    for item in stats["most_connected"]:
        lines.append(f"- **{item['name']}** — 连接数: {item['degree']}")

    if stats["isolated_nodes"]:
        lines.extend([
            "",
            "### 孤立节点",
            "",
            ", ".join(stats["isolated_nodes"]),
        ])

    lines.extend([
        "",
        "---",
        "",
        "## 🕸️ 关系图谱",
        "",
        mermaid,
        "",
        "---",
        "",
        "",
        "## 📖 图例",
        "",
        "### 节点颜色",
        "",
    ])

    for t, color in TYPE_COLORS.items():
        lines.append(f"- <span style='color:{color}'>●</span> **{t}**")

    lines.extend([
        "",
        "### 边类型",
        "",
    ])
    for etype, style in EDGE_STYLES.items():
        lines.append(f"- **{style['label']}** ({etype}) — 颜色: {style['color']}")

    lines.append("")

    path = output_dir / "knowledge-graph.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"Mermaid 图谱: {path}")
    return path
