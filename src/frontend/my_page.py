"""“我的”页面生成器：收藏、分类、标签与账号同步状态入口。"""
from pathlib import Path
from typing import Optional

from src.engine.utils import ROOT_DIR, ensure_dir, log
from src.interfaces.i18n import t
from .frontend_components import card, page_header
from .frontend_shell import PageShell, render_page


MY_CSS = """\
.my-layout{display:grid;grid-template-columns:1.4fr .9fr;gap:16px}.my-stack{display:flex;flex-direction:column;gap:16px}.my-note{color:var(--text-secondary);font-size:13px;line-height:1.7}.my-list{display:flex;flex-direction:column;gap:10px}.my-item{display:flex;justify-content:space-between;gap:12px;padding:12px;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--bg-elevated)}.my-item strong{font-size:13px}.my-item span{color:var(--text-secondary);font-size:11px}.my-pill-row{display:flex;flex-wrap:wrap;gap:8px}.my-pill{padding:6px 10px;border:1px solid var(--border);border-radius:999px;color:var(--text-secondary);font-size:12px}.sync-box{border-left:3px solid var(--warning);background:#e3b34114}
@media(max-width:768px){.my-layout{grid-template-columns:1fr}}
"""


MY_JS = r"""
function renderMyFavorites() {
  const root = document.getElementById('my-favorites-list');
  const items = typeof uiFavoriteStore === 'function' ? uiFavoriteStore() : [];
  if (!items.length) {
    root.innerHTML = '<div class="ui-empty"><div class="ui-empty__icon">◇</div><h3>'+T('my_empty_favorites')+'</h3><p>'+T('my_empty_favorites_desc')+'</p></div>';
    return;
  }
  root.innerHTML = '<div class="my-list">' + items.map(function (item) {
    return '<div class="my-item"><div><strong>' + esc(item.title || item.id) + '</strong><br><span>' + esc(item.type || 'item') + ' · ' + esc((item.saved_at || '').slice(0,10)) + '</span></div><button class="ui-button ui-button--small ui-button--ghost" data-favorite-type="' + esc(item.type || 'item') + '" data-favorite-id="' + esc(item.id || '') + '" onclick="uiToggleFavorite({type:this.dataset.favoriteType,id:this.dataset.favoriteId}, this);renderMyFavorites();">' + T('favorite_removed') + '</button></div>';
  }).join('') + '</div>';
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
    body += card('<div class="my-pill-row"><span class="my-pill">AI Agent</span><span class="my-pill">Model</span><span class="my-pill">Workflow</span></div>', title=t("my_categories", lang), title_key="my_categories")
    body += card('<div class="my-pill-row"><span class="my-pill">值得研究</span><span class="my-pill">待验证</span><span class="my-pill">工具</span></div>', title=t("my_tags", lang), title_key="my_tags")
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
