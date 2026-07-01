# AI News — OpenSpec Proposal

> **状态**: 待确认  
> **作者**: AI 首席架构师 + 杨成俊  
> **日期**: 2026-06-27  
> **版本**: v1.0

---

## 1. 项目定义

### 1.1 一句话描述

每天自动从 RSS 抓取 AI 资讯，经 AI 去重、分类、摘要、评分后，生成一份 5-10 分钟可读完的中文 Markdown 日报。

### 1.2 要解决的问题

| 痛点 | 现状 | 目标 |
|------|------|------|
| 信息过载 | 每天 300-500 条 AI 新闻 | 筛选到 15-20 条 |
| 低质内容 | 情绪化标题、片面解读、蹭热度 | 完整、前沿、深度 |
| 缺乏筛选 | 不知道哪些真正重要 | 星级评分 + 理由 |
| 英文壁垒 | 长篇英文阅读耗时 | 中文三句话摘要 |
| 无分类 | 信息混杂 | 自动归类（模型/Agent/融资/论文…） |
| 无上下文 | 不知道某条新闻为什么重要 | AI 深度分析 + 社区观点提炼 |

### 1.3 核心用户

- **当前**: 杨成俊（单人使用）
- **未来**: 可能作为付费产品对外提供

### 1.4 成功标准

- [ ] 每天自动运行，无需人工干预
- [ ] 5-10 分钟内读完当天最重要的 AI 新闻
- [ ] 能发现真正重要的新模型、新工具、新趋势
- [ ] 后续可作为其他 Agent（内容创作、研究助手）的信息基础设施

---

## 2. MVP 范围

### 2.1 MVP 目标（7 天）

端到端跑通：**RSS 抓取 → AI 处理 → Markdown 日报**，每天自动生成一份报告。

### 2.2 MVP 包含

| 模块 | 说明 | AI 参与度 |
|------|------|-----------|
| RSS 抓取 | 从配置的 RSS 源抓取文章 | ⭐ (无 AI) |
| 去重 | URL 精确去重 + 标题相似度去重 | ⭐ (少量 AI) |
| 自动分类 | 将文章归入预定义类别 | ⭐⭐⭐⭐⭐ |
| 中文摘要 | 标题翻译 + 一句话总结 + 三点摘要 | ⭐⭐⭐⭐⭐ |
| 重要性评分 | 1-5 星评分 + 评分理由 | ⭐⭐⭐⭐⭐ |
| 日报生成 | 按模板生成 Markdown 日报 | ⭐ (无 AI) |

### 2.3 MVP 不包含

| 功能 | 原因 | 计划阶段 |
|------|------|----------|
| X / Reddit / GitHub 监控 | 先跑通 RSS | Phase 2 |
| 深度分析（为什么重要） | MVP 先做摘要+评分 | Phase 2 |
| 社区观点提炼 | 需要额外数据源 | Phase 3 |
| 个性化推荐 | 需要用户反馈数据 | Phase 3 |
| Web Dashboard | 先 Markdown 看效果 | Phase 3 |
| 微信/Telegram/飞书推送 | 先文件输出 | Phase 2 |
| 复杂前端页面 | 不做 | — |
| 自建网站 | 不做 | — |
| 大量网页爬虫 | 优先 RSS 和 API | — |
| 微服务架构 | 过度设计 | — |
| 数据库 | JSON 文件足够 | — |
| 高并发设计 | 单人使用 | — |

---

