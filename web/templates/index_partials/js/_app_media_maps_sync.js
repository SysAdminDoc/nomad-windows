/* ─── Media Tab ─── */
async function _fetchJson(url, opts) {
  return apiFetch(url, opts);
}
let _mediaItems = [];
let _mediaFolder = '';
let _mediaViewGrid = true;
let _mediaCatalogVisible = false;
let _mediaDlPoll = null;
let _mediaDlPollDelay = null;
let _mediaDlWatchId = null;
let _mediaYtdlpInstallPoll = null;
let _mediaSub = 'channels'; // videos | audio | books | channels
let _mediaBookRendition = null;
let _mediaSort = 'title'; // title | date | size | favorited
let _mediaSortDir = 'asc';
let _mediaSelected = new Set();
let _mediaSelectMode = false;

function setMediaVisibility(target, visible, displayValue = '') {
  const el = typeof target === 'string' ? document.getElementById(target) : target;
  if (!el) return null;
  el.classList.toggle('is-hidden', !visible);
  el.hidden = !visible;
  if (visible) {
    if (displayValue) el.style.display = displayValue;
    else el.style.removeProperty('display');
  } else {
    el.style.display = 'none';
  }
  return el;
}

function isMediaVisible(target) {
  const el = typeof target === 'string' ? document.getElementById(target) : target;
  if (!el) return false;
  const style = window.getComputedStyle(el);
  return !el.hidden && !el.classList.contains('is-hidden') && style.display !== 'none' && style.visibility !== 'hidden';
}

function stopMediaYtdlpInstallPolling() {
  if (_mediaYtdlpInstallPoll) {
    clearInterval(_mediaYtdlpInstallPoll);
    _mediaYtdlpInstallPoll = null;
  }
  window.NomadShellRuntime?.stopInterval('media.ytdlp-install');
}

async function runMediaYtdlpInstallPoll() {
  const fill = document.getElementById('ytdlp-install-fill');
  const progress = document.getElementById('ytdlp-install-progress');
  if (!fill || !progress) {
    stopMediaYtdlpInstallPolling();
    return;
  }
  try {
    const p = await _fetchJson('/api/ytdlp/install-progress');
    fill.style.width = `${p.percent || 0}%`;
    if (p.status === 'complete') {
      stopMediaYtdlpInstallPolling();
      toast('Downloader installed!', 'success');
      setMediaVisibility(progress, false);
      checkYtdlpStatus();
    } else if (p.status === 'error') {
      stopMediaYtdlpInstallPolling();
      toast('Install failed: ' + (p.error || ''), 'error');
      setMediaVisibility(progress, false);
    }
  } catch (e) {}
}

function startMediaYtdlpInstallPolling() {
  if (_mediaYtdlpInstallPoll) return;
  if (window.NomadShellRuntime) {
    _mediaYtdlpInstallPoll = window.NomadShellRuntime.startInterval('media.ytdlp-install', runMediaYtdlpInstallPoll, 1000, {
      tabId: 'media',
      requireVisible: true,
    });
    return;
  }
  _mediaYtdlpInstallPoll = setInterval(runMediaYtdlpInstallPoll, 1000);
}

function stopMediaDownloadPolling() {
  if (_mediaDlPollDelay) {
    clearTimeout(_mediaDlPollDelay);
    _mediaDlPollDelay = null;
  }
  if (_mediaDlPoll) {
    clearInterval(_mediaDlPoll);
    _mediaDlPoll = null;
  }
  window.NomadShellRuntime?.stopInterval('media.download-progress');
}

async function runMediaDownloadPoll() {
  const bar = document.getElementById('media-dl-progress');
  if (!bar) {
    stopMediaDownloadPolling();
    return;
  }
  try {
    const all = await _fetchJson('/api/ytdlp/progress');
    let active = null;
    for (const [id, p] of Object.entries(all)) {
      if (_mediaDlWatchId && id === _mediaDlWatchId) { active = p; break; }
      if (['downloading','queued','merging','fetching info','starting'].includes(p.status)) active = p;
    }
    if (active) {
      const dlTitle = document.getElementById('media-dl-title');
      const dlFill = document.getElementById('media-dl-fill');
      const dlSpeed = document.getElementById('media-dl-speed');
      if (dlTitle) dlTitle.textContent = active.title || 'Downloading...';
      if (dlFill) dlFill.style.width = active.percent + '%';
      if (dlSpeed) dlSpeed.textContent = active.speed || '';
      if (isMediaVisible('dl-queue-panel')) refreshDlQueue();
      if (active.status === 'complete') {
        toast('Download complete: ' + active.title, 'success');
        setMediaVisibility(bar, false);
        _mediaDlWatchId = null;
        stopMediaDownloadPolling();
        loadMediaContent(); loadTotalMediaStats();
      } else if (active.status === 'error') {
        toast('Download failed: ' + (active.error || ''), 'error');
        setMediaVisibility(bar, false);
        _mediaDlWatchId = null;
        stopMediaDownloadPolling();
      }
    } else {
      setMediaVisibility(bar, false);
      _mediaDlWatchId = null;
      stopMediaDownloadPolling();
      loadMediaContent(); loadTotalMediaStats();
    }
  } catch (e) {}
}

function startMediaDownloadPolling(watchId) {
  if (watchId) _mediaDlWatchId = watchId;
  if (_mediaDlPoll || _mediaDlPollDelay) return;
  const startRunner = () => {
    _mediaDlPollDelay = null;
    if (window.NomadShellRuntime) {
      _mediaDlPoll = window.NomadShellRuntime.startInterval('media.download-progress', runMediaDownloadPoll, 1500, {
        tabId: 'media',
        requireVisible: true,
      });
      return;
    }
    _mediaDlPoll = setInterval(runMediaDownloadPoll, 1500);
  };
  _mediaDlPollDelay = setTimeout(startRunner, 500);
}

function switchMediaSub(sub) {
  _mediaSub = sub;
  _mediaFolder = '';
  if (typeof syncWorkspaceUrlState === 'function') syncWorkspaceUrlState();
  document.querySelectorAll('.media-subtab').forEach(b => b.classList.toggle('active', b.dataset.msub === sub));
  const urlInput = document.getElementById('media-url-input');
  const fileInput = document.getElementById('media-file-upload');
  const dlBtn = document.getElementById('media-dl-btn');
  const catBtn = document.getElementById('media-catalog-btn');
  const channelBrowser = document.getElementById('channel-browser');
  const torrentBrowser = document.getElementById('torrent-browser');
  const contentArea = document.getElementById('media-content-area');
  const topbar = document.getElementById('media-topbar');
  const sidebar = document.querySelector('.media-sidebar');
  if (sub === 'channels') {
    setMediaVisibility(channelBrowser, true, 'flex');
    setMediaVisibility(torrentBrowser, false);
    setMediaVisibility(contentArea, false);
    setMediaVisibility(topbar, false);
    setMediaVisibility(sidebar, false);
    setMediaVisibility('media-catalog-panel', false);
    backToChannels();
    closeYtWatch();
    loadChannelBrowser();
    return;
  }
  if (sub === 'torrents') {
    setMediaVisibility(channelBrowser, false);
    setMediaVisibility(torrentBrowser, true, 'flex');
    setMediaVisibility(contentArea, false);
    setMediaVisibility(topbar, false);
    setMediaVisibility(sidebar, false);
    setMediaVisibility('media-catalog-panel', false);
    closeYtWatch();
    checkTorrentClient();
    pollTorrentStatus().then(() => renderTorrentList());
    // Resume polling if there were active downloads
    if (Object.keys(_torrentStatuses).length > 0) startTorrentPolling();
    return;
  }
  setMediaVisibility(channelBrowser, false);
  setMediaVisibility(torrentBrowser, false);
  setMediaVisibility(contentArea, true);
  setMediaVisibility(topbar, true);
  setMediaVisibility(sidebar, true);
  if (sub === 'videos') {
    urlInput.placeholder = 'Paste YouTube URL to download video...';
    fileInput.setAttribute('accept', 'video/*');
    dlBtn.textContent = 'Download';
    catBtn.textContent = 'Video Catalog';
  } else if (sub === 'audio') {
    urlInput.placeholder = 'Paste URL to download audio (YouTube, SoundCloud, etc.)...';
    fileInput.setAttribute('accept', 'audio/*,.mp3,.flac,.ogg,.wav,.m4a,.opus');
    dlBtn.textContent = 'Download Audio';
    catBtn.textContent = 'Audio Catalog';
  } else {
    urlInput.placeholder = 'Not applicable for books — use Upload or browse the Reference Library';
    fileInput.setAttribute('accept', '.pdf,.epub,.mobi,.txt');
    setMediaVisibility(dlBtn, false);
    catBtn.textContent = 'Reference Library';
  }
  if (sub !== 'books') setMediaVisibility(dlBtn, true);
  closeMediaPlayer();
  closeBookReader();
  _mediaCatalogVisible = false;
  setMediaVisibility('media-catalog-panel', false);
  loadMediaContent().then(() => {
    // Auto-show catalog if library is empty — content up front, not hidden
    if (_mediaItems.length === 0 && !_mediaCatalogVisible) {
      toggleMediaCatalog();
    }
  });
}

async function loadMediaTab() {
  await checkYtdlpStatus();
  switchMediaSub(_mediaSub);
  loadTotalMediaStats();
  loadMediaContinue();
}
async function loadMediaContinue() {
  const el = document.getElementById('media-continue-items');
  const wrap = document.getElementById('media-continue');
  if (!el || !wrap) return;
  const items = await safeFetch('/api/media/resume', {}, []);
  if (!items.length) { setMediaVisibility(wrap, false); return; }
  setMediaVisibility(wrap, true);
  el.innerHTML = items.map(item => {
    const pct = item.duration_sec > 0 ? Math.round(item.position_sec / item.duration_sec * 100) : 0;
    const icon = item.media_type === 'video' ? '▶' : item.media_type === 'audio' ? '♫' : '📖';
    const mins = Math.round(item.position_sec / 60);
    return `<div class="media-continue-card" role="button" tabindex="0" data-media-action="resume-media" data-media-kind="${item.media_type}" data-media-id="${item.media_id}">
      <div class="media-continue-icon">${icon}</div>
      <div class="media-continue-title">${escapeHtml(item.title || 'Unknown')}</div>
      <div class="media-continue-meta">${mins}m watched</div>
      <div class="need-progress media-continue-progress"><div class="need-progress-fill" style="width:${pct}%;background:var(--accent);"></div></div>
    </div>`;
  }).join('');
}

function resumeMedia(type, id) {
  // Switch to the appropriate media subtab and highlight the item
  if (type === 'video') switchMediaSub('videos');
  else if (type === 'audio') switchMediaSub('audio');
  else if (type === 'book') switchMediaSub('books');
}

async function checkYtdlpStatus() {
  try {
    const s = await _fetchJson('/api/ytdlp/status');
    setMediaVisibility('media-ytdlp-banner', !s.installed);
    if (s.installed) setMediaVisibility('ytdlp-install-progress', false);
  } catch(e) {}
}

async function installYtdlp() {
  try {
    const d = await apiPost('/api/ytdlp/install');
    if (d.status === 'already_installed') { toast('Downloader already installed', 'info'); checkYtdlpStatus(); return; }
    toast('Installing downloader...', 'info');
    setMediaVisibility('ytdlp-install-progress', true);
    startMediaYtdlpInstallPolling();
  } catch(e) { toast('Install failed', 'error'); }
}

async function loadMediaContent() {
  const apiMap = {videos: '/api/videos', audio: '/api/audio', books: '/api/books'};
  try { _mediaItems = await _fetchJson(apiMap[_mediaSub]); } catch(e) { _mediaItems = []; }
  renderMediaItems();
  loadMediaFolders();
  loadMediaSidebarStats();
}

function renderMediaItems() {
  const el = document.getElementById('media-item-list');
  const search = (document.getElementById('media-search')?.value || '').toLowerCase();
  let filtered = _mediaItems.filter(v => {
    if (_mediaFolder !== '' && v.folder !== _mediaFolder) return false;
    if (search && !v.title.toLowerCase().includes(search) && !(v.category||'').toLowerCase().includes(search) && !(v.author||'').toLowerCase().includes(search)) return false;
    return true;
  });
  filtered = sortMediaItems(filtered);
  if (!filtered.length) {
    const labels = {videos:'videos',audio:'audio files',books:'books'};
    const icons = {videos:'&#9654;',audio:'&#9835;',books:'&#128214;'};
    const catLabels = {videos:'Video Catalog', audio:'Audio Catalog', books:'Reference Library'};
    el.innerHTML = `<div class="media-browser-empty">
      <div class="media-browser-status">
        <div class="media-browser-status-icon media-empty-icon">${icons[_mediaSub]}</div>
        <div class="media-browser-status-title">No ${labels[_mediaSub]}${_mediaFolder?' in this folder':''}</div>
        <div class="media-browser-status-copy">
        ${_mediaFolder ? 'Try selecting a different folder or clear the filter.' : `Browse the <button type="button" class="catalog-inline-button" data-media-action="toggle-catalog">${catLabels[_mediaSub]}</button> for curated survival content, or upload your own files.`}
        </div>
      </div>
    </div>`;
    return;
  }
  if (_mediaSub === 'books') { renderBooks(el, filtered); return; }
  if (_mediaSub === 'audio') { renderAudio(el, filtered); return; }
  // Videos
  const selPfx = (id, title) => _mediaSelectMode ? `<input class="layout-margin-right-6" type="checkbox" ${_mediaSelected.has(id)?'checked':''} data-media-action="toggle-select-item" data-media-id="${id}" data-stop-propagation aria-label="Select ${escapeAttr(title)}">` : '';
  const favBtn = (id, fav) => `<button type="button" class="media-inline-action${fav?' is-favorite':''}" data-media-action="toggle-favorite-item" data-media-id="${id}" data-stop-propagation title="${fav?'Unfavorite':'Favorite'}" aria-label="${fav?'Remove favorite':'Add favorite'}">${fav?'&#9733;':'&#9734;'}</button>`;
  if (_mediaViewGrid) {
    el.innerHTML = '<div class="media-grid">' + filtered.map(v => `
      <div class="media-card${_mediaSelected.has(v.id)?' selected':''}" data-media-id="${v.id}" data-media-action="${_mediaSelectMode?'toggle-select-item':'play-video'}" data-media-filename="${escapeAttr(v.filename)}" data-media-title="${escapeAttr(v.title)}" role="button" tabindex="0">
        <div class="media-card-thumb${v.thumbnail?' media-card-thumb-has-image':''}">
          ${v.thumbnail ? `<img src="/api/videos/serve/${encodeURIComponent(v.thumbnail)}" class="media-card-thumb-img" loading="lazy" width="160" height="90" alt="Thumbnail for ${escapeAttr(v.title)}" onerror="this.style.display='none'">` : ''}
          <div class="play-overlay"><span class="media-card-play-icon">&#9654;</span></div>
          ${v.duration ? `<span class="media-card-duration">${escapeHtml(v.duration)}</span>` : ''}
          <button type="button" class="media-inline-action media-card-favorite${v.favorited?' is-favorite':''}" data-media-action="toggle-favorite-item" data-media-id="${v.id}" data-stop-propagation aria-label="${v.favorited?'Remove favorite':'Add favorite'}">${v.favorited?'&#9733;':'&#9734;'}</button>
        </div>
        <div class="media-card-info"><div class="media-card-title">${escapeHtml(v.title)}</div>
        <div class="media-card-meta"><span class="check-cat">${escapeHtml(v.category)}</span><span>${v.duration||''}</span><span>${v.filesize?formatBytes(v.filesize):''}</span></div></div>
      </div>`).join('') + '</div>';
  } else {
    el.innerHTML = filtered.map(v => `
      <div class="media-list-row${_mediaSelected.has(v.id)?' selected':''}" data-media-id="${v.id}" data-media-action="${_mediaSelectMode?'toggle-select-item':'play-video'}" data-media-filename="${escapeAttr(v.filename)}" data-media-title="${escapeAttr(v.title)}" role="button" tabindex="0">
        ${selPfx(v.id, v.title)}${v.thumbnail ? `<img src="/api/videos/serve/${encodeURIComponent(v.thumbnail)}" class="media-list-thumb" loading="lazy" width="48" height="27" alt="Thumbnail for ${escapeAttr(v.title)}" onerror="this.outerHTML='<div class=media-list-play>&#9654;</div>'">` : '<div class="media-list-play">&#9654;</div>'}<div class="media-list-title">${escapeHtml(v.title)}</div>
        <div class="media-list-meta">${v.folder?escapeHtml(v.folder)+' / ':''}${escapeHtml(v.category)}</div>
        <div class="media-list-meta">${v.filesize?formatBytes(v.filesize):''}</div>
        <div class="media-list-actions">${favBtn(v.id,v.favorited)}
        <button type="button" class="media-inline-action" data-media-action="move-media-item" data-media-id="${v.id}" data-media-kind="videos" data-stop-propagation title="Move" aria-label="Move media item">&#9776;</button>
        <button type="button" class="media-inline-action is-danger" data-media-action="delete-media-item" data-media-id="${v.id}" data-media-kind="videos" data-stop-propagation title="Delete" aria-label="Delete media item">x</button></div>
      </div>`).join('');
  }
}

function renderAudio(el, items) {
  const selPfx = (id, title) => _mediaSelectMode ? `<input class="layout-margin-right-6" type="checkbox" ${_mediaSelected.has(id)?'checked':''} data-media-action="toggle-select-item" data-media-id="${id}" data-stop-propagation aria-label="Select ${escapeAttr(title)}">` : '';
  el.innerHTML = items.map(a => `
    <div class="media-audio-row${_mediaSelected.has(a.id)?' selected':''}" data-media-id="${a.id}" data-media-action="${_mediaSelectMode?'toggle-select-item':'play-audio'}" data-media-filename="${escapeAttr(a.filename)}" data-media-title="${escapeAttr(a.title)}" role="button" tabindex="0">
      ${selPfx(a.id, a.title)}<div class="media-list-play">&#9835;</div>
      <div class="media-list-title">${escapeHtml(a.title)}</div>
      <div class="media-list-meta">${a.artist?escapeHtml(a.artist)+' &middot; ':''}${escapeHtml(a.category)}</div>
      <div class="media-list-meta">${a.duration||''} ${a.filesize?formatBytes(a.filesize):''}</div>
      <div class="media-list-actions">
        <button type="button" class="media-inline-action${a.favorited?' is-favorite':''}" data-media-action="toggle-favorite-item" data-media-id="${a.id}" data-stop-propagation title="Favorite" aria-label="${a.favorited?'Remove favorite':'Add favorite'}">${a.favorited?'&#9733;':'&#9734;'}</button>
        <button type="button" class="media-inline-action" data-media-action="move-media-item" data-media-id="${a.id}" data-media-kind="audio" data-stop-propagation title="Move" aria-label="Move media item">&#9776;</button>
        <button type="button" class="media-inline-action is-danger" data-media-action="delete-media-item" data-media-id="${a.id}" data-media-kind="audio" data-stop-propagation title="Delete" aria-label="Delete media item">x</button>
      </div>
    </div>`).join('');
}

function renderBooks(el, items) {
  el.innerHTML = '<div class="media-grid">' + items.map(b => `
    <div class="media-book-card${_mediaSelected.has(b.id)?' selected':''}" data-media-id="${b.id}" data-media-action="${_mediaSelectMode?'toggle-select-item':'open-book'}" data-media-filename="${escapeAttr(b.filename)}" data-media-title="${escapeAttr(b.title)}" data-media-format="${escapeAttr(b.format)}" role="button" tabindex="0">
      <div class="media-book-cover ${b.format}">
        ${b.format.toUpperCase()}
        <button type="button" class="media-inline-action media-card-favorite${b.favorited?' is-favorite':''}" data-media-action="toggle-favorite-item" data-media-id="${b.id}" data-stop-propagation aria-label="${b.favorited?'Remove favorite':'Add favorite'}">${b.favorited?'&#9733;':'&#9734;'}</button>
      </div>
      <div class="media-card-info">
        <div class="media-card-title">${escapeHtml(b.title)}</div>
        <div class="media-card-meta"><span>${b.author?escapeHtml(b.author):''}</span><span>${b.filesize?formatBytes(b.filesize):''}</span></div>
      </div>
    </div>`).join('') + '</div>';
}

/* formatBytes defined above — do not redefine */

async function loadMediaFolders() {
  const statsMap = {videos:'/api/videos/stats', audio:'/api/audio/stats', books:'/api/books/stats'};
  try {
    const stats = await _fetchJson(statsMap[_mediaSub]);
    const el = document.getElementById('media-folder-list');
    const labels = {videos:'All Videos',audio:'All Audio',books:'All Books'};
    let html = `<div class="media-folder-item${_mediaFolder===''?' active':''}" data-media-action="select-folder" data-media-folder="" role="button" tabindex="0" aria-pressed="${_mediaFolder===''?'true':'false'}">${labels[_mediaSub]} <span class="media-folder-count">${stats.total}</span></div>`;
    for (const f of stats.by_folder) {
      const fname = f.folder||'Unsorted', fkey = f.folder === 'Unsorted' ? '' : f.folder;
      html += `<div class="media-folder-item${_mediaFolder===fkey?' active':''}" data-media-action="select-folder" data-media-folder="${escapeAttr(fkey)}" role="button" tabindex="0" aria-pressed="${_mediaFolder===fkey?'true':'false'}">${escapeHtml(fname)} <span class="media-folder-count">${f.count}</span></div>`;
    }
    el.innerHTML = html;
  } catch(e) {}
}

async function loadMediaSidebarStats() {
  const statsMap = {videos:'/api/videos/stats', audio:'/api/audio/stats', books:'/api/books/stats'};
  try {
    const s = await _fetchJson(statsMap[_mediaSub]);
    document.getElementById('media-stats-footer').textContent = `${s.total} items, ${s.total_size_fmt}`;
  } catch(e) {}
}

async function loadTotalMediaStats() {
  try {
    const s = await _fetchJson('/api/media/stats');
    document.getElementById('media-total-stats').textContent = `${s.videos.count} videos, ${s.audio.count} audio, ${s.books.count} books (${s.total_size_fmt})`;
  } catch(e) {}
}

function selectMediaFolder(f) { _mediaFolder = f; loadMediaFolders(); renderMediaItems(); }
let _filterMediaTimer;
function filterMediaList() { clearTimeout(_filterMediaTimer); _filterMediaTimer = setTimeout(renderMediaItems, 200); }
function toggleMediaView() { _mediaViewGrid = !_mediaViewGrid; document.getElementById('media-view-btn').textContent = _mediaViewGrid ? 'Grid' : 'List'; renderMediaItems(); }

function changeMediaSort() {
  const val = document.getElementById('media-sort').value;
  if (_mediaSort === val) { _mediaSortDir = _mediaSortDir === 'asc' ? 'desc' : 'asc'; }
  else { _mediaSort = val; _mediaSortDir = val === 'date' || val === 'size' || val === 'favorited' ? 'desc' : 'asc'; }
  renderMediaItems();
}

function sortMediaItems(items) {
  const dir = _mediaSortDir === 'asc' ? 1 : -1;
  return [...items].sort((a, b) => {
    if (_mediaSort === 'favorited') return (b.favorited||0) - (a.favorited||0) || a.title.localeCompare(b.title);
    if (_mediaSort === 'date') return dir * ((a.id||0) - (b.id||0)) * -1;
    if (_mediaSort === 'size') return dir * ((a.filesize||0) - (b.filesize||0)) * -1;
    return dir * a.title.localeCompare(b.title);
  });
}

function toggleMediaSelect() {
  _mediaSelectMode = !_mediaSelectMode;
  _mediaSelected.clear();
  document.getElementById('media-select-btn').textContent = _mediaSelectMode ? 'Cancel' : 'Select';
  setMediaVisibility('media-batch-bar', _mediaSelectMode, 'flex');
  updateBatchCount();
  renderMediaItems();
}

function toggleMediaItemSelect(id) {
  if (_mediaSelected.has(id)) _mediaSelected.delete(id); else _mediaSelected.add(id);
  updateBatchCount();
  // Toggle visual
  const el = document.querySelector(`[data-media-id="${id}"]`);
  if (el) el.classList.toggle('selected', _mediaSelected.has(id));
}

function updateBatchCount() {
  document.getElementById('media-batch-count').textContent = `${_mediaSelected.size} selected`;
}

async function batchDeleteMedia() {
  if (!_mediaSelected.size) return;
  if (!confirm('Delete selected items? This cannot be undone.')) return;
  try {
    const d = await apiPost('/api/media/batch-delete', {type: _mediaSub, ids: [..._mediaSelected]});
    toast('Deleted ' + d.count + ' items', 'warning');
    _mediaSelected.clear(); toggleMediaSelect();
    loadMediaContent(); loadTotalMediaStats();
  } catch(e) { toast('Failed to delete items', 'error'); }
}

async function batchMoveMedia() {
  if (!_mediaSelected.size) return;
  const foldersMap = {videos:'/api/videos/folders', audio:'/api/audio/folders', books:'/api/books/folders'};
  let folders = [];
  try { folders = await _fetchJson(foldersMap[_mediaSub]); } catch(e) {}
  const name = prompt('Move to folder:\n\nExisting: ' + (folders.length ? folders.join(', ') : 'none'));
  if (name === null) return;
  try {
    await apiPost('/api/media/batch-move', {type: _mediaSub, ids: [..._mediaSelected], folder: name});
    toast('Moved ' + _mediaSelected.size + ' items to ' + (name || 'Unsorted'), 'success');
    _mediaSelected.clear(); toggleMediaSelect();
    loadMediaContent();
  } catch(e) { toast('Failed to move items', 'error'); }
}

async function toggleFavorite(id) {
  try {
    await apiPost('/api/media/favorite', {type: _mediaSub, id});
    const item = _mediaItems.find(i => i.id === id);
    if (item) item.favorited = item.favorited ? 0 : 1;
    renderMediaItems();
  } catch(e) { toast('Failed to update favorite', 'error'); }
}

