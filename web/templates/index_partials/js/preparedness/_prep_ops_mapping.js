/* ─── Timers ─── */
let _timerPanelOpen = false;
let _timerPoll = null;

function startTimerPolling() {
  if (_timerPoll) return;
  if (window.NomadShellRuntime) {
    _timerPoll = window.NomadShellRuntime.startInterval('utility.timers', loadTimers, 1000, {
      requireVisible: true,
    });
    return;
  }
  _timerPoll = setInterval(() => {
    if (!document.hidden) loadTimers();
  }, 1000);
}

function stopTimerPolling() {
  if (_timerPoll) {
    clearInterval(_timerPoll);
    _timerPoll = null;
  }
  window.NomadShellRuntime?.stopInterval('utility.timers');
}

function toggleTimerPanel() {
  _timerPanelOpen = !_timerPanelOpen;
  const panel = document.getElementById('timer-panel');
  const button = document.getElementById('copilot-utility-timer-btn');
  if (_timerPanelOpen) {
    _lanChatOpen = false;
    setShellVisibility(document.getElementById('lan-chat-panel'), false);
    setUtilityDockButtonExpanded('chat', false);
    if (typeof stopLanMessagePolling === 'function') stopLanMessagePolling();
    else if (_lanPoll) { clearInterval(_lanPoll); _lanPoll = null; }
    if (typeof stopLanPresencePolling === 'function') stopLanPresencePolling();
    _qaOpen = false;
    setShellVisibility(document.getElementById('quick-actions-menu'), false);
    setUtilityDockButtonExpanded('actions', false);
  }
  setShellVisibility(panel, _timerPanelOpen);
  if (button) button.setAttribute('aria-expanded', _timerPanelOpen ? 'true' : 'false');
  if (_timerPanelOpen) {
    loadTimers();
    startTimerPolling();
  } else {
    stopTimerPolling();
  }
}

async function loadTimers() {
  try {
    const resp = await fetch('/api/timers');
    if (!resp.ok) return;
    const timers = await resp.json();
    const el = document.getElementById('timer-list');
    if (!timers.length) {
      el.innerHTML = utilityEmptyState('No active timers. Start one above.');
      return;
    }
    el.innerHTML = timers.map(t => {
      const rem = Math.max(0, Math.round(t.remaining_sec));
      const h = Math.floor(rem / 3600);
      const m = Math.floor((rem % 3600) / 60);
      const s = rem % 60;
      const timeStr = h > 0 ? `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}` : `${m}:${String(s).padStart(2,'0')}`;
      const label = t.done ? 'DONE' : timeStr;
      const toneClass = t.done ? 'timer-item-time-done' : rem < 60 ? 'timer-item-time-danger' : rem < 300 ? 'timer-item-time-warning' : '';
      return `<div class="timer-item${t.done ? ' is-done' : ''}">
        <div class="timer-item-main"><div class="timer-item-name">${escapeHtml(t.name)}</div></div>
        <div class="timer-item-side">
          <span class="timer-item-time ${toneClass}">${label}</span>
          <button class="btn btn-sm btn-danger timer-item-delete" type="button" data-shell-action="delete-timer" data-timer-id="${t.id}">x</button>
        </div>
      </div>`;
    }).join('');
    // Alert for newly done timers
    if (!window._alertedTimers) window._alertedTimers = new Set();
    timers.filter(t => t.done).forEach(t => {
      if (!window._alertedTimers.has(t.id)) {
        window._alertedTimers.add(t.id);
        toast(`Timer "${t.name}" is DONE!`, 'warning');
        sendNotification('Timer Complete', `${t.name} has finished!`);
        playAlertSound('timer');
      }
    });
  } catch(e) {}
}

async function createTimer() {
  const name = document.getElementById('timer-name').value.trim() || 'Timer';
  const mins = parseInt(document.getElementById('timer-mins').value) || 30;
  try {
    const r = await fetch('/api/timers', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name, duration_sec: mins * 60})});
    if (!r.ok) { toast('Failed to create timer', 'error'); return; }
    document.getElementById('timer-name').value = '';
    document.getElementById('timer-mins').value = '';
    toast('Timer "' + name + '" started (' + mins + 'm)', 'success');
    loadTimers();
  } catch(e) { toast('Failed to create timer', 'error'); }
}

function createTimerQuick(name, mins) {
  fetch('/api/timers', {method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({name, duration_sec: mins * 60})}).then(r => {
    if (!r.ok) { toast('Failed to create timer', 'error'); return; }
    toast('Timer "' + name + '" started (' + mins + 'm)', 'success');
    loadTimers();
  }).catch(() => toast('Failed to create timer', 'error'));
}

