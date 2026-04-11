/* ─── Maps ─── */
async function _workspaceExtractError(resp, fallbackMessage) {
  try {
    const data = await resp.json();
    return data?.error || data?.message || fallbackMessage;
  } catch (_) {
    try {
      const text = await resp.text();
      return text || fallbackMessage;
    } catch (_) {
      return fallbackMessage;
    }
  }
}

async function _workspaceFetchOk(url, opts = {}, failureLabel = 'Request failed') {
  const resp = await fetch(url, opts);
  if (!resp.ok) {
    throw new Error(await _workspaceExtractError(resp.clone(), `${failureLabel} (HTTP ${resp.status})`));
  }
  return resp;
}

async function _workspaceFetchJson(url, opts = {}, failureLabel = 'Request failed') {
  const resp = await _workspaceFetchOk(url, opts, failureLabel);
  try {
    return await resp.json();
  } catch (_) {
    throw new Error(`Invalid server response from ${url}`);
  }
}

async function _workspaceFetchJsonSafe(url, opts = {}, fallback = null, failureLabel = 'Request failed') {
  try {
    return await _workspaceFetchJson(url, opts, failureLabel);
  } catch (e) {
    console.warn(`${failureLabel}:`, e.message);
    return fallback;
  }
}

async function loadMaps() {
  const [regions, files] = await Promise.all([
    safeFetch('/api/maps/regions', {}, []),
    safeFetch('/api/maps/files', {}, []),
  ]);
  const regionGrid = document.getElementById('region-grid');
  const filesEl = document.getElementById('map-files-list');
  if (!regionGrid || !filesEl) return;

  regionGrid.innerHTML = regions.map(r => `
    <div class="region-card">
      <div class="region-card-shell">
        <div class="region-card-copy">
          <div class="region-card-title">${r.name}</div>
          <div class="region-card-meta">${r.states}</div>
        </div>
        ${r.downloaded
          ? `<div class="region-card-actions">
              <span class="region-card-size">${r.size}</span>
              <button class="btn btn-sm btn-danger" type="button" data-map-action="delete-map" data-map-filename="${escapeAttr(r.id)}.pmtiles">x</button>
            </div>`
          : `<button class="btn btn-sm btn-primary btn-open-svc-compact" type="button" data-map-action="download-region" data-map-region="${escapeAttr(r.id)}">Download</button>`
        }
      </div>
    </div>
  `).join('');

  if (!files.length) {
    filesEl.innerHTML = '<span class="map-files-empty">No maps downloaded yet.</span>';
  } else {
    filesEl.innerHTML = files.map(f => `
      <div class="model-item">
        <span class="model-name">${escapeHtml(f.filename)}</span>
        <span class="model-item-actions">
          <span class="model-size">${f.size}</span>
          <button class="btn btn-sm btn-danger" type="button" data-map-action="delete-map" data-map-filename="${escapeAttr(f.filename)}">Delete</button>
        </span>
      </div>
    `).join('');
  }
}

async function deleteMap(filename, btn) {
  if (!btn) btn = (typeof event !== 'undefined' && event) ? event.target : null;
  if (!btn) return;
  if (!btn.dataset.confirm) {
    btn.dataset.confirm = '1';
    const orig = btn.textContent;
    btn.textContent = 'Confirm delete?';
      btn.style.background = 'var(--red)'; btn.style.color = getThemeCssVar('--text-inverse', '#fff');
    setTimeout(() => { btn.textContent = orig; btn.style.background = ''; btn.style.color = ''; delete btn.dataset.confirm; }, 3000);
    return;
  }
  try {
    await _workspaceFetchOk('/api/maps/delete', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({filename})}, 'Failed to delete map');
    toast('Map deleted', 'warning');
    loadMaps();
  } catch (e) {
    toast(e.message || 'Failed to delete map', 'error');
  }
}

async function downloadMapRegion(regionId) {
  try {
    await _workspaceFetchJson('/api/maps/download-region', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({region_id: regionId})
    }, 'Download failed');
    toast(`Started downloading region "${regionId}". This may take a while — tiles are extracted from the Protomaps planet build.`, 'info');
    startMapDownloadPolling();
  } catch (e) { toast('Download request failed: ' + e.message, 'error'); }
}

async function downloadAllMaps() {
  if (!confirm('This will download ALL map regions. Each region is extracted from the Protomaps planet build and may be several GB. Continue?')) return;
  try {
    const regions = await _workspaceFetchJson('/api/maps/regions', {}, 'Could not load map regions');
    const toDownload = regions.filter(r => !r.downloaded);
    if (!toDownload.length) { toast('All regions already downloaded!', 'info'); return; }
    // Start downloads sequentially (one at a time to avoid overload)
    for (const r of toDownload) {
      await _workspaceFetchOk('/api/maps/download-region', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({region_id: r.id})
      }, `Could not queue ${r.name || r.id}`);
    }
    toast(`Queued ${toDownload.length} regions for download.`, 'info');
    startMapDownloadPolling();
  } catch (e) { toast('Failed: ' + e.message, 'error'); }
}

let _mapDlPollTimer = null;
function startMapDownloadPolling() {
  if (_mapDlPollTimer) return;
  const statusEl = document.getElementById('map-download-status');
  if (statusEl) statusEl.style.display = 'block';
  const poll = async () => {
    try {
      const progress = await _workspaceFetchJsonSafe('/api/maps/download-progress', {}, null, 'Could not load map download progress');
      if (!progress || typeof progress !== 'object') return;
      const active = Object.entries(progress).filter(([, v]) => v.progress > 0 && v.progress < 100);
      const errors = Object.entries(progress).filter(([, v]) => v.error);

      if (active.length > 0) {
        const label = document.getElementById('map-dl-label');
        const pct = document.getElementById('map-dl-pct');
        const bar = document.getElementById('map-dl-bar');
        // Show all active downloads, not just first
        if (active.length === 1) {
          const [id, info] = active[0];
          if (label) label.textContent = `${id}: ${info.status}`;
          if (pct) pct.textContent = `${info.progress}%`;
          if (bar) bar.style.width = `${info.progress}%`;
        } else {
          const avgPct = Math.round(active.reduce((s,[,v]) => s + v.progress, 0) / active.length);
          if (label) label.textContent = `Downloading ${active.length} regions: ${active.map(([id]) => id).join(', ')}`;
          if (pct) pct.textContent = `~${avgPct}%`;
          if (bar) bar.style.width = `${avgPct}%`;
        }
      } else {
        // No active downloads
        if (statusEl) statusEl.style.display = 'none';
        if (_mapDlPollTimer) clearInterval(_mapDlPollTimer);
        _mapDlPollTimer = null;
        window.NomadShellRuntime?.stopInterval('maps.download-progress');
        loadMaps(); // Refresh the map list
        // Show any errors
        for (const [id, info] of errors) {
          if (info.error) toast(`Map "${id}" failed: ${info.error}`, 'error');
        }
        // Check for completions
        const completed = Object.entries(progress).filter(([, v]) => v.progress === 100);
        if (completed.length > 0) toast(`${completed.length} map region(s) downloaded successfully!`, 'success');
      }
    } catch (e) { /* ignore polling errors */ }
  };
  if (window.NomadShellRuntime) {
    _mapDlPollTimer = window.NomadShellRuntime.startInterval('maps.download-progress', poll, 2000, {
      tabId: 'maps',
      requireVisible: true,
    });
    return;
  }
  _mapDlPollTimer = setInterval(poll, 2000);
}

async function downloadMapFromUrl() {
  const url = document.getElementById('map-url-input')?.value?.trim();
  if (!url) { toast('Enter a URL first', 'warning'); return; }
  // Auto-generate filename from URL, user can edit via the file path input field
  const filename = (document.getElementById('map-file-input')?.value?.trim()) || url.split('/').pop()?.split('?')[0] || 'download.pmtiles';
  if (!filename) { toast('Could not determine filename', 'warning'); return; }
  try {
    await _workspaceFetchJson('/api/maps/download-url', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url, filename})
    }, 'Failed');
    toast('Download started: ' + filename, 'info');
    startMapDownloadPolling();
  } catch (e) { toast('Failed: ' + e.message, 'error'); }
}

async function importMapFile() {
  const path = document.getElementById('map-file-input')?.value?.trim();
  if (!path) { toast('Enter a file path first', 'error'); return; }
  try {
    const data = await _workspaceFetchJson('/api/maps/import-file', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({path})
    }, 'Import failed');
    toast(`Imported ${data.filename} (${data.size})`, 'success');
    loadMaps();
  } catch (e) { toast('Import failed: ' + e.message, 'error'); }
}

async function loadMapSources() {
  try {
    const sources = await _workspaceFetchJson('/api/maps/sources', {}, 'Could not load map source catalog');
    const catalog = document.getElementById('map-sources-catalog');
    if (!catalog) return;
    const categories = {};
    for (const s of sources) {
      if (!categories[s.category]) categories[s.category] = [];
      categories[s.category].push(s);
    }
    catalog.innerHTML = Object.entries(categories).map(([cat, items]) => `
      <div class="map-source-group">
        <h4 class="map-source-title">${escapeHtml(cat)}</h4>
        ${items.map(s => `
          <div class="map-source-row">
            <div class="map-source-copy">
              <span class="map-source-name">${escapeHtml(s.name)}</span>
              <span class="map-source-desc">${escapeHtml(s.desc)}</span>
            </div>
            <div class="map-source-actions">
              <span class="map-source-meta">${escapeHtml(s.est_size)} · ${escapeHtml(s.format.toUpperCase())}</span>
              ${s.direct
                ? `<button class="btn btn-sm btn-primary btn-open-svc-compact" data-map-download-url="${escapeAttr(s.url)}">Download</button>`
                : `<button class="btn btn-sm btn-open-svc-compact" data-app-frame-title="${escapeAttr(s.name)}" data-app-frame-url="${escapeAttr(s.url)}">Visit</button>`
              }
            </div>
          </div>
        `).join('')}
      </div>
    `).join('');
  } catch (e) { /* ignore */ }
}

/* ─── Notes ─── */
let allNotes = [];
async function loadNotes() {
  const notesList = document.getElementById('notes-list');
  if (notesList && (!allNotes || allNotes.length === 0)) notesList.innerHTML = Array(4).fill('<div class="skeleton skeleton-card notes-skeleton"></div>').join('');
  try {
    const notes = await _workspaceFetchJsonSafe('/api/notes', {}, allNotes || [], 'Failed to load notes');
    allNotes = Array.isArray(notes) ? notes : (allNotes || []);
  } catch(e) { allNotes = allNotes || []; }
  renderNotesList();
}
function renderNoteListHtml(items, emptyText) {
  return items.map(n => `
    <div class="note-item ${n.id===currentNoteId?'active':''}" data-note-action="select-note" data-note-id="${n.id}" role="button" tabindex="0">
      <div class="note-item-head">
        ${n.pinned ? '<span class="note-pin" title="Pinned">&#9733;</span>' : ''}
        <div class="note-title">${escapeHtml(n.title||'Untitled')}</div>
      </div>
      <div class="note-date">${n.tags ? '<span class="note-tag-list">' + n.tags.split(',').map(t=>t.trim()).filter(t=>t).map(t=>'<span class="note-tag-badge">'+escapeHtml(t)+'</span>').join('') + '</span> ' : ''}${new Date(n.updated_at).toLocaleDateString()}</div>
    </div>
  `).join('') || `<div class="notes-empty-state">${emptyText}</div>`;
}
function renderNotesList() {
  const list = document.getElementById('notes-list');
  if (!list) return;
  const q = (document.getElementById('notes-search')?.value || '').toLowerCase();
  let filtered = q ? allNotes.filter(n => (n.title||'').toLowerCase().includes(q) || (n.tags||'').toLowerCase().includes(q)) : allNotes;
  list.innerHTML = renderNoteListHtml(filtered, 'No notes yet');
}
function selectNote(id) {
  currentNoteId = id;
  const n = allNotes.find(n => n.id === id);
  const titleInput = document.getElementById('note-title');
  const contentInput = document.getElementById('note-content');
  const tagsInput = document.getElementById('note-tags');
  const pinBtn = document.getElementById('note-pin-btn');
  if (!titleInput || !contentInput || !tagsInput || !pinBtn) return;
  if (n) {
    titleInput.value = n.title||'';
    contentInput.value = n.content||'';
    tagsInput.value = n.tags||'';
    pinBtn.textContent = n.pinned ? 'Unpin' : 'Pin';
  }
  renderNotesList();
  updateNoteWordCount();
  loadNoteBacklinks(id);
}
async function createNote() {
  const n = await safeFetch('/api/notes', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({title:'New Note', content:''})}, null);
  if (!n || !n.id) { toast('Failed to create note', 'error'); return; }
  await loadNotes();
  selectNote(n.id);
}
function exportCurrentNote() {
  if (!currentNoteId) { toast('No note selected', 'warning'); return; }
  window.location = `/api/notes/${currentNoteId}/export`;
}

function openWikiLink(title) {
  // Switch to notes tab and open the linked note
  document.querySelector('[data-tab="notes"]')?.click();
  setTimeout(() => {
    const note = (typeof allNotes !== 'undefined' ? allNotes : []).find(n => n.title === title);
    if (note) {
      selectNote(note.id);
    } else {
      // Create a new note with this title
      if (confirm('Note "' + title + '" does not exist. Create it?')) {
        createNoteWithTitle(title);
      }
    }
  }, 200);
}

