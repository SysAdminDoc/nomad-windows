/* ─── Burn Rate Dashboard ─── */
async function loadBurnRate() {
  try {
    const data = await safeFetch('/api/inventory/burn-rate', {}, {});
    const el = document.getElementById('burn-rate-dash');
    if (!data || typeof data !== 'object' || !Object.keys(data).length) { el.innerHTML = ''; return; }
    let html = '<div class="prep-resource-summary-grid utility-summary-grid">';
    for (const [cat, info] of Object.entries(data).sort((a,b) => (a[1].min_days||999) - (b[1].min_days||999))) {
      const days = info.min_days;
      const toneClass = days === null ? 'utility-summary-card-muted' : days < 3 ? 'prep-summary-card-danger' : days < 7 ? 'utility-summary-card-alert' : days < 14 ? 'prep-summary-card-warn' : 'prep-summary-card-ok';
      html += `<div class="prep-summary-card utility-summary-card ${toneClass}">
        <div class="prep-summary-meta">${escapeHtml(cat)}</div>
        <div class="prep-summary-value${days === null ? ' utility-summary-value-muted' : ''}">${days !== null ? days : '--'}</div>
        <div class="utility-summary-caption">days left</div>
      </div>`;
    }
    html += '</div>';
    el.innerHTML = html;
  } catch(e) {}
}

/* ─── Solar Calculator ─── */
function calcSolar() {
  const lat = parseFloat(document.getElementById('solar-lat').value) || 0;
  const lng = parseFloat(document.getElementById('solar-lng').value) || 0;
  const dateStr = document.getElementById('solar-date').value;
  if (!dateStr) {
    document.getElementById('solar-result').innerHTML = utilityEmptyState('Select a date.');
    return;
  }
  const date = new Date(dateStr + 'T12:00:00');
  const doy = Math.floor((date - new Date(date.getFullYear(),0,0)) / 86400000);
  const rad = Math.PI / 180;
  const B = (360/365) * (doy - 81) * rad;
  const decl = Math.asin(0.39779 * Math.sin(B));
  const latRad = lat * rad;
  const cosH = -Math.tan(latRad) * Math.tan(decl);
  if (cosH > 1) {
    document.getElementById('solar-result').innerHTML = utilityEmptyState('No sunrise — polar night at this latitude and date.');
    return;
  }
  if (cosH < -1) {
    document.getElementById('solar-result').innerHTML = utilityEmptyState('No sunset — midnight sun at this latitude and date.');
    return;
  }
  const H = Math.acos(cosH) / rad;
  const dayLengthHrs = 2 * H / 15;
  const eot = 9.87 * Math.sin(2*B) - 7.53 * Math.cos(B) - 1.5 * Math.sin(B);
  const solarNoonUTC = 720 - 4 * lng - eot;
  const sunriseUTC = solarNoonUTC - dayLengthHrs * 30;
  const sunsetUTC = solarNoonUTC + dayLengthHrs * 30;
  const tzOffset = Math.round(lng / 15) * 60;
  const toLocal = (utcMin) => { let m = utcMin + tzOffset; if (m < 0) m += 1440; if (m >= 1440) m -= 1440; const h = Math.floor(m / 60); const min = Math.round(m % 60); return `${String(h).padStart(2,'0')}:${String(min).padStart(2,'0')}`; };
  const nightHrs = 24 - dayLengthHrs;
  const goldenAM = sunriseUTC + 60;
  const goldenPM = sunsetUTC - 60;
  document.getElementById('solar-result').innerHTML = `
    <div class="prep-dashboard-grid utility-summary-grid">
      <div class="prep-summary-card utility-summary-card"><div class="prep-summary-meta">Sunrise</div><div class="prep-summary-value">${toLocal(sunriseUTC)}</div></div>
      <div class="prep-summary-card utility-summary-card"><div class="prep-summary-meta">Solar Noon</div><div class="prep-summary-value">${toLocal(solarNoonUTC)}</div></div>
      <div class="prep-summary-card utility-summary-card"><div class="prep-summary-meta">Sunset</div><div class="prep-summary-value">${toLocal(sunsetUTC)}</div></div>
      <div class="prep-summary-card utility-summary-card"><div class="prep-summary-meta">Day Length</div><div class="prep-summary-value utility-summary-value-split">${Math.floor(dayLengthHrs)}h ${Math.round((dayLengthHrs%1)*60)}m</div></div>
      <div class="prep-summary-card utility-summary-card"><div class="prep-summary-meta">Night Length</div><div class="prep-summary-value utility-summary-value-split">${Math.floor(nightHrs)}h ${Math.round((nightHrs%1)*60)}m</div></div>
      <div class="prep-summary-card utility-summary-card"><div class="prep-summary-meta">Golden Hour</div><div class="prep-summary-value utility-summary-value-split">${toLocal(sunriseUTC)}-${toLocal(goldenAM)}<br>${toLocal(goldenPM)}-${toLocal(sunsetUTC)}</div></div>
    </div>
    <div class="prep-status-footnote utility-note">Times based on longitude timezone (UTC${tzOffset>=0?'+':''}${tzOffset/60}). Adjust for DST. Accuracy ~10min.</div>`;
}

