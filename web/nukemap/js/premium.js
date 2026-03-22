// NukeMap - Premium Features Module
// Draggable GZ, per-zone casualties, EMP details, destruction stats,
// weapon info cards, altitude cross-section, export PNG, warhead arc,
// survival calculator, historic test timeline
window.NM = window.NM || {};

// ---- DRAGGABLE GROUND ZERO ----
NM.DraggableGZ = {
  enabled: false,
  marker: null,

  enable(map, det, redrawFn) {
    this.enabled = true;
    // Replace the GZ marker with a draggable one
    const icon = L.divIcon({
      className: '', iconSize: [32, 32], iconAnchor: [16, 16],
      html: '<div class="gz-marker gz-draggable"><div class="gz-outer"></div><div class="gz-inner"></div><div class="gz-drag-hint">DRAG</div></div>'
    });
    if (this.marker) map.removeLayer(this.marker);
    this.marker = L.marker([det.lat, det.lng], {icon, draggable: true}).addTo(map);
    this.marker.on('dragend', (e) => {
      const pos = e.target.getLatLng();
      redrawFn(pos.lat, pos.lng);
    });
  },

  disable(map) {
    this.enabled = false;
    if (this.marker) { map.removeLayer(this.marker); this.marker = null; }
  }
};

// ---- PER-ZONE CASUALTY BREAKDOWN ----
NM.ZoneCasualties = {
  generate(effects, density) {
    const zones = [
      {name: 'Fireball', r: effects.fireball, color: '#f5e0dc', dfrac: 1.0, ifrac: 0},
      {name: '200 psi', r: effects.psi200, color: '#89dceb', dfrac: 0.98, ifrac: 0.02},
      {name: '20 psi', r: effects.psi20, color: '#89b4fa', dfrac: 0.90, ifrac: 0.08},
      {name: '5 psi', r: effects.psi5, color: '#cba6f7', dfrac: 0.50, ifrac: 0.40},
      {name: '3rd\u00B0 Burns', r: effects.thermal3, color: '#fab387', dfrac: 0.25, ifrac: 0.40},
      {name: '1 psi', r: effects.psi1, color: '#f9e2af', dfrac: 0.05, ifrac: 0.30},
      {name: '1st\u00B0 Burns', r: effects.thermal1, color: '#f5c2e7', dfrac: 0.01, ifrac: 0.15},
    ].filter(z => z.r > 0.001);

    let html = '<div class="zone-table"><div class="zt-row zt-head"><span>Zone</span><span>Area</span><span>Fatalities</span><span>Injuries</span></div>';
    let prevArea = 0, totalD = 0, totalI = 0;
    for (const z of zones) {
      const area = Math.PI * z.r * z.r;
      const ring = Math.max(0, area - prevArea);
      const deaths = Math.round(ring * density * z.dfrac);
      const injuries = Math.round(ring * density * z.ifrac);
      totalD += deaths; totalI += injuries;
      html += `<div class="zt-row"><span style="color:${z.color};font-weight:700">${z.name}</span><span>${NM.fmtArea(z.r)}</span><span class="zt-d">${NM.fmtNum(deaths)}</span><span class="zt-i">${NM.fmtNum(injuries)}</span></div>`;
      prevArea = area;
    }
    html += `<div class="zt-row zt-total"><span>Total</span><span></span><span class="zt-d">${NM.fmtNum(totalD)}</span><span class="zt-i">${NM.fmtNum(totalI)}</span></div></div>`;
    return html;
  }
};

