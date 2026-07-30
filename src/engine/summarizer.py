"""
AI News - AI 摘要生成器

使用 DeepSeek API 将英文 AI 新闻翻译为中文摘要。
支持并发批处理，通过 concurrency 参数控制并发数。
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

from .fetcher import Article
from .utils import log, ROOT_DIR, clean_html
from .ai_client import call_ai
from .processing_errors import ProcessingError, StageProcessingError


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

    if results is None:
        raise ProcessingError(
            "summarize", "ai_unavailable", [a.id for a in articles],
            "摘要模型调用失败或返回无法解析",
        )
    if not results:
        raise ProcessingError(
            "summarize", "empty_response", [a.id for a in articles],
            "摘要模型返回了空结果",
        )

    result_map = {
        item.get("id"): item
        for item in results
        if isinstance(item, dict) and item.get("id")
    }
    failed_ids = []
    for a in articles:
        r = result_map.get(a.id)
        title_cn = r.get("title_cn") if r else None
        if not isinstance(title_cn, str) or not title_cn.strip():
            failed_ids.append(a.id)
            continue
        a.title_cn = title_cn.strip()
        a.one_liner = r.get("one_liner", "")
        a.summary_points = r.get("summary_points", [])

    if failed_ids:
        raise ProcessingError(
            "summarize", "incomplete_response", failed_ids,
            f"摘要结果缺少 {len(failed_ids)} 篇文章",
        )
    return articles


def summarize(
    articles: list[Article],
    batch_size: int = 10,
    knowledge_context: str = "",
    concurrency: int = 3,
) -> list[Article]:
    """
    分批 + 并发生成摘要。

    concurrency=1 时串行（原行为），>1 时使用线程池并发调 API。
    """
    if not articles:
        return articles

    # 按 batch_size 分片
    batches = [articles[i:i + batch_size] for i in range(0, len(articles), batch_size)]
    total = len(batches)
    log.info(f"AI 摘要: {len(articles)} 篇 → {total} 批 × {batch_size} (并发={concurrency})")

    if concurrency <= 1:
        # 串行（保持兼容）
        result: list[Article] = []
        failures: list[ProcessingError] = []
        for idx, batch in enumerate(batches):
            log.info(f"  摘要 {idx + 1}/{total} ({len(batch)}篇)")
            try:
                result.extend(summarize_batch(batch, knowledge_context))
            except ProcessingError as e:
                failures.append(e)
                result.extend(batch)
        if failures:
            raise StageProcessingError("summarize", failures)
        return result

    # 并发模式
    result: list[Article] = []
    failures: list[ProcessingError] = []
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
                result.extend(batch_result)
            except ProcessingError as e:
                failures.append(e)
                result.extend(batches[idx])
                log.error(f"  摘要 batch {idx + 1} 异常: {e}")
            except Exception as e:
                batch = batches[idx]
                failures.append(ProcessingError(
                    "summarize", "unexpected_error", [a.id for a in batch], str(e)
                ))
                result.extend(batch)
                log.error(f"  摘要 batch {idx + 1} 异常: {e}")
            completed += 1
            log.info(f"  摘要 {completed}/{total} 完成")

    # 按原始顺序排序
    id_order = {a.id: i for i, a in enumerate(articles)}
    result.sort(key=lambda a: id_order.get(a.id, 99999))
    log.info(f"摘要完成: {len(result)} 篇")
    if failures:
        raise StageProcessingError("summarize", failures)
    return result
