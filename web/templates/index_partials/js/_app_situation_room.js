/* ─── Situation Room v2 — Global Intelligence Dashboard ─── */

let _sitroomMap = null;
let _sitroomMarkers = { earthquakes: [], weather: [], conflicts: [], aviation: [], volcanoes: [], fires: [], nuclear: [], bases: [], cables: [], datacenters: [], pipelines: [], waterways: [], spaceports: [] };
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
    setTimeout(_sitroomResizeMap, 100);
    return;
  }
  _sitroomInitDone = true;
  _sitroomRefreshPanels();
  initSitroomMap();
  _initSitroomMapResize();
  _initSitroomClock();
  _sitroomAutoRefreshIfEmpty();
  if (_sitroomAutoTimer) clearInterval(_sitroomAutoTimer);
  _sitroomAutoTimer = setInterval(_sitroomRefreshPanels, 60000);
}

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
  loadSitroomLiveChannels();
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
  {lat:51.39,lng:-1.32,name:'Aldermaston, UK'},{lat:48.86,lng:2.35,name:'CEA, France'},
  {lat:38.46,lng:-105.0,name:'NORAD, US'},{lat:35.74,lng:139.72,name:'Tokai, Japan'},
  {lat:55.75,lng:37.62,name:'Kurchatov Inst, Russia'},{lat:39.91,lng:116.39,name:'CIAE, China'},
  {lat:33.73,lng:73.05,name:'PAEC, Pakistan'},{lat:28.61,lng:77.21,name:'BARC, India'},
  {lat:32.07,lng:34.78,name:'Dimona, Israel'},{lat:35.37,lng:51.42,name:'Tehran NRC, Iran'},
  {lat:39.03,lng:125.75,name:'Yongbyon, DPRK'},{lat:47.62,lng:-122.35,name:'Hanford, US'},
  {lat:35.89,lng:-84.31,name:'Oak Ridge, US'},{lat:33.68,lng:-106.47,name:'White Sands, US'},
  {lat:36.95,lng:-116.05,name:'Nevada Test Site, US'},{lat:50.10,lng:36.23,name:'Kharkiv NPI, Ukraine'},
  {lat:57.74,lng:59.98,name:'Mayak, Russia'},{lat:61.26,lng:73.36,name:'Seversk, Russia'},
  {lat:41.18,lng:69.24,name:'Tashkent, Uzbekistan'},{lat:45.94,lng:-119.04,name:'Columbia Gen, US'},
  {lat:51.56,lng:-0.73,name:'Burghfield, UK'},{lat:44.26,lng:26.06,name:'Cernavoda, Romania'},
  {lat:46.46,lng:30.66,name:'Odesa NPP, Ukraine'},{lat:51.39,lng:30.10,name:'Chernobyl, Ukraine'},
  {lat:47.51,lng:34.59,name:'Zaporizhzhia NPP, Ukraine'},
];
const _MILITARY_BASES = [
  {lat:36.77,lng:-76.29,name:'Norfolk Naval, US'},{lat:32.87,lng:-117.14,name:'Camp Pendleton, US'},
  {lat:38.95,lng:-77.45,name:'Dulles/CIA, US'},{lat:38.87,lng:-77.06,name:'Pentagon, US'},
  {lat:26.30,lng:50.21,name:'NSA Bahrain'},{lat:25.41,lng:51.25,name:'Al Udeid, Qatar'},
  {lat:24.43,lng:54.65,name:'Al Dhafra, UAE'},{lat:11.55,lng:43.15,name:'Camp Lemonnier, Djibouti'},
  {lat:36.15,lng:-5.35,name:'Gibraltar'},{lat:35.09,lng:33.27,name:'Akrotiri, Cyprus'},
  {lat:37.09,lng:24.94,name:'Souda Bay, Greece'},{lat:41.05,lng:28.95,name:'Incirlik, Turkey'},
  {lat:49.20,lng:-2.13,name:'HMNB Devonport, UK'},{lat:48.45,lng:-4.42,name:'Brest Naval, France'},
  {lat:35.45,lng:139.35,name:'Yokosuka, Japan'},{lat:33.45,lng:126.57,name:'Jeju, South Korea'},
  {lat:1.35,lng:103.82,name:'Changi Naval, Singapore'},{lat:-34.73,lng:138.57,name:'Edinburgh, Australia'},
  {lat:21.35,lng:-157.95,name:'Pearl Harbor, US'},{lat:22.32,lng:114.17,name:'Stonecutters Island, HK'},
  {lat:59.95,lng:30.32,name:'Kronstadt, Russia'},{lat:44.62,lng:33.53,name:'Sevastopol, Russia'},
  {lat:69.08,lng:33.42,name:'Severomorsk, Russia'},{lat:53.01,lng:158.65,name:'Petropavlovsk, Russia'},
  {lat:18.27,lng:109.58,name:'Yulin, China'},{lat:38.05,lng:121.37,name:'Lushun, China'},
  {lat:36.07,lng:120.38,name:'Qingdao, China'},{lat:30.00,lng:122.15,name:'Zhoushan, China'},
  {lat:37.47,lng:126.62,name:'Pyeongtaek/Osan, S. Korea'},{lat:51.28,lng:-0.77,name:'Aldershot, UK'},
  {lat:48.73,lng:44.50,name:'Volgograd, Russia'},{lat:55.01,lng:82.93,name:'Novosibirsk, Russia'},
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
];
const _DATA_CENTERS = [
  {lat:39.04,lng:-77.49,name:'Ashburn VA, US (largest cluster)'},{lat:37.37,lng:-121.92,name:'Santa Clara CA, US'},
  {lat:53.35,lng:-6.26,name:'Dublin, Ireland (EU hub)'},{lat:50.11,lng:8.68,name:'Frankfurt, Germany'},
  {lat:52.37,lng:4.90,name:'Amsterdam, Netherlands'},{lat:51.50,lng:-0.12,name:'London, UK'},
  {lat:59.33,lng:18.07,name:'Stockholm, Sweden'},{lat:1.35,lng:103.82,name:'Singapore'},
  {lat:35.68,lng:139.69,name:'Tokyo, Japan'},{lat:22.32,lng:114.17,name:'Hong Kong'},
  {lat:37.57,lng:126.98,name:'Seoul, South Korea'},{lat:-33.87,lng:151.21,name:'Sydney, Australia'},
  {lat:25.20,lng:55.27,name:'Dubai, UAE'},{lat:19.08,lng:72.88,name:'Mumbai, India'},
  {lat:-23.55,lng:-46.63,name:'Sao Paulo, Brazil'},{lat:45.50,lng:-73.57,name:'Montreal, Canada'},
  {lat:47.61,lng:-122.33,name:'Seattle WA, US'},{lat:33.75,lng:-84.39,name:'Atlanta GA, US'},
  {lat:41.88,lng:-87.63,name:'Chicago IL, US'},{lat:32.78,lng:-96.80,name:'Dallas TX, US'},
];

