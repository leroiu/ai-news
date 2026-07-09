#!/bin/bash
# ============================================================
# cron_backup_db.sh — 服务器端数据库备份（在服务器 crontab 中运行）
#
# 不需要本地机器在线。复制 SQLite DB + WAL 文件到备份目录。
# 保留最近 30 天。
#
# 服务器 Cron 配置:
#   0 3 * * * /home/admin/app/scripts/cron_backup_db.sh
# ============================================================
set -euo pipefail

APP_DIR="/home/admin/app"
BACKUP_DIR="$APP_DIR/data/backups"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
DB="$APP_DIR/data/platform.db"
DB_NAME="platform"
KEEP_DAYS=30

mkdir -p "$BACKUP_DIR"

# 备份数据库文件
for ext in "" "-wal" "-shm"; do
  if [ -f "${DB}${ext}" ]; then
    cp "${DB}${ext}" "$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.db${ext}"
  fi
done

# 记录表统计
.venv/bin/python -c "
import sqlite3
from datetime import datetime
db = sqlite3.connect('$DB')
tables = ['articles','entities','relationships','reports']
stats = []
for t in tables:
    try:
        c = db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
        stats.append(f'{t}={c}')
    except: pass
db.close()
print(f'{datetime.now():%Y-%m-%d %H:%M:%S}  backup: {\" \".join(stats)}')
" >> "$BACKUP_DIR/backup.log"

# 清理旧备份
find "$BACKUP_DIR" -name "${DB_NAME}_*.db*" -mtime +${KEEP_DAYS} -delete 2>/dev/null || true

echo "backup done: $TIMESTAMP ($(ls "$BACKUP_DIR"/${DB_NAME}_*.db 2>/dev/null | wc -l) 个备份)"
