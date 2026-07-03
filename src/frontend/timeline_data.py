"""
AI Intelligence Platform — Timeline 常量与模板

TYPE_COLORS、TYPE_ICONS、CSS_TEMPLATE、JS_TEMPLATE。
模板中的 __C_JSON__ / __I_JSON__ 占位符由 timeline_renderer 替换。
使用共享设计系统 (frontend_styles.py) 消除重复。
"""
import json
from .frontend_styles import TYPE_COLORS, TYPE_ICONS, ANIMATION_CSS, RESPONSIVE_CSS, ERROR_CSS, INTELLIGENCE_CSS, SHARED_JS, THEME_VARS

C_JSON = json.dumps(TYPE_COLORS)
I_JSON = json.dumps(TYPE_ICONS)

# ── CSS 模板（原 f-string，已将 {{ → {, }} → }） ──

CSS_TEMPLATE = """\
<style>
""" + THEME_VARS + """
""" + INTELLIGENCE_CSS + """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:var(--bg-primary);color:var(--text-primary);padding:24px 0 0 0;overflow-x:hidden}
.top-bar{padding:0 24px;max-width:100%}
.related-views{display:flex;gap:8px;margin:-8px 24px 20px;padding-bottom:14px;border-bottom:1px solid var(--border)}
.related-views a{padding:5px 10px;border-radius:999px;color:var(--text-secondary);font-size:11px;text-decoration:none}
.related-views a:hover,.related-views a.active{background:var(--accent-subtle);color:var(--accent)}
h1{font-size:22px;color:var(--accent);margin-bottom:4px}
.date{font-size:12px;color:var(--text-secondary);margin-bottom:16px}
.nav{display:flex;gap:12px;margin-bottom:12px;flex-wrap:wrap;align-items:center}
.nav a{padding:6px 14px;border-radius:6px;font-size:13px;text-decoration:none;color:var(--text-primary);background:var(--bg-elevated);transition:background .15s}
.nav a:hover{background:#30363d}
.nav a.active{background:var(--accent-subtle);color:#58a6ff}
.lang-btn{padding:4px 12px;border:1px solid var(--border);background:var(--bg-elevated);color:var(--text-primary);border-radius:6px;cursor:pointer;font-size:12px;margin-left:auto;transition:background .15s}
.lang-btn+.lang-btn{margin-left:0}
.lang-btn:hover{background:#30363d}

/* ── 控制栏 ── */
.controls{display:flex;align-items:center;gap:12px;margin-bottom:12px;flex-wrap:wrap;padding:0 24px}
.filters{display:flex;gap:6px;flex-wrap:wrap}
.filter-btn{padding:4px 12px;border-radius:12px;font-size:11px;cursor:pointer;border:1px solid var(--border);background:var(--bg-card);color:var(--text-secondary);transition:all .15s;white-space:nowrap}
.filter-btn:hover{border-color:var(--accent);color:#c9d1d9}
.filter-btn.active{background:#1f6feb33;border-color:var(--accent);color:#58a6ff}
.filter-btn.hidden{opacity:0.25}

/* ── 年份滑块 ── */
.year-slider-wrap{display:flex;align-items:center;gap:8px;margin-left:auto;flex-shrink:0}
.year-slider-wrap label{font-size:11px;color:var(--text-secondary);white-space:nowrap}
.year-slider{-webkit-appearance:none;width:200px;height:4px;background:var(--bg-elevated);border-radius:2px;outline:none}
.year-slider::-webkit-slider-thumb{-webkit-appearance:none;width:14px;height:14px;background:#58a6ff;border-radius:50%;cursor:pointer}
.year-range{font-size:11px;color:var(--accent);min-width:60px;text-align:right;cursor:pointer}

/* ── 统计条 ── */
.stats-bar{display:flex;gap:16px;padding:4px 24px;font-size:10px;color:var(--text-muted);margin-bottom:8px;flex-wrap:wrap}
.stats-bar span{white-space:nowrap}

/* ── 横向时间线容器 ── */
.timeline-scroll{position:relative;overflow-x:auto;overflow-y:hidden;cursor:grab;padding:0 24px;-webkit-overflow-scrolling:touch;scroll-behavior:smooth}
.timeline-scroll:active{cursor:grabbing}
.timeline-scroll::-webkit-scrollbar{height:6px}
.timeline-scroll::-webkit-scrollbar-track{background:#161b22}
.timeline-scroll::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
.timeline-scroll::-webkit-scrollbar-thumb:hover{background:#484f58}
.timeline-inner{display:flex;flex-direction:column;min-width:max-content;padding-bottom:8px}
.tl-year-row{display:flex;align-items:stretch;margin-bottom:4px}
.tl-year-label{flex-shrink:0;width:56px;display:flex;align-items:flex-start;justify-content:flex-end;padding-right:12px;font-size:20px;font-weight:700;color:var(--text-primary);position:sticky;left:0;background:linear-gradient(to left,transparent 0,#0d1117 12px);z-index:2;padding-top:8px}
.tl-year-cards{display:flex;gap:8px;padding:8px 0 4px 0}
.tl-card{flex-shrink:0;width:260px;background:var(--bg-card);border:1px solid var(--border);border-radius:10px;padding:14px;transition:all .2s;cursor:pointer;position:relative}
.tl-card:hover{border-color:#58a6ff66;transform:translateY(-2px);box-shadow:0 4px 12px #00000033}
.tl-card.expanded{width:420px;border-color:var(--accent);z-index:3;box-shadow:0 8px 24px #00000055}
.tl-card .card-type{display:inline-flex;align-items:center;gap:3px;padding:1px 8px;border-radius:8px;font-size:9px;color:#fff;margin-bottom:6px}
.tl-card .card-name{font-size:13px;font-weight:600;color:var(--accent);margin-bottom:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tl-card .card-date{font-size:10px;color:var(--text-secondary);margin-bottom:6px}
.tl-card .card-summary{font-size:11px;color:var(--text-secondary);line-height:1.4;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden}
.tl-card .card-detail{display:none;margin-top:8px;padding-top:8px;border-top:1px solid #21262d;font-size:11px;color:var(--text-secondary);line-height:1.5}
.tl-card.expanded .card-detail{display:block}
.tl-card.expanded .card-summary{-webkit-line-clamp:unset}
.tl-card .card-tags{display:flex;gap:3px;flex-wrap:wrap;margin-top:8px}
.tl-card .card-tags .tag{font-size:8px;padding:1px 6px;background:var(--bg-elevated);border-radius:3px;color:#6e7681}
.tl-card .card-stars{position:absolute;top:8px;right:10px;font-size:9px;color:#d2991d}
.tl-card .card-link{display:inline-block;margin-top:6px;font-size:10px;color:var(--accent);text-decoration:none}
.tl-card .card-link:hover{text-decoration:underline}
.favorite-btn{display:inline-block;margin-top:7px;padding:2px 7px;border:1px solid var(--border);background:var(--bg-elevated);color:var(--text-secondary);border-radius:999px;cursor:pointer;font-size:10px;line-height:1.4}.favorite-btn:hover,.favorite-btn.is-favorited,.favorite-btn[aria-pressed="true"]{border-color:var(--warning);background:#e3b34122;color:var(--warning)}
.tl-card .card-timeline{margin-top:6px;font-size:10px;color:var(--text-muted);line-height:1.6}
.tl-card .card-timeline .tl-event-date{color:#6e7681;font-family:monospace;margin-right:4px}
.timeline-empty{text-align:center;padding:60px 24px;color:var(--text-muted);font-size:14px}

@media (max-width:768px){
  .controls{flex-direction:column;align-items:flex-start}
  .year-slider-wrap{width:100%;max-width:100%;margin-left:0}
  .year-slider{width:min(200px,calc(100vw - 150px))}
  .year-range{min-width:40px}
  .intel-rating-help{margin-left:24px;margin-right:24px;max-width:calc(100vw - 48px)}
  .card-stars .intel-rating__label{display:none}
  .tl-card{width:220px}
  .tl-card.expanded{width:320px}
}
</style>"""
CSS_TEMPLATE = CSS_TEMPLATE.replace("</style>", ANIMATION_CSS + RESPONSIVE_CSS + ERROR_CSS + "</style>", 1)

