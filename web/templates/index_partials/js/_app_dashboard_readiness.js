/* ─── Sparkline Chart Renderer ─── */
function drawSparkline(canvasId, data, color, opts = {}) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !data.length) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.width = canvas.offsetWidth * dpr;
  const h = canvas.height = canvas.offsetHeight * dpr;
  ctx.scale(dpr, dpr);
  const cw = canvas.offsetWidth, ch = canvas.offsetHeight;
  ctx.clearRect(0, 0, cw, ch);
  const min = opts.min ?? Math.min(...data);
  const max = opts.max ?? Math.max(...data);
  const range = max - min || 1;
  const pad = 2;
  const stepX = (cw - pad * 2) / Math.max(data.length - 1, 1);
  // Gradient fill
  if (opts.fill !== false) {
    const grad = ctx.createLinearGradient(0, 0, 0, ch);
    grad.addColorStop(0, color + '30');
    grad.addColorStop(1, color + '05');
    ctx.beginPath();
    ctx.moveTo(pad, ch);
    data.forEach((v, i) => ctx.lineTo(pad + i * stepX, ch - pad - ((v - min) / range) * (ch - pad * 2)));
    ctx.lineTo(pad + (data.length - 1) * stepX, ch);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();
  }
  // Line
  ctx.beginPath();
  data.forEach((v, i) => {
    const x = pad + i * stepX;
    const y = ch - pad - ((v - min) / range) * (ch - pad * 2);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.lineJoin = 'round';
  ctx.stroke();
  // Current value dot
  if (data.length > 1) {
    const lastX = pad + (data.length - 1) * stepX;
    const lastY = ch - pad - ((data[data.length - 1] - min) / range) * (ch - pad * 2);
    ctx.beginPath();
    ctx.arc(lastX, lastY, 2.5, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
  }
}

// Load sparkline data for dashboard widgets
async function loadDashboardSparklines() {
  const powerSparkline = document.getElementById('spark-power');
  if (powerSparkline) {
    const powerData = await safeFetch('/api/power/history?period=24h', {}, []);
    if (powerData.length > 1) {
      const socData = powerData.map(r => r.battery_soc || 0);
      setTimeout(() => drawSparkline('spark-power', socData, '#f9a825', {min: 0, max: 100}), 100);
    }
  }
}

/* ─── Getting Started Checklist ─── */
function updateGettingStartedPresentation(data) {
  const onboardingIncomplete = window.NOMAD_FIRST_RUN_COMPLETE === false;
  const kicker = document.getElementById('gs-panel-kicker');
  const note = document.getElementById('gs-onboarding-note');
  const resumeBtn = document.getElementById('gs-resume-setup-btn');

  if (kicker) {
    kicker.textContent = onboardingIncomplete ? 'CONTINUE SETUP' : 'GETTING STARTED';
  }
  if (resumeBtn) {
    setShellVisibility(resumeBtn, onboardingIncomplete);
  }
  if (!note) return;

  if (onboardingIncomplete) {
    note.innerHTML = `Guided setup is still the fastest way to finish your offline workspace. Resume setup to choose storage, install tools, and download content without hunting through tabs.`;
    setShellVisibility(note, true);
    return;
  }

  note.textContent = '';
  setShellVisibility(note, false);
}

async function loadGettingStarted() {
  const panel = document.getElementById('getting-started-panel');
  if (!panel) return;
  const data = await safeFetch('/api/system/getting-started', {}, null);
  if (!data) return;
  updateGettingStartedPresentation(data);
  // Hide if all steps complete
  if (data.pct >= 100 && window.NOMAD_FIRST_RUN_COMPLETE !== false) { panel.style.display = 'none'; return; }
  panel.style.display = '';
  const progressTextEl = document.getElementById('gs-progress-text');
  const el = document.getElementById('gs-steps');
  if (!progressTextEl || !el) return;
  progressTextEl.textContent = `${data.completed}/${data.total} complete (${data.pct}%)`;
  el.innerHTML = data.steps.map((s, i) => {
    const borderColor = s.done ? 'var(--green)' : 'var(--border)';
    const attrs = s.done ? '' : ' role="button" tabindex="0" data-prep-action="gs-navigate" data-gs-step-index="' + i + '"';
    return '<div class="gs-step-row gs-step-row-shell ' + (s.done ? 'gs-step-row-shell-complete' : 'gs-step-row-shell-open') + '" style="--gs-step-tone:' + borderColor + ';"' + attrs + '>' +
      '<span class="gs-step-row-glyph">' + (s.done ? '&#9745;' : '&#9744;') + '</span>' +
      '<div class="gs-step-row-copy"><div class="gs-step-row-title ' + (s.done ? 'gs-step-row-title-complete' : '') + '">' + escapeHtml(s.title) + '</div>' +
      '<div class="gs-step-row-desc">' + escapeHtml(s.desc) + '</div></div></div>';
  }).join('');
  // Store step data for navigation
  window._gsSteps = data.steps;
}

function gsNavigate(stepIndex) {
  const steps = window._gsSteps;
  if (!steps || !steps[stepIndex]) return;
  const s = steps[stepIndex];
  const tabEl = document.querySelector('.tab[data-tab="' + s.action + '"]');
  if (tabEl) tabEl.click();
  if (s.sub) setTimeout(function() { switchPrepSub(s.sub); }, 200);
}

/* ─── Survival Needs Overview ─── */
async function loadNeedsOverview() {
  const el = document.getElementById('needs-grid');
  if (!el) return;
  const data = await safeFetch('/api/needs', {}, {});
  if (!data || !Object.keys(data).length) { el.innerHTML = ''; return; }
  el.innerHTML = Object.entries(data).map(([id, n]) => {
    const safeColor = /^#[0-9a-fA-F]{3,8}$/.test(n.color) ? n.color : 'var(--accent)';
    const safeId = escapeAttr(id);
    return `
    <div class="need-card" style="--need-tone:${safeColor};" role="button" tabindex="0" data-shell-action="open-needs-detail" data-need-id="${safeId}">
      <div class="need-card-head">
        <span class="need-card-icon">${escapeHtml(n.icon)}</span>
        <span class="need-card-title">${escapeHtml(n.label)}</span>
      </div>
      <div class="need-card-badges">
        ${n.inventory > 0 ? `<span class="need-badge">${n.inventory} supplies</span>` : ''}
        ${n.contacts > 0 ? `<span class="need-badge">${n.contacts} contacts</span>` : ''}
        ${n.books > 0 ? `<span class="need-badge">${n.books} books</span>` : ''}
        ${n.guides > 0 ? `<span class="need-badge">${n.guides} guides</span>` : ''}
        ${n.total === 0 ? `<span class="need-badge need-badge-danger">NO COVERAGE</span>` : ''}
      </div>
      <div class="need-progress"><div class="need-progress-fill" style="width:${Math.min((n.total||0) * 10, 100)}%;background:${(n.total||0) >= 6 ? 'var(--green)' : (n.total||0) >= 3 ? 'var(--orange)' : 'var(--red)'};"></div></div>
    </div>`;
  }).join('');
}

async function openNeedsDetail(needId) {
  const modal = document.getElementById('needs-detail-modal');
  const title = document.getElementById('needs-detail-title');
  const body = document.getElementById('needs-detail-body');
  modal.style.display = 'flex';
  title.textContent = 'Loading...';
  body.innerHTML = '<div class="need-detail-state">Loading cross-module data...</div>';

  const data = await safeFetch(`/api/needs/${needId}`, {}, null);
  if (!data) { body.innerHTML = '<div class="need-detail-state need-detail-state-error">Failed to load</div>'; return; }

  title.innerHTML = `${data.need.icon} ${escapeHtml(data.need.label)}`;

  let html = '';
  // Inventory section
  if (data.inventory.length) {
    html += `<div class="need-section">
      <div class="need-section-title">SUPPLIES (${data.inventory.length})</div>
      <div class="need-item-pill-list">
        ${data.inventory.map(i => `<span class="need-item-pill">${escapeHtml(i.name)} <strong>${i.quantity} ${i.unit||''}</strong></span>`).join('')}
      </div>
    </div>`;
  }
  // Contacts section
  if (data.contacts.length) {
    html += `<div class="need-section">
      <div class="need-section-title">TEAM (${data.contacts.length})</div>
      ${data.contacts.map(c => `<div class="need-item-row"><strong>${escapeHtml(c.name)}</strong> <span class="need-item-meta">— ${escapeHtml(c.role||'')} ${c.skills ? '&middot; ' + escapeHtml(c.skills) : ''}</span></div>`).join('')}
    </div>`;
  }
  // Books section
  if (data.books.length) {
    html += `<div class="need-section">
      <div class="need-section-title">REFERENCE BOOKS (${data.books.length})</div>
      ${data.books.map(b => `<div class="need-item-row">${escapeHtml(b.title)} <span class="need-item-meta need-item-meta-compact">— ${escapeHtml(b.author||'')}</span></div>`).join('')}
    </div>`;
  }
  // Decision guides
  if (data.guides.length) {
    html += `<div class="need-section">
      <div class="need-section-title">DECISION GUIDES (${data.guides.length})</div>
      ${data.guides.map(g => `<button type="button" class="need-item-row need-item-link" data-tab-target="preparedness" data-prep-sub="guides" data-guide-start="${escapeAttr(g.id)}" data-close-needs-detail>${escapeHtml(g.title)} &#8594;</button>`).join('')}
    </div>`;
  }
  if (!html) html = '<div class="need-detail-state">No data matched this need. Add supplies, contacts, or books to see them here.</div>';
  body.innerHTML = html;
}

function closeNeedsDetail() {
  document.getElementById('needs-detail-modal').style.display = 'none';
}

/* ─── AI Copilot ─── */
function updateCopilotButtons() {
  const el = document.getElementById('copilot-quick-btns');
  if (!el) return;
  const mode = _dashboardMode || 'command';
  const modeQuestions = {
    command: [
      {q: 'What needs attention today?', label: 'SITREP'},
      {q: 'What am I low on?', label: 'LOW STOCK'},
      {q: 'How many days of water do I have?', label: 'WATER'},
      {q: 'Who is our medic and what medical supplies do we have?', label: 'MEDICAL'},
      {q: 'Summarize our current threat posture and active alerts', label: 'THREATS'},
    ],
    homestead: [
      {q: 'What should I plant this month?', label: 'PLANTING'},
      {q: 'How is my garden doing? What was my last harvest?', label: 'HARVEST'},
      {q: 'What equipment needs service?', label: 'EQUIPMENT'},
      {q: 'How much fuel do I have and when does it expire?', label: 'FUEL'},
      {q: 'What food items are expiring soon?', label: 'EXPIRING'},
    ],
    minimal: [
      {q: 'What needs attention today?', label: 'TODAY'},
      {q: 'What am I low on?', label: 'LOW STOCK'},
      {q: 'Who are my emergency contacts?', label: 'CONTACTS'},
    ],
  };
  const questions = modeQuestions[mode] || modeQuestions.command;
  el.innerHTML = questions.map(q =>
    `<button class="btn btn-sm copilot-quick-btn" type="button" data-shell-action="ask-copilot" data-copilot-question="${escapeAttr(q.q)}">${escapeHtml(q.label)}</button>`
  ).join('');
}

function dismissCopilotAnswer() {
  const answerEl = document.getElementById('copilot-answer');
  if (answerEl) { answerEl.classList.remove('show'); answerEl.innerHTML = ''; }
  const btn = document.getElementById('copilot-dismiss');
  if (btn) btn.style.display = 'none';
}

async function askCopilot(question) {
  const input = document.getElementById('copilot-input');
  const answerEl = document.getElementById('copilot-answer');
  if (!answerEl) return;
  if (!question) question = input?.value?.trim();
  if (!question) return;
  if (input) input.value = '';
  answerEl.classList.add('show');
  const dismissBtn = document.getElementById('copilot-dismiss');
  if (dismissBtn) dismissBtn.style.display = 'block';
  answerEl.innerHTML = '<div class="copilot-answer-shell"><span class="copilot-answer-state">Thinking…</span></div>';
  // Voice turn flag is set by the single-shot mic button in voiceInput();
  // hands-free mode drives its own TTS from NomadVoiceCopilot.
  const isVoiceTurn = !!window._copilotVoiceTurn;
  window._copilotVoiceTurn = false;
  try {
    const data = await apiPost('/api/ai/quick-query', {question});
    const answer = data.answer || 'No answer generated.';
    answerEl.innerHTML = `<div class="copilot-answer-shell"><div class="copilot-answer-body">${escapeHtml(answer)}</div>
      ${data.data_sources?.length ? `<div class="copilot-source-row"><span class="copilot-source-label">Sources:</span>${data.data_sources.map(s => `<span class="copilot-source-chip">${escapeHtml(s)}</span>`).join('')}</div>` : ''}</div>`;
    // Speak the answer if the question was dictated via the single-shot mic.
    // Hands-free mode uses its own speak path (and ignores this flag since
    // it calls askCopilot directly without setting _copilotVoiceTurn).
    if (isVoiceTurn && window.NomadSpeech && window.NomadSpeech.isSupported()) {
      window.NomadSpeech.speak(answer, { interrupt: true });
    }
  } catch(e) {
    answerEl.innerHTML = `<span class="copilot-answer-error">${escapeHtml(e?.data?.error || 'Failed to reach AI service')}</span>`;
  }
}

async function loadSuggestedActions() {
  const el = document.getElementById('copilot-suggestions');
  if (!el) return;
  const data = await safeFetch('/api/ai/suggested-actions', {}, {suggestions: []});
  el.hidden = false;
  if (!data.suggestions.length) {
    el.innerHTML = '<div class="copilot-suggestion-empty">&#10003; All clear — no actions needed</div>';
    return;
  }
  const typeClasses = {critical: 'copilot-suggestion-icon-critical', urgent: 'copilot-suggestion-icon-urgent', warning: 'copilot-suggestion-icon-warning'};
  const typeIcons = {critical: '&#9888;', urgent: '&#9650;', warning: '&#8226;'};
  el.innerHTML = `<div class="copilot-suggestion-list">${data.suggestions.map(s => `
    <div class="copilot-suggestion-item">
      <span class="copilot-suggestion-icon ${typeClasses[s.type] || 'copilot-suggestion-icon-warning'}">${typeIcons[s.type] || '&#8226;'}</span>
      <span class="copilot-suggestion-copy">${escapeHtml(s.action)}</span>
    </div>`).join('')}</div>`;
}

/* ─── Dashboard Widget Configuration ─── */
window._widgetConfig = null;

async function loadWidgetConfig() {
  const workspace = document.getElementById('dash-workspace');
  const liveDashboard = document.getElementById('live-dashboard');
  const widgetContainer = document.getElementById('dash-live-widgets');
  if (!workspace && !liveDashboard && !widgetContainer) {
    window._widgetConfig = null;
    return window._widgetConfig;
  }
  const data = await safeFetch('/api/dashboard/widgets', {}, null);
  window._widgetConfig = data?.widgets || null;
  return window._widgetConfig;
}

function renderDashboardWidgets() {
  if (!window._widgetConfig || !_liveDashData) return;
  const el = document.getElementById('live-dashboard');
  if (!el) return;
  const mode = _dashboardMode || 'command';

  // We rely on renderLiveDashboard to create the HTML, then we reorder
  // First render normally so all widgets exist
  renderLiveDashboard(_liveDashData);

  // Now reorder: grab all .live-widget elements and sort by config
  const widgets = Array.from(el.querySelectorAll('.live-widget'));
  if (!widgets.length) return;

  // Build a map of widget label text -> element
  const labelMap = {};
  widgets.forEach(w => {
    const label = w.querySelector('.live-widget-label');
    if (label) {
      const text = label.textContent.trim().toUpperCase();
      labelMap[text] = w;
    }
  });

  // Map config IDs to widget labels
  const idToLabel = {
    'weather': 'WEATHER', 'inventory': 'SUPPLIES', 'power': 'POWER',
    'medical': 'MEDICAL', 'comms': 'COMMS', 'tasks': 'TASKS',
    'alerts': 'ALERTS', 'contacts': 'TEAM', 'solar': 'SUN',
    'map': 'MAP', 'status': 'SITUATION', 'burn-rate': 'CRITICAL SUPPLY',
    'security': 'SECURITY', 'garden': 'FOOD PRODUCTION', 'fuel': 'FUEL RESERVES',
    'sun': 'SUN',
  };

  // Sort config by order
  const sorted = [...window._widgetConfig].sort((a, b) => a.order - b.order);

  // Clear grid and re-add in config order
  el.innerHTML = '';
  sorted.forEach(cfg => {
    if (!cfg.visible) return;
    const label = idToLabel[cfg.id];
    if (label && labelMap[label]) {
      const widget = labelMap[label];
      // Apply size class
      widget.classList.remove('widget-size-normal', 'widget-size-wide', 'widget-size-full');
      widget.classList.add('widget-size-' + (cfg.size || 'normal'));
      widget.setAttribute('data-widget-id', cfg.id);
      el.appendChild(widget);
    }
  });

  // Add any remaining widgets not in config (mode-specific ones)
  Object.values(labelMap).forEach(w => {
    if (!w.parentElement) el.appendChild(w);
  });
}

function openWidgetManager() {
  const modal = document.getElementById('widget-config-modal');
  if (!modal) return;
  modal.style.display = 'flex';

  // Ensure we have config
  const renderList = (config) => {
    const list = document.getElementById('widget-config-list');
    if (!list) return;
    const sorted = [...config].sort((a, b) => a.order - b.order);
    list.innerHTML = sorted.map((w, i) => `
      <div class="widget-config-item" draggable="true" data-widget-idx="${i}" data-widget-id="${w.id}">
        <span class="drag-handle widget-drag-handle" title="Drag to reorder" aria-label="Drag to reorder"></span>
        <span class="widget-config-icon">${escapeHtml(w.icon || '')}</span>
        <span class="widget-config-title">${escapeHtml(w.title || w.id)}</span>
        <select class="widget-size-select" data-field="size" data-change-action="update-widget-field" data-widget-id="${w.id}" data-widget-field="size">
          <option value="normal"${w.size === 'normal' ? ' selected' : ''}>Normal</option>
          <option value="wide"${w.size === 'wide' ? ' selected' : ''}>Wide</option>
          <option value="full"${w.size === 'full' ? ' selected' : ''}>Full</option>
        </select>
        <label class="toggle-switch widget-toggle">
          <input type="checkbox" ${w.visible ? 'checked' : ''} data-change-action="update-widget-field" data-widget-id="${w.id}" data-widget-field="visible">
          <span class="toggle-slider"></span>
        </label>
      </div>
    `).join('');

    // Attach drag-and-drop handlers
    _attachWidgetDragHandlers();
  };

  if (window._widgetConfig) {
    renderList(window._widgetConfig);
  } else {
    loadWidgetConfig().then(cfg => {
      if (cfg) renderList(cfg);
    });
  }
}

function closeWidgetManager() {
  const modal = document.getElementById('widget-config-modal');
  if (modal) modal.style.display = 'none';
}

function updateWidgetField(id, field, value) {
  if (!window._widgetConfig) return;
  const w = window._widgetConfig.find(x => x.id === id);
  if (w) w[field] = value;
}

function _attachWidgetDragHandlers() {
  const list = document.getElementById('widget-config-list');
  if (!list) return;
  let dragSrc = null;

  list.querySelectorAll('.widget-config-item').forEach(item => {
    item.addEventListener('dragstart', (e) => {
      dragSrc = item;
      item.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', item.dataset.widgetId);
    });

    item.addEventListener('dragend', () => {
      item.classList.remove('dragging');
      list.querySelectorAll('.widget-config-item').forEach(el => el.classList.remove('drag-over'));
      dragSrc = null;
    });

    item.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
    });

    item.addEventListener('dragenter', (e) => {
      e.preventDefault();
      if (item !== dragSrc) item.classList.add('drag-over');
    });

    item.addEventListener('dragleave', () => {
      item.classList.remove('drag-over');
    });

    item.addEventListener('drop', (e) => {
      e.preventDefault();
      item.classList.remove('drag-over');
      if (!dragSrc || dragSrc === item) return;

      // Reorder in DOM
      const items = Array.from(list.querySelectorAll('.widget-config-item'));
      const fromIdx = items.indexOf(dragSrc);
      const toIdx = items.indexOf(item);

      if (fromIdx < toIdx) {
        item.parentNode.insertBefore(dragSrc, item.nextSibling);
      } else {
        item.parentNode.insertBefore(dragSrc, item);
      }

      // Update order in config
      const reordered = Array.from(list.querySelectorAll('.widget-config-item'));
      reordered.forEach((el, idx) => {
        const id = el.dataset.widgetId;
        const w = window._widgetConfig.find(x => x.id === id);
        if (w) w.order = idx;
      });

      // Auto-save after drag
      saveWidgetConfig(true);
    });
  });
}

async function saveWidgetConfig(silent) {
  if (!window._widgetConfig) return;
  try {
    const data = await apiPost('/api/dashboard/widgets', {widgets: window._widgetConfig});
    if (data.ok) {
      window._widgetConfig = data.widgets;
      if (_liveDashData) renderDashboardWidgets();
      if (!silent) closeWidgetManager();
    }
  } catch(e) {
    console.error('Failed to save widget config:', e);
  }
}

async function resetWidgetConfig() {
  try {
    const data = await apiPost('/api/dashboard/widgets/reset');
    if (data.ok) {
      window._widgetConfig = data.widgets;
      if (_liveDashData) renderDashboardWidgets();
      openWidgetManager(); // Re-render the list
    }
  } catch(e) {
    console.error('Failed to reset widget config:', e);
  }
}

/* ─── Live Situational Dashboard ─── */
let _liveDashTimer = null;
let _liveDashData = null;

async function loadLiveDashboard() {
  const workspace = document.getElementById('dash-workspace');
  const liveDashboard = document.getElementById('live-dashboard');
  const widgetContainer = document.getElementById('dash-live-widgets');
  if (!workspace && !liveDashboard && !widgetContainer) return;
  const data = await safeFetch('/api/dashboard/live', {}, null);
  if (!data) return;
  _liveDashData = data;
  renderLiveDashboard(data);
  // Apply widget config ordering after render
  if (window._widgetConfig) {
    renderDashboardWidgets();
  }
  // Restore expanded widget state after re-render
  if (_expandedWidget) {
    const detail = document.getElementById('widget-detail-' + _expandedWidget);
    if (detail) detail.style.display = 'block';
  }
  // Load sparklines after DOM update
  setTimeout(() => loadDashboardSparklines(), 50);
  // Load sun data for widget if not already loaded
  if (!_sunData) loadSunData().then(() => { if (_sunData) renderLiveDashboard(_liveDashData); });
}

let _expandedWidget = null;
function toggleWidgetExpand(widgetId, evt) {
  if (evt) evt.stopPropagation();
  const detail = document.getElementById('widget-detail-' + widgetId);
  if (!detail) return;
  const isOpen = detail.style.display !== 'none';
  // Close all
  document.querySelectorAll('.widget-detail').forEach(d => d.style.display = 'none');
  if (!isOpen) { detail.style.display = 'block'; _expandedWidget = widgetId; }
  else { _expandedWidget = null; }
}

function renderLiveDashboard(d) {
  const el = document.getElementById('live-dashboard');
  if (!el) return;
  const mode = _dashboardMode || 'command';

  // Widget definitions — each mode gets a different set
  const allWidgets = {
    'status': () => {
      const levels = Object.values(d.situation || {});
      const worst = levels.includes('red') ? 'red' : levels.includes('orange') ? 'orange' : levels.includes('yellow') ? 'yellow' : 'green';
      const labels = {red:'ALERT',orange:'CONCERN',yellow:'CAUTION',green:'ALL CLEAR'};
      const colors = {red:'var(--red)',orange:'var(--orange)',yellow:'var(--warning)',green:'var(--green)'};
      const sitEntries = Object.entries(d.situation || {});
      return `<div class="live-widget" role="button" tabindex="0" data-shell-action="toggle-widget-expand" data-widget-id="status">
        <div class="live-widget-label">SITUATION</div>
        <div class="live-widget-value live-widget-value-toned" style="--widget-tone:${colors[worst]};">${labels[worst]}</div>
        <div class="live-widget-detail">${Object.keys(d.situation||{}).length} domains assessed</div>
      </div>`;
    },
    'alerts': () => {
      const c = d.alerts || {};
      const color = c.critical > 0 ? 'var(--red)' : c.active > 0 ? 'var(--orange)' : 'var(--green)';
      return `<div class="live-widget" role="button" tabindex="0" data-shell-action="toggle-alert-bar">
        <div class="live-widget-label">ALERTS</div>
        <div class="live-widget-value live-widget-value-toned" style="--widget-tone:${color};">${c.active || 0}</div>
        <div class="live-widget-detail">${c.critical||0} critical</div>
      </div>`;
    },
    'inventory': () => {
      const inv = d.inventory || {};
      const burns = inv.burn_rates || [];
      const color = inv.low_stock > 0 ? 'var(--red)' : inv.expiring_30d > 0 ? 'var(--orange)' : 'var(--green)';
      const burnHtml = burns.length ? burns.map(b => {
        const tone = b.days_left < 7 ? 'live-widget-mini-count-critical' : b.days_left < 30 ? 'live-widget-mini-count-warning' : 'live-widget-mini-count-muted';
        return `<div class="live-widget-mini-row"><span>${escapeHtml(b.name)}</span><strong class="live-widget-mini-count ${tone}">${b.days_left}d</strong></div>`;
      }).join('') : '<div class="live-widget-mini-empty">No burn rate items tracked</div>';
      return `<div class="live-widget" role="button" tabindex="0" data-shell-action="toggle-widget-expand" data-widget-id="inventory">
        <div class="live-widget-label">SUPPLIES <span class="live-widget-chevron">&#9660;</span></div>
        <div class="live-widget-value live-widget-value-toned" style="--widget-tone:${color};">${inv.total || 0}</div>
        <div class="live-widget-detail">${inv.low_stock||0} low &middot; ${inv.expiring_30d||0} expiring &middot; ${inv.critical_7d||0} critical</div>
        <div id="widget-detail-inventory" class="widget-detail widget-detail-shell is-hidden">
          <div class="widget-detail-kicker">BURN RATE — DAYS REMAINING</div>
          <div class="live-widget-mini-list">${burnHtml}</div>
          <div class="widget-detail-action"><button class="btn btn-sm live-widget-action-full" data-tab-target="preparedness" data-prep-sub="inventory" data-stop-propagation>OPEN INVENTORY &#8594;</button></div>
        </div>
      </div>`;
    },
    'burn-rate': () => {
      const burns = (d.inventory || {}).burn_rates || [];
      if (!burns.length) return '';
      const worst = burns[0];
      const color = worst.days_left < 7 ? 'var(--red)' : worst.days_left < 30 ? 'var(--orange)' : 'var(--green)';
      return `<div class="live-widget" role="button" tabindex="0" data-shell-action="toggle-widget-expand" data-widget-id="burn">
        <div class="live-widget-label">CRITICAL SUPPLY</div>
        <div class="live-widget-value live-widget-value-toned live-widget-value-compact" style="--widget-tone:${color};">${escapeHtml(worst.name)}</div>
        <div class="live-widget-detail live-widget-detail-toned" style="--widget-tone:${color};">${worst.days_left} days remaining</div>
        <div id="widget-detail-burn" class="widget-detail widget-detail-shell is-hidden">
          ${burns.slice(0,5).map(b => `<div class="widget-detail-row"><span>${escapeHtml(b.name)}</span><span class="widget-detail-row-value-toned" style="--widget-tone:${b.days_left < 7 ? 'var(--red)' : 'var(--text-dim)'}">${b.days_left}d</span></div>`).join('')}
        </div>
      </div>`;
    },
    'security': () => {
      const s = d.security || {};
      const color = s.incidents_24h > 0 ? 'var(--red)' : 'var(--green)';
      return `<div class="live-widget live-widget-nav" role="button" tabindex="0" data-tab-target="preparedness" data-prep-sub="security" data-prep-delay="200">
        <div class="live-widget-label">SECURITY</div>
        <div class="live-widget-value live-widget-value-toned" style="--widget-tone:${color};">${s.incidents_24h > 0 ? s.incidents_24h + ' INCIDENTS' : 'SECURE'}</div>
        <div class="live-widget-detail">${s.cameras||0} cameras &middot; ${s.access_24h||0} access events</div>
      </div>`;
    },
    'weather': () => {
      const w = d.weather || {};
      const trend = w.pressure_trend || 'stable';
      const trendIcon = trend === 'rising' ? '&#9650;' : trend === 'falling' ? '&#9660;' : '&#9644;';
      const trendColor = trend === 'falling' ? 'var(--orange)' : 'var(--green)';
      return `<div class="live-widget live-widget-nav" role="button" tabindex="0" data-tab-target="preparedness" data-prep-sub="weather" data-prep-delay="200">
        <div class="live-widget-label">WEATHER</div>
        <div class="live-widget-value live-widget-value-toned live-widget-value-compact" style="--widget-tone:${trendColor};"><span class="live-widget-trend-icon">${trendIcon}</span> ${trend.toUpperCase()}</div>
        <div class="live-widget-detail">${w.latest?.pressure_hpa ? w.latest.pressure_hpa + ' hPa' : 'No readings'}</div>
      </div>`;
    },
    'power': () => {
      const p = d.power || {};
      if (!p.battery_soc && !p.solar_watts) return '';
      return `<div class="live-widget live-widget-nav" role="button" tabindex="0" data-tab-target="preparedness" data-prep-sub="power" data-prep-delay="200">
        <div class="live-widget-label">POWER</div>
        <div class="live-widget-value-split">
          <div class="live-widget-value">${p.battery_soc != null ? p.battery_soc + '%' : '--'}</div>
          <canvas id="spark-power" class="live-widget-spark-canvas"></canvas>
        </div>
        <div class="live-widget-detail">${p.solar_watts ? p.solar_watts + 'W solar' : ''} ${p.load_watts ? '&middot; ' + p.load_watts + 'W load' : ''}</div>
      </div>`;
    },
    'garden': () => {
      const g = d.garden || {};
      return `<div class="live-widget live-widget-nav" role="button" tabindex="0" data-tab-target="preparedness" data-prep-sub="garden" data-prep-delay="200">
        <div class="live-widget-label">FOOD PRODUCTION</div>
        <div class="live-widget-value">${g.plots||0} plots</div>
        <div class="live-widget-detail">${g.livestock||0} livestock &middot; ${g.harvests_7d||0} harvests this week</div>
      </div>`;
    },
    'comms': () => {
      const c = d.comms || {};
      const lastStr = c.last_contact ? timeAgo(c.last_contact) : 'No contacts';
      return `<div class="live-widget live-widget-nav" role="button" tabindex="0" data-tab-target="preparedness" data-prep-sub="radio" data-prep-delay="200">
        <div class="live-widget-label">COMMS</div>
        <div class="live-widget-value live-widget-value-compact">${lastStr}</div>
        <div class="live-widget-detail">${(d.federation||{}).peers_recent||0} peers active</div>
      </div>`;
    },
    'fuel': () => {
      const f = d.fuel || {};
      if (!f.total_gallons) return '';
      return `<div class="live-widget live-widget-nav" role="button" tabindex="0" data-tab-target="preparedness" data-prep-sub="fuel" data-prep-delay="200">
        <div class="live-widget-label">FUEL RESERVES</div>
        <div class="live-widget-value">${f.total_gallons} gal</div>
        <div class="live-widget-detail">${(d.equipment||{}).overdue||0} equipment overdue</div>
      </div>`;
    },
    'contacts': () => {
      return `<div class="live-widget live-widget-nav" role="button" tabindex="0" data-tab-target="preparedness" data-prep-sub="contacts" data-prep-delay="200">
        <div class="live-widget-label">TEAM</div>
        <div class="live-widget-value">${(d.contacts||{}).total||0}</div>
        <div class="live-widget-detail">${(d.medical||{}).patients||0} patients tracked</div>
      </div>`;
    },
    'medical': () => {
      const m = d.medical || {};
      return `<div class="live-widget live-widget-nav" role="button" tabindex="0" data-tab-target="preparedness" data-prep-sub="medical" data-prep-delay="200">
        <div class="live-widget-label">MEDICAL</div>
        <div class="live-widget-value">${m.patients||0} patients</div>
        <div class="live-widget-detail">Active care tracking</div>
      </div>`;
    },
    'sun': () => {
      const s = d.sun || _sunData || {};
      if (!s.sunrise) return '';
      return `<div class="live-widget">
        <div class="live-widget-label">SUN</div>
        <div class="live-widget-value live-widget-value-small">${s.sunrise ? s.sunrise.slice(11,16) : '--'} / ${s.sunset ? s.sunset.slice(11,16) : '--'}</div>
        <div class="live-widget-detail">${s.day_length || 'N/A'} daylight</div>
      </div>`;
    },
  };

  // Mode-specific widget selection
  const modeWidgets = {
    command: ['status','alerts','inventory','burn-rate','security','weather','power','sun','comms','fuel','contacts'],
    homestead: ['weather','garden','power','inventory','fuel','sun','alerts','contacts','comms'],
    minimal: ['status','alerts','inventory','burn-rate'],
  };

  const widgetKeys = modeWidgets[mode] || modeWidgets.command;
  const html = widgetKeys.map(k => allWidgets[k] ? allWidgets[k]() : '').filter(Boolean).join('');
  el.innerHTML = html;
}

function timeAgo(dateStr) {
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = now - d;
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return mins + 'm ago';
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return hrs + 'h ago';
  const days = Math.floor(hrs / 24);
  return days + 'd ago';
}

function startLiveDashPolling() {
  if (_liveDashTimer) clearInterval(_liveDashTimer);
  window.NomadShellRuntime?.stopInterval('services.live-dashboard');
  const workspace = document.getElementById('dash-workspace');
  const liveDashboard = document.getElementById('live-dashboard');
  const widgetContainer = document.getElementById('dash-live-widgets');
  if (!workspace && !liveDashboard && !widgetContainer) return;
  loadLiveDashboard();
  const pollLiveDashboard = () => {
    if (workspace && !workspace.classList.contains('active') && !liveDashboard) return;
    loadLiveDashboard();
  };
  if (window.NomadShellRuntime) {
    _liveDashTimer = window.NomadShellRuntime.startInterval('services.live-dashboard', pollLiveDashboard, 30000, {
      tabId: liveDashboard ? 'services' : '',
      requireVisible: true,
    });
    return;
  }
  _liveDashTimer = setInterval(() => {
    if (!document.getElementById('dash-workspace')?.classList.contains('active')) return;
    if (!document.hidden) loadLiveDashboard();
  }, 30000);
}

/* ─── Command Dashboard ─── */
async function loadCmdDashboard() {
  const el = document.getElementById('cmd-dashboard');
  if (!el) return;
  try {
    const [d, crit] = await Promise.all([
      safeFetch('/api/dashboard/overview', {}, null),
      safeFetch('/api/dashboard/critical', {}, {critical_burn:[], expiring_items:[]}),
    ]);
    if (!d) throw new Error('dashboard overview unavailable');
    const sitLabels = {green:'ALL CLEAR',yellow:'CAUTION',orange:'CONCERN',red:'CRITICAL'};
      const sitColors = {green:'var(--green)',yellow:'var(--warning)',orange:'var(--orange)',red:'var(--red)'};
    const metricCard = ({ label, value, tone = 'var(--accent)', meta = '', nav = '', valueClass = '' }) =>
      `<div class="prep-metric-card${nav ? ' cmd-dashboard-card-nav' : ''}"${nav ? ` ${nav}` : ''} style="--prep-tone:${tone};">
        <div class="prep-metric-label">${label}</div>
        <div class="prep-metric-value${valueClass ? ' ' + valueClass : ''}">${value}</div>
        ${meta ? `<div class="prep-metric-meta">${meta}</div>` : ''}
      </div>`;
    // Find worst situation
    let worstSit = 'green';
    const sitOrder = ['green','yellow','orange','red'];
    for (const [domain, level] of Object.entries(d.situation || {})) {
      if (sitOrder.indexOf(level) > sitOrder.indexOf(worstSit)) worstSit = level;
    }
    el.innerHTML = `
      ${metricCard({ label: 'Status', value: sitLabels[worstSit], tone: sitColors[worstSit], valueClass: 'live-widget-value-compact' })}
      ${metricCard({ label: 'Timers', value: d.timers, tone: d.timers > 0 ? 'var(--accent)' : 'var(--text-muted)', valueClass: 'live-widget-value-compact' })}
      ${metricCard({ label: 'Low Stock', value: d.low_stock, tone: d.low_stock > 0 ? 'var(--red)' : 'var(--green)', nav: 'role="button" tabindex="0" data-tab-target="preparedness" data-prep-sub="inventory" data-prep-delay="200"', valueClass: 'live-widget-value-compact' })}
      ${metricCard({ label: 'Expiring', value: d.expiring, tone: d.expiring > 0 ? 'var(--orange)' : 'var(--green)', valueClass: 'live-widget-value-compact' })}
      ${metricCard({ label: 'Incidents 24h', value: d.recent_incidents, tone: d.recent_incidents > 0 ? 'var(--orange)' : 'var(--text-muted)', nav: 'role="button" tabindex="0" data-tab-target="preparedness" data-prep-sub="incidents" data-prep-delay="200"', valueClass: 'live-widget-value-compact' })}
      ${d.pressure_current ? metricCard({ label: 'Pressure', value: d.pressure_current, tone: 'var(--text)', valueClass: 'live-widget-value-compact' }) : ''}
      ${(() => {
        const ts = localStorage.getItem('nomad-last-backup');
        let backupLabel = 'Never';
        let backupColor = 'var(--red)';
        if (ts) {
          const ago = Math.round((Date.now() - new Date(ts).getTime()) / (1000*60*60*24));
          backupLabel = ago === 0 ? 'Today' : ago + 'd ago';
          backupColor = ago > 30 ? 'var(--red)' : ago > 7 ? 'var(--orange)' : 'var(--green)';
        }
        return metricCard({ label: 'Last Backup', value: backupLabel, tone: backupColor, nav: 'role="button" tabindex="0" data-tab-target="settings"', valueClass: 'live-widget-value-compact' });
      })()}
    `;
    // Append critical alerts from parallel fetch
    let critHtml = '';
    if (crit.critical_burn.length) critHtml += `<div class="cmd-dashboard-note-line text-danger">Running low: ${crit.critical_burn.map(i => `${escapeHtml(i.name)} (${escapeHtml(String(i.days_left))}d)`).join(', ')}</div>`;
    if (crit.expiring_items.length) critHtml += `<div class="cmd-dashboard-note-line text-orange">Expiring: ${crit.expiring_items.map(i => `${escapeHtml(i.name)} (${escapeHtml(i.expiration)})`).join(', ')}</div>`;
    if (critHtml) el.innerHTML += `<div class="cmd-dashboard-note">${critHtml}</div>`;
  } catch(e) { console.warn('loadCmdDashboard failed:', e); }
}

/* ─── Readiness Score ─── */
async function loadReadinessScore() {
  const gradeEl = document.getElementById('rs-grade');
  const totalEl = document.getElementById('rs-total');
  const fill = document.getElementById('rs-bar-fill');
  const cats = document.getElementById('rs-categories');
  if (!gradeEl || !totalEl || !fill || !cats) return;
  try {
    const d = await safeFetch('/api/readiness-score', {}, null);
    if (!d || !d.categories) return;
    const gradeColors = {A:'var(--green)',B:'var(--green)',C:'var(--warning)',D:'var(--orange)',F:'var(--red)'};
    gradeEl.textContent = d.grade;
    gradeEl.style.color = gradeColors[d.grade] || 'var(--text)';
    totalEl.textContent = `${d.total}/100`;
    fill.style.width = `${d.total}%`;
    fill.style.background = d.total >= 80 ? 'var(--green)' : d.total >= 50 ? 'var(--orange)' : 'var(--red)';
    const catLabels = {water:'Water',food:'Food',medical:'Medical',security:'Security',comms:'Communications',shelter:'Power & Land',planning:'Plans & Knowledge'};
    const catMax = {water:20,food:20,medical:15,security:10,comms:10,shelter:10,planning:15};
    const catLinks = {water:'inventory',food:'inventory',medical:'medical',security:'security',comms:'contacts',shelter:'power',planning:'checklists'};
    cats.innerHTML = Object.entries(d.categories).map(([k, v]) => {
      const pct = Math.round(v.score / (catMax[k] || 1) * 100);
      const color = pct >= 70 ? 'var(--green)' : pct >= 40 ? 'var(--orange)' : 'var(--red)';
      const link = catLinks[k] || 'inventory';
      return `<div class="readiness-category-link readiness-category-row" role="button" tabindex="0" data-tab-target="preparedness" data-prep-sub="${link}" data-prep-delay="200" title="${escapeAttr(v.detail || '')} — click to improve">
        <span class="readiness-category-label">${escapeHtml(catLabels[k] || k)}</span>
        <div class="readiness-category-track">
          <div class="readiness-category-fill" style="--readiness-pct:${pct}%;--readiness-tone:${color};"></div>
        </div>
        <span class="readiness-category-score" style="--readiness-tone:${color};">${v.score}</span>
      </div>`;
    }).join('');
  } catch(e) {}
}
async function loadReadinessNeeds() {
  const el = document.getElementById('readiness-needs-grid');
  if (!el) return;
  const data = await safeFetch('/api/needs', {}, {});
  if (!data || !Object.keys(data).length) { el.innerHTML = ''; return; }
  el.innerHTML = Object.entries(data).map(([id, n]) => {
    const safeColor = /^#[0-9a-fA-F]{3,8}$/.test(n.color) ? n.color : 'var(--accent)';
    const safeId = escapeAttr(id);
    return `
    <div class="need-card" style="--need-tone:${safeColor};" role="button" tabindex="0" data-shell-action="open-needs-detail" data-need-id="${safeId}">
      <div class="need-card-head">
        <span class="need-card-icon">${escapeHtml(n.icon)}</span>
        <span class="need-card-title">${escapeHtml(n.label)}</span>
      </div>
      <div class="need-card-badges">
        ${n.inventory > 0 ? `<span class="need-badge">${n.inventory} supplies</span>` : ''}
        ${n.contacts > 0 ? `<span class="need-badge">${n.contacts} contacts</span>` : ''}
        ${n.books > 0 ? `<span class="need-badge">${n.books} books</span>` : ''}
        ${n.guides > 0 ? `<span class="need-badge">${n.guides} guides</span>` : ''}
        ${n.total === 0 ? `<span class="need-badge need-badge-danger">NO COVERAGE</span>` : ''}
      </div>
      <div class="need-progress"><div class="need-progress-fill" style="width:${Math.min((n.total||0) * 10, 100)}%;background:${(n.total||0) >= 6 ? 'var(--green)' : (n.total||0) >= 3 ? 'var(--orange)' : 'var(--red)'};"></div></div>
    </div>`;
  }).join('');
}

/* ─── Document Vault (AES-256-GCM client-side encryption) ─── */
let _vaultKey = null;

async function deriveVaultKey(password, salt) {
  const enc = new TextEncoder();
  const keyMaterial = await crypto.subtle.importKey('raw', enc.encode(password), 'PBKDF2', false, ['deriveKey']);
  return crypto.subtle.deriveKey({name: 'PBKDF2', salt, iterations: 100000, hash: 'SHA-256'}, keyMaterial, {name: 'AES-GCM', length: 256}, false, ['encrypt', 'decrypt']);
}

async function unlockVault() {
  const passwordInput = document.getElementById('vault-pw');
  const lockedEl = document.getElementById('vault-locked');
  const unlockedEl = document.getElementById('vault-unlocked');
  if (!passwordInput || !lockedEl || !unlockedEl) return;
  const pw = passwordInput.value;
  if (!pw) { toast('Enter a password', 'warning'); return; }
  try {
    // Verify password by trying to decrypt the verification entry if one exists
    const entries = await safeFetch('/api/vault', {}, null);
    if (!Array.isArray(entries)) { toast('Failed to access vault', 'error'); return; }
    const verifyEntry = entries.find(e => e.title === '__vault_verify__');
    if (verifyEntry) {
      try {
        const e = await apiFetch(`/api/vault/${verifyEntry.id}`);
        const salt = Uint8Array.from(atob(e.salt), c => c.charCodeAt(0));
        const iv = Uint8Array.from(atob(e.iv), c => c.charCodeAt(0));
        const data = Uint8Array.from(atob(e.encrypted_data), c => c.charCodeAt(0));
        const key = await deriveVaultKey(pw, salt);
        await crypto.subtle.decrypt({name: 'AES-GCM', iv}, key, data);
      } catch(decErr) {
        toast('Wrong password', 'error');
        return;
      }
    }
    _vaultKey = {password: pw};
    // Create verification entry on first unlock
    if (!verifyEntry) {
      const encrypted = await encryptVaultData('nomad-vault-v1');
      try { await apiPost('/api/vault', {title: '__vault_verify__', ...encrypted}); } catch(e) {}
    }
    lockedEl.style.display = 'none';
    unlockedEl.style.display = 'block';
    loadVaultList();
    toast('Vault unlocked', 'success');
  } catch(e) { toast('Failed to unlock: ' + e.message, 'error'); }
}

function lockVault() {
  const passwordInput = document.getElementById('vault-pw');
  const lockedEl = document.getElementById('vault-locked');
  const unlockedEl = document.getElementById('vault-unlocked');
  if (!passwordInput || !lockedEl || !unlockedEl) return;
  _vaultKey = null;
  lockedEl.style.display = 'block';
  unlockedEl.style.display = 'none';
  passwordInput.value = '';
  toast('Vault locked');
}

async function encryptVaultData(text) {
  const enc = new TextEncoder();
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await deriveVaultKey(_vaultKey.password, salt);
  const encrypted = await crypto.subtle.encrypt({name: 'AES-GCM', iv}, key, enc.encode(text));
  return {
    encrypted_data: btoa(String.fromCharCode(...new Uint8Array(encrypted))),
    iv: btoa(String.fromCharCode(...iv)),
    salt: btoa(String.fromCharCode(...salt)),
  };
}

async function decryptVaultData(encrypted_data, iv_b64, salt_b64) {
  const dec = new TextDecoder();
  const salt = Uint8Array.from(atob(salt_b64), c => c.charCodeAt(0));
  const iv = Uint8Array.from(atob(iv_b64), c => c.charCodeAt(0));
  const data = Uint8Array.from(atob(encrypted_data), c => c.charCodeAt(0));
  const key = await deriveVaultKey(_vaultKey.password, salt);
  const decrypted = await crypto.subtle.decrypt({name: 'AES-GCM', iv}, key, data);
  return dec.decode(decrypted);
}

async function loadVaultList() {
  try {
    const allEntries = await safeFetch('/api/vault', {}, null);
    if (!Array.isArray(allEntries)) return;
    const entries = allEntries.filter(e => e.title !== '__vault_verify__');
    const el = document.getElementById('vault-list');
    if (!el) return;
    if (!entries.length) { el.innerHTML = '<div class="utility-empty-state vault-empty-state">No entries yet. Click "+ New Entry" to add encrypted documents.</div>'; return; }
    el.innerHTML = entries.map(e => `
      <div class="prep-record-item vault-entry-row">
        <button type="button" class="btn btn-ghost vault-entry-open" data-prep-action="view-vault-entry" data-vault-id="${e.id}">
          <span class="vault-entry-title">${escapeHtml(e.title)}</span>
          <span class="vault-entry-meta">${new Date(e.updated_at).toLocaleString()}</span>
        </button>
        <div class="vault-entry-actions">
          <button type="button" class="btn btn-sm" data-prep-action="edit-vault-entry" data-vault-id="${e.id}">Edit</button>
          <button type="button" class="btn btn-sm btn-danger" data-prep-action="delete-vault-entry" data-vault-id="${e.id}">Delete</button>
        </div>
      </div>
    `).join('');
  } catch(e) {}
}

function newVaultEntry() {
  const form = document.getElementById('vault-form');
  const titleInput = document.getElementById('vault-title');
  const contentInput = document.getElementById('vault-content');
  const editIdInput = document.getElementById('vault-edit-id');
  if (!form || !titleInput || !contentInput || !editIdInput) return;
  form.style.display = 'block';
  titleInput.value = '';
  contentInput.value = '';
  editIdInput.value = '';
}

function hideVaultForm() {
  const form = document.getElementById('vault-form');
  if (!form) return;
  form.style.display = 'none';
}

async function saveVaultEntry() {
  if (!_vaultKey) { toast('Vault is locked', 'warning'); return; }
  const titleInput = document.getElementById('vault-title');
  const contentInput = document.getElementById('vault-content');
  const editIdInput = document.getElementById('vault-edit-id');
  if (!titleInput || !contentInput || !editIdInput) return;
  const title = titleInput.value.trim();
  const content = contentInput.value;
  if (!title) { toast('Title required', 'warning'); return; }
  try {
    const encrypted = await encryptVaultData(content);
    const editId = editIdInput.value;
    if (editId) {
      await apiPut('/api/vault/' + editId, {title, ...encrypted});
    } else {
      await apiPost('/api/vault', {title, ...encrypted});
    }
    toast('Entry encrypted and saved', 'success');
    hideVaultForm();
    loadVaultList();
  } catch(e) { toast('Encryption failed: ' + e.message, 'error'); }
}

async function viewVaultEntry(id) {
  if (!_vaultKey) { toast('Vault is locked', 'warning'); return; }
  try {
    const e = await apiFetch(`/api/vault/${id}`);
    const decrypted = await decryptVaultData(e.encrypted_data, e.iv, e.salt);
    const form = document.getElementById('vault-form');
    const titleInput = document.getElementById('vault-title');
    const contentInput = document.getElementById('vault-content');
    const editIdInput = document.getElementById('vault-edit-id');
    if (!form || !titleInput || !contentInput || !editIdInput) return;
    form.style.display = 'block';
    titleInput.value = e.title;
    contentInput.value = decrypted;
    editIdInput.value = id;
  } catch(err) { toast('Decryption failed — wrong password?', 'error'); }
}

async function editVaultEntry(id) { await viewVaultEntry(id); }

function deleteVaultEntry(id, btn) {
  if (!confirm('Delete this vault entry?')) return;
  if (!btn) return;
  if (!btn.dataset.confirm) {
    btn.dataset.confirm = '1';
    btn.textContent = 'Confirm?';
      btn.classList.add('is-confirming');
    setTimeout(() => { btn.textContent = 'Delete'; btn.classList.remove('is-confirming'); delete btn.dataset.confirm; }, 3000);
    return;
  }
  apiDelete('/api/vault/' + id)
    .then(() => { toast('Entry deleted', 'warning'); loadVaultList(); })
    .catch(() => toast('Failed to delete entry', 'error'));
}

/* ─── Weather Journal ─── */
async function logWeather() {
  const pressureInput = document.getElementById('wx-pressure');
  const tempInput = document.getElementById('wx-temp');
  const windDirInput = document.getElementById('wx-wind-dir');
  const windSpeedInput = document.getElementById('wx-wind-spd');
  const cloudsInput = document.getElementById('wx-clouds');
  const precipInput = document.getElementById('wx-precip');
  const notesInput = document.getElementById('wx-notes');
  if (!pressureInput || !tempInput || !windDirInput || !windSpeedInput || !cloudsInput || !precipInput || !notesInput) return;
  const data = {
    pressure_hpa: parseFloat(pressureInput.value) || null,
    temp_f: parseFloat(tempInput.value) || null,
    wind_dir: windDirInput.value,
    wind_speed: windSpeedInput.value,
    clouds: cloudsInput.value,
    precip: precipInput.value,
    notes: notesInput.value.trim(),
  };
  if (!data.pressure_hpa && !data.temp_f && !data.notes) { toast('Enter at least temperature, pressure, or notes', 'warning'); return; }
  try {
    await apiPost('/api/weather', data);
    toast('Weather observation logged', 'success');
  } catch(e) { toast('Failed to log weather observation', 'error'); return; }
  notesInput.value = '';
  loadWeather();
}

async function loadWeather() {
  const trendEl = document.getElementById('wx-trend');
  if (trendEl) trendEl.innerHTML = '<div class="skeleton skeleton-line weather-skeleton-short"></div>';
  const logEl = document.getElementById('wx-log');
  if (logEl) logEl.innerHTML = Array(3).fill('<div class="skeleton skeleton-line weather-skeleton-row"></div>').join('');
  try {
    // Load trend
    const trend = await safeFetch('/api/weather/trend', {}, null);
    if (!trend) { if (trendEl) trendEl.innerHTML = '<span class="text-muted">Weather data unavailable</span>'; return; }
    const trendIcons = {rising_fast:'++ ',rising:'+ ',steady:'= ',falling:'- ',falling_fast:'-- ',insufficient:''};
    trendEl.innerHTML = `
      <div class="weather-trend-value ${trend.trend === 'falling' || trend.trend === 'falling_fast' ? 'text-red' : trend.trend === 'rising' || trend.trend === 'rising_fast' ? 'text-green' : trend.trend === 'steady' ? 'text-strong' : 'text-muted'}">${trendIcons[trend.trend]}${trend.current ? trend.current + ' hPa' : 'No data'}</div>
      ${trend.diff_hpa !== undefined ? `<div class="text-size-12 text-dim">Change: ${trend.diff_hpa > 0 ? '+' : ''}${trend.diff_hpa} hPa over ${trend.readings} readings</div>` : ''}
      <div class="weather-trend-prediction">${trend.prediction}</div>`;

    // Load history
    const history = await safeFetch('/api/weather?limit=20', {}, []);
    const histEl = document.getElementById('wx-history');
    if (!histEl) return;
    if (!history.length) { histEl.innerHTML = '<div class="text-muted text-size-12">No observations yet.</div>'; return; }
    histEl.innerHTML = '<table class="freq-table"><thead><tr><th>Time</th><th>hPa</th><th>Temp</th><th>Wind</th><th>Sky</th><th>Notes</th></tr></thead><tbody>' +
      history.map(w => {
        const t = new Date(w.created_at);
        const ts = t.toLocaleDateString([],{month:'short',day:'numeric'}) + ' ' + t.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
        return `<tr><td class="runtime-table-nowrap">${ts}</td><td>${w.pressure_hpa||'-'}</td><td>${w.temp_f ? w.temp_f+'F' : '-'}</td><td>${w.wind_dir||'-'} ${w.wind_speed||''}</td><td>${[w.clouds,w.precip].filter(Boolean).join(', ')||'-'}</td><td class="text-size-10">${escapeHtml(w.notes||'')}</td></tr>`;
      }).join('') + '</tbody></table>';
  } catch(e) {}
}

async function loadZambretti() {
  const el = document.getElementById('zambretti-content');
  if (!el) return;
  const data = await safeFetch('/api/weather/predict', {}, null);
  if (!data || data.forecast === 'Insufficient data') {
    el.innerHTML = '<div class="prep-status-copy">Add at least 3 barometric pressure readings to enable offline weather prediction.<br><span class="prep-status-footnote">The Zambretti algorithm predicts weather from pressure trends — no internet needed.</span></div>';
    return;
  }
  const trendIcon = data.trend === 'rising' ? '\u2191' : data.trend === 'falling' ? '\u2193' : '\u2192';
  const trendColor = data.trend === 'rising' ? 'var(--green)' : data.trend === 'falling' ? 'var(--red)' : 'var(--text)';
  el.innerHTML = `
    <div class="weather-zambretti-title">${escapeHtml(data.forecast)}</div>
    <div class="weather-zambretti-grid">
      <div class="weather-zambretti-stat"><span class="weather-zambretti-label">Pressure</span><br><strong class="weather-zambretti-value weather-zambretti-value-data">${data.current_hpa} hPa</strong></div>
      <div class="weather-zambretti-stat"><span class="weather-zambretti-label">Trend</span><br><strong class="weather-zambretti-value weather-zambretti-trend" style="--weather-trend-tone:${trendColor};">${trendIcon}</strong> <span class="weather-zambretti-value weather-zambretti-value-data">${data.delta_hpa > 0 ? '+' : ''}${data.delta_hpa} hPa</span></div>
      <div class="weather-zambretti-stat"><span class="weather-zambretti-label">Based on</span><br><strong class="weather-zambretti-value">${data.readings_count} readings</strong></div>
    </div>`;
}

async function loadPressureGraph() {
  const canvas = document.getElementById('pressure-canvas');
  const info = document.getElementById('pressure-graph-info');
  if (!canvas || !info) return;
  const data = await safeFetch('/api/weather/history?hours=48', {}, []);
  const readings = data.filter(r => r.pressure_hpa != null);
  if (readings.length < 2) { info.textContent = 'Need at least 2 pressure readings to show graph.'; return; }

  const ctx = canvas.getContext('2d');
  const w = canvas.width = canvas.offsetWidth * (window.devicePixelRatio || 1);
  const h = canvas.height = 200 * (window.devicePixelRatio || 1);
  ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
  const dw = canvas.offsetWidth, dh = 200;

  const pressures = readings.map(r => r.pressure_hpa);
  const minP = Math.min(...pressures) - 2;
  const maxP = Math.max(...pressures) + 2;
  const rangeP = maxP - minP || 1;

  ctx.clearRect(0, 0, dw, dh);

  // Grid lines
  const style = getComputedStyle(document.documentElement);
  const borderColor = style.getPropertyValue('--border').trim() || '#333';
  const accentColor = style.getPropertyValue('--accent').trim() || '#5b9fff';
  const textColor = style.getPropertyValue('--text-muted').trim() || '#888';

  ctx.strokeStyle = borderColor;
  ctx.lineWidth = 0.5;
  for (let i = 0; i <= 4; i++) {
    const y = (i / 4) * (dh - 30) + 10;
    ctx.beginPath(); ctx.moveTo(40, y); ctx.lineTo(dw - 10, y); ctx.stroke();
    ctx.fillStyle = textColor; ctx.font = '9px monospace';
    ctx.fillText((maxP - (i/4)*rangeP).toFixed(0), 2, y + 3);
  }

  // Data line
  ctx.strokeStyle = accentColor;
  ctx.lineWidth = 2;
  ctx.beginPath();
  readings.forEach((r, i) => {
    const x = readings.length <= 1 ? (dw / 2) : 40 + (i / (readings.length - 1)) * (dw - 50);
    const y = 10 + ((maxP - r.pressure_hpa) / rangeP) * (dh - 30);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Dots
  ctx.fillStyle = accentColor;
  readings.forEach((r, i) => {
    const x = readings.length <= 1 ? (dw / 2) : 40 + (i / (readings.length - 1)) * (dw - 50);
    const y = 10 + ((maxP - r.pressure_hpa) / rangeP) * (dh - 30);
    ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI*2); ctx.fill();
  });

  // Time labels
  ctx.fillStyle = textColor; ctx.font = '9px monospace';
  const first = new Date(readings[0].created_at);
  const last = new Date(readings[readings.length-1].created_at);
  ctx.fillText(first.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}), 40, dh - 2);
  ctx.fillText(last.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}), dw - 50, dh - 2);

  info.textContent = readings.length + ' readings — ' + pressures[pressures.length-1].toFixed(1) + ' hPa current';
}

/* ─── Weather Action Rules ─── */

const _wxRuleDefaults = [
  { name: 'Storm Warning', condition_type: 'pressure_drop', threshold: -4, comparison: 'lt', action_type: 'alert', action_data: { severity: 'critical', title: 'Storm Warning — Rapid Pressure Drop', message: 'Barometric pressure dropping rapidly. Storm likely imminent.' }, cooldown_minutes: 120 },
  { name: 'Extreme Heat Alert', condition_type: 'temp_high', threshold: 105, comparison: 'gt', action_type: 'both', action_data: { severity: 'critical', title: 'Extreme Heat Alert', message: 'Temperature exceeds 105F — heat stroke danger.', task_name: 'Heat emergency prep', task_category: 'weather' }, cooldown_minutes: 60 },
  { name: 'Freeze Warning', condition_type: 'temp_low', threshold: 32, comparison: 'lt', action_type: 'alert', action_data: { severity: 'warning', title: 'Freeze Warning', message: 'Temperature below freezing — protect pipes and plants.' }, cooldown_minutes: 120 },
  { name: 'Dangerous Wind Chill', condition_type: 'wind_chill', threshold: 0, comparison: 'lt', action_type: 'alert', action_data: { severity: 'critical', title: 'Dangerous Wind Chill', message: 'Wind chill below 0F — frostbite risk in minutes.' }, cooldown_minutes: 120 },
];

async function loadWeatherRules() {
  const el = document.getElementById('wx-rules-list');
  if (!el) return;
  el.innerHTML = '<div class="skeleton skeleton-line weather-skeleton-row"></div>';
  try {
    const rules = await safeFetch('/api/weather/action-rules', {}, null);
    if (!Array.isArray(rules)) { el.innerHTML = ''; return; }
    // Seed defaults if empty
    if (rules.length === 0) {
      await Promise.all(_wxRuleDefaults.map(def => apiPost('/api/weather/action-rules', def)));
      return loadWeatherRules();
    }
    if (!rules.length) { el.innerHTML = '<div class="text-muted">No weather action rules defined.</div>'; return; }
    const compLabels = { lt: '<', gt: '>', lte: '\u2264', gte: '\u2265' };
    const condLabels = { pressure_drop: 'Pressure Drop', pressure_rise: 'Pressure Rise', temp_high: 'Temp High', temp_low: 'Temp Low', wind_chill: 'Wind Chill', heat_index: 'Heat Index' };
    el.innerHTML = '<table class="freq-table"><thead><tr><th>Name</th><th>Condition</th><th>Action</th><th>Cooldown</th><th>Last Triggered</th><th>Status</th><th></th></tr></thead><tbody>' +
      rules.map(r => {
        const lastTrig = r.last_triggered ? new Date(r.last_triggered).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : 'Never';
        return `<tr class="${r.enabled ? '' : 'weather-rule-row-disabled'}">
          <td class="text-strong">${escapeHtml(r.name)}</td>
          <td><span class="weather-rule-condition">${condLabels[r.condition_type] || r.condition_type} ${compLabels[r.comparison] || r.comparison} ${r.threshold}</span></td>
          <td><span class="weather-rule-action ${r.action_type === 'both' ? 'text-red' : r.action_type === 'alert' ? 'text-orange' : 'text-accent'}">${r.action_type}</span></td>
          <td class="text-size-11">${r.cooldown_minutes}m</td>
          <td class="text-size-11">${lastTrig}</td>
          <td><button type="button" class="btn btn-sm weather-rule-btn" data-prep-action="toggle-weather-rule" data-weather-rule-id="${r.id}">${r.enabled ? 'ON' : 'OFF'}</button></td>
          <td><button type="button" class="btn btn-sm weather-rule-btn weather-rule-delete" data-prep-action="delete-weather-rule" data-weather-rule-id="${r.id}" aria-label="Delete weather rule">X</button></td>
        </tr>`;
      }).join('') + '</tbody></table>';
  } catch (e) { el.innerHTML = '<div class="runtime-empty-error">Failed to load rules.</div>'; }
}

async function createWeatherRule() {
  const nameInput = document.getElementById('wxr-name');
  const severityInput = document.getElementById('wxr-severity');
  const titleInput = document.getElementById('wxr-title');
  const messageInput = document.getElementById('wxr-message');
  const taskNameInput = document.getElementById('wxr-taskname');
  const taskCategoryInput = document.getElementById('wxr-taskcat');
  const conditionInput = document.getElementById('wxr-condition');
  const comparisonInput = document.getElementById('wxr-comparison');
  const thresholdInput = document.getElementById('wxr-threshold');
  const actionInput = document.getElementById('wxr-action');
  const cooldownInput = document.getElementById('wxr-cooldown');
  const form = document.getElementById('wx-rule-form');
  if (!nameInput || !severityInput || !titleInput || !messageInput || !taskNameInput || !taskCategoryInput || !conditionInput || !comparisonInput || !thresholdInput || !actionInput || !cooldownInput || !form) return;
  const name = nameInput.value.trim();
  if (!name) { toast('Rule name is required', 'warning'); return; }
  const action_data = {};
  const sev = severityInput.value;
  if (sev) action_data.severity = sev;
  const title = titleInput.value.trim();
  if (title) action_data.title = title;
  const msg = messageInput.value.trim();
  if (msg) action_data.message = msg;
  const taskName = taskNameInput.value.trim();
  if (taskName) action_data.task_name = taskName;
  const taskCat = taskCategoryInput.value.trim();
  if (taskCat) action_data.task_category = taskCat;
  const body = {
    name,
    condition_type: conditionInput.value,
    comparison: comparisonInput.value,
    threshold: parseFloat(thresholdInput.value) || 0,
    action_type: actionInput.value,
    action_data,
    cooldown_minutes: parseInt(cooldownInput.value) || 60,
  };
  try {
    await apiPost('/api/weather/action-rules', body);
    toast('Weather action rule created', 'success');
    form.style.display = 'none';
    nameInput.value = '';
    thresholdInput.value = '';
    titleInput.value = '';
    messageInput.value = '';
    taskNameInput.value = '';
    loadWeatherRules();
  } catch(e) {
    toast(e.data?.error || 'Failed to create rule', 'error');
  }
}

async function toggleWeatherRule(id) {
  try {
    await apiPost(`/api/weather/action-rules/${id}/toggle`);
    loadWeatherRules();
  } catch (e) {
    toast(e?.data?.error || 'Failed to toggle rule', 'error');
  }
}

async function deleteWeatherRule(id) {
  if (!confirm('Delete this weather action rule?')) return;
  try {
    await apiDelete('/api/weather/action-rules/' + id);
    toast('Rule deleted', 'success');
    loadWeatherRules();
  } catch(e) { toast('Failed to delete rule', 'error'); }
}

async function evaluateWeatherRules() {
  try {
    const data = await apiPost('/api/weather/evaluate-rules');
    if (data.triggered && data.triggered.length > 0) {
      toast(data.triggered.length + ' rule(s) triggered: ' + data.triggered.map(t => t.name).join(', '), 'warning');
    } else {
      toast('No rules triggered — conditions not met or on cooldown', 'info');
    }
    loadWeatherRules();
  } catch(e) { toast('Failed to evaluate rules', 'error'); }
}

/* ─── Signal Schedule ─── */
let _signalSchedule = [];

function loadSignalSchedule() {
  _signalSchedule = readJsonStorage(localStorage, 'nomad-signal-schedule', []);
  if (!Array.isArray(_signalSchedule)) _signalSchedule = [];
  renderSignalSchedule();
}

function addSignalSchedule() {
  const freqInput = document.getElementById('sig-freq');
  const timeInput = document.getElementById('sig-time');
  const intervalInput = document.getElementById('sig-interval');
  const purposeInput = document.getElementById('sig-purpose');
  if (!freqInput || !timeInput || !intervalInput || !purposeInput) return;
  const freq = freqInput.value.trim();
  const time = timeInput.value;
  const interval = parseInt(intervalInput.value);
  const purpose = purposeInput.value.trim();
  if (!freq || !time) { toast('Frequency and time required', 'warning'); return; }
  _signalSchedule.push({freq, time, interval, purpose, id: Date.now()});
  localStorage.setItem('nomad-signal-schedule', JSON.stringify(_signalSchedule));
  freqInput.value = '';
  purposeInput.value = '';
  renderSignalSchedule();
  toast('Signal schedule added', 'success');
}

function deleteSignalEntry(id) {
  _signalSchedule = _signalSchedule.filter(s => s.id !== id);
  localStorage.setItem('nomad-signal-schedule', JSON.stringify(_signalSchedule));
  renderSignalSchedule();
}

function renderSignalSchedule() {
  const el = document.getElementById('signal-schedule-list');
  const nextEl = document.getElementById('signal-next');
  if (!el) return;
  if (!nextEl) return;
  if (!_signalSchedule.length) {
    el.innerHTML = '<div class="prep-empty-state prep-empty-state-wide">No signal schedules. Add check-in times above.</div>';
    nextEl.hidden = true;
    return;
  }
  el.innerHTML = '<table class="freq-table"><thead><tr><th>Freq/Channel</th><th>Start Time</th><th>Interval</th><th>Purpose</th><th></th></tr></thead><tbody>' +
    _signalSchedule.map(s => `<tr><td class="text-strong">${escapeHtml(s.freq)}</td><td>${s.time}</td><td>Every ${s.interval}h</td><td>${escapeHtml(s.purpose)}</td><td><button type="button" class="signal-delete-btn" data-prep-action="delete-signal-entry" data-signal-id="${s.id}" aria-label="Remove signal schedule for ${escapeHtml(s.freq)}">x</button></td></tr>`).join('') +
    '</tbody></table>';

  // Calculate next check-in
  const now = new Date();
  const nowMins = now.getHours() * 60 + now.getMinutes();
  let nextMin = Infinity, nextEntry = null;
  _signalSchedule.forEach(s => {
    const [h, m] = s.time.split(':').map(Number);
    const startMins = h * 60 + m;
    for (let t = startMins; t < 1440; t += s.interval * 60) {
      if (t > nowMins && t < nextMin) { nextMin = t; nextEntry = s; }
    }
  });
  if (nextEntry) {
    const nh = Math.floor(nextMin / 60), nm = nextMin % 60;
    nextEl.hidden = false;
    nextEl.innerHTML = `<strong>Next check-in:</strong> ${String(nh).padStart(2,'0')}:${String(nm).padStart(2,'0')} on <strong>${escapeHtml(nextEntry.freq)}</strong> ${nextEntry.purpose ? '(' + escapeHtml(nextEntry.purpose) + ')' : ''}`;
  } else { nextEl.hidden = true; }
}

/* ─── CSV Import ─── */
async function importInvCSV() {
  const input = document.getElementById('inv-import-file');
  if (!input || !input.files.length) return;
  const formData = new FormData();
  formData.append('file', input.files[0]);
  try {
    const r = await apiUpload('/api/inventory/import-csv', formData);
    input.value = '';
    toast(`Imported ${r.count} items`, 'success');
    loadInventory();
  } catch(e) { toast(e?.data?.error || 'Import failed', 'error'); input.value = ''; }
}

async function importContactsCSV() {
  const input = document.getElementById('ct-import-file');
  if (!input || !input.files.length) return;
  const formData = new FormData();
  formData.append('file', input.files[0]);
  try {
    const r = await apiUpload('/api/contacts/import-csv', formData);
    input.value = '';
    toast(`Imported ${r.count} contacts`, 'success');
    loadContacts();
  } catch(e) { toast(e?.data?.error || 'Import failed', 'error'); input.value = ''; }
}

/* ─── Meshtastic (Web Serial) ─── */
let _meshPort = null;
/* ─── Compass & Inclinometer ─── */
let _compassActive = false;
function startCompass() {
  if (_compassActive) return;
  const errEl = document.getElementById('compass-error');

  // iOS requires permission request
  if (typeof DeviceOrientationEvent !== 'undefined' && typeof DeviceOrientationEvent.requestPermission === 'function') {
    DeviceOrientationEvent.requestPermission().then(state => {
      if (state === 'granted') _attachCompassListener();
      else if (errEl) { errEl.textContent = 'Permission denied'; }
    }).catch(() => { if (errEl) errEl.textContent = 'Permission request failed'; });
  } else if ('DeviceOrientationEvent' in window) {
    _attachCompassListener();
  } else {
    if (errEl) errEl.textContent = 'Device orientation not supported on this device';
  }
}
let _compassHandler = null;
function _attachCompassListener() {
  _compassActive = true;
  const btn = document.getElementById('compass-start-btn');
  if (btn) { btn.textContent = 'Compass Active'; btn.disabled = true; }
  const compassErrEl = document.getElementById('compass-error');
  if (compassErrEl) compassErrEl.textContent = '';

  if (_compassHandler) window.removeEventListener('deviceorientation', _compassHandler);
  _compassHandler = function(e) {
    // Use webkitCompassHeading on iOS, or derive from alpha on Android
    let heading = e.webkitCompassHeading ?? (e.alpha != null ? (360 - e.alpha) % 360 : null);
    let pitch = e.beta != null ? Math.round(e.beta) : null;
    let roll = e.gamma != null ? Math.round(e.gamma) : null;

    if (heading != null) {
      heading = Math.round(heading);
      const headingEl = document.getElementById('compass-heading');
      if (headingEl) headingEl.textContent = heading + '\u00B0';
      const needleEl = document.getElementById('compass-needle');
      if (needleEl) needleEl.style.transform = `rotate(${heading}deg)`;
      const dirs = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'];
      const cardinalEl = document.getElementById('compass-cardinal');
      if (cardinalEl) cardinalEl.textContent = dirs[Math.round(heading / 22.5) % 16];
    }
    if (pitch != null) { const el = document.getElementById('inclinometer-pitch'); if (el) el.textContent = pitch + '\u00B0'; }
    if (roll != null) { const el = document.getElementById('inclinometer-roll'); if (el) el.textContent = roll + '\u00B0'; }
  };
  window.addEventListener('deviceorientation', _compassHandler, true);

  // Fallback: if no events fire in 3 seconds, show message
  setTimeout(() => {
    const chkEl = document.getElementById('compass-heading');
    if (chkEl && chkEl.textContent === '---\u00B0') {
      const ceEl = document.getElementById('compass-error');
      if (ceEl) ceEl.textContent = 'No sensor data received. Sensors may not be available on this device.';
    }
  }, 3000);
}

async function scanMeshtastic() {
  if (!('serial' in navigator)) { toast('Web Serial not supported. Use Chrome or Edge.', 'error'); return; }
  try {
    const statusEl = document.getElementById('mesh-status');
    const messageInput = document.getElementById('mesh-msg');
    const sendBtn = document.getElementById('mesh-send-btn');
    if (!statusEl || !messageInput || !sendBtn) return;
    _meshPort = await navigator.serial.requestPort();
    await _meshPort.open({baudRate: 115200});
    statusEl.textContent = 'Device connected';
    statusEl.classList.add('tools-status-pill-live');
    statusEl.classList.remove('tools-status-pill-alert');
    messageInput.disabled = false;
    sendBtn.disabled = false;
    appendMeshLogEntry('Radio connected. Listening for traffic.', 'system');
    toast('Meshtastic device connected', 'success');
    readMeshSerial();
  } catch(e) { toast('No device selected or connection failed', 'warning'); }
}

function appendMeshLogEntry(message, tone = 'system') {
  const log = document.getElementById('mesh-log');
  if (!log) return;
  if (!log.dataset.hydrated) {
    log.innerHTML = '';
    log.dataset.hydrated = '1';
  }
  const time = new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit', second:'2-digit'});
  const label = tone === 'outbound'
    ? 'Sent'
    : tone === 'inbound'
      ? 'Received'
      : tone === 'error'
        ? 'Alert'
        : 'System';
  log.insertAdjacentHTML('beforeend', `
    <div class="mesh-log-entry mesh-log-entry-${tone}">
      <span class="mesh-log-entry-time">${time}</span>
      <span class="mesh-log-entry-label">${label}</span>
      <span class="mesh-log-entry-body">${escapeHtml(message)}</span>
    </div>
  `);
  log.scrollTop = log.scrollHeight;
}

let _meshReader = null;
async function readMeshSerial() {
  if (!_meshPort || !_meshPort.readable) return;
  if (_meshReader) { try { _meshReader.cancel(); } catch(e) {} }
  const reader = _meshPort.readable.getReader();
  _meshReader = reader;
  const decoder = new TextDecoder();
  try {
    while (true) {
      const {value, done} = await reader.read();
      if (done) break;
      const text = decoder.decode(value);
      text
        .split(/\r?\n/)
        .map(line => line.trim())
        .filter(Boolean)
        .forEach(line => appendMeshLogEntry(line, 'inbound'));
    }
  } catch(e) {
    const statusEl = document.getElementById('mesh-status');
    if (statusEl) {
      statusEl.textContent = 'Connection lost';
      statusEl.classList.add('tools-status-pill-alert');
      statusEl.classList.remove('tools-status-pill-live');
    }
    const meshMsg = document.getElementById('mesh-msg');
    if (meshMsg) meshMsg.disabled = true;
    const meshSendBtn = document.getElementById('mesh-send-btn');
    if (meshSendBtn) meshSendBtn.disabled = true;
    appendMeshLogEntry('Connection lost', 'error');
  }
}

async function sendMeshMsg() {
  if (!_meshPort || !_meshPort.writable) return;
  const messageInput = document.getElementById('mesh-msg');
  if (!messageInput) return;
  const msg = messageInput.value.trim();
  if (!msg) return;
  const writer = _meshPort.writable.getWriter();
  await writer.write(new TextEncoder().encode(msg + '\n'));
  writer.releaseLock();
  messageInput.value = '';
  appendMeshLogEntry(msg, 'outbound');
}

// ── Mesh Node Map Overlay ──
async function loadMeshMapOverlay() {
  if (typeof _map === 'undefined' || !_map) return;
  const nodes = await safeFetch('/api/mesh/nodes', {}, []);
  if (!nodes.length) return;

  // Remove existing mesh markers
  document.querySelectorAll('.mesh-map-marker').forEach(m => m.remove());

  nodes.forEach(n => {
    if (!n.lat || !n.lng) return;
    const el = document.createElement('div');
    el.className = 'mesh-map-marker';
    el.style.cssText = `width:12px;height:12px;border-radius:50%;background:${getThemeCssVar('--green', '#4caf50')};border:2px solid ${getThemeCssVar('--text-inverse', '#fff')};box-shadow:0 0 6px rgba(0,0,0,0.3);cursor:pointer;`;
    el.title = (n.name || 'Mesh Node') + (n.rssi ? ' (RSSI: ' + n.rssi + ')' : '');

    if (typeof maplibregl !== 'undefined') {
      new maplibregl.Marker({element: el}).setLngLat([n.lng, n.lat]).addTo(_map);
    }
  });
}

/* ─── Garden Map Overlay ─── */
let _gardenOverlayVisible = true;
async function loadGardenOverlay() {
  if (typeof _map === 'undefined' || !_map) return;
  try {
    const geo = await safeFetch('/api/garden/plots/geo', {}, null);
    if (!geo || !geo.features || !geo.features.length) return;

    if (_map.getSource('garden-plots')) {
      _map.getSource('garden-plots').setData(geo);
      return;
    }

    _map.addSource('garden-plots', {type: 'geojson', data: geo});

    // Fill layer for polygons
    const themeGreen = getThemeCssVar('--green', '#4caf50');
    const themeInverse = getThemeCssVar('--text-inverse', '#fff');
    _map.addLayer({
      id: 'garden-plots-fill', type: 'fill', source: 'garden-plots',
      filter: ['==', '$type', 'Polygon'],
      paint: {'fill-color': themeGreen, 'fill-opacity': 0.25}
    });
    // Outline for polygons
    _map.addLayer({
      id: 'garden-plots-outline', type: 'line', source: 'garden-plots',
      filter: ['==', '$type', 'Polygon'],
      paint: {'line-color': themeGreen, 'line-width': 2}
    });
    // Circle for points (plots without boundary)
    _map.addLayer({
      id: 'garden-plots-circle', type: 'circle', source: 'garden-plots',
      filter: ['==', '$type', 'Point'],
      paint: {'circle-radius': 8, 'circle-color': themeGreen, 'circle-opacity': 0.6, 'circle-stroke-width': 2, 'circle-stroke-color': themeInverse}
    });
    // Labels
    _map.addLayer({
      id: 'garden-plots-label', type: 'symbol', source: 'garden-plots',
      layout: {
        'text-field': ['get', 'name'], 'text-size': 12, 'text-offset': [0, 1.5],
        'text-anchor': 'top', 'text-allow-overlap': true,
      },
      paint: {'text-color': themeGreen, 'text-halo-color': '#000', 'text-halo-width': 1}
    });

    // Popup on click
    _map.on('click', 'garden-plots-fill', (e) => {
      const p = e.features[0].properties;
      new maplibregl.Popup().setLngLat(e.lngLat).setHTML(
        renderMapPopupShell({
          title: escapeHtml(p.name),
          meta: 'Garden plot',
          facts: [
            { label: 'Footprint', value: `${escapeHtml(String(p.width_ft))} ft x ${escapeHtml(String(p.length_ft))} ft` },
            { label: 'Sun', value: escapeHtml(p.sun_exposure) },
            { label: 'Soil', value: escapeHtml(p.soil_type) }
          ],
          notes: p.notes ? escapeHtml(p.notes) : '',
          coords: `${e.lngLat.lat.toFixed(5)}, ${e.lngLat.lng.toFixed(5)}`
        })
      ).addTo(_map);
    });
    _map.on('click', 'garden-plots-circle', (e) => {
      const p = e.features[0].properties;
      new maplibregl.Popup().setLngLat(e.lngLat).setHTML(
        renderMapPopupShell({
          title: escapeHtml(p.name),
          meta: 'Garden plot',
          facts: [
            { label: 'Footprint', value: `${escapeHtml(String(p.width_ft))} ft x ${escapeHtml(String(p.length_ft))} ft` },
            { label: 'Sun', value: escapeHtml(p.sun_exposure) },
            { label: 'Soil', value: escapeHtml(p.soil_type) }
          ],
          coords: `${e.lngLat.lat.toFixed(5)}, ${e.lngLat.lng.toFixed(5)}`
        })
      ).addTo(_map);
    });
    _map.on('mouseenter', 'garden-plots-fill', () => _map.getCanvas().style.cursor = 'pointer');
    _map.on('mouseleave', 'garden-plots-fill', () => _map.getCanvas().style.cursor = '');
    _map.on('mouseenter', 'garden-plots-circle', () => _map.getCanvas().style.cursor = 'pointer');
    _map.on('mouseleave', 'garden-plots-circle', () => _map.getCanvas().style.cursor = '');
  } catch(e) {}
}

function toggleGardenOverlay() {
  if (!_map) return;
  _gardenOverlayVisible = !_gardenOverlayVisible;
  const vis = _gardenOverlayVisible ? 'visible' : 'none';
  ['garden-plots-fill','garden-plots-outline','garden-plots-circle','garden-plots-label'].forEach(id => {
    if (_map.getLayer(id)) _map.setLayoutProperty(id, 'visibility', vis);
  });
}

/* ─── Supply Chain Map Overlay ─── */
let _supplyChainVisible = false;
async function loadSupplyChainOverlay() {
  if (typeof _map === 'undefined' || !_map) return;
  try {
    const geo = await safeFetch('/api/federation/supply-chain', {}, null);
    if (!geo || !geo.features || !geo.features.length) return;

    if (_map.getSource('supply-chain')) {
      _map.getSource('supply-chain').setData(geo);
      return;
    }

    _map.addSource('supply-chain', {type: 'geojson', data: geo});

    // Peer nodes
    _map.addLayer({
      id: 'supply-chain-nodes', type: 'circle', source: 'supply-chain',
      filter: ['==', ['get', 'type'], 'peer'],
      paint: {
        'circle-radius': 10, 'circle-color': ['get', 'color'],
        'circle-stroke-width': 2, 'circle-stroke-color': getThemeCssVar('--text-inverse', '#fff')
      },
      layout: {visibility: 'none'}
    });
    // Peer labels
    _map.addLayer({
      id: 'supply-chain-labels', type: 'symbol', source: 'supply-chain',
      filter: ['==', ['get', 'type'], 'peer'],
      layout: {
        'text-field': ['get', 'name'], 'text-size': 11,
        'text-offset': [0, 1.8], 'text-anchor': 'top',
        'text-allow-overlap': true, visibility: 'none',
      },
      paint: {'text-color': getThemeCssVar('--text-inverse', '#fff'), 'text-halo-color': '#000', 'text-halo-width': 1}
    });
    // Trade route lines
    _map.addLayer({
      id: 'supply-chain-routes', type: 'line', source: 'supply-chain',
      filter: ['==', ['get', 'type'], 'trade_route'],
      paint: {
        'line-color': getThemeCssVar('--warning', '#ff9800'), 'line-width': ['get', 'match_count'],
        'line-opacity': 0.7, 'line-dasharray': [2, 2]
      },
      layout: {visibility: 'none'}
    });

    // Popup on peer click
    _map.on('click', 'supply-chain-nodes', (e) => {
      const p = e.features[0].properties;
      const offers = safeJsonParse(p.offers, []);
      const requests = safeJsonParse(p.requests, []);
      new maplibregl.Popup().setLngLat(e.lngLat).setHTML(
        renderMapPopupShell({
          title: escapeHtml(p.name),
          meta: 'Supply partner',
          facts: [
            { label: 'Trust', value: escapeHtml(p.trust_level) }
          ],
          sections: [
            {
              label: 'Offers',
              items: offers.map(o => `${escapeHtml(o.item)} · x${escapeHtml(String(o.qty))}`)
            },
            {
              label: 'Requests',
              items: requests.map(r => `${escapeHtml(r.item)} · x${escapeHtml(String(r.qty))} · ${escapeHtml(r.urgency)}`)
            }
          ],
          coords: `${e.lngLat.lat.toFixed(5)}, ${e.lngLat.lng.toFixed(5)}`
        })
      ).addTo(_map);
    });
    // Popup on trade route click
    _map.on('click', 'supply-chain-routes', (e) => {
      const p = e.features[0].properties;
      const items = safeJsonParse(p.matched_items, []);
      new maplibregl.Popup().setLngLat(e.lngLat).setHTML(
        renderMapPopupShell({
          title: 'Trade route',
          meta: `${escapeHtml(p.from)} ↔ ${escapeHtml(p.to)}`,
          sections: [
            {
              label: 'Matching items',
              items: items.map(item => escapeHtml(item))
            }
          ],
          coords: `${e.lngLat.lat.toFixed(5)}, ${e.lngLat.lng.toFixed(5)}`
        })
      ).addTo(_map);
    });
    _map.on('mouseenter', 'supply-chain-nodes', () => _map.getCanvas().style.cursor = 'pointer');
    _map.on('mouseleave', 'supply-chain-nodes', () => _map.getCanvas().style.cursor = '');
  } catch(e) {}
}

function toggleSupplyChainOverlay() {
  if (!_map) return;
  _supplyChainVisible = !_supplyChainVisible;
  const vis = _supplyChainVisible ? 'visible' : 'none';
  ['supply-chain-nodes','supply-chain-labels','supply-chain-routes'].forEach(id => {
    if (_map.getLayer(id)) _map.setLayoutProperty(id, 'visibility', vis);
  });
  if (_supplyChainVisible && !_map.getSource('supply-chain')) loadSupplyChainOverlay();
}

/* ─── Contour Line Overlay ─── */
let _contourVisible = false;
let _contourDebounceTimer = null;
let _contourLastCenter = null;

function toggleContourOverlay() {
  if (!_map) { toast('Open the map first', 'warning'); return; }
  _contourVisible = !_contourVisible;
  const btn = document.getElementById('contour-btn');
  if (btn) btn.style.background = _contourVisible ? 'var(--accent-dim)' : '';

  if (_contourVisible) {
    loadContourOverlay();
    // Add moveend listener for auto-refresh
    _map.on('moveend', _contourMoveHandler);
  } else {
    ['contour-lines', 'contour-lines-major', 'contour-labels'].forEach(id => {
      if (_map.getLayer(id)) _map.setLayoutProperty(id, 'visibility', 'none');
    });
    _map.off('moveend', _contourMoveHandler);
  }
}

function _contourMoveHandler() {
  if (!_contourVisible) return;
  const center = _map.getCenter();
  // Only reload if moved significantly (> ~5km)
  if (_contourLastCenter) {
    const dlat = Math.abs(center.lat - _contourLastCenter.lat);
    const dlng = Math.abs(center.lng - _contourLastCenter.lng);
    if (dlat < 0.05 && dlng < 0.05) return;
  }
  clearTimeout(_contourDebounceTimer);
  _contourDebounceTimer = setTimeout(() => loadContourOverlay(), 1500);
}

async function loadContourOverlay() {
  if (!_map) return;
  const center = _map.getCenter();
  _contourLastCenter = { lat: center.lat, lng: center.lng };
  const data = await safeFetch(`/api/maps/contours?lat=${center.lat}&lng=${center.lng}&radius_km=50&interval=100`);
  if (!data) return;

  if (data.message) {
    toast(data.message, 'info');
  }

  if (!data.features || data.features.length === 0) return;

  // Remove old source/layers if they exist
  ['contour-labels', 'contour-lines-major', 'contour-lines'].forEach(id => {
    if (_map.getLayer(id)) _map.removeLayer(id);
  });
  if (_map.getSource('contours')) _map.removeSource('contours');

  _map.addSource('contours', { type: 'geojson', data: data });

  // Regular contour lines (thin)
  _map.addLayer({
    id: 'contour-lines',
    type: 'line',
    source: 'contours',
    filter: ['!=', ['%', ['get', 'elevation'], 500], 0],
    paint: {
      'line-color': '#8B6914',
      'line-width': 0.8,
      'line-opacity': 0.5
    }
  });

  // Major contour lines (every 500m — thicker)
  _map.addLayer({
    id: 'contour-lines-major',
    type: 'line',
    source: 'contours',
    filter: ['==', ['%', ['get', 'elevation'], 500], 0],
    paint: {
      'line-color': '#8B6914',
      'line-width': 2,
      'line-opacity': 0.8
    }
  });

  // Labels on major contours
  _map.addLayer({
    id: 'contour-labels',
    type: 'symbol',
    source: 'contours',
    filter: ['==', ['%', ['get', 'elevation'], 500], 0],
    layout: {
      'symbol-placement': 'line',
      'text-field': ['get', 'label'],
      'text-size': 10,
      'text-max-angle': 25,
      'text-allow-overlap': false,
    },
    paint: {
      'text-color': '#6B5010',
      'text-halo-color': 'rgba(255,252,240,0.8)',
      'text-halo-width': 1.5,
    }
  });
}

/* ─── Garden Plot Polygon Drawing ─── */
let _drawingGarden = false, _gardenPoints = [], _gardenPlotEditId = null;
function startGardenDraw(plotId) {
  _drawingGarden = true;
  _gardenPoints = [];
  _gardenPlotEditId = plotId;
  toast('Click on map to draw garden boundary. Double-click to finish.', 'info');
}
// Integrated into map click handler via _drawingGarden flag — see map click handler
async function finishGardenDraw() {
  if (_gardenPoints.length < 3) { toast('Need at least 3 points', 'warning'); _drawingGarden = false; _gardenPoints = []; return; }
  _gardenPoints.push(_gardenPoints[0]); // Close polygon
  const geojson = JSON.stringify({type: 'Polygon', coordinates: [_gardenPoints]});
  const center = _gardenPoints.reduce((a, p) => [a[0]+p[0], a[1]+p[1]], [0,0]).map(v => v / (_gardenPoints.length - 1));
  try {
    await apiPut(`/api/garden/plots/${_gardenPlotEditId}`, {boundary_geojson: geojson, lng: center[0], lat: center[1]});
    toast('Garden boundary saved', 'success');
    loadGardenOverlay();
  } catch (e) {
    toast(e?.data?.error || e?.message || 'Failed to save garden boundary', 'error');
  }
  _drawingGarden = false;
  _gardenPoints = [];
}

/* ─── Barcode Scanner ─── */
let _barcodeStream = null;
async function startBarcodeScanner() {
  try {
    const video = document.getElementById('barcode-video');
    const resultEl = document.getElementById('barcode-result');
    if (!video || !resultEl) return;
    const stream = await navigator.mediaDevices.getUserMedia({video: {facingMode: 'environment'}});
    _barcodeStream = stream;
    video.srcObject = stream;
    video.style.display = 'block';
    if ('BarcodeDetector' in window) {
      const detector = new BarcodeDetector();
      const scanLoop = async () => {
        if (!_barcodeStream) return;
        try {
          const barcodes = await detector.detect(video);
          if (barcodes.length > 0) {
            const code = barcodes[0].rawValue;
            resultEl.innerHTML = `<div class="scan-result-title">Scanned: ${escapeHtml(code)}</div><div class="scan-results-actions"><button type="button" class="btn btn-sm btn-primary" data-shell-action="barcode-to-inventory" data-barcode-code="${escapeAttr(code)}">Add to Inventory</button></div>`;
            toast(`Barcode: ${code}`, 'success');
            return;
          }
        } catch(e) {}
        if (_barcodeStream) requestAnimationFrame(scanLoop);
      };
      requestAnimationFrame(scanLoop);
    } else {
      resultEl.innerHTML = '<div class="scan-status-warning">BarcodeDetector API not available. Use Chrome 83+ or enable chrome://flags/#enable-experimental-web-platform-features</div>';
    }
  } catch(e) { toast('Camera access denied', 'error'); }
}

function stopBarcodeScanner() {
  if (_barcodeStream) { _barcodeStream.getTracks().forEach(t => t.stop()); _barcodeStream = null; }
  const video = document.getElementById('barcode-video');
  if (!video) return;
  video.style.display = 'none';
}

function barcodeToInventory(code) {
  stopBarcodeScanner();
  document.querySelector('[data-tab="preparedness"]')?.click();
  setTimeout(() => {
    switchPrepSub('inventory');
    showInvForm();
    const barcodeInput = document.getElementById('inv-barcode');
    if (!barcodeInput) return;
    barcodeInput.value = code;
  }, 300);
}

