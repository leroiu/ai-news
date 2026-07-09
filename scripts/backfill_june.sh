#!/bin/bash
# 回填报告 + 生成6月月报
set -euo pipefail
SERVER="admin@121.43.80.221"
APP_DIR="/home/admin/app"
SSH_OPTS="-o ConnectTimeout=10 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

echo "=== Step 1: 回填所有报告到数据库 ==="
ssh $SSH_OPTS "$SERVER" "cd $APP_DIR && .venv/bin/python tools/backfill_reports.py"

echo ""
echo "=== Step 2: 生成6月月报 ==="
ssh $SSH_OPTS "$SERVER" "cd $APP_DIR && .venv/bin/python -c 'from src.engine.utils import setup_logging, log; from src.engine.trend_reporter import generate_trend_report; setup_logging(\"INFO\"); log.info(\"生成6月月报...\"); path = generate_trend_report(\"month\"); print(f\"结果: {path}\" if path else \"未生成\")'"

echo ""
echo "=== Step 3: 重生成 Dashboard ==="
ssh $SSH_OPTS "$SERVER" "cd $APP_DIR && .venv/bin/python pipeline.py --dashboard"

echo ""
echo "=== 完成 ==="
