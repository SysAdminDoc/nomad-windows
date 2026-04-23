/* ──────────────────────────────────────────────────────────────────
   Setup Wizard — first-run onboarding flow.

   Extracted from _app_workspaces.js to keep that file under the
   per-module size ceiling (tests/test_core.py enforces < 2500 lines).
   This module owns the wizard-only state (_wiz*) and every wiz*() /
   setWizard*() helper. Included after _app_workspaces.js in
   _app_inline.js so it can reuse setShellVisibility, apiFetch, toast,
   and the onboarding persistence helpers.
   ──────────────────────────────────────────────────────────────── */
let _wizDrivePath = '';
let _wizTier = 'essential';
let _wizTiers = {};

function setWizardSectionVisibility(target, visible, display = 'block') {
  const el = typeof target === 'string' ? document.getElementById(target) : target;
  if (!el) return null;
  el.classList.toggle('is-hidden', !visible);
  el.hidden = !visible;
  if (visible) {
    el.style.display = display;
  } else {
    el.style.removeProperty('display');
  }
  return el;
}

function clearWizardUrlFlag() {
  const url = new URL(window.location.href);
  if (!url.searchParams.has('wizard')) return;
  url.searchParams.delete('wizard');
  history.replaceState(null, '', `${url.pathname}${url.search}${url.hash}`);
}

function refreshOnboardingSurfaces() {
  if (typeof loadServices === 'function' && isWorkspaceTabActive('services')) {
    loadServices();
  }
  if (typeof loadGettingStarted === 'function' && isWorkspaceTabActive('services')) {
    loadGettingStarted();
  }
}

async function persistOnboardingComplete() {
  if (window.NOMAD_FIRST_RUN_COMPLETE === true) return;
  window.NOMAD_FIRST_RUN_COMPLETE = true;
  window.NOMAD_WIZARD_SHOULD_LAUNCH = false;
  refreshOnboardingSurfaces();
  try { await apiPost('/api/settings/wizard-complete'); } catch (_) {}
}

async function checkWizard() {
  const forced = new URLSearchParams(location.search).has('wizard');
  const shouldAutoLaunch = forced || (window.NOMAD_WIZARD_SHOULD_LAUNCH && isWorkspaceTabActive('services'));
  if (!shouldAutoLaunch) return;

  const wizard = document.getElementById('wizard');
  if (!wizard) return;

  try {
    const state = await _workspaceFetchJson('/api/wizard/progress', {}, 'Could not load setup progress');
    if (state?.status === 'running') {
      setShellVisibility(wizard, true);
      setShellVisibility(document.getElementById('wiz-mini-banner'), false);
      wizGoPage(4);
      wizPollProgress();
      return;
    }
    if (state?.status === 'complete' && window.NOMAD_FIRST_RUN_COMPLETE === false) {
      setShellVisibility(wizard, true);
      setShellVisibility(document.getElementById('wiz-mini-banner'), false);
      await wizShowComplete(state);
      return;
    }
  } catch (_) {
    // Fall back to the welcome page if progress state is unavailable.
  }

  wizGoPage(1);
  setShellVisibility(wizard, true);
  setShellVisibility(document.getElementById('wiz-mini-banner'), false);
}

function wizGoPage(n) {
  for (let i = 1; i <= 5; i++) {
    setWizardSectionVisibility('wiz-page-' + i, i === n, 'grid');
  }
  if (n === 2) wizLoadDrives();
  if (n === 3) wizLoadTiers();
}

function setWizardStorageStatus(message, success = false) {
  const el = document.getElementById('wiz-storage-status');
  const nextBtn = document.getElementById('wiz-storage-next');
  if (!el) return;
  el.textContent = message;
  el.classList.toggle('wizard-status-line-success', success);
  if (nextBtn) nextBtn.disabled = !success;
}

