# 项目结构 — AI Intelligence Platform

> 面试准备文档。说明项目目录结构、核心文件、启动方式和本地访问。

---

## 一、项目定位

AI Intelligence Platform（AI 智能情报平台）是一个自动化的 AI 新闻聚合与分析系统。每天从 RSS 抓取数百条 AI 相关新闻，经过 AI 分类、摘要、评分后，生成中文日报，并沉淀为知识卡片和知识图谱。

**技术栈**:

| 层 | 选型 | 说明 |
|---|------|------|
| 语言 | Python 3.13 | — |
| Web 框架 | FastAPI | 8 个 API 端点 + 5 个页面路由 |
| 数据库 | SQLite (WAL 模式) | 4 张表，外键约束 |
| AI 引擎 | DeepSeek / Kimi 双后端 | OpenAI 兼容协议 |
| 包管理 | uv | — |
| 前端 | Vanilla JS + fetch API | 无前端框架，零外部依赖 |
| 自动化 | Windows Task Scheduler | 4 个定时任务 |

---

## 二、目录结构

`
ai-news/
|- src/                        # 核心业务逻辑
|   |- api.py                  # FastAPI 服务入口（已实现）
|   |- database.py             # SQLite 数据层 CRUD（已实现）
|   |- fetcher.py              # RSS 抓取器 + Article 数据模型（已实现）
|   |- dedup.py                # 去重：URL 精确匹配 + 标题 Jaccard 相似度（已实现）
|   |- classifier.py           # AI 分类，调用 DeepSeek/Kimi（已实现）
|   |- summarizer.py           # AI 摘要生成，支持 ThreadPoolExecutor 并发（已实现）
|   |- scorer.py               # AI 评分 1-5 星（已实现）
|   |- reporter.py             # Markdown 日报生成（已实现）
|   |- knowledge.py            # 知识卡片加载 / Jaccard 匹配 / 上下文构建（已实现）
|   |- knowledge_graph.py      # 知识图谱生成（Mermaid + D3.js）（已实现）
|   |- concept_miner.py        # 概念自动发现（已实现）
|   |- trend_reporter.py       # 周报/月报趋势分析（已实现）
|   |- dashboard.py            # Dashboard HTML shell（已实现）
|   |- library.py              # Library HTML shell（已实现）
|   |- timeline.py             # Timeline HTML shell（已实现）
|   |- entity_page.py          # 实体详情页 HTML shell（已实现）
|   |- ai_client.py            # 双后端 AI 客户端，含指数退避重试（已实现）
|   |- cache.py                # AI 处理结果磁盘缓存（已实现）
|   |- sync_cards.py           # 卡片同步到 SQLite（已实现）
|   |- utils.py                # 日志、配置、文件 I/O（已实现）
|   |- i18n.py                 # 国际化/中文化（已实现）
|
|- pipeline.py                 # CLI 主入口，9 阶段管道（已实现）
|- collector.py                # 独立 Collector，无 AI 依赖（已实现）
|- config.yaml                 # 配置文件：RSS 源、分类、兴趣、评分权重（已实现）
|- pyproject.toml              # Python 项目配置 + 依赖（已实现）
|
|- prompts/                    # AI Prompt 模板
|   |- classify.md             # 分类 prompt
|   |- summarize.md            # 摘要 prompt
|   |- score.md                # 评分 prompt
|   |- mine-concepts.md        # 概念挖掘 prompt
|   +- trend.md                # 趋势分析 prompt
|
|- data/                       # 数据文件
|   |- inbox.jsonl             # Collector 写入的原始文章队列
|   |- platform.db             # SQLite 数据库（含 entities, articles, relationships, reports）
|   |- processed_cache.json    # AI 处理结果缓存
|   |- candidate_concepts.json # 概念候选池
|   +- knowledge/              # 知识卡片 YAML 文件
|       |- model/              # 模型卡片（GPT-5, Claude 4, DeepSeek-R1 等）
|       |- company/            # 公司卡片（OpenAI, DeepSeek, Anthropic 等）
|       |- person/             # 人物卡片（Sam Altman, 李飞飞 等）
|       |- methodology/        # 方法论卡片（Prompt Engineering, RAG, Agent 等）
|       |- tech/               # 技术卡片（Transformer, MCP, BERT 等）
|       |- concept/            # 概念卡片（RLHF, MoE, LoRA 等）
|       +- product/            # 产品卡片（ChatGPT, GitHub Copilot 等）
|
|- tests/                      # 测试套件
|   |- test_database.py        # 数据库层测试（39 项）
|   |- test_api.py             # API 层测试（21 项）
|   |- test_classifier.py      # 分类器测试
|   |- test_concept_miner.py   # 概念挖掘测试
|   |- test_dedup.py           # 去重测试
|   |- test_fetcher.py         # 抓取测试
|   |- test_knowledge.py       # 知识匹配测试（23 项）
|   |- test_scorer.py          # 评分测试
|   |- test_summarizer.py      # 摘要测试
|   +- test_trend_reporter.py  # 趋势报告测试（13 项）
|
|- reports/                    # 生成的报告（日报/周报/月报）+ HTML 页面
|   |- YYYY-MM-DD.md           # 每日日报
|   |- weekly-YYYY-MM-DD.md    # 周报
|   |- monthly-YYYY-MM.md      # 月报
|   |- dashboard.html          # Dashboard 页面
|   |- library.html            # 知识资产库
|   |- timeline.html           # 时间线
|   |- knowledge-graph.html    # 知识图谱
|   +- knowledge-graph.md      # Mermaid 格式图谱
|
|- docs/interview/             # 面试准备文档（本目录）
|
|- run-daily.bat / run-weekly.bat / run-monthly.bat / run-collector.bat
+                               # Windows Task Scheduler 调度脚本
`

