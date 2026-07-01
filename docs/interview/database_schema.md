# Database Schema — AI Intelligence Platform

> 面试准备文档。说明 SQLite 数据库的表结构、字段含义、表间关系和索引策略。

---

## 一、数据库概览

**类型**: SQLite (WAL 模式)
**路径**: data/platform.db
**连接管理**: 每次操作获取独立连接，操作完后立即关闭。不保持长连接。
**外键约束**: 启用 (PRAGMA foreign_keys=ON)
**并发模式**: WAL 模式支持并发读（读不阻塞写）

共 4 张表: entities, relationships, articles, reports

---

## 二、表结构详解

### 2.1 entities (实体表 — 知识卡片)

存储 Knowledge Card 的持久化数据。从 YAML 卡片文件同步到 SQLite。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PRIMARY KEY | 卡片唯一 ID (如 gpt-5) |
| name | TEXT | NOT NULL | 实体名称 (如 GPT-5) |
| type | TEXT | NOT NULL | 实体类型 (7 种, 见下方) |
| importance | INTEGER | DEFAULT 3 | 人工策展评分 1-5 |
| summary | TEXT | DEFAULT '' | 摘要描述 |
| significance | TEXT | DEFAULT '' | 重要性说明 (长文本) |
| release_date | TEXT | DEFAULT '' | 发布日期 (ISO 格式) |
| company | TEXT | DEFAULT '' | 所属公司 |
| tags | TEXT | DEFAULT '[]' | 标签 (JSON 数组) |
| aliases | TEXT | DEFAULT '[]' | 别名 (JSON 数组) |
| timeline | TEXT | DEFAULT '[]' | 时间线事件 (JSON 数组, 含 date + event) |
| color | TEXT | DEFAULT '#999' | 图谱节点颜色 |
| created_at | TEXT | DEFAULT datetime('now') | 创建时间 |
| updated_at | TEXT | DEFAULT datetime('now') | 更新时间 |

**7 种实体类型**:

| type | 说明 | 示例 | 节点颜色 |
|------|------|------|----------|
| model | AI 模型 | GPT-5, Claude 4, DeepSeek-R1 | #4C78A8 (蓝色) |
| company | AI 公司 | OpenAI, DeepSeek, Anthropic | #F58518 (橙色) |
| person | AI 人物 | Sam Altman, 李飞飞 | #B279A2 (紫色) |
| methodology | 方法论 | Prompt Engineering, RAG, Agent | #D4A017 (金色) |
| tech | 核心技术 | Transformer, MCP, BERT | #72B7B2 (青色) |
| concept | AI 概念 | RLHF, MoE, LoRA | #E45756 (红色) |
| product | AI 产品 | ChatGPT, GitHub Copilot | #54A24B (绿色) |

**实体类型说明**: 7 种类型完整实现。新增 type 的流程是先写 5 张 YAML 卡片验证，再更新 KNOWNLEDGE-CARD-SCHEMA.md。

---

### 2.2 relationships (关系表)

记录实体之间的关联关系，用于知识图谱构建。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 自增 ID |
| source_id | TEXT | NOT NULL, FK -> entities(id) | 源实体 ID |
| target_id | TEXT | NOT NULL, FK -> entities(id) | 目标实体 ID |
| rel_type | TEXT | NOT NULL | 关系类型 (3 种) |
| label | TEXT | DEFAULT '' | 关系标签 |

**唯一约束**: UNIQUE(source_id, target_id, rel_type)

**3 种关系类型**:

| rel_type | 说明 | 示例 |
|----------|------|------|
| related | 关联关系 (灰色虚线) | GPT-5 与 RLHF 相关 |
| depends_on | 依赖关系 (红色实线) | Claude 依赖于 Transformer |
| influenced | 影响关系 (蓝色实线) | 李飞飞影响了计算机视觉发展 |

---

### 2.3 articles (文章表)

存储 AI 处理后的文章及其元数据。Pipeline 处理结果的持久化层。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PRIMARY KEY | Article ID = md5(url) |
| title | TEXT | NOT NULL | 原始标题 (英文) |
| url | TEXT | NOT NULL | 文章链接 |
| source | TEXT | DEFAULT '' | 来源名称 (RSS 源名) |
| published | TEXT | DEFAULT '' | 发布时间 (ISO 格式) |
| content_raw | TEXT | DEFAULT '' | 原始正文/摘要 |
| categories | TEXT | DEFAULT '[]' | AI 分类标签 (JSON 数组) |
| title_cn | TEXT | DEFAULT '' | AI 生成的中文标题 |
| one_liner | TEXT | DEFAULT '' | AI 生成的一句话概括 |
| summary_points | TEXT | DEFAULT '[]' | AI 生成的三点摘要 (JSON 数组) |
| score | INTEGER | DEFAULT 0 | AI 评分 1-5 |
| score_reason | TEXT | DEFAULT '' | 评分理由 |
| cluster_id | TEXT | DEFAULT '' | 事件聚类 ID (同事件多源合并) |
| created_at | TEXT | DEFAULT datetime('now') | 创建时间 |

