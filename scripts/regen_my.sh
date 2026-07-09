#!/bin/bash
# 重生成 my.html（独立脚本，不重新上传文件）
set -euo pipefail
SERVER="admin@121.43.80.221"
APP_DIR="/home/admin/app"
SSH_OPTS="-o ConnectTimeout=10 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

echo "重生成 my.html ..."
ssh $SSH_OPTS "$SERVER" "cd $APP_DIR && .venv/bin/python -c 'from src.frontend.my_page import generate_my_page; print(generate_my_page())'"
echo "完成"
