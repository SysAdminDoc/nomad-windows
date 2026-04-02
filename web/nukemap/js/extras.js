// NukeMap - Extra Features Module
// Ring labels, distance indicator, draggable GZ, layer switcher,
// distance rings, radiation decay, screenshot mode, custom psi,
// thermal gradient, fallout particles
window.NM = window.NM || {};

// ---- RING LABELS ON MAP ----
NM.RingLabels = {
  markers: [],

  draw(map, det) {
    this.clear(map);
    const e = det.effects;
    const labels = [
      {r: e.fireball, text: 'Fireball', color: '#f5e0dc'},
      {r: e.psi20, text: '20 psi', color: '#89b4fa'},
      {r: e.psi5, text: '5 psi', color: '#cba6f7'},
      {r: e.thermal3, text: '3rd\u00B0 Burns', color: '#fab387'},
      {r: e.psi1, text: '1 psi', color: '#f9e2af'},
      {r: e.thermal1, text: '1st\u00B0 Burns', color: '#f5c2e7'},
      {r: e.radiation, text: '500 rem', color: '#a6e3a1'},
    ].filter(l => l.r > 0.001);

    const R = 6371;
    labels.forEach(l => {
      // Place label at the north edge of the ring
      const labelLat = det.lat + (l.r / R) * (180 / Math.PI);
      const icon = L.divIcon({
        className: 'ring-label',
        html: `<div class="rl-tag" style="border-color:${l.color};color:${l.color}">${l.text}<span class="rl-dist">${NM.fmtR(l.r)}</span></div>`,
        iconSize: [0, 0], iconAnchor: [0, 12]
      });
      const m = L.marker([labelLat, det.lng], {icon, interactive: false}).addTo(map);
      this.markers.push(m);
    });
  },

  clear(map) {
    this.markers.forEach(m => map.removeLayer(m));
    this.markers = [];
  }
};

// ---- LIVE DISTANCE FROM GZ ----
NM.DistanceIndicator = {
  el: null,
  active: false,
  gzLat: 0, gzLng: 0,

  init() {
    this.el = document.getElementById('dist-indicator') || document.createElement('div');
    this.el.id = 'dist-indicator';
    this.el.className = 'dist-indicator';
    if (!this.el.isConnected) (NM.getUiRoot ? NM.getUiRoot() : document.body).appendChild(this.el);
  },

  start(map, lat, lng) {
    this.gzLat = lat; this.gzLng = lng; this.active = true;
    this._handler = (e) => {
      if (!this.active) return;
      const d = NM.haversine(this.gzLat, this.gzLng, e.latlng.lat, e.latlng.lng);
      this.el.textContent = `${NM.fmtDist(d)} from GZ`;
      this.el.style.display = 'block';
    };
    map.on('mousemove', this._handler);
  },

  stop(map) {
    this.active = false;
    if (this._handler) map.off('mousemove', this._handler);
    if (this.el) this.el.style.display = 'none';
  },

  update(lat, lng) {
    this.gzLat = lat; this.gzLng = lng;
  }
};

// ---- CONCENTRIC DISTANCE REFERENCE RINGS ----
NM.DistanceRings = {
  layers: [],

  draw(map, lat, lng, maxR) {
    this.clear(map);
    // Draw rings at nice intervals
    const intervals = maxR > 100 ? [25, 50, 100, 200, 500] :
                      maxR > 50 ? [10, 25, 50, 100] :
                      maxR > 10 ? [5, 10, 25, 50] :
                      maxR > 5 ? [1, 2, 5, 10] :
                      [0.5, 1, 2, 5];

    intervals.forEach(km => {
      if (km > maxR * 1.2) return;
      const c = L.circle([lat, lng], {
        radius: km * 1000, color: '#6c7086', weight: 0.8, opacity: 0.3,
        fill: false, dashArray: '3 6', interactive: false
      }).addTo(map);
      this.layers.push(c);

      // Label
      const R = 6371;
      const labelLat = lat + (km / R) * (180 / Math.PI);
      const icon = L.divIcon({
        className: 'dist-ring-label',
        html: `<span>${km >= 1 ? km + ' km' : (km * 1000) + ' m'}</span>`,
        iconSize: [0, 0], iconAnchor: [-4, 6]
      });
      const m = L.marker([labelLat, lng], {icon, interactive: false}).addTo(map);
      this.layers.push(m);
    });
  },

  clear(map) {
    this.layers.forEach(l => map.removeLayer(l));
    this.layers = [];
  }
};

