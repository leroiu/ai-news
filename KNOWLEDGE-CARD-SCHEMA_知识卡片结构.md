# Knowledge Card Schema v1.0

> AI Intelligence Hub 的唯一事实来源（Single Source of Truth）
>
> 所有模块（Timeline / Daily / Weekly / Monthly / Graph / RAG / Search）
> 都只读取 Knowledge Card，不自行存储数据。

---

## 目录结构

```
data/knowledge/
  models/         # 模型卡片
  companies/      # 公司卡片
  tech/           # 技术卡片
  people/         # 人物卡片
  events/         # 事件卡片
  concepts/       # 概念卡片
  papers/         # 论文卡片（预留）
  datasets/       # 数据集卡片（预留）
  benchmarks/     # 基准测试卡片（预留）
  products/       # 产品卡片（预留）
  opensource/     # 开源项目卡片（预留）
```

文件名 = `{id}.yaml`，如 `gpt-4.yaml`。

注意：不存在独立的 `data/timeline/` 目录。Timeline 只是 Knowledge Card 的一个视图——按 `release_date` 排序所有 Card 即可生成。不存两份数据。

## 架构约束

```
Knowledge Card（唯一数据源）
    │
    ├── Timeline 视图      按 date 排序
    ├── Knowledge Graph     按 related/depends_on/influenced 生成节点和边
    ├── Daily 引用          按 tags/aliases 匹配，注入日报 prompt
    ├── Company Page        按 type=company 筛选 + 反向引用
    ├── Model Page          按 type=model 筛选 + 反向引用
    ├── Search              全字段检索
    └── RAG                 向量化后语义检索
```

所有模块只读不写。修改一张 Card，所有视图自动受益。

---

## 通用字段（所有 type 必填或可选）

```yaml
# ============================================================
# 标识
# ============================================================
id: gpt-4                          # ★必填，唯一 ID，kebab-case
name: GPT-4                        # ★必填，显示名称
type: model                        # ★必填，见下方 type 枚举
aliases:                           # 搜索/匹配别名，解决新闻中拼写不一致
  - GPT4
  - GPT-4
  - GPT 4
  - gpt4

# ============================================================
# 时间
# ============================================================
release_date: 2023-03-14           # 发布日期（公司用成立日期）
end_date:                          # 结束日期（停服/废弃/离职时填）
status: active                     # active | deprecated | preview | closed | rumored

# ============================================================
# 归属
# ============================================================
company: OpenAI                    # 所属公司（name 或 company card id）
creators:                          # 关键人物
  - Ilya Sutskever
  - Sam Altman

# ============================================================
# 分类
# ============================================================
tags:                              # ★必填，多维度标签，用于匹配和检索
  - llm
  - multimodal
  - reasoning
  - api
  - openai

# ============================================================
# 评级（两套独立体系）
# ============================================================
importance: 5                      # 历史重要性（1-5），人工策展，永久不变
confidence: confirmed              # confirmed | disputed | speculative

# ============================================================
# 内容
# ============================================================
summary: |                         # ★必填，一句话概述（≤100字）
  首个大规模多模态 LLM。

significance: |                    # ★必填，为什么重要（≤500字）
  GPT-4 是多模态 LLM 的里程碑。在推理、代码生成和文本理解方面
  远超 GPT-3.5，直接奠定了 ChatGPT Plus 的商业模式。

background: |                      # 详细背景（可选，长度不限）
  （完整的发布背景、技术细节、社会影响等）

# ============================================================
# 时间线（该实体自身的关键节点）
# ============================================================
timeline:                          # 不与 data/timeline/ 混淆——这是卡片自身的里程碑
  - date: 2023-03-14
    event: 正式发布
  - date: 2023-11-06
    event: Turbo 版发布（GPT-4 Turbo）
  - date: 2024-05-13
    event: Omni 版发布（GPT-4o）

# ============================================================
# 关系
# ============================================================
related:                           # 双向关联——互相引用
  - chatgpt
  - gpt-4o
  - gpt-5

depends_on:                        # 前置依赖——"因为有了 X 才有了我"
  - transformer
  - rlhf

influenced:                        # 后继影响——"我影响了谁"（depends_on 的反向）
  - gpt-4o
  - multimodal-llm-wave

# ============================================================
# 外部引用
# ============================================================
sources:                           # 信息来源
  official: https://openai.com/research/gpt-4
  paper: https://arxiv.org/abs/2303.08774
  wikipedia:
  github:
```

