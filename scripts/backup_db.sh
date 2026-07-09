#!/bin/bash
# ============================================================
# backup_db.sh — 服务器数据库备份
#
# 从本地拉取服务器的 SQLite 数据库，保存到本地备份目录。
# 保留最近 30 天的备份，自动清理过期文件。
#
# 用法:
#   手动: bash scripts/backup_db.sh
#   服务器 Cron: 0 3 * * * /home/admin/app/scripts/backup_db.sh
#
# 安全: 只读操作（scp），不修改服务器任何文件。
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="$PROJECT_DIR/data/backups"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')

SERVER="admin@121.43.80.221"
APP_DIR="/home/admin/app"
SSH_OPTS="-o ConnectTimeout=10 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "  ${GREEN}[OK]${NC} $1"; }
fail() { echo -e "  ${RED}[FAIL]${NC} $1"; }
warn() { echo -e "  ${YELLOW}[WARN]${NC} $1"; }

mkdir -p "$BACKUP_DIR"

echo ""
echo "=============================================="
echo "  AI 观察室 — 数据库备份"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "=============================================="
echo ""

# 1. 检查服务器连通性
echo -n "  连接 $SERVER ... "
if ssh $SSH_OPTS "$SERVER" "echo OK" 2>/dev/null; then
  pass "SSH 可达"
else
  fail "SSH 连接失败"
  exit 1
fi

# 2. 检查服务器数据库文件
DB_SIZE=$(ssh $SSH_OPTS "$SERVER" "stat -c%s $APP_DIR/data/news.db 2>/dev/null || echo 0" 2>/dev/null | tr -d '\r\n')
if [ "${DB_SIZE:-0}" -eq 0 ]; then
  fail "服务器数据库不存在或为空"
  exit 1
fi
DB_SIZE_MB=$(awk "BEGIN {printf \"%.1f\", $DB_SIZE/1024/1024}")
pass "服务器数据库: ${DB_SIZE_MB} MB"

# 3. 备份数据库
BACKUP_FILE="$BACKUP_DIR/news_${TIMESTAMP}.db"
echo ""
echo "  下载数据库到 $BACKUP_FILE ..."
scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "$SERVER:$APP_DIR/data/news.db" "$BACKUP_FILE"

# 4. 验证备份
LOCAL_SIZE=$(stat -c%s "$BACKUP_FILE" 2>/dev/null || echo 0)
if [ "${LOCAL_SIZE:-0}" -eq "${DB_SIZE:-0}" ]; then
  pass "备份完成 (${DB_SIZE_MB} MB, 大小一致)"
else
  fail "备份大小不一致: 服务器=${DB_SIZE}B, 本地=${LOCAL_SIZE}B"
  exit 1
fi

# 5. 保留备注：记录表数据量
echo ""
echo "  数据库统计:"
ssh $SSH_OPTS "$SERVER" "
  cd $APP_DIR && .venv/bin/python -c \"
import sqlite3
db = sqlite3.connect('data/news.db')
tables = ['articles','entities','relationships','reports']
for t in tables:
    try:
        c = db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
        print(f'    {t}: {c}')
    except:
        print(f'    {t}: N/A')
db.close()
\" 2>/dev/null || echo '    统计失败'
"

# 6. 清理 30 天前的旧备份
OLD_COUNT=$(find "$BACKUP_DIR" -name "news_*.db" -mtime +30 2>/dev/null | wc -l)
if [ "$OLD_COUNT" -gt 0 ]; then
  warn "清理 $OLD_COUNT 个超过 30 天的旧备份"
  find "$BACKUP_DIR" -name "news_*.db" -mtime +30 -delete
fi

# 7. 备份报告
echo ""
echo "=============================================="
echo "  备份完成"
echo "  文件: $BACKUP_FILE"
echo "  大小: ${DB_SIZE_MB} MB"
echo "  当前备份数: $(ls "$BACKUP_DIR"/news_*.db 2>/dev/null | wc -l)"
echo "=============================================="
