// NukeMap - Immersive Features Module
// Geiger counter, casualty counter animation, city size comparisons,
// seismic equivalent, escape time calc, GPS "Am I Safe?", shockwave ring,
// fallout contours, KML export, nuclear test database
window.NM = window.NM || {};

// ---- GEIGER COUNTER AUDIO ----
NM.Geiger = {
  ctx: null, active: false, intervalId: null,

  init() {
    try { this.ctx = new (window.AudioContext || window.webkitAudioContext)(); } catch(e) {}
  },

  start(map) {
    if (!this.ctx) this.init();
    this.active = true;
    this._handler = (e) => {
      if (!this.active || !NM._lastDet) return;
      const det = NM._lastDet;
      const dist = NM.haversine(det.lat, det.lng, e.latlng.lat, e.latlng.lng);
      // Radiation intensity falls off with distance squared
      const maxR = Math.max(det.effects.radiation, det.effects.psi1);
      const intensity = Math.max(0, 1 - dist / maxR);
      this._setRate(intensity);
    };
    map.on('mousemove', this._handler);
  },

  stop(map) {
    this.active = false;
    if (this._handler) map.off('mousemove', this._handler);
    if (this.intervalId) { clearInterval(this.intervalId); this.intervalId = null; }
  },

  _setRate(intensity) {
    if (this.intervalId) clearInterval(this.intervalId);
    if (intensity <= 0.01) return;
    // Clicks per second: 0.5 to 50 based on intensity
    const cps = 0.5 + intensity * intensity * 60;
    const interval = Math.max(15, 1000 / cps);
    this.intervalId = setInterval(() => this._click(intensity), interval);
  },

  _click(intensity) {
    if (!this.ctx || !this.active) return;
    if (this.ctx.state === 'suspended') this.ctx.resume();
    const now = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    osc.type = 'square';
    osc.frequency.value = 800 + Math.random() * 400;
    const gain = this.ctx.createGain();
    gain.gain.setValueAtTime(0.04 * intensity, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.02);
    const filter = this.ctx.createBiquadFilter();
    filter.type = 'highpass';
    filter.frequency.value = 1000;
    osc.connect(filter).connect(gain).connect(this.ctx.destination);
    osc.start(now);
    osc.stop(now + 0.025);
  }
};

// ---- CASUALTY COUNTER ANIMATION ----
NM.CasualtyCounter = {
  animate(deaths, injuries) {
    const dEl = document.getElementById('stat-deaths');
    const iEl = document.getElementById('stat-injuries');
    const tEl = document.getElementById('stat-total');
    if (!dEl) return;

    const duration = 2000;
    const start = performance.now();
    const tick = (now) => {
      const p = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - p, 4); // ease-out quartic
      const curD = Math.round(deaths * eased);
      const curI = Math.round(injuries * eased);
      dEl.textContent = NM.fmtNum(curD);
      iEl.textContent = NM.fmtNum(curI);
      tEl.textContent = NM.fmtNum(curD + curI);
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }
};

// ---- CITY SIZE COMPARISONS ----
NM.SizeCompare = {
  landmarks: [
    {name: 'Football field', km: 0.1, area: 0.005},
    {name: 'The White House grounds', km: 0.15, area: 0.007},
    {name: 'Vatican City', km: 0.35, area: 0.44},
    {name: 'Central Park (NYC)', km: 2.0, area: 3.41},
    {name: 'Manhattan', km: 3.6, area: 59.1},
    {name: 'Walt Disney World', km: 5.5, area: 101},
    {name: 'Washington DC', km: 8.5, area: 177},
    {name: 'Paris (city proper)', km: 5.3, area: 105},
    {name: 'San Francisco', km: 6.0, area: 121},
    {name: 'London (M25)', km: 25, area: 1572},
    {name: 'Los Angeles', km: 30, area: 1302},
    {name: 'Rhode Island', km: 37, area: 4001},
    {name: 'Connecticut', km: 60, area: 14357},
  ],

  generate(effects) {
    const zones = [
      {name: 'Fireball', r: effects.fireball, color: '#f5e0dc'},
      {name: '5 psi zone', r: effects.psi5, color: '#cba6f7'},
      {name: '1 psi zone', r: effects.psi1, color: '#f9e2af'},
      {name: 'Thermal burn zone', r: effects.thermal3, color: '#fab387'},
    ].filter(z => z.r > 0.01);

    let html = '<div class="sc-list">';
    for (const zone of zones) {
      const area = Math.PI * zone.r * zone.r;
      // Find the closest landmark
      let closest = this.landmarks[0];
      let closestDiff = Infinity;
      for (const lm of this.landmarks) {
        const diff = Math.abs(area - lm.area);
        if (diff < closestDiff) { closestDiff = diff; closest = lm; }
      }
      const ratio = area / closest.area;
      const comparison = ratio > 1
        ? `${ratio.toFixed(1)}x the size of ${closest.name}`
        : `${(ratio * 100).toFixed(0)}% the size of ${closest.name}`;

      html += `<div class="sc-item">
        <div class="sc-zone" style="color:${zone.color}">${zone.name} (${NM.fmtR(zone.r)} radius)</div>
        <div class="sc-comp">${comparison}</div>
      </div>`;
    }
    html += '</div>';
    return html;
  }
};

