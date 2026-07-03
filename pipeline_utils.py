#!/usr/bin/env python3
"""
Pipeline 工具 — 断点系统 + 计时 + 容错执行器。

从 pipeline.py 拆分出来。
"""

import json
import time
import traceback
from datetime import datetime
from pathlib import Path

from src.engine.utils import log, ROOT_DIR
from src.engine.database import update_pipeline_run

# ── Checkpoint 文件 ──
CHECKPOINT_FILE = ROOT_DIR / "data" / ".pipeline_checkpoint.json"

# ── 全局状态 ──
_stage_times: dict[str, float] = {}
_failed_articles: dict[str, list[str]] = {}


# ═══════════════════════════════════════════════════════════════
# 计时工具
# ═══════════════════════════════════════════════════════════════

def _tick() -> float:
    return time.time()


def _log_stage(name: str, elapsed: float):
    _stage_times[name] = elapsed
    log.info(f"  ⏱ {name}: {elapsed:.1f}s")


# ═══════════════════════════════════════════════════════════════
# Checkpoint 系统
# ═══════════════════════════════════════════════════════════════

def save_checkpoint(stage: str, article_ids: list[str], run_id: int,
                    extra: dict | None = None) -> None:
    """保存断点：当前阶段 + 文章列表 + 已完成阶段 + 失败记录。"""
    try:
        existing = {}
        if CHECKPOINT_FILE.exists():
            existing = json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8"))
        completed = existing.get("completed_stages", [])
        if stage not in completed:
            completed.append(stage)
        data = {
            "run_id": run_id,
            "stage": stage,
            "article_ids": article_ids,
            "completed_stages": completed,
            "failed_articles": _failed_articles,
            "stage_times": _stage_times,
            "started_at": existing.get("started_at", datetime.now().isoformat()),
            "updated_at": datetime.now().isoformat(),
        }
        if extra:
            data.update(extra)
        CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
        CHECKPOINT_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as e:
        log.warning(f"保存断点失败: {e}")


def load_checkpoint() -> dict | None:
    """加载断点文件，恢复全局状态。"""
    if not CHECKPOINT_FILE.exists():
        return None
    try:
        data = json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8"))
        global _stage_times, _failed_articles
        _stage_times = data.get("stage_times", {})
        _failed_articles = data.get("failed_articles", {})
        return data
    except (json.JSONDecodeError, OSError) as e:
        log.warning(f"断点文件损坏，忽略: {e}")
        return None


def clear_checkpoint() -> None:
    """清除断点文件。"""
    try:
        if CHECKPOINT_FILE.exists():
            CHECKPOINT_FILE.unlink()
    except OSError:
        pass


# ═══════════════════════════════════════════════════════════════
# 容错执行器
# ═══════════════════════════════════════════════════════════════

class StageError(Exception):
    """阶段级错误（非致命，可跳过继续）。"""
    pass


class FatalError(Exception):
    """致命错误（无法继续，需中止 pipeline）。"""
    pass


def run_stage(name: str, articles: list, run_id: int,
              checkpoint: bool = True,
              allow_partial: bool = False) -> list:
    """执行一个阶段，带错误恢复和断点保存。

    - 非致命异常：记录到 _failed_articles，继续执行
    - 致命异常：保存断点后重新抛出
    - allow_partial: True 时，部分失败不影响后续阶段
    """
    article_ids = [a.id for a in articles] if articles else []
    if checkpoint and article_ids:
        save_checkpoint(name, article_ids, run_id)

    try:
        yield  # 让调用方执行阶段逻辑
    except FatalError:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        log.error(f"阶段 [{name}] 异常: {e}")
        log.debug(tb)
        if allow_partial:
            log.warning(f"  → [{name}] 部分失败，继续执行后续阶段")
            _failed_articles.setdefault(name, []).append(str(e))
            update_pipeline_run(run_id, error_message=f"[{name}] {e}")
        else:
            save_checkpoint(name, article_ids, run_id)
            update_pipeline_run(run_id, error_message=f"[{name}] {e}")
            raise StageError(f"阶段 [{name}] 失败: {e}")
