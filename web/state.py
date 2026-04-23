"""Shared mutable state for NOMAD Field Desk routes.

This module holds all cross-route state (locks, caches, tracking dicts)
so that Flask Blueprints can import it without closure dependencies.
"""

import json
import queue
import threading
import time

# ─── API Response Cache ─────────────────────────────────────────────
_api_cache = {}
_cache_lock = threading.Lock()


def cached_get(key, ttl_seconds=30):
    """Return cached value if fresh, else None."""
    with _cache_lock:
        entry = _api_cache.get(key)
        if entry and (time.time() - entry['ts']) < ttl_seconds:
            return entry['val']
    return None


def cached_set(key, val):
    """Store a value in the TTL cache."""
    with _cache_lock:
        _api_cache[key] = {'val': val, 'ts': time.time()}
        if len(_api_cache) > 50:
            now = time.time()
            stale = [k for k, v in _api_cache.items() if now - v['ts'] > 120]
            for k in stale:
                del _api_cache[k]


# ─── Service Management ──────────────────────────────────────────────
_installing = set()
_installing_lock = threading.Lock()

# ─── AI Model Pull Queue ─────────────────────────────────────────────
_pull_queue = []
_pull_queue_active = False
_pull_queue_lock = threading.Lock()

# ─── Wizard Setup ────────────────────────────────────────────────────
_wizard_lock = threading.Lock()


def _wizard_default_state():
    return {
        'status': 'idle',
        'phase': '',
        'current_item': '',
        'item_progress': 0,
        'overall_progress': 0,
        'completed': [],
        'errors': [],
        'total_items': 0,
    }


def _wizard_copy_value(value):
    if isinstance(value, list):
        return list(value)
    if isinstance(value, dict):
        return dict(value)
    return value


def _wizard_snapshot_unlocked():
    return {key: _wizard_copy_value(value) for key, value in _wizard_state.items()}


_wizard_state = _wizard_default_state()


def wizard_reset(**updates):
    with _wizard_lock:
        _wizard_state.clear()
        _wizard_state.update(_wizard_default_state())
        for key, value in updates.items():
            _wizard_state[key] = _wizard_copy_value(value)
        return _wizard_snapshot_unlocked()


def wizard_update(**updates):
    with _wizard_lock:
        for key, value in updates.items():
            _wizard_state[key] = _wizard_copy_value(value)
        return _wizard_snapshot_unlocked()


def wizard_append_list_item(field, value):
    with _wizard_lock:
        current = _wizard_state.get(field)
        if not isinstance(current, list):
            current = []
            _wizard_state[field] = current
        current.append(value)
        return list(current)


def wizard_snapshot():
    with _wizard_lock:
        return _wizard_snapshot_unlocked()

# ─── Offline Map Downloads ───────────────────────────────────────────
_map_downloads = {}  # {region_id: {'progress': 0-100, 'status': str, 'error': str|None}}
_map_downloads_lock = threading.Lock()

# ─── yt-dlp Media Downloads ──────────────────────────────────────────
_ytdlp_downloads = {}  # id -> {status, percent, title, speed, error}
_ytdlp_dl_counter = 0
_ytdlp_dl_lock = threading.Lock()
_ytdlp_install_state = {'status': 'idle', 'percent': 0, 'error': None}

# ─── Proactive Alert System ──────────────────────────────────────────
_alert_lock = threading.Lock()
_alert_check_running = False


def try_begin_alert_check():
    global _alert_check_running
    with _alert_lock:
        if _alert_check_running:
            return False
        _alert_check_running = True
        return True


def set_alert_check_running(is_running):
    global _alert_check_running
    with _alert_lock:
        _alert_check_running = bool(is_running)

# ─── Peer Discovery ──────────────────────────────────────────────────
_discovered_peers = {}

# ─── Auto Backup Timer ───────────────────────────────────────────────
_auto_backup_timer = {'timer': None}

