/* ─── Init ─── */
function getActiveWorkspaceTab() {
  return window.NOMAD_ACTIVE_TAB || document.querySelector('.tab.active')?.dataset.tab || '';
}

function isWorkspaceTabActive(tabId) {
  return getActiveWorkspaceTab() === tabId;
}

function hasVisibleStatusStrip() {
  return Array.from(document.querySelectorAll('.status-strip'))
    .some(candidate => candidate && !candidate.hidden && getComputedStyle(candidate).display !== 'none');
}

function revokeObjectUrlSafe(url) {
  if (!url || typeof URL === 'undefined' || typeof URL.revokeObjectURL !== 'function') return;
  try {
    URL.revokeObjectURL(url);
  } catch (_) {}
}

function downloadBlobFile(blob, filename) {
  if (!(blob instanceof Blob) || !filename || typeof URL === 'undefined' || typeof URL.createObjectURL !== 'function') {
    return false;
  }
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.rel = 'noopener';
  document.body.appendChild(link);
  link.click();
  window.setTimeout(() => {
    link.remove();
    revokeObjectUrlSafe(url);
  }, 1000);
  return true;
}

let _iframeHtmlWriteNonce = 0;

function writeIframeHtml(iframe, html, options = {}) {
  if (!iframe || typeof html !== 'string') return false;
  const { scrollTo = '', afterRender = null } = options || {};
  _iframeHtmlWriteNonce += 1;
  const renderToken = String(_iframeHtmlWriteNonce);
  let committed = false;

  iframe.dataset.nomadFrameRenderToken = renderToken;

  if (iframe.__nomadHtmlLoadHandler) {
    try {
      iframe.removeEventListener('load', iframe.__nomadHtmlLoadHandler);
    } catch (_) {}
    iframe.__nomadHtmlLoadHandler = null;
  }

  const finalizeRender = () => {
    if (!iframe.isConnected || iframe.dataset.nomadFrameRenderToken !== renderToken) return false;
    const doc = iframe.contentDocument;
    if (!doc) return false;
    if (scrollTo) {
      const target = doc.getElementById(scrollTo);
      if (target) {
        try {
          target.scrollIntoView({behavior:'smooth', block:'start'});
        } catch (_) {}
      }
    }
    if (typeof afterRender === 'function') {
      try {
        afterRender(iframe, doc);
      } catch (_) {}
    }
    return true;
  };

  const commitHtml = () => {
    if (committed) return true;
    if (!iframe.isConnected || iframe.dataset.nomadFrameRenderToken !== renderToken) return false;
    const doc = iframe.contentDocument;
    if (!doc) return false;
    committed = true;
    try {
      doc.open();
      doc.write(html);
      doc.close();
    } catch (_) {
      return false;
    }
    window.requestAnimationFrame(() => {
      finalizeRender();
    });
    return true;
  };

  const handleBlankLoad = () => {
    if (iframe.__nomadHtmlLoadHandler === handleBlankLoad) {
      iframe.__nomadHtmlLoadHandler = null;
    }
    commitHtml();
  };

  iframe.__nomadHtmlLoadHandler = handleBlankLoad;
  iframe.addEventListener('load', handleBlankLoad, { once: true });
  iframe.src = 'about:blank';
  window.setTimeout(() => {
    commitHtml();
  }, 100);
  return true;
}

function printHtmlInHiddenFrame(html, title = 'Document') {
  if (typeof html !== 'string' || !document.body) return false;
  const frame = document.createElement('iframe');
  frame.setAttribute('aria-hidden', 'true');
  frame.tabIndex = -1;
  frame.style.cssText = 'position:fixed;top:-9999px;left:-9999px;width:0;height:0;border:0;visibility:hidden';
  document.body.appendChild(frame);

  let cleanupTimer = 0;
  let cleanedUp = false;
  let printStarted = false;

  const cleanup = () => {
    if (cleanedUp) return;
    cleanedUp = true;
    window.clearTimeout(cleanupTimer);
    try {
      frame.contentWindow?.removeEventListener('afterprint', cleanup);
    } catch (_) {}
    if (frame.isConnected) frame.remove();
  };

  const startPrint = () => {
    if (cleanedUp || printStarted) return false;
    const win = frame.contentWindow;
    const doc = frame.contentDocument;
    if (!win || !doc) {
      cleanup();
      return false;
    }
    printStarted = true;
    if (title && !doc.title) {
      try {
        doc.title = title;
      } catch (_) {}
    }
    try {
      win.addEventListener('afterprint', cleanup, { once: true });
    } catch (_) {}
    cleanupTimer = window.setTimeout(cleanup, 60000);
    try {
      win.focus();
      win.print();
      return true;
    } catch (_) {
      cleanup();
      return false;
    }
  };

  const wrote = writeIframeHtml(frame, html, {
    afterRender: () => {
      window.setTimeout(() => {
        startPrint();
      }, 0);
    },
  });
  if (!wrote) {
    cleanup();
    return false;
  }
  window.setTimeout(() => {
    startPrint();
  }, 800);
  return true;
}

function renderPopupStatus(popup, title, message, tone = 'info') {
  if (!popup || popup.closed) return false;
  const safeTitle = escapeHtml(title || 'Document');
  const safeMessage = escapeHtml(message || '').replace(/\n/g, '<br>');
  const toneStyles = {
    info: {
      accent: '#1f5c8d',
      panel: '#eef5fb',
      text: '#16324a',
    },
    warning: {
      accent: '#9a5a00',
      panel: '#fff4df',
      text: '#4d2e00',
    },
    error: {
      accent: '#9b1c1c',
      panel: '#fff1f1',
      text: '#5f1414',
    },
  };
  const palette = toneStyles[tone] || toneStyles.info;
  popup.document.open();
  popup.document.write(`<!DOCTYPE html><html><head><meta charset="UTF-8"><title>${safeTitle}</title>
    <style>
      :root{color-scheme:light;}
      body{margin:0;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f4f7fb;color:#102338;display:grid;place-items:center;min-height:100vh;padding:24px;}
      .popup-status{max-width:520px;width:min(100%,520px);background:#fff;border:1px solid rgba(16,35,56,0.12);border-radius:18px;box-shadow:0 24px 60px rgba(16,35,56,0.12);padding:28px 24px;}
      .popup-status-kicker{font-size:11px;letter-spacing:0.16em;text-transform:uppercase;color:${palette.accent};font-weight:700;margin-bottom:10px;}
      .popup-status-title{font-size:24px;line-height:1.2;margin:0 0 10px;}
      .popup-status-copy{background:${palette.panel};color:${palette.text};border-radius:12px;padding:14px 16px;line-height:1.6;}
    </style></head><body>
    <div class="popup-status">
      <div class="popup-status-kicker">NOMAD Field Desk</div>
      <h1 class="popup-status-title">${safeTitle}</h1>
      <div class="popup-status-copy">${safeMessage}</div>
    </div>
  </body></html>`);
  popup.document.close();
  return true;
}

function replacePopupHtml(popup, html) {
  if (!popup || typeof html !== 'string') return false;
  // P1-10: Handle in-app frame proxy from openPendingPopup
  if (popup._nomadAppFrame) {
    const iframe = document.getElementById('app-frame-iframe');
    if (iframe && typeof writeIframeHtml === 'function') return writeIframeHtml(iframe, html);
    try { const doc = iframe?.contentDocument; if (doc) { doc.open(); doc.write(html); doc.close(); return true; } } catch(_) {}
    return false;
  }
  if (popup.closed) return false;
  popup.document.open();
  popup.document.write(html);
  popup.document.close();
  return true;
}

function openPendingPopup(title, loadingMessage = 'Preparing document…') {
  // P1-10: Prefer in-app frame over new window for print preview
  if (typeof openAppFrameHTML === 'function') {
    const loadingHtml = `<!DOCTYPE html><html><head><title>${escapeHtml(title)}</title><style>body{background:#1a1a2e;color:#e0e0e0;font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}.loader{text-align:center}.spin{width:32px;height:32px;border:3px solid #333;border-top:3px solid #4f9cf7;border-radius:50%;animation:s .8s linear infinite}@keyframes s{to{transform:rotate(360deg)}}</style></head><body><div class="loader"><div class="spin"></div><p>${escapeHtml(loadingMessage)}</p></div></body></html>`;
    openAppFrameHTML(title, loadingHtml);
    // Return a proxy object that replacePopupHtml can use
    const iframe = document.getElementById('app-frame-iframe');
    return { document: iframe?.contentDocument || null, _nomadAppFrame: true, close() {}, print() { iframe?.contentWindow?.print(); } };
  }
  const popup = window.open('', '_blank');
  if (!popup) return null;
  renderPopupStatus(popup, title, loadingMessage, 'info');
  return popup;
}

window.revokeObjectUrlSafe = revokeObjectUrlSafe;
window.downloadBlobFile = downloadBlobFile;
window.writeIframeHtml = writeIframeHtml;
window.printHtmlInHiddenFrame = printHtmlInHiddenFrame;
window.renderPopupStatus = renderPopupStatus;
window.replacePopupHtml = replacePopupHtml;
window.openPendingPopup = openPendingPopup;

async function loadServicesWorkspaceCore() {
  const servicesData = await safeFetch('/api/services', {}, []);
  if (!Array.isArray(servicesData)) return [];
  loadServices(servicesData);
  loadReadiness(servicesData);
  loadServiceQuickLinks(servicesData);
  return servicesData;
}

function refreshServicesWorkspacePanels() {
  loadServicesWorkspaceCore();
  loadWidgetConfig().then(() => startLiveDashPolling());
  loadNeedsOverview();
  loadGettingStarted();
  loadCmdDashboard();
  loadCmdChecklists();
  loadActivity();
  loadContentSummary();
  pollDownloadQueue();
}

function refreshSettingsWorkspacePanels() {
  loadSuggestedActions();
}

window.refreshServicesWorkspacePanels = refreshServicesWorkspacePanels;
window.refreshSettingsWorkspacePanels = refreshSettingsWorkspacePanels;

function loadStartupWorkspaceCore(tabId) {
  if (!tabId) return;
  if (tabId === 'services') {
    loadServicesWorkspaceCore();
    return;
  }
  requestAnimationFrame(() => {
    const startupTab = document.querySelector(`.tab[data-tab="${tabId}"]`);
    if (startupTab && typeof activateWorkspaceTab === 'function') activateWorkspaceTab(startupTab);
  });
}

// Critical: only load the visible workspace up front.
const _startupWorkspaceTab = getActiveWorkspaceTab();
// Mark Home as initialized because it uses the lighter startup path below.
if (typeof _tabInitialized !== 'undefined' && _startupWorkspaceTab === 'services') _tabInitialized[_startupWorkspaceTab] = true;
loadStartupWorkspaceCore(_startupWorkspaceTab);
// Defer secondary workspace data so non-home launches do not fetch hidden panels.
setTimeout(() => {
  const _c = e => console.warn('[Init]', e.message || e);
  if (isWorkspaceTabActive('services')) {
    Promise.resolve(loadServicesWorkspaceCore()).catch(_c);
    loadWidgetConfig().then(() => startLiveDashPolling()).catch(_c);
    Promise.resolve(loadNeedsOverview()).catch(_c);
    Promise.resolve(loadGettingStarted()).catch(_c);
    Promise.resolve(loadCmdDashboard()).catch(_c);
    Promise.resolve(loadCmdChecklists()).catch(_c);
  }
  if (isWorkspaceTabActive('settings')) Promise.resolve(refreshSettingsWorkspacePanels()).catch(_c);
}, 500);
setTimeout(() => {
  const _c = e => console.warn('[Init]', e.message || e);
  if (isWorkspaceTabActive('services')) {
    Promise.resolve(loadActivity()).catch(_c);
    Promise.resolve(loadContentSummary()).catch(_c);
  }
  if (hasVisibleStatusStrip()) Promise.resolve(updateStatusStrip()).catch(_c);
  Promise.resolve(updateTabBadges()).catch(_c);
}, 1000);
const shellRuntime = window.NomadShellRuntime;
if (shellRuntime) {
  shellRuntime.startInterval('shell.status-strip', () => {
    if (hasVisibleStatusStrip()) updateStatusStrip();
    updateTabBadges();
  }, 30000, { requireVisible: true });
  shellRuntime.startInterval('services.download-queue', () => {
    pollDownloadQueue();
  }, 5000, { tabId: 'services', requireVisible: true });
  shellRuntime.startInterval('services.workspace-refresh', () => {
    loadServicesWorkspaceCore();
    loadCmdDashboard();
  }, 8000, { tabId: 'services', requireVisible: true });
  shellRuntime.startInterval('shell.network', () => {
    checkNetwork();
  }, 30000, { requireVisible: true });
  shellRuntime.startInterval('shell.broadcast', () => {
    pollBroadcast();
  }, 5000, { requireVisible: true });
} else {
  setInterval(() => {
    if (!document.hidden) {
      if (hasVisibleStatusStrip()) updateStatusStrip();
      updateTabBadges();
    }
  }, 30000);
  setInterval(() => {
    if (!document.hidden && isWorkspaceTabActive('services')) pollDownloadQueue();
  }, 5000);
  setInterval(() => {
    if (document.hidden || !isWorkspaceTabActive('services')) return;
    loadServicesWorkspaceCore();
    loadCmdDashboard();
  }, 8000);
  setInterval(() => { if (!document.hidden) checkNetwork(); }, 30000);
  setInterval(() => { if (!document.hidden) pollBroadcast(); }, 5000);
}
checkNetwork();
checkWizard();
checkForUpdate();
// Auto-update toast notification (fires after checkForUpdate sets banner)
(async () => {
  try {
    const d = await safeFetch('/api/update-check', {}, null);
    if (!d?.update_available) return;
    toast('Update available: v' + escapeHtml(d.latest), 'info');
  } catch(_) {}
})();
loadStartupState();
if (_startupWorkspaceTab === 'services') pollDownloadQueue();
pollBroadcast();

// Proactive alert system — handled via NomadEvents 'alert_check' event
setTimeout(loadAlerts, 5000);

// ═══════════════════════════════════════════════════════════════
// BALLISTICS CALCULATOR
// ═══════════════════════════════════════════════════════════════
function calcBallistics() {
  const caliberSelect = document.getElementById('bal-caliber');
  const zeroInput = document.getElementById('bal-zero');
  const windInput = document.getElementById('bal-wind');
  const resultEl = document.getElementById('bal-result');
  if (!caliberSelect || !zeroInput || !windInput || !resultEl) return;
  const selectedValue = caliberSelect.value;
  const selectedOption = caliberSelect.options[caliberSelect.selectedIndex];
  if (!selectedValue || !selectedOption) return;
  const sel = selectedValue.split(',');
  const name = selectedOption.text;
  const bulletWt = parseFloat(sel[1]);
  const muzzleV = parseFloat(sel[2]);
  const zeroYd = parseFloat(zeroInput.value) || 100;
  const windMph = parseFloat(windInput.value) || 0;
  // Simple ballistic coefficient approximations by caliber type
  const bcMap = {'5.56':0.304,'7.62':0.475,'30-06':0.41,'300blk':0.275,'9mm':0.165,'45acp':0.195,'22lr':0.14,'12ga-slug':0.12};
  const calKey = sel[0];
  const bc = bcMap[calKey] || 0.3;
  // Using simplified point-mass ballistics (flat-fire approximation)
  const g = 32.174; // ft/s²
  const ranges = [0,50,100,150,200,250,300,400,500];
  const rows = ranges.map(yd => {
    const ft = yd * 3;
    const tof = ft / muzzleV; // simplified
    const drop_in = -0.5 * g * tof * tof * 12; // inches, negative = below LOS
    // Velocity at range (simplified exponential decay)
    const vr = muzzleV * Math.exp(-1.25 * ft / (bc * 1000));
    const energy = Math.round((bulletWt * vr * vr) / 450437);
    // Elevation vs zero (drop relative to zero point)
    const zeroDrop = -0.5 * g * ((zeroYd*3)/muzzleV) * ((zeroYd*3)/muzzleV) * 12;
    const poi = drop_in - zeroDrop; // POI relative to zero
    // Wind drift: simplified 10mph right-angle wind = W * T * (V-Vr)/V inches
    const windDrift = windMph > 0 ? ((windMph/10) * tof * (muzzleV-vr)/muzzleV * 12).toFixed(1) : '0';
    const poiToneClass = poi > 0 ? 'prep-reference-good' : poi < -3 ? 'fallout-rate-warn' : '';
    return `<tr>
      <td>${yd}</td>
      <td>${Math.round(vr)}</td>
      <td>${energy}</td>
      <td class="${poiToneClass}">${poi>0?'+':''}${poi.toFixed(1)}"</td>
      <td>${windDrift}"</td>
    </tr>`;
  }).join('');
  resultEl.innerHTML = `
    <div class="prep-reference-callout prep-reference-callout-info">${name} | Zero: ${zeroYd}yd | Wind: ${windMph}mph crosswind</div>
    <div class="prep-table-wrap"><table class="prep-data-table prep-reference-table-compact prep-calc-table prep-calc-table-center">
      <thead><tr>
        <th>Range (yd)</th>
        <th>Velocity (fps)</th>
        <th>Energy (ft-lb)</th>
        <th>POI (in)</th>
        <th>Wind Drift (in)</th>
      </tr></thead><tbody>${rows}</tbody>
    </table></div>
    <div class="prep-reference-callout prep-reference-callout-warn">Estimates only. Actual results vary with barrel length, altitude, temperature, and actual BC. Verify with live fire.</div>`;
}

// ═══════════════════════════════════════════════════════════════
// COMPOSTING CALCULATOR
// ═══════════════════════════════════════════════════════════════
function calcCompost() {
  const brownsInput = document.getElementById('comp-browns');
  const greensInput = document.getElementById('comp-greens');
  const volumeInput = document.getElementById('comp-vol');
  const resultEl = document.getElementById('comp-result');
  if (!brownsInput || !greensInput || !volumeInput || !resultEl) return;
  const browns = parseFloat(brownsInput.value) || 0;
  const greens = parseFloat(greensInput.value) || 0;
  const vol = parseFloat(volumeInput.value) || 1;
  if (!browns && !greens) { resultEl.innerHTML = ''; return; }
  // C:N ratios: browns ~50:1, greens ~15:1
  const totalN = browns / 50 + greens / 15;
  const cn = totalN > 0 ? Math.round((browns * 50 + greens * 15) / (browns + greens)) : 50;
  const ideal = cn >= 25 && cn <= 35;
  const tooCarbon = cn > 35;
  const wColor = ideal ? 'var(--green)' : tooCarbon ? 'var(--orange)' : 'var(--red)';
  const advice = ideal ? 'Ratio is ideal. Pile should heat up within 3-5 days.' :
    tooCarbon ? `Too much carbon (${cn}:1). Add more greens: kitchen scraps, fresh grass, manure.` :
    `Too much nitrogen (${cn}:1). Add more browns: dry leaves, cardboard, straw.`;
  const days = ideal ? '30-60' : tooCarbon ? '90-180' : '45-90';
  // Volume check — minimum 3×3×3 ft (27 cu ft) for thermophilic composting
  const volOK = vol >= 27;
  const ratioToneClass = ideal ? 'prep-summary-card-ok' : tooCarbon ? 'utility-summary-card-alert' : 'prep-summary-card-danger';
  const adviceToneClass = ideal ? 'prep-reference-callout-safe' : tooCarbon ? 'prep-reference-callout-warn' : 'prep-reference-callout-danger';
  const volumeToneClass = volOK ? 'prep-summary-card-ok' : 'utility-summary-card-alert';
  resultEl.innerHTML = `
    <div class="utility-summary-result utility-summary-grid">
      <div class="prep-summary-card utility-summary-card ${ratioToneClass}">
        <div class="prep-summary-meta">C:N Ratio</div>
        <div class="prep-summary-value">${cn}:1</div>
        <div class="prep-summary-label">ideal 25-35:1</div>
      </div>
      <div class="prep-summary-card utility-summary-card ${volumeToneClass}">
        <div class="prep-summary-meta">Pile Volume</div>
        <div class="prep-summary-value">${vol} cu ft</div>
        <div class="prep-summary-label">${volOK ? 'hot-compost capable' : 'cold-compost pace'}</div>
      </div>
      <div class="prep-summary-card utility-summary-card">
        <div class="prep-summary-meta">Decomposition</div>
        <div class="prep-summary-value prep-summary-value-compact">${days} days</div>
        <div class="prep-summary-label">with regular turning</div>
      </div>
    </div>
    <div class="prep-reference-callout ${adviceToneClass}">${advice}</div>
    <div class="prep-reference-callout ${volOK ? 'prep-reference-callout-safe' : 'prep-reference-callout-warn'}">Pile Volume: <strong>${vol} cu ft</strong> — ${volOK ? 'Sufficient for thermophilic (hot) composting.' : 'Too small for hot composting (&lt;27 cu ft). It will cold-compost slowly.'}</div>`;
}

// ═══════════════════════════════════════════════════════════════
// PASTURE ROTATION CALCULATOR
// ═══════════════════════════════════════════════════════════════
function calcPastureRotation() {
  const acresInput = document.getElementById('pr-acres');
  const auInput = document.getElementById('pr-au');
  const paddocksInput = document.getElementById('pr-paddocks');
  const seasonInput = document.getElementById('pr-season');
  const resultEl = document.getElementById('pr-result');
  if (!acresInput || !auInput || !paddocksInput || !seasonInput || !resultEl) return;
  const acres = parseFloat(acresInput.value) || 1;
  const au = parseFloat(auInput.value) || 1; // Animal Units (1 AU = 1000 lb cow)
  const paddocks = parseInt(paddocksInput.value) || 4;
  const season = seasonInput.value;
  // Stocking rate: warm season ~1.5 acres/AU, cool season ~2.5 acres/AU
  const acresPerAU = season === 'warm' ? 1.5 : 2.5;
  const restDays = season === 'warm' ? 21 : 60;
  const grazeDays = restDays / (paddocks - 1);
  const acresPerPaddock = acres / paddocks;
  const capacityAU = acresPerPaddock / acresPerAU;
  const totalCapacity = capacityAU * paddocks;
  const adequate = au <= totalCapacity * 0.8;
  const statusToneClass = adequate ? 'prep-summary-card-ok' : 'prep-summary-card-danger';
  const statusCopy = adequate
    ? `Adequate for ${au} AU. ${((totalCapacity*0.8-au)/totalCapacity*100).toFixed(0)}% below safe stocking limit.`
    : `Overstocked. Max safe load: ${(totalCapacity*0.8).toFixed(1)} AU. Reduce by ${(au - totalCapacity*0.8).toFixed(1)} AU or add ${Math.ceil((au*acresPerAU*paddocks/0.8 - acres)/acresPerPaddock)} paddocks.`;
  resultEl.innerHTML = `
    <div class="utility-summary-result utility-summary-grid">
      <div class="prep-summary-card utility-summary-card">
        <div class="prep-summary-meta">Acres / paddock</div>
        <div class="prep-summary-value">${acresPerPaddock.toFixed(1)}</div>
        <div class="prep-summary-label">usable rotation slice</div>
      </div>
      <div class="prep-summary-card utility-summary-card">
        <div class="prep-summary-meta">Graze days</div>
        <div class="prep-summary-value">${grazeDays.toFixed(1)}</div>
        <div class="prep-summary-label">per paddock</div>
      </div>
      <div class="prep-summary-card utility-summary-card">
        <div class="prep-summary-meta">Rest period</div>
        <div class="prep-summary-value">${restDays}</div>
        <div class="prep-summary-label">days between grazes</div>
      </div>
      <div class="prep-summary-card utility-summary-card">
        <div class="prep-summary-meta">Carrying capacity</div>
        <div class="prep-summary-value">${totalCapacity.toFixed(1)} AU</div>
        <div class="prep-summary-label">total herd load</div>
      </div>
      <div class="prep-summary-card utility-summary-card ${statusToneClass} prep-summary-card-wide">
        <div class="prep-summary-meta">Stocking Assessment</div>
        <div class="prep-summary-value prep-summary-value-compact">${adequate ? 'Adequate' : 'Overstocked'}</div>
        <div class="prep-summary-label">${statusCopy}</div>
      </div>
    </div>
    <div class="prep-reference-callout prep-reference-callout-info">Rotation schedule: move to the next paddock every ${grazeDays.toFixed(1)} days. Never graze below 3-4 inches (warm season) or 4-5 inches (cool season). One Animal Unit (AU) equals a 1,000 lb cow or equivalent.</div>`;
}

// ═══════════════════════════════════════════════════════════════
// NATURAL BUILDING CALCULATOR
// ═══════════════════════════════════════════════════════════════
function calcNaturalBuilding() {
  const methodInput = document.getElementById('nb-method');
  const lengthInput = document.getElementById('nb-length');
  const heightInput = document.getElementById('nb-height');
  const thicknessInput = document.getElementById('nb-thick');
  const resultEl = document.getElementById('nb-result');
  if (!methodInput || !lengthInput || !heightInput || !thicknessInput || !resultEl) return;
  const method = methodInput.value;
  const length = parseFloat(lengthInput.value) || 0;
  const height = parseFloat(heightInput.value) || 0;
  const thick = parseFloat(thicknessInput.value) || 14;
  const wallArea = length * height; // sq ft
  let html = '';
  if (method === 'adobe') {
    // Standard adobe: 10×4×14 inch brick, ~2-3 lbs clay mix per brick
    const brickVol = (10/12) * (4/12) * (14/12); // cu ft
    const wallVol = wallArea * (thick/12); // cu ft
    const mortarFactor = 0.8; // bricks fill ~80% of wall volume
    const numBricks = Math.ceil(wallVol * mortarFactor / brickVol);
    const clayYards = Math.ceil(wallVol * 0.037); // cu yards of clay-sand mix
    html = `<div><strong>Adobe Brick Wall</strong></div>
      <div>Wall area: ${wallArea.toFixed(0)} sq ft | Volume: ${(wallVol).toFixed(1)} cu ft</div>
      <div>Bricks needed: <strong>${numBricks.toLocaleString()}</strong> (10×4×14 in)</div>
      <div>Clay-sand mix: ~<strong>${clayYards} cu yd</strong> (3 parts sand : 1 part clay : straw)</div>
      <div class="copy-dim-note">Adobe production rate: 100-200 bricks/person/day. Cure 2-4 weeks before laying. Plaster both sides with 1-inch earth plaster. Adobe is not waterproof — roof overhang critical (min 18 in).</div>`;
  } else if (method === 'cob') {
    const wallVol = wallArea * (thick/12);
    const yds = Math.ceil(wallVol / 27);
    const sand_bags = Math.ceil(yds * 0.6 * 27); // approx
    html = `<div><strong>Cob Wall (monolithic)</strong></div>
      <div>Wall area: ${wallArea.toFixed(0)} sq ft | Volume: ${wallVol.toFixed(1)} cu ft (${yds} cu yd)</div>
      <div>Clay-sand-straw mix: ~<strong>${yds} cu yd</strong></div>
      <div class="copy-dim-note">Mix: 2 parts subsoil (with clay) + 1 part sand + straw for fiber. Test: squeeze a ball — if it holds shape and doesn't crack when dry, clay content is right. Build in 6-8 inch lifts, allow each to firm before next. Cob is slow — 1-2 cu ft/hour per person.</div>`;
  } else {
    // Straw bale: 2-string bale = 14×18×36 inches
    const baleVol = (14/12) * (18/12) * (36/12); // cu ft
    const wallVol = wallArea * (thick/12);
    const numBales = Math.ceil(wallArea / ((36/12) * (18/12))); // bales per sq ft of wall face
    html = `<div><strong>Straw Bale Wall</strong></div>
      <div>Wall area: ${wallArea.toFixed(0)} sq ft</div>
      <div>Bales needed: <strong>${numBales}</strong> (2-string 14×18×36 in)</div>
      <div>Plaster needed: ~<strong>${Math.ceil(wallArea * 2 * 0.04)} cu yd</strong> (both sides, 1.5 in earth/lime plaster)</div>
      <div class="copy-dim-note">Straw bale: R-value ~R-30 (far superior to adobe or cob). Must be kept dry — moisture is fatal. Use a rubble trench foundation raised 18+ inches above grade. Pin bales with rebar stakes. Plaster immediately after stacking to prevent wetting.</div>`;
  }
  resultEl.innerHTML = html;
}

// ═══════════════════════════════════════════════════════════════
// NUCLEAR FALLOUT DOSE CALCULATOR (7-10 Rule)
// ═══════════════════════════════════════════════════════════════
function calcFallout() {
  const rateInput = document.getElementById('fall-h1');
  const shelterInput = document.getElementById('fall-shelter');
  const hoursInput = document.getElementById('fall-hours');
  const resultEl = document.getElementById('fall-result');
  if (!rateInput || !shelterInput || !hoursInput || !resultEl) return;
  const h1Rate = parseFloat(rateInput.value) || 0;
  const pf = parseFloat(shelterInput.value) || 1;
  const hours = parseFloat(hoursInput.value) || 1;
  if (!h1Rate) { resultEl.innerHTML = ''; return; }
  // 7-10 Rule: rate at time T = H1_rate * (T ^ -1.2)
  const rateAtT = h1Rate * Math.pow(hours, -1.2);
  const shelteredRate = rateAtT / pf;
  const exitSafeRate = 2; // R/hr — generally safe for limited exposure
  const hoursToSafe = Math.pow(h1Rate / exitSafeRate, 1/1.2);
  const hoursToVerySafe = Math.pow(h1Rate / 0.1, 1/1.2);
  const colorRate = shelteredRate < 0.5 ? 'var(--green)' : shelteredRate < 5 ? 'var(--orange)' : 'var(--red)';
  // Dose accumulation estimate for 24h shelter stay
  let cum24h = 0;
  for (let h = 1; h <= 24; h++) {
    cum24h += h1Rate * Math.pow(h, -1.2) / pf;
  }
  const rows = [1,2,4,7,12,24,48,168,336,720].map(h => {
    const rate = h1Rate * Math.pow(h, -1.2);
    const sRate = (rate / pf).toFixed(3);
    const sRateNum = parseFloat(sRate);
    const rateToneClass = sRateNum < 0.1 ? 'prep-reference-good' : sRateNum < 2 ? 'fallout-rate-warn' : 'prep-reference-bad';
    return `<tr>
      <td>H+${h < 24 ? h+'hr' : (h/24)+'d'}</td>
      <td>${rate.toFixed(3)}</td>
      <td class="fallout-rate ${rateToneClass}">${sRate}</td>
    </tr>`;
  }).join('');
  const shelteredToneClass = shelteredRate < 0.5 ? 'prep-summary-card-ok' : shelteredRate < 5 ? 'utility-summary-card-alert' : 'prep-summary-card-danger';
  const cumDoseToneClass = cum24h > 25 ? 'prep-reference-callout-danger' : cum24h > 5 ? 'prep-reference-callout-warn' : 'prep-reference-callout-safe';
  const cumDoseStatus = cum24h > 25 ? 'HIGH — health risk' : cum24h > 5 ? 'moderate' : 'low risk';
  resultEl.innerHTML = `
    <div class="utility-summary-result utility-summary-grid fallout-result-summary">
      <div class="prep-summary-card utility-summary-card ${shelteredToneClass}">
        <div class="prep-summary-meta">Dose rate now (H+${hours}hr)</div>
        <div class="prep-summary-value">${shelteredRate.toFixed(3)} R/hr</div>
        <div class="prep-summary-label">in shelter (PF ${pf})</div>
      </div>
      <div class="prep-summary-card utility-summary-card">
        <div class="prep-summary-meta">Exit viable</div>
        <div class="prep-summary-value">H+${hoursToSafe.toFixed(1)}hr</div>
        <div class="prep-summary-label">&lt;2 R/hr outside</div>
      </div>
      <div class="prep-summary-card utility-summary-card">
        <div class="prep-summary-meta">Freely exit</div>
        <div class="prep-summary-value">H+${hoursToVerySafe > 720 ? '30+ days' : hoursToVerySafe.toFixed(0)+'hr'}</div>
        <div class="prep-summary-label">&lt;0.1 R/hr outside</div>
      </div>
    </div>
    <div class="prep-reference-callout ${cumDoseToneClass} fallout-dose-note">Estimated cumulative dose in 24hr shelter stay: <strong>${cum24h.toFixed(2)} rem</strong> <span>${cumDoseStatus}</span></div>
    <div class="prep-table-wrap">
      <table class="prep-data-table prep-reference-table-compact fallout-result-table">
        <thead><tr>
          <th>Time</th>
          <th>Outside (R/hr)</th>
          <th>In Shelter (R/hr)</th>
        </tr></thead><tbody>${rows}</tbody>
      </table>
    </div>`;
}

// ═══════════════════════════════════════════════════════════════
// CANNING CALCULATOR
// ═══════════════════════════════════════════════════════════════
function calcCanning() {
  const foodSelect = document.getElementById('can-food');
  const poundsInput = document.getElementById('can-lbs');
  const jarInput = document.getElementById('can-jar');
  const altitudeInput = document.getElementById('can-alt');
  const resultEl = document.getElementById('can-result');
  if (!foodSelect || !poundsInput || !jarInput || !altitudeInput || !resultEl) return;
  const selectedValue = foodSelect.value;
  const selectedOption = foodSelect.options[foodSelect.selectedIndex];
  if (!selectedValue || !selectedOption) return;
  const foodSel = selectedValue.split(',');
  const foodName = selectedOption.text;
  const lbsPerJar = parseFloat(foodSel[1]);
  const baseTime = parseInt(foodSel[2]);
  const method = foodSel[3]; // 'wb' = water bath, 'pc' = pressure canner
  const lbs = parseFloat(poundsInput.value) || 0;
  const jarSize = parseFloat(jarInput.value);
  const altitude = parseInt(altitudeInput.value) || 0;
  const numJars = Math.ceil(lbs / (lbsPerJar * jarSize));
  // Altitude time adjustment for water bath (every 1000 ft above 1000 ft = +5 min)
  let timeAdj = 0;
  if (method === 'wb') {
    if (altitude >= 6000) timeAdj = 20;
    else if (altitude >= 3000) timeAdj = 10;
    else if (altitude >= 1000) timeAdj = 5;
  }
  // Pressure canner: altitude raises required pressure (not time for most)
  const finalTime = baseTime + timeAdj;
  const methodLabel = method === 'wb' ? 'Water Bath Canner' : 'Pressure Canner';
  const pressurePSI = method === 'pc' ? (altitude >= 6000 ? 15 : altitude >= 2001 ? 12 : 10) : null;
  resultEl.innerHTML = `
    <div class="utility-summary-result utility-summary-grid canning-result-summary">
      <div class="prep-summary-card utility-summary-card">
        <div class="prep-summary-meta">Jars needed</div>
        <div class="prep-summary-value">${numJars}</div>
        <div class="prep-summary-label">${jarSize===0.5?'half-pints':jarSize===1?'pints':'quarts'}</div>
      </div>
      <div class="prep-summary-card utility-summary-card">
        <div class="prep-summary-meta">Process time</div>
        <div class="prep-summary-value">${finalTime} min</div>
        <div class="prep-summary-label">${methodLabel}</div>
      </div>
      ${pressurePSI ? `<div class="prep-summary-card utility-summary-card">
        <div class="prep-summary-meta">Pressure</div>
        <div class="prep-summary-value">${pressurePSI} PSI</div>
        <div class="prep-summary-label">at ${altitude===0?'sea level':altitude+' ft+'}</div>
      </div>` : ''}
    </div>
    <div class="prep-reference-callout prep-reference-callout-info canning-result-note"><strong>Notes for ${foodName}:</strong> ${method==='wb'?'Water bath canning is safe ONLY for high-acid foods (pH &lt; 4.6). Always use tested recipes. Do not reduce headspace or processing times.':'Pressure canning required for low-acid foods. Botulism spores cannot be destroyed at boiling temperatures (212°F). Pressure canner reaches 240°F+ which kills all pathogens.'}</div>
    ${timeAdj > 0 ? `<div class="prep-reference-callout prep-reference-callout-warn canning-result-note">Altitude adjustment: +${timeAdj} min added for ${altitude}+ ft elevation.</div>` : ''}`;
}

