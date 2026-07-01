# AI Intelligence Platform — 项目大脑

> 记录"这个项目为什么存在、现在是什么、怎么做的、踩过什么坑"。
> 不记录历史细节——历史见 OPENSPEC_原始设计.md / CHANGELOG_变更日志.md / HANDOVER_项目交接.md。
> 最后更新: 2026-07-01 (V1.8)

---

## 1. Project Identity

- **项目名称**: AI Intelligence Platform（AI 智能情报平台）
- **一句话**: 每天从 RSS 自动抓取 AI 资讯，AI 处理后生成中文日报，积累知识卡片构建知识图谱
- **组件**: News / Knowledge / Graph / Research
- **状态**: 🟢 活跃（V1.8）
- **SSOT**: Knowledge Card（YAML）是整个系统的唯一事实来源

---

## 2. Core Goals

- 📰 **日报**: 每天自动生成 5-10 分钟读完的中文 AI 新闻日报
- 🃏 **知识卡片**: 积累高质量结构化知识实体（模型/公司/人物/技术/概念/产品/方法论）
- 🕸️ **知识图谱**: 实体之间建立关系，可视化 AI 行业演进
- 🔬 **研究助手**（远期）: 基于知识库做深度检索和分析

---

## 3. Current Version — V1.8

### 数据管道
| 模块 | 触发 | 说明 |
|------|------|------|
| Collector | 每小时 | RSS → 去重 → inbox.jsonl |
| Daily Pipeline | 每天 9:00 | inbox → 分类 → 概念挖掘 → 卡片匹配 → 摘要 → 评分 → 日报 |
| Weekly Report | 每周日 | 汇总 7 天日报 → AI 趋势分析 |
| Monthly Report | 每月 1 日 | 汇总 30 天日报 → AI 趋势分析 |

### Web 服务 (FastAPI :8765)
| 页面 | 路由 | 说明 |
|------|------|------|
| Dashboard | `/` | 报告入口 + Top Stories + Report History |
| Library | `/library` | 知识资产库 |
| Graph | `/graph` | 知识图谱（Mermaid + D3.js） |
| Timeline | `/timeline` | AI 行业时间线 |
| Entity Detail | `/entity/{id}` | 实体详情页 |

### 关键数字
- 文章: 283 篇（268 篇已 AI 评分）
- 实体: 61 张（7 种类型）
- 关系: 383 条
- 报告: 日报×4 + 周报×1
- 测试: 147 个，全部通过
- 草稿卡: 155 张（methodology，Concept Miner 自动生成，待审核）
- 语言: 5 页中英文切换，技术术语采用 "Model（模型）" 双语格式

---

## 4. Architecture Decisions（不可轻易推翻）

> 完整 ADR 详情见 [`DECISIONS_架构决策记录.md`](DECISIONS_架构决策记录.md)：ADR-001 ~ ADR-011。

| # | 决策 | 理由 |
|---|------|------|
| 1 | Knowledge Card (YAML) 是 SSOT | 所有模块只读 Card，唯一写入路径是手动编辑或 Concept Miner |
| 2 | SQLite 而非 PostgreSQL | 零配置，单人使用足够，WAL 模式读写不冲突 |
| 3 | API-driven UI | HTML shell + JS fetch，数据变化无需重新生成页面 |
| 4 | Jaccard 匹配而非 Embedding | 零成本，可离线 |
| 5 | importance（人工策展）≠ score（AI 实时打分） | 前者是长期价值，后者是新闻热度 |
| 6 | 文件驱动而非 ORM | 简单透明，Python 直接读写 |
| 7 | Collector 与 Pipeline 分离 | Collector 无 AI 依赖，Pipeline 才是 AI 处理入口 |
| 8 | `INSERT OR REPLACE`（非 IGNORE） | Pipeline 处理后必须覆写裸数据 |
| 9 | 并发摘要用 ThreadPoolExecutor | DeepSeek/Kimi API 每批次 ~30s，3 并发可将 27 批缩短到 ~278s |
| 10 | 双后端 DeepSeek + Kimi | 移除了 Anthropic（使用 DeepSeek 兼容端点转发），保留两个原生 OpenAI 兼容后端 |
| 11 | Context Budget Rule | 一个 Conversation 一个 Feature；>300行文件必须拆分；60%收尾/70%完成/75% compact |
| 12 | Claude-Codex 三层协作协议 | `frontend_styles.py` 版本号（Layer A）→ `CODEX_HANDOFF.md` §3 会话状态（Layer B）→ §11 变更日志（Layer C）。Codex 启动时读取 §3+§11 自动感知变更 |

---

## 5. 技术栈

