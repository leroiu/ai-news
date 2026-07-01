"""
AI Intelligence Platform — Entity Detail Page (i18n)
API-driven. 技术专有名词保留英文原名，UI标签中文化。
使用共享设计系统 (frontend_styles.py)。

增强：
- 关联文章时间线视图（按日期分组）
- 关系类型统计（按类型计数+分组展示）
- 展示 domain / background / known_for / creators 字段
- 两栏布局（字段信息 + 背景/重要性）
"""
import json
from pathlib import Path
from src.engine.utils import log, ensure_dir, ROOT_DIR
from src.interfaces.i18n import t, i18n_js, nav_html
from .frontend_styles import TYPE_COLORS, ANIMATION_CSS, RESPONSIVE_CSS, ERROR_CSS, SHARED_JS, THEME_VARS


def generate_entity_shell(lang: str = "zh") -> Path:
    ensure_dir(ROOT_DIR / "reports")

    html = f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{t("platform_title", lang)}</title>
<style>
{THEME_VARS}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:var(--bg-primary);color:var(--text-primary);padding:24px;max-width:900px;margin:0 auto;animation:fadeIn .35s ease-out}}
.nav{{display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap;align-items:center}}
.nav a{{padding:6px 14px;border-radius:var(--radius-sm);font-size:13px;text-decoration:none;color:var(--text-primary);background:var(--bg-elevated)}}
.nav a:hover{{background:var(--border)}}
.lang-btn{{padding:4px 12px;border:1px solid var(--border);background:var(--bg-elevated);color:var(--text-primary);border-radius:var(--radius-sm);cursor:pointer;font-size:12px;margin-left:auto;transition:background .15s}}
.lang-btn:hover{{background:var(--border)}}
h1{{font-size:24px;margin-bottom:4px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
h1 .badge{{font-size:11px;padding:2px 12px;border-radius:10px;color:#fff;flex-shrink:0}}
.date-line{{font-size:12px;color:var(--text-secondary);margin-bottom:24px}}
.section{{margin-bottom:24px}}
.section h2{{font-size:15px;margin-bottom:8px;color:var(--text-primary);padding-bottom:6px;border-bottom:1px solid var(--bg-elevated)}}
.section p{{font-size:13px;line-height:1.7;color:var(--text-secondary);white-space:pre-wrap}}
.stars{{color:#d2991d;font-size:14px;margin-left:8px}}
.tags{{display:flex;gap:4px;flex-wrap:wrap;margin-top:8px}}
.tag{{font-size:10px;padding:2px 10px;background:var(--bg-elevated);border-radius:4px;color:var(--text-secondary)}}
.rel-item{{display:flex;align-items:center;gap:8px;padding:6px 0;font-size:13px;border-bottom:1px solid var(--bg-elevated)}}
.rel-item:last-child{{border-bottom:none}}
.rel-type{{font-size:9px;padding:1px 8px;border-radius:8px;color:#fff;background:var(--border);flex-shrink:0;min-width:80px;text-align:center}}
.rel-item a{{color:var(--accent);text-decoration:none}}
.rel-item a:hover{{text-decoration:underline}}
.tl-entry{{font-size:12px;color:var(--text-secondary);padding:4px 0;display:flex;gap:12px}}
.tl-date{{color:var(--accent);min-width:90px;flex-shrink:0}}
.not-found{{text-align:center;padding:60px 20px;color:var(--text-muted)}}
.not-found h2{{font-size:48px;margin-bottom:12px}}
.spinner{{text-align:center;padding:40px}}
.loading{{display:inline-block;width:20px;height:20px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin .6s linear infinite}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}

/* ── Two-column grid ── */
.info-grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
@media(max-width:640px){{.info-grid{{grid-template-columns:1fr}}}}

/* ── Known-for badges ── */
.kf-badge{{display:inline-block;padding:3px 10px;background:var(--accent-subtle);color:var(--accent);border-radius:12px;font-size:11px;margin:2px 4px 2px 0}}

/* ── Rel type summary ── */
.rel-summary{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px}}
.rel-count-badge{{font-size:10px;padding:2px 10px;border-radius:10px;background:var(--bg-elevated);color:var(--text-secondary)}}
.rel-count-badge b{{color:var(--text-primary)}}

/* ── Article list ── */
.article-list{{display:flex;flex-direction:column;gap:4px}}
.article-item{{display:flex;justify-content:space-between;align-items:center;padding:8px 10px;border-radius:var(--radius-sm);text-decoration:none;color:var(--text-primary);background:var(--bg-card);border:1px solid var(--bg-elevated);transition:all .15s;gap:12px}}
.article-item:hover{{background:#1c2333;border-color:var(--border);transform:translateX(2px)}}
.article-title{{font-size:12px;line-height:1.5;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.article-meta{{display:flex;align-items:center;gap:8px;flex-shrink:0}}
.article-date{{font-size:10px;color:var(--text-secondary)}}
.article-score{{font-size:10px;color:#d2991d}}

/* ── Article Timeline ── */
.article-timeline{{position:relative;padding-left:24px}}
.article-timeline::before{{content:"";position:absolute;left:7px;top:4px;bottom:4px;width:2px;background:var(--border)}}
.atl-entry{{position:relative;padding:6px 0 6px 12px;font-size:12px}}
.atl-entry::before{{content:"";position:absolute;left:-20px;top:12px;width:8px;height:8px;border-radius:50%;background:var(--accent);border:2px solid var(--bg-primary)}}
.atl-entry .atl-date{{font-size:10px;color:var(--accent);font-weight:600}}
.atl-entry .atl-title{{color:var(--text-primary);margin-top:2px}}
.atl-entry .atl-source{{font-size:10px;color:var(--text-muted)}}
.atl-toggle{{font-size:11px;color:var(--accent);cursor:pointer;margin-top:8px;display:inline-block;user-select:none}}
.atl-toggle:hover{{text-decoration:underline}}

/* ── Similar entities ── */
.similar-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:8px}}
.similar-card{{display:flex;align-items:center;gap:8px;padding:10px 12px;border-radius:var(--radius-sm);text-decoration:none;background:var(--bg-card);border:1px solid var(--bg-elevated);transition:all .15s}}
.similar-card:hover{{background:#1c2333;border-color:var(--border);transform:translateY(-1px)}}
.similar-badge{{font-size:9px;padding:2px 8px;border-radius:8px;color:#fff;flex-shrink:0}}
.similar-name{{font-size:12px;color:var(--text-primary);flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.similar-score{{font-size:10px;color:var(--accent);flex-shrink:0}}

/* ── Card metadata ── */
.metadata-row{{display:flex;gap:20px;flex-wrap:wrap;font-size:11px;color:var(--text-secondary)}}
.meta-item{{display:flex;gap:4px}}
.meta-label{{color:var(--text-muted)}}
{ANIMATION_CSS}
{RESPONSIVE_CSS}
{ERROR_CSS}
.back-link{{display:inline-block;margin-top:20px;padding:6px 14px;border-radius:var(--radius-sm);font-size:13px;text-decoration:none;color:var(--text-primary);background:var(--bg-elevated);transition:all .15s}}
.back-link:hover{{background:var(--border);transform:translateY(-1px)}}
</style>
</head>
<body>
{nav_html("")}
<div id="root"><div class="spinner"><div class="loading"></div></div></div>

<script>
{SHARED_JS}
{i18n_js()}
</script>
<script>
const C={json.dumps(TYPE_COLORS)};

async function init(){{
  try{{
  const eid=location.pathname.split("/").pop();
  const resp=await fetch("/api/entities/"+eid);
  if(!resp.ok){{
    document.getElementById("root").innerHTML='<div class="not-found"><h2>404</h2><p>'+T("not_found")+'</p><a href="/" class="back-link">'+T("back_home")+'</a></div>';
    return;
  }}
  const e=await resp.json();
  const color=e.color||C[e.type]||"#999";
  const stars="★".repeat(e.importance||0);
  const typeName = TLbl(e.type);
  document.title=e.name+" — "+T("platform_title");

  var html='<h1><span class="badge" style="background:'+color+'">'+typeName+'</span>'+e.name+'<span class="stars">'+stars+'</span></h1>';
  html+='<div class="date-line">';
  if(e.release_date)html+=e.release_date;
  if(e.company)html+=(e.release_date?" &middot; ":"")+e.company;
  if(e.domain)html+=' &middot; '+e.domain;
  html+='</div>';

  // ── 两栏布局：摘要 + 背景 ──
  if(e.summary||e.background){{
    html+='<div class="info-grid section">';
    if(e.summary)html+='<div><h2>'+T("summary_label")+'</h2><p>'+e.summary+'</p></div>';
    if(e.background)html+='<div><h2>'+T("background_label")+'</h2><p>'+e.background+'</p></div>';
    html+='</div>';
  }}

  if(e.significance)html+='<div class="section"><h2>'+T("importance_label")+'</h2><p>'+e.significance+'</p></div>';

  // ── Known For / Creators ──
  if((e.known_for&&e.known_for.length)||(e.creators&&e.creators.length)){{
    html+='<div class="section"><h2>'+T("known_for_label")+'</h2>';
    if(e.known_for&&e.known_for.length)html+=e.known_for.map(function(f){{return '<span class="kf-badge">'+f+'</span>'}}).join("");
    if(e.creators&&e.creators.length)html+='<div style="margin-top:6px;font-size:11px;color:var(--text-secondary)">'+T("creators_label")+': '+e.creators.join(", ")+'</div>';
    html+='</div>';
  }}

  if(e.tags&&e.tags.length)html+='<div class="section"><h2>'+T("tags_label")+'</h2><div class="tags">'+e.tags.map(function(t){{return '<span class="tag">'+t+'</span>'}}).join("")+'</div></div>';

  if(e.timeline&&e.timeline.length)html+='<div class="section"><h2>'+T("timeline_label")+'</h2>'+e.timeline.map(function(t){{return '<div class="tl-entry"><span class="tl-date">'+(t.date||"")+'</span><span>'+(t.event||"")+'</span></div>'}}).join("")+'</div>';

  if(e.aliases&&e.aliases.length)html+='<div class="section"><h2>'+T("aliases_label")+'</h2><div class="tags">'+e.aliases.map(function(a){{return '<span class="tag">'+a+'</span>'}}).join("")+'</div></div>';

  // ── Relationships with type summary ──
  if(e.relationships&&e.relationships.length){{
    var relByType={{}};
    e.relationships.forEach(function(r){{relByType[r.rel_type]=(relByType[r.rel_type]||0)+1}});
    html+='<div class="section"><h2>'+T("relationships_label")+' ('+e.relationships.length+')</h2>';
    html+='<div class="rel-summary">';
    Object.keys(relByType).sort().forEach(function(rt){{html+='<span class="rel-count-badge">'+rt+': <b>'+relByType[rt]+'</b></span>'}});
    html+='</div>';
    e.relationships.forEach(function(r){{
      var otherId=r.source_id===eid?r.target_id:r.source_id;
      html+='<div class="rel-item"><span class="rel-type">'+r.rel_type+'</span><a href="/entity/'+otherId+'">'+otherId+'</a></div>';
    }});
    html+='</div>';
  }}

  // Card metadata
  if(e.created_at||e.updated_at){{
    html+='<div class="section"><h2>'+T("card_metadata")+'</h2><div class="metadata-row">';
    if(e.created_at)html+='<span class="meta-item"><span class="meta-label">'+T("created_at")+':</span> '+esc(e.created_at).slice(0,16)+'</span>';
    if(e.updated_at)html+='<span class="meta-item"><span class="meta-label">'+T("updated_at")+':</span> '+esc(String(e.updated_at)).slice(0,16)+'</span>';
    html+='</div></div>';
  }}

  // Placeholder sections for lazy-loaded content
  html+='<div id="related-articles-section" class="section"><h2>'+T("related_articles")+'</h2><div class="spinner"><div class="loading"></div></div></div>';
  html+='<div id="similar-entities-section" class="section"><h2>'+T("similar_entities")+'</h2><div class="spinner"><div class="loading"></div></div></div>';

  html+='<a href="javascript:history.back()" class="back-link">'+T("back_label")+'</a>';
  document.getElementById("root").innerHTML=html;

  // Lazy-load related articles and similar entities
  loadRelatedArticles(eid);
  loadSimilarEntities(eid);
  }}catch(e){{showError("root",T("error_loading"),e.message);}}
}}

async function loadRelatedArticles(eid){{
  var section=document.getElementById("related-articles-section");
  try{{
    var resp=await fetch("/api/entities/"+eid+"/articles?limit=20");
    if(!resp.ok||!resp.ok){{section.innerHTML='<h2>'+T("related_articles")+'</h2><p style="color:#8b949e;font-size:12px">'+T("no_related_articles")+'</p>';return}}
    var articles=await resp.json();
    if(!articles||!articles.length){{section.innerHTML='<h2>'+T("related_articles")+'</h2><p style="color:#8b949e;font-size:12px">'+T("no_related_articles")+'</p>';return}}

    // 列表视图
    var h='<h2>'+T("related_articles")+' ('+articles.length+')</h2>';
    h+='<div class="article-list">';
    articles.forEach(function(a){{
      var s="★".repeat(a.score||0);
      h+='<a class="article-item" href="'+esc(a.url)+'" target="_blank" rel="noopener">';
      h+='<span class="article-title">'+esc(a.title_cn||a.title)+'</span>';
      h+='<span class="article-meta">';
      if(a.published)h+='<span class="article-date">'+esc(String(a.published).slice(0,10))+'</span>';
      h+='<span class="article-score" title="'+T("score_label")+'">'+s+'</span>';
      h+='</span></a>';
    }});
    h+='</div>';

    // 时间线视图（按日期分组）
    var withDate=articles.filter(function(a){{return a.published}}).sort(function(a,b){{return (b.published||"").localeCompare(a.published||"")}});
    if(withDate.length>=3){{
      h+='<span class="atl-toggle" onclick="var tl=document.getElementById(\\'article-timeline-'+eid+'\\');var show=tl.style.display===\\'block\\';tl.style.display=show?\\'none\\':\\'block\\';this.textContent=show?\\'▶ '+T("show_timeline")+'\\':\\'▼ '+T("hide_timeline")+'\\'">▶ '+T("show_timeline")+'</span>';
      h+='<div id="article-timeline-'+eid+'" class="article-timeline" style="display:none;margin-top:8px">';
      withDate.forEach(function(a){{
        h+='<div class="atl-entry"><div class="atl-date">'+esc(String(a.published).slice(0,10))+'</div>';
        h+='<div class="atl-title">'+esc(a.title_cn||a.title)+'</div>';
        h+='<div class="atl-source">'+esc(a.source||"")+' &middot; ★'.repeat(a.score||0)+'</div></div>';
      }});
      h+='</div>';
    }}

    section.innerHTML=h;
  }}catch(e){{section.innerHTML='<h2>'+T("related_articles")+'</h2><p style="color:#8b949e;font-size:12px">'+T("error_loading")+'</p>'}}
}}

async function loadSimilarEntities(eid){{
  var section=document.getElementById("similar-entities-section");
  try{{
    var resp=await fetch("/api/entities/"+eid+"/similar?limit=6");
    if(!resp.ok){{section.innerHTML='<h2>'+T("similar_entities")+'</h2><p style="color:#8b949e;font-size:12px">'+T("no_similar_entities")+'</p>';return}}
    var similar=await resp.json();
    if(!similar||!similar.length){{section.innerHTML='<h2>'+T("similar_entities")+'</h2><p style="color:#8b949e;font-size:12px">'+T("no_similar_entities")+'</p>';return}}
    var h='<h2>'+T("similar_entities")+'</h2><div class="similar-grid">';
    similar.forEach(function(s){{
      var c=s.color||C[s.type]||"#999";
      h+='<a class="similar-card" href="/entity/'+esc(s.id)+'">';
      h+='<span class="similar-badge" style="background:'+c+'">'+TLbl(s.type)+'</span>';
      h+='<span class="similar-name">'+esc(s.name)+'</span>';
      h+='<span class="similar-score">'+(s.similarity?Math.round(s.similarity*100)+"%":"")+'</span>';
      h+='</a>';
    }});
    h+='</div>';
    section.innerHTML=h;
  }}catch(e){{section.innerHTML='<h2>'+T("similar_entities")+'</h2><p style="color:#8b949e;font-size:12px">'+T("error_loading")+'</p>'}}
}}

function esc(s){{return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;")}}

init();
</script>
</body>
</html>"""
    path = ROOT_DIR / "reports" / "entity.html"
    path.write_text(html, encoding="utf-8")
    log.info(f"Entity shell (i18n): {path}")
    return path
