#!/bin/bash
# ============================================================
# deploy_frontend.sh — 前端文件部署
# 用法:
#   bash scripts/deploy_frontend.sh                    # 部署所有前端文件
#   bash scripts/deploy_frontend.sh dashboard.py       # 只部署指定文件
#   bash scripts/deploy_frontend.sh dashboard.py i18n.py
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

cd "$PROJECT_DIR"

# ============================================================
# 确定要部署的文件
# ============================================================

# 文件 → 服务器目标路径 + 重生成命令 映射
declare -A FILE_TARGET
FILE_TARGET["src/frontend/dashboard.py"]="src/frontend/"
FILE_TARGET["src/frontend/report_reader.py"]="src/frontend/"
FILE_TARGET["src/frontend/my_page.py"]="src/frontend/"
FILE_TARGET["src/frontend/frontend_styles.py"]="src/frontend/"
FILE_TARGET["src/frontend/timeline_renderer.py"]="src/frontend/"
FILE_TARGET["src/frontend/timeline_data.py"]="src/frontend/"
FILE_TARGET["src/interfaces/i18n.py"]="src/interfaces/"

# 确定哪些文件需要重生成
NEEDS_DASHBOARD=false
NEEDS_REPORT_READER=false
NEEDS_MY_PAGE=false
NEEDS_TIMELINE=false

mark_regeneration() {
  local f="$1"
  case "$f" in
    *dashboard.py)         NEEDS_DASHBOARD=true ;;
    *report_reader.py)     NEEDS_REPORT_READER=true ;;
    *my_page.py)           NEEDS_MY_PAGE=true ;;
    *frontend_styles.py)   NEEDS_DASHBOARD=true; NEEDS_REPORT_READER=true; NEEDS_MY_PAGE=true ;;
    *i18n.py)              NEEDS_DASHBOARD=true; NEEDS_REPORT_READER=true; NEEDS_MY_PAGE=true ;;
    *timeline_renderer.py) NEEDS_TIMELINE=true ;;
    *timeline_data.py)     NEEDS_TIMELINE=true ;;
  esac
}

