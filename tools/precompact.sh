#!/bin/bash
# PreCompact Hook — 轻量级：仅更新时间戳，不执行任何耗时操作
# 规则：不 sync、不 rebuild、不 test、不 git
set -e

TODAY=$(date +%Y-%m-%d)
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HANDOVER="$PROJECT_DIR/HANDOVER_项目交接.md"
MEMORY="$PROJECT_DIR/PROJECT_MEMORY_项目长期记忆.md"

# 1. HANDOVER: 更新状态行日期
if [ -f "$HANDOVER" ]; then
  sed -i "s/## 当前状态（[0-9\-]* 更新）/## 当前状态（$TODAY 更新）/" "$HANDOVER"
fi

# 2. PROJECT_MEMORY: 更新最后更新行
if [ -f "$MEMORY" ]; then
  sed -i "s/> 最后更新: [0-9\-]*/> 最后更新: $TODAY/" "$MEMORY"
fi
