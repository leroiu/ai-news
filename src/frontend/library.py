"""知识资产集合页：搜索、分类导航与可展开实体卡片。"""
import json
from pathlib import Path
from typing import Optional
from src.engine.utils import log, ensure_dir, ROOT_DIR
from src.interfaces.i18n import t, i18n_js, nav_html
from .frontend_styles import ACTION_COMPONENT_CSS, ACCESSIBILITY_CSS, TYPE_COLORS, ANIMATION_CSS, RESPONSIVE_CSS, ERROR_CSS, INTELLIGENCE_CSS, SHARED_JS, THEME_VARS

def generate_library(output_dir: Optional[Path] = None, lang: str = "zh") -> Path:
    if output_dir is None:
        output_dir = ROOT_DIR / "reports"
    ensure_dir(output_dir)

    html = _build_html(lang)
    path = output_dir / "library.html"
    path.write_text(html, encoding="utf-8")
    log.info(f"Library v2 (i18n): {path}")
    return path


def _build_html(lang: str = "zh") -> str:
    return f'''<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{t("platform_title", lang)} — {t("library_title", lang)}</title>
<style>
{THEME_VARS}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:var(--font-sans);background:var(--bg-primary);color:var(--text-primary);padding:24px;max-width:var(--content-max);margin:0 auto;animation:fadeIn .2s ease-out}}
h1{{font-family:var(--font-display);font-size:38px;line-height:1.1;letter-spacing:-.035em;color:var(--text-primary);margin-bottom:8px}}
.page-heading{{min-height:112px;padding:4px 0 22px}}
.date{{font-size:12px;color:var(--text-secondary);margin-bottom:16px}}
.nav{{display:flex;min-height:34px;gap:8px;margin-bottom:24px;flex-wrap:wrap;align-items:center}}
.nav a{{padding:6px 14px;border-radius:var(--radius-sm);font-size:13px;text-decoration:none;color:var(--text-primary);background:var(--bg-elevated);transition:background .15s}}
.nav a:hover{{background:var(--border)}}
.nav a.active{{background:var(--accent-subtle);color:var(--accent)}}
.lang-btn{{padding:4px 12px;border:1px solid var(--border);background:var(--bg-elevated);color:var(--text-primary);border-radius:var(--radius-sm);cursor:pointer;font-size:12px;margin-left:auto;transition:background .15s}}
.lang-btn+.lang-btn{{margin-left:0}}
.lang-btn:hover{{background:var(--border)}}

.library-tools{{position:sticky;top:0;z-index:100;padding:10px 0 0;background:var(--bg-primary);box-shadow:0 1px 0 var(--border)}}
.search-wrap{{margin-bottom:10px}}
.search-wrap input{{width:100%;padding:10px 16px;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);color:var(--text-primary);font-size:14px;outline:none;transition:border-color .15s}}
.search-wrap input:focus{{border-color:var(--accent)}}
.search-wrap input::placeholder{{color:var(--text-muted)}}
.related-views{{display:flex;gap:8px;margin:-8px 0 20px;padding-bottom:14px;border-bottom:1px solid var(--border);flex-wrap:wrap}}
.related-views a{{padding:5px 10px;border-radius:999px;color:var(--text-secondary);font-size:11px;text-decoration:none}}
.related-views a:hover,.related-views a.active{{background:var(--accent-subtle);color:var(--accent)}}

html{{scroll-behavior:smooth}}
.category-nav{{padding:8px 0;margin-bottom:18px}}
.category-nav-inner{{display:flex;gap:6px;flex-wrap:wrap;align-items:center}}
.cat-tag{{display:inline-flex;align-items:center;gap:4px;padding:4px 12px;border-radius:14px;font-size:11px;cursor:pointer;border:1px solid var(--border);background:var(--bg-card);color:var(--text-secondary);transition:all .15s;white-space:nowrap;text-decoration:none}}
.cat-tag:hover{{border-color:var(--accent);color:var(--text-primary)}}
.cat-tag.active{{background:var(--accent-subtle);border-color:var(--accent);color:var(--accent);font-weight:600}}
.cat-tag .count{{font-weight:600;opacity:.85}}
.cat-tag.active .count{{opacity:1}}
.stats-extra{{display:flex;gap:14px;font-size:10px;color:var(--text-muted);margin-bottom:12px;flex-wrap:wrap}}
.stats-extra span b{{color:var(--text-secondary)}}

/* ── 分组 ── */
.section{{margin-bottom:42px}}
.section h2{{font-family:var(--font-display);font-size:21px;margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid var(--border-strong);display:flex;align-items:center;gap:8px}}
.section h2 .count{{font-size:11px;color:var(--text-secondary);font-weight:normal}}
.section h2 .icon{{font-size:18px}}

/* ── 卡片 ── */
.card{{background:transparent;border:0;border-bottom:1px solid var(--border);border-radius:0;padding:16px 0;margin:0;transition:border-color .15s;cursor:pointer}}
.card:hover{{border-color:#58a6ff44}}
.card.expanded{{border-color:var(--accent);box-shadow:var(--shadow)}}

.card-header{{display:flex;align-items:flex-start;gap:10px;margin-bottom:8px}}
.card-header .type-badge{{display:inline-flex;align-items:center;gap:3px;padding:2px 10px;border-radius:10px;font-size:10px;color:#fff;flex-shrink:0}}
.card-header .name{{font-size:15px;font-weight:600;color:var(--accent);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.card-header .stars{{color:#d2991d;font-size:11px;flex-shrink:0;white-space:nowrap}}
.favorite-btn{{padding:2px 7px;border:1px solid var(--border);background:var(--bg-elevated);color:var(--text-secondary);border-radius:999px;cursor:pointer;font-size:10px;line-height:1.4;flex-shrink:0}}
.favorite-btn:hover,.favorite-btn.is-favorited,.favorite-btn[aria-pressed="true"]{{border-color:var(--warning);background:#e3b34122;color:var(--warning)}}

.card-meta{{display:flex;gap:16px;flex-wrap:wrap;font-size:10px;color:var(--text-muted);margin-bottom:8px}}
.card-meta span{{display:inline-flex;align-items:center;gap:3px}}

.card-def{{font-size:12px;color:var(--text-secondary);line-height:1.5;margin-bottom:0;overflow-wrap:break-word;word-break:break-word}}

/* ── 展开详情 ── */
.card-detail{{display:none;margin-top:12px;padding-top:12px;border-top:1px solid var(--bg-elevated)}}
.card.expanded .card-detail{{display:block}}
.card-detail .dl-row{{display:flex;gap:8px;margin-bottom:8px;font-size:11px}}
.card-detail .dl-label{{color:var(--text-muted);flex-shrink:0;min-width:60px}}
.card-detail .dl-value{{color:var(--text-secondary);line-height:1.5;overflow-wrap:break-word;word-break:break-word}}
.card-detail .dl-value a{{color:var(--accent);text-decoration:none}}
.card-detail .dl-value a:hover{{text-decoration:underline}}

.card-tags{{display:flex;gap:4px;flex-wrap:wrap;margin-top:8px}}
.tag{{font-size:9px;padding:1px 7px;background:var(--bg-elevated);border-radius:4px;color:#6e7681}}

.timeline-compact{{font-size:10px;color:#6e7681;line-height:1.7}}
.timeline-compact .tl-dot{{display:inline-block;width:5px;height:5px;background:var(--accent);border-radius:50%;margin-right:5px;vertical-align:middle}}

/* ── 展开指示 ── */
.expand-hint{{font-size:10px;color:var(--border);margin-top:8px}}

/* ── 空状态 ── */
.empty{{text-align:center;padding:40px;color:var(--text-muted);font-size:13px}}
.section-actions{{padding-top:14px}}
.section-toggle{{padding:7px 12px;border:1px solid var(--border);border-radius:999px;background:transparent;color:var(--text-secondary);font-size:11px;cursor:pointer}}
.section-toggle:hover{{border-color:var(--accent);color:var(--accent)}}
.card-hover{{transition:all .2s ease}}.card-hover:hover{{transform:translateY(-2px);box-shadow:var(--shadow);border-color:#58a6ff44}}
@media(max-width:480px){{.search-wrap input{{min-height:42px}}.related-views a{{display:inline-flex;min-height:34px;padding:7px 10px;align-items:center}}.card{{padding:14px 0}}.card-header{{flex-wrap:wrap;gap:7px}}.card-header .name{{min-width:0;font-size:14px}}.card-header .stars .intel-rating__label{{display:none}}.card-def{{font-size:12px;line-height:1.6}}.section-toggle{{min-height:36px}}.intel-rating-help p{{max-width:100%}}}}
{ANIMATION_CSS}
{RESPONSIVE_CSS}
{ERROR_CSS}
{INTELLIGENCE_CSS}
{ACTION_COMPONENT_CSS}
{ACCESSIBILITY_CSS}
</style>
</head>
<body data-page-template="collection">
<a class="skip-link" href="#main-content">{t("skip_to_content", lang)}</a>
{nav_html("/library")}
<header class="page-heading">
<h1 data-i18n="library_title">{t("library_title", lang)}</h1>
<p class="date" id="date-line">{t("loading", lang)}</p>
</header>
<main id="main-content">
<nav class="related-views" aria-label="Related knowledge views">
  <a class="active" href="/library">{t("library_title", lang)}</a>
  <a href="/graph">{t("graph_title", lang)}</a>
  <a href="/graph3d">{t("graph_title", lang)} 3D</a>
</nav>

<div class="library-tools">
<div class="search-wrap">
  <input type="text" id="search" data-i18n-placeholder="search_placeholder" placeholder="{t("search_placeholder", lang)}" oninput="filterEntities()">
</div>

<div class="stats-extra" id="stats-extra" aria-live="polite"></div>
<div class="category-nav" id="category-nav">
  <div class="category-nav-inner" id="category-tags"></div>
</div>
</div>
<div id="content" data-ui-state="loading">{t("loading", lang)}</div>
</main>

<script>
{SHARED_JS}
{i18n_js()}
</script>
<script>
const COLORS={json.dumps(TYPE_COLORS)};
const I = {{model:"\\ud83e\\udde0",company:"\\ud83c\\udfe2",tech:"\\u2699\\ufe0f",concept:"\\ud83d\\udca1",product:"\\ud83d\\ude80",person:"\\ud83d\\udc64",methodology:"\\ud83d\\udcd0",event:"\\ud83d\\udcc5"}};
const TYPE_ORDER = ["methodology","model","company","tech","concept","product","person","event"];

let allEntities = [];
const expandedTypes = new Set();
const CATEGORY_PREVIEW_LIMIT = 4;
let activeType = "all";
let searchVersion = 0;
let lastRenderedIds = "";

function updatePlaceholders() {{
  document.querySelectorAll('[data-i18n-placeholder]').forEach(function(el) {{
    el.placeholder = T(el.getAttribute('data-i18n-placeholder'));
  }});
}}

async function init() {{
  try{{
  allEntities = await apiFetch("/api/entities");
  var types = new Set(allEntities.map(e=>e.type));
  document.getElementById("date-line").textContent = new Date().toISOString().slice(0,10) + " \\u00b7 " + allEntities.length + " " + T("entities_label") + " \\u00b7 " + types.size + " " + T("types_label");
  renderCategoryNav();
  applyFilters();
  updatePlaceholders();
  }}catch(e){{showError("content",T("error_loading"),e.message);}}
}}

function renderStats(entities) {{
  const totalImp = entities.reduce((s,e) => s + (e.importance||0), 0);

  // 额外统计行（总数 + 平均重要性）
  var extraHtml = '<span>' + T("all_label") + ': <b>' + entities.length + '</b></span>';
  extraHtml += '<span>' + T("importance_label") + ': <b>' + (entities.length ? (totalImp/entities.length).toFixed(1) : 0) + '</b></span>';
  document.getElementById("stats-extra").innerHTML = extraHtml;

}}

function renderCategoryNav() {{
  const byType = {{}};
  allEntities.forEach(e => {{ byType[e.type] = (byType[e.type]||0) + 1; }});
  var tagsHtml = '<button class="cat-tag active" type="button" data-cat="all" onclick="setCategory(this.dataset.cat)">' + T("all_label") + ' <span class="count">' + allEntities.length + '</span></button>';
  TYPE_ORDER.forEach(function(t) {{
    var c = byType[t];
    if (!c) return;
    var color = getColor(t);
    tagsHtml += '<button class="cat-tag" type="button" data-cat="' + t + '" onclick="setCategory(this.dataset.cat)" style="border-color:' + color + '44;color:' + color + '">' + (I[t]||"") + ' ' + TLbl(t) + ' <span class="count">' + c + '</span></button>';
  }});
  document.getElementById("category-tags").innerHTML = tagsHtml;
}}

function getColor(type) {{return COLORS[type] || "#999";}}

function keywordMatches(e, q) {{
  return (e.name||"").toLowerCase().includes(q) ||
    (e.summary||"").toLowerCase().includes(q) ||
    (Array.isArray(e.tags) ? e.tags.some(function(t){{return t.toLowerCase().includes(q)}}) : String(e.tags||"").toLowerCase().includes(q)) ||
    (e.company||"").toLowerCase().includes(q) ||
    (e.id||"").toLowerCase().includes(q);
}}

function applyFilters(semanticIds) {{
  const q = document.getElementById("search").value.toLowerCase().trim();
  const filtered = allEntities.filter(function(e) {{
    return (activeType === "all" || e.type === activeType) &&
      (!q || keywordMatches(e, q) || (semanticIds && semanticIds.has(e.id)));
  }});
  const ids = filtered.map(function(e) {{ return e.id; }}).sort().join(",");
  if (ids === lastRenderedIds) return;
  lastRenderedIds = ids;
  renderStats(filtered);
  renderAll(filtered, Boolean(q) || activeType !== "all");
}}

function setCategory(type) {{
  activeType = type;
  document.querySelectorAll(".cat-tag").forEach(function(tag) {{
    tag.classList.toggle("active", tag.dataset.cat === type);
  }});
  applyFilters();
}}

function filterEntities() {{
  const q = document.getElementById("search").value.toLowerCase().trim();
  const version = ++searchVersion;
  lastRenderedIds = "";
  if (q && activeType !== "all") {{
    const hasGlobalMatch = allEntities.some(function(e) {{ return keywordMatches(e, q); }});
    const hasCategoryMatch = allEntities.some(function(e) {{ return e.type === activeType && keywordMatches(e, q); }});
    if (hasGlobalMatch && !hasCategoryMatch) setCategory("all");
  }}
  applyFilters();
  if (window._searchTimer) clearTimeout(window._searchTimer);
  if (!q) return;
  // 语义搜索仅在关键词无匹配时补充；已有结果时不再触发，保证卡片稳定不闪
  const keywordMatched = allEntities.filter(function(e){{return keywordMatches(e,q);}});
  if (keywordMatched.length > 0) return;
  window._searchTimer = setTimeout(async function() {{
    try {{
      const result = await apiFetch("/api/search?q=" + encodeURIComponent(q) + "&semantic=true&limit=61");
      if (version !== searchVersion || document.getElementById("search").value.toLowerCase().trim() !== q) return;
      applyFilters(new Set((result.entities||[]).map(function(e){{return e.id;}})));
    }} catch(e) {{ /* 保持即时过滤结果 */ }}
  }}, 500);
}}

function renderAll(entities, revealAll=false) {{
  const byType = {{}};
  entities.forEach(e => {{ if (!byType[e.type]) byType[e.type] = []; byType[e.type].push(e); }});

  let html = ratingHelpHTML();
  TYPE_ORDER.forEach(t => {{
    const items = (byType[t] || []).sort((a,b) => (b.importance||0)-(a.importance||0));
    if (!items.length) return;
    const expanded = revealAll || expandedTypes.has(t);
    const visibleItems = expanded ? items : items.slice(0, CATEGORY_PREVIEW_LIMIT);
    html += '<div class="section" id="cat-' + t + '"><h2><span class="icon">' + (I[t]||"") + '</span>' + TLbl(t) + '<span class="count">' + items.length + '</span></h2>';
    visibleItems.forEach(e => {{ html += renderCard(e); }});
    if (!revealAll && items.length > CATEGORY_PREVIEW_LIMIT) {{
      html += '<div class="section-actions"><button class="section-toggle" type="button" onclick="toggleCategory(\\'' + t + '\\')">' +
        (expanded ? T("collapse_category") : T("show_all_entities", {{n: items.length}})) + '</button></div>';
    }}
    html += '</div>';
  }});

  const content = document.getElementById("content");
  content.innerHTML = html || '<div class="empty">' + T("no_results") + '</div>';
  if (html) content.removeAttribute("data-ui-state");
  else content.setAttribute("data-ui-state","empty");
  if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {{
    content.animate(
      [{{opacity:.35,transform:'translateY(4px)'}},{{opacity:1,transform:'translateY(0)'}}],
      {{duration:180,easing:'ease-out'}}
    );
  }}
}}

function toggleCategory(type) {{
  if (expandedTypes.has(type)) expandedTypes.delete(type);
  else expandedTypes.add(type);
  renderAll(allEntities);
  if (!expandedTypes.has(type)) scrollToCategory(type);
}}

function renderCard(e) {{
  const color = e.color || getColor(e.type);
  const date = e.release_date || (e.timeline && e.timeline[0] && e.timeline[0].date) || "";
  const company = e.company || (e.affiliations || []).join(", ") || "";
  const creators = (e.creators || []).join(", ");
  const knownFor = (e.known_for || []).map(f => '<span class="tag">' + f + '</span>').join(" ");
  const relatedEnt = (e.related || []).slice(0,8).map(id => '<span class="tag" style="cursor:pointer" onclick="event.stopPropagation();window.location=\\'/entity/' + id + '\\'">' + id + '</span>').join(" ");
  const tags = (e.tags || []).slice(0,10).map(t => '<span class="tag">' + t + '</span>').join("");
  const timelineHtml = (e.timeline || []).map(t => '<div><span class="tl-dot"></span>' + (t.date||"") + ' \\u2014 ' + (t.event||"") + '</div>').join("");
  const domain = e.domain || "";
  const background = e.background || "";

  return '<div class="card" role="link" tabindex="0" onclick="window.location=\\'/entity/' + e.id + '\\'" onkeydown="if(event.key===\\'Enter\\')window.location=\\'/entity/' + e.id + '\\'">' +
    '<div class="card-header">' +
      '<span class="type-badge" style="background:' + color + '22;color:' + color + '">' + (I[e.type]||"") + ' ' + TLbl(e.type) + '</span>' +
      '<span class="name">' + e.name + '</span>' +
      '<span class="stars">' + editorialRatingHTML(e.importance||0) + '</span>' +
      favoriteButtonHTML('entity', e.id, e.name, '', '/entity/'+e.id) +
    '</div>' +
    '<div class="card-meta">' +
      (date ? '<span>\\ud83d\\udcc5 ' + date + '</span>' : "") +
      (company ? '<span>\\ud83c\\udfe2 ' + company + '</span>' : "") +
      (domain ? '<span>\\ud83d\\udcc2 ' + domain + '</span>' : "") +
      (creators ? '<span>\\ud83d\\udc65 ' + creators + '</span>' : "") +
    '</div>' +
    '<div class="card-def">' + evidenceLabelHTML('fact') + ' ' + (e.summary || "") + '</div>' +
    '<div class="card-detail">' +
      (e.significance ? '<div class="dl-row"><span class="dl-label">' + T("importance_label") + '</span><span class="dl-value">' + e.significance.slice(0,500) + '</span></div>' : "") +
      (background ? '<div class="dl-row"><span class="dl-label">' + T("background_label") + '</span><span class="dl-value">' + background.slice(0,400) + '</span></div>' : "") +
      (knownFor ? '<div class="dl-row"><span class="dl-label">' + T("known_for_label") + '</span><span class="dl-value">' + knownFor + '</span></div>' : "") +
      (relatedEnt ? '<div class="dl-row"><span class="dl-label">' + T("related_label") + '</span><span class="dl-value">' + relatedEnt + '</span></div>' : "") +
      (timelineHtml ? '<div class="dl-row"><span class="dl-label">' + T("timeline_label") + '</span><span class="dl-value"><div class="timeline-compact">' + timelineHtml + '</div></span></div>' : "") +
      (tags ? '<div class="card-tags">' + tags + '</div>' : "") +
      '<div style="margin-top:8px"><a href="/entity/' + e.id + '" class="dl-value" onclick="event.stopPropagation()" style="font-size:11px">' + T("view_detail") + ' \\u2192</a></div>' +
    '</div>' +
    '<div class="expand-hint">' + T("view_detail") + ' \\u2192 · ' + e.id + '</div>' +
  '</div>';
}}

function scrollToCategory(type) {{
  var el = document.getElementById('cat-' + type);
  if (el) {{
    var navH = document.getElementById('category-nav').offsetHeight + 16;
    var top = el.getBoundingClientRect().top + window.pageYOffset - navH;
    window.scrollTo({{ top: top, behavior: 'smooth' }});
  }}
}}

// Scroll Spy via Intersection Observer
(function() {{
  var observer = new IntersectionObserver(function(entries) {{
    entries.forEach(function(entry) {{
      var cat = entry.target.id.replace('cat-', '');
      var tag = document.querySelector('.cat-tag[data-cat="' + cat + '"]');
      if (tag) {{
        if (entry.isIntersecting) {{
          document.querySelectorAll('.cat-tag.active').forEach(function(t) {{ t.classList.remove('active'); }});
          tag.classList.add('active');
        }}
      }}
    }});
  }}, {{ rootMargin: '-80px 0px -60% 0px' }});

  TYPE_ORDER.forEach(function(t) {{
    var el = document.getElementById('cat-' + t);
    if (el) observer.observe(el);
  }});
}})();

// 点击后即时高亮
var _origScrollTo = scrollToCategory;
scrollToCategory = function(type) {{
  document.querySelectorAll('.cat-tag.active').forEach(function(t) {{ t.classList.remove('active'); }});
  var tag = document.querySelector('.cat-tag[data-cat="' + type + '"]');
  if (tag) tag.classList.add('active');
  _origScrollTo(type);
}};

init();
</script>
</body>
</html>'''
