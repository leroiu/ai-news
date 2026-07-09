"""
AI News - 规则分类器 + LLM Fallback

关键词规则高置信命中时不调用 LLM。
规则无法判断或类别冲突时才调用 LLM。
分类结果带 confidence 和 method 标记。
"""

import re
from typing import Optional

from .fetcher import Article
from .utils import log, load_config, ROOT_DIR, clean_html
from .ai_client import call_ai


# ============================================================
# 规则分类
# ============================================================

def _load_rules(config: dict) -> list[dict]:
    """从 config 加载关键词规则。"""
    cls = config.get("classifier", {})
    return cls.get("keyword_rules", [])


def _match_article(article: Article, rules: list[dict]) -> list[tuple[str, float]]:
    """
    对单篇文章运行所有关键词规则。
    返回 [(category, weight), ...] 匹配列表。
    """
    text = f"{article.title} {article.content_raw}".lower()
    matches: list[tuple[str, float]] = []

    for rule in rules:
        category = rule.get("category", "")
        patterns = rule.get("patterns", [])
        weight = rule.get("weight", 1)

        for pattern in patterns:
            try:
                if re.search(pattern, text, re.IGNORECASE):
                    matches.append((category, float(weight)))
                    break  # 每个分类只计一次
            except re.error:
                continue

    return matches


def _rule_classify(article: Article, rules: list[dict],
                   max_categories: int, threshold: float) -> dict:
    """
    规则分类：返回 {categories, confidence, method}。
    """
    matches = _match_article(article, rules)

    if not matches:
        return {"categories": [], "confidence": 0.0, "method": "fallback"}

    # 按 weight 降序取 top N
    matched_cats: list[str] = []
    seen: set[str] = set()
    for cat, _ in sorted(matches, key=lambda x: -x[1]):
        if cat not in seen:
            seen.add(cat)
            matched_cats.append(cat)
        if len(matched_cats) >= max_categories:
            break

    # 置信度：命中1条=0.7，N条=max(0.7, N/max_categories)
    confidence = max(0.7, min(1.0, len(matches) / max_categories))

    method = "rule" if confidence >= threshold else "llm"
    return {"categories": matched_cats, "confidence": round(confidence, 2), "method": method}


# ============================================================
# LLM 分类（原逻辑，仅 fallback 时调用）
# ============================================================

def _build_system_prompt() -> str:
    template = (ROOT_DIR / "prompts" / "classify.md").read_text(encoding="utf-8")
    config = load_config()
    categories = config.get("categories", [])
    category_list = "\n".join(f"- {c}" for c in categories)
    return template.replace("$CATEGORY_LIST", category_list)


def _build_user_prompt(articles: list[Article]) -> str:
    lines = ["请为以下文章分类：\n"]
    for a in articles:
        content = clean_html(a.content_raw)[:300]
        lines.append(
            f"ID: {a.id}\n标题: {a.title}\n来源: {a.source}\n摘要: {content}\n"
        )
    return "\n".join(lines)


def _llm_classify_batch(articles: list[Article]) -> list[Article]:
    """对一批文章调用 LLM 分类。"""
    if not articles:
        return articles

    system = _build_system_prompt()
    user = _build_user_prompt(articles)

    log.info(f"AI 分类: {len(articles)} 篇（LLM fallback）")
    results = call_ai(system, user, max_tokens=4096)

    if not results:
        log.warning("LLM 分类失败，标记为'未分类'")
        for a in articles:
            a.categories = ["未分类"]
            a.classification_meta = {"method": "fallback", "confidence": 0.0}
        return articles

    class_map = {item["id"]: item.get("categories", ["未分类"]) for item in results}
    for a in articles:
        a.categories = class_map.get(a.id, ["未分类"])
        a.classification_meta = {"method": "llm", "confidence": 0.7}

    cat_counts: dict[str, int] = {}
    for a in articles:
        for c in a.categories:
            cat_counts[c] = cat_counts.get(c, 0) + 1
    top = sorted(cat_counts.items(), key=lambda x: -x[1])[:5]
    log.info(f"LLM 分类完成, Top: {top}")
    return articles


# ============================================================
# 主入口
# ============================================================

def classify(articles: list[Article], batch_size: int = 25) -> list[Article]:
    """
    分类主入口：先规则，后 LLM fallback。

    规则分类（从 config.classifier.keyword_rules 加载）:
      - keyword 命中 → 规则分类，标记 method=rule
      - 置信度 >= threshold → 不调 LLM
      - 置信度 < threshold → 降级到 LLM

    LLM fallback（原行为）:
      - 规则无法分类或置信度过低的文章
      - 分批调用 LLM

    降级模式：
      当 config.degradation.skip_all_llm=true 时，跳过所有 LLM 调用。
    """
    if not articles:
        return articles

    config = load_config()
    cls_cfg = config.get("classifier", {})
    deg_cfg = config.get("degradation", {})
    skip_llm = deg_cfg.get("skip_all_llm", False)
    rules = _load_rules(config)
    max_categories = cls_cfg.get("max_categories", 3)
    threshold = cls_cfg.get("rule_threshold", 0.6)
    method = cls_cfg.get("method", "rules_first")

    # ── 阶段 1: 规则分类 ──
    rule_result = []
    llm_candidates = []

    for a in articles:
        result = _rule_classify(a, rules, max_categories, threshold)

        if result["method"] == "rule" and result["categories"]:
            a.categories = result["categories"]
            a.classification_meta = {
                "method": "rule",
                "confidence": result["confidence"],
                "matched_categories": result["categories"],
            }
            rule_result.append(a)
        else:
            llm_candidates.append(a)

    log.info(
        f"分类: {len(articles)} 篇 → "
        f"规则={len(rule_result)} "
        f"LLM待定={len(llm_candidates)} "
        f"(阈值={threshold})"
    )

    # ── 阶段 2: LLM fallback ──
    if method == "llm_only":
        # 纯 LLM 模式：全部走 LLM
        llm_candidates = articles
        rule_result = []
        log.info("  模式=llm_only，全部走 LLM")

    # 降级模式：跳过所有 LLM 调用
    if skip_llm and llm_candidates:
        log.warning(f"  降级模式: 跳过 {len(llm_candidates)} 篇 LLM 分类，标记为'未分类'")
        for a in llm_candidates:
            a.categories = ["未分类"]
            a.classification_meta = {"method": "fallback", "confidence": 0.0}
        llm_candidates = []

    if llm_candidates:
        total = (len(llm_candidates) - 1) // batch_size + 1
        for i in range(0, len(llm_candidates), batch_size):
            batch = llm_candidates[i:i + batch_size]
            log.info(f"  LLM分类 {i // batch_size + 1}/{total} ({len(batch)}篇)")
            _llm_classify_batch(batch)

            # 如果 LLM 失败，对这批中未分类的标记 fallback
            for a in batch:
                if not a.categories:
                    a.categories = ["未分类"]
                    a.classification_meta = {"method": "fallback", "confidence": 0.0}

    # ── 统计 ──
    method_counts = {"rule": 0, "llm": 0, "fallback": 0}
    for a in articles:
        m = a.classification_meta.get("method", "fallback")
        method_counts[m] = method_counts.get(m, 0) + 1
    log.info(
        f"分类完成: 规则={method_counts['rule']} "
        f"LLM={method_counts['llm']} "
        f"Fallback={method_counts['fallback']}"
    )

    return articles
