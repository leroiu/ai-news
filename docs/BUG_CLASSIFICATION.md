# Bug Classification Guide

> 本指南用于在不懂代码的情况下，也能根据现象把问题快速归类到模块，从而决定下一步：自己修、丢给 AI、还是暂时绕过。
>
> 适用项目：AI Intelligence Platform（ai-news）

---

## 1. 核心原则

遇到 bug 时，先不要想"代码哪里错了"，而是回答三个问题：

1. **我看到了什么？**（现象）
2. **哪个环节出的问题？**（模块）
3. **影响范围有多大？**（全部 / 某个来源 / 某篇文章 / 某个页面）

本指南把项目拆成 6 大模块、12 个子模块。对照下表即可快速定位。

---

## 2. 模块速查表

| 模块 | 职责 | 典型症状 |
|------|------|---------|
| **Fetcher（抓取）** | 从 RSS / 网页 / 来源拉取新闻 | 新闻数量突然变少；某个来源完全空白；内容残缺；抓取很慢 |
| **Summarizer（摘要）** | 把文章生成中文一句话摘要 | 摘要胡说；遗漏重点；英文没有翻译；格式不对 |
| **Classifier（分类）** | 给文章打标签 / 分类 | 分类错误；标签混乱；重要新闻没被归类 |
| **Dedup（去重）** | 排除重复或相似文章 | 同一条新闻出现多次；新文章被误当成旧文删除 |
| **Scorer（评分）** | 给新闻重要性打分 | 重要新闻排名低；垃圾新闻排前面 |
| **Knowledge（知识卡片）** | YAML 卡片加载与匹配 | 卡片不显示；匹配错误；摘要没引用背景 |
| **Embeddings（嵌入/语义搜索）** | 向量生成与语义匹配 | 语义搜索没结果；卡片匹配不准；API 报错 |
| **Reporter（报告生成）** | 生成 Markdown / 日报 | 日报格式乱；章节缺失；链接失效 |
| **Frontend（前端）** | 网页展示与交互 | 页面白屏；按钮没反应；排版错位；加载慢 |
| **Database（数据库）** | SQLite 存储与查询 | 程序启动失败；查询慢；数据丢失；表不存在 |
| **Config / Env（配置/环境）** | API Key、路径、依赖、权限 | 突然全部失败；某个功能时好时坏；换了电脑就出問題 |
| **Pipeline（流程调度）** | 串联所有步骤、定时任务 | 定时任务没跑；流程卡住不动；某个步骤被跳过 |

---

## 3. 按症状定位

### 3.1 数据类问题

| 现象 | 可能模块 | 你该检查什么 |
|------|---------|-------------|
| 新闻数量突然变少 | Fetcher / Source | 源网站是否正常；API Key 是否过期；网络是否可达 |
| 新闻有，但摘要/分类不对 | Summarizer / Classifier | 看摘要质量；看标签是否正确 |
| 同一条新闻重复出现 | Dedup | 标题是否极度相似；去重阈值是否合理 |
| 搜索不到相关卡片 | Embeddings / Knowledge | 卡片是否已嵌入；语义 API 是否可用 |
| 卡片匹配错误 | Knowledge / Embeddings | 查询和卡片语义是否相关 |

### 3.2 报错 vs 结果错误

| 类型 | 例子 | 处理建议 |
|------|------|---------|
| **报错型** | 数据库连不上、API 429、文件找不到 | 把最后 20 行报错复制给 AI，定位最快 |
| **结果型** | 摘要差、分类错、匹配错 | 提供"输入 + 期望输出 + 实际输出"样本 |
| **体验型** | 页面丑、加载慢、按钮没反应 | 截图 + 描述操作步骤 |

### 3.3 发生频率

| 频率 | 含义 | 应对 |
|------|------|------|
| 必现 | 代码逻辑或配置问题 | 一定能定位，给 AI 复现步骤 |
| 偶发 | API 波动、网络、限流、数据异常 | 看日志、加容错、换 provider |
| 定时出现 | cron / 调度 / 资源问题 | 检查定时脚本和运行时长 |

---

## 4. 定位检查单

遇到 bug 时按这个顺序扫一遍：

### Step 1：看报错关键词

| 报错里出现 | 对应模块 |
|-----------|---------|
| `fetcher` / `rss` / `source` / `feed` | 输入层 - Fetcher |
| `summarize` / `classify` / `prompt` / `anthropic` / `openai` | 处理层 - Summarizer / Classifier |
| `embeddings` / `knowledge` / `match` / `cosine` | 知识层 - Embeddings / Knowledge |
| `reporter` / `report` / `markdown` / `template` | 输出层 - Reporter |
| `frontend` / `streamlit` / `page` / `component` | 前端 - Frontend |
| `sqlite` / `database` / `table` / `integrity` | 基础设施 - Database |
| `config` / `env` / `key` / `permission` / `module not found` | 基础设施 - Config / Env |
| `pipeline` / `cron` / `schedule` / `timeout` | 流程 - Pipeline |
| 没有报错，但结果不对 | 结果型 / 静默错误 |

