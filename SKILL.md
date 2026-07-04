---
name: ai-news
description: AI 智能情报平台 — News / Knowledge / Graph / Research。当用户想知道 AI 行业动态、查询知识卡片、搜索实体关系、生成研究报告、查看今日 AI 新闻时使用。触发词："AI 情报"、"知识库"、"查一下"、"研究一下"、"AI 动态"、"知识图谱"、"最近 AI 新闻"、"帮我做个研究"、"AI日报"。
---

# AI Intelligence Platform — AI Agent 使用手册

让外部 AI Agent（Claude Code / Codex / Cursor / 任何兼容平台）用最自然的中文查询调用本平台的知识库、研究引擎和情报流水线。

## 能力速览

| 能力 | 入口 | 适用场景 |
|------|------|----------|
| 知识卡片查询 | API `/api/entities` + 语义搜索 | "查一下 Transformer"、"OpenAI 这家公司" |
| 知识图谱遍历 | API `/api/graph` | "GPT-4 和哪些论文相关" |
| 研究报告生成 | Research Agent (Pipeline触发) | "帮我深度研究一下 AI Agent 框架" |
| 今日 AI 动态 | API `/api/articles?hours=24` | "今天 AI 圈发生了什么" |
| 趋势分析 | Trend Reporter (Pipeline触发) | "最近一周 AI 行业趋势" |
| 概念发现 | Concept Miner (Pipeline触发) | "有什么新兴的 AI 概念" |
| 时间线浏览 | API `/api/timeline` | "大模型发展历程" |

## 路由优先级（核心原则）

```
用户问得宽 → 默认精选/高分 → 用户明确要"全部" → 才走全量
```

| 用户说的 | 走什么 |
|---------|--------|
| "查一下 Transformer"、"GPT-4 是什么" | 语义搜索 → 返回最匹配的 5 张卡片 |
| "AI Agent 相关的内容" | 语义搜索 → 返回匹配卡片 + 知识图谱邻居 |
| "列出所有卡片"、"全部实体" | 全量列表，分页返回 |
| "最近一周 AI 趋势" | Pipeline 日报，最近 7 天 |
| "深度研究一下 X" | Research Agent，不设时间窗 |
| "今天 AI 圈" | 最近 24h ★3+ 文章摘要 |

## 工作流

### 1. 知识卡片查询（最常用）

```bash
# 语义搜索 — 模糊匹配
curl -s "http://localhost:8765/api/search?q=Transformer&semantic=true&limit=5"

# 精确匹配 — 按 type 筛选
curl -s "http://localhost:8765/api/entities?type=model&limit=20"

# 单张卡片详情
curl -s "http://localhost:8765/api/entities/gpt-4"
```

返回字段：`id` / `name` / `type` / `summary` / `significance` / `related` / `timeline` / `source_articles`

### 2. 知识图谱遍历

```bash
# 查看某实体的关系网络
curl -s "http://localhost:8765/api/graph?entity=gpt-4&depth=1"

# 全局图谱数据
curl -s "http://localhost:8765/api/graph?mode=full"
```

### 3. 今日 AI 动态

```bash
# 最近 24 小时文章
curl -s "http://localhost:8765/api/articles?hours=24"

# ★3+ 高评分文章（精选）
curl -s "http://localhost:8765/api/articles?hours=24&min_score=3"
```

### 4. 研究报告生成

```bash
# 触发研究流水线
curl -s -X POST "http://localhost:8765/api/pipeline/research" \
  -H "Content-Type: application/json" \
  -d '{"topic": "AI Agent 框架", "depth": "standard"}'
```

标准深度耗时 ~60s，深度模式 ~180s。返回 markdown 格式研究报告。

### 5. 每日报告

```bash
# 生成今日报告
uv run python pipeline.py --hours 24

# 查看已生成报告
ls reports/$(date +%Y-%m-%d).md
```

---

## 数据模型速查

### Entity Type（8 种）

