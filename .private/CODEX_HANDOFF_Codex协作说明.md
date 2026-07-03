# Codex 前端协作说明书

> **写给 Codex**：这是你在本项目的工作边界、技术约束和验收标准。
> Claude 负责后端/数据层，你负责前端 HTML/CSS/JS。
> 
> **启动流程**（每次会话必读）：
> 1. 读 §3 会话状态 → 了解当前进度和待做任务
> 2. 读 §11 变更日志 → 知道上次会话改了什么
> 3. 对比 `src/frontend_styles.py` 中的 `DESIGN_SYSTEM_VERSION` → 决定是否重新读设计系统

---

## 1. 项目是什么

AI Intelligence Platform — 每天从 RSS 自动抓取 AI 资讯，AI 处理后生成中文日报，积累知识卡片构建知识图谱。

- **后端**: Python FastAPI，端口 8765
- **前端**: 纯 HTML + Vanilla JS + 内联 CSS（无框架）
- **数据库**: SQLite

---

## 2. 你的职责范围

### ✅ 你负责
- 生成**单个独立的 HTML 页面**（每个页面是一个自包含文件）
- CSS 样式、动画、响应式布局
- JavaScript 数据获取和交互逻辑
- 页面视觉一致性

### ❌ 你不负责
- 后端 API 逻辑（Claude 负责）
- 数据库 schema
- Pipeline / Collector 等数据管道
- Python 模块（除了前端生成器）

### 📍 边界线 = `/api/*` 
你通过 fetch API 获取数据，不改 API 实现。

---

## 3. 会话状态（每次必读）

> Claude 每次前端变更后更新此节。Codex 启动时先读这里。

### 当前页面状态

| 页面 | 文件 | 状态 | 备注 |
|------|------|------|------|
| Today（原 Dashboard） | `src/frontend/dashboard.py` | ✅ V7.2.1 标杆 | 聚焦报告中心、6 条头条预览与 3 条最近报告；移除知识库和运维模块 |
| Article Detail | `src/frontend/article_page.py` | ✅ V7 标杆 | 杂志式标题、证据轨道、无卡片阅读区与可信度侧栏 |
| Topics（原 Library） | `src/frontend/library.py` | ✅ V7.2.2 | 编辑型分类列表；每类默认 4 项，支持展开/收起与完整搜索结果 |
| Graph (2D) | `src/frontend/kg_d3.py` | ✅ 完成 | D3.js 力导向图 |
| Graph (3D) | `src/frontend/kg_3d.py` | ✅ 完成 | Three.js + 3d-force-graph |
| Timeline | `src/frontend/timeline_renderer.py` | ✅ 完成 | 年份分布 + 类型筛选 |
| Entity Detail | `src/frontend/entity_page.py` | ✅ 完成 | 关联文章/相似实体/卡片元数据 |
| Events | `src/frontend/events_page.py` | ✅ 完成 | 时间线布局 + 搜索/年份筛选 |
| Research | `src/frontend/research_page.py` | ✅ 完成 | 深度研究助手 + Reports 导航合并 |
| **My（🆕）** | `src/frontend/my_page.py` | ✅ 完成 | 收藏列表 + 分类/标签 + 同步状态 |

**全部 9 页面 ✅ 完成。导航简化为 5 项：今日 / 专题 / 时间线 / 研究 / 我的。**

### 设计系统

| 项 | 值 |
|----|-----|
| 当前版本 | `DESIGN_SYSTEM_VERSION = "7.2.3"` in `frontend_styles.py` |
| 上次变更 | 2026-07-03 — v7.2.3: Reports 编辑型归档列表与紧凑统计 |
| 项目状态 | 9 页面全部完成 ✅ / 249 tests / 123 卡片 / 14 活跃 RSS 源 |
| 主题系统 | `:root` 暗色 + `[data-theme="light"]` 亮色，localStorage 持久化，9 页面全覆盖 |
| CSS Token | 13 个变量 + `.favorite-btn` / `.ui-favorite` 收藏组件 |
| 品牌名称 | **AI 观察室** (AI Observatory) |

### 已知问题

| 问题 | 影响 | 状态 |
|------|------|------|
| 收藏系统当前为 localStorage MVP，无账号同步 | My 页面 | 📋 待后端账号体系 |
| Research 页面为初版，视觉风格与成熟页面有差距 | Research | 📋 待优化 |
| 移动端（<480px）部分页面 nav 换行拥挤 | 全部 | 📋 待优化 |
| Codex 改动未 commit | 全部 | ✅ 已提交 (2026-07-03) |

### 当前分配给 Codex 的任务