## 3. 架构设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                     AI News Pipeline                     │
│                                                         │
│  config.yaml                                            │
│  ┌──────────┐                                           │
│  │ sources  │── RSS feeds, API keys                     │
│  │ categories│── Taxonomy                                │
│  │ interests │── User profile                           │
│  └──────────┘                                           │
│       │                                                 │
│       ▼                                                 │
│  ┌────────────┐    ┌────────────┐    ┌───────────────┐  │
│  │  Fetcher   │───▶│ Deduplicator│───▶│  Classifier   │  │
│  │  (Script)  │    │ (Script+AI) │    │  (Claude API) │  │
│  └────────────┘    └────────────┘    └───────────────┘  │
│                                              │          │
│                                              ▼          │
│  ┌────────────┐    ┌────────────┐    ┌───────────────┐  │
│  │  Reporter  │◀───│   Scorer   │◀───│  Summarizer   │  │
│  │ (Template) │    │(Claude API)│    │ (Claude API)  │  │
│  └────────────┘    └────────────┘    └───────────────┘  │
│       │                                                 │
│       ▼                                                 │
│  reports/                                               │
│  ├── 2026-06-27.md                                      │
│  ├── 2026-06-28.md                                      │
│  └── index.md                                           │
└─────────────────────────────────────────────────────────┘
```

### 3.2 架构原则

| 原则 | 说明 |
|------|------|
| **线性管道** | 每个阶段独立，输入→处理→输出，不跳跃 |
| **无状态** | 每次运行独立。仅缓存已见 URL 用于去重 |
| **文件存储** | JSON 做中间态缓存，Markdown 做最终输出。不用数据库 |
| **AI 集中调用** | 分类/摘要/评分通过 Claude API 批量调用 |
| **配置驱动** | RSS 源、分类体系、评分权重全部可配置 |
| **Prompt 外置** | 所有 AI prompt 独立文件存储，与代码分离 |

### 3.3 技术栈

| 层 | 选型 | 理由 |
|----|------|------|
| 语言 | Python 3.11+ | 生态成熟（feedparser, anthropic SDK） |
| RSS 解析 | `feedparser` | 最成熟的 Python RSS 库 |
| AI 引擎 | Claude API (Anthropic SDK) | 你已在用，中文能力强 |
| 配置 | YAML | 可读性好，支持注释 |
| 缓存 | JSON 文件 | 零依赖，直接可读 |
| 调度 | Claude Code Cron / 系统 cron | 每天自动触发 |
| 包管理 | uv / pip | 轻量 |

### 3.4 项目目录结构

```
20_Projects/ai-news/
├── OPENSPEC.md              # ← 本文件
├── README.md                # 项目说明
├── config.yaml              # 配置文件（RSS源、分类、用户偏好）
├── .env.example             # API Key 模板
├── pipeline.py              # 主入口：编排整个管道
├── src/
│   ├── fetcher.py           # RSS 抓取
│   ├── dedup.py             # 去重逻辑
│   ├── classifier.py        # AI 分类（调 Claude API）
│   ├── summarizer.py        # AI 摘要 + 翻译（调 Claude API）
│   ├── scorer.py            # AI 评分（调 Claude API）
│   ├── reporter.py          # Markdown 报告生成
│   └── utils.py             # 公共工具（日志、文件读写）
├── prompts/
│   ├── classify.md          # 分类 Prompt
│   ├── summarize.md         # 摘要 Prompt
│   └── score.md             # 评分 Prompt
├── templates/
│   └── daily-report.md      # 日报模板
├── reports/                 # 生成的日报
│   └── index.md
├── cache/
│   └── seen_urls.json       # 去重缓存
└── tests/
    ├── test_fetcher.py
    ├── test_dedup.py
    └── test_pipeline.py
```

---

## 4. Agent 设计

### 4.1 Agent 总览

```
                    ┌──────────────┐
                    │ Orchestrator │  ← 主控，调度所有 Agent
                    └──────┬───────┘
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
    │   Fetcher   │ │ Deduplicator│ │  Classifier │
    │   (Script)  │ │ (Script+AI) │ │  (AI Agent) │
    └─────────────┘ └─────────────┘ └─────────────┘
                                           │
                              ┌────────────┼────────────┐
                              │            │            │
                       ┌──────▼──────┐ ┌───▼──────┐ ┌──▼──────────┐
                       │ Summarizer  │ │  Scorer  │ │  Reporter   │
                       │ (AI Agent)  │ │(AI Agent)│ │  (Script)   │
                       └─────────────┘ └──────────┘ └─────────────┘
