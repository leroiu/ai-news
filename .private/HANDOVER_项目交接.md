# AI Intelligence Platform — 项目交接文档

> 任何新的 Claude 会话第一件事就是读这个文件。
> 每次会话结束时自动更新。

## 项目定位

AI 观察室 (AI Observatory) — AI 智能情报平台。News / Knowledge / Graph / Research。
Knowledge Card 是整个系统的唯一事实来源（SSOT）。

## 当前状态（2026-07-02 更新）

### 本次会话完成 — Concept Miner Agent ✅ (2026-07-02)

- ✅ **Agent 决策核心** (`src/engine/concept_agent.py`, ~220行)：Semantic Lookup → AI Decide → Execute
  - 语义查找：`embed_texts()` + `cosine_similarity()` 匹配已有卡片，top-5 返回
  - AI 决策：NEW（入库）/ MERGE（合并建议）/ SKIP（丢弃）/ DRAFT（暂存）
  - 每个决策记录 `_agent_decision` + `_agent_reason` + `_similar_cards` 到 pool entry
  - Fallback 机制：AI 不可用时用相似度阈值降级（sim<0.5→NEW, sim≥0.5→DRAFT）
- ✅ **Decision Prompt** (`prompts/concept-decide.md`)：轻量级策展决策提示词
- ✅ **Pipeline 集成**：`CONCEPT_AGENT=1` 环境变量启用 agent 模式，默认保持原有行为
- ✅ **concept_miner.py 零改动** — 完全向后兼容
- ✅ **测试**: 265 passed (+12), 0 failures, 0 regressions

### 本次会话完成 — Research Agent 试点 ✅ (2026-07-02)

- ✅ **Agent 循环核心** (`src/engine/research_agent.py`, ~330行)：Plan → Search → Assess → Synthesize 四阶段
  - 最多 3 轮迭代搜索，每轮 AI 自我评估完整性 (1-10分)
  - 复用 `research_engine` 工具函数（`_build_card_context` / `_verify_citations` / `_enrich_report`）
  - 图谱邻居遍历 (1-2跳) + 去重逻辑
- ✅ **Agent Prompts** (3 个)：`prompts/agent-plan.md` (话题分解) / `prompts/agent-assess.md` (完整性评估) / `prompts/agent-synthesize.md` (多轮合成)
- ✅ **API 集成**：`POST /api/research` 新增 `"agent": true` 参数，默认 false 保持向后兼容
- ✅ **前端**：Research 页面新增 Agent 模式 checkbox + round_log trace 展示
- ✅ **测试**: 253 passed, 0 failures, 0 regressions
- ✅ **已提交**: `9e00f84` (36 files, +1891/-94)

### Codex 前端交付 — 品牌升级 + 收藏系统 + "我的"页面 ✅ (2026-07-02)

- ✅ **品牌重命名**：AI 智能情报平台 → **AI 观察室** (AI Observatory)
  - Dashboard hero 新增 subtitle + description
  - 平台名称全部更新（title/footer/i18n）
- ✅ **全局收藏系统**（localStorage 持久化，key: `ai_observatory_favorites`）：
  - `frontend_components.py`：`favorite_button()` Python 组件
  - `frontend_styles.py`：`favoriteButtonHTML()` / `uiToggleFavorite()` / `uiFavoriteStore()` / `uiSaveFavoriteStore()` / `uiFavoriteKey()` / `uiEscAttr()` JS 工具函数
  - 收藏按钮遍布：Dashboard 文章/实体/报告 + Library 卡片 + 统一 `.favorite-btn` CSS
- ✅ **"我的"页面** (`src/frontend/my_page.py`)：
  - 两栏布局：收藏列表 + 分类/标签/同步状态
  - API 路由：`GET /my` + `FileResponse`
  - localStorage 读取收藏数据，动态渲染列表
  - 账号同步状态卡片（标注 MVP 阶段，待后端接入）
- ✅ **导航重构** (`nav_html()`)：
  - 简化为 5 项：今日 / 专题 / 时间线 / 研究 / 我的
  - `aliases` 机制合并相关页面（today→dashboard/library/graph, topics→library, timeline→events, research→reports）
