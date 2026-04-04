/* ─── Family Emergency Plan ─── */
let _fepMembers; try { _fepMembers = JSON.parse(localStorage.getItem('nomad-fep-members') || '[]'); } catch(e) { _fepMembers = []; }

function saveFEP() {
  const fields = ['meet1','meet2','meet3','ooa','route1','route2','route3','dest','ins-home','ins-auto','doctor','vet','utility','safe'];
  const data = {};
  fields.forEach(f => { const el = document.getElementById('fep-'+f); if (el) data[f] = el.value; });
  localStorage.setItem('nomad-fep', JSON.stringify(data));
}

function loadFEP() {
  try {
    const data = JSON.parse(localStorage.getItem('nomad-fep') || '{}');
    Object.entries(data).forEach(([k, v]) => { const el = document.getElementById('fep-'+k); if (el) el.value = v; });
  } catch(e) {}
  try { _fepMembers = JSON.parse(localStorage.getItem('nomad-fep-members') || '[]'); } catch(e) { _fepMembers = []; }
  renderFEPMembers();
}

function addFEPMember() {
  _fepMembers.push({name:'', age:'', blood:'', conditions:'', meds:'', allergies:'', id: Date.now()});
  localStorage.setItem('nomad-fep-members', JSON.stringify(_fepMembers));
  renderFEPMembers();
}

function updateFEPMember(id, field, value) {
  const m = _fepMembers.find(m => m.id === id);
  if (m) { m[field] = value; localStorage.setItem('nomad-fep-members', JSON.stringify(_fepMembers)); }
}

function deleteFEPMember(id) {
  _fepMembers = _fepMembers.filter(m => m.id !== id);
  localStorage.setItem('nomad-fep-members', JSON.stringify(_fepMembers));
  renderFEPMembers();
}

function renderFEPMembers() {
  const el = document.getElementById('fep-members');
  if (!el) return;
  if (!_fepMembers.length) { el.innerHTML = '<div class="fep-member-empty">No members added yet.</div>'; return; }
  el.innerHTML = _fepMembers.map(m => `
    <div class="fep-member-row">
      <input class="fep-input" value="${escapeAttr(m.name)}" placeholder="Name" data-input-action="update-fep-member" data-fep-member-id="${m.id}" data-fep-member-field="name">
      <input class="fep-input" value="${escapeAttr(m.age)}" placeholder="Age" data-input-action="update-fep-member" data-fep-member-id="${m.id}" data-fep-member-field="age">
      <input class="fep-input" value="${escapeAttr(m.blood)}" placeholder="Blood" data-input-action="update-fep-member" data-fep-member-id="${m.id}" data-fep-member-field="blood">
      <input class="fep-input" value="${escapeAttr(m.conditions)}" placeholder="Conditions" data-input-action="update-fep-member" data-fep-member-id="${m.id}" data-fep-member-field="conditions">
      <input class="fep-input" value="${escapeAttr(m.meds)}" placeholder="Medications" data-input-action="update-fep-member" data-fep-member-id="${m.id}" data-fep-member-field="meds">
      <input class="fep-input" value="${escapeAttr(m.allergies)}" placeholder="Allergies" data-input-action="update-fep-member" data-fep-member-id="${m.id}" data-fep-member-field="allergies">
      <button type="button" class="prep-inline-delete-btn" data-prep-action="delete-fep-member" data-fep-member-id="${m.id}" aria-label="Remove family member">x</button>
    </div>`).join('');
}

