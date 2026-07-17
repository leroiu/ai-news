# AI News 测试体系

这套测试体系面向可连续工作数小时的开发 Agent。目标不是调度 Agent，而是持续提供确定、可重复、可审计的完成证据。

## 标准入口

```powershell
uv run python tools/quality_gate.py baseline
uv run python tools/quality_gate.py checkpoint
```

也可以使用：

```powershell
make quality-baseline
make quality-checkpoint
```

- `baseline`：任务开始前记录当前分支的真实全量状态。
- `checkpoint`：每个可验收阶段完成后重复运行。
- 两个入口当前都执行全量 `tests/`，默认超时 900 秒，可用 `--timeout` 调整。
- 任一非零结果都不能作为任务完成证据。

## 第二阶段隔离保证

`tests/conftest.py` 为每个测试建立独立临时运行目录，并提供以下保证：

- 删除真实 AI 服务所需的 API Key，并 stub `call_ai`、`embed_texts`。
- 阻止所有非 loopback socket 连接。
- 将 SQLite、处理缓存、候选概念池、抓取健康状态等重定向到 pytest 临时目录。
- 将知识卡读取重定向到 4 张受控 YAML fixture。
- 将知识卡写入、报告页面和前端构建输出重定向到临时目录。
- 自动初始化临时数据库和最小静态页面，不依赖项目上一次运行留下的产物。

测试如果确实需要访问外部服务，应单独设计显式集成测试入口，不能绕过全局隔离层。

## 分支覆盖率门禁

门禁使用 `coverage run --branch` 执行全量测试，覆盖：

```text
src,pipeline,pipeline_stages,pipeline_utils,collector
```

每次运行会生成：

- `.coverage`
- `coverage.json`
- `coverage.xml`
- `coverage-report.txt`

基线保存在 `.quality/coverage-baseline.json`。当前初始基线来自真实全量运行：

```text
56.428% statements + branches
694 / 1568 branches covered
minimum_percent = 56.42
tolerance = 0.1
```

该基线包含 `src/` 以及实际导入并出现在 `coverage.json` 中的
`pipeline.py`、`pipeline_stages.py`、`pipeline_utils.py`、`collector.py`。
第一版 57.55% 基线没有真正计入这四个顶层模块，已由独立 Reviewer 判定无效并被此基线取代。

普通 `baseline` 和 `checkpoint` 只读取基线，不会自动创建、覆盖或降低基线。实际覆盖率低于 `minimum_percent - tolerance` 时，结果为 `coverage_regression`，退出码为 1。

如果确需调整基线，必须基于完整门禁证据人工修改，并在交接中说明原因。禁止为了让失败通过而降低基线。

## 工作区污染保护

门禁同时比较测试前后的两类指纹：

1. Git tracked diff、状态项和未跟踪文件内容。
2. `data/`、`reports/`、`cache/`、`logs/` 的完整内容，包括 Git 忽略文件。

任务开始前已经存在的脏工作树不会被误判；但测试期间修改已有脏文件、生成新文件、删除文件，或改变受保护运行目录，都会得到 `git_pollution`。

门禁只报告污染，不自动还原文件，避免覆盖用户或并行 Agent 的工作。

## 退出码

| 退出码 | 结果 | 含义 |
|---:|---|---|
| 0 | `pass` | 测试、覆盖率和污染检查全部通过 |
| 1 | `test_failure` / `coverage_regression` | 测试失败或覆盖率低于基线 |
| 2 | `infra_error` | Python、pytest、coverage、Git 或证据生成环境不可用 |
| 3 | `timeout` | 测试超时且进程树已确认清理 |
| 4 | `git_pollution` | 测试期间工作区或受保护运行目录发生变化 |

## 证据目录

每次门禁写入独立目录：

```text
output/quality-gate/<run-id>-<profile>/
├── metadata.json
├── summary.json
├── commands.txt
├── command-result.json
├── stdout.log
├── stderr.log
├── coverage.json
├── coverage.xml
├── coverage-report.txt
├── git-status-before.txt
└── git-status-after.txt
```

