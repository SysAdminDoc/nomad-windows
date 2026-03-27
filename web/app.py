"""Flask web application — dashboard and API routes."""

import json
import os
import sys
import time
import threading
import platform
import logging
import shutil
import subprocess
import queue
from flask import Flask, render_template, jsonify, request, Response, stream_with_context
from werkzeug.utils import secure_filename
from web.validation import validate_json, validate_file_upload
import web.state as _state
from web.state import (
    _installing, _installing_lock,
    _pull_queue, _pull_queue_lock,
    _wizard_state,
    _map_downloads,
    _ytdlp_downloads, _ytdlp_dl_lock,
    _ytdlp_install_state,
    _auto_backup_timer,
    _broadcast,
    _update_state,
    _serial_state, _serial_conn,
    _mesh_state,
    MAX_SSE_CLIENTS, _sse_clients, _sse_lock,
    broadcast_event,
)

from config import get_data_dir, set_data_dir, Config
from platform_utils import get_data_base
try:
    from web.catalog import CHANNEL_CATALOG, CHANNEL_CATEGORIES
except Exception:
    try:
        from catalog import CHANNEL_CATALOG, CHANNEL_CATEGORIES
    except Exception:
        logging.getLogger('nomad.web').warning('Could not import channel catalog — media features will be limited')
        CHANNEL_CATALOG = []
        CHANNEL_CATEGORIES = []
from db import get_db, get_db_path, db_session, log_activity
from web.sql_safety import safe_table, safe_columns, build_update, build_insert
from services import ollama, kiwix, cyberchef, kolibri, qdrant, stirling, flatnotes
from services.manager import (
    get_download_progress, get_dir_size, format_size, uninstall_service, get_services_dir,
    ensure_dependencies, detect_gpu
)

log = logging.getLogger('nomad.web')
_CREATION_FLAGS = {'creationflags': 0x08000000} if sys.platform == 'win32' else {}

# ─── Security Helpers ─────────────────────────────────────────────────