if [ $# -eq 0 ]; then
  # 无参数：部署所有前端文件
  FILES=(
    "src/frontend/dashboard.py"
    "src/frontend/report_reader.py"
    "src/frontend/my_page.py"
    "src/frontend/frontend_styles.py"
    "src/interfaces/i18n.py"
  )
  log_info "未指定文件，部署全部 ${#FILES[@]} 个前端文件"
else
  FILES=()
  for arg in "$@"; do
    # 支持短名（如 dashboard.py）和完整相对路径
    if [[ "$arg" == src/* ]]; then
      FILES+=("$arg")
    else
      # 尝试匹配
      MATCHED=$(find src/ -name "$arg" -type f 2>/dev/null | head -1)
      if [ -n "$MATCHED" ]; then
        FILES+=("$MATCHED")
      else
        log_fail "找不到文件: $arg"
        exit 1
      fi
    fi
  done
fi

echo ""
echo "=============================================="
echo " Deploy Frontend — $(date '+%Y-%m-%d %H:%M:%S')"
echo "=============================================="
echo ""

# ============================================================
# Step 1: Python 语法检查（本地）
# ============================================================
log_step "Step 1: Python 语法检查"

PYTHON=$(command -v python || command -v python3)
log_info "使用: $PYTHON"

SYNTAX_OK=true
for f in "${FILES[@]}"; do
  if [ ! -f "$PROJECT_DIR/$f" ]; then
    log_fail "$f — 本地文件不存在"
    SYNTAX_OK=false
    continue
  fi
  if $PYTHON -m py_compile "$PROJECT_DIR/$f" 2>&1; then
    log_pass "$f 语法正确"
  else
    log_fail "$f 语法错误"
    SYNTAX_OK=false
  fi
done

if [ "$SYNTAX_OK" = false ]; then
  echo ""
  log_fail "语法检查未通过，终止部署。"
  exit 1
fi

# ============================================================
# Step 2: 上传前备份（服务器）
# ============================================================
log_step "Step 2: 服务器备份"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_COUNT=0

for f in "${FILES[@]}"; do
  REMOTE_PATH="$APP_DIR/$f"
  BACKUP_PATH="${REMOTE_PATH}.bak.${TIMESTAMP}"
  # 检查远程文件是否存在
  if ssh $SSH_OPTS "$SERVER" "test -f $REMOTE_PATH" 2>/dev/null; then
    ssh $SSH_OPTS "$SERVER" "cp $REMOTE_PATH $BACKUP_PATH" 2>/dev/null && {
      log_pass "备份: $f → $(basename "$BACKUP_PATH")"
      BACKUP_COUNT=$((BACKUP_COUNT + 1))
    } || {
      log_warn "备份失败: $f（继续上传）"
    }
  else
    log_info "$f — 服务器上不存在，跳过备份（新文件）"
  fi
done
log_info "共备份 $BACKUP_COUNT 个文件"

# ============================================================
# Step 3: 逐文件上传 + md5 验证
# ============================================================
log_step "Step 3: 上传 + md5 验证"

UPLOAD_OK=true

for f in "${FILES[@]}"; do
  TARGET_DIR="${FILE_TARGET[$f]:-}"
  if [ -z "$TARGET_DIR" ]; then
    log_fail "$f — 未配置目标路径，跳过"
    UPLOAD_OK=false
    continue
  fi

  LOCAL_PATH="$PROJECT_DIR/$f"
  REMOTE_FULL="$APP_DIR/$f"

  # 上传
  log_info "上传: $f → $SERVER:$APP_DIR/$TARGET_DIR"
  if scp -q "$LOCAL_PATH" "$SERVER:$APP_DIR/$TARGET_DIR" 2>/dev/null; then
    log_pass "scp 完成: $f"
  else
    log_fail "scp 失败: $f"
    UPLOAD_OK=false
    continue
  fi

  # md5 验证
  LOCAL_MD5=$(md5sum "$LOCAL_PATH" 2>/dev/null | awk '{print $1}' || echo "unknown")
  REMOTE_MD5=$(ssh $SSH_OPTS "$SERVER" "md5sum $REMOTE_FULL 2>/dev/null | awk '{print \$1}' || echo 'missing'")

  if [ "$LOCAL_MD5" = "$REMOTE_MD5" ]; then
    log_pass "md5 一致: $LOCAL_MD5"
  else
    log_fail "md5 不一致! 本地=$LOCAL_MD5 服务器=$REMOTE_MD5"
    UPLOAD_OK=false
  fi

  # 标记需要重生成
  mark_regeneration "$f"
done

if [ "$UPLOAD_OK" = false ]; then
  echo ""
  log_fail "上传验证未通过，终止部署。请检查网络后重试。"
  exit 1
fi

# ============================================================
# Step 4: 服务器重生成 HTML
# ============================================================
log_step "Step 4: 重生成 HTML"

REGEN_CMDS=()

if [ "$NEEDS_MY_PAGE" = true ]; then
  REGEN_CMDS+=("cd $APP_DIR && $APP_DIR/.venv/bin/python -c 'from src.frontend.my_page import generate_my_page; print(f\"my.html → {generate_my_page()}\")'")
fi
if [ "$NEEDS_REPORT_READER" = true ]; then
  REGEN_CMDS+=("cd $APP_DIR && $APP_DIR/.venv/bin/python -c 'from src.frontend.report_reader import generate_report_reader; print(f\"report-reader.html → {generate_report_reader()}\")'")
fi
if [ "$NEEDS_DASHBOARD" = true ]; then
  REGEN_CMDS+=("cd $APP_DIR && $APP_DIR/.venv/bin/python pipeline.py --dashboard")
fi
if [ "$NEEDS_TIMELINE" = true ]; then
  REGEN_CMDS+=("cd $APP_DIR && $APP_DIR/.venv/bin/python pipeline.py --timeline")
fi

if [ ${#REGEN_CMDS[@]} -eq 0 ]; then
  log_info "无需重生成 HTML"
else
  for cmd in "${REGEN_CMDS[@]}"; do
    log_info "执行: $cmd"
    if ssh $SSH_OPTS "$SERVER" "$cmd" 2>&1; then
      log_pass "重生成完成"
    else
      log_fail "重生成失败"
      UPLOAD_OK=false
    fi
  done
fi

# ============================================================
# Step 5: 清除 __pycache__（服务器）
# ============================================================
log_step "Step 5: 清除服务器 __pycache__"

# 只清除 .pyc 文件，不删目录（避免 rm -rf）
ssh $SSH_OPTS "$SERVER" "
  find $APP_DIR -type f -name '*.pyc' -delete 2>/dev/null || true
  find $APP_DIR -type d -name '__pycache__' -empty -delete 2>/dev/null || true
  echo 'cache cleared'
" 2>/dev/null && log_pass "缓存已清除" || log_warn "缓存清除部分失败（不影响部署）"

# ============================================================
# Step 6: Nginx reload
# ============================================================
log_step "Step 6: Nginx reload"

NGX_TEST=$(ssh $SSH_OPTS "$SERVER" "sudo nginx -t 2>&1" 2>/dev/null || true)
if echo "$NGX_TEST" | grep -q "successful"; then
  if ssh $SSH_OPTS "$SERVER" "sudo nginx -s reload" 2>/dev/null; then
    log_pass "Nginx reload 成功"
  else
    log_warn "Nginx reload 失败 — 请手动检查"
  fi
else
  log_warn "Nginx 配置语法错误，跳过 reload"
  echo "  $NGX_TEST"
fi

# ============================================================
# Step 7: 写入部署日志
# ============================================================
log_step "Step 7: 写入部署日志"

FILE_LIST=$(printf '%s, ' "${FILES[@]}" | sed 's/, $//')
GIT_REF=$(cd "$PROJECT_DIR" && git rev-parse --short HEAD 2>/dev/null || echo "no-git")

ssh $SSH_OPTS "$SERVER" "echo \"\$(date -Iseconds) | deploy_frontend.sh | files: $FILE_LIST | git: $GIT_REF\" >> $APP_DIR/deploy_history.log" 2>/dev/null && \
  log_pass "部署日志已写入" || log_warn "部署日志写入失败（不影响部署）"

# ============================================================
# 完成
# ============================================================
echo ""
echo "=============================================="
echo " Deploy Frontend 完成"
echo " 上传: ${#FILES[@]} 个文件"
echo " 备份: $BACKUP_COUNT 个文件"
echo " 重生成: Dashboard=$NEEDS_DASHBOARD | ReportReader=$NEEDS_REPORT_READER | MyPage=$NEEDS_MY_PAGE | Timeline=$NEEDS_TIMELINE"
echo "=============================================="
echo ""
echo "下一步: bash scripts/verify_server.sh"