交接和审查必须引用 `summary.json` 及对应原始日志，不能只写“测试已通过”。`summary.json` 包含：

- 测试计数和失败指纹
- Git 内容指纹及状态差异
- 受保护运行目录前后指纹
- 分支覆盖率摘要和采用的基线
- Python、Git HEAD、耗时与证据路径

## 长程 Agent 工作循环

1. 接管任务后先运行 `baseline`。
2. 记录既有失败、覆盖率和证据目录，不把历史问题归因于当前修改。
3. 每完成一个可独立验收的阶段，运行相关专项测试，再运行 `checkpoint`。
4. 修复失败时引用失败指纹和新证据，不盲目重复同一动作。
5. 同一故障连续两次修复仍无新证据时暂停并升级。
6. 最终交付必须引用最近一次完整、通过的门禁证据。

## 统一完成检查与验收状态机

业务任务准备提交验收时，使用统一入口运行完整本地 DoD：

```powershell
uv run python tools/acceptance_gate.py verify `
  --task .workspace/tasks/<TASK-ID>/task.json

# 或
make acceptance-verify TASK=".workspace/tasks/<TASK-ID>/task.json"
```

Task Contract 必须显式包含：

- `issue_status = "ready"`
- `execution_gate = "allowed"`
- `target_environment = "local"` 或 `"dev"`
- 非空、可逐项判定 PASS/FAIL 的 `acceptance_criteria`
- `max_iteration_rounds`，默认和推荐值为 2

`draft`、`blocked`、`completed`、执行门未开放或缺少可测试验收标准的任务不会启动任何子门禁。第二轮仍失败后不得继续盲目重试：

```powershell
uv run python tools/acceptance_gate.py verify --task <task.json> --round 2
```

统一入口固定顺序运行：

1. `quality_gate.py checkpoint`
2. `browser_gate.py --profile core`
3. `accessibility_gate.py check`
4. `performance_gate.py check`

门禁串行执行，避免争用 Python 环境、端口或 Chromium 资源。即使某一项失败，其余独立门禁仍继续运行并保留证据。统一入口会重新解释每个 `summary.json`：

- quality 必须为完整 checkpoint，pytest、coverage、Git 和运行目录污染均通过；
- browser 必须是 20 个 core 案例、60 张截图和 loopback-only 网络策略；
- accessibility 必须是 30 个案例、0 infrastructure failure、0 new violation；
- performance 必须是 30 个页面样本、100 个 API 样本、0 错误、0预算违规。

因此，伪造退出码 0 但修改 summary 内容不能通过。

四项全部通过时状态仅为 `awaiting_review`，不是 `accepted`。输出会给出本次 `run_id` 和 `summary_sha256`。独立 Reviewer 必须输出绑定报告：

```json
{
  "task_id": "<TASK-ID>",
  "acceptance_run_id": "<verify run_id>",
  "acceptance_summary_sha256": "<verify summary SHA-256>",
  "reviewed_at": "<带时区 ISO 时间>",
  "reviewer_role": "independent Reviewer",
  "verdict": "PASS",
  "acceptance_criteria": [
    {
      "criterion": "<与 Task Contract 完全一致的验收标准>",
      "result": "PASS",
      "evidence": "<独立复验命令或证据>"
    }
  ],
  "findings": [],
  "blocking_issues": [],
  "residual_risks": []
}
```

Reviewer 完成后执行：

```powershell
uv run python tools/acceptance_gate.py finalize `
  --run-dir output/acceptance-gate/<run-id> `
  --review .workspace/tasks/<TASK-ID>/quality-gate.json

