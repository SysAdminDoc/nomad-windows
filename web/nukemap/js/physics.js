// NukeMap - Nuclear Physics Module (Glasstone & Dolan + Brode)
window.NM = window.NM || {};

NM.calcEffects = function(Y, burstType, heightM, fissionFrac) {
  Y = Math.max(Y, 0.001);
  fissionFrac = (fissionFrac ?? 50) / 100;
  const isSurface = burstType === 'surface';
  const optH = 0.22 * Math.pow(Y, 1/3) * 1000;
  const h = burstType === 'airburst' ? optH : (heightM || 0);
  const hf = isSurface ? 0.8 : 1.0;

  return {
    fireball:  isSurface ? 0.05*Math.pow(Y,0.4) : 0.066*Math.pow(Y,0.4),
    psi200:    hf * 0.11 * Math.pow(Y, 1/3),
    psi20:     hf * 0.24 * Math.pow(Y, 1/3),
    psi5:      hf * 0.59 * Math.pow(Y, 1/3),
    psi3:      hf * 0.79 * Math.pow(Y, 1/3),
    psi1:      hf * 1.93 * Math.pow(Y, 1/3),
    thermal3:  0.68 * Math.pow(Y, 0.41),
    thermal2:  0.87 * Math.pow(Y, 0.41),
    thermal1:  1.18 * Math.pow(Y, 0.41),
    radiation: 1.15 * Math.pow(Y, 0.19),
    emp:       Math.min(2.5 * Math.pow(Y, 0.33), 500),
    craterR:   isSurface ? 0.038*Math.pow(Y,1/3.4) : 0,
    craterDepth: isSurface ? 0.013*Math.pow(Y,1/3.4) : 0,
    cloudTopH: (isSurface?0.24:0.29) * Math.pow(Y, 0.42),
    cloudTopR: 0.19 * Math.pow(Y, 0.4),
    stemR:     0.05 * Math.pow(Y, 0.35),
    cloudH:    0.29 * Math.pow(Y, 0.4),
    fallout:   (isSurface || (heightM !== undefined && heightM < (isSurface?0.05:0.066)*Math.pow(Y,0.4)*1000))
      ? { heavy:{length:1.3*Math.pow(Y*fissionFrac,0.45), width:0.39*Math.pow(Y*fissionFrac,0.35)},
          light:{length:4.6*Math.pow(Y*fissionFrac,0.45), width:1.1*Math.pow(Y*fissionFrac,0.35)} }
      : null,
    flashBlindDay:  2.1 * Math.pow(Y, 0.4),   // km - temporary blindness in daylight
    flashBlindNight: 55 * Math.pow(Y, 0.25),  // km - temporary blindness at night (much larger)
    firestormR: 0.68 * Math.pow(Y, 0.41) * 0.85, // km - firestorm probability zone (inside 3rd degree burns)
    burstHeight: h, optimalHeight: optH, isSurface, yieldKt: Y
  };
};

NM.calcTimeline = function(Y, e) {
  const items = [
    {time:'0 ms', desc:'Detonation. X-ray pulse heats air to millions of degrees.'},
    {time:'0.1 ms', desc:'Thermal flash. Temporary blindness to '+NM.fmtR(e.flashBlindDay)+' (day) or '+NM.fmtR(e.flashBlindNight)+' (night).'},
    {time: (0.0013*Math.pow(Y,0.4)*1000).toFixed(0)+' ms', desc:'Fireball reaches max size ('+NM.fmtR(e.fireball)+' radius). Surface temperature ~10,000,000\u00B0C.'},
    {time: NM.fmtTime(e.psi5/0.34), desc:'Blast wave at 5 psi ('+NM.fmtR(e.psi5)+'). Buildings destroyed. 160 mph winds.'},
    {time: NM.fmtTime(e.psi1/0.34), desc:'Blast wave at 1 psi ('+NM.fmtR(e.psi1)+'). Windows shatter into shrapnel.'},
  ];
  if (e.firestormR > 0.1) items.push({time:'~5 min', desc:'Firestorm ignites within '+NM.fmtR(e.firestormR)+'. Hurricane-force inward winds feed the fire.'});
  if (e.isSurface && e.fallout) {
    items.push({time:'~10 min', desc:'Mushroom cloud stabilizes at ~'+e.cloudTopH.toFixed(1)+' km. Fallout begins.'});
    items.push({time:'~30 min', desc:'Heaviest fallout within '+NM.fmtR(e.fallout.heavy.length)+' downwind.'});
    items.push({time:'~24 hrs', desc:'Light fallout extends '+NM.fmtR(e.fallout.light.length)+' downwind. 7:10 decay rule applies.'});
  } else {
    items.push({time:'~10 min', desc:'Mushroom cloud reaches ~'+e.cloudTopH.toFixed(1)+' km altitude.'});
  }
  return items;
};

