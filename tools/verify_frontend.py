"""前端一键验证：生成页面、运行测试、检查路由与开发服务器。"""

from __future__ import annotations

import argparse
from collections import Counter
from html.parser import HTMLParser
import os
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports"
DEFAULT_PORT = int(os.environ.get("VERIFY_PORT", "8765"))
CORE_ROUTES = [
    "/", "/library", "/timeline", "/events", "/reports", "/research",
    "/my", "/graph", "/graph3d", "/entity/openai",
]
FORBIDDEN_SYNC_CLAIMS = ("已同步账号", "已云端同步", "跨设备已同步")


class IdCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.ids.extend(value for key, value in attrs if key == "id" and value)


def section(title: str) -> None:
    print(f"\n== {title} ==", flush=True)


def generate_pages() -> list[Path]:
    """使用生产生成器重建所有可访问的静态页面。"""
    sys.path.insert(0, str(ROOT))
    from src.frontend.dashboard import generate_dashboard
    from src.frontend.entity_page import generate_entity_shell
    from src.frontend.events_page import generate_events_page
    from src.frontend.kg_3d import generate_3d_html
    from src.frontend.kg_d3 import generate_html
    from src.frontend.library import generate_library
    from src.frontend.my_page import generate_my_page
    from src.frontend.reports_page import generate_reports_page
    from src.research import generate_research_page
    from src.timeline import generate_timeline

    generators: list[tuple[str, Callable[[], Path]]] = [
        ("今日", lambda: generate_dashboard(REPORTS_DIR)),
        ("专题", lambda: generate_library(REPORTS_DIR)),
        ("行业时间线", lambda: generate_timeline(REPORTS_DIR)),
        ("里程碑事件", lambda: generate_events_page(REPORTS_DIR)),
        ("研究报告", lambda: generate_reports_page(REPORTS_DIR)),
        ("研究助手", lambda: generate_research_page(REPORTS_DIR)),
        ("我的", lambda: generate_my_page(REPORTS_DIR)),
        ("实体详情", generate_entity_shell),
        ("知识图谱 2D", lambda: generate_html(output_dir=REPORTS_DIR)),
        ("知识图谱 3D", lambda: generate_3d_html(output_dir=REPORTS_DIR)),
    ]

    generated: list[Path] = []
    for name, generator in generators:
        path = Path(generator())
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"{name} 生成失败：{path}")
        generated.append(path)
        print(f"[生成] {name}: {path.relative_to(ROOT)}")
    return generated


def audit_generated_pages(pages: list[Path]) -> None:
    """执行无需浏览器即可可靠判断的 HTML 验收规则。"""
    for page in pages:
        html = page.read_text(encoding="utf-8")
        parser = IdCollector()
        parser.feed(html)
        duplicates = sorted(key for key, count in Counter(parser.ids).items() if count > 1)
        if duplicates:
            raise RuntimeError(f"{page.name} 包含重复 ID：{', '.join(duplicates)}")
        claims = [claim for claim in FORBIDDEN_SYNC_CLAIMS if claim in html]
        if claims:
            raise RuntimeError(f"{page.name} 包含虚假同步文案：{', '.join(claims)}")
        print(f"[HTML] {page.relative_to(ROOT)}: ID 与同步文案通过")


def run_tests(mode: str) -> None:
    """开发模式跑前端相关测试；合并和发布模式跑完整测试。"""
    targets = ["tests/test_frontend.py", "tests/test_frontend_components.py"] if mode == "dev" else []
    result = subprocess.run(
        [sys.executable, "-m", "pytest", *targets, "-q"], cwd=ROOT, check=False
    )
    if result.returncode:
        raise RuntimeError(f"测试失败，退出码 {result.returncode}")


def check_asgi_routes(routes: list[str]) -> None:
    """不依赖外部服务进程，直接验证 FastAPI 路由与静态文件。"""
    sys.path.insert(0, str(ROOT))
    from fastapi.testclient import TestClient
    from src.api.api import app

    routes = [*routes, "/api/health"]
    with TestClient(app) as client:
        for route in routes:
            response = client.get(route)
            if response.status_code != 200:
                raise RuntimeError(f"路由 {route} 返回 {response.status_code}")
            print(f"[路由] {route}: 200")


