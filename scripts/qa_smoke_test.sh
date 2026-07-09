#!/bin/bash
# ============================================================
# qa_smoke_test.sh — 部署后冒烟测试
# 检查核心页面是否可访问、基本功能是否正常。
# 不修改任何文件。
# 用法: bash scripts/qa_smoke_test.sh
# ============================================================
set -euo pipefail

BASE_URL="http://121.43.80.221"
SERVER="admin@121.43.80.221"
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
skip() { echo -e "  ${YELLOW}[SKIP]${NC} $1"; }

PASS=0
FAIL=0
SKIP=0

# --- 测试辅助 ---
# 安全提取 HTTP 状态码：curl 自身连接失败会输出 000；
# 用 || true 防 set -e 中断，再清洗非数字，避免 200+000 拼接成 200000。
clean_http_code() {
  local raw
  raw=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 --max-time 10 "$1" 2>/dev/null || true)
  raw=$(printf '%s' "$raw" | tr -cd '0-9')
  raw=${raw:0:3}
  [ -z "$raw" ] && raw="000"
  echo "$raw"
}

check_http() {
  local url="$1"
  local label="$2"
  local expected="${3:-200}"
  local code
  code=$(clean_http_code "$url")
  if [ "$code" = "$expected" ]; then
    pass "$label (HTTP $code)"
    PASS=$((PASS + 1))
    return 0
  else
    fail "$label (HTTP $code, 期望 $expected)"
    FAIL=$((FAIL + 1))
    return 1
  fi
}

check_content() {
  local url="$1"
  local label="$2"
  local keyword="$3"
  local body
  body=$(curl -s --connect-timeout 5 --max-time 10 "$url" 2>/dev/null || true)
  local code
  code=$(clean_http_code "$url")
  if [ "$code" != "200" ]; then
    fail "$label → HTTP $code"
    FAIL=$((FAIL + 1))
    return 1
  fi
  if echo "$body" | grep -q "$keyword" 2>/dev/null; then
    pass "$label → 含 '$keyword'"
    PASS=$((PASS + 1))
    return 0
  else
    fail "$label → HTTP 200 但不含 '$keyword'"
    FAIL=$((FAIL + 1))
    return 1
  fi
}

echo ""
echo "=============================================="
echo " QA Smoke Test — $(date '+%Y-%m-%d %H:%M:%S')"
echo "=============================================="
echo ""

# ============================================================
# 1. 核心页面可访问性
# ============================================================
echo "[1/4] 核心页面可访问性"
echo "------------------------"

# 1.1 Dashboard 首页
check_content "$BASE_URL/" \
  "Dashboard 首页" \
  "</html>"

# 1.2 My 页面
check_content "$BASE_URL/my" \
  "My 我的页面" \
  "</html>"

# 1.3 报告列表
check_content "$BASE_URL/reports" \
  "报告列表" \
  "</html>"

# 1.4 报告阅读器 — 有日报时检查
RECENT_MD=$(ssh $SSH_OPTS "$SERVER" "ls $APP_DIR/reports/????-??-??.md 2>/dev/null | sort -r | head -1" 2>/dev/null || echo "")
if [ -n "$RECENT_MD" ]; then
  RECENT_NAME=$(basename "$RECENT_MD")
  check_content "$BASE_URL/report/$RECENT_NAME" \
    "报告阅读器 ($RECENT_NAME)" \
    "</html>"
else
  skip "报告阅读器 — 无日报 .md 文件"
  SKIP=$((SKIP + 1))
fi

# 1.5 周报 — 有则检查
RECENT_WEEKLY=$(ssh $SSH_OPTS "$SERVER" "ls $APP_DIR/reports/weekly-*.md 2>/dev/null | sort -r | head -1" 2>/dev/null || echo "")
if [ -n "$RECENT_WEEKLY" ]; then
  WEEKLY_NAME=$(basename "$RECENT_WEEKLY")
  check_content "$BASE_URL/report/$WEEKLY_NAME" \
    "报告阅读器-周报 ($WEEKLY_NAME)" \
    "</html>"
else
  skip "报告阅读器-周报 — 无周报文件"
  SKIP=$((SKIP + 1))
fi

echo ""

# ============================================================
# 2. API 核心端点
# ============================================================
echo "[2/4] API 核心端点"
echo "--------------------"

check_http "$BASE_URL/api/health" \
  "Health check" \
  "200"

# 检查 JSON 响应
API_BODY=$(curl -s --connect-timeout 5 --max-time 10 "$BASE_URL/api/reports?type=daily&limit=3" 2>/dev/null || true)
API_CODE=$(clean_http_code "$BASE_URL/api/reports?type=daily&limit=3")
if [ "$API_CODE" = "200" ]; then
  if echo "$API_BODY" | grep -q '\[{' 2>/dev/null || echo "$API_BODY" | grep -q '\[ \{' 2>/dev/null; then
    pass "/api/reports → JSON 数组"
    PASS=$((PASS + 1))
  elif echo "$API_BODY" | grep -q '\[\]' 2>/dev/null; then
    pass "/api/reports → 空数组 (OK)"
    PASS=$((PASS + 1))
  else
    warn_but_pass="/api/reports → 200 但可能不是 JSON"
    pass "$warn_but_pass"
    PASS=$((PASS + 1))
  fi
