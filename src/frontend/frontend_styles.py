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
DESIGN_SYSTEM_VERSION = "7.4.0"

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
:root{--bg-primary:#121311;--bg-card:#191a17;--bg-elevated:#23241f;--border:#34362f;--border-strong:#505247;--text-primary:#f0ede5;--text-secondary:#b4b0a6;--text-muted:#7f7c73;--accent:#8db4cf;--accent-subtle:#8db4cf1a;--success:#7fb88a;--danger:#df7a72;--warning:#d3ad63;--radius:10px;--radius-sm:6px;--shadow:0 20px 56px #0000004a;--font-sans:"SF Pro Text","Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;--font-display:"Iowan Old Style","Noto Serif SC","Songti SC",STSong,serif;--content-max:1180px}
[data-theme="light"]{--bg-primary:#e9e5dc;--bg-card:#f7f4ed;--bg-elevated:#ded9cf;--border:#c9c2b6;--border-strong:#9f978a;--text-primary:#272621;--text-secondary:#5f5b53;--text-muted:#817b70;--accent:#315f7d;--accent-subtle:#315f7d14;--success:#387351;--danger:#a94e48;--warning:#8b672f;--shadow:0 20px 56px #5d55451c}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:var(--font-sans);background:var(--bg-primary);color:var(--text-primary)}
"""

# 独立的主题变量块（供不使用 RESET_CSS 的页面引用）
THEME_VARS = """:root{--bg-primary:#121311;--bg-card:#191a17;--bg-elevated:#23241f;--border:#34362f;--border-strong:#505247;--text-primary:#f0ede5;--text-secondary:#b4b0a6;--text-muted:#7f7c73;--accent:#8db4cf;--accent-subtle:#8db4cf1a;--success:#7fb88a;--danger:#df7a72;--warning:#d3ad63;--radius:10px;--radius-sm:6px;--shadow:0 20px 56px #0000004a;--font-sans:"SF Pro Text","Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;--font-display:"Iowan Old Style","Noto Serif SC","Songti SC",STSong,serif;--content-max:1180px}
[data-theme="light"]{--bg-primary:#e9e5dc;--bg-card:#f7f4ed;--bg-elevated:#ded9cf;--border:#c9c2b6;--border-strong:#9f978a;--text-primary:#272621;--text-secondary:#5f5b53;--text-muted:#817b70;--accent:#315f7d;--accent-subtle:#315f7d14;--success:#387351;--danger:#a94e48;--warning:#8b672f;--shadow:0 20px 56px #5d55451c}
"""

NAV_CSS = """\
.nav{display:flex;min-height:34px;gap:8px;margin-bottom:24px;flex-wrap:wrap;align-items:center}
.nav a{padding:6px 14px;border-radius:var(--radius-sm);font-size:13px;text-decoration:none;color:var(--text-primary);background:var(--bg-elevated);transition:background .15s;white-space:nowrap}
.nav a:hover{background:var(--border)}
.nav a.active{background:var(--accent-subtle);color:var(--accent)}
[data-theme="light"] .nav a{background:var(--bg-elevated);color:var(--text-primary)}
[data-theme="light"] .nav a.active{background:var(--accent-subtle);color:var(--accent)}
.lang-btn{padding:4px 12px;border:1px solid var(--border);background:var(--bg-elevated);color:var(--text-primary);border-radius:var(--radius-sm);cursor:pointer;font-size:12px;margin-left:auto;transition:background .15s}
[data-theme="light"] .lang-btn{background:var(--bg-elevated);color:var(--text-primary)}
.lang-btn+.lang-btn{margin-left:0}
.lang-btn:hover{background:var(--border)}
"""

ORDINARY_PAGE_CSS = """\
.ordinary-page{width:min(100%,var(--content-max));margin:0 auto;padding:24px}
.ordinary-nav{min-height:58px}
.ordinary-heading{display:flex;min-height:112px;flex-direction:column;justify-content:flex-start;padding:4px 0 22px}
.ordinary-heading h1{font-family:var(--font-display);font-size:38px;line-height:1.1;letter-spacing:-.035em;color:var(--text-primary)}
.ordinary-heading__summary{max-width:760px;margin-top:8px;color:var(--text-secondary);font-size:14px;line-height:1.6}
.ordinary-heading__meta{margin-top:10px;color:var(--text-muted);font-size:11px}
.ordinary-tools{position:relative;z-index:20;min-height:72px}
.ordinary-content{animation:anchorContentIn .2s ease-out}
@keyframes anchorContentIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
@media(max-width:768px){.ordinary-page{padding:16px}.ordinary-heading{min-height:104px}.ordinary-heading h1{font-size:32px}}
@media(max-width:480px){.ordinary-page{padding:12px}.ordinary-nav{min-height:50px}.ordinary-heading{min-height:96px}.ordinary-heading h1{font-size:28px}.ordinary-tools{min-height:64px}}
@media(prefers-reduced-motion:reduce){.ordinary-content{animation:none}}
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
.btn{display:inline-block;padding:6px 14px;background:var(--accent);color:var(--bg-primary);border-radius:var(--radius-sm);text-decoration:none;font-size:12px;font-weight:650;transition:filter .15s,transform .15s}
.btn:hover{filter:brightness(1.12);transform:translateY(-1px)}
.btn:active{transform:translateY(0)}
.btn-outline{background:var(--bg-elevated);border:1px solid var(--border)}
.btn-outline:hover{background:var(--border)}
.btn-sm{padding:3px 10px;font-size:11px}
.filter-btn{padding:4px 12px;border-radius:12px;font-size:11px;cursor:pointer;border:1px solid var(--border);background:var(--bg-card);color:var(--text-secondary);transition:all .15s;white-space:nowrap}
.filter-btn:hover{border-color:var(--accent);color:var(--text-primary)}
.filter-btn.active,.filter-btn.active:hover{background:var(--accent-subtle);border-color:var(--accent);color:var(--accent)}
.favorite-btn{padding:3px 9px;border:1px solid var(--border);background:var(--bg-elevated);color:var(--text-secondary);border-radius:999px;cursor:pointer;font-size:11px}.favorite-btn.is-favorited,.favorite-btn[aria-pressed="true"]{border-color:var(--warning);background:#e3b34122;color:var(--warning)}
"""

INTELLIGENCE_CSS = """\
.intel-rating{display:inline-flex;align-items:center;gap:7px}.intel-rating__stars{color:var(--warning);letter-spacing:1px}.intel-rating__label{color:var(--text-secondary);font-size:10px}.intel-rating-help{margin:8px 0;color:var(--text-secondary);font-size:11px}.intel-rating-help summary{width:max-content;color:var(--accent);cursor:pointer}.intel-rating-help p{max-width:620px;margin-top:6px;line-height:1.6}.intel-source{display:flex;align-items:center;gap:6px;flex-wrap:wrap;color:var(--text-muted);font-size:11px}.intel-source a{color:var(--accent);text-decoration:none}.intel-evidence{display:inline-flex;padding:2px 7px;border:1px solid var(--border);border-radius:999px;font-size:10px;font-weight:650}.intel-evidence--fact{color:var(--success)}.intel-evidence--analysis{color:var(--accent)}.intel-evidence--inference{color:var(--warning)}.intel-evidence--advice{color:var(--text-secondary)}.intel-topic{display:inline-flex;padding:3px 8px;border-radius:999px;background:var(--bg-elevated);color:var(--text-secondary);font-size:10px}.ui-state{padding:28px 20px;text-align:center;border:1px dashed var(--border);border-radius:var(--radius);color:var(--text-secondary)}.ui-state__icon{margin-bottom:8px;font-size:24px}.ui-state strong{display:block;margin-bottom:5px;color:var(--text-primary);font-size:14px}.ui-state p{max-width:520px;margin:auto;font-size:12px;line-height:1.6}.ui-state--pending{border-style:solid;border-left:3px solid var(--warning);text-align:left}.ui-state--error{border-color:var(--danger)}.ui-state--unavailable{opacity:.8}
"""

ACTION_COMPONENT_CSS = """\
.favorite-btn{display:inline-flex;min-height:28px;padding:3px 9px;align-items:center;justify-content:center;border:1px solid var(--border);border-radius:999px;background:var(--bg-elevated);color:var(--text-secondary);font:inherit;font-size:10px;line-height:1.2;cursor:pointer;transition:background .18s,border-color .18s,color .18s}.favorite-btn:hover{border-color:var(--warning);color:var(--warning)}.favorite-btn.is-favorited,.favorite-btn[aria-pressed="true"]{border-color:var(--warning);background:#e3b34122;color:var(--warning)}
:where(.filter-btn,.cat-tag,.my-filter){display:inline-flex;min-height:28px;padding:4px 10px;align-items:center;justify-content:center;gap:4px;border:1px solid var(--border);border-radius:999px;background:transparent;color:var(--text-secondary);font:inherit;font-size:11px;line-height:1.2;cursor:pointer;transition:background .18s,border-color .18s,color .18s}
:where(.filter-btn,.cat-tag,.my-filter):hover{border-color:var(--accent);color:var(--accent)}
:where(.filter-btn,.cat-tag,.my-filter).active{border-color:var(--accent);background:var(--accent-subtle);color:var(--accent)}
:where(.favorite-btn,.filter-btn,.cat-tag,.my-filter):focus-visible{outline:2px solid var(--accent);outline-offset:2px}
"""

ACCESSIBILITY_CSS = """\
.skip-link{position:fixed;left:16px;top:8px;z-index:1000;padding:8px 12px;border-radius:6px;background:var(--accent);color:#fff;text-decoration:none;font-size:13px;font-weight:600;transform:translateY(-160%);transition:transform .18s ease}
.skip-link:focus{transform:translateY(0)}
:where(a,button,input,select,textarea,summary,[tabindex]):focus-visible{outline:2px solid var(--accent);outline-offset:2px}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{scroll-behavior:auto!important;animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important}}
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
  .nav{gap:3px;flex-wrap:nowrap;margin-bottom:18px}
  .nav a{min-height:32px;padding:6px 7px;display:inline-flex;align-items:center;font-size:10px}
  .lang-btn{min-width:30px;min-height:32px;padding:5px 7px;font-size:10px;margin-left:1px;flex-shrink:0}
  .card{padding:14px}
  .btn,.btn-outline,.btn-sm{min-height:34px;padding:6px 10px;font-size:10px}
}
@media (max-width:360px){
  .nav{gap:2px}
  .nav a{padding:6px 5px;font-size:10px}
  .lang-btn{min-width:28px;padding:5px;font-size:10px;margin-left:0}
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
.error-state .err-retry{display:inline-block;padding:8px 20px;background:var(--accent);color:var(--bg-primary);border:none;border-radius:var(--radius-sm);cursor:pointer;font-size:12px;font-weight:650;transition:filter .15s,transform .15s}
.error-state .err-retry:hover{filter:brightness(1.12);transform:translateY(-1px)}
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

/* ── Auth ── */
function getToken(){
  try { return localStorage.getItem('ai_obs_token') || null; }
  catch(e) { return null; }
}
function getCurrentUser(){
  try { var u = localStorage.getItem('ai_obs_user'); return u ? JSON.parse(u) : null; }
  catch(e) { return null; }
}
function isLoggedIn(){ return !!getToken(); }
function isAdmin(){ var u = getCurrentUser(); return u && u.role === 'admin'; }
function logoutFn(){
  localStorage.removeItem('ai_obs_token');
  localStorage.removeItem('ai_obs_user');
  window.location.reload();
}

async function apiFetch(url, options) {
  try {
    options = options || {};
    var token = getToken();
    if (token) {
      options.headers = options.headers || {};
      options.headers['Authorization'] = 'Bearer ' + token;
    }
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
  el.innerHTML = '<div class="error-state ui-state ui-state--error" data-ui-state="error"><div class="err-icon">⚠️</div>' +
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
function uiPersonalMetaStore() {
  try { return JSON.parse(localStorage.getItem('ai_observatory_personal_meta') || '{}'); }
  catch (e) { return {}; }
}
function uiGetPersonalMeta(type, id) {
  const store=uiPersonalMetaStore(), key=uiFavoriteKey({type:type,id:id});
  return Object.assign({category:'',tags:[],reading_state:'unread'},store[key]||{});
}
function uiUpdatePersonalMeta(type, id, patch) {
  const store=uiPersonalMetaStore(), key=uiFavoriteKey({type:type,id:id});
  store[key]=Object.assign({},uiGetPersonalMeta(type,id),patch||{}, {type:type,id:id,updated_at:new Date().toISOString()});
  localStorage.setItem('ai_observatory_personal_meta',JSON.stringify(store));
  if(typeof uiToast==='function')uiToast(typeof T==='function'?T('personal_saved'):'Saved','success');
  return store[key];
}
function uiPersonalItems() {
  const store=uiPersonalMetaStore();
  return Object.keys(store).map(function(key) {
    const meta=store[key]||{}, split=key.indexOf(':');
    return Object.assign({},meta,{
      type:meta.type||key.slice(0,split<0?key.length:split),
      id:meta.id||key.slice(split<0?key.length:split+1)
    });
  }).filter(function(item){return item.id&&item.reading_state&&item.reading_state!=='unread'});
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
function favoriteButtonHTML(type, id, title, extraClass, href) {
  const pressed = uiFavoriteStore().some(function (item) { return uiFavoriteKey(item) === uiFavoriteKey({type:type, id:id}); });
  return '<button class="favorite-btn '+(extraClass || '')+(pressed ? ' is-favorited' : '')+'" aria-pressed="'+pressed+'" data-favorite-type="'+uiEscAttr(type)+'" data-favorite-id="'+uiEscAttr(id)+'" data-favorite-title="'+uiEscAttr(title || '')+'" data-favorite-href="'+uiEscAttr(href || '')+'" onclick="uiToggleFavorite({type:this.dataset.favoriteType,id:this.dataset.favoriteId,title:this.dataset.favoriteTitle,href:this.dataset.favoriteHref},this);event.preventDefault();event.stopPropagation()">'+(typeof T !== 'undefined' ? T(pressed ? 'favorited' : 'favorite') : (pressed ? 'Saved' : 'Save'))+'</button>';
}

function editorialRatingHTML(value, explanation) {
  const score=Math.max(0,Math.min(5,Number(value)||0)), label=explanation||(typeof T==='function'?T('editorial_rating_label'):'Editorial rating');
  return '<span class="intel-rating" title="'+uiEscAttr(label)+'" aria-label="'+uiEscAttr(label)+' '+score+'/5"><span class="intel-rating__stars">'+'★'.repeat(score)+'☆'.repeat(5-score)+'</span><span class="intel-rating__label">'+uiEscAttr(label)+'</span></span>';
}
function ratingHelpHTML() { return '<details class="intel-rating-help"><summary>'+uiEscAttr(T('editorial_rating_label'))+'</summary><p>'+uiEscAttr(T('editorial_rating_help'))+'</p></details>'; }
function sourceMetaHTML(source, published, href) {
  const name=href?'<a href="'+uiEscAttr(href)+'" target="_blank" rel="noopener">'+uiEscAttr(source)+'</a>':uiEscAttr(source||'');
  const date=published?'<time datetime="'+uiEscAttr(published)+'">'+uiEscAttr(published)+'</time>':'';
  return '<div class="intel-source">'+name+(name&&date?'<span>·</span>':'')+date+'</div>';
}
function evidenceLabelHTML(kind) {
  const labels={fact:'evidence_fact',analysis:'evidence_analysis',inference:'evidence_inference',advice:'evidence_advice'};
  return '<span class="intel-evidence intel-evidence--'+uiEscAttr(kind)+'">'+uiEscAttr(typeof T==='function'?T(labels[kind]||labels.analysis):kind)+'</span>';
}
function topicTagHTML(label) { return '<span class="intel-topic">'+uiEscAttr(label)+'</span>'; }
function uiStateHTML(state, title, description) {
  const icons={loading:'◌',empty:'◇',error:'⚠',processing:'◌',pending:'◷',unavailable:'—'};
  return '<div class="ui-state ui-state--'+uiEscAttr(state)+'" data-ui-state="'+uiEscAttr(state)+'" role="status"><div class="ui-state__icon">'+(icons[state]||'◇')+'</div><strong>'+uiEscAttr(title)+'</strong>'+(description?'<p>'+uiEscAttr(description)+'</p>':'')+'</div>';
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

BASE_CSS = RESET_CSS + NAV_CSS + ORDINARY_PAGE_CSS + SPINNER_CSS + SKELETON_CSS + BUTTON_CSS + INTELLIGENCE_CSS + ACTION_COMPONENT_CSS + ACCESSIBILITY_CSS + ANIMATION_CSS + RESPONSIVE_CSS + ERROR_CSS

# 注入顺序建议: {RESET_CSS} + 页面专属样式 + {NAV_CSS} + {SPINNER_CSS} + {SKELETON_CSS} + {BUTTON_CSS} + {ANIMATION_CSS} + {RESPONSIVE_CSS} + {ERROR_CSS}
# 简化为: 末尾加 {ANIMATION_CSS}{RESPONSIVE_CSS}{ERROR_CSS}（骨架屏按需使用 skeletonHTML()）