// ═══════════════════════════════════════════════════════════════
// EMERGENCY PHRASE TRANSLATOR
// ═══════════════════════════════════════════════════════════════
const _phrases = {
  es: {name:'Spanish', phrases: [
    ['Help!', '¡Ayuda! [ah-YOO-dah]'],
    ['I need a doctor.', 'Necesito un médico. [neh-seh-SEE-toh oon MEH-dee-koh]'],
    ['Call an ambulance!', '¡Llame una ambulancia! [YAH-meh OO-nah am-boo-LAN-syah]'],
    ['I am injured.', 'Estoy herido/a. [es-TOY eh-REE-doh]'],
    ['Where is the hospital?', '¿Dónde está el hospital? [DON-deh es-TAH el os-pee-TAHL]'],
    ['Water! / Food!', '¡Agua! / ¡Comida! [AH-gwah / koh-MEE-dah]'],
    ['I am lost.', 'Estoy perdido/a. [es-TOY pehr-DEE-doh]'],
    ['Danger! / Fire!', '¡Peligro! / ¡Fuego! [peh-LEE-groh / FWEH-goh]'],
    ['Police / Military', 'Policía / Ejército [poh-lee-SEE-ah / eh-HEHR-see-toh]'],
    ['I am American.', 'Soy americano/a. [soy ah-meh-ree-KAH-noh]'],
    ['Do you speak English?', '¿Habla inglés? [AH-blah een-GLAYS]'],
    ['Do not shoot!', '¡No dispare! [noh dees-PAH-reh]'],
    ['I surrender.', 'Me rindo. [meh REEN-doh]'],
    ['We need shelter.', 'Necesitamos refugio. [neh-seh-see-TAH-mohs reh-FOO-hyoh]'],
    ['Where is safety?', '¿Dónde está la seguridad? [DON-deh es-TAH lah seh-goo-ree-DAHD]'],
  ]},
  fr: {name:'French', phrases: [
    ['Help!', 'Au secours! [oh suh-KOOR]'],
    ['I need a doctor.', "J'ai besoin d'un médecin. [zhay buh-ZWAN dun mayd-SAN]"],
    ['Call an ambulance!', 'Appelez une ambulance! [ah-play OON am-byoo-LAHNS]'],
    ['I am injured.', 'Je suis blessé(e). [zhuh swee bleh-SAY]'],
    ['Where is the hospital?', "Où est l'hôpital? [oo ay loh-pee-TAHL]"],
    ['Water! / Food!', 'De l\'eau! / De la nourriture! [duh LOH / duh lah noo-ree-TOOR]'],
    ['I am lost.', 'Je suis perdu(e). [zhuh swee pehr-DY]'],
    ['Danger! / Fire!', 'Danger! / Au feu! [dahn-ZHAY / oh FUH]'],
    ['Police / Military', 'Police / Militaires [poh-LEES / mee-lee-TEHR]'],
    ['I am American.', 'Je suis américain(e). [zhuh swee ah-may-ree-KAN]'],
    ['Do you speak English?', 'Parlez-vous anglais? [par-lay voo ahn-GLAY]'],
    ['Do not shoot!', 'Ne tirez pas! [nuh tee-RAY pah]'],
    ['I surrender.', 'Je me rends. [zhuh muh rahn]'],
    ['We need shelter.', 'Nous avons besoin d\'un abri. [noo zahv-on buh-ZWAN dun ah-BREE]'],
    ['Where is safety?', 'Où est-il sûr? [oo ay-TEEL syoor]'],
  ]},
  de: {name:'German', phrases: [
    ['Help!', 'Hilfe! [HIL-feh]'],
    ['I need a doctor.', 'Ich brauche einen Arzt. [ikh BROW-kheh EYE-nen artst]'],
    ['Call an ambulance!', 'Rufen Sie einen Krankenwagen! [ROO-fen zee EYE-nen KRAN-ken-vah-gen]'],
    ['I am injured.', 'Ich bin verletzt. [ikh bin fehr-LETST]'],
    ['Where is the hospital?', 'Wo ist das Krankenhaus? [vo ist das KRAN-ken-hows]'],
    ['Water! / Food!', 'Wasser! / Essen! [VAS-ser / ES-sen]'],
    ['I am lost.', 'Ich habe mich verirrt. [ikh HAH-beh mikh fehr-IRT]'],
    ['Danger! / Fire!', 'Gefahr! / Feuer! [geh-FAR / FOY-er]'],
    ['Do not shoot!', 'Nicht schießen! [nikht SHEE-sen]'],
    ['I surrender.', 'Ich ergebe mich. [ikh ehr-GAY-beh mikh]'],
    ['Do you speak English?', 'Sprechen Sie Englisch? [SHPREH-khen zee ENG-lish]'],
    ['We need help.', 'Wir brauchen Hilfe. [veer BROW-khen HIL-feh]'],
    ['I am American.', 'Ich bin Amerikaner(in). [ikh bin ah-meh-ree-KAH-ner]'],
    ['Where is safety?', 'Wo ist es sicher? [vo ist es ZI-kher]'],
    ['Police / Military', 'Polizei / Militär [po-lee-TSY / mee-lee-TEHR]'],
  ]},
  pt: {name:'Portuguese', phrases: [
    ['Help!', 'Socorro! [so-KO-hoo]'],
    ['I need a doctor.', 'Preciso de um médico. [preh-SEE-zoo deh oom MEH-dee-koo]'],
    ['Call an ambulance!', 'Chame uma ambulância! [SHA-meh OO-mah am-boo-LAN-syah]'],
    ['I am injured.', 'Estou ferido/a. [es-TOH feh-REE-doo]'],
    ['Where is the hospital?', 'Onde é o hospital? [ON-deh eh oo os-pee-TAHL]'],
    ['Water! / Food!', 'Água! / Comida! [AH-gwah / koh-MEE-dah]'],
    ['Danger! / Fire!', 'Perigo! / Fogo! [peh-REE-goo / FO-goo]'],
    ['Do not shoot!', 'Não atire! [nowm ah-TEE-reh]'],
    ['I surrender.', 'Eu me rendo. [eh-oo meh HEN-doo]'],
    ['Do you speak English?', 'Fala inglês? [FAH-lah een-GLAYS]'],
    ['I am American.', 'Sou americano/a. [soh ah-meh-ree-KAH-noo]'],
    ['Police / Military', 'Polícia / Militares [poh-LEE-syah / mee-lee-TAH-rehs]'],
    ['We need shelter.', 'Precisamos de abrigo. [preh-see-ZAH-mohs deh ah-BREE-goo]'],
    ['I am lost.', 'Estou perdido/a. [es-TOH pehr-DEE-doo]'],
    ['Where is safety?', 'Onde é seguro? [ON-deh eh seh-GOO-roo]'],
  ]},
  ru: {name:'Russian', phrases: [
    ['Help!', 'Помогите! [pah-mah-GEE-tye]'],
    ['I need a doctor.', 'Мне нужен врач. [mnyeh NOO-zhen vrach]'],
    ['Call an ambulance!', 'Вызовите скорую! [VY-zah-vee-tye SKO-roo-yoo]'],
    ['I am injured.', 'Я ранен/а. [ya RAH-nyen]'],
    ['Where is the hospital?', 'Где больница? [gdye bol-NEE-tsah]'],
    ['Water! / Food!', 'Воды! / Еды! [vah-DY / yeh-DY]'],
    ['Danger! / Fire!', 'Опасность! / Пожар! [ah-PAS-nost / pah-ZHAR]'],
    ['Do not shoot!', 'Не стреляйте! [nyeh strye-LYAY-tye]'],
    ['I surrender.', 'Я сдаюсь. [ya zdah-YOOS]'],
    ['Do you speak English?', 'Вы говорите по-английски? [vy gah-vah-REE-tye pah-ahng-GLIY-ski]'],
    ['I am American.', 'Я американец/ка. [ya ah-myer-ee-KAH-nyets]'],
    ['Police / Military', 'Полиция / Военные [pah-LEE-tsee-yah / vah-YEN-ny-ye]'],
    ['We need help.', 'Нам нужна помощь. [nam noozh-NAH POH-mahsh]'],
    ['I am lost.', 'Я заблудился/ась. [ya zah-bloo-DEEL-sya]'],
    ['Where is safety?', 'Где безопасно? [gdye byez-ah-PAS-nah]'],
  ]},
  ar: {name:'Arabic', phrases: [
    ['Help!', 'النجدة! [an-NAJ-dah]'],
    ['I need a doctor.', 'أحتاج طبيب. [akh-TAJ ta-BEEB]'],
    ['Call an ambulance!', 'اتصل بالإسعاف! [IT-ta-sil bil-is-AAF]'],
    ['I am injured.', 'أنا مجروح. [AH-na maj-ROOH]'],
    ['Where is the hospital?', 'أين المستشفى؟ [AY-na al-mus-TASH-fa]'],
    ['Water! / Food!', 'ماء! / طعام! [MA-ah / ta-AAM]'],
    ['Danger! / Fire!', 'خطر! / حريق! [KHA-tar / ha-REEK]'],
    ['Do not shoot!', 'لا تطلق النار! [la TUT-liq an-nar]'],
    ['I surrender.', 'أنا أستسلم. [AH-na as-TAS-lim]'],
    ['Do you speak English?', 'هل تتكلم الإنجليزية؟ [hal ta-TAK-lam al-ing-lee-ZEE-ya]'],
    ['I am American.', 'أنا أمريكي. [AH-na am-REE-kee]'],
    ['Police / Military', 'الشرطة / الجيش [ash-SHUR-ta / al-JAYSH]'],
    ['We need shelter.', 'نحتاج ملجأ. [nakh-TAJ MAL-ja]'],
    ['I am lost.', 'أنا ضائع. [AH-na DA-i]'],
    ['Where is safety?', 'أين الأمان؟ [AY-na al-AH-man]'],
  ]},
  zh: {name:'Mandarin Chinese', phrases: [
    ['Help!', '救命! [jiù mìng]'],
    ['I need a doctor.', '我需要医生。[wǒ xūyào yīshēng]'],
    ['Call an ambulance!', '叫救护车! [jiào jiùhùchē]'],
    ['I am injured.', '我受伤了。[wǒ shòushāng le]'],
    ['Where is the hospital?', '医院在哪里? [yīyuàn zài nǎlǐ]'],
    ['Water! / Food!', '水! / 食物! [shuǐ / shíwù]'],
    ['Danger! / Fire!', '危险! / 火! [wēixiǎn / huǒ]'],
    ['Do not shoot!', '不要开枪! [bùyào kāiqiāng]'],
    ['I surrender.', '我投降。[wǒ tóuxiáng]'],
    ['Do you speak English?', '你会说英语吗? [nǐ huì shuō yīngyǔ ma]'],
    ['I am American.', '我是美国人。[wǒ shì měiguó rén]'],
    ['Police / Military', '警察 / 军队 [jǐngchá / jūnduì]'],
    ['We need help.', '我们需要帮助。[wǒmen xūyào bāngzhù]'],
    ['I am lost.', '我迷路了。[wǒ mílù le]'],
    ['Where is safety?', '哪里安全? [nǎlǐ ānquán]'],
  ]},
  ja: {name:'Japanese', phrases: [
    ['Help!', '助けて! [tasu-ke-te]'],
    ['I need a doctor.', '医者が必要です。[isha ga hitsuyō desu]'],
    ['Call an ambulance!', '救急車を呼んで! [kyukyusha wo yonde]'],
    ['I am injured.', '怪我をしています。[kega wo shite imasu]'],
    ['Where is the hospital?', '病院はどこですか? [byōin wa doko desu ka]'],
    ['Water! / Food!', '水! / 食べ物! [mizu / tabemono]'],
    ['Danger! / Fire!', '危険! / 火事! [kiken / kaji]'],
    ['Do not shoot!', '撃たないで! [uta-nai-de]'],
    ['I surrender.', '降参します。[kōsan shimasu]'],
    ['Do you speak English?', '英語を話せますか? [eigo wo hanasemasu ka]'],
    ['I am American.', '私はアメリカ人です。[watashi wa amerikajin desu]'],
    ['Police / Military', '警察 / 軍隊 [keisatsu / guntai]'],
    ['We need help.', '助けが必要です。[tasuke ga hitsuyō desu]'],
    ['I am lost.', '迷子になりました。[maigo ni narimashita]'],
    ['Where is safety?', '安全な場所はどこ? [anzen na basho wa doko]'],
  ]},
  ko: {name:'Korean', phrases: [
    ['Help!', '도와주세요! [do-wa-ju-se-yo]'],
    ['I need a doctor.', '의사가 필요해요. [ui-sa-ga pil-yo-hae-yo]'],
    ['Call an ambulance!', '구급차를 불러주세요! [gu-geup-cha-reul bul-leo-ju-se-yo]'],
    ['I am injured.', '다쳤어요. [da-chyeo-sseo-yo]'],
    ['Where is the hospital?', '병원이 어디예요? [byeong-won-i eo-di-ye-yo]'],
    ['Water! / Food!', '물! / 음식! [mul / eum-sik]'],
    ['Danger! / Fire!', '위험! / 불이야! [wi-heom / bur-i-ya]'],
    ['Do not shoot!', '쏘지 마세요! [sso-ji ma-se-yo]'],
    ['I surrender.', '항복합니다. [hang-bok-ham-ni-da]'],
    ['Do you speak English?', '영어 하세요? [yeong-eo ha-se-yo]'],
    ['I am American.', '저는 미국인입니다. [jeo-neun mi-guk-in-im-ni-da]'],
    ['Police / Military', '경찰 / 군대 [gyeong-chal / gun-dae]'],
    ['We need help.', '도움이 필요해요. [do-um-i pil-yo-hae-yo]'],
    ['I am lost.', '길을 잃었어요. [gil-eul il-eo-sseo-yo]'],
    ['Where is safety?', '어디가 안전해요? [eo-di-ga an-jeon-hae-yo]'],
  ]},
  hi: {name:'Hindi', phrases: [
    ['Help!', 'मदद करो! [ma-dad ka-ro]'],
    ['I need a doctor.', 'मुझे डॉक्टर चाहिए। [mu-jhe dok-tar cha-hi-ye]'],
    ['Call an ambulance!', 'एम्बुलेंस बुलाओ! [em-bu-lens bu-lao]'],
    ['I am injured.', 'मैं घायल हूँ। [main gha-yal hoon]'],
    ['Where is the hospital?', 'अस्पताल कहाँ है? [as-pa-tal ka-han hai]'],
    ['Water! / Food!', 'पानी! / खाना! [pa-ni / kha-na]'],
    ['Danger! / Fire!', 'खतरा! / आग! [kha-tra / aag]'],
    ['Do not shoot!', 'गोली मत मारो! [go-li mat ma-ro]'],
    ['I surrender.', 'मैं आत्मसमर्पण करता हूँ। [main atm-sa-mar-pan kar-ta hoon]'],
    ['Do you speak English?', 'क्या आप अंग्रेजी बोलते हैं? [kya aap ang-re-ji bol-te hain]'],
    ['I am American.', 'मैं अमेरिकन हूँ। [main a-me-ri-can hoon]'],
    ['Police / Military', 'पुलिस / सेना [pu-lis / se-na]'],
    ['We need help.', 'हमें मदद चाहिए। [ha-men ma-dad cha-hi-ye]'],
    ['I am lost.', 'मैं खो गया हूँ। [main kho ga-ya hoon]'],
    ['Where is safety?', 'सुरक्षित जगह कहाँ है? [su-rak-shit ja-gah ka-han hai]'],
  ]},
};
function showPhrases() {
  const languageSelect = document.getElementById('phrase-lang');
  const el = document.getElementById('phrase-output');
  if (!languageSelect || !el) return;
  const lang = languageSelect.value;
  const data = _phrases[lang];
  if (!data) return;
  if (!data.phrases || !data.phrases.length) { el.innerHTML = '<div class="empty-state">No phrases available for this language.</div>'; return; }
  el.innerHTML = data.phrases.map(([eng,trans]) =>
    `<div class="prep-reference-phrase-card">
      <div class="prep-reference-phrase-source">${escapeHtml(eng)}</div>
      <div class="prep-reference-phrase-translation">${escapeHtml(trans)}</div>
    </div>`
  ).join('');
}
document.addEventListener('DOMContentLoaded', () => { if(document.getElementById('phrase-output')) showPhrases(); });

// ═══════════════════════════════════════════════════════════════
// FORAGING CALENDAR
// ═══════════════════════════════════════════════════════════════
const _forageData = {
  1: [{cat:'Bark/Inner Bark',items:['Eastern White Pine (needles for tea, vitamin C)','Birch sap rising (tap inner bark)','Hemlock needles (tea, NOT water hemlock plant)']},
      {cat:'Roots & Below-Ground',items:['Cattail rhizomes (flour substitute)','Jerusalem Artichoke','Wild Onion / Garlic (dried bulbs)']},
      {cat:'Nuts/Seeds (cached)',items:['Hickory nuts (stored)','Walnuts (stored)','Acorns (stored/leached)']}],
  2: [{cat:'Early Greens',items:['Chickweed (first to appear above snow)','Henbit','Hairy Bittercress','Dandelion (first leaves, rosette stage)']},
      {cat:'Roots',items:['Chicory root','Burdock root (year 1 plants)','Cattail rhizomes (starch peak)']},
      {cat:'Bark/Sap',items:['Maple sap (sugar maple, February–March before buds open)','Birch sap (late Feb–March)']}],
  3: [{cat:'Spring Greens',items:['Dandelion (greens + crown)','Chickweed','Violet leaves','Garlic Mustard (invasive, very common)','Nettles (young shoots — cook first)']},
      {cat:'Shoots',items:["Ramps / Wild Leeks (AKA 'wild garlic', Appalachians+)",'Ostrich Fern fiddleheads (ONLY this species)','Elderberry shoots (young only, cook first)']},
      {cat:'Roots',items:['Chicory','Burdock (year 1)','Wild Carrot / Queen Anne\'s Lace (NOT poison hemlock!)']}],
  4: [{cat:'Greens / Shoots',items:['Nettles (peak season — excellent spinach substitute)','Lamb\'s Quarters (emerges mid-spring)','Wood Sorrel','Clover (leaves + flowers)','Watercress (cold, clear running streams)']},
      {cat:'Flowers',items:["Dandelion flowers (fritters, wine)",'Redbud flowers (edible raw)','Wisteria flowers (edible, ornamental invasive)']},
      {cat:'Mushrooms',items:['Morel — PEAK season (April–May, deciduous forests, dying elms/ash)','Oyster mushroom (spring flush on dead hardwoods)']}],
  5: [{cat:'Greens',items:['Lamb\'s Quarters (peak)','Purslane (starts appearing)','Elderberry flowers','Mullein young leaves']},
      {cat:'Berries (early)',items:['Wild Strawberry (early May, some areas)','Serviceberry / Juneberry (dark purple, tree/shrub)']},
      {cat:'Mushrooms',items:['Morel (late season, move to higher elevations)','Chicken of the Woods (first flush on oaks)','Giant Puffball']}],
  6: [{cat:'Berries',items:['Wild Strawberry (peak)','Serviceberry / Juneberry','Black Mulberry (June–July)','Elderberry flowers (make into tea, fritters)']},
      {cat:'Greens',items:['Purslane (peak, high omega-3s)','Lamb\'s Quarters','Amaranth (leaves and seeds)','Plantain (broadleaf and narrowleaf)']},
      {cat:'Mushrooms',items:['Chicken of the Woods','Oyster mushroom','Chanterelle (beginning)']}],
  7: [{cat:'Berries',items:['Blueberry (mid–late July peak)','Wild Black Cherry','Thimbleberry','Black Currant (native species)','Elderberry (flowers → berries forming)']},
      {cat:'Greens/Seeds',items:['Purslane','Amaranth (seeds starting to form)','Lamb\'s Quarters seeds']},
      {cat:'Mushrooms',items:['Chanterelle (peak)','Chicken of the Woods','Black Trumpet']}],
  8: [{cat:'Berries',items:['Blueberry (late)','Blackberry / Dewberry (PEAK)','Wild Plum','Pawpaw (SE US, late August)','Elderberry (ripe, dark purple — must cook)']},
      {cat:'Seeds/Nuts',items:['Lamb\'s Quarters seeds (highest protein now)','Amaranth seeds (like tiny quinoa)','Sunflower seeds']},
      {cat:'Mushrooms',items:['Chanterelle','Hen of the Woods / Maitake (starts)','Lobster mushroom']}],
  9: [{cat:'Berries/Fruits',items:['Pawpaw (PEAK — custard-like, SE US only)','Wild Grape','Autumn Olive (invasive, sweet-tart)','Hawthorn berries (jelly/tea)','Crabapple']},
      {cat:'Nuts (PEAK)',items:['Hickory nuts (green husks split open)','Black Walnut (green husks, stain hands)','Butternuts','Beechnut']},
      {cat:'Mushrooms',items:['Hen of the Woods / Maitake (PEAK, base of oaks)','Chicken of the Woods','Giant Puffball (peak fall flush)','Chanterelle (late)']}],
  10: [{cat:'Nuts (PEAK)',items:['Acorns (all species — leach tannins for edibility)','Hickory nuts (hull and dry)','Black Walnut (hull promptly to prevent black stain)','Chestnuts (American is rare; Chinese chestnut common ornamental)']},
       {cat:'Fruits/Berries',items:['Persimmon (ONLY after first frost — before frost = inedible astringent)','Crabapple (better after frost)','Rose hips (high vitamin C)','Wild Grape (late)']},
       {cat:'Mushrooms',items:['Hen of the Woods / Maitake (late)','Oyster mushroom (cold weather flush on dead hardwoods)','Lion\'s Mane (white, tooth-like, on oaks)']}],
  11: [{cat:'Nuts (stored/late)',items:['Acorns (gather from ground)','Hickory nuts','Beechnuts']},
       {cat:'Roots',items:['Jerusalem Artichoke (sweeter after frost)','Chicory root','Wild Carrot (root sugars peak in cold)','Burdock root']},
       {cat:'Bark/Evergreens',items:['Pine needles (fresh, high vitamin C)','Cattail pollen (gone — harvest rhizomes)']}],
  12: [{cat:'Roots (peak starch)',items:['Cattail rhizomes','Chicory','Burdock','Wild Onion/Garlic bulbs']},
       {cat:'Evergreens',items:['Eastern White Pine needles (tea — vitamin C)','Spruce needles (tea)','Eastern Hemlock (tree, NOT plant) tips']},
       {cat:'Nuts (stored)',items:['Acorns','Hickory','Walnut (from storage)']}],
};
function showForageMonth(m) {
  const outputEl = document.getElementById('forage-output');
  if (!outputEl) return;
  document.querySelectorAll('[id^="forage-btn-"]').forEach(b => {
    const isActive = b.id === `forage-btn-${m}`;
    b.className = isActive ? 'btn btn-sm btn-primary' : 'btn btn-sm';
    b.setAttribute('aria-pressed', String(isActive));
  });
  const months = ['','January','February','March','April','May','June','July','August','September','October','November','December'];
  const data = _forageData[m] || [];
  outputEl.innerHTML = data.map(group =>
    `<div class="prep-reference-forage-card">
      <div class="prep-reference-forage-title">${group.cat}</div>
      ${group.items.map(i => `<div class="prep-reference-forage-item">• ${i}</div>`).join('')}
    </div>`
  ).join('') || '<div class="prep-reference-empty-note">No data for this month.</div>';
}
document.addEventListener('DOMContentLoaded', () => {
  const m = new Date().getMonth() + 1;
  showForageMonth(m);
});

// ═══════════════════════════════════════════════════════════════
// SKILLS TRACKER
// ═══════════════════════════════════════════════════════════════
let _skills = [];
const PROF_COLORS = {none:'var(--text-muted)', basic:'var(--orange)', intermediate:'var(--yellow)', expert:'var(--green)'};
const PROF_LABELS = {none:'None', basic:'Basic', intermediate:'Intermediate', expert:'Expert'};
async function loadSkills(filterCat) {
  try {
    _skills = await apiFetch('/api/skills');
    renderSkills(filterCat);
    renderSkillSummary();
    renderSkillFilterBtns();
  } catch(e) { console.warn('loadSkills failed:', e.message); }
}
function renderSkillFilterBtns() {
  const cats = [...new Set(_skills.map(s => s.category))].sort();
  const el = document.getElementById('skills-filter-btns');
  if (!el) return;
  el.innerHTML = '<button type="button" class="btn btn-sm" data-prep-action="filter-skills" data-skill-category="">All</button>' +
    cats.map(c => `<button type="button" class="btn btn-sm" data-prep-action="filter-skills" data-skill-category="${escapeAttr(c)}">${c}</button>`).join('');
}
function renderSkills(filterCat) {
  const el = document.getElementById('skills-list');
  if (!el) return;
  const filtered = filterCat ? _skills.filter(s => s.category === filterCat) : _skills;
  if (!filtered.length) { el.innerHTML = '<div class="prep-empty-state prep-empty-state-wide">No skills yet. Click "Load Default 60 Skills" to get started.</div>'; return; }
  el.innerHTML = filtered.map(s => `
    <div class="contact-card prep-skill-card">
      <div class="prep-card-head">
        <div class="prep-card-meta">
          <div class="cc-name">${escapeHtml(s.name)}</div>
          <div class="cc-field">${escapeHtml(s.category)}</div>
        </div>
        <div class="prep-skill-level-stack">
          <span class="prep-skill-level" style="--skill-level-color:${PROF_COLORS[s.proficiency]}">${PROF_LABELS[s.proficiency]}</span>
          <div class="prep-card-actions">
            <button type="button" class="btn btn-xs btn-ghost" data-prep-action="edit-skill" data-skill-id="${s.id}">Edit</button>
            <button type="button" class="btn btn-xs btn-ghost prep-inline-delete" data-prep-action="delete-skill" data-skill-id="${s.id}">Delete</button>
          </div>
        </div>
      </div>
      ${s.last_practiced ? `<div class="prep-skill-date">Last practiced: ${escapeHtml(s.last_practiced)}</div>` : ''}
      ${s.notes ? `<div class="contact-card-note">${escapeHtml(s.notes)}</div>` : ''}
    </div>`).join('');
}
function renderSkillSummary() {
  const el = document.getElementById('skills-summary');
  if (!el) return;
  const counts = {none:0,basic:0,intermediate:0,expert:0};
  _skills.forEach(s => counts[s.proficiency]++);
  el.innerHTML = `${_skills.length} skills: <span>${counts.expert} Expert</span> · <span>${counts.intermediate} Mid</span> · <span>${counts.basic} Basic</span> · <span>${counts.none} None</span>`;
}
function openSkillForm(s) {
  const nameInput = document.getElementById('skill-name');
  const categoryInput = document.getElementById('skill-cat');
  const proficiencyInput = document.getElementById('skill-prof');
  const practicedInput = document.getElementById('skill-practiced');
  const notesInput = document.getElementById('skill-notes');
  const editIdInput = document.getElementById('skill-edit-id');
  const form = document.getElementById('skills-form');
  if (!nameInput || !categoryInput || !proficiencyInput || !practicedInput || !notesInput || !editIdInput || !form) return;
  nameInput.value = s ? s.name : '';
  categoryInput.value = s ? s.category : 'General';
  proficiencyInput.value = s ? s.proficiency : 'none';
  practicedInput.value = s ? s.last_practiced : '';
  notesInput.value = s ? s.notes : '';
  editIdInput.value = s ? s.id : '';
  form.style.display = 'block';
  nameInput.focus();
}
function closeSkillForm() {
  const editIdInput = document.getElementById('skill-edit-id');
  const form = document.getElementById('skills-form');
  if (!editIdInput || !form) return;
  editIdInput.value = '';
  form.style.display = 'none';
}
function editSkill(id) { openSkillForm(_skills.find(s => s.id === id)); }
async function saveSkill() {
  const editIdInput = document.getElementById('skill-edit-id');
  const nameInput = document.getElementById('skill-name');
  const categoryInput = document.getElementById('skill-cat');
  const proficiencyInput = document.getElementById('skill-prof');
  const practicedInput = document.getElementById('skill-practiced');
  const notesInput = document.getElementById('skill-notes');
  if (!editIdInput || !nameInput || !categoryInput || !proficiencyInput || !practicedInput || !notesInput) return;
  const id = editIdInput.value;
  const body = {
    name: nameInput.value.trim(),
    category: categoryInput.value,
    proficiency: proficiencyInput.value,
    last_practiced: practicedInput.value,
    notes: notesInput.value.trim(),
  };
  if (!body.name) { toast('Skill name required', 'error'); return; }
  try {
    if (id) await apiPut(`/api/skills/${id}`, body);
    else await apiPost('/api/skills', body);
  } catch(e) {
    toast(e?.data?.error || 'Failed to save skill', 'error');
    return;
  }
  closeSkillForm();
  loadSkills();
  toast('Skill saved', 'success');
}
async function deleteSkill(id) {
  if (!confirm('Delete this skill?')) return;
  try {
    await apiDelete('/api/skills/' + id);
    toast('Skill deleted', 'info');
    loadSkills();
  } catch(e) { toast('Failed to delete skill', 'error'); }
}
async function seedDefaultSkills() {
  try {
    const d = await apiPost('/api/skills/seed-defaults');
    if (d.seeded === 0) { toast('Default skills already loaded', 'info'); }
    else { toast('Loaded ' + d.seeded + ' default skills', 'success'); loadSkills(); }
  } catch(e) { toast('Failed to seed skills', 'error'); }
}

// ═══════════════════════════════════════════════════════════════
// AMMO INVENTORY
// ═══════════════════════════════════════════════════════════════
let _ammo = [];
async function loadAmmo() {
  try {
    _ammo = await apiFetch('/api/ammo');
    renderAmmo();
    loadAmmoSummary();
  } catch(e) { console.warn('loadAmmo failed:', e.message); }
}
async function loadAmmoSummary() {
  const d = await apiFetch('/api/ammo/summary');
  const bar = document.getElementById('ammo-summary-bar');
  if (bar) bar.innerHTML = `Total: <strong>${d.total.toLocaleString()} rounds</strong> across ${d.by_caliber.length} calibers`;
  const cal = document.getElementById('ammo-by-caliber');
  if (cal) cal.innerHTML = d.by_caliber.map(b =>
    `<div class="prep-ammo-summary-card">
      <div class="prep-ammo-summary-total">${b.total}</div>
      <div class="prep-ammo-summary-label">${escapeHtml(b.caliber)}</div>
    </div>`).join('');
}
function renderAmmo() {
  const el = document.getElementById('ammo-list');
  if (!el) return;
  if (!_ammo.length) { el.innerHTML = '<div class="prep-empty-state prep-empty-state-wide">No ammo logged yet.</div>'; return; }
  el.innerHTML = `<table class="freq-table prep-data-table prep-ammo-table">
    <thead><tr>
      <th>Caliber</th>
      <th>Brand</th>
      <th>Weight/Type</th>
      <th class="text-align-right">Qty</th>
      <th>Location</th>
      <th>Notes</th>
      <th class="prep-actions-col">Actions</th>
    </tr></thead>
    <tbody>${_ammo.map(a => `
      <tr>
        <td><strong>${escapeHtml(a.caliber)}</strong></td>
        <td>${escapeHtml(a.brand || '-')}</td>
        <td>${escapeHtml([a.bullet_weight, a.bullet_type].filter(Boolean).join(' ') || '-')}</td>
        <td class="text-align-right"><strong>${a.quantity.toLocaleString()}</strong></td>
        <td>${escapeHtml(a.location || '-')}</td>
        <td class="prep-muted-cell">${escapeHtml(a.notes || '-')}</td>
        <td class="prep-row-actions">
          <button type="button" class="btn btn-xs btn-ghost" data-prep-action="edit-ammo" data-ammo-id="${a.id}">Edit</button>
          <button type="button" class="btn btn-xs btn-ghost prep-inline-delete" data-prep-action="delete-ammo" data-ammo-id="${a.id}">Delete</button>
        </td>
      </tr>`).join('')}
    </tbody></table>`;
}
function openAmmoForm(a) {
  const caliberInput = document.getElementById('ammo-caliber');
  const brandInput = document.getElementById('ammo-brand');
  const weightInput = document.getElementById('ammo-weight');
  const typeInput = document.getElementById('ammo-type');
  const qtyInput = document.getElementById('ammo-qty');
  const locationInput = document.getElementById('ammo-location');
  const notesInput = document.getElementById('ammo-notes');
  const editIdInput = document.getElementById('ammo-edit-id');
  const form = document.getElementById('ammo-form');
  if (!caliberInput || !brandInput || !weightInput || !typeInput || !qtyInput || !locationInput || !notesInput || !editIdInput || !form) return;
  caliberInput.value = a ? a.caliber : '';
  brandInput.value = a ? a.brand : '';
  weightInput.value = a ? a.bullet_weight : '';
  typeInput.value = a ? a.bullet_type : 'FMJ';
  qtyInput.value = a ? a.quantity : 0;
  locationInput.value = a ? a.location : '';
  notesInput.value = a ? a.notes : '';
  editIdInput.value = a ? a.id : '';
  form.style.display = 'block';
}
function closeAmmoForm() {
  const editIdInput = document.getElementById('ammo-edit-id');
  const form = document.getElementById('ammo-form');
  if (!editIdInput || !form) return;
  editIdInput.value = '';
  form.style.display = 'none';
}
function editAmmo(id) { openAmmoForm(_ammo.find(a => a.id === id)); }
async function saveAmmo() {
  const editIdInput = document.getElementById('ammo-edit-id');
  const caliberInput = document.getElementById('ammo-caliber');
  const brandInput = document.getElementById('ammo-brand');
  const weightInput = document.getElementById('ammo-weight');
  const typeInput = document.getElementById('ammo-type');
  const qtyInput = document.getElementById('ammo-qty');
  const locationInput = document.getElementById('ammo-location');
  const notesInput = document.getElementById('ammo-notes');
  if (!editIdInput || !caliberInput || !brandInput || !weightInput || !typeInput || !qtyInput || !locationInput || !notesInput) return;
  const id = editIdInput.value;
  const body = {
    caliber: caliberInput.value.trim(),
    brand: brandInput.value.trim(),
    bullet_weight: weightInput.value.trim(),
    bullet_type: typeInput.value,
    quantity: parseInt(qtyInput.value) || 0,
    location: locationInput.value.trim(),
    notes: notesInput.value.trim(),
  };
  if (!body.caliber) { toast('Caliber required', 'error'); return; }
  try {
    if (id) await apiPut(`/api/ammo/${id}`, body);
    else await apiPost('/api/ammo', body);
  } catch(e) {
    toast(e?.data?.error || 'Failed to save ammo entry', 'error');
    return;
  }
  closeAmmoForm();
  loadAmmo();
  toast('Saved', 'success');
}
async function deleteAmmo(id) {
  if (!confirm('Delete this entry?')) return;
  try {
    await apiDelete('/api/ammo/' + id);
    loadAmmo();
  } catch(e) { toast('Failed to delete ammo entry', 'error'); }
}

// ═══════════════════════════════════════════════════════════════
// COMMUNITY RESOURCE REGISTRY
// ═══════════════════════════════════════════════════════════════
let _community = [];
const TRUST_COLORS = {unknown:'var(--text-muted)', acquaintance:'var(--text-dim)', trusted:'var(--orange)', 'inner-circle':'var(--green)'};
async function loadCommunity() {
  try {
    const data = await safeFetch('/api/community', {}, []);
    _community = Array.isArray(data) ? data : [];
    renderCommunity();
  } catch(e) { console.warn('loadCommunity failed:', e.message); }
}
function renderCommunity() {
  const el = document.getElementById('community-list');
  if (!el) return;
  if (!_community.length) {
    el.innerHTML = '<div class="prep-empty-state prep-empty-state-wide">No community members logged yet. Add trusted neighbors and their skills.</div>';
    return;
  }
  el.innerHTML = _community.map(p => {
    const skills = safeJsonParse(p.skills, []);
    const equip = safeJsonParse(p.equipment, []);
    const trustKey = (p.trust_level || 'unknown').toLowerCase();
    const trustLabel = trustKey.split('-').map(part => part.charAt(0).toUpperCase() + part.slice(1)).join(' ');
    const distance = Number(p.distance_mi);
    const distanceLabel = Number.isFinite(distance) ? `${distance} mi away` : 'Distance unknown';
    return `<div class="contact-card prep-community-card">
      <div class="prep-card-head">
        <div class="prep-card-meta">
          <div class="cc-name">${escapeHtml(p.name || 'Unknown')}</div>
          <div class="cc-field"><strong>Distance:</strong> ${escapeHtml(distanceLabel)}</div>
          ${p.contact ? `<div class="cc-field"><strong>Contact:</strong> ${escapeHtml(p.contact)}</div>` : ''}
        </div>
        <span class="prep-trust-pill prep-trust-${escapeAttr(trustKey)}">${escapeHtml(trustLabel)}</span>
      </div>
      ${skills.length ? `<div class="prep-detail-group"><div class="prep-detail-label">Skills</div><div class="prep-chip-row">${skills.map(skill => `<span class="prep-summary-chip">${escapeHtml(skill)}</span>`).join('')}</div></div>` : ''}
      ${equip.length ? `<div class="prep-detail-group"><div class="prep-detail-label">Equipment</div><div class="prep-chip-row">${equip.map(item => `<span class="prep-summary-chip">${escapeHtml(item)}</span>`).join('')}</div></div>` : ''}
      ${p.notes ? `<div class="contact-card-note">${escapeHtml(p.notes)}</div>` : ''}
      <div class="prep-card-actions">
        <button type="button" class="btn btn-sm" data-prep-action="edit-community" data-community-id="${p.id}">Edit</button>
        <button type="button" class="btn btn-sm prep-inline-delete" data-prep-action="delete-community" data-community-id="${p.id}">Delete</button>
      </div>
    </div>`;
  }).join('');
  // Skills summary
  const allSkills = _community.flatMap(p => safeJsonParse(p.skills, []));
  const skillCounts = {};
  allSkills.forEach(s => skillCounts[s] = (skillCounts[s]||0)+1);
  const sumEl = document.getElementById('community-skills-summary');
  if (sumEl) {
    const topSkills = Object.entries(skillCounts).sort((a,b) => b[1]-a[1]).slice(0, 10);
    sumEl.innerHTML = topSkills.length ? '<span class="prep-command-note">Top skills in network</span>' +
      topSkills.map(([s,n]) => `<span class="prep-summary-chip">${escapeHtml(s)} (${n})</span>`).join('') : '';
  }
}
function openCommunityForm(p) {
  const nameInput = document.getElementById('comm-name');
  const distanceInput = document.getElementById('comm-dist');
  const trustInput = document.getElementById('comm-trust');
  const contactInput = document.getElementById('comm-contact');
  const skillsInput = document.getElementById('comm-skills');
  const equipmentInput = document.getElementById('comm-equip');
  const notesInput = document.getElementById('comm-notes');
  const editIdInput = document.getElementById('comm-edit-id');
  const form = document.getElementById('community-form');
  if (!nameInput || !distanceInput || !trustInput || !contactInput || !skillsInput || !equipmentInput || !notesInput || !editIdInput || !form) return;
  nameInput.value = p ? p.name : '';
  distanceInput.value = p ? p.distance_mi : '0.1';
  trustInput.value = p ? p.trust_level : 'unknown';
  contactInput.value = p ? p.contact : '';
  skillsInput.value = p ? safeJsonParse(p.skills, []).join(', ') : '';
  equipmentInput.value = p ? safeJsonParse(p.equipment, []).join(', ') : '';
  notesInput.value = p ? p.notes : '';
  editIdInput.value = p ? p.id : '';
  form.style.display = 'block';
}
function closeCommunityForm() {
  const editIdInput = document.getElementById('comm-edit-id');
  const form = document.getElementById('community-form');
  if (!editIdInput || !form) return;
  editIdInput.value = '';
  form.style.display = 'none';
}
function editCommunity(id) { openCommunityForm(_community.find(p => p.id === id)); }
async function saveCommunity() {
  const editIdInput = document.getElementById('comm-edit-id');
  const nameInput = document.getElementById('comm-name');
  const distanceInput = document.getElementById('comm-dist');
  const trustInput = document.getElementById('comm-trust');
  const contactInput = document.getElementById('comm-contact');
  const skillsInput = document.getElementById('comm-skills');
  const equipmentInput = document.getElementById('comm-equip');
  const notesInput = document.getElementById('comm-notes');
  if (!editIdInput || !nameInput || !distanceInput || !trustInput || !contactInput || !skillsInput || !equipmentInput || !notesInput) return;
  const id = editIdInput.value;
  const skillsRaw = skillsInput.value;
  const equipRaw = equipmentInput.value;
  const body = {
    name: nameInput.value.trim(),
    distance_mi: parseFloat(distanceInput.value) || 0,
    trust_level: trustInput.value,
    contact: contactInput.value.trim(),
    skills: skillsRaw ? skillsRaw.split(',').map(s => s.trim()).filter(Boolean) : [],
    equipment: equipRaw ? equipRaw.split(',').map(s => s.trim()).filter(Boolean) : [],
    notes: notesInput.value.trim(),
  };
  if (!body.name) { toast('Name required', 'error'); return; }
  try {
    if (id) await apiPut(`/api/community/${id}`, body);
    else await apiPost('/api/community', body);
  } catch(e) {
    toast(e?.data?.error || 'Failed to save', 'error');
    return;
  }
  closeCommunityForm();
  loadCommunity();
  toast('Saved', 'success');
}
async function deleteCommunity(id) {
  if (!confirm('Remove this person?')) return;
  try {
    await apiDelete('/api/community/' + id);
    loadCommunity();
  } catch(e) { toast('Failed to remove community member', 'error'); }
}

