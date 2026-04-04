// NukeMap v3.3.0 - Main Application Controller
window.NM = window.NM || {};

(function() {
'use strict';

let map, currentDets = [], windAngle = 0, multiMode = false, mirvMode = false, currentMirvPreset = null;
let factRotationIntervalId = 0, factHideTimeoutId = 0, zipcodesLoadRequested = false, nukemapTabObserver = null;
let factIdx = Math.floor(Math.random() * NM.Facts.length);
const OFFLINE_ATLAS_STORAGE_KEY = 'nomad-offline-atlas-cache';
const OFFLINE_ATLAS_VERSION = '2026-04-02.3';
const OFFLINE_ATLAS_URL = '/nukemap/data/offline_atlas.json';
let offlineAtlasInstallPromise = null;
let offlineAtlasData = null;
let offlineAtlasState = 'missing';
let offlineAtlasError = '';
NM._nightMode = false;
NM.getUiRoot = function() {
  return document.getElementById('nukemap-stage') || document.getElementById('tab-nukemap') || document.body;
};

function setOfflineAtlasState(state, error) {
  offlineAtlasState = state;
  offlineAtlasError = error || '';
}

function normalizeAtlasFlatFeature(feature, extraKeys = []) {
  if (!feature || !Array.isArray(feature.points) || feature.points.length < 4) return null;
  const points = feature.points.map((value) => Number(value));
  if (points.some((value) => !Number.isFinite(value))) return null;
  let bbox = Array.isArray(feature.bbox) && feature.bbox.length === 4
    ? feature.bbox.map((value) => Number(value))
    : null;
  if (!bbox || bbox.some((value) => !Number.isFinite(value))) {
    let minLng = 999;
    let minLat = 999;
    let maxLng = -999;
    let maxLat = -999;
    for (let idx = 0; idx < points.length; idx += 2) {
      const lng = points[idx];
      const lat = points[idx + 1];
      minLng = Math.min(minLng, lng);
      minLat = Math.min(minLat, lat);
      maxLng = Math.max(maxLng, lng);
      maxLat = Math.max(maxLat, lat);
    }
    bbox = [minLng, minLat, maxLng, maxLat];
  }
  const normalized = {
    minZoom: Number.isFinite(Number(feature.minZoom)) ? Number(feature.minZoom) : null,
    bbox,
    points,
  };
  extraKeys.forEach((key) => {
    if (feature[key] !== undefined && feature[key] !== null && feature[key] !== '') {
      normalized[key] = feature[key];
    }
  });
  return normalized;
}

function normalizeOfflineAtlas(atlas) {
  if (
    !atlas ||
    !Array.isArray(atlas.land) ||
    !Array.isArray(atlas.coastlines) ||
    !Array.isArray(atlas.countryBorders) ||
    !Array.isArray(atlas.admin1Borders) ||
    !Array.isArray(atlas.lakes) ||
    !Array.isArray(atlas.rivers) ||
    !Array.isArray(atlas.places)
  ) return null;
  return {
    version: atlas.version || OFFLINE_ATLAS_VERSION,
    source: atlas.source || null,
    land: atlas.land.map((feature) => normalizeAtlasFlatFeature(feature)).filter(Boolean),
    lakes: atlas.lakes.map((feature) => normalizeAtlasFlatFeature(feature, ['name'])).filter(Boolean),
    coastlines: atlas.coastlines.map((feature) => normalizeAtlasFlatFeature(feature)).filter(Boolean),
    countryBorders: atlas.countryBorders.map((feature) => normalizeAtlasFlatFeature(feature, ['name'])).filter(Boolean),
    admin1Borders: atlas.admin1Borders.map((feature) => normalizeAtlasFlatFeature(feature, ['name', 'adm0_name'])).filter(Boolean),
    rivers: atlas.rivers.map((feature) => normalizeAtlasFlatFeature(feature, ['name'])).filter(Boolean),
    places: atlas.places.filter((place) =>
      typeof place?.lat === 'number' &&
      typeof place?.lng === 'number' &&
      place?.name
    ).map((place) => ({
      name: place.name,
      lat: Number(place.lat),
      lng: Number(place.lng),
      pop: Number(place.pop) || 0,
      rank: Number(place.rank) || 5,
      minZoom: Number.isFinite(Number(place.minZoom)) ? Number(place.minZoom) : null,
      capital: !!place.capital,
      world: !!place.world,
      adm0: place.adm0 || '',
    })),
  };
}

function loadOfflineAtlasFromStorage() {
  try {
    const raw = window.localStorage?.getItem(OFFLINE_ATLAS_STORAGE_KEY);
    if (!raw) {
      setOfflineAtlasState('missing');
      return null;
    }
    const parsed = normalizeOfflineAtlas(JSON.parse(raw));
    if (!parsed || parsed.version !== OFFLINE_ATLAS_VERSION) {
      window.localStorage?.removeItem(OFFLINE_ATLAS_STORAGE_KEY);
      setOfflineAtlasState('missing');
      return null;
    }
    offlineAtlasData = parsed;
    setOfflineAtlasState('ready');
    return parsed;
  } catch (_error) {
    offlineAtlasData = null;
    setOfflineAtlasState('missing');
    return null;
  }
}

function persistOfflineAtlas(atlas) {
  const normalized = normalizeOfflineAtlas(atlas);
  if (!normalized) throw new Error('Offline atlas data is invalid.');
  normalized.version = OFFLINE_ATLAS_VERSION;
  offlineAtlasData = normalized;
  window.localStorage?.setItem(OFFLINE_ATLAS_STORAGE_KEY, JSON.stringify(normalized));
  setOfflineAtlasState('ready');
  return normalized;
}

loadOfflineAtlasFromStorage();

NM.hasOfflineAtlas = function() {
  return !!offlineAtlasData;
};
NM.getOfflineAtlasData = function() {
  return offlineAtlasData;
};
NM.getOfflineAtlasState = function() {
  return {
    ready: !!offlineAtlasData,
    state: offlineAtlasState,
    error: offlineAtlasError,
    version: offlineAtlasData?.version || null
  };
};
NM.isOfflineAtlasInstalling = function() {
  return offlineAtlasState === 'installing';
};
NM.projectLngToTileX = function(lng, zoom) {
  return Math.pow(2, zoom) * ((lng + 180) / 360);
};
NM.projectLatToTileY = function(lat, zoom) {
  const safeLat = Math.max(-85.05112878, Math.min(85.05112878, lat));
  const radians = safeLat * Math.PI / 180;
  return Math.pow(2, zoom) * (1 - (Math.log(Math.tan(radians) + 1 / Math.cos(radians)) / Math.PI)) / 2;
};
NM.projectTileXToLng = function(tileX, zoom) {
  return (tileX / Math.pow(2, zoom)) * 360 - 180;
};
NM.projectTileYToLat = function(tileY, zoom) {
  const n = Math.PI - (2 * Math.PI * tileY) / Math.pow(2, zoom);
  return (180 / Math.PI) * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)));
};
NM.getOfflineAtlasPalette = function(theme) {
  const activeTheme = theme || document.documentElement.getAttribute('data-theme') || 'nomad';
  const palettes = {
    nomad: {
      ocean: '#d7e4f0',
      grid: 'rgba(86, 104, 129, 0.16)',
      land: '#f8fbfd',
      coast: '#51657a',
      countryBorder: 'rgba(70, 89, 112, 0.62)',
      admin1Border: 'rgba(124, 144, 168, 0.38)',
      lake: '#c7dcf4',
      river: 'rgba(102, 145, 196, 0.58)',
      city: '#1c2d3f',
      capital: '#0f1722',
      cityHalo: 'rgba(255, 255, 255, 0.92)',
      label: '#162132',
      labelHalo: 'rgba(255, 255, 255, 0.96)'
    },
    nightops: {
      ocean: '#071018',
      grid: 'rgba(131, 160, 194, 0.15)',
      land: '#172433',
      coast: '#94bae8',
      countryBorder: 'rgba(171, 201, 237, 0.74)',
      admin1Border: 'rgba(109, 135, 164, 0.42)',
      lake: '#102338',
      river: 'rgba(107, 155, 214, 0.6)',
      city: '#f0c27a',
      capital: '#ffe0ae',
      cityHalo: 'rgba(7, 16, 24, 0.92)',
      label: '#e4f0ff',
      labelHalo: 'rgba(7, 16, 24, 0.98)'
    },
    cyber: {
      ocean: '#07131e',
      grid: 'rgba(110, 199, 255, 0.15)',
      land: '#133043',
      coast: '#6ed6ff',
      countryBorder: 'rgba(135, 223, 255, 0.7)',
      admin1Border: 'rgba(90, 165, 196, 0.38)',
      lake: '#0f2232',
      river: 'rgba(83, 195, 231, 0.64)',
      city: '#bff264',
      capital: '#f7ffb4',
      cityHalo: 'rgba(7, 19, 30, 0.93)',
      label: '#e2f8ff',
      labelHalo: 'rgba(7, 19, 30, 0.98)'
    },
    redlight: {
      ocean: '#190d13',
      grid: 'rgba(255, 169, 169, 0.14)',
      land: '#2a151d',
      coast: '#ff9b90',
      countryBorder: 'rgba(255, 180, 168, 0.66)',
      admin1Border: 'rgba(184, 109, 109, 0.34)',
      lake: '#24161c',
      river: 'rgba(255, 149, 120, 0.38)',
      city: '#ffd39a',
      capital: '#fff0cc',
      cityHalo: 'rgba(25, 13, 19, 0.92)',
      label: '#ffe9de',
      labelHalo: 'rgba(25, 13, 19, 0.97)'
    },
    eink: {
      ocean: '#f1f0eb',
      grid: 'rgba(44, 44, 44, 0.12)',
      land: '#ffffff',
      coast: '#202020',
      countryBorder: 'rgba(37, 37, 37, 0.58)',
      admin1Border: 'rgba(92, 92, 92, 0.32)',
      lake: '#e2e5ea',
      river: 'rgba(88, 88, 88, 0.24)',
      city: '#111111',
      capital: '#000000',
      cityHalo: 'rgba(243, 242, 237, 0.96)',
      label: '#111111',
      labelHalo: 'rgba(243, 242, 237, 0.98)'
    }
  };
  return palettes[activeTheme] || palettes.nomad;
};
NM.buildOfflineAtlasLayer = function(theme) {
  const OfflineAtlasLayer = L.GridLayer.extend({
    initialize(options = {}) {
      this._theme = options.theme || document.documentElement.getAttribute('data-theme') || 'nomad';
      L.GridLayer.prototype.initialize.call(this, Object.assign({
        attribution: 'Offline atlas | Natural Earth | NukeMap',
        maxZoom: 12,
        tileSize: 256,
        updateWhenIdle: true
      }, options));
    },
    createTile(coords) {
      const tile = document.createElement('canvas');
      const size = this.getTileSize();
      const context = tile.getContext('2d');
      const zoom = coords.z;
      const atlas = NM.getOfflineAtlasData();
      const palette = NM.getOfflineAtlasPalette(this._theme);
      const fallbackLand = Object.entries(NM.WORLD || {}).map(([id, points]) => ({
        id,
        minZoom: 0,
        bbox: null,
        points: points.flat(),
      }));
      const land = atlas?.land?.length ? atlas.land : fallbackLand;
      const lakes = atlas?.lakes || [];
      const coastlines = atlas?.coastlines || [];
      const countryBorders = atlas?.countryBorders || [];
      const admin1Borders = atlas?.admin1Borders || [];
      const rivers = atlas?.rivers || [];
      const places = atlas?.places || [];
      const wrapOffsets = [-1, 0, 1];
      const tileBounds = {
        west: NM.projectTileXToLng(coords.x, zoom),
        east: NM.projectTileXToLng(coords.x + 1, zoom),
        north: NM.projectTileYToLat(coords.y, zoom),
        south: NM.projectTileYToLat(coords.y + 1, zoom),
      };
      const shouldRenderFeature = (feature, fallbackMinZoom = 0) => {
        const minZoom = Number.isFinite(feature?.minZoom) ? feature.minZoom : fallbackMinZoom;
        return zoom >= Math.max(0, Math.floor(minZoom));
      };
      const bboxVisible = (bbox, wrapOffset = 0, padding = 0) => {
        if (!Array.isArray(bbox) || bbox.length !== 4) return true;
        const west = bbox[0] + wrapOffset * 360;
        const south = bbox[1];
        const east = bbox[2] + wrapOffset * 360;
        const north = bbox[3];
        return !(
          east < tileBounds.west - padding ||
          west > tileBounds.east + padding ||
          north < tileBounds.south - padding ||
          south > tileBounds.north + padding
        );
      };
      const drawPath = (points, wrapOffset, closePath) => {
        context.beginPath();
        let firstPoint = true;
        for (let idx = 0; idx < points.length; idx += 2) {
          const lng = points[idx];
          const lat = points[idx + 1];
          const pixelX = (NM.projectLngToTileX(lng + wrapOffset * 360, zoom) - coords.x) * size.x;
          const pixelY = (NM.projectLatToTileY(lat, zoom) - coords.y) * size.y;
          if (firstPoint) {
            context.moveTo(pixelX, pixelY);
            firstPoint = false;
          } else {
            context.lineTo(pixelX, pixelY);
          }
        }
        if (closePath) context.closePath();
        return !firstPoint;
      };
      const drawPolygonFeature = (feature, wrapOffset) => {
        if (!shouldRenderFeature(feature) || !bboxVisible(feature.bbox, wrapOffset, 1.2)) return;
        if (drawPath(feature.points, wrapOffset, true)) context.fill();
      };
      const drawLineFeature = (feature, wrapOffset) => {
        if (!shouldRenderFeature(feature) || !bboxVisible(feature.bbox, wrapOffset, 1.4)) return;
        if (drawPath(feature.points, wrapOffset, false)) context.stroke();
      };

      tile.width = size.x;
      tile.height = size.y;
      context.fillStyle = palette.ocean;
      context.fillRect(0, 0, size.x, size.y);

      const gridStep = zoom < 2 ? 45 : zoom < 4 ? 30 : zoom < 6 ? 15 : 10;
      context.strokeStyle = palette.grid;
      context.lineWidth = 0.6;
      for (let lat = -80; lat <= 80; lat += gridStep) {
        const y = (NM.projectLatToTileY(lat, zoom) - coords.y) * size.y;
        if (y < -size.y || y > size.y * 2) continue;
        context.beginPath();
        context.moveTo(0, y);
        context.lineTo(size.x, y);
        context.stroke();
      }
      for (let lng = -180; lng <= 180; lng += gridStep) {
        wrapOffsets.forEach((wrapOffset) => {
          const x = (NM.projectLngToTileX(lng + wrapOffset * 360, zoom) - coords.x) * size.x;
          if (x < -size.x || x > size.x * 2) return;
          context.beginPath();
          context.moveTo(x, 0);
          context.lineTo(x, size.y);
          context.stroke();
        });
      }

      context.fillStyle = palette.land;
      land.forEach((feature) => {
        wrapOffsets.forEach((wrapOffset) => drawPolygonFeature(feature, wrapOffset));
      });

      if (lakes.length) {
        context.fillStyle = palette.lake;
        lakes.forEach((feature) => {
          wrapOffsets.forEach((wrapOffset) => drawPolygonFeature(feature, wrapOffset));
        });
      }

      if (rivers.length && zoom >= 2) {
        context.strokeStyle = palette.river;
        context.lineWidth = zoom >= 5 ? 1.35 : zoom >= 3 ? 1 : 0.75;
        rivers.forEach((feature) => {
          wrapOffsets.forEach((wrapOffset) => drawLineFeature(feature, wrapOffset));
        });
      }

      context.strokeStyle = palette.coast;
      context.lineWidth = zoom >= 4 ? 1.5 : 1.1;
      coastlines.forEach((feature) => {
        wrapOffsets.forEach((wrapOffset) => drawLineFeature(feature, wrapOffset));
      });

      if (countryBorders.length) {
        context.strokeStyle = palette.countryBorder;
        context.lineWidth = zoom >= 4 ? 1.05 : 0.85;
        countryBorders.forEach((feature) => {
          wrapOffsets.forEach((wrapOffset) => drawLineFeature(feature, wrapOffset));
        });
      }

      if (admin1Borders.length && zoom >= 3) {
        context.strokeStyle = palette.admin1Border;
        context.lineWidth = zoom >= 6 ? 0.9 : 0.65;
        admin1Borders.forEach((feature) => {
          wrapOffsets.forEach((wrapOffset) => drawLineFeature(feature, wrapOffset));
        });
      }

      if (places.length) {
        const shouldShowPlace = (place) => {
          const datasetZoom = Number.isFinite(place.minZoom) ? Math.max(0, Math.floor(place.minZoom)) : 0;
          const placeZoom = place.world ? 1 : place.capital ? 2 : place.pop >= 5000000 ? 2 : place.pop >= 1000000 ? 3 : place.pop >= 250000 ? 4 : 5;
          return zoom >= Math.max(datasetZoom, placeZoom);
        };
        context.textBaseline = 'middle';
        context.lineJoin = 'round';
        context.lineCap = 'round';
        wrapOffsets.forEach((wrapOffset) => {
          places.forEach((place) => {
            if (!shouldShowPlace(place)) return;
            const x = (NM.projectLngToTileX(place.lng + wrapOffset * 360, zoom) - coords.x) * size.x;
            const y = (NM.projectLatToTileY(place.lat, zoom) - coords.y) * size.y;
            if (x < -60 || x > size.x + 60 || y < -20 || y > size.y + 24) return;
            const important = place.capital || place.world || place.pop >= 5000000;
            const dotRadius = zoom >= 5 ? (important ? 2.8 : 2.1) : (important ? 2.3 : 1.8);
            context.fillStyle = palette.cityHalo;
            context.beginPath();
            context.arc(x, y, dotRadius + 1.2, 0, Math.PI * 2);
            context.fill();
            context.fillStyle = important ? palette.capital : palette.city;
            context.beginPath();
            context.arc(x, y, dotRadius, 0, Math.PI * 2);
            context.fill();
            const fontSize = zoom >= 6 ? 11 : zoom >= 4 ? 10 : 9;
            context.font = `${important ? 600 : 500} ${fontSize}px "Segoe UI", sans-serif`;
            context.lineWidth = 3;
            context.strokeStyle = palette.labelHalo;
            context.strokeText(place.name, x + dotRadius + 4, y);
            context.fillStyle = palette.label;
            context.fillText(place.name, x + dotRadius + 4, y);
          });
        });
      }

      return tile;
    },
    setTheme(themeName) {
      this._theme = themeName || this._theme;
      this.redraw();
    },
    syncAtlas() {
      this.redraw();
    }
  });

  return new OfflineAtlasLayer({ theme });
};
NM.installOfflineAtlas = function() {
  if (offlineAtlasData) {
    NM.refreshOfflineAtlasUi?.();
    return Promise.resolve(offlineAtlasData);
  }
  if (offlineAtlasInstallPromise) return offlineAtlasInstallPromise;
  setOfflineAtlasState('installing');
  NM.refreshOfflineAtlasUi?.();
  offlineAtlasInstallPromise = fetch(OFFLINE_ATLAS_URL, { cache: 'no-store' })
    .then((response) => {
      if (!response.ok) throw new Error(`Offline basemap install failed (${response.status}).`);
      return response.json();
    })
    .then((atlas) => {
      const storedAtlas = persistOfflineAtlas(atlas);
      NM.LayerSwitcher?.refreshOfflineAtlasLayer?.();
      NM.LayerSwitcher?.applyTheme?.(document.documentElement.getAttribute('data-theme') || 'nomad');
      NM.switchToPreferredMapLayer?.('offline-atlas-ready');
      NM.refreshOfflineAtlasUi?.();
      showBadge('atlas', 'Offline Basemap Ready');
      return storedAtlas;
    })
    .catch((error) => {
      offlineAtlasData = null;
      setOfflineAtlasState('error', error?.message || 'Offline basemap install failed.');
      NM.refreshOfflineAtlasUi?.();
      throw error;
    })
    .finally(() => {
      offlineAtlasInstallPromise = null;
    });
  return offlineAtlasInstallPromise;
};
NM.ensureOfflineAtlas = function() {
  if (offlineAtlasData) {
    NM.refreshOfflineAtlasUi?.();
    return Promise.resolve(offlineAtlasData);
  }
  return NM.installOfflineAtlas();
};
NM.refreshOfflineAtlasUi = function() {
  const status = document.getElementById('welcome-atlas-status');
  const button = document.getElementById('welcome-dismiss');
  const ready = !!offlineAtlasData;
  const installing = offlineAtlasState === 'installing';
  const failed = offlineAtlasState === 'error';
  if (status) {
    status.dataset.state = ready ? 'ready' : installing ? 'installing' : failed ? 'error' : 'missing';
    if (ready) {
      status.textContent = 'Enhanced offline basemap ready. NukeMap now has real coastlines, country borders, state and province outlines, lakes, rivers, and place labels offline.';
    } else if (installing) {
      status.textContent = 'Installing the enhanced offline basemap with real boundaries and labels so NukeMap stays usable without internet.';
    } else if (failed) {
      status.textContent = offlineAtlasError || 'Offline basemap install failed. Retry to restore the enhanced offline map.';
    } else {
      status.textContent = 'NukeMap will install the enhanced offline basemap before you start so the map is available with proper boundaries and labels.';
    }
  }
  if (button) {
    if (ready) {
      button.disabled = false;
      button.textContent = 'Start Exploring';
    } else if (installing) {
      button.disabled = true;
      button.textContent = 'Installing Offline Basemap…';
    } else if (failed) {
      button.disabled = false;
      button.textContent = 'Retry Basemap Install';
    } else {
      button.disabled = false;
      button.textContent = 'Install Basemap & Start';
    }
  }
};
NM.getThemeMapLayerName = function(theme) {
  if (NM.hasOfflineAtlas()) return 'offlineAtlas';
  if (!navigator.onLine) return 'offlineAtlas';
  return ({
    nomad: 'terrain',
    nightops: 'dark',
    cyber: 'darkClean',
    redlight: 'dark',
    eink: 'positron'
  })[theme] || 'terrain';
};
NM.isStandaloneRoute = function() {
  return /^\/nukemap(?:\/|$)/.test(window.location.pathname || '');
};
NM.queryUiAll = function(selector) {
  const root = document.getElementById('tab-nukemap') || document;
  return [...root.querySelectorAll(selector)];
};
NM.queryUi = function(selector) {
  const root = document.getElementById('tab-nukemap') || document;
  return root.querySelector(selector);
};
NM.protectOverlayInteractions = function(selectors) {
  if (!window.L?.DomEvent) return;
  selectors.forEach((selector) => {
    const el = document.querySelector(selector);
    if (!el) return;
    L.DomEvent.disableClickPropagation(el);
    L.DomEvent.disableScrollPropagation(el);
  });
};
NM.isWorkspaceVisible = function() {
  const tabRoot = document.getElementById('tab-nukemap');
  if (tabRoot) return tabRoot.classList.contains('active') && document.visibilityState === 'visible';
  return document.visibilityState === 'visible';
};
NM.ensureZipcodesLoaded = function() {
  if (zipcodesLoadRequested || NM.ZIPDB) return false;
  if (document.querySelector('script[data-nukemap-zipcodes="true"]')) {
    zipcodesLoadRequested = true;
    return false;
  }
  zipcodesLoadRequested = true;
  const script = document.createElement('script');
  script.src = '/nukemap/js/zipcodes.js';
  script.async = true;
  script.dataset.nukemapZipcodes = 'true';
  script.addEventListener('error', () => { zipcodesLoadRequested = false; });
  document.body.appendChild(script);
  return true;
};
NM.stopFactRotation = function() {
  if (factRotationIntervalId) {
    clearInterval(factRotationIntervalId);
    factRotationIntervalId = 0;
  }
  if (factHideTimeoutId) {
    clearTimeout(factHideTimeoutId);
    factHideTimeoutId = 0;
  }
  const banner = document.getElementById('fact-banner');
  if (banner) banner.classList.remove('show');
};
NM.startFactRotation = function(options = {}) {
  if (!NM.isWorkspaceVisible()) return;
  if (!factRotationIntervalId || options.immediate) showFact();
  if (factRotationIntervalId) return;
  factRotationIntervalId = setInterval(showFact, 30000);
};
NM.syncAmbientUi = function(options = {}) {
  if (NM.isWorkspaceVisible()) {
    NM.ensureZipcodesLoaded();
    NM.startFactRotation({ immediate: !!options.immediate });
  } else {
    NM.stopFactRotation();
  }
};
NM.getHostSnapshot = function() {
  return {
    embedded: !NM.isStandaloneRoute(),
    workspaceVisible: NM.isWorkspaceVisible(),
    mapReady: !!NM._map,
    currentLayer: NM.LayerSwitcher?.current || null,
    offlineAtlasReady: NM.hasOfflineAtlas(),
    offlineAtlasInstalling: NM.isOfflineAtlasInstalling(),
    zipcodesLoaded: !!NM.ZIPDB,
    zipcodesRequested: !!zipcodesLoadRequested,
    factRotationActive: !!factRotationIntervalId,
    factVisible: !!document.getElementById('fact-banner')?.classList.contains('show'),
    nightMode: !!NM._nightMode,
  };
};

