"""研究 Agent：将单次 research_engine 调用升级为迭代式研究循环。

Agent Loop:
  Plan（分解话题）→ Search（每轮搜索）→ Assess（自评完整性）
  → 如不完整且轮次未耗尽则迭代 → Synthesize（合成最终报告）

复用 research_engine 的工具函数（上下文构建、引用验证、报告丰富化），
在其上增加决策循环和自我评估能力。
"""

from pathlib import Path

from .utils import log

PROMPT_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


# ── Prompt 加载 ──

def _load_prompt(name: str) -> str:
    path = PROMPT_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    log.warning(f"Prompt not found: {path}")
    return ""


# ── Phase 1: Plan ──

def _plan_research(topic: str, depth: str) -> list[str]:
    """将研究话题分解为子问题列表。"""
    from .ai_client import call_ai

    prompt = _load_prompt("agent-plan.md")
    prompt = prompt.replace("$RESEARCH_TOPIC", topic)
    prompt = prompt.replace("$DEPTH", depth)

    user = f"请将以下研究话题分解为子问题：{topic}（深度：{depth}）"

    result = call_ai(prompt, user, temperature=0.3, max_tokens=512)
    if not result:
        # Fallback: 直接用话题作为唯一子问题
        return [topic]

    plan = result[0] if result else {}
    sub_questions = plan.get("sub_questions", [topic])
    focus_areas = plan.get("focus_areas", [])

    # 合并 focus_areas 作为补充搜索方向
    if focus_areas:
        sub_questions.extend(focus_areas[:2])  # 最多加 2 个领域

    log.info(f"Agent Plan: {len(sub_questions)} sub_questions for '{topic}'")
    return sub_questions


# ── Phase 2: Search Round ──

def _search_round(
    sub_questions: list[str],
    seen_entity_ids: set[str],
    seen_article_ids: set[str],
    depth: str,
) -> tuple[list[dict], list[dict]]:
    """对一组子问题执行搜索，返回去重后的新实体和新文章。"""
    from .database import init_db, search, get_entity_neighbors

    init_db()

    all_new_entities: list[dict] = []
    all_new_articles: list[dict] = []
    neighbor_depth = 1 if depth == "standard" else 2

    for question in sub_questions:
        result = search(question, limit=10, semantic=True)
        entities = result.get("entities", [])
        articles = result.get("articles", [])

        # 去重
        for e in entities:
            eid = e.get("id", "")
            if eid and eid not in seen_entity_ids:
                seen_entity_ids.add(eid)
                all_new_entities.append(e)

        for a in articles:
            aid = a.get("id", "")
            if aid and aid not in seen_article_ids:
                seen_article_ids.add(aid)
                all_new_articles.append(a)

    # 图谱扩展：对新发现的种子实体扩展邻居
    seed_ids = [e.get("id", "") for e in all_new_entities[:10]]
    for eid in seed_ids:
        neighbors = get_entity_neighbors(eid, max_depth=neighbor_depth)
        for n in neighbors:
            n_entity = n.get("entity", {})
            nid = n_entity.get("id", "")
            if nid and nid not in seen_entity_ids:
                seen_entity_ids.add(nid)
                all_new_entities.append(n_entity)

    return all_new_entities, all_new_articles


# ── Phase 3: Assess ──

def _assess_completeness(
    topic: str,
    sub_questions: list[str],
    all_entities: list[dict],
    all_articles: list[dict],
    round_num: int,
    new_entities: list[dict],
    new_articles: list[dict],
) -> dict:
    """评估当前信息收集是否完整，返回评估结果。"""
    from .ai_client import call_ai

    # 构建轻量摘要而不是全量实体列表
    entity_summary = "\n".join(
        f'- {e.get("name", "")} ({e.get("type", "")}): {(e.get("summary") or "")[:100]}'
        for e in all_entities[:30]
    ) or "（无）"

    article_summary = "\n".join(
        f'- {a.get("title", a.get("title_cn", ""))} (来源: {a.get("source", "")})'
        for a in all_articles[:30]
    ) or "（无）"

    round_summary = (
        f"Round {round_num}: +{len(new_entities)} entities, +{len(new_articles)} articles"
    )

    prompt = _load_prompt("agent-assess.md")
    prompt = prompt.replace("$RESEARCH_TOPIC", topic)
    prompt = prompt.replace("$COLLECTED_ENTITIES", entity_summary)
    prompt = prompt.replace("$COLLECTED_ARTICLES", article_summary)
    prompt = prompt.replace("$SUB_QUESTIONS", "\n".join(f"- {q}" for q in sub_questions))
    prompt = prompt.replace("$ROUND_SUMMARY", round_summary)

    user = (
        f"评估话题 '{topic}' 的研究完整性。当前共 {len(all_entities)} 实体、"
        f"{len(all_articles)} 篇文章，已搜索 {round_num} 轮。"
    )

    result = call_ai(prompt, user, temperature=0.1, max_tokens=256)
    if not result:
        return {"score": 5, "is_complete": True, "gaps": [], "new_questions": []}

    assessment = result[0] if result else {}
    log.info(
        f"Agent Assess (round {round_num}): score={assessment.get('score', '?')}, "
        f"complete={assessment.get('is_complete', False)}"
    )
    return assessment


# ── Phase 4: Synthesize ──