```

### 4.2 Agent 详细定义

#### Agent 1: Fetcher（内容抓取器）

| 属性 | 值 |
|------|-----|
| **类型** | Script（无 AI） |
| **输入** | `config.yaml` 中的 RSS 源列表 |
| **输出** | `[{title, url, published, source, content_raw}]` |
| **职责** | 解析 RSS/Atom 源，提取标题、URL、发布时间、正文/摘要 |
| **错误处理** | 单个源失败不影响整体；超时 30s；记录失败源 |
| **Prompt** | 不需要 |

#### Agent 2: Deduplicator（去重器）

| 属性 | 值 |
|------|-----|
| **类型** | Script + 少量 AI |
| **输入** | Fetcher 输出的文章列表 |
| **输出** | 去重后的文章列表 |
| **职责** | URL 精确匹配去重；标题相似度 > 0.85 视为重复；维护 7 天 seen_urls 缓存 |
| **AI 介入点** | 标题相似度模糊判断（可选，规则也能做大部分） |
| **Prompt** | `dedup.md`（可选，MVP 可先用规则） |

#### Agent 3: Classifier（分类器）

| 属性 | 值 |
|------|-----|
| **类型** | AI Agent（Claude API） |
| **输入** | 去重后文章列表（批量） |
| **输出** | 每篇文章 1-3 个分类标签 |
| **职责** | 基于文章标题+内容，分配预定义分类标签 |
| **Prompt** | `prompts/classify.md` |
| **Knowledge** | 分类体系 (`ai-news-categories.md`) |
| **批量策略** | 每批 20-30 篇文章，一次 API 调用 |

#### Agent 4: Summarizer（摘要生成器）

| 属性 | 值 |
|------|-----|
| **类型** | AI Agent（Claude API） |
| **输入** | 已分类文章列表 |
| **输出** | 中文标题 + 一句话总结 + 三点摘要 |
| **职责** | 英文→中文翻译；提取核心信息；控制摘要长度 |
| **Prompt** | `prompts/summarize.md` |
| **Knowledge** | AI 术语词汇表 (`ai-glossary.md`) |
| **批量策略** | 每篇文章独立调用（内容较长） |

#### Agent 5: Scorer（评分器）

| 属性 | 值 |
|------|-----|
| **类型** | AI Agent（Claude API） |
| **输入** | 已摘要文章列表 + 用户兴趣配置 |
| **输出** | 1-5 星评分 + 评分理由（一句话） |
| **职责** | 基于新闻重要性 + 用户相关性综合打分 |
| **Prompt** | `prompts/score.md` |
| **Knowledge** | 评分标准 (`scoring-criteria.md`)、用户兴趣 (`user-interests.md`) |
| **批量策略** | 每批 20-30 篇，一次 API 调用 |

#### Agent 6: Reporter（报告生成器）

| 属性 | 值 |
|------|-----|
| **类型** | Script（模板引擎，无 AI） |
| **输入** | 已评分文章列表（按分数降序） |
| **输出** | `reports/YYYY-MM-DD.md` |
| **职责** | 按模板组装日报；星级分组；生成目录；更新 index.md |
| **Prompt** | 不需要（纯模板） |
| **Template** | `templates/daily-report.md` |

#### Agent 7: Orchestrator（编排器）

| 属性 | 值 |
|------|-----|
| **类型** | Script（CLI 入口） |
| **职责** | 串联所有 Agent；日志记录；错误恢复；统计输出 |
| **CLI** | `python pipeline.py` 或 `python pipeline.py --date 2026-06-27` |

### 4.3 Claude Code Agent 定义

在 `60_Agents/` 下创建以下 Agent 定义，使 Claude Code 可以手动调用：

| Agent 定义文件 | 对应功能 | 用途 |
|---------------|----------|------|
| `ai-news-run.md` | 运行完整管道 | 一键生成日报 |
| `ai-news-classify.md` | 仅运行分类 | 调试/调整分类 prompt |
| `ai-news-summarize.md` | 仅运行摘要 | 调试/调整摘要 prompt |
| `ai-news-score.md` | 仅运行评分 | 调试/调整评分 prompt |

---

## 5. Prompt 复用策略

### 5.1 设计原则

1. **Prompt 与代码分离** — Prompt 是独立 Markdown 文件，修改 prompt 不需要改代码
2. **版本可追踪** — Git 管理，可对比不同版本效果
3. **参数化注入** — 变量（`{{article_title}}`、`{{user_interests}}`）运行时注入
4. **双向存储** — 项目内 `prompts/` 是工作副本；`30_Knowledge/Prompts/` 是知识库副本，供其他项目参考

### 5.2 三个核心 Prompt

#### Prompt 1: 分类（`classify.md`）

```
系统角色：你是顶级 AI 行业分析师，擅长信息分类。

