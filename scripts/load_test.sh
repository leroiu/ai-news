#!/bin/bash
# ============================================================
# load_test.sh — 性能测试编排器
#
# 职责：
#   - 将触发词(轻压测/标准压测/…)映射到具体 PROFILE
#   - 根据测试等级实施确认门（未经确认的 profile 拒绝执行）
#   - 调用 k6 执行 load_test_k6.js
#   - 收集结果并生成 performance_report
#   - 压测后自动触发 qa_smoke_test.sh
#
# 用法：
#   bash scripts/load_test.sh <trigger-word>    # 交互式
#   bash scripts/load_test.sh <trigger-word> --yes  # 跳过确认
#
# 触发词 → PROFILE 映射：
#   轻压测  → smoke-load  (默认允许)
#   标准压测 → normal-load (需确认)
#   高峰压测 → peak-load   (需确认)
#   突刺测试 → spike-test  (需确认)
#   长稳测试 → soak-test   (需确认)
#   极限测试 → limit-test  (默认禁止，需二次确认)
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# k6 是 Windows 原生程序，不认 Git Bash 的 /c/xxx 路径。转成 Windows 格式供传参用。
K6_SCRIPT="$SCRIPT_DIR/load_test_k6.js"
if command -v cygpath &>/dev/null; then
  K6_SCRIPT="$(cygpath -w "$K6_SCRIPT")"
fi

# Git Bash (MSYS2) 会把参数里的裸 / 转成 Windows 路径，导致 k6 URL 拼错。
# 在脚本内部统一关闭路径转换，调用方无需再加前缀。
export MSYS2_ARG_CONV_EXCL='*'
export MSYS_NO_PATHCONV=1


# ============================================================
# 配置
# ============================================================
BASE_URL="http://121.43.80.221"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
RESULT_DIR="$PROJECT_DIR/output/loadtest"
mkdir -p "$RESULT_DIR"
SUMMARY_JSON="$RESULT_DIR/k6_summary_${TIMESTAMP}.json"
MONITOR_CSV="$RESULT_DIR/monitor_${TIMESTAMP}.csv"
# k6.exe 是 Windows 原生程序，路径必须转成 C:\xxx 格式
if command -v cygpath &>/dev/null; then
  SUMMARY_JSON="$(cygpath -w "$SUMMARY_JSON")"
fi

# 只读路径白名单（与 k6 脚本对齐，生产勿改）
STATIC_PATHS="/,/reports,/my"
API_PATHS="/api/health,/api/reports?type=daily&limit=5,/api/articles?limit=10&min_score=4"
# 报告阅读器路径（可选）：通过环境变量 REPORT_PATH 传入，如 /report/2026-07-02.md
RECENT_REPORT="${REPORT_PATH:-}"

# ============================================================
# 颜色 + 辅助
# ============================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

pass()  { echo -e "  ${GREEN}[PASS]${NC} $1"; }
fail()  { echo -e "  ${RED}[FAIL]${NC} $1"; }
warn()  { echo -e "  ${YELLOW}[WARN]${NC} $1"; }
info()  { echo -e "  ${CYAN}[INFO]${NC} $1"; }
header(){ echo -e "\n${BOLD}$1${NC}\n---"; }

# ============================================================
# 确认门
# ============================================================
confirm() {
  local level="$1"
  local msg="$2"
  if [ "${SKIP_CONFIRM:-}" = "yes" ]; then
    return 0
  fi
  echo ""
  warn "⚠  ${msg}"
  echo -n "  确认执行？(yes/[no]): "
  read -r ans
  case "$ans" in
    y|Y|yes|YES) return 0 ;;
    *) fail "已取消 — ${level}" ; return 1 ;;
  esac
}

confirm_double() {
  local level="$1"
  echo ""
  warn "⚠⚠  ${level} 有打崩线上服务的风险！"
  echo -n "  你确定要执行？如有疑问请先读 docs/PERFORMANCE_TEST_PLAN.md。"
  echo -n "  输入 极限测试 确认(不加引号): "
  read -r ans
  if [ "$ans" != "极限测试" ]; then
    fail "已取消 — ${level}"
    return 1
  fi
  echo -n "  再确认一次：输入服务 target URL（默认 $BASE_URL）: "
  read -r ans2
  if [ "$ans2" != "$BASE_URL" ]; then
    fail "URL 不匹配，已取消"
    return 1
  fi
  return 0
}

