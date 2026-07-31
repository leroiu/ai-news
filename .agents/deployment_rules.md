# Deployment Rules — 部署铁律与共享知识

> 本文件是部署体系的共享宪法。模型无关，适用于所有 AI 和开发者。
> 所有部署操作遵循"触发词 + 固定脚本 + 固定输出"原则。

---

## 1. 服务器信息

| 项目 | 值 |
|------|-----|
| IP | `121.43.80.221` |
| 用户 | `admin` |
| SSH 连接 | `ssh admin@121.43.80.221 "命令"` |
| SCP 上传 | `scp 本地文件 admin@121.43.80.221:远程路径` |
| SSH 认证 | ed25519 免密（已配置） |
| 系统 | Ubuntu 24.04 2C4G |
| 应用根目录 | `/home/admin/app/` |
| 服务器 Python | `/home/admin/app/.venv/bin/python` |
| 前端入口 | Nginx → `/home/admin/app/reports/` |
| API 代理 | Nginx `location /api/` → `http://127.0.0.1:8765` |
| 报告路由 | `/report/*.md` → Nginx 返回 `report-reader.html` shell |
| 报告内容 API | `/api/report-content/{filename}` |
| known_hosts | 中文路径编码警告，不影响部署，暂不处理 |
| SSH alias | 不使用 `ai-server`，统一使用完整地址 `admin@121.43.80.221` |

---

## 2. 铁律（所有部署操作必须遵守）

| # | 规则 | 说明 |
|---|------|------|
| 1 | **本地开发，服务器部署** | 所有源码修改只在本地项目中进行 |
| 2 | **禁止 cat pipe 上传** | 不使用 `cat local | ssh "cat > remote"` |
| 3 | **禁止服务器 nano 粘大段代码** | 不在阿里云 Web 终端用 nano 编辑 |
| 4 | **上传统一使用 scp** | 单文件逐个上传，md5 验证每个文件 |
| 5 | **每条命令标明执行位置** | `📁 本地 Git Bash / VS Code 终端` 或 `🖥️ 阿里云服务器` 或 `🔍 浏览器 F12` |
| 6 | **服务器只负责运行/验证/重启/reload** | 不在服务器上编辑源码 |
| 7 | **前端问题优先 F12** | Console / Network / Application / Storage 四面板诊断 |
| 8 | **连续补洞时先做回归测试** | 修一个 bug 前先验证其他功能没有被破坏 |
| 9 | **上下文超过 80% 必须收口** | 停止新功能，只写 HANDOVER / PROJECT_MEMORY / 总结 |
| 10 | **不要临时拼复杂远程命令** | 涉及引号/f-string/花括号的远程命令，优先用 `scripts/` 固定脚本。如果现有脚本不能覆盖，先说明缺口，再补脚本，不要临时硬拼 `ssh + python -c` |
| 11 | **PowerShell 只执行简单命令** | PowerShell 只允许 `ssh ... 'echo OK'`、`curl` 等简单命令。复杂部署命令在 Git Bash 执行或写入脚本 |
| 12 | **失败不超过 2 次** | 连续失败 2 次停止，优先交给 `server_debugger` 判断原因 |

---

## 3. 部署陷阱库（已踩过的坑）

> 来源：PROJECT_MEMORY + CODEX_HANDOFF

| # | 陷阱 | 现象 | 预防/修复 |
|---|------|------|----------|
| T1 | **scp 静默失败** | exit 0 但服务器文件未变 | 每次 scp 后立即比对本地和服务器 md5 |
| T2 | **Pipeline Stage 9 覆盖 HTML** | 手动上传的 HTML 被 pipeline 覆盖 | 先上传 .py 源文件，再运行 pipeline 重生成 |
| T3 | **`__pycache__` 缓存旧代码** | 上传 .py 后服务器仍运行旧逻辑 | 每次部署后 `find . -type f -name '*.pyc' -delete` |
| T4 | **`__file__.parent.parent` 路径** | 脚本放 app 根目录时 `parent` 指向 `/home/admin` | 用 `Path(__file__).resolve().parent` + 检测 `src/` 目录 |
| T5 | **f-string `{{}}` 转义** | JS 模板字符串中的 `{}` 被 Python f-string 吃掉 | Python f-string 中 JS 的 `{}` 必须写成 `{{}}` |
| T6 | **Nginx 对 `/report/*.md` 返回 HTML shell** | `curl /report/2026-07-05.md` 返回 HTML | 用 `/api/report-content/{filename}` 获取原始 markdown |
| T7 | **服务器终端不支持多行** | here-doc / 多行命令在阿里云 Web 终端失败 | 所有服务器命令单行；复杂脚本在本地写好上传执行 |
| T8 | **`python3` 指向 Windows Store 假 Python** | 语法检查失败，实际 `python` 才是真的 | 脚本优先用 `command -v python`，`python3` 作为 fallback |
| T9 | **服务器无 `uv`** | Ubuntu 系统 Python 环境被 apt 管理 | 不使用 `uv run python`，统一用 `.venv/bin/python` |

---

## 4. 触发词部署流程

所有部署围绕 7 个触发词 + 固定脚本。不临时拼命令，不临时造轮子。

### 4.1 "体检" — 环境检查

**含义**：部署前检查环境，不修改任何文件，不上传，不重启。

**操作**：
```
📁 VS Code 终端: bash scripts/preflight.sh
```

**输出格式**：
```
状态：PASS / FAIL
证据：
1. SSH 连接 → OK
2. 磁盘使用率 → 8%
3. ai-news 服务 → active
下一步：可以部署 / 阻塞原因
```

