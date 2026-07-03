"""
Tests for embeddings.py — semantic search and vector storage.
Uses temp DB + mocked API calls.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from src.engine.database import (
    init_db, upsert_entity, get_entities, DB_PATH,
)
from src.engine.embeddings import (
    cosine_similarity,
    build_card_embedding_text,
    init_embeddings_table,
    store_embedding,
    get_embedding,
    get_all_embeddings,
    search_semantic,
    search_hybrid,
    match_cards_semantic,
    rebuild_card_embeddings,
)


# ── Helpers ──────────────────────────────────────────────


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Redirect DB_PATH to a temp file."""
    tmp_db = tmp_path / "test_platform.db"
    monkeypatch.setattr("src.engine.db_core.DB_PATH", tmp_db)
    monkeypatch.setattr("src.engine.embeddings.ROOT_DIR", tmp_path.parent)
    init_db()
    init_embeddings_table()
    # Seed test entities
    for eid, name, etype, summary, significance in [
        ("gpt-4", "GPT-4", "model", "OpenAI flagship LLM", "Set new benchmark"),
        ("claude", "Claude", "model", "Anthropic assistant", "Safety-focused AI"),
        ("transformer", "Transformer", "tech", "Attention architecture", "Revolutionized NLP"),
    ]:
        upsert_entity({
            "id": eid, "name": name, "type": etype,
            "summary": summary, "significance": significance,
            "tags": [], "aliases": [], "timeline": [],
        })
    yield
    if tmp_db.exists():
        tmp_db.unlink()


@pytest.fixture
def mock_embed_api(monkeypatch):
    """Patch ai_client.embed_texts (lazy-imported by embeddings module)."""
    def fake_embed(texts):
        # Simple mock: each vector has 3 dims based on text length
        return [[len(t) * 0.01, len(t) * 0.02, 1.0] for t in texts]
    monkeypatch.setattr("src.engine.ai_client.embed_texts", fake_embed)
    return fake_embed


# ── Cosine Similarity ────────────────────────────────────


