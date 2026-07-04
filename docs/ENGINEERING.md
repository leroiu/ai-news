# Engineering Principles — AI Intelligence Platform

> 开发过程中必须遵守的工程原则。违反这些原则会导致上下文爆炸、代码腐化、迭代效率骤降。

---

## 1. Context Budget Rule（上下文预算）

Claude Code 真正的上下文消耗不是代码本身，而是**代码修改记录**（diff、思考链、工具调用）。每修改一个文件都会产生大量上下文碎片。

### 硬性规则

| 阈值 | 动作 |
|------|------|
| 60% tokens | 开始收尾当前功能，不再扩展需求 |
| 70% tokens | 完成当前功能，准备 `/compact` |
| 75% tokens | **立即 `/compact`**，不协商 |
| 80%+ | 🛑 停止，不开新需求 |

### Agent 调用约束

| 规则 | 说明 |
|------|------|
| Explore Agent 限长 | prompt 必须含"只返回路径和摘要，不返回文件内容；≤500 words" |
| 不走全量读取 | 先 Grep 定位 → Read 用 offset/length，200+ 行文件禁止全文读取 |
| JS 语法优先 node | `node -e "new Function(code)"` 验证，禁止为看语法读完整 HTML |
| 文件不重读 | 同一会话内 ENGINEERING_PRINCIPLES / PROJECT_MEMORY / HANDOVER 只读一次 |

### 功能隔离

- **一个 Conversation = 一个 Feature**（Dashboard / Timeline / API / Graph / Library）
- Feature 完成后：测试 → Git Commit → `/compact` → **新 Conversation**
- 禁止在一个 Conversation 中连续开发多个模块

### 文件规模（Size Policy）

> 文件规模服务于可维护性，不追求固定行数。不为了满足行数而拆分，只为了降低未来维护成本而拆分。

| Level | 行数 | 策略 |
|-------|------|------|
| **L1 健康** | ≤350 | 正常维护，不主动拆分。新增功能时可顺手优化 |
| **L2 计划拆分** | 351–500 | 下次相关开发任务时一起拆分。否则保持现状 |
| **L3 优先拆分** | >500 | 下一轮开发的优先任务（除非长期稳定且不再增长） |

#### 当前状态 (2026-07-03)

| Level | 生产文件 | 已解决 |
|-------|---------|--------|
| L3 (>500) | 0 | database.py ✅, pipeline.py ✅ |
| L2 (351-500) | fetcher(497), api(420), i18n(415), twitter(371), trend_agent(367), embeddings(354) | 下次相关开发时拆分 |
| L1 (≤350) | knowledge(327), research_agent(332), trend_reporter(333), library(307), pipeline_stages(300) 等 | 健康 |

> 测试文件（test_*.py）不纳入行数限制。

### 上下文反模式（2026-06-30 已识别）

> 单次会话 136.9k tokens (80%) 的根因分析。

| 反模式 | 浪费量 | 正确做法 |
|--------|--------|----------|
| Explore Agent 无输出限制 | ~35k | prompt 中明确"≤500 words"或"只返回路径，不返回内容" |
| 全量读取大文件（Read 无 offset） | ~25k | Grep 定位行号 → `Read offset=N limit=M` 只取目标区间 |
| JS 调试时读取完整 HTML | ~15k | `node -e "new Function(code)"` 验证语法，不读 HTML 文件 |
| 单会话连续开发多模块 | diff 累积 | 一 Feature 一 Conversation，完成即 `/compact` |
| 重复读取不变文件 | 叠加 | ENGINEERING_PRINCIPLES / PROJECT_MEMORY / HANDOVER 同会话只读一次 |

---

## 2. SSOT Principle（单一事实来源）

- Knowledge Card (YAML) 是整个系统的 SSOT
- 所有模块只读 Card，唯一写入路径：手动编辑 或 Concept Miner 生成草稿
- Timeline 不存数据，只是 Card 的视图
- importance（人工策展）≠ score（AI 实时打分）

---

## 3. API-Driven UI

