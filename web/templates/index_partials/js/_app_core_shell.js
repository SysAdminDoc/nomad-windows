const VERSION = window.NOMAD_VERSION || '0.0.0';

let _settingsDebounceMap = {};
function _debouncedSettingSave(key, value) {
    clearTimeout(_settingsDebounceMap[key]);
    _settingsDebounceMap[key] = setTimeout(() => {
        apiPut('/api/settings', {[key]: value})
            .catch(e => { console.error('Settings save failed:', e); toast('Failed to save settings', 'error'); });
    }, 500);
}

/* ─── Theme ─── */
const THEME_NAMES = {
  nomad: 'Atlas (Light)',
  nightops: 'Midnight (Dark)',
  cyber: 'Cobalt (Blue Steel)',
  redlight: 'Ember (Warm Dark)',
  eink: 'Paper (E-Ink)',
};
const THEME_COLORS = {
  nomad: 'linear-gradient(135deg,#f7f3ec,#8f6836)',
  nightops: 'linear-gradient(135deg,#0f141c,#d0a86d)',
  cyber: 'linear-gradient(135deg,#0b1320,#71a8ff)',
  redlight: 'linear-gradient(135deg,#1a1212,#df855c)',
  eink: 'linear-gradient(135deg,#ffffff,#111111)',
};

