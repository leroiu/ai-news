"""
Twitter/X v2 API 数据源插件。

从 Twitter API v2 获取推文：
  - 关键词搜索 (search/recent)
  - 用户时间线 (users/:id/tweets)

用法:
  配置 config.yaml 中 type: "twitter" 的源，设置 TWITTER_BEARER_TOKEN 环境变量。

依赖:
  - httpx (已在项目依赖中)
  - TWITTER_BEARER_TOKEN 环境变量 (从 developer.twitter.com 获取)

API 文档:
  https://developer.twitter.com/en/docs/twitter-api/tweets/search/api-reference/get-tweets-search-recent
"""

import asyncio
import os
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from src.engine.fetcher import Article
from src.engine.utils import log

# ── 常量 ───────────────────────────────────────────────────────

TWITTER_API_BASE = "https://api.twitter.com/2"

# 推文字段: 获取文本、时间、指标、链接
TWEET_FIELDS = "created_at,public_metrics,entities,author_id,context_annotations"
USER_FIELDS = "name,username,description,public_metrics"

# 速率限制 (Basic 套餐)
SEARCH_RATE_LIMIT = 60    # 每 15 分钟
USER_RATE_LIMIT = 100     # 每 15 分钟，每用户
RATE_WINDOW = 15 * 60     # 15 分钟（秒）

# 速率跟踪 (模块级)
_rate_tracker: dict[str, list[float]] = {}  # {endpoint: [timestamps]}
_last_request: dict[str, float] = {}        # {endpoint: last_request_time}


def _get_bearer_token() -> str:
    """获取 Twitter Bearer Token。"""
    token = os.getenv("TWITTER_BEARER_TOKEN", "")
    if not token:
        raise ValueError("未设置 TWITTER_BEARER_TOKEN 环境变量。"
                       "请从 https://developer.twitter.com/en/portal/dashboard 获取。")
    return token


def _check_rate(endpoint: str, max_req: int) -> None:
    """检查并等待速率限制。

    如果接近限制，自动等待。不保证 100% 准确，但足够实用。
    """
    now = time.time()
    # 清除旧记录
    timestamps = _rate_tracker.setdefault(endpoint, [])
    timestamps[:] = [t for t in timestamps if now - t < RATE_WINDOW]

    if len(timestamps) >= max_req:
        oldest = timestamps[0]
        wait = RATE_WINDOW - (now - oldest) + 1.0
        if wait > 0:
            log.info(f"[Twitter] 速率限制等待 {wait:.1f}s ({endpoint})")
            time.sleep(wait)
            timestamps[:] = []

    # 延迟: 连续请求至少间隔 0.3s
    last = _last_request.get(endpoint, 0)
    if now - last < 0.3:
        time.sleep(0.3 - (now - last))

    timestamps.append(time.time())
    _last_request[endpoint] = time.time()


# ── API 客户端 ──────────────────────────────────────────────────

