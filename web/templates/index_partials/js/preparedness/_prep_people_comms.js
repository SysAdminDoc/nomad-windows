/* ─── Contacts ─── */
let _cachedContacts = [];
async function loadContacts() {
  const q = document.getElementById('contact-search').value.trim();
  let url = '/api/contacts';
  if (q) url += `?q=${encodeURIComponent(q)}`;
  const el = document.getElementById('contacts-grid');
  if (el && !el.children.length) el.innerHTML = Array(3).fill('<div class="skeleton skeleton-card"></div>').join('');
  try {
    const contacts = await apiFetch(url);
    if (!q) _cachedContacts = contacts;
    if (!contacts.length) {
      el.innerHTML = '<div class="prep-empty-state prep-empty-state-wide">No contacts yet. Add your emergency contacts, team members, and neighbors.</div>';
      return;
    }
    el.innerHTML = contacts.map(c => {
      let fields = '';
      if (c.callsign) fields += `<div class="cc-field"><strong>Callsign:</strong> ${escapeHtml(c.callsign)}</div>`;
      if (c.phone) fields += `<div class="cc-field"><strong>Phone:</strong> ${escapeHtml(c.phone)}</div>`;
      if (c.freq) fields += `<div class="cc-field"><strong>Freq:</strong> ${escapeHtml(c.freq)}</div>`;
      if (c.skills) fields += `<div class="cc-field"><strong>Skills:</strong> ${escapeHtml(c.skills)}</div>`;
      if (c.rally_point) fields += `<div class="cc-field"><strong>Rally:</strong> ${escapeHtml(c.rally_point)}</div>`;
      if (c.blood_type) fields += `<div class="cc-field"><strong>Blood:</strong> ${escapeHtml(c.blood_type)}</div>`;
      if (c.medical_notes) fields += `<div class="cc-field"><strong>Medical:</strong> ${escapeHtml(c.medical_notes)}</div>`;
      if (c.address) fields += `<div class="cc-field"><strong>Address:</strong> ${escapeHtml(c.address)}</div>`;
      if (c.notes) fields += `<div class="cc-field contact-card-note">${escapeHtml(c.notes)}</div>`;
      return `<div class="contact-card">
        <div class="cc-name">${escapeHtml(c.name)}</div>
        ${c.role ? `<div class="cc-role">${escapeHtml(c.role)}</div>` : ''}
        ${fields}
        <div class="cc-actions">
          <button type="button" class="btn btn-sm" data-prep-action="edit-contact" data-contact-id="${c.id}">Edit</button>
          <button type="button" class="btn btn-sm btn-danger" data-prep-action="delete-contact" data-contact-id="${c.id}">Delete</button>
        </div>
      </div>`;
    }).join('');
  } catch(e) {
    document.getElementById('contacts-grid').innerHTML = '<div class="prep-empty-state prep-empty-state-wide prep-error-state">Failed to load contacts</div>';
  }
}

async function addEmergencyNumbers() {
  const numbers = [
    {name: 'Emergency Services', phone: '911', role: 'Police / Fire / EMS', notes: 'Primary emergency number'},
    {name: 'Poison Control', phone: '1-800-222-1222', role: 'Poison emergency', notes: '24/7 — free, confidential'},
    {name: 'National Suicide Hotline', phone: '988', role: 'Mental health crisis', notes: 'Call or text 988'},
    {name: 'FEMA Helpline', phone: '1-800-621-3362', role: 'Disaster assistance', notes: 'Federal disaster relief registration'},
    {name: 'Red Cross', phone: '1-800-733-2767', role: 'Disaster relief / shelter locator', notes: 'redcross.org'},
    {name: 'National Weather Service', phone: '', role: 'Weather alerts', freq: 'NOAA 162.400-162.550 MHz', notes: 'Monitor via NOAA weather radio'},
    {name: 'Coast Guard', phone: 'VHF Ch 16', role: 'Maritime emergency', freq: '156.800 MHz', notes: 'Marine distress frequency'},
  ];
  const results = await Promise.allSettled(numbers.map(c => apiPost('/api/contacts', c)));
  const added = results.filter(r => r.status === 'fulfilled').length;
  toast(`Added ${added} emergency contacts`, 'success');
  loadContacts();
}