function getThemeCssVar(name, fallback = '') {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

function getThemePalette() {
  return {
    bg: getThemeCssVar('--bg', '#f5f3eb'),
    surface: getThemeCssVar('--surface-solid', '#ffffff'),
    surface2: getThemeCssVar('--surface2', '#f0f0f0'),
    text: getThemeCssVar('--text', '#111111'),
    textDim: getThemeCssVar('--text-dim', '#666666'),
    textMuted: getThemeCssVar('--text-muted', '#8a8a8a'),
    textInverse: getThemeCssVar('--text-inverse', '#ffffff'),
    accent: getThemeCssVar('--accent', '#5b9fff'),
    green: getThemeCssVar('--green', '#4caf50'),
    orange: getThemeCssVar('--orange', '#ff9800'),
    warning: getThemeCssVar('--warning', '#c8a800'),
    red: getThemeCssVar('--red', '#f44336'),
    border: getThemeCssVar('--border', '#cccccc'),
    overlay: getThemeCssVar('--overlay-scrim', 'rgba(0,0,0,0.45)'),
    overlayStrong: getThemeCssVar('--overlay-scrim-strong', 'rgba(0,0,0,0.72)'),
  };
}

/* ─── Skeleton Loading ─── */
function showSkeleton(container, count = 6) {
  if (!container) return;
  container.innerHTML = Array(count).fill('<div class="skeleton-card"><div class="skeleton-line" style="width:60%"></div><div class="skeleton-line" style="width:80%"></div><div class="skeleton-line" style="width:40%"></div></div>').join('');
}

function inferButtonAriaLabel(button, text) {
  const title = button.getAttribute('title')?.trim();
  if (title) return title;

  const classNames = typeof button.className === 'string' ? button.className : '';
  const id = button.id || '';
  const roleHint = `${classNames} ${id}`;
  if (button.dataset.help !== undefined || /help-icon/i.test(roleHint) || text === '?') return 'Open help';
  if (/close/i.test(roleHint) || ['x', 'X', '×', '✕', '✖'].includes(text)) return 'Close';
  if (/delete|danger|remove/i.test(roleHint)) return 'Delete item';
  return '';
}

function applyShellAccessibilityDefaults(root = document) {
  if (!root) return;
  const buttons = [];
  if (root.matches?.('button')) buttons.push(root);
  if (root.querySelectorAll) root.querySelectorAll('button').forEach(button => buttons.push(button));
  if (!buttons.length) return;

  buttons.forEach(button => {
    if (!button.hasAttribute('type')) button.type = 'button';
    if (!button.hasAttribute('aria-label')) {
      const text = button.textContent?.replace(/\s+/g, ' ').trim() || '';
      const label = inferButtonAriaLabel(button, text);
      if (label && (!text || text.length <= 2 || ['?', 'x', 'X', '×', '✕', '✖'].includes(text))) {
        button.setAttribute('aria-label', label);
      }
    }
  });
}

function observeShellAccessibilityDefaults() {
  if (typeof MutationObserver !== 'function' || !document?.body) return;
  if (window.__nomadAccessibilityObserverInstalled) return;
  const observer = new MutationObserver(mutations => {
    mutations.forEach(mutation => {
      mutation.addedNodes.forEach(node => {
        if (node.nodeType === Node.ELEMENT_NODE) applyShellAccessibilityDefaults(node);
      });
    });
  });
  observer.observe(document.body, { childList: true, subtree: true });
  window.__nomadAccessibilityObserverInstalled = true;
}

applyShellAccessibilityDefaults();
observeShellAccessibilityDefaults();

function setShellVisibility(el, visible) {
  if (!el) return;
  el.classList.toggle('is-hidden', !visible);
  if (visible) {
    el.hidden = false;
    if (el.style.display === 'none') el.style.removeProperty('display');
  } else {
    el.hidden = true;
    el.style.removeProperty('display');
  }
  if (el.hasAttribute('aria-hidden')) {
    el.setAttribute('aria-hidden', visible ? 'false' : 'true');
  }
  if (typeof syncViewportChrome === 'function') {
    requestAnimationFrame(syncViewportChrome);
  }
}

function isShellVisible(el) {
  if (!el || el.classList.contains('is-hidden') || el.hidden) return false;
  const style = getComputedStyle(el);
  return style.display !== 'none' && style.visibility !== 'hidden';
}

const UTILITY_DOCK_BUTTON_IDS = {
  chat: 'copilot-utility-chat-btn',
  actions: 'copilot-utility-actions-btn',
  timer: 'copilot-utility-timer-btn',
};

function setUtilityDockButtonExpanded(kind, open) {
  const buttonId = UTILITY_DOCK_BUTTON_IDS[kind];
  if (!buttonId) return;
  document.getElementById(buttonId)?.setAttribute('aria-expanded', open ? 'true' : 'false');
}

function getLastVisibleShellElement(selector) {
  const matches = Array.from(document.querySelectorAll(selector)).filter(isShellVisible);
  return matches.length ? matches[matches.length - 1] : null;
}

function closeVisibleShellSurface(surface) {
  if (!surface) return false;
  switch (surface.id) {
    case 'command-palette-overlay':
      if (typeof toggleCommandPalette === 'function') toggleCommandPalette(false);
      else setShellVisibility(surface, false);
      return true;
    case 'shortcuts-overlay':
      if (typeof toggleShortcutsHelp === 'function') toggleShortcutsHelp(false);
      else setShellVisibility(surface, false);
      return true;
    case 'shell-health-overlay':
      if (typeof toggleShellHealth === 'function') toggleShellHealth(false);
      else setShellVisibility(surface, false);
      return true;
    case 'app-frame-overlay':
      if (typeof closeAppFrame === 'function') closeAppFrame();
      else surface.style.display = 'none';
      return true;
    case 'needs-detail-modal':
      if (typeof closeNeedsDetail === 'function') closeNeedsDetail();
      else surface.style.display = 'none';
      return true;
    case 'tccc-modal':
      surface.style.display = 'none';
      return true;
    case 'tour-overlay':
      if (typeof tourSkip === 'function') tourSkip();
      else setShellVisibility(surface, false);
      return true;
    case 'wizard':
      if (isShellVisible(document.getElementById('wiz-page-4')) && typeof wizMinimize === 'function') {
        wizMinimize();
      } else if (typeof skipWizard === 'function') {
        skipWizard();
      } else {
        setShellVisibility(surface, false);
      }
      return true;
    case 'quick-actions-menu':
      if (typeof _qaOpen !== 'undefined') _qaOpen = false;
      setShellVisibility(surface, false);
      setUtilityDockButtonExpanded('actions', false);
      return true;
    case 'lan-chat-panel':
      if (typeof _lanChatOpen !== 'undefined') _lanChatOpen = false;
      setShellVisibility(surface, false);
      setUtilityDockButtonExpanded('chat', false);
      if (typeof setLanChatCompact === 'function') setLanChatCompact(true);
      if (typeof stopLanMessagePolling === 'function') stopLanMessagePolling();
      else if (typeof _lanPoll !== 'undefined' && _lanPoll) { clearInterval(_lanPoll); _lanPoll = null; }
      if (typeof stopLanPresencePolling === 'function') stopLanPresencePolling();
      return true;
    case 'timer-panel':
      if (typeof _timerPanelOpen !== 'undefined') _timerPanelOpen = false;
      setShellVisibility(surface, false);
      setUtilityDockButtonExpanded('timer', false);
      if (typeof stopTimerPolling === 'function') stopTimerPolling();
      else if (typeof _timerPoll !== 'undefined' && _timerPoll) { clearInterval(_timerPoll); _timerPoll = null; }
      return true;
    default:
      break;
  }

  if (surface.classList.contains('generated-modal-overlay')) {
    surface.remove();
    return true;
  }

  if (surface.classList.contains('modal-overlay')) {
    const closeButton = surface.querySelector('[data-shell-action="close-generated-modal"], [data-shell-action="close-ai-sitrep"], .modal-close, .settings-modal-close');
    if (closeButton && typeof closeButton.click === 'function') {
      closeButton.click();
      return true;
    }
    surface.style.display = 'none';
    if (surface.hasAttribute('aria-hidden')) surface.setAttribute('aria-hidden', 'true');
    return true;
  }

  return false;
}

function closeTopVisibleShellSurface() {
  const prioritizedIds = [
    'command-palette-overlay',
    'shortcuts-overlay',
    'shell-health-overlay',
    'app-frame-overlay',
    'needs-detail-modal',
    'tccc-modal',
    'tour-overlay',
    'wizard',
  ];
  for (const id of prioritizedIds) {
    const surface = document.getElementById(id);
    if (isShellVisible(surface)) return closeVisibleShellSurface(surface);
  }

  const modal = getLastVisibleShellElement('.generated-modal-overlay, .modal-overlay');
  if (modal) return closeVisibleShellSurface(modal);

  const utilityIds = ['quick-actions-menu', 'lan-chat-panel', 'timer-panel'];
  for (const id of utilityIds) {
    const surface = document.getElementById(id);
    if (isShellVisible(surface)) return closeVisibleShellSurface(surface);
  }

  return false;
}

/* ─── Sidebar Sub-Menu Toggle ─── */
function updateSidebarSubs() {
  const activeTab = document.querySelector('.tab.active');
  const activeId = activeTab ? activeTab.dataset.tab : '';
  document.querySelectorAll('.sidebar-sub').forEach(sub => {
    sub.classList.toggle('open', sub.dataset.parent === activeId);
  });
}
// Hook into tab switching
document.querySelectorAll('.sidebar-nav .tab').forEach(tab => {
  tab.addEventListener('click', () => setTimeout(updateSidebarSubs, 50));
});
updateSidebarSubs();

function scrollToSection(id) {
  setTimeout(() => {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({behavior:'smooth', block:'start'});
  }, 200);
}

function getWorkspaceRouteMap() {
  return window.NOMAD_WORKSPACE_ROUTES || {};
}

function getWorkspacePageTab() {
  return window.NOMAD_ACTIVE_TAB || document.querySelector('.tab.active')?.dataset.tab || 'services';
}

function hasWorkspaceTabContent(tabId) {
  return !!document.getElementById(`tab-${tabId}`);
}

const NOMAD_EMBEDDED_WORKSPACE_STATE_KEY = 'nomad-embedded-workspace-state';

function cloneJsonFallback(fallback) {
  if (typeof fallback === 'function') return fallback();
  if (Array.isArray(fallback)) return [...fallback];
  if (fallback && typeof fallback === 'object') return { ...fallback };
  return fallback;
}

function safeJsonParse(value, fallback = null, options = {}) {
  const storage = options.storage || null;
  const key = options.key || '';
  const removeOnError = options.removeOnError !== false;
  if (value == null || value === '') return cloneJsonFallback(fallback);
  try {
    const parsed = typeof value === 'string' ? JSON.parse(value) : value;
    return parsed == null ? cloneJsonFallback(fallback) : parsed;
  } catch (error) {
    if (storage && key && removeOnError) {
      try { storage.removeItem(key); } catch (_) {}
    }
    return cloneJsonFallback(fallback);
  }
}

function readJsonStorage(storage, key, fallback = null, options = {}) {
  if (!storage || !key) return cloneJsonFallback(fallback);
  try {
    const value = storage.getItem(key);
    return safeJsonParse(value, fallback, { ...options, storage, key });
  } catch (_) {
    return cloneJsonFallback(fallback);
  }
}

window.safeJsonParse = window.safeJsonParse || safeJsonParse;
window.readJsonStorage = window.readJsonStorage || readJsonStorage;

function loadEmbeddedWorkspaceStates() {
  return readJsonStorage(sessionStorage, NOMAD_EMBEDDED_WORKSPACE_STATE_KEY, {});
}

function createEmbeddedWorkspaceStateStore() {
  let cache = loadEmbeddedWorkspaceStates();

  function persist() {
    try {
      sessionStorage.setItem(NOMAD_EMBEDDED_WORKSPACE_STATE_KEY, JSON.stringify(cache));
    } catch (_) {}
    window.NomadShellRuntime?.notify?.();
  }

  return {
    save(tabId, snapshot) {
      if (!tabId || !snapshot || typeof snapshot !== 'object') return null;
      cache[tabId] = { tabId, updatedAt: Date.now(), ...snapshot };
      persist();
      return cache[tabId];
    },
    get(tabId) {
      return tabId ? cache[tabId] || null : null;
    },
    all() {
      return { ...cache };
    },
    clear(tabId) {
      if (!tabId || !cache[tabId]) return;
      delete cache[tabId];
      persist();
    },
  };
}

window.NomadEmbeddedWorkspaceState = window.NomadEmbeddedWorkspaceState || createEmbeddedWorkspaceStateStore();

function buildWorkspaceUrl(tabId, options = {}) {
  const route = getWorkspaceRouteMap()[tabId] || window.location.pathname || '/';
  const url = new URL(route, window.location.origin);
  url.searchParams.set('tab', tabId);
  if (options.prepSub) url.searchParams.set('prep', options.prepSub);
  if (options.mediaSub) url.searchParams.set('media', options.mediaSub);
  if (options.checklistFocus !== undefined && options.checklistFocus !== null) {
    url.searchParams.set('checklist_focus', String(options.checklistFocus));
  }
  if (options.showInvForm) url.searchParams.set('show_inv_form', '1');
  if (options.guideStart) url.searchParams.set('guide_start', options.guideStart);
  if (options.scrollTarget) url.hash = options.scrollTarget;
  return url.toString();
}

function navigateToWorkspace(tabId, options = {}) {
  window.location.assign(buildWorkspaceUrl(tabId, options));
}

function runWorkspaceLeaveCallback(tabId) {
  if (!tabId || !window._nomadTabLeaveCallbacks || !window._nomadTabLeaveCallbacks[tabId]) return;
  try {
    window._nomadTabLeaveCallbacks[tabId]();
  } catch (e) {}
}

/* ─── Lazy Tab Init ─── */
const _tabInitialized = {};

function activateWorkspaceTab(tab) {
  const tabId = tab.dataset.tab;
  const previousTabId = window.NOMAD_ACTIVE_TAB || document.querySelector('.tab.active')?.dataset.tab || '';
  const tabContent = document.getElementById('tab-' + tabId);
  if (!tabContent) {
    navigateToWorkspace(tabId);
    return false;
  }
  if (previousTabId && previousTabId !== tabId) runWorkspaceLeaveCallback(previousTabId);
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  tab.classList.add('active');
  tabContent.classList.add('active');
  window.NOMAD_ACTIVE_TAB = tabId;
  updateSidebarSubs();
  window.scrollTo(0, 0);
  const firstVisit = !_tabInitialized[tabId];
  _tabInitialized[tabId] = true;
  if (tabId === 'services' && typeof refreshServicesWorkspacePanels === 'function') {
    refreshServicesWorkspacePanels();
  }
  if (tabId === 'ai-chat') { loadModels(); loadConversations(); pollPullProgress(); }
  if (tabId === 'notes') loadNotes();
  if (tabId === 'settings') { loadSystemInfo(); loadModelManager(); loadSettings(); startLiveGauges(); loadLogViewer(); loadDiskMonitor(); loadStartupState(); loadOllamaHost(); updateLastBackup(); loadNodeIdentity(); loadSyncLog(); loadConflicts(); loadGroupExercises(); loadDataSummary(); loadTrainingDatasets(); loadTrainingJobs(); loadBackups(); loadBackupConfig(); if (typeof refreshSettingsWorkspacePanels === 'function') refreshSettingsWorkspacePanels(); }
  if (tabId === 'kiwix-library') { loadZimList(); loadZimCatalog(); loadZimDownloads(); loadPDFList(); loadWikipediaTiers(); }
  if (tabId === 'maps') {
    if (firstVisit) { loadMaps(); loadMapSources(); }
    loadWPDistances(); renderMapBookmarks(); loadSavedRoutes();
  }
  if (tabId === 'benchmark') { loadBenchHistory(); loadBuilderTag(); }
  if (tabId === 'media') { loadMediaTab(); }
  if (tabId === 'tools') { loadDrillHistory(); renderScenarioSelector(); }
  if (tabId === 'preparedness') { loadPrepTab(); }
  if (tabId === 'readiness') { loadReadinessScore(); loadReadinessNeeds(); }
  if (tabId === 'water-mgmt') { loadWaterMgmt(); }
  if (tabId === 'financial') { loadFinancial(); }
  if (tabId === 'vehicles') { loadVehicles(); }
  if (tabId === 'loadout') { loadLoadout(); }
  if (tabId === 'timeline') { loadTimeline(); }
  if (tabId === 'threat-intel') { loadThreatIntel(); }
  if (tabId === 'situation-room') {
    if (firstVisit) initSituationRoom();
  }
  // Native tab visibility callbacks (NukeMap, VIPTrack)
  if (window._nomadTabCallbacks && window._nomadTabCallbacks[tabId]) {
    try { window._nomadTabCallbacks[tabId](); } catch(e) {}
  }
  if (typeof window.nukemapOnVisible === 'function' && tabId === 'nukemap') {
    try { window.nukemapOnVisible(); } catch(e) {}
  }
  if (tabId !== 'situation-room' && typeof _restoreCopilotDock === 'function') { _restoreCopilotDock(); }
  if (typeof syncWorkspaceUrlState === 'function') syncWorkspaceUrlState();
  return true;
}

function openWorkspaceRouteAware(tabId, options = {}) {
  const tab = document.querySelector(`.tab[data-tab="${tabId}"]`);
  if (tab && hasWorkspaceTabContent(tabId)) {
    activateWorkspaceTab(tab);
    return true;
  }
  navigateToWorkspace(tabId, options);
  return false;
}

window.addEventListener('pagehide', () => {
  const activeTab = window.NOMAD_ACTIVE_TAB || document.querySelector('.tab.active')?.dataset.tab || '';
  runWorkspaceLeaveCallback(activeTab);
});

function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('nomad-theme', theme);
  document.querySelectorAll('.theme-btn').forEach(b => {
    const active = b.dataset.t === theme;
    b.classList.toggle('active', active);
    b.setAttribute('aria-pressed', active ? 'true' : 'false');
  });
  updateThemeIndicator(theme);
  if (typeof updateCustomizeTheme === 'function') {
    updateCustomizeTheme();
  }
  _debouncedSettingSave('theme', theme);
  // Auto-switch map tiles if tile selector is on "auto"
  const tileSelector = document.getElementById('map-tile-selector');
  if (tileSelector && tileSelector.value === 'auto') {
    applyMapThemeTiles(theme);
  }
}

