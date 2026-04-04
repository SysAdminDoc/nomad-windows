/* ─── Services ─── */
const SVC_ICONS = {
  ollama: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2a7 7 0 0 0-7 7c0 3.5 2.5 6.5 7 13 4.5-6.5 7-9.5 7-13a7 7 0 0 0-7-7z"/><circle cx="12" cy="9" r="2.5"/></svg>',
  kiwix: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/><path d="M8 7h8M8 11h5"/></svg>',
  cyberchef: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-4"/></svg>',
  kolibri: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c0 1.66 2.69 3 6 3s6-1.34 6-3v-5"/></svg>',
  qdrant: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>',
  stirling: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M9 13h6M9 17h4"/></svg>',
};
const SVC = {
  ollama:    { name:'Ollama (AI Chat)',             desc:'Local AI chat powered by LLMs. Run Llama 3, Mistral, and more entirely offline.', tip:'Go to the AI Chat tab to start a private conversation.', dlSize:'~310 MB' },
  kiwix:     { name:'Kiwix (Information Library)',   desc:'Offline Wikipedia, medical references, survival guides, and ebooks.', hint:'Download content from the Library tab to get started.', tip:'Open in browser to browse your downloaded content packs.', dlSize:'~15 MB' },
  cyberchef: { name:'CyberChef (Data Tools)',        desc:'Encryption, encoding, hashing, and data analysis toolkit by GCHQ.', tip:'Open in browser for 400+ data transformation operations.', dlSize:'~20 MB' },
  kolibri:   { name:'Kolibri (Education Platform)',  desc:'Offline Khan Academy courses, textbooks, and educational content.', requires:'Python on PATH', tip:'Open in browser to access courses and learning materials.', dlSize:'~200 MB' },
  qdrant:    { name:'Qdrant (Vector DB)',           desc:'Vector database enabling AI to search your uploaded documents.', tip:'Enable "Search My Documents" in AI Chat to use this.', dlSize:'~30 MB' },
  stirling:  { name:'Stirling PDF',                  desc:'Offline PDF toolkit — merge, split, compress, convert, OCR, and 50+ tools.', requires:'Java 17+ (<a href="https://adoptium.net">adoptium.net</a>)', tip:'Open in browser to work with PDFs without cloud services.', dlSize:'~400 MB' },
  flatnotes: { name:'FlatNotes (Notes App)',            desc:'Simple, beautiful markdown note-taking with tags, search, and flat-file storage.', requires:'Python 3.9+', tip:'Open in browser for a full-featured note-taking experience.', dlSize:'~20 MB' },
};

let _servicesLoaded = false;
async function loadServices(servicesData = null) {
  const grid = document.getElementById('services-grid');
  if (!grid) return;
  if (!_servicesLoaded) {
    grid.innerHTML = Array(6).fill('<div class="skeleton skeleton-card"></div>').join('');
  }
  try {
    const services = Array.isArray(servicesData)
      ? servicesData
      : await (await fetch('/api/services')).json();
    _lastServicesData = services;
    _servicesLoaded = true;
    grid.innerHTML = services.map(s => {
      const info = SVC[s.id] || { name:s.id, desc:'' };
      const prog = s.progress || {};
      const isInstalling = prog.status === 'downloading' || prog.status === 'extracting' || (prog.status && prog.status.startsWith('downloading'));
      const statusClass = isInstalling ? 'installing' : !s.installed ? 'not-installed' : s.running ? 'running' : 'stopped';
      const statusText = isInstalling ? 'Installing' : !s.installed ? 'Not Installed' : s.running ? 'Running' : 'Stopped';

      const busy = svcBusy(s.id);
      let actions = '';
      if (busy) {
        actions = `<button class="btn btn-sm service-busy-btn" disabled>
          <span class="inline-status-spinner inline-status-spinner-md"></span>Working…
        </button>`;
      } else if (isInstalling) {
        actions = `<button class="btn btn-sm" disabled>Installing…</button>`;
      } else if (!s.installed) {
        actions = `<button class="btn btn-sm btn-primary" type="button" data-shell-action="install-service" data-service-id="${escapeAttr(s.id)}">Install${info.dlSize ? ' ('+info.dlSize+')' : ''}</button>`;
      } else if (s.running) {
        actions = `
          ${s.port ? (s.id === 'ollama' ? `<button class="btn btn-sm btn-open-svc" data-tab-target="ai-chat">Open AI Chat</button>` : `<button class="btn btn-sm btn-open-svc" data-app-frame-title="${escapeAttr(info.name)}" data-app-frame-url="http://localhost:${s.port}">Open</button>`) : ''}
          <button class="btn btn-sm btn-danger" type="button" data-shell-action="stop-service" data-service-id="${escapeAttr(s.id)}">Stop</button>
          <button class="btn btn-sm" type="button" data-shell-action="restart-service" data-service-id="${escapeAttr(s.id)}">Restart</button>
          <button class="btn btn-sm btn-ghost btn-danger" type="button" data-shell-action="uninstall-service" data-service-id="${escapeAttr(s.id)}">Uninstall</button>
        `;
      } else {
        actions = `
          <button class="btn btn-sm btn-primary" type="button" data-shell-action="start-service" data-service-id="${escapeAttr(s.id)}">Start</button>
          <button class="btn btn-sm btn-ghost btn-danger" type="button" data-shell-action="uninstall-service" data-service-id="${escapeAttr(s.id)}">Uninstall</button>
        `;
      }

      let progressHtml = '';
      if (isInstalling) {
        const dlInfo = prog.total > 0 ? `${formatBytes(prog.downloaded||0)} / ${formatBytes(prog.total)}` : '';
        progressHtml = `<div class="progress-wrap">
          <div class="progress-bar"><div class="fill" style="width:${prog.percent||0}%"></div></div>
          <div class="progress-info"><span>${prog.status||''}${prog.speed ? ' - '+prog.speed : ''}${dlInfo ? ' - '+dlInfo : ''}</span><span>${prog.percent||0}%</span></div>
        </div>`;
      }

      let errorHtml = '';
      if (prog.status === 'error' && prog.error) {
        errorHtml = `<div class="svc-error">${escapeHtml(prog.error)} <button class="btn btn-sm layout-margin-left-6" type="button" data-shell-action="install-service" data-service-id="${escapeAttr(s.id)}">Retry</button></div>`;
      }

      let prereqHtml = '';
      if (!s.installed && info.requires) {
        prereqHtml = `<div class="svc-prereq">Requires: ${escapeHtml(info.requires)}</div>`;
      }

      let hintHtml = '';
      if (s.installed && !s.running && info.hint) {
        hintHtml = `<div class="service-hint-note">${escapeHtml(info.hint)}</div>`;
      }

      let tipHtml = '';
      if (s.running && info.tip) {
        tipHtml = `<div class="service-tip-note">${escapeHtml(info.tip)}</div>`;
      }

      const icon = SVC_ICONS[s.id] || '';
      const svcVariant = !s.installed ? 'svc-not-installed' : s.running ? 'svc-running' : 'svc-stopped';
      return `<div class="service-card ${svcVariant}">
        <div class="card-header">
          <div class="service-card-head">
            <span class="service-card-icon">${icon}</span>
            <h3>${info.name}</h3>
          </div>
          <span class="badge ${statusClass}"><span class="dot"></span>${statusText}</span>
        </div>
        <p class="desc">${info.desc}</p>
        ${prereqHtml}${hintHtml}${tipHtml}
        <div class="meta"><span>${s.disk_used && s.disk_used !== '0 B' ? 'Using '+s.disk_used : ''}</span>${s.running ? '<span class="service-card-ready">Ready</span>' : ''}</div>
        ${progressHtml}${errorHtml}
        <div class="card-actions">${actions}</div>
      </div>`;
    }).join('');

    // Welcome banner if nothing is installed
    const anyInstalled = services.some(s => s.installed);
    const welcomeEl = document.getElementById('welcome-banner');
    const onboardingIncomplete = window.NOMAD_FIRST_RUN_COMPLETE === false;
    setShellVisibility(welcomeEl, !onboardingIncomplete && !anyInstalled);
  } catch(e) {
    // error logged silently
    if (!_servicesLoaded) {
      const grid = document.getElementById('services-grid');
      grid.innerHTML = '<div class="utility-empty-state service-load-error">Failed to load services. <button class="btn btn-sm" type="button" data-shell-action="reload-services">Retry</button></div>';
    }
  }
}

