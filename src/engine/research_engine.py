"""深度研究后端引擎：话题搜索、上下文组装与 AI 报告生成。"""
from pathlib import Path

from src.interfaces.i18n import TYPE_LABELS_ZH, t

RESEARCH_PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "prompts" / "research.md"


def _load_research_prompt() -> str:
    if RESEARCH_PROMPT_PATH.exists():
        return RESEARCH_PROMPT_PATH.read_text(encoding="utf-8")
    return """你是顶级 AI 行业研究分析师。基于提供的知识卡片和文章进行深度研究。

## 已知知识卡片
$KNOWLEDGE_CARDS

## 相关文章
$RELATED_ARTICLES

## 研究主题
$RESEARCH_TOPIC

返回 JSON：{"summary":"...", "key_findings":[...], "card_connections":[...], "timeline":[...], "further_reading":[...]}
"""


def generate_research_report(topic: str, depth: str = "standard", lang: str = "zh") -> dict:
    """生成结构化研究报告，返回 ``report`` 或 ``error``。"""
    from .ai_client import call_ai
    from .database import init_db, search

    init_db()
    if not topic or not topic.strip():
        return {"error": t("research_no_results", lang)}

    entity_limit = 10 if depth == "standard" else 20
    article_limit = 15 if depth == "standard" else 30
    search_result = search(topic, limit=max(entity_limit, article_limit), semantic=True)
    entities = search_result.get("entities", [])[:entity_limit]
    articles = search_result.get("articles", [])[:article_limit]
    if not entities and not articles:
        return {"error": t("research_no_results", lang)}

    card_lines = []
    for entity in entities:
        entity_type = entity.get("type", "")
        summary = (entity.get("summary") or entity.get("significance") or "")[:300]
        card_lines.append(
            f'- [{entity.get("id", "")}] {entity.get("name", "")} '
            f'({TYPE_LABELS_ZH.get(entity_type, entity_type)}): {summary}'
        )
    article_lines = []
    for article in articles:
        title = article.get("title", article.get("title_cn", ""))
        article_lines.append(
            f'- [{article.get("id", "")}] {title} (来源: {article.get("source", "")}) '
            f'{article.get("one_liner", "") or ""}'
        )

    system_prompt = _load_research_prompt()
    system_prompt = system_prompt.replace("$KNOWLEDGE_CARDS", "\n".join(card_lines))
    system_prompt = system_prompt.replace("$RELATED_ARTICLES", "\n".join(article_lines))
    system_prompt = system_prompt.replace("$RESEARCH_TOPIC", topic)
    user_prompt = (
        f"请对以下主题进行深度研究：{topic}\n\n研究深度: {depth}\n"
        f"语言: {'中文' if lang == 'zh' else 'English'}"
    )
    result = call_ai(system_prompt, user_prompt, temperature=0.3, max_tokens=4096)
    if result is None:
        return {"error": t("research_ai_error", lang)}
    if isinstance(result, list) and result:
        report = result[0]
    elif isinstance(result, dict):
        report = result
    else:
        report = {}
    report["_meta"] = {
        "topic": topic, "depth": depth,
        "entity_count": len(entities), "article_count": len(articles),
    }
    report["_entities"] = entities
    report["_articles"] = articles
    return {"report": report}
