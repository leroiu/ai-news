"""
AI Intelligence Platform — 国际化 (i18n) 翻译表

所有页面通过此模块获取多语言文本。
生成的页面包含完整的 zh/en 翻译作为 JS 对象，切换语言不刷新页面。
"""

import json
from typing import Optional

# UI 文本翻译表
I18N: dict[str, dict[str, str]] = {
    # ── Dashboard ──
    "platform_title":     {"zh": "AI 观察室", "en": "AI Observatory"},
    "platform_subtitle":  {"zh": "在信息噪音中，持续理解 AI 的真实变化。", "en": "Understand what is really changing in AI, beyond the noise."},
    "platform_description": {"zh": "一份面向长期主义者的 AI 观察、研究与知识沉淀空间。", "en": "An AI observation, research, and knowledge-compounding space for long-term thinkers."},
    "today":              {"zh": "今日", "en": "Today"},
    "topics":             {"zh": "专题", "en": "Topics"},
    "my":                 {"zh": "我的", "en": "My"},
    "dashboard":          {"zh": "今日", "en": "Today"},
    "library":            {"zh": "专题", "en": "Topics"},
    "graph":              {"zh": "图谱", "en": "Graph"},
    "timeline":           {"zh": "时间线", "en": "Timeline"},
    "events":             {"zh": "里程碑", "en": "Milestones"},
    "reports":            {"zh": "报告", "en": "Reports"},
    "research":           {"zh": "研究", "en": "Research"},
    "loading":            {"zh": "加载中...", "en": "Loading..."},
    "loading_reports":    {"zh": "正在加载报告...", "en": "Loading reports..."},
    "report_center":      {"zh": "报告中心", "en": "Report Center"},
    "today_daily":        {"zh": "今日日报", "en": "Today's Daily"},
    "not_generated_yet":  {"zh": "尚未生成", "en": "Not generated yet"},
    "read_daily":         {"zh": "阅读日报", "en": "Read Daily"},
    "latest_weekly":      {"zh": "最新周报", "en": "Latest Weekly"},
    "read_weekly":        {"zh": "阅读周报", "en": "Read Weekly"},
    "latest_monthly":     {"zh": "最新月报", "en": "Latest Monthly"},
    "read_monthly":       {"zh": "阅读月报", "en": "Read Monthly"},
    "headlines":          {"zh": "头条新闻", "en": "Headlines"},
    "star5_headlines":    {"zh": "★5 头条", "en": "★5 Headlines"},
    "star4_highlights":   {"zh": "★4 亮点", "en": "★4 Highlights"},
    "kb_title":           {"zh": "知识库", "en": "Knowledge Base"},
    "entities_label":     {"zh": "实体", "en": "Entities"},
    "types_label":        {"zh": "类型", "en": "Types"},
    "browse_kb":          {"zh": "浏览知识库", "en": "Browse Library"},
    "data_pipeline":      {"zh": "数据管道", "en": "Data Pipeline"},
    "articles_label":     {"zh": "文章", "en": "Articles"},
    "reports_label":      {"zh": "报告", "en": "Reports"},
    "pipeline_desc":      {"zh": "采集器每小时 · 管道每天", "en": "Collector hourly · Pipeline daily"},
    "report_history":     {"zh": "报告历史", "en": "Report History"},
    "recent_reports":     {"zh": "最近报告", "en": "Recent Reports"},
    "view_all_reports":   {"zh": "查看全部报告", "en": "View All Reports"},
    "all_label":          {"zh": "全部", "en": "All"},
    "no_reports_found":   {"zh": "未找到报告", "en": "No reports found"},
    "view_report":        {"zh": "查看报告", "en": "View Report"},
    "core_entities":      {"zh": "核心实体", "en": "Core Entities"},
    "footer_text":        {"zh": "AI 观察室", "en": "AI Observatory"},
    "entities_count_fmt": {"zh": "{n} 实体 · {m} 文章 · {r} 关系", "en": "{n} entities · {m} articles · {r} relationships"},
    "rating_3plus":       {"zh": "评分≥3", "en": "Rating ≥3"},
    "fetch_count":        {"zh": "抓取", "en": "Fetched"},

    # ── Library ──
    "library_title":      {"zh": "知识资产库", "en": "Knowledge Library"},
    "type_filter_all":    {"zh": "全部", "en": "All"},
    "search_placeholder": {"zh": "搜索实体...", "en": "Search entities..."},
    "semantic_search":    {"zh": "语义搜索已启用", "en": "Semantic search enabled"},
    "keyword_search":     {"zh": "关键词搜索", "en": "Keyword search"},
    "rebuilding":         {"zh": "重建嵌入中...", "en": "Rebuilding embeddings..."},
    "no_results":         {"zh": "未找到匹配的实体", "en": "No matching entities"},
    "show_all_entities":  {"zh": "查看全部 {n} 项", "en": "View all {n}"},
    "collapse_category":  {"zh": "收起", "en": "Collapse"},
    "importance_label":   {"zh": "重要度", "en": "Importance"},
    "timeline_label":     {"zh": "时间线", "en": "Timeline"},
    "related_label":      {"zh": "关联", "en": "Related"},
    "no_related":         {"zh": "暂无关联", "en": "No relations"},
    "aliases_label":      {"zh": "别名", "en": "Aliases"},
    "tags_label":         {"zh": "标签", "en": "Tags"},
    "source_label":       {"zh": "来源", "en": "Source"},
    "detail_title":       {"zh": "实体详情", "en": "Entity Detail"},
    "back_to_list":       {"zh": "← 返回列表", "en": "← Back to list"},
    "background_label":   {"zh": "背景", "en": "Background"},
    "known_for_label":    {"zh": "知名于", "en": "Known for"},
    "view_detail":        {"zh": "查看详情", "en": "View Details"},
    "click_to_expand":    {"zh": "点击展开", "en": "Click to expand"},
    "summary_label":      {"zh": "摘要", "en": "Summary"},

    # ── Graph ──
    "graph_title":        {"zh": "AI 知识图谱", "en": "AI Knowledge Graph"},
    "graph_legend":       {"zh": "图例", "en": "Legend"},
    "graph_2d_mode":      {"zh": "2D 视图", "en": "2D View"},
    "graph_stats":        {"zh": "节点: {n} · 边: {e}", "en": "Nodes: {n} · Edges: {e}"},
    "detail_panel_title": {"zh": "详情", "en": "Details"},
    "select_node_hint":   {"zh": "选择节点查看详情", "en": "Select a node to view details"},
    "no_description":     {"zh": "暂无描述", "en": "No description"},

    # ── Timeline ──
    "timeline_title":     {"zh": "AI 行业时间线", "en": "AI Industry Timeline"},
    "year_distribution":  {"zh": "年份分布", "en": "Year Distribution"},
    "type_filter":        {"zh": "类型筛选", "en": "Type Filter"},
    "entities_count":     {"zh": "{n} 个实体", "en": "{n} entities"},
    "no_timeline_data":   {"zh": "没有日期数据", "en": "No timeline data"},
    "clear":              {"zh": "清除", "en": "Clear"},
    "no_date":            {"zh": "无日期", "en": "No date"},
    "jump_to":            {"zh": "跳转到", "en": "Jump to"},
    "total_label":        {"zh": "总计", "en": "Total"},
    "years_label":        {"zh": "年份", "en": "Years"},
    "range_label":        {"zh": "范围", "en": "Range"},

    # ── Milestone Events ──
    "events_title":       {"zh": "AI 里程碑事件", "en": "AI Milestone Events"},
    "events_eyebrow":     {"zh": "塑造人工智能的历史时刻", "en": "Moments That Shaped AI"},
    "events_subtitle":    {"zh": "沿时间脉络回顾改变技术、产业与社会认知的关键突破。", "en": "Trace the breakthroughs that changed technology, industry, and society."},
    "events_search_placeholder": {"zh": "搜索事件、摘要或意义…", "en": "Search events, summaries, or significance…"},
    "events_year_filter": {"zh": "按年份筛选", "en": "Filter by year"},
    "events_all_years":   {"zh": "全部年份", "en": "All years"},
    "events_count":       {"zh": "{n} 个事件", "en": "{n} events"},
    "events_empty":       {"zh": "没有匹配的里程碑事件", "en": "No matching milestone events"},
    "events_empty_hint":  {"zh": "请调整搜索词或年份筛选。", "en": "Try another search or year filter."},
    "events_unknown_date": {"zh": "日期未知", "en": "Unknown date"},
    "events_expand":      {"zh": "展开详情 ↓", "en": "Expand details ↓"},
    "events_significance": {"zh": "历史意义", "en": "Significance"},
    "events_background":  {"zh": "事件背景", "en": "Background"},
    "events_related":     {"zh": "关联实体", "en": "Related entities"},
    "events_no_background": {"zh": "暂无背景资料", "en": "No background available"},
    "events_no_relations": {"zh": "暂无关联实体", "en": "No related entities"},

    # ── Reports ──
    "reports_title":      {"zh": "分析报告", "en": "Analysis Reports"},
    "reports_subtitle":   {"zh": "日报、周报与月报——AI 情报的系统化沉淀。", "en": "Daily, weekly and monthly reports — systemized AI intelligence."},
    "reports_daily":      {"zh": "日报", "en": "Daily Reports"},
    "reports_weekly":     {"zh": "周报", "en": "Weekly Reports"},
    "reports_monthly":    {"zh": "月报", "en": "Monthly Reports"},

    # ── Entity Page ──
    "entity_page_title":  {"zh": "实体: {name}", "en": "Entity: {name}"},
    "not_found":          {"zh": "未找到实体", "en": "Entity not found"},
    "back_home":          {"zh": "← 返回首页", "en": "← Back to home"},
    "relationships_label": {"zh": "关系", "en": "Relationships"},
    "show_all_relationships": {"zh": "查看全部 {n} 条关系", "en": "Show all {n} relationships"},
    "collapse_relationships": {"zh": "收起关系", "en": "Collapse relationships"},
    "back_label":         {"zh": "← 返回", "en": "← Back"},

    # ── Common ──
    "lang_toggle":        {"zh": "EN", "en": "中文"},
    "lang_label":         {"zh": "语言", "en": "Language"},
    "api_error":          {"zh": "数据加载失败", "en": "Data load failed"},
    "star":               {"zh": "★", "en": "★"},
    "no_data":            {"zh": "暂无数据", "en": "No data"},
    "retry":              {"zh": "重试", "en": "Retry"},
    "error_loading":      {"zh": "数据加载失败", "en": "Failed to load data"},
    "network_error":      {"zh": "网络连接失败，请检查服务是否运行", "en": "Network error, check if the server is running"},
    "back_to_home":       {"zh": "← 返回首页", "en": "← Back to home"},
    "skip_to_content":    {"zh": "跳到主要内容", "en": "Skip to main content"},
    "favorite":           {"zh": "收藏", "en": "Save"},
    "favorited":          {"zh": "已收藏", "en": "Saved"},
    "favorite_saved":     {"zh": "已加入我的收藏", "en": "Saved to My"},
    "favorite_removed":   {"zh": "已取消收藏", "en": "Removed from saved items"},
    "sync_pending":       {"zh": "账号同步待接入", "en": "Account sync pending"},

    # ── Entity Detail ──
    "related_articles":   {"zh": "相关文章", "en": "Related Articles"},
    "similar_entities":   {"zh": "相似实体", "en": "Similar Entities"},
    "card_metadata":      {"zh": "卡片信息", "en": "Card Info"},
    "created_at":         {"zh": "创建时间", "en": "Created"},
    "updated_at":         {"zh": "更新时间", "en": "Updated"},
    "score_label":        {"zh": "评分", "en": "Score"},
    "editorial_rating_label": {"zh": "平台重要性评级", "en": "Editorial importance rating"},
    "editorial_rating_help": {"zh": "平台依据影响范围、来源质量、关联对象与潜在后续影响给出的筛选参考，不代表用户评分。", "en": "An editorial signal based on impact, source quality, connections, and potential follow-up impact; it is not a user rating."},
    "evidence_fact":      {"zh": "事实", "en": "Fact"},
    "evidence_analysis":  {"zh": "分析", "en": "Analysis"},
    "evidence_inference": {"zh": "推测", "en": "Inference"},
    "evidence_advice":    {"zh": "建议", "en": "Advice"},
    "state_loading":      {"zh": "正在加载", "en": "Loading"},
    "state_processing":   {"zh": "正在处理", "en": "Processing"},
    "state_empty":        {"zh": "暂无数据", "en": "No data"},
    "state_error":        {"zh": "加载失败", "en": "Failed to load"},
    "state_pending":      {"zh": "等待接入", "en": "Pending integration"},
    "state_unavailable":  {"zh": "当前不可用", "en": "Currently unavailable"},
    "read_more":          {"zh": "阅读原文", "en": "Read more"},
    "no_related_articles": {"zh": "暂无相关文章", "en": "No related articles"},
    "no_similar_entities": {"zh": "暂无相似实体", "en": "No similar entities"},
    "similarity_score":   {"zh": "相似度", "en": "Similarity"},
    "creators_label":    {"zh": "创建者", "en": "Creators"},
    "show_timeline":     {"zh": "时间线视图", "en": "Show Timeline"},
    "hide_timeline":     {"zh": "收起时间线", "en": "Hide Timeline"},

    # ── Health Panel ──
    "health_title":       {"zh": "系统健康", "en": "System Health"},
    "health_ok":          {"zh": "运行正常", "en": "Healthy"},
    "health_warn":        {"zh": "需关注", "en": "Warning"},
    "health_error":       {"zh": "异常", "en": "Error"},
    "health_no_data":     {"zh": "暂无运行记录", "en": "No run history"},
    "health_last_pipeline": {"zh": "最近管道", "en": "Last Pipeline"},
    "health_last_collector": {"zh": "最近采集", "en": "Last Collector"},
    "health_success_rate": {"zh": "24h 成功率", "en": "24h Success Rate"},
    "health_db_stats":    {"zh": "数据规模", "en": "Data Scale"},
    "health_duration":    {"zh": "耗时", "en": "Duration"},
    "health_processed":   {"zh": "处理", "en": "Processed"},
    "health_running":     {"zh": "运行中", "en": "Running"},
    "health_success":     {"zh": "成功", "en": "Success"},
    "health_dry_run":     {"zh": "试运行", "en": "Dry Run"},

    # ── Filter labels ──
    "filter_daily":       {"zh": "日报", "en": "Daily"},
    "filter_weekly":      {"zh": "周报", "en": "Weekly"},
    "filter_monthly":     {"zh": "月报", "en": "Monthly"},

    # ── Research Assistant ──
    "research_title":           {"zh": "深度研究助手", "en": "Research Assistant"},
    "research_subtitle":        {"zh": "基于知识库的 AI 驱动深度研究——输入话题，自动收集、分析、生成结构化报告。", "en": "AI-powered deep research based on your knowledge base — enter a topic, auto-collect, analyze, and generate structured reports."},
    "research_topic_label":     {"zh": "研究主题", "en": "Research Topic"},
    "research_placeholder":     {"zh": "输入你想深入研究的话题，例如：AI Agent 的最新进展、大模型安全对齐技术...", "en": "Enter a topic for deep research, e.g.: Latest advances in AI Agents, LLM safety alignment..."},
    "research_start":           {"zh": "开始研究", "en": "Start Research"},
    "research_depth_standard":  {"zh": "标准深度 (15篇+10卡片)", "en": "Standard (15 articles + 10 cards)"},
    "research_depth_deep":      {"zh": "深度 (30篇+20卡片)", "en": "Deep (30 articles + 20 cards)"},
    "research_agent_mode":      {"zh": "Agent 多轮探索", "en": "Agent multi-round exploration"},
    "research_generating":      {"zh": "正在生成研究报告...（约30-60秒）", "en": "Generating research report... (~30-60s)"},
    "research_done":            {"zh": "✓ 报告已生成", "en": "✓ Report generated"},
    "research_summary":         {"zh": "研究概述", "en": "Summary"},
    "research_key_findings":    {"zh": "核心发现", "en": "Key Findings"},
    "research_cards":           {"zh": "知识卡片关联", "en": "Knowledge Card Connections"},
    "research_timeline":        {"zh": "发展时间线", "en": "Development Timeline"},
    "research_further":         {"zh": "进一步探索", "en": "Further Reading"},
    "research_ref_entities":    {"zh": "引用实体", "en": "Referenced Entities"},
    "research_no_results":      {"zh": "未找到相关知识卡片或文章。请尝试更具体的关键词。", "en": "No relevant knowledge cards or articles found. Try a more specific topic."},
    "research_ai_error":        {"zh": "AI 研究报告生成失败，请稍后重试。", "en": "AI research report generation failed. Please try again later."},
    "research_eyebrow":         {"zh": "Research Workspace", "en": "Research Workspace"},
    "research_brief_title":     {"zh": "定义研究任务", "en": "Define the research brief"},
    "research_depth_label":     {"zh": "研究深度", "en": "Research depth"},
    "research_process_title":   {"zh": "研究如何完成", "en": "How research works"},
    "research_step_retrieve":   {"zh": "检索证据", "en": "Retrieve evidence"},
    "research_step_retrieve_desc": {"zh": "从知识卡片与文章中定位相关材料。", "en": "Find relevant knowledge cards and articles."},
    "research_step_analyze":    {"zh": "交叉分析", "en": "Cross-analyze"},
    "research_step_analyze_desc": {"zh": "比较观点、时间和实体关系。", "en": "Compare claims, timelines, and entity relationships."},
    "research_step_synthesize": {"zh": "形成报告", "en": "Synthesize report"},
    "research_step_synthesize_desc": {"zh": "生成结构化结论与进一步探索方向。", "en": "Produce structured findings and next questions."},
    "research_scope_note":      {"zh": "报告基于当前本地知识库，不代表完整互联网检索结果。", "en": "Reports reflect the current local knowledge base, not the entire web."},
    "research_output_title":    {"zh": "研究结果将在这里形成", "en": "Your research report will appear here"},
    "research_output_desc":     {"zh": "输入明确的问题，系统将组织证据、关键发现、关联知识与发展时间线。", "en": "Ask a focused question to organize evidence, findings, connections, and a timeline."},
    "research_topic_required":  {"zh": "请输入一个明确的研究主题。", "en": "Enter a focused research topic."},
    "research_generating_short": {"zh": "研究中…", "en": "Researching…"},
    "research_report_label":    {"zh": "Research Report", "en": "Research Report"},
    "depth":                    {"zh": "深度", "en": "Depth"},

    # ── My Workspace ──
    "my_title":                 {"zh": "我的沉淀", "en": "My Library"},
    "my_subtitle":              {"zh": "收藏、分类与标签会在这里成为长期可回看的个人资产。", "en": "Saved items, categories, and tags become your long-term personal knowledge assets here."},
    "my_eyebrow":               {"zh": "Personal Workspace", "en": "Personal Workspace"},
    "my_favorites":             {"zh": "我的收藏", "en": "Saved Items"},
    "my_overview":              {"zh": "收藏概览", "en": "Saved Overview"},
    "my_saved_count":           {"zh": "收藏内容", "en": "Saved items"},
    "my_type_count":            {"zh": "内容类型", "en": "Content types"},
    "my_revisit":               {"zh": "回看", "en": "Open"},
    "my_remove":                {"zh": "移除", "en": "Remove"},
    "all_label":                {"zh": "全部", "en": "All"},
    "favorite_type_news":       {"zh": "新闻", "en": "News"},
    "favorite_type_entity":     {"zh": "专题", "en": "Topic"},
    "favorite_type_event":      {"zh": "事件", "en": "Event"},
    "favorite_type_timeline":   {"zh": "时间线", "en": "Timeline"},
    "favorite_type_report":     {"zh": "报告", "en": "Report"},
    "favorite_type_research":   {"zh": "研究", "en": "Research"},
    "favorite_type_item":       {"zh": "内容", "en": "Item"},
    "article_title":            {"zh": "资讯详情", "en": "Article Detail"},
    "article_eyebrow":          {"zh": "Intelligence Brief", "en": "Intelligence Brief"},
    "article_summary":          {"zh": "核心摘要", "en": "Key Summary"},
    "article_evidence":         {"zh": "证据与依据", "en": "Evidence"},
    "article_related":          {"zh": "关联专题", "en": "Related Topics"},
    "article_original":         {"zh": "阅读原文", "en": "Read Original"},
    "source_credibility":       {"zh": "来源可信度提示", "en": "Source credibility signal"},
    "source_high":              {"zh": "较高", "en": "Higher"},
    "source_medium":            {"zh": "中等", "en": "Medium"},
    "source_contextual":        {"zh": "线索来源", "en": "Context only"},
    "published_at":             {"zh": "原文发布时间", "en": "Published"},
    "collected_at":             {"zh": "平台抓取时间", "en": "Collected"},
    "reading_state":            {"zh": "阅读状态", "en": "Reading state"},
    "reading_unread":           {"zh": "未读", "en": "Unread"},
    "reading_read":             {"zh": "已读", "en": "Read"},
    "reading_later":            {"zh": "待回看", "en": "Read later"},
    "category_label":           {"zh": "分类", "en": "Category"},
    "tags_edit_label":          {"zh": "个人标签", "en": "Personal tags"},
    "uncategorized":            {"zh": "未分类", "en": "Uncategorized"},
    "category_learning":        {"zh": "学习", "en": "Learning"},
    "category_tools":           {"zh": "工具", "en": "Tools"},
    "category_research":        {"zh": "研究", "en": "Research"},
    "category_archive":         {"zh": "归档", "en": "Archive"},
    "personal_saved":           {"zh": "个人状态已保存", "en": "Personal state saved"},
    "report_reader_title":      {"zh": "报告阅读", "en": "Report Reader"},
    "report_reader_eyebrow":    {"zh": "Report Archive", "en": "Report Archive"},
    "report_toc":               {"zh": "目录", "en": "Contents"},
    "my_categories":            {"zh": "我的分类", "en": "My Categories"},
    "my_tags":                  {"zh": "我的标签", "en": "My Tags"},
    "my_sync_status":           {"zh": "账号同步状态", "en": "Sync Status"},
    "my_sync_pending_desc":     {"zh": "当前 MVP 仅提供前端收藏交互和入口；完整账号同步需要后端账号体系接入后启用。", "en": "The MVP currently provides front-end saving interactions and entry points; full account sync requires the future account backend."},
    "my_empty_favorites":       {"zh": "还没有收藏内容", "en": "No saved items yet"},
    "my_empty_favorites_desc":  {"zh": "后续所有新闻、报告、专题实体、时间线事件、里程碑事件和研究结果都应统一进入这里。", "en": "News, reports, topic entities, timeline events, milestones, and research results should all flow here."},
    "my_loop_title":            {"zh": "收藏闭环", "en": "Saving Loop"},
    "my_loop_desc":             {"zh": "看到内容 → 判断价值 → 收藏 → 添加分类/标签 → 我的收藏回看 → 从收藏进入专题、时间线或研究。", "en": "See content → judge value → save → add categories/tags → revisit in My → continue into Topics, Timeline, or Research."},
}

