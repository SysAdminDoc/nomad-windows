/* ─── Situation Room v2 — Global Intelligence Dashboard ─── */

let _sitroomMap = null;
let _sitroomMarkers = { earthquakes: [], weather: [], conflicts: [], aviation: [], volcanoes: [] };
let _sitroomNewsOffset = 0;
const SITROOM_NEWS_PAGE = 50;
let _sitroomAutoTimer = null;
let _sitroomInitDone = false;
let _sitroomNewsCat = ''; // preserve category across refreshes

/* ─── Init ─── */
function initSituationRoom() {
  _closeSitroomOverlays();
  setTimeout(_closeSitroomOverlays, 500);

  if (_sitroomInitDone) {
    _sitroomRefreshPanels();
    return;
  }
  _sitroomInitDone = true;
  _sitroomRefreshPanels();
  initSitroomMap();
  _sitroomAutoRefreshIfEmpty();
  if (_sitroomAutoTimer) clearInterval(_sitroomAutoTimer);
  _sitroomAutoTimer = setInterval(_sitroomRefreshPanels, 60000);
}

function _sitroomRefreshPanels() {
  loadSitroomSummary();
  loadSitroomNews();
  loadSitroomFeeds();
}

async function _sitroomAutoRefreshIfEmpty() {
  const d = await safeFetch('/api/sitroom/status', {}, null);
  if (d && d.feed_count > 0 && (!d.last_fetch || Object.keys(d.last_fetch).length === 0)) {
    refreshSitroomFeeds();
  }
}

/* ─── Close Overlays / Copilot Dock ─── */
function _closeSitroomOverlays() {
  ['lan-chat-panel', 'timer-panel', 'quick-actions-menu'].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.classList.add('is-hidden'); el.hidden = true; }
  });
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
  const dock = document.getElementById('copilot-dock');
  if (dock) dock.style.removeProperty('display');
  ['lan-chat-panel', 'timer-panel', 'quick-actions-menu'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.hidden = false;
  });
}

/* ─── Map ─── */
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
    _sitroomMap.on('load', () => loadSitroomMapData());
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
}

function clearSitroomMarkers(layerType) {
  const arr = _sitroomMarkers[layerType];
  if (arr) { arr.forEach(m => m.remove()); arr.length = 0; }
}

function addSitroomMarker(ev, layerType) {
  if (!_sitroomMap) return;
  const colors = { earthquakes: '#ff4444', weather: '#ffaa00', conflicts: '#ff6600', aviation: '#44aaff', volcanoes: '#ff3366' };
  const color = colors[layerType] || '#ffffff';
  let size = layerType === 'aviation' ? 5 : 8;
  if (ev.magnitude) size = Math.max(6, Math.min(24, ev.magnitude * 3));

  const el = document.createElement('div');
  el.className = 'sitroom-marker sitroom-marker-' + layerType;
  el.style.cssText = `width:${size}px;height:${size}px;background:${color};border-radius:50%;border:1px solid rgba(255,255,255,0.3);cursor:pointer;box-shadow:0 0 ${size}px ${color}40;`;

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
  renderSitroomSpaceWeather(d.space_weather);
  renderSitroomQuakes();
  loadSitroomWeather();
  loadSitroomPredictions();
  loadSitroomMapData();
}