// ---- MAP LAYER SWITCHER ----
NM.LayerSwitcher = {
  layers: {},
  current: 'dark',

  init(map) {
    this.layers = {
      offlineAtlas: NM.buildOfflineAtlasLayer?.(document.documentElement.getAttribute('data-theme') || 'nomad'),
      dark:       L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {attribution:'&copy; OSM &copy; CARTO',subdomains:'abcd',maxZoom:19}),
      darkClean:  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png', {attribution:'&copy; CARTO',subdomains:'abcd',maxZoom:19}),
      satellite:  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {attribution:'&copy; Esri',maxZoom:19}),
      satLabels:  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {attribution:'&copy; Esri',maxZoom:19}),
      terrain:    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', {attribution:'&copy; Esri',maxZoom:19}),
      osm:        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {attribution:'&copy; OSM',maxZoom:19}),
      voyager:    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {attribution:'&copy; CARTO',subdomains:'abcd',maxZoom:19}),
      positron:   L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {attribution:'&copy; CARTO',subdomains:'abcd',maxZoom:19}),
    };
    // Satellite + labels combo: overlay labels on imagery
    this._labelOverlay = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png', {subdomains:'abcd',maxZoom:19,pane:'shadowPane'});
    this.map = map;
  },
  refreshOfflineAtlasLayer() {
    if (!this.layers.offlineAtlas && typeof NM.buildOfflineAtlasLayer === 'function') {
      this.layers.offlineAtlas = NM.buildOfflineAtlasLayer(document.documentElement.getAttribute('data-theme') || 'nomad');
    }
    this.layers.offlineAtlas?.syncAtlas?.();
  },
  applyTheme(theme) {
    this.layers.offlineAtlas?.setTheme?.(theme);
  },

  switchTo(name) {
    if (!this.layers[name]) return;
    this.refreshOfflineAtlasLayer();
    this.applyTheme(document.documentElement.getAttribute('data-theme') || 'nomad');
    // Remove ALL tile layers (including initial dark layer and any overlays)
    const toRemove = [];
    this.map.eachLayer(l => {
      if ((l._url !== undefined && l._tiles !== undefined) || typeof l.createTile === 'function') toRemove.push(l);
    });
    toRemove.forEach(l => this.map.removeLayer(l));
    // Add selected tile layer
    this.layers[name].addTo(this.map);
    // Add label overlay on satellite
    if (name === 'satLabels') this._labelOverlay.addTo(this.map);
    this.current = name;
    // Update active state in both switchers
    const uiButtons = NM.queryUiAll ? NM.queryUiAll('.ms-btn') : [...document.querySelectorAll('.ms-btn')];
    const layerButtons = NM.queryUiAll ? NM.queryUiAll('#layer-switcher .layer-btn') : [...document.querySelectorAll('#layer-switcher .layer-btn')];
    uiButtons.forEach(b => b.classList.toggle('active', b.dataset.layer === name));
    layerButtons.forEach(b => b.classList.toggle('active', b.dataset.layer === name));
  }
};

