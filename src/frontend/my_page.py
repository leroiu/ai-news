"""“我的”页面生成器：收藏、分类、标签与账号同步状态入口。"""
from pathlib import Path
from typing import Optional

from src.engine.utils import ROOT_DIR, ensure_dir, log
from src.interfaces.i18n import t
from .frontend_components import card, page_header
from .frontend_shell import PageShell, render_page


MY_CSS = """\
.my-tools{position:sticky;top:0;z-index:30;padding:12px 0;background:var(--bg-primary);box-shadow:0 1px 0 var(--border)}.my-search{width:100%;margin-bottom:10px;padding:10px 12px;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--bg-primary);color:var(--text-primary);font:inherit;font-size:13px}.my-search:focus{outline:2px solid var(--accent-subtle);border-color:var(--accent)}
.my-layout{display:grid;grid-template-columns:1.4fr .9fr;gap:16px}.my-stack{display:flex;flex-direction:column;gap:16px}.my-note{color:var(--text-secondary);font-size:13px;line-height:1.7}.my-list{display:flex;flex-direction:column;gap:8px}.my-item{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;padding:13px;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--bg-elevated)}.my-item__content{min-width:0}.my-item__title{display:block;color:var(--text-primary);font-size:13px;font-weight:650;text-decoration:none;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.my-item__title:hover{color:var(--accent)}.my-item__meta{display:flex;gap:6px;flex-wrap:wrap;margin-top:5px;color:var(--text-secondary);font-size:11px}.my-item__actions{display:flex;align-items:flex-start;gap:6px}.my-item__editor{grid-column:1/-1;display:grid;grid-template-columns:140px 140px minmax(160px,1fr);gap:8px;padding-top:10px;border-top:1px solid var(--border)}.my-item__editor select,.my-item__editor input,.my-filter-select{min-width:0;padding:6px 8px;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--bg-primary);color:var(--text-primary);font:inherit;font-size:11px}.my-filter-bar{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:14px}.my-filter{padding:5px 9px;border:1px solid var(--border);border-radius:999px;background:transparent;color:var(--text-secondary);font:inherit;font-size:11px;cursor:pointer}.my-filter.active{border-color:var(--accent);background:var(--accent-subtle);color:var(--accent)}.my-summary{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.my-stat{padding:12px;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--bg-elevated)}.my-stat strong{display:block;color:var(--text-primary);font-size:20px}.my-stat span{color:var(--text-secondary);font-size:11px}.sync-box{border-left:3px solid var(--warning);background:#e3b34114}
.my-stack>.ui-card{border:0;border-top:1px solid var(--border-strong);border-radius:0;background:transparent;box-shadow:none}.my-stack>.ui-card>.ui-card__header{padding-left:0;padding-right:0}.my-stack>.ui-card>.ui-card__body{padding-left:0;padding-right:0}.my-item{border:0;border-bottom:1px solid var(--border);border-radius:0;background:transparent}.my-stat{border:0;border-right:1px solid var(--border);border-radius:0;background:transparent}.my-stat:last-child{border-right:0}
@keyframes myListIn{from{opacity:.35;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}.my-list{animation:myListIn .18s ease-out}.my-item__editor{display:none}.my-item.editing .my-item__editor{display:grid}
@media(max-width:768px){.my-layout{grid-template-columns:1fr}.my-item__editor{grid-template-columns:1fr}}@media(max-width:480px){.my-item{grid-template-columns:1fr}.my-item__actions{justify-content:flex-start;flex-wrap:wrap}.my-filter-bar{display:grid;grid-template-columns:auto minmax(0,1fr);align-items:stretch}.my-filter-bar .my-filter-select{min-height:40px}.my-filter-bar .my-filter-select:last-child{grid-column:1/-1}.my-search{min-height:42px}}
"""


