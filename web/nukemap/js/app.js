// NukeMap v3.0.0 - Main Application Controller
window.NM = window.NM || {};

(function() {
'use strict';

let map, currentDets = [], windAngle = 0, multiMode = false, mirvMode = false, currentMirvPreset = null;

// ---- MAP INIT ----
function initMap() {
  map = L.map('map', {center: [39.83, -98.58], zoom: 5, zoomControl: true, attributionControl: true});
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
  const offline = new Offline('', {maxZoom: 12, attribution: 'Offline | NukeMap'});

  let loaded = false;
  dark.on('tileerror', () => { if (!loaded) { loaded = true; map.removeLayer(dark); offline.addTo(map); showBadge(false); } });
  dark.on('tileload', () => { loaded = true; });
  dark.addTo(map);
  if (!navigator.onLine) { offline.addTo(map); showBadge(false); } else showBadge(true);
  window.addEventListener('online', () => showBadge(true));
  window.addEventListener('offline', () => showBadge(false));

  map.on('click', e => onMapClick(e.latlng.lat, e.latlng.lng));
  map.on('mousemove', e => { document.getElementById('coords').textContent = `${e.latlng.lat.toFixed(4)}, ${e.latlng.lng.toFixed(4)}`; });
  map.on('moveend zoomend', () => { if (NM.Mushroom3D.active) NM.Mushroom3D.onMapMove(); });
  map.getContainer().classList.add('crosshair');

  NM.Heatmap.init(map);
  loadFromURL();
}

function showBadge(on) {
  const b = document.getElementById('offline-badge'), d = b.querySelector('.ob-dot'), l = b.querySelector('.ob-lbl');
  b.classList.add('show'); d.className = 'ob-dot ' + (on ? 'on' : 'off'); l.textContent = on ? 'Online' : 'Offline';
  if (on) setTimeout(() => b.classList.remove('show'), 3000);
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
  const burst = getBurst();
  const hM = burst === 'custom' ? (+$('burst-height').value || 0) : 0;
  const fission = +$('fission-pct').value || 50;
  const effects = NM.calcEffects(Y, burst, hM, fission);
  const cas = NM.estimateCasualties(lat, lng, effects);

  // Single mode: clear previous
  if (!multiMode) {
    currentDets.forEach(d => d.layers.forEach(l => map.removeLayer(l)));
    currentDets = [];
    NM.Mushroom3D.hide();
  }

  const det = {
    id: Date.now(), lat, lng, yieldKt: Y, burstType: burst, heightM: hM, fission, effects, casualties: cas, layers: [],
    weapon: $('weapon-select').selectedOptions[0]?.textContent || 'Custom'
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

  // Seismic equivalent
  $('seismic-section').style.display = '';
  $('seismic-content').innerHTML = NM.Seismic.generateHTML(Y, effects.isSurface);

  // Size comparisons
  $('sizecompare-section').style.display = '';
  $('sizecompare-content').innerHTML = NM.SizeCompare.generate(effects);

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

  // Zoom to fit
  const largest = [effects.emp, effects.thermal1, effects.psi1].filter(r => r > 0).sort((a, b) => b - a)[0];
  if (largest) {
    map.fitBounds(L.circle([lat, lng], {radius: largest * 1000}).getBounds().pad(0.3), {maxZoom: 15, animate: true, duration: 0.8});
  }

  updateURL();
}

// ---- UI HELPERS ----
function $(id) { return document.getElementById(id); }
function getYield() { return NM.sliderToYield(+$('yield-slider').value); }
function getBurst() { return document.querySelector('.burst-btn.active')?.dataset.burst || 'airburst'; }

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
  document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', () => switchTab(t.dataset.tab)));

  // Weapon select (grouped by country)
  const sel = $('weapon-select');
  const groups = {};
  NM.WEAPONS.forEach((w, i) => { const g = w.country || 'Custom'; if (!groups[g]) groups[g] = []; groups[g].push({...w, idx: i}); });
  for (const [g, ws] of Object.entries(groups)) {
    const og = document.createElement('optgroup'); og.label = g;
    ws.forEach(w => { const o = document.createElement('option'); o.value = w.idx; o.textContent = w.name; o.title = w.desc; og.appendChild(o); });
    sel.appendChild(og);
  }
  sel.addEventListener('change', () => setYield(NM.WEAPONS[sel.value].yield_kt));

  // Yield slider
  $('yield-slider').addEventListener('input', () => { const kt = NM.sliderToYield(+$('yield-slider').value); updateYieldUI(kt); syncYieldInput(kt); });

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
  document.querySelectorAll('.burst-btn').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('.burst-btn').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    $('height-row').style.display = b.dataset.burst === 'custom' ? '' : 'none';
    $('wind-wrap').style.display = b.dataset.burst === 'surface' ? '' : 'none';
  }));

  // Detonate / Clear / Share
  $('detonate-btn').addEventListener('click', () => { const c = map.getCenter(); onMapClick(c.lat, c.lng); });
  $('clear-btn').addEventListener('click', clearAll);
  $('share-btn').addEventListener('click', showShareLink);
  $('share-copy').addEventListener('click', copyShareLink);

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
  $('panel-toggle').addEventListener('click', () => $('panel').classList.toggle('collapsed'));

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

  // Layer switcher buttons
  document.querySelectorAll('#layer-switcher .layer-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#layer-switcher .layer-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      NM.LayerSwitcher.switchTo(btn.dataset.layer);
    });
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
            document.querySelectorAll('.burst-btn').forEach(b => b.classList.toggle('active', b.dataset.burst === d.burst));
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

  // Export PNG + KML
  $('export-png').addEventListener('click', () => NM.ExportPNG.capture());
  $('export-kml').addEventListener('click', () => { if (currentDets.length) NM.KMLExport.download(currentDets); });

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

  // Rotating facts banner
  let factIdx = Math.floor(Math.random() * NM.Facts.length);
  function showFact() {
    const banner = $('fact-banner');
    $('fact-text').textContent = NM.Facts[factIdx % NM.Facts.length];
    banner.classList.add('show');
    factIdx++;
    setTimeout(() => banner.classList.remove('show'), 12000);
  }
  showFact();
  setInterval(showFact, 30000);
  $('fact-banner').addEventListener('click', () => { $('fact-banner').classList.remove('show'); showFact(); });
}