function getTabButtons() {
  const embeddedRoot = document.getElementById('tab-nukemap');
  if (embeddedRoot) {
    const embeddedTabs = embeddedRoot.querySelectorAll('.nk-tab');
    if (embeddedTabs.length) return [...embeddedTabs];
  }
  return [...document.querySelectorAll('.tab')];
}

function getTabPanes() {
  const embeddedRoot = document.getElementById('tab-nukemap');
  if (embeddedRoot) {
    const embeddedPanes = embeddedRoot.querySelectorAll('.nk-tab-pane');
    if (embeddedPanes.length) return [...embeddedPanes];
  }
  return [...document.querySelectorAll('.tab-content')];
}

function showFact() {
  const banner = $('fact-banner');
  const text = $('fact-text');
  if (!banner || !text) return;
  if (factHideTimeoutId) clearTimeout(factHideTimeoutId);
  text.textContent = NM.Facts[factIdx % NM.Facts.length];
  banner.classList.add('show');
  factIdx++;
  factHideTimeoutId = setTimeout(() => {
    banner.classList.remove('show');
    factHideTimeoutId = 0;
  }, 12000);
}

// ---- MAP INIT ----
function initMap() {
  map = L.map('map', {center: [39.83, -98.58], zoom: 5, zoomControl: true, attributionControl: true, zoomSnap: 0.5});
  NM.protectOverlayInteractions([
    '#panel',
    '#welcome-overlay',
    '#flash',
    '#coords',
    '#offline-badge',
    '#det-counter',
    '#ms-panel',
    '#nukemap-search-results'
  ]);
  L.control.scale({position: 'bottomleft', imperial: true, metric: true, maxWidth: 200}).addTo(map);
  NM._map = map; // expose for mushroom3d positioning
  const dark = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://osm.org">OSM</a> &copy; <a href="https://carto.com">CARTO</a>',
    subdomains: 'abcd', maxZoom: 19
  });

  // Offline canvas tiles
  const Offline = L.TileLayer.extend({
    createTile(coords) {
      const c = document.createElement('canvas'), s = this.getTileSize(); c.width = s.x; c.height = s.y;
      const ctx = c.getContext('2d'), z = coords.z;
      ctx.fillStyle = '#11111b'; ctx.fillRect(0, 0, s.x, s.y);
      ctx.strokeStyle = 'rgba(69,71,90,0.25)'; ctx.lineWidth = 0.5;
      const gs = z < 3 ? 30 : z < 6 ? 10 : 5;
      for (let lat = -80; lat <= 80; lat += gs) { const y = (this._l2y(lat, z) - coords.y) * s.y; if (y > -s.y && y < s.y * 2) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(s.x, y); ctx.stroke(); if (z >= 2) { ctx.fillStyle = 'rgba(108,112,134,0.4)'; ctx.font = '8px sans-serif'; ctx.fillText(lat + '\u00B0', 2, y - 1); ctx.fillStyle = 'transparent'; } } }
      for (let lng = -180; lng <= 180; lng += gs) { const x = (this._l2x(lng, z) - coords.x) * s.x; if (x > -s.x && x < s.x * 2) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, s.y); ctx.stroke(); } }
      ctx.strokeStyle = 'rgba(137,180,250,0.35)'; ctx.lineWidth = 1; ctx.fillStyle = 'rgba(49,50,68,0.5)';
      for (const sh of Object.values(NM.WORLD)) { ctx.beginPath(); let f = true; for (const [lng, lat] of sh) { const px = (this._l2x(lng, z) - coords.x) * s.x, py = (this._l2y(lat, z) - coords.y) * s.y; f ? (ctx.moveTo(px, py), f = false) : ctx.lineTo(px, py); } ctx.closePath(); ctx.fill(); ctx.stroke(); }
      return c;
    },
    _l2y(lat, z) { const n = Math.pow(2, z), r = lat * Math.PI / 180; return n * (1 - (Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI)) / 2; },
    _l2x(lng, z) { return Math.pow(2, z) * ((lng + 180) / 360); }
  });
  const offline = new Offline('', {maxZoom: 12, attribution: 'Offline fallback | NukeMap'});

  let loaded = false;
  dark.on('tileerror', () => { if (!loaded) { loaded = true; map.removeLayer(dark); offline.addTo(map); showBadge(false); } });
  dark.on('tileload', () => { loaded = true; });
  dark.addTo(map);
  if (!navigator.onLine) { offline.addTo(map); showBadge(false); } else showBadge(true);
  window.addEventListener('online', () => showBadge(true));
  window.addEventListener('offline', () => showBadge(false));

  map.on('click', e => onMapClick(e.latlng.lat, e.latlng.lng));
  map.on('contextmenu', e => { e.originalEvent.preventDefault(); onMapClick(e.latlng.lat, e.latlng.lng); });
  map.on('mousemove', e => { document.getElementById('coords').textContent = `${e.latlng.lat.toFixed(4)}, ${e.latlng.lng.toFixed(4)}`; });
  map.on('moveend zoomend', () => { if (NM.Mushroom3D.active) NM.Mushroom3D.onMapMove(); });
  map.getContainer().classList.add('crosshair');

  // Dismiss loading overlay once first tile loads
  const lo = document.getElementById('loading-overlay');
  if (lo) {
    const dismiss = () => {
      if (!lo.isConnected) return;
      lo.classList.add('hidden');
      setTimeout(() => lo.remove(), 600);
    };
    NM.dismissLoading = dismiss;
    dark.once('load', dismiss);
    setTimeout(dismiss, 4000); // fallback
  }

  NM.Heatmap.init(map);
  loadFromURL();
}

