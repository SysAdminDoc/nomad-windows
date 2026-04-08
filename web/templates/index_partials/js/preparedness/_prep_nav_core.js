/* ─── Prep Sub-Tab Navigation ─── */
// Preparedness lanes organize the workspace around common field situations.
const PREP_CATEGORIES = {
  coordinate: {label:'Coordinate', description:'Run checklists, capture incidents, and keep the operational picture current.', tabs:[
    {id:'checklists',label:'Checklists'},
    {id:'incidents',label:'Incidents'},
    {id:'ops',label:'Command Post'},
    {id:'analytics',label:'Trends'}
  ]},
  sustain:    {label:'Sustain', description:'Keep supplies, power, food production, and environmental awareness stable.', tabs:[
    {id:'inventory',label:'Supplies'},
    {id:'fuel',label:'Fuel'},
    {id:'power',label:'Power'},
    {id:'garden',label:'Food Production'},
    {id:'equipment',label:'Equipment'},
    {id:'weather',label:'Weather'}
  ]},
  care:       {label:'Care & People', description:'Support medical readiness, family planning, and the people network around you.', tabs:[
    {id:'medical',label:'Medical'},
    {id:'contacts',label:'Contacts'},
    {id:'family',label:'Family Plan'},
    {id:'community',label:'Community'},
    {id:'skills',label:'Skills'},
    {id:'journal',label:'Journal'}
  ]},
  protect:    {label:'Protect & Secure', description:'Manage security, comms discipline, exposure threats, and sensitive records.', tabs:[
    {id:'security',label:'Security'},
    {id:'radio',label:'Radio'},
    {id:'signals',label:'Signal Plan'},
    {id:'vault',label:'Vault'},
    {id:'ammo',label:'Ammo'},
    {id:'radiation',label:'Radiation'}
  ]},
  learn:      {label:'Reference & Planning', description:'Use decision guides, procedures, quick reference, and calculators to act fast.', tabs:[
    {id:'guides',label:'Guides'},
    {id:'protocols',label:'Protocols'},
    {id:'reference',label:'Quick Ref'},
    {id:'calculators',label:'Calculators'}
  ]},
};
const PREP_WORKSPACE_STORAGE_KEY = 'nomad-prep-workspace-memory-v2';
const PREP_DEFAULT_FAVORITES = ['checklists', 'inventory', 'medical', 'security', 'guides'];
const PREP_WORKSPACE_DETAILS = {
  checklists: {icon:'&#9745;', summary:'Run active response checklists and keep handoffs clear.'},
  incidents: {icon:'&#9888;', summary:'Capture events, severity, and timing in sequence.'},
  ops: {icon:'&#9878;', summary:'Manage command-post operations and active posture.'},
  analytics: {icon:'&#128202;', summary:'Review trend lines before they become new problems.'},
  inventory: {icon:'&#128230;', summary:'Track stock, expiry pressure, and replenishment needs.'},
  fuel: {icon:'&#9981;', summary:'Watch fuel posture, reserves, and burn planning.'},
  power: {icon:'&#9889;', summary:'Manage power sources, devices, and continuity.'},
  garden: {icon:'&#127793;', summary:'Keep food production and seasonal planting on track.'},
  equipment: {icon:'&#128295;', summary:'Review tool readiness, repair needs, and spares.'},
  weather: {icon:'&#9729;', summary:'Monitor forecast changes and weather-driven risk.'},
  medical: {icon:'&#10010;', summary:'Check patient status, supplies, and medical readiness.'},
  contacts: {icon:'&#128101;', summary:'Keep key people, roles, and contact paths current.'},
  family: {icon:'&#127968;', summary:'Update family plans, rally points, and responsibilities.'},
  community: {icon:'&#129309;', summary:'Track local support, peers, and mutual-aid posture.'},
  skills: {icon:'&#127891;', summary:'Review capability gaps and who can cover them.'},
  journal: {icon:'&#9999;', summary:'Capture observations, decisions, and daily context.'},
  security: {icon:'&#128737;', summary:'Check security posture, perimeter, and threat state.'},
  radio: {icon:'&#128225;', summary:'Manage radio readiness, propagation, and frequencies.'},
  signals: {icon:'&#128246;', summary:'Plan check-ins, signal windows, and message flow.'},
  vault: {icon:'&#128274;', summary:'Access protected records and sensitive materials.'},
  ammo: {icon:'&#127919;', summary:'Watch supply levels, compatibility, and gaps.'},
  radiation: {icon:'&#9762;', summary:'Track exposure, contamination, and fallout posture.'},
  guides: {icon:'&#128214;', summary:'Open decision guides and step-by-step field help.'},
  protocols: {icon:'&#128196;', summary:'Use operating procedures and standard playbooks fast.'},
  reference: {icon:'&#128209;', summary:'Reach quick-reference answers without digging.'},
  calculators: {icon:'&#129518;', summary:'Run planning and survival calculations quickly.'},
};
let _currentPrepCat = 'coordinate';

