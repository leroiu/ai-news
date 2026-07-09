#!/bin/bash
# ============================================================
# preflight.sh — 部署前环境检查
# 检查本地 + 服务器是否就绪，不修改任何文件。
# 用法: bash scripts/preflight.sh
# ============================================================
set -euo pipefail

SERVER="admin@121.43.80.221"
APP_DIR="/home/admin/app"
SSH_OPTS="-o ConnectTimeout=10 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

# --- 颜色 ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass() { echo -e "  ${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "  ${RED}[FAIL]${NC} $1"; }
warn() { echo -e "  ${YELLOW}[WARN]${NC} $1"; }

echo ""
echo "=============================================="
echo " Preflight Check — $(date '+%Y-%m-%d %H:%M:%S')"
echo "=============================================="
echo ""

# ============================================================
# Phase 1: 本地环境检查
# ============================================================
echo "[Phase 1/3] 本地环境检查"
echo "------------------------"

# 1.1 项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
echo "  项目目录: $PROJECT_DIR"

if [ -f "$PROJECT_DIR/pipeline.py" ]; then
  pass "pipeline.py 存在"
else
  fail "pipeline.py 不存在 — 请在项目根目录运行此脚本"
  exit 1
fi

# 1.2 关键源文件
KEY_FILES=(
  "src/frontend/dashboard.py"
  "src/frontend/report_reader.py"
  "src/frontend/my_page.py"
  "src/frontend/frontend_styles.py"
  "src/interfaces/i18n.py"
  "src/api/api.py"
  "pipeline.py"
  "pipeline_stages.py"
)

MISSING_FILES=()
for f in "${KEY_FILES[@]}"; do
  if [ -f "$PROJECT_DIR/$f" ]; then
    pass "$f"
  else
    fail "$f — 缺失"
    MISSING_FILES+=("$f")
  fi
done

if [ ${#MISSING_FILES[@]} -gt 0 ]; then
  echo ""
  fail "${#MISSING_FILES[@]} 个文件缺失，无法继续。"
  exit 1
fi

# 1.3 Python 可用
if command -v python &>/dev/null; then
  pass "python 可用: $(python --version 2>&1)"
elif command -v python3 &>/dev/null; then
  pass "python3 可用: $(python3 --version 2>&1)"
else
  fail "python 不可用"
  exit 1
fi

# 1.4 Git 仓库状态
if [ -d "$PROJECT_DIR/.git" ]; then
  BRANCH=$(cd "$PROJECT_DIR" && git branch --show-current 2>/dev/null || echo "unknown")
  CHANGES=$(cd "$PROJECT_DIR" && git status --short 2>/dev/null | wc -l)
  pass "Git 分支: $BRANCH, 未提交变更: $CHANGES 个"
  if [ "$CHANGES" -gt 0 ]; then
    warn "有未提交的变更 — 请确认是否继续"
  fi
else
  warn "非 Git 仓库，跳过版本检查"
fi

echo ""

# ============================================================
# Phase 2: SSH 连通性 & 服务器环境
# ============================================================
echo "[Phase 2/3] 服务器连通性 & 环境"
echo "--------------------------------"

# 2.1 SSH 连通
echo -n "  连接 $SERVER ... "
if ssh $SSH_OPTS "$SERVER" "echo OK" 2>/dev/null; then
  pass "SSH 连接成功"
else
  fail "SSH 连接失败 — 请检查网络和 SSH key"
  exit 1
fi

# 2.2 服务器 APP_DIR 是否存在
if ssh $SSH_OPTS "$SERVER" "test -d $APP_DIR" 2>/dev/null; then
  pass "服务器 $APP_DIR 存在"
else
  fail "服务器 $APP_DIR 不存在"
  exit 1
fi

# 2.3 服务器磁盘空间
DISK_LINE=$(ssh $SSH_OPTS "$SERVER" "df -h /home/admin | tail -1" 2>/dev/null || echo "")
if [ -n "$DISK_LINE" ]; then
  echo "  $DISK_LINE"
  USED_PCT=$(echo "$DISK_LINE" | awk '{print $5}' | sed 's/%//')
  if [ "${USED_PCT:-0}" -gt 90 ]; then
    warn "磁盘使用率 > 90%，请注意空间"
  else
    pass "磁盘使用率: ${USED_PCT}%"
  fi
else
  warn "无法获取磁盘信息"
fi

# 2.4 ai-news 服务状态
echo -n "  ai-news 服务: "
SVC_STATUS=$(ssh $SSH_OPTS "$SERVER" "systemctl is-active ai-news 2>/dev/null || echo 'unknown'" 2>/dev/null | tr -d '\r\n')
case "$SVC_STATUS" in
  active)   pass "ai-news 服务运行中" ;;
  inactive) warn "ai-news 服务未运行" ;;
  unknown)  warn "无法检测 ai-news 服务状态（可能未配置 systemd）" ;;
  *)        warn "ai-news 服务状态: $SVC_STATUS" ;;
esac

# 2.5 Nginx 状态
echo -n "  Nginx 服务: "
NGX_STATUS=$(ssh $SSH_OPTS "$SERVER" "systemctl is-active nginx 2>/dev/null || echo 'unknown'" 2>/dev/null | tr -d '\r\n')
case "$NGX_STATUS" in
  active)   pass "Nginx 运行中" ;;
  inactive) fail "Nginx 未运行" ;;
  unknown)  warn "无法检测 Nginx 状态" ;;
  *)        warn "Nginx 状态: $NGX_STATUS" ;;
esac

# 2.6 Nginx 配置语法
echo -n "  Nginx 配置语法: "
NGX_TEST=$(ssh $SSH_OPTS "$SERVER" "sudo nginx -t 2>&1" 2>/dev/null || true)
if echo "$NGX_TEST" | grep -q "successful"; then
  pass "Nginx 配置语法正确"
else
  warn "Nginx 配置语法检查: $NGX_TEST"
fi

# 2.7 服务器 .venv Python
echo -n "  服务器 .venv Python: "
VENV_VER=$(ssh $SSH_OPTS "$SERVER" "$APP_DIR/.venv/bin/python --version 2>/dev/null || echo 'missing'" 2>/dev/null | tr -d '\r\n')
if [ "$VENV_VER" != "missing" ]; then
  pass ".venv Python 可用: $VENV_VER"
else
  fail ".venv Python 不可用 — 部署无法执行"
  exit 1
fi

echo ""

# ============================================================
# Phase 3: 服务可达性检查（从本地）
# ============================================================
echo "[Phase 3/3] HTTP 服务可达性"
echo "----------------------------"

check_http() {
  local url="$1"
  local label="$2"
  local expected="${3:-200}"
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "$url" 2>/dev/null || echo "000")
  if [ "$code" = "$expected" ]; then
    pass "$label → $code"
  else
    warn "$label → $code (期望 $expected)"
  fi
}

check_http "http://121.43.80.221/"               "首页 /"               "200"
check_http "http://121.43.80.221/api/health"      "API /api/health"      "200"
check_http "http://121.43.80.221/api/reports?type=daily&limit=1" "API /api/reports" "200"

echo ""
echo "=============================================="
echo " Preflight 完成"
echo "=============================================="
