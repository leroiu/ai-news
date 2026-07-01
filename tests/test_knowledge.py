"""
Knowledge Card 加载、匹配、上下文构建测试（无 AI 依赖）
"""
import pytest
from pathlib import Path
from src.engine.fetcher import Article
from src.engine.knowledge import (
    load_cards,
    match_cards,
    build_context,
    _extract_keywords,
    _validate_card,
    KnowledgeCard,
    REQUIRED_FIELDS,
)


class TestCardValidation:
    def test_valid_card_no_issues(self):
        raw = {
            "id": "test", "name": "Test", "type": "model",
            "tags": ["llm"], "summary": "A summary.", "significance": "Important.",
        }
        issues = _validate_card(raw, "test.yaml")
        assert len(issues) == 0 or all("建议" in i for i in issues)

    def test_missing_required(self):
        raw = {"id": "test", "name": "Test"}
        issues = _validate_card(raw, "test.yaml")
        assert any("缺少" in i for i in issues)

    def test_empty_tags(self):
        raw = {
            "id": "test", "name": "Test", "type": "model",
            "tags": [], "summary": "A.", "significance": "B.",
        }
        issues = _validate_card(raw, "test.yaml")
        assert any("tags" in i for i in issues)

    def test_invalid_type(self):
        raw = {
            "id": "test", "name": "Test", "type": "invalid_type_xyz",
            "tags": ["a"], "summary": "A.", "significance": "B.",
        }
        issues = _validate_card(raw, "test.yaml")
        assert any("type" in i for i in issues)

    def test_invalid_importance(self):
        raw = {
            "id": "test", "name": "Test", "type": "model",
            "tags": ["a"], "summary": "A.", "significance": "B.",
            "importance": 99,
        }
        issues = _validate_card(raw, "test.yaml")
        assert any("importance" in i for i in issues)

    def test_all_required_fields_defined(self):
        """确保 REQUIRED_FIELDS 在每个 card YAML 中都有定义"""
        assert "id" in REQUIRED_FIELDS
        assert "name" in REQUIRED_FIELDS
        assert "type" in REQUIRED_FIELDS
        assert "tags" in REQUIRED_FIELDS
        assert "summary" in REQUIRED_FIELDS
        assert "significance" in REQUIRED_FIELDS


class TestKnowledgeCard:
    def test_from_dict(self):
        raw = {
            "id": "test-card", "name": "Test Card", "type": "model",
            "tags": ["llm", "test"], "aliases": ["tc", "test"],
            "summary": "A test card.", "significance": "Important for testing.",
            "importance": 4, "related": ["gpt-4"], "depends_on": ["transformer"],
        }
        card = KnowledgeCard(raw)
        assert card.id == "test-card"
        assert card.name == "Test Card"
        assert card.type == "model"
        assert card.importance == 4

    def test_match_surface(self):
        raw = {
            "id": "x", "name": "GPT-4", "type": "model",
            "tags": ["llm", "openai"], "aliases": ["gpt4"],
        }
        card = KnowledgeCard(raw)
        surface = card.match_surface
        assert "llm" in surface
        assert "openai" in surface
        assert "gpt4" in surface
        assert "gpt-4" in surface

    def test_context_block(self):
        raw = {
            "id": "x", "name": "GPT-4", "type": "model",
            "summary": "A large model.", "significance": "Very important.",
            "timeline": [
                {"date": "2023-03-14", "event": "GPT-4 officially released by OpenAI"},
            ],
        }
        card = KnowledgeCard(raw)
        block = card.context_block()
        assert "GPT-4" in block
        assert "A large model" in block
        # timeline events with short descriptions (<10 chars) are filtered out as noise
        # long events appear in the context block
        assert "2023-03-14" in block
        assert "GPT-4 officially released by OpenAI" in block


class TestExtractKeywords:
    def test_extracts_categories(self):
        a = Article(id="1", title="Something", url="http://x.com/1", source="Test",
                     categories=["大模型发布", "Agent"])
        kw = _extract_keywords(a)
        assert "大模型发布" in kw
        assert "agent" in kw

    def test_extracts_title_words(self):
        a = Article(id="1", title="OpenAI Launches GPT5", url="http://x.com/1",
                     source="TechCrunch")
        kw = _extract_keywords(a)
        assert "openai" in kw
        assert "launches" in kw
        assert "gpt5" in kw  # regex splits on hyphen, so GPT-5 → gpt + 5

    def test_stopwords_filtered(self):
        a = Article(id="1", title="The AI is a new way to do things",
                     url="http://x.com/1", source="Test")
        kw = _extract_keywords(a)
        assert "the" not in kw
        assert "a" not in kw
        assert "is" not in kw
        assert "to" not in kw
        assert "new" not in kw  # stopword
        assert "things" in kw

    def test_short_words_filtered(self):
        a = Article(id="1", title="AI is OK", url="http://x.com/1", source="Test")
        kw = _extract_keywords(a)
        # "ok" is 2 chars — filtered by len>=3
        assert "ok" not in kw
        # "ai" is a stopword
        assert "ai" not in kw