/* ─── UI Zoom Control ─── */
function setUIZoom(level) {
  document.documentElement.setAttribute('data-zoom', level);
  localStorage.setItem('nomad-ui-zoom', level);
  ['small','default','large','xlarge'].forEach(z => {
    ['zoom-', 'cust-zoom-'].forEach(prefix => {
      const btn = document.getElementById(prefix + z);
      if (!btn) return;
      btn.classList.toggle('btn-primary', z === level);
      btn.classList.toggle('btn-sm', true);
      btn.setAttribute('aria-pressed', z === level ? 'true' : 'false');
    });
  });
}
// Init zoom from localStorage
(function initZoom() {
  const z = localStorage.getItem('nomad-ui-zoom') || 'default';
  setUIZoom(z);
})();

/* ─── Density Control ─── */
const DENSITY_LEVELS = ['ultra', 'compact', 'comfortable'];

function setDensity(level) {
  const safeLevel = DENSITY_LEVELS.includes(level) ? level : 'compact';
  document.documentElement.setAttribute('data-density', safeLevel);
  localStorage.setItem('nomad-density', safeLevel);
  DENSITY_LEVELS.forEach((densityLevel) => {
    const btn = document.getElementById(`cust-density-${densityLevel}`);
    if (!btn) return;
    btn.classList.toggle('btn-primary', densityLevel === safeLevel);
    btn.classList.toggle('btn-sm', true);
    btn.setAttribute('aria-pressed', densityLevel === safeLevel ? 'true' : 'false');
  });
  if (typeof updateCustomizeDensity === 'function') {
    updateCustomizeDensity();
  }
}

