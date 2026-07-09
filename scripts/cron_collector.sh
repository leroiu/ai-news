#!/bin/bash
# ============================================
# AI News - Collector (runs every hour)
# Fetch RSS -> Dedup -> Write inbox.jsonl
# ============================================
set -e
cd /home/admin/app

export PYTHONIOENCODING=utf-8
LOGFILE=/home/admin/app/logs/collector.log

echo "===== $(date '+%Y-%m-%d %H:%M:%S') COLLECTOR START =====" >> "$LOGFILE"
/home/admin/app/.venv/bin/python collector.py >> "$LOGFILE" 2>&1
echo "===== $(date '+%Y-%m-%d %H:%M:%S') COLLECTOR END (exit=$?) =====" >> "$LOGFILE"