// ---- RADIATION DECAY CALCULATOR (7:10 Rule) ----
NM.RadDecay = {
  // 7:10 rule: for every 7x increase in time, radiation drops 10x
  // R(t) = R(1hr) * t^(-1.2)  where t is in hours
  calculate(yieldKt, fissionFrac, distanceKm, hours) {
    fissionFrac = (fissionFrac || 50) / 100;
    // Reference dose rate at 1 hour, 1 km from 1 kT surface burst: ~3000 R/hr
    const refRate = 3000 * yieldKt * fissionFrac;
    const distFactor = Math.pow(Math.max(distanceKm, 0.1), -2); // inverse square
    const rateAt1hr = refRate * distFactor;

    const results = [];
    const times = [1, 2, 6, 12, 24, 48, 72, 168, 336, 720]; // hours
    for (const t of times) {
      if (t > hours) break;
      const rate = rateAt1hr * Math.pow(t, -1.2);
      const cumDose = rateAt1hr * (Math.pow(t, -0.2) - 1) / (-0.2); // integral approximation
      results.push({
        hours: t,
        label: t < 24 ? t + 'h' : (t / 24).toFixed(0) + 'd',
        rate: rate,
        cumDose: Math.abs(cumDose),
        lethal: rate > 100 // roughly
      });
    }
    return results;
  },

  generateHTML(yieldKt, fissionFrac, distanceKm) {
    const data = this.calculate(yieldKt, fissionFrac, distanceKm, 720);
    if (!data.length) return '<div style="color:var(--overlay0);font-size:11px">No fallout data (airburst)</div>';

    let html = `<div class="rd-header">Radiation at ${NM.fmtR(distanceKm)} from GZ (${NM.fmtYield(yieldKt)} surface)</div>`;
    html += '<div class="rd-table"><div class="rd-row rd-head"><span>Time</span><span>Rate (R/hr)</span><span>Status</span></div>';
    for (const d of data) {
      const status = d.rate > 300 ? 'LETHAL' : d.rate > 100 ? 'SEVERE' : d.rate > 10 ? 'DANGER' : d.rate > 0.5 ? 'CAUTION' : 'LOW';
      const statusColor = d.rate > 300 ? 'var(--red)' : d.rate > 100 ? 'var(--peach)' : d.rate > 10 ? 'var(--yellow)' : d.rate > 0.5 ? 'var(--teal)' : 'var(--green)';
      html += `<div class="rd-row"><span class="rd-time">${d.label}</span><span class="rd-rate">${d.rate >= 1 ? d.rate.toFixed(0) : d.rate.toFixed(2)}</span><span class="rd-status" style="color:${statusColor}">${status}</span></div>`;
    }
    html += '</div><div class="rd-note">7:10 rule: every 7x time increase = 10x dose rate decrease</div>';
    return html;
  }
};

// ---- SCREENSHOT MODE ----
NM.Screenshot = {
  active: false,

  toggle() {
    this.active = !this.active;
    document.getElementById('panel').style.display = this.active ? 'none' : '';
    document.getElementById('info-bar').style.display = this.active ? 'none' : '';
    document.getElementById('coords').style.display = this.active ? 'none' : '';
    document.getElementById('offline-badge').style.display = 'none';
    document.getElementById('screenshot-hint').style.display = this.active ? 'block' : 'none';

    // Hide Leaflet controls
    document.querySelectorAll('.leaflet-control-zoom, .leaflet-control-attribution').forEach(el => {
      el.style.display = this.active ? 'none' : '';
    });

    return this.active;
  }
};