- ✅ **验证工具** (`tools/verify_frontend.py`，190行)：
  - 4 步验证：生成页面 → 运行测试 → 检查路由 → HTTP 检查
  - 支持 `--skip-tests` `--skip-server` `--port`
  - 自动启动临时 dev server 验证后关闭
- ✅ **Makefile**：`make verify` 一键验证
- ✅ **测试更新**：test_api.py (+5 路由验证) / test_frontend.py (+25) / test_frontend_components.py (+9)
- ✅ **i18n**：新增 20+ 翻译键（收藏/我的页面/品牌文案）

### 本次会话完成 — Research Engine 增强 (P2 #30) ✅

- ✅ **知识图谱深度关联**：`database.py` 新增 `get_entity_neighbors()` (1-2跳邻居遍历) + `get_entity_relation_graph()` (子图关系查询) + `verify_entity_ids()` (批量验证)
- ✅ **引用溯源**：`_verify_citations()` 验证 AI 返回的 card_id/article_id 真实性，剔除幻觉引用，标注 `_hallucinated_*`
- ✅ **关系上下文注入**：prompt 新增 `$ENTITY_RELATIONS` 占位符，注入实体间关系信息
- ✅ **响应丰富化**：`_enrich_report()` 用实际 DB 数据填充 card_connections、timeline、key_findings 引用
- ✅ **研究深度扩展**：deep 模式搜索更多实体 + 2跳邻居遍历
- ✅ **测试**: 249 passed, 0 failures

### 本次会话完成 — Pipeline 健壮性 V2 (P2 #31) ✅

- ✅ **错误恢复**：每个阶段独立的 try/except，非致命错误记录后继续，致命错误保存断点后中止
- ✅ **断点续跑**：`--resume` 从上次中断阶段恢复，`--reset-checkpoint` 清除断点
- ✅ **Checkpoint 系统**：`data/.pipeline_checkpoint.json` 自动保存每阶段完成状态
- ✅ **部分失败降级**：`_failed_articles` 跟踪每阶段失败，汇总报告中展示
- ✅ **增量状态更新**：`update_pipeline_run()` 支持运行中更新 `articles_processed` 和错误信息
- ✅ **页面生成容错**：5 个页面独立 try/except，单个失败不影响其他
- ✅ **测试**: 249 passed, 0 failures

### 本次会话完成 — 项目结构重构 ✅

- ✅ **`src/` 分层重构**：37 文件扁平结构 → 6 个子包
  - `src/engine/` (18 files) — AI引擎+数据处理 (ai_client, database, fetcher, knowledge, ...)
  - `src/frontend/` (14 files) — 页面生成器 (dashboard, library, kg_3d, timeline_renderer, ...)
  - `src/api/` (1 file) — FastAPI 路由 (api.py)
  - `src/interfaces/` (1 file) — 共享层 (i18n.py)
  - `src/plugins/` — 可插拔 Provider 注册表
  - `src/cli/` — CLI 入口占位
  - `src/research.py`, `src/knowledge_graph.py`, `src/timeline.py` — 向后兼容 shim
- ✅ **关键修复**：5 处 `__file__` 路径 + 循环导入 (`utils.py` → `from __future__ import annotations`)
- ✅ **测试**: 249 passed, 0 failures
- ✅ **启动命令更新**: `uv run uvicorn src.api.api:app --reload --port 8765`

### 本次会话完成 — 多源全启用 + GitHub Trending 解析器

- ✅ **RSS 源全启用**：5 个 disabled 源全部启用（MIT TR / Anthropic Eng / Google AI / ArXiv CS.CL / GitHub Trending）
- ✅ **GitHub Trending HTML 解析器**：`src/fetcher.py` 新增 `parse_github_trending()`，BeautifulSoup 解析，15 repos/daily
- ✅ **HTML/RSS 分路抓取**：`fetch_all()` 按 `type: rss|html` 分 client 抓取（不同 Accept headers）
- ✅ **config.yaml**：新增 `type: html` 字段支持非 RSS 源，活跃源 14/16
- ✅ **ROADMAP 同步**：V5.10 新增 + V6.1 标记完成 + V6.2 部分完成 + 指标更新
- ✅ **测试**: 249 passed, 0 failures

