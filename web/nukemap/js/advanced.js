// NukeMap - Advanced Features Module
// "What would I experience here?" mode, attack scenarios, measurement tool,
// missile flight time, firestorm zone, yield comparison chart, nuclear winter,
// draggable GZ, enhanced casualty stats, educational facts
window.NM = window.NM || {};

// ---- "EXPERIENCE HERE" MODE - Click anywhere to see what you'd experience ----
NM.Experience = {
  active: false,
  marker: null,
  popup: null,

  toggle(map) {
    this.active = !this.active;
    if (this.active) {
      map.getContainer().style.cursor = 'help';
    } else {
      map.getContainer().classList.add('crosshair');
      map.getContainer().style.cursor = '';
      if (this.marker) { map.removeLayer(this.marker); this.marker = null; }
    }
    return this.active;
  },

  analyze(map, clickLat, clickLng, det) {
    if (!det) return;
    const dist = NM.haversine(det.lat, det.lng, clickLat, clickLng);
    const e = det.effects;

    // Determine what effects reach this point
    const inFireball = dist <= e.fireball;
    const inPsi200 = dist <= e.psi200;
    const inPsi20 = dist <= e.psi20;
    const inPsi5 = dist <= e.psi5;
    const inPsi1 = dist <= e.psi1;
    const inThermal3 = dist <= e.thermal3;
    const inThermal1 = dist <= e.thermal1;
    const inRad = dist <= e.radiation;
    const inEMP = dist <= e.emp;

    // Estimate overpressure at this distance
    const psi = NM.Shelter.estimatePsi(e, dist);
    const thermal = NM.Shelter.estimateThermalCal(e, dist);

    // Blast wave arrival time
    const arrivalSec = dist / 0.34; // ~340 m/s average

    // Survival assessment
    let survival = 'You would survive with no injuries';
    let survivalColor = 'var(--green)';
    if (inFireball) { survival = 'Instant vaporization. No remains.'; survivalColor = 'var(--red)'; }
    else if (inPsi200) { survival = 'Instant death. Everything obliterated.'; survivalColor = 'var(--red)'; }
    else if (inPsi20) { survival = 'Near-certain death. 98% fatality rate.'; survivalColor = 'var(--red)'; }
    else if (inPsi5) { survival = 'Likely fatal. ~50% die, most buildings collapse.'; survivalColor = 'var(--red)'; }
    else if (inThermal3 && inPsi1) { survival = 'Severe burns + blast injuries. High mortality without shelter.'; survivalColor = 'var(--peach)'; }
    else if (inPsi1) { survival = 'Flying glass shrapnel. Moderate injuries likely. Take cover.'; survivalColor = 'var(--yellow)'; }
    else if (inThermal1) { survival = 'Flash burns on exposed skin. Temporary blindness. Duck and cover.'; survivalColor = 'var(--yellow)'; }
    else if (inEMP) { survival = 'Outside blast range. EMP may disable electronics.'; survivalColor = 'var(--teal)'; }

    let html = `<div class="exp-report">
      <div class="exp-header">
        <div class="exp-dist">${NM.fmtDist(dist)}</div>
        <div class="exp-from">from ground zero</div>
      </div>
      <div class="exp-survival" style="border-color:${survivalColor}">
        <div class="exp-verdict" style="color:${survivalColor}">${survival}</div>
      </div>
      <div class="exp-details">
        <div class="exp-row"><span class="exp-label">Overpressure</span><span class="exp-val">${psi.toFixed(1)} psi</span></div>
        <div class="exp-row"><span class="exp-label">Thermal fluence</span><span class="exp-val">${thermal >= 1 ? thermal.toFixed(1) : thermal.toFixed(2)} cal/cm\u00B2</span></div>
        <div class="exp-row"><span class="exp-label">Blast wave arrives</span><span class="exp-val">${NM.fmtTime(arrivalSec)} after flash</span></div>
        <div class="exp-row"><span class="exp-label">Wind speed</span><span class="exp-val">${psi > 0.5 ? Math.round(psi * 30) + ' mph' : 'Negligible'}</span></div>`;

    if (inRad) html += `<div class="exp-row exp-warn"><span class="exp-label">Radiation</span><span class="exp-val" style="color:var(--green)">Lethal dose (500+ rem)</span></div>`;

    // What to do
    let advice = '';
    if (inPsi20) advice = 'No survival possible in any structure above ground.';
    else if (inPsi5) advice = 'Only reinforced concrete basements offer any protection.';
    else if (inPsi1) advice = 'GET DOWN: Away from windows immediately. Interior room, below window level. Cover head.';
    else if (inThermal1) advice = 'DO NOT LOOK at the fireball. Take cover behind any solid object. Remove burning clothing.';
    else if (inEMP) advice = 'Unplug sensitive electronics. Expect power outages. Monitor emergency broadcasts.';
    else advice = 'You are outside the immediate blast zone. Monitor for fallout if surface burst.';

    if (advice) html += `<div class="exp-advice"><div class="exp-advice-title">What to do</div>${advice}</div>`;
    html += '</div></div>';

    // Place marker and popup
    if (this.marker) map.removeLayer(this.marker);
    const icon = L.divIcon({
      className: '', iconSize: [20, 20], iconAnchor: [10, 10],
      html: '<div style="width:20px;height:20px;border-radius:50%;border:2px solid var(--blue);background:rgba(137,180,250,0.2)"></div>'
    });
    this.marker = L.marker([clickLat, clickLng], {icon}).addTo(map);
    this.marker.bindPopup(html, {maxWidth: 300, className: 'exp-popup'}).openPopup();

    // Draw line from GZ to click point
    const line = L.polyline([[det.lat, det.lng], [clickLat, clickLng]], {
      color: '#89b4fa', weight: 1.5, opacity: 0.5, dashArray: '6 4'
    }).addTo(map);
    // Clean up line after 10 seconds
    setTimeout(() => map.removeLayer(line), 10000);
  }
};