// ---- CUSTOM OVERPRESSURE CALCULATOR ----
NM.CustomPsi = {
  // Given yield and target overpressure, calculate radius
  calcRadius(yieldKt, psi) {
    // Inverse of: psi = k * Y^(1/3) / R^3 (simplified)
    // Using known reference points to interpolate
    const Y = Math.max(yieldKt, 0.001);
    // psi ~ coeff * Y^(1/3) where coeff varies
    // At 20 psi: R = 0.24 * Y^(1/3), so 20 = k / 0.24, k = 4.8
    // Rough: R = (k/psi)^(1/3) * Y^(1/3) but it's not that simple
    // Use empirical fit: R = A * Y^(1/3) / psi^B
    // Calibrated: at Y=1kT, psi=20 -> R=0.24, psi=5 -> R=0.59, psi=1 -> R=1.93
    // Fit: R = 4.8 * Y^(1/3) * psi^(-0.93)
    const R = 4.8 * Math.pow(Y, 1/3) * Math.pow(psi, -0.93) * 0.8;
    return R; // km
  },

  generateHTML(yieldKt) {
    const psiValues = [0.5, 1, 2, 3, 5, 7, 10, 15, 20, 50, 100, 200];
    let html = '<div class="psi-table">';
    html += '<div class="psi-row psi-head"><span>Overpressure</span><span>Radius</span><span>Effect</span></div>';
    const effects = {
      0.5: 'Windows crack', 1: 'Windows shatter', 2: 'Light damage', 3: 'Moderate damage',
      5: 'Buildings collapse', 7: 'Heavy damage', 10: 'Severe destruction',
      15: 'Near-total destruction', 20: 'Reinforced concrete fails',
      50: 'Hardened structures fail', 100: 'Deep bunkers damaged', 200: 'Everything destroyed'
    };
    for (const psi of psiValues) {
      const r = this.calcRadius(yieldKt, psi);
      html += `<div class="psi-row"><span class="psi-val">${psi} psi</span><span class="psi-r">${NM.fmtDist(r)}</span><span class="psi-eff">${effects[psi] || ''}</span></div>`;
    }
    html += '</div>';
    return html;
  }
};