### 本次会话完成 — 卡片字段补充 (P2 #5)

- ✅ **卡片字段补充**：11 张 methodology 卡片全部补全 timeline 字段（56 条时间线条目）
  - agent-orchestration / ai-evaluation / context-engineering / guardrails / harness-engineering
  - long-running-agent / memory-architecture / multi-agent-systems / planning / reflection / self-correction
  - 每张 5-6 条 timeline，覆盖从 2018 到 2025-06 的关键历史事件
- ✅ **全部 92 张知识卡片** timeline + significance 字段完整，零缺失
- ✅ **测试**: 249 passed, 0 failures

### 本次会话完成 — 6 项交付：文档同步 + Research + 多源 + T() 修复 + Entity 增强 + Category Nav

- ✅ **文档债务同步**：ROADMAP.md V5.1~V5.9 完整记录 + TASKS.md 优先级重构
- ✅ **Category Navigation**：Library 页新增 sticky 分类标签栏，8 标签可点击 + Scroll Spy + smooth scroll
- ✅ **Research Assistant**：新建 `src/research.py` + `prompts/research.md` + `POST /api/research`
- ✅ **多源扩展 RSS**：config.yaml 新增 Reddit/HN/ArXiv 等 5 个源，总数 11→16
- ✅ **T() 参数化**：`T(key, {n: 5, m: 10})` 统一参数替换，消除 5 处手动 `.replace()` 调用
- ✅ **Entity 详情页增强**：新增 background/known_for/creators 展示 + 关系统计 + 文章时间线视图
- ✅ **测试**: 241 passed (+11) → 249 passed (+8)
  - 搜索实体+文章 → AI 生成结构化报告（概述/核心发现/卡片关联/时间线/进一步阅读）
  - 新建 `prompts/research.md` 提示词模板，支持 standard/deep 两种深度
  - 新增 241 passed (+11: 8 research + 3 RSS config)
- ✅ **多源扩展 RSS + Social**：`config.yaml` 新增 5 个 RSS 源
  - Reddit r/MachineLearning + r/artificial（社区讨论）
  - Hacker News 全部（与 AI 过滤版互补）+ ArXiv CS.CL（计算语言学）
  - 源总数 11 → 16（10 启用 + 4 待启用 + 2 未实现）
- ✅ **文档债务同步**：ROADMAP.md 完整更新 V5.1~V5.9 全部子版本 + 当前基线指标
  - TASKS.md 重新整理优先级，已完成项归档，新增 Category Navigation 记录
- ✅ **测试**: 241 passed, 0 failures (+11: 8 research page/API + 3 RSS config)

### 本次会话完成 — 周报/月报系统完善 (P2 #14) + 新增实体卡片 (P2 #13) + 主题切换 (P2 #7)

- ✅ **主题系统**：`:root` 暗色 + `[data-theme="light"]` 亮色双主题，13 个 CSS Token 全覆盖
- ✅ **主题切换按钮**：`nav_html()` 新增 ☀️/🌙 切换按钮，localStorage 持久化，刷新不丢失
- ✅ **全部 7 个页面 CSS 变量化**：Dashboard / Library / Entity / 2D Graph / 3D Graph / Timeline / Events
- ✅ **共享模块更新**：`frontend_styles.py` 新增 `THEME_VARS` 导出 + `SHARED_JS` 注入主题 JS
- ✅ **测试**: 179 passed, 0 failures
- ✅ **DESIGN_SYSTEM_VERSION**: 5.0.0 → 5.1.0 (MINOR: 新增 THEME_VARS 导出 + 主题切换 JS)

### 本次会话完成 — 周报/月报系统完善 (P2 #14)

- ✅ **Reports 页面**：新建 `src/reports_page.py`，API-driven 报告浏览器
  - 统计卡片（日报/周报/月报数量）、按类型分组列出所有报告
  - 响应式设计 + 共享设计系统 + i18n 中英文