# 实体类型翻译
TYPE_LABELS_ZH: dict[str, str] = {
    "model": "Model（模型）", "company": "Company（公司）", "tech": "Technology（技术）",
    "concept": "Concept（概念）", "product": "Product（产品）", "person": "Person（人物）",
    "methodology": "Methodology（方法论）", "event": "Event（事件）",
    "paper": "Paper（论文）", "dataset": "Dataset（数据集）",
    "benchmark": "Benchmark（基准）", "opensource": "Open Source（开源项目）",
}
TYPE_LABELS_EN: dict[str, str] = {
    "model": "Model", "company": "Company", "tech": "Technology", "concept": "Concept",
    "product": "Product", "person": "Person", "methodology": "Methodology", "event": "Event",
    "paper": "Paper", "dataset": "Dataset", "benchmark": "Benchmark", "opensource": "Open Source",
}


def t(key: str, lang: str = "zh") -> str:
    """获取翻译文本。"""
    entry = I18N.get(key)
    if not entry:
        return key
    return entry.get(lang, entry.get("zh", key))


def type_label(entity_type: str, lang: str = "zh") -> str:
    """获取实体类型的中文/英文标签。"""
    if lang == "en":
        return TYPE_LABELS_EN.get(entity_type, entity_type)
    return TYPE_LABELS_ZH.get(entity_type, entity_type)


