# 长程自主开发模式

## 目标

让 Claude Code 在无人确认的情况下连续完成数小时的仓库内开发，同时把生产、云资源、密钥和不可逆外部操作留在边界之外。

ECS 不是本模式的前置条件。没有 Preview ECS 时，本模式可完成代码修改、本地测试、质量门禁、检查点提交和交付报告；远程部署后验收保持阻塞。

## 模式划分

| 模式 | 权限 | 使用环境 | 当前状态 |
|---|---|---|---|
| Plan | 只读分析 | 任意环境 | 可用 |
| LongRun Host | `dontAsk` + 白名单 | 本机独立 worktree | 可用 |
| Full Sandbox | `bypassPermissions` + OS 沙箱 | 一次性容器/VM/WSL2 Linux 文件系统 | 尚未配置 |

本机禁止直接使用 `bypassPermissions`。它跳过权限检查，而当前 Windows 原生 Claude Code 没有 OS 级沙箱；仓库内运行的 Python/Node 子进程也不受文件工具权限的完整约束。

## LongRun Host 权限

允许：

- 读取和修改当前 worktree 内的项目文件；
- 使用锁定依赖运行 `uv`、`pytest`、项目质量工具、npm 和 Playwright；
- 创建功能分支、本地暂存和本地提交；
- 查询公开技术文档；
- 写入 `output/` 下的测试证据与运行检查点。

拒绝：

- 读取或修改 `.env`、`.private/`、SSH 和凭据目录；
- 修改规则文件、Claude 权限配置和断点工具；
- `git push`、merge、rebase、force、reset、clean；
- `gh` 写操作、SSH/SCP、云 CLI、生产部署和数据库迁移；
- 购买资源、配置域名、IAM、安全组或共享基础设施；
- 访问现有生产服务器 `121.43.80.221`。

## 执行循环

1. 在独立 worktree 中记录目标、验收条件、初始 Git 状态。
2. 阅读相关实现和测试，形成最小改动范围。
3. 完成一个可验证增量。
4. 运行文件级测试或 `tools/test_router.py run`。
5. 记录证据；跨模块前进行本地检查点提交。
6. 重复 2–5，直到满足验收条件。
7. 运行 `tools/quality_gate.py checkpoint`；涉及前端时追加 browser 与 accessibility gate。
8. 对抗式检查边界、失败路径、污染和未验证假设。
9. 输出改动、证据、残余风险和需要用户执行的外部步骤。

## 中断与恢复

- `PreCompact` 和 `Stop` hook 将分支、Git 状态、差异统计和最后提交写入 `output/claude-checkpoints/`。
- 模型容量错误时保留当前会话和 worktree，等待后使用 `claude --continue` 或从 `latest.json` 恢复。
- Headless 模式可配置主模型、fallback model 和 API 预算；fallback 只能处理支持的模型不可用场景，不能突破账户限额或服务故障。
- 同一失败连续出现三次后停止重试，记录失败指纹和所需输入，避免无限循环。

## 启动

交互运行：

```powershell
.\scripts\start-claude-longrun.ps1
```

单任务无人值守运行：

```powershell
.\scripts\start-claude-longrun.ps1 `
  -Headless `
  -Task "实现已批准的任务并跑完本地质量门禁" `
  -MaxBudgetUsd 10
```

默认使用新的 Git worktree。只有工作区完全干净且明确需要当前分支时，才传 `-CurrentWorktree`。
可先附加 `-DryRun` 验证参数与本机前置条件，不启动模型会话。
隔离 worktree 创建在系统临时目录 `ai-news-longrun-worktrees/`，使用 `codex/ai-news-longrun-*` 分支，并在会话结束后保留，供人工检查和恢复。

## 升级到 Full Sandbox

配置 WSL2 沙箱后才允许启用：

- 仓库复制到 WSL2 的 Linux 文件系统，不在 `/mnt/c` 下执行；
- 安装并验证 `bubblewrap` 与 `socat`；
- `sandbox.failIfUnavailable=true`，禁止无沙箱降级；
- 默认禁止网络，只放行依赖源和必要文档域名；
- 不挂载 Windows 用户目录、SSH、云凭据或生产密钥；
- 沙箱销毁后不保留凭据和后台进程。

达到上述条件后，`bypassPermissions` 才能作为沙箱内部权限模式使用。Preview ECS 准备完成后，只增加独立 Preview 部署和 postdeploy gate，不改变生产禁区。