let _busyServices = new Set();
function svcBusy(id) { return _busyServices.has(id); }

// Approximate download sizes in MB for disk space check
const SVC_SIZES_MB = {ollama:310, kiwix:15, cyberchef:20, kolibri:300, qdrant:30, stirling:500};

async function installService(id) {
  // Check disk space first
  const neededMB = SVC_SIZES_MB[id] || 100;
  try {
    const sys = await (await fetch('/api/system')).json();
    const freeMB = (sys.disk_free_bytes || 0) / (1024*1024);
    if (freeMB > 0 && freeMB < neededMB * 1.5) {
      toast(`Low disk space! ${Math.round(freeMB)} MB free, need ~${neededMB} MB. Install may fail.`, 'warning');
    }
  } catch(e) {}
  // Check prereqs
  try {
    const p = await (await fetch(`/api/services/${id}/prereqs`)).json();
    if (!p.met) { toast(p.message || `Prerequisites not met for ${SVC[id]?.name||id}`, 'error'); return; }
    if (p.message) toast(p.message, 'info');
  } catch(e) { toast('Failed to check prerequisites', 'warning'); }
  try {
    const r = await fetch(`/api/services/${id}/install`, {method:'POST'});
    const d = await r.json();
    if (d.status === 'already_installing') { toast('Already installing...', 'info'); return; }
    toast(`Installing ${SVC[id]?.name||id} (${SVC[id]?.dlSize || '?'})...`, 'info');
    pollServices();
  } catch(e) { toast(`Failed to install ${SVC[id]?.name||id}`, 'error'); }
}
async function startService(id) {
  _busyServices.add(id); loadServices();
  try {
    const r = await (await fetch(`/api/services/${id}/start`, {method:'POST'})).json();
    if (r.error) { toast(r.error, 'error'); } else { toast(`${SVC[id]?.name||id} started`, 'success'); }
  } catch(e) { toast(`Failed to start ${SVC[id]?.name||id}`, 'error'); }
  finally { _busyServices.delete(id); loadServices(); }
}
async function stopService(id) {
  _busyServices.add(id); loadServices();
  try {
    await fetch(`/api/services/${id}/stop`, {method:'POST'});
    toast(`${SVC[id]?.name||id} stopped`, 'warning');
  } catch(e) { toast(`Failed to stop ${SVC[id]?.name||id}`, 'error'); }
  finally { _busyServices.delete(id); loadServices(); }
}
async function restartService(id) {
  _busyServices.add(id); loadServices();
  toast(`Restarting ${SVC[id]?.name||id}...`, 'info');
  try {
    const r = await (await fetch(`/api/services/${id}/restart`, {method:'POST'})).json();
    if (r.error) { toast(r.error, 'error'); } else { toast(`${SVC[id]?.name||id} restarted`, 'success'); }
  } catch(e) { toast(`Failed to restart ${SVC[id]?.name||id}`, 'error'); }
  finally { _busyServices.delete(id); loadServices(); }
}
async function uninstallService(id) {
  _busyServices.add(id); loadServices();
  try {
    await fetch(`/api/services/${id}/uninstall`, {method:'POST'});
    toast(`${SVC[id]?.name||id} uninstalled`, 'warning');
  } catch(e) { toast(`Failed to uninstall ${SVC[id]?.name||id}`, 'error'); }
  finally { _busyServices.delete(id); loadServices(); }
}

async function startAllServices() {
  toast('Starting all services...', 'info');
  const r = await safeFetch('/api/services/start-all', {method:'POST'}, null);
  if (!r) { toast('Failed to start services', 'error'); return; }
  if (r.started?.length) toast(`Started ${r.started.length} service${r.started.length>1?'s':''}`, 'success');
  if (r.errors?.length) r.errors.forEach(e => toast(e, 'error'));
  loadServices();
}
async function stopAllServices() {
  toast('Stopping all services...', 'warning');
  const r = await safeFetch('/api/services/stop-all', {method:'POST'}, null);
  if (!r) { toast('Failed to stop services', 'error'); return; }
  toast(`Stopped ${r.stopped?.length||0} service${(r.stopped?.length||0)>1?'s':''}`, 'warning');
  loadServices();
}

let _pollInt = null;
let _lastServicesData = [];
let _prevInstalling = new Set();
let _pollCount = 0;
function stopServicesPolling() {
  if (_pollInt) {
    clearInterval(_pollInt);
    _pollInt = null;
  }
  window.NomadShellRuntime?.stopInterval('services.install-progress');
}
function pollServices() {
  if (_pollInt) return;
  _pollCount = 0;
  const runner = async () => {
    _pollCount++;
    if (_pollCount > 1200) { // 30 min at 1.5s interval
      stopServicesPolling();
      toast('Service install polling timed out after 30 minutes', 'warning');
      return;
    }
    await loadServices();
    const nowInstalling = new Set();
    const nowComplete = new Set();
    const nowError = new Set();
    _lastServicesData.forEach(s => {
      const p = s.progress;
      if (p && (p.status === 'downloading' || p.status === 'extracting' || p.status?.startsWith('downloading'))) nowInstalling.add(s.id);
      if (p && p.status === 'complete') nowComplete.add(s.id);
      if (p && p.status === 'error') nowError.add(s.id);
    });
    // Notify on completion — was installing, now complete
    _prevInstalling.forEach(id => {
      if (!nowInstalling.has(id) && !nowError.has(id)) {
        const name = SVC[id]?.name || id;
        if (nowComplete.has(id) || _lastServicesData.find(s => s.id === id)?.installed) {
          toast(`${name} installed successfully! Click Start to use it.`, 'success');
          sendNotification('Install Complete', `${name} is ready`);
        }
      }
    });
    _prevInstalling = nowInstalling;
    if (!nowInstalling.size) stopServicesPolling();
  };
  if (window.NomadShellRuntime) {
    _pollInt = window.NomadShellRuntime.startInterval('services.install-progress', runner, 1500, {
      tabId: 'services',
      requireVisible: true,
    });
    return;
  }
  _pollInt = setInterval(runner, 1500);
}