/* ─── Shelter Defense Assessment ─── */
const SHELTER_CRITERIA = [
  'Line of sight (visibility of approaches)',
  'Cover from gunfire (brick/concrete)',
  'Concealment (not easily spotted)',
  'Multiple exits/escape routes',
  'Water access within perimeter',
  'Food storage capacity',
  'Heating without grid power',
  'Defensible entry points (choke points)',
  'Communication capability (radio/antenna)',
  'Medical treatment area',
  'Storage for supplies/equipment',
  'Sanitation plan (latrine/waste)',
  'Fire resistance of structure',
  'Flooding/drainage risk',
  'Distance from high-threat areas',
];
const SHELTER_SCORES = {green:3, yellow:2, red:1};
const SHELTER_COLORS = {green:'var(--green)',yellow:'var(--warning)',red:'var(--red)'};
function prepToneClass(value, map) { return map[value] || 'text-muted'; }
function fuelToneClass(fuel) { return fuel > 50 ? 'text-green' : fuel > 25 ? 'text-orange' : 'text-red'; }

function loadShelterAssess() {
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem('nomad-shelter') || '{}'); } catch(e) {}
  const el = document.getElementById('shelter-assess');
  if (!el) return;
  el.innerHTML = SHELTER_CRITERIA.map((c, i) => {
    const level = saved[i] || 'red';
    return `<div class="shelter-assess-row" role="button" tabindex="0" data-prep-action="cycle-shelter" data-shelter-index="${i}">
      <span class="shelter-assess-copy">${c}</span>
      <span class="shelter-assess-status" style="--shelter-tone:${SHELTER_COLORS[level]};">${level.toUpperCase()}</span>
    </div>`;
  }).join('');
  // Score
  let total = 0;
  SHELTER_CRITERIA.forEach((_, i) => total += SHELTER_SCORES[saved[i] || 'red']);
  const max = SHELTER_CRITERIA.length * 3;
  const pct = Math.round(total / max * 100);
  const scoreToneClass = pct >= 70 ? 'text-green' : pct >= 40 ? 'text-orange' : 'text-red';
  document.getElementById('shelter-score').innerHTML = `Overall Score: <span class="${scoreToneClass}">${total}/${max} (${pct}%)</span>`;
}

function cycleShelter(idx) {
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem('nomad-shelter') || '{}'); } catch(e) {}
  const levels = ['red','yellow','green'];
  const current = saved[idx] || 'red';
  saved[idx] = levels[(levels.indexOf(current) + 1) % levels.length];
  localStorage.setItem('nomad-shelter', JSON.stringify(saved));
  loadShelterAssess();
}

/* ─── Distance to Horizon ─── */
function calcHorizon() {
  const elev = parseFloat(document.getElementById('horizon-elev').value) || 0;
  const target = parseFloat(document.getElementById('horizon-target').value) || 0;
  // Distance to horizon in miles = sqrt(1.5 * height_in_feet)
  const d1 = Math.sqrt(1.5 * elev);
  const d2 = Math.sqrt(1.5 * target);
  const total = d1 + d2;
  const km = total * 1.60934;
  document.getElementById('horizon-result').innerHTML = `
    Your horizon: <strong>${d1.toFixed(1)} mi</strong> (${(d1*1.61).toFixed(1)} km)<br>
    ${target > 0 ? `Target visible at: <strong>${total.toFixed(1)} mi</strong> (${km.toFixed(1)} km)<br>` : ''}
    <div class="copy-dim-note">
      Common elevations: Standing (6ft) = ${Math.sqrt(9).toFixed(1)} mi |
      Roof (25ft) = ${Math.sqrt(37.5).toFixed(1)} mi |
      Hill (100ft) = ${Math.sqrt(150).toFixed(1)} mi |
      Tower (200ft) = ${Math.sqrt(300).toFixed(1)} mi
    </div>
    <div class="text-size-11 text-dim">VHF/UHF radio range is approximately line-of-sight. HF radio bounces off ionosphere (unlimited range).</div>`;
}

/* ─── Infrastructure Status ─── */
const INFRA_ITEMS = ['Power Grid','Water Supply','Natural Gas','Internet','Cell Service','Landline','Roads (Primary)','Roads (Secondary)','Hospital/ER','Fuel Stations','Grocery/Supply','Schools'];
const INFRA_LEVELS = ['operational','degraded','down','unknown'];
const INFRA_LABELS = {operational:'UP',degraded:'DEGRADED',down:'DOWN',unknown:'UNKNOWN'};
const INFRA_TONE_CLASSES = {operational:'text-green',degraded:'text-orange',down:'text-red',unknown:'text-muted'};

