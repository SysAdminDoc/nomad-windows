"""Flask web application — app factory + startup-only concerns.

Route families live in dedicated modules and get wired in by
``create_app()``:

- Workspace pages + i18n + render cache .................. web/pages.py
- Cross-module aggregation (needs/planner/readiness/…) ... web/aggregation.py
- NukeMap + VIPTrack static bundles ...................... web/bundled_assets.py
- Root + PWA (favicon/sw/offline snapshot+changes) ....... web/root_routes.py
- SSE event stream + test echo ........................... web/sse_routes.py
- 72 domain blueprints ................................... web/blueprint_registry.py
- Middleware (CSRF, rate limit, host, auth, headers) ..... web/middleware.py
- Background threads (discovery, auto-backup, SSE GC) .... web/background.py
- Deferred blueprint registration ........................ web/lazy_blueprints.py
"""

import os
import time
import threading
import logging
from flask import Flask

from config import Config
from db import init_db
from web.middleware import setup_middleware
from web.blueprint_registry import register_blueprints
from web.pages import register_pages
from web.aggregation import register_aggregation_routes
from web.bundled_assets import register_bundled_assets
from web.root_routes import register_root_routes
from web.background import start_discovery_listener, start_auto_backup, start_sse_cleanup
from web.sse_routes import register_sse_routes
from web.lazy_blueprints import LazyBlueprintDispatcher, DEFERRED_BLUEPRINTS
from services import ollama, kiwix, cyberchef, kolibri, qdrant, stirling, flatnotes

log = logging.getLogger('nomad.web')

# ─── Security Helpers ─────────────────────────────────────────────────

_db_bootstrap_lock = threading.Lock()
_db_bootstrap_done = False

SERVICE_MODULES = {
    'ollama': ollama,
    'kiwix': kiwix,
    'cyberchef': cyberchef,
    'kolibri': kolibri,
    'qdrant': qdrant,
    'stirling': stirling,
    'flatnotes': flatnotes,
}

VERSION = Config.VERSION

def set_version(v):
    global VERSION
    import re
    # Sanitize to prevent XSS — version must be semver-like (digits, dots, hyphens, letters)
    VERSION = re.sub(r'[^a-zA-Z0-9.\-+]', '', str(v)) or '0.0.0'

# _embed_state, _motion_detectors, _motion_config, _discovered_peers,
# _ocr_pipeline_state, _ocr_processed_files extracted to blueprints (imported from web.state there)
# EMBED_MODEL, CHUNK_SIZE, CHUNK_OVERLAP extracted to web/blueprints/kb.py

# Benchmark state moved to web/blueprints/benchmark.py

# Background CPU monitor — avoids blocking Flask threads with psutil.cpu_percent(interval=...)
_cpu_percent = 0

def _cpu_monitor():
    """Daemon thread: sample CPU usage without blocking request threads.

    ``psutil.cpu_percent(interval=2)`` blocks internally — if it ever raises
    (permission error on an unusual platform, psutil import failure after
    startup) we must NOT tight-loop: sleep between retries so a persistently
    failing sample doesn't peg a core.
    """
    global _cpu_percent
    try:
        import psutil as _ps
    except ImportError:
        return
    while True:
        try:
            _cpu_percent = _ps.cpu_percent(interval=2)
        except Exception:
            # Back off on failure so we don't spin
            time.sleep(2)

_cpu_monitor_started = False


def create_app():
    """Flask app factory — one-time bootstrap + route wiring.

    Keeps this function a thin orchestrator. Every concern that owns
    more than a handful of lines lives in its own module (see the
    module docstring up top for the map).
    """
    global _cpu_monitor_started, _db_bootstrap_done
    if not _db_bootstrap_done:
        with _db_bootstrap_lock:
            if not _db_bootstrap_done:
                init_db()
                _db_bootstrap_done = True
    if not _cpu_monitor_started:
        _cpu_monitor_started = True
        threading.Thread(target=_cpu_monitor, daemon=True).start()

    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')
    app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH
    # DEBUG off by default; set NOMAD_DEBUG=1 to enable for development
    app.config['DEBUG'] = os.environ.get('NOMAD_DEBUG', '0') == '1'
    if app.config['DEBUG']:
        log.warning('Debug mode enabled -- do not use in production')
    app.secret_key = Config.secret_key()

    setup_middleware(app)
    register_pages(app)

    # ─── Eager route wiring ───────────────────────────────────────────
    # Order: background work first (so alert engine / discovery listener
    # are live before the first request lands), then the route families,
    # then the 72-blueprint registry, then SSE, then the lazy-blueprint
    # dispatcher wraps the whole WSGI app last.
    from web.blueprints.preparedness import start_alert_engine  # noqa: F401 — engine side-effects
    start_alert_engine()
    from web.blueprints.scheduled_reports import _ensure_scheduler
    _ensure_scheduler()
    start_discovery_listener(app)
    start_auto_backup(app)

    register_aggregation_routes(app)
    register_bundled_assets(app)
    register_root_routes(app)
    register_blueprints(app)

    register_sse_routes(app)
    start_sse_cleanup(app)

    # ─── Lazy blueprints (H-09 / V8-11) ───────────────────────────────
    # Wrap AFTER all eager registrations so the dispatcher's forwarded call
    # resolves against the final Flask WSGI app.
    app.wsgi_app = LazyBlueprintDispatcher(app, DEFERRED_BLUEPRINTS)

    return app