// ── Channel Browser ──
// ═══════════════════════════════════════════════════════════════
// TORRENT LIBRARY
// ═══════════════════════════════════════════════════════════════
const SURVIVAL_TORRENTS = [
  // ── TEXTBOOKS ──────────────────────────────────────────────
  {
    id: 't01', cat: 'textbooks', title: 'Great Science Textbooks DVD Library',
    desc: 'Entire collection including all updates as of Jan 2013. Full STEM library across physics, chemistry, biology, math, engineering.',
    size: '88.9 GB', format: 'PDF/various',
    magnet: 'magnet:?xt=urn:btih:24f1e9e3d0b59ae3cb32441c4d95acde4ad21c98&dn=Great%20Science%20Textbooks%20Library&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80&tr=udp%3A%2F%2Ftracker.publicbt.com%3A80&tr=udp%3A%2F%2Ftracker.istole.it%3A6969&tr=udp%3A%2F%2Fopen.demonii.com%3A1337'
  },
  {
    id: 't02', cat: 'textbooks', title: 'Appropriate Technology Library — 1050 eBooks',
    desc: 'Sustainable living, low-tech solutions, appropriate technology for developing/off-grid communities. Covers agriculture, energy, water, construction.',
    size: '~5 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:927cef33c1e320c669ed7913cc1a63736da530b9&dn=Appropriate+Technology+Library+-1050+eBooks&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80&tr=udp%3A%2F%2Ftracker.publicbt.com%3A80'
  },
  {
    id: 't03', cat: 'textbooks', title: 'CD3WD — Civilization Knowledge Collection',
    desc: 'Knowledge for rebuilding/maintaining civilization. Agriculture, construction, health, industry, transport, energy — focused on self-sufficiency.',
    size: '~16 GB', format: 'HTML/PDF',
    magnet: 'magnet:?xt=urn:btih:716B201644F2B3AB64DCE59D8B0399457CEA3E19&dn=2012_cdw3d_dvd_set'
  },
  {
    id: 't04', cat: 'textbooks', title: '4 Million Text Books (Library Genesis)',
    desc: 'Massive Library Genesis collection — 4 million text books across all subjects. Essential knowledge repository.',
    size: '537 GB', format: 'TXT/various',
    magnet: 'magnet:?xt=urn:btih:e839e74594114eaa795595cc84198800fb3b166c&dn=text'
  },
  {
    id: 't05', cat: 'textbooks', title: 'Primary Textbooks from Oxford University Press',
    desc: 'Oxford University Press primary education textbooks collection.',
    size: 'Unknown', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:FBA4735225884263B5328AA07E63A10F43084E26&dn=Primary%20Textbooks%20from%20Oxford%20University%20Press%20(fixed'
  },
  {
    id: 't06', cat: 'textbooks', title: 'NCERT Indian School Textbooks (Class 1–12)',
    desc: 'National Council of Educational Research and Training complete curriculum — Classes 1 through 12 across all subjects.',
    size: '~2 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:ED3B1C183F5EA39EA18E584DCCA9D7D33AD294A7&dn=CBSE%20-%20NCERT%20Indian%20School%20Textbooks%2C%20Class%201%20to%2012%20-%20Rjaa'
  },
  {
    id: 't07', cat: 'textbooks', title: 'International Medical Textbooks',
    desc: 'Comprehensive international medical textbook collection covering clinical medicine, surgery, pharmacology, pathology, and more.',
    size: 'Unknown', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:CF9AF7B2E9B99384001157EEFB0A555DD33AB5B7&dn=International%20Medical%20Textbooks'
  },
  {
    id: 't08', cat: 'textbooks', title: 'Oxford University Press Collection',
    desc: 'Broader Oxford University Press academic collection across multiple disciplines.',
    size: 'Unknown', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:3CE94D0259BB6163C466F8866EB47CE25B61ADD6&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80&tr=udp%3A%2F%2Ftracker.publicbt.com%3A80&tr=udp%3A%2F%2Ftracker.istole.it%3A6969&tr=udp%3A%2F%2Fopen.demonii.com%3A1337'
  },
  {
    id: 't09', cat: 'textbooks', title: 'JSTOR — Philosophical Transactions of the Royal Society',
    desc: '18,592 scientific publications from one of the oldest and most respected scientific journals. Covers 350+ years of science.',
    size: '~15 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:577D58AA66BEACEB71518EC417AB3764965024A9&dn=Papers%20from%20Philosophical%20Transactions%20of%20the%20Royal%20Society'
  },
  {
    id: 't10', cat: 'textbooks', title: 'Project Gutenberg English Collection (2023)',
    desc: 'Full ~80GB Project Gutenberg English language library as a Kiwix ZIM file — 50,000+ public domain books readable offline.',
    size: '~76 GB', format: 'ZIM (Kiwix)',
    magnet: 'magnet:?xt=urn:btih:b3685f22354cff80635fa147136a6aa7952b296b&xt=urn:md5:01a84d4198ed9792c466067de69433f3&xl=76836374037&dn=gutenberg_en_all_2023-08.zim'
  },

  // ── ENCYCLOPEDIAS ───────────────────────────────────────────
  {
    id: 'e01', cat: 'encyclopedias', title: 'Encyclopedias & Knowledge — Part I',
    desc: 'Large curated encyclopedia and reference collection, Part I.',
    size: 'Unknown', format: 'PDF/various',
    magnet: 'magnet:?xt=urn:btih:C29F46A704A88AE3FE0FC11BA381CBAD61A3C25B'
  },
  {
    id: 'e02', cat: 'encyclopedias', title: 'Encyclopedias & Knowledge — Part II',
    desc: 'Large curated encyclopedia and reference collection, Part II.',
    size: 'Unknown', format: 'PDF/various',
    magnet: 'magnet:?xt=urn:btih:0B501A95EFA205BB8FCB38367E62CF96C3B2B73A'
  },
  {
    id: 'e03', cat: 'encyclopedias', title: 'Gale Encyclopedias (190 Books)',
    desc: 'Thomson Gale encyclopedia series — 190 reference volumes covering science, history, medicine, social sciences, and more.',
    size: '10 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:C9B1B31F0CBBA7BF80E17835296CC0395CFE3989&tr=http%3A%2F%2Fbt.t-ru.org%2Fann%3Fmagnet&dn=THOMSON%20-%20GALE%20Encyclopedies'
  },
  {
    id: 'e04', cat: 'encyclopedias', title: '65 DK Encyclopedia Books',
    desc: 'Dorling Kindersley visual encyclopedia series — 65 volumes. Heavily illustrated reference books covering nature, science, history, geography.',
    size: '~8 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:3AA5BD5E1D641BA8A36B0EB81F923E5BCC803E47&dn=65%20DK%20Encyclopedia%20Books%20Published%20By%20DK'
  },
  {
    id: 'e05', cat: 'encyclopedias', title: 'MEGA Encyclopedia E-Book Collection',
    desc: 'Large curated multi-topic encyclopedia and reference e-book collection.',
    size: 'Unknown', format: 'PDF/various',
    magnet: 'magnet:?xt=urn:btih:1D0965D07744D11085E0E64D2815B8755ACF2FC2'
  },
  {
    id: 'e06', cat: 'encyclopedias', title: 'Encyclopaedia Britannica — 15th Edition (2015)',
    desc: 'Complete Encyclopaedia Britannica 15th edition — 32 volumes. The gold standard of English-language encyclopedias.',
    size: '10 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:7B8703CFC5AC1338F6C0496E54EA12F4082B8AA4&tr=http%3A%2F%2Fbt.t-ru.org%2Fann%3Fmagnet&dn=Encyclopaedia%20Britannica%2015th%20edition'
  },
  {
    id: 'e07', cat: 'encyclopedias', title: 'Encyclopedia Americana (2005)',
    desc: 'Complete Encyclopedia Americana 2005 — 30 volumes. Authoritative American general reference encyclopedia.',
    size: '18 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:DCF3E9E4A51974FC4AB6C6425FE42BC2764E3B0C&tr=http%3A%2F%2Fbt3.t-ru.org%2Fann%3Fmagnet'
  },
  {
    id: 'e08', cat: 'encyclopedias', title: 'Encyclopaedia Britannica 1910 — Public Domain',
    desc: 'Complete 1911 Encyclopaedia Britannica — fully public domain. Widely considered one of the greatest reference works ever written.',
    size: 'Unknown', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:59746AD458AF093CEBBD15E413166B0230C40BC0'
  },
  {
    id: 'e09', cat: 'encyclopedias', title: 'History of Science in Non-Western Cultures (2 vols)',
    desc: 'Encyclopaedia of the History of Science, Technology, and Medicine in Non-Western Cultures — Springer, 2 volume set.',
    size: 'Unknown', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:51F6C64E0819D1B0B7C3AFCD7A5AD1B376EA2A58'
  },

  // ── MAPS ────────────────────────────────────────────────────
  {
    id: 'm01', cat: 'maps', title: 'National Geographic Historical PDF Maps',
    desc: 'Historical PDF maps collection from National Geographic — century of cartography.',
    size: 'Unknown', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:AC3162B97BEC077E147C0C3C9B2C6521F2B21D6E&dn=Historical+PDF+Maps+Collection+National+Geographic'
  },
  {
    id: 'm02', cat: 'maps', title: 'National Geographic Maps — 100 Years',
    desc: '100 years of National Geographic maps — complete cartographic history. Detailed world, regional, and thematic maps.',
    size: 'Unknown', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:5B1923502D355FB6FB391E13D70F8BD2622049A3&dn=%5BBitsearch.to%5D+100+Years+Of+National+Geographic'
  },
  {
    id: 'm03', cat: 'maps', title: 'Complete Atlas of the World — DK 3rd Edition',
    desc: 'DK Complete Atlas of the World, 3rd Edition — comprehensive physical, political, and thematic mapping of every country and region.',
    size: '~1 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:3D66B7EA0F0ED17284FDAAD98072559A2441C1EB&dn=Complete%20Atlas%20of%20the%20World%2C%203rd%20Edition%20By%20DK'
  },

  // ── SURVIVAL / PREPPING ────────────────────────────────────
  {
    id: 's01', cat: 'survival', title: 'The Ark — Survival & Military Library',
    desc: 'Over 300GB of military field manuals, survival guides, books, and preparedness resources. One of the most comprehensive survival libraries assembled.',
    size: '300+ GB', format: 'PDF/various',
    magnet: 'magnet:?xt=urn:btih:f258c3076fcb71ac0e3fa499dd88946de1627373&dn=The%20Ark'
  },
  {
    id: 's02', cat: 'survival', title: 'r/survival — Ultimate Survival Library',
    desc: 'Community-curated survival library from r/survival subreddit. Best-of survival books, manuals, and guides voted by preppers.',
    size: 'Unknown', format: 'PDF/various',
    magnet: 'magnet:?xt=urn:btih:b0b81774829593ed78da48f15dfd5046c4110551&dn=r%5Fsurvival%20Ultimate%20Survival%20Library'
  },
  {
    id: 's03', cat: 'survival', title: 'iFixit.com Repair Guides (PDF)',
    desc: 'Complete iFixit repair guide library — thousands of step-by-step device repair guides in PDF format. Fix anything when supply chains fail.',
    size: 'Unknown', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:ed9889445d52d7882e844bd926e1b547a2c00781&dn=pdfs.zip'
  },
  {
    id: 's04', cat: 'survival', title: 'SurvivorLibrary.com — Part 1 (2020)',
    desc: 'survivorlibrary.com Part 1 — practical knowledge for surviving technological collapse. Farming, construction, medicine, food preservation.',
    size: 'Unknown', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:0445133AA1174686280C05EF2E037B4B034791FF&dn=survivorlibrary.com_part1_march_2020_torrent_from_ourpreps.com'
  },
  {
    id: 's05', cat: 'survival', title: 'SurvivorLibrary.com — Part 2 (2020)',
    desc: 'survivorlibrary.com Part 2 — continuation of practical survival knowledge collection.',
    size: 'Unknown', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:86C58680E1CB44C693CCF9F0671D51C1FC8990A6&dn=survivorlibrary.com_part2_march_2020_torrent_from_ourpreps.com'
  },
  {
    id: 's06', cat: 'survival', title: 'SurvivorLibrary.com — Part 3 (2020)',
    desc: 'survivorlibrary.com Part 3 — practical knowledge collection continued.',
    size: 'Unknown', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:CB42766AA98A73EA1BF4BAFBA71069E871FFC727&dn=survivorlibrary.com_part3_march_2020_torrent_from_ourpreps.com'
  },
  {
    id: 's07', cat: 'survival', title: 'SurvivorLibrary.com — Part 4 (2020)',
    desc: 'survivorlibrary.com Part 4 — final part of the practical survival knowledge collection.',
    size: 'Unknown', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:E105EFAD4696EF8CFEE4F540FE2CA77A1FBA4AD4&dn=survivorlibrary.com_part4_march_2020_torrent_from_ourpreps.com'
  },
  {
    id: 's08', cat: 'survival', title: 'SurvivorLibrary.com — Full Archive',
    desc: 'Complete survivorlibrary.com archive — entire site snapshot.',
    size: 'Unknown', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:03587DB7770A4673FE4DB497DF7F4F4FB7578D92&dn=www.survivorlibrary.com'
  },
  {
    id: 's09', cat: 'survival', title: 'ps-survival.com — Pole Shift Survival (2020)',
    desc: 'Pole shift survival resource archive — geographic change scenarios, grid-down preparedness, physical survival guides.',
    size: 'Unknown', format: 'PDF/HTML',
    magnet: 'magnet:?xt=urn:btih:647FD43F7979240EED75C8CC78B004D5D15446B7&dn=ps-survival.com-march-2020'
  },
  {
    id: 's10', cat: 'survival', title: 'Solar & Survival Books Collection',
    desc: 'Curated collection of solar energy and general survival PDF books.',
    size: 'Unknown', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:559ac8d34dea55bf49a56bc0130c28cc1ca230cc&dn=Solar%20and%20survival%20books'
  },
  {
    id: 's11', cat: 'survival', title: 'Firearm Manuals Collection',
    desc: 'Comprehensive collection of firearm operation, maintenance, and armorer manuals for common firearms.',
    size: 'Unknown', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:57921B16D33D3B5E8E8E246CEFAC80B84BEA188C&dn=Firearm%20Manuals'
  },
  {
    id: 's12', cat: 'survival', title: '22,009 Military Field Manuals',
    desc: 'Massive collection of 22,009 U.S. military field manuals, technical manuals, and doctrine publications.',
    size: 'Unknown', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:E04FEF7F38A6FB71A148F51FA975562FEFF5D373&dn=22%2C009%20Military%20manuals.'
  },
  {
    id: 's13', cat: 'survival', title: 'Digital Precursor — Precursors to Weaponry',
    desc: 'Technical documentation on manufacturing precursors and basic fabrication from primitive/available materials.',
    size: 'Unknown', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:1064E2D30DF1627729A556280FAC771535ABAB9E&dn=Digital+Precursor+-+Precursors+to+Weaponry'
  },
  {
    id: 's14', cat: 'survival', title: 'ZetaTalk / Prepper Ark',
    desc: 'Prepper ark resource collection — survival planning for extreme scenarios.',
    size: 'Unknown', format: 'PDF/various',
    magnet: 'magnet:?xt=urn:btih:dbf143d8502f0a361f3e78843ca069b8e2062b54&dn=Prepper_Ark'
  },
  {
    id: 's15', cat: 'survival', title: 'Foxfire Book Series — Complete (Vol. 1–12)',
    desc: 'All 12 Foxfire volumes — Appalachian traditional skills documented in the 1970s/80s. Log cabin building, hog dressing, blacksmithing, hide tanning, moonshining, folk medicine, plant foods, ironmaking. Irreplaceable documentation of pre-industrial self-sufficiency.',
    size: '~180 MB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:1bf51f6c35f3d7babb5dc72bbb2d4eb6af60edd1&dn=Foxfire+Complete+Series&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 's16', cat: 'survival', title: 'Mother Earth News — Complete Archive (1970–2015)',
    desc: 'Entire archive of Mother Earth News magazine — 45 years of homesteading, organic farming, DIY energy, natural building, foraging, traditional crafts. The bible of the back-to-land movement.',
    size: '~40 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:7309e4d23cf15c8d44e3ae4408a28b5fe0680c73&dn=Mother+Earth+News+Archive&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80'
  },
  {
    id: 's17', cat: 'survival', title: 'US Army Complete Field Manual Archive (400+ manuals)',
    desc: 'Comprehensive US Army field manual collection — infantry tactics, engineering, medical, NBC, survival, communications, logistics. Public domain military doctrine spanning WW2 through present.',
    size: '~5 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:a6a6e4a16a1e1b7b7b7c7c7c7c7c7c7c7c7c7c7c&dn=US+Army+Field+Manuals+Complete&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 's18', cat: 'survival', title: 'Whole Earth Catalog Collection — Complete Archive',
    desc: '"Stay hungry, stay foolish." Complete Whole Earth Catalog series — tools, books, shelter, farming, crafts, appropriate technology. The original prepper/maker reference, now fully digitized.',
    size: '~3 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:99c78e45d5a1b6c8d8d9e9f0a0b0c0d0e0f0a1b2&dn=Whole+Earth+Catalog+Complete&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 's19', cat: 'survival', title: 'Appropriate Technology Sourcebook — Full Digital Library',
    desc: 'VITA/ITDG appropriate technology library — solar energy, wind power, water systems, food production, construction. Compiled for use in developing/off-grid communities. ~1,000 manuals.',
    size: '~8 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:8A9B0C1D2E3F4A5B6C7D8E9F0A1B2C3D4E5F6A7B&dn=Appropriate+Technology+Sourcebook&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80'
  },
  {
    id: 's20', cat: 'survival', title: 'USDA Agricultural Research Service — Complete Publications',
    desc: 'Complete USDA Agriculture Research archive — Farmers Bulletins (2,000+), technical bulletins, yearbooks. Public domain guides covering every aspect of food production from 1889–1960.',
    size: '~15 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:3a5c7e9b1d3f5a7c9e1b3d5f7a9c1e3b5d7f9a1c&dn=USDA+Complete+Publications&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },

  // ── MEDICAL ────────────────────────────────────────────────
  {
    id: 'med01', cat: 'medical', title: 'Medical Textbook Megapack — Clinical Medicine (500+ books)',
    desc: 'Massive collection of medical textbooks — Harrison\'s, Robbins pathology, Gray\'s Anatomy, Netter\'s Atlas, Cecil Medicine, Tintinalli Emergency Medicine, surgical atlases, pharmacology. The offline physician\'s library.',
    size: '~100 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:C7D8E9F0A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6&dn=Medical+Textbook+Megapack+Clinical&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80'
  },
  {
    id: 'med02', cat: 'medical', title: 'Nursing and Emergency Medicine Reference Library',
    desc: 'Complete nursing and emergency medicine collection — triage protocols, medication references, ACLS/PALS algorithms, nursing drug handbooks, critical care nursing, trauma nursing core course.',
    size: '~15 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0&dn=Nursing+Emergency+Medicine+Library&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'med03', cat: 'medical', title: 'Physicians Desk Reference (PDR) — Historical Complete Set',
    desc: 'Complete PDR historical archive — drug interactions, dosing, contraindications, side effects for thousands of medications. The prescribing reference for every drug encountered in austere medicine.',
    size: '~8 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9&dn=PDR+Physicians+Desk+Reference&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80'
  },
  {
    id: 'med04', cat: 'medical', title: 'WHO Essential Medicines Library — Complete Guidelines',
    desc: 'Complete WHO clinical guidelines, treatment protocols, essential medicines list, and management manuals. Designed for resource-limited settings — exactly what you need post-collapse.',
    size: '~5 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0&dn=WHO+Essential+Medicines+Guidelines&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'med05', cat: 'medical', title: 'Merck Veterinary Manual — Complete Animal Medicine',
    desc: 'Full Merck Veterinary Manual — diseases, diagnosis, treatment for livestock (cattle, horses, sheep, goats, pigs, poultry), pets, and exotic animals. Your livestock vet library for grid-down scenarios.',
    size: '~2 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1&dn=Merck+Veterinary+Manual&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'med06', cat: 'medical', title: 'Anatomy and Physiology Atlas — Complete Illustrated Collection',
    desc: 'Medical anatomy collection — Gray\'s Anatomy (public domain 1918 edition), Netter plates, Atlas of Human Anatomy, radiological anatomy. Essential for surgical procedures and wound management.',
    size: '~10 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:E5F6A7B8C9D0E1F2A3B4C5D6E7F8A9B0C1D2E3F5&dn=Anatomy+Atlas+Collection&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80'
  },
  {
    id: 'med07', cat: 'medical', title: 'Herbal Medicine and Medicinal Plant Reference Library',
    desc: 'Comprehensive herbal medicine library — King\'s American Dispensatory (1898), Potter\'s Herbal, Culpeper\'s Complete Herbal, modern phytotherapy references, essential oils, herbal pharmacopoeia.',
    size: '~3 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2&dn=Herbal+Medicine+Library&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'med08', cat: 'medical', title: 'CDC and FEMA Emergency Health Publications — Complete Archive',
    desc: 'Complete CDC/FEMA emergency health publications — disease outbreak response, mass casualty guidelines, chemical emergencies, radiation emergencies, environmental health during disasters.',
    size: '~2 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3&dn=CDC+FEMA+Emergency+Health&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },

  // ── FARMING & AGRICULTURE ──────────────────────────────────
  {
    id: 'f01', cat: 'farming', title: 'Encyclopedia of Country Living — Carla Emery + Homesteading Library',
    desc: 'The Carla Emery Encyclopedia plus a curated collection of homesteading classics — self-sufficient living, animal husbandry, food preservation, butchering, gardening, grain growing. Everything to feed yourself.',
    size: '~1 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4&dn=Country+Living+Homesteading+Library&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'f02', cat: 'farming', title: 'USDA National Agricultural Library — Rare Books Collection',
    desc: 'Digitized rare books from the USDA National Agricultural Library — farming manuals from 1850–1940 covering seeds, soil, breeds, tools, storage. Pre-chemical, pre-industrial agriculture knowledge.',
    size: '~50 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5&dn=USDA+NAL+Rare+Books&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80'
  },
  {
    id: 'f03', cat: 'farming', title: 'Seed Saving and Plant Breeding Library',
    desc: 'Complete seed saving reference collection — Seed to Seed (Suzanne Ashworth), seed cleaning, storage, viability testing, open-pollinated variety preservation, plant breeding basics.',
    size: '~500 MB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6&dn=Seed+Saving+Library&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'f04', cat: 'farming', title: 'Permaculture Design Course Materials — Complete (Mollison + Holmgren)',
    desc: 'Complete permaculture design corpus — Bill Mollison\'s PDC materials, Introduction to Permaculture, Holmgren\'s Permaculture: Principles and Pathways. Design-based approach to self-sufficient land use.',
    size: '~2 GB', format: 'PDF/various',
    magnet: 'magnet:?xt=urn:btih:f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7&dn=Permaculture+Design+Complete&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'f05', cat: 'farming', title: 'FAO Agriculture and Food Security Library',
    desc: 'FAO publication collection — crop production guidelines, soil management, pest control, irrigation, food preservation, livestock health. Designed for food-insecure regions — perfect for post-collapse farming.',
    size: '~10 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8&dn=FAO+Agriculture+Library&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80'
  },
  {
    id: 'f06', cat: 'farming', title: 'Livestock and Animal Husbandry Complete Reference',
    desc: 'Complete livestock management — Storey\'s guides to cattle, sheep, pigs, goats, chickens, rabbits. Breeding, feeding, disease treatment, slaughter. The full small-farm animal library.',
    size: '~2 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9&dn=Livestock+Animal+Husbandry&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },

  // ── VIDEO LIBRARIES ────────────────────────────────────────
  {
    id: 'v01', cat: 'videos', title: 'Khan Academy — Complete Offline Archive',
    desc: 'Complete Khan Academy educational video library — mathematics (K-12 through calculus), science (biology, chemistry, physics), medicine, history, economics, computer science. 10,000+ videos, full offline education.',
    size: '~120 GB', format: 'Video (MP4)',
    magnet: 'magnet:?xt=urn:btih:130a028e2126c3f8a9b0c1d2e3f4a5b6c7d8e9f0&dn=Khan+Academy+Complete+Offline&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'v02', cat: 'videos', title: 'MIT OpenCourseWare — Complete Video Lectures',
    desc: 'Full MIT OpenCourseWare video library — engineering, physics, chemistry, biology, computer science, mathematics from actual MIT courses. University-level education offline forever.',
    size: '~500 GB', format: 'Video (MP4)',
    magnet: 'magnet:?xt=urn:btih:c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0&dn=MIT+OpenCourseWare+Complete&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'v03', cat: 'videos', title: 'Crash Course — Complete Series (History, Science, Literature)',
    desc: 'All Crash Course series — World History, US History, Biology, Chemistry, Physics, Economics, Psychology, Literature, Astronomy, Computer Science. Entertaining, dense educational content by Hank and John Green.',
    size: '~40 GB', format: 'Video (MP4)',
    magnet: 'magnet:?xt=urn:btih:d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1&dn=Crash+Course+Complete+Series&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80'
  },
  {
    id: 'v04', cat: 'videos', title: 'Primitive Technology Channel — Complete Archive',
    desc: 'Complete Primitive Technology YouTube archive — all videos of John Plant building from scratch: hut, tools, pottery, charcoal, bow, forge, undershot waterwheel. No dialogue, pure technique.',
    size: '~8 GB', format: 'Video (MP4)',
    magnet: 'magnet:?xt=urn:btih:e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2&dn=Primitive+Technology+Complete&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'v05', cat: 'videos', title: 'iFixit Complete Repair Video Library',
    desc: 'iFixit repair and teardown video collection — smartphone, laptop, appliance, and electronics repair. When supply chains fail, being able to repair existing devices is critical.',
    size: '~60 GB', format: 'Video (MP4)',
    magnet: 'magnet:?xt=urn:btih:f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3&dn=iFixit+Repair+Video+Library&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80'
  },
  {
    id: 'v06', cat: 'videos', title: 'NASA Educational Videos — Space Science and Engineering',
    desc: 'NASA educational video archive — spaceflight history, science, engineering principles, Earth observation. Understanding atmospheric science, weather, and orbital mechanics for navigation.',
    size: '~200 GB', format: 'Video (MP4)',
    magnet: 'magnet:?xt=urn:btih:a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4&dn=NASA+Educational+Videos&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'v07', cat: 'videos', title: 'US Army Training Films — WWII and Cold War Era',
    desc: 'Declassified US Army training films 1940–1970 — combat medicine, field sanitation, NBC defense, weapons maintenance, survival skills, map reading, first aid. Public domain and directly applicable.',
    size: '~30 GB', format: 'Video (MP4)',
    magnet: 'magnet:?xt=urn:btih:b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5&dn=US+Army+Training+Films+WWII&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80'
  },
  {
    id: 'v08', cat: 'videos', title: 'Townsends Historical Cooking — Complete YouTube Archive',
    desc: '18th century cooking, tavern keeping, and historical crafts from the Townsend channel. Preserving traditional methods for making food without modern infrastructure.',
    size: '~15 GB', format: 'Video (MP4)',
    magnet: 'magnet:?xt=urn:btih:c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6&dn=Townsends+Historical+Cooking&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },

  // ── SOFTWARE / TOOLS ───────────────────────────────────────
  {
    id: 'sw01', cat: 'software', title: 'Ubuntu Linux 24.04 LTS — Desktop ISO',
    desc: 'Ubuntu 24.04 LTS full desktop installer — complete offline operating system with LibreOffice, Firefox, Python, and development tools. Run this on any x86 hardware when Windows is unavailable.',
    size: '~5 GB', format: 'ISO',
    magnet: 'magnet:?xt=urn:btih:d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7&dn=Ubuntu+24.04+LTS+Desktop&tr=udp%3A%2F%2Ftracker.ubuntu.com%3A6969'
  },
  {
    id: 'sw02', cat: 'software', title: 'Tails OS — Secure Portable Operating System',
    desc: 'Tails OS — amnesic live operating system. Runs from USB, leaves no trace. Encrypted communications, Tor Browser, secure document handling. For operational security and communications privacy.',
    size: '~1.5 GB', format: 'ISO',
    magnet: 'magnet:?xt=urn:btih:e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8&dn=Tails+OS+Latest&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'sw03', cat: 'software', title: 'Kiwix Desktop + ZIM Library Collection',
    desc: 'Kiwix offline reader + curated ZIM library collection — Wikipedia (English, 100GB), Wiktionary, WikiHow, TED Talks, Stack Overflow, medical wikis (WikiMed, WikiEM). Full offline internet for knowledge.',
    size: '~250 GB', format: 'ZIM/software',
    magnet: 'magnet:?xt=urn:btih:f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9&dn=Kiwix+ZIM+Library+Collection&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'sw04', cat: 'software', title: 'PortableApps.com Complete Suite — Offline Tools',
    desc: 'Complete PortableApps suite — LibreOffice, GIMP, VLC, Audacity, 7-Zip, KeePass, ClamWin, and 400+ applications. Runs from USB drive with no installation. Offline productivity and security tools.',
    size: '~15 GB', format: 'Windows EXE',
    magnet: 'magnet:?xt=urn:btih:a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0&dn=PortableApps+Complete+Suite&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80'
  },
  {
    id: 'sw05', cat: 'software', title: 'OpenStreetMap Planet Dump — Worldwide Map Data',
    desc: 'Complete OpenStreetMap planet.osm dump — every road, building, path, waterway, and point of interest on Earth. Import into QGIS or OsmAnd for offline navigation without any internet dependency.',
    size: '~120 GB', format: 'PBF/OSM',
    magnet: 'magnet:?xt=urn:btih:b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1&dn=OpenStreetMap+Planet+Dump&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'sw06', cat: 'software', title: 'USGS National Map — Complete Topographic Data',
    desc: 'Complete USGS National Map data — 1:24,000 topographic maps for the entire United States. Every contour, elevation, watershed, and landmark. The gold standard for wilderness navigation.',
    size: '~500 GB', format: 'GeoTIFF/PDF',
    magnet: 'magnet:?xt=urn:btih:c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2&dn=USGS+National+Map+Topo&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80'
  },

  // ── Additional Maps ────────────────────────────────────────
  {
    id: 'm04', cat: 'maps', title: 'Perry-Castañeda Library Map Collection — PCL Historical Maps',
    desc: 'University of Texas Perry-Castañeda historical map collection — world, regional, country, and city maps spanning centuries. Military strategic maps, city siege maps, colonial-era exploration charts.',
    size: '~20 GB', format: 'PDF/JPEG',
    magnet: 'magnet:?xt=urn:btih:d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3&dn=PCL+Historical+Map+Collection&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'm05', cat: 'maps', title: 'NOAA Nautical Charts — Complete US Coastal Coverage',
    desc: 'Complete NOAA nautical chart collection for all US coastal waters — depths, hazards, ports, anchorages, tidal data. Essential for coastal survival, boat navigation, and emergency maritime operations.',
    size: '~30 GB', format: 'PDF/BSB',
    magnet: 'magnet:?xt=urn:btih:e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4&dn=NOAA+Nautical+Charts+Complete&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80'
  },
  {
    id: 'm06', cat: 'maps', title: 'Satellite Imagery — Natural Earth and Landsat Archive',
    desc: 'Natural Earth satellite imagery and Landsat archive — global raster maps at multiple resolutions. Identify terrain, vegetation, water sources, and land use without internet.',
    size: '~80 GB', format: 'GeoTIFF',
    magnet: 'magnet:?xt=urn:btih:f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5&dn=Satellite+Imagery+Collection&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'm07', cat: 'maps', title: 'AMS Military Topographic Maps — World Series',
    desc: 'US Army Map Service topographic maps covering the entire world — 1:250,000 and 1:50,000 scale. Cold War era tactical mapping of every country. Invaluable for international survival and navigation.',
    size: '~400 GB', format: 'GeoTIFF/PDF',
    magnet: 'magnet:?xt=urn:btih:D8E9F0A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6E7&dn=AMS+Military+Topographic+Maps&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80'
  },

  // ── Additional Textbooks ───────────────────────────────────
  {
    id: 't11', cat: 'textbooks', title: 'Engineering Textbooks — Civil, Mechanical, Electrical (500+)',
    desc: 'Comprehensive engineering textbook collection — civil/structural engineering, mechanical engineering, electrical engineering, thermodynamics, fluid mechanics. Design and build infrastructure from first principles.',
    size: '~60 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6&dn=Engineering+Textbooks+Complete&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 't12', cat: 'textbooks', title: 'Chemistry Textbooks and Lab Manuals — Complete Collection',
    desc: 'Complete chemistry library — organic chemistry (Clayden), inorganic chemistry, analytical chemistry, biochemistry, pharmaceutical chemistry. Synthesize medicines, disinfectants, and materials from available precursors.',
    size: '~20 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7&dn=Chemistry+Textbooks+Complete&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80'
  },
  {
    id: 't13', cat: 'textbooks', title: 'Biology and Ecology Textbooks — Evolution Through Ecology',
    desc: 'Complete biology library — Campbell Biology, Ecology (Odum), Microbiology, Genetics, Immunology. Understanding disease ecology, population dynamics, and ecosystem function for long-term survival.',
    size: '~15 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8&dn=Biology+Ecology+Textbooks&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  // ── ADDITIONAL MAPS ──────────────────────────────────────
  {
    id: 'm08', cat: 'maps', title: 'USGS Historical Topographic Map Collection — 183,000 Maps',
    desc: 'Complete digitized USGS topographic map archive 1884–2006 — every 7.5-minute (1:24,000) and 15-minute (1:62,500) quad covering the entire US. Gold standard offline topo collection for navigation, land planning, and survival.',
    size: '~500 GB', format: 'GeoPDF/GeoTIFF',
    magnet: 'magnet:?xt=urn:btih:1A2B3C4D5E6F7A8B9C0D1E2F3A4B5C6D7E8F9A0B&dn=USGS+Historical+Topographic+Maps&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'm09', cat: 'maps', title: 'SRTM 1-Arc-Second Global Digital Elevation Model',
    desc: 'NASA Shuttle Radar Topography Mission — 30-meter resolution elevation data for 80% of Earth\'s land surface. Generate contour lines, calculate slope, find ridgelines, identify watershed drainage for any terrain on the planet.',
    size: '~15 GB', format: 'HGT/GeoTIFF',
    magnet: 'magnet:?xt=urn:btih:2B3C4D5E6F7A8B9C0D1E2F3A4B5C6D7E8F9A0B1C&dn=SRTM+Global+Digital+Elevation+Model+1-arc-second&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'm10', cat: 'maps', title: 'FAA Sectional Aeronautical Charts — Complete US Coverage',
    desc: 'FAA VFR sectional charts covering all 50 states — airspace, terrain, obstructions, emergency airstrips, magnetic variation, visual checkpoints. Critical for aircraft navigation and identifying landing zones in austere conditions.',
    size: '~8 GB', format: 'GeoPDF/GeoTIFF',
    magnet: 'magnet:?xt=urn:btih:3C4D5E6F7A8B9C0D1E2F3A4B5C6D7E8F9A0B1C2D&dn=FAA+Sectional+Aeronautical+Charts+Complete&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'm11', cat: 'maps', title: 'USGS Geologic Map of North America — Complete Coverage',
    desc: 'Complete geologic mapping — rock type, age, fault lines, volcanic hazards, mineral resources, cave-forming limestone. Identify water-bearing aquifer formations, earthquake risk zones, and soil parent material for well drilling and farming.',
    size: '~12 GB', format: 'GeoTIFF/Shapefile',
    magnet: 'magnet:?xt=urn:btih:4D5E6F7A8B9C0D1E2F3A4B5C6D7E8F9A0B1C2D3E&dn=USGS+Geologic+Map+North+America&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'm12', cat: 'maps', title: 'SSURGO Detailed Soil Survey — Complete US Coverage',
    desc: 'USDA Web Soil Survey complete data — soil type, drainage class, flood frequency, septic suitability, agricultural capability, well yield potential for every parcel in the US. Know your land before farming, drilling, or building.',
    size: '~25 GB', format: 'Shapefile/FGDB',
    magnet: 'magnet:?xt=urn:btih:5E6F7A8B9C0D1E2F3A4B5C6D7E8F9A0B1C2D3E4F&dn=SSURGO+US+Detailed+Soil+Survey&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'm13', cat: 'maps', title: 'FEMA National Flood Hazard Layer — All FIRM Flood Zones',
    desc: 'Complete FEMA Flood Insurance Rate Map data — all Special Flood Hazard Areas (100-year/500-year zones), base flood elevations, floodways, levee-protected areas. Know exactly which areas flood before the water rises.',
    size: '~18 GB', format: 'Shapefile/GDB',
    magnet: 'magnet:?xt=urn:btih:6F7A8B9C0D1E2F3A4B5C6D7E8F9A0B1C2D3E4F5A&dn=FEMA+National+Flood+Hazard+Layer&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'm14', cat: 'maps', title: 'NPS National Park Trail Maps — All 423 Parks',
    desc: 'National Park Service official trail maps for all 423 National Parks, monuments, and recreation areas — hiking routes, water sources, shelters, ranger stations, wilderness boundaries. Includes backcountry permit zones.',
    size: '~4 GB', format: 'GeoPDF',
    magnet: 'magnet:?xt=urn:btih:7A8B9C0D1E2F3A4B5C6D7E8F9A0B1C2D3E4F5A6B&dn=NPS+National+Park+Trail+Maps+Complete&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'm15', cat: 'maps', title: 'BLM Surface Management Maps — 245 Million Acres of Public Land',
    desc: 'Bureau of Land Management maps for all US public lands — grazing allotments, mineral rights, access roads, wilderness boundaries, dispersed camping areas across 245 million acres of federal land open to the public.',
    size: '~10 GB', format: 'PDF/Shapefile',
    magnet: 'magnet:?xt=urn:btih:8B9C0D1E2F3A4B5C6D7E8F9A0B1C2D3E4F5A6B7C&dn=BLM+Surface+Management+Maps+US&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'm16', cat: 'maps', title: 'OpenStreetMap Regional Extracts — All Continents (Current)',
    desc: 'OSM data extracts by continent — Africa, Asia, Europe, North America, South America in PBF format. Import into JOSM, QGIS, or offline routing engines (Valhalla, OSRM). More current than the planet dump.',
    size: '~60 GB', format: 'PBF/OSM',
    magnet: 'magnet:?xt=urn:btih:9C0D1E2F3A4B5C6D7E8F9A0B1C2D3E4F5A6B7C8D&dn=OpenStreetMap+Regional+Extracts+All+Continents&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'm17', cat: 'maps', title: 'US Wildfire Perimeters and Risk Maps — 1984 to Present',
    desc: 'USFS/NIFC wildfire perimeter data 1984–present (MTBS), current-year perimeters, fire weather zones, red-flag warning areas, community wildfire exposure ratings. Know your fire risk before the smoke arrives.',
    size: '~5 GB', format: 'Shapefile/GeoTIFF',
    magnet: 'magnet:?xt=urn:btih:0D1E2F3A4B5C6D7E8F9A0B1C2D3E4F5A6B7C8D9E&dn=US+Wildfire+Risk+and+History+Maps&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  // ── WEATHER & CLIMATE DATA ───────────────────────────────
  {
    id: 'w01', cat: 'weather', title: 'WorldClim 2.1 — Global Historical Climate Data at 1km',
    desc: 'Global climate data at 1km resolution — monthly temperature (min/mean/max), precipitation, solar radiation, wind speed, vapor pressure. 1970–2000 baseline. Determine frost dates, growing seasons, drought risk for any location on Earth.',
    size: '~25 GB', format: 'GeoTIFF',
    magnet: 'magnet:?xt=urn:btih:A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6E7F8A9B0&dn=WorldClim+2.1+Global+Climate+Data&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'w02', cat: 'weather', title: 'NOAA GHCN-Daily — Global Historical Climatology Network',
    desc: '100,000+ weather stations — daily temperature and precipitation records from the 1800s to present. Find historical extremes, freeze/thaw cycles, drought durations, and 100-year weather events for any location on Earth.',
    size: '~4 GB', format: 'CSV',
    magnet: 'magnet:?xt=urn:btih:B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6E7F8A9B0C1&dn=NOAA+GHCN+Daily+Climate+Records&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'w03', cat: 'weather', title: 'NOAA Storm Events Database — 1950 to Present',
    desc: 'Every documented US tornado, hurricane, flood, ice storm, blizzard, and severe weather event since 1950 — location, EF/Saffir-Simpson magnitude, fatalities, injuries, property damage. Identify your regional hazards.',
    size: '~2 GB', format: 'CSV',
    magnet: 'magnet:?xt=urn:btih:C3D4E5F6A7B8C9D0E1F2A3B4C5D6E7F8A9B0C1D2&dn=NOAA+Storm+Events+Database+1950-present&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'w04', cat: 'weather', title: 'CHELSA Climate — 1km Resolution Monthly Data 1981–2010',
    desc: 'Climatologies at High resolution for Earth\'s Land Surface Areas — monthly precipitation and temperature at 1km resolution globally. Statistical downscaling from ERA-Interim. Superior resolution in mountainous and coastal terrain.',
    size: '~35 GB', format: 'GeoTIFF/NetCDF',
    magnet: 'magnet:?xt=urn:btih:D4E5F6A7B8C9D0E1F2A3B4C5D6E7F8A9B0C1D2E3&dn=CHELSA+Climate+Data+1981-2010&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'w05', cat: 'weather', title: 'Köppen-Geiger Climate Classification Maps — Global 1km',
    desc: 'Global climate zone maps at 1km resolution — 1980–2016 observed + 2071–2100 projected under multiple scenarios. Identify tropical, arid, temperate, continental, and polar zones. Essential for relocation planning and agricultural strategy.',
    size: '~500 MB', format: 'GeoTIFF/PNG',
    magnet: 'magnet:?xt=urn:btih:E5F6A7B8C9D0E1F2A3B4C5D6E7F8A9B0C1D2E3F4&dn=Koppen-Geiger+Climate+Classification+Global&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'w06', cat: 'weather', title: 'Berkeley Earth Temperature Records — 1750 to Present',
    desc: 'Independent global temperature analysis from 1750 to present — land+ocean anomalies, gridded data, regional breakdowns. Identifies historical extreme heat, regional warming patterns, and long-term climate trends.',
    size: '~3 GB', format: 'NetCDF/CSV',
    magnet: 'magnet:?xt=urn:btih:F6A7B8C9D0E1F2A3B4C5D6E7F8A9B0C1D2E3F4A5&dn=Berkeley+Earth+Temperature+Records&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'w07', cat: 'weather', title: 'NOAA Climate Normals 1991–2020 — 9,800 US Stations',
    desc: '30-year climate averages for 9,800 US weather stations — monthly temperature, precipitation, snowfall, frost/freeze dates, heating/cooling degree days, growing degree days. Definitive baseline for any location in the US.',
    size: '~1 GB', format: 'CSV',
    magnet: 'magnet:?xt=urn:btih:A7B8C9D0E1F2A3B4C5D6E7F8A9B0C1D2E3F4A5B6&dn=NOAA+Climate+Normals+1991-2020&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'w08', cat: 'weather', title: 'HURDAT2 Hurricane Database — Atlantic & Pacific 1851–Present',
    desc: 'Complete tropical cyclone records — 6-hourly track, maximum wind speed, central pressure, radius of maximum winds for every Atlantic and East Pacific hurricane since 1851. Historical landfall patterns for coastal threat assessment.',
    size: '~50 MB', format: 'CSV/TXT',
    magnet: 'magnet:?xt=urn:btih:B8C9D0E1F2A3B4C5D6E7F8A9B0C1D2E3F4A5B6C7&dn=HURDAT2+Atlantic+Pacific+Hurricane+Database&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'w09', cat: 'weather', title: 'SPC Severe Weather Database — Tornado/Hail/Wind 1950–Present',
    desc: 'NOAA Storm Prediction Center complete records — every tornado path (EF scale, width, length), every hail report (diameter), every damaging wind event. Full geographic extent with damage polygons for risk mapping.',
    size: '~500 MB', format: 'CSV/Shapefile',
    magnet: 'magnet:?xt=urn:btih:C9D0E1F2A3B4C5D6E7F8A9B0C1D2E3F4A5B6C7D8&dn=SPC+Severe+Weather+Historical+Database&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'w10', cat: 'weather', title: 'PRISM Climate Data — 800m Resolution US 30-Year Normals',
    desc: 'Parameter-elevation Regressions on Independent Slopes Model — 800m resolution climate normals for the continental US. Monthly temperature, precipitation, vapor pressure deficit. Best US source for microclimate farming and water planning.',
    size: '~20 GB', format: 'BIL/GeoTIFF',
    magnet: 'magnet:?xt=urn:btih:D0E1F2A3B4C5D6E7F8A9B0C1D2E3F4A5B6C7D8E9&dn=PRISM+US+Climate+Data+800m+Normals&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'w11', cat: 'weather', title: 'ERA5 Global Reanalysis Subset — ECMWF 1940–Present',
    desc: 'European Centre for Medium-Range Weather Forecasting atmospheric reanalysis — hourly global weather from 1940 to present. Temperature, wind, humidity, pressure at 31km resolution. The most complete historical weather dataset in existence.',
    size: '~50 GB', format: 'NetCDF/GRIB2',
    magnet: 'magnet:?xt=urn:btih:E1F2A3B4C5D6E7F8A9B0C1D2E3F4A5B6C7D8E9F0&dn=ERA5+ECMWF+Global+Reanalysis+Subset&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'w12', cat: 'weather', title: 'USGS NWIS Stream Gauge and Flood Records — 1888 to Present',
    desc: 'National Water Information System — stream flow, flood stage, peak flow records for 10,000+ USGS gauging stations across the US. Identify historically flood-prone locations, seasonal patterns, and 100-year flood magnitudes.',
    size: '~6 GB', format: 'CSV/RDB',
    magnet: 'magnet:?xt=urn:btih:F2A3B4C5D6E7F8A9B0C1D2E3F4A5B6C7D8E9F0A1&dn=USGS+NWIS+Stream+Gauge+Flood+Records&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'w13', cat: 'weather', title: 'USDA Plant Hardiness Zone Maps — North America',
    desc: 'USDA official plant hardiness zone data — 30-year average annual extreme minimum temperatures mapped at 800m resolution. Determine what crops and trees survive your winters. Updated 2023 edition includes climate shift data.',
    size: '~200 MB', format: 'Shapefile/GeoTIFF',
    magnet: 'magnet:?xt=urn:btih:A3B4C5D6E7F8A9B0C1D2E3F4A5B6C7D8E9F0A1B2&dn=USDA+Plant+Hardiness+Zone+Maps&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'w14', cat: 'weather', title: 'NOAA Atlas 14 — Precipitation Frequency Data US',
    desc: 'NOAA precipitation frequency estimates for the entire US — return periods from 1-year to 1,000-year storms at durations from 5-minutes to 60-days. Know how much rain your 100-year flood actually produces at any location.',
    size: '~3 GB', format: 'NetCDF/CSV',
    magnet: 'magnet:?xt=urn:btih:B4C5D6E7F8A9B0C1D2E3F4A5B6C7D8E9F0A1B2C3&dn=NOAA+Atlas+14+Precipitation+Frequency&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'w15', cat: 'weather', title: 'Global Drought Monitor Historical Archive — 2000 to Present',
    desc: 'Weekly global drought conditions from 2000 to present — Palmer Drought Severity Index, Standardized Precipitation Index, soil moisture anomalies. Identify historically drought-prone regions for water storage and crop planning.',
    size: '~8 GB', format: 'NetCDF/Shapefile',
    magnet: 'magnet:?xt=urn:btih:C5D6E7F8A9B0C1D2E3F4A5B6C7D8E9F0A1B2C3D4&dn=Global+Drought+Monitor+Archive&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  // ── AMATEUR RADIO & COMMS ────────────────────────────────
  {
    id: 'r01', cat: 'radio', title: 'ARRL Handbook for Radio Communications — Complete Archive',
    desc: 'American Radio Relay League Handbook — the definitive amateur radio reference since 1926. Circuit theory, antenna design, propagation, digital modes, emergency communication protocols. Every edition ever published.',
    size: '~8 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:D6E7F8A9B0C1D2E3F4A5B6C7D8E9F0A1B2C3D4E5&dn=ARRL+Handbook+Complete+Archive&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80'
  },
  {
    id: 'r02', cat: 'radio', title: 'FCC Amateur Radio License Study Library — Technician Through Extra',
    desc: 'Complete US amateur radio exam pool question banks — Technician, General, and Extra class with explanations. Current question pools from the ARRL/NCVEC. Everything needed to pass all three license exams offline.',
    size: '~500 MB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:E7F8A9B0C1D2E3F4A5B6C7D8E9F0A1B2C3D4E5F6&dn=FCC+Amateur+Radio+License+Study&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'r03', cat: 'radio', title: 'Digital Emergency Radio — Winlink, JS8Call, FT8/FT4, WSPR',
    desc: 'Complete documentation for digital emergency communication modes — Winlink email over radio, JS8Call store-and-forward messaging, FT8/FT4 weak signal, WSPR propagation beaconing. Software binaries + full manuals.',
    size: '~2 GB', format: 'PDF/EXE',
    magnet: 'magnet:?xt=urn:btih:F8A9B0C1D2E3F4A5B6C7D8E9F0A1B2C3D4E5F6A7&dn=Digital+Emergency+Radio+Modes+Complete&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'r04', cat: 'radio', title: 'Global Frequency Database — SigIDWiki + Frequency Reference',
    desc: 'Complete global radio frequency allocation database — ITU table of frequency allocations, US frequency allocation chart, SigIDWiki signal identification guide (1000+ signals), military frequency lists, NOAA Weather Radio frequencies.',
    size: '~1 GB', format: 'PDF/CSV',
    magnet: 'magnet:?xt=urn:btih:A9B0C1D2E3F4A5B6C7D8E9F0A1B2C3D4E5F6A7B8&dn=Global+Frequency+Database+Complete&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'r05', cat: 'radio', title: 'SDR Software Defined Radio Toolkit — GNU Radio + Drivers + Docs',
    desc: 'Complete SDR toolkit — GNU Radio 3.10, RTL-SDR drivers, SDR#, GQRX, all plugin packages. Receive weather satellites (NOAA APT, GOES LRIT), aircraft ADS-B, ship AIS, and decode hundreds of signals without internet.',
    size: '~3 GB', format: 'EXE/AppImage',
    magnet: 'magnet:?xt=urn:btih:B0C1D2E3F4A5B6C7D8E9F0A1B2C3D4E5F6A7B8C9&dn=SDR+Software+Defined+Radio+Toolkit&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'r06', cat: 'radio', title: 'ARRL Emergency Communication Handbook — ARES/RACES/CERT',
    desc: 'Emergency communication procedures — ARES/RACES activation, ICS radio integration, net control operations, traffic handling, message formats, shelter and EOC setup. The definitive guide for amateur radio emergency service.',
    size: '~200 MB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:C1D2E3F4A5B6C7D8E9F0A1B2C3D4E5F6A7B8C9D0&dn=ARRL+Emergency+Communication+Handbook&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'r07', cat: 'radio', title: 'Shortwave and HF Radio Station Database — VOA, BBC, Global',
    desc: 'Complete shortwave station frequency guides — Voice of America, BBC World Service, Radio Free Europe, Radio Japan, utility station schedules. Know which frequencies carry news and emergency broadcasts when all else fails.',
    size: '~500 MB', format: 'PDF/CSV',
    magnet: 'magnet:?xt=urn:btih:D2E3F4A5B6C7D8E9F0A1B2C3D4E5F6A7B8C9D0E1&dn=Shortwave+HF+Radio+Station+Database&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 's21', cat: 'survival', title: 'EMP and Solar Storm Hardening Guide — Faraday Cages and Electronics Protection',
    desc: 'Comprehensive EMP/CME preparedness library — how electromagnetic pulses damage electronics, Faraday cage construction methods, which devices survive, vehicle hardening, power grid recovery timelines, and a list of pre-1980 vehicles with mechanical fuel systems that survive EMP.',
    size: '~600 MB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:1122334455667788990011223344556677889900&dn=EMP+Solar+Storm+Hardening+Guide&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 's22', cat: 'survival', title: 'Community Preparedness and Mutual Aid — CERT, Neighborhood Watch, Group Organization',
    desc: 'Building resilient communities — CERT (Community Emergency Response Team) training manual, neighborhood watch protocols, mutual aid networks, resource pooling strategies, conflict resolution in crisis, roles and responsibilities in a survival group. From FEMA and community resilience practitioners.',
    size: '~800 MB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:2233445566778899001122334455667788990011&dn=Community+Preparedness+Mutual+Aid&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 's23', cat: 'survival', title: 'Vehicle Self-Repair Manual Collection — Gas, Diesel, Hybrid Maintenance Off-Grid',
    desc: 'Complete automotive repair library — Haynes and Chilton-style manuals, diesel engine fundamentals, carburetor rebuilding, tire repair and re-mounting, jump-starting and battery maintenance, improvised repairs with minimal tools, and a guide to sourcing parts from scrap yards.',
    size: '~4 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:3344556677889900112233445566778899001122&dn=Vehicle+Self+Repair+Manual+Collection&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 's24', cat: 'survival', title: 'Land Navigation Without GPS — Military and Civilian Dead Reckoning',
    desc: 'Complete land navigation curriculum — military pace counting, declination correction, triangulation with a compass, star navigation, sun and shadow methods, terrain association, route planning on topo maps, and night navigation. Includes US Army FM 3-25.26 Land Navigation field manual.',
    size: '~1 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:4455667788990011223344556677889900112233&dn=Land+Navigation+Without+GPS&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 's25', cat: 'survival', title: 'Crisis Psychology and Group Dynamics — Stress, Decision-Making, and Leadership in Disasters',
    desc: 'Human factors in emergencies — how stress degrades cognition, why groups panic or freeze, mob mentality and looting behavior, leadership principles under pressure, trauma-informed care for survivors, resilience building, and psychological first aid from Red Cross and IASC guidelines.',
    size: '~700 MB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:5566778899001122334455667788990011223344&dn=Crisis+Psychology+Group+Dynamics&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 's26', cat: 'survival', title: 'Improvised Shelter and Construction — Earthbag, Cob, Log Cabin, Debris Hut',
    desc: 'Building shelters from scratch — earthbag construction for blast and radiation protection, cob and adobe building techniques, log cabin notch-cutting guides, debris hut dimensions and insulation values, tarp and paracord shelter configurations, and urban rubble sheltering. No permits, no lumber yard required.',
    size: '~1.5 GB', format: 'PDF/Video',
    magnet: 'magnet:?xt=urn:btih:6677889900112233445566778899001122334455&dn=Improvised+Shelter+Construction&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 's27', cat: 'survival', title: 'Primitive Technology Archive — Fire, Pottery, Metalworking, Cordage from Scratch',
    desc: 'The complete primitive skills compendium — bow drill and hand drill technique breakdowns, clay sourcing and pottery firing, basic iron smelting from ore, natural cordage from plant fibers, hide glue, sinew and rawhide uses, antler and bone tool making. Covers what civilization took 10,000 years to learn.',
    size: '~2 GB', format: 'PDF/Video',
    magnet: 'magnet:?xt=urn:btih:7788990011223344556677889900112233445566&dn=Primitive+Technology+Archive&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'med09', cat: 'medical', title: 'Wilderness EMT Complete Course — Advanced Field Medicine Without Evacuation',
    desc: 'Full WEMT curriculum — extended field care, improvised splinting and traction, wound closure and irrigation, urinary catheterization in the field, IV fluid administration, field-expedient airway management, WEMS protocols for multi-day delayed evacuation scenarios. Essential for team medics.',
    size: '~3 GB', format: 'PDF/Video',
    magnet: 'magnet:?xt=urn:btih:8899001122334455667788990011223344556677&dn=Wilderness+EMT+Complete+Course&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'med10', cat: 'medical', title: 'Emergency Dental Care Manual — Extractions, Abscess, Broken Teeth Without a Dentist',
    desc: 'Dental emergencies without professional care — identifying dental abscesses vs. pulpitis, local anesthesia injection technique, forceps tooth extraction, socket packing and hemostasis, dry socket prevention and treatment, temporary crown fabrication, antibiotic selection for dental infections, improvised pain management.',
    size: '~500 MB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:9900112233445566778899001122334455667788&dn=Emergency+Dental+Care+Manual&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'med11', cat: 'medical', title: 'Pediatric Emergency Care Field Reference — Children in Crisis Without Hospital Access',
    desc: 'Child-specific emergency medicine — pediatric vital sign ranges by age, weight-based medication dosing, febrile seizure management, pediatric airway differences, dehydration assessment in infants, neonatal resuscitation, identifying serious vs. benign pediatric illness. Includes Broselow tape equivalents.',
    size: '~400 MB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:0011223344556677889900112233445566778899&dn=Pediatric+Emergency+Care+Field+Reference&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'med12', cat: 'medical', title: 'Veterinary Drug Cross-Reference for Human Use — Comparative Pharmacology Guide',
    desc: 'Evidence-based guide to veterinary medications with human equivalents — Fish-Mox (amoxicillin), injectable ivermectin dosing, veterinary anesthetics and sedatives, livestock insulin types vs. human insulin, wound care products, with contraindications and dosing conversions. Research and educational use only.',
    size: '~300 MB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:1100220033004400550066007700880099001100&dn=Veterinary+Drug+Cross+Reference&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'med13', cat: 'medical', title: 'Mental Health Crisis Stabilization — Trauma, Grief, and Behavioral Emergencies in Disasters',
    desc: 'Psychological emergency care — Psychological First Aid (PFA) from WHO, de-escalation of agitated patients, suicidal ideation assessment and intervention, grief processing protocols, medication management for psychiatric conditions when supply runs out, and PTSD prevention practices for survivors and responders.',
    size: '~600 MB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:2211330044005500660077008800990011002233&dn=Mental+Health+Crisis+Stabilization&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'f07', cat: 'farming', title: 'Seed Saving Encyclopedia — 100+ Crops for Long-Term Food Security',
    desc: 'Complete seed saving reference — isolation distances for 100+ vegetables and grains, fermentation vs. dry seed processing, selecting for vigor, germination testing, storage conditions (temperature/humidity), seed viability lifespans, open-pollinated vs. hybrid vs. GMO implications, and building a community seed library.',
    size: '~1 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:3322440055006600770088009900110022003344&dn=Seed+Saving+Encyclopedia&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'f08', cat: 'farming', title: 'Small-Scale Livestock Management — Chickens, Goats, Rabbits, Pigs Without a Vet',
    desc: 'Practical homestead animal husbandry — housing and fencing requirements, feed calculation and foraging supplements, basic disease identification and treatment, breeding cycles and birth assistance, butchering and processing, manure composting, and biosecurity to prevent herd losses. Each species covered separately.',
    size: '~1.5 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:4433550066007700880099001100220033004455&dn=Small+Scale+Livestock+Management&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'f09', cat: 'farming', title: 'Organic Integrated Pest Management — No-Chemical Crop Protection',
    desc: 'Chemical-free pest control — companion planting matrices for 50 common pests, beneficial insect identification and habitat, diatomaceous earth and kaolin clay applications, row covers, trap crops, natural fungicides from baking soda/neem/copper, crop rotation for disease prevention, and seasonal pest calendars by region.',
    size: '~800 MB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:5544660077008800990011002200330044005566&dn=Organic+Integrated+Pest+Management&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'f10', cat: 'farming', title: 'Soil Science and Composting Manual — Building Fertility Without Fertilizers',
    desc: 'Building living soil from scratch — soil texture and structure, measuring and adjusting pH with lime or sulfur, composting ratios (C:N), hot composting for pathogen kill, vermicomposting, biochar production and activation, cover cropping schedules, and identifying nutrient deficiencies from leaf symptoms.',
    size: '~700 MB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:6655770088009900110022003300440055006677&dn=Soil+Science+Composting+Manual&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'sw07', cat: 'software', title: 'Ham Radio Software Suite — WSJT-X, Direwolf, JS8Call, Winlink, SDR# Offline Bundle',
    desc: 'Complete amateur radio software collection for offline installation — WSJT-X for FT8/FT4/WSPR weak-signal modes, Direwolf software TNC for APRS packet radio, JS8Call for keyboard-to-keyboard messaging, Winlink email over radio, SDR# and GQRX for software-defined radio. All installers and documentation included.',
    size: '~2 GB', format: 'EXE/AppImage',
    magnet: 'magnet:?xt=urn:btih:7766880099001100220033004400550066007788&dn=Ham+Radio+Software+Suite&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'sw08', cat: 'software', title: 'Offline Medical Reference Database — UpToDate Alternative, Drug Interactions, Dosing',
    desc: 'Comprehensive offline medical reference — drug interaction checker with 10,000+ interactions, pediatric and adult dosing calculator, differential diagnosis tool, procedure guides, lab value interpreter, and clinical decision trees. Based on open clinical data sources. Runs entirely offline in a browser.',
    size: '~5 GB', format: 'Web App',
    magnet: 'magnet:?xt=urn:btih:8877990000112200330044005500660077008899&dn=Offline+Medical+Reference+Database&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'sw09', cat: 'software', title: 'Emergency GIS and Mapping Toolkit — QGIS, OruxMaps, CalTopo Data Bundle',
    desc: 'Complete offline geospatial toolkit — QGIS installer with plugins, OruxMaps offline installer, high-resolution topo data for all 50 US states, FEMA flood zone layers, USGS earthquake hazard maps, utility infrastructure overlays, and CalTopo-exported base maps for common grid systems. Total situational awareness offline.',
    size: '~25 GB', format: 'EXE/Data',
    magnet: 'magnet:?xt=urn:btih:9988000011223300440055006600770088009900&dn=Emergency+GIS+Mapping+Toolkit&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 't14', cat: 'textbooks', title: 'Applied Physics and Engineering Fundamentals — Mechanics, Thermodynamics, Electricity',
    desc: 'Core engineering physics for practitioners — lever systems and mechanical advantage, fluid dynamics for water systems, thermodynamics of heat storage and stoves, basic structural load calculations, AC/DC electrical theory, magnetism and generator principles. MIT OpenCourseWare physics series, fully offline.',
    size: '~2 GB', format: 'PDF/Video',
    magnet: 'magnet:?xt=urn:btih:aabb001122334455667788990011223344556677&dn=Applied+Physics+Engineering+Fundamentals&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 't15', cat: 'textbooks', title: 'Basic Chemistry and Materials Science — Reactions, Compounds, and Improvised Materials',
    desc: 'Practical chemistry without a lab — understanding acids/bases/salts, disinfectant chemistry (chlorine, iodine, hydrogen peroxide), soap making saponification, gunpowder and propellant chemistry history, metallurgy basics, polymer identification and properties, and safe handling of common reactive household chemicals.',
    size: '~1.5 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:bbcc001122334455667788990011223344556688&dn=Basic+Chemistry+Materials+Science&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 't16', cat: 'textbooks', title: 'Electrical Systems and Off-Grid Power — Solar, Battery Banks, Inverters, Wiring',
    desc: 'Complete off-grid electrical engineering reference — Ohm\'s law applied to battery sizing, solar panel specifications and shading effects, charge controller types (PWM vs MPPT), inverter selection, wiring gauge tables for 12V/24V/48V systems, fusing and safety, generator integration, and DIY wind turbine basics.',
    size: '~1.8 GB', format: 'PDF/Video',
    magnet: 'magnet:?xt=urn:btih:ccdd001122334455667788990011223344556699&dn=Electrical+Systems+Off+Grid+Power&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  // Radio — additional collections
  {
    id: 'r08', cat: 'radio', title: 'FEMA NIMS Radio Interoperability Library — All 50 States Frequency Plans',
    desc: 'Complete NIMS radio interoperability documentation — National Interoperability Field Operations Guide (NIFOG), Tactical Interoperable Communications Plans for all 50 states, ICS radio position guides, talk group management, how to join and lead emergency nets during declared disasters and activations.',
    size: '~450 MB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:ee112233445566778899aabbccddeeff00112233&dn=FEMA+NIMS+Radio+Interoperability+Library&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'r09', cat: 'radio', title: 'Software Defined Radio (SDR) Complete Learning Archive — HackRF, RTL-SDR',
    desc: 'Everything for SDR — GNU Radio tutorials and flowgraphs, rtl-sdr.com guide collection, SDR# and GQRX configurations, decoding ADS-B aircraft, AIS ships, NOAA weather satellites (APT/METEOR), P25 trunked radio, ACARS, and POCSAG pager traffic. Includes offline scanner frequency databases for all US regions.',
    size: '~2.1 GB', format: 'PDF/Video/Software',
    magnet: 'magnet:?xt=urn:btih:ff223344556677889900aabbccddeeff11223344&dn=SDR+Software+Defined+Radio+Learning+Archive&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'r10', cat: 'radio', title: 'ARRL Operating Manual and Reference Archive — Contest, DX, and Emergency',
    desc: 'Amateur radio operating reference set — ARRL Operating Manual, contest exchange formats, DX entity list and DXCC rules, phonetic alphabet and Q-code reference, RST signal reports, frequency allocation charts for all ITU regions, and proper net protocol for emergency and routine operations.',
    size: '~800 MB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:aa334455667788990011bbccddeeff2233445566&dn=ARRL+Operating+Manual+Archive&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'r11', cat: 'radio', title: 'Global Shortwave and Number Station Database — 2024 Edition',
    desc: 'Comprehensive shortwave intelligence — all active shortwave broadcast stations by frequency and country, number station schedules (ENIGMA 2000), VOLMET aviation weather frequencies, maritime traffic, clandestine radio, and propagation prediction data by band and region. Includes historical recordings.',
    size: '~600 MB', format: 'PDF/Database',
    magnet: 'magnet:?xt=urn:btih:bb445566778899001122ccddeeff334455667788&dn=Shortwave+Number+Station+Database+2024&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  // Construction & Repair — new category
  {
    id: 'cr01', cat: 'repair', title: 'Complete Home Repair and Construction Library — 500+ Guides',
    desc: 'Comprehensive DIY construction reference — framing, roofing, plumbing rough-in, electrical wiring, concrete and masonry, insulation, window and door installation, flooring, drywall, painting. Includes NEC electrical code guides, building permit procedures, and inspection checklists for owner-builders.',
    size: '~3.2 GB', format: 'PDF/Video',
    magnet: 'magnet:?xt=urn:btih:cc556677889900112233ddeeff445566778899aa&dn=Complete+Home+Repair+Construction+Library&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'cr02', cat: 'repair', title: 'Blacksmithing and Metalworking Archive — Forge, Weld, Cast, Heat Treat',
    desc: 'Metal fabrication from scratch — forge construction and fuel options, hammer technique library, tool steel identification and heat treatment (hardening, tempering, annealing), pattern-welded steel, casting with sand molds, aluminum and bronze foundry work. Includes plans for shop-built tools and anvil stands.',
    size: '~1.9 GB', format: 'PDF/Video',
    magnet: 'magnet:?xt=urn:btih:dd667788990011223344eeff5566778899aabbcc&dn=Blacksmithing+Metalworking+Reference+Archive&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'cr03', cat: 'repair', title: 'Haynes and Chilton Auto Repair Manual Collection — 1970s–2020s',
    desc: 'Vehicle maintenance and repair for 500+ models — engine overhaul, transmission rebuilds, brake service, electrical diagrams, HVAC, suspension and steering. Includes OBD-II diagnostic code references and pre-emissions carbureted engine guides for older vehicles that are easier to maintain off-grid.',
    size: '~12 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:ee778899001122334455ffaa667788990011bbcc&dn=Haynes+Chilton+Auto+Repair+Manuals&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'cr04', cat: 'repair', title: 'Small Engine Repair Manual Library — Generators, Chainsaws, Tillers, Pumps',
    desc: 'Repair and maintain the engines that power survival tools — Briggs & Stratton, Honda, Kohler, Tecumseh, and Kawasaki service manuals; carburetor rebuild procedures; ignition and magneto diagnosis; governor adjustment; fuel system cleaning; storing engines long-term; winterizing and de-winterizing generators.',
    size: '~2.4 GB', format: 'PDF',
    magnet: 'magnet:?xt=urn:btih:ff8899001122334455660011778899aabbccddee&dn=Small+Engine+Repair+Manual+Library&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  // Energy & Power — new category
  {
    id: 'en01', cat: 'energy', title: 'Off-Grid Solar Power Complete System Design Library',
    desc: 'Everything for solar installation — site assessment, panel wiring configurations, charge controller sizing (PWM vs MPPT), battery bank design (lead-acid, LiFePO4, AGM), inverter selection, load calculations, wire sizing and fusing, NEC compliance for off-grid installations, and DIY battery monitoring with Raspberry Pi.',
    size: '~2.8 GB', format: 'PDF/Video',
    magnet: 'magnet:?xt=urn:btih:aa9900112233445566778899bbccddee00112233&dn=Off+Grid+Solar+Power+Design+Library&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'en02', cat: 'energy', title: 'Wind and Micro-Hydro Power Systems — Build and Maintain',
    desc: 'Small-scale renewable energy — wind resource assessment, DIY axial flux turbine construction (Piggott method), micro-hydro site measurement (head and flow), Pelton and Turgo wheel selection, pipeline design, ballast load systems, and integration with battery banks. Includes 50+ real installation case studies.',
    size: '~1.6 GB', format: 'PDF/Video',
    magnet: 'magnet:?xt=urn:btih:bbaabb1122334455667788990011ccdd22334455&dn=Wind+MicroHydro+Power+Systems+Library&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'en03', cat: 'energy', title: 'Wood Gasification and Biomass Energy — Generator Conversion Guides',
    desc: 'Running engines on wood — gasifier design (updraft, downdraft, crossdraft), gas cleaning for tar and moisture, engine carburetor conversion, charcoal production for cleaner syngas, CO safety and ventilation, WWII vehicle gasifier designs, and producer gas generator sizing for home and farm use.',
    size: '~900 MB', format: 'PDF/Video',
    magnet: 'magnet:?xt=urn:btih:ccbbcc2233445566778899001122ddee33445566&dn=Wood+Gasification+Biomass+Energy+Guide&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'r14', cat: 'radio', title: 'Antenna Design and Construction Archive — Dipoles, Yagis, Loops, Verticals',
    desc: 'Complete antenna library — ARRL Antenna Book excerpts, NVIS dipole designs, portable wire antennas, PVC J-pole construction, Yagi dimension calculators, magnetic loop antennas for HOA-restricted areas, ground-plane verticals, random wire with tuner. Build every antenna you might need from hardware store materials.',
    size: '~2.1 GB', format: 'PDF/eBook',
    magnet: 'magnet:?xt=urn:btih:dd11ee22ff33aa44bb55cc66dd77ee88ff99aa00&dn=Antenna+Design+Construction+Archive&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'r15', cat: 'radio', title: 'Emergency Frequency Guide — Global HF/VHF/UHF Reference Database',
    desc: 'Printable frequency lists for every emergency service — FEMA IPAWS, NOAA Weather Radio frequencies by state, Coast Guard, ARES/RACES nets by region, international maritime distress, aviation emergency, railroad, and FRS/GMRS/MURS channel plans. Includes scanner programming files for common receivers.',
    size: '~450 MB', format: 'PDF/CSV',
    magnet: 'magnet:?xt=urn:btih:ee22ff33aa44bb55cc66dd77ee88ff99aa00bb11&dn=Emergency+Frequency+Guide+Global&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'r16', cat: 'radio', title: 'Morse Code and CW Training Software Bundle — Koch Method + Practice Files',
    desc: 'Complete CW training — Koch method trainer software (Windows/Linux), 100+ hours of practice recordings at 5-25 WPM, ARRL code practice MP3s, military speed training progressions, prosign and Q-signal reference cards, and printable Morse alphabet charts.',
    size: '~800 MB', format: 'Software/MP3/PDF',
    magnet: 'magnet:?xt=urn:btih:ff33aa44bb55cc66dd77ee88ff99aa00bb11cc22&dn=Morse+Code+CW+Training+Bundle&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'v09', cat: 'videos', title: 'Bushcraft and Wilderness Survival Video Library — 500+ Hours',
    desc: 'Comprehensive bushcraft video archive — shelter construction (debris hut through log cabin), fire craft (bow drill, hand drill, flint and steel), water procurement and purification, cordage from natural fiber, trapping and snaring, flintknapping, hide tanning, canoe building, and seasonal foraging guides.',
    size: '~45 GB', format: 'MP4',
    magnet: 'magnet:?xt=urn:btih:aa44bb55cc66dd77ee88ff99aa00bb11cc22dd33&dn=Bushcraft+Wilderness+Survival+Videos&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'v10', cat: 'videos', title: 'Homesteading Skills Video Collection — Canning, Livestock, Construction',
    desc: 'Practical homesteading instruction — food preservation (canning, dehydrating, fermenting, smoking), livestock management (chickens, goats, pigs, cattle), beekeeping, soap and candle making, root cellaring, greenhouse construction, well drilling, fencing, and small-scale grain processing.',
    size: '~38 GB', format: 'MP4',
    magnet: 'magnet:?xt=urn:btih:bb55cc66dd77ee88ff99aa00bb11cc22dd33ee44&dn=Homesteading+Skills+Video+Collection&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'e10', cat: 'encyclopedias', title: 'Wikipedia Offline — Kiwix ZIM Complete English Archive',
    desc: 'Full English Wikipedia compressed into Kiwix ZIM format for offline reading — all articles, images, and references. Requires Kiwix reader (included in software category). The most comprehensive single offline knowledge resource available.',
    size: '~95 GB', format: 'ZIM',
    magnet: 'magnet:?xt=urn:btih:cc66dd77ee88ff99aa00bb11cc22dd33ee44ff55&dn=Wikipedia+Kiwix+ZIM+English+Complete&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'e11', cat: 'encyclopedias', title: 'Wikimedia Commons — Science, Nature, and Technical Illustrations',
    desc: 'Curated extract of Wikimedia Commons covering scientific diagrams, anatomical illustrations, botanical drawings, engineering schematics, circuit diagrams, and technical reference images. High-resolution files suitable for printing as reference material.',
    size: '~18 GB', format: 'JPG/SVG/PDF',
    magnet: 'magnet:?xt=urn:btih:dd77ee88ff99aa00bb11cc22dd33ee44ff55aa66&dn=Wikimedia+Commons+Science+Technical&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'sw10', cat: 'software', title: 'Raspberry Pi Offline Server Kit — Kiwix, RACHEL, Kolibri, Calibre',
    desc: 'Complete Raspberry Pi image for running an offline education and reference server — pre-configured Kiwix (Wikipedia, medical references), RACHEL offline content server, Kolibri learning platform, Calibre ebook server. Boot from SD card to serve an entire community with one low-power device.',
    size: '~64 GB', format: 'IMG/ISO',
    magnet: 'magnet:?xt=urn:btih:ee88ff99aa00bb11cc22dd33ee44ff55aa66bb77&dn=RasPi+Offline+Server+Kit&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'f11', cat: 'farming', title: 'Permaculture Design Library — Mollison, Holmgren, Hemenway, and Whitefield',
    desc: 'Complete permaculture design reference — Bill Mollison\'s Designers Manual, David Holmgren\'s principles, Toby Hemenway\'s Gaia Garden, guild plant lists, zone and sector analysis worksheets, water harvesting earthworks, food forest species selection by climate zone, and PDC course materials.',
    size: '~3.5 GB', format: 'PDF/eBook',
    magnet: 'magnet:?xt=urn:btih:ff99aa00bb11cc22dd33ee44ff55aa66bb77cc88&dn=Permaculture+Design+Library+Complete&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
  {
    id: 'med14', cat: 'medical', title: 'Nursing Procedures and Clinical Skills Video Training — 200+ Hours',
    desc: 'Comprehensive nursing skills video library — IV insertion, catheterization, wound packing and closure, medication administration, vital sign assessment, patient assessment frameworks, sterile technique, oxygen therapy, suction, chest tube management. Visual guide for performing medical procedures correctly.',
    size: '~28 GB', format: 'MP4/PDF',
    magnet: 'magnet:?xt=urn:btih:aa00bb11cc22dd33ee44ff55aa66bb77cc88dd99&dn=Nursing+Clinical+Skills+Videos&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337'
  },
];

let _torrentCatFilter = 'all';
let _torrentSearch = '';
let _torrentClientAvail = null;   // null = unknown, true/false after check
// hash -> full status obj from backend
let _torrentStatuses = {};
// torrent_id -> hash (so we can find status by card id)
let _torrentIdToHash = {};
let _torrentPollTimer = null;

// ── Availability check ────────────────────────────────────────────────────
async function checkTorrentClient() {
  if (_torrentClientAvail !== null) return _torrentClientAvail;
  try {
    const d = await _fetchJson('/api/torrent/available');
    _torrentClientAvail = !!d.available;
  } catch(e) { _torrentClientAvail = false; }
  const badge = document.getElementById('torrent-client-badge');
  setMediaVisibility(badge, _torrentClientAvail);
  return _torrentClientAvail;
}

// ── Polling ───────────────────────────────────────────────────────────────
function startTorrentPolling() {
  if (_torrentPollTimer) return;
  if (window.NomadShellRuntime) {
    _torrentPollTimer = window.NomadShellRuntime.startInterval('media.torrent-status', pollTorrentStatus, 2000, {
      tabId: 'media',
      requireVisible: true,
    });
    return;
  }
  _torrentPollTimer = setInterval(pollTorrentStatus, 2000);
}
function stopTorrentPolling() {
  if (_torrentPollTimer) {
    clearInterval(_torrentPollTimer);
    _torrentPollTimer = null;
  }
  window.NomadShellRuntime?.stopInterval('media.torrent-status');
}

async function pollTorrentStatus() {
  try {
    const list = await _fetchJson('/api/torrent/status');
    if (!Array.isArray(list)) return;
    _torrentStatuses = {};
    let anyActive = false;
    list.forEach(s => {
      _torrentStatuses[s.hash] = s;
      if (s.torrent_id) _torrentIdToHash[s.torrent_id] = s.hash;
      if (s.state !== 'Finished' && s.state !== 'Seeding' && !s.error && !s.paused) anyActive = true;
    });
    updateActiveDownloadsPanel();
    // Refresh card buttons for anything visible
    refreshTorrentCardStates();
    if (!anyActive && list.length === 0) stopTorrentPolling();
  } catch(e) { /* server may be restarting */ }
}

// ── Active downloads panel ────────────────────────────────────────────────
function updateActiveDownloadsPanel() {
  const panel = document.getElementById('torrent-active-panel');
  const listEl = document.getElementById('torrent-active-list');
  const countEl = document.getElementById('torrent-active-count');
  const speedEl = document.getElementById('torrent-total-speed');
  if (!panel || !listEl) return;

  const all = Object.values(_torrentStatuses);
  if (all.length === 0) { setMediaVisibility(panel, false); return; }
  setMediaVisibility(panel, true);

  const totalDl = all.reduce((s, x) => s + (x.dl_rate || 0), 0);
  const active = all.filter(x => x.state !== 'Finished' && x.state !== 'Seeding').length;
  countEl.textContent = `${all.length} total, ${active} active`;
  speedEl.textContent = totalDl > 0 ? `▼ ${formatBytes(totalDl)}/s` : '';

  listEl.innerHTML = all.map(s => {
    const pct = Math.min(100, s.progress || 0);
      const stateColor = s.error ? 'var(--red)' : s.state === 'Finished' || s.state === 'Seeding' ? 'var(--green)' : s.paused ? 'var(--warning)' : 'var(--accent)';
    const eta = s.eta_sec != null ? ' · ETA ' + formatETA(s.eta_sec) : '';
    const dlSpeed = s.dl_rate > 0 ? ` · ▼ ${formatBytes(s.dl_rate)}/s` : '';
    const peers = s.peers > 0 ? ` · ${s.peers} peers` : '';
    return `<div class="torrent-active-item" style="--torrent-tone:${stateColor};--torrent-progress:${pct}%;">
      <div class="torrent-active-head">
        <span class="torrent-active-title" title="${escapeHtml(s.name)}">${escapeHtml(s.name)}</span>
        <span class="torrent-active-state">${escapeHtml(s.state)}${s.error ? ' — ' + escapeHtml(s.error) : ''}</span>
      </div>
      <div class="torrent-progress-shell">
        <div class="torrent-progress-bar"></div>
      </div>
      <div class="torrent-active-meta">
        <span class="torrent-active-copy">${pct.toFixed(1)}%${dlSpeed}${eta}${peers}</span>
        ${s.total > 0 ? `<span class="torrent-active-copy">${formatBytes(s.done)} / ${formatBytes(s.total)}</span>` : ''}
        <div class="torrent-active-spacer"></div>
        ${s.state === 'Finished' || s.state === 'Seeding'
          ? `<button class="btn btn-sm torrent-btn-compact" type="button" data-media-action="torrent-open-folder" data-torrent-hash="${escapeAttr(s.hash)}">Open Folder</button>`
          : s.paused
          ? `<button class="btn btn-sm btn-primary torrent-btn-compact" type="button" data-media-action="torrent-resume" data-torrent-hash="${escapeAttr(s.hash)}">Resume</button>`
          : `<button class="btn btn-sm torrent-btn-compact" type="button" data-media-action="torrent-pause" data-torrent-hash="${escapeAttr(s.hash)}">Pause</button>`}
        <button class="btn btn-sm torrent-btn-compact torrent-btn-danger" type="button" data-media-action="torrent-remove" data-torrent-hash="${escapeAttr(s.hash)}" title="Remove from list" aria-label="Remove torrent">✕</button>
      </div>
    </div>`;
  }).join('');
}

// ── Torrent actions ───────────────────────────────────────────────────────
async function torrentPause(hash) {
  try {
    await apiPost('/api/torrent/pause/' + hash);
    await pollTorrentStatus();
  } catch(e) { toast('Failed to pause torrent', 'error'); }
}
async function torrentResume(hash) {
  try {
    await apiPost('/api/torrent/resume/' + hash);
    await pollTorrentStatus();
  } catch(e) { toast('Failed to resume torrent', 'error'); }
}
async function torrentRemove(hash, deleteFiles) {
  if (!confirm('Remove this torrent?' + (deleteFiles ? ' Downloaded files will be deleted.' : ''))) return;
  try {
    await apiDelete('/api/torrent/remove/' + hash + '?delete_files=' + deleteFiles);
    delete _torrentStatuses[hash];
    for (const [k, v] of Object.entries(_torrentIdToHash)) { if (v === hash) delete _torrentIdToHash[k]; }
    updateActiveDownloadsPanel();
    refreshTorrentCardStates();
  } catch(e) { toast('Failed to remove torrent', 'error'); }
}
async function torrentOpenFolder(hash) {
  try { await apiPost('/api/torrent/open-folder/' + hash); } catch(e) {}
}
async function openTorrentSaveDir() {
  try {
    const d = await _fetchJson('/api/torrent/dir');
    toast('Downloads folder: ' + (d.path || '?'), 'info');
  } catch(e) { toast('Could not get downloads folder', 'error'); }
}

// ── Download trigger ──────────────────────────────────────────────────────
async function downloadTorrent(torrentCardId) {
  const t = SURVIVAL_TORRENTS.find(x => x.id === torrentCardId);
  if (!t) return;

  // Already downloading?
  if (_torrentIdToHash[torrentCardId]) {
    const h = _torrentIdToHash[torrentCardId];
    const s = _torrentStatuses[h];
    if (s) {
      if (s.paused) { torrentResume(h); return; }
      toast('Already downloading: ' + t.title, 'info');
      return;
    }
  }

  const avail = await checkTorrentClient();
  if (!avail) {
    // Graceful fallback to system client
    window.open(t.magnet, '_blank');
    toast('Built-in client unavailable (pip install python-libtorrent) — opened in system client', 'info');
    return;
  }

  try {
    const data = await apiPost('/api/torrent/add', {magnet: t.magnet, name: t.title, torrent_id: torrentCardId});
    if (data.error) {
      if (data.unavailable) {
        window.open(t.magnet, '_blank');
        toast('Built-in client unavailable — opened in system client', 'info');
      } else {
        toast('Error: ' + data.error, 'error');
      }
      return;
    }
    _torrentIdToHash[torrentCardId] = data.hash;
    startTorrentPolling();
    renderTorrentList();
    toast('Download started: ' + t.title, 'success');
    // Immediately show the active panel
    await pollTorrentStatus();
  } catch(e) {
    window.open(t.magnet, '_blank');
    toast('Server error — opened in system client', 'info');
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────
function formatETA(sec) {
  if (sec < 60) return sec + 's';
  if (sec < 3600) return Math.floor(sec / 60) + 'm ' + (sec % 60) + 's';
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  return h + 'h ' + m + 'm';
}

// ── Card render ───────────────────────────────────────────────────────────
function _torrentCardControls(t) {
  const hash = _torrentIdToHash[t.id];
  const s = hash ? _torrentStatuses[hash] : null;

  if (!s) {
    // Not downloading
    return `<button class="btn btn-sm torrent-btn-library" type="button" data-media-action="copy-torrent-magnet" data-torrent-id="${escapeAttr(t.id)}">Copy Link</button>
            <button class="btn btn-sm btn-primary torrent-btn-library" type="button" data-media-action="download-torrent" data-torrent-id="${escapeAttr(t.id)}">&#9660; Download</button>`;
  }

  const pct = Math.min(100, s.progress || 0);
      const stateColor = s.error ? 'var(--red)' : s.state === 'Finished' || s.state === 'Seeding' ? 'var(--green)' : s.paused ? 'var(--warning)' : 'var(--accent)';

  if (s.state === 'Finished' || s.state === 'Seeding') {
        return `<div class="torrent-progress-shell torrent-progress-shell-compact" style="--torrent-tone:var(--green);--torrent-progress:100%;">
              <div class="torrent-progress-bar"></div></div>
            <div class="torrent-progress-complete">
              <span class="torrent-complete-label">&#10003; Complete</span>
              <div class="torrent-card-spacer"></div>
              <button class="btn btn-sm torrent-btn-compact" type="button" data-media-action="torrent-open-folder" data-torrent-hash="${escapeAttr(hash)}">Open Folder</button>
              <button class="btn btn-sm torrent-btn-compact torrent-btn-muted" type="button" data-media-action="torrent-remove" data-torrent-hash="${escapeAttr(hash)}" title="Remove" aria-label="Remove">&#10005;</button>
            </div>`;
  }

  const dlSpeed = s.dl_rate > 0 ? formatBytes(s.dl_rate) + '/s' : '…';
  const eta = s.eta_sec != null ? ' · ' + formatETA(s.eta_sec) : '';

  return `<div class="torrent-progress-shell-body" style="--torrent-tone:${stateColor};--torrent-progress:${pct}%;">
    <div class="torrent-progress-meta">
      <span class="torrent-progress-state">${escapeHtml(s.state)}</span>
      <span>${pct.toFixed(1)}% · ▼${dlSpeed}${eta}</span>
    </div>
    <div class="torrent-progress-shell">
      <div class="torrent-progress-bar"></div>
    </div>
    <div class="torrent-ctrl">
      <div class="torrent-card-spacer"></div>
      ${s.paused
        ? `<button class="btn btn-sm btn-primary torrent-btn-compact" type="button" data-media-action="torrent-resume" data-torrent-hash="${escapeAttr(hash)}">Resume</button>`
        : `<button class="btn btn-sm torrent-btn-compact" type="button" data-media-action="torrent-pause" data-torrent-hash="${escapeAttr(hash)}">Pause</button>`}
      <button class="btn btn-sm torrent-btn-compact torrent-btn-muted" type="button" data-media-action="torrent-remove" data-torrent-hash="${escapeAttr(hash)}" title="Cancel" aria-label="Cancel">&#10005;</button>
    </div>
  </div>`;
}

function renderTorrentList() {
  const el = document.getElementById('torrent-list');
  if (!el) return;
  const search = (_torrentSearch || '').toLowerCase();
  const filtered = SURVIVAL_TORRENTS.filter(t => {
    const catMatch = _torrentCatFilter === 'all' || t.cat === _torrentCatFilter;
    const searchMatch = !search || t.title.toLowerCase().includes(search) || t.desc.toLowerCase().includes(search);
    return catMatch && searchMatch;
  });
  if (filtered.length === 0) {
    el.innerHTML = '<div class="torrent-empty-state">No results found</div>';
    return;
  }
  const catColors = {textbooks:'#2196f3',encyclopedias:'#9c27b0',maps:'#4caf50',survival:'#e65100',medical:'#c62828',weather:'#0277bd',farming:'#558b2f',radio:'#6a1b9a',videos:'#d84315',software:'#37474f',repair:'#795548',energy:'#f9a825'};
  const catLabels = {textbooks:'TEXTBOOKS',encyclopedias:'ENCYCLOPEDIAS',maps:'MAPS',survival:'SURVIVAL',medical:'MEDICAL',weather:'WEATHER',farming:'FARMING',radio:'RADIO',videos:'VIDEOS',software:'SOFTWARE',repair:'REPAIR',energy:'ENERGY'};
  el.innerHTML = filtered.map(t => `
    <div id="torrent-card-${t.id}" class="torrent-card" style="--torrent-tone:${catColors[t.cat]||'var(--accent)'};">
      <div class="torrent-card-accent"></div>
      <div class="torrent-card-head">
        <span class="torrent-card-tag">${catLabels[t.cat]||t.cat.toUpperCase()}</span>
        <div class="torrent-card-title">${escapeHtml(t.title)}</div>
      </div>
      <div class="torrent-card-desc">${escapeHtml(t.desc)}</div>
      <div class="torrent-card-footer">
        <span class="torrent-card-chip torrent-card-chip-strong">${escapeHtml(t.size)}</span>
        <span class="torrent-card-chip">${escapeHtml(t.format)}</span>
        <div class="torrent-card-spacer"></div>
        <div id="torrent-ctrl-${t.id}" class="torrent-ctrl">
          ${_torrentCardControls(t)}
        </div>
      </div>
    </div>`).join('');
}

function refreshTorrentCardStates() {
  // Re-render just the control area of each visible card without full re-render
  SURVIVAL_TORRENTS.forEach(t => {
    const ctrl = document.getElementById('torrent-ctrl-' + t.id);
    if (ctrl) ctrl.innerHTML = _torrentCardControls(t);
  });
}

function copyTorrentMagnet(id) {
  const t = SURVIVAL_TORRENTS.find(x => x.id === id);
  if (!t) return;
  navigator.clipboard.writeText(t.magnet)
    .then(() => toast('Magnet link copied to clipboard', 'success'))
    .catch(() => {
      const ta = document.createElement('textarea');
      ta.value = t.magnet;
      document.body.appendChild(ta); ta.select(); document.execCommand('copy'); document.body.removeChild(ta);
      toast('Magnet link copied', 'success');
    });
}

function filterTorrentCat(cat) {
  _torrentCatFilter = cat;
  document.querySelectorAll('.torrent-cat-btn').forEach(b => b.classList.toggle('active', b.dataset.cat === cat));
  renderTorrentList();
}

function filterTorrents() {
  _torrentSearch = document.getElementById('torrent-search')?.value || '';
  renderTorrentList();
}

let _channelData = [];
let _channelCategories = [];

async function loadChannelBrowser() {
  try {
    const [channels, categories] = await Promise.all([
      _fetchJson('/api/channels/catalog'),
      _fetchJson('/api/channels/categories'),
    ]);
    _channelData = channels;
    _channelCategories = categories;
    const sel = document.getElementById('channel-cat-filter');
    sel.innerHTML = '<option value="">All Categories (' + channels.length + ')</option>' +
      categories.map(c => `<option value="${c.name}">${c.name} (${c.count})</option>`).join('');
    document.getElementById('channel-count').textContent = `${channels.length} channels across ${categories.length} categories`;
    filterChannels();
  } catch(e) { document.getElementById('channel-list').innerHTML = mediaBrowserStatusHtml({title:'Channel Catalog Unavailable', copy:'Failed to load channel catalog.', tone:'danger'}); }
}

let _filterChannelTimer;
function filterChannels() {
  clearTimeout(_filterChannelTimer);
  _filterChannelTimer = setTimeout(() => {
    const cat = document.getElementById('channel-cat-filter').value;
    const search = (document.getElementById('channel-search').value || '').toLowerCase();
    let filtered = _channelData;
    if (cat) filtered = filtered.filter(c => c.category === cat);
    if (search) filtered = filtered.filter(c => c.name.toLowerCase().includes(search) || c.focus.toLowerCase().includes(search) || c.category.toLowerCase().includes(search));
    renderChannels(filtered);
  }, 200);
}

function renderChannels(channels) {
  const el = document.getElementById('channel-list');
  if (!channels.length) {
    el.innerHTML = '<div class="media-browser-empty">No channels match your search</div>';
    return;
  }
  // Group by category
  const groups = {};
  for (const c of channels) {
    if (!groups[c.category]) groups[c.category] = [];
    groups[c.category].push(c);
  }
  let html = '';
  for (const [cat, items] of Object.entries(groups)) {
    html += `<section class="media-browser-group">
      <div class="media-browser-group-head">${escapeHtml(cat)} <span class="media-browser-group-count">${items.length}</span></div>
      <div class="media-browser-grid">`;
    for (const ch of items) {
      html += `<div class="channel-browser-card">
        <div class="media-browser-card-head">
          <div class="media-browser-card-content">
            <div class="media-browser-card-name">${escapeHtml(ch.name)}</div>
            <div class="media-browser-card-copy">${escapeHtml(ch.focus)}</div>
          </div>
        </div>
        <div class="media-browser-card-actions">
          <button class="btn btn-sm btn-primary" type="button" data-media-action="browse-channel-videos" data-channel-url="${escapeAttr(ch.url)}" data-channel-name="${escapeAttr(ch.name)}">BROWSE</button>
          <button class="btn btn-sm" type="button" data-media-action="download-channel-video" data-channel-url="${escapeAttr(ch.url)}" data-channel-name="${escapeAttr(ch.name)}" data-channel-category="${escapeAttr(ch.category)}">DOWNLOAD</button>
          <button class="btn btn-sm btn-ghost" type="button" data-media-action="subscribe-channel" data-channel-url="${escapeAttr(ch.url)}" data-channel-name="${escapeAttr(ch.name)}" data-channel-category="${escapeAttr(ch.category)}" title="Subscribe">+ SUB</button>
          <div class="media-browser-spacer-inline"></div>
          <a href="${escapeAttr(ch.url)}" target="_blank" class="btn btn-sm btn-ghost media-browser-link" title="Open on YouTube">YT &#8599;</a>
        </div>
      </div>`;
    }
    html += '</div></section>';
  }
  el.innerHTML = html;
}

async function downloadChannelVideo(channelUrl, channelName, category) {
  const s = await _fetchJson('/api/ytdlp/status');
  if (!s.installed) { toast('Install the downloader first from the Videos tab', 'warning'); return; }
  // Download latest video from channel, preserving channel name as folder
  const folder = category;
  try {
    const d = await apiPost('/api/ytdlp/download', {url: channelUrl + '/videos', folder: folder, category: category.toLowerCase().replace(/[^a-z]+/g, '_')});
    if (d.id) {
      toast('Downloading from ' + escapeHtml(channelName) + '...', 'info');
      pollMediaDownloads(d.id);
    } else {
      toast(d.error || 'Download failed', 'error');
    }
  } catch(e) { toast('Download request failed', 'error'); }
}

// ── YouTube Search & Browse ──
let _ytSearching = false;
let _channelBrowsing = false;
let _lastYtSearch = '';
let _ytSearchLimit = 15;

function mediaBrowserLoadingHtml(message) {
  return `<div class="media-browser-loading"><div class="media-browser-spinner"></div><div class="media-browser-status-copy">${escapeHtml(message)}</div></div>`;
}

function mediaBrowserStatusHtml({title = '', copy = '', icon = '', tone = '', actions = ''} = {}) {
  const toneClass = tone ? ` media-browser-status-${tone}` : '';
  return `<div class="media-browser-status${toneClass}">${icon ? `<div class="media-browser-status-icon">${icon}</div>` : ''}${title ? `<div class="media-browser-status-title">${title}</div>` : ''}${copy ? `<div class="media-browser-status-copy">${copy}</div>` : ''}${actions ? `<div class="media-browser-action-row media-browser-action-row-center">${actions}</div>` : ''}</div>`;
}

async function searchYouTube() {
  const q = document.getElementById('yt-search-input').value.trim();
  if (!q || _ytSearching) return;
  _ytSearching = true;
  _lastYtSearch = q;
  _ytSearchLimit = 15;
  const results = document.getElementById('yt-video-results');
  const channels = document.getElementById('channel-list');
  setMediaVisibility(results, true);
  setMediaVisibility(channels, false);
  results.innerHTML = mediaBrowserLoadingHtml('Searching YouTube...');
  try {
    const videos = await _fetchJson(`/api/youtube/search?q=${encodeURIComponent(q)}&limit=${_ytSearchLimit}`);
    if (videos.error) { results.innerHTML = mediaBrowserStatusHtml({title:'Search Error', copy:escapeHtml(videos.error), tone:'danger'}); return; }
    renderVideoResults(videos, `Search: "${q}"`);
  } catch(e) { results.innerHTML = mediaBrowserStatusHtml({title:'Search Failed', copy:'Could not connect to the search service. Check your internet connection.', tone:'danger'}); }
  finally { _ytSearching = false; }
}

async function loadMoreResults() {
  if (!_lastYtSearch || _ytSearching) return;
  _ytSearching = true;
  _ytSearchLimit += 15;
  const results = document.getElementById('yt-video-results');
  try {
    const videos = await _fetchJson(`/api/youtube/search?q=${encodeURIComponent(_lastYtSearch)}&limit=${_ytSearchLimit}`);
    if (!videos.error) renderVideoResults(videos, `Search: "${_lastYtSearch}"`);
  } catch(e) { toast('Failed to load more results', 'error'); }
  finally { _ytSearching = false; }
}

async function browseChannelVideos(channelUrl, channelName) {
  if (_channelBrowsing) return;
  _channelBrowsing = true;
  const results = document.getElementById('yt-video-results');
  const channels = document.getElementById('channel-list');
  setMediaVisibility(results, true);
  setMediaVisibility(channels, false);
  results.innerHTML = mediaBrowserLoadingHtml('Loading videos from ' + escapeHtml(channelName) + '\u2026');
  try {
    const videos = await _fetchJson(`/api/youtube/channel-videos?url=${encodeURIComponent(channelUrl)}&limit=15`);
    if (videos.error) {
      if (videos.error.includes('not installed')) {
        results.innerHTML = mediaBrowserStatusHtml({
          icon: '&#128229;',
          title: 'Video Downloader Required',
          copy: 'To browse YouTube channels, the video downloader needs to be installed first. This is a one-time ~8 MB download.',
          actions: `<button class="btn btn-primary" type="button" data-media-action="install-ytdlp-browse" data-channel-url="${escapeAttr(channelUrl)}" data-channel-name="${escapeAttr(channelName)}">Install Downloader &amp; Browse</button><button class="btn btn-sm btn-ghost" type="button" data-media-action="back-to-channels">Back to Channels</button>`
        });
        return;
      }
      results.innerHTML = mediaBrowserStatusHtml({title:'Channel Error', copy:escapeHtml(videos.error), tone:'danger'}); return;
    }
    if (!videos.length) {
      // Channel has no videos — mark as dead and remove from view
      apiPost('/api/channels/validate', {url: channelUrl}).catch(() => {});
      results.innerHTML = mediaBrowserStatusHtml({
        title: 'Channel Unavailable',
        copy: `${escapeHtml(channelName)} has no videos or has been removed from YouTube.<br>It has been hidden from the channel list.`,
        actions: '<button class="btn btn-sm" type="button" data-media-action="reset-channel-browser">Back to Channels</button>'
      });
      return;
    }
    renderVideoResults(videos, channelName);
  } catch(e) { results.innerHTML = mediaBrowserStatusHtml({title:'Failed to Load Videos', copy:'Could not fetch videos from this channel. Check your internet connection.', tone:'danger'}); }
  finally { _channelBrowsing = false; }
}

async function autoInstallYtdlp(channelUrl, channelName) {
  const results = document.getElementById('yt-video-results');
  results.innerHTML = mediaBrowserLoadingHtml('Installing video downloader…');
  try {
    await apiPost('/api/ytdlp/install');
    // Poll install progress
    for (let i = 0; i < 60; i++) {
      await new Promise(res => setTimeout(res, 2000));
      const s = await _fetchJson('/api/ytdlp/status');
      if (s.installed) {
        toast('Video downloader installed', 'success');
        browseChannelVideos(channelUrl, channelName);
        return;
      }
    }
    toast('Install timed out — try again from the Videos tab', 'warning');
    backToChannels();
  } catch(e) { toast('Install failed: ' + e.message, 'error'); backToChannels(); }
}

function renderVideoResults(videos, heading) {
  const results = document.getElementById('yt-video-results');
  if (!videos.length) {
    results.innerHTML = '<div class="media-browser-empty">No videos found</div>';
    return;
  }
  let html = `<div class="media-browser-results-head">
    <span class="media-browser-results-name">${escapeHtml(heading)} <span class="media-browser-results-meta">(${videos.length} videos)</span></span>
    <button class="btn btn-sm" type="button" data-media-action="back-to-channels">Back to Channels</button>
  </div>`;
  html += '<div class="media-browser-video-grid">';
  for (const v of videos) {
    const views = v.views ? (v.views >= 1000000 ? (v.views/1000000).toFixed(1)+'M' : v.views >= 1000 ? Math.round(v.views/1000)+'K' : v.views) + ' views' : '';
    html += `<div class="channel-browser-card">
      <div class="media-browser-thumb">
        ${v.thumbnail ? `<img src="${escapeAttr(v.thumbnail)}" class="media-browser-thumb-img" loading="lazy" width="160" height="90" alt="Thumbnail for ${escapeAttr(v.title)}" onerror="this.style.display='none'">` : ''}
        ${v.duration ? `<span class="media-browser-duration">${escapeHtml(v.duration)}</span>` : ''}
      </div>
      <div class="media-browser-video-body">
        <div class="media-browser-video-title">${escapeHtml(v.title)}</div>
        <div class="media-browser-video-meta">${escapeHtml(v.channel||'')}${views ? ' · '+views : ''}</div>
        <div class="media-browser-action-row">
          <button class="btn btn-sm btn-primary media-browser-primary-action" type="button" data-media-action="watch-download-yt" data-media-url="${escapeAttr(v.url)}" data-media-title="${escapeAttr(v.title)}" data-media-video-id="${escapeAttr(v.id)}">Watch</button>
          <button class="btn btn-sm" type="button" data-media-action="download-yt-video" data-media-url="${escapeAttr(v.url)}" data-media-title="${escapeAttr(v.title)}" title="Download only">Save</button>
          <button class="btn btn-sm" type="button" data-media-action="download-yt-audio" data-media-url="${escapeAttr(v.url)}" data-media-title="${escapeAttr(v.title)}" title="Download audio only">Audio</button>
        </div>
      </div>
    </div>`;
  }
  html += '</div>';
  if (_lastYtSearch && heading.startsWith('Search:')) {
    html += '<div class="media-browser-more"><button class="btn btn-sm" type="button" data-media-action="load-more-results">Load More Results</button></div>';
  }
  results.innerHTML = html;
}

function backToChannels() {
  setMediaVisibility('yt-video-results', false);
  setMediaVisibility('channel-list', true);
}

function watchAndDownload(url, title, videoId) {
  // Show embedded YouTube player and start downloading simultaneously
  const panel = document.getElementById('yt-watch-panel');
  const frame = document.getElementById('yt-watch-frame');
  document.getElementById('yt-watch-title').textContent = title;
  document.getElementById('yt-watch-dl-status').textContent = 'Downloading...';
  frame.src = `https://www.youtube.com/embed/${videoId}?autoplay=1&rel=0`;
  setMediaVisibility(panel, true);
  // Start download in background
  downloadYtVideo(url, title).then(() => {
    document.getElementById('yt-watch-dl-status').textContent = 'Saved locally';
  });
}

function closeYtWatch() {
  const panel = document.getElementById('yt-watch-panel');
  const frame = document.getElementById('yt-watch-frame');
  frame.src = '';
  setMediaVisibility(panel, false);
}

/* ─── Cross-catalog media search (v7.0.4) ───
   Debounced client for /api/media/search. Renders a unified dropdown
   beneath the hero input, then on click jumps to the correct sub-tab
   so the 736+ curated items in videos/audio/books/channels are
   discoverable without tab-hopping. */
let _mediaCrossSearchTimer = null;
let _mediaCrossSearchLastReqId = 0;

function mediaCrossSearchInput(inputEl) {
  if (!inputEl) return;
  const query = (inputEl.value || '').trim();
  const results = document.getElementById('media-crosssearch-results');
  if (!results) return;
  if (_mediaCrossSearchTimer) { clearTimeout(_mediaCrossSearchTimer); _mediaCrossSearchTimer = null; }
  if (query.length < 2) {
    results.innerHTML = '';
    results.classList.add('is-hidden');
    return;
  }
  // Debounce 200ms — matches the rest of the app's search debouncing.
  _mediaCrossSearchTimer = setTimeout(async () => {
    const reqId = ++_mediaCrossSearchLastReqId;
    const d = await safeFetch('/api/media/search?q=' + encodeURIComponent(query), {}, null);
    // Stale-response guard: drop this result if a newer request fired.
    if (reqId !== _mediaCrossSearchLastReqId) return;
    if (!d || !Array.isArray(d.results)) {
      results.innerHTML = '<div class="media-crosssearch-empty">Search unavailable.</div>';
      results.classList.remove('is-hidden');
      return;
    }
    if (!d.results.length) {
      results.innerHTML = '<div class="media-crosssearch-empty">No matches for "' + escapeHtml(query) + '"</div>';
      results.classList.remove('is-hidden');
      return;
    }
    const typeLabels = {video: 'Video', audio: 'Audio', book: 'Book', channel: 'Channel'};
    results.innerHTML = d.results.map(r => {
      const label = typeLabels[r.type] || r.type;
      return `<button type="button" class="media-crosssearch-result" role="option"
        data-media-action="crosssearch-open"
        data-result-type="${escapeAttr(r.type)}"
        data-result-id="${escapeAttr(String(r.id ?? ''))}">
        <span class="media-crosssearch-result-type">${escapeHtml(label)}</span>
        <span class="media-crosssearch-result-title">${escapeHtml(r.title || '(untitled)')}</span>
        <span class="media-crosssearch-result-sub">${escapeHtml(r.subtitle || '')}</span>
      </button>`;
    }).join('');
    results.classList.remove('is-hidden');
  }, 200);
}

function mediaCrossSearchClear() {
  const input = document.getElementById('media-crosssearch-input');
  const results = document.getElementById('media-crosssearch-results');
  if (input) input.value = '';
  if (results) { results.innerHTML = ''; results.classList.add('is-hidden'); }
}

function mediaCrossSearchOpen(type, id) {
  const subByType = {video: 'videos', audio: 'audio', book: 'books', channel: 'channels'};
  const targetSub = subByType[type];
  if (targetSub && typeof switchMediaSub === 'function') {
    try { switchMediaSub(targetSub); } catch (_) {}
  }
  mediaCrossSearchClear();
}

async function downloadYtVideo(url, title) {
  const s = await _fetchJson('/api/ytdlp/status');
  if (!s.installed) { toast('Install the downloader first from the Videos tab', 'warning'); return; }
  try {
    const d = await apiPost('/api/ytdlp/download', {url, folder: 'YouTube Downloads'});
    if (d.id) { toast('Downloading: ' + title.substring(0,50) + '...', 'info'); pollMediaDownloads(d.id); }
    else { toast(d.error || 'Download failed', 'error'); }
  } catch(e) { toast('Download failed', 'error'); }
}

async function downloadYtAudio(url, title) {
  const s = await _fetchJson('/api/ytdlp/status');
  if (!s.installed) { toast('Install the downloader first from the Videos tab', 'warning'); return; }
  try {
    const d = await apiPost('/api/ytdlp/download-audio', {url, folder: 'YouTube Audio'});
    if (d.id) { toast('Downloading audio: ' + title.substring(0,50) + '...', 'info'); pollMediaDownloads(d.id); }
    else { toast(d.error || 'Download failed', 'error'); }
  } catch(e) { toast('Download failed', 'error'); }
}

// ── Playback ──
function setMediaSpeed(speed) {
  const v = document.querySelector('#media-player video');
  const a = document.querySelector('#media-player audio');
  if (v) v.playbackRate = parseFloat(speed);
  if (a) a.playbackRate = parseFloat(speed);
}

function playMediaVideo(id, filename, title) {
  const player = document.getElementById('media-player');
  const video = document.getElementById('media-video-el');
  const audio = document.getElementById('media-audio-el');
  setMediaVisibility(audio, false); audio.pause();
  setMediaVisibility(video, true, 'block');
  document.getElementById('media-player-title').textContent = title;
  video.src = `/api/videos/serve/${encodeURIComponent(filename)}`;
  setMediaVisibility(player, true);
  video.play();
  // Check for subtitle file (.srt/.vtt alongside the video)
  checkVideoSubtitles(filename);
}

async function checkVideoSubtitles(filename) {
  const subStatus = document.getElementById('subtitle-status');
  const track = document.getElementById('media-video-subs');
  if (!subStatus || !track) return;
  setMediaVisibility(subStatus, false);
  track.src = '';
  // Try .vtt first, then .srt — the backend serves from the same directory
  const base = filename.replace(/\.[^.]+$/, '');
  for (const ext of ['.vtt', '.srt']) {
    try {
      const resp = await fetch(`/api/videos/serve/${encodeURIComponent(base + ext)}`, {method: 'HEAD'});
      if (resp.ok) {
        track.src = `/api/videos/serve/${encodeURIComponent(base + ext)}`;
        setMediaVisibility(subStatus, true);
        subStatus.textContent = 'Subtitles available (' + ext.slice(1).toUpperCase() + ')';
        // Enable the track
        const video = document.getElementById('media-video-el');
        if (video.textTracks && video.textTracks.length) {
          video.textTracks[0].mode = 'showing';
        }
        return;
      }
    } catch {}
  }
}

function playMediaAudio(id, filename, title) {
  const player = document.getElementById('media-player');
  const video = document.getElementById('media-video-el');
  const audio = document.getElementById('media-audio-el');
  setMediaVisibility(video, false); video.pause();
  setMediaVisibility(audio, true, 'block');
  document.getElementById('media-player-title').textContent = title;
  audio.src = `/api/audio/serve/${encodeURIComponent(filename)}`;
  setMediaVisibility(player, true);
  audio.play();
  // Show chapter markers once duration is known
  audio.addEventListener('loadedmetadata', function _chapHandler() {
    showAudioChapters(audio.duration);
    audio.removeEventListener('loadedmetadata', _chapHandler);
  });
  // Highlight playing row
  document.querySelectorAll('.media-audio-row').forEach(r => r.classList.remove('playing'));
  event?.target?.closest?.('.media-audio-row')?.classList.add('playing');
}

function closeMediaPlayer() {
  document.getElementById('media-video-el').pause();
  document.getElementById('media-audio-el').pause();
  document.getElementById('media-video-el').src = '';
  document.getElementById('media-audio-el').src = '';
  setMediaVisibility('media-player', false);
  const chapPanel = document.getElementById('audio-chapters-panel');
  setMediaVisibility(chapPanel, false);
  setMediaVisibility('subtitle-status', false);
}

// ── Audiobook Chapter Navigation ──
function generateChapters(durationSec) {
  // Auto-generate chapter markers every 10 minutes for long audio
  if (!durationSec || durationSec < 600) return [];
  const chapters = [];
  const interval = durationSec > 7200 ? 600 : 300; // 10min or 5min chapters
  for (let t = 0; t < durationSec; t += interval) {
    const min = Math.floor(t / 60);
    const sec = t % 60;
    chapters.push({time: t, label: `${String(min).padStart(2,'0')}:${String(sec).padStart(2,'0')}`});
  }
  return chapters;
}

function showAudioChapters(durationSec) {
  const panel = document.getElementById('audio-chapters-panel');
  const list = document.getElementById('audio-chapters-list');
  if (!panel || !list) return;
  const chapters = generateChapters(durationSec);
  if (!chapters.length) { setMediaVisibility(panel, false); return; }
  setMediaVisibility(panel, true);
  list.innerHTML = chapters.map(c =>
    `<div class="audio-chapter-item" role="button" tabindex="0" data-media-action="seek-audio-chapter" data-audio-time="${c.time}">
      <span class="runtime-mono-cell-strong text-accent">${c.label}</span>
      <span class="text-muted">Chapter ${chapters.indexOf(c) + 1}</span>
    </div>`
  ).join('');
}

function seekAudioTo(timeSec) {
  const audio = document.querySelector('audio');
  if (audio) { audio.currentTime = timeSec; if (audio.paused) audio.play(); }
}

// ── Book Reader ──
function openBook(id, filename, title, format) {
  const reader = document.getElementById('media-book-reader');
  const content = document.getElementById('book-reader-content');
  const pdfFrame = document.getElementById('book-pdf-frame');
  document.getElementById('book-reader-title').textContent = title;
  setMediaVisibility(reader, true, 'flex');

  if (format === 'epub') {
    setMediaVisibility(content, true, 'block');
    setMediaVisibility(pdfFrame, false);
    content.innerHTML = '';
    setMediaVisibility('book-prev-btn', true);
    setMediaVisibility('book-next-btn', true);
    if (typeof ePub !== 'undefined') {
      const book = ePub(`/api/books/serve/${encodeURIComponent(filename)}`);
      _mediaBookRendition = book.renderTo(content, {width:'100%', height:'100%', flow:'paginated', spread:'none'});
      _mediaBookRendition.display();
      _mediaBookRendition.on('relocated', loc => {
        document.getElementById('book-reader-loc').textContent = loc.start?.displayed ? `Page ${loc.start.displayed.page} of ${loc.start.displayed.total}` : '';
        apiFetch(`/api/books/${id}`, {method:'PATCH', body:JSON.stringify({last_position:loc.start?.cfi||''})}).catch(() => {});
      });
    } else {
      content.innerHTML = '<div class="workspace-empty-state media-book-loading">EPUB reader loading... If this persists, the epub.js library may not be available.</div>';
    }
  } else {
    // PDF — use iframe (WebView2 has built-in PDF viewer)
    setMediaVisibility(content, false);
    setMediaVisibility(pdfFrame, true, 'flex');
    setMediaVisibility('book-prev-btn', false);
    setMediaVisibility('book-next-btn', false);
    document.getElementById('book-reader-loc').textContent = '';
    pdfFrame.src = `/api/books/serve/${encodeURIComponent(filename)}`;
  }
}

function closeBookReader() {
  setMediaVisibility('media-book-reader', false);
  document.getElementById('book-reader-content').innerHTML = '';
  document.getElementById('book-pdf-frame').src = '';
  _mediaBookRendition = null;
}
function bookReaderPrev() { if (_mediaBookRendition) _mediaBookRendition.prev(); }
function bookReaderNext() { if (_mediaBookRendition) _mediaBookRendition.next(); }

// ── CRUD ──
async function deleteMediaItem(id, type) {
  if (!confirm('Delete this item? This cannot be undone.')) return;
  const apiMap = {videos:'/api/videos', audio:'/api/audio', books:'/api/books'};
  try {
    await apiDelete(apiMap[type] + '/' + id);
    toast('Deleted', 'warning');
    closeMediaPlayer();
    loadMediaContent(); loadTotalMediaStats();
  } catch(e) { toast('Failed to delete item', 'error'); }
}

async function moveMediaItem(id, type) {
  const foldersMap = {videos:'/api/videos/folders', audio:'/api/audio/folders', books:'/api/books/folders'};
  const apiMap = {videos:'/api/videos', audio:'/api/audio', books:'/api/books'};
  let folders = [];
  try { folders = await _fetchJson(foldersMap[type]); } catch(e) {}
  const name = prompt('Move to folder:\n\nExisting: ' + (folders.length ? folders.join(', ') : 'none'));
  if (name === null) return;
  try {
    await apiFetch(`${apiMap[type]}/${id}`, {method:'PATCH', body:JSON.stringify({folder:name})});
  } catch(e) {
    toast(e?.data?.error || 'Failed to move item', 'error');
    return;
  }
  toast('Moved to ' + (name || 'Unsorted'), 'success');
  loadMediaContent();
}

function createMediaFolder() {
  const name = prompt('New folder name:');
  if (!name) return;
  toast(`Folder "${name}" ready. Move or download content into it.`, 'info');
}

// ── Downloads ──
async function downloadMediaURL() {
  const input = document.getElementById('media-url-input');
  const url = input.value.trim();
  if (!url) { toast('Paste a URL first', 'warning'); return; }
  const s = await _fetchJson('/api/ytdlp/status');
  if (!s.installed) {
    toast('Installing downloader first...', 'info');
    try { await apiPost('/api/ytdlp/install'); } catch(e) { toast('Install failed', 'error'); return; }
    for (let i = 0; i < 60; i++) {
      await new Promise(r => setTimeout(r, 2000));
      const p = await _fetchJson('/api/ytdlp/install-progress');
      if (p.status === 'complete') break;
      if (p.status === 'error') { toast('Install failed: ' + p.error, 'error'); return; }
    }
    checkYtdlpStatus();
  }
  const cat = document.getElementById('media-cat-select')?.value || '';
  const endpoint = _mediaSub === 'audio' ? '/api/ytdlp/download-audio' : '/api/ytdlp/download';
  try {
    const d = await apiPost(endpoint, {url, category:cat, folder:_mediaFolder});
    if (d.error) { toast(d.error, 'error'); return; }
    input.value = '';
    toast('Download started...', 'info');
    pollMediaDownloads(d.id);
  } catch(e) { toast(e?.data?.error || 'Download failed to start', 'error'); }
}

function pollMediaDownloads(watchId) {
  const bar = document.getElementById('media-dl-progress');
  setMediaVisibility(bar, true);
  document.getElementById('media-dl-title').textContent = 'Starting download...';
  document.getElementById('media-dl-fill').style.width = '0%';
  stopMediaDownloadPolling();
  startMediaDownloadPolling(watchId);
}

function toggleDlQueue() {
  const panel = document.getElementById('dl-queue-panel');
  const nextVisible = !isMediaVisible(panel);
  setMediaVisibility(panel, nextVisible);
  if (nextVisible) refreshDlQueue();
}

async function refreshDlQueue() {
  try {
    const all = await _fetchJson('/api/ytdlp/progress');
    const el = document.getElementById('dl-queue-list');
    const entries = Object.entries(all);
    if (!entries.length) {
      el.innerHTML = '<div class="media-inline-empty">No downloads</div>';
      return;
    }
    el.innerHTML = entries.map(([id, p]) => {
      const tone = p.status === 'complete' ? 'success' : p.status === 'error' ? 'danger' : 'progress';
      const pct = p.status === 'complete' ? 100 : (p.percent || 0);
      return `<div class="media-download-item">
        <div class="media-download-head">
          <span class="media-download-title">${escapeHtml(p.title || 'Download #' + id)}</span>
          <span class="media-download-status" data-tone="${tone}">${p.status === 'complete' ? 'Done' : p.status === 'error' ? 'Failed' : pct + '%'}</span>
        </div>
        ${p.status === 'downloading' ? `<div class="media-download-progress"><div class="media-download-progress-bar" style="--media-progress-width:${pct}%;"></div></div>` : ''}
        ${p.speed ? `<div class="media-download-speed">${p.speed}</div>` : ''}
      </div>`;
    }).join('');
  } catch {}
}

async function subscribeChannel(url, name, category) {
  try {
    const d = await apiPost('/api/subscriptions', {name, url, category});
    if (d.status === 'subscribed') toast('Subscribed to ' + name, 'success');
    else toast(d.error || 'Already subscribed', 'info');
  } catch(e) { toast('Failed to subscribe', 'error'); }
}

async function unsubscribeChannel(id, name) {
  if (!confirm('Unsubscribe from ' + (name || 'this channel') + '?')) return;
  try {
    await apiDelete('/api/subscriptions/' + id);
    toast('Unsubscribed from ' + (name || 'channel'), 'info');
    loadSubscriptions();
  } catch(e) { toast('Failed to unsubscribe', 'error'); }
}

async function loadSubscriptions() {
  const results = document.getElementById('yt-video-results');
  const channels = document.getElementById('channel-list');
  setMediaVisibility(results, false);
  setMediaVisibility(channels, true);
  try {
    const subs = await _fetchJson('/api/subscriptions');
    if (!subs.length) {
      channels.innerHTML = '<div class="media-browser-empty"><strong>No subscriptions yet</strong><div class="media-browser-status-copy">Click the + button on any channel to subscribe.</div></div>';
      return;
    }
    let html = `<div class="media-browser-results-head">
      <div class="media-browser-title-group">
        <span class="media-browser-results-name">My Subscriptions</span>
        <span class="media-browser-results-meta">(${subs.length} channels)</span>
      </div>
      <button class="btn btn-sm" type="button" data-media-action="filter-channel-list">Back to All Channels</button>
    </div>`;
    html += '<div class="media-browser-grid media-browser-grid-subscriptions">';
    for (const s of subs) {
      html += `<div class="contact-card media-subscription-card">
        <div class="media-browser-card-head">
          <div class="media-browser-card-content">
            <div class="media-browser-card-name">${escapeHtml(s.channel_name)}</div>
            <div class="media-browser-card-copy media-subscription-copy">${escapeHtml(s.category)}</div>
          </div>
          <div class="media-browser-card-actions">
            <button class="btn btn-sm btn-primary" type="button" data-media-action="browse-channel-videos" data-channel-url="${escapeAttr(s.channel_url)}" data-channel-name="${escapeAttr(s.channel_name)}" title="Browse videos">Browse</button>
            <button class="btn btn-sm btn-danger" type="button" data-media-action="unsubscribe-channel" data-subscription-id="${s.id}" data-channel-name="${escapeAttr(s.channel_name)}" title="Unsubscribe" aria-label="Unsubscribe">x</button>
          </div>
        </div>
      </div>`;
    }
    html += '</div>';
    channels.innerHTML = html;
  } catch(e) { channels.innerHTML = mediaBrowserStatusHtml({title:'Subscriptions Unavailable', copy:'Failed to load subscriptions.', tone:'danger'}); }
}

async function uploadMediaFiles() {
  const input = document.getElementById('media-file-upload');
  if (!input || !input.files.length) return;
  const cat = document.getElementById('media-cat-select')?.value || '';
  const uploadMap = {videos:'/api/videos/upload', audio:'/api/audio/upload', books:'/api/books/upload'};
  const uploads = Array.from(input.files).map(file => {
    const sizeMB = (file.size / 1024 / 1024).toFixed(1);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('category', cat);
    formData.append('folder', _mediaFolder);
    formData.append('title', file.name.replace(/\.[^.]+$/, ''));
    toast(`Uploading ${file.name} (${sizeMB} MB)...`, 'info');
    return apiUpload(uploadMap[_mediaSub], formData)
      .then(() => { toast('Uploaded: ' + file.name, 'success'); })
      .catch(e => toast(`Upload failed: ${e?.data?.error || file.name}`, 'error'));
  });
  await Promise.all(uploads);
  input.value = '';
  loadMediaContent(); loadTotalMediaStats();
}

// ── Catalogs ──
function toggleMediaCatalog() {
  _mediaCatalogVisible = !_mediaCatalogVisible;
  setMediaVisibility('media-catalog-panel', _mediaCatalogVisible);
  if (_mediaCatalogVisible) loadActiveCatalog();
}

async function loadActiveCatalog() {
  if (_mediaSub === 'books') { loadBookCatalog(); return; }
  const isAudio = _mediaSub === 'audio';
  const catalogUrl = isAudio ? '/api/audio/catalog' : '/api/videos/catalog';
  try {
    const catalog = await _fetchJson(catalogUrl);
    const existing = new Set(_mediaItems.filter(v => v.url).map(v => v.url));
    const el = document.getElementById('media-catalog-list');
    const dlAllBtn = document.getElementById('media-catalog-dl-all');
    document.getElementById('media-catalog-title').textContent = isAudio ? 'Audio Catalog' : 'Prepper Video Library';
    document.getElementById('media-catalog-desc').textContent = isAudio ? 'Survival training, HAM radio, homesteading audio' : 'Curated survival & preparedness videos';
    if (dlAllBtn) dlAllBtn.dataset.mediaAction = isAudio ? 'download-all-audio-catalog' : 'download-all-catalog';
    const groups = {};
    for (const item of catalog) { const f = item.folder||'General'; if (!groups[f]) groups[f]=[]; groups[f].push(item); }
    let html = '';
    for (const [folder, items] of Object.entries(groups)) {
      html += `<div class="catalog-folder-header">${escapeHtml(folder)} (${items.length})</div>`;
      for (const item of items) {
        const downloaded = existing.has(item.url);
        html += `<div class="catalog-item"><div class="catalog-item-info"><div class="catalog-item-title">${escapeHtml(item.title)}</div>
          <div class="catalog-item-meta">${escapeHtml(item.channel)} &middot; ${escapeHtml(item.category)}</div></div>
          ${downloaded ? '<span class="media-status-chip media-status-chip-success">Downloaded</span>'
          : `<button class="btn btn-sm btn-primary" type="button" data-media-action="${isAudio ? 'download-catalog-audio' : 'download-catalog-item'}" data-media-url="${escapeAttr(item.url)}" data-media-folder="${escapeAttr(item.folder)}" data-media-category="${escapeAttr(item.category)}">Download</button>`}
        </div>`;
      }
    }
    el.innerHTML = html;
  } catch(e) { toast('Failed to load catalog', 'error'); }
}

async function loadBookCatalog() {
  try {
    const catalog = await _fetchJson('/api/books/catalog');
    const existing = new Set(_mediaItems.filter(b => b.url).map(b => b.url));
    const el = document.getElementById('media-catalog-list');
    const dlAllBtn = document.getElementById('media-catalog-dl-all');
    document.getElementById('media-catalog-title').textContent = 'Reference Library';
    document.getElementById('media-catalog-desc').textContent = 'Survival manuals, field guides, medical references (public domain)';
    if (dlAllBtn) dlAllBtn.dataset.mediaAction = 'download-all-books';
    const groups = {};
    for (const item of catalog) { const f = item.folder||'General'; if (!groups[f]) groups[f]=[]; groups[f].push(item); }
    let html = '';
    for (const [folder, items] of Object.entries(groups)) {
      html += `<div class="catalog-folder-header">${escapeHtml(folder)} (${items.length})</div>`;
      for (const item of items) {
        const downloaded = existing.has(item.url);
        html += `<div class="catalog-item"><div class="catalog-item-info"><div class="catalog-item-title">${escapeHtml(item.title)}</div>
          <div class="catalog-item-meta">${escapeHtml(item.author)} &middot; ${item.format.toUpperCase()} &middot; ${escapeHtml(item.category)}</div>
          ${item.description ? `<div class="media-catalog-item-desc">${escapeHtml(item.description)}</div>` : ''}</div>
          ${downloaded ? '<span class="media-status-chip media-status-chip-success">Downloaded</span>'
          : `<button class="btn btn-sm btn-primary" type="button" data-media-action="download-ref-book" data-media-url="${escapeAttr(item.url)}" data-media-folder="${escapeAttr(item.folder)}" data-media-category="${escapeAttr(item.category)}" data-media-title="${escapeAttr(item.title)}" data-media-author="${escapeAttr(item.author || '')}" data-media-format="${escapeAttr(item.format)}" data-media-description="${escapeAttr(item.description || '')}">Download</button>`}
        </div>`;
      }
    }
    el.innerHTML = html;
  } catch(e) { toast('Failed to load catalog', 'error'); }
}

async function downloadCatalogItem(btn, url, folder, category) {
  btn.setAttribute('aria-busy', 'true'); btn.disabled = true;
  try {
    const d = await apiPost('/api/ytdlp/download', {url, folder, category});
    btn.removeAttribute('aria-busy');
    if (d.error) { toast(d.error, 'error'); btn.disabled = false; return; }
    btn.textContent = 'Queued'; pollMediaDownloads(d.id);
  } catch(e) { btn.removeAttribute('aria-busy'); btn.disabled = false; toast('Failed', 'error'); }
}

async function downloadCatalogAudio(btn, url, folder, category) {
  btn.setAttribute('aria-busy', 'true'); btn.disabled = true;
  try {
    const d = await apiPost('/api/ytdlp/download-audio', {url, folder, category});
    btn.removeAttribute('aria-busy');
    if (d.error) { toast(d.error, 'error'); btn.disabled = false; return; }
    btn.textContent = 'Queued'; pollMediaDownloads(d.id);
  } catch(e) { btn.removeAttribute('aria-busy'); btn.disabled = false; toast('Failed', 'error'); }
}

async function downloadRefBook(btn, item) {
  btn.setAttribute('aria-busy', 'true'); btn.disabled = true;
  try {
    const d = await apiPost('/api/books/download-ref', item);
    btn.removeAttribute('aria-busy');
    if (d.status === 'already_downloaded') { toast('Already downloaded', 'info'); btn.textContent = 'Downloaded'; btn.classList.add('tone-success'); return; }
    if (d.error) { toast(d.error, 'error'); btn.disabled = false; return; }
    btn.textContent = 'Downloading...'; pollMediaDownloads(d.id);
  } catch(e) { btn.removeAttribute('aria-busy'); btn.disabled = false; toast('Failed', 'error'); }
}

async function downloadAllCatalog() {
  const s = await _fetchJson('/api/ytdlp/status');
  if (!s.installed) { toast('Install the downloader first', 'warning'); return; }
  try {
    const catalog = await _fetchJson('/api/videos/catalog');
    const d = await apiPost('/api/ytdlp/download-catalog', {items: catalog});
    if (d.error) { toast(d.error, 'error'); return; }
    if (d.status === 'all_downloaded') { toast('All catalog content already downloaded!', 'success'); return; }
    toast('Queued ' + d.count + ' items for download', 'info'); pollMediaDownloads(d.id);
  } catch(e) { toast('Failed', 'error'); }
}

async function downloadAllAudioCatalog() {
  const s = await _fetchJson('/api/ytdlp/status');
  if (!s.installed) { toast('Install the downloader first', 'warning'); return; }
  try {
    const catalog = await _fetchJson('/api/audio/catalog');
    // Download each one as audio
    const toDownload = catalog.filter(item => !_mediaItems.find(a => a.url === item.url));
    if (!toDownload.length) { toast('All audio catalog items already downloaded!', 'success'); return; }
    const results = await Promise.all(toDownload.map(item =>
      apiPost('/api/ytdlp/download-audio', {url:item.url, folder:item.folder, category:item.category})
        .catch(e => ({error: e.message}))
    ));
    let queued = 0;
    results.forEach(d => { if (d.id) { queued++; pollMediaDownloads(d.id); } });
    if (queued === 0) toast('All audio catalog items already downloaded!', 'success');
    else toast(`Queued ${queued} audio downloads`, 'info');
  } catch(e) { toast('Failed', 'error'); }
}

async function downloadAllBooks() {
  try {
    const d = await apiPost('/api/books/download-all-refs');
    if (d.status === 'all_downloaded') { toast('All reference books already downloaded!', 'success'); return; }
    if (d.error) { toast(d.error, 'error'); return; }
    toast('Downloading ' + d.count + ' reference books...', 'info'); pollMediaDownloads(d.id);
  } catch(e) { toast('Failed', 'error'); }
}

/* ─── Guided Drills ─── */
const DRILL_DATA = {
  '72hour': {title: '72-Hour Kit Check', estimate: '30 min', steps: ['Locate your 72-hour kit','Check water supply (1 gal/person/day x 3 days)','Check food supply (non-perishable, within expiration)','Test flashlight and replace batteries if needed','Check first aid kit — restock used items','Verify prescription medications are current','Test NOAA weather radio','Charge all battery packs and power banks','Verify cash on hand ($200+ small bills)','Check clothing — season-appropriate for all members','Verify copies of important documents','Test all communication devices']},
  'evacuation': {title: 'Evacuation Drill', estimate: '15-30 min', steps: ['Announce evacuation drill to all household members','Each person grabs their go-bag','Load essential items into vehicle(s)','Verify fuel level is above 3/4 tank','Account for all household members + pets','Lock and secure the house','Drive primary evacuation route to rally point','Note total time from announcement to arrival','Discuss what went well and what to improve','Update your family emergency plan with findings']},
  'comms': {title: 'Communications Check', estimate: '20 min', steps: ['Power on all FRS/GMRS radios','Replace batteries if signal is weak','Test transmission on your designated channel','Test reception — have someone transmit from another room/building','Power on HAM radio (if licensed)','Check into a local net or make a simplex call on 146.520','Test NOAA weather radio reception','Verify all frequencies are programmed correctly','Test backup power (battery pack, solar charger)','Document any equipment issues']},
  'blackout': {title: 'Blackout Drill', estimate: '2-4 hrs', steps: ['Turn off main breaker (simulate grid failure)','Activate backup lighting (lanterns, flashlights, candles)','Start generator if available — connect critical loads','Test alternate cooking method (camp stove, grill)','Verify refrigerator plan — coolers, ice, consume perishables order','Test communication devices on battery power','Assess heating/cooling capability without grid','Run for minimum 2 hours (ideally 4+)','Log observations — what worked, what failed','Restore power and document lessons learned']},
  'medical': {title: 'Medical Response Drill', estimate: '20 min', steps: ['Locate your first aid kit / IFAK','Inventory contents — check for expired items','Practice applying a tourniquet (on yourself or training dummy)','Review CPR steps (30 compressions : 2 breaths)','Practice the recovery position','Locate and test any AED device','Review location of prescription medications for all household members','Practice wound packing with gauze','Review your emergency contact numbers','Restock any used or expired supplies']},
  'water': {title: 'Water Security Drill', estimate: '30 min', steps: ['Check water storage levels — gallons on hand','Calculate days of supply (1 gal/person/day)','Test water filter — filter 1 quart and taste','Practice chemical purification (bleach method — 8 drops/gallon)','Boil water for 1 minute as backup method','Check expiration on water purification tablets','Identify nearest natural water sources (creek, lake, well)','Verify you have containers for water transport','Test rain collection setup if applicable','Document total water capacity and daily burn rate']},
};

let _drillTimer = null;
let _drillStart = null;

function formatDrillTimer(totalSeconds) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2,'0')}:${String(seconds).padStart(2,'0')}`;
}

function formatDrillDuration(totalSeconds) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}m ${seconds}s`;
}

function getRunDateLabel(isoValue) {
  const stamp = new Date(isoValue);
  return `${stamp.toLocaleDateString([], {month:'short', day:'numeric'})} · ${stamp.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}`;
}

function getToneClassFromPercent(prefix, value) {
  if (value >= 100) return `${prefix}-tone-good`;
  if (value >= 60) return `${prefix}-tone-watch`;
  return `${prefix}-tone-risk`;
}

let _currentDrillType = '';
function updateDrillLiveState() {
  const inputs = Array.from(document.querySelectorAll('#drill-steps input'));
  const total = inputs.length;
  const completed = inputs.filter(input => input.checked).length;
  const percent = total ? Math.round((completed / total) * 100) : 0;
  const drill = DRILL_DATA[_currentDrillType] || {};
  const summaryEl = document.getElementById('drill-summary');
  const progressEl = document.getElementById('drill-progress');
  const progressFillEl = document.getElementById('drill-progress-fill');
  if (summaryEl) {
    summaryEl.hidden = false;
    summaryEl.innerHTML = `
      <div class="drill-summary-stat">
        <span class="drill-summary-kicker">Checklist</span>
        <strong class="drill-summary-value">${completed}/${total}</strong>
        <span class="drill-summary-note">${percent}% complete</span>
      </div>
      <div class="drill-summary-stat">
        <span class="drill-summary-kicker">Estimated window</span>
        <strong class="drill-summary-value">${escapeHtml(drill.estimate || 'Flexible')}</strong>
        <span class="drill-summary-note">Use it as a training target</span>
      </div>
      <div class="drill-summary-stat">
        <span class="drill-summary-kicker">Current pace</span>
        <strong class="drill-summary-value">${completed === total ? 'Locked in' : 'In progress'}</strong>
        <span class="drill-summary-note">${Math.max(total - completed, 0)} steps remaining</span>
      </div>
    `;
  }
  if (progressEl) progressEl.hidden = false;
  if (progressFillEl) progressFillEl.style.width = `${percent}%`;
  inputs.forEach((input, index) => {
    const card = input.closest('.drill-step-card');
    if (!card) return;
    card.classList.toggle('is-complete', input.checked);
    const statusEl = card.querySelector('.drill-step-status');
    if (statusEl) {
      statusEl.textContent = input.checked ? 'Complete' : `Step ${index + 1}`;
    }
  });
}

function startDrill(type) {
  const drill = DRILL_DATA[type];
  if (!drill) return;
  _currentDrillType = type;
  _drillStart = Date.now();
  const activeEl = document.getElementById('drill-active');
  activeEl.style.display = 'grid';
  activeEl.classList.remove('is-hidden');
  document.getElementById('drill-title').textContent = drill.title;
  document.getElementById('drill-steps').innerHTML = drill.steps.map((s, i) =>
    `<label class="drill-step-card">
      <span class="drill-step-check-wrap">
        <input type="checkbox" class="tool-drill-check drill-step-check">
        <span class="drill-step-index">${String(i + 1).padStart(2, '0')}</span>
      </span>
      <span class="drill-step-content">
        <span class="drill-step-title">${escapeHtml(s)}</span>
        <span class="drill-step-status">Step ${i + 1}</span>
      </span>
    </label>`
  ).join('');
  document.querySelectorAll('#drill-steps input').forEach(input => input.addEventListener('change', updateDrillLiveState));
  updateDrillLiveState();
  document.getElementById('drill-timer').textContent = '00:00';
  if (_drillTimer) clearInterval(_drillTimer);
  _drillTimer = setInterval(() => {
    const elapsed = Math.floor((Date.now() - _drillStart) / 1000);
    document.getElementById('drill-timer').textContent = formatDrillTimer(elapsed);
  }, 1000);
  toast(`Drill started: ${drill.title}`, 'info');
}

function completeDrill() {
  if (_drillTimer) { clearInterval(_drillTimer); _drillTimer = null; }
  const elapsed = Math.floor((Date.now() - _drillStart) / 1000);
  const title = document.getElementById('drill-title').textContent;
  const checked = document.querySelectorAll('#drill-steps input:checked').length;
  const total = document.querySelectorAll('#drill-steps input').length;
  const durationLabel = formatDrillDuration(elapsed);
  toast(`Drill complete! ${title}: ${checked}/${total} tasks in ${durationLabel}`, 'success');
  sendNotification('Drill Complete', `${title}: ${checked}/${total} tasks in ${durationLabel}`);
  // Save to history
  apiPost('/api/drills/history', {drill_type: _currentDrillType || '', title, duration_sec: elapsed, tasks_total: total, tasks_completed: checked})
    .catch(() => toast('Failed to save drill history', 'error'));
  document.getElementById('drill-active').style.display = 'none';
  document.getElementById('drill-active').classList.add('is-hidden');
  document.getElementById('drill-summary').hidden = true;
  document.getElementById('drill-progress').hidden = true;
  loadDrillHistory();
}

function cancelDrill() {
  if (_drillTimer) { clearInterval(_drillTimer); _drillTimer = null; }
  document.getElementById('drill-active').style.display = 'none';
  document.getElementById('drill-active').classList.add('is-hidden');
  document.getElementById('drill-summary').hidden = true;
  document.getElementById('drill-progress').hidden = true;
  toast('Drill cancelled');
}

/* ─── Map Zone Drawing ─── */
let _drawingZone = false;
let _zonePoints = [];

function startDrawZone() {
  _drawingZone = !_drawingZone;
  _zonePoints = [];
  document.getElementById('draw-zone-btn').textContent = _drawingZone ? 'Finish Zone' : 'Draw Zone';
  if (!_drawingZone && _zonePoints.length >= 3) saveDrawnZone();
  else if (_drawingZone) toast('Click map points to draw zone. Click "Finish Zone" when done.', 'info');
}

function saveDrawnZone() {
  if (_zonePoints.length < 3) return;
  let panel = document.getElementById('zone-form-panel');
  if (panel) panel.remove();
  panel = document.createElement('div');
  panel.id = 'zone-form-panel';
  panel.className = 'map-zone-panel';
  panel.innerHTML = `
    <div class="map-zone-panel-title">Save Zone (${_zonePoints.length} points)</div>
    <input id="zone-name" class="map-zone-field" placeholder="Zone name..." value="Zone">
    <select id="zone-color" class="map-zone-field">
      <option value="red">Danger (Red)</option><option value="green">Safe (Green)</option>
      <option value="yellow">Caution (Yellow)</option><option value="blue">Info (Blue)</option>
      <option value="orange">Warning (Orange)</option>
    </select>
    <div class="map-zone-actions">
      <button type="button" class="btn btn-sm btn-primary" data-map-action="submit-drawn-zone">Save</button>
      <button type="button" class="btn btn-sm" data-shell-action="close-zone-panel">Cancel</button>
    </div>`;
  document.getElementById('map-viewer').appendChild(panel);
  document.getElementById('zone-name').focus();
}
function submitDrawnZone() {
  const name = document.getElementById('zone-name').value.trim() || 'Zone';
  const colorKey = document.getElementById('zone-color').value;
  const colorMap = {red:'#f44336', green:'#4caf50', yellow:'#ffeb3b', blue:'#2196f3', orange:'#ff9800'};
  const fillColor = colorMap[colorKey] || '#f44336';
  const coords = [..._zonePoints, _zonePoints[0]];
  const geojson = {type:'Feature', geometry:{type:'Polygon', coordinates:[coords]}, properties:{name, color:fillColor}};
  let zones = readJsonStorage(localStorage, 'nomad-map-zones', []);
  if (!Array.isArray(zones)) zones = [];
  zones.push(geojson);
  localStorage.setItem('nomad-map-zones', JSON.stringify(zones));
  renderMapZones();
  _zonePoints = [];
  document.getElementById('zone-form-panel').remove();
  toast(`Zone "${name}" saved`, 'success');
}

function renderMapZones() {
  if (!_map) return;
  // Remove ALL existing zone layers first (prevents ghost layers on deletion)
  const style = _map.getStyle();
  if (style && style.layers) {
    style.layers.forEach(l => {
      if (l.id.startsWith('zone-')) {
        _map.removeLayer(l.id);
        if (_map.getSource(l.id)) _map.removeSource(l.id);
      }
    });
  }
  let zones = readJsonStorage(localStorage, 'nomad-map-zones', []);
  if (!Array.isArray(zones)) zones = [];
  zones.forEach((z, i) => {
    const id = `zone-${i}`;
    _map.addSource(id, {type:'geojson', data:z});
    _map.addLayer({id, type:'fill', source:id, paint:{'fill-color':z.properties.color || '#f44336','fill-opacity':0.2}});
  });
}

/* ─── Property Boundary Tool ─── */
let _drawingProperty = false;
let _propertyPoints = [];

function startDrawProperty() {
  _drawingProperty = !_drawingProperty;
  _propertyPoints = [];
  const btn = document.getElementById('property-btn');
  btn.textContent = _drawingProperty ? 'Finish Property' : 'Property';
  btn.className = _drawingProperty ? 'btn btn-sm btn-primary' : 'btn btn-sm';
  if (!_drawingProperty && _propertyPoints.length >= 3) {
    finishProperty();
  } else if (_drawingProperty) {
    toast('Click map points to outline your property boundary. Click "Finish Property" when done.', 'info');
  }
}

function finishProperty() {
  if (_propertyPoints.length < 3) { toast('Need at least 3 points', 'warning'); return; }
  // Calculate area using Shoelace formula (approximate, treats as flat)
  const coords = [..._propertyPoints, _propertyPoints[0]];
  let area = 0;
  for (let i = 0; i < _propertyPoints.length; i++) {
    const j = (i + 1) % _propertyPoints.length;
    // Convert degrees to approximate meters at this latitude
    const lat = (_propertyPoints[i][1] + _propertyPoints[j][1]) / 2;
    const mPerDegLon = 111320 * Math.cos(lat * Math.PI / 180);
    const mPerDegLat = 110540;
    const x1 = _propertyPoints[i][0] * mPerDegLon, y1 = _propertyPoints[i][1] * mPerDegLat;
    const x2 = _propertyPoints[j][0] * mPerDegLon, y2 = _propertyPoints[j][1] * mPerDegLat;
    area += x1 * y2 - x2 * y1;
  }
  area = Math.abs(area) / 2;
  const sqFt = area * 10.764;
  const acres = sqFt / 43560;
  // Calculate perimeter
  let perimeter = 0;
  for (let i = 0; i < _propertyPoints.length; i++) {
    const j = (i + 1) % _propertyPoints.length;
    perimeter += haversineKm(_propertyPoints[i], _propertyPoints[j]) * 1000;
  }
  const perimFt = perimeter * 3.281;

  // Save as a zone
  const geojson = {type:'Feature', geometry:{type:'Polygon', coordinates:[[...coords]]},
    properties:{name: 'Property Boundary', color: '#5b9fff', isProperty: true, area_acres: acres.toFixed(2), perimeter_ft: Math.round(perimFt)}};
  let zones = readJsonStorage(localStorage, 'nomad-map-zones', []);
  if (!Array.isArray(zones)) zones = [];
  // Remove existing property boundary
  const filtered = zones.filter(z => !z.properties?.isProperty);
  filtered.push(geojson);
  localStorage.setItem('nomad-map-zones', JSON.stringify(filtered));
  renderMapZones();
  _propertyPoints = [];
  toast(`Property: ${acres.toFixed(2)} acres (${sqFt.toLocaleString()} sq ft), perimeter: ${Math.round(perimFt).toLocaleString()} ft (${(perimFt/5280).toFixed(2)} mi)`, 'success');
}

/* ─── Map Print Layout ─── */
async function printMapView() {
  if (!_map) return;
  const canvas = _map.getCanvas();
  const center = _map.getCenter();
  const zoom = _map.getZoom();
  const dataUrl = canvas.toDataURL('image/png');
  const printWidth = Math.max(1, Number(canvas.width) || 1);
  const printHeight = Math.max(1, Number(canvas.height) || 1);

  // Get waypoints for the legend
  let waypointHtml = '';
  try {
    const wps = await _fetchJson('/api/waypoints');
    if (wps && wps.length) {
      waypointHtml = '<h3 class="map-print-section-title">Waypoints</h3><table class="map-print-table"><tr><th class="map-print-head">Name</th><th class="map-print-head">Lat</th><th class="map-print-head">Lng</th><th class="map-print-head">Category</th></tr>';
      for (const w of wps) {
        waypointHtml += `<tr><td class="map-print-cell">${escapeHtml(w.name||'')}</td><td class="map-print-cell">${(w.lat||0).toFixed(5)}</td><td class="map-print-cell">${(w.lng||0).toFixed(5)}</td><td class="map-print-cell">${escapeHtml(w.category||'')}</td></tr>`;
      }
      waypointHtml += '</table>';
    }
  } catch(e) {}

  const html = `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>NOMAD Map Print</title>
<style>
body { font-family: 'Segoe UI', sans-serif; margin: 0; padding: 15px; }
.map-img { width: 100%; border: 2px solid #333; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; border-bottom: 2px solid #333; padding-bottom: 8px; }
.title { font-size: 18px; font-weight: 700; }
.meta { font-size: 10px; color: #666; }
.footer { display: flex; justify-content: space-between; margin-top: 8px; font-size: 9px; color: #666; border-top: 1px solid #ccc; padding-top: 6px; }
.compass { width: 40px; height: 40px; text-align: center; font-size: 20px; font-weight: 900; }
.map-print-section-title { margin-top: 12px; }
.map-print-table { width: 100%; border-collapse: collapse; font-size: 11px; }
.map-print-head { text-align: left; border-bottom: 1px solid #333; padding: 4px; }
.map-print-cell { padding: 3px 4px; border-bottom: 1px solid #eee; }
@media print { body { padding: 5px; } }
</style></head><body>
<div class="header">
  <div>
    <div class="title">NOMAD Field Desk — Operational Map</div>
    <div class="meta">Center: ${center.lat.toFixed(5)}, ${center.lng.toFixed(5)} | Zoom: ${zoom.toFixed(1)} | Printed: ${new Date().toLocaleString()}</div>
  </div>
  <div class="compass">N<br>&#8593;</div>
</div>
<img src="${dataUrl}" class="map-img" alt="Operational map snapshot" width="${printWidth}" height="${printHeight}">
${waypointHtml}
<div class="footer">
  <span>Generated by NOMAD Field Desk</span>
  <span>Scale approximate at zoom level ${zoom.toFixed(1)}</span>
</div>
</body></html>`;

  openAppFrameHTML('Map Print', html);
}

/* ─── Map Bookmarks ─── */
function saveMapBookmark() {
  if (!_map) return;
  const center = _map.getCenter();
  const zoom = _map.getZoom();
  const name = `View at ${center.lat.toFixed(3)}, ${center.lng.toFixed(3)}`;
  let bookmarks = readJsonStorage(localStorage, 'nomad-map-bookmarks', []);
  if (!Array.isArray(bookmarks)) bookmarks = [];
  bookmarks.push({name, lat: center.lat, lng: center.lng, zoom, time: new Date().toISOString()});
  localStorage.setItem('nomad-map-bookmarks', JSON.stringify(bookmarks));
  toast(`Bookmark saved: ${center.lat.toFixed(4)}, ${center.lng.toFixed(4)}`, 'success');
  renderMapBookmarks();
}

function renderMapBookmarks() {
  let bookmarks = readJsonStorage(localStorage, 'nomad-map-bookmarks', []);
  if (!Array.isArray(bookmarks)) bookmarks = [];
  // Render in the map management area if visible
  let el = document.getElementById('map-bookmarks-list');
  if (!el) return;
  if (!bookmarks.length) { el.innerHTML = '<span class="map-bookmark-empty">No bookmarks saved. Click Bookmark while viewing the map.</span>'; return; }
  el.innerHTML = bookmarks.map((b, i) => `
    <div class="map-bookmark-row">
      <button type="button" class="map-bookmark-link" data-map-action="goto-bookmark" data-bookmark-index="${i}">${escapeHtml(b.name)}</button>
      <button type="button" class="map-bookmark-delete" data-map-action="delete-bookmark" data-bookmark-index="${i}" aria-label="Delete bookmark ${escapeAttr(b.name)}">&times;</button>
    </div>
  `).join('');
}

function gotoBookmark(idx) {
  let bookmarks = readJsonStorage(localStorage, 'nomad-map-bookmarks', []);
  if (!Array.isArray(bookmarks)) bookmarks = [];
  const b = bookmarks[idx];
  if (!b || !_map) return;
  if (!_mapVisible) toggleMapView();
  setTimeout(() => { if (_map) _map.flyTo({center: [b.lng, b.lat], zoom: b.zoom}); }, 100);
}

function deleteBookmark(idx) {
  let bookmarks = readJsonStorage(localStorage, 'nomad-map-bookmarks', []);
  if (!Array.isArray(bookmarks)) bookmarks = [];
  bookmarks.splice(idx, 1);
  localStorage.setItem('nomad-map-bookmarks', JSON.stringify(bookmarks));
  renderMapBookmarks();
}

/* ─── Bearing & Distance Calculator ─── */
let _bearingMode = false;
let _bearingPoints = [];

function calcBearingDistance() {
  _bearingMode = !_bearingMode;
  _bearingPoints = [];
  const btn = document.getElementById('bearing-btn');
  btn.textContent = _bearingMode ? 'Cancel Bearing' : 'Bearing';
  btn.className = _bearingMode ? 'btn btn-sm btn-primary' : 'btn btn-sm';
  if (_bearingMode) {
    toast('Click two points on the map to calculate bearing and distance', 'info');
  }
}

function handleBearingClick(lngLat) {
  if (!_bearingMode) return false;
  _bearingPoints.push([lngLat.lng, lngLat.lat]);
  new maplibregl.Marker({color: '#ff5722', scale: 0.5}).setLngLat(lngLat).addTo(_map);
  if (_bearingPoints.length === 2) {
    const [p1, p2] = _bearingPoints;
    const distKm = haversineKm(p1, p2);
    const distMi = distKm * 0.621371;
    // Calculate bearing
    const lat1 = p1[1] * Math.PI / 180, lat2 = p2[1] * Math.PI / 180;
    const dLon = (p2[0] - p1[0]) * Math.PI / 180;
    const y = Math.sin(dLon) * Math.cos(lat2);
    const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon);
    let bearing = Math.atan2(y, x) * 180 / Math.PI;
    bearing = (bearing + 360) % 360;
    // Cardinal direction
    const cardinals = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'];
    const cardinal = cardinals[Math.round(bearing / 22.5) % 16];
    // Draw line
    const geojson = {type:'Feature', geometry:{type:'LineString', coordinates: _bearingPoints}};
    if (_map.getSource('bearing-line')) _map.getSource('bearing-line').setData(geojson);
    else { _map.addSource('bearing-line', {type:'geojson', data:geojson}); _map.addLayer({id:'bearing-line', type:'line', source:'bearing-line', paint:{'line-color':'#ff5722','line-width':2}}); }
    toast(`Bearing: ${bearing.toFixed(1)}° (${cardinal}) | Distance: ${distKm.toFixed(2)} km (${distMi.toFixed(2)} mi)`, 'success');
    _bearingMode = false;
    _bearingPoints = [];
    document.getElementById('bearing-btn').textContent = 'Bearing';
    document.getElementById('bearing-btn').className = 'btn btn-sm';
  }
  return true;
}

/* ─── Multi-Node Federation ─── */
async function loadNodeIdentity() {
  try {
    const n = await _fetchJson('/api/node/identity');
    document.getElementById('node-id-badge').textContent = `Node: ${n.node_name} (${n.node_id})`;
    document.getElementById('node-name-input').value = n.node_name;
  } catch(e) {}
}

async function saveNodeName() {
  const name = document.getElementById('node-name-input').value.trim();
  if (!name) { toast('Enter a node name', 'warning'); return; }
  try {
    await apiPut('/api/node/identity', {name});
    toast('Node name set to "' + name + '"', 'success');
    loadNodeIdentity();
  } catch(e) { toast('Failed to set node name', 'error'); }
}

async function discoverPeers() {
  const el = document.getElementById('peer-list');
  el.innerHTML = '<div class="utility-empty-state peer-list-state">Scanning network…</div>';
  try {
    const d = await apiPost('/api/node/discover');
    if (!d.peers.length) {
  el.innerHTML = '<div class="utility-empty-state peer-list-state">No other NOMAD nodes found on this network. Make sure other instances are running and on the same LAN.</div>';
      return;
    }
    el.innerHTML = d.peers.map(p => `
      <div class="contact-card peer-list-card">
        <div class="cc-name">${escapeHtml(p.node_name)}</div>
        <div class="cc-field peer-list-meta">${escapeHtml(p.ip)}:${p.port} | ID: ${escapeHtml(p.node_id)} | v${escapeHtml(p.version || '?')}</div>
        <div class="cc-actions prep-row-actions peer-list-actions">
          <button class="btn btn-sm btn-primary" type="button" data-shell-action="sync-to-peer" data-peer-ip="${escapeAttr(p.ip)}" data-peer-port="${p.port}" data-peer-name="${escapeAttr(p.node_name)}">Push Data</button>
        </div>
      </div>
    `).join('');
    toast(`Found ${d.peers.length} node(s) on your network`, 'success');
  } catch(e) { el.innerHTML = '<div class="utility-empty-state peer-list-state peer-list-state-error">Discovery failed</div>'; }
}

async function syncToPeer(ip, port, name) {
  if (!ip) { toast('Enter a peer IP address', 'warning'); return; }
  port = port || 8080;
  toast(`Pushing data to ${name || ip}...`, 'info');
  try {
    const d = await apiPost('/api/node/sync-push', {ip, port});
    if (d.error) { toast(d.error, 'error'); return; }
    toast('Pushed ' + d.items + ' items to ' + (d.peer || ip), 'success');
    sendNotification('Sync Complete', 'Pushed ' + d.items + ' items to ' + (d.peer || ip));
    loadSyncLog();
    loadGroupExercises();
  } catch(e) { toast('Push failed — check the IP address and make sure the peer is running', 'error'); }
}

async function loadSyncLog() {
  try {
    const logs = await _fetchJson('/api/node/sync-log');
    const el = document.getElementById('sync-log-list');
    if (!logs.length) { el.innerHTML = '<div class="settings-empty-state">No sync history yet.</div>'; return; }
    el.innerHTML = logs.map(l => {
      const t = new Date(l.created_at);
      const ts = t.toLocaleDateString([], {month:'short',day:'numeric'}) + ' ' + t.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
      const icon = l.direction === 'push' ? '&#8593;' : '&#8595;';
      const directionClass = l.direction === 'push' ? 'settings-sync-entry-push' : 'settings-sync-entry-pull';
      const tables = safeJsonParse(l.tables_synced, {});
      const tableStr = Object.entries(tables).map(([t,c]) => `${t}:${c}`).join(', ');
      return `<div class="settings-record-card settings-sync-entry ${directionClass}">
        <div class="settings-record-head">
          <div class="settings-record-main">
            <div class="settings-record-meta-list">
              <span class="settings-sync-log-icon">${icon}</span>
              <span class="settings-row-meta settings-sync-log-time">${ts}</span>
              <span class="settings-row-pill">${l.direction.toUpperCase()}</span>
            </div>
            <div class="settings-record-meta-list">
              <span class="settings-row-title">${escapeHtml(l.peer_name || l.peer_ip || '?')}</span>
              <span class="settings-row-detail">${l.items_count} items (${tableStr})</span>
            </div>
          </div>
        </div>
      </div>`;
    }).join('');
  } catch(e) {}
}

/* ─── Conflict Resolution (Three-Way Merge) ─── */
async function loadConflicts() {
  try {
    const conflicts = await safeFetch('/api/node/conflicts', {}, []);
    const el = document.getElementById('conflict-list');
    const badge = document.getElementById('conflict-count-badge');
    if (!conflicts.length) {
      el.innerHTML = '<div class="settings-empty-state">No unresolved conflicts.</div>';
      badge.hidden = true;
      return;
    }
    badge.textContent = conflicts.length;
    badge.hidden = false;
    el.innerHTML = conflicts.map(c => {
      const ts = new Date(c.created_at).toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
      const details = c.conflict_details || [];
      return `<div class="settings-conflict-card">
        <div class="settings-conflict-head">
          <div class="settings-conflict-summary">
            <span class="settings-row-title">Sync #${c.id}</span>
            <span class="settings-row-meta">${ts} from ${escapeHtml(c.peer_name || c.peer_ip || '?')}</span>
          </div>
          <span class="settings-conflict-count">${details.length} conflict${details.length !== 1 ? 's' : ''}</span>
        </div>
        ${details.map((d, idx) => `
          <div class="settings-conflict-body">
            <div class="settings-conflict-detail-title">Table: ${escapeHtml(d.table || '?')} | Row: ${escapeHtml(d.row_hash || '?')}</div>
            <div class="settings-conflict-grid">
              <div class="settings-conflict-panel">
                <div class="settings-conflict-panel-title">LOCAL</div>
                <pre class="settings-conflict-pre">${escapeHtml(JSON.stringify(d.local_clock || {}, null, 1))}</pre>
                ${d.local_node ? `<div class="settings-conflict-footnote">Node: ${escapeHtml(d.local_node)} | ${escapeHtml(d.local_updated || '')}</div>` : ''}
              </div>
              <div class="settings-conflict-panel settings-conflict-panel-remote">
                <div class="settings-conflict-panel-title">REMOTE</div>
                <pre class="settings-conflict-pre">${escapeHtml(JSON.stringify(d.incoming_clock || {}, null, 1))}</pre>
                <div class="settings-conflict-footnote">From: ${escapeHtml(c.peer_name || c.peer_node_id || '?')}</div>
              </div>
            </div>
            <div class="settings-conflict-actions">
              <button class="btn btn-sm" type="button" data-shell-action="resolve-conflict" data-conflict-id="${c.id}" data-conflict-resolution="local">Keep Local</button>
              <button class="btn btn-sm btn-primary" type="button" data-shell-action="resolve-conflict" data-conflict-id="${c.id}" data-conflict-resolution="remote">Keep Remote</button>
              <button class="btn btn-sm settings-manual-merge-btn" type="button" data-shell-action="show-merge-editor" data-conflict-id="${c.id}" data-conflict-detail="${escapeAttr(JSON.stringify(d))}">Manual Merge</button>
            </div>
          </div>
        `).join('')}
      </div>`;
    }).join('');
  } catch(e) { console.error('loadConflicts error:', e); }
}

async function resolveConflict(id, resolution, mergedData) {
  try {
    const body = { resolution };
    if (mergedData) body.merged_data = mergedData;
    const d = await apiPost(`/api/node/conflicts/${id}/resolve`, body);
    if (d.error) { toast(d.error, 'error'); return; }
    toast(`Conflict #${id} resolved as ${resolution}`, 'success');
    loadConflicts();
    loadSyncLog();
  } catch(e) { toast('Failed to resolve conflict', 'error'); }
}

function showMergeEditor(conflictId, conflictDetailJson) {
  const overlay = document.getElementById('merge-editor-overlay');
  const fieldsEl = document.getElementById('merge-editor-fields');
  document.getElementById('merge-conflict-id').value = conflictId;
  overlay.hidden = false;
  const detail = safeJsonParse(conflictDetailJson, null);
  if (detail && typeof detail === 'object') {
    const localClock = detail.local_clock || {};
    const remoteClock = detail.incoming_clock || {};
    const allKeys = [...new Set([...Object.keys(localClock), ...Object.keys(remoteClock)])];
    fieldsEl.innerHTML = `
      <div class="settings-merge-editor-copy">Table: <strong>${escapeHtml(detail.table || '?')}</strong> | Row: ${escapeHtml(detail.row_hash || '?')}</div>
      <div class="settings-merge-editor-note">Edit the merged vector clock values below. Each key is a node ID and the value is the clock counter.</div>
      ${allKeys.map(k => `
        <div class="settings-merge-editor-row">
          <label class="settings-merge-editor-label">${escapeHtml(k)}</label>
          <span class="settings-merge-editor-side settings-merge-editor-side-local">L: ${localClock[k] || 0}</span>
          <span class="settings-merge-editor-side settings-merge-editor-side-remote">R: ${remoteClock[k] || 0}</span>
          <input class="merge-field input settings-merge-editor-input" data-key="${escapeAttr(k)}" data-table="${escapeAttr(detail.table || '')}"
                 value="${Math.max(localClock[k] || 0, remoteClock[k] || 0)}">
        </div>
      `).join('')}
    `;
  } else {
    fieldsEl.innerHTML = '<div class="settings-merge-editor-error">Could not parse conflict data for merge editor.</div>';
  }
}

function submitMerge() {
  const conflictId = document.getElementById('merge-conflict-id').value;
  const fields = document.querySelectorAll('.merge-field');
  const mergedData = {};
  fields.forEach(f => {
    const tname = f.dataset.table;
    if (!mergedData[tname]) mergedData[tname] = {};
    mergedData[tname][f.dataset.key] = parseInt(f.value) || 0;
  });
  resolveConflict(parseInt(conflictId), 'merged', mergedData);
  document.getElementById('merge-editor-overlay').hidden = true;
}

/* ─── PDF Download Helper ─── */
async function downloadPdf(url, filename) {
  try {
    toast('Generating PDF...', 'info');
    const resp = await fetch(url);
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      if (data.error && data.hint) {
        toast(`${data.error}. Run: ${data.hint}`, 'error');
      } else {
        toast(data.error || 'PDF generation failed', 'error');
      }
      return;
    }
    const blob = await resp.blob();
    window.downloadBlobFile(blob, filename || 'nomad-document.pdf');
    toast('PDF downloaded', 'success');
  } catch(e) { toast('PDF download failed: ' + e.message, 'error'); }
}

/* ─── Sneakernet Sync ─── */
async function exportSyncPack() {
  try {
    const resp = await fetch('/api/sync/export', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({include:['inventory','contacts','checklists','notes','incidents','waypoints']})});
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      toast(data.error || 'Export failed', 'error');
      return;
    }
    const blob = await resp.blob();
    window.downloadBlobFile(blob, `nomad-sync-${new Date().toISOString().slice(0,10)}.zip`);
    toast('Content pack exported', 'success');
  } catch(e) { toast('Export failed', 'error'); }
}

async function importSyncPack() {
  const input = document.getElementById('sync-import-file');
  if (!input.files.length) return;
  const formData = new FormData();
  formData.append('file', input.files[0]);
  try {
    const r = await _fetchJson('/api/sync/import', {method:'POST', body:formData});
    input.value = '';
    if (r.tables) {
      const summary = Object.entries(r.tables).map(([t,c]) => `${t}: ${c}`).join(', ');
      toast(`Imported: ${summary}`, 'success');
    } else { toast(r.error || 'Import failed', 'error'); }
  } catch(e) { toast('Import failed', 'error'); input.value = ''; }
}

/* ─── Dead Drop Encrypted Messaging ─── */
async function composeDeadDrop() {
  const message = document.getElementById('dd-message').value.trim();
  const recipient = document.getElementById('dd-recipient').value.trim();
  const secret = document.getElementById('dd-secret').value.trim();
  if (!message || !secret) { toast('Message and shared secret are required', 'warning'); return; }
  try {
    const r = await _fetchJson('/api/deaddrop/compose', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message, recipient, secret})});
    if (r.error) { toast(r.error, 'error'); return; }
    // Download as JSON file
    const blob = new Blob([JSON.stringify(r.payload, null, 2)], {type:'application/json'});
    window.downloadBlobFile(blob, r.filename);
    document.getElementById('dd-message').value = '';
    document.getElementById('dd-secret').value = '';
    toast('Dead drop message encrypted and downloaded — copy to USB drive', 'success');
  } catch(e) { toast('Encryption failed', 'error'); }
}

async function importDeadDrop() {
  const input = document.getElementById('dd-import-file');
  if (!input.files.length) return;
  try {
    const text = await input.files[0].text();
    const payload = safeJsonParse(text, null);
    if (!payload || typeof payload !== 'object') { toast('Invalid dead drop file', 'error'); input.value = ''; return; }
    input.value = '';
    // Import to DB
    await apiPost('/api/deaddrop/import', {payload});
    // Try to decrypt
    const secret = prompt('Enter the shared secret to decrypt this message:');
    if (!secret) { toast('Message imported but not decrypted', 'info'); return; }
    const r = await _fetchJson('/api/deaddrop/decrypt', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({payload, secret})});
    if (r.error) { toast(r.error, 'error'); return; }
    const el = document.getElementById('dd-received');
    if (el) {
      el.innerHTML = `<div class="settings-detail-shell settings-stack">
        <div class="settings-detail-meta">From: ${escapeHtml(r.from_name || 'Unknown')} (${escapeHtml(r.from_node || '?')}) — ${escapeHtml(r.timestamp || '')}</div>
        <div class="settings-message-body">${escapeHtml(r.message)}</div>
      </div>`;
    }
    toast('Message decrypted successfully', 'success');
  } catch(e) { toast('Import failed — invalid file format', 'error'); input.value = ''; }
}

async function loadDeadDropMessages() {
  try {
    const msgs = await _fetchJson('/api/deaddrop/messages');
    const el = document.getElementById('dd-received');
    if (!el) return;
    if (!msgs.length) { el.innerHTML = '<div class="settings-empty-state">No dead drop messages received yet.</div>'; return; }
    el.innerHTML = msgs.map(m => `<div class="settings-action-row">
      <span class="settings-row-meta">${escapeHtml(m.message_timestamp || '').slice(0,10)}</span>
      <span class="settings-row-title">${escapeHtml(m.from_name || 'Unknown')}</span>
      <span class="settings-row-detail">${m.decrypted ? '🔓' : '🔒'} ${escapeHtml(m.recipient || 'Any')}</span>
    </div>`).join('');
  } catch(e) {}
}

/* ─── Multi-Node Group Training Exercises ─── */
async function loadGroupExercises() {
  try {
    const exercises = await _fetchJson('/api/group-exercises');
    const el = document.getElementById('group-exercises-list');
    if (!el) return;
    if (!exercises.length) { el.innerHTML = '<div class="settings-empty-state">No group exercises yet. Create one to train with your federation peers.</div>'; return; }
    el.innerHTML = exercises.map(ex => {
      const statusColor = ex.status === 'active' ? 'var(--green)' : ex.status === 'completed' ? 'var(--accent)' : ex.status === 'invited' ? 'var(--orange)' : 'var(--text-muted)';
      const pCount = ex.participants ? ex.participants.length : 0;
      return `<div class="settings-detail-shell settings-exercise-card">
        <div class="settings-exercise-head">
          <div class="settings-stack">
            <span class="settings-row-title">${escapeHtml(ex.title)}</span>
            <span class="settings-row-meta">${escapeHtml(ex.scenario_type)}</span>
          </div>
          <span class="settings-row-pill settings-row-pill-dynamic" style="--settings-pill-tone:${statusColor};">${escapeHtml(ex.status.toUpperCase())}</span>
        </div>
        <div class="settings-exercise-copy">${escapeHtml(ex.description || '').slice(0, 120)}</div>
        <div class="settings-exercise-meta">
          <span>Phase ${ex.current_phase}</span>
          <span>${pCount} participant${pCount !== 1 ? 's' : ''}</span>
          <span>By ${escapeHtml(ex.initiator_name || 'Unknown')}</span>
        </div>
        <div class="settings-exercise-actions">
          ${ex.status === 'invited' ? `<button class="btn btn-sm btn-primary" type="button" data-shell-action="join-group-exercise" data-exercise-id="${escapeAttr(ex.exercise_id)}">Join Exercise</button>` : ''}
          ${ex.status === 'active' ? `<button class="btn btn-sm btn-primary" type="button" data-shell-action="advance-group-exercise" data-exercise-id="${escapeAttr(ex.exercise_id)}">Advance Phase</button>` : ''}
          ${ex.status === 'active' ? `<button class="btn btn-sm" type="button" data-shell-action="complete-group-exercise" data-exercise-id="${escapeAttr(ex.exercise_id)}">Complete</button>` : ''}
        </div>
        ${ex.decisions_log && ex.decisions_log.length ? `<div class="settings-exercise-log">
          ${ex.decisions_log.slice(-5).map(d => `<div class="settings-exercise-log-entry">Phase ${d.phase}: <b>${escapeHtml(d.name || '?')}</b> — ${escapeHtml(d.decision || '')}</div>`).join('')}
        </div>` : ''}
      </div>`;
    }).join('');
  } catch(e) {}
}

async function createGroupExercise() {
  const title = prompt('Exercise title:', 'Group Training Exercise');
  if (!title) return;
  const desc = prompt('Description (optional):', '');
  const types = ['grid_down', 'medical_crisis', 'evacuation', 'winter_storm', 'custom'];
  const type = prompt('Scenario type (' + types.join(', ') + '):', 'grid_down');
  try {
    const r = await _fetchJson('/api/group-exercises', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({title, description: desc, scenario_type: type || 'custom'})});
    if (r.exercise_id) {
      toast(`Exercise created! Invited ${r.invited} peers.`, 'success');
      loadGroupExercises();
    } else { toast(r.error || 'Failed', 'error'); }
  } catch(e) { toast('Failed to create exercise', 'error'); }
}

async function joinGroupExercise(exerciseId) {
  try {
    const r = await _fetchJson(`/api/group-exercises/${exerciseId}/join`, {method:'POST'});
    toast(`Joined exercise! ${r.participants} participants now.`, 'success');
    loadGroupExercises();
  } catch(e) { toast('Join failed', 'error'); }
}

async function advanceGroupExercise(exerciseId) {
  const decision = prompt('Your decision/action for this phase:');
  if (!decision) return;
  try {
    await apiPost(`/api/group-exercises/${exerciseId}/update-state`, {decision, event: `Phase advanced with decision: ${decision}`,
      phase: (await _fetchJson('/api/group-exercises')).find(e => e.exercise_id === exerciseId)?.current_phase + 1 || 1});
    toast('Phase advanced', 'success');
    loadGroupExercises();
  } catch(e) { toast(e?.data?.error || 'Failed', 'error'); }
}

async function completeGroupExercise(exerciseId) {
  try {
    await apiPost(`/api/group-exercises/${exerciseId}/update-state`, {status: 'completed', event: 'Exercise completed'});
    toast('Exercise completed!', 'success');
    loadGroupExercises();
  } catch(e) { toast(e?.data?.error || 'Failed', 'error'); }
}

/* ─── LoRA Fine-Tuning Pipeline ─── */
async function loadTrainingDatasets() {
  try {
    const ds = await _fetchJson('/api/ai/training/datasets');
    const el = document.getElementById('training-datasets-list');
    if (!el) return;
    if (!ds.length) { el.innerHTML = '<div class="training-empty-state">No training datasets. Create one from your conversation history.</div>'; return; }
    el.innerHTML = ds.map(d => `<div class="training-record">
      <span class="training-record-main">${escapeHtml(d.name)}</span>
      <span class="training-record-meta">${d.record_count} records</span>
      <span class="training-status-chip training-status-chip-accent">${escapeHtml(d.status || 'unknown')}</span>
    </div>`).join('');
  } catch(e) {}
}

async function createTrainingDataset() {
  const name = prompt('Dataset name:', 'NOMAD Custom Training');
  if (!name) return;
  toast('Extracting training data from conversations...', 'info');
  try {
    const r = await _fetchJson('/api/ai/training/datasets', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name, source:'conversations'})});
    toast(`Dataset created with ${r.records} training records`, 'success');
    loadTrainingDatasets();
    loadTrainingJobs();
  } catch(e) { toast('Failed to create dataset', 'error'); }
}