function getAllPrepWorkspaceIds() {
  return Object.values(PREP_CATEGORIES).flatMap(group => group.tabs.map(tab => tab.id));
}

function getPrepWorkspaceMeta(sub) {
  const cat = _findCategoryForSub(sub);
  const group = PREP_CATEGORIES[cat];
  const tab = group?.tabs.find(item => item.id === sub);
  const detail = PREP_WORKSPACE_DETAILS[sub] || {};
  return {
    id: sub,
    lane: cat,
    laneLabel: group?.label || 'Preparedness',
    label: tab?.label || sub,
    icon: detail.icon || '&#8250;',
    summary: detail.summary || group?.description || 'Open workspace',
  };
}

function normalizePrepWorkspaceState(raw) {
  const validIds = new Set(getAllPrepWorkspaceIds());
  const toList = value => Array.isArray(value) ? value.filter(id => validIds.has(id)) : [];
  const dedupe = list => Array.from(new Set(list));
  const favorites = dedupe(toList(raw?.favorites));
  const recent = dedupe(toList(raw?.recent));
  const current = validIds.has(raw?.current) ? raw.current : 'checklists';
  const last = validIds.has(raw?.last) && raw.last !== current ? raw.last : '';
  return {
    current,
    last,
    favorites: (favorites.length ? favorites : PREP_DEFAULT_FAVORITES.filter(id => validIds.has(id))).slice(0, 6),
    recent: [current, ...recent.filter(id => id !== current)].slice(0, 6),
  };
}

function getPrepWorkspaceState() {
  return normalizePrepWorkspaceState(readJsonStorage(localStorage, PREP_WORKSPACE_STORAGE_KEY, {}));
}

function savePrepWorkspaceState(state) {
  try {
    localStorage.setItem(PREP_WORKSPACE_STORAGE_KEY, JSON.stringify(normalizePrepWorkspaceState(state)));
  } catch (error) {
    console.warn('Unable to save preparedness workspace state', error);
  }
}

function openPrepWorkspaceFromMemory(sub) {
  if (!sub) return;
  document.querySelector('[data-tab="preparedness"]')?.click();
  setTimeout(() => {
    if (typeof switchPrepSub === 'function') switchPrepSub(sub);
  }, 160);
}

function rememberPrepWorkspace(sub) {
  if (!sub) return;
  const state = getPrepWorkspaceState();
  if (state.current && state.current !== sub) state.last = state.current;
  state.current = sub;
  state.recent = [sub, ...state.recent.filter(id => id !== sub)].slice(0, 6);
  savePrepWorkspaceState(state);
}

function togglePrepWorkspaceFavorite(sub) {
  if (!sub) return false;
  const state = getPrepWorkspaceState();
  if (state.favorites.includes(sub)) {
    state.favorites = state.favorites.filter(id => id !== sub);
  } else {
    state.favorites = [sub, ...state.favorites.filter(id => id !== sub)].slice(0, 6);
  }
  savePrepWorkspaceState(state);
  return state.favorites.includes(sub);
}