# ─── Emergency Broadcast ─────────────────────────────────────────────
_broadcast = {'active': False, 'message': '', 'severity': 'info', 'timestamp': ''}
_broadcast_lock = threading.Lock()


def get_broadcast():
    """Return a snapshot of the broadcast state under lock."""
    with _broadcast_lock:
        return dict(_broadcast)


def set_broadcast(active, message='', severity='info', timestamp=''):
    """Atomically update all broadcast fields under lock."""
    with _broadcast_lock:
        _broadcast['active'] = active
        _broadcast['message'] = message
        _broadcast['severity'] = severity
        _broadcast['timestamp'] = timestamp
        return dict(_broadcast)


# ─── Self-Update Download ────────────────────────────────────────────
_update_state = {'status': 'idle', 'progress': 0, 'error': None, 'path': None}
_update_state_lock = threading.Lock()


def get_update_state():
    with _update_state_lock:
        return dict(_update_state)


def set_update_state(**kwargs):
    with _update_state_lock:
        _update_state.update(kwargs)
        return dict(_update_state)


# ─── Serial / Meshtastic ─────────────────────────────────────────────
_serial_lock = threading.Lock()
_serial_state = {
    'connected': False, 'port': None, 'baud': None,
    'protocol': None, 'last_reading': None, 'error': None,
}
_serial_conn = {'conn': None}
_mesh_state = {
    'connected': False, 'node_count': 0, 'channel': 'LongFast',
    'my_node_id': '!local', 'firmware': None,
}


def get_serial_state():
    with _serial_lock:
        return dict(_serial_state)


def set_serial_state(**kwargs):
    with _serial_lock:
        _serial_state.update(kwargs)
        return dict(_serial_state)


def get_mesh_state():
    with _serial_lock:
        return dict(_mesh_state)


def set_mesh_state(**kwargs):
    with _serial_lock:
        _mesh_state.update(kwargs)
        return dict(_mesh_state)

# ─── Motion Detection ────────────────────────────────────────────────
_motion_detectors = {}  # keyed by camera_id
_motion_config = {'threshold': 25, 'check_interval': 2, 'cooldown': 60}

# ─── RAG / Embedding ────────────────────────────────────────────────
_embed_lock = threading.Lock()
_embed_state = {'status': 'idle', 'doc_id': None, 'progress': 0, 'detail': ''}


def get_embed_state():
    with _embed_lock:
        return dict(_embed_state)


def set_embed_state(**kwargs):
    with _embed_lock:
        _embed_state.update(kwargs)
        return dict(_embed_state)


# ─── Auto-OCR Pipeline ───────────────────────────────────────────────
_ocr_lock = threading.Lock()
_ocr_pipeline_state = {'running': False, 'processed': 0, 'errors': 0, 'last_scan': None}
_ocr_processed_files = set()
_OCR_PROCESSED_MAX = 10000  # Cap to prevent unbounded memory growth


def get_ocr_pipeline_state():
    with _ocr_lock:
        return dict(_ocr_pipeline_state)


def set_ocr_pipeline_state(**kwargs):
    with _ocr_lock:
        _ocr_pipeline_state.update(kwargs)
        return dict(_ocr_pipeline_state)