// ═══════════════════════════════════════════════════════════════
// RADIATION DOSE TRACKER
// ═══════════════════════════════════════════════════════════════
async function loadRadiation() {
  try {
    const d = await safeFetch('/api/radiation', {}, null);
    if (!d) throw new Error('Failed to load radiation data');
    const readings = Array.isArray(d.readings) ? d.readings : [];
    renderRadiationDashboard({...d, readings});
    renderRadiationLog(readings);
  } catch(e) {
    const el = document.getElementById('radiation-dashboard');
    if (el) el.innerHTML = '<div class="prep-empty-state prep-empty-state-wide prep-error-state">Failed to load radiation data.</div>';
  }
}
function renderRadiationDashboard(d) {
  const el = document.getElementById('radiation-dashboard');
  if (!el) return;
  const latest = d.readings && d.readings.length > 0 ? d.readings[0] : null;
  const latestRate = latest ? latest.dose_rate_rem : 0;
  const latestClass = latestRate < 0.1 ? 'prep-summary-card-ok' : latestRate < 2 ? 'prep-summary-card-warn' : 'prep-summary-card-danger';
  const cumulativeClass = d.total_rem < 25 ? 'prep-summary-card-ok' : d.total_rem < 100 ? 'prep-summary-card-warn' : 'prep-summary-card-danger';
  el.innerHTML = `
    <div class="prep-summary-card ${latestClass}">
      <div class="prep-summary-meta">Latest Reading</div>
      <div class="prep-summary-value">${latestRate.toFixed(3)}</div>
      <div class="prep-summary-label">R/hr</div>
    </div>
    <div class="prep-summary-card ${cumulativeClass}">
      <div class="prep-summary-meta">Cumulative Dose</div>
      <div class="prep-summary-value">${d.total_rem.toFixed(2)}</div>
      <div class="prep-summary-label">rem total</div>
    </div>
    <div class="prep-summary-card">
      <div class="prep-summary-meta">Total Readings</div>
      <div class="prep-summary-value">${d.readings.length}</div>
      <div class="prep-summary-label">logged</div>
    </div>`;
}
function renderRadiationLog(readings) {
  const el = document.getElementById('radiation-log-table');
  if (!el) return;
  if (!readings.length) { el.innerHTML = '<div class="prep-empty-state prep-empty-state-wide">No readings logged.</div>'; return; }
  el.innerHTML = `<div class="prep-table-wrap"><table class="freq-table prep-data-table">
    <thead><tr>
      <th>Time</th>
      <th>Rate (R/hr)</th>
      <th>Cumulative (rem)</th>
      <th>Location</th>
      <th>Notes</th>
    </tr></thead>
    <tbody>${readings.map(r => {
      const rateClass = r.dose_rate_rem < 0.1 ? 'prep-dose-rate-safe' : r.dose_rate_rem < 2 ? 'prep-dose-rate-warn' : 'prep-dose-rate-danger';
      return `<tr>
        <td>${escapeHtml((r.created_at || '').replace('T',' ').slice(0,16))}</td>
        <td class="${rateClass}">${r.dose_rate_rem.toFixed(3)}</td>
        <td>${r.cumulative_rem.toFixed(3)}</td>
        <td>${escapeHtml(r.location || '-')}</td>
        <td>${escapeHtml(r.notes || '-')}</td>
      </tr>`;
    }).join('')}</tbody></table></div>`;
}
async function logRadiation() {
  const rateInput = document.getElementById('rad-log-rate');
  const locationInput = document.getElementById('rad-location');
  const notesInput = document.getElementById('rad-notes');
  if (!rateInput || !locationInput || !notesInput) return;
  const rate = parseFloat(rateInput.value);
  if (!rate && rate !== 0) { toast('Enter a dose rate', 'error'); return; }
  try {
    await apiPost('/api/radiation', {dose_rate_rem: rate, location: locationInput.value, notes: notesInput.value});
    rateInput.value = '';
    loadRadiation();
    toast('Reading logged', 'success');
  } catch(e) { toast('Failed to log reading', 'error'); }
}
async function clearRadiation() {
  if (!confirm('Clear all radiation dose log entries? This cannot be undone.')) return;
  try {
    await apiPost('/api/radiation/clear');
    loadRadiation();
    toast('Radiation log cleared', 'warning');
  } catch(e) { toast('Failed to clear radiation log', 'error'); }
}

// ═══════════════════════════════════════════════════════════════
// ICS FORMS
// ═══════════════════════════════════════════════════════════════
let _ics309Entries = readJsonStorage(localStorage, 'nomad_ics309', []);
if (!Array.isArray(_ics309Entries)) _ics309Entries = [];
let _ics214Entries = readJsonStorage(localStorage, 'nomad_ics214', []);
if (!Array.isArray(_ics214Entries)) _ics214Entries = [];
function _persistICS() {
  try {
    localStorage.setItem('nomad_ics309', JSON.stringify(_ics309Entries));
    localStorage.setItem('nomad_ics214', JSON.stringify(_ics214Entries));
  } catch(e) {}
}
function showICSTab(tab) {
  ['213','309','214'].forEach(t => {
    const isActive = t === tab;
    const panel = document.getElementById(`ics-${t}-panel`);
    const tabBtn = document.getElementById(`ics-tab-${t}`);
    if (!panel || !tabBtn) return;
    panel.style.display = isActive ? '' : 'none';
    tabBtn.className = isActive ? 'btn btn-sm btn-primary' : 'btn btn-sm';
    tabBtn.setAttribute('aria-pressed', String(isActive));
  });
}
function printICS213() {
  const toInput = document.getElementById('ics213-to');
  const fromInput = document.getElementById('ics213-from');
  const subjectInput = document.getElementById('ics213-subject');
  const dtInput = document.getElementById('ics213-datetime');
  const incidentInput = document.getElementById('ics213-incident');
  const priorityInput = document.getElementById('ics213-priority');
  const messageInput = document.getElementById('ics213-message');
  const replyByInput = document.getElementById('ics213-replyby');
  const replyInput = document.getElementById('ics213-reply');
  if (!toInput || !fromInput || !subjectInput || !dtInput || !incidentInput || !priorityInput || !messageInput || !replyByInput || !replyInput) return;
  const to = toInput.value;
  const from = fromInput.value;
  const subject = subjectInput.value;
  const dt = dtInput.value || new Date().toLocaleString();
  const incident = incidentInput.value;
  const priority = priorityInput.value;
  const message = messageInput.value;
  const replyby = replyByInput.value;
  const reply = replyInput.value;
  const w = window.openPendingPopup?.('ICS-213', 'Preparing the printable ICS-213 form…');
  if (!w) { toast('Pop-up blocked -- please allow pop-ups', 'warning'); return; }
  window.replacePopupHtml?.(w, `<!DOCTYPE html><html><head><title>ICS-213</title>
  <style>body{font-family:Arial,sans-serif;font-size:12px;margin:20px;}table{width:100%;border-collapse:collapse;}
  td,th{border:1px solid #000;padding:4px 6px;}h2{text-align:center;}
  .header-row{background:#ccc;font-weight:bold;text-align:center;font-size:14px;}
  @media print{body{margin:0.5in;}}</style></head><body>
  <h2>GENERAL MESSAGE (ICS-213)</h2>
  <table><tr><td class="header-row" colspan="4">ICS 213</td></tr>
  <tr><td><strong>To:</strong> ${escapeHtml(to)}</td><td><strong>From:</strong> ${escapeHtml(from)}</td><td><strong>Date/Time:</strong> ${escapeHtml(dt)}</td><td><strong>Priority:</strong> ${escapeHtml(priority)}</td></tr>
  <tr><td colspan="2"><strong>Incident Name:</strong> ${escapeHtml(incident)}</td><td colspan="2"><strong>Subject:</strong> ${escapeHtml(subject)}</td></tr>
  <tr><td colspan="4"><strong>Message:</strong><br><br>${escapeHtml(message).replace(/\n/g,'<br>')}<br><br><br></td></tr>
  <tr><td colspan="2"><strong>Reply By:</strong> ${escapeHtml(replyby)}</td><td colspan="2"><strong>Reply:</strong> ${escapeHtml(reply)}</td></tr>
  <tr><td colspan="2"><strong>Approved by (Signature):</strong><br><br><br></td><td colspan="2"><strong>Position/Title:</strong><br></td></tr>
  </table><br><p class="text-size-10 text-center">ICS-213 — General Message Form — NIMS Compatible</p>
  <script>window.print();<\/script></body></html>`);
}
function clearICS213() {
  const fields = ['ics213-to','ics213-from','ics213-subject','ics213-datetime','ics213-incident','ics213-message','ics213-replyby','ics213-reply']
    .map(id => document.getElementById(id));
  if (fields.some(field => !field)) return;
  fields.forEach(field => { field.value = ''; });
}
function addICS309Entry() {
  const timeInput = document.getElementById('ics309-time');
  const fromInput = document.getElementById('ics309-from');
  const toInput = document.getElementById('ics309-to');
  const msgInput = document.getElementById('ics309-msg');
  if (!timeInput || !fromInput || !toInput || !msgInput) return;
  const entry = {
    time: timeInput.value,
    from: fromInput.value,
    to: toInput.value,
    msg: msgInput.value,
  };
  if (!entry.msg) return;
  _ics309Entries.push(entry);
  _persistICS();
  [timeInput, fromInput, toInput, msgInput].forEach(field => { field.value = ''; });
  renderICS309Table();
}
function removeICS309Entry(index) {
  _ics309Entries.splice(index, 1);
  _persistICS();
  renderICS309Table();
}
function renderICS309Table() {
  const el = document.getElementById('ics309-entries');
  if (!el) return;
  if (!_ics309Entries.length) {
    el.innerHTML = '<div class="prep-empty-state prep-empty-state-wide">No entries yet.</div>';
    return;
  }
  el.innerHTML = `<table class="freq-table prep-data-table">
    <thead><tr><th>Time</th><th>From</th><th>To</th><th>Message</th><th class="prep-actions-col"></th></tr></thead>
    <tbody>${_ics309Entries.map((e,i) => `<tr>
      <td>${escapeHtml(e.time || '')}</td><td>${escapeHtml(e.from || '')}</td><td>${escapeHtml(e.to || '')}</td><td>${escapeHtml(e.msg || '')}</td>
      <td class="prep-row-actions"><button type="button" class="ics-log-delete-btn" data-prep-action="remove-ics309-entry" data-ics309-index="${i}" aria-label="Remove ICS-309 entry ${i + 1}">Delete</button></td>
    </tr>`).join('')}</tbody></table>`;
}
function printICS309() {
  const incidentInput = document.getElementById('ics309-incident');
  const operatorInput = document.getElementById('ics309-operator');
  const stationInput = document.getElementById('ics309-station');
  if (!incidentInput || !operatorInput || !stationInput) return;
  const incident = incidentInput.value;
  const operator = operatorInput.value;
  const station = stationInput.value;
  const rows = _ics309Entries.map(e =>
    `<tr><td>${escapeHtml(e.time)}</td><td>${escapeHtml(e.from)}</td><td>${escapeHtml(e.to)}</td><td>${escapeHtml(e.msg)}</td></tr>`).join('');
  const w = window.openPendingPopup?.('ICS-309', 'Preparing the printable ICS-309 log…');
  if (!w) { toast('Pop-up blocked -- please allow pop-ups', 'warning'); return; }
  window.replacePopupHtml?.(w, `<!DOCTYPE html><html><head><title>ICS-309</title>
  <style>body{font-family:Arial,sans-serif;font-size:11px;margin:20px;}table{width:100%;border-collapse:collapse;}
  td,th{border:1px solid #000;padding:4px 6px;}h2{text-align:center;}
  @media print{body{margin:0.5in;}}</style></head><body>
  <h2>COMMUNICATIONS LOG (ICS-309)</h2>
  <table><tr><td><strong>Incident Name:</strong> ${escapeHtml(incident)}</td><td><strong>Operator:</strong> ${escapeHtml(operator)}</td><td><strong>Station/Freq:</strong> ${escapeHtml(station)}</td><td><strong>Date:</strong> ${new Date().toLocaleDateString()}</td></tr></table>
  <br><table><thead><tr><th>Time</th><th>From</th><th>To</th><th>Message/Traffic</th></tr></thead><tbody>${rows}</tbody></table>
  <br><p><strong>Operator Signature:</strong> ______________________ <strong>Date/Time:</strong> ______________</p>
  <p class="text-size-10 text-center">ICS-309 — Communications Log — NIMS Compatible</p>
  <script>window.print();<\/script></body></html>`);
}
function clearICS309() { _ics309Entries = []; _persistICS(); renderICS309Table(); }
function addICS214Entry() {
  const timeInput = document.getElementById('ics214-time');
  const activityInput = document.getElementById('ics214-activity');
  if (!timeInput || !activityInput) return;
  const entry = {time: timeInput.value, activity: activityInput.value};
  if (!entry.activity) return;
  _ics214Entries.push(entry);
  _persistICS();
  [timeInput, activityInput].forEach(field => { field.value = ''; });
  renderICS214Table();
}
function removeICS214Entry(index) {
  _ics214Entries.splice(index, 1);
  _persistICS();
  renderICS214Table();
}
function renderICS214Table() {
  const el = document.getElementById('ics214-entries');
  if (!el) return;
  if (!_ics214Entries.length) {
    el.innerHTML = '<div class="prep-empty-state prep-empty-state-wide">No activities yet.</div>';
    return;
  }
  el.innerHTML = `<table class="freq-table prep-data-table">
    <thead><tr><th>Time</th><th>Notable Activity</th><th class="prep-actions-col"></th></tr></thead>
    <tbody>${_ics214Entries.map((e,i) => `<tr>
      <td>${escapeHtml(e.time || '')}</td><td>${escapeHtml(e.activity || '')}</td>
      <td class="prep-row-actions"><button type="button" class="ics-log-delete-btn" data-prep-action="remove-ics214-entry" data-ics214-index="${i}" aria-label="Remove ICS-214 entry ${i + 1}">Delete</button></td>
    </tr>`).join('')}</tbody></table>`;
}
function printICS214() {
  const incidentInput = document.getElementById('ics214-incident');
  const unitInput = document.getElementById('ics214-unit');
  const leaderInput = document.getElementById('ics214-leader');
  const periodInput = document.getElementById('ics214-period');
  if (!incidentInput || !unitInput || !leaderInput || !periodInput) return;
  const incident = incidentInput.value;
  const unit = unitInput.value;
  const leader = leaderInput.value;
  const period = periodInput.value;
  const rows = _ics214Entries.map(e => `<tr><td>${escapeHtml(e.time)}</td><td>${escapeHtml(e.activity)}</td></tr>`).join('');
  const w = window.openPendingPopup?.('ICS-214', 'Preparing the printable ICS-214 activity log…');
  if (!w) { toast('Pop-up blocked -- please allow pop-ups', 'warning'); return; }
  window.replacePopupHtml?.(w, `<!DOCTYPE html><html><head><title>ICS-214</title>
  <style>body{font-family:Arial,sans-serif;font-size:11px;margin:20px;}table{width:100%;border-collapse:collapse;}
  td,th{border:1px solid #000;padding:4px 6px;}h2{text-align:center;}.time-col{width:100px;}
  @media print{body{margin:0.5in;}}</style></head><body>
  <h2>ACTIVITY LOG (ICS-214)</h2>
  <table><tr><td><strong>Incident Name:</strong> ${escapeHtml(incident)}</td><td><strong>Unit/Team:</strong> ${escapeHtml(unit)}</td><td><strong>Leader:</strong> ${escapeHtml(leader)}</td><td><strong>Op Period:</strong> ${escapeHtml(period)}</td></tr></table>
  <br><table><thead><tr><th class="time-col">Time</th><th>Notable Activity</th></tr></thead><tbody>${rows}</tbody></table>
  <br><p><strong>Prepared by:</strong> ______________________ <strong>Date/Time:</strong> ______________</p>
  <p class="text-size-10 text-center">ICS-214 — Activity Log — NIMS Compatible</p>
  <script>window.print();<\/script></body></html>`);
}
function clearICS214() { _ics214Entries = []; _persistICS(); renderICS214Table(); }

// ═══════════════════════════════════════════════════════════════
// LAN QR CODE
// ═══════════════════════════════════════════════════════════════
function showLanQR() {
  const urlEl = document.getElementById('lan-url-setting');
  const url = urlEl ? urlEl.textContent.trim() : '';
  if (!url || url === '-' || !url.startsWith('http')) {
    toast('LAN URL not available. Ensure the app is running on a network.', 'error');
    return;
  }
  // Use QR code via qrserver.com (offline fallback: show URL prominently)
  const modal = document.createElement('div');
  modal.id = 'lan-qr-modal';
  modal.className = 'generated-modal-overlay lan-qr-modal-overlay';
  modal.onclick = e => { if (e.target === modal) modal.remove(); };
  modal.innerHTML = `
    <div class="generated-modal-card lan-qr-modal-card">
      <h3 class="lan-qr-title">Scan to Connect on LAN</h3>
      <p class="lan-qr-copy">Any device on your local network can open NOMAD at:</p>
      <div class="lan-qr-url">${escapeHtml(url)}</div>
      <canvas id="qr-canvas" width="200" height="200" class="lan-qr-canvas"></canvas>
      <button type="button" class="btn btn-sm" data-shell-action="close-lan-qr">Close</button>
    </div>`;
  document.body.appendChild(modal);
  if (typeof NomadModal !== 'undefined') NomadModal.open(modal, {
    onClose: () => { if (modal.parentNode) modal.remove(); },
  });
  // Simple QR code generation using a data URL approach (pure JS QR)
  generateQRCanvas('qr-canvas', url);
}
function generateQRCanvas(canvasId, text) {
  // Use a minimal QR code — encode as URL in img via public API when online, else show text
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  // Draw a placeholder with the URL text if pure-JS QR isn't bundled
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, 200, 200);
  // Try to load from a local QR generator if available; otherwise display text prominently
  const img = new Image();
  img.onload = () => ctx.drawImage(img, 0, 0, 200, 200);
  img.onerror = () => {
    ctx.fillStyle = '#000000';
    ctx.font = 'bold 11px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('Open this URL on your device:', 100, 80);
    ctx.font = '10px monospace';
    const words = text.split('/');
    words.forEach((w,i) => ctx.fillText(w, 100, 100 + i*14));
  };
  img.src = `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(text)}`;
}

// ═══════════════════════════════════════════════════════════════
// CHIRP CSV EXPORT
// ═══════════════════════════════════════════════════════════════
/* ─── Triage Board UI ─── */
async function loadTriageBoard() {
  const data = await safeFetch('/api/medical/triage-board', {}, null);
  if (!data) return;
  const el = document.getElementById('triage-board');
  if (!el) return;
  const catColors = {immediate:'#c62828',delayed:'#f9a825',minimal:'#2e7d32',expectant:'#424242',unassigned:'var(--text-muted)'};
  const catLabels = {immediate:'IMMEDIATE',delayed:'DELAYED',minimal:'MINIMAL',expectant:'EXPECTANT'};
  const catOrder = ['immediate','delayed','minimal','expectant'];
  if (data.total === 0) {
    el.innerHTML = prepEmptyBlock('No patients registered yet. Add medical profiles below to use triage.');
    return;
  }
  el.innerHTML = catOrder.map(cat => {
    const patients = data.categories[cat] || [];
    const color = catColors[cat] || 'var(--text-muted)';
    return `<div class="prep-triage-column">
      <div class="prep-triage-column-title" style="--prep-triage-tone:${color};">${catLabels[cat]} (${patients.length})</div>
      ${patients.map(p => `<button type="button" class="prep-triage-patient" style="--prep-triage-tone:${color};" data-prep-action="change-triage-category" data-patient-id="${p.id}" data-triage-category="${cat}">
        <span class="prep-triage-name">${escapeHtml(p.name)}</span>
        <span class="prep-record-meta">${p.age ? 'Age '+p.age : 'Age unknown'}${p.blood_type ? ' · ' + escapeHtml(p.blood_type) : ''}</span>
      </button>`).join('')}
      ${!patients.length ? '<div class="prep-garden-calendar-empty">No patients in this category</div>' : ''}
    </div>`;
  }).join('');
  const unassigned = data.categories.unassigned || [];
  if (unassigned.length) {
    el.innerHTML += `<div class="prep-triage-unassigned">
      <div class="prep-triage-column-title" style="--prep-triage-tone:var(--text-dim);">Unassigned (${unassigned.length})</div>
      <div class="prep-command-actions">
        ${unassigned.map(p => `<button type="button" class="btn btn-sm prep-utility-tab prep-triage-chip" data-prep-action="change-triage-category" data-patient-id="${p.id}" data-triage-category="unassigned">${escapeHtml(p.name)}</button>`).join('')}
      </div>
    </div>`;
  }
}

async function changeTriageCategory(patientId, currentCat) {
  const cats = ['immediate','delayed','minimal','expectant'];
  const labels = {immediate:'IMMEDIATE (Red)',delayed:'DELAYED (Yellow)',minimal:'MINIMAL (Green)',expectant:'EXPECTANT (Black)'};
  const options = cats.map(c => `<button type="button" class="btn btn-sm ${c===currentCat?'prep-utility-tab prep-utility-tab-active':'prep-utility-tab'}" data-prep-action="set-triage-category" data-patient-id="${patientId}" data-triage-category="${c}">${labels[c]}</button>`).join(' ');
  const el = document.getElementById('triage-board');
  const existing = document.getElementById('triage-picker');
  if (existing) existing.remove();
  const picker = document.createElement('div');
  picker.id = 'triage-picker';
  picker.className = 'prep-triage-picker';
  picker.innerHTML = `<span class="prep-triage-prompt">Assign triage:</span> ${options} <button type="button" class="btn btn-sm" data-shell-action="close-triage-picker">Cancel</button>`;
  el.appendChild(picker);
}

async function setTriageCategory(patientId, category) {
  try {
    await apiPut(`/api/medical/triage/${patientId}`, {triage_category: category});
    document.getElementById('triage-picker')?.remove();
    loadTriageBoard();
    toast('Triage updated', 'success');
  } catch (e) {
    toast(e?.data?.error || e?.message || 'Failed to update triage', 'error');
  }
}

/* ─── Medical Quick Reference ─── */
async function loadMedRef(category) {
  const el = document.getElementById('med-ref-content');
  if (!el) return;
  document.querySelectorAll('button[id^="med-ref-"]').forEach(btn => {
    btn.className = btn.id === `med-ref-${category}`
      ? 'btn btn-sm prep-utility-tab prep-utility-tab-active'
      : 'btn btn-sm prep-utility-tab';
  });
  el.style.display = 'block';
  el.innerHTML = '<div class="prep-status-copy">Loading reference...</div>';
  const data = await safeFetch('/api/medical/reference?category=' + category, {}, null);
  if (!data || !data.items) { el.innerHTML = '<div class="prep-error-state">Failed to load reference.</div>'; return; }
  if (!data.items.length) { el.innerHTML = prepEmptyBlock('No reference entries are available for this topic.'); return; }

  el.innerHTML = '<h4 class="prep-med-ref-title">' + escapeHtml(data.title) + '</h4>' +
    '<div class="prep-table-wrap">' +
    '<table class="freq-table prep-data-table">' +
    '<thead><tr>' +
    Object.keys(data.items[0]).map(k => '<th>' + escapeHtml(k.replace(/_/g,' ')) + '</th>').join('') +
    '</tr></thead><tbody>' +
    data.items.map(item =>
      '<tr>' +
      Object.values(item).map(v => '<td>' + escapeHtml(String(v)) + '</td>').join('') +
      '</tr>'
    ).join('') +
    '</tbody></table></div>';
}

/* ─── Saved Routes ─── */
async function loadSavedRoutes() {
  const container = document.getElementById('saved-routes-list');
  if (!container) return;
  try {
    const routes = await safeFetch('/api/maps/routes', {}, []);
    if (!routes || routes.length === 0) {
      container.innerHTML = '<div class="settings-empty-state saved-route-empty"><strong>No Routes Yet</strong><span>Build a route from saved waypoints to keep travel plans, timing, and terrain review ready from one place.</span></div>';
      document.getElementById('elevation-profile-panel').style.display = 'none';
      return;
    }
    container.innerHTML = routes.map(r => {
        const wpIds = safeJsonParse(r.waypoint_ids, []);
        const wpCount = Array.isArray(wpIds) ? wpIds.length : 0;
      const difficulty = r.terrain_difficulty || 'moderate';
      const diffColor = difficulty === 'easy' ? 'var(--green)' : difficulty === 'hard' ? 'var(--red)' : 'var(--orange)';
      return '<div class="saved-route-row">' +
        '<div class="saved-route-main" role="button" tabindex="0" data-map-action="load-elevation-profile" data-route-id="' + r.id + '">' +
          '<strong class="saved-route-title">' + escapeHtml(r.name || 'Unnamed Route') + '</strong>' +
          '<div class="saved-route-meta">' + wpCount + ' waypoints' +
            (r.distance_km ? ' &mdash; ' + r.distance_km + ' km' : '') +
            ' &mdash; <span class="saved-route-difficulty" style="--saved-route-tone:' + diffColor + ';">' + difficulty + '</span></div>' +
        '</div>' +
        '<div class="saved-route-actions">' +
          '<button type="button" class="btn btn-sm saved-route-btn" data-map-action="show-elevation-profile" data-route-id="' + r.id + '">Profile</button>' +
          '<button type="button" class="btn btn-sm saved-route-btn" data-map-action="plan-route" data-route-id="' + r.id + '" title="Plan timed milestones for this route">Plan</button>' +
          '<button type="button" class="btn btn-sm btn-ghost saved-route-delete" data-map-action="delete-saved-route" data-route-id="' + r.id + '" title="Delete route">Delete</button>' +
        '</div>' +
      '</div>';
    }).join('');
  } catch(e) { container.innerHTML = '<div class="settings-empty-state saved-route-empty"><strong>Routes Could Not Be Loaded</strong><span>Refresh the route shelf and try again. Saved waypoints and route plans should return here once the workspace reconnects.</span></div>'; }
}

async function deleteSavedRoute(routeId) {
  if (!confirm('Delete this route?')) return;
  await safeFetch('/api/maps/routes/' + routeId, {method:'DELETE'});
  loadSavedRoutes();
  const epPanel = document.getElementById('elevation-profile-panel');
  if (epPanel) epPanel.style.display = 'none';
}

