/* ─── Situation Room v4 — World Monitor Intelligence Dashboard ─── */

let _sitroomMap = null;
let _sitroomMarkers = { earthquakes: [], weather: [], conflicts: [], aviation: [], volcanoes: [], fires: [], nuclear: [], bases: [], cables: [], datacenters: [], pipelines: [], waterways: [], spaceports: [], shipping: [], ucdp: [], airports: [], fincenters: [], mining: [], techHQs: [], diseases: [], radiation: [], protests: [], ships: [], cloudRegions: [], exchanges: [], commodityHubs: [], startupHubs: [], gpsJamming: [], tradeRoutes: [], accelerators: [], refugees: [], unMissions: [], ixps: [], embassies: [], desalination: [], weatherStations: [], spaceTracking: [], rareEarths: [], tsunamiStations: [], borderCrossings: [], listeningPosts: [], volcanicArcs: [], webcams: [] };
let _sitroomRadarLayer = null; // RainViewer radar tile layer state
let _sitroomNewsOffset = 0;
const SITROOM_NEWS_PAGE = 50;
let _sitroomAutoTimer = null;
let _sitroomClockTimer = null;
let _sitroomWorldClockTimer = null;
let _sitroomRefreshPollTimer = null;
let _sitroomIsGlobe = false;
let _sitroomAlertsSeen = new Set();
let _sitroomInitDone = false;
let _sitroomNewsCat = ''; // preserve category across refreshes
let _sitroomView = 'topline';
let _sitroomNewsGroup = 'all';
let _sitroomLayoutEdit = false;
let _sitroomRegionPreset = 'global';
let _sitroomNewsArticles = [];
let _sitroomDeskPreset = 'executive';
let _sitroomLayerPreset = 'crisis';
let _sitroomSavedDeskId = '';
let _sitroomBriefMode = 'morning';
let _sitroomSnapshotTemplate = 'morning';

const SITROOM_VIEW_META = {
  topline: {
    copy: 'Critical signals, narrative shifts, and decision support in one live surface.',
    mapTitle: 'Track live pressure points, infrastructure risk, and narrative shifts in one canvas.',
    mapCopy: 'Start with the map for orientation, then drop into the intelligence cards below for depth, analyst output, and follow-up action.',
  },
  news: {
    copy: 'Work the information picture by desk instead of scanning a warehouse of unrelated cards.',
    mapTitle: 'Use the map for orientation, then work the news desk by lane.',
    mapCopy: 'Topline stories, topic feeds, and drill-down reporting are grouped so you can follow a narrative instead of hunting through the whole grid.',
  },
  markets: {
    copy: 'Keep macro stress, flows, regime, and business signals in one operator view.',
    mapTitle: 'Watch market risk against the same global operating picture.',
    mapCopy: 'Use the map for context, then stay focused on price action, calendars, flows, and structural stress.',
  },
  security: {
    copy: 'Focus on conflict, cyber, disruption, escalation, and intelligence quality without the rest of the noise.',
    mapTitle: 'Track pressure points, adversary signals, and disruption risk in one security surface.',
    mapCopy: 'Keep the global picture visible, but prioritize conflict, cyber, infrastructure, and warning indicators.',
  },
  map: {
    copy: 'Operate from the map first, then pull only the supporting panels you need.',
    mapTitle: 'Use the map as the primary command canvas.',
    mapCopy: 'Layer presets, hotspot monitoring, and country drill-down stay in focus while the card field trims down to map-relevant support.',
  },
};

const SITROOM_TOPLINE_PANELS = new Set([
  'sitroom-news-list',
  'sr-live-player',
  'sr-cii',
  'sitroom-timeline',
  'sitroom-correlations',
  'sitroom-breaking-detection',
  'sitroom-briefing-content',
  'sitroom-deduction',
  'sitroom-country-brief-content',
  'sitroom-snapshot',
  'sitroom-anomalies',
  'sitroom-enhanced-signals',
  'sitroom-source-health',
  'sitroom-alert-history',
  'sitroom-outages-list',
]);

const SITROOM_MAP_PANELS = new Set([
  'sitroom-quake-list',
  'sitroom-weather-list',
  'sitroom-fires-list',
  'sitroom-diseases-list',
  'sitroom-radiation',
  'sitroom-outages-list',
  'sr-cii',
  'sitroom-country-brief-content',
  'sitroom-space-weather',
  'sitroom-ucdp',
]);

const SITROOM_MARKETS_KEYWORDS = [
  'market', 'fear-greed', 'predictions', 'yield', 'macro', 'forex', 'crypto', 'stablecoins',
  'bigmac', 'btc-etf', 'fintech', 'earnings', 'central-banks', 'cb-calendar', 'ipo',
  'derivatives', 'hedgefunds', 'unicorn', 'gulf', 'commodities', 'debt', 'fin-regulation',
  'fuel', 'velocity',
];

const SITROOM_SECURITY_KEYWORDS = [
  'intel', 'osint', 'cyber', 'sec-advisories', 'source-health', 'cable-health', 'chokepoints',
  'escalation', 'oref', 'apt', 'anomalies', 'enhanced-signals', 'radiation', 'ucdp', 'protests',
  'sanctions', 'outages', 'internet-health', 'country-brief', 'briefing', 'deduction',
  'displacement', 'humanitarian',
];

const SITROOM_TECH_KEYWORDS = [
  'github', 'arxiv', 'semiconductors', 'space-news', 'cloud-infra', 'dev-community',
  'startups', 'ai-regulation', 'rd-signal', 'tech-events', 'renewable', 'producthunt',
];

const SITROOM_POSITIVE_KEYWORDS = [
  'good-news', 'conservation', 'progress', 'breakthroughs', 'species-tracker',
  'todays-hero', 'good-things', 'live-counters',
];

const SITROOM_WORLD_KEYWORDS = [
  'news-list', 'timeline', 'think-tanks', 'layoffs', 'airline', 'supplychain', 'world-clock',
  'intel-gap', 'news-clusters', 'country-brief',
];

const SITROOM_REGION_PRESETS = {
  global: {
    label: 'Global',
    title: 'Global watchfloor',
    copy: 'Scan the widest signal mix first, then pin the story or country that deserves a longer read.',
    keywords: [],
  },
  americas: {
    label: 'Americas',
    title: 'Americas desk',
    copy: 'Track North and South American political, weather, infrastructure, and market spillover without the rest of the globe crowding the lane.',
    keywords: ['united states', 'u.s.', 'usa', 'canada', 'mexico', 'brazil', 'argentina', 'colombia', 'chile', 'peru', 'venezuela', 'latin america', 'caribbean', 'americas'],
  },
  europe: {
    label: 'Europe',
    title: 'Europe desk',
    copy: 'Keep Europe, Russia, and adjacent pressure points in one reading lane so escalation and market shifts connect faster.',
    keywords: ['europe', 'uk', 'united kingdom', 'britain', 'france', 'germany', 'poland', 'italy', 'spain', 'ukraine', 'russia', 'eu', 'nato', 'baltic'],
  },
  mena: {
    label: 'Middle East',
    title: 'Middle East desk',
    copy: 'Prioritize the Eastern Mediterranean, Gulf, Levant, and Red Sea storylines where escalation and infrastructure risk move together.',
    keywords: ['middle east', 'mena', 'israel', 'gaza', 'west bank', 'iran', 'iraq', 'syria', 'lebanon', 'saudi', 'uae', 'qatar', 'oman', 'yemen', 'jordan', 'egypt', 'turkey', 'red sea', 'gulf'],
  },
  'indo-pacific': {
    label: 'Indo-Pacific',
    title: 'Indo-Pacific desk',
    copy: 'Keep Asia-Pacific security, logistics, semiconductor, and maritime stories together so the regional operating picture stays coherent.',
    keywords: ['asia-pacific', 'indo-pacific', 'china', 'taiwan', 'japan', 'korea', 'south korea', 'north korea', 'india', 'pakistan', 'philippines', 'australia', 'indonesia', 'malaysia', 'vietnam', 'south china sea'],
  },
};

const SITROOM_BRIEF_MODE_META = {
  morning: {
    label: 'Morning Brief',
    copy: 'Morning Brief keeps the desk broad and helps you establish the operating picture before you narrow down.',
    keywords: ['breaking', 'weather', 'conflict', 'market', 'election', 'outage', 'summit', 'policy', 'quake', 'storm'],
  },
  crisis: {
    label: 'Crisis Brief',
    copy: 'Crisis Brief pushes escalation, disruption, and safety-critical reporting to the top so you can assess what needs attention fastest.',
    keywords: ['conflict', 'strike', 'attack', 'evacuation', 'storm', 'quake', 'wildfire', 'outage', 'cyber', 'protest', 'military', 'missile', 'sanction', 'explosion', 'emergency', 'warning'],
  },
  'market-open': {
    label: 'Market Open',
    copy: 'Market Open surfaces macro, policy, rates, oil, and business pressure so you can get a cleaner risk picture before the session moves.',
    keywords: ['market', 'fed', 'rates', 'inflation', 'treasury', 'oil', 'futures', 'earnings', 'currency', 'bond', 'jobs', 'cpi', 'pmi', 'growth', 'tariff', 'export'],
  },
};

const SITROOM_SNAPSHOT_TEMPLATES = {
  morning: {
    label: 'AM Brief',
    title: 'Situation Room AM Brief',
  },
  handoff: {
    label: 'Crisis Handoff',
    title: 'Situation Room Crisis Handoff',
  },
  market: {
    label: 'Market Note',
    title: 'Situation Room Market Note',
  },
};

const SITROOM_LAYER_PRESETS = {
  crisis: ['earthquakes', 'weather', 'conflicts', 'fires', 'volcanoes', 'ucdp', 'diseases', 'radiation', 'protests', 'daynight'],
  infrastructure: ['nuclear', 'bases', 'cables', 'datacenters', 'pipelines', 'airports', 'cloudRegions', 'ixps', 'weatherStations', 'spaceTracking'],
  markets: ['fincenters', 'exchanges', 'commodityHubs', 'shipping', 'tradeRoutes', 'airports', 'mining', 'rareEarths'],
  mobility: ['aviation', 'ships', 'shipping', 'waterways', 'tradeRoutes', 'borderCrossings', 'airports', 'weather', 'radar'],
  comms: ['cables', 'datacenters', 'ixps', 'cloudRegions', 'listeningPosts', 'techHQs', 'spaceTracking', 'gpsJamming', 'webcams'],
};

const SITROOM_DESK_PRESETS = {
  executive: {
    view: 'topline',
    newsGroup: 'all',
    region: 'global',
    layerPreset: 'crisis',
    briefMode: 'morning',
  },
  crisis: {
    view: 'security',
    newsGroup: 'security',
    region: 'global',
    layerPreset: 'crisis',
    briefMode: 'crisis',
  },
  markets: {
    view: 'markets',
    newsGroup: 'markets',
    region: 'global',
    layerPreset: 'markets',
    briefMode: 'market-open',
  },
  cyber: {
    view: 'security',
    newsGroup: 'security',
    region: 'global',
    layerPreset: 'comms',
    briefMode: 'crisis',
  },
  'middle-east': {
    view: 'news',
    newsGroup: 'security',
    region: 'mena',
    layerPreset: 'mobility',
    briefMode: 'crisis',
  },
};

const SITROOM_VIEW_LABELS = {
  topline: 'Topline',
  news: 'News Desk',
  markets: 'Markets',
  security: 'Security',
  map: 'Map',
};

function _titleCaseSitroomLabel(value) {
  return String(value || '')
    .split('-')
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function _getSitroomViewLabel(view = _sitroomView) {
  return SITROOM_VIEW_LABELS[view] || 'Topline';
}

function _getSitroomDeskLabel(name = _sitroomDeskPreset) {
  return name === 'custom' ? 'Custom Desk' : `${_titleCaseSitroomLabel(name)} Desk`;
}

function _getSitroomLayerLabel(name = _sitroomLayerPreset) {
  return name === 'custom' ? 'Custom Layers' : `${_titleCaseSitroomLabel(name)} Layers`;
}

function _getSitroomDefaultSnapshotTemplate(mode = _sitroomBriefMode) {
  if (mode === 'crisis') return 'handoff';
  if (mode === 'market-open') return 'market';
  return 'morning';
}

function _formatSitroomSavedTime(value) {
  if (!value) return '';
  try {
    return new Date(value).toLocaleString([], {month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'});
  } catch (e) {
    return '';
  }
}

function _getActiveSitroomLayerLabels() {
  return [...document.querySelectorAll('[data-sitroom-layer]')]
    .filter(cb => cb.checked)
    .map(cb => cb.closest('label')?.textContent?.replace(/\s+/g, ' ').trim() || cb.dataset.sitroomLayer)
    .filter(Boolean);
}

function _getSitroomSnapshotContext() {
  const saved = _getSitroomSavedDeskById(_sitroomSavedDeskId);
  const preset = SITROOM_REGION_PRESETS[_sitroomRegionPreset] || SITROOM_REGION_PRESETS.global;
  const brief = SITROOM_BRIEF_MODE_META[_sitroomBriefMode] || SITROOM_BRIEF_MODE_META.morning;
  const template = SITROOM_SNAPSHOT_TEMPLATES[_sitroomSnapshotTemplate] || SITROOM_SNAPSHOT_TEMPLATES.morning;
  const deskName = saved?.name || _getSitroomDeskLabel();
  const headlineLines = (_sitroomNewsArticles || []).slice(0, 5).map((article, index) => {
    const source = article.source_name ? ` (${article.source_name})` : '';
    return `${index + 1}. ${article.title || 'Untitled'}${source}`;
  });
  const layerLines = _getActiveSitroomLayerLabels().slice(0, 10);
  const updateText = document.getElementById('sitroom-last-update')?.textContent?.trim() || 'Update time unavailable';
  const threat = document.getElementById('sitroom-threat-level')?.textContent?.trim() || 'Unknown';
  const online = document.getElementById('sitroom-online-badge')?.textContent?.trim() || 'Unknown';
  return {saved, preset, brief, template, deskName, headlineLines, layerLines, updateText, threat, online};
}

function _buildSitroomDeskSnapshot() {
  const {saved, preset, brief, template, deskName, headlineLines, layerLines, updateText, threat, online} = _getSitroomSnapshotContext();
  const header = [
    `${template.title}`,
    `Desk: ${deskName}${saved?.isDefault ? ' (Launch Desk)' : ''}`,
    `View: ${_getSitroomViewLabel()} · ${preset.label}`,
    `News Lane: ${_getSitroomNewsGroupLabel()} · ${brief.label}`,
    `Layers: ${_getSitroomLayerLabel()}`,
    `Threat: ${threat} · Status: ${online}`,
    `Updated: ${updateText}`,
    '',
  ];

  if (_sitroomSnapshotTemplate === 'handoff') {
    return [
      ...header,
      `Immediate Focus:`,
      ...(headlineLines.length ? headlineLines.slice(0, 3) : ['No immediate headlines currently loaded.']),
      '',
      `Next Operator Needs To Watch:`,
      `- Keep ${_getSitroomNewsGroupLabel().toLowerCase()} in focus for ${preset.label}.`,
      `- Maintain ${_getSitroomLayerLabel().toLowerCase()} on the map while validating new alerts.`,
      `- Recheck the desk after the next refresh cycle if threat or status changes.`,
      '',
      `Active Layers:`,
      ...(layerLines.length ? layerLines.map(item => `- ${item}`) : ['- No active layers recorded.']),
    ].join('\n');
  }

  if (_sitroomSnapshotTemplate === 'market') {
    return [
      ...header,
      `Market Drivers:`,
      ...(headlineLines.length ? headlineLines : ['No market headlines currently loaded.']),
      '',
      `Desk Posture:`,
      `- Region focus: ${preset.label}`,
      `- Primary lane: ${_getSitroomNewsGroupLabel()}`,
      `- Map stance: ${_getSitroomLayerLabel()}`,
      '',
      `Active Layers:`,
      ...(layerLines.length ? layerLines.map(item => `- ${item}`) : ['- No active layers recorded.']),
    ].join('\n');
  }

  return [
    ...header,
    `Top Headlines:`,
    ...(headlineLines.length ? headlineLines : ['No headlines currently loaded.']),
    '',
    `Watch Items:`,
    `- Region focus: ${preset.label}`,
    `- News lane: ${_getSitroomNewsGroupLabel()}`,
    `- Map stance: ${_getSitroomLayerLabel()}`,
    '',
    `Active Layers:`,
    ...(layerLines.length ? layerLines.map(item => `- ${item}`) : ['- No active layers recorded.']),
  ].join('\n');
}

function _buildSitroomDeskSnapshotMarkdown() {
  const {saved, preset, brief, template, deskName, headlineLines, layerLines, updateText, threat, online} = _getSitroomSnapshotContext();
  const lines = [
    `# ${template.title}`,
    ``,
    `- **Desk:** ${deskName}${saved?.isDefault ? ' (Launch Desk)' : ''}`,
    `- **View:** ${_getSitroomViewLabel()} · ${preset.label}`,
    `- **News Lane:** ${_getSitroomNewsGroupLabel()} · ${brief.label}`,
    `- **Layers:** ${_getSitroomLayerLabel()}`,
    `- **Threat:** ${threat}`,
    `- **Status:** ${online}`,
    `- **Updated:** ${updateText}`,
    ``,
  ];

  if (_sitroomSnapshotTemplate === 'handoff') {
    lines.push(`## Immediate Focus`);
    lines.push(...(headlineLines.length ? headlineLines.map(item => item.replace(/^\d+\.\s*/, '- ')) : ['- No immediate headlines currently loaded.']));
    lines.push(``);
    lines.push(`## Next Operator Needs To Watch`);
    lines.push(`- Keep ${_getSitroomNewsGroupLabel().toLowerCase()} in focus for ${preset.label}.`);
    lines.push(`- Maintain ${_getSitroomLayerLabel().toLowerCase()} on the map while validating new alerts.`);
    lines.push(`- Recheck the desk after the next refresh cycle if threat or status changes.`);
  } else if (_sitroomSnapshotTemplate === 'market') {
    lines.push(`## Market Drivers`);
    lines.push(...(headlineLines.length ? headlineLines.map(item => item.replace(/^\d+\.\s*/, '- ')) : ['- No market headlines currently loaded.']));
    lines.push(``);
    lines.push(`## Desk Posture`);
    lines.push(`- Region focus: ${preset.label}`);
    lines.push(`- Primary lane: ${_getSitroomNewsGroupLabel()}`);
    lines.push(`- Map stance: ${_getSitroomLayerLabel()}`);
  } else {
    lines.push(`## Top Headlines`);
    lines.push(...(headlineLines.length ? headlineLines.map(item => item.replace(/^\d+\.\s*/, '- ')) : ['- No headlines currently loaded.']));
    lines.push(``);
    lines.push(`## Watch Items`);
    lines.push(`- Region focus: ${preset.label}`);
    lines.push(`- News lane: ${_getSitroomNewsGroupLabel()}`);
    lines.push(`- Map stance: ${_getSitroomLayerLabel()}`);
  }

  lines.push(``);
  lines.push(`## Active Layers`);
  lines.push(...(layerLines.length ? layerLines.map(item => `- ${item}`) : ['- No active layers recorded.']));
  return lines.join('\n');
}

async function _copySitroomDeskSnapshot() {
  const text = _buildSitroomDeskSnapshot();
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      toast('Desk snapshot copied', 'success');
      return;
    }
  } catch (e) { /* clipboard blocked */ }

  try {
    const blob = new Blob([text], {type: 'text/plain;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `sitroom-desk-snapshot-${Date.now()}.txt`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    toast('Desk snapshot downloaded', 'info');
  } catch (e) {
    _showSitroomAlert('warning', 'Unable to share desk snapshot on this device');
  }
}

async function _saveSitroomDeskSnapshotToNotes() {
  const {template, deskName} = _getSitroomSnapshotContext();
  const now = new Date();
  const stamp = now.toLocaleString([], {month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'});
  const title = `${template.label} · ${deskName} · ${stamp}`;
  const content = _buildSitroomDeskSnapshotMarkdown();
  try {
    const note = await safeFetch('/api/notes', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({title, content}),
    }, null);
    if (!note?.id) { toast('Failed to save desk note', 'error'); return; }
    if (typeof loadNotes === 'function') await loadNotes();
    const tab = document.querySelector('[data-tab="notes"]');
    if (tab) tab.click();
    setTimeout(() => { if (typeof selectNote === 'function') selectNote(note.id); }, 250);
    toast('Desk note created', 'success');
  } catch (e) {
    toast('Failed to save desk note', 'error');
  }
}

async function _sendSitroomDeskSnapshotToLan() {
  const {template, deskName} = _getSitroomSnapshotContext();
  const sender = document.getElementById('lan-chat-name')?.value.trim() || 'Situation Room';
  const content = `${template.title}\nDesk: ${deskName}\n\n${_buildSitroomDeskSnapshot()}`;
  try {
    const msg = await safeFetch('/api/lan/messages', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({sender, content, msg_type: 'sitroom_snapshot'}),
    }, null);
    if (!msg?.id) { toast('Failed to send to LAN', 'error'); return; }
    toast('Desk snapshot sent to LAN', 'success');
    if (typeof loadLanMessages === 'function') loadLanMessages();
  } catch (e) {
    toast('Failed to send to LAN', 'error');
  }
}

/* ─── Init ─── */
function initSituationRoom() {
  _setSitroomShellState(true);
  _closeSitroomOverlays();
  setTimeout(_closeSitroomOverlays, 500);
  _decorateSitroomPanels();
  _restoreSitroomWorkspaceState();
  _applySitroomDefaultDeskOnOpen();
  _applySitroomWorkspaceState();

  if (_sitroomInitDone) {
    _sitroomRefreshPanels();
    _applySitroomWorkspaceState();
    setTimeout(_sitroomResizeMap, 100);
    return;
  }
  _sitroomInitDone = true;
  _sitroomRefreshPanels();
  _restoreLayerState();
  _applySitroomDefaultDeskOnOpen();
  _applySitroomWorkspaceState();
  initSitroomMap();
  _initSitroomMapResize();
  _initSitroomClock();
  _initSitroomWorldClock();
  _initSitroomSearch();
  _initRefreshBar();
  _initPanelDragReorder();
  _restorePanelOrder();
  _sitroomAutoRefreshIfEmpty();
  _initSmartPollLoop();
  _initAnalysisWorker();
  _initSitroomIDB();
  _initCardResize();
}

function _isSitroomActive() {
  if (window.NomadShellRuntime?.isTabActive?.('situation-room')) return true;
  if (window.NOMAD_ACTIVE_TAB) return window.NOMAD_ACTIVE_TAB === 'situation-room';
  return document.getElementById('tab-situation-room')?.classList.contains('active') || false;
}

// Cleanup intervals on tab leave to prevent memory leaks
if (!window._nomadTabLeaveCallbacks) window._nomadTabLeaveCallbacks = {};
window._nomadTabLeaveCallbacks['situation-room'] = function() {
  if (_sitroomAutoTimer) { clearInterval(_sitroomAutoTimer); _sitroomAutoTimer = null; }
  if (_sitroomClockTimer) { clearInterval(_sitroomClockTimer); _sitroomClockTimer = null; }
  if (_sitroomWorldClockTimer) { clearInterval(_sitroomWorldClockTimer); _sitroomWorldClockTimer = null; }
  if (_sitroomRefreshPollTimer) { clearInterval(_sitroomRefreshPollTimer); _sitroomRefreshPollTimer = null; }
  window.NomadShellRuntime?.stopInterval('sitroom.smart-poll');
  window.NomadShellRuntime?.stopInterval('sitroom.utc-clock');
  window.NomadShellRuntime?.stopInterval('sitroom.world-clock');
  window.NomadShellRuntime?.stopInterval('sitroom.refresh-status');
  if (_sitroomResizeMap) window.removeEventListener('resize', _sitroomResizeMap);
};

function _sitroomRefreshPanels() {
  loadSitroomSummary();
  loadSitroomNews();
  loadSitroomFeeds();
  loadSitroomIntelFeed();
  loadSitroomCII();
  renderSitroomBreakingNews();
  loadSitroomFires();
  loadSitroomDiseases();
  loadSitroomOutages();
  loadSitroomRadiation();
  loadSitroomTrending();
  loadSitroomSanctions();
  loadSitroomDisplacement();
  loadSitroomTimeline();
  loadSitroomUcdp();
  loadSitroomCyber();
  loadSitroomThinkTanks();
  loadSitroomOsint();
  loadSitroomMonitors();
  loadSitroomEconCal();
  loadSitroomDebt();
  loadSitroomCorrelations();
  loadSitroomYieldCurve();
  loadSitroomStablecoins();
  loadSitroomVelocity();
  loadSitroomServiceStatus();
  loadSitroomBigMac();
  loadSitroomRenewable();
  loadSitroomGithub();
  loadSitroomFuel();
  loadSitroomProductHunt();
  loadSitroomEarnings();
  loadSitroomCentralBanks();
  loadSitroomArxiv();
  loadSitroomSecAdvisories();
  _loadCategoryCard('sitroom-semiconductors', 'Semiconductors');
  _loadCategoryCard('sitroom-space-news', 'Space');
  _loadCategoryCard('sitroom-maritime-news', 'Maritime');
  _loadCategoryCard('sitroom-nuclear-news', 'Nuclear');
  _loadCategoryCard('sitroom-startups', 'Startups');
  _loadCategoryCard('sitroom-good-news', 'Good News');
  _loadCategoryCard('sitroom-conservation', 'Conservation');
  _loadCategoryCard('sitroom-cloud-infra', 'Cloud');
  _loadCategoryCard('sitroom-dev-community', 'Developer');
  _loadKeywordCard('sitroom-ai-regulation', '/api/sitroom/ai-regulation', 'articles');
  _loadKeywordCard('sitroom-rd-signal', '/api/sitroom/rd-signal', 'articles');
  _loadKeywordCard('sitroom-chokepoints', '/api/sitroom/chokepoints', 'articles');
  _loadKeywordCard('sitroom-fin-regulation', '/api/sitroom/fin-regulation', 'articles');
  _loadKeywordCard('sitroom-ipo', '/api/sitroom/keyword-search/ipo|spac|listing|public offering', 'articles');
  _loadKeywordCard('sitroom-derivatives', '/api/sitroom/keyword-search/options|futures|derivatives|swap|hedge', 'articles');
  _loadKeywordCard('sitroom-hedgefunds', '/api/sitroom/keyword-search/hedge fund|private equity|venture capital|buyout|acquisition', 'articles');
  _loadKeywordCard('sitroom-progress', '/api/sitroom/keyword-search/progress|milestone|achievement|record|breakthrough', 'articles');
  _loadKeywordCard('sitroom-breakthroughs', '/api/sitroom/keyword-search/breakthrough|discovery|innovation|cure|first ever', 'articles');
  _loadKeywordCard('sitroom-tech-events', '/api/sitroom/keyword-search/conference|summit|expo|keynote|launch event|developer conference', 'articles');
  _loadKeywordCard('sitroom-escalation', '/api/sitroom/keyword-search/escalation|mobilization|nuclear threat|missile launch|invasion|troops deployed', 'articles');
  _loadKeywordCard('sitroom-btc-etf', '/api/sitroom/keyword-search/bitcoin etf|btc etf|crypto etf|spot etf|etf flow', 'articles');
  _loadKeywordCard('sitroom-fintech', '/api/sitroom/keyword-search/fintech|neobank|digital bank|payment|stripe|square|paypal', 'articles');
  _loadKeywordCard('sitroom-internet-health', '/api/sitroom/keyword-search/internet outage|dns|bgp|cdn|ddos|cloudflare|bandwidth', 'articles');
  loadSitroomPopExposure();
  loadSitroomMarketBriefInit();
  _loadKeywordCard('sitroom-unicorns', '/api/sitroom/keyword-search/unicorn|valuation|billion|funding round|series', 'articles');
  _loadKeywordCard('sitroom-gulf', '/api/sitroom/keyword-search/opec|saudi|uae|qatar|bahrain|kuwait|gcc|aramco', 'articles');
  _loadCategoryCard('sitroom-commodities-news', 'Commodities');
  _loadKeywordCard('sitroom-market-analysis', '/api/sitroom/keyword-search/market analysis|outlook|forecast|rally|correction|bear|bull', 'articles');
  _loadKeywordCard('sitroom-protests', '/api/sitroom/keyword-search/protest|demonstration|riot|unrest|strike|uprising|march', 'articles');
  loadSitroomLayoffs();
  loadSitroomAirline();
  loadSitroomSupplyChain();
  loadSitroomMacroStress();
  loadSitroomForex();
  loadSitroomCryptoSectors();
  loadSitroomSentiment();
  loadSitroomIntelGap();
  loadSitroomHumanitarian();
  loadSitroomOrefAlerts();
  loadSitroomGdeltFull();
  loadSitroomCot();
  loadSitroomBreakingDetection();
  loadSitroomNewsClusters();
  loadSitroomSourceHealth();
  loadSitroomCableHealth();
  loadSitroomAnomalies();
  loadSitroomAlertHistory();
  loadSitroomEnhancedSignals();
  loadSitroomGulfEcon();
  loadSitroomMarketRegime();
  loadSitroomLiveCounters();
  loadSitroomSpecies();
  loadSitroomAptGroups();
  loadSitroomSnapshot();
  loadSitroomTechReadiness();
  loadSitroomTodaysHero();
  loadSitroomGoodThings();
  loadSitroomCbCalendar();
  _checkCriticalAlerts();
  _updateDataFreshness();
  _checkQuakeAlerts();
  loadSitroomLiveChannels();
}

async function _sitroomAutoRefreshIfEmpty() {
  const d = await safeFetch('/api/sitroom/status', {}, null);
  if (d && d.feed_count > 0 && (!d.last_fetch || Object.keys(d.last_fetch).length === 0)) {
    refreshSitroomFeeds();
  }
}

function _setSitroomShellState(active) {
  document.body.classList.toggle('situation-room-active', active);
  const tab = document.getElementById('tab-situation-room');
  const container = tab?.closest('.container');
  const main = tab?.closest('.main-content');
  if (container) container.classList.toggle('container-situation-room', active);
  if (main) main.classList.toggle('situation-room-main', active);
}

/* ─── Close Overlays / Copilot Dock ─── */
function _closeSitroomOverlays() {
  ['lan-chat-panel', 'timer-panel', 'quick-actions-menu'].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.classList.add('is-hidden'); el.hidden = true; }
  });
  if (typeof stopLanMessagePolling === 'function') stopLanMessagePolling();
  if (typeof stopLanPresencePolling === 'function') stopLanPresencePolling();
  if (typeof stopTimerPolling === 'function') stopTimerPolling();
  if (typeof setUtilityDockButtonExpanded === 'function') {
    setUtilityDockButtonExpanded('chat', false);
    setUtilityDockButtonExpanded('timer', false);
    setUtilityDockButtonExpanded('actions', false);
  }
  if (typeof _lanChatOpen !== 'undefined') _lanChatOpen = false;
  if (typeof _timerPanelOpen !== 'undefined') _timerPanelOpen = false;
  if (typeof _qaOpen !== 'undefined') _qaOpen = false;
  const dock = document.getElementById('copilot-dock');
  if (dock) dock.style.display = 'none';
}

function _restoreCopilotDock() {
  _setSitroomShellState(false);
  const dock = document.getElementById('copilot-dock');
  if (dock) dock.style.removeProperty('display');
  ['lan-chat-panel', 'timer-panel', 'quick-actions-menu'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.hidden = false;
  });
}

function _slugSitroomPanelId(text) {
  return String(text || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48);
}

function _getSitroomPanelId(card) {
  if (!card) return '';
  if (card.dataset.panelId) return card.dataset.panelId;
  const panelBody = card.querySelector('.sr-card-body[id], .sr-live-player[id]');
  const panelId = panelBody?.id || `sr-panel-${_slugSitroomPanelId(card.querySelector('.sr-card-head')?.textContent || '')}`;
  card.dataset.panelId = panelId;
  return panelId;
}

function _sitroomPanelHasKeyword(panelId, keywords) {
  return keywords.some(keyword => panelId.includes(keyword));
}

function _getSitroomPanelMeta(panelId) {
  const views = new Set();
  let newsGroup = '';

  if (SITROOM_TOPLINE_PANELS.has(panelId)) views.add('topline');
  if (SITROOM_MAP_PANELS.has(panelId)) views.add('map');

  const isMarkets = _sitroomPanelHasKeyword(panelId, SITROOM_MARKETS_KEYWORDS);
  const isSecurity = _sitroomPanelHasKeyword(panelId, SITROOM_SECURITY_KEYWORDS);
  const isTech = _sitroomPanelHasKeyword(panelId, SITROOM_TECH_KEYWORDS);
  const isPositive = _sitroomPanelHasKeyword(panelId, SITROOM_POSITIVE_KEYWORDS);
  const isWorld = _sitroomPanelHasKeyword(panelId, SITROOM_WORLD_KEYWORDS);
  const isNews = isWorld || isSecurity || isMarkets || isTech || isPositive;

  if (isNews) views.add('news');
  if (isMarkets) views.add('markets');
  if (isSecurity) views.add('security');

  if (!views.size) views.add('news');

  if (isPositive) newsGroup = 'positive';
  else if (isTech) newsGroup = 'tech';
  else if (isMarkets) newsGroup = 'markets';
  else if (isSecurity) newsGroup = 'security';
  else newsGroup = 'world';

  return {views: [...views], newsGroup};
}

function _decorateSitroomPanels() {
  document.querySelectorAll('#sr-cards-anchor .sr-card').forEach(card => {
    const panelId = _getSitroomPanelId(card);
    const meta = _getSitroomPanelMeta(panelId);
    card.dataset.srViews = meta.views.join(' ');
    if (meta.newsGroup) card.dataset.newsGroup = meta.newsGroup;
  });
}

function _saveSitroomWorkspaceState() {
  try {
    localStorage.setItem('sr-workspace-state', JSON.stringify({
      view: _sitroomView,
      newsGroup: _sitroomNewsGroup,
      regionPreset: _sitroomRegionPreset,
      deskPreset: _sitroomDeskPreset,
      layerPreset: _sitroomLayerPreset,
      savedDeskId: _sitroomSavedDeskId,
      briefMode: _sitroomBriefMode,
      snapshotTemplate: _sitroomSnapshotTemplate,
    }));
  } catch (e) { /* localStorage unavailable */ }
  if (typeof syncWorkspaceUrlState === 'function') syncWorkspaceUrlState();
}

function _readSitroomStorageJson(key, fallback) {
  if (typeof readJsonStorage === 'function') {
    return readJsonStorage(localStorage, key, fallback);
  }
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw);
  } catch (e) {
    try { localStorage.removeItem(key); } catch (_) {}
    return fallback;
  }
}

function _readSitroomStorageObject(key, fallback = {}) {
  const parsed = _readSitroomStorageJson(key, fallback);
  if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) return parsed;
  return fallback && typeof fallback === 'object' && !Array.isArray(fallback) ? { ...fallback } : {};
}

function _parseSitroomDetailJson(value) {
  const parsed = typeof safeJsonParse === 'function'
    ? safeJsonParse(value, {})
    : (() => {
        try { return value ? JSON.parse(value) : {}; } catch (_) { return {}; }
      })();
  return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
}

function _restoreSitroomWorkspaceState() {
  const saved = _readSitroomStorageJson('sr-workspace-state', null);
  if (!saved) return;
  if (saved.view && SITROOM_VIEW_META[saved.view]) _sitroomView = saved.view;
  if (saved.newsGroup) _sitroomNewsGroup = saved.newsGroup;
  if (saved.regionPreset && SITROOM_REGION_PRESETS[saved.regionPreset]) _sitroomRegionPreset = saved.regionPreset;
  if (saved.deskPreset && (SITROOM_DESK_PRESETS[saved.deskPreset] || saved.deskPreset === 'custom')) _sitroomDeskPreset = saved.deskPreset;
  if (saved.layerPreset && (SITROOM_LAYER_PRESETS[saved.layerPreset] || saved.layerPreset === 'custom')) _sitroomLayerPreset = saved.layerPreset;
  if (saved.savedDeskId) _sitroomSavedDeskId = saved.savedDeskId;
  if (saved.briefMode && SITROOM_BRIEF_MODE_META[saved.briefMode]) _sitroomBriefMode = saved.briefMode;
  if (saved.snapshotTemplate && SITROOM_SNAPSHOT_TEMPLATES[saved.snapshotTemplate]) _sitroomSnapshotTemplate = saved.snapshotTemplate;
}

function _syncSitroomLayoutEditState() {
  const tab = document.getElementById('tab-situation-room');
  if (tab) tab.dataset.layoutEditing = _sitroomLayoutEdit ? 'true' : 'false';
  const btn = document.getElementById('sr-layout-edit-btn');
  if (btn) {
    btn.classList.toggle('active', _sitroomLayoutEdit);
    btn.setAttribute('aria-pressed', _sitroomLayoutEdit ? 'true' : 'false');
    btn.textContent = _sitroomLayoutEdit ? 'DONE LAYOUT' : 'EDIT LAYOUT';
  }
  const note = document.getElementById('sr-layout-note');
  if (note) note.hidden = !_sitroomLayoutEdit;
  document.querySelectorAll('#sr-cards-anchor .sr-card').forEach(card => {
    card.setAttribute('draggable', _sitroomLayoutEdit ? 'true' : 'false');
  });
}

function _applySitroomWorkspaceState() {
  const tab = document.getElementById('tab-situation-room');
  if (tab) tab.dataset.srView = _sitroomView;

  document.querySelectorAll('[data-sitroom-view]').forEach(btn => {
    const active = btn.dataset.sitroomView === _sitroomView;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-pressed', active ? 'true' : 'false');
  });

  document.querySelectorAll('[data-sitroom-news-group]').forEach(btn => {
    const active = btn.dataset.sitroomNewsGroup === _sitroomNewsGroup;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-pressed', active ? 'true' : 'false');
  });

  document.querySelectorAll('[data-sitroom-region]').forEach(btn => {
    const active = btn.dataset.sitroomRegion === _sitroomRegionPreset;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-pressed', active ? 'true' : 'false');
  });

  document.querySelectorAll('[data-sitroom-desk]').forEach(btn => {
    const active = btn.dataset.sitroomDesk === _sitroomDeskPreset;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-pressed', active ? 'true' : 'false');
  });

  document.querySelectorAll('[data-sitroom-layer-preset]').forEach(btn => {
    const active = btn.dataset.sitroomLayerPreset === _sitroomLayerPreset;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-pressed', active ? 'true' : 'false');
  });

  document.querySelectorAll('[data-sitroom-brief-mode]').forEach(btn => {
    const active = btn.dataset.sitroomBriefMode === _sitroomBriefMode;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-pressed', active ? 'true' : 'false');
  });

  document.querySelectorAll('[data-sitroom-snapshot-template]').forEach(btn => {
    const active = btn.dataset.sitroomSnapshotTemplate === _sitroomSnapshotTemplate;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-pressed', active ? 'true' : 'false');
  });

  _renderSitroomSavedDesks();
  _renderSitroomPosture();

  const newsNav = document.getElementById('sr-newsdesk-nav');
  if (newsNav) newsNav.hidden = _sitroomView !== 'news';
  const newsBrief = document.getElementById('sr-newsdesk-brief');
  if (newsBrief) newsBrief.hidden = _sitroomView !== 'news';

  const copy = document.getElementById('sr-view-copy');
  const mapTitle = document.getElementById('sr-map-command-title');
  const mapCopy = document.getElementById('sr-map-command-copy');
  const meta = SITROOM_VIEW_META[_sitroomView] || SITROOM_VIEW_META.topline;
  const preset = SITROOM_REGION_PRESETS[_sitroomRegionPreset] || SITROOM_REGION_PRESETS.global;
  const deskLabel = _sitroomDeskPreset === 'custom'
    ? 'Custom desk'
    : `${String(_sitroomDeskPreset).replace(/-/g, ' ')} desk`;
  if (copy) copy.textContent = _sitroomView === 'news' ? `${meta.copy} Regional preset: ${preset.label}. ${deskLabel}.` : `${meta.copy} ${deskLabel}.`;
  if (mapTitle) mapTitle.textContent = _sitroomView === 'news' ? `Use the map to anchor the ${preset.label} desk before reading the story stack.` : meta.mapTitle;
  if (mapCopy) mapCopy.textContent = _sitroomView === 'news' ? `The ${preset.label} preset keeps geographic context visible while News Desk narrows the narrative lane to ${_getSitroomNewsGroupLabel().toLowerCase()}.` : meta.mapCopy;

  document.querySelectorAll('#sr-cards-anchor .sr-card').forEach(card => {
    const views = (card.dataset.srViews || '').split(/\s+/).filter(Boolean);
    let visible = views.includes(_sitroomView);
    if (visible && _sitroomView === 'news' && _sitroomNewsGroup !== 'all') {
      const groups = (card.dataset.newsGroup || '').split(/\s+/).filter(Boolean);
      visible = groups.includes(_sitroomNewsGroup);
    }
    card.hidden = !visible;
  });

  _renderSitroomNewsDeskBriefing(_sitroomNewsArticles, _sitroomNewsArticles.length);
  _syncSitroomLayoutEditState();
  _syncSitroomAnalysisState();
}

function _setSitroomView(view) {
  if (!SITROOM_VIEW_META[view]) return;
  _sitroomView = view;
  _sitroomDeskPreset = 'custom';
  _sitroomSavedDeskId = '';
  _applySitroomWorkspaceState();
  _saveSitroomWorkspaceState();
  setTimeout(_sitroomResizeMap, 60);
}

function _setSitroomNewsGroup(group) {
  _sitroomNewsGroup = group || 'all';
  _sitroomDeskPreset = 'custom';
  _sitroomSavedDeskId = '';
  _applySitroomWorkspaceState();
  _saveSitroomWorkspaceState();
}

function _setSitroomRegionPreset(region) {
  if (!SITROOM_REGION_PRESETS[region]) return;
  _sitroomRegionPreset = region;
  _sitroomDeskPreset = 'custom';
  _sitroomSavedDeskId = '';
  _applySitroomWorkspaceState();
  _saveSitroomWorkspaceState();
  loadSitroomNews();
}

function _setSitroomBriefMode(mode) {
  if (!SITROOM_BRIEF_MODE_META[mode]) return;
  _sitroomBriefMode = mode;
  _sitroomSnapshotTemplate = _getSitroomDefaultSnapshotTemplate(mode);
  _sitroomDeskPreset = 'custom';
  _sitroomSavedDeskId = '';
  _applySitroomWorkspaceState();
  _saveSitroomWorkspaceState();
  loadSitroomNews();
}

function _setSitroomSnapshotTemplate(template) {
  if (!SITROOM_SNAPSHOT_TEMPLATES[template]) return;
  _sitroomSnapshotTemplate = template;
  _applySitroomWorkspaceState();
  _saveSitroomWorkspaceState();
}

function _applySitroomLayerPreset(name, options = {}) {
  const {persist = true, saveState = true} = options;
  const layers = SITROOM_LAYER_PRESETS[name];
  if (!layers) return;
  const next = new Set(layers);
  document.querySelectorAll('[data-sitroom-layer]').forEach(cb => {
    cb.checked = next.has(cb.dataset.sitroomLayer);
  });
  _sitroomLayerPreset = name;
  _updateActiveLayerCount();
  if (persist) _saveLayerState();
  if (saveState) _saveSitroomWorkspaceState();
  loadSitroomMapData();
  _updateMapLegend();
  _renderDayNight();
}

function _setSitroomLayerPreset(name) {
  if (!SITROOM_LAYER_PRESETS[name]) return;
  _sitroomDeskPreset = 'custom';
  _sitroomSavedDeskId = '';
  _applySitroomLayerPreset(name, {persist: true, saveState: true});
}

function _setSitroomDeskPreset(name) {
  const preset = SITROOM_DESK_PRESETS[name];
  if (!preset) return;
  _sitroomDeskPreset = name;
  _sitroomSavedDeskId = '';
  _sitroomView = preset.view;
  _sitroomNewsGroup = preset.newsGroup;
  _sitroomRegionPreset = preset.region;
  _sitroomBriefMode = preset.briefMode || 'morning';
  _sitroomSnapshotTemplate = _getSitroomDefaultSnapshotTemplate(_sitroomBriefMode);
  _applySitroomLayerPreset(preset.layerPreset, {persist: true, saveState: false});
  _applySitroomWorkspaceState();
  _saveSitroomWorkspaceState();
  loadSitroomNews();
  setTimeout(_sitroomResizeMap, 60);
}

function _inferSitroomLayerPreset() {
  const checked = [...document.querySelectorAll('[data-sitroom-layer]')]
    .filter(cb => cb.checked)
    .map(cb => cb.dataset.sitroomLayer)
    .sort()
    .join('|');
  for (const [name, layers] of Object.entries(SITROOM_LAYER_PRESETS)) {
    if ([...layers].sort().join('|') === checked) return name;
  }
  return 'custom';
}

function _applySitroomLayerState(state, options = {}) {
  const {persist = true, saveState = true} = options;
  if (!state) return;
  document.querySelectorAll('[data-sitroom-layer]').forEach(cb => {
    if (state[cb.dataset.sitroomLayer] !== undefined) cb.checked = !!state[cb.dataset.sitroomLayer];
  });
  _sitroomLayerPreset = _inferSitroomLayerPreset();
  _updateActiveLayerCount();
  if (persist) _saveLayerState();
  if (saveState) _saveSitroomWorkspaceState();
  loadSitroomMapData();
  _updateMapLegend();
  _renderDayNight();
}

function _saveCurrentSitroomDesk() {
  const input = document.getElementById('sr-saved-desk-name');
  if (!input) return;
  const rawName = input.value.trim();
  if (!rawName) {
    input.focus();
    return;
  }
  const idBase = _slugSitroomPanelId(rawName) || `desk-${Date.now()}`;
  const saved = _readSitroomSavedDesks();
  const existing = saved.find(item => item.name.toLowerCase() === rawName.toLowerCase());
  const entry = {
    id: existing?.id || `${idBase}-${Date.now()}`,
    name: rawName,
    view: _sitroomView,
    newsGroup: _sitroomNewsGroup,
    regionPreset: _sitroomRegionPreset,
    layerPreset: _sitroomLayerPreset,
    briefMode: _sitroomBriefMode,
    snapshotTemplate: _sitroomSnapshotTemplate,
    isDefault: existing?.isDefault || false,
    pinned: existing?.pinned || false,
    order: existing?.order ?? _getNextSitroomSavedDeskOrder(saved),
    layerState: _captureSitroomLayerState(),
    savedAt: new Date().toISOString(),
  };
  const next = existing
    ? saved.map(item => item.id === existing.id ? entry : item)
    : [entry, ...saved].slice(0, 8);
  _writeSitroomSavedDesks(next);
  _sitroomSavedDeskId = entry.id;
  _sitroomDeskPreset = 'custom';
  _saveSitroomWorkspaceState();
  _applySitroomWorkspaceState();
  input.value = '';
}

function _loadSavedSitroomDesk(id) {
  const saved = _readSitroomSavedDesks().find(item => item.id === id);
  if (!saved) return;
  _sitroomSavedDeskId = saved.id;
  _sitroomDeskPreset = 'custom';
  _sitroomView = saved.view && SITROOM_VIEW_META[saved.view] ? saved.view : 'topline';
  _sitroomNewsGroup = saved.newsGroup || 'all';
  _sitroomRegionPreset = SITROOM_REGION_PRESETS[saved.regionPreset] ? saved.regionPreset : 'global';
  _sitroomBriefMode = SITROOM_BRIEF_MODE_META[saved.briefMode] ? saved.briefMode : 'morning';
  _sitroomSnapshotTemplate = SITROOM_SNAPSHOT_TEMPLATES[saved.snapshotTemplate] ? saved.snapshotTemplate : _getSitroomDefaultSnapshotTemplate(_sitroomBriefMode);
  if (saved.layerState) {
    _applySitroomLayerState(saved.layerState, {persist: true, saveState: false});
  } else if (saved.layerPreset && SITROOM_LAYER_PRESETS[saved.layerPreset]) {
    _applySitroomLayerPreset(saved.layerPreset, {persist: true, saveState: false});
  }
  _applySitroomWorkspaceState();
  _saveSitroomWorkspaceState();
  loadSitroomNews();
  setTimeout(_sitroomResizeMap, 60);
}

function _deleteSavedSitroomDesk(id) {
  const next = _readSitroomSavedDesks().filter(item => item.id !== id);
  _writeSitroomSavedDesks(next);
  if (_sitroomSavedDeskId === id) _sitroomSavedDeskId = '';
  _saveSitroomWorkspaceState();
  _applySitroomWorkspaceState();
}

function _toggleSitroomLayoutEdit() {
  _sitroomLayoutEdit = !_sitroomLayoutEdit;
  _syncSitroomLayoutEditState();
}

function _srFeedBadge(text, tone = 'neutral') {
  return `<span class="sr-feed-badge" data-tone="${tone}">${escapeHtml(String(text))}</span>`;
}

function _srFeedIcon(icon, tone = 'neutral') {
  return `<span class="sr-feed-icon" data-tone="${tone}">${icon}</span>`;
}

function _srSummaryChip(text, tone = 'neutral') {
  return `<span class="sr-summary-chip" data-tone="${tone}">${escapeHtml(String(text))}</span>`;
}

function _srMetricRow(label, value, fillPct, tone = 'accent') {
  const pct = Math.max(0, Math.min(100, Number(fillPct) || 0));
  return `<div class="sr-metric-row">
    <span class="sr-metric-label">${escapeHtml(String(label))}</span>
    <div class="sr-metric-bar"><div class="sr-metric-bar-fill" data-tone="${tone}" data-sr-fill="${pct.toFixed(0)}"></div></div>
    <span class="sr-metric-value">${escapeHtml(String(value))}</span>
  </div>`;
}

function _hydrateSitroomRuntimeVars(root) {
  if (!root) return;
  const selector = '[data-sr-fill],[data-sr-width],[data-sr-height],[data-sr-spark-height],[data-sr-monitor-color]';
  const nodes = [];
  if (typeof root.matches === 'function' && root.matches(selector)) nodes.push(root);
  if (typeof root.querySelectorAll === 'function') nodes.push(...root.querySelectorAll(selector));
  nodes.forEach(node => {
    if (node.dataset.srFill) node.style.setProperty('--sr-fill', `${node.dataset.srFill}%`);
    if (node.dataset.srWidth) node.style.setProperty('--sr-width', `${node.dataset.srWidth}%`);
    if (node.dataset.srHeight) node.style.setProperty('--sr-height', `${node.dataset.srHeight}%`);
    if (node.dataset.srSparkHeight) node.style.setProperty('--sr-spark-height', `${node.dataset.srSparkHeight}px`);
    if (node.dataset.srMonitorColor) node.style.setProperty('--sr-monitor-color', node.dataset.srMonitorColor);
  });
}

function _normalizeSitroomText(value) {
  return String(value || '').toLowerCase();
}

function _formatSitroomRelativeTime(value) {
  if (!value) return '';
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) return String(value);
  const diffMs = Date.now() - parsed;
  const diffMinutes = Math.max(0, Math.round(diffMs / 60000));
  if (diffMinutes < 1) return 'just now';
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.round(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return new Date(parsed).toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function _getSitroomFreshnessMeta(status) {
  const meta = {
    LIVE: {label: 'Fresh', tone: 'good', title: 'Live feed updated on schedule and behaving normally.'},
    CACHED: {label: 'Cached', tone: 'warn', title: 'Using cached data. Feed is still usable, but it is not fully live right now.'},
    STALE: {label: 'Stale', tone: 'danger', title: 'Data is older than expected. Treat this feed as aging, not current.'},
    UNAVAILABLE: {label: 'Offline', tone: 'neutral', title: 'The source is unavailable or not responding right now.'},
  };
  return meta[String(status || '').toUpperCase()] || {label: humanizeWorkspaceSlug(status || 'unknown'), tone: 'neutral', title: 'Feed freshness is unknown.'};
}

function _getSitroomSourceAgeLabel(ageSeconds) {
  const value = Number(ageSeconds);
  if (!Number.isFinite(value) || value <= 0) return 'No recent check';
  const minutes = Math.round(value / 60);
  if (minutes < 1) return 'Checked just now';
  if (minutes < 60) return `${minutes}m since last good pull`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h since last good pull`;
  const days = Math.round(hours / 24);
  return `${days}d since last good pull`;
}

function _getSitroomConfidenceMeta(confidence) {
  const value = String(confidence || '').toLowerCase();
  if (value === 'high') return {label: 'High confidence', tone: 'good'};
  if (value === 'medium') return {label: 'Medium confidence', tone: 'warn'};
  if (value === 'low') return {label: 'Low confidence', tone: 'neutral'};
  return {label: humanizeWorkspaceSlug(confidence || 'unknown confidence'), tone: 'neutral'};
}

function _storyMetaLine(source, published) {
  const relativeTime = _formatSitroomRelativeTime(published);
  return [source, relativeTime || published].filter(Boolean).join(' | ');
}

function _captureSitroomLayerState() {
  const state = {};
  document.querySelectorAll('[data-sitroom-layer]').forEach(cb => {
    state[cb.dataset.sitroomLayer] = cb.checked;
  });
  return state;
}

function _readSitroomSavedDesks() {
  const saved = _readSitroomStorageJson('sr-saved-desks', []);
  return Array.isArray(saved) ? _sortSitroomSavedDesks(saved.map((item, index) => _normalizeSitroomSavedDesk(item, index))) : [];
}

function _getSitroomSavedDeskById(id) {
  if (!id) return null;
  return _readSitroomSavedDesks().find(item => item.id === id) || null;
}

function _writeSitroomSavedDesks(saved) {
  try {
    const normalized = _sortSitroomSavedDesks((saved || []).map((item, index) => _normalizeSitroomSavedDesk(item, index)));
    localStorage.setItem('sr-saved-desks', JSON.stringify(normalized));
  } catch (e) { /* localStorage unavailable */ }
}

function _normalizeSitroomSavedDesk(item, index = 0) {
  return {
    ...item,
    isDefault: !!item?.isDefault,
    pinned: !!item?.pinned,
    order: Number.isFinite(Number(item?.order)) ? Number(item.order) : index,
    briefMode: SITROOM_BRIEF_MODE_META[item?.briefMode] ? item.briefMode : 'morning',
    snapshotTemplate: SITROOM_SNAPSHOT_TEMPLATES[item?.snapshotTemplate] ? item.snapshotTemplate : _getSitroomDefaultSnapshotTemplate(item?.briefMode || 'morning'),
  };
}

function _sortSitroomSavedDesks(saved) {
  return [...saved].sort((a, b) => {
    if (!!a.isDefault !== !!b.isDefault) return a.isDefault ? -1 : 1;
    if (!!a.pinned !== !!b.pinned) return a.pinned ? -1 : 1;
    if ((a.order ?? 0) !== (b.order ?? 0)) return (a.order ?? 0) - (b.order ?? 0);
    return String(b.savedAt || '').localeCompare(String(a.savedAt || ''));
  });
}

function _getNextSitroomSavedDeskOrder(saved) {
  return saved.reduce((max, item) => Math.max(max, Number(item.order) || 0), -1) + 1;
}

function _getSitroomDefaultDesk() {
  return _readSitroomSavedDesks().find(item => item.isDefault) || null;
}

function _shouldApplySitroomDefaultDesk() {
  return !_sitroomSavedDeskId
    && _sitroomDeskPreset === 'executive'
    && _sitroomView === 'topline'
    && _sitroomNewsGroup === 'all'
    && _sitroomRegionPreset === 'global';
}

function _applySitroomDefaultDeskOnOpen() {
  const launchDesk = _getSitroomDefaultDesk();
  if (!launchDesk || !_shouldApplySitroomDefaultDesk()) return;
  _loadSavedSitroomDesk(launchDesk.id);
}

function _updateCurrentSavedSitroomDesk() {
  const current = _getSitroomSavedDeskById(_sitroomSavedDeskId);
  if (!current) return;
  const next = _readSitroomSavedDesks().map(item => item.id === current.id ? {
    ...item,
    view: _sitroomView,
    newsGroup: _sitroomNewsGroup,
    regionPreset: _sitroomRegionPreset,
    layerPreset: _sitroomLayerPreset,
    briefMode: _sitroomBriefMode,
    snapshotTemplate: _sitroomSnapshotTemplate,
    layerState: _captureSitroomLayerState(),
    savedAt: new Date().toISOString(),
  } : item);
  _writeSitroomSavedDesks(next);
  _saveSitroomWorkspaceState();
  _applySitroomWorkspaceState();
}

function _togglePinSavedSitroomDesk(id) {
  const next = _readSitroomSavedDesks().map(item => item.id === id ? {...item, pinned: !item.pinned} : item);
  _writeSitroomSavedDesks(next);
  _applySitroomWorkspaceState();
}

function _setSitroomDefaultDesk(id) {
  const next = _readSitroomSavedDesks().map(item => ({
    ...item,
    isDefault: item.id === id ? !item.isDefault : false,
  }));
  _writeSitroomSavedDesks(next);
  _applySitroomWorkspaceState();
}

function _moveSitroomSavedDesk(id, direction = 'later') {
  const saved = _readSitroomSavedDesks();
  const current = saved.find(item => item.id === id);
  if (!current) return;
  const peers = saved.filter(item => !!item.pinned === !!current.pinned);
  const index = peers.findIndex(item => item.id === id);
  const targetIndex = direction === 'earlier' ? index - 1 : index + 1;
  if (index < 0 || targetIndex < 0 || targetIndex >= peers.length) return;
  const target = peers[targetIndex];
  const next = saved.map(item => {
    if (item.id === current.id) return {...item, order: target.order};
    if (item.id === target.id) return {...item, order: current.order};
    return item;
  });
  _writeSitroomSavedDesks(next);
  _applySitroomWorkspaceState();
}

function _renderSitroomSavedDesks() {
  const list = document.getElementById('sr-saved-desk-list');
  if (!list) return;
  const saved = _readSitroomSavedDesks();
  if (!saved.length) {
    list.innerHTML = '<span class="sr-saved-desk-empty">No saved watchlists yet.</span>';
    return;
  }
  list.innerHTML = saved.map(item => `
    <span class="sr-saved-desk-chip${item.id === _sitroomSavedDeskId ? ' active' : ''}">
      <button type="button" class="sr-saved-desk-chip-btn sr-saved-desk-chip-main" data-sitroom-action="load-saved-desk" data-sitroom-saved-desk="${escapeAttr(item.id)}" title="${escapeAttr(`${_getSitroomViewLabel(item.view || 'topline')} · ${(SITROOM_REGION_PRESETS[item.regionPreset] || SITROOM_REGION_PRESETS.global).label} · ${_getSitroomLayerLabel(item.layerPreset || 'custom')} · ${(SITROOM_BRIEF_MODE_META[item.briefMode] || SITROOM_BRIEF_MODE_META.morning).label}`)}">
        <span class="sr-saved-desk-chip-name">${escapeHtml(item.name)}</span>
        <span class="sr-saved-desk-chip-meta">${escapeHtml(`${item.isDefault ? 'Launch Desk · ' : ''}${_getSitroomViewLabel(item.view || 'topline')} · ${(SITROOM_REGION_PRESETS[item.regionPreset] || SITROOM_REGION_PRESETS.global).label} · ${(SITROOM_BRIEF_MODE_META[item.briefMode] || SITROOM_BRIEF_MODE_META.morning).label}`)}</span>
      </button>
      <span class="sr-saved-desk-chip-actions">
        <button type="button" class="sr-saved-desk-chip-btn sr-saved-desk-chip-control sr-saved-desk-chip-default${item.isDefault ? ' is-default' : ''}" data-sitroom-action="set-default-saved-desk" data-sitroom-saved-desk="${escapeAttr(item.id)}" aria-label="${item.isDefault ? 'Unset' : 'Set'} launch desk ${escapeAttr(item.name)}" title="${item.isDefault ? 'Unset launch desk' : 'Set as launch desk'}">&#8962;</button>
        <button type="button" class="sr-saved-desk-chip-btn sr-saved-desk-chip-control sr-saved-desk-chip-pin${item.pinned ? ' is-pinned' : ''}" data-sitroom-action="toggle-pin-saved-desk" data-sitroom-saved-desk="${escapeAttr(item.id)}" aria-label="${item.pinned ? 'Unpin' : 'Pin'} saved desk ${escapeAttr(item.name)}" title="${item.pinned ? 'Unpin watchlist' : 'Pin watchlist'}">&#9733;</button>
        <button type="button" class="sr-saved-desk-chip-btn sr-saved-desk-chip-control" data-sitroom-action="move-saved-desk-earlier" data-sitroom-saved-desk="${escapeAttr(item.id)}" aria-label="Move saved desk ${escapeAttr(item.name)} earlier" title="Move earlier">&#8592;</button>
        <button type="button" class="sr-saved-desk-chip-btn sr-saved-desk-chip-control" data-sitroom-action="move-saved-desk-later" data-sitroom-saved-desk="${escapeAttr(item.id)}" aria-label="Move saved desk ${escapeAttr(item.name)} later" title="Move later">&#8594;</button>
        <button type="button" class="sr-saved-desk-chip-btn sr-saved-desk-chip-remove sr-saved-desk-chip-control" data-sitroom-action="delete-saved-desk" data-sitroom-saved-desk="${escapeAttr(item.id)}" aria-label="Delete saved desk ${escapeAttr(item.name)}">&#10005;</button>
      </span>
    </span>`).join('');
}

function _renderSitroomPosture() {
  const titleEl = document.getElementById('sr-posture-title');
  const copyEl = document.getElementById('sr-posture-copy');
  const chipRow = document.getElementById('sr-posture-chip-row');
  const updateBtn = document.getElementById('sr-update-saved-desk-btn');
  const copyBtn = document.getElementById('sr-copy-desk-snapshot-btn');
  const saveNoteBtn = document.getElementById('sr-save-desk-note-btn');
  const sendLanBtn = document.getElementById('sr-send-desk-lan-btn');
  const input = document.getElementById('sr-saved-desk-name');
  const saved = _getSitroomSavedDeskById(_sitroomSavedDeskId);
  const preset = SITROOM_REGION_PRESETS[_sitroomRegionPreset] || SITROOM_REGION_PRESETS.global;
  const viewLabel = _getSitroomViewLabel();
  const deskLabel = saved ? saved.name : _getSitroomDeskLabel();
  const layerLabel = _getSitroomLayerLabel();
  const groupLabel = _getSitroomNewsGroupLabel();
  const briefLabel = (SITROOM_BRIEF_MODE_META[_sitroomBriefMode] || SITROOM_BRIEF_MODE_META.morning).label;
  const snapshotLabel = (SITROOM_SNAPSHOT_TEMPLATES[_sitroomSnapshotTemplate] || SITROOM_SNAPSHOT_TEMPLATES.morning).label;
  const savedTime = saved ? _formatSitroomSavedTime(saved.savedAt) : '';
  const launchDesk = saved?.isDefault;

  if (titleEl) titleEl.textContent = `${deskLabel} · ${preset.label}`;

  if (copyEl) {
    if (saved) {
      copyEl.textContent = `${viewLabel} view with ${layerLabel.toLowerCase()}, ${groupLabel.toLowerCase()}, and ${briefLabel.toLowerCase()}. Loaded from a saved watchlist${launchDesk ? ' that is also your launch desk' : ''}${savedTime ? ` updated ${savedTime}` : ''}.`;
    } else if (_sitroomDeskPreset === 'custom') {
      copyEl.textContent = `${viewLabel} view with ${layerLabel.toLowerCase()}, ${groupLabel.toLowerCase()}, and ${briefLabel.toLowerCase()}. This is a custom posture, so save it if you expect to return to it.`;
    } else {
      copyEl.textContent = `${viewLabel} view with ${layerLabel.toLowerCase()}, ${groupLabel.toLowerCase()}, and ${briefLabel.toLowerCase()}. Built-in desk presets are meant to get you oriented quickly before you narrow the watchfloor.`;
    }
  }

  if (chipRow) {
    const chips = [
      saved
        ? `<span class="sr-posture-chip is-saved">${launchDesk ? 'Launch Desk' : 'Saved Watchlist'}</span>`
        : _sitroomDeskPreset === 'custom'
          ? '<span class="sr-posture-chip is-custom">Custom Desk</span>'
          : `<span class="sr-posture-chip">${escapeHtml(_getSitroomDeskLabel())}</span>`,
      `<span class="sr-posture-chip">${escapeHtml(viewLabel)}</span>`,
      `<span class="sr-posture-chip">${escapeHtml(preset.label)}</span>`,
      `<span class="sr-posture-chip is-layer">${escapeHtml(layerLabel)}</span>`,
      `<span class="sr-posture-chip">${escapeHtml(briefLabel)}</span>`,
      `<span class="sr-posture-chip">${escapeHtml(snapshotLabel)}</span>`,
    ];
    if (_sitroomView === 'news' || _sitroomNewsGroup !== 'all') {
      chips.push(`<span class="sr-posture-chip">${escapeHtml(groupLabel)}</span>`);
    }
    if (savedTime) chips.push(`<span class="sr-posture-chip">${escapeHtml(savedTime)}</span>`);
    chipRow.innerHTML = chips.join('');
  }

  if (updateBtn) updateBtn.hidden = !saved;
  if (copyBtn) copyBtn.textContent = `Copy ${snapshotLabel}`;
  if (saveNoteBtn) saveNoteBtn.textContent = `Save ${snapshotLabel} to Notes`;
  if (sendLanBtn) sendLanBtn.textContent = `Send ${snapshotLabel} to LAN`;
  if (input && !input.value) {
    input.placeholder = saved ? `Save new desk or update "${saved.name}"` : 'Name current desk';
  }
}

function _filterSitroomNewsByRegion(articles) {
  if (_sitroomRegionPreset === 'global') return articles;
  const preset = SITROOM_REGION_PRESETS[_sitroomRegionPreset];
  if (!preset || !preset.keywords?.length) return articles;
  return articles.filter(article => {
    const haystack = _normalizeSitroomText([
      article.category,
      article.title,
      article.source_name,
      article.description,
      article.published,
    ].filter(Boolean).join(' '));
    return preset.keywords.some(keyword => haystack.includes(keyword));
  });
}

function _scoreSitroomArticleForBriefMode(article) {
  const mode = SITROOM_BRIEF_MODE_META[_sitroomBriefMode];
  if (!mode || _sitroomBriefMode === 'morning') return 0;
  const haystack = _normalizeSitroomText([
    article.category,
    article.title,
    article.description,
    article.source_name,
  ].filter(Boolean).join(' '));
  return mode.keywords.reduce((score, keyword) => score + (haystack.includes(keyword) ? 1 : 0), 0);
}

function _prioritizeSitroomBriefArticles(articles) {
  if (!Array.isArray(articles) || articles.length < 2 || _sitroomBriefMode === 'morning') return articles.slice();
  return articles
    .map((article, index) => ({article, index, score: _scoreSitroomArticleForBriefMode(article)}))
    .sort((a, b) => (b.score - a.score) || (a.index - b.index))
    .map(item => item.article);
}

function _getSitroomNewsGroupLabel() {
  const labels = {
    all: 'All desks',
    world: 'World desk',
    security: 'Security desk',
    markets: 'Markets desk',
    tech: 'Tech desk',
    positive: 'Positive signals',
  };
  return labels[_sitroomNewsGroup] || 'News Desk';
}

function _renderSitroomNewsDeskBriefing(articles = [], totalAvailable = 0) {
  const title = document.getElementById('sr-newsdesk-title');
  const copy = document.getElementById('sr-newsdesk-copy');
  const focus = document.getElementById('sr-newsdesk-focus');
  const chipRow = document.getElementById('sr-newsdesk-chip-row');
  const modeCopy = document.getElementById('sr-newsdesk-mode-copy');
  const preset = SITROOM_REGION_PRESETS[_sitroomRegionPreset] || SITROOM_REGION_PRESETS.global;
  const mode = SITROOM_BRIEF_MODE_META[_sitroomBriefMode] || SITROOM_BRIEF_MODE_META.morning;
  const visibleCount = articles.length;
  const categoryCounts = {};
  const sourceCounts = {};

  articles.forEach(article => {
    if (article.category) categoryCounts[article.category] = (categoryCounts[article.category] || 0) + 1;
    if (article.source_name) sourceCounts[article.source_name] = (sourceCounts[article.source_name] || 0) + 1;
  });

  const topCategories = Object.entries(categoryCounts).sort((a, b) => b[1] - a[1]).slice(0, 3);
  const leadSource = Object.entries(sourceCounts).sort((a, b) => b[1] - a[1])[0];
  const groupLabel = _getSitroomNewsGroupLabel();

  if (title) title.textContent = `${preset.title} · ${groupLabel}`;
  if (copy) {
    copy.textContent = visibleCount
      ? `${preset.copy} ${mode.label} is active, and ${visibleCount} live headlines are in this lane${totalAvailable ? ` out of ${totalAvailable} loaded` : ''}.`
      : `${preset.copy} No current headlines match this regional preset, so switch presets or broaden the desk.`;
  }
  if (modeCopy) modeCopy.textContent = mode.copy;
  if (focus) {
    focus.textContent = visibleCount
      ? `Lead signal: ${topCategories[0] ? `${topCategories[0][0]} is driving this desk` : 'Mixed coverage across sources'}${leadSource ? `, with ${leadSource[0]} appearing most often.` : '.'} ${mode.label} is weighting the headline order for this pass.`
      : `No ${preset.label.toLowerCase()} stories are visible in this desk right now. Use another preset or open the broader News Desk.`;
  }
  if (chipRow) {
    const chips = [];
    chips.push(`<span class="sr-newsdesk-chip">${preset.label}</span>`);
    chips.push(`<span class="sr-newsdesk-chip">${groupLabel}</span>`);
    chips.push(`<span class="sr-newsdesk-chip">${escapeHtml(mode.label)}</span>`);
    topCategories.forEach(([name, count]) => chips.push(`<span class="sr-newsdesk-chip">${escapeHtml(name)} ${count}</span>`));
    chipRow.innerHTML = chips.join('');
  }
}

function _syncSitroomAnalysisState() {
  const tab = document.getElementById('tab-situation-room');
  const panel = document.getElementById('sr-analysis-panel');
  if (tab) tab.dataset.inspectorOpen = panel && !panel.hidden ? 'true' : 'false';
}

function _closeSitroomAnalysis() {
  const panel = document.getElementById('sr-analysis-panel');
  if (panel) panel.hidden = true;
  _syncSitroomAnalysisState();
}

function _openSitroomAnalysis({kicker, title, meta, bodyHtml, link, linkLabel = 'Open Source'}) {
  const panel = document.getElementById('sr-analysis-panel');
  const kickerEl = document.getElementById('sr-analysis-kicker');
  const titleEl = document.getElementById('sr-analysis-title');
  const metaEl = document.getElementById('sr-analysis-meta');
  const bodyEl = document.getElementById('sr-analysis-body');
  const linkEl = document.getElementById('sr-analysis-link');
  if (!panel || !kickerEl || !titleEl || !metaEl || !bodyEl || !linkEl) return;
  kickerEl.textContent = kicker || 'Analyst Inspector';
  titleEl.textContent = title || 'Situation Detail';
  metaEl.textContent = meta || 'Context stays docked here while you continue working the main surface.';
  bodyEl.innerHTML = bodyHtml || '<div class="sr-empty">No detail available</div>';
  if (link) {
    linkEl.hidden = false;
    linkEl.href = link;
    linkEl.textContent = linkLabel;
  } else {
    linkEl.hidden = true;
    linkEl.href = '#';
    linkEl.textContent = 'Open Source';
  }
  panel.hidden = false;
  _syncSitroomAnalysisState();
}

function _srKvRow(label, value) {
  return `<div class="sr-kv-row">
    <span class="sr-kv-label">${escapeHtml(String(label))}</span>
    <span class="sr-kv-value">${escapeHtml(String(value))}</span>
  </div>`;
}

function _srHeatIntensity(change) {
  return Math.max(1, Math.min(4, Math.ceil(Math.abs(change) / 0.75)));
}

/* ─── Map ─── */
function _sitroomResizeMap() {
  if (_sitroomMap) { _sitroomMap.resize(); }
}

/* ─── Map Resize Drag Handle ─── */
function _initSitroomMapResize() {
  const handle = document.getElementById('sr-map-resize');
  const mapWrap = document.querySelector('.sr-map-wrap');
  if (!handle || !mapWrap) return;
  let startY = 0, startH = 0, dragging = false;
  handle.addEventListener('mousedown', e => {
    e.preventDefault(); dragging = true; startY = e.clientY; startH = mapWrap.offsetHeight;
    handle.classList.add('dragging');
    document.body.style.cursor = 'ns-resize'; document.body.style.userSelect = 'none';
  });
  document.addEventListener('mousemove', e => {
    if (!dragging) return;
    const newH = Math.max(150, Math.min(window.innerHeight - 200, startH + (e.clientY - startY)));
    mapWrap.style.flex = 'none'; mapWrap.style.height = newH + 'px';
    _sitroomResizeMap();
  });
  document.addEventListener('mouseup', () => {
    if (!dragging) return; dragging = false;
    handle.classList.remove('dragging');
    document.body.style.cursor = ''; document.body.style.userSelect = '';
    _sitroomResizeMap();
  });
}

/* ─── Static Map Data: Nuclear Sites & Military Bases ─── */
const _NUCLEAR_SITES = [
  // Weapons Research & Labs
  {lat:51.39,lng:-1.32,name:'AWE Aldermaston, UK'},{lat:48.86,lng:2.35,name:'CEA Saclay, France'},
  {lat:38.46,lng:-105.0,name:'NORAD Cheyenne Mtn, US'},{lat:55.75,lng:37.62,name:'Kurchatov Inst, Russia'},
  {lat:39.91,lng:116.39,name:'CIAE, China'},{lat:33.73,lng:73.05,name:'PAEC Kahuta, Pakistan'},
  {lat:28.61,lng:77.21,name:'BARC, India'},{lat:32.07,lng:34.78,name:'Dimona, Israel'},
  {lat:35.37,lng:51.42,name:'Tehran NRC, Iran'},{lat:39.03,lng:125.75,name:'Yongbyon, DPRK'},
  {lat:47.62,lng:-122.35,name:'Hanford, US'},{lat:35.89,lng:-84.31,name:'Oak Ridge, US'},
  {lat:33.68,lng:-106.47,name:'White Sands, US'},{lat:36.95,lng:-116.05,name:'Nevada NTS, US'},
  {lat:35.10,lng:-106.62,name:'Sandia Labs, US'},{lat:37.69,lng:-121.70,name:'LLNL, US'},
  {lat:43.59,lng:-116.05,name:'INL Idaho, US'},{lat:34.80,lng:-114.60,name:'Yucca Mountain, US'},
  {lat:51.56,lng:-0.73,name:'AWE Burghfield, UK'},{lat:51.82,lng:-1.31,name:'Harwell, UK'},
  {lat:54.43,lng:-3.50,name:'Sellafield, UK'},{lat:46.20,lng:6.04,name:'CERN, Switzerland'},
  {lat:43.71,lng:7.27,name:'ITER, France'},{lat:44.14,lng:20.65,name:'Vinca, Serbia'},
  {lat:57.74,lng:59.98,name:'Mayak, Russia'},{lat:61.26,lng:73.36,name:'Seversk, Russia'},
  {lat:54.84,lng:20.20,name:'Kaliningrad Storage, Russia'},{lat:56.30,lng:43.97,name:'Sarov/Arzamas-16, Russia'},
  {lat:41.18,lng:69.24,name:'Tashkent Research, Uzbekistan'},
  // Active NPPs — Americas
  {lat:45.94,lng:-119.04,name:'Columbia Gen, US'},{lat:46.21,lng:-119.27,name:'Hanford Site B, US'},
  {lat:44.93,lng:-93.16,name:'Prairie Island, US'},{lat:41.24,lng:-73.95,name:'Indian Point, US'},
  {lat:29.79,lng:-83.51,name:'Crystal River, US'},{lat:33.37,lng:-80.16,name:'VC Summer, US'},
  {lat:30.04,lng:-81.38,name:'St Lucie, US'},{lat:25.44,lng:-80.33,name:'Turkey Point, US'},
  {lat:33.95,lng:-81.32,name:'Vogtle, US'},{lat:35.21,lng:-85.09,name:'Watts Bar, US'},
  {lat:41.60,lng:-81.15,name:'Perry, US'},{lat:43.27,lng:-77.31,name:'Ginna, US'},
  {lat:42.80,lng:-70.79,name:'Seabrook, US'},{lat:39.46,lng:-75.54,name:'Salem/Hope Creek, US'},
  {lat:43.78,lng:-79.19,name:'Pickering, Canada'},{lat:44.34,lng:-81.60,name:'Bruce, Canada'},
  {lat:46.50,lng:-66.45,name:'Point Lepreau, Canada'},{lat:-38.25,lng:-57.88,name:'Atucha, Argentina'},
  {lat:-23.00,lng:-44.46,name:'Angra, Brazil'},
  // Active NPPs — Europe
  {lat:47.38,lng:0.70,name:'Chinon, France'},{lat:49.54,lng:1.88,name:'Paluel, France'},
  {lat:44.33,lng:4.73,name:'Tricastin, France'},{lat:47.90,lng:1.27,name:'St-Laurent, France'},
  {lat:49.98,lng:2.14,name:'Gravelines, France'},{lat:48.27,lng:7.57,name:'Fessenheim, France'},
  {lat:44.26,lng:26.06,name:'Cernavoda, Romania'},{lat:50.70,lng:3.90,name:'Doel, Belgium'},
  {lat:50.53,lng:5.27,name:'Tihange, Belgium'},{lat:51.33,lng:3.71,name:'Borssele, Netherlands'},
  {lat:48.52,lng:10.43,name:'Gundremmingen, Germany'},{lat:49.71,lng:8.41,name:'Biblis, Germany'},
  {lat:61.24,lng:21.44,name:'Olkiluoto, Finland'},{lat:61.40,lng:28.08,name:'Loviisa, Finland'},
  {lat:55.70,lng:13.68,name:'Barseback, Sweden'},{lat:57.42,lng:16.67,name:'Oskarshamn, Sweden'},
  {lat:57.25,lng:12.11,name:'Ringhals, Sweden'},{lat:42.06,lng:24.30,name:'Kozloduy, Bulgaria'},
  {lat:48.09,lng:17.12,name:'Jaslovske Bohunice, Slovakia'},{lat:48.49,lng:18.88,name:'Mochovce, Slovakia'},
  {lat:51.19,lng:22.40,name:'Lublin (proposed), Poland'},{lat:46.40,lng:15.51,name:'Krsko, Slovenia'},
  {lat:47.62,lng:21.72,name:'Paks, Hungary'},{lat:51.42,lng:0.56,name:'Sizewell B, UK'},
  {lat:55.00,lng:-3.21,name:'Torness, UK'},
  // Active NPPs — Asia & Others
  {lat:35.74,lng:139.72,name:'Tokai, Japan'},{lat:36.52,lng:140.60,name:'Tokai-2, Japan'},
  {lat:42.86,lng:141.64,name:'Tomari, Japan'},{lat:37.39,lng:138.60,name:'Kashiwazaki-Kariwa, Japan'},
  {lat:33.49,lng:129.83,name:'Genkai, Japan'},{lat:35.53,lng:135.98,name:'Takahama, Japan'},
  {lat:37.42,lng:126.99,name:'Wolsong, S. Korea'},{lat:35.32,lng:129.38,name:'Shin-Kori, S. Korea'},
  {lat:37.24,lng:127.02,name:'KAERI, S. Korea'},{lat:35.40,lng:129.43,name:'Ulchin/Hanul, S. Korea'},
  {lat:21.67,lng:69.33,name:'Kakrapar, India'},{lat:19.84,lng:72.75,name:'Tarapur, India'},
  {lat:10.17,lng:79.65,name:'Kalpakkam, India'},{lat:13.63,lng:80.18,name:'PFBR Madras, India'},
  {lat:24.10,lng:54.62,name:'Barakah, UAE'},{lat:30.44,lng:30.05,name:'El Dabaa, Egypt'},
  {lat:30.74,lng:120.96,name:'Qinshan, China'},{lat:22.60,lng:114.55,name:'Daya Bay, China'},
  {lat:21.52,lng:109.15,name:'Fangchenggang, China'},{lat:25.44,lng:119.43,name:'Fuqing, China'},
  {lat:44.19,lng:125.30,name:'Hongyanhe, China'},{lat:26.64,lng:108.06,name:'Taishan, China'},
  {lat:50.10,lng:36.23,name:'Kharkiv NPI, Ukraine'},{lat:51.39,lng:30.10,name:'Chernobyl, Ukraine'},
  {lat:47.51,lng:34.59,name:'Zaporizhzhia NPP, Ukraine'},{lat:46.46,lng:30.66,name:'South Ukraine NPP'},
  {lat:51.33,lng:25.86,name:'Rivne NPP, Ukraine'},{lat:56.43,lng:30.60,name:'Leningrad NPP, Russia'},
  {lat:51.67,lng:39.17,name:'Novovoronezh NPP, Russia'},{lat:55.62,lng:41.93,name:'VVER Dimitrovgrad, Russia'},
  {lat:56.84,lng:35.91,name:'Kalinin NPP, Russia'},{lat:59.44,lng:24.48,name:'Paldiski, Estonia'},
  {lat:-34.00,lng:18.72,name:'Koeberg, South Africa'},
];
const _MILITARY_BASES = [
  // US Major Installations
  {lat:36.77,lng:-76.29,name:'Norfolk Naval Station, US'},{lat:32.87,lng:-117.14,name:'Camp Pendleton, US'},
  {lat:38.95,lng:-77.45,name:'CIA Langley, US'},{lat:38.87,lng:-77.06,name:'Pentagon, US'},
  {lat:21.35,lng:-157.95,name:'Pearl Harbor, US'},{lat:32.34,lng:-64.68,name:'USNS Bermuda'},
  {lat:71.29,lng:-156.77,name:'Utqiagvik/Barrow, US'},{lat:42.43,lng:-71.22,name:'Hanscom AFB, US'},
  {lat:38.71,lng:-104.78,name:'Fort Carson, US'},{lat:31.38,lng:-100.42,name:'Goodfellow AFB, US'},
  {lat:38.95,lng:-92.33,name:'Fort Leonard Wood, US'},{lat:30.43,lng:-86.70,name:'Eglin AFB, US'},
  {lat:30.39,lng:-87.35,name:'NAS Pensacola, US'},{lat:28.23,lng:-80.61,name:'Patrick SFB, US'},
  {lat:39.82,lng:-104.66,name:'Buckley SFB, US'},{lat:35.43,lng:-97.38,name:'Tinker AFB, US'},
  {lat:32.38,lng:-86.36,name:'Maxwell AFB, US'},{lat:33.92,lng:-118.02,name:'Los Alamitos, US'},
  {lat:35.23,lng:-106.61,name:'Kirtland AFB, US'},{lat:47.05,lng:-122.77,name:'JBLM, US'},
  {lat:36.23,lng:-76.02,name:'MCAS Cherry Point, US'},{lat:34.72,lng:-120.57,name:'Vandenberg SFB, US'},
  {lat:41.12,lng:-100.68,name:'USSTRATCOM Offutt, US'},{lat:39.11,lng:-121.44,name:'Beale AFB, US'},
  {lat:29.38,lng:-98.58,name:'JBSA, US'},{lat:35.14,lng:-89.99,name:'NSA Mid-South, US'},
  {lat:44.05,lng:-103.06,name:'Ellsworth AFB, US'},{lat:47.92,lng:-117.40,name:'Fairchild AFB, US'},
  {lat:40.49,lng:-93.84,name:'Whiteman AFB, US'},{lat:28.93,lng:-111.05,name:'MCAS Yuma, US'},
  {lat:36.58,lng:-87.49,name:'Fort Campbell, US'},{lat:31.61,lng:-84.17,name:'Fort Moore, US'},
  {lat:35.14,lng:-79.00,name:'Fort Liberty, US'},{lat:31.95,lng:-81.15,name:'Fort Stewart, US'},
  {lat:48.42,lng:-89.91,name:'Fort Drum, US'},{lat:64.30,lng:-149.18,name:'Fort Wainwright, US'},
  // US Overseas
  {lat:26.30,lng:50.21,name:'NSA Bahrain'},{lat:25.41,lng:51.25,name:'Al Udeid AB, Qatar'},
  {lat:24.43,lng:54.65,name:'Al Dhafra AB, UAE'},{lat:11.55,lng:43.15,name:'Camp Lemonnier, Djibouti'},
  {lat:-7.32,lng:72.41,name:'Diego Garcia, BIOT'},{lat:49.95,lng:7.26,name:'Ramstein AB, Germany'},
  {lat:49.43,lng:7.60,name:'Landstuhl Medical, Germany'},{lat:48.22,lng:11.81,name:'Grafenwoehr, Germany'},
  {lat:35.45,lng:139.35,name:'Yokosuka Naval, Japan'},{lat:35.05,lng:136.88,name:'Yokota AB, Japan'},
  {lat:26.35,lng:127.77,name:'Kadena AB, Okinawa'},{lat:26.27,lng:127.73,name:'Camp Foster, Okinawa'},
  {lat:37.47,lng:126.62,name:'Osan AB, S. Korea'},{lat:36.96,lng:127.03,name:'Camp Humphreys, S. Korea'},
  {lat:64.29,lng:-15.23,name:'Keflavik, Iceland'},{lat:36.63,lng:-6.16,name:'Rota Naval, Spain'},
  {lat:41.05,lng:28.95,name:'Incirlik AB, Turkey'},{lat:40.87,lng:14.29,name:'NSA Naples, Italy'},
  {lat:40.92,lng:9.51,name:'La Maddalena, Italy'},{lat:36.82,lng:14.51,name:'NAS Sigonella, Italy'},
  {lat:30.63,lng:32.34,name:'MFO Sinai, Egypt'},{lat:-2.17,lng:-79.92,name:'FOL Manta, Ecuador'},
  // UK
  {lat:36.15,lng:-5.35,name:'Gibraltar, UK'},{lat:35.09,lng:33.27,name:'Akrotiri, Cyprus'},
  {lat:49.20,lng:-2.13,name:'HMNB Devonport, UK'},{lat:51.28,lng:-0.77,name:'Aldershot, UK'},
  {lat:50.79,lng:-1.10,name:'HMNB Portsmouth, UK'},{lat:56.43,lng:-2.87,name:'HMNB Clyde/Faslane, UK'},
  {lat:52.36,lng:0.49,name:'RAF Lakenheath, UK'},{lat:52.35,lng:0.77,name:'RAF Mildenhall, UK'},
  {lat:53.04,lng:-1.25,name:'RAF Waddington, UK'},{lat:51.75,lng:-1.58,name:'RAF Brize Norton, UK'},
  // France
  {lat:48.45,lng:-4.42,name:'Brest Naval, France'},{lat:43.10,lng:5.93,name:'Toulon Naval, France'},
  {lat:48.79,lng:-3.41,name:'Ile Longue SSBN, France'},{lat:43.52,lng:5.44,name:'BA 701 Salon, France'},
  // Russia
  {lat:59.95,lng:30.32,name:'Kronstadt, Russia'},{lat:44.62,lng:33.53,name:'Sevastopol, Russia'},
  {lat:69.08,lng:33.42,name:'Severomorsk, Russia'},{lat:53.01,lng:158.65,name:'Petropavlovsk, Russia'},
  {lat:48.73,lng:44.50,name:'Volgograd, Russia'},{lat:55.01,lng:82.93,name:'Novosibirsk, Russia'},
  {lat:43.12,lng:131.90,name:'Vladivostok Fleet, Russia'},{lat:68.97,lng:33.09,name:'Gadzhiyevo SSBN, Russia'},
  {lat:62.73,lng:40.32,name:'Severodvinsk Shipyard, Russia'},{lat:56.14,lng:40.40,name:'Teykovo ICBM, Russia'},
  {lat:51.77,lng:55.95,name:'Dombarovsky ICBM, Russia'},{lat:52.93,lng:84.32,name:'Barnaul, Russia'},
  {lat:59.57,lng:150.78,name:'Magadan, Russia'},{lat:43.11,lng:44.67,name:'Vladikavkaz, Russia'},
  // China
  {lat:18.27,lng:109.58,name:'Yulin Naval, China'},{lat:38.05,lng:121.37,name:'Lushun Naval, China'},
  {lat:36.07,lng:120.38,name:'Qingdao Naval, China'},{lat:30.00,lng:122.15,name:'Zhoushan Naval, China'},
  {lat:22.32,lng:114.17,name:'Stonecutters Is, HK'},{lat:39.13,lng:117.35,name:'Tianjin Garrison, China'},
  {lat:31.40,lng:121.46,name:'Shanghai Garrison, China'},{lat:25.05,lng:102.72,name:'Kunming AB, China'},
  {lat:29.57,lng:106.55,name:'Chongqing Mil Region, China'},{lat:34.38,lng:108.93,name:'Xian PLAAF, China'},
  {lat:43.80,lng:87.63,name:'Urumqi, China'},{lat:16.83,lng:112.33,name:'Woody Island, SCS'},
  // India
  {lat:13.05,lng:77.51,name:'Yelahanka AFB, India'},{lat:15.39,lng:73.83,name:'INS Hansa Goa, India'},
  {lat:8.97,lng:76.96,name:'Trivandrum Naval, India'},{lat:18.58,lng:83.55,name:'Visakhapatnam Naval, India'},
  {lat:26.30,lng:73.05,name:'Jodhpur AFB, India'},{lat:26.93,lng:75.78,name:'Jaipur Mil, India'},
  // Middle East
  {lat:24.75,lng:46.65,name:'Prince Sultan AB, Saudi Arabia'},{lat:26.27,lng:50.16,name:'King Fahd AB, Saudi'},
  {lat:21.48,lng:39.18,name:'Jeddah Naval, Saudi Arabia'},{lat:29.01,lng:48.08,name:'Ali Al Salem, Kuwait'},
  {lat:23.58,lng:58.28,name:'Thumrait AB, Oman'},{lat:32.35,lng:36.26,name:'Muwaffaq al-Salti, Jordan'},
  // NATO Europe
  {lat:37.09,lng:24.94,name:'Souda Bay, Greece'},{lat:56.94,lng:24.11,name:'Adazi, Latvia'},
  {lat:54.52,lng:18.53,name:'Gdynia Naval, Poland'},{lat:68.43,lng:17.39,name:'Bardufoss, Norway'},
  {lat:64.84,lng:25.42,name:'Oulu, Finland'},{lat:59.41,lng:24.83,name:'Tapa, Estonia'},
  {lat:55.07,lng:14.68,name:'Bornholm, Denmark'},{lat:58.11,lng:8.08,name:'Kristiansand, Norway'},
  {lat:52.65,lng:13.50,name:'Strausberg, Germany'},{lat:50.84,lng:6.95,name:'Geilenkirchen AWACS, Germany'},
  {lat:41.92,lng:12.50,name:'Centocelle, Italy'},{lat:45.43,lng:12.34,name:'Venice Arsenale, Italy'},
  {lat:41.65,lng:-8.75,name:'Braga, Portugal'},{lat:40.50,lng:-3.68,name:'Torrejon AB, Spain'},
  {lat:57.66,lng:12.24,name:'Gothenburg Garrison, Sweden'},{lat:59.87,lng:17.59,name:'Uppsala, Sweden'},
  // Asia-Pacific
  {lat:1.35,lng:103.82,name:'Changi Naval, Singapore'},{lat:-34.73,lng:138.57,name:'Edinburgh, Australia'},
  {lat:-33.84,lng:151.25,name:'Garden Island, Australia'},{lat:-19.25,lng:146.77,name:'Townsville, Australia'},
  {lat:-31.93,lng:115.97,name:'HMAS Stirling, Australia'},{lat:14.49,lng:121.00,name:'Fort Bonifacio, Philippines'},
  {lat:12.88,lng:100.86,name:'U-Tapao, Thailand'},{lat:33.45,lng:126.57,name:'Jeju Naval, S. Korea'},
  // South America & Africa
  {lat:-25.70,lng:28.23,name:'Waterkloof AFB, South Africa'},{lat:-33.97,lng:18.60,name:'Simon\'s Town Naval, SA'},
  {lat:6.22,lng:-75.59,name:'Rionegro, Colombia'},{lat:-31.40,lng:-64.18,name:'Cordoba AB, Argentina'},
  {lat:-22.92,lng:-43.17,name:'Rio Naval, Brazil'},{lat:-12.91,lng:-38.51,name:'Salvador Naval, Brazil'},
  {lat:5.60,lng:-0.17,name:'Burma Camp, Ghana'},{lat:9.06,lng:7.49,name:'Abuja Barracks, Nigeria'},
  // Pakistan/Central Asia
  {lat:30.24,lng:67.00,name:'Quetta Cantonment, Pakistan'},{lat:33.62,lng:73.10,name:'Rawalpindi GHQ, Pakistan'},
  {lat:24.89,lng:67.01,name:'Masroor AB, Pakistan'},{lat:25.27,lng:68.37,name:'Shahbaz AB, Pakistan'},
  {lat:34.95,lng:69.27,name:'Bagram, Afghanistan'},{lat:41.26,lng:69.28,name:'Chirchik, Uzbekistan'},
  {lat:38.55,lng:68.77,name:'Dushanbe 201st, Tajikistan'},
];

const _CABLE_LANDINGS = [
  {lat:50.95,lng:1.85,name:'Calais Cable Landing, FR'},{lat:51.13,lng:1.32,name:'Dover Cable Landing, UK'},
  {lat:40.57,lng:-73.97,name:'NYC Cable Hub, US'},{lat:37.78,lng:-122.41,name:'SF Cable Hub, US'},
  {lat:25.77,lng:-80.19,name:'Miami Cable Hub, US'},{lat:22.28,lng:114.17,name:'Hong Kong Cable Hub'},
  {lat:1.29,lng:103.85,name:'Singapore Cable Hub'},{lat:35.68,lng:139.77,name:'Tokyo Cable Hub, JP'},
  {lat:-33.87,lng:151.21,name:'Sydney Cable Hub, AU'},{lat:6.45,lng:3.39,name:'Lagos Cable Hub, NG'},
  {lat:32.08,lng:34.78,name:'Tel Aviv Cable Hub, IL'},{lat:25.20,lng:55.27,name:'Dubai Cable Hub, UAE'},
  {lat:13.08,lng:80.28,name:'Chennai Cable Hub, IN'},{lat:4.62,lng:-74.07,name:'Bogota Cable Landing, CO'},
  {lat:-22.91,lng:-43.17,name:'Rio Cable Hub, BR'},{lat:51.50,lng:0.08,name:'London Docklands Hub, UK'},
  {lat:52.37,lng:4.90,name:'Amsterdam Cable Hub, NL'},{lat:60.17,lng:24.94,name:'Helsinki Cable Hub, FI'},
  {lat:59.33,lng:18.07,name:'Stockholm Cable Hub, SE'},{lat:36.20,lng:-5.37,name:'Gibraltar Cable Hub'},
  {lat:41.15,lng:-8.61,name:'Porto/Carcavelos, PT'},{lat:43.37,lng:-8.40,name:'Vigo, Spain'},
  {lat:38.72,lng:-9.14,name:'Lisbon/Sesimbra, PT'},{lat:33.59,lng:-7.59,name:'Casablanca, Morocco'},
  {lat:36.75,lng:3.06,name:'Algiers, Algeria'},{lat:36.81,lng:10.17,name:'Tunis, Tunisia'},
  {lat:31.21,lng:29.89,name:'Alexandria, Egypt'},{lat:11.59,lng:43.15,name:'Djibouti Cable Hub'},
  {lat:-4.04,lng:39.67,name:'Mombasa Cable Hub, KE'},{lat:-6.16,lng:39.19,name:'Dar es Salaam, TZ'},
  {lat:-25.97,lng:32.58,name:'Maputo, Mozambique'},{lat:-33.93,lng:18.42,name:'Cape Town, SA'},
  {lat:-4.30,lng:15.30,name:'Muanda, DRC'},{lat:14.69,lng:-17.44,name:'Dakar Cable Hub, SN'},
  {lat:5.56,lng:-0.19,name:'Accra Cable Hub, GH'},{lat:3.14,lng:101.69,name:'Kuala Lumpur Cable, MY'},
  {lat:-6.21,lng:106.85,name:'Jakarta Cable Hub, ID'},{lat:14.60,lng:120.98,name:'Manila Cable Hub, PH'},
  {lat:10.82,lng:106.63,name:'Ho Chi Minh Cable, VN'},{lat:21.03,lng:105.85,name:'Hanoi/Haiphong, VN'},
  {lat:37.57,lng:126.98,name:'Seoul/Busan Cable, KR'},{lat:25.04,lng:121.57,name:'Taipei/Toucheng, TW'},
  {lat:34.69,lng:135.50,name:'Osaka Cable Hub, JP'},{lat:-37.81,lng:144.96,name:'Melbourne Cable Hub, AU'},
  {lat:-36.85,lng:174.76,name:'Auckland Cable Hub, NZ'},{lat:21.31,lng:-157.86,name:'Honolulu Cable Hub, US'},
  {lat:-17.73,lng:-149.57,name:'Tahiti Cable Hub, FR'},{lat:-18.14,lng:178.44,name:'Fiji Cable Hub'},
  {lat:45.50,lng:-73.57,name:'Montreal Cable, CA'},{lat:43.65,lng:-79.38,name:'Toronto Cable, CA'},
  {lat:19.43,lng:-99.13,name:'Mexico City Cable Hub'},{lat:-12.05,lng:-77.04,name:'Lima Cable Hub, PE'},
  {lat:-34.60,lng:-58.38,name:'Buenos Aires Cable, AR'},{lat:-33.45,lng:-70.67,name:'Santiago/Valparaiso, CL'},
];
const _DATA_CENTERS = [
  // US — Major Cloud Regions & Colocation
  {lat:39.04,lng:-77.49,name:'Ashburn VA (Data Center Alley)'},{lat:39.10,lng:-77.55,name:'Ashburn VA West Cluster'},
  {lat:37.37,lng:-121.92,name:'Santa Clara CA, US'},{lat:37.57,lng:-122.05,name:'Milpitas CA, US'},
  {lat:47.61,lng:-122.33,name:'Seattle/Westin, US'},{lat:45.59,lng:-122.60,name:'Portland Hillsboro, US'},
  {lat:33.75,lng:-84.39,name:'Atlanta GA, US'},{lat:41.88,lng:-87.63,name:'Chicago IL, US'},
  {lat:32.78,lng:-96.80,name:'Dallas TX, US'},{lat:29.76,lng:-95.37,name:'Houston TX, US'},
  {lat:34.05,lng:-118.24,name:'Los Angeles CA, US'},{lat:36.17,lng:-115.14,name:'Las Vegas NV, US'},
  {lat:33.45,lng:-112.07,name:'Phoenix AZ, US'},{lat:39.74,lng:-104.99,name:'Denver CO, US'},
  {lat:25.76,lng:-80.19,name:'Miami FL, US'},{lat:43.07,lng:-89.40,name:'Madison WI, US'},
  {lat:42.36,lng:-71.06,name:'Boston MA, US'},{lat:40.71,lng:-74.01,name:'New York NY, US'},
  {lat:38.90,lng:-77.04,name:'Washington DC, US'},{lat:35.23,lng:-80.84,name:'Charlotte NC, US'},
  {lat:27.95,lng:-82.46,name:'Tampa FL, US'},{lat:47.25,lng:-122.44,name:'Tacoma/CenturyLink, US'},
  {lat:41.49,lng:-81.69,name:'Cleveland OH, US'},{lat:44.97,lng:-93.27,name:'Minneapolis MN, US'},
  {lat:30.27,lng:-97.74,name:'Austin TX, US'},{lat:36.85,lng:-76.29,name:'Virginia Beach VA, US'},
  // Canada
  {lat:45.50,lng:-73.57,name:'Montreal QC, Canada'},{lat:43.65,lng:-79.38,name:'Toronto ON, Canada'},
  {lat:45.42,lng:-75.70,name:'Ottawa ON, Canada'},{lat:49.28,lng:-123.12,name:'Vancouver BC, Canada'},
  {lat:51.05,lng:-114.07,name:'Calgary AB, Canada'},
  // Europe
  {lat:53.35,lng:-6.26,name:'Dublin, Ireland (EU hub)'},{lat:53.34,lng:-6.44,name:'Dublin West, Ireland'},
  {lat:50.11,lng:8.68,name:'Frankfurt, Germany'},{lat:50.08,lng:8.58,name:'Frankfurt DE2'},
  {lat:52.37,lng:4.90,name:'Amsterdam, Netherlands'},{lat:52.08,lng:5.13,name:'Utrecht, Netherlands'},
  {lat:51.50,lng:-0.12,name:'London Docklands, UK'},{lat:51.52,lng:-0.71,name:'Slough, UK'},
  {lat:55.68,lng:12.57,name:'Copenhagen, Denmark'},{lat:59.33,lng:18.07,name:'Stockholm, Sweden'},
  {lat:60.17,lng:24.94,name:'Helsinki, Finland'},{lat:59.95,lng:10.75,name:'Oslo, Norway'},
  {lat:48.86,lng:2.35,name:'Paris, France'},{lat:43.60,lng:1.44,name:'Toulouse, France'},
  {lat:45.46,lng:9.19,name:'Milan, Italy'},{lat:41.90,lng:12.50,name:'Rome, Italy'},
  {lat:40.42,lng:-3.70,name:'Madrid, Spain'},{lat:41.39,lng:2.17,name:'Barcelona, Spain'},
  {lat:55.75,lng:37.62,name:'Moscow, Russia'},{lat:59.93,lng:30.32,name:'St Petersburg, Russia'},
  {lat:52.52,lng:13.41,name:'Berlin, Germany'},{lat:48.14,lng:11.58,name:'Munich, Germany'},
  {lat:50.94,lng:6.96,name:'Cologne, Germany'},{lat:46.95,lng:7.45,name:'Bern, Switzerland'},
  {lat:47.37,lng:8.54,name:'Zurich, Switzerland'},{lat:46.20,lng:6.14,name:'Geneva, Switzerland'},
  {lat:48.21,lng:16.37,name:'Vienna, Austria'},{lat:50.08,lng:14.44,name:'Prague, Czech Republic'},
  {lat:52.23,lng:21.01,name:'Warsaw, Poland'},{lat:47.50,lng:19.04,name:'Budapest, Hungary'},
  {lat:44.43,lng:26.10,name:'Bucharest, Romania'},{lat:42.70,lng:23.32,name:'Sofia, Bulgaria'},
  {lat:38.72,lng:-9.14,name:'Lisbon, Portugal'},{lat:41.01,lng:28.98,name:'Istanbul, Turkey'},
  // Middle East
  {lat:25.20,lng:55.27,name:'Dubai, UAE'},{lat:24.45,lng:54.65,name:'Abu Dhabi, UAE'},
  {lat:26.22,lng:50.58,name:'Bahrain'},{lat:25.29,lng:51.53,name:'Doha, Qatar'},
  {lat:24.71,lng:46.67,name:'Riyadh, Saudi Arabia'},{lat:31.95,lng:35.95,name:'Amman, Jordan'},
  {lat:32.07,lng:34.78,name:'Tel Aviv, Israel'},{lat:33.89,lng:35.50,name:'Beirut, Lebanon'},
  {lat:35.69,lng:51.39,name:'Tehran, Iran'},{lat:30.04,lng:31.24,name:'Cairo, Egypt'},
  // Asia-Pacific
  {lat:1.35,lng:103.82,name:'Singapore (Tuas/Jurong)'},{lat:1.31,lng:103.86,name:'Singapore (Tai Seng)'},
  {lat:35.68,lng:139.69,name:'Tokyo, Japan'},{lat:34.69,lng:135.50,name:'Osaka, Japan'},
  {lat:22.32,lng:114.17,name:'Hong Kong'},{lat:22.27,lng:114.19,name:'Tseung Kwan O, HK'},
  {lat:37.57,lng:126.98,name:'Seoul, South Korea'},{lat:36.35,lng:127.38,name:'Daejeon, S. Korea'},
  {lat:25.04,lng:121.57,name:'Taipei, Taiwan'},{lat:24.97,lng:121.24,name:'Taoyuan, Taiwan'},
  {lat:39.91,lng:116.39,name:'Beijing, China'},{lat:31.23,lng:121.47,name:'Shanghai, China'},
  {lat:23.13,lng:113.26,name:'Guangzhou, China'},{lat:22.54,lng:114.06,name:'Shenzhen, China'},
  {lat:29.06,lng:111.68,name:'Changsha, China'},{lat:26.07,lng:119.30,name:'Fuzhou, China'},
  {lat:19.08,lng:72.88,name:'Mumbai, India'},{lat:12.97,lng:77.59,name:'Bangalore, India'},
  {lat:28.63,lng:77.22,name:'New Delhi/Noida, India'},{lat:17.39,lng:78.49,name:'Hyderabad, India'},
  {lat:13.08,lng:80.27,name:'Chennai, India'},{lat:23.81,lng:90.41,name:'Dhaka, Bangladesh'},
  {lat:14.60,lng:120.98,name:'Manila, Philippines'},{lat:3.14,lng:101.69,name:'Kuala Lumpur, Malaysia'},
  {lat:-6.21,lng:106.85,name:'Jakarta, Indonesia'},{lat:13.76,lng:100.50,name:'Bangkok, Thailand'},
  {lat:21.03,lng:105.85,name:'Hanoi, Vietnam'},{lat:10.82,lng:106.63,name:'Ho Chi Minh City, Vietnam'},
  // Oceania
  {lat:-33.87,lng:151.21,name:'Sydney, Australia'},{lat:-37.81,lng:144.96,name:'Melbourne, Australia'},
  {lat:-27.47,lng:153.03,name:'Brisbane, Australia'},{lat:-31.95,lng:115.86,name:'Perth, Australia'},
  {lat:-35.28,lng:149.13,name:'Canberra, Australia'},{lat:-36.85,lng:174.76,name:'Auckland, New Zealand'},
  // Latin America
  {lat:-23.55,lng:-46.63,name:'Sao Paulo, Brazil'},{lat:-22.91,lng:-43.17,name:'Rio de Janeiro, Brazil'},
  {lat:-34.60,lng:-58.38,name:'Buenos Aires, Argentina'},{lat:-33.45,lng:-70.67,name:'Santiago, Chile'},
  {lat:4.60,lng:-74.08,name:'Bogota, Colombia'},{lat:19.43,lng:-99.13,name:'Mexico City, Mexico'},
  {lat:20.68,lng:-103.35,name:'Guadalajara, Mexico'},{lat:25.67,lng:-100.31,name:'Monterrey, Mexico'},
  {lat:10.50,lng:-66.92,name:'Caracas, Venezuela'},{lat:-12.05,lng:-77.04,name:'Lima, Peru'},
  // Africa
  {lat:6.52,lng:3.38,name:'Lagos, Nigeria'},{lat:-1.29,lng:36.82,name:'Nairobi, Kenya'},
  {lat:-33.93,lng:18.42,name:'Cape Town, South Africa'},{lat:-26.20,lng:28.04,name:'Johannesburg, South Africa'},
  {lat:5.56,lng:-0.19,name:'Accra, Ghana'},{lat:33.59,lng:-7.59,name:'Casablanca, Morocco'},
  {lat:14.69,lng:-17.44,name:'Dakar, Senegal'},{lat:9.02,lng:38.75,name:'Addis Ababa, Ethiopia'},
  {lat:36.75,lng:3.06,name:'Algiers, Algeria'},{lat:0.31,lng:32.58,name:'Kampala, Uganda'},
];

const _PIPELINE_HUBS = [
  // Europe
  {lat:51.50,lng:3.60,name:'Rotterdam Pipeline Hub, NL'},{lat:60.39,lng:5.32,name:'Bergen Gas Hub, NO'},
  {lat:56.15,lng:10.21,name:'Denmark Gas Junction'},{lat:41.01,lng:28.98,name:'TurkStream Landing, TR'},
  {lat:54.32,lng:13.09,name:'Nord Stream Landing, DE'},{lat:36.80,lng:10.18,name:'TransMed Pipeline, TN'},
  {lat:31.25,lng:32.31,name:'East Med Gas Hub, EG'},{lat:51.88,lng:55.10,name:'Druzhba Pipeline Hub, RU'},
  {lat:55.76,lng:49.12,name:'Kazan Junction, RU'},{lat:53.21,lng:50.14,name:'Samara Pipeline Hub, RU'},
  {lat:58.96,lng:5.73,name:'Stavanger Gas, NO'},{lat:57.05,lng:9.93,name:'Aalborg Gas, DK'},
  {lat:51.43,lng:6.76,name:'Duisburg Pipeline Hub, DE'},{lat:48.78,lng:9.18,name:'Stuttgart Gas Hub, DE'},
  {lat:45.46,lng:9.19,name:'Milan Pipeline Junction, IT'},{lat:40.85,lng:14.27,name:'Naples Compressor, IT'},
  {lat:38.72,lng:-9.14,name:'Sines LNG Terminal, PT'},{lat:43.26,lng:5.38,name:'Marseille Fos LNG, FR'},
  {lat:43.35,lng:-3.01,name:'Bilbao LNG, Spain'},{lat:37.80,lng:-1.28,name:'Cartagena LNG, Spain'},
  {lat:46.15,lng:14.99,name:'TAG Pipeline Hub, Slovenia'},{lat:47.87,lng:16.25,name:'Baumgarten Gas Hub, Austria'},
  {lat:51.23,lng:4.40,name:'Antwerp Pipeline Hub, BE'},{lat:54.18,lng:-6.34,name:'Interconnector UK-IE'},
  {lat:53.25,lng:-4.25,name:'Point of Ayr Terminal, UK'},{lat:57.13,lng:-2.08,name:'St Fergus Terminal, UK'},
  {lat:60.81,lng:4.99,name:'Kollsnes Terminal, NO'},{lat:62.47,lng:6.15,name:'Ormen Lange, NO'},
  // Middle East & Central Asia
  {lat:40.41,lng:49.87,name:'BTC Pipeline, AZ'},{lat:41.69,lng:44.80,name:'BTC Tbilisi, Georgia'},
  {lat:36.80,lng:34.63,name:'Ceyhan Terminal, Turkey'},{lat:26.72,lng:49.98,name:'Ras Tanura, SA'},
  {lat:29.37,lng:47.97,name:'Kuwait Oil Hub'},{lat:26.22,lng:50.55,name:'Bahrain Oil Hub'},
  {lat:27.17,lng:56.27,name:'Bandar Abbas, Iran'},{lat:23.59,lng:58.54,name:'Mina al-Fahal, Oman'},
  {lat:29.07,lng:48.13,name:'Mina Abdullah, Kuwait'},{lat:21.38,lng:39.17,name:'Yanbu Terminal, SA'},
  {lat:26.43,lng:50.10,name:'Abqaiq Processing, SA'},{lat:25.36,lng:51.48,name:'Ras Laffan LNG, Qatar'},
  {lat:24.19,lng:52.66,name:'Habshan-Fujairah, UAE'},{lat:30.38,lng:49.00,name:'Basra Oil Terminal, Iraq'},
  {lat:36.19,lng:44.01,name:'Kirkuk Pipeline Hub, Iraq'},{lat:34.44,lng:35.84,name:'Tripoli Terminal, Lebanon'},
  {lat:32.08,lng:34.78,name:'Ashkelon-Eilat Pipeline, IL'},{lat:31.78,lng:35.23,name:'Trans-Israel Pipeline'},
  {lat:43.24,lng:76.95,name:'Almaty CPC, Kazakhstan'},{lat:41.32,lng:69.28,name:'Tashkent Gas Hub, UZ'},
  {lat:37.95,lng:58.38,name:'Turkmenistan TAPI, TM'},{lat:40.18,lng:44.51,name:'Yerevan Gas Hub, Armenia'},
  // Russia & Asia
  {lat:52.52,lng:104.30,name:'ESPO Pipeline East, RU'},{lat:43.12,lng:131.90,name:'Kozmino Terminal, RU'},
  {lat:48.68,lng:44.51,name:'Volgograd Pipeline, RU'},{lat:61.00,lng:69.00,name:'Tyumen Gas Hub, RU'},
  {lat:56.25,lng:43.45,name:'Nizhny Novgorod Junction, RU'},{lat:55.04,lng:73.37,name:'Omsk Pipeline Hub, RU'},
  {lat:39.91,lng:116.39,name:'China Gas Hub, Beijing'},{lat:31.23,lng:121.47,name:'Shanghai LNG Terminal'},
  {lat:23.13,lng:113.26,name:'Guangdong LNG, China'},{lat:39.00,lng:121.86,name:'Dalian LNG, China'},
  {lat:34.66,lng:135.43,name:'Osaka Terminals, Japan'},{lat:35.45,lng:139.65,name:'Yokohama LNG, Japan'},
  {lat:37.57,lng:126.98,name:'Pyeongtaek LNG, S. Korea'},{lat:35.10,lng:128.60,name:'Tongyeong LNG, S. Korea'},
  {lat:20.70,lng:70.35,name:'Jamnagar Refinery, India'},{lat:19.97,lng:73.10,name:'GAIL Pipeline Hub, India'},
  {lat:22.30,lng:91.80,name:'Chittagong LNG, Bangladesh'},
  // Americas
  {lat:29.76,lng:-95.37,name:'Houston Pipeline Hub, US'},{lat:30.07,lng:-89.93,name:'Gulf Coast LOOP, US'},
  {lat:51.05,lng:-114.07,name:'Alberta Pipeline Hub, CA'},{lat:48.80,lng:-123.16,name:'Trans Mountain, CA'},
  {lat:49.16,lng:-122.70,name:'Burnaby Terminal, CA'},{lat:40.33,lng:-80.00,name:'Marcellus Hub, US'},
  {lat:29.93,lng:-93.93,name:'Sabine Pass LNG, US'},{lat:30.12,lng:-93.28,name:'Cameron LNG, US'},
  {lat:27.83,lng:-97.42,name:'Corpus Christi LNG, US'},{lat:30.39,lng:-89.11,name:'Pascagoula, US'},
  {lat:32.35,lng:-90.18,name:'Jackson MS Pipeline, US'},{lat:40.81,lng:-74.07,name:'Linden NJ Hub, US'},
  {lat:41.33,lng:-81.73,name:'Cushing-Patoka, US'},{lat:35.99,lng:-96.75,name:'Cushing OK Hub, US'},
  {lat:4.64,lng:-74.10,name:'Cano Limon, Colombia'},{lat:-23.96,lng:-46.33,name:'Santos Oil Port, Brazil'},
  {lat:-3.73,lng:-38.52,name:'Pecem LNG, Brazil'},{lat:18.20,lng:-66.59,name:'EcoElectrica LNG, PR'},
  {lat:9.36,lng:-79.92,name:'Colon LNG, Panama'},
  // Africa & Oceania
  {lat:36.83,lng:3.08,name:'Arzew LNG, Algeria'},{lat:36.89,lng:5.07,name:'Skikda LNG, Algeria'},
  {lat:0.38,lng:9.41,name:'Libreville FLNG, Gabon'},{lat:-4.30,lng:15.30,name:'Banana Terminal, Congo'},
  {lat:4.05,lng:9.72,name:'Kribi LNG, Cameroon'},{lat:6.45,lng:3.39,name:'Bonny Island LNG, Nigeria'},
  {lat:-25.97,lng:32.59,name:'Temane Pipeline, Mozambique'},{lat:-19.84,lng:34.83,name:'Beira Pipeline, Mozambique'},
  {lat:-38.04,lng:145.19,name:'Longford Terminal, Australia'},{lat:-23.85,lng:151.25,name:'Gladstone LNG, Australia'},
  {lat:-20.78,lng:139.48,name:'Isa-Gladstone Pipeline, AU'},{lat:-21.62,lng:115.39,name:'Karratha NWS LNG, AU'},
];
const _STRATEGIC_WATERWAYS = [
  {lat:30.45,lng:32.35,name:'Suez Canal, Egypt'},{lat:12.60,lng:43.15,name:'Bab el-Mandeb Strait'},
  {lat:26.57,lng:56.25,name:'Strait of Hormuz'},{lat:1.25,lng:103.75,name:'Strait of Malacca'},
  {lat:41.17,lng:29.07,name:'Bosphorus Strait, Turkey'},{lat:9.08,lng:-79.68,name:'Panama Canal'},
  {lat:35.97,lng:-5.50,name:'Strait of Gibraltar'},{lat:36.95,lng:22.48,name:'Cape Matapan, Greece'},
  {lat:-34.62,lng:20.00,name:'Cape of Good Hope'},{lat:-54.80,lng:-68.30,name:'Drake Passage'},
  {lat:61.10,lng:-45.00,name:'Denmark Strait'},{lat:54.00,lng:7.90,name:'Kiel Canal, Germany'},
  {lat:48.40,lng:-4.50,name:'English Channel entrance'},{lat:10.40,lng:107.00,name:'South China Sea chokepoint'},
  {lat:2.50,lng:101.80,name:'Singapore Strait'},{lat:43.37,lng:4.84,name:'Gulf of Lion, France'},
  {lat:-8.00,lng:115.50,name:'Lombok Strait, Indonesia'},{lat:-5.50,lng:105.80,name:'Sunda Strait, Indonesia'},
  {lat:12.00,lng:44.00,name:'Gulf of Aden'},{lat:33.70,lng:35.90,name:'Eastern Mediterranean'},
  {lat:57.00,lng:11.00,name:'Skagerrak Strait, DK/NO/SE'},{lat:55.50,lng:12.70,name:'Oresund, DK/SE'},
  {lat:-1.50,lng:116.00,name:'Makassar Strait, Indonesia'},{lat:22.20,lng:114.10,name:'Victoria Harbour, HK'},
  {lat:38.00,lng:-0.50,name:'Strait of Sicily/Tunisia'},{lat:42.50,lng:18.50,name:'Strait of Otranto'},
];
const _SPACEPORTS = [
  {lat:28.57,lng:-80.65,name:'Kennedy Space Center, US'},{lat:34.63,lng:-120.63,name:'Vandenberg SFB, US'},
  {lat:45.92,lng:63.34,name:'Baikonur Cosmodrome, KZ'},{lat:62.93,lng:40.58,name:'Plesetsk, Russia'},
  {lat:5.24,lng:-52.77,name:'Guiana Space Centre, FR'},{lat:19.61,lng:110.95,name:'Wenchang, China'},
  {lat:40.96,lng:100.30,name:'Jiuquan, China'},{lat:28.25,lng:102.03,name:'Xichang, China'},
  {lat:13.72,lng:80.23,name:'Satish Dhawan, India'},{lat:31.25,lng:131.08,name:'Tanegashima, Japan'},
  {lat:-2.95,lng:40.21,name:'Luigi Broglio, Kenya'},{lat:28.24,lng:-16.64,name:'El Hierro (proposed), Spain'},
  {lat:25.99,lng:-97.15,name:'SpaceX Starbase, US'},{lat:-31.04,lng:136.50,name:'Woomera, Australia'},
  {lat:57.44,lng:-4.26,name:'Sutherland Spaceport, UK'},{lat:69.30,lng:16.02,name:'Andoya, Norway'},
  {lat:51.23,lng:0.53,name:'One Web Newquay, UK'},{lat:36.46,lng:-6.20,name:'El Arenosillo, Spain'},
  {lat:2.37,lng:101.40,name:'SEALS, Malaysia'},{lat:-2.18,lng:-44.39,name:'Alcantara, Brazil'},
  {lat:30.39,lng:130.97,name:'Uchinoura, Japan'},{lat:38.33,lng:127.53,name:'Naro, South Korea'},
  {lat:41.10,lng:100.46,name:'Taiyuan, China'},{lat:68.11,lng:21.58,name:'Esrange, Sweden'},
  {lat:-39.26,lng:177.86,name:'Rocket Lab Mahia, NZ'},{lat:64.66,lng:-18.10,name:'Keflavik (proposed), Iceland'},
];
const _SHIPPING_HUBS = [
  {lat:31.23,lng:121.47,name:'Shanghai, China (#1 port)'},{lat:1.26,lng:103.84,name:'Singapore (#2 port)'},
  {lat:22.25,lng:114.17,name:'Hong Kong/Shenzhen'},{lat:35.44,lng:129.37,name:'Busan, South Korea'},
  {lat:51.90,lng:4.50,name:'Rotterdam, Netherlands'},{lat:53.55,lng:9.99,name:'Hamburg, Germany'},
  {lat:37.95,lng:23.63,name:'Piraeus, Greece'},{lat:29.95,lng:32.56,name:'Port Said, Egypt (Suez)'},
  {lat:25.28,lng:55.30,name:'Jebel Ali, UAE'},{lat:40.68,lng:-74.04,name:'NY/NJ Port, US'},
  {lat:33.75,lng:-118.28,name:'Long Beach/LA, US'},{lat:12.98,lng:80.18,name:'Chennai, India'},
  {lat:-33.86,lng:151.21,name:'Sydney, Australia'},{lat:-23.95,lng:-46.30,name:'Santos, Brazil'},
  {lat:35.45,lng:139.65,name:'Yokohama, Japan'},{lat:22.84,lng:108.37,name:'Qinzhou, China'},
  {lat:22.62,lng:120.29,name:'Kaohsiung, Taiwan'},{lat:30.63,lng:104.07,name:'Ningbo-Zhoushan, China'},
  {lat:23.13,lng:113.26,name:'Guangzhou, China'},{lat:36.07,lng:120.38,name:'Qingdao, China'},
  {lat:39.00,lng:121.86,name:'Dalian, China'},{lat:38.93,lng:121.62,name:'Tianjin, China'},
  {lat:3.00,lng:101.40,name:'Port Klang, Malaysia'},{lat:-6.12,lng:106.88,name:'Tanjung Priok, Indonesia'},
  {lat:13.10,lng:80.29,name:'Ennore, India'},{lat:22.95,lng:72.68,name:'Mundra, India'},
  {lat:10.00,lng:76.27,name:'Kochi, India'},{lat:18.94,lng:72.84,name:'JNPT Mumbai, India'},
  {lat:53.35,lng:-6.26,name:'Dublin Port, Ireland'},{lat:51.95,lng:1.25,name:'Felixstowe, UK'},
  {lat:50.90,lng:1.85,name:'Calais, France'},{lat:43.30,lng:5.36,name:'Marseille, France'},
  {lat:53.50,lng:8.13,name:'Bremerhaven, Germany'},{lat:51.43,lng:3.57,name:'Antwerp, Belgium'},
  {lat:59.55,lng:10.70,name:'Oslo, Norway'},{lat:57.70,lng:11.93,name:'Gothenburg, Sweden'},
  {lat:37.78,lng:-122.28,name:'Oakland, US'},{lat:29.73,lng:-95.27,name:'Houston Ship Channel, US'},
  {lat:32.10,lng:-81.09,name:'Savannah, US'},{lat:-33.93,lng:18.42,name:'Cape Town, South Africa'},
  {lat:-4.05,lng:39.67,name:'Mombasa, Kenya'},{lat:6.45,lng:3.39,name:'Apapa/Lagos, Nigeria'},
  {lat:36.83,lng:3.08,name:'Algiers, Algeria'},{lat:33.60,lng:-7.60,name:'Casablanca, Morocco'},
];
const _MAJOR_AIRPORTS = [
  {lat:40.64,lng:-73.78,name:'JFK, New York'},{lat:33.94,lng:-118.41,name:'LAX, Los Angeles'},
  {lat:51.47,lng:-0.46,name:'Heathrow, London'},{lat:49.01,lng:2.55,name:'CDG, Paris'},
  {lat:25.25,lng:55.36,name:'DXB, Dubai'},{lat:1.36,lng:103.99,name:'Changi, Singapore'},
  {lat:35.55,lng:139.78,name:'Haneda, Tokyo'},{lat:22.31,lng:113.91,name:'HKG, Hong Kong'},
  {lat:50.03,lng:8.57,name:'FRA, Frankfurt'},{lat:52.31,lng:4.77,name:'AMS, Amsterdam'},
  {lat:41.98,lng:-87.91,name:'ORD, Chicago'},{lat:33.64,lng:-84.43,name:'ATL, Atlanta'},
  {lat:13.68,lng:100.75,name:'BKK, Bangkok'},{lat:40.08,lng:116.58,name:'PEK, Beijing'},
  {lat:37.46,lng:126.44,name:'ICN, Incheon'},{lat:-33.95,lng:151.18,name:'SYD, Sydney'},
  {lat:19.09,lng:72.87,name:'BOM, Mumbai'},{lat:-23.43,lng:-46.47,name:'GRU, Sao Paulo'},
  {lat:55.97,lng:37.41,name:'SVO, Moscow'},{lat:41.80,lng:12.25,name:'FCO, Rome'},
  {lat:32.90,lng:-97.04,name:'DFW, Dallas'},{lat:42.36,lng:-71.01,name:'BOS, Boston'},
  {lat:47.45,lng:-122.31,name:'SEA, Seattle'},{lat:39.86,lng:-104.67,name:'DEN, Denver'},
  {lat:25.80,lng:-80.29,name:'MIA, Miami'},{lat:29.99,lng:-95.34,name:'IAH, Houston'},
  {lat:38.95,lng:-77.46,name:'IAD, Washington Dulles'},{lat:36.08,lng:-115.15,name:'LAS, Las Vegas'},
  {lat:33.44,lng:-112.01,name:'PHX, Phoenix'},{lat:45.59,lng:-73.74,name:'YUL, Montreal'},
  {lat:43.68,lng:-79.63,name:'YYZ, Toronto'},{lat:49.19,lng:-123.18,name:'YVR, Vancouver'},
  {lat:19.43,lng:-99.07,name:'MEX, Mexico City'},{lat:40.47,lng:-3.57,name:'MAD, Madrid'},
  {lat:41.30,lng:2.08,name:'BCN, Barcelona'},{lat:45.63,lng:8.72,name:'MXP, Milan Malpensa'},
  {lat:37.94,lng:23.94,name:'ATH, Athens'},{lat:41.26,lng:28.74,name:'IST, Istanbul'},
  {lat:28.57,lng:77.10,name:'DEL, New Delhi'},{lat:12.99,lng:80.17,name:'MAA, Chennai'},
  {lat:31.14,lng:121.81,name:'PVG, Shanghai Pudong'},{lat:23.39,lng:113.30,name:'CAN, Guangzhou'},
  {lat:22.64,lng:113.81,name:'SZX, Shenzhen'},{lat:34.78,lng:135.44,name:'KIX, Osaka Kansai'},
  {lat:25.08,lng:121.23,name:'TPE, Taipei Taoyuan'},{lat:14.51,lng:121.02,name:'MNL, Manila'},
  {lat:5.98,lng:116.05,name:'BKI, Kota Kinabalu'},{lat:2.74,lng:101.70,name:'KUL, Kuala Lumpur'},
  {lat:-6.13,lng:106.66,name:'CGK, Jakarta'},{lat:21.22,lng:-97.86,name:'CUN, Cancun'},
  {lat:-34.82,lng:-58.54,name:'EZE, Buenos Aires'},{lat:-33.39,lng:-70.79,name:'SCL, Santiago'},
  {lat:-22.81,lng:-43.25,name:'GIG, Rio de Janeiro'},{lat:-1.32,lng:36.93,name:'NBO, Nairobi'},
  {lat:-26.14,lng:28.24,name:'JNB, Johannesburg'},{lat:30.12,lng:31.41,name:'CAI, Cairo'},
  {lat:36.69,lng:3.22,name:'ALG, Algiers'},{lat:33.93,lng:-6.57,name:'CMN, Casablanca'},
  {lat:25.32,lng:51.61,name:'DOH, Doha'},{lat:24.44,lng:54.65,name:'AUH, Abu Dhabi'},
  {lat:26.27,lng:50.64,name:'BAH, Bahrain'},{lat:29.23,lng:47.97,name:'KWI, Kuwait'},
];
const _FINANCIAL_CENTERS = [
  {lat:40.71,lng:-74.01,name:'Wall Street, New York'},{lat:51.51,lng:-0.08,name:'City of London'},
  {lat:22.28,lng:114.16,name:'Central, Hong Kong'},{lat:1.28,lng:103.85,name:'Raffles Place, Singapore'},
  {lat:35.68,lng:139.76,name:'Marunouchi, Tokyo'},{lat:47.37,lng:8.54,name:'Paradeplatz, Zurich'},
  {lat:50.11,lng:8.68,name:'Bankenviertel, Frankfurt'},{lat:31.23,lng:121.47,name:'Lujiazui, Shanghai'},
  {lat:25.21,lng:55.27,name:'DIFC, Dubai'},{lat:48.87,lng:2.34,name:'La Defense, Paris'},
  {lat:-33.87,lng:151.21,name:'Martin Place, Sydney'},{lat:43.65,lng:-79.38,name:'Bay Street, Toronto'},
  {lat:19.08,lng:72.88,name:'Dalal Street, Mumbai'},{lat:37.57,lng:126.98,name:'Yeouido, Seoul'},
  {lat:-23.55,lng:-46.64,name:'Faria Lima, Sao Paulo'},{lat:52.37,lng:4.90,name:'Zuidas, Amsterdam'},
  {lat:49.61,lng:6.13,name:'Kirchberg, Luxembourg'},{lat:55.68,lng:12.57,name:'Copenhagen Finance'},
  {lat:53.35,lng:-6.26,name:'IFSC, Dublin'},{lat:59.33,lng:18.07,name:'Stureplan, Stockholm'},
  {lat:60.17,lng:24.94,name:'Helsinki Finance'},{lat:46.20,lng:6.14,name:'Geneva Private Banking'},
  {lat:44.43,lng:26.10,name:'Bucharest Finance'},{lat:41.01,lng:28.98,name:'Levent, Istanbul'},
  {lat:30.04,lng:31.24,name:'Smart Village, Cairo'},{lat:39.91,lng:116.39,name:'Financial St, Beijing'},
  {lat:-34.60,lng:-58.38,name:'Microcentro, Buenos Aires'},{lat:19.43,lng:-99.17,name:'Reforma, Mexico City'},
  {lat:-1.29,lng:36.82,name:'Upper Hill, Nairobi'},{lat:-26.20,lng:28.04,name:'Sandton, Johannesburg'},
];
const _MINING_SITES = [
  {lat:-22.34,lng:-68.93,name:'Escondida, Chile (copper)'},{lat:-29.78,lng:137.77,name:'Olympic Dam, AU (uranium/copper)'},
  {lat:-21.27,lng:-70.04,name:'Collahuasi, Chile (copper)'},{lat:37.13,lng:-113.55,name:'Iron County, US (iron)'},
  {lat:62.45,lng:114.37,name:'Diavik, Canada (diamond)'},{lat:-6.02,lng:106.05,name:'Grasberg, Indonesia (gold/copper)'},
  {lat:-20.65,lng:118.55,name:'Pilbara, AU (iron)'},{lat:47.30,lng:87.90,name:'Altay, China (rare earth)'},
  {lat:40.65,lng:109.97,name:'Baotou, China (rare earth)'},{lat:-26.20,lng:27.95,name:'Witwatersrand, SA (gold)'},
  {lat:56.30,lng:60.61,name:'Ural Mountains, RU (nickel)'},{lat:69.35,lng:88.21,name:'Norilsk, RU (Ni/Pd)'},
  {lat:-15.45,lng:28.28,name:'Lumwana, Zambia (copper)'},{lat:-12.04,lng:26.40,name:'Konkola, Zambia (copper)'},
  {lat:60.03,lng:-112.47,name:'Athabasca, Canada (oil sands)'},{lat:-9.42,lng:147.12,name:'Ok Tedi, PNG (gold/copper)'},
  {lat:51.46,lng:59.00,name:'Gai, Russia (copper)'},{lat:7.35,lng:-2.33,name:'Obuasi, Ghana (gold)'},
  {lat:11.43,lng:-12.28,name:'Simandou, Guinea (iron)'},{lat:-6.80,lng:29.25,name:'Kipushi, DRC (zinc/copper)'},
  {lat:-10.73,lng:25.47,name:'Kamoto, DRC (cobalt/copper)'},{lat:-4.32,lng:28.63,name:'Tenke Fungurume, DRC (cobalt)'},
  {lat:-22.50,lng:-68.05,name:'Chuquicamata, Chile (copper)'},{lat:-26.85,lng:-65.23,name:'Bajo de la Alumbrera, AR'},
  {lat:-18.50,lng:-69.05,name:'Cerro Verde, Peru (copper)'},{lat:-14.92,lng:-75.13,name:'Marcona, Peru (iron)'},
  {lat:46.88,lng:-71.25,name:'Lac-Megantic, Canada (lithium)'},{lat:36.51,lng:-117.08,name:'Boron, US (lithium/boron)'},
  {lat:-22.83,lng:-68.28,name:'SQM Atacama, Chile (lithium)'},{lat:-20.55,lng:-68.64,name:'Uyuni, Bolivia (lithium)'},
  {lat:67.86,lng:20.22,name:'Kiruna, Sweden (iron)'},{lat:64.17,lng:18.87,name:'Boliden, Sweden (base metals)'},
  {lat:42.07,lng:43.57,name:'Chiatura, Georgia (manganese)'},{lat:68.65,lng:21.39,name:'Kevitsa, Finland (nickel)'},
  {lat:-21.17,lng:48.33,name:'Ambatovy, Madagascar (nickel)'},{lat:-3.20,lng:116.00,name:'Batu Hijau, Indonesia (copper)'},
  {lat:43.23,lng:76.95,name:'Kounrad, Kazakhstan (copper)'},{lat:2.00,lng:102.25,name:'Pahang, Malaysia (tin)'},
  {lat:-15.93,lng:-68.70,name:'San Cristobal, Bolivia (silver)'},{lat:19.50,lng:-103.50,name:'Penasquito, Mexico (gold)'},
];
const _TECH_HQS = [
  {lat:37.39,lng:-122.08,name:'Google, Mountain View'},{lat:37.48,lng:-122.14,name:'Meta, Menlo Park'},
  {lat:37.33,lng:-122.01,name:'Apple, Cupertino'},{lat:47.64,lng:-122.13,name:'Microsoft, Redmond'},
  {lat:47.62,lng:-122.34,name:'Amazon, Seattle'},{lat:37.79,lng:-122.39,name:'Salesforce, San Francisco'},
  {lat:37.56,lng:-122.27,name:'Tesla, Palo Alto'},{lat:30.27,lng:-97.74,name:'Tesla GF, Austin'},
  {lat:37.42,lng:-122.17,name:'NVIDIA, Santa Clara'},{lat:37.40,lng:-121.96,name:'Intel, Santa Clara'},
  {lat:25.04,lng:121.57,name:'TSMC, Hsinchu'},{lat:37.57,lng:126.98,name:'Samsung, Seoul'},
  {lat:35.68,lng:139.69,name:'Sony, Tokyo'},{lat:22.28,lng:114.17,name:'Tencent, Shenzhen'},
  {lat:30.27,lng:120.15,name:'Alibaba, Hangzhou'},{lat:39.98,lng:116.31,name:'ByteDance, Beijing'},
  {lat:51.50,lng:-0.08,name:'DeepMind, London'},{lat:48.86,lng:2.35,name:'Mistral AI, Paris'},
  {lat:52.52,lng:13.41,name:'SAP, Berlin'},{lat:12.97,lng:77.64,name:'Infosys, Bangalore'},
];
const _CLOUD_REGIONS = [
  // AWS Regions
  {lat:39.04,lng:-77.49,name:'AWS us-east-1 (Virginia)'},{lat:41.88,lng:-87.63,name:'AWS us-east-2 (Ohio)'},
  {lat:34.05,lng:-118.24,name:'AWS us-west-1 (N. California)'},{lat:45.59,lng:-122.60,name:'AWS us-west-2 (Oregon)'},
  {lat:45.50,lng:-73.57,name:'AWS ca-central-1 (Montreal)'},{lat:53.35,lng:-6.26,name:'AWS eu-west-1 (Ireland)'},
  {lat:51.50,lng:-0.12,name:'AWS eu-west-2 (London)'},{lat:48.86,lng:2.35,name:'AWS eu-west-3 (Paris)'},
  {lat:50.11,lng:8.68,name:'AWS eu-central-1 (Frankfurt)'},{lat:59.33,lng:18.07,name:'AWS eu-north-1 (Stockholm)'},
  {lat:45.46,lng:9.19,name:'AWS eu-south-1 (Milan)'},{lat:35.68,lng:139.69,name:'AWS ap-northeast-1 (Tokyo)'},
  {lat:37.57,lng:126.98,name:'AWS ap-northeast-2 (Seoul)'},{lat:34.69,lng:135.50,name:'AWS ap-northeast-3 (Osaka)'},
  {lat:1.35,lng:103.82,name:'AWS ap-southeast-1 (Singapore)'},{lat:-33.87,lng:151.21,name:'AWS ap-southeast-2 (Sydney)'},
  {lat:19.08,lng:72.88,name:'AWS ap-south-1 (Mumbai)'},{lat:-23.55,lng:-46.63,name:'AWS sa-east-1 (Sao Paulo)'},
  {lat:25.20,lng:55.27,name:'AWS me-south-1 (Bahrain)'},{lat:-1.29,lng:36.82,name:'AWS af-south-1 (Cape Town)'},
  {lat:22.32,lng:114.17,name:'AWS ap-east-1 (Hong Kong)'},{lat:-6.21,lng:106.85,name:'AWS ap-southeast-3 (Jakarta)'},
  // Azure Regions
  {lat:37.37,lng:-121.92,name:'Azure West US (California)'},{lat:47.61,lng:-122.33,name:'Azure West US 2 (WA)'},
  {lat:39.04,lng:-77.49,name:'Azure East US (Virginia)'},{lat:41.88,lng:-87.63,name:'Azure North Central US'},
  {lat:32.78,lng:-96.80,name:'Azure South Central US (TX)'},{lat:43.65,lng:-79.38,name:'Azure Canada Central'},
  {lat:52.37,lng:4.90,name:'Azure West Europe (NL)'},{lat:53.35,lng:-6.26,name:'Azure North Europe (IE)'},
  {lat:50.11,lng:8.68,name:'Azure Germany West Central'},{lat:51.50,lng:-0.12,name:'Azure UK South'},
  {lat:48.86,lng:2.35,name:'Azure France Central'},{lat:47.37,lng:8.54,name:'Azure Switzerland North'},
  {lat:59.33,lng:18.07,name:'Azure Sweden Central'},{lat:52.23,lng:21.01,name:'Azure Poland Central'},
  {lat:35.68,lng:139.69,name:'Azure Japan East'},{lat:37.57,lng:126.98,name:'Azure Korea Central'},
  {lat:1.35,lng:103.82,name:'Azure Southeast Asia'},{lat:-33.87,lng:151.21,name:'Azure Australia East'},
  {lat:20.08,lng:77.0,name:'Azure Central India'},{lat:25.20,lng:55.27,name:'Azure UAE North'},
  {lat:-26.20,lng:28.04,name:'Azure South Africa North'},{lat:-23.55,lng:-46.63,name:'Azure Brazil South'},
  {lat:24.71,lng:46.67,name:'Azure Saudi Arabia'},{lat:21.31,lng:-157.86,name:'Azure Hawaii (DoD)'},
  // GCP Regions
  {lat:34.05,lng:-118.24,name:'GCP us-west1 (Oregon)'},{lat:36.17,lng:-115.14,name:'GCP us-west4 (Las Vegas)'},
  {lat:33.45,lng:-112.07,name:'GCP us-west3 (Salt Lake)'},{lat:39.04,lng:-77.49,name:'GCP us-east4 (Virginia)'},
  {lat:33.75,lng:-84.39,name:'GCP us-south1 (Atlanta)'},{lat:45.50,lng:-73.57,name:'GCP northamerica-ne1 (Montreal)'},
  {lat:51.50,lng:-0.12,name:'GCP europe-west2 (London)'},{lat:50.11,lng:8.68,name:'GCP europe-west3 (Frankfurt)'},
  {lat:52.37,lng:4.90,name:'GCP europe-west4 (Netherlands)'},{lat:47.37,lng:8.54,name:'GCP europe-west6 (Zurich)'},
  {lat:35.68,lng:139.69,name:'GCP asia-northeast1 (Tokyo)'},{lat:1.35,lng:103.82,name:'GCP asia-southeast1 (Singapore)'},
  {lat:-33.87,lng:151.21,name:'GCP australia-southeast1 (Sydney)'},{lat:19.08,lng:72.88,name:'GCP asia-south1 (Mumbai)'},
  {lat:-23.55,lng:-46.63,name:'GCP southamerica-east1 (Sao Paulo)'},{lat:25.20,lng:55.27,name:'GCP me-central1 (Doha)'},
  {lat:32.07,lng:34.78,name:'GCP me-west1 (Tel Aviv)'},
];
const _STOCK_EXCHANGES = [
  {lat:40.71,lng:-74.01,name:'NYSE, New York (largest)'},{lat:40.72,lng:-73.99,name:'NASDAQ, New York'},
  {lat:41.88,lng:-87.63,name:'CBOE, Chicago'},{lat:41.88,lng:-87.64,name:'CME Group, Chicago'},
  {lat:51.51,lng:-0.09,name:'LSE, London'},{lat:48.87,lng:2.34,name:'Euronext, Paris'},
  {lat:50.11,lng:8.68,name:'Deutsche Borse, Frankfurt'},{lat:47.37,lng:8.54,name:'SIX, Zurich'},
  {lat:40.42,lng:-3.70,name:'BME, Madrid'},{lat:45.46,lng:9.19,name:'Borsa Italiana, Milan'},
  {lat:55.68,lng:12.57,name:'NASDAQ Nordic, Copenhagen'},{lat:59.33,lng:18.07,name:'NASDAQ Stockholm'},
  {lat:60.17,lng:24.94,name:'NASDAQ Helsinki'},{lat:52.23,lng:21.01,name:'GPW, Warsaw'},
  {lat:48.21,lng:16.37,name:'Wiener Borse, Vienna'},{lat:41.01,lng:28.98,name:'Borsa Istanbul'},
  {lat:55.75,lng:37.62,name:'MOEX, Moscow'},{lat:35.68,lng:139.77,name:'JPX/TSE, Tokyo'},
  {lat:34.69,lng:135.50,name:'OSE, Osaka'},{lat:22.28,lng:114.16,name:'HKEX, Hong Kong'},
  {lat:31.23,lng:121.47,name:'SSE, Shanghai'},{lat:22.54,lng:114.07,name:'SZSE, Shenzhen'},
  {lat:37.57,lng:126.98,name:'KRX, Seoul'},{lat:25.04,lng:121.57,name:'TWSE, Taipei'},
  {lat:1.28,lng:103.85,name:'SGX, Singapore'},{lat:19.08,lng:72.88,name:'BSE, Mumbai'},
  {lat:19.07,lng:72.87,name:'NSE, Mumbai'},{lat:13.76,lng:100.50,name:'SET, Bangkok'},
  {lat:3.14,lng:101.69,name:'Bursa Malaysia, KL'},{lat:-6.21,lng:106.85,name:'IDX, Jakarta'},
  {lat:14.60,lng:120.98,name:'PSE, Manila'},{lat:21.03,lng:105.85,name:'HOSE, Ho Chi Minh'},
  {lat:25.20,lng:55.27,name:'DFM, Dubai'},{lat:24.45,lng:54.65,name:'ADX, Abu Dhabi'},
  {lat:24.71,lng:46.67,name:'Tadawul, Riyadh'},{lat:31.95,lng:35.93,name:'ASE, Amman'},
  {lat:32.07,lng:34.78,name:'TASE, Tel Aviv'},{lat:30.04,lng:31.24,name:'EGX, Cairo'},
  {lat:-33.93,lng:18.42,name:'JSE, Johannesburg'},{lat:6.45,lng:3.39,name:'NGX, Lagos'},
  {lat:-1.29,lng:36.82,name:'NSE, Nairobi'},{lat:5.56,lng:-0.19,name:'GSE, Accra'},
  {lat:43.65,lng:-79.38,name:'TSX, Toronto'},{lat:19.43,lng:-99.13,name:'BMV, Mexico City'},
  {lat:-23.55,lng:-46.63,name:'B3, Sao Paulo'},{lat:-34.60,lng:-58.38,name:'BCBA, Buenos Aires'},
  {lat:-33.45,lng:-70.67,name:'BCS, Santiago'},{lat:4.60,lng:-74.08,name:'BVC, Bogota'},
  {lat:-12.05,lng:-77.04,name:'BVL, Lima'},{lat:-33.87,lng:151.21,name:'ASX, Sydney'},
  {lat:-36.85,lng:174.76,name:'NZX, Auckland'},
];
const _COMMODITY_HUBS = [
  // Oil & Gas Trading
  {lat:29.76,lng:-95.37,name:'Houston TX (Oil & Gas Capital)'},{lat:51.50,lng:-0.12,name:'London ICE (Brent)'},
  {lat:40.71,lng:-74.01,name:'NYMEX, New York (WTI)'},{lat:25.20,lng:55.27,name:'DME, Dubai (Oman Crude)'},
  {lat:1.35,lng:103.82,name:'Singapore (Asia Oil Hub)'},{lat:51.92,lng:4.48,name:'Rotterdam (NW Europe Oil)'},
  // Metals
  {lat:51.51,lng:-0.08,name:'LME, London (Base Metals)'},{lat:41.88,lng:-87.63,name:'COMEX, Chicago (Gold/Silver)'},
  {lat:31.23,lng:121.47,name:'SHFE, Shanghai (Metals)'},{lat:35.68,lng:139.69,name:'TOCOM, Tokyo (Platinum)'},
  {lat:-26.20,lng:28.04,name:'Johannesburg (Gold Mining)'},{lat:-30.03,lng:-51.23,name:'Porto Alegre (Iron Ore)'},
  {lat:22.28,lng:114.17,name:'Hong Kong (Gold Market)'},
  // Agriculture
  {lat:41.88,lng:-87.64,name:'CBOT, Chicago (Grains)'},{lat:-23.55,lng:-46.63,name:'B3, Sao Paulo (Coffee/Sugar)'},
  {lat:3.14,lng:101.69,name:'MDEX, KL (Palm Oil)'},{lat:51.50,lng:-0.12,name:'LIFFE, London (Cocoa/Coffee)'},
  {lat:19.08,lng:72.88,name:'NCDEX, Mumbai (Spices/Cotton)'},{lat:40.71,lng:-74.01,name:'ICE NY (Cotton/Sugar)'},
  {lat:0.31,lng:32.58,name:'Kampala (E. Africa Coffee)'},{lat:5.56,lng:-0.19,name:'Accra (Cocoa)'},
  {lat:7.49,lng:3.60,name:'Ibadan (Cocoa Processing)'},{lat:-4.27,lng:15.28,name:'Kinshasa (Cobalt Trade)'},
  // LNG & Energy
  {lat:35.45,lng:139.65,name:'JKM, Tokyo (Asia LNG Benchmark)'},{lat:51.50,lng:3.60,name:'TTF, Rotterdam (EU Gas)'},
  {lat:29.76,lng:-95.37,name:'Henry Hub, Louisiana (US Gas)'},{lat:25.29,lng:51.53,name:'Ras Laffan (LNG Export)'},
  {lat:56.34,lng:2.75,name:'NBP, UK (Natural Gas)'},{lat:47.87,lng:16.25,name:'CEGH, Austria (EU Gas)'},
  // Diamond & Precious Stones
  {lat:51.22,lng:4.40,name:'Antwerp (Diamond Hub)'},{lat:19.08,lng:72.88,name:'Surat (Diamond Cutting)'},
  {lat:32.07,lng:34.78,name:'Ramat Gan (Diamond Exchange)'},{lat:40.76,lng:-73.98,name:'47th St, NYC (Diamonds)'},
  // Rare Earths & Specialty
  {lat:40.65,lng:109.97,name:'Baotou (Rare Earth Capital)'},{lat:-12.04,lng:26.40,name:'Copper Belt (DRC/Zambia)'},
  {lat:69.35,lng:88.21,name:'Norilsk (Nickel/Palladium)'},{lat:-20.65,lng:118.55,name:'Pilbara (Iron Ore)'},
];
const _STARTUP_HUBS = [
  {lat:37.39,lng:-122.08,name:'Silicon Valley, US'},{lat:40.75,lng:-73.98,name:'NYC Tech, US'},
  {lat:42.36,lng:-71.06,name:'Boston/Cambridge, US'},{lat:47.61,lng:-122.33,name:'Seattle, US'},
  {lat:30.27,lng:-97.74,name:'Austin TX, US'},{lat:25.76,lng:-80.19,name:'Miami, US'},
  {lat:51.52,lng:-0.08,name:'Silicon Roundabout, London'},{lat:52.52,lng:13.41,name:'Berlin, Germany'},
  {lat:48.86,lng:2.35,name:'Station F, Paris'},{lat:59.33,lng:18.07,name:'Stockholm, Sweden'},
  {lat:52.37,lng:4.90,name:'Amsterdam, Netherlands'},{lat:55.68,lng:12.57,name:'Copenhagen, Denmark'},
  {lat:60.17,lng:24.94,name:'Helsinki/Slush, Finland'},{lat:41.39,lng:2.17,name:'Barcelona, Spain'},
  {lat:53.35,lng:-6.26,name:'Dublin, Ireland'},{lat:47.37,lng:8.54,name:'Crypto Valley, Zurich'},
  {lat:32.07,lng:34.78,name:'Tel Aviv, Israel'},{lat:12.97,lng:77.59,name:'Bangalore, India'},
  {lat:19.08,lng:72.88,name:'Mumbai, India'},{lat:1.30,lng:103.85,name:'Singapore'},
  {lat:22.28,lng:114.17,name:'Hong Kong/Shenzhen'},{lat:31.23,lng:121.47,name:'Shanghai, China'},
  {lat:39.91,lng:116.39,name:'Zhongguancun, Beijing'},{lat:37.57,lng:126.98,name:'Gangnam, Seoul'},
  {lat:35.68,lng:139.69,name:'Shibuya, Tokyo'},{lat:-33.87,lng:151.21,name:'Sydney, Australia'},
  {lat:43.65,lng:-79.38,name:'MaRS, Toronto'},{lat:-23.55,lng:-46.63,name:'Sao Paulo, Brazil'},
  {lat:6.52,lng:3.38,name:'Yaba/Lagos, Nigeria'},{lat:-1.29,lng:36.82,name:'iHub, Nairobi'},
  {lat:-33.93,lng:18.42,name:'Cape Town, South Africa'},{lat:25.20,lng:55.27,name:'Dubai/DIFC, UAE'},
];
const _GPS_JAMMING_ZONES = [
  // Known chronic GPS interference zones (sourced from GPSJAM.org / OPSGROUP reports)
  {lat:34.70,lng:33.05,name:'Eastern Mediterranean (chronic)'},{lat:35.00,lng:38.00,name:'Syria/NE Med conflict zone'},
  {lat:33.90,lng:35.50,name:'Beirut/Lebanon'},{lat:31.50,lng:34.50,name:'Gaza/Southern Israel'},
  {lat:32.90,lng:35.30,name:'Northern Israel/Golan'},{lat:36.20,lng:37.15,name:'Aleppo, Syria'},
  {lat:33.30,lng:44.40,name:'Baghdad, Iraq'},{lat:35.70,lng:51.40,name:'Tehran, Iran'},
  {lat:59.90,lng:30.30,name:'St Petersburg, Russia'},{lat:55.75,lng:37.62,name:'Moscow, Russia'},
  {lat:54.70,lng:20.50,name:'Kaliningrad, Russia'},{lat:69.00,lng:33.00,name:'Kola Peninsula, Russia'},
  {lat:44.60,lng:33.50,name:'Crimea, Ukraine'},{lat:48.50,lng:37.50,name:'Donbas, Ukraine'},
  {lat:41.00,lng:29.00,name:'Istanbul/Bosphorus'},{lat:39.93,lng:32.86,name:'Ankara, Turkey'},
  {lat:36.90,lng:30.70,name:'Antalya, Turkey'},{lat:25.25,lng:55.36,name:'Dubai, UAE'},
  {lat:26.20,lng:50.55,name:'Bahrain/Persian Gulf'},{lat:15.40,lng:44.20,name:'Sana\'a, Yemen'},
  {lat:2.05,lng:45.32,name:'Mogadishu, Somalia'},{lat:11.55,lng:43.15,name:'Djibouti/Gulf of Aden'},
  {lat:39.03,lng:125.75,name:'Pyongyang, DPRK'},{lat:22.30,lng:114.17,name:'South China Sea (variable)'},
  {lat:8.50,lng:115.00,name:'Indonesia/Bali Strait (variable)'},{lat:34.05,lng:-118.24,name:'LA Basin (test/spoof events)'},
];
const _TRADE_ROUTES = [
  // Major shipping lane waypoints (simplified routes)
  {lat:31.00,lng:121.00,name:'Shanghai-Singapore lane'},{lat:10.00,lng:108.00,name:'South China Sea transit'},
  {lat:1.30,lng:104.00,name:'Singapore Strait'},{lat:5.00,lng:80.00,name:'Indian Ocean crossroads'},
  {lat:12.50,lng:53.00,name:'Arabian Sea/Gulf of Aden'},{lat:13.00,lng:42.50,name:'Red Sea/Bab el-Mandeb'},
  {lat:29.00,lng:33.00,name:'Suez approach'},{lat:35.50,lng:24.00,name:'Central Mediterranean'},
  {lat:36.00,lng:-5.50,name:'Gibraltar transit'},{lat:48.00,lng:-5.00,name:'English Channel/Biscay'},
  {lat:51.00,lng:2.00,name:'Dover Strait'},{lat:57.00,lng:1.00,name:'North Sea corridor'},
  {lat:60.00,lng:-15.00,name:'GIUK Gap (Atlantic chokepoint)'},{lat:40.00,lng:-50.00,name:'Mid-Atlantic route'},
  {lat:25.00,lng:-80.00,name:'Florida Straits'},{lat:10.00,lng:-80.00,name:'Panama approach'},
  {lat:-5.00,lng:-35.00,name:'South Atlantic crossing'},{lat:-34.00,lng:18.50,name:'Cape route'},
  {lat:-35.00,lng:115.00,name:'Southern Indian Ocean'},{lat:-42.00,lng:147.00,name:'Bass Strait, Australia'},
  {lat:35.00,lng:140.00,name:'Pacific approach Japan'},{lat:50.00,lng:-130.00,name:'North Pacific route'},
  {lat:20.00,lng:-155.00,name:'Hawaii mid-Pacific waypoint'},{lat:-10.00,lng:-170.00,name:'South Pacific route'},
];
const _ACCELERATORS = [
  {lat:37.39,lng:-122.08,name:'Y Combinator, Mountain View'},{lat:37.78,lng:-122.41,name:'500 Global, San Francisco'},
  {lat:40.74,lng:-73.99,name:'Techstars NYC'},{lat:42.36,lng:-71.06,name:'MassChallenge, Boston'},
  {lat:47.61,lng:-122.33,name:'Techstars Seattle'},{lat:30.27,lng:-97.74,name:'Capital Factory, Austin'},
  {lat:34.05,lng:-118.24,name:'Amplify LA'},{lat:51.52,lng:-0.08,name:'Seedcamp, London'},
  {lat:52.52,lng:13.41,name:'Techstars Berlin'},{lat:48.86,lng:2.35,name:'Station F / Techstars Paris'},
  {lat:55.68,lng:12.57,name:'Accelerace, Copenhagen'},{lat:52.37,lng:4.90,name:'Rockstart, Amsterdam'},
  {lat:41.39,lng:2.17,name:'Startupbootcamp, Barcelona'},{lat:53.35,lng:-6.26,name:'NDRC, Dublin'},
  {lat:32.07,lng:34.78,name:'8200 EISP, Tel Aviv'},{lat:1.30,lng:103.85,name:'JFDI, Singapore'},
  {lat:12.97,lng:77.59,name:'T-Hub, Bangalore'},{lat:22.28,lng:114.17,name:'Cyberport, Hong Kong'},
  {lat:35.68,lng:139.69,name:'Plug and Play, Tokyo'},{lat:37.57,lng:126.98,name:'SparkLabs, Seoul'},
  {lat:-33.87,lng:151.21,name:'Startmate, Sydney'},{lat:-23.55,lng:-46.63,name:'ACE, Sao Paulo'},
  {lat:6.52,lng:3.38,name:'CcHUB, Lagos'},{lat:-1.29,lng:36.82,name:'Nairobi Garage, Kenya'},
  {lat:25.20,lng:55.27,name:'in5, Dubai'},{lat:43.65,lng:-79.38,name:'Creative Destruction Lab, Toronto'},
];

const _REFUGEE_CAMPS = [
  {lat:29.87,lng:36.08,name:'Zaatari Camp, Jordan'},{lat:31.83,lng:35.88,name:'Azraq Camp, Jordan'},
  {lat:37.05,lng:42.35,name:'Domiz Camp, Iraq'},{lat:4.32,lng:31.62,name:'Bidi Bidi, Uganda'},
  {lat:9.15,lng:42.79,name:'Dadaab Complex, Kenya'},{lat:0.35,lng:34.20,name:'Kakuma Camp, Kenya'},
  {lat:8.95,lng:38.73,name:'Shire Camps, Ethiopia'},{lat:20.46,lng:92.98,name:'Cox\'s Bazar, Bangladesh'},
  {lat:15.60,lng:32.50,name:'Khartoum IDP, Sudan'},{lat:3.58,lng:32.30,name:'Adjumani, Uganda'},
  {lat:-3.38,lng:29.36,name:'Nyarugusu, Tanzania'},{lat:-13.98,lng:33.78,name:'Dzaleka, Malawi'},
  {lat:34.40,lng:36.35,name:'Bekaa Valley, Lebanon'},{lat:33.52,lng:36.30,name:'Damascus suburbs, Syria'},
  {lat:36.20,lng:36.15,name:'Hatay camps, Turkey'},{lat:37.76,lng:30.29,name:'Afyonkarahisar, Turkey'},
  {lat:6.43,lng:2.37,name:'Seme/Lagos, Nigeria (IDP)'},{lat:11.85,lng:13.16,name:'Maiduguri IDP, Nigeria'},
  {lat:-4.32,lng:15.31,name:'Kinshasa IDP, DRC'},{lat:15.55,lng:44.20,name:'Sana\'a IDP, Yemen'},
];
const _UN_MISSIONS = [
  {lat:4.85,lng:31.61,name:'UNMISS (South Sudan)'},{lat:-4.32,lng:15.31,name:'MONUSCO (DRC)'},
  {lat:12.65,lng:-8.00,name:'MINUSMA (Mali)'},{lat:6.30,lng:-10.80,name:'UNSMIL (Libya)'},
  {lat:33.89,lng:35.50,name:'UNIFIL (Lebanon)'},{lat:34.72,lng:36.80,name:'UNDOF (Golan)'},
  {lat:35.17,lng:33.36,name:'UNFICYP (Cyprus)'},{lat:34.53,lng:69.17,name:'UNAMA (Afghanistan)'},
  {lat:2.06,lng:45.34,name:'UNSOM (Somalia)'},{lat:18.54,lng:-72.34,name:'BINUH (Haiti)'},
  {lat:42.44,lng:19.26,name:'UNMIK (Kosovo)'},{lat:19.76,lng:96.13,name:'UN Myanmar'},
  {lat:-8.56,lng:125.57,name:'UNMIT (Timor-Leste legacy)'},{lat:27.71,lng:85.32,name:'UNMIN (Nepal legacy)'},
  {lat:4.04,lng:9.70,name:'UNOCA (Central Africa)'},{lat:15.60,lng:32.53,name:'UNITAMS (Sudan)'},
];
const _INTERNET_EXCHANGES = [
  {lat:39.04,lng:-77.49,name:'Equinix Ashburn IX'},{lat:50.11,lng:8.68,name:'DE-CIX Frankfurt (#1)'},
  {lat:52.37,lng:4.90,name:'AMS-IX Amsterdam (#2)'},{lat:51.50,lng:-0.12,name:'LINX London'},
  {lat:48.86,lng:2.35,name:'France-IX Paris'},{lat:45.46,lng:9.19,name:'MIX Milan'},
  {lat:40.42,lng:-3.70,name:'ESPANIX Madrid'},{lat:59.33,lng:18.07,name:'Netnod Stockholm'},
  {lat:60.17,lng:24.94,name:'FICIX Helsinki'},{lat:55.68,lng:12.57,name:'DIX Copenhagen'},
  {lat:52.23,lng:21.01,name:'PLIX Warsaw'},{lat:41.01,lng:28.98,name:'IXTR Istanbul'},
  {lat:55.75,lng:37.62,name:'MSK-IX Moscow'},{lat:35.68,lng:139.69,name:'JPIX Tokyo'},
  {lat:22.28,lng:114.17,name:'HKIX Hong Kong'},{lat:1.35,lng:103.82,name:'SGIX Singapore'},
  {lat:37.57,lng:126.98,name:'KINX Seoul'},{lat:19.08,lng:72.88,name:'NIXI Mumbai'},
  {lat:-23.55,lng:-46.63,name:'IX.br Sao Paulo'},{lat:6.45,lng:3.39,name:'IXPN Lagos'},
  {lat:-1.29,lng:36.82,name:'KIXP Nairobi'},{lat:-33.93,lng:18.42,name:'NAPAfrica Johannesburg'},
  {lat:-33.87,lng:151.21,name:'IX Australia Sydney'},{lat:40.71,lng:-74.01,name:'NYIIX New York'},
  {lat:41.88,lng:-87.63,name:'CHI-IX Chicago'},{lat:47.61,lng:-122.33,name:'SIX Seattle'},
  {lat:34.05,lng:-118.24,name:'LAIIX Los Angeles'},{lat:25.76,lng:-80.19,name:'FLIIX Miami'},
];
const _EMBASSIES_DC = [
  // Major embassy clusters (Washington DC + key diplomatic hubs)
  {lat:38.91,lng:-77.05,name:'Embassy Row, Washington DC'},{lat:46.23,lng:6.14,name:'UN/Palais, Geneva'},
  {lat:40.75,lng:-73.97,name:'UN HQ, New York'},{lat:48.21,lng:16.37,name:'UN/IAEA, Vienna'},
  {lat:52.52,lng:13.38,name:'Embassy Quarter, Berlin'},{lat:51.50,lng:-0.18,name:'Embassy Row, London'},
  {lat:48.86,lng:2.31,name:'Embassy Quarter, Paris'},{lat:55.75,lng:37.60,name:'Embassy Row, Moscow'},
  {lat:39.91,lng:116.43,name:'Embassy District, Beijing'},{lat:35.67,lng:139.74,name:'Embassy Area, Tokyo'},
  {lat:-38.90,lng:-77.04,name:'OAS HQ, Washington DC'},{lat:50.84,lng:4.38,name:'EU/NATO, Brussels'},
  {lat:47.55,lng:7.59,name:'BIS, Basel'},{lat:43.77,lng:11.25,name:'Embassy Quarter, Rome'},
];

const _DESALINATION_PLANTS = [
  {lat:26.10,lng:50.21,name:'Ras Al Khair, Saudi (largest)'},{lat:24.45,lng:54.65,name:'Taweelah, UAE'},
  {lat:25.20,lng:55.15,name:'Jebel Ali, Dubai'},{lat:32.07,lng:34.78,name:'Sorek, Israel'},
  {lat:31.50,lng:34.45,name:'Ashkelon, Israel'},{lat:36.80,lng:10.18,name:'Sfax, Tunisia'},
  {lat:33.30,lng:-117.30,name:'Carlsbad, California'},{lat:-33.87,lng:151.21,name:'Sydney Desalination, AU'},
  {lat:-31.95,lng:115.86,name:'Perth Desal, Australia'},{lat:37.80,lng:-1.28,name:'Torrevieja, Spain'},
  {lat:36.70,lng:-4.40,name:'Malaga, Spain'},{lat:-33.93,lng:18.42,name:'Cape Town (emergency)'},
  {lat:1.35,lng:103.82,name:'Tuas, Singapore'},{lat:25.29,lng:51.53,name:'Ras Abu Fontas, Qatar'},
  {lat:23.62,lng:58.55,name:'Barka, Oman'},{lat:29.23,lng:47.97,name:'Doha, Kuwait'},
  {lat:13.08,lng:80.27,name:'Minjur, Chennai, India'},{lat:30.04,lng:31.24,name:'El Alamein, Egypt'},
];
const _WEATHER_STATIONS = [
  // WMO Global Observing System key stations
  {lat:90.00,lng:0.00,name:'North Pole Drifting Station'},{lat:-89.98,lng:139.27,name:'Amundsen-Scott, South Pole'},
  {lat:71.32,lng:-156.61,name:'Utqiagvik/Barrow, AK'},{lat:78.25,lng:15.47,name:'Ny-Alesund, Svalbard'},
  {lat:-77.85,lng:166.67,name:'McMurdo, Antarctica'},{lat:21.32,lng:-157.84,name:'Mauna Loa, Hawaii'},
  {lat:51.97,lng:-10.25,name:'Valentia, Ireland'},{lat:46.55,lng:11.43,name:'Bolzano, Alps'},
  {lat:-14.25,lng:-170.68,name:'Pago Pago, Samoa'},{lat:0.00,lng:0.00,name:'PIRATA Buoy, Equatorial Atlantic'},
  {lat:-34.58,lng:-58.48,name:'Buenos Aires WMO'},{lat:35.68,lng:139.77,name:'Tokyo WMO'},
  {lat:55.75,lng:37.62,name:'Moscow WMO'},{lat:1.35,lng:103.82,name:'Singapore WMO'},
  {lat:-1.29,lng:36.82,name:'Nairobi WMO'},{lat:30.04,lng:31.24,name:'Cairo WMO'},
  {lat:-22.91,lng:-43.17,name:'Rio de Janeiro WMO'},{lat:39.91,lng:116.39,name:'Beijing WMO'},
  {lat:28.61,lng:77.21,name:'New Delhi WMO'},{lat:-33.87,lng:151.21,name:'Sydney WMO'},
];
const _SPACE_TRACKING = [
  // Space surveillance / tracking stations
  {lat:39.99,lng:-104.85,name:'Buckley SDA, Colorado'},{lat:33.87,lng:-117.99,name:'Vandenberg Tracking, CA'},
  {lat:71.39,lng:-156.47,name:'Clear SFS, Alaska'},{lat:28.49,lng:-80.58,name:'Cape Canaveral Tracking'},
  {lat:36.25,lng:-5.38,name:'RAF Fylingdales (relay)'},{lat:56.13,lng:-3.22,name:'RAF Fylingdales, UK'},
  {lat:-31.87,lng:133.73,name:'Woomera SSA, Australia'},{lat:-35.40,lng:148.98,name:'Canberra DSN'},
  {lat:40.43,lng:-4.25,name:'Madrid DSN, Spain'},{lat:35.34,lng:-116.87,name:'Goldstone DSN, US'},
  {lat:19.01,lng:-155.67,name:'Maui SSA, Hawaii'},{lat:-23.00,lng:-67.77,name:'ALMA, Chile'},
  {lat:28.30,lng:-16.51,name:'Tenerife ESA, Spain'},{lat:48.26,lng:11.67,name:'GSOC, Germany'},
  {lat:52.22,lng:21.01,name:'POLSA, Poland'},{lat:31.25,lng:131.08,name:'JAXA Tanegashima, Japan'},
];
const _RARE_EARTH_MINES = [
  {lat:40.65,lng:109.97,name:'Bayan Obo, China (60% global RE)'},{lat:34.19,lng:-115.53,name:'Mountain Pass, US'},
  {lat:-23.00,lng:-43.50,name:'Araxá, Brazil (niobium)'},{lat:-33.29,lng:138.02,name:'Mt Weld, Australia'},
  {lat:60.03,lng:-112.47,name:'Thor Lake, Canada'},{lat:67.86,lng:20.22,name:'Norra Kärr, Sweden'},
  {lat:-29.20,lng:31.02,name:'Zululand, South Africa'},{lat:17.38,lng:78.49,name:'Hyderabad RE, India'},
  {lat:2.04,lng:102.57,name:'Kuantan, Malaysia (Lynas)'},{lat:61.99,lng:5.86,name:'Fensfeltet, Norway'},
  {lat:68.42,lng:18.18,name:'Kvanefjeld, Greenland'},{lat:-21.17,lng:48.33,name:'Ambatovy, Madagascar'},
];

const _TSUNAMI_STATIONS = [
  // NOAA DART buoys + international tsunami warning network
  {lat:38.48,lng:-123.32,name:'DART 46407, NE Pacific'},{lat:46.14,lng:-128.97,name:'DART 46404, Juan de Fuca'},
  {lat:19.64,lng:-156.43,name:'DART 51407, Hawaii'},{lat:-15.01,lng:-175.02,name:'DART 51425, Tonga'},
  {lat:-32.39,lng:-72.50,name:'DART 32413, Chile'},{lat:8.89,lng:-89.56,name:'DART 43413, E. Pacific'},
  {lat:39.33,lng:142.77,name:'DART 21418, Japan'},{lat:-5.04,lng:101.92,name:'DART 23401, Sumatra'},
  {lat:-7.60,lng:107.50,name:'InaTEWS, Indonesia'},{lat:-38.45,lng:178.17,name:'GeoNet, New Zealand'},
  {lat:33.17,lng:136.58,name:'JMA Tonankai, Japan'},{lat:36.88,lng:21.76,name:'NEAMTWS, Greece'},
  {lat:61.05,lng:-147.79,name:'DART 46410, Alaska'},{lat:-8.88,lng:115.48,name:'Bali Warning Buoy'},
  {lat:24.45,lng:122.12,name:'CWB Taiwan'},{lat:-43.53,lng:172.53,name:'Canterbury, NZ'},
];
const _BORDER_CROSSINGS = [
  // World's busiest / most strategic border crossings
  {lat:32.54,lng:-117.04,name:'San Ysidro, US-Mexico (busiest)'},{lat:25.96,lng:-97.50,name:'Brownsville-Matamoros, US-MX'},
  {lat:31.76,lng:-106.45,name:'El Paso-Juarez, US-MX'},{lat:42.33,lng:-83.04,name:'Detroit-Windsor, US-CA'},
  {lat:49.00,lng:-122.76,name:'Peace Arch, US-CA'},{lat:43.24,lng:-79.07,name:'Niagara Falls, US-CA'},
  {lat:50.95,lng:1.85,name:'Calais-Dover, FR-UK (Channel)'},{lat:50.73,lng:7.10,name:'Bonn-Remagen, DE'},
  {lat:48.97,lng:2.16,name:'CDG Airport Border, FR'},{lat:41.01,lng:28.98,name:'Istanbul Border Gates, TR'},
  {lat:36.81,lng:-5.33,name:'Gibraltar, UK-ES'},{lat:35.16,lng:33.34,name:'Green Line, Cyprus'},
  {lat:38.32,lng:126.63,name:'DMZ, Korea (most fortified)'},{lat:32.50,lng:35.47,name:'Allenby Bridge, IL-JO'},
  {lat:31.24,lng:34.28,name:'Rafah, Gaza-Egypt'},{lat:30.02,lng:31.24,name:'Cairo Airport Border, EG'},
  {lat:27.17,lng:78.02,name:'Wagah-Attari, India-PK'},{lat:22.53,lng:114.06,name:'Shenzhen Bay, CN-HK'},
  {lat:1.35,lng:103.82,name:'Woodlands, SG-MY'},{lat:-25.74,lng:28.21,name:'Beit Bridge, ZA-ZW'},
];
const _LISTENING_POSTS = [
  // Known SIGINT / signals intelligence stations
  {lat:51.15,lng:-1.75,name:'GCHQ Bude, UK'},{lat:52.10,lng:-0.74,name:'GCHQ Cheltenham, UK'},
  {lat:56.13,lng:-3.22,name:'RAF Menwith Hill, UK (NSA)'},{lat:39.11,lng:-76.77,name:'NSA Fort Meade, US'},
  {lat:38.95,lng:-77.15,name:'NRO Chantilly, US'},{lat:-23.80,lng:133.74,name:'Pine Gap, Australia (Five Eyes)'},
  {lat:-41.37,lng:174.83,name:'Waihopai, New Zealand'},{lat:44.63,lng:-63.57,name:'CSE Leitrim, Canada'},
  {lat:48.33,lng:11.80,name:'Bad Aibling, Germany (BND)'},{lat:50.36,lng:7.88,name:'Dagger Complex, DE (NSA)'},
  {lat:35.38,lng:24.47,name:'Souda Bay SIGINT, Greece'},{lat:36.12,lng:32.99,name:'Incirlik SIGINT, Turkey'},
  {lat:25.38,lng:51.49,name:'Al Udeid SIGINT, Qatar'},{lat:-7.27,lng:72.37,name:'Diego Garcia SIGINT'},
  {lat:26.56,lng:128.12,name:'Torii Station, Okinawa'},{lat:64.88,lng:-147.60,name:'Eielson AFB SIGINT, AK'},
];
const _LIVE_WEBCAMS = [
  // Strategic live webcam locations (tourism/monitoring hotspots)
  {lat:48.86,lng:2.29,name:'Eiffel Tower, Paris'},{lat:40.76,lng:-73.98,name:'Times Square, NYC'},
  {lat:51.50,lng:-0.12,name:'Abbey Road, London'},{lat:35.66,lng:139.70,name:'Shibuya Crossing, Tokyo'},
  {lat:41.90,lng:12.49,name:'Colosseum, Rome'},{lat:22.28,lng:114.17,name:'Victoria Harbour, HK'},
  {lat:55.75,lng:37.62,name:'Red Square, Moscow'},{lat:-22.95,lng:-43.17,name:'Copacabana, Rio'},
  {lat:64.13,lng:-21.90,name:'Reykjavik Harbour, Iceland'},{lat:25.20,lng:55.27,name:'Burj Khalifa, Dubai'},
  {lat:37.82,lng:-122.48,name:'Golden Gate Bridge, SF'},{lat:-33.86,lng:151.21,name:'Sydney Opera House'},
  {lat:13.41,lng:103.87,name:'Angkor Wat, Cambodia'},{lat:27.18,lng:78.04,name:'Taj Mahal, India'},
  {lat:29.98,lng:31.13,name:'Pyramids of Giza, Egypt'},{lat:63.07,lng:-151.01,name:'Denali, Alaska'},
];
const _VOLCANIC_ARCS = [
  // Major volcanic arc segments and monitoring points
  {lat:60.49,lng:-152.74,name:'Ring of Fire: Alaska/Aleutians'},{lat:46.85,lng:-121.76,name:'Ring of Fire: Cascades'},
  {lat:19.42,lng:-155.29,name:'Hawaii Hotspot'},{lat:14.50,lng:-90.88,name:'Central America Arc'},
  {lat:-1.47,lng:-78.44,name:'Northern Andes Arc'},{lat:-33.40,lng:-70.00,name:'Southern Andes Arc'},
  {lat:64.13,lng:-21.32,name:'Mid-Atlantic Ridge: Iceland'},{lat:37.75,lng:14.99,name:'Mediterranean Arc: Etna'},
  {lat:40.82,lng:14.43,name:'Mediterranean: Vesuvius'},{lat:36.40,lng:25.40,name:'Aegean: Santorini'},
  {lat:42.35,lng:42.10,name:'Caucasus: Elbrus'},{lat:-8.34,lng:116.47,name:'Sunda Arc: Rinjani'},
  {lat:-7.54,lng:110.45,name:'Sunda Arc: Merapi'},{lat:35.36,lng:138.73,name:'Japan Arc: Fuji'},
  {lat:31.06,lng:130.66,name:'Japan Arc: Sakurajima'},{lat:56.06,lng:160.64,name:'Kamchatka Arc'},
  {lat:-38.69,lng:176.07,name:'Taupo Volcanic Zone, NZ'},{lat:14.14,lng:121.93,name:'Philippines Arc: Taal'},
  {lat:5.98,lng:-75.32,name:'Northern Andes: Nevado del Ruiz'},{lat:-15.79,lng:-71.85,name:'Andes: Ubinas, Peru'},
];

function initSitroomMap() {
  const container = document.getElementById('sitroom-map');
  if (!container || _sitroomMap) return;

  try {
    _sitroomMap = new maplibregl.Map({
      container: 'sitroom-map',
      style: {
        version: 8,
        sources: { 'carto': { type: 'raster', tiles: ['https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png'], tileSize: 256 } },
        layers: [{ id: 'carto', type: 'raster', source: 'carto', minzoom: 0, maxzoom: 18 }]
      },
      center: [0, 20], zoom: 1.8, attributionControl: false,
    });
    _sitroomMap.on('load', () => {
      _sitroomResizeMap();
      loadSitroomMapData();
      _updateMapLegend();
      setTimeout(_renderDayNight, 500);
    });
    // Resize on window resize for full-bleed flex layout
    window.addEventListener('resize', _sitroomResizeMap);
    // Force resize after layout settles
    setTimeout(_sitroomResizeMap, 300);
    setTimeout(_sitroomResizeMap, 1000);
    _sitroomMap.on('error', (e) => {
      if (e.error && e.error.status === 0) {
        try {
          const protocol = new pmtiles.Protocol();
          maplibregl.addProtocol('pmtiles', protocol.tile);
        } catch (ex) {}
      }
    });
  } catch (err) {
    container.innerHTML = '<div class="sitroom-empty">Map unavailable</div>';
  }
}

async function loadSitroomMapData() {
  if (!_sitroomMap || !_sitroomMap.loaded()) return;
  _sitroomClusterGrid = {}; // Reset clustering grid
  _sitroomClusterCounts = {};
  const data = await safeFetch('/api/sitroom/events', {}, null);
  if (!data || !data.events) return;
  clearSitroomMarkers('earthquakes');
  clearSitroomMarkers('weather');
  clearSitroomMarkers('conflicts');
  data.events.forEach(ev => {
    if (ev.lat == null && ev.lng == null) return;
    if (ev.lat === 0 && ev.lng === 0) return; // skip null island unless real
    const lt = ev.event_type === 'earthquake' ? 'earthquakes' : ev.event_type === 'weather_alert' ? 'weather' : 'conflicts';
    const cbId = lt === 'earthquakes' ? 'quakes' : lt;
    const cb = document.getElementById('sitroom-layer-' + cbId);
    if (cb && !cb.checked) return;
    addSitroomMarker(ev, lt);
  });

  // Aviation layer
  if (document.getElementById('sitroom-layer-aviation')?.checked) {
    const av = await safeFetch('/api/sitroom/aviation?limit=200', {}, null);
    if (av && av.aircraft) {
      clearSitroomMarkers('aviation');
      av.aircraft.forEach(a => {
        if (!a.lat || !a.lng) return;
        addSitroomMarker({lat: a.lat, lng: a.lng, title: `${a.callsign || a.icao24} (${a.origin_country})`,
          event_type: 'aircraft', magnitude: null, depth_km: null,
          detail_json: JSON.stringify({alt: a.altitude_m, speed: a.velocity_ms, heading: a.heading})}, 'aviation');
      });
    }
  }

  // Fire layer
  if (document.getElementById('sitroom-layer-fires')?.checked) {
    const fr = await safeFetch('/api/sitroom/fires?limit=300', {}, null);
    if (fr && fr.fires) {
      clearSitroomMarkers('fires');
      fr.fires.forEach(f => {
        if (!f.lat || !f.lng) return;
        addSitroomMarker({lat: f.lat, lng: f.lng, title: f.title || 'Fire',
          event_type: 'fire', magnitude: f.magnitude, depth_km: null,
          detail_json: f.detail_json}, 'fires');
      });
    }
  }

  // Volcano layer
  if (document.getElementById('sitroom-layer-volcanoes')?.checked) {
    const vol = await safeFetch('/api/sitroom/volcanoes', {}, null);
    if (vol && vol.volcanoes) {
      clearSitroomMarkers('volcanoes');
      vol.volcanoes.slice(0, 30).forEach(v => {
        if (!v.lat || !v.lng) return;
        addSitroomMarker({lat: v.lat, lng: v.lng, title: `${v.volcano_name} (${v.country})`,
          event_type: 'volcano', magnitude: v.vei, depth_km: null}, 'volcanoes');
      });
    }
  }

  // Nuclear sites layer (static data)
  if (document.getElementById('sitroom-layer-nuclear')?.checked) {
    clearSitroomMarkers('nuclear');
    _NUCLEAR_SITES.forEach(s => {
      addSitroomMarker({lat: s.lat, lng: s.lng, title: s.name,
        event_type: 'nuclear', magnitude: null, depth_km: null}, 'nuclear');
    });
  } else { clearSitroomMarkers('nuclear'); }

  // Military bases layer (static data)
  if (document.getElementById('sitroom-layer-bases')?.checked) {
    clearSitroomMarkers('bases');
    _MILITARY_BASES.forEach(s => {
      addSitroomMarker({lat: s.lat, lng: s.lng, title: s.name,
        event_type: 'military_base', magnitude: null, depth_km: null}, 'bases');
    });
  } else { clearSitroomMarkers('bases'); }

  // Undersea cable landings (static)
  if (document.getElementById('sitroom-layer-cables')?.checked) {
    clearSitroomMarkers('cables');
    _CABLE_LANDINGS.forEach(s => {
      addSitroomMarker({lat: s.lat, lng: s.lng, title: s.name,
        event_type: 'cable', magnitude: null, depth_km: null}, 'cables');
    });
  } else { clearSitroomMarkers('cables'); }

  // Data centers (static)
  if (document.getElementById('sitroom-layer-datacenters')?.checked) {
    clearSitroomMarkers('datacenters');
    _DATA_CENTERS.forEach(s => {
      addSitroomMarker({lat: s.lat, lng: s.lng, title: s.name,
        event_type: 'datacenter', magnitude: null, depth_km: null}, 'datacenters');
    });
  } else { clearSitroomMarkers('datacenters'); }

  // Pipeline hubs (static)
  if (document.getElementById('sitroom-layer-pipelines')?.checked) {
    clearSitroomMarkers('pipelines');
    _PIPELINE_HUBS.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'pipeline'}, 'pipelines'));
  } else { clearSitroomMarkers('pipelines'); }

  // Strategic waterways (static)
  if (document.getElementById('sitroom-layer-waterways')?.checked) {
    clearSitroomMarkers('waterways');
    _STRATEGIC_WATERWAYS.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'waterway'}, 'waterways'));
  } else { clearSitroomMarkers('waterways'); }

  // Spaceports (static)
  if (document.getElementById('sitroom-layer-spaceports')?.checked) {
    clearSitroomMarkers('spaceports');
    _SPACEPORTS.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'spaceport'}, 'spaceports'));
  } else { clearSitroomMarkers('spaceports'); }

  // Shipping hubs (static)
  if (document.getElementById('sitroom-layer-shipping')?.checked) {
    clearSitroomMarkers('shipping');
    _SHIPPING_HUBS.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'shipping'}, 'shipping'));
  } else { clearSitroomMarkers('shipping'); }

  // UCDP armed conflicts (live data)
  if (document.getElementById('sitroom-layer-ucdp')?.checked) {
    const uc = await safeFetch('/api/sitroom/ucdp?limit=50', {}, null);
    if (uc && uc.conflicts) {
      clearSitroomMarkers('ucdp');
      uc.conflicts.forEach(c => {
        if (!c.lat || !c.lng) return;
        addSitroomMarker({lat:c.lat,lng:c.lng,title:c.title||'Conflict',
          event_type:'ucdp_conflict',magnitude:c.magnitude,depth_km:null,detail_json:c.detail_json}, 'ucdp');
      });
    }
  } else { clearSitroomMarkers('ucdp'); }

  // Airports (static)
  if (document.getElementById('sitroom-layer-airports')?.checked) {
    clearSitroomMarkers('airports');
    _MAJOR_AIRPORTS.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'airport'}, 'airports'));
  } else { clearSitroomMarkers('airports'); }

  // Financial centers (static)
  if (document.getElementById('sitroom-layer-fincenters')?.checked) {
    clearSitroomMarkers('fincenters');
    _FINANCIAL_CENTERS.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'finance'}, 'fincenters'));
  } else { clearSitroomMarkers('fincenters'); }

  // Mining sites (static)
  if (document.getElementById('sitroom-layer-mining')?.checked) {
    clearSitroomMarkers('mining');
    _MINING_SITES.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'mining'}, 'mining'));
  } else { clearSitroomMarkers('mining'); }

  // Tech HQs (static)
  if (document.getElementById('sitroom-layer-techHQs')?.checked) {
    clearSitroomMarkers('techHQs');
    _TECH_HQS.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'tech_hq'}, 'techHQs'));
  } else { clearSitroomMarkers('techHQs'); }

  // Disease outbreaks (live data — plot geocoded WHO DON)
  if (document.getElementById('sitroom-layer-diseases')?.checked) {
    const dis = await safeFetch('/api/sitroom/diseases', {}, null);
    if (dis && dis.outbreaks) {
      clearSitroomMarkers('diseases');
      dis.outbreaks.forEach(d => {
        if (!d.lat || !d.lng) return;
        addSitroomMarker({lat:d.lat,lng:d.lng,title:d.title||'Outbreak',
          event_type:'disease',magnitude:null,depth_km:null,detail_json:d.detail_json}, 'diseases');
      });
    }
  } else { clearSitroomMarkers('diseases'); }

  // Radiation monitors (live data — plot Safecast readings)
  if (document.getElementById('sitroom-layer-radiation')?.checked) {
    const rad = await safeFetch('/api/sitroom/radiation', {}, null);
    if (rad && rad.readings) {
      clearSitroomMarkers('radiation');
      rad.readings.forEach(r => {
        if (!r.lat || !r.lng) return;
        addSitroomMarker({lat:r.lat,lng:r.lng,title:r.title||'Radiation',
          event_type:'radiation',magnitude:r.magnitude,depth_km:null,detail_json:r.detail_json}, 'radiation');
      });
    }
  } else { clearSitroomMarkers('radiation'); }

  // Protests & Unrest (live — filter UCDP for protest-type events)
  if (document.getElementById('sitroom-layer-protests')?.checked) {
    const pr = await safeFetch('/api/sitroom/protests', {}, null);
    if (pr && pr.events) {
      clearSitroomMarkers('protests');
      pr.events.forEach(p => {
        if (!p.lat || !p.lng) return;
        addSitroomMarker({lat:p.lat,lng:p.lng,title:p.title||'Protest/Unrest',
          event_type:'protest',magnitude:null,depth_km:null,detail_json:p.detail_json}, 'protests');
      });
    }
  } else { clearSitroomMarkers('protests'); }

  // AIS Ship Traffic (live data)
  if (document.getElementById('sitroom-layer-ships')?.checked) {
    const sh = await safeFetch('/api/sitroom/ships?limit=200', {}, null);
    if (sh && sh.ships) {
      clearSitroomMarkers('ships');
      sh.ships.forEach(s => {
        if (!s.lat || !s.lng) return;
        addSitroomMarker({lat:s.lat,lng:s.lng,title:`${s.ship_name||s.mmsi} (${s.flag||'?'})`,
          event_type:'ship',magnitude:null,depth_km:null,
          detail_json:JSON.stringify({speed:s.speed_kn,heading:s.heading,type:s.ship_type})}, 'ships');
      });
    }
  } else { clearSitroomMarkers('ships'); }

  // Cloud Regions (static)
  if (document.getElementById('sitroom-layer-cloudRegions')?.checked) {
    clearSitroomMarkers('cloudRegions');
    _CLOUD_REGIONS.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'cloud_region'}, 'cloudRegions'));
  } else { clearSitroomMarkers('cloudRegions'); }

  // Stock Exchanges (static)
  if (document.getElementById('sitroom-layer-exchanges')?.checked) {
    clearSitroomMarkers('exchanges');
    _STOCK_EXCHANGES.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'exchange'}, 'exchanges'));
  } else { clearSitroomMarkers('exchanges'); }

  // Commodity Hubs (static)
  if (document.getElementById('sitroom-layer-commodityHubs')?.checked) {
    clearSitroomMarkers('commodityHubs');
    _COMMODITY_HUBS.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'commodity_hub'}, 'commodityHubs'));
  } else { clearSitroomMarkers('commodityHubs'); }

  // Startup Hubs (static)
  if (document.getElementById('sitroom-layer-startupHubs')?.checked) {
    clearSitroomMarkers('startupHubs');
    _STARTUP_HUBS.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'startup_hub'}, 'startupHubs'));
  } else { clearSitroomMarkers('startupHubs'); }

  // GPS Jamming Zones (static — known chronic interference areas)
  if (document.getElementById('sitroom-layer-gpsJamming')?.checked) {
    clearSitroomMarkers('gpsJamming');
    _GPS_JAMMING_ZONES.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'gps_jamming'}, 'gpsJamming'));
  } else { clearSitroomMarkers('gpsJamming'); }

  // Trade Routes (static waypoints along major shipping lanes)
  if (document.getElementById('sitroom-layer-tradeRoutes')?.checked) {
    clearSitroomMarkers('tradeRoutes');
    _TRADE_ROUTES.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'trade_route'}, 'tradeRoutes'));
  } else { clearSitroomMarkers('tradeRoutes'); }

  // Accelerators (static)
  if (document.getElementById('sitroom-layer-accelerators')?.checked) {
    clearSitroomMarkers('accelerators');
    _ACCELERATORS.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'accelerator'}, 'accelerators'));
  } else { clearSitroomMarkers('accelerators'); }

  // Refugee Camps / IDP Sites (static)
  if (document.getElementById('sitroom-layer-refugees')?.checked) {
    clearSitroomMarkers('refugees');
    _REFUGEE_CAMPS.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'refugee_camp'}, 'refugees'));
  } else { clearSitroomMarkers('refugees'); }

  // UN Peacekeeping Missions (static)
  if (document.getElementById('sitroom-layer-unMissions')?.checked) {
    clearSitroomMarkers('unMissions');
    _UN_MISSIONS.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'un_mission'}, 'unMissions'));
  } else { clearSitroomMarkers('unMissions'); }

  // Internet Exchange Points (static)
  if (document.getElementById('sitroom-layer-ixps')?.checked) {
    clearSitroomMarkers('ixps');
    _INTERNET_EXCHANGES.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'ixp'}, 'ixps'));
  } else { clearSitroomMarkers('ixps'); }

  // Embassies / Diplomatic Hubs (static)
  if (document.getElementById('sitroom-layer-embassies')?.checked) {
    clearSitroomMarkers('embassies');
    _EMBASSIES_DC.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'embassy'}, 'embassies'));
  } else { clearSitroomMarkers('embassies'); }

  // Desalination Plants (static)
  if (document.getElementById('sitroom-layer-desalination')?.checked) {
    clearSitroomMarkers('desalination');
    _DESALINATION_PLANTS.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'desalination'}, 'desalination'));
  } else { clearSitroomMarkers('desalination'); }

  // Weather Stations (static)
  if (document.getElementById('sitroom-layer-weatherStations')?.checked) {
    clearSitroomMarkers('weatherStations');
    _WEATHER_STATIONS.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'weather_station'}, 'weatherStations'));
  } else { clearSitroomMarkers('weatherStations'); }

  // Space Tracking Stations (static)
  if (document.getElementById('sitroom-layer-spaceTracking')?.checked) {
    clearSitroomMarkers('spaceTracking');
    _SPACE_TRACKING.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'space_tracking'}, 'spaceTracking'));
  } else { clearSitroomMarkers('spaceTracking'); }

  // Rare Earth Mines (static)
  if (document.getElementById('sitroom-layer-rareEarths')?.checked) {
    clearSitroomMarkers('rareEarths');
    _RARE_EARTH_MINES.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'rare_earth'}, 'rareEarths'));
  } else { clearSitroomMarkers('rareEarths'); }

  // Live Webcams (static)
  if (document.getElementById('sitroom-layer-webcams')?.checked) {
    clearSitroomMarkers('webcams');
    _LIVE_WEBCAMS.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'webcam'}, 'webcams'));
  } else { clearSitroomMarkers('webcams'); }

  // Tsunami Warning Stations (static)
  if (document.getElementById('sitroom-layer-tsunamiStations')?.checked) {
    clearSitroomMarkers('tsunamiStations');
    _TSUNAMI_STATIONS.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'tsunami_station'}, 'tsunamiStations'));
  } else { clearSitroomMarkers('tsunamiStations'); }

  // Border Crossings (static)
  if (document.getElementById('sitroom-layer-borderCrossings')?.checked) {
    clearSitroomMarkers('borderCrossings');
    _BORDER_CROSSINGS.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'border_crossing'}, 'borderCrossings'));
  } else { clearSitroomMarkers('borderCrossings'); }

  // SIGINT / Listening Posts (static)
  if (document.getElementById('sitroom-layer-listeningPosts')?.checked) {
    clearSitroomMarkers('listeningPosts');
    _LISTENING_POSTS.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'listening_post'}, 'listeningPosts'));
  } else { clearSitroomMarkers('listeningPosts'); }

  // Volcanic Arcs (static)
  if (document.getElementById('sitroom-layer-volcanicArcs')?.checked) {
    clearSitroomMarkers('volcanicArcs');
    _VOLCANIC_ARCS.forEach(s => addSitroomMarker({lat:s.lat,lng:s.lng,title:s.name,event_type:'volcanic_arc'}, 'volcanicArcs'));
  } else { clearSitroomMarkers('volcanicArcs'); }

  // Weather radar overlay (RainViewer tile layer)
  _toggleWeatherRadar();
}

/* ─── Weather Radar (RainViewer) ─── */
async function _toggleWeatherRadar() {
  if (!_sitroomMap) return;
  const cb = document.getElementById('sitroom-layer-radar');
  if (!cb || !cb.checked) {
    _removeRadarLayer();
    return;
  }
  try {
    const resp = await fetch('https://api.rainviewer.com/public/weather-maps.json', {
      signal: AbortSignal.timeout(8000),
    });
    if (!resp.ok) return;
    const data = await resp.json();
    const frames = Array.isArray(data?.radar?.past) ? data.radar.past : [];
    if (!frames || !frames.length) return;
    const latest = frames[frames.length - 1];
    const tileUrl = `${data.host}${latest.path}/256/{z}/{x}/{y}/2/1_1.png`;

    _removeRadarLayer();
    _sitroomMap.addSource('rainviewer', {
      type: 'raster',
      tiles: [tileUrl],
      tileSize: 256,
      maxzoom: 7
    });
    _sitroomMap.addLayer({
      id: 'rainviewer-layer',
      type: 'raster',
      source: 'rainviewer',
      paint: { 'raster-opacity': 0.6 }
    });
    _sitroomRadarLayer = true;
  } catch (e) { /* offline or API down */ }
}

function _removeRadarLayer() {
  if (!_sitroomMap || !_sitroomRadarLayer) return;
  try {
    if (_sitroomMap.getLayer('rainviewer-layer')) _sitroomMap.removeLayer('rainviewer-layer');
    if (_sitroomMap.getSource('rainviewer')) _sitroomMap.removeSource('rainviewer');
  } catch (e) {}
  _sitroomRadarLayer = null;
}

function clearSitroomMarkers(layerType) {
  const arr = _sitroomMarkers[layerType];
  if (arr) { arr.forEach(m => m.remove()); arr.length = 0; }
}

/* ─── Enhanced Marker Clustering (Supercluster-inspired) ─── */
let _sitroomClusterGrid = {};
let _sitroomClusterCounts = {};
function _shouldCluster(lat, lng, layerType) {
  if (!_sitroomMap) return false;
  const zoom = _sitroomMap.getZoom();
  if (zoom > 8) return false; // No clustering at high zoom
  // Adaptive grid — tighter at medium zoom, wider at low zoom
  const gridSize = zoom < 3 ? 10 : zoom < 5 ? 5 : zoom < 7 ? 2 : 1;
  const key = `${layerType}:${Math.round(lat/gridSize)}:${Math.round(lng/gridSize)}`;
  if (_sitroomClusterGrid[key]) {
    _sitroomClusterCounts[key] = (_sitroomClusterCounts[key] || 1) + 1;
    return true;
  }
  _sitroomClusterGrid[key] = true;
  _sitroomClusterCounts[key] = 1;
  return false;
}
function _getClusterCount(lat, lng, layerType) {
  const zoom = _sitroomMap ? _sitroomMap.getZoom() : 2;
  const gridSize = zoom < 3 ? 10 : zoom < 5 ? 5 : zoom < 7 ? 2 : 1;
  const key = `${layerType}:${Math.round(lat/gridSize)}:${Math.round(lng/gridSize)}`;
  return _sitroomClusterCounts[key] || 1;
}

function addSitroomMarker(ev, layerType) {
  if (!_sitroomMap) return;
  // Skip if would cluster with existing marker at this zoom
  if (_shouldCluster(ev.lat, ev.lng, layerType)) return;
  const colors = { earthquakes: '#ff4444', weather: '#ffaa00', conflicts: '#ff6600', aviation: '#44aaff', volcanoes: '#ff3366', fires: '#ff8800', nuclear: '#ffff00', bases: '#44ff88', cables: '#3388ff', datacenters: '#aa66ff', pipelines: '#cc8844', waterways: '#00ddff', spaceports: '#ff66ff', shipping: '#88ccaa', ucdp: '#dd2222', airports: '#cccccc', fincenters: '#44dd88', mining: '#cc8844', techHQs: '#44aadd', diseases: '#ff44ff', radiation: '#66ff00', protests: '#ffcc00', ships: '#22bbdd', cloudRegions: '#6688ff', exchanges: '#ddaa22', commodityHubs: '#dd8866', startupHubs: '#ff88dd', gpsJamming: '#ff2200', tradeRoutes: '#66ccff', accelerators: '#cc66ff', refugees: '#ff8866', unMissions: '#4488ff', ixps: '#88ffcc', embassies: '#ddddaa', desalination: '#44cccc', weatherStations: '#aabb44', spaceTracking: '#bb88ff', rareEarths: '#ee6699', tsunamiStations: '#ff6644', borderCrossings: '#ccaa66', listeningPosts: '#8844cc', volcanicArcs: '#ff3333', webcams: '#ffffff' };
  const color = colors[layerType] || '#ffffff';
  let size = layerType === 'aviation' ? 5 : 8;
  if (ev.magnitude) size = Math.max(6, Math.min(24, ev.magnitude * 3));

  const el = document.createElement('div');
  el.className = 'sitroom-marker sitroom-marker-' + layerType;
  el.dataset.layer = layerType;
  el.style.setProperty('--sr-marker-size', `${size}px`);
  el.style.setProperty('--sr-marker-glow-size', `${size}px`);
  el.style.setProperty('--sr-marker-color', color);
  el.style.setProperty('--sr-marker-glow', `${color}40`);

  let popupHtml = `<div class="sitroom-popup"><strong>${escapeHtml(ev.title || 'Event')}</strong>`;
  if (ev.magnitude) popupHtml += `<br>Magnitude: ${escapeHtml(String(ev.magnitude))}`;
  if (ev.depth_km) popupHtml += `<br>Depth: ${escapeHtml(String(ev.depth_km))} km`;
  popupHtml += `<br><small>${escapeHtml(ev.event_type || layerType)}</small></div>`;

  const popup = new maplibregl.Popup({ offset: 10, closeButton: false }).setHTML(popupHtml);
  const marker = new maplibregl.Marker({ element: el }).setLngLat([ev.lng, ev.lat]).setPopup(popup).addTo(_sitroomMap);
  if (!_sitroomMarkers[layerType]) _sitroomMarkers[layerType] = [];
  _sitroomMarkers[layerType].push(marker);
}

/* ─── Summary ─── */
async function loadSitroomSummary() {
  const d = await safeFetch('/api/sitroom/summary', {}, null);
  if (!d) return;
  const s = (id, val) => { const e = document.getElementById(id); if (e) e.textContent = val; };
  s('sitroom-stat-news', d.news_count || 0);
  s('sitroom-stat-quakes', d.earthquake_count || 0);
  s('sitroom-stat-weather', d.weather_alert_count || 0);
  s('sitroom-stat-conflicts', d.conflict_count || 0);
  s('sitroom-stat-markets', d.market_count || 0);
  s('sitroom-stat-aircraft', d.aircraft_count || 0);
  s('sitroom-stat-volcanoes', d.volcano_count || 0);
  s('sitroom-stat-fires', d.fire_count || 0);
  s('sitroom-stat-outages', d.outage_count || 0);
  s('sitroom-stat-predictions', d.prediction_count || 0);

  const badge = document.getElementById('sitroom-online-badge');
  if (badge) {
    const hasData = (d.news_count || 0) > 0;
    badge.textContent = hasData ? 'DATA CACHED' : 'OFFLINE';
    badge.className = 'sitroom-badge ' + (hasData ? 'sitroom-badge-online' : 'sitroom-badge-offline');
  }
  const ts = document.getElementById('sitroom-last-update');
  if (ts && d.last_fetch) {
    const latest = Object.values(d.last_fetch).filter(Boolean).sort().pop();
    if (latest) ts.textContent = 'Updated ' + _timeAgo(new Date(latest));
  }

  renderSitroomMarkets(d.markets || []);
  renderSitroomMarketRibbon(d.markets || []);
  renderSitroomFearGreed(d.markets || []);
  renderSitroomSectorHeatmap(d.markets || []);
  renderSitroomSpaceWeather(d.space_weather);
  _updateThreatLevel(d);
  _updateStatusDot(d);
  renderSitroomQuakes();
  loadSitroomWeather();
  loadSitroomPredictions();
  loadSitroomMapData();
}

/* ─── Markets (grouped by type) ─── */
function renderSitroomMarkets(markets) {
  const c = document.getElementById('sitroom-market-ticker');
  if (!c) return;
  if (!markets.length) { c.innerHTML = '<div class="sitroom-empty">No market data — click Refresh</div>'; return; }
  const groups = {index:'INDICES',forex:'FOREX',crypto:'CRYPTO',commodity:'COMMODITIES'};
  const grouped = {};
  markets.forEach(m => {
    if (m.market_type === 'sector' || m.market_type === 'sentiment') return; // shown in other cards
    const g = groups[m.market_type] || 'OTHER';
    if (!grouped[g]) grouped[g] = [];
    grouped[g].push(m);
  });
  let html = '';
  for (const [label, items] of Object.entries(grouped)) {
    html += `<div class="sr-market-group-label">${label}</div>`;
    html += items.map(m => {
      const ch = m.change_24h || 0;
      const up = ch >= 0;
      const cls = up ? 'sitroom-market-up' : 'sitroom-market-down';
      let price;
      if (m.price >= 1) price = '$' + Number(m.price).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
      else price = '$' + Number(m.price).toFixed(4);
      return `<div class="sitroom-market-card ${cls}">
        <div class="sitroom-market-symbol">${escapeHtml(m.label || m.symbol)}</div>
        <div class="sitroom-market-price">${price}</div>
        <div class="sitroom-market-change">${up ? '&#9650;' : '&#9660;'} ${Math.abs(ch).toFixed(1)}%</div>
      </div>`;
    }).join('');
  }
  c.innerHTML = html;
}

/* ─── Space Weather ─── */
function renderSitroomSpaceWeather(sw) {
  const c = document.getElementById('sitroom-space-weather');
  if (!c) return;
  if (!sw) { c.innerHTML = '<div class="sitroom-empty">No space weather data</div>'; return; }
  const r = sw.R || {}, s = sw.S || {}, g = sw.G || {};
  const scaleColor = (val) => val >= 4 ? 'sitroom-sw-extreme' : val >= 2 ? 'sitroom-sw-moderate' : 'sitroom-sw-normal';
  c.innerHTML = `<div class="sitroom-sw-grid">
    <div class="sitroom-sw-card ${scaleColor(r.Scale || 0)}"><div class="sitroom-sw-label">Radio Blackout</div><div class="sitroom-sw-value">R${r.Scale || 0}</div></div>
    <div class="sitroom-sw-card ${scaleColor(s.Scale || 0)}"><div class="sitroom-sw-label">Solar Radiation</div><div class="sitroom-sw-value">S${s.Scale || 0}</div></div>
    <div class="sitroom-sw-card ${scaleColor(g.Scale || 0)}"><div class="sitroom-sw-label">Geomagnetic</div><div class="sitroom-sw-value">G${g.Scale || 0}</div></div>
  </div>`;
}

/* ─── Earthquakes ─── */
async function renderSitroomQuakes() {
  const minMag = parseFloat(document.getElementById('sitroom-quake-filter')?.value || '4') || 0;
  const d = await safeFetch('/api/sitroom/earthquakes?min_magnitude=' + minMag, {}, null);
  const list = document.getElementById('sitroom-quake-list');
  if (!list) return;
  if (!d || !d.earthquakes?.length) { list.innerHTML = '<div class="sitroom-empty">No earthquakes above M' + minMag + '</div>'; return; }
  list.innerHTML = d.earthquakes.map(q => {
    const mc = q.magnitude >= 6 ? 'sitroom-mag-high' : q.magnitude >= 4.5 ? 'sitroom-mag-med' : 'sitroom-mag-low';
    const det = _parseSitroomDetailJson(q.detail_json);
    return `<div class="sitroom-event-item">
      <span class="sitroom-mag ${mc}">M${q.magnitude ? q.magnitude.toFixed(1) : '?'}</span>
      <div class="sitroom-event-info">
        <div class="sitroom-event-title" title="${escapeAttr(q.title || '')}">${escapeHtml(q.title || 'Unknown')}</div>
        <div class="sitroom-event-meta">Depth: ${q.depth_km ? q.depth_km.toFixed(0) + ' km' : 'N/A'}${det.alert ? ' | Alert: ' + escapeHtml(String(det.alert)) : ''}${det.felt ? ' | Felt: ' + escapeHtml(String(det.felt)) + ' reports' : ''}</div>
      </div>
      ${q.source_url ? `<a href="${escapeAttr(q.source_url)}" target="_blank" rel="noopener" class="sitroom-event-link" aria-label="View earthquake details">&#8599;</a>` : ''}
    </div>`;
  }).join('');
}

/* ─── Weather ─── */
async function loadSitroomWeather() {
  const d = await safeFetch('/api/sitroom/weather-alerts', {}, null);
  const list = document.getElementById('sitroom-weather-list');
  if (!list) return;
  if (!d || !d.alerts?.length) { list.innerHTML = '<div class="sitroom-empty">No severe weather alerts</div>'; return; }
  list.innerHTML = d.alerts.slice(0, 30).map(a => {
    const det = _parseSitroomDetailJson(a.detail_json);
    const sc = det.severity === 'Extreme' ? 'sitroom-sev-extreme' : 'sitroom-sev-severe';
    return `<div class="sitroom-event-item ${sc}">
      <div class="sitroom-event-info">
        <div class="sitroom-event-title" title="${escapeAttr(a.title || '')}">${escapeHtml(a.title || 'Alert')}</div>
        <div class="sitroom-event-meta">${escapeHtml(det.headline || '')}${det.sender ? ' (' + escapeHtml(det.sender) + ')' : ''}</div>
      </div>
    </div>`;
  }).join('');
}

/* ─── Predictions ─── */
async function loadSitroomPredictions() {
  const d = await safeFetch('/api/sitroom/predictions', {}, null);
  const c = document.getElementById('sitroom-predictions-list');
  if (!c) return;
  if (!d || !d.predictions?.length) { c.innerHTML = '<div class="sitroom-empty">No prediction markets</div>'; return; }
  c.innerHTML = d.predictions.map(p => {
    const yPct = Math.round((p.outcome_yes || 0) * 100);
    const nPct = 100 - yPct;
    return `<div class="sitroom-prediction-item">
      <div class="sitroom-prediction-q">${escapeHtml(p.question)}</div>
      <div class="sitroom-prediction-bar">
        <div class="sitroom-prediction-yes" data-sr-width="${yPct}">${yPct}%</div>
        <div class="sitroom-prediction-no" data-sr-width="${nPct}">${nPct}%</div>
      </div>
      <div class="sitroom-prediction-meta">Vol: $${Number(p.volume || 0).toLocaleString(undefined, {maximumFractionDigits: 0})}</div>
    </div>`;
  }).join('');
  _hydrateSitroomRuntimeVars(c);
}

/* ─── News Deduplication ─── */
function _dedupeHeadlines(articles) {
  if (!articles || articles.length < 2) return articles;
  const seen = [];
  return articles.filter(a => {
    const words = new Set((a.title || '').toLowerCase().replace(/[^a-z0-9 ]/g, '').split(/\s+/).filter(w => w.length > 3));
    for (const prev of seen) {
      const inter = [...words].filter(w => prev.has(w)).length;
      const union = new Set([...words, ...prev]).size;
      if (union > 0 && inter / union > 0.6) return false; // >60% word overlap = duplicate
    }
    seen.push(words);
    return true;
  });
}

/* ─── News ─── */
async function loadSitroomNews(append) {
  if (!append) _sitroomNewsOffset = 0;
  _sitroomNewsCat = document.getElementById('sitroom-news-category')?.value || '';
  const d = await safeFetch('/api/sitroom/news?category=' + encodeURIComponent(_sitroomNewsCat) + '&limit=' + SITROOM_NEWS_PAGE + '&offset=' + _sitroomNewsOffset, {}, null);
  const list = document.getElementById('sitroom-news-list');
  const more = document.getElementById('sitroom-news-more');
  if (!list) return;
  if (!d || !d.articles?.length) {
    if (!append) { list.innerHTML = '<div class="sitroom-empty">No news cached — click Refresh Feeds</div>'; if (more) more.hidden = true; }
    return;
  }
  // Deduplicate similar headlines (Jaccard similarity on word sets)
  const deduped = _dedupeHeadlines(d.articles);
  const filtered = _filterSitroomNewsByRegion(deduped);
  const prioritized = _prioritizeSitroomBriefArticles(filtered);
  if (!append) _sitroomNewsArticles = [];
  _sitroomNewsArticles = append ? _sitroomNewsArticles.concat(prioritized) : prioritized.slice();
  if (!prioritized.length) {
    if (!append) {
      list.innerHTML = '<div class="sitroom-empty">No headlines match this regional preset yet. Try another preset or broaden the desk.</div>';
      if (more) more.hidden = _sitroomNewsOffset >= (d.total || 0);
    }
    _renderSitroomNewsDeskBriefing(_sitroomNewsArticles, d.total || 0);
    return;
  }
  const html = prioritized.map(a => `<div class="sitroom-news-item">
    <span class="sitroom-news-cat" data-cat="${escapeAttr(a.category || '')}">${escapeHtml(a.category || '')}</span>
    <div class="sitroom-news-body">
      <button type="button" class="sitroom-news-title sitroom-news-title-action"
        data-sitroom-action="open-story"
        data-story-title="${escapeAttr(a.title || '')}"
        data-story-category="${escapeAttr(a.category || 'News')}"
        data-story-link="${escapeAttr(a.link || '#')}"
        data-story-description="${escapeAttr(a.description || '')}"
        data-story-source="${escapeAttr(a.source_name || '')}"
        data-story-published="${escapeAttr(a.published || '')}">${escapeHtml(a.title)}</button>
      <div class="sitroom-news-meta">${escapeHtml(a.source_name || '')} ${a.published ? '| ' + escapeHtml(a.published) : ''}</div>
    </div>
    ${a.link ? `<a href="${escapeAttr(a.link)}" target="_blank" rel="noopener" class="sr-analysis-linkout" aria-label="Open source article">&#8599;</a>` : ''}
  </div>`).join('');
  if (append) list.insertAdjacentHTML('beforeend', html); else list.innerHTML = html;
  _sitroomNewsOffset += deduped.length;
  if (more) more.hidden = _sitroomNewsOffset >= (d.total || 0);
  _renderSitroomNewsDeskBriefing(_sitroomNewsArticles, d.total || 0);
}

/* ─── Feeds ─── */
async function loadSitroomFeeds() {
  const d = await safeFetch('/api/sitroom/feeds', {}, null);
  if (!d) return;
  const sel = document.getElementById('sitroom-news-category');
  if (sel) {
    const prev = _sitroomNewsCat || sel.value;
    const cats = [...new Set([...(d.categories || []), ...(d.custom || []).map(f => f.category)])].sort();
    sel.innerHTML = '<option value="">All Categories</option>' + cats.map(c =>
      '<option value="' + escapeAttr(c) + '"' + (c === prev ? ' selected' : '') + '>' + escapeHtml(c) + '</option>').join('');
  }
  const be = document.getElementById('sitroom-builtin-count');
  const ce = document.getElementById('sitroom-custom-count');
  if (be) be.textContent = (d.builtin || []).length;
  if (ce) ce.textContent = (d.custom || []).length;
  const cl = document.getElementById('sitroom-custom-feeds-list');
  if (cl) {
    if (!d.custom?.length) cl.innerHTML = '<div class="sitroom-empty">No custom feeds</div>';
    else cl.innerHTML = d.custom.map(f => `<div class="sitroom-custom-feed-item">
      <span class="sitroom-news-cat">${escapeHtml(f.category)}</span>
      <span class="sitroom-custom-feed-name">${escapeHtml(f.name)}</span>
      <button class="btn btn-sm btn-danger" data-sitroom-action="delete-feed" data-feed-id="${f.id}">Remove</button>
    </div>`).join('');
  }
}

/* ─── AI Briefing ─── */
async function generateSitroomBriefing() {
  return _generateAiBriefing();
}

function _renderBriefing(text) {
  let h = escapeHtml(text);
  h = h.replace(/^### (.*?)$/gm, '<h4>$1</h4>');
  h = h.replace(/^## (.*?)$/gm, '<h3>$1</h3>');
  h = h.replace(/^# (.*?)$/gm, '<h2>$1</h2>');
  h = h.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  h = h.replace(/\n/g, '<br>');
  return h;
}

/* ─── Feed CRUD ─── */
async function addSitroomFeed() {
  const n = document.getElementById('sitroom-feed-name')?.value.trim();
  const u = document.getElementById('sitroom-feed-url')?.value.trim();
  const cat = document.getElementById('sitroom-feed-category')?.value.trim() || 'Custom';
  if (!n || !u) { toast('Name and URL required', 'warning'); return; }
  try {
    await apiPost('/api/sitroom/feeds', {name: n, url: u, category: cat});
    toast('Feed added', 'success'); document.getElementById('sitroom-feed-name').value = ''; document.getElementById('sitroom-feed-url').value = ''; loadSitroomFeeds();
  } catch (e) { toast(e.data?.error || 'Failed to add feed', 'error'); }
}

async function deleteSitroomFeed(id) {
  if (!confirm('Remove this custom feed?')) return;
  try {
    await apiDelete('/api/sitroom/feeds/' + id);
    toast('Feed removed', 'success'); loadSitroomFeeds();
  } catch (e) { toast('Failed to delete feed', 'error'); }
}

/* ─── Refresh with polling ─── */
async function refreshSitroomFeeds() {
  const btn = document.getElementById('sitroom-refresh-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Refreshing...'; }
  try {
    await apiPost('/api/sitroom/refresh');
    toast('Feed refresh started', 'info');
    _pollSitroomRefresh();
  } catch (e) { toast('Refresh failed', 'error'); }
  finally { if (btn) { btn.disabled = false; btn.textContent = 'Refresh Feeds'; } }
}

function _pollSitroomRefresh() {
  let attempts = 0;
  const poll = async () => {
    attempts++;
    const d = await safeFetch('/api/sitroom/status', {}, null);
    if (!d) return;
    if (!d.refreshing || attempts >= 20) {
      if (_sitroomRefreshPollTimer) {
        clearInterval(_sitroomRefreshPollTimer);
        _sitroomRefreshPollTimer = null;
      }
      window.NomadShellRuntime?.stopInterval('sitroom.refresh-status');
      _sitroomRefreshPanels();
      return;
    }
    if (attempts % 3 === 0) _sitroomRefreshPanels(); // partial updates every ~9s
  };
  if (_sitroomRefreshPollTimer) {
    clearInterval(_sitroomRefreshPollTimer);
    _sitroomRefreshPollTimer = null;
  }
  window.NomadShellRuntime?.stopInterval('sitroom.refresh-status');
  if (window.NomadShellRuntime) {
    _sitroomRefreshPollTimer = window.NomadShellRuntime.startInterval('sitroom.refresh-status', poll, 3000, {
      tabId: 'situation-room',
      requireVisible: true,
    });
    return;
  }
  _sitroomRefreshPollTimer = setInterval(() => {
    if (!_isSitroomActive() || document.hidden) return;
    poll();
  }, 3000);
}

/* ─── Utility ─── */
function _timeAgo(date) {
  const s = Math.floor((Date.now() - date.getTime()) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return Math.floor(s / 60) + 'm ago';
  if (s < 86400) return Math.floor(s / 3600) + 'h ago';
  return Math.floor(s / 86400) + 'd ago';
}

/* ─── Breaking News Banner ─── */
async function renderSitroomBreakingNews() {
  const el = document.getElementById('sr-breaking-text');
  if (!el) return;
  const items = [];

  // High-magnitude earthquakes
  const eq = await safeFetch('/api/sitroom/earthquakes?min_magnitude=5', {}, null);
  if (eq?.earthquakes) {
    eq.earthquakes.slice(0, 3).forEach(q => {
      items.push('EARTHQUAKE M' + (q.magnitude||0).toFixed(1) + ' - ' + (q.title||'Unknown'));
    });
  }

  // Latest news headlines
  const d = await safeFetch('/api/sitroom/news?limit=12', {}, null);
  if (d?.articles) {
    d.articles.forEach(a => items.push(a.title));
  }

  if (!items.length) { el.textContent = 'No breaking news'; return; }
  const text = items.map(t => escapeHtml(t)).join('  ///  ');
  el.innerHTML = text + '  ///  ' + text;
}

/* ─── Market Ribbon ─── */
function renderSitroomMarketRibbon(markets) {
  const el = document.getElementById('sr-market-ribbon');
  if (!el || !markets?.length) return;
  const items = markets.map(m => {
    const ch = m.change_24h || 0;
    const cls = ch >= 0 ? 'sr-ribbon-up' : 'sr-ribbon-down';
    const arrow = ch >= 0 ? '+' : '';
    let price;
    if (m.market_type === 'sentiment') price = m.price + '/100';
    else if (m.price >= 1) price = '$' + Number(m.price).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
    else price = '$' + Number(m.price).toFixed(4);
    return `<span class="sr-ribbon-item"><span class="sr-ribbon-sym">${escapeHtml(m.label || m.symbol)}</span> ${price} <span class="${cls}">${arrow}${ch.toFixed(1)}%</span></span>`;
  }).join('');
  // Duplicate for seamless scroll loop
  el.innerHTML = `<div class="sr-market-ribbon-inner">${items}${items}</div>`;
}

/* ─── Country Instability Index ─── */
async function loadSitroomCII() {
  const el = document.getElementById('sr-cii-list');
  if (!el) return;
  // Compute CII from events + news signal density per country
  const [events, newsData] = await Promise.all([
    safeFetch('/api/sitroom/events?limit=500', {}, null),
    safeFetch('/api/sitroom/news?limit=200', {}, null)
  ]);
  if ((!events || !events.events?.length) && (!newsData || !newsData.articles?.length)) {
    el.innerHTML = '<div class="sr-empty">No data for CII</div>'; return;
  }
  const countryScores = {};
  const _addCountry = (country, points, sev, type) => {
    if (!country || country === 'Unknown') return;
    if (!countryScores[country]) countryScores[country] = { events: 0, severity: 0, types: {} };
    countryScores[country].events++;
    countryScores[country].severity += sev;
    countryScores[country].types[type] = (countryScores[country].types[type] || 0) + 1;
  };
  // Score from events
  if (events?.events) {
    events.events.forEach(ev => {
      const det = _parseSitroomDetailJson(ev.detail_json);
      const country = det.country || '';
      let sev = 0;
      if (ev.magnitude) sev += ev.magnitude;
      if (det.severity === 'Extreme') sev += 5;
      if (det.severity === 'Severe') sev += 3;
      if (det.alert_level === 'Red') sev += 4;
      if (det.alert_level === 'Orange') sev += 2;
      if (ev.event_type === 'fire') sev += 0.5;
      if (ev.event_type === 'disease') sev += 3;
      if (ev.event_type === 'internet_outage') sev += 2;
      _addCountry(country, 1, sev, ev.event_type || 'unknown');
    });
  }
  // Boost from news mentions (scan titles for country names)
  if (newsData?.articles) {
    const knownCountries = Object.keys(countryScores);
    newsData.articles.forEach(a => {
      const title = (a.title || '').toLowerCase();
      knownCountries.forEach(c => {
        if (title.includes(c.toLowerCase())) {
          countryScores[c].severity += 0.5;
          countryScores[c].types['news'] = (countryScores[c].types['news'] || 0) + 1;
        }
      });
    });
  }
  const sorted = Object.entries(countryScores)
    .map(([c, s]) => ({ country: c, score: Math.min(100, Math.round(s.events * 3 + s.severity * 2)), events: s.events, types: s.types }))
    .sort((a, b) => b.score - a.score)
    .slice(0, 20);
  if (!sorted.length) { el.innerHTML = '<div class="sr-empty">No country data</div>'; return; }
  const maxScore = sorted[0].score || 1;
  el.innerHTML = sorted.map(c => {
    const cls = c.score >= 60 ? 'sr-cii-high' : c.score >= 30 ? 'sr-cii-med' : 'sr-cii-low';
    const tone = c.score >= 60 ? 'danger' : c.score >= 30 ? 'warn' : 'good';
    // Signal type icons
    const typeIcons = [];
    if (c.types.earthquake) typeIcons.push('<span class="sr-cii-signal" data-type="seismic" title="Seismic">S</span>');
    if (c.types.conflict) typeIcons.push('<span class="sr-cii-signal" data-type="crisis" title="Crisis">C</span>');
    if (c.types.weather_alert) typeIcons.push('<span class="sr-cii-signal" data-type="weather" title="Weather">W</span>');
    if (c.types.fire) typeIcons.push('<span class="sr-cii-signal" data-type="fires" title="Fires">F</span>');
    if (c.types.disease) typeIcons.push('<span class="sr-cii-signal" data-type="disease" title="Disease">D</span>');
    if (c.types.internet_outage) typeIcons.push('<span class="sr-cii-signal" data-type="outage" title="Outage">O</span>');
    if (c.types.news) typeIcons.push('<span class="sr-cii-signal" data-type="news" title="News mentions">N</span>');
    const signals = typeIcons.length ? `<span class="sr-cii-signals">${typeIcons.join('')}</span>` : '';
    return `<div class="sr-cii-row" data-cii-country="${escapeAttr(c.country)}">
      <span class="sr-cii-country">${escapeHtml(c.country)}</span>
      ${signals}
      <div class="sr-cii-bar"><div class="sr-cii-bar-fill" data-tone="${tone}" data-sr-fill="${(c.score / maxScore * 100).toFixed(0)}"></div></div>
      <span class="sr-cii-score ${cls}">${c.score}</span>
    </div>`;
  }).join('');
  _hydrateSitroomRuntimeVars(el);
}

/* ─── Intel Feed ─── */
async function loadSitroomIntelFeed() {
  const el = document.getElementById('sr-intel-feed');
  if (!el) return;
  // Filter news for Defense, Cyber, Geopolitics categories
  const d = await safeFetch('/api/sitroom/news?limit=30', {}, null);
  if (!d || !d.articles?.length) { el.innerHTML = '<div class="sr-empty">No intel data</div>'; return; }
  const intel = d.articles.filter(a => ['Defense', 'Cyber', 'Geopolitics', 'Disaster'].includes(a.category));
  if (!intel.length) { el.innerHTML = '<div class="sr-empty">No intel articles</div>'; return; }
  el.innerHTML = intel.slice(0, 20).map(a => `<div class="sr-intel-item">
    <span class="sr-intel-src">${escapeHtml(a.category)}</span>
    <div class="sr-intel-body">
      <a href="${escapeAttr(a.link || '#')}" target="_blank" rel="noopener" class="sr-intel-title">${escapeHtml(a.title)}</a>
      <div class="sr-intel-meta">${escapeHtml(a.source_name || '')}</div>
    </div>
  </div>`).join('');
}

/* ─── Status Dot ─── */
function _updateStatusDot(d) {
  const dot = document.getElementById('sr-status-dot');
  if (!dot) return;
  const hasData = (d.news_count || 0) > 0;
  dot.className = 'sr-status-dot ' + (hasData ? 'live' : '');
  dot.title = hasData ? 'Live data cached' : 'No data';
}

/* ─── Sector Heatmap ─── */
function renderSitroomSectorHeatmap(markets) {
  const el = document.getElementById('sitroom-sector-heatmap');
  if (!el) return;
  const sectors = markets.filter(m => m.market_type === 'sector');
  if (!sectors.length) { el.innerHTML = '<div class="sr-empty">No sector data</div>'; return; }
  el.innerHTML = sectors.map(s => {
    const ch = s.change_24h || 0;
    const tone = ch > 0.05 ? 'up' : ch < -0.05 ? 'down' : 'flat';
    const intensity = tone === 'flat' ? 1 : _srHeatIntensity(ch);
    return `<div class="sr-heatmap-cell" data-tone="${tone}" data-intensity="${intensity}">
      <span class="sr-heatmap-cell-name">${escapeHtml(s.symbol)}</span>
      <span class="sr-heatmap-cell-val" data-tone="${tone}">${ch >= 0 ? '+' : ''}${ch.toFixed(1)}%</span>
    </div>`;
  }).join('');
}

/* ─── Map Legend ─── */
function _updateMapLegend() {
  const el = document.getElementById('sr-map-legend');
  if (!el) return;
  const layers = {
    quakes: 'Quakes', weather: 'Weather',
    conflicts: 'Crises', aviation: 'Aircraft',
    volcanoes: 'Volcanoes', fires: 'Fires',
    nuclear: 'Nuclear', bases: 'Mil. Bases',
    cables: 'Cables', datacenters: 'Data Ctrs',
    pipelines: 'Pipelines', waterways: 'Waterways',
    spaceports: 'Spaceports', shipping: 'Shipping',
    ucdp: 'Armed Conflicts',
    airports: 'Airports', fincenters: 'Finance',
    mining: 'Mining', techHQs: 'Tech HQs',
  };
  const active = [];
  document.querySelectorAll('[data-sitroom-layer]').forEach(cb => {
    if (cb.checked && layers[cb.dataset.sitroomLayer]) {
      const label = layers[cb.dataset.sitroomLayer];
      active.push(`<span class="sr-legend-item"><span class="sr-legend-dot" data-layer="${escapeAttr(cb.dataset.sitroomLayer || '')}"></span>${label}</span>`);
    }
  });
  el.innerHTML = active.length ? `<span class="sr-legend-label">Active Layers</span>${active.join('')}` : '';
}

/* ─── Day/Night Terminator ─── */
let _sitroomDayNightCanvas = null;
function _renderDayNight() {
  const mapEl = document.getElementById('sitroom-map');
  if (!mapEl || !_sitroomMap) return;
  const checked = document.getElementById('sitroom-layer-daynight')?.checked;
  let canvas = _sitroomDayNightCanvas;
  if (!checked) {
    if (canvas) { canvas.remove(); _sitroomDayNightCanvas = null; }
    return;
  }
  if (!canvas) {
    canvas = document.createElement('canvas');
    canvas.className = 'sr-daynight-overlay';
    canvas.width = mapEl.offsetWidth; canvas.height = mapEl.offsetHeight;
    mapEl.parentElement.appendChild(canvas);
    _sitroomDayNightCanvas = canvas;
  }
  canvas.width = mapEl.offsetWidth; canvas.height = mapEl.offsetHeight;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Compute subsolar point
  const now = new Date();
  const dayOfYear = Math.floor((now - new Date(now.getFullYear(), 0, 0)) / 86400000);
  const declination = -23.44 * Math.cos((360 / 365) * (dayOfYear + 10) * Math.PI / 180);
  const hourAngle = ((now.getUTCHours() + now.getUTCMinutes() / 60) / 24 * 360) - 180;

  // Draw night overlay using map projection
  const bounds = _sitroomMap.getBounds();
  const w = canvas.width, h = canvas.height;
  ctx.fillStyle = 'rgba(0,0,20,0.5)';
  for (let px = 0; px < w; px += 4) {
    for (let py = 0; py < h; py += 4) {
      const lng = bounds.getWest() + (px / w) * (bounds.getEast() - bounds.getWest());
      const lat = bounds.getNorth() - (py / h) * (bounds.getNorth() - bounds.getSouth());
      const latR = lat * Math.PI / 180, decR = declination * Math.PI / 180;
      const ha = (lng - hourAngle) * Math.PI / 180;
      const sinAlt = Math.sin(latR) * Math.sin(decR) + Math.cos(latR) * Math.cos(decR) * Math.cos(ha);
      if (sinAlt < 0) ctx.fillRect(px, py, 4, 4);
    }
  }
}

/* ─── Threat Level (DEFCON-style composite) ─── */
function _updateThreatLevel(d) {
  const el = document.getElementById('sitroom-threat-level');
  if (!el) return;
  // Composite score from event counts
  let score = 0;
  score += Math.min(20, (d.earthquake_count || 0) * 2);
  score += Math.min(15, (d.weather_alert_count || 0));
  score += Math.min(25, (d.conflict_count || 0) * 3);
  score += Math.min(15, (d.fire_count || 0) / 10);
  score += Math.min(10, (d.disease_count || 0) * 2);
  score += Math.min(10, (d.outage_count || 0) * 3);
  // Space weather
  if (d.space_weather) {
    const g = d.space_weather.G || {}; const s = d.space_weather.S || {}; const r = d.space_weather.R || {};
    score += ((g.Scale || 0) + (s.Scale || 0) + (r.Scale || 0)) * 2;
  }
  // Map to DEFCON-style 1-5 (5 = lowest threat)
  let level = 5;
  if (score >= 60) level = 1;
  else if (score >= 40) level = 2;
  else if (score >= 25) level = 3;
  else if (score >= 10) level = 4;
  const labels = {1:'CRITICAL',2:'SEVERE',3:'ELEVATED',4:'GUARDED',5:'NORMAL'};
  el.textContent = labels[level];
  el.setAttribute('data-level', level);
}

/* ─── Internet Outages ─── */
async function loadSitroomOutages() {
  const d = await safeFetch('/api/sitroom/internet-outages', {}, null);
  const el = document.getElementById('sitroom-outages-list');
  if (!el) return;
  if (!d || !d.outages?.length) { el.innerHTML = '<div class="sr-empty">No internet disruptions</div>'; return; }
  el.innerHTML = d.outages.map(o => {
    const det = _parseSitroomDetailJson(o.detail_json);
    return `<div class="sitroom-event-item">
      <span class="sitroom-mag sitroom-mag-net">NET</span>
      <div class="sitroom-event-info">
        <div class="sitroom-event-title" title="${escapeAttr(o.title || '')}">${escapeHtml(o.title || 'Disruption')}</div>
        <div class="sitroom-event-meta">${det.country ? escapeHtml(det.country) : ''}${det.start ? ' | ' + escapeHtml(det.start) : ''}${det.scope ? ' | ' + escapeHtml(det.scope) : ''}</div>
      </div>
    </div>`;
  }).join('');
}

/* ─── Fear & Greed Gauge ─── */
function renderSitroomFearGreed(markets) {
  const el = document.getElementById('sitroom-fear-greed');
  if (!el) return;
  const fg = markets.find(m => m.symbol === 'FEAR_GREED');
  if (!fg) { el.innerHTML = '<div class="sr-empty">No Fear & Greed data</div>'; return; }
  const val = fg.price || 50;
  const label = fg.label || (val <= 25 ? 'Extreme Fear' : val <= 45 ? 'Fear' : val <= 55 ? 'Neutral' : val <= 75 ? 'Greed' : 'Extreme Greed');
  const tone = val <= 25 ? 'danger' : val <= 45 ? 'warn' : val <= 55 ? 'neutral' : 'good';
  // Needle rotation: 0=left (-90deg), 100=right (90deg)
  const deg = -90 + (val / 100) * 180;
  el.innerHTML = `<div class="sr-fg-gauge">
    <div class="sr-fg-arc"></div>
    <div class="sr-fg-needle"></div>
  </div>
  <div class="sr-fg-value" data-tone="${tone}">${val}</div>
  <div class="sr-fg-label">${escapeHtml(label.toUpperCase())}</div>`;
  el.querySelector('.sr-fg-gauge')?.style.setProperty('--sr-fg-rotation', `${deg}deg`);
}

/* ─── Fires ─── */
async function loadSitroomFires() {
  const d = await safeFetch('/api/sitroom/fires?limit=50', {}, null);
  const el = document.getElementById('sitroom-fires-list');
  if (!el) return;
  if (!d || !d.fires?.length) { el.innerHTML = '<div class="sr-empty">No fire data</div>'; return; }
  el.innerHTML = d.fires.slice(0, 30).map(f => {
    const det = _parseSitroomDetailJson(f.detail_json);
    const bright = f.magnitude ? f.magnitude.toFixed(0) + 'K' : '?';
    return `<div class="sitroom-event-item">
      <span class="sitroom-mag sitroom-mag-fire">${bright}</span>
      <div class="sitroom-event-info">
        <div class="sitroom-event-title">${escapeHtml(f.title || 'Fire detection')}</div>
        <div class="sitroom-event-meta">${f.lat?.toFixed(2)}, ${f.lng?.toFixed(2)}${det.acq_date ? ' | ' + escapeHtml(det.acq_date) : ''}</div>
      </div>
    </div>`;
  }).join('');
}

/* ─── Disease Outbreaks ─── */
async function loadSitroomDiseases() {
  const d = await safeFetch('/api/sitroom/diseases', {}, null);
  const el = document.getElementById('sitroom-diseases-list');
  if (!el) return;
  if (!d || !d.outbreaks?.length) { el.innerHTML = '<div class="sr-empty">No outbreak data</div>'; return; }
  el.innerHTML = d.outbreaks.map(o => {
    const det = _parseSitroomDetailJson(o.detail_json);
    return `<div class="sitroom-event-item">
      <div class="sitroom-event-info">
        <div class="sitroom-event-title" title="${escapeAttr(o.title || '')}">${escapeHtml(o.title || 'Outbreak')}</div>
        <div class="sitroom-event-meta">${det.published ? escapeHtml(det.published) : ''}</div>
      </div>
      ${o.source_url ? `<a href="${escapeAttr(o.source_url)}" target="_blank" rel="noopener" class="sitroom-event-link">&#8599;</a>` : ''}
    </div>`;
  }).join('');
}

/* ─── Panel Drag Reorder ─── */
function _initPanelDragReorder() {
  const grid = document.getElementById('sr-cards-anchor');
  if (!grid) return;
  grid.querySelectorAll('.sr-card').forEach((card, i) => {
    card.setAttribute('draggable', 'false');
    card.dataset.panelIdx = i;
    card.addEventListener('dragstart', e => {
      if (!_sitroomLayoutEdit) {
        e.preventDefault();
        return;
      }
      card.classList.add('dragging');
      e.dataTransfer.setData('text/plain', i);
      e.dataTransfer.effectAllowed = 'move';
    });
    card.addEventListener('dragend', () => {
      card.classList.remove('dragging');
      grid.querySelectorAll('.sr-card').forEach(c => c.classList.remove('drag-over'));
      _savePanelOrder();
    });
    card.addEventListener('dragover', e => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; card.classList.add('drag-over'); });
    card.addEventListener('dragleave', () => card.classList.remove('drag-over'));
    card.addEventListener('drop', e => {
      e.preventDefault(); card.classList.remove('drag-over');
      const fromIdx = parseInt(e.dataTransfer.getData('text/plain'));
      const cards = [...grid.querySelectorAll('.sr-card')];
      const fromCard = cards[fromIdx];
      if (fromCard && fromCard !== card) {
        const rect = card.getBoundingClientRect();
        const after = e.clientY > rect.top + rect.height / 2;
        if (after) card.after(fromCard); else card.before(fromCard);
      }
    });
  });
}

function _savePanelOrder() {
  const grid = document.getElementById('sr-cards-anchor');
  if (!grid) return;
  const order = [...grid.querySelectorAll('.sr-card')].map(c => _getSitroomPanelId(c));
  try { localStorage.setItem('sr-panel-order', JSON.stringify(order)); } catch(e) {}
}

function _restorePanelOrder() {
  const saved = _readSitroomStorageJson('sr-panel-order', []);
  if (!Array.isArray(saved) || !saved.length) return;
  const grid = document.getElementById('sr-cards-anchor');
  if (!grid) return;
  const cards = [...grid.querySelectorAll('.sr-card')];
  const byTitle = {};
  cards.forEach(c => {
    const panelId = _getSitroomPanelId(c);
    if (panelId) byTitle[panelId] = c;
  });
  saved.forEach(title => {
    if (byTitle[title]) grid.appendChild(byTitle[title]);
  });
}

/* ─── Map Fullscreen ─── */
function _toggleMapFullscreen() {
  const wrap = document.querySelector('.sr-map-wrap');
  if (!wrap) return;
  wrap.classList.toggle('fullscreen');
  setTimeout(_sitroomResizeMap, 100);
  setTimeout(_sitroomResizeMap, 500);
}

/* ─── 3D Globe Toggle ─── */
function _toggleGlobe() {
  if (!_sitroomMap) return;
  _sitroomIsGlobe = !_sitroomIsGlobe;
  const btn = document.getElementById('sr-globe-toggle');
  try {
    if (_sitroomIsGlobe) {
      _sitroomMap.setProjection({type: 'globe'});
      if (btn) { btn.textContent = '2D'; btn.classList.add('active'); }
    } else {
      _sitroomMap.setProjection({type: 'mercator'});
      if (btn) { btn.textContent = '3D'; btn.classList.remove('active'); }
    }
    setTimeout(_sitroomResizeMap, 200);
  } catch(e) {
    // Globe projection not supported in this MapLibre build
    if (btn) btn.hidden = true;
  }
}

/* ─── Event Timeline ─── */
async function loadSitroomTimeline() {
  const el = document.getElementById('sitroom-timeline');
  if (!el) return;
  const d = await safeFetch('/api/sitroom/events?limit=50', {}, null);
  if (!d || !d.events?.length) { el.innerHTML = '<div class="sr-empty">No events for timeline</div>'; return; }

  // Sort by cached_at descending, take latest 20
  const events = d.events.slice(0, 20);
  const html = '<div class="sr-timeline-track">' + events.map(ev => {
    const severity = ev.magnitude > 5 ? 'high' : ev.magnitude > 3 ? 'med' : 'low';
    const typeLabel = (ev.event_type || '').replace(/_/g, ' ');
    let timeStr = '';
    if (ev.cached_at) {
      try { timeStr = new Date(ev.cached_at).toLocaleTimeString('en-US', {hour:'2-digit',minute:'2-digit',hour12:false}); } catch(e) {}
    }
    return `<div class="sr-timeline-event" data-severity="${severity}">
      <div class="sr-timeline-time">${escapeHtml(timeStr)}</div>
      <div class="sr-timeline-title">${escapeHtml(ev.title || 'Event')}</div>
      <div class="sr-timeline-type">${escapeHtml(typeLabel)}</div>
    </div>`;
  }).join('') + '</div>';
  el.innerHTML = html;
}

/* ─── Auto-Refresh Progress Bar ─── */
function _initRefreshBar() {
  const bar = document.getElementById('sr-refresh-bar');
  if (bar) bar.classList.add('active');
}

/* ─── World Clock ─── */
const _WORLD_CLOCK_ZONES = [
  {city:'New York',tz:'America/New_York'},{city:'London',tz:'Europe/London'},
  {city:'Paris',tz:'Europe/Paris'},{city:'Moscow',tz:'Europe/Moscow'},
  {city:'Dubai',tz:'Asia/Dubai'},{city:'Mumbai',tz:'Asia/Kolkata'},
  {city:'Beijing',tz:'Asia/Shanghai'},{city:'Tokyo',tz:'Asia/Tokyo'},
  {city:'Sydney',tz:'Australia/Sydney'},{city:'Los Angeles',tz:'America/Los_Angeles'},
  {city:'Chicago',tz:'America/Chicago'},{city:'Sao Paulo',tz:'America/Sao_Paulo'},
];

function _initSitroomWorldClock() {
  const el = document.getElementById('sitroom-world-clock');
  if (!el) return;
  const render = () => {
    const now = new Date();
    el.innerHTML = _WORLD_CLOCK_ZONES.map(z => {
      try {
        const opts = {timeZone: z.tz, hour: '2-digit', minute: '2-digit', hour12: false};
        const dateOpts = {timeZone: z.tz, month: 'short', day: 'numeric'};
        const time = now.toLocaleTimeString('en-US', opts);
        const date = now.toLocaleDateString('en-US', dateOpts);
        const hour = parseInt(time.split(':')[0]);
        const isNight = hour < 6 || hour >= 20;
        return `<div class="sr-clock-cell${isNight ? ' night' : ''}">
          <div class="sr-clock-city">${z.city}</div>
          <div class="sr-clock-time">${time}</div>
          <div class="sr-clock-date">${date}</div>
        </div>`;
      } catch(e) { return ''; }
    }).join('');
  };
  render();
  if (_sitroomWorldClockTimer) {
    clearInterval(_sitroomWorldClockTimer);
    _sitroomWorldClockTimer = null;
  }
  window.NomadShellRuntime?.stopInterval('sitroom.world-clock');
  if (window.NomadShellRuntime) {
    _sitroomWorldClockTimer = window.NomadShellRuntime.startInterval('sitroom.world-clock', render, 30000, {
      tabId: 'situation-room',
      requireVisible: true,
    });
    return;
  }
  _sitroomWorldClockTimer = setInterval(() => {
    if (!_isSitroomActive() || document.hidden) return;
    render();
  }, 30000);
}

/* ─── Search Modal (desk-local search) ─── */
function _initSitroomSearch() {
  document.addEventListener('keydown', e => {
    // Don't handle shortcuts when typing in inputs
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT' || e.target.isContentEditable) {
      if (e.key === 'Escape') {
        _toggleSitroomSearch(false);
        _closeStoryModal();
      }
      return;
    }
    const srTab = document.getElementById('tab-situation-room');
    if (srTab?.classList.contains('active') && e.key === '/' && !e.ctrlKey && !e.metaKey && !e.altKey) {
      e.preventDefault();
      _toggleSitroomSearch(true);
    }
    if (e.key === 'Escape') {
      _toggleSitroomSearch(false);
      _closeSitroomAnalysis();
      const fp = document.getElementById('sr-feed-panel');
      if (fp) fp.hidden = true;
    }
    // Keyboard shortcuts (only when SR tab is active)
    if (!srTab?.classList.contains('active')) return;
    if (e.key === 'f' || e.key === 'F') _toggleMapFullscreen();
    if (e.key === 'r' || e.key === 'R') refreshSitroomFeeds();
  });
}

function _toggleSitroomSearch(show) {
  const overlay = document.getElementById('sr-search-overlay');
  const input = document.getElementById('sr-search-input');
  if (!overlay) return;
  overlay.hidden = !show;
  if (show && input) { input.value = ''; input.focus(); document.getElementById('sr-search-results').innerHTML = ''; }
}

let _searchDebounce = null;
async function _sitroomDoSearch(query) {
  const results = document.getElementById('sr-search-results');
  if (!results) return;
  if (!query || query.length < 2) { results.innerHTML = ''; return; }

  const [d, ev] = await Promise.all([
    safeFetch('/api/sitroom/news?limit=20&category=', {}, null),
    safeFetch('/api/sitroom/events?limit=100', {}, null)
  ]);
  const q = query.toLowerCase();
  let html = '';

  // Search news
  if (d?.articles) {
    d.articles.filter(a => (a.title || '').toLowerCase().includes(q)).slice(0, 8).forEach(a => {
      html += `<button type="button" class="sr-search-result" data-sitroom-action="open-story"
        data-story-title="${escapeAttr(a.title || '')}"
        data-story-category="${escapeAttr(a.category || 'News')}"
        data-story-link="${escapeAttr(a.link || '#')}"
        data-story-description="${escapeAttr(a.description || '')}"
        data-story-source="${escapeAttr(a.source_name || '')}"
        data-story-published="${escapeAttr(a.published || '')}">
        <span class="sr-search-result-type">${escapeHtml(a.category || 'NEWS')}</span>
        <span class="sr-search-result-title">${escapeHtml(a.title)}</span>
      </button>`;
    });
  }

  // Search events
  if (ev?.events) {
    ev.events.filter(e => (e.title || '').toLowerCase().includes(q)).slice(0, 5).forEach(e => {
      html += `<button type="button" class="sr-search-result" data-sitroom-action="fly-search-result" data-lng="${escapeAttr(e.lng || 0)}" data-lat="${escapeAttr(e.lat || 0)}">
        <span class="sr-search-result-type sr-search-result-type-event">${escapeHtml(e.event_type || 'EVENT')}</span>
        <span class="sr-search-result-title">${escapeHtml(e.title)}</span>
      </button>`;
    });
  }

  results.innerHTML = html || '<div class="sr-empty sr-empty-padded">No results</div>';
}

/* ─── UTC Clock ─── */
function _initSitroomClock() {
  const el = document.getElementById('sr-utc-clock');
  if (!el) return;
  const tick = () => {
    const now = new Date();
    el.textContent = now.toUTCString().replace('GMT', 'UTC');
  };
  tick();
  if (_sitroomClockTimer) {
    clearInterval(_sitroomClockTimer);
    _sitroomClockTimer = null;
  }
  window.NomadShellRuntime?.stopInterval('sitroom.utc-clock');
  if (window.NomadShellRuntime) {
    _sitroomClockTimer = window.NomadShellRuntime.startInterval('sitroom.utc-clock', tick, 1000, {
      tabId: 'situation-room',
      requireVisible: true,
    });
    return;
  }
  _sitroomClockTimer = setInterval(() => {
    if (!_isSitroomActive() || document.hidden) return;
    tick();
  }, 1000);
}

/* ─── Radiation Watch ─── */
async function loadSitroomRadiation() {
  const d = await safeFetch('/api/sitroom/radiation', {}, null);
  const el = document.getElementById('sitroom-radiation');
  if (!el) return;
  if (!d || !d.readings?.length) { el.innerHTML = '<div class="sr-empty">No radiation data</div>'; return; }
  el.innerHTML = d.readings.slice(0, 20).map(r => {
    const det = _parseSitroomDetailJson(r.detail_json);
    const val = r.magnitude || 0;
    const cls = val > 100 ? 'sitroom-mag-high' : val > 50 ? 'sitroom-mag-med' : 'sitroom-mag-low';
    return `<div class="sitroom-event-item">
      <span class="sitroom-mag ${cls}">${val.toFixed(0)}</span>
      <div class="sitroom-event-info">
        <div class="sitroom-event-title">${escapeHtml(det.location || r.title || 'Reading')}</div>
        <div class="sitroom-event-meta">${det.unit || 'cpm'}${det.captured_at ? ' | ' + escapeHtml(det.captured_at.substring(0, 16)) : ''}</div>
      </div>
    </div>`;
  }).join('');
}

/* ─── GDELT Trending ─── */
async function loadSitroomTrending() {
  const d = await safeFetch('/api/sitroom/trending', {}, null);
  const el = document.getElementById('sitroom-trending');
  if (!el) return;
  if (!d || !d.topics?.length) { el.innerHTML = '<div class="sr-empty">No trending data</div>'; return; }
  el.innerHTML = d.topics.map(t => {
    const det = _parseSitroomDetailJson(t.detail_json);
    const tone = t.magnitude || 0;
    const toneColor = tone > 2 ? '#4aedc4' : tone < -2 ? '#e05050' : '#888';
    return `<div class="sitroom-news-item">
      <span class="sitroom-news-cat" data-tone="${tone > 2 ? 'positive' : tone < -2 ? 'negative' : 'neutral'}">${tone > 0 ? '+' : ''}${tone.toFixed(1)}</span>
      <div class="sitroom-news-body">
        <a href="${escapeAttr(t.source_url || '#')}" target="_blank" rel="noopener" class="sitroom-news-title">${escapeHtml(t.title || '')}</a>
        <div class="sitroom-news-meta">${escapeHtml(det.domain || '')}${det.seendate ? ' | ' + escapeHtml(det.seendate.substring(0, 8)) : ''}</div>
      </div>
    </div>`;
  }).join('');
}

/* ─── Sanctions & Trade ─── */
async function loadSitroomSanctions() {
  const d = await safeFetch('/api/sitroom/sanctions', {}, null);
  const el = document.getElementById('sitroom-sanctions');
  if (!el) return;
  if (!d || !d.items?.length) { el.innerHTML = '<div class="sr-empty">No sanctions/trade data</div>'; return; }
  el.innerHTML = d.items.map(s => {
    const det = _parseSitroomDetailJson(s.detail_json);
    return `<div class="sitroom-event-item">
      <div class="sitroom-event-info">
        <div class="sitroom-event-title" title="${escapeAttr(s.title || '')}">${escapeHtml(s.title || '')}</div>
        <div class="sitroom-event-meta">${escapeHtml(det.category || '')}${det.published ? ' | ' + escapeHtml(det.published) : ''}</div>
      </div>
      ${s.source_url ? `<a href="${escapeAttr(s.source_url)}" target="_blank" rel="noopener" class="sitroom-event-link">&#8599;</a>` : ''}
    </div>`;
  }).join('');
}

/* ─── Critical Alert System ─── */
async function _checkCriticalAlerts() {
  const stack = document.getElementById('sr-alert-stack');
  if (!stack) return;

  // Check for M6+ earthquakes
  const eq = await safeFetch('/api/sitroom/earthquakes?min_magnitude=6', {}, null);
  if (eq?.earthquakes) {
    eq.earthquakes.forEach(q => {
      const key = 'eq:' + q.event_id;
      if (_sitroomAlertsSeen.has(key)) return;
      _sitroomAlertsSeen.add(key);
      _showSitroomAlert('critical', 'EARTHQUAKE M' + (q.magnitude||0).toFixed(1) + ' — ' + (q.title||'Unknown'));
    });
  }

  // Check for extreme weather
  const wx = await safeFetch('/api/sitroom/weather-alerts', {}, null);
  if (wx?.alerts) {
    wx.alerts.slice(0, 3).forEach(a => {
    const det = _parseSitroomDetailJson(a.detail_json);
      if (det.severity !== 'Extreme') return;
      const key = 'wx:' + a.event_id;
      if (_sitroomAlertsSeen.has(key)) return;
      _sitroomAlertsSeen.add(key);
      _showSitroomAlert('warning', 'EXTREME WEATHER — ' + (a.title||'Alert'));
    });
  }
}

function _showSitroomAlert(type, message) {
  const stack = document.getElementById('sr-alert-stack');
  if (!stack) return;
  const toast = document.createElement('div');
  toast.className = 'sr-alert-toast ' + (type === 'critical' ? '' : type);
  const icon = type === 'critical' ? '&#9888;' : type === 'warning' ? '&#9888;' : '&#8505;';
  toast.innerHTML = `<span class="sr-alert-icon">${icon}</span><span class="sr-alert-text">${escapeHtml(message)}</span><button type="button" class="sr-alert-dismiss" aria-label="Dismiss alert">&#10005;</button>`;
  toast.querySelector('.sr-alert-dismiss')?.addEventListener('click', () => {
    if (toast.parentElement) toast.remove();
  });
  stack.appendChild(toast);
  // Auto-dismiss after 15s
  setTimeout(() => { if (toast.parentElement) toast.remove(); }, 15000);
}

/* ─── Macro Stress Indicators ─── */
async function loadSitroomMacroStress() {
  const d = await safeFetch('/api/sitroom/macro-stress', {}, null);
  const el = document.getElementById('sitroom-macro');
  if (!el) return;
  if (!d || !d.indicators?.length) { el.innerHTML = '<div class="sr-empty">No macro data</div>'; return; }
  el.innerHTML = d.indicators.map(i => {
    const det = _parseSitroomDetailJson(i.detail_json);
    const val = i.magnitude || 0;
    return `<div class="sr-macro-row">
      <span class="sr-macro-label">${escapeHtml(i.title || det.series || '')}</span>
      <span class="sr-macro-val">${val.toFixed(2)}</span>
    </div>`;
  }).join('');
}

/* ─── Forex Card ─── */
async function loadSitroomForex() {
  const d = await safeFetch('/api/sitroom/forex', {}, null);
  const el = document.getElementById('sitroom-forex');
  if (!el) return;
  if (!d || !d.pairs?.length) { el.innerHTML = '<div class="sr-empty">No forex data</div>'; return; }
  el.innerHTML = d.pairs.map(m => {
    const ch = m.change_24h || 0;
    const cls = ch >= 0 ? 'sitroom-market-up' : 'sitroom-market-down';
    return `<div class="sitroom-market-card ${cls}">
      <div class="sitroom-market-symbol">${escapeHtml(m.symbol)}</div>
      <div class="sitroom-market-price">${Number(m.price).toFixed(4)}</div>
      <div class="sitroom-market-change">${ch >= 0 ? '&#9650;' : '&#9660;'} ${Math.abs(ch).toFixed(2)}%</div>
    </div>`;
  }).join('');
}

/* ─── Crypto Sectors ─── */
async function loadSitroomCryptoSectors() {
  const d = await safeFetch('/api/sitroom/crypto-sectors', {}, null);
  const el = document.getElementById('sitroom-crypto-sectors');
  if (!el) return;
  const all = [...(d?.crypto || []), ...(d?.stablecoins || [])];
  if (!all.length) { el.innerHTML = '<div class="sr-empty">No crypto data</div>'; return; }
  el.innerHTML = all.map(m => {
    const ch = m.change_24h || 0;
    const cls = ch >= 0 ? 'sitroom-market-up' : 'sitroom-market-down';
    const price = m.price >= 1 ? '$' + Number(m.price).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2}) : '$' + Number(m.price).toFixed(4);
    return `<div class="sitroom-market-card ${cls}">
      <div class="sitroom-market-symbol">${escapeHtml(m.symbol)}</div>
      <div class="sitroom-market-price">${price}</div>
      <div class="sitroom-market-change">${ch >= 0 ? '&#9650;' : '&#9660;'} ${Math.abs(ch).toFixed(1)}%</div>
    </div>`;
  }).join('');
}

/* ─── News Sentiment ─── */
async function loadSitroomSentiment() {
  const d = await safeFetch('/api/sitroom/news-sentiment', {}, null);
  const el = document.getElementById('sitroom-sentiment');
  if (!el || !d) return;
  const total = d.total || 1;
  const posPct = ((d.positive || 0) / total * 100).toFixed(0);
  const negPct = ((d.negative || 0) / total * 100).toFixed(0);
  const neuPct = ((d.neutral || 0) / total * 100).toFixed(0);
  const score = d.sentiment_score || 0;
  const tone = score > 10 ? 'good' : score < -10 ? 'danger' : 'neutral';
  const label = score > 20 ? 'BULLISH' : score > 5 ? 'POSITIVE' : score < -20 ? 'BEARISH' : score < -5 ? 'NEGATIVE' : 'NEUTRAL';
  el.innerHTML = `<div class="sr-sentiment-score" data-tone="${tone}">${score > 0 ? '+' : ''}${score.toFixed(0)}</div>
    <div class="sr-sentiment-label">${label}</div>
    <div class="sr-sentiment-row">
      <div class="sr-sentiment-bar">
        <div class="sr-sentiment-pos" data-sr-width="${posPct}">${posPct}%</div>
        <div class="sr-sentiment-neu" data-sr-width="${neuPct}">${neuPct}%</div>
        <div class="sr-sentiment-neg" data-sr-width="${negPct}">${negPct}%</div>
      </div>
    </div>`;
  _hydrateSitroomRuntimeVars(el);
}

/* ─── Generic Category Card Loader ─── */
async function _loadCategoryCard(elId, category) {
  const d = await safeFetch('/api/sitroom/category-feed/' + encodeURIComponent(category), {}, null);
  const el = document.getElementById(elId);
  if (!el) return;
  if (!d || !d.articles?.length) { el.innerHTML = '<div class="sr-empty">No ' + category + ' data</div>'; return; }
  el.innerHTML = d.articles.map(a => `<div class="sitroom-news-item">
    <span class="sitroom-news-cat" data-cat="${escapeAttr(category)}">${escapeHtml(a.source_name || category)}</span>
    <div class="sitroom-news-body">
      <a href="${escapeAttr(a.link || '#')}" target="_blank" rel="noopener" class="sitroom-news-title">${escapeHtml(a.title)}</a>
    </div>
  </div>`).join('');
}

/* ─── Population Exposure ─── */
async function loadSitroomPopExposure() {
  const d = await safeFetch('/api/sitroom/pop-exposure', {}, null);
  const el = document.getElementById('sitroom-pop-exposure');
  if (!el) return;
  if (!d || !d.exposures?.length) { el.innerHTML = '<div class="sr-empty">No M5+ earthquakes for exposure calc</div>'; return; }
  el.innerHTML = '<div class="sr-humanitarian-grid">' + d.exposures.map(e =>
    `<div class="sr-humanitarian-stat">
      <div class="sr-humanitarian-val sr-humanitarian-val-large" data-tone="${e.magnitude >= 6 ? 'danger' : 'warn'}">${(e.estimated_population/1000).toFixed(0)}K</div>
      <div class="sr-humanitarian-lbl">M${e.magnitude.toFixed(1)} ~${e.radius_km}km</div>
    </div>`
  ).join('') + '</div>';
}

/* ─── Daily Market Brief ─── */
function loadSitroomMarketBriefInit() { /* loaded on demand via button */ }
async function _generateMarketBrief() {
  const el = document.getElementById('sitroom-market-brief');
  if (!el) return;
  el.innerHTML = '<div class="sr-empty"><div class="sr-radar"></div>Generating brief...</div>';
  try {
    const d = await apiPost('/api/sitroom/market-brief');
    if (d.brief) {
      let h = escapeHtml(d.brief);
      h = h.replace(/^### (.*?)$/gm, '<h4 class="sr-market-brief-subhead">$1</h4>');
      h = h.replace(/^## (.*?)$/gm, '<h3 class="sr-market-brief-head">$1</h3>');
      h = h.replace(/\n/g, '<br>');
      el.innerHTML = '<div class="sr-market-brief">' + h + '</div>';
    }
  } catch(e) { el.innerHTML = '<div class="sr-empty">Failed to generate brief</div>'; }
}

/* ─── Generic Keyword Card Loader ─── */
async function _loadKeywordCard(elId, apiUrl, dataKey) {
  const d = await safeFetch(apiUrl, {}, null);
  const el = document.getElementById(elId);
  if (!el) return;
  const items = d ? (d[dataKey] || []) : [];
  if (!items.length) { el.innerHTML = '<div class="sr-empty">No data available</div>'; return; }
  el.innerHTML = items.map(a => `<div class="sitroom-news-item">
    <span class="sitroom-news-cat sitroom-news-cat-muted">${escapeHtml(a.source_name || '')}</span>
    <div class="sitroom-news-body">
      <a href="${escapeAttr(a.link || '#')}" target="_blank" rel="noopener" class="sitroom-news-title">${escapeHtml(a.title)}</a>
    </div>
  </div>`).join('');
}

/* ─── Security Advisories ─── */
async function loadSitroomSecAdvisories() {
  const d = await safeFetch('/api/sitroom/security-advisories', {}, null);
  const el = document.getElementById('sitroom-sec-advisories');
  if (!el) return;
  if (!d || !d.advisories?.length) { el.innerHTML = '<div class="sr-empty">No security advisories</div>'; return; }
  el.innerHTML = d.advisories.map(a => `<div class="sitroom-event-item sitroom-sev-severe">
    <div class="sitroom-event-info">
      <div class="sitroom-event-title">${escapeHtml(a.title)}</div>
      <div class="sitroom-event-meta">${escapeHtml(a.source_name || '')}</div>
    </div>
    ${a.link ? `<a href="${escapeAttr(a.link)}" target="_blank" rel="noopener" class="sitroom-event-link">&#8599;</a>` : ''}
  </div>`).join('');
}

/* ─── Central Bank Watch ─── */
async function loadSitroomCentralBanks() {
  const d = await safeFetch('/api/sitroom/central-banks', {}, null);
  const el = document.getElementById('sitroom-central-banks');
  if (!el) return;
  if (!d || !d.articles?.length) { el.innerHTML = '<div class="sr-empty">No central bank data</div>'; return; }
  el.innerHTML = d.articles.map(a => `<div class="sitroom-news-item">
    <span class="sitroom-news-cat" data-cat="Central Bank">${escapeHtml(a.source_name || '')}</span>
    <div class="sitroom-news-body">
      <a href="${escapeAttr(a.link || '#')}" target="_blank" rel="noopener" class="sitroom-news-title">${escapeHtml(a.title)}</a>
    </div>
  </div>`).join('');
}

/* ─── AI Research (ArXiv) ─── */
async function loadSitroomArxiv() {
  const d = await safeFetch('/api/sitroom/ai-research', {}, null);
  const el = document.getElementById('sitroom-arxiv');
  if (!el) return;
  if (!d || !d.papers?.length) { el.innerHTML = '<div class="sr-empty">No ArXiv data</div>'; return; }
  el.innerHTML = d.papers.map(p => `<div class="sitroom-news-item">
    <span class="sitroom-news-cat" data-cat="Arxiv">AI</span>
    <div class="sitroom-news-body">
      <a href="${escapeAttr(p.link || '#')}" target="_blank" rel="noopener" class="sitroom-news-title">${escapeHtml(p.title)}</a>
    </div>
  </div>`).join('');
}

/* ─── Layoffs Tracker ─── */
async function loadSitroomLayoffs() {
  const d = await safeFetch('/api/sitroom/layoffs', {}, null);
  const el = document.getElementById('sitroom-layoffs');
  if (!el) return;
  if (!d || !d.layoffs?.length) { el.innerHTML = '<div class="sr-empty">No layoff data</div>'; return; }
  el.innerHTML = d.layoffs.map(l => `<div class="sitroom-news-item">
    <span class="sitroom-news-cat" data-cat="Layoff">CUT</span>
    <div class="sitroom-news-body">
      <a href="${escapeAttr(l.link || '#')}" target="_blank" rel="noopener" class="sitroom-news-title">${escapeHtml(l.title)}</a>
      <div class="sitroom-news-meta">${escapeHtml(l.source_name || '')}</div>
    </div>
  </div>`).join('');
}

/* ─── Airline Intelligence ─── */
async function loadSitroomAirline() {
  const d = await safeFetch('/api/sitroom/airline-intel', {}, null);
  const el = document.getElementById('sitroom-airline');
  if (!el) return;
  if (!d || !d.articles?.length) { el.innerHTML = '<div class="sr-empty">No airline data</div>'; return; }
  el.innerHTML = d.articles.map(a => `<div class="sitroom-news-item">
    <span class="sitroom-news-cat" data-cat="Airline">AIR</span>
    <div class="sitroom-news-body">
      <a href="${escapeAttr(a.link || '#')}" target="_blank" rel="noopener" class="sitroom-news-title">${escapeHtml(a.title)}</a>
      <div class="sitroom-news-meta">${escapeHtml(a.source_name || '')}</div>
    </div>
  </div>`).join('');
}

/* ─── Supply Chain ─── */
async function loadSitroomSupplyChain() {
  const d = await safeFetch('/api/sitroom/supply-chain', {}, null);
  const el = document.getElementById('sitroom-supplychain');
  if (!el) return;
  if (!d || !d.articles?.length) { el.innerHTML = '<div class="sr-empty">No supply chain data</div>'; return; }
  el.innerHTML = d.articles.map(a => `<div class="sitroom-news-item">
    <span class="sitroom-news-cat" data-cat="Supply Chain">LOG</span>
    <div class="sitroom-news-body">
      <a href="${escapeAttr(a.link || '#')}" target="_blank" rel="noopener" class="sitroom-news-title">${escapeHtml(a.title)}</a>
      <div class="sitroom-news-meta">${escapeHtml(a.source_name || '')}</div>
    </div>
  </div>`).join('');
}

/* ─── Product Hunt ─── */
async function loadSitroomProductHunt() {
  const d = await safeFetch('/api/sitroom/product-hunt', {}, null);
  const el = document.getElementById('sitroom-producthunt');
  if (!el) return;
  if (!d || !d.products?.length) { el.innerHTML = '<div class="sr-empty">No Product Hunt data</div>'; return; }
  el.innerHTML = d.products.map(p => `<div class="sitroom-news-item">
    <span class="sitroom-news-cat" data-cat="Product Hunt">PH</span>
    <div class="sitroom-news-body">
      <a href="${escapeAttr(p.link || '#')}" target="_blank" rel="noopener" class="sitroom-news-title">${escapeHtml(p.title)}</a>
    </div>
  </div>`).join('');
}

/* ─── Earnings & Revenue ─── */
async function loadSitroomEarnings() {
  const d = await safeFetch('/api/sitroom/earnings', {}, null);
  const el = document.getElementById('sitroom-earnings');
  if (!el) return;
  if (!d || !d.earnings?.length) { el.innerHTML = '<div class="sr-empty">No earnings data</div>'; return; }
  el.innerHTML = d.earnings.map(e => `<div class="sitroom-news-item">
    <span class="sitroom-news-cat" data-cat="Finance">${escapeHtml(e.source_name || '')}</span>
    <div class="sitroom-news-body">
      <a href="${escapeAttr(e.link || '#')}" target="_blank" rel="noopener" class="sitroom-news-title">${escapeHtml(e.title)}</a>
    </div>
  </div>`).join('');
}

/* ─── GitHub Trending ─── */
async function loadSitroomGithub() {
  const d = await safeFetch('/api/sitroom/github-trending', {}, null);
  const el = document.getElementById('sitroom-github');
  if (!el) return;
  if (!d || !d.repos?.length) { el.innerHTML = '<div class="sr-empty">No GitHub data</div>'; return; }
  el.innerHTML = d.repos.map(r => {
    const det = _parseSitroomDetailJson(r.detail_json);
    return `<div class="sitroom-news-item">
      <span class="sitroom-news-cat" data-cat="GitHub">${escapeHtml(det.language || '?')}</span>
      <div class="sitroom-news-body">
        <a href="${escapeAttr(r.source_url || '#')}" target="_blank" rel="noopener" class="sitroom-news-title">${escapeHtml(r.title || '')}</a>
        <div class="sitroom-news-meta">${(r.magnitude||0).toLocaleString()} stars${det.forks ? ' | ' + det.forks + ' forks' : ''}</div>
      </div>
    </div>`;
  }).join('');
}

/* ─── Fuel Prices ─── */
async function loadSitroomFuel() {
  const d = await safeFetch('/api/sitroom/fuel-prices', {}, null);
  const el = document.getElementById('sitroom-fuel');
  if (!el) return;
  if (!d || !d.prices?.length) { el.innerHTML = '<div class="sr-empty">No fuel data</div>'; return; }
  el.innerHTML = d.prices.map(p => {
    const det = _parseSitroomDetailJson(p.detail_json);
    return `<div class="sr-fuel-card">
      <div class="sr-fuel-value">$${(p.magnitude||0).toFixed(2)}</div>
      <div class="sr-fuel-label">${escapeHtml(p.title || 'US GASOLINE')}</div>
      <div class="sr-fuel-meta">${escapeHtml(det.period || '')}</div>
    </div>`;
  }).join('');
}

/* ─── Intelligence Gap ─── */
async function loadSitroomIntelGap() {
  const d = await safeFetch('/api/sitroom/intelligence-gap', {}, null);
  const el = document.getElementById('sitroom-intel-gap');
  if (!el) return;
  if (!d || !d.gaps?.length) { el.innerHTML = '<div class="sr-empty">No gap data</div>'; return; }
  el.innerHTML = d.gaps.map(g => {
    const ageStr = g.age ? (g.age < 60 ? g.age + 's' : g.age < 3600 ? Math.floor(g.age/60) + 'm' : Math.floor(g.age/3600) + 'h') : 'never';
    return `<div class="sr-gap-row">
      <span class="sr-gap-dot ${g.status}"></span>
      <span class="sr-gap-label">${escapeHtml(g.label)}</span>
      <span class="sr-gap-age">${ageStr}</span>
    </div>`;
  }).join('');
}

/* ─── Humanitarian Summary ─── */
async function loadSitroomHumanitarian() {
  const d = await safeFetch('/api/sitroom/humanitarian-summary', {}, null);
  const el = document.getElementById('sitroom-humanitarian');
  if (!el) return;
  if (!d) { el.innerHTML = '<div class="sr-empty">No data</div>'; return; }
  el.innerHTML = `<div class="sr-humanitarian-grid">
    <div class="sr-humanitarian-stat"><div class="sr-humanitarian-val">${d.active_conflicts || 0}</div><div class="sr-humanitarian-lbl">Conflicts</div></div>
    <div class="sr-humanitarian-stat"><div class="sr-humanitarian-val">${d.active_fires || 0}</div><div class="sr-humanitarian-lbl">Fires</div></div>
    <div class="sr-humanitarian-stat"><div class="sr-humanitarian-val">${d.severe_weather || 0}</div><div class="sr-humanitarian-lbl">Weather</div></div>
    <div class="sr-humanitarian-stat"><div class="sr-humanitarian-val">${d.significant_quakes || 0}</div><div class="sr-humanitarian-lbl">M5+ Quakes</div></div>
    <div class="sr-humanitarian-stat"><div class="sr-humanitarian-val">${d.disease_outbreaks || 0}</div><div class="sr-humanitarian-lbl">Outbreaks</div></div>
    <div class="sr-humanitarian-stat"><div class="sr-humanitarian-val">${d.displacement_records || 0}</div><div class="sr-humanitarian-lbl">Displaced</div></div>
  </div>`;
}

/* ─── Big Mac Index ─── */
async function loadSitroomBigMac() {
  const d = await safeFetch('/api/sitroom/bigmac', {}, null);
  const el = document.getElementById('sitroom-bigmac');
  if (!el) return;
  if (!d || !d.countries?.length) { el.innerHTML = '<div class="sr-empty">No Big Mac data</div>'; return; }
  const usBM = d.countries.find(c => c.title === 'United States');
  const usPrice = usBM ? usBM.magnitude : 5.69;
  el.innerHTML = d.countries.map(c => {
    const price = c.magnitude || 0;
    const ppp = ((price - usPrice) / usPrice * 100).toFixed(0);
    const tone = ppp > 0 ? 'danger' : 'good';
    return `<div class="sr-cii-row">
      <span class="sr-cii-country">${escapeHtml(c.title)}</span>
      <span class="sr-feed-time">$${price.toFixed(2)}</span>
      <span class="sr-feed-value" data-tone="${tone}">${ppp > 0 ? '+' : ''}${ppp}%</span>
    </div>`;
  }).join('');
}

/* ─── Renewable Energy ─── */
async function loadSitroomRenewable() {
  const d = await safeFetch('/api/sitroom/renewable', {}, null);
  const el = document.getElementById('sitroom-renewable');
  if (!el) return;
  if (!d || !d.articles?.length) { el.innerHTML = '<div class="sr-empty">No renewable data</div>'; return; }
  el.innerHTML = d.articles.map(a => `<div class="sitroom-news-item">
    <span class="sitroom-news-cat" data-cat="Renewable">${escapeHtml(a.source_name || '')}</span>
    <div class="sitroom-news-body">
      <a href="${escapeAttr(a.link || '#')}" target="_blank" rel="noopener" class="sitroom-news-title">${escapeHtml(a.title)}</a>
    </div>
  </div>`).join('');
}

/* ─── Social Velocity ─── */
async function loadSitroomVelocity() {
  const d = await safeFetch('/api/sitroom/social-velocity', {}, null);
  const el = document.getElementById('sitroom-velocity');
  if (!el) return;
  if (!d || !d.stories?.length) { el.innerHTML = '<div class="sr-empty">No velocity data yet</div>'; return; }
  el.innerHTML = d.stories.map(s => {
    const det = _parseSitroomDetailJson(s.detail_json);
    const speed = s.magnitude || 0;
    const barWidth = Math.min(100, speed * 15);
    const tone = speed >= 6 ? 'danger' : speed >= 4 ? 'warn' : 'neutral';
    return `<div class="sr-velocity-item">
      <div class="sr-velocity-title">${escapeHtml(s.title || '')}</div>
      <div class="sr-velocity-row">
        <div class="sr-velocity-bar">
          <div class="sr-velocity-bar-fill" data-tone="${tone}" data-sr-fill="${barWidth}"></div>
        </div>
        <span class="sr-velocity-mult" data-tone="${speed >= 6 ? 'danger' : 'neutral'}">${speed}x</span>
      </div>
      <div class="sr-velocity-meta">${escapeHtml(det.sources || '')}</div>
    </div>`;
  }).join('');
  _hydrateSitroomRuntimeVars(el);
}

/* ─── Service Status ─── */
async function loadSitroomServiceStatus() {
  const d = await safeFetch('/api/sitroom/service-status', {}, null);
  const el = document.getElementById('sitroom-service-status');
  if (!el) return;
  if (!d || !d.services?.length) { el.innerHTML = '<div class="sr-empty">No service status data</div>'; return; }
  el.innerHTML = d.services.map(s => {
    const det = _parseSitroomDetailJson(s.detail_json);
    const isIncident = (s.title || '').toLowerCase().includes('incident') || (s.title || '').toLowerCase().includes('outage');
    return `<div class="sitroom-event-item${isIncident ? ' sitroom-sev-extreme' : ''}">
      <span class="sitroom-mag ${isIncident ? 'sitroom-mag-service-incident' : 'sitroom-mag-service-ok'}">${(det.service || '??').substring(0,3)}</span>
      <div class="sitroom-event-info">
        <div class="sitroom-event-title">${escapeHtml(s.title || '')}</div>
        <div class="sitroom-event-meta">${det.published ? escapeHtml(det.published) : ''}</div>
      </div>
      ${s.source_url ? `<a href="${escapeAttr(s.source_url)}" target="_blank" rel="noopener" class="sitroom-event-link">&#8599;</a>` : ''}
    </div>`;
  }).join('');
}

/* ─── Cross-Domain Correlations ─── */
async function loadSitroomCorrelations() {
  const d = await safeFetch('/api/sitroom/correlations', {}, null);
  const el = document.getElementById('sitroom-correlations');
  if (!el) return;
  if (!d || !d.signals?.length) { el.innerHTML = '<div class="sr-empty">No cross-domain signals detected</div>'; return; }
  el.innerHTML = d.signals.map(s => {
    const det = _parseSitroomDetailJson(s.detail_json);
    return `<div class="sr-corr-signal" data-sev="${escapeAttr(det.severity || 'normal')}">
      <div class="sr-corr-title">${escapeHtml(s.title || '')}</div>
      <div class="sr-corr-detail">${escapeHtml(det.detail || '')}</div>
      <div class="sr-corr-type">${escapeHtml(det.type || '')}</div>
    </div>`;
  }).join('');
}

/* ─── Yield Curve ─── */
async function loadSitroomYieldCurve() {
  const d = await safeFetch('/api/sitroom/yield-curve', {}, null);
  const el = document.getElementById('sitroom-yield');
  if (!el) return;
  if (!d || !d.rates?.length) { el.innerHTML = '<div class="sr-empty">No yield data</div>'; return; }
  const maxRate = Math.max(...d.rates.map(r => r.magnitude || 0), 1);
  el.innerHTML = '<div class="sr-yield-bars">' + d.rates.slice(0, 12).map(r => {
    const det = _parseSitroomDetailJson(r.detail_json);
    const rate = r.magnitude || 0;
    const pct = (rate / maxRate * 100).toFixed(0);
    const label = (det.security || r.title || '').replace('Treasury ', '').substring(0, 8);
    return `<div class="sr-yield-bar">
      <div class="sr-yield-bar-rate">${rate.toFixed(2)}%</div>
      <div class="sr-yield-bar-fill" data-sr-height="${pct}"></div>
      <div class="sr-yield-bar-label">${escapeHtml(label)}</div>
    </div>`;
  }).join('') + '</div>';
  _hydrateSitroomRuntimeVars(el);
}

/* ─── Stablecoins ─── */
async function loadSitroomStablecoins() {
  const d = await safeFetch('/api/sitroom/stablecoins', {}, null);
  const el = document.getElementById('sitroom-stablecoins');
  if (!el) return;
  if (!d || !d.stablecoins?.length) { el.innerHTML = '<div class="sr-empty">No stablecoin data</div>'; return; }
  el.innerHTML = d.stablecoins.map(s => {
    const depeg = Math.abs(s.price - 1.0);
    const tone = depeg > 0.01 ? 'danger' : depeg > 0.003 ? 'warn' : 'good';
    return `<div class="sitroom-market-card" data-tone="${tone}">
      <div class="sitroom-market-symbol">${escapeHtml(s.symbol)}</div>
      <div class="sitroom-market-price" data-tone="${tone}">$${s.price.toFixed(4)}</div>
      <div class="sitroom-market-change">${escapeHtml(s.label || '')}</div>
    </div>`;
  }).join('');
}

/* ─── Playback Control ─── */
document.getElementById('sr-playback-slider')?.addEventListener('input', e => {
  const val = parseInt(e.target.value);
  const timeEl = document.getElementById('sr-playback-time');
  const liveBtn = document.getElementById('sr-playback-live');
  if (val >= 24) {
    if (timeEl) timeEl.textContent = 'NOW';
    if (liveBtn) liveBtn.classList.add('active');
  } else {
    const hoursAgo = 24 - val;
    if (timeEl) timeEl.textContent = `-${hoursAgo}h`;
    if (liveBtn) liveBtn.classList.remove('active');
  }
});

/* ─── AI Strategic Briefing ─── */
async function _generateAiBriefing() {
  const btn = document.getElementById('sitroom-gen-briefing');
  const el = document.getElementById('sitroom-briefing-content');
  if (!el) return;
  if (btn) btn.disabled = true;
  el.innerHTML = '<div class="sr-empty sr-empty-emphasis"><div class="sr-radar"></div><span>Generating intelligence briefing...</span></div>';
  try {
    const d = await apiPost('/api/sitroom/ai-briefing');
    if (d.briefing) {
      el.innerHTML = '<div class="sr-briefing-text">' + _renderBriefing(d.briefing) + '</div>';
    } else {
      el.innerHTML = '<div class="sr-empty">Briefing generation failed</div>';
    }
  } catch(e) {
    el.innerHTML = '<div class="sr-empty">Network error generating briefing</div>';
  } finally {
    if (btn) btn.disabled = false;
  }
}

/* ─── Keyword Monitors ─── */
async function loadSitroomMonitors() {
  const d = await safeFetch('/api/sitroom/monitors', {}, null);
  const el = document.getElementById('sitroom-monitors');
  if (!el) return;
  if (!d || !d.monitors?.length) { el.innerHTML = '<div class="sr-empty">No keyword monitors — click + ADD</div>'; return; }
  el.innerHTML = d.monitors.map(m => {
    let matchHtml = m.matches?.slice(0, 5).map(n =>
      `<div class="sr-monitor-match">${escapeHtml(n.title)}</div>`
    ).join('') || '';
    return `<div class="sr-monitor-item">
      <div class="sr-monitor-kw">
        <span class="sr-monitor-kw-dot" data-sr-monitor-color="${escapeAttr(m.color)}"></span>
        <span class="sr-monitor-kw-text">${escapeHtml(m.keyword)}</span>
        <span class="sr-monitor-kw-count">${m.match_count || 0}</span>
        <span class="sr-monitor-kw-del" data-sitroom-action="delete-monitor" data-monitor-id="${m.id}">&#10005;</span>
      </div>
      ${matchHtml}
    </div>`;
  }).join('');
  _hydrateSitroomRuntimeVars(el);
}

function _promptAddMonitor() {
  const keyword = prompt('Enter keyword to monitor:');
  if (!keyword || !keyword.trim()) return;
  apiPost('/api/sitroom/monitors', {keyword: keyword.trim()})
    .then(() => loadSitroomMonitors())
    .catch((e) => toast(e?.data?.error || e?.message || 'Failed to add monitor', 'error'));
}

async function _deleteMonitor(id) {
  try {
    await apiDelete('/api/sitroom/monitors/' + id);
  } catch(e) { toast('Failed to delete monitor', 'error'); }
  loadSitroomMonitors();
}

/* ─── Economic Calendar ─── */
async function loadSitroomEconCal() {
  const d = await safeFetch('/api/sitroom/economic-calendar', {}, null);
  const el = document.getElementById('sitroom-econ-cal');
  if (!el) return;
  if (!d || !d.events?.length) { el.innerHTML = '<div class="sr-empty">No economic events</div>'; return; }
  el.innerHTML = d.events.map(e => `<div class="sitroom-news-item">
    <span class="sitroom-news-cat" data-cat="Finance">${escapeHtml(e.source_name || 'Econ')}</span>
    <div class="sitroom-news-body">
      <a href="${escapeAttr(e.link || '#')}" target="_blank" rel="noopener" class="sitroom-news-title">${escapeHtml(e.title)}</a>
      <div class="sitroom-news-meta">${e.published ? escapeHtml(e.published) : ''}</div>
    </div>
  </div>`).join('');
}

/* ─── National Debt ─── */
async function loadSitroomDebt() {
  const d = await safeFetch('/api/sitroom/national-debt', {}, null);
  const el = document.getElementById('sitroom-debt');
  if (!el) return;
  if (!d || !d.debt?.us) { el.innerHTML = '<div class="sr-empty">No debt data</div>'; return; }
  const total = d.debt.us.total;
  const formatted = '$' + (total / 1e12).toFixed(3) + 'T';
  el.innerHTML = `<div class="sr-debt-value">${formatted}</div>
    <div class="sr-debt-label">US NATIONAL DEBT</div>
    <div class="sr-debt-date">As of ${escapeHtml(d.debt.us.date || '')}</div>`;
}

/* ─── Story Detail Modal ─── */
function _closeStoryModal() {
  _closeSitroomAnalysis();
}

function _openStoryModal(title, category, link, description, source, published) {
  const bodyHtml = `<div class="sr-analysis-section">
    <div class="sr-analysis-section-title">Story Brief</div>
    <div class="sr-analysis-story">
      <div class="sr-analysis-story-copy">${description ? escapeHtml(description) : 'No preview was cached for this story yet. Use the source link for the full article while keeping this desk context visible.'}</div>
    </div>
  </div>
  <div class="sr-analysis-section">
    <div class="sr-analysis-section-title">Source Trail</div>
    <div class="sr-analysis-list">
      <div class="sr-analysis-item">
        <div class="sr-analysis-item-head">
          <span class="sr-analysis-item-title">${escapeHtml(source || category || 'Open-source feed')}</span>
          <span class="sr-analysis-item-meta">${escapeHtml(published || 'Live cache')}</span>
        </div>
        <div class="sr-analysis-item-meta">Open the source article in a separate tab if you want the full source trail without losing the desk layout.</div>
      </div>
    </div>
  </div>`;
  _openSitroomAnalysis({
    kicker: category || 'Story',
    title: title || 'Untitled story',
    meta: _storyMetaLine(source, published) || 'Pinned from News Desk',
    bodyHtml,
    link,
    linkLabel: 'Open Article',
  });
}

/* ─── UCDP Armed Conflicts ─── */
async function loadSitroomUcdp() {
  const d = await safeFetch('/api/sitroom/ucdp', {}, null);
  const el = document.getElementById('sitroom-ucdp');
  if (!el) return;
  if (!d || !d.conflicts?.length) { el.innerHTML = '<div class="sr-empty">No UCDP data</div>'; return; }
  el.innerHTML = d.conflicts.slice(0, 20).map(c => {
    const det = _parseSitroomDetailJson(c.detail_json);
    const deaths = c.magnitude || 0;
    const cls = deaths >= 10 ? 'sitroom-mag-high' : deaths >= 3 ? 'sitroom-mag-med' : 'sitroom-mag-low';
    return `<div class="sitroom-event-item">
      <span class="sitroom-mag ${cls}">${deaths}</span>
      <div class="sitroom-event-info">
        <div class="sitroom-event-title">${escapeHtml(c.title || '')}</div>
        <div class="sitroom-event-meta">${escapeHtml(det.country || '')}${det.violence_type ? ' | ' + escapeHtml(det.violence_type) : ''}</div>
      </div>
    </div>`;
  }).join('');
}

/* ─── Cyber Threats ─── */
async function loadSitroomCyber() {
  const d = await safeFetch('/api/sitroom/cyber-threats', {}, null);
  const el = document.getElementById('sitroom-cyber');
  if (!el) return;
  if (!d || !d.threats?.length) { el.innerHTML = '<div class="sr-empty">No cyber threat data</div>'; return; }
  el.innerHTML = d.threats.map(t => {
    const det = _parseSitroomDetailJson(t.detail_json);
    const sevClass = det.severity === 'high' ? 'sitroom-mag-cyber-high' : 'sitroom-mag-cyber-med';
    return `<div class="sitroom-event-item">
      <span class="sitroom-mag ${sevClass}">${(det.severity || '?').substring(0,1).toUpperCase()}</span>
      <div class="sitroom-event-info">
        <div class="sitroom-event-title">${escapeHtml(t.title || '')}</div>
        <div class="sitroom-event-meta">${escapeHtml(det.source || '')}${det.date ? ' | ' + escapeHtml(det.date) : ''}</div>
      </div>
      ${t.source_url ? `<a href="${escapeAttr(t.source_url)}" target="_blank" rel="noopener" class="sitroom-event-link">&#8599;</a>` : ''}
    </div>`;
  }).join('');
}

/* ─── Think Tanks ─── */
async function loadSitroomThinkTanks() {
  const d = await safeFetch('/api/sitroom/news?category=Think+Tanks&limit=20', {}, null);
  const el = document.getElementById('sitroom-think-tanks');
  if (!el) return;
  if (!d || !d.articles?.length) { el.innerHTML = '<div class="sr-empty">No think tank data</div>'; return; }
  el.innerHTML = d.articles.map(a => `<div class="sitroom-news-item">
    <span class="sitroom-news-cat" data-cat="Think Tanks">${escapeHtml(a.source_name || '')}</span>
    <div class="sitroom-news-body">
      <a href="${escapeAttr(a.link || '#')}" target="_blank" rel="noopener" class="sitroom-news-title">${escapeHtml(a.title)}</a>
    </div>
  </div>`).join('');
}

/* ─── OSINT Feed (Telegram via RSS) ─── */
async function loadSitroomOsint() {
  const d = await safeFetch('/api/sitroom/osint', {}, null);
  const el = document.getElementById('sitroom-osint');
  if (!el) return;
  if (!d || !d.articles?.length) { el.innerHTML = '<div class="sr-empty">No OSINT data — click Refresh</div>'; return; }
  el.innerHTML = d.articles.map(a => `<div class="sitroom-news-item">
    <span class="sitroom-news-cat" data-cat="OSINT">${escapeHtml(a.source_name || 'OSINT')}</span>
    <div class="sitroom-news-body">
      <a href="${escapeAttr(a.link || '#')}" target="_blank" rel="noopener" class="sitroom-news-title">${escapeHtml(a.title)}</a>
      <div class="sitroom-news-meta">${a.published ? escapeHtml(a.published) : ''}</div>
    </div>
  </div>`).join('');
}

/* ─── Export Intelligence Report ─── */
function _exportSitroomReport() {
  window.open('/api/sitroom/export', '_blank');
}

/* ─── UNHCR Displacement ─── */
async function loadSitroomDisplacement() {
  const d = await safeFetch('/api/sitroom/displacement', {}, null);
  const el = document.getElementById('sitroom-displacement');
  if (!el) return;
  if (!d || !d.records?.length) { el.innerHTML = '<div class="sr-empty">No displacement data</div>'; return; }
  el.innerHTML = d.records.map(r => {
    const det = _parseSitroomDetailJson(r.detail_json);
    return `<div class="sitroom-event-item">
      <div class="sitroom-event-info">
        <div class="sitroom-event-title">${escapeHtml(r.title || '')}</div>
        <div class="sitroom-event-meta">${det.recognized ? 'Recognized: ' + Number(det.recognized).toLocaleString() : ''}${det.year ? ' | ' + escapeHtml(String(det.year)) : ''}</div>
      </div>
      ${r.source_url ? `<a href="${escapeAttr(r.source_url)}" target="_blank" rel="noopener" class="sitroom-event-link">&#8599;</a>` : ''}
    </div>`;
  }).join('');
}

/* ─── Country Deep Dive ─── */
async function openCountryDeepDive(country) {
  _openSitroomAnalysis({
    kicker: 'Country Deep Dive',
    title: country.toUpperCase(),
    meta: 'Loading country posture, recent signals, and source trail...',
    bodyHtml: '<div class="sr-empty"><div class="sr-radar"></div>Loading intelligence...</div>',
  });
  const body = document.getElementById('sr-analysis-body');
  if (!body) return;

  const d = await safeFetch('/api/sitroom/country/' + encodeURIComponent(country), {}, null);
  if (!d) { body.innerHTML = '<div class="sr-empty">No data available</div>'; return; }

  const summaryItems = Object.entries(d.event_summary || {}).slice(0, 6).map(([type, count]) => `
    <div class="sr-analysis-item">
      <div class="sr-analysis-item-head">
        <span class="sr-analysis-item-title">${escapeHtml(type.replace(/_/g, ' '))}</span>
        <span class="sr-analysis-item-meta">${count}</span>
      </div>
    </div>`).join('');
  const quakeItems = (d.recent_quakes || []).slice(0, 4).map(q => `
    <div class="sr-analysis-item">
      <div class="sr-analysis-item-head">
        <span class="sr-analysis-item-title">${escapeHtml(q.title || 'Seismic event')}</span>
        <span class="sr-analysis-item-meta">M${q.magnitude || '?'}</span>
      </div>
    </div>`).join('');
  const newsItems = (d.recent_news || []).slice(0, 5).map(n => `
    <div class="sr-analysis-item">
      <div class="sr-analysis-item-head">
        <span class="sr-analysis-item-title">${escapeHtml(n.title || 'Headline')}</span>
        ${n.link ? `<a href="${escapeAttr(n.link)}" target="_blank" rel="noopener" class="sr-analysis-linkout">Source</a>` : ''}
      </div>
      <div class="sr-analysis-item-meta">${escapeHtml(_storyMetaLine(n.source_name || '', n.published || ''))}</div>
    </div>`).join('');

  const html = `<div class="sr-analysis-section">
    <div class="sr-analysis-section-title">Overview</div>
    <div class="sr-analysis-grid">
      <div class="sr-analysis-stat"><span class="sr-analysis-stat-label">Total Events</span><span class="sr-analysis-stat-value">${d.total_events || 0}</span></div>
      <div class="sr-analysis-stat"><span class="sr-analysis-stat-label">Signal Types</span><span class="sr-analysis-stat-value">${Object.keys(d.event_summary || {}).length}</span></div>
      <div class="sr-analysis-stat"><span class="sr-analysis-stat-label">News Mentions</span><span class="sr-analysis-stat-value">${(d.recent_news || []).length}</span></div>
    </div>
  </div>
  ${summaryItems ? `<div class="sr-analysis-section"><div class="sr-analysis-section-title">Event Signals</div><div class="sr-analysis-list">${summaryItems}</div></div>` : ''}
  ${quakeItems ? `<div class="sr-analysis-section"><div class="sr-analysis-section-title">Seismic Activity</div><div class="sr-analysis-list">${quakeItems}</div></div>` : ''}
  ${newsItems ? `<div class="sr-analysis-section"><div class="sr-analysis-section-title">Recent Intelligence</div><div class="sr-analysis-list">${newsItems}</div></div>` : '<div class="sr-empty">No intelligence signals for this country</div>'}`;
  _openSitroomAnalysis({
    kicker: 'Country Deep Dive',
    title: country.toUpperCase(),
    meta: `${d.total_events || 0} events · ${(d.recent_news || []).length} recent headlines`,
    bodyHtml: html,
  });
}

/* ─── Live YouTube Channels ─── */
let _sitroomChannelsLoaded = false;
async function loadSitroomLiveChannels() {
  if (_sitroomChannelsLoaded) return;
  const d = await safeFetch('/api/sitroom/live-channels', {}, null);
  const btns = document.getElementById('sr-channel-btns');
  if (!btns || !d || !d.channels?.length) return;
  _sitroomChannelsLoaded = true;
  btns.innerHTML = d.channels.map((ch, i) =>
    `<button class="sr-channel-btn${i === 0 ? ' active' : ''}" data-channel-idx="${i}" data-channel-vid="${escapeAttr(ch.video_id || '')}" data-channel-handle="${escapeAttr(ch.handle || '')}" title="${escapeAttr(ch.name)}">${escapeHtml(ch.name.split(' ')[0])}</button>`
  ).join('');
  // Auto-play first channel with a known video_id
  const first = d.channels.find(c => c.video_id);
  if (first) _sitroomPlayChannel(first.video_id);
}

function _sitroomPlayChannel(videoId) {
  const player = document.getElementById('sr-live-player');
  if (!player || !videoId) return;
  player.innerHTML = `<iframe class="sr-live-iframe" src="https://www.youtube.com/embed/${encodeURIComponent(videoId)}?autoplay=1&mute=1&controls=1" frameborder="0" allow="autoplay; encrypted-media" allowfullscreen></iframe>`;
}

/* ─── Events ─── */
document.addEventListener('click', e => {
  const ctrl = e.target.closest('[data-sitroom-action]');
  if (!ctrl) return;
  const a = ctrl.dataset.sitroomAction;
  if (a === 'refresh') refreshSitroomFeeds();
  if (a === 'add-feed') addSitroomFeed();
  if (a === 'delete-feed') deleteSitroomFeed(ctrl.dataset.feedId);
  if (a === 'load-more-news') loadSitroomNews(true);
  if (a === 'toggle-feeds') {
    const fp = document.getElementById('sr-feed-panel');
    if (fp) { fp.hidden = !fp.hidden; if (!fp.hidden) loadSitroomFeeds(); }
  }
  if (a === 'open-search') _toggleSitroomSearch(true);
  if (a === 'toggle-map-fullscreen') _toggleMapFullscreen();
  if (a === 'toggle-globe') _toggleGlobe();
  if (a === 'export-report') _exportSitroomReport();
  if (a === 'copy-desk-snapshot') _copySitroomDeskSnapshot();
  if (a === 'save-desk-note') _saveSitroomDeskSnapshotToNotes();
  if (a === 'send-desk-lan') _sendSitroomDeskSnapshotToLan();
  if (a === 'set-snapshot-template') _setSitroomSnapshotTemplate(ctrl.dataset.sitroomSnapshotTemplate || 'morning');
  if (a === 'set-view') _setSitroomView(ctrl.dataset.sitroomView || 'topline');
  if (a === 'set-news-group') _setSitroomNewsGroup(ctrl.dataset.sitroomNewsGroup || 'all');
  if (a === 'set-region-preset') _setSitroomRegionPreset(ctrl.dataset.sitroomRegion || 'global');
  if (a === 'set-brief-mode') _setSitroomBriefMode(ctrl.dataset.sitroomBriefMode || 'morning');
  if (a === 'set-desk-preset') _setSitroomDeskPreset(ctrl.dataset.sitroomDesk || 'executive');
  if (a === 'set-layer-preset') _setSitroomLayerPreset(ctrl.dataset.sitroomLayerPreset || 'crisis');
  if (a === 'save-current-desk') _saveCurrentSitroomDesk();
  if (a === 'update-saved-desk') _updateCurrentSavedSitroomDesk();
  if (a === 'set-default-saved-desk') _setSitroomDefaultDesk(ctrl.dataset.sitroomSavedDesk || '');
  if (a === 'toggle-pin-saved-desk') _togglePinSavedSitroomDesk(ctrl.dataset.sitroomSavedDesk || '');
  if (a === 'move-saved-desk-earlier') _moveSitroomSavedDesk(ctrl.dataset.sitroomSavedDesk || '', 'earlier');
  if (a === 'move-saved-desk-later') _moveSitroomSavedDesk(ctrl.dataset.sitroomSavedDesk || '', 'later');
  if (a === 'load-saved-desk') _loadSavedSitroomDesk(ctrl.dataset.sitroomSavedDesk || '');
  if (a === 'delete-saved-desk') _deleteSavedSitroomDesk(ctrl.dataset.sitroomSavedDesk || '');
  if (a === 'reset-desk-posture') _setSitroomDeskPreset('executive');
  if (a === 'toggle-layout-edit') _toggleSitroomLayoutEdit();
  if (a === 'generate-briefing') _generateAiBriefing();
  if (a === 'close-story') _closeStoryModal();
  if (a === 'close-analysis') _closeSitroomAnalysis();
  if (a === 'open-story') {
    _openStoryModal(
      ctrl.dataset.storyTitle || 'Untitled story',
      ctrl.dataset.storyCategory || 'News',
      ctrl.dataset.storyLink || '#',
      ctrl.dataset.storyDescription || '',
      ctrl.dataset.storySource || '',
      ctrl.dataset.storyPublished || ''
    );
    _toggleSitroomSearch(false);
  }
  if (a === 'run-deduction') runSitroomDeduction();
  if (a === 'gen-market-brief') _generateMarketBrief();
  if (a === 'add-monitor') _promptAddMonitor();
  if (a === 'delete-monitor') _deleteMonitor(ctrl.dataset.monitorId);
  if (a === 'fly-search-result') {
    const lng = parseFloat(ctrl.dataset.lng || '0');
    const lat = parseFloat(ctrl.dataset.lat || '0');
    if (_sitroomMap && Number.isFinite(lng) && Number.isFinite(lat)) {
      _sitroomMap.flyTo({center:[lng, lat], zoom:6});
    }
    _toggleSitroomSearch(false);
  }
  if (a === 'playback-live') {
    const slider = document.getElementById('sr-playback-slider');
    if (slider) { slider.value = 24; slider.dispatchEvent(new Event('input')); }
  }
  if (a === 'toggle-layers') {
    const lp = document.getElementById('sr-layer-panel');
    if (lp) lp.classList.toggle('open');
  }
});

document.getElementById('sitroom-news-category')?.addEventListener('change', () => loadSitroomNews());
document.getElementById('sitroom-quake-filter')?.addEventListener('change', () => renderSitroomQuakes());
document.querySelectorAll('[data-sitroom-layer]').forEach(cb => cb.addEventListener('change', () => {
  _sitroomLayerPreset = _inferSitroomLayerPreset();
  _sitroomDeskPreset = 'custom';
  _sitroomSavedDeskId = '';
  loadSitroomMapData(); _updateMapLegend(); _renderDayNight(); _updateActiveLayerCount(); _saveLayerState(); _saveSitroomWorkspaceState(); _applySitroomWorkspaceState();
}));

function _updateActiveLayerCount() {
  const badge = document.getElementById('sr-active-layer-count');
  if (!badge) return;
  let count = 0;
  document.querySelectorAll('[data-sitroom-layer]').forEach(cb => { if (cb.checked) count++; });
  badge.textContent = count;
}

function _saveLayerState() {
  const state = {};
  document.querySelectorAll('[data-sitroom-layer]').forEach(cb => {
    state[cb.dataset.sitroomLayer] = cb.checked;
  });
  try { localStorage.setItem('sr-layer-state', JSON.stringify(state)); } catch(e) {}
}

function _restoreLayerState() {
  const state = _readSitroomStorageJson('sr-layer-state', null);
  if (!state) return;
  document.querySelectorAll('[data-sitroom-layer]').forEach(cb => {
    if (state[cb.dataset.sitroomLayer] !== undefined) cb.checked = state[cb.dataset.sitroomLayer];
  });
  _sitroomLayerPreset = _inferSitroomLayerPreset();
  _updateActiveLayerCount();
}

// Search input handler
document.getElementById('sr-search-input')?.addEventListener('input', e => {
  clearTimeout(_searchDebounce);
  _searchDebounce = setTimeout(() => _sitroomDoSearch(e.target.value.trim()), 300);
});

document.getElementById('sr-saved-desk-name')?.addEventListener('keydown', e => {
  if (e.key === 'Enter') {
    e.preventDefault();
    _saveCurrentSitroomDesk();
  }
});

// Search overlay click-to-close
document.getElementById('sr-search-overlay')?.addEventListener('click', e => {
  if (e.target.id === 'sr-search-overlay') _toggleSitroomSearch(false);
});

// Panel collapse on header click (but not on buttons/selects inside header)
document.addEventListener('click', e => {
  const head = e.target.closest('.sr-card-head');
  if (!head) return;
  if (e.target.closest('button, select, input, a, .sr-channel-btns')) return;
  const card = head.closest('.sr-card');
  if (card) card.classList.toggle('collapsed');
});

/* ─── P3: Cable Health Card ─── */
async function loadSitroomCableHealth() {
  const el = document.getElementById('sitroom-cable-health');
  if (!el) return;
  const d = await safeFetch('/api/sitroom/cable-health', {}, null);
  if (!d) { el.innerHTML = '<div class="sitroom-empty">No data</div>'; return; }
  let html = '';
  (d.cables || []).forEach(c => {
    const tone = c.status === 'operational' ? 'good' : 'danger';
    const icon = c.status === 'operational' ? '&#9679;' : '&#9888;';
    html += `<div class="sr-feed-item" data-tone="${tone}">${_srFeedIcon(icon, tone)}
      <span class="sr-feed-title">${escapeHtml(c.name)}</span>
      <span class="sr-feed-source">${escapeHtml(c.route)}</span></div>`;
    if (c.alert_title) html += `<div class="sr-feed-item" data-tone="warn" data-indent="subtle">${escapeHtml(c.alert_title)}</div>`;
  });
  if (d.related_news && d.related_news.length) {
    html += '<div class="sr-mini-label sr-mini-label-spaced">Related News</div>';
    d.related_news.slice(0, 3).forEach(n => {
      html += `<div class="sr-feed-item"><span class="sr-feed-title">${escapeHtml(n.title)}</span></div>`;
    });
  }
  el.innerHTML = html || '<div class="sitroom-empty">All cables operational</div>';
}

/* ─── P3: Anomaly Detection Card ─── */
async function loadSitroomAnomalies() {
  const el = document.getElementById('sitroom-anomalies');
  if (!el) return;
  const d = await safeFetch('/api/sitroom/anomalies', {}, null);
  if (!d || !d.anomalies || !d.anomalies.length) {
    el.innerHTML = '<div class="sr-feed-item" data-tone="good">No anomalies detected</div>';
    return;
  }
  let html = '';
  d.anomalies.forEach(a => {
    const tone = a.severity === 'critical' || a.severity === 'high'
      ? 'danger'
      : a.severity === 'medium'
        ? 'warn'
        : 'neutral';
    html += `<div class="sr-feed-item" data-tone="${tone}">
      ${_srFeedBadge(a.severity.toUpperCase(), tone)}
      <span class="sr-feed-title">${escapeHtml(a.message)}</span></div>`;
  });
  el.innerHTML = html;
}

/* ─── P3: Alert History Card ─── */
async function loadSitroomAlertHistory() {
  const el = document.getElementById('sitroom-alert-history');
  if (!el) return;
  const d = await safeFetch('/api/sitroom/alert-history', {}, null);
  if (!d) { el.innerHTML = '<div class="sitroom-empty">No history</div>'; return; }
  let html = '';
  if (d.earthquake_history && d.earthquake_history.length) {
    html += '<div class="sr-mini-label">Earthquakes (7-day)</div><div class="sr-sparkline-row">';
    [...d.earthquake_history].reverse().forEach(day => {
      const h = Math.max(3, Math.min(30, (day.count || 0) / 2));
      html += `<div class="sr-spark-bar sr-spark-bar-danger" data-sr-spark-height="${h}" title="${day.day}: ${day.count} quakes, max M${day.max_mag || '?'}"></div>`;
    });
    html += '</div>';
  }
  if (d.news_volume_24h && d.news_volume_24h.length) {
    html += '<div class="sr-mini-label sr-mini-label-spaced">News Volume (24h by category)</div>';
    d.news_volume_24h.slice(0, 8).forEach(cat => {
      const w = Math.min(100, (cat.count / (d.news_volume_24h[0].count || 1)) * 100);
      html += _srMetricRow(cat.category || '?', cat.count, w, 'accent');
    });
  }
  el.innerHTML = html || '<div class="sitroom-empty">No history</div>';
  _hydrateSitroomRuntimeVars(el);
}

/* ─── P3: Enhanced Signals Card ─── */
async function loadSitroomEnhancedSignals() {
  const el = document.getElementById('sitroom-enhanced-signals');
  if (!el) return;
  const d = await safeFetch('/api/sitroom/enhanced-signals', {}, null);
  if (!d || !d.signals || !d.signals.length) {
    el.innerHTML = '<div class="sitroom-empty">No signals detected</div>';
    return;
  }
  let html = '';
  d.signals.forEach(s => {
    const confidenceMeta = _getSitroomConfidenceMeta(s.confidence);
    const corroboratingCount = Number(s.corroborating_signals) || 0;
    html += `<div class="sr-feed-item" data-tone="${confidenceMeta.tone}">
      ${_srFeedBadge(confidenceMeta.label, confidenceMeta.tone)}
      <span class="sr-feed-title">${escapeHtml(s.title)}</span>
      <span class="sr-feed-source">${escapeHtml(s.signal_type)} · corroborated by ${corroboratingCount} signal${corroboratingCount === 1 ? '' : 's'}</span></div>`;
  });
  el.innerHTML = html;
}

/* ─── P3: Gulf Economies Card ─── */
async function loadSitroomGulfEcon() {
  const el = document.getElementById('sitroom-gulf-econ');
  if (!el) return;
  const d = await safeFetch('/api/sitroom/gulf-economies', {}, null);
  if (!d) { el.innerHTML = '<div class="sitroom-empty">No data</div>'; return; }
  let html = '';
  if (d.oil_markets && d.oil_markets.length) {
    html += '<div class="sr-mini-label">Oil Markets</div>';
    d.oil_markets.forEach(m => {
      const chg = m.change_24h || 0;
      const tone = chg >= 0 ? 'good' : 'danger';
      html += `<div class="sr-feed-item" data-layout="split"><span class="sr-feed-title">${escapeHtml(m.symbol)}</span>
        <span class="sr-feed-value" data-tone="${tone}">$${m.price} (${chg >= 0 ? '+' : ''}${chg.toFixed(1)}%)</span></div>`;
    });
  }
  if (d.news && d.news.length) {
    html += '<div class="sr-mini-label sr-mini-label-spaced">GCC Headlines</div>';
    d.news.slice(0, 8).forEach(n => {
      html += `<div class="sr-feed-item"><span class="sr-feed-source">${escapeHtml(n.source_name || '')}</span>
        <span class="sr-feed-title">${escapeHtml(n.title)}</span></div>`;
    });
  }
  el.innerHTML = html || '<div class="sitroom-empty">No Gulf data</div>';
}

// Country brief select
document.addEventListener('change', e => {
  if (e.target.id === 'sitroom-country-select' && e.target.value) {
    loadSitroomCountryBrief(e.target.value);
  }
});

/* ─── P5: Market Regime Card ─── */
async function loadSitroomMarketRegime() {
  const el = document.getElementById('sitroom-market-regime');
  if (!el) return;
  const d = await safeFetch('/api/sitroom/market-regime', {}, null);
  if (!d) { el.innerHTML = '<div class="sitroom-empty">No data</div>'; return; }
  const tone = d.regime === 'RISK-ON' ? 'good' : d.regime === 'RISK-OFF' ? 'danger' : 'warn';
  let html = `<div class="sr-runtime-hero">
    <div class="sr-runtime-hero-value" data-tone="${tone}">${escapeHtml(d.regime)}</div>
    <div class="sr-runtime-hero-meta">Composite Score: ${d.score > 0 ? '+' : ''}${d.score}</div>
  </div>`;
  if (d.signals) {
    html += '<div class="sr-kv-list">';
    for (const [k, v] of Object.entries(d.signals)) {
      html += _srKvRow(k, typeof v === 'number' ? v.toFixed(1) : v);
    }
    html += '</div>';
  }
  el.innerHTML = html;
}

/* ─── P5: Live Counters Card ─── */
async function loadSitroomLiveCounters() {
  const el = document.getElementById('sitroom-live-counters');
  if (!el) return;
  const d = await safeFetch('/api/sitroom/live-counters', {}, null);
  if (!d || !d.counters) { el.innerHTML = '<div class="sitroom-empty">No data</div>'; return; }
  let html = '';
  for (const [, info] of Object.entries(d.counters)) {
    html += `<div class="sr-feed-item" data-tone="good" data-layout="split">
      <span class="sr-feed-title">${escapeHtml(info.label)}</span>
      <span class="sr-feed-value" data-tone="good">${info.value.toLocaleString()}</span>
    </div>`;
  }
  el.innerHTML = html;
}

/* ─── P5: Species Comeback Card ─── */
async function loadSitroomSpecies() {
  const el = document.getElementById('sitroom-species-tracker');
  if (!el) return;
  const d = await safeFetch('/api/sitroom/species-tracker', {}, null);
  if (!d) { el.innerHTML = '<div class="sitroom-empty">No data</div>'; return; }
  let html = '';
  if (d.comebacks) {
    d.comebacks.forEach(s => {
      const tone = s.status === 'Recovered' ? 'good' : s.status === 'Recovering' ? 'accent' : 'warn';
      html += `<div class="sr-feed-item" data-tone="${tone}">
        <span class="sr-feed-title">${escapeHtml(s.species)}</span>
        ${_srFeedBadge(s.status, tone)}
        <span class="sr-feed-source">${escapeHtml(s.change)}</span>
      </div>`;
    });
  }
  if (d.news && d.news.length) {
    html += '<div class="sr-mini-label sr-mini-label-spaced">Conservation News</div>';
    d.news.slice(0, 5).forEach(n => {
      html += `<div class="sr-feed-item"><a href="${escapeAttr(n.link || '#')}" target="_blank" class="sr-feed-title">${escapeHtml(n.title)}</a></div>`;
    });
  }
  el.innerHTML = html || '<div class="sitroom-empty">No species data</div>';
}

/* ─── P5: Tech Readiness Card ─── */
async function loadSitroomTechReadiness() {
  const el = document.getElementById('sitroom-tech-readiness');
  if (!el) return;
  const d = await safeFetch('/api/sitroom/tech-readiness', {}, null);
  if (!d) { el.innerHTML = '<div class="sitroom-empty">No data</div>'; return; }
  const overallTone = d.overall >= 7 ? 'good' : d.overall >= 4 ? 'warn' : 'danger';
  let html = `<div class="sr-runtime-hero">
    <div class="sr-runtime-hero-value" data-tone="${overallTone}">${d.overall}/10</div>
    <div class="sr-runtime-hero-label">Tech Readiness Score</div>
  </div><div class="sr-metric-list">`;
  for (const [name, val] of Object.entries(d.dimensions || {})) {
    const tone = val >= 7 ? 'good' : val >= 4 ? 'warn' : 'danger';
    html += _srMetricRow(name, val, val * 10, tone);
  }
  html += '</div>';
  el.innerHTML = html;
  _hydrateSitroomRuntimeVars(el);
}

/* ─── P5: Today's Hero Card ─── */
async function loadSitroomTodaysHero() {
  const el = document.getElementById('sitroom-todays-hero');
  if (!el) return;
  const d = await safeFetch('/api/sitroom/todays-hero', {}, null);
  if (!d || !d.hero) { el.innerHTML = '<div class="sitroom-empty">No hero story found today</div>'; return; }
  el.innerHTML = `<div class="sr-feature-story">
    <a href="${escapeAttr(d.hero.link || '#')}" target="_blank" class="sr-feature-story-title">${escapeHtml(d.hero.title)}</a>
    <div class="sr-feature-story-meta">${escapeHtml(d.hero.source_name || '')} | Positivity: ${d.score}/10</div>
  </div>`;
}

/* ─── P5: 5 Good Things Card ─── */
async function loadSitroomGoodThings() {
  const el = document.getElementById('sitroom-good-things');
  if (!el) return;
  const d = await safeFetch('/api/sitroom/five-good-things', {}, null);
  if (!d || !d.good_things || !d.good_things.length) { el.innerHTML = '<div class="sitroom-empty">No good news found</div>'; return; }
  let html = '';
  d.good_things.forEach((g, i) => {
    html += `<div class="sr-feed-item" data-tone="good">
      <span class="sr-feed-index">${i + 1}.</span>
      <a href="${escapeAttr(g.link || '#')}" target="_blank" class="sr-feed-title">${escapeHtml(g.title)}</a>
      <span class="sr-feed-source">${escapeHtml(g.source_name || '')}</span>
    </div>`;
  });
  el.innerHTML = html;
}

/* ─── P5: Central Bank Calendar Card ─── */
async function loadSitroomCbCalendar() {
  const el = document.getElementById('sitroom-cb-calendar');
  if (!el) return;
  const d = await safeFetch('/api/sitroom/central-bank-calendar', {}, null);
  if (!d) { el.innerHTML = '<div class="sitroom-empty">No data</div>'; return; }
  let html = '<table class="sr-table"><tr><th>Bank</th><th>Frequency</th></tr>';
  (d.calendar || []).forEach(cb => {
    html += `<tr><td>${escapeHtml(cb.bank)}</td><td>${escapeHtml(cb.frequency)}</td></tr>`;
  });
  html += '</table>';
  if (d.news && d.news.length) {
    html += '<div class="sr-mini-label sr-mini-label-spaced">Rate Decision News</div>';
    d.news.slice(0, 5).forEach(n => {
      html += `<div class="sr-feed-item"><span class="sr-feed-title">${escapeHtml(n.title)}</span></div>`;
    });
  }
  el.innerHTML = html;
}

/* ─── P7: APT Groups Card ─── */
async function loadSitroomAptGroups() {
  const el = document.getElementById('sitroom-apt-groups');
  if (!el) return;
  const d = await safeFetch('/api/sitroom/apt-groups', {}, null);
  if (!d || !d.groups) { el.innerHTML = '<div class="sitroom-empty">No data</div>'; return; }
  let html = `<div class="sr-mini-label">${d.active_count} Active Groups</div>`;
  d.groups.forEach(g => {
    const tone = g.active ? 'danger' : 'neutral';
    const badge = g.active ? '<span class="sr-badge-live">ACTIVE</span>' : '';
    html += `<div class="sr-feed-item" data-tone="${tone}">
      <div><span class="sr-feed-title">${escapeHtml(g.name)}</span> ${badge}</div>
      <div class="sr-apt-meta">${escapeHtml(g.origin)} | ${escapeHtml(g.targets)}</div>
      <div class="sr-apt-note">${escapeHtml(g.notable)}</div>
    </div>`;
  });
  el.innerHTML = html;
}

/* ─── Situation Snapshot Card ─── */
async function loadSitroomSnapshot() {
  const el = document.getElementById('sitroom-snapshot');
  if (!el) return;
  const d = await safeFetch('/api/sitroom/situation-snapshot', {}, null);
  if (!d) { el.innerHTML = '<div class="sitroom-empty">No data</div>'; return; }
  const stats = [
    {label: 'Articles', value: d.total_articles || 0, tone: 'accent'},
    {label: 'Events', value: d.total_events || 0, tone: 'info'},
    {label: 'Earthquakes', value: d.earthquakes || 0, tone: 'danger'},
    {label: 'Fires', value: d.active_fires || 0, tone: 'warn'},
    {label: 'Conflicts', value: d.conflicts || 0, tone: 'warn'},
    {label: 'Cyber', value: d.cyber_threats || 0, tone: 'violet'},
    {label: 'OREF', value: d.oref_alerts || 0, tone: 'danger'},
    {label: 'Markets', value: d.market_symbols || 0, tone: 'good'},
    {label: 'Sources', value: d.live_sources || 0, tone: 'accent'},
  ];
  let html = '<div class="sr-snapshot-grid">';
  stats.forEach(s => {
    html += `<div class="sr-snapshot-stat">
      <div class="sr-snapshot-value" data-tone="${s.tone}">${s.value.toLocaleString()}</div>
      <div class="sr-snapshot-label">${s.label}</div>
    </div>`;
  });
  html += '</div>';
  if (d.max_magnitude) {
    html += `<div class="sr-snapshot-footer">Max quake: M${d.max_magnitude} | ${d.is_refreshing ? 'Refreshing...' : 'Idle'}</div>`;
  }
  el.innerHTML = html;
}

/* ─── P6: IndexedDB Offline Cache ─── */
const _SITROOM_DB_NAME = 'SitroomCache';
const _SITROOM_DB_VERSION = 1;
let _sitroomIDB = null;

function _initSitroomIDB() {
  if (!window.indexedDB) return;
  const req = indexedDB.open(_SITROOM_DB_NAME, _SITROOM_DB_VERSION);
  req.onupgradeneeded = (e) => {
    const db = e.target.result;
    if (!db.objectStoreNames.contains('snapshots')) {
      db.createObjectStore('snapshots', {keyPath: 'key'});
    }
    if (!db.objectStoreNames.contains('news')) {
      const store = db.createObjectStore('news', {keyPath: 'id', autoIncrement: true});
      store.createIndex('category', 'category', {unique: false});
    }
  };
  req.onsuccess = (e) => { _sitroomIDB = e.target.result; };
}

function _idbSave(storeName, data) {
  if (!_sitroomIDB) return;
  try {
    const tx = _sitroomIDB.transaction(storeName, 'readwrite');
    const store = tx.objectStore(storeName);
    if (Array.isArray(data)) {
      data.forEach(item => store.put(item));
    } else {
      store.put(data);
    }
  } catch (e) { /* IDB not available */ }
}

function _idbGet(storeName, key) {
  return new Promise((resolve) => {
    if (!_sitroomIDB) { resolve(null); return; }
    try {
      const tx = _sitroomIDB.transaction(storeName, 'readonly');
      const req = tx.objectStore(storeName).get(key);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve(null);
    } catch (e) { resolve(null); }
  });
}

/* ─── P4: Panel Resize Controls ─── */
function _initCardResize() {
  document.addEventListener('click', e => {
    const btn = e.target.closest('.sr-size-btn');
    if (!btn) return;
    const card = btn.closest('.sr-card');
    if (!card) return;
    const size = btn.dataset.size;
    if (size) {
      card.dataset.cardSize = size;
      // Persist to localStorage
      const cardId = _getSitroomPanelId(card);
      if (cardId) {
        const sizes = _readSitroomStorageObject('sitroom-card-sizes', {});
        sizes[cardId] = size;
        localStorage.setItem('sitroom-card-sizes', JSON.stringify(sizes));
      }
    }
  });
  // Restore saved sizes
  const sizes = _readSitroomStorageObject('sitroom-card-sizes', {});
  document.querySelectorAll('.sr-card').forEach(card => {
    const cardId = _getSitroomPanelId(card);
    if (cardId && sizes[cardId]) {
      card.dataset.cardSize = sizes[cardId];
    }
  });
}

/* ─── P4: Virtual Scroll for News ─── */
function _initVirtualScroll(containerId, items, renderFn, rowHeight) {
  const container = document.getElementById(containerId);
  if (!container || !items.length) return;
  rowHeight = rowHeight || 36;
  const visibleCount = Math.ceil(container.clientHeight / rowHeight) + 2;
  let scrollTop = 0;

  const totalHeight = items.length * rowHeight;
  const wrapper = document.createElement('div');
  wrapper.className = 'sr-virtual-wrapper';
  wrapper.style.setProperty('--sr-virtual-height', `${totalHeight}px`);
  container.replaceChildren(wrapper);

  function render() {
    const startIdx = Math.floor(scrollTop / rowHeight);
    const endIdx = Math.min(startIdx + visibleCount, items.length);
    const fragment = document.createDocumentFragment();
    for (let i = startIdx; i < endIdx; i++) {
      const row = document.createElement('div');
      row.className = 'sr-virtual-row';
      row.style.setProperty('--sr-virtual-top', `${i * rowHeight}px`);
      row.style.setProperty('--sr-virtual-row-height', `${rowHeight}px`);
      row.innerHTML = renderFn(items[i], i);
      fragment.appendChild(row);
    }
    wrapper.replaceChildren(fragment);
  }

  container.addEventListener('scroll', () => {
    scrollTop = container.scrollTop;
    requestAnimationFrame(render);
  });
  render();
}

/* ─── P6: Web Worker for Analysis ─── */
let _sitroomWorker = null;
function _initAnalysisWorker() {
  if (_sitroomWorker || typeof Worker === 'undefined') return;
  // Inline worker using Blob URL (no separate file needed)
  const workerCode = `
    self.onmessage = function(e) {
      const {type, data} = e.data;
      if (type === 'cluster-news') {
        const articles = data;
        const wordSets = articles.map(a => {
          const words = new Set(a.title.toLowerCase().replace(/[^\\w\\s]/g, '').split(/\\s+/));
          words.delete(''); words.delete('the'); words.delete('and'); words.delete('for');
          return words;
        });
        const used = new Set();
        const clusters = [];
        for (let i = 0; i < articles.length; i++) {
          if (used.has(i)) continue;
          const cluster = [articles[i]];
          used.add(i);
          for (let j = i + 1; j < articles.length && cluster.length < 8; j++) {
            if (used.has(j)) continue;
            const inter = [...wordSets[i]].filter(w => wordSets[j].has(w)).length;
            const union = new Set([...wordSets[i], ...wordSets[j]]).size;
            if (union > 0 && inter / union > 0.35) { cluster.push(articles[j]); used.add(j); }
          }
          if (cluster.length >= 2) {
            clusters.push({label: cluster[0].title, count: cluster.length,
              sources: [...new Set(cluster.map(c => c.source_name).filter(Boolean))],
              articles: cluster.slice(0, 5)});
          }
        }
        clusters.sort((a, b) => b.count - a.count);
        self.postMessage({type: 'cluster-result', clusters: clusters.slice(0, 20)});
      }
      if (type === 'sentiment-scan') {
        const titles = data;
        const pos = ['peace','agreement','growth','recovery','breakthrough','deal','progress','ceasefire'];
        const neg = ['attack','killed','war','crisis','crash','explosion','collapse','sanctions','missile'];
        let posCount = 0, negCount = 0;
        titles.forEach(t => {
          const tl = t.toLowerCase();
          if (pos.some(w => tl.includes(w))) posCount++;
          if (neg.some(w => tl.includes(w))) negCount++;
        });
        self.postMessage({type: 'sentiment-result', positive: posCount, negative: negCount, total: titles.length});
      }
    };
  `;
  try {
    const blob = new Blob([workerCode], {type: 'application/javascript'});
    _sitroomWorker = new Worker(URL.createObjectURL(blob));
    _sitroomWorker.onmessage = function(e) {
      if (e.data.type === 'cluster-result') {
        _renderWorkerClusters(e.data.clusters);
      }
    };
  } catch (err) { /* Web Workers not available */ }
}

function _renderWorkerClusters(clusters) {
  const el = document.getElementById('sitroom-news-clusters');
  if (!el || !clusters.length) return;
  let html = '';
  clusters.forEach(c => {
    const sources = (c.sources || []).join(', ');
    html += `<div class="sr-feed-item" data-tone="good">
      <span class="sr-feed-badge sr-feed-badge-compact" data-tone="good">${c.count}x</span>
      <span class="sr-feed-title">${escapeHtml(c.label)}</span>
      <span class="sr-feed-source">${escapeHtml(sources)}</span>
    </div>`;
  });
  el.innerHTML = html;
}

/* ─── P4: Smart Poll Loop ─── */
let _sitroomPollInterval = 60000;
let _sitroomPollFailures = 0;
let _smartPollListenerAdded = false;
function _initSmartPollLoop() {
  if (_sitroomAutoTimer) {
    clearInterval(_sitroomAutoTimer);
    _sitroomAutoTimer = null;
  }
  window.NomadShellRuntime?.stopInterval('sitroom.smart-poll');
  if (!_smartPollListenerAdded) {
    _smartPollListenerAdded = true;
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden && _isSitroomActive()) _sitroomRefreshPanels();
    });
  }
  if (window.NomadShellRuntime) {
    _sitroomAutoTimer = window.NomadShellRuntime.startInterval('sitroom.smart-poll', _smartPoll, _sitroomPollInterval, {
      tabId: 'situation-room',
      requireVisible: true,
    });
    return;
  }
  _sitroomAutoTimer = setInterval(() => {
    if (!_isSitroomActive() || document.hidden) return;
    _smartPoll();
  }, _sitroomPollInterval);
}

function _smartPoll() {
  if (document.hidden || !_isSitroomActive()) return;
  _sitroomRefreshPanels();
  // Exponential backoff on repeated empty data
  _sitroomPollFailures = Math.max(0, _sitroomPollFailures - 1);
}

/* ─── P4: Notification Sounds ─── */
let _sitroomLastQuakeAlert = 0;
function _checkQuakeAlerts() {
  const el = document.getElementById('sitroom-stat-quakes');
  if (!el) return;
  // Check for M6+ earthquakes via recent data
  safeFetch('/api/sitroom/anomalies', {}, null).then(d => {
    if (!d || !d.anomalies) return;
    const seismic = d.anomalies.find(a => a.type === 'seismic');
    if (seismic && Date.now() - _sitroomLastQuakeAlert > 300000) {
      _sitroomLastQuakeAlert = Date.now();
      _playAlertTone();
    }
  });
}

function _playAlertTone() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.value = 880;
    osc.type = 'sine';
    gain.gain.value = 0.15;
    osc.start();
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5);
    osc.stop(ctx.currentTime + 0.5);
    setTimeout(() => {
      const osc2 = ctx.createOscillator();
      const gain2 = ctx.createGain();
      osc2.connect(gain2);
      gain2.connect(ctx.destination);
      osc2.frequency.value = 660;
      osc2.type = 'sine';
      gain2.gain.value = 0.15;
      osc2.start();
      gain2.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5);
      osc2.stop(ctx.currentTime + 0.5);
    }, 200);
    setTimeout(() => ctx.close(), 1500);
  } catch (e) { /* AudioContext not available */ }
}

/* ─── P4: Data Freshness Badges ─── */
async function _updateDataFreshness() {
  const d = await safeFetch('/api/sitroom/data-freshness', {}, null);
  if (!d || !d.freshness) return;
  document.querySelectorAll('.sr-card-head').forEach(head => {
    // Remove existing badge
    const old = head.querySelector('.sr-freshness-badge');
    if (old) old.remove();
  });
  // Map source keys to card header text patterns
  const mapping = {
    'rss': 'NEWS WIRE', 'earthquakes': 'SEISMIC', 'markets': 'MARKETS',
    'aviation': 'AIRCRAFT', 'fires': 'FIRES', 'radiation': 'RADIATION',
    'oref_alerts': 'OREF', 'ais_ships': 'SHIP TRAFFIC',
  };
  for (const [key, pattern] of Object.entries(mapping)) {
    const status = d.freshness[key];
    if (!status) continue;
    const freshnessMeta = _getSitroomFreshnessMeta(status);
    document.querySelectorAll('.sr-card-head').forEach(head => {
      if (head.textContent.includes(pattern)) {
        const badge = document.createElement('span');
        badge.className = 'sr-feed-badge sr-freshness-badge';
        badge.dataset.tone = freshnessMeta.tone;
        badge.textContent = freshnessMeta.label;
        badge.title = freshnessMeta.title;
        head.appendChild(badge);
      }
    });
  }
}

// CII country click -> deep dive
document.addEventListener('click', e => {
  const row = e.target.closest('[data-cii-country]');
  if (row) openCountryDeepDive(row.dataset.ciiCountry);
});

// Live channel button clicks
document.addEventListener('click', e => {
  const btn = e.target.closest('.sr-channel-btn');
  if (!btn) return;
  document.querySelectorAll('.sr-channel-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const vid = btn.dataset.channelVid;
  if (vid) _sitroomPlayChannel(vid);
});

/* ─── P3: OREF Alerts Card ─── */
async function loadSitroomOrefAlerts() {
  const el = document.getElementById('sitroom-oref-alerts');
  if (!el) return;
  const d = await safeFetch('/api/sitroom/oref-alerts', {}, null);
  if (!d || !d.alerts || !d.alerts.length) {
    el.innerHTML = '<div class="sitroom-empty">No active OREF alerts</div>';
    return;
  }
  let html = '';
  d.alerts.forEach(a => {
    const detail = _parseSitroomDetailJson(a.detail_json);
    html += `<div class="sr-feed-item" data-tone="danger">
      ${_srFeedBadge('OREF', 'danger')}
      <span class="sr-feed-title">${escapeHtml(a.title)}</span>
      <span class="sr-feed-time">${escapeHtml(detail.date || '')}</span>
    </div>`;
  });
  el.innerHTML = html;
}

/* ─── P3: GDELT Full Card ─── */
async function loadSitroomGdeltFull() {
  const el = document.getElementById('sitroom-gdelt-full');
  if (!el) return;
  const d = await safeFetch('/api/sitroom/gdelt-full', {}, null);
  if (!d) { el.innerHTML = '<div class="sitroom-empty">No GDELT data</div>'; return; }
  let html = '';
  if (d.volume && d.volume.timeline) {
    const series = d.volume.timeline;
    if (Array.isArray(series) && series.length > 0) {
      const points = series[0].data || [];
      html += '<div class="sr-mini-label">24h Event Volume</div><div class="sr-sparkline-row">';
      const vals = points.slice(-24).map(p => p.value || 0);
      const max = Math.max(...vals, 1);
      vals.forEach(v => {
        const h = Math.max(2, (v / max) * 30);
        html += `<div class="sr-spark-bar" data-sr-spark-height="${h}" title="${v}"></div>`;
      });
      html += '</div>';
    }
  }
  if (d.tone && d.tone.timeline) {
    const series = d.tone.timeline;
    if (Array.isArray(series) && series.length > 0) {
      const points = series[0].data || [];
      const recent = points.slice(-12);
      const avg = recent.reduce((s, p) => s + (p.value || 0), 0) / (recent.length || 1);
      const sentiment = avg > 0 ? 'Positive' : avg < -2 ? 'Negative' : 'Neutral';
      const tone = avg > 0 ? 'good' : avg < -2 ? 'danger' : 'neutral';
      html += `<div class="sr-mini-label">72h Tone: <span class="sr-feed-value" data-tone="${tone}">${sentiment} (${avg.toFixed(1)})</span></div>`;
    }
  }
  if (d.hotspots) {
    html += '<div class="sr-mini-label sr-mini-label-spaced">Top Hotspots</div>';
    const pts = (d.hotspots.features || d.hotspots || []).slice(0, 5);
    pts.forEach(p => {
      const name = (p.properties && p.properties.name) || p.name || 'Location';
      const count = (p.properties && p.properties.count) || p.count || '';
      html += `<div class="sr-feed-item"><span class="sr-feed-title">${escapeHtml(name)}</span>`;
      if (count) html += _srFeedBadge(count, 'neutral');
      html += '</div>';
    });
  }
  el.innerHTML = html || '<div class="sitroom-empty">No GDELT data</div>';
  _hydrateSitroomRuntimeVars(el);
}

/* ─── P3: COT Positioning Card ─── */
async function loadSitroomCot() {
  const el = document.getElementById('sitroom-cot-positioning');
  if (!el) return;
  const d = await safeFetch('/api/sitroom/cot-positioning', {}, null);
  if (!d || !d.positions || !d.positions.length) {
    el.innerHTML = '<div class="sitroom-empty">No COT data</div>';
    return;
  }
  // Group by market, show latest for each
  const byMarket = {};
  d.positions.forEach(p => {
    const key = p.market.split(' -')[0].trim();
    if (!byMarket[key]) byMarket[key] = p;
  });
  let html = '<table class="sr-table"><tr><th>Market</th><th>Net</th><th>Long</th><th>Short</th></tr>';
  Object.entries(byMarket).slice(0, 10).forEach(([name, p]) => {
    const net = p.net_positions || 0;
    const tone = net > 0 ? 'good' : 'danger';
    const shortName = name.length > 25 ? name.substring(0, 22) + '...' : name;
    html += `<tr><td title="${escapeHtml(name)}">${escapeHtml(shortName)}</td>
      <td class="sr-table-value" data-tone="${tone}">${net > 0 ? '+' : ''}${Math.round(net).toLocaleString()}</td>
      <td>${Math.round(p.long_positions).toLocaleString()}</td>
      <td>${Math.round(p.short_positions).toLocaleString()}</td></tr>`;
  });
  html += '</table>';
  el.innerHTML = html;
}

/* ─── P3: Breaking News Detection Card ─── */
async function loadSitroomBreakingDetection() {
  const el = document.getElementById('sitroom-breaking-detection');
  if (!el) return;
  const d = await safeFetch('/api/sitroom/breaking-news', {}, null);
  if (!d || !d.breaking || !d.breaking.length) {
    el.innerHTML = '<div class="sitroom-empty">No breaking news detected</div>';
    return;
  }
  let html = '';
  d.breaking.forEach(b => {
    const urgency = b.urgency_score || 0;
    const tone = urgency >= 8 ? 'danger' : urgency >= 5 ? 'warn' : 'neutral';
    const badge = urgency >= 8 ? 'CRITICAL' : urgency >= 5 ? 'HIGH' : 'MEDIUM';
    html += `<div class="sr-feed-item" data-tone="${tone}">
      ${_srFeedBadge(badge, tone)}
      <a href="${escapeAttr(b.link || '#')}" target="_blank" class="sr-feed-title">${escapeHtml(b.title)}</a>
      <span class="sr-feed-source">${escapeHtml(b.source_name || '')}</span>
    </div>`;
  });
  el.innerHTML = html;
}

/* ─── P3: News Clusters Card ─── */
async function loadSitroomNewsClusters() {
  const el = document.getElementById('sitroom-news-clusters');
  if (!el) return;
  const d = await safeFetch('/api/sitroom/news-clusters', {}, null);
  if (!d || !d.clusters || !d.clusters.length) {
    el.innerHTML = '<div class="sitroom-empty">No clusters detected</div>';
    return;
  }
  let html = '';
  d.clusters.forEach(c => {
    const sources = (c.sources || []).filter(Boolean).join(', ');
    html += `<div class="sr-feed-item" data-tone="accent">
      ${_srFeedBadge(`${c.count}x`, 'accent')}
      <span class="sr-feed-title">${escapeHtml(c.label)}</span>
      <span class="sr-feed-source">${escapeHtml(sources)}</span>
    </div>`;
  });
  el.innerHTML = html;
}

/* ─── P3: AI Deduction Panel ─── */
async function runSitroomDeduction() {
  const el = document.getElementById('sitroom-deduction');
  if (!el) return;
  el.innerHTML = '<div class="sitroom-empty">Analyzing situation...</div>';
  const d = await safeFetch('/api/sitroom/deduction', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({focus:'global situation'})}, null);
  if (!d) { el.innerHTML = '<div class="sitroom-empty">Analysis failed</div>'; return; }
  let html = '';
  if (d.deduction) {
    html += `<div class="sr-ai-brief">${escapeHtml(d.deduction).replace(/\n/g, '<br>')}</div>`;
  } else {
    html += '<div class="sitroom-empty">AI not available — install Ollama for deduction analysis</div>';
  }
  html += `<div class="sr-mini-label sr-mini-label-spaced">${d.data_points || 0} data points analyzed</div>`;
  el.innerHTML = html;
}

/* ─── P3: Source Health Card ─── */
async function loadSitroomSourceHealth() {
  const el = document.getElementById('sitroom-source-health');
  if (!el) return;
  const d = await safeFetch('/api/sitroom/source-health', {}, null);
  if (!d || !d.sources) { el.innerHTML = '<div class="sitroom-empty">No health data</div>'; return; }
  const s = d.summary || {};
  let html = `<div class="sr-summary-chip-row">
    ${_srSummaryChip(`${s.live || 0} live`, 'good')}
    ${_srSummaryChip(`${s.stale || 0} stale`, 'warn')}
    ${_srSummaryChip(`${s.unavailable || 0} down`, 'danger')}
  </div>`;
  // Show problematic sources only
  const problems = d.sources.filter(src => src.status !== 'live').slice(0, 10);
  if (problems.length) {
    problems.forEach(src => {
      const freshnessMeta = _getSitroomFreshnessMeta(src.status);
      const ageLabel = _getSitroomSourceAgeLabel(src.age_seconds);
      html += `<div class="sr-feed-item" data-tone="${freshnessMeta.tone}">${_srFeedIcon('&#9679;', freshnessMeta.tone)}
        <span class="sr-feed-title">${escapeHtml(src.source)}</span>
        ${_srFeedBadge(freshnessMeta.label, freshnessMeta.tone)}
        <span class="sr-feed-time" title="${escapeHtml(freshnessMeta.title)}">${escapeHtml(ageLabel)}</span></div>`;
    });
  } else {
    html += '<div class="sr-feed-item" data-tone="good">All sources healthy</div>';
  }
  el.innerHTML = html;
}

/* ─── P3: Country Intelligence Brief ─── */
async function loadSitroomCountryBrief(country) {
  const el = document.getElementById('sitroom-country-brief-content');
  if (!el) return;
  el.innerHTML = '<div class="sitroom-empty">Loading intelligence brief...</div>';
  const d = await safeFetch(`/api/sitroom/country-brief/${encodeURIComponent(country)}`, {}, null);
  if (!d) { el.innerHTML = '<div class="sitroom-empty">Failed to load</div>'; return; }
  let html = `<div class="sr-mini-label">${escapeHtml(d.country)} Intelligence Brief</div>`;
  html += `<div class="sr-summary-chip-row">
    ${_srSummaryChip(`${d.news_count} articles`, 'accent')}
    ${_srSummaryChip(`${d.event_count} events`, 'warn')}
    ${_srSummaryChip(`${d.categories ? d.categories.length : 0} categories`, 'neutral')}
  </div>`;
  if (d.ai_summary) {
    html += `<div class="sr-ai-brief">${escapeHtml(d.ai_summary).replace(/\n/g, '<br>')}</div>`;
  }
  if (d.recent_news && d.recent_news.length) {
    html += '<div class="sr-mini-label sr-mini-label-spaced">Recent Headlines</div>';
    d.recent_news.slice(0, 5).forEach(n => {
      html += `<div class="sr-feed-item"><span class="sr-feed-source">${escapeHtml(n.source_name || '')}</span>
        <span class="sr-feed-title">${escapeHtml(n.title)}</span></div>`;
    });
  }
  el.innerHTML = html;
}