def ocr_check_and_add_file(file_key):
    """Atomically check whether file_key has been processed, and mark it if not.

    Returns True if the file is new (caller should process it), False if it
    was already tracked.  Also prunes the set when it exceeds the cap.
    """
    with _ocr_lock:
        if file_key in _ocr_processed_files:
            return False
        _ocr_processed_files.add(file_key)
        if len(_ocr_processed_files) > _OCR_PROCESSED_MAX:
            to_remove = list(_ocr_processed_files)[:len(_ocr_processed_files) // 2]
            _ocr_processed_files.difference_update(to_remove)
        return True


def ocr_increment_processed():
    with _ocr_lock:
        _ocr_pipeline_state['processed'] += 1


def ocr_increment_errors():
    with _ocr_lock:
        _ocr_pipeline_state['errors'] += 1

# ─── SSE Event Bus ────────────────────────────────────────────────────
from config import Config
MAX_SSE_CLIENTS = Config.MAX_SSE_CLIENTS
_sse_clients = []  # list of queue.Queue objects
_sse_client_last_active = {}  # queue id -> last activity timestamp
_sse_lock = threading.Lock()
SSE_STALE_TIMEOUT = 60  # seconds before a client is considered stale


def sse_register_client(q):
    """Register an SSE client queue and record its activity timestamp."""
    sse_cleanup_stale_clients()
    with _sse_lock:
        if len(_sse_clients) >= MAX_SSE_CLIENTS:
            return False
        _sse_clients.append(q)
        _sse_client_last_active[id(q)] = time.time()
        return True


def sse_unregister_client(q):
    """Remove an SSE client queue and its activity tracking."""
    with _sse_lock:
        if q in _sse_clients:
            _sse_clients.remove(q)
        _sse_client_last_active.pop(id(q), None)


def sse_touch_client(q):
    """Update last-activity timestamp for an SSE client."""
    with _sse_lock:
        _sse_client_last_active[id(q)] = time.time()


def sse_cleanup_stale_clients():
    """Remove SSE client queues that have been inactive for too long.

    Called periodically (e.g. from a background thread) to prevent
    leaked queues from accumulating when clients disconnect without
    triggering GeneratorExit. Queues that predate activity tracking are
    backfilled instead of being treated as instantly stale.
    """
    now = time.time()
    with _sse_lock:
        # Prune orphaned activity timestamps whose queue is no longer
        # registered. CPython recycles id() values for garbage-collected
        # objects, so a freshly-allocated queue can otherwise inherit a
        # stale timestamp from a prior queue with the same id() and be
        # incorrectly evicted on the next cleanup pass.
        current_ids = {id(q) for q in _sse_clients}
        for orphan_id in [k for k in _sse_client_last_active if k not in current_ids]:
            _sse_client_last_active.pop(orphan_id, None)
        stale = []
        for q in list(_sse_clients):
            queue_id = id(q)
            last_active = _sse_client_last_active.get(queue_id)
            if last_active is None:
                _sse_client_last_active[queue_id] = now
                continue
            if now - last_active > SSE_STALE_TIMEOUT:
                stale.append(q)
        for q in stale:
            _sse_clients.remove(q)
            _sse_client_last_active.pop(id(q), None)
    return len(stale)


def broadcast_event(event_type, data):
    """Send an event to all connected SSE clients.

    On queue back-pressure, drop the OLDEST queued message for that client and
    push the newest — evicting the entire client (the prior behaviour) meant
    one slow consumer could stop receiving updates forever after a single
    burst. Dropping the oldest message preserves the connection and keeps the
    client eventually consistent.
    """
    # Sanitize event_type: SSE event names must not contain newlines or colons.
    # A colon in an SSE `event:` line would be parsed as a field separator by
    # the browser's EventSource and mis-route the frame as a comment, so strip
    # it too. Also drop raw control characters — the SSE spec allows only
    # printable chars in field values.
    safe_type = (
        str(event_type)
        .replace('\n', '').replace('\r', '').replace(':', '')
        .strip()
    )
    if not safe_type:
        safe_type = 'message'
    try:
        payload = json.dumps(data)
    except (TypeError, ValueError):
        # Refuse to crash the broadcaster on un-serializable payloads.
        return
    message = f"event: {safe_type}\ndata: {payload}\n\n"
    with _sse_lock:
        for q in list(_sse_clients):
            try:
                q.put_nowait(message)
            except queue.Full:
                # Drop oldest, retry once; if still full, give up for this client.
                try:
                    q.get_nowait()
                except queue.Empty:
                    continue
                try:
                    q.put_nowait(message)
                except queue.Full:
                    pass
