"""深度研究后端引擎：话题搜索、图谱扩展、上下文组装与 AI 报告生成。

V2 增强：
- 知识图谱深度关联：搜索匹配实体后遍历关系图谱，扩展 1-2 跳邻居
- 引用溯源：AI 返回后验证 card_id/article_id 真实性，剔除幻觉引用
- 关系上下文注入：在 prompt 中包含实体间关系信息
"""

from pathlib import Path

from src.interfaces.i18n import TYPE_LABELS_ZH, t

RESEARCH_PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "prompts" / "research.md"


def _load_research_prompt() -> str:
    if RESEARCH_PROMPT_PATH.exists():
        return RESEARCH_PROMPT_PATH.read_text(encoding="utf-8")
    return """你是顶级 AI 行业研究分析师。基于提供的知识卡片和文章进行深度研究。

## 已知知识卡片
$KNOWLEDGE_CARDS

## 实体关系图
$ENTITY_RELATIONS

## 相关文章
$RELATED_ARTICLES

## 研究主题
$RESEARCH_TOPIC

返回 JSON：{"summary":"...", "key_findings":[...], "card_connections":[...], "timeline":[...], "further_reading":[...]}
"""


def _build_card_context(entities: list[dict]) -> str:
    """将实体列表构建为知识卡片上下文字符串。"""
    lines = []
    for entity in entities:
        entity_type = entity.get("type", "")
        summary = (entity.get("summary") or entity.get("significance") or "")[:300]
        lines.append(
            f'- [{entity.get("id", "")}] {entity.get("name", "")} '
            f'({TYPE_LABELS_ZH.get(entity_type, entity_type)}): {summary}'
        )
    return "\n".join(lines)


def _build_relation_context(entity_ids: list[str], all_entities: list[dict]) -> str:
    """构建实体间关系上下文字符串。"""
    from .database import get_entity_relation_graph

    graph = get_entity_relation_graph(entity_ids)
    relations = graph.get("relations", [])
    if not relations:
        return "（未发现直接关系）"

    # 构建实体名映射
    name_map = {e.get("id"): e.get("name", e.get("id")) for e in all_entities}

    lines = []
    for r in relations:
        src_name = name_map.get(r["source_id"], r["source_id"])
        tgt_name = name_map.get(r["target_id"], r["target_id"])
        label = r.get("label", "") or r["rel_type"]
        lines.append(f"  {src_name} --[{label}]--> {tgt_name}")

    return "\n".join(lines)


def _build_article_context(articles: list[dict]) -> str:
    """将文章列表构建为上下文字符串。"""
    lines = []
    for article in articles:
        title = article.get("title", article.get("title_cn", ""))
        lines.append(
            f'- [{article.get("id", "")}] {title} (来源: {article.get("source", "")}) '
            f'{article.get("one_liner", "") or ""}'
        )
    return "\n".join(lines)


def _verify_citations(report: dict, valid_entity_ids: set[str], valid_article_ids: set[str]) -> dict:
    """验证 AI 返回的引用是否真实存在，剔除不存在的 ID，标注可信度。

    对 key_findings 中的 card_ids/article_ids 和 card_connections 中的 card_id 进行校验。
    """
    if not isinstance(report, dict):
        return report

    # 验证 key_findings 中的引用
    findings = report.get("key_findings", [])
    if isinstance(findings, list):
        for f in findings:
            if not isinstance(f, dict):
                continue
            card_ids = f.get("card_ids", [])
            article_ids = f.get("article_ids", [])
            if isinstance(card_ids, list):
                verified_cards = [c for c in card_ids if c in valid_entity_ids]
                hallucinated_cards = [c for c in card_ids if c not in valid_entity_ids]
                f["card_ids"] = verified_cards
                if hallucinated_cards:
                    f["_hallucinated_cards"] = hallucinated_cards
            if isinstance(article_ids, list):
                verified_articles = [a for a in article_ids if a in valid_article_ids]
                hallucinated_articles = [a for a in article_ids if a not in valid_article_ids]
                f["article_ids"] = verified_articles
                if hallucinated_articles:
                    f["_hallucinated_articles"] = hallucinated_articles

    # 验证 card_connections
    connections = report.get("card_connections", [])
    if isinstance(connections, list):
        verified_connections = []
        hallucinated_connections = []
        for c in connections:
            if not isinstance(c, dict):
                continue
            cid = c.get("card_id", "")
            if cid in valid_entity_ids:
                verified_connections.append(c)
            else:
                hallucinated_connections.append(c)
        report["card_connections"] = verified_connections
        if hallucinated_connections:
            report["_hallucinated_connections"] = hallucinated_connections

    return report