function getSolarLocation() {
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(pos => {
      document.getElementById('solar-lat').value = pos.coords.latitude.toFixed(4);
      document.getElementById('solar-lng').value = pos.coords.longitude.toFixed(4);
      document.getElementById('solar-date').value = new Date().toISOString().slice(0,10);
      calcSolar();
      toast('Location acquired', 'success');
    }, () => toast('Location access denied', 'warning'));
  } else { toast('Geolocation not available', 'warning'); }
}

/* ─── Planting Calendar ─── */
const PLANT_DATA = {
  crops: ['Tomatoes','Peppers','Lettuce','Spinach','Carrots','Beans','Peas','Squash','Corn','Potatoes','Onions','Garlic','Beets','Radishes','Cucumbers','Kale','Broccoli','Cabbage','Watermelon','Herbs (Basil)'],
  zones: {
    '4': [[5,6],[5,6],[4,5],[4,5],[5,6],[5,6],[4,5],[5,6],[5,6],[5,5],[4,5],[9,10],[5,6],[4,8],[5,6],[4,5],[4,5],[4,5],[5,6],[5,6]],
    '5': [[5,6],[5,6],[3,5],[3,5],[4,6],[5,6],[3,5],[5,6],[5,6],[4,5],[3,4],[9,10],[4,6],[3,9],[5,6],[3,5],[3,5],[3,5],[5,6],[5,6]],
    '6': [[4,5],[4,5],[3,4],[3,4],[3,6],[4,6],[2,4],[4,6],[4,5],[3,4],[2,4],[10,11],[3,6],[3,9],[4,6],[2,4],[2,4],[2,4],[4,6],[4,6]],
    '7': [[4,5],[4,5],[2,4],[2,4],[2,5],[3,5],[1,3],[4,5],[4,5],[2,3],[1,3],[10,11],[2,5],[2,10],[4,5],[1,3],[1,3],[1,3],[4,5],[4,5]],
    '8': [[3,4],[3,4],[1,3],[1,3],[1,4],[3,5],[1,2],[3,5],[3,4],[1,3],[1,2],[10,12],[1,4],[1,10],[3,5],[1,3],[1,3],[1,3],[3,5],[3,5]],
    '9': [[2,3],[2,3],[10,2],[10,2],[1,3],[2,4],[11,1],[2,4],[2,3],[1,2],[10,1],[11,12],[1,3],[1,11],[2,4],[10,2],[10,2],[10,2],[3,4],[2,4]],
  }
};
const MONTH_NAMES = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
function showPlantZone() {
  const zone = document.getElementById('plant-zone').value;
  const zoneData = PLANT_DATA.zones[zone];
  if (!zoneData) return;
  let html = '<div class="prep-inline-table-shell plant-calendar-table-shell"><table class="freq-table prep-inline-table plant-calendar-table"><thead><tr><th>Crop</th>';
  for (let m = 1; m <= 12; m++) html += `<th class="plant-calendar-month">${MONTH_NAMES[m]}</th>`;
  html += '</tr></thead><tbody>';
  PLANT_DATA.crops.forEach((crop, i) => {
    const [s, e] = zoneData[i];
    html += `<tr><td class="plant-calendar-crop">${crop}</td>`;
    for (let m = 1; m <= 12; m++) {
      const inRange = s <= e ? (m >= s && m <= e) : (m >= s || m <= e);
      html += `<td class="plant-calendar-cell ${inRange ? 'is-active' : 'is-idle'}">${inRange ? 'SOW' : '-'}</td>`;
    }
    html += '</tr>';
  });
  html += '</tbody></table></div><div class="prep-status-footnote plant-calendar-note">SOW = direct outdoor sowing window. Start transplants indoors 4-6 weeks earlier. Garlic planted in fall.</div>';
  document.getElementById('plant-calendar').innerHTML = html;
}

