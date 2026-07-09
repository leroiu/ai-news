#!/bin/bash
# ============================================================
# performance_report.sh — 性能测试报告生成器
#
# 解析 k6 结果 JSON + 服务器监控 CSV，输出固定格式报告。
# 429（限流）和 5xx（系统错误）分开统计。
#
# 用法:
#   bash scripts/performance_report.sh <k6_summary.json> [monitor.csv]
# ============================================================
set -euo pipefail

K6_JSON="${1:-}"
MONITOR_CSV="${2:-}"

if [ -z "$K6_JSON" ] || [ ! -f "$K6_JSON" ]; then
  echo "[ERROR] 需要 k6 结果 JSON 文件路径" >&2
  echo "用法: $0 <k6_summary.json> [monitor.csv]" >&2
  exit 1
fi

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

# ============================================================
# JSON 解析（兼容无 jq）
# ============================================================
json_val() {
  local file="$1"
  local key="$2"
  if command -v jq &>/dev/null; then
    jq -r "$key" "$file" 2>/dev/null || echo "N/A"
  else
    grep -oP "\"$key\":\\s*\"?[^\",}]+" "$file" 2>/dev/null | head -1 | sed 's/.*: *//; s/^"//; s/"$//' || echo "N/A"
  fi
}

to_pct() {
  local val="$1"
  if [ -n "$val" ] && [ "$val" != "N/A" ] && [ "$val" != "null" ]; then
    awk "BEGIN {printf \"%.2f\", $val * 100}" 2>/dev/null || echo "N/A"
  else
    echo "N/A"
  fi
}

# ============================================================
# 解析 k6 JSON
# ============================================================
parse_k6_metrics() {
  local file="$1"

  # 真错误率（4xx 排除 429 + 5xx）
  local real_err
  real_err=$(json_val "$file" '.metrics.real_error_rate.values.rate // empty')
  [ -z "$real_err" ] || [ "$real_err" = "N/A" ] && real_err=$(json_val "$file" '.metrics.real_error_rate.values.rate')

  # 限流命中率（429）
  local rl_rate
  rl_rate=$(json_val "$file" '.metrics.rate_limit_hit.values.rate // empty')
  [ -z "$rl_rate" ] || [ "$rl_rate" = "N/A" ] && rl_rate=$(json_val "$file" '.metrics.rate_limit_hit.values.rate')

  # 兼容旧版 http_req_failed
  local fail_rate
  fail_rate=$(json_val "$file" '.metrics.http_req_failed.values.rate // empty')
  [ -z "$fail_rate" ] || [ "$fail_rate" = "N/A" ] && fail_rate=$(json_val "$file" '.metrics.http_req_failed.values.rate')

  local total_reqs static_p95 api_p95 req_p99
  total_reqs=$(json_val "$file" '.metrics.http_reqs.values.count')
  static_p95=$(json_val "$file" '.metrics.static_page_duration.values["p(95)"]')
  api_p95=$(json_val "$file" '.metrics.api_duration.values["p(95)"]')
  req_p99=$(json_val "$file" '.metrics.http_req_duration.values["p(99)"]')

  echo "real_err_pct=$(to_pct "$real_err")"
  echo "rate_limit_pct=$(to_pct "$rl_rate")"
  echo "fail_rate_pct=$(to_pct "$fail_rate")"
  echo "total_reqs=${total_reqs:-N/A}"
  echo "static_p95_ms=${static_p95:-N/A}"
  echo "api_p95_ms=${api_p95:-N/A}"
  echo "req_p99_ms=${req_p99:-N/A}"
}

# ============================================================
# 解析监控 CSV
# ============================================================
parse_monitor() {
  local file="$1"
  if [ ! -f "$file" ]; then
    echo "cpu_avg=N/A cpu_max=N/A mem_avg=N/A mem_max=N/A load_max=N/A peak_conn=N/A total_5xx=N/A service_drop=N/A"
    return
  fi

  local lines
  lines=$(tail -n +2 "$file" 2>/dev/null || true)
  if [ -z "$lines" ]; then
    echo "cpu_avg=N/A cpu_max=N/A mem_avg=N/A mem_max=N/A load_max=N/A peak_conn=N/A total_5xx=N/A service_drop=N/A"
    return
  fi

  eval "$(echo "$lines" | awk -F',' '
    BEGIN { cpu_sum=0; cpu_max=0; mem_sum=0; mem_max=0; load_max=0; conn_max=0; svc_drop=0; cnt=0; total_5xx=0 }
    {
      cnt++
      cpu=$2+0; mem=$3+0; l1=$4+0; conn=$7+0; fivxx=$9+0
      cpu_sum+=cpu; if(cpu>cpu_max) cpu_max=cpu
      mem_sum+=mem; if(mem>mem_max) mem_max=mem
      if(l1>load_max) load_max=l1
      if(conn>conn_max) conn_max=conn
      total_5xx+=fivxx
      if($10!="active") svc_drop++
    }
    END {
      printf "cpu_avg=%.1f\n", (cnt>0?cpu_sum/cnt:0)
      printf "cpu_max=%.1f\n", cpu_max
      printf "mem_avg=%.1f\n", (cnt>0?mem_sum/cnt:0)
      printf "mem_max=%.1f\n", mem_max
      printf "load_max=%.1f\n", load_max
      printf "peak_conn=%d\n", conn_max
      printf "total_5xx=%d\n", total_5xx
      printf "service_drop=%d\n", svc_drop
    }')"
}