输入：文章标题 + 摘要/正文

输出：每篇文章的 1-3 个分类标签，从指定分类体系中选择。

分类体系（注入自 Knowledge）：
- 大模型发布、开源模型、Agent、编程/AI Coding、视频生成、
  图像生成、语音、机器人、芯片/算力、融资/商业、论文/研究、
  政策/监管、安全/对齐、工具/平台、行业应用、人物/观点

规则：
- 优先匹配最精确的分类
- 一篇文章最多 3 个标签
- 不确定时标注 "其他" + 建议新分类
```

#### Prompt 2: 摘要（`summarize.md`）

```
系统角色：你是顶级 AI 科技编辑，擅长将英文技术内容精准翻译为简洁中文。

输入：文章标题 + 正文/摘要

输出格式：
【中文标题】（不超过 25 字）
【一句话】（一句话概括核心，不超过 50 字）
【三点摘要】
① ……
② ……
③ ……

规则：
- 保留技术术语的英文原名（如 "Claude Code"、"MCP"）
- 去掉营销话术和情绪化表述
- 三点摘要覆盖：What（是什么）、Why（为什么重要）、How（怎么用/影响谁）
- 术语翻译参考词汇表（注入自 Knowledge）
```

#### Prompt 3: 评分（`score.md`）

```
系统角色：你是 AI 行业资深分析师，每天需要从大量新闻中筛选最重要的内容。

输入：
- 文章摘要（中文标题 + 一句话 + 三点摘要）
- 已分配的分类标签
- 用户的兴趣配置（注入自 Knowledge）

评分标准（1-5 星）：
★★★★★ (5): 行业里程碑事件。模型发布、重大收购、范式转变。今天必看。
★★★★ (4): 重要更新或趋势信号。对有深度关注的用户很重要。
★★★ (3): 一般新闻。值得了解但非必须。
★★ (2): 边角信息。与 AI 相关但深度不足。
★ (1): 可忽略。纯营销、重复报道、与核心关注无关。

输出格式：
- 评分（★符号 + 数字）
- 评分理由（一句话，说明为什么这个分数）

用户当前兴趣权重（注入自 Knowledge）：
- Claude Code / AI Coding 工具：高权重
- AI Agent / MCP：高权重
- Kimi / DeepSeek / 国产模型：高权重
- AI 自动化工作流：中高权重
- AI 创业/商业：中权重
- AI 绘画/音乐/视频生成：低权重
```

### 5.3 复用场景

| Prompt | 复用场景 |
|--------|----------|
| `classify.md` | 也可用于对旧报道分类、对其他领域新闻分类（改分类体系即可） |
| `summarize.md` | 可复用给任何"英文技术内容→中文摘要"的场景 |
| `score.md` | 核心逻辑可复用给任何"信息筛选+个性化排序"的场景 |

---

## 6. Knowledge 知识库

### 6.1 需要建立的知识条目

所有知识文件存放在 `30_Knowledge/` 下，项目内和知识库双写。

#### K1: AI 新闻分类体系 (`ai-news-categories.md`)

```markdown
# AI 新闻分类体系

## 一级分类

