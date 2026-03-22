// NukeMap - Search Engine
window.NM = window.NM || {};

NM.searchLocations = function(q) {
  q = q.trim(); if (!q) return [];
  const cm = q.match(/^(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)$/);
  if (cm) { const la=+cm[1],ln=+cm[2]; if(la>=-90&&la<=90&&ln>=-180&&ln<=180) return [{name:`${la.toFixed(4)}, ${ln.toFixed(4)}`,detail:'Coordinates',lat:la,lng:ln,pop:0,score:100}] }
  if (/^\d{5}$/.test(q)) { const i=NM.ZIP_IDX[q]; if(i!==undefined){const c=NM.CITIES[i];return[{name:c[0],detail:`${c[1]} ${q}`,lat:c[2],lng:c[3],pop:c[4],score:100}]} }
  if (/^\d{3,4}$/.test(q)) { const r=[];for(const[z,i]of Object.entries(NM.ZIP_IDX)){if(z.startsWith(q)){const c=NM.CITIES[i],k=c[0]+c[1];if(!r.find(x=>x.key===k))r.push({name:c[0],detail:`${c[1]} (${z}...)`,lat:c[2],lng:c[3],pop:c[4],score:50+c[4]/1e5,key:k})}if(r.length>=8)break}if(r.length)return r.sort((a,b)=>b.score-a.score) }
  const ql=q.toLowerCase(),qp=ql.split(/[,\s]+/).filter(Boolean),r=[];
  for (const c of NM.CITIES) {
    const n=c[0].toLowerCase(),s=c[1].toLowerCase(),sf=NM.STATES[c[1]]?.toLowerCase()||s;let sc=0;
    if(n===ql)sc=100;else if(n.startsWith(ql))sc=80;else if(s===ql||sf===ql)sc=40;
    else if(qp.length>=2){const cq=qp.slice(0,-1).join(' '),sq=qp[qp.length-1];if(n.startsWith(cq)&&(s.startsWith(sq)||sf.startsWith(sq)))sc=90}
    if(!sc&&n.includes(ql))sc=60;
    if(!sc&&qp.length===1){for(const w of n.split(/[\s-]+/))if(w.startsWith(ql)){sc=55;break}}
    if(!sc&&qp.length>=1){const cb=n+' '+s+' '+sf;if(qp.every(p=>cb.includes(p)))sc=45}
    if(sc>0){sc+=Math.min(20,Math.log10(Math.max(c[4],1))*3);r.push({name:c[0],detail:c[1],lat:c[2],lng:c[3],pop:c[4],score:sc})}
  }
  r.sort((a,b)=>b.score-a.score||b.pop-a.pop);
  return r.slice(0, 10);
};