| # | 任务 | 优先级 | 预估 |
|---|------|--------|------|
| 1 | **V7 全站推广** — 将首页/文章标杆的编辑型排版推广到 Topics、Timeline、Reports、My | 🔴 高 | 3-5h |
| 2 | **首页第二轮** — 聚焦报告与头条，移除知识库、实体、管道和健康模块 | ✅ 完成 | — |
| 3 | **移动端响应式打磨** — 所有页面在 320-480px 下的导航、密度和表单优化 | 🔵 中 | 2-3h |
| 3 | **收藏同步后端接入** — 账号体系就绪后，localStorage → 服务端同步 | ⚫ 暂缓 | - |

---

## 4. 架构模式（强制遵循）

### 4.0 关键文件（必读）

| 文件 | 用途 | 必读程度 |
|------|------|----------|
| `src/frontend_styles.py` | **设计系统** — 颜色/图标/CSS片段/JS工具 + `DESIGN_SYSTEM_VERSION` | ★★★ 每页都要 import |
| `src/i18n.py` | **翻译** — 所有文本的中英文翻译 | ★★★ 所有 UI 文本必须走翻译 |
| `src/api.py` | **API 路由** — 所有 `/api/*` 端点定义 | ★★ 知道有哪些端点 |
| `src/dashboard.py` | **参考实现** — 一个标准页面的完整写法 | ★★★ 照着这个模式写 |

### 4.1 页面 = Python 函数 → HTML 文件

每个页面有一个 Python 文件在 `src/`，一个输出文件在 `reports/`：

```
src/xxx.py              # Python 生成器 → 生成内联 CSS + JS 的完整 HTML
reports/xxx.html         # 输出文件
src/api.py               # 注册路由 → 返回 reports/xxx.html
```

### 4.2 Python 生成器模板

```python
"""简短描述"""
from .frontend_styles import TYPE_COLORS, ANIMATION_CSS, RESPONSIVE_CSS, ERROR_CSS, SHARED_JS
from .i18n import t, type_label, i18n_js, nav_html

def generate_xxx(output_dir=None, lang="zh"):
    html = _build_html(lang)
    # 写入 reports/xxx.html
    return path

def _build_html(lang="zh") -> str:
    return f'''<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{t("page_title", lang)}</title>
<style>
{ANIMATION_CSS}
{RESPONSIVE_CSS}
{ERROR_CSS}
/* 你的页面专属样式 */
</style>
</head>
<body>
{nav_html("xxx")}

<!-- 页面内容 -->

<script>
const LANG = "{lang}";
// i18n_js() 注入 JS 翻译对象 I18N 和 T()/TLbl() 函数
{i18n_js()}
{SHARED_JS}
// 你的页面专属 JS
</script>
</body>
</html>'''
```

### 4.3 必须使用的共享资源

| 资源 | 引入方式 | 用途 |
|------|----------|------|
| `TYPE_COLORS` | `from .frontend_styles import TYPE_COLORS` | 实体类型 → 颜色映射 |
| `TYPE_ICONS` | 同上 | 实体类型 → 图标映射 |
| `ANIMATION_CSS` | 注入 `<style>` 中 | 淡入/hover 动画 |
| `RESPONSIVE_CSS` | 注入 `<style>` 中 | 480/768/1024 断点 |
| `ERROR_CSS` | 注入 `<style>` 中 | 错误提示样式 |
| `SHARED_JS` | 注入 `<script>` 中 | apiFetch() / showError() |
| `nav_html(path)` | Python 中调用 | 顶部导航栏 + 语言切换（只接受页面路径） |
| `i18n_js()` | Python 中调用 | 注入 JS 翻译字典 `I18N` + `T()`/`TLbl()` 函数 |
| `t(key, lang)` | Python 中调用 | 后端翻译（lang 可选，默认 zh） |
| `T(key)` | JS 中调用 | 前端运行时翻译 |
| `TLbl(type)` | JS 中调用 | 类型标签翻译（双语格式） |

### 4.4 JS 数据获取规范

```javascript
// ✅ 正确：用 apiFetch 包装
const data = await apiFetch('/api/entities?type=model');

// ✅ 正确：带 loading 状态
showLoading();
const data = await apiFetch('/api/search?q=' + encodeURIComponent(q));
hideLoading();

// ❌ 错误：裸 fetch 不处理错误
fetch('/api/entities').then(r => r.json())  // 禁止

// ❌ 错误：不处理空结果
const data = await apiFetch('/api/articles');
data.forEach(...) // data 可能为 null
```

---

## 5. 设计约束