- ✅ **趋势报告增强**：`trend_reporter.py` 注入知识卡片上下文，周报/月报自动存 DB
- ✅ **`index.md` 自动生成**：`_generate_reports_index()` 自动维护报告索引
- ✅ **导航入口**：nav 新增"报告"入口，i18n 中英文
- ✅ **API 端点**：`/api/reports?type=weekly|monthly` 支持周报/月报查询
- ✅ **静态文件挂载**：`/report-files/` 提供 `.md` 文件下载（Dashboard 和 Reports 页面链接已更新）
- ✅ **第一期月报已生成**：`monthly-2026-07.md`
- ✅ **测试**: 179 passed, 0 failures

### 本次会话完成 — 测试覆盖率提升 (P2 #8)

- ✅ **新增 51 项测试**，总计 179 → 230
- ✅ **前端页面测试** (`tests/test_frontend.py`, 19 tests)：所有 8 个页面生成器 HTML 结构验证
  - Dashboard / Library / Entity / Events / Reports / 2D Graph / 3D Graph / Timeline
  - CSS 变量使用检查、响应式 768px 断点验证、i18n 中英文输出
  - 导航完整性、加载指示器、THEME_VARS/RESET_CSS 双主题
- ✅ **边界条件测试** (`tests/test_edge_cases.py`, 18 tests)：
  - 空搜索/超长输入/不存在实体/零结果/负数 limit
  - 空文章去重/相同 URL 去重/多文章保留
  - 余弦相似度边界（相同/正交/零向量）/ 空卡片加载 / 空图谱 / 无日报
- ✅ **i18n 测试**：nav keys 完整性、reports 翻译键、nav_html 包含 Reports
- ✅ **设计系统测试**：版本号格式、TYPE_COLORS/ICONS 8 类型完整
- ✅ **230 passed, 0 failures**

### 本次会话完成 — 新增实体卡片 78→92 (P2 #13)

- ✅ **新增 14 张高质量知识卡片**，实体总数 78 → 92（超 90+ 目标）
- ✅ **Tech 卡片 +5**：PyTorch / CUDA / Vector Database / TensorFlow / JAX（4→9）
- ✅ **Concept 卡片 +3**：AGI / AI Alignment / Hallucination（5→8）
- ✅ **Product 卡片 +5**：Notion AI / Windsurf / Suno / Character.AI / Claude Code CLI（6→11）
- ✅ **Company 卡片 +1**：NVIDIA（11→12）
- ✅ **关系 592 条**（+8 新增），全部 92 张卡片嵌入向量已重建
- ✅ **测试**: 179 passed, 0 failures

### 前期已完成 — P1+P2 全面交付

- ✅ **Pipeline 健壮性**：`pipeline.py`/`collector.py` 接入 `start/finish_pipeline_run` 和 `log_collector_run`，Dashboard 新增健康面板（DB 统计/最后运行/24h 成功率）
- ✅ **前端优化**：CSS 自定义属性 Token 体系（:root 13 个变量）+ 骨架屏 CSS/JS（`SKELETON_CSS` + `skeletonHTML()`）+ 响应式 NAV 滚动优化 + 全部 CSS 片段迁移到变量
- ✅ **卡片策展**：新增 5 张高价值卡片（AI Agent 概念、GPT-4o、Claude 4、Midjourney、Perplexity），实体 74→79，关系 450→495
- ✅ **3D Knowledge Graph**：Three.js + 3d-force-graph，79 节点 495 边，旋转/缩放/类型筛选/悬停高亮，2D/3D 互相切换
- ✅ **测试**: 179 passed, 0 failures

### 上次会话完成 — Events 里程碑页面 (Codex 交付)

- ✅ **Events 页面**：`src/events_page.py` (129行) — API-driven 里程碑事件页面
  - 时间线布局（CSS 中线 + 左右交替卡片）
  - 搜索 + 年份筛选 + 展开详情（含 significance/background/关联实体）
  - 响应式 3 断点 (480/768/1024px)，中英文切换完整
  - 导航入口已加（`nav_html()` 新增 events 标签）
  - API: `GET /api/entities?type=event` 驱动数据
- ✅ **测试**: 179 passed, 0 failures
- ⚠️ **已知**: API 当前无 `background` 字段，页面显示"暂无背景资料"（已兼容未来字段）

### 上次会话完成 — V5.2 卡片质量提升 + Codex 协作建立