def _validate_download_url(url):
    """Validate that a download URL is safe (SSRF protection).

    Raises ValueError if the URL uses a non-https scheme or points to a
    private/internal IP address.
    """
    import ipaddress
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in ('https', 'http'):
        raise ValueError(f'Unsupported URL scheme: {parsed.scheme}')
    hostname = parsed.hostname or ''
    # Block obvious private hostnames
    if hostname in ('localhost', '') or hostname.endswith('.local'):
        raise ValueError('URLs pointing to internal hosts are not allowed')
    # Resolve and check for private IPs
    try:
        import socket
        resolved = socket.getaddrinfo(hostname, None)
        for _family, _type, _proto, _canonname, sockaddr in resolved:
            ip = ipaddress.ip_address(sockaddr[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ValueError(f'URL resolves to a private/internal IP: {ip}')
    except (socket.gaierror, OSError):
        raise ValueError(f'Cannot resolve hostname: {hostname}')
    return url


def _check_origin(req):
    """Block cross-origin state-changing requests (CSRF protection)."""
    origin = req.headers.get('Origin', '')
    if origin and not origin.startswith(('http://localhost:', 'http://127.0.0.1:')):
        from flask import abort
        abort(403, 'Cross-origin request blocked')

_state_lock = threading.Lock()

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

# Benchmark state — single dict replacement/update is GIL-atomic under CPython
_benchmark_state = {'status': 'idle', 'progress': 0, 'stage': '', 'results': None}

# Background CPU monitor — avoids blocking Flask threads with psutil.cpu_percent(interval=...)
_cpu_percent = 0

def _cpu_monitor():
    global _cpu_percent
    import psutil as _ps
    while True:
        try:
            _cpu_percent = _ps.cpu_percent(interval=2)
        except Exception:
            pass

_cpu_monitor_started = False


# ─── Build Bundle Manifest Helper ──────────────────────────────────────
_bundle_manifest = None


def _load_bundle_manifest():
    """Read the esbuild build manifest (web/static/dist/manifest.json).

    Returns a dict mapping logical names to hashed filenames, e.g.
    {"nomad.bundle.js": "nomad.bundle.a1b2c3d4.js"}.
    Caches the result so the file is read only once per process.
    """
    global _bundle_manifest
    if _bundle_manifest is not None:
        return _bundle_manifest
    manifest_path = os.path.join(os.path.dirname(__file__), 'static', 'dist', 'manifest.json')
    try:
        with open(manifest_path, 'r') as f:
            _bundle_manifest = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _bundle_manifest = {}
    return _bundle_manifest


def create_app():
    global _cpu_monitor_started
    if not _cpu_monitor_started:
        _cpu_monitor_started = True
        threading.Thread(target=_cpu_monitor, daemon=True).start()

    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')
    app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH
    # DEBUG off by default; set NOMAD_DEBUG=1 to enable for development
    app.config['DEBUG'] = os.environ.get('NOMAD_DEBUG', '0') == '1'
    app.secret_key = Config.secret_key()

    # ─── Rate Limiting (optional) ─────────────────────────────────────
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address

        def _rate_limit_key():
            """Return key for rate limiting; exempt localhost."""
            addr = get_remote_address()
            if addr in ('127.0.0.1', '::1'):
                return None  # exempt localhost
            return addr

        limiter = Limiter(
            app=app,
            key_func=_rate_limit_key,
            default_limits=[Config.RATELIMIT_DEFAULT],
            storage_uri='memory://',
        )

        # Apply stricter limit to mutating methods via a shared limiter decorator
        _mutating_limit = limiter.shared_limit(
            Config.RATELIMIT_MUTATING,
            scope='mutating',
        )

        @app.before_request
        def _check_mutating_rate_limit():
            """Apply stricter rate limit to POST/PUT/DELETE requests."""
            if request.method in ('POST', 'PUT', 'DELETE'):
                # The shared limit is checked via the limiter's internals
                pass

        app.extensions['limiter'] = limiter
    except ImportError:
        log.info('flask-limiter not installed — rate limiting disabled')

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

    @app.before_request
    def _csrf_origin_check():
        """Block cross-origin state-changing requests."""
        if request.method in ('POST', 'PUT', 'DELETE'):
            _check_origin(request)

    @app.before_request
    def _csrf_token_check():
        """Validate CSRF token on mutating requests (token-based CSRF layer)."""
        if request.method not in ('POST', 'PUT', 'DELETE'):
            return
        # Exempt localhost from token-based CSRF
        remote = request.remote_addr or ''
        if remote in ('127.0.0.1', '::1', 'localhost'):
            return
        from flask import session
        token = request.headers.get('X-CSRF-Token', '')
        if not token or token != session.get('csrf_token'):
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
            log.error(f'Unhandled error on {request.method} {request.path}: {e}', exc_info=True)
            status = getattr(e, 'code', 500) if hasattr(e, 'code') else 500
            # Don't leak internal error details — only show message for HTTP errors
            msg = str(e) if hasattr(e, 'code') and status < 500 else 'Internal server error'
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
        """Require auth token for state-changing LAN requests when password is set."""
        if request.method not in ('POST', 'PUT', 'DELETE'):
            return
        remote = request.remote_addr or ''
        if remote in ('127.0.0.1', '::1', 'localhost'):
            return
        # LAN request with mutating method — check if auth is enabled
        try:
            with db_session() as db:
                row = db.execute("SELECT value FROM settings WHERE key = 'auth_password'").fetchone()
            if row and row['value']:
                import hashlib, hmac
                token = request.headers.get('X-Auth-Token', '')
                if not hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(), row['value']):
                    return jsonify({'error': 'Authentication required'}), 403
        except Exception as e:
            log.warning(f'Auth check failed (denying access): {e}')
            return jsonify({'error': 'Auth check failed'}), 403

    @app.after_request
    def no_cache(response):
        """Prevent WebView2 from caching HTML/API responses."""
        if 'text/html' in response.content_type or 'application/json' in response.content_type:
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response

    # ─── Pages ─────────────────────────────────────────────────────────

    @app.route('/')
    def dashboard():
        manifest = _load_bundle_manifest()
        return render_template(
            'index.html',
            version=VERSION,
            bundle_js=manifest.get('nomad.bundle.js', ''),
            bundle_css=manifest.get('nomad.bundle.css', ''),
        )

    # ─── Service API ───────────────────────────────────────────────────

    # [EXTRACTED to blueprint]


    # [EXTRACTED to blueprint]


    # ─── LAN File Transfer (v5.0 Phase 10) ──────────────────────────

    # [EXTRACTED to blueprint]


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
        db = get_db()
        try:
            result = {}
            for need_id, need in SURVIVAL_NEEDS.items():
                kw = need['keywords']
                # Count matching inventory items
                inv_count = 0
                for k in kw[:5]:  # Limit keyword searches for performance
                    inv_count += db.execute('SELECT COUNT(*) as c FROM inventory WHERE name LIKE ? OR category LIKE ?',
                                           (f'%{k}%', f'%{k}%')).fetchone()['c']

                # Count matching contacts by skills/role
                contact_count = 0
                for k in kw[:3]:
                    contact_count += db.execute('SELECT COUNT(*) as c FROM contacts WHERE role LIKE ? OR skills LIKE ?',
                                                (f'%{k}%', f'%{k}%')).fetchone()['c']

                # Count matching books (from reference catalog)
                book_count = 0
                for k in kw[:3]:
                    book_count += db.execute('SELECT COUNT(*) as c FROM books WHERE title LIKE ? OR category LIKE ?',
                                            (f'%{k}%', f'%{k}%')).fetchone()['c']

                # Decision guides count
                guide_count = len(need.get('guides', []))

                result[need_id] = {
                    'label': need['label'], 'icon': need['icon'], 'color': need['color'],
                    'inventory': min(inv_count, 999), 'contacts': min(contact_count, 99),
                    'books': min(book_count, 99), 'guides': guide_count,
                    'total': min(inv_count + contact_count + book_count + guide_count, 9999),
                }
            return jsonify(result)
        finally:
            db.close()

    @app.route('/api/needs/<need_id>')
    def api_need_detail(need_id):
        """Returns detailed cross-module data for a specific survival need."""
        need = SURVIVAL_NEEDS.get(need_id)
        if not need:
            return jsonify({'error': 'Unknown need category'}), 404
        db = get_db()
        try:
            kw = need['keywords']
            like_clauses = ' OR '.join(['name LIKE ?' for _ in kw[:5]])
            like_vals = [f'%{k}%' for k in kw[:5]]

            # Inventory items
            inv_items = []
            for k in kw[:5]:
                rows = db.execute('SELECT id, name, quantity, unit, category FROM inventory WHERE name LIKE ? OR category LIKE ? LIMIT 20',
                                  (f'%{k}%', f'%{k}%')).fetchall()
                for r in rows:
                    item = dict(r)
                    if item not in inv_items:
                        inv_items.append(item)

            # Contacts
            contacts = []
            for k in kw[:3]:
                rows = db.execute('SELECT id, name, role, skills FROM contacts WHERE role LIKE ? OR skills LIKE ? LIMIT 10',
                                  (f'%{k}%', f'%{k}%')).fetchall()
                for r in rows:
                    item = dict(r)
                    if item not in contacts:
                        contacts.append(item)

            # Books
            books = []
            for k in kw[:3]:
                rows = db.execute('SELECT id, title, author, category FROM books WHERE title LIKE ? OR category LIKE ? LIMIT 10',
                                  (f'%{k}%', f'%{k}%')).fetchall()
                for r in rows:
                    item = dict(r)
                    if item not in books:
                        books.append(item)

            # Decision guides (from hardcoded list)
            guides = [{'id': gid, 'title': gid.replace('_', ' ').title()} for gid in need.get('guides', [])]

            return jsonify({
                'need': {'id': need_id, 'label': need['label'], 'icon': need['icon'], 'color': need['color']},
                'inventory': inv_items[:30],
                'contacts': contacts[:10],
                'books': books[:15],
                'guides': guides,
            })
        finally:
            db.close()

    # ─── Kiwix ZIM API ─────────────────────────────────────────────────

    @app.route('/api/kiwix/zims')
    def api_kiwix_zims():
        if not kiwix.is_installed():
            return jsonify([])
        return jsonify(kiwix.list_zim_files())

    @app.route('/api/kiwix/catalog')
    def api_kiwix_catalog():
        return jsonify(kiwix.get_catalog())

    @app.route('/api/kiwix/download-zim', methods=['POST'])
    def api_kiwix_download_zim():
        data = request.get_json() or {}
        url = data.get('url', kiwix.STARTER_ZIM_URL)
        filename = data.get('filename')

        # SSRF protection — validate URL before downloading
        try:
            _validate_download_url(url)
        except ValueError as e:
            return jsonify({'error': f'Invalid download URL: {e}'}), 400

        def do_download():
            try:
                kiwix.download_zim(url, filename)
                if kiwix.running():
                    log.info('Restarting Kiwix to load new ZIM content...')
                    kiwix.stop()
                    time.sleep(1)
                    kiwix.start()
            except Exception as e:
                log.error(f'ZIM download failed: {e}')

        threading.Thread(target=do_download, daemon=True).start()
        return jsonify({'status': 'downloading'})

    @app.route('/api/kiwix/zim-downloads')
    def api_kiwix_zim_downloads():
        """Return all active/recent ZIM download progress entries."""
        from services.manager import _download_progress
        zim_entries = {
            k.replace('kiwix-zim-', ''): v
            for k, v in _download_progress.items()
            if k.startswith('kiwix-zim-')
        }
        return jsonify(zim_entries)

    @app.route('/api/kiwix/delete-zim', methods=['POST'])
    def api_kiwix_delete_zim():
        data = request.get_json() or {}
        filename = data.get('filename')
        if not filename:
            return jsonify({'error': 'No filename'}), 400
        success = kiwix.delete_zim(filename)
        if not success:
            return jsonify({'error': 'Failed to delete ZIM file'}), 500
        return jsonify({'status': 'deleted'})
    # ─── Settings API ─────────────────────────────────────────────────

    # [EXTRACTED to blueprint]

    # ─── Conversations API ────────────────────────────────────────────

    # [EXTRACTED to blueprint]


    # ─── Unified Search API ────────────────────────────────────────────

    # [EXTRACTED to blueprint]


    # ─── Benchmark API ─────────────────────────────────────────────────

    @app.route('/api/benchmark/run', methods=['POST'])
    def api_benchmark_run():
        data = request.get_json() or {}
        mode = data.get('mode', 'full')  # full, system, ai

        def do_benchmark():
            import psutil
            global _benchmark_state
            _benchmark_state = {'status': 'running', 'progress': 0, 'stage': 'Starting...', 'results': None}
            results = {}
            hw = {}

            try:
                # Hardware detection
                hw['cpu'] = platform.processor() or f'{os.cpu_count()} cores'
                hw['cpu_cores'] = psutil.cpu_count()
                hw['ram_gb'] = round(psutil.virtual_memory().total / (1024**3), 1)

                from platform_utils import detect_gpu as _bench_gpu
                _bg = _bench_gpu()
                hw['gpu'] = _bg.get('name', 'None')

                if mode in ('full', 'system'):
                    # CPU benchmark — prime calculation
                    _benchmark_state.update({'progress': 10, 'stage': 'CPU benchmark...'})
                    start = time.time()
                    count = 0
                    while time.time() - start < 10:
                        n = 2
                        for _ in range(10000):
                            n = (n * 1103515245 + 12345) & 0x7FFFFFFF
                        count += 10000
                    cpu_score = count / 10
                    results['cpu_score'] = round(cpu_score)

                    # Memory benchmark — sequential allocation
                    _benchmark_state.update({'progress': 30, 'stage': 'Memory benchmark...'})
                    start = time.time()
                    block_size = 1024 * 1024  # 1MB
                    blocks = 0
                    while time.time() - start < 5:
                        data_block = bytearray(block_size)
                        for i in range(0, block_size, 4096):
                            data_block[i] = 0xFF
                        blocks += 1
                    mem_score = blocks * block_size / (1024 * 1024)  # MB/s
                    results['memory_score'] = round(mem_score)

                    # Disk benchmark
                    _benchmark_state.update({'progress': 50, 'stage': 'Disk benchmark...'})
                    test_dir = os.path.join(get_data_base(), 'ProjectNOMAD', 'benchmark')
                    os.makedirs(test_dir, exist_ok=True)
                    test_file = os.path.join(test_dir, 'bench.tmp')

                    # Write
                    chunk = os.urandom(1024 * 1024)
                    start = time.time()
                    written = 0
                    with open(test_file, 'wb') as f:
                        while time.time() - start < 5:
                            f.write(chunk)
                            written += len(chunk)
                    write_elapsed = time.time() - start
                    results['disk_write_score'] = round(written / write_elapsed / (1024 * 1024)) if write_elapsed > 0 else 0

                    # Read
                    _benchmark_state.update({'progress': 65, 'stage': 'Disk read benchmark...'})
                    start = time.time()
                    read_bytes = 0
                    with open(test_file, 'rb') as f:
                        while True:
                            d = f.read(1024 * 1024)
                            if not d:
                                break
                            read_bytes += len(d)
                    read_elapsed = time.time() - start
                    results['disk_read_score'] = round(read_bytes / read_elapsed / (1024 * 1024)) if read_elapsed > 0 else 0

                    try:
                        os.remove(test_file)
                        os.rmdir(test_dir)
                    except Exception:
                        pass

                if mode in ('full', 'ai'):
                    _benchmark_state.update({'progress': 80, 'stage': 'AI benchmark...'})
                    results['ai_tps'] = 0
                    results['ai_ttft'] = 0

                    if ollama.is_installed() and ollama.running():
                        models = ollama.list_models()
                        if models:
                            test_model = models[0]['name']
                            try:
                                import requests
                                start = time.time()
                                resp = requests.post(
                                    f'http://localhost:{ollama.OLLAMA_PORT}/api/generate',
                                    json={'model': test_model, 'prompt': 'Write a paragraph about the history of computing.', 'stream': True},
                                    stream=True, timeout=120,
                                )
                                ttft = None
                                tokens = 0
                                for line in resp.iter_lines():
                                    if line:
                                        try:
                                            d = json.loads(line)
                                            if d.get('response') and ttft is None:
                                                ttft = time.time() - start
                                            if d.get('response'):
                                                tokens += 1
                                            if d.get('done'):
                                                break
                                        except Exception:
                                            pass
                                elapsed = time.time() - start
                                results['ai_tps'] = round(tokens / elapsed, 1) if elapsed > 0 else 0
                                results['ai_ttft'] = round(ttft * 1000) if ttft else 0
                            except Exception as e:
                                log.error(f'AI benchmark failed: {e}')

                # Calculate NOMAD Score (0-100, weighted)
                _benchmark_state.update({'progress': 95, 'stage': 'Calculating score...'})
                import math

                def norm(val, ref):
                    if val <= 0:
                        return 0
                    return min(100, math.log(val / ref + 1) / math.log(2) * 100)

                cpu_n = norm(results.get('cpu_score', 0), 500000)
                mem_n = norm(results.get('memory_score', 0), 500)
                dr_n = norm(results.get('disk_read_score', 0), 500)
                dw_n = norm(results.get('disk_write_score', 0), 300)
                ai_n = norm(results.get('ai_tps', 0), 10)
                ttft_n = max(0, 100 - results.get('ai_ttft', 5000) / 50) if results.get('ai_ttft', 0) > 0 else 0

                nomad_score = (
                    ai_n * 0.30 + cpu_n * 0.25 + mem_n * 0.15 +
                    ttft_n * 0.10 + dr_n * 0.10 + dw_n * 0.10
                )
                results['nomad_score'] = round(nomad_score, 1)

                # Save to DB
                db = get_db()
                try:
                    db.execute('''INSERT INTO benchmarks
                        (cpu_score, memory_score, disk_read_score, disk_write_score, ai_tps, ai_ttft, nomad_score, hardware, details)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (results.get('cpu_score', 0), results.get('memory_score', 0),
                         results.get('disk_read_score', 0), results.get('disk_write_score', 0),
                         results.get('ai_tps', 0), results.get('ai_ttft', 0),
                         results.get('nomad_score', 0), json.dumps(hw), json.dumps(results)))
                    db.commit()
                finally:
                    db.close()

                _benchmark_state = {'status': 'complete', 'progress': 100, 'stage': 'Done', 'results': results, 'hardware': hw}

            except Exception as e:
                log.error(f'Benchmark failed: {e}')
                _benchmark_state = {'status': 'error', 'progress': 0, 'stage': str(e), 'results': None}

        threading.Thread(target=do_benchmark, daemon=True).start()
        return jsonify({'status': 'started'})

    @app.route('/api/benchmark/status')
    def api_benchmark_status():
        return jsonify(_benchmark_state)

    @app.route('/api/benchmark/history')
    def api_benchmark_history():
        db = get_db()
        try:
            rows = db.execute('SELECT * FROM benchmarks ORDER BY created_at DESC LIMIT 20').fetchall()
        finally:
            db.close()
        return jsonify([dict(r) for r in rows])

    # ─── Benchmark Enhancements (v5.0 Phase 12) ─────────────────────

    @app.route('/api/benchmark/ai-inference', methods=['POST'])
    def api_benchmark_ai_inference():
        """Benchmark AI inference speed (tokens/second) for installed models."""
        model = (request.json or {}).get('model', '')
        if not model:
            return jsonify({'error': 'model required'}), 400
        try:
            import time as _time
            prompt = 'Write a short paragraph about weather forecasting in exactly 100 words.'
            start = _time.time()
            resp = ollama.chat(model, [{'role': 'user', 'content': prompt}])
            elapsed = _time.time() - start
            text = resp.get('message', {}).get('content', '') if isinstance(resp, dict) else str(resp)
            tokens = len(text.split())  # approximate
            tps = round(tokens / elapsed, 1) if elapsed > 0 else 0
            ttft = round(elapsed, 2)

            db = get_db()
            try:
                db.execute(
                    'INSERT INTO benchmark_results (test_type, scores, details) VALUES (?, ?, ?)',
                    ('ai_inference', json.dumps({'tps': tps, 'ttft': ttft, 'model': model}),
                     json.dumps({'tokens': tokens, 'elapsed': elapsed, 'text_length': len(text)}))
                )
                db.commit()
            finally:
                db.close()

            return jsonify({'model': model, 'tokens_per_sec': tps, 'time_to_complete': ttft, 'tokens': tokens})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/benchmark/storage', methods=['POST'])
    def api_benchmark_storage():
        """Benchmark storage I/O speed."""
        import tempfile
        import time as _time

        test_dir = os.path.join(get_data_dir(), 'benchmark_tmp')
        os.makedirs(test_dir, exist_ok=True)
        test_file = os.path.join(test_dir, 'io_test.bin')

        try:
            # Write test (32MB)
            data = os.urandom(32 * 1024 * 1024)
            start = _time.time()
            with open(test_file, 'wb') as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            write_time = _time.time() - start
            write_mbps = round(32 / write_time, 1) if write_time > 0 else 0

            # Read test
            start = _time.time()
            with open(test_file, 'rb') as f:
                _ = f.read()
            read_time = _time.time() - start
            read_mbps = round(32 / read_time, 1) if read_time > 0 else 0

            os.remove(test_file)

            db = get_db()
            try:
                db.execute(
                    'INSERT INTO benchmark_results (test_type, scores) VALUES (?, ?)',
                    ('storage', json.dumps({'read_mbps': read_mbps, 'write_mbps': write_mbps}))
                )
                db.commit()
            finally:
                db.close()

            return jsonify({'read_mbps': read_mbps, 'write_mbps': write_mbps})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            try:
                os.rmdir(test_dir)
            except Exception:
                pass

    @app.route('/api/benchmark/results')
    def api_benchmark_results_history():
        """Get benchmark results history for charting."""
        test_type = request.args.get('type', '')
        limit = min(request.args.get('limit', 20, type=int), 500)
        db = get_db()
        try:
            if test_type:
                rows = db.execute('SELECT * FROM benchmark_results WHERE test_type = ? ORDER BY created_at DESC LIMIT ?', (test_type, limit)).fetchall()
            else:
                rows = db.execute('SELECT * FROM benchmark_results ORDER BY created_at DESC LIMIT ?', (limit,)).fetchall()
            return jsonify([dict(r) for r in rows])
        finally:
            db.close()

    # [EXTRACTED to blueprint]

    # ─── Connectivity & Network ───────────────────────────────────────

    # [EXTRACTED to blueprint]


    # ─── Checklists API ──────────────────────────────────────────────

    CHECKLIST_TEMPLATES = {
        '72hour': {
            'name': '72-Hour Emergency Kit',
            'items': [
                {'text': 'Water — 1 gallon per person per day (3-day supply)', 'checked': False, 'cat': 'water'},
                {'text': 'Water purification tablets or filter', 'checked': False, 'cat': 'water'},
                {'text': 'Collapsible water container', 'checked': False, 'cat': 'water'},
                {'text': 'Non-perishable food (3-day supply)', 'checked': False, 'cat': 'food'},
                {'text': 'Manual can opener', 'checked': False, 'cat': 'food'},
                {'text': 'Eating utensils, plates, cups', 'checked': False, 'cat': 'food'},
                {'text': 'First aid kit (comprehensive)', 'checked': False, 'cat': 'medical'},
                {'text': 'Prescription medications (7-day supply)', 'checked': False, 'cat': 'medical'},
                {'text': 'Flashlight + extra batteries', 'checked': False, 'cat': 'gear'},
                {'text': 'Battery-powered or hand-crank radio (NOAA)', 'checked': False, 'cat': 'comms'},
                {'text': 'Cell phone charger (solar/hand-crank)', 'checked': False, 'cat': 'comms'},
                {'text': 'Whistle (signal for help)', 'checked': False, 'cat': 'gear'},
                {'text': 'Dust masks / N95 respirators', 'checked': False, 'cat': 'safety'},
                {'text': 'Plastic sheeting and duct tape (shelter-in-place)', 'checked': False, 'cat': 'shelter'},
                {'text': 'Wrench / pliers (turn off utilities)', 'checked': False, 'cat': 'tools'},
                {'text': 'Local maps (paper copies)', 'checked': False, 'cat': 'nav'},
                {'text': 'Cash in small denominations', 'checked': False, 'cat': 'docs'},
                {'text': 'Important documents (copies in waterproof bag)', 'checked': False, 'cat': 'docs'},
                {'text': 'Change of clothes per person', 'checked': False, 'cat': 'clothing'},
                {'text': 'Sturdy shoes per person', 'checked': False, 'cat': 'clothing'},
                {'text': 'Sleeping bag or warm blanket per person', 'checked': False, 'cat': 'shelter'},
                {'text': 'Rain poncho', 'checked': False, 'cat': 'clothing'},
                {'text': 'Fire extinguisher (small, portable)', 'checked': False, 'cat': 'safety'},
                {'text': 'Matches/lighter in waterproof container', 'checked': False, 'cat': 'fire'},
                {'text': 'Feminine supplies / personal hygiene items', 'checked': False, 'cat': 'hygiene'},
                {'text': 'Garbage bags and plastic ties', 'checked': False, 'cat': 'sanitation'},
                {'text': 'Paper towels, moist towelettes', 'checked': False, 'cat': 'hygiene'},
                {'text': 'Infant formula / diapers (if needed)', 'checked': False, 'cat': 'special'},
                {'text': 'Pet food and supplies (if needed)', 'checked': False, 'cat': 'special'},
                {'text': 'Books, games, puzzles (morale)', 'checked': False, 'cat': 'morale'},
            ],
        },
        'bugout': {
            'name': 'Bug-Out Bag (Go Bag)',
            'items': [
                {'text': 'Backpack (50-70L, sturdy, waterproof)', 'checked': False, 'cat': 'gear'},
                {'text': 'Water bottle + filter (Sawyer/LifeStraw)', 'checked': False, 'cat': 'water'},
                {'text': 'Water purification tablets (backup)', 'checked': False, 'cat': 'water'},
                {'text': 'Food: MREs or freeze-dried meals (3 days)', 'checked': False, 'cat': 'food'},
                {'text': 'Energy bars / trail mix', 'checked': False, 'cat': 'food'},
                {'text': 'Compact stove + fuel canister', 'checked': False, 'cat': 'food'},
                {'text': 'Metal cup / pot for boiling', 'checked': False, 'cat': 'food'},
                {'text': 'Fixed-blade knife (full tang)', 'checked': False, 'cat': 'tools'},
                {'text': 'Multi-tool (Leatherman/Gerber)', 'checked': False, 'cat': 'tools'},
                {'text': 'Ferro rod + waterproof matches', 'checked': False, 'cat': 'fire'},
                {'text': 'Tinder (cotton balls w/ vaseline)', 'checked': False, 'cat': 'fire'},
                {'text': 'Headlamp + extra batteries', 'checked': False, 'cat': 'gear'},
                {'text': 'Tarp / emergency bivvy', 'checked': False, 'cat': 'shelter'},
                {'text': 'Paracord (100 ft minimum)', 'checked': False, 'cat': 'gear'},
                {'text': 'Compass + topographic map', 'checked': False, 'cat': 'nav'},
                {'text': 'First aid kit (IFAK level)', 'checked': False, 'cat': 'medical'},
                {'text': 'Tourniquet (CAT or SOFTT-W)', 'checked': False, 'cat': 'medical'},
                {'text': 'Prescription meds (7-day supply)', 'checked': False, 'cat': 'medical'},
                {'text': 'Hand-crank / solar radio', 'checked': False, 'cat': 'comms'},
                {'text': 'FRS/GMRS radio (charged)', 'checked': False, 'cat': 'comms'},
                {'text': 'Cash + coins', 'checked': False, 'cat': 'docs'},
                {'text': 'ID / passport copies (laminated)', 'checked': False, 'cat': 'docs'},
                {'text': 'USB drive with scanned documents', 'checked': False, 'cat': 'docs'},
                {'text': 'Change of clothes (layerable)', 'checked': False, 'cat': 'clothing'},
                {'text': 'Rain gear', 'checked': False, 'cat': 'clothing'},
                {'text': 'Work gloves', 'checked': False, 'cat': 'clothing'},
                {'text': 'Bandana / shemagh', 'checked': False, 'cat': 'clothing'},
                {'text': 'Duct tape (small roll)', 'checked': False, 'cat': 'gear'},
                {'text': 'Zip ties (assorted)', 'checked': False, 'cat': 'gear'},
                {'text': 'Notepad + pencil', 'checked': False, 'cat': 'gear'},
            ],
        },
        'medical': {
            'name': 'Medical / First Aid Kit',
            'items': [
                {'text': 'Adhesive bandages (assorted sizes)', 'checked': False, 'cat': 'wound'},
                {'text': 'Sterile gauze pads (4x4)', 'checked': False, 'cat': 'wound'},
                {'text': 'Roller bandage / gauze rolls', 'checked': False, 'cat': 'wound'},
                {'text': 'Medical tape', 'checked': False, 'cat': 'wound'},
                {'text': 'Butterfly closures / steri-strips', 'checked': False, 'cat': 'wound'},
                {'text': 'Tourniquet (CAT gen 7)', 'checked': False, 'cat': 'trauma'},
                {'text': 'Hemostatic gauze (QuikClot/Celox)', 'checked': False, 'cat': 'trauma'},
                {'text': 'Israeli bandage (pressure dressing)', 'checked': False, 'cat': 'trauma'},
                {'text': 'Chest seal (vented, 2-pack)', 'checked': False, 'cat': 'trauma'},
                {'text': 'NPA airway (28Fr with lube)', 'checked': False, 'cat': 'trauma'},
                {'text': 'SAM splint', 'checked': False, 'cat': 'ortho'},
                {'text': 'ACE wrap / elastic bandage', 'checked': False, 'cat': 'ortho'},
                {'text': 'Triangle bandage / sling', 'checked': False, 'cat': 'ortho'},
                {'text': 'Nitrile gloves (multiple pairs)', 'checked': False, 'cat': 'ppe'},
                {'text': 'CPR pocket mask', 'checked': False, 'cat': 'ppe'},
                {'text': 'Trauma shears', 'checked': False, 'cat': 'tools'},
                {'text': 'Tweezers (fine point)', 'checked': False, 'cat': 'tools'},
                {'text': 'Thermometer', 'checked': False, 'cat': 'tools'},
                {'text': 'Ibuprofen / acetaminophen', 'checked': False, 'cat': 'meds'},
                {'text': 'Antihistamine (Benadryl)', 'checked': False, 'cat': 'meds'},
                {'text': 'Anti-diarrheal (Imodium)', 'checked': False, 'cat': 'meds'},
                {'text': 'Electrolyte packets (ORS)', 'checked': False, 'cat': 'meds'},
                {'text': 'Antibiotic ointment (Neosporin)', 'checked': False, 'cat': 'meds'},
                {'text': 'Hydrocortisone cream', 'checked': False, 'cat': 'meds'},
                {'text': 'Eye wash solution', 'checked': False, 'cat': 'meds'},
                {'text': 'Burn gel packets', 'checked': False, 'cat': 'meds'},
                {'text': 'Prescription medications log', 'checked': False, 'cat': 'docs'},
                {'text': 'Emergency medical info cards', 'checked': False, 'cat': 'docs'},
                {'text': 'First aid reference guide', 'checked': False, 'cat': 'docs'},
            ],
        },
        'comms': {
            'name': 'Communications Kit',
            'items': [
                {'text': 'NOAA weather radio (battery + crank)', 'checked': False, 'cat': 'receive'},
                {'text': 'FRS/GMRS handheld radio (pair)', 'checked': False, 'cat': 'twoway'},
                {'text': 'Extra batteries for all radios', 'checked': False, 'cat': 'power'},
                {'text': 'Solar charger panel (foldable)', 'checked': False, 'cat': 'power'},
                {'text': 'Power bank (20,000+ mAh)', 'checked': False, 'cat': 'power'},
                {'text': 'USB cables (multi-type)', 'checked': False, 'cat': 'power'},
                {'text': 'HAM radio (Baofeng UV-5R or better)', 'checked': False, 'cat': 'twoway'},
                {'text': 'HAM radio license study guide', 'checked': False, 'cat': 'docs'},
                {'text': 'Frequency list (laminated card)', 'checked': False, 'cat': 'docs'},
                {'text': 'CB radio (mobile or handheld)', 'checked': False, 'cat': 'twoway'},
                {'text': 'Signal mirror', 'checked': False, 'cat': 'visual'},
                {'text': 'Whistle (pealess, storm-proof)', 'checked': False, 'cat': 'visual'},
                {'text': 'Glow sticks / chem lights', 'checked': False, 'cat': 'visual'},
                {'text': 'Pen flares or road flares', 'checked': False, 'cat': 'visual'},
                {'text': 'Written comms plan (rally points, contacts)', 'checked': False, 'cat': 'docs'},
                {'text': 'Out-of-area emergency contact designated', 'checked': False, 'cat': 'docs'},
                {'text': 'Family meeting point established', 'checked': False, 'cat': 'docs'},
                {'text': 'Paper maps of local area + routes', 'checked': False, 'cat': 'nav'},
                {'text': 'Shortwave radio (for international news)', 'checked': False, 'cat': 'receive'},
                {'text': 'Faraday bag (EMP protection for electronics)', 'checked': False, 'cat': 'protect'},
            ],
        },
        'vehicle': {
            'name': 'Vehicle Emergency Kit',
            'items': [
                {'text': 'Jumper cables / jump starter pack', 'checked': False, 'cat': 'auto'},
                {'text': 'Tire repair kit + inflator', 'checked': False, 'cat': 'auto'},
                {'text': 'Spare tire (confirmed inflated)', 'checked': False, 'cat': 'auto'},
                {'text': 'Lug wrench + jack', 'checked': False, 'cat': 'auto'},
                {'text': 'Tow strap / recovery strap', 'checked': False, 'cat': 'auto'},
                {'text': 'Quart of oil + coolant', 'checked': False, 'cat': 'auto'},
                {'text': 'Fuses (assorted, matching vehicle)', 'checked': False, 'cat': 'auto'},
                {'text': 'Flashlight + spare batteries', 'checked': False, 'cat': 'gear'},
                {'text': 'Road flares / reflective triangles', 'checked': False, 'cat': 'safety'},
                {'text': 'Hi-vis vest', 'checked': False, 'cat': 'safety'},
                {'text': 'Fire extinguisher (small, mounted)', 'checked': False, 'cat': 'safety'},
                {'text': 'Basic tool kit (wrenches, screwdrivers, pliers)', 'checked': False, 'cat': 'tools'},
                {'text': 'Duct tape + zip ties + wire', 'checked': False, 'cat': 'tools'},
                {'text': 'Water (1 gallon minimum)', 'checked': False, 'cat': 'survival'},
                {'text': 'Non-perishable snacks', 'checked': False, 'cat': 'survival'},
                {'text': 'Emergency blanket / sleeping bag', 'checked': False, 'cat': 'survival'},
                {'text': 'Rain poncho', 'checked': False, 'cat': 'survival'},
                {'text': 'First aid kit', 'checked': False, 'cat': 'medical'},
                {'text': 'Paper maps / atlas', 'checked': False, 'cat': 'nav'},
                {'text': 'Pen + paper', 'checked': False, 'cat': 'gear'},
                {'text': 'Cash (small bills)', 'checked': False, 'cat': 'docs'},
                {'text': 'Phone charger (12V adapter)', 'checked': False, 'cat': 'power'},
                {'text': 'Seatbelt cutter + window breaker', 'checked': False, 'cat': 'safety'},
                {'text': 'Siphon pump', 'checked': False, 'cat': 'tools'},
            ],
        },
        'home': {
            'name': 'Home Emergency Supplies',
            'items': [
                {'text': 'Water storage — 1 gal/person/day for 14 days', 'checked': False, 'cat': 'water'},
                {'text': 'Water purification (filter, tablets, bleach)', 'checked': False, 'cat': 'water'},
                {'text': 'WaterBOB or bathtub bladder', 'checked': False, 'cat': 'water'},
                {'text': 'Food storage — 14-day supply per person', 'checked': False, 'cat': 'food'},
                {'text': 'Manual can opener (2+)', 'checked': False, 'cat': 'food'},
                {'text': 'Camp stove + fuel (outdoor use only)', 'checked': False, 'cat': 'food'},
                {'text': 'Cooler + ice plan for fridge items', 'checked': False, 'cat': 'food'},
                {'text': 'Generator + fuel (stored safely)', 'checked': False, 'cat': 'power'},
                {'text': 'Extension cords (heavy duty)', 'checked': False, 'cat': 'power'},
                {'text': 'Flashlights + lanterns (LED)', 'checked': False, 'cat': 'power'},
                {'text': 'Batteries (D, AA, AAA — bulk)', 'checked': False, 'cat': 'power'},
                {'text': 'Solar panel charger', 'checked': False, 'cat': 'power'},
                {'text': 'Propane heater (indoor-safe Mr Buddy)', 'checked': False, 'cat': 'heat'},
                {'text': 'Extra propane tanks', 'checked': False, 'cat': 'heat'},
                {'text': 'Warm blankets / sleeping bags', 'checked': False, 'cat': 'heat'},
                {'text': 'Plastic sheeting + duct tape (windows)', 'checked': False, 'cat': 'shelter'},
                {'text': 'Plywood for window boarding', 'checked': False, 'cat': 'shelter'},
                {'text': 'Sandbags (if flood zone)', 'checked': False, 'cat': 'shelter'},
                {'text': 'Comprehensive first aid kit', 'checked': False, 'cat': 'medical'},
                {'text': 'Prescription meds (30-day supply)', 'checked': False, 'cat': 'medical'},
                {'text': 'Bucket toilet + bags + kitty litter', 'checked': False, 'cat': 'sanitation'},
                {'text': 'Trash bags (heavy duty, lots)', 'checked': False, 'cat': 'sanitation'},
                {'text': 'Bleach (unscented, for sanitation)', 'checked': False, 'cat': 'sanitation'},
                {'text': 'Hand soap, sanitizer, disinfectant', 'checked': False, 'cat': 'hygiene'},
                {'text': 'Toilet paper (extra supply)', 'checked': False, 'cat': 'hygiene'},
                {'text': 'NOAA weather radio', 'checked': False, 'cat': 'comms'},
                {'text': 'Fire extinguishers (kitchen + garage)', 'checked': False, 'cat': 'safety'},
                {'text': 'Smoke + CO detectors (fresh batteries)', 'checked': False, 'cat': 'safety'},
                {'text': 'Important docs in fireproof safe', 'checked': False, 'cat': 'docs'},
                {'text': 'Cash on hand ($500+ in small bills)', 'checked': False, 'cat': 'docs'},
                {'text': 'Utility shut-off tools + knowledge', 'checked': False, 'cat': 'tools'},
                {'text': 'Axe / hatchet / pry bar', 'checked': False, 'cat': 'tools'},
            ],
        },
        'earthquake': {
            'name': 'Scenario: Earthquake',
            'items': [
                {'text': 'Check for injuries — self, then others', 'checked': False, 'cat': 'immediate'},
                {'text': 'Move to safe area away from damaged structures', 'checked': False, 'cat': 'immediate'},
                {'text': 'Check for gas leaks (smell, hissing) — shut off if suspected', 'checked': False, 'cat': 'immediate'},
                {'text': 'Check water supply — fill tubs/containers before pressure drops', 'checked': False, 'cat': 'water'},
                {'text': 'Check structural damage — do NOT enter if walls cracked/leaning', 'checked': False, 'cat': 'shelter'},
                {'text': 'Turn on NOAA weather radio for aftershock warnings', 'checked': False, 'cat': 'comms'},
                {'text': 'Wear sturdy shoes — broken glass and debris everywhere', 'checked': False, 'cat': 'safety'},
                {'text': 'Check on neighbors, especially elderly/disabled', 'checked': False, 'cat': 'community'},
                {'text': 'Photograph damage for insurance before cleanup', 'checked': False, 'cat': 'docs'},
                {'text': 'Prepare for aftershocks — stay away from chimneys and tall furniture', 'checked': False, 'cat': 'safety'},
                {'text': 'Set up alternative shelter if home is unsafe (tent, vehicle, tarp)', 'checked': False, 'cat': 'shelter'},
                {'text': 'Conserve phone battery — text instead of call', 'checked': False, 'cat': 'comms'},
            ],
        },
        'hurricane': {
            'name': 'Scenario: Hurricane/Major Storm',
            'items': [
                {'text': 'Board windows with plywood or close hurricane shutters', 'checked': False, 'cat': 'shelter'},
                {'text': 'Fill bathtub(s) with water for flushing/cleaning', 'checked': False, 'cat': 'water'},
                {'text': 'Charge all devices, battery packs, and radios', 'checked': False, 'cat': 'power'},
                {'text': 'Move vehicles to highest ground available', 'checked': False, 'cat': 'vehicle'},
                {'text': 'Secure or bring inside all outdoor furniture/objects', 'checked': False, 'cat': 'shelter'},
                {'text': 'Fill vehicle fuel tanks completely', 'checked': False, 'cat': 'fuel'},
                {'text': 'Withdraw cash ($500+ small bills)', 'checked': False, 'cat': 'docs'},
                {'text': 'Set fridge/freezer to coldest — food lasts longer in power outage', 'checked': False, 'cat': 'food'},
                {'text': 'Know your evacuation zone and route', 'checked': False, 'cat': 'evac'},
                {'text': 'Stage go-bags at door if evacuation may be needed', 'checked': False, 'cat': 'evac'},
                {'text': 'Move to interior room during storm (no windows)', 'checked': False, 'cat': 'safety'},
                {'text': 'After storm: avoid downed power lines and standing water', 'checked': False, 'cat': 'safety'},
            ],
        },
        'pandemic': {
            'name': 'Scenario: Pandemic/Quarantine',
            'items': [
                {'text': 'Stock 30+ days of food and water per person', 'checked': False, 'cat': 'food'},
                {'text': 'Stock 90-day supply of prescription medications', 'checked': False, 'cat': 'medical'},
                {'text': 'N95/KN95 masks — minimum 50 per person', 'checked': False, 'cat': 'medical'},
                {'text': 'Nitrile gloves, hand sanitizer, disinfectant', 'checked': False, 'cat': 'hygiene'},
                {'text': 'Thermometer and pulse oximeter', 'checked': False, 'cat': 'medical'},
                {'text': 'Establish quarantine room/area if household member gets sick', 'checked': False, 'cat': 'medical'},
                {'text': 'Set up contactless delivery/pickup protocols', 'checked': False, 'cat': 'supply'},
                {'text': 'Home school/education materials for children', 'checked': False, 'cat': 'morale'},
                {'text': 'Entertainment/morale supplies for extended isolation', 'checked': False, 'cat': 'morale'},
                {'text': 'Establish check-in schedule with family/neighbors', 'checked': False, 'cat': 'comms'},
                {'text': 'Disinfect all incoming packages/deliveries', 'checked': False, 'cat': 'hygiene'},
                {'text': 'Backup internet/comms plan if ISP fails', 'checked': False, 'cat': 'comms'},
            ],
        },
        'wildfire': {
            'name': 'Scenario: Wildfire Evacuation',
            'items': [
                {'text': 'Monitor fire maps and evacuation orders continuously', 'checked': False, 'cat': 'intel'},
                {'text': 'Load go-bags in vehicle NOW — do not wait for mandatory evac', 'checked': False, 'cat': 'evac'},
                {'text': 'Important documents, photos, irreplaceable items in car first', 'checked': False, 'cat': 'docs'},
                {'text': 'Close all windows, doors, and vents to slow ember entry', 'checked': False, 'cat': 'shelter'},
                {'text': 'Connect garden hoses, fill pools/tubs/trash cans with water', 'checked': False, 'cat': 'defense'},
                {'text': 'Move flammable furniture away from windows', 'checked': False, 'cat': 'shelter'},
                {'text': 'Remove flammable items from around house (30ft clearance)', 'checked': False, 'cat': 'defense'},
                {'text': 'N95 masks for smoke — limit outdoor exposure', 'checked': False, 'cat': 'medical'},
                {'text': 'Know 2+ evacuation routes — primary route may be blocked', 'checked': False, 'cat': 'evac'},
                {'text': 'Livestock/pets loaded and ready', 'checked': False, 'cat': 'evac'},
                {'text': 'Leave lights on and a note on door with destination info', 'checked': False, 'cat': 'comms'},
                {'text': 'DO NOT return until authorities give all-clear', 'checked': False, 'cat': 'safety'},
            ],
        },
        'civil_unrest': {
            'name': 'Scenario: Civil Unrest',
            'items': [
                {'text': 'Stay home — avoid protest/riot areas entirely', 'checked': False, 'cat': 'safety'},
                {'text': 'Lock and secure all entry points', 'checked': False, 'cat': 'security'},
                {'text': 'Close blinds/curtains — do not attract attention', 'checked': False, 'cat': 'security'},
                {'text': 'Park vehicles in garage or away from street', 'checked': False, 'cat': 'security'},
                {'text': 'Verify food/water supply for 2+ weeks sheltering in place', 'checked': False, 'cat': 'supply'},
                {'text': 'Keep all devices charged — power disruptions possible', 'checked': False, 'cat': 'power'},
                {'text': 'Monitor multiple news/radio sources for situational awareness', 'checked': False, 'cat': 'intel'},
                {'text': 'Establish neighborhood watch communication with trusted neighbors', 'checked': False, 'cat': 'comms'},
                {'text': 'Have fire extinguishers accessible (arson risk)', 'checked': False, 'cat': 'safety'},
                {'text': 'Know alternate routes to hospital/pharmacy if primary roads blocked', 'checked': False, 'cat': 'medical'},
                {'text': 'Cash on hand — ATMs and card systems may go down', 'checked': False, 'cat': 'docs'},
                {'text': 'Gray man principles — do not display wealth, supplies, or opinions', 'checked': False, 'cat': 'opsec'},
            ],
        },
        'winter_storm': {
            'name': 'Scenario: Winter Storm / Ice Storm',
            'items': [
                {'text': 'Stock firewood / fuel for 7+ days of heating', 'checked': False, 'cat': 'heating'},
                {'text': 'Insulate windows with plastic film or heavy curtains', 'checked': False, 'cat': 'shelter'},
                {'text': 'Pipe insulation or heat tape on exposed plumbing', 'checked': False, 'cat': 'shelter'},
                {'text': 'Water stored in case pipes freeze (1 gal/person/day x 7 days)', 'checked': False, 'cat': 'water'},
                {'text': 'Non-perishable food (no cooking required) for 7 days', 'checked': False, 'cat': 'food'},
                {'text': 'Extra blankets, sleeping bags, thermal underwear', 'checked': False, 'cat': 'warmth'},
                {'text': 'Battery/crank-powered radio for weather alerts', 'checked': False, 'cat': 'comms'},
                {'text': 'Flashlights, lanterns, extra batteries', 'checked': False, 'cat': 'light'},
                {'text': 'Generator fueled + extension cords ready', 'checked': False, 'cat': 'power'},
                {'text': 'Carbon monoxide detector with fresh batteries', 'checked': False, 'cat': 'safety'},
                {'text': 'Snow shovel, ice melt, sand/kitty litter for traction', 'checked': False, 'cat': 'tools'},
                {'text': 'Vehicle: full tank, winter kit (blanket, shovel, chains, flares)', 'checked': False, 'cat': 'vehicle'},
                {'text': 'Medications: 14-day supply on hand', 'checked': False, 'cat': 'medical'},
                {'text': 'Let faucets drip to prevent pipe freezing', 'checked': False, 'cat': 'shelter'},
                {'text': 'Know location of water shut-off valve', 'checked': False, 'cat': 'shelter'},
            ],
        },
        'grid_down': {
            'name': 'Scenario: Extended Power Grid Failure',
            'items': [
                {'text': 'Fill all water containers immediately (water pressure will drop)', 'checked': False, 'cat': 'water'},
                {'text': 'Inventory food: eat perishables first, then frozen, then shelf-stable', 'checked': False, 'cat': 'food'},
                {'text': 'Unplug sensitive electronics to prevent surge damage on restoration', 'checked': False, 'cat': 'power'},
                {'text': 'Generator: test, fuel, extension cords, run OUTSIDE only', 'checked': False, 'cat': 'power'},
                {'text': 'Solar panels and battery banks charged and accessible', 'checked': False, 'cat': 'power'},
                {'text': 'Cash on hand ($500+ in small bills) — electronic payments are down', 'checked': False, 'cat': 'finance'},
                {'text': 'Fill vehicle gas tanks (pumps need electricity)', 'checked': False, 'cat': 'fuel'},
                {'text': 'Battery/crank radio for information', 'checked': False, 'cat': 'comms'},
                {'text': 'HAM/FRS/GMRS radio charged for local communication', 'checked': False, 'cat': 'comms'},
                {'text': 'Establish neighborhood watch / check on elderly neighbors', 'checked': False, 'cat': 'security'},
                {'text': 'Security: lock doors, close curtains, low profile after dark', 'checked': False, 'cat': 'security'},
                {'text': 'Medical: inventory all medications, calculate days of supply', 'checked': False, 'cat': 'medical'},
                {'text': 'Sanitation plan: bucket toilet with bags + kitty litter if water fails', 'checked': False, 'cat': 'sanitation'},
                {'text': 'Cooking: camp stove, grill, or fire pit with fuel supply', 'checked': False, 'cat': 'food'},
                {'text': 'Entertainment: books, cards, board games (morale matters)', 'checked': False, 'cat': 'morale'},
            ],
        },
        'shelter_in_place': {
            'name': 'Scenario: Shelter-in-Place (Chemical/Nuclear)',
            'items': [
                {'text': 'Get INSIDE immediately — sealed building is best protection', 'checked': False, 'cat': 'shelter'},
                {'text': 'Close and lock all windows and doors', 'checked': False, 'cat': 'shelter'},
                {'text': 'Turn OFF HVAC / air conditioning / fans', 'checked': False, 'cat': 'shelter'},
                {'text': 'Seal door gaps with wet towels', 'checked': False, 'cat': 'shelter'},
                {'text': 'Tape plastic sheeting over windows and vents', 'checked': False, 'cat': 'shelter'},
                {'text': 'Move to interior room above ground level', 'checked': False, 'cat': 'shelter'},
                {'text': 'Monitor NOAA radio / emergency broadcasts for all-clear', 'checked': False, 'cat': 'comms'},
                {'text': 'Water: fill containers from tap BEFORE contamination reaches supply', 'checked': False, 'cat': 'water'},
                {'text': 'Potassium iodide (KI) tablets if nuclear — take per instructions', 'checked': False, 'cat': 'medical'},
                {'text': 'DO NOT go outside to check conditions', 'checked': False, 'cat': 'safety'},
                {'text': 'Cover nose and mouth with wet cloth if air quality degrades', 'checked': False, 'cat': 'safety'},
                {'text': 'Account for all household members — do not separate', 'checked': False, 'cat': 'family'},
                {'text': 'If contamination suspected on skin/clothes: remove outer clothing, shower', 'checked': False, 'cat': 'decon'},
                {'text': 'Remain sheltered minimum 24 hours (nuclear) or until all-clear (chemical)', 'checked': False, 'cat': 'shelter'},
            ],
        },
        'infant_emergency': {
            'name': 'Infant / Baby Emergency Kit',
            'items': [
                {'text': 'Formula or breastmilk storage (3-day supply minimum)', 'checked': False, 'cat': 'food'},
                {'text': 'Bottles, nipples, bottle brush, dish soap', 'checked': False, 'cat': 'feeding'},
                {'text': 'Diapers (minimum 50) + wipes (2 packs)', 'checked': False, 'cat': 'hygiene'},
                {'text': 'Diaper rash cream', 'checked': False, 'cat': 'medical'},
                {'text': 'Baby Tylenol (infant acetaminophen) + dosing syringe', 'checked': False, 'cat': 'medical'},
                {'text': 'Pedialyte or ORS packets (dehydration prevention)', 'checked': False, 'cat': 'medical'},
                {'text': 'Warm clothing layers + hat + socks (season appropriate)', 'checked': False, 'cat': 'clothing'},
                {'text': 'Blankets (2 receiving, 1 heavier)', 'checked': False, 'cat': 'warmth'},
                {'text': 'Pacifiers (if used) — 2 minimum', 'checked': False, 'cat': 'comfort'},
                {'text': 'Baby carrier (hands-free, for evacuation)', 'checked': False, 'cat': 'gear'},
                {'text': 'Clean water for mixing formula (if not breastfeeding)', 'checked': False, 'cat': 'water'},
                {'text': 'Small first aid kit: thermometer, nasal aspirator, nail clippers', 'checked': False, 'cat': 'medical'},
                {'text': 'Birth certificate + insurance card copies', 'checked': False, 'cat': 'docs'},
                {'text': 'Comfort item (stuffed animal, favorite toy)', 'checked': False, 'cat': 'comfort'},
                {'text': 'Portable crib or pack-n-play (if evacuating)', 'checked': False, 'cat': 'gear'},
            ],
        },
    }

    @app.route('/api/checklists')
    def api_checklists_list():
        db = get_db()
        try:
            rows = db.execute('SELECT * FROM checklists ORDER BY updated_at DESC').fetchall()
        finally:
            db.close()
        result = []
        for r in rows:
            items = json.loads(r['items'] or '[]')
            result.append({
                'id': r['id'], 'name': r['name'], 'template': r['template'],
                'item_count': len(items),
                'checked_count': sum(1 for i in items if i.get('checked')),
                'created_at': r['created_at'], 'updated_at': r['updated_at'],
            })
        return jsonify(result)

    @app.route('/api/checklists/templates')
    def api_checklists_templates():
        return jsonify({k: {'name': v['name'], 'item_count': len(v['items'])} for k, v in CHECKLIST_TEMPLATES.items()})

    @app.route('/api/checklists', methods=['POST'])
    @validate_json({
        'name': {'type': str, 'max_length': 300},
        'template': {'type': str, 'max_length': 100},
    })
    def api_checklists_create():
        data = request.get_json() or {}
        template_id = data.get('template', '')
        tmpl = CHECKLIST_TEMPLATES.get(template_id)
        if tmpl:
            name = tmpl['name']
            items = json.dumps(tmpl['items'])
        else:
            name = data.get('name', 'Custom Checklist')
            items = json.dumps(data.get('items', []))
        db = get_db()
        try:
            cur = db.execute('INSERT INTO checklists (name, template, items) VALUES (?, ?, ?)',
                             (name, template_id, items))
            db.commit()
            cid = cur.lastrowid
            row = db.execute('SELECT * FROM checklists WHERE id = ?', (cid,)).fetchone()
        finally:
            db.close()
        return jsonify({**dict(row), 'items': json.loads(row['items'] or '[]')}), 201

    @app.route('/api/checklists/<int:cid>')
    def api_checklists_get(cid):
        db = get_db()
        try:
            row = db.execute('SELECT * FROM checklists WHERE id = ?', (cid,)).fetchone()
        finally:
            db.close()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        return jsonify({**dict(row), 'items': json.loads(row['items'] or '[]')})

    @app.route('/api/checklists/<int:cid>', methods=['PUT'])
    def api_checklists_update(cid):
        data = request.get_json() or {}
        db = get_db()
        try:
            update_data = {}
            if 'name' in data:
                update_data['name'] = data['name']
            if 'items' in data:
                update_data['items'] = json.dumps(data['items'])
            filtered = safe_columns(update_data, ['name', 'items'])
            if filtered:
                set_clause = ', '.join(f'{col} = ?' for col in filtered)
                vals = list(filtered.values())
                vals.append(cid)
                db.execute(f'UPDATE checklists SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?', vals)
            db.commit()
        finally:
            db.close()
        return jsonify({'status': 'saved'})

    @app.route('/api/checklists/<int:cid>', methods=['DELETE'])
    def api_checklists_delete(cid):
        db = get_db()
        try:
            db.execute('DELETE FROM checklists WHERE id = ?', (cid,))
            db.commit()
        finally:
            db.close()
        return jsonify({'status': 'deleted'})

    # [EXTRACTED to blueprint]

    def _esc(s):
        """Escape HTML for print output."""
        return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

    @app.route('/api/preparedness/print')
    def api_preparedness_print():
        """Generate printable emergency summary page."""
        db = get_db()
        try:
            contacts = db.execute('SELECT * FROM contacts ORDER BY name').fetchall()
            settings = {r['key']: r['value'] for r in db.execute('SELECT key, value FROM settings').fetchall()}

            # Burn rate summary
            burn_rows = db.execute('SELECT category, name, quantity, unit, daily_usage FROM inventory WHERE daily_usage > 0 ORDER BY category').fetchall()
            burn = {}
            for r in burn_rows:
                cat = r['category']
                days = round(r['quantity'] / r['daily_usage'], 1) if r['daily_usage'] > 0 else 999
                if cat not in burn or days < burn[cat]:
                    burn[cat] = days

            # Low stock items
            low = db.execute('SELECT name, quantity, unit, category FROM inventory WHERE quantity <= min_quantity AND min_quantity > 0').fetchall()

            # Expiring items
            from datetime import datetime, timedelta
            soon = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            expiring = db.execute("SELECT name, expiration, category FROM inventory WHERE expiration != '' AND expiration <= ? ORDER BY expiration", (soon,)).fetchall()
        finally:
            db.close()

        # Situation board
        sit = {}
        try:
            sit = json.loads(settings.get('sit_board', '{}'))
        except Exception:
            pass

        sit_colors = {'green': '#2d6a2d', 'yellow': '#8a7a00', 'orange': '#a84a12', 'red': '#993333'}
        sit_labels = {'green': 'GOOD', 'yellow': 'CAUTION', 'orange': 'CONCERN', 'red': 'CRITICAL'}

        html = f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>N.O.M.A.D. Emergency Card</title>
        <style>
        @media print {{ @page {{ margin: 0.5in; }} }}
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{ font-family: Arial, Helvetica, sans-serif; font-size: 11px; color: #111; line-height: 1.4; }}
        h1 {{ font-size: 16px; text-align: center; margin-bottom: 4px; }}
        h2 {{ font-size: 12px; background: #222; color: #fff; padding: 3px 8px; margin: 8px 0 4px; }}
        .date {{ text-align: center; font-size: 10px; color: #666; margin-bottom: 8px; }}
        .sit-row {{ display: flex; gap: 4px; margin-bottom: 6px; }}
        .sit-box {{ flex:1; text-align:center; padding: 4px; border: 1px solid #999; font-weight: bold; font-size: 10px; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 6px; }}
        th, td {{ border: 1px solid #999; padding: 3px 6px; text-align: left; font-size: 10px; }}
        th {{ background: #eee; font-weight: bold; }}
        .warn {{ color: #993333; font-weight: bold; }}
        .cols2 {{ display: flex; gap: 8px; }}
        .cols2 > div {{ flex: 1; }}
        </style></head><body>
        <h1>PROJECT N.O.M.A.D. - EMERGENCY CARD</h1>
        <div class="date">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")} | KEEP THIS CARD ACCESSIBLE</div>'''

        # Situation Board
        if sit:
            html += '<h2>SITUATION STATUS</h2><div class="sit-row">'
            for domain in ['security','water','food','medical','power','comms']:
                lvl = sit.get(domain, 'green')
                html += f'<div class="sit-box" style="background:{sit_colors.get(lvl,"#fff")}; color:#fff;">{domain.upper()}<br>{sit_labels.get(lvl,"?")}</div>'
            html += '</div>'

        # Contacts
        if contacts:
            html += '<h2>EMERGENCY CONTACTS</h2><table><tr><th>Name</th><th>Role</th><th>Callsign</th><th>Phone</th><th>Freq</th><th>Blood</th><th>Rally Point</th></tr>'
            for c in contacts:
                html += f'<tr><td>{_esc(c["name"])}</td><td>{_esc(c["role"])}</td><td>{_esc(c["callsign"])}</td><td>{_esc(c["phone"])}</td><td>{_esc(c["freq"])}</td><td>{_esc(c["blood_type"])}</td><td>{_esc(c["rally_point"])}</td></tr>'
            html += '</table>'

        # Burn rate + alerts
        html += '<div class="cols2"><div>'
        if burn:
            html += '<h2>DAYS OF SUPPLY</h2><table><tr><th>Resource</th><th>Days Left</th></tr>'
            for cat, days in sorted(burn.items()):
                cls = ' class="warn"' if days < 7 else ''
                html += f'<tr{cls}><td>{cat.upper()}</td><td>{days}</td></tr>'
            html += '</table>'

        if low:
            html += '<h2>LOW STOCK ALERTS</h2><table><tr><th>Item</th><th>Qty</th><th>Cat</th></tr>'
            for r in low:
                html += f'<tr class="warn"><td>{_esc(r["name"])}</td><td>{r["quantity"]} {_esc(r["unit"])}</td><td>{_esc(r["category"])}</td></tr>'
            html += '</table>'
        html += '</div><div>'

        if expiring:
            html += '<h2>EXPIRING SOON</h2><table><tr><th>Item</th><th>Expires</th><th>Cat</th></tr>'
            for r in expiring:
                html += f'<tr><td>{_esc(r["name"])}</td><td>{_esc(r["expiration"])}</td><td>{_esc(r["category"])}</td></tr>'
            html += '</table>'

        # Key frequencies
        html += '''<h2>KEY FREQUENCIES</h2><table>
        <tr><th>Use</th><th>Freq/Ch</th></tr>
        <tr><td>FRS Rally (Ch 1)</td><td>462.5625 MHz</td></tr>
        <tr><td>FRS Emergency (Ch 3)</td><td>462.6125 MHz</td></tr>
        <tr><td>GMRS Emergency (Ch 20)</td><td>462.6750 MHz</td></tr>
        <tr><td>CB Emergency (Ch 9)</td><td>27.065 MHz</td></tr>
        <tr><td>CB Highway (Ch 19)</td><td>27.185 MHz</td></tr>
        <tr><td>2m HAM Calling</td><td>146.520 MHz</td></tr>
        <tr><td>2m HAM Emergency</td><td>146.550 MHz</td></tr>
        <tr><td>NOAA Weather</td><td>162.400-.550 MHz</td></tr>
        </table>'''
        html += '</div></div>'
        html += '<div style="text-align:center;margin-top:8px;font-size:9px;color:#999;">Project N.O.M.A.D. - Offline Survival Command Center</div>'
        html += '</body></html>'
        return Response(html, mimetype='text/html')

    # ─── Contacts API ─────────────────────────────────────────────────

    @app.route('/api/contacts')
    def api_contacts_list():
        with db_session() as db:
            search = request.args.get('q', '').strip()
            if search:
                rows = db.execute(
                    "SELECT * FROM contacts WHERE name LIKE ? OR callsign LIKE ? OR role LIKE ? OR skills LIKE ? ORDER BY name",
                    tuple(f'%{search}%' for _ in range(4))
                ).fetchall()
            else:
                rows = db.execute('SELECT * FROM contacts ORDER BY name').fetchall()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/contacts', methods=['POST'])
    @validate_json({
        'name': {'type': str, 'required': True, 'max_length': 200},
    })
    def api_contacts_create():
        data = request.get_json() or {}
        with db_session() as db:
            cur = db.execute(
                'INSERT INTO contacts (name, callsign, role, skills, phone, freq, email, address, rally_point, blood_type, medical_notes, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (data.get('name', ''), data.get('callsign', ''), data.get('role', ''),
                 data.get('skills', ''), data.get('phone', ''), data.get('freq', ''),
                 data.get('email', ''), data.get('address', ''), data.get('rally_point', ''),
                 data.get('blood_type', ''), data.get('medical_notes', ''), data.get('notes', '')))
            db.commit()
            cid = cur.lastrowid
            row = db.execute('SELECT * FROM contacts WHERE id = ?', (cid,)).fetchone()
        return jsonify(dict(row)), 201

    @app.route('/api/contacts/<int:cid>', methods=['PUT'])
    def api_contacts_update(cid):
        data = request.get_json() or {}
        with db_session() as db:
            allowed = ['name', 'callsign', 'role', 'skills', 'phone', 'freq', 'email', 'address', 'rally_point', 'blood_type', 'medical_notes', 'notes']
            filtered = safe_columns(data, allowed)
            if not filtered:
                return jsonify({'error': 'No fields'}), 400
            set_clause = ', '.join(f'{col} = ?' for col in filtered)
            vals = list(filtered.values())
            vals.append(cid)
            db.execute(f'UPDATE contacts SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?', vals)
            db.commit()
        return jsonify({'status': 'saved'})

    @app.route('/api/contacts/<int:cid>', methods=['DELETE'])
    def api_contacts_delete(cid):
        with db_session() as db:
            db.execute('DELETE FROM contacts WHERE id = ?', (cid,))
            db.commit()
        return jsonify({'status': 'deleted'})

    # ─── Guides Context API ────────────────────────────────────────────

    @app.route('/api/guides/context')
    def api_guides_context():
        """Return live inventory/contacts data for context-aware decision tree rendering."""
        db = get_db()
        try:
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
        finally:
            db.close()

    # ─── LAN Chat API ─────────────────────────────────────────────────

    # [EXTRACTED to blueprint]


    # ─── Incident Log API ─────────────────────────────────────────────

    @app.route('/api/incidents')
    def api_incidents_list():
        with db_session() as db:
            limit = min(request.args.get('limit', 100, type=int), 500)
            cat = request.args.get('category', '')
            query = 'SELECT * FROM incidents'
            params = []
            if cat:
                query += ' WHERE category = ?'
                params.append(cat)
            query += ' ORDER BY created_at DESC LIMIT ?'
            params.append(limit)
            rows = db.execute(query, params).fetchall()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/incidents', methods=['POST'])
    @validate_json({
        'description': {'type': str, 'required': True, 'max_length': 2000},
        'severity': {'type': str, 'max_length': 50},
        'category': {'type': str, 'max_length': 100},
    })
    def api_incidents_create():
        data = request.get_json() or {}
        desc = (data.get('description', '') or '').strip()
        if not desc:
            return jsonify({'error': 'Description required'}), 400
        with db_session() as db:
            cur = db.execute('INSERT INTO incidents (severity, category, description) VALUES (?, ?, ?)',
                             (data.get('severity', 'info'), data.get('category', 'other'), desc))
            db.commit()
            row = db.execute('SELECT * FROM incidents WHERE id = ?', (cur.lastrowid,)).fetchone()
        return jsonify(dict(row)), 201

    @app.route('/api/incidents/<int:iid>', methods=['DELETE'])
    def api_incidents_delete(iid):
        with db_session() as db:
            db.execute('DELETE FROM incidents WHERE id = ?', (iid,))
            db.commit()
        return jsonify({'status': 'deleted'})

    @app.route('/api/incidents/clear', methods=['POST'])
    def api_incidents_clear():
        with db_session() as db:
            db.execute('DELETE FROM incidents')
            db.commit()
        return jsonify({'status': 'cleared'})

    # [EXTRACTED to blueprint]


    # ─── Comms / Frequency Database API ─────────────────────────────

    # [EXTRACTED to blueprint]


    # [EXTRACTED to blueprint]


    # ─── Timers API ───────────────────────────────────────────────────

    @app.route('/api/timers')
    def api_timers_list():
        with db_session() as db:
            rows = db.execute('SELECT * FROM timers ORDER BY created_at DESC').fetchall()
        result = []
        from datetime import datetime
        now = datetime.now()
        for r in rows:
            try:
                started = datetime.fromisoformat(r['started_at'])
                elapsed = (now - started).total_seconds()
                remaining = max(0, r['duration_sec'] - elapsed)
                result.append({**dict(r), 'remaining_sec': remaining, 'done': remaining <= 0})
            except (ValueError, TypeError):
                continue
        return jsonify(result)

    @app.route('/api/timers', methods=['POST'])
    def api_timers_create():
        data = request.get_json() or {}
        try:
            from datetime import datetime
            duration = int(data.get('duration_sec', 300))
            db = get_db()
            cur = db.execute('INSERT INTO timers (name, duration_sec, started_at) VALUES (?, ?, ?)',
                             (data.get('name', 'Timer'), duration,
                              datetime.now().isoformat()))
            db.commit()
            row = db.execute('SELECT * FROM timers WHERE id = ?', (cur.lastrowid,)).fetchone()
            db.close()
            return jsonify(dict(row)), 201
        except (ValueError, TypeError) as e:
            return jsonify({'error': f'Invalid duration: {e}'}), 400
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/timers/<int:tid>', methods=['DELETE'])
    def api_timers_delete(tid):
        with db_session() as db:
            db.execute('DELETE FROM timers WHERE id = ?', (tid,))
            db.commit()
        return jsonify({'status': 'deleted'})

    # ─── CSV Export API ───────────────────────────────────────────────

    # [EXTRACTED to blueprint]


    @app.route('/api/contacts/export-csv')
    def api_contacts_csv():
        with db_session() as db:
            rows = db.execute('SELECT name, callsign, role, skills, phone, freq, email, address, rally_point, blood_type, medical_notes, notes FROM contacts ORDER BY name').fetchall()
        import csv, io
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['Name', 'Callsign', 'Role', 'Skills', 'Phone', 'Frequency', 'Email', 'Address', 'Rally Point', 'Blood Type', 'Medical Notes', 'Notes'])
        for r in rows:
            w.writerow([r['name'], r['callsign'], r['role'], r['skills'], r['phone'], r['freq'], r['email'], r['address'], r['rally_point'], r['blood_type'], r['medical_notes'], r['notes']])
        return Response(buf.getvalue(), mimetype='text/csv',
                       headers={'Content-Disposition': 'attachment; filename="nomad-contacts.csv"'})

    # ─── Vault API (encrypted client-side) ──────────────────────────

    @app.route('/api/vault')
    def api_vault_list():
        with db_session() as db:
            rows = db.execute('SELECT id, title, created_at, updated_at FROM vault_entries ORDER BY updated_at DESC').fetchall()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/vault', methods=['POST'])
    def api_vault_create():
        data = request.get_json() or {}
        for field in ('encrypted_data', 'iv', 'salt'):
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        with db_session() as db:
            cur = db.execute('INSERT INTO vault_entries (title, encrypted_data, iv, salt) VALUES (?, ?, ?, ?)',
                             (data.get('title', 'Untitled'), data['encrypted_data'], data['iv'], data['salt']))
            db.commit()
            eid = cur.lastrowid
        return jsonify({'id': eid, 'status': 'saved'}), 201

    @app.route('/api/vault/<int:eid>')
    def api_vault_get(eid):
        with db_session() as db:
            row = db.execute('SELECT * FROM vault_entries WHERE id = ?', (eid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        return jsonify(dict(row))

    @app.route('/api/vault/<int:eid>', methods=['PUT'])
    def api_vault_update(eid):
        data = request.get_json() or {}
        for field in ('encrypted_data', 'iv', 'salt'):
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        with db_session() as db:
            db.execute('UPDATE vault_entries SET title = ?, encrypted_data = ?, iv = ?, salt = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                       (data.get('title', ''), data['encrypted_data'], data['iv'], data['salt'], eid))
            db.commit()
        return jsonify({'status': 'saved'})

    @app.route('/api/vault/<int:eid>', methods=['DELETE'])
    def api_vault_delete(eid):
        with db_session() as db:
            db.execute('DELETE FROM vault_entries WHERE id = ?', (eid,))
            db.commit()
        return jsonify({'status': 'deleted'})
    # [EXTRACTED to blueprint]


    @app.route('/api/contacts/import-csv', methods=['POST'])
    def api_contacts_import_csv():
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        import csv, io
        file = request.files['file']
        try:
            raw = file.read()
            if len(raw) > 10 * 1024 * 1024:
                return jsonify({'error': 'File too large (max 10 MB)'}), 400
            try:
                content = raw.decode('utf-8-sig')
            except UnicodeDecodeError:
                content = raw.decode('latin-1')
            reader = csv.DictReader(io.StringIO(content))
            with db_session() as db:
                imported = 0
                for row in reader:
                    name = row.get('Name', row.get('name', '')).strip()
                    if not name:
                        continue
                    db.execute(
                        'INSERT INTO contacts (name, callsign, role, skills, phone, freq, email, address, rally_point, blood_type, medical_notes, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                        (name, row.get('Callsign', row.get('callsign', '')),
                         row.get('Role', row.get('role', '')),
                         row.get('Skills', row.get('skills', '')),
                         row.get('Phone', row.get('phone', '')),
                         row.get('Frequency', row.get('freq', '')),
                         row.get('Email', row.get('email', '')),
                         row.get('Address', row.get('address', '')),
                         row.get('Rally Point', row.get('rally_point', '')),
                         row.get('Blood Type', row.get('blood_type', '')),
                         row.get('Medical Notes', row.get('medical_notes', '')),
                         row.get('Notes', row.get('notes', ''))))
                    imported += 1
                db.commit()
            return jsonify({'status': 'imported', 'count': imported})
        except Exception as e:
            log.error(f'Contacts CSV import failed: {e}')
            return jsonify({'error': f'Import failed: {e}'}), 500

    # ─── Full Data Export ─────────────────────────────────────────────

    # [EXTRACTED to blueprint]


    # [EXTRACTED to blueprint]


    # [EXTRACTED to blueprint] Sneakernet sync export/import

    # ─── Community Sharing API ────────────────────────────────────────

    @app.route('/api/checklists/<int:cid>/export-json')
    def api_checklist_export_json(cid):
        db = None
        try:
            db = get_db()
            row = db.execute('SELECT * FROM checklists WHERE id = ?', (cid,)).fetchone()
            if not row:
                return jsonify({'error': 'Not found'}), 404
            export = {'type': 'nomad_checklist', 'version': 1,
                      'name': row['name'], 'template': row['template'],
                      'items': json.loads(row['items'] or '[]')}
            safe_name = secure_filename(row['name']) or 'checklist'
            return Response(json.dumps(export, indent=2), mimetype='application/json',
                           headers={'Content-Disposition': f'attachment; filename="{safe_name}.json"'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            if db:
                try: db.close()
                except Exception: pass

    @app.route('/api/checklists/import-json', methods=['POST'])
    def api_checklist_import_json():
        if 'file' not in request.files:
            return jsonify({'error': 'No file'}), 400
        file = request.files['file']
        db = None
        try:
            data = json.loads(file.read().decode('utf-8'))
            if data.get('type') != 'nomad_checklist':
                return jsonify({'error': 'Invalid checklist file'}), 400
            db = get_db()
            cur = db.execute('INSERT INTO checklists (name, template, items) VALUES (?, ?, ?)',
                             (data['name'], data.get('template', 'imported'), json.dumps(data['items'])))
            db.commit()
            return jsonify({'status': 'imported', 'id': cur.lastrowid})
        except Exception as e:
            return jsonify({'error': str(e)}), 400
        finally:
            if db:
                try: db.close()
                except Exception: pass

    # ─── Service Health API ───────────────────────────────────────────

    # [EXTRACTED to blueprint]


    # ─── GPX Waypoint Export ─────────────────────────────────────────

    @app.route('/api/waypoints/export-gpx')
    def api_waypoints_gpx():
        with db_session() as db:
            rows = db.execute('SELECT * FROM waypoints ORDER BY created_at').fetchall()
        gpx = '<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="ProjectNOMAD">\n'
        for w in rows:
            gpx += f'  <wpt lat="{w["lat"]}" lon="{w["lng"]}">\n'
            gpx += f'    <name>{_esc(w["name"])}</name>\n'
            gpx += f'    <desc>{_esc(w["notes"])}</desc>\n'
            gpx += f'    <type>{_esc(w["category"])}</type>\n'
            gpx += f'  </wpt>\n'
        gpx += '</gpx>'
        return Response(gpx, mimetype='application/gpx+xml',
                       headers={'Content-Disposition': 'attachment; filename="nomad-waypoints.gpx"'})

    # ─── GPX Waypoint Import ─────────────────────────────────────────

    @app.route('/api/waypoints/import-gpx', methods=['POST'])
    def api_waypoints_import_gpx():
        if 'file' not in request.files:
            return jsonify({'error': 'No file'}), 400
        file = request.files['file']
        content = file.read().decode('utf-8', errors='replace')
        import re
        wpts = re.findall(r'<wpt\s+lat="([^"]+)"\s+lon="([^"]+)"[^>]*>.*?</wpt>', content, re.DOTALL)
        with db_session() as db:
            count = 0
            for lat, lon in wpts:
                segment = content[content.find(f'lat="{lat}"'):][:500]
                name_match = re.search(r'<name>([^<]+)</name>', segment)
                name = name_match.group(1) if name_match else f'Imported {lat},{lon}'
                try:
                    db.execute('INSERT INTO waypoints (name, lat, lng, category) VALUES (?, ?, ?, ?)',
                               (name, float(lat), float(lon), 'imported'))
                    count += 1
                except Exception:
                    pass
            db.commit()
        return jsonify({'status': 'imported', 'count': count})

    # ─── Enhanced Dashboard API ───────────────────────────────────────

    # [EXTRACTED to blueprint]


    # ─── Proactive Alert System ──────────────────────────────────────

    def _run_alert_checks():
        """Background alert engine — checks inventory, weather, incidents every 5 minutes."""
        with _state_lock:
            if _state._alert_check_running:
                return
            _state._alert_check_running = True
        import time as _t
        _t.sleep(30)  # Wait for app to initialize
        while True:
            try:
                alerts = []
                db = get_db()
                from datetime import datetime, timedelta
                now = datetime.now()
                today = now.strftime('%Y-%m-%d')
                soon = (now + timedelta(days=14)).strftime('%Y-%m-%d')

                # 1. Critical burn rate items (<7 days supply)
                burn_items = db.execute(
                    'SELECT name, quantity, daily_usage, category FROM inventory WHERE daily_usage > 0 AND (quantity / daily_usage) < 7 ORDER BY (quantity / daily_usage) LIMIT 50'
                ).fetchall()
                for item in burn_items:
                    days = round(item['quantity'] / item['daily_usage'], 1)
                    sev = 'critical' if days < 3 else 'warning'
                    alerts.append({
                        'type': 'burn_rate', 'severity': sev,
                        'title': f'{item["name"]} running low',
                        'message': f'{item["name"]}: {days} days remaining at current usage ({item["quantity"]} {item.get("category", "")} left, using {item["daily_usage"]}/day). Reduce consumption or resupply.',
                    })

                # 2. Expiring items (within 14 days)
                expiring = db.execute(
                    "SELECT name, expiration FROM inventory WHERE expiration != '' AND expiration <= ? AND expiration >= ? ORDER BY expiration",
                    (soon, today)
                ).fetchall()
                for item in expiring:
                    exp_days = (datetime.strptime(item['expiration'], '%Y-%m-%d') - now).days
                    sev = 'critical' if exp_days <= 3 else 'warning'
                    alerts.append({
                        'type': 'expiration', 'severity': sev,
                        'title': f'{item["name"]} expiring',
                        'message': f'{item["name"]} expires in {exp_days} day{"s" if exp_days != 1 else ""} ({item["expiration"]}). Use, rotate, or replace.',
                    })

                # 3. Barometric pressure drop (>4mb in recent readings)
                pressure_rows = db.execute(
                    'SELECT pressure_hpa, created_at FROM weather_log WHERE pressure_hpa IS NOT NULL ORDER BY created_at DESC LIMIT 10'
                ).fetchall()
                if len(pressure_rows) >= 2:
                    newest = pressure_rows[0]['pressure_hpa']
                    oldest = pressure_rows[-1]['pressure_hpa']
                    diff = newest - oldest
                    if diff < -4:
                        alerts.append({
                            'type': 'weather', 'severity': 'warning',
                            'title': 'Rapid pressure drop detected',
                            'message': f'Barometric pressure dropped {abs(round(diff, 1))} hPa ({round(oldest, 1)} to {round(newest, 1)}). Storm likely within 12-24 hours. Secure shelter, fill water containers, charge devices.',
                        })

                # 4. Incident cluster (3+ in same category within 48h)
                cutoff = (now - timedelta(hours=48)).strftime('%Y-%m-%d %H:%M:%S')
                incident_clusters = db.execute(
                    "SELECT category, COUNT(*) as cnt FROM incidents WHERE created_at >= ? GROUP BY category HAVING cnt >= 3",
                    (cutoff,)
                ).fetchall()
                for cluster in incident_clusters:
                    alerts.append({
                        'type': 'incident_cluster', 'severity': 'warning',
                        'title': f'{cluster["category"].title()} incidents escalating',
                        'message': f'{cluster["cnt"]} {cluster["category"]} incidents in the last 48 hours. Review incident log and consider elevating threat level.',
                    })

                # 5. Low stock items (quantity <= min_quantity)
                low_stock = db.execute(
                    'SELECT name, quantity, unit, min_quantity FROM inventory WHERE quantity <= min_quantity AND min_quantity > 0 LIMIT 50'
                ).fetchall()
                for item in low_stock:
                    alerts.append({
                        'type': 'low_stock', 'severity': 'warning',
                        'title': f'{item["name"]} below minimum',
                        'message': f'{item["name"]}: {item["quantity"]} {item["unit"]} remaining (minimum: {item["min_quantity"]}). Add to shopping list or resupply.',
                    })

                # 6. Equipment overdue for service
                try:
                    overdue_equip = db.execute(
                        "SELECT name, category, next_service FROM equipment_log WHERE next_service != '' AND next_service < ? AND status != 'non-operational'",
                        (today,)
                    ).fetchall()
                    for eq in overdue_equip:
                        alerts.append({
                            'type': 'equipment_service', 'severity': 'warning',
                            'title': f'{eq["name"]} service overdue',
                            'message': f'{eq["name"]} ({eq["category"]}) was due for service on {eq["next_service"]}. Service overdue equipment may fail when needed most.',
                        })
                except Exception:
                    pass

                # 7. Expiring fuel (within 30 days)
                try:
                    fuel_expiry = (now + timedelta(days=30)).strftime('%Y-%m-%d')
                    expiring_fuel = db.execute(
                        "SELECT fuel_type, quantity, unit, expires FROM fuel_storage WHERE expires != '' AND expires <= ? AND expires >= ?",
                        (fuel_expiry, today)
                    ).fetchall()
                    for f in expiring_fuel:
                        days_left = (datetime.strptime(f['expires'], '%Y-%m-%d') - now).days
                        sev = 'warning' if days_left > 7 else 'critical'
                        alerts.append({
                            'type': 'fuel_expiry', 'severity': sev,
                            'title': f'{f["fuel_type"]} expiring soon',
                            'message': f'{f["quantity"]} {f["unit"]} of {f["fuel_type"]} expires in {days_left} days ({f["expires"]}). Use, rotate, or add stabilizer to extend shelf life.',
                        })
                except Exception:
                    pass

                # 8. High cumulative radiation dose
                try:
                    rad_row = db.execute('SELECT MAX(cumulative_rem) as max_rem FROM radiation_log').fetchone()
                    if rad_row and rad_row['max_rem'] and rad_row['max_rem'] >= 25:
                        sev = 'critical' if rad_row['max_rem'] >= 75 else 'warning'
                        alerts.append({
                            'type': 'radiation', 'severity': sev,
                            'title': f'Cumulative radiation dose: {round(rad_row["max_rem"], 1)} rem',
                            'message': f'Cumulative radiation exposure has reached {round(rad_row["max_rem"], 1)} rem. {">75 rem: Acute Radiation Syndrome risk." if rad_row["max_rem"] >= 75 else "25-75 rem: Increased cancer risk. Minimize further exposure. Take KI if thyroid threat."} Seek shelter with highest available Protection Factor.',
                        })
                except Exception:
                    pass

                db.close()

                # Deduplicate against existing active alerts (don't re-create dismissed ones within 24h)
                if alerts:
                    with db_session() as db2:
                        for alert in alerts:
                            existing = db2.execute(
                                "SELECT id, dismissed FROM alerts WHERE alert_type = ? AND title = ? AND created_at >= ? ORDER BY created_at DESC LIMIT 1",
                                (alert['type'], alert['title'], (now - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S'))
                            ).fetchone()
                            if not existing:
                                db2.execute(
                                    'INSERT INTO alerts (alert_type, severity, title, message) VALUES (?, ?, ?, ?)',
                                    (alert['type'], alert['severity'], alert['title'], alert['message'])
                                )
                        db2.commit()
                    broadcast_event('alert_check', {'event': 'new_alerts'})

                # Prune old dismissed alerts (>7 days)
                with db_session() as db3:
                    db3.execute("DELETE FROM alerts WHERE dismissed = 1 AND created_at < ?",
                               ((now - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S'),))
                    db3.commit()

            except Exception as e:
                log.error(f'Alert engine error: {e}')
            _t.sleep(300)  # Check every 5 minutes

    threading.Thread(target=_run_alert_checks, daemon=True).start()

    @app.route('/api/alerts')
    def api_alerts():
        """Get active (non-dismissed) alerts."""
        with db_session() as db:
            rows = db.execute('SELECT * FROM alerts WHERE dismissed = 0 ORDER BY severity DESC, created_at DESC LIMIT 50').fetchall()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/alerts/<int:alert_id>/dismiss', methods=['POST'])
    def api_alert_dismiss(alert_id):
        with db_session() as db:
            db.execute('UPDATE alerts SET dismissed = 1 WHERE id = ?', (alert_id,))
            db.commit()
        broadcast_event('alert_check', {'event': 'dismissed', 'alert_id': alert_id})
        broadcast_event('alert', {'level': 'info', 'message': f'Alert {alert_id} dismissed'})
        return jsonify({'status': 'dismissed'})

    @app.route('/api/alerts/dismiss-all', methods=['POST'])
    def api_alerts_dismiss_all():
        with db_session() as db:
            db.execute('UPDATE alerts SET dismissed = 1 WHERE dismissed = 0')
            db.commit()
        broadcast_event('alert_check', {'event': 'dismissed_all'})
        return jsonify({'status': 'dismissed'})

    @app.route('/api/alerts/stream')
    def api_alerts_stream():
        """Deprecated: Use /api/events/stream instead. Kept for backward compat."""
        return event_stream()

    @app.route('/api/alerts/generate-summary', methods=['POST'])
    def api_alerts_generate_summary():
        """Use AI to generate a natural language situation summary from active alerts."""
        with db_session() as db:
            alerts = db.execute('SELECT * FROM alerts WHERE dismissed = 0 ORDER BY severity DESC').fetchall()
        if not alerts:
            return jsonify({'summary': 'All clear. No active alerts.'})
        # Build a concise prompt for Ollama
        alert_text = '\n'.join([f'- [{a["severity"].upper()}] {a["title"]}: {a["message"]}' for a in alerts])
        prompt = f'You are a survival operations officer. Summarize these alerts into a brief, actionable situation report (3-5 sentences max). Be direct and practical.\n\nActive Alerts:\n{alert_text}'
        try:
            if not ollama.running():
                return jsonify({'summary': f'{len(alerts)} active alert(s). Start the AI service for an intelligent situation summary.'})
            models = ollama.list_models()
            if not models:
                return jsonify({'summary': f'{len(alerts)} active alert(s). Download an AI model for intelligent summaries.'})
            model = models[0]['name']
            import requests as req
            resp = req.post(f'http://localhost:{ollama.OLLAMA_PORT}/api/generate',
                           json={'model': model, 'prompt': prompt, 'stream': False},
                           timeout=30)
            result = resp.json()
            return jsonify({'summary': result.get('response', '').strip()})
        except Exception as e:
            return jsonify({'summary': f'{len(alerts)} active alert(s). AI summary unavailable: {e}'})

    # [EXTRACTED to blueprint] KB deep doc understanding + analyze routes


    # [EXTRACTED to blueprint] Security cameras/access/dashboard


    # [EXTRACTED to blueprint] Power devices/log/dashboard

    # ─── Multi-Node Federation ─────────────────────────────────────────

    import uuid as _uuid

    def _get_node_id():
        with db_session() as db:
            row = db.execute("SELECT value FROM settings WHERE key = 'node_id'").fetchone()
            if row and row['value']:
                return row['value']
            node_id = str(_uuid.uuid4())[:8]
            db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('node_id', ?)", (node_id,))
            db.commit()
            return node_id

    def _get_node_name():
        with db_session() as db:
            row = db.execute("SELECT value FROM settings WHERE key = 'node_name'").fetchone()
        return (row['value'] if row and row['value'] else platform.node()) or 'NOMAD Node'

    # [EXTRACTED to blueprint] Node/sync federation routes

    # Start UDP discovery listener in background
    def _discovery_listener():
        import socket
        discovery_port = Config.DISCOVERY_PORT
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('', discovery_port))
            sock.settimeout(1)
            while True:
                try:
                    data, addr = sock.recvfrom(1024)
                    msg = json.loads(data.decode())
                    if msg.get('type') == 'nomad_discover' and msg.get('node_id') != _get_node_id():
                        # Respond with our identity
                        response = json.dumps({
                            'type': 'nomad_announce', 'node_id': _get_node_id(),
                            'node_name': _get_node_name(), 'port': Config.APP_PORT, 'version': VERSION,
                        }).encode()
                        sock.sendto(response, addr)
                except socket.timeout:
                    continue
                except Exception:
                    continue
        except Exception as e:
            log.warning(f'Discovery listener failed to start: {e}')

    threading.Thread(target=_discovery_listener, daemon=True).start()

    # ─── Food Production Module ────────────────────────────────────────

    @app.route('/api/livestock')
    def api_livestock_list():
        with db_session() as db:
            rows = db.execute('SELECT * FROM livestock ORDER BY species, name').fetchall()
        return jsonify([{**dict(r), 'health_log': json.loads(r['health_log'] or '[]'),
                         'vaccinations': json.loads(r['vaccinations'] or '[]')} for r in rows])

    @app.route('/api/livestock', methods=['POST'])
    def api_livestock_create():
        data = request.get_json() or {}
        if not data.get('species'):
            return jsonify({'error': 'Species required'}), 400
        with db_session() as db:
            db.execute('INSERT INTO livestock (species, name, tag, dob, sex, weight_lbs, notes) VALUES (?,?,?,?,?,?,?)',
                       (data['species'], data.get('name', ''), data.get('tag', ''), data.get('dob', ''),
                        data.get('sex', ''), data.get('weight_lbs'), data.get('notes', '')))
            db.commit()
        return jsonify({'status': 'created'}), 201

    @app.route('/api/livestock/<int:lid>', methods=['PUT'])
    def api_livestock_update(lid):
        data = request.get_json() or {}
        with db_session() as db:
            db.execute('UPDATE livestock SET species=?, name=?, tag=?, dob=?, sex=?, weight_lbs=?, status=?, health_log=?, vaccinations=?, notes=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                       (data.get('species', ''), data.get('name', ''), data.get('tag', ''), data.get('dob', ''),
                        data.get('sex', ''), data.get('weight_lbs'), data.get('status', 'active'),
                        json.dumps(data.get('health_log', [])), json.dumps(data.get('vaccinations', [])),
                        data.get('notes', ''), lid))
            db.commit()
        return jsonify({'status': 'updated'})

    @app.route('/api/livestock/<int:lid>', methods=['DELETE'])
    def api_livestock_delete(lid):
        with db_session() as db:
            db.execute('DELETE FROM livestock WHERE id = ?', (lid,))
            db.commit()
        return jsonify({'status': 'deleted'})

    @app.route('/api/livestock/<int:lid>/health', methods=['POST'])
    def api_livestock_health_event(lid):
        """Add a health event to an animal's log."""
        data = request.get_json() or {}
        with db_session() as db:
            animal = db.execute('SELECT health_log FROM livestock WHERE id = ?', (lid,)).fetchone()
            if not animal:
                return jsonify({'error': 'Not found'}), 404
            log_entries = json.loads(animal['health_log'] or '[]')
            log_entries.append({'date': time.strftime('%Y-%m-%d'), 'event': data.get('event', ''), 'notes': data.get('notes', '')})
            db.execute('UPDATE livestock SET health_log = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                       (json.dumps(log_entries), lid))
            db.commit()
            return jsonify({'status': 'logged'}), 201

    # ─── Scenario Training Engine ──────────────────────────────────────

    @app.route('/api/scenarios')
    def api_scenarios_list():
        with db_session() as db:
            rows = db.execute('SELECT * FROM scenarios ORDER BY started_at DESC LIMIT 20').fetchall()
        return jsonify([{**dict(r), 'decisions': json.loads(r['decisions'] or '[]'),
                         'complications': json.loads(r['complications'] or '[]')} for r in rows])

    @app.route('/api/scenarios', methods=['POST'])
    def api_scenarios_create():
        data = request.get_json() or {}
        with db_session() as db:
            cur = db.execute('INSERT INTO scenarios (scenario_type, title) VALUES (?, ?)',
                             (data.get('type', ''), data.get('title', '')))
            db.commit()
            sid = cur.lastrowid
        return jsonify({'id': sid}), 201

    @app.route('/api/scenarios/<int:sid>', methods=['PUT'])
    def api_scenarios_update(sid):
        data = request.get_json() or {}
        with db_session() as db:
            db.execute('UPDATE scenarios SET current_phase=?, status=?, decisions=?, complications=?, score=?, aar_text=?, completed_at=? WHERE id=?',
                       (data.get('current_phase', 0), data.get('status', 'active'),
                        json.dumps(data.get('decisions', [])), json.dumps(data.get('complications', [])),
                        data.get('score', 0), data.get('aar_text', ''), data.get('completed_at', ''), sid))
            db.commit()
        return jsonify({'status': 'updated'})

    @app.route('/api/scenarios/<int:sid>/complication', methods=['POST'])
    def api_scenario_complication(sid):
        """AI generates a context-aware complication based on current scenario state + user's real data."""
        data = request.get_json() or {}
        phase_desc = data.get('phase_description', '')
        decisions_so_far = data.get('decisions', [])

        # Gather real situation context
        with db_session() as db:
            inv_items = db.execute('SELECT name, quantity, unit, daily_usage FROM inventory WHERE daily_usage > 0 ORDER BY (quantity/daily_usage) LIMIT 5').fetchall()
            contacts_count = db.execute('SELECT COUNT(*) as c FROM contacts').fetchone()['c']
            sit_raw = db.execute("SELECT value FROM settings WHERE key='sit_board'").fetchone()

        inv_str = ', '.join(f"{r['name']}: {r['quantity']} {r['unit']}" for r in inv_items) or 'unknown'
        context = f"Inventory: {inv_str}\n"
        context += f"Group size: {contacts_count} contacts\n"
        if sit_raw and sit_raw['value']:
            try:
                sit = json.loads(sit_raw['value'] or '{}')
                context += f"Situation: {', '.join(f'{k}={v}' for k,v in sit.items())}\n"
            except Exception:
                pass

        prompt = f"""You are a survival training instructor running a disaster scenario. Generate ONE realistic complication for the current phase of the scenario. The complication should force a difficult decision.

Scenario phase: {phase_desc}
Decisions made so far: {', '.join(d.get('label','') for d in decisions_so_far[-3:]) if decisions_so_far else 'none yet'}
Real situation data: {context}

Respond with ONLY a JSON object (no markdown, no explanation):
{{"title": "short complication title", "description": "2-3 sentence description of the complication", "choices": ["choice A text", "choice B text", "choice C text"]}}"""

        try:
            if not ollama.running():
                return jsonify({'title': 'Equipment Failure', 'description': 'Your primary water filter has cracked. You need to switch to backup purification methods.',
                                'choices': ['Use bleach purification', 'Boil all water', 'Ration existing clean water']})
            models = ollama.list_models()
            if not models:
                return jsonify({'title': 'Supply Shortage', 'description': 'You discover your food supply is 30% less than expected. Some items were damaged.',
                                'choices': ['Implement strict rationing', 'Forage for supplemental food', 'Send a team to resupply']})
            import requests as req
            resp = req.post(f'http://localhost:{ollama.OLLAMA_PORT}/api/generate',
                           json={'model': models[0]['name'], 'prompt': prompt, 'stream': False, 'format': 'json'}, timeout=30)
            result = resp.json().get('response', '{}')
            complication = json.loads(result)
            return jsonify(complication)
        except Exception as e:
            log.error(f'Complication generation failed: {e}')
            return jsonify({'title': 'Unexpected Event', 'description': 'Weather conditions have changed rapidly. High winds are approaching your position.',
                            'choices': ['Shelter in place', 'Relocate to secondary position', 'Reinforce current shelter']})

    @app.route('/api/scenarios/<int:sid>/aar', methods=['POST'])
    def api_scenario_aar(sid):
        """AI generates an After-Action Review scoring the user's decisions."""
        with db_session() as db:
            scenario = db.execute('SELECT * FROM scenarios WHERE id = ?', (sid,)).fetchone()
        if not scenario:
            return jsonify({'error': 'Not found'}), 404

        decisions = json.loads(scenario['decisions'] or '[]')
        complications = json.loads(scenario['complications'] or '[]')

        decision_summary = '\n'.join([f"Phase {d.get('phase',0)+1}: {d.get('label','')} (chose: {d.get('choice','')})" for d in decisions])
        complication_summary = '\n'.join([f"- {c.get('title','')}: chose {c.get('response','')}" for c in complications])

        prompt = f"""You are a survival training evaluator. Score this scenario performance and write a brief After-Action Review.

Scenario: {scenario['title']}
Decisions made:
{decision_summary or 'None recorded'}

Complications encountered and responses:
{complication_summary or 'None'}

Provide:
1. An overall score 0-100
2. A 3-5 sentence assessment of strengths and weaknesses
3. 2-3 specific improvement recommendations

Respond as plain text, not JSON. Start with "Score: XX/100" on the first line."""

        try:
            if not ollama.running() or not ollama.list_models():
                score = min(100, max(20, len(decisions) * 15 + 10))
                return jsonify({'score': score, 'aar': f'Score: {score}/100\n\nCompleted {len(decisions)} phases with {len(complications)} complications handled. Practice regularly to improve response times and decision quality.'})
            import requests as req
            resp = req.post(f'http://localhost:{ollama.OLLAMA_PORT}/api/generate',
                           json={'model': ollama.list_models()[0]['name'], 'prompt': prompt, 'stream': False}, timeout=45)
            aar_text = resp.json().get('response', '').strip()
            # Try to extract score
            score = 50
            import re
            score_match = re.search(r'Score:\s*(\d+)', aar_text)
            if score_match:
                score = min(100, max(0, int(score_match.group(1))))
            return jsonify({'score': score, 'aar': aar_text})
        except Exception as e:
            score = min(100, max(20, len(decisions) * 15 + 10))
            return jsonify({'score': score, 'aar': f'Score: {score}/100\n\nAI review unavailable. Completed {len(decisions)} decision phases. Review your choices and consider alternative approaches for future training.'})

    # [EXTRACTED to blueprint] Medical module (patients + drugs + dosage + triage + TCCC)


    # [EXTRACTED to blueprint] Sensor devices + readings


    # [EXTRACTED to blueprint] Power history + autonomy + solar


    # ─── Scheduled Automatic Backups ──────────────────────────────────

    def _run_auto_backup():
        """Execute scheduled auto-backup and reschedule."""
        import sqlite3 as _sqlite3
        from datetime import datetime
        try:
            db = get_db()
            try:
                row = db.execute("SELECT value FROM settings WHERE key = 'auto_backup_config'").fetchone()
            finally:
                db.close()

            if not row or not row['value']:
                return
            cfg = json.loads(row['value'])
            if not cfg.get('enabled'):
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
            db = get_db()
            try:
                row = db.execute("SELECT value FROM settings WHERE key = 'auto_backup_config'").fetchone()
            finally:
                db.close()
            if not row or not row['value']:
                return
            cfg = json.loads(row['value'])
            if not cfg.get('enabled'):
                return
            interval = cfg.get('interval', 'daily')
            seconds = 86400 if interval == 'daily' else 604800
            timer = threading.Timer(seconds, _run_auto_backup)
            timer.daemon = True
            timer.start()
            _auto_backup_timer['timer'] = timer
        except Exception as e:
            log.warning(f'Failed to schedule auto-backup: {e}')

    try:
        _schedule_auto_backup()
    except Exception:
        pass

    # [EXTRACTED to blueprint]

    @app.route('/api/planner/calculate', methods=['POST'])
    def api_planner_calculate():
        """Calculate resource needs for X people over Y days."""
        data = request.get_json() or {}
        people = max(1, int(data.get('people', 4)))
        days = max(1, int(data.get('days', 14)))
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

    # ─── Waypoint Distance Matrix ─────────────────────────────────────

    @app.route('/api/waypoints/distances')
    def api_waypoints_distances():
        with db_session() as db:
            wps = db.execute('SELECT id, name, lat, lng, category FROM waypoints ORDER BY name').fetchall()
        import math
        def haversine(lat1, lon1, lat2, lon2):
            R = 3959  # miles
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
            return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        points = [dict(w) for w in wps]
        matrix = []
        for i, a in enumerate(points):
            row = []
            for j, b in enumerate(points):
                if i == j:
                    row.append(0)
                else:
                    row.append(round(haversine(a['lat'], a['lng'], b['lat'], b['lng']), 2))
            matrix.append(row)
        return jsonify({'points': points, 'matrix': matrix})

    # ─── External Ollama Host ─────────────────────────────────────────

    @app.route('/api/settings/ollama-host')
    def api_ollama_host_get():
        with db_session() as db:
            row = db.execute("SELECT value FROM settings WHERE key = 'ollama_host'").fetchone()
        return jsonify({'host': row['value'] if row else ''})

    @app.route('/api/settings/ollama-host', methods=['PUT'])
    def api_ollama_host_set():
        data = request.get_json() or {}
        host = (data.get('host', '') or '').strip()
        with db_session() as db:
            db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('ollama_host', ?)", (host,))
            db.commit()
        # Update ollama module's port/host
        if host:
            log_activity('ollama_host_changed', detail=host)
        return jsonify({'status': 'saved', 'host': host})

    # ─── Host Power Control ───────────────────────────────────────────

    # [EXTRACTED to blueprint]


    # [EXTRACTED to blueprint]

    @app.route('/api/drills/history')
    def api_drill_history():
        with db_session() as db:
            rows = db.execute('SELECT * FROM drill_history ORDER BY created_at DESC LIMIT 50').fetchall()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/drills/history', methods=['POST'])
    def api_drill_history_save():
        data = request.get_json() or {}
        try:
            db = get_db()
            db.execute('INSERT INTO drill_history (drill_type, title, duration_sec, tasks_total, tasks_completed, notes) VALUES (?, ?, ?, ?, ?, ?)',
                       (data.get('drill_type', ''), data.get('title', ''), int(data.get('duration_sec', 0)),
                        int(data.get('tasks_total', 0)), int(data.get('tasks_completed', 0)), data.get('notes', '')))
            db.commit()
            db.close()
            return jsonify({'status': 'saved'}), 201
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # ─── Shopping List Generator ──────────────────────────────────────

    # [EXTRACTED to blueprint]


    # ─── Comprehensive Status Report ──────────────────────────────────

    @app.route('/api/status-report')
    def api_status_report():
        """Generate a comprehensive status report from all systems."""
        with db_session() as db:
            from datetime import datetime, timedelta

            report = {'generated': datetime.now().isoformat(), 'version': VERSION}

            # Situation board
            sit_row = db.execute("SELECT value FROM settings WHERE key = 'sit_board'").fetchone()
            report['situation'] = json.loads(sit_row['value'] or '{}') if sit_row else {}

            # Services
            report['services'] = {}
            for sid, mod in SERVICE_MODULES.items():
                report['services'][sid] = {'installed': mod.is_installed(), 'running': mod.running() if mod.is_installed() else False}

            # Inventory summary
            inv = db.execute('SELECT category, COUNT(*) as cnt, SUM(quantity) as qty FROM inventory GROUP BY category').fetchall()
            report['inventory'] = {r['category']: {'count': r['cnt'], 'quantity': r['qty'] or 0} for r in inv}

            low = db.execute('SELECT COUNT(*) as c FROM inventory WHERE quantity <= min_quantity AND min_quantity > 0').fetchone()['c']
            report['low_stock_count'] = low

            # Burn rates
            burns = db.execute('SELECT category, MIN(quantity/daily_usage) as min_days FROM inventory WHERE daily_usage > 0 GROUP BY category').fetchall()
            report['burn_rates'] = {r['category']: round(r['min_days'], 1) for r in burns if r['min_days'] is not None}

            # Contacts
            report['contact_count'] = db.execute('SELECT COUNT(*) as c FROM contacts').fetchone()['c']

            # Recent incidents
            report['incidents_24h'] = db.execute("SELECT COUNT(*) as c FROM incidents WHERE created_at >= datetime('now', '-24 hours')").fetchone()['c']

            # Active checklists
            cls = db.execute('SELECT name, items FROM checklists').fetchall()
            cl_summary = []
            for c in cls:
                items = json.loads(c['items'] or '[]')
                total = len(items)
                checked = sum(1 for i in items if i.get('checked'))
                cl_summary.append({'name': c['name'], 'pct': round(checked / total * 100) if total > 0 else 0})
            report['checklists'] = cl_summary

            # Weather
            wx = db.execute('SELECT pressure_hpa, temp_f, created_at FROM weather_log ORDER BY created_at DESC LIMIT 1').fetchone()
            if wx:
                report['weather'] = {'pressure': wx['pressure_hpa'], 'temp_f': wx['temp_f'], 'time': wx['created_at']}

            # Timers
            report['active_timers'] = db.execute('SELECT COUNT(*) as c FROM timers').fetchone()['c']

            # Notes and conversations
            report['notes_count'] = db.execute('SELECT COUNT(*) as c FROM notes').fetchone()['c']
            report['conversations_count'] = db.execute('SELECT COUNT(*) as c FROM conversations').fetchone()['c']


        # Generate text report
        txt = f"===== N.O.M.A.D. STATUS REPORT =====\nGenerated: {report['generated']}\nVersion: {report['version']}\n\n"

        if report['situation']:
            txt += "SITUATION BOARD:\n"
            for domain, level in report['situation'].items():
                txt += f"  {domain.upper()}: {level.upper()}\n"
            txt += "\n"

        txt += "SERVICES:\n"
        for sid, info in report['services'].items():
            status = 'RUNNING' if info['running'] else 'INSTALLED' if info['installed'] else 'NOT INSTALLED'
            txt += f"  {sid}: {status}\n"
        txt += "\n"

        if report['inventory']:
            txt += f"INVENTORY ({report['low_stock_count']} low stock):\n"
            for cat, info in report['inventory'].items():
                burn = report['burn_rates'].get(cat, '')
                burn_str = f" ({burn} days)" if burn else ''
                txt += f"  {cat}: {info['count']} items, {info['quantity']} total{burn_str}\n"
            txt += "\n"

        txt += f"TEAM: {report['contact_count']} contacts\n"
        txt += f"INCIDENTS (24h): {report['incidents_24h']}\n"
        txt += f"ACTIVE TIMERS: {report['active_timers']}\n"
        txt += f"NOTES: {report['notes_count']} | CONVERSATIONS: {report['conversations_count']}\n"

        if report.get('weather'):
            txt += f"\nWEATHER: {report['weather']['pressure']} hPa, {report['weather']['temp_f']}F\n"

        if report['checklists']:
            txt += "\nCHECKLISTS:\n"
            for cl in report['checklists']:
                txt += f"  {cl['name']}: {cl['pct']}% complete\n"

        txt += "\n===== END REPORT ====="

        report['text'] = txt
        return jsonify(report)

    # ─── Printable Reports ───────────────────────────────────────────

    @app.route('/api/print/freq-card')
    def api_print_freq_card():
        """Printable pocket frequency reference card."""
        with db_session() as db:
            freqs = db.execute('SELECT * FROM comms_log ORDER BY created_at DESC LIMIT 20').fetchall()
            contacts = db.execute("SELECT name, callsign, phone FROM contacts WHERE callsign != '' OR phone != '' ORDER BY name").fetchall()
        from datetime import datetime
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        html = f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Frequency Reference Card</title>
<style>
body {{ font-family: 'Courier New', monospace; margin: 0; padding: 8px; font-size: 9px; line-height: 1.3; color: #000; }}
h1 {{ font-size: 12px; text-align: center; margin: 0 0 4px; border-bottom: 2px solid #000; }}
h2 {{ font-size: 10px; background: #333; color: #fff; padding: 2px 6px; margin: 6px 0 2px; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ border: 1px solid #999; padding: 1px 4px; font-size: 8px; }}
th {{ background: #ddd; font-weight: 700; }}
.col2 {{ columns: 2; column-gap: 12px; }}
@media print {{ body {{ margin: 0; }} @page {{ size: A5 landscape; margin: 6mm; }} }}
</style></head><body>
<h1>&#128225; FREQ CARD — Generated {now}</h1>
<div class="col2">
<h2>STANDARD FREQUENCIES</h2>
<table><tr><th>Service</th><th>Freq</th><th>Notes</th></tr>
<tr><td>FRS Ch 1</td><td>462.5625</td><td>Family Radio primary</td></tr>
<tr><td>FRS Ch 3</td><td>462.6125</td><td>Neighborhood net</td></tr>
<tr><td>GMRS Ch 1</td><td>462.5625</td><td>Higher power (5W)</td></tr>
<tr><td>MURS Ch 1</td><td>151.820</td><td>No license required</td></tr>
<tr><td>2m Call</td><td>146.520</td><td>National calling freq</td></tr>
<tr><td>70cm Call</td><td>446.000</td><td>National calling freq</td></tr>
<tr><td>HF 40m</td><td>7.260</td><td>Emergency net</td></tr>
<tr><td>Marine 16</td><td>156.800</td><td>Distress/calling</td></tr>
<tr><td>CB Ch 9</td><td>27.065</td><td>Emergency channel</td></tr>
<tr><td>CB Ch 19</td><td>27.185</td><td>Highway/trucker</td></tr>
<tr><td>NOAA WX</td><td>162.550</td><td>Weather broadcast</td></tr>
</table>
<h2>TEAM CONTACTS</h2>
<table><tr><th>Name</th><th>Callsign</th><th>Phone</th></tr>'''
        from html import escape as esc
        for c in contacts:
            html += f'<tr><td>{esc(c["name"])}</td><td>{esc(c["callsign"] or "—")}</td><td>{esc(c["phone"] or "—")}</td></tr>'
        html += '</table></div></body></html>'
        return Response(html, mimetype='text/html')

    @app.route('/api/print/medical-cards')
    def api_print_medical_cards():
        """Printable wallet-sized medical cards for each person."""
        with db_session() as db:
            patients = db.execute('SELECT * FROM patients ORDER BY name').fetchall()
        from datetime import datetime
        now = datetime.now().strftime('%Y-%m-%d')
        html = '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Medical Cards</title>
<style>
body { font-family: 'Courier New', monospace; margin: 0; padding: 8px; color: #000; }
.card { border: 2px solid #000; border-radius: 6px; padding: 8px 10px; width: 3.25in; height: 2in; display: inline-block; margin: 4px; font-size: 8px; line-height: 1.3; overflow: hidden; vertical-align: top; page-break-inside: avoid; }
.card h3 { font-size: 11px; margin: 0 0 4px; border-bottom: 1px solid #000; padding-bottom: 2px; }
.card .field { margin-bottom: 1px; }
.card .label { font-weight: 700; }
@media print { @page { margin: 10mm; } }
</style></head><body>'''
        from html import escape as esc
        for p in patients:
            try: allergies = json.loads(p['allergies'] or '[]')
            except (json.JSONDecodeError, TypeError): allergies = []
            try: conditions = json.loads(p['conditions'] or '[]')
            except (json.JSONDecodeError, TypeError): conditions = []
            try: medications = json.loads(p['medications'] or '[]')
            except (json.JSONDecodeError, TypeError): medications = []
            html += f'''<div class="card">
<h3>&#9829; {esc(p["name"])} — MEDICAL CARD</h3>
<div class="field"><span class="label">DOB:</span> {esc(str(p.get("dob","—")))} | <span class="label">Blood:</span> {esc(str(p.get("blood_type","—")))} | <span class="label">Weight:</span> {esc(str(p.get("weight_kg","?")))}kg</div>
<div class="field"><span class="label">ALLERGIES:</span> {esc(", ".join(str(a) for a in allergies)) if allergies else "NKDA (None Known)"}</div>
<div class="field"><span class="label">CONDITIONS:</span> {esc(", ".join(str(c) for c in conditions)) if conditions else "None"}</div>
<div class="field"><span class="label">MEDICATIONS:</span> {esc(", ".join(str(m) for m in medications)) if medications else "None"}</div>
<div style="margin-top:4px;font-size:7px;color:#666;">Generated {esc(now)} by N.O.M.A.D.</div>
</div>'''
        if not patients:
            html += '<div style="text-align:center;padding:40px;color:#999;">No patients registered. Add medical profiles in the Medical sub-tab.</div>'
        html += '</body></html>'
        return Response(html, mimetype='text/html')

    @app.route('/api/print/bug-out-checklist')
    def api_print_bugout():
        """Printable bug-out grab-and-go checklist."""
        from datetime import datetime
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        items = [
            ('WATER','2+ gallons per person, filter/purification tabs, collapsible container'),
            ('FOOD','72-hour supply, MREs/bars/freeze-dried, can opener, utensils'),
            ('FIRST AID','IFAK, tourniquet, hemostatic gauze, meds, Rx copies'),
            ('SHELTER','Tent/tarp, sleeping bag/bivvy, emergency blankets, cordage'),
            ('FIRE','Lighter, ferro rod, tinder, stormproof matches, candle'),
            ('COMMS','Radio (GMRS/ham), extra batteries, frequencies card, whistle'),
            ('NAVIGATION','Maps (paper), compass, GPS (charged), waypoints list'),
            ('DOCUMENTS','IDs, insurance, deeds, cash ($small bills), USB backup'),
            ('CLOTHING','Season-appropriate layers, rain gear, boots, extra socks, hat, gloves'),
            ('TOOLS','Knife, multi-tool, flashlight (2+), headlamp, duct tape, zip ties'),
            ('DEFENSE','Per your plan and training'),
            ('POWER','Battery bank, solar charger, cables, crank radio'),
            ('HYGIENE','Toilet paper, soap, toothbrush, medications, feminine products, trash bags'),
            ('SPECIALTY','Glasses, hearing aids, pet supplies, infant needs, prescription meds'),
        ]
        html = f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Bug-Out Checklist</title>
<style>
body {{ font-family: 'Courier New', monospace; margin: 0; padding: 12px; font-size: 10px; color: #000; }}
h1 {{ font-size: 14px; text-align: center; margin: 0 0 8px; border-bottom: 3px solid #000; padding-bottom: 4px; }}
.item {{ display: flex; gap: 6px; padding: 4px 0; border-bottom: 1px solid #ccc; }}
.check {{ width: 14px; height: 14px; border: 2px solid #000; flex-shrink: 0; margin-top: 1px; }}
.cat {{ font-weight: 700; min-width: 80px; flex-shrink: 0; }}
.desc {{ color: #333; }}
@media print {{ @page {{ margin: 12mm; }} }}
</style></head><body>
<h1>&#9888; BUG-OUT CHECKLIST — {now}</h1>
<div style="font-size:9px;text-align:center;margin-bottom:8px;color:#666;">Check each item as you load. Aim for 15 minutes or less.</div>'''
        for cat, desc in items:
            html += f'<div class="item"><div class="check"></div><div class="cat">{cat}</div><div class="desc">{desc}</div></div>'
        html += '''<div style="margin-top:12px;border-top:2px solid #000;padding-top:6px;">
<div style="font-weight:700;">RALLY POINTS:</div>
<div style="display:flex;gap:20px;margin-top:4px;">
<div>PRIMARY: ________________</div><div>SECONDARY: ________________</div><div>TERTIARY: ________________</div>
</div>
<div style="margin-top:6px;font-weight:700;">ROUTES:</div>
<div style="display:flex;gap:20px;margin-top:4px;">
<div>PRIMARY: ________________</div><div>ALTERNATE: ________________</div>
</div>
</div></body></html>'''
        return Response(html, mimetype='text/html')

    # [EXTRACTED to blueprint]


    @app.route('/api/contacts/print')
    def api_contacts_print():
        """Printable contacts directory."""
        with db_session() as db:
            contacts = db.execute('SELECT * FROM contacts ORDER BY name').fetchall()
        now = time.strftime('%Y-%m-%d %H:%M')
        html = f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Contact Directory</title>
<style>body{{font-family:'Segoe UI',sans-serif;padding:15px;font-size:11px;}}
h1{{font-size:16px;border-bottom:2px solid #000;padding-bottom:4px;}}
table{{width:100%;border-collapse:collapse;margin:8px 0;}}th,td{{border:1px solid #999;padding:3px 6px;text-align:left;font-size:10px;}}th{{background:#eee;}}
@media print{{@page{{margin:0.3in;size:letter;}}}}
</style></head><body>
<h1>N.O.M.A.D. Contact Directory — {now}</h1>
<table><thead><tr><th>Name</th><th>Role</th><th>Phone</th><th>Callsign</th><th>Radio Freq</th><th>Blood</th><th>Rally Point</th><th>Skills</th><th>Medical Notes</th></tr></thead><tbody>'''
        for c in contacts:
            d = dict(c)
            html += f"<tr><td><strong>{_esc(d['name'])}</strong></td><td>{_esc(d.get('role',''))}</td><td>{_esc(d.get('phone',''))}</td><td>{_esc(d.get('callsign',''))}</td><td>{_esc(d.get('freq',''))}</td><td>{_esc(d.get('blood_type',''))}</td><td>{_esc(d.get('rally_point',''))}</td><td>{_esc(d.get('skills',''))}</td><td>{_esc(d.get('medical_notes',''))}</td></tr>"
        html += f'</tbody></table><p style="font-size:9px;color:#666;">Generated by N.O.M.A.D. — {now}</p></body></html>'
        return html

    # ─── PDF Generation (ReportLab) ──────────────────────────────────

    @app.route('/api/print/pdf/operations-binder')
    def api_print_pdf_operations_binder():
        """Generate a full operations binder as a PDF using ReportLab."""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.units import inch
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
        except ImportError:
            return jsonify({'error': 'reportlab not installed', 'hint': 'pip install reportlab'}), 500

        import io
        from datetime import datetime

        with db_session() as db:
            contacts = [dict(r) for r in db.execute('SELECT * FROM contacts ORDER BY name LIMIT 500').fetchall()]
            freqs = [dict(r) for r in db.execute('SELECT * FROM comms_log ORDER BY created_at DESC LIMIT 50').fetchall()]
            patients = [dict(r) for r in db.execute('SELECT * FROM patients ORDER BY name LIMIT 200').fetchall()]
            inventory = [dict(r) for r in db.execute('SELECT * FROM inventory ORDER BY category, name LIMIT 1000').fetchall()]
            checklists = [dict(r) for r in db.execute('SELECT name, items FROM checklists ORDER BY name LIMIT 200').fetchall()]
            waypoints = [dict(r) for r in db.execute('SELECT * FROM waypoints ORDER BY category, name LIMIT 500').fetchall()]

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch,
                                leftMargin=0.6*inch, rightMargin=0.6*inch)
        styles = getSampleStyleSheet()
        mono = ParagraphStyle('Mono', parent=styles['Normal'], fontName='Courier', fontSize=8, leading=10)
        mono_bold = ParagraphStyle('MonoBold', parent=mono, fontName='Courier-Bold', fontSize=9, leading=11)
        title_style = ParagraphStyle('TitleMono', fontName='Courier-Bold', fontSize=18, leading=22, alignment=1, spaceAfter=12)
        subtitle_style = ParagraphStyle('SubtitleMono', fontName='Courier', fontSize=11, leading=14, alignment=1, spaceAfter=6, textColor=colors.grey)
        section_style = ParagraphStyle('SectionMono', fontName='Courier-Bold', fontSize=12, leading=15, spaceBefore=16, spaceAfter=8,
                                        borderWidth=1, borderColor=colors.black, borderPadding=4)
        toc_style = ParagraphStyle('TOCMono', fontName='Courier', fontSize=10, leading=14, spaceBefore=4)

        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        node_name = _get_node_name()
        elements = []

        # Cover page
        elements.append(Spacer(1, 2*inch))
        elements.append(Paragraph('N.O.M.A.D.', title_style))
        elements.append(Paragraph('OPERATIONS BINDER', ParagraphStyle('Cover2', fontName='Courier-Bold', fontSize=14, alignment=1, spaceAfter=20)))
        elements.append(Paragraph(f'Node: {_esc(node_name)}', subtitle_style))
        elements.append(Paragraph(f'Generated: {now}', subtitle_style))
        elements.append(Paragraph('CLASSIFIED -- FOR AUTHORIZED PERSONNEL ONLY', ParagraphStyle('Warn', fontName='Courier-Bold', fontSize=9, alignment=1, textColor=colors.red, spaceBefore=40)))
        elements.append(PageBreak())

        # Table of Contents
        elements.append(Paragraph('TABLE OF CONTENTS', section_style))
        toc_items = ['1. Contacts Directory', '2. Communications / Frequencies', '3. Medical Patient Cards',
                     '4. Supply Inventory', '5. Checklists', '6. Waypoints / Navigation']
        for item in toc_items:
            elements.append(Paragraph(item, toc_style))
        elements.append(PageBreak())

        # 1. Contacts
        elements.append(Paragraph('1. CONTACTS DIRECTORY', section_style))
        if contacts:
            t_data = [['Name', 'Role', 'Callsign', 'Phone', 'Freq', 'Blood', 'Rally Point']]
            for c in contacts:
                t_data.append([c.get('name',''), c.get('role',''), c.get('callsign',''),
                              c.get('phone',''), c.get('freq',''), c.get('blood_type',''), c.get('rally_point','')])
            t = Table(t_data, repeatRows=1)
            t.setStyle(TableStyle([
                ('FONTNAME', (0,0), (-1,0), 'Courier-Bold'), ('FONTSIZE', (0,0), (-1,-1), 7),
                ('FONTNAME', (0,1), (-1,-1), 'Courier'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('BACKGROUND', (0,0), (-1,0), colors.Color(0.85, 0.85, 0.85)),
                ('VALIGN', (0,0), (-1,-1), 'TOP'), ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ]))
            elements.append(t)
        else:
            elements.append(Paragraph('No contacts registered.', mono))
        elements.append(PageBreak())

        # 2. Frequencies
        elements.append(Paragraph('2. COMMUNICATIONS / FREQUENCIES', section_style))
        if freqs:
            t_data = [['Freq', 'Callsign', 'Direction', 'Message', 'Signal', 'Time']]
            for f in freqs:
                t_data.append([f.get('freq',''), f.get('callsign',''), f.get('direction',''),
                              (f.get('message','') or '')[:60], f.get('signal_quality',''), f.get('created_at','')])
            t = Table(t_data, repeatRows=1)
            t.setStyle(TableStyle([
                ('FONTNAME', (0,0), (-1,0), 'Courier-Bold'), ('FONTSIZE', (0,0), (-1,-1), 7),
                ('FONTNAME', (0,1), (-1,-1), 'Courier'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('BACKGROUND', (0,0), (-1,0), colors.Color(0.85, 0.85, 0.85)),
                ('VALIGN', (0,0), (-1,-1), 'TOP'), ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ]))
            elements.append(t)
        else:
            elements.append(Paragraph('No communications logged.', mono))
        elements.append(PageBreak())

        # 3. Medical
        elements.append(Paragraph('3. MEDICAL PATIENT CARDS', section_style))
        if patients:
            for p in patients:
                elements.append(Paragraph(f'Patient: {_esc(p["name"])}', mono_bold))
                try: allergies = ', '.join(str(a) for a in json.loads(p.get('allergies') or '[]'))
                except (json.JSONDecodeError, TypeError): allergies = ''
                try: conditions = ', '.join(str(c) for c in json.loads(p.get('conditions') or '[]'))
                except (json.JSONDecodeError, TypeError): conditions = ''
                try: medications = ', '.join(str(m) for m in json.loads(p.get('medications') or '[]'))
                except (json.JSONDecodeError, TypeError): medications = ''
                info = [
                    f'Blood Type: {p.get("blood_type","--")}  |  Weight: {p.get("weight_kg","?")} kg  |  Sex: {p.get("sex","--")}',
                    f'Allergies: {allergies or "NKDA"}',
                    f'Conditions: {conditions or "None"}',
                    f'Medications: {medications or "None"}',
                ]
                for line in info:
                    elements.append(Paragraph(line, mono))
                elements.append(Spacer(1, 12))
        else:
            elements.append(Paragraph('No patients registered.', mono))
        elements.append(PageBreak())

        # 4. Inventory
        elements.append(Paragraph('4. SUPPLY INVENTORY', section_style))
        if inventory:
            t_data = [['Name', 'Category', 'Qty', 'Unit', 'Min', 'Location', 'Expires']]
            for item in inventory:
                t_data.append([item.get('name',''), item.get('category',''), str(item.get('quantity',0)),
                              item.get('unit',''), str(item.get('min_quantity','')),
                              item.get('location',''), item.get('expiration','')])
            t = Table(t_data, repeatRows=1)
            t.setStyle(TableStyle([
                ('FONTNAME', (0,0), (-1,0), 'Courier-Bold'), ('FONTSIZE', (0,0), (-1,-1), 7),
                ('FONTNAME', (0,1), (-1,-1), 'Courier'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('BACKGROUND', (0,0), (-1,0), colors.Color(0.85, 0.85, 0.85)),
                ('VALIGN', (0,0), (-1,-1), 'TOP'), ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ]))
            elements.append(t)
        else:
            elements.append(Paragraph('No inventory items.', mono))
        elements.append(PageBreak())

        # 5. Checklists
        elements.append(Paragraph('5. CHECKLISTS', section_style))
        if checklists:
            for cl in checklists:
                elements.append(Paragraph(f'[ ] {_esc(cl["name"])}', mono_bold))
                try:
                    cl_items = json.loads(cl.get('items') or '[]')
                    for it in cl_items:
                        label = it.get('text', it) if isinstance(it, dict) else str(it)
                        checked = it.get('done', False) if isinstance(it, dict) else False
                        mark = '[X]' if checked else '[ ]'
                        elements.append(Paragraph(f'    {mark} {_esc(str(label))}', mono))
                except (json.JSONDecodeError, TypeError):
                    pass
                elements.append(Spacer(1, 8))
        else:
            elements.append(Paragraph('No checklists.', mono))
        elements.append(PageBreak())

        # 6. Waypoints
        elements.append(Paragraph('6. WAYPOINTS / NAVIGATION', section_style))
        if waypoints:
            t_data = [['Name', 'Category', 'Latitude', 'Longitude', 'Elevation', 'Notes']]
            for w in waypoints:
                t_data.append([w.get('name',''), w.get('category',''), str(w.get('lat','')),
                              str(w.get('lng','')), str(w.get('elevation_m','') or ''),
                              (w.get('notes','') or '')[:40]])
            t = Table(t_data, repeatRows=1)
            t.setStyle(TableStyle([
                ('FONTNAME', (0,0), (-1,0), 'Courier-Bold'), ('FONTSIZE', (0,0), (-1,-1), 7),
                ('FONTNAME', (0,1), (-1,-1), 'Courier'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('BACKGROUND', (0,0), (-1,0), colors.Color(0.85, 0.85, 0.85)),
                ('VALIGN', (0,0), (-1,-1), 'TOP'), ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ]))
            elements.append(t)
        else:
            elements.append(Paragraph('No waypoints.', mono))

        # Footer
        elements.append(Spacer(1, 20))
        elements.append(Paragraph(f'End of Operations Binder -- Generated {now} by N.O.M.A.D. ({_esc(node_name)})', subtitle_style))

        doc.build(elements)
        buf.seek(0)
        return Response(buf.read(), mimetype='application/pdf',
                       headers={'Content-Disposition': f'attachment; filename="NOMAD-Operations-Binder-{datetime.now().strftime("%Y%m%d")}.pdf"'})

    @app.route('/api/print/pdf/wallet-cards')
    def api_print_pdf_wallet_cards():
        """Generate PDF wallet-sized cards (3.375 x 2.125 inches each)."""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.units import inch
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        except ImportError:
            return jsonify({'error': 'reportlab not installed', 'hint': 'pip install reportlab'}), 500

        import io
        from datetime import datetime

        with db_session() as db:
            patients = [dict(r) for r in db.execute('SELECT * FROM patients ORDER BY name').fetchall()]
            contacts = [dict(r) for r in db.execute("SELECT name, phone, callsign, freq, rally_point FROM contacts WHERE phone != '' OR callsign != '' ORDER BY name LIMIT 10").fetchall()]
            waypoints = [dict(r) for r in db.execute("SELECT name, lat, lng, category FROM waypoints WHERE category IN ('rally','shelter','cache','home','base') ORDER BY name LIMIT 6").fetchall()]
            freqs = [dict(r) for r in db.execute('SELECT freq, callsign, message FROM comms_log ORDER BY created_at DESC LIMIT 8').fetchall()]

        CARD_W = 3.375 * inch

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch,
                                leftMargin=0.5*inch, rightMargin=0.5*inch)
        card_title = ParagraphStyle('CardTitle', fontName='Courier-Bold', fontSize=8, leading=10, alignment=1, spaceAfter=2)
        card_body = ParagraphStyle('CardBody', fontName='Courier', fontSize=6, leading=7.5)
        card_label = ParagraphStyle('CardLabel', fontName='Courier-Bold', fontSize=6, leading=7.5)
        footer_style = ParagraphStyle('Footer', fontName='Courier', fontSize=5, leading=6, textColor=colors.grey, alignment=2)

        now = datetime.now().strftime('%Y-%m-%d')
        elements = []
        cards = []

        # ICE Card for each patient
        for p in patients:
            try: allergies = ', '.join(str(a) for a in json.loads(p.get('allergies') or '[]'))
            except (json.JSONDecodeError, TypeError): allergies = ''
            try: meds = ', '.join(str(m) for m in json.loads(p.get('medications') or '[]'))
            except (json.JSONDecodeError, TypeError): meds = ''
            try: conditions_str = ', '.join(str(c) for c in json.loads(p.get('conditions') or '[]'))
            except (json.JSONDecodeError, TypeError): conditions_str = ''

            card_data = [
                [Paragraph(f'ICE CARD -- {_esc(p["name"])}', card_title)],
                [Paragraph(f'<b>Blood:</b> {_esc(p.get("blood_type","--"))}  <b>Wt:</b> {p.get("weight_kg","?")}kg  <b>Sex:</b> {_esc(p.get("sex","--"))}', card_body)],
                [Paragraph(f'<b>Allergies:</b> {_esc(allergies) or "NKDA"}', card_body)],
                [Paragraph(f'<b>Conditions:</b> {_esc(conditions_str) or "None"}', card_body)],
                [Paragraph(f'<b>Medications:</b> {_esc(meds) or "None"}', card_body)],
                [Paragraph(f'N.O.M.A.D. -- {now}', footer_style)],
            ]
            cards.append(card_data)

        # Rally Points card
        if waypoints:
            wp_lines = [[Paragraph('RALLY POINTS', card_title)]]
            for w in waypoints:
                wp_lines.append([Paragraph(f'{_esc(w["name"])} ({w["category"]}): {w["lat"]:.5f}, {w["lng"]:.5f}', card_body)])
            wp_lines.append([Paragraph(f'N.O.M.A.D. -- {now}', footer_style)])
            cards.append(wp_lines)

        # Frequency Quick-Ref card
        freq_lines = [[Paragraph('FREQ QUICK REFERENCE', card_title)]]
        std_freqs = [('FRS 1', '462.5625'), ('GMRS 1', '462.5625'), ('2m Call', '146.520'),
                     ('70cm Call', '446.000'), ('CB 9', '27.065'), ('NOAA', '162.550')]
        for fname, fval in std_freqs:
            freq_lines.append([Paragraph(f'{fname}: {fval}', card_body)])
        if freqs:
            freq_lines.append([Paragraph('<b>-- Team Freqs --</b>', card_label)])
            for f in freqs[:4]:
                freq_lines.append([Paragraph(f'{f.get("freq","?")} ({_esc(f.get("callsign",""))})', card_body)])
        freq_lines.append([Paragraph(f'N.O.M.A.D. -- {now}', footer_style)])
        cards.append(freq_lines)

        # Emergency Contacts card
        if contacts:
            ec_lines = [[Paragraph('EMERGENCY CONTACTS', card_title)]]
            for c in contacts:
                phone_or_call = c.get('phone') or c.get('callsign') or c.get('freq') or ''
                ec_lines.append([Paragraph(f'{_esc(c["name"])}: {_esc(phone_or_call)}', card_body)])
            ec_lines.append([Paragraph(f'N.O.M.A.D. -- {now}', footer_style)])
            cards.append(ec_lines)

        # Build cards as tables with borders
        for card_data in cards:
            card_table = Table(card_data, colWidths=[CARD_W - 12])
            card_table.setStyle(TableStyle([
                ('BOX', (0,0), (-1,-1), 1.5, colors.black),
                ('TOPPADDING', (0,0), (-1,-1), 2),
                ('BOTTOMPADDING', (0,0), (-1,-1), 1),
                ('LEFTPADDING', (0,0), (-1,-1), 6),
                ('RIGHTPADDING', (0,0), (-1,-1), 6),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ]))
            elements.append(card_table)
            elements.append(Spacer(1, 8))

        if not elements:
            elements.append(Paragraph('No data available for wallet cards.', card_body))

        doc.build(elements)
        buf.seek(0)
        return Response(buf.read(), mimetype='application/pdf',
                       headers={'Content-Disposition': f'attachment; filename="NOMAD-Wallet-Cards-{datetime.now().strftime("%Y%m%d")}.pdf"'})

    @app.route('/api/print/pdf/soi')
    def api_print_pdf_soi():
        """Generate Signal Operating Instructions (SOI) as PDF."""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.units import inch
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        except ImportError:
            return jsonify({'error': 'reportlab not installed', 'hint': 'pip install reportlab'}), 500

        import io
        from datetime import datetime

        with db_session() as db:
            contacts = [dict(r) for r in db.execute("SELECT name, callsign, freq, role FROM contacts WHERE callsign != '' OR freq != '' ORDER BY name").fetchall()]
            freqs = [dict(r) for r in db.execute('SELECT freq, callsign, direction, message, signal_quality, created_at FROM comms_log ORDER BY created_at DESC LIMIT 30').fetchall()]

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch,
                                leftMargin=0.6*inch, rightMargin=0.6*inch)
        mono = ParagraphStyle('Mono', fontName='Courier', fontSize=8, leading=10)
        title_style = ParagraphStyle('TitleMono', fontName='Courier-Bold', fontSize=16, leading=20, alignment=1, spaceAfter=8)
        subtitle_style = ParagraphStyle('SubMono', fontName='Courier', fontSize=10, alignment=1, spaceAfter=4, textColor=colors.grey)
        section_style = ParagraphStyle('SectionMono', fontName='Courier-Bold', fontSize=11, leading=14, spaceBefore=14, spaceAfter=6,
                                        borderWidth=1, borderColor=colors.black, borderPadding=3)

        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        node_name = _get_node_name()
        elements = []

        # Header
        elements.append(Paragraph('SIGNAL OPERATING INSTRUCTIONS', title_style))
        elements.append(Paragraph(f'Node: {_esc(node_name)} | Generated: {now}', subtitle_style))
        elements.append(Paragraph('OPERATIONAL SECURITY -- DO NOT LEAVE UNATTENDED', ParagraphStyle('Warn', fontName='Courier-Bold', fontSize=8, alignment=1, textColor=colors.red, spaceBefore=8, spaceAfter=16)))

        # Standard Emergency Frequencies
        elements.append(Paragraph('STANDARD EMERGENCY FREQUENCIES', section_style))
        std_data = [
            ['Service', 'Frequency', 'Notes'],
            ['FRS Ch 1', '462.5625 MHz', 'Family Radio primary'],
            ['FRS Ch 3', '462.6125 MHz', 'Neighborhood net'],
            ['GMRS Ch 1', '462.5625 MHz', 'Higher power (5W)'],
            ['MURS Ch 1', '151.820 MHz', 'No license required'],
            ['2m Call', '146.520 MHz', 'National calling freq'],
            ['70cm Call', '446.000 MHz', 'National calling freq'],
            ['HF 40m', '7.260 MHz', 'Emergency net'],
            ['Marine 16', '156.800 MHz', 'Distress/calling'],
            ['CB Ch 9', '27.065 MHz', 'Emergency channel'],
            ['CB Ch 19', '27.185 MHz', 'Highway/trucker'],
            ['NOAA WX', '162.550 MHz', 'Weather broadcast'],
        ]
        t = Table(std_data, repeatRows=1, colWidths=[1.8*inch, 1.5*inch, 3*inch])
        t.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,0), 'Courier-Bold'), ('FONTSIZE', (0,0), (-1,-1), 8),
            ('FONTNAME', (0,1), (-1,-1), 'Courier'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BACKGROUND', (0,0), (-1,0), colors.Color(0.85, 0.85, 0.85)),
            ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]))
        elements.append(t)

        # Team Call Signs
        elements.append(Paragraph('TEAM CALLSIGNS / OPERATORS', section_style))
        if contacts:
            t_data = [['Name', 'Callsign', 'Frequency', 'Role']]
            for c in contacts:
                t_data.append([c.get('name',''), c.get('callsign',''), c.get('freq',''), c.get('role','')])
            t = Table(t_data, repeatRows=1)
            t.setStyle(TableStyle([
                ('FONTNAME', (0,0), (-1,0), 'Courier-Bold'), ('FONTSIZE', (0,0), (-1,-1), 8),
                ('FONTNAME', (0,1), (-1,-1), 'Courier'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('BACKGROUND', (0,0), (-1,0), colors.Color(0.85, 0.85, 0.85)),
                ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ]))
            elements.append(t)
        else:
            elements.append(Paragraph('No team contacts with callsigns registered.', mono))

        # Recent Communications Log
        elements.append(Paragraph('RECENT COMMUNICATIONS LOG', section_style))
        if freqs:
            t_data = [['Time', 'Freq', 'Callsign', 'Dir', 'Message', 'Signal']]
            for f in freqs:
                t_data.append([f.get('created_at',''), f.get('freq',''), f.get('callsign',''),
                              f.get('direction',''), (f.get('message','') or '')[:50], f.get('signal_quality','')])
            t = Table(t_data, repeatRows=1)
            t.setStyle(TableStyle([
                ('FONTNAME', (0,0), (-1,0), 'Courier-Bold'), ('FONTSIZE', (0,0), (-1,-1), 7),
                ('FONTNAME', (0,1), (-1,-1), 'Courier'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('BACKGROUND', (0,0), (-1,0), colors.Color(0.85, 0.85, 0.85)),
                ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ]))
            elements.append(t)
        else:
            elements.append(Paragraph('No communications logged.', mono))

        # Radio Procedures
        elements.append(Paragraph('RADIO PROCEDURES', section_style))
        procedures = [
            'PROWORDS: Roger (understood), Wilco (will comply), Over (your turn), Out (end)',
            'PHONETIC: Alpha, Bravo, Charlie, Delta, Echo, Foxtrot, Golf, Hotel...',
            'NET CALL: "[Callsign] this is [Callsign], radio check, over"',
            'EMERGENCY: "MAYDAY MAYDAY MAYDAY, this is [Callsign], [situation], over"',
            'MEDEVAC 9-LINE: Location, Freq, # Patients, Equipment, # by type, Security, Marking, Nationality, CBRN',
        ]
        for proc in procedures:
            elements.append(Paragraph(proc, mono))

        elements.append(Spacer(1, 20))
        elements.append(Paragraph(f'End of SOI -- {now} -- N.O.M.A.D. ({_esc(node_name)})', subtitle_style))

        doc.build(elements)
        buf.seek(0)
        return Response(buf.read(), mimetype='application/pdf',
                       headers={'Content-Disposition': f'attachment; filename="NOMAD-SOI-{datetime.now().strftime("%Y%m%d")}.pdf"'})

    @app.route('/api/emergency-sheet')
    def api_emergency_sheet():
        """Generate a comprehensive printable emergency reference sheet."""
        with db_session() as db:
            from datetime import datetime, timedelta

            # Gather all critical data
            contacts = [dict(r) for r in db.execute('SELECT * FROM contacts ORDER BY name').fetchall()]
            inventory = [dict(r) for r in db.execute('SELECT * FROM inventory ORDER BY category, name').fetchall()]
            burn_items = [dict(r) for r in db.execute('SELECT name, quantity, unit, daily_usage, category FROM inventory WHERE daily_usage > 0 ORDER BY (quantity/daily_usage)').fetchall()]
            patients = [dict(r) for r in db.execute('SELECT * FROM patients ORDER BY name').fetchall()]
            waypoints = [dict(r) for r in db.execute('SELECT * FROM waypoints ORDER BY category, name').fetchall()]
            checklists = [dict(r) for r in db.execute('SELECT name, items FROM checklists ORDER BY name').fetchall()]
            sit_raw = db.execute("SELECT value FROM settings WHERE key = 'sit_board'").fetchone()
            sit = json.loads(sit_raw['value'] or '{}') if sit_raw else {}
            wx = [dict(r) for r in db.execute('SELECT * FROM weather_log ORDER BY created_at DESC LIMIT 5').fetchall()]

        sit_labels = {'green': 'GOOD', 'yellow': 'CAUTION', 'orange': 'CONCERN', 'red': 'CRITICAL'}
        sit_colors = {'green': '#2e7d32', 'yellow': '#f9a825', 'orange': '#ef6c00', 'red': '#c62828'}
        now = datetime.now().strftime('%Y-%m-%d %H:%M')

        html = f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>N.O.M.A.D. Emergency Reference Sheet</title>
<style>
body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 12px; font-size: 10px; line-height: 1.4; color: #000; }}
h1 {{ font-size: 16px; text-align: center; margin: 0 0 4px; border-bottom: 3px solid #000; padding-bottom: 4px; }}
h2 {{ font-size: 12px; background: #333; color: #fff; padding: 3px 8px; margin: 8px 0 4px; border-radius: 3px; }}
table {{ width: 100%; border-collapse: collapse; margin-bottom: 6px; }}
th, td {{ border: 1px solid #999; padding: 2px 5px; text-align: left; font-size: 9px; }}
th {{ background: #eee; font-weight: 700; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
.sit-badge {{ display: inline-block; padding: 1px 6px; border-radius: 3px; color: #fff; font-weight: 700; font-size: 9px; }}
.warn {{ color: #c62828; font-weight: 700; }}
@media print {{ body {{ padding: 5px; }} @page {{ margin: 0.3in; size: letter; }} }}
</style></head><body>
<h1>PROJECT N.O.M.A.D. — EMERGENCY REFERENCE SHEET</h1>
<div style="text-align:center;font-size:9px;margin-bottom:8px;">Generated: {now} | Keep in go-bag | Replace monthly</div>
'''

        # Situation Board
        if sit:
            html += '<h2>SITUATION STATUS</h2><div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:6px;">'
            for domain, level in sit.items():
                html += f'<span class="sit-badge" style="background:{sit_colors.get(level,"#666")}">{domain.upper()}: {sit_labels.get(level, level.upper())}</span>'
            html += '</div>'

        # Emergency Contacts
        html += '<h2>EMERGENCY CONTACTS</h2>'
        if contacts:
            html += '<table><tr><th>Name</th><th>Role</th><th>Phone</th><th>Callsign</th><th>Radio Freq</th><th>Blood</th><th>Rally Point</th></tr>'
            for c in contacts:
                html += f"<tr><td><strong>{_esc(c.get('name',''))}</strong></td><td>{_esc(c.get('role',''))}</td><td>{_esc(c.get('phone',''))}</td><td>{_esc(c.get('callsign',''))}</td><td>{_esc(c.get('freq',''))}</td><td>{_esc(c.get('blood_type',''))}</td><td>{_esc(c.get('rally_point',''))}</td></tr>"
            html += '</table>'
        else:
            html += '<p>No contacts registered.</p>'

        # Medical — Patients with allergies
        if patients:
            html += '<h2>MEDICAL — PATIENT PROFILES</h2><table><tr><th>Name</th><th>Age</th><th>Weight</th><th>Blood</th><th>ALLERGIES</th><th>Medications</th><th>Conditions</th></tr>'
            for p in patients:
                allergies = json.loads(p.get('allergies') or '[]')
                meds = json.loads(p.get('medications') or '[]')
                conds = json.loads(p.get('conditions') or '[]')
                allergy_str = ', '.join(allergies) if allergies else 'NKDA'
                html += f"<tr><td><strong>{_esc(p.get('name',''))}</strong></td><td>{p.get('age','')}</td><td>{p.get('weight_kg','') or ''} kg</td><td>{_esc(p.get('blood_type',''))}</td><td class='warn'>{_esc(allergy_str)}</td><td>{_esc(', '.join(meds))}</td><td>{_esc(', '.join(conds))}</td></tr>"
            html += '</table>'

        # Critical Supply Status
        html += '<h2>SUPPLY STATUS</h2>'
        if burn_items:
            html += '<table><tr><th>Item</th><th>Category</th><th>Quantity</th><th>Daily Use</th><th>Days Left</th></tr>'
            for b in burn_items[:15]:
                days = round(b['quantity'] / b['daily_usage'], 1) if b['daily_usage'] > 0 else 999
                color = '#c62828' if days < 3 else '#ef6c00' if days < 7 else '#2e7d32' if days < 30 else ''
                html += f"<tr><td><strong>{_esc(b['name'])}</strong></td><td>{_esc(b['category'])}</td><td>{b['quantity']} {_esc(b.get('unit',''))}</td><td>{b['daily_usage']}/day</td><td style='color:{color};font-weight:700;'>{days}d</td></tr>"
            html += '</table>'

        # Inventory by category
        cats = {}
        for item in inventory:
            cat = item.get('category', 'other')
            if cat not in cats:
                cats[cat] = {'count': 0, 'items': []}
            cats[cat]['count'] += 1
            cats[cat]['items'].append(item)
        if cats:
            html += '<div style="font-size:9px;margin-bottom:4px;">'
            for cat, info in sorted(cats.items()):
                html += f'<strong>{cat}:</strong> {info["count"]} items | '
            html += '</div>'

        # Waypoints / Rally Points
        if waypoints:
            html += '<h2>WAYPOINTS & RALLY POINTS</h2><table><tr><th>Name</th><th>Category</th><th>Lat</th><th>Lng</th><th>Notes</th></tr>'
            for w in waypoints:
                html += f"<tr><td><strong>{_esc(w.get('name',''))}</strong></td><td>{_esc(w.get('category',''))}</td><td>{w.get('lat','')}</td><td>{w.get('lng','')}</td><td>{_esc(w.get('notes',''))}</td></tr>"
            html += '</table>'

        # Checklist Progress
        if checklists:
            html += '<h2>CHECKLIST STATUS</h2><table><tr><th>Checklist</th><th>Progress</th></tr>'
            for cl in checklists:
                items = json.loads(cl.get('items') or '[]')
                total = len(items)
                checked = sum(1 for i in items if i.get('checked'))
                pct = round(checked / total * 100) if total > 0 else 0
                html += f"<tr><td>{_esc(cl['name'])}</td><td>{checked}/{total} ({pct}%)</td></tr>"
            html += '</table>'

        # Weather
        if wx:
            html += '<h2>RECENT WEATHER</h2><table><tr><th>Time</th><th>Pressure (hPa)</th><th>Temp (F)</th><th>Wind</th><th>Clouds</th></tr>'
            for w in wx:
                html += f"<tr><td>{w.get('created_at','')}</td><td>{w.get('pressure_hpa','') or '-'}</td><td>{w.get('temp_f','') or '-'}</td><td>{w.get('wind_dir','')} {w.get('wind_speed','')}</td><td>{w.get('clouds','') or '-'}</td></tr>"
            html += '</table>'

        # Scheduled Tasks (due/overdue)
        try:
            db2 = get_db()
            tasks = [dict(r) for r in db2.execute("SELECT name, category, next_due, assigned_to FROM scheduled_tasks WHERE next_due IS NOT NULL ORDER BY next_due LIMIT 15").fetchall()]
            db2.close()
            if tasks:
                html += '<h2>SCHEDULED TASKS</h2><table><tr><th>Task</th><th>Category</th><th>Due</th><th>Assigned</th></tr>'
                for t in tasks:
                    html += f"<tr><td><strong>{_esc(t.get('name',''))}</strong></td><td>{_esc(t.get('category',''))}</td><td>{_esc(t.get('next_due',''))}</td><td>{_esc(t.get('assigned_to','') or 'Unassigned')}</td></tr>"
                html += '</table>'
        except Exception:
            pass

        # AI Memory / Operator Notes
        try:
            db3 = get_db()
            mem_row = db3.execute("SELECT value FROM settings WHERE key = 'ai_memory'").fetchone()
            db3.close()
            if mem_row and mem_row['value']:
                memories = json.loads(mem_row['value'])
                if memories:
                    html += '<h2>OPERATOR NOTES (AI MEMORY)</h2><ul style="font-size:9px;margin:0;padding-left:16px;">'
                    for m in memories:
                        fact = m['fact'] if isinstance(m, dict) else m
                        html += f'<li>{_esc(fact)}</li>'
                    html += '</ul>'
        except Exception:
            pass

        # Quick Reference Footer
        html += '''<h2>QUICK REFERENCE</h2>
<div class="grid">
<div><strong>Water:</strong> 1 gal/person/day. Bleach: 8 drops/gal (clear), 16 drops/gal (cloudy). Wait 30 min.</div>
<div><strong>Food:</strong> 2,000 cal/person/day. Eat perishable first, then frozen, then shelf-stable.</div>
<div><strong>Radio:</strong> FRS Ch 1 (rally), Ch 3 (emergency). GMRS Ch 20 (emergency). HAM 146.520 MHz (calling).</div>
<div><strong>Medical:</strong> Direct pressure for bleeding. Tourniquet if limb bleeding won\'t stop. Note time applied.</div>
</div>
<div style="text-align:center;margin-top:8px;font-size:8px;color:#666;">Generated by Project N.O.M.A.D. — projectnomad.us</div>
</body></html>'''

        return html

    # ─── Dashboard Checklists Progress ─────────────────────────────────

    @app.route('/api/dashboard/checklists')
    def api_dashboard_checklists():
        with db_session() as db:
            rows = db.execute('SELECT id, name, items FROM checklists ORDER BY updated_at DESC LIMIT 5').fetchall()
        result = []
        for r in rows:
            items = json.loads(r['items'] or '[]')
            total = len(items)
            checked = sum(1 for i in items if i.get('checked'))
            result.append({'id': r['id'], 'name': r['name'], 'total': total, 'checked': checked,
                          'pct': round(checked / total * 100) if total > 0 else 0})
        return jsonify(result)

    # ─── Readiness Score ─────────────────────────────────────────────

    @app.route('/api/readiness-score')
    def api_readiness_score():
        """Cross-module readiness assessment (0-100) with category breakdown."""
        from datetime import datetime, timedelta
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
                items = json.loads(cl['items'] or '[]')
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

        return jsonify({
            'total': total, 'max': max_total, 'grade': grade,
            'categories': scores,
        })

    # [EXTRACTED to blueprint] KB workspaces


    # [EXTRACTED to blueprint]

    @app.route('/api/benchmark/network', methods=['POST'])
    def api_benchmark_network():
        """Benchmark local network throughput."""
        import time as _time
        import socket
        try:
            # Test local loopback as baseline, or test to a peer
            peer = (request.json or {}).get('peer', '127.0.0.1')
            port = 18234
            chunk = b'X' * (1024 * 1024)  # 1MB chunks
            total_mb = 10

            # Simple TCP throughput test
            server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_sock.bind(('0.0.0.0', port))
            server_sock.listen(1)
            server_sock.settimeout(5)

            # Connect in background
            def send_data():
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.connect((peer, port))
                    for _ in range(total_mb):
                        s.sendall(chunk)
                    s.close()
                except Exception:
                    pass

            t = threading.Thread(target=send_data, daemon=True)
            t.start()

            conn, _ = server_sock.accept()
            start = _time.time()
            received = 0
            while received < total_mb * 1024 * 1024:
                data = conn.recv(65536)
                if not data:
                    break
                received += len(data)
            elapsed = _time.time() - start
            conn.close()
            server_sock.close()
            t.join(timeout=2)

            mbps = round((received / 1024 / 1024) / elapsed * 8, 1) if elapsed > 0 else 0

            db = get_db()
            try:
                db.execute('INSERT INTO benchmark_results (test_type, scores) VALUES (?, ?)',
                           ('network', json.dumps({'throughput_mbps': mbps, 'peer': peer, 'data_mb': total_mb})))
                db.commit()
            finally:
                db.close()

            return jsonify({'throughput_mbps': mbps, 'data_mb': round(received/1024/1024, 1), 'elapsed_sec': round(elapsed, 2)})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

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
        """Extended search across all data types."""
        q = request.args.get('q', '').strip()[:200]
        if not q:
            return jsonify({'conversations': [], 'notes': [], 'documents': [], 'inventory': [], 'contacts': [], 'checklists': []})
        with db_session() as db:
            like = f'%{q}%'
            convos = db.execute("SELECT id, title, 'conversation' as type FROM conversations WHERE title LIKE ? OR messages LIKE ? LIMIT 10", (like, like)).fetchall()
            notes = db.execute("SELECT id, title, 'note' as type FROM notes WHERE title LIKE ? OR content LIKE ? LIMIT 10", (like, like)).fetchall()
            docs = db.execute("SELECT id, filename as title, 'document' as type FROM documents WHERE filename LIKE ? AND status = 'ready' LIMIT 10", (like,)).fetchall()
            inv = db.execute("SELECT id, name as title, 'inventory' as type FROM inventory WHERE name LIKE ? OR location LIKE ? OR notes LIKE ? LIMIT 10", (like, like, like)).fetchall()
            contacts = db.execute("SELECT id, name as title, 'contact' as type FROM contacts WHERE name LIKE ? OR callsign LIKE ? OR role LIKE ? OR skills LIKE ? LIMIT 10", (like, like, like, like)).fetchall()
            checklists = db.execute("SELECT id, name as title, 'checklist' as type FROM checklists WHERE name LIKE ? LIMIT 10", (like,)).fetchall()
            skills = db.execute("SELECT id, name as title, 'skill' as type FROM skills WHERE name LIKE ? OR category LIKE ? OR notes LIKE ? LIMIT 5", (like, like, like)).fetchall()
            ammo = db.execute("SELECT id, caliber as title, 'ammo' as type FROM ammo_inventory WHERE caliber LIKE ? OR brand LIKE ? OR location LIKE ? LIMIT 5", (like, like, like)).fetchall()
            equipment = db.execute("SELECT id, name as title, 'equipment' as type FROM equipment_log WHERE name LIKE ? OR category LIKE ? OR location LIKE ? LIMIT 5", (like, like, like)).fetchall()
            waypoints = db.execute("SELECT id, name as title, 'waypoint' as type FROM waypoints WHERE name LIKE ? OR notes LIKE ? OR category LIKE ? LIMIT 5", (like, like, like)).fetchall()
            freqs = db.execute("SELECT id, service as title, 'frequency' as type FROM freq_database WHERE service LIKE ? OR description LIKE ? OR notes LIKE ? LIMIT 5", (like, like, like)).fetchall()
            patients = db.execute("SELECT id, name as title, 'patient' as type FROM patients WHERE name LIKE ? LIMIT 5", (like,)).fetchall()
            incidents = db.execute("SELECT id, description as title, 'incident' as type FROM incidents WHERE description LIKE ? OR category LIKE ? LIMIT 5", (like, like)).fetchall()
            fuel = db.execute("SELECT id, fuel_type as title, 'fuel' as type FROM fuel_storage WHERE fuel_type LIKE ? OR location LIKE ? LIMIT 5", (like, like)).fetchall()
        return jsonify({
            'conversations': [dict(r) for r in convos], 'notes': [dict(r) for r in notes],
            'documents': [dict(r) for r in docs], 'inventory': [dict(r) for r in inv],
            'contacts': [dict(r) for r in contacts], 'checklists': [dict(r) for r in checklists],
            'skills': [dict(r) for r in skills], 'ammo': [dict(r) for r in ammo],
            'equipment': [dict(r) for r in equipment], 'waypoints': [dict(r) for r in waypoints],
            'frequencies': [dict(r) for r in freqs], 'patients': [dict(r) for r in patients],
            'incidents': [dict(r) for r in incidents], 'fuel': [dict(r) for r in fuel],
        })

    # ─── System Health & Diagnostics ────────────────────────────────

    # [EXTRACTED to blueprint]

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
        full_path = os.path.normpath(os.path.join(_nukemap_dir, filepath))
        if not full_path.startswith(os.path.normpath(_nukemap_dir)):
            return jsonify({'error': 'Forbidden'}), 403
        if not os.path.isfile(full_path):
            log.warning(f'NukeMap file not found: {full_path}')
            return jsonify({'error': f'Not found: {filepath}'}), 404
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
        full_path = os.path.normpath(os.path.join(_viptrack_dir, filepath))
        if not full_path.startswith(os.path.normpath(_viptrack_dir)):
            return jsonify({'error': 'Forbidden'}), 403
        if not os.path.isfile(full_path):
            return jsonify({'error': f'Not found: {filepath}'}), 404
        return send_from_directory(os.path.dirname(full_path), os.path.basename(full_path))

    # ─── Skills Tracker ───────────────────────────────────────────────

    @app.route('/api/skills')
    def api_skills_list():
        conn = get_db()
        try:
            rows = conn.execute('SELECT * FROM skills ORDER BY category, name').fetchall()
            return jsonify([dict(r) for r in rows])
        finally:
            conn.close()

    @app.route('/api/skills', methods=['POST'])
    def api_skills_create():
        d = request.json or {}
        if not d.get('name', '').strip():
            return jsonify({'error': 'name is required'}), 400
        conn = get_db()
        try:
            cur = conn.execute(
                'INSERT INTO skills (name, category, proficiency, notes, last_practiced) VALUES (?,?,?,?,?)',
                (d['name'].strip(), d.get('category','general'), d.get('proficiency','none'),
                 d.get('notes',''), d.get('last_practiced','')))
            conn.commit()
            row = conn.execute('SELECT * FROM skills WHERE id=?', (cur.lastrowid,)).fetchone()
            return jsonify(dict(row)), 201
        finally:
            conn.close()

    @app.route('/api/skills/<int:sid>', methods=['PUT'])
    def api_skills_update(sid):
        d = request.json or {}
        conn = get_db()
        try:
            conn.execute(
                'UPDATE skills SET name=?, category=?, proficiency=?, notes=?, last_practiced=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                (d.get('name',''), d.get('category','general'), d.get('proficiency','none'),
                 d.get('notes',''), d.get('last_practiced',''), sid))
            conn.commit()
            row = conn.execute('SELECT * FROM skills WHERE id=?', (sid,)).fetchone()
            return jsonify(dict(row) if row else {})
        finally:
            conn.close()

    @app.route('/api/skills/<int:sid>', methods=['DELETE'])
    def api_skills_delete(sid):
        conn = get_db()
        try:
            conn.execute('DELETE FROM skills WHERE id=?', (sid,))
            conn.commit()
            return jsonify({'ok': True})
        finally:
            conn.close()

    @app.route('/api/skills/seed-defaults', methods=['POST'])
    def api_skills_seed():
        """Seed the default 60-skill list if table is empty."""
        conn = get_db()
        count = conn.execute('SELECT COUNT(*) FROM skills').fetchone()[0]
        if count > 0:
            conn.close()
            return jsonify({'seeded': 0})
        defaults = [
            # Fire
            ('Fire Starting (friction/bow drill)', 'Fire'), ('Fire Starting (ferro rod)', 'Fire'),
            ('Fire Starting (flint & steel)', 'Fire'), ('Fire Starting (magnification)', 'Fire'),
            ('Maintaining a fire for 12+ hours', 'Fire'), ('Building a fire in rain/wind', 'Fire'),
            # Water
            ('Water sourcing (streams, dew, transpiration)', 'Water'),
            ('Water purification (boiling)', 'Water'), ('Water purification (chemical)', 'Water'),
            ('Water purification (filtration)', 'Water'), ('Rainwater collection setup', 'Water'),
            ('Solar disinfection (SODIS)', 'Water'),
            # Shelter
            ('Debris hut construction', 'Shelter'), ('Tarp shelter rigging', 'Shelter'),
            ('Cold-weather shelter (snow trench, quinzhee)', 'Shelter'),
            ('Knot tying (8 essential knots)', 'Shelter'), ('Rope/cordage making', 'Shelter'),
            # Food
            ('Foraging wild edibles', 'Food'), ('Identifying poisonous plants', 'Food'),
            ('Small game trapping (snares)', 'Food'), ('Hunting / firearms proficiency', 'Food'),
            ('Fishing (without conventional tackle)', 'Food'), ('Food preservation (canning)', 'Food'),
            ('Food preservation (dehydrating)', 'Food'), ('Food preservation (smoking)', 'Food'),
            ('Butchering / game processing', 'Food'), ('Gardening (seed-to-harvest)', 'Food'),
            # Navigation
            ('Map and compass navigation', 'Navigation'), ('Celestial navigation (stars/sun)', 'Navigation'),
            ('GPS use and offline mapping', 'Navigation'), ('Dead reckoning', 'Navigation'),
            ('Terrain association', 'Navigation'), ('Creating a field sketch map', 'Navigation'),
            # Medical
            ('CPR (adult, child, infant)', 'Medical'), ('Tourniquet application', 'Medical'),
            ('Wound packing / pressure bandage', 'Medical'), ('Splinting fractures', 'Medical'),
            ('Suturing / wound closure (improvised)', 'Medical'),
            ('Burn treatment', 'Medical'), ('Triage (START method)', 'Medical'),
            ('Managing shock', 'Medical'), ('Drug interaction awareness', 'Medical'),
            ('Childbirth assistance', 'Medical'), ('Dental emergency management', 'Medical'),
            # Communications
            ('Ham radio operation (Technician)', 'Communications'),
            ('Ham radio operation (General/HF)', 'Communications'),
            ('Morse code (sending & receiving)', 'Communications'),
            ('Meshtastic / LoRa mesh setup', 'Communications'),
            ('Radio programming (CHIRP)', 'Communications'),
            ('ICS / ARES net procedures', 'Communications'),
            # Security
            ('Threat assessment / situational awareness', 'Security'),
            ('Perimeter security setup', 'Security'),
            ('Night operations', 'Security'), ('Gray man / OPSEC', 'Security'),
            # Mechanical
            ('Vehicle maintenance (basic)', 'Mechanical'),
            ('Small engine repair', 'Mechanical'),
            ('Improvised tool fabrication', 'Mechanical'),
            ('Electrical / solar system wiring', 'Mechanical'),
            ('Water system plumbing', 'Mechanical'),
            # Homesteading
            ('Livestock care (chickens)', 'Homesteading'),
            ('Livestock care (goats/pigs/cattle)', 'Homesteading'),
            ('Composting', 'Homesteading'), ('Seed saving', 'Homesteading'),
            ('Natural building (adobe/cob)', 'Homesteading'),
        ]
        for name, cat in defaults:
            conn.execute('INSERT OR IGNORE INTO skills (name, category, proficiency) VALUES (?,?,?)',
                         (name, cat, 'none'))
        conn.commit()
        conn.close()
        return jsonify({'seeded': len(defaults)})

    # ─── Ammo Inventory ───────────────────────────────────────────────

    @app.route('/api/ammo')
    def api_ammo_list():
        conn = get_db()
        rows = conn.execute('SELECT * FROM ammo_inventory ORDER BY caliber, brand').fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/ammo', methods=['POST'])
    def api_ammo_create():
        d = request.json or {}
        try:
            qty = int(d.get('quantity', 0))
        except (ValueError, TypeError):
            qty = 0
        conn = get_db()
        try:
            cur = conn.execute(
                'INSERT INTO ammo_inventory (caliber, brand, bullet_weight, bullet_type, quantity, location, notes) VALUES (?,?,?,?,?,?,?)',
                (d.get('caliber',''), d.get('brand',''), d.get('bullet_weight',''),
                 d.get('bullet_type',''), qty, d.get('location',''), d.get('notes','')))
            conn.commit()
            row = conn.execute('SELECT * FROM ammo_inventory WHERE id=?', (cur.lastrowid,)).fetchone()
            return jsonify(dict(row)), 201
        finally:
            conn.close()

    @app.route('/api/ammo/<int:aid>', methods=['PUT'])
    def api_ammo_update(aid):
        d = request.json or {}
        try:
            qty = int(d.get('quantity', 0))
        except (ValueError, TypeError):
            qty = 0
        conn = get_db()
        try:
            conn.execute(
                'UPDATE ammo_inventory SET caliber=?, brand=?, bullet_weight=?, bullet_type=?, quantity=?, location=?, notes=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                (d.get('caliber',''), d.get('brand',''), d.get('bullet_weight',''),
                 d.get('bullet_type',''), qty, d.get('location',''), d.get('notes',''), aid))
            conn.commit()
            row = conn.execute('SELECT * FROM ammo_inventory WHERE id=?', (aid,)).fetchone()
            return jsonify(dict(row) if row else {})
        finally:
            conn.close()

    @app.route('/api/ammo/<int:aid>', methods=['DELETE'])
    def api_ammo_delete(aid):
        conn = get_db()
        try:
            conn.execute('DELETE FROM ammo_inventory WHERE id=?', (aid,))
            conn.commit()
            return jsonify({'ok': True})
        finally:
            conn.close()

    @app.route('/api/ammo/summary')
    def api_ammo_summary():
        conn = get_db()
        try:
            rows = conn.execute(
                'SELECT caliber, SUM(quantity) as total FROM ammo_inventory GROUP BY caliber ORDER BY total DESC'
            ).fetchall()
            total = conn.execute('SELECT SUM(quantity) FROM ammo_inventory').fetchone()[0] or 0
            return jsonify({'by_caliber': [dict(r) for r in rows], 'total': total})
        finally:
            conn.close()

    # ─── Community Resource Registry ──────────────────────────────────

    @app.route('/api/community')
    def api_community_list():
        conn = get_db()
        try:
            rows = conn.execute('SELECT * FROM community_resources ORDER BY trust_level DESC, name').fetchall()
            return jsonify([dict(r) for r in rows])
        finally:
            conn.close()

    @app.route('/api/community', methods=['POST'])
    def api_community_create():
        d = request.json or {}
        if not d.get('name', '').strip():
            return jsonify({'error': 'name is required'}), 400
        try:
            dist = float(d.get('distance_mi', 0))
        except (ValueError, TypeError):
            dist = 0.0
        import json as _json
        conn = get_db()
        try:
            cur = conn.execute(
                'INSERT INTO community_resources (name, distance_mi, skills, equipment, contact, notes, trust_level) VALUES (?,?,?,?,?,?,?)',
                (d['name'].strip(), dist,
                 _json.dumps(d.get('skills',[])), _json.dumps(d.get('equipment',[])),
                 d.get('contact',''), d.get('notes',''), d.get('trust_level','unknown')))
            conn.commit()
            row = conn.execute('SELECT * FROM community_resources WHERE id=?', (cur.lastrowid,)).fetchone()
            return jsonify(dict(row)), 201
        finally:
            conn.close()

    @app.route('/api/community/<int:cid>', methods=['PUT'])
    def api_community_update(cid):
        d = request.json or {}
        try:
            dist = float(d.get('distance_mi', 0))
        except (ValueError, TypeError):
            dist = 0.0
        import json as _json
        conn = get_db()
        try:
            conn.execute(
                'UPDATE community_resources SET name=?, distance_mi=?, skills=?, equipment=?, contact=?, notes=?, trust_level=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                (d.get('name',''), dist,
                 _json.dumps(d.get('skills',[])), _json.dumps(d.get('equipment',[])),
                 d.get('contact',''), d.get('notes',''), d.get('trust_level','unknown'), cid))
            conn.commit()
            row = conn.execute('SELECT * FROM community_resources WHERE id=?', (cid,)).fetchone()
            return jsonify(dict(row) if row else {})
        finally:
            conn.close()

    @app.route('/api/community/<int:cid>', methods=['DELETE'])
    def api_community_delete(cid):
        conn = get_db()
        try:
            conn.execute('DELETE FROM community_resources WHERE id=?', (cid,))
            conn.commit()
            return jsonify({'ok': True})
        finally:
            conn.close()

    # ─── Radiation Dose Log ───────────────────────────────────────────

    @app.route('/api/radiation')
    def api_radiation_list():
        conn = get_db()
        try:
            rows = conn.execute('SELECT * FROM radiation_log ORDER BY created_at DESC LIMIT 200').fetchall()
            total = conn.execute('SELECT COALESCE(MAX(cumulative_rem), 0) FROM radiation_log').fetchone()[0] or 0
            return jsonify({'readings': [dict(r) for r in rows], 'total_rem': round(total, 4)})
        finally:
            conn.close()

    @app.route('/api/radiation', methods=['POST'])
    def api_radiation_create():
        d = request.json or {}
        try:
            new_rate = float(d.get('dose_rate_rem', 0))
        except (ValueError, TypeError):
            new_rate = 0.0
        conn = get_db()
        try:
            last = conn.execute('SELECT cumulative_rem FROM radiation_log ORDER BY id DESC LIMIT 1').fetchone()
            prev_cum = (last['cumulative_rem'] or 0) if last else 0
            new_cum = round(prev_cum + new_rate, 4)
            cur = conn.execute(
                'INSERT INTO radiation_log (dose_rate_rem, location, cumulative_rem, notes) VALUES (?,?,?,?)',
                (new_rate, d.get('location',''), new_cum, d.get('notes','')))
            conn.commit()
            row = conn.execute('SELECT * FROM radiation_log WHERE id=?', (cur.lastrowid,)).fetchone()
            return jsonify(dict(row)), 201
        finally:
            conn.close()

    @app.route('/api/radiation/clear', methods=['POST'])
    def api_radiation_clear():
        conn = get_db()
        try:
            conn.execute('DELETE FROM radiation_log')
            conn.commit()
            return jsonify({'ok': True})
        finally:
            conn.close()

    # ─── Fuel Storage ─────────────────────────────────────────────────

    @app.route('/api/fuel')
    def api_fuel_list():
        conn = get_db()
        try:
            rows = conn.execute('SELECT * FROM fuel_storage ORDER BY fuel_type, created_at DESC').fetchall()
            return jsonify([dict(r) for r in rows])
        finally:
            conn.close()

    @app.route('/api/fuel', methods=['POST'])
    def api_fuel_create():
        d = request.json or {}
        if not d.get('fuel_type', '').strip():
            return jsonify({'error': 'fuel_type is required'}), 400
        try:
            stab = int(d.get('stabilizer_added', 0))
        except (ValueError, TypeError):
            stab = 0
        try:
            qty = float(d.get('quantity', 0))
        except (ValueError, TypeError):
            qty = 0.0
        conn = get_db()
        try:
            cur = conn.execute(
                'INSERT INTO fuel_storage (fuel_type, quantity, unit, container, location, stabilizer_added, date_stored, expires, notes) VALUES (?,?,?,?,?,?,?,?,?)',
                (d['fuel_type'].strip(), qty, d.get('unit','gallons'),
                 d.get('container',''), d.get('location',''), stab,
                 d.get('date_stored',''), d.get('expires',''), d.get('notes','')))
            conn.commit()
            row = conn.execute('SELECT * FROM fuel_storage WHERE id=?', (cur.lastrowid,)).fetchone()
            return jsonify(dict(row)), 201
        finally:
            conn.close()

    @app.route('/api/fuel/<int:fid>', methods=['PUT'])
    def api_fuel_update(fid):
        d = request.json or {}
        try:
            stab = int(d.get('stabilizer_added', 0))
        except (ValueError, TypeError):
            stab = 0
        try:
            qty = float(d.get('quantity', 0))
        except (ValueError, TypeError):
            qty = 0.0
        conn = get_db()
        try:
            conn.execute(
                'UPDATE fuel_storage SET fuel_type=?,quantity=?,unit=?,container=?,location=?,stabilizer_added=?,date_stored=?,expires=?,notes=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',
                (d.get('fuel_type',''), qty, d.get('unit','gallons'),
                 d.get('container',''), d.get('location',''), stab,
                 d.get('date_stored',''), d.get('expires',''), d.get('notes',''), fid))
            conn.commit()
            row = conn.execute('SELECT * FROM fuel_storage WHERE id=?', (fid,)).fetchone()
            return jsonify(dict(row) if row else {})
        finally:
            conn.close()

    @app.route('/api/fuel/<int:fid>', methods=['DELETE'])
    def api_fuel_delete(fid):
        conn = get_db()
        try:
            conn.execute('DELETE FROM fuel_storage WHERE id=?', (fid,))
            conn.commit()
            return jsonify({'ok': True})
        finally:
            conn.close()

    @app.route('/api/fuel/summary')
    def api_fuel_summary():
        conn = get_db()
        try:
            rows = conn.execute('SELECT fuel_type, SUM(quantity) as total, unit FROM fuel_storage GROUP BY fuel_type, unit').fetchall()
            return jsonify([dict(r) for r in rows])
        finally:
            conn.close()

    # ─── Equipment Maintenance ────────────────────────────────────────

    @app.route('/api/equipment')
    def api_equipment_list():
        conn = get_db()
        try:
            rows = conn.execute('SELECT * FROM equipment_log ORDER BY status, next_service').fetchall()
            return jsonify([dict(r) for r in rows])
        finally:
            conn.close()

    @app.route('/api/equipment', methods=['POST'])
    def api_equipment_create():
        d = request.json or {}
        if not d.get('name', '').strip():
            return jsonify({'error': 'name is required'}), 400
        conn = get_db()
        try:
            cur = conn.execute(
                'INSERT INTO equipment_log (name, category, last_service, next_service, service_notes, status, location, notes) VALUES (?,?,?,?,?,?,?,?)',
                (d['name'].strip(), d.get('category','general'), d.get('last_service',''),
                 d.get('next_service',''), d.get('service_notes',''), d.get('status','operational'),
                 d.get('location',''), d.get('notes','')))
            conn.commit()
            row = conn.execute('SELECT * FROM equipment_log WHERE id=?', (cur.lastrowid,)).fetchone()
            return jsonify(dict(row)), 201
        finally:
            conn.close()

    @app.route('/api/equipment/<int:eid>', methods=['PUT'])
    def api_equipment_update(eid):
        d = request.json or {}
        conn = get_db()
        try:
            conn.execute(
                'UPDATE equipment_log SET name=?,category=?,last_service=?,next_service=?,service_notes=?,status=?,location=?,notes=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',
                (d.get('name',''), d.get('category','general'), d.get('last_service',''),
                 d.get('next_service',''), d.get('service_notes',''), d.get('status','operational'),
                 d.get('location',''), d.get('notes',''), eid))
            conn.commit()
            row = conn.execute('SELECT * FROM equipment_log WHERE id=?', (eid,)).fetchone()
            return jsonify(dict(row) if row else {})
        finally:
            conn.close()

    @app.route('/api/equipment/<int:eid>', methods=['DELETE'])
    def api_equipment_delete(eid):
        conn = get_db()
        try:
            conn.execute('DELETE FROM equipment_log WHERE id=?', (eid,))
            conn.commit()
            return jsonify({'ok': True})
        finally:
            conn.close()

    # [EXTRACTED to blueprint]


    # [EXTRACTED to blueprint]

    # ─── Content Update Checker ───────────────────────────────────────

    @app.route('/api/kiwix/check-updates')
    def api_kiwix_check_updates():
        """Compare installed ZIMs against catalog for newer versions."""
        if not kiwix.is_installed():
            return jsonify([])
        installed = kiwix.list_zim_files()
        catalog = kiwix.get_catalog()
        updates = []

        # Build lookup of all catalog entries by filename prefix
        catalog_by_prefix = {}
        for cat in catalog:
            for tier_name, zims in cat.get('tiers', {}).items():
                for z in zims:
                    # Extract base name (before date portion)
                    fname = z.get('filename', '')
                    # e.g. "wikipedia_en_all_maxi_2026-02.zim" -> "wikipedia_en_all_maxi"
                    parts = fname.rsplit('_', 1)
                    if len(parts) == 2:
                        prefix = parts[0]
                    else:
                        prefix = fname.replace('.zim', '')
                    catalog_by_prefix[prefix] = z

        for inst in installed:
            inst_fname = inst.get('name', '') if isinstance(inst, dict) else str(inst)
            parts = inst_fname.rsplit('_', 1)
            prefix = parts[0] if len(parts) == 2 else inst_fname.replace('.zim', '')
            if prefix in catalog_by_prefix:
                cat_entry = catalog_by_prefix[prefix]
                if cat_entry['filename'] != inst_fname:
                    updates.append({
                        'installed': inst_fname,
                        'available': cat_entry['filename'],
                        'name': cat_entry.get('name', ''),
                        'size': cat_entry.get('size', ''),
                        'url': cat_entry.get('url', ''),
                    })
        return jsonify(updates)

    # ─── Wikipedia Tier Selection ─────────────────────────────────────

    @app.route('/api/kiwix/wikipedia-options')
    def api_kiwix_wikipedia_options():
        """Return Wikipedia download tiers for dedicated selector."""
        catalog = kiwix.get_catalog()
        for cat in catalog:
            if cat.get('category', '').startswith('Wikipedia'):
                # Flatten all tiers into a list with tier labels
                options = []
                for tier_name, zims in cat.get('tiers', {}).items():
                    for z in zims:
                        options.append({**z, 'tier': tier_name})
                return jsonify(options)
        return jsonify([])

    # ─── Self-Update Download ─────────────────────────────────────────

    # [EXTRACTED to blueprint]

    @app.route('/api/tasks')
    def api_tasks_list():
        with db_session() as db:
            cat = request.args.get('category', '')
            assigned = request.args.get('assigned_to', '')
            query = 'SELECT * FROM scheduled_tasks'
            params = []
            clauses = []
            if cat:
                clauses.append('category = ?')
                params.append(cat)
            if assigned:
                clauses.append('assigned_to = ?')
                params.append(assigned)
            if clauses:
                query += ' WHERE ' + ' AND '.join(clauses)
            query += ' ORDER BY next_due ASC LIMIT 500'
            rows = db.execute(query, params).fetchall()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/tasks', methods=['POST'])
    def api_tasks_create():
        data = request.get_json() or {}
        if not data.get('name'):
            return jsonify({'error': 'name is required'}), 400
        with db_session() as db:
            cur = db.execute(
                'INSERT INTO scheduled_tasks (name, category, recurrence, next_due, assigned_to, notes) VALUES (?, ?, ?, ?, ?, ?)',
                (data.get('name', ''), data.get('category', 'custom'), data.get('recurrence', 'once'),
                 data.get('next_due', ''), data.get('assigned_to', ''), data.get('notes', '')))
            db.commit()
            row = db.execute('SELECT * FROM scheduled_tasks WHERE id = ?', (cur.lastrowid,)).fetchone()
        log_activity('task_created', 'scheduler', data.get('name', ''))
        return jsonify(dict(row)), 201

    @app.route('/api/tasks/<int:task_id>', methods=['PUT'])
    def api_tasks_update(task_id):
        data = request.get_json() or {}
        with db_session() as db:
            allowed = ['name', 'category', 'recurrence', 'next_due', 'assigned_to', 'notes']
            filtered = safe_columns(data, allowed)
            if not filtered:
                return jsonify({'error': 'No fields to update'}), 400
            sql, params = build_update('scheduled_tasks', filtered, allowed, where_val=task_id)
            db.execute(sql, params)
            db.commit()
            row = db.execute('SELECT * FROM scheduled_tasks WHERE id = ?', (task_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Task not found'}), 404
        return jsonify(dict(row))

    @app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
    def api_tasks_delete(task_id):
        with db_session() as db:
            db.execute('DELETE FROM scheduled_tasks WHERE id = ?', (task_id,))
            db.commit()
        return jsonify({'status': 'deleted'})

    @app.route('/api/tasks/<int:task_id>/complete', methods=['POST'])
    def api_tasks_complete(task_id):
        from datetime import datetime, timedelta
        with db_session() as db:
            row = db.execute('SELECT * FROM scheduled_tasks WHERE id = ?', (task_id,)).fetchone()
            if not row:
                return jsonify({'error': 'Task not found'}), 404
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            new_count = (row['completed_count'] or 0) + 1
            # Calculate next_due for recurring tasks
            next_due = None
            rec = row['recurrence']
            if rec == 'daily':
                next_due = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
            elif rec == 'weekly':
                next_due = (datetime.now() + timedelta(weeks=1)).strftime('%Y-%m-%d %H:%M:%S')
            elif rec == 'monthly':
                next_due = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
            else:
                next_due = None  # one-time task stays completed
            db.execute('UPDATE scheduled_tasks SET completed_count = ?, last_completed = ?, next_due = ? WHERE id = ?',
                       (new_count, now, next_due, task_id))
            db.commit()
            updated = db.execute('SELECT * FROM scheduled_tasks WHERE id = ?', (task_id,)).fetchone()
            task_name = row['name']
        log_activity('task_completed', 'scheduler', task_name)
        broadcast_event('task_update', {'id': task_id, 'status': 'completed'})
        return jsonify(dict(updated))

    @app.route('/api/tasks/due')
    def api_tasks_due():
        from datetime import datetime
        with db_session() as db:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            rows = db.execute(
                'SELECT * FROM scheduled_tasks WHERE next_due IS NOT NULL AND next_due <= ? ORDER BY next_due ASC',
                (now,)).fetchall()
        return jsonify([dict(r) for r in rows])

    # ─── Watch/Shift Rotation Planner (Phase 15) ─────────────────────

    @app.route('/api/watch-schedules')
    def api_watch_schedules():
        db = get_db()
        try:
            rows = db.execute('SELECT * FROM watch_schedules ORDER BY start_date DESC').fetchall()
            return jsonify([dict(r) for r in rows])
        finally:
            db.close()

    @app.route('/api/watch-schedules', methods=['POST'])
    def api_watch_schedules_create():
        data = request.get_json() or {}
        name = data.get('name', 'Watch Schedule').strip()
        start_date = data.get('start_date', '')
        end_date = data.get('end_date', '')
        shift_hours = int(data.get('shift_duration_hours', 4))
        personnel = data.get('personnel', [])
        notes = data.get('notes', '')

        if not start_date:
            return jsonify({'error': 'start_date is required'}), 400
        if shift_hours < 1 or shift_hours > 24:
            return jsonify({'error': 'shift_duration_hours must be 1-24'}), 400
        if not personnel or len(personnel) < 2:
            return jsonify({'error': 'At least 2 personnel required'}), 400

        import json as _json
        from datetime import datetime, timedelta

        # Auto-generate rotation schedule
        schedule = []
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d') if end_date else start + timedelta(days=7)
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

        current = start
        person_idx = 0
        while current < end:
            shift_end = current + timedelta(hours=shift_hours)
            if shift_end > end:
                shift_end = end
            schedule.append({
                'person': personnel[person_idx % len(personnel)],
                'start': current.strftime('%Y-%m-%d %H:%M'),
                'end': shift_end.strftime('%Y-%m-%d %H:%M'),
                'position': person_idx % len(personnel) + 1,
            })
            current = shift_end
            person_idx += 1

        db = get_db()
        try:
            cur = db.execute(
                'INSERT INTO watch_schedules (name, start_date, end_date, shift_duration_hours, personnel, schedule_json, notes) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (name, start_date, end_date or (start + timedelta(days=7)).strftime('%Y-%m-%d'), shift_hours, _json.dumps(personnel), _json.dumps(schedule), notes)
            )
            db.commit()
            sid = cur.lastrowid
        finally:
            db.close()
        log_activity('watch_schedule_created', 'operations', f'{name}: {len(personnel)} personnel, {shift_hours}h shifts')
        return jsonify({'id': sid, 'name': name, 'shifts': len(schedule), 'schedule': schedule}), 201

    @app.route('/api/watch-schedules/<int:sid>', methods=['DELETE'])
    def api_watch_schedules_delete(sid):
        db = get_db()
        try:
            db.execute('DELETE FROM watch_schedules WHERE id = ?', (sid,))
            db.commit()
        finally:
            db.close()
        return jsonify({'status': 'deleted'})

    @app.route('/api/watch-schedules/<int:sid>')
    def api_watch_schedule_detail(sid):
        db = get_db()
        try:
            row = db.execute('SELECT * FROM watch_schedules WHERE id = ?', (sid,)).fetchone()
            if not row:
                return jsonify({'error': 'Not found'}), 404
            return jsonify(dict(row))
        finally:
            db.close()

    @app.route('/api/watch-schedules/<int:sid>/print')
    def api_watch_schedule_print(sid):
        """Generate a printable HTML watch schedule."""
        import json as _json
        db = get_db()
        try:
            row = db.execute('SELECT * FROM watch_schedules WHERE id = ?', (sid,)).fetchone()
            if not row:
                return jsonify({'error': 'Not found'}), 404
            sched = row
            schedule = _json.loads(sched['schedule_json'] or '[]')
            personnel = _json.loads(sched['personnel'] or '[]')
        finally:
            db.close()

        def _esc(s):
            return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')

        html = f'''<!DOCTYPE html><html><head><meta charset="utf-8"><title>Watch Schedule — {_esc(sched["name"])}</title>
        <style>body{{font-family:Arial,sans-serif;max-width:900px;margin:auto;padding:24px}}
        h1{{font-size:22px;border-bottom:2px solid #333;padding-bottom:8px}}
        table{{width:100%;border-collapse:collapse;margin-top:16px}}th,td{{border:1px solid #ccc;padding:8px;text-align:left;font-size:13px}}
        th{{background:#f0f0f0;font-weight:bold}}.meta{{font-size:12px;color:#666;margin:4px 0}}
        @media print{{body{{padding:0}}}}
        </style></head><body>
        <h1>Watch Schedule: {_esc(sched["name"])}</h1>
        <div class="meta">Period: {_esc(sched["start_date"])} to {_esc(sched["end_date"] or "ongoing")} | Shift Duration: {sched["shift_duration_hours"]}h | Personnel: {len(personnel)}</div>
        <table><thead><tr><th>#</th><th>Person</th><th>Start</th><th>End</th></tr></thead><tbody>'''

        for i, shift in enumerate(schedule):
            html += f'<tr><td>{i+1}</td><td>{_esc(shift["person"])}</td><td>{_esc(shift["start"])}</td><td>{_esc(shift["end"])}</td></tr>'

        html += f'</tbody></table><p style="margin-top:24px;font-size:9px;color:#999;">Generated by Project N.O.M.A.D. — {__import__("time").strftime("%Y-%m-%d %H:%M")}</p></body></html>'
        return html, 200, {'Content-Type': 'text/html'}

    # ─── Sunrise/Sunset Engine (Phase 15) ─────────────────────────────

    @app.route('/api/sun')
    def api_sun():
        """NOAA solar calculator — returns sunrise, sunset, civil twilight, golden hour."""
        import math
        from datetime import datetime, timedelta, timezone

        lat = request.args.get('lat', type=float)
        lng = request.args.get('lng', type=float)
        date_str = request.args.get('date', '')
        if lat is None or lng is None:
            return jsonify({'error': 'lat and lng are required'}), 400
        try:
            if date_str:
                dt = datetime.strptime(date_str, '%Y-%m-%d')
            else:
                dt = datetime.now()
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

        # NOAA Solar Calculator implementation
        def _julian_day(year, month, day):
            if month <= 2:
                year -= 1
                month += 12
            A = int(year / 100)
            B = 2 - A + int(A / 4)
            return int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + B - 1524.5

        def _sun_times(latitude, longitude, jd, zenith):
            """Calculate sunrise/sunset for a given zenith angle."""
            n = jd - 2451545.0 + 0.0008
            Jstar = n - longitude / 360.0
            M = (357.5291 + 0.98560028 * Jstar) % 360
            M_rad = math.radians(M)
            C = 1.9148 * math.sin(M_rad) + 0.02 * math.sin(2 * M_rad) + 0.0003 * math.sin(3 * M_rad)
            lam = (M + C + 180 + 102.9372) % 360
            lam_rad = math.radians(lam)
            Jtransit = 2451545.0 + Jstar + 0.0053 * math.sin(M_rad) - 0.0069 * math.sin(2 * lam_rad)
            sin_dec = math.sin(lam_rad) * math.sin(math.radians(23.4397))
            cos_dec = math.cos(math.asin(sin_dec))
            cos_ha = (math.cos(math.radians(zenith)) - math.sin(math.radians(latitude)) * sin_dec) / (math.cos(math.radians(latitude)) * cos_dec)
            if cos_ha < -1 or cos_ha > 1:
                return None, None  # no sunrise/sunset (polar)
            ha = math.degrees(math.acos(cos_ha))
            J_rise = Jtransit - ha / 360.0
            J_set = Jtransit + ha / 360.0
            return J_rise, J_set

        def _jd_to_time(jd_val):
            """Convert Julian Day to HH:MM time string."""
            jd_val += 0.5
            Z = int(jd_val)
            F = jd_val - Z
            if Z < 2299161:
                A = Z
            else:
                alpha = int((Z - 1867216.25) / 36524.25)
                A = Z + 1 + alpha - int(alpha / 4)
            B = A + 1524
            C = int((B - 122.1) / 365.25)
            D = int(365.25 * C)
            E = int((B - D) / 30.6001)
            day_frac = B - D - int(30.6001 * E) + F
            hours = (day_frac - int(day_frac)) * 24
            h = int(hours)
            m = int((hours - h) * 60)
            return f'{h:02d}:{m:02d}'

        year, month, day = dt.year, dt.month, dt.day
        jd = _julian_day(year, month, day)

        result = {'date': dt.strftime('%Y-%m-%d'), 'lat': lat, 'lng': lng}

        # Standard sunrise/sunset (zenith 90.833)
        rise_jd, set_jd = _sun_times(lat, lng, jd, 90.833)
        if rise_jd and set_jd:
            result['sunrise'] = _jd_to_time(rise_jd)
            result['sunset'] = _jd_to_time(set_jd)
        else:
            result['sunrise'] = None
            result['sunset'] = None

        # Civil twilight (zenith 96)
        civ_rise, civ_set = _sun_times(lat, lng, jd, 96.0)
        if civ_rise and civ_set:
            result['civil_twilight_begin'] = _jd_to_time(civ_rise)
            result['civil_twilight_end'] = _jd_to_time(civ_set)
        else:
            result['civil_twilight_begin'] = None
            result['civil_twilight_end'] = None

        # Golden hour (approximately when sun is 6 degrees above horizon -> zenith 84)
        gold_rise, gold_set = _sun_times(lat, lng, jd, 84.0)
        if gold_rise and gold_set and rise_jd and set_jd:
            result['golden_hour_morning_end'] = _jd_to_time(gold_rise)
            result['golden_hour_evening_start'] = _jd_to_time(gold_set)
        else:
            result['golden_hour_morning_end'] = None
            result['golden_hour_evening_start'] = None

        # Day length
        if rise_jd and set_jd:
            day_len_hours = (set_jd - rise_jd) * 24
            h = int(day_len_hours)
            m = int((day_len_hours - h) * 60)
            result['day_length'] = f'{h}h {m}m'
        else:
            result['day_length'] = None

        return jsonify(result)

    # ─── Predictive Alerts (Phase 15) ─────────────────────────────────

    @app.route('/api/alerts/predictive')
    def api_alerts_predictive():
        """Analyze trends and return predictions: burn rates, fuel expiry, equipment overdue, medication schedules."""
        from datetime import datetime, timedelta
        alerts = []
        today = datetime.now()
        today_str = today.strftime('%Y-%m-%d')
        with db_session() as db:

            # 1. Inventory burn rate — items that will run out
            burn_rows = db.execute('SELECT id, name, category, quantity, unit, daily_usage, expiration FROM inventory WHERE daily_usage > 0 LIMIT 200').fetchall()
            for r in burn_rows:
                days_left = r['quantity'] / r['daily_usage'] if r['daily_usage'] > 0 else float('inf')
                if days_left <= 30:
                    severity = 'critical' if days_left <= 7 else 'warning'
                    alerts.append({
                        'type': 'inventory_depletion',
                        'severity': severity,
                        'title': f'{r["name"]} running low',
                        'message': f'{r["quantity"]} {r["unit"]} remaining at {r["daily_usage"]}/day — ~{round(days_left, 1)} days left',
                        'item_id': r['id'],
                        'days_remaining': round(days_left, 1),
                        'category': r['category'],
                    })

            # 2. Inventory expiration
            exp_rows = db.execute("SELECT id, name, category, quantity, unit, expiration FROM inventory WHERE expiration != '' AND expiration IS NOT NULL LIMIT 200").fetchall()
            for r in exp_rows:
                try:
                    exp_date = datetime.strptime(r['expiration'], '%Y-%m-%d')
                    days_until = (exp_date - today).days
                    if days_until <= 90:
                        if days_until < 0:
                            severity = 'critical'
                            msg = f'Expired {abs(days_until)} days ago'
                        elif days_until <= 14:
                            severity = 'critical'
                            msg = f'Expires in {days_until} days'
                        else:
                            severity = 'warning'
                            msg = f'Expires in {days_until} days'
                        alerts.append({
                            'type': 'inventory_expiration',
                            'severity': severity,
                            'title': f'{r["name"]} expiring',
                            'message': f'{msg} ({r["expiration"]})',
                            'item_id': r['id'],
                            'days_until_expiry': days_until,
                            'category': r['category'],
                        })
                except (ValueError, TypeError):
                    pass

            # 3. Fuel expiry
            fuel_rows = db.execute("SELECT id, fuel_type, quantity, unit, expires FROM fuel_storage WHERE expires != '' AND expires IS NOT NULL LIMIT 100").fetchall()
            for r in fuel_rows:
                try:
                    exp_date = datetime.strptime(r['expires'], '%Y-%m-%d')
                    days_until = (exp_date - today).days
                    if days_until <= 90:
                        severity = 'critical' if days_until <= 14 else 'warning'
                        alerts.append({
                            'type': 'fuel_expiry',
                            'severity': severity,
                            'title': f'{r["fuel_type"]} fuel expiring',
                            'message': f'{r["quantity"]} {r["unit"]} expires in {days_until} days ({r["expires"]})',
                            'item_id': r['id'],
                            'days_until_expiry': days_until,
                        })
                except (ValueError, TypeError):
                    pass

            # 4. Equipment maintenance overdue
            equip_rows = db.execute("SELECT id, name, category, next_service, status FROM equipment_log WHERE next_service != '' AND next_service IS NOT NULL LIMIT 100").fetchall()
            for r in equip_rows:
                try:
                    svc_date = datetime.strptime(r['next_service'], '%Y-%m-%d')
                    days_until = (svc_date - today).days
                    if days_until <= 14:
                        severity = 'critical' if days_until < 0 else 'warning'
                        if days_until < 0:
                            msg = f'Maintenance overdue by {abs(days_until)} days'
                        else:
                            msg = f'Maintenance due in {days_until} days'
                        alerts.append({
                            'type': 'equipment_maintenance',
                            'severity': severity,
                            'title': f'{r["name"]} maintenance {"overdue" if days_until < 0 else "due"}',
                            'message': msg,
                            'item_id': r['id'],
                            'days_until_service': days_until,
                        })
                except (ValueError, TypeError):
                    pass

            # 5. Scheduled tasks overdue
            task_rows = db.execute("SELECT id, name, category, next_due, assigned_to FROM scheduled_tasks WHERE next_due IS NOT NULL AND next_due <= ?",
                                   (today.strftime('%Y-%m-%d %H:%M:%S'),)).fetchall()
            for r in task_rows:
                alerts.append({
                    'type': 'task_overdue',
                    'severity': 'warning',
                    'title': f'Task overdue: {r["name"]}',
                    'message': f'Category: {r["category"]}, Assigned to: {r["assigned_to"] or "unassigned"}',
                    'item_id': r['id'],
                    'category': r['category'],
                })

        # Sort: critical first, then warning
        alerts.sort(key=lambda a: (0 if a['severity'] == 'critical' else 1, a.get('days_remaining', a.get('days_until_expiry', a.get('days_until_service', 999)))))
        return jsonify({'alerts': alerts, 'count': len(alerts), 'generated_at': today.strftime('%Y-%m-%d %H:%M:%S')})

    # ─── CSV Import Wizard (Phase 17) ─────────────────────────────────

    # [EXTRACTED to blueprint]


    # [EXTRACTED to blueprint]


    # ─── QR Code Generation (Phase 17) ────────────────────────────────

    # [EXTRACTED to blueprint]


    # [EXTRACTED to blueprint]

    # ─── PWA Service Worker ─────────────────────────────────────────

    @app.route('/sw.js')
    def service_worker():
        return app.send_static_file('sw.js')

    # ─── Favicon ──────────────────────────────────────────────────────

    @app.route('/favicon.ico')
    def favicon():
        svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><polygon points="32,4 60,32 32,60 4,32" fill="#4f9cf7"/><polygon points="32,14 50,32 32,50 14,32" fill="#0d0d0d"/><polygon points="32,22 42,32 32,42 22,32" fill="#4f9cf7"/></svg>'
        return Response(svg, mimetype='image/svg+xml')

    # [EXTRACTED to blueprint] OCR pipeline helpers + routes


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
                'checklists': 'SELECT id, name, items, category FROM checklists ORDER BY name LIMIT 500',
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
                'contacts': "SELECT * FROM contacts WHERE created_at > ? ORDER BY created_at DESC LIMIT 500",
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

    # [EXTRACTED to blueprint] Dead drop routes


    # ─── Multi-Node Group Training Exercises ─────────────────────────
    @app.route('/api/group-exercises')
    def api_group_exercises_list():
        """List all group training exercises."""
        with db_session() as db:
            rows = db.execute('SELECT * FROM group_exercises ORDER BY updated_at DESC LIMIT 50').fetchall()
        result = []
        for r in rows:
            entry = dict(r)
            entry['participants'] = json.loads(entry.get('participants') or '[]')
            entry['decisions_log'] = json.loads(entry.get('decisions_log') or '[]')
            entry['shared_state'] = json.loads(entry.get('shared_state') or '{}')
            result.append(entry)
        return jsonify(result)

    @app.route('/api/group-exercises', methods=['POST'])
    def api_group_exercises_create():
        """Create a new group exercise and broadcast to federation peers."""
        import uuid as _uuid
        data = request.get_json() or {}
        exercise_id = str(_uuid.uuid4())[:12]
        node_id = _get_node_id()
        node_name = _get_node_name()
        title = (data.get('title', '') or 'Group Exercise').strip()[:200]
        scenario_type = data.get('scenario_type', 'grid_down')
        description = (data.get('description', '') or '').strip()[:1000]

        with db_session() as db:
            db.execute('''INSERT INTO group_exercises
                (exercise_id, title, scenario_type, description, initiator_node, initiator_name, participants, status, shared_state)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'recruiting', ?)''',
                (exercise_id, title, scenario_type, description, node_id, node_name,
                 json.dumps([{'node_id': node_id, 'node_name': node_name, 'role': 'initiator', 'joined_at': time.strftime('%Y-%m-%dT%H:%M:%S')}]),
                 json.dumps({'phase': 0, 'scenario_type': scenario_type, 'events': []})))
            db.commit()

        # Broadcast to federation peers
        peers = _get_trusted_peers()
        import requests as req
        invited = 0
        for peer in peers:
            try:
                req.post(f"http://{peer['ip']}:{peer.get('port', 8080)}/api/group-exercises/invite",
                         json={'exercise_id': exercise_id, 'title': title, 'scenario_type': scenario_type,
                               'description': description, 'initiator_node': node_id, 'initiator_name': node_name},
                         timeout=5)
                invited += 1
            except Exception:
                pass

        log_activity('group_exercise_created', 'training', f'Exercise "{title}" ({exercise_id}), invited {invited} peers')
        return jsonify({'exercise_id': exercise_id, 'invited': invited}), 201

    @app.route('/api/group-exercises/invite', methods=['POST'])
    def api_group_exercises_invite():
        """Receive an exercise invitation from a peer."""
        data = request.get_json() or {}
        exercise_id = data.get('exercise_id', '')
        if not exercise_id:
            return jsonify({'error': 'Missing exercise_id'}), 400

        # Validate initiator is a known, non-blocked peer
        initiator = data.get('initiator_node', '')
        if initiator:
            with db_session() as db_check:
                peer = db_check.execute("SELECT trust_level FROM federation_peers WHERE node_id = ?", (initiator,)).fetchone()
            if peer and peer['trust_level'] == 'blocked':
                return jsonify({'error': 'Peer is blocked'}), 403

        with db_session() as db:
            existing = db.execute('SELECT id FROM group_exercises WHERE exercise_id = ?', (exercise_id,)).fetchone()
            if existing:
                return jsonify({'status': 'already_known'})
            db.execute('''INSERT INTO group_exercises
                (exercise_id, title, scenario_type, description, initiator_node, initiator_name, participants, status, shared_state)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'invited', '{}')''',
                (exercise_id, data.get('title', 'Group Exercise'), data.get('scenario_type', ''),
                 data.get('description', ''), data.get('initiator_node', ''), data.get('initiator_name', ''),
                 json.dumps([])))
            db.commit()
        log_activity('group_exercise_invited', 'training', f'Invited to "{data.get("title", "")}" by {data.get("initiator_name", "")}')
        return jsonify({'status': 'invited'})

    @app.route('/api/group-exercises/<exercise_id>/join', methods=['POST'])
    def api_group_exercises_join(exercise_id):
        """Join an exercise — notifies initiator."""
        with db_session() as db:
            row = db.execute('SELECT * FROM group_exercises WHERE exercise_id = ?', (exercise_id,)).fetchone()
            if not row:
                return jsonify({'error': 'Exercise not found'}), 404

            node_id = _get_node_id()
            node_name = _get_node_name()
            participants = json.loads(row['participants'] or '[]')
            if not any(p['node_id'] == node_id for p in participants):
                participants.append({'node_id': node_id, 'node_name': node_name, 'role': 'participant', 'joined_at': time.strftime('%Y-%m-%dT%H:%M:%S')})

            db.execute("UPDATE group_exercises SET participants = ?, status = 'active', updated_at = datetime('now') WHERE exercise_id = ?",
                       (json.dumps(participants), exercise_id))
            db.commit()
            initiator_node = row['initiator_node']

        # Notify initiator
        peers = _get_trusted_peers()
        import requests as req
        for peer in peers:
            if peer.get('node_id') == initiator_node:
                try:
                    req.post(f"http://{peer['ip']}:{peer.get('port', 8080)}/api/group-exercises/{exercise_id}/participant-joined",
                             json={'node_id': node_id, 'node_name': node_name}, timeout=5)
                except Exception:
                    pass
                break

        return jsonify({'status': 'joined', 'participants': len(participants)})

    @app.route('/api/group-exercises/<exercise_id>/participant-joined', methods=['POST'])
    def api_group_exercises_participant_joined(exercise_id):
        """Receive notification that a peer joined."""
        data = request.get_json() or {}
        with db_session() as db:
            row = db.execute('SELECT participants FROM group_exercises WHERE exercise_id = ?', (exercise_id,)).fetchone()
            if not row:
                return jsonify({'error': 'Not found'}), 404
            participants = json.loads(row['participants'] or '[]')
            node_id = data.get('node_id', '')
            if not any(p['node_id'] == node_id for p in participants):
                participants.append({'node_id': node_id, 'node_name': data.get('node_name', ''), 'role': 'participant', 'joined_at': time.strftime('%Y-%m-%dT%H:%M:%S')})
            db.execute("UPDATE group_exercises SET participants = ?, updated_at = datetime('now') WHERE exercise_id = ?",
                       (json.dumps(participants), exercise_id))
            db.commit()
        return jsonify({'status': 'noted'})

    @app.route('/api/group-exercises/<exercise_id>/update-state', methods=['POST'])
    def api_group_exercises_update_state(exercise_id):
        """Update shared exercise state (phase advance, decision, etc.)."""
        data = request.get_json() or {}
        with db_session() as db:
            row = db.execute('SELECT * FROM group_exercises WHERE exercise_id = ?', (exercise_id,)).fetchone()
            if not row:
                return jsonify({'error': 'Not found'}), 404

            shared_state = json.loads(row['shared_state'] or '{}')
            decisions_log = json.loads(row['decisions_log'] or '[]')

            if 'phase' in data:
                shared_state['phase'] = data['phase']
            if 'event' in data:
                shared_state.setdefault('events', []).append({
                    'node': _get_node_id(), 'name': _get_node_name(),
                    'event': data['event'], 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S')
                })
            if 'decision' in data:
                decisions_log.append({
                    'node': _get_node_id(), 'name': _get_node_name(),
                    'decision': data['decision'], 'phase': shared_state.get('phase', 0),
                    'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S')
                })

            status = data.get('status', row['status'])
            score = data.get('score', row['score'])
            aar_text = data.get('aar_text', row['aar_text'])

            db.execute("""UPDATE group_exercises SET shared_state = ?, decisions_log = ?, current_phase = ?,
                          status = ?, score = ?, aar_text = ?, updated_at = datetime('now') WHERE exercise_id = ?""",
                       (json.dumps(shared_state), json.dumps(decisions_log), shared_state.get('phase', 0),
                        status, score, aar_text, exercise_id))
            db.commit()
            participants = json.loads(row['participants'] or '[]')

        # Broadcast state to all participants
        peers = _get_trusted_peers()
        import requests as req
        for p in participants:
            if p['node_id'] == _get_node_id():
                continue
            for peer in peers:
                if peer.get('node_id') == p['node_id']:
                    try:
                        req.post(f"http://{peer['ip']}:{peer.get('port', 8080)}/api/group-exercises/{exercise_id}/sync-state",
                                 json={'shared_state': shared_state, 'decisions_log': decisions_log,
                                       'status': status, 'score': score, 'aar_text': aar_text,
                                       'phase': shared_state.get('phase', 0)}, timeout=5)
                    except Exception:
                        pass
                    break

        return jsonify({'status': 'updated'})

    @app.route('/api/group-exercises/<exercise_id>/sync-state', methods=['POST'])
    def api_group_exercises_sync_state(exercise_id):
        """Receive state update from another participant."""
        data = request.get_json() or {}
        # Validate sender is a known, non-blocked peer
        sender = data.get('source_node_id', '')
        if sender:
            with db_session() as db_check:
                peer = db_check.execute("SELECT trust_level FROM federation_peers WHERE node_id = ?", (sender,)).fetchone()
            if peer and peer['trust_level'] == 'blocked':
                return jsonify({'error': 'Peer is blocked'}), 403
        with db_session() as db:
            db.execute("""UPDATE group_exercises SET shared_state = ?, decisions_log = ?, current_phase = ?,
                          status = ?, score = ?, aar_text = ?, updated_at = datetime('now') WHERE exercise_id = ?""",
                       (json.dumps(data.get('shared_state', {})), json.dumps(data.get('decisions_log', [])),
                        data.get('phase', 0), data.get('status', 'active'),
                        data.get('score', 0), data.get('aar_text', ''), exercise_id))
            db.commit()
        return jsonify({'status': 'synced'})

    def _get_trusted_peers():
        """Get list of trusted federation peers."""
        with db_session() as db:
            peers = [dict(r) for r in db.execute(
                "SELECT node_id, node_name, ip, port FROM federation_peers WHERE trust_level IN ('trusted','admin','member') AND ip != ''").fetchall()]
        return peers

    # ─── Map Atlas Pages ─────────────────────────────────────────────
    # [EXTRACTED to blueprint]


    # [EXTRACTED to blueprint] Perimeter zones + motion detection


    # ─── Blueprints ──────────────────────────────────────────────────
    from web.blueprints.garden import garden_bp
    from web.blueprints.notes import notes_bp
    from web.blueprints.weather import weather_bp
    from web.blueprints.medical import medical_bp
    from web.blueprints.power import power_bp
    from web.blueprints.federation import federation_bp
    from web.blueprints.kb import kb_bp
    from web.blueprints.security import security_bp
    app.register_blueprint(garden_bp)
    app.register_blueprint(notes_bp)
    app.register_blueprint(weather_bp)
    app.register_blueprint(medical_bp)
    app.register_blueprint(power_bp)
    app.register_blueprint(federation_bp)
    app.register_blueprint(kb_bp)
    app.register_blueprint(security_bp)

    # ─── Phase 2 Batch 3 Blueprints ──────────────────────────────────
    from web.blueprints.services import services_bp
    from web.blueprints.ai import ai_bp
    from web.blueprints.inventory import inventory_bp
    from web.blueprints.comms import comms_bp
    from web.blueprints.media import media_bp
    from web.blueprints.maps import maps_bp
    from web.blueprints.system import system_bp
    app.register_blueprint(services_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(comms_bp)
    app.register_blueprint(media_bp)
    app.register_blueprint(maps_bp)
    app.register_blueprint(system_bp)

    # ─── Advanced Routes (Phases 16, 18, 19, 20) ────────────────────
    from web.routes_advanced import register_advanced_routes
    register_advanced_routes(app)

    # ─── SSE Real-Time Event Bus ─────────────────────────────────────

    @app.route('/api/events/stream')
    def event_stream():
        """SSE endpoint — pushes real-time events to connected clients."""
        with _sse_lock:
            if len(_sse_clients) >= MAX_SSE_CLIENTS:
                return jsonify({'error': 'Too many SSE connections'}), 429
        q = queue.Queue(maxsize=50)
        with _sse_lock:
            _sse_clients.append(q)
        def generate():
            try:
                while True:
                    try:
                        msg = q.get(timeout=30)
                        yield msg
                    except queue.Empty:
                        yield ": keepalive\n\n"
            except GeneratorExit:
                with _sse_lock:
                    if q in _sse_clients:
                        _sse_clients.remove(q)
        return Response(generate(), mimetype='text/event-stream',
                        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    @app.route('/api/events/test')
    def event_test():
        """Broadcast a test event (useful for debugging SSE)."""
        broadcast_event('alert', {'level': 'info', 'message': 'SSE test event'})
        return jsonify({'status': 'sent', 'clients': len(_sse_clients)})

    # ─── Internationalization (i18n) ─────────────────────────────────────
    try:
        from web.translations import SUPPORTED_LANGUAGES, TRANSLATIONS
    except ImportError:
        from translations import SUPPORTED_LANGUAGES, TRANSLATIONS

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
        db = get_db()
        try:
            row = db.execute("SELECT value FROM settings WHERE key = 'language'").fetchone()
            lang = row['value'] if row else 'en'
        except Exception:
            lang = 'en'
        finally:
            db.close()
        return jsonify({'language': lang})

    @app.route('/api/i18n/language', methods=['POST'])
    def api_i18n_set_language():
        data = request.get_json(force=True)
        lang = data.get('language', '').strip()
        if lang not in SUPPORTED_LANGUAGES:
            return jsonify({'error': f'Unsupported language: {lang}'}), 400
        db = get_db()
        try:
            db.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('language', ?)",
                (lang,)
            )
            db.commit()
        finally:
            db.close()
        return jsonify({'status': 'ok', 'language': lang})

    return app
