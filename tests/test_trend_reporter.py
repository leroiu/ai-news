"""
Trend Reporter 测试 — mock AI 调用 + 格式化函数
"""
import pytest
from pathlib import Path
from unittest.mock import patch
from src.engine.trend_reporter import (
    _find_daily_reports,
    _format_top5,
    _format_trends,
    _format_signals,
    _format_new_players,
    _format_daily_index,
    generate_trend_report,
)


class TestFormatTop5:
    def test_formats_items(self):
        top5 = [
            {"title": "GPT-5 Released", "why": "Big milestone", "importance": 5},
            {"title": "Minor update", "why": "Not important", "importance": 2},
        ]
        result = _format_top5(top5)
        assert "GPT-5 Released" in result
        assert "Big milestone" in result
        assert "★★★★★" in result

    def test_empty(self):
        assert _format_top5([]) == ""


class TestFormatTrends:
    def test_formats_trends_with_evidence(self):
        trends = [
            {"trend": "AI Chips", "description": "Custom chips trending.",
             "evidence": ["Mon: OpenAI chip", "Thu: Google chip"]},
        ]
        result = _format_trends(trends)
        assert "AI Chips" in result
        assert "Custom chips" in result
        assert "OpenAI chip" in result
        assert "Google chip" in result

    def test_empty(self):
        assert "无明显新趋势" in _format_trends([])


class TestFormatSignals:
    def test_formats_signals(self):
        signals = [
            {"signal": "Export ban impact", "why_matters": "Market split"},
        ]
        result = _format_signals(signals)
        assert "Export ban impact" in result
        assert "Market split" in result

    def test_empty(self):
        assert "无特殊信号" in _format_signals([])


class TestFormatNewPlayers:
    def test_formats_players(self):
        players = [
            {"name": "NewCo", "what": "AI chip startup", "why_worth_watching": "Disruptive"},
        ]
        result = _format_new_players(players)
        assert "NewCo" in result
        assert "AI chip startup" in result

    def test_empty(self):
        assert "无值得关注的新玩家" in _format_new_players([])


class TestFormatDailyIndex:
    def test_formats_links(self, tmp_path: Path):
        reports = [("2026-06-28", "content")]
        result = _format_daily_index(reports, tmp_path)
        assert "2026-06-28" in result
        assert ".md" in result

    def test_empty(self):
        assert "无日报" in _format_daily_index([], Path("."))


class TestGenerateTrendReport:
    @patch("src.engine.trend_reporter._find_daily_reports")
    @patch("src.engine.trend_reporter.call_ai")
    def test_insufficient_reports(self, mock_ai, mock_find, tmp_path: Path):
        mock_find.return_value = [("2026-06-28", "content")]
        result = generate_trend_report(period="week", output_dir=tmp_path)
        assert result is None

    @patch("src.engine.trend_reporter._find_daily_reports")
    @patch("src.engine.trend_reporter.call_ai")
    def test_ai_failure(self, mock_ai, mock_find, tmp_path: Path):
        mock_find.return_value = [
            ("2026-06-27", "day 1 content"),
            ("2026-06-28", "day 2 content"),
        ]
        mock_ai.return_value = None
        result = generate_trend_report(period="week", output_dir=tmp_path)
        assert result is None

    @patch("src.engine.trend_reporter._find_daily_reports")
    @patch("src.engine.trend_reporter.call_ai")
    def test_generates_weekly_report(self, mock_ai, mock_find, tmp_path: Path):
        mock_find.return_value = [
            ("2026-06-27", "day 1"),
            ("2026-06-28", "day 2"),
        ]
        mock_ai.return_value = {
            "headline": "A big week for AI",
            "top5": [{"title": "News 1", "why": "Important", "importance": 5}],
            "trends": [],
            "signals": [],
            "new_players": [],
        }
        result = generate_trend_report(period="week", output_dir=tmp_path)
        assert result is not None
        assert result.suffix == ".md"
        content = result.read_text(encoding="utf-8")
        assert "A big week for AI" in content
        assert "News 1" in content

    @patch("src.engine.trend_reporter._find_daily_reports")
    @patch("src.engine.trend_reporter.call_ai")
    def test_generates_monthly_report(self, mock_ai, mock_find, tmp_path: Path):
        mock_find.return_value = [
            ("2026-06-27", "day 1"),
            ("2026-06-28", "day 2"),
        ]
        mock_ai.return_value = {
            "headline": "Monthly summary",
            "top5": [],
            "trends": [],
            "signals": [],
            "new_players": [],
        }
        result = generate_trend_report(period="month", output_dir=tmp_path)
        assert result is not None
        assert "monthly" in result.name