(function initDensity() {
  const density = localStorage.getItem('nomad-density') || 'compact';
  setDensity(density);
})();

function updateThemeIndicator(theme) {
  const dot = document.getElementById('active-theme-dot');
  const label = document.getElementById('active-theme-label');
  if (dot) dot.style.background = THEME_COLORS[theme] || '';
  if (label) label.textContent = THEME_NAMES[theme] || theme;
}
// Keyboard support for theme buttons
document.addEventListener('keydown', e => {
  if ((e.key === 'Enter' || e.key === ' ') && e.target.classList.contains('theme-btn') && e.target.tagName !== 'BUTTON') {
    e.preventDefault(); e.target.click();
  }
});
(function initTheme() {
  let saved = localStorage.getItem('nomad-theme');
  // Auto-detect OS dark mode on first run (no saved preference)
  if (!saved) {
    saved = window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'nightops' : 'nomad';
  }
  if (saved !== 'nomad') document.documentElement.setAttribute('data-theme', saved);
  document.querySelectorAll('.theme-btn').forEach(b => {
    const active = b.dataset.t === saved;
    b.classList.toggle('active', active);
    b.setAttribute('aria-pressed', active ? 'true' : 'false');
  });
  updateThemeIndicator(saved);
  if (typeof updateCustomizeTheme === 'function') updateCustomizeTheme();
})();
// Init sidebar sub-menus
setTimeout(updateSidebarSubs, 100);

/* ─── Dashboard Mode System ─── */
let _dashboardMode = 'command';
let _dashboardModeConfig = null;

async function setMode(mode) {
  _dashboardMode = mode;
  document.documentElement.setAttribute('data-mode', mode);
  localStorage.setItem('nomad-mode', mode);
  document.querySelectorAll('.mode-btn').forEach(b => {
    const active = b.dataset.mode === mode;
    b.classList.toggle('active', active);
    b.setAttribute('aria-pressed', active ? 'true' : 'false');
  });
  _debouncedSettingSave('dashboard_mode', mode);
  // Fetch mode config and apply
  try {
    const data = await safeFetch('/api/dashboard/mode', {}, {mode:'command',config:{}});
    _dashboardModeConfig = data.config;
    applyModeVisibility();
    updateCopilotButtons();
    // Update settings mode panel
    document.querySelectorAll('.mode-option').forEach(o => o.classList.toggle('active-mode', o.dataset.modeOpt === mode));
    const settingsLabel = document.getElementById('settings-mode-label');
    if (settingsLabel && _dashboardModeConfig) settingsLabel.textContent = _dashboardModeConfig.label || mode;
  } catch(e) {}
}

function applyModeVisibility() {
  if (!_dashboardModeConfig) return;
  const cfg = _dashboardModeConfig;
  // Sidebar tab visibility
  const hideTabs = new Set(cfg.sidebar_hide || []);
  document.querySelectorAll('.sidebar-nav .tab[data-tab]').forEach(tab => {
    const tabId = tab.dataset.tab;
    tab.style.display = hideTabs.has(tabId) ? 'none' : '';
  });
  // Prep sub-tab visibility
  const hidePreps = new Set(cfg.prep_hide || []);
  document.querySelectorAll('.prep-subtab[data-psub]').forEach(btn => {
    btn.style.display = hidePreps.has(btn.dataset.psub) ? 'none' : '';
  });
  // Reorder prep sub-tabs if order specified
  if (cfg.prep_order && cfg.prep_order.length) {
    const container = document.querySelector('.prep-subtabs');
    if (container) {
      const tabs = {};
      container.querySelectorAll('.prep-subtab[data-psub]').forEach(b => { tabs[b.dataset.psub] = b; });
      for (const key of cfg.prep_order) {
        if (tabs[key]) container.appendChild(tabs[key]);
      }
    }
  }
  // Update mode indicator
  const label = document.getElementById('mode-label');
  if (label) label.textContent = cfg.label || _dashboardMode;
}

(function initMode() {
  const validModes = ['command', 'homestead', 'minimal'];
  let saved = localStorage.getItem('nomad-mode') || 'command';
  if (!validModes.includes(saved)) saved = 'command';
  _dashboardMode = saved;
  document.documentElement.setAttribute('data-mode', saved);
  document.querySelectorAll('.mode-btn').forEach(b => {
    const active = b.dataset.mode === saved;
    b.classList.toggle('active', active);
    b.setAttribute('aria-pressed', active ? 'true' : 'false');
  });
  // Defer full config load until after DOM ready
  setTimeout(() => setMode(saved), 100);
})();

/* ─── Shell Runtime ─── */
function normalizeShellRuntimeUrl(url) {
  try {
    const parsed = new URL(String(url || ''), window.location.origin);
    return `${parsed.pathname}${parsed.search}`;
  } catch (_) {
    return String(url || '');
  }
}

function createShellRuntime() {
  const intervals = new Map();
  const listeners = new Set();
  const recentFetches = [];
  let inflightFetches = 0;

  function getActiveTab() {
    return window.NOMAD_ACTIVE_TAB
      || document.querySelector('.tab.active')?.dataset.tab
      || getWorkspacePageTab()
      || '';
  }

  function shouldRun(options = {}) {
    if (options.requireVisible !== false && document.hidden) return false;
    if (options.tabId && getActiveTab() !== options.tabId) return false;
    return true;
  }

  function snapshot() {
    return {
      activeTab: getActiveTab(),
      hidden: document.hidden,
      inflightFetches,
      intervals: Array.from(intervals.values())
        .map(({ timerId, ...record }) => ({ ...record }))
        .sort((left, right) => left.name.localeCompare(right.name)),
      recentFetches: recentFetches.slice(0, 10),
    };
  }

  function notify() {
    const state = snapshot();
    listeners.forEach((listener) => {
      try {
        listener(state);
      } catch (_) {}
    });
  }

  function startInterval(name, callback, ms, options = {}) {
    if (!name || typeof callback !== 'function') return null;
    stopInterval(name);
    const record = {
      name,
      tabId: options.tabId || '',
      requireVisible: options.requireVisible !== false,
      intervalMs: ms,
      lastRunAt: 0,
      runCount: 0,
      timerId: null,
    };
    const runner = () => {
      if (!shouldRun(record)) return;
      record.lastRunAt = Date.now();
      record.runCount += 1;
      notify();
      try {
        const result = callback();
        if (result && typeof result.catch === 'function') {
          result.catch((error) => console.warn(`Interval ${name} failed:`, error));
        }
      } catch (error) {
        console.warn(`Interval ${name} failed:`, error);
      }
    };
    record.timerId = setInterval(runner, ms);
    intervals.set(name, record);
    notify();
    return record.timerId;
  }

  function stopInterval(name) {
    const record = intervals.get(name);
    if (!record) return;
    clearInterval(record.timerId);
    intervals.delete(name);
    notify();
  }

  function trackFetchStart(url, method) {
    inflightFetches += 1;
    const entry = {
      method: String(method || 'GET').toUpperCase(),
      status: 'Pending',
      ok: null,
      url: normalizeShellRuntimeUrl(url),
      startedAt: Date.now(),
      finishedAt: 0,
    };
    recentFetches.unshift(entry);
    if (recentFetches.length > 12) recentFetches.length = 12;
    notify();
    return entry;
  }

  function trackFetchEnd(entry, status, ok) {
    inflightFetches = Math.max(0, inflightFetches - 1);
    if (entry) {
      entry.status = String(status || 'ERR');
      entry.ok = !!ok;
      entry.finishedAt = Date.now();
    }
    notify();
  }

  function subscribe(listener) {
    if (typeof listener !== 'function') return () => {};
    listeners.add(listener);
    listener(snapshot());
    return () => listeners.delete(listener);
  }

  document.addEventListener('visibilitychange', notify);

  return {
    getActiveTab,
    isTabActive(tabId) {
      return !tabId || getActiveTab() === tabId;
    },
    shouldRun,
    startInterval,
    stopInterval,
    trackFetchStart,
    trackFetchEnd,
    subscribe,
    snapshot,
    notify,
  };
}