def _synthesize_report(
    topic: str,
    all_entities: list[dict],
    all_articles: list[dict],
    round_log: list[dict],
    depth: str,
    lang: str,
) -> dict:
    """综合多轮搜索的所有发现，生成最终结构化报告。"""
    from .ai_client import call_ai
    from .research_engine import (
        _build_card_context,
        _build_article_context,
        _build_relation_context,
    )

    entity_ids = [e.get("id", "") for e in all_entities]

    card_context = _build_card_context(all_entities[:40])
    relation_context = _build_relation_context(entity_ids[:40], all_entities)
    article_context = _build_article_context(all_articles[:40])

    # 轮次日志摘要
    round_lines = []
    for r in sorted(round_log, key=lambda x: x.get("round", 0)):
        round_lines.append(
            f"  Round {r.get('round', '?')}: "
            f"+{r.get('new_entities', 0)} entities, "
            f"+{r.get('new_articles', 0)} articles, "
            f"score={r.get('score', '?')}"
        )
    round_summary = "\n".join(round_lines) if round_lines else "单轮搜索"

    prompt = _load_prompt("agent-synthesize.md")
    prompt = prompt.replace("$ROUNDS", str(len(round_log)))
    prompt = prompt.replace("$ROUND_LOG", round_summary)
    prompt = prompt.replace("$KNOWLEDGE_CARDS", card_context)
    prompt = prompt.replace("$ENTITY_RELATIONS", relation_context)
    prompt = prompt.replace("$RELATED_ARTICLES", article_context)
    prompt = prompt.replace("$RESEARCH_TOPIC", topic)

    user = (
        f"请基于 {len(all_entities)} 个实体和 {len(all_articles)} 篇文章，"
        f"对 '{topic}' 生成最终研究报告。语言: {'中文' if lang == 'zh' else 'English'}"
    )

    result = call_ai(prompt, user, temperature=0.3, max_tokens=4096)
    if result is None:
        return {}

    if isinstance(result, list) and result:
        report = result[0]
    elif isinstance(result, dict):
        report = result
    else:
        report = {}

    return report


# ── Main Entry Point ──

def research_agent(
    topic: str,
    depth: str = "standard",
    max_rounds: int = 3,
    lang: str = "zh",
) -> dict:
    """Agent 驱动的迭代式深度研究。

    Args:
        topic: 研究话题
        depth: 研究深度 ("standard" | "deep")
        max_rounds: 最大搜索轮次 (默认 3)
        lang: 报告语言 ("zh" | "en")

    Returns:
        {"report": {...}, "_agent_meta": {...}} 或 {"error": "..."}
    """
    from .research_engine import _verify_citations, _enrich_report

    if not topic or not topic.strip():
        return {"error": "研究主题不能为空"}

    # Phase 1: Plan
    sub_questions = _plan_research(topic, depth)
    if not sub_questions:
        return {"error": f"无法分解研究话题: {topic}"}

    # Phase 2: Research Loop
    all_entities: list[dict] = []
    all_articles: list[dict] = []
    seen_entity_ids: set[str] = set()
    seen_article_ids: set[str] = set()
    round_log: list[dict] = []

    for rnd in range(1, max_rounds + 1):
        new_entities, new_articles = _search_round(
            sub_questions, seen_entity_ids, seen_article_ids, depth
        )

        if not new_entities and not new_articles and rnd > 1:
            log.info(f"Agent: no new results in round {rnd}, stopping")
            round_log.append({
                "round": rnd, "new_entities": 0, "new_articles": 0,
                "score": 0, "stopped": "no_new_results",
            })
            break

        all_entities.extend(new_entities)
        all_articles.extend(new_articles)

        assessment = _assess_completeness(
            topic, sub_questions, all_entities, all_articles,
            rnd, new_entities, new_articles,
        )

        round_log.append({
            "round": rnd,
            "new_entities": len(new_entities),
            "new_articles": len(new_articles),
            "score": assessment.get("score", 0),
            "is_complete": assessment.get("is_complete", False),
            "gaps": assessment.get("gaps", []),
        })

        if assessment.get("is_complete"):
            break

        # 更新子问题继续搜索
        new_questions = assessment.get("new_questions", [])
        if new_questions:
            sub_questions = new_questions

    # 如果没有任何结果
    if not all_entities and not all_articles:
        return {"error": f"未找到与 '{topic}' 相关的信息"}

    # Phase 3: Synthesize
    report = _synthesize_report(
        topic, all_entities, all_articles, round_log, depth, lang
    )

    if not report:
        return {"error": "AI 报告生成失败，请稍后重试"}

    # Phase 4: Verify + Enrich
    valid_entity_ids = {e.get("id", "") for e in all_entities}
    valid_article_ids = {a.get("id", "") for a in all_articles}
    report = _verify_citations(report, valid_entity_ids, valid_article_ids)
    report = _enrich_report(report, all_entities, all_articles)

    # Agent 元数据
    report["_meta"] = {
        "topic": topic,
        "depth": depth,
        "mode": "agent",
        "rounds": len(round_log),
        "max_rounds": max_rounds,
        "total_entities": len(all_entities),
        "total_articles": len(all_articles),
        "round_log": round_log,
    }
    report["_entities"] = all_entities
    report["_articles"] = all_articles

    log.info(
        f"Agent: research complete for '{topic}' — "
        f"{len(round_log)} rounds, {len(all_entities)} entities, {len(all_articles)} articles"
    )

    return {"report": report}
