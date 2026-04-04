/**
 * NomadChart - reusable Canvas 2D chart engine for NOMAD Field Desk.
 * Provides line, bar, donut, breakdown, and sparkline charts.
 */

const NomadChart = {
  _themeColors: null,
  _getTheme() {
    const s = getComputedStyle(document.documentElement);
    return {
      text: s.getPropertyValue('--text').trim() || '#d4c9a8',
      textDim: s.getPropertyValue('--text-dim').trim() || '#5c5040',
      textMuted: s.getPropertyValue('--text-muted').trim() || '#888',
      accent: s.getPropertyValue('--accent').trim() || '#4a4d24',
      border: s.getPropertyValue('--border').trim() || '#3a3520',
      surface: s.getPropertyValue('--surface').trim() || '#1a1814',
      red: s.getPropertyValue('--red').trim() || '#c0392b',
      orange: s.getPropertyValue('--orange').trim() || '#e67e22',
      green: s.getPropertyValue('--green').trim() || '#27ae60',
    };
  },
  _palette: ['#5b9fff','#ff6b6b','#51cf66','#ffd43b','#cc5de8','#ff922b','#20c997','#a9e34b','#f06595','#74c0fc'],
  _noData(ctx, W, H, msg) {
    const t = this._getTheme();
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = t.textMuted;
    ctx.font = '12px monospace';
    ctx.textAlign = 'center';
    ctx.fillText(msg || 'No data yet', W / 2, H / 2);
    ctx.textAlign = 'start';
  },

  line(canvasId, data, options) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    if (canvas.parentElement.clientWidth <= 0) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width = canvas.parentElement.clientWidth;
    const H = canvas.height = options.height || 200;
    const t = this._getTheme();
    ctx.clearRect(0, 0, W, H);

    if (!data.labels || !data.labels.length || !data.datasets || !data.datasets.length) {
      return this._noData(ctx, W, H);
    }

    // Cap unbounded chart data
    if (data.labels.length > 2000) {
      data.labels = data.labels.slice(-2000);
      data.datasets.forEach(ds => { if (ds.values && ds.values.length > 2000) ds.values = ds.values.slice(-2000); });
    }

    const pad = {top: 30, right: 20, bottom: 40, left: 55};
    if (options.rightAxis) pad.right = 55;
    const plotW = W - pad.left - pad.right;
    const plotH = H - pad.top - pad.bottom;

    // Compute Y range across all datasets (left axis)
    let allVals = [];
    data.datasets.filter(d => !d.rightAxis).forEach(ds => ds.values.forEach(v => { if (v != null) allVals.push(v); }));
    let yMin = allVals.length ? Math.min(...allVals) : 0;
    let yMax = allVals.length ? Math.max(...allVals) : 1;
    if (yMin === yMax) { yMin -= 1; yMax += 1; }
    const yRange = yMax - yMin || 1;

    // Right axis range
    let rMin = 0, rMax = 1, rRange = 1;
    if (options.rightAxis) {
      let rVals = [];
      data.datasets.filter(d => d.rightAxis).forEach(ds => ds.values.forEach(v => { if (v != null) rVals.push(v); }));
      if (rVals.length) { rMin = Math.min(...rVals); rMax = Math.max(...rVals); }
      if (rMin === rMax) { rMin -= 1; rMax += 1; }
      rRange = rMax - rMin || 1;
    }

    const xScale = i => pad.left + (i / (data.labels.length - 1 || 1)) * plotW;
    const yScale = v => pad.top + plotH - ((v - yMin) / yRange) * plotH;
    const rScale = v => pad.top + plotH - ((v - rMin) / rRange) * plotH;

    // Grid
    if (options.showGrid !== false) {
      ctx.strokeStyle = t.border;
      ctx.lineWidth = 0.5;
      for (let i = 0; i <= 4; i++) {
        const y = pad.top + (plotH * i / 4);
        ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(pad.left + plotW, y); ctx.stroke();
      }
    }

    // Axes
    ctx.strokeStyle = t.border;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(pad.left, pad.top); ctx.lineTo(pad.left, pad.top + plotH); ctx.lineTo(pad.left + plotW, pad.top + plotH);
    ctx.stroke();

    // Draw datasets
    data.datasets.forEach((ds, di) => {
      const color = ds.color || this._palette[di % this._palette.length];
      const scale = ds.rightAxis ? rScale : yScale;
      ctx.strokeStyle = color;
      ctx.lineWidth = ds.lineWidth || 2;

      // Fill area if requested
      if (ds.fill) {
        ctx.save();
        ctx.beginPath();
        let started = false;
        let firstX = 0, lastX = 0;
        for (let i = 0; i < ds.values.length; i++) {
          if (ds.values[i] == null) continue;
          const x = xScale(i), y = scale(ds.values[i]);
          if (!started) { ctx.moveTo(x, y); firstX = x; started = true; } else { ctx.lineTo(x, y); }
          lastX = x;
        }
        ctx.lineTo(lastX, pad.top + plotH);
        ctx.lineTo(firstX, pad.top + plotH);
        ctx.closePath();
        ctx.globalAlpha = 0.12;
        ctx.fillStyle = color;
        ctx.fill();
        ctx.restore();
      }

      // Line
      ctx.beginPath();
      let started = false;
      for (let i = 0; i < ds.values.length; i++) {
        if (ds.values[i] == null) continue;
        const x = xScale(i), y = scale(ds.values[i]);
        if (!started) { ctx.moveTo(x, y); started = true; } else { ctx.lineTo(x, y); }
      }
      ctx.strokeStyle = color;
      ctx.stroke();

      // Dots
      ctx.fillStyle = color;
      for (let i = 0; i < ds.values.length; i++) {
        if (ds.values[i] == null) continue;
        ctx.beginPath(); ctx.arc(xScale(i), scale(ds.values[i]), 2.5, 0, Math.PI * 2); ctx.fill();
      }
    });

    // Y-axis labels (left)
    ctx.fillStyle = t.textMuted;
    ctx.font = '9px monospace';
    ctx.textAlign = 'right';
    for (let i = 0; i <= 4; i++) {
      const v = yMin + (yRange * i / 4);
      ctx.fillText(v % 1 === 0 ? v.toFixed(0) : v.toFixed(1), pad.left - 6, pad.top + plotH - (plotH * i / 4) + 3);
    }

    // Y-axis labels (right)
    if (options.rightAxis) {
      ctx.textAlign = 'left';
      for (let i = 0; i <= 4; i++) {
        const v = rMin + (rRange * i / 4);
        ctx.fillText(v % 1 === 0 ? v.toFixed(0) : v.toFixed(1), pad.left + plotW + 6, pad.top + plotH - (plotH * i / 4) + 3);
      }
    }

    // X-axis labels
    ctx.textAlign = 'center';
    const step = Math.max(1, Math.floor(data.labels.length / 8));
    for (let i = 0; i < data.labels.length; i += step) {
      const lbl = data.labels[i];
      const short = lbl.length > 5 ? lbl.slice(5) : lbl;
      ctx.fillText(short, xScale(i), pad.top + plotH + 16);
    }

    // Title
    if (options.title) {
      ctx.fillStyle = t.text;
      ctx.font = 'bold 11px monospace';
      ctx.textAlign = 'left';
      ctx.fillText(options.title, pad.left, pad.top - 10);
    }

    // Y label
    if (options.yLabel) {
      ctx.save();
      ctx.fillStyle = t.textDim;
      ctx.font = '9px monospace';
      ctx.translate(10, pad.top + plotH / 2);
      ctx.rotate(-Math.PI / 2);
      ctx.textAlign = 'center';
      ctx.fillText(options.yLabel, 0, 0);
      ctx.restore();
    }

    // Legend
    if (options.showLegend !== false && data.datasets.length > 1) {
      ctx.font = '9px monospace';
      ctx.textAlign = 'left';
      let lx = pad.left;
      data.datasets.forEach((ds, di) => {
        const color = ds.color || this._palette[di % this._palette.length];
        ctx.fillStyle = color;
        ctx.fillRect(lx, pad.top + plotH + 28, 10, 8);
        ctx.fillStyle = t.textMuted;
        ctx.fillText(ds.label, lx + 14, pad.top + plotH + 36);
        lx += ctx.measureText(ds.label).width + 28;
      });
    }
    ctx.textAlign = 'start';
  },

  bar(canvasId, data, options) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    if (canvas.parentElement.clientWidth <= 0) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width = canvas.parentElement.clientWidth;
    const H = canvas.height = options.height || 200;
    const t = this._getTheme();
    ctx.clearRect(0, 0, W, H);

    if (!data.labels || !data.labels.length) return this._noData(ctx, W, H);

    // Cap unbounded chart data
    if (data.labels.length > 2000) {
      data.labels = data.labels.slice(-2000);
      data.datasets.forEach(ds => { if (ds.values && ds.values.length > 2000) ds.values = ds.values.slice(-2000); });
    }

    const pad = {top: 30, right: 20, bottom: 40, left: 55};
    if (options.lineOverlay) pad.right = 55;
    const plotW = W - pad.left - pad.right;
    const plotH = H - pad.top - pad.bottom;
    const nGroups = data.labels.length;
    const nBars = data.datasets.filter(d => !d.lineOverlay).length;
    const groupW = plotW / nGroups;
    const barW = Math.min(groupW * 0.7 / nBars, 30);

    let allVals = [];
    data.datasets.filter(d => !d.lineOverlay).forEach(ds => ds.values.forEach(v => { if (v != null) allVals.push(v); }));
    let yMax = allVals.length ? Math.max(...allVals) : 1;
    if (yMax === 0) yMax = 1;
    const yScale = v => pad.top + plotH - (v / yMax) * plotH;

    // Line overlay range
    let lMin = 0, lMax = 100, lRange = 100;
    if (options.lineOverlay) {
      let lVals = [];
      data.datasets.filter(d => d.lineOverlay).forEach(ds => ds.values.forEach(v => { if (v != null) lVals.push(v); }));
      if (lVals.length) { lMin = Math.min(...lVals); lMax = Math.max(...lVals); }
      if (lMin === lMax) { lMin -= 1; lMax += 1; }
      lRange = lMax - lMin || 1;
    }
    const lScale = v => pad.top + plotH - ((v - lMin) / lRange) * plotH;

    // Grid
    ctx.strokeStyle = t.border; ctx.lineWidth = 0.5;
    for (let i = 0; i <= 4; i++) {
      const y = pad.top + (plotH * i / 4);
      ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(pad.left + plotW, y); ctx.stroke();
    }

    // Axes
    ctx.strokeStyle = t.border; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(pad.left, pad.top); ctx.lineTo(pad.left, pad.top + plotH); ctx.lineTo(pad.left + plotW, pad.top + plotH); ctx.stroke();

    // Bars
    let barIdx = 0;
    data.datasets.forEach((ds, di) => {
      if (ds.lineOverlay) return;
      const color = ds.color || this._palette[di % this._palette.length];
      const bi = barIdx++;
      for (let i = 0; i < ds.values.length; i++) {
        if (ds.values[i] == null) continue;
        const cx = pad.left + groupW * i + groupW / 2;
        const x = cx - (nBars * barW) / 2 + bi * barW;
        const y = yScale(ds.values[i]);
        const h = pad.top + plotH - y;
        ctx.fillStyle = color;
        ctx.fillRect(x, y, barW - 1, h);
      }
    });

    // Line overlay
    data.datasets.filter(d => d.lineOverlay).forEach((ds, di) => {
      const color = ds.color || '#ffd43b';
      ctx.strokeStyle = color; ctx.lineWidth = 2;
      ctx.beginPath();
      let started = false;
      for (let i = 0; i < ds.values.length; i++) {
        if (ds.values[i] == null) continue;
        const x = pad.left + groupW * i + groupW / 2;
        const y = lScale(ds.values[i]);
        if (!started) { ctx.moveTo(x, y); started = true; } else { ctx.lineTo(x, y); }
      }
      ctx.stroke();
      ctx.fillStyle = color;
      for (let i = 0; i < ds.values.length; i++) {
        if (ds.values[i] == null) continue;
        const x = pad.left + groupW * i + groupW / 2;
        ctx.beginPath(); ctx.arc(x, lScale(ds.values[i]), 3, 0, Math.PI * 2); ctx.fill();
      }
    });

    // Y labels
    ctx.fillStyle = t.textMuted; ctx.font = '9px monospace'; ctx.textAlign = 'right';
    for (let i = 0; i <= 4; i++) {
      const v = yMax * (4 - i) / 4;
      ctx.fillText(v % 1 === 0 ? v.toFixed(0) : v.toFixed(1), pad.left - 6, pad.top + plotH * i / 4 + 3);
    }

    // Right axis labels
    if (options.lineOverlay) {
      ctx.textAlign = 'left';
      for (let i = 0; i <= 4; i++) {
        const v = lMin + (lRange * (4 - i) / 4);
        ctx.fillText(v % 1 === 0 ? v.toFixed(0) : v.toFixed(1), pad.left + plotW + 6, pad.top + plotH * i / 4 + 3);
      }
    }

    // X labels
    ctx.textAlign = 'center';
    const xStep = Math.max(1, Math.floor(nGroups / 8));
    for (let i = 0; i < nGroups; i += xStep) {
      const short = data.labels[i].length > 5 ? data.labels[i].slice(5) : data.labels[i];
      ctx.fillText(short, pad.left + groupW * i + groupW / 2, pad.top + plotH + 16);
    }

    // Title
    if (options.title) {
      ctx.fillStyle = t.text; ctx.font = 'bold 11px monospace'; ctx.textAlign = 'left';
      ctx.fillText(options.title, pad.left, pad.top - 10);
    }

    // Legend
    if (options.showLegend !== false && data.datasets.length > 1) {
      ctx.font = '9px monospace'; ctx.textAlign = 'left';
      let lx = pad.left;
      data.datasets.forEach((ds, di) => {
        const color = ds.color || this._palette[di % this._palette.length];
        ctx.fillStyle = color; ctx.fillRect(lx, pad.top + plotH + 28, 10, 8);
        ctx.fillStyle = t.textMuted; ctx.fillText(ds.label, lx + 14, pad.top + plotH + 36);
        lx += ctx.measureText(ds.label).width + 28;
      });
    }
    ctx.textAlign = 'start';
  },

  breakdown(canvasId, data, options) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    if (canvas.parentElement.clientWidth <= 0) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width = canvas.parentElement.clientWidth;
    const H = canvas.height = options.height || Math.max(120, data.items.length * 32 + 40);
    const t = this._getTheme();
    ctx.clearRect(0, 0, W, H);

    if (!data.items || !data.items.length) return this._noData(ctx, W, H, 'No consumption data \u2014 set daily usage on inventory items');

    const pad = {top: 10, right: 20, bottom: 10, left: 10};
    const barH = 22;
    const gap = 8;
    const maxVal = Math.max(...data.items.map(d => d.value)) || 1;
    const labelW = 120;
    const valW = 60;
    const barArea = W - pad.left - pad.right - labelW - valW;

    const green = t.green || '#2f7c68';
    const red = t.red || '#b34d44';
    const orange = t.orange || '#cf7d2f';
    data.items.forEach((item, i) => {
      const y = pad.top + i * (barH + gap);
      // Label
      ctx.fillStyle = t.text; ctx.font = '10px monospace'; ctx.textAlign = 'left';
      ctx.fillText(item.label.slice(0, 16), pad.left, y + barH / 2 + 3);
      // Bar
      const bx = pad.left + labelW;
      const bw = Math.max(2, (item.value / maxVal) * barArea);
      const color = item.value > 90 ? green : item.value > 30 ? orange : red;
      ctx.fillStyle = color;
      ctx.fillRect(bx, y, bw, barH);
      // Value text
      ctx.fillStyle = t.textMuted; ctx.textAlign = 'right';
      ctx.fillText(item.value >= 9999 ? 'N/A' : Math.round(item.value) + 'd', W - pad.right, y + barH / 2 + 3);
    });
    ctx.textAlign = 'start';
  },

  donut(canvasId, data, options) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const size = options.size || 180;
    canvas.width = size;
    canvas.height = size;
    const t = this._getTheme();
    ctx.clearRect(0, 0, size, size);

    if (!data.items || !data.items.length) return this._noData(ctx, size, size, 'No categories');

    const cx = size / 2, cy = size / 2;
    const outerR = size / 2 - 8;
    const innerR = outerR * 0.55;
    const total = data.items.reduce((s, d) => s + d.value, 0) || 1;

    let angle = -Math.PI / 2;
    data.items.forEach((item, i) => {
      const slice = (item.value / total) * Math.PI * 2;
      const color = item.color || this._palette[i % this._palette.length];
      ctx.beginPath();
      ctx.arc(cx, cy, outerR, angle, angle + slice);
      ctx.arc(cx, cy, innerR, angle + slice, angle, true);
      ctx.closePath();
      ctx.fillStyle = color;
      ctx.fill();

      // Label on larger slices
      if (slice > 0.25) {
        const midAngle = angle + slice / 2;
        const lx = cx + Math.cos(midAngle) * (outerR + innerR) / 2;
        const ly = cy + Math.sin(midAngle) * (outerR + innerR) / 2;
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 8px monospace';
        ctx.textAlign = 'center';
        ctx.fillText(item.label.slice(0, 8), lx, ly + 3);
      }
      angle += slice;
    });

    // Center text
    ctx.fillStyle = t.text;
    ctx.font = 'bold 14px monospace';
    ctx.textAlign = 'center';
    ctx.fillText(total.toString(), cx, cy + 2);
    ctx.font = '8px monospace';
    ctx.fillStyle = t.textMuted;
    ctx.fillText('items', cx, cy + 14);
    ctx.textAlign = 'start';
  },

  sparkline(canvasId, values, options) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width = options.width || 120;
    const H = canvas.height = options.height || 30;
    ctx.clearRect(0, 0, W, H);
    const vals = values.filter(v => v != null);
    if (vals.length < 2) return;
    const mn = Math.min(...vals), mx = Math.max(...vals);
    const range = mx - mn || 1;
    const color = options.color || this._getTheme().accent;
    ctx.strokeStyle = color; ctx.lineWidth = 1.5;
    ctx.beginPath();
    vals.forEach((v, i) => {
      const x = (i / (vals.length - 1)) * W;
      const y = H - 2 - ((v - mn) / range) * (H - 4);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();
  },
};

// Attach to window for backward compatibility
window.NomadChart = NomadChart;
