// NukeMap - Search Engine (cities + 41,958 ZIP codes + 29,976 ZIPDB cities + military targets)
window.NM = window.NM || {};

// Common city aliases/abbreviations
NM._ALIASES = {
  'nyc':'New York','ny':'New York','la':'Los Angeles','sf':'San Francisco',
  'dc':'Washington','philly':'Philadelphia','vegas':'Las Vegas',
  'chi':'Chicago','atl':'Atlanta','det':'Detroit','nola':'New Orleans',
  'slc':'Salt Lake City','kc':'Kansas City','okc':'Oklahoma City',
};

// Build city index from ZIPDB on first search (lazy init)
NM._zipCityIndex = null;
NM._buildZipCityIndex = function() {
  if (NM._zipCityIndex || !NM.ZIPDB) return;
  NM._zipCityIndex = new Map();
  for (const [zip, val] of Object.entries(NM.ZIPDB)) {
    const parts = val.split(',');
    const city = parts.slice(2, -1).join(',');
    const st = parts[parts.length - 1];
    const key = city.toLowerCase() + ',' + st.toLowerCase();
    if (!NM._zipCityIndex.has(key)) {
      NM._zipCityIndex.set(key, {name: city, state: st, lat: +parts[0], lng: +parts[1], zips: 0});
    }
    NM._zipCityIndex.get(key).zips++;
  }
};