const _ctFields = {name:'ct-name', callsign:'ct-callsign', role:'ct-role', skills:'ct-skills', phone:'ct-phone', freq:'ct-freq', address:'ct-address', rally:'ct-rally', blood:'ct-blood', medical:'ct-medical', notes:'ct-notes'};
let _ctRecoveryAttached = false;
function showContactForm(contact) {
  document.getElementById('contact-form').style.display = 'block';
  const fields = ['name','callsign','role','skills','phone','freq','address','rally','blood','medical','notes'];
  const keys = ['name','callsign','role','skills','phone','freq','address','rally_point','blood_type','medical_notes','notes'];
  if (contact) {
    document.getElementById('ct-edit-id').value = contact.id;
    fields.forEach((f,i) => document.getElementById('ct-'+f).value = contact[keys[i]] || '');
  } else {
    document.getElementById('ct-edit-id').value = '';
    fields.forEach(f => document.getElementById('ct-'+f).value = '');
    if (FormStateRecovery.restore('contact', _ctFields)) {
      toast('Recovered unsaved contact data', 'info');
    }
  }
  if (!_ctRecoveryAttached) { FormStateRecovery.attach('contact', _ctFields); _ctRecoveryAttached = true; }
}
function hideContactForm() { document.getElementById('contact-form').style.display = 'none'; FormStateRecovery.clear('contact'); }

async function saveContact() {
  const editId = document.getElementById('ct-edit-id').value;
  const data = {
    name: document.getElementById('ct-name').value.trim(),
    callsign: document.getElementById('ct-callsign').value.trim(),
    role: document.getElementById('ct-role').value.trim(),
    skills: document.getElementById('ct-skills').value.trim(),
    phone: document.getElementById('ct-phone').value.trim(),
    freq: document.getElementById('ct-freq').value.trim(),
    address: document.getElementById('ct-address').value.trim(),
    rally_point: document.getElementById('ct-rally').value.trim(),
    blood_type: document.getElementById('ct-blood').value,
    medical_notes: document.getElementById('ct-medical').value.trim(),
    notes: document.getElementById('ct-notes').value.trim(),
  };
  if (!data.name) { toast('Name is required', 'warning'); return; }
  const btn = document.querySelector('#contact-form .btn-primary, #contact-form [onclick*="saveContact"]');
  if (btn) btn.classList.add('is-loading');
  try {
    if (editId) {
      await apiPut(`/api/contacts/${editId}`, data);
      toast('Contact updated', 'success');
    } else {
      await apiPost('/api/contacts', data);
      toast('Contact added', 'success');
    }
  } catch(e) { toast(e.message || 'Failed to save contact', 'error'); return;
  } finally { if (btn) btn.classList.remove('is-loading'); }
  FormStateRecovery.clear('contact');
  hideContactForm();
  loadContacts();
}

function editContact(id) {
  const c = _cachedContacts.find(x => x.id === id);
  if (c) showContactForm(c);
}

async function deleteContact(id) {
  if (!confirm('Delete this contact?')) return;
  try {
    await apiDelete(`/api/contacts/${id}`);
    toast('Contact deleted', 'warning', {
      duration: 6000,
      actions: [{ label: 'Undo', onClick: () => {
        apiPost('/api/undo').then(() => { toast('Undo successful', 'success'); loadContacts(); }).catch(() => toast('Undo expired', 'info'));
      }}]
    });
    loadContacts();
  } catch(e) { toast(e?.data?.error || e?.message || 'Failed to delete contact', 'error'); }
}

/* ─── Unit Converter ─── */
function convertUnit() {
  const val = parseFloat(document.getElementById('uc-value').value) || 0;
  const type = document.getElementById('uc-type').value;
  const conversions = {
    'mi-km': [1.60934, 'km'], 'km-mi': [0.621371, 'miles'],
    'lb-kg': [0.453592, 'kg'], 'kg-lb': [2.20462, 'lbs'],
    'gal-L': [3.78541, 'liters'], 'L-gal': [0.264172, 'gallons'],
    'F-C': [null, null], 'C-F': [null, null],
    'ft-m': [0.3048, 'meters'], 'm-ft': [3.28084, 'feet'],
    'in-cm': [2.54, 'cm'], 'oz-g': [28.3495, 'grams'],
    'fl-mL': [29.5735, 'mL'], 'acre-ha': [0.404686, 'hectares'],
  };
  let result;
  if (type === 'F-C') result = `<strong>${((val-32)*5/9).toFixed(2)}</strong> degrees Celsius`;
  else if (type === 'C-F') result = `<strong>${(val*9/5+32).toFixed(2)}</strong> degrees Fahrenheit`;
  else { const [factor, unit] = conversions[type]; result = `<strong>${(val*factor).toFixed(4)}</strong> ${unit}`; }
  document.getElementById('uc-result').innerHTML = result;
}

