"""
AI News - Knowledge Card 加载与匹配

加载 data/knowledge/ 下的 YAML 卡片，根据文章关键词匹配相关卡片，
用于在日报生成时注入历史背景。
"""

import re
from pathlib import Path
from typing import Optional

import yaml

from .fetcher import Article
from .utils import log, ROOT_DIR

CARDS_DIR = ROOT_DIR / "data" / "knowledge"


# ============================================================
# 知识卡片数据模型
# ============================================================

class KnowledgeCard:
    """一张知识卡片的内存表示。"""

    def __init__(self, raw: dict):
        self.id: str = raw.get("id", "")
        self.name: str = raw.get("name", "")
        self.type: str = raw.get("type", "")
        self.tags: list[str] = raw.get("tags", [])
        self.aliases: list[str] = raw.get("aliases", [])
        self.summary: str = raw.get("summary", "").strip()
        self.significance: str = raw.get("significance", "").strip()
        self.importance: int = raw.get("importance", 0)
        self.related: list[str] = raw.get("related", [])
        self.depends_on: list[str] = raw.get("depends_on", [])
        self.influenced: list[str] = raw.get("influenced", [])
        self.company: str = raw.get("company", "")
        self.timeline: list[dict] = raw.get("timeline", [])
        self._raw = raw

    @property
    def match_surface(self) -> set[str]:
        """匹配面：tags + aliases + name，全部小写。"""
        surface: set[str] = set()
        surface.update(t.lower().strip() for t in self.tags)
        surface.update(a.lower().strip() for a in self.aliases)
        surface.add(self.name.lower().strip())
        return surface

    def context_block(self) -> str:
        """生成注入 prompt 的上下文片段——叙述性风格，方便 AI 自然引用。"""
        lines = [f"### {self.name}"]
        if self.summary:
            lines.append(f"{self.summary}")
        if self.significance:
            sig = self.significance.replace("\n", " ").strip()
            sentences = sig.split("。")
            key_sentences = "。".join(sentences[:3]) + ("。" if len(sentences) > 3 else "")
            lines.append(f"为什么重要: {key_sentences}")
        if self.timeline:
            key_milestones = [
                f"{t.get('date','')} {t.get('event','')}"
                for t in self.timeline
                if t.get("event") and len(t.get("event", "")) > 10
            ][-4:]
            if key_milestones:
                lines.append(f"关键时间线: {' | '.join(key_milestones)}")
        if self.company:
            lines.append(f"所属组织: {self.company}")
        return "\n".join(lines)


# ============================================================
# 加载
# ============================================================

# 卡片必填字段（★★★）
REQUIRED_FIELDS = ["id", "name", "type", "tags", "summary", "significance"]

# 推荐字段（★★☆）— 全局推荐
RECOMMENDED_FIELDS_ALL = ["importance", "related"]

# 推荐字段 — 按 type 区分，避免对不适用的类型误报警告
RECOMMENDED_BY_TYPE: dict[str, list[str]] = {
    "model":       ["release_date", "company", "timeline"],
    "product":     ["release_date", "company", "timeline"],
    "person":      ["company", "timeline"],
    "event":       ["release_date", "timeline"],
    "paper":       ["release_date", "timeline"],
    "company":     ["timeline"],
    "tech":        ["release_date", "timeline"],
    "concept":     ["release_date", "timeline"],
    "methodology": [],
    "dataset":     ["release_date"],
    "benchmark":   ["release_date"],
    "opensource":  ["release_date", "timeline"],
}

# 合法 type 值
VALID_TYPES = {"model", "company", "tech", "concept", "product", "person", "event",
               "methodology", "paper", "dataset", "benchmark", "opensource"}


