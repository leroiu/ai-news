"""
AI Intelligence Platform — Dashboard 生成器 (API-driven + i18n)

生成轻量 HTML shell，数据由 JavaScript fetch API 实时获取。
支持中英文切换，翻译由客户端 JS 运行时完成。
使用共享设计系统 (frontend_styles.py) 确保视觉一致性。
"""
from pathlib import Path
from typing import Optional
from src.engine.utils import log, ensure_dir, ROOT_DIR
from src.interfaces.i18n import t, i18n_js, nav_html
from .frontend_styles import ANIMATION_CSS, RESPONSIVE_CSS, ERROR_CSS, INTELLIGENCE_CSS, SHARED_JS, THEME_VARS


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
body{{font-family:var(--font-sans);background:var(--bg-primary);color:var(--text-primary);padding:36px 28px 56px;max-width:var(--content-max);margin:0 auto;animation:fadeIn .35s ease-out}}
h1{{max-width:720px;font-family:var(--font-display);font-size:46px;font-weight:650;color:var(--text-primary);margin-bottom:10px;letter-spacing:-.045em;line-height:1.08}}
.hero-subtitle{{font-family:var(--font-display);font-size:20px;color:var(--text-secondary);line-height:1.55;margin-bottom:6px;max-width:760px}}
.hero-desc{{font-size:13px;color:var(--text-muted);line-height:1.6;margin-bottom:12px;max-width:760px}}
.date{{font-size:11px;color:var(--text-muted);margin:18px 0 28px;letter-spacing:.04em}}
.nav{{display:flex;gap:4px;margin-bottom:30px;padding:5px;border:1px solid var(--border);border-radius:10px;flex-wrap:wrap;align-items:center;width:max-content;max-width:100%}}
.nav a{{padding:7px 14px;border-radius:6px;font-size:12px;text-decoration:none;color:var(--text-secondary);background:transparent;transition:background .15s,color .15s}}
.nav a:hover{{background:var(--border)}}
.nav a.active{{background:var(--accent-subtle);color:var(--accent)}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}}
.card{{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);padding:24px}}
.card h2{{font-family:var(--font-display);font-size:19px;font-weight:650;margin-bottom:16px;display:flex;align-items:center;gap:8px}}
.card h3{{font-size:12px;color:var(--text-secondary);text-transform:uppercase;margin:16px 0 8px}}
.stat-row{{display:flex;gap:20px;margin-bottom:12px;flex-wrap:wrap}}
.stat{{text-align:center}}
.num{{display:block;font-size:24px;font-weight:700}}
.num.green{{color:var(--success)}}.num.red{{color:var(--danger)}}.num.blue{{color:var(--accent)}}
.lbl{{font-size:10px;color:var(--text-secondary);text-transform:uppercase}}
.headlines{{font-size:13px;line-height:1.8;padding-left:20px}}
.headlines li{{margin-bottom:4px}}
.btn{{display:inline-block;padding:6px 14px;background:var(--accent);color:var(--bg-primary);border-radius:var(--radius-sm);text-decoration:none;font-size:12px;font-weight:650;transition:filter .15s}}
.btn:hover{{filter:brightness(1.12)}}
.btn-outline{{background:var(--bg-elevated);border:1px solid var(--border);color:var(--text-primary)}}
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
.badge{{display:inline-block;padding:1px 8px;border-radius:8px;font-size:9px;color:#fff;margin-right:6px}}
.footer{{text-align:center;margin-top:24px;font-size:11px;color:var(--text-muted)}}
.footer a{{color:var(--accent);text-decoration:none}}
.spinner{{text-align:center;padding:40px;color:var(--text-secondary)}}
.loading{{display:inline-block;width:20px;height:20px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin .6s linear infinite}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
.report-highlight{{position:relative;overflow:hidden;background:var(--bg-card);border-color:var(--border-strong)}}
.report-highlight:before{{content:"TODAY / BRIEFING";display:block;margin-bottom:16px;color:var(--accent);font-size:10px;font-weight:700;letter-spacing:.16em}}
.home-masthead{{position:relative;padding:24px 0 30px;margin-bottom:28px;border-bottom:1px solid var(--border)}}
.home-masthead:before{{content:"AI OBSERVATORY / DAILY INTELLIGENCE";display:block;margin-bottom:18px;color:var(--accent);font-size:10px;font-weight:750;letter-spacing:.18em}}
.home-masthead .date{{margin-bottom:22px}}
.home-masthead .nav{{margin-bottom:0}}
.editorial-section{{background:transparent;border:0;border-top:1px solid var(--border-strong);border-radius:0;padding:24px 0 30px}}
#reports-hero{{margin-bottom:34px!important;border-top-color:var(--accent)}}
#reports-hero>div{{gap:0!important;border-top:1px solid var(--border)}}
#reports-hero>div>div{{background:transparent!important;border-radius:0!important;padding:18px 20px!important;border-right:1px solid var(--border)}}
#reports-hero>div>div:first-child{{padding-left:0!important}}#reports-hero>div>div:last-child{{border-right:0;padding-right:0!important}}
.editorial-grid{{grid-template-columns:1fr;margin-bottom:28px}}
.editorial-grid>.card{{background:transparent;border:0;border-top:1px solid var(--border-strong);border-radius:0;padding:24px 0}}
.editorial-section h2,.editorial-grid h2{{font-size:23px;letter-spacing:-.02em}}
#daily-card .stat-row{{justify-content:flex-start;padding-bottom:16px;border-bottom:1px solid var(--border)}}
#reports-history .report-entry{{padding:15px 0}}
[data-theme="light"] .editorial-section{{margin-left:-22px;margin-right:-22px;padding-left:22px;padding-right:22px;background:var(--bg-card);border-top-color:var(--border-strong);box-shadow:0 1px 0 var(--border)}}
[data-theme="light"] .editorial-grid{{gap:12px}}
[data-theme="light"] .editorial-grid>.card{{padding:24px;background:var(--bg-card);border-top:2px solid var(--border-strong)}}
.lang-btn{{padding:4px 12px;border:1px solid var(--border);background:var(--bg-elevated);color:var(--text-primary);border-radius:var(--radius-sm);cursor:pointer;font-size:12px;margin-left:auto;transition:background .15s}}
.lang-btn+.lang-btn{{margin-left:0}}
.lang-btn:hover{{background:var(--border)}}
.card-hover{{transition:transform .2s ease,border-color .2s ease}}.card-hover:hover{{transform:translateY(-2px);border-color:var(--accent)}}
{ANIMATION_CSS}
{RESPONSIVE_CSS}
{ERROR_CSS}
{INTELLIGENCE_CSS}
@media(max-width:768px){{[data-theme="light"] .editorial-section{{margin-left:0;margin-right:0}}}}
@media(max-width:480px){{
  body{{padding:18px 16px 40px}}h1{{font-size:38px}}.hero-subtitle{{font-size:17px}}.hero-desc{{font-size:12px}}.nav{{width:100%;flex-wrap:nowrap;overflow-x:auto}}.card{{padding:18px}}.grid{{gap:10px}}
  .home-masthead{{padding-top:12px;margin-bottom:24px}}.home-masthead:before{{margin-bottom:14px}}
  #reports-hero>div{{display:block!important}}#reports-hero>div>div{{padding:16px 0!important;border-right:0;border-bottom:1px solid var(--border)}}
  .editorial-grid{{grid-template-columns:1fr;gap:8px}}.editorial-section{{padding:20px 0 24px}}
  .report-entry{{display:grid;grid-template-columns:72px 1fr auto;gap:6px;align-items:center}}
  .report-type{{width:max-content}}
  .report-stars,.report-counts{{display:none}}
  .report-link{{grid-column:2}}
  .headlines .favorite-btn{{padding:1px 6px;font-size:9px}}
}}
</style>
</head>
<body data-page-template="overview">
<header class="home-masthead">
<h1 data-i18n="platform_title">{t("platform_title", lang)}</h1>
<p class="hero-subtitle" data-i18n="platform_subtitle">{t("platform_subtitle", lang)}</p>
<p class="hero-desc" data-i18n="platform_description">{t("platform_description", lang)}</p>
<p class="date" id="date-line">{t("loading", lang)}</p>
{nav_html("today")}
</header>

<div class="card report-highlight editorial-section" id="reports-hero" style="margin-bottom:16px">
  <div class="spinner"><div class="loading"></div><p style="margin-top:12px" data-i18n="loading_reports">{t("loading_reports", lang)}</p></div>
</div>

<div class="grid editorial-grid">
  <div class="card" id="daily-card"><div class="spinner"><div class="loading"></div></div></div>
</div>

<div class="card editorial-section" id="reports-history" style="margin-bottom:16px">
  <h2 data-i18n="report_history">{t("report_history", lang)}</h2>
  <div class="spinner"><div class="loading"></div></div>
</div>

<p class="footer"><span data-i18n="footer_text">{t("footer_text", lang)}</span> · <a href="/" data-i18n="today">{t("today", lang)}</a> · <a href="/library" data-i18n="topics">{t("topics", lang)}</a> · <a href="/timeline" data-i18n="timeline">{t("timeline", lang)}</a> · <a href="/research" data-i18n="research">{t("research", lang)}</a> · <a href="/my" data-i18n="my">{t("my", lang)}</a></p>

<script>
{SHARED_JS}
{i18n_js()}
</script>
<script>
function starRow(s5,s4,s3){{return '<span title="★5">★5:'+(s5||0)+'</span> <span title="★4">★4:'+(s4||0)+'</span> <span title="★3">★3:'+(s3||0)+'</span>'}}
function favBtn(type,id,title,href){{return favoriteButtonHTML(type,id,title,"",href)}}

async function init(){{
  try{{
  const [articles,dailies,weeklies,monthlies]=await Promise.all([
    apiFetch("/api/articles?limit=30&min_score=3"),
    apiFetch("/api/reports?type=daily&limit=30"),
    apiFetch("/api/reports?type=weekly&limit=10"),
    apiFetch("/api/reports?type=monthly&limit=10"),
  ]);
  document.getElementById("date-line").textContent = new Date().toISOString().slice(0,10);

  const allReports=[...dailies.map(r=>({{...r,type:"daily"}})),...weeklies.map(r=>({{...r,type:"weekly"}})),...monthlies.map(r=>({{...r,type:"monthly"}}))].sort((a,b)=>b.date.localeCompare(a.date));
  const today=new Date().toISOString().slice(0,10);
  const todayReport=dailies.find(r=>r.date===today);
  const latestWeekly=weeklies[0];
  const latestMonthly=monthlies[0];

  // Reports Hero
  let heroHTML='<h2>'+T("report_center")+'</h2><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px">';
  heroHTML+='<div style="background:#0d1117;border-radius:8px;padding:16px"><h3 style="margin:0 0 8px">'+T("today_daily")+'</h3>';
  if(todayReport){{
    heroHTML+='<div class="stat-row"><div class="stat"><span class="num blue">'+(todayReport.star5||0)+'</span><span class="lbl">★5</span></div><div class="stat"><span class="num">'+(todayReport.star4||0)+'</span><span class="lbl">★4</span></div><div class="stat"><span class="num">'+(todayReport.star3||0)+'</span><span class="lbl">★3</span></div><div class="stat"><span class="num">'+(todayReport.fetched||0)+'</span><span class="lbl">'+T("fetch_count")+'</span></div></div><a href="/report/'+today+'.md" class="btn btn-sm" style="margin-top:8px">'+T("read_daily")+'</a>';
  }}else{{
    heroHTML+='<p style="color:var(--text-muted);font-size:13px">'+T("not_generated_yet")+'</p>';
  }}
  heroHTML+='</div>';
  heroHTML+='<div style="background:#0d1117;border-radius:8px;padding:16px"><h3 style="margin:0 0 8px">'+T("latest_weekly")+'</h3>';
  if(latestWeekly){{
    heroHTML+='<p style="font-size:18px;font-weight:700;color:#9c6ade">'+latestWeekly.date+'</p><a href="/report/weekly-'+latestWeekly.date+'.md" class="btn btn-sm" style="margin-top:8px">'+T("read_weekly")+'</a>';
  }}else{{heroHTML+='<p style="color:var(--text-muted);font-size:13px">'+T("not_generated_yet")+'</p>'}}
  heroHTML+='</div>';
  heroHTML+='<div style="background:#0d1117;border-radius:8px;padding:16px"><h3 style="margin:0 0 8px">'+T("latest_monthly")+'</h3>';
  if(latestMonthly){{
    heroHTML+='<p style="font-size:18px;font-weight:700;color:#f0883e">'+latestMonthly.date+'</p><a href="/report/monthly-'+latestMonthly.date+'.md" class="btn btn-sm" style="margin-top:8px">'+T("read_monthly")+'</a>';
  }}else{{heroHTML+='<p style="color:var(--text-muted);font-size:13px">'+T("not_generated_yet")+'</p>'}}
  heroHTML+='</div></div>';
  document.getElementById("reports-hero").innerHTML=heroHTML;

  // Articles Card
  const sc=(s)=>articles.filter(a=>a.score===s).length;
  const top5=articles.filter(a=>a.score>=5).slice(0,3);
  const top4=articles.filter(a=>a.score===4).slice(0,3);
  document.getElementById("daily-card").innerHTML=
    '<h2>'+T("headlines")+'</h2>'+
    ratingHelpHTML()+'<div class="stat-row">'+
    '<div class="stat"><span class="num">'+articles.length+'</span><span class="lbl">'+T("rating_3plus")+'</span></div>'+
    '<div class="stat"><span class="num">'+sc(5)+'</span><span class="lbl">★5</span></div>'+
    '<div class="stat"><span class="num">'+sc(4)+'</span><span class="lbl">★4</span></div>'+
    '<div class="stat"><span class="num">'+sc(3)+'</span><span class="lbl">★3</span></div></div>'+
    (top5.length?'<h3>'+T("star5_headlines")+'</h3><ol class="headlines">'+top5.map(a=>'<li>'+evidenceLabelHTML('fact')+' <a href="/article/'+encodeURIComponent(a.id)+'" style="color:var(--accent)">'+(a.title_cn||a.title)+'</a> '+sourceMetaHTML(a.source||'',String(a.published||'').slice(0,10),a.url)+' '+favBtn('news',a.id,a.title_cn||a.title,'/article/'+encodeURIComponent(a.id))+'</li>').join("")+'</ol>':'')+
    '<h3>'+T("star4_highlights")+'</h3><ol class="headlines">'+top4.map(a=>'<li>'+evidenceLabelHTML('fact')+' <a href="/article/'+encodeURIComponent(a.id)+'" style="color:var(--accent)">'+(a.title_cn||a.title)+'</a> '+sourceMetaHTML(a.source||'',String(a.published||'').slice(0,10),a.url)+' '+favBtn('news',a.id,a.title_cn||a.title,'/article/'+encodeURIComponent(a.id))+'</li>').join("")+'</ol>';

  let historyHTML='<h2>'+T("recent_reports")+'</h2>';
  if(!allReports.length){{historyHTML+='<p style="color:var(--text-muted);font-size:13px">'+T("no_reports_found")+'</p>'}}
  else{{historyHTML+=allReports.slice(0,3).map(r=>{{
    const isDaily=r.type==="daily";
    const fname=isDaily?r.date+'.md':r.type+'-'+r.date+'.md';
    return '<div class="report-entry"><span class="report-date">'+r.date+'</span><span class="report-type '+r.type+'">'+T("filter_"+r.type)+'</span>'+(isDaily?'<span class="report-stars">'+starRow(r.star5,r.star4,r.star3)+'</span>':'<span class="report-stars"></span>')+'<a href="/report/'+fname+'" class="report-link">'+T("view_report")+'</a>'+favBtn('report',fname,T("filter_"+r.type)+' '+r.date,'/report/'+fname)+(isDaily?'<span class="report-counts">'+(r.fetched||0)+'&rarr;'+(r.filtered||0)+'</span>':'')+'</div>'}}).join("")}}
  historyHTML+='<a href="/reports" class="btn btn-outline btn-sm" style="margin-top:16px">'+T("view_all_reports")+'</a>';
  document.getElementById("reports-history").innerHTML=historyHTML;

  }}catch(e){{
    showError("reports-hero",T("error_loading"),e.message);
    document.getElementById("daily-card").innerHTML="";
    document.getElementById("reports-history").innerHTML="";
  }}
}}
init();
</script>
</body>
</html>'''