async function wizLoadDrives() {
  const el = document.getElementById('wiz-drives');
  if (!el) return;
  let drives = [];
  try {
    drives = await _workspaceFetchJson('/api/drives', {}, 'Could not scan storage locations');
  } catch (_) {
    el.innerHTML = '<div class="utility-empty-state"><strong>Storage scan unavailable</strong><span>Enter a custom path for now, or retry once the desk can read available drives again.</span></div>';
    setWizardStorageStatus('Storage scan unavailable. Enter a custom path to keep moving.', false);
    return;
  }
  if (!Array.isArray(drives) || !drives.length) {
    el.innerHTML = '<div class="utility-empty-state"><strong>No writable drives detected</strong><span>Choose a specific folder path to continue, then revisit storage options later if you need to.</span></div>';
    setWizardStorageStatus('Choose a custom path to continue.', false);
    return;
  }
  let bestDrive = drives[0];
  drives.forEach(d => {
    if (d.free > (bestDrive?.free || 0)) bestDrive = d;
  });
  if (!_wizDrivePath && bestDrive) _wizDrivePath = bestDrive.path;

  el.innerHTML = drives.map(d => {
    const sel = d.path === _wizDrivePath;
    const pct = d.percent;
    const color = pct > 90 ? 'var(--red)' : pct > 75 ? 'var(--orange)' : 'var(--green)';
    return `<button type="button" class="wizard-drive-card${sel ? ' is-selected' : ''}" data-shell-action="wiz-select-drive" data-drive-path="${escapeAttr(d.path)}">
      <span class="wizard-drive-title">${escapeHtml(d.path)}</span>
      <span class="wizard-drive-copy">${escapeHtml(d.free_str)} free of ${escapeHtml(d.total_str)}</span>
      <div class="progress-bar wizard-drive-progress"><div class="fill" style="width:${pct}%;background:${color};"></div></div>
    </button>`;
  }).join('');
  setWizardStorageStatus(
    _wizDrivePath ? 'Data will be stored at: ' + _wizDrivePath + 'NOMADFieldDesk\\' : 'Select a drive above',
    !!_wizDrivePath
  );
}

function wizSelectDrive(path) { _wizDrivePath = path; wizLoadDrives(); }

function wizSetCustomPath() {
  const input = document.getElementById('wiz-custom-path');
  const path = input?.value?.trim() || '';
  if (!path) {
    setWizardStorageStatus('Enter a folder path first.', false);
    input?.focus();
    return;
  }
  _wizDrivePath = path.endsWith('\\') ? path : path + '\\';
  setWizardStorageStatus('Desk data will be stored at: ' + _wizDrivePath + 'NOMADFieldDesk\\', true);
}

// Custom tier selection state
let _wizCustomServices = [];
let _wizCustomModels = [];
let _wizCustomZims = [];

