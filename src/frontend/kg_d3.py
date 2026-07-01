"""
AI News - D3.js 交互式知识图谱 HTML 生成器

生成自包含的 HTML 页面，内嵌 D3.js 力导向图。
页面在运行时通过 /api/entities 和 /api/relationships 获取数据。
使用共享设计系统 (frontend_styles.py)。
"""
import json
from pathlib import Path
from typing import Optional

from src.engine.utils import log, ensure_dir, ROOT_DIR
from src.interfaces.i18n import t, i18n_js, nav_html
from src.engine.kg_data import TYPE_COLORS, EDGE_STYLES
from .frontend_styles import ANIMATION_CSS, RESPONSIVE_CSS, ERROR_CSS, SHARED_JS, THEME_VARS


def generate_html(graph: dict = None, output_dir: Optional[Path] = None, lang: str = "zh") -> Path:
    """生成 Graph Explorer — API-driven 交互式知识图谱 HTML (i18n)。"""
    if output_dir is None:
        output_dir = ROOT_DIR / "reports"
    ensure_dir(output_dir)

    stats = graph["stats"] if graph else {"total_nodes": 0, "total_edges": 0, "components": 0}

    type_colors_js = json.dumps(TYPE_COLORS, ensure_ascii=False)
    edge_colors_js = json.dumps({k: v["color"] for k, v in EDGE_STYLES.items()}, ensure_ascii=False)

    html = f'''<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{t("platform_title", lang)} — {t("graph_title", lang)}</title>
<style>
{THEME_VARS}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:var(--bg-primary);color:var(--text-primary);overflow:hidden;height:100vh}}
#app{{display:flex;height:100vh}}
#sidebar{{width:280px;min-width:280px;background:var(--bg-card);border-right:1px solid var(--border);display:flex;flex-direction:column}}
#sidebar-header{{padding:16px;border-bottom:1px solid var(--border)}}
#sidebar-header h1{{font-size:16px;color:var(--accent)}}
#sidebar-header p{{font-size:11px;color:var(--text-secondary);margin-top:2px}}
.nav{{display:flex;gap:8px;margin-top:8px;flex-wrap:wrap;align-items:center}}
.nav a{{padding:4px 10px;border-radius:5px;font-size:10px;text-decoration:none;color:var(--text-primary);background:var(--bg-elevated);transition:background .15s}}
.nav a:hover{{background:var(--border)}}
.nav a.active{{background:var(--accent-subtle);color:var(--accent)}}
.lang-btn{{padding:3px 10px;border:1px solid var(--border);background:var(--bg-elevated);color:var(--text-primary);border-radius:5px;cursor:pointer;font-size:10px;margin-left:auto;transition:background .15s}}
.lang-btn:hover{{background:var(--border)}}
#type-list{{flex:1;overflow-y:auto;padding:10px}}
.type-group{{margin-bottom:14px}}
.type-group h3{{font-size:10px;text-transform:uppercase;letter-spacing:.5px;color:var(--text-secondary);margin-bottom:4px;padding:0 4px}}
.entity-item{{display:flex;align-items:center;gap:8px;padding:5px 8px;cursor:pointer;border-radius:4px;font-size:12px;transition:background .12s}}
.entity-item:hover{{background:var(--bg-elevated)}}
.entity-item .dot{{width:6px;height:6px;border-radius:50%;flex-shrink:0}}
.entity-item .stars{{font-size:9px;margin-left:auto;color:#d2991d;flex-shrink:0}}
#detail-pane{{width:300px;min-width:300px;background:var(--bg-card);border-left:1px solid var(--border);display:flex;flex-direction:column;transition:all .3s;overflow:hidden}}
#detail-pane.hidden{{width:0;min-width:0}}
#detail-header{{padding:16px;border-bottom:1px solid var(--border)}}
#detail-header h2{{font-size:15px}}
.badge{{display:inline-block;padding:2px 10px;border-radius:10px;font-size:10px;color:#fff;margin:4px 0}}
#detail-body{{flex:1;overflow-y:auto;padding:16px;font-size:12px;line-height:1.5}}
#detail-body h3{{font-size:11px;color:var(--text-secondary);text-transform:uppercase;margin:14px 0 6px}}
.rel-item{{display:inline-block;padding:2px 8px;margin:2px;background:var(--bg-elevated);border-radius:4px;font-size:11px;cursor:pointer;color:var(--text-primary)}}
.rel-item:hover{{background:var(--border)}}
.tl-item{{padding:3px 0 3px 10px;border-left:2px solid var(--border);font-size:11px;margin:2px 0}}
.tl-date{{color:var(--text-secondary);font-size:10px}}
#graph-area{{flex:1;position:relative}}
#legend{{position:absolute;bottom:10px;right:12px;display:flex;gap:8px;flex-wrap:wrap;max-width:260px}}
.leg{{display:flex;align-items:center;gap:4px;font-size:10px;color:var(--text-secondary)}}
.leg-dot{{width:7px;height:7px;border-radius:50%}}
#timeline-bar{{height:44px;background:var(--bg-card);border-top:1px solid var(--border);display:flex;align-items:center;padding:0 14px;gap:10px}}
#timeline-bar input[type=range]{{flex:1;accent-color:var(--accent)}}
#timeline-bar span{{font-size:10px;color:var(--text-secondary);white-space:nowrap}}
svg{{width:100%;height:100%}}
.node-enter{{animation:nodePop .4s ease-out}}
@keyframes nodePop{{from{{opacity:0;transform:scale(0)}}to{{opacity:1;transform:scale(1)}}}}
{ANIMATION_CSS}
{RESPONSIVE_CSS}
{ERROR_CSS}
/* 响应式: 窄屏侧边栏折叠 */
@media (max-width:768px){{#sidebar{{width:60px;min-width:60px}}#sidebar-header h1{{font-size:12px}}#sidebar-header p{{display:none}}#type-list{{display:none}}#detail-pane{{width:260px;min-width:260px}}}}
</style>
</head>
<body>
<div id="app">
<div id="sidebar">
<div id="sidebar-header"><h1 data-i18n="graph_title">{t("graph_title", lang)}</h1><p id="stats-line">{t("loading", lang)}</p>
{nav_html("/graph")}
<a href="/graph3d" style="display:inline-block;margin-top:6px;padding:4px 12px;background:#1f6feb22;color:#58a6ff;border:1px solid #1f6feb44;border-radius:5px;font-size:10px;text-decoration:none;text-align:center">🌐 3D 视图</a>
</div>
<div id="type-list"></div>
</div>
<div id="graph-area"><svg id="graph-svg"></svg><div id="legend"></div></div>
<div id="detail-pane" class="hidden"><div id="detail-header"></div><div id="detail-body"><div style="display:flex;align-items:center;justify-content:center;height:100%;color:#484f58;font-size:12px" id="detail-hint">{t("select_node_hint", lang)}</div></div></div>
</div>
<div id="timeline-bar">
<span style="font-weight:600" data-i18n="timeline_label">{t("timeline_label", lang)}</span><span id="tl-min">2015</span>
<input type="range" id="tl-slider" min="0" max="100" value="100"><span id="tl-max">2026</span>
<span id="tl-label" style="color:#58a6ff"></span>
</div>

<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
{SHARED_JS}
{i18n_js()}
</script>
<script>
const TYPE_COLORS = {type_colors_js};
const C={edge_colors_js};
let NODES=[],EDGES=[],nm={{}},bt={{}};

// Init after data loads
(async function(){{
try{{
const [nodes,edges]=await Promise.all([
  apiFetch("/api/entities"),
  apiFetch("/api/relationships")
]);
NODES=nodes.map(n=>({{...n,color:n.color||TYPE_COLORS[n.type]||"#999"}}));
EDGES=edges.map(e=>({{...e,color:e.color||(C[e.rel_type]||"#999"),type:e.rel_type||e.type,label:e.label||e.rel_type}}));
NODES.forEach(n=>nm[n.id]=n);
// 过滤孤立边 + 映射 source_id/target_id 为 D3 需要的 source/target
EDGES=EDGES.filter(e=>nm[e.source_id] && nm[e.target_id])
  .map(e=>({{...e,source:e.source_id,target:e.target_id}}));
NODES.forEach(n=>{{if(!bt[n.type])bt[n.type]=[];bt[n.type].push(n)}});

// Sidebar
const tl=document.getElementById("type-list");
Object.entries(bt).sort((a,b)=>b[1].length-a[1].length).forEach(([t,nodes])=>{{
const c=TYPE_COLORS[t]||"#999";
const d=document.createElement("div");d.className="type-group";
d.innerHTML=`<h3 style="color:${{c}}">● ${{TLbl(t)}} (${{nodes.length}})</h3>`;
nodes.sort((a,b)=>b.importance-a.importance).forEach(n=>{{
const i=document.createElement("div");i.className="entity-item";
i.innerHTML=`<div class="dot" style="background:${{c}}"></div>${{n.name}}<span class="stars">${{"★".repeat(n.importance||0)}}</span>`;
i.onclick=()=>select(n.id);d.appendChild(i);
}});
tl.appendChild(d);
}});

// Legend
const lg=document.getElementById("legend");
Object.entries(TYPE_COLORS).forEach(([t,c])=>{{if(bt[t])lg.innerHTML+=`<div class="leg"><div class="leg-dot" style="background:${{c}}"></div>${{TLbl(t)}}</div>`}});
var gs = T("graph_stats", {{n: NODES.length, e: EDGES.length}});
document.getElementById("stats-line").textContent = gs + " \\u00b7 " + Object.keys(bt).length + " " + T("types_label");

document.getElementById("detail-hint").textContent = T("select_node_hint");

// D3
const svg=d3.select("#graph-svg");
const area=document.getElementById("graph-area");
const W=area.clientWidth,H=area.clientHeight;
const gRoot=svg.append("g");
svg.call(d3.zoom().scaleExtent([0.15,4]).on("zoom",e=>gRoot.attr("transform",e.transform)));

const sim=d3.forceSimulation(NODES)
.force("link",d3.forceLink(EDGES).id(d=>d.id).distance(130))
.force("charge",d3.forceManyBody().strength(-320))
.force("center",d3.forceCenter(W/2,H/2))
.force("collision",d3.forceCollide().radius(28));

const defs=svg.append("defs");
EDGES.forEach((e,i)=>{{
defs.append("marker").attr("id","ar"+i).attr("viewBox","0 -5 10 10").attr("refX",18).attr("refY",0).attr("markerWidth",4).attr("markerHeight",4).attr("orient","auto").append("path").attr("fill",e.color).attr("d","M0,-5L10,0L0,5");
}});

const linkG=gRoot.append("g");
const links=linkG.selectAll("line").data(EDGES).join("line")
.attr("stroke",d=>d.color).attr("stroke-width",1.2)
.attr("stroke-dasharray",d=>d.type==="related"?"5,5":"0")
.attr("marker-end",(d,i)=>d.type!=="related"?"url(#ar"+i+")":null)
.attr("opacity",0.5);

const nodeG=gRoot.append("g");
const nodeSel=nodeG.selectAll("g").data(NODES).join("g")
.attr("cursor","pointer")
.call(d3.drag().on("start",(e,d)=>{{if(!e.active)sim.alphaTarget(0.3).restart();d.fx=d.x;d.fy=d.y}}).on("drag",(e,d)=>{{d.fx=e.x;d.fy=e.y}}).on("end",(e,d)=>{{if(!e.active)sim.alphaTarget(0);d.fx=null;d.fy=null}}))
.on("click",(e,d)=>{{e.stopPropagation();select(d.id)}});

nodeSel.append("circle").attr("r",d=>9+d.importance*3).attr("fill",d=>d.color).attr("stroke","#fff").attr("stroke-width",1.5);
nodeSel.append("text").attr("dy",d=>20+d.importance*3).attr("text-anchor","middle").attr("font-size",9).attr("fill","#c9d1d9").text(d=>d.name.length>14?d.name.slice(0,14)+"…":d.name);

sim.on("tick",()=>{{
links.attr("x1",d=>d.source.x).attr("y1",d=>d.source.y).attr("x2",d=>d.target.x).attr("y2",d=>d.target.y);
nodeSel.attr("transform",d=>`translate(${{d.x}},${{d.y}})`);
}});

// Selection
let sel=null;
function select(id){{
sel=id;const d=nm[id];if(!d)return;
// Connected set
const conn=new Set([id]);
EDGES.forEach(e=>{{const s=typeof e.source==="object"?e.source.id:e.source,t=typeof e.target==="object"?e.target.id:e.target;if(s===id||t===id){{conn.add(s);conn.add(t)}}}});
nodeSel.select("circle").attr("opacity",n=>conn.has(n.id)?1:0.12);
nodeSel.select("text").attr("opacity",n=>conn.has(n.id)?1:0.08);
links.attr("opacity",e=>{{const s=typeof e.source==="object"?e.source.id:e.source,t=typeof e.target==="object"?e.target.id:e.target;return(s===id||t===id)?1:0.06}}).attr("stroke-width",e=>{{const s=typeof e.source==="object"?e.source.id:e.source,t=typeof e.target==="object"?e.target.id:e.target;return(s===id||t===id)?2.5:1}});

const pane=document.getElementById("detail-pane");pane.classList.remove("hidden");
const hdr=document.getElementById("detail-header"),body=document.getElementById("detail-body");
const stars="★".repeat(d.importance||0)+"☆".repeat(Math.max(0,5-(d.importance||0)));
hdr.innerHTML=`<h2>${{d.name}}</h2><span class="badge" style="background:${{d.color}}">${{TLbl(d.type)}}</span><span style="font-size:11px;color:#d2991d;margin-left:6px">${{stars}}</span>`;
let h="";
if(d.summary)h+=`<p>${{d.summary}}</p>`;
const rels=EDGES.filter(e=>{{const s=typeof e.source==="object"?e.source.id:e.source,t=typeof e.target==="object"?e.target.id:e.target;return s===id||t===id}});
if(rels.length){{h+=`<h3>${{T("relationships_label")}} (${{rels.length}})</h3>`;rels.forEach(r=>{{const oid=(typeof r.source==="object"?r.source.id:r.source)===id?(typeof r.target==="object"?r.target.id:r.target):(typeof r.source==="object"?r.source.id:r.source);const o=nm[oid];if(o)h+=`<span class="rel-item" style="border-left:3px solid ${{r.color}}" onclick="select('${{oid}}')">${{r.label}}: ${{o.name}}</span>`;}});}}
if(d.timeline&&d.timeline.length){{h+=`<h3>${{T("timeline_label")}}</h3>`;d.timeline.slice(-8).forEach(t=>h+=`<div class="tl-item"><span class="tl-date">${{t.date||''}}</span> ${{t.event||''}}</div>`)}}
body.innerHTML=h;
}}

svg.on("click",()=>{{sel=null;nodeSel.select("circle").attr("opacity",1);nodeSel.select("text").attr("opacity",1);links.attr("opacity",0.5).attr("stroke-width",1.2);document.getElementById("detail-pane").classList.add("hidden");var dh=document.getElementById("detail-hint");if(dh)dh.textContent=T("select_node_hint");}});

// Timeline slider
const sl=document.getElementById("tl-slider"),tll=document.getElementById("tl-label");
sl.oninput=()=>{{const v=parseInt(sl.value);const y=Math.round(2015+v/100*11);tll.textContent="≤ "+y;const cutoff=y.toString();nodeSel.select("circle").attr("opacity",n=>{{if(!n.release_date)return 1;return n.release_date<=cutoff?1:0.08}});nodeSel.select("text").attr("opacity",n=>{{if(!n.release_date)return 1;return n.release_date<=cutoff?1:0.06}})}};

}}catch(e){{showError("graph-area",T("error_loading"),e.message);}}
}}
)();
</script>
</body>
</html>'''

    path = output_dir / "knowledge-graph.html"
    path.write_text(html, encoding="utf-8")
    log.info(f"Graph Explorer (i18n): {path}")
    return path
