"""
AI News - AI 评分器

使用 DeepSeek API 对文章进行重要性评分（1-5★）。
"""

from .fetcher import Article
from .utils import log, load_config, ROOT_DIR
from .ai_client import call_ai


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

    if not results:
        log.warning("评分失败")
        return articles

    result_map = {item["id"]: item for item in results}
    for a in articles:
        r = result_map.get(a.id, {})
        a.score = r.get("score", 3)
        a.score_reason = r.get("score_reason", "")
        a.cluster_id = r.get("cluster_id") or ""

    dist = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    for a in articles:
        s = max(1, min(5, a.score))
        dist[s] = dist.get(s, 0) + 1
    log.info(f"评分完成 ★5:{dist[5]} ★4:{dist[4]} ★3:{dist[3]} ★2:{dist[2]} ★1:{dist[1]}")
    return articles


def score(articles: list[Article], batch_size: int = 25) -> list[Article]:
    """分批评分。"""
    if not articles:
        return articles
    result: list[Article] = []
    total = (len(articles) - 1) // batch_size + 1
    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        log.info(f"评分 {i//batch_size + 1}/{total} ({len(batch)}篇)")
        result.extend(score_batch(batch))
    return result