async function deleteTimer(id) {
  if (!confirm('Delete this timer?')) return;
  try {
    const resp = await fetch(`/api/timers/${id}`, {method:'DELETE'});
    if (!resp.ok) { toast('Failed to delete timer', 'error'); return; }
    toast('Timer deleted', 'warning');
    loadTimers();
  } catch(e) { console.error(e); toast('Failed to delete timer', 'error'); }
}

/* ─── Map Waypoints ─── */
function renderMapPopupFacts(facts = []) {
  const validFacts = facts.filter(fact =>
    fact &&
    fact.label &&
    fact.value !== undefined &&
    fact.value !== null &&
    `${fact.value}` !== ''
  );
  if (!validFacts.length) return '';
  return `<div class="map-popup-facts">
    ${validFacts.map(fact => `
      <div class="map-popup-fact">
        <div class="map-popup-fact-label">${escapeHtml(fact.label)}</div>
        <div class="map-popup-fact-value">${fact.value}</div>
      </div>
    `).join('')}
  </div>`;
}

function renderMapPopupSections(sections = []) {
  const validSections = sections.filter(section => section && section.label);
  if (!validSections.length) return '';
  return `<div class="map-popup-sections">
    ${validSections.map(section => {
      const items = Array.isArray(section.items) ? section.items : [];
      const rows = items.length
        ? items.map(item => `<li>${item}</li>`).join('')
        : `<li>${escapeHtml(section.empty || 'None')}</li>`;
      return `
        <div class="map-popup-section">
          <div class="map-popup-section-label">${escapeHtml(section.label)}</div>
          <ul class="map-popup-list">${rows}</ul>
        </div>
      `;
    }).join('')}
  </div>`;
}

function renderMapPopupShell({ title, meta = '', facts = [], notes = '', sections = [], coords = '', action = '' }) {
  return `<div class="map-popup-shell">
    <div class="map-popup-title">${title}</div>
    ${meta ? `<div class="map-popup-meta">${meta}</div>` : ''}
    ${renderMapPopupFacts(facts)}
    ${notes ? `<div class="map-popup-notes">${notes}</div>` : ''}
    ${renderMapPopupSections(sections)}
    ${coords ? `<div class="map-popup-coords">${coords}</div>` : ''}
    ${action}
  </div>`;
}

async function loadWaypoints() {
  if (!_map) return;
  try {
    const waypoints = await apiFetch('/api/waypoints');
    // Remove existing waypoint markers
    if (window._waypointMarkers) window._waypointMarkers.forEach(m => m.remove());
    window._waypointMarkers = [];
    waypoints.forEach(w => {
      const marker = new maplibregl.Marker({color: w.color || '#5b9fff'})
        .setLngLat([w.lng, w.lat])
        .setPopup(new maplibregl.Popup().setHTML(
          renderMapPopupShell({
            title: escapeHtml(w.name),
            meta: escapeHtml(w.category),
            notes: w.notes ? escapeHtml(w.notes) : '',
            coords: `${w.lat.toFixed(5)}, ${w.lng.toFixed(5)}`,
            action: `<button type="button" class="map-popup-delete" data-map-action="delete-waypoint" data-waypoint-id="${w.id}">Delete</button>`,
          })
        ))
        .addTo(_map);
      window._waypointMarkers.push(marker);
    });
  } catch(e) {}
}

function saveWaypoint() {
  if (!_map) return;
  // Show inline waypoint form
  let panel = document.getElementById('waypoint-form-panel');
  if (panel) { panel.remove(); return; }
  const center = _map.getCenter();
  panel = document.createElement('div');
  panel.id = 'waypoint-form-panel';
  panel.className = 'map-waypoint-panel';
  panel.innerHTML = `
    <div class="map-waypoint-title">Save Waypoint at ${center.lat.toFixed(5)}, ${center.lng.toFixed(5)}</div>
    <div class="map-waypoint-form">
    <input id="wp-name" class="map-waypoint-input" placeholder="Waypoint name...">
    <select id="wp-cat" class="map-waypoint-input">
      <option value="general">General</option><option value="rally">Rally</option><option value="water">Water</option>
      <option value="cache">Cache</option><option value="shelter">Shelter</option><option value="hazard">Hazard</option>
      <option value="medical">Medical</option><option value="comms">Comms</option>
    </select>
    <input id="wp-notes" class="map-waypoint-input" placeholder="Notes (optional)">
    <div class="map-waypoint-actions">
      <button type="button" class="btn btn-sm btn-primary" data-map-action="submit-waypoint" data-wp-lat="${center.lat}" data-wp-lng="${center.lng}">Save</button>
      <button type="button" class="btn btn-sm" data-shell-action="close-waypoint-panel">Cancel</button>
    </div>
    </div>`;
  document.getElementById('map-viewer').appendChild(panel);
  document.getElementById('wp-name').focus();
}
async function submitWaypoint(lat, lng) {
  const name = document.getElementById('wp-name').value.trim();
  if (!name) { toast('Enter a waypoint name', 'warning'); return; }
  const cat = document.getElementById('wp-cat').value;
  const notes = document.getElementById('wp-notes').value.trim();
  await fetch('/api/waypoints', {method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({name, lat, lng, category: cat, notes})});
  toast(`Waypoint "${name}" saved`, 'success');
  document.getElementById('waypoint-form-panel').remove();
  loadWaypoints();
}