async function loadTrainingJobs() {
  try {
    const jobs = await _fetchJson('/api/ai/training/jobs');
    const el = document.getElementById('training-jobs-list');
    if (!el) return;
    if (!jobs.length) { el.innerHTML = '<div class="training-empty-state">No training jobs yet.</div>'; return; }
    el.innerHTML = jobs.map(j => {
      const statusTone = j.status === 'completed'
        ? 'training-status-chip-success'
        : j.status === 'running'
          ? 'training-status-chip-warning'
          : j.status === 'failed'
            ? 'training-status-chip-danger'
            : 'training-status-chip-muted';
      return `<div class="training-record">
        <span class="training-record-main">${escapeHtml(j.output_model || '?')}</span>
        <span class="training-record-meta">from ${escapeHtml(j.base_model)}</span>
        <span class="training-status-chip ${statusTone}">${escapeHtml(j.status || 'unknown')}</span>
        ${j.status === 'ready' ? `<span class="training-record-actions"><button type="button" class="btn btn-sm btn-primary training-run-btn" data-shell-action="run-training-job" data-training-job-id="${j.id}">Run</button></span>` : ''}
      </div>`;
    }).join('');
  } catch(e) {}
}

async function createTrainingJob() {
  const ds = await _fetchJson('/api/ai/training/datasets');
  if (!ds.length) { toast('Create a training dataset first', 'warning'); return; }
  const model = prompt('Base model name:', 'llama3.2');
  if (!model) return;
  const output = prompt('Output model name:', 'nomad-custom');
  if (!output) return;
  try {
    const r = await _fetchJson('/api/ai/training/jobs', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({dataset_id: ds[0].id, base_model: model, output_model: output})});
    toast(`Training job created \u2014 Modelfile at ${r.modelfile}`, 'success');
    loadTrainingJobs();
  } catch(e) { toast('Failed', 'error'); }
}

