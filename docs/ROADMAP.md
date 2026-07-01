# ROADMAP.md — AI Intelligence Platform

> 迭代路线图。记录每个版本的完成内容、当前状态和未来方向。

---

## V1: MVP — 跑通日报管道

**时间**: 2026-06-27  
**状态**: ✅ 完成

### 目标

端到端跑通：RSS 抓取 → AI 处理 → Markdown 日报。

### 完成内容

- [x] RSS 抓取 (feedparser, 8 个源)
- [x] 去重 (URL 精确 + 标题 Jaccard 相似度)
- [x] AI 分类 (批量 20-30 篇, 15 个分类标签)
- [x] AI 摘要 (英文 → 中文标题 + 一句话 + 三点)
- [x] AI 评分 (1-5 星 + 理由, 注入用户兴趣)
- [x] Markdown 日报生成 (星级分组 + 目录)
- [x] config.yaml 配置驱动
- [x] Prompt 外置 (prompts/*.md)
- [x] 15 项测试

### 架构决策

- Python 3.11+ / feedparser / Anthropic SDK
- 线性管道，无状态
- JSON 文件存储 (无数据库)

---

## V2: 知识化 — Cards + 调度 + 周报月报

**时间**: 2026-06-28  
**状态**: ✅ 完成

### 目标

从"日报机器"升级为"知识系统"——卡片化、可调度、可回顾。

### 完成内容

- [x] Knowledge Card Schema v1.0 (YAML 格式规范)
- [x] 20 张知识卡片 (5 models, 3 companies, 4 tech, 4 concepts, 3 products, 1 person)
- [x] Jaccard 匹配算法 (文章 ↔ 卡片)
- [x] 历史上下文注入摘要
- [x] Collector 独立拆分 (每小时抓取 → inbox.jsonl)
- [x] Pipeline inbox 模式 (从 inbox 读取)
- [x] 周报系统 (`--weekly`, 汇总 7 天日报, AI 趋势分析)
- [x] 月报系统 (`--monthly`, 汇总 30 天日报)
- [x] Windows Task Scheduler (4 个定时任务)
- [x] 50+ 项测试

### 新增文件

```
src/trend_reporter.py     # 趋势报告 (周报/月报)
src/knowledge.py           # 卡片加载/匹配/上下文
prompts/trend.md           # 趋势分析 prompt
run-collector.bat          # 每小时调度脚本
run-daily.bat / run-weekly.bat / run-monthly.bat
```

---

## V3: 平台化 — SQLite + Web + Graph

**时间**: 2026-06-28 ~ 2026-06-29  
**状态**: ✅ 完成

### 目标

从"命令行工具"升级为"Web 平台"——有数据库、有 API、有可视化。

### 完成内容

- [x] SQLite 统一数据层 (4 表, WAL, FK)
- [x] FastAPI 服务 (8 API + 3 页面路由)
- [x] Dashboard 页面 (API-driven, 实时数据)
- [x] Library 页面 (知识资产库)
- [x] Knowledge Graph (Mermaid + D3.js 双输出)
- [x] 28 张卡片 (新增 8 张 methodology 类型)
- [x] 卡片同步到 SQLite entities 表
- [x] 文章同步到 SQLite articles 表
- [x] 报告同步到 SQLite reports 表
- [x] Concept Miner (候选池 + 准入规则)
- [x] Hook 审批系统 (弹窗 + Telegram 双通道)
- [x] 87 项测试

### 新增文件

```
src/api.py                 # FastAPI 服务
src/database.py            # SQLite 数据层
src/dashboard.py           # Dashboard HTML 生成
src/library.py             # Library HTML 生成
src/knowledge_graph.py     # 知识图谱生成
src/concept_miner.py       # 概念发现器
src/ai_client.py           # 多后端 AI 客户端
```

### 架构转变

```
之前: JSON files → Markdown 日报
之后: JSON files → SQLite → FastAPI → Web UI
```

---

## V4: 完善 — Timeline + 测试 + 文档

**时间**: 2026-06-29  
**状态**: ✅ 完成

### 目标

补齐缺口——时间线可视化、测试覆盖翻倍、文档体系建立。

### 完成内容

- [x] Timeline 页面 (按时间排列 20 个有日期的实体, 1985-2026)
- [x] 年份分布柱状图
- [x] 类型筛选 (7 种类型切换)
- [x] Database 测试 39 项 (CRUD, 搜索, 统计, 边界)
- [x] API 测试 21 项 (所有端点 + 页面路由)
- [x] API Bug 修复 (404 返回 HTTPException + lifespan 替代 on_event)
- [x] 全页面导航交叉链接
- [x] README.md 重写
- [x] PRODUCT_GUIDE.md (产品说明书)
- [x] ARCHITECTURE.md (系统架构文档)
- [x] ROADMAP.md (本文档)
- [x] HANDOVER.md 更新 (反映 28 卡片 + 147 测试 + 完整架构)

### 当前指标

```
测试:      147 passed
卡片:      28 张 (7 types)
文章:      280 条
关系:      128 条
页面:      4 个 (Dashboard / Library / Graph / Timeline)
API:       8 个端点
调度:      4 个定时任务
```

---

## V5: 智能增强

**时间**: 2026-07  
**状态**: ✅ 完成

### V5.1 RAG 混合检索

**优先级**: 🟢 高  
**完成日期**: 2026-07-01

- [x] 卡片 + 文章 embedding → SiliconFlow BAAI/bge-large-zh-v1.5 (1024维, 免费)
- [x] 向量存储 → SQLite `embeddings` 表 (JSON array, 零新依赖)
- [x] 语义搜索 `/api/search?q=...&semantic=true` + 混合检索 (keyword + semantic 加权融合)
- [x] 卡片匹配从 Jaccard 升级为语义相似度 (优先语义, 自动 fallback)
- [x] 可插拔 Embedding Provider 注册表 (siliconflow/openai/kimi/local)
- [x] 92 张卡片嵌入全部构建完成
- [x] `src/embeddings.py` (~340行) + `tests/test_embeddings.py` (26 tests)
- [x] 新增 API: `POST /api/embeddings/rebuild` + `GET /api/embeddings/status`
- [x] 前端 Library 搜索 300ms 防抖 → 语义搜索 API

### V5.2 卡片质量提升

**优先级**: 🟡 中  
**完成日期**: 2026-07-01

- [x] 清理 155 张空壳草稿卡，归档至 `data/archive/draft-cards-2026-06-30/`
- [x] 补充缺失的 timeline/significance/background 字段（6 张 methodology 卡）
- [x] 修复 concept 卡 evolution→timeline 字段标准化（LoRA/MoE/RAG）
- [x] 新增 10 张 event 卡片 (AlphaGo-Lee-Sedol, Transformer Paper, GPT-3/4 Release, ChatGPT Launch, DeepSeek R1, Claude Fable 5, Sora, Gemini, OpenAI DevDay 2023)
- [x] 重置 candidate_concepts.json（清除 294 条目）

### V5.3 Events 里程碑页面 (Codex 交付)

**优先级**: 🟡 中  
**完成日期**: 2026-07-01

- [x] `src/events_page.py` (129行) — API-driven 里程碑事件页面
- [x] 时间线布局（CSS 中线 + 左右交替卡片）
- [x] 搜索 + 年份筛选 + 展开详情（含 significance/background/关联实体）
- [x] 响应式 3 断点 (480/768/1024px)，中英文切换完整
- [x] API: `GET /api/entities?type=event` 驱动数据
- [x] 导航入口已加（`nav_html()` 新增 events 标签）

### V5.4 Pipeline 健壮性 + 前端优化

**优先级**: 🟡 中  
**完成日期**: 2026-07-01

- [x] `pipeline_runs` + `collector_runs` 表，完整追踪每次运行
- [x] Dashboard 健康面板（DB 统计/最后运行/24h 成功率）
- [x] `pipeline.py`/`collector.py` 接入 `start/finish_pipeline_run` 和 `log_collector_run`
- [x] CSS 自定义属性 Token 体系（:root 13 个变量）
- [x] 骨架屏 CSS/JS（`SKELETON_CSS` + `skeletonHTML()`）
- [x] 响应式 NAV 滚动优化
- [x] 共享设计系统 `frontend_styles.py`（TYPE_COLORS/ICONS/动画/响应式/错误处理）
- [x] 全部 7 个页面 CSS 变量化

### V5.5 Reports 页面 + 周报/月报系统完善

**优先级**: 🟡 中  
**完成日期**: 2026-07-01

- [x] `src/reports_page.py` — API-driven 报告浏览器（统计卡片 + 按类型分组 + 响应式 + i18n）
- [x] 趋势报告增强：`trend_reporter.py` 注入知识卡片上下文，周报/月报自动存 DB
- [x] `index.md` 自动生成：`_generate_reports_index()` 自动维护报告索引
- [x] API: `/api/reports?type=weekly|monthly` + `/report-files/` 静态文件挂载
- [x] 导航入口：nav 新增"报告"入口
- [x] 第一期月报已生成：`monthly-2026-07.md`

### V5.6 3D Knowledge Graph

**优先级**: 🔵 低  
**完成日期**: 2026-07-01

- [x] Three.js + 3d-force-graph，79 节点 495 边
- [x] 节点颜色/大小按 type/importance 区分
- [x] 旋转/缩放/类型筛选/悬停高亮
- [x] 与 2D Graph 共存（切换按钮）

### V5.7 新增实体卡片 + 测试覆盖率

**优先级**: 🟡 中  
**完成日期**: 2026-07-01

- [x] 新增 14 张高质量知识卡片：Tech +5 (PyTorch/CUDA/Vector DB/TensorFlow/JAX), Concept +3 (AGI/Alignment/Hallucination), Product +5 (Notion AI/Windsurf/Suno/Character.AI/Claude Code CLI), Company +1 (NVIDIA)
- [x] 实体总数 78 → 92，关系 495 → 592
- [x] 测试：179 → 230 (+51：19 frontend + 18 edge cases + 14 others)
- [x] 前端页面测试 (19 tests)：所有 7 页面 HTML 结构/CSS 变量/响应式/i18n
- [x] 边界条件测试 (18 tests)：空搜索/超长输入/不存在实体/零结果/去重/余弦相似度/空图谱

### V5.8 主题切换

**优先级**: 🔵 低  
**完成日期**: 2026-07-01

- [x] `:root` 暗色 + `[data-theme="light"]` 亮色双主题，13 个 CSS Token 全覆盖
- [x] 主题切换按钮：`nav_html()` 新增 ☀️/🌙 切换，localStorage 持久化
- [x] 全部 7 个页面 CSS 变量化，刷新不丢失
- [x] `frontend_styles.py` 新增 `THEME_VARS` 导出 + `SHARED_JS` 注入主题 JS
- [x] DESIGN_SYSTEM_VERSION: 5.0.0 → 5.1.0

### V5.9 Category Navigation（分类导航）

**优先级**: 🟡 中  
**完成日期**: 2026-07-01

- [x] 顶部分类标签可点击，平滑滚动到对应分类区域
- [x] Scroll Spy：滚动时自动高亮当前分类标签（IntersectionObserver）
- [x] Sticky 吸顶导航（`position: sticky; top: 0`）
- [x] 即时高亮反馈：点击标签立即添加 `.active`，不等滚动完成
- [x] 分类数量保留显示（如 "Methodology 17"）
- [x] 8 个分类按 TYPE_ORDER 排序，保持颜色区分

---

## V5.10: 卡片字段完整性 + 多源全启用（本次会话）

**时间**: 2026-07-01  
**状态**: ✅ 完成

### 卡片字段补充
- [x] 11 张 methodology 卡片补充 timeline（56 条历史事件条目）
- [x] 全部 92 张卡片 timeline + significance 字段完整

### RSS 源全启用
- [x] 启用 5 个之前 disabled 的源：MIT Tech Review / Anthropic Eng / Google AI Blog / ArXiv CS.CL / GitHub Trending
- [x] GitHub Trending HTML 解析器（BeautifulSoup）：15 repos/daily 自动转为 Article
- [x] `config.yaml` 新增 `type: html` 支持非 RSS 源
- [x] `src/fetcher.py` 新增 `parse_github_trending()` + HTML/RSS 分路抓取
- [x] 活跃源：14/16（仅 2 个 disabled）

---

## V6: Agent 生态 (远期)

**时间**: 2026-07+  
**状态**: 🔵 远期（V6.1+V6.2 部分已完成）

### V6.1 Research Assistant ✅

- [x] 基于知识库的深度研究模式
- [x] 给定一个话题, 自动收集文章 → 匹配卡片 → 生成研究报告
- [x] 引用溯源 (每条结论关联到原文 + 卡片)
- [x] `src/research.py` + `prompts/research.md` + `POST /api/research`
- [x] standard/deep 两种深度模式

### V6.2 多源扩展 (部分完成)

- [x] Reddit r/MachineLearning + r/artificial ✅
- [x] Hacker News 全部 + ArXiv CS.CL ✅
- [x] GitHub Trending Python (HTML 解析) ✅
- [ ] X/Twitter 监控 (v2 API)
- [ ] 微信公众号 (RSS 桥接)

### V6.3 推送（暂缓）

- [ ] Telegram Bot 推送日报链接 ⚫ 暂不实施
- [ ] 高星文章即时推送 (score ≥ 5)
- [ ] 每日/每周摘要推送

### V6.4 移动端体验优化（暂缓）

- [ ] 验证 3 断点 (480/768/1024px) ⚫ 暂不实施
- [ ] 优化触屏交互（卡片展开、图谱拖拽）
- [ ] 离线 PWA 支持

### V6.5 多用户

- [ ] 用户表 + 认证
- [ ] 个性化兴趣配置
- [ ] 阅读历史 + 反馈闭环

---

## 版本总览

```
V1 (06-27)  MVP          ████████ 日报管道跑通
V2 (06-28)  知识化        ████████ Cards + 调度 + 周报月报
V3 (06-28)  平台化        ████████ SQLite + Web + Graph + Concept Miner
V4 (06-29)  完善          ████████ Timeline + 147 tests + 文档体系
V5 (07-01)  智能增强      ████████ 9 个子版本全部交付 ✅ (V5.10 卡片完整性+多源全启用)
V6 (07-xx+) Agent 生态    ░░░░░░░░ Research ✅ / 多源 部分 / 推送+移动端 暂缓
```

---

## 当前指标（2026-07-01）

| 指标 | 数值 |
|------|------|
| 文章 | 283 篇 |
| 实体 | 92 张（company:12, model:15, tech:9, concept:8, product:11, person:10, methodology:17, event:10） |
| 嵌入向量 | 92 个（SiliconFlow BGE 1024维） |
| 关系 | 592 条 |
| RSS 源 | 16 个（14 启用 + 2 禁用） |
| 报告 | 日报×5 + 周报×1 + 月报×1 |
| 页面 | 8 个 (Dashboard / Library / Entity / 2D Graph / 3D Graph / Timeline / Events / Reports / Research) |
| 测试 | 249 passed, 0 failures |
| 卡片字段完整性 | 92/92 timeline + significance ✅ |

---

## 优先级矩阵

```
高影响 / 低成本  → 先做
├── ✅ Entity 详情页增强
├── ✅ T() 占位符修复
├── ✅ Research Assistant
├── ✅ 多源扩展 (HN/Reddit/ArXiv/GitHub/Google/MIT)
├── ✅ 卡片字段完整性 (timeline 补全)
├── ⚫ Telegram Bot 推送 (暂缓)
├── ⚫ 移动端体验优化 (暂缓)
└── 🔵 多用户 (远期)
```

---

## 相关文档

| 文档 | 内容 |
|------|------|
| `ARCHITECTURE.md` | 系统架构、数据层、API、Pipeline、Concept Miner |
| `HANDOVER.md` | 项目交接、关键文件、架构约束、当前问题 |
| `PRODUCT_GUIDE.md` | 给不懂技术的人看的产品说明书 |
| `OPENSPEC.md` | 原始设计决策 (2026-06-27) |
| `../TASKS.md` | 当前任务清单 |
