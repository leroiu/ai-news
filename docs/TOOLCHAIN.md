# 工具链基线

本项目以可复现构建为优先目标。版本升级必须同时更新清单、锁文件、CI 和验证证据。

## 当前基线

| 层级 | 固定版本 | 说明 |
|---|---:|---|
| Python | 3.13.14 | 生产与本地默认版本 |
| Python 兼容性 | 3.14.6 | CI 非阻断兼容性任务 |
| uv | 0.11.32 | `pyproject.toml`、CI 与容器统一 |
| Node.js | 24.17.0 | 与已审查性能基线绑定 |
| npm | 11.16.0 | `package.json` 与 CI 统一 |
| Playwright | 1.61.1 | 与已审查性能基线绑定 |
| Chromium | 149.0.7827.55 | 由 Playwright 1.61.1 管理 |
| FastAPI | 0.139.2 | Web API |
| Uvicorn | 0.51.0 | ASGI Server |
| OpenAI SDK | 2.46.0 | OpenAI-compatible provider 客户端 |
| PyJWT | 2.13.0 | JWT 编解码；替代 python-jose |
| Ruff | 0.15.22 | 首期阻断确定性运行错误 |
| pip-audit | 2.10.1 | Python 依赖漏洞审计 |

精确依赖解析以 `uv.lock` 和 `package-lock.json` 为准。

## 常用命令

```powershell
uv sync --frozen --all-groups
npm ci
uv run --frozen ruff check .
uv run --frozen pip-audit --local
uv run --frozen python tools/test_router.py run
uv run --frozen python tools/quality_gate.py checkpoint
```

浏览器运行时按锁定的 Playwright 安装：

```powershell
npx playwright install chromium
```

下载受限时，本地审计可以临时指定已安装的 Chromium 浏览器；CI 不设置此变量，仍使用 Playwright 管理的版本：

```powershell
$env:PLAYWRIGHT_EXECUTABLE_PATH = "C:\Program Files\Google\Chrome\Application\chrome.exe"
```

## 升级策略

- Dependabot 每周检查 uv、npm、GitHub Actions 和 Docker，默认等待 7 天。
- 生产 Python 保持在 3.13 补丁线；3.14 先作为非阻断兼容性信号。
- GitHub Actions 必须固定到完整提交 SHA，并在行尾记录对应 release 标签。
- Python 和 Node 依赖变更必须提交对应锁文件，CI 一律使用冻结安装。
- Playwright 或 Node 变化会使性能环境指纹变化，必须重新采样并人工复核性能基线。
- Ruff 当前只阻断 `E9`、`F63`、`F7`、`F82`；扩大规则集前先分批清理存量问题。

Node 24.18.0、Playwright 1.62.0 与 Chromium 151.0.7922.34 已完成兼容性采样，但当前工作区含独立前端改动，候选基线无法归因，因此暂不进入阻断 CI。应在干净工作树中单独升级并重建性能基线。
