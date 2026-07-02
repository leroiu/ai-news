"""“我的”页面生成器：收藏、分类、标签与账号同步状态入口。"""
from pathlib import Path
from typing import Optional

from src.engine.utils import ROOT_DIR, ensure_dir, log
from src.interfaces.i18n import t
from .frontend_components import card, page_header
from .frontend_shell import PageShell, render_page


MY_CSS = """\
.my-layout{display:grid;grid-template-columns:1.4fr .9fr;gap:16px}.my-stack{display:flex;flex-direction:column;gap:16px}.my-note{color:var(--text-secondary);font-size:13px;line-height:1.7}.my-list{display:flex;flex-direction:column;gap:8px}.my-item{display:flex;justify-content:space-between;gap:14px;padding:13px;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--bg-elevated)}.my-item__content{min-width:0}.my-item__title{display:block;color:var(--text-primary);font-size:13px;font-weight:650;text-decoration:none;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.my-item__title:hover{color:var(--accent)}.my-item__meta{display:block;margin-top:5px;color:var(--text-secondary);font-size:11px}.my-item__actions{display:flex;align-items:center;gap:6px;flex-shrink:0}.my-filter-bar{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:14px}.my-filter{padding:5px 9px;border:1px solid var(--border);border-radius:999px;background:transparent;color:var(--text-secondary);font:inherit;font-size:11px;cursor:pointer}.my-filter.active{border-color:var(--accent);background:var(--accent-subtle);color:var(--accent)}.my-summary{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}.my-stat{padding:12px;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--bg-elevated)}.my-stat strong{display:block;color:var(--text-primary);font-size:20px}.my-stat span{color:var(--text-secondary);font-size:11px}.sync-box{border-left:3px solid var(--warning);background:#e3b34114}
@media(max-width:768px){.my-layout{grid-template-columns:1fr}}
"""


MY_JS = r"""
let activeFavoriteType = 'all';
function favoriteHref(item) {
  const type = item.type || 'item', id = String(item.id || '');
  if (type === 'news' && /^https?:\/\//.test(id)) return id;
  if (['entity','event','timeline'].includes(type)) return '/entity/' + encodeURIComponent(id);
  if (type === 'report') return '/reports';
  if (type === 'research') return '/research';
  return '/my';
}
function renderMyFavorites() {
  const root = document.getElementById('my-favorites-list');
  const items = typeof uiFavoriteStore === 'function' ? uiFavoriteStore() : [];
  renderFavoriteSummary(items);
  if (!items.length) {
    root.innerHTML = '<div class="ui-empty"><div class="ui-empty__icon">◇</div><h3>'+T('my_empty_favorites')+'</h3><p>'+T('my_empty_favorites_desc')+'</p></div>';
    return;
  }
  const types = [...new Set(items.map(item => item.type || 'item'))];
  if (activeFavoriteType !== 'all' && !types.includes(activeFavoriteType)) activeFavoriteType = 'all';
  const filters = '<div class="my-filter-bar"><button class="my-filter '+(activeFavoriteType==='all'?'active':'')+'" onclick="setFavoriteType(\'all\')">'+T('all_label')+' · '+items.length+'</button>'+types.map(type => '<button class="my-filter '+(activeFavoriteType===type?'active':'')+'" onclick="setFavoriteType(\''+esc(type)+'\')">'+favoriteTypeLabel(type)+' · '+items.filter(item => (item.type||'item')===type).length+'</button>').join('')+'</div>';
  const visible = activeFavoriteType === 'all' ? items : items.filter(item => (item.type || 'item') === activeFavoriteType);
  root.innerHTML = filters + '<div class="my-list">' + visible.map(function (item) {
    const href = favoriteHref(item), external = /^https?:\/\//.test(href);
    return '<article class="my-item"><div class="my-item__content"><a class="my-item__title" href="'+esc(href)+'"'+(external?' target="_blank" rel="noopener"':'')+'>' + esc(item.title || item.id) + '</a><span class="my-item__meta">' + favoriteTypeLabel(item.type) + ' · ' + esc((item.saved_at || '').slice(0,10)) + '</span></div><div class="my-item__actions"><a class="ui-button ui-button--small ui-button--secondary" href="'+esc(href)+'"'+(external?' target="_blank" rel="noopener"':'')+'>'+T('my_revisit')+'</a><button class="ui-button ui-button--small ui-button--ghost" data-favorite-type="' + esc(item.type || 'item') + '" data-favorite-id="' + esc(item.id || '') + '" onclick="uiToggleFavorite({type:this.dataset.favoriteType,id:this.dataset.favoriteId}, this);renderMyFavorites();">' + T('my_remove') + '</button></div></article>';
  }).join('') + '</div>';
}
function setFavoriteType(type) { activeFavoriteType = type; renderMyFavorites(); }
function favoriteTypeLabel(type) { return T('favorite_type_' + (type || 'item')) === 'favorite_type_' + (type || 'item') ? (type || 'item') : T('favorite_type_' + (type || 'item')); }
function renderFavoriteSummary(items) {
  const root = document.getElementById('my-favorites-summary');
  const types = new Set(items.map(item => item.type || 'item'));
  root.innerHTML = '<div class="my-summary"><div class="my-stat"><strong>'+items.length+'</strong><span>'+T('my_saved_count')+'</span></div><div class="my-stat"><strong>'+types.size+'</strong><span>'+T('my_type_count')+'</span></div></div>';
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
    body += card('<div id="my-favorites-list"></div>', title=t("my_favorites", lang), title_key="my_favorites")
    body += card(f'<p class="my-note" data-i18n="my_loop_desc">{t("my_loop_desc", lang)}</p>', title=t("my_loop_title", lang), title_key="my_loop_title")
    body += '</section><aside class="my-stack">'
    body += card('<div id="my-favorites-summary"></div>', title=t("my_overview", lang), title_key="my_overview")
    sync = f'<div class="sync-box ui-card__body"><strong data-i18n="sync_pending">{t("sync_pending", lang)}</strong><p class="my-note" data-i18n="my_sync_pending_desc">{t("my_sync_pending_desc", lang)}</p></div>'
    body += card(sync, title=t("my_sync_status", lang), title_key="my_sync_status")
    body += '</aside></div>'
    return render_page(PageShell(
        title_key="my_title",
        current_page="my",
        body_html=body,
        lang=lang,
        extra_css=MY_CSS,
        extra_js=MY_JS,
    ))
