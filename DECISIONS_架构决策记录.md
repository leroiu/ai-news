# AI Intelligence Platform — 架构决策记录

> **Layer 2 — 按需加载**
> 编号的 ADR (Architecture Decision Records)，简洁可扫描。
> 详细的设计演进叙事见 `OPENSPEC_原始设计.md`。

---

## ADR-001: Knowledge Card (YAML) 是 SSOT

- **日期**: 2026-06
- **状态**: ✅ 采纳
- **决策**: Knowledge Card 是整个系统的唯一事实来源，所有模块只读 Card
- **理由**: 单一写入路径（手动编辑 YAML 或 Concept Miner），避免数据不一致
- **替代方案**: 以数据库为主存储 — 放弃，因为 YAML 可读性好、git 可追踪

## ADR-002: SQLite 而非 PostgreSQL

- **日期**: 2026-06
- **状态**: ✅ 采纳
- **决策**: 使用 SQLite + WAL 模式作为唯一数据库
- **理由**: 零配置，单人使用足够，WAL 模式读写不冲突，备份就是 cp 文件
- **替代方案**: PostgreSQL — 放弃，单人场景下运维成本过高

## ADR-003: API-driven UI

- **日期**: 2026-06
- **状态**: ✅ 采纳
- **决策**: 页面为静态 HTML shell，数据通过 JS fetch /api/* 动态获取
- **理由**: 数据变化时无需重新生成 HTML 文件
- **替代方案**: SSR / 模板渲染 — 放弃，数据变化需重新生成 HTML

## ADR-004: Jaccard 匹配而非 Embedding

- **日期**: 2026-06
- **状态**: ✅ 采纳
- **决策**: 文章与知识卡片匹配使用 Jaccard 关键词相似度
- **理由**: 零成本、可离线，61 张卡片规模下精度足够
- **替代方案**: Embedding + 向量搜索 — 远期考虑，当前规模不需要

## ADR-005: importance ≠ score

- **日期**: 2026-06
- **状态**: ✅ 采纳
- **决策**: importance（人工策展的历史价值）和 score（AI 实时打分的新闻热度）分开存储
- **理由**: 两者含义不同，混用会导致排序混乱
- **替代方案**: 单一评分字段 — 放弃，无法区分长期价值和短期热度

## ADR-006: 文件驱动而非 ORM

- **日期**: 2026-06
- **状态**: ✅ 采纳
- **决策**: 不使用 SQLAlchemy 等 ORM，直接用 sqlite3 + 手写 SQL
- **理由**: 简单透明，4 张表不需要 ORM 的抽象层
- **替代方案**: SQLAlchemy — 放弃，增加依赖和学习成本

## ADR-007: Collector 与 Pipeline 分离

- **日期**: 2026-06
- **状态**: ✅ 采纳
- **决策**: Collector 无 AI 依赖（纯抓取+去重），Pipeline 是 AI 处理入口
- **理由**: Collector 每小时运行，不能依赖 AI API；分离后各自独立调度
- **替代方案**: 合并在一个脚本 — 放弃，无法独立调度

## ADR-008: INSERT OR REPLACE（非 IGNORE）

- **日期**: 2026-06
- **状态**: ✅ 采纳
- **决策**: 数据库写入使用 INSERT OR REPLACE 而非 INSERT OR IGNORE
- **理由**: Pipeline 处理后必须覆写裸数据（score=0 → score=N）
- **替代方案**: INSERT OR IGNORE — 已推翻，导致 AI 处理后的数据无法写入

## ADR-009: ThreadPoolExecutor 并发摘要

- **日期**: 2026-06
- **状态**: ✅ 采纳
- **决策**: 摘要生成使用 ThreadPoolExecutor 并发调用 AI API
- **理由**: DeepSeek/Kimi API 每批次 ~30s，3 并发将 27 批从 ~810s 缩短到 ~278s
- **替代方案**: 串行调用 — 放弃，耗时过长

## ADR-010: 双后端 DeepSeek + Kimi

- **日期**: 2026-06
- **状态**: ✅ 采纳
- **决策**: 使用 DeepSeek + Kimi 双 OpenAI 兼容后端，移除 Anthropic
- **理由**: DeepSeek 和 Kimi 提供 OpenAI 兼容 API，统一调用方式；Anthropic 端点通过 DeepSeek 兼容代理转发
- **替代方案**: 保留 Anthropic SDK — 已推翻，统一为 OpenAI 兼容接口

## ADR-011: Context Budget Rule

- **日期**: 2026-06
- **状态**: ✅ 采纳
- **决策**: 一个 Conversation 一个 Feature；>300行文件必须拆分；60%收尾/70%完成/75% compact
- **理由**: 防止单会话上下文爆炸，保持开发效率
- **替代方案**: 无限制开发 — 放弃，已多次出现上下文爆炸

## ADR-012: Plugin Architecture — 可插拔接口预留

- **日期**: 2026-07-01
- **状态**: ✅ 采纳（仅接口定义，不实现商业逻辑）
- **决策**: 所有商业化功能（认证、计费、调度、存储、Research 计费）通过 ABC 抽象接口定义在 `interfaces/`，默认使用本地免认证实现，未来通过依赖注入切换到云端实现
- **接口清单**:
  - `AuthProvider` — 用户认证（本地版：免登录单用户；云版：JWT 多租户）
  - `BillingProvider` — 计费/积分（本地版：全免；云版：按 tier 限制）
  - `SchedulerProvider` — 任务调度（本地版：CLI 手动；云版：Cron/Queue）
  - `StorageProvider` — 存储（本地版：文件系统；云版：S3）
  - `ResearchProvider` — Research 入口（本地版：直接调用；云版：计费包裹）
- **原则**: 只定义接口签名，不实现云端逻辑。所有接口默认绑定本地无限制实现
- **理由**: 现在实现商业化会增加 3-4 周工作量且无用户验证需求；预留接口保证未来可以无缝切换到云版本而不改动核心引擎代码
- **替代方案**: 现在就实现完整多租户 — 暂缓，无用户时过早优化
- **配置文件**: 详见 `商业化架构决策.md`（同目录，完整架构设计）

## ADR-013: Open Core / Closed Cloud — 双仓库策略

- **日期**: 2026-07-01
- **状态**: ✅ 采纳（暂不建私有仓库，等有用户后执行）
- **决策**: 项目分为公开核心仓库（MIT）和私有云仓库两个独立 repo
- **开源 (ai-news, GitHub 公开)**:
  - `engine/` — 全部核心引擎
  - `interfaces/` — 全部 ABC 接口定义
  - `plugins/` — 本地实现（单用户、免计费）
  - `frontend/` — 核心 9 个页面
  - `api/` — FastAPI 工厂 + 公开路由
  - `cli/` — collector / pipeline 命令行
- **闭源 (ai-news-cloud, 私有仓库)**:
  - `services/` — CloudAuth, CloudBilling, CloudScheduler, CloudStorage, CloudResearch
  - `frontend/` — Login, Settings, Billing, Admin 页面
  - `api/` — Auth/Billing/Admin 路由
- **当前阶段**: 只开发开源核心，不建私有仓库。代码结构中保留 `interfaces/` 和 `plugins/` 目录作为扩展点
- **理由**: 先有用户和社区再考虑商业化；但架构上现在就分离边界，避免未来需要大规模重构
- **替代方案**: 全部代码公开 — 放弃，商业化时无法对云服务收费

---

> **维护**: 每次重大技术决策后新增一条。决策被推翻时更新状态（标注 `❌ 已推翻` + 指向新决策），不删除。
