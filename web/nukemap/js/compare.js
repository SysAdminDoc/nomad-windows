// NukeMap - Weapon Comparison Mode
window.NM = window.NM || {};

NM.Compare = {
  active: false,
  weaponA: null,
  weaponB: null,
  layers: [],

  generateTable(wA, wB) {
    const eA = NM.calcEffects(wA.yield_kt, 'airburst', 0, 50);
    const eB = NM.calcEffects(wB.yield_kt, 'airburst', 0, 50);

    const rows = [
      ['Yield', NM.fmtYield(wA.yield_kt), NM.fmtYield(wB.yield_kt)],
      ['Fireball', NM.fmtDist(eA.fireball), NM.fmtDist(eB.fireball)],
      ['200 psi', NM.fmtDist(eA.psi200), NM.fmtDist(eB.psi200)],
      ['20 psi', NM.fmtDist(eA.psi20), NM.fmtDist(eB.psi20)],
      ['5 psi', NM.fmtDist(eA.psi5), NM.fmtDist(eB.psi5)],
      ['1 psi', NM.fmtDist(eA.psi1), NM.fmtDist(eB.psi1)],
      ['3rd\u00B0 Burns', NM.fmtDist(eA.thermal3), NM.fmtDist(eB.thermal3)],
      ['1st\u00B0 Burns', NM.fmtDist(eA.thermal1), NM.fmtDist(eB.thermal1)],
      ['500 rem', NM.fmtDist(eA.radiation), NM.fmtDist(eB.radiation)],
      ['EMP', NM.fmtDist(eA.emp), NM.fmtDist(eB.emp)],
      ['Cloud Top', NM.fmtDist(eA.cloudTopH), NM.fmtDist(eB.cloudTopH)],
      ['5 psi Area', NM.fmtArea(eA.psi5), NM.fmtArea(eB.psi5)],
    ];

    let html = `<table class="compare-table">
      <thead><tr><th></th><th style="color:var(--blue)">${NM.esc(wA.name)}</th><th style="color:var(--peach)">${NM.esc(wB.name)}</th></tr></thead><tbody>`;
    for (const [label, vA, vB] of rows) {
      html += `<tr><td class="ct-label">${label}</td><td class="ct-a">${vA}</td><td class="ct-b">${vB}</td></tr>`;
    }
    html += '</tbody></table>';
    return html;
  },

  // Draw both weapons' effects overlaid on map at same location
  drawOverlay(map, lat, lng, wA, wB) {
    this.clearOverlay(map);
    const eA = NM.calcEffects(wA.yield_kt, 'airburst', 0, 50);
    const eB = NM.calcEffects(wB.yield_kt, 'airburst', 0, 50);

    const drawRings = (e, color, offsetLng) => {
      const rings = [
        {r: e.psi5, label: '5 psi'},
        {r: e.psi1, label: '1 psi'},
        {r: e.thermal3, label: '3rd\u00B0'},
        {r: e.fireball, label: 'Fireball'},
      ];
      rings.forEach(ring => {
        if (ring.r < 0.001) return;
        const c = L.circle([lat, lng + offsetLng], {
          radius: ring.r * 1000, color, weight: 2, opacity: 0.6,
          fillColor: color, fillOpacity: 0.08, dashArray: '6 4'
        }).addTo(map);
        this.layers.push(c);
      });
    };

    // Slight offset so both are visible
    drawRings(eA, '#89b4fa', -0.001);
    drawRings(eB, '#fab387', 0.001);

    // Fit bounds to largest
    const maxR = Math.max(eA.psi1, eB.psi1, eA.thermal1, eB.thermal1);
    if (maxR > 0) {
      map.fitBounds(L.circle([lat, lng], {radius: maxR * 1000}).getBounds().pad(0.2));
    }
  },

  clearOverlay(map) {
    this.layers.forEach(l => map.removeLayer(l));
    this.layers = [];
  }
};