- ✅ **清理 155 张空壳草稿卡**：全部删除（Concept Miner 占位符，无实质内容）
- ✅ **重置 candidate_concepts.json**：清除候选条目
- ✅ **修复概念卡 timeline 字段**：LoRA / MoE / RAG 的 `evolution` → `timeline`（标准化）
- ✅ **新增 8 张 event 卡片**：alphago-lee-sedol / transformer-paper / gpt-3-release / chatgpt-launch / gpt-4-release / deepseek-r1-release / claude-fable-5-release / sora-announcement / gemini-launch / openai-devday-2023
- ✅ **新增 2 张 product 卡片**：Cursor / Claude.ai
- ✅ **Codex 协作体系建立**：创建 `CODEX_HANDOFF_Codex协作说明.md` — 前端边界/约束/验收标准；修正 `i18n_js()`/`nav_html()` 签名
- ✅ **V5.2.2 字段完整性**：6 张 methodology 卡补 `release_date` + `background` + `evolution→timeline`（chain-of-thought/tool-use/prompt-engineering/fine-tuning/constitutional-ai/model-distillation）
- 🔄 **P2 #5 Pipeline 健壮性（已完成）**：`pipeline_runs` + `collector_runs` 表已建，`get_health()` 函数已添加，`pipeline.py` 和 `collector.py` 已接入追踪，Dashboard 健康面板已上线 ✅

### 上次会话完成（FOCUS Mode）

- ✅ **RAG 混合检索（ROADMAP V5.1）**：完整实现语义搜索层
  - 新建 `src/embeddings.py` (~340行) — 核心模块：语义搜索、混合检索、卡片语义匹配、嵌入向量存储
  - **可插拔 Embedding Provider 注册表** (`ai_client.py`): `siliconflow` / `openai` / `kimi` / `local`，新增 Provider 一行注册零改动
  - 默认使用 **SiliconFlow BAAI/bge-large-zh-v1.5**（1024维，免费），Kimi Embedding API 不可用(403)
  - SQLite 新增 `embeddings` 表 (id, dims, vector, updated_at)
  - API: `GET /api/search?semantic=true` + `POST /api/embeddings/rebuild` + `GET /api/embeddings/status`
  - `match_cards()` 升级：优先语义匹配，嵌入表空时自动 fallback Jaccard
  - Library 前端搜索改为 300ms 防抖 `/api/search?semantic=true`，降级客户端过滤
  - **62 张卡片嵌入全部构建完成**，语义搜索验证通过（"AI agent 编程" → Agent Orchestration/Harness Engineering/Planning）
- ✅ **测试**: 179 passed (基线147 + 新增32)，零破坏
- ✅ **桌面文件归类**: 10张 AI News 截图 → `ai-news/screenshots/`；cover.png + build_cover.py → `40_Experiments/xianyu-cover/`；exp_step 图片已不存在
- ✅ **AI News 日报**: 2026-07-01 已生成 (267篇, ★5:1 ★4:32 ★3:79)

### 前期已完成（上次会话）

### 前期已完成（上次会话）

- ✅ **大文件拆分**：`knowledge_graph.py`(518行) → `kg_data.py`(167) + `kg_mermaid.py`(147) + `kg_d3.py`(212)；`timeline.py`(339行) → `timeline_data.py`(291) + `timeline_renderer.py`(70)。原始模块保留为 re-export shim，pipeline.py 零改动。所有文件 <300 行。
- ✅ **API 超时设置**：`ai_client.py` OpenAI 客户端新增 `timeout=120.0`，防止 API 调用无限挂起。
- ✅ **Workspace 清理**：删除 dashboard-snap/snapshot 调试文件；合并 Decision Log 到 `80_Logs/Decisions/`；迁移 Toolchain/Prompt Rules 到正确位置；00_Global 文件名去空格。

- ✅ **卡片同步**：修复 9 张损坏 YAML，`sync_cards.py` 将磁盘卡片 + 关系同步到 SQLite
- ✅ **中英文切换**：新建 `src/i18n.py`（100+ 翻译条目），5 个页面全部支持即时切换
- ✅ **技术术语规则**：中文模式下实体名保留英文原文，类型标签使用 "Model（模型）" 双语格式
- ✅ V1.8: 中文版界面 + AI 后端简化为 DeepSeek + Kimi
- ✅ 日报生成 + 周报/月报 + Dashboard 集成
- ✅ 61 张知识卡片（7 种类型）+ SQLite + FastAPI + Knowledge Graph + Timeline v2 + Concept Miner
- ✅ 147 项测试全部通过

