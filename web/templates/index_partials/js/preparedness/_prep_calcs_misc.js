/* ─── Bleach Calculator ─── */
function calcBleach() {
  const pct = parseFloat(document.getElementById('bleach-pct').value);
  const gal = parseFloat(document.getElementById('bleach-gal').value) || 1;
  const cloudy = document.getElementById('bleach-clarity').value === 'cloudy';
  // EPA: 6% bleach = 8 drops/gal clear, 16 drops cloudy; 8.25% = 6 drops clear, 12 cloudy
  const dropsPerGal = pct <= 6 ? (cloudy ? 16 : 8) : (cloudy ? 12 : 6);
  const totalDrops = dropsPerGal * gal;
  const tsp = totalDrops / 76; // ~76 drops per teaspoon
  const ml = totalDrops * 0.05; // ~0.05 mL per drop
  document.getElementById('bleach-result').innerHTML = `
    <strong>${totalDrops} drops</strong> (~${tsp.toFixed(2)} tsp / ${ml.toFixed(1)} mL) of ${pct}% bleach<br>
    for <strong>${gal} gallon${gal!==1?'s':''}</strong> of ${cloudy?'cloudy':'clear'} water<br>
    <div class="copy-dim-note">
      Stir and wait <strong>30 minutes</strong>. Should have slight chlorine smell after waiting.
      If no smell, repeat dose and wait another 15 minutes.
      ${cloudy ? '<br>Pre-filter cloudy water through cloth/coffee filter first.' : ''}
    </div>`;
}

/* ─── Battery Life Calculator ─── */
function calcBattery() {
  const mah = parseInt(document.getElementById('batt-mah').value) || 0;
  const v = parseFloat(document.getElementById('batt-v').value) || 5;
  const watts = parseFloat(document.getElementById('batt-watts').value) || 1;
  const eff = parseFloat(document.getElementById('batt-eff').value) || 0.85;
  const wh = (mah / 1000) * v * eff;
  const hours = wh / watts;
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  document.getElementById('batt-result').innerHTML = `
    Battery capacity: <strong>${wh.toFixed(1)} Wh</strong> (usable)<br>
    Runtime at ${watts}W: <strong>${h}h ${m}m</strong><br>
    <div class="copy-dim-note">Common devices: Phone charging ~5-10W | LED lantern ~3-5W | Radio ~1-3W | Laptop ~30-65W | Router ~10-15W</div>`;
}

/* ─── Moon Phase Calculator ─── */
function calcMoon() {
  const dateStr = document.getElementById('moon-date').value;
  if (!dateStr) { document.getElementById('moon-result').innerHTML = 'Select a date.'; return; }
  const date = new Date(dateStr + 'T12:00:00');
  // Simplified moon phase calculation (synodic month = 29.53059 days)
  const known_new = new Date('2000-01-06T12:00:00'); // Known new moon
  const diff = (date - known_new) / 86400000; // days
  const cycle = 29.53059;
  const phase = ((diff % cycle) + cycle) % cycle;
  const phasePercent = Math.round(phase / cycle * 100);
  const phases = [
    {name:'New Moon', icon:'&#127761;', max:1.85}, {name:'Waxing Crescent', icon:'&#127762;', max:7.38},
    {name:'First Quarter', icon:'&#127763;', max:11.07}, {name:'Waxing Gibbous', icon:'&#127764;', max:14.77},
    {name:'Full Moon', icon:'&#127765;', max:18.46}, {name:'Waning Gibbous', icon:'&#127766;', max:22.15},
    {name:'Last Quarter', icon:'&#127767;', max:25.84}, {name:'Waning Crescent', icon:'&#127768;', max:29.53},
  ];
  const p = phases.find(p => phase <= p.max) || phases[0];
  const illumination = Math.round(50 * (1 - Math.cos(2 * Math.PI * phase / cycle)));
  const nextFull = cycle * (0.5 - phase / cycle + (phase > cycle/2 ? 1 : 0));
  const nextNew = cycle - phase;
  document.getElementById('moon-result').innerHTML = `
    <div class="calc-moon-summary">
      <span class="calc-moon-icon">${p.icon}</span>
      <div class="calc-moon-body">
        <div class="calc-moon-title">${p.name}</div>
        <div class="calc-moon-meta">${illumination}% illuminated | Day ${Math.round(phase)} of ${cycle.toFixed(0)}-day cycle</div>
        <div class="calc-moon-note">Next full: ~${Math.round(nextFull)} days | Next new: ~${Math.round(nextNew)} days</div>
      </div>
    </div>
    <div class="calc-moon-footnote">Best fishing/hunting: 2 days before and after full/new moon. Best stealth movement: new moon (darkest).</div>`;
}