async function createNoteWithTitle(title) {
  const r = await safeFetch('/api/notes', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({title, content:''})}, null);
  if (r && r.id) {
    loadNotes();
    setTimeout(() => selectNote(r.id), 300);
  }
}

let _noteTemplatesCache = [];
async function toggleNoteTemplates() {
  const dd = document.getElementById('note-template-dropdown');
  const list = document.getElementById('note-template-list');
  if (!dd || !list) return;
  if (dd.style.display === 'block') { dd.style.display = 'none'; return; }
  dd.style.display = 'block';
  _noteTemplatesCache = await safeFetch('/api/notes/templates', {}, []);
  list.innerHTML = _noteTemplatesCache.map((t, idx) => `
    <div class="note-template-item" data-note-action="apply-note-template" data-note-template-index="${idx}" role="button" tabindex="0">
      <span class="note-template-item-icon">${escapeHtml(t.icon || '\u{1F4DD}')}</span>
      <span class="note-template-item-label">${escapeHtml(t.name)}</span>
    </div>
  `).join('');
  setTimeout(() => document.addEventListener('click', function closer(e) {
    if (!dd.contains(e.target)) { dd.style.display = 'none'; document.removeEventListener('click', closer); }
  }), 10);
}

async function applyNoteTemplateByIndex(idx) {
  const t = _noteTemplatesCache[idx];
  const dropdown = document.getElementById('note-template-dropdown');
  if (!dropdown) return;
  if (!t) return;
  dropdown.style.display = 'none';
  const r = await safeFetch('/api/notes', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({title: t.name, content: t.content})}, null);
  if (r && r.id) {
    loadNotes();
    setTimeout(() => selectNote(r.id), 300);
  }
}

async function deleteNote() {
  if (!confirm('Delete this note?')) return;
  if (!currentNoteId) return;
  const titleInput = document.getElementById('note-title');
  const contentInput = document.getElementById('note-content');
  if (!titleInput || !contentInput) return;
  try {
    await _workspaceFetchOk(`/api/notes/${currentNoteId}`, {method:'DELETE'}, 'Failed to delete note');
    currentNoteId = null;
    titleInput.value = '';
    contentInput.value = '';
    await loadNotes();
  } catch (e) {
    toast(e.message || 'Failed to delete note', 'error');
  }
}
function filterNotes() {
  const searchInput = document.getElementById('notes-search');
  const list = document.getElementById('notes-list');
  if (!searchInput || !list) return;
  const q = searchInput.value.toLowerCase();
  if (!q) { renderNotesList(); return; }
  const filtered = allNotes.filter(n => (n.title||'').toLowerCase().includes(q) || (n.content||'').toLowerCase().includes(q));
  list.innerHTML = renderNoteListHtml(filtered, 'No matches');
}

function updateNoteWordCount() {
  const text = document.getElementById('note-content')?.value || '';
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  const chars = text.length;
  const el = document.getElementById('note-word-count');
  if (el) el.textContent = words > 0 ? `${words} words | ${chars} chars` : '';
}

function autoSaveNote() {
  if (!currentNoteId) return;
  clearTimeout(saveTimer);
  saveTimer = setTimeout(async () => {
    const titleInput = document.getElementById('note-title');
    const contentInput = document.getElementById('note-content');
    if (!titleInput || !contentInput) return;
    try {
      await _workspaceFetchOk(`/api/notes/${currentNoteId}`, {method:'PUT', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({title:titleInput.value, content:contentInput.value})}, 'Note save failed');
      await loadNotes();
    } catch(e) { toast(e.message || 'Note save failed', 'error'); }
  }, 500);
}

/* ─── Benchmark ─── */
async function runBenchmark(mode) {
  const runBtn = document.getElementById('bench-run-btn');
  const progressEl = document.getElementById('bench-progress');
  const resultsEl = document.getElementById('bench-results');
  if (!runBtn || !progressEl || !resultsEl) return;
  runBtn.disabled = true;
  progressEl.style.display = 'block';
  resultsEl.innerHTML = '';
  try {
    await _workspaceFetchOk('/api/benchmark/run', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({mode}),
    }, 'Could not start benchmark');
    pollBenchmark();
  } catch (e) {
    runBtn.disabled = false;
    progressEl.style.display = 'none';
    toast(e.message || 'Could not start benchmark', 'error');
  }
}

let _benchPoll = null;
function pollBenchmark() {
  if (_benchPoll) clearInterval(_benchPoll);
  window.NomadShellRuntime?.stopInterval('benchmark.status');
  const poll = async () => {
    const fillEl = document.getElementById('bench-fill');
    const stageEl = document.getElementById('bench-stage');
    const pctEl = document.getElementById('bench-pct');
    if (!fillEl || !stageEl || !pctEl) return;
    const s = await _workspaceFetchJsonSafe('/api/benchmark/status', {}, null, 'Could not load benchmark status');
    if (!s) return;
    fillEl.style.width = s.progress + '%';
    stageEl.textContent = s.stage;
    pctEl.textContent = s.progress + '%';

    if (s.status === 'complete' || s.status === 'error') {
      const runBtn = document.getElementById('bench-run-btn');
      const progressEl = document.getElementById('bench-progress');
      if (_benchPoll) clearInterval(_benchPoll);
      _benchPoll = null;
      window.NomadShellRuntime?.stopInterval('benchmark.status');
      if (runBtn) runBtn.disabled = false;
      if (progressEl) progressEl.style.display = 'none';
      if (s.status === 'complete' && s.results) showBenchResults(s.results);
      if (s.status === 'error') toast('Benchmark failed: ' + s.stage, 'error');
      loadBenchHistory();
    }
  };
  if (window.NomadShellRuntime) {
    _benchPoll = window.NomadShellRuntime.startInterval('benchmark.status', poll, 1000, {
      tabId: 'benchmark',
      requireVisible: true,
    });
    return;
  }
  _benchPoll = setInterval(poll, 1000);
}

function showBenchResults(r) {
  const resultsEl = document.getElementById('bench-results');
  if (!resultsEl) return;
  resultsEl.innerHTML = `
    <div class="benchmark-results-overview">
      <div class="benchmark-score-hero"><div class="bench-big"><span>${r.nomad_score}</span></div><div class="benchmark-score-caption">NOMAD Score</div></div>
      <div class="benchmark-run-summary">
        <div class="benchmark-run-summary-kicker">LATEST RUN</div>
        <div class="benchmark-run-summary-title">This snapshot covers system throughput and model responsiveness.</div>
        <div class="benchmark-run-summary-copy">Use the score cards below for the immediate picture, then compare against history to spot drift or a machine that is falling behind.</div>
      </div>
    </div>
    <div class="bench-scores benchmark-metric-grid">
      <div class="bench-score"><div class="score-val">${r.cpu_score||0}</div><div class="score-label">CPU ops/s</div></div>
      <div class="bench-score"><div class="score-val">${r.memory_score||0}</div><div class="score-label">Memory MB/s</div></div>
      <div class="bench-score"><div class="score-val">${r.disk_read_score||0}</div><div class="score-label">Disk Read MB/s</div></div>
      <div class="bench-score"><div class="score-val">${r.disk_write_score||0}</div><div class="score-label">Disk Write MB/s</div></div>
      <div class="bench-score"><div class="score-val">${r.ai_tps||0}</div><div class="score-label">AI Speed (tok/s)</div></div>
      <div class="bench-score"><div class="score-val">${r.ai_ttft||0}</div><div class="score-label">Response Time (ms)</div></div>
    </div>
    <div class="benchmark-result-note">Compare this run against Diagnostics History below before changing hardware, storage, or model expectations.</div>
  `;
}

async function loadBenchHistory() {
  try {
    const history = await _workspaceFetchJson('/api/benchmark/history', {}, 'Could not load benchmark history');
    const el = document.getElementById('bench-history');
    if (!el) return;
    if (!history.length) { el.innerHTML = '<span class="benchmark-empty-state">No benchmarks run yet.</span>'; return; }
    const latest = history[0];
    const oldest = history[history.length - 1];
    const totalDelta = oldest && latest ? latest.nomad_score - oldest.nomad_score : 0;
    function delta(curr, prev) {
      if (!prev || curr == null || prev == null) return '';
      const d = curr - prev;
      if (d === 0) return '';
      const tone = d > 0 ? 'benchmark-delta-up' : 'benchmark-delta-down';
      return ` <span class="benchmark-delta ${tone}">${d > 0 ? '+' : ''}${d.toFixed ? d.toFixed(1) : d}</span>`;
    }
    el.innerHTML = `<div class="benchmark-history-summary">
      <div class="benchmark-history-stat">
        <span class="benchmark-history-stat-label">Tracked runs</span>
        <strong class="benchmark-history-stat-value">${history.length}</strong>
      </div>
      <div class="benchmark-history-stat">
        <span class="benchmark-history-stat-label">Latest score</span>
        <strong class="benchmark-history-stat-value">${latest.nomad_score}</strong>
      </div>
      <div class="benchmark-history-stat">
        <span class="benchmark-history-stat-label">Long trend</span>
        <strong class="benchmark-history-stat-value ${totalDelta >= 0 ? 'benchmark-delta-up' : 'benchmark-delta-down'}">${totalDelta >= 0 ? '+' : ''}${totalDelta}</strong>
      </div>
    </div>
    <div class="benchmark-history-shell"><table class="benchmark-history-table">
      <tr><th>Date</th><th>Score</th><th>CPU</th><th>Mem</th><th>Disk R</th><th>Disk W</th><th>AI tok/s</th></tr>
      ${history.map((h, i) => {
        const prev = history[i + 1]; // previous run (older)
        return `<tr>
          <td>${new Date(h.created_at).toLocaleDateString()}</td>
          <td><strong class="benchmark-score-pill">${h.nomad_score}</strong>${delta(h.nomad_score, prev?.nomad_score)}</td>
          <td>${h.cpu_score}${delta(h.cpu_score, prev?.cpu_score)}</td>
          <td>${h.memory_score}${delta(h.memory_score, prev?.memory_score)}</td>
          <td>${h.disk_read_score}${delta(h.disk_read_score, prev?.disk_read_score)}</td>
          <td>${h.disk_write_score}${delta(h.disk_write_score, prev?.disk_write_score)}</td>
          <td>${h.ai_tps}${delta(h.ai_tps, prev?.ai_tps)}</td>
        </tr>`;
      }).join('')}
    </table></div>`;
    // Also load extended benchmark results (AI inference, storage)
    const extResults = await safeFetch('/api/benchmark/results', {}, []);
    if (extResults.length) {
      el.innerHTML += `<div class="benchmark-tests-block"><div class="benchmark-subheading">Individual Tests</div>
        <div class="benchmark-history-shell"><table class="benchmark-history-table benchmark-history-table-secondary">
        <tr><th>Date</th><th>Test</th><th>Result</th></tr>
        ${extResults.slice(0, 10).map(r => {
          const scores = safeJsonParse(r.scores, {});
          let result = '';
          if (r.test_type === 'ai_inference') result = (scores.tps || 0) + ' tok/s (' + escapeHtml(scores.model || '') + ')';
          else if (r.test_type === 'storage') result = 'R: ' + (scores.read_mbps || 0) + ' MB/s, W: ' + (scores.write_mbps || 0) + ' MB/s';
          else result = JSON.stringify(scores).substring(0, 60);
          return '<tr><td>' + new Date(r.created_at).toLocaleDateString() + '</td><td class="benchmark-result-type">' + escapeHtml(r.test_type.replace('_', ' ')) + '</td><td class="benchmark-result-mono">' + result + '</td></tr>';
        }).join('')}
        </table></div></div>`;
    }
  } catch(e) {
    const el = document.getElementById('bench-history');
    if (el) el.innerHTML = '<span class="benchmark-empty-state">Failed to load history</span>';
  }
}

async function runAIBenchmark() {
  const btn = document.getElementById('bench-ai-btn');
  if (btn) btn.disabled = true;
  const modelSel = document.getElementById('model-select');
  const model = modelSel ? modelSel.value : '';
  if (!model) { toast('Select an AI model first (go to AI Chat tab)', 'warning'); if (btn) btn.disabled = false; return; }
  toast('Running AI inference benchmark...', 'info');
  const r = await safeFetch('/api/benchmark/ai-inference', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({model})}, null);
  if (btn) btn.disabled = false;
  if (r) {
    toast(`AI Benchmark: ${r.tokens_per_sec} tokens/sec (${r.model})`, 'success');
    loadBenchHistory();
  } else {
    toast('AI benchmark failed — is a model loaded?', 'error');
  }
}

async function runStorageBenchmark() {
  const btn = document.getElementById('bench-storage-btn');
  if (btn) btn.disabled = true;
  toast('Running storage I/O benchmark (32MB read/write)...', 'info');
  const r = await safeFetch('/api/benchmark/storage', {method:'POST'}, null);
  if (btn) btn.disabled = false;
  if (r) {
    toast(`Storage: Read ${r.read_mbps} MB/s, Write ${r.write_mbps} MB/s`, 'success');
    loadBenchHistory();
  } else {
    toast('Storage benchmark failed', 'error');
  }
}

