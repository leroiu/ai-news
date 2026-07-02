# CODEX.md — 前端协作入口

> **写给 Codex**：这是项目入口。先读短版上下文；只有任务需要时再查详细文档。

---

## 启动必读（按顺序）

| # | 读什么 | 得到什么 | 行数 |
|---|--------|---------|------|
| 1 | `PROJECT_CONTEXT.md` | 设计宪法、信息架构、技术约束、验收入口 | ~60 |
| 2 | `.private/CODEX_HANDOFF_Codex协作说明.md` **§3** | 当前页面状态与待办；按需阅读 | ~40 |
| 3 | `src/frontend/frontend_styles.py` → 搜 `DESIGN_SYSTEM_VERSION` | 当前设计系统版本号 | 1 |

## 关键路径速查

| 你要做的事 | 去哪个文件 |
|-----------|-----------|
| 新建/改页面 | `src/frontend/` — 按已有页面模式写 |
| 注册路由 | `src/api/api.py` — 加 `@app.get("/xxx")` |
| 加翻译 | `src/interfaces/i18n.py` — 中英文 key |
| 加共享 CSS/JS | `src/frontend/frontend_styles.py` |
| 加共享组件 | `src/frontend/frontend_components.py` |
| 改导航 | `src/interfaces/i18n.py` → `nav_html()` |
| 看 API 有哪些 | `CODEX_HANDOFF` §7 |
| 跑验证 | `make verify` 或 `uv run python tools/verify_frontend.py` |

## 硬约束（违反会打回）

- 纯 Vanilla JS + 内联 CSS，**零框架零 CDN**
- 所有 UI 文本走 `T()` / `t()` 翻译
- 颜色从 `TYPE_COLORS` 取，不硬编码
- 文件 < 300 行
- 响应式 480/768/1024 断点
- API 调用用 `apiFetch()`，不用裸 `fetch()`

## 同步协议

每次前端变更后，Claude 更新：
1. `CODEX_HANDOFF` §3 页面状态表 + §11 变更日志
2. `frontend_styles.py` `DESIGN_SYSTEM_VERSION` bump

Codex 下次会话读 §3 就知道当前状态，读 §11 知道上次改了什么。