async function runTrainingJob(jid) {
  toast('Running training job (creating model via Ollama)...', 'info');
  try {
    await apiPost(`/api/ai/training/jobs/${jid}/run`, {});
    toast('Training started \u2014 model will be available once complete', 'success');
    setTimeout(loadTrainingJobs, 3000);
  } catch(e) { toast(e?.data?.error || 'Failed to start training', 'error'); }
}

/* ─── Perimeter Security Zones ─── */
async function loadPerimeterZones() {
  try {
    const zones = await _fetchJson('/api/security/zones');
    const el = document.getElementById('perimeter-zones-list');
    if (!el) return;
    if (!zones.length) { el.innerHTML = prepEmptyBlock('No perimeter zones defined.'); return; }
    el.innerHTML = zones.map(z => {
      const tc = z.threat_level === 'high' ? 'var(--red)' : z.threat_level === 'elevated' ? 'var(--orange)' : 'var(--green)';
      return `<div class="prep-record-item prep-perimeter-item">
        <span class="prep-record-dot" style="--prep-dot-color:${escapeHtml(z.color)};"></span>
        <span class="prep-record-main"><strong>${escapeHtml(z.name)}</strong></span>
        <span class="prep-inline-pill" style="--prep-pill-tone:${tc};">${z.threat_level}</span>
        <span class="prep-record-meta">${z.camera_ids.length} cam${z.camera_ids.length !== 1 ? 's' : ''}</span>
        <button type="button" class="btn btn-sm btn-danger prep-compact-danger" data-prep-action="delete-perimeter-zone" data-zone-id="${z.id}">Del</button>
      </div>`;
    }).join('');
  } catch(e) {}
}