const _PIPELINE_HUBS = [
  {lat:51.50,lng:3.60,name:'Rotterdam Pipeline Hub, NL'},{lat:60.39,lng:5.32,name:'Bergen Gas Hub, NO'},
  {lat:56.15,lng:10.21,name:'Denmark Gas Junction'},{lat:41.01,lng:28.98,name:'TurkStream Landing, TR'},
  {lat:54.32,lng:13.09,name:'Nord Stream Landing, DE'},{lat:36.80,lng:10.18,name:'TransMed Pipeline, TN'},
  {lat:31.25,lng:32.31,name:'East Med Gas Hub, EG'},{lat:40.41,lng:49.87,name:'BTC Pipeline, AZ'},
  {lat:29.37,lng:47.97,name:'Kuwait Oil Hub'},{lat:26.22,lng:50.55,name:'Bahrain Oil Hub'},
  {lat:51.88,lng:55.10,name:'Druzhba Pipeline Hub, RU'},{lat:52.52,lng:104.30,name:'ESPO Pipeline, RU'},
  {lat:39.91,lng:116.39,name:'China Gas Hub, Beijing'},{lat:29.76,lng:-95.37,name:'Houston Pipeline Hub, US'},
  {lat:30.07,lng:-89.93,name:'Gulf Coast LOOP, US'},{lat:51.05,lng:-114.07,name:'Alberta Pipeline Hub, CA'},
];
const _STRATEGIC_WATERWAYS = [
  {lat:30.45,lng:32.35,name:'Suez Canal, Egypt'},{lat:12.60,lng:43.15,name:'Bab el-Mandeb Strait'},
  {lat:26.57,lng:56.25,name:'Strait of Hormuz'},{lat:1.25,lng:103.75,name:'Strait of Malacca'},
  {lat:41.17,lng:29.07,name:'Bosphorus Strait, Turkey'},{lat:9.08,lng:-79.68,name:'Panama Canal'},
  {lat:35.97,lng:-5.50,name:'Strait of Gibraltar'},{lat:36.95,lng:22.48,name:'Cape Matapan, Greece'},
  {lat:-34.62,lng:20.00,name:'Cape of Good Hope'},{lat:-54.80,lng:-68.30,name:'Drake Passage'},
  {lat:61.10,lng:-45.00,name:'Denmark Strait'},{lat:54.00,lng:7.90,name:'Kiel Canal, Germany'},
  {lat:48.40,lng:-4.50,name:'English Channel entrance'},{lat:10.40,lng:107.00,name:'South China Sea chokepoint'},
];
const _SPACEPORTS = [
  {lat:28.57,lng:-80.65,name:'Kennedy Space Center, US'},{lat:34.63,lng:-120.63,name:'Vandenberg SFB, US'},
  {lat:45.92,lng:63.34,name:'Baikonur Cosmodrome, KZ'},{lat:62.93,lng:40.58,name:'Plesetsk, Russia'},
  {lat:5.24,lng:-52.77,name:'Guiana Space Centre, FR'},{lat:19.61,lng:110.95,name:'Wenchang, China'},
  {lat:40.96,lng:100.30,name:'Jiuquan, China'},{lat:28.25,lng:102.03,name:'Xichang, China'},
  {lat:13.72,lng:80.23,name:'Satish Dhawan, India'},{lat:31.25,lng:131.08,name:'Tanegashima, Japan'},
  {lat:-2.95,lng:40.21,name:'Luigi Broglio, Kenya (San Marco)'},{lat:28.24,lng:-16.64,name:'El Hierro (proposed), Spain'},
  {lat:25.99,lng:-97.15,name:'SpaceX Starbase, US'},{lat:-31.04,lng:136.50,name:'Woomera, Australia'},
  {lat:57.44,lng:-4.26,name:'Sutherland Spaceport, UK'},{lat:69.30,lng:16.02,name:'Andoya, Norway'},
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
}

