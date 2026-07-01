# API Reference — AI Intelligence Platform

> 面试准备文档。说明各核心模块的接口、输入格式、处理流程和输出。

---

## 一、模块概览

整个系统由以下核心模块组成，在 pipeline.py 中按顺序调用。每个模块职责独立，输入/输出通过 Article 数据对象传递。

---

## 二、Article 数据模型

所有模块共享同一个数据结构，随处理阶段逐步丰富字段。

| 阶段 | 填充字段 | 类型 | 说明 |
|------|----------|------|------|
| Fetcher | id, title, url, source, published, content_raw | 基础字段 | RSS 解析结果 |
| Dedup | is_duplicate, duplicate_of | bool/str | 去重标记 |
| Classifier | categories | list[str] | 分类标签 |
| Summarizer | title_cn, one_liner, summary_points | str/list | 中文摘要 |
| Scorer | score, score_reason, cluster_id | int/str/str | 评分 + 聚类 |

Article 使用 Python dataclass 实现 (src/fetcher.py)。

---

## 三、各模块接口详情

### 3.1 Fetcher (RSS 抓取器)

**文件**: src/fetcher.py
**功能**: 从 config.yaml 配置的 RSS 源并发抓取文章，解析为标准 Article 结构。
**输入**: config.yaml 中的 sources 列表 (源名称 + RSS URL + 启用状态)

**处理流程**:
1. 过滤 enabled: true 的源
2. 使用 httpx 异步并发请求 (asyncio)
3. 每个源独立解析，失败只跳过该源
4. 单源超时 30 秒，重试最多 3 次
5. 只保留最近 72 小时的文章

**输出**: list[Article] 或写入 data/inbox.jsonl（追加写）

**已实现**: 是

---

### 3.2 Dedup (去重器)

**文件**: src/dedup.py
**功能**: URL 精确匹配 + 标题 Jaccard 相似度去重。
**输入**: list[Article]

**处理流程**:
1. URL 精确匹配（始终启用）
2. 标题 Jaccard 相似度 > 0.85 判定为重复
3. 7 天 seen_urls 缓存窗口

**输出**: 去重后的 list[Article]

**已实现**: 是

---

### 3.3 Classifier (AI 分类器)

**文件**: src/classifier.py
**功能**: 使用 DeepSeek/Kimi API 对文章进行自动分类。
**输入**: list[Article]

**处理流程**:
1. 加载 prompts/classify.md 作为 system prompt
2. 从 config.yaml 读取 16 个分类标签，注入 prompt
3. 每批 20-25 篇，调用 call_ai()
4. 文章匹配 1-3 个标签
5. 失败时标记为 "未分类"

**输出**: 更新 Article.categories 字段

**已实现**: 是

---

### 3.4 Summarizer (AI 摘要生成器)

**文件**: src/summarizer.py
**功能**: 英文 AI 新闻 -> 中文标题 + 一句话概括 + 三点摘要。
**输入**: list[Article], knowledge_context (可选), concurrency (默认 3)

**处理流程**:
1. 加载 prompts/summarize.md 作为 system prompt
2. 每批 10 篇，调用 call_ai()
3. 支持 ThreadPoolExecutor 并发
4. 注入知识上下文（匹配到的卡片信息）

**输出**: 更新 Article.title_cn, Article.one_liner, Article.summary_points

**已实现**: 是

---

### 3.5 Scorer (AI 评分器)

**文件**: src/scorer.py
**功能**: 1-5 星评分 + 评分理由。
**输入**: list[Article]

**处理流程**:
1. 加载 prompts/score.md 作为 system prompt
2. 注入用户兴趣权重 (config.yaml -> interests)
3. 每批 20-30 篇，调用 call_ai()
4. 四个评分维度: 行业影响力 40% / 技术突破性 25% / 用户相关性 25% / 信息独特性 10%

**输出**: 更新 Article.score, Article.score_reason

**已实现**: 是

---

### 3.6 Reporter (日报生成器)

**文件**: src/reporter.py
**功能**: 将评分后的文章组装为 Markdown 日报。
**输入**: list[Article], fetched_count, min_score (默认 3)

**处理流程**:
1. 按 cluster_id 聚类同事件多源文章
2. 按评分降序排列
3. 星级分组展示
4. 更新 reports/index.md 索引

**输出**: reports/YYYY-MM-DD.md (Markdown 文件)

**已实现**: 是

---

### 3.7 Trend Reporter (趋势报告器)

**文件**: src/trend_reporter.py
**功能**: 汇总多天日报，AI 分析趋势和信号。
**输入**: period ("week" 或 "month")

**处理流程**:
1. 加载近 N 天日报 Markdown
2. 调用 call_ai() 识别趋势、信号、新玩家
3. 格式化为周报/月报 Markdown

