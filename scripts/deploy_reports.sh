#!/bin/bash
# ============================================================
# deploy_reports.sh — 报告内容部署
# 上传 reports/*.md 和 reports/*.html，然后重生成 Dashboard
# 用法:
#   bash scripts/deploy_reports.sh                    # 部署所有报告
#   bash scripts/deploy_reports.sh 2026-07-06.md      # 只部署指定报告
#   bash scripts/deploy_reports.sh --md-only           # 只上传 .md 报告
# ============================================================
set -euo pipefail

SERVER="admin@121.43.80.221"
APP_DIR="/home/admin/app"
SSH_OPTS="-o ConnectTimeout=10 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

# --- 颜色 ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
log_pass()  { echo -e "${GREEN}[PASS]${NC}  $1"; }
log_fail()  { echo -e "${RED}[FAIL]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_step()  { echo -e "\n${CYAN}>>>${NC} $1"; }

# --- 项目根目录 ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPORTS_DIR="$PROJECT_DIR/reports"

cd "$PROJECT_DIR"

echo ""
echo "=============================================="
echo " Deploy Reports — $(date '+%Y-%m-%d %H:%M:%S')"
echo "=============================================="
echo ""

# ============================================================
# 确定要上传的文件
# ============================================================

MD_ONLY=false
MD_FILES=()
HTML_FILES=()

if [ $# -eq 0 ]; then
  # 无参数：所有报告
  log_info "未指定文件，收集所有 reports/*.md + reports/*.html ..."
  while IFS= read -r -d '' f; do
    MD_FILES+=("$f")
  done < <(find "$REPORTS_DIR" -maxdepth 1 -name "*.md" -type f -print0 2>/dev/null || true)
  while IFS= read -r -d '' f; do
    HTML_FILES+=("$f")
  done < <(find "$REPORTS_DIR" -maxdepth 1 -name "*.html" -type f -print0 2>/dev/null || true)
elif [ "$1" = "--md-only" ]; then
  MD_ONLY=true
  log_info "--md-only 模式：只上传 .md 报告"
  while IFS= read -r -d '' f; do
    MD_FILES+=("$f")
  done < <(find "$REPORTS_DIR" -maxdepth 1 -name "*.md" -type f -print0 2>/dev/null || true)
else
  for arg in "$@"; do
    if [ -f "$REPORTS_DIR/$arg" ]; then
      case "$arg" in
        *.md)   MD_FILES+=("$REPORTS_DIR/$arg") ;;
        *.html) HTML_FILES+=("$REPORTS_DIR/$arg") ;;
        *)      log_warn "$arg — 非 .md/.html 文件，跳过" ;;
      esac
    else
      log_fail "reports/$arg — 文件不存在"
      exit 1
    fi
  done
fi

log_info ".md 文件: ${#MD_FILES[@]} 个"
log_info ".html 文件: ${#HTML_FILES[@]} 个"