class TestCosineSimilarity:
    def test_identical(self):
        v = [1.0, 2.0, 3.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal(self):
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_opposite(self):
        assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)

    def test_empty(self):
        assert cosine_similarity([], []) == 0.0

    def test_mismatched_lengths(self):
        assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0

    def test_zero_norm(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0


# ── Embedding Text Builder ────────────────────────────────


class TestBuildCardEmbeddingText:
    def test_full_card(self):
        card = {"name": "GPT-4", "summary": "Flagship LLM", "significance": "Important"}
        text = build_card_embedding_text(card)
        assert "GPT-4" in text
        assert "Flagship LLM" in text
        assert "Important" in text

    def test_no_significance(self):
        card = {"name": "GPT-4", "summary": "Flagship LLM"}
        text = build_card_embedding_text(card)
        assert "GPT-4" in text
        assert "Flagship LLM" in text

    def test_empty_card(self):
        card = {"name": ""}
        text = build_card_embedding_text(card)
        assert text == ""


# ── Embedding Storage ─────────────────────────────────────


class TestEmbeddingStorage:
    def test_store_and_get(self):
        store_embedding("gpt-4", [1.0, 2.0, 3.0])
        v = get_embedding("gpt-4")
        assert v == [1.0, 2.0, 3.0]

    def test_get_nonexistent(self):
        assert get_embedding("nonexistent") is None

    def test_update_existing(self):
        store_embedding("gpt-4", [1.0, 2.0])
        store_embedding("gpt-4", [4.0, 5.0, 6.0])
        v = get_embedding("gpt-4")
        assert v == [4.0, 5.0, 6.0]

    def test_get_all(self):
        store_embedding("gpt-4", [1.0])
        store_embedding("claude", [2.0])
        all_v = get_all_embeddings()
        assert len(all_v) == 2
        assert "gpt-4" in all_v
        assert "claude" in all_v


# ── Rebuild Card Embeddings ───────────────────────────────


class TestRebuildCardEmbeddings:
    def test_rebuild_creates(self, mock_embed_api):
        result = rebuild_card_embeddings(force=True)
        assert result["embedded"] == 3  # 3 seeded entities
        assert result["failed"] == 0
        all_v = get_all_embeddings()
        assert len(all_v) == 3

    def test_rebuild_skips_existing(self, mock_embed_api):
        store_embedding("gpt-4", [1.0, 2.0, 3.0])
        result = rebuild_card_embeddings(force=False)
        assert result["embedded"] == 2  # claude + transformer
        assert result["skipped"] == 1  # gpt-4
        all_v = get_all_embeddings()
        assert len(all_v) == 3

    def test_rebuild_force_overwrites(self, mock_embed_api):
        store_embedding("gpt-4", [1.0, 2.0])
        result = rebuild_card_embeddings(force=True)
        assert result["embedded"] == 3
        v = get_embedding("gpt-4")
        assert len(v) == 3  # new vector has 3 dims from mock


# ── Semantic Search ───────────────────────────────────────


class TestSemanticSearch:
    def test_returns_results(self, mock_embed_api):
        # First build embeddings
        rebuild_card_embeddings(force=True)
        results = search_semantic("LLM model", limit=10)
        assert len(results) > 0
        # Each result should have _semantic_score
        assert "_semantic_score" in results[0]

    def test_empty_without_embeddings(self):
        results = search_semantic("LLM model")
        assert results == []

    def test_score_ordering(self, mock_embed_api):
        rebuild_card_embeddings(force=True)
        results = search_semantic("LLM model", limit=10)
        scores = [r["_semantic_score"] for r in results]
        assert scores == sorted(scores, reverse=True)


# ── Hybrid Search ─────────────────────────────────────────


class TestHybridSearch:
    def test_returns_mode(self, mock_embed_api):
        rebuild_card_embeddings(force=True)
        result = search_hybrid("model", limit=10)
        assert result["mode"] == "hybrid"

    def test_keyword_only(self):
        result = search_hybrid("model", limit=10)
        assert result["mode"] == "keyword"

    def test_alpha_zero(self, mock_embed_api):
        rebuild_card_embeddings(force=True)
        result = search_hybrid("model", limit=10, alpha=0.0)
        assert result["mode"] == "hybrid"
        assert result["alpha"] == 0.0

    def test_alpha_one(self):
        result = search_hybrid("model", limit=10, alpha=1.0)
        assert result["mode"] == "keyword"

    def test_empty_query(self, mock_embed_api):
        rebuild_card_embeddings(force=True)
        result = search_hybrid("", limit=10)
        assert "entities" in result
        assert "articles" in result


# ── Semantic Card Matching ────────────────────────────────


class FakeArticle:
    def __init__(self, aid, title, categories=None):
        self.id = aid
        self.title = title
        self.categories = categories or []


class FakeCard:
    def __init__(self, cid, name, etype="model", summary="", tags=None):
        self.id = cid
        self.name = name
        self.type = etype
        self.summary = summary
        self.tags = tags or []
        self.importance = 3


class TestSemanticCardMatching:
    def test_matches_when_embeddings_ready(self, mock_embed_api):
        rebuild_card_embeddings(force=True)
        articles = [FakeArticle("a1", "OpenAI releases new language model")]
        cards = [
            FakeCard("gpt-4", "GPT-4", summary="OpenAI flagship LLM"),
            FakeCard("claude", "Claude", summary="Anthropic assistant"),
        ]
        result = match_cards_semantic(articles, cards, min_score=0.0)
        assert "a1" in result
        assert len(result["a1"]) > 0

    def test_empty_when_no_embeddings(self):
        articles = [FakeArticle("a1", "test")]
        cards = [FakeCard("gpt-4", "GPT-4")]
        result = match_cards_semantic(articles, cards)
        assert result == {}

    def test_max_per_article(self, mock_embed_api):
        rebuild_card_embeddings(force=True)
        articles = [FakeArticle("a1", "AI model")]
        cards = [
            FakeCard("gpt-4", "GPT-4", summary="LLM"),
            FakeCard("claude", "Claude", summary="AI assistant"),
            FakeCard("transformer", "Transformer", summary="Architecture"),
        ]
        result = match_cards_semantic(articles, cards, min_score=0.0, max_per_article=2)
        assert len(result["a1"]) <= 2

    def test_min_score_threshold(self, mock_embed_api):
        rebuild_card_embeddings(force=True)
        articles = [FakeArticle("a1", "AI model")]
        cards = [FakeCard("gpt-4", "GPT-4", summary="LLM")]
        # Very high threshold should filter everything
        result = match_cards_semantic(articles, cards, min_score=0.999)
        assert len(result.get("a1", [])) == 0