| type | 中文 | 示例 |
|------|------|------|
| `model` | AI 模型 | GPT-4, Claude 5, Gemini |
| `company` | 公司/组织 | OpenAI, Anthropic, Google |
| `product` | 产品 | ChatGPT, Cursor, Claude Code |
| `methodology` | 方法/技术 | RAG, Chain-of-Thought, MoE |
| `tech` | 底层技术 | Transformer, Diffusion, RLHF |
| `concept` | 概念/范式 | AGI, Alignment, Scalable Oversight |
| `person` | 人物 | Sam Altman, Dario Amodei |
| `event` | 事件/里程碑 | GPT-4 发布, OpenAI DevDay |

### Article 评分体系

| 星级 | 含义 | 过滤策略 |
|------|------|----------|
| ★★★★★ | 必读 | 全部保留 |
| ★★★★ | 重要 | 全部保留 |
| ★★★ | 值得关注 | 保留（默认精选底线） |
| ★★ | 可读 | 仅"全部"模式显示 |
| ★ | 可跳过 | 仅"全部"模式显示 |

---

## 输出格式规则

> 这些规则适用于 Agent 向用户展示结果。目标：普通人能看懂、能追溯、不被技术细节干扰。

### 时间转人话

| 内部值 | 展示给用户 |
|--------|-----------|
| `2026-07-04T09:48:00.000Z` | "今天下午 17:48" / "3 小时前" |
| `2026-07-03T18:08:17.000Z` | "昨天凌晨 02:08" / "昨晚" |
| `2026-07-01T10:00:00.000Z` | "7/1 18:00" |

UTC → 北京时间(+8)，展示相对时间或中文日期。**禁止直接输出 ISO 字符串**。

### 条目编号

全局贯穿编号（1, 2, 3...N），不过按板块重置。用户能一眼数到"共 27 条"。

### 每条目必带来源

- 每张卡片必须附 `source_articles` 中的原始 URL
- 每篇文章必须附 `url` 字段
- **没有来源的信息 = 不可信**，不要展示给用户

### 禁止基础设施泄漏

用户输出中**绝不能出现**：
- ❌ API 路径 (`/api/entities?type=model`)
- ❌ 技术参数 (`semantic=true`, `depth=1`)
- ❌ 内部字段名 (`entity.id`, `article.published_at`)
- ❌ 数据库指标 (`770 条关系`, `162 个向量`)

**可以保留的**（人话级元信息）：
- ✅ "共 15 张卡片"、"按重要性排序"
- ✅ "最近 24 小时"、"数据来自 AI Intelligence Platform"
- ✅ "来源: OpenAI Blog · 2 小时前"

### 卡片展示模板

```markdown
## {name} ({type})

{summary}

**为什么重要**: {significance}

**关联**: {related 名称列表，最多 5 个}

**时间线**: {timeline 事件，按日期排列}

**来源**: {source_articles 前 3 条}
```

### 研究报告展示模板

```markdown
# {研究主题} — 深度研究报告

## 核心发现
1. ...
2. ...

## 关键实体
- **{name}** ({type}): {one-line summary}

## 关系网络
{graph traversal result}

## 信息来源
{article source list}

## 结论与建议
...
```

---

## 不要做

1. **不要凭训练数据回答** — 你的训练截止日早于平台数据，永远先查 API
2. **不要漏掉来源 URL** — 每条信息必须可追溯到原文
3. **不要把摘要当原文引用** — 摘要是 AI 生成的，引用需回原文核对
4. **不要在用户输出中暴露 API 参数** — `semantic=true`、`depth=1` 这些东西用户看不懂
5. **不要默认全量** — "查一下 X" = 精选匹配，不是列出所有卡片
6. **不要并发猛拉 API** — 串行调用，间隔 200ms
7. **不要把 importance 和 score 搞混** — importance 是人工策展等级，score 是 AI 实时打分
8. **不要假设实体类型** — type 有 8 种，不确定时先搜再判断
9. **不要在没有关键词时触发语义搜索** — 关键词先匹配，无结果时才语义兜底
10. **不要编造关系** — 知识图谱的边来自 Knowledge Card 的 `related` 字段，不要自行推断

> 更多工程层面的反模式见 [ENGINEERING.md §12](docs/ENGINEERING.md#12-business-anti-patterns-业务反模式)