/* ─── Elevation Profile ─── */
async function loadElevationProfile(routeId) {
  const panel = document.getElementById('elevation-profile-panel');
  const canvas = document.getElementById('elevation-canvas');
  if (!panel || !canvas) return;
  const data = await safeFetch('/api/maps/elevation-profile/' + routeId, {}, null);
  if (!data || !data.points || data.points.length < 2) { panel.style.display = 'none'; return; }
  panel.style.display = 'block';

  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  canvas.width = canvas.offsetWidth * dpr;
  canvas.height = 150 * dpr;
  ctx.scale(dpr, dpr);
  const dw = canvas.offsetWidth, dh = 150;
  ctx.clearRect(0, 0, dw, dh);

  const elevs = data.points.map(p => p.elevation_m);
  const dists = data.points.map(p => p.distance_m);
  const minE = Math.min(...elevs) - 10;
  const maxE = Math.max(...elevs) + 10;
  const maxD = Math.max(...dists) || 1;
  const rangeE = maxE - minE || 1;

  const style = getComputedStyle(document.documentElement);
  const green = style.getPropertyValue('--green').trim() || '#4caf50';
  const border = style.getPropertyValue('--border').trim() || '#333';
  const textMuted = style.getPropertyValue('--text-muted').trim() || '#888';

  // Fill area under curve
  ctx.fillStyle = green + '20';
  ctx.beginPath();
  ctx.moveTo(40, dh - 20);
  data.points.forEach((p, i) => {
    const x = 40 + (p.distance_m / maxD) * (dw - 50);
    const y = 15 + ((maxE - p.elevation_m) / rangeE) * (dh - 40);
    ctx.lineTo(x, y);
  });
  ctx.lineTo(40 + (dists[dists.length-1] / maxD) * (dw - 50), dh - 20);
  ctx.closePath();
  ctx.fill();

  // Draw line
  ctx.strokeStyle = green;
  ctx.lineWidth = 2;
  ctx.beginPath();
  data.points.forEach((p, i) => {
    const x = 40 + (p.distance_m / maxD) * (dw - 50);
    const y = 15 + ((maxE - p.elevation_m) / rangeE) * (dh - 40);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Y-axis labels
  ctx.fillStyle = textMuted; ctx.font = '9px monospace';
  ctx.fillText(maxE.toFixed(0) + 'm', 2, 18);
  ctx.fillText(minE.toFixed(0) + 'm', 2, dh - 22);

  // Stats
  document.getElementById('elevation-stats').innerHTML =
    '<span>Distance: <strong>' + (data.total_distance_m / 1000).toFixed(1) + ' km</strong></span>' +
    '<span>Ascent: <strong class="text-green">+' + data.total_ascent + 'm</strong></span>' +
    '<span>Descent: <strong class="text-danger">-' + data.total_descent + 'm</strong></span>';
}

/* ─── Elevation Profile Chart ─── */
async function showElevationProfile(routeId) {
  try {
    const data = await apiFetch(`/api/maps/elevation-profile/${routeId}`);
    if (data.error) { toast(data.error, 'error'); return; }
    if (!data.points || !data.points.length) { toast('No elevation data — add waypoints with elevation to this route', 'warning'); return; }

    const el = document.getElementById('elevation-profile-chart');
    if (!el) return;
    el.style.display = 'block';

    const canvas = document.getElementById('elevation-canvas-detail');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width = el.offsetWidth - 24;
    const H = canvas.height = 200;
    const pad = {top: 20, right: 20, bottom: 35, left: 50};
    const plotW = W - pad.left - pad.right;
    const plotH = H - pad.top - pad.bottom;

    ctx.clearRect(0, 0, W, H);

    const pts = data.points;
    const maxDist = Math.max(...pts.map(p => p.distance_m)) || 1;
    const elevs = pts.map(p => p.elevation_m);
    const minElev = Math.min(...elevs) - 10;
    const maxElev = Math.max(...elevs) + 10;
    const elevRange = maxElev - minElev || 1;

    const xScale = d => pad.left + (d / maxDist) * plotW;
    const yScale = e => pad.top + plotH - ((e - minElev) / elevRange) * plotH;

    // Fill area under curve
    ctx.beginPath();
    ctx.moveTo(xScale(pts[0].distance_m), yScale(pts[0].elevation_m));
    for (let i = 1; i < pts.length; i++) {
      ctx.lineTo(xScale(pts[i].distance_m), yScale(pts[i].elevation_m));
    }
    ctx.lineTo(xScale(pts[pts.length-1].distance_m), pad.top + plotH);
    ctx.lineTo(xScale(pts[0].distance_m), pad.top + plotH);
    ctx.closePath();
    ctx.fillStyle = 'rgba(74,77,36,0.15)';
    ctx.fill();

    // Draw line
    ctx.beginPath();
    ctx.moveTo(xScale(pts[0].distance_m), yScale(pts[0].elevation_m));
    for (let i = 1; i < pts.length; i++) {
      ctx.lineTo(xScale(pts[i].distance_m), yScale(pts[i].elevation_m));
    }
    ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#4a4d24';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Waypoint dots + labels
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#4a4d24';
    for (const p of pts) {
      const x = xScale(p.distance_m);
      const y = yScale(p.elevation_m);
      ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--text-dim').trim() || '#5c5040';
      ctx.font = '9px monospace';
      ctx.fillText(p.name.slice(0, 12), x - 15, y - 8);
      ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#4a4d24';
    }

    // Axes
    ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--border').trim() || '#ccc';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(pad.left, pad.top); ctx.lineTo(pad.left, pad.top + plotH); ctx.lineTo(pad.left + plotW, pad.top + plotH);
    ctx.stroke();

    // Y-axis labels (elevation)
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim() || '#888';
    ctx.font = '9px monospace';
    for (let i = 0; i <= 4; i++) {
      const elev = minElev + (elevRange * i / 4);
      const y = yScale(elev);
      ctx.fillText(Math.round(elev) + 'm', 2, y + 3);
      ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(pad.left + plotW, y);
      ctx.strokeStyle = 'rgba(128,128,128,0.15)'; ctx.stroke();
    }

    // X-axis labels (distance)
    for (let i = 0; i <= 4; i++) {
      const dist = maxDist * i / 4;
      const x = xScale(dist);
      const label = dist >= 1000 ? (dist/1000).toFixed(1) + 'km' : Math.round(dist) + 'm';
      ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim() || '#888';
      ctx.fillText(label, x - 15, pad.top + plotH + 15);
    }

    // Stats
    const statsEl = document.getElementById('elevation-detail-stats');
    if (statsEl) {
      statsEl.innerHTML = `<span>Ascent: <b>${data.total_ascent}m</b></span>
        <span>Descent: <b>${data.total_descent}m</b></span>
        <span>Distance: <b>${(data.total_distance_m/1000).toFixed(2)}km</b></span>
        <span>Min: <b>${Math.round(minElev+10)}m</b></span>
        <span>Max: <b>${Math.round(maxElev-10)}m</b></span>`;
    }
  } catch(e) { toast('Failed to load elevation profile', 'error'); }
}

function hideElevationProfile() {
  const el = document.getElementById('elevation-profile-chart');
  if (el) el.style.display = 'none';
}

/* ─── Route Planner (v7.4.0) ─── */
let _routePlannerRouteId = null;

function openRoutePlanner(routeId) {
  _routePlannerRouteId = routeId;
  const modal = document.getElementById('route-planner-modal');
  if (!modal) return;
  document.getElementById('route-planner-inputs')?.classList.remove('is-hidden');
  document.getElementById('route-planner-results')?.classList.add('is-hidden');
  // Default departure = now, rounded to next :00
  const now = new Date();
  now.setMinutes(0, 0, 0);
  now.setHours(now.getHours() + 1);
  const iso = now.toISOString().slice(0, 16);  // YYYY-MM-DDTHH:MM (local input wants this format)
  const depart = document.getElementById('rp-depart');
  if (depart && !depart.value) depart.value = iso;
  modal.classList.remove('is-hidden');
  document.getElementById('rp-pace')?.focus();
}

function closeRoutePlanner() {
  const modal = document.getElementById('route-planner-modal');
  if (modal) modal.classList.add('is-hidden');
  _routePlannerRouteId = null;
}

async function runRoutePlan() {
  if (!_routePlannerRouteId) return;
  const payload = {
    route_id: _routePlannerRouteId,
    pace_kmh: parseFloat(document.getElementById('rp-pace')?.value) || 5,
    corridor_km: parseFloat(document.getElementById('rp-corridor')?.value) || 5,
    people: parseInt(document.getElementById('rp-people')?.value, 10) || 1,
    depart_iso: (document.getElementById('rp-depart')?.value || '') + ':00',
  };
  try {
    const plan = await apiPost('/api/maps/route-plan', payload);
    renderRoutePlan(plan);
  } catch (e) {
    toast(e?.data?.error || 'Could not generate route plan', 'error');
  }
}

function renderRoutePlan(plan) {
  const inputsEl = document.getElementById('route-planner-inputs');
  const resultsEl = document.getElementById('route-planner-results');
  if (!resultsEl) return;
  inputsEl?.classList.add('is-hidden');
  resultsEl.classList.remove('is-hidden');
  const t = plan.totals || {};
  const hrs = Math.floor(t.duration_hours || 0);
  const mins = Math.round(((t.duration_hours || 0) - hrs) * 60);
  const fmtTime = iso => {
    try {
      const d = new Date(iso);
      return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch (_) { return iso; }
  };
  const sunHtml = (plan.sun || []).map(s => {
    const sunrise = s.sunrise_iso ? fmtTime(s.sunrise_iso) : '(polar day/night)';
    const sunset = s.sunset_iso ? fmtTime(s.sunset_iso) : '(polar day/night)';
    return `<div class="route-plan-sun-row"><span>${escapeHtml(s.date)}</span> <span>Sunrise ${escapeHtml(sunrise)}</span> <span>Sunset ${escapeHtml(sunset)}</span></div>`;
  }).join('');
  const milestonesHtml = (plan.milestones || []).map((m, i) => {
    const inDark = _milestoneInDark(m.eta_iso, plan.sun || []);
    return `<div class="route-plan-milestone ${inDark ? 'route-plan-milestone-dark' : ''}">
      <div class="route-plan-mile-num">${i + 1}</div>
      <div class="route-plan-mile-main">
        <div class="route-plan-mile-name">${escapeHtml(m.name || '(unnamed)')}</div>
        <div class="route-plan-mile-meta">${m.cumulative_km} km from start · ETA ${escapeHtml(fmtTime(m.eta_iso))}${inDark ? ' · <strong>in darkness</strong>' : ''}</div>
      </div>
    </div>`;
  }).join('');
  const nearbyHtml = (plan.nearby_waypoints || []).length
    ? `<div class="route-plan-section-head">Resupply / shelter within corridor</div>
       <div class="route-plan-nearby">` +
      (plan.nearby_waypoints || []).map(n => `
        <div class="route-plan-nearby-row">
          <strong>${escapeHtml(n.name)}</strong>
          <span>${n.distance_from_route_km} km from ${escapeHtml(n.nearest_route_wp)}</span>
          ${n.category ? `<span class="route-plan-nearby-cat">${escapeHtml(n.category)}</span>` : ''}
        </div>`).join('') + `</div>`
    : '<div class="route-plan-empty">No nearby waypoints within the corridor. Widen the corridor or add more waypoints to your map.</div>';
  resultsEl.innerHTML = `
    <div class="route-plan-summary">
      <div class="route-plan-stat"><span class="route-plan-stat-num">${t.distance_km || 0}</span><span class="route-plan-stat-label">km</span></div>
      <div class="route-plan-stat"><span class="route-plan-stat-num">${hrs}h ${mins}m</span><span class="route-plan-stat-label">duration</span></div>
      <div class="route-plan-stat"><span class="route-plan-stat-num">${t.ascent_m || 0}</span><span class="route-plan-stat-label">m ascent</span></div>
      <div class="route-plan-stat"><span class="route-plan-stat-num">${t.water_l_total || 0}</span><span class="route-plan-stat-label">L water</span></div>
      <div class="route-plan-stat"><span class="route-plan-stat-num">${Math.round((t.kcal_total || 0) / 1000)}k</span><span class="route-plan-stat-label">kcal</span></div>
    </div>
    <div class="route-plan-sun">${sunHtml}</div>
    <div class="route-plan-section-head">Arrive by ${escapeHtml(fmtTime(t.arrive_iso))}</div>
    <div class="route-plan-milestones">${milestonesHtml}</div>
    ${nearbyHtml}
    <div class="prep-form-actions">
      <button class="btn btn-sm" type="button" onclick="openRoutePlanner(${_routePlannerRouteId})">Back to Inputs</button>
      <button class="btn btn-sm btn-ghost" type="button" data-map-action="close-route-planner">Close</button>
    </div>`;
}

function _milestoneInDark(eta_iso, sun) {
  try {
    const eta = new Date(eta_iso).getTime();
    for (const s of sun) {
      if (!s.sunrise_iso || !s.sunset_iso) continue;
      const rise = new Date(s.sunrise_iso).getTime();
      const set = new Date(s.sunset_iso).getTime();
      // Compare on the same day
      const etaDate = new Date(eta_iso).toISOString().slice(0, 10);
      if (etaDate === s.date) {
        return eta < rise || eta > set;
      }
    }
  } catch (_) {}
  return false;
}

/* ─── NomadChart: loaded from /static/js/chart.js ─── */
/* ─── Analytics Dashboard Loader ─── */
let _analyticsLoaded = false;
let _analyticsResizeTimer = null;

async function loadAnalyticsDashboard() {
  const [inv, burn, weather, power, vitals] = await Promise.all([
    safeFetch('/api/analytics/inventory-trends', {}, null),
    safeFetch('/api/analytics/consumption-rate', {}, null),
    safeFetch('/api/analytics/weather-history', {}, null),
    safeFetch('/api/analytics/power-history', {}, null),
    safeFetch('/api/analytics/medical-vitals', {}, null),
  ]);

  requestAnimationFrame(() => {
    _renderInventoryCharts(inv);
    _renderConsumptionChart(burn);
    _renderWeatherChart(weather);
    _renderPowerChart(power);
    _renderVitalsCharts(vitals);
  });

  if (!_analyticsLoaded) {
    _analyticsLoaded = true;
    window.addEventListener('resize', () => {
      clearTimeout(_analyticsResizeTimer);
      _analyticsResizeTimer = setTimeout(() => {
        if (document.getElementById('psub-analytics') && document.getElementById('psub-analytics').classList.contains('active')) {
          loadAnalyticsDashboard();
        }
      }, 300);
    });
  }
}

function _renderInventoryCharts(data) {
  if (!data || (!data.daily_counts.length && !data.categories.length)) {
    const c = document.getElementById('chart-inventory-trends');
    if (c) NomadChart._noData(c.getContext('2d'), c.parentElement.clientWidth, 200, 'No inventory activity yet — add items to see trends');
    const el = document.getElementById('inventory-stats');
    if (el) el.innerHTML = '';
    return;
  }

  // Line chart: added vs removed
  if (data.daily_counts.length) {
    NomadChart.line('chart-inventory-trends', {
      labels: data.daily_counts.map(d => d.date),
      datasets: [
        {label: 'Added', values: data.daily_counts.map(d => d.added), color: '#51cf66'},
        {label: 'Removed', values: data.daily_counts.map(d => d.removed), color: '#ff6b6b'},
      ],
    }, {title: 'Daily Inventory Activity', yLabel: 'Count', height: 180, showGrid: true});
  }

  // Donut: categories
  if (data.categories.length) {
    NomadChart.donut('chart-inventory-categories', {
      items: data.categories.map(c => ({label: c.name, value: c.count})),
    }, {size: 180});
  }

  // Stats
  const el = document.getElementById('inventory-stats');
  if (el) {
    el.innerHTML = '<div class="prep-analytics-stats-grid">' +
      '<div><strong>Total Items:</strong> ' + (data.total_items || 0) + '</div>' +
      '<div><strong>Categories:</strong> ' + (data.total_categories || 0) + '</div>' +
      '<div><strong>Expiring (30d):</strong> <span class="' + (data.expiring_30d > 0 ? 'prep-date-alert-danger' : '') + '">' + (data.expiring_30d || 0) + '</span></div>' +
    '</div>';
  }
}

function _renderConsumptionChart(data) {
  if (!data || !data.categories || !data.categories.length) {
    const c = document.getElementById('chart-consumption-rate');
    if (c) NomadChart._noData(c.getContext('2d'), c.parentElement.clientWidth, 120, 'No consumption data — set daily usage on inventory items');
    const el = document.getElementById('consumption-stats');
    if (el) el.innerHTML = '';
    return;
  }

  NomadChart.breakdown('chart-consumption-rate', {
    items: data.categories.map(c => ({
      label: c.name,
      value: c.days_remaining,
    })),
  }, {});

  const el = document.getElementById('consumption-stats');
  if (el && data.overall_days != null) {
    const runwayClass = data.overall_days > 90 ? 'prep-dose-rate-safe' : data.overall_days > 30 ? 'prep-dose-rate-warn' : 'prep-dose-rate-danger';
    el.innerHTML = 'Overall shortest runway: <strong class="' + runwayClass + '">' +
      (data.overall_days >= 9999 ? 'N/A' : Math.round(data.overall_days) + ' days') + '</strong>';
  }
}

function _renderWeatherChart(data) {
  if (!data || !data.readings || !data.readings.length) {
    const c = document.getElementById('chart-weather-history');
    if (c) NomadChart._noData(c.getContext('2d'), c.parentElement.clientWidth, 200, 'No weather data yet — log weather observations');
    return;
  }
  const r = data.readings;
  const datasets = [];
  if (r.some(d => d.temp != null)) {
    datasets.push({label: 'Temp (F)', values: r.map(d => d.temp), color: '#ff6b6b'});
  }
  if (r.some(d => d.pressure != null)) {
    datasets.push({label: 'Pressure (hPa)', values: r.map(d => d.pressure), color: '#74c0fc', rightAxis: true});
  }
  if (r.some(d => d.humidity != null)) {
    datasets.push({label: 'Humidity %', values: r.map(d => d.humidity), color: '#20c997', fill: true});
  }

  NomadChart.line('chart-weather-history', {
    labels: r.map(d => d.date),
    datasets: datasets,
  }, {title: 'Temperature / Pressure / Humidity', height: 220, rightAxis: datasets.some(d => d.rightAxis)});
}

function _renderPowerChart(data) {
  if (!data || !data.daily || !data.daily.length) {
    const c = document.getElementById('chart-power-history');
    if (c) NomadChart._noData(c.getContext('2d'), c.parentElement.clientWidth, 200, 'No power data yet — log power readings');
    return;
  }
  const d = data.daily;
  const datasets = [
    {label: 'Generated (kWh)', values: d.map(r => r.generated_kwh), color: '#51cf66'},
    {label: 'Consumed (kWh)', values: d.map(r => r.consumed_kwh), color: '#ff6b6b'},
  ];
  if (d.some(r => r.battery_level != null)) {
    datasets.push({label: 'Battery %', values: d.map(r => r.battery_level), color: '#ffd43b', lineOverlay: true});
  }

  NomadChart.bar('chart-power-history', {
    labels: d.map(r => r.date),
    datasets: datasets,
  }, {title: 'Daily Generation vs Consumption', height: 220, lineOverlay: d.some(r => r.battery_level != null)});
}

function _renderVitalsCharts(data) {
  const card = document.getElementById('analytics-vitals-card');
  const container = document.getElementById('chart-vitals-container');
  if (!data || !data.patients || !data.patients.length) {
    if (card) card.style.display = 'none';
    return;
  }
  if (card) card.style.display = 'block';
  container.innerHTML = '';

  data.patients.forEach((patient, pi) => {
    const div = document.createElement('div');
    div.className = 'prep-vitals-card';
    const safeName = escapeHtml(patient.name || 'Patient ' + (pi + 1));
    div.innerHTML = '<div class="prep-vitals-name">' + safeName + '</div>' +
      '<div class="prep-vitals-spark-grid">' +
      '<div><span class="prep-vitals-label">Pulse</span><canvas id="spark-pulse-' + pi + '"></canvas></div>' +
      '<div><span class="prep-vitals-label">Temp</span><canvas id="spark-temp-' + pi + '"></canvas></div>' +
      '<div><span class="prep-vitals-label">SpO2</span><canvas id="spark-spo2-' + pi + '"></canvas></div>' +
      '</div>';
    container.appendChild(div);

    requestAnimationFrame(() => {
      NomadChart.sparkline('spark-pulse-' + pi, patient.readings.map(r => r.pulse), {color: '#ff6b6b', width: 120, height: 28});
      NomadChart.sparkline('spark-temp-' + pi, patient.readings.map(r => r.temp), {color: '#ffd43b', width: 120, height: 28});
      NomadChart.sparkline('spark-spo2-' + pi, patient.readings.map(r => r.spo2), {color: '#51cf66', width: 120, height: 28});
    });
  });
}

/* ─── Offline Geocoding ─── */
let _geocodeTimeout = null;
async function geocodeSearch(query) {
  if (!query || query.length < 2) { document.getElementById('geocode-results').style.display = 'none'; return; }
  clearTimeout(_geocodeTimeout);
  _geocodeTimeout = setTimeout(async () => {
    try {
      const results = await safeFetch(`/api/geocode/search?q=${encodeURIComponent(query)}`, {}, []);
      const el = document.getElementById('geocode-results');
      if (!results.length) { el.style.display = 'none'; return; }
      el.style.display = 'block';
      el.innerHTML = results.slice(0, 10).map(r =>
        `<div class="map-geocode-item"
              role="button" tabindex="0" data-map-action="geocode-go" data-geocode-lat="${r.lat}" data-geocode-lng="${r.lng}" data-geocode-name="${escapeAttr(r.name)}">
          <span class="map-geocode-type">${escapeHtml(r.type)}</span>
          <span class="map-geocode-name">${escapeHtml(r.name)}</span>
          <span class="map-geocode-coords">${r.lat?.toFixed(4)}, ${r.lng?.toFixed(4)}</span>
        </div>`
      ).join('');
    } catch(e) {}
  }, 300);
}

function geocodeGo(lat, lng, name) {
  if (_map) {
    _map.flyTo({center: [lng, lat], zoom: 15});
    new maplibregl.Popup({closeOnClick: true}).setLngLat([lng, lat]).setHTML(
      renderMapPopupShell({ title: escapeHtml(name) })
    ).addTo(_map);
  }
  document.getElementById('geocode-input').value = '';
}

async function reverseGeocode(lat, lng) {
  try {
    const results = await safeFetch(`/api/geocode/reverse?lat=${lat}&lng=${lng}`, {}, []);
    if (results.length) {
      const nearest = results[0];
      const distStr = nearest.distance_m >= 1000 ? (nearest.distance_m/1000).toFixed(1) + 'km' : nearest.distance_m + 'm';
      toast(`Nearest: ${nearest.name} (${distStr} away)`, 'info');
    }
  } catch(e) {}
}

/* ─── Voice Input (Web Speech API) ─── */
let _voiceRecognition = null;
function voiceInput(targetInputId) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) { toast('Speech recognition not available in this browser', 'warning'); return; }
  const input = document.getElementById(targetInputId);
  if (!input) return;

  if (_voiceRecognition) {
    _voiceRecognition.stop();
    _voiceRecognition = null;
    document.querySelectorAll('.voice-active').forEach(b => b.classList.remove('voice-active'));
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.lang = 'en-US';
  recognition.interimResults = true;
  recognition.continuous = false;
  _voiceRecognition = recognition;

  // Visual feedback
  const btn = document.querySelector(`[onclick*="voiceInput('${targetInputId}')"]`);
  if (btn) btn.classList.add('voice-active');

  recognition.onresult = (event) => {
    let transcript = '';
    for (let i = 0; i < event.results.length; i++) {
      transcript += event.results[i][0].transcript;
    }
    input.value = transcript;
  };

  recognition.onend = () => {
    _voiceRecognition = null;
    if (btn) btn.classList.remove('voice-active');
    // Auto-submit if it's the copilot. Mark the call as voice-originated so
    // askCopilot can speak the answer via NomadSpeech.
    if (targetInputId === 'copilot-input' && input.value.trim()) {
      window._copilotVoiceTurn = true;
      askCopilot();
    }
  };

  recognition.onerror = (e) => {
    _voiceRecognition = null;
    if (btn) btn.classList.remove('voice-active');
    if (e.error !== 'aborted') toast('Voice error: ' + e.error, 'warning');
  };

  // Clear any stale input to prevent auto-submitting old text on timeout
  input.value = '';
  recognition.start();
  toast('Listening...', 'info');
}

/* ─── Voice Copilot Preferences (Settings row) ─── */
function hydrateVoicePrefs() {
  if (typeof window.NomadSpeech === 'undefined' || !window.NomadSpeech.isSupported()) {
    const row = document.getElementById('voice-prefs-row');
    if (row) {
      const hint = document.getElementById('voice-prefs-hint');
      if (hint) hint.textContent = 'Not supported in this browser.';
      const tog = document.getElementById('voice-tts-toggle');
      const sel = document.getElementById('voice-voice-select');
      const rate = document.getElementById('voice-rate-slider');
      [tog, sel, rate].forEach(el => { if (el) el.disabled = true; });
    }
    return;
  }
  const prefs = window.NomadSpeech.getPrefs();
  const tog = document.getElementById('voice-tts-toggle');
  const sel = document.getElementById('voice-voice-select');
  const rate = document.getElementById('voice-rate-slider');
  if (tog) tog.checked = !!prefs.enabled;
  if (rate) rate.value = prefs.rate || 1;
  if (sel) {
    const populate = () => {
      const voices = window.NomadSpeech.getVoices();
      const prior = sel.value || prefs.voiceURI || '';
      sel.innerHTML = '<option value="">Default voice</option>' +
        voices.map(v => `<option value="${escapeAttr(v.voiceURI)}">${escapeHtml(v.name)} (${escapeHtml(v.lang)})</option>`).join('');
      if (prior) sel.value = prior;
    };
    populate();
    // Voices arrive async in Chromium — repopulate when they load
    setTimeout(populate, 600);
  }
}

/* ─── Home Location (used by weather, sun calc, and SR proximity) ─── */
async function hydrateHomeLocation() {
  const latEl = document.getElementById('home-lat-input');
  const lngEl = document.getElementById('home-lng-input');
  const radEl = document.getElementById('proximity-radius-select');
  if (!latEl || !lngEl) return;
  try {
    const s = await apiFetch('/api/settings');
    if (s.latitude) latEl.value = s.latitude;
    if (s.longitude) lngEl.value = s.longitude;
    if (s.proximity_radius_km && radEl) radEl.value = s.proximity_radius_km;
  } catch (_) { /* not fatal — user can still fill the form */ }
}

async function saveHomeLocation() {
  const lat = parseFloat(document.getElementById('home-lat-input')?.value);
  const lng = parseFloat(document.getElementById('home-lng-input')?.value);
  const radEl = document.getElementById('proximity-radius-select');
  const radius = radEl ? radEl.value : '500';
  if (!isFinite(lat) || !isFinite(lng) || lat < -90 || lat > 90 || lng < -180 || lng > 180) {
    toast('Enter a valid latitude and longitude', 'warning');
    return;
  }
  try {
    await apiPut('/api/settings', {
      latitude: String(lat),
      longitude: String(lng),
      proximity_radius_km: String(radius),
    });
    toast('Home location saved', 'success');
    // Refresh the proximity card immediately if Situation Room is mounted
    if (typeof loadSitroomProximity === 'function') loadSitroomProximity();
  } catch (e) {
    toast('Failed to save location', 'error');
  }
}

function detectHomeLocation() {
  if (!navigator.geolocation) {
    toast('Geolocation not supported in this browser', 'warning');
    return;
  }
  toast('Detecting location...', 'info');
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const latEl = document.getElementById('home-lat-input');
      const lngEl = document.getElementById('home-lng-input');
      if (latEl) latEl.value = pos.coords.latitude.toFixed(4);
      if (lngEl) lngEl.value = pos.coords.longitude.toFixed(4);
      saveHomeLocation();
    },
    (err) => {
      toast('Location detection failed: ' + (err.message || err.code), 'error');
    },
    { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 }
  );
}

function saveVoicePrefs() {
  if (typeof window.NomadSpeech === 'undefined') return;
  const tog = document.getElementById('voice-tts-toggle');
  const sel = document.getElementById('voice-voice-select');
  const rate = document.getElementById('voice-rate-slider');
  window.NomadSpeech.setPrefs({
    enabled: tog ? !!tog.checked : true,
    voiceURI: sel ? sel.value : '',
    rate: rate ? parseFloat(rate.value) || 1 : 1,
  });
}

/* ─── Federation Peer Management UI ─── */
async function loadFederationPeers() {
  const peers = await safeFetch('/api/federation/peers', {}, []);
  const el = document.getElementById('federation-peers-list');
  if (!el) return;
  if (!peers.length) {
    el.innerHTML = '<div class="prep-empty-state prep-empty-state-wide">No peers connected. Click "+ Add Peer" to connect with another NOMAD node.</div>';
    return;
  }
  el.innerHTML = peers.map(p => {
    const trustKey = (p.trust_level || 'observer').toLowerCase();
    const trustLabel = trustKey.split('-').map(part => part.charAt(0).toUpperCase() + part.slice(1)).join(' ');
    return `
    <div class="contact-card prep-peer-card">
      <div class="prep-card-head">
        <div class="prep-card-meta">
          <div class="cc-name">${escapeHtml(p.node_name || p.node_id)}</div>
          <div class="cc-field prep-ops-mono-field">${escapeHtml(p.node_id)}</div>
        </div>
        <span class="prep-trust-pill prep-trust-${escapeAttr(trustKey)}">${escapeHtml(trustLabel)}</span>
      </div>
      <div class="cc-field"><strong>IP:</strong> ${escapeHtml(p.ip||'—')}:${p.port||8080}</div>
      <div class="cc-field"><strong>Last seen:</strong> ${p.last_seen ? timeAgo(p.last_seen) : 'Never'}</div>
      <div class="cc-field"><strong>Auto-sync:</strong> <span class="${p.auto_sync ? 'prep-sync-on' : 'prep-sync-off'}">${p.auto_sync ? 'ON' : 'OFF'}</span></div>
      <div class="prep-peer-footer">
        <label class="prep-field prep-peer-select-field">
          <span class="prep-field-label">Trust</span>
          <select data-change-action="update-peer-trust" data-node-id="${escapeAttr(p.node_id)}" class="prep-field-control prep-peer-select">
          ${['observer','member','trusted','admin'].map(t => `<option value="${t}" ${p.trust_level===t?'selected':''}>${t}</option>`).join('')}
          </select>
        </label>
        <button type="button" class="btn btn-sm btn-danger" data-prep-action="remove-peer" data-node-id="${escapeAttr(p.node_id)}">Remove</button>
      </div>
    </div>`;
  }).join('');
}

function showAddPeerForm() {
  const form = document.getElementById('add-peer-form');
  form.style.display = form.style.display === 'block' ? 'none' : 'block';
}

function hideAddPeerForm() {
  const form = document.getElementById('add-peer-form');
  if (form) form.style.display = 'none';
}

async function submitAddPeer() {
  const data = {
    node_id: document.getElementById('fp-nodeid').value.trim(),
    node_name: document.getElementById('fp-name').value.trim(),
    trust_level: document.getElementById('fp-trust').value,
    ip: document.getElementById('fp-ip').value.trim(),
  };
  if (!data.node_id) { toast('Node ID required', 'warning'); return; }
  try {
    await apiPost('/api/federation/peers', data);
    hideAddPeerForm();
    loadFederationPeers();
    toast('Peer added', 'success');
  } catch(e) { toast('Failed to add peer', 'error'); }
}

async function updatePeerTrust(nodeId, trust) {
  try {
    await apiPut('/api/federation/peers/' + nodeId + '/trust', {trust_level: trust});
    toast('Trust updated', 'success');
  } catch(e) { toast('Failed to update trust', 'error'); }
}

async function removePeer(nodeId) {
  if (!confirm('Remove this federation peer?')) return;
  try {
    await apiDelete('/api/federation/peers/' + nodeId);
    loadFederationPeers();
    toast('Peer removed', 'success');
  } catch(e) { toast('Remove failed — network error', 'error'); }
}

async function loadFederationMarketplace() {
  const el = document.getElementById('federation-marketplace');
  if (!el) return;
  el.style.display = el.style.display === 'none' ? 'block' : 'none';
  if (el.style.display === 'none') return;
  const [offers, requests] = await Promise.all([
    safeFetch('/api/federation/offers', {}, []),
    safeFetch('/api/federation/requests', {}, []),
  ]);
  el.innerHTML = `
    <div class="prep-market-grid">
      <div class="prep-market-column">
        <div class="prep-market-header">
          <span class="prep-market-label prep-market-label-offers">Offers (Have)</span>
          <button type="button" class="btn btn-sm" data-prep-action="post-federation-offer">+ Post</button>
        </div>
        <div class="prep-market-list">
          ${offers.length ? offers.map(o => `<div class="prep-market-item prep-market-item-offer">
            <div class="prep-market-item-title">${escapeHtml(o.item_type)}</div>
            <div class="prep-market-item-copy">${escapeHtml(String(o.quantity))}${o.notes ? ` · ${escapeHtml(o.notes)}` : ''}</div>
          </div>`).join('') : '<div class="prep-market-empty">No offers posted</div>'}
        </div>
      </div>
      <div class="prep-market-column">
        <div class="prep-market-header">
          <span class="prep-market-label prep-market-label-requests">Requests (Need)</span>
          <button type="button" class="btn btn-sm" data-prep-action="post-federation-request">+ Post</button>
        </div>
        <div class="prep-market-list">
          ${requests.length ? requests.map(r => `<div class="prep-market-item prep-market-item-request">
            <div class="prep-market-item-title">${escapeHtml(r.item_type)}</div>
            <div class="prep-market-item-copy">${escapeHtml(r.description || '')}</div>
            <div class="prep-market-urgency ${r.urgency === 'critical' ? 'prep-market-urgency-critical' : ''}">${escapeHtml(r.urgency || 'normal')}</div>
          </div>`).join('') : '<div class="prep-market-empty">No requests posted</div>'}
        </div>
      </div>
    </div>`;
}

async function postOffer() {
  const type = prompt('What are you offering? (e.g., diesel, antibiotics, water)');
  if (!type) return;
  const qty = prompt('Quantity?') || '0';
  const notes = prompt('Notes (optional)') || '';
  try {
    await apiPost('/api/federation/offers', {item_type: type, quantity: parseFloat(qty), notes});
    loadFederationMarketplace();
    toast('Offer posted', 'success');
  } catch(e) { toast('Failed to post offer', 'error'); }
}

async function postRequest() {
  const type = prompt('What do you need? (e.g., antibiotics, fuel, medical)');
  if (!type) return;
  const desc = prompt('Description?') || '';
  const urgency = prompt('Urgency? (normal/urgent/critical)') || 'normal';
  try {
    await apiPost('/api/federation/requests', {item_type: type, description: desc, urgency});
    loadFederationMarketplace();
    toast('Request posted', 'success');
  } catch(e) { toast('Failed to post request', 'error'); }
}

/* ─── TCCC MARCH Interactive Wizard ─── */
let _tcccPatientId = null;
let _tcccStep = 0;
let _tcccLog = [];
let _tcccProtocol = [];

function closeTCCCModal() {
  if (typeof NomadModal !== 'undefined' && NomadModal.isOpen()) { NomadModal.close(); return; }
  const modal = document.getElementById('tccc-modal');
  if (modal) modal.style.display = 'none';
}

async function startTCCC(patientId) {
  _tcccPatientId = patientId;
  _tcccStep = 0;
  _tcccLog = [];
  _tcccProtocol = await safeFetch('/api/medical/tccc-protocol', {}, []);
  if (!_tcccProtocol.length) { toast('Failed to load TCCC protocol', 'error'); return; }
  const protocol = _tcccProtocol;
  let modal = document.getElementById('tccc-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'tccc-modal';
    modal.className = 'modal-overlay prep-tccc-modal';
    modal.onclick = (e) => { if (e.target === modal) closeTCCCModal(); };
    document.body.appendChild(modal);
  }
  modal.style.display = 'flex';
  if (typeof NomadModal !== 'undefined') NomadModal.open(modal, {
    onClose: () => closeTCCCModal(),
  });
  renderTCCCStep(protocol);
}