function showBadge(on, labelText) {
  const b = document.getElementById('offline-badge'), d = b.querySelector('.ob-dot'), l = b.querySelector('.ob-lbl');
  const state = typeof on === 'string' ? on : (on ? 'on' : 'off');
  b.classList.add('show');
  d.className = 'ob-dot ' + state;
  l.textContent = labelText || (state === 'on' ? 'Online' : state === 'atlas' ? 'Offline Basemap Ready' : 'Offline');
  if (state !== 'off') setTimeout(() => b.classList.remove('show'), 3200);
}

// ---- MAP CLICK ----
function onMapClick(lat, lng) {
  // Experience mode: analyze click point vs last detonation
  if (NM.Experience.active && currentDets.length) {
    NM.Experience.analyze(map, lat, lng, currentDets[currentDets.length - 1]);
    return;
  }
  // Measurement tool
  if (NM.Measure.active) {
    NM.Measure.addPoint(map, lat, lng);
    return;
  }
  // MIRV mode
  if (mirvMode && currentMirvPreset) {
    NM.MIRV.execute(map, lat, lng, currentMirvPreset, (la, ln, yk) => {
      const origYield = getYield();
      setYield(yk || origYield);
      triggerDetonation(la, ln);
      setYield(origYield);
    });
    return;
  }
  triggerDetonation(lat, lng);
}

// ---- DETONATION ----
function triggerDetonation(lat, lng) {
  const Y = getYield();
  let burst = getBurst();
  const isHEMP = burst === 'hemp';
  if (isHEMP) burst = 'airburst'; // HEMP uses airburst physics but overrides effects
  const hM = burst === 'custom' ? (+$('burst-height').value || 0) : 0;
  const fission = +$('fission-pct').value || 50;
  const effects = NM.calcEffects(Y, isHEMP ? 'airburst' : burst, hM, fission);

  // HEMP override: no blast/thermal at ground level, massive EMP
  if (isHEMP) {
    effects.fireball = 0; effects.psi200 = 0; effects.psi20 = 0; effects.psi5 = 0;
    effects.psi3 = 0; effects.psi1 = 0; effects.thermal3 = 0; effects.thermal2 = 0;
    effects.thermal1 = 0; effects.radiation = 0; effects.craterR = 0; effects.craterDepth = 0;
    effects.firestormR = 0; effects.flashBlindDay = 0; effects.flashBlindNight = 0;
    effects.fallout = null;
    effects.emp = Math.min(2200, 40 * Math.pow(Y, 0.25)); // continent-scale EMP
    effects.burstHeight = 400000; // 400 km
    effects.isSurface = false;
  }
  const cas = isHEMP ? {deaths: 0, injuries: 0, density: 0} : NM.estimateCasualties(lat, lng, effects);

  // Single mode: clear previous
  if (!multiMode) {
    currentDets.forEach(d => d.layers.forEach(l => map.removeLayer(l)));
    currentDets = [];
    NM.Mushroom3D.hide();
  }

  const det = {
    id: Date.now(), lat, lng, yieldKt: Y, burstType: isHEMP ? 'hemp' : burst, heightM: hM, fission, effects, casualties: cas, layers: [],
    weapon: $('weapon-select').selectedOptions[0]?.textContent || 'Custom', isHEMP
  };

  // Draw static effect rings
  const ringLayers = NM.Effects.drawRings(map, det);
  det.layers.push(...ringLayers);

  // Fallout
  if (effects.fallout) {
    const fl = NM.Effects.drawFallout(map, lat, lng, effects.fallout, windAngle);
    if (fl) { fl.addTo(map); det.layers.push(fl); }
  }

  // GZ marker
  const marker = NM.Effects.drawMarker(map, lat, lng).bindPopup(NM.Effects.buildPopup(det)).addTo(map);
  det.layers.push(marker);

  currentDets.push(det);

  // Animations
  NM.Animation.detonateSequence(map, lat, lng, effects, Y);

  // 3D mushroom cloud
  if ($('cloud-toggle')?.checked) {
    setTimeout(() => NM.Mushroom3D.show(det, multiMode), 500);
  }

  // Update all UI panels
  updateDetsList();
  updateLegend(det);
  updateStats();
  updateCloud(det);
  updateTimeline(det);
  updateCrater(det);
  updateShelter(det);

  $('dets-section').style.display = '';

  // Extras: update overlays based on toggle state
  if ($('ringlabels-check').checked) NM.RingLabels.draw(map, det);
  if ($('distrings-check').checked) {
    const maxR = Math.max(effects.psi1, effects.thermal1, effects.emp);
    NM.DistanceRings.draw(map, det.lat, det.lng, maxR);
  }
  if ($('distfromgz-check').checked) NM.DistanceIndicator.start(map, det.lat, det.lng);
  if ($('thermal-check').checked) NM.ThermalOverlay.draw(map, det.lat, det.lng, effects);
  if ($('falloutanim-check').checked && effects.fallout) NM.FalloutParticles.start(map, det.lat, det.lng, effects.fallout, windAngle);
  if ($('radoverlay-check').checked) NM.RadiationOverlay.draw(map, det.lat, det.lng, effects);
  if ($('dmgheatmap-check').checked) NM.DamageHeatmap.draw(map, currentDets);

  // Show radiation decay & psi sections in Tools tab
  if (effects.isSurface) $('raddecay-section').style.display = '';
  $('psi-section').style.display = '';
  $('psi-result').innerHTML = NM.CustomPsi.generateHTML(Y);

  // Yield comparison chart
  $('yieldchart-section').style.display = '';
  $('yield-chart').innerHTML = NM.YieldChart.generate(Y);

  // Nuclear winter estimate
  const totalYield = currentDets.reduce((s, d) => s + d.yieldKt, 0);
  if (totalYield > 10) {
    $('nw-section').style.display = '';
    $('nw-result').innerHTML = NM.NuclearWinter.generateHTML(totalYield, currentDets.length);
  }

  // Premium panels
  $('altitude-section').style.display = '';
  $('altitude-profile').innerHTML = NM.AltitudeProfile.generate(effects, Y);

  $('zonecas-section').style.display = '';
  $('zonecas-content').innerHTML = NM.ZoneCasualties.generate(effects, cas.density);

  $('destruction-section').style.display = '';
  $('destruction-content').innerHTML = NM.DestructionStats.generate(effects, cas);

  $('emp-section').style.display = '';
  $('emp-content').innerHTML = NM.EMPDetails.generate(effects.emp);

  $('survival-section').style.display = '';
  $('survival-content').innerHTML = NM.SurvivalCalc.generateHTML(effects);

  const wInfo = NM.WeaponInfo.generate(det.weapon);
  if (wInfo) { $('weaponinfo-section').style.display = ''; $('weaponinfo-content').innerHTML = wInfo; }
  else $('weaponinfo-section').style.display = 'none';

  // Nearby strategic targets
  updateNearbyTargets(det);

  // Ground-level experience report
  $('ground-section').style.display = '';
  $('ground-content').innerHTML = NM.GroundReport.generate(effects, Y);

  // Cloud height comparison
  $('cloudcompare-section').style.display = '';
  $('cloudcompare-content').innerHTML = NM.CloudCompare.generate(effects);

  // Emergency guide
  $('guide-section').style.display = '';
  $('guide-content').innerHTML = NM.EmergencyGuide.generate(det);

  // Dose calculator visibility
  if (effects.isSurface) $('dosecalc-section').style.display = '';

  // Seismic equivalent
  $('seismic-section').style.display = '';
  $('seismic-content').innerHTML = NM.Seismic.generateHTML(Y, effects.isSurface);

  // Conventional weapon comparison
  $('conventional-section').style.display = '';
  $('conventional-content').innerHTML = NM.ConventionalCompare.generate(Y);

  // Building damage
  $('bldgdmg-section').style.display = '';
  $('bldgdmg-content').innerHTML = NM.BuildingDamage.generate(Y);

  // Size comparisons
  $('sizecompare-section').style.display = '';
  $('sizecompare-content').innerHTML = NM.SizeCompare.generate(effects);

  // Fallout time-lapse visibility
  if (effects.fallout) $('fallout-timelapse').style.display = '';

  // Escape time
  $('escape-section').style.display = '';
  $('escape-content').innerHTML = NM.EscapeTime.generate(effects);

  // Casualty counter animation
  NM.CasualtyCounter.animate(cas.deaths, cas.injuries);

  // Shockwave ring
  if ($('shockwave-check')?.checked) NM.ShockwaveRing.draw(map, lat, lng, effects);

  // Fallout contours
  if ($('contours-check')?.checked && effects.fallout) NM.FalloutContours.draw(map, lat, lng, effects.fallout, windAngle);

  // Store last det ref for GPS/Geiger
  NM._lastDet = det;

  // Draggable GZ
  if ($('draggable-check').checked) {
    NM.DraggableGZ.enable(map, det, (newLat, newLng) => {
      removeDet(currentDets.length - 1);
      triggerDetonation(newLat, newLng);
    });
  }

  // Auto-switch to Effects tab after first detonation
  if (currentDets.length === 1) switchTab('effects');

  // Detonation toast
  showDetToast(det);

  // No auto-zoom — let user control the map view

  updateURL();
}

