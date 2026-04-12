/**
 * NomadSpeech — Text-to-speech wrapper on top of the Web Speech API.
 *
 * Responsibilities:
 *   - Queue multiple utterances so rapid `speak()` calls don't drop mid-sentence.
 *   - Allow a single interrupt (cancel the queue) without tearing down state.
 *   - Persist user preferences (enabled, voice URI, rate, pitch) to localStorage.
 *   - Fire "start" / "end" / "error" callbacks so the copilot UI can show
 *     speaking/listening states and chain hands-free turns.
 *
 * Hand-wavy polyfill notes:
 *   - `speechSynthesis.getVoices()` returns [] on first page load in Chrome/
 *     Edge until the `voiceschanged` event fires. We listen for it and
 *     re-populate `_voices` on change.
 *   - Linux WebKitGTK typically ships with zero TTS voices. We gate with
 *     `isSupported()` so callers can hide the UI gracefully.
 */

const NomadSpeech = (() => {
  const STORAGE_KEY = 'nomad-speech-prefs';
  const DEFAULTS = { enabled: true, voiceURI: '', rate: 1.0, pitch: 1.0 };

  let _prefs = { ...DEFAULTS };
  let _voices = [];
  let _currentUtterance = null;
  let _queue = [];
  let _speaking = false;
  const _listeners = { start: [], end: [], error: [] };

  function isSupported() {
    return typeof window !== 'undefined'
      && 'speechSynthesis' in window
      && typeof window.SpeechSynthesisUtterance === 'function';
  }

  function _loadPrefs() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) _prefs = { ...DEFAULTS, ...(JSON.parse(raw) || {}) };
    } catch (_) { _prefs = { ...DEFAULTS }; }
  }

  function _savePrefs() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(_prefs)); } catch (_) {}
  }

  function _refreshVoices() {
    if (!isSupported()) return;
    _voices = window.speechSynthesis.getVoices() || [];
  }

  function _fire(event, payload) {
    (_listeners[event] || []).forEach(cb => { try { cb(payload); } catch (_) {} });
  }

  function init() {
    if (!isSupported()) return false;
    _loadPrefs();
    _refreshVoices();
    // Voices load async on Chrome/Edge
    if (typeof window.speechSynthesis.addEventListener === 'function') {
      window.speechSynthesis.addEventListener('voiceschanged', _refreshVoices);
    } else {
      window.speechSynthesis.onvoiceschanged = _refreshVoices;
    }
    return true;
  }

  function getVoices() {
    if (!_voices.length) _refreshVoices();
    return _voices.slice();
  }

  function getPrefs() { return { ..._prefs }; }

  function setPrefs(patch) {
    _prefs = { ..._prefs, ...(patch || {}) };
    _savePrefs();
  }

  function _pickVoice() {
    if (!_voices.length) _refreshVoices();
    if (_prefs.voiceURI) {
      const match = _voices.find(v => v.voiceURI === _prefs.voiceURI);
      if (match) return match;
    }
    // Prefer an English default
    return _voices.find(v => /^en[-_]/i.test(v.lang)) || _voices[0] || null;
  }

  function _startNext() {
    if (_speaking) return;
    const next = _queue.shift();
    if (!next) { _fire('end', null); return; }

    const u = new SpeechSynthesisUtterance(next.text);
    const voice = _pickVoice();
    if (voice) { u.voice = voice; u.lang = voice.lang; }
    u.rate = _prefs.rate || 1.0;
    u.pitch = _prefs.pitch || 1.0;
    u.onstart = () => { _speaking = true; _fire('start', next); };
    u.onend = () => {
      _speaking = false;
      _currentUtterance = null;
      if (next.onEnd) { try { next.onEnd(); } catch (_) {} }
      _startNext();
    };
    u.onerror = (e) => {
      _speaking = false;
      _currentUtterance = null;
      _fire('error', e);
      _startNext();
    };
    _currentUtterance = u;
    window.speechSynthesis.speak(u);
  }

  /**
   * Speak a string. If `options.interrupt` is true (default), any current
   * queue is cancelled first. `options.onEnd` fires after THIS utterance
   * completes — useful for chaining a listen-again turn in hands-free mode.
   */
  function speak(text, options) {
    if (!isSupported() || !_prefs.enabled) return false;
    const opts = options || {};
    const clean = String(text || '').trim();
    if (!clean) return false;
    if (opts.interrupt !== false) cancel();
    _queue.push({ text: clean, onEnd: opts.onEnd || null });
    _startNext();
    return true;
  }

  function cancel() {
    _queue = [];
    _speaking = false;
    _currentUtterance = null;
    if (isSupported()) {
      try { window.speechSynthesis.cancel(); } catch (_) {}
    }
  }

  function isSpeaking() { return _speaking; }

  function on(event, cb) {
    if (_listeners[event]) _listeners[event].push(cb);
  }

  function off(event, cb) {
    if (!_listeners[event]) return;
    _listeners[event] = _listeners[event].filter(fn => fn !== cb);
  }

  // Auto-init on script load (safe if unsupported — returns false)
  if (typeof window !== 'undefined') {
    init();
  }

  return {
    isSupported, init, speak, cancel, isSpeaking,
    getVoices, getPrefs, setPrefs, on, off,
  };
})();

if (typeof window !== 'undefined') {
  window.NomadSpeech = NomadSpeech;
}
