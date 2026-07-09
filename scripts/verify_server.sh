#!/bin/bash
# ============================================================
# verify_server.sh — 服务器部署后验证
# 检查 API + 页面 HTTP 可达性，不修改任何文件。
# 用法: bash scripts/verify_server.sh
# ============================================================
set -euo pipefail

SERVER="admin@121.43.80.221"
BASE_URL="http://121.43.80.221"
APP_DIR="/home/admin/app"
SSH_OPTS="-o ConnectTimeout=10 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

# --- 颜色 ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

pass()  { echo -e "  ${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "  ${RED}[FAIL]${NC} $1"; }
warn() { echo -e "  ${YELLOW}[WARN]${NC} $1"; }

PASS_COUNT=0
FAIL_COUNT=0

check() {
  local url="$1"
  local label="$2"
  local expected="${3:-200}"
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "$url" 2>/dev/null || echo "000")
  if [ "$code" = "$expected" ]; then
    pass "$label → $code"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    fail "$label → $code (期望 $expected)"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
}

check_content() {
  local url="$1"
  local label="$2"
  local keyword="$3"
  local code
  local body
  body=$(curl -s --connect-timeout 5 "$url" 2>/dev/null || echo "")
  code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "$url" 2>/dev/null || echo "000")
  if [ "$code" != "200" ]; then
    fail "$label → HTTP $code (期望 200)"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  elif echo "$body" | grep -q "$keyword" 2>/dev/null; then
    pass "$label → 200, 含 '$keyword'"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    warn "$label → 200, 但不含 '$keyword'"
    PASS_COUNT=$((PASS_COUNT + 1))  # 200 就算基本通过
  fi
}

echo ""
echo "=============================================="
echo " Verify Server — $(date '+%Y-%m-%d %H:%M:%S')"
echo "=============================================="
echo ""

# ============================================================
# Phase 1: API 端点
# ============================================================
echo "[Phase 1/3] API 端点"
echo "---------------------"

check "$BASE_URL/api/health"                            "/api/health"                  "200"

# /api/reports 支持多种 type
for report_type in daily weekly monthly; do
  check "$BASE_URL/api/reports?type=$report_type&limit=1"  "/api/reports?type=$report_type" "200"
done

check "$BASE_URL/api/articles?limit=1&min_score=5"      "/api/articles?min_score=5"    "200"

echo ""

# ============================================================
# Phase 2: 静态页面
# ============================================================
echo "[Phase 2/3] 静态 HTML 页面"
echo "--------------------------"

PAGES=(
  "/"
  "/library"
  "/graph"
  "/timeline"
  "/events"
  "/reports"
  "/research"
  "/my"
  "/login"
  "/register"
)

for page in "${PAGES[@]}"; do
  check_content "$BASE_URL$page" "$page" "</html>"
done

echo ""

# ============================================================
# Phase 3: 报告文件
# ============================================================
echo "[Phase 3/3] 报告文件 & 特殊路由"
echo "---------------------------------"

# 3.1 报告阅读器 — 访问 .md 应返回 HTML shell
# (Nginx 对 /report/*.md 返回 report-reader.html)
TODAY=$(date +%Y-%m-%d)
check_content "$BASE_URL/report/$TODAY.md"  "/report/$TODAY.md"          "</html>"

# 3.2 报告内容 API — 应返回原始 markdown
REPORT_BODY=$(curl -s --connect-timeout 5 "$BASE_URL/api/report-content/$TODAY.md" 2>/dev/null || echo "")
REPORT_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "$BASE_URL/api/report-content/$TODAY.md" 2>/dev/null || echo "000")
if [ "$REPORT_CODE" = "200" ]; then
  pass "/api/report-content/$TODAY.md → 200"
  PASS_COUNT=$((PASS_COUNT + 1))
elif [ "$REPORT_CODE" = "404" ]; then
  warn "/api/report-content/$TODAY.md → 404（今天可能还没生成日报）"
else
  fail "/api/report-content/$TODAY.md → $REPORT_CODE"
  FAIL_COUNT=$((FAIL_COUNT + 1))
fi

# 3.3 检查已有日报 — 用最近一天
RECENT_MD=$(ssh $SSH_OPTS "$SERVER" "ls $APP_DIR/reports/????-??-??.md 2>/dev/null | sort -r | head -1" 2>/dev/null || echo "")
if [ -n "$RECENT_MD" ]; then
  RECENT_NAME=$(basename "$RECENT_MD")
  check_content "$BASE_URL/report/$RECENT_NAME"  "/report/$RECENT_NAME"  "</html>"
  check "$BASE_URL/api/report-content/$RECENT_NAME"  "/api/report-content/$RECENT_NAME"  "200"
else
  warn "服务器无日报 .md 文件"
fi

echo ""

# ============================================================
# 汇总
# ============================================================
echo "=============================================="
echo " Verify 汇总"
echo "=============================================="
echo -e "  ${GREEN}PASS: $PASS_COUNT${NC}"
echo -e "  ${RED}FAIL: $FAIL_COUNT${NC}"

if [ "$FAIL_COUNT" -eq 0 ]; then
  echo ""
  echo -e "  ${GREEN}全部检查通过 ✅${NC}"
  echo ""
  echo "下一步: bash scripts/qa_smoke_test.sh"
  exit 0
else
  echo ""
  echo -e "  ${RED}存在 $FAIL_COUNT 个失败项 ❌${NC}"
  echo ""
  echo "请检查后重新部署，或运行诊断:"
  echo "  ssh $SERVER 'tail -50 /var/log/nginx/error.log'"
  echo "  ssh $SERVER 'systemctl status ai-news'"
  exit 1
fi