// ---- EMP DETAILED EFFECTS ----
NM.EMPDetails = {
  generate(empRadius) {
    const items = [
      {dist: 0.1, name: 'Computers & servers', effect: 'Permanent damage to all unshielded electronics', icon: 'computer'},
      {dist: 0.2, name: 'Smartphones & radios', effect: 'Circuits burned out, permanent failure', icon: 'phone'},
      {dist: 0.3, name: 'Vehicle electronics', effect: 'Engine control units fail, vehicles stall', icon: 'car'},
      {dist: 0.4, name: 'Power grid transformers', effect: 'High-voltage transformers destroyed, months to replace', icon: 'power'},
      {dist: 0.5, name: 'Hospital equipment', effect: 'Life support, ventilators, monitoring fails', icon: 'hospital'},
      {dist: 0.6, name: 'Water treatment', effect: 'Pumps and control systems disabled', icon: 'water'},
      {dist: 0.7, name: 'Communication towers', effect: 'Cell towers, internet backbone down', icon: 'tower'},
      {dist: 0.8, name: 'Traffic systems', effect: 'All traffic lights, rail signals fail', icon: 'traffic'},
      {dist: 0.9, name: 'Aircraft electronics', effect: 'Avionics disrupted, navigation lost', icon: 'plane'},
      {dist: 1.0, name: 'Peripheral electronics', effect: 'Sensitive devices may be damaged or disrupted', icon: 'misc'},
    ];

    let html = '<div class="emp-list">';
    for (const item of items) {
      const r = empRadius * item.dist;
      const status = item.dist < 0.5 ? 'Destroyed' : item.dist < 0.8 ? 'Severe damage' : 'Disrupted';
      const statusColor = item.dist < 0.5 ? 'var(--red)' : item.dist < 0.8 ? 'var(--peach)' : 'var(--yellow)';
      html += `<div class="emp-item">
        <div class="emp-name">${item.name}</div>
        <div class="emp-effect">${item.effect}</div>
        <div class="emp-range">Within ${NM.fmtR(r)} <span style="color:${statusColor};font-weight:700">${status}</span></div>
      </div>`;
    }
    html += `<div class="emp-note">Total EMP radius: ${NM.fmtDist(empRadius)}. Faraday cages protect electronics.</div></div>`;
    return html;
  }
};

// ---- DESTRUCTION AREA STATISTICS ----
NM.DestructionStats = {
  generate(effects, casualties) {
    const totalDestroyed = Math.PI * effects.psi5 * effects.psi5; // km^2, 5 psi = most buildings destroyed
    const heavyDamage = Math.PI * effects.psi20 * effects.psi20;
    const moderateDamage = Math.PI * effects.psi1 * effects.psi1;
    const burnArea = Math.PI * effects.thermal3 * effects.thermal3;
    const totalAffected = Math.PI * Math.max(effects.psi1, effects.thermal1) ** 2;

    // Rough estimates: urban area has ~2000 buildings/km2, 1 hospital per 30,000 people
    const buildingsDestroyed = Math.round(totalDestroyed * 2000);
    const buildingsDamaged = Math.round((moderateDamage - totalDestroyed) * 800);
    const hospitalsAffected = Math.round((casualties.deaths + casualties.injuries) / 30000);

    return `<div class="ds-grid">
      <div class="ds-card"><div class="ds-val" style="color:var(--red)">${totalDestroyed.toFixed(1)} km\u00B2</div><div class="ds-label">Total destruction (5+ psi)</div></div>
      <div class="ds-card"><div class="ds-val" style="color:var(--peach)">${moderateDamage.toFixed(1)} km\u00B2</div><div class="ds-label">Damage zone (1+ psi)</div></div>
      <div class="ds-card"><div class="ds-val" style="color:var(--yellow)">${burnArea.toFixed(1)} km\u00B2</div><div class="ds-label">Fire/burn zone</div></div>
      <div class="ds-card"><div class="ds-val" style="color:var(--text)">${totalAffected.toFixed(0)} km\u00B2</div><div class="ds-label">Total affected area</div></div>
      <div class="ds-card"><div class="ds-val" style="color:var(--blue)">${NM.fmtNum(buildingsDestroyed)}</div><div class="ds-label">Est. buildings destroyed</div></div>
      <div class="ds-card"><div class="ds-val" style="color:var(--mauve)">${NM.fmtNum(buildingsDamaged)}</div><div class="ds-label">Est. buildings damaged</div></div>
      <div class="ds-card"><div class="ds-val" style="color:var(--maroon)">${hospitalsAffected}</div><div class="ds-label">Hospitals overwhelmed</div></div>
      <div class="ds-card"><div class="ds-val" style="color:var(--flamingo)">${(totalDestroyed * 0.386).toFixed(1)} mi\u00B2</div><div class="ds-label">Destruction (sq miles)</div></div>
    </div>`;
  }
};