const HOME_SECURITY_ITEMS = [
  {cat:'Doors',items:['Deadbolts on all exterior doors (Grade 1)','3" screws in strike plates (not 3/4")','Solid core or metal exterior doors','Door reinforcement kit / door armor','Peephole or video doorbell','Sliding door bar / security bar','Garage door manual release secured']},
  {cat:'Windows',items:['Window locks functional on all windows','Security film on ground-floor windows','Dowels/pins in sliding window tracks','Thorny bushes below accessible windows','Window well covers (basement)']},
  {cat:'Exterior',items:['Motion-activated lights (all sides)','Address clearly visible (for emergency response)','No hiding spots near entry points','Trees/branches trimmed away from house','Fence/gate in good repair','Driveway alert / perimeter sensor','No spare key under mat/rock (use lockbox)']},
  {cat:'Interior',items:['Safe room designated (reinforced interior room)','Fire extinguishers (kitchen, garage, bedrooms)','Smoke + CO detectors on every floor','Flashlights staged (bedroom, kitchen, garage)','Home defense plan discussed with family','Valuables in fireproof safe (bolted down)','Important docs backed up off-site']},
  {cat:'OPSEC',items:['No visible high-value items from outside','Curtains/blinds on ground floor at night','No delivery boxes left curbside (cut up, recycle)','Social media doesn\'t reveal absences','Mail/packages held during travel','Neighbor has your contact info','Vary daily routines when possible']},
];

function renderHomeSecurity() {
  const el = document.getElementById('home-security-list');
  if (!el) return;
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem('nomad-home-security') || '{}'); } catch(e) {}
  let total = 0, checked = 0;
  el.innerHTML = HOME_SECURITY_ITEMS.map(cat => {
    return `<div class="prep-home-security-card">
      <div class="prep-home-security-title">${cat.cat}</div>
      ${cat.items.map(item => {
        const key = item.replace(/[^a-zA-Z]/g,'').substring(0,30);
        total++;
        if (saved[key]) checked++;
        return `<label class="prep-home-security-item">
          <input type="checkbox" ${saved[key]?'checked':''} data-change-action="toggle-home-security" data-home-security-key="${key}" class="prep-toggle-check">
          <span>${item}</span>
        </label>`;
      }).join('')}
    </div>`;
  }).join('');
  const pct = total > 0 ? Math.round(checked / total * 100) : 0;
  const scoreToneClass = pct >= 80 ? 'text-green' : pct >= 50 ? 'text-forecast-caution' : 'text-red';
  document.getElementById('home-security-score').innerHTML = `<span class="prep-score-value ${scoreToneClass}">Security Score: ${pct}%</span> <span class="prep-score-meta">(${checked}/${total} items)</span>`;
}

function toggleHomeSecurity(key, val) {
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem('nomad-home-security') || '{}'); } catch(e) {}
  if (val) saved[key] = true; else delete saved[key];
  localStorage.setItem('nomad-home-security', JSON.stringify(saved));
  renderHomeSecurity();
}

function loadInfraStatus() {
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem('nomad-infra') || '{}'); } catch(e) {}
  const el = document.getElementById('infra-status');
  if (!el) return;
  el.innerHTML = INFRA_ITEMS.map(item => {
    const key = item.replace(/[^a-zA-Z]/g,'').toLowerCase();
    const level = saved[key] || 'unknown';
    return `<div class="prep-status-row" role="button" tabindex="0" data-prep-action="cycle-infra" data-infra-key="${key}">
      <span class="prep-status-label">${item}</span>
      <span class="prep-status-value ${prepToneClass(level, INFRA_TONE_CLASSES)}">${INFRA_LABELS[level]}</span>
    </div>`;
  }).join('');
}