/* ─── Settings ─── */
async function loadSettings() {
  try {
    const s = await _workspaceFetchJson('/api/settings', {}, 'Could not load settings');
    const aiNameInput = document.getElementById('ai-name-input');
    if (s.ai_name) {
      aiName = s.ai_name;
      if (aiNameInput) aiNameInput.value = aiName;
    }
    if (s.theme && !localStorage.getItem('nomad-theme')) {
      setTheme(s.theme);
    }
  } catch(e) {}

  try {
    const n = await _workspaceFetchJson('/api/network', {}, 'Could not load network status');
    const lanUrlEl = document.getElementById('lan-url-setting');
    if (lanUrlEl) lanUrlEl.textContent = n.dashboard_url || '-';
  } catch(e) {}
}

let _saveNameTimer;
function saveAIName() {
  clearTimeout(_saveNameTimer);
  _saveNameTimer = setTimeout(async () => {
    const aiNameInput = document.getElementById('ai-name-input');
    if (!aiNameInput) return;
    aiName = aiNameInput.value || 'AI';
    try {
      await _workspaceFetchOk('/api/settings', {
        method:'PUT',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({ai_name: aiName}),
      }, 'Could not save assistant name');
    } catch (e) {
      console.warn('Could not save assistant name:', e.message);
    }
  }, 500);
}

async function loadSystemInfo() {
  const gaugesEl = document.getElementById('system-gauges');
  const systemInfoEl = document.getElementById('system-info');
  const dataDirEl = document.getElementById('data-dir');
  const diskDevicesEl = document.getElementById('disk-devices');
  if (!gaugesEl || !systemInfoEl || !dataDirEl || !diskDevicesEl) return;
  try {
    const s = await _workspaceFetchJson('/api/system', {}, 'Could not load system info');

    // Gauges
    function gaugeColor(pct) { return pct > 90 ? 'gauge-red' : pct > 70 ? 'gauge-orange' : 'gauge-green'; }
    gaugesEl.innerHTML = `
      <div class="gauge-card ${gaugeColor(s.cpu_percent)}">
        <div class="gauge-label">CPU</div>
        <div class="gauge-value">${s.cpu_percent}%</div>
        <div class="gauge-bar"><div class="fill" style="width:${s.cpu_percent}%"></div></div>
      </div>
      <div class="gauge-card ${gaugeColor(s.ram_percent)}">
        <div class="gauge-label">Memory</div>
        <div class="gauge-value">${s.ram_percent}%</div>
        <div class="gauge-bar"><div class="fill" style="width:${s.ram_percent}%"></div></div>
      </div>
      <div class="gauge-card ${gaugeColor(s.swap_percent)}">
        <div class="gauge-label">Swap</div>
        <div class="gauge-value">${s.swap_percent}%</div>
        <div class="gauge-bar"><div class="fill" style="width:${s.swap_percent}%"></div></div>
      </div>
      <div class="gauge-card gauge-blue">
        <div class="gauge-label">Uptime</div>
        <div class="gauge-value" style="font-size:16px;">${s.uptime}</div>
        <div class="gauge-bar"><div class="fill" style="width:100%"></div></div>
      </div>
    `;

    // System info
    systemInfoEl.innerHTML = `
      <div class="setting-row"><span class="setting-label">Version</span><span class="setting-value">v${s.version}</span></div>
      <div class="setting-row"><span class="setting-label">Platform</span><span class="setting-value">${s.platform}</span></div>
      <div class="setting-row"><span class="setting-label">Hostname</span><span class="setting-value">${s.hostname}</span></div>
      <div class="setting-row"><span class="setting-label">CPU</span><span class="setting-value">${s.cpu}</span></div>
      <div class="setting-row"><span class="setting-label">Cores</span><span class="setting-value">${s.cpu_cores_physical} physical / ${s.cpu_cores} logical</span></div>
      <div class="setting-row"><span class="setting-label">RAM</span><span class="setting-value">${s.ram_used} / ${s.ram_total} (${s.ram_percent}%)</span></div>
      <div class="setting-row"><span class="setting-label">Swap</span><span class="setting-value">${s.swap_used} / ${s.swap_total}</span></div>
      <div class="setting-row"><span class="setting-label">GPU</span><span class="setting-value">${s.gpu}${s.gpu_vram ? ' ('+s.gpu_vram+')' : ''}</span></div>
      <div class="setting-row"><span class="setting-label">NOMAD Data</span><span class="setting-value">${s.nomad_disk_used}</span></div>
    `;
    dataDirEl.textContent = s.data_dir;

    // Disk devices
    const dd = diskDevicesEl;
    if (s.disk_devices && s.disk_devices.length) {
      dd.innerHTML = s.disk_devices.map(d => {
        const color = d.percent > 90 ? 'var(--red)' : d.percent > 75 ? 'var(--orange)' : 'var(--accent)';
        return `<div class="disk-device">
          <div class="disk-label"><span>${d.mountpoint} (${d.fstype})</span><span>${d.used} / ${d.total} (${d.percent}%)</span></div>
          <div class="progress-bar"><div class="fill" style="width:${d.percent}%;background:${color};"></div></div>
        </div>`;
      }).join('');
    } else {
      dd.innerHTML = `<div class="setting-row"><span class="setting-label">Disk Free</span><span class="setting-value">${s.disk_free} / ${s.disk_total}</span></div>`;
    }
  } catch(e) { systemInfoEl.innerHTML = '<span class="text-red">Failed to load</span>'; }
}

let _liveGaugeInt = null;
function startLiveGauges() {
  if (_liveGaugeInt) clearInterval(_liveGaugeInt);
  window.NomadShellRuntime?.stopInterval('settings.live-gauges');
  const poll = async () => {
    const l = await _workspaceFetchJsonSafe('/api/system/live', {}, null, 'Could not load live system gauges');
    if (l) {
      const gauges = document.querySelectorAll('#system-gauges .gauge-card');
      if (gauges.length >= 3) {
        function updateGauge(g, pct) {
          g.querySelector('.gauge-value').textContent = pct + '%';
          g.querySelector('.gauge-bar .fill').style.width = pct + '%';
          g.className = 'gauge-card ' + (pct > 90 ? 'gauge-red' : pct > 70 ? 'gauge-orange' : 'gauge-green');
        }
        updateGauge(gauges[0], l.cpu_percent);
        updateGauge(gauges[1], l.ram_percent);
        updateGauge(gauges[2], l.swap_percent);
      }
      return;
    }
    const vals = document.querySelectorAll('#system-gauges .gauge-card .gauge-value');
    vals.forEach(g => { if (!g.textContent.endsWith('?')) g.textContent += ' ?'; });
  };
  if (window.NomadShellRuntime) {
    _liveGaugeInt = window.NomadShellRuntime.startInterval('settings.live-gauges', poll, 3000, {
      tabId: 'settings',
      requireVisible: true,
    });
    return;
  }
  _liveGaugeInt = setInterval(async () => {
    if (!document.getElementById('tab-settings').classList.contains('active')) { clearInterval(_liveGaugeInt); _liveGaugeInt = null; return; }
    await poll();
  }, 3000);
}

async function loadModelManager() {
  const el = document.getElementById('model-list');
  const recommendedEl = document.getElementById('recommended-models');
  if (!el || !recommendedEl) return;
  try {
    const [models, rec] = await Promise.all([
      _workspaceFetchJson('/api/ai/models', {}, 'Could not load installed models'),
      _workspaceFetchJson('/api/ai/recommended', {}, 'Could not load recommended models'),
    ]);
    if (!models.length) {
      el.innerHTML = '<div class="settings-empty-state model-list-empty">No models downloaded</div>';
    } else {
      el.innerHTML = models.map(m => `
        <div class="model-item">
          <span class="model-name">${m.name}</span>
          <span class="model-item-actions">
            <span class="model-size">${(m.size/1e9).toFixed(1)} GB</span>
            <button class="btn btn-sm btn-danger" type="button" data-shell-action="delete-model" data-model-name="${escapeAttr(m.name)}">Delete</button>
          </span>
        </div>
      `).join('');
    }

    const installed = new Set(models.map(m => m.name));
    recommendedEl.innerHTML = rec.map(r => `
      <div class="model-item">
        <span><span class="model-name">${r.name}</span> <span class="model-size">${r.desc} (${r.size})</span></span>
        ${installed.has(r.name)
          ? '<span class="runtime-status-installed">Installed</span>'
          : `<button class="btn btn-sm btn-primary" type="button" data-shell-action="pull-settings-model" data-model-name="${escapeAttr(r.name)}">Pull</button>`}
      </div>
    `).join('');
  } catch(e) {
    el.innerHTML = '<div class="settings-empty-state model-list-empty">Could not load models right now.</div>';
  }
}

function deleteModel(name, btn) {
  if (!btn) btn = event.target;
  if (!btn.dataset.confirm) {
    btn.dataset.confirm = '1';
    btn.textContent = 'Confirm?';
      btn.style.background = 'var(--red)'; btn.style.color = getThemeCssVar('--text-inverse', '#fff');
    setTimeout(() => { btn.textContent = 'Delete'; btn.style.background = ''; btn.style.color = ''; delete btn.dataset.confirm; }, 3000);
    return;
  }
  apiPost('/api/ai/delete', {model: name}).then(d => {
      toast(`Deleted ${name}`, 'warning');
      loadModelManager(); loadModels();
    }).catch(e => toast(e.message || 'Delete failed', 'error'));
}

async function pullFromSettings(name) {
  try {
    await _workspaceFetchOk('/api/ai/pull', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({model:name}),
    }, `Could not start download for ${name}`);
    toast(`Pulling ${name}...`);
    document.querySelector('[data-tab="ai-chat"]')?.click();
    pollPullProgress();
  } catch (e) {
    toast(e.message || 'Could not start model download', 'error');
  }
}

/* ─── Network Status ─── */
let _backendFailCount = 0;
async function checkNetwork() {
  try {
    const n = await _workspaceFetchJson('/api/network', {}, 'Could not load network status');
    _backendFailCount = 0;
    const el = document.getElementById('net-status');
    const label = n.online ? 'Online' : 'Offline';
    if (el) {
      el.innerHTML = `<span class="network-status-inline ${n.online ? 'is-online' : 'is-offline'}"><span class="network-status-dot"></span><span>${label} &middot; ${escapeHtml(n.lan_ip)}</span></span>`;
    }
    // Clear connection-lost banner if it was shown
    const lostBanner = document.getElementById('connection-lost');
    if (lostBanner) lostBanner.style.display = 'none';
    // LAN banner
    const banner = document.getElementById('lan-banner');
    if (banner && n.lan_ip !== '127.0.0.1') {
      banner.style.display = 'flex';
      banner.innerHTML = `Access from other devices on your network: <a href="${escapeAttr(n.dashboard_url)}">${escapeHtml(n.dashboard_url)}</a>`;
    } else if (banner) {
      banner.style.display = 'none';
      banner.innerHTML = '';
    }
  } catch(e) {
    _backendFailCount++;
    if (_backendFailCount >= 2) {
      const el = document.getElementById('net-status');
      if (el) {
        el.innerHTML = '<span class="network-status-inline is-offline"><span class="network-status-dot"></span><span>Disconnected</span></span>';
      }
      // Show connection-lost banner
      let lostBanner = document.getElementById('connection-lost');
      if (!lostBanner) {
        lostBanner = document.createElement('div');
        lostBanner.id = 'connection-lost';
        lostBanner.className = 'connection-lost-banner';
        lostBanner.textContent = 'Connection to backend lost — retrying automatically...';
        const headerEl = Array.from(document.querySelectorAll('.status-strip'))
          .find((candidate) => !candidate.hidden && getComputedStyle(candidate).display !== 'none')
          || document.querySelector('.main-content');
        if (headerEl) headerEl.prepend(lostBanner);
        else document.body.prepend(lostBanner);
      }
      lostBanner.style.display = 'block';
    }
  }
}

/* ─── Setup Wizard ─── */
let _wizDrivePath = '';
let _wizTier = 'essential';
let _wizTiers = {};

function setWizardSectionVisibility(target, visible, display = 'block') {
  const el = typeof target === 'string' ? document.getElementById(target) : target;
  if (!el) return null;
  el.classList.toggle('is-hidden', !visible);
  el.hidden = !visible;
  if (visible) {
    el.style.display = display;
  } else {
    el.style.removeProperty('display');
  }
  return el;
}

function clearWizardUrlFlag() {
  const url = new URL(window.location.href);
  if (!url.searchParams.has('wizard')) return;
  url.searchParams.delete('wizard');
  history.replaceState(null, '', `${url.pathname}${url.search}${url.hash}`);
}

function refreshOnboardingSurfaces() {
  if (typeof loadServices === 'function' && isWorkspaceTabActive('services')) {
    loadServices();
  }
  if (typeof loadGettingStarted === 'function' && isWorkspaceTabActive('services')) {
    loadGettingStarted();
  }
}