// ---- WEAPON INFO CARDS ----
NM.WeaponInfo = {
  specs: {
    'Little Boy (Hiroshima)': {type:'Gun-type fission',fuel:'Uranium-235',weight:'4,400 kg',length:'3 m',diameter:'0.71 m',deployed:'B-29 Superfortress',note:'First weapon used in combat. 64 kg of U-235, only ~1 kg fissioned.'},
    'Fat Man (Nagasaki)': {type:'Implosion fission',fuel:'Plutonium-239',weight:'4,670 kg',length:'3.25 m',diameter:'1.52 m',deployed:'B-29 Superfortress',note:'Implosion design using explosive lenses. More efficient than Little Boy.'},
    'W88 (Trident II)': {type:'Thermonuclear',fuel:'Plutonium + Lithium deuteride',weight:'~360 kg',length:'~1.75 m',diameter:'~0.55 m',deployed:'Trident II D5 SLBM',note:'Most powerful US SLBM warhead. 5 per missile, 24 missiles per Ohio-class sub.'},
    'B83-1': {type:'Thermonuclear',fuel:'Classified',weight:'1,100 kg',length:'3.67 m',diameter:'0.46 m',deployed:'B-2 Spirit, B-52',note:'Largest weapon in active US inventory. Variable yield up to 1.2 MT.'},
    'Tsar Bomba (50 MT)': {type:'Three-stage thermonuclear',fuel:'Lithium deuteride',weight:'27,000 kg',length:'8 m',diameter:'2.1 m',deployed:'Tu-95V bomber',note:'Largest detonation in history. Shockwave circled Earth 3x. Mushroom cloud rose 64 km.'},
    'RS-28 Sarmat': {type:'Thermonuclear MIRV',fuel:'Liquid (UDMH/N2O4)',weight:'208,100 kg',length:'35.5 m',diameter:'3 m',deployed:'Silo-based ICBM',note:'Replaces SS-18 Satan. Can carry 10-15 MIRV warheads or Avangard HGV. Range: 18,000 km.'},
  },

  generate(weaponName) {
    const info = this.specs[weaponName];
    if (!info) return '';
    let html = '<div class="wi-card">';
    const rows = [['Type', info.type], ['Fuel', info.fuel], ['Weight', info.weight], ['Dimensions', `${info.length} x ${info.diameter}`], ['Delivery', info.deployed]];
    for (const [label, val] of rows) {
      html += `<div class="wi-row"><span class="wi-label">${label}</span><span class="wi-val">${val}</span></div>`;
    }
    if (info.note) html += `<div class="wi-note">${info.note}</div>`;
    html += '</div>';
    return html;
  }
};

// ---- ALTITUDE CROSS-SECTION (SVG) ----
NM.AltitudeProfile = {
  generate(effects, yieldKt) {
    const cloudTop = effects.cloudTopH;
    const cloudR = effects.cloudTopR;
    const stemR = effects.stemR;
    const burstH = effects.burstHeight / 1000; // to km
    const fireR = effects.fireball;
    const maxH = Math.max(cloudTop * 1.3, 20);
    const maxW = Math.max(effects.psi1 * 1.2, cloudR * 3, 10);

    // SVG coordinates: width=300, height=200, origin at bottom center
    const W = 300, H = 180;
    const sx = (km) => 150 + (km / maxW) * 140; // x scale
    const sy = (km) => H - (km / maxH) * 160;    // y scale (inverted)

    let svg = `<svg viewBox="0 0 ${W} ${H}" class="alt-svg">`;

    // Ground line
    svg += `<line x1="0" y1="${sy(0)}" x2="${W}" y2="${sy(0)}" stroke="var(--surface1)" stroke-width="1"/>`;

    // Altitude grid
    for (let alt = 5; alt < maxH; alt += maxH > 50 ? 20 : maxH > 20 ? 10 : 5) {
      const y = sy(alt);
      svg += `<line x1="0" y1="${y}" x2="${W}" y2="${y}" stroke="var(--surface0)" stroke-width="0.5" stroke-dasharray="3 4"/>`;
      svg += `<text x="4" y="${y - 2}" fill="var(--overlay0)" font-size="7">${alt} km</text>`;
    }

    // Fireball (circle at burst height)
    const fbCx = sx(0), fbCy = sy(burstH);
    const fbR = Math.max(3, (fireR / maxW) * 140);
    svg += `<circle cx="${fbCx}" cy="${fbCy}" r="${fbR}" fill="rgba(245,224,220,0.5)" stroke="#f5e0dc" stroke-width="1"/>`;

    // Stem
    const stemW = Math.max(4, (stemR / maxW) * 140 * 2);
    svg += `<rect x="${sx(0) - stemW/2}" y="${sy(cloudTop * 0.7)}" width="${stemW}" height="${sy(burstH) - sy(cloudTop * 0.7)}" fill="rgba(139,115,85,0.3)" rx="2"/>`;

    // Mushroom cap
    const capCx = sx(0), capCy = sy(cloudTop);
    const capRx = Math.max(10, (cloudR / maxW) * 140);
    const capRy = Math.max(6, capRx * 0.5);
    svg += `<ellipse cx="${capCx}" cy="${capCy}" rx="${capRx}" ry="${capRy}" fill="rgba(238,136,68,0.4)" stroke="#ee8844" stroke-width="1"/>`;

    // Labels
    svg += `<text x="${sx(0) + capRx + 4}" y="${capCy + 3}" fill="var(--peach)" font-size="8" font-weight="700">${cloudTop.toFixed(1)} km</text>`;
    svg += `<text x="${sx(0) + fbR + 4}" y="${fbCy + 3}" fill="var(--rosewater)" font-size="7">Fireball</text>`;

    // 5 psi radius markers on ground
    const psi5x = sx(effects.psi5);
    if (psi5x < W - 10) {
      svg += `<line x1="${psi5x}" y1="${sy(0) - 3}" x2="${psi5x}" y2="${sy(0) + 3}" stroke="var(--mauve)" stroke-width="1.5"/>`;
      svg += `<text x="${psi5x}" y="${sy(0) + 12}" fill="var(--mauve)" font-size="7" text-anchor="middle">5 psi</text>`;
    }
    const psi1x = sx(effects.psi1);
    if (psi1x < W - 10) {
      svg += `<line x1="${psi1x}" y1="${sy(0) - 3}" x2="${psi1x}" y2="${sy(0) + 3}" stroke="var(--yellow)" stroke-width="1.5"/>`;
      svg += `<text x="${psi1x}" y="${sy(0) + 12}" fill="var(--yellow)" font-size="7" text-anchor="middle">1 psi</text>`;
    }

    // Burst height indicator
    if (burstH > 0.1) {
      svg += `<line x1="${sx(0)}" y1="${sy(0)}" x2="${sx(0)}" y2="${fbCy}" stroke="var(--overlay0)" stroke-width="0.5" stroke-dasharray="2 3"/>`;
      svg += `<text x="${sx(0) + 4}" y="${sy(burstH / 2)}" fill="var(--overlay0)" font-size="7">HOB: ${(burstH * 1000).toFixed(0)}m</text>`;
    }

    svg += '</svg>';
    return svg;
  }
};

