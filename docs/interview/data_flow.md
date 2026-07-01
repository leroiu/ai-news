# Data Flow

> 用一条新闻从进入系统到知识图谱的完整流转，串讲所有核心模块。

---

## 一、示例新闻

本文以一条虚构但合理的 AI 新闻为例：

> **"Anthropic 发布 Claude 4 Sonnet，性能超越 GPT-5，支持 200K 上下文窗口"**
> 来源: TechCrunch AI | 时间: 2026-06-30 10:00 UTC

使用 python pipeline.py 默认模式 (从 inbox 读取) 说明完整流程。

---

## 二、完整数据流 (9 阶段)

### Stage 0: Collector (独立进程，每小时运行)

Collector 是独立脚本，零 AI 依赖。每小时抓取一次，写入 data/inbox.jsonl。
从 config.yaml 配置的 RSS 源抓取，每条 RSS 记录创建一个 Article 对象。

设计采用 Collector 与 Pipeline 分离，原因：
- Collector 纯抓取+去重，不需要 API Key
- Pipeline 是 AI 处理入口，需要 API Key
- 分离后 Collector 可以更高频运行

**已实现**: 是 (collector.py)

---

### Stage 1: Fetcher (从 inbox 读取)

处理范围: 近 72 小时内的 inbox.jsonl 文章。
参数控制: --hours 24, --limit 10, --only-unprocessed

此时 Article 字段:
- id = md5(url)
- title = 原始英文标题
- source = RSS 源名称
- published = 发布时间
- content_raw = HTML 格式的正文摘要

**已实现**: 是 (pipeline.py, src/utils.py)

---

### Stage 2: Dedup (去重)

1. URL 精确匹配: 检查相同 URL -> 通过
2. 标题 Jaccard 相似度 > 0.85 -> 无相似 -> 通过

**已实现**: 是 (src/dedup.py)

---

### Stage 3: Classify (AI 分类)

prompt: prompts/classify.md + config.yaml categories
每批 20-25 篇，调用 call_ai()。
失败降级: 标记为 "未分类"

**已实现**: 是 (src/classifier.py)

---

### Stage 4: Concept Miner (概念发现)

检查文章中是否包含尚未建立知识卡片的新概念。

准入规则:
- 1 次出现 -> 候选池
- 2 次出现 -> 草稿卡片
- 3+ 次 -> 人工审查

**已实现**: 是 (src/concept_miner.py)

---

### Stage 5: Knowledge Match (卡片匹配)

load_cards() 遍历 data/knowledge/**/*.yaml (61 张卡片)
match_cards() 使用 Jaccard 相似度匹配文章到卡片。

匹配结果注入摘要 prompt 提供历史背景上下文。

**已实现**: 是 (src/knowledge.py)

---

### Stage 6: Summarize (AI 摘要)

prompt: prompts/summarize.md + knowledge_context
每批 10 篇，ThreadPoolExecutor 并发 3。

输出: title_cn, one_liner, summary_points

**已实现**: 是 (src/summarizer.py)

---

### Stage 7: Score (AI 评分)

四个维度 (权重在 config.yaml):
- 行业影响力 40%
- 技术突破性 25%
- 用户相关性 25%
- 信息独特性 10%

输出: score (1-5), score_reason

**已实现**: 是 (src/scorer.py)

---

### Stage 8: Report (日报生成)

1. 聚类合并同事件多源报道
2. 按评分降序排列
3. 过滤 score >= 3
4. 生成 Markdown

输出: reports/YYYY-MM-DD.md

**已实现**: 是 (src/reporter.py)

---

### Stage 9: DB Sync + Page Refresh

1. init_db() 初始化 SQLite
2. insert_articles() + insert_report()
3. generate_dashboard() + generate_library() + generate_timeline()

页面是静态 HTML shell，数据通过 JS fetch() 从 /api/* 获取。

**已实现**: 是

---

## 三、知识图谱生成 (独立分支)

命令: python pipeline.py --graph

遍历 61 张卡片 -> 节点，读取关系字段 -> 边。
输出: Mermaid 格式 + D3.js HTML (交互式拖拽)。

**已实现**: 是 (src/knowledge_graph.py)

---

## 四、周报/月报分支

命令: python pipeline.py --weekly / --monthly

加载近 N 天日报 -> AI 趋势分析 -> Markdown -> SQLite。

**已实现**: 是 (src/trend_reporter.py)

---

## 五、缓存机制

缓存文件: data/processed_cache.json
- apply_cache() 恢复缓存
- save_results() 写入缓存
- 超过 10000 条淘汰最旧的 50%

**已实现**: 是 (src/cache.py)

---

## 面试官可能追问的问题

1. Collector 和 Pipeline 并发时会不会竞态？  Collector 只写 inbox.jsonl (追加写)，Pipeline 读 inbox.jsonl 写 SQLite。文件不冲突。

2. Pipeline 速度？ 实测 260 篇缓存全命中约 200 秒 (瓶颈在 Concept Miner)。

3. 一篇文章匹配多张卡片？ match_cards() 返回多对多映射，build_context() 格式化为文本块注入。

4. 聚类合并实现？ _cluster_articles() 按 cluster_id 分组。最高分为主报道。

5. 中途失败？ 每个阶段独立，缓存确保已处理文章不重复。重新运行跳过已处理。

6. 需人工确认: 各阶段精确耗时依赖 API 响应速度，缓存命中率越高速度越快。