function buildPrepWorkspaceChip(meta, options = {}) {
  const classes = [
    'prep-workspace-chip',
    options.isCurrent ? 'is-current' : '',
    options.isFavorite ? 'is-favorite' : '',
  ].filter(Boolean).join(' ');
  return `<button type="button" class="${classes}" data-prep-nav-open="${meta.id}">
    <span class="prep-workspace-chip-icon" aria-hidden="true">${meta.icon}</span>
    <span class="prep-workspace-chip-body">
      <span class="prep-workspace-chip-title">${escapeHtml(meta.label)}</span>
      <span class="prep-workspace-chip-meta">${escapeHtml(meta.laneLabel)} · ${escapeHtml(meta.summary)}</span>
    </span>
  </button>`;
}

function renderPrepWorkspaceHub() {
  const state = getPrepWorkspaceState();
  const currentMeta = getPrepWorkspaceMeta(state.current || 'checklists');
  const lastMeta = state.last && state.last !== currentMeta.id ? getPrepWorkspaceMeta(state.last) : null;
  const recentIds = state.recent.filter(id => id !== currentMeta.id && !state.favorites.includes(id)).slice(0, 5);
  const activeLane = _currentPrepCat;
  const favoriteMetas = state.favorites
    .map((id, index) => ({...getPrepWorkspaceMeta(id), _index: index}))
    .sort((a, b) => {
      const laneDelta = (a.lane === activeLane ? 0 : 1) - (b.lane === activeLane ? 0 : 1);
      return laneDelta || a._index - b._index;
    });

  const recentEl = document.getElementById('prep-recent-workspaces');
  const favoritesEl = document.getElementById('prep-favorite-workspaces');
  const summaryEl = document.getElementById('prep-resume-summary');
  const favoriteSummaryEl = document.getElementById('prep-favorite-summary');
  const subtabsCopyEl = document.getElementById('prep-subtabs-copy');
  const resumeBtn = document.getElementById('prep-resume-last-btn');
  const favoriteBtn = document.getElementById('prep-favorite-current-btn');
  if (!recentEl || !favoritesEl || !summaryEl || !favoriteSummaryEl || !resumeBtn || !favoriteBtn) return;

  summaryEl.textContent = lastMeta
    ? `Current: ${currentMeta.label} in ${currentMeta.laneLabel}. Last workspace: ${lastMeta.label}.`
    : `Current: ${currentMeta.label} in ${currentMeta.laneLabel}. Your last workspace will appear here once you move around.`;
  recentEl.innerHTML = recentIds.length
    ? recentIds.map(id => buildPrepWorkspaceChip(getPrepWorkspaceMeta(id))).join('')
    : '<div class="prep-workbench-empty">Recent workspace jumps will show up here.</div>';

  favoritesEl.innerHTML = favoriteMetas.length
    ? favoriteMetas.map(meta => buildPrepWorkspaceChip(meta, {isCurrent: meta.id === currentMeta.id, isFavorite: true})).join('')
    : '<div class="prep-workbench-empty">Pin the workspaces you use most.</div>';

  const isCurrentFavorite = state.favorites.includes(currentMeta.id);
  favoriteSummaryEl.textContent = isCurrentFavorite
    ? `${currentMeta.label} is pinned. Open any workspace, then pin or unpin it from here.`
    : `${currentMeta.label} is not pinned yet. Pin it if this is part of your normal operating loop.`;
  favoriteBtn.textContent = isCurrentFavorite ? `Unpin ${currentMeta.label}` : `Pin ${currentMeta.label}`;
  favoriteBtn.setAttribute('aria-pressed', isCurrentFavorite ? 'true' : 'false');

  resumeBtn.disabled = !lastMeta;
  resumeBtn.textContent = lastMeta ? `Resume ${lastMeta.label}` : 'Resume Last Workspace';
  resumeBtn.setAttribute('aria-disabled', lastMeta ? 'false' : 'true');

  if (subtabsCopyEl) {
    subtabsCopyEl.textContent = isCurrentFavorite
      ? `${currentMeta.label} is pinned for faster return. Switch lanes when the situation changes.`
      : `${currentMeta.label} is active now. Pin it if you keep coming back here.`;
  }
}