async function persistOnboardingComplete() {
  if (window.NOMAD_FIRST_RUN_COMPLETE === true) return;
  window.NOMAD_FIRST_RUN_COMPLETE = true;
  window.NOMAD_WIZARD_SHOULD_LAUNCH = false;
  refreshOnboardingSurfaces();
  try { await apiPost('/api/settings/wizard-complete'); } catch (_) {}
}

async function checkWizard() {
  const forced = new URLSearchParams(location.search).has('wizard');
  const shouldAutoLaunch = forced || (window.NOMAD_WIZARD_SHOULD_LAUNCH && isWorkspaceTabActive('services'));
  if (!shouldAutoLaunch) return;

  const wizard = document.getElementById('wizard');
  if (!wizard) return;

  try {
    const state = await _workspaceFetchJson('/api/wizard/progress', {}, 'Could not load setup progress');
    if (state?.status === 'running') {
      setShellVisibility(wizard, true);
      setShellVisibility(document.getElementById('wiz-mini-banner'), false);
      wizGoPage(4);
      wizPollProgress();
      return;
    }
    if (state?.status === 'complete' && window.NOMAD_FIRST_RUN_COMPLETE === false) {
      setShellVisibility(wizard, true);
      setShellVisibility(document.getElementById('wiz-mini-banner'), false);
      await wizShowComplete(state);
      return;
    }
  } catch (_) {
    // Fall back to the welcome page if progress state is unavailable.
  }

  wizGoPage(1);
  setShellVisibility(wizard, true);
  setShellVisibility(document.getElementById('wiz-mini-banner'), false);
}

function wizGoPage(n) {
  for (let i = 1; i <= 5; i++) {
    setWizardSectionVisibility('wiz-page-' + i, i === n, 'grid');
  }
  if (n === 2) wizLoadDrives();
  if (n === 3) wizLoadTiers();
}

function setWizardStorageStatus(message, success = false) {
  const el = document.getElementById('wiz-storage-status');
  const nextBtn = document.getElementById('wiz-storage-next');
  if (!el) return;
  el.textContent = message;
  el.classList.toggle('wizard-status-line-success', success);
  if (nextBtn) nextBtn.disabled = !success;
}

async function wizLoadDrives() {
  const el = document.getElementById('wiz-drives');
  if (!el) return;
  let drives = [];
  try {
    drives = await _workspaceFetchJson('/api/drives', {}, 'Could not scan storage locations');
  } catch (_) {
    el.innerHTML = '<div class="utility-empty-state">Unable to list storage locations right now. You can retry or enter a custom path.</div>';
    setWizardStorageStatus('Storage scan failed. Enter a custom path or retry.', false);
    return;
  }
  if (!Array.isArray(drives) || !drives.length) {
    el.innerHTML = '<div class="utility-empty-state">No writable drives were detected yet. Enter a custom path to continue.</div>';
    setWizardStorageStatus('Enter a custom path to continue.', false);
    return;
  }
  let bestDrive = drives[0];
  drives.forEach(d => {
    if (d.free > (bestDrive?.free || 0)) bestDrive = d;
  });
  if (!_wizDrivePath && bestDrive) _wizDrivePath = bestDrive.path;

  el.innerHTML = drives.map(d => {
    const sel = d.path === _wizDrivePath;
    const pct = d.percent;
    const color = pct > 90 ? 'var(--red)' : pct > 75 ? 'var(--orange)' : 'var(--green)';
    return `<button type="button" class="wizard-drive-card${sel ? ' is-selected' : ''}" data-shell-action="wiz-select-drive" data-drive-path="${escapeAttr(d.path)}">
      <span class="wizard-drive-title">${escapeHtml(d.path)}</span>
      <span class="wizard-drive-copy">${escapeHtml(d.free_str)} free of ${escapeHtml(d.total_str)}</span>
      <div class="progress-bar wizard-drive-progress"><div class="fill" style="width:${pct}%;background:${color};"></div></div>
    </button>`;
  }).join('');
  setWizardStorageStatus(
    _wizDrivePath ? 'Data will be stored at: ' + _wizDrivePath + 'NOMADFieldDesk\\' : 'Select a drive above',
    !!_wizDrivePath
  );
}

function wizSelectDrive(path) { _wizDrivePath = path; wizLoadDrives(); }

function wizSetCustomPath() {
  const input = document.getElementById('wiz-custom-path');
  const path = input?.value?.trim() || '';
  if (!path) {
    setWizardStorageStatus('Enter a folder path first.', false);
    input?.focus();
    return;
  }
  _wizDrivePath = path.endsWith('\\') ? path : path + '\\';
  setWizardStorageStatus('Custom path: ' + _wizDrivePath + 'NOMADFieldDesk\\', true);
}

// Custom tier selection state
let _wizCustomServices = [];
let _wizCustomModels = [];
let _wizCustomZims = [];

async function wizLoadTiers() {
  const el = document.getElementById('wiz-tiers');
  if (!el) return;
  try {
    _wizTiers = await _workspaceFetchJson('/api/content-tiers', {}, 'Could not load setup profiles');
  } catch (_) {
    el.innerHTML = '<div class="utility-empty-state">Could not load setup profiles. Retry from Services or come back later.</div>';
    setWizardSectionVisibility('wiz-tier-detail', false);
    setWizardSectionVisibility('wiz-custom-panel', false);
    return;
  }
  const tierOrder = ['essential','standard','maximum','custom'];
  const tierIcons = {essential:'&#9733;', standard:'&#9733;&#9733;', maximum:'&#9733;&#9733;&#9733;', custom:'&#9881;'};
  const tierColors = {essential:'var(--green)', standard:'var(--accent)', maximum:'var(--purple)', custom:'var(--orange)'};
  // Add a virtual "custom" tier
  if (!_wizTiers['custom']) {
    _wizTiers['custom'] = {name:'Custom', desc:'Choose exactly which services, models, and content packs to install', services:[], zims:[], models:[], zim_count:0, est_size:'Varies'};
  }
  el.innerHTML = tierOrder.map(tid => {
    const t = _wizTiers[tid]; if (!t) return '';
    const sel = tid === _wizTier;
    const detail = tid === 'custom'
      ? '<div class="wizard-tier-meta">Pick individual items below</div>'
      : `<div class="wizard-tier-meta">${t.services.length} tools + ${t.zim_count || t.zims.length} content packs + ${t.models.length} AI model${t.models.length>1?'s':''}</div>`;
    return '<button type="button" class="wizard-tier-card' + (sel ? ' is-selected' : '') + '" data-shell-action="wiz-select-tier" data-tier-id="' + tid + '">'
      + '<div class="wizard-tier-copy">'
      + '<div class="wizard-tier-title" style="color:' + tierColors[tid] + ';">' + tierIcons[tid] + ' ' + t.name + '</div>'
      + '<div class="wizard-tier-desc">' + t.desc + '</div>'
      + detail
      + '</div>'
      + '<div class="wizard-tier-size">'
      + '<div class="wizard-tier-size-value" style="color:' + tierColors[tid] + ';">' + t.est_size + '</div>'
      + (tid !== 'custom' ? '<div class="wizard-tier-size-label">estimated</div>' : '')
      + '</div>'
      + '</button>';
  }).join('');
  // Show/hide custom panel and tier detail
  if (_wizTier === 'custom') {
    setWizardSectionVisibility('wiz-custom-panel', true);
    setWizardSectionVisibility('wiz-tier-detail', false);
    wizBuildCustomPanel();
  } else {
    setWizardSectionVisibility('wiz-custom-panel', false);
    wizShowTierDetail();
  }
}

function wizBuildCustomPanel() {
  // Populate custom checkboxes from the "maximum" tier (full list)
  const max = _wizTiers['maximum'] || _wizTiers['standard'] || {};
  const allServices = ['ollama','kiwix','cyberchef','kolibri','qdrant','stirling','flatnotes'];
  const allModels = ['qwen3:4b','qwen3:8b','alibayram/medgemma','deepseek-r1:8b','gemma3:4b','llama3.2:3b'];
  // If no custom selections yet, pre-select essentials
  if (!_wizCustomServices.length) _wizCustomServices = ['ollama','kiwix','cyberchef','stirling'];
  if (!_wizCustomModels.length) _wizCustomModels = ['qwen3:4b'];

  const svcEl = document.getElementById('wiz-custom-services');
  svcEl.innerHTML = allServices.map(s => {
    const checked = _wizCustomServices.includes(s);
    const name = (SVC[s] || {}).name || s;
    return '<label class="wizard-custom-chip">'
      + '<input type="checkbox" class="wizard-custom-check" ' + (checked?'checked':'') + ' data-change-action="wiz-toggle-custom" data-wiz-custom-type="service" data-wiz-custom-value="' + s + '">'
      + escapeHtml(name) + '</label>';
  }).join('');

  const modEl = document.getElementById('wiz-custom-models');
  modEl.innerHTML = allModels.map(m => {
    const checked = _wizCustomModels.includes(m);
    return '<label class="wizard-custom-chip">'
      + '<input type="checkbox" class="wizard-custom-check" ' + (checked?'checked':'') + ' data-change-action="wiz-toggle-custom" data-wiz-custom-type="model" data-wiz-custom-value="' + escapeHtml(m) + '">'
      + escapeHtml(m) + '</label>';
  }).join('');

  // Group ZIMs by category (from maximum tier)
  const allZims = max.zims || [];
  const cats = {};
  allZims.forEach(z => { const c = z.category || 'Other'; if (!cats[c]) cats[c] = []; cats[c].push(z); });
  // Default: select essential ZIMs only
  if (!_wizCustomZims.length) {
    const ess = _wizTiers['essential'];
    if (ess) _wizCustomZims = ess.zims.map(z => z.filename);
  }

  const zimEl = document.getElementById('wiz-custom-zims');
  zimEl.innerHTML = Object.entries(cats).map(([cat, items]) => {
    return '<div class="wizard-custom-zim-group">'
      + '<div class="wizard-custom-zim-group-title">' + escapeHtml(cat) + '</div>'
      + items.map(z => {
        const checked = _wizCustomZims.includes(z.filename);
        return '<label class="wizard-custom-zim-row">'
          + '<input type="checkbox" class="wizard-custom-check" ' + (checked?'checked':'') + ' data-change-action="wiz-toggle-custom" data-wiz-custom-type="zim" data-wiz-custom-value="' + escapeHtml(z.filename) + '">'
          + '<span class="wizard-custom-zim-name">' + escapeHtml(z.name) + '</span>'
          + '<span class="wizard-custom-zim-size">' + escapeHtml(z.size) + '</span>'
          + '</label>';
      }).join('')
      + '</div>';
  }).join('');
}

function wizToggleCustom(type, value, checked) {
  if (type === 'service') {
    if (checked) { if (!_wizCustomServices.includes(value)) _wizCustomServices.push(value); }
    else { _wizCustomServices = _wizCustomServices.filter(s => s !== value); }
  } else if (type === 'model') {
    if (checked) { if (!_wizCustomModels.includes(value)) _wizCustomModels.push(value); }
    else { _wizCustomModels = _wizCustomModels.filter(m => m !== value); }
  } else if (type === 'zim') {
    if (checked) { if (!_wizCustomZims.includes(value)) _wizCustomZims.push(value); }
    else { _wizCustomZims = _wizCustomZims.filter(z => z !== value); }
  }
}

function wizCustomSelectAll() {
  const max = _wizTiers['maximum'] || {};
  _wizCustomZims = (max.zims || []).map(z => z.filename);
  wizBuildCustomPanel();
}

function wizCustomDeselectAll() {
  _wizCustomZims = [];
  wizBuildCustomPanel();
}

function wizSelectTier(tid) { _wizTier = tid; wizLoadTiers(); }

function wizShowTierDetail() {
  const t = _wizTiers[_wizTier]; if (!t) return;
  const el = setWizardSectionVisibility('wiz-tier-detail', true);
  if (!el) return;
  const cats = {};
  (t.zims || []).forEach(z => { if (!cats[z.category]) cats[z.category] = []; cats[z.category].push(z); });
  el.innerHTML = '<div class="wizard-tier-detail-shell">'
    + '<div class="wizard-tier-detail-title">What\'s included in ' + escapeHtml(t.name) + ':</div>'
    + '<div class="wizard-tier-detail-row"><span class="wizard-tier-detail-label">Services</span><span class="wizard-tier-detail-copy">' + t.services.map(function(s){return escapeHtml((SVC[s]||{}).name||s);}).join(', ') + '</span></div>'
    + '<div class="wizard-tier-detail-row"><span class="wizard-tier-detail-label">AI Models</span><span class="wizard-tier-detail-copy">' + t.models.map(escapeHtml).join(', ') + '</span></div>'
    + '<div class="wizard-tier-detail-row wizard-tier-detail-row-stack"><span class="wizard-tier-detail-label">Content Packs (' + (t.zim_count || t.zims.length) + ')</span></div>'
    + Object.entries(cats).map(function([cat, items]) {
      return '<div class="wizard-tier-group"><div class="wizard-tier-group-title">' + escapeHtml(cat) + '</div>'
      + items.map(function(z){return '<div class="wizard-tier-zim-row"><span class="wizard-tier-zim-name">' + escapeHtml(z.name) + '</span><span class="wizard-tier-zim-size">' + escapeHtml(z.size) + '</span></div>';}).join('')
      + '</div>';}).join('')
    + '</div>';
}

