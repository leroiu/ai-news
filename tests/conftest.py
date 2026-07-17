"""全量测试隔离：临时运行目录、受控知识卡、AI stub 与外部网络阻断。"""

from __future__ import annotations

import ipaddress
import shutil
import socket
from pathlib import Path

import pytest
import yaml


@pytest.fixture(scope="session")
def isolated_cards_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    cards_dir = tmp_path_factory.mktemp("knowledge-cards")
    cards = [
        {
            "id": "openai",
            "name": "OpenAI",
            "type": "company",
            "tags": ["openai", "ai-lab"],
            "aliases": ["open ai"],
            "summary": "AI research company.",
            "significance": "Develops major AI systems.",
        },
        {
            "id": "gpt-4",
            "name": "GPT-4",
            "type": "model",
            "tags": ["gpt-4", "openai", "llm"],
            "aliases": ["gpt4"],
            "summary": "OpenAI multimodal model.",
            "significance": "Important model release.",
        },
        {
            "id": "transformer",
            "name": "Transformer",
            "type": "tech",
            "tags": ["transformer", "attention"],
            "aliases": [],
            "summary": "Attention-based architecture.",
            "significance": "Foundation of modern LLMs.",
        },
        {
            "id": "agent",
            "name": "AI Agent",
            "type": "concept",
            "tags": ["agent", "automation"],
            "aliases": ["ai agent"],
            "summary": "A system that acts toward goals.",
            "significance": "Core automation pattern.",
        },
    ]
    for card in cards:
        target = cards_dir / card["type"] / f"{card['id']}.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            yaml.safe_dump(card, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
    return cards_dir


def _is_loopback(address: object) -> bool:
    if not isinstance(address, tuple) or not address:
        return False
    host = str(address[0]).strip("[]").lower()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def isolated_test_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    isolated_cards_dir: Path,
):
    runtime = tmp_path / "runtime"
    data_dir = runtime / "data"
    reports_dir = runtime / "reports"
    cache_dir = runtime / "cache"
    logs_dir = runtime / "logs"
    for path in (data_dir, reports_dir, cache_dir, logs_dir):
        path.mkdir(parents=True, exist_ok=True)

    project_root = Path(__file__).resolve().parent.parent
    for asset_dir in ("prompts", "templates"):
        shutil.copytree(project_root / asset_dir, runtime / asset_dir)

    for page in (
        "dashboard.html",
        "library.html",
        "knowledge-graph.html",
        "knowledge-graph-3d.html",
        "timeline.html",
        "events.html",
        "reports.html",
        "research.html",
        "my.html",
        "auth.html",
        "entity.html",
        "article.html",
        "report-reader.html",
    ):
        (reports_dir / page).write_text(
            f"<!doctype html><title>{page}</title>",
            encoding="utf-8",
        )

    monkeypatch.setenv("AI_NEWS_TESTING", "1")
    for name in (
        "DEEPSEEK_API_KEY",
        "MOONSHOT_API_KEY",
        "AGNES_API_KEY",
        "SILICONFLOW_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    from src.engine import (
        ai_client,
        cache,
        concept_miner,
        db_core,
        dedup,
        fetcher,
        kg_mermaid,
        knowledge,
        reporter,
        sync_cards,
        trend_agent,
        trend_reporter,
        utils,
    )
    import pipeline_utils

    call_ai_stub = lambda *args, **kwargs: None
    embed_texts_stub = lambda *args, **kwargs: None
    monkeypatch.setattr(ai_client, "call_ai", call_ai_stub)
    monkeypatch.setattr(ai_client, "embed_texts", embed_texts_stub)
    for module_name in ("classifier", "concept_miner", "summarizer", "trend_reporter"):
        module = __import__(f"src.engine.{module_name}", fromlist=["call_ai"])
        monkeypatch.setattr(module, "call_ai", call_ai_stub)

    monkeypatch.setattr(db_core, "DB_PATH", data_dir / "platform.db")
    monkeypatch.setattr(cache, "CACHE_PATH", data_dir / "processed_cache.json")
    monkeypatch.setattr(concept_miner, "POOL_PATH", data_dir / "candidate_concepts.json")
    monkeypatch.setattr(concept_miner, "MINED_CACHE_PATH", data_dir / "mined_article_ids.json")
    monkeypatch.setattr(concept_miner, "ROOT_DIR", runtime)
    monkeypatch.setattr(fetcher, "HEALTH_FILE", data_dir / "source_health.json")
    monkeypatch.setattr(knowledge, "CARDS_DIR", isolated_cards_dir)
    monkeypatch.setattr(sync_cards, "CARDS_DIR", isolated_cards_dir)
    monkeypatch.setattr(utils, "INBOX_DIR", data_dir)
    monkeypatch.setattr(utils, "ARCHIVE_DIR", data_dir / "archive")
    monkeypatch.setattr(dedup, "ROOT_DIR", runtime)
    monkeypatch.setattr(reporter, "ROOT_DIR", runtime)
    monkeypatch.setattr(trend_agent, "ROOT_DIR", runtime)
    monkeypatch.setattr(trend_reporter, "ROOT_DIR", runtime)
    monkeypatch.setattr(kg_mermaid, "ROOT_DIR", runtime)
    monkeypatch.setattr(
        pipeline_utils,
        "CHECKPOINT_FILE",
        data_dir / ".pipeline_checkpoint.json",
    )
    db_core.init_db()

    import src.engine.card_writer as card_writer
    monkeypatch.setattr(card_writer, "ROOT_DIR", runtime)

    for module_name in (
        "article_page",
        "auth_page",
        "dashboard",
        "entity_page",
        "events_page",
        "kg_3d",
        "kg_d3",
        "library",
        "my_page",
        "report_reader",
        "reports_page",
        "research_page",
        "timeline_renderer",
    ):
        module = __import__(f"src.frontend.{module_name}", fromlist=["ROOT_DIR"])
        if hasattr(module, "ROOT_DIR"):
            monkeypatch.setattr(module, "ROOT_DIR", runtime)

    import src.api.api as api_module
    monkeypatch.setattr(api_module, "REPORTS_DIR", reports_dir)

    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create_connection = socket.create_connection
    original_sendto = socket.socket.sendto
    original_getaddrinfo = socket.getaddrinfo

    def guarded_connect(sock, address):
        if not _is_loopback(address):
            raise RuntimeError(f"测试禁止外部网络连接: {address!r}")
        return original_connect(sock, address)

    def guarded_connect_ex(sock, address):
        if not _is_loopback(address):
            raise RuntimeError(f"测试禁止外部网络连接: {address!r}")
        return original_connect_ex(sock, address)

    def guarded_create_connection(address, *args, **kwargs):
        if not _is_loopback(address):
            raise RuntimeError(f"测试禁止外部网络连接: {address!r}")
        return original_create_connection(address, *args, **kwargs)

    def guarded_sendto(sock, data, address, *args, **kwargs):
        if not _is_loopback(address):
            raise RuntimeError(f"测试禁止外部网络连接: {address!r}")
        return original_sendto(sock, data, address, *args, **kwargs)

    def guarded_getaddrinfo(host, *args, **kwargs):
        if host is not None and not _is_loopback((host, 0)):
            raise RuntimeError(f"测试禁止外部网络解析: {host!r}")
        return original_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket.socket, "sendto", guarded_sendto)
    monkeypatch.setattr(socket, "create_connection", guarded_create_connection)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)

    yield runtime
