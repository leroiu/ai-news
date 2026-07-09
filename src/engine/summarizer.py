"""
AI News - AI 摘要生成器 + Fallback

使用 DeepSeek API 将英文 AI 新闻翻译为中文摘要。
只对 Top N 文章调用 LLM，其余使用标题+原文截取作为 fallback。
支持并发批处理，通过 concurrency 参数控制并发数。
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

from .fetcher import Article
from .utils import log, ROOT_DIR, clean_html, load_config
from .ai_client import call_ai


def _build_system_prompt(knowledge_context: str = "") -> str:
    base = (ROOT_DIR / "prompts" / "summarize.md").read_text(encoding="utf-8")
    if knowledge_context:
        base += "\n\n" + knowledge_context
    return base


def _build_user_prompt(articles: list[Article]) -> str:
    lines = ["请为以下文章生成中文摘要：\n"]
    for a in articles:
        content = clean_html(a.content_raw)[:800]
        lines.append(
            f"ID: {a.id}\n标题: {a.title}\n来源: {a.source}\n正文: {content}\n"
        )
    return "\n".join(lines)


def summarize_batch(articles: list[Article], knowledge_context: str = "") -> list[Article]:
    """对一批文章调用 DeepSeek API 生成中文摘要。"""
    if not articles:
        return articles

    system = _build_system_prompt(knowledge_context)
    user = _build_user_prompt(articles)

    results = call_ai(system, user, max_tokens=8192)

    if not results:
        log.warning("摘要失败")
        return articles

    result_map = {item["id"]: item for item in results}
    for a in articles:
        r = result_map.get(a.id, {})
        a.title_cn = r.get("title_cn", "")
        a.one_liner = r.get("one_liner", "")
        a.summary_points = r.get("summary_points", [])

    return articles


def _fallback_summarize(article: Article, truncate: int = 200) -> Article:
    """不使用 LLM，用原始标题+内容截取作为降级摘要。"""
    article.title_cn = article.title  # 用原标题
    content = clean_html(article.content_raw)[:truncate].strip()
    if content:
        article.one_liner = f"[{article.source}] {content[:120]}"
        article.summary_points = [content[:truncate]]
    else:
        article.one_liner = f"[{article.source}] {article.title[:80]}"
        article.summary_points = []
    return article


def summarize(
    articles: list[Article],
    batch_size: int = 10,
    knowledge_context: str = "",
    concurrency: int = 3,
    top_n: int | None = None,
) -> list[Article]:
    """
    分批 + 并发生成摘要。

    只对 Top N 文章调用 LLM，其余用 fallback（标题+原文截取）。
    top_n 默认从 config.yaml 读取 summarizer.top_n。

    concurrency=1 时串行（原行为），>1 时使用线程池并发调 API。
    """
    if not articles:
        return articles

    # 读取配置
    config = load_config()
    if top_n is None:
        top_n = config.get("summarizer", {}).get("top_n", 20)
    fallback_truncate = config.get("summarizer", {}).get("fallback_truncate", 200)
    deg_cfg = config.get("degradation", {})
    skip_llm = deg_cfg.get("skip_all_llm", False)

    # 降级模式：跳过所有 LLM
    if skip_llm:
        log.warning(f"  降级模式: 全部 {len(articles)} 篇走 fallback 摘要（跳过 LLM）")
        for a in articles:
            _fallback_summarize(a, fallback_truncate)
        return articles

    # 按评分排序（高优先）
    sorted_articles = sorted(articles, key=lambda a: (a.score or 0), reverse=True)
    top_articles = sorted_articles[:top_n]
    fallback_articles = sorted_articles[top_n:]

    log.info(f"摘要: {len(articles)} 篇 → LLM={len(top_articles)} Fallback={len(fallback_articles)} (top_n={top_n})")

    # ── Fallback 处理 ──
    for a in fallback_articles:
        _fallback_summarize(a, fallback_truncate)
    if fallback_articles:
        log.info(f"  Fallback: {len(fallback_articles)} 篇（跳过 LLM）")

    if not top_articles:
        return articles

    # ── LLM 只处理 Top N ──
    # 按 batch_size 分片
    batches = [top_articles[i:i + batch_size] for i in range(0, len(top_articles), batch_size)]
    total = len(batches)
    log.info(f"AI 摘要: {len(top_articles)} 篇 → {total} 批 × {batch_size} (并发={concurrency})")

    processed: list[Article] = []

    if concurrency <= 1:
        for idx, batch in enumerate(batches):
            log.info(f"  摘要 {idx + 1}/{total} ({len(batch)}篇)")
            processed.extend(summarize_batch(batch, knowledge_context))
    else:
        completed = 0
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {
                pool.submit(summarize_batch, batch, knowledge_context): idx
                for idx, batch in enumerate(batches)
            }
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    batch_result = future.result()
                    processed.extend(batch_result)
                except Exception as e:
                    log.error(f"  摘要 batch {idx + 1} 异常: {e}")
                completed += 1
                log.info(f"  摘要 {completed}/{total} 完成")

    # 按原始顺序排序
    id_order = {a.id: i for i, a in enumerate(articles)}
    all_articles = processed + fallback_articles
    all_articles.sort(key=lambda a: id_order.get(a.id, 99999))
    log.info(f"摘要完成: {len(all_articles)} 篇（LLM={len(processed)}, Fallback={len(fallback_articles)})")
    return all_articles