// ---- ATTACK SCENARIO PRESETS ----
NM.Scenarios = [
  {
    name: 'Hiroshima + Nagasaki',
    desc: 'The only nuclear weapons used in warfare',
    dets: [
      {lat:34.3955,lng:132.4534,yield_kt:15,burst:'airburst'},
      {lat:32.7736,lng:129.8616,yield_kt:21,burst:'airburst'},
    ]
  },
  {
    name: 'DC Counter-Value',
    desc: '3 warheads on Washington DC metro area',
    dets: [
      {lat:38.8977,lng:-77.037,yield_kt:800,burst:'airburst'},  // White House
      {lat:38.8719,lng:-77.056,yield_kt:455,burst:'airburst'},   // Pentagon
      {lat:39.0481,lng:-77.473,yield_kt:300,burst:'airburst'},   // Reston/CIA area
    ]
  },
  {
    name: 'NYC Full Strike',
    desc: '5 warheads targeting Manhattan and boroughs',
    dets: [
      {lat:40.758,lng:-73.9855,yield_kt:800,burst:'airburst'},   // Midtown
      {lat:40.7074,lng:-74.011,yield_kt:455,burst:'airburst'},    // Wall St
      {lat:40.6892,lng:-73.982,yield_kt:300,burst:'airburst'},    // Brooklyn
      {lat:40.7831,lng:-73.9712,yield_kt:300,burst:'airburst'},   // Upper East
      {lat:40.6413,lng:-74.0781,yield_kt:150,burst:'surface'},    // Port/industrial
    ]
  },
  {
    name: 'Moscow Strike',
    desc: '4 warheads on Moscow targets',
    dets: [
      {lat:55.752,lng:37.6175,yield_kt:455,burst:'airburst'},    // Kremlin
      {lat:55.8,lng:37.5,yield_kt:800,burst:'airburst'},         // North Moscow
      {lat:55.7,lng:37.75,yield_kt:300,burst:'airburst'},        // East Moscow
      {lat:55.65,lng:37.55,yield_kt:300,burst:'surface'},        // South industrial
    ]
  },
  {
    name: 'US ICBM Fields',
    desc: 'Counter-force strike on Minuteman III silos',
    dets: [
      {lat:47.505,lng:-111.183,yield_kt:800,burst:'surface'},    // Malmstrom
      {lat:48.416,lng:-101.331,yield_kt:800,burst:'surface'},    // Minot
      {lat:41.145,lng:-104.862,yield_kt:800,burst:'surface'},    // F.E. Warren
    ]
  },
  {
    name: 'Limited Exchange',
    desc: 'Tit-for-tat: 1 warhead each on DC and Moscow',
    dets: [
      {lat:38.8977,lng:-77.037,yield_kt:800,burst:'airburst'},
      {lat:55.752,lng:37.6175,yield_kt:800,burst:'airburst'},
    ]
  },
  {
    name: 'London Strike',
    desc: '3 warheads targeting central London',
    dets: [
      {lat:51.5014,lng:-0.1419,yield_kt:800,burst:'airburst'},  // Buckingham Palace
      {lat:51.5155,lng:-0.0922,yield_kt:455,burst:'airburst'},   // City of London
      {lat:51.4775,lng:-0.0014,yield_kt:300,burst:'surface'},    // Canary Wharf
    ]
  },
  {
    name: 'Beijing Strike',
    desc: '3 warheads on Chinese capital',
    dets: [
      {lat:39.9042,lng:116.3974,yield_kt:455,burst:'airburst'},  // Forbidden City
      {lat:39.9554,lng:116.3976,yield_kt:300,burst:'airburst'},   // Olympic area
      {lat:39.8665,lng:116.3658,yield_kt:300,burst:'surface'},    // South Beijing
    ]
  },
  {
    name: 'Tel Aviv + Tehran',
    desc: 'Middle East exchange scenario',
    dets: [
      {lat:32.0853,lng:34.7818,yield_kt:200,burst:'airburst'},   // Tel Aviv
      {lat:35.6892,lng:51.389,yield_kt:250,burst:'airburst'},     // Tehran
    ]
  },
  {
    name: 'Korean Peninsula',
    desc: 'DPRK strikes Seoul, US retaliates on Pyongyang',
    dets: [
      {lat:37.5665,lng:126.978,yield_kt:250,burst:'airburst'},    // Seoul
      {lat:39.0392,lng:125.763,yield_kt:455,burst:'airburst'},     // Pyongyang
      {lat:39.0319,lng:125.754,yield_kt:100,burst:'surface'},      // Pyongyang military
    ]
  },
  {
    name: 'US West Coast',
    desc: 'Strikes on LA, SF, and Seattle',
    dets: [
      {lat:34.0522,lng:-118.244,yield_kt:800,burst:'airburst'},
      {lat:37.7749,lng:-122.419,yield_kt:455,burst:'airburst'},
      {lat:47.6062,lng:-122.332,yield_kt:300,burst:'airburst'},
    ]
  },
];

