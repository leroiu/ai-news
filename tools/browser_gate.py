"""隔离运行真实 Chromium，生成前端结构化证据和响应式截图。"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_OUTPUT = ROOT / "output" / "browser-gate"
PROTECTED_RUNTIME_PATHS = ("data", "reports", "cache", "logs")
CORE_ROUTES = [
    "/",
    "/library",
    "/timeline",
    "/events",
    "/reports",
    "/research",
    "/my",
    "/entity/openai",
    "/article/fixture-article-1",
    "/report/2026-07-16.md",
]
EXTENDED_ROUTES = [*CORE_ROUTES, "/graph", "/graph3d"]
GRAPH_EXTERNAL_ORIGINS = [
    "https://d3js.org",
    "https://unpkg.com",
]
FIXED_BROWSER_TIME = "2026-07-16T12:00:00.000Z"
SECRET_ENV_NAMES = (
    "DEEPSEEK_API_KEY",
    "MOONSHOT_API_KEY",
    "AGNES_API_KEY",
    "SILICONFLOW_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DOUBAO_API_KEY",
    "DASHSCOPE_API_KEY",
)


class IdCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.ids.extend(value for key, value in attrs if key == "id" and value)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def protected_digest(root: Path = ROOT) -> tuple[str, dict[str, int]]:
    """对业务运行目录做内容指纹，检测门禁前后污染。"""
    digest = hashlib.sha256()
    counts: dict[str, int] = {}
    for relative_root in PROTECTED_RUNTIME_PATHS:
        directory = root / relative_root
        count = 0
        digest.update(f"{relative_root}\0".encode())
        if not directory.exists():
            digest.update(b"<missing>")
            counts[relative_root] = 0
            continue
        for path in sorted(directory.rglob("*"), key=lambda item: item.as_posix()):
            relative = path.relative_to(root).as_posix()
            digest.update(relative.encode("utf-8", "surrogatepass"))
            if path.is_file():
                count += 1
                digest.update(b"<file>")
                digest.update(hashlib.sha256(path.read_bytes()).digest())
            elif path.is_dir():
                digest.update(b"<dir>")
        counts[relative_root] = count
    return digest.hexdigest(), counts


def fixture_entities() -> list[dict]:
    return [
        {
            "id": "openai",
            "name": "OpenAI",
            "type": "company",
            "importance": 5,
            "summary": "构建通用人工智能模型与开发平台的研究公司。",
            "significance": "推动大模型产品化并形成广泛的开发者生态。",
            "release_date": "2015-12-11",
            "company": "OpenAI",
            "tags": ["AGI", "foundation-model"],
            "aliases": ["Open AI"],
            "timeline": [
                {"date": "2015-12", "event": "公司成立"},
                {"date": "2022-11", "event": "ChatGPT 发布"},
            ],
            "color": "#58a6ff",
        },
        {
            "id": "chatgpt",
            "name": "ChatGPT",
            "type": "product",
            "importance": 5,
            "summary": "面向大众的对话式 AI 产品。",
            "significance": "显著扩大了生成式 AI 的社会可见度。",
            "release_date": "2022-11-30",
            "company": "OpenAI",
            "tags": ["assistant", "chat"],
            "aliases": [],
            "timeline": [{"date": "2022-11", "event": "公开发布"}],
            "color": "#3fb950",
        },
        {
            "id": "gpt-4",
            "name": "GPT-4",
            "type": "model",
            "importance": 5,
            "summary": "支持复杂推理和多模态输入的大语言模型。",
            "significance": "提升了大模型在专业任务中的可用性。",
            "release_date": "2023-03-14",
            "company": "OpenAI",
            "tags": ["LLM", "multimodal"],
            "aliases": ["GPT4"],
            "timeline": [{"date": "2023-03", "event": "模型发布"}],
            "color": "#a371f7",
        },
        {
            "id": "transformer",
            "name": "Transformer",
            "type": "tech",
            "importance": 5,
            "summary": "基于注意力机制的序列建模架构。",
            "significance": "成为现代大语言模型的核心技术基础。",
            "release_date": "2017-06-12",
            "company": "Google",
            "tags": ["attention", "architecture"],
            "aliases": [],
            "timeline": [{"date": "2017-06", "event": "论文发表"}],
            "color": "#d29922",
        },
        {
            "id": "in-context-learning",
            "name": "In-context Learning",
            "type": "concept",
            "importance": 4,
            "summary": "模型通过提示中的示例临时学习任务模式。",
            "significance": "无需更新参数即可快速适配任务。",
            "release_date": "2020-05",
            "company": "",
            "tags": ["prompting", "learning"],
            "aliases": ["ICL"],
            "timeline": [],
            "color": "#f0883e",
        },
        {
            "id": "sam-altman",
            "name": "Sam Altman",
            "type": "person",
            "importance": 4,
            "summary": "OpenAI 联合创始人与首席执行官。",
            "significance": "参与推动生成式 AI 产品和产业发展。",
            "release_date": "",
            "company": "OpenAI",
            "tags": ["leadership"],
            "aliases": [],
            "timeline": [],
            "color": "#db61a2",
        },
        {
            "id": "chatgpt-launch",
            "name": "ChatGPT Launch",
            "type": "event",
            "importance": 5,
            "summary": "ChatGPT 面向公众发布。",
            "significance": "生成式 AI 进入大众应用阶段。",
            "release_date": "2022-11-30",
            "company": "OpenAI",
            "tags": ["milestone"],
            "aliases": [],
            "timeline": [],
            "color": "#f85149",
        },
        {
            "id": "retrieval-augmented-generation",
            "name": "Retrieval-Augmented Generation",
            "type": "methodology",
            "importance": 4,
            "summary": "在生成前检索外部知识以增强回答。",
            "significance": "改善知识时效性、可追溯性和准确性。",
            "release_date": "2020-05",
            "company": "",
            "tags": ["RAG", "retrieval"],
            "aliases": ["RAG"],
            "timeline": [],
            "color": "#39c5cf",
        },
    ]


def seed_database(runtime: Path) -> Path:
    """初始化唯一 SQLite，并写入确定性实体、关系、文章和报告。"""
    from src.engine import db_core
    from src.engine.database import (
        init_db,
        insert_articles,
        insert_report,
        upsert_entity,
        upsert_relationship,
    )

    db_path = runtime / "data" / "platform.db"
    db_core.DB_PATH = db_path
    init_db()
    for entity in fixture_entities():
        upsert_entity(entity)
    for source, target, relation, label in [
        ("openai", "chatgpt", "created", "创建"),
        ("openai", "gpt-4", "developed", "研发"),
        ("gpt-4", "transformer", "uses", "基于"),
        ("gpt-4", "in-context-learning", "enables", "支持"),
        ("sam-altman", "openai", "leads", "领导"),
        ("chatgpt-launch", "chatgpt", "released", "发布"),
        ("retrieval-augmented-generation", "transformer", "uses", "使用"),
    ]:
        upsert_relationship(source, target, relation, label)
    insert_articles(
        [
            {
                "id": "fixture-article-1",
                "title": "OpenAI releases a deterministic browser fixture",
                "url": "https://example.invalid/fixture-article-1",
                "source": "Fixture News",
                "published": "2026-07-16T08:00:00+00:00",
                "content_raw": "Fixture content for browser gate verification.",
                "categories": ["openai", "gpt-4"],
                "title_cn": "确定性浏览器门禁夹具发布",
                "one_liner": "用于验证首页、详情页和知识关联的固定数据。",
                "summary_points": ["固定输入", "无外部 AI", "可重复截图"],
                "score": 5,
                "score_reason": "浏览器门禁夹具",
            },
            {
                "id": "fixture-article-2",
                "title": "RAG workflow testing",
                "url": "https://example.invalid/fixture-article-2",
                "source": "Fixture Lab",
                "published": "2026-07-15T08:00:00+00:00",
                "content_raw": "A second deterministic fixture article.",
                "categories": ["retrieval-augmented-generation", "transformer"],
                "title_cn": "RAG 工作流测试",
                "one_liner": "为列表和时间线提供第二条稳定内容。",
                "summary_points": ["检索", "生成"],
                "score": 4,
                "score_reason": "浏览器门禁夹具",
            },
        ]
    )
    insert_report(
        "2026-07-16",
        "daily",
        "2026-07-16.md",
        fetched=12,
        filtered=8,
        star5=1,
        star4=1,
        star3=2,
    )
    conn = db_core.get_db()
    conn.execute(
        "UPDATE entities SET created_at=?, updated_at=?",
        ("2026-07-16T08:00:00+00:00", "2026-07-16T08:00:00+00:00"),
    )
    conn.execute(
        "UPDATE reports SET created_at=?",
        ("2026-07-16T08:00:00+00:00",),
    )
    conn.execute(
        "UPDATE articles SET created_at=?",
        ("2026-07-16T08:00:00+00:00",),
    )
    conn.commit()
    conn.close()
    return db_path


def generate_pages(runtime: Path, *, include_graphs: bool = False) -> list[Path]:
    reports = runtime / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "2026-07-16.md").write_text(
        "# AI News 浏览器门禁日报\n\n"
        "这是一份确定性测试报告，用于验证报告列表和阅读页面。\n",
        encoding="utf-8",
    )

    from src.frontend.article_page import generate_article_page
    from src.frontend.auth_page import generate_auth_page
    from src.frontend.dashboard import generate_dashboard
    from src.frontend.entity_page import generate_entity_shell
    from src.frontend.events_page import generate_events_page
    from src.frontend.kg_3d import generate_3d_html
    from src.frontend.kg_d3 import generate_html
    from src.frontend.library import generate_library
    from src.frontend.my_page import generate_my_page
    from src.frontend.report_reader import generate_report_reader
    from src.frontend.reports_page import generate_reports_page
    from src.frontend.research_page import generate_research_page
    from src.frontend.timeline_renderer import generate_timeline
    import src.frontend.auth_page as auth_page
    import src.frontend.entity_page as entity_page

    auth_page.ROOT_DIR = runtime
    entity_page.ROOT_DIR = runtime
    generated = [
        generate_dashboard(reports),
        generate_library(reports),
        generate_timeline(reports),
        generate_events_page(reports),
        generate_reports_page(reports),
        generate_research_page(reports),
        generate_my_page(reports),
        generate_article_page(reports),
        generate_report_reader(reports),
        generate_entity_shell(),
        generate_auth_page(),
    ]
    if include_graphs:
        generated.extend(
            [
                generate_html(output_dir=reports),
                generate_3d_html(output_dir=reports),
            ]
        )
    return [Path(path) for path in generated]


def audit_pages(pages: Iterable[Path]) -> list[dict]:
    results = []
    for page in pages:
        html = page.read_text(encoding="utf-8")
        collector = IdCollector()
        collector.feed(html)
        duplicates = sorted(
            key for key, count in Counter(collector.ids).items() if count > 1
        )
        results.append(
            {
                "path": str(page),
                "size": page.stat().st_size,
                "duplicate_ids": duplicates,
                "has_document": "<html" in html.lower() and "</html>" in html.lower(),
            }
        )
    return results


def prepare_runtime(run_dir: Path, *, include_graphs: bool = False) -> dict:
    runtime = run_dir / "runtime"
    for name in ("data", "reports", "cache", "logs"):
        (runtime / name).mkdir(parents=True, exist_ok=True)
    db_path = seed_database(runtime)
    pages = generate_pages(runtime, include_graphs=include_graphs)
    audit = audit_pages(pages)
    failures = [
        item
        for item in audit
        if item["duplicate_ids"] or not item["has_document"] or item["size"] <= 0
    ]
    fixture = {
        "runtime": str(runtime),
        "database": str(db_path),
        "entities": len(fixture_entities()),
        "pages": audit,
        "failures": failures,
    }
    (run_dir / "fixture.json").write_text(
        json.dumps(fixture, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if failures:
        raise RuntimeError(f"静态页面夹具审计失败：{failures}")
    return fixture


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def http_status(url: str, timeout: float = 1.0) -> int | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return None


def start_server(runtime: Path, port: int, run_dir: Path) -> subprocess.Popen:
    env = os.environ.copy()
    env["AI_NEWS_BROWSER_RUNTIME"] = str(runtime)
    env["AI_NEWS_TESTING"] = "1"
    for name in SECRET_ENV_NAMES:
        env.pop(name, None)
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "tools.browser_fixture_app:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    stdout = (run_dir / "server.stdout.log").open("w", encoding="utf-8")
    stderr = (run_dir / "server.stderr.log").open("w", encoding="utf-8")
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=env,
        stdout=stdout,
        stderr=stderr,
        creationflags=creation_flags,
    )
    process._browser_gate_logs = (stdout, stderr)  # type: ignore[attr-defined]
    deadline = time.monotonic() + 15
    health = f"http://127.0.0.1:{port}/api/health"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stop_server(process)
            raise RuntimeError(
                f"隔离前端服务启动失败，退出码 {process.returncode}；"
                f"查看 {run_dir / 'server.stderr.log'}"
            )
        if http_status(health) == 200:
            return process
        time.sleep(0.2)
    stop_server(process)
    raise RuntimeError("隔离前端服务在 15 秒内未就绪")


def stop_server(process: subprocess.Popen | None) -> None:
    if process is None:
        return
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
    for stream in getattr(process, "_browser_gate_logs", ()):
        stream.close()


def run_browser(
    base_url: str,
    routes: list[str],
    run_dir: Path,
    allowed_origins: list[str],
) -> subprocess.CompletedProcess[str]:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("未找到 Node.js，无法运行 Playwright Chromium")
    env = os.environ.copy()
    env.update(
        {
            "FRONTEND_BASE_URL": base_url,
            "FRONTEND_ROUTES": json.dumps(routes, ensure_ascii=False),
            "FRONTEND_OUTPUT_DIR": str(run_dir / "browser"),
            "FRONTEND_ALLOWED_ORIGINS": json.dumps(allowed_origins),
            "FRONTEND_FIXED_TIME": FIXED_BROWSER_TIME,
        }
    )
    return subprocess.run(
        [node, "tools/browser_audit.spec.js"],
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=240,
    )


def build_summary(
    *,
    run_id: str,
    run_dir: Path,
    fixture: dict | None,
    routes: list[str],
    profile: str,
    allowed_origins: list[str],
    before_digest: str,
    before_counts: dict[str, int],
    after_digest: str,
    after_counts: dict[str, int],
    browser_result: subprocess.CompletedProcess[str] | None,
    prepare_only: bool = False,
    error: str = "",
) -> dict:
    audit_path = run_dir / "browser" / "audit.json"
    audit = None
    if audit_path.is_file():
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
    pollution = before_digest != after_digest
    browser_exit = browser_result.returncode if browser_result else None
    passed = (
        not error
        and not pollution
        and (prepare_only or browser_exit == 0)
    )
    return {
        "schema_version": 1,
        "run_id": run_id,
        "generated_at": utc_now(),
        "status": "passed" if passed else "failed",
        "profile": profile,
        "prepare_only": prepare_only,
        "routes": routes,
        "viewports": [
            {"name": "desktop", "width": 1440, "height": 1000},
            {"name": "mobile", "width": 390, "height": 844},
        ],
        "network": {
            "policy": "loopback-only" if not allowed_origins else "allowlist",
            "allowed_external_origins": allowed_origins,
        },
        "fixed_browser_time": FIXED_BROWSER_TIME,
        "runtime": fixture,
        "browser": {
            "exit_code": browser_exit,
            "stdout": browser_result.stdout if browser_result else "",
            "stderr": browser_result.stderr if browser_result else "",
            "audit": audit,
        },
        "pollution": {
            "detected": pollution,
            "before_digest": before_digest,
            "after_digest": after_digest,
            "before_counts": before_counts,
            "after_counts": after_counts,
            "protected_paths": list(PROTECTED_RUNTIME_PATHS),
        },
        "error": error,
        "run_dir": str(run_dir),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=("core", "extended"),
        default="core",
        help="core 默认拒绝外网；extended 增加依赖 CDN 的 2D/3D 图谱",
    )
    parser.add_argument("--routes", nargs="+", help="覆盖 profile 的路由列表")
    parser.add_argument(
        "--allow-external-origin",
        action="append",
        default=[],
        help="显式允许的外部 origin，可重复传入",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="只构建和审计隔离夹具，不启动浏览器",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_id = make_run_id()
    run_dir = args.output_dir.resolve() / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    routes = args.routes or (
        EXTENDED_ROUTES if args.profile == "extended" else CORE_ROUTES
    )
    allowed_origins = list(dict.fromkeys(args.allow_external_origin))
    if args.profile == "extended":
        allowed_origins = list(dict.fromkeys([*allowed_origins, *GRAPH_EXTERNAL_ORIGINS]))

    before_digest, before_counts = protected_digest()
    fixture = None
    process = None
    browser_result = None
    error = ""
    try:
        fixture = prepare_runtime(run_dir, include_graphs=args.profile == "extended")
        if not args.prepare_only:
            port = free_port()
            process = start_server(Path(fixture["runtime"]), port, run_dir)
            browser_result = run_browser(
                f"http://127.0.0.1:{port}",
                routes,
                run_dir,
                allowed_origins,
            )
            (run_dir / "browser.stdout.log").write_text(
                browser_result.stdout, encoding="utf-8"
            )
            (run_dir / "browser.stderr.log").write_text(
                browser_result.stderr, encoding="utf-8"
            )
            if browser_result.returncode:
                error = f"Chromium 门禁失败，退出码 {browser_result.returncode}"
    except (
        OSError,
        RuntimeError,
        subprocess.SubprocessError,
        json.JSONDecodeError,
    ) as exc:
        error = str(exc)
    finally:
        stop_server(process)

    after_digest, after_counts = protected_digest()
    summary = build_summary(
        run_id=run_id,
        run_dir=run_dir,
        fixture=fixture,
        routes=list(routes),
        profile=args.profile,
        allowed_origins=allowed_origins,
        before_digest=before_digest,
        before_counts=before_counts,
        after_digest=after_digest,
        after_counts=after_counts,
        browser_result=browser_result,
        prepare_only=args.prepare_only,
        error=error,
    )
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    browser_audit = summary.get("browser", {}).get("audit") or {}
    print(
        json.dumps(
            {
                "status": summary["status"],
                "run_dir": str(run_dir),
                "cases": len(browser_audit.get("cases", [])),
                "pollution": summary["pollution"]["detected"],
                "error": error,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if summary["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
