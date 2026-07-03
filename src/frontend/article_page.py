"""站内资讯详情页：摘要、证据、来源、关联专题与个人状态。"""
from pathlib import Path
from typing import Optional

from src.engine.utils import ROOT_DIR, ensure_dir, log
from .frontend_shell import PageShell, render_page


ARTICLE_CSS = """\
.article-shell{max-width:1080px;margin:auto}.article-head{position:relative;padding:34px 0 38px;border-bottom:1px solid var(--border)}.article-eyebrow{color:var(--accent);font-size:10px;font-weight:750;letter-spacing:.18em;text-transform:uppercase}.article-head h1{max-width:920px;margin:14px 0 18px;font-family:var(--font-display);font-size:46px;font-weight:650;letter-spacing:-.035em;line-height:1.18}.article-meta-row,.article-actions,.article-tags{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.article-tags{margin-top:10px}.article-actions{margin-top:22px}.article-grid{display:grid;grid-template-columns:minmax(0,1fr) 304px;gap:42px;margin-top:34px;align-items:start}.article-stack{display:grid;gap:30px}.article-stack>.ui-card{background:transparent;border:0;border-radius:0}.article-stack>.ui-card>.ui-card__header{padding:0 0 12px;border-bottom:1px solid var(--border)}.article-stack>.ui-card>.ui-card__body{padding:18px 0}.article-stack>.ui-card .ui-card__title{font-family:var(--font-display);font-size:20px}.article-summary{font-family:var(--font-display);font-size:20px;line-height:1.85;color:var(--text-primary)}.evidence-list{display:grid;gap:0;list-style:none;counter-reset:evidence}.evidence-list li{position:relative;padding:17px 12px 17px 22px;border-left:1px solid var(--border-strong);border-bottom:1px solid var(--border);background:transparent;color:var(--text-secondary);font-size:14px;line-height:1.75}.evidence-list li:before{content:"";position:absolute;left:-3px;top:24px;width:5px;height:5px;border-radius:50%;background:var(--success)}.provenance-list{display:grid;gap:13px}.provenance-row{display:grid;gap:4px;padding-bottom:10px;border-bottom:1px solid var(--border);font-size:12px}.provenance-row span{color:var(--text-muted)}.provenance-row strong{font-weight:600}.credibility-note{margin-top:14px;padding:14px;border-radius:var(--radius-sm);background:var(--bg-elevated);font-size:12px;line-height:1.7;color:var(--text-secondary)}.personal-controls{display:grid;gap:14px}.personal-controls label{display:grid;gap:7px;color:var(--text-secondary);font-size:11px}.personal-controls select,.personal-controls input{width:100%;padding:10px 11px;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--bg-primary);color:var(--text-primary);font:inherit}.reading-buttons{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}.reading-buttons button.active{border-color:var(--accent);background:var(--accent-subtle);color:var(--accent)}.related-list{display:flex;gap:7px;flex-wrap:wrap}.related-list a{text-decoration:none}.article-original{display:inline-flex}.article-error{margin-top:20px}
@media(max-width:768px){.article-head{padding-top:20px}.article-grid{grid-template-columns:1fr;gap:30px}.article-head h1{font-size:34px}.article-stack{gap:22px}}@media(max-width:480px){.article-head h1{font-size:29px;line-height:1.22}.article-summary{font-size:18px}.provenance-row{gap:3px}.reading-buttons{grid-template-columns:1fr}.article-grid{margin-top:26px}}
"""