NM.searchLocations = function(q) {
  q = q.trim(); if (!q) return [];

  // Alias expansion
  const alias = NM._ALIASES[q.toLowerCase()];
  if (alias) q = alias;

  // Exact coordinates
  const cm = q.match(/^(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)$/);
  if (cm) { const la=+cm[1],ln=+cm[2]; if(la>=-90&&la<=90&&ln>=-180&&ln<=180) return [{name:`${la.toFixed(4)}, ${ln.toFixed(4)}`,detail:'Coordinates',lat:la,lng:ln,pop:0,score:100}] }

  // Exact 5-digit ZIP
  if (/^\d{5}$/.test(q)) {
    if (NM.ZIPDB && NM.ZIPDB[q]) {
      const parts = NM.ZIPDB[q].split(',');
      return [{name: parts.slice(2, -1).join(','), detail: `${parts[parts.length-1]} ${q}`, lat: +parts[0], lng: +parts[1], pop: 0, score: 100}];
    }
    const i = NM.ZIP_IDX[q]; if (i !== undefined) { const c = NM.CITIES[i]; return [{name:c[0],detail:`${c[1]} ${q}`,lat:c[2],lng:c[3],pop:c[4],score:100}] }
    return [];
  }

  // Partial ZIP (3-4 digits)
  if (/^\d{3,4}$/.test(q)) {
    const r = [], seen = new Set();
    if (NM.ZIPDB) {
      for (const [z, val] of Object.entries(NM.ZIPDB)) {
        if (z.startsWith(q)) {
          const parts = val.split(',');
          const city = parts.slice(2, -1).join(',');
          const st = parts[parts.length - 1];
          const key = city + ',' + st;
          if (!seen.has(key)) { seen.add(key); r.push({name: city, detail: `${st} (${z}...)`, lat: +parts[0], lng: +parts[1], pop: 0, score: 50, key}); }
        }
        if (r.length >= 12) break;
      }
    }
    if (r.length) return r;
  }

  // Build ZIPDB city index if needed
  NM._buildZipCityIndex();

  const ql = q.toLowerCase(), qp = ql.split(/[,\s]+/).filter(Boolean), r = [];

  // Search main CITIES array (has population data)
  for (const c of NM.CITIES) {
    const n=c[0].toLowerCase(),s=c[1].toLowerCase(),sf=NM.STATES[c[1]]?.toLowerCase()||s;let sc=0;
    if(n===ql)sc=100;else if(n.startsWith(ql))sc=80;else if(s===ql||sf===ql)sc=40;
    else if(qp.length>=2){const cq=qp.slice(0,-1).join(' '),sq=qp[qp.length-1];if(n.startsWith(cq)&&(s.startsWith(sq)||sf.startsWith(sq)))sc=90}
    if(!sc&&n.includes(ql))sc=60;
    if(!sc&&qp.length===1){for(const w of n.split(/[\s-]+/))if(w.startsWith(ql)){sc=55;break}}
    if(!sc&&qp.length>=1){const cb=n+' '+s+' '+sf;if(qp.every(p=>cb.includes(p)))sc=45}
    if(sc>0){sc+=Math.min(20,Math.log10(Math.max(c[4],1))*3);r.push({name:c[0],detail:c[1],lat:c[2],lng:c[3],pop:c[4],score:sc})}
  }

  // Search ZIPDB cities (29,976 unique cities — fills gaps in main list)
  if (NM._zipCityIndex) {
    const seenCoords = new Set(r.map(x => x.lat.toFixed(2) + ',' + x.lng.toFixed(2)));
    for (const [key, city] of NM._zipCityIndex) {
      const n = city.name.toLowerCase();
      const st = city.state.toLowerCase();
      const sf = NM.STATES[city.state]?.toLowerCase() || st;
      let sc = 0;
      if (n === ql) sc = 85;
      else if (n.startsWith(ql)) sc = 65;
      else if (qp.length >= 2) {
        const cq = qp.slice(0, -1).join(' '), sq = qp[qp.length - 1];
        if (n.startsWith(cq) && (st.startsWith(sq) || sf.startsWith(sq))) sc = 78;
      }
      if (!sc && n.includes(ql) && ql.length >= 3) sc = 48;
      if (!sc && qp.length >= 1 && qp.every(p => (n + ' ' + st + ' ' + sf).includes(p)) && ql.length >= 3) sc = 42;
      if (sc > 0) {
        const coordKey = city.lat.toFixed(2) + ',' + city.lng.toFixed(2);
        if (!seenCoords.has(coordKey)) {
          seenCoords.add(coordKey);
          sc += Math.min(10, city.zips * 0.3); // more zips = likely bigger city
          r.push({name: city.name, detail: city.state, lat: city.lat, lng: city.lng, pop: 0, score: sc});
        }
      }
      if (r.length >= 50) break; // limit search work
    }
  }

  // Search WW3 strategic targets
  const typeLabels = {icbm:'ICBM Base',bomber:'Bomber Base',sub:'Submarine Base',c2:'Command Center',nuclear:'Nuclear Facility',military:'Military Base',infra:'Infrastructure',city:'Metro Area'};
  const allTargets = [
    ...(NM.WW3_TARGETS_US || []).map(t => ({...t, side: 'US'})),
    ...(NM.WW3_TARGETS_RU || []).map(t => ({...t, side: 'RU'})),
    ...(NM.WW3_TARGETS_NATO || []).map(t => ({...t, side: 'NATO'})),
  ];
  for (const t of allTargets) {
    const n = t.name.toLowerCase(), catL = (t.cat || '').toLowerCase(), typeL = (t.type || '').toLowerCase();
    let sc = 0;
    const searchable = n + ' ' + catL + ' ' + typeL + ' ' + (typeLabels[t.type]||'').toLowerCase();
    if (n === ql) sc = 95; else if (n.startsWith(ql)) sc = 75; else if (n.includes(ql)) sc = 55;
    else if (typeL.includes(ql) || (typeLabels[t.type]||'').toLowerCase().includes(ql)) sc = 50;
    else if (catL.includes(ql)) sc = 40;
    else if (qp.length >= 1 && qp.every(p => searchable.includes(p))) sc = 45;
    if (sc > 0 && !r.find(x => Math.abs(x.lat - t.lat) < 0.01 && Math.abs(x.lng - t.lng) < 0.01)) {
      r.push({name: t.name, detail: `${typeLabels[t.type] || t.type} (${t.side})`, lat: t.lat, lng: t.lng, pop: 0, score: sc, isTarget: true});
    }
  }

  r.sort((a, b) => b.score - a.score || b.pop - a.pop);
  return r.slice(0, 15);
};
