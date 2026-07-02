"""
AI Intelligence Platform — 前端设计系统

集中管理颜色、CSS 片段、动画和响应式布局。
所有页面生成器从本模块导入，消除重复定义。

遵循 ENGINEERING_PRINCIPLES.md: 文件 < 300 行，单一事实来源。

版本号变更规则（SemVer）：
  MAJOR — 移除或重命名导出 → Codex 必须重新读取本文件
  MINOR — 新增导出或 CSS 片段 → Codex 建议重新读取
  PATCH — 仅修改样式值，接口不变 → Codex 无需关注
"""
import json

# ── 设计系统版本（Claude-Codex 协作协议 Layer A）──
DESIGN_SYSTEM_VERSION = "5.2.0"

# ═══════════════════════════════════════════════════════════
# 设计令牌
# ═══════════════════════════════════════════════════════════

TYPE_COLORS = {
    "model": "#4C78A8", "company": "#F58518", "tech": "#72B7B2",
    "concept": "#E45756", "product": "#54A24B", "person": "#B279A2",
    "methodology": "#D4A017", "event": "#FF9DA6",
}

TYPE_ICONS = {
    "model": "🧠", "company": "🏢", "tech": "⚙️",
    "concept": "💡", "product": "🚀", "person": "👤",
    "methodology": "📐", "event": "📅",
}

EDGE_COLORS = {
    "related": "#999", "depends_on": "#E45756", "influenced": "#4C78A8",
}

# ═══════════════════════════════════════════════════════════
# CSS 片段（每个页面注入的共享样式）
# ═══════════════════════════════════════════════════════════

RESET_CSS = """\
:root{--bg-primary:#0d1117;--bg-card:#161b22;--bg-elevated:#21262d;--border:#30363d;--text-primary:#c9d1d9;--text-secondary:#8b949e;--text-muted:#484f58;--accent:#58a6ff;--accent-subtle:#1f6feb22;--success:#3fb950;--danger:#f85149;--warning:#e3b341;--radius:8px;--radius-sm:6px;--shadow:0 4px 16px #00000033}
[data-theme="light"]{--bg-primary:#fff;--bg-card:#f6f8fa;--bg-elevated:#eaeef2;--border:#d0d7de;--text-primary:#1f2328;--text-secondary:#656d76;--text-muted:#8b949e;--accent:#0969da;--accent-subtle:#ddf4ff;--success:#1a7f37;--danger:#cf222e;--warning:#9a6700;--shadow:0 4px 16px #00000011}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:var(--bg-primary);color:var(--text-primary)}
"""

# 独立的主题变量块（供不使用 RESET_CSS 的页面引用）
THEME_VARS = """:root{--bg-primary:#0d1117;--bg-card:#161b22;--bg-elevated:#21262d;--border:#30363d;--text-primary:#c9d1d9;--text-secondary:#8b949e;--text-muted:#484f58;--accent:#58a6ff;--accent-subtle:#1f6feb22;--success:#3fb950;--danger:#f85149;--warning:#e3b341;--radius:8px;--radius-sm:6px;--shadow:0 4px 16px #00000033}
[data-theme="light"]{--bg-primary:#fff;--bg-card:#f6f8fa;--bg-elevated:#eaeef2;--border:#d0d7de;--text-primary:#1f2328;--text-secondary:#656d76;--text-muted:#8b949e;--accent:#0969da;--accent-subtle:#ddf4ff;--success:#1a7f37;--danger:#cf222e;--warning:#9a6700;--shadow:0 4px 16px #00000011}
"""

NAV_CSS = """\
.nav{display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap;align-items:center}
.nav a{padding:6px 14px;border-radius:var(--radius-sm);font-size:13px;text-decoration:none;color:var(--text-primary);background:var(--bg-elevated);transition:background .15s;white-space:nowrap}
.nav a:hover{background:var(--border)}
.nav a.active{background:var(--accent-subtle);color:var(--accent)}
.lang-btn{padding:4px 12px;border:1px solid var(--border);background:var(--bg-elevated);color:var(--text-primary);border-radius:var(--radius-sm);cursor:pointer;font-size:12px;margin-left:auto;transition:background .15s}
.lang-btn+.lang-btn{margin-left:0}
.lang-btn:hover{background:var(--border)}
"""

SPINNER_CSS = """\
.spinner{text-align:center;padding:40px;color:var(--text-secondary)}
.loading{display:inline-block;width:20px;height:20px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin .6s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
"""

SKELETON_CSS = """\
.skeleton{background:linear-gradient(90deg,var(--bg-elevated) 25%,var(--border) 50%,var(--bg-elevated) 75%);background-size:200% 100%;animation:shimmer 1.5s ease-in-out infinite;border-radius:var(--radius-sm)}
.skeleton-text{height:14px;margin-bottom:8px}.skeleton-text:last-child{width:60%}
.skeleton-title{height:20px;width:40%;margin-bottom:12px}
.skeleton-card{height:80px;border-radius:var(--radius)}
@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
"""