### 5.1 技术约束（硬性）
- ❌ **不要**引入任何 JS 框架（React/Vue/jQuery 等）— 纯 Vanilla JS
- ❌ **不要**引入任何 CSS 框架（Bootstrap/Tailwind 等）— 手写 CSS
- ❌ **不要**引入任何外部 CDN（字体/图标库除外）
- ❌ **不要**让文件超过 300 行 — 超过了就拆分
- ✅ **必须**支持中英文切换（所有 UI 文本走 `T()` / `t()`）
- ✅ **必须**响应式（≥480/768/1024 三个断点）
- ✅ **必须**有加载状态和错误处理

### 5.2 视觉约束
- **背景**: `#0d1117`（深色主题）
- **卡片**: `#161b22` + 边框 `#30363d` + 圆角 `8px`
- **强调色**: `#58a6ff`
- **字体**: 系统默认（-apple-system, BlinkMacSystemFont, Segoe UI, Roboto）
- **间距**: `padding: 20-24px` for cards, `gap: 12-16px` for grids
- **类型颜色**: 从 `TYPE_COLORS` 获取，不要硬编码

### 5.3 UI 文字全中文（术语保留英文 + 中文）
```
正确: "Model（模型）"
正确: "12 个实体"
错误: "12 entities"
```

---

## 6. 现有页面清单

| 页面 | Python 文件 | HTML 输出 | API 端点 |
|------|-----------|-----------|----------|
| Dashboard | `src/dashboard.py` | `reports/dashboard.html` | `/api/stats`, `/api/articles`, `/api/reports` |
| Library | `src/library.py` | `reports/library.html` | `/api/entities`, `/api/search` |
| Graph | `src/kg_d3.py` | `reports/knowledge-graph.html` | `/api/entities`, `/api/relationships` |
| Timeline | `src/timeline_data.py` + `src/timeline_renderer.py` | `reports/timeline.html` | `/api/entities` |
| Entity Detail | `src/entity_page.py` | `reports/entity.html` | `/api/entities/{id}` |
| **Events** | `src/events_page.py` | `reports/events.html` | `/api/entities?type=event` |

---

## 7. 可用 API 端点

```
GET  /api/entities?type=model          # 实体列表，按类型筛选
GET  /api/entities/{id}                # 单个实体 + 关系
GET  /api/entities/{id}/articles       # 实体关联文章
GET  /api/entities/{id}/similar        # 相似实体（embedding）
GET  /api/relationships?entity_id=     # 关系列表
GET  /api/articles?limit=50&min_score= # 文章列表
GET  /api/reports?type=daily&limit=30  # 报告列表
GET  /api/search?q=...&limit=20&semantic=true  # 搜索（关键词+语义混合）
GET  /api/stats                        # 统计概览
GET  /api/health                       # 健康检查
POST /api/research  {"topic":"...","depth":"standard|deep","lang":"zh|en"}  # 🆕 深度研究
POST /api/embeddings/rebuild?force=true # 重建嵌入
GET  /api/embeddings/status            # 嵌入状态
```

---

## 8. 验收清单（Claude 审查时必查）

每次你交付一个页面，Claude 会按以下清单检查：

- [ ] 页面能正常加载（无 JS 报错）
- [ ] 所有 API 调用用 `apiFetch()` 包装
- [ ] 有 loading 状态和错误提示
- [ ] 中英文切换正常工作
- [ ] 所有 UI 文字走 `T()` / `t()` 翻译
- [ ] 类型颜色/图标从 `TYPE_COLORS` / `TYPE_ICONS` 获取
- [ ] 导航栏通过 `nav_html()` 生成
- [ ] 样式注入 `ANIMATION_CSS` / `RESPONSIVE_CSS` / `ERROR_CSS`
- [ ] 响应式：在 480/768/1024 宽度下不崩
- [ ] 文件 < 300 行
- [ ] 无 jQuery / React / Bootstrap 等外部依赖
- [ ] 数据为空时有合理空状态

---

## 9. 启动开发环境

```bash
# 启动 API 服务器（Claude 会帮你启动）
cd ai-news
uv run uvicorn src.api:app --reload --port 8765

# 访问页面
http://127.0.0.1:8765/                  # Dashboard
http://127.0.0.1:8765/library           # Library
http://127.0.0.1:8765/graph             # Knowledge Graph
http://127.0.0.1:8765/timeline          # Timeline
http://127.0.0.1:8765/entity/{id}       # Entity Detail
http://127.0.0.1:8765/events            # Events
```

---

## 10. Claude 的职责

为了避免你做的事情和我做的事情冲突，以下是 Claude 的职责：
- 后端 API（新增端点、修改返回格式）
- 数据库 schema 变更
- 知识卡片（YAML）管理
- Pipeline / Collector 等数据管道
- **审查你的前端代码**，按第 8 节清单验收
- **维护本文件**的 §3 会话状态和 §11 变更日志