window.NomadShellRuntime = window.NomadShellRuntime || createShellRuntime();

if (typeof window.fetch === 'function' && !window.__nomadFetchInstrumented) {
  const originalFetch = window.fetch.bind(window);
  window.fetch = (...args) => {
    const [resource, init] = args;
    const url = typeof resource === 'string'
      ? resource
      : resource?.url || '';
    const method = init?.method || resource?.method || 'GET';
    const fetchEntry = window.NomadShellRuntime.trackFetchStart(url, method);
    return originalFetch(...args)
      .then((response) => {
        window.NomadShellRuntime.trackFetchEnd(fetchEntry, response.status, response.ok);
        return response;
      })
      .catch((error) => {
        window.NomadShellRuntime.trackFetchEnd(fetchEntry, 'ERR', false);
        throw error;
      });
  };
  window.__nomadFetchInstrumented = true;
}

let _shellHealthUnsubscribe = null;
let _shellHealthReturnFocus = null;

function formatShellRuntimeAge(timestamp) {
  if (!timestamp) return 'idle';
  const seconds = Math.max(0, Math.round((Date.now() - timestamp) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  return `${minutes}m ago`;
}

function renderShellHealth(snapshot = window.NomadShellRuntime?.snapshot?.()) {
  const overlay = document.getElementById('shell-health-overlay');
  if (!overlay || overlay.hidden || !snapshot) return;
  const embeddedStates = Object.values(window.NomadEmbeddedWorkspaceState?.all?.() || {})
    .sort((left, right) => String(left.tabId || '').localeCompare(String(right.tabId || '')));
  const activeTab = document.getElementById('shell-health-active-tab');
  const visibility = document.getElementById('shell-health-visibility');
  const fetchState = document.getElementById('shell-health-fetch-state');
  const intervalCount = document.getElementById('shell-health-interval-count');
  const requestCount = document.getElementById('shell-health-request-count');
  const embeddedCount = document.getElementById('shell-health-embedded-count');
  const intervalsEl = document.getElementById('shell-health-intervals');
  const requestsEl = document.getElementById('shell-health-requests');
  const embeddedEl = document.getElementById('shell-health-embedded');

  if (activeTab) activeTab.textContent = `Desk: ${snapshot.activeTab || 'unknown'}`;
  if (visibility) visibility.textContent = snapshot.hidden ? 'Window hidden' : 'Window visible';
  if (fetchState) fetchState.textContent = snapshot.inflightFetches > 0 ? `${snapshot.inflightFetches} fetches in flight` : 'No active fetches';
  if (intervalCount) intervalCount.textContent = `${snapshot.intervals.length} active`;
  if (requestCount) requestCount.textContent = `${snapshot.recentFetches.length} recent`;
  if (embeddedCount) embeddedCount.textContent = `${embeddedStates.length} tracked`;

  if (intervalsEl) {
    intervalsEl.innerHTML = snapshot.intervals.length
      ? snapshot.intervals.map((interval) => `
        <div class="shell-health-row">
          <div class="shell-health-row-main">
            <span class="shell-health-row-title">${escapeHtml(interval.name)}</span>
            <span class="shell-health-row-meta">${interval.intervalMs}ms${interval.tabId ? ` · ${escapeHtml(interval.tabId)}` : ''}${interval.requireVisible ? ' · visible' : ''}</span>
          </div>
          <span class="shell-health-row-meta">${interval.runCount} runs · ${escapeHtml(formatShellRuntimeAge(interval.lastRunAt))}</span>
        </div>
      `).join('')
      : '<div class="shell-health-empty">No runtime intervals are registered right now.</div>';
  }

  if (requestsEl) {
    requestsEl.innerHTML = snapshot.recentFetches.length
      ? snapshot.recentFetches.map((request) => `
        <div class="shell-health-row">
          <div class="shell-health-row-main">
            <span class="shell-health-row-title">${escapeHtml(request.method)} ${escapeHtml(request.url)}</span>
            <span class="shell-health-row-meta">${request.ok === false ? 'Request failed' : request.ok === true ? 'Completed' : 'Pending'}</span>
          </div>
          <span class="shell-health-row-meta">${escapeHtml(request.status)} · ${escapeHtml(formatShellRuntimeAge(request.finishedAt || request.startedAt))}</span>
        </div>
      `).join('')
      : '<div class="shell-health-empty">No recent fetches yet for this session.</div>';
  }

  if (embeddedEl) {
    embeddedEl.innerHTML = embeddedStates.length
      ? embeddedStates.map((state) => `
        <div class="shell-health-row">
          <div class="shell-health-row-main">
            <span class="shell-health-row-title">${escapeHtml(state.tabId || 'embedded')}</span>
            <span class="shell-health-row-meta">${state.tabPaused ? 'paused' : 'active'}${state.reason ? ` · ${escapeHtml(state.reason)}` : ''}</span>
          </div>
          <span class="shell-health-row-meta">${escapeHtml(formatShellRuntimeAge(state.updatedAt || state.savedAt))}</span>
        </div>
      `).join('')
      : '<div class="shell-health-empty">No embedded workspace state has been captured yet.</div>';
  }
}

function toggleShellHealth(force) {
  const overlay = document.getElementById('shell-health-overlay');
  if (!overlay) return;
  const shouldOpen = typeof force === 'boolean' ? force : !isShellVisible(overlay);
  if (!shouldOpen) {
    setShellVisibility(overlay, false);
    if (_shellHealthUnsubscribe) {
      _shellHealthUnsubscribe();
      _shellHealthUnsubscribe = null;
    }
    const returnFocus = _shellHealthReturnFocus;
    _shellHealthReturnFocus = null;
    if (returnFocus && returnFocus.isConnected && typeof returnFocus.focus === 'function') {
      requestAnimationFrame(() => returnFocus.focus());
    }
    return;
  }
  _shellHealthReturnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  setShellVisibility(overlay, true);
  renderShellHealth();
  if (_shellHealthUnsubscribe) _shellHealthUnsubscribe();
  _shellHealthUnsubscribe = window.NomadShellRuntime.subscribe(renderShellHealth);
  requestAnimationFrame(() => overlay.querySelector('.shell-health-close')?.focus());
}

document.addEventListener('keydown', (event) => {
  if (event.defaultPrevented) return;
  if (event.key === 'Escape' && !document.getElementById('shell-health-overlay')?.hidden) {
    event.preventDefault();
    toggleShellHealth(false);
    return;
  }
  if (event.ctrlKey && event.altKey && event.key.toLowerCase() === 'h') {
    event.preventDefault();
    toggleShellHealth();
  }
});

let chatMessages = [];
let currentNoteId = null;
let saveTimer = null;
let isSending = false;
let _chatAbortCtrl = null;
let _streamRAF = null;
let currentConvoId = null;
let allConvos = [];
let aiName = 'AI';
let _catalogTiers = {};
/* ─── Branch State ─── */
let currentBranchId = null;
let parentConvoId = null;
let branchMsgIdx = null;

/* ─── Tabs ─── */
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', e => {
    if (!hasWorkspaceTabContent(tab.dataset.tab)) {
      e.preventDefault();
      navigateToWorkspace(tab.dataset.tab);
      return;
    }
    activateWorkspaceTab(tab);
  });
});