function getPrepWorkspacePaletteCommands() {
  const state = getPrepWorkspaceState();
  const favorites = state.favorites.slice(0, 5).map((id, index) => {
    const meta = getPrepWorkspaceMeta(id);
    return {
      id: `prep-favorite-${meta.id}`,
      section: 'Preparedness Favorites',
      title: `Open ${meta.label}`,
      subtitle: `${meta.laneLabel} · ${meta.summary}`,
      keywords: `preparedness favorite ${meta.laneLabel} ${meta.label} ${meta.summary}`,
      icon: meta.icon,
      meta: 'Pinned',
      priority: 93 - index,
      run: () => openPrepWorkspaceFromMemory(meta.id),
    };
  });
  const recent = state.recent
    .filter(id => id !== state.current && !state.favorites.includes(id))
    .slice(0, 4)
    .map((id, index) => {
      const meta = getPrepWorkspaceMeta(id);
      return {
        id: `prep-recent-${meta.id}`,
        section: 'Recent Preparedness',
        title: `Resume ${meta.label}`,
        subtitle: `${meta.laneLabel} · ${meta.summary}`,
        keywords: `preparedness recent ${meta.laneLabel} ${meta.label} ${meta.summary}`,
        icon: meta.icon,
        meta: 'Recent',
        priority: 85 - index,
        run: () => openPrepWorkspaceFromMemory(meta.id),
      };
    });
  return [...favorites, ...recent];
}

function setPrepScenarioFocus(group) {
  const kicker = document.getElementById('prep-scenario-focus-kicker');
  const copy = document.getElementById('prep-scenario-focus-copy');
  if (kicker) kicker.textContent = group?.label || '';
  if (copy) copy.textContent = group?.description || '';
}

function showPrepCategory(cat) {
  const group = PREP_CATEGORIES[cat];
  if (!group) return;
  _currentPrepCat = cat;
  // Update scenario cards
  document.querySelectorAll('.prep-cat-btn').forEach(b => {
    const isActive = b.dataset.cat === cat;
    b.classList.toggle('active', isActive);
    b.setAttribute('aria-pressed', isActive ? 'true' : 'false');
  });
  setPrepScenarioFocus(group);
  renderPrepWorkspaceHub();
  // Render sub-tabs for this lane
  const bar = document.getElementById('prep-subtab-bar');
  bar.innerHTML = group.tabs.map(function(t) {
    const active = document.querySelector('.prep-sub.active');
    const isActive = active && active.id === 'psub-' + t.id;
    return '<button type="button" class="prep-subtab' + (isActive ? ' active' : '') + '" data-psub="' + t.id + '" data-prep-sub-switch="' + t.id + '">' + t.label + '</button>';
  }).join('');
  // If no tab in this category is active, activate the first one
  const activeInCat = group.tabs.find(function(t) {
    const el = document.getElementById('psub-' + t.id);
    return el && el.classList.contains('active');
  });
  if (!activeInCat && group.tabs.length) {
    switchPrepSub(group.tabs[0].id);
  }
}

// Find which category a sub-tab belongs to
function _findCategoryForSub(sub) {
  for (const [cat, group] of Object.entries(PREP_CATEGORIES)) {
    if (group.tabs.some(function(t) { return t.id === sub; })) return cat;
  }
  return 'coordinate';
}

// Initialize Preparedness lanes on first load
function initPrepNav() {
  showPrepCategory('coordinate');
}