function clearSitroomMarkers(layerType) {
  const arr = _sitroomMarkers[layerType];
  if (arr) { arr.forEach(m => m.remove()); arr.length = 0; }
}

function addSitroomMarker(ev, layerType) {
  if (!_sitroomMap) return;
  const colors = { earthquakes: '#ff4444', weather: '#ffaa00', conflicts: '#ff6600', aviation: '#44aaff', volcanoes: '#ff3366', fires: '#ff8800', nuclear: '#ffff00', bases: '#44ff88', cables: '#3388ff', datacenters: '#aa66ff', pipelines: '#cc8844', waterways: '#00ddff', spaceports: '#ff66ff' };
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
  renderSitroomSpaceWeather(d.space_weather);
  _updateThreatLevel(d);
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

/* ─── Breaking News Banner ─── */
async function renderSitroomBreakingNews() {
  const el = document.getElementById('sr-breaking-text');
  if (!el) return;
  const d = await safeFetch('/api/sitroom/news?limit=15', {}, null);
  if (!d || !d.articles?.length) { el.textContent = 'No breaking news'; return; }
  const text = d.articles.map(a => escapeHtml(a.title)).join('  ///  ');
  el.innerHTML = text + '  ///  ' + text; // duplicate for seamless scroll
}

/* ─── Market Ribbon ─── */
function renderSitroomMarketRibbon(markets) {
  const el = document.getElementById('sr-market-ribbon');
  if (!el || !markets?.length) return;
  el.innerHTML = markets.map(m => {
    const ch = m.change_24h || 0;
    const cls = ch >= 0 ? 'sr-ribbon-up' : 'sr-ribbon-down';
    const arrow = ch >= 0 ? '+' : '';
    let price;
    if (m.market_type === 'sentiment') price = m.price + '/100';
    else if (m.price >= 1) price = '$' + Number(m.price).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
    else price = '$' + Number(m.price).toFixed(4);
    return `<span class="sr-ribbon-item"><span class="sr-ribbon-sym">${escapeHtml(m.label || m.symbol)}</span> ${price} <span class="${cls}">${arrow}${ch.toFixed(1)}%</span></span>`;
  }).join('');
}

/* ─── Country Instability Index ─── */
async function loadSitroomCII() {
  const el = document.getElementById('sr-cii-list');
  if (!el) return;
  // Compute CII from event data — count events per country
  const events = await safeFetch('/api/sitroom/events?limit=500', {}, null);
  if (!events || !events.events?.length) { el.innerHTML = '<div class="sr-empty">No data for CII</div>'; return; }
  const countryScores = {};
  events.events.forEach(ev => {
    let det = {};
    try { det = ev.detail_json ? JSON.parse(ev.detail_json) : {}; } catch(e) {}
    const country = det.country || 'Unknown';
    if (country === 'Unknown' || !country) return;
    if (!countryScores[country]) countryScores[country] = { events: 0, severity: 0 };
    countryScores[country].events++;
    if (ev.magnitude) countryScores[country].severity += ev.magnitude;
    if (det.severity === 'Extreme') countryScores[country].severity += 5;
    if (det.severity === 'Severe') countryScores[country].severity += 3;
    if (det.alert_level === 'Red') countryScores[country].severity += 4;
    if (det.alert_level === 'Orange') countryScores[country].severity += 2;
  });
  const sorted = Object.entries(countryScores)
    .map(([c, s]) => ({ country: c, score: Math.min(100, Math.round(s.events * 3 + s.severity * 2)), events: s.events }))
    .sort((a, b) => b.score - a.score)
    .slice(0, 20);
  if (!sorted.length) { el.innerHTML = '<div class="sr-empty">No country data</div>'; return; }
  const maxScore = sorted[0].score || 1;
  el.innerHTML = sorted.map(c => {
    const cls = c.score >= 60 ? 'sr-cii-high' : c.score >= 30 ? 'sr-cii-med' : 'sr-cii-low';
    const color = c.score >= 60 ? '#e05050' : c.score >= 30 ? '#d4a017' : '#2aad94';
    return `<div class="sr-cii-row" style="cursor:pointer" data-cii-country="${escapeAttr(c.country)}">
      <span class="sr-cii-country">${escapeHtml(c.country)}</span>
      <div class="sr-cii-bar"><div class="sr-cii-bar-fill" style="width:${(c.score/maxScore*100).toFixed(0)}%;background:${color}"></div></div>
      <span class="sr-cii-score ${cls}">${c.score}</span>
    </div>`;
  }).join('');
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
    let det = {}; try { det = o.detail_json ? JSON.parse(o.detail_json) : {}; } catch(e) {}
    return `<div class="sitroom-event-item">
      <span class="sitroom-mag" style="background:#3388ff;color:#fff">NET</span>
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
  const color = val <= 25 ? '#e05050' : val <= 45 ? '#d4a017' : val <= 55 ? '#888' : val <= 75 ? '#2aad94' : '#4aedc4';
  // Needle rotation: 0=left (-90deg), 100=right (90deg)
  const deg = -90 + (val / 100) * 180;
  el.innerHTML = `<div class="sr-fg-gauge">
    <div class="sr-fg-arc"></div>
    <div class="sr-fg-needle" style="transform:rotate(${deg}deg)"></div>
  </div>
  <div class="sr-fg-value" style="color:${color}">${val}</div>
  <div class="sr-fg-label">${escapeHtml(label.toUpperCase())}</div>`;
}

/* ─── Fires ─── */
async function loadSitroomFires() {
  const d = await safeFetch('/api/sitroom/fires?limit=50', {}, null);
  const el = document.getElementById('sitroom-fires-list');
  if (!el) return;
  if (!d || !d.fires?.length) { el.innerHTML = '<div class="sr-empty">No fire data</div>'; return; }
  el.innerHTML = d.fires.slice(0, 30).map(f => {
    let det = {}; try { det = f.detail_json ? JSON.parse(f.detail_json) : {}; } catch(e) {}
    const bright = f.magnitude ? f.magnitude.toFixed(0) + 'K' : '?';
    return `<div class="sitroom-event-item">
      <span class="sitroom-mag" style="background:#ff8800">${bright}</span>
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
    let det = {}; try { det = o.detail_json ? JSON.parse(o.detail_json) : {}; } catch(e) {}
    return `<div class="sitroom-event-item">
      <div class="sitroom-event-info">
        <div class="sitroom-event-title" title="${escapeAttr(o.title || '')}">${escapeHtml(o.title || 'Outbreak')}</div>
        <div class="sitroom-event-meta">${det.published ? escapeHtml(det.published) : ''}</div>
      </div>
      ${o.source_url ? `<a href="${escapeAttr(o.source_url)}" target="_blank" rel="noopener" class="sitroom-event-link">&#8599;</a>` : ''}
    </div>`;
  }).join('');
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
  setInterval(tick, 1000);
}

/* ─── Radiation Watch ─── */
async function loadSitroomRadiation() {
  const d = await safeFetch('/api/sitroom/radiation', {}, null);
  const el = document.getElementById('sitroom-radiation');
  if (!el) return;
  if (!d || !d.readings?.length) { el.innerHTML = '<div class="sr-empty">No radiation data</div>'; return; }
  el.innerHTML = d.readings.slice(0, 20).map(r => {
    let det = {}; try { det = r.detail_json ? JSON.parse(r.detail_json) : {}; } catch(e) {}
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
    let det = {}; try { det = t.detail_json ? JSON.parse(t.detail_json) : {}; } catch(e) {}
    const tone = t.magnitude || 0;
    const toneColor = tone > 2 ? '#4aedc4' : tone < -2 ? '#e05050' : '#888';
    return `<div class="sitroom-news-item">
      <span class="sitroom-news-cat" style="background:${tone > 0 ? '#0f5040' : '#3a1515'}">${tone > 0 ? '+' : ''}${tone.toFixed(1)}</span>
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
    let det = {}; try { det = s.detail_json ? JSON.parse(s.detail_json) : {}; } catch(e) {}
    return `<div class="sitroom-event-item">
      <div class="sitroom-event-info">
        <div class="sitroom-event-title" title="${escapeAttr(s.title || '')}">${escapeHtml(s.title || '')}</div>
        <div class="sitroom-event-meta">${escapeHtml(det.category || '')}${det.published ? ' | ' + escapeHtml(det.published) : ''}</div>
      </div>
      ${s.source_url ? `<a href="${escapeAttr(s.source_url)}" target="_blank" rel="noopener" class="sitroom-event-link">&#8599;</a>` : ''}
    </div>`;
  }).join('');
}

/* ─── UNHCR Displacement ─── */
async function loadSitroomDisplacement() {
  const d = await safeFetch('/api/sitroom/displacement', {}, null);
  const el = document.getElementById('sitroom-displacement');
  if (!el) return;
  if (!d || !d.records?.length) { el.innerHTML = '<div class="sr-empty">No displacement data</div>'; return; }
  el.innerHTML = d.records.map(r => {
    let det = {}; try { det = r.detail_json ? JSON.parse(r.detail_json) : {}; } catch(e) {}
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
  const panel = document.getElementById('sr-country-panel');
  const nameEl = document.getElementById('sr-country-name');
  const body = document.getElementById('sr-country-body');
  if (!panel || !body) return;
  nameEl.textContent = country.toUpperCase();
  panel.hidden = false;
  body.innerHTML = '<div class="sr-empty"><div class="sr-radar"></div>Loading intelligence...</div>';

  const d = await safeFetch('/api/sitroom/country/' + encodeURIComponent(country), {}, null);
  if (!d) { body.innerHTML = '<div class="sr-empty">No data available</div>'; return; }

  let html = '';

  // Event summary
  if (d.event_summary && Object.keys(d.event_summary).length) {
    html += '<div class="sr-country-section"><div class="sr-country-section-title">EVENT SIGNALS</div>';
    for (const [type, count] of Object.entries(d.event_summary)) {
      html += `<div class="sr-country-stat"><span>${escapeHtml(type.replace(/_/g, ' '))}</span><span class="sr-country-stat-val">${count}</span></div>`;
    }
    html += '</div>';
  }

  // Recent quakes
  if (d.recent_quakes?.length) {
    html += '<div class="sr-country-section"><div class="sr-country-section-title">SEISMIC ACTIVITY</div>';
    d.recent_quakes.forEach(q => {
      html += `<div class="sr-country-stat"><span>${escapeHtml(q.title || '')}</span><span class="sr-country-stat-val">M${q.magnitude || '?'}</span></div>`;
    });
    html += '</div>';
  }

  // Recent news
  if (d.recent_news?.length) {
    html += '<div class="sr-country-section"><div class="sr-country-section-title">RECENT INTELLIGENCE</div>';
    d.recent_news.forEach(n => {
      html += `<div class="sitroom-news-item" style="padding:3px 0">
        <span class="sitroom-news-cat">${escapeHtml(n.category || '')}</span>
        <div class="sitroom-news-body">
          <a href="${escapeAttr(n.link || '#')}" target="_blank" rel="noopener" class="sitroom-news-title">${escapeHtml(n.title)}</a>
          <div class="sitroom-news-meta">${escapeHtml(n.source_name || '')}</div>
        </div>
      </div>`;
    });
    html += '</div>';
  }

  if (!html) html = '<div class="sr-empty">No intelligence signals for this country</div>';
  body.innerHTML = html;
}

/* ─── Live YouTube Channels ─── */
let _sitroomChannelsLoaded = false;
async function loadSitroomLiveChannels() {
  if (_sitroomChannelsLoaded) return;
  _sitroomChannelsLoaded = true;
  const d = await safeFetch('/api/sitroom/live-channels', {}, null);
  const btns = document.getElementById('sr-channel-btns');
  if (!btns || !d || !d.channels?.length) return;
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
  player.innerHTML = `<iframe src="https://www.youtube.com/embed/${encodeURIComponent(videoId)}?autoplay=1&mute=1&controls=1" frameborder="0" allow="autoplay; encrypted-media" allowfullscreen style="width:100%;height:100%;border:0;background:#000"></iframe>`;
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
  if (a === 'close-country') {
    const cp = document.getElementById('sr-country-panel');
    if (cp) cp.hidden = true;
  }
});

document.getElementById('sitroom-news-category')?.addEventListener('change', () => loadSitroomNews());
document.getElementById('sitroom-quake-filter')?.addEventListener('change', () => renderSitroomQuakes());
document.querySelectorAll('[data-sitroom-layer]').forEach(cb => cb.addEventListener('change', () => loadSitroomMapData()));

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