function renderTCCCStep(protocol) {
  const modal = document.getElementById('tccc-modal');
  if (!modal) return;
  const step = protocol[_tcccStep];
  if (!step) { finishTCCC(protocol); return; }
  const stepColors = {M:'#c62828',A:'#e65100',R:'#1565c0',C:'#6a1b9a',H:'#2e7d32'};
  const now = new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'});
  const actionRows = step.actions.map((a, i) => {
    const logged = _tcccLog.find(l => l.step === _tcccStep && l.action === i);
    return `<div class="prep-tccc-action-row" id="tccc-action-${i}">
      <button type="button" class="btn btn-sm prep-tccc-action-btn ${logged ? 'prep-tccc-action-done' : 'prep-utility-tab'}" data-prep-action="complete-tccc-action" data-tccc-action-index="${i}" ${logged ? 'disabled' : ''}>${logged ? logged.time : 'Done'}</button>
      <div class="prep-tccc-action-copy">${escapeHtml(a)}</div>
    </div>`;
  }).join('');
  modal.innerHTML = `
    <div class="modal-card prep-tccc-card" style="--prep-tccc-tone:${stepColors[step.step]};">
      <div class="prep-tccc-header">
        <div class="prep-tccc-header-copy">
          <div class="prep-tccc-step-badge">${step.step}</div>
          <div>
            <div class="prep-tccc-step-title">${escapeHtml(step.name)}</div>
            <div class="prep-tccc-meta">Step ${_tcccStep + 1} of ${protocol.length} · ${now}</div>
          </div>
        </div>
        <button type="button" class="btn btn-sm modal-close prep-tccc-close" data-prep-action="close-tccc-modal" aria-label="Close TCCC wizard">&#10005;</button>
      </div>
      <div class="modal-body prep-tccc-body">
        <div class="prep-tccc-actions-list">
          ${actionRows}
        </div>
        <div class="prep-tccc-footer">
          ${_tcccStep > 0 ? `<button type="button" class="btn btn-sm" data-prep-action="tccc-step-prev">&#9664; Prev</button>` : ''}
          <div class="prep-tccc-spacer"></div>
          <button type="button" class="btn btn-sm btn-primary" data-prep-action="tccc-step-next">
            ${_tcccStep < protocol.length - 1 ? 'Next Step &#9654;' : 'Complete TCCC'}
          </button>
        </div>
      </div>
    </div>`;
}

function completeTCCCAction(idx, btn) {
  const now = new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'});
  btn.textContent = now;
  btn.className = 'btn btn-sm prep-tccc-action-btn prep-tccc-action-done';
  btn.disabled = true;
  _tcccLog.push({step: _tcccStep, action: idx, time: now});
}

function finishTCCC(protocol) {
  const modal = document.getElementById('tccc-modal');
  if (!modal) return;
  modal.innerHTML = `
    <div class="modal-card prep-tccc-card prep-tccc-complete-card">
      <div class="prep-tccc-complete-icon">&#9989;</div>
      <div class="prep-tccc-complete-title">TCCC March Complete</div>
      <div class="prep-tccc-meta">${_tcccLog.length} actions recorded</div>
      <div class="prep-tccc-footer prep-tccc-footer-center">
        ${_tcccPatientId ? `<button type="button" class="btn btn-sm btn-primary" data-prep-action="generate-handoff-close-tccc" data-patient-id="${_tcccPatientId}">Generate Handoff Report</button>` : ''}
        <button type="button" class="btn btn-sm" data-prep-action="close-tccc-modal">Close</button>
      </div>
    </div>`;
}

async function generateHandoff(patientId) {
  const data = await safeFetch(`/api/medical/handoff/${patientId}`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({from_provider:'Field Team',to_provider:'Receiving'})}, null);
  if (data && data.id) {
    openAppFrame('SBAR Handoff', `/api/medical/handoff/${data.id}/print`);
    toast('Handoff report generated', 'success');
  } else {
    toast('Failed to generate handoff', 'error');
  }
}

/* ─── HF Propagation Forecast ─── */
async function loadPropagation() {
  const el = document.getElementById('propagation-panel');
  if (!el) return;
  const data = await safeFetch('/api/radio/propagation', {}, null);
  if (!data) { el.innerHTML = prepEmptyBlock('Failed to load propagation data.'); return; }

  el.innerHTML = `
    <div class="prep-dashboard-grid prep-propagation-metrics">
      ${prepMetricCard('Est. MUF', `${data.muf_estimate} MHz`, 'var(--accent)')}
      ${prepMetricCard('Conditions', data.is_day ? 'Daytime' : 'Nighttime', data.is_day ? 'var(--green)' : 'var(--accent)')}
      ${prepMetricCard('Season', data.season_factor >= 1 ? 'Good' : data.season_factor >= 0.9 ? 'Fair' : 'Reduced', 'var(--text)')}
    </div>
    <div class="prep-table-wrap prep-propagation-table-shell">
    <table class="freq-table prep-inline-table">
      <tr><th>Band</th><th>Freq</th><th>Status</th><th>Quality</th><th>Range</th><th>Best</th></tr>
      ${data.bands.map(b => {
        const color = b.status === 'OPEN' ? (b.quality === 'excellent' ? 'var(--green)' : b.quality === 'good' ? 'var(--accent)' : 'var(--orange)') : 'var(--red)';
        const qualityToneClass = color === 'var(--green)' ? 'text-green' : color === 'var(--accent)' ? 'text-accent' : color === 'var(--orange)' ? 'text-orange' : 'text-red';
        return '<tr><td><strong>' + b.name + '</strong></td><td class="prep-data-cell">' + b.freq + ' MHz</td><td><span class="prep-inline-pill" style="--prep-pill-tone:' + color + ';">' + b.status + '</span></td><td class="' + qualityToneClass + '">' + b.quality + '</td><td>' + b.range + '</td><td class="prep-muted-cell">' + b.best + '</td></tr>';
      }).join('')}
    </table>
    </div>
    <div class="prep-status-footnote prep-propagation-note">${escapeHtml(data.note)}</div>`;
}

/* ─── Frequency Database UI ─── */
let _freqData = [];
async function loadFreqDatabase() {
  _freqData = await safeFetch('/api/comms/frequencies', {}, []);
  renderFreqTable();
}
function renderFreqTable() {
  const body = document.getElementById('freq-table-body');
  if (!body) return;
  const search = (document.getElementById('freq-search')?.value || '').toLowerCase();
  const licFilter = document.getElementById('freq-license-filter')?.value || '';
  let filtered = _freqData.filter(f => {
    if (search && !f.service.toLowerCase().includes(search) && !f.description.toLowerCase().includes(search) && !f.notes.toLowerCase().includes(search)) return false;
    if (licFilter !== '' && String(f.license_required) !== licFilter) return false;
    return true;
  });
  // Group by service type
  const groups = {};
  filtered.forEach(f => { const svc = f.service.split(' ')[0]; if (!groups[svc]) groups[svc] = []; groups[svc].push(f); });
  let html = '';
  for (const [svc, freqs] of Object.entries(groups)) {
    freqs.sort((a,b) => a.frequency - b.frequency);
    for (const f of freqs) {
      const priColor = f.priority >= 8 ? 'var(--green)' : f.priority >= 5 ? 'var(--text-dim)' : 'var(--text-muted)';
      html += `<tr>
        <td class="runtime-mono-cell-strong" style="cursor:pointer" data-copy="${f.frequency.toFixed(4)}" data-copy-label="${f.frequency.toFixed(4)} MHz" title="Click to copy">${f.frequency.toFixed(4)}</td>
        <td>${escapeHtml(f.mode)}</td>
        <td class="text-strong">${escapeHtml(f.service)}</td>
        <td>${escapeHtml(f.description)}${f.notes ? ` <span class="runtime-inline-note">(${escapeHtml(f.notes)})</span>` : ''}</td>
        <td>${f.license_required ? '<span class="text-orange">YES</span>' : '<span class="text-green">NO</span>'}</td>
        <td class="runtime-priority-cell ${priColor === 'var(--green)' ? 'text-green' : priColor === 'var(--text-dim)' ? 'text-dim' : 'text-muted'}">${f.priority}</td>
        <td><button type="button" class="btn btn-sm btn-ghost freq-delete-btn" data-prep-action="delete-freq" data-freq-id="${f.id}" aria-label="Delete freq">&#10005;</button></td>
      </tr>`;
    }
  }
  body.innerHTML = html || '<tr><td colspan="7" class="freq-table-empty">No frequencies found</td></tr>';
  const countEl = document.getElementById('freq-count');
  if (countEl) countEl.textContent = `${filtered.length} frequencies loaded`;
}
function filterFreqTable() { renderFreqTable(); }
async function deleteFreq(id) {
  if (!confirm('Delete this frequency?')) return;
  try {
    await apiDelete(`/api/comms/frequencies/${id}`);
  } catch(e) { toast('Delete failed — network error', 'error'); return; }
  loadFreqDatabase();
}
function showAddFreqForm() {
  const existing = document.getElementById('add-freq-form');
  if (existing) { existing.remove(); return; }
  const form = document.createElement('div');
  form.id = 'add-freq-form';
  form.className = 'prep-calc-inline-builder';
  form.innerHTML = `
    <div class="prep-calc-inline-field"><label class="prep-calc-inline-label">Freq (MHz)</label><input type="number" step="0.001" id="af-freq" class="prep-calc-inline-input prep-calc-inline-input-sm"></div>
    <div class="prep-calc-inline-field"><label class="prep-calc-inline-label">Mode</label><select id="af-mode" class="prep-calc-inline-select"><option>FM</option><option>AM</option><option>LSB</option><option>USB</option><option>LoRa</option></select></div>
    <div class="prep-calc-inline-field"><label class="prep-calc-inline-label">Service</label><input type="text" id="af-service" placeholder="e.g. Local Repeater" class="prep-calc-inline-input prep-calc-inline-input-md"></div>
    <div class="prep-calc-inline-field"><label class="prep-calc-inline-label">Description</label><input type="text" id="af-desc" placeholder="Description" class="prep-calc-inline-input prep-calc-inline-input-lg"></div>
    <div class="prep-calc-inline-field"><label class="prep-calc-inline-label">License?</label><select id="af-lic" class="prep-calc-inline-select"><option value="0">No</option><option value="1">Yes</option></select></div>
    <button type="button" class="btn btn-sm btn-primary" data-prep-action="submit-add-freq">ADD</button>
    <button type="button" class="btn btn-sm btn-ghost" data-prep-action="cancel-add-freq-form">CANCEL</button>`;
  document.getElementById('freq-table-dynamic').parentElement.insertBefore(form, document.getElementById('freq-table-dynamic'));
}
async function submitAddFreq() {
  const data = {
    frequency: parseFloat(document.getElementById('af-freq').value) || 0,
    mode: document.getElementById('af-mode').value,
    service: document.getElementById('af-service').value,
    description: document.getElementById('af-desc').value,
    license_required: parseInt(document.getElementById('af-lic').value),
    priority: 5,
  };
  if (!data.frequency || !data.service) { toast('Frequency and service required', 'warning'); return; }
  try {
    await apiPost('/api/comms/frequencies', data);
    document.getElementById('add-freq-form')?.remove();
    loadFreqDatabase();
    toast('Frequency added', 'success');
  } catch(e) { toast('Failed to add frequency', 'error'); }
}

function exportChirpCSV() {
  const channels = [
    // Location,Name,Frequency,Duplex,Offset,Tone,rToneFreq,cToneFreq,DtcsCode,DtcsPolarity,Mode,TStep,Skip,Comment,URCALL,RPT1CALL,RPT2CALL
    ['0','NOAA-1','162.400000','','0.000000','','88.5','88.5','023','NN','NFM','5.00','','NOAA Weather Ch 1','','',''],
    ['1','NOAA-2','162.425000','','0.000000','','88.5','88.5','023','NN','NFM','5.00','','NOAA Weather Ch 2','','',''],
    ['2','NOAA-3','162.450000','','0.000000','','88.5','88.5','023','NN','NFM','5.00','','NOAA Weather Ch 3','','',''],
    ['3','NOAA-4','162.475000','','0.000000','','88.5','88.5','023','NN','NFM','5.00','','NOAA Weather Ch 4','','',''],
    ['4','NOAA-5','162.500000','','0.000000','','88.5','88.5','023','NN','NFM','5.00','','NOAA Weather Ch 5','','',''],
    ['5','NOAA-6','162.525000','','0.000000','','88.5','88.5','023','NN','NFM','5.00','','NOAA Weather Ch 6','','',''],
    ['6','NOAA-7','162.550000','','0.000000','','88.5','88.5','023','NN','NFM','5.00','','NOAA Weather Ch 7','','',''],
    ['7','FRS-1','462.562500','','0.000000','','88.5','88.5','023','NN','NFM','5.00','','FRS Ch 1 - Rally','','',''],
    ['8','FRS-3','462.612500','','0.000000','','88.5','88.5','023','NN','NFM','5.00','','FRS Ch 3 - Emergency','','',''],
    ['9','FRS-7','462.712500','','0.000000','','88.5','88.5','023','NN','NFM','5.00','','FRS Ch 7','','',''],
    ['10','GMRS-20','462.675000','','0.000000','','88.5','88.5','023','NN','NFM','5.00','','GMRS Ch 20 - National Emergency','','',''],
    ['11','MURS-1','151.820000','','0.000000','','88.5','88.5','023','NN','NFM','5.00','','MURS Ch 1','','',''],
    ['12','MURS-3','151.940000','','0.000000','','88.5','88.5','023','NN','NFM','5.00','','MURS Ch 3','','',''],
    ['13','CB-9','27.065000','','0.000000','','88.5','88.5','023','NN','AM','5.00','','CB Ch 9 - Emergency','','',''],
    ['14','CB-19','27.185000','','0.000000','','88.5','88.5','023','NN','AM','5.00','','CB Ch 19 - Truckers','','',''],
    ['15','2M-CALL','146.520000','','0.000000','','88.5','88.5','023','NN','FM','5.00','','2m National Simplex Calling','','',''],
    ['16','2M-EMRG','146.550000','','0.000000','','88.5','88.5','023','NN','FM','5.00','','2m Emergency Simplex','','',''],
    ['17','70CM-CALL','446.000000','','0.000000','','88.5','88.5','023','NN','FM','5.00','','70cm National Simplex Calling','','',''],
    ['18','MARINE-16','156.800000','','0.000000','','88.5','88.5','023','NN','FM','5.00','','Marine Ch 16 - Distress (RX only)','','',''],
    ['19','WWV-10','10.000000','','0.000000','','88.5','88.5','023','NN','AM','1.00','','NIST Time Signal WWV 10 MHz','','',''],
    ['20','WWV-5','5.000000','','0.000000','','88.5','88.5','023','NN','AM','1.00','','NIST Time Signal WWV 5 MHz','','',''],
    ['21','JS8-40M','7.078000','','0.000000','','88.5','88.5','023','NN','USB','0.50','','JS8Call 40m Emergency Net','','',''],
    ['22','JS8-20M','14.078000','','0.000000','','88.5','88.5','023','NN','USB','0.50','','JS8Call 20m Net','','',''],
    ['23','WL-20M','14.103000','','0.000000','','88.5','88.5','023','NN','USB','0.50','','Winlink/APRS 20m','','',''],
    ['24','SATERN','14.265000','','0.000000','','88.5','88.5','023','NN','USB','0.50','','SATERN Emergency Net 20m','','',''],
    ['25','HF-40M','7.250000','','0.000000','','88.5','88.5','023','NN','LSB','0.50','','HF 40m Phone Band','','',''],
    ['26','HF-20M','14.225000','','0.000000','','88.5','88.5','023','NN','USB','0.50','','HF 20m Phone Band','','',''],
    ['27','HF-80M','3.900000','','0.000000','','88.5','88.5','023','NN','LSB','0.50','','HF 80m Phone Band','','',''],
  ];
  const header = 'Location,Name,Frequency,Duplex,Offset,Tone,rToneFreq,cToneFreq,DtcsCode,DtcsPolarity,Mode,TStep,Skip,Comment,URCALL,RPT1CALL,RPT2CALL\n';
  const csv = header + channels.map(r => r.join(',')).join('\n');
  const blob = new Blob([csv], {type: 'text/csv'});
  downloadBlobFile(blob, 'NOMAD_Emergency_Channels.csv');
  toast('CHIRP CSV exported', 'success');
}

// ═══════════════════════════════════════════════════════════════
// CALCULATORS — ADVANCED
// ═══════════════════════════════════════════════════════════════

// --- Burn Surface Area (Rule of Nines) ---
function calcBurnArea() {
  const weightInput = document.getElementById('burn-weight');
  const el = document.getElementById('burn-result');
  if (!weightInput || !el) return;
  const regions = {
    'burn-head': 9, 'burn-chest': 9, 'burn-abdomen': 9,
    'burn-upperback': 9, 'burn-lowerback': 9,
    'burn-rightarm': 9, 'burn-leftarm': 9,
    'burn-rightthigh': 9, 'burn-rightleg': 9,
    'burn-leftthigh': 9, 'burn-leftleg': 9,
    'burn-genitalia': 1
  };
  let tbsa = 0;
  for (const [id, pct] of Object.entries(regions)) {
    if (document.getElementById(id) && document.getElementById(id).checked) tbsa += pct;
  }
  const weight = parseFloat(weightInput.value) || 70;
  if (tbsa === 0) { el.innerHTML = '<span class="text-dim">Select burned body regions above.</span>'; return; }
  const parkland4h = (4 * weight * tbsa).toFixed(0);
  const first8h = (parkland4h / 2).toFixed(0);
  const next16h = (parkland4h / 2).toFixed(0);
  let severity = tbsa < 10 ? 'Minor' : tbsa < 20 ? 'Moderate' : tbsa < 40 ? 'Major' : 'Critical/Life-Threatening';
  const burnToneClass = tbsa < 10 ? 'prep-summary-card-ok' : tbsa < 20 ? 'utility-summary-card-alert' : 'prep-summary-card-danger';
  el.innerHTML = `<div class="utility-summary-result utility-summary-grid">
    <div class="prep-summary-card utility-summary-card ${burnToneClass}">
      <div class="prep-summary-meta">Burn Area</div>
      <div class="prep-summary-value">${tbsa}%</div>
      <div class="prep-summary-label">total body surface area</div>
    </div>
    <div class="prep-summary-card utility-summary-card ${burnToneClass}">
      <div class="prep-summary-meta">Severity</div>
      <div class="prep-summary-value prep-summary-value-compact">${severity}</div>
      <div class="prep-summary-label">current classification</div>
    </div>
    <div class="prep-summary-card utility-summary-card prep-summary-card-wide">
      <div class="prep-summary-meta">Parkland Formula</div>
      <div class="prep-summary-value">${Number(parkland4h).toLocaleString()} mL</div>
      <div class="prep-summary-label">total 24h Lactated Ringer's</div>
      <div class="prep-summary-meta">First 8 hrs: ${Number(first8h).toLocaleString()} mL | Next 16 hrs: ${Number(next16h).toLocaleString()} mL</div>
    </div>
  </div>
  <div class="prep-reference-callout prep-reference-callout-warn">Parkland formula is a guideline. Adjust based on urine output (goal 0.5–1 mL/kg/hr). Seek medical care when possible.</div>`;
}

// --- IV Drip Rate ---
function calcIVDrip() {
  const volInput = document.getElementById('iv-vol');
  const timeInput = document.getElementById('iv-time');
  const dropsInput = document.getElementById('iv-drops');
  const el = document.getElementById('iv-result');
  if (!volInput || !timeInput || !dropsInput || !el) return;
  const vol = parseFloat(volInput.value) || 1000;
  const time = parseFloat(timeInput.value) || 60;
  const drops = parseInt(dropsInput.value) || 20;
  const dropsPerMin = (vol * drops / time).toFixed(1);
  const mlPerHr = (vol / (time / 60)).toFixed(1);
  el.innerHTML = `<div class="utility-summary-result utility-summary-grid">
    <div class="prep-summary-card utility-summary-card">
      <div class="prep-summary-meta">Drops / min</div>
      <div class="prep-summary-value">${dropsPerMin}</div>
      <div class="prep-summary-label">manual drip count</div>
    </div>
    <div class="prep-summary-card utility-summary-card">
      <div class="prep-summary-meta">mL / hour</div>
      <div class="prep-summary-value">${mlPerHr}</div>
      <div class="prep-summary-label">infusion rate</div>
    </div>
  </div>
  <div class="prep-reference-callout prep-reference-callout-info">Count drops in the drip chamber for 15 seconds and multiply by 4 to verify the rate.</div>`;
}

// --- KI Dosage ---
let _kiPersons = [{age:'adult', label:'Adult'}];
function addKIPerson() {
  _kiPersons.push({age:'adult', label:'Person ' + (_kiPersons.length + 1)});
  renderKIPersons();
}
function removeKIPerson(idx) {
  _kiPersons.splice(idx, 1);
  renderKIPersons();
}
function renderKIPersons() {
  const el = document.getElementById('ki-people-list');
  if (!el) return;
  if (!_kiPersons.length) { el.innerHTML = '<div class="empty-state">Add family members above to calculate dosing.</div>'; return; }
  el.innerHTML = _kiPersons.map((p, i) => `
    <div class="prep-calc-dynamic-row">
      <input type="text" value="${p.label}" data-input-action="update-ki-person" data-ki-index="${i}" data-ki-field="label" class="prep-calc-dynamic-input prep-calc-dynamic-input-label">
      <select data-change-action="update-ki-person" data-ki-index="${i}" data-ki-field="age" class="prep-calc-dynamic-select prep-calc-dynamic-select-flex">
        <option value="adult" ${p.age==='adult'?'selected':''}>Adult (≥18 yrs)</option>
        <option value="teen" ${p.age==='teen'?'selected':''}>Teen 12–18 yrs</option>
        <option value="child" ${p.age==='child'?'selected':''}>Child 3–12 yrs</option>
        <option value="toddler" ${p.age==='toddler'?'selected':''}>Toddler 1m–3 yrs</option>
        <option value="infant" ${p.age==='infant'?'selected':''}>Infant <1 mo</option>
        <option value="pregnant" ${p.age==='pregnant'?'selected':''}>Pregnant/Nursing</option>
      </select>
      ${_kiPersons.length > 1 ? `<button type="button" data-prep-action="remove-ki-person" data-ki-index="${i}" class="prep-calc-remove-btn" aria-label="Remove person">✕</button>` : ''}
    </div>`).join('');
  calcKIDosage();
}
function calcKIDosage() {
  const doses = {
    adult: {mg: 130, tab: '2 × 65mg tabs or 1 × 130mg tab'},
    teen: {mg: 65, tab: '1 × 65mg tab'},
    child: {mg: 65, tab: '½ × 130mg tab or 1 × 65mg tab'},
    toddler: {mg: 32, tab: '¼ × 130mg tab (~liquid form preferred)'},
    infant: {mg: 16, tab: '⅛ × 130mg tab (liquid form only)'},
    pregnant: {mg: 130, tab: '2 × 65mg tabs or 1 × 130mg tab'}
  };
  const el = document.getElementById('ki-result');
  if (!el) return;
  const rows = _kiPersons.map(p => {
    const d = doses[p.age] || doses.adult;
    return `<tr><td>${p.label}</td><td>${p.age.charAt(0).toUpperCase()+p.age.slice(1)}</td><td><strong>${d.mg} mg</strong></td><td>${d.tab}</td></tr>`;
  }).join('');
  el.innerHTML = `<div class="prep-table-wrap"><table class="prep-data-table prep-reference-table-compact prep-calc-table prep-calc-table-center">
    <thead><tr>
      <th>Person</th><th>Age Group</th><th>KI Dose</th><th>How to Take</th>
    </tr></thead><tbody>${rows}</tbody></table></div>
    <div class="prep-reference-callout prep-reference-callout-warn">KI only protects the thyroid from radioactive iodine. Take within 3–4 hrs of exposure. Take with food/water. Do NOT take if allergic to iodine. Repeat daily only on official instruction.</div>`;
}

// --- Dead Reckoning Navigator ---
function calcDeadReckoning() {
  const latInput = document.getElementById('dr-lat');
  const lonInput = document.getElementById('dr-lon');
  const bearingInput = document.getElementById('dr-bearing');
  const speedInput = document.getElementById('dr-speed');
  const hoursInput = document.getElementById('dr-hours');
  const el = document.getElementById('dr-result');
  if (!latInput || !lonInput || !el) return;
  const lat = parseFloat(latInput.value);
  const lon = parseFloat(lonInput.value);
  const bearing = parseFloat(bearingInput?.value) || 0;
  const speed = parseFloat(speedInput?.value) || 3;
  const hours = parseFloat(hoursInput?.value) || 1;
  if (isNaN(lat) || isNaN(lon)) { el.innerHTML = '<span class="text-dim">Enter start coordinates.</span>'; return; }
  const distMi = speed * hours;
  const distKm = distMi * 1.60934;
  const bearingRad = bearing * Math.PI / 180;
  const latRad = lat * Math.PI / 180;
  const deltaLat = distMi * Math.cos(bearingRad) / 69.0;
  const deltaLon = distMi * Math.sin(bearingRad) / (69.0 * Math.cos(latRad));
  const newLat = lat + deltaLat;
  const newLon = lon + deltaLon;
  const cardinals = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'];
  const card = cardinals[Math.round(bearing / 22.5) % 16];
  el.innerHTML = `<div class="utility-summary-result utility-summary-grid">
    <div class="prep-summary-card utility-summary-card">
      <div class="prep-summary-meta">Est. Latitude</div>
      <div class="prep-summary-value prep-summary-value-compact">${newLat.toFixed(4)}°</div>
      <div class="prep-summary-label">projected position</div>
    </div>
    <div class="prep-summary-card utility-summary-card">
      <div class="prep-summary-meta">Est. Longitude</div>
      <div class="prep-summary-value prep-summary-value-compact">${newLon.toFixed(4)}°</div>
      <div class="prep-summary-label">projected position</div>
    </div>
    <div class="prep-summary-card utility-summary-card">
      <div class="prep-summary-meta">Distance</div>
      <div class="prep-summary-value">${distMi.toFixed(1)} mi</div>
      <div class="prep-summary-label">${distKm.toFixed(1)} km traveled</div>
    </div>
    <div class="prep-summary-card utility-summary-card">
      <div class="prep-summary-meta">Direction</div>
      <div class="prep-summary-value prep-summary-value-compact">${bearing}° ${card}</div>
      <div class="prep-summary-label">direction of travel</div>
    </div>
  </div>
  <div class="prep-reference-callout prep-reference-callout-info">Estimated position: <strong>${newLat.toFixed(4)}, ${newLon.toFixed(4)}</strong>. Error accumulates over distance, so verify with landmarks or GPS when possible.</div>`;
}

// --- Shelter Protection Factor ---
let _shelterLayers = [];
function addShelterLayer() {
  _shelterLayers.push({material:'concrete', thickness:8});
  renderShelterLayers();
}
function removeShelterLayer(idx) {
  _shelterLayers.splice(idx, 1);
  renderShelterLayers();
}
// halving thicknesses in inches (approx for gamma radiation)
const _hvtData = {
  concrete: {hvt: 2.2, label: 'Concrete (in)'},
  earth: {hvt: 3.3, label: 'Earth/Soil (in)'},
  brick: {hvt: 2.8, label: 'Brick (in)'},
  steel: {hvt: 0.7, label: 'Steel (in)'},
  water: {hvt: 7.2, label: 'Water (in)'},
  wood: {hvt: 11.0, label: 'Wood (in)'},
  sandbags: {hvt: 3.5, label: 'Sand/Sandbags (in)'},
  lead: {hvt: 0.5, label: 'Lead (in)'}
};
function renderShelterLayers() {
  const el = document.getElementById('shpf-layers');
  if (!el) return;
  el.innerHTML = _shelterLayers.map((l, i) => `
    <div class="prep-calc-dynamic-row">
      <select data-change-action="update-shelter-layer" data-shelter-index="${i}" data-shelter-field="material" class="prep-calc-dynamic-select prep-calc-dynamic-select-flex">
        ${Object.entries(_hvtData).map(([k,v])=>`<option value="${k}" ${l.material===k?'selected':''}>${v.label}</option>`).join('')}
      </select>
      <input type="number" value="${l.thickness}" min="1" max="120" data-input-action="update-shelter-layer" data-shelter-index="${i}" data-shelter-field="thickness" class="prep-calc-dynamic-input prep-calc-dynamic-input-measure">
      <button type="button" data-prep-action="remove-shelter-layer" data-shelter-index="${i}" class="prep-calc-remove-btn" aria-label="Remove layer">✕</button>
    </div>`).join('') || '<div class="prep-calc-empty">Add layers above to calculate protection.</div>';
  calcShelterPF();
}
function calcShelterPF() {
  const el = document.getElementById('shpf-result');
  if (!el) return;
  if (_shelterLayers.length === 0) { el.innerHTML = '<span class="text-dim">Add material layers above.</span>'; return; }
  const geoSel = document.getElementById('shpf-geo');
  const geoMult = geoSel ? parseFloat(geoSel.value) : 1.0;
  // PF = product of (2^(thickness/HVT)) for each layer × geometry multiplier
  let pf = 1;
  for (const l of _shelterLayers) {
    const hvt = _hvtData[l.material]?.hvt || 3.3;
    pf *= Math.pow(2, l.thickness / hvt);
  }
  pf = Math.round(pf * geoMult);
  const outsideDose = 100; // reference cGy
  const insideDose = (outsideDose / pf).toFixed(2);
  let rating = pf < 10 ? 'Poor' : pf < 40 ? 'Fair' : pf < 100 ? 'Good' : pf < 1000 ? 'Excellent' : 'Exceptional';
  const shelterToneClass = pf < 10 ? 'prep-summary-card-danger' : pf < 40 ? 'utility-summary-card-alert' : 'prep-summary-card-ok';
  el.innerHTML = `<div class="utility-summary-result utility-summary-grid">
    <div class="prep-summary-card utility-summary-card ${shelterToneClass}">
      <div class="prep-summary-meta">Protection Factor</div>
      <div class="prep-summary-value">PF ${pf.toLocaleString()}</div>
      <div class="prep-summary-label">combined shielding</div>
    </div>
    <div class="prep-summary-card utility-summary-card ${shelterToneClass}">
      <div class="prep-summary-meta">Rating</div>
      <div class="prep-summary-value prep-summary-value-compact">${rating}</div>
      <div class="prep-summary-label">current assessment</div>
    </div>
    <div class="prep-summary-card utility-summary-card prep-summary-card-wide">
      <div class="prep-summary-meta">Inside Dose</div>
      <div class="prep-summary-value">${insideDose} cGy</div>
      <div class="prep-summary-label">for every 100 cGy outside</div>
    </div>
  </div>
  <div class="prep-reference-callout prep-reference-callout-info">FEMA target: PF ≥ 40. Basements of brick or concrete buildings typically achieve PF 10–40. Expedient fallout shelters with 3ft of earth can reach PF 1000+.</div>`;
}

// --- Survival Garden Calorie Planner ---
let _cropRows = [];
const _cropData = {
  potato: {name:'Potatoes', cal_per_sqft_yr: 1.5, notes:'High yield, store well'},
  sweetpotato: {name:'Sweet Potatoes', cal_per_sqft_yr: 1.4, notes:'Very nutritious, drought tolerant'},
  corn: {name:'Corn (field)', cal_per_sqft_yr: 0.5, notes:'Staple grain, needs space'},
  beans: {name:'Beans (dry)', cal_per_sqft_yr: 0.3, notes:'Protein + nitrogen fixer'},
  squash: {name:'Winter Squash', cal_per_sqft_yr: 0.35, notes:'Long storage life'},
  wheat: {name:'Wheat', cal_per_sqft_yr: 0.25, notes:'Needs grain mill'},
  kale: {name:'Kale/Greens', cal_per_sqft_yr: 0.15, notes:'Vitamins, year-round'},
  tomato: {name:'Tomatoes', cal_per_sqft_yr: 0.1, notes:'Vitamin C, versatile'},
  sunflower: {name:'Sunflowers (seed)', cal_per_sqft_yr: 0.4, notes:'Oil, protein, easy to store'},
  amaranth: {name:'Amaranth (grain)', cal_per_sqft_yr: 0.35, notes:'Complete protein grain'}
};
function addCropRow() {
  const keys = Object.keys(_cropData);
  _cropRows.push({crop: keys[_cropRows.length % keys.length], sqft: 100});
  renderCropRows();
}
function removeCropRow(idx) {
  _cropRows.splice(idx, 1);
  renderCropRows();
}
function renderCropRows() {
  const el = document.getElementById('crop-rows');
  if (!el) return;
  el.innerHTML = _cropRows.map((r, i) => `
    <div class="prep-calc-dynamic-row">
      <select data-change-action="update-crop-row" data-crop-index="${i}" data-crop-field="crop" class="prep-calc-dynamic-select prep-calc-dynamic-select-flex">
        ${Object.entries(_cropData).map(([k,v])=>`<option value="${k}" ${r.crop===k?'selected':''}>${v.name}</option>`).join('')}
      </select>
      <input type="number" value="${r.sqft}" min="1" max="100000" placeholder="sq ft…" data-input-action="update-crop-row" data-crop-index="${i}" data-crop-field="sqft" class="prep-calc-dynamic-input prep-calc-dynamic-input-wide">
      <span class="prep-calc-dynamic-note">${_cropData[r.crop]?.notes||''}</span>
      <button type="button" data-prep-action="remove-crop-row" data-crop-index="${i}" class="prep-calc-remove-btn" aria-label="Remove crop">✕</button>
    </div>`).join('') || '<div class="prep-calc-empty">Add crops above.</div>';
  calcCropCalories();
}
function calcCropCalories() {
  const el = document.getElementById('crop-result');
  if (!el) return;
  const people = parseInt(document.getElementById('crop-people').value) || 4;
  if (_cropRows.length === 0) { el.innerHTML = '<span class="text-dim">Add crop rows above.</span>'; return; }
  const calPerDayPerson = 2000;
  const calPerYearPerson = calPerDayPerson * 365;
  let totalCalYear = 0;
  const rows = _cropRows.map(r => {
    const cd = _cropData[r.crop] || {cal_per_sqft_yr: 0.3};
    const cal = Math.round(r.sqft * cd.cal_per_sqft_yr * 1000);
    totalCalYear += cal;
    return `<tr><td>${_cropData[r.crop]?.name||r.crop}</td><td>${r.sqft.toLocaleString()} ft²</td><td>${cal.toLocaleString()}</td><td>${Math.round(cal/calPerYearPerson*10)/10} person-yrs</td></tr>`;
  }).join('');
  const personYears = totalCalYear / calPerYearPerson;
  const pct = Math.round(personYears / people * 100);
  const cropToneClass = pct < 50 ? 'prep-summary-card-danger' : pct < 90 ? 'utility-summary-card-alert' : 'prep-summary-card-ok';
  el.innerHTML = `<div class="utility-summary-result utility-summary-grid">
    <div class="prep-summary-card utility-summary-card">
      <div class="prep-summary-meta">Total kcal/year</div>
      <div class="prep-summary-value">${Math.round(totalCalYear/1000).toLocaleString()}k</div>
      <div class="prep-summary-label">all planned crops</div>
    </div>
    <div class="prep-summary-card utility-summary-card ${cropToneClass}">
      <div class="prep-summary-meta">Coverage</div>
      <div class="prep-summary-value">${pct}%</div>
      <div class="prep-summary-label">of ${people}-person calorie need</div>
    </div>
  </div>
  <div class="prep-table-wrap"><table class="prep-data-table prep-reference-table-compact prep-calc-table prep-calc-table-center">
    <thead><tr><th>Crop</th><th>Area</th><th>kcal/yr</th><th>Person-yrs</th></tr></thead>
    <tbody>${rows}</tbody></table></div>
  <div class="prep-reference-callout prep-reference-callout-info">Estimates assume good soil, water, and weather. Diversify crops for nutrition balance because calories alone do not equal survival.</div>`;
}

// --- NVIS/HF Frequency Advisor ---
function calcNVIS() {
  const solar = document.getElementById('nvis-solar')?.value || 'moderate';
  const timeOfDay = document.getElementById('nvis-time')?.value || 'day';
  const rangeMi = parseFloat(document.getElementById('nvis-range')?.value) || 200;
  const el = document.getElementById('nvis-result');
  if (!el) return;
  // NVIS optimal frequency lookup table (MHz)
  // Based on typical MUF/FOT for NVIS (0-600 mile paths)
  const table = {
    high: { // Solar maximum
      night: {bands: ['80m (3.5–4 MHz)', '160m (1.8–2 MHz)'], mhz: '3.5–4.0', note: 'D-layer absent, 80m/160m best at night'},
      dawn:  {bands: ['40m (7–7.3 MHz)', '80m (3.5–4 MHz)'], mhz: '7.0–7.3', note: 'Transition — try 40m first'},
      day:   {bands: ['15m (21–21.45 MHz)', '20m (14–14.35 MHz)', '10m (28–29.7 MHz)'], mhz: '14–21', note: 'High solar flux pushes MUF up; 20/15m strong'},
      dusk:  {bands: ['40m (7–7.3 MHz)', '20m (14–14.35 MHz)'], mhz: '7–14', note: 'Transition — 40m/20m reliable'}
    },
    moderate: {
      night: {bands: ['80m (3.5–4 MHz)', '40m (7–7.3 MHz)'], mhz: '3.5–7.3', note: '80m primary; 40m works for >200mi'},
      dawn:  {bands: ['40m (7–7.3 MHz)', '60m (5.33 MHz)'], mhz: '5.3–7.3', note: '40m primary; 60m (US channelized) backup'},
      day:   {bands: ['40m (7–7.3 MHz)', '20m (14–14.35 MHz)'], mhz: '7–14', note: '40m NVIS reliable for 0–500mi daytime'},
      dusk:  {bands: ['80m (3.5–4 MHz)', '40m (7–7.3 MHz)'], mhz: '3.5–7.3', note: 'Back to 80m/40m as sun sets'}
    },
    low: { // Solar minimum
      night: {bands: ['160m (1.8–2 MHz)', '80m (3.5–4 MHz)'], mhz: '1.8–4.0', note: 'Low MUF — 160m if available, 80m reliable'},
      dawn:  {bands: ['80m (3.5–4 MHz)', '60m (5.33 MHz)'], mhz: '3.5–5.4', note: '80m primary at dawn'},
      day:   {bands: ['40m (7–7.3 MHz)', '80m (3.5–4 MHz)'], mhz: '3.5–7.3', note: 'Low solar flux limits daytime NVIS to 40m'},
      dusk:  {bands: ['80m (3.5–4 MHz)'], mhz: '3.5–4.0', note: '80m most reliable after sunset'}
    }
  };
  const rec = table[solar]?.[timeOfDay] || table.moderate.day;
  const longRange = rangeMi > 300;
  el.innerHTML = `<div class="utility-summary-result utility-summary-grid">
    <div class="prep-summary-card utility-summary-card prep-summary-card-wide">
      <div class="prep-summary-meta">Recommended Bands</div>
      <div class="prep-calc-band-list">${rec.bands.map(b=>`<div class="prep-calc-band-item">${b}</div>`).join('')}</div>
      <div class="prep-summary-label">${rec.note}</div>
    </div>
    <div class="prep-summary-card utility-summary-card">
      <div class="prep-summary-meta">Frequency Range</div>
      <div class="prep-summary-value prep-summary-value-compact">${rec.mhz} MHz</div>
      <div class="prep-summary-label">best starting window</div>
    </div>
  </div>
  ${longRange ? `<div class="prep-reference-callout prep-reference-callout-warn">Range &gt;300 mi: NVIS alone may not cover the path. Consider combining with ground-wave or skip propagation. Higher bands (20m/15m) provide broader coverage at the expense of shorter ranges.</div>` : ''}
  <div class="prep-reference-callout prep-reference-callout-info">NVIS (Near Vertical Incidence Skywave) is best for 0–300 mile regional comms. Use a horizontal dipole at 0.1–0.25 wavelength height for the best overhead angle.</div>`;
}

// --- Weight-Based Medication Dosing ---
function calcWeightDose() {
  const weightRaw = parseFloat(document.getElementById('dose-weight')?.value) || 20;
  const unit = document.getElementById('dose-unit')?.value || 'kg';
  const med = document.getElementById('dose-med')?.value || 'amoxicillin';
  const el = document.getElementById('dose-result');
  if (!el) return;
  const weightKg = unit === 'lb' ? weightRaw * 0.453592 : weightRaw;
  // [dose mg/kg, min mg, max mg, frequency, route, notes]
  const meds = {
    amoxicillin: {name:'Amoxicillin', dose_per_kg: 25, min: 250, max: 500, freq: 'Every 8 hours', route: 'PO', notes:'Broad spectrum antibiotic. Standard for respiratory, ear, skin infections.'},
    amoxiclav: {name:'Amoxicillin-Clavulanate', dose_per_kg: 25, min: 250, max: 875, freq: 'Every 12 hours', route: 'PO', notes:'Add for resistant organisms or animal bites.'},
    azithromycin: {name:'Azithromycin (Z-Pak)', dose_per_kg: 10, min: 250, max: 500, freq: 'Once daily × 5 days', route: 'PO', notes:'Day 1: loading dose ×2. Useful for atypicals.'},
    ciprofloxacin: {name:'Ciprofloxacin', dose_per_kg: 10, min: 250, max: 500, freq: 'Every 12 hours', route: 'PO', notes:'UTI, GI infections. Avoid in children <18 (except anthrax/plague).'},
    doxycycline: {name:'Doxycycline', dose_per_kg: 2.2, min: 100, max: 200, freq: 'Every 12 hours', route: 'PO', notes:'Avoid <8 yrs (stains teeth). Malaria prophylaxis, Lyme, respiratory.'},
    ibuprofen: {name:'Ibuprofen', dose_per_kg: 10, min: 200, max: 800, freq: 'Every 6–8 hours', route: 'PO', notes:'Anti-inflammatory, antipyretic, analgesic. Take with food.'},
    acetaminophen: {name:'Acetaminophen (Tylenol)', dose_per_kg: 15, min: 325, max: 1000, freq: 'Every 4–6 hours', route: 'PO', notes:'Max 4g/day adult, 75 mg/kg/day children. Safe with food or empty stomach.'},
    diphenhydramine: {name:'Diphenhydramine (Benadryl)', dose_per_kg: 1.25, min: 25, max: 50, freq: 'Every 4–6 hours', route: 'PO/IM', notes:'Antihistamine, mild sedation. Mild allergic reactions.'},
    epinephrine: {name:'Epinephrine (Anaphylaxis)', dose_per_kg: 0.01, min: 0.15, max: 0.5, freq: 'May repeat in 5–15 min', route: 'IM (thigh)', notes:'⚠ ANAPHYLAXIS ONLY. 0.3mg for adults, 0.15mg for <30kg. EpiPen Jr = 0.15mg, EpiPen = 0.3mg. Seek emergency care immediately.'},
    metronidazole: {name:'Metronidazole (Flagyl)', dose_per_kg: 7.5, min: 250, max: 500, freq: 'Every 8 hours', route: 'PO', notes:'Anaerobic infections, C. diff, giardia, abscess. Avoid alcohol.'}
  };
  const m = meds[med] || meds.amoxicillin;
  let calcDose = Math.round(weightKg * m.dose_per_kg);
  const clampedDose = Math.max(m.min, Math.min(m.max, calcDose));
  const wasClamped = calcDose !== clampedDose;
  const doseToneClass = med === 'epinephrine' ? 'prep-summary-card-danger' : '';
  el.innerHTML = `<div class="utility-summary-result utility-summary-grid">
    <div class="prep-summary-card utility-summary-card ${doseToneClass}">
      <div class="prep-summary-meta">Single Dose</div>
      <div class="prep-summary-value">${clampedDose} mg</div>
      <div class="prep-summary-label">${m.name}</div>
    </div>
    <div class="prep-summary-card utility-summary-card">
      <div class="prep-summary-meta">Frequency / Route</div>
      <div class="prep-summary-value prep-summary-value-compact">${m.freq}</div>
      <div class="prep-summary-label">${m.route}</div>
    </div>
  </div>
  ${wasClamped ? `<div class="prep-reference-callout prep-reference-callout-warn">Dose clamped to ${calcDose>m.max?'maximum':'minimum'} (calculated ${calcDose}mg → using ${clampedDose}mg).</div>` : ''}
  <div class="prep-reference-callout prep-reference-callout-info">${m.notes}</div>
  <div class="prep-reference-callout prep-reference-callout-warn">These are reference guidelines only. Drug allergies, renal or hepatic function, interactions, and contraindications must be considered. This is not medical advice.</div>`;
}

// Initialize calculators on first load
// ═══════════════════════════════════════════════════════════════
// HYPOTHERMIA ASSESSMENT
// ═══════════════════════════════════════════════════════════════
function calcHypothermia() {
  const tempInput = document.getElementById('hypo-temp');
  const windInput = document.getElementById('hypo-wind');
  const hoursInput = document.getElementById('hypo-hours');
  const wetInput = document.getElementById('hypo-wet');
  const el = document.getElementById('hypo-result');
  if (!tempInput || !windInput || !hoursInput || !wetInput || !el) return;
  const temp = parseFloat(tempInput.value) || 32;
  const wind = parseFloat(windInput.value) || 10;
  const hours = parseFloat(hoursInput.value) || 1;
  const wetFactor = parseFloat(wetInput.value) || 1;

  // NOAA wind chill (valid T<=50°F, wind>=3 mph)
  let windChill = temp;
  if (temp <= 50 && wind >= 3) {
    windChill = 35.74 + 0.6215*temp - 35.75*Math.pow(wind,0.16) + 0.4275*temp*Math.pow(wind,0.16);
    windChill = Math.round(windChill * 10) / 10;
  }

  // Estimate heat loss — baseline ~1.5°F/hr drop at 32°F still dry, scaled by conditions
  const baseLossRate = Math.max(0, (98.6 - windChill) / 80);
  const lossRate = baseLossRate * wetFactor;
  const coreDropF = lossRate * hours;
  const estimatedCoreF = 98.6 - coreDropF;
  const estimatedCoreC = (estimatedCoreF - 32) * 5 / 9;

  let stage, stageColor, treatment;
  if (estimatedCoreC >= 35) {
    stage = 'Normal / Pre-hypothermic risk';
    stageColor = getThemeCssVar('--green', '#4caf50');
    treatment = 'Preventive: add insulation, seek shelter, consume warm high-calorie food/drinks. Remove wet clothing now. Monitor closely.';
  } else if (estimatedCoreC >= 32) {
    stage = 'MILD Hypothermia (32–35°C)';
    stageColor = getThemeCssVar('--warning', '#ff9800');
    treatment = '1. Move to shelter — stop further heat loss\n2. Remove ALL wet clothing\n3. Insulate from ground; wrap in dry blankets/sleeping bag\n4. Warm sweet drinks if conscious and swallowing normally\n5. Chemical heat packs to armpits, groin, neck (never directly on skin)\n6. Do NOT massage extremities — drives cold blood to core\n7. Monitor — shivering stopping is a danger sign';
  } else if (estimatedCoreC >= 28) {
    stage = 'MODERATE Hypothermia (28–32°C)';
    stageColor = getThemeCssVar('--red', '#f44336');
    treatment = '1. Handle GENTLY — cardiac arrest risk from any jostling\n2. Keep horizontal — do NOT allow to walk\n3. Carefully remove wet clothing\n4. Passive rewarming (wrap fully, insulate from ground)\n5. Warm humidified O2 if available\n6. Monitor pulse carefully — may be very slow\n7. Begin CPR only if confirmed pulseless\n8. EVACUATE as highest priority';
  } else {
    stage = 'SEVERE Hypothermia (<28°C) — LIFE THREATENING';
    stageColor = getThemeCssVar('--red', '#b71c1c');
    treatment = '"Not dead until warm and dead."\n1. Absolute minimal movement — any handling may cause cardiac arrest\n2. CPR if pulseless — may need 60+ continuous minutes\n3. Do NOT give oral fluids — aspiration risk\n4. Full insulation in place\n5. Hospital with ECMO/bypass is only definitive treatment\n6. EVACUATE immediately';
  }

  let frostbite = '';
  if (windChill <= 19) frostbite = 'Frostbite possible in 30 min';
  if (windChill <= 9) frostbite = 'Frostbite risk within 10 min';
  if (windChill <= -19) frostbite = 'Frostbite risk within 5 min';
  if (windChill <= -39) frostbite = '⚠ Frostbite in under 2 min';

  el.innerHTML = `<div class="prep-calc-result-block">
    <div class="prep-calc-result-line"><strong>Wind chill:</strong> ${windChill}°F (${((windChill-32)*5/9).toFixed(1)}°C)</div>
    <div class="prep-calc-result-line"><strong>Estimated core after ${hours}h:</strong> ~${estimatedCoreF.toFixed(1)}°F (~${estimatedCoreC.toFixed(1)}°C)</div>
    <div class="prep-calc-result-stage" style="--prep-stage-tone:${stageColor};">${stage}</div>
    ${frostbite ? `<div class="prep-calc-result-alert">${frostbite}</div>` : ''}
    <div class="prep-calc-result-treatment">${treatment}</div>
    <div class="prep-calc-result-footnote">Estimate based on wind chill and exposure model. Actual core temp requires thermometer. Always err on side of caution.</div>
  </div>`;
}

// ═══════════════════════════════════════════════════════════════
// ORAL REHYDRATION THERAPY
// ═══════════════════════════════════════════════════════════════
function calcORT() {
  const unitInput = document.getElementById('ort-unit');
  const weightInput = document.getElementById('ort-weight');
  const severityInput = document.getElementById('ort-sev');
  const el = document.getElementById('ort-result');
  if (!unitInput || !weightInput || !severityInput || !el) return;
  const unit = unitInput.value;
  let weight = parseFloat(weightInput.value) || 70;
  if (unit === 'lb') weight = weight / 2.205;
  const sev = severityInput.value;

  const mLperKg = {mild: 50, moderate: 75, severe: 100};
  const replacement = weight * mLperKg[sev];
  const hourlyTarget = Math.round(replacement / 4);
  const liters = (replacement / 1000).toFixed(2);
  const sugarTsp = Math.round(replacement / 1000 * 6 * 10) / 10;
  const saltTsp = Math.round(replacement / 1000 * 0.5 * 10) / 10;

  const sevLabel = {mild:'Mild', moderate:'Moderate', severe:'Severe'}[sev];
  const sevColor = {mild:getThemeCssVar('--green', '#4caf50'), moderate:getThemeCssVar('--warning', '#ff9800'), severe:getThemeCssVar('--red', '#f44336')}[sev];
  const sevNote = sev === 'severe'
    ? `<div class="prep-reference-callout prep-reference-callout-danger prep-calc-inline-callout">⚠ Severe: IV fluids preferred when available. ORT is second-line. If altered consciousness, unable to swallow safely, or continuous vomiting — IV or nasogastric tube required.</div>`
    : '';

  el.innerHTML = `<div class="prep-calc-result-block">
    ${sevNote}
    <div class="prep-calc-result-stage" style="--prep-stage-tone:${sevColor};">${sevLabel} dehydration</div>
    <div class="prep-calc-result-line"><strong>Replace ${Math.round(replacement)} mL over 4 hours</strong> (${hourlyTarget} mL/hr)</div>
    <div class="prep-calc-result-kicker">WHO ORS Recipe (per ${liters}L batch):</div>
    <div class="prep-calc-bullet">• ${liters}L clean boiled/filtered water</div>
    <div class="prep-calc-bullet">• ${sugarTsp} tsp sugar (${(sugarTsp*4).toFixed(0)}g)</div>
    <div class="prep-calc-bullet prep-calc-bullet-last">• ${saltTsp} tsp table salt (${(saltTsp*5.7).toFixed(1)}g NaCl)</div>
    <div class="prep-result-note-text">Give small sips frequently. Children: 5 mL every 1–2 min. If vomiting, pause 10 min then resume. After 4h: reassess — if improved, switch to maintenance (100–150 mL/kg/day). Improvement signs: urination resumes, tears return, skin pinch test normalizes.</div>
  </div>`;
}

// ═══════════════════════════════════════════════════════════════
// ANTIBIOTIC INVENTORY PLANNER
// ═══════════════════════════════════════════════════════════════
function calcAbxInventory() {
  const drugInput = document.getElementById('abx-drug');
  const qtyInput = document.getElementById('abx-qty');
  const peopleInput = document.getElementById('abx-people');
  const el = document.getElementById('abx-result');
  if (!drugInput || !qtyInput || !peopleInput || !el) return;
  const drug = drugInput.value;
  const qty = parseInt(qtyInput.value) || 0;
  const people = parseInt(peopleInput.value) || 1;

  const drugs = {
    amox500:      {name:'Amoxicillin 500mg',        tabs:21, days:7,  freq:'TID (3×/day)', dose:'500mg',        indications:'Respiratory, ear/sinus, skin, dental, UTI (uncomplicated)'},
    amox250:      {name:'Amoxicillin 250mg',        tabs:42, days:7,  freq:'TID (3×/day)', dose:'250mg (2 tabs→500mg)', indications:'Respiratory, ear/sinus, skin (lower strength)'},
    doxy100:      {name:'Doxycycline 100mg',        tabs:14, days:7,  freq:'BID (2×/day)', dose:'100mg',        indications:'Respiratory, skin, tick-borne illness (Lyme/RMSF), anthrax (60-day course needed)'},
    cipro500:     {name:'Ciprofloxacin 500mg',      tabs:14, days:7,  freq:'BID (2×/day)', dose:'500mg',        indications:'UTI (3-day short course), GI/traveler\'s diarrhea, anthrax post-exposure'},
    metro500:     {name:'Metronidazole 500mg',      tabs:21, days:7,  freq:'TID (3×/day)', dose:'500mg',        indications:'Anaerobic infections, GI (C.diff, Giardia), dental abscess, BV'},
    azithro250:   {name:'Azithromycin 250mg',       tabs:7,  days:5,  freq:'QD (1×/day)',  dose:'500mg day 1, 250mg days 2–5', indications:'Respiratory, atypical pneumonia, STDs, skin/soft tissue'},
    azithro500:   {name:'Azithromycin 500mg',       tabs:5,  days:5,  freq:'QD (1×/day)',  dose:'500mg/day',   indications:'Community-acquired pneumonia, respiratory infections'},
    trimeth:      {name:'TMP/SMX DS 800/160mg',    tabs:14, days:7,  freq:'BID (2×/day)', dose:'1 DS tab',     indications:'UTI, MRSA skin infections, respiratory (PCP prophylaxis)'},
    cephalex500:  {name:'Cephalexin 500mg',         tabs:28, days:7,  freq:'QID (4×/day)', dose:'500mg',        indications:'Skin/soft tissue, respiratory, UTI, bone/joint'},
    augmentin875: {name:'Amox-Clavulanate 875mg',  tabs:14, days:7,  freq:'BID (2×/day)', dose:'875mg',        indications:'Animal bites, dental, skin (beta-lactamase organisms), respiratory'},
  };

  const d = drugs[drug];
  const totalCourses = qty / d.tabs;
  const coursesPerPerson = Math.floor(totalCourses / people * 10) / 10;
  const daysSupply = Math.floor(qty / (d.tabs / d.days) / people);

  const coursesColor = totalCourses >= people * 2 ? getThemeCssVar('--green', '#4caf50') : totalCourses >= people ? getThemeCssVar('--warning', '#ff9800') : getThemeCssVar('--red', '#f44336');
  const coursesNote = totalCourses >= people * 2 ? 'Good stockpile' : totalCourses >= people ? 'Minimal — 1 course per person' : 'Insufficient — partial course only';

  el.innerHTML = `<div class="prep-calc-result-block">
    <div class="prep-calc-result-head">${d.name}</div>
    <div class="prep-calc-result-line"><strong>Dose:</strong> ${d.dose} ${d.freq} × ${d.days} days = ${d.tabs} tabs/course</div>
    <div class="prep-calc-result-line"><strong>Total courses from ${qty} tabs:</strong> ${totalCourses.toFixed(1)}</div>
    <div class="prep-calc-result-stage" style="--prep-stage-tone:${coursesColor};">For ${people} person${people>1?'s':''}: ${coursesPerPerson} courses each — ${coursesNote}</div>
    <div class="prep-calc-result-line prep-calc-result-line-tight"><strong>Days of supply (${people} person${people>1?'s':''}):</strong> ${daysSupply} days</div>
    <div class="prep-result-note-text"><strong>Indicated for:</strong> ${d.indications}</div>
    <div class="prep-calc-result-footnote">Standard adult dosing. Adjust for weight (&lt;40kg), age, renal function, and drug interactions. Always complete the full course — partial courses promote resistance.</div>
  </div>`;
}

// ═══════════════════════════════════════════════════════════════
// MEDICAL SUPPLY STATUS
// ═══════════════════════════════════════════════════════════════
async function loadMedicalSupplies() {
  const el = document.getElementById('med-supplies-status');
  if (!el) return;
  el.innerHTML = prepEmptyBlock('Loading medical supplies...');
  try {
    const data = await safeFetch('/api/inventory?category=Medical', {}, null);
    if (!data) throw new Error('Failed to load');
    const items = Array.isArray(data?.items) ? data.items : (Array.isArray(data) ? data : []);
    if (!items.length) {
      el.innerHTML = prepEmptyBlock('No medical supplies in inventory. Add items under Preparedness → Inventory.');
      return;
    }
    const now = new Date();
    const soon = new Date(now); soon.setDate(soon.getDate() + 90);
    const buckets = { expired: [], expiring_soon: [], low_stock: [], ok: [], no_date: [] };
    for (const item of items) {
      const qty = parseFloat(item.quantity) || 0;
      const minQty = parseFloat(item.min_quantity) || 0;
      if (item.expiration) {
        const exp = new Date(item.expiration);
        if (exp < now) { buckets.expired.push(item); continue; }
        if (exp < soon) { buckets.expiring_soon.push(item); continue; }
      }
      if (minQty > 0 && qty <= minQty) { buckets.low_stock.push(item); continue; }
      if (!item.expiration) { buckets.no_date.push(item); continue; }
      buckets.ok.push(item);
    }
    const renderBucket = (label, color, icon, list) => {
      if (!list.length) return '';
      const rows = list.map(i => {
        const expStr = i.expiration ? ` — exp ${i.expiration}` : '';
        const qtyStr = i.quantity ? ` (${i.quantity}${i.unit ? ' '+i.unit : ''})` : '';
        return `<div class="prep-med-supply-item">${escapeHtml(i.name)}${qtyStr}${expStr}</div>`;
      }).join('');
      return `<div class="prep-med-supply-card" style="--prep-med-tone:${color};">
        <div class="prep-med-supply-title">${icon} ${label} (${list.length})</div>
        ${rows}
      </div>`;
    };
    const html = [
      renderBucket('Expired', '#ef4444', '✗', buckets.expired),
      renderBucket('Expiring Soon (<90d)', '#f59e0b', '⚠', buckets.expiring_soon),
      renderBucket('Low Stock', '#3b82f6', '↓', buckets.low_stock),
      renderBucket('OK', '#22c55e', '✓', buckets.ok),
      renderBucket('No Expiry Date', 'var(--text-dim)', '—', buckets.no_date),
    ].join('');
    el.innerHTML = html || prepEmptyBlock('No medical items found.');
  } catch (e) {
    el.innerHTML = `<div class="prep-error-state prep-empty-block">Error loading supplies: ${escapeHtml(e.message)}</div>`;
  }
}

// ═══════════════════════════════════════════════════════════════
// TCCC MARCH INTERACTIVE FLOWCHART
// ═══════════════════════════════════════════════════════════════
const TCCC_STEPS = [
  {id:'M',title:'M — Massive Hemorrhage',question:'Is there life-threatening bleeding?',
   yes:{action:'Apply tourniquet HIGH and TIGHT. Note time. Pack wound with hemostatic gauze if junctional.',next:1},
   no:{action:'No massive hemorrhage. Proceed to Airway.',next:1}},
  {id:'A',title:'A — Airway',question:'Is the airway clear? Can the casualty speak/breathe?',
   yes:{action:'Airway clear. Maintain position of comfort. Proceed to Respiration.',next:2},
   no:{action:'Perform head-tilt chin-lift or jaw thrust. Insert NPA if unconscious. Recovery position if unresponsive.',next:2}},
  {id:'R',title:'R — Respiration',question:'Is breathing adequate? Check chest rise, listen for air entry.',
   yes:{action:'Respiration adequate. Proceed to Circulation.',next:3},
   no:{action:'Check for tension pneumothorax (absent breath sounds, JVD, tracheal deviation). Needle decompress if present. Apply chest seal for open wounds.',next:3}},
  {id:'C',title:'C — Circulation',question:'Signs of shock? (Altered mental status, weak pulse, pale/cool skin)',
   yes:{action:'Establish IV/IO access. Administer TXA 1g IV. Warm fluids if available. Elevate legs. Keep warm.',next:4},
   no:{action:'No signs of shock. Continue monitoring. Proceed to Hypothermia prevention.',next:4}},
  {id:'H',title:'H — Hypothermia / Head Injury',question:'Exposure risk or head injury present?',
   yes:{action:'Wrap in blanket/sleeping bag. Prevent further heat loss. For head injury: maintain C-spine, monitor GCS, elevate head 30°.',next:5},
   no:{action:'Keep casualty warm regardless. Prevent ground contact.',next:5}},
  {id:'done',title:'Assessment Complete',question:'MARCH assessment complete. Document all findings and interventions. Prepare for evacuation.',
   yes:null,no:null}
];
let _tcccIdx = 0;

function startTCCCFlow() {
  _tcccIdx = 0;
  document.getElementById('tccc-flow').hidden = false;
  renderTCCCQuizStep();
}

function renderTCCCQuizStep() {
  const step = TCCC_STEPS[_tcccIdx];
  const el = document.getElementById('tccc-step');
  const prevBtn = document.getElementById('tccc-prev-btn');
  if (prevBtn) prevBtn.hidden = !(_tcccIdx > 0);

  if (step.id === 'done') {
    el.innerHTML = '<div class="prep-tccc-complete-icon">&#10003;</div><div class="prep-tccc-complete-title">' + escapeHtml(step.title) + '</div><div class="prep-reference-note prep-reference-note-tight">' + escapeHtml(step.question) + '</div>';
    return;
  }

  const letterColor = {M:'var(--red)',A:'var(--orange)',R:'var(--accent)',C:'#9c27b0',H:'var(--green)'}[step.id] || 'var(--accent)';
  el.innerHTML = `
    <div class="prep-tccc-header" style="--prep-tccc-tone:${letterColor};">
      <div class="prep-tccc-header-copy">
        <div class="prep-tccc-step-badge">${step.id}</div>
        <div>
          <div class="prep-tccc-step-title">${escapeHtml(step.title)}</div>
          <div class="prep-tccc-meta">Step ${_tcccIdx + 1} of 5</div>
        </div>
      </div>
    </div>
    <div class="prep-tccc-body">
      <div class="prep-tccc-action-copy">${escapeHtml(step.question)}</div>
      <div class="prep-tccc-footer prep-tccc-footer-center">
        <button type="button" class="btn btn-primary prep-tccc-action-btn" data-prep-action="tccc-quiz-answer" data-tccc-answer="yes">YES</button>
        <button type="button" class="btn prep-tccc-action-btn" data-prep-action="tccc-quiz-answer" data-tccc-answer="no">NO</button>
      </div>
      <div id="tccc-action" class="prep-reference-callout prep-reference-callout-info" hidden></div>
    </div>`;
}

function tcccAnswer(isYes) {
  const step = TCCC_STEPS[_tcccIdx];
  const result = isYes ? step.yes : step.no;
  if (!result) return;
  const actionEl = document.getElementById('tccc-action');
  actionEl.hidden = false;
  actionEl.innerHTML = '<strong>Action:</strong> ' + result.action + '<div class="prep-tccc-footer prep-tccc-footer-center"><button type="button" class="btn btn-sm btn-primary prep-tccc-action-btn" data-prep-action="tccc-quiz-next" data-tccc-next="' + result.next + '">Continue &#8594;</button></div>';
}

function tcccNext(nextIdx) {
  _tcccIdx = nextIdx;
  renderTCCCQuizStep();
  document.getElementById('tccc-step').scrollIntoView({behavior:'smooth',block:'center'});
}

function tcccPrev() {
  if (_tcccIdx > 0) { _tcccIdx--; renderTCCCQuizStep(); }
}

function tcccReset() {
  _tcccIdx = 0;
  document.getElementById('tccc-flow').hidden = true;
}

// ═══════════════════════════════════════════════════════════════
// RADIATION DOSE ACCUMULATOR
// ═══════════════════════════════════════════════════════════════
function calcRadDose() {
  const rateInput = document.getElementById('rad-rate');
  const unitInput = document.getElementById('rad-unit');
  const hoursInput = document.getElementById('rad-hours');
  const pfInput = document.getElementById('rad-pf');
  const el = document.getElementById('rad-result');
  if (!rateInput || !unitInput || !hoursInput || !pfInput || !el) return;
  const rate = parseFloat(rateInput.value) || 0;
  const unit = unitInput.value;
  const hours = parseFloat(hoursInput.value) || 0;
  const pf = parseFloat(pfInput.value) || 1;
  if (rate <= 0 || hours <= 0) { el.innerHTML = ''; return; }

  // Normalize to mSv/hr
  let rateMSv;
  if (unit === 'mR') rateMSv = rate * 0.01; // 1 mR ≈ 0.01 mSv
  else if (unit === 'uSv') rateMSv = rate / 1000;
  else rateMSv = rate; // already mSv

  const effectiveRate = rateMSv / pf;
  const totalMSv = effectiveRate * hours;
  const totalMR = unit === 'mR' ? (rate / pf) * hours : totalMSv * 100;

  // FEMA/FDA dose thresholds (mSv)
  let riskLevel, riskColor, riskText;
  if (totalMSv < 50) { riskLevel = 'Low Risk'; riskColor = '#22c55e'; riskText = 'Below threshold for acute effects. Minimize further exposure.'; }
  else if (totalMSv < 100) { riskLevel = 'Moderate Risk'; riskColor = '#f59e0b'; riskText = 'Possible mild symptoms (nausea). Evacuate if possible.'; }
  else if (totalMSv < 1000) { riskLevel = 'High Risk (ARS possible)'; riskColor = '#ef4444'; riskText = 'Acute Radiation Syndrome likely. Medical care required. Nausea, vomiting begin at ~1000 mSv.'; }
  else { riskLevel = 'Extreme — Potentially Fatal'; riskColor = '#dc2626'; riskText = '>1 Sv — Severe ARS. Fatality risk increases significantly above 3 Sv without treatment.'; }

  // Time to KI pill threshold (10 mSv thyroid dose)
  const safeHours = totalMSv > 0 ? (10 / rateMSv * pf).toFixed(1) : '—';

  const riskClass = totalMSv < 50 ? 'prep-reference-callout-safe' : totalMSv < 100 ? 'prep-reference-callout-warn' : 'prep-reference-callout-danger';

  el.innerHTML = `<div class="prep-reference-callout ${riskClass}">
    <div class="prep-summary-meta">${riskLevel}</div>
    <div class="prep-summary-label">Accumulated dose: <strong>${totalMSv.toFixed(2)} mSv</strong> (${totalMR.toFixed(1)} mR) — effective rate with PF: ${effectiveRate.toFixed(3)} mSv/hr</div>
    <div class="settings-summary-note">${riskText}</div>
    <div class="prep-reference-note prep-reference-note-tight">Without shelter (PF 1×): ${(rateMSv * hours).toFixed(2)} mSv · Safe duration at this rate &amp; shelter: ${safeHours} hrs before 10 mSv</div>
  </div>`;
}

// ═══════════════════════════════════════════════════════════════
// WATER NEEDS CALCULATOR
// ═══════════════════════════════════════════════════════════════
function calcWaterNeeds() {
  const adultsInput = document.getElementById('wn-adults');
  const childrenInput = document.getElementById('wn-children');
  const activityInput = document.getElementById('wn-activity');
  const climateInput = document.getElementById('wn-climate');
  const daysInput = document.getElementById('wn-days');
  const el = document.getElementById('wn-result');
  if (!adultsInput || !childrenInput || !activityInput || !climateInput || !daysInput || !el) return;
  const adults = parseInt(adultsInput.value) || 0;
  const children = parseInt(childrenInput.value) || 0;
  const activity = parseFloat(activityInput.value) || 1;
  const climate = parseFloat(climateInput.value) || 1;
  const days = parseInt(daysInput.value) || 1;

  // Base: 2L/day adult drinking, 0.5L sanitation, 1L cooking. Children = 60% of adult.
  const adultDailyL = (2 + 0.5 + 1) * activity * climate;
  const childDailyL = adultDailyL * 0.6;
  const totalDailyL = (adults * adultDailyL) + (children * childDailyL);
  const totalL = totalDailyL * days;
  const totalGal = totalL / 3.785;

  // Containers needed (55-gal drum, 7-gal aquatainer, 1-gal jugs)
  const drums55 = Math.ceil(totalGal / 55);
  const jugs7 = Math.ceil(totalGal / 7);

  el.innerHTML = `<div class="utility-summary-result utility-summary-grid">
    <div class="prep-summary-card utility-summary-card">
      <div class="prep-summary-meta">Daily Need</div>
      <div class="prep-summary-value prep-summary-value-compact">${totalDailyL.toFixed(1)} L/day</div>
      <div class="prep-summary-label">${(totalDailyL/3.785).toFixed(1)} gal/day</div>
    </div>
    <div class="prep-summary-card utility-summary-card">
      <div class="prep-summary-meta">Total Required</div>
      <div class="prep-summary-value prep-summary-value-compact">${totalL.toFixed(0)} L</div>
      <div class="prep-summary-label">${totalGal.toFixed(0)} gallons</div>
    </div>
    <div class="prep-summary-card utility-summary-card">
      <div class="prep-summary-meta">Storage</div>
      <div class="prep-summary-value prep-summary-value-compact">${drums55} x 55-gal</div>
      <div class="prep-summary-label">${jugs7} x 7-gal or ${Math.ceil(totalGal)} x 1-gal jugs</div>
    </div>
  </div>
  <div class="prep-reference-note prep-reference-note-tight">Breakdown: adult ${adultDailyL.toFixed(1)} L/day · child ${childDailyL.toFixed(1)} L/day · Includes drinking (2L) + cooking (1L) + minimal sanitation (0.5L)</div>
  <div class="settings-summary-note">Add 15–20% margin for spillage, purification loss, and medical needs. Do NOT use stored water for bathing.</div>`;
}

// ═══════════════════════════════════════════════════════════════
// GENERATOR RUNTIME CALCULATOR
// ═══════════════════════════════════════════════════════════════
function calcGenerator() {
  const wattsInput = document.getElementById('gen-watts');
  const loadInput = document.getElementById('gen2-load');
  const fuelTypeInput = document.getElementById('gen2-fuel');
  const fuelQtyInput = document.getElementById('gen2-fuel-qty');
  const unitEl = document.getElementById('gen2-fuel-unit');
  const el = document.getElementById('gen2-result');
  if (!wattsInput || !loadInput || !fuelTypeInput || !fuelQtyInput || !el) return;
  const watts = parseFloat(wattsInput.value) || 0;
  const loadPct = parseFloat(loadInput.value) || 50;
  const fuelType = fuelTypeInput.value;
  const fuelQty = parseFloat(fuelQtyInput.value) || 0;

  // Fuel consumption rates at 100% load (gal/hr per 1000W) — typical values
  const fuelData = {
    gasoline:    { rate: 0.12, unit: 'gallons', unitShort: 'gal', perUnit: 1 },
    diesel:      { rate: 0.08, unit: 'gallons', unitShort: 'gal', perUnit: 1 },
    propane:     { rate: 1.4,  unit: 'lbs',     unitShort: 'lbs', perUnit: 1 },  // lbs/hr per 1000W
    natural_gas: { rate: 1.09, unit: 'CCF',     unitShort: 'CCF', perUnit: 100 }, // therms equiv
  };
  const fd = fuelData[fuelType];
  if (unitEl) unitEl.textContent = fd.unit;

  if (!watts || !fuelQty) { el.innerHTML = ''; return; }

  const actualLoad = watts * (loadPct / 100);
  const consumptionPerHr = (actualLoad / 1000) * fd.rate;
  const runtimeHrs = fuelQty / consumptionPerHr;
  const runtimeDays = runtimeHrs / 24;
  const runtimeDaysFormatted = runtimeDays < 1 ? `${runtimeHrs.toFixed(1)} hours` : `${runtimeDays.toFixed(1)} days (${runtimeHrs.toFixed(0)} hrs)`;

  // Daily fuel needed for 24/7 run
  const dailyFuel = consumptionPerHr * 24;
  // 8-hr/day operation
  const daily8hrFuel = consumptionPerHr * 8;

  el.innerHTML = `<div class="prep-calc-result-shell" style="--prep-result-tone:var(--warning);">
    <div class="prep-calc-result-head prep-calc-result-head-toned">Generator Runtime Estimate</div>
    <div class="prep-calc-result-line">Running load: <strong>${actualLoad.toFixed(0)}W</strong> (${loadPct}% of ${watts}W)</div>
    <div class="prep-calc-result-line">Fuel burn rate: <strong>${consumptionPerHr.toFixed(3)} ${fd.unitShort}/hr</strong></div>
    <div class="prep-calc-result-line">Runtime on ${fuelQty} ${fd.unit}: <strong>${runtimeDaysFormatted}</strong></div>
    <div class="prep-calc-result-muted">24/7 operation: ${dailyFuel.toFixed(2)} ${fd.unitShort}/day · 8 hrs/day: ${daily8hrFuel.toFixed(2)} ${fd.unitShort}/day</div>
    <div class="prep-calc-result-muted">Fuel calculations are estimates. Actual consumption varies with load, altitude, temperature, and generator age. Add 10–15% margin. Never run generator indoors or near open windows (CO poisoning).</div>
  </div>`;
}

// ═══════════════════════════════════════════════════════════════
// DEHYDRATION ASSESSMENT
// ═══════════════════════════════════════════════════════════════
function calcDehydration() {
  const weightInput = document.getElementById('deh-weight');
  const severityInput = document.getElementById('deh-sev');
  const ageInput = document.getElementById('deh-age');
  const el = document.getElementById('deh-result');
  if (!weightInput || !severityInput || !ageInput || !el) return;
  const weight = parseFloat(weightInput.value) || 70;
  const sev = severityInput.value;
  const age = ageInput.value;

  const sevData = {
    mild:     { pct: 0.02, label: 'Mild (2%)',     color: '#f59e0b', route: 'Oral', urgency: 'Monitor' },
    moderate: { pct: 0.055, label: 'Moderate (5.5%)', color: '#ef4444', route: 'Oral (ORT) or IV',    urgency: 'Treat now' },
    severe:   { pct: 0.09, label: 'Severe (9%)',    color: '#dc2626', route: 'IV preferred',        urgency: 'Urgent' },
    critical: { pct: 0.12, label: 'Critical (12%)', color: '#7f1d1d', route: 'IV bolus required',   urgency: 'Emergency' },
  };
  const sd = sevData[sev];
  const deficitL = weight * sd.pct;
  const deficitML = Math.round(deficitL * 1000);

  // Replacement rate
  let rateNote = '';
  if (sev === 'mild') rateNote = 'Replace over 4–6 hours with ORS or water + electrolytes';
  else if (sev === 'moderate') rateNote = 'Replace 50–75 mL/kg over 4h orally, or IV NS at maintenance + deficit rate';
  else if (sev === 'severe') rateNote = 'IV 20–30 mL/kg NS bolus over 30 min, then reassess; replace remaining over 8–12h';
  else rateNote = 'IV 20 mL/kg NS bolus STAT; repeat until SBP >90, HR <100. ICU-level care needed';

  // Age-specific notes
  const ageNote = age === 'infant' ? 'INFANT: Oral rehydration or IV. NG tube if not drinking. Weight loss >8% = severe. Consult pediatric protocol.' :
                  age === 'child' ? 'CHILD: ORT first-line for mild/moderate. 50–100 mL/kg over 4h.' :
                  age === 'elderly' ? 'ELDERLY: Higher risk of over-resuscitation. Monitor for pulmonary edema. Lower threshold for IV access.' : '';

  // Signs to monitor
  const monitorSigns = sev === 'mild' ? 'Urine color (target pale yellow), increased thirst' :
    'Urine output (target >0.5 mL/kg/hr adult, >1 mL/kg/hr child), mental status, skin turgor, pulse rate';

  el.innerHTML = `<div class="prep-calc-result-shell" style="--prep-result-tone:${sd.color};">
    <div class="prep-calc-result-head prep-calc-result-head-toned">${sd.urgency} — ${sd.label}</div>
    <div class="prep-calc-result-line">Estimated fluid deficit: <strong>${deficitML} mL</strong> (${deficitL.toFixed(1)} L) based on ${weight}kg body weight</div>
    <div class="prep-calc-result-line">Route: <strong>${sd.route}</strong></div>
    <div class="prep-calc-result-line">${rateNote}</div>
    ${ageNote ? `<div class="prep-calc-result-muted prep-result-accent">${ageNote}</div>` : ''}
    <div class="prep-calc-result-muted">Monitor: ${monitorSigns}</div>
    <div class="prep-calc-result-muted">Always add ongoing losses (vomiting, diarrhea, fever: ~200 mL/°C above normal/day) to replacement volume.</div>
  </div>`;
}

// ═══════════════════════════════════════════════════════════════
// VITAL SIGNS ASSESSMENT
// ═══════════════════════════════════════════════════════════════
function calcVitals() {
  const hrInput = document.getElementById('vs-hr');
  const sbpInput = document.getElementById('vs-sbp');
  const dbpInput = document.getElementById('vs-dbp');
  const rrInput = document.getElementById('vs-rr');
  const tempInput = document.getElementById('vs-temp');
  const spo2Input = document.getElementById('vs-spo2');
  const ageInput = document.getElementById('vs-age');
  const el = document.getElementById('vs-result');
  if (!hrInput || !sbpInput || !dbpInput || !rrInput || !tempInput || !spo2Input || !ageInput || !el) return;
  const hr = parseInt(hrInput.value) || 0;
  const sbp = parseInt(sbpInput.value) || 0;
  const dbp = parseInt(dbpInput.value) || 0;
  const rr = parseInt(rrInput.value) || 0;
  const temp = parseFloat(tempInput.value) || 98.6;
  const spo2 = parseInt(spo2Input.value) || 98;
  const age = ageInput.value;

  // Age-specific normal ranges
  const ranges = {
    adult:   { hr:[60,100], rr:[12,20], sbpLow:100, sbpHigh:140, dbpHigh:90 },
    child:   { hr:[70,120], rr:[18,30], sbpLow:85,  sbpHigh:120, dbpHigh:80 },
    infant:  { hr:[80,140], rr:[24,40], sbpLow:70,  sbpHigh:100, dbpHigh:65 },
    elderly: { hr:[60,100], rr:[12,20], sbpLow:100, sbpHigh:150, dbpHigh:90 },
  };
  const r = ranges[age];
  const map = Math.round(dbp + (sbp - dbp) / 3);
  const pp = sbp - dbp; // pulse pressure

  const findings = [];
  let worstColor = '#22c55e';
  const flag = (msg, color) => { findings.push({msg, color}); if (color === '#ef4444' || color === '#dc2626') worstColor = color; else if (color === '#f59e0b' && worstColor === '#22c55e') worstColor = '#f59e0b'; };

  // Heart Rate
  if (hr < r.hr[0]) flag(`HR ${hr} bpm — Bradycardia (too slow)`, hr < 40 ? '#dc2626' : '#f59e0b');
  else if (hr > r.hr[1]) flag(`HR ${hr} bpm — Tachycardia (too fast)`, hr > 150 ? '#dc2626' : '#f59e0b');
  else flag(`HR ${hr} bpm — Normal`, '#22c55e');

  // Blood Pressure
  if (sbp < r.sbpLow) flag(`BP ${sbp}/${dbp} — HYPOTENSION (SBP <${r.sbpLow})`, sbp < 80 ? '#dc2626' : '#ef4444');
  else if (sbp > 180 && dbp > 120) flag(`BP ${sbp}/${dbp} — HYPERTENSIVE CRISIS`, '#dc2626');
  else if (sbp > r.sbpHigh) flag(`BP ${sbp}/${dbp} — Elevated / Hypertension`, '#f59e0b');
  else flag(`BP ${sbp}/${dbp} — Normal (MAP ${map} mmHg)`, '#22c55e');

  // Respiratory Rate
  if (rr < r.rr[0]) flag(`RR ${rr} — Bradypnea (too slow)`, rr < 8 ? '#dc2626' : '#f59e0b');
  else if (rr > r.rr[1]) flag(`RR ${rr} — Tachypnea (too fast)`, rr > 30 ? '#dc2626' : '#f59e0b');
  else flag(`RR ${rr} — Normal`, '#22c55e');

  // Temperature
  const tempC = ((temp - 32) * 5/9);
  if (temp < 95) flag(`Temp ${temp}°F (${tempC.toFixed(1)}°C) — HYPOTHERMIA`, temp < 90 ? '#dc2626' : '#ef4444');
  else if (temp > 104) flag(`Temp ${temp}°F (${tempC.toFixed(1)}°C) — HYPERTHERMIA / High Fever`, temp > 106 ? '#dc2626' : '#ef4444');
  else if (temp > 100.4) flag(`Temp ${temp}°F (${tempC.toFixed(1)}°C) — Fever`, '#f59e0b');
  else if (temp < 96.8) flag(`Temp ${temp}°F (${tempC.toFixed(1)}°C) — Low (mild hypothermia risk)`, '#f59e0b');
  else flag(`Temp ${temp}°F (${tempC.toFixed(1)}°C) — Normal`, '#22c55e');

  // SpO2
  if (spo2 < 90) flag(`SpO2 ${spo2}% — SEVERE HYPOXIA — O2 required NOW`, '#dc2626');
  else if (spo2 < 94) flag(`SpO2 ${spo2}% — Low — supplemental O2 recommended`, '#ef4444');
  else if (spo2 < 96) flag(`SpO2 ${spo2}% — Borderline low`, '#f59e0b');
  else flag(`SpO2 ${spo2}% — Normal`, '#22c55e');

  // Shock Index (HR/SBP — >1.0 = concern, >1.4 = severe)
  const si = sbp > 0 ? (hr / sbp).toFixed(2) : '—';
  const siNote = sbp > 0 && hr / sbp > 1.0 ? ` ⚠ SHOCK INDEX ${si} — Hemorrhagic/distributive shock possible` : ` Shock Index: ${si} (normal <1.0)`;

  const rows = findings.map(f => `<div class="prep-calc-result-line"><span class="prep-calc-result-dot" style="--prep-result-tone:${f.color};">●</span> ${f.msg}</div>`).join('');
  el.innerHTML = `<div class="prep-calc-result-shell" style="--prep-result-tone:${worstColor};">
    <div class="prep-calc-result-head prep-calc-result-head-toned">Vital Signs Assessment</div>
    <div class="prep-calc-result-list">${rows}</div>
    <div class="prep-calc-result-footnote">${siNote}</div>
  </div>`;
}

(function initCalcDefaults() {
  const hasNodes = ids => ids.every(id => document.getElementById(id));
  const safeInit = ({ label, fn, required }) => {
    if (!hasNodes(required)) return;
    try {
      fn();
    } catch (error) {
      console.warn(`Skipping ${label} defaults:`, error);
    }
  };
  const calculatorInitializers = [
    { label: 'KI persons', fn: renderKIPersons, required: ['ki-people-list'] },
    { label: 'IV drip', fn: calcIVDrip, required: ['iv-vol', 'iv-time', 'iv-drops', 'iv-result'] },
    { label: 'Burn area', fn: calcBurnArea, required: ['burn-weight', 'burn-result'] },
    { label: 'Dead reckoning', fn: calcDeadReckoning, required: ['dr-lat', 'dr-lon', 'dr-result'] },
    { label: 'NVIS', fn: calcNVIS, required: ['nvis-result'] },
    { label: 'Weight-based dosing', fn: calcWeightDose, required: ['dose-result'] },
    { label: 'Shelter layers', fn: renderShelterLayers, required: ['shpf-layers'] },
    { label: 'Crop calories', fn: calcCropCalories, required: ['crop-result'] },
    { label: 'Hypothermia', fn: calcHypothermia, required: ['hypo-temp', 'hypo-wind', 'hypo-hours', 'hypo-wet', 'hypo-result'] },
    { label: 'ORT', fn: calcORT, required: ['ort-unit', 'ort-weight', 'ort-sev', 'ort-result'] },
    { label: 'Antibiotic inventory', fn: calcAbxInventory, required: ['abx-drug', 'abx-qty', 'abx-people', 'abx-result'] },
    { label: 'Radiation dose', fn: calcRadDose, required: ['rad-rate', 'rad-unit', 'rad-hours', 'rad-pf', 'rad-result'] },
    { label: 'Water needs', fn: calcWaterNeeds, required: ['wn-adults', 'wn-children', 'wn-activity', 'wn-climate', 'wn-days', 'wn-result'] },
    { label: 'Generator sizing', fn: calcGenerator, required: ['gen-watts', 'gen2-load', 'gen2-fuel', 'gen2-fuel-qty', 'gen2-result'] },
    { label: 'Dehydration', fn: calcDehydration, required: ['deh-weight', 'deh-sev', 'deh-age', 'deh-result'] },
    { label: 'Vitals', fn: calcVitals, required: ['vs-hr', 'vs-sbp', 'vs-dbp', 'vs-rr', 'vs-temp', 'vs-spo2', 'vs-age', 'vs-result'] },
  ];
  setTimeout(() => {
    calculatorInitializers.forEach(safeInit);
  }, 500);
})();

// ═══════════════════════════════════════════════════════════════
// FUEL STORAGE
// ═══════════════════════════════════════════════════════════════
let _fuelData = [];

async function loadFuel() {
  try {
    _fuelData = await safeFetch('/api/fuel', {}, []);
    renderFuelSummary();
    renderFuelTable();
  } catch(e) { console.error('loadFuel', e); }
}

function renderFuelSummary() {
  const el = document.getElementById('fuel-summary');
  if (!el) return;
  const totals = {};
  _fuelData.forEach(r => {
    const k = r.fuel_type + '|' + r.unit;
    totals[k] = (totals[k] || { type: r.fuel_type, unit: r.unit, total: 0 });
    totals[k].total += parseFloat(r.quantity) || 0;
  });
  const cards = Object.values(totals);
  if (!cards.length) {
    el.innerHTML = '<div class="prep-empty-state prep-empty-state-wide">No fuel stored. Add entries to track your fuel reserves.</div>';
    return;
  }
  el.innerHTML = cards.map(c => `
    <div class="prep-summary-card">
      <div class="prep-summary-value">${c.total.toFixed(1)}</div>
      <div class="prep-summary-meta">${escapeHtml(c.unit)}</div>
      <div class="prep-summary-label">${escapeHtml(c.type)}</div>
    </div>`).join('');
}

function renderFuelTable() {
  const el = document.getElementById('fuel-table');
  if (!el) return;
  if (!_fuelData.length) {
    el.innerHTML = '<div class="prep-empty-state prep-empty-state-wide">No fuel entries logged yet.</div>';
    return;
  }
  const today = new Date().toISOString().slice(0,10);
  el.innerHTML = `<div class="prep-table-wrap"><table class="freq-table prep-data-table"><thead><tr>
    <th>Fuel Type</th><th>Qty</th><th>Container</th><th>Location</th>
    <th>Stored</th><th>Expires</th><th>Stabilizer</th><th class="prep-actions-col">Actions</th>
  </tr></thead><tbody>${_fuelData.map(r => {
    const expired = r.expires && r.expires < today;
    const expiring = r.expires && !expired && r.expires <= new Date(Date.now()+30*86400000).toISOString().slice(0,10);
    const expireClass = expired ? 'prep-date-alert-danger' : expiring ? 'prep-date-alert-warn' : '';
    return `<tr>
      <td>${escapeHtml(r.fuel_type || '—')}</td>
      <td>${parseFloat(r.quantity).toFixed(1)} ${escapeHtml(r.unit || '')}</td>
      <td>${escapeHtml(r.container || '—')}</td>
      <td>${escapeHtml(r.location || '—')}</td>
      <td>${escapeHtml(r.date_stored || '—')}</td>
      <td class="${expireClass}">${escapeHtml(r.expires || '—')}${expired?' (expired)':expiring?' (soon)':''}</td>
      <td class="prep-cell-center">${r.stabilizer_added ? 'Yes' : 'No'}</td>
      <td class="prep-row-actions"><button type="button" class="btn btn-xs btn-ghost" data-prep-action="edit-fuel" data-fuel-id="${r.id}">Edit</button> <button type="button" class="btn btn-xs btn-ghost prep-inline-delete" data-prep-action="delete-fuel" data-fuel-id="${r.id}">Delete</button></td>
    </tr>`;
  }).join('')}</tbody></table></div>`;
}

function openFuelForm() {
  document.getElementById('fuel-id').value = '';
  document.getElementById('fuel-modal-title').textContent = 'Add Fuel Entry';
  document.getElementById('fuel-type').value = 'Gasoline (Regular)';
  document.getElementById('fuel-qty').value = '5';
  document.getElementById('fuel-unit').value = 'gallons';
  document.getElementById('fuel-container').value = '';
  document.getElementById('fuel-location').value = '';
  document.getElementById('fuel-stored').value = new Date().toISOString().slice(0,10);
  document.getElementById('fuel-expires').value = '';
  document.getElementById('fuel-stabilizer').checked = false;
  document.getElementById('fuel-notes').value = '';
  const m = document.getElementById('fuel-modal');
  m.style.display = 'flex';
}

function closeFuelForm() { document.getElementById('fuel-modal').style.display = 'none'; }

function editFuel(id) {
  const r = _fuelData.find(x => x.id === id);
  if (!r) return;
  document.getElementById('fuel-id').value = r.id;
  document.getElementById('fuel-modal-title').textContent = 'Edit Fuel Entry';
  document.getElementById('fuel-type').value = r.fuel_type;
  document.getElementById('fuel-qty').value = r.quantity;
  document.getElementById('fuel-unit').value = r.unit;
  document.getElementById('fuel-container').value = r.container || '';
  document.getElementById('fuel-location').value = r.location || '';
  document.getElementById('fuel-stored').value = r.date_stored || '';
  document.getElementById('fuel-expires').value = r.expires || '';
  document.getElementById('fuel-stabilizer').checked = !!r.stabilizer_added;
  document.getElementById('fuel-notes').value = r.notes || '';
  document.getElementById('fuel-modal').style.display = 'flex';
}

async function saveFuel() {
  const id = document.getElementById('fuel-id').value;
  const body = {
    fuel_type: document.getElementById('fuel-type').value,
    quantity: parseFloat(document.getElementById('fuel-qty').value) || 0,
    unit: document.getElementById('fuel-unit').value,
    container: document.getElementById('fuel-container').value,
    location: document.getElementById('fuel-location').value,
    date_stored: document.getElementById('fuel-stored').value,
    expires: document.getElementById('fuel-expires').value,
    stabilizer_added: document.getElementById('fuel-stabilizer').checked ? 1 : 0,
    notes: document.getElementById('fuel-notes').value,
  };
  const url = id ? `/api/fuel/${id}` : '/api/fuel';
  try {
    if (id) await apiPut(url, body);
    else await apiPost(url, body);
  } catch(e) {
    toast(e?.data?.error || 'Failed to save fuel entry', 'error');
    return;
  }
  closeFuelForm();
  loadFuel();
  toast('Fuel entry saved', 'success');
}

async function deleteFuel(id) {
  if (!confirm('Delete this fuel entry?')) return;
  try {
    await apiDelete(`/api/fuel/${id}`);
    loadFuel();
    toast('Fuel entry deleted', 'success');
  } catch(e) { toast('Failed to delete fuel entry', 'error'); }
}

// ═══════════════════════════════════════════════════════════════
// EQUIPMENT MAINTENANCE
// ═══════════════════════════════════════════════════════════════
let _equipData = [];

async function loadEquipment() {
  try {
    _equipData = await safeFetch('/api/equipment', {}, []);
    renderEquipStatus();
    renderEquipTable();
  } catch(e) { console.error('loadEquipment', e); }
}

function renderEquipStatus() {
  const el = document.getElementById('equip-status-row');
  if (!el) return;
  const counts = { operational: 0, 'needs-service': 0, 'in-service': 0, 'non-operational': 0 };
  _equipData.forEach(r => { if (counts[r.status] !== undefined) counts[r.status]++; });
  const today = new Date().toISOString().slice(0,10);
  const overdue = _equipData.filter(r => r.next_service && r.next_service < today).length;
  const cards = [
    ['Operational', counts['operational'], 'prep-summary-card-ok'],
    ['Needs Service', counts['needs-service'], 'prep-summary-card-warn'],
    ['Non-Operational', counts['non-operational'], 'prep-summary-card-danger'],
    ['Service Overdue', overdue, 'prep-summary-card-danger'],
  ].filter(([, count]) => count > 0);
  if (!cards.length) {
    el.innerHTML = '<div class="prep-empty-state prep-empty-state-wide">No equipment logged yet.</div>';
    return;
  }
  el.innerHTML = [
    ...cards.map(([label, count, cardClass]) => `<div class="prep-summary-card ${cardClass}">
      <div class="prep-summary-value">${count}</div>
      <div class="prep-summary-label">${label}</div>
    </div>`)
  ].join('');
}

const _equipCatIcons = { generator:'⚡', vehicle:'🚗', tool:'🔧', communication:'📻', medical:'💊', water:'💧', security:'🔒', general:'⚙️' };

function renderEquipTable() {
  const el = document.getElementById('equip-table');
  if (!el) return;
  if (!_equipData.length) {
    el.innerHTML = '<div class="prep-empty-state prep-empty-state-wide">No equipment logged. Track generators, vehicles, tools, and critical devices here.</div>';
    return;
  }
  const today = new Date().toISOString().slice(0,10);
  el.innerHTML = `<div class="prep-table-wrap"><table class="freq-table prep-data-table"><thead><tr>
    <th>Equipment</th><th>Category</th><th>Status</th><th>Last Service</th><th>Next Service</th><th>Location</th><th class="prep-actions-col">Actions</th>
  </tr></thead><tbody>${_equipData.map(r => {
    const overdue = r.next_service && r.next_service < today;
    const upcoming = r.next_service && !overdue && r.next_service <= new Date(Date.now()+30*86400000).toISOString().slice(0,10);
    const nextServiceClass = overdue ? 'prep-date-alert-danger' : upcoming ? 'prep-date-alert-warn' : '';
    return `<tr>
      <td>${_equipCatIcons[r.category]||'⚙️'} <strong>${escapeHtml(r.name || 'Unnamed')}</strong>${r.service_notes?`<span class="prep-cell-note">${escapeHtml(r.service_notes.slice(0,60))}${r.service_notes.length>60?'...':''}</span>`:''}</td>
      <td class="prep-cell-capitalize">${escapeHtml(r.category || 'general')}</td>
      <td><span class="prep-status-badge prep-status-badge-${escapeAttr(r.status || 'operational')}">${escapeHtml((r.status || 'operational').replace('-', ' '))}</span></td>
      <td>${escapeHtml(r.last_service || '—')}</td>
      <td class="${nextServiceClass}">${escapeHtml(r.next_service||'—')}${overdue?' (overdue)':upcoming?' (soon)':''}</td>
      <td>${escapeHtml(r.location || '—')}</td>
      <td class="prep-row-actions"><button type="button" class="btn btn-xs btn-ghost" data-prep-action="edit-equip" data-equip-id="${r.id}">Edit</button> <button type="button" class="btn btn-xs btn-primary" data-prep-action="mark-equip-serviced" data-equip-id="${r.id}" title="Mark serviced today">Serviced</button> <button type="button" class="btn btn-xs btn-ghost prep-inline-delete" data-prep-action="delete-equip" data-equip-id="${r.id}">Delete</button></td>
    </tr>`;
  }).join('')}</tbody></table></div>`;
}

function openEquipForm() {
  document.getElementById('equip-id').value = '';
  document.getElementById('equip-modal-title').textContent = 'Add Equipment';
  document.getElementById('equip-name').value = '';
  document.getElementById('equip-category').value = 'generator';
  document.getElementById('equip-status').value = 'operational';
  document.getElementById('equip-last').value = '';
  document.getElementById('equip-next').value = '';
  document.getElementById('equip-location').value = '';
  document.getElementById('equip-service-notes').value = '';
  document.getElementById('equip-notes').value = '';
  document.getElementById('equip-modal').style.display = 'flex';
}

function closeEquipForm() { document.getElementById('equip-modal').style.display = 'none'; }

function editEquip(id) {
  const r = _equipData.find(x => x.id === id);
  if (!r) return;
  document.getElementById('equip-id').value = r.id;
  document.getElementById('equip-modal-title').textContent = 'Edit Equipment';
  document.getElementById('equip-name').value = r.name;
  document.getElementById('equip-category').value = r.category;
  document.getElementById('equip-status').value = r.status;
  document.getElementById('equip-last').value = r.last_service || '';
  document.getElementById('equip-next').value = r.next_service || '';
  document.getElementById('equip-location').value = r.location || '';
  document.getElementById('equip-service-notes').value = r.service_notes || '';
  document.getElementById('equip-notes').value = r.notes || '';
  document.getElementById('equip-modal').style.display = 'flex';
}

async function saveEquip() {
  const id = document.getElementById('equip-id').value;
  const body = {
    name: document.getElementById('equip-name').value.trim(),
    category: document.getElementById('equip-category').value,
    status: document.getElementById('equip-status').value,
    last_service: document.getElementById('equip-last').value,
    next_service: document.getElementById('equip-next').value,
    location: document.getElementById('equip-location').value,
    service_notes: document.getElementById('equip-service-notes').value,
    notes: document.getElementById('equip-notes').value,
  };
  if (!body.name) { toast('Equipment name required', 'warning'); return; }
  const url = id ? `/api/equipment/${id}` : '/api/equipment';
  try {
    if (id) await apiPut(url, body);
    else await apiPost(url, body);
  } catch(e) {
    toast(e?.data?.error || 'Failed to save equipment', 'error');
    return;
  }
  closeEquipForm();
  loadEquipment();
  toast('Equipment saved', 'success');
}

async function markServiced(id) {
  const r = _equipData.find(x => x.id === id);
  if (!r) return;
  const today = new Date().toISOString().slice(0,10);
  try {
    await apiPut(`/api/equipment/${id}`, { ...r, last_service: today, status: 'operational' });
  } catch(e) {
    toast(e?.data?.error || 'Failed to update equipment service', 'error');
    return;
  }
  loadEquipment();
  toast('Marked serviced today', 'success');
}

async function deleteEquip(id) {
  if (!confirm('Delete this equipment entry?')) return;
  try {
    await apiDelete(`/api/equipment/${id}`);
    loadEquipment();
    toast('Equipment deleted', 'success');
  } catch(e) { toast('Failed to delete equipment', 'error'); }
}

// ═══════════════════════════════════════════════════════════════
// (Prep sub-tab loaders consolidated into main switchPrepSub function)
// ANTENNA LENGTH CALCULATOR
function calcAntenna() {
  const freq = parseFloat(document.getElementById('ant-freq')?.value);
  const factor = parseFloat(document.getElementById('ant-type')?.value || '0.5');
  const el = document.getElementById('ant-result');
  if (!el || !freq || freq <= 0) return;
  // Speed of light / frequency = wavelength in meters
  const wavelength_m = 299.792 / freq;
  const length_m = wavelength_m * factor;
  const length_ft = length_m * 3.28084;
  const length_in = length_ft * 12;
  const typeName = document.getElementById('ant-type')?.selectedOptions[0]?.text || '';
  el.innerHTML = `<strong class="antenna-result-value">${length_ft.toFixed(1)} ft</strong> <span class="text-muted">(${length_m.toFixed(2)} m / ${length_in.toFixed(0)} in)</span>
    <div class="antenna-result-meta">${typeName} for ${freq} MHz — Wavelength: ${wavelength_m.toFixed(2)} m</div>
    <div class="antenna-result-note">Tip: Actual length varies ~5% based on wire thickness and height above ground. Cut slightly long and trim to tune.</div>`;
}

// Init calculators on load
document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('bal-caliber')) calcBallistics();
  if (document.getElementById('comp-browns')) calcCompost();
  if (document.getElementById('pr-acres')) calcPastureRotation();
  if (document.getElementById('nb-length')) calcNaturalBuilding();
  if (document.getElementById('fall-h1')) calcFallout();
  if (document.getElementById('can-food')) calcCanning();
  if (document.getElementById('ant-freq')) calcAntenna();
});
/* ─── Task Scheduler ─── */
function showTaskForm() { document.getElementById('task-form').style.display = 'block'; }
function hideTaskForm() { document.getElementById('task-form').style.display = 'none'; }

async function loadTasks() {
  const el = document.getElementById('task-list');
  if (!el) return;
  try {
    const tasks = await safeFetch('/api/tasks', {}, null);
    if (!Array.isArray(tasks)) throw new Error('invalid tasks');
    if (!tasks.length) { el.innerHTML = '<div class="settings-empty-state">No scheduled tasks. Click "+ New Task" to create one.</div>'; return; }
    const now = new Date();
    el.innerHTML = tasks.map(t => {
      const due = new Date(t.next_due);
      const isOverdue = due < now;
      const isToday = due.toDateString() === now.toDateString();
      const dueClass = isOverdue ? 'settings-task-due-overdue' : isToday ? 'settings-task-due-today' : 'settings-task-due-upcoming';
      const recIcons = {daily:'&#x1F504;',weekly:'&#x1F4C5;',monthly:'&#x1F5D3;',quarterly:'&#x1F4CA;',yearly:'&#x1F389;',once:''};
      return `<div class="settings-record-card settings-task-card">
        <div class="settings-record-head">
          <div class="settings-record-main">
            <span class="settings-row-title">${escapeHtml(t.name)}</span>
            <div class="settings-record-meta-list">
              <span class="settings-row-pill">${escapeHtml(t.category||'other')}</span>
              <span class="settings-row-meta">${recIcons[t.recurrence]||''} ${t.recurrence||''}</span>
              ${t.assigned_to ? '<span class="settings-row-detail">Assigned: '+escapeHtml(t.assigned_to)+'</span>' : ''}
            </div>
          </div>
          <div class="settings-record-actions">
            <button class="btn btn-sm settings-row-compact-btn" type="button" data-shell-action="complete-task" data-task-id="${t.id}" title="Complete">&#10003;</button>
            <button class="btn btn-sm btn-danger settings-row-compact-btn" type="button" data-shell-action="delete-task" data-task-id="${t.id}" aria-label="Delete task">x</button>
          </div>
        </div>
        <div class="settings-record-foot">
          <span class="settings-task-due ${dueClass}">${due.toLocaleDateString()} ${due.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</span>
        </div>
      </div>`;
    }).join('');
  } catch(e) {
    console.error('loadTasks:', e);
    el.innerHTML = '<div class="settings-empty-state">Could not load scheduled tasks right now.</div>';
  }
}

async function saveTask() {
  const name = document.getElementById('task-name').value.trim();
  if (!name) { toast('Task name is required', 'error'); return; }
  try {
    await apiPost('/api/tasks', {
      name, category: document.getElementById('task-category').value,
      recurrence: document.getElementById('task-recurrence').value,
      next_due: document.getElementById('task-next-due').value || new Date().toISOString(),
      assigned_to: document.getElementById('task-assigned').value.trim(),
      notes: document.getElementById('task-notes').value.trim()
    });
    toast('Task created', 'success');
    hideTaskForm();
    document.getElementById('task-name').value = '';
    document.getElementById('task-assigned').value = '';
    document.getElementById('task-notes').value = '';
    loadTasks();
  } catch(e) { toast('Failed to save task', 'error'); }
}

async function completeTask(id) {
  try {
    await apiPost(`/api/tasks/${id}/complete`, {});
    toast('Task completed', 'success');
    loadTasks();
  } catch(e) { toast('Failed to complete task', 'error'); }
}

async function deleteTask(id) {
  if (!confirm('Delete this task?')) return;
  try {
    await apiDelete(`/api/tasks/${id}`);
    toast('Task deleted', 'info');
    loadTasks();
  } catch(e) { toast('Failed to delete task', 'error'); }
}

/* ─── Watch/Shift Rotation Planner ─── */
function showWatchForm() { document.getElementById('watch-form').style.display = 'block'; }
function hideWatchForm() { document.getElementById('watch-form').style.display = 'none'; }

async function loadWatchSchedules() {
  const el = document.getElementById('watch-list');
  if (!el) return;
  try {
    const schedules = await safeFetch('/api/watch-schedules', {}, null);
    if (!Array.isArray(schedules)) throw new Error('invalid watch schedules');
    if (!schedules.length) { el.innerHTML = '<div class="settings-empty-state">No watch schedules. Click "+ New Watch Schedule" to create one.</div>'; return; }
    el.innerHTML = schedules.map(s => {
      const personnel = safeJsonParse(s.personnel, []);
      return `<div class="settings-record-card settings-watch-card">
        <div class="settings-record-head">
          <div class="settings-record-main">
            <span class="settings-row-title">${escapeHtml(s.name)}</span>
            <div class="settings-record-meta-list">
              <span class="settings-row-pill">${s.shift_duration_hours}h shifts</span>
              <span class="settings-row-meta">${personnel.length} personnel</span>
              <span class="settings-row-detail">${escapeHtml(s.start_date)} to ${escapeHtml(s.end_date||'—')}</span>
            </div>
          </div>
          <div class="settings-record-actions">
            <button class="btn btn-sm settings-row-compact-btn" type="button" data-shell-action="view-watch-schedule" data-watch-id="${s.id}">View</button>
            <a class="btn btn-sm settings-row-compact-btn" href="/api/watch-schedules/${s.id}/print" target="_blank" rel="noopener noreferrer">Print</a>
            <button class="btn btn-sm btn-danger settings-row-compact-btn" type="button" data-shell-action="delete-watch-schedule" data-watch-id="${s.id}" aria-label="Delete watch schedule">x</button>
          </div>
        </div>
      </div>`;
    }).join('');
  } catch(e) {
    console.error('loadWatchSchedules:', e);
    el.innerHTML = '<div class="settings-empty-state">Could not load watch schedules right now.</div>';
  }
}

async function createWatchSchedule() {
  const name = document.getElementById('watch-name').value.trim() || 'Watch Schedule';
  const start_date = document.getElementById('watch-start-date').value;
  const end_date = document.getElementById('watch-end').value;
  const shift_duration_hours = parseInt(document.getElementById('watch-shift-hours').value);
  const personnelText = document.getElementById('watch-personnel').value.trim();
  const notes = document.getElementById('watch-notes').value.trim();

  if (!start_date) { toast('Start date is required', 'error'); return; }
  const personnel = personnelText.split('\n').map(s => s.trim()).filter(Boolean);
  if (personnel.length < 2) { toast('At least 2 personnel required (one per line)', 'error'); return; }

  try {
    const data = await apiPost('/api/watch-schedules', {
      name, start_date, end_date, shift_duration_hours, personnel, notes
    });
    toast('Schedule created: ' + data.shifts + ' shifts', 'success');
    hideWatchForm();
    document.getElementById('watch-personnel').value = '';
    document.getElementById('watch-notes').value = '';
    loadWatchSchedules();
  } catch(e) { toast('Failed to create watch schedule', 'error'); }
}

async function viewWatchSchedule(id) {
  try {
    const s = await apiFetch(`/api/watch-schedules/${id}`);
    if (s.error) { toast(s.error, 'error'); return; }
    let schedule = safeJsonParse(s.schedule_json, []);
    let personnel = safeJsonParse(s.personnel, []);

    document.getElementById('watch-detail-title').textContent = s.name;
    document.getElementById('watch-detail-meta').innerHTML =
      `Period: ${escapeHtml(s.start_date)} to ${escapeHtml(s.end_date||'ongoing')} | Shift: ${s.shift_duration_hours}h | Personnel: ${personnel.join(', ')}` +
      (s.notes ? ` | Notes: ${escapeHtml(s.notes)}` : '');

    let html = '<table class="freq-table prep-data-table prep-reference-table-compact watch-result-table"><thead><tr>' +
      '<th>#</th>' +
      '<th>Person</th>' +
      '<th>Start</th>' +
      '<th>End</th>' +
      '</tr></thead><tbody>';
    schedule.forEach((shift, i) => {
      html += `<tr><td>${i+1}</td>` +
        `<td class="watch-result-member">${escapeHtml(shift.person)}</td>` +
        `<td>${escapeHtml(shift.start)}</td>` +
        `<td>${escapeHtml(shift.end)}</td></tr>`;
    });
    html += '</tbody></table>';
    document.getElementById('watch-detail-table').innerHTML = html;
    document.getElementById('watch-detail').style.display = 'block';
  } catch(e) { toast('Failed to load schedule', 'error'); }
}

async function deleteWatchSchedule(id) {
  if (!confirm('Delete this watch schedule?')) return;
  try {
    await apiDelete(`/api/watch-schedules/${id}`);
    toast('Watch schedule deleted', 'info');
    document.getElementById('watch-detail').style.display = 'none';
    loadWatchSchedules();
  } catch(e) { toast('Failed to delete watch schedule', 'error'); }
}

/* ─── Sunrise/Sunset Widget ─── */
let _sunData = null;
async function loadSunData() {
  try {
    let lat, lng;
    const settings = await safeFetch('/api/settings', {}, {});
    if (settings.latitude && settings.longitude) { lat = settings.latitude; lng = settings.longitude; }
    else {
      const wps = await safeFetch('/api/waypoints', {}, []);
      if (wps.length) { lat = wps[0].latitude; lng = wps[0].longitude; }
    }
    if (!lat || !lng) return;
    _sunData = await apiFetch(`/api/sun?lat=${lat}&lng=${lng}`);
  } catch(e) {}
}

/* ─── Predictive Alerts ─── */
async function loadPredictiveAlerts() {
  try {
    const preds = await safeFetch('/api/alerts/predictive', {}, []);
    if (!Array.isArray(preds) || !preds.length) return;
    const items = document.getElementById('alert-items');
    if (!items) return;
    // Update badge count to include predictions
    const badge = document.getElementById('alert-badge');
    const count = document.getElementById('alert-count');
    if (badge && badge.style.display !== 'none') {
      const current = parseInt(badge.textContent) || 0;
      badge.textContent = current + preds.length;
      if (count) count.textContent = '(' + (current + preds.length) + ')';
    } else if (badge && preds.length) {
      badge.style.display = 'block';
      badge.textContent = preds.length;
      if (count) count.textContent = '(' + preds.length + ')';
    }
    const predHtml = preds.map(function(a) {
      const sevClass = a.severity === 'critical' ? 'critical' : 'info';
      return '<div class="alert-item">'
        + '<span class="alert-sev ' + sevClass + '">PREDICTED</span>'
        + '<div class="alert-body">'
        + '<div class="alert-title">' + escapeHtml(a.title) + '</div>'
        + '<div class="alert-msg">' + escapeHtml(a.message) + '</div>'
        + '</div>'
        + '</div>';
    }).join('');
    items.insertAdjacentHTML('beforeend', predHtml);
  } catch(e) {}
}

/* ─── CSV Import ─── */
let _csvParsedData = null;
let _csvHeaders = [];

function showCSVImportModal() {
  document.getElementById('csv-import-modal').style.display = 'flex';
}
function closeCSVImportModal() {
  document.getElementById('csv-import-modal').style.display = 'none';
  _csvParsedData = null; _csvHeaders = [];
}

function previewCSVImport() {
  const file = document.getElementById('csv-import-file').files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = function(e) {
    const text = e.target.result;
    const lines = text.split('\n').filter(l => l.trim());
    if (lines.length < 2) { toast('CSV file appears empty', 'error'); return; }
    function parseCSVLine(line) {
      const fields = [];
      let field = '', inQuotes = false;
      for (let i = 0; i < line.length; i++) {
        const c = line[i];
        if (inQuotes) {
          if (c === '"' && line[i+1] === '"') { field += '"'; i++; }
          else if (c === '"') { inQuotes = false; }
          else { field += c; }
        } else {
          if (c === '"') { inQuotes = true; }
          else if (c === ',') { fields.push(field.trim()); field = ''; }
          else { field += c; }
        }
      }
      fields.push(field.trim());
      return fields;
    }
    _csvHeaders = parseCSVLine(lines[0]);
    _csvParsedData = lines.slice(1).map(line => {
      const vals = parseCSVLine(line);
      const row = {};
      _csvHeaders.forEach((h, i) => row[h] = vals[i] || '');
      return row;
    });

    const table = document.getElementById('csv-target-table').value;
    const dbCols = getDBColumns(table);

    // Column mapping UI
    const mapEl = document.getElementById('csv-column-mapping');
    mapEl.innerHTML = _csvHeaders.map(h =>
      `<span>${escapeHtml(h)}</span><span>&#8594;</span><select class="csv-col-map settings-csv-select" data-csv="${escapeHtml(h)}" aria-label="Map CSV column ${escapeAttr(h)}"><option value="">-- skip --</option>${dbCols.map(c => `<option value="${c}" ${c.toLowerCase()===h.toLowerCase()?'selected':''}>${c}</option>`).join('')}</select>`
    ).join('');

    // Preview table
    const preview = _csvParsedData.slice(0, 3);
    const prevEl = document.getElementById('csv-preview-table');
    prevEl.innerHTML = `<table class="freq-table"><thead><tr>${_csvHeaders.map(h=>'<th>'+escapeHtml(h)+'</th>').join('')}</tr></thead><tbody>${preview.map(r => '<tr>'+_csvHeaders.map(h=>'<td>'+escapeHtml(r[h]||'')+'</td>').join('')+'</tr>').join('')}</tbody></table>`;

    document.getElementById('csv-mapping-area').style.display = 'block';
    document.getElementById('csv-preview-area').style.display = 'block';
    document.getElementById('csv-import-btn').style.display = 'inline-block';
  };
  reader.readAsText(file);
}

