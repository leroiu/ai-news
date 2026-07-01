"""
Deduplicator 单元测试
"""

import pytest
from pathlib import Path
from src.engine.fetcher import Article
from src.engine.dedup import deduplicate, title_similarity, SeenCache


class TestTitleSimilarity:
    def test_identical(self):
        assert title_similarity("Hello World", "Hello World") == 1.0

    def test_different(self):
        assert title_similarity("Hello World", "Foo Bar") < 0.5

    def test_case_insensitive(self):
        assert title_similarity("HELLO WORLD", "hello world") == 1.0

    def test_similar(self):
        sim = title_similarity(
            "OpenAI launches GPT-5 with new features",
            "OpenAI launches GPT-5 with amazing new features",
        )
        assert sim > 0.8


class TestSeenCache:
    def test_new_cache_empty(self, tmp_path: Path):
        cache = SeenCache(cache_path=tmp_path / "seen.json")
        assert len(cache) == 0

    def test_add_and_check(self, tmp_path: Path):
        cache = SeenCache(cache_path=tmp_path / "seen.json")
        cache.add("abc123")
        assert cache.has("abc123")
        assert not cache.has("xyz")

    def test_flush_persists(self, tmp_path: Path):
        path = tmp_path / "seen.json"
        cache = SeenCache(cache_path=path)
        cache.add("abc123")
        cache.flush()

        cache2 = SeenCache(cache_path=path)
        assert cache2.has("abc123")


class TestDeduplicate:
    def setup_method(self):
        self.articles = [
            Article(
                id=Article.make_id("http://a.com/1"),
                title="AI Breakthrough Today",
                url="http://a.com/1",
                source="TechCrunch",
            ),
            Article(
                id=Article.make_id("http://b.com/2"),
                title="AI Breakthrough Today!",  # 极相似标题
                url="http://b.com/2",
                source="The Verge",
            ),
            Article(
                id=Article.make_id("http://c.com/3"),
                title="Something Different",
                url="http://c.com/3",
                source="ArXiv",
            ),
        ]

    def test_removes_title_duplicate(self, tmp_path: Path):
        cache = SeenCache(cache_path=tmp_path / "seen.json")
        result = deduplicate(self.articles, cache=cache, title_threshold=0.85)
        titles = {a.title for a in result}
        assert "Something Different" in titles
        # 2 篇 "AI Breakthrough" 只保留 1 篇
        assert len([a for a in result if "AI Breakthrough" in a.title]) == 1

    def test_cache_prevents_repeat(self, tmp_path: Path):
        cache = SeenCache(cache_path=tmp_path / "seen.json")
        # 第一次
        result1 = deduplicate(self.articles, cache=cache)
        cache.flush()

        # 第二次 — 相同文章应全部命中缓存
        cache2 = SeenCache(cache_path=tmp_path / "seen.json")
        result2 = deduplicate(self.articles, cache=cache2)
        assert len(result2) == 0  # 全部缓存命中