/* ─── Situation Board ─── */
const SIT_LEVELS = ['green','yellow','orange','red'];
const SIT_LABELS = {green:'Good', yellow:'Caution', orange:'Concern', red:'Critical'};

function cycleSitLevel(cell) {
  const current = cell.dataset.level;
  const next = SIT_LEVELS[(SIT_LEVELS.indexOf(current) + 1) % SIT_LEVELS.length];
  cell.dataset.level = next;
  cell.querySelector('.sit-level').textContent = SIT_LABELS[next];
  saveSitBoard();
}

async function saveSitBoard() {
  const levels = {};
  document.querySelectorAll('.sit-cell').forEach(c => levels[c.dataset.domain] = c.dataset.level);
  try {
    await fetch('/api/settings', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({sit_board: JSON.stringify(levels)})});
  } catch(e) { toast('Failed to save situation board', 'error'); }
}

async function loadSitBoard() {
  try {
    const s = await safeFetch('/api/settings', {}, {});
    if (s.sit_board) {
      const levels = safeJsonParse(s.sit_board, {});
      document.querySelectorAll('.sit-cell').forEach(c => {
        const lvl = levels[c.dataset.domain] || 'green';
        c.dataset.level = lvl;
        c.querySelector('.sit-level').textContent = SIT_LABELS[lvl];
      });
    }
  } catch(e) {}
}

/* ─── Incident Log ─── */
async function loadIncidents() {
  const cat = document.getElementById('inc-filter').value;
  let url = '/api/incidents?limit=200';
  if (cat) url += `&category=${encodeURIComponent(cat)}`;
  try {
    const items = await safeFetch(url, {}, []);
    if (!Array.isArray(items)) throw new Error('invalid incidents payload');
    const el = document.getElementById('incidents-list');
    if (!items.length) {
      el.innerHTML = '<div class="prep-empty-state">No incidents logged. Use this to track events during an emergency.</div>';
      return;
    }
    const criticalCount = items.filter(i => i.severity === 'critical').length;
    const warningCount = items.filter(i => i.severity === 'warning' || i.severity === 'alert').length;
    const latest = items[0];
    el.innerHTML = `
      <div class="incident-summary-grid">
        <div class="incident-summary-card">
          <span class="incident-summary-kicker">Entries</span>
          <strong class="incident-summary-value">${items.length}</strong>
          <span class="incident-summary-note">Current filtered timeline.</span>
        </div>
        <div class="incident-summary-card">
          <span class="incident-summary-kicker">Critical</span>
          <strong class="incident-summary-value">${criticalCount}</strong>
          <span class="incident-summary-note">Events requiring immediate attention.</span>
        </div>
        <div class="incident-summary-card">
          <span class="incident-summary-kicker">Warning + Alert</span>
          <strong class="incident-summary-value">${warningCount}</strong>
          <span class="incident-summary-note">Events that still need review.</span>
        </div>
        <div class="incident-summary-card">
          <span class="incident-summary-kicker">Latest event</span>
          <strong class="incident-summary-value incident-summary-value-text">${escapeHtml(latest.category)}</strong>
          <span class="incident-summary-note">${new Date(latest.created_at).toLocaleDateString([], {month:'short', day:'numeric'})}</span>
        </div>
      </div>
      <div class="incident-records">
      ${items.map(i => {
      const t = new Date(i.created_at);
      const ts = t.toLocaleDateString([], {month:'short',day:'numeric'}) + ' ' + t.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
      return `<article class="incident-item incident-record incident-record-${i.severity}">
        <div class="incident-record-head">
          <div class="incident-record-meta">
            <span class="incident-sev ${i.severity}">${i.severity}</span>
            <span class="incident-cat">${i.category}</span>
            <span class="incident-time">${ts}</span>
          </div>
          <button type="button" class="incident-del incident-record-delete" data-prep-action="delete-incident" data-incident-id="${i.id}" aria-label="Delete incident">x</button>
        </div>
        <div class="incident-desc incident-record-copy">${escapeHtml(i.description)}</div>
      </article>`;
    }).join('')}
      </div>
    `;
  } catch(e) {
    document.getElementById('incidents-list').innerHTML = '<div class="prep-empty-state prep-error-state">Failed to load incidents</div>';
  }
}