/* ─── LAN Message Encryption ─── */
const _lanEncKey = 'nomad-lan-v1'; // Simple shared key for LAN

async function encryptLanMessage(text) {
  try {
    const enc = new TextEncoder();
    const keyData = enc.encode(_lanEncKey.padEnd(32, '0').slice(0, 32));
    const key = await crypto.subtle.importKey('raw', keyData, 'AES-GCM', false, ['encrypt']);
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const cipher = await crypto.subtle.encrypt({name: 'AES-GCM', iv}, key, enc.encode(text));
    return btoa(String.fromCharCode(...iv)) + '.' + btoa(String.fromCharCode(...new Uint8Array(cipher)));
  } catch(e) { return text; } // Fallback to plaintext if crypto fails
}

async function decryptLanMessage(encoded) {
  try {
    if (!encoded.includes('.')) return encoded; // Not encrypted
    const [ivB64, dataB64] = encoded.split('.');
    const iv = new Uint8Array([...atob(ivB64)].map(c => c.charCodeAt(0)));
    const data = new Uint8Array([...atob(dataB64)].map(c => c.charCodeAt(0)));
    const enc = new TextEncoder();
    const keyData = enc.encode(_lanEncKey.padEnd(32, '0').slice(0, 32));
    const key = await crypto.subtle.importKey('raw', keyData, 'AES-GCM', false, ['decrypt']);
    const plain = await crypto.subtle.decrypt({name: 'AES-GCM', iv}, key, data);
    return new TextDecoder().decode(plain);
  } catch(e) { return encoded; } // Return raw if decryption fails (plaintext message)
}

/* ─── LAN Chat ─── */
let _lanChatOpen = false;
let _lanPoll = null;
let _lanPresencePoll = null;
let _lanLastId = 0;
let _lanChatCompact = true;

function utilityEmptyState(titleOrMessage, body = '') {
  if (body) {
    return `<div class="utility-empty-state"><strong>${escapeHtml(titleOrMessage)}</strong><span>${escapeHtml(body)}</span></div>`;
  }
  return `<div class="utility-empty-state"><span>${escapeHtml(titleOrMessage)}</span></div>`;
}

function startLanMessagePolling() {
  if (_lanPoll) return;
  if (window.NomadShellRuntime) {
    _lanPoll = window.NomadShellRuntime.startInterval('utility.lan-messages', pollLanMessages, 3000, {
      requireVisible: true,
    });
    return;
  }
  _lanPoll = setInterval(() => {
    if (!document.hidden) pollLanMessages();
  }, 3000);
}

function stopLanMessagePolling() {
  if (_lanPoll) {
    clearInterval(_lanPoll);
    _lanPoll = null;
  }
  window.NomadShellRuntime?.stopInterval('utility.lan-messages');
}

function startLanPresencePolling() {
  if (_lanPresencePoll) return;
  const refreshPresence = () => {
    const panel = document.getElementById('lan-chat-panel');
    if (isShellVisible(panel)) loadLanPresence();
  };
  if (window.NomadShellRuntime) {
    _lanPresencePoll = window.NomadShellRuntime.startInterval('utility.lan-presence', refreshPresence, 15000, {
      requireVisible: true,
    });
    return;
  }
  _lanPresencePoll = setInterval(() => {
    if (!document.hidden) refreshPresence();
  }, 15000);
}

function stopLanPresencePolling() {
  if (_lanPresencePoll) {
    clearInterval(_lanPresencePoll);
    _lanPresencePoll = null;
  }
  window.NomadShellRuntime?.stopInterval('utility.lan-presence');
}