/* ─── Toast: loaded from /static/js/toast.js ─── */

/* ─── OfflineSync: loaded from /static/js/offline.js ─── */

async function offlineFullSync() {
  toast('Starting full offline sync...', 'info');
  const r = await OfflineSync.fullSync();
  if (r) {
    toast(`Offline sync complete: ${r.tables} tables cached`, 'success');
    const el = document.getElementById('offline-sync-result');
    if (el) el.textContent = `Last synced: ${r.timestamp}`;
  } else {
    toast('Offline sync failed', 'error');
  }
}

async function offlineStatus() {
  const s = await OfflineSync.getSyncStatus();
  const el = document.getElementById('offline-sync-result');
  if (!el) return;
  if (s && s.value) {
    el.textContent = `Last sync: ${s.value} | Type: ${s.fullSync ? 'Full' : 'Incremental'}${s.changes !== undefined ? ' | Changes: ' + s.changes : ''}`;
  } else {
    el.textContent = 'No sync data found. Run a full sync first.';
  }
}

async function offlineClear() {
  if (!confirm('Clear all offline cached data?')) return;
  try {
    const dbs = await indexedDB.databases();
    for (const db of dbs) {
      if (db.name === 'nomad-offline') indexedDB.deleteDatabase(db.name);
    }
    OfflineSync._db = null;
    toast('Offline cache cleared', 'success');
    const el = document.getElementById('offline-sync-result');
    if (el) el.textContent = 'Cache cleared.';
  } catch(e) { toast('Failed to clear cache', 'error'); }
}

/* ─── BatteryManager: loaded from /static/js/battery.js ─── */

/* ─── Voice-to-Inventory Natural Language Parser ─── */
const VoiceInput = {
  _recognition: null,
  _targetCallback: null,
  _active: false,

  init() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return false;
    this._recognition = new SpeechRecognition();
    this._recognition.continuous = false;
    this._recognition.interimResults = false;
    this._recognition.lang = 'en-US';
    this._recognition.onresult = (e) => {
      const text = e.results[0][0].transcript;
      if (this._targetCallback) this._targetCallback(text);
    };
    this._recognition.onerror = (e) => { this._active = false; toast('Voice recognition error: ' + e.error, 'warning'); };
    this._recognition.onend = () => { this._active = false; };
    return true;
  },

  start(callback) {
    if (!this._recognition && !this.init()) {
      toast('Voice input not supported in this browser', 'warning');
      return;
    }
    this._targetCallback = callback;
    this._active = true;
    this._recognition.start();
    toast('Listening... speak now', 'info');
  },

  stop() {
    if (this._recognition && this._active) this._recognition.stop();
    this._active = false;
  },

  isActive() { return this._active; },

  parseInventoryCommand(text) {
    // Parse: "add 10 cans of beans to pantry" or "10 gallons water" or "remove 5 batteries"
    const t = text.toLowerCase().trim();
    let action = 'add';
    let cleaned = t;
    if (t.startsWith('remove ') || t.startsWith('delete ') || t.startsWith('subtract ')) {
      action = 'remove';
      cleaned = t.replace(/^(remove|delete|subtract)\s+/, '');
    } else if (t.startsWith('add ')) {
      cleaned = t.replace(/^add\s+/, '');
    }

    // Extract quantity
    const qtyMatch = cleaned.match(/^(\d+(?:\.\d+)?)\s+/);
    let quantity = 1;
    if (qtyMatch) {
      quantity = parseFloat(qtyMatch[1]);
      cleaned = cleaned.slice(qtyMatch[0].length);
    }

    // Extract unit (cans of, bottles of, gallons of, pounds of, boxes of, etc.)
    const unitMatch = cleaned.match(/^(cans?|bottles?|gallons?|liters?|pounds?|lbs?|boxes?|bags?|packs?|rolls?|pairs?|units?|pieces?|each|dozen)\s+(of\s+)?/i);
    let unit = 'units';
    if (unitMatch) {
      unit = unitMatch[1].replace(/s$/, '');
      cleaned = cleaned.slice(unitMatch[0].length);
    }

    // Extract location (to/in/at location)
    const locMatch = cleaned.match(/\s+(to|in|at|for)\s+(.+?)$/i);
    let location = '';
    if (locMatch) {
      location = locMatch[2].trim();
      cleaned = cleaned.slice(0, locMatch.index);
    }

    // Extract category hints
    let category = 'general';
    const catMap = {
      'food': ['bean', 'rice', 'pasta', 'flour', 'sugar', 'salt', 'canned', 'meat', 'fruit', 'vegetable', 'soup', 'coffee', 'tea', 'oil', 'honey', 'oat'],
      'water': ['water', 'purif', 'filter'],
      'medical': ['bandage', 'gauze', 'aspirin', 'ibuprofen', 'antibiotic', 'medicine', 'med ', 'first aid', 'tourniquet'],
      'tools': ['knife', 'saw', 'hammer', 'wrench', 'tape', 'rope', 'cord', 'wire', 'tool'],
      'fuel': ['gas', 'diesel', 'propane', 'kerosene', 'fuel', 'butane', 'charcoal'],
      'ammo': ['ammo', 'ammunition', 'round', 'bullet', 'shell', 'cartridge'],
      'hygiene': ['soap', 'shampoo', 'toothpaste', 'toilet paper', 'sanitizer', 'wipes'],
      'electronics': ['battery', 'batteries', 'radio', 'flashlight', 'lantern', 'solar', 'charger'],
    };
    for (const [cat, keywords] of Object.entries(catMap)) {
      if (keywords.some(k => cleaned.includes(k))) { category = cat; break; }
    }

    return { action, name: cleaned.trim(), quantity, unit, category, location };
  }
};