MY_JS = r"""
let activeFavoriteType = 'all', activeCategory = 'all', activeReading = 'all', activeQuery = '';
function favoriteHref(item) {
  if (item.href && item.href.startsWith('/report-files/')) return '/report/' + item.href.split('/').pop();
  if (item.href) return item.href;
  const type = item.type || 'item', id = String(item.id || '');
  if (type === 'news') return /^https?:\/\//.test(id) ? id : '/article/' + encodeURIComponent(id);
  if (['entity','event','timeline'].includes(type)) return '/entity/' + encodeURIComponent(id);
  if (type === 'report') return '/reports';
  if (type === 'research') return '/research';
  return '/my';
}
function renderMyFavorites() {
  const root = document.getElementById('my-favorites-list');
  const controls = document.getElementById('my-filter-controls');
  const items = typeof uiFavoriteStore === 'function' ? uiFavoriteStore() : [];
  renderFavoriteSummary(items);
  const types = [...new Set(items.map(item => item.type || 'item'))];
  if (activeFavoriteType !== 'all' && !types.includes(activeFavoriteType)) activeFavoriteType = 'all';
  controls.innerHTML = '<div class="my-filter-bar"><button class="my-filter '+(activeFavoriteType==='all'?'active':'')+'" onclick="setFavoriteType(\'all\')">'+T('all_label')+' · '+items.length+'</button>'+types.map(type => '<button class="my-filter '+(activeFavoriteType===type?'active':'')+'" onclick="setFavoriteType(\''+esc(type)+'\')">'+favoriteTypeLabel(type)+' · '+items.filter(item => (item.type||'item')===type).length+'</button>').join('')+'<select class="my-filter-select" onchange="activeCategory=this.value;renderMyFavorites()"><option value="all">'+T('category_label')+': '+T('all_label')+'</option>'+categoryOptions(activeCategory)+'</select><select class="my-filter-select" onchange="activeReading=this.value;renderMyFavorites()"><option value="all">'+T('reading_state')+': '+T('all_label')+'</option>'+readingOptions(activeReading)+'</select></div>';
  if (!items.length) {root.innerHTML=uiStateHTML('empty',T('my_empty_favorites'),T('my_empty_favorites_desc'));return}
  const q=activeQuery.toLowerCase().trim();
  const visible = items.filter(item => {const meta=uiGetPersonalMeta(item.type,item.id);const text=[item.title,item.id,...(meta.tags||[])].join(' ').toLowerCase();return (!q||text.includes(q))&&(activeFavoriteType==='all'||(item.type||'item')===activeFavoriteType)&&(activeCategory==='all'||(meta.category||'')===activeCategory)&&(activeReading==='all'||meta.reading_state===activeReading)});
  if(!visible.length){root.innerHTML=uiStateHTML('empty',T('no_results'),T('my_filter_empty_desc'));return}
  root.innerHTML = '<div class="my-list">' + visible.map(function (item) {
    const href=favoriteHref(item),external=/^https?:\/\//.test(href),meta=uiGetPersonalMeta(item.type,item.id),tags=(meta.tags||[]).map(topicTagHTML).join('');
    return '<article class="my-item"><div class="my-item__content"><a class="my-item__title" href="'+esc(href)+'"'+(external?' target="_blank" rel="noopener"':'')+'>' + esc(item.title || item.id) + '</a><span class="my-item__meta"><span>'+favoriteTypeLabel(item.type)+'</span><span>· '+T('reading_'+meta.reading_state)+'</span><span>· '+categoryLabel(meta.category)+'</span>'+tags+'</span></div><div class="my-item__actions"><a class="ui-button ui-button--small ui-button--secondary" href="'+esc(href)+'"'+(external?' target="_blank" rel="noopener"':'')+'>'+T('my_revisit')+'</a><button class="ui-button ui-button--small ui-button--ghost" onclick="this.closest(\'.my-item\').classList.toggle(\'editing\')">'+T('my_organize')+'</button><button class="ui-button ui-button--small ui-button--ghost" data-favorite-type="' + esc(item.type || 'item') + '" data-favorite-id="' + esc(item.id || '') + '" onclick="uiToggleFavorite({type:this.dataset.favoriteType,id:this.dataset.favoriteId}, this);renderMyFavorites();">' + T('my_remove') + '</button></div><div class="my-item__editor"><select onchange="updateItemMeta(\''+esc(item.type)+'\',\''+esc(item.id)+'\',{category:this.value})">'+categoryOptions(meta.category,true)+'</select><select onchange="updateItemMeta(\''+esc(item.type)+'\',\''+esc(item.id)+'\',{reading_state:this.value})">'+readingOptions(meta.reading_state,true)+'</select><input value="'+esc((meta.tags||[]).join(', '))+'" placeholder="'+T('tags_edit_label')+'" onchange="updateItemTags(\''+esc(item.type)+'\',\''+esc(item.id)+'\',this.value)"></div></article>';
  }).join('') + '</div>';
}
function setFavoriteType(type) { activeFavoriteType = type; renderMyFavorites(); }
function categoryLabel(value){return T(value?'category_'+value:'uncategorized')}
function categoryOptions(selected,includeEmpty){const values=[['',T('uncategorized')],['learning',T('category_learning')],['tools',T('category_tools')],['research',T('category_research')],['archive',T('category_archive')]];return values.filter(x=>includeEmpty||x[0]).map(x=>'<option value="'+x[0]+'" '+(selected===x[0]?'selected':'')+'>'+x[1]+'</option>').join('')}
function readingOptions(selected,plain){return ['unread','read','later'].map(x=>'<option value="'+x+'" '+(selected===x?'selected':'')+'>'+T('reading_'+x)+'</option>').join('')}
function updateItemMeta(type,id,patch){uiUpdatePersonalMeta(type,id,patch);renderMyFavorites()}
function updateItemTags(type,id,value){uiUpdatePersonalMeta(type,id,{tags:value.split(/[,，]/).map(x=>x.trim()).filter(Boolean).slice(0,12)});renderMyFavorites()}
function favoriteTypeLabel(type) { return T('favorite_type_' + (type || 'item')) === 'favorite_type_' + (type || 'item') ? (type || 'item') : T('favorite_type_' + (type || 'item')); }
function renderFavoriteSummary(items) {
  const root = document.getElementById('my-favorites-summary');
  const types = new Set(items.map(item => item.type || 'item'));
  const later=items.filter(item=>uiGetPersonalMeta(item.type,item.id).reading_state==='later').length;
  root.innerHTML = '<div class="my-summary"><div class="my-stat"><strong>'+items.length+'</strong><span>'+T('my_saved_count')+'</span></div><div class="my-stat"><strong>'+types.size+'</strong><span>'+T('my_type_count')+'</span></div><div class="my-stat"><strong>'+later+'</strong><span>'+T('reading_later')+'</span></div></div>';
}
function esc(value) {
  return String(value || '').replace(/[&<>"']/g, function (ch) {
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch];
  });
}
renderMyFavorites();
"""