class TwitterClient:
    """Twitter API v2 最小化客户端。"""

    def __init__(self, bearer_token: str | None = None):
        self.token = bearer_token or _get_bearer_token()
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "AI-News-Bot/0.2",
        }

    async def _get(self, url: str, params: dict | None = None,
                   endpoint: str = "search", max_req: int = SEARCH_RATE_LIMIT,
                   timeout: int = 30) -> dict:
        """GET 请求，带速率限制和错误处理。"""
        _check_rate(endpoint, max_req)

        async with httpx.AsyncClient(headers=self.headers, timeout=timeout) as client:
            try:
                resp = await client.get(url, params=params)
                if resp.status_code == 429:
                    log.warning(f"[Twitter] 429 Too Many Requests, 等待 60s...")
                    await asyncio.sleep(60)
                    resp = await client.get(url, params=params)

                resp.raise_for_status()
                return resp.json()

            except httpx.HTTPStatusError as e:
                log.error(f"[Twitter] HTTP {e.response.status_code}: {e.response.text[:200]}")
                raise
            except httpx.TimeoutException:
                log.error(f"[Twitter] 请求超时: {url}")
                raise

    async def search_recent(self, query: str, max_results: int = 10) -> list[dict]:
        """搜索最近 7 天的推文。

        Args:
            query: 搜索查询 (支持 Twitter 搜索语法)
            max_results: 返回条数 (10-100)

        Returns:
            [{id, text, created_at, author_id, public_metrics, ...}, ...]
        """
        url = f"{TWITTER_API_BASE}/tweets/search/recent"
        params = {
            "query": query,
            "tweet.fields": TWEET_FIELDS,
            "user.fields": USER_FIELDS,
            "max_results": min(max_results, 100),
            "expansions": "author_id",
        }
        data = await self._get(url, params, endpoint="search", max_req=SEARCH_RATE_LIMIT)

        tweets = data.get("data", [])
        users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}

        # 注入用户信息
        for tweet in tweets:
            author = users.get(tweet.get("author_id", ""), {})
            tweet["_author_name"] = author.get("name", "")
            tweet["_author_username"] = author.get("username", "")
            tweet["_author_followers"] = author.get("public_metrics", {}).get("followers_count", 0)

        return tweets

    async def get_user_tweets(self, username: str, max_results: int = 10) -> list[dict]:
        """获取指定用户的最近推文。

        Args:
            username: Twitter 用户名 (不含 @)
            max_results: 返回条数 (5-100)

        Returns:
            [{id, text, created_at, public_metrics, ...}, ...]
        """
        # Step 1: 用用户名查 ID
        lookup_url = f"{TWITTER_API_BASE}/users/by/username/{username}"
        user_data = await self._get(
            lookup_url,
            params={"user.fields": USER_FIELDS},
            endpoint="user_lookup",
            max_req=300,  # user lookup 限制宽松
        )
        user = user_data.get("data", {})
        if not user:
            log.warning(f"[Twitter] 用户不存在: @{username}")
            return []

        user_id = user["id"]

        # Step 2: 获取用户推文
        tweets_url = f"{TWITTER_API_BASE}/users/{user_id}/tweets"
        params = {
            "tweet.fields": TWEET_FIELDS,
            "user.fields": USER_FIELDS,
            "max_results": min(max_results, 100),
            "exclude": "retweets,replies",  # 只拿原创
        }
        data = await self._get(tweets_url, params, endpoint="user_timeline", max_req=USER_RATE_LIMIT)

        tweets = data.get("data", [])

        # 注入用户信息
        for tweet in tweets:
            tweet["_author_name"] = user.get("name", username)
            tweet["_author_username"] = user.get("username", username)
            tweet["_author_followers"] = user.get("public_metrics", {}).get("followers_count", 0)

        return tweets


# ── Article 转换 ────────────────────────────────────────────────

def _tweet_to_article(tweet: dict, source_name: str) -> Article:
    """将推文对象转换为 Article。

    Args:
        tweet: Twitter API 返回的推文数据 (增强后含 _author_* 字段)
        source_name: 配置中源的显示名称

    Returns:
        标准 Article 对象
    """
    tweet_id = tweet["id"]
    text = tweet.get("text", "")
    author = tweet.get("_author_username", "")
    author_name = tweet.get("_author_name", "")
    followers = tweet.get("_author_followers", 0)

    # 构造标题: 截取前 100 字符
    title = text[:100].replace("\n", " ").strip()
    if len(text) > 100:
        title += "…"
    if author:
        title = f"@{author}: {title}"

    # 推文 URL
    url = f"https://twitter.com/{author}/status/{tweet_id}" if author else f"https://twitter.com/i/status/{tweet_id}"

    # 发布时间
    created_at = tweet.get("created_at")
    if created_at:
        try:
            dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%fZ")
            created_at = dt.replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            pass

    # 指标摘要
    metrics = tweet.get("public_metrics", {})
    metric_str = f"❤{metrics.get('like_count', 0)} 🔁{metrics.get('retweet_count', 0)} 💬{metrics.get('reply_count', 0)}"
    if followers:
        metric_str += f" 👥{followers}"

    # 展开 URL
    entities = tweet.get("entities", {})
    urls = entities.get("urls", [])
    url_text = ""
    if urls:
        url_text = " | ".join(u.get("expanded_url", u.get("url", "")) for u in urls[:3])

    content = f"{text}\n\n📊 {metric_str} | 👤 {author_name}(@{author})"
    if url_text:
        content += f"\n🔗 {url_text}"

    return Article(
        id=Article.make_id(f"twitter:{tweet_id}"),
        title=title,
        url=url,
        source=source_name,
        published=created_at,
        content_raw=content,
    )