async function wizStartSetup() {
  let services, zims, models;
  if (_wizTier === 'custom') {
    services = _wizCustomServices;
    models = _wizCustomModels;
    // Resolve filenames to full ZIM objects
    const max = _wizTiers['maximum'] || _wizTiers['standard'] || {};
    const allZims = max.zims || [];
    zims = allZims.filter(z => _wizCustomZims.includes(z.filename));
  } else {
    const t = _wizTiers[_wizTier]; if (!t) return;
    services = t.services;
    zims = t.zims;
    models = t.models;
  }

  if (![services, zims, models].some(items => Array.isArray(items) && items.length)) {
    toast('Select at least one service, model, or content pack before starting setup.', 'warning');
    return;
  }

  window.NOMAD_WIZARD_SHOULD_LAUNCH = true;
  wizGoPage(4);
  setWizardSectionVisibility('wiz-errors', false);
  setWizardSectionVisibility('wiz-stall-help', false);
  setShellVisibility(document.getElementById('wiz-mini-banner'), false);
  try {
    if (_wizDrivePath) {
      await _workspaceFetchOk('/api/settings/data-dir', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({path: _wizDrivePath}),
      }, 'Could not save setup storage path');
    }
    await _workspaceFetchOk('/api/wizard/setup', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({services: services, zims: zims, models: models}),
    }, 'Could not start setup');
    wizPollProgress();
  } catch (e) {
    toast(e.message || 'Could not start setup', 'error');
    wizGoPage(3);
  }
}

let _wizMinimized = false;

function wizMinimize() {
  _wizMinimized = true;
  setShellVisibility(document.getElementById('wizard'), false);
  setShellVisibility(document.getElementById('wiz-mini-banner'), true);
}

function wizRestore() {
  _wizMinimized = false;
  setShellVisibility(document.getElementById('wiz-mini-banner'), false);
  setShellVisibility(document.getElementById('wizard'), true);
}

let _wizPollInt = null;
let _wizLastProgress = 0;
let _wizStallCount = 0;
function stopWizardProgressPoll() {
  if (_wizPollInt) {
    clearInterval(_wizPollInt);
    _wizPollInt = null;
  }
  window.NomadShellRuntime?.stopInterval('wizard.progress');
}
function wizPollProgress() {
  stopWizardProgressPoll();
  _wizLastProgress = 0;
  _wizStallCount = 0;
  const runner = async () => {
    try {
      const s = await _workspaceFetchJsonSafe('/api/wizard/progress', {}, null, 'Could not load setup progress');
      if (!s) return;
      const overallFillEl = document.getElementById('wiz-overall-fill');
      const overallPctEl = document.getElementById('wiz-overall-pct');
      const currentItemEl = document.getElementById('wiz-current-item');
      const itemFillEl = document.getElementById('wiz-item-fill');
      const itemPctEl = document.getElementById('wiz-item-pct');
      const miniPctEl = document.getElementById('wiz-mini-pct');
      const miniFillEl = document.getElementById('wiz-mini-fill');
      const miniItemEl = document.getElementById('wiz-mini-item');
      const phaseLabelEl = document.getElementById('wiz-phase-label');
      const completedListEl = document.getElementById('wiz-completed-list');
      if (!overallFillEl || !overallPctEl || !currentItemEl || !itemFillEl || !itemPctEl || !miniPctEl || !miniFillEl || !miniItemEl || !phaseLabelEl || !completedListEl) return;
      overallFillEl.style.width = s.overall_progress + '%';
      overallPctEl.textContent = s.overall_progress + '%';
      currentItemEl.textContent = s.current_item || '...';
      itemFillEl.style.width = s.item_progress + '%';
      itemPctEl.textContent = s.item_progress + '%';
      miniPctEl.textContent = s.overall_progress + '%';
      miniFillEl.style.width = s.overall_progress + '%';
      miniItemEl.textContent = s.current_item || '...';

      const phaseNames = {services:'Installing tools...', starting:'Starting services...', content:'Downloading offline content...', models:'Downloading AI models...', done:'Complete!'};
      phaseLabelEl.textContent = phaseNames[s.phase] || s.phase;

      if (s.overall_progress === _wizLastProgress && s.item_progress === 0) {
        _wizStallCount++;
      } else {
        _wizStallCount = 0;
        _wizLastProgress = s.overall_progress;
      }
      setWizardSectionVisibility('wiz-stall-help', _wizStallCount > 30);

      completedListEl.innerHTML = (s.completed || []).map(c =>
        `<div class="wizard-complete-row"><span class="wizard-complete-icon">&#10003;</span><span>${escapeHtml(c)}</span></div>`).join('');

      const errEl = document.getElementById('wiz-errors');
      if ((s.errors || []).length) {
        setWizardSectionVisibility(errEl, true);
        errEl.innerHTML = s.errors.map(e => `<div class="wizard-error-row">&#10007; ${escapeHtml(e)}</div>`).join('');
      } else if (errEl) {
        errEl.innerHTML = '';
        setWizardSectionVisibility(errEl, false);
      }

      if (s.status === 'complete') {
        stopWizardProgressPoll();
        setShellVisibility(document.getElementById('wiz-mini-banner'), false);
        if (_wizMinimized) {
          _wizMinimized = false;
          setShellVisibility(document.getElementById('wizard'), true);
        }
        setTimeout(() => wizShowComplete(s), 1000);
      }
    } catch(e) { /* poll error — server may be busy */ }
  };
  if (window.NomadShellRuntime) {
    _wizPollInt = window.NomadShellRuntime.startInterval('wizard.progress', runner, 2000, {
      requireVisible: true,
    });
    runner();
    return;
  }
  _wizPollInt = setInterval(runner, 2000);
  runner();
}

function wizSkipToComplete() {
  stopWizardProgressPoll();
  persistOnboardingComplete();
  wizShowComplete({completed:[], errors:['Setup was skipped — you can install services and content manually from the Services and Library tabs.']});
}

async function wizShowComplete(state) {
  wizGoPage(5);
  const lanUrlEl = document.getElementById('wiz-lan-url');
  const summaryEl = document.getElementById('wiz-summary');
  const errorSummaryEl = document.getElementById('wiz-error-summary');
  if (!lanUrlEl || !summaryEl || !errorSummaryEl) return;
  // Show LAN URL
  try {
    const net = await _workspaceFetchJson('/api/network', {}, 'Could not load LAN access URL');
    lanUrlEl.textContent = net.dashboard_url;
  } catch(e) {}
  const svcCount = state.completed.filter(c => ['ollama','kiwix','cyberchef','kolibri','qdrant','stirling'].includes(c)).length;
  const contentCount = state.completed.length - svcCount;
  summaryEl.innerHTML = `
    <div class="wizard-summary-card">
      <div class="wizard-summary-number wizard-summary-number-green">${svcCount}</div><div class="wizard-summary-label">Tools Installed</div>
    </div>
    <div class="wizard-summary-card">
      <div class="wizard-summary-number wizard-summary-number-accent">${contentCount}</div><div class="wizard-summary-label">Content Packs</div>
    </div>
    <div class="wizard-summary-card">
      <div class="wizard-summary-number ${state.errors.length === 0 ? 'wizard-summary-number-green' : 'wizard-summary-number-warning'}">${state.errors.length===0?'All Clear':state.errors.length+' Issues'}</div><div class="wizard-summary-label">Status</div>
    </div>`;
  if (state.errors.length) {
    setWizardSectionVisibility('wiz-error-summary', true);
    errorSummaryEl.innerHTML = `<div class="wizard-error-summary-card">`
      + state.errors.map(e => `<div class="wizard-error-row">&#10007; ${escapeHtml(e)}</div>`).join('') + `</div>`;
  } else {
    setWizardSectionVisibility('wiz-error-summary', false);
    errorSummaryEl.innerHTML = '';
  }
}

function skipWizard() {
  stopWizardProgressPoll();
  setShellVisibility(document.getElementById('wizard'), false);
  setShellVisibility(document.getElementById('wiz-mini-banner'), false);
  clearWizardUrlFlag();
  persistOnboardingComplete();
}

function closeTourWizard() {
  stopWizardProgressPoll();
  setShellVisibility(document.getElementById('wizard'), false);
  setShellVisibility(document.getElementById('wiz-mini-banner'), false);
  clearWizardUrlFlag();
  persistOnboardingComplete();
  refreshOnboardingSurfaces();
}

/* ─── Guided Tour ─── */
const TOUR_STEPS = [
  { tab: 'services', title: 'Your Command Center', text: 'This is your dashboard. Live widgets show inventory, power, weather, and alerts at a glance. Click any widget to drill into that section.', pos: 'center' },
  { tab: 'ai-chat', title: 'AI Chat', text: 'Chat with a private AI that runs entirely on your computer. It knows your inventory, contacts, and situation. No internet needed, no data leaves your machine.', pos: 'center' },
  { tab: 'kiwix-library', title: 'Offline Encyclopedia', text: 'Download Wikipedia, medical references, survival guides, and more. Choose Essential (~10 GB), Standard (~80 GB), or pick individual packs.', pos: 'center' },
  { tab: 'preparedness', title: 'Preparedness Tools', text: '25 tools organized into 5 categories: Supplies, People, Readiness, Knowledge, and Operations. Click a category at the top, then choose a specific tool.', pos: 'center' },
  { tab: 'maps', title: 'Offline Maps', text: 'Download maps for your area. Add waypoints, draw zones, measure distances, and plan routes — all without internet.', pos: 'center' },
  { tab: 'settings', title: 'Settings & System Health', text: 'Manage AI models, run system health checks, schedule recurring tasks, back up your data, and configure multi-node sync.', pos: 'center' },
];
let _tourStep = 0;
const TOUR_SESSION_KEY = 'nomad-guided-tour-state';
const TOUR_FOCUS_KEY = 'nomad-guided-tour-focus';