// ---- MEASUREMENT TOOL ----
NM.Measure = {
  active: false,
  points: [],
  layers: [],

  toggle(map) {
    this.active = !this.active;
    if (!this.active) this.clear(map);
    return this.active;
  },

  addPoint(map, lat, lng) {
    this.points.push([lat, lng]);

    const icon = L.divIcon({
      className: '', iconSize: [12, 12], iconAnchor: [6, 6],
      html: `<div style="width:12px;height:12px;border-radius:50%;background:var(--blue);border:2px solid var(--text);box-shadow:0 0 6px rgba(0,0,0,0.4)"></div>`
    });
    const m = L.marker([lat, lng], {icon}).addTo(map);
    this.layers.push(m);

    if (this.points.length >= 2) {
      const [p1, p2] = [this.points[this.points.length - 2], this.points[this.points.length - 1]];
      const dist = NM.haversine(p1[0], p1[1], p2[0], p2[1]);

      const line = L.polyline([p1, p2], {color: '#89b4fa', weight: 2, opacity: 0.8}).addTo(map);
      this.layers.push(line);

      // Distance label at midpoint
      const midLat = (p1[0] + p2[0]) / 2, midLng = (p1[1] + p2[1]) / 2;
      const label = L.divIcon({
        className: 'measure-label',
        html: `<div class="ml-tag">${NM.fmtDist(dist)}</div>`,
        iconSize: [0, 0], iconAnchor: [0, 10]
      });
      const lm = L.marker([midLat, midLng], {icon: label, interactive: false}).addTo(map);
      this.layers.push(lm);
    }
  },

  clear(map) {
    this.layers.forEach(l => map.removeLayer(l));
    this.layers = [];
    this.points = [];
  }
};