function getDBColumns(table) {
  const cols = {
    inventory: ['name','category','quantity','unit','min_quantity','daily_usage','expiration_date','location','barcode','cost_per_unit','notes'],
    contacts: ['name','callsign','role','phone','email','address','skills','blood_type','medical_notes','rally_point','notes'],
    waypoints: ['name','latitude','longitude','category','description','notes'],
    seeds: ['name','variety','quantity','source','planting_season','days_to_harvest','notes'],
    ammo: ['caliber','type','quantity','brand','location','notes'],
    fuel: ['fuel_type','quantity_gallons','container','location','date_stored','notes'],
    equipment: ['name','category','condition','location','last_maintenance','next_maintenance','notes']
  };
  return cols[table] || [];
}

async function executeCSVImport() {
  if (!_csvParsedData || !_csvParsedData.length) { toast('No CSV data loaded', 'error'); return; }
  const table = document.getElementById('csv-target-table').value;
  const mappings = {};
  document.querySelectorAll('.csv-col-map').forEach(sel => {
    if (sel.value) mappings[sel.dataset.csv] = sel.value;
  });
  if (!Object.keys(mappings).length) { toast('No columns mapped', 'error'); return; }
  const rows = _csvParsedData.map(row => {
    const mapped = {};
    for (const [csvCol, dbCol] of Object.entries(mappings)) mapped[dbCol] = row[csvCol] || '';
    return mapped;
  });
  try {
    const result = await apiPost('/api/import/csv', { table, rows });
    toast(`Imported ${result.imported || rows.length} rows into ${table}`, 'success');
    closeCSVImportModal();
  } catch(e) { toast('Import failed: ' + e.message, 'error'); }
}

