# ARCHITECTURE.md — AI Intelligence Platform

> 系统架构文档。给需要理解代码结构、做技术决策或接手开发的人看。

---

## 1. 总体架构

```
┌──────────────────────────────────────────────────────────────────┐
│                        AI Intelligence Platform                   │
│                                                                  │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────┐  │
│  │ Collector │   │ Pipeline │   │ FastAPI   │   │ Web Pages    │  │
│  │ (每小时)  │   │ (每天)   │   │ :8765     │   │ Dashboard    │  │
│  │           │   │          │   │           │   │ Library      │  │
│  │ RSS抓取   │   │ 9阶段管道 │   │ 8 API     │   │ Graph        │  │
│  │ 去重      │   │ AI处理   │   │ 4 Pages   │   │ Timeline     │  │
│  │ inbox写入 │   │ 日报生成 │   │ Static    │   │              │  │
│  └─────┬─────┘   └────┬─────┘   └─────┬─────┘   └──────┬───────┘  │
│        │              │               │                │          │
│        └──────────────┼───────────────┼────────────────┘          │
│                       │               │                           │
│                  ┌────▼──────┐  ┌─────▼──────┐                    │
│                  │ inbox.jsonl│  │  SQLite    │                    │
│                  │ (追加写)   │  │ platform.db│                    │
│                  └────────────┘  └─────┬──────┘                    │
│                                        │                          │
│                                   ┌────▼──────┐                   │
│                                   │ Knowledge  │                   │
│                                   │ Cards (61) │                   │
│                                   │ YAML files │                   │
│                                   └────────────┘                   │
└──────────────────────────────────────────────────────────────────┘
```

### 设计原则

| 原则 | 说明 |
|------|------|
| **线性管道** | 每个阶段独立，输入→处理→输出，不跳跃 |
| **SSOT 单一事实源** | Knowledge Card 是唯一写入点，所有模块只读 |
| **文件驱动** | 卡片是 YAML，Prompt 是 Markdown，数据是 SQLite |
| **AI 集中调用** | 分类/摘要/评分/概念挖掘 通过统一的 `ai_client.py` |
| **API-driven UI** | 页面是静态 HTML shell，数据通过 `/api/*` 实时获取 |
| **配置外置** | RSS 源、分类体系、Prompt 全部独立文件 |

---

## 2. 数据层 (SQLite)

### 2.1 为什么选 SQLite

- 零配置，不需要单独数据库服务
- WAL 模式支持并发读（读不阻塞写）
- 外键约束保证数据完整性
- 单文件，备份就是 `cp platform.db`
- 单人使用场景下性能绰绰有余

### 2.2 Schema

```sql
-- 实体 (Knowledge Cards)
CREATE TABLE entities (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    type        TEXT NOT NULL,          -- model/company/tech/concept/methodology/product/person/event
    importance  INTEGER DEFAULT 3,      -- 1-5 人工策展评分
    summary     TEXT DEFAULT '',
    significance TEXT DEFAULT '',
    release_date TEXT DEFAULT '',
    company     TEXT DEFAULT '',
    tags        TEXT DEFAULT '[]',      -- JSON array
    aliases     TEXT DEFAULT '[]',      -- JSON array
    timeline    TEXT DEFAULT '[]',      -- JSON array of {date, event}
    color       TEXT DEFAULT '#999',
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

-- 关系
CREATE TABLE relationships (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id   TEXT NOT NULL REFERENCES entities(id),
    target_id   TEXT NOT NULL REFERENCES entities(id),
    rel_type    TEXT NOT NULL,          -- depends_on/influenced/develops/uses/competes_with
    label       TEXT DEFAULT '',
    UNIQUE(source_id, target_id, rel_type)
);

-- 文章
CREATE TABLE articles (
    id          TEXT PRIMARY KEY,       -- MD5(url)
    title       TEXT NOT NULL,
    url         TEXT NOT NULL,
    source      TEXT DEFAULT '',
    published   TEXT DEFAULT '',
    content_raw TEXT DEFAULT '',
    categories  TEXT DEFAULT '[]',      -- JSON array
    title_cn    TEXT DEFAULT '',
    one_liner   TEXT DEFAULT '',
    summary_points TEXT DEFAULT '[]',   -- JSON array
    score       INTEGER DEFAULT 0,      -- 1-5 AI评分
    score_reason TEXT DEFAULT '',
    cluster_id  TEXT DEFAULT '',
    created_at  TEXT DEFAULT (datetime('now'))
);

-- 报告
CREATE TABLE reports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL UNIQUE,
    report_type TEXT DEFAULT 'daily',   -- daily/weekly/monthly
    path        TEXT NOT NULL,
    fetched     INTEGER DEFAULT 0,
    filtered    INTEGER DEFAULT 0,
    star5       INTEGER DEFAULT 0,
    star4       INTEGER DEFAULT 0,
    star3       INTEGER DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now'))
);
```

