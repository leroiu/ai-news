"""AI News - Reports 页面生成器。"""
import json
from pathlib import Path
from typing import Optional

from .frontend_styles import (
    RESET_CSS, NAV_CSS, SPINNER_CSS, SKELETON_CSS, BUTTON_CSS,
    ANIMATION_CSS, RESPONSIVE_CSS, ERROR_CSS, INTELLIGENCE_CSS,
    ACTION_COMPONENT_CSS, ACCESSIBILITY_CSS, SHARED_JS, TYPE_COLORS,
)
from src.interfaces.i18n import t, i18n_js, nav_html
from src.engine.utils import ROOT_DIR, ensure_dir, log


def generate_reports_page(output_dir: Optional[Path] = None, lang: str = "zh") -> Path:
    output_dir = output_dir or ROOT_DIR / "reports"
    ensure_dir(output_dir)
    # HTML 保存在 reports 目录，但由 FastAPI route 直接返回
    # （不与 StaticFiles mount 路径冲突——build 到 reports 目录下）
    path = output_dir / "reports.html"
    path.write_text(_build_html(lang), encoding="utf-8")
    log.info("Reports page (%s): %s", lang, path)
    return path


def _build_html(lang: str = "zh") -> str:
    return f'''<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{t("reports_title", lang)} — {t("platform_title", lang)}</title>
<style>
{RESET_CSS}
body{{padding:24px;max-width:var(--content-max);margin:0 auto;animation:fadeIn .2s ease-out}}
{NAV_CSS}
{SPINNER_CSS}
{BUTTON_CSS}
h1{{font-family:var(--font-display);font-size:38px;letter-spacing:-.035em;color:var(--text-primary);margin:26px 0 8px}}
.subtitle{{color:var(--text-secondary);font-size:13px;margin-bottom:20px}}
.section{{margin:36px 0 42px}}
.section h2{{font-family:var(--font-display);font-size:21px;color:var(--text-primary);margin-bottom:0;padding-bottom:10px;border-bottom:1px solid var(--border-strong)}}
.section h3{{font-size:13px;color:var(--text-secondary);margin-bottom:6px;font-weight:600}}
.report-list{{display:flex;flex-direction:column}}
.report-item{{display:flex;align-items:center;gap:12px;padding:14px 0;background:transparent;border:0;border-bottom:1px solid var(--border);border-radius:0;text-decoration:none;color:var(--text-primary);transition:all .15s}}
.report-item:hover{{padding-left:8px;background:var(--accent-subtle)}}
.report-main{{display:flex;align-items:center;gap:12px;flex:1;color:inherit;text-decoration:none;min-width:0}}
.report-item .icon{{font-size:16px;flex-shrink:0}}
.report-item .label{{font-size:14px;font-weight:500}}
.report-item .meta{{margin-left:auto;font-size:11px;color:var(--text-muted);white-space:nowrap}}
.report-item .arrow{{color:var(--text-muted);font-size:12px}}
.empty{{text-align:center;padding:32px;color:var(--text-muted);font-size:13px}}
.badge{{display:inline-block;padding:1px 8px;border-radius:10px;font-size:10px;font-weight:600;letter-spacing:.04em}}
.badge-daily{{background:#1f6feb22;color:var(--accent)}}
.badge-weekly{{background:#3fb95022;color:var(--success)}}
.badge-monthly{{background:#e3b34122;color:var(--warning)}}
#stats-grid{{display:grid;grid-template-columns:repeat(3,1fr)!important;gap:0;margin:26px 0 8px;border-top:1px solid var(--border-strong);border-bottom:1px solid var(--border)}}
.stat-card{{padding:18px 12px;background:transparent;border:0;border-right:1px solid var(--border);border-radius:0;text-align:left}}
.stat-card:last-child{{border-right:0}}
.stat-card .num{{font-size:32px;font-weight:700;color:var(--accent)}}
.stat-card .label{{font-size:11px;color:var(--text-secondary);margin-top:4px}}
@media(max-width:480px){{body{{padding:16px 12px}}h1{{font-size:32px}}.stat-card{{padding:14px 8px}}.stat-card .num{{font-size:26px}}.report-item{{padding:12px 0}}}}
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
{nav_html("reports")}
<main id="main-content">
<h1 data-i18n="reports_title">{t("reports_title", lang)}</h1>
<p class="subtitle" data-i18n="reports_subtitle">{t("reports_subtitle", lang)}</p>
<details class="intel-rating-help"><summary data-i18n="editorial_rating_label">{t("editorial_rating_label", lang)}</summary><p data-i18n="editorial_rating_help">{t("editorial_rating_help", lang)}</p></details>

<div class="grid" id="stats-grid"><div class="spinner"><div class="loading"></div></div></div>

<section class="section">
  <h2 data-i18n="reports_weekly">📊 {t("reports_weekly", lang)}</h2>
  <div class="report-list" id="weekly-list"><div class="spinner"><div class="loading"></div></div></div>
</section>
</main>

<section class="section">
  <h2 data-i18n="reports_monthly">📈 {t("reports_monthly", lang)}</h2>
  <div class="report-list" id="monthly-list"><div class="spinner"><div class="loading"></div></div></div>
</section>

<section class="section">
  <h2 data-i18n="reports_daily">📆 {t("reports_daily", lang)}</h2>
  <div class="report-list" id="daily-list"><div class="spinner"><div class="loading"></div></div></div>
</section>

<script>
{SHARED_JS}
{i18n_js()}

function reportItem(r) {{
  var date = r.date || "", label = date;
  var icon = r.report_type === "daily" ? "D" : r.report_type === "weekly" ? "W" : "M";
  var badgeType = r.report_type === "daily" ? "badge-daily" : r.report_type === "weekly" ? "badge-weekly" : "badge-monthly";
  var path = r.path || "";
  var filename = path.split("/").pop() || path.split("\\\\").pop() || path;
  if (!filename) filename = date + ".md";
  var stars = r.star5 ? " ★5:"+r.star5 : "";
  var fetched = r.fetched ? " " + r.fetched + "篇" : "";
  return '<div class="report-item card-hover">' +
    '<a class="report-main" href="/report/'+encodeURIComponent(filename)+'">' +
    '<span class="icon">'+icon+'</span>' +
    '<span class="label">'+label+'</span>' +
    '<span class="badge '+badgeType+'">'+T('filter_'+r.report_type)+'</span>' +
    '<span class="meta">'+fetched+stars+'</span>' +
    '<span class="arrow">→</span></a>' +
    favoriteButtonHTML('report', filename, label, '', '/report/'+encodeURIComponent(filename)) +
    '</div>';
}}

function statCard(num, label) {{
  return '<div class="stat-card anim-fade"><div class="num">'+num+'</div><div class="label">'+label+'</div></div>';
}}

async function init() {{
  applyI18n();
  document.title = T("reports_title") + " — " + T("platform_title");

  try {{
    const [daily, weekly, monthly] = await Promise.all([
      apiFetch("/api/reports?type=daily&limit=30"),
      apiFetch("/api/reports?type=weekly&limit=12"),
      apiFetch("/api/reports?type=monthly&limit=12"),
    ]);

    document.getElementById("stats-grid").innerHTML =
      statCard(daily.length, T("reports_daily")) +
      statCard(weekly.length, T("reports_weekly")) +
      statCard(monthly.length, T("reports_monthly"));

    function render(containerId, data) {{
      var el = document.getElementById(containerId);
      if (!data.length) {{
        el.innerHTML = '<div class="empty">'+T("no_data")+'</div>';
        return;
      }}
      el.innerHTML = data.map(reportItem).join("");
    }}

    render("daily-list", daily);
    render("weekly-list", weekly);
    render("monthly-list", monthly);
  }} catch(e) {{
    showError("daily-list", T("error_loading"), e.message);
  }}
}}

init();
</script>
</body></html>'''