| 层 | 选型 | 版本 |
|----|------|------|
| 语言 | Python | 3.13 |
| AI 引擎 | DeepSeek + Kimi | 双后端 OpenAI 兼容 |
| Web 框架 | FastAPI | — |
| 数据库 | SQLite (WAL mode) | — |
| 包管理 | uv | — |
| 配置 | YAML | — |
| 存储 | JSONL (inbox) + YAML (cards) + Markdown (reports) | — |
| 调度 | Windows Task Scheduler | — |
| 前端 | Vanilla JS + fetch API | — |

---

## 6. Entity Types（7 种）

| Type | 说明 | 数量 | 颜色 |
|------|------|------|------|
| `model` | AI 模型 | 13 | `#4C78A8` |
| `company` | AI 公司 | 10 | `#F58518` |
| `tech` | 核心技术 | 4 | `#72B7B2` |
| `concept` | AI 概念 | 4 | `#E45756` |
| `product` | AI 产品 | 3 | `#54A24B` |
| `person` | AI 人物 | 10 | `#B279A2` |
| `methodology` | 方法论 | 17+ | `#D4A017` |

**规则**: 新增 type 先写 5 张卡验证，再回来补 Schema。

---

## 7. Methodology Taxonomy（8 种）

Prompt Engineering / Tool Use / Context Engineering / Harness Engineering / Long-Running Agent / Memory Architecture / Planning / Reflection

---

## 8. 命名与目录规范

- **文件名**: kebab-case（`concept-miner.py`, `knowledge-graph.html`）
- **卡片 ID**: kebab-case（`gpt-4`, `prompt-engineering`）
- **日报**: `reports/YYYY-MM-DD.md`
- **周报**: `reports/weekly-YYYY-MM-DD.md`
- **月报**: `reports/monthly-YYYY-MM.md`
- **卡片**: `data/knowledge/{type}/{id}.yaml`

---

## 9. 已知陷阱

| 陷阱 | 表现 | 解决 |
|------|------|------|
| f-string 中 `\'` 不转义 | Python 吃掉反斜杠，JS 收到裸引号导致 `Unexpected identifier` | 用 `\\'` 在 Python 中产生 JS 的 `\'` |
| `INSERT OR IGNORE` 导致 AI 数据无法覆写 | 裸数据（score=0）不会被处理后的数据覆盖 | 改用 `INSERT OR REPLACE` |
| Pipeline 只写文件不同步 DB | `/api/reports` 返回 `[]` | 调用 `insert_report()` |
| 周报/月报未写 DB | 只生成文件 | pipeline.py 增加 `insert_report()` |
| `--limit 10` 不生效 | 只解析 `--limit=10` | 同时支持 `--limit 10` |
| Anthropic API 偶尔返回无法解析的 JSON | thinking block 或格式异常 | 指数退避重试（最多 3 次） |
| Concept Miner 生成低质量草稿卡 | 自动生成大量论文概念卡片 | 定期人工审核 data/knowledge/methodology/ 目录 |
| CMD 编码不匹配导致中文乱码 | 第三方 App 中文输出到 GBK 终端 | 卸载问题软件 (EleBank) 或开启 UTF-8 全局支持 |
| Claude Code 上下文爆炸 | 单会话连续开发多模块 → diff 记录占满上下文 | 一个 Conversation 一个 Feature；>300行文件拆分；75% compact |

---

## 10. 调度表

| 任务 | 频率 | 时间 |
|------|------|------|
| Collector | 每小时 | 8:00 起 |
| Daily Pipeline | 每天 | 9:00 |
| Weekly Report | 每周日 | 10:00 |
| Monthly Report | 每月 1 日 | 10:00 |

---

## 11. 永久约束

- ❌ Knowledge Card 只读不写（唯一写入路径: 手动编辑 YAML 或 Concept Miner 生成草稿）
- ❌ tags 不嵌套，平铺
- ❌ 不引入 ORM，保持文件驱动
- ❌ 不引入 SSR，保持 API-driven HTML shell
- ❌ 不扫描整个项目（AI 启动规则见 SESSION_RULES_会话规则.md）
- ❌ README.md 不给 AI 读（Human Only）
- ✅ 所有文件 <300 行（knowledge_graph.py → kg_data/kg_mermaid/kg_d3; timeline.py → timeline_data/timeline_renderer）
- ✅ Timeline 不存数据，只是 Card 的时间视图
- ✅ importance ≠ score
- ✅ 卡片匹配用 Jaccard
- ✅ 新增 type 先写 5 张卡验证
- ✅ 前端 UI 全中文（TYPE_LABELS 统一为中文）
