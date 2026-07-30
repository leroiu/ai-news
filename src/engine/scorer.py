"""
AI News - AI 评分器

使用 DeepSeek API 对文章进行重要性评分（1-5★）。
"""

from .fetcher import Article
from .utils import log, load_config, ROOT_DIR
from .ai_client import call_ai
from .processing_errors import ProcessingError, StageProcessingError


def _build_system_prompt() -> str:
    template = (ROOT_DIR / "prompts" / "score.md").read_text(encoding="utf-8")
    config = load_config()
    interests = config.get("interests", {})
    parts = []
    for level, items in interests.items():
        if items:
            parts.append(f"- {level} 优先级: {', '.join(items)}")
    return template.replace("$USER_INTERESTS", "\n".join(parts))


def _build_user_prompt(articles: list[Article]) -> str:
    lines = ["请为以下文章评分：\n"]
    for a in articles:
        categories = ", ".join(a.categories) if a.categories else "未分类"
        summary = a.one_liner or a.title
        lines.append(
            f"ID: {a.id}\n"
            f"标题: {a.title}\n"
            f"分类: {categories}\n"
            f"摘要: {summary}\n"
        )
    return "\n".join(lines)


def score_batch(articles: list[Article]) -> list[Article]:
    """对一批文章调用 DeepSeek API 评分。"""
    if not articles:
        return articles

    system = _build_system_prompt()
    user = _build_user_prompt(articles)

    log.info(f"AI 评分: {len(articles)} 篇")
    results = call_ai(system, user, max_tokens=4096)

    if results is None:
        raise ProcessingError(
            "score", "ai_unavailable", [a.id for a in articles],
            "评分模型调用失败或返回无法解析",
        )
    if not results:
        raise ProcessingError(
            "score", "empty_response", [a.id for a in articles],
            "评分模型返回了空结果",
        )

    result_map = {
        item.get("id"): item
        for item in results
        if isinstance(item, dict) and item.get("id")
    }
    failed_ids = []
    for a in articles:
        r = result_map.get(a.id)
        raw_score = r.get("score") if r else None
        if type(raw_score) is not int or not 1 <= raw_score <= 5:
            failed_ids.append(a.id)
            continue
        a.score = raw_score
        a.score_reason = r.get("score_reason", "")
        a.cluster_id = r.get("cluster_id") or ""

    dist = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    for a in articles:
        if 1 <= a.score <= 5:
            dist[a.score] = dist.get(a.score, 0) + 1
    log.info(f"评分完成 ★5:{dist[5]} ★4:{dist[4]} ★3:{dist[3]} ★2:{dist[2]} ★1:{dist[1]}")
    if failed_ids:
        raise ProcessingError(
            "score", "incomplete_response", failed_ids,
            f"评分结果缺少或无效的文章共 {len(failed_ids)} 篇",
        )
    return articles


def score(articles: list[Article], batch_size: int = 25) -> list[Article]:
    """分批评分。"""
    if not articles:
        return articles
    result: list[Article] = []
    failures: list[ProcessingError] = []
    total = (len(articles) - 1) // batch_size + 1
    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        log.info(f"评分 {i//batch_size + 1}/{total} ({len(batch)}篇)")
        try:
            result.extend(score_batch(batch))
        except ProcessingError as e:
            failures.append(e)
            result.extend(batch)
    if failures:
        raise StageProcessingError("score", failures)
    return result