/* ─── Coordinate Converter ─── */
function convertCoords() {
  const lat = parseFloat(document.getElementById('coord-lat').value) || 0;
  const lng = parseFloat(document.getElementById('coord-lng').value) || 0;
  // Decimal degrees
  const dd = `${Math.abs(lat).toFixed(6)}${lat >= 0 ? 'N' : 'S'}, ${Math.abs(lng).toFixed(6)}${lng >= 0 ? 'E' : 'W'}`;
  // DMS
  const toDMS = (d) => { const abs = Math.abs(d); const deg = Math.floor(abs); const min = Math.floor((abs-deg)*60); const sec = ((abs-deg)*60-min)*60; return `${deg}° ${min}' ${sec.toFixed(1)}"`; };
  const dms = `${toDMS(lat)} ${lat>=0?'N':'S'}, ${toDMS(lng)} ${lng>=0?'E':'W'}`;
  // UTM (simplified)
  const zoneNum = Math.floor((lng + 180) / 6) + 1;
  const zoneLetter = 'CDEFGHJKLMNPQRSTUVWX'[Math.floor((lat + 80) / 8)] || '?';
  // MGRS-style grid reference
  const mgrsApprox = `${zoneNum}${zoneLetter}`;
  document.getElementById('coord-result').innerHTML = `
    <div class="coords-result-block">
      <div><strong>Decimal:</strong> ${dd}</div>
      <div><strong>DMS:</strong> ${dms}</div>
      <div><strong>UTM Zone:</strong> ${mgrsApprox} (Zone ${zoneNum}${zoneLetter})</div>
      <div><strong>Google Maps:</strong> ${lat.toFixed(6)}, ${lng.toFixed(6)}</div>
    </div>`;
}

/* ─── Travel Time Calculator ─── */
function calcTravel() {
  const dist = parseFloat(document.getElementById('travel-dist').value) || 0;
  const speeds = {walk:3, walk_loaded:2, run:6, horse:6, bike:12, vehicle:30, vehicle_offroad:10};
  const mode = document.getElementById('travel-mode').value;
  const terrain = parseFloat(document.getElementById('travel-terrain').value);
  const baseSpeed = speeds[mode] || 3;
  const adjustedSpeed = baseSpeed / terrain;
  const hours = dist / adjustedSpeed;
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  // Calories burned
  const calPerMile = {walk:80, walk_loaded:120, run:100, horse:40, bike:45, vehicle:0, vehicle_offroad:0};
  const cal = Math.round(dist * (calPerMile[mode] || 0) * terrain);
  // Water needed (0.5L per hour of exertion)
  const waterL = (hours * 0.5).toFixed(1);
  document.getElementById('travel-result').innerHTML = `
    <strong>${h}h ${m}m</strong> estimated travel time<br>
    Effective speed: <strong>${adjustedSpeed.toFixed(1)} mph</strong> (${baseSpeed} mph base, ${terrain}x terrain factor)<br>
    ${cal > 0 ? `Calories burned: ~<strong>${cal}</strong> | Water needed: ~<strong>${waterL}L</strong>` : 'Motorized — minimal physical exertion'}
    <div class="copy-dim-note">Add 30% for nighttime travel. Add rest stops: 10 min per hour for walking, 15 min per 2 hours driving.</div>`;
}

/* ─── Calorie Tracker ─── */
let _calLog; try { _calLog = JSON.parse(localStorage.getItem('nomad-cal-log') || '[]'); } catch(e) { _calLog = []; }
let _calLogDate = new Date().toISOString().slice(0,10);

function addCalEntry() {
  const item = document.getElementById('cal-item').value.trim();
  const amount = parseInt(document.getElementById('cal-amount').value) || 0;
  if (!item) { toast('Enter a food item', 'warning'); return; }
  if (!amount) { toast('Enter calorie amount', 'warning'); return; }
  const today = new Date().toISOString().slice(0,10);
  if (today !== _calLogDate) { _calLog = []; _calLogDate = today; }
  _calLog.push({item, cal: amount, time: new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})});
  localStorage.setItem('nomad-cal-log', JSON.stringify(_calLog));
  localStorage.setItem('nomad-cal-date', _calLogDate);
  document.getElementById('cal-item').value = '';
  updateCalTracker();
}