function setLanChatCompact(compact) {
  _lanChatCompact = compact;
  const panel = document.getElementById('lan-chat-panel');
  const toggle = document.getElementById('lan-chat-compact-toggle');
  if (!panel) return;
  panel.classList.toggle('utility-panel-compact', compact);
  panel.classList.toggle('utility-panel-expanded', !compact);
  if (toggle) {
    toggle.textContent = compact ? 'Expand' : 'Compact';
    toggle.setAttribute('aria-expanded', compact ? 'false' : 'true');
    toggle.setAttribute('aria-label', compact ? 'Expand LAN chat panel' : 'Collapse LAN chat panel');
    toggle.title = compact ? 'Show full LAN chat details' : 'Return LAN chat to compact mode';
  }
}

function toggleLanChatCompact() {
  setLanChatCompact(!_lanChatCompact);
}

function toggleLanChat() {
  _lanChatOpen = !_lanChatOpen;
  const panel = document.getElementById('lan-chat-panel');
  const button = document.getElementById('copilot-utility-chat-btn');
  if (_lanChatOpen) {
    _qaOpen = false;
    setShellVisibility(document.getElementById('quick-actions-menu'), false);
    setUtilityDockButtonExpanded('actions', false);
    _timerPanelOpen = false;
    setShellVisibility(document.getElementById('timer-panel'), false);
    setUtilityDockButtonExpanded('timer', false);
    if (typeof stopTimerPolling === 'function') stopTimerPolling();
    else if (_timerPoll) { clearInterval(_timerPoll); _timerPoll = null; }
  }
  setShellVisibility(panel, _lanChatOpen);
  if (button) button.setAttribute('aria-expanded', _lanChatOpen ? 'true' : 'false');
  if (_lanChatOpen) {
    setLanChatCompact(true);
    const saved = localStorage.getItem('nomad-lan-name') || '';
    document.getElementById('lan-chat-name').value = saved;
    loadLanMessages();
    loadLanChannels();
    loadLanPresence();
    startLanMessagePolling();
    startLanPresencePolling();
  } else {
    setLanChatCompact(true);
    stopLanMessagePolling();
    stopLanPresencePolling();
  }
}

