"""Shared mutable state for NOMAD Field Desk routes.

This module holds all cross-route state (locks, caches, tracking dicts)
so that Flask Blueprints can import it without closure dependencies.
"""

import json
import queue
import threading
import time

# ─── Service Management ──────────────────────────────────────────────
_installing = set()
_installing_lock = threading.Lock()

# ─── AI Model Pull Queue ─────────────────────────────────────────────
_pull_queue = []
_pull_queue_active = False
_pull_queue_lock = threading.Lock()

# ─── Wizard Setup ────────────────────────────────────────────────────
_wizard_lock = threading.Lock()
_wizard_state = {
    'status': 'idle', 'phase': '', 'current_item': '', 'item_progress': 0,
    'overall_progress': 0, 'completed': [], 'errors': [], 'total_items': 0,
}

# ─── Offline Map Downloads ───────────────────────────────────────────
_map_downloads = {}  # {region_id: {'progress': 0-100, 'status': str, 'error': str|None}}

# ─── yt-dlp Media Downloads ──────────────────────────────────────────
_ytdlp_downloads = {}  # id -> {status, percent, title, speed, error}
_ytdlp_dl_counter = 0
_ytdlp_dl_lock = threading.Lock()
_ytdlp_install_state = {'status': 'idle', 'percent': 0, 'error': None}

# ─── Proactive Alert System ──────────────────────────────────────────
# Guarded by _state_lock (defined in web/app.py) for thread-safe access
_alert_check_running = False

# ─── Peer Discovery ──────────────────────────────────────────────────
_discovered_peers = {}

# ─── Auto Backup Timer ───────────────────────────────────────────────
_auto_backup_timer = {'timer': None}

# ─── Emergency Broadcast ─────────────────────────────────────────────
_broadcast = {'active': False, 'message': '', 'severity': 'info', 'timestamp': ''}

# ─── Self-Update Download ────────────────────────────────────────────
_update_state = {'status': 'idle', 'progress': 0, 'error': None, 'path': None}

# ─── Serial / Meshtastic ─────────────────────────────────────────────
_serial_state = {
    'connected': False, 'port': None, 'baud': None,
    'protocol': None, 'last_reading': None, 'error': None,
}
_serial_conn = {'conn': None}
_mesh_state = {
    'connected': False, 'node_count': 0, 'channel': 'LongFast',
    'my_node_id': '!local', 'firmware': None,
}

# ─── Motion Detection ────────────────────────────────────────────────
_motion_detectors = {}  # keyed by camera_id
_motion_config = {'threshold': 25, 'check_interval': 2, 'cooldown': 60}

# ─── RAG / Embedding ────────────────────────────────────────────────
_embed_state = {'status': 'idle', 'doc_id': None, 'progress': 0, 'detail': ''}

# ─── Auto-OCR Pipeline ───────────────────────────────────────────────
_ocr_pipeline_state = {'running': False, 'processed': 0, 'errors': 0, 'last_scan': None}
_ocr_processed_files = set()
_OCR_PROCESSED_MAX = 10000  # Cap to prevent unbounded memory growth

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
    triggering GeneratorExit.
    """
    now = time.time()
    with _sse_lock:
        stale = [
            q for q in _sse_clients
            if now - _sse_client_last_active.get(id(q), 0) > SSE_STALE_TIMEOUT
        ]
        for q in stale:
            _sse_clients.remove(q)
            _sse_client_last_active.pop(id(q), None)
    return len(stale)


def broadcast_event(event_type, data):
    """Send an event to all connected SSE clients."""
    message = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    now = time.time()
    with _sse_lock:
        dead = []
        for q in _sse_clients:
            try:
                q.put_nowait(message)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _sse_clients.remove(q)
            _sse_client_last_active.pop(id(q), None)