# 或
make acceptance-finalize RUN_DIR="output/acceptance-gate/<run-id>" REVIEW="<quality-gate.json>"
```

`finalize` 会重新校验：

- Git HEAD、tracked diff 和未跟踪实现文件内容与 verify 完成时一致；只允许新增本次精确 Reviewer 报告路径；
- Task Contract 内容和 SHA-256 未变化；
- 统一 `summary.json` 未变化；
- 四个子门禁 `summary.json` 的路径、SHA-256 和语义仍有效；
- 每个 step 完整 evidence 目录的文件集合、大小和 SHA-256 均未发生新增、删除或内容变化；
- Reviewer 绑定同一 task、run 和 summary SHA；
- Reviewer 时间晚于 verify，角色是 independent Reviewer；
- 每条 acceptance criterion 均有 PASS 和非空证据；
- 不存在 open、unresolved、blocked 或 blocking finding。

成功后只在本次目录写入 `accepted.json`，不会自动修改 Task Contract、commit、push、PR、部署或合并。`accepted` 只证明绑定证据覆盖的本地 DoD。

证据目录：

```text
output/acceptance-gate/<run-id>/
├── summary.json
├── accepted.json                 # finalize 成功后才存在
└── steps/
    ├── quality/
    ├── browser/
    ├── accessibility/
    └── performance/