async function wizLoadTiers() {
  const el = document.getElementById('wiz-tiers');
  if (!el) return;
  try {
    _wizTiers = await _workspaceFetchJson('/api/content-tiers', {}, 'Could not load setup profiles');
  } catch (_) {
    el.innerHTML = '<div class="utility-empty-state"><strong>Setup profiles unavailable</strong><span>Retry from Home or continue later when the desk can reach the profile catalog again.</span></div>';
    setWizardSectionVisibility('wiz-tier-detail', false);
    setWizardSectionVisibility('wiz-custom-panel', false);
    return;
  }
  const tierOrder = ['essential','standard','maximum','custom'];
  const tierIcons = {essential:'&#9733;', standard:'&#9733;&#9733;', maximum:'&#9733;&#9733;&#9733;', custom:'&#9881;'};
  // Tier tone classes defined in premium/70_layout_hardening.css.
  // Add a virtual "custom" tier
  if (!_wizTiers['custom']) {
    _wizTiers['custom'] = {name:'Custom', desc:'Choose exactly which services, models, and content packs to install', services:[], zims:[], models:[], zim_count:0, est_size:'Varies'};
  }
  el.innerHTML = tierOrder.map(tid => {
    const t = _wizTiers[tid]; if (!t) return '';
    const sel = tid === _wizTier;
    const detail = tid === 'custom'
      ? '<div class="wizard-tier-meta">Pick individual items below</div>'
      : `<div class="wizard-tier-meta">${t.services.length} tools + ${t.zim_count || t.zims.length} content packs + ${t.models.length} AI model${t.models.length>1?'s':''}</div>`;
    const toneClass = 'tier-' + tid;
    return '<button type="button" class="wizard-tier-card' + (sel ? ' is-selected' : '') + '" data-shell-action="wiz-select-tier" data-tier-id="' + tid + '">'
      + '<div class="wizard-tier-copy">'
      + '<div class="wizard-tier-title ' + toneClass + '">' + tierIcons[tid] + ' ' + t.name + '</div>'
      + '<div class="wizard-tier-desc">' + t.desc + '</div>'
      + detail
      + '</div>'
      + '<div class="wizard-tier-size">'
      + '<div class="wizard-tier-size-value ' + toneClass + '">' + t.est_size + '</div>'
      + (tid !== 'custom' ? '<div class="wizard-tier-size-label">estimated</div>' : '')
      + '</div>'
      + '</button>';
  }).join('');
  // Show/hide custom panel and tier detail
  if (_wizTier === 'custom') {
    setWizardSectionVisibility('wiz-custom-panel', true);
    setWizardSectionVisibility('wiz-tier-detail', false);
    wizBuildCustomPanel();
  } else {
    setWizardSectionVisibility('wiz-custom-panel', false);
    wizShowTierDetail();
  }
}

function wizBuildCustomPanel() {
  // Populate custom checkboxes from the "maximum" tier (full list)
  const max = _wizTiers['maximum'] || _wizTiers['standard'] || {};
  const allServices = ['ollama','kiwix','cyberchef','kolibri','qdrant','stirling','flatnotes'];
  const allModels = ['qwen3:4b','qwen3:8b','alibayram/medgemma','deepseek-r1:8b','gemma3:4b','llama3.2:3b'];
  // If no custom selections yet, pre-select essentials
  if (!_wizCustomServices.length) _wizCustomServices = ['ollama','kiwix','cyberchef','stirling'];
  if (!_wizCustomModels.length) _wizCustomModels = ['qwen3:4b'];

  const svcEl = document.getElementById('wiz-custom-services');
  svcEl.innerHTML = allServices.map(s => {
    const checked = _wizCustomServices.includes(s);
    const name = (SVC[s] || {}).name || s;
    return '<label class="wizard-custom-chip">'
      + '<input type="checkbox" class="wizard-custom-check" ' + (checked?'checked':'') + ' data-change-action="wiz-toggle-custom" data-wiz-custom-type="service" data-wiz-custom-value="' + s + '">'
      + escapeHtml(name) + '</label>';
  }).join('');

  const modEl = document.getElementById('wiz-custom-models');
  modEl.innerHTML = allModels.map(m => {
    const checked = _wizCustomModels.includes(m);
    return '<label class="wizard-custom-chip">'
      + '<input type="checkbox" class="wizard-custom-check" ' + (checked?'checked':'') + ' data-change-action="wiz-toggle-custom" data-wiz-custom-type="model" data-wiz-custom-value="' + escapeHtml(m) + '">'
      + escapeHtml(m) + '</label>';
  }).join('');

  // Group ZIMs by category (from maximum tier)
  const allZims = max.zims || [];
  const cats = {};
  allZims.forEach(z => { const c = z.category || 'Other'; if (!cats[c]) cats[c] = []; cats[c].push(z); });
  // Default: select essential ZIMs only
  if (!_wizCustomZims.length) {
    const ess = _wizTiers['essential'];
    if (ess) _wizCustomZims = ess.zims.map(z => z.filename);
  }

  const zimEl = document.getElementById('wiz-custom-zims');
  zimEl.innerHTML = Object.entries(cats).map(([cat, items]) => {
    return '<div class="wizard-custom-zim-group">'
      + '<div class="wizard-custom-zim-group-title">' + escapeHtml(cat) + '</div>'
      + items.map(z => {
        const checked = _wizCustomZims.includes(z.filename);
        return '<label class="wizard-custom-zim-row">'
          + '<input type="checkbox" class="wizard-custom-check" ' + (checked?'checked':'') + ' data-change-action="wiz-toggle-custom" data-wiz-custom-type="zim" data-wiz-custom-value="' + escapeHtml(z.filename) + '">'
          + '<span class="wizard-custom-zim-name">' + escapeHtml(z.name) + '</span>'
          + '<span class="wizard-custom-zim-size">' + escapeHtml(z.size) + '</span>'
          + '</label>';
      }).join('')
      + '</div>';
  }).join('');
}