### 2.3 索引策略

```sql
CREATE INDEX idx_entities_type ON entities(type);
CREATE INDEX idx_relationships_source ON relationships(source_id);
CREATE INDEX idx_relationships_target ON relationships(target_id);
CREATE INDEX idx_articles_published ON articles(published);
CREATE INDEX idx_articles_score ON articles(score);
CREATE INDEX idx_reports_date ON reports(date);
```

### 2.4 JSON 字段处理

`tags`、`aliases`、`timeline`、`categories`、`summary_points` 以 JSON 字符串存储。
读写时通过 `json.dumps(data, default=str)` 和 `json.loads()` 做序列化/反序列化。
`default=str` 处理 `datetime.date` 等不可序列化类型。

### 2.5 连接管理

每次操作获取独立连接（`get_db()`），操作完后立即关闭。不保持长连接——SQLite 的 WAL 模式让这个模式的性能损失可忽略。

---

## 3. API 层 (FastAPI)

### 3.1 设计决策

| 决策 | 理由 |
|------|------|
| `lifespan` 而非 `on_event` | FastAPI 推荐，避免 deprecation warning |
| `HTTPException` 而非 tuple return | 保证 404 状态码正确返回 |
| CORS `allow_origins=["*"]` | 单人本地使用，不需要来源限制 |
| Static files 挂载 `/reports` | 日报/周报/月报 Markdown 可通过 URL 直接访问 |
| 页面是 `FileResponse` | 静态 HTML shell 文件，数据通过 JS fetch API 获取 |

### 3.2 路由表

```
页面路由 (9):
  GET /               → Dashboard (今日)
  GET /library        → Library (专题)
  GET /timeline       → Timeline (时间线)
  GET /events         → Events (里程碑)
  GET /graph          → 2D Knowledge Graph
  GET /graph-3d       → 3D Knowledge Graph
  GET /entity/{id}    → Entity Detail
  GET /research       → Research Workbench
  GET /my             → My Favorites

API 路由 (20+):
  GET /api/health                          → {"status": "ok"}
  GET /api/entities?type=model&page=1      → [Entity, ...] (分页)
  GET /api/entities/{entity_id}            → Entity + relationships
  GET /api/entities/{id}/versions           → 版本历史
  POST/PUT/DELETE /api/entities             → 写操作
  GET /api/relationships?entity_id=xxx      → [Relationship, ...]
  POST/DELETE /api/relationships            → 写操作
  GET /api/articles?limit=50&page=1         → [Article, ...] (分页)
  GET /api/articles/{article_id}            → Article by ID
  GET /api/reports?type=daily               → [Report, ...]
  GET /api/search?q=GPT&semantic=true       → {entities, articles}
  GET /api/stats                            → 统计
  POST /api/research                        → Research Agent
  POST /api/pipeline/run                     → 手动触发 Pipeline
  GET /api/export                           → 数据导出
  GET/POST /api/migrations                  → 迁移管理
  POST /api/embeddings/rebuild              → 重建嵌入

静态文件:
  /report-files/*                           → reports/ 目录下的 Markdown 文件
```

### 3.3 API-driven UI 模式

所有页面（Dashboard、Library、Graph、Timeline）使用相同模式：

```
1. HTML shell 加载 → 显示 loading spinner
2. JS async init() 函数 fetch /api/* 端点
3. 数据到达 → 纯客户端渲染 innerHTML
4. 数据变化时只需重新加载页面，无需重新生成 HTML
```