async function deleteWaypoint(id) {
  if (!confirm('Delete this waypoint?')) return;
  try {
    const r = await fetch(`/api/waypoints/${id}`, {method:'DELETE'});
    if (!r.ok) throw new Error('Delete failed');
    toast('Waypoint deleted', 'warning');
    loadWaypoints();
  } catch(e) { toast('Failed to delete waypoint', 'error'); }
}

/* ─── Threat Assessment Matrix ─── */
const THREAT_SCENARIOS = ['Natural disaster','Power grid failure','Water contamination','Civil unrest','Pandemic','Wildfire','Economic collapse','Cyber attack','EMP/solar flare','Supply chain disruption'];
const THREAT_LEVELS = ['low','medium','high','critical'];
const THREAT_LVL_COLORS = {low:'var(--green)',medium:'var(--warning)',high:'var(--orange)',critical:'var(--red)'};
const THREAT_LVL_LABELS = {low:'LOW',medium:'MED',high:'HIGH',critical:'CRIT'};

function loadThreatMatrix() {
  let saved = readJsonStorage(localStorage, 'nomad-threats', {});
  let html = '<div class="prep-inline-table-shell threat-matrix-table-shell"><table class="freq-table prep-inline-table threat-matrix-table"><thead><tr><th>Threat</th><th>Likelihood</th><th>Impact</th><th>Risk</th></tr></thead><tbody>';
  THREAT_SCENARIOS.forEach((t, i) => {
    const like = saved[`${i}_l`] || 'low';
    const impact = saved[`${i}_i`] || 'low';
    const likeN = THREAT_LEVELS.indexOf(like) + 1;
    const impactN = THREAT_LEVELS.indexOf(impact) + 1;
    const riskN = likeN * impactN;
    const risk = riskN >= 12 ? 'critical' : riskN >= 6 ? 'high' : riskN >= 3 ? 'medium' : 'low';
    html += `<tr>
      <td class="threat-matrix-label">${t}</td>
      <td class="threat-matrix-cell"><span class="threat-level-btn threat-level-${like}" role="button" tabindex="0" data-prep-action="cycle-threat" data-threat-index="${i}" data-threat-axis="l">${THREAT_LVL_LABELS[like]}</span></td>
      <td class="threat-matrix-cell"><span class="threat-level-btn threat-level-${impact}" role="button" tabindex="0" data-prep-action="cycle-threat" data-threat-index="${i}" data-threat-axis="i">${THREAT_LVL_LABELS[impact]}</span></td>
      <td class="threat-matrix-cell"><span class="threat-level-risk threat-level-${risk}">${THREAT_LVL_LABELS[risk]}</span></td>
    </tr>`;
  });
  html += '</tbody></table></div>';
  html += '<div class="prep-status-footnote threat-matrix-note">Click Likelihood/Impact cells to cycle. Risk = Likelihood x Impact. Prioritize HIGH/CRIT risk scenarios in your preparedness planning.</div>';
  document.getElementById('threat-matrix').innerHTML = html;
}

function cycleThreat(idx, type) {
  let saved = readJsonStorage(localStorage, 'nomad-threats', {});
  const key = `${idx}_${type}`;
  const current = saved[key] || 'low';
  saved[key] = THREAT_LEVELS[(THREAT_LEVELS.indexOf(current) + 1) % THREAT_LEVELS.length];
  localStorage.setItem('nomad-threats', JSON.stringify(saved));
  fetch('/api/settings', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({threat_matrix: JSON.stringify(saved)})});
  loadThreatMatrix();
}

