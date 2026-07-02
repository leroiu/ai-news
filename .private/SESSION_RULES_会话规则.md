# AI Intelligence Platform — 会话启动规则

> 定义 AI Agent 进入本项目时的标准启动流程。
> 适用范围: Claude Code / Codex / Kimi / GPT 等所有 AI 编码助手。

---

## 新会话启动流程

```
① 读 ENGINEERING_PRINCIPLES_工程原则.md
     ↓
② 读 PROJECT_MEMORY_项目长期记忆.md（§1-3: 身份 + 目标 + 约束）
     ↓
③ 读 HANDOVER_项目交接.md
     ↓
④ 确认当前任务
     ↓
⑤ 只读取当前任务相关的文档（不扫描全项目）
     ↓
⑥ 优先使用已有架构（不重新发明）
     ↓
⑦ 开始开发
```

---

## 规则

### 读取规则

- **Layer 1 必读**: 每新对话都读。ENGINEERING_PRINCIPLES_工程原则.md → PROJECT_MEMORY_项目长期记忆.md §1-3 → HANDOVER_项目交接.md
- **Layer 2 按需**: 任务需要时读。ARCHITECTURE_系统架构.md / ROADMAP_项目路线图.md / DECISIONS_架构决策记录.md / CHANGELOG_变更日志.md
- **Layer 3 自动判断**: AI 判断需要时才读。API_API接口.md / DATABASE_数据库结构.md / OPENSPEC_原始设计.md / KNOWLEDGE-CARD-SCHEMA_知识卡片结构.md
- **禁止读取**: README.md（Human Only，AI 不需要）

### 上下文效率规则（Context Efficiency）

> 基于 2026-06-30 会话教训：136.9k tokens (80%) 浪费于 Agent 过度输出 + 全量文件读 + JS 调试读 HTML。
> 这些规则是 ENGINEERING_PRINCIPLES_工程原则.md §1 的战术执行层。

#### Agent 调用

| 规则 | 强制 |
|------|------|
| Explore Agent prompt 必须含输出上限："只返回路径和摘要，不返回文件内容；≤500 words" | ✅ |
| 多 Agent 并行时，每个 Agent 职责单一，不交叉读取相同文件 | ✅ |
| 禁止让 Agent 读取它不需要的文档（如让 Explore Agent 读 HANDOVER） | ✅ |

#### 文件读取

| 规则 | 强制 |
|------|------|
| 超过 200 行的文件禁止全文 Read → 先 Grep 定位行号，再 `Read offset=N limit=M` | ✅ |
| 配置文件（.env / pyproject.toml / config.yaml）用 offset 读关键段，不读全文 | ✅ |
| 同会话内 Layer 1 文档只读一次，后续引用记忆，不重读 | ✅ |

#### JS/HTML 调试

| 规则 | 强制 |
|------|------|
| JS 语法验证：`node -e "new Function(code)"` 一行命令，不读 HTML 文件 | ✅ |
| 浏览器验证：用 Playwright snapshot（文本），不用 screenshot（图片更大） | ✅ |
| 页面问题定位：先 browser_snapshot 看结构，再决定是否需要 screenshot | ✅ |

#### 搜索策略

| 规则 | 强制 |
|------|------|
| 明确目标文件和模式后再 Grep，不无方向扫描 | ✅ |
| Grep 用 `glob` 过滤文件类型（如 `glob: "*.py"`），缩小范围 | ✅ |
| 搜索结果过多时（>20 条）先缩小范围，不全量展开 | ✅ |

### 行为规则

- 🚫 **禁止扫描整个项目**: 不要遍历所有文件，只读当前任务相关的
- 🚫 **禁止重新发明**: 已有架构/模块直接复用，不推倒重来
- ✅ **优先增量**: 在现有架构上增量修改，不做大重构
- ✅ **先理解再动手**: 读完 Layer 1 + 相关文档后再写代码

### Plan Mode

- 涉及 3 个以上文件修改 → 先出方案
- 架构/数据库变更 → 先出方案
- 需求不明确 → 先澄清再动手

---

## Adaptive Autonomy（自适应自治）

### Normal Mode（默认）

**AI 可自主执行**: 阅读项目、修改代码、创建文件、运行测试、修复普通 Bug、重构局部代码

**必须暂停确认**: 删除重要文件/数据库、修改环境变量/密钥、调用收费 API、Git Push / 发布版本、任何不可逆操作

### Focus Mode（专注模式）

**AI 可自主执行**: 连续开发、自动测试、运行 Pipeline、重构模块、创建和修改数据库结构、更新 HANDOVER_项目交接.md、按 ROADMAP_项目路线图.md 推进项目

**仍必须暂停**: 调用收费 API、删除大量数据/文件、获取或修改密钥、Git Push / Release、不可逆操作、AI 对方案存在明显不确定性

### Working Rule

- 除非用户明确切换到 Focus Mode，否则始终使用 Normal Mode
- 进入 Focus Mode 后：不频繁请求确认、优先完成当前 ROADMAP_项目路线图.md、不擅自新增需求、每完成一个阶段更新 HANDOVER_项目交接.md、遇到安全边界立即暂停

---

## Codex 协作规则

> 本项目与 Codex（前端 AI Agent）协作开发。Codex 每次新会话**没有**完整记忆，依赖项目文件获取上下文。

### Codex 入口

- Codex 启动时读取项目根 `CODEX.md`（指针文件，< 50 行）
- `CODEX.md` → `docs/DESIGN_SYSTEM.md` → `docs/INFORMATION_ARCHITECTURE.md` → `CODEX_HANDOFF` §3
- 不在 `CODEX.md` 中存储内容，只做路由

### 会话结束同步协议（3 步）

每次前端变更后，Claude 必须执行：

| 步骤 | 更新什么 | 位置 | 约需 |
|------|---------|------|------|
| 1 | 页面状态表 + 待办任务 | `CODEX_HANDOFF` §3 | 30s |
| 2 | 版本号 bump | `frontend_styles.py` `DESIGN_SYSTEM_VERSION` | 10s |
| 3 | 变更日志追一行 | `CODEX_HANDOFF` §11 | 10s |

HANDOVER 仍是 Claude 的完整记录（含非前端变更），Codex 不需要读。

### Codex 上下文预算

- 禁止让 Codex 读 HANDOVER、ENGINEERING_PRINCIPLES 等 Claude 内部文档
- 禁止让 Codex 扫描整个项目或 `src/engine/`
- `CODEX.md` < 50 行，`CODEX_HANDOFF` §3 < 50 行

---
> **维护**: 随项目协作经验迭代。