例外：Graph 页面使用 D3.js force-directed graph，数据量大，渲染逻辑更复杂。

---

## 4. Pipeline 管道

### 4.1 9 阶段详解

```
Stage 1: 数据源选择
  - 默认: 从 data/inbox.jsonl 读取（近 N 小时）
  - --fetch-direct: 直接从 RSS 抓取
  - --dry-run: 只抓取+去重，不调 AI

Stage 2: 去重 (dedup.py)
  - URL 精确匹配
  - 标题 Jaccard 相似度 > 0.85
  - 7 天 seen_urls 缓存

Stage 3: AI 分类 (classifier.py)
  - 批量调用，每批 20-30 篇
  - 从 config.yaml 分类体系中匹配 1-3 个标签
  - Prompt: prompts/classify.md

Stage 4: 概念挖掘 (concept_miner.py)
  - 从文章内容中抽取候选新概念
  - 维护候选池 (candidate_concepts.json)
  - 3 次出现 → 自动生成草稿 Knowledge Card

Stage 5: 知识匹配 (knowledge.py)
  - 加载所有 YAML 卡片
  - Jaccard 相似度匹配文章 ↔ 卡片
  - 构建历史上下文字符串（注入摘要 prompt）

Stage 6: AI 摘要 (summarizer.py)
  - 英文 → 中文标题 + 一句话 + 三点摘要
  - 接受 knowledge_context 参数
  - Prompt: prompts/summarize.md

Stage 7: AI 评分 (scorer.py)
  - 1-5 星 + 评分理由
  - 注入用户兴趣权重 (config.yaml)
  - Prompt: prompts/score.md

Stage 8: 日报生成 (reporter.py)
  - 按分数降序排列
  - 星级分组展示
  - Markdown 格式 + 目录

Stage 9: 同步 + 刷新
  - 文章 + 报告写入 SQLite
  - 重新生成 Dashboard / Library / Timeline HTML
```

### 4.2 中间数据结构

```python
Article = {
    # Fetcher 产出
    "id": "md5(url)",
    "title": "原始标题",
    "url": "https://...",
    "source": "TechCrunch",
    "published": "2026-06-29T10:00:00Z",
    "content_raw": "原始摘要或正文...",

    # Classifier 产出
    "categories": ["大模型发布", "Agent"],

    # Summarizer 产出
    "title_cn": "OpenAI 发布 GPT-6 Preview",
    "one_liner": "一句话概括",
    "summary_points": ["点1", "点2", "点3"],

    # Scorer 产出
    "score": 5,
    "score_reason": "行业里程碑发布"
}
```

### 4.3 周报/月报分支

独立于日报管道，不经过 Stage 3-7：

```
加载近 N 天日报 Markdown
  → trend_reporter.py
  → AI 识别趋势/信号/新玩家
  → 生成周报/月报 Markdown
```

---

## 5. Knowledge Card 系统

### 5.1 卡片即 SSOT

Knowledge Card 是整个平台的唯一事实来源（Single Source of Truth）。

- 存储在 `data/knowledge/<type>/<id>.yaml`
- 所有模块只读卡片，通过 `knowledge.py` 的 `load_cards()` 加载
- 唯一写入路径：手动编辑 YAML 或 Concept Miner 自动生成草稿

### 5.2 匹配算法 (Jaccard)

```python
def match_cards(articles, cards):
    for article in articles:
        keywords = extract_keywords(article)  # title + categories
        for card in cards:
            overlap = keywords ∩ (card.name + card.aliases + card.tags)
            if jaccard(overlap) > threshold:
                matched[article.id].append(card)
```

### 5.3 上下文构建

匹配到的卡片被格式化为上下文文本块，注入到摘要 prompt 中：

```
📚 历史背景：
- GPT-4 (OpenAI, 2023-03): 首个多模态 LLM, ★5 ...
- RLHF (2017): 让模型对齐人类偏好的核心技术 ...
关联: GPT-4 使用了 RLHF 进行训练对齐
```

---

## 6. Concept Miner (概念发现器)

### 6.1 算法流程

