# .agents — 部署 Agent 体系说明

> 5 个规则文档 + 6 个部署脚本，覆盖"规划 → 执行 → 诊断 → 验收"全流程。

---

## 触发词速查

你说以下词，AI 按对应流程执行：

| 你说 | AI 做什么 | 对应脚本 |
|------|-----------|---------|
| **体检** | 环境检查（只读） | `bash scripts/preflight.sh` |
| **准备部署** | 分析变更 → 产出部署清单（不执行） | — |
| **执行前端部署** | 前端文件上传 + 重生成 HTML + Nginx reload | `bash scripts/deploy_frontend.sh` |
| **执行后端部署** | 后端文件上传 + 重启 ai-news（L2 需确认） | `bash scripts/deploy_backend.sh` |
| **执行报告部署** | 报告上传 + 重生成 Dashboard + Nginx reload | `bash scripts/deploy_reports.sh` |
| **验收** | 冒烟测试（只读） | `bash scripts/qa_smoke_test.sh` |
| **回滚** | 输出回滚方案 → 等确认 → 恢复（L3 逐条确认） | 按方案执行 |

> 完整规则见 `deployment_rules.md`。

---

## 文件体系

### 规则文档（AI 读的 SOP）

| 文件 | 职责 |
|------|------|
| `deployment_rules.md` | **共享宪法**：铁律、触发词、权限、陷阱库、部署基线 |
| `deploy_planner.md` | **部署规划**：分析变更 → 产出部署清单 |
| `deploy_executor.md` | **部署执行**：按清单执行备份→上传→重生成→重启 |
| `server_debugger.md` | **服务器诊断**：QA 失败后定位根因 |
| `release_qa.md` | **发布验收**：跑 AC1-AC20 + T1-T16 验收清单 |

### 可执行脚本（人直接跑的）

| 脚本 | 职责 | 行数 |
|------|------|------|
| `scripts/preflight.sh` | 环境检查 | 201 |
| `scripts/deploy_backend.sh` | 后端部署 | 304 |
| `scripts/deploy_frontend.sh` | 前端部署 | 282 |
| `scripts/deploy_reports.sh` | 报告部署 | 204 |
| `scripts/verify_server.sh` | HTTP 验证 | 169 |
| `scripts/qa_smoke_test.sh` | 冒烟测试 | 264 |

---

## 标准部署流水线

```
"体检"
    ↓ PASS
"准备部署"  → 看一眼清单
    ↓
"执行后端部署"  → 确认一次重启（L2）
    ↓
"执行前端部署"
    ↓
"执行报告部署"（如有）
    ↓
"验收"  → PASS = 发布完成 | FAIL = 诊断/回滚
```

---

## 安全边界

- 不使用 `ai-server` alias，统一 `admin@121.43.80.221`
- 服务器 Python 统一 `.venv/bin/python`，不使用 `uv`
- 所有脚本 `set -euo pipefail`，任何一步失败立即停止
- 禁止 `rm -rf`、禁止覆盖 `.env/data/reports/.venv`
- 回滚必须先出方案再等确认（L3）
