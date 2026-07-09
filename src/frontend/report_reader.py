"""Markdown 报告的联动式阅读器。

桌面端：左侧固定目录 + 右侧正文，滚动自动高亮。
移动端：正文优先，浮层目录 + 上一篇/下一篇导航 + 阅读进度指示。
"""

from pathlib import Path
from typing import Optional

from src.engine.utils import ROOT_DIR, ensure_dir, log
from .frontend_shell import PageShell, render_page


REPORT_READER_CSS = r"""
/* ── Layout ── */
.reader-layout{display:flex;gap:28px;justify-content:center;align-items:flex-start}
.reader-sidebar{position:sticky;top:20px;z-index:10;width:200px;flex-shrink:0;max-height:calc(100vh-40px);overflow-y:auto}
.reader-sidebar-inner{display:grid;gap:4px;padding:12px 8px}
.reader-sidebar-header{font-size:11px;font-weight:700;color:var(--text-muted);letter-spacing:.08em;padding:4px 8px 8px;border-bottom:1px solid var(--border);margin-bottom:4px}
.reader-toc{display:grid;gap:2px}
.reader-toc a{display:block;padding:5px 8px;border-radius:6px;color:var(--text-secondary);font-size:12px;line-height:1.4;text-decoration:none;transition:all .12s;border-left:2px solid transparent;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.reader-toc a:hover{color:var(--accent);background:var(--accent-subtle)}
.reader-toc a.active{color:var(--accent);background:var(--accent-subtle);border-left-color:var(--accent);font-weight:600}
.reader-toc a.toc-h3{padding-left:20px;font-size:11px;color:var(--text-muted)}
.reader-toc a.toc-h3.active{color:var(--accent)}
.reader-content{flex:1;min-width:0;max-width:760px}

/* ── Reader head ── */
.reader-head{margin-bottom:22px;padding-bottom:18px;border-bottom:1px solid var(--border)}
.reader-eyebrow{color:var(--accent);font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase}
.reader-head h1{margin:8px 0 12px;font-size:30px}
.reader-actions{display:flex;gap:8px;flex-wrap:wrap}

/* ── Markdown body ── */
.markdown-body{font-size:14px;line-height:1.85;color:var(--text-secondary);scroll-behavior:smooth;word-break:break-word;overflow-wrap:break-word}
.markdown-body h1,.markdown-body h2,.markdown-body h3{scroll-margin-top:80px;color:var(--text-primary);line-height:1.35}
.markdown-body h1{margin:32px 0 14px;font-size:26px}
.markdown-body h2{margin:28px 0 8px;padding-bottom:7px;border-bottom:1px solid var(--border);font-size:20px}
.markdown-body h3{margin:22px 0 9px;font-size:16px}
.markdown-body p{margin:10px 0}
.markdown-body ul{margin:10px 0;padding-left:22px}
.markdown-body li{margin:5px 0}
.markdown-body a{color:var(--accent)}
.markdown-body code{padding:2px 5px;border-radius:4px;background:var(--bg-elevated);font-size:.9em;word-break:break-all}

/* ── Article action buttons ── */
.ra-actions{display:flex;gap:8px;margin:8px 0 14px;flex-wrap:wrap}
.ra-btn{display:inline-flex;min-height:30px;align-items:center;gap:4px;padding:4px 9px;border:1px solid var(--border);border-radius:999px;background:transparent;color:var(--text-muted);font-size:10px;cursor:pointer;transition:all .15s;line-height:1.5;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ra-btn:hover{border-color:var(--accent);color:var(--accent)}
.ra-btn.done{border-color:var(--success);color:var(--success)}

/* ── Mobile TOC: inline button in header ── */
.reader-toc-btn{display:none;align-items:center;gap:3px;padding:3px 8px;border:1px solid var(--border);border-radius:4px;background:transparent;color:var(--text-secondary);font:inherit;font-size:10px;line-height:1.4;cursor:pointer;transition:all .15s}
.reader-toc-btn:hover{border-color:var(--accent);color:var(--accent)}
.reader-toc-btn .toc-progress{display:inline-block;width:24px;height:2px;background:var(--bg-elevated);border-radius:1px;margin-left:4px;vertical-align:middle;overflow:hidden}
.reader-toc-btn .toc-progress span{display:block;height:100%;background:var(--accent);border-radius:1px;width:0%;transition:width .2s}
.reader-toc-btn .toc-count{color:var(--text-muted);font-size:9px;margin-left:2px}
/* ── Mobile position indicator below heading ── */
.reader-position{display:none;font-size:10px;color:var(--text-muted);padding:6px 0 0;border-top:1px solid var(--border);margin-top:8px}
.reader-position span{color:var(--text-secondary);font-weight:500}
/* ── Mobile TOC overlay ── */
.reader-toc-overlay{display:none;position:fixed;top:0;left:0;right:0;bottom:0;z-index:200;background:var(--bg-primary);overflow-y:auto;animation:fadeIn .2s ease-out}
.reader-toc-overlay.open{display:block}
.reader-toc-overlay-header{display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid var(--border);position:sticky;top:0;background:var(--bg-primary);z-index:10}
.reader-toc-overlay-header span{font-size:14px;font-weight:700;color:var(--text-primary)}
.reader-toc-current{display:block;font-size:11px;font-weight:400;color:var(--text-muted);margin-top:2px}
.reader-toc-current em{font-style:normal;color:var(--text-secondary)}
.reader-toc-close{width:36px;height:36px;border:none;background:var(--bg-elevated);border-radius:50%;color:var(--text-secondary);font-size:18px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background .15s}
.reader-toc-close:hover{background:var(--border);color:var(--text-primary)}
.reader-toc-overlay-body{padding:8px 20px 24px}
.reader-toc-overlay-body .reader-toc a{padding:10px 8px;font-size:14px;border-radius:8px}
.reader-toc-overlay-body .reader-toc a.toc-h3{padding-left:24px;font-size:13px}
.reader-toc-overlay-body .reader-toc a.active{background:var(--accent-subtle);font-weight:700}
/* ── TOC scroll progress bar ── */
.reader-progress-track{position:fixed;top:0;left:0;width:100%;height:3px;z-index:300;pointer-events:none}
.reader-progress-track span{display:block;height:100%;background:var(--accent);width:0%;transition:width .1s ease-out}

/* ── Prev/Next navigation ── */
.reader-nav{display:flex;gap:12px;justify-content:space-between;margin-top:32px;padding-top:20px;border-top:1px solid var(--border)}
.reader-nav-btn{display:inline-flex;align-items:center;gap:4px;padding:8px 14px;border:1px solid var(--border);border-radius:8px;background:var(--bg-elevated);color:var(--text-secondary);font-size:12px;cursor:pointer;transition:all .15s;text-decoration:none;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:200px}
.reader-nav-btn:hover{border-color:var(--accent);color:var(--accent);background:var(--accent-subtle)}
.reader-nav-btn:disabled{opacity:.35;cursor:default;pointer-events:none}
.reader-nav-btn.prev{text-align:left}
.reader-nav-btn.next{text-align:right;margin-left:auto}

/* ── Responsive ── */
@media(min-width:900px){
  .reader-sidebar{display:block!important}
}
@media(max-width:899px){
  .reader-layout{flex-direction:column}
  .reader-sidebar{display:none}
  .reader-toc-btn{display:inline-flex}
  .reader-position{display:block}
  .reader-head h1{font-size:24px}
  .markdown-body{font-size:13px}
  .markdown-body h1{font-size:22px}
  .markdown-body h2{font-size:18px}
}
@media(max-width:480px){
  .reader-head h1{font-size:20px}
  .reader-toc-overlay-body{padding:8px 14px 20px}
  .reader-toc-overlay-body .reader-toc a{padding:8px 6px;font-size:13px}
}
"""


