"""
Summarizer 测试 — mock AI 调用
"""
import pytest
from unittest.mock import patch
from src.engine.fetcher import Article
from src.engine.summarizer import summarize, summarize_batch, _build_system_prompt, _build_user_prompt


def make_article(aid: str, title: str) -> Article:
    return Article(
        id=aid, title=title, url=f"http://test.com/{aid}",
        source="TechCrunch", content_raw="Detailed article content about AI advances.",
    )


class TestPromptBuilding:
    def test_system_prompt_no_knowledge(self):
        prompt = _build_system_prompt()
        assert "摘要" in prompt or "summar" in prompt.lower()
        assert "中文" in prompt

    def test_system_prompt_with_knowledge(self):
        prompt = _build_system_prompt(knowledge_context="## 历史背景\nGPT-4 was released in 2023.")
        assert "GPT-4" in prompt
        assert "历史背景" in prompt

    def test_user_prompt_has_content(self):
        articles = [make_article("a1", "AI Breakthrough")]
        prompt = _build_user_prompt(articles)
        assert "a1" in prompt
        assert "AI Breakthrough" in prompt
        assert "Detailed article content" in prompt


class TestSummarizeBatch:
    @patch("src.engine.summarizer.call_ai")
    def test_successful_summary(self, mock_call):
        mock_call.return_value = [
            {"id": "a1", "title_cn": "AI突破", "one_liner": "重大进展",
             "summary_points": ["点1", "点2", "点3"]},
        ]
        articles = [make_article("a1", "AI Breakthrough")]
        result = summarize_batch(articles)
        assert result[0].title_cn == "AI突破"
        assert result[0].one_liner == "重大进展"
        assert len(result[0].summary_points) == 3

    @patch("src.engine.summarizer.call_ai")
    def test_api_failure_no_crash(self, mock_call):
        mock_call.return_value = None
        articles = [make_article("a1", "News")]
        result = summarize_batch(articles)
        assert len(result) == 1  # articles still returned

    @patch("src.engine.summarizer.call_ai")
    def test_knowledge_context_passed(self, mock_call):
        mock_call.return_value = [{"id": "a1", "title_cn": "T", "one_liner": "O",
                                    "summary_points": []}]
        articles = [make_article("a1", "News")]
        summarize_batch(articles, knowledge_context="Context about GPT-4")
        # Verify the system prompt passed to call_ai includes the context
        call_args = mock_call.call_args
        system_prompt = call_args[0][0]
        assert "GPT-4" in system_prompt

    def test_empty_articles(self):
        assert summarize_batch([]) == []


class TestSummarize:
    @patch("src.engine.summarizer.summarize_batch")
    def test_batches(self, mock_batch):
        articles = [make_article(f"a{i}", f"News {i}") for i in range(25)]
        mock_batch.side_effect = lambda x, knowledge_context="": x
        result = summarize(articles, batch_size=10)
        assert len(result) == 25
        assert mock_batch.call_count == 3

    def test_empty(self):
        assert summarize([]) == []