function updateCalTracker() {
  const today = new Date().toISOString().slice(0,10);
  const savedDate = localStorage.getItem('nomad-cal-date');
  if (savedDate !== today) { _calLog = []; _calLogDate = today; }
  const target = parseInt(document.getElementById('cal-target').value) || 2000;
  const total = _calLog.reduce((s, e) => s + e.cal, 0);
  const pct = Math.min(100, Math.round(total / target * 100));
  const remaining = Math.max(0, target - total);
  const color = total >= target ? 'var(--green)' : total >= target * 0.5 ? 'var(--orange)' : 'var(--red)';
  let html = `<div class="calorie-track-summary">
    <div class="calorie-track-head">
      <span class="calorie-track-total" style="--calorie-tone:${color};">${total} / ${target} cal (${pct}%)</span>
      <span class="calorie-track-remaining">${remaining} remaining</span>
    </div>
    <div class="calorie-track-bar">
      <div class="calorie-track-fill" style="--calorie-pct:${pct}%;--calorie-tone:${color};"></div>
    </div>
  </div>`;
  if (_calLog.length) {
    html += _calLog.map(e => `<div class="calorie-track-entry"><span>${e.time} — ${escapeHtml(e.item)}</span><span class="calorie-track-value">${e.cal} cal</span></div>`).join('');
    html += `<button type="button" class="btn btn-sm calorie-track-clear" data-prep-action="clear-cal-log">Clear Today</button>`;
  }
  document.getElementById('cal-tracker-result').innerHTML = html;
}

/* ─── Skills Matrix ─── */
async function loadSkillsMatrix() {
  try {
    const contacts = await (await fetch('/api/contacts')).json();
    if (!contacts.length) { document.getElementById('skills-matrix').innerHTML = '<div class="text-muted text-size-12">Add contacts with skills to see the matrix.</div>'; return; }
    // Extract all unique skills
    const allSkills = new Set();
    contacts.forEach(c => { if (c.skills) c.skills.split(',').map(s => s.trim().toLowerCase()).filter(Boolean).forEach(s => allSkills.add(s)); });
    if (!allSkills.size) { document.getElementById('skills-matrix').innerHTML = '<div class="text-muted text-size-12">No skills listed in contacts. Edit contacts to add skills.</div>'; return; }
    const skills = [...allSkills].sort();
    let html = '<table><thead><tr><th>Name</th>';
    skills.forEach(s => html += `<th>${s.charAt(0).toUpperCase()+s.slice(1)}</th>`);
    html += '</tr></thead><tbody>';
    contacts.forEach(c => {
      const mySkills = c.skills ? c.skills.split(',').map(s => s.trim().toLowerCase()) : [];
      html += `<tr><td class="skills-matrix-name">${escapeHtml(c.name)}</td>`;
      skills.forEach(s => {
        const has = mySkills.includes(s);
        html += `<td class="${has ? 'has-skill' : 'no-skill'}">${has ? 'Y' : '-'}</td>`;
      });
      html += '</tr>';
    });
    // Gap analysis row
    html += '<tr class="gap-row"><td class="skills-matrix-gap-label">Coverage</td>';
    skills.forEach(s => {
      const count = contacts.filter(c => c.skills && c.skills.toLowerCase().includes(s)).length;
      html += `<td>${count === 0 ? 'GAP' : count}</td>`;
    });
    html += '</tr></tbody></table>';
    document.getElementById('skills-matrix').innerHTML = html;
  } catch(e) {}
}

/* ─── PACE Plan ─── */
let _paceSaveTimer;
function savePace() {
  const pace = {};
  ['p','a','c','e'].forEach(l => {
    ['method','detail','when'].forEach(f => {
      pace[`${l}_${f}`] = document.getElementById(`pace-${l}-${f}`).value;
    });
  });
  localStorage.setItem('nomad-pace-plan', JSON.stringify(pace));
  // Debounced server-side persist for backup
  clearTimeout(_paceSaveTimer);
  _paceSaveTimer = setTimeout(() => {
    fetch('/api/settings', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({pace_plan: JSON.stringify(pace)})});
  }, 1000);
}

async function loadPace() {
  try {
    // Try localStorage first (fast), then server (backup source)
    let pace = {};
    try { pace = JSON.parse(localStorage.getItem('nomad-pace-plan') || '{}'); } catch(e) {}
    if (!Object.keys(pace).length) {
      try {
        const settings = await (await fetch('/api/settings')).json();
        if (settings.pace_plan) {
          pace = JSON.parse(settings.pace_plan);
          localStorage.setItem('nomad-pace-plan', JSON.stringify(pace));
        }
      } catch(e) {}
    }
    ['p','a','c','e'].forEach(l => {
      ['method','detail','when'].forEach(f => {
        const el = document.getElementById(`pace-${l}-${f}`);
        if (el && pace[`${l}_${f}`]) el.value = pace[`${l}_${f}`];
      });
    });
  } catch(e) {}
}
