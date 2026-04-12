/**
 * NomadVoiceCopilot — Hands-free conversation loop for the AI copilot dock.
 *
 * Flow:
 *   1. User clicks the "hands-free" button on the copilot dock.
 *   2. Loop:  listen → (pause) → submit transcript to copilot → speak answer → listen again
 *   3. User clicks the button again (or says "stop listening" or presses Escape)
 *      to exit.
 *
 * The `voiceInput()` helper in `_app_init_runtime.js` already covers the
 * single-shot "tap mic, dictate once, submit" path. This module is a
 * higher-level orchestrator layered on top of that SpeechRecognition +
 * NomadSpeech, specifically for the copilot dock. It is intentionally
 * decoupled from the generic voiceInput() helper so that one-off voice
 * entry on other inputs (e.g. inventory add) keeps its existing behavior.
 *
 * Accessibility contract:
 *   - A visible `#copilot-voice-transcript` strip shows what was heard so
 *     users who can't hear the TTS response still follow the exchange.
 *   - A visible `#copilot-voice-state` badge reflects {idle|listening|
 *     thinking|speaking} for motion-sensitive users who need non-animated
 *     state indication.
 *   - Escape key exits the session.
 *   - Failures surface via `toast()` — never silent.
 */

const NomadVoiceCopilot = (() => {
  const EXIT_PHRASES = ['stop listening', 'exit voice', 'end session', 'goodbye'];

  let _recognition = null;
  let _active = false;
  let _restartTimer = null;
  let _lastTranscript = '';

  function _getSpeechRecognitionCtor() {
    return (typeof window !== 'undefined') &&
      (window.SpeechRecognition || window.webkitSpeechRecognition);
  }

  function isSupported() {
    const ctor = _getSpeechRecognitionCtor();
    const tts = (typeof window !== 'undefined') && window.NomadSpeech && window.NomadSpeech.isSupported();
    return !!(ctor && tts);
  }

  function _setState(state) {
    const badge = document.getElementById('copilot-voice-state');
    if (badge) {
      badge.dataset.state = state;
      badge.textContent = {
        idle: 'Idle',
        listening: 'Listening…',
        thinking: 'Thinking…',
        speaking: 'Speaking…',
      }[state] || state;
    }
    const btn = document.getElementById('copilot-handsfree-btn');
    if (btn) {
      btn.dataset.state = state;
      btn.setAttribute('aria-pressed', _active ? 'true' : 'false');
    }
  }

  function _setTranscript(text) {
    _lastTranscript = text || '';
    const strip = document.getElementById('copilot-voice-transcript');
    if (strip) {
      if (text) {
        strip.textContent = 'You: ' + text;
        strip.hidden = false;
      } else {
        strip.textContent = '';
        strip.hidden = true;
      }
    }
  }

  function _onResult(event) {
    // Use the final segment only — interim results are chatty and unreliable
    let transcript = '';
    for (let i = event.resultIndex; i < event.results.length; i++) {
      if (event.results[i].isFinal) transcript += event.results[i][0].transcript;
    }
    transcript = transcript.trim();
    if (!transcript) return;

    _setTranscript(transcript);

    // Exit phrase detection
    const lower = transcript.toLowerCase();
    if (EXIT_PHRASES.some(p => lower.includes(p))) {
      stop();
      if (typeof window.toast === 'function') window.toast('Voice session ended', 'info');
      return;
    }

    // Hand off to the existing copilot pipeline
    _submitToCopilot(transcript);
  }

  function _submitToCopilot(question) {
    const input = document.getElementById('copilot-input');
    if (input) input.value = question;
    _setState('thinking');

    // Pause recognition while we're thinking+speaking so the TTS output
    // doesn't feed back into the mic as a new question.
    _safeRecognitionStop();

    if (typeof window.askCopilot !== 'function') {
      if (typeof window.toast === 'function') window.toast('Copilot unavailable', 'error');
      stop();
      return;
    }

    // askCopilot writes the answer into #copilot-answer via innerHTML.
    // We read it back out as plain text for TTS after the promise resolves.
    Promise.resolve(window.askCopilot(question))
      .then(() => _speakLatestAnswer())
      .catch(() => {
        _setState('listening');
        _restartRecognition();
      });
  }

  function _speakLatestAnswer() {
    const answerEl = document.getElementById('copilot-answer');
    if (!answerEl) { _restartRecognition(); return; }
    const body = answerEl.querySelector('.copilot-answer-body') || answerEl;
    const text = (body.textContent || '').trim();
    if (!text) { _restartRecognition(); return; }
    _setState('speaking');
    const spoken = window.NomadSpeech.speak(text, {
      interrupt: true,
      onEnd: () => { if (_active) _restartRecognition(); },
    });
    // If TTS couldn't even start, don't strand the user
    if (!spoken && _active) _restartRecognition();
  }

  function _safeRecognitionStop() {
    try { if (_recognition) _recognition.stop(); } catch (_) {}
  }

  function _restartRecognition() {
    if (!_active) return;
    _setState('listening');
    // Small delay — Chrome can reject start() if called in the same tick as stop()
    clearTimeout(_restartTimer);
    _restartTimer = setTimeout(() => {
      if (!_active) return;
      try { _recognition && _recognition.start(); }
      catch (e) { /* already started is fine; any other error -> stop */ }
    }, 300);
  }

  function start() {
    if (_active) return true;
    if (!isSupported()) {
      if (typeof window.toast === 'function') {
        window.toast('Hands-free voice not supported in this browser', 'warning');
      }
      return false;
    }
    const Ctor = _getSpeechRecognitionCtor();
    _recognition = new Ctor();
    _recognition.lang = 'en-US';
    _recognition.continuous = false;
    _recognition.interimResults = false;
    _recognition.onresult = _onResult;
    _recognition.onerror = (e) => {
      // 'no-speech' and 'aborted' are expected during the listen→speak→listen loop
      if (e.error && e.error !== 'no-speech' && e.error !== 'aborted') {
        if (typeof window.toast === 'function') {
          window.toast('Voice error: ' + e.error, 'warning');
        }
      }
    };
    _recognition.onend = () => {
      // If we're still active and not currently speaking, re-enter listen
      if (_active && !window.NomadSpeech.isSpeaking()) {
        _restartRecognition();
      }
    };

    _active = true;
    _setState('listening');
    _setTranscript('');
    try {
      _recognition.start();
      if (typeof window.toast === 'function') {
        window.toast('Hands-free mode on — say "stop listening" to exit', 'info');
      }
      // Speak a greeting so the user knows TTS works
      const greeting = 'Hands free mode active. Ask me anything.';
      window.NomadSpeech.speak(greeting, { interrupt: true });
    } catch (e) {
      _active = false;
      _setState('idle');
      if (typeof window.toast === 'function') {
        window.toast('Could not start voice session', 'error');
      }
      return false;
    }
    return true;
  }

  function stop() {
    _active = false;
    clearTimeout(_restartTimer);
    _safeRecognitionStop();
    _recognition = null;
    try { window.NomadSpeech && window.NomadSpeech.cancel(); } catch (_) {}
    _setState('idle');
    _setTranscript('');
  }

  function toggle() {
    return _active ? (stop(), false) : start();
  }

  function isActive() { return _active; }

  // Global Escape exits the session
  if (typeof document !== 'undefined') {
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && _active) stop();
    });
  }

  return { start, stop, toggle, isActive, isSupported };
})();

if (typeof window !== 'undefined') {
  window.NomadVoiceCopilot = NomadVoiceCopilot;
}
