"""Card Writer：研究资料 → AI 撰写 → 结构化 YAML 知识卡片。

组成完整的三 Agent 收集流水线的最后一环:
  Concept Agent (发现+去重) → Research Agent (深度收集) → Card Writer (撰写+保存)

核心函数:
  - write_card(): AI 基于研究资料撰写 YAML 卡片
  - save_card(): 写入 data/knowledge/<type>/<id>.yaml
  - collect_and_write(): 完整流水线 — 研究→撰写→保存
"""

import re
import json
from pathlib import Path
from typing import Optional

from .utils import log, ensure_dir, ROOT_DIR

PROMPT_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"

# type → 目录映射
TYPE_DIR_MAP = {
    "methodology": "methodology",
    "company": "companies",
    "model": "models",
    "tech": "tech",
    "concept": "concepts",
    "product": "products",
    "person": "people",
    "event": "events",
    "technique": "methodology",
    "pattern": "methodology",
    "framework": "tech",
    "workflow": "methodology",
}


# ── Prompt ──

def _load_prompt(name: str) -> str:
    path = PROMPT_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    log.warning(f"Prompt not found: {path}")
    return ""


def _slugify(name: str) -> str:
    """Name → kebab-case ID"""
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug)
    return slug[:50]


# ── Card Writer ──

def write_card(
    name: str,
    entity_info: str = "",
    articles: list[dict] | None = None,
    knowledge_cards: list[dict] | None = None,
    card_type: str = "methodology",
) -> Optional[str]:
    """AI 基于研究资料撰写一张完整的 YAML 知识卡片。

    Args:
        name: 实体/概念名称
        entity_info: 从 Research Agent 或其他渠道收集的实体信息
        articles: 相关文章列表 [{title, source, one_liner, ...}]
        knowledge_cards: 知识库中已有的关联卡片 [{id, name, type, summary}]
        card_type: 卡片类型 (methodology/company/model/tech/concept/product/person/event)

    Returns:
        YAML 字符串，AI 调用失败时返回 None
    """
    from .ai_client import call_ai

    prompt = _load_prompt("card-write.md")
    if not prompt:
        return None

    # 构建实体信息
    entity_text = f"名称: {name}\n类型: {card_type}\n"
    if entity_info:
        entity_text += f"\n研究资料:\n{entity_info[:4000]}\n"

    # 构建文章列表
    if articles:
        article_lines = []
        for a in articles[:10]:
            article_lines.append(
                f"- {a.get('title', a.get('title_cn', ''))} "
                f"(来源: {a.get('source', '')})\n"
                f"  {(a.get('one_liner') or a.get('summary') or '')[:200]}"
            )
        articles_text = "\n".join(article_lines)
    else:
        articles_text = "（无）"

    # 构建已有卡片
    if knowledge_cards:
        card_lines = []
        for c in knowledge_cards[:15]:
            card_lines.append(
                f"- [{c.get('id', '')}] {c.get('name', '')} "
                f"({c.get('type', '')}): {(c.get('summary') or '')[:150]}"
            )
        cards_text = "\n".join(card_lines)
    else:
        cards_text = "（无关联卡片）"

    prompt = prompt.replace("$ENTITY_INFO", entity_text)
    prompt = prompt.replace("$RELATED_ARTICLES", articles_text)
    prompt = prompt.replace("$KNOWLEDGE_CARDS", cards_text)
    prompt = prompt.replace("$CARD_TYPE", card_type)

    user = f"请为 '{name}' 撰写一张 {card_type} 类型的知识卡片"

    result = call_ai(prompt, user, temperature=0.3, max_tokens=4096)
    if not result:
        return None

    # call_ai 可能返回 list 或 dict，这里期望文本
    if isinstance(result, list):
        yaml_text = result[0] if result else ""
    elif isinstance(result, dict):
        # 如果 AI 返回了 JSON，尝试提取
        yaml_text = result.get("yaml", result.get("content", ""))
    else:
        yaml_text = str(result)

    if not yaml_text or len(str(yaml_text).strip()) < 50:
        log.warning(f"Card Write: 返回内容过短 ({len(str(yaml_text))} chars)")
        return None

    log.info(f"Card Write: '{name}' → {len(str(yaml_text))} chars")
    return str(yaml_text)


