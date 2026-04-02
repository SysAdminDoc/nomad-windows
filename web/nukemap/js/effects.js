// NukeMap - Map Effects Drawing (rings, fallout, markers, tooltips)
window.NM = window.NM || {};

NM.Effects = {
  rtEl: null,

  drawRings(map, det) {
    const {lat, lng, effects: e} = det;
    const flashR = NM._nightMode ? e.flashBlindNight : e.flashBlindDay;
    const rings = [
      {id:'flashblind',r:flashR,color:'#b4befe',fo:0.03,bo:0.15,dashed:true},
      {id:'emp',r:e.emp,color:'#94e2d5',fo:0.06,bo:0.25,dashed:true},
      {id:'thermal1',r:e.thermal1,color:'#f5c2e7',fo:0.08,bo:0.35},
      {id:'psi1',r:e.psi1,color:'#f9e2af',fo:0.10,bo:0.40},
      {id:'thermal3',r:e.thermal3,color:'#fab387',fo:0.12,bo:0.45},
      {id:'firestorm',r:e.firestormR,color:'#e64553',fo:0.14,bo:0.50},
      {id:'psi5',r:e.psi5,color:'#cba6f7',fo:0.15,bo:0.50},
      {id:'psi20',r:e.psi20,color:'#89b4fa',fo:0.18,bo:0.55},
      {id:'psi200',r:e.psi200,color:'#89dceb',fo:0.22,bo:0.60},
      {id:'radiation',r:e.radiation,color:'#a6e3a1',fo:0.20,bo:0.60},
      {id:'fireball',r:e.fireball,color:'#f5e0dc',fo:0.45,bo:0.75},
    ];
    if (e.craterR > 0) rings.push({id:'crater',r:e.craterR,color:'#585b70',fo:0.5,bo:0.7,dashed:true});

    const layers = [];

    // Burn scar (dark destruction zone at 5 psi)
    if (e.psi5 > 0.01) {
      const scar = L.circle([lat, lng], {
        radius: e.psi5 * 1000, color: 'transparent', weight: 0,
        fillColor: '#000', fillOpacity: 0.25, interactive: false, className: 'burn-scar'
      });
      scar._effectId = '_scar';
      scar.addTo(map);
      layers.push(scar);
    }

    for (const ring of rings) {
      if (ring.r < 0.0005) continue;
      const circ = L.circle([lat, lng], {
        radius: ring.r * 1000, color: ring.color, weight: 1.5, opacity: ring.bo,
        fillColor: ring.color, fillOpacity: ring.fo, dashArray: ring.dashed ? '6 5' : null
      });
      circ._effectId = ring.id;
      circ._effectR = ring.r;
      const def = NM.EFFECTS_DEF.find(d => d.id === ring.id);
      if (def) {
        circ.on('mouseover', (ev) => this.showTooltip(map, ev.latlng, def, ring.r));
        circ.on('mouseout', () => this.hideTooltip());
        circ.on('mousemove', (ev) => {
          if (this.rtEl && this.rtEl.style.display !== 'none') {
            const pt = map.latLngToContainerPoint(ev.latlng);
            this.rtEl.style.left = (pt.x + 16) + 'px';
            this.rtEl.style.top = (pt.y - 20) + 'px';
          }
        });
      }
      circ.addTo(map);
      layers.push(circ);
    }
    return layers;
  },

  drawFallout(map, lat, lng, fallout, windAngle) {
    const dAngle = ((windAngle + 180) % 360) * Math.PI / 180;
    const mkE = (l, w) => {
      const pts = [], R = 6371;
      for (let i = 0; i <= 40; i++) {
        const t = (i / 40) * 2 * Math.PI;
        const dx = l * (0.5 + 0.5 * Math.cos(t)) * Math.cos(dAngle) - (w / 2) * Math.sin(t) * Math.sin(dAngle);
        const dy = l * (0.5 + 0.5 * Math.cos(t)) * Math.sin(dAngle) + (w / 2) * Math.sin(t) * Math.cos(dAngle);
        pts.push([lat + (dy / R) * (180 / Math.PI), lng + (dx / R) * (180 / Math.PI) / Math.cos(lat * Math.PI / 180)]);
      }
      return pts;
    };
    const hp = L.polygon(mkE(fallout.heavy.length, fallout.heavy.width), {color: '#f9e2af', weight: 1, opacity: 0.5, fillColor: '#f9e2af', fillOpacity: 0.15, dashArray: '4 4'});
    const lp = L.polygon(mkE(fallout.light.length, fallout.light.width), {color: '#f9e2af', weight: 1, opacity: 0.25, fillColor: '#f9e2af', fillOpacity: 0.05, dashArray: '6 4'});
    return L.layerGroup([lp, hp]);
  },

  drawMarker(map, lat, lng) {
    const icon = L.divIcon({
      className: '',
      html: '<div class="gz-marker"><div class="gz-outer"></div><div class="gz-inner"></div></div>',
      iconSize: [28, 28], iconAnchor: [14, 14]
    });
    return L.marker([lat, lng], {icon});
  },

  buildPopup(det) {
    const e = det.effects, nc = NM.findNearestCity(det.lat, det.lng);
    let loc = `${det.lat.toFixed(4)}, ${det.lng.toFixed(4)}`;
    if (nc && nc.dist < 50) loc = `${nc.name}, ${nc.state}`;
    return `<div style="min-width:250px">
      <div style="font-weight:800;font-size:15px;color:var(--red)">${NM.fmtYield(det.yieldKt)}</div>
      <div style="font-size:10px;color:var(--overlay1);margin-bottom:8px;text-transform:uppercase;letter-spacing:0.5px">${det.burstType}${det.burstType==='airburst'?' ('+Math.round(e.burstHeight)+'m)':''} \u2014 ${loc}</div>
      <table style="width:100%;font-size:11px;border-collapse:collapse">
      ${[['Fireball',e.fireball,'#f5e0dc'],['500 rem',e.radiation,'#a6e3a1'],['20 psi',e.psi20,'#89b4fa'],['Firestorm',e.firestormR,'#e64553'],['5 psi',e.psi5,'#cba6f7'],['3rd\u00B0 burns',e.thermal3,'#fab387'],['1 psi',e.psi1,'#f9e2af'],['Flash blind',NM._nightMode?e.flashBlindNight:e.flashBlindDay,'#b4befe']].map(([l,r,c])=>`<tr><td style="padding:2px 0"><span style="color:${c};font-size:8px">\u2B24</span> ${l}</td><td style="text-align:right;font-weight:600">${NM.fmtDist(r)}</td></tr>`).join('')}
      </table>
      <div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--surface1);font-size:12px">
        <span style="color:var(--red);font-weight:700">${NM.fmtNum(det.casualties.deaths)} killed</span> &nbsp;
        <span style="color:var(--peach);font-weight:600">${NM.fmtNum(det.casualties.injuries)} injured</span>
      </div></div>`;
  },

  showTooltip(map, latlng, def, r) {
    if (!this.rtEl) {
      this.rtEl = document.createElement('div');
      this.rtEl.className = 'ring-tooltip';
      (NM.getUiRoot ? NM.getUiRoot() : document.body).appendChild(this.rtEl);
    }
    this.rtEl.innerHTML = `<div class="rt-title" style="color:${def.color}">${def.label}</div><div>Radius: <b>${NM.fmtDist(r)}</b></div><div>Area: <b>${NM.fmtArea(r)}</b></div><div class="rt-desc">${def.desc}</div>`;
    this.rtEl.style.display = 'block';
    const pt = map.latLngToContainerPoint(latlng);
    this.rtEl.style.left = (pt.x + 16) + 'px';
    this.rtEl.style.top = (pt.y - 20) + 'px';
  },

  hideTooltip() { if (this.rtEl) this.rtEl.style.display = 'none'; }
};
