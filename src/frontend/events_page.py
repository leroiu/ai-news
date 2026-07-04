"""AI 行业里程碑事件页面生成器。"""
import json
from pathlib import Path
from typing import Optional

from .frontend_styles import (
    TYPE_COLORS, TYPE_ICONS, RESET_CSS, NAV_CSS, SPINNER_CSS,
    ANIMATION_CSS, RESPONSIVE_CSS, ERROR_CSS, INTELLIGENCE_CSS,
    ACTION_COMPONENT_CSS, ACCESSIBILITY_CSS, SHARED_JS,
)
from src.interfaces.i18n import t, i18n_js, nav_html
from src.engine.utils import ROOT_DIR, ensure_dir, log


def generate_events_page(output_dir: Optional[Path] = None, lang: str = "zh") -> Path:
    """生成 API 驱动的里程碑事件页面。"""
    output_dir = output_dir or ROOT_DIR / "reports"
    ensure_dir(output_dir)
    path = output_dir / "events.html"
    path.write_text(_build_html(lang), encoding="utf-8")
    log.info("Events page (%s): %s", lang, path)
    return path


def _build_html(lang: str = "zh") -> str:
    template = '''<!DOCTYPE html>
<html lang="__LANG__">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>__TITLE__</title>
<style>
__RESET_CSS__
body{padding:24px;max-width:1180px;margin:0 auto;animation:fadeIn .35s ease-out}
__NAV_CSS__
__SPINNER_CSS__
.hero{padding:40px 24px 28px;text-align:center}.eyebrow{color:var(--event-color);font-size:11px;font-weight:700;letter-spacing:.16em;text-transform:uppercase}
h1{margin:8px 0;font-size:32px;color:var(--text-primary)}.subtitle{max-width:640px;margin:auto;color:var(--text-secondary);font-size:14px;line-height:1.7}
.controls{display:flex;gap:10px;margin:10px auto 28px;padding:12px;background:var(--bg-card);border:1px solid var(--border);border-radius:10px}
.controls input,.controls select{min-width:0;padding:9px 12px;background:var(--bg-primary);border:1px solid var(--border);border-radius:6px;color:var(--text-primary);font:inherit}
.controls input{flex:1}.controls select{width:180px}.controls :focus{outline:2px solid #58a6ff55;border-color:var(--accent)}
.count{align-self:center;white-space:nowrap;color:var(--text-secondary);font-size:12px}
.timeline{position:relative;display:grid;gap:24px;padding:8px 0 40px}.timeline:before{content:"";position:absolute;top:0;bottom:0;left:50%;width:2px;background:linear-gradient(var(--event-color),#58a6ff,#30363d);transform:translateX(-1px)}
.event-item{position:relative;display:grid;grid-template-columns:1fr 48px 1fr;align-items:start}.event-card{grid-column:1;background:var(--bg-card);border:1px solid var(--border);border-radius:8px;overflow:hidden}
.event-item:nth-child(even) .event-card{grid-column:3}.event-dot{grid-column:2;grid-row:1;width:14px;height:14px;margin:24px auto 0;border:3px solid var(--bg-primary);border-radius:50%;background:var(--event-color);box-shadow:0 0 0 2px #ff9da655}
.event-main{display:block;width:100%;padding:20px 22px;border:0;background:none;color:inherit;text-align:left;cursor:pointer}.event-main:hover{background:#21262d55}
.event-date{color:var(--event-color);font-size:12px;font-weight:700;letter-spacing:.06em}.event-name{margin:7px 0 8px;color:var(--text-primary);font-size:18px}.event-summary{color:var(--text-secondary);font-size:13px;line-height:1.65;white-space:pre-line}
.event-meta{display:flex;justify-content:space-between;gap:12px;margin-top:14px}.stars{color:#e3b341;letter-spacing:2px}.expand-hint{color:var(--accent);font-size:11px}
.favorite-btn{padding:2px 7px;border:1px solid var(--border);background:var(--bg-elevated);color:var(--text-secondary);border-radius:999px;cursor:pointer;font-size:10px;line-height:1.4}.favorite-btn:hover,.favorite-btn.is-favorited,.favorite-btn[aria-pressed="true"]{border-color:var(--warning);background:#e3b34122;color:var(--warning)}
.event-detail{display:none;padding:0 22px 20px;border-top:1px solid #30363d}.event-detail.open{display:block;animation:fadeIn .25s ease-out}.detail-section{margin-top:16px}.detail-section h3{margin-bottom:6px;color:var(--text-secondary);font-size:11px;text-transform:uppercase;letter-spacing:.08em}.detail-section p{font-size:13px;line-height:1.7;white-space:pre-line}
.relations{display:flex;flex-wrap:wrap;gap:7px}.relation{padding:4px 9px;border:1px solid var(--border);border-radius:12px;color:var(--accent);text-decoration:none;font-size:11px}.relation:hover{border-color:var(--accent);background:#1f6feb18}
.empty{text-align:center;padding:64px 20px;color:var(--text-secondary)}.empty strong{display:block;margin-bottom:8px;color:var(--text-primary);font-size:16px}
@media(max-width:768px){.hero{padding:24px 8px 20px}.controls{position:static}.timeline:before{left:18px}.event-item{grid-template-columns:36px 1fr}.event-card,.event-item:nth-child(even) .event-card{grid-column:2}.event-dot{grid-column:1}.event-main{padding:18px}.event-detail{padding:0 18px 18px}}
@media(max-width:480px){.controls{flex-direction:column}.controls select{width:100%}.count{align-self:flex-start}h1{font-size:24px}.timeline{gap:16px}}
@media(min-width:1024px){.event-card{max-width:520px}.event-item:nth-child(odd) .event-card{justify-self:end}.event-item:nth-child(even) .event-card{justify-self:start}}
__ANIMATION_CSS__
__RESPONSIVE_CSS__
__ERROR_CSS__
__INTELLIGENCE_CSS__
__ACTION_COMPONENT_CSS__
__ACCESSIBILITY_CSS__
</style>
</head>
<body data-page-template="narrative" style="--event-color:__EVENT_COLOR__">
<a class="skip-link" href="#events-root">__SKIP_TO_CONTENT__</a>
__NAV__
<header class="hero"><div class="eyebrow" data-i18n="events_eyebrow">__EYEBROW__</div><h1 data-i18n="events_title">__TITLE__</h1><p class="subtitle" data-i18n="events_subtitle">__SUBTITLE__</p></header>
<section class="controls" aria-label="Event filters"><input id="event-search" type="search" data-i18n-placeholder="events_search_placeholder" placeholder="__SEARCH__"><select id="year-filter" aria-label="__YEAR_FILTER__"></select><span class="count" id="event-count"></span></section>
<main id="events-root"><div class="spinner"><div class="loading"></div><p data-i18n="loading">__LOADING__</p></div></main>
<script>
__SHARED_JS__
__I18N_JS__
const EVENT_COLOR=__EVENT_COLOR__, EVENT_ICON=__EVENT_ICON__;
let events=[], entityMap=new Map(), detailCache=new Map();
const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const eventYear=e=>(e.release_date||"").slice(0,4)||"unknown";

function applyEventI18n(){
  applyI18n(); document.title=T("events_title");
  document.querySelectorAll("[data-i18n-placeholder]").forEach(el=>el.placeholder=T(el.dataset.i18nPlaceholder));
}
function buildYearFilter(){
  const select=document.getElementById("year-filter"), current=select.value;
  const years=[...new Set(events.map(eventYear).filter(y=>y!=="unknown"))].sort().reverse();
  select.innerHTML='<option value="">'+T("events_all_years")+'</option>'+years.map(y=>'<option value="'+y+'">'+y+'</option>').join("");
  if(years.includes(current)) select.value=current;
}
function filteredEvents(){
  const q=document.getElementById("event-search").value.trim().toLowerCase(), year=document.getElementById("year-filter").value;
  return events.filter(e=>(!year||eventYear(e)===year)&&(!q||[e.name,e.summary,e.significance].some(v=>String(v||"").toLowerCase().includes(q))));
}
function render(){
  const list=filteredEvents(), root=document.getElementById("events-root");
  document.getElementById("event-count").textContent=T("events_count", {n: list.length});
  if(!list.length){root.innerHTML='<div class="empty"><strong>'+T("events_empty")+'</strong><span>'+T("events_empty_hint")+'</span></div>';return}
  root.innerHTML=ratingHelpHTML()+'<div class="timeline">'+list.map(e=>'<article class="event-item"><span class="event-dot" aria-hidden="true"></span><div class="event-card card-hover"><button class="event-main" data-id="'+esc(e.id)+'" aria-expanded="false" onclick="toggleEvent(this.dataset.id,this)"><div class="event-date">'+esc(e.release_date||T("events_unknown_date"))+'</div><h2 class="event-name">'+esc(EVENT_ICON+' '+e.name)+'</h2><p class="event-summary">'+evidenceLabelHTML('fact')+' '+esc(e.summary||T("no_data"))+'</p><div class="event-meta">'+editorialRatingHTML(e.importance||0)+'<span class="expand-hint">'+T("events_expand")+'</span></div></button><div style="padding:0 22px 16px">'+favoriteButtonHTML('event',e.id,e.name,'','/entity/'+e.id)+'</div><div class="event-detail" id="detail-'+esc(e.id)+'"></div></div></article>').join("")+'</div>';
}
async function toggleEvent(id,button){
  const detail=document.getElementById("detail-"+id), opening=!detail.classList.contains("open");
  document.querySelectorAll(".event-detail.open").forEach(el=>el.classList.remove("open"));
  document.querySelectorAll(".event-main[aria-expanded=true]").forEach(el=>el.setAttribute("aria-expanded","false"));
  if(!opening)return; button.setAttribute("aria-expanded","true"); detail.classList.add("open");
  if(detailCache.has(id)){detail.innerHTML=detailCache.get(id);return}
  detail.innerHTML='<div class="spinner"><div class="loading"></div></div>';
  try{const data=await apiFetch("/api/entities/"+encodeURIComponent(id));const html=detailHtml(data);detailCache.set(id,html);detail.innerHTML=html}
  catch(err){detail.innerHTML='<p class="detail-section">'+esc(T("error_loading"))+': '+esc(err.message)+'</p>'}
}
function detailHtml(e){
  const related=[...new Set((e.relationships||[]).map(r=>r.source_id===e.id?r.target_id:r.source_id).filter(Boolean))];
  const relations=related.length?related.map(id=>{const item=entityMap.get(id);return '<a class="relation" href="/entity/'+encodeURIComponent(id)+'" onclick="event.stopPropagation()">'+esc(item?.name||id)+'</a>'}).join(""):T("events_no_relations");
  return '<section class="detail-section"><h3>'+T("events_significance")+'</h3><p>'+esc(e.significance||T("no_data"))+'</p></section><section class="detail-section"><h3>'+T("events_background")+'</h3><p>'+esc(e.background||T("events_no_background"))+'</p></section><section class="detail-section"><h3>'+T("events_related")+'</h3><div class="relations">'+relations+'</div></section>';
}
async function init(){
  applyEventI18n();
  try{const [eventData,allEntities]=await Promise.all([apiFetch("/api/entities?type=event"),apiFetch("/api/entities")]);events=(eventData||[]).sort((a,b)=>(b.release_date||"").localeCompare(a.release_date||""));entityMap=new Map((allEntities||[]).map(e=>[e.id,e]));buildYearFilter();render()}
  catch(err){showError("events-root",T("error_loading"),err.message)}
}
document.getElementById("event-search").addEventListener("input",render);
document.getElementById("year-filter").addEventListener("change",render);
init();
</script>
</body></html>'''
    replacements = {
        "__LANG__": lang, "__TITLE__": t("events_title", lang),
        "__EYEBROW__": t("events_eyebrow", lang), "__SUBTITLE__": t("events_subtitle", lang),
        "__SEARCH__": t("events_search_placeholder", lang), "__YEAR_FILTER__": t("events_year_filter", lang),
        "__LOADING__": t("loading", lang), "__SKIP_TO_CONTENT__": t("skip_to_content", lang), "__NAV__": nav_html("events"),
        "__RESET_CSS__": RESET_CSS, "__NAV_CSS__": NAV_CSS, "__SPINNER_CSS__": SPINNER_CSS,
        "__ANIMATION_CSS__": ANIMATION_CSS, "__RESPONSIVE_CSS__": RESPONSIVE_CSS,
        "__ERROR_CSS__": ERROR_CSS, "__INTELLIGENCE_CSS__": INTELLIGENCE_CSS,
        "__ACTION_COMPONENT_CSS__": ACTION_COMPONENT_CSS, "__ACCESSIBILITY_CSS__": ACCESSIBILITY_CSS,
        "__SHARED_JS__": SHARED_JS, "__I18N_JS__": i18n_js(),
        "__EVENT_COLOR__": json.dumps(TYPE_COLORS["event"]), "__EVENT_ICON__": json.dumps(TYPE_ICONS["event"], ensure_ascii=False),
    }
    for key, value in replacements.items():
        template = template.replace(key, value)
    return template
