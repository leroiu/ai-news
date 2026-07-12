"""
AI News - RSS 内容抓取器

从配置的 RSS 源并发抓取文章，解析为标准 Article 结构。
"""

import asyncio
import hashlib
import json
import re
import sys
import time as _time
from calendar import timegm
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from typing import Optional

import feedparser
import httpx
from bs4 import BeautifulSoup

from .source_validation import validate_source
from .utils import log, load_config, ROOT_DIR

FETCH_RETRY_MAX = 3
FETCH_RETRY_BASE_DELAY = 1.0  # 秒


# ============================================================
# 数据模型
# ============================================================

@dataclass
class Article:
    """标准化文章结构。每个处理阶段逐步丰富字段。"""

    # --- Fetcher 产出 ---
    id: str                          # md5(url)
    title: str                       # 原始标题
    url: str                         # 文章链接
    source: str                      # 来源名称（RSS 源 name）
    published: Optional[str] = None  # 发布时间 ISO 格式
    content_raw: str = ""            # 原始摘要或正文

    # --- Deduplicator 产出 ---
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None

    # --- Classifier 产出 ---
    categories: list[str] = field(default_factory=list)
    classification_meta: dict = field(default_factory=dict)  # method, confidence 等

    # --- Summarizer 产出 ---
    title_cn: str = ""
    one_liner: str = ""
    summary_points: list[str] = field(default_factory=list)

    # --- Scorer 产出 ---
    score: int = 0
    score_reason: str = ""
    score_breakdown: dict = field(default_factory=dict)  # 规则评分明细
    cluster_id: str = ""              # 事件聚类 ID（同事件多源合并）

    @staticmethod
    def make_id(url: str) -> str:
        return hashlib.md5(url.strip().encode()).hexdigest()

    def to_dict(self) -> dict:
        """序列化为字典，用于 JSONL 存储。只存管道字段，跳过 dedup 标记。"""
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "published": self.published,
            "content_raw": self.content_raw,
            "categories": self.categories,
            "title_cn": self.title_cn,
            "one_liner": self.one_liner,
            "summary_points": self.summary_points,
            "score": self.score,
            "score_reason": self.score_reason,
            "cluster_id": self.cluster_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Article":
        """从字典反序列化 Article。忽略未知字段。"""
        return cls(
            id=d.get("id", ""),
            title=d.get("title", ""),
            url=d.get("url", ""),
            source=d.get("source", ""),
            published=d.get("published"),
            content_raw=d.get("content_raw", ""),
            categories=d.get("categories", []),
            title_cn=d.get("title_cn", ""),
            one_liner=d.get("one_liner", ""),
            summary_points=d.get("summary_points", []),
            score=d.get("score", 0),
            score_reason=d.get("score_reason", ""),
            cluster_id=d.get("cluster_id", ""),
        )


# ============================================================
# RSS 解析
# ============================================================

def _extract_content(entry: dict) -> str:
    """从 feedparser entry 中提取最佳文本内容。"""
    # 优先级: content > summary > description > title
    if entry.get("content"):
        return entry["content"][0].get("value", "")
    if entry.get("summary"):
        return entry["summary"]
    if entry.get("description"):
        return entry["description"]
    return entry.get("title", "")


def _parse_date(entry: dict) -> Optional[str]:
    """解析发布时间，统一为 UTC ISO 格式字符串。"""
    # 优先用 parsed 结构体（feedparser 已解析为 UTC struct_time）
    for field in ("published_parsed", "updated_parsed"):
        tp = entry.get(field)
        if tp and len(tp) >= 6:
            try:
                ts = timegm(tp + (0,) * (9 - len(tp)))
                return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            except Exception:
                pass

    # fallback: 解析 RFC 2822 字符串
    for field in ("published", "updated"):
        raw = entry.get(field, "")
        if raw:
            try:
                from email.utils import parsedate_to_datetime
                return parsedate_to_datetime(raw).isoformat()
            except Exception:
                pass

    return None


