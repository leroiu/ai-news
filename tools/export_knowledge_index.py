#!/usr/bin/env python3
"""Export Knowledge Card index to 30_Knowledge/Documents/"""
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.engine.knowledge import load_cards

OUT = Path("C:/Users/杨成俊/Desktop/AI-Workspace/30_Knowledge/Documents/ai-news-knowledge-cards.md")

cards = load_cards()
by_type = defaultdict(list)
for c in cards:
    by_type[c.type].append(c)

lines = [
    "# AI News — Knowledge Card 索引",
    "",
    f"> {len(cards)} 张卡片 | {len(by_type)} 种类型 | 数据源: `20_Projects/ai-news/data/knowledge/`",
    f"> 生成时间: 2026-06-28",
    "",
    "---",
    "",
    "## 卡片总览",
    "",
    "| ID | 名称 | type | ★ | 摘要 |",
    "|----|------|------|---|------|",
]

for c in sorted(cards, key=lambda x: (x.type, x.id)):
    imp = "★" * c.importance
    summary = c.summary.replace("\n", " ").strip()[:60]
    lines.append(f"| `{c.id}` | {c.name} | {c.type} | {imp} | {summary} |")

lines.append("")
lines.append("---")
lines.append("")

for t, clist in sorted(by_type.items()):
    lines.append(f"## {t} ({len(clist)} 张)")
    lines.append("")
    for c in sorted(clist, key=lambda x: x.id):
        imp = "★" * c.importance
        lines.append(f"### {c.name} {imp}")
        lines.append(f"- **ID**: `{c.id}` | **importance**: {c.importance}")
        if c.company:
            lines.append(f"- **所属**: {c.company}")
        lines.append(f"- **摘要**: {c.summary.strip()}")
        if c.significance:
            sig_short = c.significance.strip().replace("\n", " ")[:200]
            lines.append(f"- **重要性**: {sig_short}")
        lines.append(f"- **标签**: {', '.join(c.tags[:8])}")
        if c.related:
            lines.append(f"- **关联**: {', '.join(c.related[:5])}")
        if c.depends_on:
            lines.append(f"- **依赖**: {', '.join(c.depends_on[:5])}")
        if c.influenced:
            lines.append(f"- **影响**: {', '.join(c.influenced[:5])}")
        if c.timeline:
            latest = c.timeline[-1]
            lines.append(f"- **最近事件**: {latest.get('date', '')} — {latest.get('event', '')}")
        lines.append("")

lines.append("---")
lines.append("")
lines.append("*由 AI News `tools/export_knowledge_index.py` 自动生成*")
lines.append("")

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"Written: {OUT}")
print(f"  {len(cards)} cards, {len(by_type)} types, {len(lines)} lines")
