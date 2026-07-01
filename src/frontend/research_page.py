"""Research Assistant 工作台页面生成器。"""
from pathlib import Path
from typing import Optional

from .frontend_components import button, card, page_header
from .frontend_shell import PageShell, render_page
from src.interfaces.i18n import t
from src.engine.utils import ROOT_DIR, ensure_dir, log


RESEARCH_CSS = """\
.research-layout{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(280px,.6fr);gap:16px;align-items:start}.research-form{display:flex;flex-direction:column;gap:16px}.field-label{display:block;margin-bottom:7px;color:var(--text-secondary);font-size:12px;font-weight:650}.research-input,.depth-select{width:100%;padding:12px 14px;background:var(--bg-primary);border:1px solid var(--border);border-radius:var(--radius-sm);color:var(--text-primary);font:inherit}.research-input{font-size:15px}.research-input:focus,.depth-select:focus{outline:2px solid var(--accent-subtle);border-color:var(--accent)}.form-actions{display:flex;gap:10px;align-items:end}.depth-field{flex:1}.research-submit{min-width:130px}.research-status{min-height:18px;color:var(--text-secondary);font-size:11px}
.research-guide{display:grid;gap:16px}.process-step{display:grid;grid-template-columns:30px 1fr;gap:10px;align-items:start}.process-step__index{display:grid;width:28px;height:28px;place-items:center;border-radius:50%;background:var(--accent-subtle);color:var(--accent);font-size:11px;font-weight:750}.process-step strong{display:block;margin-bottom:3px;color:var(--text-primary);font-size:12px}.process-step p,.scope-note{color:var(--text-secondary);font-size:11px;line-height:1.55}.scope-note{padding:12px;border-left:2px solid var(--warning);background:var(--bg-elevated);border-radius:0 var(--radius-sm) var(--radius-sm) 0}
.output-stage{margin-top:24px}.output-placeholder{padding:54px 20px;text-align:center;border:1px dashed var(--border);border-radius:var(--radius);color:var(--text-secondary)}.output-placeholder__icon{margin-bottom:10px;font-size:30px}.output-placeholder h2{margin-bottom:6px;color:var(--text-primary);font-size:16px}.output-placeholder p{font-size:12px}.research-progress{display:none}.research-progress.visible{display:block}.progress-copy{margin-bottom:16px;color:var(--text-secondary);font-size:12px}.progress-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.progress-step{padding:14px;background:var(--bg-elevated);border-radius:var(--radius-sm)}.progress-step strong{display:block;margin-bottom:8px;font-size:11px;color:var(--text-primary)}
.report-container{display:none}.report-container.visible{display:block;animation:fadeIn .35s ease-out}.report-header{display:flex;justify-content:space-between;gap:20px;align-items:flex-end;margin-bottom:18px}.report-title{font-size:22px;color:var(--text-primary)}.report-meta{margin-top:5px;color:var(--text-muted);font-size:11px}.report-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.report-section{padding:20px;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius)}.report-section--wide{grid-column:1/-1}.report-section h2{margin-bottom:12px;color:var(--text-primary);font-size:15px}.summary-text{color:var(--text-secondary);font-size:13px;line-height:1.8;white-space:pre-wrap}.finding-card{padding:14px 0;border-bottom:1px solid var(--border)}.finding-card:last-child{border-bottom:0}.finding-title{color:var(--text-primary);font-size:13px;font-weight:650}.finding-elab{margin-top:6px;color:var(--text-secondary);font-size:12px;line-height:1.65}.finding-sources,.entity-list{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}.report-chip{display:inline-flex;padding:3px 8px;border-radius:999px;background:var(--bg-elevated);color:var(--text-secondary);font-size:10px}.report-chip--high{color:var(--danger)}.report-chip--medium{color:var(--warning)}.connection{padding:10px 0;border-bottom:1px solid var(--border)}.connection:last-child{border-bottom:0}.connection strong{color:var(--accent);font-size:12px}.connection p,.reading-item p{margin-top:3px;color:var(--text-muted);font-size:11px}.timeline-item{display:grid;grid-template-columns:78px 1fr;gap:12px;padding:9px 0}.timeline-date{color:var(--accent);font-size:11px;font-weight:700}.timeline-event{font-size:12px}.timeline-significance{margin-top:3px;color:var(--text-secondary);font-size:11px}.reading-item{padding:9px 0;border-bottom:1px solid var(--border)}.reading-item:last-child{border-bottom:0}.reading-item strong{color:var(--text-primary);font-size:12px}.error-box{margin-top:16px;padding:14px;border:1px solid var(--danger);border-radius:var(--radius);background:color-mix(in srgb,var(--danger) 10%,transparent);color:var(--danger);font-size:12px}
@media(max-width:768px){.research-layout,.report-grid{grid-template-columns:1fr}.form-actions{align-items:stretch;flex-direction:column}.research-submit,.research-submit .ui-button{width:100%}.progress-grid{grid-template-columns:1fr}.report-header{align-items:flex-start;flex-direction:column}}@media(max-width:480px){.timeline-item{grid-template-columns:1fr;gap:3px}.report-section{padding:15px}}
"""


