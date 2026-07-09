#!/bin/bash
# run_smoke_load.sh — 一次性包装：设 PATH + 跑轻压测
export PATH="/c/Program Files/k6:$PATH"
cd "$(dirname "$0")/.."
bash scripts/load_test.sh smoke-load