// ---- SURVIVAL PROBABILITY AT DISTANCE ----
NM.SurvivalCalc = {
  calculate(effects, distKm) {
    const psi = NM.Shelter.estimatePsi(effects, distKm);
    const thermal = NM.Shelter.estimateThermalCal(effects, distKm);
    const inRad = distKm <= effects.radiation;

    // Probability in open air
    let openSurvival = 1;
    if (psi >= 200) openSurvival = 0;
    else if (psi >= 20) openSurvival = 0.02;
    else if (psi >= 5) openSurvival = Math.max(0, 0.5 - (psi - 5) / 30);
    else if (psi >= 1) openSurvival = Math.max(0.5, 1 - psi * 0.12);
    else openSurvival = Math.max(0.8, 1 - psi * 0.05);

    if (thermal >= 8) openSurvival *= 0.3;
    else if (thermal >= 2) openSurvival *= 0.7;
    if (inRad) openSurvival *= 0.2;

    // In basement
    let basementSurvival = 1;
    if (psi >= 15) basementSurvival = 0.1;
    else if (psi >= 5) basementSurvival = 0.5;
    else basementSurvival = 0.95;
    if (inRad) basementSurvival *= 0.8;

    return {
      openAir: Math.round(Math.max(0, Math.min(1, openSurvival)) * 100),
      basement: Math.round(Math.max(0, Math.min(1, basementSurvival)) * 100),
      psi, thermal, inRadiation: inRad,
      blastArrival: distKm / 0.34
    };
  },

  generateHTML(effects) {
    const distances = [1, 2, 3, 5, 8, 10, 15, 20, 30, 50];
    let html = '<div class="surv-table"><div class="surv-row surv-head"><span>Distance</span><span>Open Air</span><span>Basement</span><span>Overpressure</span></div>';
    for (const d of distances) {
      const r = this.calculate(effects, d);
      const openClass = r.openAir >= 80 ? 'safe' : r.openAir >= 30 ? 'risk' : 'dead';
      const baseClass = r.basement >= 80 ? 'safe' : r.basement >= 30 ? 'risk' : 'dead';
      html += `<div class="surv-row">
        <span class="surv-dist">${d} km</span>
        <span class="surv-pct ${openClass}">${r.openAir}%</span>
        <span class="surv-pct ${baseClass}">${r.basement}%</span>
        <span class="surv-psi">${r.psi.toFixed(1)} psi</span>
      </div>`;
    }
    html += '</div>';
    return html;
  }
};