// ---- SEISMIC EQUIVALENT ----
NM.Seismic = {
  // Nuclear explosion to earthquake magnitude (approximate)
  // Based on: M = 4.0 + 0.67 * log10(Y_kt) for contained underground
  // Surface/air: reduced coupling, roughly M = 3.5 + 0.67 * log10(Y_kt)
  calculate(yieldKt, isSurface) {
    const coupling = isSurface ? 0.5 : 1.0; // surface = less seismic coupling
    const magnitude = 3.5 + 0.67 * Math.log10(Math.max(yieldKt * coupling, 0.001));

    // Earthquake comparison
    let comparison = '';
    if (magnitude < 3) comparison = 'Minor tremor, rarely felt';
    else if (magnitude < 4) comparison = 'Like a small local earthquake';
    else if (magnitude < 5) comparison = 'Similar to 2011 Virginia earthquake';
    else if (magnitude < 6) comparison = 'Similar to 2014 Napa earthquake';
    else if (magnitude < 7) comparison = 'Similar to 1994 Northridge earthquake';
    else if (magnitude < 8) comparison = 'Similar to 2010 Haiti earthquake';
    else comparison = 'Greater than the 2011 Tohoku earthquake';

    const feltRadius = Math.pow(10, magnitude - 1.5) * 0.5; // very rough km

    return { magnitude, comparison, feltRadiusKm: feltRadius };
  },

  generateHTML(yieldKt, isSurface) {
    const r = this.calculate(yieldKt, isSurface);
    return `<div class="seismic-panel">
      <div class="seis-mag">${r.magnitude.toFixed(1)}</div>
      <div class="seis-label">Richter Equivalent</div>
      <div class="seis-comp">${r.comparison}</div>
      <div class="seis-felt">Seismic waves felt up to ~${NM.fmtR(r.feltRadiusKm)} away</div>
    </div>`;
  }
};

// ---- ESCAPE TIME CALCULATOR ----
NM.EscapeTime = {
  speeds: [
    {name: 'Walking', kmh: 5, icon: 'walk'},
    {name: 'Running', kmh: 12, icon: 'run'},
    {name: 'Bicycle', kmh: 20, icon: 'bike'},
    {name: 'Car (city)', kmh: 35, icon: 'car'},
    {name: 'Car (highway)', kmh: 100, icon: 'highway'},
  ],

  generate(effects) {
    const zones = [
      {name: '5 psi (fatal zone)', r: effects.psi5, color: '#cba6f7'},
      {name: '1 psi (injury zone)', r: effects.psi1, color: '#f9e2af'},
      {name: 'Thermal burn zone', r: effects.thermal1, color: '#f5c2e7'},
    ].filter(z => z.r > 0.01);

    let html = '<div class="escape-table"><div class="esc-row esc-head"><span>Mode</span>';
    zones.forEach(z => html += `<span style="color:${z.color}">${z.name.split('(')[0].trim()}</span>`);
    html += '</div>';

    for (const speed of this.speeds) {
      html += `<div class="esc-row"><span class="esc-mode">${speed.name}</span>`;
      for (const zone of zones) {
        const timeMin = (zone.r / speed.kmh) * 60;
        const display = timeMin < 1 ? `${(timeMin*60).toFixed(0)}s` : timeMin < 60 ? `${timeMin.toFixed(0)}m` : `${(timeMin/60).toFixed(1)}h`;
        const feasible = timeMin < 15; // blast wave arrives in seconds/minutes
        html += `<span class="${feasible ? '' : 'esc-too-slow'}">${display}</span>`;
      }
      html += '</div>';
    }
    html += '</div><div class="esc-note">Warning: blast wave travels at ~1,200 km/h. You cannot outrun it. These times assume pre-evacuation.</div>';
    return html;
  }
};