/* ─── Markets ─── */
function renderSitroomMarkets(markets) {
  const c = document.getElementById('sitroom-market-ticker');
  if (!c) return;
  if (!markets.length) { c.innerHTML = '<div class="sitroom-empty">No market data — click Refresh</div>'; return; }
  c.innerHTML = markets.map(m => {
    const ch = m.change_24h || 0;
    const up = ch >= 0;
    const cls = up ? 'sitroom-market-up' : 'sitroom-market-down';
    let price;
    if (m.market_type === 'sentiment') price = m.price + '/100';
    else if (m.price >= 1) price = '$' + Number(m.price).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
    else price = '$' + Number(m.price).toFixed(6);
    return `<div class="sitroom-market-card ${cls}">
      <div class="sitroom-market-symbol">${escapeHtml(m.label || m.symbol)}</div>
      <div class="sitroom-market-price">${price}</div>
      <div class="sitroom-market-change">${up ? '&#9650;' : '&#9660;'} ${Math.abs(ch).toFixed(1)}%</div>
    </div>`;
  }).join('');
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
    let det = {}; try { det = q.detail_json ? JSON.parse(q.detail_json) : {}; } catch(e) {}
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
    let det = {}; try { det = a.detail_json ? JSON.parse(a.detail_json) : {}; } catch(e) {}
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
        <div class="sitroom-prediction-yes" style="width:${yPct}%">${yPct}%</div>
        <div class="sitroom-prediction-no" style="width:${nPct}%">${nPct}%</div>
      </div>
      <div class="sitroom-prediction-meta">Vol: $${Number(p.volume || 0).toLocaleString(undefined, {maximumFractionDigits: 0})}</div>
    </div>`;
  }).join('');
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
    if (!append) { list.innerHTML = '<div class="sitroom-empty">No news cached — click Refresh Feeds</div>'; if (more) more.style.display = 'none'; }
    return;
  }
  const html = d.articles.map(a => `<div class="sitroom-news-item">
    <span class="sitroom-news-cat">${escapeHtml(a.category || '')}</span>
    <div class="sitroom-news-body">
      <a href="${escapeAttr(a.link || '#')}" target="_blank" rel="noopener" class="sitroom-news-title">${escapeHtml(a.title)}</a>
      <div class="sitroom-news-meta">${escapeHtml(a.source_name || '')} ${a.published ? '| ' + escapeHtml(a.published) : ''}</div>
    </div>
  </div>`).join('');
  if (append) list.insertAdjacentHTML('beforeend', html); else list.innerHTML = html;
  _sitroomNewsOffset += d.articles.length;
  if (more) more.style.display = _sitroomNewsOffset < (d.total || 0) ? '' : 'none';
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
  const btn = document.getElementById('sitroom-gen-briefing');
  const c = document.getElementById('sitroom-briefing-content');
  if (!c) return;
  if (btn) btn.disabled = true;
  c.innerHTML = '<div class="sitroom-loading">Generating intelligence briefing...</div>';
  try {
    const resp = await fetch('/api/sitroom/ai-briefing', { method: 'POST', headers: {'Content-Type': 'application/json'} });
    const d = await resp.json();
    if (!resp.ok) { c.innerHTML = '<div class="sitroom-empty">' + escapeHtml(d.error || 'Briefing failed') + '</div>'; return; }
    c.innerHTML = '<div class="sitroom-briefing-text">' + _renderBriefing(d.briefing || '') + '</div>';
  } catch (e) {
    c.innerHTML = '<div class="sitroom-empty">Network error generating briefing</div>';
  } finally { if (btn) btn.disabled = false; }
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
    const resp = await fetch('/api/sitroom/feeds', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name: n, url: u, category: cat}) });
    const d = await resp.json();
    if (resp.ok) { toast('Feed added', 'success'); document.getElementById('sitroom-feed-name').value = ''; document.getElementById('sitroom-feed-url').value = ''; loadSitroomFeeds(); }
    else toast(d.error || 'Failed', 'error');
  } catch (e) { toast('Network error', 'error'); }
}

async function deleteSitroomFeed(id) {
  try {
    const resp = await fetch('/api/sitroom/feeds/' + id, {method: 'DELETE'});
    if (resp.ok) { toast('Feed removed', 'success'); loadSitroomFeeds(); }
    else { const d = await resp.json().catch(() => ({})); toast(d.error || 'Failed', 'error'); }
  } catch (e) {}
}

/* ─── Refresh with polling ─── */
async function refreshSitroomFeeds() {
  const btn = document.getElementById('sitroom-refresh-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Refreshing...'; }
  try {
    const resp = await fetch('/api/sitroom/refresh', {method: 'POST'});
    if (resp.ok) {
      toast('Feed refresh started', 'info');
      _pollSitroomRefresh();
    }
  } catch (e) { toast('Refresh failed', 'error'); }
  finally { if (btn) { btn.disabled = false; btn.textContent = 'Refresh Feeds'; } }
}

function _pollSitroomRefresh() {
  let attempts = 0;
  const poll = setInterval(async () => {
    attempts++;
    const d = await safeFetch('/api/sitroom/status', {}, null);
    if (!d) return;
    if (!d.refreshing || attempts >= 20) {
      clearInterval(poll);
      _sitroomRefreshPanels();
      return;
    }
    if (attempts % 3 === 0) _sitroomRefreshPanels(); // partial updates every ~9s
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

/* ─── Events ─── */
document.addEventListener('click', e => {
  const ctrl = e.target.closest('[data-sitroom-action]');
  if (!ctrl) return;
  const a = ctrl.dataset.sitroomAction;
  if (a === 'refresh') refreshSitroomFeeds();
  if (a === 'generate-briefing') generateSitroomBriefing();
  if (a === 'add-feed') addSitroomFeed();
  if (a === 'delete-feed') deleteSitroomFeed(ctrl.dataset.feedId);
  if (a === 'load-more-news') loadSitroomNews(true);
});

document.getElementById('sitroom-news-category')?.addEventListener('change', () => loadSitroomNews());
document.getElementById('sitroom-quake-filter')?.addEventListener('change', () => renderSitroomQuakes());
document.querySelectorAll('[data-sitroom-layer]').forEach(cb => cb.addEventListener('change', () => loadSitroomMapData()));