/* ─── Daily Operations Brief (v7.7.0) ─── */
function renderInlineWorkspaceEmptyState(className, title, body) {
  return `<div class="${className}"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(body)}</span></div>`;
}

async function generateDailyBrief() {
  const body = document.getElementById('daily-brief-body');
  const btn = document.getElementById('daily-brief-gen-btn');
  if (!body) return;
  if (btn) { btn.setAttribute('aria-busy', 'true'); btn.disabled = true; }
  body.innerHTML = renderInlineWorkspaceEmptyState(
    'daily-brief-empty',
    'Compiling the brief',
    'Pulling together weather, alerts, tasks, and household context for a fresh operating snapshot.'
  );
  try {
    const d = await apiFetch('/api/brief/daily');
    body.innerHTML = _renderDailyBrief(d);
  } catch (e) {
    body.innerHTML = renderInlineWorkspaceEmptyState(
      'daily-brief-empty',
      'Brief unavailable',
      'The desk could not compile a fresh brief right now. Try again in a moment.'
    );
  } finally {
    if (btn) { btn.removeAttribute('aria-busy'); btn.disabled = false; }
  }
}

function _renderDailyBrief(d) {
  const s = d.sections || {};
  const blocks = [];

  const emer = s.emergency || {};
  if (emer.active) {
    blocks.push(`<div class="daily-brief-block daily-brief-block-alert">
      <div class="daily-brief-block-title">⚠ EMERGENCY MODE ACTIVE</div>
      <div>${escapeHtml(emer.reason || '')}</div>
    </div>`);
  }

  const w = s.weather;
  if (w) {
    const bits = [];
    if (w.temp_c != null) bits.push(`${w.temp_c}°C`);
    if (w.humidity != null) bits.push(`${w.humidity}% humidity`);
    if (w.pressure != null) bits.push(`${w.pressure} hPa`);
    if (w.conditions) bits.push(escapeHtml(w.conditions));
    blocks.push(`<div class="daily-brief-block">
      <div class="daily-brief-block-title">Weather</div>
      <div>${bits.length ? bits.join(' · ') : 'No reading'}</div>
    </div>`);
  }

  const p = s.proximity;
  if (p) {
    if (p.count === 0) {
      blocks.push(`<div class="daily-brief-block daily-brief-block-ok">
        <div class="daily-brief-block-title">Proximity (within ${Math.round(p.radius_km)} km)</div>
        <div>All clear — no active threats.</div>
      </div>`);
    } else {
      const top = p.events.slice(0, 5).map(e =>
        `<li>${escapeHtml(e.event_type.replace(/_/g, ' '))}: ${escapeHtml(e.title || '')} <span class="daily-brief-dist">${e.distance_km} km</span></li>`
      ).join('');
      blocks.push(`<div class="daily-brief-block daily-brief-block-warn">
        <div class="daily-brief-block-title">Proximity — ${p.count} active within ${Math.round(p.radius_km)} km</div>
        <ul class="daily-brief-list">${top}</ul>
      </div>`);
    }
  }

  const inv = s.inventory || {};
  const exp = (inv.expiring_14d || []).slice(0, 5);
  const low = (inv.low_stock || []).slice(0, 5);
  if (exp.length || low.length) {
    const expHtml = exp.length
      ? `<strong>Expiring (14d):</strong> ` + exp.map(r => escapeHtml(r.name)).join(', ')
      : '';
    const lowHtml = low.length
      ? `<strong>Low stock:</strong> ` + low.map(r => escapeHtml(r.name)).join(', ')
      : '';
    blocks.push(`<div class="daily-brief-block daily-brief-block-warn">
      <div class="daily-brief-block-title">Inventory</div>
      ${expHtml ? `<div>${expHtml}</div>` : ''}
      ${lowHtml ? `<div>${lowHtml}</div>` : ''}
    </div>`);
  }

  const tasks = (s.tasks || {}).due_today || [];
  if (tasks.length) {
    const top = tasks.slice(0, 5).map(t => `<li>${escapeHtml(t.title || '')}</li>`).join('');
    blocks.push(`<div class="daily-brief-block">
      <div class="daily-brief-block-title">Tasks due today (${tasks.length})</div>
      <ul class="daily-brief-list">${top}</ul>
    </div>`);
  }

  const fam = s.family;
  if (fam && fam.total > 0) {
    const parts = Object.entries(fam.summary || {}).map(([k, v]) => `${k.replace('_', ' ')}: ${v}`);
    blocks.push(`<div class="daily-brief-block">
      <div class="daily-brief-block-title">Family check-in (${fam.total})</div>
      <div>${parts.join(' · ')}</div>
    </div>`);
  }

  if (!blocks.length) {
    return renderInlineWorkspaceEmptyState(
      'daily-brief-empty',
      'Quiet signal picture',
      'The brief compiled successfully, but nothing unusual is standing out right now.'
    );
  }
  const ts = d.generated_at ? new Date(d.generated_at).toLocaleString() : '';
  return blocks.join('') + `<div class="daily-brief-footer">Compiled ${escapeHtml(ts)}</div>`;
}

/* ─── Family Check-in Board (v7.6.0) ─── */
const _FAMILY_STATUS_LABELS = {
  ok: 'OK',
  needs_help: 'NEEDS HELP',
  en_route: 'EN ROUTE',
  unaccounted: 'UNACCOUNTED',
};
const _FAMILY_STATUS_ORDER = ['ok', 'en_route', 'needs_help', 'unaccounted'];

async function loadFamilyCheckins() {
  const list = document.getElementById('family-checkin-list');
  const summary = document.getElementById('family-checkin-summary');
  if (!list || !summary) return;
  try {
    const d = await apiFetch('/api/family-checkins');
    _renderFamilySummary(d.summary || {}, d.total || 0);
    if (!d.members || !d.members.length) {
      list.innerHTML = renderInlineWorkspaceEmptyState(
        'family-checkin-empty',
        'No household check-ins yet',
        'Add each person you want on the board so status changes, drills, and accountability stay easy to track.'
      );
      return;
    }
    list.innerHTML = d.members.map(m => _renderFamilyRow(m)).join('');
  } catch (e) {
    list.innerHTML = renderInlineWorkspaceEmptyState(
      'family-checkin-empty',
      'Check-in board unavailable',
      'The desk could not load household status right now. Refresh and try again.'
    );
  }
}

function _renderFamilySummary(summary, total) {
  const el = document.getElementById('family-checkin-summary');
  if (!el) return;
  if (!total) { el.innerHTML = ''; return; }
  const parts = _FAMILY_STATUS_ORDER.map(s => {
    const count = summary[s] || 0;
    if (!count) return '';
    return `<span class="family-checkin-chip family-checkin-chip-${s}"><strong>${count}</strong> ${escapeHtml(_FAMILY_STATUS_LABELS[s])}</span>`;
  }).filter(Boolean);
  el.innerHTML = parts.join('');
}

function _renderFamilyRow(m) {
  const buttons = _FAMILY_STATUS_ORDER.map(s => {
    const active = m.status === s ? 'is-active' : '';
    return `<button type="button" class="family-status-btn family-status-btn-${s} ${active}" data-shell-action="update-family-status" data-member-id="${m.id}" data-status="${s}" title="Set status to ${escapeAttr(_FAMILY_STATUS_LABELS[s])}">${escapeHtml(_FAMILY_STATUS_LABELS[s])}</button>`;
  }).join('');
  const updated = m.updated_at ? new Date(m.updated_at + (m.updated_at.endsWith('Z') ? '' : 'Z')).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
  return `<div class="family-checkin-row family-checkin-row-${m.status}">
    <div class="family-checkin-main">
      <div class="family-checkin-name">${escapeHtml(m.name)}${m.phone ? ` <span class="family-checkin-phone">${escapeHtml(m.phone)}</span>` : ''}</div>
      <div class="family-checkin-meta">${m.location ? escapeHtml(m.location) + ' · ' : ''}Updated ${escapeHtml(updated)}</div>
    </div>
    <div class="family-checkin-actions">${buttons}</div>
    <button type="button" class="btn btn-sm btn-ghost family-checkin-del" data-shell-action="delete-family-member" data-member-id="${m.id}" data-member-name="${escapeAttr(m.name)}" title="Remove" aria-label="Remove">x</button>
  </div>`;
}

function openAddFamilyMember() {
  document.getElementById('family-add-modal')?.classList.remove('is-hidden');
  const name = document.getElementById('family-add-name');
  if (name) { name.value = ''; name.focus(); }
  const phone = document.getElementById('family-add-phone');
  if (phone) phone.value = '';
}

