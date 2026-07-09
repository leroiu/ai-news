#!/bin/bash
# ============================================
# AI News - Daily Pipeline (runs once per day)
# 1. Run collector to get latest articles
# 2. Run pipeline from inbox -> daily report
# 3. Refresh all frontend pages
# ============================================
set -e
cd /home/admin/app

export PYTHONIOENCODING=utf-8
LOGFILE=/home/admin/app/logs/pipeline.log
TODAY=$(date +%Y-%m-%d)

echo "===== $(date '+%Y-%m-%d %H:%M:%S') DAILY PIPELINE START ($TODAY) =====" >> "$LOGFILE"

# Step 1: Collect fresh articles
echo "[$(date '+%H:%M:%S')] Running collector..." >> "$LOGFILE"
/home/admin/app/.venv/bin/python collector.py >> "$LOGFILE" 2>&1

# Step 2: Run daily pipeline (reads from inbox, last 24h)
echo "[$(date '+%H:%M:%S')] Running pipeline --hours 24..." >> "$LOGFILE"
/home/admin/app/.venv/bin/python pipeline.py --hours 24 --date "$TODAY" >> "$LOGFILE" 2>&1

# Step 3: Cleanup old inbox entries
echo "[$(date '+%H:%M:%S')] Running inbox cleanup..." >> "$LOGFILE"
/home/admin/app/.venv/bin/python -c "
from src.engine.utils import cleanup_inbox
kept, archived = cleanup_inbox()
print(f'Inbox: {kept} kept, {archived} archived')
" >> "$LOGFILE" 2>&1

echo "===== $(date '+%Y-%m-%d %H:%M:%S') DAILY PIPELINE END (exit=$?) =====" >> "$LOGFILE"