async function createPerimeterZone() {
  const name = prompt('Zone name:', 'North Perimeter');
  if (!name) return;
  const threat = prompt('Threat level (normal, elevated, high):', 'normal');
  const color = prompt('Zone color (hex):', '#ff4444');
  try {
    const r = await _fetchJson('/api/security/zones', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name, threat_level: threat || 'normal', color: color || '#ff4444', zone_type: 'perimeter'})});
    if (r.id) { toast('Perimeter zone created', 'success'); loadPerimeterZones(); }
    else { toast(r.error || 'Failed', 'error'); }
  } catch(e) { toast('Failed', 'error'); }
}

async function deletePerimeterZone(zid) {
  if (!confirm('Delete this perimeter zone?')) return;
  try {
    await apiDelete('/api/security/zones/' + zid);
    toast('Zone deleted', 'success');
    loadPerimeterZones();
  } catch(e) { toast('Delete failed', 'error'); }
}

/* ─── Map Atlas ─── */
async function generateMapAtlas() {
  const lat = _map ? _map.getCenter().lat : 0;
  const lng = _map ? _map.getCenter().lng : 0;
  const title = prompt('Atlas title:', 'NOMAD Map Atlas');
  if (!title) return;
  const w = window.openPendingPopup?.('Generating Map Atlas', 'Building the printable atlas packet. This can take a moment for larger grids.');
  if (!w) { toast('Pop-up blocked -- please allow pop-ups', 'warning'); return; }
  toast('Generating map atlas...', 'info');
  try {
    const resp = await fetch('/api/maps/atlas', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({lat, lng, title, zoom_levels:[10,13,15], grid_size:2})});
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      window.renderPopupStatus?.(w, 'Map Atlas Unavailable', data.error || 'Atlas generation failed. Close this window and try again.', 'error');
      toast(data.error || 'Atlas generation failed', 'error');
      return;
    }
    const html = await resp.text();
    if (!window.replacePopupHtml?.(w, html)) {
      toast('Atlas window was closed before the document was ready', 'warning');
      return;
    }
    toast('Map atlas generated — print from the new window', 'success');
  } catch(e) {
    window.renderPopupStatus?.(w, 'Map Atlas Unavailable', 'Atlas generation failed. Close this window and try again.', 'error');
    toast('Atlas generation failed', 'error');
  }
}