- HTML shell + Vanilla JS `fetch()` API，数据动态获取
- 不引入 SSR（服务端渲染）
- 不引入前端框架（React/Vue），保持零依赖

---

## 4. File-Driven Architecture

- 不引入 ORM，Python 直接读写文件/DB
- SQLite WAL 模式，外键约束
- 配置用 YAML，存储用 JSONL + Markdown

---

## 5. AI Backend Simplicity

- 双后端 DeepSeek + Kimi，OpenAI 兼容协议
- `_call_openai_compatible()` 工厂函数，移除所有 provider 特定代码
- 重试：指数退避，最多 3 次（1.5s / 3s / 6s）

---

## 6. Test Before Commit

- 每次修改后跑 `uv run pytest tests/ -q`
- 不通过不提交
- 当前基线：357 tests, 0 failures

---

## 7. Naming & Organization

- 文件名/卡片 ID：kebab-case
- 日报：`reports/YYYY-MM-DD.md`
- 卡片：`data/knowledge/{type}/{id}.yaml`
- tags 不嵌套，平铺

---

## 8. Knowledge Layering（知识分层）

> 借鉴 neat-freak 技能。不同层次的文档有不同受众和职责，不能混在一起。

| 层次 | 文件 | 受众 | 职责 |
|------|------|------|------|
| Agent 交接 | `.private/HANDOVER.md` | AI 自己跨会话 | 上次做到哪了、当前状态、快速参考 |
| 工程规则 | `ENGINEERING.md` + `PROJECT_MEMORY.md` | 当前项目 AI | 怎么做决策、长期约定 |
| 对外文档 | `docs/ARCHITECTURE.md` `ROADMAP.md` `README.md` | 人类同事 | 系统怎么工作、怎么接入 |

**规则**:
- CLAUDE.md / ENGINEERING.md 是规则手册，不是变更日志。历史叙事归 git log
- "X 时刻起 Y 上线" 不属于规则文件 → 进 git log 或 docs/CHANGELOG
- 同主题内容合并进已有段落，不追加新段

---

## 9. End-of-Session Sync（会话结束同步）

两级机制：默认只做轻量交接，明确要求时才做完整归档。

### 9a. 轻量交接（默认）

触发词："整理一下" / "收尾" / "sync up"

**只允许更新 `.private/HANDOVER.md`**。目标：让下一次会话能接上，不追求完整复盘。

追加格式：
```md
## YYYY-MM-DD 轻量交接

### 本轮完成
- 

### 当前状态
- 

### 未解决
- 

### 下次优先
- 

### 注意
- 
```

轻量交接**禁止**：
- 不扫描全项目、不读取无关目录
- 不修改源码、ENGINEERING、ARCHITECTURE、ROADMAP、TASKS
- 不修改全局工作区规则文件
- 不移/删文件
- 不 commit（除非用户要求）

### 9b. 阶段性归档（显式触发）

触发词："完整归档" / "全面同步" / "full sync" / "做一次完整交接"

此时才启用变更影响矩阵：

| 本次改了什么 | HANDOVER | PROJECT_MEMORY | ARCHITECTURE | ROADMAP | ENGINEERING | CODEX_HANDOFF | TASKS | memory |
|------------|----------|---------------|-------------|---------|-------------|---------------|-------|--------|
| 任何开发 | ✅ 追加摘要+指标 | — | — | — | — | — | — | — |
| 新约定/陷阱/经验 | — | ✅ 追加对应 § | — | — | — | — | — | — |
| 架构变化（新模块/新路由/DB表） | — | — | ✅ 更新章节 | — | — | — | — | — |
| 里程碑完成 | — | — | — | ✅ 标记 | — | — | — | — |
| 文件拆分/合并 | — | — | — | — | ✅ 更新状态表 | — | — | — |
| 前端改动 | — | — | — | — | — | ✅ 更新 §3+§11 | — | — |
| 任务完成 | — | — | — | — | — | — | ✅ 更新状态 | — |
| 跨会话教训/踩坑 | — | — | — | — | — | — | — | ✅ 写入 |

### 文档读取最小化