function _readTourSession() {
  try {
    const raw = sessionStorage.getItem(TOUR_SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (_) {
    return null;
  }
}

function _writeTourSession(step = _tourStep) {
  try {
    sessionStorage.setItem(TOUR_SESSION_KEY, JSON.stringify({ active: true, step }));
  } catch (_) {}
}

function _clearTourSession() {
  try {
    sessionStorage.removeItem(TOUR_SESSION_KEY);
  } catch (_) {}
}

function _queueTourFocusRestore(tabId = 'services') {
  try {
    sessionStorage.setItem(TOUR_FOCUS_KEY, tabId);
  } catch (_) {}
}

function _restoreTourFocusIfNeeded() {
  let tabId = '';
  try {
    tabId = sessionStorage.getItem(TOUR_FOCUS_KEY) || '';
    if (!tabId) return;
    sessionStorage.removeItem(TOUR_FOCUS_KEY);
  } catch (_) {
    return;
  }
  const tabBtn = document.querySelector(`.tab[data-tab="${tabId}"]`);
  if (tabBtn) requestAnimationFrame(() => tabBtn.focus());
}

function _renderTourStep(step) {
  const tourOverlay = document.getElementById('tour-overlay');
  const contentEl = document.getElementById('tour-content');
  const stepNumEl = document.getElementById('tour-step-num');
  const nextBtn = document.getElementById('tour-next-btn');
  const card = document.getElementById('tour-card');
  if (!contentEl || !stepNumEl || !nextBtn || !card) return;
  if (!tourOverlay) return false;
  setShellVisibility(tourOverlay, true);
  contentEl.innerHTML = `<h3 class="tour-content-title">${step.title}</h3><p class="tour-content-copy">${step.text}</p>`;
  stepNumEl.textContent = `${_tourStep+1} of ${TOUR_STEPS.length}`;
  nextBtn.textContent = _tourStep === TOUR_STEPS.length - 1 ? 'Done' : 'Next';
  card.style.top = '50%';
  card.style.left = '50%';
  card.style.transform = 'translate(-50%, -50%)';
  return true;
}

function startTour() {
  persistOnboardingComplete();
  setShellVisibility(document.getElementById('wizard'), false);
  setShellVisibility(document.getElementById('wiz-mini-banner'), false);
  clearWizardUrlFlag();
  _tourStep = 0;
  const tourOverlay = document.getElementById('tour-overlay');
  if (!tourOverlay) return;
  _writeTourSession(_tourStep);
  setShellVisibility(tourOverlay, true);
  showTourStep();
  loadServices();
}

function showTourStep() {
  const step = TOUR_STEPS[_tourStep];
  if (!step) { tourSkip(); return; }
  if (!_renderTourStep(step)) return;
  _writeTourSession(_tourStep);
  const activeTab = window.NOMAD_ACTIVE_TAB || getWorkspacePageTab();
  if (activeTab !== step.tab) {
    const openedInPlace = typeof openWorkspaceRouteAware === 'function'
      ? openWorkspaceRouteAware(step.tab)
      : !!document.querySelector(`.tab[data-tab="${step.tab}"]`)?.click();
    if (!openedInPlace) return;
  }
  document.getElementById('tour-next-btn')?.focus();
}

function tourNext() {
  _tourStep++;
  if (_tourStep >= TOUR_STEPS.length) {
    tourSkip();
  } else {
    showTourStep();
  }
}

function tourSkip() {
  const tourOverlay = document.getElementById('tour-overlay');
  _clearTourSession();
  _queueTourFocusRestore('services');
  if (tourOverlay) setShellVisibility(tourOverlay, false);
  const servicesTab = document.querySelector('.tab[data-tab="services"]');
  const activeTab = window.NOMAD_ACTIVE_TAB || getWorkspacePageTab();
  if (activeTab === 'services') {
    servicesTab?.focus();
    _restoreTourFocusIfNeeded();
    return;
  }
  if (typeof openWorkspaceRouteAware === 'function') {
    const openedInPlace = openWorkspaceRouteAware('services');
    if (openedInPlace) {
      _restoreTourFocusIfNeeded();
    }
    return;
  }
  servicesTab?.click();
  _restoreTourFocusIfNeeded();
}

function restoreGuidedTourIfNeeded() {
  _restoreTourFocusIfNeeded();
  const state = _readTourSession();
  if (!state?.active) return;
  const nextStep = Number.parseInt(state.step, 10);
  if (!Number.isFinite(nextStep) || nextStep < 0 || nextStep >= TOUR_STEPS.length) {
    _clearTourSession();
    return;
  }
  _tourStep = nextStep;
  const tourOverlay = document.getElementById('tour-overlay');
  if (!tourOverlay) return;
  setShellVisibility(tourOverlay, true);
  showTourStep();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', restoreGuidedTourIfNeeded, { once: true });
} else {
  requestAnimationFrame(restoreGuidedTourIfNeeded);
}

/* ─── Inline Model Picker ─── */
let _modelPickerVisible = false;
function toggleModelPicker() {
  _modelPickerVisible = !_modelPickerVisible;
  const panel = document.getElementById('model-picker-panel');
  if (!panel) return;
  panel.style.display = _modelPickerVisible ? 'block' : 'none';
  if (_modelPickerVisible) loadModelPickerList();
}

async function loadModelPickerList() {
  const list = document.getElementById('model-picker-list');
  if (!list) return;
  try {
    const [rec, models] = await Promise.all([
      _workspaceFetchJson('/api/ai/recommended', {}, 'Could not load recommended models'),
      _workspaceFetchJson('/api/ai/models', {}, 'Could not load installed models')
    ]);
    const installed = new Set(models.map(m => m.name));
    list.innerHTML = rec.map((r, idx) => `
      <div class="model-picker-card">
        <div class="model-picker-main">
          <div class="model-picker-title">${r.name}</div>
          <div class="model-picker-copy">${r.desc} (${r.size})</div>
          <div id="model-info-${idx}" class="model-picker-meta"></div>
        </div>
        <div class="model-picker-actions">
          <button class="btn btn-sm btn-ghost model-picker-info-btn" type="button" data-shell-action="show-model-info" data-model-name="${escapeAttr(r.name)}" data-model-info-id="model-info-${idx}" title="Model details">Info</button>
          ${installed.has(r.name)
            ? '<span class="model-picker-status">Ready</span>'
            : `<button class="btn btn-sm btn-primary" type="button" data-shell-action="pull-model" data-model-name="${escapeAttr(r.name)}">Get</button>`}
        </div>
      </div>
    `).join('');
  } catch (e) {
    list.innerHTML = '<div class="model-picker-empty">Could not load recommended models right now.</div>';
  }
}

async function showModelInfo(modelName, infoEl) {
  if (!infoEl) return;
  infoEl.textContent = 'Loading…';
  const info = await safeFetch('/api/ai/model-info/' + encodeURIComponent(modelName), {}, null);
  if (info && !info.error) {
    infoEl.innerHTML = '<span class="model-picker-meta">' + escapeHtml(info.parameters || '?') + ' params &middot; ' + escapeHtml(info.quantization || '?') + ' &middot; ' + escapeHtml(info.ram_estimate || '?') + ' RAM</span>';
  } else {
    infoEl.textContent = '';
  }
}

async function ensureOllamaReady() {
  // Auto-install and auto-start Ollama if needed — returns true when ready
  try {
    const svcs = await _workspaceFetchJson('/api/services', {}, 'Could not load AI service status');
    const svc = svcs.find(s => s.id === 'ollama');
    // Already running? Great, we're done
    if (svc?.installed && svc?.running) return true;
    // Not installed? Auto-install
    if (!svc?.installed) {
      toast('Installing AI Chat service...', 'info');
      await installService('ollama');
      // Wait for install (poll up to 3 min)
      for (let i = 0; i < 90; i++) {
        await new Promise(r => setTimeout(r, 2000));
        const fresh = await _workspaceFetchJson('/api/services', {}, 'Could not load AI service status');
        if (fresh.find(s => s.id === 'ollama')?.installed) break;
      }
      const check = await _workspaceFetchJson('/api/services', {}, 'Could not load AI service status');
      if (!check.find(s => s.id === 'ollama')?.installed) {
        toast('AI Chat is still installing. Please wait and try again.', 'warning');
        return false;
      }
    }
    // Installed but not running? Auto-start
    toast('Starting AI Chat service...', 'info');
    await startService('ollama');
    // Wait for ready (up to 20 seconds)
    for (let i = 0; i < 10; i++) {
      await new Promise(r => setTimeout(r, 2000));
      const fresh = await _workspaceFetchJson('/api/services', {}, 'Could not load AI service status');
      if (fresh.find(s => s.id === 'ollama')?.running) return true;
    }
    toast('AI Chat is starting up. Try again in a moment.', 'warning');
    return false;
  } catch(e) {
    toast('Could not check AI Chat status', 'error');
    return false;
  }
}

async function pullModel(name) {
  if (!await ensureOllamaReady()) return;
  try {
    await _workspaceFetchOk('/api/ai/pull', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({model:name})
    }, `Failed to start download for ${name}`);
    toast(`Downloading ${name}...`, 'info');
    toggleModelPicker();
    pollPullProgress();
  } catch(e) { toast(e.message || 'Failed to connect to AI service', 'error'); }
}

function pullCustomModel() {
  const input = document.getElementById('custom-model-input');
  if (!input) return;
  const name = input.value.trim();
  if (!name) return;
  input.value = '';
  pullModel(name);
}

async function pullAllModels() {
  if (!await ensureOllamaReady()) return;
  // Get all recommended model names
  try {
    const rec = await _workspaceFetchJson('/api/ai/recommended', {}, 'Could not load recommended models');
    const models = rec.map(r => r.name);
    const totalSize = rec.reduce((s, r) => s + parseFloat(r.size), 0).toFixed(1);
    const d = await _workspaceFetchJson('/api/ai/pull-queue', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({models})
    }, 'Could not queue recommended models');
    if (d.error) { toast(d.error, 'warning'); return; }
    if (d.status === 'all_installed') { toast('All recommended models are already downloaded!', 'success'); return; }
    toast(`Queued ${d.count} models for download. They will download one at a time.`, 'info');
    toggleModelPicker();
    pollPullProgress();
  } catch(e) { toast('Failed to start model queue', 'error'); }
}

/* ─── Knowledge Base ─── */
let kbEnabled = false;

function toggleKB() {
  const toggle = document.getElementById('kb-toggle');
  const docsEl = document.getElementById('kb-docs-list');
  if (!toggle || !docsEl) return;
  kbEnabled = toggle.checked;
  docsEl.style.display = kbEnabled ? 'block' : 'none';
  if (kbEnabled) loadKBDocs();
}

async function loadKBDocs() {
  const el = document.getElementById('kb-docs-list');
  if (!el) return;
  let docs;
  try {
    docs = await _workspaceFetchJson('/api/kb/documents', {}, 'Could not load knowledge base documents');
  } catch(e) {
    el.innerHTML = '<span class="kb-doc-empty">Could not load documents. Document search may not be running.</span>';
    return;
  }
  if (!docs.length) { el.innerHTML = '<span class="kb-doc-empty">No documents uploaded yet.</span>'; return; }
  const catColors = {medical:'#e91e63',property:'#4caf50',vehicle:'#2196f3',financial:'#ff9800',legal:'#9c27b0',reference:'#00bcd4',personal:'#795548',other:'var(--text-muted)'};
  el.innerHTML = docs.map(d => {
    const statusClass = d.status === 'ready' ? 'kb-doc-status-success' : d.status === 'error' ? 'kb-doc-status-danger' : 'kb-doc-status-warning';
    const cat = d.doc_category || '';
    const catBadge = cat ? `<span class="kb-doc-category" style="--kb-doc-category-tone:${catColors[cat]||'var(--surface3)'};">${cat}</span>` : '';
    const summary = d.summary ? `<div class="kb-doc-summary" title="${escapeAttr(d.summary)}">${escapeHtml(d.summary.slice(0,100))}</div>` : '';
    const analyzeBtn = d.status === 'ready' && !d.doc_category ? `<button type="button" class="kb-doc-action" data-chat-action="analyze-kb-doc" data-doc-id="${d.id}" title="AI: classify, summarize, extract entities">Analyze</button>` : '';
    const detailBtn = d.doc_category ? `<button type="button" class="kb-doc-action" data-chat-action="show-doc-details" data-doc-id="${d.id}" title="View analysis details">Details</button>` : '';
    return `<div class="kb-doc-item kb-doc-item-stack">
      <div class="kb-doc-head">
        <span class="kb-doc-main">${escapeHtml(d.filename)} ${catBadge} <span class="kb-doc-status ${statusClass}">${d.status}${d.chunks_count ? ' ('+d.chunks_count+' chunks)' : ''}</span></span>
        <span class="kb-doc-actions">${analyzeBtn}${detailBtn}<button type="button" class="convo-action-btn convo-del" data-chat-action="delete-kb-doc" data-doc-id="${d.id}" title="Delete document" aria-label="Delete document">x</button></span>
      </div>
      ${summary}
    </div>`;
  }).join('');

  // Update badge
  const badge = document.getElementById('kb-status-badge');
  try {
    const status = await safeFetch('/api/kb/status', {}, null);
    if (!status) throw new Error('kb status unavailable');
    if (status.qdrant_running) {
      const ct = status.collection?.points_count || 0;
      badge.textContent = ct > 0 ? `${ct} searchable passages` : 'Ready for documents';
      badge.style.color = 'var(--green)';
    } else {
      badge.textContent = 'Document search not running';
      badge.style.color = 'var(--red)';
    }
  } catch(e) {
    badge.textContent = 'Document search unavailable';
    badge.style.color = 'var(--text-muted)';
  }
}

async function uploadKBFile() {
  const input = document.getElementById('kb-file-input');
  if (!input || !input.files.length) return;
  const file = input.files[0];
  const formData = new FormData();
  formData.append('file', file);
  try {
    toast(`Uploading ${file.name}...`);
    await _workspaceFetchOk('/api/kb/upload', {method: 'POST', body: formData}, `Could not upload ${file.name}`);
    input.value = '';
    toast('Processing document...');
    pollKBEmbed();
  } catch (e) {
    toast(e.message || 'Could not upload document', 'error');
  }
}

let _kbPoll = null;
function stopKBPoll() {
  if (_kbPoll) {
    clearInterval(_kbPoll);
    _kbPoll = null;
  }
  window.NomadShellRuntime?.stopInterval('ai-chat.kb-embed');
}
function pollKBEmbed() {
  if (_kbPoll) return;
  const runner = async () => {
    const s = await _workspaceFetchJsonSafe('/api/kb/status', {}, null, 'Could not load document embed status');
    if (!s) return;
    if (s.status === 'complete' || s.status === 'error' || s.status === 'idle') {
      stopKBPoll();
      if (s.status === 'complete') toast('Document embedded!', 'success');
      if (s.status === 'error') toast('Embedding failed: ' + s.detail, 'error');
      loadKBDocs();
    }
  };
  if (window.NomadShellRuntime) {
    _kbPoll = window.NomadShellRuntime.startInterval('ai-chat.kb-embed', runner, 2000, {
      tabId: 'ai-chat',
      requireVisible: true,
    });
    return;
  }
  _kbPoll = setInterval(runner, 2000);
}

async function deleteKBDoc(id) {
  if (!confirm('Delete this document?')) return;
  try {
    await _workspaceFetchOk(`/api/kb/documents/${id}`, {method:'DELETE'}, 'Delete failed');
    toast('Document deleted', 'warning');
    loadKBDocs();
  } catch(e) { toast(e.message || 'Failed to delete document', 'error'); }
}

async function analyzeDoc(id) {
  try {
    await _workspaceFetchOk(`/api/kb/documents/${id}/analyze`, {method:'POST'}, 'Could not start document analysis');
  } catch (e) {
    toast(e.message || 'Could not start document analysis', 'error');
    return;
  }
  toast('Analyzing document with AI...', 'info');
  // Poll for completion
  let polls = 0;
  let poll = null;
  const stopPoll = () => {
    if (poll) {
      clearInterval(poll);
      poll = null;
    }
    window.NomadShellRuntime?.stopInterval(`ai-chat.kb-analyze.${id}`);
  };
  const runner = async () => {
    polls++;
    const d = await _workspaceFetchJsonSafe(`/api/kb/documents/${id}/details`, {}, null, 'Could not load document analysis status');
    if (!d) return;
    if (d.doc_category || polls > 30) {
      stopPoll();
      toast(`Document analyzed: ${d.doc_category || 'complete'}`, 'success');
      loadKBDocs();
    }
  };
  if (window.NomadShellRuntime) {
    poll = window.NomadShellRuntime.startInterval(`ai-chat.kb-analyze.${id}`, runner, 2000, {
      tabId: 'ai-chat',
      requireVisible: true,
    });
    return;
  }
  poll = setInterval(runner, 2000);
}