RESEARCH_JS = r"""
let lastResearchReport = null, currentResearchState = 'idle';
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const list = value => Array.isArray(value) ? value : [];

function updateResearchI18n() {
  applyI18n();
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => { el.placeholder = T(el.dataset.i18nPlaceholder); });
  const status = document.getElementById('research-status');
  if (currentResearchState === 'loading') status.textContent = T('research_generating');
  if (currentResearchState === 'done') status.textContent = T('research_done');
  if (lastResearchReport) renderResearchReport(lastResearchReport);
}

function setResearchState(state, message) {
  currentResearchState = state;
  const progress = document.getElementById('research-progress');
  const placeholder = document.getElementById('output-placeholder');
  const report = document.getElementById('report-container');
  progress.classList.toggle('visible', state === 'loading');
  placeholder.hidden = state !== 'idle';
  report.classList.toggle('visible', state === 'done');
  document.getElementById('research-status').textContent = message || '';
}

function showResearchError(message) {
  const area = document.getElementById('error-area');
  area.innerHTML = '<div class="error-box" role="alert">' + esc(message) + '</div>';
}

async function startResearch() {
  const topic = document.getElementById('research-topic').value.trim();
  const button = document.getElementById('research-btn');
  if (!topic) { showResearchError(T('research_topic_required')); document.getElementById('research-topic').focus(); return; }
  document.getElementById('error-area').innerHTML = '';
  setResearchState('loading', T('research_generating'));
  uiSetBusy(button, true, T('research_generating_short'));
  try {
    const data = await apiFetch('/api/research', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({topic, depth:document.getElementById('research-depth').value, lang:localStorage.getItem('lang') || 'zh'})});
    if (data.error) throw new Error(data.error);
    lastResearchReport = data.report || {};
    renderResearchReport(lastResearchReport);
    setResearchState('done', T('research_done'));
    uiAnnounce(T('research_done'));
  } catch (error) {
    setResearchState('idle', '');
    showResearchError(error.message || T('research_ai_error'));
  } finally { uiSetBusy(button, false); }
}

function renderResearchReport(report) {
  const meta = report._meta || {}, entities = list(report._entities);
  document.getElementById('report-header').innerHTML = '<div><div class="ui-page-header__eyebrow">'+esc(T('research_report_label'))+'</div><h2 class="report-title">'+esc(meta.topic || T('research_title'))+'</h2><p class="report-meta">'+esc(T('entities_label'))+': '+esc(meta.entity_count || 0)+' · '+esc(T('articles_label'))+': '+esc(meta.article_count || 0)+' · '+esc(T('depth'))+': '+esc(meta.depth || 'standard')+'</p></div>';
  let html = '';
  if (report.summary) html += sectionHtml('research_summary', '<div class="summary-text">'+esc(report.summary)+'</div>', true);
  if (list(report.key_findings).length) {
    const findings = report.key_findings.map(f => '<article class="finding-card"><div class="finding-title"><span class="report-chip report-chip--'+(f.importance==='high'?'high':'medium')+'">'+esc(f.importance || '')+'</span> '+esc(f.finding || '')+'</div>'+(f.elaboration?'<p class="finding-elab">'+esc(f.elaboration)+'</p>':'')+'<div class="finding-sources">'+list(f.card_ids).map(id=>'<span class="report-chip">📋 '+esc(id)+'</span>').join('')+list(f.article_ids).map(id=>'<span class="report-chip">📄 '+esc(id)+'</span>').join('')+'</div></article>').join('');
    html += sectionHtml('research_key_findings', findings, true);
  }
  if (list(report.card_connections).length) html += sectionHtml('research_cards', report.card_connections.map(c=>'<div class="connection"><strong>'+esc(c.card_name || c.card_id || '')+'</strong>'+(c.relevance?'<p>'+esc(c.relevance)+'</p>':'')+'</div>').join(''));
  if (list(report.timeline).length) html += sectionHtml('research_timeline', report.timeline.map(item=>'<div class="timeline-item"><div class="timeline-date">'+esc(item.date || '')+'</div><div><div class="timeline-event">'+esc(item.event || '')+'</div>'+(item.significance?'<p class="timeline-significance">'+esc(item.significance)+'</p>':'')+'</div></div>').join(''));
  if (list(report.further_reading).length) html += sectionHtml('research_further', report.further_reading.map(item=>'<div class="reading-item"><strong>'+esc(item.topic || '')+'</strong>'+(item.why?'<p>'+esc(item.why)+'</p>':'')+'</div>').join(''));
  if (entities.length) html += sectionHtml('research_ref_entities', '<div class="entity-list">'+entities.map(e=>'<a class="report-chip" href="/entity/'+encodeURIComponent(e.id || '')+'">'+esc(e.name || e.id)+' · '+esc(TLbl(e.type))+'</a>').join('')+'</div>');
  document.getElementById('report-body').innerHTML = html || '<div class="output-placeholder"><p>'+esc(T('no_data'))+'</p></div>';
}

function sectionHtml(key, content, wide) { return '<section class="report-section'+(wide?' report-section--wide':'')+'"><h2>'+esc(T(key))+'</h2>'+content+'</section>'; }
function init() { updateResearchI18n(); }
document.getElementById('research-topic').addEventListener('keydown', event => { if (event.key === 'Enter') startResearch(); });
init();
"""