def _validate_card(raw: dict, source: str) -> list[str]:
    """校验单张卡片，返回问题列表（空 = 合格）。"""
    issues: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in raw or not raw[field]:
            issues.append(f"缺少必填字段: {field}")
        elif field == "tags" and (not isinstance(raw["tags"], list) or len(raw["tags"]) == 0):
            issues.append(f"tags 必须是非空列表")

    if raw.get("type") and raw["type"] not in VALID_TYPES:
        issues.append(f"未知 type: {raw['type']}")

    for field in RECOMMENDED_FIELDS_ALL:
        if field not in raw or not raw[field]:
            issues.append(f"建议填写: {field}")

    # 按实体类型的推荐字段
    entity_type = raw.get("type", "")
    type_specific_fields = RECOMMENDED_BY_TYPE.get(entity_type, [])
    for field in type_specific_fields:
        if field not in raw or not raw[field]:
            issues.append(f"建议填写: {field}")

    if raw.get("importance") is not None:
        imp = raw["importance"]
        if not isinstance(imp, (int, float)) or imp < 1 or imp > 5:
            issues.append(f"importance 应在 1-5 之间，当前: {imp}")

    if raw.get("aliases") is not None and not isinstance(raw["aliases"], list):
        issues.append("aliases 必须是列表")

    if raw.get("related") is not None and not isinstance(raw["related"], list):
        issues.append("related 必须是列表")

    if raw.get("depends_on") is not None and not isinstance(raw["depends_on"], list):
        issues.append("depends_on 必须是列表")

    if raw.get("influenced") is not None and not isinstance(raw["influenced"], list):
        issues.append("influenced 必须是列表")

    return issues


def load_cards(cards_dir: Optional[Path] = None) -> list[KnowledgeCard]:
    """加载所有知识卡片，自动校验格式。"""
    if cards_dir is None:
        cards_dir = CARDS_DIR
    cards: list[KnowledgeCard] = []
    all_issues: dict[str, list[str]] = {}

    if not cards_dir.exists():
        log.warning(f"知识卡片目录不存在: {cards_dir}")
        return cards

    for f in sorted(cards_dir.rglob("*.yaml")):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                raw = yaml.safe_load(fh)
            if not raw or not raw.get("id"):
                log.warning(f"跳过无效卡片 {f.name}: 缺少 id")
                continue

            issues = _validate_card(raw, f.name)
            if issues:
                all_issues[f.name] = issues

            cards.append(KnowledgeCard(raw))
        except (yaml.YAMLError, OSError) as e:
            log.warning(f"跳过损坏的卡片 {f.name}: {e}")

    # 汇报校验结果
    errors = {k: v for k, v in all_issues.items() if any("缺少" in i or "未知" in i or "必须" in i for i in v)}
    warnings = {k: v for k, v in all_issues.items() if k not in errors}

    if errors:
        log.warning(f"卡片校验: {len(errors)} 张有错误:")
        for name, issues in errors.items():
            log.warning(f"  [{name}] {'; '.join(issues)}")

    if warnings:
        log.info(f"卡片校验: {len(warnings)} 张缺少推荐字段 (不影响加载)")

    log.debug(f"加载 {len(cards)} 张知识卡片, {len(errors)} 错误, {len(warnings)} 警告")
    return cards


# ============================================================
# 匹配
# ============================================================

def _extract_keywords(article: Article) -> set[str]:
    """从文章中提取用于匹配的关键词集合。"""
    keywords: set[str] = set()
    # 分类标签
    for cat in article.categories:
        keywords.add(cat.lower().strip())
    # 标题中的有意义的词（≥3 字符，过滤常见停用词）
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "has", "have", "had", "do", "does", "did", "will", "would",
        "can", "could", "may", "might", "shall", "should", "to",
        "of", "in", "for", "on", "with", "at", "by", "from", "as",
        "it", "its", "and", "or", "not", "but", "that", "this",
        "what", "how", "why", "who", "when", "where", "which",
        "new", "more", "about", "after", "just", "only", "also",
        "into", "over", "than", "then", "now", "out", "up", "one",
        "says", "said", "like", "make", "made", "use", "used",
        "set", "get", "got", "put", "see", "way", "ai",
        "first", "still", "even", "much", "many", "back", "could",
        "next", "last", "well", "two", "three",
    }
    words = re.findall(r"[a-zA-Z一-鿿0-9]+", article.title)
    for w in words:
        wl = w.lower().strip()
        if len(wl) >= 3 and wl not in stopwords:
            keywords.add(wl)
    # 来源名称
    keywords.add(article.source.lower().strip())
    return keywords