| 分类 | 说明 | 示例 |
|------|------|------|
| 大模型发布 | 新模型发布、版本更新、能力展示 | GPT-5, Claude 4, Gemini 3 |
| 开源模型 | 开源模型发布、微调、社区动态 | Llama 4, Mistral, 通义千问 |
| Agent | AI Agent 框架、产品、案例 | AutoGPT, CrewAI, MCP |
| 编程/AI Coding | AI 编程工具、代码生成、Dev 工具 | Claude Code, Cursor, Copilot |
| 视频生成 | 文生视频、图生视频 | Sora, Runway, 可灵 |
| 图像生成 | 文生图、图编辑、设计工具 | Midjourney, DALL-E, SD |
| 语音 | TTS、STT、声音克隆 | ElevenLabs, Whisper |
| 机器人 | 具身智能、人形机器人 | Figure, Tesla Bot |
| 芯片/算力 | GPU、AI 芯片、算力基建 | NVIDIA, Groq, Cerebras |
| 融资/商业 | 融资、收购、IPO、商业模式 | OpenAI 融资, xAI |
| 论文/研究 | 重要论文、技术突破 | arXiv, NeurIPS |
| 政策/监管 | AI 法规、政策、伦理 | EU AI Act, 中国 AI 法规 |
| 安全/对齐 | AI 安全、对齐研究 | Superalignment, Red-teaming |
| 工具/平台 | 开发者工具、云服务、API | LangChain, HuggingFace |
| 行业应用 | AI 在医疗/法律/金融等的应用 | AI 制药, AI 法律 |
| 人物/观点 | 关键人物言论、行业观点 | Sam Altman, 行业报告 |
```

#### K2: 评分标准 (`ai-news-scoring-criteria.md`)

```markdown
# AI 新闻重要性评分标准

## 评分维度

| 维度 | 权重 | 说明 |
|------|------|------|
| 行业影响力 | 40% | 对整个 AI 行业的影响范围和深度 |
| 技术突破性 | 25% | 是否代表真正的技术进步 |
| 用户相关性 | 25% | 与用户当前关注领域的匹配度 |
| 信息独特性 | 10% | 是否独家/首发，还是重复报道 |

## 评分锚点

- ★★★★★: 行业里程碑（新模型发布、范式转变、重大收购）
- ★★★★: 重要更新/趋势信号（版本更新、新功能、行业报告）
- ★★★: 一般新闻（合作伙伴关系、次要更新）
- ★★: 边角信息（花边新闻、纯观点、低质来源）
- ★: 可忽略（营销稿、重复报道）
```

#### K3: 用户兴趣画像 (`ai-news-user-interests.md`)

```markdown
# 用户兴趣画像 — 杨成俊

## 高优先级（权重 3x）
- Claude Code / AI Coding 工具
- AI Agent 框架与产品
- MCP 协议与生态
- 深度求索 (DeepSeek)
- 月之暗面 (Kimi)

## 中优先级（权重 2x）
- AI 自动化工作流
- AI 创业公司与商业模式
- 国产大模型动态
- 开源模型发布

## 低优先级（权重 0.5x）
- AI 绘画 / AI 音乐
- 纯学术论文（非应用方向）
- 非 AI 科技新闻

## 更新频率
每周日手动或 AI 辅助回顾一次，根据近期关注点调整。
```

#### K4: RSS 源质量评级 (`ai-news-source-quality.md`)

```markdown
# RSS 源质量评级

## 评级标准
- S: 一手信源，内容权威、深度、无营销
- A: 高质量二手信源，转载优质内容
- B: 一般科技媒体，有原创也有转载
- C: 聚合站，质量参差不齐

## 源列表（MVP 初始配置，后续补充）
| 源 | 评级 | 语言 | 更新频率 |
|----|------|------|----------|
| (待配置) | — | — | — |
```

#### K5: AI 术语词汇表 (`ai-news-glossary.md`)

```markdown
# AI 术语中文翻译规范

## 原则
- 技术名词首次出现保留英文 + 中文注释
- 已广泛接受的翻译直接使用中文
- 品牌名/产品名保留原文

## 常用术语
| 英文 | 中文 | 备注 |
|------|------|------|
| Large Language Model (LLM) | 大语言模型 | 或"大模型" |
| Agent | AI Agent / 智能体 | 日常用 AI Agent |
| Prompt Engineering | 提示工程 | — |
| Fine-tuning | 微调 | — |
| Inference | 推理 | — |
| Alignment | 对齐 | — |
| Hallucination | 幻觉 | — |
| RAG | RAG / 检索增强生成 | 首次出现加注释 |
| MCP | MCP / Model Context Protocol | 首次出现加注释 |
| Token | Token | 不翻译 |
| Benchmark | 基准测试 | — |

