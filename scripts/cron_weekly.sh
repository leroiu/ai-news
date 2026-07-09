#!/bin/bash
# ============================================
# AI News - Weekly Report (runs every Sunday)
# ============================================
set -e
cd /home/admin/app

export PYTHONIOENCODING=utf-8
LOGFILE=/home/admin/app/logs/pipeline.log

echo "===== $(date '+%Y-%m-%d %H:%M:%S') WEEKLY REPORT START =====" >> "$LOGFILE"
/home/admin/app/.venv/bin/python pipeline.py --weekly >> "$LOGFILE" 2>&1
echo "===== $(date '+%Y-%m-%d %H:%M:%S') WEEKLY REPORT END (exit=$?) =====" >> "$LOGFILE"
