"""
Concept Agent 测试 — 语义查找 + AI 决策 + Agent 候选池更新
"""
import json
import pytest
from pathlib import Path

from src.engine.concept_agent import (
    _semantic_lookup,
    _fallback_decide,
    assess_concepts,
    update_pool_with_agent,
)
from src.engine.concept_miner import _slugify, POOL_PATH


class TestSemanticLookup:
    def test_returns_list(self):
        """语义查找至少不崩溃，返回 list 类型。"""
        result = _semantic_lookup("Transformer Architecture")
        assert isinstance(result, list)

    def test_empty_name_handled(self):
        """空名称不崩溃。"""
        result = _semantic_lookup("")
        assert isinstance(result, list)

    def test_top_k_respected(self):
        """返回数量不超过 top_k。"""
        result = _semantic_lookup("Machine Learning", top_k=3)
        assert len(result) <= 3

    def test_result_structure(self):
        """返回结果包含必要字段。"""
        result = _semantic_lookup("Neural Network", top_k=2)
        for item in result:
            assert "id" in item
            assert "name" in item
            assert "type" in item
            assert "_similarity" in item
            assert 0.0 <= item["_similarity"] <= 1.0


class TestFallbackDecide:
    def test_new_when_low_similarity(self):
        """相似度低 → NEW。"""
        decision = _fallback_decide(
            {"name": "NewConcept", "confidence": 0.8},
            [{"_similarity": 0.3}, {"_similarity": 0.2}],
        )
        assert decision["decision"] == "NEW"

    def test_draft_when_high_similarity(self):
        """相似度高 → DRAFT。"""
        decision = _fallback_decide(
            {"name": "ExistingConcept", "confidence": 0.9},
            [{"_similarity": 0.85}],
        )
        assert decision["decision"] == "DRAFT"

    def test_new_when_no_similar_cards(self):
        """无相似卡片 → NEW。"""
        decision = _fallback_decide(
            {"name": "UniqueConcept", "confidence": 0.6},
            [],
        )
        assert decision["decision"] == "NEW"


class TestAssessConcepts:
    def test_empty_candidates(self):
        """空列表不崩溃。"""
        result = assess_concepts([])
        assert isinstance(result, list)
        assert len(result) == 0

    def test_empty_name_skipped(self):
        """空名称候选被跳过。"""
        result = assess_concepts([{"name": "", "type": "technique"}])
        assert len(result) == 0

    def test_valid_candidate_assessed(self):
        """有效候选被评估（可能走 AI 或 fallback）。"""
        result = assess_concepts([
            {"name": "Transformer Neural Architecture", "type": "methodology",
             "confidence": 0.9, "evidence": "The Transformer architecture..."},
        ])
        assert len(result) == 1
        r = result[0]
        assert "decision" in r
        assert r["decision"] in ("NEW", "MERGE", "SKIP", "DRAFT")
        assert "reason" in r
        assert "similar_cards" in r


class TestUpdatePoolWithAgent:
    def setup_method(self):
        self.orig_path = POOL_PATH

    def test_new_concept_enters_pool(self, tmp_path: Path):
        """NEW 决策的概念进入候选池。"""
        import src.engine.concept_miner as cm
        old_path = cm.POOL_PATH
        fake_pool = tmp_path / "candidate_concepts.json"
        fake_pool.write_text(json.dumps({"candidates": {}, "last_updated": ""}))
        cm.POOL_PATH = fake_pool

        try:
            candidates = [{
                "name": "Completely Novel AI Paradigm XYZ",
                "type": "methodology",
                "confidence": 0.7,
                "evidence": "A completely new way of building AI systems...",
                "should_create_card": True,
            }]
            actions = update_pool_with_agent(candidates, [], dry_run=False)
            assert len(actions) > 0
            name = list(actions.keys())[0]
            assert "Completely Novel" in name
            # 读取 pool 验证写入
            pool = json.loads(fake_pool.read_text(encoding="utf-8"))
            slug = _slugify("Completely Novel AI Paradigm XYZ")
            assert slug in pool["candidates"]
            entry = pool["candidates"][slug]
            assert "_agent_decision" in entry
            assert "_agent_reason" in entry
            assert entry["_agent_decision"] in ("NEW", "DRAFT")
        finally:
            cm.POOL_PATH = old_path

    def test_dry_run_does_not_persist(self, tmp_path: Path):
        """dry_run=True 不写入文件。"""
        import src.engine.concept_miner as cm
        old_path = cm.POOL_PATH
        fake_pool = tmp_path / "candidate_concepts.json"
        original = json.dumps({"candidates": {}, "last_updated": ""})
        fake_pool.write_text(original)
        cm.POOL_PATH = fake_pool

        try:
            candidates = [{
                "name": "Dry Run Test Concept",
                "type": "technique",
                "confidence": 0.5,
                "evidence": "test",
                "should_create_card": False,
            }]
            update_pool_with_agent(candidates, [], dry_run=True)
            # 文件内容不变
            assert fake_pool.read_text(encoding="utf-8") == original
        finally:
            cm.POOL_PATH = old_path
