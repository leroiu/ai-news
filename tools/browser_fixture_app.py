"""浏览器门禁专用 FastAPI 应用。

此模块只在独立子进程中加载。它在导入生产 API 前把 ROOT_DIR 和数据库
重定向到门禁运行目录，从而避免读取或写入项目 data/ 与 reports/。
"""

from __future__ import annotations

import os
from pathlib import Path


runtime_value = os.environ.get("AI_NEWS_BROWSER_RUNTIME", "").strip()
if not runtime_value:
    raise RuntimeError("缺少 AI_NEWS_BROWSER_RUNTIME，禁止启动未隔离的浏览器夹具")

RUNTIME_DIR = Path(runtime_value).resolve()
REPORTS_DIR = RUNTIME_DIR / "reports"
DB_PATH = RUNTIME_DIR / "data" / "platform.db"

if not REPORTS_DIR.is_dir() or not DB_PATH.is_file():
    raise RuntimeError(f"浏览器夹具未准备完成：{RUNTIME_DIR}")

os.environ["AI_NEWS_TESTING"] = "1"

from src.engine import utils  # noqa: E402

utils.ROOT_DIR = RUNTIME_DIR

from src.engine import db_core  # noqa: E402

db_core.DB_PATH = DB_PATH

from src.api import api as api_module  # noqa: E402

if api_module.REPORTS_DIR.resolve() != REPORTS_DIR:
    raise RuntimeError(
        f"API 静态目录未隔离：{api_module.REPORTS_DIR} != {REPORTS_DIR}"
    )

app = api_module.app