// ---- UI HELPERS ----
function $(id) { return document.getElementById(id); }

NM.switchToPreferredMapLayer = function() {
  const theme = document.documentElement.getAttribute('data-theme') || 'nomad';
  const preferredLayer = NM.getThemeMapLayerName(theme);
  const preferredMapLayer = NM.LayerSwitcher?.layers?.[preferredLayer];
  if (!preferredMapLayer || typeof NM.LayerSwitcher?.switchTo !== 'function') return false;
  if (typeof preferredMapLayer.once === 'function' && NM.dismissLoading) preferredMapLayer.once('load', NM.dismissLoading);
  NM.LayerSwitcher.applyTheme?.(theme);
  if (NM.LayerSwitcher.current !== preferredLayer) NM.LayerSwitcher.switchTo(preferredLayer);
  return true;
};
function getYield() { return NM.sliderToYield(+$('yield-slider').value); }
function getBurst() { return NM.queryUi('.burst-btn.active')?.dataset.burst || 'airburst'; }

function setYield(kt) {
  $('yield-slider').value = NM.yieldToSlider(kt);
  updateYieldUI(kt);
  syncYieldInput(kt);
}

function updateYieldUI(kt) {
  const v = $('yield-val'), u = $('yield-unit');
  if (kt >= 1000) { v.textContent = (kt / 1000).toFixed(kt >= 10000 ? 0 : 1); u.textContent = 'MT'; }
  else if (kt >= 1) { v.textContent = kt.toFixed(kt >= 100 ? 0 : 1); u.textContent = 'kT'; }
  else { v.textContent = (kt * 1000).toFixed(kt < 0.01 ? 1 : 0); u.textContent = 'tons'; }
}

function syncYieldInput(kt) {
  const yi = $('yield-input'), yu = $('yield-unit-select');
  if (kt >= 1000) { yi.value = (kt / 1000).toFixed(2); yu.value = 'mt'; }
  else if (kt >= 1) { yi.value = kt.toFixed(2); yu.value = 'kt'; }
  else { yi.value = (kt * 1000).toFixed(1); yu.value = 't'; }
}

