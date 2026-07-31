# Deployment Status — 部署状态

> 最后更新：2026-07-06

---

## SSH 免密登录

| 项目 | 状态 |
|------|------|
| 密钥类型 | ed25519 |
| 认证方式 | 免密（公钥已写入服务器） |
| 连接命令 | `ssh admin@121.43.80.221 "命令"` |
| SCP 命令 | `scp 本地文件 admin@121.43.80.221:远程路径` |
| 基本可用 | ✅ |

### 已知限制

| 问题 | 影响 | 处理 |
|------|------|------|
| `known_hosts` 中文路径编码警告 | 每次 ssh 输出 2 行编码乱码警告 | **暂不处理**，不影响连接和部署 |
| SSH alias（`ai-server`）不可用 | 不能用 `ssh ai-server` 简写 | **统一使用完整地址** `admin@121.43.80.221` |

---

## 部署 Agent 体系

| Agent | 文件 | 状态 |
|-------|------|------|
| 共享宪法 | `.agents/deployment_rules.md` | ✅ 已创建 |
| 部署规划 | `.agents/deploy_planner.md` | ✅ 已创建 |
| 部署执行 | `.agents/deploy_executor.md` | ✅ 已创建 |
| 服务器诊断 | `.agents/server_debugger.md` | ✅ 已创建 |
| 发布验收 | `.agents/release_qa.md` | ✅ 已创建 |

---

## 部署脚本体系

| 脚本 | 行数 | 职责 | 触发 |
|------|------|------|------|
| `scripts/preflight.sh` | 201 | 部署前环境检查（本地+SSH+磁盘+Nginx+API） | 每次部署前 |
| `scripts/deploy_backend.sh` | ~260 | 语法检查→备份→上传→md5→重启 ai-news→API冒烟 | API/Engine/Pipeline 变更后 |
| `scripts/deploy_frontend.sh` | 282 | 语法检查→备份→上传→md5→重生成 HTML→Nginx reload | 前端文件变更后 |
| `scripts/deploy_reports.sh` | 204 | 批量上传 reports/*.md + *.html → 重生成 Dashboard | 报告内容变更后 |
| `scripts/verify_server.sh` | 169 | API + 页面 HTTP 可达性检查 | 部署完成后 |
| `scripts/qa_smoke_test.sh` | 264 | 核心页面+API+JS注入+文件时间戳 冒烟测试 | 发布前 |

### 完整部署流水线

```
bash scripts/preflight.sh        # 1. 环境检查
    ↓ (全部 PASS)
bash scripts/deploy_backend.sh   # 2a. 后端部署（API/Engine/Pipeline）
    ↓                          #     上传 → 重启 ai-news 服务
bash scripts/deploy_frontend.sh  # 2b. 前端部署（Dashboard/ReportReader/My）
    ↓                          #     上传 → 重生成 HTML → Nginx reload
bash scripts/deploy_reports.sh   # 3. 报告部署（如有）
    ↓
bash scripts/verify_server.sh    # 4. HTTP 验证
    ↓
bash scripts/qa_smoke_test.sh    # 5. 冒烟测试 → PASS/FAIL
```

所有脚本：
- 统一使用 `admin@121.43.80.221`（无 alias）
- 禁止 `rm -rf`，不修改 Nginx/systemd 配置
- `set -euo pipefail` — 任何一步失败立即停止
- 每步输出清晰日志 + 颜色标记 PASS/FAIL/WARN

---

## 近期待部署

> 当前等待部署的文件（来自 Codex 验收发现）：

| 文件 | 原因 |
|------|------|
| `src/frontend/frontend_styles.py` | `uiPersonalItems()` 未部署 + meta 字段补全 |
| `src/frontend/report_reader.py` | `inlineMarkdown` 缺相对 URL 处理 |
| `src/frontend/my_page.py` | 合并收藏+已读/稍后项 |
| `src/interfaces/i18n.py` | `star5_*` 新 key + "稍后"/"沉淀" 文案 |

---

## 下一步

1. 运行 Deploy Planner 分析变更
2. 运行 Deploy Executor 上传 + 重生成
3. 运行 Release QA 验收
