"""
AI Intelligence Platform — Timeline 页面组装器

generate_timeline() 负责将 CSS_TEMPLATE / JS_TEMPLATE 与 i18n 翻译、
导航栏等动态部分组装为完整的 HTML 页面。
使用共享设计系统 (frontend_styles.py)。
"""
from pathlib import Path
from typing import Optional

from src.engine.utils import log, ensure_dir, ROOT_DIR
from src.interfaces.i18n import t, i18n_js, nav_html, TYPE_LABELS_ZH
from .frontend_styles import TYPE_COLORS, TYPE_ICONS
from .timeline_data import C_JSON, I_JSON, CSS_TEMPLATE, JS_TEMPLATE


def generate_timeline(output_dir: Optional[Path] = None, lang: str = "zh") -> Path:
    if output_dir is None:
        output_dir = ROOT_DIR / "reports"
    ensure_dir(output_dir)

    filter_btns = "".join(
        f'<button class="filter-btn" data-type="{t}">{TYPE_ICONS.get(t, "")} {TYPE_LABELS_ZH.get(t, t)}</button>'
        for t in ["model", "company", "tech", "concept", "methodology", "product", "person"]
    )

    # 解析 JS 模板中的占位符
    js_code = JS_TEMPLATE.replace("__C_JSON__", C_JSON).replace("__I_JSON__", I_JSON)

    html = f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{t("platform_title", lang)} — {t("timeline_title", lang)}</title>
{CSS_TEMPLATE}
</head>
<body data-page-template="narrative">
<a class="skip-link" href="#main-content">{t("skip_to_content", lang)}</a>
<div class="top-bar">
{nav_html("/timeline")}
<header class="timeline-heading">
<h1 data-i18n="timeline_title">{t("timeline_title", lang)}</h1>
<p class="date" id="date-line">{t("loading", lang)}</p>
</header>
</div>
<main id="main-content">
<nav class="related-views" aria-label="Related timeline views">
  <a class="active" href="/timeline">{t("timeline_title", lang)}</a>
  <a href="/events">{t("events_title", lang)}</a>
</nav>

<div class="controls">
  <div class="filters" id="filters">
    <button class="filter-btn active" data-type="all" data-i18n="all_label">{t("all_label", lang)}</button>
    {filter_btns}
  </div>
  <div class="year-slider-wrap">
    <label for="year-slider" data-i18n="jump_to">{t("jump_to", lang)}</label>
    <input type="range" id="year-slider" class="year-slider" min="0" max="100" value="0">
    <span class="year-range" id="year-range">—</span>
  </div>
</div>

<div class="stats-bar" id="stats-bar"></div>
<details class="intel-rating-help"><summary data-i18n="editorial_rating_label">{t("editorial_rating_label", lang)}</summary><p data-i18n="editorial_rating_help">{t("editorial_rating_help", lang)}</p></details>
<div class="timeline-scroll" id="timeline-scroll">
  <div class="timeline-inner" id="timeline-inner">
    <div class="timeline-empty" data-ui-state="loading" data-i18n="loading">{t("loading", lang)}</div>
  </div>
</div>
</main>

<script>
{i18n_js()}
</script>
{js_code}
</body>
</html>"""
    path = output_dir / "timeline.html"
    path.write_text(html, encoding="utf-8")
    log.info(f"Timeline v2 (i18n): {path}")
    return path