NM.estimateCasualties = function(lat, lng, effects) {
  const nc = NM.findNearestCity(lat, lng);
  let density = 40;
  if (nc) {
    const d=nc.dist, p=nc.pop;
    if(d<3&&p>1e6)density=15000;else if(d<5&&p>5e5)density=10000;else if(d<10&&p>5e5)density=5000;
    else if(d<15&&p>1e5)density=3000;else if(d<25&&p>1e5)density=1500;else if(d<40&&p>5e4)density=500;
    else if(d<60&&p>1e4)density=200;else if(d<100)density=80;
  }
  const zones=[
    {r:effects.fireball,dfrac:1,ifrac:0},{r:effects.psi200||0,dfrac:0.98,ifrac:0.02},
    {r:effects.psi20,dfrac:0.90,ifrac:0.08},{r:effects.psi5,dfrac:0.50,ifrac:0.40},
    {r:Math.max(effects.thermal3,effects.psi3),dfrac:0.25,ifrac:0.40},
    {r:effects.psi1,dfrac:0.05,ifrac:0.30},{r:effects.thermal1,dfrac:0.01,ifrac:0.15},
  ];
  let deaths=0,injuries=0,prevA=0;
  for(const z of zones){if(z.r<0.001)continue;const a=Math.PI*z.r*z.r,ring=Math.max(0,a-prevA);deaths+=ring*density*z.dfrac;injuries+=ring*density*z.ifrac;prevA=a}
  return {deaths:Math.round(deaths),injuries:Math.round(injuries),density};
};

// Helpers
NM.haversine = function(lat1,lng1,lat2,lng2){
  const R=6371,dLat=(lat2-lat1)*Math.PI/180,dLng=(lng2-lng1)*Math.PI/180;
  const a=Math.sin(dLat/2)**2+Math.cos(lat1*Math.PI/180)*Math.cos(lat2*Math.PI/180)*Math.sin(dLng/2)**2;
  return R*2*Math.atan2(Math.sqrt(a),Math.sqrt(1-a));
};
NM.findNearestCity = function(lat,lng){
  let best=null,bd=Infinity;
  for(const c of NM.CITIES){if(!c[4])continue;const d=NM.haversine(lat,lng,c[2],c[3]);if(d<bd){bd=d;best={name:c[0],state:c[1],lat:c[2],lng:c[3],pop:c[4],dist:d}}}
  return best;
};

// Formatting
NM.fmtR = function(km){if(!isFinite(km))return'--';if(km<0.01)return Math.round(km*1000)+' m';if(km<1)return(km*1000).toFixed(0)+' m';if(km<10)return km.toFixed(2)+' km';if(km<100)return km.toFixed(1)+' km';return km.toFixed(0)+' km'};
NM.fmtArea = function(km){if(!isFinite(km))return'--';const a=Math.PI*km*km;if(a<0.01)return(a*1e6).toFixed(0)+' m\u00B2';if(a<1)return(a*100).toFixed(0)+' ha';return a.toFixed(1)+' km\u00B2'};
NM.fmtYield = function(kt){if(!isFinite(kt)||isNaN(kt))return'--';if(kt<0.001)return(kt*1e6).toFixed(0)+' g';if(kt<1)return(kt<0.01?(kt*1000).toFixed(1):(kt*1000).toFixed(0))+' tons';if(kt<1000)return(kt>=100?kt.toFixed(0):kt.toFixed(1))+' kT';return(kt/1000).toFixed(kt>=10000?0:1)+' MT'};
NM.fmtNum = function(n){if(!isFinite(n)||isNaN(n))return'--';if(n>=1e6)return(n/1e6).toFixed(1)+'M';if(n>=1e3)return(n/1e3).toFixed(n>=1e4?0:1)+'K';return Math.round(n).toLocaleString()};
NM.fmtDist = function(km){const mi=km*0.621371;return NM.fmtR(km)+' ('+(mi<1?(mi*5280).toFixed(0)+' ft':mi.toFixed(mi<10?1:0)+' mi')+')'};
NM.fmtTime = function(s){if(s<1)return(s*1000).toFixed(0)+' ms';if(s<60)return s.toFixed(1)+' sec';return(s/60).toFixed(1)+' min'};
NM.sliderToYield = function(v){return Math.pow(10,-3+(v/1000)*8)};
NM.yieldToSlider = function(kt){return((Math.log10(Math.max(kt,0.001))+3)/8)*1000};
NM.esc = function(s){const d=document.createElement('div');d.textContent=s;return d.innerHTML};
