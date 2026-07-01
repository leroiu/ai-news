"""
AI News - AI 分类器

使用 DeepSeek API 批量对文章进行自动分类。
"""

from .fetcher import Article
from .utils import log, load_config, ROOT_DIR, clean_html
from .ai_client import call_ai


def _build_system_prompt() -> str:
    template = (ROOT_DIR / "prompts" / "classify.md").read_text(encoding="utf-8")
    config = load_config()
    categories = config.get("categories", [])
    category_list = "\n".join(f"- {c}" for c in categories)
    return template.replace("$CATEGORY_LIST", category_list)


def _build_user_prompt(articles: list[Article]) -> str:
    lines = ["请为以下文章分类：\n"]
    for a in articles:
        content = clean_html(a.content_raw)[:300]
        lines.append(
            f"ID: {a.id}\n标题: {a.title}\n来源: {a.source}\n摘要: {content}\n"
        )
    return "\n".join(lines)


def classify_batch(articles: list[Article]) -> list[Article]:
    """对一批文章调用 DeepSeek API 进行分类。"""
    if not articles:
        return articles

    system = _build_system_prompt()
    user = _build_user_prompt(articles)

    log.info(f"AI 分类: {len(articles)} 篇")
    results = call_ai(system, user, max_tokens=4096)

    if not results:
        log.warning("分类失败，全部标记为'未分类'")
        for a in articles:
            a.categories = ["未分类"]
        return articles

    class_map = {item["id"]: item.get("categories", ["未分类"]) for item in results}
    for a in articles:
        a.categories = class_map.get(a.id, ["未分类"])

    cat_counts: dict[str, int] = {}
    for a in articles:
        for c in a.categories:
            cat_counts[c] = cat_counts.get(c, 0) + 1
    top = sorted(cat_counts.items(), key=lambda x: -x[1])[:5]
    log.info(f"分类完成, Top: {top}")
    return articles


def classify(articles: list[Article], batch_size: int = 25) -> list[Article]:
    """分批分类。"""
    if not articles:
        return articles
    result: list[Article] = []
    total = (len(articles) - 1) // batch_size + 1
    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        log.info(f"分类 {i//batch_size + 1}/{total} ({len(batch)}篇)")
        result.extend(classify_batch(batch))
    return result