# ============================================================
# PROFILE 映射 + 确认等级
# ============================================================
map_profile() {
  local trigger="$1"
  case "$trigger" in
    轻压测|smoke-load)
      echo "smoke-load"
      return 0
      ;;
    限流测试|rate-limit-load)
      echo "rate-limit-load"
      return 10  # 需确认
      ;;
    标准压测|normal-load)
      echo "normal-load"
      return 10  # 需确认
      ;;
    高峰压测|peak-load)
      echo "peak-load"
      return 20  # 需确认
      ;;
    突刺测试|spike-test)
      echo "spike-test"
      return 30  # 需确认+高亮
      ;;
    长稳测试|soak-test)
      echo "soak-test"
      return 40  # 需确认+时间加长
      ;;
    极限测试|limit-test)
      echo "limit-test"
      return 50  # 默认禁止+二次确认
      ;;
    *)
      return 255
      ;;
  esac
}

# ============================================================
# 前置检查
# ============================================================
preflight() {
  header "前置检查"

  # 1. k6 可用
  if command -v k6 &>/dev/null; then
    pass "k6: $(k6 version | head -1)"
  else
    fail "k6 未安装 — 请先安装 https://k6.io/docs/get-started/installation/"
    exit 1
  fi

  # 2. SSH 可达
  if ssh -o ConnectTimeout=5 admin@121.43.80.221 "echo OK" &>/dev/null; then
    pass "SSH 连接正常"
  else
    fail "SSH 无法连接 admin@121.43.80.221"
    exit 1
  fi

  # 3. curl 可达目标
  local http_code
  # curl 自身在连接失败时会输出 000；用 || true 防止 set -e 中断，
  # 再清洗掉非数字字符（避免退出码拼接导致 200000 之类），取前 3 位。
  http_code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 --max-time 10 "$BASE_URL/" 2>/dev/null || true)
  http_code=$(printf '%s' "$http_code" | tr -cd '0-9')
  http_code=${http_code:0:3}
  [ -z "$http_code" ] && http_code="000"
  case "$http_code" in
    200|301|302|308)
      pass "目标 $BASE_URL 可达 (HTTP $http_code)"
      ;;
    *)
      fail "目标 $BASE_URL 不可达 (HTTP $http_code)"
      exit 1
      ;;
  esac

  # 4. ai-news 服务运行中
  local svc
  svc=$(ssh -o ConnectTimeout=5 admin@121.43.80.221 \
    "systemctl is-active ai-news 2>/dev/null || echo unknown" 2>/dev/null | tr -d '\r\n')
  if [ "$svc" = "active" ]; then
    pass "ai-news.service 运行中"
  else
    fail "ai-news.service 状态: $svc"
    exit 1
  fi

  info "前置检查全部 PASS"
}

# ============================================================
# 压测后烟雾测试
# ============================================================
post_smoke() {
  header "压测后冒烟测试"
  if ! bash "$SCRIPT_DIR/qa_smoke_test.sh"; then
    fail "冒烟测试未通过 — 可能有服务异常"
    return 1
  fi
  pass "冒烟测试通过"
}

# ============================================================
# 执行 k6 压测
# ============================================================
run_k6() {
  local profile="$1"

  header "执行压测 — $profile"
  info "Profile  : $profile"
  info "Target   : $BASE_URL"
  info "Result   : $SUMMARY_JSON"
  echo ""

  local extra=""
  if [ -n "$RECENT_REPORT" ]; then
    extra="-e REPORT_PATH=$RECENT_REPORT"
  fi

  set +e  # k6 v2.x 退出码：0=通过, 99=阈值破线, 1+=脚本错误
  # 路径转换已在脚本顶部通过 MSYS2_ARG_CONV_EXCL 关闭
  k6 run "$K6_SCRIPT" \
    -e "PROFILE=$profile" \
    -e "TARGET_URL=$BASE_URL" \
    -e "STATIC_PATHS=$STATIC_PATHS" \
    -e "API_PATHS=$API_PATHS" \
    -e "SUMMARY_JSON=$SUMMARY_JSON" \
    $extra \
    --quiet
  local K6_EXIT=$?
  set -e

  if [ $K6_EXIT -eq 0 ]; then
    pass "k6 执行完成，所有阈值通过"
  elif [ $K6_EXIT -eq 99 ]; then
    warn "k6 退出码 99 — 存在阈值破线（报告会详细分析）"
  else
    warn "k6 退出码 $K6_EXIT — 脚本执行异常"
  fi
  return $K6_EXIT
}

