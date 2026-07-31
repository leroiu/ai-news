# 项目目录地图

> 本文档帮你快速找到项目中的任何文件，不用一个一个翻目录。
>
> 项目：AI Intelligence Platform（ai-news）

---

## 目录分类

### 🔵 核心目录（你需要关心）

| 目录 | 用途 | 什么时候进 |
|------|------|-----------|
| **`src/`** | 所有核心代码 | 修改功能、修 bug |
| **`data/`** | 数据库、知识卡片、抓取数据 | 查数据、改卡片 |
| **`docs/`** | 项目文档、架构说明、bug 分类 | 查文档、看架构 |
| **`tests/`** | 自动化测试 | 测试失败时排查 |
| **`prompts/`** | AI 提示词模板 | 调整摘要/分类质量 |
| **`templates/`** | 日报/报告模板 | 修改日报格式 |
| **`config.yaml`** | 项目主配置 | 改参数、换 API |
| **`pipeline*.py`** | 主流程入口 | 运行/调度出问题 |

### 🟡 运维目录（偶尔需要）

| 目录 | 用途 | 什么时候进 |
|------|------|-----------|
| **`scripts/`** | 定时任务、部署、备份脚本 | 定时任务出问题、部署 |
| **`tools/`** | 质量检查、数据迁移、前端验证 | 排查质量门禁、迁数据 |
| **`.agents/`** | AI Agent 配置 | 调整 agent 行为 |
| **`.claude/`** | Claude Code 设置 | 改 AI 权限 |
| **`migrations/`** | 数据库迁移脚本 | 数据库结构变更 |
| **`.github/`** | GitHub CI/CD 配置 | CI 流水线出问题 |

### 🟢 运行时产出（自动生成，不需要关心）

| 目录 | 内容 | 说明 |
|------|------|------|
| **`logs/`** | 运行日志 | 出 bug 时看日志 |
| **`reports/`** | 生成的日报 | 程序自动生成 |
| **`cache/`** | 运行缓存 | 程序自动管理 |
| **`output/`** | 质量门禁输出 | 测试/检查结果 |
| **`screenshots/`** | 截图 | 前端检查时生成 |
| **`test-results/`** | 测试结果 | 跑完测试后生成 |
| **`.playwright-mcp/`** | 浏览器自动化缓存 | 自动生成 |

### ⚫ 依赖/缓存（已隐藏，看不到就对了）

| 目录 | 说明 |
|------|------|
| `.venv/` | Python 虚拟环境 |
| `node_modules/` | Node.js 依赖 |
| `__pycache__/` | Python 编译缓存 |
| `.uv-cache/` `.uv-cache-test/` | uv 包管理器缓存 |
| `.pytest_cache/` | 测试框架缓存 |

### 🚫 私有目录（AI 不会读）

| 目录 | 说明 |
|------|------|
| `.private/` | 私人笔记、交接文档 |

---

## 常见任务 → 去哪找

| 我想做什么 | 去这里 |
|-----------|--------|
| 改新闻抓取来源 | `config.yaml` → `src/engine/fetcher.py` |
| 改摘要/分类质量 | `prompts/` → `src/engine/ai_client.py` |
| 改日报格式 | `templates/` → `src/engine/reporter.py` |
| 改前端页面 | `src/frontend/` |
| 改知识卡片 | `data/knowledge/` |
| 改语义搜索 | `src/engine/embeddings.py` |
| 查数据库 | `data/ai_news.db` |
| 查报错日志 | `logs/` |
| 看项目架构 | `docs/ARCHITECTURE.md` |
| 看功能规划 | `docs/ROADMAP.md` |
| 看变更记录 | `docs/CHANGELOG.md` |
| 看架构决策 | `docs/DECISIONS.md` |
| 看 bug 分类 | `docs/BUG_CLASSIFICATION.md` |
| 记录 bug | `docs/BUG_LOG.md` |
| 定时任务出问题 | `scripts/cron_*.sh` |
| 部署到服务器 | `scripts/deploy_*.sh` + `scripts/deploy/` |
| 跑质量检查 | `tools/quality_gate.py` |
| 数据迁移 | `tools/migrate.py` |

---

## src/ 子目录详解

| 子目录 | 用途 |
|--------|------|
| `src/engine/` | 核心引擎：抓取、摘要、分类、去重、评分、嵌入、知识卡片 |
| `src/frontend/` | 前端页面：仪表盘、文章页、实体页、研究页、认证 |
| `src/api/` | API 接口 |
| `src/plugins/` | 插件（如 Twitter） |
| `src/interfaces/` | 数据模型、i18n |

---

## 快速定位口诀

```
要改功能 → src/
要查数据 → data/
要看文档 → docs/
要改配置 → config.yaml
要改提示词 → prompts/
要改模板 → templates/
要改脚本 → scripts/
要查工具 → tools/
要查日志 → logs/
要看报告 → reports/
```

---

*最后更新：2026-07-24*