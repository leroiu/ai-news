"""
Concept Miner 测试 — 候选池管理（无 AI 依赖）
"""
import json
import pytest
from pathlib import Path
from src.engine.concept_miner import (
    _slugify, _is_already_known, update_pool, get_pool_summary, POOL_PATH,
)
from src.engine.fetcher import Article


class TestSlugify:
    def test_basic(self):
        assert _slugify("Context Engineering") == "context-engineering"

    def test_special_chars(self):
        slug = _slugify("RAG / Retrieval Augmented Generation")
        assert slug.startswith("rag")
        assert "retrieval" in slug
        assert "augmented" in slug

    def test_truncation(self):
        long_name = "a" * 60
        assert len(_slugify(long_name)) <= 50


class TestIsAlreadyKnown:
    def test_exact_match(self):
        known = {"gpt-4": {"gpt-4", "gpt4", "gpt 4"}}
        assert _is_already_known("GPT-4", known) is True
        assert _is_already_known("GPT4", known) is True

    def test_no_match(self):
        known = {"transformer": {"transformer"}}
        assert _is_already_known("New Concept XYZ", known) is False

    def test_substring_match(self):
        known = {"context engineering": {"context engineering", "context eng"}}
        assert _is_already_known("Context Engineering", known) is True


class TestUpdatePool:
    def setup_method(self):
        # Don't touch real pool
        self.orig_path = POOL_PATH

    def test_new_candidate_enters_pool(self, tmp_path: Path):
        import src.engine.concept_miner as cm
        old_path = cm.POOL_PATH
        fake_pool = tmp_path / "candidate_concepts.json"
        fake_pool.write_text(json.dumps({"candidates": {}, "last_updated": ""}))
        cm.POOL_PATH = fake_pool

        try:
            candidates = [{
                "name": "New Agent Pattern",
                "type": "pattern",
                "confidence": 0.8,
                "evidence": "This is a new agent pattern...",
                "should_create_card": True,
            }]
            actions = update_pool(candidates, [], dry_run=False)
            assert "New Agent Pattern" in actions

            pool = json.loads(fake_pool.read_text())
            slug = _slugify("New Agent Pattern")
            assert slug in pool["candidates"]
            assert pool["candidates"][slug]["occurrences"] == 1
        finally:
            cm.POOL_PATH = old_path

    def test_skips_already_known(self, tmp_path: Path):
        import src.engine.concept_miner as cm
        old_path = cm.POOL_PATH
        fake_pool = tmp_path / "candidate_concepts.json"
        fake_pool.write_text(json.dumps({"candidates": {}, "last_updated": ""}))
        cm.POOL_PATH = fake_pool

        try:
            # "transformer" is a known card
            candidates = [{
                "name": "Transformer Architecture",
                "type": "methodology",
                "confidence": 1.0,
                "evidence": "test",
                "should_create_card": False,
            }]
            actions = update_pool(candidates, [], dry_run=False)
            assert len(actions) == 0  # skipped
        finally:
            cm.POOL_PATH = old_path


class TestGetPoolSummary:
    def test_empty_pool(self, tmp_path: Path):
        import src.engine.concept_miner as cm
        old_path = cm.POOL_PATH
        fake_pool = tmp_path / "candidate_concepts.json"
        fake_pool.write_text(json.dumps({"candidates": {}, "last_updated": ""}))
        cm.POOL_PATH = fake_pool

        try:
            summary = get_pool_summary()
            assert summary["total"] == 0
        finally:
            cm.POOL_PATH = old_path