def _enrich_report(report: dict, entities: list[dict], articles: list[dict]) -> dict:
    """用实际数据库中的实体/文章信息丰富报告引用。

    将 card_connections 中的 card_id 替换为包含实际数据的对象，
    将 timeline 中的 source 关联到实际实体。
    """
    if not isinstance(report, dict):
        return report

    entity_map = {e["id"]: e for e in entities}
    article_map = {a["id"]: a for a in articles}

    # 丰富 card_connections
    connections = report.get("card_connections", [])
    if isinstance(connections, list):
        for c in connections:
            if not isinstance(c, dict):
                continue
            cid = c.get("card_id", "")
            if cid in entity_map:
                ent = entity_map[cid]
                c["card_name"] = c.get("card_name") or ent.get("name", "")
                c["card_type"] = ent.get("type", "")
                c["card_summary"] = (ent.get("summary") or "")[:200]

    # 丰富 timeline
    timeline = report.get("timeline", [])
    if isinstance(timeline, list):
        for entry in timeline:
            if not isinstance(entry, dict):
                continue
            source = entry.get("source", "")
            # 尝试匹配 entity
            for eid, ent in entity_map.items():
                if eid in source or ent.get("name", "") in source:
                    entry["_source_entity"] = {
                        "id": eid, "name": ent.get("name"), "type": ent.get("type")
                    }
                    break

    # 丰富 key_findings 中的引用
    findings = report.get("key_findings", [])
    if isinstance(findings, list):
        for f in findings:
            if not isinstance(f, dict):
                continue
            card_ids = f.get("card_ids", [])
            if isinstance(card_ids, list):
                f["_card_refs"] = [
                    {"id": cid, "name": entity_map[cid].get("name", cid)}
                    for cid in card_ids if cid in entity_map
                ]
            article_ids = f.get("article_ids", [])
            if isinstance(article_ids, list):
                f["_article_refs"] = [
                    {"id": aid, "title": article_map[aid].get("title", aid)}
                    for aid in article_ids if aid in article_map
                ]

    return report


def generate_research_report(topic: str, depth: str = "standard", lang: str = "zh") -> dict:
    """生成结构化研究报告，返回 ``report`` 或 ``error``。

    V2 增强：
    - 搜索匹配实体后遍历知识图谱邻居（深度=depth 对应 1-2 跳）
    - 注入实体间关系上下文到 AI prompt
    - 验证 AI 返回的引用真实性，剔除幻觉 card_id/article_id
    - 用实际数据库信息丰富报告引用
    """
    from .ai_client import call_ai
    from .database import init_db, search, get_entity_neighbors

    init_db()
    if not topic or not topic.strip():
        return {"error": t("research_no_results", lang)}

    entity_limit = 10 if depth == "standard" else 20
    article_limit = 15 if depth == "standard" else 30
    neighbor_depth = 1 if depth == "standard" else 2

    search_result = search(topic, limit=max(entity_limit, article_limit), semantic=True)
    entities = search_result.get("entities", [])[:entity_limit]
    articles = search_result.get("articles", [])[:article_limit]

    if not entities and not articles:
        return {"error": t("research_no_results", lang)}

    # ── 知识图谱扩展：遍历邻居 ──
    seed_ids = [e.get("id", "") for e in entities]
    neighbor_map: dict[str, dict] = {}
    if seed_ids:
        for eid in seed_ids:
            neighbors = get_entity_neighbors(eid, max_depth=neighbor_depth)
            for n in neighbors:
                n_entity = n.get("entity", {})
                nid = n_entity.get("id", "")
                if nid and nid not in seed_ids:
                    neighbor_map[nid] = n

    # 合并种子实体 + 邻居（去重，优先保留种子实体详情）
    all_entity_ids = set(seed_ids) | set(neighbor_map.keys())
    expanded_entities = list(entities)
    seen_ids = set(seed_ids)
    for nid, ndata in neighbor_map.items():
        if nid not in seen_ids:
            seen_ids.add(nid)
            expanded_entities.append(ndata["entity"])

    # ── 构建上下文 ──
    card_context = _build_card_context(expanded_entities)
    relation_context = _build_relation_context(list(all_entity_ids), expanded_entities)
    article_context = _build_article_context(articles)

    system_prompt = _load_research_prompt()
    system_prompt = system_prompt.replace("$KNOWLEDGE_CARDS", card_context)
    system_prompt = system_prompt.replace("$ENTITY_RELATIONS", relation_context)
    system_prompt = system_prompt.replace("$RELATED_ARTICLES", article_context)
    system_prompt = system_prompt.replace("$RESEARCH_TOPIC", topic)

    user_prompt = (
        f"请对以下主题进行深度研究：{topic}\n\n研究深度: {depth}\n"
        f"语言: {'中文' if lang == 'zh' else 'English'}\n\n"
        "请在 card_connections 中引用上述知识卡片中真实存在的 card_id，不要编造不存在的 ID。"
    )

    result = call_ai(system_prompt, user_prompt, temperature=0.3, max_tokens=4096)
    if result is None:
        return {"error": t("research_ai_error", lang)}

    if isinstance(result, list) and result:
        report = result[0]
    elif isinstance(result, dict):
        report = result
    else:
        report = {}

    # ── 引用溯源验证 ──
    valid_entity_ids = {e.get("id", "") for e in expanded_entities}
    valid_article_ids = {a.get("id", "") for a in articles}
    report = _verify_citations(report, valid_entity_ids, valid_article_ids)

    # ── 响应丰富化 ──
    report = _enrich_report(report, expanded_entities, articles)

    # ── 元数据 ──
    report["_meta"] = {
        "topic": topic,
        "depth": depth,
        "entity_count": len(entities),
        "expanded_entity_count": len(expanded_entities),
        "neighbor_count": len(neighbor_map),
        "article_count": len(articles),
    }
    report["_entities"] = expanded_entities
    report["_articles"] = articles

    return {"report": report}