```
文章批次 (每批 20-30 篇)
  → AI 抽取候选概念 (name, type, confidence, evidence)
  → 过滤: 检查是否已被已有卡片覆盖 (模糊匹配)
  → 更新候选池:
      1 次出现   → 候选池 (candidate)
      2 次出现   → 生成草稿卡片 (draft)
      3+ 次出现  → 确认 (confirmed)
      高权威源 + 高置信度 → 加速确认
```

### 6.2 候选池

存储在 `data/candidate_concepts.json`：

```json
{
  "candidates": {
    "agent-orchestration": {
      "name": "Agent Orchestration",
      "type": "technique",
      "occurrences": 2,
      "confidence_sum": 1.6,
      "first_seen": "2026-06-20T...",
      "last_seen": "2026-06-28T...",
      "sources": ["Anthropic Research", "ArXiv AI"],
      "evidence": ["...", "..."],
      "status": "draft"
    }
  }
}
```

### 6.3 自动草稿卡片

`status == "draft"` 或 `"confirmed"` 时，自动在 `data/knowledge/methodology/<slug>.yaml` 生成草稿卡片。
卡片标记 `auto-generated` + `candidate` tags，importance=2，需要人工审查补充。

---

## 7. 知识图谱

### 7.1 构建逻辑

```python
def build_graph():
    cards = load_cards()
    nodes = [card_to_node(c) for c in cards]       # 162 nodes
    edges = []
    for card in cards:
        for related_id in card.related:
            edges.append((card.id, related_id, "depends_on"))
        # 也连接同公司/同类型的实体
    return {"nodes": nodes, "edges": edges}
```

### 7.2 双输出

| 格式 | 文件 | 用途 |
|------|------|------|
| Mermaid | `knowledge-graph.md` | 可嵌入 Markdown 文档 |
| D3.js HTML | `knowledge-graph.html` | 交互式拖拽探索 |

### 7.3 D3.js 实现

- 力导向图 (force-directed)，`d3.forceSimulation()`
- 节点颜色按 type 区分
- 节点大小按 importance 缩放
- 侧边栏：按类型分组的实体列表
- 点击节点 → 详情面板显示完整卡片信息
- 支持节点拖拽、缩放、平移

---

## 8. AI 客户端

### 8.1 双后端支持

`ai_client.py` 通过 `AI_PROVIDER` 环境变量切换后端：

| Provider | SDK | 说明 |
|----------|-----|------|
| `deepseek` | OpenAI SDK | `DEEPSEEK_API_KEY` + `DEEPSEEK_BASE_URL` |
| `kimi` | OpenAI SDK | `KIMI_API_KEY` + `KIMI_BASE_URL` |

> Anthropic 端点已移除，改用 DeepSeek 兼容代理转发 Anthropic 格式请求。

### 8.2 统一接口

```python
def call_ai(system: str, user: str, max_tokens=4096) -> list[dict] | None:
    """所有 AI 调用的统一入口。返回解析后的 JSON list，失败返回 None。"""
```

### 8.3 错误处理

- 指数退避重试（最多 3 次）
- Thinking block 兼容处理（DeepSeek 返回 `ThinkingBlock` → 提取 `TextBlock`）
- 单篇文章失败不影响同批次其他文章
- 整批失败 → 返回默认值（分类=空, 评分=3, 摘要=原文）

---

## 9. Web 页面架构

### 9.1 公共模式

所有 9 个页面遵循相同的 API-driven 模式：

```
1. 静态 HTML shell（一次性生成，数据变化不需重新生成）
2. CSS inline（零外部依赖，离线可用）
3. JS async IIFE 初始化
4. fetch /api/* 获取数据
5. 纯客户端 DOM 渲染
```

### 9.2 页面清单

所有 9 个页面遵循相同的 API-driven 模式：

| 页面 | 路由 | 对应前端模块 |
|------|------|-------------|
| Dashboard (今日) | `/` | `dashboard.py` |
| Library (专题) | `/library` | `library.py` |
| Entity Detail | `/entity/{id}` | `entity_page.py` |
| 2D Graph | `/graph` | `kg_d3.py` |
| 3D Graph | `/graph-3d` | `kg_3d.py` |
| Timeline | `/timeline` | `timeline_renderer.py` |
| Events | `/events` | `events_page.py` |
| Research | `/research` | `research_page.py` |
| My Favorites | `/my` | `my_page.py` |