/* ─── AI Chat ─── */
let _chatReady = false;
let _chatReadyPoll = null;
function stopChatReadyPoll() {
  if (_chatReadyPoll) {
    clearInterval(_chatReadyPoll);
    _chatReadyPoll = null;
  }
  window.NomadShellRuntime?.stopInterval('ai-chat.model-ready');
}

async function loadModels() {
  try {
    const models = await (await fetch('/api/ai/models')).json();
    const sel = document.getElementById('model-select');
    if (!sel) return;
    if (!models.length) {
      sel.innerHTML = '<option value="">No models yet — click "+ Get Model"</option>';
      setChatReady(false, 'No AI models downloaded');
      startChatReadyPoll();
    } else {
      sel.innerHTML = models.map(m => `<option value="${escapeAttr(m.name)}">${escapeHtml(m.name)} (${(m.size/1e9).toFixed(1)}GB)</option>`).join('');
      // Pre-warm the model — send a tiny request to load it into VRAM
      setChatReady(false, 'Loading AI model into memory...');
      warmupModel(models[0].name);
    }
  } catch(e) {
    const sel = document.getElementById('model-select');
    if (sel) sel.innerHTML = '<option value="">Failed to load models</option>';
    setChatReady(false, 'AI service starting...');
    startChatReadyPoll();
  }
}

async function warmupModel(modelName) {
  try {
    const resp = await fetch('/api/ai/chat', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({model: modelName, messages: [{role:'user', content:'hi'}]}),
    });
    if (!resp.ok) throw new Error('Warmup failed: ' + resp.status);
    // Read and discard the streaming response
    const reader = resp.body.getReader();
    while (true) { const {done} = await reader.read(); if (done) break; }
    setChatReady(true);
    toast('AI assistant ready', 'success');
  } catch(e) {
    // If warmup fails, still enable chat — the user's first real message will trigger loading
    setChatReady(true);
  }
}

function setChatReady(ready, reason) {
  _chatReady = ready;
  const btn = document.getElementById('send-btn');
  const input = document.getElementById('chat-input');
  if (btn) btn.disabled = !ready;
  if (input) { input.disabled = !ready; input.placeholder = ready ? 'Type a message... (Enter to send, Shift+Enter for newline, drop files)' : (reason || 'AI service starting...'); }
  if (ready) stopChatReadyPoll();
}

function startChatReadyPoll() {
  if (_chatReadyPoll) return;
  const runner = async () => {
    try {
      const models = await (await fetch('/api/ai/models')).json();
      if (models.length) {
        stopChatReadyPoll();
        const sel = document.getElementById('model-select');
        sel.innerHTML = models.map(m => `<option value="${escapeAttr(m.name)}">${escapeHtml(m.name)} (${(m.size/1e9).toFixed(1)}GB)</option>`).join('');
        setChatReady(false, 'Loading AI model into memory...');
        warmupModel(models[0].name);
      }
    } catch {}
  };
  if (window.NomadShellRuntime) {
    _chatReadyPoll = window.NomadShellRuntime.startInterval('ai-chat.model-ready', runner, 3000, {
      tabId: 'ai-chat',
      requireVisible: true,
    });
    return;
  }
  _chatReadyPoll = setInterval(runner, 3000);
}

/* managePullModel replaced by inline model picker */

let _pullPoll = null;
let _pullPollCount = 0;
function stopPullProgressPolling() {
  if (_pullPoll) {
    clearInterval(_pullPoll);
    _pullPoll = null;
  }
  window.NomadShellRuntime?.stopInterval('ai-chat.pull-progress');
}
function pollPullProgress() {
  if (_pullPoll) return;
  _pullPollCount = 0;
  const runner = async () => {
    _pullPollCount++;
    if (_pullPollCount > 1800) { // 30 min at 1s interval
      stopPullProgressPolling();
      toast('Model pull polling timed out after 30 minutes', 'warning');
      return;
    }
    try {
    const p = await (await fetch('/api/ai/pull-progress')).json();
    const bar = document.getElementById('pull-progress-bar');
    if (p.status === 'pulling') {
      bar.style.display = 'block';
      document.getElementById('pull-fill').style.width = p.percent + '%';
      let detail = p.detail || '...';
      if (p.queue_total > 1) detail = `[${p.queue_pos || '?'}/${p.queue_total}] ${detail}`;
      document.getElementById('pull-detail').textContent = detail;
      document.getElementById('pull-pct').textContent = p.percent + '%';
    } else {
      if (p.status === 'complete') {
        toast(`Model ${p.model} ready!`, 'success');
        loadModels();
        // If queue is still active, keep polling for next model
        if (p.queue_active) return;
      }
      if (p.status === 'error') toast(`Model pull failed: ${p.detail}`, 'error');
      if (!p.queue_active) {
        bar.style.display = 'none';
        stopPullProgressPolling();
        if (p.queue?.length > 0) toast('All queued models finished downloading!', 'success');
        loadModelManager();
      }
    }
    } catch(e) {}
  };
  if (window.NomadShellRuntime) {
    _pullPoll = window.NomadShellRuntime.startInterval('ai-chat.pull-progress', runner, 1000, {
      tabId: 'ai-chat',
      requireVisible: true,
    });
    return;
  }
  _pullPoll = setInterval(runner, 1000);
}

