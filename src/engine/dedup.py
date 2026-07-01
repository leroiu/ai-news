"""
AI News - 去重器

移除重复文章：
1. URL 精确匹配（MD5 缓存）
2. 标题相似度匹配（SequenceMatcher > 阈值）
3. 维护 7 天 seen_urls 缓存
"""

import json
from difflib import SequenceMatcher
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from .fetcher import Article
from .utils import log, load_config, ROOT_DIR


# ============================================================
# 缓存管理
# ============================================================

class SeenCache:
    """已见 URL 缓存。自动清理超过 N 天的记录。"""

    def __init__(self, cache_path: Optional[Path] = None, max_days: int = 7, no_persist: bool = False):
        self.cache_path = cache_path or (ROOT_DIR / "cache" / "seen_urls.json")
        self.max_days = max_days
        self.no_persist = no_persist
        self._data: dict[str, str] = {}  # {article_id: iso_datetime}
        if not no_persist:
            self._load()

    def _load(self):
        if self.cache_path.exists():
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._data = {}
        self._purge()

    def _save(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def _purge(self):
        """清理超过 max_days 的缓存条目。"""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.max_days)).isoformat()
        before = len(self._data)
        self._data = {k: v for k, v in self._data.items() if v > cutoff}
        after = len(self._data)
        if before > after:
            log.debug(f"缓存清理: {before} → {after} 条 (>{self.max_days}d)")

    def has(self, article_id: str) -> bool:
        return article_id in self._data

    def add(self, article_id: str):
        self._data[article_id] = datetime.now(timezone.utc).isoformat()

    def add_batch(self, article_ids: list[str]):
        now = datetime.now(timezone.utc).isoformat()
        for aid in article_ids:
            self._data[aid] = now

    def flush(self):
        if not self.no_persist:
            self._save()

    def __len__(self) -> int:
        return len(self._data)


# ============================================================
# 去重逻辑
# ============================================================

def title_similarity(a: str, b: str) -> float:
    """计算两个标题的相似度 (0-1)。"""
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def deduplicate(
    articles: list[Article],
    cache: Optional[SeenCache] = None,
    title_threshold: float = 0.85,
    skip_cache: bool = False,
) -> list[Article]:
    """
    对文章列表去重。

    策略：
    1. URL MD5 已在 fetcher 中生成，直接对比缓存
    2. 标题相似度 > threshold 的视为重复
    3. 相同源 + 相同标题 = 重复（兜底）

    返回去重后的文章列表（标记 is_duplicate=True 的已移除）。
    """
    if cache is None:
        cache = SeenCache(no_persist=skip_cache)

    cfg = load_config()
    dedup_cfg = cfg.get("dedup", {})
    threshold = dedup_cfg.get("title_similarity", title_threshold)

    before = len(articles)
    unique: list[Article] = []
    seen_ids: set[str] = set()

    for article in articles:
        aid = article.id

        # 1. 缓存命中 — 之前抓取过
        if cache.has(aid):
            article.is_duplicate = True
            article.duplicate_of = "cache"
            continue

        # 2. 本轮已见（同一批次内重复）
        if aid in seen_ids:
            article.is_duplicate = True
            article.duplicate_of = "batch"
            continue

        # 3. 标题相似度检测
        is_dup = False
        for existing in unique:
            sim = title_similarity(article.title, existing.title)
            if sim >= threshold:
                article.is_duplicate = True
                article.duplicate_of = existing.id
                is_dup = True
                log.debug(f"标题重复 ({sim:.2f}): \"{article.title[:60]}\" ≈ \"{existing.title[:60]}\"")
                break
        if is_dup:
            continue

        # 4. 同源同名（最后一层兜底）
        for existing in unique:
            if article.source == existing.source and article.title.strip() == existing.title.strip():
                article.is_duplicate = True
                article.duplicate_of = existing.id
                is_dup = True
                break
        if is_dup:
            continue

        unique.append(article)
        seen_ids.add(aid)

    # 写入缓存（包括被标题去重标记的文章，防止下次运行再次出现）
    to_cache: set[str] = {a.id for a in unique}
    for article in articles:
        if article.is_duplicate:
            to_cache.add(article.id)
    cache.add_batch(list(to_cache))
    cache.flush()

    after = len(unique)
    removed = before - after
    if removed > 0:
        log.info(f"去重: {before} → {after} 篇 (移除 {removed} 篇重复)")
    else:
        log.info(f"去重: {before} 篇，无重复")

    return unique


# ============================================================
# CLI 测试
# ============================================================

def main():
    """CLI: 测试去重功能。"""
    import asyncio
    from .fetcher import fetch_all
    from .utils import setup_logging
    setup_logging("DEBUG")

    articles = asyncio.run(fetch_all())
    if not articles:
        print("没有抓取到文章")
        return 0

    unique = deduplicate(articles)
    print(f"\n去重后: {len(unique)} 篇")
    for i, a in enumerate(unique[:10], 1):
        print(f"  [{i}] [{a.source}] {a.title[:80]}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
