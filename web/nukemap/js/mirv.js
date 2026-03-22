// NukeMap - MIRV Simulation
window.NM = window.NM || {};

NM.MIRV = {
  active: false,

  // Generate warhead positions around a center point
  generatePattern(lat, lng, preset) {
    const count = preset.warheads;
    const spreadKm = preset.spread;
    const R = 6371;
    const points = [];

    if (preset.pattern === 'circle') {
      for (let i = 0; i < count; i++) {
        const angle = (i / count) * Math.PI * 2 - Math.PI / 2;
        const dLat = (spreadKm / 2 * Math.sin(angle)) / R * (180 / Math.PI);
        const dLng = (spreadKm / 2 * Math.cos(angle)) / R * (180 / Math.PI) / Math.cos(lat * Math.PI / 180);
        points.push({lat: lat + dLat, lng: lng + dLng, delay: i * 200});
      }
    } else if (preset.pattern === 'triangle') {
      const angles = [0, 2*Math.PI/3, 4*Math.PI/3];
      for (let i = 0; i < Math.min(count, angles.length); i++) {
        const dLat = (spreadKm / 2 * Math.sin(angles[i])) / R * (180 / Math.PI);
        const dLng = (spreadKm / 2 * Math.cos(angles[i])) / R * (180 / Math.PI) / Math.cos(lat * Math.PI / 180);
        points.push({lat: lat + dLat, lng: lng + dLng, delay: i * 300});
      }
    } else if (preset.pattern === 'grid') {
      const cols = Math.ceil(Math.sqrt(count));
      const rows = Math.ceil(count / cols);
      let idx = 0;
      for (let r = 0; r < rows && idx < count; r++) {
        for (let c = 0; c < cols && idx < count; c++) {
          const dx = (c - (cols - 1) / 2) * spreadKm / cols;
          const dy = (r - (rows - 1) / 2) * spreadKm / rows;
          const dLat = dy / R * (180 / Math.PI);
          const dLng = dx / R * (180 / Math.PI) / Math.cos(lat * Math.PI / 180);
          points.push({lat: lat + dLat, lng: lng + dLng, delay: idx * 150});
          idx++;
        }
      }
    } else if (preset.pattern === 'cross') {
      // Center + 4 cardinal directions
      points.push({lat, lng, delay: 0});
      const dirs = [[1,0],[0,1],[-1,0],[0,-1]];
      for (let i = 0; i < Math.min(count - 1, dirs.length); i++) {
        const dLat = dirs[i][0] * spreadKm / 2 / R * (180 / Math.PI);
        const dLng = dirs[i][1] * spreadKm / 2 / R * (180 / Math.PI) / Math.cos(lat * Math.PI / 180);
        points.push({lat: lat + dLat, lng: lng + dLng, delay: (i + 1) * 250});
      }
    }

    return points;
  },

  // Preview MIRV pattern on map (before detonation)
  previewMarkers: [],
  showPreview(map, lat, lng, preset) {
    this.clearPreview(map);
    const points = this.generatePattern(lat, lng, preset);
    points.forEach((pt, i) => {
      const marker = L.circleMarker([pt.lat, pt.lng], {
        radius: 6, color: '#f38ba8', fillColor: '#f38ba8', fillOpacity: 0.4,
        weight: 2, dashArray: '4 3'
      }).addTo(map);
      marker.bindTooltip(`Warhead ${i + 1}`, {permanent: false, className: 'mirv-tooltip'});
      this.previewMarkers.push(marker);
    });

    // Draw spread circle
    const spread = L.circle([lat, lng], {
      radius: preset.spread * 500, color: '#f38ba8', weight: 1,
      opacity: 0.3, fill: false, dashArray: '8 6'
    }).addTo(map);
    this.previewMarkers.push(spread);
  },

  clearPreview(map) {
    this.previewMarkers.forEach(m => map.removeLayer(m));
    this.previewMarkers = [];
  },

  // Execute MIRV strike with staggered detonations
  execute(map, lat, lng, preset, detonateFn) {
    this.clearPreview(map);
    const points = this.generatePattern(lat, lng, preset);
    points.forEach(pt => {
      setTimeout(() => detonateFn(pt.lat, pt.lng, preset.yield_kt), pt.delay);
    });
  }
};