# ============================================================
# 瓶颈判断
# ============================================================
assess_bottleneck() {
  local static_p95="$1" api_p95="$2" real_err_pct="$3" rate_limit_pct="$4"
  local cpu_max="$5" mem_max="$6" total_5xx="$7" profile="$8"

  local bottlenecks=()

  if (( $(echo "$static_p95 > 500" | bc -l 2>/dev/null) )); then
    bottlenecks+=("静态页面 P95 ${static_p95}ms 超限 (>500ms) — Nginx 缓存或 I/O 瓶颈")
  fi

  if (( $(echo "$api_p95 > 1500" | bc -l 2>/dev/null) )); then
    bottlenecks+=("API P95 ${api_p95}ms 超限 (>1500ms) — 后端处理慢，检查数据库/外部调用")
  fi

  # 真错误（非 429）才算系统问题
  if (( $(echo "${real_err_pct:-0} >= 1" | bc -l 2>/dev/null) )); then
    bottlenecks+=("真错误率 ${real_err_pct}% 超阈值 — 存在 4xx/5xx 系统错误")
  fi

  # 429 限流是信息性的，不是系统崩溃
  if (( $(echo "${rate_limit_pct:-0} > 0" | bc -l 2>/dev/null) )); then
    if [ "$profile" = "rate-limit-load" ]; then
      bottlenecks+=("限流命中率 ${rate_limit_pct}% — 符合预期（rate-limit-load 专测限流）")
    else
      bottlenecks+=("限流命中率 ${rate_limit_pct}% — 超过后端 120 req/min 限流，非系统故障")
    fi
  fi

  if (( $(echo "$cpu_max > 90" | bc -l 2>/dev/null) )); then
    bottlenecks+=("CPU 峰值 ${cpu_max}% > 90%")
  fi

  if [ "${total_5xx:-0}" -gt 0 ]; then
    bottlenecks+=("出现 ${total_5xx} 个 5xx — 应用层错误")
  fi

  if (( $(echo "${mem_max:-0} > 85" | bc -l 2>/dev/null) )); then
    bottlenecks+=("内存峰值 ${mem_max}% — 疑似内存泄漏")
  fi

  if [ ${#bottlenecks[@]} -eq 0 ]; then
    echo "未发现明确性能瓶颈。"
  else
    printf '%s\n' "${bottlenecks[@]}"
  fi
}

# ============================================================
# 下一步建议
# ============================================================
next_step() {
  local profile="$1" real_err="$2" rate_limit="$3" static_p95="$4" api_p95="$5"

  # 真错误率高 → 先修 bug
  if (( $(echo "${real_err:-0} >= 5" | bc -l 2>/dev/null) )); then
    echo "1. 真错误率过高，先排查 4xx/5xx 原因，再继续压测"
    return
  fi

  local steps=()

  # 限流建议
  if (( $(echo "${rate_limit:-0} > 0" | bc -l 2>/dev/null) )) && [ "$profile" != "rate-limit-load" ]; then
    steps+=("1. 限流命中率 ${rate_limit}% — 考虑提高限流阈值或增加限流策略（按端点/用户分级）")
  fi

  if (( $(echo "$static_p95 > 300" | bc -l 2>/dev/null) )); then
    steps+=("2. 静态页面偏慢：确认 Nginx gzip/缓存，检查磁盘 I/O")
  fi

  if (( $(echo "$api_p95 > 800" | bc -l 2>/dev/null) )); then
    steps+=("3. API 偏慢：添加 Redis 缓存 / 优化数据库查询 / 增加 uvicorn workers")
  fi

  # profile 递进建议
  case "$profile" in
    smoke-load)     steps+=("4. smoke-load 通过 → 建议 normal-load 验证中负载") ;;
    rate-limit-load) steps+=("4. 限流测试完成 → 记录限流拐点，用于容量规划") ;;
    normal-load)    steps+=("4. normal-load 通过 → 建议 peak-load 模拟高峰") ;;
    peak-load)      steps+=("4. peak-load 通过 → 建议 spike-test 验证突发承受力") ;;
    spike-test|soak-test) steps+=("4. 结果作为基线，与历史比较趋势") ;;
    limit-test)     steps+=("4. 根据拐点并发数保留 30% 余量") ;;
  esac

  if [ ${#steps[@]} -eq 0 ]; then
    echo "4. 所有指标良好，持续监控退化。"
  else
    printf '%s\n' "${steps[@]}"
  fi
}

# ============================================================
# 主流程
# ============================================================
main() {
  local k6_file="$1"
  local monitor_file="$2"

  # 读取 PROFILE
  local profile="unknown"
  if command -v jq &>/dev/null; then
    profile=$(jq -r '.options.env.PROFILE // "unknown"' "$k6_file" 2>/dev/null || echo "unknown")
  fi
  if [ "$profile" = "unknown" ] || [ "$profile" = "null" ]; then
    local fname
    fname=$(basename "$k6_file")
    for p in smoke-load rate-limit-load normal-load peak-load spike-test soak-test limit-test; do
      if echo "$fname" | grep -q "$p"; then profile="$p"; break; fi
    done
  fi

  # 解析指标
  eval "$(parse_k6_metrics "$k6_file")"
  eval "$(parse_monitor "$monitor_file")"

  # ---- 判定：真错误 + 性能阈值 ----
  local verdict="PASS"
  # 真错误率 ≥ 1% → FAIL（429 不算）
  if [ -n "${real_err_pct:-}" ] && [ "${real_err_pct:-}" != "N/A" ] && \
     (( $(echo "${real_err_pct} >= 1" | bc -l 2>/dev/null) )); then
    verdict="FAIL"
  fi
  # smoke-load 不允许任何限流
  if [ "$profile" = "smoke-load" ] && [ -n "${rate_limit_pct:-}" ] && \
     [ "${rate_limit_pct:-}" != "N/A" ] && [ "${rate_limit_pct:-}" != "0.00" ] && \
     (( $(echo "${rate_limit_pct} > 0" | bc -l 2>/dev/null) )); then
    verdict="FAIL"
  fi
  # 性能阈值
  if [ -n "${static_p95_ms:-}" ] && [ "${static_p95_ms:-}" != "N/A" ] && \
     (( $(echo "${static_p95_ms} > 500" | bc -l 2>/dev/null) )); then
    verdict="FAIL"
  fi
  if [ -n "${api_p95_ms:-}" ] && [ "${api_p95_ms:-}" != "N/A" ] && \
     (( $(echo "${api_p95_ms} > 1500" | bc -l 2>/dev/null) )); then
    verdict="FAIL"
  fi

  # ---- 瓶颈 ----
  local bottleneck_text
  bottleneck_text=$(assess_bottleneck \
    "${static_p95_ms:-0}" "${api_p95_ms:-0}" "${real_err_pct:-0}" "${rate_limit_pct:-0}" \
    "${cpu_max:-0}" "${mem_max:-0}" "${total_5xx:-0}" "$profile")

  local next_text
  next_text=$(next_step "$profile" "${real_err_pct:-0}" "${rate_limit_pct:-0}" "${static_p95_ms:-0}" "${api_p95_ms:-0}")

  # ---- 输出固定格式报告 ----
  echo ""
  echo "=============================================="
  echo "  AI 观察室 — 性能测试报告"
  echo "  $(date '+%Y-%m-%d %H:%M:%S')"
  echo "=============================================="
  echo ""
  echo "状态：${verdict}"
  echo "测试类型：${profile}"
  echo "总请求数：${total_reqs:-N/A}"
  echo "真错误率(4xx+5xx)：${real_err_pct:-N/A}%"
  echo "限流命中率(429)：${rate_limit_pct:-N/A}%"
  echo "静态页面 P95：${static_p95_ms:-N/A}ms"
  echo "API P95：${api_p95_ms:-N/A}ms"
  echo "HTTP P99：${req_p99_ms:-N/A}ms"
  echo ""
  echo "服务器状态："
  echo "  CPU 平均：${cpu_avg:-N/A}%"
  echo "  CPU 峰值：${cpu_max:-N/A}%"
  echo "  内存峰值：${mem_max:-N/A}%"
  echo "  Load 峰值：${load_max:-N/A}"
  echo "  峰值连接数：${peak_conn:-N/A}"
  echo "  Total 5xx：${total_5xx:-N/A}"
  echo "  服务中断次数：${service_drop:-0}"
  echo ""
  echo "瓶颈判断："
  echo "  ${bottleneck_text}" | sed 's/^/  /'
  echo ""
  echo "下一步："
  echo "${next_text}" | sed 's/^/  /'
  echo ""
  echo "=============================================="

  if [ -f "$monitor_file" ]; then
    echo ""
    echo "CPU 时间序列（前10行）:"
    awk -F',' 'NR>1{print $1, $2"%"}' "$monitor_file" | head -10
    echo "  ..."
  fi

  [ "$verdict" = "FAIL" ] && return 1
  return 0
}

main "$@"
