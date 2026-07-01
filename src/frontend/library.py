"""
AI Intelligence Platform — Library 生成器 v2 (i18n)
卡片详情优化：每张卡显示定义/重要性/时间/公司/关系/Timeline/标签
支持中英文切换。使用共享设计系统 (frontend_styles.py)。
"""

import json
from pathlib import Path
from typing import Optional
from src.engine.utils import log, ensure_dir, ROOT_DIR
from src.interfaces.i18n import t, i18n_js, nav_html
from .frontend_styles import TYPE_COLORS, ANIMATION_CSS, RESPONSIVE_CSS, ERROR_CSS, SHARED_JS, THEME_VARS


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
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:var(--bg-primary);color:var(--text-primary);padding:24px;max-width:1100px;margin:0 auto;animation:fadeIn .35s ease-out}}
h1{{font-size:22px;color:var(--accent);margin-bottom:4px}}
.date{{font-size:12px;color:var(--text-secondary);margin-bottom:16px}}
.nav{{display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap;align-items:center}}
.nav a{{padding:6px 14px;border-radius:var(--radius-sm);font-size:13px;text-decoration:none;color:var(--text-primary);background:var(--bg-elevated);transition:background .15s}}
.nav a:hover{{background:var(--border)}}
.nav a.active{{background:var(--accent-subtle);color:var(--accent)}}
.lang-btn{{padding:4px 12px;border:1px solid var(--border);background:var(--bg-elevated);color:var(--text-primary);border-radius:var(--radius-sm);cursor:pointer;font-size:12px;margin-left:auto;transition:background .15s}}
.lang-btn:hover{{background:var(--border)}}

/* ── 搜索栏 ── */
.search-wrap{{margin-bottom:16px}}
.search-wrap input{{width:100%;padding:10px 16px;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);color:var(--text-primary);font-size:14px;outline:none;transition:border-color .15s}}
.search-wrap input:focus{{border-color:var(--accent)}}
.search-wrap input::placeholder{{color:var(--text-muted)}}

/* ── 统计条 ── */
html{{scroll-behavior:smooth}}
.category-nav{{position:sticky;top:0;z-index:100;background:var(--bg-primary);padding:10px 0 8px;margin-bottom:18px;border-bottom:1px solid var(--border)}}
.category-nav-inner{{display:flex;gap:6px;flex-wrap:wrap;align-items:center}}
.cat-tag{{display:inline-flex;align-items:center;gap:4px;padding:4px 12px;border-radius:14px;font-size:11px;cursor:pointer;border:1px solid var(--border);background:var(--bg-card);color:var(--text-secondary);transition:all .15s;white-space:nowrap;text-decoration:none}}
.cat-tag:hover{{border-color:var(--accent);color:var(--text-primary)}}
.cat-tag.active{{background:var(--accent-subtle);border-color:var(--accent);color:var(--accent);font-weight:600}}
.cat-tag .count{{font-weight:600;opacity:.85}}
.cat-tag.active .count{{opacity:1}}
.stats-extra{{display:flex;gap:14px;font-size:10px;color:var(--text-muted);margin-bottom:12px;flex-wrap:wrap}}
.stats-extra span b{{color:var(--text-secondary)}}

/* ── 分组 ── */
.section{{margin-bottom:32px}}
.section h2{{font-size:17px;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid var(--bg-elevated);display:flex;align-items:center;gap:8px}}
.section h2 .count{{font-size:11px;color:var(--text-secondary);font-weight:normal}}
.section h2 .icon{{font-size:18px}}