function voiceAddInventory() {
  VoiceInput.start((text) => {
    const parsed = VoiceInput.parseInventoryCommand(text);
    toast(`Heard: "${text}" \u2192 ${parsed.action} ${parsed.quantity} ${parsed.unit} ${parsed.name}`, 'info');

    if (parsed.action === 'add' && parsed.name) {
      // Auto-fill inventory form
      const nameEl = document.getElementById('inv-name');
      const qtyEl = document.getElementById('inv-quantity') || document.getElementById('inv-qty');
      const unitEl = document.getElementById('inv-unit');
      const catEl = document.getElementById('inv-category');
      const locEl = document.getElementById('inv-location');

      if (nameEl) nameEl.value = parsed.name;
      if (qtyEl) qtyEl.value = parsed.quantity;
      if (unitEl) unitEl.value = parsed.unit;
      if (catEl) catEl.value = parsed.category;
      if (locEl && parsed.location) locEl.value = parsed.location;

      // Show the inventory form if not visible
      if (typeof showInvForm === 'function') showInvForm();
      toast(`Form filled: ${parsed.quantity} ${parsed.unit} of ${parsed.name} (${parsed.category})`, 'success');
    }
  });
}

/* ─── Form State Recovery ─── */
const FormStateRecovery = {
  _prefix: 'nomad-form-',
  _timers: {},
  _MAX_AGE: 24 * 60 * 60 * 1000,
  save(formId, data) {
    try { localStorage.setItem(this._prefix + formId, JSON.stringify({...data, _ts: Date.now()})); } catch(e) {}
  },
  load(formId) {
    try {
      const data = readJsonStorage(localStorage, this._prefix + formId, null);
      if (!data || typeof data !== 'object') return null;
      if (Date.now() - (data._ts || 0) > this._MAX_AGE) { this.clear(formId); return null; }
      const {_ts, ...rest} = data;
      return Object.keys(rest).length ? rest : null;
    } catch(e) { return null; }
  },
  clear(formId) { try { localStorage.removeItem(this._prefix + formId); } catch(e) {} },
  clearAll() {
    try { Object.keys(localStorage).filter(k => k.startsWith(this._prefix)).forEach(k => localStorage.removeItem(k)); } catch(e) {}
  },
  attach(formId, fieldMap) {
    // fieldMap: {key: elementId, ...}
    const save = () => {
      const data = {};
      for (const [key, elId] of Object.entries(fieldMap)) {
        const el = document.getElementById(elId);
        if (el) data[key] = el.value;
      }
      this.save(formId, data);
    };
    for (const elId of Object.values(fieldMap)) {
      const el = document.getElementById(elId);
      if (el) {
        el.addEventListener('input', () => {
          clearTimeout(this._timers[formId]);
          this._timers[formId] = setTimeout(save, 500);
        });
        el.addEventListener('change', () => {
          clearTimeout(this._timers[formId]);
          this._timers[formId] = setTimeout(save, 500);
        });
      }
    }
  },
  restore(formId, fieldMap) {
    const data = this.load(formId);
    if (!data) return false;
    for (const [key, elId] of Object.entries(fieldMap)) {
      const el = document.getElementById(elId);
      if (el && data[key] !== undefined) el.value = data[key];
    }
    return true;
  }
};

