# AI Intelligence Platform — 变更日志

> **Layer 2 — 按需加载**
> 按版本记录用户可感知的变化。

---

## V1.8 — 中文版界面 + AI 后端简化

- **日期**: 2026-06-30
- **主题**: Dashboard / Library / Graph / Timeline / Entity Detail 全部中文化，AI 后端简化为 DeepSeek + Kimi
- **新增**:
  - 中文版界面（TYPE_LABELS 统一中文）
  - ENGINEERING_PRINCIPLES.md（Context Budget Rule）
  - 文档体系完善（DECISIONS / CHANGELOG / SESSION_RULES）
- **变更**:
  - AI 后端：移除 Anthropic，保留 DeepSeek + Kimi 双后端

## V1.7 — SQLite 数据层 + FastAPI

- **日期**: 2026-06
- **主题**: 引入 SQLite 统一数据层，FastAPI Web 服务
- **新增**:
  - SQLite 数据库（4 表，WAL，INSERT OR REPLACE）
  - FastAPI 服务（8 端点 + 5 页面路由）
  - API-driven HTML shell 页面
- **变更**:
  - 数据从纯文件迁移到 SQLite + 文件混合存储

## V1.6 — Knowledge Graph

- **日期**: 2026-06
- **主题**: 知识图谱可视化
- **新增**:
  - 知识图谱（Mermaid + D3.js）
  - Timeline v2（横向滑动 + 年份滑块 + 点击展开）
  - Entity Detail 页（API-driven HTML）

## V1.5 — Dashboard 集成

- **日期**: 2026-06
- **主题**: 日报/周报/月报 Dashboard 集成
- **新增**:
  - Dashboard 页面（Reports Hero + Report History + 筛选）
  - 日报历史引用优化（叙述性上下文）

## V1.4 — 周报/月报系统

- **日期**: 2026-06
- **主题**: 趋势分析与周期报告
- **新增**:
  - 周报生成（`--weekly`，AI 趋势分析）
  - 月报生成（`--monthly`）
  - Trend Reporter 模块

## V1.3 — Knowledge Card 系统

- **日期**: 2026-06
- **主题**: 结构化知识卡片
- **新增**:
  - Knowledge Card Schema v1.0
  - 61 张卡片（7 种类型）
  - Concept Miner（候选池 + 准入规则）
  - AI 处理缓存（`src/cache.py`）

## V1.2 — Pipeline 性能优化

- **日期**: 2026-06
- **主题**: Pipeline inbox 模式 + 性能优化
- **新增**:
  - `--limit` / `--concurrency` / `--only-unprocessed` 参数
  - 并发摘要（ThreadPoolExecutor）
  - 260 篇已处理基线

## V1.1 — Collector 独立拆分

- **日期**: 2026-06
- **主题**: 采集器与管道分离
- **新增**:
  - Collector 独立脚本（每小时抓取，写入 inbox.jsonl）
  - Windows Task Scheduler 调度

## V1.0 — 日报生成

- **日期**: 2026-06
- **主题**: 首个可用版本
- **新增**:
  - RSS 抓取 → AI 分类/摘要/评分 → Markdown 日报
  - 日报 Pipeline（去重 → 分类 → 摘要 → 评分 → 报告）

---

> **维护**: 每个版本发布时新增一条。