# ── 主入口 ──────────────────────────────────────────────────────

async def fetch_twitter_source(source: dict) -> list[Article]:
    """从单个 Twitter 数据源配置获取文章。

    支持的配置格式：

    1. 关键词搜索:
       {name: "Twitter: AI", type: "twitter", query: "AI OR LLM", max_results: 10}

    2. 用户时间线:
       {name: "Twitter: Labs", type: "twitter", users: ["OpenAI", "AnthropicAI"], max_results: 5}

    Args:
        source: config.yaml 中的源配置字典

    Returns:
        Article 列表
    """
    token = os.getenv("TWITTER_BEARER_TOKEN", "")
    if not token:
        log.warning(f"[{source['name']}] 未设置 TWITTER_BEARER_TOKEN，跳过")
        return []

    client = TwitterClient(token)
    max_results = source.get("max_results", 10)
    name = source["name"]
    articles: list[Article] = []

    try:
        # 模式 1: 关键词搜索
        query = source.get("query", "")
        if query:
            log.info(f"[{name}] 搜索: {query[:60]}...")
            tweets = await client.search_recent(query, max_results=max_results)
            for t in tweets:
                articles.append(_tweet_to_article(t, name))
            log.info(f"[{name}] ✓ {len(tweets)} 条推文")
            return articles

        # 模式 2: 用户时间线
        users = source.get("users", [])
        if users:
            for username in users:
                try:
                    tweets = await client.get_user_tweets(username, max_results=max_results)
                    for t in tweets:
                        articles.append(_tweet_to_article(t, name))
                    log.info(f"[{name}] @{username} ✓ {len(tweets)} 条推文")
                except Exception as e:
                    log.warning(f"[{name}] @{username} 获取失败: {e}")
                # 用户间稍作延迟
                await asyncio.sleep(0.5)
            return articles

        log.warning(f"[{name}] 未配置 query 或 users，跳过")
        return []

    except Exception as e:
        log.error(f"[{name}] Twitter API 错误: {e}")
        return articles  # 返回已获取的部分


# ── CLI 测试入口 ───────────────────────────────────────────────

async def _test():
    """快速测试: python -m src.plugins.twitter"""
    from src.engine.utils import setup_logging
    setup_logging("INFO")

    token = os.getenv("TWITTER_BEARER_TOKEN", "")
    if not token:
        print("❌ 请设置 TWITTER_BEARER_TOKEN 环境变量")
        print("   获取地址: https://developer.twitter.com/en/portal/dashboard")
        return

    # 测试搜索
    print("=" * 50)
    print("测试 1: AI 关键词搜索")
    print("=" * 50)
    source = {
        "name": "Twitter: AI Search (test)",
        "query": "Claude AI OR GPT-5 -is:retweet lang:en",
        "max_results": 5,
    }
    articles = await fetch_twitter_source(source)
    for i, a in enumerate(articles[:5], 1):
        print(f"\n[{i}] {a.title}")
        print(f"    URL: {a.url}")
        print(f"    内容: {a.content_raw[:150]}...")

    # 测试用户时间线
    print(f"\n{'=' * 50}")
    print("测试 2: 用户时间线")
    print("=" * 50)
    source2 = {
        "name": "Twitter: AI Labs (test)",
        "users": ["OpenAI"],
        "max_results": 3,
    }
    articles2 = await fetch_twitter_source(source2)
    for i, a in enumerate(articles2[:3], 1):
        print(f"\n[{i}] {a.title}")
        print(f"    URL: {a.url}")

    print(f"\n总计: {len(articles) + len(articles2)} 条推文")


if __name__ == "__main__":
    asyncio.run(_test())