def parse_feed(raw: bytes, source_name: str) -> list[Article]:
    """解析单个 RSS 源的原始字节，返回 Article 列表。"""
    feed = feedparser.parse(raw)
    articles: list[Article] = []

    if feed.bozo:
        log.warning(f"[{source_name}] RSS 解析警告: {feed.bozo_exception}")

    for entry in feed.entries:
        url = entry.get("link", "")
        if not url:
            continue

        article = Article(
            id=Article.make_id(url),
            title=entry.get("title", "(无标题)"),
            url=url,
            source=source_name,
            published=_parse_date(entry),
            content_raw=_extract_content(entry),
        )
        articles.append(article)

    return articles


# ============================================================
# HTTP 抓取
# ============================================================

async def _fetch_one(
    client: httpx.AsyncClient,
    name: str,
    url: str,
    timeout: int = 30,
) -> tuple[str, Optional[bytes], Optional[str]]:
    """抓取单个 RSS 源（含重试）。返回 (name, content_bytes, error_msg)。"""
    last_error = None
    for attempt in range(1, FETCH_RETRY_MAX + 1):
        try:
            resp = await client.get(url, timeout=timeout, follow_redirects=True)
            resp.raise_for_status()
            return (name, resp.content, None)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e:
            last_error = e
            if attempt < FETCH_RETRY_MAX:
                delay = FETCH_RETRY_BASE_DELAY * (2 ** (attempt - 1))
                log.debug(f"[{name}] 重试 {attempt}/{FETCH_RETRY_MAX}: {e}, {delay:.1f}s")
                await asyncio.sleep(delay)
            else:
                return (name, None, f"超时/连接失败 (重试{FETCH_RETRY_MAX}次)")
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500 and attempt < FETCH_RETRY_MAX:
                delay = FETCH_RETRY_BASE_DELAY * (2 ** (attempt - 1))
                log.debug(f"[{name}] 服务端错误 {e.response.status_code}, 重试 {attempt}/{FETCH_RETRY_MAX}")
                await asyncio.sleep(delay)
            else:
                return (name, None, f"HTTP {e.response.status_code}")
        except Exception as e:
            return (name, None, str(e))
    return (name, None, str(last_error))


def parse_github_trending(html_bytes: bytes, source_name: str) -> list[Article]:
    """解析 GitHub Trending HTML 页面，生成 Article 列表。"""
    soup = BeautifulSoup(html_bytes, "html.parser")
    articles: list[Article] = []

    # GitHub Trending repos are in <article class="Box-row"> elements
    repos = soup.find_all("article", class_="Box-row")
    if not repos:
        log.warning(f"[{source_name}] 未找到任何仓库条目，HTML 结构可能已变化")
        return articles

    for repo in repos:
        # 仓库名: h2 > a
        h2 = repo.find("h2", class_="h3")
        if not h2 or not h2.find("a"):
            continue
        name_link = h2.find("a")
        full_name = name_link.get("href", "").strip().lstrip("/")
        repo_name = name_link.get_text(strip=True)
        repo_url = f"https://github.com/{full_name}"

        # 描述: p
        desc_p = repo.find("p", class_="col-9")
        description = desc_p.get_text(strip=True) if desc_p else ""

        # 语言 + 今日星数: 在 span 中
        lang_span = repo.find("span", itemprop="programmingLanguage")
        language = lang_span.get_text(strip=True) if lang_span else ""

        # 今日星数: span.d-inline-block.float-sm-right
        stars_today = ""
        stars_span = repo.find("span", class_="float-sm-right")
        if stars_span:
            stars_today = stars_span.get_text(strip=True)

        title = f"{full_name}: {description}" if description else full_name
        if stars_today:
            title = f"[{stars_today}] {title}"

        article = Article(
            id=Article.make_id(repo_url),
            title=title,
            url=repo_url,
            source=source_name,
            published=datetime.now(timezone.utc).isoformat(),
            content_raw=f"GitHub Trending: {full_name} | Language: {language} | {stars_today} | {description}",
        )
        articles.append(article)

    log.info(f"[{source_name}] HTML 解析: {len(articles)} 个仓库")
    return articles