TOTAL_FILES=$((${#MD_FILES[@]} + ${#HTML_FILES[@]}))
if [ "$TOTAL_FILES" -eq 0 ]; then
  log_warn "没有需要上传的报告文件"
  exit 0
fi

# ============================================================
# Step 1: 创建远程目录（如需要）
# ============================================================
log_step "Step 1: 确保服务器 reports 目录存在"

ssh $SSH_OPTS "$SERVER" "mkdir -p $APP_DIR/reports" 2>/dev/null && \
  log_pass "reports 目录就绪" || log_fail "无法创建 reports 目录"

# ============================================================
# Step 2: 上传 .md 报告
# ============================================================
if [ ${#MD_FILES[@]} -gt 0 ]; then
  log_step "Step 2: 上传 .md 报告 (${#MD_FILES[@]} 个)"

  MD_OK=0
  MD_FAIL=0
  for f in "${MD_FILES[@]}"; do
    REL_NAME=$(basename "$f")
    log_info "上传: $REL_NAME"
    if scp -q "$f" "$SERVER:$APP_DIR/reports/" 2>/dev/null; then
      # md5 验证
      LOCAL_MD5=$(md5sum "$f" 2>/dev/null | awk '{print $1}')
      REMOTE_MD5=$(ssh $SSH_OPTS "$SERVER" "md5sum $APP_DIR/reports/$REL_NAME 2>/dev/null | awk '{print \$1}'" 2>/dev/null)
      if [ "$LOCAL_MD5" = "$REMOTE_MD5" ]; then
        log_pass "$REL_NAME → md5 一致"
        MD_OK=$((MD_OK + 1))
      else
        log_fail "$REL_NAME → md5 不一致! 本地=$LOCAL_MD5 服务器=$REMOTE_MD5"
        MD_FAIL=$((MD_FAIL + 1))
      fi
    else
      log_fail "$REL_NAME → scp 失败"
      MD_FAIL=$((MD_FAIL + 1))
    fi
  done
  log_info ".md 上传: $MD_OK 成功 / $MD_FAIL 失败"

  if [ "$MD_FAIL" -gt 0 ]; then
    log_fail ".md 上传有 $MD_FAIL 个失败，终止"
    exit 1
  fi
fi

# ============================================================
# Step 3: 上传 .html 报告
# ============================================================
if [ ${#HTML_FILES[@]} -gt 0 ]; then
  log_step "Step 3: 上传 .html 报告 (${#HTML_FILES[@]} 个)"

  HTML_OK=0
  HTML_FAIL=0
  for f in "${HTML_FILES[@]}"; do
    REL_NAME=$(basename "$f")
    log_info "上传: $REL_NAME"
    if scp -q "$f" "$SERVER:$APP_DIR/reports/" 2>/dev/null; then
      LOCAL_MD5=$(md5sum "$f" 2>/dev/null | awk '{print $1}')
      REMOTE_MD5=$(ssh $SSH_OPTS "$SERVER" "md5sum $APP_DIR/reports/$REL_NAME 2>/dev/null | awk '{print \$1}'" 2>/dev/null)
      if [ "$LOCAL_MD5" = "$REMOTE_MD5" ]; then
        log_pass "$REL_NAME → md5 一致"
        HTML_OK=$((HTML_OK + 1))
      else
        log_fail "$REL_NAME → md5 不一致!"
        HTML_FAIL=$((HTML_FAIL + 1))
      fi
    else
      log_fail "$REL_NAME → scp 失败"
      HTML_FAIL=$((HTML_FAIL + 1))
    fi
  done
  log_info ".html 上传: $HTML_OK 成功 / $HTML_FAIL 失败"
fi

# ============================================================
# Step 4: 重生成 Dashboard（报告变更后更新首页）
# ============================================================
log_step "Step 4: 重生成 Dashboard"

if ssh $SSH_OPTS "$SERVER" "cd $APP_DIR && $APP_DIR/.venv/bin/python pipeline.py --dashboard" 2>&1; then
  log_pass "Dashboard 重生成完成"
else
  log_warn "Dashboard 重生成失败 — 报告已上传但首页可能未更新"
fi

# ============================================================
# Step 5: Nginx reload
# ============================================================
log_step "Step 5: Nginx reload"

NGX_TEST=$(ssh $SSH_OPTS "$SERVER" "sudo nginx -t 2>&1" 2>/dev/null || true)
if echo "$NGX_TEST" | grep -q "successful"; then
  ssh $SSH_OPTS "$SERVER" "sudo nginx -s reload" 2>/dev/null && \
    log_pass "Nginx reload 成功" || log_warn "Nginx reload 失败"
else
  log_warn "Nginx 语法错误，跳过 reload"
fi

# ============================================================
# Step 6: 写入部署日志
# ============================================================
log_step "Step 6: 写入部署日志"

GIT_REF=$(cd "$PROJECT_DIR" && git rev-parse --short HEAD 2>/dev/null || echo "no-git")
ssh $SSH_OPTS "$SERVER" "echo \"\$(date -Iseconds) | deploy_reports.sh | md:${#MD_FILES[@]} html:${#HTML_FILES[@]} | git: $GIT_REF\" >> $APP_DIR/deploy_history.log" 2>/dev/null && \
  log_pass "部署日志已写入" || log_warn "日志写入失败"

# ============================================================
# 完成
# ============================================================
echo ""
echo "=============================================="
echo " Deploy Reports 完成"
echo " .md:  ${#MD_FILES[@]} 个"
echo " .html: ${#HTML_FILES[@]} 个"
echo "=============================================="
echo ""
echo "下一步: bash scripts/verify_server.sh"