function closeAddFamilyMember() {
  document.getElementById('family-add-modal')?.classList.add('is-hidden');
}

async function submitAddFamilyMember() {
  const name = (document.getElementById('family-add-name')?.value || '').trim();
  const phone = (document.getElementById('family-add-phone')?.value || '').trim();
  if (!name) { toast('Name required', 'warning'); return; }
  try {
    await apiPost('/api/family-checkins', { name, phone });
    closeAddFamilyMember();
    loadFamilyCheckins();
    toast(`Added ${name}`, 'success');
  } catch (e) {
    toast(e?.data?.error || 'Could not add member', 'error');
  }
}

async function updateFamilyStatus(memberId, status) {
  try {
    await apiPut('/api/family-checkins/' + memberId, { status });
    loadFamilyCheckins();
  } catch (e) {
    toast('Could not update status', 'error');
  }
}

async function deleteFamilyMember(memberId, name) {
  if (!confirm(`Remove ${name} from check-in board?`)) return;
  try {
    await apiDelete('/api/family-checkins/' + memberId);
    loadFamilyCheckins();
  } catch (e) {
    toast('Could not remove member', 'error');
  }
}

async function resetFamilyCheckins() {
  if (!confirm('Reset every member back to OK? (use after a drill or when the situation ends)')) return;
  try {
    await apiPost('/api/family-checkins/reset-all', {});
    loadFamilyCheckins();
    toast('All members reset to OK', 'success');
  } catch (e) {
    toast('Could not reset', 'error');
  }
}

// Load on page init
document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('family-checkin-list')) loadFamilyCheckins();
});

/* ─── Emergency Mode (v7.5.0) ─── */
let _emergencyTickInterval = null;

function openEmergencyEnterModal() {
  document.getElementById('emergency-enter-modal')?.classList.remove('is-hidden');
  const input = document.getElementById('emergency-reason-input');
  if (input) { input.value = ''; input.focus(); }
}
function closeEmergencyEnterModal() {
  document.getElementById('emergency-enter-modal')?.classList.add('is-hidden');
}
function openEmergencyExitModal() {
  document.getElementById('emergency-exit-modal')?.classList.remove('is-hidden');
  document.getElementById('emergency-closeout-input')?.focus();
}
function closeEmergencyExitModal() {
  document.getElementById('emergency-exit-modal')?.classList.add('is-hidden');
}

async function confirmEmergencyEnter() {
  const reason = (document.getElementById('emergency-reason-input')?.value || '').trim() || 'Emergency';
  try {
    const res = await apiPost('/api/emergency/enter', { reason });
    closeEmergencyEnterModal();
    _applyEmergencyState({ active: true, reason, started_at: res.started_at, duration_hours: 0 });
    toast('Emergency Mode activated', 'warning');
    // Announce via TTS if the Voice Copilot is available
    try {
      if (window.NomadSpeech && window.NomadSpeech.isSupported()) {
        window.NomadSpeech.speak('Emergency mode activated. ' + reason, { interrupt: true });
      }
    } catch (_) {}
  } catch (e) {
    toast('Could not activate emergency mode', 'error');
  }
}

async function confirmEmergencyExit() {
  const closeout_note = (document.getElementById('emergency-closeout-input')?.value || '').trim();
  try {
    const res = await apiPost('/api/emergency/exit', { closeout_note });
    closeEmergencyExitModal();
    _applyEmergencyState({ active: false });
    const hrs = res.duration_hours != null ? ` (${res.duration_hours}h)` : '';
    toast('Emergency Mode ended' + hrs, 'success');
    try {
      if (window.NomadSpeech && window.NomadSpeech.isSupported()) {
        window.NomadSpeech.speak('Emergency mode ended' + (hrs || ''), { interrupt: true });
      }
    } catch (_) {}
  } catch (e) {
    toast('Could not exit emergency mode', 'error');
  }
}

function _applyEmergencyState(state) {
  const banner = document.getElementById('emergency-banner');
  const body = document.body;
  if (!banner || !body) return;
  if (state.active) {
    banner.classList.remove('is-hidden');
    body.classList.add('emergency-mode');
    const reasonEl = document.getElementById('emergency-banner-reason');
    if (reasonEl) reasonEl.textContent = state.reason ? ' — ' + state.reason : '';
    _updateEmergencyDuration(state.started_at);
    if (!_emergencyTickInterval) {
      _emergencyTickInterval = setInterval(
        () => _updateEmergencyDuration(state.started_at), 60000
      );
    }
    // Hide the sidebar enter button while active
    const enterBtn = document.getElementById('sidebar-emergency-btn');
    if (enterBtn) enterBtn.hidden = true;
  } else {
    banner.classList.add('is-hidden');
    body.classList.remove('emergency-mode');
    if (_emergencyTickInterval) { clearInterval(_emergencyTickInterval); _emergencyTickInterval = null; }
    const enterBtn = document.getElementById('sidebar-emergency-btn');
    if (enterBtn) enterBtn.hidden = false;
  }
}

function _updateEmergencyDuration(started_at) {
  const el = document.getElementById('emergency-banner-duration');
  if (!el || !started_at) return;
  try {
    const ms = Date.now() - new Date(started_at).getTime();
    const mins = Math.floor(ms / 60000);
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    el.textContent = ' · ' + (h > 0 ? `${h}h ${m}m` : `${m}m`);
  } catch (_) {}
}

async function loadEmergencyState() {
  try {
    const state = await apiFetch('/api/emergency/status');
    _applyEmergencyState(state);
  } catch (_) {}
}

// Hydrate emergency state on page load so banner survives reloads
document.addEventListener('DOMContentLoaded', () => {
  loadEmergencyState();
});

/* ─── Kit Builder Wizard (v7.3.0) ─── */
let _kitBuilderLastPlan = null;

function openKitBuilder() {
  const modal = document.getElementById('kit-builder-modal');
  if (!modal) return;
  modal.classList.remove('is-hidden');
  // Show inputs step; hide results
  document.getElementById('kit-builder-step-inputs')?.classList.remove('is-hidden');
  document.getElementById('kit-builder-step-results')?.classList.add('is-hidden');
  document.getElementById('kit-mission')?.focus();
}

function closeKitBuilder() {
  const modal = document.getElementById('kit-builder-modal');
  if (modal) modal.classList.add('is-hidden');
}

function resetKitBuilder() {
  document.getElementById('kit-builder-step-inputs')?.classList.remove('is-hidden');
  document.getElementById('kit-builder-step-results')?.classList.add('is-hidden');
}

async function generateKitPlan() {
  const payload = {
    mission: document.getElementById('kit-mission')?.value || 'bug_out',
    climate: document.getElementById('kit-climate')?.value || 'temperate',
    people: parseInt(document.getElementById('kit-people')?.value, 10) || 1,
    duration_hrs: parseInt(document.getElementById('kit-duration')?.value, 10) || 72,
    mobility: document.getElementById('kit-mobility')?.value || 'mixed',
  };
  try {
    const plan = await apiPost('/api/kit-builder/plan', payload);
    _kitBuilderLastPlan = plan;
    renderKitPlan(plan);
    document.getElementById('kit-builder-step-inputs')?.classList.add('is-hidden');
    document.getElementById('kit-builder-step-results')?.classList.remove('is-hidden');
  } catch (e) {
    toast(e?.data?.error || 'Could not generate kit plan', 'error');
  }
}

function renderKitPlan(plan) {
  const summary = document.getElementById('kit-builder-summary');
  const items = document.getElementById('kit-builder-items');
  if (!summary || !items) return;
  const t = plan.totals || {};
  const p = plan.params || {};
  const missionLabel = {
    bug_out: 'Bug-out', shelter_in_place: 'Shelter in place',
    vehicle: 'Vehicle / EDC', medical_bag: 'Medical bag'
  }[p.mission] || p.mission;
  summary.innerHTML = `
    <div class="kit-builder-summary-header">
      <div><strong>${escapeHtml(missionLabel)}</strong> · ${p.people} people · ${Math.round((p.duration_hrs || 0) / 24 * 10) / 10} days · ${escapeHtml(p.climate)} climate · ${escapeHtml(p.mobility)}</div>
    </div>
    <div class="kit-builder-stats">
      <div class="kit-stat"><span class="kit-stat-num">${t.item_count || 0}</span><span class="kit-stat-label">Items</span></div>
      <div class="kit-stat"><span class="kit-stat-num">${t.weight_kg || 0}</span><span class="kit-stat-label">kg total</span></div>
      <div class="kit-stat kit-stat-gap"><span class="kit-stat-num">${t.gaps || 0}</span><span class="kit-stat-label">Gaps</span></div>
      <div class="kit-stat kit-stat-partial"><span class="kit-stat-num">${t.partial || 0}</span><span class="kit-stat-label">Partial</span></div>
      <div class="kit-stat kit-stat-have"><span class="kit-stat-num">${t.have || 0}</span><span class="kit-stat-label">Have</span></div>
    </div>`;
  applyKitFilter();
}

function applyKitFilter() {
  if (!_kitBuilderLastPlan) return;
  const showGap = document.getElementById('kit-filter-gap')?.checked;
  const showPartial = document.getElementById('kit-filter-partial')?.checked;
  const showHave = document.getElementById('kit-filter-have')?.checked;
  const filtered = (_kitBuilderLastPlan.items || []).filter(it => {
    return (showGap && it.status === 'gap')
        || (showPartial && it.status === 'partial')
        || (showHave && it.status === 'have');
  });
  const items = document.getElementById('kit-builder-items');
  if (!items) return;
  if (!filtered.length) {
    items.innerHTML = '<div class="prep-empty-state">No items match the selected filters.</div>';
    return;
  }
  items.innerHTML = filtered.map(it => {
    const statusClass = `kit-item-${it.status}`;
    const statusLabel = it.status === 'have' ? 'Have'
                      : it.status === 'partial' ? `Partial (${it.owned_quantity})`
                      : 'Gap';
    return `<div class="kit-item ${statusClass}">
      <div class="kit-item-main">
        <div class="kit-item-name">${escapeHtml(it.name)}</div>
        <div class="kit-item-reason">${escapeHtml(it.reason || '')}</div>
      </div>
      <div class="kit-item-qty">${it.quantity} ${escapeHtml(it.unit || '')}</div>
      <div class="kit-item-weight">${it.weight_kg || 0} kg</div>
      <div class="kit-item-status">${statusLabel}</div>
    </div>`;
  }).join('');
}

async function commitKitToShopping() {
  if (!_kitBuilderLastPlan) return;
  // Commit only gap + partial items — don't re-shop things already owned
  const gaps = (_kitBuilderLastPlan.items || []).filter(it => it.status !== 'have');
  if (!gaps.length) {
    toast('No gaps to add', 'info');
    return;
  }
  try {
    const res = await apiPost('/api/kit-builder/add-to-shopping-list', { items: gaps });
    toast(`Added ${res.added || 0} items to shopping list`, 'success');
  } catch (e) {
    toast('Failed to add items to shopping list', 'error');
  }
}

/* ─── Template Quick Entry ─── */
let _templateDropdownOpen = false;
async function toggleTemplateDropdown() {
  const dd = document.getElementById('template-dropdown');
  _templateDropdownOpen = !_templateDropdownOpen;
  dd.style.display = _templateDropdownOpen ? 'block' : 'none';
  if (_templateDropdownOpen) {
    try {
      const templates = await safeFetch('/api/templates/inventory', {}, []);
      const el = document.getElementById('template-dropdown-items');
      if (!templates.length) { el.innerHTML = '<div class="prep-dropdown-empty">No templates available.</div>'; return; }
      el.innerHTML = templates.map(t => `<button type="button" class="prep-template-btn" data-prep-action="apply-inventory-template" data-template-name="${escapeAttr(t.name)}">${escapeHtml(t.name)} <span class="prep-template-meta">${t.items_count||''} items</span></button>`).join('');
    } catch(e) { document.getElementById('template-dropdown-items').innerHTML = '<div class="prep-dropdown-empty">Could not load templates.</div>'; }
  }
}

async function applyInventoryTemplate(name) {
  try {
    await apiPost('/api/templates/inventory/apply', { template_name: name });
    toast('Template "' + name + '" applied', 'success');
    document.getElementById('template-dropdown').style.display = 'none';
    _templateDropdownOpen = false;
    loadInventory();
  } catch(e) { toast('Failed to apply template', 'error'); }
}

/* ─── Comms Status Board ─── */
async function loadCommsStatusBoard() {
  try {
    const data = await safeFetch('/api/comms/status-board', {}, null);
    if (!data) throw new Error('status board unavailable');
    const el = document.getElementById('comms-board-content');
    const channels = data.channels || [];
    const peersOnline = data.federation_peers_online || 0;
    if (!channels.length && !peersOnline) {
      el.innerHTML = prepEmptyBlock('No active communication channels detected.');
      return;
    }
    const statusColors = {active:'var(--green)',degraded:'var(--orange)',offline:'var(--red)',unknown:'var(--text-muted)'};
    el.innerHTML = `
      <div class="prep-status-grid">
        ${channels.map(ch => `<div class="prep-status-card">
          <div class="prep-status-card-head">
            <span class="prep-status-dot" style="--prep-status-color:${statusColors[ch.status]||statusColors.unknown};"></span>
            <span class="prep-status-name">${escapeHtml(ch.name||ch.type||'Channel')}</span>
          </div>
          <div class="prep-status-meta">${escapeHtml(ch.type||'')}</div>
          <div class="prep-status-footnote">${ch.last_message ? 'Last: ' + timeAgo(ch.last_message) : 'No messages'}</div>
        </div>`).join('')}
      </div>
      <div class="prep-status-footer">Federation peers online: <strong>${peersOnline}</strong></div>
    `;
  } catch(e) {
    document.getElementById('comms-board-content').innerHTML = prepEmptyBlock('Could not load comms status.');
  }
}

/* ─── AI SITREP ─── */
async function generateAISitrep() {
  toast('Generating AI SITREP...', 'info');
  try {
    const data = await apiPost('/api/ai/sitrep', {});
    const content = data.sitrep || data.content || data.text || JSON.stringify(data, null, 2);
    document.getElementById('ai-sitrep-content').textContent = content;
    const modal = document.getElementById('ai-sitrep-modal');
    modal.style.display = 'flex';
    if (typeof NomadModal !== 'undefined') NomadModal.open(modal, {
      onClose: () => { modal.style.display = 'none'; },
    });
  } catch(e) { toast('Failed to generate AI SITREP', 'error'); }
}

/* ─── AI Memory Panel ─── */
function toggleAIMemoryPanel() {
  const panel = document.getElementById('ai-memory-panel');
  const toggle = document.getElementById('ai-memory-toggle-btn');
  const isOpen = panel.style.display !== 'none';
  panel.style.display = isOpen ? 'none' : 'block';
  if (toggle) toggle.setAttribute('aria-expanded', String(!isOpen));
  if (!isOpen) loadAIMemory();
}

function renderSettingsInlineStatus(message, tone='muted') {
  return `<div class="settings-inline-status settings-inline-status-${tone}">${escapeHtml(message)}</div>`;
}

function renderAIMemoryFacts(facts) {
  return facts.map(f => `<div class="ai-memory-entry">
      <span class="ai-memory-fact">${escapeHtml(f.fact || f.content || f.text)}</span>
      <button class="btn btn-sm btn-danger ai-memory-delete" type="button" data-ai-memory-delete="${f.id}" aria-label="Delete memory fact">x</button>
    </div>`).join('');
}

function renderSystemHealthChecks(checks) {
  return `<div class="settings-check-list">${checks.map(c => {
    const passed = c.status === 'pass';
    return `<div class="settings-check-row">
      <span class="settings-check-icon ${passed ? 'is-pass' : 'is-fail'}" aria-hidden="true">${passed ? '&#10003;' : '&#10007;'}</span>
      <div class="settings-check-copy">
        <div class="settings-check-name">${escapeHtml(c.name || c.check)}</div>
        <div class="settings-check-meta">${escapeHtml(c.message || c.detail || '')}</div>
      </div>
    </div>`;
  }).join('')}</div>`;
}

function renderSerialPortRows(ports) {
  return ports.map(p => {
    const portName = String(p.port || p.name || '');
    const stateTone = p.connected ? 'is-online' : 'is-offline';
    return `<div class="settings-port-row">
      <span class="settings-port-indicator ${stateTone}" aria-hidden="true"></span>
      <div class="settings-port-main">
        <div class="settings-port-name">${escapeHtml(portName)}</div>
        <div class="settings-port-meta">${escapeHtml(p.description || 'No device description reported.')}</div>
      </div>
      ${p.last_reading ? `<span class="settings-port-reading">Last: ${escapeHtml(String(p.last_reading))}</span>` : ''}
      <span class="settings-port-spacer"></span>
      <button class="btn btn-sm ${p.connected ? 'btn-danger' : 'btn-primary'}" type="button" data-serial-action="${p.connected ? 'disconnect' : 'connect'}" data-serial-port="${escapeHtml(portName)}">${p.connected ? 'Disconnect' : 'Connect'}</button>
    </div>`;
  }).join('');
}

async function loadAIMemory() {
  try {
    const facts = await apiFetch('/api/ai/memory');
    const el = document.getElementById('ai-memory-list');
    if (!facts || !facts.length) { el.innerHTML = renderSettingsInlineStatus('No memory facts stored.', 'muted'); return; }
    el.innerHTML = renderAIMemoryFacts(facts);
  } catch(e) { document.getElementById('ai-memory-list').innerHTML = renderSettingsInlineStatus('Could not load memory.', 'error'); }
}

async function addAIMemory() {
  const input = document.getElementById('ai-memory-input');
  const fact = input.value.trim();
  if (!fact) return;
  try {
    await apiPost('/api/ai/memory', { fact });
    input.value = '';
    toast('Memory fact added', 'success');
    loadAIMemory();
  } catch(e) { toast('Failed to add memory', 'error'); }
}

async function deleteAIMemory(id) {
  if (!confirm('Delete this AI memory?')) return;
  try {
    await apiDelete(`/api/ai/memory/${id}`);
    toast('Memory deleted', 'info');
    loadAIMemory();
  } catch(e) { toast('Failed to delete memory', 'error'); }
}

/* ─── System Health ─── */
async function runSelfTest() {
  const el = document.getElementById('system-health-results');
  el.innerHTML = renderSettingsInlineStatus('Running self-test…', 'muted');
  try {
    const results = await apiPost('/api/system/self-test', {});
    const checks = results.checks || results.results || [];
    if (Array.isArray(checks)) {
      el.innerHTML = renderSystemHealthChecks(checks);
    } else {
      el.innerHTML = renderSettingsInlineStatus(`Self-test complete: ${escapeHtml(JSON.stringify(results))}`, 'success');
    }
    toast('Self-test complete', 'success');
  } catch(e) { el.innerHTML = renderSettingsInlineStatus('Self-test failed.', 'error'); toast('Self-test failed', 'error'); }
}

async function runDBCheck() {
  const el = document.getElementById('system-health-results');
  el.innerHTML = renderSettingsInlineStatus('Checking database integrity…', 'muted');
  try {
    const result = await apiPost('/api/system/db-check', {});
    const ok = result.integrity === 'ok' || result.status === 'ok' || result.result === 'ok';
    el.innerHTML = renderSettingsInlineStatus(ok ? 'Database integrity check passed.' : `Database integrity issue: ${escapeHtml(JSON.stringify(result))}`, ok ? 'success' : 'error');
    toast(ok ? 'Database OK' : 'Database issue detected', ok ? 'success' : 'error');
  } catch(e) { el.innerHTML = renderSettingsInlineStatus('Database check failed.', 'error'); }
}

async function runDBVacuum() {
  const el = document.getElementById('system-health-results');
  el.innerHTML = renderSettingsInlineStatus('Optimizing database…', 'muted');
  try {
    const result = await apiPost('/api/system/db-vacuum', {});
    const detail = result.size_before ? `Size: ${result.size_before} -> ${result.size_after}` : (result.message || 'Done');
    el.innerHTML = renderSettingsInlineStatus(`Database optimized. ${detail}`, 'success');
    toast('Database optimized', 'success');
  } catch(e) { el.innerHTML = renderSettingsInlineStatus('Database optimization failed.', 'error'); }
}

/* ─── Health Dashboard ─── */
async function loadHealthDashboard() {
  const el = document.getElementById('health-dashboard-grid');
  if (!el) return;
  el.innerHTML = renderSettingsInlineStatus('Loading health data…', 'muted');
  try {
    const d = await safeFetch('/api/system/health', {}, null);
    if (!d) throw new Error('health unavailable');
    const cards = [];
    cards.push({label: 'Status', value: escapeHtml((d.status || 'unknown').replace(/_/g, ' ')), detail: d.db_integrity === 'ok' ? 'DB integrity OK' : ''});
    cards.push({label: 'Modules Active', value: String(d.modules_active || 0) + ' / ' + String(d.modules_total || 0), detail: (d.coverage_pct || 0) + '% coverage'});
    cards.push({label: 'Data Items', value: (d.total_data_items || 0).toLocaleString(), detail: 'across all tables'});
    if (d.issues && d.issues.length) {
      cards.push({label: 'Issues', value: String(d.issues.length), detail: d.issues.map(i => escapeHtml(i.msg)).join('; ')});
    } else {
      cards.push({label: 'Issues', value: '0', detail: 'no problems detected'});
    }
    // Coverage breakdown - show top populated modules
    if (d.coverage) {
      const populated = Object.values(d.coverage).filter(c => c.active).sort((a,b) => b.count - a.count).slice(0, 4);
      populated.forEach(c => {
        cards.push({label: escapeHtml(c.label), value: String(c.count), detail: ''});
      });
    }
    el.innerHTML = cards.map(c => `<div class="health-card">
      <div class="health-card-label">${c.label}</div>
      <div class="health-card-value">${c.value}</div>
      ${c.detail ? '<div class="health-card-detail">' + c.detail + '</div>' : ''}
    </div>`).join('');
  } catch(e) {
    el.innerHTML = renderSettingsInlineStatus('Failed to load health data.', 'error');
  }
}

/* ─── Sensor Charts ─── */
async function loadSensorDevices() {
  try {
    const devices = await safeFetch('/api/power/devices', {}, []);
    const sel = document.getElementById('sensor-device-select');
    const sensorDevices = (devices || []).filter(d => d.type === 'sensor' || d.has_readings);
    sel.innerHTML = '<option value="">Select sensor device...</option>' + sensorDevices.map(d => `<option value="${d.id}">${escapeHtml(d.name)}</option>`).join('');
  } catch(e) {}
}

async function loadSensorChart() {
  const deviceId = document.getElementById('sensor-device-select').value;
  const container = document.getElementById('sensor-chart-container');
  if (!deviceId) { container.style.display = 'none'; return; }
  container.style.display = 'block';
  try {
    const readings = await safeFetch(`/api/sensors/${deviceId}/history`, {}, []);
    if (!readings || !readings.length) {
      document.getElementById('sensor-chart-info').textContent = 'No readings available for this device.';
      return;
    }
    const values = readings.map(r => r.value || r.reading || 0);
    setTimeout(() => drawSparkline('sensor-history-chart', values, 'var(--accent)', { fill: true }), 50);
    const latest = readings[readings.length - 1];
    document.getElementById('sensor-chart-info').textContent = `${readings.length} readings | Latest: ${latest.value || latest.reading || 'N/A'} at ${new Date(latest.timestamp || latest.created_at).toLocaleString()}`;
  } catch(e) {
    document.getElementById('sensor-chart-info').textContent = 'Failed to load sensor data.';
  }
}

/* ─── Serial Port Manager ─── */
async function scanSerialPorts() {
  const el = document.getElementById('serial-port-list');
  el.innerHTML = renderSettingsInlineStatus('Scanning ports…', 'muted');
  try {
    const ports = await safeFetch('/api/serial/ports', {}, null);
    if (!Array.isArray(ports)) throw new Error('ports unavailable');
    if (!ports || !ports.length) { el.innerHTML = renderSettingsInlineStatus('No serial ports detected.', 'muted'); return; }
    el.innerHTML = renderSerialPortRows(ports);
  } catch(e) { el.innerHTML = renderSettingsInlineStatus('Failed to scan ports.', 'error'); }
}

async function serialConnect(port) {
  try {
    await apiPost('/api/serial/connect', { port });
    toast('Connected to ' + port, 'success');
    scanSerialPorts();
  } catch(e) { toast('Connection failed', 'error'); }
}

async function serialDisconnect(port) {
  try {
    await apiPost('/api/serial/disconnect', { port });
    toast('Disconnected from ' + port, 'info');
    scanSerialPorts();
  } catch(e) { toast('Disconnect failed', 'error'); }
}

document.addEventListener('click', e => {
  const memoryDelete = e.target.closest('[data-ai-memory-delete]');
  if (memoryDelete) {
    deleteAIMemory(memoryDelete.dataset.aiMemoryDelete);
    return;
  }
  const memoryAction = e.target.closest('[data-ai-memory-action]');
  if (memoryAction) {
    if (memoryAction.dataset.aiMemoryAction === 'toggle') toggleAIMemoryPanel();
    if (memoryAction.dataset.aiMemoryAction === 'add') addAIMemory();
    return;
  }
  const serialAction = e.target.closest('[data-serial-action]');
  if (serialAction) {
    const port = serialAction.dataset.serialPort;
    if (!port) return;
    if (serialAction.dataset.serialAction === 'connect') serialConnect(port);
    if (serialAction.dataset.serialAction === 'disconnect') serialDisconnect(port);
  }
});

const aiMemoryInput = document.getElementById('ai-memory-input');
if (aiMemoryInput) {
  aiMemoryInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addAIMemory();
    }
  });
}

/* ─── Init new features on load ─── */
setTimeout(() => {
  const activeWs = document.querySelector('.workspace-panel.active');
  if (activeWs) {
    loadTasks().catch(e => console.warn('[Init] loadTasks:', e.message));
    loadWatchSchedules().catch(e => console.warn('[Init] loadWatchSchedules:', e.message));
  }
  loadSunData().catch(e => console.warn('[Init] loadSunData:', e.message));
  loadSensorDevices().catch(e => console.warn('[Init] loadSensorDevices:', e.message));
}, 2000);

// === DTMF Tone Generator ===
const DTMF_FREQS = {'1':[697,1209],'2':[697,1336],'3':[697,1477],'A':[697,1633],'4':[770,1209],'5':[770,1336],'6':[770,1477],'B':[770,1633],'7':[852,1209],'8':[852,1336],'9':[852,1477],'C':[852,1633],'*':[941,1209],'0':[941,1336],'#':[941,1477],'D':[941,1633]};
let _dtmfCtx;
function playDTMF(key) {
  const freqs = DTMF_FREQS[key];
  if (!freqs) return;
  if (!_dtmfCtx) _dtmfCtx = new (window.AudioContext || window.webkitAudioContext)();
  const osc1 = _dtmfCtx.createOscillator();
  const osc2 = _dtmfCtx.createOscillator();
  const gain = _dtmfCtx.createGain();
  osc1.frequency.value = freqs[0];
  osc2.frequency.value = freqs[1];
  gain.gain.value = 0.2;
  osc1.connect(gain); osc2.connect(gain); gain.connect(_dtmfCtx.destination);
  osc1.start(); osc2.start();
  osc1.onended = () => { osc1.disconnect(); osc2.disconnect(); gain.disconnect(); };
  setTimeout(() => { osc1.stop(); osc2.stop(); }, 200);
  const input = document.getElementById('dtmf-sequence');
  if (input) input.value += key;
}
async function playDTMFSequence() {
  const seq = document.getElementById('dtmf-sequence')?.value || '';
  for (const ch of seq.toUpperCase()) {
    if (DTMF_FREQS[ch]) { playDTMF(ch); await new Promise(r => setTimeout(r, 300)); }
  }
}

// === NATO Phonetic Alphabet Trainer ===
const NATO_ALPHABET = {A:'Alpha',B:'Bravo',C:'Charlie',D:'Delta',E:'Echo',F:'Foxtrot',G:'Golf',H:'Hotel',I:'India',J:'Juliet',K:'Kilo',L:'Lima',M:'Mike',N:'November',O:'Oscar',P:'Papa',Q:'Quebec',R:'Romeo',S:'Sierra',T:'Tango',U:'Uniform',V:'Victor',W:'Whiskey',X:'X-ray',Y:'Yankee',Z:'Zulu','0':'Zero','1':'One','2':'Two','3':'Three','4':'Four','5':'Five','6':'Six','7':'Seven','8':'Eight','9':'Niner'};
let _phoneticScore = 0, _phoneticTotal = 0;

function startPhoneticQuiz() {
  document.getElementById('phonetic-quiz').style.display = 'block';
  document.getElementById('phonetic-reference').style.display = 'none';
  _phoneticScore = 0; _phoneticTotal = 0;
  updatePhoneticScore();
  nextPhoneticQuestion();
}

function nextPhoneticQuestion() {
  const keys = Object.keys(NATO_ALPHABET);
  const key = keys[Math.floor(Math.random() * keys.length)];
  const letterEl = document.getElementById('phonetic-letter');
  const inputEl = document.getElementById('phonetic-input');
  const resultEl = document.getElementById('phonetic-result');
  if (letterEl) letterEl.textContent = key;
  if (inputEl) { inputEl.value = ''; inputEl.focus(); }
  if (resultEl) resultEl.textContent = '';
}

function checkPhonetic() {
  const letter = document.getElementById('phonetic-letter')?.textContent || '';
  const answer = (document.getElementById('phonetic-input')?.value || '').trim().toLowerCase();
  const correct = NATO_ALPHABET[letter].toLowerCase();
  _phoneticTotal++;
  const el = document.getElementById('phonetic-result');
  if (answer === correct) {
    _phoneticScore++;
    el.innerHTML = '<span class="prep-quiz-result-good">Correct!</span>';
  } else {
    el.innerHTML = '<span class="prep-quiz-result-bad">Wrong</span> <strong class="prep-quiz-result-answer">' + NATO_ALPHABET[letter] + '</strong>';
  }
  updatePhoneticScore();
  setTimeout(nextPhoneticQuestion, 1200);
}

function updatePhoneticScore() {
  document.getElementById('phonetic-score').textContent = _phoneticScore;
  document.getElementById('phonetic-total').textContent = _phoneticTotal;
}

// Populate phonetic reference grid
document.addEventListener('DOMContentLoaded', () => {
  const el = document.getElementById('phonetic-reference');
  if (el) el.innerHTML = Object.entries(NATO_ALPHABET).map(([k,v]) => '<div class="prep-reference-card"><strong class="prep-reference-key">' + k + '</strong> <span class="prep-reference-value">' + v + '</span></div>').join('');
});

// Hydrate Voice Copilot + Home Location settings rows
document.addEventListener('DOMContentLoaded', () => {
  if (typeof hydrateVoicePrefs === 'function') hydrateVoicePrefs();
  if (typeof hydrateHomeLocation === 'function') hydrateHomeLocation();
  // Hide hands-free button on browsers without STT or TTS (Linux WebKitGTK
  // often lacks voices entirely — a button that toasts "not supported" on
  // every click is worse than no button).
  const handsfreeBtn = document.getElementById('copilot-handsfree-btn');
  if (handsfreeBtn && (typeof window.NomadVoiceCopilot === 'undefined' || !window.NomadVoiceCopilot.isSupported())) {
    handsfreeBtn.hidden = true;
  }
});

// === Note Backlinks ===
async function loadNoteBacklinks(noteId) {
  const el = document.getElementById('note-backlinks-list');
  const wrap = document.getElementById('note-backlinks');
  if (!el || !wrap) return;
  const links = await safeFetch('/api/notes/' + noteId + '/backlinks', {}, []);
  if (!links.length) { wrap.style.display = 'none'; return; }
  wrap.style.display = 'block';
  el.innerHTML = links.map(l => '<a href="#" class="link-accent note-backlink-link" data-note-action="select-note" data-note-id="' + l.id + '">' + escapeHtml(l.title) + '</a>').join('');
}

// === Expiring Medications ===
async function loadExpiringMeds() {
  const el = document.getElementById('expiring-meds-list');
  if (!el) return;
  const meds = await safeFetch('/api/medical/expiring-meds', {}, []);
  if (!meds.length) { el.innerHTML = '<div class="prep-status-banner prep-expiring-clear">No medications expiring within 90 days.</div>'; return; }
  el.innerHTML = meds.map(m => {
    const color = m.expired ? 'var(--red)' : (m.days_until < 30 ? 'var(--orange)' : 'var(--text-dim)');
    const label = m.expired ? 'EXPIRED' : m.days_until + 'd left';
    return `<div class="prep-record-item">
      <div>
        <div class="prep-record-main"><strong>${escapeHtml(m.name)}</strong> <span class="prep-record-meta">(${m.quantity} ${escapeHtml(m.unit)})</span></div>
        <div class="prep-record-meta">Expiration date: ${escapeHtml(m.expiration)}</div>
      </div>
      <span class="prep-inline-pill" style="--prep-pill-tone:${color};">${label}</span>
    </div>`;
  }).join('');
}

// === Vital Signs Trend Chart ===
async function loadVitalsTrend(patientId) {
  const panel = document.getElementById('vitals-trend-panel');
  const canvas = document.getElementById('vitals-canvas');
  if (!panel || !canvas) return;
  const data = await safeFetch('/api/medical/vitals-trend/' + patientId, {}, []);
  if (data.length < 2) { panel.style.display = 'none'; return; }
  panel.style.display = 'block';

  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  canvas.width = canvas.offsetWidth * dpr;
  canvas.height = 180 * dpr;
  ctx.scale(dpr, dpr);
  const dw = canvas.offsetWidth, dh = 180;
  ctx.clearRect(0, 0, dw, dh);

  const colors = {pulse:'#f44336', bp_systolic:'#2196f3', spo2:'#4caf50', temp_f:'#ff9800'};
  const labels = {pulse:'HR', bp_systolic:'BP Sys', spo2:'SpO2', temp_f:'Temp'};

  let legendX = 10;
  for (const [key, color] of Object.entries(colors)) {
    const vals = data.map(d => d[key]).filter(v => v != null);
    if (vals.length < 2) continue;
    const min = Math.min(...vals) - 5;
    const max = Math.max(...vals) + 5;
    const range = max - min || 1;

    ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.beginPath();
    let idx = 0;
    data.forEach((d, i) => {
      if (d[key] == null) return;
      const x = 10 + (i / (data.length - 1)) * (dw - 20);
      const y = 20 + ((max - d[key]) / range) * (dh - 40);
      if (idx === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      idx++;
    });
    ctx.stroke();

    ctx.fillStyle = color; ctx.font = '10px system-ui';
    ctx.fillRect(legendX, dh - 12, 12, 3);
    ctx.fillText(labels[key], legendX + 16, dh - 8);
    legendX += ctx.measureText(labels[key]).width + 30;
  }
}

/* ─── NomadI18n + loadLanguageSelector: loaded from /static/js/i18n.js ─── */

// PWA Service Worker
// In the desktop app, stale WebView2 service-worker caches can leave the UI on a
// mismatched frontend bundle after upgrades. Keep SW support for real browsers,
// but actively remove it inside pywebview.
async function configureNomadServiceWorker() {
  if (!('serviceWorker' in navigator)) return;
  const isDesktopWebview = !!window.pywebview;
  if (isDesktopWebview) {
    try {
      const registrations = await navigator.serviceWorker.getRegistrations();
      await Promise.all(registrations.map(reg => reg.unregister()));
      if ('caches' in window) {
        const cacheKeys = await caches.keys();
        const nomadCaches = cacheKeys.filter(key => key.startsWith('nomad-'));
        await Promise.all(nomadCaches.map(key => caches.delete(key)));
      }
      if (navigator.serviceWorker.controller && !sessionStorage.getItem('nomad-desktop-sw-reset')) {
        sessionStorage.setItem('nomad-desktop-sw-reset', '1');
        window.location.reload();
      }
    } catch (_) {}
    return;
  }
  navigator.serviceWorker.register('/static/sw.js').catch(() => {});
}

configureNomadServiceWorker();

// Initialize IndexedDB offline sync
try { OfflineSync.startAutoSync(300000); } catch(e) { console.warn('OfflineSync init failed:', e); }

// Initialize battery-aware throttling
BatteryManager.init();

// Initialize internationalization
NomadI18n.init();

// Restore deep-linked workspace state after the shell is ready.
setTimeout(async () => {
  if (typeof hydrateWorkspaceResumeState === 'function') {
    try {
      await hydrateWorkspaceResumeState();
    } catch (error) {
      console.warn('Workspace memory hydration failed:', error);
    }
  }
  if (typeof restoreWorkspaceUrlState === 'function') restoreWorkspaceUrlState();
}, 120);

// Check portable mode
safeFetch('/api/system/portable-mode', {}, null).then(d=>{if(d?.portable){const el=document.getElementById('portable-indicator');if(el)el.style.display='';}}).catch(()=>{});

/* ─── NomadEvents: loaded from /static/js/events.js ─── */

/* ─── Accessibility: Keyboard Navigation Enhancements ─── */
const commandPaletteOverlay = document.getElementById('command-palette-overlay');
if (commandPaletteOverlay) {
  commandPaletteOverlay.addEventListener('click', e => {
    if (e.target === commandPaletteOverlay) toggleCommandPalette(false);
  });
}

const shortcutsOverlay = document.getElementById('shortcuts-overlay');
if (shortcutsOverlay) {
  shortcutsOverlay.addEventListener('click', e => {
    if (e.target === shortcutsOverlay) toggleShortcutsHelp(false);
  });
}

// Make clickable divs with onclick keyboard-accessible
document.querySelectorAll('.customize-sortable-item[onclick], .customize-theme-card[onclick]').forEach(item => {
  if (!item.getAttribute('tabindex')) item.setAttribute('tabindex', '0');
  if (!item.getAttribute('role')) item.setAttribute('role', 'button');
  item.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); item.click(); }
  });
});
