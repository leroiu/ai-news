"""
Scorer 测试 — mock AI 调用
"""
import pytest
from unittest.mock import patch
from src.engine.fetcher import Article
from src.engine.scorer import score, score_batch, _build_system_prompt, _build_user_prompt


def make_article(aid: str, title: str, categories=None, one_liner=""):
    return Article(
        id=aid, title=title, url=f"http://test.com/{aid}",
        source="TechCrunch", categories=categories or ["大模型发布"],
        one_liner=one_liner or "A summary.",
    )


class TestPromptBuilding:
    def test_system_prompt_has_interests(self):
        prompt = _build_system_prompt()
        assert "Claude Code" in prompt or "AI Coding" in prompt or "高优先级" in prompt

    def test_system_prompt_has_scoring_criteria(self):
        prompt = _build_system_prompt()
        assert "★★★★★" in prompt or "行业" in prompt

    def test_user_prompt_has_ids(self):
        articles = [make_article("abc", "GPT-5 Released", categories=["大模型发布"])]
        prompt = _build_user_prompt(articles)
        assert "abc" in prompt
        assert "GPT-5 Released" in prompt


class TestScoreBatch:
    @patch("src.engine.scorer.call_ai")
    def test_successful_scoring(self, mock_call):
        mock_call.return_value = [
            {"id": "a1", "score": 5, "score_reason": "Milestone release", "cluster_id": "gpt5-launch"},
            {"id": "a2", "score": 3, "score_reason": "Regular news", "cluster_id": None},
        ]
        articles = [
            make_article("a1", "GPT-5 Released"),
            make_article("a2", "Minor update"),
        ]
        result = score_batch(articles)
        assert result[0].score == 5
        assert result[0].score_reason == "Milestone release"
        assert result[0].cluster_id == "gpt5-launch"
        assert result[1].score == 3

    @patch("src.engine.scorer.call_ai")
    def test_api_failure_defaults(self, mock_call):
        mock_call.return_value = None
        articles = [make_article("a1", "News")]
        result = score_batch(articles)
        # When AI call fails completely, articles returned unchanged (score=0)
        assert len(result) == 1

    @patch("src.engine.scorer.call_ai")
    def test_missing_id_defaults(self, mock_call):
        mock_call.return_value = [{"id": "different", "score": 5, "score_reason": "x"}]
        articles = [make_article("a1", "News")]
        result = score_batch(articles)
        assert result[0].score == 3  # default when no match

    def test_empty_articles(self):
        assert score_batch([]) == []


class TestScore:
    @patch("src.engine.scorer.score_batch")
    def test_batches(self, mock_batch):
        articles = [make_article(f"a{i}", f"News {i}") for i in range(45)]
        mock_batch.side_effect = lambda x: x
        result = score(articles, batch_size=25)
        assert len(result) == 45
        assert mock_batch.call_count == 2

    def test_empty(self):
        assert score([]) == []