function cycleInfra(key) {
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem('nomad-infra') || '{}'); } catch(e) {}
  const current = saved[key] || 'unknown';
  const next = INFRA_LEVELS[(INFRA_LEVELS.indexOf(current) + 1) % INFRA_LEVELS.length];
  saved[key] = next;
  localStorage.setItem('nomad-infra', JSON.stringify(saved));
  loadInfraStatus();
}

/* ─── Vehicle Readiness ─── */
let _vehicles; try { _vehicles = JSON.parse(localStorage.getItem('nomad-vehicles') || '[]'); } catch(e) { _vehicles = []; }
function _syncVehicles() {
  localStorage.setItem('nomad-vehicles', JSON.stringify(_vehicles));
  fetch('/api/settings', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({vehicles: JSON.stringify(_vehicles)})});
}

function addVehicle() {
  const name = document.getElementById('veh-name').value.trim();
  const fuel = parseInt(document.getElementById('veh-fuel').value) || 0;
  if (!name) { toast('Enter a vehicle name', 'warning'); return; }
  _vehicles.push({name, fuel, status: 'ready', id: Date.now()});
  _syncVehicles();
  document.getElementById('veh-name').value = '';
  renderVehicles();
}

function cycleVehicleStatus(id) {
  const statuses = ['ready','needs-maintenance','disabled'];
  const v = _vehicles.find(v => v.id === id);
  if (v) { v.status = statuses[(statuses.indexOf(v.status) + 1) % statuses.length]; _syncVehicles(); renderVehicles(); }
}

function updateVehicleFuel(id, fuel) {
  const v = _vehicles.find(v => v.id === id);
  if (!v) return;
  const nextFuel = Math.max(0, Math.min(100, parseInt(fuel, 10) || 0));
  v.fuel = nextFuel;
  _syncVehicles();
  const row = document.querySelector(`[data-vehicle-row="${id}"]`);
  const valueEl = row?.querySelector('[data-vehicle-fuel-value]');
  const inputEl = row?.querySelector('[data-input-action="update-vehicle-fuel"]');
  const fuelColor = nextFuel > 50 ? 'var(--green)' : nextFuel > 25 ? 'var(--orange)' : 'var(--red)';
  const fuelTone = fuelToneClass(nextFuel);
  if (inputEl) inputEl.style.accentColor = fuelColor;
  if (valueEl) {
    valueEl.textContent = `${nextFuel}%`;
    valueEl.className = `prep-vehicle-fuel ${fuelTone}`;
  }
}

function deleteVehicle(id) {
  _vehicles = _vehicles.filter(v => v.id !== id);
  _syncVehicles();
  renderVehicles();
}

function renderVehicles() {
  const el = document.getElementById('vehicle-list');
  if (!_vehicles.length) { el.innerHTML = '<div class="prep-empty-state">No vehicles tracked.</div>'; return; }
  const statusToneClasses = {ready:'text-green', 'needs-maintenance':'text-orange', disabled:'text-red'};
  const statusLabels = {ready:'READY','needs-maintenance':'MAINT',disabled:'DOWN'};
  el.innerHTML = _vehicles.map(v => {
    const fuelColor = v.fuel > 50 ? 'var(--green)' : v.fuel > 25 ? 'var(--orange)' : 'var(--red)';
    const fuelTone = fuelToneClass(v.fuel);
    const safeName = escapeHtml(v.name);
    return `<div class="prep-vehicle-row" data-vehicle-row="${v.id}">
      <div class="prep-vehicle-main">${safeName}</div>
      <div class="prep-vehicle-controls">
        <span class="prep-vehicle-label">Fuel:</span>
        <input type="range" min="0" max="100" value="${v.fuel}" class="prep-vehicle-slider" style="accent-color:${fuelColor};" data-input-action="update-vehicle-fuel" data-vehicle-id="${v.id}" aria-label="Fuel level for ${safeName}">
        <span data-vehicle-fuel-value class="prep-vehicle-fuel ${fuelTone}">${v.fuel}%</span>
        <button type="button" class="vehicle-status-btn prep-vehicle-status ${statusToneClasses[v.status]}" data-prep-action="cycle-vehicle-status" data-vehicle-id="${v.id}" title="Cycle readiness status for ${safeName}" aria-label="Cycle readiness status for ${safeName}">${statusLabels[v.status]}</button>
        <button type="button" class="vehicle-delete-btn" data-prep-action="delete-vehicle" data-vehicle-id="${v.id}" aria-label="Remove ${safeName} from vehicle readiness">x</button>
      </div>
    </div>`;
  }).join('');
}

