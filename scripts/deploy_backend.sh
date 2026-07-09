#!/bin/bash
# ============================================================
# deploy_backend.sh — 后端文件部署（API / Engine / Pipeline）
# 用法:
#   bash scripts/deploy_backend.sh                     # 部署所有后端文件
#   bash scripts/deploy_backend.sh api.py              # 只部署指定文件
#   bash scripts/deploy_backend.sh src/api/api.py src/engine/reporter.py
#   bash scripts/deploy_backend.sh --no-restart         # 部署但不重启服务
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
# 参数解析
# ============================================================
NO_RESTART=false
RAW_ARGS=()

for arg in "$@"; do
  case "$arg" in
    --no-restart) NO_RESTART=true ;;
    *) RAW_ARGS+=("$arg") ;;
  esac
done

# ============================================================
# 文件 → 服务器目标路径映射
# ============================================================
declare -A FILE_TARGET
FILE_TARGET["src/api/api.py"]="src/api/"
FILE_TARGET["src/api/auth.py"]="src/api/"
FILE_TARGET["src/api/middleware.py"]="src/api/"
FILE_TARGET["src/engine/ai_client.py"]="src/engine/"
FILE_TARGET["src/engine/cache.py"]="src/engine/"
FILE_TARGET["src/engine/card_writer.py"]="src/engine/"
FILE_TARGET["src/engine/classifier.py"]="src/engine/"
FILE_TARGET["src/engine/concept_agent.py"]="src/engine/"
FILE_TARGET["src/engine/concept_miner.py"]="src/engine/"
FILE_TARGET["src/engine/database.py"]="src/engine/"
FILE_TARGET["src/engine/db_articles.py"]="src/engine/"
FILE_TARGET["src/engine/db_core.py"]="src/engine/"
FILE_TARGET["src/engine/db_entities.py"]="src/engine/"
FILE_TARGET["src/engine/db_migrations.py"]="src/engine/"
FILE_TARGET["src/engine/db_pipeline.py"]="src/engine/"
FILE_TARGET["src/engine/db_queries.py"]="src/engine/"
FILE_TARGET["src/engine/db_relationships.py"]="src/engine/"
FILE_TARGET["src/engine/dedup.py"]="src/engine/"
FILE_TARGET["src/engine/embeddings.py"]="src/engine/"
FILE_TARGET["src/engine/fetcher.py"]="src/engine/"
FILE_TARGET["src/engine/kg_data.py"]="src/engine/"
FILE_TARGET["src/engine/kg_mermaid.py"]="src/engine/"
FILE_TARGET["src/engine/knowledge.py"]="src/engine/"
FILE_TARGET["src/engine/provenance.py"]="src/engine/"
FILE_TARGET["src/engine/reporter.py"]="src/engine/"
FILE_TARGET["src/engine/research_agent.py"]="src/engine/"
FILE_TARGET["src/engine/research_engine.py"]="src/engine/"
FILE_TARGET["src/engine/scorer.py"]="src/engine/"
FILE_TARGET["src/engine/summarizer.py"]="src/engine/"
FILE_TARGET["src/engine/sync_cards.py"]="src/engine/"
FILE_TARGET["src/engine/trend_agent.py"]="src/engine/"
FILE_TARGET["src/engine/trend_reporter.py"]="src/engine/"
FILE_TARGET["src/engine/utils.py"]="src/engine/"
FILE_TARGET["src/interfaces/schemas.py"]="src/interfaces/"
FILE_TARGET["src/knowledge_graph.py"]="src/"
FILE_TARGET["src/research.py"]="src/"
FILE_TARGET["src/timeline.py"]="src/"
FILE_TARGET["src/plugins/twitter.py"]="src/plugins/"
FILE_TARGET["pipeline.py"]=""
FILE_TARGET["pipeline_stages.py"]=""