function switchPrepSub(sub) {
  // Ensure correct category is shown
  const cat = _findCategoryForSub(sub);
  if (cat !== _currentPrepCat) showPrepCategory(cat);
  document.querySelectorAll('.prep-subtab').forEach(b => b.classList.toggle('active', b.dataset.psub === sub));
  document.querySelectorAll('.prep-sub').forEach(p => p.classList.toggle('active', p.id === 'psub-' + sub));
  rememberPrepWorkspace(sub);
  renderPrepWorkspaceHub();
  if (sub === 'incidents') loadIncidents();
  if (sub === 'inventory') { loadInventory(); loadBurnRate(); loadInvViz(); }
  if (sub === 'contacts') { loadContacts(); loadSkillsMatrix(); }
  if (sub === 'calculators') { try { calcWater(); calcFood(); calcPower(); calcWatch(); document.getElementById('solar-date').value=new Date().toISOString().slice(0,10); calcSolar(); document.getElementById('moon-date').value=new Date().toISOString().slice(0,10); calcMoon(); convertCoords(); calcTravel(); calcBattery(); calcHorizon(); updateCalTracker(); calcPlan(); calcFoodStorage(); calcGenFuel(); calcRainwater(); calcRadioRange(); calcMedDose(); calcSolarSize(); renderBOBChecklist(); calcBOB(); calcBallistics(); calcCompost(); calcPastureRotation(); calcNaturalBuilding(); calcFallout(); calcCanning(); calcBurnArea(); calcIVDrip(); calcDeadReckoning(); calcShelterPF(); calcCropCalories(); calcNVIS(); calcWeightDose(); calcHypothermia(); calcORT(); calcAbxInventory(); calcRadDose(); calcWaterNeeds(); calcGenerator(); calcDehydration(); calcVitals(); calcAntenna(); } catch(e) { console.error('Calculator init error:', e); } }
  if (sub === 'vault' && _vaultKey) loadVaultList();
  if (sub === 'weather') { loadWeather(); loadZambretti(); loadPressureGraph(); loadWeatherRules(); }
  if (sub === 'radio') { loadFreqDatabase(); loadCommsStatusBoard(); loadPropagation(); }
  if (sub === 'signals') { loadSignalSchedule(); loadCommsLog(); }
  if (sub === 'ops') { loadInfraStatus(); renderVehicles(); calcBleach(); loadThreatMatrix(); renderHomeSecurity(); }
  if (sub === 'family') loadFEP();
  if (sub === 'journal') loadJournal();
  if (sub === 'security') { loadSecurityDashboard(); loadCameras(); loadPerimeterZones(); loadMotionStatus(); _startMotionPolling(); }
  if (sub === 'power') { loadPowerDashboard(); loadPowerDevices(); updatePowerSpecFields(); }
  if (sub === 'garden') { loadPlots(); lookupZone(); loadCompanions(); loadPestGuide(); }
  if (sub === 'medical') { loadPatients(); loadMedicalSupplies(); loadTriageBoard(); loadExpiringMeds(); loadDosageCalculator(); }
  if (sub === 'guides') renderGuideSelector();
  if (sub === 'reference') { convertUnit(); showPlantZone(); textToMorse(); morseToText(); loadPace(); showPhrases(); loadShelterAssess(); }
  if (sub === 'checklists') loadChecklists();
  if (sub === 'skills') loadSkills();
  if (sub === 'ammo') loadAmmo();
  if (sub === 'community') { loadCommunity(); loadFederationPeers(); }
  if (sub === 'radiation') loadRadiation();
  if (sub === 'fuel') loadFuel();
  if (sub === 'equipment') loadEquipment();
  if (sub === 'analytics') loadAnalyticsDashboard();
  if (typeof syncWorkspaceUrlState === 'function') syncWorkspaceUrlState();
}

/* ─── Preparedness ─── */
let _prepLoaded = false;
let _currentChecklistId = null;
let _currentChecklistItems = [];

async function loadPrepTab() {
  if (!_prepLoaded) {
    initPrepNav();
    await loadPrepTemplates();
    await loadSitBoard();
    calcWater(); calcFood(); calcPower();
    loadPace();
    _prepLoaded = true;
  } else {
    // Ensure the category bar has tabs (in case it wasn't initialized)
    const _bar = document.getElementById('prep-subtab-bar');
    if (_bar && !_bar.children.length) initPrepNav();
  }
  renderPrepWorkspaceHub();
  await loadChecklists();
}