/* ── 卡片 ── */
.card{{background:var(--bg-card);border:1px solid var(--border);border-radius:10px;padding:18px;margin-bottom:12px;transition:border-color .15s;cursor:pointer}}
.card:hover{{border-color:#58a6ff44}}
.card.expanded{{border-color:var(--accent);box-shadow:var(--shadow)}}

.card-header{{display:flex;align-items:flex-start;gap:10px;margin-bottom:8px}}
.card-header .type-badge{{display:inline-flex;align-items:center;gap:3px;padding:2px 10px;border-radius:10px;font-size:10px;color:#fff;flex-shrink:0}}
.card-header .name{{font-size:15px;font-weight:600;color:var(--accent);flex:1}}
.card-header .stars{{color:#d2991d;font-size:11px;flex-shrink:0;white-space:nowrap}}

.card-meta{{display:flex;gap:16px;flex-wrap:wrap;font-size:10px;color:var(--text-muted);margin-bottom:8px}}
.card-meta span{{display:inline-flex;align-items:center;gap:3px}}

.card-def{{font-size:12px;color:var(--text-secondary);line-height:1.5;margin-bottom:0}}

/* ── 展开详情 ── */
.card-detail{{display:none;margin-top:12px;padding-top:12px;border-top:1px solid var(--bg-elevated)}}
.card.expanded .card-detail{{display:block}}
.card-detail .dl-row{{display:flex;gap:8px;margin-bottom:8px;font-size:11px}}
.card-detail .dl-label{{color:var(--text-muted);flex-shrink:0;min-width:60px}}
.card-detail .dl-value{{color:var(--text-secondary);line-height:1.5}}
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
.card-hover{{transition:all .2s ease}}.card-hover:hover{{transform:translateY(-2px);box-shadow:var(--shadow);border-color:#58a6ff44}}
{ANIMATION_CSS}
{RESPONSIVE_CSS}
{ERROR_CSS}
</style>
</head>
<body>
<h1 data-i18n="library_title">{t("library_title", lang)}</h1>
<p class="date" id="date-line">{t("loading", lang)}</p>
{nav_html("/library")}

<div class="search-wrap">
  <input type="text" id="search" data-i18n-placeholder="search_placeholder" placeholder="{t("search_placeholder", lang)}" oninput="filterEntities()">
</div>

<div class="stats-extra" id="stats-extra"></div>
<div class="category-nav" id="category-nav">
  <div class="category-nav-inner" id="category-tags"></div>
</div>
<div id="content">{t("loading", lang)}</div>

<script>
{SHARED_JS}
{i18n_js()}
</script>
<script>
const COLORS={json.dumps(TYPE_COLORS)};
const I = {{model:"\\ud83e\\udde0",company:"\\ud83c\\udfe2",tech:"\\u2699\\ufe0f",concept:"\\ud83d\\udca1",product:"\\ud83d\\ude80",person:"\\ud83d\\udc64",methodology:"\\ud83d\\udcd0",event:"\\ud83d\\udcc5"}};
const TYPE_ORDER = ["methodology","model","company","tech","concept","product","person","event"];

let allEntities = [];

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
  renderStats(allEntities);
  renderAll(allEntities);
  updatePlaceholders();
  }}catch(e){{showError("content",T("error_loading"),e.message);}}
}}

function renderStats(entities) {{
  const byType = {{}};
  entities.forEach(e => {{ byType[e.type] = (byType[e.type]||0) + 1; }});
  const totalImp = entities.reduce((s,e) => s + (e.importance||0), 0);

  // 额外统计行（总数 + 平均重要性）
  var extraHtml = '<span>' + T("all_label") + ': <b>' + entities.length + '</b></span>';
  extraHtml += '<span>' + T("importance_label") + ': <b>' + (entities.length ? (totalImp/entities.length).toFixed(1) : 0) + '</b></span>';
  document.getElementById("stats-extra").innerHTML = extraHtml;

  // 可点击分类标签（按 TYPE_ORDER 排序）
  var tagsHtml = '';
  TYPE_ORDER.forEach(function(t) {{
    var c = byType[t];
    if (!c) return;
    var color = getColor(t);
    tagsHtml += '<span class="cat-tag" data-cat="' + t + '" onclick="scrollToCategory(this.dataset.cat)" style="border-color:' + color + '44;color:' + color + '">' + (I[t]||"") + ' ' + TLbl(t) + ' <span class="count">' + c + '</span></span>';
  }});
  document.getElementById("category-tags").innerHTML = tagsHtml;
}}

function getColor(type) {{return COLORS[type] || "#999";}}

function filterEntities() {{
  const q = document.getElementById("search").value.toLowerCase().trim();
  if (!q) {{ renderStats(allEntities); renderAll(allEntities); return; }}

  // 清除上一个定时器，300ms 防抖
  if (window._searchTimer) clearTimeout(window._searchTimer);
  window._searchTimer = setTimeout(async function() {{
    try {{
      const result = await apiFetch("/api/search?q=" + encodeURIComponent(q) + "&semantic=true&limit=61");
      if (result.entities && result.entities.length > 0) {{
        document.getElementById("date-line").textContent =
          new Date().toISOString().slice(0,10) + " \\u00b7 " +
          result.entities.length + " " + T("entities_label") +
          " \\u00b7 \\u2728 " + T("semantic_search");
        renderStats(result.entities);
        renderAll(result.entities);
        return;
      }}
    }} catch(e) {{ /* 降级到客户端过滤 */ }}
    // 语义搜索不可用时，客户端过滤（原逻辑）
    const filtered = allEntities.filter(e =>
      (e.name||"").toLowerCase().includes(q) ||
      (e.summary||"").toLowerCase().includes(q) ||
      (e.tags||[]).some(t => t.toLowerCase().includes(q)) ||
      (e.company||"").toLowerCase().includes(q)
    );
    renderStats(filtered);
    renderAll(filtered);
  }}, 300);
}}

function renderAll(entities) {{
  const byType = {{}};
  entities.forEach(e => {{ if (!byType[e.type]) byType[e.type] = []; byType[e.type].push(e); }});

  let html = "";
  TYPE_ORDER.forEach(t => {{
    const items = (byType[t] || []).sort((a,b) => (b.importance||0)-(a.importance||0));
    if (!items.length) return;
    html += '<div class="section" id="cat-' + t + '"><h2><span class="icon">' + (I[t]||"") + '</span>' + TLbl(t) + '<span class="count">' + items.length + '</span></h2>';
    items.forEach(e => {{ html += renderCard(e); }});
    html += '</div>';
  }});

  document.getElementById("content").innerHTML = html || '<div class="empty">' + T("no_results") + '</div>';
}}

function renderCard(e) {{
  const stars = "\\u2605".repeat(e.importance || 0) + "\\u2606".repeat(Math.max(0,5-(e.importance||0)));
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

  return '<div class="card" onclick="this.classList.toggle(\\'expanded\\')">' +
    '<div class="card-header">' +
      '<span class="type-badge" style="background:' + color + '22;color:' + color + '">' + (I[e.type]||"") + ' ' + TLbl(e.type) + '</span>' +
      '<span class="name">' + e.name + '</span>' +
      '<span class="stars" title="' + T("importance_label") + ' ' + (e.importance||0) + '/5">' + stars + '</span>' +
    '</div>' +
    '<div class="card-meta">' +
      (date ? '<span>\\ud83d\\udcc5 ' + date + '</span>' : "") +
      (company ? '<span>\\ud83c\\udfe2 ' + company + '</span>' : "") +
      (domain ? '<span>\\ud83d\\udcc2 ' + domain + '</span>' : "") +
      (creators ? '<span>\\ud83d\\udc65 ' + creators + '</span>' : "") +
    '</div>' +
    '<div class="card-def">' + (e.summary || "") + '</div>' +
    '<div class="card-detail">' +
      (e.significance ? '<div class="dl-row"><span class="dl-label">' + T("importance_label") + '</span><span class="dl-value">' + e.significance.slice(0,500) + '</span></div>' : "") +
      (background ? '<div class="dl-row"><span class="dl-label">' + T("background_label") + '</span><span class="dl-value">' + background.slice(0,400) + '</span></div>' : "") +
      (knownFor ? '<div class="dl-row"><span class="dl-label">' + T("known_for_label") + '</span><span class="dl-value">' + knownFor + '</span></div>' : "") +
      (relatedEnt ? '<div class="dl-row"><span class="dl-label">' + T("related_label") + '</span><span class="dl-value">' + relatedEnt + '</span></div>' : "") +
      (timelineHtml ? '<div class="dl-row"><span class="dl-label">' + T("timeline_label") + '</span><span class="dl-value"><div class="timeline-compact">' + timelineHtml + '</div></span></div>' : "") +
      (tags ? '<div class="card-tags">' + tags + '</div>' : "") +
      '<div style="margin-top:8px"><a href="/entity/' + e.id + '" class="dl-value" onclick="event.stopPropagation()" style="font-size:11px">' + T("view_detail") + ' \\u2192</a></div>' +
    '</div>' +
    '<div class="expand-hint">' + T("click_to_expand") + ' \\u00b7 ' + e.id + '</div>' +
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