---

## 11. 变更日志

> Claude 每次前端变更后在此追一行。Codex 看最后几条就能知道上次会话发生了什么。

| 日期 | 设计系统版本 | 变更 | 影响页面 |
|------|-------------|------|----------|
| 2026-07-03 | 7.2.3 | **Codex 全站同步提交** — Claude 提交全部 Codex 改动（16 文件, +391/-259）；后端修复 timeline date 归一化；141 张 methodology 卡片入库 | 全部 |
| 2026-07-03 | 7.2.3 | **Reports 编辑型归档** — 卡片列表改为连续分隔行，统计区在桌面与移动端均保持紧凑三列 | Reports |
| 2026-07-03 | 7.2.2 | **Topics 渐进披露** — 全量卡片墙改为编辑型分隔列表，每类默认 4 项并支持展开/收起；搜索结果保持完整 | Topics |
| 2026-07-03 | 7.2.1 | **Today 信息架构减法** — 头条压缩至 6 条、最近报告压缩至 3 条；移除重复知识库入口、核心实体、数据管道和系统健康 | Today |
| 2026-07-03 | 7.2.0 | **双主题基础重构** — 深色改为暖石墨编辑室，亮色改为暖纸底与纸张内容面；替换首页旧 GitHub 色彩硬编码并完成 48 项视觉矩阵验收 | 全局 Token / Today |
| 2026-07-03 | 7.1.0 | **编辑型首页第二轮** — 卡片仪表盘改为刊头、非对称情报栏与分隔章节；Timeline/Topics 恢复里程碑事件及 2D/3D 知识图谱二级入口 | Today / Timeline / Topics |
| 2026-07-03 | 7.0.0 | **系统视觉升级启动** — 暖灰黑/纸白主题 Token、编辑型展示字体、紧凑分段导航；Article 改为杂志式阅读版式，Dashboard 建立 Briefing 标杆 | 全部 Token / Today / Article |
| 2026-07-02 | 5.2.0 | **品牌升级 + 收藏系统 + My 页面** — AI 观察室品牌重命名、全局 localStorage 收藏、收藏按钮遍布 Dashboard/Library、My 页面（收藏列表+分类+标签+同步状态）、导航重构（5 项 aliases）、`tools/verify_frontend.py` 一键验证、Makefile | 全部 |
| 2026-07-01 | 5.1.0 | **Research Assistant 页面** — 新建研究助手页面（表单+AI报告渲染），新增 `POST /api/research` 端点，nav 新增"研究"入口 | research |
| 2026-07-01 | 5.1.0 | **Category Navigation** — Library 页顶部分类标签可点击，smooth scroll + sticky + scroll spy | library |
| 2026-07-01 | 5.1.0 | **Reports 页面** — 报告浏览器，统计卡片 + 按类型分组 + i18n | reports |
| 2026-07-01 | 5.1.0 | **主题切换** — :root 暗色 + [data-theme="light"] 亮色，THEME_VARS 导出 + toggleTheme() JS | 全部 |
| 2026-07-01 | 5.0.0 | **3D Knowledge Graph** — Three.js + 3d-force-graph | graph3d |
| 2026-07-01 | 5.0.0 | CSS Token 体系 + 骨架屏 + 响应式NAV优化 + 共享设计系统 | 全部 |
| 2026-07-01 | 5.0.0 | Events 里程碑页面交付 | events |
| 2026-06-30 | — | 共享设计系统抽离：frontend_styles.py + i18n.py | 全部 |

---

## 12.附加说明

Codex 可以提出新的前端设计方案、交互方案和页面结构优化，但实现时必须遵守现有技术栈、设计系统、i18n 和 API 边界。若方案需要突破现有约束，先写方案，不直接改代码。

---

## 13. Codex 笔记（跨会话记忆）

> Codex 每会话结束时在此追加关键发现。只记非显而易见的经验，不记代码里已有的。
> 新会话时扫一眼最后 3-5 条。

| 日期 | 类型 | 发现 |
|------|------|------|
| 2026-07-02 | 决策 | 收藏系统用 localStorage（key: `ai_observatory_favorites`），不用 IndexedDB——当前数据量小、不需要索引 |
| 2026-07-02 | 注意 | 收藏按钮 CSS（`.favorite-btn`）在 Dashboard 和 Library 中分别定义，如果样式不统一要注意同步 |
| 2026-07-02 | 技术债 | `nav_html()` aliases 机制是临时方案，如果页面继续合并/增加，考虑抽成独立 `nav_config` |

---
> **最后更新**: 2026-07-02
> **维护者**: Claude + 杨成俊