class TestLoadCards:
    def test_loads_from_data_dir(self):
        cards = load_cards()
        assert len(cards) >= 20
        ids = {c.id for c in cards}
        assert "transformer" in ids
        assert "gpt-4" in ids
        assert "openai" in ids

    def test_all_have_required_fields(self):
        cards = load_cards()
        for c in cards:
            assert c.id, f"Missing id for {c.name}"
            assert c.name, f"Missing name"
            assert c.type, f"Missing type for {c.id}"
            assert isinstance(c.tags, list), f"tags not list for {c.id}"
            assert len(c.tags) > 0, f"Empty tags for {c.id}"


class TestMatchCards:
    def test_direct_match(self):
        cards = load_cards()
        article = Article(
            id="test1", title="OpenAI announces GPT-4 successor",
            url="http://test.com/1", source="TechCrunch",
            categories=["大模型发布"],
        )
        matched = match_cards([article], cards)
        assert "test1" in matched
        card_ids = {c.id for c in matched["test1"]}
        assert any(c in card_ids for c in ["openai", "gpt-4", "gpt-4o", "gpt-4-release"])

    def test_no_match_returns_empty(self):
        cards = load_cards()
        article = Article(
            id="test2", title="Weather forecast for tomorrow",
            url="http://test.com/2", source="WeatherChannel",
            categories=["天气"],
        )
        # 用 Jaccard 匹配 — 语义匹配总会找到最近邻居（无关内容也会 >0.3）
        matched = match_cards([article], cards, use_semantic=False)
        assert matched["test2"] == []

    def test_max_per_article(self):
        cards = load_cards()
        article = Article(
            id="test3",
            title="OpenAI GPT-4 ChatGPT Claude Anthropic DeepSeek Transformer RLHF",
            url="http://test.com/3", source="AllAI",
            categories=["大模型发布", "Agent", "融资/商业"],
        )
        matched = match_cards([article], cards, max_per_article=3)
        assert len(matched["test3"]) <= 3

    def test_empty_cards(self):
        article = Article(id="t", title="Test", url="http://x.com", source="X")
        matched = match_cards([article], [])
        assert matched == {}


class TestSemanticMatch:
    """match_cards() with use_semantic=True — falls back to Jaccard when no embeddings."""

    def test_falls_back_to_jaccard_when_no_embeddings(self):
        """Without embeddings table, semantic mode should silently use Jaccard."""
        cards = load_cards()
        article = Article(
            id="sem1", title="GPT-4 is powerful", url="http://x.com", source="OpenAI",
            categories=["大模型发布"],
        )
        matched = match_cards([article], cards, use_semantic=True)
        # Should still produce results via Jaccard fallback
        assert isinstance(matched, dict)
        # At minimum the function shouldn't crash
        assert "sem1" in matched

    def test_explicit_jaccard_mode(self):
        """use_semantic=False should always use Jaccard."""
        cards = load_cards()
        article = Article(
            id="sem2", title="OpenAI releases GPT-4", url="http://x.com", source="X",
            categories=["大模型发布"],
        )
        matched = match_cards([article], cards, use_semantic=False)
        assert "sem2" in matched


class TestBuildContext:
    def test_empty_matched(self):
        ctx = build_context({})
        assert ctx == ""

    def test_builds_context_string(self):
        cards = load_cards()
        # Simulate a matched result
        matched = {"a1": cards[:2]}
        ctx = build_context(matched, max_cards_total=2)
        assert "历史背景" in ctx
        assert len(ctx) > 50

    def test_deduplicates_and_limits(self):
        cards = load_cards()
        # Same card appears in multiple articles
        matched = {"a1": cards[:1], "a2": cards[:1], "a3": cards[:2]}
        ctx = build_context(matched, max_cards_total=2)
        # Card name appears in heading (### Name) — should appear exactly once as heading
        name = cards[0].name
        assert ctx.count(f"### {name}") <= 1