# ── JS 模板（原 f-string，已将 {{ → {, }} → }, {C_JSON} → __C_JSON__, {I_JSON} → __I_JSON__） ──

JS_TEMPLATE = """\
""" + "<script>" + SHARED_JS + "</script>" + """
<script>
const C = __C_JSON__;
const I = __I_JSON__;
let allEntities = [];
let activeFilter = "all";
let activeYear = null;

async function init() {
  try {
  const entities = await apiFetch("/api/entities");
  allEntities = entities.filter(e => e.release_date || (e.timeline && e.timeline.length));
  document.getElementById("date-line").textContent = new Date().toISOString().slice(0,10)
    + " · " + T("entities_count", {n: allEntities.length});

  const years = new Set();
  allEntities.forEach(e => {
    const y = getYear(e);
    if (y) years.add(parseInt(y));
  });
  const yearList = [...years].sort();
  if (yearList.length) {
    const slider = document.getElementById("year-slider");
    slider.min = yearList[0];
    slider.max = yearList[yearList.length - 1];
    slider.value = yearList[yearList.length - 1];
    document.getElementById("year-range").textContent = T("all_label");
  }

  renderBarChart(allEntities);
  renderTimeline(allEntities);

  document.querySelectorAll(".filter-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      activeFilter = btn.dataset.type;
      applyFilters();
    });
  });

  // Update filter button labels for i18n
  document.querySelectorAll(".filter-btn[data-type]").forEach(function(btn) {
    var t = btn.dataset.type;
    if (t === "all") {
      btn.textContent = T("all_label");
    } else {
      btn.textContent = (I[t]||"") + " " + TLbl(t);
    }
  });

  document.getElementById("year-slider").addEventListener("input", (e) => {
    activeYear = parseInt(e.target.value);
    document.getElementById("year-range").textContent = activeYear;
    applyFilters();
  });

  document.getElementById("year-range").addEventListener("click", () => {
    activeYear = null;
    const slider = document.getElementById("year-slider");
    slider.value = slider.max;
    document.getElementById("year-range").textContent = T("all_label");
    applyFilters();
  });
  } catch(e) { showError("timeline-inner", T("error_loading"), e.message); }
}

function getTimelineDate(entity) {
  const raw = entity.release_date || (entity.timeline && entity.timeline[0] && entity.timeline[0].date);
  return raw === null || raw === undefined || raw === "" ? "" : String(raw);
}

function getYear(entity) {
  const date = getTimelineDate(entity);
  return date ? date.slice(0, 4) : null;
}

function applyFilters() {
  let filtered = allEntities;
  if (activeFilter !== "all") {
    filtered = filtered.filter(e => e.type === activeFilter);
  }
  if (activeYear) {
    filtered = filtered.filter(e => {
      const y = getYear(e);
      return y && parseInt(y) === activeYear;
    });
  }
  renderBarChart(filtered);
  renderTimeline(filtered);
}

function renderBarChart(entities) {
  const byYear = {};
  let minY = Infinity, maxY = -Infinity;
  entities.forEach(e => {
    const date = getTimelineDate(e);
    if (!date) return;
    const year = parseInt(String(date).slice(0, 4));
    byYear[year] = (byYear[year] || 0) + 1;
    if (year < minY) minY = year;
    if (year > maxY) maxY = year;
  });
  const years = Object.keys(byYear).sort();
  const total = entities.length;
  const typeCounts = {};
  entities.forEach(e => { typeCounts[e.type] = (typeCounts[e.type] || 0) + 1; });

  document.getElementById("stats-bar").innerHTML = `
    <span>${T("total_label")}: <b>${total}</b></span>
    <span>${T("years_label")}: <b>${years.length}</b></span>
    <span>${T("range_label")}: <b>${minY === Infinity ? "—" : minY + "–" + maxY}</b></span>
    ${Object.entries(typeCounts).map(([t,c]) => `<span style="color:${C[t]||"#999"}">${I[t]||""} ${c}</span>`).join(" ")}
  `;
}

function renderTimeline(entities) {
  const container = document.getElementById("timeline-inner");
  const sorted = [...entities].sort((a, b) => {
    const da = getTimelineDate(a) || "9999";
    const db = getTimelineDate(b) || "9999";
    return da.localeCompare(db);
  });

  if (!sorted.length) {
    container.innerHTML = '<div class="timeline-empty">' + T("no_timeline_data") + '</div>';
    return;
  }

  const grouped = {};
  sorted.forEach(e => {
    const y = getYear(e) || "—";
    if (!grouped[y]) grouped[y] = [];
    grouped[y].push(e);
  });

  let html = "";
  Object.keys(grouped).sort().forEach(year => {
    const cards = grouped[year];
    html += '<div class="tl-year-row"><div class="tl-year-label">' + year + '</div><div class="tl-year-cards">';
    cards.forEach(e => {
      const date = getTimelineDate(e);
      const color = e.color || C[e.type] || "#999";
      const icon = I[e.type] || "📌";
      const timelineEvents = (e.timeline || []).map(function(t) { return '<div><span class="tl-event-date">' + (t.date == null ? "" : String(t.date)) + '</span>' + (t.event||"") + '</div>'; }).join("");
      const typeName = TLbl(e.type);

      html += '<div class="tl-card" data-id="' + e.id + '" onclick="toggleCard(this, event)">' +
        '<div class="card-stars">' + editorialRatingHTML(e.importance||0) + '</div>' +
        '<div class="card-type" style="background:' + color + '22;color:' + color + '">' + icon + ' ' + typeName + '</div>' +
        '<div class="card-name" title="' + e.name + '">' + e.name + '</div>' +
        '<div class="card-date">' + (date || T("no_date")) + '</div>' +
        (e.summary ? '<div class="card-summary">' + evidenceLabelHTML('fact') + ' ' + e.summary.slice(0, 300) + '</div>' : '') +
        '<div class="card-detail">' +
          (e.significance ? '<p style="margin-bottom:6px;color:#c9d1d9">' + e.significance.slice(0, 400) + '</p>' : '') +
          (e.background ? '<p style="margin-bottom:6px">' + e.background.slice(0, 300) + '</p>' : '') +
          (timelineEvents ? '<div class="card-timeline">' + timelineEvents + '</div>' : '') +
          ((e.tags || []).length ? '<div class="card-tags">' + e.tags.slice(0,8).map(function(t) { return '<span class="tag">' + t + '</span>'; }).join("") + '</div>' : '') +
          '<a class="card-link" href="/entity/' + e.id + '" onclick="event.stopPropagation()">' + T("view_detail") + ' →</a>' +
          favoriteButtonHTML('timeline', e.id, e.name, '', '/entity/'+e.id) +
        '</div>' +
      '</div>';
    });
    html += '</div></div>';
  });

  container.innerHTML = html;
}

function toggleCard(card, event) {
  if (event.target.tagName === "A") return;
  const wasExpanded = card.classList.contains("expanded");
  document.querySelectorAll(".tl-card.expanded").forEach(function(c) { c.classList.remove("expanded"); });
  if (!wasExpanded) {
    card.classList.add("expanded");
    card.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
  }
}

(function() {
  const scroll = document.getElementById("timeline-scroll");
  let isDown = false, startX, scrollLeft;
  scroll.addEventListener("mousedown", function(e) {
    if (e.target.closest(".tl-card")) return;
    isDown = true;
    startX = e.pageX - scroll.offsetLeft;
    scrollLeft = scroll.scrollLeft;
    scroll.style.cursor = "grabbing";
  });
  scroll.addEventListener("mouseleave", function() { isDown = false; scroll.style.cursor = "grab"; });
  scroll.addEventListener("mouseup", function() { isDown = false; scroll.style.cursor = "grab"; });
  scroll.addEventListener("mousemove", function(e) {
    if (!isDown) return;
    e.preventDefault();
    const x = e.pageX - scroll.offsetLeft;
    scroll.scrollLeft = scrollLeft - (x - startX);
  });
})();

init();
</script>"""