async function logIncident() {
  const desc = document.getElementById('inc-desc').value.trim();
  if (!desc) { toast('Enter an event description', 'warning'); return; }
  const severity = document.getElementById('inc-severity').value;
  const category = document.getElementById('inc-category').value;
  const resp = await fetch('/api/incidents', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({severity, category, description: desc})});
  if (!resp.ok) { toast('Failed to log event', 'error'); return; }
  document.getElementById('inc-desc').value = '';
  toast('Event logged', severity === 'critical' ? 'error' : severity === 'alert' ? 'warning' : 'success');
  loadIncidents();
}

async function deleteIncident(id) {
  if (!confirm('Delete this incident entry?')) return;
  try {
    const r = await fetch(`/api/incidents/${id}`, {method:'DELETE'});
    if (!r.ok) throw new Error('Delete failed');
    loadIncidents();
  } catch(e) { toast('Failed to delete incident', 'error'); }
}

async function clearIncidents() {
  if (!confirm('Clear all incident log entries? This cannot be undone.')) return;
  try {
    const r = await fetch('/api/incidents/clear', {method:'POST'});
    if (!r.ok) { toast('Failed to clear incidents', 'error'); return; }
    toast('Incident log cleared', 'warning');
    loadIncidents();
  } catch(e) { console.error(e); toast('Failed to clear incidents', 'error'); }
}

/* ─── Watch Schedule ─── */
function calcWatch() {
  const names = document.getElementById('watch-names').value.split(',').map(n => n.trim()).filter(Boolean);
  const shift = parseInt(document.getElementById('watch-shift').value) || 4;
  const days = parseInt(document.getElementById('watch-days').value) || 3;
  const startStr = document.getElementById('watch-start').value || '18:00';
  if (names.length < 2) {
    document.getElementById('watch-result').innerHTML = utilityEmptyState('Enter at least 2 team members.');
    return;
  }

  const totalHours = days * 24;
  const totalShifts = Math.ceil(totalHours / shift);
  const [startH, startM] = startStr.split(':').map(Number);

  let html = '<div class="prep-inline-table-shell watch-result-table-shell"><table class="freq-table prep-inline-table watch-result-table"><thead><tr><th>Shift</th><th>Day</th><th>Start</th><th>End</th><th>On Duty</th></tr></thead><tbody>';
  for (let i = 0; i < totalShifts; i++) {
    const person = names[i % names.length];
    const startMins = (startH * 60 + startM + i * shift * 60);
    const endMins = startMins + shift * 60;
    const dayNum = Math.floor(startMins / (24*60)) + 1;
    const sh = Math.floor((startMins % (24*60)) / 60);
    const sm = startMins % 60;
    const eh = Math.floor((endMins % (24*60)) / 60);
    const em = endMins % 60;
    const fmt = (h,m) => `${String(h%24).padStart(2,'0')}:${String(m).padStart(2,'0')}`;
    html += `<tr><td>${i+1}</td><td>Day ${dayNum}</td><td>${fmt(sh,sm)}</td><td>${fmt(eh,em)}</td><td class="watch-result-member">${escapeHtml(person)}</td></tr>`;
  }
  html += '</tbody></table></div>';

  // Summary
  const shiftsPerPerson = Math.ceil(totalShifts / names.length);
  const hoursPerPerson = shiftsPerPerson * shift;
  const restPerCycle = (names.length - 1) * shift;
  html += `<div class="prep-status-footnote watch-result-note">
    ${names.length} people, ${shift}h shifts, ${days} days = ${totalShifts} total shifts.
    Each person: ~${hoursPerPerson}h on duty, ${restPerCycle}h rest between shifts.
  </div>`;
  document.getElementById('watch-result').innerHTML = html;
}

/* ─── Emergency Protocols ─── */
function toggleProtocol(header) {
  const expanded = !header.classList.contains('open');
  header.classList.toggle('open', expanded);
  header.setAttribute('aria-expanded', expanded ? 'true' : 'false');
  const body = header.nextElementSibling;
  body.classList.toggle('open', expanded);
}
function toggleAllProtocols(expand) {
  document.querySelectorAll('#psub-protocols .protocol-header').forEach(h => {
    const body = h.nextElementSibling;
    h.classList.toggle('open', expand);
    h.setAttribute('aria-expanded', expand ? 'true' : 'false');
    body.classList.toggle('open', expand);
  });
}
function filterProtocols() {
  const q = document.getElementById('proto-search').value.toLowerCase();
  document.querySelectorAll('#psub-protocols .protocol-card').forEach(card => {
    const text = card.textContent.toLowerCase();
    card.style.display = !q || text.includes(q) ? '' : 'none';
  });
}