**写入策略**: INSERT OR REPLACE (非 IGNORE)，确保 AI 处理后的数据可以覆写之前的裸数据。

---

### 2.4 reports (报告表)

记录每天生成的日报/周报/月报的元数据。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 自增 ID |
| date | TEXT | NOT NULL UNIQUE | 报告日期 |
| report_type | TEXT | DEFAULT 'daily' | 报告类型: daily / week / month |
| path | TEXT | NOT NULL | Markdown 文件路径 |
| fetched | INTEGER | DEFAULT 0 | 本次抓取文章数 |
| filtered | INTEGER | DEFAULT 0 | 最终采用文章数 |
| star5 | INTEGER | DEFAULT 0 | 5 星文章数 |
| star4 | INTEGER | DEFAULT 0 | 4 星文章数 |
| star3 | INTEGER | DEFAULT 0 | 3 星文章数 |
| created_at | TEXT | DEFAULT datetime('now') | 创建时间 |

---

## 三、索引策略

```sql
CREATE INDEX idx_entities_type ON entities(type);
CREATE INDEX idx_relationships_source ON relationships(source_id);
CREATE INDEX idx_relationships_target ON relationships(target_id);
CREATE INDEX idx_articles_published ON articles(published);
CREATE INDEX idx_articles_score ON articles(score);
CREATE INDEX idx_reports_date ON reports(date);
```

**说明**:
- entities.type 常用于按类型筛选实体列表
- relationships.source/target 用于查询实体关联关系 (图谱渲染)
- articles.published 用于按时间排序和过滤
- articles.score 用于按评分筛选高价值文章
- reports.date 用于按时间倒序获取最新报告

---

## 四、表关系图

```
entities (1) ------< (N) relationships >------ (1) entities
   |                                                |
   | (entity_id <-> source_id/target_id)            |
   |                                                |
   +---- (articles 通过 categories 与 entities 间接关联)
   |      (keyword/keyname 模糊匹配)
   |
   +---- reports (独立，记录报告元数据)
          (无外键关联，文件路径直接引用)
```

**关系说明**:
1. entities 与 relationships 通过外键关联 (一对多)
2. articles 与 entities 之间无直接外键，通过 knowledge.py 的 Jaccard 匹配算法间接关联
3. reports 与其他表无外键关联，是独立的报告元数据记录

---

## 五、JSON 字段处理

tags, aliases, timeline, categories, summary_points 以 JSON 字符串存储。

```python
# 写入时序列化
json.dumps(data, default=str)

# 读取时反序列化
json.loads(raw_string)
```

default=str 参数处理 datetime.date 等不可序列化类型。

---

## 六、数据同步机制

知识卡片 (YAML) 通过 sync_cards.py 同步到 SQLite entities 表。

```python
# sync_cards.py
1. load_cards() 遍历 data/knowledge/**/*.yaml
2. 调用 upsert_entity() 逐条写入 SQLite
3. 同时写入 relationships 表
```

**SSOT 原则**: YAML 文件是唯一写入点，SQLite 是只读缓存 (供 API 快速查询)。

---

## 面试官可能追问的问题

1. **为什么用 INSERT OR REPLACE 而不是 IGNORE？** — 早期版本用 IGNORE，发现 AI 处理后的数据无法覆写裸数据 (score=0)，导致日报一直显示未处理文章。改用 REPLACE 后解决。

2. **SQLite 能支持多少条文章？** — 当前约 280 条。SQLite 单表百万级无压力，单人场景不是瓶颈。更大规模时考虑分区或迁移到 PostgreSQL。

3. **JSON 字段的查询效率？** — 简单场景 (LIKE 模糊匹配) 足够。复杂查询需要引入 SQLite JSON1 扩展 (Python 自带)。更大规模可考虑拆成关联表。

4. **entities 和 articles 之间为什么没有外键？** — 文章与卡片的匹配是 Jaccard 相似度匹配，不是精确外键关联。一篇文章可能匹配多张卡片，一张卡片也可能被多篇文章关联。

5. **WAL 模式解决了什么问题？** — 默认回滚日志模式下读操作会阻塞写操作。Pipeline 写数据库时如果用户正在浏览 Dashboard，读操作会等待。WAL 模式下读不阻塞写。

6. **需人工确认**: 当前 entities 表中 importance 字段由人工在 YAML 中维护，sync 脚本同步到 DB。score 字段由 AI 实时打分 (属于 articles 表)。两个字段含义不同，不冲突。