async def fetch_all(config: dict | None = None) -> list[Article]:
    """并发抓取所有启用的 RSS/HTML/Twitter 源，返回 Article 列表。"""
    if config is None:
        config = load_config()

    configured_sources = [s for s in config.get("sources", []) if s.get("enabled", True)]
    if not configured_sources:
        log.warning("没有启用的 RSS 源")
        return []

    sources: list[dict] = []
    results_summary: dict[str, tuple[bool, Optional[str]]] = {}
    for source in configured_sources:
        validation_error = validate_source(source)
        if validation_error:
            name = str(source.get("name", "未命名来源"))
            error = f"配置无效: {validation_error}"
            log.error(f"[{name}] {error}")
            results_summary[name] = (False, error)
            continue
        sources.append(source)

    if not sources:
        log.warning("没有可用的 RSS 源")
        _update_source_health(results_summary)
        return []

    fetch_cfg = config.get("fetch", {})
    timeout = fetch_cfg.get("timeout", 30)
    concurrency = fetch_cfg.get("concurrency", 5)

    # 分类统计
    default_type = "rss"
    rss_count = sum(1 for s in sources if s.get("type", default_type) in ("rss", "wechat"))
    html_count = sum(1 for s in sources if s.get("type") == "html")
    twitter_count = sum(1 for s in sources if s.get("type") == "twitter")

    parts = [f"RSS×{rss_count}"]
    if html_count: parts.append(f"HTML×{html_count}")
    if twitter_count: parts.append(f"Twitter×{twitter_count}")
    log.info(f"开始抓取 {len(sources)} 个源 ({', '.join(parts)}, 超时={timeout}s, 并发={concurrency})")

    all_articles: list[Article] = []
    # 建立 source name → config 的映射，方便后续判断类型
    source_map: dict[str, dict] = {s["name"]: s for s in sources}

    # HTML 源使用不同的 Accept header
    rss_headers = {
        "User-Agent": "AI-News-Bot/0.1 (personal use; contact@example.com)",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
    }
    html_headers = {
        "User-Agent": "AI-News-Bot/0.1 (personal use; contact@example.com)",
        "Accept": "text/html, application/xhtml+xml",
    }

    # 分别抓取 RSS 和 HTML 源（不同 headers）
    async def fetch_rss_sources():
        rss_sources = [s for s in sources if s.get("type", default_type) in ("rss", "wechat")]
        if not rss_sources:
            return []
        async with httpx.AsyncClient(headers=rss_headers, limits=httpx.Limits(max_connections=concurrency)) as client:
            tasks = [_fetch_one(client, s["name"], s["url"], timeout) for s in rss_sources]
            return await asyncio.gather(*tasks)

    async def fetch_html_sources():
        html_sources = [s for s in sources if s.get("type") == "html"]
        if not html_sources:
            return []
        async with httpx.AsyncClient(headers=html_headers, limits=httpx.Limits(max_connections=concurrency)) as client:
            tasks = [_fetch_one(client, s["name"], s["url"], timeout) for s in html_sources]
            return await asyncio.gather(*tasks)

    async def fetch_twitter_sources():
        """Twitter API 源 — 使用 Bearer Token 认证，独立于 HTTP 抓取。"""
        twitter_sources = [s for s in sources if s.get("type") == "twitter"]
        if not twitter_sources:
            return []
        from src.plugins.twitter import fetch_twitter_source
        tasks = [fetch_twitter_source(s) for s in twitter_sources]
        return await asyncio.gather(*tasks)

    rss_results, html_results, twitter_results = await asyncio.gather(
        fetch_rss_sources(), fetch_html_sources(), fetch_twitter_sources()
    )
    results = rss_results + html_results

    # Twitter 结果单独处理（已经是 Articles，不需要 HTTP 解析）
    twitter_sources_list = [s for s in sources if s.get("type") == "twitter"]
    for i, tw_articles in enumerate(twitter_results):
        name = twitter_sources_list[i]["name"]
        try:
            count = len(tw_articles) if tw_articles else 0
            if count > 0:
                all_articles.extend(tw_articles)
                results_summary[name] = (True, None)
                log.info(f"[{name}] ✓ {count} 条推文")
            else:
                results_summary[name] = (True, None)  # 空结果不算失败
                log.info(f"[{name}] ✓ 0 条新推文")
        except Exception as e:
            results_summary[name] = (False, str(e))
            log.warning(f"[{name}] Twitter 错误: {e}")

    success_count = 0
    fail_count = 0
    for name, content, error in results:
        src_cfg = source_map.get(name, {})
        source_type = src_cfg.get("type", "rss")

        if error or not content:
            log.warning(f"[{name}] 抓取失败: {error or '空内容'}")
            fail_count += 1
            results_summary[name] = (False, error or "空内容")
            continue

        # 根据类型选择解析器
        if source_type == "html":
            articles = parse_github_trending(content, name)
        else:
            articles = parse_feed(content, name)

        all_articles.extend(articles)
        log.info(f"[{name}] ✓ {len(articles)} 篇")
        success_count += 1
        results_summary[name] = (True, None)

    log.info(
        f"抓取完成: {success_count}/{len(sources)} 源成功, "
        f"共 {len(all_articles)} 篇文章, "
        f"{fail_count} 源失败"
    )

    # 更新源健康状态
    _update_source_health(results_summary)

    # 日期过滤：只保留近 N 小时的文章
    max_age_hours = fetch_cfg.get("max_age_hours", 0)
    if max_age_hours > 0:
        all_articles = filter_recent(all_articles, max_age_hours)

    return all_articles