// ---- CONTROLS INIT ----
function initControls() {
  // Tabs
  getTabButtons().forEach((tabButton) => {
    const tabId = tabButton.dataset.nktab || tabButton.dataset.tab;
    if (!tabId) return;
    tabButton.addEventListener('click', () => switchTab(tabId));
  });

  // Weapon select (grouped by country)
  const sel = $('weapon-select');
  const groups = {};
  NM.WEAPONS.forEach((w, i) => { const g = w.country || 'Custom'; if (!groups[g]) groups[g] = []; groups[g].push({...w, idx: i}); });
  for (const [g, ws] of Object.entries(groups)) {
    const og = document.createElement('optgroup'); og.label = g;
    ws.forEach(w => { const o = document.createElement('option'); o.value = w.idx; o.textContent = `${w.name} (${NM.fmtYield(w.yield_kt)})`; o.title = w.desc; og.appendChild(o); });
    sel.appendChild(og);
  }
  sel.addEventListener('change', () => setYield(NM.WEAPONS[sel.value].yield_kt));

  // Weapon filter
  $('weapon-filter').addEventListener('input', () => {
    const q = $('weapon-filter').value.toLowerCase();
    sel.querySelectorAll('option').forEach(o => {
      o.hidden = q && !o.textContent.toLowerCase().includes(q);
    });
    sel.querySelectorAll('optgroup').forEach(g => {
      const visible = [...g.querySelectorAll('option')].some(o => !o.hidden);
      g.hidden = !visible;
    });
  });

  // Yield slider with live preview
  let yieldPreviewRing = null;
  $('yield-slider').addEventListener('input', () => {
    const kt = NM.sliderToYield(+$('yield-slider').value);
    updateYieldUI(kt); syncYieldInput(kt);
    // Show preview circle at map center
    const c = map.getCenter();
    const previewR = 0.59 * Math.pow(kt, 1/3); // 5 psi radius
    if (yieldPreviewRing) map.removeLayer(yieldPreviewRing);
    yieldPreviewRing = L.circle([c.lat, c.lng], {
      radius: previewR * 1000, color: '#cba6f7', weight: 1.5, opacity: 0.4,
      fill: false, dashArray: '6 6', className: 'yield-preview-ring', interactive: false
    }).addTo(map);
  });
  $('yield-slider').addEventListener('change', () => {
    if (yieldPreviewRing) { map.removeLayer(yieldPreviewRing); yieldPreviewRing = null; }
  });

  // Direct yield input
  const syncFromInput = () => {
    let kt = +$('yield-input').value;
    if ($('yield-unit-select').value === 'mt') kt *= 1000;
    else if ($('yield-unit-select').value === 't') kt /= 1000;
    $('yield-slider').value = NM.yieldToSlider(kt);
    updateYieldUI(kt);
  };
  $('yield-input').addEventListener('change', syncFromInput);
  $('yield-unit-select').addEventListener('change', syncFromInput);

  updateYieldUI(NM.sliderToYield(+$('yield-slider').value));
  syncYieldInput(NM.sliderToYield(+$('yield-slider').value));

  // Burst buttons
  NM.queryUiAll('.burst-btn').forEach(b => b.addEventListener('click', () => {
    NM.queryUiAll('.burst-btn').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    $('height-row').style.display = b.dataset.burst === 'custom' ? '' : 'none';
    $('wind-wrap').style.display = b.dataset.burst === 'surface' ? '' : 'none';
    $('hemp-info').style.display = b.dataset.burst === 'hemp' ? '' : 'none';
  }));

  // Detonate / Undo / Clear / Share
  $('detonate-btn').addEventListener('click', () => { const c = map.getCenter(); onMapClick(c.lat, c.lng); });
  $('undo-btn').addEventListener('click', () => { if (currentDets.length) removeDet(currentDets.length - 1); });
  $('clear-btn').addEventListener('click', clearAll);
  $('share-btn').addEventListener('click', showShareLink);
  $('share-copy').addEventListener('click', copyShareLink);
  $('share-text').addEventListener('click', () => {
    const text = getShareText();
    if (text) { navigator.clipboard?.writeText(text); $('share-text').textContent = 'Copied!'; setTimeout(() => $('share-text').textContent = 'Copy Summary', 2000); }
  });
  $('share-native').addEventListener('click', () => {
    const text = getShareText();
    if (text && navigator.share) navigator.share({title: 'NukeMap Simulation', text, url: location.href}).catch(() => {});
  });

  // Multi-detonation toggle
  $('multi-check').addEventListener('change', () => { multiMode = $('multi-check').checked; });

  // Sound toggle
  $('sound-check').addEventListener('change', () => { NM.Sound.enabled = $('sound-check').checked; });

  // Cloud toggle
  $('cloud-toggle').addEventListener('change', () => {
    if ($('cloud-toggle').checked && currentDets.length) NM.Mushroom3D.show(currentDets[currentDets.length - 1]);
    else NM.Mushroom3D.hide();
  });

  // Heatmap toggle
  $('heatmap-check').addEventListener('change', () => {
    const on = NM.Heatmap.toggle(map);
    $('heatmap-label').textContent = on ? 'Population heatmap ON' : 'Population heatmap';
  });

  // Panel toggle
  $('panel-toggle').addEventListener('click', () => {
    const panel = $('panel');
    panel.classList.toggle('collapsed');
    const expanded = !panel.classList.contains('collapsed');
    $('panel-toggle').setAttribute('aria-expanded', expanded ? 'true' : 'false');
    $('panel-toggle').setAttribute('aria-label', expanded ? 'Collapse control panel' : 'Expand control panel');
    $('panel-toggle').setAttribute('title', expanded ? 'Collapse control panel' : 'Expand control panel');
    document.getElementById('nukemap-stage')?.classList.toggle('panel-collapsed', panel.classList.contains('collapsed'));
    NM.scheduleLayoutRefresh?.();
  });

  // Coords click-to-copy
  $('coords').addEventListener('click', () => {
    const t = $('coords').textContent;
    if (t && t !== '--') { navigator.clipboard?.writeText(t); $('coords').classList.add('copied'); setTimeout(() => $('coords').classList.remove('copied'), 1200); }
  });

  // Fullscreen
  if ($('fullscreen-btn')) $('fullscreen-btn').addEventListener('click', toggleFullscreen);

  // MIRV controls
  initMIRV();

  // Compare
  initCompare();

  // Wind compass
  initWindCompass();

  // Quick targets, presets, historical
  initQuickTargets();
  initPresets();
  initHistorical();
  initSearch();

  // ---- EXTRAS ----
  NM.DistanceIndicator.init();
  NM.LayerSwitcher.init(map);
  NM.switchToPreferredMapLayer();

  // Layer switcher buttons (panel)
  NM.queryUiAll('#layer-switcher .layer-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      NM.LayerSwitcher.switchTo(btn.dataset.layer);
    });
  });

  // Floating map switcher
  $('ms-toggle').addEventListener('click', e => {
    e.stopPropagation();
    const isOpen = $('ms-panel').classList.contains('open');
    $('ms-toggle').classList.toggle('open', !isOpen);
    $('ms-panel').classList.toggle('open', !isOpen);
  });
  $('ms-panel').addEventListener('click', e => e.stopPropagation());
  NM.queryUiAll('.ms-btn').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      NM.LayerSwitcher.switchTo(btn.dataset.layer);
      $('ms-toggle').classList.remove('open');
      $('ms-panel').classList.remove('open');
    });
  });
  document.addEventListener('click', () => {
    $('ms-toggle').classList.remove('open');
    $('ms-panel').classList.remove('open');
  });

  // Ring labels toggle
  $('ringlabels-check').addEventListener('change', () => {
    if ($('ringlabels-check').checked && currentDets.length) NM.RingLabels.draw(map, currentDets[currentDets.length - 1]);
    else NM.RingLabels.clear(map);
  });

  // Distance reference rings toggle
  $('distrings-check').addEventListener('change', () => {
    if ($('distrings-check').checked && currentDets.length) {
      const det = currentDets[currentDets.length - 1];
      const maxR = Math.max(det.effects.psi1, det.effects.thermal1, det.effects.emp);
      NM.DistanceRings.draw(map, det.lat, det.lng, maxR);
    } else NM.DistanceRings.clear(map);
  });

  // Distance from GZ toggle
  $('distfromgz-check').addEventListener('change', () => {
    if ($('distfromgz-check').checked && currentDets.length) {
      const det = currentDets[currentDets.length - 1];
      NM.DistanceIndicator.start(map, det.lat, det.lng);
    } else NM.DistanceIndicator.stop(map);
  });

  // Thermal flash gradient toggle
  $('thermal-check').addEventListener('change', () => {
    if ($('thermal-check').checked && currentDets.length) {
      const det = currentDets[currentDets.length - 1];
      NM.ThermalOverlay.draw(map, det.lat, det.lng, det.effects);
    } else NM.ThermalOverlay.clear(map);
  });

  // Fallout particle animation toggle
  $('falloutanim-check').addEventListener('change', () => {
    if ($('falloutanim-check').checked && currentDets.length) {
      const det = currentDets[currentDets.length - 1];
      if (det.effects.fallout) NM.FalloutParticles.start(map, det.lat, det.lng, det.effects.fallout, windAngle);
    } else NM.FalloutParticles.stop(map);
  });

  // Screenshot mode
  $('screenshot-check').addEventListener('change', () => NM.Screenshot.toggle());
  $('screenshot-hint').addEventListener('click', () => { $('screenshot-check').checked = false; NM.Screenshot.toggle(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && NM.Screenshot.active) { $('screenshot-check').checked = false; NM.Screenshot.toggle(); } });

  // Radiation decay calculator
  $('raddecay-calc').addEventListener('click', () => {
    if (!currentDets.length) return;
    const det = currentDets[currentDets.length - 1];
    const dist = +$('raddecay-dist').value || 10;
    $('raddecay-result').innerHTML = NM.RadDecay.generateHTML(det.yieldKt, det.fission, dist);
  });

  // ---- ADVANCED FEATURES ----

  // Experience mode toggle
  $('experience-check').addEventListener('change', () => {
    const on = NM.Experience.toggle(map);
    if (!on) map.getContainer().classList.add('crosshair');
  });

  // Measurement tool
  $('measure-toggle').addEventListener('click', () => {
    const on = NM.Measure.toggle(map);
    $('measure-toggle').textContent = on ? 'Disable Ruler' : 'Enable Ruler';
    if (on) map.getContainer().style.cursor = 'crosshair';
    else { map.getContainer().style.cursor = ''; map.getContainer().classList.add('crosshair'); }
  });
  $('measure-clear').addEventListener('click', () => NM.Measure.clear(map));

  // Attack scenarios
  const scenList = $('scenario-list');
  NM.Scenarios.forEach(sc => {
    const div = document.createElement('div');
    div.className = 'scenario-chip';
    div.innerHTML = `<div class="sc-name">${NM.esc(sc.name)}</div><div class="sc-desc">${NM.esc(sc.desc)} (${sc.dets.length} warheads)</div>`;
    div.addEventListener('click', () => {
      clearAll();
      multiMode = true; $('multi-check').checked = true;
      // Zoom to first target
      map.flyTo([sc.dets[0].lat, sc.dets[0].lng], sc.dets.length > 2 ? 6 : 9, {duration: 1});
      setTimeout(() => {
        sc.dets.forEach((d, i) => {
          setTimeout(() => {
            setYield(d.yield_kt);
              NM.queryUiAll('.burst-btn').forEach(b => b.classList.toggle('active', b.dataset.burst === d.burst));
            $('wind-wrap').style.display = d.burst === 'surface' ? '' : 'none';
            triggerDetonation(d.lat, d.lng);
          }, i * 600);
        });
      }, 1200);
    });
    scenList.appendChild(div);
  });

  // Missile flight time
  const launchSites = {
    us: {lat: 41.145, lng: -104.862, name: 'F.E. Warren AFB'},
    ru: {lat: 62.5, lng: 40.3, name: 'Plesetsk Cosmodrome'},
    cn: {lat: 28.2, lng: 102.0, name: 'Xichang (est.)'},
  };
  ['us', 'ru', 'cn'].forEach(key => {
    $('flight-' + key).addEventListener('click', () => {
      if (!currentDets.length) { $('flight-result').innerHTML = '<div style="color:var(--overlay0);font-size:11px">Detonate first to set a target</div>'; return; }
      const det = currentDets[currentDets.length - 1];
      const site = launchSites[key];
      const type = $('missile-type').value;
      const result = NM.MissileFlight.calculate(site.lat, site.lng, det.lat, det.lng, type);
      $('flight-result').innerHTML = `<div style="font-size:10px;color:var(--overlay0);margin-bottom:4px">From ${site.name}</div>` + NM.MissileFlight.generateHTML(result);
    });
  });

  // Draggable GZ toggle
  $('draggable-check').addEventListener('change', () => {
    if ($('draggable-check').checked && currentDets.length) {
      const det = currentDets[currentDets.length - 1];
      NM.DraggableGZ.enable(map, det, (newLat, newLng) => {
        removeDet(currentDets.length - 1);
        triggerDetonation(newLat, newLng);
      });
    } else NM.DraggableGZ.disable(map);
  });

  // Export PNG + KML + JSON + Report
  $('export-png').addEventListener('click', () => NM.ExportPNG.capture());
  $('export-kml').addEventListener('click', () => { if (currentDets.length) NM.KMLExport.download(currentDets); });
  $('export-json').addEventListener('click', () => { if (currentDets.length) exportJSON(); });
  $('export-report').addEventListener('click', () => { if (currentDets.length) exportReport(); });

  // GPS check
  $('gps-check').addEventListener('click', () => NM.GPSSafe.check(map));

  // Geiger counter
  $('geiger-check').addEventListener('change', () => {
    if ($('geiger-check').checked) NM.Geiger.start(map);
    else NM.Geiger.stop(map);
  });

  // Shockwave (on by default, handled in triggerDetonation)

  // Fallout contours
  $('contours-check').addEventListener('change', () => {
    if ($('contours-check').checked && NM._lastDet?.effects.fallout) {
      NM.FalloutContours.draw(map, NM._lastDet.lat, NM._lastDet.lng, NM._lastDet.effects.fallout, windAngle);
    } else NM.FalloutContours.clear(map);
  });

  // Radiation overlay
  $('radoverlay-check').addEventListener('change', () => {
    if ($('radoverlay-check').checked && currentDets.length) {
      const det = currentDets[currentDets.length - 1];
      NM.RadiationOverlay.draw(map, det.lat, det.lng, det.effects);
    } else NM.RadiationOverlay.clear(map);
  });

  // Damage heatmap
  $('dmgheatmap-check').addEventListener('change', () => {
    if ($('dmgheatmap-check').checked && currentDets.length) NM.DamageHeatmap.draw(map, currentDets);
    else NM.DamageHeatmap.clear(map);
  });

  // Test timeline
  $('test-timeline-btn').addEventListener('click', () => NM.TestTimeline.play(map));
  $('test-timeline-stop').addEventListener('click', () => NM.TestTimeline.stop(map));

  // Blast wave arrival indicator
  $('blastwaveinfo-check').addEventListener('change', () => {
    if ($('blastwaveinfo-check').checked && currentDets.length) NM.BlastArrival.start(map);
    else NM.BlastArrival.stop(map);
  });

  // Fallout time-lapse
  $('ft-slider').addEventListener('input', () => {
    const hr = +$('ft-slider').value;
    $('ft-label').textContent = hr < 24 ? hr + ' hr' : (hr / 24).toFixed(1) + ' d';
    $('ft-info').textContent = `Fallout extent at ${hr} hour${hr > 1 ? 's' : ''} after detonation`;
    if (NM._lastDet?.effects.fallout) {
      NM.FalloutTimelapse.draw(map, NM._lastDet.lat, NM._lastDet.lng, NM._lastDet.effects.fallout, windAngle, hr);
    }
  });
  $('ft-play').addEventListener('click', () => {
    if (!NM._lastDet?.effects.fallout) return;
    NM.FalloutTimelapse.playAnimation(map, NM._lastDet.lat, NM._lastDet.lng, NM._lastDet.effects.fallout, windAngle, (hr) => {
      $('ft-slider').value = Math.min(48, Math.round(hr));
      $('ft-label').textContent = hr < 24 ? Math.round(hr) + ' hr' : (hr / 24).toFixed(1) + ' d';
      $('ft-info').textContent = `Fallout extent at ${Math.round(hr)} hours after detonation`;
    });
  });

  // Night mode toggle
  $('night-check').addEventListener('change', () => {
    NM._nightMode = $('night-check').checked;
    $('night-label').textContent = NM._nightMode ? 'Night mode ON (flash blindness 20x)' : 'Night mode (flash blindness)';
    if (currentDets.length) { updateLegend(currentDets[currentDets.length - 1]); }
  });

  // Dose calculator
  $('dose-calc').addEventListener('click', () => {
    if (!currentDets.length) return;
    const det = currentDets[currentDets.length - 1];
    if (!det.effects.isSurface) { ($('nuke-dose-result') || $('dose-result')).innerHTML = '<div style="color:var(--overlay0);font-size:11px">Dose calculator requires a surface burst (fallout)</div>'; return; }
    const dist = +$('dose-dist').value || 5;
    const arrive = +$('dose-arrive').value || 1;
    const stay = +$('dose-stay').value || 4;
    ($('nuke-dose-result') || $('dose-result')).innerHTML = NM.DoseCalc.generateHTML(det.yieldKt, det.fission, dist, arrive, stay);
  });

  // Test database
  $('testdb-check').addEventListener('change', () => NM.TestDB.toggle(map));

  // WW3 Simulation
  const ww3Sel = $('ww3-scenario');
  NM.WW3_SCENARIOS.forEach(s => {
    const o = document.createElement('option'); o.value = s.id;
    o.textContent = s.name + ' (' + NM.WW3.countWarheads(s.id) + ' warheads)';
    ww3Sel.appendChild(o);
  });
  ww3Sel.addEventListener('change', () => {
    const s = NM.WW3_SCENARIOS.find(sc => sc.id === ww3Sel.value);
    $('ww3-scenario-desc').textContent = s ? s.desc : '';
  });
  $('ww3-launch').addEventListener('click', () => {
    if (!ww3Sel.value) return;
    clearAll();
    NM.WW3.start(map, ww3Sel.value);
    $('ww3-pause').style.display = '';
    $('ww3-pause').textContent = 'Pause';
  });
  $('ww3-stop').addEventListener('click', () => { NM.WW3.stop(map); $('ww3-pause').style.display = 'none'; });
  $('ww3-pause').addEventListener('click', () => {
    if (!NM.WW3.active) return;
    NM.WW3.paused = !NM.WW3.paused;
    $('ww3-pause').textContent = NM.WW3.paused ? 'Resume' : 'Pause';
  });

  // Collapsible sections in Effects/Encyclopedia tabs
  const alwaysOpen = new Set(['legend-section','cloud-section','timeline-section','shelter-section']);
  document.querySelectorAll('#tab-effects .section, #tab-encyclopedia .section').forEach(sec => {
    const title = sec.querySelector('.section-title');
    if (!title) return;
    title.classList.add('collapsible');
    title.addEventListener('click', () => {
      title.classList.toggle('collapsed');
      sec.classList.toggle('sec-collapsed');
    });
    // Auto-collapse secondary sections
    if (!alwaysOpen.has(sec.id)) {
      title.classList.add('collapsed');
      sec.classList.add('sec-collapsed');
    }
  });

  // WW3 quick-launch button
  $('ww3-quick-btn').addEventListener('click', () => {
    switchTab('tools');
    // Scroll WW3 section into view
    const ww3Sec = $('ww3-scenario')?.closest('.section');
    if (ww3Sec) ww3Sec.scrollIntoView({behavior: 'smooth', block: 'start'});
    // If panel is collapsed, open it
    $('panel').classList.remove('collapsed');
  });

  // Quick weapon bar
  NM.queryUiAll('.qw-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const kt = +chip.dataset.kt;
      setYield(kt);
      const i = NM.WEAPONS.findIndex(w => Math.abs(w.yield_kt - kt) < 0.01);
      if (i >= 0) $('weapon-select').value = i;
      NM.queryUiAll('.qw-chip').forEach(c => c.classList.remove('qw-active'));
      chip.classList.add('qw-active');
    });
  });

  // Save/Load scenarios
  $('save-btn').addEventListener('click', () => {
    if (!currentDets.length) return;
    const name = $('save-name').value.trim() || `Scenario ${new Date().toLocaleDateString()}`;
    const saves = JSON.parse(localStorage.getItem('nukemap-saves') || '[]');
    saves.push({
      name, date: Date.now(),
      dets: currentDets.map(d => ({lat:d.lat,lng:d.lng,yieldKt:d.yieldKt,burstType:d.burstType,weapon:d.weapon}))
    });
    localStorage.setItem('nukemap-saves', JSON.stringify(saves));
    $('save-name').value = '';
    renderSavedList();
  });
  renderSavedList();
  initEncyclopedia();

  // Rotating facts banner
  $('fact-banner')?.addEventListener('click', () => {
    $('fact-banner')?.classList.remove('show');
    showFact();
  });
  document.addEventListener('visibilitychange', () => {
    NM.syncAmbientUi({ immediate: document.visibilityState === 'visible' });
  });
  const tabRoot = document.getElementById('tab-nukemap');
  if (tabRoot && typeof MutationObserver === 'function' && !nukemapTabObserver) {
    nukemapTabObserver = new MutationObserver(() => {
      NM.syncAmbientUi({ immediate: tabRoot.classList.contains('active') });
    });
    nukemapTabObserver.observe(tabRoot, { attributes: true, attributeFilter: ['class'] });
  }
  NM.syncAmbientUi({ immediate: true });
}