/* ─── SITREP Generator ─── */
function fillSitrepDTG() {
  const now = new Date();
  const dtg = `${String(now.getDate()).padStart(2,'0')}${String(now.getHours()).padStart(2,'0')}${String(now.getMinutes()).padStart(2,'0')}L ${now.toLocaleString('default',{month:'short'}).toUpperCase()} ${now.getFullYear()}`;
  document.getElementById('sitrep-dtg').value = dtg;
}

function generateSitrep() {
  fillSitrepDTG();
  const dtg = document.getElementById('sitrep-dtg').value;
  const loc = document.getElementById('sitrep-loc').value;
  const sit = document.getElementById('sitrep-sit').value;
  const cas = document.getElementById('sitrep-cas').value;
  const sup = document.getElementById('sitrep-sup').value;
  const comms = document.getElementById('sitrep-comms').value;
  const req = document.getElementById('sitrep-req').value;
  const plan = document.getElementById('sitrep-plan').value;
  const text = `===== SITREP =====
DTG: ${dtg || 'N/A'}
LOC: ${loc || 'N/A'}
1. SITUATION: ${sit || 'N/A'}
2. CASUALTIES: ${cas || 'None'}
3. SUPPLIES: ${sup || 'N/A'}
4. COMMS: ${comms || 'N/A'}
5. REQUESTS: ${req || 'None'}
6. PLAN: ${plan || 'N/A'}
===== END SITREP =====`;
  const el = document.getElementById('sitrep-output');
  if (el) el.textContent = text;
  el.style.display = 'block';
}

function copySitrep() {
  const text = document.getElementById('sitrep-output').textContent;
  if (!text) { generateSitrep(); }
  navigator.clipboard.writeText(document.getElementById('sitrep-output').textContent).then(() => toast('SITREP copied to clipboard', 'success'));
}

/* ─── Cipher Tool ─── */
function runCipher() {
  const type = document.getElementById('cipher-type').value;
  const input = document.getElementById('cipher-input').value;
  const rawShift = parseInt(document.getElementById('cipher-shift').value) || 13;
  const shift = ((rawShift % 26) + 26) % 26; // Normalize to 0-25, handles negatives
  let output = '';
  if (type === 'caesar') {
    output = input.split('').map(c => {
      if (c >= 'A' && c <= 'Z') return String.fromCharCode(((c.charCodeAt(0) - 65 + shift) % 26) + 65);
      if (c >= 'a' && c <= 'z') return String.fromCharCode(((c.charCodeAt(0) - 97 + shift) % 26) + 97);
      return c;
    }).join('');
  } else if (type === 'reverse') {
    output = input.split('').reverse().join('');
  } else if (type === 'atbash') {
    output = input.split('').map(c => {
      if (c >= 'A' && c <= 'Z') return String.fromCharCode(90 - (c.charCodeAt(0) - 65));
      if (c >= 'a' && c <= 'z') return String.fromCharCode(122 - (c.charCodeAt(0) - 97));
      return c;
    }).join('');
  }
  document.getElementById('cipher-output').textContent = output;
}

function copyCipherOutput() {
  const output = document.getElementById('cipher-output').textContent;
  if (!output) {
    toast('Generate an encrypted message first', 'warning');
    return;
  }
  navigator.clipboard.writeText(output).then(() => toast('Copied', 'success'));
}