async function showDocDetails(id) {
  try {
    const d = await _workspaceFetchJson(`/api/kb/documents/${id}/details`, {}, 'Could not load document details');
    const catColors = {medical:'#e91e63',property:'#4caf50',vehicle:'#2196f3',financial:'#ff9800',legal:'#9c27b0',reference:'#00bcd4',personal:'#795548',other:'var(--text-muted)'};
    const entities = d.entities || [];
    const linked = d.linked_records || [];
    let html = `<h3 class="kb-detail-title">${escapeHtml(d.filename)}</h3>`;
    html += `<div class="kb-detail-category-row"><span class="kb-doc-category kb-doc-category-strong" style="--kb-doc-category-tone:${catColors[d.doc_category]||'#666'};">${escapeHtml(d.doc_category||'unclassified')}</span></div>`;
    if (d.summary) html += `<div class="kb-detail-summary"><strong>Summary:</strong> ${escapeHtml(d.summary)}</div>`;
    if (entities.length) {
      html += `<div class="kb-detail-section"><strong class="kb-detail-label">Extracted Entities (${entities.length}):</strong><div class="kb-detail-entity-list">`;
      entities.forEach(e => {
        const typeColors = {person:'#e91e63',date:'#ff9800',medication:'#4caf50',address:'#2196f3',phone:'#9c27b0',vehicle:'#00bcd4',amount:'#ff5722',coordinate:'#795548'};
        const tone = typeColors[e.type] || '#8a7f73';
        html += `<span class="kb-detail-entity-chip" style="--kb-entity-tone:${tone};--kb-entity-tone-soft:${tone}22;">${escapeHtml(e.type)}: ${escapeHtml(e.value)}</span>`;
      });
      html += `</div>`;
      const importableTypes = ['person','medication','coordinates','phone'];
      const hasImportable = entities.some(e => importableTypes.includes(e.type));
      if (hasImportable) {
        html += `<button class="btn btn-sm kb-detail-import-btn" type="button" data-chat-action="import-doc-entities" data-doc-id="${id}"><i class="bi bi-database-add"></i> Import Entities to Database</button>`;
      }
      html += `</div>`;
    }
    if (linked.length) {
      html += `<div class="kb-detail-section"><strong class="kb-detail-label">Cross-References:</strong><div class="kb-detail-linked-list">`;
      linked.forEach(l => {
        html += `<div class="kb-detail-linked-item">Linked to ${l.type}: <strong>${escapeHtml(l.name)}</strong></div>`;
      });
      html += `</div></div>`;
    }
    html += `<div class="kb-detail-meta">File size: ${d.file_size ? Math.round(d.file_size/1024) + ' KB' : '?'} | Chunks: ${d.chunks_count || 0} | Status: ${escapeHtml(d.status || 'unknown')}</div>`;
    html += `<div class="modal-footer"><button class="btn btn-sm" type="button" data-shell-action="close-modal-overlay">Close</button></div>`;
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.onclick = e => { if (e.target === overlay) overlay.remove(); };
    const card = document.createElement('div');
    card.className = 'modal-card';
    card.innerHTML = html;
    overlay.appendChild(card);
    document.body.appendChild(overlay);
  } catch(e) { toast('Failed to load details', 'error'); }
}

async function importDocEntities(docId) {
  try {
    const d = await _workspaceFetchJson(`/api/kb/documents/${docId}/import-entities`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({})}, 'Import failed');
    const parts = [];
    if (d.results.contacts > 0) parts.push(`${d.results.contacts} contact(s)`);
    if (d.results.inventory > 0) parts.push(`${d.results.inventory} inventory item(s)`);
    if (d.results.waypoints > 0) parts.push(`${d.results.waypoints} waypoint(s)`);
    if (d.results.skipped > 0) parts.push(`${d.results.skipped} skipped`);
    toast(`Imported ${d.total_imported} entities: ${parts.join(', ') || 'none'}`, d.total_imported > 0 ? 'success' : 'info');
  } catch(e) { toast(e.message || 'Failed to import entities', 'error'); }
}

async function analyzeAllDocs() {
  try {
    const d = await apiPost('/api/kb/analyze-all');
    toast('Analyzing ' + d.count + ' document(s)...', 'info');
    setTimeout(loadKBDocs, 10000);
  } catch(e) { toast('Failed to start analysis', 'error'); }
}

/* ─── Map Tile Themes ─── */
const MAP_TILE_THEMES = {
  dark: {
    url: 'https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
    name: 'Dark (CartoDB)'
  },
  light: {
    url: 'https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
    name: 'Light (CartoDB)'
  },
  tactical: {
    url: 'https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
    name: 'Dark Tactical'
  },
  eink: {
    url: 'https://stamen-tiles.a.ssl.fastly.net/toner/{z}/{x}/{y}.png',
    name: 'High Contrast B&W (Stamen Toner)'
  },
  satellite: {
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    name: 'Satellite (ESRI)'
  },
  terrain: {
    url: 'https://stamen-tiles.a.ssl.fastly.net/terrain/{z}/{x}/{y}.png',
    name: 'Terrain (Stamen)'
  }
};

const THEME_TO_TILE = {
  nomad: 'light',
  nightops: 'dark',
  cyber: 'dark',
  redlight: 'dark',
  eink: 'eink'
};

const _offlineMapStyle = {
  version: 8,
  name: 'NOMAD Dark',
  sources: {},
  layers: [{id:'background', type:'background', paint:{'background-color':'#1a1a2e'}}],
  glyphs: 'https://fonts.openmaptiles.org/{fontstack}/{range}.pbf',
};

function applyRasterTileStyle(tileUrl, name) {
  if (!_map) return;
  const style = {
    version: 8,
    name: name,
    sources: {
      'raster-tiles': {
        type: 'raster',
        tiles: [tileUrl],
        tileSize: 256,
        attribution: ''
      }
    },
    layers: [{
      id: 'raster-layer',
      type: 'raster',
      source: 'raster-tiles',
      minzoom: 0,
      maxzoom: 19
    }],
    glyphs: 'https://fonts.openmaptiles.org/{fontstack}/{range}.pbf',
  };
  _map.setStyle(style);
}

function applyMapThemeTiles(themeName) {
  if (!_map) return;
  const tileKey = THEME_TO_TILE[themeName] || 'dark';
  const tileDef = MAP_TILE_THEMES[tileKey];
  if (tileDef) {
    applyRasterTileStyle(tileDef.url, tileDef.name);
  }
}

function setMapTileSource(value) {
  localStorage.setItem('nomad-map-tiles', value);
  if (!_map) return;
  if (value === 'auto') {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'nomad';
    applyMapThemeTiles(currentTheme);
    toast('Map tiles: Auto (matching app theme)', 'info');
  } else if (value === 'offline') {
    _map.setStyle(_offlineMapStyle);
    toast('Map tiles: Local / Offline', 'info');
  } else {
    const tileDef = MAP_TILE_THEMES[value];
    if (tileDef) {
      applyRasterTileStyle(tileDef.url, tileDef.name);
      toast(`Map tiles: ${tileDef.name}`, 'info');
    }
  }
}

/* ─── Map Viewer ─── */
let _map = null;
let _mapVisible = false;

function toggleMapView() {
  _mapVisible = !_mapVisible;
  const viewerEl = document.getElementById('map-viewer');
  const managementEl = document.getElementById('map-management');
  const toggleBtn = document.getElementById('map-toggle-btn');
  if (!viewerEl || !managementEl || !toggleBtn) return;
  viewerEl.style.display = _mapVisible ? 'block' : 'none';
  managementEl.style.display = _mapVisible ? 'none' : 'block';
  toggleBtn.textContent = _mapVisible ? 'Manage Maps' : 'Show Map';
  ['pin-btn','measure-btn','clear-pins-btn','save-wp-btn','draw-zone-btn','gpx-btn','property-btn','print-map-btn','bookmark-btn','bearing-btn','style-btn'].forEach(id => {
    const control = document.getElementById(id);
    if (control) control.style.display = _mapVisible ? '' : 'none';
  });
  if (_mapVisible && !_map) initMap();
  if (_mapVisible && _map) loadWaypoints();
}

let _mapMarkers = [];
let _measurePoints = [];
let _measureMode = false;
let _measureActive = false;
let _measureMarkers = [];
let _measureLine = null;

let _mapStyleIdx = 0;
const MAP_STYLES = [
  {name: 'Default', filter: null},
  {name: 'Dark', filter: 'invert(1) hue-rotate(180deg)'},
  {name: 'Satellite', filter: 'saturate(1.3) contrast(1.1)'},
];

function cycleMapStyle() {
  _mapStyleIdx = (_mapStyleIdx + 1) % MAP_STYLES.length;
  const canvas = document.querySelector('#map-container canvas');
  if (canvas) {
    canvas.style.filter = MAP_STYLES[_mapStyleIdx].filter || 'none';
  }
  toast(`Map style: ${MAP_STYLES[_mapStyleIdx].name}`, 'info');
}

function toggleMapMeasure() {
  _measureActive = !_measureActive;
  const btn = document.getElementById('map-measure-btn');
  if (btn) btn.className = _measureActive ? 'btn btn-sm btn-primary' : 'btn btn-sm';
  if (!_measureActive) clearMeasure();
  if (typeof _map !== 'undefined' && _map) {
    _map.getCanvas().style.cursor = _measureActive ? 'crosshair' : '';
  }
}

function clearMeasure() {
  _measurePoints = [];
  _measureMarkers.forEach(m => m.remove());
  _measureMarkers = [];
  if (_measureLine && typeof _map !== 'undefined' && _map.getSource('measure-line')) {
    _map.getSource('measure-line').setData({type:'FeatureCollection',features:[]});
  }
  const el = document.getElementById('measure-result');
  if (el) el.style.display = 'none';
}

function calcMeasureDistance() {
  if (_measurePoints.length < 2) return 0;
  let total = 0;
  for (let i = 1; i < _measurePoints.length; i++) {
    const [lon1, lat1] = _measurePoints[i-1];
    const [lon2, lat2] = _measurePoints[i];
    const R = 6371;
    const dLat = (lat2-lat1)*Math.PI/180;
    const dLon = (lon2-lon1)*Math.PI/180;
    const a = Math.sin(dLat/2)**2 + Math.cos(lat1*Math.PI/180)*Math.cos(lat2*Math.PI/180)*Math.sin(dLon/2)**2;
    total += R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  }
  return total;
}

function printMap() {
  const mapEl = document.querySelector('.map-wrap');
  if (!mapEl) return;
  const canvas = mapEl.querySelector('canvas');
  if (!canvas) { toast('Map not loaded', 'warning'); return; }
  const win = window.open('', '_blank');
  win.document.write('<html><head><title>NOMAD Map Print</title><style>body{margin:0;text-align:center;}img{max-width:100%;height:auto;}h3{font-family:system-ui;margin:8px;}.print-meta{font-size:11px;color:#666;}</style></head><body>');
        win.document.write('<h3>NOMAD Field Desk — Map Export</h3>');
  win.document.write('<img src="' + canvas.toDataURL('image/png') + '">');
  win.document.write('<p class="print-meta">Printed ' + new Date().toLocaleString() + '</p>');
  win.document.write('</body></html>');
  win.document.close();
  setTimeout(() => win.print(), 500);
}

async function importGpxFile(input) {
  const file = input.files?.[0];
  if (!file) return;
  const formData = new FormData();
  formData.append('file', file);
  try {
    const d = await apiFetch('/api/waypoints/import-gpx', {method: 'POST', body: formData});
    toast('Imported ' + (d.count || 0) + ' waypoints from GPX', 'success');
    loadWPDistances();
  } catch(e) { toast(e.data?.error || 'GPX import failed', 'error'); }
  input.value = '';
}

