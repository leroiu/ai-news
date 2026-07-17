"""隔离性能预算门禁：多样本 Chromium/API 基线与回归比较。"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.browser_gate import (  # noqa: E402
    CORE_ROUTES,
    FIXED_BROWSER_TIME,
    free_port,
    prepare_runtime,
    protected_digest,
    start_server,
    stop_server,
)


DEFAULT_OUTPUT = ROOT / "output" / "performance-gate"
DEFAULT_BASELINE = ROOT / ".quality" / "performance-baseline.json"
RULE_VERSION = 4
PAGE_SAMPLES = 3
API_SAMPLES = 20
API_ENDPOINTS = [
    "/api/health",
    "/api/entities",
    "/api/articles?limit=10&min_score=0",
    "/api/reports?type=daily&limit=5",
    "/api/entities/openai",
]
MEASUREMENT = {
    "viewport": {"width": 1440, "height": 1000},
    "colorScheme": "dark",
    "reducedMotion": "reduce",
    "cacheDisabled": True,
    "pageWarmupsPerRoute": 1,
    "apiWarmupsPerEndpoint": 1,
}

# metric -> (aggregate stat, absolute cap, additive margin, multiplier)
PAGE_METRICS = {
    "ttfbMs": ("p50", 500.0, 20.0, 1.35),
    "domContentLoadedMs": ("p50", 1500.0, 100.0, 1.35),
    "loadMs": ("p50", 2000.0, 100.0, 1.35),
    "fcpMs": ("p50", 1500.0, 75.0, 1.35),
    "lcpMs": ("p50", 2500.0, 75.0, 1.35),
    "cls": ("max", 0.5, 0.02, 1.05),
    "longTaskMaxMs": ("max", 200.0, 50.0, 1.5),
    "requestCount": ("max", 50.0, 0.0, 1.0),
    "encodedBytes": ("max", 512 * 1024.0, 4096.0, 1.05),
    "decodedBytes": ("max", 1024 * 1024.0, 4096.0, 1.05),
    "domNodes": ("max", 2500.0, 50.0, 1.1),
}
API_METRICS = {
    "durationMs": ("p95", 500.0, 20.0, 1.5),
    "bodyBytes": ("max", 1024 * 1024.0, 1024.0, 1.05),
}
PAGE_AGGREGATE_METRICS = [
    "ttfbMs",
    "domContentLoadedMs",
    "loadMs",
    "fcpMs",
    "lcpMs",
    "cls",
    "longTaskCount",
    "longTaskTotalMs",
    "longTaskMaxMs",
    "requestCount",
    "encodedBytes",
    "decodedBytes",
    "domNodes",
    "bodyTextLength",
    "wallMs",
]
PAGE_POSITIVE_METRICS = {
    "ttfbMs",
    "domContentLoadedMs",
    "loadMs",
    "fcpMs",
    "lcpMs",
    "requestCount",
    "encodedBytes",
    "decodedBytes",
    "domNodes",
    "bodyTextLength",
    "wallMs",
}
PAGE_NONNEGATIVE_METRICS = set(PAGE_AGGREGATE_METRICS) - PAGE_POSITIVE_METRICS
API_AGGREGATE_METRICS = ["durationMs", "bodyBytes"]
BASELINE_STRATEGY = {
    "formula": (
        "limit = min(absolute_cap, "
        "max(observed * multiplier, observed + additive_margin))"
    ),
    "timing": "页面时间使用 3 次冷缓存样本 p50；API 使用 20 次样本 p95",
    "structure": "请求数不允许增长；传输/解码体积与 DOM 使用较小比例和固定余量",
    "absolute_caps": {
        "page_ttfb_ms": 500,
        "page_load_ms": 2000,
        "page_lcp_ms": 2500,
        "page_cls_quality_target": 0.1,
        "page_cls_safety_cap": 0.5,
        "page_long_task_max_ms": 200,
        "page_encoded_bytes": 512 * 1024,
        "page_decoded_bytes": 1024 * 1024,
        "page_dom_nodes": 2500,
        "api_p95_ms": 500,
    },
}
BASELINE_POLICY = (
    "普通 check 只读取预算；任何放宽或矩阵变更必须显式 "
    "baseline --force 并审查。"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def run_audit(
    mode: str, base_url: str, phase_dir: Path
) -> subprocess.CompletedProcess[str]:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("未找到 Node.js，无法运行性能 Chromium 审计")
    env = os.environ.copy()
    env.update(
        {
            "PERFORMANCE_MODE": mode,
            "PERFORMANCE_BASE_URL": base_url,
            "PERFORMANCE_ROUTES": json.dumps(CORE_ROUTES, ensure_ascii=False),
            "PERFORMANCE_API_ENDPOINTS": json.dumps(
                API_ENDPOINTS, ensure_ascii=False
            ),
            "PERFORMANCE_OUTPUT_DIR": str(phase_dir / "audit"),
            "PERFORMANCE_FIXED_TIME": FIXED_BROWSER_TIME,
            "PERFORMANCE_PAGE_SAMPLES": str(PAGE_SAMPLES),
            "PERFORMANCE_API_SAMPLES": str(API_SAMPLES),
        }
    )
    return subprocess.run(
        [node, "tools/performance_audit.mjs"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=360,
        check=False,
    )


def merge_audits(page_audit: dict, api_audit: dict) -> dict:
    shared_keys = (
        "schemaVersion",
        "ruleVersion",
        "fixedTime",
        "measurement",
        "pageSamples",
        "apiSamples",
        "routes",
        "apiEndpoints",
    )
    for key in shared_keys:
        if page_audit.get(key) != api_audit.get(key):
            raise RuntimeError(f"页面/API 性能审计元数据不一致：{key}")
    if page_audit.get("mode") != "pages" or api_audit.get("mode") != "apis":
        raise RuntimeError("性能审计阶段模式无效")
    if page_audit.get("apis") or api_audit.get("pages"):
        raise RuntimeError("性能审计阶段结果发生交叉污染")
    environment = page_audit.get("environment")
    if not isinstance(environment, dict) or not environment.get("chromium"):
        raise RuntimeError("页面性能审计缺少 Chromium 版本")
    api_environment = api_audit.get("environment")
    for key in ("node", "playwright", "platform"):
        if environment.get(key) != (api_environment or {}).get(key):
            raise RuntimeError(f"页面/API 性能审计运行环境不一致：{key}")

    pages = page_audit["pages"]
    apis = api_audit["apis"]
    return {
        "schemaVersion": page_audit["schemaVersion"],
        "ruleVersion": page_audit["ruleVersion"],
        "mode": "merged",
        "generatedAt": utc_now(),
        "fixedTime": page_audit["fixedTime"],
        "origins": {
            "pages": page_audit.get("baseOrigin"),
            "apis": api_audit.get("baseOrigin"),
        },
        "environment": environment,
        "measurement": page_audit["measurement"],
        "pageSamples": page_audit["pageSamples"],
        "apiSamples": page_audit["apiSamples"],
        "routes": page_audit["routes"],
        "apiEndpoints": page_audit["apiEndpoints"],
        "pages": pages,
        "apis": apis,
        "summary": {
            "pageRoutes": len(pages),
            "pageSamples": sum(len(item["samples"]) for item in pages),
            "apiEndpoints": len(apis),
            "apiSamples": sum(len(item["samples"]) for item in apis),
            "pageErrors": page_audit["summary"]["pageErrors"],
            "apiErrors": api_audit["summary"]["apiErrors"],
        },
        "phaseEvidence": {
            "pages": "pages/audit/audit.json",
            "apis": "apis/audit/audit.json",
        },
    }


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _is_loopback_origin(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return (
        parsed.scheme == "http"
        and parsed.hostname == "127.0.0.1"
        and parsed.port is not None
        and parsed.path in ("", "/")
        and not parsed.params
        and not parsed.query
        and not parsed.fragment
    )


def _percentile(values: list[float], percent: int) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil((percent / 100) * len(ordered)) - 1)
    return ordered[index]


def _aggregate(values: list[float]) -> dict[str, float]:
    return {
        "min": round(min(values), 3),
        "p50": round(_percentile(values, 50), 3),
        "p95": round(_percentile(values, 95), 3),
        "max": round(max(values), 3),
    }


def _aggregate_matches(
    samples: list[dict], aggregate: dict, metrics: list[str]
) -> str:
    for metric in metrics:
        values = [float(sample[metric]) for sample in samples]
        expected = _aggregate(values)
        actual = aggregate.get(metric)
        if not isinstance(actual, dict) or set(actual) != set(expected):
            return f"聚合指标 {metric} 结构无效"
        for stat, expected_value in expected.items():
            if not _is_number(actual.get(stat)) or not math.isclose(
                float(actual[stat]), expected_value, abs_tol=0.001
            ):
                return f"聚合指标 {metric}.{stat} 与原始样本不一致"
    return ""


def validate_audit(audit: dict) -> str:
    if audit.get("schemaVersion") != 1 or audit.get("ruleVersion") != RULE_VERSION:
        return "性能 audit schema/rule 版本无效"
    if audit.get("mode") != "merged":
        return "性能 audit 不是页面/API 隔离合并结果"
    if audit.get("routes") != CORE_ROUTES:
        return "性能 audit 页面路由矩阵无效"
    if audit.get("apiEndpoints") != API_ENDPOINTS:
        return "性能 audit API 矩阵无效"
    if audit.get("pageSamples") != PAGE_SAMPLES or audit.get(
        "apiSamples"
    ) != API_SAMPLES:
        return "性能 audit 样本配置无效"
    if audit.get("measurement") != MEASUREMENT:
        return "性能 audit 测量配置漂移"
    origins = audit.get("origins")
    if (
        not isinstance(origins, dict)
        or not _is_loopback_origin(origins.get("pages"))
        or not _is_loopback_origin(origins.get("apis"))
    ):
        return "性能 audit 缺少有效的隔离 loopback origin"
    page_origin = origins["pages"]
    api_origin = origins["apis"]
    environment = audit.get("environment")
    if not isinstance(environment, dict) or not all(
        isinstance(environment.get(key), str) and environment[key]
        for key in ("node", "playwright", "chromium", "platform")
    ):
        return "性能 audit 缺少完整运行环境版本"

    pages = audit.get("pages")
    apis = audit.get("apis")
    if not isinstance(pages, list) or [
        item.get("route") for item in pages
    ] != CORE_ROUTES:
        return "性能 audit 页面结果不完整或顺序漂移"
    if not isinstance(apis, list) or [
        item.get("endpoint") for item in apis
    ] != API_ENDPOINTS:
        return "性能 audit API 结果不完整或顺序漂移"

    for item in pages:
        route = item.get("route")
        warmup = item.get("warmup")
        samples = item.get("samples")
        aggregate = item.get("aggregate")
        if not isinstance(warmup, dict) or warmup.get("sample") != 0:
            return f"页面 {route} 缺少预热证据"
        if not isinstance(samples, list) or len(samples) != PAGE_SAMPLES:
            return f"页面 {route} 样本数不足"
        if [sample.get("sample") for sample in samples] != list(
            range(1, PAGE_SAMPLES + 1)
        ):
            return f"页面 {route} 样本编号无效"
        for sample in [warmup, *samples]:
            if sample.get("route") != route or sample.get("status") != 200:
                return f"页面 {route} 样本状态无效"
            if sample.get("navigationError"):
                return f"页面 {route} 存在导航错误"
            for field in (
                "badResponses",
                "failedRequests",
                "externalRequests",
                "webSockets",
                "nonGetRequests",
            ):
                if sample.get(field) != []:
                    return f"页面 {route} 存在 {field}"
            for metric in PAGE_POSITIVE_METRICS:
                if not _is_number(sample.get(metric)) or float(sample[metric]) <= 0:
                    return f"页面 {route} 指标 {metric} 必须为有限正数"
            for metric in PAGE_NONNEGATIVE_METRICS:
                if not _is_number(sample.get(metric)) or float(sample[metric]) < 0:
                    return f"页面 {route} 指标 {metric} 必须为有限非负数"
            responses = sample.get("responses")
            if not isinstance(responses, list) or len(responses) != sample["requestCount"]:
                return f"页面 {route} 响应明细与请求数不一致"
            expected_bad_responses = []
            expected_ignored_responses = []
            decoded_bytes = 0.0
            for response in responses:
                response_url = response.get("url")
                parsed = urlparse(response_url) if isinstance(response_url, str) else None
                response_origin = (
                    f"{parsed.scheme}://{parsed.netloc}" if parsed else ""
                )
                if response_origin != page_origin:
                    return f"页面 {route} 响应 URL 不是隔离 loopback origin"
                if response.get("method") != "GET":
                    return f"页面 {route} 包含非 GET 响应"
                status = response.get("status")
                body_bytes = response.get("bodyBytes")
                if (
                    not isinstance(status, int)
                    or isinstance(status, bool)
                    or status < 100
                    or status > 599
                ):
                    return f"页面 {route} 响应状态无效"
                if not _is_number(body_bytes) or float(body_bytes) < 0:
                    return f"页面 {route} 响应 bodyBytes 无效"
                decoded_bytes += float(body_bytes)
                if parsed.path == "/favicon.ico" and status == 404:
                    expected_ignored_responses.append(response)
                elif status >= 400:
                    expected_bad_responses.append(response)
            if sample.get("badResponses") != expected_bad_responses:
                return f"页面 {route} badResponses 与响应明细不一致"
            if sample.get("ignoredResponses") != expected_ignored_responses:
                return f"页面 {route} ignoredResponses 与响应明细不一致"
            if not math.isclose(
                float(sample["decodedBytes"]), decoded_bytes, abs_tol=0.001
            ):
                return f"页面 {route} decodedBytes 与响应明细不一致"
        expected_warmup_errors = (
            (warmup["status"] != 200)
            + bool(warmup["navigationError"])
            + len(warmup["failedRequests"])
            + len(warmup["badResponses"])
            + len(warmup["externalRequests"])
            + len(warmup["webSockets"])
            + len(warmup["nonGetRequests"])
        )
        if item.get("warmupErrors") != expected_warmup_errors:
            return f"页面 {route} 预热错误计数与原始证据不一致"
        if not isinstance(aggregate, dict) or aggregate.get("samples") != PAGE_SAMPLES:
            return f"页面 {route} 聚合样本数无效"
        expected_counts = {
            "statusErrors": sum(sample["status"] != 200 for sample in samples),
            "navigationErrors": sum(
                bool(sample["navigationError"]) for sample in samples
            ),
            "failedRequests": sum(
                len(sample["failedRequests"]) for sample in samples
            ),
            "badResponses": sum(len(sample["badResponses"]) for sample in samples),
            "externalRequests": sum(
                len(sample["externalRequests"]) for sample in samples
            ),
            "webSockets": sum(len(sample["webSockets"]) for sample in samples),
            "nonGetRequests": sum(
                len(sample["nonGetRequests"]) for sample in samples
            ),
        }
        if any(aggregate.get(key) != value for key, value in expected_counts.items()):
            return f"页面 {route} 错误聚合计数与原始样本不一致"
        aggregate_error = _aggregate_matches(
            samples, aggregate, PAGE_AGGREGATE_METRICS
        )
        if aggregate_error:
            return f"页面 {route} {aggregate_error}"

    for item in apis:
        endpoint = item.get("endpoint")
        warmup = item.get("warmup")
        samples = item.get("samples")
        aggregate = item.get("aggregate")
        if not isinstance(warmup, dict) or warmup.get("sample") != 0:
            return f"API {endpoint} 缺少预热证据"
        if not isinstance(samples, list) or len(samples) != API_SAMPLES:
            return f"API {endpoint} 样本数不足"
        if [sample.get("sample") for sample in samples] != list(
            range(1, API_SAMPLES + 1)
        ):
            return f"API {endpoint} 样本编号无效"
        for sample in [warmup, *samples]:
            if sample.get("status") != 200 or sample.get("error"):
                return f"API {endpoint} 样本包含请求错误"
            if (
                sample.get("url") != f"{api_origin}{endpoint}"
                or sample.get("method") != "GET"
            ):
                return f"API {endpoint} 样本不是隔离 loopback GET"
            for metric in API_AGGREGATE_METRICS:
                if not _is_number(sample.get(metric)) or float(sample[metric]) <= 0:
                    return f"API {endpoint} 指标 {metric} 必须为有限正数"
        if not isinstance(aggregate, dict) or aggregate.get("samples") != API_SAMPLES:
            return f"API {endpoint} 聚合样本数无效"
        expected_errors = sum(
            bool(sample["error"]) or sample["status"] != 200 for sample in samples
        )
        expected_warmup_errors = int(
            bool(warmup["error"]) or warmup["status"] != 200
        )
        if aggregate.get("warmupErrors") != expected_warmup_errors:
            return f"API {endpoint} 预热错误计数与原始证据不一致"
        if aggregate.get("errors") != expected_errors:
            return f"API {endpoint} 错误聚合计数与原始样本不一致"
        aggregate_error = _aggregate_matches(
            samples, aggregate, API_AGGREGATE_METRICS
        )
        if aggregate_error:
            return f"API {endpoint} {aggregate_error}"

    expected_summary = {
        "pageRoutes": len(CORE_ROUTES),
        "pageSamples": len(CORE_ROUTES) * PAGE_SAMPLES,
        "apiEndpoints": len(API_ENDPOINTS),
        "apiSamples": len(API_ENDPOINTS) * API_SAMPLES,
        "pageErrors": sum(
            item["warmupErrors"]
            + sum(
                item["aggregate"][key]
                for key in (
                    "statusErrors",
                    "navigationErrors",
                    "failedRequests",
                    "badResponses",
                    "externalRequests",
                    "webSockets",
                    "nonGetRequests",
                )
            )
            for item in pages
        ),
        "apiErrors": sum(
            item["aggregate"]["warmupErrors"] + item["aggregate"]["errors"]
            for item in apis
        ),
    }
    if audit.get("summary") != expected_summary:
        return "性能 audit 汇总计数无效"
    if expected_summary["pageErrors"] or expected_summary["apiErrors"]:
        return "性能 audit 包含页面或 API 错误"
    return ""


def budget_value(
    observed: float, absolute: float, additive: float, multiplier: float
) -> float:
    relative = max(observed + additive, observed * multiplier)
    value = min(relative, absolute)
    return round(value, 3)


def build_budgets(audit: dict) -> dict:
    pages = {}
    for item in audit["pages"]:
        aggregate = item["aggregate"]
        route_budgets = {}
        for metric, (stat, absolute, additive, multiplier) in PAGE_METRICS.items():
            observed = float(aggregate[metric][stat])
            route_budgets[metric] = {
                "stat": stat,
                "observed": observed,
                "limit": budget_value(observed, absolute, additive, multiplier),
                "absolute_cap": absolute,
                "additive_margin": additive,
                "multiplier": multiplier,
            }
        pages[item["route"]] = route_budgets
    apis = {}
    for item in audit["apis"]:
        aggregate = item["aggregate"]
        endpoint_budgets = {}
        for metric, (stat, absolute, additive, multiplier) in API_METRICS.items():
            observed = float(aggregate[metric][stat])
            endpoint_budgets[metric] = {
                "stat": stat,
                "observed": observed,
                "limit": budget_value(observed, absolute, additive, multiplier),
                "absolute_cap": absolute,
                "additive_margin": additive,
                "multiplier": multiplier,
            }
        apis[item["endpoint"]] = endpoint_budgets
    return {"pages": pages, "apis": apis}


def compare_budgets(audit: dict, baseline: dict) -> list[dict]:
    violations = []
    pages = {item["route"]: item["aggregate"] for item in audit["pages"]}
    apis = {item["endpoint"]: item["aggregate"] for item in audit["apis"]}
    for route, metrics in baseline["budgets"]["pages"].items():
        for metric, budget in metrics.items():
            actual = float(pages[route][metric][budget["stat"]])
            if actual > float(budget["limit"]):
                violations.append(
                    {
                        "kind": "page",
                        "target": route,
                        "metric": metric,
                        "stat": budget["stat"],
                        "actual": actual,
                        "limit": float(budget["limit"]),
                        "fingerprint": f"page|{route}|{metric}|{budget['stat']}",
                    }
                )
    for endpoint, metrics in baseline["budgets"]["apis"].items():
        for metric, budget in metrics.items():
            actual = float(apis[endpoint][metric][budget["stat"]])
            if actual > float(budget["limit"]):
                violations.append(
                    {
                        "kind": "api",
                        "target": endpoint,
                        "metric": metric,
                        "stat": budget["stat"],
                        "actual": actual,
                        "limit": float(budget["limit"]),
                        "fingerprint": (
                            f"api|{endpoint}|{metric}|{budget['stat']}"
                        ),
                    }
                )
    return violations


def _validate_budget(
    target_kind: str,
    target: str,
    metric: str,
    budget: dict,
    config: tuple[str, float, float, float],
) -> str:
    stat, absolute, additive, multiplier = config
    for field in (
        "observed",
        "limit",
        "absolute_cap",
        "additive_margin",
        "multiplier",
    ):
        if not _is_number(budget.get(field)):
            return f"{target_kind} {target} 指标 {metric} 缺少有效 {field}"
    observed = float(budget["observed"])
    limit = float(budget["limit"])
    if budget.get("stat") != stat:
        return f"{target_kind} {target} 指标 {metric} 聚合方式漂移"
    if (
        not math.isclose(float(budget["absolute_cap"]), absolute, abs_tol=0.001)
        or not math.isclose(float(budget["additive_margin"]), additive, abs_tol=0.001)
        or not math.isclose(float(budget["multiplier"]), multiplier, abs_tol=0.001)
    ):
        return f"{target_kind} {target} 指标 {metric} 预算策略被修改"
    if observed < 0 or observed > absolute:
        return f"{target_kind} {target} 指标 {metric} 观测值超过绝对上限"
    expected_limit = budget_value(observed, absolute, additive, multiplier)
    if not math.isclose(limit, expected_limit, abs_tol=0.001):
        return f"{target_kind} {target} 指标 {metric} limit 未按策略生成"
    if limit > absolute:
        return f"{target_kind} {target} 指标 {metric} limit 超过绝对上限"
    return ""


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_baseline(baseline: dict, audit: dict) -> str:
    if baseline.get("schema_version") != 1 or baseline.get(
        "rule_version"
    ) != RULE_VERSION:
        return "性能基线 schema/rule 版本无效"
    if baseline.get("routes") != audit.get("routes"):
        return "性能基线页面矩阵不匹配"
    if baseline.get("api_endpoints") != audit.get("apiEndpoints"):
        return "性能基线 API 矩阵不匹配"
    if baseline.get("page_samples") != PAGE_SAMPLES or baseline.get(
        "api_samples"
    ) != API_SAMPLES:
        return "性能基线样本配置不匹配"
    if baseline.get("measurement") != audit.get("measurement"):
        return "性能基线测量配置不匹配"
    if baseline.get("environment") != audit.get("environment"):
        return "性能基线运行环境版本不匹配"
    if baseline.get("strategy") != BASELINE_STRATEGY:
        return "性能基线 strategy 被修改"
    if baseline.get("policy") != BASELINE_POLICY:
        return "性能基线 policy 被修改"
    budgets = baseline.get("budgets")
    if not isinstance(budgets, dict):
        return "性能基线 budgets 无效"
    if list(budgets.get("pages", {})) != CORE_ROUTES:
        return "性能基线页面预算不完整"
    if list(budgets.get("apis", {})) != API_ENDPOINTS:
        return "性能基线 API 预算不完整"
    for route, metrics in budgets["pages"].items():
        if set(metrics) != set(PAGE_METRICS):
            return f"页面 {route} 性能预算指标不完整"
        for metric, budget in metrics.items():
            error = _validate_budget(
                "页面", route, metric, budget, PAGE_METRICS[metric]
            )
            if error:
                return error
    for endpoint, metrics in budgets["apis"].items():
        if set(metrics) != set(API_METRICS):
            return f"API {endpoint} 性能预算指标不完整"
        for metric, budget in metrics.items():
            error = _validate_budget(
                "API", endpoint, metric, budget, API_METRICS[metric]
            )
            if error:
                return error
    expected_known_debt = [
        {
            "kind": "page",
            "target": route,
            "metric": "cls",
            "observed": float(metrics["cls"]["observed"]),
            "quality_target": 0.1,
            "fingerprint": f"page|{route}|cls|max",
        }
        for route, metrics in budgets["pages"].items()
        if float(metrics["cls"]["observed"]) > 0.1
    ]
    if baseline.get("known_debt") != expected_known_debt:
        return "性能基线 known_debt 与观测值不一致"
    evidence_value = baseline.get("evidence")
    evidence_digest = baseline.get("evidence_sha256")
    if not isinstance(evidence_value, str) or not evidence_value:
        return "性能基线缺少 evidence 路径"
    if (
        not isinstance(evidence_digest, str)
        or len(evidence_digest) != 64
        or any(char not in "0123456789abcdef" for char in evidence_digest)
    ):
        return "性能基线 evidence_sha256 无效"
    evidence_path = Path(evidence_value)
    if not evidence_path.is_absolute():
        evidence_path = ROOT / evidence_path
    try:
        actual_digest = _file_sha256(evidence_path)
        evidence_audit = json.loads(evidence_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return f"性能基线证据不存在：{evidence_path}"
    except (OSError, json.JSONDecodeError) as error:
        return f"性能基线证据无法读取：{error}"
    if actual_digest != evidence_digest:
        return "性能基线证据摘要不匹配"
    evidence_error = validate_audit(evidence_audit)
    if evidence_error:
        return f"性能基线原始证据无效：{evidence_error}"
    if evidence_audit.get("environment") != baseline.get("environment"):
        return "性能基线 environment 与原始证据不一致"
    if evidence_audit.get("measurement") != baseline.get("measurement"):
        return "性能基线 measurement 与原始证据不一致"
    if build_budgets(evidence_audit) != budgets:
        return "性能基线 observed/limit 与原始证据不一致"
    return ""


def create_baseline(
    path: Path, audit: dict, evidence: Path, force: bool
) -> dict:
    if path.exists() and not force:
        raise RuntimeError(f"性能基线已存在：{path}；替换必须使用 --force")
    budgets = build_budgets(audit)
    if not evidence.is_file():
        raise RuntimeError(f"性能基线原始证据不存在：{evidence}")
    resolved_evidence = evidence.resolve()
    try:
        stored_evidence = resolved_evidence.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        stored_evidence = str(resolved_evidence)
    for target_kind, targets, config in (
        ("页面", budgets["pages"], PAGE_METRICS),
        ("API", budgets["apis"], API_METRICS),
    ):
        for target, metrics in targets.items():
            for metric, budget in metrics.items():
                error = _validate_budget(
                    target_kind, target, metric, budget, config[metric]
                )
                if error:
                    raise RuntimeError(f"拒绝创建性能基线：{error}")
    payload = {
        "schema_version": 1,
        "rule_version": RULE_VERSION,
        "created_at": utc_now(),
        "routes": CORE_ROUTES,
        "api_endpoints": API_ENDPOINTS,
        "page_samples": PAGE_SAMPLES,
        "api_samples": API_SAMPLES,
        "measurement": audit["measurement"],
        "environment": audit["environment"],
        "budgets": budgets,
        "known_debt": [
            {
                "kind": "page",
                "target": item["route"],
                "metric": "cls",
                "observed": float(item["aggregate"]["cls"]["max"]),
                "quality_target": 0.1,
                "fingerprint": f"page|{item['route']}|cls|max",
            }
            for item in audit["pages"]
            if float(item["aggregate"]["cls"]["max"]) > 0.1
        ],
        "strategy": BASELINE_STRATEGY,
        "evidence": stored_evidence,
        "evidence_sha256": _file_sha256(resolved_evidence),
        "policy": BASELINE_POLICY,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)
    return payload


def load_baseline(path: Path, audit: dict) -> tuple[dict | None, str]:
    try:
        baseline = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"缺少性能基线：{path}"
    except (OSError, json.JSONDecodeError) as error:
        return None, f"无法读取性能基线：{error}"
    validation_error = validate_baseline(baseline, audit)
    return (None, validation_error) if validation_error else (baseline, "")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("baseline", "check"):
        command = subparsers.add_parser(name)
        command.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
        command.add_argument("--baseline-path", type=Path, default=DEFAULT_BASELINE)
        if name == "baseline":
            command.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_id = make_run_id()
    run_dir = args.output_dir.resolve() / f"{run_id}-{args.command}"
    run_dir.mkdir(parents=True, exist_ok=False)
    before_digest, before_counts = protected_digest()
    fixture = None
    audit_results: dict[str, subprocess.CompletedProcess[str]] = {}
    audit = None
    baseline = None
    violations = []
    error = ""
    try:
        fixture = prepare_runtime(run_dir)
        phase_audits = {}
        for mode in ("pages", "apis"):
            phase_dir = run_dir / mode
            phase_dir.mkdir(parents=True, exist_ok=False)
            process = None
            try:
                port = free_port()
                process = start_server(Path(fixture["runtime"]), port, phase_dir)
                result = run_audit(mode, f"http://127.0.0.1:{port}", phase_dir)
                audit_results[mode] = result
            finally:
                stop_server(process)
            (phase_dir / "audit.stdout.log").write_text(
                result.stdout, encoding="utf-8"
            )
            (phase_dir / "audit.stderr.log").write_text(
                result.stderr, encoding="utf-8"
            )
            audit_path = phase_dir / "audit" / "audit.json"
            if not audit_path.is_file():
                raise RuntimeError(f"{mode} 性能审计未生成 audit.json")
            phase_audits[mode] = json.loads(
                audit_path.read_text(encoding="utf-8")
            )
            if result.returncode:
                raise RuntimeError(
                    f"{mode} 性能审计失败，退出码 {result.returncode}"
                )

        audit = merge_audits(phase_audits["pages"], phase_audits["apis"])
        merged_dir = run_dir / "audit"
        merged_dir.mkdir(parents=True, exist_ok=False)
        merged_path = merged_dir / "audit.json"
        merged_path.write_text(
            json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        audit_error = validate_audit(audit)
        if audit_error:
            raise RuntimeError(audit_error)
        if args.command == "baseline":
            if args.baseline_path.resolve().exists() and not args.force:
                raise RuntimeError(
                    f"性能基线已存在：{args.baseline_path.resolve()}；"
                    "替换必须使用 --force"
                )
        else:
            baseline, baseline_error = load_baseline(
                args.baseline_path.resolve(), audit
            )
            if baseline_error:
                raise RuntimeError(baseline_error)
            violations = compare_budgets(audit, baseline)
            if violations:
                error = f"发现 {len(violations)} 个性能预算回归"
    except (
        OSError,
        RuntimeError,
        subprocess.SubprocessError,
        json.JSONDecodeError,
    ) as exc:
        error = str(exc)

    after_digest, after_counts = protected_digest()
    pollution = before_digest != after_digest
    if pollution and not error:
        error = "性能门禁修改了受保护业务运行目录"
    if args.command == "baseline" and not error and audit:
        try:
            baseline = create_baseline(
                args.baseline_path.resolve(),
                audit,
                run_dir / "audit" / "audit.json",
                args.force,
            )
        except (OSError, RuntimeError) as exc:
            error = str(exc)
    status = "passed" if not error else "failed"
    summary = {
        "schema_version": 1,
        "run_id": run_id,
        "command": args.command,
        "status": status,
        "generated_at": utc_now(),
        "audit": {
            "exit_codes": {
                mode: result.returncode for mode, result in audit_results.items()
            },
            "summary": audit.get("summary") if audit else None,
            "path": str(run_dir / "audit" / "audit.json"),
            "phase_paths": {
                mode: str(run_dir / mode / "audit" / "audit.json")
                for mode in ("pages", "apis")
            },
        },
        "baseline": {
            "path": str(args.baseline_path.resolve()),
            "rule_version": baseline.get("rule_version") if baseline else None,
        },
        "violations": violations,
        "pollution": {
            "detected": pollution,
            "before_digest": before_digest,
            "after_digest": after_digest,
            "before_counts": before_counts,
            "after_counts": after_counts,
        },
        "fixture": fixture,
        "error": error,
        "run_dir": str(run_dir),
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": status,
                "run_dir": str(run_dir),
                "page_samples": (audit or {}).get("summary", {}).get(
                    "pageSamples", 0
                ),
                "api_samples": (audit or {}).get("summary", {}).get(
                    "apiSamples", 0
                ),
                "violations": len(violations),
                "pollution": pollution,
                "error": error,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