# ── Save Card ──

def save_card(yaml_str: str, card_type: str = "methodology") -> Optional[Path]:
    """将 AI 生成的 YAML 内容写入知识卡片文件。

    自动从 YAML 中提取 id，写入到正确的类型子目录。
    已有卡片不会被覆盖。

    Args:
        yaml_str: YAML 格式的卡片内容
        card_type: 卡片类型

    Returns:
        写入的 Path，已有卡片或解析失败时返回 None
    """
    import yaml as yaml_lib

    # 解析 YAML 获取 id
    try:
        card_data = yaml_lib.safe_load(yaml_str)
        if not isinstance(card_data, dict):
            log.warning("Card Save: YAML 解析结果不是 dict")
            return None
        card_id = card_data.get("id", "")
        if not card_id:
            log.warning("Card Save: YAML 中没有 id 字段")
            return None
    except Exception as e:
        log.warning(f"Card Save: YAML 解析失败: {e}")
        return None

    # 确定目标目录
    dir_name = TYPE_DIR_MAP.get(card_type, "methodology")
    card_dir = ROOT_DIR / "data" / "knowledge" / dir_name
    ensure_dir(card_dir)

    card_path = card_dir / f"{card_id}.yaml"
    if card_path.exists():
        log.info(f"Card Save: 跳过已有卡片 {card_path.name}")
        return None

    # 写入
    card_path.write_text(yaml_str, encoding="utf-8")
    log.info(f"Card Save: {card_path.name} ({card_type})")
    return card_path


# ── Full Pipeline: Collect + Write + Save ──

def collect_and_write(
    name: str,
    card_type: str = "methodology",
    depth: str = "standard",
    lang: str = "zh",
) -> dict:
    """完整流水线：Research Agent 深度收集 → Card Writer 撰写 → 保存。

    Args:
        name: 实体/概念名称
        card_type: 卡片类型
        depth: 研究深度 ("standard" | "deep")
        lang: 语言 ("zh" | "en")

    Returns:
        {
            "name": ...,
            "card_type": ...,
            "yaml": <YAML 字符串>,
            "saved_path": <Path 或 None>,
            "research_report": <Research Agent 的报告摘要>,
            "error": <错误信息，成功时为 None>,
        }
    """
    from .research_agent import research_agent

    result: dict = {
        "name": name,
        "card_type": card_type,
        "yaml": None,
        "saved_path": None,
        "research_report": None,
        "error": None,
    }

    # Step 1: Research Agent 深度研究
    log.info(f"Card Pipeline: 开始研究 '{name}' (depth={depth})")
    try:
        research_result = research_agent(name, depth=depth, lang=lang)
        if "error" in research_result:
            result["error"] = f"Research failed: {research_result['error']}"
            return result

        report = research_result.get("report", {})
        entities = report.get("_entities", [])
        articles = report.get("_articles", [])
        summary = report.get("summary", "")
        result["research_report"] = summary

        # 构建实体信息文本
        entity_parts = [summary]
        for e in entities[:10]:
            entity_parts.append(
                f"{e.get('name', '')} ({e.get('type', '')}): "
                f"{(e.get('summary') or '')[:300]}"
            )
        entity_info = "\n\n".join(entity_parts)
    except Exception as e:
        result["error"] = f"Research exception: {e}"
        return result

    # Step 2: 获取知识库中已有相关卡片
    try:
        from .database import search, init_db
        init_db()
        search_result = search(name, limit=10, semantic=True)
        knowledge_cards = search_result.get("entities", [])[:10]
    except Exception:
        knowledge_cards = []

    # Step 3: Card Writer 撰写
    yaml_str = write_card(
        name=name,
        entity_info=entity_info,
        articles=articles[:10] if articles else [],
        knowledge_cards=knowledge_cards,
        card_type=card_type,
    )
    if not yaml_str:
        result["error"] = "Card Writer: AI 生成失败"
        return result

    result["yaml"] = yaml_str

    # Step 4: 保存
    saved = save_card(yaml_str, card_type)
    result["saved_path"] = str(saved) if saved else None
    if not saved:
        result["error"] = "Card 已存在或保存失败"

    log.info(
        f"Card Pipeline: '{name}' done → "
        f"{'saved' if saved else 'skipped'}"
    )
    return result