// ---- GPS "AM I SAFE?" MODE ----
NM.GPSSafe = {
  marker: null,

  check(map) {
    if (!navigator.geolocation) {
      document.getElementById('gps-result').innerHTML = '<div style="color:var(--red);font-size:11px">Geolocation not available in this browser</div>';
      return;
    }
    document.getElementById('gps-result').innerHTML = '<div style="color:var(--overlay0);font-size:11px">Getting your location...</div>';

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = pos.coords.latitude, lng = pos.coords.longitude;
        this._analyze(map, lat, lng);
      },
      (err) => {
        document.getElementById('gps-result').innerHTML = `<div style="color:var(--red);font-size:11px">Location error: ${err.message}</div>`;
      },
      {enableHighAccuracy: true, timeout: 10000}
    );
  },

  _analyze(map, lat, lng) {
    const det = NM._lastDet;
    if (!det) {
      document.getElementById('gps-result').innerHTML = '<div style="color:var(--overlay0);font-size:11px">No detonation to check against. Detonate first.</div>';
      return;
    }

    const dist = NM.haversine(det.lat, det.lng, lat, lng);
    const e = det.effects;

    // Place marker at user's location
    if (this.marker) map.removeLayer(this.marker);
    const icon = L.divIcon({
      className: '', iconSize: [24, 24], iconAnchor: [12, 12],
      html: '<div style="width:24px;height:24px;border-radius:50%;background:var(--green);border:3px solid var(--text);box-shadow:0 0 10px var(--green)"></div>'
    });
    this.marker = L.marker([lat, lng], {icon}).addTo(map);

    let status, statusColor, advice;
    if (dist <= e.fireball) { status = 'VAPORIZED'; statusColor = 'var(--red)'; advice = 'You are inside the fireball. Instant death.'; }
    else if (dist <= e.psi20) { status = 'FATAL'; statusColor = 'var(--red)'; advice = 'Near-certain death. No survivable shelter at this distance.'; }
    else if (dist <= e.psi5) { status = 'CRITICAL'; statusColor = 'var(--red)'; advice = 'Seek reinforced concrete basement immediately. ~50% fatality rate.'; }
    else if (dist <= e.psi1) { status = 'DANGER'; statusColor = 'var(--peach)'; advice = 'Get away from windows NOW. Interior room, below window level. Flying glass is lethal.'; }
    else if (dist <= e.thermal1) { status = 'CAUTION'; statusColor = 'var(--yellow)'; advice = 'Do NOT look toward the flash. Take cover behind solid objects. Flash burns possible.'; }
    else if (dist <= e.emp) { status = 'EMP ZONE'; statusColor = 'var(--teal)'; advice = 'Electronics may be disrupted. Expect power outages. Monitor emergency broadcasts.'; }
    else { status = 'SAFE'; statusColor = 'var(--green)'; advice = 'You are outside the immediate blast effects. Monitor for fallout if surface burst.'; }

    if (e.fallout && dist <= e.fallout.light.length * 1.5) {
      advice += ' FALLOUT WARNING: You may be in the fallout path. Shelter in place for 24-48 hours.';
    }

    document.getElementById('gps-result').innerHTML = `<div class="gps-report">
      <div class="gps-status" style="color:${statusColor}">${status}</div>
      <div class="gps-dist">${NM.fmtDist(dist)} from ground zero</div>
      <div class="gps-advice">${advice}</div>
      <div class="gps-coords">${lat.toFixed(4)}, ${lng.toFixed(4)}</div>
    </div>`;
  }
};

// ---- PERSISTENT SHOCKWAVE RING ON MAP ----
NM.ShockwaveRing = {
  layers: [],

  draw(map, lat, lng, effects) {
    this.clear(map);
    // Expanding shockwave that fades and settles at 1 psi radius
    const targetR = effects.psi1 * 1000;
    const duration = 4000;
    const ring = L.circle([lat, lng], {
      radius: 10, color: '#f9e2af', weight: 3, opacity: 0.8,
      fill: false, className: 'shockwave-ring'
    }).addTo(map);
    this.layers.push(ring);

    const start = performance.now();
    const tick = (now) => {
      const p = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - p, 2);
      ring.setRadius(eased * targetR);
      ring.setStyle({
        opacity: p < 0.3 ? 0.9 : 0.9 * (1 - (p - 0.3) / 0.7),
        weight: Math.max(1, 4 * (1 - p))
      });
      if (p < 1) requestAnimationFrame(tick);
      else {
        // Leave a faint residual ring at 1 psi
        ring.setStyle({opacity: 0.15, weight: 1, dashArray: '4 6'});
      }
    };
    requestAnimationFrame(tick);
  },

  clear(map) {
    this.layers.forEach(l => map.removeLayer(l));
    this.layers = [];
  }
};

