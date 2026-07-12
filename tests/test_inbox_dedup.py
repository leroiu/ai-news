"""inbox 持久化去重测试。

验证 append_inbox 在写入前按 article_id 去重，
确保同一 URL 的文章不会在 inbox.jsonl 中出现多次。
"""

import json
from pathlib import Path

from src.engine.utils import append_inbox, read_inbox
from src.engine.fetcher import Article


def _make_article(title: str, url: str, source: str = "Test") -> Article:
    return Article(id=Article.make_id(url), title=title, url=url, source=source)


def test_append_new_articles_to_empty_inbox(tmp_path: Path):
    """空 inbox：新文章应正常写入。"""
    inbox = tmp_path / "inbox.jsonl"
    articles = [
        _make_article("Article A", "https://example.com/a"),
        _make_article("Article B", "https://example.com/b"),
    ]
    result = append_inbox(articles, inbox_path=inbox)
    assert result == inbox
    assert inbox.exists()
    lines = inbox.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2


def test_duplicate_articles_are_skipped(tmp_path: Path):
    """同一 URL 的文章再次写入应被跳过。"""
    inbox = tmp_path / "inbox.jsonl"
    articles = [_make_article("Article A", "https://example.com/a")]
    append_inbox(articles, inbox_path=inbox)

    # 第二次写入相同 URL
    articles2 = [_make_article("Article A (repeat)", "https://example.com/a")]
    append_inbox(articles2, inbox_path=inbox)

    lines = inbox.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["title"] == "Article A"  # 保留首次写入的标题，不覆盖


def test_mix_of_new_and_existing_articles(tmp_path: Path):
    """混合新旧文章时，只追加新文章。"""
    inbox = tmp_path / "inbox.jsonl"
    articles = [
        _make_article("Old A", "https://example.com/a"),
        _make_article("Old B", "https://example.com/b"),
    ]
    append_inbox(articles, inbox_path=inbox)

    articles2 = [
        _make_article("Old A (repeat)", "https://example.com/a"),  # 重复
        _make_article("New C", "https://example.com/c"),           # 新增
    ]
    append_inbox(articles2, inbox_path=inbox)

    lines = inbox.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 3  # a, b, c
    ids = [json.loads(l)["id"] for l in lines]
    assert ids.count(Article.make_id("https://example.com/a")) == 1


def test_rss_deduplicate_across_runs(tmp_path: Path):
    """模拟两次 Action 运行：同一 RSS 源产出相同 URL，inbox 只保留一条。"""
    inbox = tmp_path / "inbox.jsonl"

    # Run 1: 采集器写入 A, B
    run1 = [
        _make_article("RSS Item 1", "https://rss.example.com/1"),
        _make_article("RSS Item 2", "https://rss.example.com/2"),
    ]
    append_inbox(run1, inbox_path=inbox)

    # Run 2: 同一个 RSS 源产出完全相同 URL（seen_urls.json 丢失的情况）
    run2 = [
        _make_article("RSS Item 1", "https://rss.example.com/1"),
        _make_article("RSS Item 2", "https://rss.example.com/2"),
        _make_article("RSS Item 3", "https://rss.example.com/3"),
    ]
    append_inbox(run2, inbox_path=inbox)

    lines = inbox.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 3  # 1, 2, 3（1 和 2 不重复）

    # 验证 read_inbox 也不会返回重复
    articles = read_inbox(inbox_path=inbox)
    assert len(articles) == 3


def test_empty_articles_list(tmp_path: Path):
    """空文章列表不应创建文件或报错。"""
    inbox = tmp_path / "inbox.jsonl"
    append_inbox([], inbox_path=inbox)
    assert not inbox.exists() or inbox.stat().st_size == 0


def test_corrupted_line_does_not_block(tmp_path: Path):
    """inbox 中有损坏行时不应阻塞后续写入。"""
    inbox = tmp_path / "inbox.jsonl"
    # 写一条正常 + 一条损坏
    inbox.write_text(
        json.dumps(_make_article("Good", "https://example.com/good").to_dict())
        + "\ncorrupted json line\n",
        encoding="utf-8",
    )
    articles = [_make_article("New", "https://example.com/new")]
    append_inbox(articles, inbox_path=inbox)

    lines = inbox.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 3  # good + corrupted + new