# ============================================================
# 源健康监控
# ============================================================

HEALTH_FILE = ROOT_DIR / "data" / "source_health.json"
DEAD_THRESHOLD = 3  # 连续失败次数阈值


def _load_health() -> dict:
    try:
        if HEALTH_FILE.exists():
            with open(HEALTH_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _save_health(data: dict):
    HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HEALTH_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def _update_source_health(results: dict[str, tuple[bool, Optional[str]]]):
    """根据本次抓取结果更新源健康状态。连续失败 >=3 次 → 警告。"""
    health = _load_health()
    now = datetime.now(timezone.utc).isoformat()

    for name, (ok, error) in results.items():
        if name not in health:
            health[name] = {"consecutive_failures": 0, "status": "healthy",
                           "last_success": None, "last_failure": None, "last_error": None}

        entry = health[name]
        if ok:
            entry["consecutive_failures"] = 0
            entry["status"] = "healthy"
            entry["last_success"] = now
        else:
            entry["consecutive_failures"] = entry.get("consecutive_failures", 0) + 1
            entry["last_failure"] = now
            entry["last_error"] = error or "未知"

            fails = entry["consecutive_failures"]
            if fails >= DEAD_THRESHOLD:
                if entry["status"] != "dead":
                    log.warning(f"⚠ [{name}] 连续失败 {fails} 次，标记为 dead")
                entry["status"] = "dead"
            elif fails >= 2:
                entry["status"] = "degraded"

    _save_health(health)

    # 汇报死源
    dead = [(n, h["consecutive_failures"]) for n, h in health.items()
            if h.get("status") == "dead"]
    if dead:
        names = ", ".join(f"[{n}] x{c}" for n, c in dead)
        log.warning(f"死源 ({len(dead)}): {names} — 请检查 config.yaml")


def filter_recent(articles: list[Article], max_age_hours: int) -> list[Article]:
    """只保留最近 max_age_hours 小时内发布的文章。无日期的保留（保守策略）。"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    before = len(articles)
    filtered: list[Article] = []
    for a in articles:
        if a.published is None:
            filtered.append(a)
            continue
        try:
            dt = datetime.fromisoformat(a.published)
            if dt >= cutoff:
                filtered.append(a)
        except (ValueError, TypeError):
            filtered.append(a)
    after = len(filtered)
    if before > after:
        log.info(f"日期过滤: {before} → {after} 篇 (最近 {max_age_hours}h)")
    return filtered


# ============================================================
# CLI 入口（调试用）
# ============================================================

def main():
    """CLI: 测试抓取功能。"""
    from .utils import setup_logging
    setup_logging("INFO")

    articles = asyncio.run(fetch_all())

    # 打印前 10 条
    for i, a in enumerate(articles[:10], 1):
        print(f"\n--- [{i}] {a.source} ---")
        print(f"Title: {a.title}")
        print(f"URL:   {a.url}")
        print(f"Date:  {a.published}")
        content_preview = a.content_raw[:200].replace("\n", " ")
        print(f"Body:  {content_preview}...")

    print(f"\n总计: {len(articles)} 篇文章")
    return 0


if __name__ == "__main__":
    sys.exit(main())