持续补充中。
```

### 6.2 知识文件存放位置

```
30_Knowledge/
├── Documents/
│   ├── ai-news-categories.md
│   ├── ai-news-scoring-criteria.md
│   ├── ai-news-user-interests.md
│   ├── ai-news-source-quality.md
│   └── ai-news-glossary.md
├── Prompts/
│   ├── ai-news-classify.md          ← 链接到 20_Projects/ai-news/prompts/classify.md
│   ├── ai-news-summarize.md         ← 链接到 20_Projects/ai-news/prompts/summarize.md
│   └── ai-news-score.md             ← 链接到 20_Projects/ai-news/prompts/score.md
```

---

## 7. 数据流详解

### 7.1 单次运行流程

```
[启动] python pipeline.py
  │
  ├─ 1. 加载配置 (config.yaml)
  │     - RSS 源列表
  │     - 分类体系
  │     - 用户兴趣
  │
  ├─ 2. Fetcher: 抓取所有 RSS 源
  │     - 并发请求（asyncio）
  │     - 单源超时 30s
  │     - 输出: [Article] (200-500 条)
  │
  ├─ 3. Deduplicator: 去重
  │     - URL 精确匹配去重
  │     - 标题相似度 > 0.85 去重
  │     - 对比 7 天缓存
  │     - 输出: [Article] (150-300 条)
  │
  ├─ 4. Classifier: AI 分类
  │     - 每 20-30 篇一批
  │     - Claude API 批量分类
  │     - 输出: [Article + categories]
  │
  ├─ 5. Summarizer: AI 摘要
  │     - 每篇独立调用（内容长）
  │     - 或批量 5-10 篇（内容短的）
  │     - 输出: [Article + categories + summary_cn]
  │
  ├─ 6. Scorer: AI 评分
  │     - 每 20-30 篇一批
  │     - 注入用户兴趣配置
  │     - 输出: [Article + categories + summary_cn + score]
  │
  ├─ 7. Reporter: 生成日报
  │     - 按分数降序排列
  │     - 星级分组展示
  │     - 更新 index.md
  │     - 输出: reports/2026-06-27.md
  │
  └─ 8. 完成：输出统计信息
        - 抓取 X 条 → 去重后 Y 条 → 推荐 Z 条
        - ★★★★★: N 条
        - API 调用次数和 token 消耗