function switchTab(id) {
  const tabButtons = getTabButtons();
  const tabPanes = getTabPanes();
  const paneId = tabPanes.some((pane) => pane.classList.contains('nk-tab-pane')) ? 'nk-pane-' + id : 'tab-' + id;
  const hasTargetPane = tabPanes.some((pane) => pane.id === paneId);

  if (!hasTargetPane) return;

  tabButtons.forEach((tabButton) => {
    const tabId = tabButton.dataset.nktab || tabButton.dataset.tab;
    tabButton.classList.toggle('active', tabId === id);
  });
  tabPanes.forEach((pane) => pane.classList.toggle('active', pane.id === paneId));
}

// ---- MIRV ----
function initMIRV() {
  const grid = $('mirv-grid');
  NM.MIRV_PRESETS.forEach((p, i) => {
    const chip = document.createElement('div');
    chip.className = 'preset-chip';
    chip.innerHTML = `${NM.esc(p.name)}<span class="chip-yield">${p.warheads}x ${NM.fmtYield(p.yield_kt)}</span>`;
    chip.addEventListener('click', () => {
      document.querySelectorAll('#mirv-grid .preset-chip').forEach(c => c.classList.remove('mirv-active'));
      if (currentMirvPreset === p) {
        mirvMode = false; currentMirvPreset = null;
        $('mirv-status').textContent = 'Select a MIRV preset, then click the map';
        NM.MIRV.clearPreview(map);
      } else {
        mirvMode = true; currentMirvPreset = p;
        chip.classList.add('mirv-active');
        $('mirv-status').textContent = `${p.name} armed. Click map to deploy ${p.warheads} warheads.`;
        multiMode = true; $('multi-check').checked = true;
        setYield(p.yield_kt);
      }
    });
    grid.appendChild(chip);
  });
}

// ---- COMPARE ----
function initCompare() {
  const selA = $('compare-a'), selB = $('compare-b');
  NM.WEAPONS.forEach((w, i) => {
    if (!w.country) return;
    const oA = document.createElement('option'); oA.value = i; oA.textContent = w.name + ' (' + NM.fmtYield(w.yield_kt) + ')';
    const oB = oA.cloneNode(true);
    selA.appendChild(oA); selB.appendChild(oB);
  });
  selA.value = 3; selB.value = 22; // Little Boy vs Tsar Bomba default

  const doCompare = () => {
    const wA = NM.WEAPONS[selA.value], wB = NM.WEAPONS[selB.value];
    if (!wA || !wB) return;
    $('compare-result').innerHTML = NM.Compare.generateTable(wA, wB);
    // Draw overlay at current map center
    const c = map.getCenter();
    NM.Compare.drawOverlay(map, c.lat, c.lng, wA, wB);
  };
  $('compare-go').addEventListener('click', doCompare);
  $('compare-clear').addEventListener('click', () => { NM.Compare.clearOverlay(map); $('compare-result').innerHTML = ''; });
}

// ---- WIND ----
function initWindCompass() {
  const comp = $('wind-compass'), arr = $('wind-arrow'), lbl = $('wind-dir-label');
  const dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
  function upd() { arr.style.transform = `rotate(${windAngle}deg)`; lbl.textContent = `From ${dirs[Math.round(windAngle / 45) % 8]} (${Math.round(windAngle)}\u00B0)`; }
  comp.addEventListener('click', e => { const r = comp.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2; windAngle = (Math.atan2(e.clientX - cx, -(e.clientY - cy)) * 180 / Math.PI + 360) % 360; upd(); });
  upd();
}

// ---- QUICK TARGETS / PRESETS / HISTORICAL ----
function initQuickTargets() {
  const c = $('target-pills');
  NM.QUICK_TARGETS.forEach(t => {
    const p = document.createElement('div'); p.className = 'target-pill'; p.textContent = t.name;
    p.addEventListener('click', () => map.flyTo([t.lat, t.lng], 12, {duration: 1}));
    c.appendChild(p);
  });
}

function initPresets() {
  const g = $('preset-grid');
  [{name: 'Davy Crockett', y: 0.02}, {name: 'Hiroshima', y: 15}, {name: 'W76-1', y: 100}, {name: 'W88', y: 455}, {name: 'B83', y: 1200}, {name: 'Castle Bravo', y: 15000}, {name: 'Tsar Bomba', y: 50000}, {name: '100 MT', y: 100000}].forEach(p => {
    const ch = document.createElement('div'); ch.className = 'preset-chip';
    ch.innerHTML = `${NM.esc(p.name)}<span class="chip-yield">${NM.fmtYield(p.y)}</span>`;
    ch.addEventListener('click', () => { setYield(p.y); const i = NM.WEAPONS.findIndex(w => Math.abs(w.yield_kt - p.y) < 0.01); if (i >= 0) $('weapon-select').value = i; });
    g.appendChild(ch);
  });
}

function initHistorical() {
  const g = $('historical-grid');
  NM.HISTORICAL.forEach(h => {
    const ch = document.createElement('div'); ch.className = 'preset-chip';
    ch.innerHTML = `${NM.esc(h.name)}<span class="chip-yield">${h.year} \u2014 ${NM.fmtYield(h.yield_kt)}</span>`;
    ch.addEventListener('click', () => {
      setYield(h.yield_kt);
      NM.queryUiAll('.burst-btn').forEach(b => b.classList.toggle('active', b.dataset.burst === h.burst));
      $('height-row').style.display = h.burst === 'custom' ? '' : 'none';
      $('wind-wrap').style.display = h.burst === 'surface' ? '' : 'none';
      if (h.height) $('burst-height').value = h.height;
      map.flyTo([h.lat, h.lng], h.yield_kt > 5000 ? 8 : 11, {duration: 1.2});
      setTimeout(() => triggerDetonation(h.lat, h.lng), 1300);
    });
    g.appendChild(ch);
  });
}

function initSearch() {
  const inp = $('search'), res = $('nukemap-search-results'); let si = -1;
  inp.addEventListener('input', () => {
    NM.ensureZipcodesLoaded();
    const items = NM.searchLocations(inp.value); si = -1;
    if (!items.length) { res.classList.remove('active'); return; }
    res.innerHTML = items.map((it, i) => `<div class="sr-item" data-idx="${i}"><div><div class="sr-name">${it.isTarget ? '<span style="color:var(--red);font-size:8px;margin-right:3px">&#9733;</span>' : ''}${NM.esc(it.name)}</div><div class="sr-detail">${NM.esc(it.detail)}</div></div>${it.pop ? `<div class="sr-pop">${NM.fmtNum(it.pop)}</div>` : ''}</div>`).join('');
    res.classList.add('active');
    res.querySelectorAll('.sr-item').forEach(el => el.addEventListener('click', () => { const it = items[+el.dataset.idx]; selectResult(it); }));
  });
  inp.addEventListener('keydown', e => { const items = res.querySelectorAll('.sr-item'); if (!items.length) return; if (e.key === 'ArrowDown') { e.preventDefault(); si = Math.min(si + 1, items.length - 1); items.forEach((el, i) => el.classList.toggle('selected', i === si)); } else if (e.key === 'ArrowUp') { e.preventDefault(); si = Math.max(si - 1, 0); items.forEach((el, i) => el.classList.toggle('selected', i === si)); } else if (e.key === 'Enter') { e.preventDefault(); (si >= 0 ? items[si] : items[0])?.click(); } else if (e.key === 'Escape') { res.classList.remove('active'); inp.blur(); } });
  inp.addEventListener('blur', () => setTimeout(() => res.classList.remove('active'), 200));
  inp.addEventListener('focus', () => {
    NM.ensureZipcodesLoaded();
    if (inp.value.trim()) inp.dispatchEvent(new Event('input'));
  });
}

function selectResult(it) {
  $('search').value = it.name + (it.detail ? ', ' + it.detail : '');
  $('nukemap-search-results').classList.remove('active');
  map.flyTo([it.lat, it.lng], it.pop > 1e6 ? 11 : it.pop > 1e5 ? 12 : 10, {duration: 1});
}

// ---- UPDATE UI PANELS ----
function updateDetsList() {
  const list = $('dets-list'); list.innerHTML = '';
  currentDets.forEach((d, i) => {
    const nc = NM.findNearestCity(d.lat, d.lng);
    const nm = nc && nc.dist < 50 ? nc.name : `${d.lat.toFixed(2)}, ${d.lng.toFixed(2)}`;
    const el = document.createElement('div'); el.className = 'det-item';
    const wShort = d.weapon ? d.weapon.split('(')[0].trim() : '';
    el.innerHTML = `<span class="det-idx">${i + 1}</span><div class="det-info"><span class="det-name">${NM.esc(nm)}</span><span class="det-weapon">${NM.esc(wShort)}</span></div>${d.isHEMP ? '<span class="det-badge">HEMP</span>' : ''}<span class="det-yield">${NM.fmtYield(d.yieldKt)}</span><button class="det-remove" type="button" data-i="${i}" aria-label="Remove detonation ${i + 1}">&times;</button>`;
    el.querySelector('.det-remove').addEventListener('click', e => { e.stopPropagation(); removeDet(i); });
    el.addEventListener('click', e => { if (!e.target.classList.contains('det-remove')) map.flyTo([d.lat, d.lng], map.getZoom(), {duration: 0.6}); });
    list.appendChild(el);
  });
}

function updateLegend(det) {
  const c = $('legend-items'); c.innerHTML = '';
  const e = det.effects;
  const flashR = NM._nightMode ? e.flashBlindNight : e.flashBlindDay;
  const items = [
    {id: 'fireball', r: e.fireball, color: '#f5e0dc'}, {id: 'radiation', r: e.radiation, color: '#a6e3a1'},
    {id: 'psi200', r: e.psi200, color: '#89dceb'}, {id: 'psi20', r: e.psi20, color: '#89b4fa'},
    {id: 'firestorm', r: e.firestormR, color: '#e64553'},
    {id: 'psi5', r: e.psi5, color: '#cba6f7'}, {id: 'thermal3', r: e.thermal3, color: '#fab387'},
    {id: 'psi1', r: e.psi1, color: '#f9e2af'}, {id: 'thermal1', r: e.thermal1, color: '#f5c2e7'},
    {id: 'emp', r: e.emp, color: '#94e2d5'},
    {id: 'flashblind', r: flashR, color: '#b4befe'},
  ];
  if (e.craterR > 0) items.unshift({id: 'crater', r: e.craterR, color: '#585b70'});

  items.forEach(it => {
    if (it.r < 0.0005) return;
    const def = NM.EFFECTS_DEF.find(d => d.id === it.id); if (!def) return;
    const div = document.createElement('div'); div.className = 'legend-item';
    const popEst = Math.round(Math.PI * it.r * it.r * (det.casualties.density || 40));
    div.innerHTML = `<div class="legend-dot" style="background:${it.color}"></div><div class="legend-label">${def.label}<span class="legend-desc">${def.desc.split('.')[0]}</span><span class="legend-pop">~${NM.fmtNum(popEst)} people in zone</span></div><div class="legend-value">${NM.fmtR(it.r)}<span class="legend-area">${NM.fmtArea(it.r)}</span></div><button class="legend-eye on" type="button" data-eid="${it.id}" aria-label="Hide ${def.label} ring" aria-pressed="true">&#10003;</button>`;
    div.querySelector('.legend-eye').addEventListener('click', ev => {
      const btn = ev.currentTarget; btn.classList.toggle('on');
      div.classList.toggle('dimmed', !btn.classList.contains('on'));
      toggleEffect(it.id, btn.classList.contains('on'));
      btn.setAttribute('aria-pressed', btn.classList.contains('on') ? 'true' : 'false');
      btn.setAttribute('aria-label', `${btn.classList.contains('on') ? 'Hide' : 'Show'} ${def.label} ring`);
      btn.innerHTML = btn.classList.contains('on') ? '&#10003;' : '&#9675;';
    });
    c.appendChild(div);
  });
}

function updateCloud(det) {
  $('cloud-section').style.display = '';
  $('cloud-panel').innerHTML = [
    ['Cloud top altitude', NM.fmtDist(det.effects.cloudTopH)],
    ['Cloud cap radius', NM.fmtDist(det.effects.cloudTopR)],
    ['Stem radius', NM.fmtDist(det.effects.stemR)],
    ['Burst height', det.effects.isSurface ? 'Surface (0 m)' : Math.round(det.effects.burstHeight) + ' m'],
    ['Fireball max radius', NM.fmtDist(det.effects.fireball)],
  ].map(([l, v]) => `<div class="cloud-row"><span class="cl">${l}</span><span class="cv">${v}</span></div>`).join('');
}

function updateTimeline(det) {
  $('timeline-section').style.display = '';
  const items = NM.calcTimeline(det.yieldKt, det.effects);
  $('timeline').innerHTML = items.map(it => `<div class="tl-item"><span class="tl-time">${it.time}</span><span class="tl-desc">${it.desc}</span></div>`).join('');
}