// ---- FALLOUT DOSE RATE CONTOUR LINES ----
NM.FalloutContours = {
  layers: [],

  draw(map, lat, lng, fallout, windAngle) {
    this.clear(map);
    if (!fallout) return;

    const dAngle = ((windAngle + 180) % 360) * Math.PI / 180;
    const R = 6371;

    // Draw contour lines at different dose rates
    const contours = [
      {label: '1000 R/hr', frac: 0.2, color: '#f38ba8', weight: 2},
      {label: '300 R/hr', frac: 0.4, color: '#fab387', weight: 1.5},
      {label: '100 R/hr', frac: 0.6, color: '#f9e2af', weight: 1.5},
      {label: '10 R/hr', frac: 0.85, color: '#a6e3a1', weight: 1},
      {label: '1 R/hr', frac: 1.0, color: '#89b4fa', weight: 1},
    ];

    contours.forEach(c => {
      const l = fallout.light.length * c.frac;
      const w = fallout.light.width * c.frac;
      const pts = [];
      for (let i = 0; i <= 40; i++) {
        const t = (i / 40) * 2 * Math.PI;
        const dx = l * (0.5 + 0.5 * Math.cos(t)) * Math.cos(dAngle) - (w / 2) * Math.sin(t) * Math.sin(dAngle);
        const dy = l * (0.5 + 0.5 * Math.cos(t)) * Math.sin(dAngle) + (w / 2) * Math.sin(t) * Math.cos(dAngle);
        pts.push([lat + (dy / R) * (180 / Math.PI), lng + (dx / R) * (180 / Math.PI) / Math.cos(lat * Math.PI / 180)]);
      }
      const line = L.polyline(pts, {color: c.color, weight: c.weight, opacity: 0.6, dashArray: '6 4'}).addTo(map);
      this.layers.push(line);

      // Label at the downwind tip
      if (pts.length > 1) {
        const tipIdx = Math.floor(pts.length * 0.02);
        const tip = pts[tipIdx] || pts[0];
        const icon = L.divIcon({
          className: 'fallout-contour-label',
          html: `<span style="color:${c.color}">${c.label}</span>`,
          iconSize: [0, 0], iconAnchor: [-5, 6]
        });
        const m = L.marker(tip, {icon, interactive: false}).addTo(map);
        this.layers.push(m);
      }
    });
  },

  clear(map) {
    this.layers.forEach(l => map.removeLayer(l));
    this.layers = [];
  }
};