```

### 7.2 中间数据结构

```python
# 每个处理阶段逐步丰富 Article 对象
Article = {
    # Fetcher 产出
    "id": "md5(url)",
    "title": "原始标题",
    "url": "https://...",
    "source": "TechCrunch",
    "published": "2026-06-27T10:00:00Z",
    "content_raw": "原始摘要或正文...",

    # Deduplicator 产出
    "is_duplicate": False,
    "duplicate_of": None,

    # Classifier 产出
    "categories": ["大模型发布", "Agent"],

    # Summarizer 产出
    "title_cn": "OpenAI 发布 GPT-6 Preview",
    "one_liner": "GPT-6 Preview 在 Agent 能力上提升明显",
    "summary_points": [
        "新增长效记忆能力，可跨会话保持上下文",
        "支持 MCP 协议原生集成",
        "推理成本较 GPT-5 降低 60%"
    ],

    # Scorer 产出
    "score": 5,
    "score_reason": "行业里程碑发布，直接影响你关注的 Agent 和 MCP 领域"
}
```

---

## 8. 7 天 MVP 开发计划

### Day 1: 项目搭建 + Fetcher
- [ ] 初始化项目目录结构
- [ ] 创建 `config.yaml`（初始配置 5-10 个 RSS 源）
- [ ] 实现 `fetcher.py`（feedparser 解析 RSS）
- [ ] 写 `fetcher` 的单元测试
- [ ] **验收**: 能成功抓取并打印文章列表

### Day 2: Deduplicator + 数据管道
- [ ] 实现 `dedup.py`（URL 去重 + 标题相似度）
- [ ] 实现 `cache/seen_urls.json` 读写
- [ ] 连接 Fetcher → Deduplicator
- [ ] **验收**: 去重后文章数 ≤ 原始文章数

### Day 3: Classifier（AI 分类）
- [ ] 编写 `prompts/classify.md`
- [ ] 实现 `classifier.py`（Claude API 批量调用）
- [ ] 创建 Knowledge: `ai-news-categories.md`
- [ ] 调优 prompt（用真实数据测试）
- [ ] **验收**: 10 篇文章能在 1 次 API 调用中正确分类

### Day 4: Summarizer（AI 摘要）
- [ ] 编写 `prompts/summarize.md`
- [ ] 实现 `summarizer.py`
- [ ] 创建 Knowledge: `ai-news-glossary.md`
- [ ] 调优 prompt
- [ ] **验收**: 英文文章输出高质量中文摘要

### Day 5: Scorer + Reporter
- [ ] 编写 `prompts/score.md`
- [ ] 实现 `scorer.py`
- [ ] 创建 Knowledge: `scoring-criteria.md` + `user-interests.md`
- [ ] 编写 `templates/daily-report.md`
- [ ] 实现 `reporter.py`
- [ ] **验收**: 能输出格式完整的 Markdown 日报

### Day 6: 端到端集成
- [ ] 实现 `pipeline.py`（完整编排）
- [ ] 错误处理：单步失败不中断管道
- [ ] 日志输出
- [ ] 全流程测试
- [ ] **验收**: `python pipeline.py` 一键生成日报

### Day 7: 文档 + 首次真实运行
- [ ] 编写 `README.md`
- [ ] 创建 Claude Code Agent 定义（`60_Agents/`）
- [ ] 配置自动调度（Claude Code Cron 每日触发）
- [ ] 首次真实数据运行
- [ ] 根据结果微调 prompt
- [ ] **验收**: 成功标准 4 条全部达标

---

## 9. 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| RSS 源内容质量差 | 高 | 中 | 源头筛选 + AI 评分过滤低质内容 |
| Claude API 调用成本过高 | 中 | 中 | 批量调用、控制每批大小、缓存结果 |
| 中文摘要质量不稳定 | 中 | 高 | Prompt 迭代 + 术语表约束 + 人工抽查 |
| RSS 源不稳定/失效 | 高 | 低 | 错误隔离、定期检查源状态 |
| 评分标准不准确 | 高 | 中 | 人工反馈闭环，每周调整用户兴趣权重 |

---

## 10. Phase 2-4 路线图（MVP 后）

### Phase 2: 多源 + 推送（预计第 2-4 周）
- X (Twitter) 监控
- Reddit / Hacker News 热帖
- GitHub Trending
- AI 深度分析（为什么重要）
- Telegram / 微信 / 邮件推送

### Phase 3: 智能增强（预计第 2-3 月）
- 社区观点提炼
- 个性化推荐（基于阅读反馈）
- Web Dashboard（历史搜索、分类浏览）
- 自动发现新 RSS 源

### Phase 4: 内容复用（预计第 3-4 月）
- 一键生成公众号文章
- 周报/月报自动生成
- 作为其他 Agent 的信息基础设施
- 多用户支持（如决定对外提供）

---

## 11. 决策记录

| 决策 | 理由 | 权衡 |
|------|------|------|
| Python 而非 Node.js | feedparser 生态成熟，AI/ML 工具链好 | Node.js 异步更好但 RSS 生态弱 |
| 文件存储而非数据库 | MVP 数据量小，JSON 够用 | 后期数据量大再迁移到 SQLite |
| 批量 API 调用 | 降低成本，提高速度 | 单篇失败影响同批次 |
| Prompt 外置文件 | 方便迭代，可版本管理 | 需要文件读取逻辑 |
| 先做 RSS 不做 X/Reddit | RSS 最简单，先跑通管道 | 覆盖不全，但 MVP 足够 |

---

> **下一步**: 等待确认后进入 Day 1 实现阶段。确认后请说"开始实现"。
