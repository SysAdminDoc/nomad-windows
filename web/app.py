"""Flask web application — dashboard and API routes."""

import json
import os
import sys
import time
import threading
import logging
import queue
from datetime import datetime
from flask import Flask, render_template, jsonify, request, Response
import web.state as _state
from web.state import (
    _auto_backup_timer,
    MAX_SSE_CLIENTS, _sse_clients, _sse_lock,
    broadcast_event,
    sse_register_client, sse_unregister_client, sse_touch_client,
    sse_cleanup_stale_clients,
)

from config import Config
from db import get_db_path, db_session, init_db
from web.sql_safety import safe_table
from web.utils import (
    check_origin as _check_origin,
    hash_local_secret as _hash_local_secret,
    is_loopback_addr as _is_loopback,
    local_secret_needs_rehash as _local_secret_needs_rehash,
    require_json_body as _require_json_body,
    safe_json_value as _safe_json_value,
    safe_json_list as _safe_json_list,
    read_household_size as _read_household_size_setting,
    verify_local_secret as _verify_local_secret,
)
from services import ollama, kiwix, cyberchef, kolibri, qdrant, stirling, flatnotes

log = logging.getLogger('nomad.web')

# ─── Security Helpers ─────────────────────────────────────────────────

_db_bootstrap_lock = threading.Lock()
_db_bootstrap_done = False
_discovery_listener_lock = threading.Lock()
_discovery_listener_started = False
_sse_cleanup_lock = threading.Lock()
_sse_cleanup_started = False

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

# ─── Build Bundle Manifest Helper ──────────────────────────────────────
_bundle_manifest = None
_bundle_manifest_mtime = None

def _load_bundle_manifest():
    """Read the esbuild build manifest (web/static/dist/manifest.json).

    Returns a dict mapping logical names to hashed filenames, e.g.
    {"nomad.bundle.js": "nomad.bundle.a1b2c3d4.js"}.
    Refreshes automatically when the manifest changes so rebuilt assets are
    served without requiring a process restart.
    """
    manifest_path = os.path.join(os.path.dirname(__file__), 'static', 'dist', 'manifest.json')
    global _bundle_manifest, _bundle_manifest_mtime
    try:
        manifest_mtime = os.path.getmtime(manifest_path)
        if _bundle_manifest is not None and _bundle_manifest_mtime == manifest_mtime:
            return _bundle_manifest
        with open(manifest_path, 'r') as f:
            _bundle_manifest = json.load(f)
        _bundle_manifest_mtime = manifest_mtime
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        _bundle_manifest = {}
        _bundle_manifest_mtime = None
    return _bundle_manifest