---

## 三、核心文件说明

### pipeline.py — 管道主入口

CLI 入口，通过 --flag 切换不同执行模式。所有模块在 pipeline.py 中按顺序编排：

`python
# 典型日报执行流程（pipeline.py 中的 main() 函数）
fetch_and_dedup()       # 数据获取 + 去重
classify(articles)      # AI 分类
mine_concepts()         # 概念发现
match_cards()           # 知识卡片匹配
summarize(articles)     # AI 摘要（支持并发）
score(articles)         # AI 评分
generate_report()       # 日报生成
init_db()               # SQLite 写入
insert_articles()       # 文章入库
generate_dashboard()    # 页面重新生成
generate_library()
generate_timeline()
`

### src/api.py — FastAPI 服务入口

`python
uv run uvicorn src.api:app --reload --port 8765
`

提供 8 个 API 端点和 5 个页面路由。页面为 API-driven HTML shell——HTML 只包含骨架，数据通过 JS etch() 从 /api/* 动态获取。

### src/database.py — 统一数据层

所有模块通过 get_db() 获取 SQLite 连接，读写分离。采用 WAL 模式支持并发读。

---

## 四、本地服务访问

`ash
# 1. 安装依赖
uv sync

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env: DEEPSEEK_API_KEY=sk-xxx

# 3. 启动 Web 服务
uv run uvicorn src.api:app --reload --port 8765

# 4. 访问
#    http://127.0.0.1:8765          → Dashboard
#    http://127.0.0.1:8765/library  → 知识资产库
#    http://127.0.0.1:8765/graph    → 知识图谱
#    http://127.0.0.1:8765/timeline → 时间线
#    http://127.0.0.1:8765/api/health → 健康检查

# 5. 运行一次日报管道
python pipeline.py --fetch-direct
`

---

## 五、核心架构模式

| 模式 | 说明 |
|------|------|
| 线性管道 | 每个阶段独立，输入→处理→输出，不跳跃 |
| SSOT | Knowledge Card (YAML) 是整个系统的唯一事实来源 |
| 文件驱动 | 卡片是 YAML，Prompt 是 Markdown，数据是 SQLite |
| API-driven UI | 页面是静态 HTML shell，数据通过 /api/* 实时获取 |
| 双后端 AI | DeepSeek + Kimi 通过 AI_PROVIDER 环境变量切换 |

---

## 面试官可能追问的问题

1. **为什么选 SQLite 而不是 PostgreSQL？** — 零配置，单人够用，WAL 支持并发读，备份就是 cp 文件。但要注意 SQLite 不支持并发写，多用户场景需迁移。
2. **API-driven UI 有什么优缺点？** — 优：数据变化不需重生成 HTML；缺：首次加载有 Loading spinner，SEO 不友好。
3. **uv 和 pip 的区别？** — uv 是 Rust 实现的 Python 包管理器，比 pip 快 10-100 倍，支持 uv.lock 锁定版本。
4. **Pipeline 是同步还是异步？** — 抓取阶段用 syncio + httpx 实现异步并发抓取。AI 调用阶段用 ThreadPoolExecutor 实现并发摘要。其余阶段均为同步串行。
5. **如何处理 RSS 源不可用？** — 单源超时 30 秒，不影响其他源；每个源独立抓取，失败时只跳过该源。
