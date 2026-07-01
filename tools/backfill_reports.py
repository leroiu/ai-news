#!/usr/bin/env python3
"""
回填历史报告到 SQLite reports 表。

扫描 reports/ 目录中的日报/周报/月报文件，
解析元数据后写入数据库。
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.engine.database import init_db, insert_report
from src.engine.utils import log, setup_logging, ROOT_DIR


def parse_daily(path: Path) -> dict | None:
    """解析日报文件头，提取元数据。"""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None

    # 日期: 2026-06-27
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", path.stem)
    if not date_match:
        return None

    info = {"date": date_match.group(1), "report_type": "daily", "path": str(path),
            "fetched": 0, "filtered": 0, "star5": 0, "star4": 0, "star3": 0}

    # 抓取 41 条 → 筛选 28 条
    fm = re.search(r"抓取\s*(\d+)\s*条.*?筛选\s*(\d+)\s*条", text)
    if fm:
        info["fetched"] = int(fm.group(1))
        info["filtered"] = int(fm.group(2))

    # 用负向断言精确匹配星数，避免 ★★★★ 误匹配 ★★★★★ 前四星
    s5 = re.search(r"(?<![★])★★★★★(?![★])\s*(\d+)\s*条", text)
    if s5:
        info["star5"] = int(s5.group(1))
    s4 = re.search(r"(?<![★])★★★★(?![★])\s*(\d+)\s*条", text)
    if s4:
        info["star4"] = int(s4.group(1))
    s3 = re.search(r"(?<![★])★★★(?![★])\s*(\d+)\s*条", text)
    if s3:
        info["star3"] = int(s3.group(1))

    return info


def parse_weekly(path: Path) -> dict | None:
    """解析周报文件名。"""
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", path.stem)
    if not date_match:
        return None
    return {"date": date_match.group(1), "report_type": "weekly", "path": str(path)}


def parse_monthly(path: Path) -> dict | None:
    """解析月报文件名。"""
    date_match = re.search(r"(\d{4}-\d{2})", path.stem)
    if not date_match:
        return None
    return {"date": date_match.group(1) + "-01", "report_type": "monthly", "path": str(path)}


def main():
    setup_logging("INFO")
    init_db()

    reports_dir = ROOT_DIR / "reports"
    if not reports_dir.exists():
        log.error(f"reports 目录不存在: {reports_dir}")
        return 1

    inserted = 0
    for f in sorted(reports_dir.iterdir()):
        if not f.suffix == ".md":
            continue

        name = f.name.lower()
        if name.startswith("weekly"):
            info = parse_weekly(f)
        elif name.startswith("monthly"):
            info = parse_monthly(f)
        elif re.match(r"^\d{4}-\d{2}-\d{2}\.md$", f.name):
            info = parse_daily(f)
        else:
            continue  # skip index.md, dashboard.html etc.

        if info:
            insert_report(**{k: v for k, v in info.items() if k != "report_type"},
                          report_type=info["report_type"])
            log.info(f"  ✅ {info['report_type']}: {info['date']} ({info.get('star5', 0)}★5)")
            inserted += 1

    log.info(f"回填完成: {inserted} 条报告写入 DB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