def create_app():
    global _cpu_monitor_started, _db_bootstrap_done
    global _discovery_listener_started, _sse_cleanup_started
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

    # HTTP methods that can mutate server state. Every CSRF/auth/rate-limit
    # guard must share this list — earlier versions missed PATCH.
    _MUTATING_METHODS = ('POST', 'PUT', 'PATCH', 'DELETE')

    # ─── Rate Limiting (optional) ─────────────────────────────────────
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address

        limiter = Limiter(
            app=app,
            key_func=get_remote_address,
            default_limits=[Config.RATELIMIT_DEFAULT],
            storage_uri='memory://',
        )

        @limiter.request_filter
        def _exempt_localhost():
            """Exempt localhost from rate limiting (desktop app)."""
            addr = get_remote_address()
            return _is_loopback(addr)

        # Stricter rate limit for POST/PUT/DELETE — audit H3.
        # Implemented as a per-client sliding-window counter so it actually
        # enforces (flask-limiter's shared_limit decorator only applies if
        # each route opts in, which none did). Localhost is exempt — the
        # check only matters when the desktop app is reached over LAN.
        import collections
        import threading as _th
        _mutating_window = int(os.environ.get('NOMAD_RATELIMIT_MUTATING_WINDOW', 60))
        _mutating_max = 60  # requests per window, per remote IP
        try:
            # parse "N/minute" form → N (60s window)
            _n, _per = Config.RATELIMIT_MUTATING.split('/')
            _mutating_max = int(_n.strip())
        except (ValueError, AttributeError):
            pass
        _mutating_hits = collections.defaultdict(collections.deque)
        _mutating_lock = _th.Lock()

        @app.before_request
        def _check_mutating_rate_limit():
            if request.method not in _MUTATING_METHODS:
                return
            addr = get_remote_address()
            if _is_loopback(addr):
                return
            now = time.time()
            cutoff = now - _mutating_window
            with _mutating_lock:
                q = _mutating_hits[addr]
                while q and q[0] < cutoff:
                    q.popleft()
                if len(q) >= _mutating_max:
                    from flask import jsonify as _j
                    return _j({'error': 'Rate limit exceeded for mutating requests',
                               'retry_after': _mutating_window}), 429
                q.append(now)
                # Prune empty deques to prevent unbounded memory growth from old IPs
                if len(_mutating_hits) > 500:
                    stale_addrs = [a for a, dq in _mutating_hits.items() if not dq]
                    for a in stale_addrs:
                        del _mutating_hits[a]

        app.extensions['limiter'] = limiter
    except ImportError:
        log.info('flask-limiter not installed — rate limiting disabled')

    # TTL cache moved to web.state (shared across blueprints)
    _cached = _state.cached_get
    _set_cache = _state.cached_set

    try:
        from web.translations import SUPPORTED_LANGUAGES, TRANSLATIONS
    except ImportError:
        from translations import SUPPORTED_LANGUAGES, TRANSLATIONS

    def _get_current_language():
        lang = 'en'
        try:
            with db_session() as db:
                row = db.execute("SELECT value FROM settings WHERE key = 'language'").fetchone()
                lang = (row['value'] if row else 'en') or 'en'
        except Exception:
            lang = 'en'
        return lang if lang in SUPPORTED_LANGUAGES else 'en'

    def _get_template_i18n_context():
        current_lang = _get_current_language()
        fallback_translations = TRANSLATIONS.get('en', {})
        current_translations = TRANSLATIONS.get(current_lang, fallback_translations)

        def _tr(key, default=''):
            return current_translations.get(key) or fallback_translations.get(key) or default or key

        return {
            'current_lang': current_lang,
            'is_rtl': current_lang == 'ar',
            'current_translations': current_translations,
            'fallback_translations': fallback_translations,
            'i18n_bootstrap': {
                'lang': current_lang,
                'translations': current_translations,
                'fallback': fallback_translations,
            },
            'tr': _tr,
        }

    @app.context_processor
    def _inject_i18n_context():
        return _get_template_i18n_context()

    # ─── CSRF Protection ─────────────────────────────────────────────
    @app.after_request
    def _set_cookie_samesite(response):
        """Set SameSite=Strict on all cookies for CSRF protection."""
        cookies = response.headers.getlist('Set-Cookie')
        if cookies:
            new_cookies = []
            for cookie in cookies:
                if 'SameSite' not in cookie:
                    cookie += '; SameSite=Strict'
                new_cookies.append(cookie)
            # Replace Set-Cookie headers
            response.headers.pop('Set-Cookie')
            for c in new_cookies:
                response.headers.add('Set-Cookie', c)
        return response

    # All HTTP methods that can change state must flow through the same
    # CSRF/auth/rate-limit guards. Audit found that earlier versions only
    # covered POST/PUT/DELETE — PATCH (and any future state-changing
    # methods) slipped through.
    _MUTATING_METHODS = ('POST', 'PUT', 'PATCH', 'DELETE')

    @app.before_request
    def _csrf_origin_check():
        """Block cross-origin state-changing requests."""
        if request.method in _MUTATING_METHODS:
            _check_origin(request)

    @app.before_request
    def _csrf_token_check():
        """Validate CSRF token on mutating requests (token-based CSRF layer)."""
        if request.method not in _MUTATING_METHODS:
            return
        # Exempt localhost from token-based CSRF
        remote = request.remote_addr or ''
        if _is_loopback(remote):
            return
        import hmac as _hmac
        from flask import session
        token = request.headers.get('X-CSRF-Token', '')
        expected = session.get('csrf_token', '')
        if not token or not expected or not _hmac.compare_digest(token, expected):
            from flask import abort
            abort(403, 'CSRF token missing or invalid')

    @app.route('/api/csrf-token')
    def api_csrf_token():
        """Generate and return a CSRF token for the current session."""
        import secrets as _secrets
        from flask import session
        if 'csrf_token' not in session:
            session['csrf_token'] = _secrets.token_hex(32)
        return jsonify({'csrf_token': session['csrf_token']})

    # ─── DB Connection Safety Net ─────────────────────────────────────
    # Auto-close any DB connections left open when a request ends.
    # This prevents connection leaks if a route raises before calling db.close().
    @app.teardown_appcontext
    def close_leaked_db(exception):
        """Auto-close DB connections stored on flask.g at end of request."""
        from flask import g
        db = g.pop('_db_conn', None)
        if db is not None:
            try:
                db.close()
            except Exception:
                pass

    # ─── Global API Error Handler ─────────────────────────────────────
    # Return consistent JSON for unhandled exceptions instead of HTML error pages.
    @app.errorhandler(Exception)
    def handle_unhandled_exception(e):
        """Catch-all: return JSON error for API routes, let others fall through."""
        if request.path.startswith('/api/'):
            status = getattr(e, 'code', 500) if hasattr(e, 'code') else 500
            log.warning(f'API error on {request.method} {request.path} ({status}): {e}')
            # Use generic messages — don't leak internal details
            _http_messages = {400: 'Bad request', 403: 'Forbidden', 404: 'Not found',
                              405: 'Method not allowed', 409: 'Conflict', 413: 'Payload too large',
                              429: 'Too many requests'}
            msg = _http_messages.get(status, 'Request error' if status < 500 else 'Internal server error')
            return jsonify({'error': msg}), status
        # Non-API routes: re-raise to let Flask's default handler render HTML
        raise e

    @app.errorhandler(404)
    def handle_404(e):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Not found'}), 404
        return e

    # ─── LAN Auth Guard ────────────────────────────────────────────────
    @app.before_request
    def check_lan_auth():
        """Require auth token for state-changing LAN requests when password is set.

        Must mirror ``_MUTATING_METHODS`` — an earlier revision only checked
        POST/PUT/DELETE, leaving PATCH as an unauthenticated back door on any
        route that accepts it.
        """
        if request.method not in _MUTATING_METHODS:
            return
        remote = request.remote_addr or ''
        if _is_loopback(remote):
            return
        # LAN request with mutating method — check if auth is enabled
        try:
            with db_session() as db:
                row = db.execute("SELECT value FROM settings WHERE key = 'auth_password'").fetchone()
            if row and row['value']:
                token = request.headers.get('X-Auth-Token', '')
                if not _verify_local_secret(token, row['value']):
                    return jsonify({'error': 'Authentication required'}), 403
                if _local_secret_needs_rehash(row['value']):
                    with db_session() as db:
                        db.execute(
                            "INSERT OR REPLACE INTO settings (key, value) VALUES ('auth_password', ?)",
                            (_hash_local_secret(token),)
                        )
                        db.commit()
        except Exception as e:
            log.warning(f'Auth check failed (denying access): {e}')
            return jsonify({'error': 'Auth check failed'}), 403

    @app.after_request
    def no_cache(response):
        """Prevent WebView2 from caching HTML/API responses."""
        if 'text/html' in response.content_type or 'application/json' in response.content_type:
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response

    # Hand-picked CSP for a single-origin desktop/LAN app. `unsafe-inline`
    # + `unsafe-eval` are required by the current UI (inline <script>/onclick
    # handlers, Leaflet/Cesium wasm). `blob:` and `data:` accommodate
    # offline tile previews and inline SVG favicons. Tightening further
    # would require a sweep across templates to remove inline handlers.
    _CSP_POLICY = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' blob:; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob: https:; "
        "font-src 'self' data:; "
        "connect-src 'self' blob: ws: http://127.0.0.1:* http://localhost:*; "
        "media-src 'self' blob:; "
        "worker-src 'self' blob:; "
        "frame-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    _EMBED_CSP_POLICY = _CSP_POLICY.replace("frame-ancestors 'none'; ", "frame-ancestors 'self'; ")

    @app.after_request
    def _set_security_headers(response):
        """Apply defense-in-depth response headers.

        X-Content-Type-Options blocks MIME sniffing; X-Frame-Options and
        CSP's frame-ancestors stop clickjacking (redundant by design —
        some engines honor only one); Referrer-Policy limits URL leakage
        on outbound links. CSP is only set on HTML so it doesn't break
        JSON/SSE clients that inspect response bodies.
        """
        # Always safe to set
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('Referrer-Policy', 'same-origin')
        response.headers.setdefault(
            'Permissions-Policy',
            'camera=(self), microphone=(self), geolocation=(self), '
            'interest-cohort=()',
        )
        is_same_origin_embed = request.path.startswith('/viptrack/')
        response.headers['X-Frame-Options'] = 'SAMEORIGIN' if is_same_origin_embed else 'DENY'
        ctype = response.content_type or ''
        if 'text/html' in ctype:
            response.headers['Content-Security-Policy'] = _EMBED_CSP_POLICY if is_same_origin_embed else _CSP_POLICY
        return response

    # ─── Pages ─────────────────────────────────────────────────────────

    workspace_pages = {
        'services': {
            'route': '/',
            'aliases': ['/home'],
            'title': 'Home',
            'partial': 'index_partials/_tab_services.html',
        },
        'situation-room': {
            'route': '/situation-room',
            'aliases': ['/briefing'],
            'title': 'Situation Room',
            'partial': 'index_partials/_tab_situation_room.html',
        },
        'readiness': {
            'route': '/readiness',
            'aliases': [],
            'title': 'Readiness',
            'partial': 'index_partials/_tab_readiness.html',
        },
        'preparedness': {
            'route': '/preparedness',
            'aliases': ['/operations'],
            'title': 'Preparedness',
            'partial': 'index_partials/_tab_preparedness.html',
        },
        'maps': {
            'route': '/maps',
            'aliases': [],
            'title': 'Maps',
            'partial': 'index_partials/_tab_maps.html',
        },
        'tools': {
            'route': '/tools',
            'aliases': [],
            'title': 'Tools',
            'partial': 'index_partials/_tab_tools.html',
        },
        'loadout': {
            'route': '/loadout',
            'aliases': [],
            'title': 'Loadout',
            'partial': 'index_partials/_tab_loadout.html',
        },
        'kiwix-library': {
            'route': '/library',
            'aliases': ['/knowledge'],
            'title': 'Library',
            'partial': 'index_partials/_tab_library.html',
        },
        'notes': {
            'route': '/notes',
            'aliases': [],
            'title': 'Notes',
            'partial': 'index_partials/_tab_notes.html',
        },
        'media': {
            'route': '/media',
            'aliases': [],
            'title': 'Media',
            'partial': 'index_partials/_tab_media.html',
        },
        'ai-chat': {
            'route': '/copilot',
            'aliases': ['/assistant'],
            'title': 'Copilot',
            'partial': 'index_partials/_tab_ai_chat.html',
        },
        'benchmark': {
            'route': '/diagnostics',
            'aliases': [],
            'title': 'Diagnostics',
            'partial': 'index_partials/_tab_benchmark.html',
        },
        'settings': {
            'route': '/settings',
            'aliases': ['/system'],
            'title': 'Settings',
            'partial': 'index_partials/_tab_settings.html',
        },
        'nukemap': {
            'route': '/nukemap-tab',
            'aliases': [],
            'title': 'NukeMap',
            'partial': 'index_partials/_tab_nukemap.html',
        },
        'viptrack': {
            'route': '/viptrack-tab',
            'aliases': [],
            'title': 'VIPTrack',
            'partial': 'index_partials/_tab_viptrack.html',
        },
        'training-knowledge': {
            'route': '/training-knowledge',
            'aliases': ['/training'],
            'title': 'Training & Knowledge',
            'partial': 'index_partials/_tab_training_knowledge.html',
        },
        'interoperability': {
            'route': '/interoperability',
            'aliases': ['/data-exchange'],
            'title': 'Interoperability',
            'partial': 'index_partials/_tab_interoperability.html',
        },
    }

    workspace_routes = {tab: meta['route'] for tab, meta in workspace_pages.items()}

    def _is_first_run_complete():
        try:
            with db_session() as db:
                row = db.execute("SELECT value FROM settings WHERE key = 'first_run_complete'").fetchone()
        except Exception:
            row = None
        value = (row['value'] if row else '') or ''
        return str(value).strip().lower() in ('1', 'true', 'yes', 'on')

    def _render_workspace_page(tab_id, allow_launch_restore=False):
        meta = workspace_pages[tab_id]
        manifest = _load_bundle_manifest()
        first_run_complete = _is_first_run_complete()
        return render_template(
            'workspace_page.html',
            version=VERSION,
            bundle_js=manifest.get('nomad.bundle.js', ''),
            bundle_css=manifest.get('nomad.bundle.css', ''),
            active_tab=tab_id,
            page_title=meta['title'],
            workspace_partial=meta['partial'],
            workspace_routes=workspace_routes,
            allow_launch_restore=allow_launch_restore,
            first_run_complete=first_run_complete,
            wizard_should_launch=(tab_id == 'services' and not first_run_complete),
        )

    @app.route('/app-runtime.js')
    def app_runtime_js():
        response = Response(
            render_template('index_partials/_app_inline.js', version=VERSION),
            mimetype='application/javascript',
        )
        response.headers['Cache-Control'] = (
            'no-cache' if app.config.get('DEBUG') else 'public, max-age=86400'
        )
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.route('/')
    def dashboard():
        return _render_workspace_page('services', allow_launch_restore=True)

    @app.route('/home')
    def home_page():
        return _render_workspace_page('services')

    @app.route('/situation-room')
    @app.route('/briefing')
    def situation_room_page():
        return _render_workspace_page('situation-room')

    @app.route('/readiness')
    def readiness_page():
        return _render_workspace_page('readiness')

    @app.route('/preparedness')
    @app.route('/operations')
    def preparedness_page():
        return _render_workspace_page('preparedness')

    @app.route('/maps')
    def maps_page():
        return _render_workspace_page('maps')

    @app.route('/tools')
    def tools_page():
        return _render_workspace_page('tools')

    @app.route('/loadout')
    def loadout_page():
        return _render_workspace_page('loadout')

    @app.route('/library')
    @app.route('/knowledge')
    def library_page():
        return _render_workspace_page('kiwix-library')

    @app.route('/notes')
    def notes_page():
        return _render_workspace_page('notes')

    @app.route('/media')
    def media_page():
        return _render_workspace_page('media')

    @app.route('/copilot')
    @app.route('/assistant')
    def copilot_page():
        return _render_workspace_page('ai-chat')

    @app.route('/diagnostics')
    def diagnostics_page():
        return _render_workspace_page('benchmark')

    @app.route('/settings')
    @app.route('/system')
    def settings_page():
        return _render_workspace_page('settings')

    @app.route('/nukemap-tab')
    def nukemap_tab_page():
        return _render_workspace_page('nukemap')

    @app.route('/viptrack-tab')
    def viptrack_tab_page():
        return _render_workspace_page('viptrack')

    @app.route('/training-knowledge')
    @app.route('/training')
    def training_knowledge_page():
        return _render_workspace_page('training-knowledge')

    @app.route('/interoperability')
    @app.route('/data-exchange')
    def interoperability_page():
        return _render_workspace_page('interoperability')

    # ─── Cross-Module Intelligence (Needs System) ─────────────────────

    SURVIVAL_NEEDS = {
        'water': {
            'label': 'Water & Hydration', 'icon': '\U0001F4A7', 'color': '#0288d1',
            'keywords': ['water','hydration','purif','filter','well','rain','cistern','dehydrat','boil','bleach','iodine','sodis','biosand'],
            'guides': ['water_purify','water_source_assessment'],
            'calcs': ['water-needs','water-storage','bleach-dosage'],
        },
        'food': {
            'label': 'Food & Nutrition', 'icon': '\U0001F372', 'color': '#558b2f',
            'keywords': ['food','calori','nutrition','canning','preserv','dehydrat','jerky','fermenting','seed','garden','harvest','livestock','chicken','goat','rabbit','grain','flour','rice','bean','MRE','freeze dry','smoking meat','salt cur'],
            'guides': ['food_preserve','food_safety_assessment'],
            'calcs': ['calorie-needs','food-storage','canning','composting','pasture'],
        },
        'medical': {
            'label': 'Medical & Health', 'icon': '\U0001FA79', 'color': '#c62828',
            'keywords': ['medical','first aid','wound','bleed','tourniquet','suture','fracture','burn','infection','antibiotic','medicine','triage','TCCC','CPR','AED','dental','eye','childbirth','diabetic','allergic','anaphyla','splint','vital','patient'],
            'guides': ['wound_assess','triage_start','antibiotic_selection','chest_trauma','envenomation','wound_infection','anaphylaxis','hypothermia_response'],
            'calcs': ['drug-dosage','burn-area','blood-loss','dehydration'],
        },
        'shelter': {
            'label': 'Shelter & Construction', 'icon': '\U0001F3E0', 'color': '#795548',
            'keywords': ['shelter','cabin','build','construct','adobe','timber','stone','masonry','insulation','roof','foundation','tent','tarp','debris hut','earthbag','cob','log'],
            'guides': ['shelter_build'],
            'calcs': ['shelter-sizing','insulation','concrete-mix'],
        },
        'security': {
            'label': 'Security & Defense', 'icon': '\U0001F6E1', 'color': '#d32f2f',
            'keywords': ['security','defense','perimeter','alarm','camera','night vision','firearm','ammo','ammunition','caliber','tactical','gray man','OPSEC','trip wire','home harden'],
            'guides': ['bugout_decision'],
            'calcs': ['ballistic','range','ammo-load'],
        },
        'comms': {
            'label': 'Communications', 'icon': '\U0001F4E1', 'color': '#6a1b9a',
            'keywords': ['radio','ham','amateur','frequency','antenna','HF','VHF','UHF','GMRS','FRS','MURS','Meshtastic','JS8Call','Winlink','APRS','morse','CW','SDR','repeater','net','callsign','comms','communication'],
            'guides': ['radio_setup'],
            'calcs': ['antenna-length','radio-range','power-budget'],
        },
        'power': {
            'label': 'Energy & Power', 'icon': '\u26A1', 'color': '#f9a825',
            'keywords': ['power','solar','battery','generator','inverter','watt','amp','volt','charge','fuel','diesel','propane','gasoline','wood gas','wind','hydro','off-grid','grid-down'],
            'guides': ['power_outage'],
            'calcs': ['solar-sizing','battery-bank','generator-fuel','wire-gauge'],
        },
        'navigation': {
            'label': 'Navigation & Maps', 'icon': '\U0001F310', 'color': '#0277bd',
            'keywords': ['map','compass','GPS','navigation','topographic','waypoint','route','bearing','MGRS','grid','coordinate','terrain','elevation','celestial','star','landmark'],
            'guides': [],
            'calcs': ['bearing','distance','pace-count','grid-to-latlong'],
        },
        'knowledge': {
            'label': 'Knowledge & Training', 'icon': '\U0001F4DA', 'color': '#37474f',
            'keywords': ['book','manual','reference','training','guide','course','encyclopedia','textbook','library','skill','learn','practice','drill'],
            'guides': [],
            'calcs': [],
        },
    }

    @app.route('/api/needs')
    def api_needs_overview():
        """Returns all survival need categories with item counts from each module."""
        cached = _cached('needs', 60)
        if cached:
            return jsonify(cached)
        with db_session() as db:
            result = {}
            for need_id, need in SURVIVAL_NEEDS.items():
                kw = need['keywords']
                # Count matching inventory items
                kw_inv = kw[:5]
                if kw_inv:
                    like_clauses = ' OR '.join(['name LIKE ? OR category LIKE ?' for _ in kw_inv])
                    like_vals = [v for k in kw_inv for v in (f'%{k}%', f'%{k}%')]
                    inv_count = db.execute(f'SELECT COUNT(*) as c FROM inventory WHERE {like_clauses}', like_vals).fetchone()['c']
                else:
                    inv_count = 0

                # Count matching contacts by skills/role
                kw_con = kw[:3]
                if kw_con:
                    like_clauses = ' OR '.join(['role LIKE ? OR skills LIKE ?' for _ in kw_con])
                    like_vals = [v for k in kw_con for v in (f'%{k}%', f'%{k}%')]
                    contact_count = db.execute(f'SELECT COUNT(*) as c FROM contacts WHERE {like_clauses}', like_vals).fetchone()['c']
                else:
                    contact_count = 0

                # Count matching books (from reference catalog)
                kw_book = kw[:3]
                if kw_book:
                    like_clauses = ' OR '.join(['title LIKE ? OR category LIKE ?' for _ in kw_book])
                    like_vals = [v for k in kw_book for v in (f'%{k}%', f'%{k}%')]
                    book_count = db.execute(f'SELECT COUNT(*) as c FROM books WHERE {like_clauses}', like_vals).fetchone()['c']
                else:
                    book_count = 0

                # Decision guides count
                guide_count = len(need.get('guides', []))

                result[need_id] = {
                    'label': need['label'], 'icon': need['icon'], 'color': need['color'],
                    'inventory': min(inv_count, 999), 'contacts': min(contact_count, 99),
                    'books': min(book_count, 99), 'guides': guide_count,
                    'total': min(inv_count + contact_count + book_count + guide_count, 9999),
                }
            _set_cache('needs', result)
            return jsonify(result)

    @app.route('/api/needs/<need_id>')
    def api_need_detail(need_id):
        """Returns detailed cross-module data for a specific survival need."""
        need = SURVIVAL_NEEDS.get(need_id)
        if not need:
            return jsonify({'error': 'Unknown need category'}), 404
        with db_session() as db:
            kw = need['keywords']
            like_clauses = ' OR '.join(['name LIKE ?' for _ in kw[:5]])
            like_vals = [f'%{k}%' for k in kw[:5]]

            # Inventory items
            kw_inv = kw[:5]
            if kw_inv:
                like_clauses = ' OR '.join(['name LIKE ? OR category LIKE ?' for _ in kw_inv])
                like_vals = [v for k in kw_inv for v in (f'%{k}%', f'%{k}%')]
                rows = db.execute(f'SELECT id, name, quantity, unit, category FROM inventory WHERE {like_clauses} LIMIT 100', like_vals).fetchall()
                seen_ids = set()
                inv_items = []
                for r in rows:
                    if r['id'] not in seen_ids:
                        seen_ids.add(r['id'])
                        inv_items.append(dict(r))
            else:
                inv_items = []

            # Contacts
            kw_con = kw[:3]
            if kw_con:
                like_clauses = ' OR '.join(['role LIKE ? OR skills LIKE ?' for _ in kw_con])
                like_vals = [v for k in kw_con for v in (f'%{k}%', f'%{k}%')]
                rows = db.execute(f'SELECT id, name, role, skills FROM contacts WHERE {like_clauses} LIMIT 30', like_vals).fetchall()
                seen_ids = set()
                contacts = []
                for r in rows:
                    if r['id'] not in seen_ids:
                        seen_ids.add(r['id'])
                        contacts.append(dict(r))
            else:
                contacts = []

            # Books
            kw_book = kw[:3]
            if kw_book:
                like_clauses = ' OR '.join(['title LIKE ? OR category LIKE ?' for _ in kw_book])
                like_vals = [v for k in kw_book for v in (f'%{k}%', f'%{k}%')]
                rows = db.execute(f'SELECT id, title, author, category FROM books WHERE {like_clauses} LIMIT 30', like_vals).fetchall()
                seen_ids = set()
                books = []
                for r in rows:
                    if r['id'] not in seen_ids:
                        seen_ids.add(r['id'])
                        books.append(dict(r))
            else:
                books = []

            # Decision guides (from hardcoded list)
            guides = [{'id': gid, 'title': gid.replace('_', ' ').title()} for gid in need.get('guides', [])]

            return jsonify({
                'need': {'id': need_id, 'label': need['label'], 'icon': need['icon'], 'color': need['color']},
                'inventory': inv_items[:30],
                'contacts': contacts[:10],
                'books': books[:15],
                'guides': guides,
            })

    @app.route('/api/guides/context')
    def api_guides_context():
        """Return live inventory/contacts data for context-aware decision tree rendering."""
        with db_session() as db:
            # Relevant inventory items grouped by category
            items = db.execute("SELECT name, quantity, unit, category, expiration FROM inventory WHERE quantity > 0 ORDER BY category, name LIMIT 500").fetchall()
            inv_by_cat = {}
            for it in items:
                cat = it['category'] or 'other'
                if cat not in inv_by_cat:
                    inv_by_cat[cat] = []
                inv_by_cat[cat].append({'name': it['name'], 'qty': it['quantity'], 'unit': it['unit'] or 'ea', 'expiration': it['expiration'] or ''})

            # Key contacts by role
            contacts = db.execute("SELECT name, role, callsign, phone FROM contacts ORDER BY name LIMIT 200").fetchall()
            contacts_by_role = {}
            for c in contacts:
                role = (c['role'] or 'general').lower()
                if role not in contacts_by_role:
                    contacts_by_role[role] = []
                contacts_by_role[role].append({'name': c['name'], 'callsign': c['callsign'] or '', 'phone': c['phone'] or ''})

            # Key stats
            water_items = [i for i in items if i['category'] == 'water']
            medical_items = [i for i in items if i['category'] == 'medical']
            food_items = [i for i in items if i['category'] == 'food']

            return jsonify({
                'inventory': inv_by_cat,
                'contacts': contacts_by_role,
                'summary': {
                    'water_items': len(water_items),
                    'medical_items': len(medical_items),
                    'food_items': len(food_items),
                    'total_contacts': len(contacts),
                    'medic': next((c['name'] for c in contacts if 'medic' in (c['role'] or '').lower() or 'doctor' in (c['role'] or '').lower() or 'nurse' in (c['role'] or '').lower()), None),
                    'comms_officer': next((c['name'] for c in contacts if 'comms' in (c['role'] or '').lower() or 'radio' in (c['role'] or '').lower()), None),
                },
            })

    from web.blueprints.preparedness import start_alert_engine, preparedness_bp  # noqa: F401 — preparedness_bp re-used at registration site
    start_alert_engine()

    # ─── Multi-Node Federation ─────────────────────────────────────────

    import uuid as _uuid

    from web.utils import get_node_id as _get_node_id, get_node_name as _get_node_name

    # Start UDP discovery listener in background
    def _discovery_listener():
        import socket
        discovery_port = Config.DISCOVERY_PORT
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Bind to loopback by default — set NOMAD_DISCOVERY_BIND=0.0.0.0
            # to expose on the LAN for multi-node discovery. Binding to
            # '0.0.0.0' (all interfaces) without opt-in was surprising for a
            # desktop app and exposed the discovery listener to the LAN even
            # when federation was unused.
            bind_addr = os.environ.get('NOMAD_DISCOVERY_BIND', '127.0.0.1').strip() or '127.0.0.1'
            sock.bind((bind_addr, discovery_port))
            sock.settimeout(1)
            while True:
                try:
                    data, addr = sock.recvfrom(1024)
                except socket.timeout:
                    continue
                except OSError:
                    # Socket closed by shutdown or OS-level error — exit loop
                    break
                except Exception as loop_err:
                    log.debug('Discovery listener recv error: %s', loop_err)
                    continue
                try:
                    msg = _safe_json_value(data, {})
                    if not isinstance(msg, dict):
                        continue
                    if msg.get('type') == 'nomad_discover' and msg.get('node_id') != _get_node_id():
                        # Respond with our identity
                        response = json.dumps({
                            'type': 'nomad_announce', 'node_id': _get_node_id(),
                            'node_name': _get_node_name(), 'port': Config.APP_PORT, 'version': VERSION,
                        }).encode()
                        sock.sendto(response, addr)
                except Exception as loop_err:
                    log.debug('Discovery listener handle error: %s', loop_err)
                    continue
        except OSError as e:
            # Port in use or permission denied — log once, don't retry
            log.warning('Discovery listener not available (port %s in use?): %s', discovery_port, e)
        except Exception as e:
            log.warning('Discovery listener failed to start: %s', e)
        finally:
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass

    if not _discovery_listener_started:
        with _discovery_listener_lock:
            if not _discovery_listener_started:
                threading.Thread(target=_discovery_listener, daemon=True).start()
                _discovery_listener_started = True

    # ─── Scheduled Automatic Backups ──────────────────────────────────

    def _load_auto_backup_config():
        """Load backup settings, skipping quietly if the configured DB is unavailable."""
        try:
            with db_session() as db:
                row = db.execute("SELECT value FROM settings WHERE key = 'auto_backup_config'").fetchone()
        except Exception as e:
            log.debug(f'Auto-backup config unavailable: {e}')
            return None

        if not row or not row['value']:
            return None

        try:
            return _safe_json_value(row['value'], None)
        except (TypeError, ValueError) as e:
            log.warning(f'Invalid auto-backup config — skipping schedule: {e}')
            return None

    def _run_auto_backup():
        """Execute scheduled auto-backup and reschedule."""
        import sqlite3 as _sqlite3
        try:
            cfg = _load_auto_backup_config()
            if not cfg or not cfg.get('enabled'):
                return

            db_path = get_db_path()
            data_dir = os.path.dirname(db_path)
            backup_dir = os.path.join(data_dir, 'backups')
            os.makedirs(backup_dir, exist_ok=True)

            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = os.path.join(backup_dir, f'nomad_backup_{ts}.db')

            src = _sqlite3.connect(db_path, timeout=30)
            try:
                dst = _sqlite3.connect(backup_path)
                try:
                    src.backup(dst)
                finally:
                    dst.close()
            finally:
                src.close()

            if cfg.get('encrypt') and cfg.get('_derived_key'):
                try:
                    from cryptography.fernet import Fernet
                    key = cfg['_derived_key'].encode()
                    f = Fernet(key)
                    with open(backup_path, 'rb') as fp:
                        data = fp.read()
                    encrypted = f.encrypt(data)
                    enc_path = backup_path + '.enc'
                    with open(enc_path, 'wb') as fp:
                        fp.write(encrypted)
                    os.remove(backup_path)
                except ImportError:
                    log.warning('cryptography package not installed — backup saved unencrypted')
                except Exception as e:
                    log.warning(f'Encryption failed — backup saved unencrypted: {e}')

            keep_count = cfg.get('keep_count', 7)
            _rotate_backups(backup_dir, keep_count)
            log.info(f'Auto-backup created: {os.path.basename(backup_path)}')
        except Exception as e:
            log.error(f'Auto-backup failed: {e}')
        finally:
            _schedule_auto_backup()

    def _rotate_backups(backup_dir, keep_count):
        """Delete oldest backups exceeding keep_count."""
        try:
            files = sorted(
                [f for f in os.listdir(backup_dir) if f.startswith('nomad_backup_')],
                key=lambda f: os.path.getmtime(os.path.join(backup_dir, f)),
                reverse=True,
            )
            for old_file in files[keep_count:]:
                try:
                    os.remove(os.path.join(backup_dir, old_file))
                except Exception:
                    pass
        except Exception:
            pass

    def _schedule_auto_backup():
        """Schedule the next auto-backup based on settings."""
        if _auto_backup_timer.get('timer'):
            _auto_backup_timer['timer'].cancel()
            _auto_backup_timer['timer'] = None
        try:
            cfg = _load_auto_backup_config()
            if not cfg:
                return
            if not cfg.get('enabled'):
                return
            interval = cfg.get('interval', 'daily')
            seconds = 86400 if interval == 'daily' else 604800
            timer = threading.Timer(seconds, _run_auto_backup)
            timer.daemon = True
            timer.start()
            _auto_backup_timer['timer'] = timer
        except Exception as e:
            log.debug(f'Failed to schedule auto-backup: {e}')

    app.config['_schedule_auto_backup'] = _schedule_auto_backup
    try:
        _schedule_auto_backup()
    except Exception:
        pass

    @app.route('/api/planner/calculate', methods=['POST'])
    def api_planner_calculate():
        """Calculate resource needs for X people over Y days."""
        data, error = _require_json_body(request)
        if error:
            return error
        try:
            people = max(1, int(data.get('people', 4)))
            days = max(1, int(data.get('days', 14)))
        except (ValueError, TypeError):
            return jsonify({'error': 'people and days must be integers'}), 400
        activity = data.get('activity', 'moderate')  # sedentary, moderate, heavy

        cal_mult = {'sedentary': 1800, 'moderate': 2200, 'heavy': 3000}.get(activity, 2200)
        water_mult = {'sedentary': 0.75, 'moderate': 1.0, 'heavy': 1.5}.get(activity, 1.0)

        needs = {
            'water_gal': round(people * days * water_mult, 1),
            'food_cal': people * days * cal_mult,
            'food_lbs_rice': round(people * days * cal_mult / 1800 * 0.45, 1),  # ~0.45 lb rice/1800cal
            'food_cans': people * days * 2,  # ~2 cans per person per day
            'tp_rolls': max(1, round(people * days / 5)),  # ~1 roll per 5 person-days
            'bleach_oz': round(people * days * 0.1, 1),  # ~0.1 oz per person-day for water treatment
            'batteries_aa': people * 2 + days,  # rough estimate
            'trash_bags': max(1, round(people * days / 3)),
            'first_aid_kits': max(1, round(people / 4)),
        }

        # Compare with current inventory
        with db_session() as db:
            inv = {}
            rows = db.execute('SELECT category, SUM(quantity) as qty FROM inventory GROUP BY category').fetchall()
            for r in rows:
                inv[r['category']] = r['qty'] or 0

        return jsonify({
            'people': people, 'days': days, 'activity': activity,
            'needs': needs, 'current_inventory': inv,
        })

    @app.route('/api/readiness-score')
    def api_readiness_score():
        """Cross-module readiness assessment (0-100) with category breakdown."""
        cached = _cached('readiness', 60)
        if cached:
            return jsonify(cached)
        with db_session() as db:
            scores = {}

            # 1. Water (20 pts) — based on water-category inventory vs people
            water_items = db.execute("SELECT SUM(quantity) as qty FROM inventory WHERE LOWER(category) IN ('water', 'hydration')").fetchone()
            water_qty = water_items['qty'] or 0
            contacts_count = max(db.execute('SELECT COUNT(*) as c FROM contacts').fetchone()['c'], 1)
            water_days = water_qty / max(contacts_count, 1)  # rough gal/person
            scores['water'] = {'score': min(round(water_days / 14 * 20), 20), 'detail': f'{round(water_days, 1)} gal/person'}

            # 2. Food (20 pts) — based on food-category inventory with usage tracking
            food_items = db.execute("SELECT COUNT(*) as c FROM inventory WHERE LOWER(category) IN ('food', 'food storage', 'canned goods')").fetchone()
            food_count = food_items['c'] or 0
            food_with_usage = db.execute("SELECT COUNT(*) as c FROM inventory WHERE LOWER(category) IN ('food', 'food storage', 'canned goods') AND daily_usage > 0").fetchone()['c']
            today = datetime.now().strftime('%Y-%m-%d')
            food_expired = db.execute("SELECT COUNT(*) as c FROM inventory WHERE LOWER(category) IN ('food', 'food storage', 'canned goods') AND expiration != '' AND expiration < ?", (today,)).fetchone()['c']
            food_score = min(food_count * 2, 14) + (3 if food_with_usage > 0 else 0) + (3 if food_expired == 0 else 0)
            scores['food'] = {'score': min(food_score, 20), 'detail': f'{food_count} items, {food_expired} expired'}

            # 3. Medical (15 pts) — patients, meds inventory, contacts with blood types
            med_items = db.execute("SELECT COUNT(*) as c FROM inventory WHERE LOWER(category) IN ('medical', 'first aid', 'medicine')").fetchone()['c']
            patients = db.execute('SELECT COUNT(*) as c FROM patients').fetchone()['c']
            blood_typed = db.execute("SELECT COUNT(*) as c FROM contacts WHERE blood_type != ''").fetchone()['c']
            med_score = min(med_items, 8) + (4 if patients > 0 else 0) + min(blood_typed, 3)
            scores['medical'] = {'score': min(med_score, 15), 'detail': f'{med_items} supplies, {patients} patients'}

            # 4. Security (10 pts) — cameras, access logging, incidents, ammo reserve
            cameras = db.execute('SELECT COUNT(*) as c FROM cameras').fetchone()['c']
            access_entries = db.execute("SELECT COUNT(*) as c FROM access_log WHERE created_at >= datetime('now', '-7 days')").fetchone()['c']
            recent_incidents = db.execute("SELECT COUNT(*) as c FROM incidents WHERE created_at >= datetime('now', '-7 days')").fetchone()['c']
            ammo_total = db.execute('SELECT COALESCE(SUM(quantity),0) as q FROM ammo_inventory').fetchone()['q']
            ammo_pts = min(2 if ammo_total >= 500 else (1 if ammo_total > 0 else 0), 2)
            sec_score = min(cameras * 2, 3) + (2 if access_entries > 0 else 0) + (3 if recent_incidents == 0 else 1) + ammo_pts
            scores['security'] = {'score': min(sec_score, 10), 'detail': f'{cameras} cameras, {int(ammo_total)} rounds'}

            # 5. Communications (10 pts) — contacts, comms log, radio ref usage
            contact_count = db.execute('SELECT COUNT(*) as c FROM contacts').fetchone()['c']
            comms_entries = db.execute('SELECT COUNT(*) as c FROM comms_log').fetchone()['c']
            comm_score = min(contact_count, 5) + (3 if comms_entries > 0 else 0) + (2 if contact_count >= 5 else 0)
            scores['comms'] = {'score': min(comm_score, 10), 'detail': f'{contact_count} contacts, {comms_entries} radio logs'}

            # 6. Shelter & Power (10 pts) — power devices, garden, waypoints, fuel reserve
            power_devices = db.execute('SELECT COUNT(*) as c FROM power_devices').fetchone()['c']
            garden_plots = db.execute('SELECT COUNT(*) as c FROM garden_plots').fetchone()['c']
            waypoints = db.execute('SELECT COUNT(*) as c FROM waypoints').fetchone()['c']
            fuel_total = db.execute('SELECT COALESCE(SUM(quantity),0) as q FROM fuel_storage').fetchone()['q']
            fuel_pts = min(2 if fuel_total >= 20 else (1 if fuel_total > 0 else 0), 2)
            shelter_score = min(power_devices * 2, 3) + min(garden_plots * 2, 3) + min(waypoints, 2) + fuel_pts
            scores['shelter'] = {'score': min(shelter_score, 10), 'detail': f'{power_devices} power devices, {round(fuel_total,1)} gal fuel'}

            # 7. Planning & Knowledge (15 pts) — checklists, notes, documents, drills, skills proficiency
            checklists = db.execute('SELECT items FROM checklists').fetchall()
            cl_total = 0
            cl_checked = 0
            for cl in checklists:
                items = _safe_json_list(cl['items'], [])
                cl_total += len(items)
                cl_checked += sum(1 for i in items if i.get('checked'))
            cl_pct = (cl_checked / cl_total * 100) if cl_total > 0 else 0
            notes_count = db.execute('SELECT COUNT(*) as c FROM notes').fetchone()['c']
            docs_count = db.execute("SELECT COUNT(*) as c FROM documents WHERE status = 'ready'").fetchone()['c']
            drills = db.execute('SELECT COUNT(*) as c FROM drill_history').fetchone()['c']
            skilled = db.execute("SELECT COUNT(*) as c FROM skills WHERE proficiency IN ('intermediate','expert')").fetchone()['c']
            skill_pts = min(skilled // 5, 3)  # 1 pt per 5 skilled areas, max 3
            community_count = db.execute("SELECT COUNT(*) as c FROM community_resources WHERE trust_level IN ('trusted','inner-circle')").fetchone()['c']
            plan_score = min(round(cl_pct / 10), 5) + min(notes_count, 2) + min(docs_count, 3) + min(drills, 2) + skill_pts + min(community_count, 1)
            scores['planning'] = {'score': min(plan_score, 15), 'detail': f'{round(cl_pct)}% checklists, {skilled} skilled areas, {drills} drills'}

        total = sum(s['score'] for s in scores.values())
        max_total = 100

        # Letter grade
        if total >= 90:
            grade = 'A'
        elif total >= 80:
            grade = 'B'
        elif total >= 65:
            grade = 'C'
        elif total >= 50:
            grade = 'D'
        else:
            grade = 'F'

        result = {
            'total': total, 'max': max_total, 'grade': grade,
            'categories': scores,
        }
        _set_cache('readiness', result)
        return jsonify(result)

    # ─── Data Summary ──────────────────────────────────────────────────

    @app.route('/api/data-summary')
    def api_data_summary():
        """Counts across all major tables for the settings data summary card."""
        with db_session() as db:
            tables = [
                ('inventory', 'Inventory Items'), ('contacts', 'Contacts'), ('notes', 'Notes'),
                ('conversations', 'AI Conversations'), ('checklists', 'Checklists'),
                ('incidents', 'Incidents'), ('patients', 'Patients'),
                ('waypoints', 'Waypoints'), ('documents', 'Documents'),
                ('garden_plots', 'Garden Plots'), ('seeds', 'Seeds'),
                ('harvest_log', 'Harvests'), ('livestock', 'Livestock'),
                ('power_devices', 'Power Devices'), ('cameras', 'Cameras'),
                ('comms_log', 'Radio Logs'), ('weather_log', 'Weather Entries'),
                ('journal', 'Journal Entries'), ('drill_history', 'Drills'),
                ('scenarios', 'Scenarios'), ('videos', 'Videos'),
                ('activity_log', 'Activity Events'), ('alerts', 'Alerts'),
                ('skills', 'Skills'), ('ammo_inventory', 'Ammo Inventory'),
                ('community_resources', 'Community Resources'), ('radiation_log', 'Radiation Entries'),
                ('fuel_storage', 'Fuel Storage'), ('equipment_log', 'Equipment'),
            ]
            _SUMMARY_TABLES = {t for t, _ in tables}
            result = []
            total = 0
            for tname, label in tables:
                try:
                    safe_table(tname, _SUMMARY_TABLES)
                    c = db.execute(f'SELECT COUNT(*) as c FROM {tname}').fetchone()['c']
                    if c > 0:
                        result.append({'table': tname, 'label': label, 'count': c})
                    total += c
                except Exception:
                    pass
        return jsonify({'tables': result, 'total_records': total})

    # ─── Expanded Unified Search ──────────────────────────────────────

    @app.route('/api/search/all')
    def api_search_all():
        """Extended search across all data types — single UNION ALL query.

        v7.29.0: uses FTS5 for notes/inventory/contacts/documents/waypoints
        when available (O(log n) vs LIKE's O(n) full scan). Remaining targets
        still use LIKE until their FTS5 indexes are added incrementally.
        """
        q = request.args.get('q', '').strip()[:200]
        if not q:
            return jsonify({'conversations': [], 'notes': [], 'documents': [], 'inventory': [], 'contacts': [], 'checklists': []})
        with db_session() as db:
            q_escaped = q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            like = f'%{q_escaped}%'
            esc = "ESCAPE '\\'"
            # FTS5 MATCH expression: escape embedded double quotes then wrap
            # the whole query in double quotes for phrase/prefix handling.
            fts_q = '"' + q.replace('"', '""') + '"' + '*'
            use_fts = False
            try:
                use_fts = db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='notes_fts'"
                ).fetchone() is not None
            except Exception:
                use_fts = False
            # Single UNION ALL — 1 round-trip instead of 14
            if use_fts:
                _search_parts = [
                    (f"SELECT * FROM (SELECT id, title, 'conversation' as type FROM conversations WHERE title LIKE ? {esc} OR messages LIKE ? {esc} LIMIT 10)", (like, like)),
                    ("SELECT * FROM (SELECT n.id, n.title, 'note' as type FROM notes n JOIN notes_fts f ON f.rowid = n.id WHERE notes_fts MATCH ? LIMIT 10)", (fts_q,)),
                    ("SELECT * FROM (SELECT d.id, d.filename as title, 'document' as type FROM documents d JOIN documents_fts f ON f.rowid = d.id WHERE documents_fts MATCH ? AND d.status = 'ready' LIMIT 10)", (fts_q,)),
                    ("SELECT * FROM (SELECT i.id, i.name as title, 'inventory' as type FROM inventory i JOIN inventory_fts f ON f.rowid = i.id WHERE inventory_fts MATCH ? LIMIT 10)", (fts_q,)),
                    ("SELECT * FROM (SELECT c.id, c.name as title, 'contact' as type FROM contacts c JOIN contacts_fts f ON f.rowid = c.id WHERE contacts_fts MATCH ? LIMIT 10)", (fts_q,)),
                ]
            else:
                _search_parts = [
                    (f"SELECT * FROM (SELECT id, title, 'conversation' as type FROM conversations WHERE title LIKE ? {esc} OR messages LIKE ? {esc} LIMIT 10)", (like, like)),
                    (f"SELECT * FROM (SELECT id, title, 'note' as type FROM notes WHERE title LIKE ? {esc} OR content LIKE ? {esc} LIMIT 10)", (like, like)),
                    (f"SELECT * FROM (SELECT id, filename as title, 'document' as type FROM documents WHERE filename LIKE ? {esc} AND status = 'ready' LIMIT 10)", (like,)),
                    (f"SELECT * FROM (SELECT id, name as title, 'inventory' as type FROM inventory WHERE name LIKE ? {esc} OR location LIKE ? {esc} OR notes LIKE ? {esc} LIMIT 10)", (like, like, like)),
                    (f"SELECT * FROM (SELECT id, name as title, 'contact' as type FROM contacts WHERE name LIKE ? {esc} OR callsign LIKE ? {esc} OR role LIKE ? {esc} OR skills LIKE ? {esc} LIMIT 10)", (like, like, like, like)),
                ]
            _search_parts.extend([
                (f"SELECT * FROM (SELECT id, name as title, 'checklist' as type FROM checklists WHERE name LIKE ? {esc} LIMIT 10)", (like,)),
                (f"SELECT * FROM (SELECT id, name as title, 'skill' as type FROM skills WHERE name LIKE ? {esc} OR category LIKE ? {esc} OR notes LIKE ? {esc} LIMIT 5)", (like, like, like)),
                (f"SELECT * FROM (SELECT id, caliber as title, 'ammo' as type FROM ammo_inventory WHERE caliber LIKE ? {esc} OR brand LIKE ? {esc} OR location LIKE ? {esc} LIMIT 5)", (like, like, like)),
                (f"SELECT * FROM (SELECT id, name as title, 'equipment' as type FROM equipment_log WHERE name LIKE ? {esc} OR category LIKE ? {esc} OR location LIKE ? {esc} LIMIT 5)", (like, like, like)),
                (f"SELECT * FROM (SELECT id, name as title, 'waypoint' as type FROM waypoints WHERE name LIKE ? {esc} OR notes LIKE ? {esc} OR category LIKE ? {esc} LIMIT 5)", (like, like, like)),
                (f"SELECT * FROM (SELECT id, service as title, 'frequency' as type FROM freq_database WHERE service LIKE ? {esc} OR description LIKE ? {esc} OR notes LIKE ? {esc} LIMIT 5)", (like, like, like)),
                (f"SELECT * FROM (SELECT id, name as title, 'patient' as type FROM patients WHERE name LIKE ? {esc} LIMIT 5)", (like,)),
                (f"SELECT * FROM (SELECT id, description as title, 'incident' as type FROM incidents WHERE description LIKE ? {esc} OR category LIKE ? {esc} LIMIT 5)", (like, like)),
                (f"SELECT * FROM (SELECT id, fuel_type as title, 'fuel' as type FROM fuel_storage WHERE fuel_type LIKE ? {esc} OR location LIKE ? {esc} LIMIT 5)", (like, like)),
            ])
            union_sql = ' UNION ALL '.join(sql for sql, _ in _search_parts)
            union_params = []
            for _, params in _search_parts:
                union_params.extend(params)
            rows = db.execute(union_sql, tuple(union_params)).fetchall()

        # Group results by type
        result = {}
        _type_keys = {
            'conversation': 'conversations', 'note': 'notes', 'document': 'documents',
            'inventory': 'inventory', 'contact': 'contacts', 'checklist': 'checklists',
            'skill': 'skills', 'ammo': 'ammo', 'equipment': 'equipment',
            'waypoint': 'waypoints', 'frequency': 'frequencies', 'patient': 'patients',
            'incident': 'incidents', 'fuel': 'fuel',
        }
        for key in _type_keys.values():
            result[key] = []
        for r in rows:
            key = _type_keys.get(r['type'])
            if key:
                result[key].append(dict(r))
        return jsonify(result)

    # Resolve nukemap directory — try multiple paths for robustness
    _nukemap_candidates = []
    if getattr(sys, 'frozen', False):
        _nukemap_candidates.append(os.path.join(sys._MEIPASS, 'web', 'nukemap'))
    _nukemap_candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nukemap'))
    _nukemap_candidates.append(os.path.join(os.getcwd(), 'web', 'nukemap'))

    _nukemap_dir = _nukemap_candidates[0]
    for candidate in _nukemap_candidates:
        if os.path.isdir(candidate) and os.path.isfile(os.path.join(candidate, 'index.html')):
            _nukemap_dir = candidate
            break

    @app.route('/nukemap')
    def nukemap_redirect():
        """Redirect /nukemap to /nukemap/ so relative CSS/JS paths resolve correctly."""
        from flask import redirect
        return redirect('/nukemap/', code=301)

    @app.route('/nukemap/')
    @app.route('/nukemap/<path:filepath>')
    def nukemap_serve(filepath='index.html'):
        from flask import send_from_directory
        full_path = os.path.realpath(os.path.join(_nukemap_dir, filepath))
        base_dir = os.path.realpath(_nukemap_dir)
        # Audit H5: commonpath is normalization-safe on Windows where
        # mixed-case/mixed-separator paths could bypass startswith checks.
        try:
            if os.path.commonpath([full_path, base_dir]) != base_dir:
                return jsonify({'error': 'Forbidden'}), 403
        except ValueError:
            # commonpath raises when paths are on different drives (Windows)
            return jsonify({'error': 'Forbidden'}), 403
        if not os.path.isfile(full_path):
            log.warning('NukeMap file not found: %s', full_path)
            return jsonify({'error': 'Not found'}), 404
        return send_from_directory(os.path.dirname(full_path), os.path.basename(full_path))

    # ─── VIPTrack ─────────────────────────────────────────────────────

    # Resolve VIPTrack directory — try multiple paths including external repo
    _viptrack_candidates = []
    if getattr(sys, 'frozen', False):
        _viptrack_candidates.append(os.path.join(sys._MEIPASS, 'web', 'viptrack'))
    _viptrack_candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'viptrack'))
    _viptrack_candidates.append(os.path.join(os.getcwd(), 'web', 'viptrack'))
    # External repo path (development)
    _viptrack_candidates.append(os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'VIPTrack')))

    _viptrack_dir = None
    for candidate in _viptrack_candidates:
        if os.path.isdir(candidate) and os.path.isfile(os.path.join(candidate, 'index.html')):
            _viptrack_dir = candidate
            break
    if _viptrack_dir:
        log.info(f'VIPTrack directory: {_viptrack_dir}')
    else:
        log.warning(f'VIPTrack directory NOT FOUND. Tried: {_viptrack_candidates}')
        _viptrack_dir = _viptrack_candidates[0]  # Use first candidate as fallback

    @app.route('/viptrack')
    def viptrack_redirect():
        """Redirect /viptrack to /viptrack/ so relative paths resolve correctly."""
        from flask import redirect
        return redirect('/viptrack/', code=301)

    @app.route('/viptrack/')
    @app.route('/viptrack/<path:filepath>')
    def viptrack_serve(filepath='index.html'):
        from flask import send_from_directory
        full_path = os.path.realpath(os.path.join(_viptrack_dir, filepath))
        base_dir = os.path.realpath(_viptrack_dir)
        # Audit H5 — commonpath is normalization-safe on Windows.
        try:
            if os.path.commonpath([full_path, base_dir]) != base_dir:
                return jsonify({'error': 'Forbidden'}), 403
        except ValueError:
            return jsonify({'error': 'Forbidden'}), 403
        if not os.path.isfile(full_path):
            return jsonify({'error': 'Not found'}), 404
        return send_from_directory(os.path.dirname(full_path), os.path.basename(full_path))

    @app.route('/sw.js')
    def service_worker():
        return app.send_static_file('sw.js')

    # ─── Favicon ──────────────────────────────────────────────────────

    @app.route('/favicon.ico')
    def favicon():
        svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><polygon points="32,4 60,32 32,60 4,32" fill="#4f9cf7"/><polygon points="32,14 50,32 32,50 14,32" fill="#0d0d0d"/><polygon points="32,22 42,32 32,42 22,32" fill="#4f9cf7"/></svg>'
        return Response(svg, mimetype='image/svg+xml')

    # ─── IndexedDB Offline Sync ──────────────────────────────────────
    @app.route('/api/offline/snapshot')
    def api_offline_snapshot():
        """Return a snapshot of critical data for IndexedDB offline cache."""
        with db_session() as db:
            snapshot = {}
            OFFLINE_TABLES = {
                'inventory': 'SELECT id, name, category, quantity, unit, location, expiration, notes FROM inventory ORDER BY name LIMIT 5000',
                'contacts': 'SELECT id, name, callsign, role, phone, email, notes FROM contacts ORDER BY name LIMIT 2000',
                'patients': 'SELECT id, contact_id, blood_type, allergies, medications, conditions FROM patients LIMIT 1000',
                'waypoints': 'SELECT id, name, lat, lng, category, icon, notes FROM waypoints ORDER BY name LIMIT 5000',
                'checklists': 'SELECT id, name, items FROM checklists ORDER BY name LIMIT 500',
                'freq_database': 'SELECT id, frequency, service, mode, notes, channel_name FROM freq_database ORDER BY frequency LIMIT 2000',
            }
            for table, query in OFFLINE_TABLES.items():
                try:
                    rows = db.execute(query).fetchall()
                    snapshot[table] = [dict(r) for r in rows]
                except Exception:
                    snapshot[table] = []
        snapshot['_timestamp'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        snapshot['_node_id'] = _get_node_id()
        return jsonify(snapshot)

    @app.route('/api/offline/changes-since')
    def api_offline_changes_since():
        """Return rows changed since a given timestamp (for incremental sync)."""
        since = request.args.get('since', '2000-01-01T00:00:00')
        with db_session() as db:
            changes = {}
            # Tables with updated_at or created_at
            TRACKED = {
                'inventory': "SELECT * FROM inventory WHERE created_at > ? OR updated_at > ? ORDER BY updated_at DESC LIMIT 1000",
                'contacts': "SELECT * FROM contacts WHERE created_at > ? OR updated_at > ? ORDER BY created_at DESC LIMIT 500",
                'waypoints': "SELECT * FROM waypoints WHERE created_at > ? ORDER BY created_at DESC LIMIT 500",
            }
            for table, query in TRACKED.items():
                try:
                    if 'updated_at' in query and query.count('?') == 2:
                        rows = db.execute(query, (since, since)).fetchall()
                    else:
                        rows = db.execute(query, (since,)).fetchall()
                    changes[table] = [dict(r) for r in rows]
                except Exception:
                    changes[table] = []
        changes['_timestamp'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        return jsonify(changes)

    # ─── Blueprints ──────────────────────────────────────────────────
    from web.blueprints.benchmark import benchmark_bp
    from web.blueprints.garden import garden_bp
    from web.blueprints.notes import notes_bp
    from web.blueprints.weather import weather_bp
    from web.blueprints.medical import medical_bp
    from web.blueprints.power import power_bp
    from web.blueprints.federation import federation_bp
    from web.blueprints.kb import kb_bp
    from web.blueprints.security import security_bp
    from web.blueprints.supplies import supplies_bp
    app.register_blueprint(benchmark_bp)
    app.register_blueprint(garden_bp)
    app.register_blueprint(notes_bp)
    app.register_blueprint(weather_bp)
    app.register_blueprint(medical_bp)
    app.register_blueprint(power_bp)
    app.register_blueprint(federation_bp)
    app.register_blueprint(kb_bp)
    app.register_blueprint(security_bp)
    app.register_blueprint(supplies_bp)

    # ─── Phase 2 Batch 3 Blueprints ──────────────────────────────────
    from web.blueprints.services import services_bp
    from web.blueprints.ai import ai_bp
    from web.blueprints.inventory import inventory_bp
    from web.blueprints.comms import comms_bp
    from web.blueprints.media import media_bp
    from web.blueprints.maps import maps_bp
    from web.blueprints.system import system_bp
    from web.blueprints.situation_room import situation_room_bp
    app.register_blueprint(services_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(comms_bp)
    app.register_blueprint(media_bp)
    app.register_blueprint(maps_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(situation_room_bp)

    # ─── Phase 3 Blueprints ──────────────────────────────────────────
    from web.blueprints.checklists import checklists_bp
    from web.blueprints.tasks import tasks_bp
    from web.blueprints.contacts import contacts_bp
    from web.blueprints.exercises import exercises_bp
    app.register_blueprint(checklists_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(contacts_bp)
    app.register_blueprint(exercises_bp)
    # preparedness_bp already imported above at the start_alert_engine() call site
    from web.blueprints.print_routes import print_routes_bp
    from web.blueprints.kiwix import kiwix_bp
    app.register_blueprint(preparedness_bp)
    app.register_blueprint(print_routes_bp)
    app.register_blueprint(kiwix_bp)

    # ─── Undo Blueprint ──────────────────────────────────────────────
    from web.blueprints.undo import undo_bp
    app.register_blueprint(undo_bp)

    # ─── Kit Builder (v7.3.0 — personalized kit wizard) ──────────────
    from web.blueprints.kit_builder import kit_builder_bp
    app.register_blueprint(kit_builder_bp)

    # ─── Emergency Mode (v7.5.0 — crisis orchestrator) ───────────────
    from web.blueprints.emergency import emergency_bp
    app.register_blueprint(emergency_bp)

    # ─── Family Check-in Board (v7.6.0) ──────────────────────────────
    from web.blueprints.family import family_bp
    app.register_blueprint(family_bp)

    # ─── Daily Operations Brief (v7.7.0) ─────────────────────────────
    from web.blueprints.brief import brief_bp
    app.register_blueprint(brief_bp)

    # ─── v7.8.0 — Critical Path Modules ─────────────────────────────
    from web.blueprints.water_mgmt import water_mgmt_bp
    from web.blueprints.financial import financial_bp
    from web.blueprints.vehicles import vehicles_bp
    from web.blueprints.loadout import loadout_bp
    app.register_blueprint(water_mgmt_bp)
    app.register_blueprint(financial_bp)
    app.register_blueprint(vehicles_bp)
    app.register_blueprint(loadout_bp)

    # ─── v7.10.0 — High Value Modules ───────────────────────────────
    from web.blueprints.readiness_goals import readiness_goals_bp
    from web.blueprints.alert_rules import alert_rules_bp
    from web.blueprints.timeline import timeline_bp
    from web.blueprints.threat_intel import threat_intel_bp
    from web.blueprints.evac_drills import evac_drills_bp
    app.register_blueprint(readiness_goals_bp)
    app.register_blueprint(alert_rules_bp)
    app.register_blueprint(timeline_bp)
    app.register_blueprint(threat_intel_bp)
    app.register_blueprint(evac_drills_bp)

    # ─── v7.11.0 — Data Foundation & Localization (Phase 1) ─────────
    from web.blueprints.data_packs import data_packs_bp
    from web.blueprints.regional_profile import regional_profile_bp
    from web.blueprints.nutrition import nutrition_bp
    app.register_blueprint(data_packs_bp)
    app.register_blueprint(regional_profile_bp)
    app.register_blueprint(nutrition_bp)

    # ─── v7.12.0 — Nutritional Intelligence & Water Expansion (Phase 2) ──
    from web.blueprints.consumption import consumption_bp
    app.register_blueprint(consumption_bp)

    # ─── v7.13.0 — Advanced Inventory & Consumption Modeling (Phase 4) ──
    from web.blueprints.meal_planning import meal_planning_bp
    app.register_blueprint(meal_planning_bp)

    # ─── v7.14.0 — Movement & Route Planning (Phase 5) ───────────────
    from web.blueprints.movement_ops import movement_ops_bp
    app.register_blueprint(movement_ops_bp)

    # ─── v7.14.0 — Tactical Communications (Phase 6) ─────────────────
    from web.blueprints.tactical_comms import tactical_comms_bp
    app.register_blueprint(tactical_comms_bp)

    # ─── v7.15.0 — Land Assessment & Property (Phase 8) ──────────────
    from web.blueprints.land_assessment import land_assessment_bp
    app.register_blueprint(land_assessment_bp)

    # ─── v7.15.0 — Medical Phase 2 (Phase 9) ─────────────────────────
    from web.blueprints.medical_phase2 import medical_phase2_bp
    app.register_blueprint(medical_phase2_bp)

    # ─── v7.16.0 — Training & Knowledge (Phase 10) ───────────────────
    from web.blueprints.training_knowledge import training_knowledge_bp
    app.register_blueprint(training_knowledge_bp)

    # ─── v7.17.0 — Group Operations & Governance (Phase 11) ──────────
    from web.blueprints.group_ops import group_ops_bp
    app.register_blueprint(group_ops_bp)

    # ─── v7.18.0 — Security, OPSEC & Night Ops (Phase 12) ────────────
    from web.blueprints.security_opsec import security_opsec_bp
    app.register_blueprint(security_opsec_bp)

    # ─── v7.19.0 — Agriculture & Permaculture (Phase 13) ─────────────
    from web.blueprints.agriculture import agriculture_bp
    app.register_blueprint(agriculture_bp)

    # ─── v7.20.0 — Disaster-Specific Modules (Phase 14) ──────────────
    from web.blueprints.disaster_modules import disaster_modules_bp
    app.register_blueprint(disaster_modules_bp)

    # ─── v7.21.0 — Daily Living & Quality of Life (Phase 15) ─────────
    from web.blueprints.daily_living import daily_living_bp
    app.register_blueprint(daily_living_bp)

    # ─── v7.22.0 — Interoperability & Data Exchange (Phase 16) ───────
    from web.blueprints.interoperability import interoperability_bp
    app.register_blueprint(interoperability_bp)

    # ─── v7.23.0 — Hunting, Foraging & Wild Food (Phase 17) ──────────
    from web.blueprints.hunting_foraging import hunting_foraging_bp
    app.register_blueprint(hunting_foraging_bp)

    # ─── v7.24.0 — Hardware, Sensors & Mesh (Phase 18) ───────────────
    from web.blueprints.hardware_sensors import hardware_sensors_bp
    app.register_blueprint(hardware_sensors_bp)

    # ─── Platform Security (Users, Auth, Sessions, Configs, Metrics) ──
    from web.blueprints.platform_security import platform_security_bp
    app.register_blueprint(platform_security_bp)

    # ─── Specialized Modules (Caches, Pets, Intel, Drones, etc.) ─────
    from web.blueprints.specialized_modules import specialized_modules_bp
    app.register_blueprint(specialized_modules_bp)

    # ─── User Plugins ─────────────────────────────────────────────────
    from web.plugins import load_plugins
    load_plugins(app)

    # ─── SSE Real-Time Event Bus ─────────────────────────────────────
    _sse_connects = {}  # ip -> list of timestamps

    @app.route('/api/events/stream')
    def event_stream():
        """SSE endpoint — pushes real-time events to connected clients."""
        ip = request.remote_addr or 'unknown'
        now = time.time()
        if not _is_loopback(ip):
            with _sse_lock:
                connects = _sse_connects.get(ip, [])
                connects = [t for t in connects if now - t < 60]
                if len(connects) >= 10:
                    return jsonify({'error': 'rate limited'}), 429
                connects.append(now)
                _sse_connects[ip] = connects
                # Prune IPs with no recent connections to prevent unbounded growth
                stale_ips = [k for k, v in _sse_connects.items()
                             if all(now - t > 60 for t in v)]
                for k in stale_ips:
                    del _sse_connects[k]
        q = queue.Queue(maxsize=50)
        if not sse_register_client(q):
            return jsonify({'error': 'Too many SSE connections'}), 429
        def generate():
            try:
                # Yield an initial keepalive so clients (and test harnesses)
                # receive the response headers + first chunk immediately
                # rather than waiting for the first event/keepalive tick.
                yield ": connected\n\n"
                while True:
                    try:
                        msg = q.get(timeout=30)
                        sse_touch_client(q)
                        yield msg
                    except queue.Empty:
                        sse_touch_client(q)
                        yield ": keepalive\n\n"
            finally:
                sse_unregister_client(q)
        return Response(generate(), mimetype='text/event-stream',
                        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    # Background thread: periodically clean up stale SSE clients.
    # Use Event.wait so the loop can be interrupted during shutdown rather
    # than sleeping the full interval.
    _sse_cleanup_stop = threading.Event()
    app.config['_sse_cleanup_stop'] = _sse_cleanup_stop

    def _sse_stale_cleanup_loop():
        while not _sse_cleanup_stop.is_set():
            if _sse_cleanup_stop.wait(timeout=30):
                return
            try:
                sse_cleanup_stale_clients()
            except Exception as e:
                log.debug('SSE cleanup error: %s', e)
    if not _sse_cleanup_started:
        with _sse_cleanup_lock:
            if not _sse_cleanup_started:
                threading.Thread(target=_sse_stale_cleanup_loop, daemon=True).start()
                _sse_cleanup_started = True

    @app.route('/api/events/test')
    def event_test():
        """Broadcast a test event (useful for debugging SSE)."""
        broadcast_event('alert', {'level': 'info', 'message': 'SSE test event'})
        return jsonify({'status': 'sent', 'clients': len(_sse_clients)})

    @app.route('/api/i18n/languages')
    def api_i18n_languages():
        return jsonify({'languages': SUPPORTED_LANGUAGES})

    @app.route('/api/i18n/translations/<lang>')
    def api_i18n_translations(lang):
        if lang not in TRANSLATIONS:
            return jsonify({'error': f'Language not found: {lang}'}), 404
        return jsonify({'language': lang, 'translations': TRANSLATIONS[lang]})

    @app.route('/api/i18n/language', methods=['GET'])
    def api_i18n_get_language():
        return jsonify({'language': _get_current_language()})

    @app.route('/api/i18n/language', methods=['POST'])
    def api_i18n_set_language():
        data, error = _require_json_body(request)
        if error:
            return error
        lang = data.get('language', '').strip()
        if lang not in SUPPORTED_LANGUAGES:
            return jsonify({'error': f'Unsupported language: {lang}'}), 400
        with db_session() as db:
            db.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('language', ?)",
                (lang,)
            )
            db.commit()
        return jsonify({'status': 'ok', 'language': lang})

    return app
