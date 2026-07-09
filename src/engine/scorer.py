"""
AI News - 规则评分器

使用来源权威性、关键词匹配、时效性、高权威加成四维规则评分。
不调用 LLM，评分可复现、可调试。
"""

import re
from datetime import datetime, timezone
from typing import Optional

from .fetcher import Article
from .utils import log, load_config


def _load_scoring_config() -> dict:
    """加载评分配置。"""
    config = load_config()
    scoring = config.get("scoring", {})
    # 确保所有子项存在
    scoring.setdefault("weights", {
        "source_authority": 0.30,
        "keyword_match": 0.30,
        "recency": 0.20,
        "high_authority_bonus": 0.20,
    })
    scoring.setdefault("source_scores", {})
    scoring.setdefault("source_default", 30)
    scoring.setdefault("keyword_boost", [])
    scoring.setdefault("keyword_penalty", [])
    scoring.setdefault("recency", {"peak_hours": 24, "decay_hours": 72, "min_score": 10})
    scoring.setdefault("high_authority_sources", [])
    scoring.setdefault("thresholds", {"star_5": 85, "star_4": 70, "star_3": 50, "star_2": 30, "star_1": 0})
    return scoring


def _build_interest_pattern(config: dict) -> str:
    """从 config.interests 构建用户兴趣关键词模式。"""
    interests = config.get("interests", {})
    items = []
    for level in ("high", "medium", "low"):
        items.extend(interests.get(level, []))
    if not items:
        return r"(?!)"  # 永不匹配
    # 转义特殊字符，支持空格
    escaped = [re.escape(i) for i in items if i]
    return "|".join(escaped)


def _source_score(source: str, cfg: dict) -> int:
    """来源权威分 (0-100)。"""
    scores = cfg.get("source_scores", {})
    return scores.get(source, cfg.get("source_default", 30))


def _keyword_score(article: Article, cfg: dict, config: dict) -> int:
    """关键词匹配分 (0-100)。"""
    total = 0
    text = f"{article.title} {article.content_raw}".lower()
    hits = []

    boosts = cfg.get("keyword_boost", [])
    if isinstance(boosts, dict):
        boosts = [boosts]
    elif isinstance(boosts, list):
        pass

    for boost in boosts:
        patterns = boost.get("patterns") or boost.get("pattern") or []
        score_val = boost.get("score", 10)
        if isinstance(patterns, str):
            patterns = [patterns]

        for pattern in patterns:
            # 替换 {interests_high} 占位符
            if "{interests_high}" in pattern or "{interests}" in pattern:
                pattern = _build_interest_pattern(config)
            try:
                if re.search(pattern, text, re.IGNORECASE):
                    total += score_val
                    hits.append(str(score_val))
            except re.error:
                continue

    # 扣分
    penalties = cfg.get("keyword_penalty", [])
    if isinstance(penalties, dict):
        penalties = [penalties]
    for penalty in penalties:
        patterns = penalty.get("patterns") or penalty.get("pattern") or []
        score_val = penalty.get("score", -15)
        if isinstance(patterns, str):
            patterns = [patterns]
        for pattern in patterns:
            try:
                if re.search(pattern, text, re.IGNORECASE):
                    total += score_val
            except re.error:
                continue

    return max(0, min(100, total))


def _recency_score(article: Article, cfg: dict) -> int:
    """时效性分 (0-100)。"""
    if not article.published:
        return cfg.get("recency", {}).get("min_score", 10)

    try:
        if isinstance(article.published, str):
            published = datetime.fromisoformat(article.published)
        else:
            published = article.published
    except (ValueError, TypeError):
        return cfg.get("recency", {}).get("min_score", 10)

    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    age_hours = max(0, (now - published).total_seconds() / 3600)

    recency_cfg = cfg.get("recency", {})
    peak_hours = recency_cfg.get("peak_hours", 24)
    decay_hours = recency_cfg.get("decay_hours", 72)
    min_score = recency_cfg.get("min_score", 10)

    if age_hours <= peak_hours:
        return 100
    elif age_hours >= decay_hours:
        return min_score
    else:
        # 线性衰减
        ratio = (age_hours - peak_hours) / (decay_hours - peak_hours)
        return max(min_score, int(100 - (100 - min_score) * ratio))


def _authority_bonus(article: Article, cfg: dict) -> int:
    """高权威来源加成 (0 或 100)。"""
    high = cfg.get("high_authority_sources", [])
    return 100 if article.source in high else 0


def _final_to_stars(final_score: int, cfg: dict) -> int:
    """百分制 → 1-5★。"""
    thresholds = cfg.get("thresholds", {})
    if final_score >= thresholds.get("star_5", 85):
        return 5
    elif final_score >= thresholds.get("star_4", 70):
        return 4
    elif final_score >= thresholds.get("star_3", 50):
        return 3
    elif final_score >= thresholds.get("star_2", 30):
        return 2
    else:
        return 1


def _build_reason(
    src_raw: int, kw_raw: int, rec_raw: int, auth_raw: int,
    final: float, stars: int, hits: list[str]
) -> str:
    """构造简短评分理由。"""
    kw_part = f"关键词:{kw_raw}" if not hits else f"关键词:{kw_raw}({' '.join(hits)})"
    detail = f"来源:{src_raw} + {kw_part} + 时效:{rec_raw} + 权威:{auth_raw}"
    return f"规则评分: {detail} = {int(final)}分 → {'★' * stars}"


def score_article(article: Article, cfg: dict, config: dict) -> Article:
    """对单篇文章执行规则评分。"""
    weights = cfg.get("weights", {})

    # 四维原始分
    src_raw = _source_score(article.source, cfg)
    kw_raw = _keyword_score(article, cfg, config)
    rec_raw = _recency_score(article, cfg)
    auth_raw = _authority_bonus(article, cfg)

    # 加权总分
    final = (
        src_raw * weights.get("source_authority", 0.30) +
        kw_raw * weights.get("keyword_match", 0.30) +
        rec_raw * weights.get("recency", 0.20) +
        auth_raw * weights.get("high_authority_bonus", 0.20)
    )
    final = max(0, min(100, final))

    stars = _final_to_stars(final, cfg)

    article.score = stars
    article.score_reason = _build_reason(src_raw, kw_raw, rec_raw, auth_raw, final, stars, [])
    article.score_breakdown = {
        "source_authority": src_raw,
        "keyword_match": kw_raw,
        "recency": rec_raw,
        "high_authority_bonus": auth_raw,
        "final": round(final, 1),
        "stars": stars,
    }
    return article


def score(articles: list[Article], batch_size: int = 9999) -> list[Article]:
    """对文章列表执行规则评分（batch_size 参数保留兼容，实际不使用）。"""
    if not articles:
        return articles

    cfg = _load_scoring_config()
    config = load_config()

    log.info(f"规则评分: {len(articles)} 篇 (方法={cfg.get('method', 'rules')})")

    for a in articles:
        score_article(a, cfg, config)

    # 统计
    dist = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    for a in articles:
        dist[a.score] = dist.get(a.score, 0) + 1
    log.info(f"评分完成 ★5:{dist[5]} ★4:{dist[4]} ★3:{dist[3]} ★2:{dist[2]} ★1:{dist[1]}")

    return articles