```

每个 step 保存命令、退出码、stdout/stderr，并把对应子门禁的完整输出放在自己的 `evidence/` 下。统一 summary 会为其中每个文件记录相对路径、大小和 SHA-256。

## 变更感知增量测试

完整 checkpoint 会记录 coverage 的逐测试动态上下文。阶段开始或完整 checkpoint 通过后创建快照：

```powershell
uv run python tools/test_router.py snapshot
```

修改代码后先查看计划：

```powershell
uv run python tools/test_router.py plan
```

执行相关测试：

```powershell
uv run python tools/test_router.py run
```

也可以使用 `make test-snapshot`、`make test-plan` 和 `make test-changed`。

路由规则：

- 测试文件变化时直接运行该测试文件。
- Python 源码变化时，优先选择完整 coverage 中实际执行该源码的测试文件。
- `src/engine/<name>.py` 还会加入同名 `tests/test_<name>.py` 作为约定式保护。
- 仅文档变化时明确返回 `none`，不启动 pytest。
- `conftest.py`、依赖/配置、门禁工具、模板/提示词、未知映射或影响面过大时自动回退全量 `tests/`。
- coverage 证据缺失或内容与快照不一致时自动回退全量测试。

增量执行会保存到 `output/test-router/<run-id>/`，包括计划、命令、stdout/stderr、Git 内容指纹和 `data/reports/cache/logs` 指纹。

增量测试只用于开发中的快速反馈，不能作为最终完成证据。每个阶段结束仍必须运行 `quality_gate.py checkpoint`；checkpoint 通过后应刷新快照，避免后续计划持续包含已经验收的历史变化。

## 隔离浏览器门禁

核心前端门禁使用确定性 SQLite、固定文章/实体/报告和真实 Chromium，不复用项目 `data/` 或 `reports/`：

```powershell
uv run python tools/browser_gate.py --profile core
# 或
make browser-check
```

默认核心路由覆盖首页、专题、时间线、事件、报告、研究、我的、实体详情、文章详情和报告阅读器。每个路由均验证：

- 桌面端 `1440x1000` 与移动端 `390x844`
- 页面 HTTP 200
- 无未允许的 console error、pageerror、失败请求和异常 HTTP 子资源
- 无横向溢出
- 主体不是空白页
- 1.2 秒稳定期后不再显示加载态
- 默认拒绝所有非应用 origin 的 HTTP(S) 请求和 WebSocket 连接；WebSocket 不能绕过网络策略

每个案例保存三张截图：全页、首屏和滚动到底部后的视口。证据目录：

```text
output/browser-gate/<run-id>/
├── fixture.json
├── summary.json
├── server.stdout.log
├── server.stderr.log
├── browser.stdout.log
├── browser.stderr.log
├── runtime/
│   ├── data/platform.db
│   └── reports/
└── browser/
    ├── audit.json
    ├── cases/*.json
    └── screenshots/*-{full,top,bottom}.png
```

门禁前后会对项目 `data/`、`reports/`、`cache/`、`logs/` 做完整内容指纹；任何变化都会令结果失败。临时夹具只写入本次唯一的 `output/browser-gate/<run-id>/runtime/`。

只验证夹具构建和静态 HTML 审计：

```powershell
uv run python tools/browser_gate.py --prepare-only
```

2D/3D 图谱当前分别依赖 `d3js.org` 和 `unpkg.com`，因此不进入默认离线核心门禁。需要显式扩展检查时运行：

```powershell
uv run python tools/browser_gate.py --profile extended
```

扩展模式只允许上述精确 CDN origin，并在逐案例证据中记录每个外部请求。当前图谱页面还会被静态审计发现重复的导航控件 ID；在产品页面修复前，扩展门禁应保持失败，不能加入忽略列表。

浏览器结构门禁不等于视觉审美验收。Agent 在前端改动后仍应查看本次真实截图；配置视觉模型密钥时可继续使用 `tools/capture_frontend.py` 的视觉分析能力。

## 可访问性回归门禁

可访问性门禁复用同一套隔离数据库、静态页面和临时 FastAPI 服务：

```powershell
uv run python tools/accessibility_gate.py check
# 或
make accessibility-check
```

矩阵为 10 条核心路由 × `desktop-dark`、`desktop-light`、`mobile-dark`，共 30 个真实 Chromium 案例。当前规则检查：

- `html lang`
- 非空 `document title`
- 单一 `h1` 和单一 `main`
- 带名称的主导航和唯一 `aria-current="page"`
- 重复 ID
- skip-link、目标和首个 Tab 焦点
- 可见控件、链接和图片的可访问名称
- 非原生 `onclick` 必须同时具备 `role=button/link`、`tabindex>=0`，以及明确覆盖 Enter/Space 的键盘处理
- 正数 tabindex

这是一套轻量回归规则，不等同于完整 WCAG 认证，也不替代 axe-core 或人工辅助技术测试。

既有产品违规保存在 `.quality/accessibility-baseline.json`。普通 `check` 只读取基线：

- 与基线相同的违规记为 `known`，允许通过。
- 新增指纹记为 `new`，门禁失败。
- 已消失的指纹记为 `resolved`，门禁通过并在证据中保留改进记录。
- 规则版本、路由矩阵或 case 矩阵变化时，旧基线无效，必须人工审查后显式重建。

首次建立或经审查替换基线：

```powershell
uv run python tools/accessibility_gate.py baseline
uv run python tools/accessibility_gate.py baseline --force
```

普通运行不会自动新增、覆盖或放宽基线。每次证据位于：

```text
output/accessibility-gate/<run-id>-<command>/
├── summary.json
├── audit.stdout.log
├── audit.stderr.log
├── runtime/
└── audit/
    ├── audit.json
    └── cases/*.json
```

`summary.json` 同时记录 known/new/resolved、浏览器基础设施结果，以及 `data/reports/cache/logs` 前后内容指纹。

## 隔离性能预算门禁

性能门禁复用确定性夹具，但将页面阶段和 API 阶段放在两个独立 FastAPI 进程中，避免两类采样共用 `120/min` 限流桶而产生伪 429：

```powershell
uv run python tools/performance_gate.py check
# 或
make performance-check
```

页面矩阵为 10 条核心路由，每条先执行 1 次不计入性能聚合、但保留完整网络/状态证据的预热，再执行 3 次新 browser context、禁用缓存的冷缓存采样。任何预热错误同样会令门禁失败。门禁记录并校验：

- TTFB、DOMContentLoaded、load、FCP、LCP
- Web Vitals session-window CLS
- long task 数量、总时长和最大单任务时长
- 请求数、CDP encoded bytes、响应 decoded bytes
- DOM 节点数和正文长度
- 所有请求必须为 loopback GET；外部 HTTP、WebSocket、失败请求和异常响应均失败

API 阶段覆盖 5 个只读端点，每个预热 1 次、顺序采样 20 次，共 100 个正式样本；记录 p50、p95、max、响应体积和错误数。独立 API 服务共接收 105 次请求，不超过夹具的限流上限。

首次建立或经审查替换基线：

```powershell
uv run python tools/performance_gate.py baseline
uv run python tools/performance_gate.py baseline --force
# 或
make performance-baseline
```

普通 `check` 不会自动创建、覆盖或放宽 `.quality/performance-baseline.json`。基线保存观测值、预算公式参数、绝对安全上限、Node/Playwright/Chromium 版本、原始 audit 路径及其 SHA-256；加载时会重新验证原始 audit 并重建全部预算。手工调大 limit、同时修改 observed/limit、修改策略、改变矩阵、替换证据或漂移测量环境都会失败。

页面时间指标使用本地多样本 p50，API 延迟使用 20 样本 p95。请求数不允许增长；体积和 DOM 只保留较小噪声余量。`networkidle` 仅用于等待页面稳定，其约 500ms 静默窗口对应的 wall time 不进入预算。

当前基线明确登记一项历史债务：`/timeline` 的 CLS 为 `0.374`，高于 `0.1` 质量目标。P6 不修改业务页面，因此基线允许它在 `0.5` 灾难性安全上限内最多增加 `0.02` 或 5%；该记录不能静默删除或放宽。

每次证据位于：

```text
output/performance-gate/<run-id>-<command>/
├── summary.json
├── audit/audit.json
├── runtime/
├── pages/
│   ├── server.*.log
│   ├── audit.*.log
│   └── audit/audit.json
└── apis/
    ├── server.*.log
    ├── audit.*.log
    └── audit/audit.json
```

`summary.json` 同时记录两阶段退出码、预算违规和 `data/reports/cache/logs` 前后内容指纹。本门禁是单用户本地回归测试，不替代 `docs/PERFORMANCE_TEST_PLAN.md` 中面向获批目标服务器的 k6 并发、峰值和耐久测试。

## CI 质量工作流

`.github/workflows/quality-gate.yml` 在 PR、master 分支的非纯采集数据 push 和手动触发时运行。工作流使用只读仓库权限、分支级并发取消和 45 分钟总超时。当前 runner 固定为 `windows-latest`，Node 固定为 `24.17.0`，因为已审查的 P6 性能基线绑定 `win32-x64 / Node v24.17.0 / Chromium 149.0.7827.55`；Linux runner 必须建立独立性能基线后才能启用。工作流固定执行：

1. 从 `uv.lock` 和 `package-lock.json` 冻结恢复依赖；
2. 安装固定版本 Chromium；
3. 串行运行 quality、browser、accessibility、performance；
4. 无论成功或失败，都上传本次 `output/` 完整证据，artifact 名绑定 run id 与 attempt。

`tests/test_ci_workflow.py` 在本地解析 YAML 并保护触发器、权限、工具版本、冻结参数、门禁顺序和证据上传契约。P5/P6 的原始 accessibility/performance audit 以仓库相对路径和原 SHA-256 暴露为可提交证据，避免干净 checkout 依赖本机绝对 `output/` 路径；除这两个内容寻址文件外，其他 `output/` 仍被忽略。测试只能证明工作流定义正确；实际 GitHub runner 结果仍需未来 push/PR 后的 Actions 证据。

## 部署后只读门禁

部署系统必须为 `/api/health` 注入非敏感标识：

```text
AI_NEWS_ENVIRONMENT=dev
AI_NEWS_RELEASE_SHA=<完整 Git commit SHA>
```

获准的 dev 部署完成后运行：

```powershell
uv run python tools/postdeploy_gate.py check `
  --base-url "https://dev.example.com" `
  --environment dev `
  --allowed-host "dev.example.com" `
  --expected-environment dev `
  --expected-release "<预期 Git SHA>"

# 或
make postdeploy-check BASE_URL="https://dev.example.com" ENVIRONMENT="dev" ALLOWED_HOST="dev.example.com" RELEASE="<预期 Git SHA>"
```

门禁只发送 GET，不读取代理环境变量、不跟随重定向，并启用 TLS 校验和 2 MiB 响应上限。`local` 只接受 localhost/loopback；`dev` 必须与调用方显式给出的精确 `host[:port]` 白名单相同。stage、production、URL 凭据、带业务 path/query/fragment 的 base URL 会在发出请求前被拒绝。

就绪阶段最多重试 6 次；health 必须同时匹配 `status=ok`、环境、版本和 DB 证据。随后固定检查 7 个核心页面与 3 个额外只读 API；所有响应必须为 HTTP 200、类型/JSON 结构正确，并包含安全响应头。证据位于：

```text
output/postdeploy-gate/<run-id>-check/summary.json
```

summary 不保存响应正文，只保存字节数、SHA-256、有限响应头、时延、逐项错误和稳定失败指纹。真实 dev 目标与白名单必须由用户或部署系统明确提供；本工具不会部署、重启、SSH、回滚或访问 production。

当 Task Contract 的 `target_environment` 为 `dev` 时，还必须提供：

```json
{
  "postdeploy": {
    "base_url": "https://dev.example.com",
    "allowed_host": "dev.example.com",
    "expected_environment": "dev",
    "expected_release": "<预期 Git SHA>"
  }
}
```

统一 acceptance gate 会把 postdeploy 固定追加在四个本地门禁之后；缺少任一字段时 issue gate 直接阻止执行。

## 环境恢复

项目依赖必须从 `uv.lock` 恢复：

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache-test"
uv sync
```

沙箱无法启动中文路径下的解释器，只能证明沙箱执行受限，不能据此判断宿主机 Python 已卸载。必须在获得授权后通过实际 `python --version`、依赖导入和最小测试验证环境。

不要并行执行多个会同步同一项目环境的 `uv run`、`uv sync` 或 `uv venv` 命令。它们会争用 `.venv`，可能导致环境被重建或部分删除。并行测试应共享一个已经稳定的解释器，或为每个执行器分配独立的 `UV_PROJECT_ENVIRONMENT`。

如果工作区被 Windows 与 Unix/WSL 工具同时访问，还要检查 `.venv/pyvenv.cfg`。Windows 项目环境应指向 Windows Python 路径；如果出现 `home = /usr/bin` 和 `bin/`、`lib64`，说明另一个环境同步层覆盖了 `.venv`，不能据此断言宿主机 Python 不存在。可为验证任务使用独立环境：

```powershell
$env:UV_PROJECT_ENVIRONMENT = "C:\tmp\ai-news-test-venv"
uv sync --python "C:\Users\<user>\AppData\Local\Programs\Python\Python313\python.exe"
& "$env:UV_PROJECT_ENVIRONMENT\Scripts\python.exe" tools\quality_gate.py checkpoint
```

Windows 进程树清理有一项显式宿主机测试：

```powershell
$env:AI_NEWS_RUN_PROCESS_TREE_TEST = "1"
uv run pytest tests/test_quality_gate.py -q
```

该测试会启动父子 Python 进程，触发超时，并验证整个子进程树被清理。

## 测试卫生

`PytestUnraisableExceptionWarning` 已被配置为全局测试错误。测试如果创建了未 await 的协程、对象析构异常或其他不可回收异常，将直接导致 pytest 失败，不能再以运行结束后的非阻塞警告形式出现。

测试异步编排时应 mock 网络边界函数，例如 `_fetch_one` 或具体插件客户端，不能替换全局 `asyncio.gather` 后直接丢弃传入协程。

## 已知后续项

- 自动视觉模型判分、完整 WCAG/辅助技术验证、真实远端 CI runner 证据，以及获批 dev 部署的真实 postdeploy 运行属于后续项。