// ---- MISSILE FLIGHT TIME CALCULATOR ----
NM.MissileFlight = {
  // ICBM typical speed: ~7 km/s, total flight ~30 min for intercontinental
  // SLBM: ~25-12 min depending on range
  // Tactical: varies widely

  calculate(fromLat, fromLng, toLat, toLng, missileType) {
    const dist = NM.haversine(fromLat, fromLng, toLat, toLng);
    let speed, name, maxRange;

    switch (missileType) {
      case 'icbm':
        speed = 7; name = 'ICBM'; maxRange = 13000;
        break;
      case 'slbm':
        speed = 6.5; name = 'SLBM'; maxRange = 12000;
        break;
      case 'irbm':
        speed = 4; name = 'IRBM'; maxRange = 5500;
        break;
      case 'srbm':
        speed = 2; name = 'SRBM'; maxRange = 1000;
        break;
      default:
        speed = 7; name = 'ICBM'; maxRange = 13000;
    }

    if (dist > maxRange) return null;

    // Simplified: boost phase ~3 min, midcourse ~majority, terminal ~1 min
    const boostTime = 180; // seconds
    const terminalTime = 60;
    const midcourseDist = Math.max(0, dist - 200); // km after boost/before terminal
    const midcourseTime = midcourseDist / speed;
    const totalTime = boostTime + midcourseTime + terminalTime;
    const apogee = missileType === 'icbm' ? Math.min(1200, dist * 0.09) : Math.min(600, dist * 0.06);

    return {
      distance: dist,
      totalSeconds: totalTime,
      totalMinutes: totalTime / 60,
      apogeeKm: apogee,
      missileType: name,
      boostSec: boostTime,
      midcourseSec: midcourseTime,
      terminalSec: terminalTime,
      inRange: dist <= maxRange
    };
  },

  generateHTML(result) {
    if (!result) return '<div style="color:var(--red);font-size:11px">Target out of range for this missile type</div>';
    return `<div class="flight-result">
      <div class="flight-row"><span class="fl-label">Missile Type</span><span class="fl-val">${result.missileType}</span></div>
      <div class="flight-row"><span class="fl-label">Distance</span><span class="fl-val">${NM.fmtDist(result.distance)}</span></div>
      <div class="flight-row flight-main"><span class="fl-label">Total Flight Time</span><span class="fl-val fl-time">${result.totalMinutes.toFixed(1)} min</span></div>
      <div class="flight-phases">
        <div class="fl-phase"><div class="fl-bar" style="width:${(result.boostSec/result.totalSeconds*100)}%;background:var(--peach)"></div><span>Boost ${(result.boostSec/60).toFixed(1)}m</span></div>
        <div class="fl-phase"><div class="fl-bar" style="width:${(result.midcourseSec/result.totalSeconds*100)}%;background:var(--blue)"></div><span>Midcourse ${(result.midcourseSec/60).toFixed(1)}m</span></div>
        <div class="fl-phase"><div class="fl-bar" style="width:${(result.terminalSec/result.totalSeconds*100)}%;background:var(--red)"></div><span>Terminal ${(result.terminalSec/60).toFixed(1)}m</span></div>
      </div>
      <div class="flight-row"><span class="fl-label">Apogee</span><span class="fl-val">${result.apogeeKm.toFixed(0)} km altitude</span></div>
      <div class="flight-row"><span class="fl-label">Warning Time</span><span class="fl-val" style="color:var(--red)">${(result.totalMinutes - 3).toFixed(0)} min after detection</span></div>
    </div>`;
  }
};

