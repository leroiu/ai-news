"""
AI News - 3D 交互式知识图谱生成器

使用 Three.js + 3d-force-graph 生成 3D 力导向图。
节点按类型着色、大小按 importance，支持旋转/缩放/悬停高亮。
数据通过 /api/entities 和 /api/relationships 动态获取。
"""
import json
from pathlib import Path
from typing import Optional

from src.engine.utils import log, ensure_dir, ROOT_DIR
from src.interfaces.i18n import t, i18n_js, nav_html
from .frontend_styles import TYPE_COLORS, TYPE_ICONS, ANIMATION_CSS, RESPONSIVE_CSS, ERROR_CSS, INTELLIGENCE_CSS, SHARED_JS, THEME_VARS
from src.engine.kg_data import EDGE_STYLES


def generate_3d_html(output_dir: Optional[Path] = None, lang: str = "zh") -> Path:
    """生成 3D Knowledge Graph Explorer HTML。"""
    if output_dir is None:
        output_dir = ROOT_DIR / "reports"
    ensure_dir(output_dir)
    html = _build_html(lang)
    path = output_dir / "knowledge-graph-3d.html"
    path.write_text(html, encoding="utf-8")
    log.info(f"3D Graph Explorer: {path}")
    return path


def _build_html(lang: str = "zh") -> str:
    type_colors_js = json.dumps(TYPE_COLORS, ensure_ascii=False)
    icons_js = json.dumps(TYPE_ICONS, ensure_ascii=False)
    edge_colors_js = json.dumps({k: v["color"] for k, v in EDGE_STYLES.items()}, ensure_ascii=False)

    return f'''<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{t("platform_title", lang)} — 3D {t("graph_title", lang)}</title>
<style>
{THEME_VARS}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:var(--bg-primary,#0d1117);color:var(--text-primary,#c9d1d9);overflow:hidden;height:100vh}}
#app{{display:flex;height:100vh}}
#sidebar{{width:280px;min-width:280px;background:var(--bg-card,#161b22);border-right:1px solid var(--border,#30363d);display:flex;flex-direction:column;z-index:10}}
#sidebar-header{{padding:16px;border-bottom:1px solid var(--border,#30363d)}}
#sidebar-header h1{{font-size:16px;color:var(--accent,#58a6ff)}}
#sidebar-header p{{font-size:11px;color:var(--text-secondary,#8b949e);margin-top:2px}}
.nav{{display:flex;gap:6px;margin-top:8px;flex-wrap:wrap;align-items:center}}
.nav a{{padding:4px 10px;border-radius:5px;font-size:10px;text-decoration:none;color:var(--text-primary,#c9d1d9);background:var(--bg-elevated,#21262d);transition:background .15s;white-space:nowrap}}
.nav a:hover{{background:var(--border,#30363d)}}
.nav a.active{{background:var(--accent-subtle,#1f6feb22);color:var(--accent,#58a6ff)}}
.lang-btn{{padding:3px 10px;border:1px solid var(--border,#30363d);background:var(--bg-elevated,#21262d);color:var(--text-primary,#c9d1d9);border-radius:5px;cursor:pointer;font-size:10px;transition:background .15s}}
.lang-btn:hover{{background:var(--border,#30363d)}}
#type-list{{flex:1;overflow-y:auto;padding:10px}}
.type-group{{margin-bottom:14px}}
.type-group h3{{font-size:10px;text-transform:uppercase;letter-spacing:.5px;color:var(--text-secondary,#8b949e);margin-bottom:4px;padding:0 4px}}
.type-item{{display:flex;align-items:center;gap:6px;padding:3px 4px;cursor:pointer;border-radius:4px;font-size:11px;transition:background .12s}}
.type-item:hover{{background:var(--bg-elevated,#21262d)}}
.type-dot{{display:inline-block;width:8px;height:8px;border-radius:50%;flex-shrink:0}}
.type-count{{margin-left:auto;color:var(--text-muted,#484f58);font-size:9px}}
#detail-panel{{padding:14px;border-top:1px solid var(--border,#30363d);min-height:120px;max-height:280px;overflow-y:auto;font-size:12px}}
#detail-panel h2{{font-size:14px;color:var(--accent,#58a6ff);margin-bottom:4px}}
#detail-panel .meta{{color:var(--text-secondary,#8b949e);font-size:10px;margin-bottom:6px}}
#detail-panel .summary{{font-size:11px;line-height:1.6;color:var(--text-primary,#c9d1d9)}}
#graph-container{{flex:1;min-width:0;min-height:0;position:relative;cursor:grab;overflow:hidden}}
#graph-container:active{{cursor:grabbing}}
#controls{{position:absolute;bottom:16px;right:16px;display:flex;flex-direction:column;gap:8px;z-index:5}}
#controls button{{width:36px;height:36px;border:1px solid var(--border,#30363d);background:var(--bg-card,#161b22);color:var(--text-primary,#c9d1d9);border-radius:var(--radius-sm,6px);cursor:pointer;font-size:16px;display:flex;align-items:center;justify-content:center;transition:all .15s}}
#controls button:hover{{background:var(--bg-elevated,#21262d);border-color:var(--accent,#58a6ff)}}
#hint{{position:absolute;top:16px;left:50%;transform:translateX(-50%);font-size:11px;color:var(--text-muted,#484f58);pointer-events:none;transition:opacity .5s}}
.spinner{{text-align:center;padding:80px 20px;color:var(--text-secondary,#8b949e);position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);z-index:2}}
.loading{{display:inline-block;width:28px;height:28px;border:3px solid var(--border,#30363d);border-top-color:var(--accent,#58a6ff);border-radius:50%;animation:spin .6s linear infinite}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
{ANIMATION_CSS}
{RESPONSIVE_CSS}
{ERROR_CSS}
{INTELLIGENCE_CSS}
@media(max-width:768px){{#sidebar{{width:220px;min-width:220px}}}}
@media(max-width:480px){{#app{{flex-direction:column}}#sidebar{{width:100%;min-width:0;max-height:40vh}}#graph-container{{flex:1}}}}
</style>
</head>
<body data-page-template="collection">
<div id="app">
  <div id="sidebar">
    <div id="sidebar-header">
      <h1>3D {t("graph_title", lang)}</h1>
      <p id="stats-line">{t("loading", lang)}</p>
      <details class="intel-rating-help"><summary data-i18n="editorial_rating_label">{t("editorial_rating_label", lang)}</summary><p data-i18n="editorial_rating_help">{t("editorial_rating_help", lang)}</p></details>
      {nav_html("graph")}
    </div>
    <div id="type-list"></div>
    <div id="detail-panel">
      <p style="color:var(--text-secondary,#8b949e)">{t("select_node_hint", lang)}</p>
    </div>
  </div>
  <div id="graph-container">
    <div class="spinner" id="loader"><div><div class="loading"></div><p style="margin-top:12px">{t("loading", lang)}</p></div></div>
    <div id="hint">🖱 拖拽旋转 · 滚轮缩放 · 右键平移 · 点击节点查看详情</div>
    <div id="controls">
      <button onclick="resetCamera()" title="重置视角">🏠</button>
      <button onclick="cycleView()" title="切换视图">🔄</button>
      <a href="/graph" style="text-decoration:none"><button title="2D 视图">2D</button></a>
    </div>
  </div>
</div>
<script src="https://unpkg.com/three@0.160.0/build/three.min.js"></script>
<script src="https://unpkg.com/3d-force-graph@1.73.5/dist/3d-force-graph.min.js"></script>
<script>
{SHARED_JS}
{i18n_js()}
const TC={type_colors_js}, ICONS={icons_js}, EC={edge_colors_js};
let graph, nodes=[], links=[], highlightNodes=new Set(), highlightLinks=new Set();
let currentView=0;
const views=[
  {{pos:[0,0,300],look:[0,0,0]}},
  {{pos:[0,300,50],look:[0,0,0]}},
  {{pos:[300,150,0],look:[0,0,0]}},
];

function resetCamera(){{graph.cameraPosition(...views[0].pos, ...views[0].look);currentView=0}}
function cycleView(){{currentView=(currentView+1)%views.length;const v=views[currentView];graph.cameraPosition(...v.pos, ...v.look)}}

function renderTypeList(){{
  const counts={{}};nodes.forEach(n=>{{const t=n.type||'unknown';counts[t]=(counts[t]||0)+1}});
  const items=Object.entries(counts).sort((a,b)=>b[1]-a[1]).map(([t,c])=>
    '<div class="type-item" onclick="filterByType(\\''+t+'\\')"><span class="type-dot" style="background:'+(TC[t]||'#999')+'"></span>'+t+'<span class="type-count">'+c+'</span></div>').join('');
  document.getElementById("type-list").innerHTML='<div class="type-group"><h3>'+T("type_filter")+' ('+nodes.length+')</h3>'+items+'</div>';
}}

let typeFilter=null;
function filterByType(t){{typeFilter=typeFilter===t?null:t;refreshGraph()}}
function refreshGraph(){{
  const filtered=typeFilter?nodes.filter(n=>(n.type||'unknown')===typeFilter):nodes;
  const nIds=new Set(filtered.map(n=>n.id));
  const visibleLinks=links.filter(l=>nIds.has((l.source&&l.source.id||l.source))&&nIds.has((l.target&&l.target.id||l.target)));
  graph.graphData({{nodes:filtered,links:visibleLinks}});
  renderTypeList();
}}

async function init(){{
  applyI18n();
  try{{
    const [entData,relData]=await Promise.all([apiFetch("/api/entities"),apiFetch("/api/relationships")]);
    nodes=(entData||[]).map(e=>({{...e,val:(e.importance||1)*2,color:TC[e.type]||'#999',desc:(e.summary||'').slice(0,200)}}));
    links=(relData||[]).map(r=>({{source:r.source_id,target:r.target_id,type:r.relation_type||'related',color:EC[r.relation_type]||'#999'}}));
    const loader=document.getElementById("loader");if(loader)loader.style.display="none";
    document.getElementById("stats-line").textContent=T("graph_stats", {{n: nodes.length, e: links.length}});
    buildGraph();
    renderTypeList();
    setTimeout(()=>document.getElementById("hint").style.opacity="0",8000);
  }}catch(e){{showError("graph-container",T("error_loading"),e.message)}}
}}

function buildGraph(){{
  const container=document.getElementById("graph-container");
  graph=ForceGraph3D()(container)
    .width(container.clientWidth)
    .height(container.clientHeight)
    .graphData({{nodes,links}})
    .nodeColor(n=>n.color||'#999')
    .nodeVal(n=>n.val||2)
    .nodeLabel(n=>'<b>'+ICONS[n.type]+' '+n.name+'</b><br>'+editorialRatingHTML(n.importance||0))
    .linkColor(l=>l.color||'#444')
    .linkWidth(l=>highlightLinks.has(l)?3:0.5)
    .linkOpacity(0.4)
    .linkDirectionalParticles(2)
    .linkDirectionalParticleWidth(l=>highlightLinks.has(l)?2:0)
    .backgroundColor('#0d1117')
    .onNodeClick(node=>{{
      const panel=document.getElementById("detail-panel");
      panel.innerHTML='<h2>'+ICONS[node.type]+' '+node.name+'</h2>'+
        '<div class="meta">'+topicTagHTML(TLbl(node.type))+' '+editorialRatingHTML(node.importance||0)+'</div>'+
        '<div class="summary">'+(node.summary||node.desc||T("no_data"))+'</div>'+
        '<a href="/entity/'+encodeURIComponent(node.id)+'" style="color:var(--accent,#58a6ff);font-size:11px;margin-top:8px;display:inline-block">'+T("view_detail")+'</a>';
      highlightNodes.clear();highlightLinks.clear();
      highlightNodes.add(node);
      links.forEach(l=>{{if(l.source.id===node.id||l.target.id===node.id)highlightLinks.add(l)}});
      updateHighlight();
    }})
    .onNodeHover(node=>{{if(!node&&!highlightNodes.size){{highlightNodes.clear();highlightLinks.clear();updateHighlight()}}}})
    .onBackgroundClick(()=>{{highlightNodes.clear();highlightLinks.clear();updateHighlight();document.getElementById("detail-panel").innerHTML='<p style="color:var(--text-secondary,#8b949e)">'+T("select_node_hint")+'</p>'}})
    .onEngineStop(()=>{{if(!graph)return;graph.zoomToFit(400,60)}});
  new ResizeObserver(()=>{{
    if(graph) graph.width(container.clientWidth).height(container.clientHeight);
  }}).observe(container);
}}

function updateHighlight(){{
  graph.nodeColor(n=>highlightNodes.has(n)?n.color||'#999':highlightNodes.size?'#444':n.color||'#999');
  graph.linkColor(l=>highlightLinks.has(l)?l.color||'#58a6ff':highlightNodes.size?'#222':l.color||'#444');
  graph.linkWidth(l=>highlightLinks.has(l)?3:0.5);
  graph.linkDirectionalParticles(highlightNodes.size?0:2);
  graph.linkDirectionalParticleWidth(l=>highlightLinks.has(l)?2:0);
}}

init();
</script>
</body></html>'''