### 新增文件

| 文件 | 作用 |
|------|------|
| `src/embeddings.py` | **RAG 核心** — 语义搜索、混合检索、卡片语义匹配、嵌入向量存储(SQLite) |
| `src/frontend_styles.py` | 共享设计系统 — TYPE_COLORS/ICONS/EDGE_COLORS + 共享CSS(动画/响应式/错误) + JS工具(apiFetch/showError) |
| `src/i18n.py` | 翻译模块 — I18N 字典 + TYPE_LABELS + `i18n_js()` + `nav_html()` |
| `src/sync_cards.py` | YAML → SQLite 卡片/关系同步 + 同步后自动重建嵌入 |
| `src/kg_data.py` | 知识图谱数据层 — TYPE_COLORS + build_graph + _compute_stats |
| `src/kg_mermaid.py` | Mermaid 图谱导出 — to_mermaid + generate_mermaid_report |
| `src/kg_d3.py` | D3.js 交互式图谱 HTML 生成 — generate_html |
| `src/timeline_data.py` | Timeline 常量与模板 — CSS_TEMPLATE + JS_TEMPLATE |
| `src/timeline_renderer.py` | Timeline 页面组装 — generate_timeline |
| `src/engine/research_engine.py` | **Research Engine V2** — 图谱邻居遍历 + 引用溯源 + 关系注入 + 响应丰富化 |
| `pipeline.py` | **Pipeline V2** — 错误恢复 + 断点续跑 + checkpoint 系统 + 部分失败降级 |
| `src/research.py` | **Research Assistant** — 深度研究页面生成 + API 后端（搜索→AI分析→结构化报告） |
| `prompts/research.md` | **Research 提示词模板** — 研究分析维度与输出格式定义 |
| `CODEX_HANDOFF_Codex协作说明.md` | **Codex 前端协作** — 职责边界/架构约束/验收标准/API 文档 |
| `src/reports_page.py` | **Reports 页面** — API-driven 报告浏览器（统计+分组列表+响应式+i18n） |
| `tests/test_embeddings.py` | **RAG 测试** — 26 tests: cosine/存储/重建/混合搜索/语义匹配 |
| `src/frontend/my_page.py` | **"我的"页面** — 收藏列表 + 分类/标签/同步状态，localStorage 驱动 |
| `tools/verify_frontend.py` | **一键验证工具** — 生成页面 → 测试 → 路由 → HTTP 检查，4 步验证 |
| `CODEX.md` | **Codex 指针文件** — 路由 Codex 到 HANDOFF/Context/Session Rules |
| `PROJECT_CONTEXT.md` | **项目短版上下文** — 产品宪法 + 设计约束 |
| `Makefile` | `make verify` — 前端验证入口 |
| `src/engine/research_agent.py` | **Research Agent** — Plan→Search→Assess→Synthesize 迭代循环 |
| `prompts/agent-plan.md` | Agent Plan 阶段 prompt — 话题分解为子问题 |
| `prompts/agent-assess.md` | Agent Assess 阶段 prompt — 完整性自评 (1-10分) |
| `prompts/agent-synthesize.md` | Agent Synthesize 阶段 prompt — 多轮结果合成 |
| `src/engine/concept_agent.py` | **Concept Agent** — Semantic Lookup → AI Decide → Execute 决策闭环 |
| `prompts/concept-decide.md` | Concept Decide prompt — NEW/MERGE/SKIP/DRAFT 策展决策 |

### Codex 本次重写文件

