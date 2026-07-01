"""轻量组件层的共享 Vanilla JavaScript。"""

COMPONENT_JS = r"""
function uiSetBusy(target, busy, label) {
  const el = typeof target === 'string' ? document.getElementById(target) : target;
  if (!el) return;
  el.setAttribute('aria-busy', busy ? 'true' : 'false');
  if ('disabled' in el) el.disabled = Boolean(busy);
  if (label && busy) {
    if (!el.dataset.uiLabel) el.dataset.uiLabel = el.textContent;
    el.textContent = label;
  } else if (!busy && el.dataset.uiLabel) {
    el.textContent = el.dataset.uiLabel;
    delete el.dataset.uiLabel;
  }
}

function uiToggleDisclosure(trigger, targetId) {
  const target = document.getElementById(targetId);
  if (!target) return false;
  const expanded = trigger.getAttribute('aria-expanded') === 'true';
  trigger.setAttribute('aria-expanded', String(!expanded));
  target.hidden = expanded;
  return !expanded;
}

function uiClearForm(formId) {
  const form = document.getElementById(formId);
  if (!form) return;
  form.reset();
  form.querySelectorAll('input,select,textarea').forEach(function (el) {
    el.dispatchEvent(new Event('change', {bubbles: true}));
    if (el.tagName === 'INPUT') el.dispatchEvent(new Event('input', {bubbles: true}));
  });
}

function uiDebounce(fn, wait) {
  let timer;
  return function () {
    const args = arguments, self = this;
    clearTimeout(timer);
    timer = setTimeout(function () { fn.apply(self, args); }, wait || 250);
  };
}

function uiAnnounce(message) {
  let region = document.getElementById('ui-announcer');
  if (!region) {
    region = document.createElement('div');
    region.id = 'ui-announcer';
    region.setAttribute('aria-live', 'polite');
    region.setAttribute('aria-atomic', 'true');
    region.style.cssText = 'position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)';
    document.body.appendChild(region);
  }
  region.textContent = '';
  setTimeout(function () { region.textContent = String(message || ''); }, 20);
}

function uiToast(message, tone, duration) {
  let region = document.querySelector('.ui-toast-region');
  if (!region) {
    region = document.createElement('div');
    region.className = 'ui-toast-region';
    region.setAttribute('aria-live', 'polite');
    document.body.appendChild(region);
  }
  const toast = document.createElement('div');
  toast.className = 'ui-toast ui-toast--' + (tone || 'accent');
  toast.textContent = String(message || '');
  region.appendChild(toast);
  setTimeout(function () { toast.remove(); }, duration || 3000);
}
"""
