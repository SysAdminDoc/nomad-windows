/**
 * Toast notification system for NOMAD Field Desk.
 * Stacking, typed toast messages with auto-dismiss.
 */

const _esc = typeof escapeHtml === 'function' ? escapeHtml : (s) => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

let _toastStack = [];
const _toastIcons = {success:'&#10003;', error:'&#10007;', warning:'&#9888;', info:'&#8505;'};
const _toastTitles = {success:'Saved', error:'Action needed', warning:'Heads up', info:'Notice'};

function _compactToastText(value, limit=180) {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  return text.length > limit ? `${text.slice(0, Math.max(0, limit - 3))}...` : text;
}

function _sentenceToastText(value) {
  const text = _compactToastText(value);
  return text && !/[.!?]$/.test(text) ? `${text}.` : text;
}

function _toastErrorDetail(error) {
  if (!error) return '';
  if (typeof error === 'string') return error;
  return error?.data?.error || error?.data?.message || error?.data?.detail ||
    error?.error || error?.message || error?.detail || '';
}

function _ensureToastContainer() {
  let container = document.getElementById('toast-container');
  if (container) return container;
  container = document.createElement('div');
  container.id = 'toast-container';
  container.setAttribute('role', 'region');
  container.setAttribute('aria-label', 'Notifications');
  container.setAttribute('aria-live', 'polite');
  container.setAttribute('aria-atomic', 'false');
  document.body.appendChild(container);
  return container;
}

function toastError(action, error=null, options={}) {
  const base = _sentenceToastText(action || 'Action failed');
  const detail = _compactToastText(_toastErrorDetail(error), options.detailLimit || 180);
  const recovery = _sentenceToastText(options.recovery || '');
  const normalizedBase = base.replace(/[.!?]$/, '').toLowerCase();
  const normalizedDetail = detail.replace(/[.!?]$/, '').toLowerCase();
  const parts = [base];
  if (detail && normalizedDetail !== normalizedBase) parts.push(_sentenceToastText(detail));
  if (recovery) parts.push(recovery);
  toast(parts.filter(Boolean).join(' '), 'error', options.action || null);
}

function _removeToast(el) {
  if (!el || el.dataset.dismissed === 'true') return;
  el.dataset.dismissed = 'true';
  el.classList.remove('show');
  setTimeout(() => {
    el.remove();
    _toastStack = _toastStack.filter(t => t !== el);
  }, 250);
}

function toast(msg, type='info', action=null) {
  const container = _ensureToastContainer();
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.setAttribute('role', type === 'error' ? 'alert' : 'status');
  el.setAttribute('aria-live', type === 'error' ? 'assertive' : 'polite');
  const actionHtml = action && action.label && action.onclick
    ? `<button type="button" class="toast-action-btn">${_esc(action.label)}</button>` : '';
  el.innerHTML = `
    <span class="toast-icon" aria-hidden="true">${_toastIcons[type]||_toastIcons.info}</span>
    <div class="toast-body">
      <div class="toast-title">${_toastTitles[type] || _toastTitles.info}</div>
      <div class="toast-message">${_esc(msg)}${actionHtml}</div>
    </div>
    <button type="button" class="toast-close" aria-label="Dismiss notification">&times;</button>
  `;
  if (action && action.onclick) {
    const btn = el.querySelector('.toast-action-btn');
    if (btn) btn.addEventListener('click', () => { action.onclick(); _removeToast(el); });
  }
  container.appendChild(el);
  if (_toastStack.length >= 5) {
    const oldest = _toastStack.shift();
    oldest.remove();
  }
  _toastStack.push(el);
  const closeBtn = el.querySelector('.toast-close');
  if (closeBtn) closeBtn.addEventListener('click', () => _removeToast(el));
  requestAnimationFrame(() => el.classList.add('show'));
  const dur = type === 'error' ? 6000 : type === 'warning' ? 4500 : 3000;
  setTimeout(() => {
    _removeToast(el);
  }, dur);
}

// Attach to window for backward compatibility
window.toast = toast;
window.toastError = toastError;