ARTICLE_JS = r"""
const escArticle=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let currentArticle=null;
function articleId(){return decodeURIComponent(location.pathname.split('/').pop()||'')}
function personalControls(a){
  const meta=uiGetPersonalMeta('news',a.id), categories=[['',T('uncategorized')],['learning',T('category_learning')],['tools',T('category_tools')],['research',T('category_research')],['archive',T('category_archive')]];
  return '<div class="personal-controls"><label>'+T('category_label')+'<select id="personal-category" onchange="saveArticleMeta()">'+categories.map(x=>'<option value="'+x[0]+'" '+(meta.category===x[0]?'selected':'')+'>'+x[1]+'</option>').join('')+'</select></label><label>'+T('tags_edit_label')+'<input id="personal-tags" value="'+escArticle((meta.tags||[]).join(', '))+'" placeholder="Agent, 安全, 工具" onchange="saveArticleMeta()"></label><div><span class="field-label">'+T('reading_state')+'</span><div class="reading-buttons">'+['unread','read','later'].map(state=>'<button class="ui-button ui-button--small ui-button--ghost '+(meta.reading_state===state?'active':'')+'" onclick="setReadingState(\''+state+'\')">'+T('reading_'+state)+'</button>').join('')+'</div></div></div>';
}
function saveArticleMeta(){
  if(!currentArticle)return; const tags=(document.getElementById('personal-tags')?.value||'').split(/[,，]/).map(x=>x.trim()).filter(Boolean).slice(0,12);
  uiUpdatePersonalMeta('news',currentArticle.id,{category:document.getElementById('personal-category')?.value||'',tags});
}
function setReadingState(state){if(!currentArticle)return;uiUpdatePersonalMeta('news',currentArticle.id,{reading_state:state});document.getElementById('personal-root').innerHTML=personalControls(currentArticle)}
function renderArticle(a){
  currentArticle=a; const p=a.provenance||{}, title=a.title_cn||a.title, score=editorialRatingHTML(a.score||0), credibility=T('source_'+(p.credibility||'medium'));
  document.title=title+' — '+T('platform_title');
  const tags=(a.categories||[]).map(topicTagHTML).join('');
  const points=(a.summary_points||[]).map(point=>'<li>'+evidenceLabelHTML('fact')+' '+escArticle(String(point).replace(/^\s*[①②③④⑤]\s*/,''))+'</li>').join('');
  const related=(a.related_entities||[]).map(e=>'<a class="intel-topic" href="/entity/'+encodeURIComponent(e.id)+'">'+escArticle(e.name)+'</a>').join('');
  document.getElementById('article-root').innerHTML='<article class="article-shell"><header class="article-head"><div class="article-eyebrow">'+T('article_eyebrow')+'</div><h1>'+escArticle(title)+'</h1><div class="article-meta-row">'+score+sourceMetaHTML(a.source||'',String(a.published||'').slice(0,10),a.url)+'</div><div class="article-tags">'+tags+'</div><div class="article-actions">'+favoriteButtonHTML('news',a.id,title,'','/article/'+encodeURIComponent(a.id))+'<a class="ui-button ui-button--secondary article-original" href="'+escArticle(a.url)+'" target="_blank" rel="noopener">'+T('article_original')+' ↗</a></div>'+ratingHelpHTML()+'</header><div class="article-grid"><div class="article-stack"><section class="ui-card"><header class="ui-card__header"><h2 class="ui-card__title">'+T('article_summary')+' '+evidenceLabelHTML('fact')+'</h2></header><div class="ui-card__body"><p class="article-summary">'+escArticle(a.one_liner||T('no_data'))+'</p></div></section><section class="ui-card"><header class="ui-card__header"><h2 class="ui-card__title">'+T('article_evidence')+'</h2></header><div class="ui-card__body"><ol class="evidence-list">'+(points||uiStateHTML('empty',T('state_empty'),T('no_data')))+'</ol>'+(a.score_reason?'<p class="credibility-note">'+evidenceLabelHTML('analysis')+' '+escArticle(a.score_reason)+'</p>':'')+'</div></section><section class="ui-card"><header class="ui-card__header"><h2 class="ui-card__title">'+T('article_related')+'</h2></header><div class="ui-card__body related-list">'+(related||uiStateHTML('empty',T('state_empty'),T('no_data')))+'</div></section></div><aside class="article-stack"><section class="ui-card"><header class="ui-card__header"><h2 class="ui-card__title">'+T('source_credibility')+'</h2></header><div class="ui-card__body"><div class="provenance-list"><div class="provenance-row"><span>'+T('source_credibility')+'</span><strong>'+credibility+'</strong></div><div class="provenance-row"><span>'+T('published_at')+'</span><strong>'+escArticle(String(p.published_at||'').slice(0,16)||'—')+'</strong></div><div class="provenance-row"><span>'+T('collected_at')+'</span><strong>'+escArticle(String(p.collected_at||'').slice(0,16)||'—')+'</strong></div></div><p class="credibility-note">'+escArticle(p.basis||'')+'</p></div></section><section class="ui-card"><header class="ui-card__header"><h2 class="ui-card__title">'+T('reading_state')+'</h2></header><div class="ui-card__body" id="personal-root">'+personalControls(a)+'</div></section></aside></div></article>';
}
async function init(){try{const a=await apiFetch('/api/articles/'+encodeURIComponent(articleId()));renderArticle(a)}catch(error){showError('article-root',T('error_loading'),error.message)}}
init();
"""


def generate_article_page(output_dir: Optional[Path] = None, lang: str = "zh") -> Path:
    output_dir = output_dir or ROOT_DIR / "reports"
    ensure_dir(output_dir)
    path = output_dir / "article.html"
    path.write_text(render_page(PageShell(
        title_key="article_title", current_page="today", lang=lang,
        body_html='<main id="article-root">' +
                  '<div class="ui-state ui-state--loading" data-ui-state="loading" role="status">◌</div></main>',
        extra_css=ARTICLE_CSS, extra_js=ARTICLE_JS, page_kind="detail",
    )), encoding="utf-8")
    log.info("Article page (%s): %s", lang, path)
    return path