def http_status(url: str, timeout: float = 1.0) -> int | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return None


def run_browser_audit(base_url: str, routes: list[str]) -> None:
    """用真实 Chromium 收集控制台错误、检查溢出并保存截图。"""
    npx = shutil.which("npx")
    if not npx:
        raise RuntimeError("未找到 npx，无法运行 Playwright 浏览器验收")
    output = ROOT / "output" / "playwright"
    output.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({
        "FRONTEND_BASE_URL": base_url,
        "FRONTEND_ROUTES": json.dumps(routes),
        "FRONTEND_OUTPUT_DIR": str(output),
    })
    result = subprocess.run(
        [npx, "playwright", "test", "tools/browser_audit.spec.js", "--reporter=line"],
        cwd=ROOT, env=env, check=False,
    )
    if result.returncode:
        raise RuntimeError(f"Playwright 浏览器验收失败，退出码 {result.returncode}")
    print(f"[浏览器] 控制台、横向溢出与截图通过：{output.relative_to(ROOT)}")


def check_dev_server(port: int, routes: list[str], browser_audit: bool) -> bool:
    """检查现有服务；若未启动，则临时启动并验证后自动关闭。"""
    base_url = f"http://127.0.0.1:{port}"
    process: subprocess.Popen[bytes] | None = None
    temporary = http_status(f"{base_url}/api/health") is None

    try:
        if temporary:
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
                    raise RuntimeError("临时开发服务器启动失败，端口可能已被占用")
                if http_status(f"{base_url}/api/health") == 200:
                    break
                time.sleep(0.2)
            else:
                raise RuntimeError("临时开发服务器在 10 秒内未就绪")

        for route in (*routes, "/api/health"):
            status = http_status(f"{base_url}{route}", timeout=3)
            if status != 200:
                raise RuntimeError(f"开发服务器路由 {route} 返回 {status}")
            print(f"[HTTP] {base_url}{route}: 200")
        if browser_audit:
            run_browser_audit(base_url, routes)
        return temporary
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-tests", action="store_true", help="跳过 pytest")
    parser.add_argument("--skip-server", action="store_true", help="跳过 HTTP 服务检查")
    parser.add_argument("--skip-browser", action="store_true", help="跳过 Playwright 控制台/溢出/截图检查")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="开发服务器端口")
    parser.add_argument("--mode", choices=("dev", "merge", "release"), default="merge",
                        help="dev=相关测试；merge=全量；release=全量并要求视觉工具链")
    parser.add_argument("--routes", nargs="+", help="仅验证指定路由，适合单页开发")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    routes = args.routes or (["/"] if args.mode == "dev" else CORE_ROUTES)
    started = time.monotonic()
    try:
        section("1/4 生成页面")
        pages = generate_pages()

        section("HTML 机器验收")
        audit_generated_pages(pages)

        section("2/4 运行测试")
        if args.skip_tests:
            print("[跳过] pytest")
        else:
            run_tests(args.mode)

        section("3/4 检查应用路由")
        check_asgi_routes(routes)

        section("4/4 检查开发服务器")
        temporary = False
        if args.skip_server:
            print("[跳过] HTTP 服务检查")
        else:
            temporary = check_dev_server(args.port, routes, not args.skip_browser)
            print("[说明] 临时服务验证完成并已关闭" if temporary else "[说明] 已复用正在运行的开发服务器")

        duration = time.monotonic() - started
        base_url = f"http://127.0.0.1:{args.port}"
        section("验证通过")
        print(f"页面：{len(pages)} 个；耗时：{duration:.1f} 秒")
        print(f"首页：{base_url}/")
        print(f"我的：{base_url}/my")
        print("已检查路由：" + ", ".join(f"{base_url}{route}" for route in routes))
        if args.mode == "release":
            vision = Path.home() / ".codex" / "skills" / "vision" / "vision.py"
            if not vision.is_file():
                raise RuntimeError(f"发布验证要求 vision skill：{vision}")
            print(f"视觉工具：{vision}")
        if temporary and not args.skip_server:
            print("启动服务：uv run uvicorn src.api.api:app --reload --port 8765")
        return 0
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(f"\n[失败] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
