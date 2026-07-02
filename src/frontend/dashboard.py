"""
AI Intelligence Platform — Dashboard 生成器 (API-driven + i18n)

生成轻量 HTML shell，数据由 JavaScript fetch API 实时获取。
支持中英文切换，翻译由客户端 JS 运行时完成。
使用共享设计系统 (frontend_styles.py) 确保视觉一致性。
"""
import json
from pathlib import Path
from typing import Optional
from src.engine.utils import log, ensure_dir, ROOT_DIR
from src.interfaces.i18n import t, type_label, i18n_js, nav_html, TYPE_LABELS_ZH, TYPE_LABELS_EN
from .frontend_styles import TYPE_COLORS, ANIMATION_CSS, RESPONSIVE_CSS, ERROR_CSS, SHARED_JS, THEME_VARS


def generate_dashboard(output_dir: Optional[Path] = None, lang: str = "zh") -> Path:
    if output_dir is None: output_dir = ROOT_DIR / "reports"
    ensure_dir(output_dir)
    html = _build_html(lang)
    path = output_dir / "dashboard.html"
    path.write_text(html, encoding="utf-8")
    log.info(f"Dashboard ({lang}): {path}")
    return path


def _build_html(lang: str = "zh") -> str:
    return f'''<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{t("platform_title", lang)}</title>
<style>
{THEME_VARS}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:var(--bg-primary);color:var(--text-primary);padding:24px;max-width:1200px;margin:0 auto;animation:fadeIn .35s ease-out}}
h1{{font-size:32px;color:var(--text-primary);margin-bottom:8px;letter-spacing:-.03em}}
.hero-subtitle{{font-size:16px;color:var(--text-secondary);line-height:1.6;margin-bottom:6px;max-width:760px}}
.hero-desc{{font-size:13px;color:var(--text-muted);line-height:1.6;margin-bottom:12px;max-width:760px}}
.date{{font-size:12px;color:var(--text-secondary);margin-bottom:24px}}
.nav{{display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap;align-items:center}}
.nav a{{padding:6px 14px;border-radius:6px;font-size:13px;text-decoration:none;color:var(--text-primary);background:var(--bg-elevated);transition:background .15s}}
.nav a:hover{{background:var(--border)}}
.nav a.active{{background:var(--accent-subtle);color:var(--accent)}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}}
.card{{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);padding:20px}}
.card h2{{font-size:15px;margin-bottom:12px;display:flex;align-items:center;gap:8px}}
.card h3{{font-size:12px;color:var(--text-secondary);text-transform:uppercase;margin:16px 0 8px}}
.stat-row{{display:flex;gap:20px;margin-bottom:12px;flex-wrap:wrap}}
.stat{{text-align:center}}
.num{{display:block;font-size:24px;font-weight:700}}
.num.green{{color:var(--success)}}.num.red{{color:var(--danger)}}.num.blue{{color:var(--accent)}}
.lbl{{font-size:10px;color:var(--text-secondary);text-transform:uppercase}}
.headlines{{font-size:13px;line-height:1.8;padding-left:20px}}
.headlines li{{margin-bottom:4px}}
.btn{{display:inline-block;padding:6px 14px;background:#238636;color:#fff;border-radius:var(--radius-sm);text-decoration:none;font-size:12px;transition:background .15s}}
.btn:hover{{background:#2ea043}}
.btn-outline{{background:var(--bg-elevated);border:1px solid var(--border)}}
.btn-outline:hover{{background:var(--border)}}
.btn-sm{{padding:3px 10px;font-size:11px}}
.report-entry{{display:flex;align-items:center;gap:16px;padding:12px 0;border-bottom:1px solid var(--bg-elevated);font-size:13px}}
.report-entry:last-child{{border-bottom:none}}
.report-date{{min-width:90px;color:var(--text-secondary);font-size:12px}}
.report-type{{padding:2px 8px;border-radius:8px;font-size:10px;font-weight:600;text-transform:uppercase}}
.report-type.daily{{background:var(--accent-subtle);color:var(--accent)}}
.report-type.weekly{{background:#9c6ade22;color:#9c6ade}}
.report-type.monthly{{background:#f0883e22;color:#f0883e}}
.report-stars{{display:flex;gap:4px;font-size:10px;color:var(--text-secondary);min-width:70px}}
.report-counts{{font-size:10px;color:var(--text-muted)}}
.report-link{{color:var(--accent);text-decoration:none;flex:1}}
.report-link:hover{{text-decoration:underline}}
.favorite-btn{{padding:2px 7px;border:1px solid var(--border);background:var(--bg-elevated);color:var(--text-secondary);border-radius:999px;cursor:pointer;font-size:10px;line-height:1.4;vertical-align:middle}}
.favorite-btn:hover,.favorite-btn.is-favorited,.favorite-btn[aria-pressed="true"]{{border-color:var(--warning);background:#e3b34122;color:var(--warning)}}
.filter-bar{{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap}}
.filter-bar button{{padding:4px 10px;border:1px solid var(--border);background:var(--bg-elevated);color:var(--text-primary);border-radius:var(--radius-sm);cursor:pointer;font-size:11px;transition:background .15s}}
.filter-bar button:hover,.filter-bar button.active{{background:#1f6feb33;color:var(--accent);border-color:#1f6feb66}}
.type-bar{{margin-bottom:6px;display:flex;align-items:center;gap:8px;font-size:12px}}
.tb-label{{min-width:90px}}
.tb-count{{min-width:24px;text-align:right;color:var(--text-secondary)}}
.tb-fill{{flex:1;height:6px;background:var(--bg-elevated);border-radius:3px;overflow:hidden}}
.tb-fill div{{height:100%;border-radius:3px}}
.latest-card{{padding:8px 0;border-bottom:1px solid var(--bg-elevated);font-size:12px}}
.latest-card:last-child{{border-bottom:none}}
.latest-card p{{color:var(--text-secondary);margin-top:2px;font-size:11px}}
.badge{{display:inline-block;padding:1px 8px;border-radius:8px;font-size:9px;color:#fff;margin-right:6px}}
.footer{{text-align:center;margin-top:24px;font-size:11px;color:var(--text-muted)}}
.footer a{{color:var(--accent);text-decoration:none}}
.spinner{{text-align:center;padding:40px;color:var(--text-secondary)}}
.loading{{display:inline-block;width:20px;height:20px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin .6s linear infinite}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
.report-highlight{{background:linear-gradient(135deg,#1a2332,#0d2836);border:1px solid #1f6feb33}}
.lang-btn{{padding:4px 12px;border:1px solid var(--border);background:var(--bg-elevated);color:var(--text-primary);border-radius:var(--radius-sm);cursor:pointer;font-size:12px;margin-left:auto;transition:background .15s}}
.lang-btn+.lang-btn{{margin-left:0}}
.lang-btn:hover{{background:var(--border)}}
.card-hover{{transition:all .2s ease}}.card-hover:hover{{transform:translateY(-2px);box-shadow:var(--shadow);border-color:#58a6ff44}}
{ANIMATION_CSS}
{RESPONSIVE_CSS}
{ERROR_CSS}
@media(max-width:480px){{
  .report-entry{{display:grid;grid-template-columns:72px 1fr auto;gap:6px;align-items:center}}
  .report-type{{width:max-content}}
  .report-stars,.report-counts{{display:none}}
  .report-link{{grid-column:2}}
  .headlines .favorite-btn{{padding:1px 6px;font-size:9px}}
}}
</style>
</head>
<body>
<h1 data-i18n="platform_title">{t("platform_title", lang)}</h1>
<p class="hero-subtitle" data-i18n="platform_subtitle">{t("platform_subtitle", lang)}</p>
<p class="hero-desc" data-i18n="platform_description">{t("platform_description", lang)}</p>
<p class="date" id="date-line">{t("loading", lang)}</p>
{nav_html("today")}

<div class="card report-highlight" id="reports-hero" style="margin-bottom:16px">
  <div class="spinner"><div class="loading"></div><p style="margin-top:12px" data-i18n="loading_reports">{t("loading_reports", lang)}</p></div>
</div>

<div class="grid">
  <div class="card" id="daily-card"><div class="spinner"><div class="loading"></div></div></div>
  <div style="display:flex;flex-direction:column;gap:16px">
    <div class="card" id="kb-card"><div class="spinner"><div class="loading"></div></div></div>
    <div class="card" id="source-card"><div class="spinner"><div class="loading"></div></div></div>
  </div>
</div>

<div class="card" id="reports-history" style="margin-bottom:16px">
  <h2 data-i18n="report_history">{t("report_history", lang)}</h2>
  <div class="spinner"><div class="loading"></div></div>
</div>

<div class="card" id="recent-card" style="margin-bottom:16px"><div class="spinner"><div class="loading"></div></div></div>

	<div class="card" id="health-card" style="margin-bottom:16px">
	  <h2 data-i18n="health_title">{t("health_title", lang)}</h2>
	  <div class="spinner"><div class="loading"></div></div>
	</div>
<p class="footer"><span data-i18n="footer_text">{t("footer_text", lang)}</span> · <a href="/" data-i18n="today">{t("today", lang)}</a> · <a href="/library" data-i18n="topics">{t("topics", lang)}</a> · <a href="/timeline" data-i18n="timeline">{t("timeline", lang)}</a> · <a href="/research" data-i18n="research">{t("research", lang)}</a> · <a href="/my" data-i18n="my">{t("my", lang)}</a></p>

<script>
{SHARED_JS}
{i18n_js()}
</script>
<script>
const C={json.dumps(TYPE_COLORS)};
const L={json.dumps(TYPE_LABELS_ZH)};
const LE={json.dumps(TYPE_LABELS_EN)};

function starRow(s5,s4,s3){{return '<span title="★5">★5:'+(s5||0)+'</span> <span title="★4">★4:'+(s4||0)+'</span> <span title="★3">★3:'+(s3||0)+'</span>'}}
function favBtn(type,id,title){{return favoriteButtonHTML(type,id,title)}}

function renderHealth(h) {{
  if (!h || h.status==="error") {{
    document.getElementById("health-card").innerHTML='<h2>'+T("health_title")+'</h2><p style="color:#f85149;font-size:13px">'+(h?h.error:T("health_no_data"))+'</p>';
    return;
  }}
  const fmtTime=t=>t?t.replace("T"," ").slice(0,16):T("no_data");
  const fmtDur=d=>d?d.toFixed(1)+"s":"-";
  const statusBadge=s=>{{
    const map={{success:'<span style="color:#3fb950">'+T("health_success")+'</span>',running:'<span style="color:#58a6ff">'+T("health_running")+'</span>',dry_run:'<span style="color:#8b949e">'+T("health_dry_run")+'</span>'}};
    return map[s]||'<span style="color:#f85149">'+T("health_error")+'</span>';
  }};
  let html='<h2>'+T("health_title")+'</h2>';
  // DB stats row
  if (h.db) html+='<div class="stat-row" style="margin-bottom:12px"><div class="stat"><span class="num blue">'+(h.db.entities||0)+'</span><span class="lbl">'+T("entities_label")+'</span></div><div class="stat"><span class="num">'+(h.db.articles||0)+'</span><span class="lbl">'+T("articles_label")+'</span></div><div class="stat"><span class="num">'+(h.db.reports||0)+'</span><span class="lbl">'+T("reports_label")+'</span></div>';
  // 24h success rate
  if (h.recent_success_rate) html+='<div class="stat"><span class="num '+(h.recent_success_rate.total===h.recent_success_rate.success?"green":"red")+'">'+(h.recent_success_rate.total>0?Math.round(h.recent_success_rate.success/h.recent_success_rate.total*100)+"%":"-")+'</span><span class="lbl">'+T("health_success_rate")+'</span></div>';
  html+='</div>';
  // Last pipeline
  html+='<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;font-size:12px">';
  if (h.last_pipeline) {{
    const lp=h.last_pipeline;
    html+='<div style="background:#0d1117;padding:12px;border-radius:8px"><span style="color:#8b949e">'+T("health_last_pipeline")+'</span><br><strong>'+statusBadge(lp.status)+'</strong> · '+fmtTime(lp.started_at)+'<br><span style="color:#8b949e">'+T("health_processed")+': '+(lp.articles_processed||0)+'/'+(lp.articles_total||0)+' · '+T("health_duration")+': '+fmtDur(lp.duration_seconds)+'</span></div>';
  }} else html+='<div style="background:#0d1117;padding:12px;border-radius:8px"><span style="color:#8b949e">'+T("health_last_pipeline")+'</span><br><span style="color:#8b949e">'+T("health_no_data")+'</span></div>';
  if (h.last_collector) {{
    const lc=h.last_collector;
    html+='<div style="background:#0d1117;padding:12px;border-radius:8px"><span style="color:#8b949e">'+T("health_last_collector")+'</span><br><strong>'+statusBadge(lc.status)+'</strong> · '+fmtTime(lc.started_at)+'<br><span style="color:#8b949e">'+T("fetch_count")+': '+(lc.fetched||0)+' · +'+(lc.new_articles||0)+' · '+fmtDur(lc.duration_seconds)+'</span></div>';
  }} else html+='<div style="background:#0d1117;padding:12px;border-radius:8px"><span style="color:#8b949e">'+T("health_last_collector")+'</span><br><span style="color:#8b949e">'+T("health_no_data")+'</span></div>';
  html+='</div>';
  document.getElementById("health-card").innerHTML=html;
}}

async function init(){{
  try{{
  const [stats,articles,entities,dailies,weeklies,monthlies]=await Promise.all([
    apiFetch("/api/stats"),
    apiFetch("/api/articles?limit=30&min_score=3"),
    apiFetch("/api/entities"),
    apiFetch("/api/reports?type=daily&limit=30"),
    apiFetch("/api/reports?type=weekly&limit=10"),
    apiFetch("/api/reports?type=monthly&limit=10"),
  ]);
  document.getElementById("date-line").textContent = new Date().toISOString().slice(0,10)
    + " · " + T("entities_count_fmt", {{n: stats.entities, m: stats.articles, r: stats.relationships}});

  const allReports=[...dailies.map(r=>({{...r,type:"daily"}})),...weeklies.map(r=>({{...r,type:"weekly"}})),...monthlies.map(r=>({{...r,type:"monthly"}}))].sort((a,b)=>b.date.localeCompare(a.date));
  const today=new Date().toISOString().slice(0,10);
  const todayReport=dailies.find(r=>r.date===today);
  const latestWeekly=weeklies[0];
  const latestMonthly=monthlies[0];

  // Reports Hero
  let heroHTML='<h2>'+T("report_center")+'</h2><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px">';
  heroHTML+='<div style="background:#0d1117;border-radius:8px;padding:16px"><h3 style="margin:0 0 8px">'+T("today_daily")+'</h3>';
  if(todayReport){{
    heroHTML+='<div class="stat-row"><div class="stat"><span class="num blue">'+(todayReport.star5||0)+'</span><span class="lbl">★5</span></div><div class="stat"><span class="num">'+(todayReport.star4||0)+'</span><span class="lbl">★4</span></div><div class="stat"><span class="num">'+(todayReport.star3||0)+'</span><span class="lbl">★3</span></div><div class="stat"><span class="num">'+(todayReport.fetched||0)+'</span><span class="lbl">'+T("fetch_count")+'</span></div></div><a href="/report-files/'+today+'.md" class="btn btn-sm" style="margin-top:8px">'+T("read_daily")+'</a>';
  }}else{{
    heroHTML+='<p style="color:#8b949e;font-size:13px">'+T("not_generated_yet")+'</p>';
  }}
  heroHTML+='</div>';
  heroHTML+='<div style="background:#0d1117;border-radius:8px;padding:16px"><h3 style="margin:0 0 8px">'+T("latest_weekly")+'</h3>';
  if(latestWeekly){{
    heroHTML+='<p style="font-size:18px;font-weight:700;color:#9c6ade">'+latestWeekly.date+'</p><a href="/report-files/weekly-'+latestWeekly.date+'.md" class="btn btn-sm" style="margin-top:8px">'+T("read_weekly")+'</a>';
  }}else{{heroHTML+='<p style="color:#8b949e;font-size:13px">'+T("not_generated_yet")+'</p>'}}
  heroHTML+='</div>';
  heroHTML+='<div style="background:#0d1117;border-radius:8px;padding:16px"><h3 style="margin:0 0 8px">'+T("latest_monthly")+'</h3>';
  if(latestMonthly){{
    heroHTML+='<p style="font-size:18px;font-weight:700;color:#f0883e">'+latestMonthly.date+'</p><a href="/report-files/monthly-'+latestMonthly.date+'.md" class="btn btn-sm" style="margin-top:8px">'+T("read_monthly")+'</a>';
  }}else{{heroHTML+='<p style="color:#8b949e;font-size:13px">'+T("not_generated_yet")+'</p>'}}
  heroHTML+='</div></div>';
  document.getElementById("reports-hero").innerHTML=heroHTML;

  // Articles Card
  const sc=(s)=>articles.filter(a=>a.score===s).length;
  const top5=articles.filter(a=>a.score>=5).slice(0,5);
  const top4=articles.filter(a=>a.score===4).slice(0,8);
  document.getElementById("daily-card").innerHTML=
    '<h2>'+T("headlines")+'</h2>'+
    '<div class="stat-row">'+
    '<div class="stat"><span class="num">'+articles.length+'</span><span class="lbl">'+T("rating_3plus")+'</span></div>'+
    '<div class="stat"><span class="num">'+sc(5)+'</span><span class="lbl">★5</span></div>'+
    '<div class="stat"><span class="num">'+sc(4)+'</span><span class="lbl">★4</span></div>'+
    '<div class="stat"><span class="num">'+sc(3)+'</span><span class="lbl">★3</span></div></div>'+
    (top5.length?'<h3>'+T("star5_headlines")+'</h3><ol class="headlines">'+top5.map(a=>'<li><a href="'+a.url+'" target="_blank" style="color:#58a6ff">'+(a.title_cn||a.title)+'</a> <span style="color:#484f58;font-size:10px">'+(a.source||'')+'</span> '+favBtn('news',a.url||a.id,a.title_cn||a.title)+'</li>').join("")+'</ol>':'')+
    '<h3>'+T("star4_highlights")+'</h3><ol class="headlines">'+top4.map(a=>'<li>'+(a.title_cn||a.title)+' <span style="color:#484f58;font-size:10px">'+(a.source||'')+'</span> '+favBtn('news',a.url||a.id,a.title_cn||a.title)+'</li>').join("")+'</ol>';

  // KB Card
  const tc={{}};entities.forEach(e=>{{tc[e.type]=(tc[e.type]||0)+1}});
  document.getElementById("kb-card").innerHTML=
    '<h2>'+T("kb_title")+'</h2>'+
    '<div class="stat-row"><div class="stat"><span class="num">'+stats.entities+'</span><span class="lbl">'+T("entities_label")+'</span></div><div class="stat"><span class="num">'+Object.keys(tc).length+'</span><span class="lbl">'+T("types_label")+'</span></div></div>'+
    Object.entries(tc).sort((a,b)=>b[1]-a[1]).map(([t,n])=>'<div class="type-bar"><span class="tb-label" style="color:'+(C[t]||"#999")+'">'+TLbl(t)+'</span><span class="tb-count">'+n+'</span><div class="tb-fill"><div style="width:'+(n/Math.max(1,stats.entities)*100)+'%;background:'+(C[t]||"#999")+'"></div></div></div>').join("")+
    '<a href="/library" class="btn btn-outline btn-sm" style="margin-top:12px">'+T("browse_kb")+'</a>';

  // Source Card
  document.getElementById("source-card").innerHTML='<h2>'+T("data_pipeline")+'</h2><div class="stat-row"><div class="stat"><span class="num">'+stats.articles+'</span><span class="lbl">'+T("articles_label")+'</span></div><div class="stat"><span class="num">'+allReports.length+'</span><span class="lbl">'+T("reports_label")+'</span></div></div><p style="font-size:11px;color:#8b949e;margin-top:8px">'+T("pipeline_desc")+'</p>';

  // Report History
  window.renderHistory=function(f){{
    const filtered=f==="all"?allReports:allReports.filter(r=>r.type===f);
    const typeLabel=T("filter_"+f);
    let h='<h2>'+T("report_history")+' <span style="font-size:11px;color:#8b949e;font-weight:normal">('+filtered.length+')</span></h2>';
    h+='<div class="filter-bar"><button class="'+(f==="all"?"active":"")+'" onclick="renderHistory(\\'all\\')">'+T("all_label")+' ('+allReports.length+')</button><button class="'+(f==="daily"?"active":"")+'" onclick="renderHistory(\\'daily\\')">'+T("filter_daily")+' ('+dailies.length+')</button><button class="'+(f==="weekly"?"active":"")+'" onclick="renderHistory(\\'weekly\\')">'+T("filter_weekly")+' ('+weeklies.length+')</button><button class="'+(f==="monthly"?"active":"")+'" onclick="renderHistory(\\'monthly\\')">'+T("filter_monthly")+' ('+monthlies.length+')</button></div>';
    if(!filtered.length){{h+='<p style="color:#8b949e;font-size:13px">'+T("no_reports_found")+'</p>'}}
    else{{h+=filtered.slice(0,30).map(r=>{{
      const isDaily=r.type==="daily";
      const fname=isDaily?r.date+'.md':r.type+'-'+r.date+'.md';
      return '<div class="report-entry"><span class="report-date">'+r.date+'</span><span class="report-type '+r.type+'">'+T("filter_"+r.type)+'</span>'+(isDaily?'<span class="report-stars">'+starRow(r.star5,r.star4,r.star3)+'</span>':'<span class="report-stars"></span>')+'<a href="/report-files/'+fname+'" class="report-link">'+T("view_report")+'</a>'+favBtn('report',r.type+'-'+r.date,T("filter_"+r.type)+' '+r.date)+(isDaily?'<span class="report-counts">'+(r.fetched||0)+'&rarr;'+(r.filtered||0)+'</span>':'')+'</div>'}}).join("")}}
    document.getElementById("reports-history").innerHTML=h;
  }};
  window.renderHistory("all");

  // Top Entities
  const latest=entities.sort((a,b)=>(b.importance||0)-(a.importance||0)).slice(0,6);
  document.getElementById("recent-card").innerHTML=
    '<h2>'+T("core_entities")+'</h2>'+
    '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:8px">'+latest.map(e=>'<div class="latest-card"><span class="badge" style="background:'+(e.color||"#999")+'">'+TLbl(e.type)+'</span><a href="/entity/'+e.id+'" style="color:#58a6ff;text-decoration:none"><strong>'+e.name+'</strong></a> '+favBtn('entity',e.id,e.name)+'<p>'+(e.summary||"").slice(0,100)+'</p></div>').join("")+'</div>';

  // Health Panel
  try{{
    const health=await apiFetch("/api/health");
    renderHealth(health);
  }}catch(e){{renderHealth(null)}}

  }}catch(e){{
    showError("reports-hero",T("error_loading"),e.message);
    document.getElementById("daily-card").innerHTML="";
    document.getElementById("kb-card").innerHTML="";
    document.getElementById("source-card").innerHTML="";
    document.getElementById("reports-history").innerHTML="";
    document.getElementById("recent-card").innerHTML="";
    document.getElementById("health-card").innerHTML="";
  }}
}}
init();
</script>
</body>
</html>'''