### Step 2：看影响范围

| 影响范围 | 可能模块 |
|---------|---------|
| 只有某个来源出问题 | Fetcher / Source |
| 只有摘要/分类出问题 | Summarizer / Classifier |
| 只有搜索/卡片出问题 | Knowledge / Embeddings |
| 只有网页展示出问题 | Frontend |
| 全部流程都崩 | Config / Env / Database / Pipeline |

### Step 3：收集证据

定位时给 AI 的信息越准，修复越快。建议每次固定收集：

1. **错误截图或最后 20-30 行日志**
2. **出问题的输入**：哪篇文章 / 哪个查询 / 哪张卡片
3. **期望结果** 和 **实际结果**
4. **最近是否改过**：配置 / 源 / 依赖 / 环境

---

## 5. 问题记录模板

建议每次遇到 bug 都用这个格式记录，方便后续统计和复盘：

```markdown
## 问题记录

- **现象**: （一句话描述你看到什么）
- **模块猜测**: （Fetcher / Summarizer / Classifier / Dedup / Scorer / Knowledge / Embeddings / Reporter / Frontend / Database / Config / Pipeline）
- **影响范围**: （全部 / 某个来源 / 某篇文章 / 某个页面）
- **频率**: （必现 / 偶发 / 定时）
- **证据**: （截图 / 日志 / 输入输出样本）
- **决策**: （立即修 / 延后 / 绕过 / 需要更多信息）
```

---

## 6. 决策建议

根据问题类型决定下一步：

| 情况 | 建议动作 |
|------|---------|
| 报错明确，知道模块 | 把报错 + 复现步骤给 AI，直接修 |
| 结果不好（摘要/分类/匹配差） | 收集 3-5 个坏样本，调整 prompt 或阈值 |
| 某个 API 偶发失败 | 加降级逻辑或换 provider |
| 前端展示问题 | 截图 + 描述，让 AI 修改 UI |
| 数据来源问题 | 先确认源网站/API 是否正常，再决定修程序还是换源 |
| 无法判断模块 | 先用本指南定位；仍不确定就收集日志给 AI |

---

## 7. 进阶：建立日志和标签机制

### 7.1 日志分模块查看

项目已有 `logs/` 目录。建议出问题优先查看对应日志：

| 模块 | 可能日志文件 |
|------|-------------|
| Fetcher | `logs/fetcher.log` / `logs/pipeline.log` |
| Summarizer / Classifier | `logs/pipeline.log` / `logs/ai_client.log` |
| Embeddings | `logs/embeddings.log` |
| Reporter | `logs/reporter.log` |
| Frontend | 浏览器控制台 + `logs/frontend.log` |
| Pipeline / Cron | `logs/pipeline.log` / 系统 cron 日志 |

### 7.2 问题标签

如果使用 GitHub Issues 或本地文档追踪，建议给每个 bug 打标签：

- `input`, `processing`, `knowledge`, `output`, `frontend`, `infra`, `pipeline`

每月回顾一次，就能看出哪个模块是"重灾区"，优先加固。

---

## 8. 快速决策树

```
遇到问题
  │
  ├─ 程序报错？
  │    ├─ 报错里有 fetch/rss/source → Fetcher
  │    ├─ 报错里有 summarize/classify/prompt → Summarizer / Classifier
  │    ├─ 报错里有 embeddings/knowledge/match → Embeddings / Knowledge
  │    ├─ 报错里有 frontend/page → Frontend
  │    ├─ 报错里有 sqlite/database → Database
  │    └─ 报错里有 config/env/key → Config / Env
  │
  ├─ 结果不对但没有报错？
  │    ├─ 新闻少/缺失 → Fetcher
  │    ├─ 摘要/分类差 → Summarizer / Classifier
  │    ├─ 重复新闻 → Dedup
  │    ├─ 排名不合理 → Scorer
  │    ├─ 卡片不匹配 → Knowledge / Embeddings
  │    └─ 日报格式乱 → Reporter
  │
  └─ 前端/展示问题？
       └─ Frontend
```

---

## 9. 维护说明

- 本指南应随项目架构变化而更新。
- 新增模块时，应在第 2 节"模块速查表"中补充。
- 新增典型症状时，应在第 3 节"按症状定位"中补充。

---

*最后更新：2026-07-23*