function updateCrater(det) {
  const e = det.effects;
  if (e.craterR <= 0) { $('crater-section').style.display = 'none'; return; }
  $('crater-section').style.display = '';
  const stats = [
    ['Crater radius', NM.fmtDist(e.craterR)], ['Crater depth', NM.fmtDist(e.craterDepth)],
    ['Lip height', '~' + NM.fmtR(e.craterDepth * 0.5)], ['Ejecta radius', '~' + NM.fmtR(e.craterR * 2)],
  ].map(([l, v]) => `<div class="cloud-row"><span class="cl">${l}</span><span class="cv">${v}</span></div>`).join('');

  // SVG crater cross-section
  if (e.craterR < 0.001 || e.craterDepth < 0.001) { $('crater-panel').innerHTML = stats; return; }
  const W = 280, H = 100;
  const rPx = 120, dPx = Math.max(10, 50);
  const lipH = dPx * 0.35;
  const ejectaR = rPx * 1.6;
  const svg = `<svg viewBox="0 0 ${W} ${H}" class="crater-svg">
    <rect x="0" y="0" width="${W}" height="${H}" fill="var(--mantle)" rx="6"/>
    <line x1="10" y1="${H*0.55}" x2="${W-10}" y2="${H*0.55}" stroke="var(--surface1)" stroke-width="0.5" stroke-dasharray="4 4"/>
    <text x="12" y="${H*0.55-3}" fill="var(--overlay0)" font-size="7">Ground level</text>
    <path d="M${W/2 - ejectaR} ${H*0.55} Q${W/2 - rPx} ${H*0.55 - lipH} ${W/2 - rPx*0.8} ${H*0.55 + 2} Q${W/2} ${H*0.55 + dPx} ${W/2 + rPx*0.8} ${H*0.55 + 2} Q${W/2 + rPx} ${H*0.55 - lipH} ${W/2 + ejectaR} ${H*0.55}" fill="none" stroke="var(--surface2)" stroke-width="1.5"/>
    <path d="M${W/2 - rPx*0.8} ${H*0.55 + 2} Q${W/2} ${H*0.55 + dPx} ${W/2 + rPx*0.8} ${H*0.55 + 2}" fill="rgba(88,91,112,0.3)" stroke="var(--overlay0)" stroke-width="1"/>
    <line x1="${W/2 - rPx*0.8}" y1="${H*0.55 + 5}" x2="${W/2 + rPx*0.8}" y2="${H*0.55 + 5}" stroke="var(--peach)" stroke-width="0.8" stroke-dasharray="3 2"/>
    <text x="${W/2}" y="${H*0.55 + 14}" fill="var(--peach)" font-size="7" text-anchor="middle">${NM.fmtR(e.craterR * 2)} diameter</text>
    <line x1="${W/2 + 2}" y1="${H*0.55}" x2="${W/2 + 2}" y2="${H*0.55 + dPx - 3}" stroke="var(--red)" stroke-width="0.8" stroke-dasharray="3 2"/>
    <text x="${W/2 + 8}" y="${H*0.55 + dPx/2 + 2}" fill="var(--red)" font-size="7">${NM.fmtR(e.craterDepth)}</text>
    <text x="${W/2 - ejectaR + 5}" y="${H*0.55 - lipH - 3}" fill="var(--overlay0)" font-size="6">Lip</text>
    <text x="${W/2 + rPx + 5}" y="${H*0.55 - 5}" fill="var(--overlay0)" font-size="6">Ejecta</text>
  </svg>`;

  $('crater-panel').innerHTML = stats + svg;
}

function updateShelter(det) {
  $('shelter-section').style.display = '';
  $('shelter-content').innerHTML = NM.Shelter.generateReport(det.effects);
}

function updateNearbyTargets(det) {
  const allTargets = [
    ...(NM.WW3_TARGETS_US || []).map(t => ({...t, side: 'US'})),
    ...(NM.WW3_TARGETS_RU || []).map(t => ({...t, side: 'Russia'})),
    ...(NM.WW3_TARGETS_NATO || []).map(t => ({...t, side: 'NATO'})),
  ];
  const nearby = allTargets.map(t => ({...t, dist: NM.haversine(det.lat, det.lng, t.lat, t.lng)}))
    .filter(t => t.dist < 200)
    .sort((a, b) => a.dist - b.dist)
    .slice(0, 12);

  if (!nearby.length) { $('nearby-section').style.display = 'none'; return; }
  $('nearby-section').style.display = '';

  const typeColors = {icbm:'#f38ba8',bomber:'#fab387',sub:'#89b4fa',c2:'#cba6f7',nuclear:'#a6e3a1',military:'#f9e2af',infra:'#94e2d5',city:'#f5c2e7'};
  const typeLabels = {icbm:'ICBM',bomber:'Bomber',sub:'Submarine',c2:'Command',nuclear:'Nuclear',military:'Military',infra:'Infrastructure',city:'City'};

  let html = '<div class="nearby-list">';
  for (const t of nearby) {
    const c = typeColors[t.type] || '#cdd6f4';
    const inBlast = t.dist <= det.effects.psi1;
    html += `<div class="nearby-item${inBlast ? ' nearby-hit' : ''}">
      <div class="nb-header"><span class="nb-type" style="color:${c}">${typeLabels[t.type] || t.type}</span><span class="nb-dist">${NM.fmtR(t.dist)}</span></div>
      <div class="nb-name">${NM.esc(t.name)}</div>
                ${t.cat ? `<div class="nb-cat">${NM.esc(t.cat.substring(0, 80))}${t.cat.length > 80 ? '…' : ''}</div>` : ''}
      ${inBlast ? '<div class="nb-status">WITHIN BLAST ZONE</div>' : ''}
    </div>`;
  }
  html += '</div>';
  $('nearby-content').innerHTML = html;
}

function updateStats() {
  let td = 0, ti = 0, ty = 0; currentDets.forEach(d => { td += d.casualties.deaths; ti += d.casualties.injuries; ty += d.yieldKt; });
  const hiro = ty / 15; // Hiroshima equivalents
  $('stat-deaths').textContent = NM.fmtNum(td);
  $('stat-injuries').textContent = NM.fmtNum(ti);
  $('stat-total').textContent = NM.fmtNum(td + ti);
  $('stat-yield').textContent = ty > 0 ? NM.fmtYield(ty) : '--';
  $('stat-note').textContent = currentDets.length > 1 ? `${currentDets.length} detonations | ${hiro >= 10 ? hiro.toFixed(0) : hiro.toFixed(1)}x Hiroshima` : currentDets.length === 1 ? (hiro >= 0.01 ? `${hiro >= 10 ? hiro.toFixed(0) : hiro.toFixed(1)}x Hiroshima equivalent` : 'Sub-tactical yield') : 'Detonate a weapon to see estimates';

  // Detonation counter badge
  const dc = $('det-counter');
  if (currentDets.length) {
    $('det-counter-num').textContent = currentDets.length;
    dc.querySelector('.dc-label').textContent = currentDets.length === 1 ? 'strike' : 'strikes';
    dc.style.display = '';
  } else dc.style.display = 'none';

  // Info bar
  const bar = $('info-bar');
  if (currentDets.length) {
    const hiroStr = hiro >= 10 ? hiro.toFixed(0) : hiro >= 0.1 ? hiro.toFixed(1) : hiro.toFixed(2);
    bar.innerHTML = `<div class="ib-stat"><div class="ib-val" style="color:var(--red)">${NM.fmtNum(td)}</div><div class="ib-lbl">Fatalities</div></div><div class="ib-div"></div><div class="ib-stat"><div class="ib-val" style="color:var(--peach)">${NM.fmtNum(ti)}</div><div class="ib-lbl">Injuries</div></div><div class="ib-div"></div><div class="ib-stat"><div class="ib-val" style="color:var(--mauve)">${hiroStr}x</div><div class="ib-lbl">Hiroshimas</div></div><div class="ib-div"></div><div class="ib-stat"><div class="ib-val" style="color:var(--yellow)">${currentDets.length}</div><div class="ib-lbl">${currentDets.length === 1 ? 'Detonation' : 'Detonations'}</div></div>`;
    bar.classList.add('active');
  } else bar.classList.remove('active');
}

function toggleEffect(eid, vis) { currentDets.forEach(d => d.layers.forEach(l => { if (l._effectId === eid) { vis ? l.addTo(map) : map.removeLayer(l); } })); }

function removeDet(i) {
  const d = currentDets[i]; if (d) d.layers.forEach(l => map.removeLayer(l));
  NM.Mushroom3D.removeAt(i);
  currentDets.splice(i, 1); updateDetsList(); updateStats();
  if (!currentDets.length) resetPanels();
  else { const last = currentDets[currentDets.length - 1]; updateLegend(last); updateCloud(last); updateTimeline(last); updateCrater(last); updateShelter(last); }
  updateURL();
}

function clearAll() {
  currentDets.forEach(d => d.layers.forEach(l => map.removeLayer(l))); currentDets = [];
  NM.Mushroom3D.hide();
  NM.Compare.clearOverlay(map);
  NM.MIRV.clearPreview(map);
  NM.Animation.cleanup();
  NM.RingLabels.clear(map);
  NM.DistanceRings.clear(map);
  NM.DistanceIndicator.stop(map);
  NM.ThermalOverlay.clear(map);
  NM.FalloutParticles.stop(map);
  NM.DraggableGZ.disable(map);
  NM.DeliveryArc.layer && map.removeLayer(NM.DeliveryArc.layer);
  NM.ShockwaveRing.clear(map);
  NM.FalloutContours.clear(map);
  NM.Geiger.stop(map);
  NM.WW3.stop(map);
  NM.FalloutTimelapse.clear(map);
  NM.BlastArrival.stop(map);
  NM.RadiationOverlay.clear(map);
  NM.DamageHeatmap.clear(map);
  NM.TestTimeline.stop(map);
  $('fallout-timelapse').style.display = 'none';
  NM._lastDet = null;
  updateDetsList(); updateStats(); resetPanels(); updateURL();
}

function resetPanels() {
  $('dets-section').style.display = 'none';
  $('cloud-section').style.display = 'none';
  $('timeline-section').style.display = 'none';
  $('crater-section').style.display = 'none';
  $('shelter-section').style.display = 'none';
  $('raddecay-section').style.display = 'none';
  $('psi-section').style.display = 'none';
  $('yieldchart-section').style.display = 'none';
  $('nw-section').style.display = 'none';
  $('altitude-section').style.display = 'none';
  $('zonecas-section').style.display = 'none';
  $('destruction-section').style.display = 'none';
  $('emp-section').style.display = 'none';
  $('survival-section').style.display = 'none';
  $('weaponinfo-section').style.display = 'none';
  $('seismic-section').style.display = 'none';
  $('conventional-section').style.display = 'none';
  $('bldgdmg-section').style.display = 'none';
  $('sizecompare-section').style.display = 'none';
  $('escape-section').style.display = 'none';
  $('nearby-section').style.display = 'none';
  $('ground-section').style.display = 'none';
  $('cloudcompare-section').style.display = 'none';
  $('guide-section').style.display = 'none';
  $('dosecalc-section').style.display = 'none';
  $('legend-items').innerHTML = '<div style="color:var(--overlay0);font-size:12px;padding:10px 0">Detonate a weapon to see effects</div>';
  $('info-bar').classList.remove('active');
}

// ---- URL STATE ----
function updateURL() {
  const url = new URL(window.location.href);
  if (!currentDets.length) {
    url.searchParams.delete('d');
    history.replaceState(null, '', `${url.pathname}${url.search}${url.hash}`);
    return;
  }
  const params = currentDets.map(d => `${d.lat.toFixed(4)},${d.lng.toFixed(4)},${d.yieldKt},${d.burstType[0]}`).join(';');
  url.searchParams.set('d', params);
  history.replaceState(null, '', `${url.pathname}${url.search}${url.hash}`);
}

function loadFromURL() {
  const p = new URLSearchParams(location.search), d = p.get('d');
  if (!d) return;
  multiMode = true; $('multi-check').checked = true;
  d.split(';').forEach(seg => {
    const [lat, lng, y, bt] = seg.split(',');
    if (lat && lng && y) {
      const burst = bt === 's' ? 'surface' : bt === 'c' ? 'custom' : 'airburst';
      setYield(+y);
      NM.queryUiAll('.burst-btn').forEach(b => b.classList.toggle('active', b.dataset.burst === burst));
      triggerDetonation(+lat, +lng);
    }
  });
}