function wizToggleCustom(type, value, checked) {
  if (type === 'service') {
    if (checked) { if (!_wizCustomServices.includes(value)) _wizCustomServices.push(value); }
    else { _wizCustomServices = _wizCustomServices.filter(s => s !== value); }
  } else if (type === 'model') {
    if (checked) { if (!_wizCustomModels.includes(value)) _wizCustomModels.push(value); }
    else { _wizCustomModels = _wizCustomModels.filter(m => m !== value); }
  } else if (type === 'zim') {
    if (checked) { if (!_wizCustomZims.includes(value)) _wizCustomZims.push(value); }
    else { _wizCustomZims = _wizCustomZims.filter(z => z !== value); }
  }
}

function wizCustomSelectAll() {
  const max = _wizTiers['maximum'] || {};
  _wizCustomZims = (max.zims || []).map(z => z.filename);
  wizBuildCustomPanel();
}

function wizCustomDeselectAll() {
  _wizCustomZims = [];
  wizBuildCustomPanel();
}

function wizSelectTier(tid) { _wizTier = tid; wizLoadTiers(); }

function wizShowTierDetail() {
  const t = _wizTiers[_wizTier]; if (!t) return;
  const el = setWizardSectionVisibility('wiz-tier-detail', true);
  if (!el) return;
  const cats = {};
  (t.zims || []).forEach(z => { if (!cats[z.category]) cats[z.category] = []; cats[z.category].push(z); });
  el.innerHTML = '<div class="wizard-tier-detail-shell">'
    + '<div class="wizard-tier-detail-title">What\'s included in ' + escapeHtml(t.name) + ':</div>'
    + '<div class="wizard-tier-detail-row"><span class="wizard-tier-detail-label">Services</span><span class="wizard-tier-detail-copy">' + t.services.map(function(s){return escapeHtml((SVC[s]||{}).name||s);}).join(', ') + '</span></div>'
    + '<div class="wizard-tier-detail-row"><span class="wizard-tier-detail-label">AI Models</span><span class="wizard-tier-detail-copy">' + t.models.map(escapeHtml).join(', ') + '</span></div>'
    + '<div class="wizard-tier-detail-row wizard-tier-detail-row-stack"><span class="wizard-tier-detail-label">Content Packs (' + (t.zim_count || t.zims.length) + ')</span></div>'
    + Object.entries(cats).map(function([cat, items]) {
      return '<div class="wizard-tier-group"><div class="wizard-tier-group-title">' + escapeHtml(cat) + '</div>'
      + items.map(function(z){return '<div class="wizard-tier-zim-row"><span class="wizard-tier-zim-name">' + escapeHtml(z.name) + '</span><span class="wizard-tier-zim-size">' + escapeHtml(z.size) + '</span></div>';}).join('')
      + '</div>';}).join('')
    + '</div>';
}