function initMap() {
  if (typeof maplibregl === 'undefined') {
    toast('MapLibre GL JS not loaded (requires internet on first use)');
    return;
  }

  if (typeof pmtiles !== 'undefined') {
    const protocol = new pmtiles.Protocol();
    maplibregl.addProtocol('pmtiles', protocol.tile);
  }

  // Offline-first dark basemap — no CDN dependency
  const offlineStyle = {
    version: 8,
    name: 'NOMAD Dark',
    sources: {},
    layers: [{id:'background', type:'background', paint:{'background-color':'#1a1a2e'}}],
    glyphs: 'https://fonts.openmaptiles.org/{fontstack}/{range}.pbf',
  };

  _map = new maplibregl.Map({
    container: 'map-container',
    style: offlineStyle,
    center: [-98.5, 39.8],
    zoom: 4,
    attributionControl: true,
  });

  // Restore saved tile preference or auto-match app theme
  const savedTiles = localStorage.getItem('nomad-map-tiles') || 'auto';
  const tileSelector = document.getElementById('map-tile-selector');
  if (tileSelector) tileSelector.value = savedTiles;
  if (savedTiles === 'offline') {
    // Keep the offline basemap style as-is
  } else {
    const tileKey = (savedTiles === 'auto')
      ? (THEME_TO_TILE[document.documentElement.getAttribute('data-theme') || 'nomad'] || 'dark')
      : savedTiles;
    const tileDef = MAP_TILE_THEMES[tileKey];
    if (tileDef) {
      // Connectivity check: probe tile z/0/0, then apply raster tiles or stay offline
      fetch(tileDef.url.replace('{z}','0').replace('{x}','0').replace('{y}','0'), {signal: AbortSignal.timeout(3000)})
        .then(() => { if (_map) applyRasterTileStyle(tileDef.url, tileDef.name); })
        .catch(() => {}); // offline — keep the dark background
    }
  }

  _map.addControl(new maplibregl.NavigationControl(), 'top-right');
  _map.addControl(new maplibregl.FullscreenControl(), 'top-right');
  _map.addControl(new maplibregl.ScaleControl({maxWidth: 200}), 'bottom-left');
  _map.addControl(new maplibregl.GeolocateControl({
    positionOptions: {enableHighAccuracy: true},
    trackUserLocation: true,
  }));

  // Coordinate display on mouse move
  const coordEl = document.getElementById('map-coords');
  _map.on('mousemove', (e) => {
    if (coordEl) coordEl.textContent = `${e.lngLat.lat.toFixed(5)}, ${e.lngLat.lng.toFixed(5)}`;
  });

  // Load saved waypoints and zones after map loads
  _map.on('load', () => { loadWaypoints(); renderMapZones(); loadMeshMapOverlay(); loadGardenOverlay(); loadSupplyChainOverlay(); });

  // Click to drop pin, draw zone, property boundary, or bearing
  _map.on('click', (e) => {
    if (_measureMode) { addMeasurePoint(e.lngLat); return; }
    if (_drawingGarden) { _gardenPoints.push([e.lngLat.lng, e.lngLat.lat]); new maplibregl.Marker({color:'#4caf50',scale:0.4}).setLngLat(e.lngLat).addTo(_map); return; }
    if (_drawingZone) { _zonePoints.push([e.lngLat.lng, e.lngLat.lat]); new maplibregl.Marker({color:'#ff9800',scale:0.4}).setLngLat(e.lngLat).addTo(_map); return; }
    if (_drawingProperty) { _propertyPoints.push([e.lngLat.lng, e.lngLat.lat]); new maplibregl.Marker({color:'#5b9fff',scale:0.4}).setLngLat(e.lngLat).addTo(_map); return; }
    if (handleBearingClick(e.lngLat)) return;
  });

  _map.on('dblclick', (e) => {
    if (_drawingGarden && _gardenPoints.length >= 3) { e.preventDefault(); finishGardenDraw(); }
  });
}

function dropPin() {
  if (!_map) return;
  const center = _map.getCenter();
  const note = '';
  const marker = new maplibregl.Marker({color: '#5b9fff'})
    .setLngLat(center)
    .setPopup(new maplibregl.Popup().setHTML(
      renderMapPopupShell({
        title: note ? escapeHtml(note) : 'Dropped pin',
        meta: 'Manual marker',
        coords: `${center.lat.toFixed(4)}, ${center.lng.toFixed(4)}`
      })
    ))
    .addTo(_map);
  marker.togglePopup();
  _mapMarkers.push(marker);
  toast('Pin dropped');
}

function clearPins() {
  _mapMarkers.forEach(m => m.remove());
  _mapMarkers = [];
  toast('Pins cleared');
}

function toggleMeasure() {
  _measureMode = !_measureMode;
  const measureBtn = document.getElementById('measure-btn');
  if (!measureBtn) return;
  measureBtn.textContent = _measureMode ? 'Stop Measuring' : 'Measure';
  if (!_measureMode) {
    _measurePoints = [];
    if (_map.getSource('measure-line')) { _map.removeLayer('measure-line'); _map.removeSource('measure-line'); }
  }
  toast(_measureMode ? 'Click points on map to measure distance' : 'Measurement mode off');
}

function addMeasurePoint(lngLat) {
  _measurePoints.push([lngLat.lng, lngLat.lat]);
  new maplibregl.Marker({color: '#ff9800', scale: 0.5}).setLngLat(lngLat).addTo(_map);

  if (_measurePoints.length >= 2) {
    // Calculate total distance
    let totalKm = 0;
    for (let i = 1; i < _measurePoints.length; i++) {
      totalKm += haversineKm(_measurePoints[i-1], _measurePoints[i]);
    }
    const miles = totalKm * 0.621371;
    toast(`Distance: ${totalKm.toFixed(2)} km (${miles.toFixed(2)} mi)`);

    // Draw line
    const geojson = {type:'Feature', geometry:{type:'LineString', coordinates: _measurePoints}};
    if (_map.getSource('measure-line')) {
      _map.getSource('measure-line').setData(geojson);
    } else {
      _map.addSource('measure-line', {type:'geojson', data: geojson});
      _map.addLayer({id:'measure-line', type:'line', source:'measure-line', paint:{'line-color':'#ff9800','line-width':2,'line-dasharray':[2,2]}});
    }
  }
}

function haversineKm(a, b) {
  const R = 6371;
  const dLat = (b[1]-a[1])*Math.PI/180;
  const dLon = (b[0]-a[0])*Math.PI/180;
  const lat1 = a[1]*Math.PI/180, lat2 = b[1]*Math.PI/180;
  const x = Math.sin(dLat/2)**2 + Math.cos(lat1)*Math.cos(lat2)*Math.sin(dLon/2)**2;
  return R*2*Math.atan2(Math.sqrt(x), Math.sqrt(1-x));
}

async function searchMap() {
  const searchInput = document.getElementById('map-search-input');
  if (!searchInput) return;
  const q = searchInput.value.trim();
  if (!q || !_map) return;
  // Check if input is coordinates (lat,lng or lat lng)
  const coordMatch = q.match(/^(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)$/);
  if (coordMatch) {
    const lat = parseFloat(coordMatch[1]);
    const lng = parseFloat(coordMatch[2]);
    if (lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180) {
      _map.flyTo({center: [lng, lat], zoom: 14});
      new maplibregl.Marker({color: 'var(--accent)'}).setLngLat([lng, lat])
        .setPopup(new maplibregl.Popup().setHTML(
          renderMapPopupShell({
            title: 'Coordinate jump',
            meta: 'Offline navigation',
            coords: `${lat.toFixed(5)}, ${lng.toFixed(5)}`
          })
        ))
        .addTo(_map).togglePopup();
      toast(`Navigated to ${lat.toFixed(5)}, ${lng.toFixed(5)}`, 'success');
      return;
    }
  }
  // Online geocoding search
  try {
    const r = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(q)}&limit=1`, {
      signal: AbortSignal.timeout(8000),
    });
    if (!r.ok) { toast('Geocoding failed', 'error'); return; }
    const results = await r.json();
    if (Array.isArray(results) && results.length) {
      const {lat, lon, display_name} = results[0];
      _map.flyTo({center: [parseFloat(lon), parseFloat(lat)], zoom: 12});
      new maplibregl.Marker().setLngLat([parseFloat(lon), parseFloat(lat)])
        .setPopup(new maplibregl.Popup().setHTML(
          renderMapPopupShell({
            title: escapeHtml(display_name),
            meta: 'Search result',
            coords: `${parseFloat(lat).toFixed(5)}, ${parseFloat(lon).toFixed(5)}`
          })
        ))
        .addTo(_map).togglePopup();
    } else if (Array.isArray(results)) { toast('Location not found', 'warning'); }
    else { toast('Geocoding returned an invalid response', 'error'); }
  } catch(e) { toast('Location search requires internet. Enter coordinates (lat,lng) for offline navigation.', 'warning'); }
}

function exportConversation() {
  if (!currentConvoId) { toast('No conversation selected', 'warning'); return; }
  window.location=`/api/conversations/${currentConvoId}/export`;
}

/* ─── Conversation Search ─── */
function filterConvos() {
  const searchInput = document.getElementById('convo-search');
  if (!searchInput) return;
  const q = searchInput.value.toLowerCase();
  if (!q) { renderConvoList(); return; }
  const filtered = allConvos.filter(c => c.title.toLowerCase().includes(q));
  const el = document.getElementById('convo-list');
  if (!el) return;
  if (!filtered.length) { el.innerHTML = '<div class="sidebar-empty-state convo-search-empty">No matches</div>'; return; }
  el.innerHTML = filtered.map(c => {
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

/* ─── Unified Search ─── */
let _searchTimer;
let _commandPaletteTimer;
let _commandPaletteItems = [];
let _commandPaletteActiveIndex = -1;
let _commandPaletteReturnFocus = null;

const UNIFIED_SEARCH_TYPE_ICONS = {
  inventory: '&#128230;',
  contact: '&#128100;',
  note: '&#128196;',
  conversation: '&#128172;',
  document: '&#128206;',
  checklist: '&#9745;',
  skill: '&#127919;',
  ammo: '&#128299;',
  equipment: '&#128295;',
  waypoint: '&#128205;',
  frequency: '&#128225;',
  patient: '&#9829;',
  incident: '&#9888;',
  fuel: '&#9981;',
};

const UNIFIED_SEARCH_TYPE_LABELS = {
  inventory: 'Supply',
  contact: 'Contact',
  note: 'Note',
  conversation: 'Chat',
  document: 'Document',
  checklist: 'Checklist',
  skill: 'Skill',
  ammo: 'Ammo',
  equipment: 'Equipment',
  waypoint: 'Waypoint',
  frequency: 'Frequency',
  patient: 'Patient',
  incident: 'Incident',
  fuel: 'Fuel',
};

function openWorkspaceTab(tabId) {
  if (typeof openWorkspaceRouteAware === 'function') {
    openWorkspaceRouteAware(tabId);
    return;
  }
  document.querySelector(`.tab[data-tab="${tabId}"]`)?.click();
}

async function importConfig() {
  const input = document.getElementById('import-file');
  if (!input) return;
  if (!input.files.length) return;
  const formData = new FormData();
  formData.append('file', input.files[0]);
  try {
    const r = await _workspaceFetchJson('/api/import-config', {method:'POST', body:formData}, 'Could not import configuration');
    input.value = '';
    toast(r.message || r.error || 'Import complete');
  } catch (e) {
    input.value = '';
    toast(e.message || 'Could not import configuration', 'error');
  }
}

/* ─── In-App Frame ─── */
function openAppFrame(title, url) {
  const titleEl = document.getElementById('app-frame-title');
  const iframe = document.getElementById('app-frame-iframe');
  const overlay = document.getElementById('app-frame-overlay');
  if (!titleEl || !iframe || !overlay) return;
  titleEl.textContent = title;
  iframe.src = url;
  overlay.style.display = 'flex';
}

function openAppFrameHTML(title, html, scrollTo) {
  const iframe = document.getElementById('app-frame-iframe');
  const titleEl = document.getElementById('app-frame-title');
  const overlay = document.getElementById('app-frame-overlay');
  if (!iframe || !titleEl || !overlay) return;
  titleEl.textContent = title;
  overlay.style.display = 'flex';
  iframe.src = 'about:blank';
  setTimeout(() => {
    iframe.contentDocument.open();
    iframe.contentDocument.write(html);
    iframe.contentDocument.close();
    if (scrollTo) {
      setTimeout(() => {
        const el = iframe.contentDocument.getElementById(scrollTo);
        if (el) el.scrollIntoView({behavior:'smooth',block:'start'});
      }, 100);
    }
  }, 50);
}

function closeAppFrame() {
  const overlay = document.getElementById('app-frame-overlay');
  const iframe = document.getElementById('app-frame-iframe');
  if (!overlay || !iframe) return;
  overlay.style.display = 'none';
  iframe.src = 'about:blank';
}
document.addEventListener('keydown', e => {
  const overlay = document.getElementById('app-frame-overlay');
  if (e.key === 'Escape' && overlay?.style.display === 'flex') {
    closeAppFrame();
  }
  const needsDetailModal = document.getElementById('needs-detail-modal');
  if (e.key === 'Escape' && needsDetailModal?.style.display === 'flex') {
    closeNeedsDetail();
  }
  const tcccModal = document.getElementById('tccc-modal');
  if (e.key === 'Escape' && tcccModal && tcccModal.style.display === 'flex') {
    tcccModal.style.display = 'none';
  }
});

/* ─── Global Keyboard Shortcuts ─── */
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && !document.getElementById('command-palette-overlay')?.hidden) {
    e.preventDefault();
    toggleCommandPalette(false);
    return;
  }
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    toggleCommandPalette(true);
    return;
  }
  // Skip if user is typing in an input/textarea for the remaining shortcuts
  const tag = document.activeElement?.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
  // Ctrl+/ — Focus copilot dock (available on all tabs)
  if ((e.ctrlKey || e.metaKey) && e.key === '/') {
    e.preventDefault();
    const copilot = document.getElementById('copilot-input');
    if (copilot) { copilot.focus(); copilot.select(); }
  }
  // Alt+1-9 handled in second keydown listener below
});

function printAppFrame() {
  try {
    document.getElementById('app-frame-iframe').contentWindow.print();
  } catch(e) {
    toast('Cannot print this content — try opening it in a new browser tab instead', 'warning');
  }
}