---

## 10. 自动化调度

### 10.1 Windows Task Scheduler

| 任务 | 触发器 | 脚本 | 说明 |
|------|--------|------|------|
| Collector | 每小时, 8:00-23:00 | `run-collector.bat` | RSS → inbox.jsonl |
| Daily | 每天 9:00 | `run-daily.bat` | inbox → 日报 |
| Weekly | 每周日 10:00 | `run-weekly.bat` | 7天日报 → 趋势分析 |
| Monthly | 每月 1 号 10:00 | `run-monthly.bat` | 30天日报 → 趋势分析 |

### 10.2 .bat 脚本模式

```batch
@echo off
cd /d C:\Users\杨成俊\Desktop\AI-Workspace\20_Projects\ai-news
uv run python pipeline.py [--flags]
```

---

## 11. 测试策略

### 11.1 分层

| 层 | 策略 | 测试数 |
|-----|------|--------|
| 数据库 | 临时 SQLite + monkeypatch DB_PATH (→ db_core.DB_PATH) | 60+ |
| API | FastAPI TestClient + mock 数据库函数 | 40+ |
| AI 模块 | mock `call_ai()` 返回固定数据 | 70+ |
| 前端页面 | HTML 结构验证 + CSS 变量 + 响应式 + i18n | 20+ |
| 边界条件 | 空搜索/超长输入/不存在实体/零结果 | 20+ |
| 纯函数 + 其他 | 直接调用，无 mock | 60+ |
| Embedding | cosine/存储/重建/混合搜索/语义匹配 | 30+ |
| **合计** | | **357** |

### 11.2 Mock 模式

- **数据库测试**: `monkeypatch.setattr("src.database.DB_PATH", tmp_db)` → 隔离临时文件
- **API 测试**: `patch("src.api.get_entities", ...)` → 隔离数据库依赖
- **AI 模块测试**: `patch.object(module, "call_ai", return_value=mock_response)` → 隔离网络

### 11.3 运行

```bash
uv run pytest tests/ -v        # 全量
uv run pytest tests/ -q        # 简洁输出
uv run pytest tests/test_database.py -v  # 单模块
```

---

## 12. 关键设计决策

| 决策 | 理由 | 权衡 |
|------|------|------|
| SQLite 而非 PostgreSQL | 零配置，单人够用 | 不支持并发写 |
| YAML 而非 JSON 存卡片 | 可读性好，支持注释 | 解析稍慢 |
| API-driven UI 而非 SSR | 数据变化不需重生成 HTML | 首次加载有 spinner |
| 文件驱动而非 ORM | 简单透明，git 可追踪 | 查询能力有限 |
| Jaccard 而非 embedding 匹配 | 零成本，可离线 | 语义理解弱 |
| Windows Task Scheduler | 系统内置，零依赖 | 仅 Windows |
| WAL 模式 SQLite | 读写不互斥 | 多了一个 -wal 文件 |

---

## 13. 配置

### 13.1 环境变量 (.env)

```
AI_PROVIDER=deepseek | kimi
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
KIMI_API_KEY=sk-xxx
KIMI_BASE_URL=https://api.moonshot.cn/v1
```

### 13.2 config.yaml

```yaml
sources:           # RSS 源列表
categories:        # 分类体系
interests:         # 用户兴趣权重 (high/medium/low)
scoring:           # 评分维度
fetch:
  max_age_hours: 72
output:
  min_score: 3
```

---

## 14. 扩展点

| 扩展方向 | 改动点 |
|----------|--------|
| 新数据源 (X/Twitter, Reddit) | 新增 `src/fetcher_x.py`，在 pipeline 中切换数据源 |
| 新卡片类型 | 先写 5 张卡片验证，再更新 `KNOWLEDGE-CARD-SCHEMA_知识卡片结构.md` |
| 新页面 | 创建 `src/<page>.py`，在 `api.py` 加路由，更新导航 |
| 新 AI Provider | 在 `ai_client.py` 加分支 |
| RAG 检索 | 新增 embedding + vector search 模块 |
| 多用户 | 加 user 表，API 加认证 |