async function wizStartSetup() {
  let services, zims, models;
  if (_wizTier === 'custom') {
    services = _wizCustomServices;
    models = _wizCustomModels;
    // Resolve filenames to full ZIM objects
    const max = _wizTiers['maximum'] || _wizTiers['standard'] || {};
    const allZims = max.zims || [];
    zims = allZims.filter(z => _wizCustomZims.includes(z.filename));
  } else {
    const t = _wizTiers[_wizTier]; if (!t) return;
    services = t.services;
    zims = t.zims;
    models = t.models;
  }

  if (![services, zims, models].some(items => Array.isArray(items) && items.length)) {
    toast('Select at least one service, model, or content pack before starting setup.', 'warning');
    return;
  }

  window.NOMAD_WIZARD_SHOULD_LAUNCH = true;
  wizGoPage(4);
  setWizardSectionVisibility('wiz-errors', false);
  setWizardSectionVisibility('wiz-stall-help', false);
  setShellVisibility(document.getElementById('wiz-mini-banner'), false);
  try {
    if (_wizDrivePath) {
      await _workspaceFetchOk('/api/settings/data-dir', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({path: _wizDrivePath}),
      }, 'Could not save setup storage path');
    }
    await _workspaceFetchOk('/api/wizard/setup', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({services: services, zims: zims, models: models}),
    }, 'Could not start setup');
    wizPollProgress();
  } catch (e) {
    toast(e.message || 'Could not start setup', 'error');
    wizGoPage(3);
  }
}

let _wizMinimized = false;

function wizMinimize() {
  _wizMinimized = true;
  setShellVisibility(document.getElementById('wizard'), false);
  setShellVisibility(document.getElementById('wiz-mini-banner'), true);
}

function wizRestore() {
  _wizMinimized = false;
  setShellVisibility(document.getElementById('wiz-mini-banner'), false);
  setShellVisibility(document.getElementById('wizard'), true);
}

let _wizPollInt = null;
let _wizLastProgress = 0;
let _wizStallCount = 0;
function stopWizardProgressPoll() {
  if (_wizPollInt) {
    clearInterval(_wizPollInt);
    _wizPollInt = null;
  }
  window.NomadShellRuntime?.stopInterval('wizard.progress');
}
function wizPollProgress() {
  stopWizardProgressPoll();
  _wizLastProgress = 0;
  _wizStallCount = 0;
  const runner = async () => {
    try {
      const s = await _workspaceFetchJsonSafe('/api/wizard/progress', {}, null, 'Could not load setup progress');
      if (!s) return;
      const overallFillEl = document.getElementById('wiz-overall-fill');
      const overallPctEl = document.getElementById('wiz-overall-pct');
      const currentItemEl = document.getElementById('wiz-current-item');
      const itemFillEl = document.getElementById('wiz-item-fill');
      const itemPctEl = document.getElementById('wiz-item-pct');
      const miniPctEl = document.getElementById('wiz-mini-pct');
      const miniFillEl = document.getElementById('wiz-mini-fill');
      const miniItemEl = document.getElementById('wiz-mini-item');
      const phaseLabelEl = document.getElementById('wiz-phase-label');
      const completedListEl = document.getElementById('wiz-completed-list');
      if (!overallFillEl || !overallPctEl || !currentItemEl || !itemFillEl || !itemPctEl || !miniPctEl || !miniFillEl || !miniItemEl || !phaseLabelEl || !completedListEl) return;
      overallFillEl.style.width = s.overall_progress + '%';
      overallPctEl.textContent = s.overall_progress + '%';
      currentItemEl.textContent = s.current_item || 'Starting…';
      itemFillEl.style.width = s.item_progress + '%';
      itemPctEl.textContent = s.item_progress + '%';
      miniPctEl.textContent = s.overall_progress + '%';
      miniFillEl.style.width = s.overall_progress + '%';
      miniItemEl.textContent = s.current_item || 'Starting…';

      const phaseNames = {services:'Installing tools...', starting:'Starting services...', content:'Downloading offline content...', models:'Downloading AI models...', done:'Complete!'};
      phaseLabelEl.textContent = phaseNames[s.phase] || s.phase;

      if (s.overall_progress === _wizLastProgress && s.item_progress === 0) {
        _wizStallCount++;
      } else {
        _wizStallCount = 0;
        _wizLastProgress = s.overall_progress;
      }
      setWizardSectionVisibility('wiz-stall-help', _wizStallCount > 30);

      completedListEl.innerHTML = (s.completed || []).map(c =>
        `<div class="wizard-complete-row"><span class="wizard-complete-icon">&#10003;</span><span>${escapeHtml(c)}</span></div>`).join('');

      const errEl = document.getElementById('wiz-errors');
      if ((s.errors || []).length) {
        setWizardSectionVisibility(errEl, true);
        errEl.innerHTML = s.errors.map(e => `<div class="wizard-error-row">&#10007; ${escapeHtml(e)}</div>`).join('');
      } else if (errEl) {
        errEl.innerHTML = '';
        setWizardSectionVisibility(errEl, false);
      }

      if (s.status === 'complete') {
        stopWizardProgressPoll();
        setShellVisibility(document.getElementById('wiz-mini-banner'), false);
        if (_wizMinimized) {
          _wizMinimized = false;
          setShellVisibility(document.getElementById('wizard'), true);
        }
        setTimeout(() => wizShowComplete(s), 1000);
      }
    } catch(e) { /* poll error — server may be busy */ }
  };
  if (window.NomadShellRuntime) {
    _wizPollInt = window.NomadShellRuntime.startInterval('wizard.progress', runner, 2000, {
      requireVisible: true,
    });
    runner();
    return;
  }
  _wizPollInt = setInterval(runner, 2000);
  runner();
}