// ---- FIRESTORM PROBABILITY ----
NM.Firestorm = {
  // Based on thermal fluence + population density
  // Firestorms require: >10 cal/cm2 thermal, sufficient fuel loading (urban area)
  calcZone(effects) {
    // Firestorm likely within area receiving 10+ cal/cm2
    // Roughly between psi5 and thermal3 zones in urban areas
    const firestormR = effects.thermal3 * 0.85; // slightly inside 3rd degree zone
    return firestormR;
  }
};

// ---- YIELD COMPARISON CHART (CSS-based bars) ----
NM.YieldChart = {
  generate(currentYieldKt) {
    const weapons = [
      {name:'Davy Crockett',kt:0.02},{name:'Hiroshima',kt:15},{name:'W76-1',kt:100},
      {name:'W88',kt:455},{name:'B83',kt:1200},{name:'Castle Bravo',kt:15000},
      {name:'Tsar Bomba',kt:50000},
    ];

    // Add current weapon if not in list
    const current = {name: 'Current', kt: currentYieldKt, current: true};
    const all = [...weapons, current].sort((a, b) => a.kt - b.kt);
    const maxKt = Math.max(...all.map(w => w.kt));
    const maxLog = Math.log10(maxKt);
    const minLog = Math.log10(Math.max(0.001, Math.min(...all.map(w => w.kt))));

    let html = '<div class="yield-chart">';
    for (const w of all) {
      const logW = Math.log10(Math.max(0.001, w.kt));
      const pct = Math.max(2, ((logW - minLog) / (maxLog - minLog)) * 100);
      const isCurrent = w.current;
      html += `<div class="yc-row${isCurrent ? ' yc-current' : ''}">
        <span class="yc-name">${w.name}</span>
        <div class="yc-bar-wrap"><div class="yc-bar" style="width:${pct}%"></div></div>
        <span class="yc-yield">${NM.fmtYield(w.kt)}</span>
      </div>`;
    }
    html += '</div>';
    return html;
  }
};

// ---- NUCLEAR WINTER ESTIMATES ----
NM.NuclearWinter = {
  // Soot injection model (simplified from Toon et al. 2008)
  estimate(totalYieldMT, numDets, isUrban) {
    // Each MT on a city generates ~5 Tg of soot (very rough)
    // 150 Tg soot = full nuclear winter (~10C global cooling)
    const sootPerMT = isUrban ? 5 : 0.5; // Tg per MT
    const totalSoot = totalYieldMT * sootPerMT;

    // Temperature drop (simplified from multiple studies)
    const tempDrop = Math.min(15, totalSoot * 0.07); // ~0.07 C per Tg
    const growingSeasonLoss = Math.min(90, tempDrop * 6); // days lost

    return {
      sootTg: totalSoot,
      tempDropC: tempDrop,
      tempDropF: tempDrop * 1.8,
      growingSeasonLossDays: growingSeasonLoss,
      uvIncreasePct: Math.min(80, totalSoot * 0.5),
      ozoneDepletionPct: Math.min(70, totalSoot * 0.4),
      severity: totalSoot < 5 ? 'Negligible' : totalSoot < 20 ? 'Minor cooling' : totalSoot < 50 ? 'Significant cooling' : totalSoot < 100 ? 'Nuclear autumn' : 'Nuclear winter'
    };
  },

  generateHTML(totalYieldKt, numDets) {
    const totalMT = totalYieldKt / 1000;
    const est = this.estimate(totalMT, numDets, true);

    return `<div class="nw-panel">
      <div class="nw-row"><span class="nw-label">Total yield</span><span class="nw-val">${NM.fmtYield(totalYieldKt)}</span></div>
      <div class="nw-row"><span class="nw-label">Soot injected</span><span class="nw-val">${est.sootTg.toFixed(1)} Tg</span></div>
      <div class="nw-row nw-main"><span class="nw-label">Global cooling</span><span class="nw-val nw-temp">-${est.tempDropC.toFixed(1)}\u00B0C / -${est.tempDropF.toFixed(1)}\u00B0F</span></div>
      <div class="nw-row"><span class="nw-label">Growing season lost</span><span class="nw-val">${est.growingSeasonLossDays.toFixed(0)} days</span></div>
      <div class="nw-row"><span class="nw-label">UV increase</span><span class="nw-val">+${est.uvIncreasePct.toFixed(0)}%</span></div>
      <div class="nw-row"><span class="nw-label">Ozone depletion</span><span class="nw-val">${est.ozoneDepletionPct.toFixed(0)}%</span></div>
      <div class="nw-severity" style="color:${est.sootTg > 50 ? 'var(--red)' : est.sootTg > 20 ? 'var(--peach)' : 'var(--green)'}">${est.severity}</div>
      <div class="nw-note">Based on Toon et al. (2008) soot injection model. Assumes urban targets.</div>
    </div>`;
  }
};