function showShareLink() {
  $('share-section').style.display = ''; $('share-input').value = location.href; switchTab('results');
  // Show native share button if Web Share API available
  if (navigator.share) $('share-native').style.display = '';
}
function copyShareLink() { $('share-input').select(); navigator.clipboard?.writeText($('share-input').value); $('share-copy').textContent = 'Copied!'; setTimeout(() => $('share-copy').textContent = 'Copy Link', 2000); }
function getShareText() {
  if (!currentDets.length) return '';
  let td = 0, ti = 0, ty = 0;
  currentDets.forEach(d => { td += d.casualties.deaths; ti += d.casualties.injuries; ty += d.yieldKt; });
  const hiro = (ty / 15);
  const nc = NM.findNearestCity(currentDets[0].lat, currentDets[0].lng);
  const loc = nc && nc.dist < 50 ? nc.name : `${currentDets[0].lat.toFixed(2)}, ${currentDets[0].lng.toFixed(2)}`;
  let text = `NukeMap: ${NM.fmtYield(ty)} (${hiro >= 10 ? hiro.toFixed(0) : hiro.toFixed(1)}x Hiroshima)`;
  if (currentDets.length === 1) text += ` on ${loc}`;
  else text += ` across ${currentDets.length} targets`;
  text += ` | ${NM.fmtNum(td)} killed, ${NM.fmtNum(ti)} injured`;
  text += `\n${location.href}`;
  return text;
}

// ---- WEAPON ENCYCLOPEDIA ----
function initEncyclopedia() {
  const list = $('encyclopedia-list'); if (!list) return;
  const groups = {};
  const countryOrder = ['US','RU','CN','UK','FR','IN','PK','KP','IL'];
  const countryNames = {US:'United States',RU:'Russia',CN:'China',UK:'United Kingdom',FR:'France',IN:'India',PK:'Pakistan',KP:'North Korea',IL:'Israel'};
  NM.WEAPONS.forEach((w, i) => {
    if (!w.country) return;
    if (!groups[w.country]) groups[w.country] = [];
    groups[w.country].push({...w, idx: i});
  });

  let html = '';
  for (const code of countryOrder) {
    const ws = groups[code];
    if (!ws) continue;
    html += `<div class="enc-country"><div class="enc-country-name">${countryNames[code] || code} (${ws.length})</div>`;
    for (const w of ws) {
      html += `<div class="enc-weapon" data-idx="${w.idx}" data-yield="${w.yield_kt}">
        <span class="enc-w-name">${NM.esc(w.name)}</span>
        <span class="enc-w-year">${w.year || ''}</span>
        <span class="enc-w-yield">${NM.fmtYield(w.yield_kt)}</span>
      </div>`;
    }
    html += '</div>';
  }
  list.innerHTML = html;

  list.querySelectorAll('.enc-weapon').forEach(el => {
    el.addEventListener('click', () => {
      const idx = +el.dataset.idx;
      $('weapon-select').value = idx;
      setYield(NM.WEAPONS[idx].yield_kt);
      switchTab('weapon');
      list.querySelectorAll('.enc-weapon').forEach(e => e.classList.remove('enc-selected'));
      el.classList.add('enc-selected');
    });
  });
}

// ---- EXPORT JSON ----
function exportJSON() {
  const data = currentDets.map(d => {
    const nc = NM.findNearestCity(d.lat, d.lng);
    return {
      location: {lat: d.lat, lng: d.lng, nearestCity: nc && nc.dist < 50 ? nc.name : null},
      weapon: d.weapon, yieldKt: d.yieldKt, burstType: d.burstType,
      effects: {
        fireball_km: +d.effects.fireball.toFixed(3), psi20_km: +d.effects.psi20.toFixed(3),
        psi5_km: +d.effects.psi5.toFixed(3), psi1_km: +d.effects.psi1.toFixed(3),
        thermal3_km: +d.effects.thermal3.toFixed(3), thermal1_km: +d.effects.thermal1.toFixed(3),
        radiation_km: +d.effects.radiation.toFixed(3), emp_km: +d.effects.emp.toFixed(3),
        firestorm_km: +d.effects.firestormR.toFixed(3),
        cloudTop_km: +d.effects.cloudTopH.toFixed(2),
      },
      casualties: d.casualties, hiroshimaEquivalent: +(d.yieldKt / 15).toFixed(2)
    };
  });
  const blob = new Blob([JSON.stringify({version:'3.2.0', generated: new Date().toISOString(), detonations: data}, null, 2)], {type:'application/json'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'nukemap-data.json';
  document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(a.href);
}

// ---- SUMMARY REPORT ----
function exportReport() {
  let td = 0, ti = 0, ty = 0;
  currentDets.forEach(d => { td += d.casualties.deaths; ti += d.casualties.injuries; ty += d.yieldKt; });
  const hiro = ty / 15;

  let report = `NUKEMAP DETONATION REPORT\n`;
  report += `Generated: ${new Date().toLocaleString()}\n`;
  report += `${'='.repeat(50)}\n\n`;
  report += `SUMMARY\n`;
  report += `  Detonations: ${currentDets.length}\n`;
  report += `  Total Yield: ${NM.fmtYield(ty)} (${hiro.toFixed(1)}x Hiroshima)\n`;
  report += `  Est. Fatalities: ${NM.fmtNum(td)}\n`;
  report += `  Est. Injuries: ${NM.fmtNum(ti)}\n`;
  report += `  Total Affected: ${NM.fmtNum(td + ti)}\n\n`;

  currentDets.forEach((d, i) => {
    const nc = NM.findNearestCity(d.lat, d.lng);
    const loc = nc && nc.dist < 50 ? `${nc.name}, ${nc.state}` : `${d.lat.toFixed(4)}, ${d.lng.toFixed(4)}`;
    report += `DETONATION ${i + 1}: ${d.weapon}\n`;
    report += `${'-'.repeat(40)}\n`;
    report += `  Location: ${loc}\n`;
    report += `  Coordinates: ${d.lat.toFixed(4)}, ${d.lng.toFixed(4)}\n`;
    report += `  Yield: ${NM.fmtYield(d.yieldKt)} (${(d.yieldKt/15).toFixed(1)}x Hiroshima)\n`;
    report += `  Burst Type: ${d.burstType}\n`;
    report += `  Fatalities: ${NM.fmtNum(d.casualties.deaths)}\n`;
    report += `  Injuries: ${NM.fmtNum(d.casualties.injuries)}\n`;
    report += `  Effect Radii:\n`;
    report += `    Fireball: ${NM.fmtDist(d.effects.fireball)}\n`;
    report += `    20 psi: ${NM.fmtDist(d.effects.psi20)}\n`;
    report += `    5 psi: ${NM.fmtDist(d.effects.psi5)}\n`;
    report += `    1 psi: ${NM.fmtDist(d.effects.psi1)}\n`;
    report += `    3rd deg burns: ${NM.fmtDist(d.effects.thermal3)}\n`;
    report += `    Firestorm: ${NM.fmtDist(d.effects.firestormR)}\n`;
    report += `    EMP: ${NM.fmtDist(d.effects.emp)}\n`;
    report += `    Cloud top: ${NM.fmtDist(d.effects.cloudTopH)}\n`;
    if (d.effects.fallout) {
      report += `    Fallout (heavy): ${NM.fmtDist(d.effects.fallout.heavy.length)} downwind\n`;
      report += `    Fallout (light): ${NM.fmtDist(d.effects.fallout.light.length)} downwind\n`;
    }
    report += `\n`;
  });

  report += `\nPhysics: Glasstone & Dolan, "The Effects of Nuclear Weapons"\n`;
  report += `Generated by NukeMap v3.3.0 - https://sysadmindoc.github.io/NukeMap/\n`;

  const blob = new Blob([report], {type:'text/plain'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'nukemap-report.txt';
  document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(a.href);
}

// ---- SAVE/LOAD SCENARIOS ----
function renderSavedList() {
  const list = $('saved-list'); if (!list) return;
  const saves = JSON.parse(localStorage.getItem('nukemap-saves') || '[]');
  if (!saves.length) { list.innerHTML = '<div style="color:var(--overlay0);font-size:10px">No saved scenarios</div>'; return; }
  list.innerHTML = '';
  saves.forEach((s, i) => {
    const el = document.createElement('div'); el.className = 'saved-item';
    el.innerHTML = `<span class="si-name">${NM.esc(s.name)}</span><span class="si-meta">${s.dets.length} det${s.dets.length > 1 ? 's' : ''}</span><button class="si-del" type="button" data-i="${i}" aria-label="Delete scenario ${NM.esc(s.name)}">&times;</button>`;
    el.addEventListener('click', e => { if (!e.target.classList.contains('si-del')) loadScenario(s); });
    el.querySelector('.si-del').addEventListener('click', e => { e.stopPropagation(); deleteSave(i); });
    list.appendChild(el);
  });
}

function loadScenario(s) {
  clearAll();
  multiMode = true; $('multi-check').checked = true;
  if (s.dets.length) map.flyTo([s.dets[0].lat, s.dets[0].lng], s.dets.length > 2 ? 6 : 9, {duration: 1});
  setTimeout(() => {
    s.dets.forEach((d, i) => {
      setTimeout(() => {
        setYield(d.yieldKt);
        NM.queryUiAll('.burst-btn').forEach(b => b.classList.toggle('active', b.dataset.burst === d.burstType));
        $('wind-wrap').style.display = d.burstType === 'surface' ? '' : 'none';
        triggerDetonation(d.lat, d.lng);
      }, i * 400);
    });
  }, 1200);
}

function deleteSave(i) {
  const saves = JSON.parse(localStorage.getItem('nukemap-saves') || '[]');
  saves.splice(i, 1);
  localStorage.setItem('nukemap-saves', JSON.stringify(saves));
  renderSavedList();
}

// ---- DETONATION TOAST ----
function showDetToast(det) {
  const nc = NM.findNearestCity(det.lat, det.lng);
  const loc = nc && nc.dist < 50 ? nc.name : `${det.lat.toFixed(2)}, ${det.lng.toFixed(2)}`;
  const hiro = det.yieldKt / 15;
  const hiroStr = hiro >= 10 ? hiro.toFixed(0) + 'x Hiroshima' : hiro >= 1 ? hiro.toFixed(1) + 'x Hiroshima' : '';
  const el = document.createElement('div');
  el.className = 'det-toast';
  el.setAttribute('role', 'status');
  el.setAttribute('aria-live', 'polite');
  el.setAttribute('aria-atomic', 'true');
  el.innerHTML = `<span class="dt-yield">${NM.fmtYield(det.yieldKt)}</span> <span class="dt-loc">${NM.esc(loc)}</span>${hiroStr ? ` <span class="dt-hiro">${hiroStr}</span>` : ''}`;
  NM.getUiRoot().appendChild(el);
  requestAnimationFrame(() => el.classList.add('show'));
  setTimeout(() => { el.classList.remove('show'); setTimeout(() => el.remove(), 500); }, 3000);
}

// ---- FULLSCREEN ----
function toggleFullscreen() {
  const root = document.getElementById('nukemap-stage') || document.documentElement;
  if (!document.fullscreenElement) {
    root.requestFullscreen?.() || root.webkitRequestFullscreen?.();
  } else {
    document.exitFullscreen?.() || document.webkitExitFullscreen?.();
  }
  setTimeout(() => NM.scheduleLayoutRefresh?.(), 180);
}

// ---- INIT ----
function init() {
  NM.Sound.init();
  NM.Mushroom3D.init();
  initMap();
  initControls();
  if ('serviceWorker' in navigator && NM.isStandaloneRoute() && !window.pywebview) {
    navigator.serviceWorker.register('/nukemap/sw.js').catch(() => {});
  }

  // Welcome overlay
  const wo = $('welcome-overlay');
  const hasUrlDets = new URLSearchParams(location.search).get('d');
  const ensureAtlasReady = async () => {
    if (NM.hasOfflineAtlas()) return true;
    try {
      await NM.ensureOfflineAtlas();
      return NM.hasOfflineAtlas();
    } catch (_error) {
      return false;
    }
  };
  const dismissWelcome = () => {
    if (!wo || wo.classList.contains('hidden')) return;
    if ($('welcome-noshow')?.checked) localStorage.setItem('nukemap-welcomed', '1');
    wo.classList.add('hidden');
  };
  NM.refreshOfflineAtlasUi();
  if (wo && !localStorage.getItem('nukemap-welcomed') && !hasUrlDets) {
    wo.style.display = '';
    NM.ensureOfflineAtlas().catch(() => {});
    $('welcome-dismiss').addEventListener('click', async () => {
      if (!(await ensureAtlasReady())) {
        NM.refreshOfflineAtlasUi();
        return;
      }
      dismissWelcome();
      // Demo detonation on first visit
      if (!currentDets.length) {
        setTimeout(() => {
          map.flyTo([40.7128, -74.006], 11, {duration: 1.2});
          setTimeout(() => { setYield(455); triggerDetonation(40.7128, -74.006); }, 1400);
        }, 300);
      }
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') dismissWelcome();
    });
  } else {
    if (wo) wo.classList.add('hidden');
    if (!NM.hasOfflineAtlas()) {
      setTimeout(() => {
        NM.ensureOfflineAtlas().catch(() => {});
      }, hasUrlDets ? 180 : 60);
    }
  }
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
else init();

})();
