"""
AI News - AI 分类器

使用 DeepSeek API 批量对文章进行自动分类。
"""

from .fetcher import Article
from .utils import log, load_config, ROOT_DIR, clean_html
from .ai_client import call_ai
from .processing_errors import ProcessingError, StageProcessingError


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

    if results is None:
        raise ProcessingError(
            "classify", "ai_unavailable", [a.id for a in articles],
            "分类模型调用失败或返回无法解析",
        )
    if not results:
        raise ProcessingError(
            "classify", "empty_response", [a.id for a in articles],
            "分类模型返回了空结果",
        )

    class_map = {
        item.get("id"): item.get("categories")
        for item in results
        if isinstance(item, dict) and item.get("id")
    }
    failed_ids = []
    for a in articles:
        categories = class_map.get(a.id)
        if (
            not isinstance(categories, list)
            or not categories
            or not all(isinstance(category, str) and category.strip()
                       for category in categories)
        ):
            failed_ids.append(a.id)
            continue
        a.categories = [category.strip() for category in categories]

    cat_counts: dict[str, int] = {}
    for a in articles:
        for c in a.categories:
            cat_counts[c] = cat_counts.get(c, 0) + 1
    top = sorted(cat_counts.items(), key=lambda x: -x[1])[:5]
    log.info(f"分类完成, Top: {top}")
    if failed_ids:
        raise ProcessingError(
            "classify", "incomplete_response", failed_ids,
            f"分类结果缺少 {len(failed_ids)} 篇文章",
        )
    return articles


def classify(articles: list[Article], batch_size: int = 25) -> list[Article]:
    """分批分类。"""
    if not articles:
        return articles
    result: list[Article] = []
    failures: list[ProcessingError] = []
    total = (len(articles) - 1) // batch_size + 1
    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        log.info(f"分类 {i//batch_size + 1}/{total} ({len(batch)}篇)")
        try:
            result.extend(classify_batch(batch))
        except ProcessingError as e:
            failures.append(e)
            result.extend(batch)
    if failures:
        raise StageProcessingError("classify", failures)
    return result
