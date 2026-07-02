"""用真实 Chromium 截取桌面端与移动端页面，统一写入 output/playwright。"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output" / "playwright"
VISION_SCRIPT = Path.home() / ".codex" / "skills" / "vision" / "vision.py"
VISION_PROMPT = "分析页面布局问题：对齐、间距、溢出、留白、截断、响应式异常和视觉层级。列出具体问题。"
CORE_ROUTES = ["/", "/library", "/timeline", "/events", "/reports", "/research", "/my"]


def http_status(url: str, timeout: float = 1.0) -> int | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return None


def start_server(base_url: str, port: int) -> subprocess.Popen[bytes] | None:
    if http_status(f"{base_url}/api/health") == 200:
        return None
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.api.api:app", "--host",
         "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags,
    )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("开发服务器启动失败，端口可能已被占用")
        if http_status(f"{base_url}/api/health") == 200:
            return process
        time.sleep(0.2)
    process.terminate()
    raise RuntimeError("开发服务器在 10 秒内未就绪")


def capture(npx: str, url: str, output: Path, mobile: bool) -> None:
    command = [
        npx, "playwright", "screenshot", "--browser", "chromium",
        "--full-page", "--wait-for-timeout", "2000",
    ]
    if mobile:
        command.extend(["--device", "iPhone 13"])
    else:
        command.extend(["--viewport-size", "1440,1000"])
    command.extend([url, str(output)])
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode:
        raise RuntimeError(f"截图失败：{url}")
    print(f"[截图] {output.relative_to(ROOT)}")


def analyze_screenshots(screenshots: list[Path]) -> bool:
    """调用 vision skill 分析截图；未配置密钥时明确跳过。"""
    load_dotenv(ROOT / ".env")
    providers = {
        "doubao": "DOUBAO_API_KEY",
        "qwen": "DASHSCOPE_API_KEY",
        "openai": "OPENAI_API_KEY",
    }
    selected = os.environ.get("VISION_PROVIDER", "").lower()
    if selected and selected not in providers:
        raise RuntimeError(f"VISION_PROVIDER 无效：{selected}")
    provider = selected or next(
        (name for name, key in providers.items() if os.environ.get(key)), ""
    )
    if not VISION_SCRIPT.is_file():
        print(f"[未分析] vision skill 不存在：{VISION_SCRIPT}")
        return False
    if not provider or not os.environ.get(providers[provider]):
        print("[未分析] 未配置 DOUBAO_API_KEY、DASHSCOPE_API_KEY 或 OPENAI_API_KEY")
        return False

    for screenshot in screenshots:
        result = subprocess.run(
            [sys.executable, str(VISION_SCRIPT), "--provider", provider,
             str(screenshot), VISION_PROMPT],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if result.returncode:
            raise RuntimeError(f"视觉分析失败：{screenshot.name}：{result.stderr.strip()}")
        report = screenshot.with_suffix(".analysis.txt")
        report.write_text(result.stdout.strip() + "\n", encoding="utf-8")
        print(f"[分析] {report.relative_to(ROOT)}")
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--routes", nargs="+", default=CORE_ROUTES,
                        help="默认截取全部核心页面；传入路由可做增量检查")
    parser.add_argument("--skip-analysis", action="store_true", help="仅截图，不调用 vision skill")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    npx = shutil.which("npx")
    if not npx:
        print("[失败] 未找到 npx，请先安装 Node.js/npm", file=sys.stderr)
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base_url = f"http://127.0.0.1:{args.port}"
    process: subprocess.Popen[bytes] | None = None
    screenshots: list[Path] = []
    try:
        process = start_server(base_url, args.port)
        for route in args.routes:
            slug = route.strip("/").replace("/", "-") or "home"
            desktop = OUTPUT_DIR / f"{slug}-desktop.png"
            mobile = OUTPUT_DIR / f"{slug}-mobile.png"
            capture(npx, f"{base_url}{route}", desktop, False)
            capture(npx, f"{base_url}{route}", mobile, True)
            screenshots.extend((desktop, mobile))
        if args.skip_analysis:
            print("[跳过] vision skill 分析")
        else:
            analyze_screenshots(screenshots)
        print(f"截图目录：{OUTPUT_DIR}")
        return 0
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(f"[失败] {error}", file=sys.stderr)
        return 1
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