| 文件 | 变更 |
|------|------|
| `src/frontend/frontend_components.py` | 新增 `favorite_button()` Python 组件 + `.ui-favorite` CSS |
| `src/frontend/frontend_styles.py` | 新增收藏 JS 工具函数（`favoriteButtonHTML`/`uiToggleFavorite`/`uiFavoriteStore` 等）+ `.favorite-btn` CSS |
| `src/frontend/frontend_interactions.py` | 追加空行（格式修复） |
| `src/frontend/dashboard.py` | Hero 重设计（subtitle+desc）+ 收藏按钮全覆盖（文章/实体/报告）+ 导航更新 + 480px 响应式 |
| `src/frontend/library.py` | 卡片头部收藏按钮 + 导航更新 |
| `src/interfaces/i18n.py` | 品牌文案更新 + 收藏/我的页面 20+ 翻译键 + 导航重构（5项+aliases） |
| `src/api/api.py` | 新增 `GET /my` 路由 |

### 重写文件（历史）

| 文件 | 变更 |
|------|------|
| `src/ai_client.py` | **Embedding Provider 注册表**（可插拔：siliconflow/openai/kimi/local）+ `embed_texts()` |
| `src/database.py` | 新增 `embeddings` 表 + `search()` 支持 `semantic` 参数 |
| `src/api.py` | 新增 3 个端点：`/api/search?semantic=true` + `/api/embeddings/rebuild` + `/api/embeddings/status` |
| `src/knowledge.py` | `match_cards()` 新增 `use_semantic` 参数，优先语义匹配 fallback Jaccard |
| `src/sync_cards.py` | 同步后自动调用 `rebuild_card_embeddings()` |
| `pipeline.py` | 启用 `match_cards(use_semantic=True)` |
| `src/library.py` | 前端搜索框 300ms 防抖调用语义搜索 API，降级客户端过滤 |
| `src/trend_reporter.py` | 新增知识卡片上下文注入 + DB 存储 + index.md 自动生成 |
| `src/reports_page.py` | 新建 — Reports 页面生成器 |
| `src/i18n.py` | 新增 reports 导航/页面翻译键 + nav 增加 Reports 入口 |
| `src/api.py` | 新增 `/reports` 页面路由 + static mount 改为 `/report-files/` |
| `pipeline.py` | 新增 `generate_reports_page()` 调用 |
| `src/dashboard.py` | 报告文件链接从 `/reports/` 迁移到 `/report-files/` |
| `config.yaml` | 新增 `embeddings` 配置节 (provider: siliconflow, alpha: 0.3) |
| `src/dashboard.py` | 共享设计系统 + 动画(淡入/hover) + 响应式 + 错误处理 |
| `src/library.py` | 共享设计系统 + 动画 + 响应式 + 错误处理 + TYPE_COLORS去重 |
| `src/entity_page.py` | Entity 详情页增强 — 两栏布局 + background/known_for + 关系统计 + 文章时间线 |
| `src/i18n.py` | T() 参数化 + research/entity 翻译键 + nav 新增研究入口 |
| `config.yaml` | 新增 5 个 RSS 源（Reddit/HN/ArXiv） |
| `ROADMAP_项目路线图.md` | V5.1~V5.9 完整记录，基线指标更新 |
| `../TASKS.md` | 优先级重构，已完成项归档 |
| `src/kg_d3.py` | 共享设计系统 + 动画 + 响应式侧边栏 + 错误处理 + EDGE_COLORS去重 |
| `src/timeline_data.py` | 共享设计系统 + 动画 + 响应式 + 错误处理 + TYPE_COLORS/ICONS去重 |
| `src/timeline_renderer.py` | 导入共享 TYPE_COLORS/TYPE_ICONS |
| `src/i18n.py` | 新增 6 个错误/重试翻译键 |
| `src/knowledge_graph.py` | 拆分为 kg_data/kg_mermaid/kg_d3，本文件变为 re-export shim |
| `src/timeline.py` | 拆分为 timeline_data/timeline_renderer，本文件变为 re-export shim |
| `src/ai_client.py` | OpenAI 客户端增加 `timeout=120.0` |

### 当前数据

| 指标 | 数值 |
|------|------|
| 文章 | 283 篇 |
| 实体 | 92 张（company:12, model:15, tech:9, concept:8, product:11, person:10, methodology:17, event:10） |
| 嵌入向量 | 92 个（SiliconFlow BGE 1024维，全部就绪） |
| 关系 | 592 条 |
| RSS 源 | 16 个（10 启用 + 6 待启用/未实现） |
| 报告 | 日报×5 + 周报×1 + 月报×1 |
| 页面 | 9 个 (Today / Topics / Entity / 2D Graph / 3D Graph / Timeline / Research / My / Reports 已合并到 Research 导航) |
| 测试 | 265 passed, 0 failures |
| 超300行文件 | 0（全部已拆分） |
| 卡片完整性 | 全部 61 张策展卡字段完整（0 缺失） |