// ---- KML EXPORT ----
NM.KMLExport = {
  generate(dets) {
    let placemarks = '';
    dets.forEach((det, i) => {
      const e = det.effects;
      const rings = [
        {name: 'Fireball', r: e.fireball, color: 'ff00dcf5'},
        {name: '20 psi', r: e.psi20, color: 'fffab489'},
        {name: '5 psi', r: e.psi5, color: 'fff7a6cb'},
        {name: '1 psi', r: e.psi1, color: 'ffafe2f9'},
        {name: '3rd Degree Burns', r: e.thermal3, color: 'ff87b3fa'},
        {name: 'EMP', r: e.emp, color: 'ffd5e294'},
      ];

      rings.forEach(ring => {
        if (ring.r < 0.001) return;
        // Generate circle as polygon
        const pts = [];
        for (let j = 0; j <= 72; j++) {
          const angle = (j / 72) * 2 * Math.PI;
          const lat2 = det.lat + (ring.r / 6371) * (180 / Math.PI) * Math.sin(angle);
          const lng2 = det.lng + (ring.r / 6371) * (180 / Math.PI) * Math.cos(angle) / Math.cos(det.lat * Math.PI / 180);
          pts.push(`${lng2},${lat2},0`);
        }
        placemarks += `
    <Placemark>
      <name>${ring.name} - Det ${i + 1} (${NM.fmtYield(det.yieldKt)})</name>
      <Style><LineStyle><color>${ring.color}</color><width>2</width></LineStyle><PolyStyle><color>40${ring.color.slice(2)}</color></PolyStyle></Style>
      <Polygon><outerBoundaryIs><LinearRing><coordinates>${pts.join(' ')}</coordinates></LinearRing></outerBoundaryIs></Polygon>
    </Placemark>`;
      });

      // GZ marker
      placemarks += `
    <Placemark>
      <name>Ground Zero ${i + 1} - ${NM.fmtYield(det.yieldKt)}</name>
      <Point><coordinates>${det.lng},${det.lat},0</coordinates></Point>
    </Placemark>`;
    });

    return `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>NukeMap Export</name>
    <description>Nuclear weapon effects simulation</description>
    ${placemarks}
  </Document>
</kml>`;
  },

  download(dets) {
    const kml = this.generate(dets);
    const blob = new Blob([kml], {type: 'application/vnd.google-earth.kml+xml'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'nukemap-export.kml';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }
};

// ---- NUCLEAR TEST DATABASE (50 notable tests) ----
NM.TestDatabase = [
  {name:'Trinity',lat:33.677,lng:-106.475,kt:21,country:'US',year:1945,type:'Tower'},
  {name:'Able (Crossroads)',lat:11.583,lng:165.383,kt:23,country:'US',year:1946,type:'Airdrop'},
  {name:'Baker (Crossroads)',lat:11.583,lng:165.383,kt:23,country:'US',year:1946,type:'Underwater'},
  {name:'Joe-1 (First Soviet)',lat:50.440,lng:77.789,kt:22,country:'USSR',year:1949,type:'Tower'},
  {name:'Hurricane (First UK)',lat:-20.388,lng:115.545,kt:25,country:'UK',year:1952,type:'Ship'},
  {name:'Ivy Mike',lat:11.668,lng:162.195,kt:10400,country:'US',year:1952,type:'Surface'},
  {name:'Ivy King',lat:11.620,lng:162.235,kt:500,country:'US',year:1952,type:'Airdrop'},
  {name:'Joe-4 (First H-bomb)',lat:50.440,lng:77.789,kt:400,country:'USSR',year:1953,type:'Tower'},
  {name:'Castle Bravo',lat:11.697,lng:165.273,kt:15000,country:'US',year:1954,type:'Surface'},
  {name:'Castle Romeo',lat:11.633,lng:165.017,kt:11000,country:'US',year:1954,type:'Barge'},
  {name:'Castle Yankee',lat:11.533,lng:165.017,kt:13500,country:'US',year:1954,type:'Barge'},
  {name:'Gerboise Bleue (1st FR)',lat:26.316,lng:0.049,kt:70,country:'FR',year:1960,type:'Tower'},
  {name:'Tsar Bomba',lat:73.812,lng:54.583,kt:50000,country:'USSR',year:1961,type:'Airdrop'},
  {name:'596 (First Chinese)',lat:41.533,lng:88.717,kt:22,country:'CN',year:1964,type:'Tower'},
  {name:'Canopus (French H-bomb)',lat:-21.870,lng:-138.720,kt:2600,country:'FR',year:1968,type:'Balloon'},
  {name:'Smiling Buddha (India)',lat:27.095,lng:71.753,kt:12,country:'IN',year:1974,type:'Underground'},
  {name:'Chagai-I (Pakistan)',lat:28.990,lng:65.178,kt:12,country:'PK',year:1998,type:'Underground'},
  {name:'DPRK Test 1',lat:41.281,lng:129.106,kt:0.7,country:'DPRK',year:2006,type:'Underground'},
  {name:'DPRK Test 6',lat:41.300,lng:129.078,kt:250,country:'DPRK',year:2017,type:'Underground'},
  // Major US Nevada tests
  {name:'Sedan',lat:37.177,lng:-116.047,kt:104,country:'US',year:1962,type:'Underground (cratering)'},
  {name:'Storax Sedan Crater',lat:37.177,lng:-116.047,kt:104,country:'US',year:1962,type:'Underground'},
  {name:'Upshot-Knothole Annie',lat:37.068,lng:-116.032,kt:16,country:'US',year:1953,type:'Tower'},
  {name:'Plumbbob Hood',lat:37.067,lng:-116.020,kt:74,country:'US',year:1957,type:'Balloon'},
  // Soviet notable
  {name:'RDS-37 (Soviet H-bomb)',lat:50.440,lng:77.789,kt:1600,country:'USSR',year:1955,type:'Airdrop'},
  {name:'Test 219 (Largest underground)',lat:73.370,lng:54.750,kt:3600,country:'USSR',year:1973,type:'Underground'},
];

NM.TestDB = {
  layers: [],
  visible: false,

  toggle(map) {
    this.visible = !this.visible;
    if (this.visible) this.show(map);
    else this.clear(map);
    return this.visible;
  },

  show(map) {
    this.clear(map);
    const countryColors = {US:'#89b4fa',USSR:'#f38ba8',UK:'#a6e3a1',FR:'#cba6f7',CN:'#fab387',IN:'#f9e2af',PK:'#94e2d5',DPRK:'#f5c2e7'};

    for (const test of NM.TestDatabase) {
      const r = Math.max(3, Math.min(20, Math.log10(Math.max(test.kt, 0.1)) * 4));
      const color = countryColors[test.country] || '#cdd6f4';
      const marker = L.circleMarker([test.lat, test.lng], {
        radius: r, color, fillColor: color, fillOpacity: 0.4, weight: 1.5, opacity: 0.7
      }).bindTooltip(`<b>${test.name}</b><br>${test.country} ${test.year}<br>${NM.fmtYield(test.kt)} (${test.type})`, {
        className: 'test-tooltip'
      }).addTo(map);
      this.layers.push(marker);
    }
  },

  clear(map) {
    this.layers.forEach(l => map.removeLayer(l));
    this.layers = [];
  }
};

// ---- GROUND-LEVEL EXPERIENCE REPORT ----
NM.GroundReport = {
  generate(effects, yieldKt) {
    const distances = [
      {km: effects.fireball, label: 'Fireball Edge'},
      {km: effects.psi20, label: '20 psi Zone'},
      {km: effects.psi5, label: '5 psi Zone'},
      {km: effects.thermal3, label: '3rd Degree Burn Zone'},
      {km: effects.psi1, label: '1 psi Zone'},
      {km: effects.thermal1, label: '1st Degree Burn Zone'},
    ].filter(d => d.km > 0.01);

    const reports = {
      'Fireball Edge': {
        see: 'You see nothing. The air itself becomes plasma at millions of degrees. Everything is vaporized instantly \u2014 buildings, vehicles, people reduced to their component atoms.',
        hear: 'The sound has not yet arrived. You would not exist long enough to hear it.',
        feel: 'Instantaneous vaporization. No pain \u2014 nerve conduction speed is far too slow.',
        survive: 'Impossible. No material on Earth can survive these temperatures.'
      },
      '20 psi Zone': {
        see: 'An impossibly bright flash turns everything white. Half a second later, a wall of debris and dust moving at 500+ mph obliterates everything in sight. Concrete buildings explode outward.',
        hear: 'A crack like reality splitting open, followed by a roar louder than any jet engine. Your eardrums rupture instantly.',
        feel: 'A crushing force hits from all directions. 500 mph winds tear clothing from your body. Internal organs rupture from overpressure.',
        survive: 'Effectively impossible. Even deep basements are crushed.'
      },
      '5 psi Zone': {
        see: 'Blinding white flash, then everything catches fire simultaneously. Windows explode inward as razor shrapnel. Buildings collapse in slow motion. A wall of fire and debris rushes toward you.',
        hear: 'Thunder that never stops. Cracking, groaning, smashing as every structure fails.',
        feel: '160 mph winds throw you across the room. Glass shards embedded in exposed skin. Intense heat on exposed surfaces.',
        survive: 'About 50% fatality rate. Underground concrete shelters offer the best chance.'
      },
      '3rd Degree Burn Zone': {
        see: 'The flash is brighter than looking directly at the sun. Everything combustible ignites \u2014 curtains, paper, clothing, dry leaves. Multiple fires start simultaneously.',
        hear: 'A deep rolling thunder arrives seconds after the flash, lasting 10+ seconds.',
        feel: 'Exposed skin chars instantly. Full-thickness burns. Clothing may ignite. Hair catches fire.',
        survive: 'Being behind any solid wall or inside a building dramatically improves survival. Do NOT look at the flash.'
      },
      '1 psi Zone': {
        see: 'A blinding flash on the horizon. Seconds later, every window in sight explodes inward simultaneously. Car alarms trigger. Power goes out. A mushroom cloud rises.',
        hear: 'A sharp bang followed by sustained rumbling like distant thunder. Glass shattering everywhere.',
        feel: 'A sudden blast of hot wind. Glass fragments hit you if you were near a window. The building sways.',
        survive: 'High survival rate if away from windows. Interior rooms, below window level. The #1 cause of injury here is flying glass.'
      },
      '1st Degree Burn Zone': {
        see: 'A flash bright enough to leave afterimages for minutes. You may be temporarily blinded. A mushroom cloud rises on the horizon.',
        hear: 'A distant boom arrives 20+ seconds after the flash, like faraway thunder.',
        feel: 'A brief pulse of heat on exposed skin, like opening an oven door. Sunburn-like reddening develops over minutes.',
        survive: 'Very high survival rate. Take cover, do NOT look toward the blast. Monitor for fallout.'
      },
    };

    let html = '<div class="ground-report">';
    for (const d of distances) {
      const r = reports[d.label];
      if (!r) continue;
      html += `<div class="gr-zone">
        <div class="gr-header"><span class="gr-label">${d.label}</span><span class="gr-dist">${NM.fmtDist(d.km)} from GZ</span></div>
        <div class="gr-row"><span class="gr-sense">See</span><span class="gr-desc">${r.see}</span></div>
        <div class="gr-row"><span class="gr-sense">Hear</span><span class="gr-desc">${r.hear}</span></div>
        <div class="gr-row"><span class="gr-sense">Feel</span><span class="gr-desc">${r.feel}</span></div>
        <div class="gr-row gr-survive"><span class="gr-sense">Survive</span><span class="gr-desc">${r.survive}</span></div>
      </div>`;
    }
    html += '</div>';
    return html;
  }
};

// ---- MUSHROOM CLOUD HEIGHT COMPARISON ----
NM.CloudCompare = {
  landmarks: [
    {name: 'Empire State Building', km: 0.443},
    {name: 'Burj Khalifa', km: 0.828},
    {name: 'Commercial aircraft cruise', km: 10},
    {name: 'Weather balloons', km: 30},
    {name: 'Edge of space (Karman line)', km: 100},
    {name: 'Low Earth orbit (ISS)', km: 408},
  ],

  generate(effects) {
    const cloudH = effects.cloudTopH;
    if (cloudH < 0.1) return '';

    const maxH = Math.max(cloudH * 1.3, this.landmarks.find(l => l.km > cloudH)?.km || cloudH * 1.5);
    const W = 260, H = 140;
    const sy = (km) => H - 10 - (km / maxH) * (H - 20);

    let svg = `<svg viewBox="0 0 ${W} ${H}" class="cloud-compare-svg">`;
    svg += `<rect width="${W}" height="${H}" fill="var(--mantle)" rx="6"/>`;

    // Landmarks
    for (const lm of this.landmarks) {
      if (lm.km > maxH) continue;
      const y = sy(lm.km);
      svg += `<line x1="30" y1="${y}" x2="${W-10}" y2="${y}" stroke="var(--surface1)" stroke-width="0.5" stroke-dasharray="3 4"/>`;
      svg += `<text x="32" y="${y - 2}" fill="var(--overlay0)" font-size="6">${lm.name}</text>`;
      svg += `<text x="${W-12}" y="${y - 2}" fill="var(--overlay0)" font-size="6" text-anchor="end">${lm.km >= 1 ? lm.km.toFixed(lm.km >= 10 ? 0 : 1) + ' km' : (lm.km * 1000).toFixed(0) + ' m'}</text>`;
    }

    // Cloud
    const cloudY = sy(cloudH);
    const capW = 30, capH = 12;
    svg += `<rect x="${13}" y="${cloudY}" width="4" height="${sy(0) - cloudY}" fill="rgba(139,115,85,0.4)" rx="2"/>`;
    svg += `<ellipse cx="15" cy="${cloudY}" rx="${capW/2}" ry="${capH/2}" fill="rgba(238,136,68,0.5)" stroke="#ee8844" stroke-width="1"/>`;
    svg += `<text x="15" y="${cloudY - capH/2 - 3}" fill="var(--peach)" font-size="8" font-weight="700" text-anchor="middle">${cloudH.toFixed(1)} km</text>`;

    // Ground
    svg += `<line x1="5" y1="${sy(0)}" x2="${W-5}" y2="${sy(0)}" stroke="var(--surface2)" stroke-width="1"/>`;
    svg += `<text x="8" y="${sy(0) + 9}" fill="var(--overlay0)" font-size="6">Ground</text>`;

    svg += '</svg>';
    return svg;
  }
};

// ---- ANIMATED NUCLEAR TEST TIMELINE ----
NM.TestTimeline = {
  layers: [], active: false, animId: null,

  play(map) {
    this.stop(map);
    this.active = true;
    const tests = NM.TestDatabase.slice().sort((a, b) => a.year - b.year);
    const countryColors = {US:'#89b4fa',USSR:'#f38ba8',UK:'#a6e3a1',FR:'#cba6f7',CN:'#fab387',IN:'#f9e2af',PK:'#94e2d5',DPRK:'#f5c2e7'};

    // Show year counter on map
    const yearEl = document.createElement('div');
    yearEl.className = 'test-timeline-year';
    yearEl.id = 'tt-year';
    (NM.getUiRoot ? NM.getUiRoot() : document.body).appendChild(yearEl);

    let idx = 0;
    const tick = () => {
      if (!this.active || idx >= tests.length) {
        yearEl.textContent = 'Timeline complete';
        setTimeout(() => yearEl.remove(), 3000);
        this.active = false;
        return;
      }
      const t = tests[idx];
      const color = countryColors[t.country] || '#cdd6f4';
      const r = Math.max(4, Math.min(25, Math.log10(Math.max(t.kt, 0.1)) * 5));

      // Animated expanding circle
      const marker = L.circleMarker([t.lat, t.lng], {
        radius: 2, color, fillColor: color, fillOpacity: 0.7, weight: 1.5, opacity: 0.8
      }).addTo(map);
      this.layers.push(marker);

      // Animate expansion
      let frame = 0;
      const expand = () => {
        frame++;
        if (frame > 15) return;
        marker.setRadius(2 + (r - 2) * (frame / 15));
        marker.setStyle({fillOpacity: 0.7 - (frame / 15) * 0.4});
        requestAnimationFrame(expand);
      };
      requestAnimationFrame(expand);

      marker.bindTooltip(`<b>${t.name}</b><br>${t.country} ${t.year}<br>${NM.fmtYield(t.kt)}`, {className: 'test-tooltip'});

      yearEl.innerHTML = `<span style="color:${color}">${t.country}</span> ${t.year} - ${t.name} (${NM.fmtYield(t.kt)})`;

      idx++;
      this.animId = setTimeout(tick, 350);
    };

    map.flyTo([20, 0], 2, {duration: 1});
    setTimeout(tick, 1200);
  },

  stop(map) {
    this.active = false;
    if (this.animId) clearTimeout(this.animId);
    this.layers.forEach(l => map.removeLayer(l));
    this.layers = [];
    const el = document.getElementById('tt-year');
    if (el) el.remove();
  }
};

// ---- CONVENTIONAL WEAPON EQUIVALENTS ----
NM.ConventionalCompare = {
  weapons: [
    {name:'MOAB (GBU-43)', tnt_tons: 11, desc:'Largest non-nuclear US bomb'},
    {name:'FOAB (Russia)', tnt_tons: 44, desc:'Largest non-nuclear bomb ever'},
    {name:'Tomahawk cruise missile', tnt_tons: 0.45, desc:'Standard cruise missile'},
    {name:'Mk 84 bomb', tnt_tons: 0.43, desc:'Standard 2,000 lb bomb'},
    {name:'Grand Slam (WW2)', tnt_tons: 6.5, desc:'Largest WW2 conventional bomb'},
    {name:'Oklahoma City bombing', tnt_tons: 2, desc:'1995 truck bomb'},
    {name:'Halifax Explosion (1917)', tnt_tons: 2900, desc:'Largest accidental non-nuclear'},
  ],

  generate(yieldKt) {
    const yieldTons = yieldKt * 1000;
    let html = '<div class="conv-list">';
    for (const w of this.weapons) {
      const count = yieldTons / w.tnt_tons;
      if (count < 0.5) continue;
      const display = count >= 1e6 ? (count/1e6).toFixed(1) + 'M' : count >= 1e3 ? (count/1e3).toFixed(count >= 1e4 ? 0 : 1) + 'K' : count.toFixed(count >= 100 ? 0 : 1);
      html += `<div class="conv-row"><span class="conv-count">${display}x</span><span class="conv-name">${w.name}</span><span class="conv-desc">${w.desc}</span></div>`;
    }
    html += '</div>';
    return html;
  }
};

// ---- FALLOUT TIME-LAPSE ----
NM.FalloutTimelapse = {
  layer: null,
  animId: null,

  draw(map, lat, lng, fallout, windAngle, hours) {
    this.clear(map);
    if (!fallout) return;
    const heavyFrac = Math.min(1, hours / 3);
    const lightFrac = Math.min(1, Math.sqrt(hours / 24));
    const dAngle = ((windAngle + 180) % 360) * Math.PI / 180;
    const R = 6371;
    const mkE = (l, w) => {
      const pts = [];
      for (let i = 0; i <= 40; i++) {
        const t = (i / 40) * 2 * Math.PI;
        const dx = l * (0.5 + 0.5 * Math.cos(t)) * Math.cos(dAngle) - (w / 2) * Math.sin(t) * Math.sin(dAngle);
        const dy = l * (0.5 + 0.5 * Math.cos(t)) * Math.sin(dAngle) + (w / 2) * Math.sin(t) * Math.cos(dAngle);
        pts.push([lat + (dy / R) * (180 / Math.PI), lng + (dx / R) * (180 / Math.PI) / Math.cos(lat * Math.PI / 180)]);
      }
      return pts;
    };
    const layers = [];
    layers.push(L.polygon(mkE(fallout.heavy.length * heavyFrac, fallout.heavy.width * Math.min(1, heavyFrac + 0.3)), {
      color: '#f9e2af', weight: 1.5, opacity: 0.6, fillColor: '#f9e2af', fillOpacity: 0.2, dashArray: '4 4'
    }));
    layers.push(L.polygon(mkE(fallout.light.length * lightFrac, fallout.light.width * Math.min(1, lightFrac + 0.2)), {
      color: '#f9e2af', weight: 1, opacity: 0.3, fillColor: '#f9e2af', fillOpacity: 0.06, dashArray: '6 4'
    }));
    this.layer = L.layerGroup(layers).addTo(map);
  },

  playAnimation(map, lat, lng, fallout, windAngle, onUpdate) {
    if (this.animId) cancelAnimationFrame(this.animId);
    let hour = 0.5;
    const tick = () => {
      hour += 0.3;
      if (hour > 48) { this.animId = null; return; }
      this.draw(map, lat, lng, fallout, windAngle, hour);
      if (onUpdate) onUpdate(hour);
      this.animId = requestAnimationFrame(tick);
    };
    this.animId = requestAnimationFrame(tick);
  },

  stopAnimation() {
    if (this.animId) { cancelAnimationFrame(this.animId); this.animId = null; }
  },

  clear(map) {
    this.stopAnimation();
    if (this.layer) { map.removeLayer(this.layer); this.layer = null; }
  }
};

// ---- BLAST WAVE ARRIVAL INDICATOR ----
NM.BlastArrival = {
  active: false, el: null, _handler: null,

  init() {
    this.el = document.getElementById('blast-arrival-indicator') || document.createElement('div');
    this.el.id = 'blast-arrival-indicator';
    this.el.className = 'blast-arrival-indicator';
    if (!this.el.isConnected) (NM.getUiRoot ? NM.getUiRoot() : document.body).appendChild(this.el);
  },

  start(map) {
    if (!this.el) this.init();
    this.active = true;
    this._handler = (e) => {
      if (!this.active || !NM._lastDet) return;
      const det = NM._lastDet;
      const dist = NM.haversine(det.lat, det.lng, e.latlng.lat, e.latlng.lng);
      const arrivalSec = dist / 0.34;
      const psi = NM.Shelter.estimatePsi(det.effects, dist);
      let timeStr;
      if (arrivalSec < 1) timeStr = (arrivalSec * 1000).toFixed(0) + ' ms';
      else if (arrivalSec < 60) timeStr = arrivalSec.toFixed(1) + ' sec';
      else timeStr = (arrivalSec / 60).toFixed(1) + ' min';
      const sevColor = psi >= 20 ? 'var(--red)' : psi >= 5 ? 'var(--peach)' : psi >= 1 ? 'var(--yellow)' : psi >= 0.5 ? 'var(--teal)' : 'var(--green)';
      const severity = psi >= 20 ? 'LETHAL' : psi >= 5 ? 'SEVERE' : psi >= 1 ? 'DAMAGE' : psi >= 0.5 ? 'GLASS' : 'SAFE';
      this.el.innerHTML = `<span class="ba-time">${timeStr}</span> <span class="ba-psi">${psi.toFixed(1)} psi</span> <span class="ba-sev" style="color:${sevColor}">${severity}</span>`;
      this.el.style.display = 'block';
    };
    map.on('mousemove', this._handler);
  },

  stop(map) {
    this.active = false;
    if (this._handler) map.off('mousemove', this._handler);
    if (this.el) this.el.style.display = 'none';
  }
};
