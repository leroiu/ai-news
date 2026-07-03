"""资讯来源类型、可信度提示与关联实体推导。"""
from __future__ import annotations

from typing import Iterable


PRIMARY_MARKERS = (
    "openai", "anthropic", "google", "deepmind", "meta ai", "microsoft",
    "nvidia", "hugging face", "mit technology review", "arxiv",
)
COMMUNITY_MARKERS = ("hacker news", "reddit", "github trending")


def source_provenance(source: str) -> dict:
    """返回可解释的来源级别；它是筛选提示，不是事实正确性保证。"""
    name = (source or "").strip()
    lower = name.lower()
    if any(marker in lower for marker in COMMUNITY_MARKERS):
        return {
            "source_type": "community",
            "credibility": "contextual",
            "basis": "社区或聚合来源，适合发现线索；关键事实应回到原始发布者核验。",
        }
    if "arxiv" in lower:
        return {
            "source_type": "research",
            "credibility": "medium",
            "basis": "研究论文来源；可能尚未经过同行评审，结论需结合后续验证。",
        }
    if any(marker in lower for marker in PRIMARY_MARKERS):
        return {
            "source_type": "primary",
            "credibility": "high",
            "basis": "机构、企业或研究发布渠道，适合核验其自身产品与声明。",
        }
    return {
        "source_type": "media",
        "credibility": "medium",
        "basis": "二手资讯来源，应结合原文、其他来源和后续事实交叉验证。",
    }


def related_entities(article: dict, entities: Iterable[dict], limit: int = 12) -> list[dict]:
    text = " ".join(str(article.get(field, "")) for field in
                    ("title", "title_cn", "one_liner", "content_raw")).lower()
    matches = []
    for entity in entities:
        terms = [entity.get("name", ""), entity.get("id", ""), *(entity.get("aliases") or [])]
        if any(str(term).lower() in text for term in terms if len(str(term)) >= 3):
            matches.append({key: entity.get(key) for key in ("id", "name", "type", "color")})
    return matches[:limit]


def enrich_article(article: dict, entities: Iterable[dict]) -> dict:
    result = dict(article)
    result["provenance"] = {
        **source_provenance(result.get("source", "")),
        "published_at": result.get("published", ""),
        "collected_at": result.get("created_at", ""),
        "original_url": result.get("url", ""),
    }
    result["related_entities"] = related_entities(result, entities)
    return result