function switchTab(id) {
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === id));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.toggle('active', c.id === 'tab-' + id));
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
      document.querySelectorAll('.burst-btn').forEach(b => b.classList.toggle('active', b.dataset.burst === h.burst));
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
  const inp = $('search'), res = $('search-results'); let si = -1;
  inp.addEventListener('input', () => {
    const items = NM.searchLocations(inp.value); si = -1;
    if (!items.length) { res.classList.remove('active'); return; }
    res.innerHTML = items.map((it, i) => `<div class="sr-item" data-idx="${i}"><div><div class="sr-name">${NM.esc(it.name)}</div><div class="sr-detail">${NM.esc(it.detail)}</div></div>${it.pop ? `<div class="sr-pop">${NM.fmtNum(it.pop)}</div>` : ''}</div>`).join('');
    res.classList.add('active');
    res.querySelectorAll('.sr-item').forEach(el => el.addEventListener('click', () => { const it = items[+el.dataset.idx]; selectResult(it); }));
  });
  inp.addEventListener('keydown', e => { const items = res.querySelectorAll('.sr-item'); if (!items.length) return; if (e.key === 'ArrowDown') { e.preventDefault(); si = Math.min(si + 1, items.length - 1); items.forEach((el, i) => el.classList.toggle('selected', i === si)); } else if (e.key === 'ArrowUp') { e.preventDefault(); si = Math.max(si - 1, 0); items.forEach((el, i) => el.classList.toggle('selected', i === si)); } else if (e.key === 'Enter') { e.preventDefault(); (si >= 0 ? items[si] : items[0])?.click(); } else if (e.key === 'Escape') { res.classList.remove('active'); inp.blur(); } });
  inp.addEventListener('blur', () => setTimeout(() => res.classList.remove('active'), 200));
  inp.addEventListener('focus', () => { if (inp.value.trim()) inp.dispatchEvent(new Event('input')); });
}

function selectResult(it) {
  $('search').value = it.name + (it.detail ? ', ' + it.detail : '');
  $('search-results').classList.remove('active');
  map.flyTo([it.lat, it.lng], it.pop > 1e6 ? 11 : it.pop > 1e5 ? 12 : 10, {duration: 1});
}

// ---- UPDATE UI PANELS ----
function updateDetsList() {
  const list = $('dets-list'); list.innerHTML = '';
  currentDets.forEach((d, i) => {
    const nc = NM.findNearestCity(d.lat, d.lng);
    const nm = nc && nc.dist < 50 ? nc.name : `${d.lat.toFixed(2)}, ${d.lng.toFixed(2)}`;
    const el = document.createElement('div'); el.className = 'det-item';
    el.innerHTML = `<span class="det-idx">${i + 1}</span><span class="det-name">${NM.esc(nm)}</span><span class="det-yield">${NM.fmtYield(d.yieldKt)}</span><button class="det-remove" data-i="${i}">&times;</button>`;
    el.querySelector('.det-remove').addEventListener('click', e => { e.stopPropagation(); removeDet(i); });
    el.addEventListener('click', e => { if (!e.target.classList.contains('det-remove')) map.flyTo([d.lat, d.lng], map.getZoom(), {duration: 0.6}); });
    list.appendChild(el);
  });
}