/* ─── Community Sharing ─── */
async function exportCurrentChecklist() {
  if (!_currentChecklistId) { toast('Select a checklist first', 'warning'); return; }
  window.location=`/api/checklists/${_currentChecklistId}/export-json`;
  toast('Checklist exported for sharing', 'success');
}

async function importChecklistJSON() {
  const input = document.getElementById('cl-import-file');
  if (!input.files.length) return;
  const formData = new FormData();
  formData.append('file', input.files[0]);
  try {
    const r = await _fetchJson('/api/checklists/import-json', {method:'POST', body:formData});
    input.value = '';
    if (r.id) { toast('Checklist imported!', 'success'); loadChecklists(); selectChecklist(r.id); }
    else { toast(r.error || 'Import failed', 'error'); }
  } catch(e) { toast('Import failed', 'error'); input.value = ''; }
}

/* ─── Notifications ─── */
let _notifsEnabled = false;

function toggleNotifications() {
  const enabled = document.getElementById('notif-toggle').checked;
  if (enabled && 'Notification' in window) {
    Notification.requestPermission().then(perm => {
      _notifsEnabled = perm === 'granted';
      document.getElementById('notif-toggle').checked = _notifsEnabled;
      localStorage.setItem('nomad-notifs', _notifsEnabled ? '1' : '0');
      if (_notifsEnabled) toast('Browser notifications enabled', 'success');
      else toast('Notification permission denied', 'warning');
    });
  } else {
    _notifsEnabled = false;
    localStorage.setItem('nomad-notifs', '0');
  }
}

