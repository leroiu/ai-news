# AI Intelligence Platform — 项目交接文档

> 任何新的 Claude 会话第一件事就是读这个文件。

## 项目定位

AI 观察室 (AI Observatory) — AI 智能情报平台。News / Knowledge / Graph / Research。

## 当前状态（2026-07-31 更新）

### 本会话摘要

> **核心成果**: 分支整合 + 远程同步 + 权限调整
> **操作**: fetch 远程 100 个提交（99 collector + 1 fix）合并到 master；cherry-pick `experiment-sync`（.agents/ + docs/BUG_* + scripts/deploy/）；cherry-pick `fix`（pipeline 故障可恢复 + processing_errors.py + 247 行可靠性测试）；从 `quality-gates-ci` 提取 30 张知识卡片；删除 3 个过时分支；push 到远程
> **权限调整**: AGENTS.md + .claude/settings.json 放开 `.private/` 读写（保留 .env 禁止）
> **测试**: 523 passed, 1 skipped, 0 failed
> **Commit**: `777efa8` Merge remote-tracking branch 'origin/master'（master 已与远程同步）

### 自动化链路确认

```
GitHub Actions (每小时 :07) -> collector -> git push master
服务器 cron (每小时 :05)  -> git pull --rebase --autostash >> logs/cron-git.log
服务器 cron (每天 9:00)   -> pipeline.py --only-unprocessed (DeepSeek)
服务器 cron (每周日 10:00) -> pipeline.py --only-unprocessed --weekly
```

### 当前数据

| 指标 | 数值 |
|------|------|
| inbox | 7577 行（6/27 ~ 7/31 15:26） |
| 知识卡片 | 634 张 YAML |
| 测试 | 523 passed, 1 skipped |
| 部署 | 阿里云 admin@121.43.80.221 |
| AI Provider | DeepSeek (.env: AI_PROVIDER=deepseek) |
| 采集器 | GitHub Actions US runner, 14源 |
| pipeline | 支持故障可恢复（processing_errors.py + db_pipeline.py） |

### 分支状态

| 分支 | 状态 |
|------|------|
| `master` | ✅ 与 origin 同步 |
| `codex/agent-failure-diagnosis` | worktree 占用，0 ahead，可清理 |
| `fix` | worktree 占用，已 cherry-pick 到 master，可清理 |
| `p3-ain-graph-nav-001` | worktree 占用 |
| `experiment/pbd-v1-collector-outcome` | worktree 占用 |

### 当前问题

- 📋 HTTPS/域名配置
- ⚠ 评分体系偏斜 - ArXiv 论文最高 ★★★★
- 📋 worktree 分支待清理（agent-failure-diagnosis / fix / p3-ain-graph-nav-001）

## 注意事项（快速参考）

- Knowledge Card 是唯一写入点（SSOT），所有模块只读
- importance（人工策展）≠ score（AI 实时打分）
- tags 不嵌套，平铺
- SQLite WAL 模式，外键约束
- API 启动: `uv run uvicorn src.api.api:app --reload --port 8765`
- AI 客户端: 120s 超时 + 3 次指数退避重试（1.5s/3s/6s）
- 卡片同步: `uv run python -m src.sync_cards` (仅人工策展) 或 `--include-drafts`
- 前端设计: 新增页面从 `frontend_styles.py` 导入 TYPE_COLORS/THEME_VARS/共享CSS
- i18n: `nav_html(path)` 生成导航；`T("key")` / `TLbl(type)` JS 函数运行时翻译
- 语义搜索: 162 张卡片已嵌入，`match_cards(use_semantic=True)` 自动优先语义匹配
- Embedding Provider: 可插拔注册表，当前 `siliconflow`
- Pipeline 运行: `python pipeline.py --hours 24` (日报) / `--weekly` / `--monthly`
- Concept Miner 优化: 仅处理 ★3+ 文章，已挖掘 ID 自动跳过，3 并发批处理
- 定时任务: `schtasks /query /tn AI-News-Daily` 查看状态
- 会话收尾: 说 "整理一下" / "收尾" / "sync up" → 自动按变更矩阵更新所有文档 (详见 ENGINEERING §9)
- 故障定位: 遇到 bug 先看 `docs/BUG_CLASSIFICATION.md`（按症状定位模块），新 bug 记录到 `docs/BUG_LOG.md`
- 目录导航: 找文件先看 `docs/PROJECT_LAYOUT.md`（目录地图 + 速查表）
- 部署配置: `scripts/deploy/`（Dockerfile + fly.toml）

## 工程原则（详见 docs/ENGINEERING.md）

### Size Policy

| Level | 行数 | 策略 |
|-------|------|------|
| L1 健康 | ≤350 | 正常维护 |
| L2 计划 | 351–500 | 下次相关开发时拆分 |
| L3 优先 | >500 | 下一轮优先任务 |

### 知识分层 (2026-07-03 新增)

| 层次 | 文件 | 受众 |
|------|------|------|
| Agent 交接 | `.private/HANDOVER.md` | AI 自己跨会话 |
| 工程规则 | `docs/ENGINEERING.md` + `.private/PROJECT_MEMORY.md` | 当前项目 AI |
| 对外文档 | `docs/ARCHITECTURE.md` `ROADMAP.md` `README.md` | 人类同事 |

### 同步前尺寸体检

每次会话结束: `wc -l` HANDOVER、PROJECT_MEMORY、ARCHITECTURE。
- HANDOVER >300 → 压缩历史会话
- ARCHITECTURE >500 → 拆分子文档
- PROJECT_MEMORY >250 → 内容"毕业"进 docs/

### 减优于加

- 历史叙事归 git log，不写进文档
- 同主题内容并进已有段落，不追加新段
- 过期临时计划、已推翻决策 → 删
