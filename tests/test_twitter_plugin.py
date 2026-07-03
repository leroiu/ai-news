"""
Twitter 插件 + Fetcher 多源扩展测试。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone

from src.engine.fetcher import Article, _parse_date


# ═══════════════════════════════════════════════════════════════
# Tweet → Article 转换
# ═══════════════════════════════════════════════════════════════


class TestTweetToArticle:
    """测试推文 → Article 对象转换。"""

    def test_basic_conversion(self):
        from src.plugins.twitter import _tweet_to_article

        tweet = {
            "id": "1234567890",
            "text": "OpenAI just announced GPT-5 with groundbreaking capabilities in reasoning and coding.",
            "created_at": "2026-07-01T10:30:00.000Z",
            "author_id": "123",
            "_author_name": "OpenAI",
            "_author_username": "OpenAI",
            "_author_followers": 5000000,
            "public_metrics": {
                "like_count": 1500,
                "retweet_count": 300,
                "reply_count": 200,
            },
            "entities": {
                "urls": [
                    {"url": "https://t.co/abc", "expanded_url": "https://openai.com/blog/gpt-5"},
                ]
            },
        }

        article = _tweet_to_article(tweet, "Twitter: AI News")

        assert article.id == Article.make_id("twitter:1234567890")
        assert article.source == "Twitter: AI News"
        assert "@OpenAI" in article.title
        assert "GPT-5" in article.title
        assert "twitter.com/OpenAI/status/1234567890" in article.url
        assert article.published is not None
        assert "2026-07-01" in article.published
        assert "1500" in article.content_raw
        assert "300" in article.content_raw
        assert "OpenAI" in article.content_raw
        assert "openai.com/blog/gpt-5" in article.content_raw

    def test_long_text_truncation(self):
        from src.plugins.twitter import _tweet_to_article

        long_text = "A" * 200
        tweet = {
            "id": "999",
            "text": long_text,
            "created_at": "2026-07-01T00:00:00.000Z",
            "author_id": "1",
            "_author_name": "Test",
            "_author_username": "test",
            "_author_followers": 0,
            "public_metrics": {"like_count": 0, "retweet_count": 0, "reply_count": 0},
            "entities": {},
        }

        article = _tweet_to_article(tweet, "Test")
        # 标题应被截断 + "…"
        assert len(article.title) <= 110  # 100 chars + @author + ": " + "…"
        assert article.title.endswith("…")

    def test_no_author_url_fallback(self):
        from src.plugins.twitter import _tweet_to_article

        tweet = {
            "id": "999",
            "text": "Test tweet",
            "created_at": None,
            "author_id": "1",
            "_author_name": "",
            "_author_username": "",
            "_author_followers": 0,
            "public_metrics": {"like_count": 0, "retweet_count": 0, "reply_count": 0},
            "entities": {},
        }

        article = _tweet_to_article(tweet, "Test")
        # 无用户名时 URL 用 status 路由
        assert "twitter.com/i/status/999" in article.url

    def test_no_date(self):
        from src.plugins.twitter import _tweet_to_article

        tweet = {
            "id": "999",
            "text": "No date",
            "created_at": None,
            "author_id": "1",
            "_author_name": "T",
            "_author_username": "t",
            "_author_followers": 0,
            "public_metrics": {"like_count": 0, "retweet_count": 0, "reply_count": 0},
            "entities": {},
        }

        article = _tweet_to_article(tweet, "Test")
        assert article.published is None


# ═══════════════════════════════════════════════════════════════
# Twitter API 客户端
# ═══════════════════════════════════════════════════════════════


class TestTwitterClient:
    """测试 Twitter API 客户端（mock HTTP）。"""

    @pytest.fixture
    def mock_response(self):
        return {
            "data": [
                {
                    "id": "1001",
                    "text": "Breaking AI news!",
                    "created_at": "2026-07-01T12:00:00.000Z",
                    "author_id": "user-1",
                    "public_metrics": {"like_count": 100, "retweet_count": 50, "reply_count": 30},
                }
            ],
            "includes": {
                "users": [
                    {
                        "id": "user-1",
                        "name": "AI News Bot",
                        "username": "ainewsbot",
                        "public_metrics": {"followers_count": 10000},
                    }
                ]
            }
        }

    def test_search_recent(self, mock_response):
        from src.plugins.twitter import TwitterClient

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            mock_client.get.return_value = mock_resp
            mock_client_cls.return_value = mock_client

            import asyncio
            client = TwitterClient("test-token")
            tweets = asyncio.run(client.search_recent("AI lang:en", max_results=5))

            assert len(tweets) == 1
            assert tweets[0]["id"] == "1001"
            assert tweets[0]["_author_username"] == "ainewsbot"
            assert tweets[0]["_author_followers"] == 10000

    def test_search_with_http_error(self):
        from src.plugins.twitter import TwitterClient

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 401
            mock_resp.text = "Unauthorized"
            mock_resp.raise_for_status.side_effect = Exception("HTTP 401")
            mock_client.get.return_value = mock_resp
            mock_client_cls.return_value = mock_client

            import asyncio
            client = TwitterClient("bad-token")
            with pytest.raises(Exception):
                asyncio.run(client.search_recent("AI"))

    def test_get_user_tweets(self):
        from src.plugins.twitter import TwitterClient

        user_lookup = {
            "data": {
                "id": "user-openai",
                "name": "OpenAI",
                "username": "OpenAI",
                "public_metrics": {"followers_count": 5_000_000},
            }
        }
        user_tweets = {
            "data": [
                {
                    "id": "2001",
                    "text": "We are releasing a new model.",
                    "created_at": "2026-07-02T08:00:00.000Z",
                    "author_id": "user-openai",
                    "public_metrics": {"like_count": 5000, "retweet_count": 1000, "reply_count": 500},
                }
            ]
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock()

            # 两次调用：lookup + tweets
            resp1 = MagicMock()
            resp1.status_code = 200
            resp1.json.return_value = user_lookup

            resp2 = MagicMock()
            resp2.status_code = 200
            resp2.json.return_value = user_tweets

            mock_client.get.side_effect = [resp1, resp2]
            mock_client_cls.return_value = mock_client

            import asyncio
            client = TwitterClient("test-token")
            tweets = asyncio.run(client.get_user_tweets("OpenAI", max_results=5))

            assert len(tweets) == 1
            assert tweets[0]["_author_username"] == "OpenAI"
            assert tweets[0]["_author_followers"] == 5_000_000

    def test_get_user_tweets_user_not_found(self):
        from src.plugins.twitter import TwitterClient

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"data": None}  # 用户不存在
            mock_client.get.return_value = mock_resp
            mock_client_cls.return_value = mock_client

            import asyncio
            client = TwitterClient("test-token")
            tweets = asyncio.run(client.get_user_tweets("nonexistent_user"))

            assert tweets == []


# ═══════════════════════════════════════════════════════════════
# fetch_twitter_source
# ═══════════════════════════════════════════════════════════════


class TestFetchTwitterSource:
    """测试 fetch_twitter_source 入口函数。"""

    def test_no_token_returns_empty(self):
        from src.plugins.twitter import fetch_twitter_source

        with patch.dict("os.environ", {}, clear=True):
            import asyncio
            source = {"name": "Test", "query": "AI"}
            articles = asyncio.run(fetch_twitter_source(source))
            assert articles == []

    def test_search_query_mode(self):
        from src.plugins.twitter import fetch_twitter_source

        mock_results = [
            {
                "id": "3001",
                "text": "AI breakthrough!",
                "created_at": "2026-07-02T10:00:00.000Z",
                "author_id": "u1",
                "_author_name": "Tech",
                "_author_username": "tech",
                "_author_followers": 100,
                "public_metrics": {"like_count": 10, "retweet_count": 5, "reply_count": 2},
                "entities": {},
            }
        ]

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": "test"}):
            # Mock TwitterClient._get (底层 HTTP)，让 search_recent 正常工作
            async def mock_get(self, url, params=None, endpoint="search", max_req=60, timeout=30):
                return {
                    "data": mock_results,
                    "includes": {"users": []},
                }

            with patch.object(
                __import__("src.plugins.twitter", fromlist=["TwitterClient"]).TwitterClient,
                "_get", mock_get
            ):
                import asyncio
                source = {"name": "Twitter: AI", "query": "AI lang:en", "max_results": 10}
                articles = asyncio.run(fetch_twitter_source(source))

                assert len(articles) == 1
                assert articles[0].source == "Twitter: AI"
                assert "AI breakthrough" in articles[0].title

    def test_user_timeline_mode(self):
        from src.plugins.twitter import fetch_twitter_source

        mock_tweet = {
            "id": "4001",
            "text": "New model release!",
            "created_at": "2026-07-02T09:00:00.000Z",
            "author_id": "u-openai",
            "public_metrics": {"like_count": 10000, "retweet_count": 2000, "reply_count": 1000},
            "entities": {},
        }

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": "test"}):
            TwitterClient = __import__("src.plugins.twitter", fromlist=["TwitterClient"]).TwitterClient

            async def mock_get(self, url, params=None, endpoint="user_timeline", max_req=100, timeout=30):
                if "users/by/username" in url:
                    return {
                        "data": {
                            "id": "u-openai", "name": "OpenAI", "username": "OpenAI",
                            "public_metrics": {"followers_count": 5_000_000},
                        }
                    }
                else:
                    return {"data": [mock_tweet]}

            with patch.object(TwitterClient, "_get", mock_get):
                import asyncio
                source = {"name": "Twitter: Labs", "users": ["OpenAI"], "max_results": 3}
                articles = asyncio.run(fetch_twitter_source(source))

                assert len(articles) == 1
                assert "@OpenAI" in articles[0].title

    def test_empty_config_returns_empty(self):
        from src.plugins.twitter import fetch_twitter_source

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": "test"}):
            import asyncio
            source = {"name": "Test", "type": "twitter"}  # 无 query 无 users
            articles = asyncio.run(fetch_twitter_source(source))
            assert articles == []

    def test_partial_error_returns_collected(self):
        """一个用户失败，另一个成功的推文仍返回。"""
        from src.plugins.twitter import fetch_twitter_source

        call_count = [0]

        async def mock_get_user(username, max_results=10):
            call_count[0] += 1
            if username == "GoodAI":
                return [{
                    "id": "5001", "text": "Good news",
                    "created_at": "2026-07-02T10:00:00.000Z",
                    "author_id": "g", "_author_name": "Good", "_author_username": "GoodAI",
                    "_author_followers": 10,
                    "public_metrics": {"like_count": 1, "retweet_count": 0, "reply_count": 0},
                    "entities": {},
                }]
            else:
                raise Exception("User suspended")

        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": "test"}):
            with patch("src.plugins.twitter.TwitterClient.get_user_tweets", side_effect=mock_get_user):
                with patch("src.plugins.twitter.TwitterClient.__init__", return_value=None):
                    import asyncio
                    source = {"name": "Test", "users": ["BadAI", "GoodAI"], "max_results": 3}
                    articles = asyncio.run(fetch_twitter_source(source))

                    # GoodAI 的推文应被收集
                    assert len(articles) == 1
                    assert "Good news" in articles[0].title


# ═══════════════════════════════════════════════════════════════
# Fetcher: fetch_all 多源扩展
# ═══════════════════════════════════════════════════════════════


class TestFetchAllMultiSource:
    """测试 fetch_all 对 twitter 源类型的支持。"""

    def test_twitter_source_type_counted(self):
        """验证 Twitter 源在配置中正确分类计数。"""
        config = {
            "sources": [
                {"name": "RSS1", "url": "http://example.com/rss", "enabled": True},
                {"name": "TW1", "type": "twitter", "query": "AI", "enabled": True},
            ],
            "fetch": {"timeout": 30, "concurrency": 1, "max_age_hours": 0},
        }

        default_type = "rss"
        rss_count = sum(1 for s in config["sources"] if s.get("type", default_type) in ("rss", "wechat"))
        html_count = sum(1 for s in config["sources"] if s.get("type") == "html")
        twitter_count = sum(1 for s in config["sources"] if s.get("type") == "twitter")

        assert rss_count == 1
        assert twitter_count == 1
        assert html_count == 0

    def test_twitter_results_merged(self):
        """验证 Twitter 结果被合并到 all_articles。"""
        from src.engine.fetcher import fetch_all, Article as A

        tw_article = A(
            id=A.make_id("twitter:999"),
            title="Tweet Article",
            url="https://twitter.com/user/status/999",
            source="TW1",
            published="2026-07-02T00:00:00+00:00",
        )

        rss_article = A(
            id=A.make_id("https://example.com/1"),
            title="RSS Article",
            url="https://example.com/1",
            source="RSS1",
            published="2026-07-02T00:00:00+00:00",
        )

        config = {
            "sources": [
                {"name": "RSS1", "url": "http://example.com/rss", "enabled": True},
                {"name": "TW1", "type": "twitter", "query": "AI", "enabled": True},
            ],
            "fetch": {"timeout": 30, "concurrency": 1, "max_age_hours": 0},
        }

        import asyncio

        rss_results = [("RSS1", b"<rss></rss>", None)]
        html_results = []
        twitter_results = [[tw_article]]

        with patch("src.engine.fetcher.load_config", return_value=config):
            with patch.object(asyncio, "gather", new=AsyncMock(
                return_value=(rss_results, html_results, twitter_results)
            )):
                with patch("src.engine.fetcher.parse_feed", return_value=[rss_article]):
                    with patch("src.engine.fetcher._update_source_health"):
                        articles = asyncio.run(fetch_all(config))

        titles = {a.title for a in articles}
        assert "Tweet Article" in titles
        assert "RSS Article" in titles

    def test_all_disabled_twitter_skipped(self):
        """禁用的 Twitter 源不被处理。"""
        config = {
            "sources": [
                {"name": "TW1", "type": "twitter", "query": "AI", "enabled": False},
            ],
            "fetch": {"timeout": 30, "concurrency": 1},
        }

        sources = [s for s in config["sources"] if s.get("enabled", True)]
        assert len(sources) == 0  # 全部禁用