// ---- WARHEAD DELIVERY ARC ANIMATION ----
NM.DeliveryArc = {
  layer: null,

  animate(map, fromLat, fromLng, toLat, toLng, durationMs, onComplete) {
    if (this.layer) map.removeLayer(this.layer);
    durationMs = durationMs || 3000;

    const steps = 60;
    const arcPoints = [];
    const R = 6371;
    const dist = NM.haversine(fromLat, fromLng, toLat, toLng);
    const maxAlt = Math.min(1200, dist * 0.08); // km apogee

    // Generate arc path (great circle with altitude)
    for (let i = 0; i <= steps; i++) {
      const t = i / steps;
      const lat = fromLat + (toLat - fromLat) * t;
      const lng = fromLng + (toLng - fromLng) * t;
      arcPoints.push([lat, lng]);
    }

    // Animated polyline that grows
    const line = L.polyline([], {color: '#f38ba8', weight: 2, opacity: 0.7, dashArray: '8 4'}).addTo(map);
    const warhead = L.circleMarker([fromLat, fromLng], {
      radius: 4, color: '#f38ba8', fillColor: '#f38ba8', fillOpacity: 1, weight: 0
    }).addTo(map);

    this.layer = L.layerGroup([line, warhead]).addTo(map);

    const start = performance.now();
    const tick = (now) => {
      const elapsed = now - start;
      const progress = Math.min(1, elapsed / durationMs);
      const idx = Math.floor(progress * steps);

      line.setLatLngs(arcPoints.slice(0, idx + 1));
      if (arcPoints[idx]) warhead.setLatLng(arcPoints[idx]);

      if (progress >= 1) {
        map.removeLayer(this.layer);
        this.layer = null;
        if (onComplete) onComplete();
      } else {
        requestAnimationFrame(tick);
      }
    };
    requestAnimationFrame(tick);

    // Fit bounds to show both endpoints
    map.fitBounds(L.latLngBounds([fromLat, fromLng], [toLat, toLng]).pad(0.3), {animate: true, duration: 0.5});
  }
};

// ---- EXPORT MAP AS PNG ----
NM.ExportPNG = {
  async capture() {
    // Use html2canvas-like approach with the map container
    const mapEl = document.getElementById('map');
    try {
      // Try using the canvas renderer directly if available
      const leafletCanvas = mapEl.querySelector('canvas');
      if (leafletCanvas) {
        const dataURL = leafletCanvas.toDataURL('image/png');
        this.download(dataURL, 'nukemap-export.png');
        return;
      }
      // Fallback: capture the map tiles + overlays
      // Create a temporary canvas
      const canvas = document.createElement('canvas');
      const rect = mapEl.getBoundingClientRect();
      canvas.width = rect.width * 2; // 2x for DPI
      canvas.height = rect.height * 2;
      const ctx = canvas.getContext('2d');
      ctx.scale(2, 2);
      ctx.fillStyle = '#11111b';
      ctx.fillRect(0, 0, rect.width, rect.height);

      // Draw all visible tile images
      const tiles = mapEl.querySelectorAll('.leaflet-tile');
      for (const tile of tiles) {
        if (tile.tagName === 'IMG' && tile.complete) {
          const tr = tile.getBoundingClientRect();
          const x = tr.left - rect.left;
          const y = tr.top - rect.top;
          try { ctx.drawImage(tile, x, y, tr.width, tr.height); } catch(e) {}
        }
      }

      // Draw SVG overlays (circles)
      const svgs = mapEl.querySelectorAll('svg.leaflet-zoom-animated');
      for (const svg of svgs) {
        const svgData = new XMLSerializer().serializeToString(svg);
        const img = new Image();
        const blob = new Blob([svgData], {type: 'image/svg+xml;charset=utf-8'});
        const url = URL.createObjectURL(blob);
        await new Promise((resolve) => {
          img.onload = () => {
            const sr = svg.getBoundingClientRect();
            ctx.drawImage(img, sr.left - rect.left, sr.top - rect.top, sr.width, sr.height);
            URL.revokeObjectURL(url);
            resolve();
          };
          img.onerror = resolve;
          img.src = url;
        });
      }

      this.download(canvas.toDataURL('image/png'), 'nukemap-export.png');
    } catch(e) {
      console.error('Export failed:', e);
    }
  },

  download(dataURL, filename) {
    const a = document.createElement('a');
    a.href = dataURL;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }
};