---

## type 枚举

| type | 目录 | 说明 | 特有字段 |
|------|------|------|----------|
| `model` | models/ | AI 模型 | `parameters`, `modalities`, `license` |
| `company` | companies/ | 公司/组织 | `headquarters`, `founded`, `funding_total` |
| `tech` | tech/ | 技术/架构 | `category` (训练/推理/部署/安全) |
| `person` | people/ | 人物 | `role`, `affiliations`, `known_for` |
| `event` | events/ | 事件 | `event_type` (launch/conference/acquisition/…) |
| `concept` | concepts/ | 概念 | `domain` (training/inference/safety/ethics/…) |

待扩展：`paper`, `dataset`, `benchmark`, `product`, `opensource`

---

## 各 type 特有字段

### model

```yaml
type: model
parameters: "1.76T (传闻)"        # 参数量
modalities:                       # 模态
  - text
  - image
  - audio
license: "proprietary"            # proprietary | open-source | open-weight
architecture: "MoE"               # Transformer | MoE | Mamba | ...
```

### company

```yaml
type: company
headquarters: "San Francisco, CA"
founded: 2015
funding_total: "$11.3B (截至 2025)"
business_model: "API + 订阅"      # 一句话
key_products:
  - chatgpt
  - gpt-4
  - dall-e
```

### tech

```yaml
type: tech
category: "推理加速"              # 训练 | 推理 | 部署 | 安全 | 对齐 | 数据 | 评测
```

### person

```yaml
type: person
role: "CEO"
affiliations:                     # 所属组织
  - openai
  - y-combinator
known_for:                        # 因何知名
  - ChatGPT 发布
  - Worldcoin
```

### event

```yaml
type: event
event_type: "product_launch"      # product_launch | conference | acquisition |
                                  # paper_publish | policy_change | controversy
date: 2022-11-30                  # 事件日期（比 release_date 更精确）
```

### concept

```yaml
type: concept
domain: "training"                # training | inference | safety | ethics |
                                  # evaluation | architecture | data
```

---

## 字段优先级汇总

| 优先级 | 字段 | 含义 |
|--------|------|------|
| ★★★ | id, name, type, tags, summary, significance | 每张卡必须填 |
| ★★☆ | release_date, status, company, importance, related, depends_on, timeline | 有信息就填 |
| ★☆☆ | aliases, confidence, influenced, sources, background | 丰富卡片时补 |
| type特有 | parameters, headquarters, role, category, domain | 按类型填 |

---

## 设计原则

### 1. importance ≠ score

```
score       = AI 实时打分的"今日新闻热度"（1-5★），只对 Daily 有意义
importance  = 人工策展的"历史重要性"（1-5），永久不变
```

例：GPT-6 今天发布 → score=★5, importance=待观察  
例：Transformer → score=无, importance=5（改变了整个行业）

### 2. related vs depends_on vs influenced

```
related:    双向，"参见"——没有因果顺序
depends_on: 单向，"因为有了 X 才有了我"
influenced: 单向，"我影响了谁"（是 depends_on 的反向边）
```

写卡时只需填一边，另一边可自动推导。通常填 `related` + `depends_on`，
`influenced` 由工具补充。

### 3. tags 不做层级

不嵌套 `ai.llm.transformer`，而是平铺 `[llm, transformer, architecture]`。
层级让以后搜索/聚类去推断，不要现在定死。

### 4. 先有数据，后有 Schema

新增 type 时：先写 5 张卡，再回来补 Schema。不在写 0 张卡的情况下设计新字段。

---

## 第一批卡片（V2 产出）

| # | ID | type | 说明 |
|---|-----|------|------|
| 1 | `transformer` | tech | Attention Is All You Need |
| 2 | `gpt-4` | model | OpenAI GPT-4 |
| 3 | `chatgpt` | event | ChatGPT 发布 |
| 4 | `mcp` | tech | Model Context Protocol |
| 5 | `openai` | company | OpenAI |
| 6 | `anthropic` | company | Anthropic |
| 7 | `claude-fable-5` | model | Claude Fable 5 |
| 8 | `deepseek-v3` | model | DeepSeek V3 |
| 9 | `rlhf` | concept | RLHF 概念 |
| 10 | `agent` | concept | AI Agent 概念 |
