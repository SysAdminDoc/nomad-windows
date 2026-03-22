// NukeMap - Shelter Survival Analysis
window.NM = window.NM || {};

NM.Shelter = {
  // Calculate survival probability at a given distance for each shelter type
  analyze(effects, distanceKm) {
    const results = [];
    // Get overpressure at distance (rough interpolation)
    const psiAtDist = this.estimatePsi(effects, distanceKm);
    const thermalAtDist = this.estimateThermalCal(effects, distanceKm);
    const radAtDist = distanceKm <= effects.radiation ? 1 : 0;

    for (const shelter of NM.SHELTER_TYPES) {
      const blastSurvival = psiAtDist <= shelter.psi ? 1 : Math.max(0, 1 - (psiAtDist - shelter.psi) / (shelter.psi * 2));
      const thermalSurvival = shelter.thermal; // fraction of thermal blocked
      const radSurvival = 1 - radAtDist * (1 - shelter.rad); // lower rad factor = better protection

      const overall = Math.max(0, Math.min(1,
        blastSurvival * (thermalAtDist > 8 ? thermalSurvival : 1) * (radAtDist ? (1 - shelter.rad * 0.5) : 1)
      ));

      results.push({
        name: shelter.name,
        color: shelter.color,
        survival: Math.round(overall * 100),
        blastOk: psiAtDist <= shelter.psi,
        psiAtDist: psiAtDist.toFixed(1)
      });
    }
    return results;
  },

  // Estimate overpressure at distance (inverse cube root scaling)
  estimatePsi(effects, dist) {
    if (dist <= 0) return 999;
    // Use known radius/psi pairs to interpolate
    const pairs = [
      {r: effects.fireball, psi: 3000},
      {r: effects.psi200 || effects.fireball * 1.5, psi: 200},
      {r: effects.psi20, psi: 20},
      {r: effects.psi5, psi: 5},
      {r: effects.psi3 || effects.psi5 * 1.3, psi: 3},
      {r: effects.psi1, psi: 1},
      {r: effects.psi1 * 2, psi: 0.2},
    ].filter(p => p.r > 0).sort((a, b) => a.r - b.r);

    if (dist <= pairs[0].r) return pairs[0].psi;
    if (dist >= pairs[pairs.length - 1].r) return 0;

    for (let i = 0; i < pairs.length - 1; i++) {
      if (dist >= pairs[i].r && dist <= pairs[i + 1].r) {
        const frac = (dist - pairs[i].r) / (pairs[i + 1].r - pairs[i].r);
        return pairs[i].psi * Math.pow(pairs[i + 1].psi / pairs[i].psi, frac);
      }
    }
    return 0;
  },

  estimateThermalCal(effects, dist) {
    // Rough: 3rd degree ~8 cal/cm2, 1st degree ~2 cal/cm2
    if (dist <= effects.fireball) return 1000;
    if (dist <= effects.thermal3) return 8 * Math.pow(effects.thermal3 / dist, 2);
    if (dist <= effects.thermal1) return 2 * Math.pow(effects.thermal1 / dist, 2);
    return 0;
  },

  // Generate HTML for shelter analysis at multiple distances
  generateReport(effects) {
    const distances = [];
    // Sample at key radii
    const radii = [
      {r: effects.fireball, label: 'Fireball edge'},
      {r: effects.psi20, label: '20 psi zone'},
      {r: effects.psi5, label: '5 psi zone'},
      {r: effects.psi1, label: '1 psi zone'},
      {r: effects.psi1 * 1.5, label: 'Beyond 1 psi'},
      {r: effects.thermal1, label: '1st degree burn edge'},
    ].filter(x => x.r > 0.001);

    let html = '';
    for (const {r, label} of radii) {
      const analysis = this.analyze(effects, r);
      html += `<div class="shelter-zone">
        <div class="sz-header"><span class="sz-dist">${NM.fmtR(r)}</span><span class="sz-label">${label}</span></div>
        <div class="sz-bars">`;
      for (const a of analysis) {
        const barClass = a.survival >= 80 ? 'safe' : a.survival >= 40 ? 'risk' : 'dead';
        html += `<div class="sz-bar-row">
          <span class="sz-name">${a.name}</span>
          <div class="sz-bar"><div class="sz-fill ${barClass}" style="width:${a.survival}%"></div></div>
          <span class="sz-pct">${a.survival}%</span>
        </div>`;
      }
      html += '</div></div>';
    }
    return html;
  }
};
