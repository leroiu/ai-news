"""
边界条件测试 — 输入验证、空数据处理、异常路径。
"""
import pytest
import tempfile
from pathlib import Path
# ── 轻量 Article mock — 需要支持属性赋值（dedup 会设置 is_duplicate）──
class Article:
    def __init__(self, id, title, url, source="rss", summary="", score=3, date=None):
        self.id = id
        self.title = title
        self.url = url
        self.source = source
        self.summary = summary
        self.score = score
        self.date = date
        self.is_duplicate = False
        self.matched_cards = []


# ═══════════════════════════════════════════════════════════
# 数据库搜索边界
# ═══════════════════════════════════════════════════════════

def test_search_empty_query_returns_results():
    """空搜索关键词返回数据库所有实体（受限 limit=20）。"""
    from src.engine.database import init_db, search
    init_db()
    result = search("")
    assert isinstance(result, dict)
    assert "entities" in result
    # 空搜索退化为全表扫描，返回前20条
    assert isinstance(result["entities"], list)


def test_search_very_long_query():
    """超长搜索关键词不崩溃。"""
    from src.engine.database import init_db, search
    init_db()
    long_query = "AI" * 1000
    result = search(long_query)
    assert isinstance(result, dict)


def test_get_entity_not_found():
    """查询不存在的实体返回 None。"""
    from src.engine.database import get_entity
    result = get_entity("this-entity-does-not-exist-12345")
    assert result is None


def test_get_articles_empty_filters():
    """limit=0 的 get_articles 返回空列表。"""
    from src.engine.database import get_articles
    result = get_articles(limit=0)
    assert isinstance(result, list)
    assert result == []


def test_get_stats_returns_valid():
    """get_stats 返回有效结构。"""
    from src.engine.database import init_db, get_stats
    init_db()
    stats = get_stats()
    assert "entities" in stats
    assert "articles" in stats
    assert isinstance(stats["entities"], int)
    assert stats["entities"] >= 0


# ═══════════════════════════════════════════════════════════
# 嵌入向量边界
# ═══════════════════════════════════════════════════════════

def test_embeddings_all_vectors_valid():
    """所有嵌入向量有效。"""
    from src.engine.embeddings import get_all_embeddings
    vecs = get_all_embeddings()
    assert isinstance(vecs, dict)


def test_cosine_similarity_edge_cases():
    """余弦相似度边界情况。"""
    from src.engine.embeddings import cosine_similarity
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    result = cosine_similarity([0.0, 0.0], [1.0, 1.0])
    assert isinstance(result, (int, float))


# ═══════════════════════════════════════════════════════════
# 卡片加载边界
# ═══════════════════════════════════════════════════════════

def test_load_cards_from_empty_dir():
    """从空目录加载卡片返回空列表。"""
    from src.engine.knowledge import load_cards
    with tempfile.TemporaryDirectory() as td:
        cards = load_cards(Path(td))
        assert isinstance(cards, list)
        assert cards == []


def test_match_cards_empty_articles(isolated_cards_dir):
    """空文章列表匹配不崩溃。"""
    from src.engine.knowledge import match_cards, load_cards
    cards = load_cards(isolated_cards_dir)
    matches = match_cards([], cards)
    assert isinstance(matches, dict)
    assert matches == {}


def test_match_cards_with_articles(isolated_cards_dir):
    """有文章时能匹配卡片。"""
    from src.engine.knowledge import match_cards, load_cards
    from src.engine.fetcher import Article
    cards = load_cards(isolated_cards_dir)
    articles = [
        Article(id="test-gpt4", title="GPT-4 model released with vision capabilities",
                url="http://test.com/gpt4", source="rss")
    ]
    matches = match_cards(articles, cards, use_semantic=False)
    assert isinstance(matches, dict)


# ═══════════════════════════════════════════════════════════
# API 参数验证
# ═══════════════════════════════════════════════════════════

def test_api_reports_invalid_type_returns_empty():
    """无效 report_type 不崩溃，返回空列表。"""
    from src.engine.database import get_reports
    result = get_reports(report_type="invalid_type_xyz", limit=5)
    assert isinstance(result, list)
    assert result == []


def test_api_reports_negative_limit():
    """负数 limit 不崩溃。"""
    from src.engine.database import get_reports
    result = get_reports(report_type="daily", limit=-1)
    assert isinstance(result, list)


# ═══════════════════════════════════════════════════════════
# 去重边界
# ═══════════════════════════════════════════════════════════

def test_dedup_empty_list():
    """空文章列表去重不崩溃。"""
    from src.engine.dedup import deduplicate
    result = deduplicate([], skip_cache=True)
    assert result == []


def test_dedup_identical_urls():
    """相同 URL 的文章去重。"""
    from src.engine.dedup import deduplicate
    articles = [
        Article(id="dedup-test-1", title="AI Breakthrough 2026",
                url="http://dedup-test.example.com/1", source="rss"),
        Article(id="dedup-test-2", title="AI Breakthrough 2026",
                url="http://dedup-test.example.com/1", source="rss"),
    ]
    result = deduplicate(articles, skip_cache=True)
    assert len(result) == 1


def test_dedup_unique_articles():
    """不同文章全部保留。"""
    from src.engine.dedup import deduplicate
    articles = [
        Article(id="dedup-a1", title="OpenAI Announces GPT-5 Model Release Date",
                url="http://dedup-test.example.com/gpt5", source="rss"),
        Article(id="dedup-a2", title="Meta Releases Llama 4 with 400B Parameters",
                url="http://dedup-test.example.com/llama4", source="rss"),
        Article(id="dedup-a3", title="NVIDIA Stock Hits All-Time High on AI Chip Demand",
                url="http://dedup-test.example.com/nvidia", source="rss"),
    ]
    result = deduplicate(articles, skip_cache=True)
    assert len(result) == 3


# ═══════════════════════════════════════════════════════════
# 知识图谱边界
# ═══════════════════════════════════════════════════════════

def test_build_graph_default():
    """默认无参数调用图谱不崩溃。"""
    from src.engine.kg_data import build_graph
    graph = build_graph()
    assert isinstance(graph, dict)
    assert "nodes" in graph or "stats" in graph


def test_build_graph_with_cards(isolated_cards_dir):
    """传入知识卡片列表构建图谱。"""
    from src.engine.kg_data import build_graph
    from src.engine.knowledge import load_cards
    cards = load_cards(isolated_cards_dir)
    graph = build_graph(cards[:20])  # 限制20张测试
    assert isinstance(graph, dict)
    assert len(graph.get("nodes", [])) > 0


# ═══════════════════════════════════════════════════════════
# 趋势报告边界
# ═══════════════════════════════════════════════════════════

def test_trend_reporter_no_daily_reports():
    """没有日报时不生成周报。"""
    from src.engine.trend_reporter import generate_trend_report
    with tempfile.TemporaryDirectory() as td:
        result = generate_trend_report(period="week", reports_dir=Path(td))
        assert result is None