// ---- EDUCATIONAL NUCLEAR FACTS ----
NM.Facts = [
  "The Hiroshima bomb had a yield of only 15 kilotons \u2014 smaller than many tactical weapons today.",
  "A single modern W88 warhead (455 kT) is 30x more powerful than Hiroshima.",
  "The Tsar Bomba's shockwave circled the Earth three times.",
  "Nuclear fireballs briefly outshine the Sun. Looking at one can cause permanent blindness at 50+ miles.",
  "At 5 psi overpressure, wind speeds reach 160 mph \u2014 enough to collapse most buildings.",
  "The 7:10 rule: for every 7-fold increase in time after detonation, radiation drops 10-fold.",
  "A 1 MT surface burst creates a crater ~300 feet deep and 1,000 feet wide.",
  "EMP from a single high-altitude burst could disable electronics across an entire continent.",
  "Castle Bravo (1954) yielded 15 MT \u2014 2.5x its expected yield, contaminating 7,000 sq miles.",
  "The US once had over 31,000 nuclear warheads (peak in 1967). Russia peaked at ~45,000.",
  "A nuclear fireball rises at ~300 mph, reaching full mushroom cloud height in ~10 minutes.",
  "3rd degree burns from a 1 MT blast extend to ~7 miles from ground zero.",
  "The shortest ICBM flight time between the US and Russia is approximately 30 minutes.",
  "Fallout from a surface burst can travel hundreds of miles downwind in 24 hours.",
  "A single Trident submarine carries ~90 warheads \u2014 enough to destroy any country.",
  "Nuclear winter from a full US-Russia exchange could drop global temperatures 10\u00B0C for years.",
  "The initial radiation pulse from a nuclear weapon lasts only about 1 minute.",
  "At 20 psi, even reinforced concrete structures are destroyed. Only deep bunkers survive.",
  "Prompt radiation (neutrons and gamma rays) is the main killer within 1-2 km of small weapons.",
  "The mushroom cloud from Tsar Bomba rose to 64 km \u2014 above 99.5% of Earth's atmosphere.",
];