### 4.2 "准备部署" — 部署规划

**含义**：只做规划，不执行任何部署操作。

**操作**：
1. `git diff --name-only HEAD` 查看变更
2. 按文件类型分类（前端/后端/报告）
3. 推荐对应脚本
4. 标明 L2 风险项

**不能做**：
- 不上传文件
- 不重启服务
- 不修改服务器
- 不执行 deploy 脚本

**输出格式**：
```
状态：READY / BLOCKED
部署类型：frontend / backend / reports / full
将执行脚本：
  bash scripts/deploy_frontend.sh
  bash scripts/deploy_backend.sh
风险点：重启 ai-news 服务（L2，需确认）
需要你确认：重启 ai-news / 批量上传
```

### 4.3 "执行前端部署" — 前端部署

**含义**：部署前端相关文件并重生成页面。

**操作**：
```
📁 VS Code 终端: bash scripts/deploy_frontend.sh
```

**脚本覆盖**：`dashboard.py` `report_reader.py` `my_page.py` `frontend_styles.py` `i18n.py`

**自动执行**：语法检查 → 备份 → scp 上传 → md5 验证 → 重生成 HTML → 清 `__pycache__` → Nginx reload → 写入日志

**注意**：某个文件上传失败时只汇报，不自动乱修，不临时拼 scp/ssh。

### 4.4 "执行后端部署" — 后端部署

**含义**：部署 API / engine / 数据处理代码。

**操作**：
```
📁 VS Code 终端: bash scripts/deploy_backend.sh
```

**脚本覆盖**：`src/api/` `src/engine/` `src/interfaces/` `pipeline.py` 等

**自动执行**：语法检查 → 备份 → scp 上传 → md5 验证 → 清 `__pycache__` → 重启 ai-news 服务 → 验证 `/api/health`

**权限**：重启 ai-news 属于 L2，需用户确认一次。

**禁止**：覆盖 `.env` `data/` `reports/` `.venv/`

### 4.5 "执行报告部署" — 报告部署

**含义**：同步 reports 文件和报告入口。

**操作**：
```
📁 VS Code 终端: bash scripts/deploy_reports.sh
```

**脚本覆盖**：`reports/*.md` `reports/*.html`

**自动执行**：上传 → md5 验证 → 重生成 Dashboard → Nginx reload

**涉及 DB 同步时**：需说明影响范围，用户确认后执行。

### 4.6 "验收" — 冒烟测试

**含义**：部署后检查网站是否真的可用，不修改代码。

**操作**：
```
📁 VS Code 终端: bash scripts/qa_smoke_test.sh
```

**检查内容**：
- 所有核心页面可访问（Dashboard / My / Reports / 报告阅读器）
- API 端点返回 200（/api/health /api/reports /api/articles）
- 关键 JS 函数成功注入（favBtn / uiPersonalItems / raBtn 等）
- HTML 文件生成时间在最近 7 天内

**输出格式**：
```
状态：PASS / FAIL
通过：18
失败：0
失败项：
下一步：可以发布 / 回滚 / 诊断
```

### 4.7 "回滚" — 部署回滚

**含义**：部署后网站异常，恢复到部署前版本。

**流程**：
1. 找到最近一次备份（`filename.bak.20260706_185929` 格式）
2. 输出回滚方案：恢复哪些文件、是否影响 data/reports/.env
3. **等待用户确认**
4. 执行恢复命令
5. 重启或 reload
6. 跑 `bash scripts/qa_smoke_test.sh` 验证

**禁止**：
- ⛔ 不允许自动执行（L3 操作，必须逐条确认）
- ⛔ 不允许 `rm -rf`
- ⛔ 不允许删除 `data/` `reports/` `.env` `.venv/`
- ⛔ 不允许未说明影响范围就执行

---

## 5. 权限分级

| 等级 | 定义 | 行为 | 示例 |
|------|------|------|------|
| L0 | 只读 | 自动执行，无需确认 | `curl`, `ls`, `md5sum`, `git diff` |
| L1 | 低风险 | 允许执行，执行后报告 | `scp` 单文件, `nginx reload`, 重生成 HTML |
| L2 | 中风险 | 需用户确认一次 | `systemctl restart ai-news`, 批量 scp 3个以上 |
| L3 | 高风险 | 逐条确认 | `rm`, `chmod -R`, 改 Nginx/systemd 配置, 回滚 |
| 🚫 | 绝对禁止 | 任何情况不自动执行 | `rm -rf /`, 删 data/ 目录, 未备份的 DB 操作 |

---

## 6. 部署基线

| 项目 | 值 |
|------|-----|
| 服务器 | `admin@121.43.80.221` |
| 项目路径 | `/home/admin/app` |
| Python | `/home/admin/app/.venv/bin/python` |
| 标准入口 | 本地 Git Bash / VS Code 终端 |
| 不使用 | `uv run python`、`ai-server` alias |
| 不优化 | `known_hosts` 中文路径警告，除非阻塞部署 |

---

## 7. 执行原则

1. **触发词驱动**：用户说触发词，按对应流程执行，不自由发挥
2. **固定脚本优先**：能用 `scripts/` 不动手拼命令
3. **缺口先补脚本**：没有脚本覆盖的场景，先说明缺口，再补脚本
4. **输出精简**：只保留状态（PASS/FAIL）、关键证据、下一步
5. **不连续尝试**：失败 ≤ 2 次就停，交给 server_debugger 诊断
6. **不临时扩展**：用户确认 L2 操作后，只执行确认范围内的命令
7. **服务器无 uv**：服务器运行统一使用 `.venv/bin/python`，本地开发可以用 uv