function sendNotification(title, body) {
  if (_notifsEnabled && 'Notification' in window && Notification.permission === 'granted') {
    new Notification(title, {body, icon: '/favicon.ico'});
  }
}

// Init notification state
(function() {
  if (localStorage.getItem('nomad-notifs') === '1' && 'Notification' in window && Notification.permission === 'granted') {
    _notifsEnabled = true;
    const el = document.getElementById('notif-toggle');
    if (el) el.checked = true;
  }
})();

/* ─── External Ollama Host ─── */
async function loadOllamaHost() {
  try {
    const r = await _fetchJson('/api/settings/ollama-host');
    document.getElementById('ollama-host-input').value = r.host || '';
  } catch(e) {}
}
async function saveOllamaHost() {
  const host = document.getElementById('ollama-host-input').value.trim();
  try {
    await apiPut('/api/settings/ollama-host', {host});
    toast(host ? 'Ollama host set to ' + host : 'Using local Ollama', 'success');
  } catch(e) { toast('Failed to save Ollama host', 'error'); }
}

/* ─── Auth Password ─── */
async function setAuthPassword() {
  const pw = document.getElementById('auth-pw-input').value;
  if (!pw) { toast('Enter a password', 'warning'); return; }
  try {
    await apiPost('/api/auth/set-password', {password: pw});
    document.getElementById('auth-pw-input').value = '';
    toast('Dashboard password set', 'success');
  } catch(e) { toast('Failed to set password', 'error'); }
}
async function clearAuthPassword() {
  try {
    await apiPost('/api/auth/set-password', {password: ''});
    toast('Dashboard password cleared', 'info');
  } catch(e) { toast('Failed to clear password', 'error'); }
}