/* ─── Helpers ─── */
let _escDiv = null;
function escapeHtml(s) { if (s == null) return ''; if (!_escDiv) _escDiv = document.createElement('div'); _escDiv.textContent = s; return _escDiv.innerHTML; }
function escapeAttr(s) { return (s||'').replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/'/g,'&#39;').replace(/</g,'&lt;'); }
function showModal(html, {size, title, onClose} = {}) {
  const triggerEl = document.activeElement;
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');
  const modalTitleId = 'modal-title-' + Date.now();
  if (title) overlay.setAttribute('aria-labelledby', modalTitleId);
  const closeModal = () => {
    overlay.remove();
    if (onClose) onClose();
    if (triggerEl && triggerEl.focus) triggerEl.focus();
  };
  overlay.onclick = e => { if (e.target === overlay) closeModal(); };
  const card = document.createElement('div');
  card.className = 'modal-card' + (size === 'sm' ? ' modal-card-sm' : size === 'lg' ? ' modal-card-lg' : '');
  if (title) html = `<div class="modal-header"><h3 id="${modalTitleId}">${escapeHtml(title)}</h3><button class="modal-close" aria-label="Close dialog">&times;</button></div><div class="modal-body">${html}</div>`;
  card.innerHTML = html;
  // Wire up the close button to use closeModal (restores focus)
  const closeBtn = card.querySelector('.modal-close');
  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  overlay.appendChild(card);
  document.body.appendChild(overlay);
  // Trap focus inside modal
  overlay.addEventListener('keydown', e => {
    if (e.key === 'Escape') { e.preventDefault(); closeModal(); return; }
    if (e.key === 'Tab') {
      const focusable = overlay.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
      if (focusable.length === 0) return;
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (e.shiftKey) { if (document.activeElement === first) { e.preventDefault(); last.focus(); } }
      else { if (document.activeElement === last) { e.preventDefault(); first.focus(); } }
    }
  });
  // Auto-focus first focusable element inside modal
  requestAnimationFrame(() => {
    const focusable = card.querySelector('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
    if (focusable) focusable.focus();
  });
  return overlay;
}
/** Safe fetch wrapper — returns parsed JSON or fallback on error. Usage: const data = await safeFetch('/api/foo', {}, []); */
async function safeFetch(url, opts = {}, fallback = null) {
  try {
    const r = await fetch(url, opts);
    if (!r.ok) { console.warn(`Fetch ${url} failed: ${r.status}`); return fallback; }
    return await r.json();
  } catch(e) { console.warn(`Fetch ${url} error:`, e.message); return fallback; }
}
function copyCode(btn) {
  const code = btn.previousElementSibling.textContent;
  navigator.clipboard.writeText(code).then(() => {
    btn.textContent = 'Copied!'; btn.classList.add('copied');
    setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 2000);
  }).catch(() => { /* clipboard API not available */ });
}
function copyMsg(btn) {
  const msg = btn.closest('.message').dataset.content;
  navigator.clipboard.writeText(msg).then(() => {
    btn.textContent = 'Copied!';
    setTimeout(() => btn.textContent = 'Copy', 2000);
  }).catch(() => { /* clipboard API not available */ });
}
function formatBytes(b) {
  if (b >= 1073741824) return (b/1073741824).toFixed(1)+' GB';
  if (b >= 1048576) return (b/1048576).toFixed(1)+' MB';
  if (b >= 1024) return (b/1024).toFixed(0)+' KB';
  return b+' B';
}

/* ─── Markdown ─── */
function highlightSyntax(code) {
  const tokens = [];
  let tid = 0;
  function stash(html) { const id = '\x01T' + (tid++) + '\x01'; tokens.push({id, html}); return id; }
  // Strings (single/double quoted — escaped HTML entities &#39; and &quot;)
  code = code.replace(/(&#39;(?:[^\\]|\\.)*?&#39;|&quot;(?:[^\\]|\\.)*?&quot;)/g, m =>
      stash('<span class="text-green">' + m + '</span>'));
  // Comments (// and #)
  code = code.replace(/(\/\/.*$|#.*$)/gm, m =>
      stash('<span class="text-muted">' + m + '</span>'));
  // Numbers
  code = code.replace(/\b(\d+\.?\d*)\b/g, m =>
      stash('<span class="text-orange">' + m + '</span>'));
  // Keywords
  code = code.replace(/\b(function|const|let|var|if|else|for|while|return|import|from|class|def|async|await|try|catch|throw|new|this|self|True|False|None|true|false|null|undefined|export|default|switch|case|break|continue|yield|lambda|with|as|in|not|and|or|elif|except|finally|raise|pass|del|print|typeof|instanceof)\b/g, m =>
      stash('<span class="text-accent">' + m + '</span>'));
  tokens.forEach(t => { code = code.split(t.id).join(t.html); });
  return code;
}
function renderMarkdown(text) {
  if (!text) return '';
  let h = escapeHtml(text);
  // Wiki-links: [[Note Title]] → clickable link
  h = h.replace(/\[\[([^\]]+)\]\]/g, (_, title) => {
    const safeTitle = title.replace(/[\\'"&<>]/g, '');
    return '<a href="#" class="wiki-link text-accent-link" data-shell-action="open-wiki-link" data-wiki-title="' + escapeAttr(safeTitle) + '">' + title + '</a>';
  });
  // Extract code blocks first to protect content from other transforms
  const codeBlocks = [];
  h = h.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
    const highlighted = highlightSyntax(code);
    const ph = '\x00CB' + codeBlocks.length + '\x00';
    codeBlocks.push(`<div class="code-wrap"><pre><code>${highlighted}</code></pre><button type="button" class="code-copy-btn" data-shell-action="copy-code">Copy</button></div>`);
    return ph;
  });
  // Extract inline code to protect from other transforms
  const inlineCodes = [];
  h = h.replace(/`([^`]+)`/g, (_, code) => {
    const ph = '\x00IC' + inlineCodes.length + '\x00';
    inlineCodes.push('<code>' + code + '</code>');
    return ph;
  });
  // Tables
  h = h.replace(/((?:\|.+\|\n?)+)/g, (match) => {
    const rows = match.trim().split('\n').filter(r => r.trim());
    if (rows.length < 2) return match;
    const isSep = (r) => /^\|[\s\-:|]+\|$/.test(r.trim());
    let headerEnd = isSep(rows[1]) ? 1 : -1;
    let tableHtml = '<table>';
    rows.forEach((row, i) => {
      if (isSep(row)) return;
      const cells = row.split('|').filter((c, ci, arr) => ci > 0 && ci < arr.length - 1).map(c => c.trim());
      const tag = i < headerEnd ? 'th' : 'td';
      if (i === 0 && headerEnd > 0) tableHtml += '<thead>';
      tableHtml += '<tr>' + cells.map(c => `<${tag}>${c}</${tag}>`).join('') + '</tr>';
      if (i === 0 && headerEnd > 0) tableHtml += '</thead><tbody>';
    });
    if (headerEnd > 0) tableHtml += '</tbody>';
    return tableHtml + '</table>';
  });
  // Horizontal rules
  h = h.replace(/^(---|\*\*\*|___)$/gm, '<hr>');
  // Strikethrough
  h = h.replace(/~~(.+?)~~/g, '<del>$1</del>');
  // Bold
  h = h.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // Italic
  h = h.replace(/\*(.+?)\*/g, '<em>$1</em>');
  // Headers (shifted down for chat bubble context: # -> h3, ## -> h4, ### -> h5)
  h = h.replace(/^### (.+)$/gm, '<h5>$1</h5>');
  h = h.replace(/^## (.+)$/gm, '<h4>$1</h4>');
  h = h.replace(/^# (.+)$/gm, '<h3>$1</h3>');
  // Blockquotes (merge consecutive > lines into one blockquote)
  h = h.replace(/((?:^&gt; .+$\n?)+)/gm, (match) => {
    const lines = match.trim().split('\n').map(l => l.replace(/^&gt; /, '')).join('<br>');
    return '<blockquote>' + lines + '</blockquote>';
  });
  // Unordered list (supports 2-space nested lists)
  h = h.replace(/((?:^(?:  )*[*-] .+$\n?)+)/gm, (match) => {
    const lines = match.trim().split('\n');
    let result = '', depth = 0;
    lines.forEach(l => {
      const level = Math.floor(l.match(/^( *)/)[1].length / 2);
      const content = l.replace(/^ *[*-] /, '');
      while (depth < level) { result += '<ul>'; depth++; }
      while (depth > level) { result += '</li></ul>'; depth--; }
      if (result && depth === level && !result.endsWith('<ul>')) result += '</li>';
      result += '<li>' + content;
    });
    while (depth > 0) { result += '</li></ul>'; depth--; }
    result += '</li>';
    return '<ul>' + result + '</ul>';
  });
  // Ordered list (supports 2-space nested lists)
  h = h.replace(/((?:^(?:  )*\d+\. .+$\n?)+)/gm, (match) => {
    const lines = match.trim().split('\n');
    let result = '', depth = 0;
    lines.forEach(l => {
      const level = Math.floor(l.match(/^( *)/)[1].length / 2);
      const content = l.replace(/^ *\d+\. /, '');
      while (depth < level) { result += '<ol>'; depth++; }
      while (depth > level) { result += '</li></ol>'; depth--; }
      if (result && depth === level && !result.endsWith('<ol>')) result += '</li>';
      result += '<li>' + content;
    });
    while (depth > 0) { result += '</li></ol>'; depth--; }
    result += '</li>';
    return '<ol>' + result + '</ol>';
  });
  // Links
  h = h.replace(/\[(.+?)\]\((.+?)\)/g, (m, text, url) => {
    if (/^javascript:/i.test(url.trim()) || /^data:/i.test(url.trim()) || /^vbscript:/i.test(url.trim())) return text;
    return `<a href="${escapeAttr(url)}">${text}</a>`;
  });
  // Paragraphs
  h = h.replace(/\n\n/g, '</p><p>');
  h = h.replace(/\n/g, '<br>');
  // Restore protected content
  inlineCodes.forEach((code, i) => { h = h.split('\x00IC' + i + '\x00').join(code); });
  codeBlocks.forEach((block, i) => { h = h.split('\x00CB' + i + '\x00').join(block); });
  return '<p>' + h + '</p>';
}

/* ─── Global Keyboard Shortcuts ─── */
document.addEventListener('keydown', e => {
  // Esc — close topmost modal/overlay
  if (e.key === 'Escape') {
    if (closeTopVisibleShellSurface()) {
      e.preventDefault();
      return;
    }
  }
  // Ctrl/Cmd+K — handled by _app_workspaces.js toggleCommandPalette()
});