BUTTON_CSS = """\
.btn{display:inline-block;padding:6px 14px;background:#238636;color:#fff;border-radius:var(--radius-sm);text-decoration:none;font-size:12px;transition:all .15s}
.btn:hover{background:#2ea043;transform:translateY(-1px)}
.btn:active{transform:translateY(0)}
.btn-outline{background:var(--bg-elevated);border:1px solid var(--border)}
.btn-outline:hover{background:var(--border)}
.btn-sm{padding:3px 10px;font-size:11px}
.filter-btn{padding:4px 12px;border-radius:12px;font-size:11px;cursor:pointer;border:1px solid var(--border);background:var(--bg-card);color:var(--text-secondary);transition:all .15s;white-space:nowrap}
.filter-btn:hover{border-color:var(--accent);color:var(--text-primary)}
.filter-btn.active,.filter-btn.active:hover{background:var(--accent-subtle);border-color:var(--accent);color:var(--accent)}
.favorite-btn{padding:3px 9px;border:1px solid var(--border);background:var(--bg-elevated);color:var(--text-secondary);border-radius:999px;cursor:pointer;font-size:11px}.favorite-btn.is-favorited,.favorite-btn[aria-pressed="true"]{border-color:var(--warning);background:#e3b34122;color:var(--warning)}
"""

ANIMATION_CSS = """\
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
@keyframes slideUp{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
@keyframes slideIn{from{opacity:0;transform:translateX(-12px)}to{opacity:1;transform:translateX(0)}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.6}}
@keyframes shake{0%,100%{transform:translateX(0)}20%,60%{transform:translateX(-6px)}40%,80%{transform:translateX(6px)}}
.anim-fade{animation:fadeIn .35s ease-out}
.anim-stagger>*{opacity:0;animation:fadeIn .3s ease-out forwards}
.anim-stagger>*:nth-child(1){animation-delay:0s}
.anim-stagger>*:nth-child(2){animation-delay:.05s}
.anim-stagger>*:nth-child(3){animation-delay:.1s}
.anim-stagger>*:nth-child(4){animation-delay:.15s}
.anim-stagger>*:nth-child(5){animation-delay:.2s}
.anim-stagger>*:nth-child(6){animation-delay:.25s}
.anim-stagger>*:nth-child(7){animation-delay:.3s}
.anim-stagger>*:nth-child(8){animation-delay:.35s}
.anim-stagger>*:nth-child(9){animation-delay:.4s}
.anim-stagger>*:nth-child(10){animation-delay:.45s}
.card-hover{transition:all .2s ease}
.card-hover:hover{transform:translateY(-2px);box-shadow:var(--shadow);border-color:var(--accent-subtle)}
"""

RESPONSIVE_CSS = """\
@media (max-width:768px){
  body{padding:16px}
  h1{font-size:20px}
  .nav{gap:6px;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none}
  .nav::-webkit-scrollbar{display:none}
  .nav a{padding:5px 10px;font-size:11px;flex-shrink:0}
  .grid{grid-template-columns:1fr!important}
}
@media (max-width:480px){
  body{padding:12px}
  h1{font-size:18px}
  .nav{gap:4px}
  .nav a{padding:4px 8px;font-size:10px}
  .lang-btn{padding:3px 8px;font-size:10px;margin-left:4px}
  .card{padding:14px}
  .btn,.btn-outline,.btn-sm{font-size:10px;padding:4px 10px}
}
@media (min-width:1024px){
  .container-wide{max-width:1200px}
}
"""

ERROR_CSS = """\
.error-state{text-align:center;padding:48px 24px;color:var(--text-secondary)}
.error-state .err-icon{font-size:40px;margin-bottom:12px}
.error-state .err-msg{font-size:14px;margin-bottom:8px;color:var(--text-primary)}
.error-state .err-detail{font-size:11px;color:var(--text-muted);margin-bottom:16px}
.error-state .err-retry{display:inline-block;padding:8px 20px;background:#238636;color:#fff;border:none;border-radius:var(--radius-sm);cursor:pointer;font-size:12px;transition:all .15s}
.error-state .err-retry:hover{background:#2ea043;transform:translateY(-1px)}
"""

# ═══════════════════════════════════════════════════════════
# 共享 JavaScript（运行时注入）
# ═══════════════════════════════════════════════════════════