REPORT_READER_JS = r"""
const escReport=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function reportFilename(){return decodeURIComponent(location.pathname.split('/').pop()||'')}

function inlineMarkdown(text){
  let value=escReport(text); value=value.replace(/`([^`]+)`/g,'<code>$1</code>');
  value=value.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g,'<a href="$2" target="_blank" rel="noopener">$1</a>');
  value=value.replace(/\[([^\]]+)\]\((\/[^)]+)\)/g,'<a href="$2">$1</a>');
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

/* ── Article action buttons (favorites/read/later) ── */
function raBtn(articleId,kind){var meta=uiGetPersonalMeta('news',articleId),active=false;if(kind==='read')active=meta.reading_state==='read';if(kind==='later')active=meta.reading_state==='later';if(kind==='fav')active=uiFavoriteStore().some(function(s){return uiFavoriteKey(s)===uiFavoriteKey({type:'news',id:articleId})});var icons={fav:'★',read:'✓',later:'↳'};var labels={fav:T(active?'favorited':'favorite'),read:T('reading_read'),later:T('reading_later')};return'<button class="ra-btn'+(active?' done':'')+'" data-id="'+articleId+'" data-kind="'+kind+'" onclick="raDoAction(this.dataset.id,this.dataset.kind,this)">'+icons[kind]+' '+labels[kind]+'</button>'}
function raDoAction(articleId,kind,btn){var group=btn.closest('.ra-actions'),title=group?group.dataset.title:articleId,href=group?group.dataset.href:'/article/'+encodeURIComponent(articleId);if(kind==='fav'){var added=uiToggleFavorite({type:'news',id:articleId,title:title,href:href},null);btn.classList.toggle('done',added);btn.innerHTML='★ '+T(added?'favorited':'favorite');return}uiUpdatePersonalMeta('news',articleId,{reading_state:kind,title:title,href:href});if(group)group.innerHTML=raBtn(articleId,'fav')+raBtn(articleId,'read')+raBtn(articleId,'later')}
function injectArticleActions(){var filename=reportFilename();document.querySelectorAll('.markdown-body h2').forEach(function(heading){if(heading.nextElementSibling&&heading.nextElementSibling.classList.contains('ra-actions'))return;var node=heading.nextElementSibling,link=null;while(node&&node.tagName!=='H2'&&node.tagName!=='H1'){link=link||node.querySelector?.('a[href^="/article/"]');node=node.nextElementSibling}var title=heading.textContent.replace(/^★+\s*/, '').trim(),id=link?decodeURIComponent(link.getAttribute('href').replace('/article/','')):'report-entry:'+filename+':'+heading.id,href=link?link.getAttribute('href'):'/report/'+encodeURIComponent(filename)+'#'+heading.id;var actions=document.createElement('div');actions.className='ra-actions';actions.dataset.title=title;actions.dataset.href=href;actions.innerHTML=raBtn(id,'fav')+raBtn(id,'read')+raBtn(id,'later');heading.insertAdjacentElement('afterend',actions)})}

/* ── Scroll-spy + reading progress ── */
let _readerObserver=null, _readerTocEntries=[], _readerTotalSections=0;

function _updateReaderProgress(id,label){
  var posLabel=document.getElementById('reader-pos-label');
  if(posLabel&&label)posLabel.textContent=label;
  var tocName=document.getElementById('toc-current-name');
  if(tocName&&label)tocName.innerHTML=label;
  var idx=_readerTocEntries.findIndex(function(e){return e.id===id});
  if(idx>=0&&_readerTotalSections>0){
    var pct=Math.round((idx+1)/_readerTotalSections*100);
    var bar=document.getElementById('toc-progress-bar');
    if(bar)bar.style.width=pct+'%';
    var topBar=document.querySelector('#reader-progress span');
    if(topBar)topBar.style.width=pct+'%';
  }
}

function _activateTocItem(id){
  document.querySelectorAll('.reader-toc a').forEach(function(a){a.classList.remove('active')});
  var link=document.querySelector('.reader-toc a[href="#'+id+'"]');
  if(link)link.classList.add('active');
  var entry=_readerTocEntries.find(function(e){return e.id===id});
  if(entry)_updateReaderProgress(id,entry.label);
}

function buildToc(toc){
  _readerTocEntries=toc.filter(function(e){return e.level>1});
  _readerTotalSections=_readerTocEntries.length;
  var container=document.getElementById('reader-toc-list');
  if(!container)return;
  container.innerHTML=_readerTocEntries.map(function(e,i){
    return '<a href="#'+e.id+'" data-toc-idx="'+i+'" class="'+(e.level===3?'toc-h3':'')+'">'+escReport(e.label)+'</a>';
  }).join('');
  setupScrollSpy();
}

function setupScrollSpy(){
  if(_readerObserver)_readerObserver.disconnect();
  var headings=[].slice.call(document.querySelectorAll('.markdown-body h2,.markdown-body h3'));
  if(!headings.length)return;
  _readerObserver=new IntersectionObserver(function(entries){
    var visible=entries.filter(function(e){return e.isIntersecting}).sort(function(a,b){return a.boundingClientRect.top-b.boundingClientRect.top});
    if(!visible.length)return;
    var best=visible[0];
    var entry=_readerTocEntries.find(function(t){return t.id===best.target.id});
    if(!entry){
      var allIds={}; _readerTocEntries.forEach(function(t){allIds[t.id]=true});
      var prevBest=best.target.previousElementSibling;
      while(prevBest&&!allIds[prevBest.id])prevBest=prevBest.previousElementSibling;
      if(prevBest&&allIds[prevBest.id])entry=_readerTocEntries.find(function(t){return t.id===prevBest.id});
    }
    if(entry)_activateTocItem(entry.id);
  },{rootMargin:'-80px 0px -65% 0px'});
  headings.forEach(function(h){_readerObserver.observe(h)});
}

function scrollToSection(id){
  var el=document.getElementById(id);
  if(!el)return;
  el.scrollIntoView({behavior:'smooth',block:'start'});
  window.setTimeout(function(){_activateTocItem(id)},100);
  closeTocOverlay();
}

/* ── Mobile TOC overlay ── */
function openTocOverlay(){
  var overlay=document.getElementById('reader-toc-overlay');
  if(overlay)overlay.classList.add('open');
  var activeLink=document.querySelector('.reader-toc a.active');
  if(activeLink&&overlay){
    var overlayLink=overlay.querySelector('.reader-toc a[href="'+activeLink.getAttribute('href')+'"]');
    if(overlayLink)overlayLink.scrollIntoView({block:'center'});
  }
}
function closeTocOverlay(){
  var overlay=document.getElementById('reader-toc-overlay');
  if(overlay)overlay.classList.remove('open');
}

/* ── Prev/Next article navigation ── */
function _getArticleTocEntries(){
  return _readerTocEntries.filter(function(e){return e.level===2});
}
function _currentArticleIndex(){
  var articles=_getArticleTocEntries(), activeLink=document.querySelector('.reader-toc a.active');
  if(!activeLink||!articles.length)return -1;
  var idx=parseInt(activeLink.getAttribute('data-toc-idx'),10);
  if(idx<0)return -1;
  var entry=_readerTocEntries[idx];
  if(!entry)return -1;
  var articleIdx=-1;
  for(var i=0;i<articles.length;i++){
    var aIdx=_readerTocEntries.indexOf(articles[i]);
    if(aIdx<=idx)articleIdx=i;
  }
  return articleIdx;
}
function goToPrevArticle(){
  var articles=_getArticleTocEntries(), cur=_currentArticleIndex();
  if(cur<=0)return;
  var prev=articles[cur-1];
  if(prev){scrollToSection(prev.id);_updateNavButtons()}
}
function goToNextArticle(){
  var articles=_getArticleTocEntries(), cur=_currentArticleIndex();
  if(cur<0)cur=0;
  if(cur>=articles.length-1)return;
  var next=articles[cur+1];
  if(next){scrollToSection(next.id);_updateNavButtons()}
}
function _updateNavButtons(){
  var articles=_getArticleTocEntries(), cur=_currentArticleIndex();
  var prevBtns=[].slice.call(document.querySelectorAll('.reader-nav-btn.prev'));
  var nextBtns=[].slice.call(document.querySelectorAll('.reader-nav-btn.next'));
  prevBtns.forEach(function(b){b.disabled=cur<=0});
  nextBtns.forEach(function(b){b.disabled=cur<0||cur>=articles.length-1});
  if(cur>=0){
    prevBtns.forEach(function(b){b.innerHTML=(cur>0?'← '+escReport(articles[cur-1].label):T('reader_no_more_articles'))});
    nextBtns.forEach(function(b){b.innerHTML=(cur<articles.length-1?escReport(articles[cur+1].label)+' →':T('reader_no_more_articles'))});
  }
}
function _buildNavHTML(i,articles){
  if(!articles||!articles.length)return'';
  var prev=articles[i-1],next=articles[i+1];
  var prevLabel=prev?'← '+escReport(prev.label):'',
      nextLabel=next?escReport(next.label)+' →':'';
  return '<div class="reader-nav"><button class="reader-nav-btn prev" onclick="goToPrevArticle()"'+(prev?'':' disabled')+'>'+(prevLabel||T('reader_no_more_articles'))+'</button><button class="reader-nav-btn next" onclick="goToNextArticle()"'+(next?'':' disabled')+'>'+(nextLabel||T('reader_no_more_articles'))+'</button></div>';
}

/* ── Init ── */
async function init(){
  try{
    const filename=reportFilename(),
          data=await apiFetch('/api/report-content/'+encodeURIComponent(filename)),
          rendered=renderMarkdown(data.content);
    var levelOne=rendered.toc.find(function(x){return x.level===1}),
        firstLine=String(data.content||'').split(/\r?\n/).find(function(l){return l.trim()}),
        title=(levelOne&&levelOne.label)||(firstLine&&firstLine.replace(/^[#\s]+/,''))||filename.replace(/\.md$/,'');
    document.title=title+' — '+T('platform_title');

    var articleEntries=rendered.toc.filter(function(e){return e.level===2});
    var sidebarTocLinks=rendered.toc.filter(function(e){return e.level>1}).map(function(e,i){
      return '<a href="#'+e.id+'" data-toc-idx="'+i+'" class="'+(e.level===3?'toc-h3':'')+'">'+escReport(e.label)+'</a>';
    }).join('');
    var sectionCount=rendered.toc.filter(function(e){return e.level>1}).length;

    // Sidebar (desktop)
    var sidebarHTML='<aside class="reader-sidebar" id="reader-sidebar"><div class="reader-sidebar-inner"><div class="reader-sidebar-header">'+T('report_toc')+'</div><nav class="reader-toc" id="reader-toc-list">'+sidebarTocLinks+'</nav></div></aside>';

    // TOC button (mobile, in header actions row)
    var tocBtnHTML='<button class="reader-toc-btn" id="reader-toc-btn" onclick="openTocOverlay()">'+T('reader_toc_toggle')+' <span class="toc-count">'+sectionCount+'</span><span class="toc-progress"><span id="toc-progress-bar"></span></span></button>';
    // Position indicator (mobile, below header)
    var posHTML='<div class="reader-position" id="reader-position">'+T('reader_toc_toggle')+': <span id="reader-pos-label">—</span></div>';

    var contentHTML='<article class="reader-content" id="reader-content"><header class="reader-head"><div class="reader-eyebrow">'+T('report_reader_eyebrow')+'</div><h1>'+escReport(title)+'</h1><div class="reader-actions">'+favoriteButtonHTML('report',filename,title,'','/report/'+encodeURIComponent(filename))+tocBtnHTML+'</div>'+posHTML+'</header><div class="markdown-body">'+rendered.html+'</div>'+_buildNavHTML(0,articleEntries)+'</article>';

    // TOC overlay (mobile) — shows current section
    var overlayCurrent=sectionCount?'<span class="reader-toc-current" id="toc-current-label">'+T('reader_toc_toggle')+': <em id="toc-current-name"></em></span>':'';
    var overlayHTML='<div class="reader-toc-overlay" id="reader-toc-overlay"><div class="reader-toc-overlay-header"><span>'+T('report_toc')+overlayCurrent+'</span><button class="reader-toc-close" onclick="closeTocOverlay()">✕</button></div><div class="reader-toc-overlay-body"><nav class="reader-toc" id="reader-toc-overlay-list">'+sidebarTocLinks+'</nav></div></div>';

    // Progress bar (fixed top of page)
    var progressHTML='<div class="reader-progress-track" id="reader-progress"><span></span></div>';

    document.getElementById('reader-root').innerHTML='<div class="reader-layout">'+sidebarHTML+contentHTML+'</div>'+overlayHTML+progressHTML;

    // Wire up TOC link clicks
    document.getElementById('reader-toc-overlay-list').addEventListener('click',function(e){
      var link=e.target.closest('a[href^="#"]');
      if(!link)return;
      e.preventDefault();
      var id=link.getAttribute('href').slice(1);
      scrollToSection(id);
      _updateNavButtons();
    });
    document.getElementById('reader-toc-list').addEventListener('click',function(e){
      var link=e.target.closest('a[href^="#"]');
      if(!link)return;
      e.preventDefault();
      var id=link.getAttribute('href').slice(1);
      scrollToSection(id);
      _updateNavButtons();
    });

    buildToc(rendered.toc);

    var overlayList=document.getElementById('reader-toc-overlay-list');
    if(overlayList)overlayList.innerHTML=_readerTocEntries.map(function(e,i){
      return '<a href="#'+e.id+'" data-toc-idx="'+i+'" class="'+(e.level===3?'toc-h3':'')+'">'+escReport(e.label)+'</a>';
    }).join('');

    injectArticleActions();
    window.setTimeout(_updateNavButtons,200);

  }catch(error){
    showError('reader-root',T('error_loading'),error.message);
  }
}
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