无论哪种级别，不要默认读取所有文档。只基于会话上下文 + HANDOVER.md。仅在确实必要时才读 TASKS / ARCHITECTURE / ENGINEERING / ROADMAP。不确定时先问用户。

### 尺寸体检

| 文件 | 警戒线 | 超标动作 |
|------|--------|----------|
| `.private/HANDOVER.md` | >300 行 | 压缩历史会话，只保留最近 3 次 |
| `docs/ARCHITECTURE.md` | >500 行 | 拆分子文档 |
| `.private/PROJECT_MEMORY.md` | >250 行 | 稳定内容"毕业"进 docs/，原处只留指针 |

执行顺序：**先精简（破除膨胀）→ 再按需更新 → 用户决定是否 commit**。

---

## 10. Reduce > Add（减优于加）

- **删优于留**: 完成的临时计划、被推翻的决策、单次事故复盘 → 删
- **并优于追**: 新信息改旧条目，不追加新段落。新增前先 grep 同关键字
- **毕业优于挪腾**: 一条信息被引用 3 次以上 → 从 memory/HANDOVER "毕业"进 docs/，原处缩成一行指针或删除

---

## 11. Routing Priority（路由优先级）

> 借鉴 aihot。"默认精选、明确要全部才给全部" 的原则应贯穿所有用户面接口。

### 核心规则

```
用户问得宽 → 默认精选/高分 → 用户明确要"全部" → 才走全量
```

### 各模块应用

| 模块 | 默认行为 | "全部"触发词 | 实现位置 |
|------|---------|-------------|----------|
| 卡片搜索 | 关键词即时匹配 → 无结果才语义兜底 | — | `library.py:filterEntities()` |
| Concept Miner | 仅处理 ★3+ 文章 | — | `pipeline_stages.py:Stage 7` |
| 文章列表 | `min_score=3` | "全部文章" / "包括低分" | API `/api/articles` |
| 知识图谱 | `depth=1`（直接邻居） | "完整图谱" / "展开全部" | API `/api/graph` |
| 研究报告 | 精选关联卡片 + ★3+ 文章 | "穷尽式研究" / "不设限制" | Research Agent |

### 判断流程

```
用户输入
  ├─ 含"全部/完整/所有/全量/穷尽" → 全量模式
  ├─ 含具体名称/关键词 → 精确匹配优先
  └─ 宽泛问题 → 精选/高分/默认限制
```

---

## 12. Business Anti-Patterns（业务反模式）

> 区别于 §1 的上下文反模式（性能/读取类）。这里是业务层面的常犯错误。

| # | 反模式 | 为什么错 | 正确做法 |
|---|--------|---------|----------|
| 1 | **输出不带来源 URL** | 信息不可追溯 = 不可信 | 每条卡片/文章必须附原始链接 |
| 2 | **把 AI 摘要当原文引用** | 摘要是 LLM 生成的，可能偏离原意 | 引用需回 `url`/`sourceUrl` 核对 |
| 3 | **向用户暴露内部参数** | `semantic=true`、`depth=1` 用户看不懂 | 用人话元信息替代（"按相关性排序"） |
| 4 | **凭训练数据回答 AI 行业问题** | 训练截止日早于平台数据 | 永远先查 API / Knowledge Base |
| 5 | **混淆 importance 和 score** | importance=人工策展，score=AI打分，含义不同 | 展示时标注来源（"编辑推荐" vs "AI 评分"） |
| 6 | **输出 ISO 时间字符串** | `2026-07-04T09:48:00Z` 普通人看不懂 | 转北京时间 + 相对时间（"3小时前"） |
| 7 | **把关系图谱的边当作权威事实** | 边来自 `related` 字段，可能是弱关联 | 标注关系类型和来源 |
| 8 | **默认全量而非精选** | 用户说"查一下 X"不是要看 100 条 | 默认 top-5 匹配，用户要更多再翻页 |
| 9 | **并发猛拉 API** | 600 req/min 限制，并发可能触发限流 | 串行 + 200ms 间隔 |
| 10 | **编造不存在的关联** | 知识图谱只反映 Card 的 `related` 字段 | 不确定时标注"未在知识库中找到直接关联" |