async function loadLanPresence() {
  const el = document.getElementById('lan-presence-list');
  const statusEl = document.getElementById('lan-chat-status');
  if (!el) return;
  // Send our own heartbeat
  safeFetch('/api/lan/presence/heartbeat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name: localStorage.getItem('nomad-node-name') || 'This Node', version: VERSION})});
  const nodes = await safeFetch('/api/lan/presence', {}, []);
  if (!nodes.length) {
    if (statusEl) statusEl.textContent = 'This desk only';
    el.innerHTML = '<span class="utility-presence-pill utility-presence-pill-solo">Only you</span>';
    return;
  }
  if (statusEl) statusEl.textContent = `${nodes.length + 1} desks online`;
  el.innerHTML = nodes.map(n => `<span class="utility-presence-pill"><span class="utility-presence-dot"></span><span>${escapeHtml(n.node_name)}</span></span>`).join('');
}

async function loadLanMessages() {
  try {
    const msgs = await apiFetch('/api/lan/messages');
    renderLanMessages(msgs);
    if (msgs.length) _lanLastId = msgs[msgs.length-1].id;
  } catch(e) {}
}

async function pollLanMessages() {
  try {
    const msgs = await apiFetch(`/api/lan/messages?after=${_lanLastId}`);
    if (msgs.length) {
      const el = document.getElementById('lan-chat-messages');
      for (const m of msgs) {
        const html = await renderLanMsg(m);
        el.insertAdjacentHTML('beforeend', html);
      }
      _lanLastId = msgs[msgs.length-1].id;
      el.scrollTop = el.scrollHeight;
    }
  } catch(e) {}
}

async function renderLanMessages(msgs) {
  const el = document.getElementById('lan-chat-messages');
  if (!msgs.length) {
    el.innerHTML = utilityEmptyState('No messages yet', 'Anyone on the same local network can coordinate here as soon as another NOMAD desk comes online.');
    return;
  }
  const rendered = await Promise.all(msgs.map(m => renderLanMsg(m)));
  el.innerHTML = rendered.join('');
  el.scrollTop = el.scrollHeight;
}

async function renderLanMsg(m) {
  const t = new Date(m.created_at);
  const ts = t.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
  const decrypted = await decryptLanMessage(m.content);
  return `<div class="lan-msg"><div class="lan-msg-head"><span class="lan-sender">${escapeHtml(m.sender)}</span><span class="lan-time">${ts}</span></div><div class="lan-text">${escapeHtml(decrypted)}</div></div>`;
}

async function sendLanMsg() {
  const input = document.getElementById('lan-chat-input');
  const content = input.value.trim();
  if (!content) return;
  const sender = document.getElementById('lan-chat-name').value.trim() || 'Field Desk';
  input.value = '';
  const encrypt = document.getElementById('lan-encrypt-toggle')?.checked;
  const finalContent = encrypt ? await encryptLanMessage(content) : content;
  try {
    const msg = await apiPost('/api/lan/messages', {sender, content: finalContent, channel: document.getElementById('lan-channel')?.value || ''});
    const el = document.getElementById('lan-chat-messages');
    // Remove empty state if present
    if (el.querySelector('.utility-empty-state')) el.innerHTML = '';
    const html = await renderLanMsg(msg);
    el.insertAdjacentHTML('beforeend', html);
    _lanLastId = msg.id;
    el.scrollTop = el.scrollHeight;
  } catch(e) { toast('Message not sent. Check local network availability and try again.', 'error'); }
}

async function loadLanChannels() {
  const sel = document.getElementById('lan-channel');
  if (!sel) return;
  const channels = await safeFetch('/api/lan/channels', {}, []);
  sel.innerHTML = '<option value="">All Channels</option>' + channels.map(c => `<option value="${escapeAttr(c.name)}">${escapeHtml(c.name)}</option>`).join('');
}
function switchLanChannel() {
  loadLanMessages();
}

/* ─── Morse Code Trainer ─── */
const MORSE_MAP = {'A':'.-','B':'-...','C':'-.-.','D':'-..','E':'.','F':'..-.','G':'--.','H':'....','I':'..','J':'.---','K':'-.-','L':'.-..','M':'--','N':'-.','O':'---','P':'.--.','Q':'--.-','R':'.-.','S':'...','T':'-','U':'..-','V':'...-','W':'.--','X':'-..-','Y':'-.--','Z':'--..','0':'-----','1':'.----','2':'..---','3':'...--','4':'....-','5':'.....','6':'-....','7':'--...','8':'---..','9':'----.','.':'.-.-.-',',':'--..--','?':'..--..','!':'-.-.--','/':'-..-.','-':'-....-','=':'-...-'};
const MORSE_REV = Object.fromEntries(Object.entries(MORSE_MAP).map(([k,v])=>[v,k]));

function textToMorse() {
  const text = (document.getElementById('morse-input')?.value || '').toUpperCase();
  const morse = text.split('').map(c => c === ' ' ? '/' : (MORSE_MAP[c] || '')).filter(Boolean).join(' ');
  const out = document.getElementById('morse-output');
  if (out) out.textContent = morse;
}

function morseToText() {
  const morse = (document.getElementById('morse-decode-input')?.value || '').trim();
  const words = morse.split(/\s*\/\s*/);
  const text = words.map(w => w.split(/\s+/).map(c => MORSE_REV[c] || '?').join('')).join(' ');
  const out = document.getElementById('morse-decode-output');
  if (out) out.textContent = text;
}

let _morseAudioCtx = null;
function playMorse() {
  const morse = document.getElementById('morse-output')?.textContent;
  if (!morse) { toast('Type some text first', 'warning'); return; }
  if (!_morseAudioCtx) _morseAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
  const ctx = _morseAudioCtx;
  const wpm = parseInt(document.getElementById('morse-wpm')?.value) || 15;
  const dotLen = 1.2 / wpm; // seconds per dot
  let t = ctx.currentTime + 0.1;
  for (const ch of morse) {
    if (ch === '.') { playTone(ctx, t, dotLen, 700); t += dotLen * 2; }
    else if (ch === '-') { playTone(ctx, t, dotLen * 3, 700); t += dotLen * 4; }
    else if (ch === ' ') { t += dotLen * 3; }
    else if (ch === '/') { t += dotLen * 7; }
  }
  toast('Playing Morse...', 'info');
}

function playTone(ctx, startTime, duration, freq) {
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = 'sine';
  osc.frequency.value = freq;
  gain.gain.setValueAtTime(0.3, startTime);
  gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration);
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start(startTime);
  osc.stop(startTime + duration);
}