SHARED_JS = """\
/* ── Theme ── */
(function(){
  var theme = localStorage.getItem('theme') || 'dark';
  document.documentElement.setAttribute('data-theme', theme);
})();
function toggleTheme(){
  var cur = document.documentElement.getAttribute('data-theme') || 'dark';
  var next = cur === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
  updateThemeLabel();
}
function updateThemeLabel(){
  var btn = document.getElementById('theme-toggle');
  if (!btn) return;
  var cur = document.documentElement.getAttribute('data-theme') || 'dark';
  btn.textContent = cur === 'dark' ? '☀️' : '🌙';
  btn.title = cur === 'dark' ? 'Switch to light mode' : '切换到暗色模式';
}
function themeLabel(){
  var cur = document.documentElement.getAttribute('data-theme') || 'dark';
  return cur === 'dark' ? '☀️' : '🌙';
}
document.addEventListener('DOMContentLoaded', updateThemeLabel);

async function apiFetch(url, options) {
  try {
    const r = await fetch(url, options);
    if (!r.ok) throw new Error("HTTP " + r.status);
    return await r.json();
  } catch (err) {
    console.error("apiFetch failed:", url, err);
    throw err;
  }
}

function showError(containerId, msg, detail) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = '<div class="error-state"><div class="err-icon">⚠️</div>' +
    '<div class="err-msg">' + msg + '</div>' +
    (detail ? '<div class="err-detail">' + detail + '</div>' : '') +
    '<button class="err-retry" onclick="location.reload()">' + (typeof T !== 'undefined' ? T("retry") : "Retry") + '</button></div>';
}

function uiFavoriteStore() {
  try { return JSON.parse(localStorage.getItem('ai_observatory_favorites') || '[]'); }
  catch (e) { return []; }
}
function uiSaveFavoriteStore(items) {
  localStorage.setItem('ai_observatory_favorites', JSON.stringify(items || []));
}
function uiFavoriteKey(item) {
  return String((item && item.type) || 'item') + ':' + String((item && item.id) || '');
}
function uiToggleFavorite(item, trigger) {
  if (!item || !item.id) return false;
  const key = uiFavoriteKey(item);
  let items = uiFavoriteStore();
  const exists = items.some(function (saved) { return uiFavoriteKey(saved) === key; });
  if (exists) items = items.filter(function (saved) { return uiFavoriteKey(saved) !== key; });
  else items.unshift(Object.assign({}, item, {saved_at: new Date().toISOString()}));
  uiSaveFavoriteStore(items);
  if (trigger) {
    trigger.classList.toggle('is-favorited', !exists);
    trigger.setAttribute('aria-pressed', String(!exists));
    trigger.textContent = (typeof T !== 'undefined' ? T(!exists ? 'favorited' : 'favorite') : (!exists ? 'Saved' : 'Save'));
  }
  if (typeof uiToast === 'function') {
    uiToast(typeof T !== 'undefined' ? T(!exists ? 'favorite_saved' : 'favorite_removed') : (!exists ? 'Saved' : 'Removed'), !exists ? 'success' : 'accent');
  }
  return !exists;
}
function uiEscAttr(value) {
  return String(value || '').replace(/[&<>"']/g, function (c) {
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
  });
}
function favoriteButtonHTML(type, id, title, extraClass) {
  const pressed = uiFavoriteStore().some(function (item) { return uiFavoriteKey(item) === uiFavoriteKey({type:type, id:id}); });
  return '<button class="favorite-btn '+(extraClass || '')+(pressed ? ' is-favorited' : '')+'" aria-pressed="'+pressed+'" data-favorite-type="'+uiEscAttr(type)+'" data-favorite-id="'+uiEscAttr(id)+'" data-favorite-title="'+uiEscAttr(title || '')+'" onclick="uiToggleFavorite({type:this.dataset.favoriteType,id:this.dataset.favoriteId,title:this.dataset.favoriteTitle},this);event.preventDefault();event.stopPropagation()">'+(typeof T !== 'undefined' ? T(pressed ? 'favorited' : 'favorite') : (pressed ? 'Saved' : 'Save'))+'</button>';
}

/* 骨架屏 — 可选择替代 spinner 使用
   skeletonHTML('card', 3) → 3 张卡片骨架
   skeletonHTML('text', 4)  → 4 行文本骨架
   skeletonHTML('title')    → 1 行标题骨架 */
function skeletonHTML(type, count) {
  count = count || 1;
  if (type === 'card') return Array(count).fill('<div class="skeleton skeleton-card" style="margin-bottom:12px"></div>').join('');
  if (type === 'text') return Array(count).fill('<div class="skeleton skeleton-text"></div>').join('');
  if (type === 'title') return '<div class="skeleton skeleton-title"></div>';
  return '';
}
"""

# ═══════════════════════════════════════════════════════════
# 组合样式
# ═══════════════════════════════════════════════════════════

BASE_CSS = RESET_CSS + NAV_CSS + SPINNER_CSS + SKELETON_CSS + BUTTON_CSS + ANIMATION_CSS + RESPONSIVE_CSS + ERROR_CSS

# 注入顺序建议: {RESET_CSS} + 页面专属样式 + {NAV_CSS} + {SPINNER_CSS} + {SKELETON_CSS} + {BUTTON_CSS} + {ANIMATION_CSS} + {RESPONSIVE_CSS} + {ERROR_CSS}
# 简化为: 末尾加 {ANIMATION_CSS}{RESPONSIVE_CSS}{ERROR_CSS}（骨架屏按需使用 skeletonHTML()）