def generate_research_page(output_dir: Optional[Path] = None, lang: str = "zh") -> Path:
    output_dir = output_dir or ROOT_DIR / "reports"
    ensure_dir(output_dir)
    path = output_dir / "research.html"
    path.write_text(_build_html(lang), encoding="utf-8")
    log.info("Research page (%s): %s", lang, path)
    return path


def _build_html(lang: str = "zh") -> str:
    header = page_header(
        t("research_title", lang), summary=t("research_subtitle", lang),
        eyebrow=t("research_eyebrow", lang), title_key="research_title",
        summary_key="research_subtitle", eyebrow_key="research_eyebrow",
    )
    submit = button(t("research_start", lang), attrs={"id": "research-btn", "type": "submit", "data_i18n": "research_start"})
    form = f'''<form class="research-form" onsubmit="event.preventDefault();startResearch()">
<div><label class="field-label" for="research-topic" data-i18n="research_topic_label">{t("research_topic_label", lang)}</label><input class="research-input" id="research-topic" type="text" autocomplete="off" data-i18n-placeholder="research_placeholder" placeholder="{t("research_placeholder", lang)}"></div>
<div class="form-actions"><div class="depth-field"><label class="field-label" for="research-depth" data-i18n="research_depth_label">{t("research_depth_label", lang)}</label><select class="depth-select" id="research-depth"><option value="standard" data-i18n="research_depth_standard">{t("research_depth_standard", lang)}</option><option value="deep" data-i18n="research_depth_deep">{t("research_depth_deep", lang)}</option></select></div><div class="research-submit">{submit}</div></div>
<p class="research-status" id="research-status" aria-live="polite"></p></form>'''
    guide = ''.join(
        f'<div class="process-step"><span class="process-step__index">{index}</span><div><strong data-i18n="{key}">{t(key, lang)}</strong><p data-i18n="{key}_desc">{t(key + "_desc", lang)}</p></div></div>'
        for index, key in enumerate(("research_step_retrieve", "research_step_analyze", "research_step_synthesize"), 1)
    ) + f'<p class="scope-note" data-i18n="research_scope_note">{t("research_scope_note", lang)}</p>'
    brief_card = card(form, title=t("research_brief_title", lang), title_key="research_brief_title")
    guide_card = card(f'<div class="research-guide">{guide}</div>', title=t("research_process_title", lang), title_key="research_process_title")
    output = f'''<section class="output-stage" aria-live="polite"><div id="output-placeholder" class="output-placeholder"><div class="output-placeholder__icon">⌁</div><h2 data-i18n="research_output_title">{t("research_output_title", lang)}</h2><p data-i18n="research_output_desc">{t("research_output_desc", lang)}</p></div>
<div id="research-progress" class="research-progress ui-card"><div class="ui-card__body"><p class="progress-copy" data-i18n="research_generating">{t("research_generating", lang)}</p><div class="progress-grid">{''.join(f'<div class="progress-step"><strong data-i18n="{key}">{t(key, lang)}</strong><div class="skeleton skeleton-text"></div><div class="skeleton skeleton-text"></div></div>' for key in ("research_step_retrieve", "research_step_analyze", "research_step_synthesize"))}</div></div></div>
<div id="report-container" class="report-container"><header id="report-header" class="report-header"></header><div id="report-body" class="report-grid"></div></div><div id="error-area"></div></section>'''
    body = header + f'<div class="research-layout">{brief_card}{guide_card}</div>' + output
    return render_page(PageShell(
        title_key="research_title", current_page="research", body_html=body,
        lang=lang, extra_css=RESEARCH_CSS, extra_js=RESEARCH_JS, wide=True,
    ))