// ---- THERMAL FLASH GRADIENT OVERLAY ----
NM.ThermalOverlay = {
  layer: null,

  draw(map, lat, lng, effects) {
    this.clear(map);
    const maxR = effects.thermal1;
    if (maxR < 0.001) return;

    const ThermalLayer = L.Layer.extend({
      onAdd(map) {
        this._map = map;
        this._canvas = L.DomUtil.create('canvas', 'thermal-overlay');
        this._canvas.style.cssText = 'position:absolute;top:0;left:0;pointer-events:none;z-index:399;opacity:0.35';
        map.getPanes().overlayPane.appendChild(this._canvas);
        map.on('moveend zoomend resize', this._update, this);
        this._update();
      },
      onRemove(map) {
        L.DomUtil.remove(this._canvas);
        map.off('moveend zoomend resize', this._update, this);
      },
      _update() {
        const map = this._map, size = map.getSize();
        this._canvas.width = size.x;
        this._canvas.height = size.y;
        const ctx = this._canvas.getContext('2d');
        ctx.clearRect(0, 0, size.x, size.y);

        const center = map.latLngToContainerPoint([lat, lng]);
        const edgePt = map.latLngToContainerPoint([lat + maxR / 111.32, lng]);
        const pixelR = Math.abs(center.y - edgePt.y);

        if (pixelR < 5) return;

        const grad = ctx.createRadialGradient(center.x, center.y, 0, center.x, center.y, pixelR);
        grad.addColorStop(0, 'rgba(255, 255, 240, 0.9)');
        grad.addColorStop(0.15, 'rgba(255, 200, 100, 0.7)');
        grad.addColorStop(0.4, 'rgba(255, 120, 50, 0.4)');
        grad.addColorStop(0.7, 'rgba(200, 50, 20, 0.15)');
        grad.addColorStop(1, 'rgba(150, 30, 10, 0)');

        ctx.beginPath();
        ctx.arc(center.x, center.y, pixelR, 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.fill();

        const topLeft = map.containerPointToLayerPoint([0, 0]);
        L.DomUtil.setPosition(this._canvas, topLeft);
      }
    });

    this.layer = new ThermalLayer();
    this.layer.addTo(map);
  },

  clear(map) {
    if (this.layer) { map.removeLayer(this.layer); this.layer = null; }
  },

  toggle(map, lat, lng, effects) {
    if (this.layer) this.clear(map);
    else this.draw(map, lat, lng, effects);
    return !!this.layer;
  }
};

// ---- FALLOUT PARTICLE ANIMATION ----
NM.FalloutParticles = {
  layer: null, active: false, animId: null,
  particles: [],

  start(map, lat, lng, fallout, windAngle) {
    this.stop(map);
    if (!fallout) return;
    this.active = true;

    const downwind = ((windAngle + 180) % 360) * Math.PI / 180;
    const count = 200;
    const maxDist = fallout.light.length;
    const R = 6371;

    // Generate particles
    this.particles = [];
    for (let i = 0; i < count; i++) {
      this.particles.push({
        progress: Math.random(), // 0-1 along fallout path
        lateral: (Math.random() - 0.5) * 2, // -1 to 1 lateral offset
        speed: 0.0003 + Math.random() * 0.0005,
        size: 2 + Math.random() * 3,
        opacity: 0.3 + Math.random() * 0.5
      });
    }

    const ParticleLayer = L.Layer.extend({
      onAdd(map) {
        this._map = map;
        this._canvas = L.DomUtil.create('canvas', 'fallout-particles');
        this._canvas.style.cssText = 'position:absolute;top:0;left:0;pointer-events:none;z-index:401';
        map.getPanes().overlayPane.appendChild(this._canvas);
        map.on('moveend zoomend resize', this._resize, this);
        this._resize();
        this._animate();
      },
      onRemove(map) {
        NM.FalloutParticles.active = false;
        if (NM.FalloutParticles.animId) cancelAnimationFrame(NM.FalloutParticles.animId);
        L.DomUtil.remove(this._canvas);
        map.off('moveend zoomend resize', this._resize, this);
      },
      _resize() {
        const size = this._map.getSize();
        this._canvas.width = size.x;
        this._canvas.height = size.y;
      },
      _animate() {
        if (!NM.FalloutParticles.active) return;
        const map = this._map, ctx = this._canvas.getContext('2d');
        const size = map.getSize();
        ctx.clearRect(0, 0, size.x, size.y);

        const center = map.latLngToContainerPoint([lat, lng]);

        for (const p of NM.FalloutParticles.particles) {
          p.progress += p.speed;
          if (p.progress > 1) { p.progress = 0; p.lateral = (Math.random() - 0.5) * 2; }

          const dist = p.progress * maxDist;
          const latOff = (p.lateral * fallout.light.width * 0.5);
          const dx = dist * Math.cos(downwind) - latOff * Math.sin(downwind);
          const dy = dist * Math.sin(downwind) + latOff * Math.cos(downwind);

          const pLat = lat + (dy / R) * (180 / Math.PI);
          const pLng = lng + (dx / R) * (180 / Math.PI) / Math.cos(lat * Math.PI / 180);
          const pt = map.latLngToContainerPoint([pLat, pLng]);

          const fadeIn = p.progress < 0.1 ? p.progress / 0.1 : 1;
          const fadeOut = p.progress > 0.8 ? (1 - p.progress) / 0.2 : 1;
          const alpha = p.opacity * fadeIn * fadeOut;

          ctx.beginPath();
          ctx.arc(pt.x, pt.y, p.size, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(249, 226, 175, ${alpha})`;
          ctx.fill();
        }

        const topLeft = map.containerPointToLayerPoint([0, 0]);
        L.DomUtil.setPosition(this._canvas, topLeft);

        NM.FalloutParticles.animId = requestAnimationFrame(() => this._animate());
      }
    });

    this.layer = new ParticleLayer();
    this.layer.addTo(map);
  },

  stop(map) {
    this.active = false;
    if (this.animId) cancelAnimationFrame(this.animId);
    if (this.layer) { map.removeLayer(this.layer); this.layer = null; }
    this.particles = [];
  }
};

// ---- MULTI-DETONATION DAMAGE HEATMAP ----
NM.DamageHeatmap = {
  layer: null,

  draw(map, dets) {
    this.clear(map);
    if (!dets.length) return;

    const DmgLayer = L.Layer.extend({
      onAdd(map) {
        this._map = map;
        this._canvas = L.DomUtil.create('canvas', 'dmg-heatmap');
        this._canvas.style.cssText = 'position:absolute;top:0;left:0;pointer-events:none;z-index:397;opacity:0.4;mix-blend-mode:screen';
        map.getPanes().overlayPane.appendChild(this._canvas);
        map.on('moveend zoomend resize', this._update, this);
        this._update();
      },
      onRemove(map) {
        L.DomUtil.remove(this._canvas);
        map.off('moveend zoomend resize', this._update, this);
      },
      _update() {
        const map = this._map, size = map.getSize();
        this._canvas.width = size.x; this._canvas.height = size.y;
        const ctx = this._canvas.getContext('2d');
        ctx.clearRect(0, 0, size.x, size.y);

        for (const d of dets) {
          const e = d.effects;
          const maxR = Math.max(e.psi1, e.thermal1, e.emp) || 1;
          const center = map.latLngToContainerPoint([d.lat, d.lng]);
          const edgePt = map.latLngToContainerPoint([d.lat + maxR / 111.32, d.lng]);
          const pixelR = Math.abs(center.y - edgePt.y);
          if (pixelR < 3) continue;

          const grad = ctx.createRadialGradient(center.x, center.y, 0, center.x, center.y, pixelR);
          const intensity = Math.min(1, 0.4 + Math.log10(Math.max(d.yieldKt, 0.1)) * 0.12);
          grad.addColorStop(0, `rgba(243, 139, 168, ${intensity})`);
          grad.addColorStop(0.15, `rgba(250, 179, 135, ${intensity * 0.8})`);
          grad.addColorStop(0.35, `rgba(249, 226, 175, ${intensity * 0.5})`);
          grad.addColorStop(0.6, `rgba(203, 166, 247, ${intensity * 0.25})`);
          grad.addColorStop(1, 'rgba(203, 166, 247, 0)');

          ctx.beginPath();
          ctx.arc(center.x, center.y, pixelR, 0, Math.PI * 2);
          ctx.fillStyle = grad;
          ctx.fill();
        }

        const topLeft = map.containerPointToLayerPoint([0, 0]);
        L.DomUtil.setPosition(this._canvas, topLeft);
      }
    });
    this.layer = new DmgLayer();
    this.layer.addTo(map);
  },

  clear(map) {
    if (this.layer) { map.removeLayer(this.layer); this.layer = null; }
  }
};

// ---- RADIATION ZONE OVERLAY (canvas gradient) ----
NM.RadiationOverlay = {
  layer: null,

  draw(map, lat, lng, effects) {
    this.clear(map);
    if (!effects.fallout && !effects.radiation) return;
    const maxR = effects.fallout ? Math.max(effects.radiation, effects.fallout.heavy.length * 0.5) : effects.radiation;
    if (maxR < 0.01) return;

    const radR = effects.radiation;
    const RadLayer = L.Layer.extend({
      onAdd(map) {
        this._map = map;
        this._canvas = L.DomUtil.create('canvas', 'rad-overlay');
        this._canvas.style.cssText = 'position:absolute;top:0;left:0;pointer-events:none;z-index:398;opacity:0.3';
        map.getPanes().overlayPane.appendChild(this._canvas);
        map.on('moveend zoomend resize', this._update, this);
        this._update();
      },
      onRemove(map) {
        L.DomUtil.remove(this._canvas);
        map.off('moveend zoomend resize', this._update, this);
      },
      _update() {
        const map = this._map, size = map.getSize();
        this._canvas.width = size.x; this._canvas.height = size.y;
        const ctx = this._canvas.getContext('2d');
        ctx.clearRect(0, 0, size.x, size.y);
        const center = map.latLngToContainerPoint([lat, lng]);
        const edgePt = map.latLngToContainerPoint([lat + maxR / 111.32, lng]);
        const pixelR = Math.abs(center.y - edgePt.y);
        if (pixelR < 5) return;

        const grad = ctx.createRadialGradient(center.x, center.y, 0, center.x, center.y, pixelR);
        grad.addColorStop(0, 'rgba(166, 227, 161, 0.9)');    // bright green center
        grad.addColorStop(0.15, 'rgba(249, 226, 175, 0.7)'); // yellow
        grad.addColorStop(0.35, 'rgba(250, 179, 135, 0.5)'); // orange
        grad.addColorStop(0.6, 'rgba(243, 139, 168, 0.25)'); // red
        grad.addColorStop(0.85, 'rgba(203, 166, 247, 0.08)');// faint purple
        grad.addColorStop(1, 'rgba(203, 166, 247, 0)');

        ctx.beginPath();
        ctx.arc(center.x, center.y, pixelR, 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.fill();

        const topLeft = map.containerPointToLayerPoint([0, 0]);
        L.DomUtil.setPosition(this._canvas, topLeft);
      }
    });
    this.layer = new RadLayer();
    this.layer.addTo(map);
  },

  clear(map) {
    if (this.layer) { map.removeLayer(this.layer); this.layer = null; }
  }
};

// ---- CUMULATIVE DOSE CALCULATOR ----
NM.DoseCalc = {
  // Calculate cumulative dose for a person arriving at `arriveHr` hours after detonation
  // staying for `stayHr` hours, at `distKm` from GZ of a `yieldKt` surface burst
  calculate(yieldKt, fissionFrac, distKm, arriveHr, stayHr) {
    fissionFrac = (fissionFrac || 50) / 100;
    const refRate = 3000 * yieldKt * fissionFrac;
    const distFactor = Math.pow(Math.max(distKm, 0.1), -2);
    const rateAt1hr = refRate * distFactor;

    // Integrate dose rate R(t) = R1 * t^(-1.2) from arriveHr to arriveHr+stayHr
    // Integral of t^(-1.2) = t^(-0.2) / (-0.2)
    const t1 = Math.max(arriveHr, 0.1);
    const t2 = t1 + stayHr;
    const dose = rateAt1hr * (Math.pow(t1, -0.2) - Math.pow(t2, -0.2)) / 0.2;

    const rateOnArrival = rateAt1hr * Math.pow(t1, -1.2);
    const rateOnLeave = rateAt1hr * Math.pow(t2, -1.2);

    let prognosis, progColor;
    if (dose > 600) { prognosis = 'LETHAL - Near-certain death within days to weeks'; progColor = 'var(--red)'; }
    else if (dose > 300) { prognosis = 'SEVERE - 50%+ mortality without medical treatment'; progColor = 'var(--red)'; }
    else if (dose > 100) { prognosis = 'ACUTE - Radiation sickness, hospitalization required'; progColor = 'var(--peach)'; }
    else if (dose > 50) { prognosis = 'MODERATE - Nausea, fatigue, blood count changes'; progColor = 'var(--yellow)'; }
    else if (dose > 10) { prognosis = 'LOW - Minimal symptoms, long-term cancer risk elevated'; progColor = 'var(--teal)'; }
    else { prognosis = 'NEGLIGIBLE - Below threshold for acute effects'; progColor = 'var(--green)'; }

    return { dose, rateOnArrival, rateOnLeave, prognosis, progColor };
  },

  generateHTML(yieldKt, fissionFrac, distKm, arriveHr, stayHr) {
    const r = this.calculate(yieldKt, fissionFrac, distKm, arriveHr, stayHr);
    return `<div class="dose-panel">
      <div class="dose-main"><span class="dose-val">${r.dose >= 1 ? r.dose.toFixed(0) : r.dose.toFixed(2)}</span><span class="dose-unit">rem</span></div>
      <div class="dose-prognosis" style="color:${r.progColor}">${r.prognosis}</div>
      <div class="dose-detail">
        <div class="dose-row"><span>Rate on arrival (${arriveHr}h)</span><span>${r.rateOnArrival >= 1 ? r.rateOnArrival.toFixed(0) : r.rateOnArrival.toFixed(2)} R/hr</span></div>
        <div class="dose-row"><span>Rate on departure (${(arriveHr + stayHr).toFixed(1)}h)</span><span>${r.rateOnLeave >= 1 ? r.rateOnLeave.toFixed(0) : r.rateOnLeave.toFixed(2)} R/hr</span></div>
        <div class="dose-row"><span>Total time exposed</span><span>${stayHr}h</span></div>
      </div>
      <div class="dose-note">Assumes outdoor exposure with no shielding. Sheltering reduces dose proportionally to protection factor.</div>
    </div>`;
  }
};
