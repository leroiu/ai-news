"""
Fetcher 单元测试
"""

import pytest
from datetime import datetime, timezone, timedelta

from src.engine.fetcher import (
    Article,
    parse_feed,
    filter_recent,
    _parse_date,
)


class TestArticle:
    def test_make_id(self):
        a = Article.make_id("https://example.com/article")
        b = Article.make_id("https://example.com/article")
        c = Article.make_id("https://example.com/other")
        assert a == b
        assert a != c
        assert len(a) == 32  # MD5 hex


class TestDateParsing:
    def test_parsed_struct(self):
        from time import struct_time
        entry = {
            "published_parsed": struct_time((2026, 6, 27, 12, 0, 0, 5, 178, 0)),
        }
        result = _parse_date(entry)
        assert result is not None
        assert "2026-06-27" in result

    def test_no_date(self):
        assert _parse_date({}) is None

    def test_fallback_string(self):
        entry = {"published": "Fri, 27 Jun 2026 12:00:00 GMT"}
        result = _parse_date(entry)
        assert result is not None
        assert "2026-06-27" in result


class TestFilterRecent:
    def setup_method(self):
        self.articles = [
            Article(
                id=Article.make_id("http://example.com/1"),
                title="Recent",
                url="http://example.com/1",
                source="test",
                published=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            ),
            Article(
                id=Article.make_id("http://example.com/2"),
                title="Old",
                url="http://example.com/2",
                source="test",
                published=(datetime.now(timezone.utc) - timedelta(hours=100)).isoformat(),
            ),
            Article(
                id=Article.make_id("http://example.com/3"),
                title="No Date",
                url="http://example.com/3",
                source="test",
            ),
        ]

    def test_filters_old(self):
        result = filter_recent(self.articles, max_age_hours=24)
        titles = {a.title for a in result}
        assert "Recent" in titles
        assert "Old" not in titles
        assert "No Date" in titles  # 无日期保留


class TestParseFeed:
    def test_minimal_atom(self):
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Test</title>
  <entry>
    <title>Hello World</title>
    <link href="https://example.com/1"/>
    <published>2026-06-27T12:00:00Z</published>
    <summary>This is a test.</summary>
  </entry>
</feed>"""
        articles = parse_feed(xml, "TestSource")
        assert len(articles) == 1
        a = articles[0]
        assert a.title == "Hello World"
        assert a.url == "https://example.com/1"
        assert a.source == "TestSource"
        assert a.content_raw == "This is a test."