def generate_my_page(output_dir: Optional[Path] = None, lang: str = "zh") -> Path:
    """生成 reports/my.html。"""
    if output_dir is None:
        output_dir = ROOT_DIR / "reports"
    ensure_dir(output_dir)
    path = output_dir / "my.html"
    path.write_text(_build_html(lang), encoding="utf-8")
    log.info(f"My page ({lang}): {path}")
    return path


def _build_html(lang: str = "zh") -> str:
    body = page_header(
        t("my_title", lang),
        summary=t("my_subtitle", lang),
        eyebrow=t("my_eyebrow", lang),
        title_key="my_title",
        summary_key="my_subtitle",
        eyebrow_key="my_eyebrow",
    )
    body += '<div class="my-layout"><section class="my-stack">'
    tools = f'<div class="my-tools"><input id="my-search" class="my-search" type="search" placeholder="{t("my_search_placeholder", lang)}" oninput="activeQuery=this.value;renderMyFavorites()"><div id="my-filter-controls"></div></div>'
    body += card(tools + '<div id="my-favorites-list"></div>', title=t("my_favorites", lang), title_key="my_favorites")
    body += card(f'<p class="my-note" data-i18n="my_loop_desc">{t("my_loop_desc", lang)}</p>', title=t("my_loop_title", lang), title_key="my_loop_title")
    body += '</section><aside class="my-stack">'
    body += card('<div id="my-favorites-summary"></div>', title=t("my_overview", lang), title_key="my_overview")
    sync = f'<div class="sync-box ui-card__body ui-state ui-state--pending" data-ui-state="pending"><div class="ui-state__icon" aria-hidden="true">◷</div><strong data-i18n="sync_pending">{t("sync_pending", lang)}</strong><p class="my-note" data-i18n="my_sync_pending_desc">{t("my_sync_pending_desc", lang)}</p></div>'
    body += card(sync, title=t("my_sync_status", lang), title_key="my_sync_status")
    body += '</aside></div>'
    return render_page(PageShell(
        title_key="my_title",
        current_page="my",
        body_html=body,
        lang=lang,
        extra_css=MY_CSS,
        extra_js=MY_JS, page_kind="collection",
    ))