# ============================================================
# 生成报告
# ============================================================
generate_report() {
  header "生成性能报告"
  bash "$SCRIPT_DIR/performance_report.sh" "$SUMMARY_JSON" "$MONITOR_CSV"
}

# ============================================================
# 主流程
# ============================================================
main() {
  if [ $# -lt 1 ]; then
    echo ""
    echo "=============================================="
    echo "  AI 观察室 — 性能测试"
    echo "=============================================="
    echo ""
    echo "用法: bash scripts/load_test.sh <trigger-word> [--yes]"
    echo ""
    echo "触发词:"
    echo "  轻压测    — smoke-load       (1 VU, 30s, 无需确认, 不触发限流)"
    echo "  限流测试  — rate-limit-load  (2→20 VUs, 120s, 需确认, 专门测429)"
    echo "  标准压测  — normal-load      (3 VUs, 60s, 需确认)"
    echo "  高峰压测  — peak-load        (10 VUs, 120s, 需确认)"
    echo "  突刺测试  — spike-test       (1→50 VUs, ~50s, 需确认)"
    echo "  长稳测试  — soak-test        (2 VUs, 30min, 需确认)"
    echo "  极限测试  — limit-test       (递增寻找上限, 二次确认)"
    echo ""
    echo "选项:"
    echo "  --yes     跳过确认（仅适用于非高危等级）"
    echo ""
    exit 1
  fi

  local trigger="$1"
  local skip="${2:-no}"
  SKIP_CONFIRM="$skip"

  echo ""
  echo "=============================================="
  echo "  AI 观察室 — 性能测试"
  echo "  触发词 : $trigger"
  echo "  时间   : $(date '+%Y-%m-%d %H:%M:%S')"
  echo "=============================================="

  # 1. 映射触发词 → PROFILE
  local profile
  profile=$(map_profile "$trigger" || true)
  local need_confirm=$?

  if [ $need_confirm -eq 255 ]; then
    fail "未知触发词: '$trigger'"
    echo "  支持的触发词: 轻压测 / 标准压测 / 高峰压测 / 突刺测试 / 长稳测试 / 极限测试"
    exit 1
  fi

  # 2. 确认门
  case $need_confirm in
    0)   info "smoke-load 默认允许，无需确认" ;;
    10)  confirm "normal-load" "标准压测: 20并发 × 60秒 — 继续？" || exit 0 ;;
    20)  confirm "peak-load"  "高峰压测: 50并发 × 120秒 — 模拟高峰流量，继续？" || exit 0 ;;
    30)  echo ""
         warn "⚠⚠  突刺测试: 5→80并发突发持续30秒，会模拟真实突发流量！"
         confirm "spike-test" "确认执行？" || exit 0 ;;
    40)  confirm "soak-test" "长稳测试: 15并发 × 30分钟 — 耗时较长，确认？" || exit 0 ;;
    50)  confirm_double "limit-test" || exit 0 ;;
  esac

  # 3. 前置检查
  preflight

  # 4. 启动服务器监控（后台）
  info "启动服务器监控 (PID: $$)"
  bash "$SCRIPT_DIR/monitor_server.sh" "$MONITOR_CSV" &
  MONITOR_PID=$!
  trap "kill $MONITOR_PID 2>/dev/null; exit" INT TERM EXIT

  # 5. 执行压测
  run_k6 "$profile"
  local K6_EXIT=$?

  # 6. 停止监控
  sleep 2  # 等最后一个采样
  kill "$MONITOR_PID" 2>/dev/null || true
  trap - INT TERM EXIT
  info "服务器监控停止"

  # 7. 压测后烟雾测试
  post_smoke || true

  # 8. 生成报告
  generate_report

  # 9. 汇总
  echo ""
  echo "=============================================="
  if [ $K6_EXIT -eq 0 ]; then
    echo -e "  ${GREEN}性能测试完成 — 所有阈值通过 ✅${NC}"
  else
    echo -e "  ${RED}性能测试完成 — 存在阈值破线 ❌${NC}"
    echo "  见性能报告了解详情。"
  fi
  echo "=============================================="
  echo "  Result: $SUMMARY_JSON"
  echo "  Monitor: $MONITOR_CSV"
  echo "=============================================="

  exit $K6_EXIT
}

main "$@"