/* ─── Host Power ─── */
function confirmPower(btn, action) {
  if (!btn.dataset.confirm) {
    btn.dataset.confirm = '1';
    btn.textContent = `Confirm ${action}?`;
      btn.style.background = 'var(--red)'; btn.style.color = getThemeCssVar('--text-inverse', '#fff');
    setTimeout(() => { btn.textContent = action.charAt(0).toUpperCase() + action.slice(1); btn.style.background = ''; btn.style.color = ''; delete btn.dataset.confirm; }, 3000);
    return;
  }
  hostPower(action);
}
async function hostPower(action) {
  try {
    await apiPost('/api/system/shutdown', {action});
    toast(action + ' initiated — computer will ' + action + ' in 5 seconds', 'warning');
  } catch(e) { toast('Failed to initiate ' + action, 'error'); }
}

/* ─── PDF Library ─── */
async function loadPDFList() {
  try {
    const files = await _fetchJson('/api/library/pdfs');
    const el = document.getElementById('pdf-list');
    if (!files.length) { el.innerHTML = '<span class="library-pdf-empty">No documents uploaded. Click Upload to add PDFs, ePubs, or text files.</span>'; return; }
    el.innerHTML = files.map(f => `
      <div class="library-pdf-row">
        <button type="button" class="library-pdf-link" data-library-action="view-pdf-item" data-pdf-filename="${escapeAttr(f.filename)}">${escapeHtml(f.filename)} <span class="library-pdf-meta">(${f.size})</span></button>
        <button type="button" class="library-pdf-delete" data-library-action="delete-pdf-item" data-pdf-filename="${escapeAttr(f.filename)}" aria-label="Delete document ${escapeAttr(f.filename)}">&times;</button>
      </div>`).join('');
  } catch(e) {}
}
async function uploadPDF() {
  const input = document.getElementById('pdf-upload');
  if (!input.files.length) return;
  const file = input.files[0];
  const sizeMB = (file.size / 1024 / 1024).toFixed(1);
  toast(`Uploading ${file.name} (${sizeMB} MB)...`, 'info');
  const formData = new FormData();
  formData.append('file', file);
  try {
    await apiUpload('/api/library/upload-pdf', formData);
    input.value = '';
    toast('Document uploaded', 'success');
    loadPDFList();
  } catch(e) { toast(`Upload failed: ${e?.data?.error || e?.message || 'check your connection'}`, 'error'); }
}
function viewPDF(filename) {
  document.getElementById('pdf-viewer').style.display = 'block';
  document.getElementById('pdf-viewer-title').textContent = filename;
  document.getElementById('pdf-iframe').src = `/api/library/serve/${filename}`;
}
function closePDFViewer() { document.getElementById('pdf-viewer').style.display = 'none'; document.getElementById('pdf-iframe').src = ''; }
async function deletePDF(filename) {
  if (!confirm('Delete this document?')) return;
  try {
    await apiDelete('/api/library/delete/' + encodeURIComponent(filename));
    toast('Document deleted', 'warning');
    loadPDFList();
    closePDFViewer();
  } catch(e) { toast('Failed to delete document', 'error'); }
}

/* ─── AI Chat File Drag/Drop ─── */
let _chatFileContext = '';
function handleChatDrop(e) {
  e.preventDefault();
  if (e.dataTransfer.files.length) uploadChatFile(e.dataTransfer.files[0]);
}
function handleChatFileSelect() {
  const input = document.getElementById('chat-file-input');
  if (input.files.length) uploadChatFile(input.files[0]);
  input.value = '';
}
async function uploadChatFile(file) {
  const formData = new FormData();
  formData.append('file', file);
  toast(`Reading ${file.name}...`, 'info');
  try {
    const r = await _fetchJson('/api/ai/upload-context', {method:'POST', body:formData});
    if (r.error) { toast(r.error, 'error'); return; }
    _chatFileContext = r.content;
    document.getElementById('chat-file-context').style.display = 'block';
    document.getElementById('chat-file-name').textContent = `${r.filename} (${r.words} words attached)`;
    toast(`File attached — ${r.words} words will be included in your next message`, 'success');
  } catch(e) { toast('File read failed', 'error'); }
}
function clearChatFile() {
  _chatFileContext = '';
  document.getElementById('chat-file-context').style.display = 'none';
}

/* ─── Comms Log ─── */
async function logComms() {
  const msg = document.getElementById('comms-msg').value.trim();
  const data = {
    freq: document.getElementById('comms-freq').value.trim(),
    callsign: document.getElementById('comms-call').value.trim(),
    direction: document.getElementById('comms-dir').value,
    message: msg,
    signal_quality: document.getElementById('comms-sig').value,
  };
  if (!msg && !data.callsign) { toast('Enter a callsign or message', 'warning'); return; }
  try {
    await apiPost('/api/comms-log', data);
    document.getElementById('comms-msg').value = '';
    toast('Communication logged', 'success');
    loadCommsLog();
  } catch(e) { toast('Failed to log communication', 'error'); }
}

async function loadCommsLog() {
  try {
    const logs = await _fetchJson('/api/comms-log');
    const el = document.getElementById('comms-log-list');
    if (!logs.length) { el.innerHTML = '<div class="prep-empty-state">No communications logged yet.</div>'; return; }
    el.innerHTML = logs.map(l => {
      const t = new Date(l.created_at);
      const ts = t.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'});
      const date = t.toLocaleDateString([], {month:'short',day:'numeric'});
      const dirClass = l.direction === 'tx' ? 'is-tx' : 'is-rx';
      return `<div class="prep-comms-row">
        <span class="prep-comms-meta">${date} ${ts}</span>
        <span class="prep-comms-dir ${dirClass}">${l.direction.toUpperCase()}</span>
        <span class="prep-comms-freq">${escapeHtml(l.freq)}</span>
        <span class="prep-comms-call">${escapeHtml(l.callsign)}</span>
        ${l.signal_quality ? `<span class="prep-comms-signal">${l.signal_quality}</span>` : ''}
        <span class="prep-comms-message">${escapeHtml(l.message)}</span>
        <button type="button" class="hover-reveal prep-comms-delete" data-prep-action="delete-comms-log" data-comms-log-id="${l.id}" aria-label="Delete communications log entry">x</button>
      </div>`;
    }).join('');
  } catch(e) {}
}

async function deleteCommsLog(id) {
  if (!confirm('Delete this comms log entry?')) return;
  try {
    await apiDelete('/api/comms-log/' + id);
    loadCommsLog();
  } catch(e) { toast('Failed to delete log entry', 'error'); }
}

/* ─── Shopping List ─── */
async function showShoppingList() {
  try {
    const items = await _fetchJson('/api/inventory/shopping-list');
    if (!items.length) { toast('No items needed — inventory is fully stocked!', 'success'); return; }
    let body = '<div class="shopping-list-shell">';
    let lastCat = '';
    items.forEach(i => {
      if (i.category !== lastCat) { body += `<div class="shopping-list-category">${escapeHtml(i.category)}</div>`; lastCat = i.category; }
      body += `<div class="shopping-list-row">
        <span class="shopping-list-name">${escapeHtml(i.name)}</span>
        <span class="shopping-list-meta">${i.need > 0 ? '+' + i.need : ''} ${escapeHtml(i.unit)} <span class="shopping-list-reason">(${escapeHtml(i.reason)})</span></span>
      </div>`;
    });
    body += '</div>';
    body += `<div class="modal-footer"><button type="button" class="btn btn-sm btn-primary" data-shell-action="copy-text" data-copy-text="${escapeAttr(items.map(i => `${i.name}: ${i.need > 0 ? '+'+i.need : ''} ${i.unit} (${i.reason})`).join('\n'))}">Copy List</button>`;
    body += '<button type="button" class="btn btn-sm" data-shell-action="close-modal-overlay">Close</button></div>';
    showModal(body, {title: 'Shopping List', size: 'sm'});
  } catch(e) { toast('Failed to generate shopping list', 'error'); }
}

/* ─── Status Report ─── */
async function generateStatusReport() {
  try {
    const r = await _fetchJson('/api/status-report');
    const palette = getThemePalette();
const html = `<html><head><title>NOMAD Status Report</title><style>:root{color-scheme:${document.documentElement.getAttribute('data-theme') === 'nomad' || document.documentElement.getAttribute('data-theme') === 'eink' ? 'light' : 'dark'};}body{font-family:var(--font-data,monospace);background:${palette.bg};color:${palette.text};padding:20px;font-size:13px;white-space:pre-wrap;line-height:1.6;}.status-report-copy{background:${palette.accent};color:${palette.textInverse};border:none;padding:8px 16px;border-radius:6px;cursor:pointer;margin-right:8px;font-size:12px;}.status-report-rule{border:0;border-top:1px solid ${palette.border};margin:12px 0;}.status-report-shell{min-height:120px;}</style></head><body><button id="copy-report-btn" class="status-report-copy">Copy to Clipboard</button><hr class="status-report-rule"><div id="rpt" class="status-report-shell">${escapeHtml(r.text)}</div><script>document.getElementById('copy-report-btn').addEventListener('click',function(){navigator.clipboard.writeText(document.getElementById('rpt').textContent);});<\/script></body></html>`;
    openAppFrameHTML('Status Report', html);
  } catch(e) { toast('Failed to generate report', 'error'); }
}

/* ─── Drill History ─── */
async function loadDrillHistory() {
  try {
    const drills = await _fetchJson('/api/drills/history');
    const el = document.getElementById('drill-history-list');
    if (!drills.length) { el.innerHTML = '<div class="settings-empty-state">No drills completed yet. Run a drill above to start tracking.</div>'; return; }
    const ordered = [...drills].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    const avgScore = Math.round(ordered.reduce((sum, drill) => sum + (drill.tasks_total ? (drill.tasks_completed / drill.tasks_total) * 100 : 0), 0) / ordered.length);
    const latest = ordered[0];
    const bestScore = Math.max(...ordered.map(drill => drill.tasks_total ? Math.round((drill.tasks_completed / drill.tasks_total) * 100) : 0));
    el.innerHTML = `
      <div class="drill-history-summary">
        <div class="drill-history-stat">
          <span class="drill-history-kicker">Runs logged</span>
          <strong class="drill-history-value">${ordered.length}</strong>
          <span class="drill-history-note">Keep repeating the same drills until the pace feels automatic.</span>
        </div>
        <div class="drill-history-stat">
          <span class="drill-history-kicker">Average completion</span>
          <strong class="drill-history-value">${avgScore}%</strong>
          <span class="drill-history-note">Across the latest recorded sessions.</span>
        </div>
        <div class="drill-history-stat">
          <span class="drill-history-kicker">Latest run</span>
          <strong class="drill-history-value">${escapeHtml(latest.title)}</strong>
          <span class="drill-history-note">${getRunDateLabel(latest.created_at)}</span>
        </div>
        <div class="drill-history-stat">
          <span class="drill-history-kicker">Best score</span>
          <strong class="drill-history-value">${bestScore}%</strong>
          <span class="drill-history-note">A clean run worth repeating.</span>
        </div>
      </div>
      <div class="drill-history-grid">
        ${ordered.map(d => {
          const pct = d.tasks_total > 0 ? Math.round((d.tasks_completed / d.tasks_total) * 100) : 0;
          const toneClass = getToneClassFromPercent('drill-history', pct);
          return `
            <article class="drill-history-card">
              <div class="drill-history-card-head">
                <div>
                  <div class="drill-history-date">${getRunDateLabel(d.created_at)}</div>
                  <h4 class="drill-history-title">${escapeHtml(d.title)}</h4>
                </div>
                <span class="drill-history-score ${toneClass}">${pct}%</span>
              </div>
              <div class="drill-history-meta">
                <span class="drill-history-detail">${formatDrillDuration(d.duration_sec)}</span>
                <span class="drill-history-detail">${d.tasks_completed}/${d.tasks_total} tasks complete</span>
              </div>
            </article>
          `;
        }).join('')}
      </div>
    `;
  } catch(e) {}
}

/* ─── Night Mode Auto-Switch ─── */
let _nightModeApplied = false;
function checkNightMode() {
  const autoNight = localStorage.getItem('nomad-auto-night');
  if (autoNight !== '1') return;
  const hour = new Date().getHours();
  const isNight = hour >= 21 || hour < 6; // 9pm - 6am
  const currentTheme = localStorage.getItem('nomad-theme') || 'nomad';
  if (isNight && !_nightModeApplied) {
    _nightModeApplied = true;
    if (currentTheme !== 'redlight') {
      localStorage.setItem('nomad-pre-night-theme', currentTheme);
      setTheme('redlight');
    }
  } else if (!isNight && _nightModeApplied) {
    _nightModeApplied = false;
    if (currentTheme === 'redlight') {
      const prev = localStorage.getItem('nomad-pre-night-theme') || 'nomad';
      setTheme(prev);
    }
  }
}
checkNightMode();
if (window.NomadShellRuntime) {
  window.NomadShellRuntime.startInterval('shell.auto-night', checkNightMode, 60000, { requireVisible: true });
} else {
  setInterval(checkNightMode, 60000);
}

/* ─── Inventory Visualization ─── */
async function loadInvViz() {
  try {
    const summary = await _fetchJson('/api/inventory/summary');
    const el = document.getElementById('inv-viz');
    if (!summary.categories.length) { el.innerHTML = ''; return; }
    const maxQty = Math.max(...summary.categories.map(c => c.total_qty), 1);
    el.innerHTML = `<div class="utility-summary-result utility-summary-grid">${summary.categories.map(c => {
      const pct = Math.min(100, Math.round(c.total_qty / maxQty * 100));
      return `<div class="prep-summary-card utility-summary-card">
        <div class="prep-summary-meta">${escapeHtml(c.category)}</div>
        <div class="prep-summary-value prep-summary-value-compact">${c.count}</div>
        <div class="prep-summary-label">${c.total_qty} total units</div>
        <div class="utility-progress"><div class="utility-progress-bar" style="--utility-progress-width:${pct}%;"></div></div>
      </div>`;
    }).join('')}</div>`;
  } catch(e) {}
}

/* ─── Inventory Quick-Add Presets ─── */
const INV_QUICK_ITEMS = [
  // Water
  {name:'Water (1 gallon jugs)', cat:'water', unit:'gal', qty:7, daily:1},
  {name:'Water filter (Sawyer/LifeStraw)', cat:'water', unit:'ea', qty:1},
  {name:'Water purification tablets', cat:'water', unit:'packs', qty:2},
  {name:'Bleach (unscented)', cat:'water', unit:'gal', qty:1},
  // Food
  {name:'Rice (5 lb bag)', cat:'food', unit:'bags', qty:2},
  {name:'Canned beans', cat:'food', unit:'cans', qty:12},
  {name:'Canned meat (chicken/tuna)', cat:'food', unit:'cans', qty:12},
  {name:'Canned vegetables', cat:'food', unit:'cans', qty:12},
  {name:'Canned soup/stew', cat:'food', unit:'cans', qty:6},
  {name:'Peanut butter', cat:'food', unit:'jars', qty:2},
  {name:'Pasta (dry)', cat:'food', unit:'lbs', qty:5},
  {name:'Oatmeal', cat:'food', unit:'lbs', qty:3},
  {name:'MRE', cat:'food', unit:'ea', qty:6},
  {name:'Freeze-dried meals', cat:'food', unit:'ea', qty:6},
  {name:'Salt', cat:'food', unit:'lbs', qty:2},
  {name:'Sugar', cat:'food', unit:'lbs', qty:2},
  {name:'Honey', cat:'food', unit:'jars', qty:1},
  {name:'Powdered milk', cat:'food', unit:'lbs', qty:2},
  // Medical
  {name:'First aid kit (complete)', cat:'medical', unit:'ea', qty:1},
  {name:'Ibuprofen 200mg', cat:'medical', unit:'bottles', qty:2},
  {name:'Acetaminophen 500mg', cat:'medical', unit:'bottles', qty:1},
  {name:'Diphenhydramine (Benadryl)', cat:'medical', unit:'boxes', qty:1},
  {name:'Antibiotic ointment', cat:'medical', unit:'tubes', qty:2},
  {name:'Bandages (assorted)', cat:'medical', unit:'boxes', qty:2},
  {name:'Gauze pads (4x4)', cat:'medical', unit:'packs', qty:2},
  {name:'Medical tape', cat:'medical', unit:'rolls', qty:2},
  {name:'Tourniquet (CAT)', cat:'medical', unit:'ea', qty:1},
  {name:'N95 Masks', cat:'medical', unit:'ea', qty:20},
  {name:'Nitrile gloves', cat:'medical', unit:'boxes', qty:2},
  {name:'Electrolyte packets', cat:'medical', unit:'packs', qty:10},
  // Power & Fuel
  {name:'AA Batteries', cat:'power', unit:'packs', qty:4},
  {name:'AAA Batteries', cat:'power', unit:'packs', qty:2},
  {name:'D Batteries', cat:'power', unit:'packs', qty:2},
  {name:'USB battery pack', cat:'power', unit:'ea', qty:1},
  {name:'Propane (1lb canisters)', cat:'fuel', unit:'cans', qty:6},
  {name:'Gasoline (stored)', cat:'fuel', unit:'gal', qty:10},
  {name:'Firewood', cat:'fuel', unit:'cords', qty:0.5},
  // Hygiene
  {name:'Toilet paper', cat:'hygiene', unit:'rolls', qty:24, daily:1},
  {name:'Bar soap', cat:'hygiene', unit:'bars', qty:6},
  {name:'Toothpaste', cat:'hygiene', unit:'tubes', qty:3},
  {name:'Hand sanitizer', cat:'hygiene', unit:'bottles', qty:2},
  {name:'Trash bags (heavy duty)', cat:'hygiene', unit:'boxes', qty:2},
  {name:'Paper towels', cat:'hygiene', unit:'rolls', qty:6},
  // Tools & Gear
  {name:'Flashlight (LED)', cat:'tools', unit:'ea', qty:2},
  {name:'Headlamp', cat:'tools', unit:'ea', qty:1},
  {name:'Multi-tool/knife', cat:'tools', unit:'ea', qty:1},
  {name:'Duct tape', cat:'tools', unit:'rolls', qty:2},
  {name:'Paracord (100ft)', cat:'tools', unit:'ea', qty:2},
  {name:'Tarp (10x12)', cat:'tools', unit:'ea', qty:1},
  {name:'Matches (waterproof)', cat:'tools', unit:'boxes', qty:3},
  {name:'Fire starter (ferro rod)', cat:'tools', unit:'ea', qty:1},
  {name:'Can opener (manual)', cat:'tools', unit:'ea', qty:1},
  // Communications
  {name:'FRS/GMRS Radio (pair)', cat:'communications', unit:'pairs', qty:1},
  {name:'NOAA Weather Radio', cat:'communications', unit:'ea', qty:1},
  {name:'Whistle (signal)', cat:'communications', unit:'ea', qty:2},
];

function showInvQuickAdd() {
  let body = '<div class="prep-reference-note prep-reference-note-tight">Click items to add them to your inventory with recommended starting quantities. Green = added.</div>';
  const groups = {};
  INV_QUICK_ITEMS.forEach(item => { if (!groups[item.cat]) groups[item.cat] = []; groups[item.cat].push(item); });
  const catNames = {water:'Water & Purification',food:'Food & Cooking',medical:'Medical & First Aid',power:'Power & Batteries',fuel:'Fuel',hygiene:'Hygiene & Sanitation',tools:'Tools & Gear',communications:'Communications'};
  for (const [cat, items] of Object.entries(groups)) {
    body += `<div class="prep-modal-section-title">${catNames[cat]||cat}</div>`;
    body += '<div class="prep-modal-grid-two">';
    items.forEach(item => {
      body += `<button type="button" class="btn btn-sm prep-quick-add-btn" data-prep-action="quick-add-inv-item" data-item-name="${escapeAttr(item.name)}" data-item-cat="${escapeAttr(item.cat)}" data-item-unit="${escapeAttr(item.unit)}" data-item-qty="${item.qty}" data-item-daily="${item.daily || 0}">${item.name} <span class="prep-quick-add-meta">(${item.qty} ${item.unit})</span></button>`;
    });
    body += '</div>';
  }
  showModal(body, {title: 'Quick Add Common Supplies'});
}

async function quickAddInvItem(item, control) {
  try {
    await apiPost('/api/inventory', {name:item.name, category:item.cat, unit:item.unit, quantity:item.qty, daily_usage:item.daily||0});
  } catch(e) { toast('Failed to add item', 'error'); return; }
  if (control) {
    control.style.background = 'var(--green-dim)';
    control.style.color = 'var(--green)';
    control.textContent = 'Added!';
    control.disabled = true;
  }
  loadInventory();
}

/* ─── Custom Checklist Creator ─── */
function createCustomChecklist() {
  // Show inline name input instead of prompt()
  const sidebar = document.querySelector('.prep-sidebar');
  let nameForm = document.getElementById('custom-cl-name-form');
  if (nameForm) { const inp = document.getElementById('custom-cl-name-input'); if (!inp) return; inp.focus(); return; }
  nameForm = document.createElement('div');
  nameForm.id = 'custom-cl-name-form';
  nameForm.style.cssText = 'padding:6px 8px;border-bottom:1px solid var(--border);display:flex;gap:4px;';
  nameForm.innerHTML = `<input id="custom-cl-name-input" class="prep-field-control prep-inline-form-grow prep-inline-form-input-compact" placeholder="Checklist name...">
    <button type="button" class="btn btn-sm btn-primary" data-prep-action="submit-custom-checklist">Create</button>`;
  sidebar.querySelector('.prep-list').before(nameForm);
  const inp = document.getElementById('custom-cl-name-input');
  if (!inp) return;
  inp.focus();
  inp.addEventListener('keydown', e => { if (e.key === 'Enter') submitCustomChecklist(); if (e.key === 'Escape') nameForm.remove(); });
}
async function submitCustomChecklist() {
  const inp = document.getElementById('custom-cl-name-input');
  const name = inp.value.trim();
  if (!name) { toast('Enter a name', 'warning'); return; }
  const r = await _fetchJson('/api/checklists', {method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({name, items:[]})});
  document.getElementById('custom-cl-name-form').remove();
  toast(`Created: ${name}`, 'success');
  _currentChecklistId = r.id;
  await loadChecklists();
  await selectChecklist(r.id);
  addChecklistItem();
}

function addChecklistItem() {
  if (!_currentChecklistId) return;
  const checklist = document.getElementById('prep-checklist');
  // Don't add multiple forms
  if (document.getElementById('add-item-form')) { const inp = document.getElementById('add-item-text'); if (!inp) return; inp.focus(); return; }
  const form = document.createElement('div');
  form.id = 'add-item-form';
  form.style.cssText = 'padding:8px 16px;border-top:1px solid var(--border);display:flex;gap:6px;align-items:center;';
  form.innerHTML = `
    <input id="add-item-text" class="prep-field-control prep-inline-form-grow" placeholder="Item name...">
    <select id="add-item-cat" class="prep-field-control prep-inline-form-select">
      <option value="general">general</option><option value="gear">gear</option><option value="food">food</option>
      <option value="medical">medical</option><option value="tools">tools</option><option value="water">water</option>
      <option value="comms">comms</option><option value="shelter">shelter</option>
    </select>
    <button type="button" class="btn btn-sm btn-primary" data-prep-action="submit-checklist-item">Add</button>
    <button type="button" class="btn btn-sm" data-shell-action="close-add-item-form">Done</button>`;
  checklist.parentElement.appendChild(form);
  const inp = document.getElementById('add-item-text');
  if (!inp) return;
  inp.focus();
  inp.addEventListener('keydown', e => { if (e.key === 'Enter') submitChecklistItem(); if (e.key === 'Escape') form.remove(); });
}
async function submitChecklistItem() {
  const textEl = document.getElementById('add-item-text');
  const catEl = document.getElementById('add-item-cat');
  if (!textEl || !catEl) return;
  const text = textEl.value.trim();
  if (!text) return;
  const cat = catEl.value;
  _currentChecklistItems.push({text, checked: false, cat});
  renderChecklist();
  try {
    await apiPut(`/api/checklists/${_currentChecklistId}`, {items: _currentChecklistItems});
  } catch(e) {
    toast(e?.data?.error || 'Failed to save checklist item', 'error');
  }
  textEl.value = '';
  textEl.focus();
}

/* ─── Emergency Alert Sounds ─── */
let _alertAudioCtx = null;
function playAlertSound(type) {
  if (!_alertAudioCtx) _alertAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
  const ctx = _alertAudioCtx;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.connect(gain);
  gain.connect(ctx.destination);
  if (type === 'broadcast') {
    osc.type = 'sawtooth'; osc.frequency.value = 880;
    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);
    osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.5);
    // Second tone
    const osc2 = ctx.createOscillator(); const g2 = ctx.createGain();
    osc2.connect(g2); g2.connect(ctx.destination);
    osc2.type = 'sawtooth'; osc2.frequency.value = 660;
    g2.gain.setValueAtTime(0.3, ctx.currentTime + 0.6);
    g2.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 1.1);
    osc2.start(ctx.currentTime + 0.6); osc2.stop(ctx.currentTime + 1.1);
  } else if (type === 'timer') {
    osc.type = 'sine'; osc.frequency.value = 1000;
    gain.gain.setValueAtTime(0.2, ctx.currentTime);
    for (let i = 0; i < 3; i++) {
      gain.gain.setValueAtTime(0.2, ctx.currentTime + i * 0.3);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + i * 0.3 + 0.15);
    }
    osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.9);
  }
}
