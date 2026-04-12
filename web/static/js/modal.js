/**
 * Modal focus-trap utility for NOMAD Field Desk.
 *
 * WCAG 2.1 AA requires that when a modal dialog is open, Tab/Shift+Tab
 * cycles only within the modal's focusable elements, and pressing Escape
 * closes the modal. This module provides two functions:
 *
 *   NomadModal.open(modalEl, {onClose})
 *     — saves the previously focused element, moves focus into the modal,
 *       installs the Tab-trap and Escape handler.
 *
 *   NomadModal.close()
 *     — removes the trap, restores focus to the previously focused element,
 *       calls the optional onClose callback.
 *
 * Usage from anywhere in the app:
 *
 *   const overlay = document.getElementById('ai-sitrep-modal');
 *   overlay.classList.remove('is-hidden');
 *   NomadModal.open(overlay, {
 *     onClose: () => overlay.classList.add('is-hidden'),
 *   });
 *
 * The trap handles dynamic content: it re-queries focusable elements on
 * every Tab press, so buttons added after the modal opens are included.
 */

const NomadModal = (() => {
  let _previousFocus = null;
  let _currentModal = null;
  let _onClose = null;
  let _keyHandler = null;

  const FOCUSABLE = [
    'a[href]',
    'button:not([disabled]):not([tabindex="-1"])',
    'input:not([disabled]):not([type="hidden"]):not([tabindex="-1"])',
    'select:not([disabled]):not([tabindex="-1"])',
    'textarea:not([disabled]):not([tabindex="-1"])',
    '[tabindex]:not([tabindex="-1"])',
    '[contenteditable="true"]',
  ].join(', ');

  function _getFocusable(container) {
    return Array.from(container.querySelectorAll(FOCUSABLE)).filter(
      el => el.offsetParent !== null  // visible
    );
  }

  function open(modalEl, options) {
    if (!modalEl) return;
    // Close any already-open trap before opening a new one.
    if (_currentModal) close();

    _previousFocus = document.activeElement;
    _currentModal = modalEl;
    _onClose = options?.onClose || null;

    // Ensure the modal is in the accessibility tree.
    modalEl.setAttribute('role', modalEl.getAttribute('role') || 'dialog');
    modalEl.setAttribute('aria-modal', 'true');
    modalEl.removeAttribute('aria-hidden');
    modalEl.removeAttribute('hidden');

    // Move focus to the first focusable element inside the modal,
    // or to the modal itself if none exist.
    const first = _getFocusable(modalEl);
    if (first.length) {
      first[0].focus();
    } else {
      modalEl.setAttribute('tabindex', '-1');
      modalEl.focus();
    }

    // Install keyboard handler.
    _keyHandler = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        close();
        return;
      }
      if (e.key !== 'Tab') return;
      const focusable = _getFocusable(modalEl);
      if (!focusable.length) { e.preventDefault(); return; }
      const firstEl = focusable[0];
      const lastEl = focusable[focusable.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === firstEl) {
          e.preventDefault();
          lastEl.focus();
        }
      } else {
        if (document.activeElement === lastEl) {
          e.preventDefault();
          firstEl.focus();
        }
      }
    };
    document.addEventListener('keydown', _keyHandler, true);
  }

  function close() {
    if (_keyHandler) {
      document.removeEventListener('keydown', _keyHandler, true);
      _keyHandler = null;
    }
    const cb = _onClose;
    _onClose = null;
    _currentModal = null;

    // Restore focus to the element that was focused before the modal opened.
    if (_previousFocus && typeof _previousFocus.focus === 'function') {
      try { _previousFocus.focus(); } catch (_) {}
    }
    _previousFocus = null;

    if (typeof cb === 'function') cb();
  }

  function isOpen() {
    return _currentModal !== null;
  }

  return { open, close, isOpen };
})();