/* ─── Conversations ─── */
async function loadConversations() {
  try {
    const r = await fetch('/api/conversations');
    if (!r.ok) { allConvos = []; renderConvoList(); return; }
    const d = await r.json();
    allConvos = Array.isArray(d) ? d : [];
  } catch(e) { allConvos = []; }
  renderConvoList();
}
function renderConvoList() {
  const el = document.getElementById('convo-list');
  if (!allConvos.length) {
    el.innerHTML = '<div class="sidebar-empty-state convo-list-empty">No conversations yet</div>';
    return;
  }
  el.innerHTML = allConvos.map(c => {
    const branchBadge = (c.branch_count && c.branch_count > 0) ? `<span class="convo-branch-badge" title="${c.branch_count} branch${c.branch_count>1?'es':''}">${c.branch_count}</span>` : '';
    return `
    <div class="convo-item ${c.id===currentConvoId?'active':''}" data-convo-id="${c.id}" data-chat-action="select-conversation" data-chat-dblclick="rename-conversation" role="button" tabindex="0">
      <span class="convo-title">${escapeHtml(c.title)}${branchBadge}</span>
      <span class="convo-actions">
        <button type="button" class="convo-action-btn" data-chat-action="rename-conversation" data-convo-id="${c.id}" data-stop-propagation aria-label="Rename conversation" title="Rename">&#9998;</button>
        <button type="button" class="convo-action-btn convo-del" data-chat-action="delete-conversation" data-convo-id="${c.id}" data-stop-propagation aria-label="Delete conversation" title="Delete">x</button>
      </span>
    </div>`;
  }).join('');
}
async function newConversation() {
  const model = document.getElementById('model-select').value || '';
  try {
    const r = await fetch('/api/conversations', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({title:'New Chat', model})});
    if (!r.ok) { toast('Failed to create conversation', 'error'); return; }
    const c = await r.json();
    await loadConversations();
    selectConvo(c.id);
  } catch(e) { toast('Failed to create conversation', 'error'); }
}
async function selectConvo(id) {
  currentConvoId = id;
  // Reset branch state when switching conversations
  currentBranchId = null;
  parentConvoId = null;
  branchMsgIdx = null;
  const chatInput = document.getElementById('chat-input');
  if (chatInput) chatInput.placeholder = 'Type a message... (Enter to send, Shift+Enter for newline, drop files)';
  try {
    const r = await fetch(`/api/conversations/${id}`);
    if (!r.ok) { toast('Failed to load conversation', 'error'); return; }
    const c = await r.json();
    try { chatMessages = JSON.parse(c.messages || '[]'); } catch(e) { chatMessages = []; }
    if (c.model) {
      const sel = document.getElementById('model-select');
      for (const opt of sel.options) { if (opt.value === c.model) { sel.value = c.model; break; } }
    }
    renderChat();
    renderConvoList();
  } catch(e) { toast('Failed to load conversation', 'error'); }
}
async function deleteConvo(id) {
  try {
    await fetch(`/api/conversations/${id}`, {method:'DELETE'});
  } catch(e) { /* network error — continue cleanup */ }
  if (currentConvoId === id || parentConvoId === id) {
    currentConvoId = null; chatMessages = [];
    currentBranchId = null; parentConvoId = null; branchMsgIdx = null;
    renderChat();
  }
  await loadConversations();
}
async function deleteAllConvos() {
  if (!allConvos.length) return;
  // Two-click safety: first click shows warning, second confirms
  const btn = document.querySelector('.convo-sidebar-footer .btn-danger');
  if (btn && !btn.dataset.confirm) {
    btn.dataset.confirm = '1';
    btn.textContent = 'Click again to confirm';
      btn.style.background = 'var(--red)'; btn.style.color = getThemeCssVar('--text-inverse', '#fff');
    setTimeout(() => { btn.textContent = 'Delete All'; btn.style.background = ''; btn.style.color = ''; delete btn.dataset.confirm; }, 3000);
    return;
  }
  try {
    const r = await fetch('/api/conversations/all', {method:'DELETE'});
    if (!r.ok) { toast('Failed to delete conversations', 'error'); return; }
  } catch(e) { toast('Failed to delete conversations', 'error'); return; }
  currentConvoId = null; chatMessages = []; allConvos = [];
  currentBranchId = null; parentConvoId = null; branchMsgIdx = null;
  renderChat(); renderConvoList();
  toast('All conversations deleted', 'warning');
}
function renameConvo(id) {
  const c = allConvos.find(x => x.id === id);
  const item = document.querySelector(`.convo-item[data-convo-id="${id}"]`);
  if (!item) return;
  const titleEl = item.querySelector('.convo-title');
  const oldTitle = c?.title || 'Chat';
  titleEl.innerHTML = `<input class="convo-rename-input" value="${escapeAttr(oldTitle)}" data-convo-rename-id="${id}" aria-label="Rename conversation" autocomplete="off" spellcheck="false">`;
  const inp = titleEl.querySelector('input');
  inp.focus();
  inp.select();
}
async function finishRename(id, inp) {
  const name = inp.value.trim();
  if (name) {
    try {
      await fetch(`/api/conversations/${id}`, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({title: name})});
    } catch(e) { toast('Rename failed', 'error'); }
  }
  await loadConversations();
}
async function saveConversation() {
  // If viewing a branch, save to the branch instead
  if (currentBranchId) { await saveBranch(); return; }
  if (!currentConvoId) return;
  const model = document.getElementById('model-select').value;
  const payload = {model, messages: chatMessages};
  // Only set title for brand-new conversations (no custom title yet)
  const convoEl = document.querySelector(`.convo-item[data-convo-id="${currentConvoId}"]`);
  if (!convoEl || convoEl.textContent.trim() === 'New Chat') {
    payload.title = chatMessages.find(m => m.role === 'user')?.content.slice(0, 50) || 'New Chat';
  }
  await fetch(`/api/conversations/${currentConvoId}`, {method:'PUT', headers:{'Content-Type':'application/json'},
    body:JSON.stringify(payload)});
  await loadConversations();
}

