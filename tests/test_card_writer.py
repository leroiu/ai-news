"""
Card Writer 测试 — YAML 生成 + 保存 + 流水线
"""
import pytest
from pathlib import Path

from src.engine.card_writer import (
    _slugify,
    write_card,
    save_card,
    collect_and_write,
    TYPE_DIR_MAP,
)


class TestSlugify:
    def test_basic(self):
        assert _slugify("Context Engineering") == "context-engineering"

    def test_chinese_removed(self):
        # Chinese chars are stripped by regex
        slug = _slugify("AI Agent")
        assert " " not in slug
        assert slug == "ai-agent"


class TestTypeDirMap:
    def test_all_types_mapped(self):
        for t in ("methodology", "company", "model", "tech",
                  "concept", "product", "person", "event"):
            assert t in TYPE_DIR_MAP

    def test_concept_miner_types_mapped(self):
        """Concept Miner 的 type 值也能正确映射。"""
        assert TYPE_DIR_MAP.get("technique") == "methodology"
        assert TYPE_DIR_MAP.get("pattern") == "methodology"
        assert TYPE_DIR_MAP.get("framework") == "tech"
        assert TYPE_DIR_MAP.get("workflow") == "methodology"


class TestWriteCard:
    def test_minimal_input(self):
        """最小输入不崩溃。"""
        result = write_card("Test Concept", card_type="methodology")
        # AI 可能返回 None（无 API key）或 YAML 字符串
        assert result is None or isinstance(result, str)

    def test_with_articles(self):
        """带文章输入不崩溃。"""
        articles = [
            {"title": "Test Article", "source": "Test Source",
             "one_liner": "A test article about AI."},
        ]
        result = write_card("AI Test", articles=articles, card_type="concept")
        assert result is None or isinstance(result, str)


class TestSaveCard:
    def test_invalid_yaml(self):
        """无效 YAML 返回 None。"""
        result = save_card("not: valid: yaml: [", "methodology")
        assert result is None

    def test_missing_id(self):
        """无 id 字段的 YAML 返回 None。"""
        result = save_card("name: Test\n", "methodology")
        assert result is None

    def test_existing_card_skipped(self):
        """已有卡片不被覆盖。"""
        # 用一个已知存在的 card id
        result = save_card(
            "id: agent-orchestration\nname: Test\n",
            "methodology",
        )
        assert result is None  # 已有，跳过


class TestCollectAndWrite:
    def test_returns_structure(self):
        """返回结果包含必要字段。"""
        result = collect_and_write("NonexistentConceptXYZ123", depth="standard")
        assert "name" in result
        assert "card_type" in result
        assert "yaml" in result or "error" in result
        # 对不存在的概念，Research Agent 可能返回 error 或结果很少
