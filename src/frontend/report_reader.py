"""Markdown 报告的站内阅读页。"""
from pathlib import Path
from typing import Optional

from src.engine.utils import ROOT_DIR, ensure_dir, log
from .frontend_shell import PageShell, render_page


REPORT_READER_CSS = """\
.reader-layout{display:grid;grid-template-columns:minmax(0,760px) 240px;gap:28px;justify-content:center;align-items:start}.reader-head{margin-bottom:22px;padding-bottom:18px;border-bottom:1px solid var(--border)}.reader-eyebrow{color:var(--accent);font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase}.reader-head h1{margin:8px 0 12px;font-size:30px}.reader-actions{display:flex;gap:8px;flex-wrap:wrap}.markdown-body{font-size:14px;line-height:1.85;color:var(--text-secondary)}.markdown-body h1,.markdown-body h2,.markdown-body h3{scroll-margin-top:24px;color:var(--text-primary);line-height:1.35}.markdown-body h1{margin:32px 0 14px;font-size:26px}.markdown-body h2{margin:28px 0 12px;padding-bottom:7px;border-bottom:1px solid var(--border);font-size:20px}.markdown-body h3{margin:22px 0 9px;font-size:16px}.markdown-body p{margin:10px 0}.markdown-body ul{margin:10px 0;padding-left:22px}.markdown-body li{margin:5px 0}.markdown-body a{color:var(--accent)}.markdown-body code{padding:2px 5px;border-radius:4px;background:var(--bg-elevated);font-size:.9em}.reader-aside{position:sticky;top:20px}.reader-toc{display:grid;gap:7px}.reader-toc a{color:var(--text-secondary);font-size:11px;text-decoration:none}.reader-toc a:hover{color:var(--accent)}.reader-state{display:grid;gap:7px;margin-top:16px}.reader-state button.active{border-color:var(--accent);background:var(--accent-subtle);color:var(--accent)}
@media(max-width:900px){.reader-layout{grid-template-columns:1fr}.reader-aside{position:static;order:-1}}@media(max-width:480px){.reader-head h1{font-size:22px}.markdown-body{font-size:13px}}
"""


REPORT_READER_JS = r"""
const escReport=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function reportFilename(){return decodeURIComponent(location.pathname.split('/').pop()||'')}
function inlineMarkdown(text){
  let value=escReport(text); value=value.replace(/`([^`]+)`/g,'<code>$1</code>');
  value=value.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g,'<a href="$2" target="_blank" rel="noopener">$1</a>');
  value=value.replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>'); return value;
}
function renderMarkdown(markdown){
  const lines=String(markdown||'').split(/\r?\n/), html=[], toc=[]; let inList=false;
  lines.forEach(line=>{const heading=line.match(/^(#{1,3})\s+(.+)$/), list=line.match(/^[-*]\s+(.+)$/);
    if(heading){if(inList){html.push('</ul>');inList=false}const level=heading[1].length,id='section-'+toc.length,label=heading[2].replace(/[*`]/g,'');toc.push({id,label,level});html.push('<h'+level+' id="'+id+'">'+inlineMarkdown(heading[2])+'</h'+level+'>')}
    else if(list){if(!inList){html.push('<ul>');inList=true}html.push('<li>'+inlineMarkdown(list[1])+'</li>')}
    else{if(inList){html.push('</ul>');inList=false}if(line.trim())html.push('<p>'+inlineMarkdown(line)+'</p>')}
  }); if(inList)html.push('</ul>'); return {html:html.join(''),toc};
}
function setReportState(state){const filename=reportFilename();uiUpdatePersonalMeta('report',filename,{reading_state:state});renderReportState(filename)}
function renderReportState(filename){const meta=uiGetPersonalMeta('report',filename);document.getElementById('reader-state').innerHTML=['unread','read','later'].map(state=>'<button class="ui-button ui-button--small ui-button--ghost '+(meta.reading_state===state?'active':'')+'" onclick="setReportState(\''+state+'\')">'+T('reading_'+state)+'</button>').join('')}
async function init(){try{const filename=reportFilename(),data=await apiFetch('/api/report-content/'+encodeURIComponent(filename)), rendered=renderMarkdown(data.content),title=rendered.toc[0]?.label||filename.replace(/\.md$/,'');document.title=title+' — '+T('platform_title');document.getElementById('reader-root').innerHTML='<div class="reader-layout"><article><header class="reader-head"><div class="reader-eyebrow">'+T('report_reader_eyebrow')+'</div><h1>'+escReport(title)+'</h1><div class="reader-actions">'+favoriteButtonHTML('report',filename,title,'','/report/'+encodeURIComponent(filename))+'</div></header><div class="markdown-body">'+rendered.html+'</div></article><aside class="reader-aside ui-card"><header class="ui-card__header"><h2 class="ui-card__title">'+T('report_toc')+'</h2></header><div class="ui-card__body"><nav class="reader-toc">'+rendered.toc.filter(x=>x.level>1).map(x=>'<a href="#'+x.id+'">'+escReport(x.label)+'</a>').join('')+'</nav><div class="reader-state" id="reader-state"></div></div></aside></div>';renderReportState(filename)}catch(error){showError('reader-root',T('error_loading'),error.message)}}
init();
"""


def generate_report_reader(output_dir: Optional[Path] = None, lang: str = "zh") -> Path:
    output_dir = output_dir or ROOT_DIR / "reports"
    ensure_dir(output_dir)
    path = output_dir / "report-reader.html"
    html = render_page(PageShell(
        title_key="report_reader_title", current_page="research", lang=lang,
        body_html='<main id="reader-root"><div class="ui-state ui-state--loading" data-ui-state="loading">◌</div></main>',
        extra_css=REPORT_READER_CSS, extra_js=REPORT_READER_JS, page_kind="detail",
    ))
    path.write_text(html, encoding="utf-8")
    log.info("Report reader (%s): %s", lang, path)
    return path
