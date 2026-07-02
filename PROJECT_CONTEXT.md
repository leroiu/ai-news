# PROJECT_CONTEXT.md — 项目短版上下文

> 新会话先读本文件；详细页面状态、API 清单和变更记录见 `.private/CODEX_HANDOFF_Codex协作说明.md`。

## 产品与设计宪法

AI Intelligence Platform 是“AI 情报平台 + 初级个人收藏沉淀系统”。核心闭环是：发现信息 → 理解价值 → 判断优先级 → 收藏分类 → 定期回看。界面应低调、克制、现代、适合长期阅读；事实、分析、推测、建议必须可区分，不用焦虑营销或未来能力冒充当前能力。

收藏是用户行为，平台星级是编辑重要性评级，两者不得混用。账号后端未完成前，只能说明本地前端收藏可用，禁止声称“已同步账号”“已云端同步”或“跨设备已同步”。

## 信息架构

五个一级任务入口必须在所有核心页面保持一致：

- 今日 `/`
- 专题 `/library`
- 时间线 `/timeline`（`/events` 是内部视图）
- 研究 `/reports`（`/research` 是内部工作台）
- 我的 `/my`

页面遵循全局框架、页面上下文、内容画布三层结构。新增页面优先复用 `PageShell/render_page()`、共享导航、收藏、筛选、空状态和错误状态组件。

## 技术约束

- Python 3.11+、FastAPI、Vanilla JS、内联 CSS；零前端框架、零 CDN。
- UI 文本必须走 `T()` / `t()`；颜色使用语义 Token / `TYPE_COLORS`。
- API 调用使用 `apiFetch()`；知识卡 YAML 是 SSOT。
- 响应式断点为 480/768/1024；单文件目标少于 300 行。
- 不覆盖用户未提交改动；修改后先做相关验证，再做全量验证。

## 验证入口

- 开发：`uv run python tools/verify_frontend.py --mode dev --routes /当前页面`
- 合并：`make verify`（全量测试、路由与机器验收）
- 视觉：`make visual-check`（核心页面桌面端与移动端截图）
- 发布：`uv run python tools/verify_frontend.py --mode release`

截图与视觉分析固定输出到 `output/playwright/`。详细人工验收问题以 `docs/DESIGN_SYSTEM.md` §14 和 handoff 为准。

## 最小验收清单

- 五个一级导航一致且 active 归组正确。
- 所有适用内容卡有统一收藏入口，中英文文本完整。
- `/my` 等核心路由返回 200。
- 移动端无页面级横向溢出。
- HTML 无重复 ID，无虚假账号同步文案。
- 浏览器控制台无 `error`，相关测试通过。