async function sendChat() {
  if (isSending) return;
  if (document.getElementById('chat-image-input')?.files?.length) { await sendChatWithImage(); return; }
  if (!_chatReady) { toast('AI service is still starting. Please wait...', 'info'); return; }
  const input = document.getElementById('chat-input');
  const msg = input.value.trim();
  if (!msg) return;
  const model = document.getElementById('model-select').value;
  if (!model) { toast('No AI model available. Opening the download panel...', 'info'); toggleModelPicker(); return; }

  isSending = true;
  input.value = '';
  input.style.height = 'auto';
  _chatAbortCtrl = new AbortController();
  document.getElementById('send-btn').disabled = true;
  document.getElementById('stop-btn').style.display = '';

  if (!currentConvoId) {
    try {
      const resp = await fetch('/api/conversations', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({title: msg.slice(0,50), model})});
      if (!resp.ok) { toast('Failed to create conversation', 'error'); isSending = false; return; }
      const c = await resp.json();
      currentConvoId = c.id;
      await loadConversations();
    } catch(e) { toast('Failed to create conversation', 'error'); isSending = false; return; }
  }

  // Attach file context if present
  let fullMsg = msg;
  if (_chatFileContext) {
    fullMsg = msg + '\n\n--- Attached File Content ---\n' + _chatFileContext + '\n--- End File ---';
    clearChatFile();
  }
  chatMessages.push({role:'user', content:fullMsg});
  chatMessages.push({role:'assistant', content:'', thinking: true, kb_used: kbEnabled});
  renderChat();

  let _chatTimeout = null;
  try {
    const resp = await fetch('/api/ai/chat', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({model, knowledge_base: kbEnabled, situation_context: document.getElementById('sit-context-toggle').checked, system_prompt: PRESETS[activePreset] || '', messages: chatMessages.filter(m=>m.content && m.role !== 'thinking').slice(0,-1)}),
      signal: _chatAbortCtrl.signal,
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error || `AI service error (${resp.status})`);
    }
    const reader = resp.body.getReader();
    _chatTimeout = setTimeout(() => {
        reader.cancel();
        toast('Chat response timed out', 'warning');
    }, 120000); // 2 min timeout
    const dec = new TextDecoder();
    let full = '';
    let streamBuf = '';
    const msgs = document.getElementById('chat-messages');
    let lastMsgEl = null;
    while (true) {
      const {done, value} = await reader.read();
      if (done) { clearTimeout(_chatTimeout); break; }
      streamBuf += dec.decode(value, {stream: true});
      const lines = streamBuf.split('\n');
      streamBuf = lines.pop(); // keep incomplete last line in buffer
      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const d = JSON.parse(line);
          // Handle RAG citations chunk (first chunk when KB is enabled)
          if (d.citations) {
            chatMessages[chatMessages.length-1].citations = d.citations;
            continue;
          }
          if (d.message?.content) {
            full += d.message.content;
            chatMessages[chatMessages.length-1].content = full;
            chatMessages[chatMessages.length-1].thinking = false;
            if (!lastMsgEl) {
              lastMsgEl = msgs.querySelector('.message.assistant:last-child .content');
            }
            if (lastMsgEl && !_streamRAF) {
              _streamRAF = requestAnimationFrame(() => {
                _streamRAF = null;
                if (lastMsgEl) lastMsgEl.innerHTML = renderMarkdown(full);
                const nearBottom = msgs.scrollHeight - msgs.scrollTop - msgs.clientHeight < 100;
                if (nearBottom) msgs.scrollTop = msgs.scrollHeight;
              });
            }
          }
          if (d.done && d.eval_count) {
            const toks = d.eval_count;
            const secs = (d.eval_duration || 1) / 1e9;
            document.getElementById('chat-stats').textContent = `${toks} tokens | ${(secs > 0 ? (toks/secs).toFixed(1) : '0.0')} tok/s | ${secs.toFixed(1)}s`;
          }
        } catch {}
      }
    }
    renderChat();
  } catch(e) {
    clearTimeout(_chatTimeout);
    if (e.name !== 'AbortError') {
      chatMessages[chatMessages.length-1].content = 'Could not reach the AI. Attempting to start the service automatically...';
      chatMessages[chatMessages.length-1].thinking = false;
      renderChat();
      // Auto-start Ollama
      ensureOllamaReady().then(ok => {
        if (ok) {
          chatMessages[chatMessages.length-1].content = 'AI service restarted. Please send your message again.';
        } else {
          chatMessages[chatMessages.length-1].content = 'Could not start the AI service. Check the Home page to make sure AI Chat is installed and try starting it manually.';
        }
        renderChat();
      }).catch(() => {
        chatMessages[chatMessages.length-1].content = 'Failed to contact AI service. Check your connection and try again.';
        renderChat();
      });
    }
  }
  isSending = false;
  _chatAbortCtrl = null;
  document.getElementById('send-btn').disabled = false;
  document.getElementById('stop-btn').style.display = 'none';
  document.getElementById('regen-btn').style.display = chatMessages.length >= 2 ? '' : 'none';
  saveConversation();
}

function regenerateChat() {
  if (isSending || !chatMessages.length) return;
  // Remove the last assistant message and re-send
  if (chatMessages[chatMessages.length-1].role === 'assistant') {
    chatMessages.pop();
  }
  if (chatMessages.length && chatMessages[chatMessages.length-1].role === 'user') {
    const lastUserMsg = chatMessages.pop();
    const originalContent = lastUserMsg.content.split('\n\n--- Attached File Content ---\n')[0];
    document.getElementById('chat-input').value = originalContent;
    renderChat();
    sendChat();
  }
}

function stopChat() {
  if (_chatAbortCtrl) {
    _chatAbortCtrl.abort();
    _chatAbortCtrl = null;
    isSending = false;
    document.getElementById('send-btn').disabled = false;
    document.getElementById('stop-btn').style.display = 'none';
    if (chatMessages.length && chatMessages[chatMessages.length-1].role === 'assistant') {
      chatMessages[chatMessages.length-1].thinking = false;
    }
    renderChat();
    saveConversation();
    toast('Generation stopped', 'warning');
  }
}

function formatSourceCitations(sources) {
  if (!sources || !sources.length) return '';
  return '<div class="chat-source-row">' +
    sources.map(s => '<span class="chat-source-chip">&#128196; ' + escapeHtml(s) + '</span>').join('') +
    '</div>';
}
function formatRAGCitations(citations) {
  if (!citations || !citations.length) return '';
  return '<div class="chat-citation-shell">' +
    '<div class="chat-citation-kicker">&#128218; Sources</div>' +
    '<div class="chat-source-row">' +
    citations.map(c => {
      const score = c.score ? ` (${Math.round(c.score * 100)}%)` : '';
      const citationLabel = `&#128196; ${escapeHtml(c.filename)}${score}`;
      if (c.doc_id) {
        return `<button type="button" class="rag-citation rag-citation-link chat-source-chip chat-source-chip-accent" data-chat-action="view-kb-document" data-doc-id="${parseInt(c.doc_id,10)||0}" title="${escapeAttr(c.excerpt || '')}">${citationLabel}</button>`;
      }
      return `<span class="rag-citation chat-source-chip chat-source-chip-accent" title="${escapeAttr(c.excerpt || '')}">${citationLabel}</span>`;
    }).join('') +
    '</div></div>';
}
function viewKBDocument(docId) {
  document.querySelector('[data-tab="kiwix-library"]')?.click();
  setTimeout(() => {
    const section = document.getElementById('doc-library');
    if (section) section.scrollIntoView({behavior: 'smooth'});
    // Highlight the document if a detail view exists
    if (typeof loadDocumentDetail === 'function') loadDocumentDetail(docId);
  }, 200);
}

