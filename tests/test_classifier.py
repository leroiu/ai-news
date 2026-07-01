"""
Classifier 测试 — mock AI 调用
"""
import pytest
from unittest.mock import patch, MagicMock
from src.engine.fetcher import Article
from src.engine.classifier import classify, classify_batch, _build_system_prompt, _build_user_prompt


def make_article(aid: str, title: str, source: str = "Test") -> Article:
    return Article(
        id=aid, title=title, url=f"http://test.com/{aid}",
        source=source, content_raw="Some content about AI.",
    )


class TestPromptBuilding:
    def test_system_prompt_has_categories(self):
        prompt = _build_system_prompt()
        assert "大模型发布" in prompt
        assert "Agent" in prompt
        assert "分类体系" in prompt or "分类" in prompt

    def test_user_prompt_has_article_ids(self):
        articles = [make_article("abc123", "Test Title")]
        prompt = _build_user_prompt(articles)
        assert "abc123" in prompt
        assert "Test Title" in prompt


class TestClassifyBatch:
    def test_empty_articles(self):
        result = classify_batch([])
        assert result == []

    @patch("src.engine.classifier.call_ai")
    def test_successful_classification(self, mock_call):
        mock_call.return_value = [
            {"id": "a1", "categories": ["大模型发布", "Agent"]},
            {"id": "a2", "categories": ["融资/商业"]},
        ]
        articles = [
            make_article("a1", "GPT-5 Released"),
            make_article("a2", "AI Startup Raises $100M"),
        ]
        result = classify_batch(articles)
        assert result[0].categories == ["大模型发布", "Agent"]
        assert result[1].categories == ["融资/商业"]

    @patch("src.engine.classifier.call_ai")
    def test_api_failure_fallback(self, mock_call):
        mock_call.return_value = None
        articles = [make_article("a1", "Some News")]
        result = classify_batch(articles)
        assert result[0].categories == ["未分类"]

    @patch("src.engine.classifier.call_ai")
    def test_missing_id_in_response(self, mock_call):
        mock_call.return_value = [
            {"id": "different", "categories": ["Agent"]},
        ]
        articles = [make_article("a1", "Some News")]
        result = classify_batch(articles)
        assert result[0].categories == ["未分类"]


class TestClassify:
    @patch("src.engine.classifier.classify_batch")
    def test_batches_small_list(self, mock_batch):
        articles = [make_article(f"a{i}", f"News {i}") for i in range(5)]
        mock_batch.return_value = articles
        result = classify(articles, batch_size=25)
        assert len(result) == 5
        mock_batch.assert_called_once()

    @patch("src.engine.classifier.classify_batch")
    def test_batches_large_list(self, mock_batch):
        articles = [make_article(f"a{i}", f"News {i}") for i in range(55)]
        mock_batch.side_effect = lambda x: x  # pass through
        result = classify(articles, batch_size=25)
        assert len(result) == 55
        assert mock_batch.call_count == 3

    def test_empty_list(self):
        assert classify([]) == []