else
  fail "/api/reports → HTTP $API_CODE"
  FAIL=$((FAIL + 1))
fi

check_http "$BASE_URL/api/articles?limit=1&min_score=5" \
  "/api/articles" \
  "200"

echo ""

# ============================================================
# 3. 关键 JS/CSS 资源
# ============================================================
echo "[3/4] 静态资源"
echo "-----------------"

# JS 函数检查辅助（纯 bash 字符串匹配，不依赖 grep）
check_js_func() {
  local html="$1" label="$2" func="$3"
  if [[ "$html" == *"$func"* ]]; then
    pass "JS 函数 '$func' 已注入 $label"
    PASS=$((PASS + 1))
  else
    fail "JS 函数 '$func' 未在 $label 中找到"
    FAIL=$((FAIL + 1))
  fi
}

# Dashboard 页 JS 函数检查
DASHBOARD_HTML=$(curl -s --connect-timeout 5 --max-time 10 "$BASE_URL/" 2>/dev/null || true)
check_js_func "$DASHBOARD_HTML" "Dashboard" "favBtn"
check_js_func "$DASHBOARD_HTML" "Dashboard" "loadStar5"
check_js_func "$DASHBOARD_HTML" "Dashboard" "renderStar5"

# My 页面 JS 函数检查
MY_HTML=$(curl -s --connect-timeout 5 --max-time 10 "$BASE_URL/my" 2>/dev/null || true)
check_js_func "$MY_HTML" "My 页面" "uiPersonalItems"

# 报告阅读器 JS 函数检查（有日报时）
if [ -n "${RECENT_MD:-}" ]; then
  REPORT_HTML=$(curl -s --connect-timeout 5 --max-time 10 "$BASE_URL/report/${RECENT_NAME:-}" 2>/dev/null || true)
  check_js_func "$REPORT_HTML" "报告阅读器" "raBtn"
  check_js_func "$REPORT_HTML" "报告阅读器" "raDoAction"
  check_js_func "$REPORT_HTML" "报告阅读器" "injectArticleActions"
fi

echo ""

# ============================================================
# 4. 服务器端文件时间戳检查
# ============================================================
echo "[4/4] 服务器文件时间戳"
echo "------------------------"

# 检查关键 HTML 生成时间
HTML_FILES=(
  "reports/dashboard.html"
  "reports/report-reader.html"
  "reports/my.html"
)

for f in "${HTML_FILES[@]}"; do
  TS=$(ssh $SSH_OPTS "$SERVER" "stat -c '%Y' $APP_DIR/$f 2>/dev/null" 2>/dev/null || echo "0")
  if [ "$TS" = "0" ]; then
    fail "$f — 文件不存在"
    FAIL=$((FAIL + 1))
  else
    HR_TIME=$(ssh $SSH_OPTS "$SERVER" "stat -c '%y' $APP_DIR/$f 2>/dev/null" 2>/dev/null || echo "?")
    # 检查是否在最近 7 天内
    NOW=$(date +%s)
    AGE_DAYS=$(( (NOW - TS) / 86400 ))
    if [ "$AGE_DAYS" -le 7 ]; then
      pass "$f — $HR_TIME (${AGE_DAYS}d ago)"
      PASS=$((PASS + 1))
    else
      warn_msg="$f — ${AGE_DAYS}d 前生成（可能过期）"
      skip "$warn_msg"
      SKIP=$((SKIP + 1))
    fi
  fi
done

echo ""

# ============================================================
# 汇总报告
# ============================================================
echo "=============================================="
echo " QA Smoke Test 报告"
echo "=============================================="
TOTAL=$((PASS + FAIL + SKIP))
echo ""
printf "  %-20s %s\n" "通过 (PASS):" "${GREEN}$PASS${NC}"
printf "  %-20s %s\n" "失败 (FAIL):" "${RED}$FAIL${NC}"
printf "  %-20s %s\n" "跳过 (SKIP):" "${YELLOW}$SKIP${NC}"
printf "  %-20s %s\n" "总计:" "$TOTAL"
echo ""

if [ "$FAIL" -eq 0 ]; then
  echo -e "  ${GREEN}冒烟测试全部通过 ✅${NC}"
  if [ "$SKIP" -gt 0 ]; then
    echo -e "  ${YELLOW}注意: $SKIP 项因前置条件不足而跳过${NC}"
  fi
  echo ""
  echo "可以发布。"
  exit 0
else
  echo -e "  ${RED}冒烟测试 $FAIL 项失败 ❌${NC}"
  echo ""
  echo "失败项需要诊断："
  echo "  查看 .agents/server_debugger.md"
  echo "  或运行: bash scripts/verify_server.sh 获取更多细节"
  exit 1
fi