function renderChat() {
  const c = document.getElementById('chat-messages');
  const empty = document.getElementById('chat-empty');
  if (!chatMessages.length) { empty.hidden = false; c.querySelectorAll('.message').forEach(m=>m.remove()); updateBranchBanner(); return; }
  empty.hidden = true;
  let html = '';
  for (let i = 0; i < chatMessages.length; i++) {
    const m = chatMessages[i];
    const av = m.role === 'user' ? 'U' : aiName.slice(0,2).toUpperCase();
    const thinkHtml = m.thinking ? '<div class="thinking">Thinking...</div>' : '';
    const content = m.role === 'assistant' ? renderMarkdown(m.content) : escapeHtml(m.content).replace(/\n/g,'<br>');
    // "What If" button on AI responses (not on branches being viewed — they can fork further from the convo they belong to)
    const whatIfBtn = (m.role === 'assistant' && m.content && !m.thinking && !currentBranchId) ? `<button class="msg-action-btn whatif-btn" type="button" data-chat-action="fork-what-if" data-message-index="${i}" title="Explore an alternative scenario from this point">What If?</button>` : '';
    const forkBtn = m.content && !m.thinking ? `<button class="msg-action-btn" type="button" data-chat-action="fork-conversation" data-message-index="${i}" title="Branch from here">Fork</button>` : '';
    const copyAction = m.content && !m.thinking ? `<div class="message-actions"><button class="msg-action-btn" type="button" data-chat-action="copy-message">Copy</button>${whatIfBtn}${forkBtn}</div>` : '';
    // Show source citations if available on this message
    const sourcesHtml = (m.sources && m.sources.length) ? formatSourceCitations(m.sources) : '';
    // Show RAG citations with clickable document links
    const citationsHtml = (m.citations && m.citations.length) ? formatRAGCitations(m.citations) : '';
    // Show KB badge on assistant messages when knowledge base was active
    const kbBadge = (m.role === 'assistant' && m.kb_used && !m.thinking && !m.citations?.length) ? '<div class="chat-kb-badge-row"><span class="chat-kb-badge">&#128218; Knowledge Base</span></div>' : '';
    html += `<div class="message ${m.role}" data-content="${escapeAttr(m.content)}"><div class="avatar">${av}</div><div class="content">${content}${sourcesHtml}${citationsHtml}${kbBadge}${thinkHtml}${copyAction}</div></div>`;
  }
  c.innerHTML = `<div class="empty-state chat-empty-state-compact" id="chat-empty" hidden><div class="icon chat-empty-icon-shell"><span class="chat-empty-avatar">${escapeHtml(aiName.slice(0,2).toUpperCase())}</span></div><p class="chat-empty-heading">Start a conversation</p><p class="chat-empty-copy">Ask a question or start a new branch when you're ready.</p></div>` + html;
  c.scrollTop = c.scrollHeight;
  // Update chat stats
  const stats = document.getElementById('chat-stats');
  if (stats && chatMessages.length) {
    const totalChars = chatMessages.reduce((s, m) => s + (m.content?.length || 0), 0);
    const approxTokens = Math.round(totalChars / 4);
    stats.textContent = `${chatMessages.length} msgs | ~${approxTokens.toLocaleString()} tokens`;
  } else if (stats) { stats.textContent = ''; }
  updateBranchBanner();
  if (currentConvoId && !currentBranchId) refreshBranchCount(currentConvoId);
}

async function forkConversation(messageIndex) {
  if (!currentConvoId) { toast('No active conversation', 'warning'); return; }
  const cid = currentBranchId ? parentConvoId : currentConvoId;
  const r = await safeFetch('/api/conversations/' + cid + '/branch', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({message_index: messageIndex})
  }, null);
  if (r && r.branch_id) {
    toast('Conversation forked — branch #' + r.branch_id, 'success');
    refreshBranchCount(cid);
  }
}

/* ─── "What If" Scenario Fork ─── */
async function forkWhatIf(messageIndex) {
  if (!currentConvoId) { toast('No active conversation', 'warning'); return; }
  const cid = currentConvoId;
  // Create the branch via the API
  const r = await safeFetch('/api/conversations/' + cid + '/branch', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({message_index: messageIndex})
  }, null);
  if (!r || !r.branch_id) { toast('Failed to create branch', 'error'); return; }
  // Switch to the new branch
  parentConvoId = cid;
  currentBranchId = r.branch_id;
  branchMsgIdx = messageIndex;
  chatMessages = r.messages || [];
  renderChat();
  toast('Branch created — type an alternative question below', 'success');
  // Focus the main chat input and set placeholder hint
  const input = document.getElementById('chat-input');
  if (input) {
    input.placeholder = 'Enter an alternative question or scenario to explore...';
    input.focus();
  }
}

/* ─── Branch Navigation ─── */
async function switchToBranch(branchId, convId) {
  const r = await safeFetch('/api/conversations/branches/' + branchId, {}, null);
  if (!r) { toast('Failed to load branch', 'error'); return; }
  parentConvoId = convId || r.conversation_id;
  currentBranchId = branchId;
  branchMsgIdx = r.parent_message_idx;
  try { chatMessages = JSON.parse(r.messages || '[]'); } catch(e) { chatMessages = []; }
  renderChat();
  // Close branch panel if open
  const panel = document.getElementById('branch-panel');
  if (panel) panel.classList.remove('open');
}

function returnToMainConversation() {
  if (!parentConvoId) return;
  const cid = parentConvoId;
  currentBranchId = null;
  parentConvoId = null;
  branchMsgIdx = null;
  // Restore the chat input placeholder
  const input = document.getElementById('chat-input');
  if (input) input.placeholder = 'Type a message... (Enter to send, Shift+Enter for newline, drop files)';
  selectConvo(cid);
}

function updateBranchBanner() {
  const banner = document.getElementById('branch-banner');
  if (!banner) return;
  if (currentBranchId) {
    banner.style.display = 'flex';
    const msgNum = branchMsgIdx != null ? branchMsgIdx + 1 : '?';
    document.getElementById('branch-banner-text').textContent =
      'Viewing branch #' + currentBranchId + ' (forked from message #' + msgNum + ')';
  } else {
    banner.style.display = 'none';
  }
}

/* ─── Branch Panel ─── */
async function toggleBranchPanel() {
  const panel = document.getElementById('branch-panel');
  if (!panel) return;
  if (panel.classList.contains('open')) { panel.classList.remove('open'); return; }
  const cid = currentBranchId ? parentConvoId : currentConvoId;
  if (!cid) return;
  panel.innerHTML = '<div class="branch-panel-header">Loading...</div>';
  panel.classList.add('open');
  const branches = await safeFetch('/api/conversations/' + cid + '/branches', {}, []);
  if (!branches.length) {
    panel.innerHTML = '<div class="branch-panel-header">Branches</div><div class="branch-panel-empty">No branches yet. Click "What If?" on an AI response to create one.</div>';
    return;
  }
  let html = '<div class="branch-panel-header"><span>Branches (' + branches.length + ')</span></div>';
  // Add "Return to main" if viewing a branch
  if (currentBranchId) {
    html += '<div class="branch-panel-item branch-panel-item-return" role="button" tabindex="0" data-chat-action="return-main-conversation">&#8592; Return to main conversation</div>';
  }
  for (const b of branches) {
    const active = b.id === currentBranchId ? ' branch-panel-item-active' : '';
    const time = b.created_at ? new Date(b.created_at).toLocaleString() : '';
    html += `<div class="branch-panel-item${active}" role="button" tabindex="0" data-branch-switch="${b.id}" data-branch-convo="${cid}">`;
    html += `<div>Branch #${b.id} <span class="branch-panel-copy">from msg #${b.parent_message_idx + 1}</span></div>`;
    html += `<div class="bp-meta">${time}</div>`;
    html += '</div>';
  }
  panel.innerHTML = html;
}