async function loadPrepTemplates() {
  try {
    const templates = await safeFetch('/api/checklists/templates', {}, {});
    if (!templates || typeof templates !== 'object') throw new Error('invalid checklist templates payload');
    const el = document.getElementById('prep-template-btns');
    if (!el) return;
    el.innerHTML = Object.entries(templates).map(([k, v]) =>
      `<button class="prep-template-btn" data-checklist-template="${escapeHtml(k)}" title="${v.item_count} items">+ ${v.name}</button>`
    ).join('');
  } catch(e) {}
}

async function loadChecklists() {
  try {
    const lists = await safeFetch('/api/checklists', {}, []);
    if (!Array.isArray(lists)) throw new Error('invalid checklist list payload');
    const el = document.getElementById('prep-list');
    if (!lists.length) {
      el.innerHTML = '<div class="prep-empty-block"><div class="prep-empty-copy">No checklists yet. Choose a template above.</div></div>';
      return;
    }
    el.innerHTML = lists.map(c => {
      const pct = c.item_count > 0 ? Math.round(c.checked_count / c.item_count * 100) : 0;
      const remaining = Math.max(c.item_count - c.checked_count, 0);
      const toneClass = pct === 100 ? 'prep-list-card-good' : pct >= 50 ? 'prep-list-card-watch' : 'prep-list-card-risk';
      return `<div class="prep-item prep-list-card ${toneClass} ${c.id === _currentChecklistId ? 'active' : ''}" data-cl-id="${c.id}" data-checklist-id="${c.id}" role="button" tabindex="0" aria-pressed="${c.id === _currentChecklistId ? 'true' : 'false'}">
        <div class="prep-list-card-main">
          <div class="prep-list-card-head">
            <span class="prep-item-name prep-list-card-title">${escapeHtml(c.name)}</span>
            <span class="prep-progress prep-list-card-progress">${pct}%</span>
          </div>
          <div class="prep-list-card-bar"><span class="prep-list-card-bar-fill" style="width:${pct}%;"></span></div>
          <div class="prep-list-card-meta">${c.checked_count}/${c.item_count} complete · ${remaining} remaining</div>
        </div>
        <button type="button" class="prep-del prep-list-card-delete" data-checklist-delete="${c.id}" title="Delete" aria-label="Delete ${escapeHtml(c.name)}">x</button>
      </div>`;
    }).join('');
  } catch(e) {
    document.getElementById('prep-list').innerHTML = '<div class="prep-error-state">Failed to load checklists</div>';
  }
}

async function createChecklist(template) {
  try {
    const r = await safeFetch('/api/checklists', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({template})
    }, null);
    if (!r || !r.id) throw new Error('invalid checklist creation payload');
    toast(`Created: ${r.name}`, 'success');
    _currentChecklistId = r.id;
    await loadChecklists();
    await selectChecklist(r.id);
  } catch(e) { toast('Failed to create checklist', 'error'); }
}

async function selectChecklist(id) {
  _currentChecklistId = id;
  try {
    const c = await safeFetch(`/api/checklists/${id}`, {}, null);
    if (!c || typeof c !== 'object') throw new Error('invalid checklist payload');
    _currentChecklistItems = c.items || [];
    document.getElementById('prep-active-name').textContent = c.name;
    renderChecklist();
    // Update sidebar active state
    document.querySelectorAll('.prep-item').forEach(el => {
      el.classList.toggle('active', el.dataset.clId == id);
    });
    await loadChecklists();
  } catch(e) { toast('Failed to load checklist', 'error'); }
}