function printWalletCard() {
  const v = id => (document.getElementById(id)?.value || '').trim();
  const esc = s => s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  const html = `<!DOCTYPE html><html><head><title>Emergency Wallet Card</title>
<style>@page{size:3.5in 2.5in;margin:0}body{margin:0;padding:0;font-family:Arial,sans-serif}
.card{width:3.3in;height:2.3in;border:2px solid #333;border-radius:6px;padding:4px 8px;font-size:7pt;line-height:1.4;page-break-after:always;box-sizing:border-box}
.card h1{font-size:9pt;margin:0 0 2px;text-align:center;border-bottom:1px solid #666;padding-bottom:2px}
.row{display:flex;gap:4px}.col{flex:1}.lbl{font-weight:bold;font-size:6pt;color:#666;text-transform:uppercase}.val{font-size:7.5pt}
.warn{background:#ffeeee;border:1px solid #c00;border-radius:3px;padding:2px 4px;margin-top:3px;font-size:6.5pt;text-align:center}
.val-critical{font-size:11pt;font-weight:bold;color:#c00}
.val-alert{color:#c00;font-weight:bold}
.quickref{font-size:7pt;line-height:1.5}
</style></head><body>
<div class="card">
<h1>EMERGENCY INFORMATION</h1>
<div class="row"><div class="col"><div class="lbl">Name</div><div class="val">${esc(v('wc-name'))}</div></div>
<div class="col"><div class="lbl">Blood Type</div><div class="val val-critical">${esc(v('wc-blood'))}</div></div></div>
<div class="row"><div class="col"><div class="lbl">Allergies</div><div class="val val-alert">${esc(v('wc-allergies')) || 'NKDA'}</div></div>
<div class="col"><div class="lbl">Medications</div><div class="val">${esc(v('wc-meds')) || 'None'}</div></div></div>
<div class="row"><div class="col"><div class="lbl">Emergency Contact 1</div><div class="val">${esc(v('wc-ec1'))}</div></div>
<div class="col"><div class="lbl">Emergency Contact 2</div><div class="val">${esc(v('wc-ec2'))}</div></div></div>
<div class="row"><div class="col"><div class="lbl">Rally Point 1</div><div class="val">${esc(v('wc-rp1'))}</div></div>
<div class="col"><div class="lbl">Rally Point 2</div><div class="val">${esc(v('wc-rp2'))}</div></div></div>
<div class="row"><div class="col"><div class="lbl">Insurance</div><div class="val">${esc(v('wc-insurance'))}</div></div>
<div class="col"><div class="lbl">Radio</div><div class="val">${esc(v('wc-radio'))}</div></div></div>
<div class="warn">IF UNCONSCIOUS: Check allergies above before administering any medication</div>
</div>
<div class="card">
<h1>QUICK REFERENCE</h1>
<div class="quickref">
<div><b>CPR:</b> 30 compressions (2" deep, 100-120/min) : 2 breaths. "Stayin Alive" tempo.</div>
<div><b>Choking:</b> 5 back blows + 5 abdominal thrusts. Repeat until clear.</div>
<div><b>Bleeding:</b> Direct pressure + pack wound + tourniquet 2" above (note time).</div>
<div><b>Shock:</b> Lay flat, elevate legs 12", keep warm, no food/water.</div>
<div><b>Burns:</b> Cool water 10-20 min. Cover loosely. No ice, no butter.</div>
<div><b>Fracture:</b> Splint as found. Immobilize joint above and below.</div>
<div><b>Water:</b> Boil 1 min (3 min &gt;6500ft). Bleach: 8 drops/gal, wait 30 min.</div>
<div><b>SOS:</b> 3 of anything (fires, whistles, flashes). Mirror signal 50+ miles.</div>
<div><b>Rule of 3:</b> 3 min air, 3 hrs exposure, 3 days water, 3 weeks food.</div>
</div></div></body></html>`;
  const frame = document.createElement('iframe');
  frame.style.cssText = 'position:fixed;top:-9999px;left:-9999px;width:0;height:0';
  document.body.appendChild(frame);
  frame.contentDocument.write(html);
  frame.contentDocument.close();
  setTimeout(() => { frame.contentWindow.print(); setTimeout(() => frame.remove(), 1000); }, 250);
}