async function refreshBranchCount(cid) {
  if (!cid) return;
  const branches = await safeFetch('/api/conversations/' + cid + '/branches', {}, []);
  const btn = document.getElementById('branches-btn');
  const badge = document.getElementById('branches-count-badge');
  if (branches.length > 0) {
    if (btn) btn.style.display = '';
    if (badge) { badge.style.display = ''; badge.textContent = branches.length; }
  } else {
    if (btn) btn.style.display = 'none';
    if (badge) badge.style.display = 'none';
  }
}

/* ─── Save branch messages (called from sendChat when in branch mode) ─── */
async function saveBranch() {
  if (!currentBranchId) return;
  await safeFetch('/api/conversations/branches/' + currentBranchId, {
    method: 'PUT', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({messages: chatMessages})
  }, null);
}

/* ─── Image Chat ─── */
function previewChatImage() {
  const input = document.getElementById('chat-image-input');
  const preview = document.getElementById('chat-image-preview');
  if (!input.files.length) { preview.style.display = 'none'; return; }
  preview.style.display = 'block';
  const file = input.files[0];
  if (window._chatImagePreviewUrl) URL.revokeObjectURL(window._chatImagePreviewUrl);
  window._chatImagePreviewUrl = URL.createObjectURL(file);
  preview.innerHTML = '<div class="chat-image-preview-row"><img src="' + window._chatImagePreviewUrl + '" class="chat-image-preview-thumb"> <span class="chat-image-preview-name">' + escapeHtml(file.name) + '</span> <span class="chat-image-preview-copy">Image will be sent with your next message using multimodal analysis.</span> <button class="btn btn-sm btn-ghost chat-image-preview-clear" type="button" data-chat-action="clear-chat-image" aria-label="Clear image">✕</button></div>';
}

function clearChatImage() {
  document.getElementById('chat-image-input').value = '';
  document.getElementById('chat-image-preview').style.display = 'none';
}

async function sendChatWithImage() {
  const input = document.getElementById('chat-image-input');
  if (!input || !input.files.length) return false;
  const model = document.getElementById('model-select')?.value;
  const msgInput = document.getElementById('chat-input');
  const msg = msgInput?.value?.trim() || 'Describe this image.';
  if (!model) { toast('Select a model first', 'warning'); return true; }

  msgInput.value = '';
  msgInput.style.height = 'auto';

  const fd = new FormData();
  fd.append('image', input.files[0]);
  fd.append('model', model);
  fd.append('message', msg);

  // Show user message with image preview
  chatMessages.push({role:'user', content: msg + ' [image attached]'});
  chatMessages.push({role:'assistant', content:'Analyzing image...', thinking: true});
  renderChat();

  const r = await safeFetch('/api/ai/chat-with-image', {method: 'POST', body: fd}, null);
  clearChatImage();

  // Remove thinking placeholder
  chatMessages.pop();
  if (r && r.answer) {
    chatMessages.push({role:'assistant', content: r.answer});
  } else {
    chatMessages.push({role:'assistant', content: 'Failed to analyze image. Make sure you\'re using a multimodal model (Gemma 3, LLaVA, etc.).'});
  }
  renderChat();
  return true;
}

/* ─── Kiwix Library (Tiered Catalog) ─── */
let _installedZims = new Set();
let _downloadingZims = new Set();

async function loadZimList() {
  const zims = await safeFetch('/api/kiwix/zims', {}, []);
  if (!zims) return;
  _installedZims = new Set(zims.map(z => z.filename));

  // Update library summary
  const summaryEl = document.getElementById('library-summary');
  if (summaryEl) {
    const totalMB = zims.reduce((sum, z) => sum + z.size_mb, 0);
    const totalStr = totalMB >= 1024 ? (totalMB/1024).toFixed(1) + ' GB' : totalMB.toFixed(0) + ' MB';
    summaryEl.innerHTML = `
      <div><div class="cs-total">${zims.length}</div><div class="cs-label">Content Packs Downloaded</div></div>
      <div class="cs-stat"><div class="cs-val">${totalStr}</div><div class="cs-label">Total Library Size</div></div>
    `;
  }

  // Re-render catalog if visible to update download states
  if (_cachedCatalog) renderFullCatalog(_cachedCatalog);
}

async function loadZimCatalog() {
  const catalog = await safeFetch('/api/kiwix/catalog', {}, []);
  if (!catalog) return;
  _cachedCatalog = catalog;
  renderFullCatalog(catalog);
}

function renderFullCatalog(catalog) {
  const el = document.getElementById('zim-catalog');
  el.innerHTML = catalog.map((cat, ci) => {
    const tiers = cat.tiers || {};
    const tierNames = Object.keys(tiers);
    if (!tierNames.length) return '';
    const activeTier = _catalogTiers[ci] || tierNames[0];
    _catalogTiers[ci] = activeTier;

    return `<div class="settings-card library-tier-card">
      <h4 class="library-tier-title">${escapeHtml(cat.category)}</h4>
      <div class="tier-tabs library-tier-tabs">${tierNames.map(t =>
        `<button class="tier-tab ${t===activeTier?'active':''}" type="button" data-library-action="switch-tier" data-zim-category-index="${ci}" data-zim-tier-value="${escapeAttr(t)}">${t}</button>`
      ).join('')}</div>
      <div id="cat-items-${ci}">${renderTierItems(tiers[activeTier])}</div>
    </div>`;
  }).join('');
}

function renderTierItems(items) {
  if (!items || !items.length) return '<span class="library-tier-empty">No items in this tier.</span>';
  return items.map(i => {
    const installed = _installedZims.has(i.filename);
    const downloading = _downloadingZims.has(i.filename);
    let actionHtml;
    if (installed) {
      actionHtml = `<span class="catalog-action-group">
        <span class="catalog-action-status catalog-action-status-success">Downloaded</span>
        <button class="btn btn-sm btn-danger catalog-action-btn" type="button" data-library-action="delete-zim" data-zim-filename="${escapeAttr(i.filename)}">Delete</button>
      </span>`;
    } else if (downloading) {
      actionHtml = `<span class="catalog-action-group">
        <span class="catalog-action-status catalog-action-status-progress"><span class="inline-status-spinner inline-status-spinner-sm"></span>Downloading…</span>
      </span>`;
    } else {
      actionHtml = `<button class="btn btn-sm btn-primary catalog-download-btn" type="button" data-library-action="download-zim-item" data-zim-url="${escapeAttr(i.url)}" data-zim-filename="${escapeAttr(i.filename)}">Download</button>`;
    }
    return `<div class="catalog-item" data-filename="${escapeAttr(i.filename)}">
      <div class="cat-info"><div class="cat-name">${escapeHtml(i.name)}</div><div class="cat-desc">${escapeHtml(i.desc)}</div></div>
      <span class="cat-size cat-size-nowrap">${i.size}</span>
      ${actionHtml}
    </div>`;
  }).join('');
}