function renderChecklist() {
  const el = document.getElementById('prep-checklist');
  const total = _currentChecklistItems.length;
  const checked = _currentChecklistItems.filter(i => i.checked).length;
  const pct = total > 0 ? Math.round(checked / total * 100) : 0;
  document.getElementById('prep-active-stats').textContent = total ? `${checked}/${total} complete · ${pct}%` : 'No items yet';
  document.getElementById('prep-progress-fill').style.width = pct + '%';

  if (!total) {
    el.innerHTML = '<div class="prep-empty-block"><div class="prep-empty-copy">This checklist is empty. Add an item to start building the runbook.</div></div>';
    return;
  }

  // Group by category
  const cats = {};
  _currentChecklistItems.forEach((item, idx) => {
    const cat = item.cat || 'general';
    if (!cats[cat]) cats[cat] = [];
    cats[cat].push({...item, idx});
  });

  let html = '';
  for (const [cat, items] of Object.entries(cats)) {
    const groupChecked = items.filter(item => item.checked).length;
    html += `
      <section class="prep-checklist-group">
        <div class="checklist-group-head prep-checklist-group-head">
          <span class="check-cat">${cat}</span>
          <span class="prep-checklist-group-meta">${groupChecked}/${items.length} complete</span>
        </div>
        <div class="prep-checklist-group-items">
          ${items.map((item, itemIndex) =>
            `<label class="check-item prep-check-item ${item.checked ? 'checked is-checked' : ''}" data-check-item="${item.idx}">
              <input type="checkbox" ${item.checked ? 'checked' : ''}>
              <span class="prep-check-item-body">
                <span class="prep-check-item-title">${escapeHtml(item.text)}</span>
                <span class="prep-check-item-status">${item.checked ? 'Done' : `Item ${itemIndex + 1}`}</span>
              </span>
            </label>`
          ).join('')}
        </div>
      </section>
    `;
  }
  el.innerHTML = html;
}

async function toggleCheckItem(idx) {
  if (!_currentChecklistId || idx >= _currentChecklistItems.length) return;
  _currentChecklistItems[idx].checked = !_currentChecklistItems[idx].checked;
  renderChecklist();
  // Save
  try {
    await apiPut(`/api/checklists/${_currentChecklistId}`, {items: _currentChecklistItems});
    loadChecklists();
  } catch (e) {
    toast(e?.data?.error || e?.message || 'Failed to save checklist', 'error');
  }
}

async function deleteChecklist(id) {
  if (!confirm('Delete this checklist?')) return;
  try {
    await apiDelete(`/api/checklists/${id}`);
    toast('Checklist deleted', 'warning');
    if (_currentChecklistId === id) {
      _currentChecklistId = null;
      _currentChecklistItems = [];
      document.getElementById('prep-active-name').textContent = 'Select or create a checklist';
      document.getElementById('prep-active-stats').textContent = '';
      document.getElementById('prep-progress-fill').style.width = '0%';
      document.getElementById('prep-checklist').innerHTML = '<div class="empty-state empty-state-fill"><div class="icon empty-state-icon-muted">&#9745;</div><p>Choose a template above to create a checklist, or select an existing one.</p></div>';
    }
    await loadChecklists();
  } catch(e) { console.error(e); toast('Failed to delete checklist', 'error'); }
}

document.addEventListener('click', event => {
  const openButton = event.target.closest('[data-prep-nav-open]');
  if (openButton) {
    event.preventDefault();
    openPrepWorkspaceFromMemory(openButton.dataset.prepNavOpen);
    return;
  }

  const actionButton = event.target.closest('[data-prep-nav-action]');
  if (!actionButton) return;

  if (actionButton.dataset.prepNavAction === 'resume-last') {
    const state = getPrepWorkspaceState();
    if (state.last) openPrepWorkspaceFromMemory(state.last);
    return;
  }

  if (actionButton.dataset.prepNavAction === 'toggle-current-favorite') {
    const current = getPrepWorkspaceState().current;
    if (!current) return;
    const isPinned = togglePrepWorkspaceFavorite(current);
    renderPrepWorkspaceHub();
    toast(isPinned ? 'Workspace pinned' : 'Workspace unpinned', isPinned ? 'success' : 'info');
  }
});