def match_cards(
    articles: list[Article],
    cards: list[KnowledgeCard],
    min_score: float = 0.1,
    max_per_article: int = 3,
    use_semantic: bool = True,
) -> dict[str, list[KnowledgeCard]]:
    """
    为每篇文章匹配最相关的知识卡片。

    算法：优先语义相似度（cosine），嵌入表为空时 fallback 到 Jaccard。

    返回 {article_id: [matched_cards, ...]}。
    """
    if not cards:
        return {}

    # 语义匹配优先
    if use_semantic:
        from .embeddings import match_cards_semantic, get_all_embeddings
        stored = get_all_embeddings()
        if stored:
            semantic_result = match_cards_semantic(
                articles, cards,
                min_score=max(0.3, min_score),
                max_per_article=max_per_article,
            )
            # 即使部分文章未匹配也使用语义结果（可能全部不相关）
            hits = sum(1 for v in semantic_result.values() if v)
            log.debug(f"卡片匹配 (semantic): {hits}/{len(articles)} 篇文章找到关联卡片")
            return semantic_result
        log.debug("嵌入表为空，回退到 Jaccard 匹配")

    # Jaccard fallback
    result: dict[str, list[KnowledgeCard]] = {}

    for article in articles:
        keywords = _extract_keywords(article)
        if not keywords:
            result[article.id] = []
            continue

        scored: list[tuple[float, KnowledgeCard]] = []

        for card in cards:
            # 快速跳过：完全没有交集
            overlap = keywords & card.match_surface
            if not overlap:
                continue

            denominator = max(1, min(len(keywords), len(card.match_surface)))
            score = len(overlap) / denominator

            if score >= min_score:
                scored.append((score, card))

        scored.sort(key=lambda x: x[0], reverse=True)
        result[article.id] = [c for _, c in scored[:max_per_article]]

    hits = sum(1 for v in result.values() if v)
    log.debug(f"卡片匹配: {hits}/{len(articles)} 篇文章找到关联卡片")
    return result


def build_context(
    matched: dict[str, list[KnowledgeCard]],
    max_cards_total: int = 5,
) -> str:
    """
    将匹配结果构建为纯文本上下文块，注入 AI prompt。
    按 importance 排序，去重，限制总数。
    """
    seen: set[str] = set()
    cards: list[KnowledgeCard] = []
    for card_list in matched.values():
        for c in card_list:
            if c.id not in seen:
                seen.add(c.id)
                cards.append(c)

    cards.sort(key=lambda c: c.importance, reverse=True)
    cards = cards[:max_cards_total]

    if not cards:
        return ""

    blocks = ["## 历史背景（自动匹配的知识卡片）", ""]
    blocks.append("以下信息可以帮助你理解新闻的背景。如果相关，请在摘要中自然提及（而非生硬插入）：")
    blocks.append("")
    blocks.append("引用示例：")
    blocks.append("- \"这是继 [某模型] 之后，OpenAI 在 [某领域] 的又一次迭代\"")
    blocks.append("- \"与 [某公司] 的路线不同，这次发布更侧重……\"")
    blocks.append("- \"相比 [某技术] 的历史路径，新方案在 [某方面] 做了改进\"")
    blocks.append("- 不相关则忽略，不要强行引用")
    blocks.append("")
    for c in cards:
        blocks.append(c.context_block())
        blocks.append("")

    return "\n".join(blocks)
