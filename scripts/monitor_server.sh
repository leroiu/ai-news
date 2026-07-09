#!/bin/bash
# ============================================================
# monitor_server.sh — 性能测试期间服务器状态监控
#
# 由 load_test.sh 自动启动（后台），产出一个 CSV 文件，
# 每 5 秒采样一次，记录 CPU / 内存 / 负载 / 连接数 / 5xx 增量。
#
# 用法（一般不需要手动执行）:
#   bash scripts/monitor_server.sh <output.csv>
#
# 输出 CSV 列:
#   timestamp, cpu_pct, mem_pct, load_1, load_5, load_15,
#   conn_est, active_conn, nginx_5xx, service_alive
# ============================================================
set -euo pipefail

SERVER="admin@121.43.80.221"
SSH_OPTS="-o ConnectTimeout=5 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
INTERVAL=5

OUTPUT="${1:-/dev/null}"
rm -f "$OUTPUT"

# 写入 CSV 表头
echo "timestamp,cpu_pct,mem_pct,load_1,load_5,load_15,conn_est,active_conn,nginx_5xx,service_alive" > "$OUTPUT"

# 初始 5xx 基线
LAST_5XX=$(ssh $SSH_OPTS "$SERVER" \
  "tail -c 1M /var/log/nginx/ai-news-access.log 2>/dev/null | grep -cE 'HTTP/1\\.[01]\" 5[0-9][0-9]' 2>/dev/null || echo 0" 2>/dev/null || echo 0)
LAST_5XX=$(printf '%s' "$LAST_5XX" | tr -cd '0-9')
[ -z "$LAST_5XX" ] && LAST_5XX=0

warn() { echo "  [MONITOR] $1"; }

trap 'warn "监控已停止"' EXIT

warn "服务器监控已启动 → $OUTPUT"

while true; do
  TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

  # 采集服务器指标（一条 SSH 做完，减少连接开销）
  SSH_OUT=$(ssh $SSH_OPTS "$SERVER" "
    set -euo pipefail
    # CPU & 内存
    CPU=\$(top -bn1 | grep 'Cpu(s)' | awk '{print \$2+ \$4}' 2>/dev/null || echo 0)
    MEM=\$(free | grep Mem | awk '{printf \"%.1f\", \$3*100/\$2}' 2>/dev/null || echo 0)
    LOAD=\$(cat /proc/loadavg 2>/dev/null || echo '0 0 0 0')
    # 连接数
    CONN_EST=\$(ss -tn state established 2>/dev/null | tail -n +2 | wc -l || echo 0)
    ACTIVE=\$(ss -tn 2>/dev/null | tail -n +2 | wc -l || echo 0)
    # 服务状态
    SVC=\$(systemctl is-active ai-news 2>/dev/null || echo 'unknown')
    echo \"\$CPU|\$MEM|\$LOAD|\$CONN_EST|\$ACTIVE|\$SVC\"
  " 2>/dev/null || echo "||0 0 0 0||unknown")

  IFS='|' read -r CPU MEM LOAD_RAW CONN_EST ACTIVE SVC <<< "$SSH_OUT"
  read -r L1 L2 L3 _ <<< "$(echo "$LOAD_RAW" | tr '/' ' ' 2>/dev/null || echo '0 0 0')"

  # 5xx 增量
  CURRENT_5XX=$(ssh $SSH_OPTS "$SERVER" \
    "tail -c 1M /var/log/nginx/ai-news-access.log 2>/dev/null | grep -cE 'HTTP/1\\.[01]\" 5[0-9][0-9]' 2>/dev/null || echo 0" 2>/dev/null || echo 0)
  # 清洗成整数，避免 ssh 输出含回车/空格导致算术语法错误
  CURRENT_5XX=$(printf '%s' "$CURRENT_5XX" | tr -cd '0-9')
  LAST_5XX=$(printf '%s' "$LAST_5XX" | tr -cd '0-9')
  [ -z "$CURRENT_5XX" ] && CURRENT_5XX=0
  [ -z "$LAST_5XX" ] && LAST_5XX=0
  DELTA_5XX=$(( CURRENT_5XX - LAST_5XX ))
  LAST_5XX=$CURRENT_5XX

  # 写入 CSV
  echo "$TIMESTAMP,${CPU:-0},${MEM:-0},${L1:-0},${L2:-0},${L3:-0},${CONN_EST:-0},${ACTIVE:-0},$DELTA_5XX,${SVC:-unknown}" >> "$OUTPUT"

  # 实时告警：服务挂了
  if [ "${SVC:-}" != "active" ] && [ "${SVC:-}" != "" ]; then
    echo ""
    warn "⚠⚠⚠  ai-news.service 状态异常: ${SVC}"
    echo ""
  fi

  # 实时告警：CPU 持续高于 90%（连续 3 次后会触发，这里只打印警告）
  if [ "$(echo "${CPU:-0} >= 90" | bc -l 2>/dev/null)" = "1" ]; then
    warn "CPU 使用率 ${CPU}% — 高位运行"
  fi

  # 实时告警：出现 5xx
  if [ "$DELTA_5XX" -gt 0 ]; then
    warn "5xx 响应: +$DELTA_5XX（本采样周期）"
  fi

  sleep "$INTERVAL"
done
