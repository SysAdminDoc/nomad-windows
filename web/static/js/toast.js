/**
 * Toast notification system for NOMAD Field Desk.
 * Stacking, typed toast messages with auto-dismiss.
 */

const _esc = typeof escapeHtml === 'function' ? escapeHtml : (s) => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

let _toastStack = [];
const _toastIcons = {success:'&#10003;', error:'&#10007;', warning:'&#9888;', info:'&#8505;'};
const _toastTitles = {success:'Saved', error:'Action needed', warning:'Heads up', info:'Notice'};

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
