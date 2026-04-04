/**
 * Toast notification system for NOMAD Field Desk.
 * Stacking, typed toast messages with auto-dismiss.
 */

const _esc = typeof escapeHtml === 'function' ? escapeHtml : (s) => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

let _toastStack = [];
const _toastIcons = {success:'&#10003;', error:'&#10007;', warning:'&#9888;', info:'&#8505;'};

function toast(msg, type='info') {
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.setAttribute('role', 'status');
  el.setAttribute('aria-live', 'polite');
  el.innerHTML = `<span class="toast-icon">${_toastIcons[type]||_toastIcons.info}</span>${_esc(msg)}`;
  document.body.appendChild(el);
  if (_toastStack.length >= 5) {
    const oldest = _toastStack.shift();
    oldest.remove();
  }
  _toastStack.push(el);
  _toastStack.forEach((t, i) => { t.style.bottom = (20 + i * 52) + 'px'; });
  requestAnimationFrame(() => el.classList.add('show'));
  const dur = type === 'error' ? 6000 : type === 'warning' ? 4500 : 3000;
  setTimeout(() => {
    el.classList.remove('show');
    setTimeout(() => {
      el.remove();
      _toastStack = _toastStack.filter(t => t !== el);
      _toastStack.forEach((t, i) => { t.style.bottom = (20 + i * 52) + 'px'; });
    }, 250);
  }, dur);
}

// Attach to window for backward compatibility
window.toast = toast;