def i18n_js() -> str:
    """生成包含所有翻译的 JavaScript 代码块。
    注入到每个页面的 <script> 中，提供运行时翻译和语言切换能力。"""
    entries = []
    for key, trans in I18N.items():
        entries.append(f'"{key}":{json.dumps(trans, ensure_ascii=False)}')

    type_labels = []
    for k, v in TYPE_LABELS_ZH.items():
        type_labels.append(f'"{k}":{json.dumps({"zh": v, "en": TYPE_LABELS_EN.get(k, k)}, ensure_ascii=False)}')

    en_toggle = t("lang_toggle", "en")
    zh_toggle = t("lang_toggle", "zh")

    return f"""/* i18n — AI Intelligence Platform */
const I18N = {{{','.join(entries)}}};
const TL = {{{','.join(type_labels)}}};

function T(key, params) {{
  const entry = I18N[key];
  var text = entry ? (entry[(localStorage.getItem('lang')||'zh')] || entry['zh'] || key) : key;
  if (params) {{
    Object.keys(params).forEach(function(k) {{ text = text.replace(new RegExp('\\{{'+k+'\\}}', 'g'), params[k]); }});
  }}
  return text;
}}

function TLbl(type) {{
  const lang = localStorage.getItem('lang') || 'zh';
  const entry = TL[type];
  return entry ? (entry[lang] || entry['zh'] || type) : type;
}}

function switchLang() {{
  const cur = localStorage.getItem('lang') || 'zh';
  const next = cur === 'zh' ? 'en' : 'zh';
  localStorage.setItem('lang', next);
  applyI18n();
  // 重新加载动态数据 (刷新页面让 init() 重新运行)
  if (typeof init === 'function') init();
}}

function langLabel() {{
  const cur = localStorage.getItem('lang') || 'zh';
  return cur === 'zh' ? '{zh_toggle}' : '{en_toggle}';
}}

function applyI18n() {{
  document.documentElement.lang = localStorage.getItem('lang') || 'zh';
  document.querySelectorAll('[data-i18n]').forEach(function(el) {{
    var key = el.getAttribute('data-i18n');
    if (key) el.textContent = T(key);
  }});
  var btn = document.getElementById('lang-toggle');
  if (btn) btn.textContent = langLabel();
}}

// 初始化
if (!localStorage.getItem('lang')) localStorage.setItem('lang', 'zh');
if (document.readyState === 'loading') {{
  document.addEventListener('DOMContentLoaded', applyI18n);
}} else {{
  applyI18n();
}}
"""


def nav_html(current_page: str = "") -> str:
    """生成包含 data-i18n 属性的导航栏 HTML。"""
    pages = [
        ("/", "today"),
        ("/library", "topics"),
        ("/timeline", "timeline"),
        ("/research", "research"),
        ("/my", "my"),
    ]
    aliases = {
        "today": {"/", "dashboard", "today"},
        "topics": {"/library", "library", "topics", "graph"},
        "timeline": {"/timeline", "timeline", "/events", "events"},
        "research": {"/research", "research", "/reports", "reports"},
        "my": {"/my", "my"},
    }
    items = []
    for path, key in pages:
        cls = 'active' if current_page in aliases.get(key, {path, key}) or (current_page == "" and path == "/") else ''
        items.append(f'<a href="{path}" class="{cls}" data-i18n="{key}">{t(key, "zh")}</a>')

    theme_btn = '<button id="theme-toggle" onclick="toggleTheme()" class="lang-btn" title="Switch theme / 切换主题">☀️</button>'
    lang_btn = f'<button id="lang-toggle" onclick="switchLang()" class="lang-btn" title="Switch language / 切换语言">{t("lang_toggle", "zh")}</button>'

    return f'<div class="nav">{" ".join(items)}{theme_btn}{lang_btn}</div>'