/* ─── After-Action Review ─── */
function generateAAR() {
  const text = `===== AFTER-ACTION REVIEW =====
Event: ${document.getElementById('aar-event').value || 'N/A'}
Date: ${document.getElementById('aar-date').value || 'N/A'}

1. WHAT WAS PLANNED:
${document.getElementById('aar-planned').value || 'N/A'}

2. WHAT ACTUALLY HAPPENED:
${document.getElementById('aar-happened').value || 'N/A'}

3. SUSTAINS (What went well):
${document.getElementById('aar-well').value || 'N/A'}

4. IMPROVES (What needs improvement):
${document.getElementById('aar-improve').value || 'N/A'}

5. ACTION ITEMS:
${document.getElementById('aar-actions').value || 'None'}
===== END AAR =====`;
  const el = document.getElementById('aar-output');
  if (!el) return;
  el.textContent = text;
  el.style.display = 'block';
}

function copyAAR() {
  const el = document.getElementById('aar-output');
  if (!el || !el.textContent) generateAAR();
  const text = document.getElementById('aar-output')?.textContent || '';
  if (text) navigator.clipboard.writeText(text).then(() => toast('AAR copied', 'success'));
}

/* ─── Full Print Card (client-side with localStorage data) ─── */
async function printFullCard() {
  let contacts = [], summary = {categories:[]}, trend = {};
  try {
    [contacts, summary, trend] = await Promise.all([
      apiFetch('/api/contacts').catch(()=>[]),
      apiFetch('/api/inventory/summary').catch(()=>({categories:[]})),
      apiFetch('/api/weather/trend').catch(()=>({})),
    ]);
  } catch(e) { toast('Failed to load data for print card', 'error'); return; }
  // Get localStorage data
  let pace = readJsonStorage(localStorage, 'nomad-pace-plan', {});
  let fep = readJsonStorage(localStorage, 'nomad-fep', {});
  let fepMembers = readJsonStorage(localStorage, 'nomad-fep-members', []);
  if (!Array.isArray(fepMembers)) fepMembers = [];
  let sit = readJsonStorage(localStorage, 'nomad-sit-board', {});
  // Also try settings
  try {
    const s = await apiFetch('/api/settings');
    if (s.sit_board) Object.assign(sit, safeJsonParse(s.sit_board, {}));
  } catch(e) {}

  const sitColors = {green:'var(--green)',yellow:'var(--yellow)',orange:'var(--orange)',red:'var(--red)'};
  const sitLabels = {green:'GOOD',yellow:'CAUTION',orange:'CONCERN',red:'CRITICAL'};
  const now = new Date();

let h = `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>NOMAD Full Emergency Card</title>
  <style>@media print{@page{margin:0.4in;}}*{margin:0;padding:0;box-sizing:border-box;}
  body{font-family:Arial,sans-serif;font-size:10px;color:#111;line-height:1.3;}
  h1{font-size:14px;text-align:center;margin-bottom:2px;}h2{font-size:11px;background:#222;color:#fff;padding:2px 6px;margin:6px 0 3px;}
  .date{text-align:center;font-size:9px;color:#666;margin-bottom:4px;}
  table{width:100%;border-collapse:collapse;margin-bottom:4px;}th,td{border:1px solid #999;padding:2px 4px;text-align:left;font-size:9px;}
  th{background:#eee;font-weight:bold;}.warn{color:#993333;font-weight:bold;}
  .cols2{display:flex;gap:6px;}.cols2>div{flex:1;}.cols3{display:flex;gap:6px;}.cols3>div{flex:1;}
  .sit-row{display:flex;gap:3px;margin-bottom:4px;}
  .sit-box{flex:1;text-align:center;padding:2px;border:1px solid #999;font-weight:bold;font-size:8px;color:#fff;}
  .strong-cell{font-weight:bold}
  .print-footer{text-align:center;margin-top:6px;font-size:8px;color:#999;}
  </style></head><body>
<h1>NOMAD FIELD DESK - COMPREHENSIVE EMERGENCY CARD</h1>
  <div class="date">Generated: ${now.toLocaleString()} | KEEP ACCESSIBLE | Review quarterly</div>`;

  // Situation
  if (Object.keys(sit).length) {
    h += '<h2>SITUATION STATUS</h2><div class="sit-row">';
    ['security','water','food','medical','power','comms'].forEach(d => {
      const lvl = sit[d]||'green';
      h += `<div class="sit-box" style="background:${sitColors[lvl]||'var(--text-muted)'}">${d.toUpperCase()}<br>${sitLabels[lvl]||'?'}</div>`;
    });
    h += '</div>';
  }

  // Family Plan
  if (fep.meet1 || fep.route1 || fepMembers.length) {
    h += '<h2>FAMILY EMERGENCY PLAN</h2><div class="cols2"><div>';
    if (fep.meet1) h += `<div><strong>Meet (Home):</strong> ${escapeHtml(fep.meet1)}</div>`;
    if (fep.meet2) h += `<div><strong>Meet (Area):</strong> ${escapeHtml(fep.meet2)}</div>`;
    if (fep.meet3) h += `<div><strong>Meet (Out):</strong> ${escapeHtml(fep.meet3)}</div>`;
    if (fep.ooa) h += `<div><strong>Out-of-Area Contact:</strong> ${escapeHtml(fep.ooa)}</div>`;
    h += '</div><div>';
    if (fep.route1) h += `<div><strong>Route A:</strong> ${escapeHtml(fep.route1)}</div>`;
    if (fep.route2) h += `<div><strong>Route B:</strong> ${escapeHtml(fep.route2)}</div>`;
    if (fep.route3) h += `<div><strong>Route C:</strong> ${escapeHtml(fep.route3)}</div>`;
    if (fep.dest) h += `<div><strong>Destination:</strong> ${escapeHtml(fep.dest)}</div>`;
    h += '</div></div>';
    if (fepMembers.length) {
      h += '<table><tr><th>Name</th><th>Age</th><th>Blood</th><th>Conditions</th><th>Medications</th><th>Allergies</th></tr>';
      fepMembers.forEach(m => h += `<tr><td>${escapeHtml(m.name)}</td><td>${escapeHtml(m.age)}</td><td>${escapeHtml(m.blood)}</td><td>${escapeHtml(m.conditions)}</td><td>${escapeHtml(m.meds)}</td><td>${escapeHtml(m.allergies)}</td></tr>`);
      h += '</table>';
    }
  }

  // Contacts
  if (contacts.length) {
    h += '<h2>EMERGENCY CONTACTS</h2><table><tr><th>Name</th><th>Role</th><th>Callsign</th><th>Phone</th><th>Freq</th><th>Blood</th><th>Rally</th></tr>';
    contacts.forEach(c => h += `<tr><td>${escapeHtml(c.name)}</td><td>${escapeHtml(c.role)}</td><td>${escapeHtml(c.callsign)}</td><td>${escapeHtml(c.phone)}</td><td>${escapeHtml(c.freq)}</td><td>${escapeHtml(c.blood_type)}</td><td>${escapeHtml(c.rally_point)}</td></tr>`);
    h += '</table>';
  }

  // PACE Plan
  if (pace.p_method || pace.a_method) {
    h += '<h2>PACE COMMUNICATION PLAN</h2><table><tr><th>Level</th><th>Method</th><th>Details</th><th>When</th></tr>';
    [['PRIMARY',pace.p_method,pace.p_detail,pace.p_when],['ALTERNATE',pace.a_method,pace.a_detail,pace.a_when],
     ['CONTINGENCY',pace.c_method,pace.c_detail,pace.c_when],['EMERGENCY',pace.e_method,pace.e_detail,pace.e_when]]
    .forEach(([l,m,d,w]) => { if(m) h += `<tr><td class="strong-cell">${l}</td><td>${escapeHtml(m)}</td><td>${escapeHtml(d)}</td><td>${escapeHtml(w)}</td></tr>`; });
    h += '</table>';
  }

  // Supply summary + Key frequencies (same as before)
  h += `<div class="cols2"><div>`;
  if (summary.low_stock > 0 || summary.expiring_soon > 0 || summary.expired > 0) {
    h += '<h2>SUPPLY ALERTS</h2>';
    if (summary.expired > 0) h += `<div class="warn">${summary.expired} EXPIRED items</div>`;
    if (summary.expiring_soon > 0) h += `<div class="warn">${summary.expiring_soon} expiring within 30 days</div>`;
    if (summary.low_stock > 0) h += `<div class="warn">${summary.low_stock} below minimum quantity</div>`;
  }
  h += `<div>Total inventory: ${summary.total} items</div>`;
  h += '</div><div>';
  h += `<h2>KEY FREQUENCIES</h2><table>
  <tr><td>FRS Rally Ch 1</td><td>462.5625</td></tr><tr><td>FRS Emerg Ch 3</td><td>462.6125</td></tr>
  <tr><td>GMRS Emerg Ch 20</td><td>462.6750</td></tr><tr><td>CB Emerg Ch 9</td><td>27.065</td></tr>
  <tr><td>HAM 2m Call</td><td>146.520</td></tr><tr><td>HAM 2m Emerg</td><td>146.550</td></tr>
  <tr><td>NOAA Weather</td><td>162.400-.550</td></tr></table></div></div>`;

h += '<div class="print-footer">NOMAD Field Desk - Offline preparedness workspace - v' + VERSION + '</div>';
  h += '</body></html>';
  openAppFrameHTML('Emergency Card', h);
}