function updateLegend(det) {
  const c = $('legend-items'); c.innerHTML = '';
  const e = det.effects;
  const items = [
    {id: 'fireball', r: e.fireball, color: '#f5e0dc'}, {id: 'radiation', r: e.radiation, color: '#a6e3a1'},
    {id: 'psi200', r: e.psi200, color: '#89dceb'}, {id: 'psi20', r: e.psi20, color: '#89b4fa'},
    {id: 'psi5', r: e.psi5, color: '#cba6f7'}, {id: 'thermal3', r: e.thermal3, color: '#fab387'},
    {id: 'psi1', r: e.psi1, color: '#f9e2af'}, {id: 'thermal1', r: e.thermal1, color: '#f5c2e7'},
    {id: 'emp', r: e.emp, color: '#94e2d5'},
  ];
  if (e.craterR > 0) items.unshift({id: 'crater', r: e.craterR, color: '#585b70'});

  items.forEach(it => {
    if (it.r < 0.0005) return;
    const def = NM.EFFECTS_DEF.find(d => d.id === it.id); if (!def) return;
    const div = document.createElement('div'); div.className = 'legend-item';
    div.innerHTML = `<div class="legend-dot" style="background:${it.color}"></div><div class="legend-label">${def.label}<span class="legend-desc">${def.desc.split('.')[0]}</span></div><div class="legend-value">${NM.fmtR(it.r)}<span class="legend-area">${NM.fmtArea(it.r)}</span></div><button class="legend-eye on" data-eid="${it.id}">&#10003;</button>`;
    div.querySelector('.legend-eye').addEventListener('click', ev => {
      const btn = ev.currentTarget; btn.classList.toggle('on');
      div.classList.toggle('dimmed', !btn.classList.contains('on'));
      toggleEffect(it.id, btn.classList.contains('on'));
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
  $('crater-panel').innerHTML = [
    ['Crater radius', NM.fmtDist(e.craterR)], ['Crater depth', NM.fmtDist(e.craterDepth)],
    ['Lip height', '~' + NM.fmtR(e.craterDepth * 0.5)], ['Ejecta radius', '~' + NM.fmtR(e.craterR * 2)],
  ].map(([l, v]) => `<div class="cloud-row"><span class="cl">${l}</span><span class="cv">${v}</span></div>`).join('');
}

function updateShelter(det) {
  $('shelter-section').style.display = '';
  $('shelter-content').innerHTML = NM.Shelter.generateReport(det.effects);
}

function updateStats() {
  let td = 0, ti = 0; currentDets.forEach(d => { td += d.casualties.deaths; ti += d.casualties.injuries; });
  $('stat-deaths').textContent = NM.fmtNum(td);
  $('stat-injuries').textContent = NM.fmtNum(ti);
  $('stat-total').textContent = NM.fmtNum(td + ti);
  $('stat-note').textContent = currentDets.length > 1 ? `Across ${currentDets.length} detonations` : 'Based on estimated population density';

  // Info bar
  const bar = $('info-bar');
  if (currentDets.length) {
    bar.innerHTML = `<div class="ib-stat"><div class="ib-val" style="color:var(--red)">${NM.fmtNum(td)}</div><div class="ib-lbl">Fatalities</div></div><div class="ib-div"></div><div class="ib-stat"><div class="ib-val" style="color:var(--peach)">${NM.fmtNum(ti)}</div><div class="ib-lbl">Injuries</div></div><div class="ib-div"></div><div class="ib-stat"><div class="ib-val" style="color:var(--yellow)">${NM.fmtNum(td + ti)}</div><div class="ib-lbl">Total</div></div>`;
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
  $('sizecompare-section').style.display = 'none';
  $('escape-section').style.display = 'none';
  $('legend-items').innerHTML = '<div style="color:var(--overlay0);font-size:12px;padding:10px 0">Detonate a weapon to see effects</div>';
  $('info-bar').classList.remove('active');
}

// ---- URL STATE ----
function updateURL() {
  if (!currentDets.length) { history.replaceState(null, '', location.pathname); return; }
  const params = currentDets.map(d => `${d.lat.toFixed(4)},${d.lng.toFixed(4)},${d.yieldKt},${d.burstType[0]}`).join(';');
  history.replaceState(null, '', `?d=${params}`);
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
      document.querySelectorAll('.burst-btn').forEach(b => b.classList.toggle('active', b.dataset.burst === burst));
      triggerDetonation(+lat, +lng);
    }
  });
}

function showShareLink() { $('share-section').style.display = ''; $('share-input').value = location.href; switchTab('results'); }
function copyShareLink() { $('share-input').select(); navigator.clipboard?.writeText($('share-input').value); $('share-copy').textContent = 'Copied!'; setTimeout(() => $('share-copy').textContent = 'Copy', 2000); }

// ---- INIT ----
function init() {
  NM.Sound.init();
  NM.Mushroom3D.init();
  initMap();
  initControls();
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('./sw.js').catch(() => {});
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
else init();

})();
