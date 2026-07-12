"""
AI News - 公共工具模块

配置加载、日志、文件读写等基础设施。
"""

from __future__ import annotations

import logging
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# 项目根目录
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

# 加载 .env
load_dotenv(ROOT_DIR / ".env")


def setup_logging(level: str = "INFO") -> logging.Logger:
    """配置并返回 logger。"""
    logger = logging.getLogger("ai-news")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


log = setup_logging()


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """加载 YAML 配置文件。"""
    if path is None:
        path = ROOT_DIR / "config.yaml"
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_json(path: str | Path) -> dict | list:
    """读取 JSON 文件，不存在则返回空 dict。"""
    path = Path(path)
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str | Path, data: dict | list) -> None:
    """写入 JSON 文件，自动创建父目录。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def ensure_dir(path: str | Path) -> Path:
    """确保目录存在。"""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def clean_html(raw: str) -> str:
    """清洗 HTML 标签，提取纯文本。减小传给 AI 的 token 量。"""
    if not raw or "<" not in raw:
        return raw
    try:
        from bs4 import BeautifulSoup
        return BeautifulSoup(raw, "html.parser").get_text(separator=" ", strip=True)
    except Exception:
        return raw


# ============================================================
# Inbox 存储（JSONL 格式，支持追加写）
# ============================================================

INBOX_DIR = ROOT_DIR / "data"


def append_inbox(articles: list[Article], inbox_path: Path | None = None) -> Path:
    """将文章追加写入 JSONL 文件（含持久化去重）。

    写入前读取现有 inbox 中的 article_id，已存在则跳过。
    确保同一 URL 的文章不会在 inbox 中出现多次（跨 Action 运行）。

    返回写入后的 inbox 路径。
    """
    if inbox_path is None:
        inbox_path = INBOX_DIR / "inbox.jsonl"
    inbox_path = Path(inbox_path)
    inbox_path.parent.mkdir(parents=True, exist_ok=True)

    # ── 读取现有 inbox 中的文章 ID ──
    existing_ids: set[str] = set()
    if inbox_path.exists() and inbox_path.stat().st_size > 0:
        with open(inbox_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    aid = json.loads(line).get("id", "")
                    if aid:
                        existing_ids.add(aid)
                except json.JSONDecodeError:
                    continue

    # ── 过滤：只保留 inbox 中不存在的文章 ──
    new_articles = [a for a in articles if a.id not in existing_ids]
    skipped = len(articles) - len(new_articles)
    if skipped:
        log.info(f"Inbox 去重: 跳过 {skipped} 篇已存在 (现有 {len(existing_ids)} 条)")

    if not new_articles:
        log.debug("Inbox 写入: 无新文章")
        return inbox_path

    with open(inbox_path, "a", encoding="utf-8") as f:
        for a in new_articles:
            f.write(json.dumps(a.to_dict(), ensure_ascii=False, default=str) + "\n")
    log.debug(f"Inbox 写入: {len(new_articles)} 条 → {inbox_path}")
    return inbox_path


def read_inbox(inbox_path: Path | None = None, since_hours: int = 0) -> list[Article]:
    """从 JSONL 文件读取文章。since_hours>0 时只返回近 N 小时的文章。"""
    from .fetcher import Article  # 延迟导入，避免循环依赖

    if inbox_path is None:
        inbox_path = INBOX_DIR / "inbox.jsonl"
    inbox_path = Path(inbox_path)
    if not inbox_path.exists():
        return []

    cutoff = None
    if since_hours > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)

    articles: list[Article] = []
    with open(inbox_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                a = Article.from_dict(d)
                # 过滤：太旧的文章跳过
                if cutoff and a.published:
                    try:
                        dt = datetime.fromisoformat(a.published)
                        if dt < cutoff:
                            continue
                    except (ValueError, TypeError):
                        pass  # 无日期的保留
                articles.append(a)
            except (json.JSONDecodeError, KeyError):
                log.warning(f"Inbox 跳过损坏行: {line[:80]}...")
    return articles


# ============================================================
# Inbox 归档（防止无限增长）
# ============================================================

ARCHIVE_DIR = ROOT_DIR / "data" / "archive"


def cleanup_inbox(
    inbox_path: Path | None = None,
    max_days: int = 14,
    dry_run: bool = False,
) -> tuple[int, int]:
    """
    归档旧条目，保持 inbox 瘦身。

    将超过 max_days 天的条目移到 data/archive/YYYY-MM.jsonl，
    只保留最近的条目在 inbox 中。

    Returns:
        (kept_count, archived_count)
    """
    if inbox_path is None:
        inbox_path = INBOX_DIR / "inbox.jsonl"
    inbox_path = Path(inbox_path)

    if not inbox_path.exists():
        log.debug("inbox 不存在，跳过归档")
        return (0, 0)

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_days)

    # 读取所有行
    recent_lines: list[str] = []
    archive_buckets: dict[str, list[str]] = {}  # {"YYYY-MM": [lines]}

    with open(inbox_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # 尝试解析日期
            is_recent = True
            try:
                d = json.loads(line)
                pub = d.get("published")
                if pub:
                    dt = datetime.fromisoformat(pub)
                    if dt < cutoff:
                        is_recent = False
                        month_key = dt.strftime("%Y-%m")
                        archive_buckets.setdefault(month_key, []).append(line)
            except (json.JSONDecodeError, ValueError):
                pass  # 无法解析的保留在 inbox

            if is_recent:
                recent_lines.append(line)

    total = len(recent_lines) + sum(len(v) for v in archive_buckets.values())
    archived = sum(len(v) for v in archive_buckets.values())

    if archived == 0:
        log.debug(f"归档检查: {total} 条，无需归档")
        return (len(recent_lines), 0)

    if dry_run:
        log.info(f"[DRY RUN] 将归档 {archived}/{total} 条 → {len(archive_buckets)} 个月份文件")
        for month, lines in sorted(archive_buckets.items()):
            log.info(f"  {month}: {len(lines)} 条")
        return (len(recent_lines), archived)

    # 写入归档
    ensure_dir(ARCHIVE_DIR)
    for month, lines in archive_buckets.items():
        archive_path = ARCHIVE_DIR / f"{month}.jsonl"
        with open(archive_path, "a", encoding="utf-8") as f:
            for line in lines:
                f.write(line + "\n")
        log.info(f"归档: {archive_path.name} ← {len(lines)} 条")

    # 重写 inbox（只保留近期条目）
    inbox_path.write_text("\n".join(recent_lines) + ("\n" if recent_lines else ""),
                          encoding="utf-8")

    log.info(f"inbox 清理: {total} → {len(recent_lines)} 条 "
             f"(归档 {archived} 条, 保留 ≤{max_days}d)")
    return (len(recent_lines), archived)