# ============================================================
# 确定部署文件
# ============================================================
if [ ${#RAW_ARGS[@]} -eq 0 ]; then
  # 无参数：所有后端文件
  FILES=(
    "src/api/api.py"
    "src/api/auth.py"
    "src/api/middleware.py"
    "src/engine/ai_client.py"
    "src/engine/cache.py"
    "src/engine/card_writer.py"
    "src/engine/classifier.py"
    "src/engine/concept_agent.py"
    "src/engine/concept_miner.py"
    "src/engine/database.py"
    "src/engine/db_articles.py"
    "src/engine/db_core.py"
    "src/engine/db_entities.py"
    "src/engine/db_migrations.py"
    "src/engine/db_pipeline.py"
    "src/engine/db_queries.py"
    "src/engine/db_relationships.py"
    "src/engine/dedup.py"
    "src/engine/embeddings.py"
    "src/engine/fetcher.py"
    "src/engine/kg_data.py"
    "src/engine/kg_mermaid.py"
    "src/engine/knowledge.py"
    "src/engine/provenance.py"
    "src/engine/reporter.py"
    "src/engine/research_agent.py"
    "src/engine/research_engine.py"
    "src/engine/scorer.py"
    "src/engine/summarizer.py"
    "src/engine/sync_cards.py"
    "src/engine/trend_agent.py"
    "src/engine/trend_reporter.py"
    "src/engine/utils.py"
    "src/interfaces/schemas.py"
    "src/knowledge_graph.py"
    "src/research.py"
    "src/timeline.py"
    "src/plugins/twitter.py"
    "pipeline.py"
    "pipeline_stages.py"
  )
  log_info "未指定文件，部署全部 ${#FILES[@]} 个后端文件"
else
  FILES=()
  for arg in "${RAW_ARGS[@]}"; do
    if [[ "$arg" == src/* ]] || [[ "$arg" == pipeline* ]]; then
      if [ -f "$PROJECT_DIR/$arg" ]; then
        FILES+=("$arg")
      else
        log_fail "找不到文件: $arg"
        exit 1
      fi
    else
      # 短名匹配
      MATCHED=$(find src/ . -maxdepth 3 -name "$arg" -type f 2>/dev/null | head -1)
      if [ -n "$MATCHED" ]; then
        FILES+=("${MATCHED#./}")
      else
        log_fail "找不到文件: $arg"
        exit 1
      fi
    fi
  done
fi

# 去重
FILES=($(printf '%s\n' "${FILES[@]}" | sort -u))

echo ""
echo "=============================================="
echo " Deploy Backend — $(date '+%Y-%m-%d %H:%M:%S')"
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
AFFECTS_API=false
AFFECTS_ENGINE=false
AFFECTS_PIPELINE=false

for f in "${FILES[@]}"; do
  TARGET_DIR="${FILE_TARGET[$f]:-}"
  if [ -z "$TARGET_DIR" ] && [ "$TARGET_DIR" != "" ]; then
    log_fail "$f — 未配置目标路径，跳过"
    UPLOAD_OK=false
    continue
  fi

  LOCAL_PATH="$PROJECT_DIR/$f"

  # 上传到服务器对应路径
  if [ "$TARGET_DIR" = "" ]; then
    # 根目录文件（如 pipeline.py），目标为 APP_DIR/
    REMOTE_FULL="$APP_DIR/$f"
    SCP_DEST="$SERVER:$APP_DIR/"
  else
    REMOTE_FULL="$APP_DIR/$f"
    SCP_DEST="$SERVER:$APP_DIR/$TARGET_DIR"
  fi

  log_info "上传: $f → $SCP_DEST"
  if scp -q "$LOCAL_PATH" "$SCP_DEST" 2>/dev/null; then
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

  # 标记影响范围
  case "$f" in
    src/api/*)            AFFECTS_API=true ;;
    src/engine/*)         AFFECTS_ENGINE=true ;;
    pipeline.py|pipeline_stages.py) AFFECTS_PIPELINE=true ;;
    src/interfaces/*)     AFFECTS_API=true ;;  # schemas 影响 API
  esac
done

if [ "$UPLOAD_OK" = false ]; then
  echo ""
  log_fail "上传验证未通过，终止部署。"
  exit 1
fi

# ============================================================
# Step 4: 清除 __pycache__（服务器）
# ============================================================
log_step "Step 4: 清除服务器 __pycache__"

ssh $SSH_OPTS "$SERVER" "
  find $APP_DIR -type f -name '*.pyc' -delete 2>/dev/null || true
  find $APP_DIR -type d -name '__pycache__' -empty -delete 2>/dev/null || true
  echo 'cache cleared'
" 2>/dev/null && log_pass "缓存已清除" || log_warn "缓存清除部分失败"

# ============================================================
# Step 5: 重启 ai-news 服务（L2 操作）
# ============================================================
log_step "Step 5: 重启 ai-news 服务"

if [ "$NO_RESTART" = true ]; then
  log_warn "--no-restart 已指定，跳过服务重启"
  log_warn "注意：新代码不会生效，直到手动重启服务！"
else
  # 先检查服务状态
  SVC_STATUS=$(ssh $SSH_OPTS "$SERVER" "systemctl is-active ai-news 2>/dev/null || echo 'unknown'" 2>/dev/null | tr -d '\r\n')

  if [ "$SVC_STATUS" = "unknown" ]; then
    log_warn "ai-news 服务未配置 systemd，跳过重启"
    log_info "如需重启，请手动操作 uvicorn 进程"
  else
    log_info "当前服务状态: $SVC_STATUS"
    log_info "正在重启 ai-news ..."

    if ssh $SSH_OPTS "$SERVER" "sudo systemctl restart ai-news" 2>/dev/null; then
      # 等待服务启动
      sleep 2
      NEW_STATUS=$(ssh $SSH_OPTS "$SERVER" "systemctl is-active ai-news 2>/dev/null || echo 'inactive'" 2>/dev/null | tr -d '\r\n')
      if [ "$NEW_STATUS" = "active" ]; then
        log_pass "ai-news 重启成功 → $NEW_STATUS"
      else
        log_warn "ai-news 重启后状态: $NEW_STATUS — 请检查日志"
      fi
    else
      log_fail "ai-news 重启失败！"
      log_info "请手动检查: ssh $SERVER 'sudo journalctl -u ai-news -n 50 --no-pager'"
    fi
  fi
fi

# ============================================================
# Step 6: 快速冒烟（API health）
# ============================================================
log_step "Step 6: API 冒烟检查"

sleep 1  # 给服务一点启动时间

HEALTH_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "http://121.43.80.221/api/health" 2>/dev/null || echo "000")
if [ "$HEALTH_CODE" = "200" ]; then
  log_pass "/api/health → 200"
else
  log_fail "/api/health → $HEALTH_CODE（服务可能未完全启动）"
fi

# ============================================================
# Step 7: 写入部署日志
# ============================================================
log_step "Step 7: 写入部署日志"

FILE_LIST=$(printf '%s, ' "${FILES[@]}" | sed 's/, $//')
GIT_REF=$(cd "$PROJECT_DIR" && git rev-parse --short HEAD 2>/dev/null || echo "no-git")

ssh $SSH_OPTS "$SERVER" "echo \"\$(date -Iseconds) | deploy_backend.sh | files: $FILE_LIST | git: $GIT_REF | restart: $([ "$NO_RESTART" = true ] && echo 'skipped' || echo 'yes')\" >> $APP_DIR/deploy_history.log" 2>/dev/null && \
  log_pass "部署日志已写入" || log_warn "日志写入失败"

# ============================================================
# 完成
# ============================================================
echo ""
echo "=============================================="
echo " Deploy Backend 完成"
echo " 上传:   ${#FILES[@]} 个文件"
echo " 备份:   $BACKUP_COUNT 个文件"
echo " 重启:   $([ "$NO_RESTART" = true ] && echo '跳过' || echo '已重启')"
echo " 影响:   API=$AFFECTS_API | Engine=$AFFECTS_ENGINE | Pipeline=$AFFECTS_PIPELINE"
echo "=============================================="
echo ""

if [ "$AFFECTS_PIPELINE" = true ] || [ "$AFFECTS_ENGINE" = true ]; then
  echo -e "${YELLOW}注意: Engine/Pipeline 文件已变更，建议重跑 pipeline 更新数据:${NC}"
  echo "  ssh $SERVER 'cd $APP_DIR && $APP_DIR/.venv/bin/python pipeline.py'"
  echo ""
fi

echo "下一步: bash scripts/verify_server.sh"
