# AI Intelligence Platform — 项目交接文档

> 任何新的 Claude 会话第一件事就是读这个文件。
> 每次会话结束时自动更新。

## 项目定位

AI 观察室 (AI Observatory) — AI 智能情报平台。News / Knowledge / Graph / Research。
Knowledge Card 是整个系统的唯一事实来源（SSOT）。

## 当前状态（2026-07-03 更新）

### 最近 3 次会话

| 日期 | 内容 | Commit |
|------|------|--------|
| 2026-07-03 | **Concept Miner 四重优化** — ★3+过滤 + 去重 + 缓存 + 3并发 | `ee3062d` |
| 2026-07-03 | **Topics 搜索稳定性** — 关键词即时匹配 + 语义搜索仅补充空结果 | `d1e2802` |
| 2026-07-03 | **Codex V7.2.3 全站同步** — 暖石墨/纸白双主题 + 编辑型排版 + 16文件 | `8d6d492` |
| 2026-07-03 | **后端 Timeline date 归一化** — int→str, YYYY/YYYY-MM/YYYY-MM-DD | `8d3a818` |
| 2026-07-03 | **数据清理** — 删除 37 张占位符 + 42 条 2026 无效事件 | `2f271d9` |
| 2026-07-03 | **文件拆分** — database.py(801→8文件) + pipeline.py(623→3文件) | `a0a1db5` `32e3f31` |
| 2026-07-03 | **Size Policy 升级** — 三级分级策略替代硬性 300 行 | `f369792` |
| 2026-07-02 | **多源扩展** — Twitter/X v2 API + 微信 RSSHub 桥接 | — |
| 2026-07-02 | **后端 P1+P2 API 补全** — Entity/Relationship 写 API + Pipeline 触发 + Pydantic 验证 + 分页 + 版本历史 + 迁移系统 | — |
| 2026-07-02 | **3 个 Agent 全部交付** — Research Agent + Concept Miner Agent + Trend Reporter Agent | — |
| 2026-07-02 | **Card Writer + 收集流水线** — Research→AI撰写→YAML 三 Agent 完整闭环 | — |

> 更早的会话历史见 `git log --oneline`。

### 当前数据

| 指标 | 数值 |
|------|------|
| 文章 | 1,188 篇 |
| 实体 | 162 张（company:20, model:61, tech:9, concept:9, product:17, person:16, methodology:17, event:13） |
| 嵌入向量 | 162 个（SiliconFlow BGE 1024维） |
| 关系 | 770 条 |
| 数据源 | 16 RSS + GitHub Trending + Twitter/X v2 + 微信公众号 |
| 页面 | 9 个 (Today / Topics / Entity / 2D/3D Graph / Timeline / Events / Research / My) |
| 测试 | 357 passed, 1 known failure (test_direct_match) |
| 定时任务 | AI-News-Daily (每天20:57) + Weekly (周日21:07) + Monthly (每月1日22:07) |

### 当前问题

- 📋 收藏系统为 localStorage MVP，无账号同步
- 📋 methodology 卡爆增：Concept Miner 生成约 130+ 张草稿卡，需批量审核
- ⚠ test_direct_match 预存失败（1/357）：methodology 卡数量变化导致 Jaccard 匹配漂移
- ⚠ `docs/ARCHITECTURE.md` 576 行超过 L3 (>500)，下次相关开发时拆分

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