**输出**: reports/weekly-YYYY-MM-DD.md 或 monthly-YYYY-MM.md

**已实现**: 是

---

### 3.8 Knowledge Card (知识卡片系统)

**文件**: src/knowledge.py
**功能**: 加载 YAML 知识卡片，匹配文章到相关卡片，构建历史上下文。

**算法流程**:
1. load_cards() 遍历 data/knowledge/**/*.yaml
2. match_cards() 使用 Jaccard 相似度匹配文章 <-> 卡片
3. build_context() 构建上下文字符串

**输出**: matched dict (文章->卡片映射), knowledge_context 字符串

**已实现**: 是

---

### 3.9 Knowledge Graph (知识图谱)

**文件**: src/knowledge_graph.py
**功能**: 基于卡片关系字段构建知识图谱。
**输入**: list[KnowledgeCard] (含 related/depends_on/influenced 字段)

**关系类型**:
- related: 灰色虚线 (关联关系)
- depends_on: 红色实线 (依赖关系)
- influenced: 蓝色实线 (影响关系)

**输出**: Mermaid 格式 (可嵌入 Markdown) + D3.js HTML (交互式拖拽)

**已实现**: 是

---

### 3.10 Concept Miner (概念发现器)

**文件**: src/concept_miner.py
**功能**: 从文章流中自动发现新兴概念，维护候选池。

**准入规则**:
| 出现次数 | 状态 | 操作 |
|----------|------|------|
| 1 次 | candidate | 加入候选池 |
| 2 次 | draft | 生成草稿 YAML 卡片 |
| 3+ 次 | confirmed | 日志提醒人工审查 |

高权威来源 (Anthropic Research, OpenAI Blog 等) 加速确认。

**输出**: 更新 data/candidate_concepts.json + 可选草稿卡片

**已实现**: 是

---

### 3.11 Cache (处理结果缓存)

**文件**: src/cache.py
**功能**: 缓存 AI 处理结果，避免重复 API 调用。
**存储**: data/processed_cache.json，键为 Article ID (md5(url))
**淘汰策略**: 超过 10000 条时淘汰最旧的 50%

**已实现**: 是

---

## 四、统一 AI 调用入口

**文件**: src/ai_client.py

```python
def call_ai(system_prompt, user_prompt, model=None, temperature=0.1, max_tokens=4096):
```

| 后端 | 环境变量 | 默认模型 |
|------|----------|----------|
| DeepSeek (默认) | DEEPSEEK_API_KEY | deepseek-chat |
| Kimi | MOONSHOT_API_KEY | moonshot-v1-8k |

**重试策略**: 指数退避，最多 3 次 (1.5s / 3s / 6s)
**JSON 解析**: 支持纯 JSON 和 ```json 包裹两种格式

**已实现**: 是

---

## 五、FastAPI 路由总表

| 路由 | 方法 | 参数 | 说明 |
|------|------|------|------|
| / | GET | — | Dashboard 首页 |
| /library | GET | — | 知识资产库 |
| /graph | GET | — | 知识图谱 |
| /timeline | GET | — | 时间线 |
| /entity/{id} | GET | entity_id | 实体详情 |
| /api/health | GET | — | 健康检查 |
| /api/entities | GET | ?type= | 实体列表 |
| /api/entities/{id} | GET | id | 实体详情+关系 |
| /api/relationships | GET | ?entity_id= | 关系列表 |
| /api/articles | GET | ?limit=&min_score= | 文章列表 |
| /api/reports | GET | ?type=&limit= | 报告列表 |
| /api/search | GET | ?q=&limit= | 全文搜索 |
| /api/stats | GET | — | 统计数据 |

---

## 面试官可能追问的问题

1. **为什么选 API-driven UI 而不是 SSR？** 页面是静态 HTML shell，数据通过 JS fetch 动态获取。前后端解耦，数据变化时不需要重新生成 HTML。

2. **AI 调用失败的降级策略？** 每篇文章独立处理，失败不影响同批其他文章。整批失败时分类返回"未分类"，评分返回 3，摘要返回原文。管道不中断。

3. **缓存为什么用 JSON 文件而不是 Redis？** 单人使用场景，磁盘缓存足够。JSON 文件透明可检查，上限 10000 条约 2-3 MB。

4. **多源报道如何聚类？** Cluster ID 由 AI 评分阶段生成。同 cluster 的文章在日报中合并为一条主报道，其他来源作为"同时报道"引用。

5. **双后端设计解决了什么？** 单一 API 依赖变成双活互备。DeepSeek 断服时切 Kimi，反之亦然。两者都是 OpenAI 兼容协议，切换只需改环境变量。

6. **提示：Concept Miner 自动生成的草稿卡片质量如何？** 需人工确认。代码中有对应的准入规则但自动摘要质量依赖 AI 模型能力，建议人工审核后再纳入正式知识库。