### 当前问题

- 📋 **收藏系统为前端 MVP**：localStorage 存储，无账号同步。账号体系待后端接入后启用
- ✅ **全部改动已提交**：`9e00f84` (2026-07-02)，36 files, +1891/-94
- ✅ **V5.2 卡片质量提升完成**（2026-07-01）：155 张空壳删除；candidate_concepts.json 重置

## 下一步（详见 ROADMAP_项目路线图.md）

| # | 任务 | 优先级 | 进度 |
|---|------|--------|------|
| 1 | **Agent Loop 复用到 trend_reporter** — 迭代趋势搜索 + 自评 | 🔵 | 📋 下一项 |
| 2 | 更多卡片策展 + 关系补充 | 🔵 | 📋 持续 |
| 3 | GitHub Actions CI + 自动测试 | 🔵 | 📋 待规划 |
| 4 | 收藏系统账号同步 — localStorage MVP → 后端接入 | 🔵 | 📋 远期 |
| 5 | 前端体验打磨 (Codex) — Research 视觉优化 + 移动端响应式 | 🔵 | 📋 远期 |

**已全部完成的核心功能**：RAG混合检索 ✅ / 卡片质量 ✅ / Pipeline健壮性V2 ✅ / 3D Graph ✅ / 实体卡片92 ✅ / 周报月报 ✅ / 测试249 ✅ / Research Engine V2 ✅ / 多源16个 ✅ / Category Nav ✅ / 项目结构重构 ✅ / GitHub开源 ✅

## 注意事项

- Knowledge Card 是唯一写入点（SSOT），所有模块只读 Card
- importance（人工策展）≠ score（AI 实时打分）
- Timeline 不存数据，只是 Card 的时间视图
- 新增 type 时：先写 5 张卡验证，再回来补 Schema
- tags 不嵌套，平铺
- SQLite WAL 模式，外键约束
- 页面均为 API-driven HTML shell，数据动态获取
- API 启动: `uv run uvicorn src.api.api:app --reload --port 8765`
- Context Budget Rule: 一个 Conversation 一个 Feature；所有文件已 <300 行
- i18n: `nav_html(path)` 生成导航 + 语言切换按钮；`T("key")` / `TLbl(type)` JS 函数用于运行时翻译
- 卡片同步: `uv run python -m src.sync_cards` (仅人工策展) 或 `--include-drafts` (含草稿)
- 技术术语：中文模式下类型标签双语（"Model（模型）"），实体名始终保持英文原文
- AI 客户端: 120s 超时 + 3 次指数退避重试（1.5s/3s/6s）
- **前端设计系统**: 新增页面请从 `frontend_styles.py` 导入 TYPE_COLORS/共享CSS片段，不要硬编码样式
- **错误处理**: 所有 fetch 调用使用 `apiFetch(url)` 包装，页面初始化包裹 try/catch
- **响应式**: 3 断点 480/768/1024px，所有页面继承基础断点，特殊页面可追加
- **语义搜索**: 62 张卡片已嵌入，`match_cards(use_semantic=True)` 自动优先语义匹配。嵌入表空时自动 fallback Jaccard
- **Embedding Provider**: 可插拔注册表 `ai_client.EMBEDDING_PROVIDERS`，当前 `siliconflow`。切换: `.env` 中设 `EMBEDDING_PROVIDER=openai|kimi|local`
- **重建嵌入**: 卡片内容变更后执行 `POST /api/embeddings/rebuild?force=true` 或重新 `sync_cards`
- **Claude-Codex 协作协议**: 遵循 `CODEX_HANDOFF_Codex协作说明.md` 的三层机制（Layer A: 版本号 / Layer B: Session State / Layer C: Changelog）。每次前端变更后执行 Handoff Ritual：bump DESIGN_SYSTEM_VERSION → 更新 §3 会话状态 → 追 §11 变更日志
