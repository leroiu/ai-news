"""
Trend Agent 测试 — 趋势扫描 + 去重合并 + 知识库增强
"""
import pytest

from src.engine.trend_agent import (
    _normalize_name,
    _merge_trends,
    _scan_reports,
)


class TestNormalizeName:
    def test_lowercase(self):
        assert _normalize_name("AI Agent") == _normalize_name("ai agent")

    def test_chinese(self):
        assert _normalize_name("大模型") == _normalize_name("大模型")

    def test_special_chars_removed(self):
        name = _normalize_name("AI Agent / RAG")
        assert "/" not in name
        assert " " not in name


class TestMergeTrends:
    def test_empty(self):
        assert _merge_trends([]) == []

    def test_single(self):
        trends = [{"trend": "AI Agent", "description": "test", "evidence": ["a"], "importance": 3}]
        result = _merge_trends(trends)
        assert len(result) == 1

    def test_duplicates_merged(self):
        trends = [
            {"trend": "AI Agent", "description": "desc1", "evidence": ["ev1"], "importance": 3},
            {"trend": "ai agent", "description": "desc2", "evidence": ["ev2"], "importance": 4},
        ]
        result = _merge_trends(trends)
        assert len(result) == 1
        assert len(result[0]["evidence"]) == 2

    def test_distinct_not_merged(self):
        trends = [
            {"trend": "AI Agent", "description": "d1", "evidence": ["e1"], "importance": 3},
            {"trend": "Multimodal Models", "description": "d2", "evidence": ["e2"], "importance": 4},
        ]
        result = _merge_trends(trends)
        assert len(result) == 2

    def test_sorted_by_importance(self):
        trends = [
            {"trend": "Low Trend", "description": "d1", "evidence": ["e1"], "importance": 1},
            {"trend": "High Trend", "description": "d2", "evidence": ["e2"], "importance": 5},
        ]
        result = _merge_trends(trends)
        assert result[0]["importance"] >= result[-1]["importance"]


class TestScanReports:
    def test_empty_reports(self):
        """空日报列表不崩溃。"""
        result = _scan_reports([], "week")
        assert isinstance(result, list)

    def test_fake_reports_handled(self):
        """假日报数据不崩溃（AI 可能返回空或无趋势）。"""
        fake_reports = [
            ("2026-07-01", "Today AI made progress in agent development."),
            ("2026-07-02", "More advances in AI agent frameworks."),
        ]
        result = _scan_reports(fake_reports, "week", batch_size=2)
        assert isinstance(result, list)
