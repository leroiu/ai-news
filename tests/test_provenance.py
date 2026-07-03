"""来源可信度提示与实体关联测试。"""
from src.engine.provenance import enrich_article, related_entities, source_provenance


def test_source_provenance_is_explainable():
    assert source_provenance("OpenAI Blog")["credibility"] == "high"
    assert source_provenance("Hacker News (AI 相关)")["credibility"] == "contextual"
    assert source_provenance("ArXiv CS.CL")["source_type"] == "research"
    assert source_provenance("Unknown Media")["credibility"] == "medium"
    assert source_provenance("OpenAI Blog")["basis"]


def test_related_entities_uses_name_id_and_aliases():
    article = {"title": "OpenAI launches GPT-4", "title_cn": "", "one_liner": "", "content_raw": ""}
    entities = [
        {"id": "openai", "name": "OpenAI", "type": "company", "aliases": []},
        {"id": "anthropic", "name": "Anthropic", "type": "company", "aliases": []},
    ]
    assert [item["id"] for item in related_entities(article, entities)] == ["openai"]


def test_enrich_article_adds_traceable_times_and_url():
    article = {"id": "a", "source": "OpenAI", "url": "https://example.com", "published": "2026-01-01", "created_at": "2026-01-02"}
    enriched = enrich_article(article, [])
    assert enriched["provenance"]["original_url"] == "https://example.com"
    assert enriched["provenance"]["published_at"] == "2026-01-01"
    assert enriched["provenance"]["collected_at"] == "2026-01-02"