function wizSkipToComplete() {
  stopWizardProgressPoll();
  persistOnboardingComplete();
  wizShowComplete({completed:[], errors:['Setup was finished later. You can still install missing tools, models, and content from Home, Library, or Settings whenever the desk is ready.']});
}

async function wizShowComplete(state) {
  wizGoPage(5);
  const lanUrlEl = document.getElementById('wiz-lan-url');
  const summaryEl = document.getElementById('wiz-summary');
  const errorSummaryEl = document.getElementById('wiz-error-summary');
  if (!lanUrlEl || !summaryEl || !errorSummaryEl) return;
  // Show LAN URL
  try {
    const net = await _workspaceFetchJson('/api/network', {}, 'Could not load LAN access URL');
    lanUrlEl.textContent = net.dashboard_url;
  } catch(e) {}
  const svcCount = state.completed.filter(c => ['ollama','kiwix','cyberchef','kolibri','qdrant','stirling'].includes(c)).length;
  const contentCount = state.completed.length - svcCount;
  summaryEl.innerHTML = `
    <div class="wizard-summary-card">
      <div class="wizard-summary-number wizard-summary-number-green">${svcCount}</div><div class="wizard-summary-label">Tools Installed</div>
    </div>
    <div class="wizard-summary-card">
      <div class="wizard-summary-number wizard-summary-number-accent">${contentCount}</div><div class="wizard-summary-label">Content Packs</div>
    </div>
    <div class="wizard-summary-card">
      <div class="wizard-summary-number ${state.errors.length === 0 ? 'wizard-summary-number-green' : 'wizard-summary-number-warning'}">${state.errors.length===0?'All Clear':state.errors.length+' Issues'}</div><div class="wizard-summary-label">Status</div>
    </div>`;
  if (state.errors.length) {
    setWizardSectionVisibility('wiz-error-summary', true);
    errorSummaryEl.innerHTML = `<div class="wizard-error-summary-card">`
      + state.errors.map(e => `<div class="wizard-error-row">&#10007; ${escapeHtml(e)}</div>`).join('') + `</div>`;
  } else {
    setWizardSectionVisibility('wiz-error-summary', false);
    errorSummaryEl.innerHTML = '';
  }
}

function skipWizard() {
  stopWizardProgressPoll();
  setShellVisibility(document.getElementById('wizard'), false);
  setShellVisibility(document.getElementById('wiz-mini-banner'), false);
  clearWizardUrlFlag();
  persistOnboardingComplete();
}

function closeTourWizard() {
  stopWizardProgressPoll();
  setShellVisibility(document.getElementById('wizard'), false);
  setShellVisibility(document.getElementById('wiz-mini-banner'), false);
  clearWizardUrlFlag();
  persistOnboardingComplete();
  refreshOnboardingSurfaces();
}