// ---- BUILDING DAMAGE AT PSI LEVELS ----
NM.BuildingDamage = {
  generate(yieldKt) {
    const levels = [
      {psi:0.5, r:NM.CustomPsi.calcRadius(yieldKt, 0.5), title:'0.5 psi', color:'var(--teal)',
        items:['Windows crack and may shatter','Light objects displaced','Doors blown open','Minor plaster damage']},
      {psi:1, r:NM.CustomPsi.calcRadius(yieldKt, 1), title:'1 psi', color:'var(--yellow)',
        items:['All glass windows shatter into lethal shrapnel','Roof tiles and shingles torn off','Wood-frame walls crack','Interior partitions damaged','Power lines downed']},
      {psi:3, r:NM.CustomPsi.calcRadius(yieldKt, 3), title:'3 psi', color:'var(--peach)',
        items:['Wood-frame houses collapse','Brick veneer walls fail','Factory-type steel frames distorted','Telephone poles snapped','Vehicles overturned','Residential area fires widespread']},
      {psi:5, r:NM.CustomPsi.calcRadius(yieldKt, 5), title:'5 psi', color:'var(--red)',
        items:['Most commercial buildings destroyed','Highway bridges damaged','Underground pipes ruptured','Railroad tracks buckled','Firestorm probable in urban areas','Residential area: total destruction']},
      {psi:10, r:NM.CustomPsi.calcRadius(yieldKt, 10), title:'10 psi', color:'var(--maroon)',
        items:['Reinforced concrete severely damaged','Steel-frame buildings collapse','Underground shelters threatened','Vehicles thrown and crushed','No standing structures above ground']},
      {psi:20, r:NM.CustomPsi.calcRadius(yieldKt, 20), title:'20 psi', color:'var(--red)',
        items:['Reinforced concrete destroyed','Hardened military structures damaged','Everything above ground obliterated','Crater formation begins','Only deep underground bunkers survive']},
    ];

    let html = '<div class="bldg-list">';
    for (const lv of levels) {
      html += `<div class="bldg-item"><div class="bldg-header" style="color:${lv.color}"><span class="bldg-psi">${lv.title}</span><span class="bldg-dist">${NM.fmtR(lv.r)}</span></div><ul class="bldg-effects">`;
      for (const item of lv.items) html += `<li>${item}</li>`;
      html += '</ul></div>';
    }
    html += '</div>';
    return html;
  }
};

// ---- EMERGENCY ACTION GUIDE ----
NM.EmergencyGuide = {
  generate(det) {
    const e = det.effects;
    const hasFallout = !!e.fallout;
    const items = [
      {title:'Immediate: Flash', body:'DO NOT look toward the blast. The thermal flash causes temporary or permanent blindness. Duck behind any solid cover. Close your eyes and cover them.', color:'var(--red)', always:true},
      {title:'0-10 seconds: Take Cover', body:'GET DOWN immediately. Lie flat face-down, away from windows. Cover head and neck. The blast wave arrives seconds after the flash \u2014 flying glass is the #1 cause of blast injuries.', color:'var(--peach)', always:true},
      {title:'10 sec - 2 min: Stay Down', body:'Remain in cover until the blast wave passes and reverses. Debris continues falling. Do not move until shaking stops completely.', color:'var(--yellow)', always:true},
      {title:'2 - 10 min: Assess & Move', body:'If your building is damaged, move to a more substantial structure. Go to a basement or interior room. Put as many walls between you and the outside as possible. Brick/concrete reduces radiation 10-100x.', color:'var(--teal)', always:true},
      {title:'10 min - 1 hr: Shelter In Place', body:hasFallout ? `Fallout begins ~10 min after a surface burst. Visible as ash/dust. Do NOT go outside. Seal windows, turn off ventilation. The first hour is the most dangerous \u2014 radiation levels are 1000x higher than at 48 hours.` : 'Airburst produces minimal fallout. Primary danger is from fires and structural collapse. If safe to move, evacuate away from fires.', color:'var(--blue)', always:true},
      {title:'1 - 48 hr: Stay Sheltered', body:hasFallout ? `7:10 Rule: Every 7x increase in time = 10x decrease in radiation. At 49 hours, radiation is 1/100th of the 1-hour level. Stay sheltered for at least 24 hours, ideally 48-72 hours. Ration water and food.` : 'Monitor emergency broadcasts. Assist injured if safe. Do not approach ground zero \u2014 fires may burn for days.', color:'var(--mauve)', always:hasFallout},
      {title:'Supplies to Have Ready', body:'Water (1 gal/person/day for 3 days), non-perishable food, battery radio, flashlight, first aid kit, dust masks or cloth, plastic sheeting and duct tape, medications.', color:'var(--green)', always:true},
    ];

    let html = '<div class="guide-list">';
    for (const it of items) {
      if (!it.always && !hasFallout) continue;
      html += `<div class="guide-item" style="border-left-color:${it.color}"><div class="gi-title" style="color:${it.color}">${it.title}</div><div class="gi-body">${it.body}</div></div>`;
    }
    html += '</div>';
    return html;
  }
};
