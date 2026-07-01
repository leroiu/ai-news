"""
AI News — 处理结果缓存

基于文章 URL 哈希缓存 AI 处理结果，避免重复调用。
缓存存储在 data/processed_cache.json，键为文章 ID。
"""

import json
from pathlib import Path
from typing import Optional

from .utils import ROOT_DIR

CACHE_PATH = ROOT_DIR / "data" / "processed_cache.json"
MAX_CACHE_SIZE = 10000


def _load() -> dict:
    """加载缓存（不存在则返回空 dict）。"""
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save(cache: dict):
    """保存缓存，超过上限时淘汰最旧的条目。"""
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    # 超过上限则淘汰前半
    if len(cache) > MAX_CACHE_SIZE:
        keys = sorted(cache.keys(), key=lambda k: cache[k].get("cached_at", ""))
        for k in keys[: len(keys) // 2]:
            del cache[k]
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def get(article_id: str) -> Optional[dict]:
    """获取缓存的文章处理结果。"""
    cache = _load()
    return cache.get(article_id)


def put(article_id: str, data: dict):
    """缓存文章处理结果。"""
    from datetime import datetime, timezone
    cache = _load()
    cache[article_id] = {
        **data,
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }
    _save(cache)


def apply_cache(articles):
    """
    对文章列表应用缓存：已缓存的恢复数据，未缓存的返回原样。
    返回 (cached_count, articles) 元组。
    """
    cache = _load()
    hit = 0
    for a in articles:
        entry = cache.get(a.id)
        if entry:
            a.title_cn = entry.get("title_cn", "") or a.title_cn
            a.one_liner = entry.get("one_liner", "") or a.one_liner
            a.summary_points = entry.get("summary_points", []) or a.summary_points
            a.categories = entry.get("categories", []) or a.categories
            a.score = entry.get("score", 0) or a.score
            a.score_reason = entry.get("score_reason", "") or a.score_reason
            hit += 1
    return hit


def save_results(articles):
    """将已处理的文章结果写入缓存。"""
    for a in articles:
        if a.score > 0 or a.title_cn:
            put(a.id, {
                "title_cn": a.title_cn,
                "one_liner": a.one_liner,
                "summary_points": a.summary_points,
                "categories": a.categories,
                "score": a.score,
                "score_reason": a.score_reason,
            })