let _cachedCatalog = null;
function switchTier(ci, tier, btn) {
  btn.parentElement.querySelectorAll('.tier-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  _catalogTiers[ci] = tier;
  if (_cachedCatalog) {
    const items = _cachedCatalog[ci]?.tiers?.[tier] || [];
    document.getElementById(`cat-items-${ci}`).innerHTML = renderTierItems(items);
  } else {
    fetch('/api/kiwix/catalog').then(r=>{if(!r.ok)throw new Error();return r.json()}).then(catalog => {
      _cachedCatalog = catalog;
      const items = catalog[ci]?.tiers?.[tier] || [];
      document.getElementById(`cat-items-${ci}`).innerHTML = renderTierItems(items);
    }).catch(()=>{});
  }
}

async function downloadAllZimsByTier(tier) {
  try {
    const [catalog, existing] = await Promise.all([
      _cachedCatalog || fetch('/api/kiwix/catalog').then(r => { if(!r.ok) throw new Error(); return r.json(); }),
      fetch('/api/kiwix/zims').then(r => { if(!r.ok) throw new Error(); return r.json(); })
    ]);
    _cachedCatalog = catalog;
    const existingNames = new Set(existing.map(z => z.filename));
    const toDownload = [];
    for (const cat of catalog) {
      // For 'comprehensive', download ALL tiers. For 'standard', download essential+standard. For 'essential', just essential.
      const tiersToGet = tier === 'comprehensive' ? Object.keys(cat.tiers || {}) :
                         tier === 'standard' ? ['essential', 'standard'] : ['essential'];
      for (const t of tiersToGet) {
        const items = cat.tiers?.[t] || [];
        for (const item of items) {
          if (!existingNames.has(item.filename) && !toDownload.some(d => d.filename === item.filename)) {
            toDownload.push(item);
          }
        }
      }
    }
    if (!toDownload.length) { toast(`All ${tier} content packs are already downloaded!`, 'success'); return; }
    toast(`Starting ${toDownload.length} downloads (${tier} tier)...`, 'info');
    toDownload.forEach(item => _downloadingZims.add(item.filename));
    await Promise.all(toDownload.map(item =>
      fetch('/api/kiwix/download-zim', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({url: item.url, filename: item.filename})})
    ));
    renderFullCatalog(_cachedCatalog); // Update button states
    startZimQueuePoll();
  } catch(e) { toast('Failed to start bulk download', 'error'); }
}

async function downloadZimItem(btn, url, filename) {
  // Change button state immediately
  btn.disabled = true;
  btn.innerHTML = '<span class="inline-status-spinner inline-status-spinner-sm"></span>Starting…';
  _downloadingZims.add(filename);
  try {
    const r = await fetch('/api/kiwix/download-zim', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({url, filename})});
    if (!r.ok) { const d = await r.json().catch(()=>({})); toast(d.error || 'Download failed', 'error'); btn.disabled = false; btn.textContent = 'Retry'; _downloadingZims.delete(filename); return; }
    btn.innerHTML = '<span class="inline-status-spinner inline-status-spinner-sm"></span>Downloading…';
    btn.style.opacity = '0.7';
  } catch(e) { toast('Failed to start download', 'error'); btn.disabled = false; btn.textContent = 'Retry'; _downloadingZims.delete(filename); return; }
  startZimQueuePoll();
}

let _zimQueuePoll = null;
function stopZimQueuePoll() {
  if (_zimQueuePoll) {
    clearInterval(_zimQueuePoll);
    _zimQueuePoll = null;
  }
  window.NomadShellRuntime?.stopInterval('library.zim-downloads');
}
async function loadZimDownloads() {
  try {
    const downloads = await (await fetch('/api/kiwix/zim-downloads')).json();
    const entries = Object.entries(downloads);
    const active = entries.filter(([,v]) => v.status === 'downloading' || v.status === 'extracting');
    const errors = entries.filter(([,v]) => v.status === 'error');
    const completed = entries.filter(([,v]) => v.status === 'complete');
    const queueEl = document.getElementById('zim-download-queue');
    const itemsEl = document.getElementById('zim-queue-items');
    // Show success toasts for newly completed downloads
    completed.forEach(([filename]) => {
      if (!window._zimCompletedSet) window._zimCompletedSet = new Set();
      if (!window._zimCompletedSet.has(filename)) {
        window._zimCompletedSet.add(filename);
        _installedZims.add(filename);
        _downloadingZims.delete(filename);
        toast(`${filename} downloaded successfully!`, 'success');
        sendNotification('Download Complete', `${filename} is ready`);
      }
    });
    // Refresh catalog to update button states if any completed
    if (completed.length && _cachedCatalog) renderFullCatalog(_cachedCatalog);
    // Show error toasts for failed downloads
    errors.forEach(([filename, p]) => {
      if (!window._zimErrorSet) window._zimErrorSet = new Set();
      if (!window._zimErrorSet.has(filename)) {
        window._zimErrorSet.add(filename);
        _downloadingZims.delete(filename);
        toast(`Download failed: ${filename} — ${p.error || 'Unknown error'}. Click Download again to retry (will resume).`, 'error');
      }
    });
    if (errors.length && _cachedCatalog) renderFullCatalog(_cachedCatalog);
    if (!active.length && !errors.length) {
      queueEl.style.display = 'none';
      stopZimQueuePoll();
      return;
    }
    queueEl.style.display = 'block';
    let html = active.map(([filename, p]) => `
      <div class="zim-queue-item">
        <div class="zq-name">${escapeHtml(filename)}</div>
        <div class="progress-bar"><div class="fill" style="width:${p.percent||0}%"></div></div>
        <div class="zq-meta"><span>${p.status||''} ${p.speed ? '- '+p.speed : ''}</span><span>${p.percent||0}%</span></div>
      </div>
    `).join('');
    html += errors.map(([filename, p]) => `
      <div class="zim-queue-item zim-queue-item-error">
        <div class="zq-name zq-name-error">${escapeHtml(filename)} - FAILED</div>
        <div class="zq-note">${escapeHtml(p.error || 'Unknown error')}. Retry will resume from where it stopped.</div>
      </div>
    `).join('');
    itemsEl.innerHTML = html;
  } catch(e) {}
}

function startZimQueuePoll() {
  if (_zimQueuePoll) return;
  const runner = async () => {
    await loadZimDownloads();
    await loadZimList();
  };
  if (window.NomadShellRuntime) {
    _zimQueuePoll = window.NomadShellRuntime.startInterval('library.zim-downloads', runner, 2000, {
      tabId: 'kiwix-library',
      requireVisible: true,
    });
    return;
  }
  _zimQueuePoll = setInterval(runner, 2000);
}

async function deleteZim(filename) {
  const resp = await fetch('/api/kiwix/delete-zim', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({filename}) });
  if (!resp.ok) { toast('Failed to delete content pack', 'error'); return; }
  _installedZims.delete(filename);
  window._zimCompletedSet?.delete(filename);
  toast('Content pack deleted', 'warning');
  loadZimList();
}

