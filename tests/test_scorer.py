"""
Scorer 测试 — 规则评分
"""

from src.engine.fetcher import Article
from src.engine.scorer import score, score_article, _load_scoring_config
from src.engine.utils import load_config


def make_article(aid: str, title: str = "Test", source: str = "Hacker News (AI 相关)",
                  published: str = "2026-07-06T10:00:00Z",
                  content_raw: str = "Test content", url: str = None) -> Article:
    return Article(
        id=aid, title=title, url=url or f"http://test.com/{aid}",
        source=source, published=published, content_raw=content_raw,
    )


class TestScoreArticle:
    def setup_method(self):
        self.cfg = _load_scoring_config()
        self.config = load_config()

    def test_openai_blog_high_score(self):
        """OpenAI Blog + 发布关键词 + 新颖 → 高★"""
        a = make_article("a1", "OpenAI Launches GPT-5", source="OpenAI Blog",
                         published="2026-07-06T10:00:00Z",
                         content_raw="OpenAI announced a major breakthrough today.")
        result = score_article(a, self.cfg, self.config)
        assert result.score >= 3, f"Expected >=3★, got {result.score}★"
        assert result.score_reason.startswith("规则评分:")
        assert isinstance(result.score_breakdown, dict)

    def test_user_interest_boost(self):
        """命中用户兴趣关键词 → 加分"""
        a = make_article("a2", "DeepSeek releases new model",
                         source="Hacker News (AI 相关)",
                         content_raw="DeepSeek breakthrough.")
        result = score_article(a, self.cfg, self.config)
        kw = result.score_breakdown["keyword_match"]
        assert kw > 0, f"Expected keyword_match > 0, got {kw}"

    def test_sponsored_penalty(self):
        """赞助/广告内容 → 扣分"""
        a = make_article("a3", "Sponsored post", source="TechCrunch AI",
                         content_raw="This sponsored content.")
        result = score_article(a, self.cfg, self.config)
        kw = result.score_breakdown["keyword_match"]
        assert kw == 0, f"Expected keyword_match=0 (penalized), got {kw}"

    def test_old_article_low_recency(self):
        """旧文章 → 低时效分"""
        a = make_article("a4", "Old news", source="Reddit r/artificial",
                         published="2026-06-01T10:00:00Z")
        result = score_article(a, self.cfg, self.config)
        rec = result.score_breakdown["recency"]
        assert rec <= 30, f"Expected low recency, got {rec}"

    def test_score_breakdown_keys(self):
        """score_breakdown 包含所有维度"""
        a = make_article("a5", "Test article")
        result = score_article(a, self.cfg, self.config)
        assert set(result.score_breakdown.keys()) == {
            "source_authority", "keyword_match", "recency",
            "high_authority_bonus", "final", "stars",
        }

    def test_score_range(self):
        """所有文章评分在 1-5★ 范围内"""
        articles = [
            make_article("b1", "Big news from high source", source="OpenAI Blog"),
            make_article("b2", "Medium news", source="TechCrunch AI"),
            make_article("b3", "Old low quality", source="Reddit r/artificial",
                         published="2026-06-01T10:00:00Z"),
            make_article("b4", "Sponsored with penalty", source="The Verge AI",
                         content_raw="This opinion piece is sponsored content."),
        ]
        scored = score(articles)
        for a in scored:
            assert 1 <= a.score <= 5, f"Score {a.score} out of range"
            assert 0 <= a.score_breakdown["final"] <= 100


class TestScoreFunction:
    def setup_method(self):
        self.cfg = _load_scoring_config()
        self.config = load_config()

    def test_empty_input(self):
        assert score([]) == []

    def test_batch_scoring(self):
        articles = [make_article(f"c{i}", f"Article {i}") for i in range(10)]
        result = score(articles)
        assert len(result) == 10
        for a in result:
            assert a.score > 0  # 每个文章都有评分

    def test_source_authority_matters(self):
        """不同来源权威性 → 不同评分"""
        high = make_article("d1", "News", source="OpenAI Blog")
        low = make_article("d2", "News", source="Reddit r/artificial")
        high_cfg = score_article(high, self.cfg if hasattr(self, 'cfg') else _load_scoring_config(),
                                 self.config if hasattr(self, 'config') else load_config())
        low_cfg = score_article(low, _load_scoring_config(), load_config())
        assert high_cfg.score >= low_cfg.score, "High authority source should score >= low authority"
