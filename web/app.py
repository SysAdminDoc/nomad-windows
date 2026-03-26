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
from flask import Flask, render_template, jsonify, request, Response
from werkzeug.utils import secure_filename

from config import get_data_dir, set_data_dir
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
from db import get_db, log_activity
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

VERSION = '4.1.0'


def set_version(v):
    global VERSION
    import re
    # Sanitize to prevent XSS — version must be semver-like (digits, dots, hyphens, letters)
    VERSION = re.sub(r'[^a-zA-Z0-9.\-+]', '', str(v)) or '0.0.0'

# RAG / Knowledge Base state
# Note: _embed_state is mutated from background threads. Individual dict mutations
# (assignment, .update()) are atomic under CPython's GIL for simple cases.
_embed_state = {'status': 'idle', 'doc_id': None, 'progress': 0, 'detail': ''}
EMBED_MODEL = 'nomic-embed-text:v1.5'
CHUNK_SIZE = 500  # approximate tokens per chunk
CHUNK_OVERLAP = 50

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

threading.Thread(target=_cpu_monitor, daemon=True).start()


def create_app():
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')

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
            return jsonify({'error': str(e)}), status
        # Non-API routes: re-raise to let Flask's default handler render HTML
        raise e

    @app.errorhandler(404)
    def handle_404(e):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Not found'}), 404
        return e

    # ─── LAN Auth Guard ────────────────────────────────────────────────
    # Protect dangerous endpoints from unauthorized LAN access
    PROTECTED_ENDPOINTS = {
        'api_system_shutdown', 'api_sync_export', 'api_export_all',
        'api_export_config', 'api_uninstall_service',
    }

    @app.before_request
    def check_lan_auth():
        """Block protected endpoints from non-localhost requests when auth is enabled."""
        if request.endpoint not in PROTECTED_ENDPOINTS:
            return
        remote = request.remote_addr or ''
        if remote in ('127.0.0.1', '::1', 'localhost'):
            return
        # LAN request — check if auth is enabled and validate
        try:
            db = get_db()
            try:
                row = db.execute("SELECT value FROM settings WHERE key = 'auth_password'").fetchone()
            finally:
                db.close()
            if row and row['value']:
                import hashlib
                token = request.headers.get('X-Auth-Token', '')
                if hashlib.sha256(token.encode()).hexdigest() != row['value']:
                    return jsonify({'error': 'Authentication required'}), 403
        except Exception as e:
            log.warning(f'Auth check failed (denying access): {e}')
            return jsonify({'error': 'Authentication check failed'}), 503

    @app.after_request
    def no_cache(response):
        """Prevent WebView2 from caching HTML/API responses."""
        if 'text/html' in response.content_type or 'application/json' in response.content_type:
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response

    # ─── Pages ─────────────────────────────────────────────────────────

    @app.route('/')
    def dashboard():
        return render_template('index.html', version=VERSION)

    # ─── Service API ───────────────────────────────────────────────────

    @app.route('/api/services')
    def api_services():
        services = []
        for sid, mod in SERVICE_MODULES.items():
            installed = mod.is_installed()
            install_dir = os.path.join(get_services_dir(), sid)
            disk_used = format_size(get_dir_size(install_dir)) if installed else '0 B'

            port_val = getattr(mod, f'{sid.upper()}_PORT', None)
            if port_val is None:
                for attr in ['OLLAMA_PORT', 'KIWIX_PORT', 'CYBERCHEF_PORT', 'KOLIBRI_PORT', 'QDRANT_PORT', 'STIRLING_PORT']:
                    port_val = getattr(mod, attr, None)
                    if port_val:
                        break

            services.append({
                'id': sid,
                'name': getattr(mod, 'SERVICE_ID', sid),
                'installed': installed,
                'running': mod.running() if installed else False,
                'port': port_val,
                'progress': get_download_progress(sid),
                'disk_used': disk_used,
            })
        return jsonify(services)

    _installing = set()
    _installing_lock = threading.Lock()

    @app.route('/api/services/<service_id>/install', methods=['POST'])
    def api_install_service(service_id):
        mod = SERVICE_MODULES.get(service_id)
        if not mod:
            return jsonify({'error': 'Unknown service'}), 404
        if mod.is_installed():
            return jsonify({'status': 'already_installed'})
        with _installing_lock:
            if service_id in _installing:
                return jsonify({'status': 'already_installing'})
            _installing.add(service_id)

        def do_install():
            try:
                mod.install()
            except Exception as e:
                log.error(f'Install failed for {service_id}: {e}')
            finally:
                _installing.discard(service_id)

        threading.Thread(target=do_install, daemon=True).start()
        return jsonify({'status': 'installing'})

    @app.route('/api/services/<service_id>/start', methods=['POST'])
    def api_start_service(service_id):
        mod = SERVICE_MODULES.get(service_id)
        if not mod:
            return jsonify({'error': 'Unknown service'}), 404
        if not mod.is_installed():
            return jsonify({'error': 'Not installed'}), 400
        try:
            # Start dependencies first
            deps_started = ensure_dependencies(service_id, SERVICE_MODULES)
            mod.start()
            result = {'status': 'started'}
            if deps_started:
                result['dependencies_started'] = deps_started
            return jsonify(result)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/services/<service_id>/stop', methods=['POST'])
    def api_stop_service(service_id):
        mod = SERVICE_MODULES.get(service_id)
        if not mod:
            return jsonify({'error': 'Unknown service'}), 404
        try:
            mod.stop()
            return jsonify({'status': 'stopped'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/services/<service_id>/restart', methods=['POST'])
    def api_restart_service(service_id):
        mod = SERVICE_MODULES.get(service_id)
        if not mod:
            return jsonify({'error': 'Unknown service'}), 404
        try:
            mod.stop()
            time.sleep(1)
            mod.start()
            return jsonify({'status': 'restarted'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/services/<service_id>/uninstall', methods=['POST'])
    def api_uninstall_service(service_id):
        if service_id not in SERVICE_MODULES:
            return jsonify({'error': 'Unknown service'}), 404
        try:
            uninstall_service(service_id)
            return jsonify({'status': 'uninstalled'})
        except Exception as e:
            log.error(f'Uninstall failed for {service_id}: {e}')
            return jsonify({'error': str(e)}), 500

    @app.route('/api/services/start-all', methods=['POST'])
    def api_start_all():
        started = []
        errors = []
        for sid, mod in SERVICE_MODULES.items():
            if mod.is_installed() and not mod.running():
                try:
                    mod.start()
                    started.append(sid)
                except Exception as e:
                    errors.append(f'{sid}: {e}')
        return jsonify({'started': started, 'errors': errors})

    @app.route('/api/services/stop-all', methods=['POST'])
    def api_stop_all():
        stopped = []
        errors = []
        for sid, mod in SERVICE_MODULES.items():
            if mod.is_installed() and mod.running():
                try:
                    mod.stop()
                    stopped.append(sid)
                except Exception as e:
                    errors.append(f'{sid}: {e}')
                    log.error(f'Stop failed for {sid}: {e}')
        return jsonify({'stopped': stopped, 'errors': errors})

    @app.route('/api/services/<service_id>/progress')
    def api_service_progress(service_id):
        return jsonify(get_download_progress(service_id))

    @app.route('/api/services/<service_id>/prereqs')
    def api_service_prereqs(service_id):
        """Check prerequisites for a service. All prerequisites auto-install if missing."""
        if service_id == 'stirling':
            java = stirling._find_java()
            return jsonify({'met': True, 'java_found': java is not None, 'java_path': java,
                            'message': None if java else 'Java will be auto-installed on first use (~50 MB download)'})
        if service_id == 'kolibri':
            try:
                py = kolibri._python_exe()
                return jsonify({'met': True, 'python_found': True, 'message': None})
            except RuntimeError:
                return jsonify({'met': True, 'python_found': False,
                                'message': 'Python will be auto-installed on first use (~15 MB download)'})
        return jsonify({'met': True, 'message': None})

    # ─── Ollama AI Chat API ───────────────────────────────────────────

    @app.route('/api/ai/models')
    def api_ai_models():
        if not ollama.is_installed() or not ollama.running():
            return jsonify([])
        return jsonify(ollama.list_models())

    _pull_queue = []
    _pull_queue_active = False
    _pull_queue_lock = threading.Lock()

    @app.route('/api/ai/pull', methods=['POST'])
    def api_ai_pull():
        data = request.get_json() or {}
        model_name = data.get('model', ollama.DEFAULT_MODEL)

        def do_pull():
            ollama.pull_model(model_name)

        threading.Thread(target=do_pull, daemon=True).start()
        return jsonify({'status': 'pulling', 'model': model_name})

    @app.route('/api/ai/pull-queue', methods=['POST'])
    def api_ai_pull_queue():
        """Queue multiple models for sequential download."""
        nonlocal _pull_queue_active
        data = request.get_json() or {}
        models = data.get('models', [])
        if not models:
            return jsonify({'error': 'No models specified'}), 400
        # Filter out already-installed models
        try:
            installed = set(m['name'] for m in ollama.list_models())
        except Exception:
            installed = set()
        to_pull = [m for m in models if m not in installed]
        if not to_pull:
            return jsonify({'status': 'all_installed', 'count': 0})
        with _pull_queue_lock:
            if _pull_queue_active:
                return jsonify({'error': 'A download queue is already running. Wait for it to finish.'}), 409
            _pull_queue.clear()
            _pull_queue.extend(to_pull)
            _pull_queue_active = True

        def do_queue():
            nonlocal _pull_queue_active
            try:
                for i, model_name in enumerate(to_pull):
                    ollama._pull_progress = {
                        'status': 'pulling', 'model': model_name, 'percent': 0,
                        'detail': f'Queue: {i+1}/{len(to_pull)} — Starting {model_name}...',
                        'queue_pos': i + 1, 'queue_total': len(to_pull),
                    }
                    ollama.pull_model(model_name)
                    # Wait for pull to finish
                    for _ in range(7200):
                        p = ollama.get_pull_progress()
                        if p.get('status') in ('complete', 'error', 'idle'):
                            break
                        time.sleep(1)
            finally:
                with _pull_queue_lock:
                    _pull_queue.clear()
                    _pull_queue_active = False

        threading.Thread(target=do_queue, daemon=True).start()
        return jsonify({'status': 'queued', 'count': len(to_pull), 'models': to_pull})

    @app.route('/api/ai/pull-progress')
    def api_ai_pull_progress():
        progress = ollama.get_pull_progress()
        progress['queue'] = list(_pull_queue)
        progress['queue_active'] = _pull_queue_active
        return jsonify(progress)

    @app.route('/api/ai/delete', methods=['POST'])
    def api_ai_delete():
        data = request.get_json() or {}
        model_name = data.get('model')
        if not model_name:
            return jsonify({'error': 'No model specified'}), 400
        success = ollama.delete_model(model_name)
        if not success:
            return jsonify({'error': 'Failed to delete model'}), 500
        return jsonify({'status': 'deleted'})

    # ─── Shared AI context builder ──────────────────────────────────
    def _safe_json_list(val, default=None):
        """Parse a JSON string, returning default on failure."""
        if default is None:
            default = []
        try:
            return json.loads(val or '[]')
        except (json.JSONDecodeError, TypeError):
            return default

    def build_situation_context(db) -> list[str]:
        """Build rich situation context from DB for AI consumption.
        Returns a list of context section strings."""
        ctx_parts = []

        # Inventory with burn rates
        inv = db.execute('SELECT name, quantity, unit, category, daily_usage, min_quantity, expiration FROM inventory ORDER BY category, name LIMIT 200').fetchall()
        if inv:
            inv_lines = []
            for r in inv:
                line = f'{r["name"]}: {r["quantity"]} {r["unit"]} ({r["category"]})'
                if r['daily_usage'] and r['daily_usage'] > 0:
                    days = round(r['quantity'] / r['daily_usage'], 1)
                    line += f' — {days} days supply at {r["daily_usage"]}/day'
                if r['min_quantity'] and r['quantity'] <= r['min_quantity']:
                    line += ' [LOW STOCK]'
                if r['expiration']:
                    line += f' expires {r["expiration"]}'
                inv_lines.append(line)
            ctx_parts.append('INVENTORY:\n' + '\n'.join(inv_lines))

        # Contacts with skills and roles
        contacts = db.execute('SELECT name, role, skills, phone, callsign, blood_type FROM contacts LIMIT 50').fetchall()
        if contacts:
            c_lines = [f'{c["name"]} — {c["role"] or "unassigned"}' +
                       (f', skills: {c["skills"]}' if c.get('skills') else '') +
                       (f', callsign: {c["callsign"]}' if c.get('callsign') else '') +
                       (f', blood: {c["blood_type"]}' if c.get('blood_type') else '')
                       for c in contacts]
            ctx_parts.append('TEAM CONTACTS:\n' + '\n'.join(c_lines))

        # Patients with medical details
        patients = db.execute('SELECT name, age, weight_kg, blood_type, allergies, conditions, medications FROM patients LIMIT 20').fetchall()
        if patients:
            p_lines = []
            for p in patients:
                line = f'{p["name"]}'
                if p['age']: line += f', age {p["age"]}'
                if p['blood_type']: line += f', blood {p["blood_type"]}'
                allg = _safe_json_list(p['allergies'])
                if allg: line += f', ALLERGIES: {", ".join(allg)}'
                cond = _safe_json_list(p['conditions'])
                if cond: line += f', conditions: {", ".join(cond)}'
                meds = _safe_json_list(p['medications'])
                if meds: line += f', meds: {", ".join(meds)}'
                p_lines.append(line)
            ctx_parts.append('PATIENTS:\n' + '\n'.join(p_lines))

        # Fuel storage
        fuel = db.execute('SELECT fuel_type, quantity, unit, location FROM fuel_storage').fetchall()
        if fuel:
            ctx_parts.append('FUEL: ' + ', '.join(f'{f["fuel_type"]}: {f["quantity"]} {f["unit"]} at {f["location"]}' for f in fuel))

        # Ammo
        ammo = db.execute('SELECT caliber, quantity, location FROM ammo_inventory').fetchall()
        if ammo:
            ctx_parts.append('AMMO: ' + ', '.join(f'{a["caliber"]}: {a["quantity"]} rounds ({a["location"]})' for a in ammo))

        # Equipment
        equip = db.execute("SELECT name, status, next_service FROM equipment_log WHERE next_service != '' ORDER BY next_service LIMIT 10").fetchall()
        if equip:
            ctx_parts.append('EQUIPMENT: ' + ', '.join(f'{e["name"]}: {e["status"]}, service due {e["next_service"]}' for e in equip))

        # Active alerts
        alerts = db.execute('SELECT title, severity, message FROM alerts WHERE dismissed = 0 LIMIT 10').fetchall()
        if alerts:
            ctx_parts.append('ACTIVE ALERTS:\n' + '\n'.join(f'[{a["severity"]}] {a["title"]}: {a["message"][:100]}' for a in alerts))

        # Weather
        wx = db.execute('SELECT * FROM weather_log ORDER BY created_at DESC LIMIT 1').fetchone()
        if wx:
            ctx_parts.append(f'WEATHER: {dict(wx)}')

        # Power
        pwr = db.execute('SELECT * FROM power_log ORDER BY created_at DESC LIMIT 1').fetchone()
        if pwr:
            ctx_parts.append(f'POWER: Battery {pwr["battery_soc"] or "?"}%, Solar {pwr["solar_watts"] or 0}W, Load {pwr["load_watts"] or 0}W')

        # Recent incidents
        incidents = db.execute("SELECT severity, category, description FROM incidents WHERE created_at >= datetime('now', '-24 hours') ORDER BY created_at DESC LIMIT 5").fetchall()
        if incidents:
            ctx_parts.append('RECENT INCIDENTS (24h): ' + ' | '.join(f'[{r["severity"]}] {r["category"]}: {r["description"][:60]}' for r in incidents))

        return ctx_parts

    def get_ai_memory_text() -> str:
        """Load AI memory facts from settings, return formatted string or empty."""
        try:
            mem_db = get_db()
            try:
                mem_row = mem_db.execute("SELECT value FROM settings WHERE key = 'ai_memory'").fetchone()
            finally:
                mem_db.close()
            if mem_row and mem_row['value']:
                memories = json.loads(mem_row['value'])
                if memories:
                    lines = '\n'.join(f'- {m["fact"] if isinstance(m, dict) else m}' for m in memories)
                    return f'\n\n--- OPERATOR NOTES ---\n{lines}\n--- END NOTES ---'
        except Exception:
            pass
        return ''

    @app.route('/api/ai/chat', methods=['POST'])
    def api_ai_chat():
        data = request.get_json() or {}
        model = data.get('model', ollama.DEFAULT_MODEL)
        messages = data.get('messages', [])
        system_prompt = data.get('system_prompt', '')
        use_kb = data.get('knowledge_base', False)

        if not ollama.running():
            return jsonify({'error': 'Ollama is not running'}), 503

        # Situation-aware context injection
        use_situation = data.get('situation_context', False)
        if use_situation:
            db_ctx = None
            try:
                db_ctx = get_db()
                sit_parts = []
                # Inventory summary
                inv_rows = db_ctx.execute('SELECT category, SUM(quantity) as qty, COUNT(*) as cnt FROM inventory GROUP BY category').fetchall()
                if inv_rows:
                    sit_parts.append('SUPPLY INVENTORY: ' + ', '.join(f'{r["category"]}: {r["cnt"]} items ({r["qty"]} total)' for r in inv_rows))
                # Low stock
                low = db_ctx.execute('SELECT name, quantity, unit, category FROM inventory WHERE quantity <= min_quantity AND min_quantity > 0 LIMIT 10').fetchall()
                if low:
                    sit_parts.append('LOW STOCK ALERTS: ' + ', '.join(f'{r["name"]} ({r["quantity"]} {r["unit"]})' for r in low))
                # Burn rate
                burn = db_ctx.execute('SELECT name, quantity, daily_usage, category FROM inventory WHERE daily_usage > 0 LIMIT 10').fetchall()
                if burn:
                    sit_parts.append('BURN RATES: ' + ', '.join(f'{r["name"]}: {round(r["quantity"]/max(r["daily_usage"],0.001),1)} days left' for r in burn))
                # Contacts count
                ct_count = db_ctx.execute('SELECT COUNT(*) as c FROM contacts').fetchone()['c']
                if ct_count:
                    sit_parts.append(f'TEAM: {ct_count} contacts registered')
                # Recent incidents
                incidents = db_ctx.execute("SELECT severity, category, description FROM incidents WHERE created_at >= datetime('now', '-24 hours') ORDER BY created_at DESC LIMIT 5").fetchall()
                if incidents:
                    sit_parts.append('RECENT INCIDENTS (24h): ' + ' | '.join(f'[{r["severity"]}] {r["category"]}: {r["description"][:60]}' for r in incidents))
                # Situation board
                settings_row = db_ctx.execute("SELECT value FROM settings WHERE key = 'sit_board'").fetchone()
                if settings_row:
                    try:
                        sit = json.loads(settings_row['value'] or '{}')
                        sit_parts.append('SITUATION STATUS: ' + ', '.join(f'{k}: {v}' for k, v in sit.items()))
                    except (json.JSONDecodeError, TypeError): pass
                # Weather
                wx = db_ctx.execute('SELECT pressure_hpa, temp_f, created_at FROM weather_log WHERE pressure_hpa IS NOT NULL ORDER BY created_at DESC LIMIT 1').fetchone()
                if wx:
                    sit_parts.append(f'WEATHER: {wx["pressure_hpa"]} hPa, {wx["temp_f"]}F (as of {wx["created_at"]})')
                # Active alerts
                alerts = db_ctx.execute('SELECT title, severity FROM alerts WHERE dismissed = 0 ORDER BY severity DESC LIMIT 5').fetchall()
                if alerts:
                    sit_parts.append('ACTIVE ALERTS: ' + ' | '.join(f'[{a["severity"]}] {a["title"]}' for a in alerts))
                # Power status
                pwr = db_ctx.execute('SELECT battery_soc, solar_watts, load_watts FROM power_log ORDER BY created_at DESC LIMIT 1').fetchone()
                if pwr:
                    sit_parts.append(f'POWER: Battery {pwr["battery_soc"] or "?"}%, Solar {pwr["solar_watts"] or 0}W, Load {pwr["load_watts"] or 0}W')
                # Patients with conditions
                patients = db_ctx.execute('SELECT name, allergies, conditions FROM patients LIMIT 5').fetchall()
                if patients:
                    def _safe_json(val):
                        try: return json.loads(val or '[]')
                        except (json.JSONDecodeError, TypeError): return []
                    pt_str = ', '.join(f'{p["name"]} (allergies: {_safe_json(p["allergies"])}, conditions: {_safe_json(p["conditions"])})' for p in patients)
                    sit_parts.append(f'PATIENTS: {pt_str}')
                # Garden/harvest
                harvest_count = db_ctx.execute('SELECT COUNT(*) as c FROM harvest_log').fetchone()['c']
                if harvest_count:
                    sit_parts.append(f'GARDEN: {harvest_count} harvests logged')
                if sit_parts:
                    ctx = '\n'.join(sit_parts)
                    system_prompt = (system_prompt + '\n\n' if system_prompt else '') + \
                        f'You have access to the user\'s current preparedness data. Use this to give specific, actionable advice based on their actual situation:\n\n--- Current Situation ---\n{ctx}\n--- End Situation ---'
            except Exception as e:
                log.warning(f'Situation context injection failed: {e}')
            finally:
                if db_ctx:
                    try: db_ctx.close()
                    except Exception: pass

        # RAG: inject knowledge base context if enabled
        if use_kb and qdrant.running() and messages:
            last_user_msg = next((m['content'] for m in reversed(messages) if m['role'] == 'user'), '')
            if last_user_msg:
                try:
                    vectors = embed_text([last_user_msg], prefix='search_query: ')
                    if vectors:
                        results = qdrant.search(vectors[0], limit=4)
                        if results:
                            context_parts = [r.get('payload', {}).get('text', '') for r in results if r.get('score', 0) > 0.3]
                            if context_parts:
                                kb_context = '\n\n---\n\n'.join(context_parts)
                                system_prompt = (system_prompt + '\n\n' if system_prompt else '') + \
                                    f'Use the following knowledge base context to help answer the question. If the context is not relevant, ignore it.\n\n--- Knowledge Base ---\n{kb_context}\n--- End Knowledge Base ---'
                except Exception as e:
                    log.warning(f'RAG context injection failed: {e}')

        # AI Memory: inject persistent facts the user has stored
        try:
            mem_db = get_db()
            try:
                mem_row = mem_db.execute("SELECT value FROM settings WHERE key = 'ai_memory'").fetchone()
            finally:
                mem_db.close()
            if mem_row and mem_row['value']:
                memories = json.loads(mem_row['value'])
                if memories:
                    mem_text = '\n'.join(f'- {m["fact"] if isinstance(m, dict) else m}' for m in memories)
                    system_prompt = (system_prompt + '\n\n' if system_prompt else '') + \
                        f'Important context the user has asked you to remember:\n{mem_text}'
        except Exception as e:
            log.warning(f'AI memory injection failed: {e}')

        if system_prompt:
            messages = [{'role': 'system', 'content': system_prompt}] + messages

        def generate():
            try:
                for line in ollama.chat(model, messages, stream=True):
                    if line:
                        yield line.decode('utf-8') + '\n'
            except Exception as e:
                yield json.dumps({'error': str(e)}) + '\n'

        return Response(generate(), mimetype='text/event-stream')

    @app.route('/api/ai/quick-query', methods=['POST'])
    def api_ai_quick_query():
        """Answer a focused question using real data without full chat context.
        Designed for the dashboard copilot widget."""
        data = request.get_json() or {}
        question = data.get('question', '').strip()
        if not question:
            return jsonify({'error': 'No question'}), 400
        if not ollama.running():
            return jsonify({'error': 'AI service not running'}), 503

        # Build rich data context from DB using shared helper
        db = get_db()
        try:
            ctx_parts = build_situation_context(db)
        finally:
            db.close()

        context = '\n\n'.join(ctx_parts) if ctx_parts else 'No data has been entered yet.'
        memory_text = get_ai_memory_text()

        system = f"""You are the N.O.M.A.D. Survival Operations Copilot — an AI embedded in a tactical preparedness command center. Your role is to provide actionable intelligence based on the operator's REAL supply data, team roster, medical records, and equipment status.

RULES:
- Answer using ONLY the data below. Never fabricate items, quantities, or people.
- Use exact names, quantities, and numbers from the data.
- If a supply has daily_usage, calculate and report days remaining.
- Flag anything critical: items below 7 days supply, expired items, overdue equipment.
- Keep responses concise (2-4 sentences). Be direct — this is an ops brief, not a conversation.
- If asked about something not in the data, say "No data available for that" — don't guess.

--- OPERATOR'S LIVE DATA ---
{context}
--- END DATA ---{memory_text}"""

        try:
            model = data.get('model', ollama.DEFAULT_MODEL)
            result = ollama.chat(model, [{'role': 'system', 'content': system}, {'role': 'user', 'content': question}], stream=False)
            response_text = result.get('message', {}).get('content', '') if isinstance(result, dict) else ''
            return jsonify({'answer': response_text.strip(), 'data_sources': list(set(p.split(':')[0] for p in ctx_parts))})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/ai/suggested-actions')
    def api_ai_suggested_actions():
        """Generate suggested actions based on current alerts and data state."""
        db = get_db()
        try:
            suggestions = []
            from datetime import datetime, timedelta
            today = datetime.now().strftime('%Y-%m-%d')
            soon7 = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
            soon30 = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

            # Low stock items
            low = db.execute('SELECT name, quantity, unit FROM inventory WHERE quantity <= min_quantity AND min_quantity > 0 LIMIT 3').fetchall()
            for r in low:
                suggestions.append({'type': 'warning', 'action': f'Restock {r["name"]} — only {r["quantity"]} {r["unit"]} remaining', 'module': 'inventory'})

            # Expiring items (7 days)
            expiring = db.execute("SELECT name, expiration FROM inventory WHERE expiration != '' AND expiration <= ? AND expiration >= ? LIMIT 3", (soon7, today)).fetchall()
            for r in expiring:
                suggestions.append({'type': 'urgent', 'action': f'Rotate {r["name"]} — expires {r["expiration"]}', 'module': 'inventory'})

            # Equipment overdue
            overdue = db.execute("SELECT name, next_service FROM equipment_log WHERE next_service != '' AND next_service <= ? LIMIT 3", (today,)).fetchall()
            for r in overdue:
                suggestions.append({'type': 'warning', 'action': f'Service {r["name"]} — overdue since {r["next_service"]}', 'module': 'equipment'})

            # Unresolved critical alerts
            crit = db.execute("SELECT title FROM alerts WHERE dismissed = 0 AND severity = 'critical' LIMIT 3").fetchall()
            for r in crit:
                suggestions.append({'type': 'critical', 'action': f'Resolve alert: {r["title"]}', 'module': 'alerts'})

            # Fuel expiring
            fuel_exp = db.execute("SELECT fuel_type, expires FROM fuel_storage WHERE expires != '' AND expires <= ? LIMIT 2", (soon30,)).fetchall()
            for r in fuel_exp:
                suggestions.append({'type': 'warning', 'action': f'Rotate {r["fuel_type"]} fuel — expires {r["expires"]}', 'module': 'fuel'})

            return jsonify({'suggestions': suggestions[:8]})
        finally:
            db.close()

    @app.route('/api/ai/recommended')
    def api_ai_recommended():
        return jsonify(ollama.RECOMMENDED_MODELS)

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

    # ─── Notes API ─────────────────────────────────────────────────────

    @app.route('/api/notes')
    def api_notes_list():
        db = get_db()
        try:
            notes = db.execute('SELECT * FROM notes ORDER BY pinned DESC, updated_at DESC').fetchall()
        finally:
            db.close()
        return jsonify([dict(n) for n in notes])

    @app.route('/api/notes', methods=['POST'])
    def api_notes_create():
        data = request.get_json() or {}
        db = get_db()
        try:
            cur = db.execute('INSERT INTO notes (title, content) VALUES (?, ?)',
                             (data.get('title', 'Untitled'), data.get('content', '')))
            db.commit()
            note_id = cur.lastrowid
            note = db.execute('SELECT * FROM notes WHERE id = ?', (note_id,)).fetchone()
            return jsonify(dict(note)), 201
        finally:
            db.close()

    @app.route('/api/notes/<int:note_id>', methods=['PUT'])
    def api_notes_update(note_id):
        data = request.get_json() or {}
        db = get_db()
        try:
            current = db.execute('SELECT title, content FROM notes WHERE id = ?', (note_id,)).fetchone()
            if not current:
                return jsonify({'error': 'Not found'}), 404
            title = data.get('title') if data.get('title') is not None else current['title']
            content = data.get('content') if data.get('content') is not None else current['content']
            db.execute('UPDATE notes SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                       (title, content, note_id))
            db.commit()
            note = db.execute('SELECT * FROM notes WHERE id = ?', (note_id,)).fetchone()
            return jsonify(dict(note))
        finally:
            db.close()

    @app.route('/api/notes/<int:note_id>', methods=['DELETE'])
    def api_notes_delete(note_id):
        db = get_db()
        try:
            db.execute('DELETE FROM notes WHERE id = ?', (note_id,))
            db.commit()
            return jsonify({'status': 'deleted'})
        finally:
            db.close()

    # ─── Settings API ─────────────────────────────────────────────────

    @app.route('/api/settings')
    def api_settings():
        db = get_db()
        try:
            rows = db.execute('SELECT key, value FROM settings').fetchall()
        finally:
            db.close()
        return jsonify({r['key']: r['value'] for r in rows})

    SETTINGS_WHITELIST = {
        'dashboard_mode', 'node_name', 'node_id', 'theme', 'sidebar_collapsed',
        'map_style', 'map_center', 'map_zoom', 'ai_model', 'ai_system_prompt',
        'ai_memory_enabled', 'ai_memory', 'wizard_tier', 'first_run_complete',
        'lan_name', 'lan_sharing', 'lan_password_enabled',
    }

    @app.route('/api/settings', methods=['PUT'])
    def api_settings_update():
        data = request.get_json() or {}
        db = get_db()
        try:
            rejected = []
            for key, value in data.items():
                if key not in SETTINGS_WHITELIST:
                    rejected.append(key)
                    continue
                db.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, str(value)))
            db.commit()
        finally:
            db.close()
        if rejected:
            return jsonify({'status': 'partial', 'rejected_keys': rejected}), 400
        return jsonify({'status': 'saved'})

    # ─── Dashboard Mode API ──────────────────────────────────────────
    DASHBOARD_MODES = {
        'command': {
            'label': 'Command Center',
            'desc': 'Full military-style ops dashboard — all modules, threat-level focus',
            'icon': '&#9876;',
            'sidebar_order': ['services','ai','library','maps','notes','media','tools','prep','benchmark','settings'],
            'sidebar_hide': [],
            'prep_order': ['inventory','contacts','checklists','medical','incidents','family','security','power','garden','weather','guides','calculators','protocols','radio','reference','signals','ops','journal','vault','skills','ammo','community','radiation','fuel','equipment'],
            'dashboard_widgets': ['readiness','alerts','inventory-burn','security','comms','power','weather','incidents'],
        },
        'homestead': {
            'label': 'Homestead',
            'desc': 'Farm & self-reliance focus — garden, livestock, weather, food production',
            'icon': '&#127793;',
            'sidebar_order': ['services','ai','library','maps','notes','media','prep','tools','settings'],
            'sidebar_hide': ['benchmark'],
            'prep_order': ['garden','weather','power','equipment','fuel','inventory','checklists','medical','contacts','skills','community','family','journal','calculators','protocols','radio','reference','signals','ops','vault','ammo','incidents','security','radiation'],
            'dashboard_widgets': ['readiness','garden','weather','power','inventory-burn','livestock','equipment','alerts'],
        },
        'minimal': {
            'label': 'Essentials',
            'desc': 'Streamlined — only core survival modules',
            'icon': '&#9679;',
            'sidebar_order': ['services','ai','notes','media','prep','settings'],
            'sidebar_hide': ['library','maps','tools','benchmark'],
            'prep_order': ['inventory','contacts','medical','checklists','family','incidents','guides','calculators','reference'],
            'prep_hide': ['signals','ops','vault','skills','ammo','community','radiation','fuel','equipment','garden','weather','power','security','protocols','radio','journal'],
            'dashboard_widgets': ['readiness','alerts','inventory-burn'],
        },
    }

    @app.route('/api/dashboard/mode')
    def api_dashboard_mode():
        db = get_db()
        try:
            row = db.execute("SELECT value FROM settings WHERE key = 'dashboard_mode'").fetchone()
        finally:
            db.close()
        mode = row['value'] if row else 'command'
        if mode not in DASHBOARD_MODES:
            mode = 'command'
        return jsonify({'mode': mode, 'config': DASHBOARD_MODES[mode], 'available': {k: {'label': v['label'], 'desc': v['desc'], 'icon': v['icon']} for k, v in DASHBOARD_MODES.items()}})

    @app.route('/api/settings/wizard-complete', methods=['POST'])
    def api_wizard_complete():
        db = get_db()
        try:
            db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('first_run_complete', '1')")
            db.commit()
        finally:
            db.close()
        return jsonify({'status': 'ok'})

    # ─── Drives API ───────────────────────────────────────────────────

    @app.route('/api/drives')
    def api_drives():
        """List available drives with free space for storage picker."""
        import psutil
        drives = []
        try:
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    drives.append({
                        'path': part.mountpoint,
                        'device': part.device,
                        'fstype': part.fstype,
                        'total': usage.total,
                        'free': usage.free,
                        'used': usage.used,
                        'percent': usage.percent,
                        'total_str': format_size(usage.total),
                        'free_str': format_size(usage.free),
                    })
                except Exception:
                    pass
        except Exception:
            pass
        return jsonify(drives)

    @app.route('/api/settings/data-dir', methods=['POST'])
    def api_set_data_dir():
        """Set custom data directory (wizard only)."""
        data = request.get_json() or {}
        path = data.get('path', '')
        if not path:
            return jsonify({'error': 'No path provided'}), 400
        try:
            full_path = os.path.join(path, 'ProjectNOMAD')
            os.makedirs(full_path, exist_ok=True)
            # Test write
            test_file = os.path.join(full_path, '.write_test')
            with open(test_file, 'w') as f:
                f.write('ok')
            os.remove(test_file)
            set_data_dir(full_path)
            return jsonify({'status': 'ok', 'path': full_path})
        except Exception as e:
            return jsonify({'error': f'Cannot write to {path}: {e}'}), 400

    # ─── Wizard Setup API ─────────────────────────────────────────────

    _wizard_state = {'status': 'idle', 'phase': '', 'current_item': '', 'item_progress': 0,
                     'overall_progress': 0, 'completed': [], 'errors': [], 'total_items': 0}

    @app.route('/api/wizard/setup', methods=['POST'])
    def api_wizard_setup():
        """Full turnkey setup — installs services, downloads content, pulls models."""
        data = request.get_json() or {}
        services_list = data.get('services', ['ollama', 'kiwix', 'cyberchef', 'stirling'])
        zims = data.get('zims', [])
        models = data.get('models', ['llama3.2:3b'])

        def do_setup():
            total = len(services_list) + len(zims) + len(models)
            _wizard_state.update({'status': 'running', 'phase': 'services', 'completed': [],
                                  'errors': [], 'total_items': total, 'overall_progress': 0})
            done = 0

            # Phase 1: Install services
            for sid in services_list:
                mod = SERVICE_MODULES.get(sid)
                if not mod:
                    continue
                _wizard_state.update({'current_item': f'Installing {SVC_FRIENDLY.get(sid, sid)}', 'item_progress': 0})
                try:
                    if not mod.is_installed():
                        mod.install()
                        # Wait for install to complete
                        import time
                        for _ in range(300):
                            p = get_download_progress(sid)
                            _wizard_state['item_progress'] = p.get('percent', 0)
                            if p.get('status') in ('complete', 'error'):
                                break
                            time.sleep(1)
                        if get_download_progress(sid).get('status') == 'error':
                            err_msg = get_download_progress(sid).get("error", "unknown")
                            _wizard_state['errors'].append(f'{sid}: Download failed — {err_msg}. You can retry from the Home tab.')
                except Exception as e:
                    _wizard_state['errors'].append(f'{sid}: Setup failed — check your internet connection and try again from the Home tab.')
                done += 1
                _wizard_state['overall_progress'] = int(done / total * 100) if total > 0 else 100
                _wizard_state['completed'].append(sid)

            # Phase 2: Start services that CAN start now (skip Kiwix — needs content first)
            _wizard_state['phase'] = 'starting'
            import time
            for sid in services_list:
                if sid == 'kiwix':
                    continue  # Kiwix needs ZIM files before it can start — handled after downloads
                mod = SERVICE_MODULES.get(sid)
                if mod and mod.is_installed() and not mod.running():
                    _wizard_state['current_item'] = f'Starting {SVC_FRIENDLY.get(sid, sid)}...'
                    try:
                        mod.start()
                        time.sleep(2)
                    except Exception as e:
                        # Non-fatal — service may need prerequisites, will auto-start later
                        log.warning(f'Wizard: non-fatal start error for {sid}: {e}')

            # Phase 3: Download ZIM content
            if zims:
                _wizard_state['phase'] = 'content'
                for zim in zims:
                    url = zim.get('url', '')
                    filename = zim.get('filename', '')
                    name = zim.get('name', filename)
                    _wizard_state.update({'current_item': f'Downloading {name}', 'item_progress': 0})
                    try:
                        kiwix.download_zim(url, filename)
                        # Poll progress
                        prog_key = f'kiwix-zim-{filename}'
                        for _ in range(7200):  # up to 2 hours per ZIM
                            p = get_download_progress(prog_key)
                            _wizard_state['item_progress'] = p.get('percent', 0)
                            if p.get('status') in ('complete', 'error'):
                                break
                            time.sleep(1)
                    except Exception as e:
                        _wizard_state['errors'].append(f'ZIM {filename}: {e}')
                    done += 1
                    _wizard_state['overall_progress'] = int(done / total * 100) if total > 0 else 100
                    _wizard_state['completed'].append(filename)

                # NOW start Kiwix — it has content to serve
                _wizard_state['current_item'] = 'Starting Kiwix with downloaded content...'
                if kiwix.is_installed():
                    try:
                        if kiwix.running():
                            kiwix.stop()
                            time.sleep(1)
                        kiwix.start()
                    except Exception as e:
                        log.warning(f'Wizard: Kiwix start after content: {e}')
            elif 'kiwix' in services_list:
                # No ZIMs selected but Kiwix installed — note it needs content
                _wizard_state['current_item'] = 'Kiwix installed (add content from Library tab to start it)'

            # Phase 4: Pull AI models
            if models:
                _wizard_state['phase'] = 'models'
                for model_name in models:
                    _wizard_state.update({'current_item': f'Downloading AI model: {model_name}', 'item_progress': 0})
                    try:
                        if not ollama.running():
                            _wizard_state['errors'].append(f'Model {model_name}: Skipped — AI service is not running. Start it from the Services tab and download models from AI Chat.')
                        else:
                            ollama.pull_model(model_name)
                            # Poll pull progress
                            for _ in range(3600):
                                p = ollama.get_pull_progress()
                                _wizard_state['item_progress'] = p.get('percent', 0)
                                if p.get('status') in ('complete', 'error'):
                                    break
                                time.sleep(1)
                    except Exception as e:
                        _wizard_state['errors'].append(f'Model {model_name}: {e}')
                    done += 1
                    _wizard_state['overall_progress'] = int(done / total * 100) if total > 0 else 100
                    _wizard_state['completed'].append(model_name)

            # Mark wizard complete
            db = get_db()
            try:
                db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('first_run_complete', '1')")
                db.commit()
            finally:
                db.close()

            _wizard_state.update({'status': 'complete', 'phase': 'done', 'overall_progress': 100,
                                  'current_item': 'Setup complete!'})

        threading.Thread(target=do_setup, daemon=True).start()
        return jsonify({'status': 'started'})

    @app.route('/api/wizard/progress')
    def api_wizard_progress():
        return jsonify(_wizard_state)

    @app.route('/api/content-tiers')
    def api_content_tiers():
        """Return content tier definitions with sizes for wizard."""
        tiers = kiwix.get_content_tiers()
        return jsonify(tiers)

    SVC_FRIENDLY = {
        'ollama': 'AI Chat', 'kiwix': 'Offline Encyclopedia', 'cyberchef': 'Data Toolkit',
        'kolibri': 'Education Platform', 'qdrant': 'Document Search', 'stirling': 'PDF Tools',
        'flatnotes': 'Notes App',
    }

    # ─── System Info ───────────────────────────────────────────────────

    @app.route('/api/system')
    def api_system():
        import psutil
        data_dir = get_data_dir()
        total_disk = get_dir_size(data_dir)

        try:
            disk = shutil.disk_usage(data_dir)
            disk_free = disk.free
            disk_total = disk.total
        except Exception:
            disk_free = 0
            disk_total = 0

        try:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            cpu_count = psutil.cpu_count()
            cpu_count_phys = psutil.cpu_count(logical=False)
            cpu_name = platform.processor()
            cpu_percent = _cpu_percent  # non-blocking, from background monitor
        except Exception:
            mem = swap = None
            cpu_count = os.cpu_count()
            cpu_count_phys = cpu_count
            cpu_name = platform.processor()
            cpu_percent = 0

        # GPU detection (cross-platform via platform_utils)
        from platform_utils import detect_gpu as _detect_gpu
        _gpu = _detect_gpu()
        gpu_name = _gpu.get('name', 'None detected')
        gpu_vram = f'{_gpu["vram_mb"]} MB' if _gpu.get('vram_mb') else ''

        # Disk partitions
        disk_devices = []
        try:
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    disk_devices.append({
                        'device': part.device,
                        'mountpoint': part.mountpoint,
                        'fstype': part.fstype,
                        'total': format_size(usage.total),
                        'used': format_size(usage.used),
                        'free': format_size(usage.free),
                        'percent': usage.percent,
                    })
                except Exception:
                    pass
        except Exception:
            pass

        # Uptime
        try:
            uptime_secs = time.time() - psutil.boot_time()
            days = int(uptime_secs // 86400)
            hours = int((uptime_secs % 86400) // 3600)
            mins = int((uptime_secs % 3600) // 60)
            uptime_str = f'{days}d {hours}h {mins}m' if days else f'{hours}h {mins}m'
        except Exception:
            uptime_str = 'Unknown'

        return jsonify({
            'version': VERSION,
            'platform': f'{platform.system()} {platform.release()}',
            'os_version': platform.version(),
            'hostname': platform.node(),
            'arch': platform.machine(),
            'cpu': cpu_name or f'{cpu_count} cores',
            'cpu_cores': cpu_count,
            'cpu_cores_physical': cpu_count_phys,
            'cpu_percent': cpu_percent,
            'ram_total': format_size(mem.total) if mem else 'Unknown',
            'ram_used': format_size(mem.used) if mem else 'Unknown',
            'ram_available': format_size(mem.available) if mem else 'Unknown',
            'ram_percent': mem.percent if mem else 0,
            'swap_total': format_size(swap.total) if swap else '0 B',
            'swap_used': format_size(swap.used) if swap else '0 B',
            'swap_percent': swap.percent if swap else 0,
            'gpu': gpu_name,
            'gpu_vram': gpu_vram,
            'data_dir': data_dir,
            'nomad_disk_used': format_size(total_disk),
            'disk_free': format_size(disk_free),
            'disk_free_bytes': disk_free,
            'disk_total': format_size(disk_total),
            'disk_devices': disk_devices,
            'uptime': uptime_str,
        })

    @app.route('/api/system/live')
    def api_system_live():
        """Lightweight live metrics for real-time gauges."""
        import psutil
        try:
            return jsonify({
                'cpu_percent': _cpu_percent,  # non-blocking, from background monitor
                'ram_percent': psutil.virtual_memory().percent,
                'swap_percent': psutil.swap_memory().percent,
            })
        except Exception:
            return jsonify({'cpu_percent': 0, 'ram_percent': 0, 'swap_percent': 0})

    # ─── Conversations API ────────────────────────────────────────────

    @app.route('/api/conversations')
    def api_conversations_list():
        db = get_db()
        try:
            convos = db.execute('SELECT id, title, model, created_at, updated_at FROM conversations ORDER BY updated_at DESC').fetchall()
        finally:
            db.close()
        return jsonify([dict(c) for c in convos])

    @app.route('/api/conversations', methods=['POST'])
    def api_conversations_create():
        data = request.get_json() or {}
        db = get_db()
        try:
            cur = db.execute('INSERT INTO conversations (title, model, messages) VALUES (?, ?, ?)',
                             (data.get('title', 'New Chat'), data.get('model', ''), '[]'))
            db.commit()
            cid = cur.lastrowid
            convo = db.execute('SELECT * FROM conversations WHERE id = ?', (cid,)).fetchone()
        finally:
            db.close()
        return jsonify(dict(convo)), 201

    @app.route('/api/conversations/<int:cid>')
    def api_conversations_get(cid):
        db = get_db()
        try:
            convo = db.execute('SELECT * FROM conversations WHERE id = ?', (cid,)).fetchone()
        finally:
            db.close()
        if not convo:
            return jsonify({'error': 'Not found'}), 404
        return jsonify(dict(convo))

    @app.route('/api/conversations/<int:cid>', methods=['PUT'])
    def api_conversations_update(cid):
        data = request.get_json() or {}
        db = get_db()
        try:
            fields = []
            vals = []
            if 'title' in data:
                fields.append('title = ?')
                vals.append(data['title'])
            if 'model' in data:
                fields.append('model = ?')
                vals.append(data['model'])
            if 'messages' in data:
                fields.append('messages = ?')
                vals.append(json.dumps(data['messages']))
            fields.append('updated_at = CURRENT_TIMESTAMP')
            vals.append(cid)
            db.execute(f'UPDATE conversations SET {", ".join(fields)} WHERE id = ?', vals)
            db.commit()
        finally:
            db.close()
        return jsonify({'status': 'saved'})

    @app.route('/api/conversations/<int:cid>', methods=['PATCH'])
    def api_conversation_rename(cid):
        data = request.get_json() or {}
        title = data.get('title', '').strip()
        if not title:
            return jsonify({'error': 'Title required'}), 400
        db = get_db()
        try:
            db.execute('UPDATE conversations SET title = ? WHERE id = ?', (title, cid))
            db.commit()
        finally:
            db.close()
        return jsonify({'status': 'renamed'})

    @app.route('/api/conversations/<int:cid>', methods=['DELETE'])
    def api_conversations_delete(cid):
        db = get_db()
        try:
            db.execute('DELETE FROM conversations WHERE id = ?', (cid,))
            db.commit()
        finally:
            db.close()
        return jsonify({'status': 'deleted'})

    @app.route('/api/conversations/all', methods=['DELETE'])
    def api_conversations_delete_all():
        db = get_db()
        try:
            db.execute('DELETE FROM conversations')
            db.commit()
        finally:
            db.close()
        return jsonify({'status': 'deleted'})

    @app.route('/api/conversations/search')
    def api_conversations_search():
        q = request.args.get('q', '').strip()
        if not q:
            return jsonify([])
        # Escape LIKE wildcard characters to prevent unintended pattern matching
        q_escaped = q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        db = get_db()
        try:
            rows = db.execute(
                "SELECT id, title, model, created_at FROM conversations WHERE title LIKE ? ESCAPE '\\' OR messages LIKE ? ESCAPE '\\' ORDER BY updated_at DESC LIMIT 20",
                (f'%{q_escaped}%', f'%{q_escaped}%')
            ).fetchall()
        finally:
            db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/conversations/<int:cid>/export')
    def api_conversations_export(cid):
        db = get_db()
        try:
            convo = db.execute('SELECT * FROM conversations WHERE id = ?', (cid,)).fetchone()
        finally:
            db.close()
        if not convo:
            return jsonify({'error': 'Not found'}), 404
        messages = json.loads(convo['messages'] or '[]')
        md = f"# {convo['title']}\n\n"
        md += f"*Model: {convo['model'] or 'Unknown'} | {convo['created_at']}*\n\n---\n\n"
        for m in messages:
            role = 'You' if m['role'] == 'user' else 'AI'
            md += f"**{role}:**\n\n{m.get('content', '')}\n\n---\n\n"
        safe_title = ''.join(c for c in (convo['title'] or 'export') if c.isalnum() or c in ' _-').strip() or 'export'
        return Response(md, mimetype='text/markdown',
                       headers={'Content-Disposition': f'attachment; filename="{safe_title}.md"'})

    # ─── Unified Search API ────────────────────────────────────────────

    @app.route('/api/content-summary')
    def api_content_summary():
        """Human-readable summary of offline knowledge capacity."""
        db = get_db()
        try:
            row = db.execute('''SELECT
                (SELECT COUNT(*) FROM conversations) as convos,
                (SELECT COUNT(*) FROM notes) as notes,
                (SELECT COUNT(*) FROM documents WHERE status = 'ready') as docs,
                (SELECT COALESCE(SUM(chunks_count), 0) FROM documents WHERE status = 'ready') as chunks
            ''').fetchone()
            convo_count, note_count, doc_count, doc_chunks = row['convos'], row['notes'], row['docs'], row['chunks']
        finally:
            db.close()

        # Disk usage
        data_dir = get_data_dir()
        total_bytes = get_dir_size(data_dir)

        # ZIM count and size
        zim_count = 0
        zim_bytes = 0
        if kiwix.is_installed():
            zims = kiwix.list_zim_files()
            zim_count = len(zims)
            zim_bytes = sum(z['size_mb'] * 1024 * 1024 for z in zims)

        # Model count
        model_count = 0
        if ollama.is_installed() and ollama.running():
            try:
                model_count = len(ollama.list_models())
            except Exception:
                pass

        return jsonify({
            'total_size': format_size(total_bytes),
            'total_bytes': total_bytes,
            'conversations': convo_count,
            'notes': note_count,
            'documents': doc_count,
            'document_chunks': doc_chunks,
            'zim_files': zim_count,
            'zim_size': format_size(int(zim_bytes)),
            'ai_models': model_count,
        })

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
        limit = request.args.get('limit', 20, type=int)
        db = get_db()
        try:
            if test_type:
                rows = db.execute('SELECT * FROM benchmark_results WHERE test_type = ? ORDER BY created_at DESC LIMIT ?', (test_type, limit)).fetchall()
            else:
                rows = db.execute('SELECT * FROM benchmark_results ORDER BY created_at DESC LIMIT ?', (limit,)).fetchall()
            return jsonify([dict(r) for r in rows])
        finally:
            db.close()

    # ─── Maps API ──────────────────────────────────────────────────────

    MAPS_DIR_NAME = 'maps'

    def get_maps_dir():
        path = os.path.join(get_data_base(), 'ProjectNOMAD', MAPS_DIR_NAME)
        os.makedirs(path, exist_ok=True)
        return path

    MAP_REGIONS = [
        # US Regions — bbox = [west, south, east, north]
        {'id': 'us-pacific', 'name': 'US Pacific', 'states': 'AK, CA, HI, OR, WA', 'bbox': [-180, 18, -100, 72]},
        {'id': 'us-mountain', 'name': 'US Mountain', 'states': 'AZ, CO, ID, MT, NV, NM, UT, WY', 'bbox': [-117, 31, -102, 49]},
        {'id': 'us-west-north-central', 'name': 'US West North Central', 'states': 'IA, KS, MN, MO, NE, ND, SD', 'bbox': [-104.1, 36, -89.1, 49]},
        {'id': 'us-east-north-central', 'name': 'US East North Central', 'states': 'IL, IN, MI, OH, WI', 'bbox': [-91.5, 36.9, -80.5, 48.3]},
        {'id': 'us-west-south-central', 'name': 'US West South Central', 'states': 'AR, LA, OK, TX', 'bbox': [-106.7, 25.8, -88.8, 37]},
        {'id': 'us-east-south-central', 'name': 'US East South Central', 'states': 'AL, KY, MS, TN', 'bbox': [-91.7, 30, -81.9, 39.2]},
        {'id': 'us-south-atlantic', 'name': 'US South Atlantic', 'states': 'DE, FL, GA, MD, NC, SC, VA, DC, WV', 'bbox': [-84.4, 24.4, -75, 39.8]},
        {'id': 'us-middle-atlantic', 'name': 'US Middle Atlantic', 'states': 'NJ, NY, PA', 'bbox': [-80.6, 38.8, -71.8, 45.1]},
        {'id': 'us-new-england', 'name': 'US New England', 'states': 'CT, ME, MA, NH, RI, VT', 'bbox': [-73.8, 40.9, -66.9, 47.5]},
        # International Regions
        {'id': 'eu-western', 'name': 'Western Europe', 'states': 'UK, France, Germany, Netherlands, Belgium', 'bbox': [-11, 42, 15, 61]},
        {'id': 'eu-eastern', 'name': 'Eastern Europe', 'states': 'Poland, Czech, Romania, Hungary, Ukraine', 'bbox': [14, 43, 41, 55]},
        {'id': 'eu-southern', 'name': 'Southern Europe', 'states': 'Spain, Italy, Portugal, Greece, Turkey', 'bbox': [-10, 34, 45, 48]},
        {'id': 'eu-northern', 'name': 'Northern Europe', 'states': 'Sweden, Norway, Finland, Denmark, Iceland', 'bbox': [-25, 54, 32, 72]},
        {'id': 'canada', 'name': 'Canada', 'states': 'All provinces and territories', 'bbox': [-141, 41.7, -52, 84]},
        {'id': 'mexico-central', 'name': 'Mexico & Central America', 'states': 'Mexico, Guatemala, Belize, Honduras', 'bbox': [-118, 13, -82, 33]},
        {'id': 'south-america', 'name': 'South America', 'states': 'Brazil, Argentina, Colombia, Chile, Peru', 'bbox': [-82, -56, -34, 13]},
        {'id': 'east-asia', 'name': 'East Asia', 'states': 'Japan, South Korea, Taiwan', 'bbox': [120, 20, 154, 46]},
        {'id': 'southeast-asia', 'name': 'Southeast Asia', 'states': 'Philippines, Thailand, Vietnam, Indonesia', 'bbox': [92, -11, 141, 29]},
        {'id': 'oceania', 'name': 'Australia & New Zealand', 'states': 'Australia, New Zealand, Pacific Islands', 'bbox': [110, -48, 180, -9]},
        {'id': 'middle-east', 'name': 'Middle East', 'states': 'Israel, Jordan, UAE, Saudi Arabia, Iraq', 'bbox': [25, 12, 60, 42]},
        {'id': 'africa-north', 'name': 'North Africa', 'states': 'Egypt, Morocco, Tunisia, Libya, Algeria', 'bbox': [-18, 15, 37, 38]},
        {'id': 'africa-sub', 'name': 'Sub-Saharan Africa', 'states': 'South Africa, Kenya, Nigeria, Ethiopia', 'bbox': [-18, -35, 52, 15]},
    ]

    # ─── Alternative Map Sources ─────────────────────────────────────
    # Sources that can be downloaded for offline map usage
    MAP_SOURCES = [
        # === PMTiles (native format — works directly with MapLibre viewer) ===
        {'id': 'protomaps-planet', 'name': 'Protomaps World Basemap', 'category': 'PMTiles',
         'url': 'https://data.source.coop/protomaps/openstreetmap/v4.pmtiles', 'format': 'pmtiles', 'est_size': '~120 GB',
         'desc': 'Full planet vector tiles (v4). Source Cooperative mirror. The definitive offline map source.', 'direct': True},
        {'id': 'openfreemap-planet', 'name': 'OpenFreeMap Planet', 'category': 'PMTiles',
         'url': 'https://openfreemap.com/', 'format': 'pmtiles', 'est_size': '~80 GB',
         'desc': 'Free, open-source planet tiles. Self-hostable.'},
        {'id': 'overture-maps', 'name': 'Overture Maps', 'category': 'PMTiles',
         'url': 'https://overturemaps.org/download/', 'format': 'pmtiles', 'est_size': 'Varies',
         'desc': 'Open map data from Meta, Microsoft, AWS, TomTom. Buildings, places, roads.'},
        {'id': 'source-coop', 'name': 'Source Cooperative Maps', 'category': 'PMTiles',
         'url': 'https://source.coop/', 'format': 'pmtiles', 'est_size': 'Varies',
         'desc': 'Community-hosted geospatial datasets in PMTiles and other formats.'},
        {'id': 'mapterhorn-terrain', 'name': 'Mapterhorn Terrain Tiles', 'category': 'PMTiles',
         'url': 'https://download.mapterhorn.com/planet.pmtiles', 'format': 'pmtiles', 'est_size': '~30 GB',
         'desc': 'Global terrain/elevation tiles in PMTiles format.', 'direct': True},

        # === OSM Extracts (PBF — need conversion to PMTiles via tilemaker or planetiler) ===
        {'id': 'geofabrik-na', 'name': 'Geofabrik: North America', 'category': 'OSM Extracts',
         'url': 'https://download.geofabrik.de/north-america-latest.osm.pbf', 'format': 'pbf', 'est_size': '~13 GB',
         'desc': 'Full North America OSM data. Requires conversion to PMTiles.', 'direct': True},
        {'id': 'geofabrik-us', 'name': 'Geofabrik: United States', 'category': 'OSM Extracts',
         'url': 'https://download.geofabrik.de/north-america/us-latest.osm.pbf', 'format': 'pbf', 'est_size': '~9 GB',
         'desc': 'Complete US OSM data. Updated daily.', 'direct': True},
        {'id': 'geofabrik-europe', 'name': 'Geofabrik: Europe', 'category': 'OSM Extracts',
         'url': 'https://download.geofabrik.de/europe-latest.osm.pbf', 'format': 'pbf', 'est_size': '~28 GB',
         'desc': 'Full Europe OSM data. Very detailed.', 'direct': True},
        {'id': 'geofabrik-asia', 'name': 'Geofabrik: Asia', 'category': 'OSM Extracts',
         'url': 'https://download.geofabrik.de/asia-latest.osm.pbf', 'format': 'pbf', 'est_size': '~12 GB',
         'desc': 'Full Asia OSM data.', 'direct': True},
        {'id': 'geofabrik-africa', 'name': 'Geofabrik: Africa', 'category': 'OSM Extracts',
         'url': 'https://download.geofabrik.de/africa-latest.osm.pbf', 'format': 'pbf', 'est_size': '~6 GB',
         'desc': 'Full Africa OSM data.', 'direct': True},
        {'id': 'geofabrik-sa', 'name': 'Geofabrik: South America', 'category': 'OSM Extracts',
         'url': 'https://download.geofabrik.de/south-america-latest.osm.pbf', 'format': 'pbf', 'est_size': '~3 GB',
         'desc': 'Full South America OSM data.', 'direct': True},
        {'id': 'geofabrik-oceania', 'name': 'Geofabrik: Australia & Oceania', 'category': 'OSM Extracts',
         'url': 'https://download.geofabrik.de/australia-oceania-latest.osm.pbf', 'format': 'pbf', 'est_size': '~1 GB',
         'desc': 'Australia, NZ, Pacific Islands OSM data.', 'direct': True},
        {'id': 'geofabrik-ca', 'name': 'Geofabrik: Central America', 'category': 'OSM Extracts',
         'url': 'https://download.geofabrik.de/central-america-latest.osm.pbf', 'format': 'pbf', 'est_size': '~600 MB',
         'desc': 'Central America and Caribbean OSM data.', 'direct': True},
        {'id': 'geofabrik-russia', 'name': 'Geofabrik: Russia', 'category': 'OSM Extracts',
         'url': 'https://download.geofabrik.de/russia-latest.osm.pbf', 'format': 'pbf', 'est_size': '~3 GB',
         'desc': 'Full Russia OSM data.', 'direct': True},
        {'id': 'geofabrik-canada', 'name': 'Geofabrik: Canada', 'category': 'OSM Extracts',
         'url': 'https://download.geofabrik.de/north-america/canada-latest.osm.pbf', 'format': 'pbf', 'est_size': '~3 GB',
         'desc': 'Complete Canada OSM data.', 'direct': True},
        {'id': 'geofabrik-planet', 'name': 'Geofabrik: Full Planet', 'category': 'OSM Extracts',
         'url': 'https://planet.openstreetmap.org/pbf/planet-latest.osm.pbf', 'format': 'pbf', 'est_size': '~70 GB',
         'desc': 'Complete OpenStreetMap planet data. Official source.', 'direct': True},

        # === Geofabrik US States ===
        {'id': 'geofabrik-us-california', 'name': 'Geofabrik: California', 'category': 'US States (OSM)',
         'url': 'https://download.geofabrik.de/north-america/us/california-latest.osm.pbf', 'format': 'pbf', 'est_size': '~1 GB',
         'desc': 'California OSM data.', 'direct': True},
        {'id': 'geofabrik-us-texas', 'name': 'Geofabrik: Texas', 'category': 'US States (OSM)',
         'url': 'https://download.geofabrik.de/north-america/us/texas-latest.osm.pbf', 'format': 'pbf', 'est_size': '~700 MB',
         'desc': 'Texas OSM data.', 'direct': True},
        {'id': 'geofabrik-us-florida', 'name': 'Geofabrik: Florida', 'category': 'US States (OSM)',
         'url': 'https://download.geofabrik.de/north-america/us/florida-latest.osm.pbf', 'format': 'pbf', 'est_size': '~400 MB',
         'desc': 'Florida OSM data.', 'direct': True},
        {'id': 'geofabrik-us-newyork', 'name': 'Geofabrik: New York', 'category': 'US States (OSM)',
         'url': 'https://download.geofabrik.de/north-america/us/new-york-latest.osm.pbf', 'format': 'pbf', 'est_size': '~400 MB',
         'desc': 'New York OSM data.', 'direct': True},
        {'id': 'geofabrik-us-pennsylvania', 'name': 'Geofabrik: Pennsylvania', 'category': 'US States (OSM)',
         'url': 'https://download.geofabrik.de/north-america/us/pennsylvania-latest.osm.pbf', 'format': 'pbf', 'est_size': '~350 MB',
         'desc': 'Pennsylvania OSM data.', 'direct': True},

        # === Topographic / Elevation Data ===
        {'id': 'usgs-national-map', 'name': 'USGS National Map', 'category': 'Topographic',
         'url': 'https://apps.nationalmap.gov/downloader/', 'format': 'various',
         'est_size': 'Varies', 'desc': 'US topographic maps, elevation, hydrography, boundaries.'},
        {'id': 'opentopo', 'name': 'OpenTopography', 'category': 'Topographic',
         'url': 'https://opentopography.org/', 'format': 'various',
         'est_size': 'Varies', 'desc': 'High-res topography data. LiDAR, DEMs, point clouds.'},
        {'id': 'viewfinderpanoramas', 'name': 'Viewfinder Panoramas DEMs', 'category': 'Topographic',
         'url': 'http://viewfinderpanoramas.org/dem3.html', 'format': 'hgt',
         'est_size': 'Varies', 'desc': '3 arc-second DEMs for the entire world. Great for terrain.'},
        {'id': 'srtm', 'name': 'SRTM Elevation (NASA)', 'category': 'Topographic',
         'url': 'https://dwtkns.com/srtm30m/', 'format': 'hgt',
         'est_size': 'Varies', 'desc': '30m resolution elevation data. Free with EarthData login.'},

        # === Natural Earth (small, low-detail reference maps) ===
        {'id': 'natural-earth-110m', 'name': 'Natural Earth 1:110m', 'category': 'Reference Maps',
         'url': 'https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip', 'format': 'shp', 'est_size': '~800 KB',
         'desc': 'World country boundaries. Very small, great for overview maps.', 'direct': True},
        {'id': 'natural-earth-50m', 'name': 'Natural Earth 1:50m', 'category': 'Reference Maps',
         'url': 'https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip', 'format': 'shp', 'est_size': '~5 MB',
         'desc': 'Medium-detail world boundaries and features.', 'direct': True},
        {'id': 'natural-earth-10m', 'name': 'Natural Earth 1:10m (Full)', 'category': 'Reference Maps',
         'url': 'https://naciscdn.org/naturalearth/packages/natural_earth_vector.gpkg.zip', 'format': 'gpkg', 'est_size': '~240 MB',
         'desc': 'Highest detail Natural Earth data in single GeoPackage.', 'direct': True},

        # === Humanitarian / Emergency Maps ===
        {'id': 'hot-export', 'name': 'HOT Export Tool', 'category': 'Humanitarian',
         'url': 'https://export.hotosm.org/', 'format': 'various',
         'est_size': 'Varies', 'desc': 'Humanitarian OpenStreetMap Team. Custom area exports for disaster response.'},
        {'id': 'hdx', 'name': 'Humanitarian Data Exchange', 'category': 'Humanitarian',
         'url': 'https://data.humdata.org/', 'format': 'various',
         'est_size': 'Varies', 'desc': 'UN OCHA humanitarian datasets. Population, infrastructure, health facilities.'},
        {'id': 'fieldpapers', 'name': 'Field Papers', 'category': 'Humanitarian',
         'url': 'http://fieldpapers.org/', 'format': 'pdf',
         'est_size': 'Varies', 'desc': 'Printable map atlases for field surveys. Works completely offline.'},

        # === BBBike City Extracts ===
        {'id': 'bbbike', 'name': 'BBBike Extracts (200+ Cities)', 'category': 'City Extracts',
         'url': 'https://extract.bbbike.org/', 'format': 'various',
         'est_size': 'Varies', 'desc': 'Custom city/area extracts in PBF, GeoJSON, Shapefile, etc.'},
        {'id': 'bbbike-download', 'name': 'BBBike Pre-built Cities', 'category': 'City Extracts',
         'url': 'https://download.bbbike.org/osm/bbbike/', 'format': 'pbf',
         'est_size': 'Varies', 'desc': 'Pre-built extracts for 200+ world cities. Updated weekly.'},

        # === Nautical / Aviation ===
        {'id': 'noaa-charts', 'name': 'NOAA Nautical Charts', 'category': 'Specialty',
         'url': 'https://charts.noaa.gov/ChartCatalog/MapSelect.html', 'format': 'pdf/bsb',
         'est_size': 'Varies', 'desc': 'US coastal and inland waterway navigation charts.'},
        {'id': 'faa-sectionals', 'name': 'FAA Sectional Charts', 'category': 'Specialty',
         'url': 'https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/vfr/', 'format': 'pdf/tiff',
         'est_size': 'Varies', 'desc': 'US VFR sectional aeronautical charts.'},

        # === Weather / Climate ===
        {'id': 'worldclim', 'name': 'WorldClim Climate Data', 'category': 'Climate',
         'url': 'https://www.worldclim.org/data/worldclim21.html', 'format': 'tiff',
         'est_size': 'Varies', 'desc': 'Global climate data: temperature, precipitation, bioclimatic variables.'},

        # === Satellite Imagery ===
        {'id': 'sentinel2', 'name': 'Sentinel-2 Satellite (ESA)', 'category': 'Satellite',
         'url': 'https://browser.dataspace.copernicus.eu/', 'format': 'jp2/tiff',
         'est_size': 'Varies', 'desc': 'Free 10m resolution satellite imagery. Updated every 5 days.'},
        {'id': 'landsat', 'name': 'Landsat (USGS)', 'category': 'Satellite',
         'url': 'https://earthexplorer.usgs.gov/', 'format': 'tiff',
         'est_size': 'Varies', 'desc': 'Free 30m satellite imagery with 50+ year archive.'},
    ]

    # Map download state tracking
    _map_downloads = {}  # {region_id: {'progress': 0-100, 'status': str, 'error': str|None}}

    @app.route('/api/maps/regions')
    def api_maps_regions():
        maps_dir = get_maps_dir()
        result = []
        for r in MAP_REGIONS:
            pmtiles = os.path.join(maps_dir, f'{r["id"]}.pmtiles')
            result.append({
                **r,
                'downloaded': os.path.isfile(pmtiles),
                'size': format_size(os.path.getsize(pmtiles)) if os.path.isfile(pmtiles) else None,
            })
        return jsonify(result)

    @app.route('/api/maps/files')
    def api_maps_files():
        maps_dir = get_maps_dir()
        MAP_EXTENSIONS = ('.pmtiles', '.pbf', '.osm', '.geojson', '.gpkg', '.mbtiles', '.shp', '.tiff', '.hgt')
        files = []
        for f in os.listdir(maps_dir):
            if any(f.endswith(ext) for ext in MAP_EXTENSIONS):
                fp = os.path.join(maps_dir, f)
                files.append({'filename': f, 'size': format_size(os.path.getsize(fp))})
        return jsonify(files)

    @app.route('/api/maps/delete', methods=['POST'])
    def api_maps_delete():
        data = request.get_json() or {}
        filename = data.get('filename')
        if not filename or '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({'error': 'Invalid filename'}), 400
        maps_dir = get_maps_dir()
        path = os.path.normpath(os.path.join(maps_dir, filename))
        if not path.startswith(os.path.normpath(maps_dir) + os.sep):
            return jsonify({'error': 'Invalid filename'}), 400
        try:
            if os.path.isfile(path):
                os.remove(path)
            return jsonify({'status': 'deleted'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/maps/tiles/<path:filepath>')
    def api_maps_serve_tile(filepath):
        """Serve local PMTiles files."""
        maps_dir = get_maps_dir()
        safe_path = os.path.normpath(os.path.join(maps_dir, filepath))
        if not os.path.normcase(safe_path).startswith(os.path.normcase(os.path.normpath(maps_dir))):
            return jsonify({'error': 'Forbidden'}), 403
        if not os.path.isfile(safe_path):
            return jsonify({'error': 'Not found'}), 404

        # Support range requests for PMTiles
        range_header = request.headers.get('Range')
        file_size = os.path.getsize(safe_path)

        if range_header:
            try:
                byte_range = range_header.replace('bytes=', '').split('-')
                start = int(byte_range[0])
                end = int(byte_range[1]) if byte_range[1] else file_size - 1
            except (ValueError, IndexError):
                return jsonify({'error': 'Invalid Range header'}), 416
            length = end - start + 1

            with open(safe_path, 'rb') as f:
                f.seek(start)
                data = f.read(length)

            resp = Response(data, 206, mimetype='application/octet-stream')
            resp.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
            resp.headers['Accept-Ranges'] = 'bytes'
            resp.headers['Content-Length'] = length
            return resp

        def stream_file():
            with open(safe_path, 'rb') as f:
                while True:
                    chunk = f.read(1024 * 1024)  # 1MB chunks
                    if not chunk:
                        break
                    yield chunk
        resp = Response(stream_file(), mimetype='application/octet-stream')
        resp.headers['Content-Length'] = file_size
        resp.headers['Accept-Ranges'] = 'bytes'
        return resp

    @app.route('/api/maps/sources')
    def api_maps_sources():
        return jsonify(MAP_SOURCES)

    @app.route('/api/maps/download-progress')
    def api_maps_download_progress():
        with _state_lock:
            snapshot = dict(_map_downloads)
        return jsonify(snapshot)

    def _get_pmtiles_cli():
        """Get path to pmtiles CLI, auto-downloading if needed."""
        from platform_utils import exe_name, IS_WINDOWS, IS_MACOS
        services_dir = get_services_dir()
        pmtiles_dir = os.path.join(services_dir, 'pmtiles')
        os.makedirs(pmtiles_dir, exist_ok=True)
        exe = os.path.join(pmtiles_dir, exe_name('pmtiles'))
        if os.path.isfile(exe):
            return exe
        # Download from GitHub releases
        import urllib.request, zipfile, io, json as _json
        api_url = 'https://api.github.com/repos/protomaps/go-pmtiles/releases/latest'
        log.info('Resolving pmtiles CLI release from %s', api_url)
        req = urllib.request.Request(api_url, headers={'User-Agent': 'ProjectNOMAD/3.5.0', 'Accept': 'application/vnd.github+json'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            release = _json.loads(resp.read())
        url = None
        if IS_WINDOWS:
            plat_key, arch_key = 'Windows', 'x86_64'
        elif IS_MACOS:
            import platform as _plat
            arch = 'arm64' if _plat.machine() == 'arm64' else 'x86_64'
            plat_key, arch_key = 'Darwin', arch
        else:
            import platform as _plat
            arch = 'arm64' if _plat.machine() == 'aarch64' else 'x86_64'
            plat_key, arch_key = 'Linux', arch
        for asset in release.get('assets', []):
            if plat_key in asset['name'] and arch_key in asset['name']:
                url = asset['browser_download_url']
                break
        if not url:
            log.error('No %s %s asset found in go-pmtiles release', plat_key, arch_key)
            return None
        log.info('Downloading pmtiles CLI from %s', url)
        req = urllib.request.Request(url, headers={'User-Agent': 'ProjectNOMAD/3.5.0'})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
        binary_name = exe_name('pmtiles') if IS_WINDOWS else 'pmtiles'
        if url.endswith('.zip'):
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for name in zf.namelist():
                    if name.endswith(binary_name):
                        extracted = zf.extract(name, pmtiles_dir)
                        if extracted != exe:
                            shutil.move(extracted, exe)
                        break
        elif url.endswith('.tar.gz') or url.endswith('.tgz'):
            import tarfile
            with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as tf:
                for name in tf.getnames():
                    if name.endswith(binary_name):
                        tf.extract(name, pmtiles_dir)
                        extracted = os.path.join(pmtiles_dir, name)
                        if extracted != exe:
                            shutil.move(extracted, exe)
                        break
        if os.path.isfile(exe):
            from platform_utils import make_executable
            make_executable(exe)
            log.info('pmtiles CLI installed at %s', exe)
            return exe
        return None

    def _download_map_region_thread(region_id, bbox, maps_dir):
        """Background thread: extract a region from Protomaps planet using pmtiles CLI."""
        with _state_lock:
            _map_downloads[region_id] = {'progress': 0, 'status': 'Preparing...', 'error': None}
        try:
            # Get or install pmtiles CLI
            _map_downloads[region_id]['status'] = 'Installing pmtiles tool...'
            _map_downloads[region_id]['progress'] = 5
            pmtiles_exe = _get_pmtiles_cli()
            if not pmtiles_exe:
                _map_downloads[region_id] = {'progress': 0, 'status': 'Error', 'error': 'Failed to download pmtiles CLI'}
                return

            output_file = os.path.join(maps_dir, f'{region_id}.pmtiles')
            temp_file = output_file + '.tmp'

            # Clean up stale temp file from previous failed download
            if os.path.isfile(temp_file):
                try:
                    os.remove(temp_file)
                    log.info('Cleaned up stale temp file: %s', temp_file)
                except PermissionError:
                    # File locked by another process — try alternative temp name
                    temp_file = output_file + f'.{int(time.time())}.tmp'
                    log.warning('Original temp file locked, using: %s', temp_file)

            # Source Cooperative mirror of Protomaps planet (supports range requests)
            source_url = 'https://data.source.coop/protomaps/openstreetmap/v4.pmtiles'

            bbox_str = f'{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}'

            _map_downloads[region_id]['status'] = f'Extracting region (bbox: {bbox_str})...'
            _map_downloads[region_id]['progress'] = 10

            # Run pmtiles extract with bbox
            cmd = [pmtiles_exe, 'extract', source_url, temp_file, f'--bbox={bbox_str}', '--maxzoom=12']
            log.info('Running: %s', ' '.join(cmd))

            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, **_CREATION_FLAGS)

            # Monitor progress from output — wrapped in try/finally to prevent process leak
            lines = []
            try:
                for line in proc.stdout:
                    lines.append(line.strip())
                    # pmtiles extract outputs progress info
                    if '%' in line:
                        try:
                            pct = int(float(line.split('%')[0].split()[-1]))
                            _map_downloads[region_id]['progress'] = min(10 + int(pct * 0.85), 95)
                        except (ValueError, IndexError):
                            pass
                    _map_downloads[region_id]['status'] = f'Downloading tiles... {line.strip()}'

                proc.wait()
            except Exception:
                # Ensure the subprocess is cleaned up on any exception
                try:
                    proc.terminate()
                except OSError:
                    pass
                proc.wait()
                raise

            if proc.returncode != 0:
                err = '\n'.join(lines[-5:]) if lines else 'Unknown error'
                if 'permission denied' in err.lower() or 'access is denied' in err.lower():
                    err = 'Permission denied. Your antivirus may be blocking pmtiles.exe. Add it to your antivirus exclusions, or try running N.O.M.A.D. as Administrator.'
                _map_downloads[region_id] = {'progress': 0, 'status': 'Error', 'error': f'pmtiles extract failed: {err}'}
                if os.path.isfile(temp_file):
                    os.remove(temp_file)
                return

            # Rename temp to final
            if os.path.isfile(temp_file):
                try:
                    if os.path.isfile(output_file):
                        os.remove(output_file)
                    os.rename(temp_file, output_file)
                except PermissionError:
                    # Output file may be locked by Flask tile server — retry with delay
                    import time as _t
                    _t.sleep(1)
                    try:
                        if os.path.isfile(output_file):
                            os.remove(output_file)
                        os.rename(temp_file, output_file)
                    except PermissionError as pe:
                        _map_downloads[region_id] = {'progress': 0, 'status': 'Error',
                            'error': f'Permission denied when saving map file. Close any programs using the maps folder and try again. ({pe})'}
                        return
                size = format_size(os.path.getsize(output_file))
                _map_downloads[region_id] = {'progress': 100, 'status': f'Complete ({size})', 'error': None}
                log.info('Map region %s downloaded: %s', region_id, size)
            else:
                _map_downloads[region_id] = {'progress': 0, 'status': 'Error', 'error': 'No output file produced'}

        except PermissionError as e:
            log.exception('Map download permission error for %s', region_id)
            _map_downloads[region_id] = {'progress': 0, 'status': 'Error',
                'error': 'Permission denied. Try running N.O.M.A.D. as Administrator, or check that your antivirus is not blocking pmtiles.exe.'}
        except Exception as e:
            log.exception('Map download error for %s', region_id)
            err_msg = str(e)
            if 'WinError 5' in err_msg or 'Permission denied' in err_msg or 'Access is denied' in err_msg:
                err_msg = 'Permission denied. Try running N.O.M.A.D. as Administrator, or check that your antivirus is not blocking pmtiles.exe.'
            _map_downloads[region_id] = {'progress': 0, 'status': 'Error', 'error': err_msg}

    @app.route('/api/maps/download-region', methods=['POST'])
    def api_maps_download_region():
        data = request.get_json() or {}
        region_id = data.get('region_id')
        if not region_id:
            return jsonify({'error': 'Missing region_id'}), 400

        # Check if already downloading
        if region_id in _map_downloads and _map_downloads[region_id].get('progress', 0) > 0 \
                and _map_downloads[region_id].get('progress', 0) < 100:
            return jsonify({'error': 'Already downloading'}), 409

        # Find region
        region = next((r for r in MAP_REGIONS if r['id'] == region_id), None)
        if not region:
            return jsonify({'error': 'Unknown region'}), 404

        maps_dir = get_maps_dir()
        bbox = region.get('bbox')
        if not bbox:
            return jsonify({'error': 'Region has no bounding box defined'}), 400

        t = threading.Thread(target=_download_map_region_thread, args=(region_id, bbox, maps_dir), daemon=True)
        t.start()
        return jsonify({'status': 'started', 'region_id': region_id})

    @app.route('/api/maps/download-url', methods=['POST'])
    def api_maps_download_url():
        """Download a map file from a direct URL."""
        data = request.get_json() or {}
        url = data.get('url', '').strip()
        filename = data.get('filename', '').strip()
        if not url:
            return jsonify({'error': 'Missing url'}), 400

        # SSRF protection — validate URL before downloading
        try:
            _validate_download_url(url)
        except ValueError as e:
            return jsonify({'error': f'Invalid download URL: {e}'}), 400

        if not filename:
            filename = url.rstrip('/').split('/')[-1]
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({'error': 'Invalid filename'}), 400

        dl_id = f'url-{filename}'
        if dl_id in _map_downloads and _map_downloads[dl_id].get('progress', 0) > 0 \
                and _map_downloads[dl_id].get('progress', 0) < 100:
            return jsonify({'error': 'Already downloading'}), 409

        def _dl_thread():
            import urllib.request
            _map_downloads[dl_id] = {'progress': 0, 'status': 'Connecting...', 'error': None}
            try:
                maps_dir = get_maps_dir()
                dest = os.path.join(maps_dir, filename)
                req = urllib.request.Request(url, headers={'User-Agent': 'ProjectNOMAD/3.5.0'})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    total = int(resp.headers.get('Content-Length', 0))
                    downloaded = 0
                    with open(dest, 'wb') as f:
                        while True:
                            chunk = resp.read(1024 * 256)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                pct = int(downloaded / total * 100)
                                speed = format_size(downloaded)
                                _map_downloads[dl_id] = {'progress': pct, 'status': f'{speed} / {format_size(total)}', 'error': None}
                            else:
                                _map_downloads[dl_id] = {'progress': 50, 'status': f'{format_size(downloaded)} downloaded', 'error': None}
                _map_downloads[dl_id] = {'progress': 100, 'status': f'Complete ({format_size(os.path.getsize(dest))})', 'error': None}
            except Exception as e:
                _map_downloads[dl_id] = {'progress': 0, 'status': 'Error', 'error': str(e)}

        threading.Thread(target=_dl_thread, daemon=True).start()
        return jsonify({'status': 'started', 'dl_id': dl_id})

    ALLOWED_MAP_EXTENSIONS = ('.pmtiles', '.mbtiles', '.geojson', '.gpx', '.kml')

    @app.route('/api/maps/import-file', methods=['POST'])
    def api_maps_import_file():
        """Import a local map file by copying it to the maps directory."""
        data = request.get_json() or {}
        source_path = data.get('path', '').strip()
        if not source_path:
            return jsonify({'error': 'No path provided'}), 400
        # Reject path traversal
        if '..' in source_path:
            return jsonify({'error': 'Invalid path: directory traversal not allowed'}), 400
        # Validate file extension
        ext = os.path.splitext(source_path)[1].lower()
        if ext not in ALLOWED_MAP_EXTENSIONS:
            return jsonify({'error': f'Unsupported map file type: {ext}. Allowed: {", ".join(ALLOWED_MAP_EXTENSIONS)}'}), 400
        if not os.path.isfile(source_path):
            return jsonify({'error': 'File not found'}), 404
        filename = os.path.basename(source_path)
        dest = os.path.join(get_maps_dir(), filename)
        try:
            shutil.copy2(source_path, dest)
            return jsonify({'status': 'imported', 'filename': filename, 'size': format_size(os.path.getsize(dest))})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # ─── Connectivity & Network ───────────────────────────────────────

    @app.route('/api/network')
    def api_network():
        import socket
        online = False
        try:
            socket.create_connection(('1.1.1.1', 443), timeout=1).close()
            online = True
        except Exception:
            pass

        lan_ip = '127.0.0.1'
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            lan_ip = s.getsockname()[0]
            s.close()
        except Exception:
            pass

        return jsonify({'online': online, 'lan_ip': lan_ip, 'dashboard_url': f'http://{lan_ip}:8080'})

    # ─── Knowledge Base / RAG API ─────────────────────────────────────

    def get_kb_upload_dir():
        path = os.path.join(get_data_base(), 'ProjectNOMAD', 'kb_uploads')
        os.makedirs(path, exist_ok=True)
        return path

    def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
        """Split text into overlapping chunks (~chunk_size words)."""
        words = text.split()
        chunks = []
        i = 0
        while i < len(words):
            chunk = ' '.join(words[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)
            i += chunk_size - overlap
        return chunks

    def embed_text(texts: list[str], prefix: str = 'search_document: ') -> list[list[float]]:
        """Embed texts using Ollama's embedding API."""
        import requests as rq
        prefixed = [prefix + t for t in texts]
        resp = rq.post(
            f'http://localhost:{ollama.OLLAMA_PORT}/api/embed',
            json={'model': EMBED_MODEL, 'input': prefixed},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json().get('embeddings', [])

    def extract_text_from_file(filepath: str, content_type: str) -> str:
        """Extract text from uploaded file."""
        if content_type == 'pdf':
            try:
                import PyPDF2
                text = ''
                with open(filepath, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        text += page.extract_text() or ''
                return text
            except Exception as e:
                log.error(f'PDF extraction failed: {e}')
                return ''
        else:
            # Plain text / markdown
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()

    @app.route('/api/kb/upload', methods=['POST'])
    def api_kb_upload():
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        if not file.filename:
            return jsonify({'error': 'No filename'}), 400

        filename = secure_filename(file.filename)
        if not filename:
            return jsonify({'error': 'Invalid filename'}), 400
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        content_type = 'pdf' if ext == 'pdf' else 'text'

        upload_dir = get_kb_upload_dir()
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)
        file_size = os.path.getsize(filepath)

        db = get_db()
        try:
            cur = db.execute('INSERT INTO documents (filename, content_type, file_size, status) VALUES (?, ?, ?, ?)',
                             (filename, content_type, file_size, 'pending'))
            db.commit()
            doc_id = cur.lastrowid
        finally:
            db.close()

        # Start embedding in background
        def do_embed():
            global _embed_state
            _embed_state = {'status': 'processing', 'doc_id': doc_id, 'progress': 0, 'detail': f'Processing {filename}...'}
            db2 = get_db()
            try:
                # Ensure embedding model is available
                _embed_state['detail'] = 'Checking embedding model...'
                models = ollama.list_models()
                model_names = [m['name'] for m in models]
                if EMBED_MODEL not in model_names and EMBED_MODEL.split(':')[0] not in [m.split(':')[0] for m in model_names]:
                    _embed_state['detail'] = f'Pulling {EMBED_MODEL}...'
                    ollama.pull_model(EMBED_MODEL)

                # Extract text
                _embed_state.update({'progress': 20, 'detail': 'Extracting text...'})
                text = extract_text_from_file(filepath, content_type)
                if not text.strip():
                    raise ValueError('No text could be extracted from file')

                # Chunk
                _embed_state.update({'progress': 30, 'detail': 'Chunking text...'})
                chunks = chunk_text(text)
                total = len(chunks)

                # Embed in batches of 8
                _embed_state.update({'progress': 40, 'detail': f'Embedding {total} chunks...'})
                batch_size = 8
                all_points = []
                import hashlib
                for i in range(0, total, batch_size):
                    batch = chunks[i:i + batch_size]
                    vectors = embed_text(batch)
                    for j, (chunk, vec) in enumerate(zip(batch, vectors)):
                        point_id = int(hashlib.md5(f'{doc_id}:{i+j}'.encode()).hexdigest()[:8], 16)
                        all_points.append({
                            'id': point_id,
                            'vector': vec,
                            'payload': {
                                'doc_id': doc_id,
                                'filename': filename,
                                'chunk_index': i + j,
                                'text': chunk,
                            }
                        })
                    pct = 40 + int(60 * min(i + batch_size, total) / total)
                    _embed_state.update({'progress': pct, 'detail': f'Embedded {min(i+batch_size, total)}/{total} chunks'})

                # Upsert to Qdrant
                qdrant.upsert_vectors(all_points)

                db2.execute('UPDATE documents SET status = ?, chunks_count = ? WHERE id = ?',
                            ('ready', total, doc_id))
                db2.commit()
                _embed_state = {'status': 'complete', 'doc_id': doc_id, 'progress': 100, 'detail': f'{filename}: {total} chunks embedded'}

                # Auto-trigger document analysis (classify, summarize, extract entities)
                threading.Thread(target=_analyze_document, args=(doc_id, text, filename), daemon=True).start()

            except Exception as e:
                log.error(f'Embedding failed for doc {doc_id}: {e}')
                db2.execute('UPDATE documents SET status = ?, error = ? WHERE id = ?', ('error', str(e), doc_id))
                db2.commit()
                _embed_state = {'status': 'error', 'doc_id': doc_id, 'progress': 0, 'detail': str(e)}
            finally:
                db2.close()

        threading.Thread(target=do_embed, daemon=True).start()
        return jsonify({'status': 'uploading', 'doc_id': doc_id}), 201

    @app.route('/api/kb/documents')
    def api_kb_documents():
        db = get_db()
        try:
            docs = db.execute('SELECT * FROM documents ORDER BY created_at DESC').fetchall()
        finally:
            db.close()
        return jsonify([dict(d) for d in docs])

    @app.route('/api/kb/documents/<int:doc_id>', methods=['DELETE'])
    def api_kb_document_delete(doc_id):
        db = get_db()
        try:
            doc = db.execute('SELECT filename FROM documents WHERE id = ?', (doc_id,)).fetchone()
            if doc:
                filepath = os.path.join(get_kb_upload_dir(), doc['filename'])
                if os.path.isfile(filepath):
                    os.remove(filepath)
                qdrant.delete_by_doc_id(doc_id)
                db.execute('DELETE FROM documents WHERE id = ?', (doc_id,))
                db.commit()
        finally:
            db.close()
        return jsonify({'status': 'deleted'})

    @app.route('/api/kb/status')
    def api_kb_status():
        info = qdrant.get_collection_info() if qdrant.running() else {'points_count': 0}
        return jsonify({**_embed_state, 'collection': info, 'qdrant_running': qdrant.running()})

    @app.route('/api/kb/search', methods=['POST'])
    def api_kb_search():
        data = request.get_json() or {}
        query = data.get('query', '')
        limit = data.get('limit', 5)
        if not query:
            return jsonify([])
        try:
            vectors = embed_text([query], prefix='search_query: ')
            if not vectors:
                return jsonify([])
            results = qdrant.search(vectors[0], limit=limit)
            return jsonify([{
                'text': r.get('payload', {}).get('text', ''),
                'filename': r.get('payload', {}).get('filename', ''),
                'score': r.get('score', 0),
            } for r in results])
        except Exception as e:
            log.error(f'KB search failed: {e}')
            return jsonify([])

    # ─── Activity Log ──────────────────────────────────────────────────

    @app.route('/api/activity')
    def api_activity():
        limit = request.args.get('limit', 50, type=int)
        filter_val = request.args.get('filter', '')
        db = get_db()
        try:
            if filter_val:
                rows = db.execute('SELECT * FROM activity_log WHERE event LIKE ? OR service LIKE ? ORDER BY created_at DESC LIMIT ?',
                                  (f'%{filter_val}%', f'%{filter_val}%', limit)).fetchall()
            else:
                rows = db.execute('SELECT * FROM activity_log ORDER BY created_at DESC LIMIT ?', (limit,)).fetchall()
        finally:
            db.close()
        return jsonify([dict(r) for r in rows])

    # ─── GPU Info ──────────────────────────────────────────────────────

    @app.route('/api/gpu')
    def api_gpu():
        return jsonify(detect_gpu())

    # ─── Health ────────────────────────────────────────────────────────

    @app.route('/api/health')
    def api_health():
        return jsonify({'status': 'ok', 'version': VERSION})

    # ─── Update Checker ───────────────────────────────────────────────

    @app.route('/api/update-check')
    def api_update_check():
        """Check GitHub for newer release."""
        try:
            import requests as rq
            resp = rq.get('https://api.github.com/repos/SysAdminDoc/project-nomad-desktop/releases/latest', timeout=10)
            if resp.ok:
                data = resp.json()
                latest = data.get('tag_name', '').lstrip('v')
                current = VERSION
                # Simple version comparison
                is_newer = False
                try:
                    from packaging.version import Version
                    is_newer = Version(latest) > Version(current)
                except Exception:
                    try:
                        is_newer = list(map(int, latest.split('.'))) > list(map(int, current.split('.')))
                    except (ValueError, AttributeError):
                        is_newer = latest != current
                return jsonify({
                    'current': current,
                    'latest': latest,
                    'update_available': is_newer,
                    'download_url': data.get('html_url', ''),
                    'release_name': data.get('name', ''),
                })
        except Exception as e:
            log.warning(f'Update check failed: {e}')
        return jsonify({'current': VERSION, 'latest': VERSION, 'update_available': False})

    # ─── Startup Toggle (Cross-Platform) ─────────────────────────────

    def _get_autostart_path():
        """Get the platform-specific autostart file/registry path."""
        if sys.platform == 'win32':
            return 'registry'
        elif sys.platform == 'darwin':
            return os.path.expanduser('~/Library/LaunchAgents/com.sysadmindoc.projectnomad.plist')
        else:  # Linux
            xdg = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
            return os.path.join(xdg, 'autostart', 'ProjectNOMAD.desktop')

    @app.route('/api/startup')
    def api_startup_get():
        """Check if app is set to start at login (cross-platform)."""
        try:
            if sys.platform == 'win32':
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                     r'Software\Microsoft\Windows\CurrentVersion\Run', 0, winreg.KEY_READ)
                winreg.QueryValueEx(key, 'ProjectNOMAD')
                winreg.CloseKey(key)
                return jsonify({'enabled': True, 'platform': 'windows'})
            else:
                path = _get_autostart_path()
                return jsonify({'enabled': os.path.isfile(path), 'platform': sys.platform})
        except Exception:
            return jsonify({'enabled': False, 'platform': sys.platform})

    @app.route('/api/startup', methods=['PUT'])
    def api_startup_set():
        """Enable or disable start at login (cross-platform)."""
        data = request.get_json() or {}
        enabled = data.get('enabled', False)
        try:
            exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath('nomad.py')

            if sys.platform == 'win32':
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                     r'Software\Microsoft\Windows\CurrentVersion\Run', 0, winreg.KEY_SET_VALUE)
                if enabled:
                    if getattr(sys, 'frozen', False):
                        winreg.SetValueEx(key, 'ProjectNOMAD', 0, winreg.REG_SZ, f'"{exe_path}"')
                    else:
                        winreg.SetValueEx(key, 'ProjectNOMAD', 0, winreg.REG_SZ, f'"{sys.executable}" "{exe_path}"')
                else:
                    try:
                        winreg.DeleteValue(key, 'ProjectNOMAD')
                    except FileNotFoundError:
                        pass
                winreg.CloseKey(key)

            elif sys.platform == 'darwin':
                plist_path = _get_autostart_path()
                if enabled:
                    os.makedirs(os.path.dirname(plist_path), exist_ok=True)
                    if getattr(sys, 'frozen', False):
                        program_args = f'<string>{exe_path}</string>'
                    else:
                        program_args = f'<string>{sys.executable}</string>\n            <string>{exe_path}</string>'
                    with open(plist_path, 'w') as f:
                        f.write(f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sysadmindoc.projectnomad</string>
    <key>ProgramArguments</key>
    <array>
        {program_args}
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>''')
                else:
                    if os.path.isfile(plist_path):
                        os.remove(plist_path)

            else:  # Linux
                desktop_path = _get_autostart_path()
                if enabled:
                    os.makedirs(os.path.dirname(desktop_path), exist_ok=True)
                    if getattr(sys, 'frozen', False):
                        exec_line = exe_path
                    else:
                        exec_line = f'{sys.executable} {exe_path}'
                    with open(desktop_path, 'w') as f:
                        f.write(f'''[Desktop Entry]
Type=Application
Name=Project N.O.M.A.D.
Comment=Offline Survival Command Center
Exec={exec_line}
Terminal=false
X-GNOME-Autostart-enabled=true
''')
                else:
                    if os.path.isfile(desktop_path):
                        os.remove(desktop_path)

            return jsonify({'status': 'ok', 'enabled': enabled})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # ─── Export / Import Config ───────────────────────────────────────

    @app.route('/api/export-config')
    def api_export_config():
        """Export settings and database as a ZIP."""
        try:
            import io
            import zipfile as zf
            from db import get_db_path

            buf = io.BytesIO()
            with zf.ZipFile(buf, 'w', zf.ZIP_DEFLATED) as z:
                db_path = get_db_path()
                if os.path.isfile(db_path):
                    z.write(db_path, 'nomad.db')
            buf.seek(0)
            return Response(buf.read(), mimetype='application/zip',
                           headers={'Content-Disposition': 'attachment; filename="nomad-backup.zip"'})
        except Exception as e:
            log.error(f'Export config failed: {e}')
            return jsonify({'error': str(e)}), 500

    @app.route('/api/import-config', methods=['POST'])
    def api_import_config():
        """Import a config backup ZIP."""
        import zipfile as zf
        import io
        from db import get_db_path

        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        file = request.files['file']
        try:
            with zf.ZipFile(io.BytesIO(file.read())) as z:
                if 'nomad.db' in z.namelist():
                    db_path = get_db_path()
                    # Backup current first
                    from db import backup_db
                    backup_db()
                    z.extract('nomad.db', os.path.dirname(db_path))
                    return jsonify({'status': 'ok', 'message': 'Config restored. Restart app to apply.'})
                else:
                    return jsonify({'error': 'Invalid backup file'}), 400
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # ─── Database Restore from Auto-Backups ──────────────────────────

    @app.route('/api/backups')
    def api_backups_list():
        """List available automatic database backups."""
        from db import get_db_path
        backup_dir = os.path.join(os.path.dirname(get_db_path()), 'backups')
        if not os.path.isdir(backup_dir):
            return jsonify([])
        backups = []
        for f in sorted(os.listdir(backup_dir), reverse=True):
            if f.endswith('.db'):
                path = os.path.join(backup_dir, f)
                size = os.path.getsize(path)
                backups.append({
                    'filename': f,
                    'size': f'{size / (1024*1024):.1f} MB' if size > 1024*1024 else f'{size / 1024:.0f} KB',
                    'modified': os.path.getmtime(path),
                })
        return jsonify(backups)

    @app.route('/api/backups/restore', methods=['POST'])
    def api_backups_restore():
        """Restore database from an automatic backup file."""
        from db import get_db_path, backup_db
        data = request.get_json() or {}
        filename = data.get('filename', '')
        if not filename or '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({'error': 'Invalid filename'}), 400
        backup_dir = os.path.join(os.path.dirname(get_db_path()), 'backups')
        backup_path = os.path.join(backup_dir, filename)
        if not os.path.isfile(backup_path):
            return jsonify({'error': 'Backup not found'}), 404
        # Safety: back up current DB first
        backup_db()
        # Replace current DB with backup
        import shutil
        db_path = get_db_path()
        shutil.copy2(backup_path, db_path)
        log_activity('database_restored', detail=f'Restored from {filename}')
        return jsonify({'status': 'ok', 'message': f'Database restored from {filename}. Restart app to fully apply.'})

    # ─── Auto-pull default model after Ollama install ─────────────────

    @app.route('/api/ai/auto-setup', methods=['POST'])
    def api_ai_auto_setup():
        """Auto-pull default model. Called after wizard installs Ollama."""
        if not ollama.is_installed():
            return jsonify({'error': 'Ollama not installed'}), 400

        def do_setup():
            # Wait for Ollama to be ready
            for _ in range(30):
                if ollama.running():
                    break
                time.sleep(1)
            if ollama.running():
                log.info('Auto-pulling default model llama3.2:3b...')
                log_activity('auto_model_pull', 'ollama', 'llama3.2:3b')
                ollama.pull_model('llama3.2:3b')

        threading.Thread(target=do_setup, daemon=True).start()
        return jsonify({'status': 'started'})

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
            fields = []
            vals = []
            if 'name' in data:
                fields.append('name = ?')
                vals.append(data['name'])
            if 'items' in data:
                fields.append('items = ?')
                vals.append(json.dumps(data['items']))
            fields.append('updated_at = CURRENT_TIMESTAMP')
            vals.append(cid)
            db.execute(f'UPDATE checklists SET {", ".join(fields)} WHERE id = ?', vals)
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

    # ─── Inventory API ────────────────────────────────────────────────

    INVENTORY_CATEGORIES = [
        'water', 'food', 'medical', 'ammo', 'fuel', 'tools',
        'hygiene', 'comms', 'clothing', 'shelter', 'power', 'other',
    ]

    @app.route('/api/inventory')
    def api_inventory_list():
        db = get_db()
        try:
            cat = request.args.get('category', '')
            search = request.args.get('q', '').strip()
            query = 'SELECT * FROM inventory'
            params = []
            clauses = []
            if cat:
                clauses.append('category = ?')
                params.append(cat)
            if search:
                clauses.append('(name LIKE ? OR location LIKE ? OR notes LIKE ?)')
                params.extend([f'%{search}%'] * 3)
            if clauses:
                query += ' WHERE ' + ' AND '.join(clauses)
            query += ' ORDER BY category, name'
            rows = db.execute(query, params).fetchall()
        finally:
            db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/inventory', methods=['POST'])
    def api_inventory_create():
        data = request.get_json() or {}
        db = get_db()
        try:
            cur = db.execute(
                'INSERT INTO inventory (name, category, quantity, unit, min_quantity, daily_usage, location, expiration, barcode, cost, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (data.get('name', ''), data.get('category', 'other'), data.get('quantity', 0),
                 data.get('unit', 'ea'), data.get('min_quantity', 0), data.get('daily_usage', 0),
                 data.get('location', ''), data.get('expiration', ''), data.get('barcode', ''), data.get('cost', 0), data.get('notes', '')))
            db.commit()
            item_id = cur.lastrowid
            row = db.execute('SELECT * FROM inventory WHERE id = ?', (item_id,)).fetchone()
        finally:
            db.close()
        return jsonify(dict(row)), 201

    @app.route('/api/inventory/<int:item_id>', methods=['PUT'])
    def api_inventory_update(item_id):
        data = request.get_json() or {}
        allowed = ['name', 'category', 'quantity', 'unit', 'min_quantity', 'daily_usage', 'location', 'expiration', 'barcode', 'cost', 'notes']
        fields = []
        vals = []
        for k in allowed:
            if k in data:
                fields.append(f'{k} = ?')
                vals.append(data[k])
        if not fields:
            return jsonify({'error': 'No fields to update'}), 400
        db = get_db()
        try:
            fields.append('updated_at = CURRENT_TIMESTAMP')
            vals.append(item_id)
            db.execute(f'UPDATE inventory SET {", ".join(fields)} WHERE id = ?', vals)
            db.commit()
        finally:
            db.close()
        return jsonify({'status': 'saved'})

    @app.route('/api/inventory/<int:item_id>', methods=['DELETE'])
    def api_inventory_delete(item_id):
        db = get_db()
        try:
            db.execute('DELETE FROM inventory WHERE id = ?', (item_id,))
            db.commit()
        finally:
            db.close()
        return jsonify({'status': 'deleted'})

    @app.route('/api/inventory/summary')
    def api_inventory_summary():
        db = get_db()
        try:
            total = db.execute('SELECT COUNT(*) as c FROM inventory').fetchone()['c']
            low_stock = db.execute('SELECT COUNT(*) as c FROM inventory WHERE quantity <= min_quantity AND min_quantity > 0').fetchone()['c']
            # Expiring within 30 days
            from datetime import datetime, timedelta
            soon = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            today = datetime.now().strftime('%Y-%m-%d')
            expiring = db.execute("SELECT COUNT(*) as c FROM inventory WHERE expiration != '' AND expiration <= ? AND expiration >= ?", (soon, today)).fetchone()['c']
            expired = db.execute("SELECT COUNT(*) as c FROM inventory WHERE expiration != '' AND expiration < ?", (today,)).fetchone()['c']
            cats = db.execute('SELECT category, COUNT(*) as c, SUM(quantity) as qty FROM inventory GROUP BY category ORDER BY category').fetchall()
        finally:
            db.close()
        return jsonify({
            'total': total, 'low_stock': low_stock, 'expiring_soon': expiring, 'expired': expired,
            'categories': [{'category': r['category'], 'count': r['c'], 'total_qty': r['qty'] or 0} for r in cats],
        })

    @app.route('/api/inventory/categories')
    def api_inventory_categories():
        return jsonify(INVENTORY_CATEGORIES)

    @app.route('/api/inventory/burn-rate')
    def api_inventory_burn_rate():
        """Calculate days of supply remaining per category."""
        db = get_db()
        try:
            rows = db.execute('SELECT category, name, quantity, unit, daily_usage FROM inventory WHERE daily_usage > 0 ORDER BY category, name').fetchall()
        finally:
            db.close()
        cats = {}
        for r in rows:
            cat = r['category']
            if cat not in cats:
                cats[cat] = {'items': [], 'min_days': float('inf')}
            days = r['quantity'] / r['daily_usage'] if r['daily_usage'] > 0 else float('inf')
            cats[cat]['items'].append({
                'name': r['name'], 'quantity': r['quantity'], 'unit': r['unit'],
                'daily_usage': r['daily_usage'], 'days_remaining': round(days, 1),
            })
            if days < cats[cat]['min_days']:
                cats[cat]['min_days'] = round(days, 1)
        # Convert inf
        for cat in cats.values():
            if cat['min_days'] == float('inf'):
                cat['min_days'] = None
        return jsonify(cats)

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
        db = get_db()
        search = request.args.get('q', '').strip()
        if search:
            rows = db.execute(
                "SELECT * FROM contacts WHERE name LIKE ? OR callsign LIKE ? OR role LIKE ? OR skills LIKE ? ORDER BY name",
                tuple(f'%{search}%' for _ in range(4))
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM contacts ORDER BY name').fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/contacts', methods=['POST'])
    def api_contacts_create():
        data = request.get_json() or {}
        db = get_db()
        cur = db.execute(
            'INSERT INTO contacts (name, callsign, role, skills, phone, freq, email, address, rally_point, blood_type, medical_notes, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (data.get('name', ''), data.get('callsign', ''), data.get('role', ''),
             data.get('skills', ''), data.get('phone', ''), data.get('freq', ''),
             data.get('email', ''), data.get('address', ''), data.get('rally_point', ''),
             data.get('blood_type', ''), data.get('medical_notes', ''), data.get('notes', '')))
        db.commit()
        cid = cur.lastrowid
        row = db.execute('SELECT * FROM contacts WHERE id = ?', (cid,)).fetchone()
        db.close()
        return jsonify(dict(row)), 201

    @app.route('/api/contacts/<int:cid>', methods=['PUT'])
    def api_contacts_update(cid):
        data = request.get_json() or {}
        db = get_db()
        allowed = ['name', 'callsign', 'role', 'skills', 'phone', 'freq', 'email', 'address', 'rally_point', 'blood_type', 'medical_notes', 'notes']
        fields = []
        vals = []
        for k in allowed:
            if k in data:
                fields.append(f'{k} = ?')
                vals.append(data[k])
        if not fields:
            return jsonify({'error': 'No fields'}), 400
        fields.append('updated_at = CURRENT_TIMESTAMP')
        vals.append(cid)
        db.execute(f'UPDATE contacts SET {", ".join(fields)} WHERE id = ?', vals)
        db.commit()
        db.close()
        return jsonify({'status': 'saved'})

    @app.route('/api/contacts/<int:cid>', methods=['DELETE'])
    def api_contacts_delete(cid):
        db = get_db()
        db.execute('DELETE FROM contacts WHERE id = ?', (cid,))
        db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    # ─── LAN Chat API ─────────────────────────────────────────────────

    @app.route('/api/lan/messages')
    def api_lan_messages():
        after_id = request.args.get('after', 0, type=int)
        db = get_db()
        if after_id:
            rows = db.execute('SELECT * FROM lan_messages WHERE id > ? ORDER BY id ASC LIMIT 100', (after_id,)).fetchall()
        else:
            rows = db.execute('SELECT * FROM lan_messages ORDER BY id DESC LIMIT 50').fetchall()
            rows = list(reversed(rows))
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/lan/messages', methods=['POST'])
    def api_lan_send():
        data = request.get_json() or {}
        content = (data.get('content', '') or '').strip()
        if not content:
            return jsonify({'error': 'Empty message'}), 400
        sender = (data.get('sender', '') or '').strip() or 'Anonymous'
        msg_type = data.get('msg_type', 'text')
        db = get_db()
        cur = db.execute('INSERT INTO lan_messages (sender, content, msg_type) VALUES (?, ?, ?)',
                         (sender[:50], content[:2000], msg_type))
        db.commit()
        msg = db.execute('SELECT * FROM lan_messages WHERE id = ?', (cur.lastrowid,)).fetchone()
        db.close()
        return jsonify(dict(msg)), 201

    @app.route('/api/lan/messages/clear', methods=['POST'])
    def api_lan_clear():
        db = get_db()
        db.execute('DELETE FROM lan_messages')
        db.commit()
        db.close()
        return jsonify({'status': 'cleared'})

    # ─── LAN Enhancements (v5.0 Phase 10) ──────────────────────────

    @app.route('/api/lan/channels')
    def api_lan_channels():
        """List LAN chat channels."""
        db = get_db()
        try:
            rows = db.execute('SELECT * FROM lan_channels ORDER BY name').fetchall()
            channels = [dict(r) for r in rows]
            if not channels:
                for ch in ['General', 'Security', 'Medical', 'Logistics']:
                    db.execute('INSERT OR IGNORE INTO lan_channels (name) VALUES (?)', (ch,))
                db.commit()
                channels = [{'name': ch} for ch in ['General', 'Security', 'Medical', 'Logistics']]
            return jsonify(channels)
        finally:
            db.close()

    @app.route('/api/lan/channels', methods=['POST'])
    def api_lan_channel_create():
        """Create a LAN chat channel."""
        d = request.json or {}
        name = d.get('name', '').strip()
        if not name:
            return jsonify({'error': 'name required'}), 400
        db = get_db()
        try:
            db.execute('INSERT OR IGNORE INTO lan_channels (name, description) VALUES (?, ?)',
                       (name, d.get('description', '')))
            db.commit()
            return jsonify({'status': 'ok'})
        finally:
            db.close()

    @app.route('/api/lan/presence')
    def api_lan_presence():
        """List known LAN nodes and their status."""
        db = get_db()
        try:
            rows = db.execute(
                "SELECT * FROM lan_presence WHERE last_seen >= datetime('now', '-5 minutes') ORDER BY node_name"
            ).fetchall()
            return jsonify([dict(r) for r in rows])
        finally:
            db.close()

    @app.route('/api/lan/presence/heartbeat', methods=['POST'])
    def api_lan_heartbeat():
        """Register/update LAN presence."""
        d = request.json or {}
        ip = request.remote_addr or d.get('ip', '')
        name = d.get('name', 'Unknown')
        version = d.get('version', '')
        db = get_db()
        try:
            db.execute(
                '''INSERT INTO lan_presence (node_name, ip, status, version, last_seen)
                   VALUES (?, ?, 'online', ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(ip) DO UPDATE SET
                   node_name = excluded.node_name, status = 'online', version = excluded.version, last_seen = CURRENT_TIMESTAMP''',
                (name, ip, version)
            )
            db.commit()
            return jsonify({'status': 'ok'})
        finally:
            db.close()

    # ─── Incident Log API ─────────────────────────────────────────────

    @app.route('/api/incidents')
    def api_incidents_list():
        db = get_db()
        limit = request.args.get('limit', 100, type=int)
        cat = request.args.get('category', '')
        query = 'SELECT * FROM incidents'
        params = []
        if cat:
            query += ' WHERE category = ?'
            params.append(cat)
        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)
        rows = db.execute(query, params).fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/incidents', methods=['POST'])
    def api_incidents_create():
        data = request.get_json() or {}
        desc = (data.get('description', '') or '').strip()
        if not desc:
            return jsonify({'error': 'Description required'}), 400
        db = get_db()
        cur = db.execute('INSERT INTO incidents (severity, category, description) VALUES (?, ?, ?)',
                         (data.get('severity', 'info'), data.get('category', 'other'), desc))
        db.commit()
        row = db.execute('SELECT * FROM incidents WHERE id = ?', (cur.lastrowid,)).fetchone()
        db.close()
        return jsonify(dict(row)), 201

    @app.route('/api/incidents/<int:iid>', methods=['DELETE'])
    def api_incidents_delete(iid):
        db = get_db()
        db.execute('DELETE FROM incidents WHERE id = ?', (iid,))
        db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    @app.route('/api/incidents/clear', methods=['POST'])
    def api_incidents_clear():
        db = get_db()
        db.execute('DELETE FROM incidents')
        db.commit()
        db.close()
        return jsonify({'status': 'cleared'})

    # ─── Waypoints API ─────────────────────────────────────────────────

    WAYPOINT_CATEGORIES = ['rally', 'water', 'cache', 'shelter', 'hazard', 'medical', 'comms', 'general']
    WAYPOINT_COLORS = {'rally': '#5b9fff', 'water': '#4fc3f7', 'cache': '#ff9800', 'shelter': '#4caf50',
                       'hazard': '#f44336', 'medical': '#e91e63', 'comms': '#b388ff', 'general': '#9e9e9e'}

    @app.route('/api/waypoints')
    def api_waypoints_list():
        db = get_db()
        rows = db.execute('SELECT * FROM waypoints ORDER BY created_at DESC').fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/waypoints', methods=['POST'])
    def api_waypoints_create():
        data = request.get_json() or {}
        cat = data.get('category', 'general')
        color = WAYPOINT_COLORS.get(cat, '#9e9e9e')
        db = get_db()
        cur = db.execute('INSERT INTO waypoints (name, lat, lng, category, color, notes) VALUES (?, ?, ?, ?, ?, ?)',
                         (data.get('name', 'Waypoint'), data.get('lat', 0), data.get('lng', 0),
                          cat, color, data.get('notes', '')))
        db.commit()
        row = db.execute('SELECT * FROM waypoints WHERE id = ?', (cur.lastrowid,)).fetchone()
        db.close()
        return jsonify(dict(row)), 201

    @app.route('/api/waypoints/<int:wid>', methods=['DELETE'])
    def api_waypoints_delete(wid):
        db = get_db()
        db.execute('DELETE FROM waypoints WHERE id = ?', (wid,))
        db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    # ─── Map Routes & Annotations API ────────────────────────────────

    @app.route('/api/maps/routes')
    def api_map_routes_list():
        db = get_db()
        rows = db.execute('SELECT * FROM map_routes ORDER BY created_at DESC').fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/maps/routes', methods=['POST'])
    def api_map_routes_create():
        data = request.get_json() or {}
        db = get_db()
        try:
            db.execute('INSERT INTO map_routes (name, waypoint_ids, distance_km, estimated_time_min, terrain_difficulty, notes) VALUES (?,?,?,?,?,?)',
                       (data.get('name', 'New Route'), json.dumps(data.get('waypoint_ids', [])),
                        data.get('distance_km', 0), data.get('estimated_time_min', 0),
                        data.get('terrain_difficulty', 'moderate'), data.get('notes', '')))
            db.commit()
            rid = db.execute('SELECT last_insert_rowid()').fetchone()[0]
            return jsonify({'status': 'created', 'id': rid})
        finally:
            db.close()

    @app.route('/api/maps/routes/<int:rid>', methods=['DELETE'])
    def api_map_routes_delete(rid):
        db = get_db()
        db.execute('DELETE FROM map_routes WHERE id = ?', (rid,))
        db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    @app.route('/api/maps/annotations')
    def api_map_annotations_list():
        db = get_db()
        rows = db.execute('SELECT * FROM map_annotations ORDER BY created_at DESC').fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/maps/annotations', methods=['POST'])
    def api_map_annotations_create():
        data = request.get_json() or {}
        db = get_db()
        try:
            db.execute('INSERT INTO map_annotations (type, geojson, label, color, notes) VALUES (?,?,?,?,?)',
                       (data.get('type', 'polygon'), json.dumps(data.get('geojson', {})),
                        data.get('label', ''), data.get('color', '#ff0000'), data.get('notes', '')))
            db.commit()
            aid = db.execute('SELECT last_insert_rowid()').fetchone()[0]
            return jsonify({'status': 'created', 'id': aid})
        finally:
            db.close()

    @app.route('/api/maps/annotations/<int:aid>', methods=['DELETE'])
    def api_map_annotations_delete(aid):
        db = get_db()
        db.execute('DELETE FROM map_annotations WHERE id = ?', (aid,))
        db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    @app.route('/api/maps/minimap-data')
    def api_maps_minimap_data():
        """Returns waypoints + annotations for the dashboard mini-map widget."""
        db = get_db()
        waypoints = [dict(r) for r in db.execute('SELECT id, name, lat, lng, category, icon, color FROM waypoints ORDER BY name').fetchall()]
        routes = [dict(r) for r in db.execute('SELECT id, name, waypoint_ids, distance_km FROM map_routes ORDER BY created_at DESC LIMIT 10').fetchall()]
        annotations = [dict(r) for r in db.execute('SELECT id, type, label, color FROM map_annotations ORDER BY created_at DESC LIMIT 20').fetchall()]
        db.close()
        return jsonify({'waypoints': waypoints, 'routes': routes, 'annotations': annotations})

    # ─── Comms / Frequency Database API ─────────────────────────────

    @app.route('/api/comms/frequencies')
    def api_comms_frequencies():
        db = get_db()
        rows = db.execute('SELECT * FROM freq_database ORDER BY service, frequency').fetchall()
        db.close()
        # If empty, seed with standard frequencies
        if not rows:
            _seed_frequencies()
            db = get_db()
            rows = db.execute('SELECT * FROM freq_database ORDER BY service, frequency').fetchall()
            db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/comms/frequencies', methods=['POST'])
    def api_comms_freq_create():
        data = request.get_json() or {}
        db = get_db()
        db.execute('INSERT INTO freq_database (frequency, mode, bandwidth, service, description, region, license_required, priority, notes) VALUES (?,?,?,?,?,?,?,?,?)',
                   (data.get('frequency', 0), data.get('mode', 'FM'), data.get('bandwidth', ''),
                    data.get('service', ''), data.get('description', ''), data.get('region', 'US'),
                    data.get('license_required', 0), data.get('priority', 0), data.get('notes', '')))
        db.commit()
        db.close()
        return jsonify({'status': 'created'})

    @app.route('/api/comms/frequencies/<int:fid>', methods=['DELETE'])
    def api_comms_freq_delete(fid):
        db = get_db()
        db.execute('DELETE FROM freq_database WHERE id = ?', (fid,))
        db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    def _seed_frequencies():
        """Seed standard emergency/preparedness frequencies."""
        db = get_db()
        freqs = [
            (462.5625,'FM','12.5','FRS/GMRS Ch 1','Family Radio — primary','US',0,10,'Most common FRS channel'),
            (462.5875,'FM','12.5','FRS/GMRS Ch 2','Family Radio — secondary','US',0,5,''),
            (462.6125,'FM','12.5','FRS/GMRS Ch 3','Family Radio — neighborhood','US',0,5,''),
            (462.6375,'FM','12.5','FRS/GMRS Ch 4','Family Radio','US',0,3,''),
            (462.6625,'FM','12.5','FRS/GMRS Ch 5','Family Radio','US',0,3,''),
            (462.6875,'FM','12.5','FRS/GMRS Ch 6','Family Radio','US',0,3,''),
            (462.7125,'FM','12.5','FRS/GMRS Ch 7','Family Radio','US',0,3,''),
            (467.5625,'FM','12.5','FRS Ch 8','FRS only (low power)','US',0,2,''),
            (151.820,'FM','11.25','MURS Ch 1','Multi-Use Radio — no license','US',0,8,'5W max, good for property'),
            (151.880,'FM','11.25','MURS Ch 2','Multi-Use Radio','US',0,5,''),
            (151.940,'FM','11.25','MURS Ch 3','Multi-Use Radio','US',0,5,''),
            (154.570,'FM','20','MURS Ch 4','Multi-Use Radio (wide)','US',0,4,''),
            (154.600,'FM','20','MURS Ch 5','Multi-Use Radio (wide)','US',0,4,''),
            (146.520,'FM','15','2m Simplex Call','National VHF calling frequency','US',1,10,'Ham license required'),
            (146.550,'FM','15','2m Simplex','Common simplex — ARES/RACES','US',1,7,''),
            (147.420,'FM','15','2m Simplex','Emergency simplex','US',1,6,''),
            (446.000,'FM','12.5','70cm Simplex Call','National UHF calling frequency','US',1,9,'Ham license required'),
            (446.500,'FM','12.5','70cm Simplex','Common UHF simplex','US',1,5,''),
            (7.260,'LSB','3','40m SSB','Emergency HF net — regional','US',1,10,'Day propagation 100-500mi'),
            (3.860,'LSB','3','75m SSB','Emergency HF net — regional','US',1,8,'Night propagation'),
            (14.300,'USB','3','20m SSB','International distress/emergency net','US',1,9,'Long-distance day'),
            (156.800,'FM','25','Marine Ch 16','International distress/calling','US',0,10,'Monitored by Coast Guard'),
            (156.450,'FM','25','Marine Ch 9','Secondary calling channel','US',0,5,''),
            (27.065,'AM','8','CB Ch 9','Emergency CB channel','US',0,8,'Monitored by REACT'),
            (27.185,'AM','8','CB Ch 19','Highway/trucker channel','US',0,6,'Good for road intel'),
            (162.400,'FM','','NOAA WX 1','Weather broadcast','US',0,10,'Check for your area'),
            (162.425,'FM','','NOAA WX 2','Weather broadcast','US',0,10,''),
            (162.450,'FM','','NOAA WX 3','Weather broadcast','US',0,10,''),
            (162.475,'FM','','NOAA WX 4','Weather broadcast','US',0,10,''),
            (162.500,'FM','','NOAA WX 5','Weather broadcast','US',0,10,''),
            (162.525,'FM','','NOAA WX 6','Weather broadcast','US',0,10,''),
            (162.550,'FM','','NOAA WX 7','Weather broadcast','US',0,10,''),
            (121.500,'AM','','Aviation Emer','Aircraft emergency/guard','US',0,7,'International air distress'),
            (243.000,'AM','','Military Emer','Military UHF guard frequency','US',0,4,''),
            (906.875,'LoRa','125','Meshtastic US','Default Meshtastic — off-grid text','US',0,9,'No license, 1W'),
        ]
        for f in freqs:
            db.execute('INSERT OR IGNORE INTO freq_database (frequency, mode, bandwidth, service, description, region, license_required, priority, notes) VALUES (?,?,?,?,?,?,?,?,?)', f)
        db.commit()
        db.close()

    @app.route('/api/comms/dashboard')
    def api_comms_dashboard():
        """Comms status overview — last contacts, active frequencies, mesh status."""
        db = get_db()
        try:
            last_logs = [dict(r) for r in db.execute('SELECT callsign, freq, direction, created_at FROM comms_log ORDER BY created_at DESC LIMIT 5').fetchall()]
            freq_count = db.execute('SELECT COUNT(*) as c FROM freq_database').fetchone()['c']
            contacts_with_radio = db.execute("SELECT COUNT(*) as c FROM contacts WHERE callsign != ''").fetchone()['c']
            profiles = db.execute('SELECT COUNT(*) as c FROM radio_profiles').fetchone()['c']
            return jsonify({
                'recent_logs': last_logs,
                'freq_count': freq_count,
                'radio_contacts': contacts_with_radio,
                'radio_profiles': profiles,
            })
        finally:
            db.close()

    @app.route('/api/comms/radio-profiles')
    def api_comms_profiles_list():
        db = get_db()
        rows = db.execute('SELECT * FROM radio_profiles ORDER BY name').fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/comms/radio-profiles', methods=['POST'])
    def api_comms_profiles_create():
        data = request.get_json() or {}
        db = get_db()
        db.execute('INSERT INTO radio_profiles (radio_model, name, channels) VALUES (?,?,?)',
                   (data.get('radio_model', ''), data.get('name', 'New Profile'), json.dumps(data.get('channels', []))))
        db.commit()
        db.close()
        return jsonify({'status': 'created'})

    @app.route('/api/comms/radio-profiles/<int:pid>', methods=['DELETE'])
    def api_comms_profiles_delete(pid):
        db = get_db()
        db.execute('DELETE FROM radio_profiles WHERE id = ?', (pid,))
        db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    WAYPOINT_ICONS = {
        'pin': '&#128205;', 'home': '&#127968;', 'water': '&#128167;', 'cache': '&#128230;',
        'rally': '&#127937;', 'danger': '&#9888;', 'shelter': '&#9978;', 'medical': '&#9829;',
        'radio': '&#128225;', 'observation': '&#128065;', 'gate': '&#128682;', 'fuel': '&#9981;',
    }

    @app.route('/api/maps/waypoint-icons')
    def api_waypoint_icons():
        return jsonify(WAYPOINT_ICONS)

    # ─── Timers API ───────────────────────────────────────────────────

    @app.route('/api/timers')
    def api_timers_list():
        db = get_db()
        rows = db.execute('SELECT * FROM timers ORDER BY created_at DESC').fetchall()
        db.close()
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
        db = get_db()
        db.execute('DELETE FROM timers WHERE id = ?', (tid,))
        db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    # ─── CSV Export API ───────────────────────────────────────────────

    @app.route('/api/inventory/export-csv')
    def api_inventory_csv():
        db = get_db()
        rows = db.execute('SELECT name, category, quantity, unit, min_quantity, daily_usage, location, expiration, notes FROM inventory ORDER BY category, name').fetchall()
        db.close()
        import csv, io
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['Name', 'Category', 'Quantity', 'Unit', 'Min Qty', 'Daily Usage', 'Location', 'Expiration', 'Notes'])
        for r in rows:
            w.writerow([r['name'], r['category'], r['quantity'], r['unit'], r['min_quantity'], r['daily_usage'], r['location'], r['expiration'], r['notes']])
        return Response(buf.getvalue(), mimetype='text/csv',
                       headers={'Content-Disposition': 'attachment; filename="nomad-inventory.csv"'})

    @app.route('/api/contacts/export-csv')
    def api_contacts_csv():
        db = get_db()
        rows = db.execute('SELECT name, callsign, role, skills, phone, freq, email, address, rally_point, blood_type, medical_notes, notes FROM contacts ORDER BY name').fetchall()
        db.close()
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
        db = get_db()
        rows = db.execute('SELECT id, title, created_at, updated_at FROM vault_entries ORDER BY updated_at DESC').fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/vault', methods=['POST'])
    def api_vault_create():
        data = request.get_json() or {}
        for field in ('encrypted_data', 'iv', 'salt'):
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        db = get_db()
        cur = db.execute('INSERT INTO vault_entries (title, encrypted_data, iv, salt) VALUES (?, ?, ?, ?)',
                         (data.get('title', 'Untitled'), data['encrypted_data'], data['iv'], data['salt']))
        db.commit()
        eid = cur.lastrowid
        db.close()
        return jsonify({'id': eid, 'status': 'saved'}), 201

    @app.route('/api/vault/<int:eid>')
    def api_vault_get(eid):
        db = get_db()
        row = db.execute('SELECT * FROM vault_entries WHERE id = ?', (eid,)).fetchone()
        db.close()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        return jsonify(dict(row))

    @app.route('/api/vault/<int:eid>', methods=['PUT'])
    def api_vault_update(eid):
        data = request.get_json() or {}
        for field in ('encrypted_data', 'iv', 'salt'):
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        db = get_db()
        db.execute('UPDATE vault_entries SET title = ?, encrypted_data = ?, iv = ?, salt = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                   (data.get('title', ''), data['encrypted_data'], data['iv'], data['salt'], eid))
        db.commit()
        db.close()
        return jsonify({'status': 'saved'})

    @app.route('/api/vault/<int:eid>', methods=['DELETE'])
    def api_vault_delete(eid):
        db = get_db()
        db.execute('DELETE FROM vault_entries WHERE id = ?', (eid,))
        db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    # ─── Weather Log API ──────────────────────────────────────────────

    @app.route('/api/weather')
    def api_weather_list():
        db = get_db()
        limit = request.args.get('limit', 50, type=int)
        rows = db.execute('SELECT * FROM weather_log ORDER BY created_at DESC LIMIT ?', (limit,)).fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/weather', methods=['POST'])
    def api_weather_create():
        data = request.get_json() or {}
        db = get_db()
        cur = db.execute(
            'INSERT INTO weather_log (pressure_hpa, temp_f, wind_dir, wind_speed, clouds, precip, visibility, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (data.get('pressure_hpa'), data.get('temp_f'), data.get('wind_dir', ''),
             data.get('wind_speed', ''), data.get('clouds', ''), data.get('precip', ''),
             data.get('visibility', ''), data.get('notes', '')))
        db.commit()
        row = db.execute('SELECT * FROM weather_log WHERE id = ?', (cur.lastrowid,)).fetchone()
        db.close()
        return jsonify(dict(row)), 201

    @app.route('/api/weather/trend')
    def api_weather_trend():
        """Return pressure trend for weather prediction."""
        db = get_db()
        rows = db.execute('SELECT pressure_hpa, created_at FROM weather_log WHERE pressure_hpa IS NOT NULL ORDER BY created_at DESC LIMIT 10').fetchall()
        db.close()
        if len(rows) < 2:
            return jsonify({'trend': 'insufficient', 'prediction': 'Need at least 2 pressure readings', 'readings': len(rows)})
        newest = rows[0]['pressure_hpa']
        oldest = rows[-1]['pressure_hpa']
        diff = newest - oldest
        if diff > 3:
            trend, pred = 'rising_fast', 'Fair weather coming. Clearing skies likely.'
        elif diff > 1:
            trend, pred = 'rising', 'Weather improving. Gradual clearing.'
        elif diff < -3:
            trend, pred = 'falling_fast', 'Storm approaching! Prepare for severe weather within 12-24 hours.'
        elif diff < -1:
            trend, pred = 'falling', 'Weather deteriorating. Rain/wind likely within 24 hours.'
        else:
            trend, pred = 'steady', 'Stable conditions. Current weather pattern continuing.'
        return jsonify({'trend': trend, 'prediction': pred, 'diff_hpa': round(diff, 1),
                       'current': newest, 'readings': len(rows)})

    @app.route('/api/dashboard/overview')
    def api_dashboard_overview():
        """Quick overview for command dashboard."""
        db = get_db()
        from datetime import datetime, timedelta

        # Active timers
        timer_count = db.execute('SELECT COUNT(*) as c FROM timers').fetchone()['c']

        # Low stock
        low_stock = db.execute('SELECT COUNT(*) as c FROM inventory WHERE quantity <= min_quantity AND min_quantity > 0').fetchone()['c']

        # Expiring soon (30 days)
        soon = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        today = datetime.now().strftime('%Y-%m-%d')
        expiring = db.execute("SELECT COUNT(*) as c FROM inventory WHERE expiration != '' AND expiration <= ? AND expiration >= ?", (soon, today)).fetchone()['c']

        # Recent incidents (24h)
        recent_incidents = db.execute("SELECT COUNT(*) as c FROM incidents WHERE created_at >= datetime('now', '-24 hours')").fetchone()['c']

        # Situation board
        settings = {r['key']: r['value'] for r in db.execute('SELECT key, value FROM settings').fetchall()}
        sit = {}
        try:
            sit = json.loads(settings.get('sit_board', '{}'))
        except Exception:
            pass

        # Weather trend
        pressure_rows = db.execute('SELECT pressure_hpa FROM weather_log WHERE pressure_hpa IS NOT NULL ORDER BY created_at DESC LIMIT 3').fetchall()

        db.close()

        return jsonify({
            'timers': timer_count, 'low_stock': low_stock, 'expiring': expiring,
            'recent_incidents': recent_incidents, 'situation': sit,
            'pressure_current': pressure_rows[0]['pressure_hpa'] if pressure_rows else None,
        })

    @app.route('/api/dashboard/live')
    def api_dashboard_live():
        """Single aggregated endpoint for the live situational dashboard.
        Returns data from all modules in one request — designed for auto-refresh."""
        db = get_db()
        try:
            from datetime import datetime, timedelta
            now = datetime.now()
            today = now.strftime('%Y-%m-%d')
            soon30 = (now + timedelta(days=30)).strftime('%Y-%m-%d')
            soon7 = (now + timedelta(days=7)).strftime('%Y-%m-%d')

            # Inventory
            inv_total = db.execute('SELECT COUNT(*) as c FROM inventory').fetchone()['c']
            inv_low = db.execute('SELECT COUNT(*) as c FROM inventory WHERE quantity <= min_quantity AND min_quantity > 0').fetchone()['c']
            inv_expiring = db.execute("SELECT COUNT(*) as c FROM inventory WHERE expiration != '' AND expiration <= ? AND expiration >= ?", (soon30, today)).fetchone()['c']
            inv_critical = db.execute("SELECT COUNT(*) as c FROM inventory WHERE expiration != '' AND expiration <= ? AND expiration >= ?", (soon7, today)).fetchone()['c']
            # Burn rate — items with daily usage
            burn_items = db.execute('SELECT name, quantity, daily_usage FROM inventory WHERE daily_usage > 0 ORDER BY (quantity / daily_usage) ASC LIMIT 5').fetchall()
            burn_rates = [{'name': r['name'], 'days_left': round(r['quantity'] / r['daily_usage'], 1) if r['daily_usage'] > 0 else 999} for r in burn_items]

            # Contacts
            contacts_total = db.execute('SELECT COUNT(*) as c FROM contacts').fetchone()['c']

            # Medical
            patients_active = db.execute('SELECT COUNT(*) as c FROM patients').fetchone()['c']

            # Security
            cameras_active = db.execute("SELECT COUNT(*) as c FROM cameras WHERE status = 'active'").fetchone()['c']
            access_24h = db.execute("SELECT COUNT(*) as c FROM access_log WHERE created_at >= datetime('now', '-24 hours')").fetchone()['c']
            incidents_24h = db.execute("SELECT COUNT(*) as c FROM incidents WHERE created_at >= datetime('now', '-24 hours')").fetchone()['c']

            # Power
            power_latest = db.execute('SELECT * FROM power_log ORDER BY created_at DESC LIMIT 1').fetchone()
            power_data = dict(power_latest) if power_latest else {}

            # Garden
            plots_active = db.execute('SELECT COUNT(*) as c FROM garden_plots').fetchone()['c']
            livestock_count = db.execute('SELECT COUNT(*) as c FROM livestock').fetchone()['c']
            recent_harvests = db.execute("SELECT COUNT(*) as c FROM harvest_log WHERE created_at >= datetime('now', '-7 days')").fetchone()['c']

            # Weather
            weather_latest = db.execute('SELECT * FROM weather_log ORDER BY created_at DESC LIMIT 1').fetchone()
            weather_data = dict(weather_latest) if weather_latest else {}
            pressure_trend_rows = db.execute('SELECT pressure_hpa FROM weather_log WHERE pressure_hpa IS NOT NULL ORDER BY created_at DESC LIMIT 5').fetchall()
            pressures = [r['pressure_hpa'] for r in pressure_trend_rows]
            pressure_trend = 'stable'
            if len(pressures) >= 2:
                diff = pressures[0] - pressures[-1]
                pressure_trend = 'rising' if diff > 1 else 'falling' if diff < -1 else 'stable'

            # Comms
            last_comms = db.execute('SELECT created_at FROM comms_log ORDER BY created_at DESC LIMIT 1').fetchone()

            # Fuel
            fuel_total = db.execute('SELECT COALESCE(SUM(quantity), 0) as t FROM fuel_storage').fetchone()['t']

            # Alerts
            alerts_active = db.execute("SELECT COUNT(*) as c FROM alerts WHERE dismissed = 0").fetchone()['c']
            alerts_critical = db.execute("SELECT COUNT(*) as c FROM alerts WHERE dismissed = 0 AND severity = 'critical'").fetchone()['c']

            # Equipment overdue
            equip_overdue = db.execute("SELECT COUNT(*) as c FROM equipment_log WHERE next_service != '' AND next_service <= ?", (today,)).fetchone()['c']

            # Situation board
            sit_raw = db.execute("SELECT value FROM settings WHERE key = 'sit_board'").fetchone()
            situation = {}
            if sit_raw and sit_raw['value']:
                try:
                    situation = json.loads(sit_raw['value'])
                except Exception:
                    pass

            # Federation peers
            peers_online = 0
            try:
                peers_online = db.execute("SELECT COUNT(*) as c FROM sync_log WHERE created_at >= datetime('now', '-1 hour')").fetchone()['c']
            except Exception:
                pass

            return jsonify({
                'inventory': {'total': inv_total, 'low_stock': inv_low, 'expiring_30d': inv_expiring, 'critical_7d': inv_critical, 'burn_rates': burn_rates},
                'contacts': {'total': contacts_total},
                'medical': {'patients': patients_active},
                'security': {'cameras': cameras_active, 'access_24h': access_24h, 'incidents_24h': incidents_24h},
                'power': power_data,
                'garden': {'plots': plots_active, 'livestock': livestock_count, 'harvests_7d': recent_harvests},
                'weather': {'latest': weather_data, 'pressure_trend': pressure_trend},
                'comms': {'last_contact': last_comms['created_at'] if last_comms else None},
                'fuel': {'total_gallons': fuel_total},
                'alerts': {'active': alerts_active, 'critical': alerts_critical},
                'equipment': {'overdue': equip_overdue},
                'situation': situation,
                'federation': {'peers_recent': peers_online},
            })
        finally:
            db.close()

    # ─── CSV Import API ────────────────────────────────────────────────

    @app.route('/api/inventory/import-csv', methods=['POST'])
    def api_inventory_import_csv():
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
            db = get_db()
            imported = 0
            for row in reader:
                name = row.get('Name', row.get('name', '')).strip()
                if not name:
                    continue
                db.execute(
                    'INSERT INTO inventory (name, category, quantity, unit, min_quantity, daily_usage, location, expiration, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (name, row.get('Category', row.get('category', 'other')),
                     float(row.get('Quantity', row.get('quantity', 0)) or 0),
                     row.get('Unit', row.get('unit', 'ea')),
                     float(row.get('Min Qty', row.get('min_quantity', 0)) or 0),
                     float(row.get('Daily Usage', row.get('daily_usage', 0)) or 0),
                     row.get('Location', row.get('location', '')),
                     row.get('Expiration', row.get('expiration', '')),
                     row.get('Notes', row.get('notes', ''))))
                imported += 1
            db.commit()
            db.close()
            return jsonify({'status': 'imported', 'count': imported})
        except Exception as e:
            log.error(f'Inventory CSV import failed: {e}')
            return jsonify({'error': f'Import failed: {e}'}), 500

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
            db = get_db()
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
            db.close()
            return jsonify({'status': 'imported', 'count': imported})
        except Exception as e:
            log.error(f'Contacts CSV import failed: {e}')
            return jsonify({'error': f'Import failed: {e}'}), 500

    # ─── Full Data Export ─────────────────────────────────────────────

    @app.route('/api/export-all')
    def api_export_all():
        """Export complete database + settings as a single ZIP."""
        try:
            import io
            import zipfile as zf
            from db import get_db_path

            buf = io.BytesIO()
            with zf.ZipFile(buf, 'w', zf.ZIP_DEFLATED) as z:
                db_path = get_db_path()
                if os.path.isfile(db_path):
                    z.write(db_path, 'nomad.db')
                try:
                    from config import get_config_path
                    cfg_path = get_config_path()
                    if os.path.isfile(cfg_path):
                        z.write(cfg_path, 'config.json')
                except Exception:
                    pass
            buf.seek(0)
            from datetime import datetime
            fname = f'nomad-full-backup-{datetime.now().strftime("%Y%m%d-%H%M%S")}.zip'
            return Response(buf.read(), mimetype='application/zip',
                           headers={'Content-Disposition': f'attachment; filename="{fname}"'})
        except Exception as e:
            log.error(f'Full export failed: {e}')
            return jsonify({'error': str(e)}), 500

    # ─── Video Library API ─────────────────────────────────────────────

    # ─── Media / Video Library API ──────────────────────────────────────

    def get_video_dir():
        path = os.path.join(get_data_dir(), 'videos')
        os.makedirs(path, exist_ok=True)
        return path

    def get_ytdlp_path():
        from platform_utils import IS_WINDOWS, IS_MACOS
        if IS_WINDOWS:
            name = 'yt-dlp.exe'
        elif IS_MACOS:
            name = 'yt-dlp_macos'
        else:
            name = 'yt-dlp_linux'
        return os.path.join(get_services_dir(), 'yt-dlp', name)

    VIDEO_CATEGORIES = ['survival', 'medical', 'repair', 'bushcraft', 'cooking', 'radio', 'farming', 'defense', 'general']

    def _get_ytdlp_url():
        from platform_utils import IS_WINDOWS, IS_MACOS
        base = 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/'
        if IS_WINDOWS:
            return base + 'yt-dlp.exe'
        elif IS_MACOS:
            return base + 'yt-dlp_macos'
        return base + 'yt-dlp_linux'

    _ytdlp_downloads = {}  # id -> {status, percent, title, speed, error}
    _ytdlp_dl_counter = 0
    _ytdlp_dl_lock = threading.Lock()

    # Curated prepper video catalog — top offline survival content
    PREPPER_CATALOG = [
        # Water & Sanitation
        {'title': 'How to Purify Water in a Survival Situation', 'url': 'https://www.youtube.com/watch?v=wEBYmeVwCeA', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Water & Sanitation'},
        {'title': 'DIY Water Filter - How to Make a Homemade Water Filter', 'url': 'https://www.youtube.com/watch?v=z4yBzMKxH_A', 'channel': 'Practical Engineering', 'category': 'survival', 'folder': 'Water & Sanitation'},
        {'title': 'How to Find and Purify Water | Survival Skills', 'url': 'https://www.youtube.com/watch?v=mV3L6w0n1jI', 'channel': 'Coalcracker Bushcraft', 'category': 'bushcraft', 'folder': 'Water & Sanitation'},
        # Food & Foraging
        {'title': 'Long Term Food Storage - A Beginners Guide', 'url': 'https://www.youtube.com/watch?v=OGkRUHl-dbw', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Food & Storage'},
        {'title': 'Canning 101: Start Here', 'url': 'https://www.youtube.com/watch?v=EqkXsVBjPJA', 'channel': 'Homesteading Family', 'category': 'cooking', 'folder': 'Food & Storage'},
        {'title': '37 Survival Foods Every Prepper Should Stockpile', 'url': 'https://www.youtube.com/watch?v=jLIWqg5Cjhc', 'channel': 'Canadian Prepper', 'category': 'survival', 'folder': 'Food & Storage'},
        {'title': '20 Wild Edibles You Can Forage for Survival', 'url': 'https://www.youtube.com/watch?v=ZPJPONHGf-0', 'channel': 'Black Scout Survival', 'category': 'bushcraft', 'folder': 'Food & Storage'},
        # First Aid & Medical
        {'title': 'Wilderness First Aid Basics', 'url': 'https://www.youtube.com/watch?v=JR2IABjLJBY', 'channel': 'Corporals Corner', 'category': 'medical', 'folder': 'First Aid & Medical'},
        {'title': 'Stop the Bleed - Tourniquet Application', 'url': 'https://www.youtube.com/watch?v=CSiuSIFDcuI', 'channel': 'Tactical Rifleman', 'category': 'medical', 'folder': 'First Aid & Medical'},
        {'title': 'Trauma Bag Essentials — Building an IFAK for Field Use', 'url': 'https://www.youtube.com/watch?v=VBuF3QKsN7o', 'channel': 'Skinny Medic', 'category': 'medical', 'folder': 'First Aid & Medical'},
        {'title': 'The Ultimate First Aid Kit Build', 'url': 'https://www.youtube.com/watch?v=MX0kB-x_XPg', 'channel': 'The Urban Prepper', 'category': 'medical', 'folder': 'First Aid & Medical'},
        # Shelter & Construction
        {'title': 'How to Build a Survival Shelter', 'url': 'https://www.youtube.com/watch?v=jfOC1ywRY3M', 'channel': 'Corporals Corner', 'category': 'bushcraft', 'folder': 'Shelter & Construction'},
        {'title': '5 Shelters Everyone Should Know How to Build', 'url': 'https://www.youtube.com/watch?v=wZjKQwjdGF0', 'channel': 'Coalcracker Bushcraft', 'category': 'bushcraft', 'folder': 'Shelter & Construction'},
        {'title': 'Off Grid Cabin Build - Start to Finish', 'url': 'https://www.youtube.com/watch?v=YOJCRvjFpgQ', 'channel': 'My Self Reliance', 'category': 'repair', 'folder': 'Shelter & Construction'},
        # Fire & Energy
        {'title': '5 Ways to Start a Fire Without Matches', 'url': 'https://www.youtube.com/watch?v=lR-LrU0zA0Y', 'channel': 'Sensible Prepper', 'category': 'bushcraft', 'folder': 'Fire & Energy'},
        {'title': 'Solar Power for Beginners', 'url': 'https://www.youtube.com/watch?v=W0Miu0mihVE', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Fire & Energy'},
        {'title': 'DIY Solar Generator Build', 'url': 'https://www.youtube.com/watch?v=k_jVk2Q2sJY', 'channel': 'Full Spectrum Survival', 'category': 'repair', 'folder': 'Fire & Energy'},
        # Navigation & Communication
        {'title': 'Land Navigation with Map and Compass', 'url': 'https://www.youtube.com/watch?v=0cF0ovA3FtY', 'channel': 'Black Scout Survival', 'category': 'survival', 'folder': 'Navigation & Comms'},
        {'title': 'Ham Radio for Beginners - Get Your License', 'url': 'https://www.youtube.com/watch?v=WIsBdMdNfNI', 'channel': 'Tin Hat Ranch', 'category': 'radio', 'folder': 'Navigation & Comms'},
        {'title': 'GMRS vs Ham Radio - Which is Better for Preppers', 'url': 'https://www.youtube.com/watch?v=uK3cMvEpnqg', 'channel': 'Magic Prepper', 'category': 'radio', 'folder': 'Navigation & Comms'},
        # Security & Defense
        {'title': 'Home Security on a Budget', 'url': 'https://www.youtube.com/watch?v=AUxTRyqp5qg', 'channel': 'City Prepping', 'category': 'defense', 'folder': 'Security & Defense'},
        {'title': 'Perimeter Security for Your Property', 'url': 'https://www.youtube.com/watch?v=bNJYjw7VSzM', 'channel': 'Bear Independent', 'category': 'defense', 'folder': 'Security & Defense'},
        {'title': 'Night Vision on a Budget for Home Defense', 'url': 'https://www.youtube.com/watch?v=f8l2E7kk654', 'channel': 'Angry Prepper', 'category': 'defense', 'folder': 'Security & Defense'},
        # Farming & Homesteading
        {'title': 'Start a Survival Garden in 30 Days', 'url': 'https://www.youtube.com/watch?v=u3x0JPCHDOQ', 'channel': 'City Prepping', 'category': 'farming', 'folder': 'Farming & Homestead'},
        {'title': 'Raising Chickens 101 - Everything You Need to Know', 'url': 'https://www.youtube.com/watch?v=jbHhEsEJ99g', 'channel': 'Homesteading Family', 'category': 'farming', 'folder': 'Farming & Homestead'},
        {'title': 'Seed Saving for Beginners', 'url': 'https://www.youtube.com/watch?v=LtH7lkP8bAU', 'channel': 'Epic Gardening', 'category': 'farming', 'folder': 'Farming & Homestead'},
        # General Preparedness
        {'title': 'The Ultimate Prepper Guide for Beginners', 'url': 'https://www.youtube.com/watch?v=JVuxCgo8mWM', 'channel': 'Canadian Prepper', 'category': 'survival', 'folder': 'Getting Started'},
        {'title': 'Bug Out Bag Essentials - 2024 Build', 'url': 'https://www.youtube.com/watch?v=HSTrM0pXnCA', 'channel': 'The Urban Prepper', 'category': 'survival', 'folder': 'Getting Started'},
        {'title': 'Get Home Bag: The Most Important Bag You Can Have', 'url': 'https://www.youtube.com/watch?v=a_L4ilHQFPQ', 'channel': 'Sensible Prepper', 'category': 'survival', 'folder': 'Getting Started'},
        {'title': 'EMP Attack - How to Prepare and Protect Electronics', 'url': 'https://www.youtube.com/watch?v=bJh1yd1yRes', 'channel': 'Canadian Prepper', 'category': 'survival', 'folder': 'Threats & Scenarios'},
        {'title': 'Economic Collapse: How to Prepare', 'url': 'https://www.youtube.com/watch?v=xhmReScCzE4', 'channel': 'Full Spectrum Survival', 'category': 'survival', 'folder': 'Threats & Scenarios'},
        {'title': 'Nuclear War Survival - What You Need to Know', 'url': 'https://www.youtube.com/watch?v=_GNh3p1GFAI', 'channel': 'Canadian Prepper', 'category': 'defense', 'folder': 'Threats & Scenarios'},
        # Bushcraft & Wilderness Skills
        {'title': 'Top 10 Knots You Need to Know', 'url': 'https://www.youtube.com/watch?v=VrSBsqe23Qk', 'channel': 'Coalcracker Bushcraft', 'category': 'bushcraft', 'folder': 'Bushcraft Skills'},
        {'title': 'Trapping for Survival - Basics and Techniques', 'url': 'https://www.youtube.com/watch?v=vAjl4IpYZXk', 'channel': 'Reality Survival', 'category': 'bushcraft', 'folder': 'Bushcraft Skills'},
        {'title': 'Knife Sharpening - How to Get a Razor Edge', 'url': 'https://www.youtube.com/watch?v=tRfBA-lBs-4', 'channel': 'Corporals Corner', 'category': 'bushcraft', 'folder': 'Bushcraft Skills'},
        # Repair & Tools
        {'title': 'Basic Automotive Repair Everyone Should Know', 'url': 'https://www.youtube.com/watch?v=MbyJjkpgNBU', 'channel': 'ChrisFix', 'category': 'repair', 'folder': 'Repair & Tools'},
        {'title': 'Essential Hand Tools for Survival', 'url': 'https://www.youtube.com/watch?v=9XUsqYoSzxo', 'channel': 'Sensible Prepper', 'category': 'repair', 'folder': 'Repair & Tools'},
        # Water — Advanced
        {'title': 'Rainwater Harvesting System Build', 'url': 'https://www.youtube.com/watch?v=OSDP3DTHXKA', 'channel': 'Homesteading Family', 'category': 'survival', 'folder': 'Water & Sanitation'},
        {'title': 'How to Test Your Water for Contaminants', 'url': 'https://www.youtube.com/watch?v=3R2SHZPC8Hs', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Water & Sanitation'},
        {'title': 'Building a Berkey-Style Gravity Water Filter', 'url': 'https://www.youtube.com/watch?v=PeK1c1M9woo', 'channel': 'Engineer775', 'category': 'survival', 'folder': 'Water & Sanitation'},
        {'title': 'How to Find Water in the Wild', 'url': 'https://www.youtube.com/watch?v=nE0qnpJKj-E', 'channel': 'Corporals Corner', 'category': 'bushcraft', 'folder': 'Water & Sanitation'},
        # Food — Fermentation & Preservation
        {'title': 'Fermenting Vegetables at Home — Complete Beginner Guide', 'url': 'https://www.youtube.com/watch?v=Ng4gMB5ZOAM', 'channel': "Mary's Nest", 'category': 'cooking', 'folder': 'Food & Storage'},
        {'title': 'Sourdough Bread from Scratch — No Yeast', 'url': 'https://www.youtube.com/watch?v=sTAiDki_ABA', 'channel': "Mary's Nest", 'category': 'cooking', 'folder': 'Food & Storage'},
        {'title': 'Dehydrating Food for Long-Term Storage', 'url': 'https://www.youtube.com/watch?v=nZWNkFjJgqM', 'channel': 'Homesteading Family', 'category': 'cooking', 'folder': 'Food & Storage'},
        {'title': 'Making Jerky — Beef, Venison, or Any Meat', 'url': 'https://www.youtube.com/watch?v=hmWGRPh5Ew8', 'channel': 'Survival Russia', 'category': 'cooking', 'folder': 'Food & Storage'},
        {'title': 'Salt Curing Meat — Preservation Without Refrigeration', 'url': 'https://www.youtube.com/watch?v=CQyJBfUiXi4', 'channel': 'Townsends', 'category': 'cooking', 'folder': 'Food & Storage'},
        {'title': 'Freeze Drying at Home — What You Need to Know', 'url': 'https://www.youtube.com/watch?v=6FPFNuVGfzk', 'channel': 'Homesteading Family', 'category': 'cooking', 'folder': 'Food & Storage'},
        {'title': 'Smoking Meat for Preservation', 'url': 'https://www.youtube.com/watch?v=0lAj1MQH_NU', 'channel': 'Survival Dispatch', 'category': 'cooking', 'folder': 'Food & Storage'},
        # Medical — Advanced
        {'title': 'Wound Closure: When to Suture vs. Leave Open', 'url': 'https://www.youtube.com/watch?v=mfWahyERGBo', 'channel': 'Skinny Medic', 'category': 'medical', 'folder': 'First Aid & Medical'},
        {'title': 'Improvised Splinting and Fracture Management', 'url': 'https://www.youtube.com/watch?v=3zT5K35EbcU', 'channel': 'PrepMedic', 'category': 'medical', 'folder': 'First Aid & Medical'},
        {'title': 'CPR and AED Training — Full Course', 'url': 'https://www.youtube.com/watch?v=cosVBV96E2g', 'channel': 'Survival Dispatch', 'category': 'medical', 'folder': 'First Aid & Medical'},
        {'title': 'Dental Emergencies Without a Dentist', 'url': 'https://www.youtube.com/watch?v=7yWpLuQcYaE', 'channel': 'DrBones NurseAmy', 'category': 'medical', 'folder': 'First Aid & Medical'},
        {'title': 'TCCC — Care Under Fire and Tactical Field Care', 'url': 'https://www.youtube.com/watch?v=J6-nFr-pn4A', 'channel': 'Skinny Medic', 'category': 'medical', 'folder': 'First Aid & Medical'},
        {'title': 'Managing Infection Without Antibiotics', 'url': 'https://www.youtube.com/watch?v=1hpEL7Jy_HI', 'channel': 'DrBones NurseAmy', 'category': 'medical', 'folder': 'First Aid & Medical'},
        {'title': 'Herbal Medicine — Making Tinctures, Salves, and Poultices', 'url': 'https://www.youtube.com/watch?v=HQdXn_bDiIs', 'channel': 'HerbMentor', 'category': 'medical', 'folder': 'First Aid & Medical'},
        # Hunting, Trapping & Fishing
        {'title': 'Primitive Fish Traps — Weirs, Basket Traps, and Gill Nets', 'url': 'https://www.youtube.com/watch?v=K6uimXgxsHE', 'channel': 'Shawn Woods', 'category': 'bushcraft', 'folder': 'Hunting & Trapping'},
        {'title': 'Field Dressing a Deer — Complete Walkthrough', 'url': 'https://www.youtube.com/watch?v=VwFADTGiXWw', 'channel': 'deermeatfordinner', 'category': 'bushcraft', 'folder': 'Hunting & Trapping'},
        {'title': 'Ice Fishing for Survival — Gear-Free Methods', 'url': 'https://www.youtube.com/watch?v=qNP5qI1DRbM', 'channel': 'Survival Russia', 'category': 'bushcraft', 'folder': 'Hunting & Trapping'},
        {'title': 'Trotlines and Limb Lines — Passive Fish Catching', 'url': 'https://www.youtube.com/watch?v=pEGAg0E2p1w', 'channel': 'Reality Survival', 'category': 'bushcraft', 'folder': 'Hunting & Trapping'},
        # Farming & Homesteading
        {'title': 'Vermicomposting — Red Wigglers for Year-Round Fertilizer Production', 'url': 'https://www.youtube.com/watch?v=D5lSFrJd6xY', 'channel': 'Epic Gardening', 'category': 'farming', 'folder': 'Farming & Homestead'},
        {'title': 'Composting 101 — Building Soil from Scratch', 'url': 'https://www.youtube.com/watch?v=egyNJ9HKMeo', 'channel': 'Epic Gardening', 'category': 'farming', 'folder': 'Farming & Homestead'},
        {'title': 'Root Cellaring — No-Electricity Food Storage', 'url': 'https://www.youtube.com/watch?v=jnFGLUeOiTQ', 'channel': 'Homesteading Family', 'category': 'farming', 'folder': 'Farming & Homestead'},
        {'title': 'Building a Simple Greenhouse from Scratch', 'url': 'https://www.youtube.com/watch?v=ZSWInr7PpTs', 'channel': 'Arms Family Homestead', 'category': 'farming', 'folder': 'Farming & Homestead'},
        {'title': 'Backyard Beekeeping for Beginners', 'url': 'https://www.youtube.com/watch?v=MmLeKkEa7J0', 'channel': 'Stoney Ridge Farmer', 'category': 'farming', 'folder': 'Farming & Homestead'},
        # Energy & Power
        {'title': 'Whole House Backup Power — Generator Sizing Guide', 'url': 'https://www.youtube.com/watch?v=g4smHKnZMRU', 'channel': 'City Prepping', 'category': 'repair', 'folder': 'Fire & Energy'},
        {'title': 'DIY Battery Bank — LiFePO4 Build', 'url': 'https://www.youtube.com/watch?v=S3E1KfFUpA4', 'channel': 'DIY Solar Power (Will Prowse)', 'category': 'repair', 'folder': 'Fire & Energy'},
        {'title': 'Wind Turbine Build from Scratch', 'url': 'https://www.youtube.com/watch?v=Yw4oqaEyFq8', 'channel': 'Engineer775', 'category': 'repair', 'folder': 'Fire & Energy'},
        {'title': 'Propane Generator Conversion — Dual-Fuel for Grid-Down Reliability', 'url': 'https://www.youtube.com/watch?v=hMt-DXMFkBk', 'channel': 'Engineer775', 'category': 'repair', 'folder': 'Fire & Energy'},
        {'title': 'How to Split Firewood Efficiently', 'url': 'https://www.youtube.com/watch?v=wn4EbVaFsUE', 'channel': 'My Self Reliance', 'category': 'bushcraft', 'folder': 'Fire & Energy'},
        # Security & Defense
        {'title': 'Home Hardening — Making Your Home Harder to Break Into', 'url': 'https://www.youtube.com/watch?v=J5MBTS4VXBI', 'channel': 'City Prepping', 'category': 'defense', 'folder': 'Security & Defense'},
        {'title': 'Improvised Alarm Systems and Trip Wires', 'url': 'https://www.youtube.com/watch?v=mEXGD7bxCIQ', 'channel': 'Black Scout Survival', 'category': 'defense', 'folder': 'Security & Defense'},
        # Repair & Fabrication
        {'title': 'Basic Welding for Survival Repairs', 'url': 'https://www.youtube.com/watch?v=u4PMqS3JNXY', 'channel': 'ChrisFix', 'category': 'repair', 'folder': 'Repair & Tools'},
        {'title': 'Blacksmithing 101 — Fire Welding and Basic Forging', 'url': 'https://www.youtube.com/watch?v=f8T7P7EFuWY', 'channel': 'Black Bear Forge', 'category': 'repair', 'folder': 'Repair & Tools'},
        {'title': 'Small Engine Repair — Carburetors, Fuel, and Ignition', 'url': 'https://www.youtube.com/watch?v=NTRpXFgPBEo', 'channel': 'EricTheCarGuy', 'category': 'repair', 'folder': 'Repair & Tools'},
        {'title': 'Chainsaw Maintenance and Safe Operation', 'url': 'https://www.youtube.com/watch?v=LFe5vvCFqAE', 'channel': 'My Self Reliance', 'category': 'repair', 'folder': 'Repair & Tools'},
        # Navigation & Communications
        {'title': 'Celestial Navigation — Finding North by Stars', 'url': 'https://www.youtube.com/watch?v=LXiYW2CKVLQ', 'channel': 'Black Scout Survival', 'category': 'survival', 'folder': 'Navigation & Comms'},
        {'title': 'Building a Faraday Cage — EMP Protection for Electronics', 'url': 'https://www.youtube.com/watch?v=P5VT1q-kM7I', 'channel': 'Tin Hat Ranch', 'category': 'survival', 'folder': 'Navigation & Comms'},
        {'title': 'GMRS Radio Setup for Family and Community Comms', 'url': 'https://www.youtube.com/watch?v=HxbCHJ0XLGY', 'channel': 'Ham Radio Crash Course', 'category': 'radio', 'folder': 'Navigation & Comms'},
        # Mental / Psychological Preparedness
        {'title': 'SHTF Psychology — Managing Panic and Decision-Making Under Stress', 'url': 'https://www.youtube.com/watch?v=qxNjJPHzN-o', 'channel': 'Canadian Prepper', 'category': 'survival', 'folder': 'Getting Started'},
        {'title': 'Gray Man Concept — Avoiding Attention During Emergencies', 'url': 'https://www.youtube.com/watch?v=_sRjSR_B2Bc', 'channel': 'City Prepping', 'category': 'defense', 'folder': 'Security & Defense'},
        # Weather Reading & Meteorology
        {'title': 'How to Read a Barometer for Weather Forecasting', 'url': 'https://www.youtube.com/watch?v=sPklvTR5K8Y', 'channel': 'NWS Headquarters', 'category': 'survival', 'folder': 'Weather & Climate'},
        {'title': 'Cloud Identification — Forecasting Weather Without a Phone', 'url': 'https://www.youtube.com/watch?v=0k2bfJIr6gQ', 'channel': 'The COMET Program', 'category': 'survival', 'folder': 'Weather & Climate'},
        {'title': 'Understanding Doppler Radar for Preppers', 'url': 'https://www.youtube.com/watch?v=4M8HJRsn8Lc', 'channel': 'Ryan Hall Y\'all', 'category': 'survival', 'folder': 'Weather & Climate'},
        {'title': 'Tornado Safety — What to Do When There\'s No Shelter', 'url': 'https://www.youtube.com/watch?v=X8TBpYOzBnY', 'channel': 'NWS Headquarters', 'category': 'survival', 'folder': 'Weather & Climate'},
        {'title': 'NOAA Weather Radio Setup and Programming', 'url': 'https://www.youtube.com/watch?v=8cGZ1lFlZjQ', 'channel': 'Ham Radio Crash Course', 'category': 'radio', 'folder': 'Weather & Climate'},
        {'title': 'Reading NWS Forecast Discussions Like a Meteorologist', 'url': 'https://www.youtube.com/watch?v=PqVTcUnRFSM', 'channel': 'The COMET Program', 'category': 'survival', 'folder': 'Weather & Climate'},
        {'title': 'Flash Flood Recognition and Escape Routes', 'url': 'https://www.youtube.com/watch?v=kFdCsKm-fgg', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Weather & Climate'},
        {'title': 'Hurricane Season Preparation Timeline — Month by Month', 'url': 'https://www.youtube.com/watch?v=kV0Y1tPMjbs', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Weather & Climate'},
        {'title': 'Winter Storm Survival — Blizzard, Ice Storm, Power Outage', 'url': 'https://www.youtube.com/watch?v=1MYy2yGX3sg', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Weather & Climate'},
        {'title': 'Lightning Safety — Distance Calculation and Shelter Protocol', 'url': 'https://www.youtube.com/watch?v=Hd_O8Xiu4hM', 'channel': 'NWS Headquarters', 'category': 'survival', 'folder': 'Weather & Climate'},
        # Maps & Geospatial
        {'title': 'How to Read a Topographic Map — Contour Lines Explained', 'url': 'https://www.youtube.com/watch?v=CoVcn2LT56k', 'channel': 'REI', 'category': 'survival', 'folder': 'Navigation & Comms'},
        {'title': 'Download and Use Free Offline Maps with QGIS', 'url': 'https://www.youtube.com/watch?v=RTjAp6dqvsM', 'channel': 'GIS Geography', 'category': 'survival', 'folder': 'Navigation & Comms'},
        {'title': 'USGS Topographic Maps — Where to Download and How to Use', 'url': 'https://www.youtube.com/watch?v=BpFCOeR02SU', 'channel': 'USGS (US Geological Survey)', 'category': 'survival', 'folder': 'Navigation & Comms'},
        {'title': 'Reading FEMA Flood Maps — Know Your Risk Before It Floods', 'url': 'https://www.youtube.com/watch?v=kCr-b8NfLFo', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Navigation & Comms'},
        {'title': 'Geologic Maps — Identifying Water Sources, Soil, and Hazards', 'url': 'https://www.youtube.com/watch?v=G87c5b9bHXs', 'channel': 'USGS (US Geological Survey)', 'category': 'survival', 'folder': 'Navigation & Comms'},
        {'title': 'OpenStreetMap for Offline Survival — Download Any Region', 'url': 'https://www.youtube.com/watch?v=7oRvtRaKFYs', 'channel': 'geodesign', 'category': 'survival', 'folder': 'Navigation & Comms'},
        {'title': 'MGRS Grid Coordinates — Military Map Reading Explained', 'url': 'https://www.youtube.com/watch?v=mjdG-oBi4Mc', 'channel': 'Black Scout Survival', 'category': 'survival', 'folder': 'Navigation & Comms'},
        {'title': 'Terrain Analysis for Survival — Reading Land Features From a Map', 'url': 'https://www.youtube.com/watch?v=FDKf5pGNxuA', 'channel': 'Black Scout Survival', 'category': 'survival', 'folder': 'Navigation & Comms'},
        # Radio Skills Deep Dive
        {'title': 'Winlink Over HF Radio — Email Without Internet', 'url': 'https://www.youtube.com/watch?v=Vf3rD-5sHtc', 'channel': 'Ham Radio Crash Course', 'category': 'radio', 'folder': 'Navigation & Comms'},
        {'title': 'JS8Call Setup — Resilient Digital Messaging for Grid-Down', 'url': 'https://www.youtube.com/watch?v=xnVBSHoqE3Y', 'channel': 'KM4ACK (Jason Oleham)', 'category': 'radio', 'folder': 'Navigation & Comms'},
        {'title': 'SDR Basics — Receive Weather Satellites with a $25 Dongle', 'url': 'https://www.youtube.com/watch?v=5q3MWBQm9t4', 'channel': 'Signals Everywhere', 'category': 'radio', 'folder': 'Navigation & Comms'},
        {'title': 'APRS Tracking and Messaging — Automatic Packet Reporting System', 'url': 'https://www.youtube.com/watch?v=YGNi1PN4kIw', 'channel': 'Ham Radio Crash Course', 'category': 'radio', 'folder': 'Navigation & Comms'},
        {'title': 'Off-Grid Solar Powered Radio Station — HF on 10W', 'url': 'https://www.youtube.com/watch?v=BKJFhKBOIaA', 'channel': 'OH8STN Julian OH8STN', 'category': 'radio', 'folder': 'Navigation & Comms'},
        {'title': 'LoRa Meshtastic — Off-Grid Text Messaging With No License', 'url': 'https://www.youtube.com/watch?v=d_h38X4_pqY', 'channel': 'Andreas Spiess', 'category': 'radio', 'folder': 'Navigation & Comms'},
        # Advanced Homesteading & Aquaponics
        {'title': 'Aquaponics for Self-Sufficiency — Growing Fish and Vegetables Together', 'url': 'https://www.youtube.com/watch?v=aOBHVCeBfqI', 'channel': 'Bright Agrotech', 'category': 'farming', 'folder': 'Farming & Homestead'},
        {'title': 'Underground Rainwater Cistern Build — 2,500 Gallon Tank', 'url': 'https://www.youtube.com/watch?v=Fg1d8S9TwPc', 'channel': 'An American Homestead', 'category': 'survival', 'folder': 'Water & Sanitation'},
        {'title': 'Rocket Stove Build — 80% More Efficient Than an Open Fire', 'url': 'https://www.youtube.com/watch?v=Qr4y5TXtGPQ', 'channel': 'Paul Wheaton (Permies)', 'category': 'repair', 'folder': 'Fire & Energy'},
        {'title': 'Hand Drilling a Water Well — No Equipment Required', 'url': 'https://www.youtube.com/watch?v=2TM_HVvnEn4', 'channel': 'Practical Engineering', 'category': 'survival', 'folder': 'Water & Sanitation'},
        {'title': 'Foraging Wild Mushrooms — Safe Identification Framework', 'url': 'https://www.youtube.com/watch?v=wMwBGqPFmv0', 'channel': 'Learn Your Land', 'category': 'bushcraft', 'folder': 'Food & Storage'},
        {'title': 'Emergency Pet Evacuation — Bug Out With Dogs, Cats, and Livestock', 'url': 'https://www.youtube.com/watch?v=wQIj3v4ySXs', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Getting Started'},
        {'title': 'Grid-Down Cooking Methods — Dutch Oven, Solar Oven, Rocket Stove', 'url': 'https://www.youtube.com/watch?v=bMpRqT5zLXw', 'channel': 'Homesteading Family', 'category': 'cooking', 'folder': 'Food & Storage'},
        {'title': 'Tanning Deer Hide — Brain Tanning Method Step by Step', 'url': 'https://www.youtube.com/watch?v=nAWfIMOuLrs', 'channel': 'Far North Bushcraft And Survival', 'category': 'bushcraft', 'folder': 'Bushcraft Skills'},
        {'title': 'Hand Tool Woodworking — Joinery Without Power Tools', 'url': 'https://www.youtube.com/watch?v=rZ8bXUGN4WQ', 'channel': 'Paul Sellers', 'category': 'repair', 'folder': 'Shelter & Construction'},
        {'title': 'Security Communication Plan — Family Radio Protocols for SHTF', 'url': 'https://www.youtube.com/watch?v=wIsBdMdNfNI', 'channel': 'Tin Hat Ranch', 'category': 'radio', 'folder': 'Navigation & Comms'},
        # Veterinary & Animal Health
        {'title': 'Goat Health and Disease Prevention — Common Ailments Without a Vet', 'url': 'https://www.youtube.com/watch?v=qT2vLpHrNkE', 'channel': 'Becky\'s Homestead', 'category': 'farming', 'folder': 'Farming & Homestead'},
        {'title': 'Wound Care for Livestock — Suturing, Bandaging, and Infection Control', 'url': 'https://www.youtube.com/watch?v=yP8tJnF3xQs', 'channel': 'The Holistic Hen', 'category': 'medical', 'folder': 'First Aid & Medical'},
        # Nuclear & CBRN Response
        {'title': 'Fallout Shelter Improvisation — Using What You Have at Home', 'url': 'https://www.youtube.com/watch?v=nX4b7Lp8KrM', 'channel': 'Canadian Prepper', 'category': 'defense', 'folder': 'Threats & Scenarios'},
        {'title': 'KI Tablets and Thyroid Protection After Nuclear Event', 'url': 'https://www.youtube.com/watch?v=Wz9qRsLmpVk', 'channel': 'City Prepping', 'category': 'medical', 'folder': 'First Aid & Medical'},
        # Textiles & Clothing
        {'title': 'Hand Sewing Essentials — Repair Clothing Without a Machine', 'url': 'https://www.youtube.com/watch?v=eKq7vFNhgL8', 'channel': 'Make It and Love It', 'category': 'repair', 'folder': 'Repair & Tools'},
        {'title': 'Wool Processing — Shearing, Carding, Spinning, and Weaving', 'url': 'https://www.youtube.com/watch?v=uYFxJkMmCbQ', 'channel': 'Jas Townsend and Son', 'category': 'bushcraft', 'folder': 'Bushcraft Skills'},
        # Grid-Down Sanitation & Hygiene
        {'title': 'Emergency Sanitation Without Running Water — Composting Toilets and Latrines', 'url': 'https://www.youtube.com/watch?v=cZ6q3nHmTwP', 'channel': 'Practical Preppers', 'category': 'survival', 'folder': 'Water & Sanitation'},
        {'title': 'Making Lye Soap from Scratch — Wood Ash and Animal Fat', 'url': 'https://www.youtube.com/watch?v=mJ4vNkwXpFo', 'channel': 'Townsends', 'category': 'cooking', 'folder': 'Food & Storage'},
        # Advanced Medical
        {'title': 'IV Fluid Therapy in the Field — Indications, Setup, and Complications', 'url': 'https://www.youtube.com/watch?v=GzHnS4kqPLx', 'channel': 'PrepMedic', 'category': 'medical', 'folder': 'First Aid & Medical'},
        {'title': 'Airway Management Without Equipment — Head Tilt, Jaw Thrust, NPA Insertion', 'url': 'https://www.youtube.com/watch?v=FxKp9vNtJyq', 'channel': 'Skinny Medic', 'category': 'medical', 'folder': 'First Aid & Medical'},
        {'title': 'Burn Treatment in the Field — Degrees, Cooling, and Infection Prevention', 'url': 'https://www.youtube.com/watch?v=pNkWc4gBmTz', 'channel': 'Corporals Corner', 'category': 'medical', 'folder': 'First Aid & Medical'},
        # Construction Techniques
        {'title': 'Adobe Brick Making — Mixing, Forming, and Curing Earth Blocks', 'url': 'https://www.youtube.com/watch?v=TsKlqY6pXZn', 'channel': 'Open Source Ecology', 'category': 'repair', 'folder': 'Shelter & Construction'},
        {'title': 'Dry Stone Wall Construction — No Mortar, No Tools Required', 'url': 'https://www.youtube.com/watch?v=RwLvzJ8NfYm', 'channel': 'My Self Reliance', 'category': 'repair', 'folder': 'Shelter & Construction'},
        # Foraging Deep Dives
        {'title': 'Acorn Processing — Leaching Tannins and Grinding Flour', 'url': 'https://www.youtube.com/watch?v=9XFhvkRqPSw', 'channel': 'Learn Your Land', 'category': 'bushcraft', 'folder': 'Food & Storage'},
        {'title': 'Cattail — The Ultimate Survival Plant (Roots to Pollen)', 'url': 'https://www.youtube.com/watch?v=bLVnT4Gq7Yw', 'channel': 'Black Scout Survival', 'category': 'bushcraft', 'folder': 'Food & Storage'},
        # Communications — Advanced
        {'title': 'HF Radio Propagation — Understanding Bands and Gray Line', 'url': 'https://www.youtube.com/watch?v=mCqPvRsFKtN', 'channel': 'Radio Prepper', 'category': 'radio', 'folder': 'Navigation & Comms'},
        {'title': 'Emergency Antenna Build — NVIS Dipole from Wire and PVC', 'url': 'https://www.youtube.com/watch?v=vHk3YpJrQwG', 'channel': 'OH8STN Julian OH8STN', 'category': 'radio', 'folder': 'Navigation & Comms'},
    ]

    @app.route('/api/videos')
    def api_videos_list():
        db = get_db()
        rows = db.execute('SELECT * FROM videos ORDER BY folder, category, title').fetchall()
        db.close()
        videos = []
        vdir = get_video_dir()
        for r in rows:
            v = dict(r)
            # Verify file still exists on disk
            v['exists'] = os.path.isfile(os.path.join(vdir, r['filename']))
            videos.append(v)
        return jsonify(videos)

    @app.route('/api/videos/upload', methods=['POST'])
    def api_videos_upload():
        if 'file' not in request.files:
            return jsonify({'error': 'No file'}), 400
        file = request.files['file']
        filename = secure_filename(file.filename)
        if not filename:
            return jsonify({'error': 'Invalid filename'}), 400
        filepath = os.path.join(get_video_dir(), filename)
        file.save(filepath)
        filesize = os.path.getsize(filepath) if os.path.isfile(filepath) else 0
        category = request.form.get('category', 'general')
        folder = request.form.get('folder', '')
        title = request.form.get('title', filename.rsplit('.', 1)[0])
        db = get_db()
        cur = db.execute('INSERT INTO videos (title, filename, category, folder, filesize) VALUES (?, ?, ?, ?, ?)',
                         (title, filename, category, folder, filesize))
        db.commit()
        db.close()
        log_activity('video_upload', 'media', title)
        return jsonify({'status': 'uploaded', 'id': cur.lastrowid}), 201

    @app.route('/api/videos/<int:vid>', methods=['DELETE'])
    def api_videos_delete(vid):
        db = get_db()
        row = db.execute('SELECT filename, title FROM videos WHERE id = ?', (vid,)).fetchone()
        if row:
            filepath = os.path.join(get_video_dir(), row['filename'])
            if os.path.isfile(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
            db.execute('DELETE FROM videos WHERE id = ?', (vid,))
            db.commit()
            log_activity('video_delete', 'media', row['title'])
        db.close()
        return jsonify({'status': 'deleted'})

    @app.route('/api/videos/<int:vid>', methods=['PATCH'])
    def api_videos_update(vid):
        data = request.get_json() or {}
        db = get_db()
        if 'title' in data:
            db.execute('UPDATE videos SET title = ? WHERE id = ?', (data['title'], vid))
        if 'folder' in data:
            db.execute('UPDATE videos SET folder = ? WHERE id = ?', (data['folder'], vid))
        if 'category' in data:
            db.execute('UPDATE videos SET category = ? WHERE id = ?', (data['category'], vid))
        db.commit()
        db.close()
        return jsonify({'status': 'updated'})

    @app.route('/api/videos/serve/<path:filename>')
    def api_videos_serve(filename):
        vdir = get_video_dir()
        safe = os.path.normpath(os.path.join(vdir, filename))
        if not safe.startswith(os.path.normpath(vdir)) or not os.path.isfile(safe):
            return jsonify({'error': 'Not found'}), 404
        from flask import send_file
        return send_file(safe)

    @app.route('/api/videos/categories')
    def api_videos_categories():
        return jsonify(VIDEO_CATEGORIES)

    @app.route('/api/videos/folders')
    def api_videos_folders():
        db = get_db()
        rows = db.execute('SELECT DISTINCT folder FROM videos WHERE folder != "" ORDER BY folder').fetchall()
        db.close()
        return jsonify([r['folder'] for r in rows])

    @app.route('/api/videos/stats')
    def api_videos_stats():
        db = get_db()
        total = db.execute('SELECT COUNT(*) as c FROM videos').fetchone()['c']
        total_size = db.execute('SELECT COALESCE(SUM(filesize),0) as s FROM videos').fetchone()['s']
        by_folder = db.execute('SELECT folder, COUNT(*) as c FROM videos GROUP BY folder ORDER BY folder').fetchall()
        db.close()
        return jsonify({
            'total': total,
            'total_size': total_size,
            'total_size_fmt': format_size(total_size),
            'by_folder': [{'folder': r['folder'] or 'Unsorted', 'count': r['c']} for r in by_folder],
        })

    AUDIO_CATALOG = [
        # HAM Radio & Communications Training
        {'title': 'Ham Radio Crash Course - Technician License', 'url': 'https://www.youtube.com/watch?v=Krc15VfkRJA', 'channel': 'Ham Radio Crash Course', 'category': 'radio', 'folder': 'Radio Training'},
        {'title': 'Emergency Communications - ARES/RACES Intro', 'url': 'https://www.youtube.com/watch?v=9acOfs8gYlk', 'channel': 'Ham Radio 2.0', 'category': 'radio', 'folder': 'Radio Training'},
        {'title': 'Morse Code Training - Learn CW', 'url': 'https://www.youtube.com/watch?v=D8tPkb98Fkk', 'channel': 'Ham Radio Crash Course', 'category': 'radio', 'folder': 'Radio Training'},
        # Survival Skills Audio
        {'title': 'Wilderness Survival Skills - Complete Audio Guide', 'url': 'https://www.youtube.com/watch?v=oBp7LoFxdhU', 'channel': 'Survival On Purpose', 'category': 'survival', 'folder': 'Survival Skills'},
        {'title': 'Prepper Mindset - Mental Preparedness', 'url': 'https://www.youtube.com/watch?v=qxNjJPHzN-o', 'channel': 'Canadian Prepper', 'category': 'survival', 'folder': 'Survival Skills'},
        {'title': 'Bushcraft Skills Every Prepper Needs', 'url': 'https://www.youtube.com/watch?v=k4vee-NTkds', 'channel': 'TA Outdoors', 'category': 'bushcraft', 'folder': 'Survival Skills'},
        # Medical Audio Training
        {'title': 'Tactical First Aid - TCCC Basics', 'url': 'https://www.youtube.com/watch?v=J6-nFr-pn4A', 'channel': 'Skinny Medic', 'category': 'medical', 'folder': 'Medical Training'},
        {'title': 'Herbal Medicine Fundamentals', 'url': 'https://www.youtube.com/watch?v=HQdXn_bDiIs', 'channel': 'Survival Dispatch', 'category': 'medical', 'folder': 'Medical Training'},
        # Homesteading & Self-Reliance
        {'title': 'Permaculture Design Principles', 'url': 'https://www.youtube.com/watch?v=cEBtmjaFU28', 'channel': 'Happen Films', 'category': 'farming', 'folder': 'Homesteading'},
        {'title': 'Food Preservation - Complete Guide', 'url': 'https://www.youtube.com/watch?v=WKwMoeBPMJ8', 'channel': 'Townsends', 'category': 'cooking', 'folder': 'Homesteading'},
        # Situational Awareness & Security
        {'title': 'Situational Awareness - Gray Man Concept', 'url': 'https://www.youtube.com/watch?v=_sRjSR_B2Bc', 'channel': 'City Prepping', 'category': 'defense', 'folder': 'Security & Defense'},
        {'title': 'Home Defense Strategies', 'url': 'https://www.youtube.com/watch?v=mSCGGr8B0W8', 'channel': 'Warrior Poet Society', 'category': 'defense', 'folder': 'Security & Defense'},
        # Additional Radio Training
        {'title': 'NVIS Antennas for Emergency Communications', 'url': 'https://www.youtube.com/watch?v=TfhxTZkCJnE', 'channel': 'Off-Grid Ham', 'category': 'radio', 'folder': 'Radio Training'},
        {'title': 'Digital Modes for Emergency Comms — JS8Call and Winlink', 'url': 'https://www.youtube.com/watch?v=YhwrPTR5P3c', 'channel': 'Ham Radio Crash Course', 'category': 'radio', 'folder': 'Radio Training'},
        {'title': 'Winlink Email Over Radio — Grid-Down Communications', 'url': 'https://www.youtube.com/watch?v=n9_x3APmR3I', 'channel': 'K8MRD Radio Activities', 'category': 'radio', 'folder': 'Radio Training'},
        {'title': 'ARES Emergency Activation and Net Operations', 'url': 'https://www.youtube.com/watch?v=mGhBcIm7X4A', 'channel': 'Ham Radio 2.0', 'category': 'radio', 'folder': 'Radio Training'},
        {'title': 'HF Radio for Preppers — Shortwave Listening and DX', 'url': 'https://www.youtube.com/watch?v=hpQBJ5gcYWk', 'channel': 'Radio Prepper', 'category': 'radio', 'folder': 'Radio Training'},
        {'title': 'Baofeng UV-5R Complete Programming Guide', 'url': 'https://www.youtube.com/watch?v=wF9hkG1GpSg', 'channel': 'Tin Hat Ranch', 'category': 'radio', 'folder': 'Radio Training'},
        # Additional Survival Skills Audio
        {'title': 'Winter Survival — Hypothermia Prevention and Recovery', 'url': 'https://www.youtube.com/watch?v=U0vBpCLz2Rg', 'channel': 'Coalcracker Bushcraft', 'category': 'survival', 'folder': 'Survival Skills'},
        {'title': 'Navigation by Stars — Polaris and Southern Cross', 'url': 'https://www.youtube.com/watch?v=LXiYW2CKVLQ', 'channel': 'Black Scout Survival', 'category': 'survival', 'folder': 'Survival Skills'},
        {'title': 'Surviving Extreme Heat — Desert and Urban Heat Emergencies', 'url': 'https://www.youtube.com/watch?v=qFiC8kS8bVg', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Survival Skills'},
        {'title': 'Urban Survival — Bugging Out from the City', 'url': 'https://www.youtube.com/watch?v=HSTrM0pXnCA', 'channel': 'The Urban Prepper', 'category': 'survival', 'folder': 'Survival Skills'},
        {'title': 'Knot Tying Masterclass — 20 Essential Knots', 'url': 'https://www.youtube.com/watch?v=VrSBsqe23Qk', 'channel': 'ITS Tactical', 'category': 'bushcraft', 'folder': 'Survival Skills'},
        {'title': 'Bow Drill Fire Starting — Complete Technique Guide', 'url': 'https://www.youtube.com/watch?v=lR-LrU0zA0Y', 'channel': 'Coalcracker Bushcraft', 'category': 'bushcraft', 'folder': 'Survival Skills'},
        # Additional Medical Training
        {'title': 'Wound Care and Infection Prevention in the Field', 'url': 'https://www.youtube.com/watch?v=JR2IABjLJBY', 'channel': 'Corporals Corner', 'category': 'medical', 'folder': 'Medical Training'},
        {'title': 'Improvised Medications and Herbal Antibiotics', 'url': 'https://www.youtube.com/watch?v=1hpEL7Jy_HI', 'channel': 'DrBones NurseAmy', 'category': 'medical', 'folder': 'Medical Training'},
        {'title': 'Managing Childbirth Emergency — Obstetric Crisis Without a Doctor', 'url': 'https://www.youtube.com/watch?v=u3x0JPCHDOQ', 'channel': 'Survival Dispatch', 'category': 'medical', 'folder': 'Medical Training'},
        {'title': 'Pediatric First Aid — Children\'s Emergencies in the Field', 'url': 'https://www.youtube.com/watch?v=MX0kB-x_XPg', 'channel': 'PrepMedic', 'category': 'medical', 'folder': 'Medical Training'},
        {'title': 'Diabetic Emergencies — Hypo and Hyperglycemia Without Insulin', 'url': 'https://www.youtube.com/watch?v=CqJNQkVLI_4', 'channel': 'DrBones NurseAmy', 'category': 'medical', 'folder': 'Medical Training'},
        # FEMA / Emergency Management
        {'title': 'FEMA IS-100: Introduction to Incident Command System', 'url': 'https://www.youtube.com/watch?v=YsA4VhAWsSE', 'channel': 'FEMA', 'category': 'survival', 'folder': 'Emergency Management'},
        {'title': 'Community Emergency Response Team (CERT) Training Overview', 'url': 'https://www.youtube.com/watch?v=JVuxCgo8mWM', 'channel': 'FEMA', 'category': 'survival', 'folder': 'Emergency Management'},
        {'title': 'Shelter-in-Place — When to Stay and How to Prepare', 'url': 'https://www.youtube.com/watch?v=_GNh3p1GFAI', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Emergency Management'},
        {'title': 'Mass Casualty Incident — START Triage for Civilians', 'url': 'https://www.youtube.com/watch?v=CSiuSIFDcuI', 'channel': 'Skinny Medic', 'category': 'medical', 'folder': 'Emergency Management'},
        # Additional Homesteading & Food Production
        {'title': 'Sprouting Seeds for Winter Nutrition', 'url': 'https://www.youtube.com/watch?v=OGkRUHl-dbw', 'channel': 'Homesteading Family', 'category': 'cooking', 'folder': 'Homesteading'},
        {'title': 'Traditional Soap Making from Wood Ash Lye', 'url': 'https://www.youtube.com/watch?v=gJ7fPmNqRkL', 'channel': 'Townsends', 'category': 'cooking', 'folder': 'Homesteading'},
        {'title': 'Natural Beekeeping — Top-Bar Hive Management', 'url': 'https://www.youtube.com/watch?v=MmLeKkEa7J0', 'channel': 'Stoney Ridge Farmer', 'category': 'farming', 'folder': 'Homesteading'},
        {'title': 'Tallow Rendering — Processing Beef Fat for Cooking, Candles, and Soap', 'url': 'https://www.youtube.com/watch?v=pLkRnB8cTqW', 'channel': 'Homesteading Family', 'category': 'cooking', 'folder': 'Homesteading'},
        # Nuclear & CBRN
        {'title': 'Nuclear Fallout Shelter — Design and Protective Measures', 'url': 'https://www.youtube.com/watch?v=9X7_xI5tGzQ', 'channel': 'Practical Preppers', 'category': 'survival', 'folder': 'Nuclear & CBRN'},
        {'title': 'Radiation Detection — Using Dosimeters and Geiger Counters', 'url': 'https://www.youtube.com/watch?v=xhmReScCzE4', 'channel': "Prepper's Paradigm", 'category': 'survival', 'folder': 'Nuclear & CBRN'},
        {'title': 'Chemical Warfare Agent Decontamination — Personal and Area', 'url': 'https://www.youtube.com/watch?v=AUxTRyqp5qg', 'channel': 'Practical Preppers', 'category': 'survival', 'folder': 'Nuclear & CBRN'},
        # Off-Grid Power
        {'title': 'Propane vs. Natural Gas Conversion for Generators', 'url': 'https://www.youtube.com/watch?v=k_jVk2Q2sJY', 'channel': 'Engineer775', 'category': 'repair', 'folder': 'Power Systems'},
        {'title': 'Battery Bank Sizing for Off-Grid Living', 'url': 'https://www.youtube.com/watch?v=W0Miu0mihVE', 'channel': 'DIY Solar Power (Will Prowse)', 'category': 'repair', 'folder': 'Power Systems'},
        {'title': 'Wood Gasification — Running Engines on Wood', 'url': 'https://www.youtube.com/watch?v=egyNJ9HKMeo', 'channel': 'Open Source Ecology', 'category': 'repair', 'folder': 'Power Systems'},
        # Weather & Climate Training
        {'title': 'Skywarn Storm Spotter Training — NWS Official Course', 'url': 'https://www.youtube.com/watch?v=5D3f9ReBnNI', 'channel': 'The COMET Program', 'category': 'survival', 'folder': 'Weather & Climate'},
        {'title': 'Understanding CAPE and Severe Weather Parameters', 'url': 'https://www.youtube.com/watch?v=F5xZ5Jm5Gmw', 'channel': 'The COMET Program', 'category': 'survival', 'folder': 'Weather & Climate'},
        {'title': 'El Niño and La Niña — What They Mean for Your Region', 'url': 'https://www.youtube.com/watch?v=WPA-KpldDVc', 'channel': 'NOAA Satellites and Information', 'category': 'survival', 'folder': 'Weather & Climate'},
        {'title': 'Atmospheric Rivers — Extreme Precipitation Explained', 'url': 'https://www.youtube.com/watch?v=xqBwLMxU4UM', 'channel': 'Cliff Mass Weather', 'category': 'survival', 'folder': 'Weather & Climate'},
        {'title': 'Wildfire Weather — Red Flag Warnings and Fire Behavior', 'url': 'https://www.youtube.com/watch?v=vKMuq7J0U1g', 'channel': 'NWS Headquarters', 'category': 'survival', 'folder': 'Weather & Climate'},
        {'title': 'Frost Dates and Growing Season — Using Climate Data for Gardening', 'url': 'https://www.youtube.com/watch?v=s3N0RFz9V0Y', 'channel': 'Epic Gardening', 'category': 'farming', 'folder': 'Weather & Climate'},
        {'title': 'Drought Recognition and Water Conservation Planning', 'url': 'https://www.youtube.com/watch?v=pQ2lIpnFB8M', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Weather & Climate'},
        {'title': 'Reading Surface Analysis Maps — Understanding Weather Systems', 'url': 'https://www.youtube.com/watch?v=7bNgZ-BQOo8', 'channel': 'The COMET Program', 'category': 'survival', 'folder': 'Weather & Climate'},
        # Maps & Geospatial Training
        {'title': 'How to Download and Use USGS Topo Quads Offline', 'url': 'https://www.youtube.com/watch?v=BpFCOeR02SU', 'channel': 'USGS (US Geological Survey)', 'category': 'survival', 'folder': 'Maps & Navigation'},
        {'title': 'QGIS Basics for Preppers — Free Offline Mapping', 'url': 'https://www.youtube.com/watch?v=RTjAp6dqvsM', 'channel': 'GIS Geography', 'category': 'survival', 'folder': 'Maps & Navigation'},
        {'title': 'NOAA Satellite Imagery — Reading Weather and Land Patterns', 'url': 'https://www.youtube.com/watch?v=m5JV6fRtFjk', 'channel': 'NOAA Satellites and Information', 'category': 'survival', 'folder': 'Maps & Navigation'},
        {'title': 'OsmAnd Offline Maps Setup — Full Tutorial', 'url': 'https://www.youtube.com/watch?v=FNLnLKuXjrU', 'channel': 'GIS Geography', 'category': 'survival', 'folder': 'Maps & Navigation'},
        # Primitive & Bushcraft Skills
        {'title': 'Primitive Bow Making — Self Bow from Raw Wood', 'url': 'https://www.youtube.com/watch?v=sTfxmFNInAU', 'channel': 'Primitive Technology', 'category': 'bushcraft', 'folder': 'Bushcraft Skills'},
        {'title': 'Snare Trapping for Small Game — Legal and Effective Methods', 'url': 'https://www.youtube.com/watch?v=gLDIpbS3OeI', 'channel': 'My Self Reliance', 'category': 'bushcraft', 'folder': 'Bushcraft Skills'},
        {'title': 'Brain Tanning Hides — Processing Deer and Rabbit Pelts', 'url': 'https://www.youtube.com/watch?v=d5MZf_mj9qU', 'channel': 'Coalcracker Bushcraft', 'category': 'bushcraft', 'folder': 'Bushcraft Skills'},
        {'title': 'Primitive Fire Starting — Bow Drill, Hand Drill, Flint and Steel', 'url': 'https://www.youtube.com/watch?v=VKTFmEFKuEw', 'channel': 'Survival Lilly', 'category': 'bushcraft', 'folder': 'Bushcraft Skills'},
        {'title': 'Basket Weaving for Beginners — Functional Containers from Natural Materials', 'url': 'https://www.youtube.com/watch?v=O2QmYJWUhWI', 'channel': 'NativeTech', 'category': 'bushcraft', 'folder': 'Bushcraft Skills'},
        # Food Preservation Deep Dives
        {'title': 'Lacto-Fermentation Fundamentals — Sauerkraut, Pickles, Kimchi Without Canning', 'url': 'https://www.youtube.com/watch?v=0z3vSe-GR3A', 'channel': 'Farmhouse on Boone', 'category': 'cooking', 'folder': 'Food & Storage'},
        {'title': 'Smoking Meat for Long-Term Preservation — Build Your Own Smoker', 'url': 'https://www.youtube.com/watch?v=aK0XKXG5Nsg', 'channel': 'Homesteading Family', 'category': 'cooking', 'folder': 'Food & Storage'},
        {'title': 'Salt Curing Meat — Historical Preservation Without Refrigeration', 'url': 'https://www.youtube.com/watch?v=WqoORPLAYGM', 'channel': 'BBQ with Franklin', 'category': 'cooking', 'folder': 'Food & Storage'},
        {'title': 'Pressure Canning Safety — Botulism Prevention and Tested Recipes', 'url': 'https://www.youtube.com/watch?v=P4kO27fy7u4', 'channel': 'Ball Mason Jars', 'category': 'cooking', 'folder': 'Food & Storage'},
        {'title': 'Dehydrating Complete Meals — Backpacking and Emergency Rations', 'url': 'https://www.youtube.com/watch?v=5_QkMFhJxPc', 'channel': 'Fresh Off The Grid', 'category': 'cooking', 'folder': 'Food & Storage'},
        # Water Treatment Advanced
        {'title': 'Slow Sand Filtration — DIY Biosand Filter Construction', 'url': 'https://www.youtube.com/watch?v=N7TFJcg-CWI', 'channel': 'CAWST Centre for Affordable Water', 'category': 'survival', 'folder': 'Water & Sanitation'},
        {'title': 'Solar Water Disinfection (SODIS) — WHO-Endorsed Method for Clear Bottles', 'url': 'https://www.youtube.com/watch?v=hd0LAqtIMLk', 'channel': 'Practical Action', 'category': 'survival', 'folder': 'Water & Sanitation'},
        {'title': 'Emergency Well Construction — Driven Point Wells for Shallow Aquifers', 'url': 'https://www.youtube.com/watch?v=8sLn9REq0ok', 'channel': 'Practical Engineering', 'category': 'survival', 'folder': 'Water & Sanitation'},
        # Medicinal & Foraging
        {'title': 'Medicinal Mushrooms — Identification and Preparation of Immune-Boosting Species', 'url': 'https://www.youtube.com/watch?v=rG0TKdFlNpc', 'channel': 'Healing Harvest Homestead', 'category': 'medical', 'folder': 'Medical Training'},
        {'title': 'Herbal Wound Care — Plantain, Yarrow, and Comfrey Poultices', 'url': 'https://www.youtube.com/watch?v=TkmVUhwK_28', 'channel': 'Herbal Prepper', 'category': 'medical', 'folder': 'Medical Training'},
        {'title': 'Essential Oils in Emergency Medicine — Evidence and Cautions', 'url': 'https://www.youtube.com/watch?v=oBSAWxQqRGc', 'channel': 'Dr. Josh Axe', 'category': 'medical', 'folder': 'Medical Training'},
        # Security & Defense Training
        {'title': 'Perimeter Security — Early Warning Systems Using Minimal Materials', 'url': 'https://www.youtube.com/watch?v=xP0hROQvNFY', 'channel': 'ITS Tactical', 'category': 'security', 'folder': 'Security & Defense'},
        {'title': 'Vehicle Security and Anti-Carjacking Awareness', 'url': 'https://www.youtube.com/watch?v=MXN4fOLwAzw', 'channel': 'PDN (Personal Defense Network)', 'category': 'security', 'folder': 'Security & Defense'},
        {'title': 'Night Vision and Thermal — Choosing the Right Optic for SHTF', 'url': 'https://www.youtube.com/watch?v=R2H7UM9gAJw', 'channel': 'Garand Thumb', 'category': 'security', 'folder': 'Security & Defense'},
        # Repair & Mechanical Skills
        {'title': 'Small Engine Repair — Generators, Chainsaws, and Tillers', 'url': 'https://www.youtube.com/watch?v=K5q_i8jVRiA', 'channel': 'LawnMowerPros', 'category': 'repair', 'folder': 'Tools & Repair'},
        {'title': 'Introduction to Arc Welding — Basic Techniques for Beginners', 'url': 'https://www.youtube.com/watch?v=7p-UMiqkeMI', 'channel': 'welding tips and tricks', 'category': 'repair', 'folder': 'Tools & Repair'},
        {'title': 'Basic Plumbing Repairs Without a Plumber — Pipes, Valves, and Fixtures', 'url': 'https://www.youtube.com/watch?v=yY3WLEg0bYI', 'channel': 'This Old House', 'category': 'repair', 'folder': 'Tools & Repair'},
        {'title': 'Hand Tool Woodworking — Bench Plane, Chisel, and Hand Saw Mastery', 'url': 'https://www.youtube.com/watch?v=XEpAEFV6M8E', 'channel': 'Paul Sellers', 'category': 'repair', 'folder': 'Tools & Repair'},
        {'title': 'Blacksmithing for Beginners — Coal and Propane Forge Basics', 'url': 'https://www.youtube.com/watch?v=sNjJ-M_zQjI', 'channel': 'Black Bear Forge', 'category': 'repair', 'folder': 'Tools & Repair'},
        {'title': 'Sharpening Knives, Axes, and Tools — Whetstone, Strop, and Jig Methods', 'url': 'https://www.youtube.com/watch?v=3xXLjEi5j6c', 'channel': 'Outdoors55', 'category': 'repair', 'folder': 'Tools & Repair'},
        # Animal Husbandry
        {'title': 'Raising Meat Rabbits — Breed Selection, Housing, and Processing', 'url': 'https://www.youtube.com/watch?v=pYA8Gz6B9hA', 'channel': 'Justin Rhodes', 'category': 'farming', 'folder': 'Animal Husbandry'},
        {'title': 'Dairy Goats for Beginners — Breed Selection, Milking, and Kidding', 'url': 'https://www.youtube.com/watch?v=w7Px_7GCTII', 'channel': 'Becky\'s Homestead', 'category': 'farming', 'folder': 'Animal Husbandry'},
        {'title': 'Backyard Chickens — Health, Egg Production, and Flock Management', 'url': 'https://www.youtube.com/watch?v=HzSdCl4XrNI', 'channel': 'Stoney Ridge Farmer', 'category': 'farming', 'folder': 'Animal Husbandry'},
        {'title': 'Hog Processing and Butchery — Farm to Table Without a Processor', 'url': 'https://www.youtube.com/watch?v=5GMM0RiJGlc', 'channel': 'Homesteading Family', 'category': 'farming', 'folder': 'Animal Husbandry'},
        {'title': 'Veterinary Basics for Livestock — Wound Care, Parasite Control, Birthing Assist', 'url': 'https://www.youtube.com/watch?v=3YpX68gHXYE', 'channel': 'The Holistic Hen', 'category': 'medical', 'folder': 'Animal Husbandry'},
        # Community Organization & Grid-Down Economics
        {'title': 'Barter Economy — What to Stock and How to Trade After SHTF', 'url': 'https://www.youtube.com/watch?v=LX5bpBJpz_M', 'channel': 'Canadian Prepper', 'category': 'survival', 'folder': 'Community & Economics'},
        {'title': 'Community Organizing After Disaster — Mutual Aid and Group Governance', 'url': 'https://www.youtube.com/watch?v=7lHm4R6Qf5E', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Community & Economics'},
        {'title': 'Grid-Down Sanitation — Composting Toilets, Latrines, and Hygiene Without Utilities', 'url': 'https://www.youtube.com/watch?v=dUqK9B4-MBI', 'channel': 'Practical Preppers', 'category': 'survival', 'folder': 'Water & Sanitation'},
        {'title': 'Ham Radio License Study — Technician Pool Q&A All 300 Questions', 'url': 'https://www.youtube.com/watch?v=HNmzjBMPLRQ', 'channel': 'Ham Radio Crash Course', 'category': 'radio', 'folder': 'Radio Training'},
        # Dental & Specialized Medical
        {'title': 'Emergency Dental Care — Abscess Treatment and Tooth Extraction Techniques', 'url': 'https://www.youtube.com/watch?v=oY9oQ9wjPyE', 'channel': 'DrBones NurseAmy', 'category': 'medical', 'folder': 'Medical Training'},
        {'title': 'Eye Emergencies — Foreign Bodies, Trauma, and Chemical Exposure Without a Doctor', 'url': 'https://www.youtube.com/watch?v=HLfGkqAZtG0', 'channel': 'PrepMedic', 'category': 'medical', 'folder': 'Medical Training'},
        {'title': 'Improvised Stretcher and Patient Transport — Moving Casualties Without Equipment', 'url': 'https://www.youtube.com/watch?v=vJ45K4qW-kI', 'channel': 'Corporals Corner', 'category': 'medical', 'folder': 'Medical Training'},
        # Grid-Down Transportation & Mobility
        {'title': 'Bicycle Repair and Maintenance — Grid-Down Transportation', 'url': 'https://www.youtube.com/watch?v=rJw2PFv8q3N', 'channel': 'Park Tool', 'category': 'repair', 'folder': 'Tools & Repair'},
        {'title': 'Diesel Engine Basics — Why Diesel Survives When Gas Doesn\'t', 'url': 'https://www.youtube.com/watch?v=Km5FcTy9NxV', 'channel': 'EricTheCarGuy', 'category': 'repair', 'folder': 'Tools & Repair'},
        # Advanced Water Skills
        {'title': 'Ram Pump Installation — Water Without Electricity Using Gravity', 'url': 'https://www.youtube.com/watch?v=sHp3QkqGxJN', 'channel': 'Engineer775', 'category': 'survival', 'folder': 'Water & Sanitation'},
        {'title': 'Greywater Recycling for Garden Irrigation — Simple DIY Systems', 'url': 'https://www.youtube.com/watch?v=tWq7RmCjFkZ', 'channel': 'Practical Preppers', 'category': 'survival', 'folder': 'Water & Sanitation'},
        # Communications — Supplemental
        {'title': 'DMR Radio Programming — Hotspots, Code Plugs, and Talk Groups', 'url': 'https://www.youtube.com/watch?v=nHqT3eMjLRb', 'channel': 'Ham Radio 2.0', 'category': 'radio', 'folder': 'Radio Training'},
        {'title': 'Antenna Theory for Beginners — Dipoles, Verticals, and Yagi Designs', 'url': 'https://www.youtube.com/watch?v=kYz8PwVrsMd', 'channel': 'Ham Radio Crash Course', 'category': 'radio', 'folder': 'Radio Training'},
        # Mental Preparedness & Stress
        {'title': 'Tactical Breathing and Stress Inoculation — Military Mental Techniques', 'url': 'https://www.youtube.com/watch?v=hLcWBqGsfXc', 'channel': 'Warrior Poet Society', 'category': 'survival', 'folder': 'Survival Skills'},
        {'title': 'Grief and Loss Management During Long-Term Emergencies', 'url': 'https://www.youtube.com/watch?v=pQm8sJvXnRw', 'channel': 'City Prepping', 'category': 'survival', 'folder': 'Emergency Management'},
        # Advanced Food Production
        {'title': 'Mushroom Cultivation — Growing Oyster and Shiitake on Logs and Straw', 'url': 'https://www.youtube.com/watch?v=tRkFnJ4mGsY', 'channel': 'FreshCap Mushrooms', 'category': 'farming', 'folder': 'Homesteading'},
        {'title': 'Greenhouse Heating Without Electricity — Thermal Mass and Compost Heat', 'url': 'https://www.youtube.com/watch?v=wNb6qVkJpTc', 'channel': 'Stoney Ridge Farmer', 'category': 'farming', 'folder': 'Homesteading'},
    ]

    @app.route('/api/audio/catalog')
    def api_audio_catalog():
        return jsonify(AUDIO_CATALOG)

    @app.route('/api/channels/catalog')
    def api_channels_catalog():
        # Filter out dead channels
        db = get_db()
        dead_row = db.execute("SELECT value FROM settings WHERE key = 'dead_channels'").fetchone()
        db.close()
        dead_urls = set(json.loads(dead_row['value']) if dead_row and dead_row['value'] else [])
        live = [c for c in CHANNEL_CATALOG if c['url'] not in dead_urls]
        category = request.args.get('category', '')
        if category:
            return jsonify([c for c in live if c['category'] == category])
        return jsonify(live)

    @app.route('/api/channels/categories')
    def api_channels_categories():
        from collections import Counter
        db = get_db()
        dead_row = db.execute("SELECT value FROM settings WHERE key = 'dead_channels'").fetchone()
        db.close()
        dead_urls = set(json.loads(dead_row['value']) if dead_row and dead_row['value'] else [])
        live = [c for c in CHANNEL_CATALOG if c['url'] not in dead_urls]
        counts = Counter(c['category'] for c in live)
        cats = sorted(counts.keys())
        return jsonify([{'name': cat, 'count': counts[cat]} for cat in cats])

    @app.route('/api/channels/validate', methods=['POST'])
    def api_channels_validate():
        """Check a channel URL — mark dead if no videos found."""
        data = request.get_json() or {}
        url = data.get('url', '').strip()
        if not url:
            return jsonify({'error': 'No URL'}), 400
        exe = get_ytdlp_path()
        if not os.path.isfile(exe):
            return jsonify({'error': 'Downloader not installed'}), 400
        try:
            result = subprocess.run(
                [exe, '--flat-playlist', '--dump-json', '--playlist-end', '1', url + '/videos'],
                capture_output=True, text=True, timeout=20, **_CREATION_FLAGS,
            )
            alive = result.returncode == 0 and bool(result.stdout.strip())
            if not alive:
                db = get_db()
                row = db.execute("SELECT value FROM settings WHERE key = 'dead_channels'").fetchone()
                dead = json.loads(row['value']) if row and row['value'] else []
                if url not in dead:
                    dead.append(url)
                    if row:
                        db.execute("UPDATE settings SET value = ? WHERE key = 'dead_channels'", (json.dumps(dead),))
                    else:
                        db.execute("INSERT INTO settings (key, value) VALUES ('dead_channels', ?)", (json.dumps(dead),))
                    db.commit()
                db.close()
            return jsonify({'url': url, 'alive': alive})
        except subprocess.TimeoutExpired:
            return jsonify({'url': url, 'alive': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # ─── YouTube Search & Channel Videos ─────────────────────────────

    @app.route('/api/youtube/search')
    def api_youtube_search():
        """Search YouTube via yt-dlp and return video metadata."""
        query = request.args.get('q', '').strip()
        try:
            limit = min(int(request.args.get('limit', '12')), 30)
        except (ValueError, TypeError):
            limit = 12
        if not query:
            return jsonify([])
        exe = get_ytdlp_path()
        if not os.path.isfile(exe):
            return jsonify({'error': 'Downloader not installed'}), 400
        try:
            result = subprocess.run(
                [exe, '--flat-playlist', '--dump-json', f'ytsearch{limit}:{query}'],
                capture_output=True, text=True, timeout=30, **_CREATION_FLAGS,
            )
            videos = []
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                    thumb = ''
                    if d.get('thumbnails'):
                        thumb = d['thumbnails'][-1].get('url', '')
                    elif d.get('thumbnail'):
                        thumb = d['thumbnail']
                    videos.append({
                        'id': d.get('id', ''),
                        'title': d.get('title', ''),
                        'channel': d.get('channel', d.get('uploader', '')),
                        'duration': d.get('duration_string', ''),
                        'views': d.get('view_count', 0),
                        'thumbnail': thumb,
                        'url': f"https://www.youtube.com/watch?v={d.get('id', '')}",
                    })
                except json.JSONDecodeError:
                    continue
            return jsonify(videos)
        except subprocess.TimeoutExpired:
            return jsonify({'error': 'Search timed out'}), 504
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/youtube/channel-videos')
    def api_youtube_channel_videos():
        """List recent videos from a YouTube channel."""
        channel_url = request.args.get('url', '').strip()
        try:
            limit = min(int(request.args.get('limit', '12')), 50)
        except (ValueError, TypeError):
            limit = 12
        if not channel_url:
            return jsonify([])
        exe = get_ytdlp_path()
        if not os.path.isfile(exe):
            return jsonify({'error': 'Downloader not installed'}), 400
        try:
            result = subprocess.run(
                [exe, '--flat-playlist', '--dump-json', '--playlist-end', str(limit),
                 channel_url + '/videos'],
                capture_output=True, text=True, timeout=45, **_CREATION_FLAGS,
            )
            videos = []
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                    thumb = ''
                    if d.get('thumbnails'):
                        thumb = d['thumbnails'][-1].get('url', '')
                    elif d.get('thumbnail'):
                        thumb = d['thumbnail']
                    videos.append({
                        'id': d.get('id', ''),
                        'title': d.get('title', ''),
                        'channel': d.get('channel', d.get('uploader', '')),
                        'duration': d.get('duration_string', ''),
                        'views': d.get('view_count', 0),
                        'thumbnail': thumb,
                        'url': f"https://www.youtube.com/watch?v={d.get('id', '')}",
                    })
                except json.JSONDecodeError:
                    continue
            return jsonify(videos)
        except subprocess.TimeoutExpired:
            return jsonify({'error': 'Request timed out'}), 504
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # ─── Channel Subscriptions ──────────────────────────────────────
    @app.route('/api/subscriptions')
    def api_subscriptions_list():
        db = get_db()
        rows = db.execute('SELECT * FROM subscriptions ORDER BY channel_name').fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/subscriptions', methods=['POST'])
    def api_subscriptions_add():
        data = request.get_json() or {}
        name = data.get('name', '').strip()
        url = data.get('url', '').strip()
        category = data.get('category', '')
        if not name or not url:
            return jsonify({'error': 'Name and URL required'}), 400
        db = get_db()
        try:
            db.execute('INSERT INTO subscriptions (channel_name, channel_url, category) VALUES (?, ?, ?)', (name, url, category))
            db.commit()
        except Exception:
            db.close()
            return jsonify({'error': 'Already subscribed'}), 409
        db.close()
        return jsonify({'status': 'subscribed'})

    @app.route('/api/subscriptions/<int:sid>', methods=['DELETE'])
    def api_subscriptions_delete(sid):
        db = get_db()
        db.execute('DELETE FROM subscriptions WHERE id = ?', (sid,))
        db.commit()
        db.close()
        return jsonify({'status': 'unsubscribed'})

    # ─── Media Shared Endpoints (favorites, batch) ────────────────────

    @app.route('/api/media/favorite', methods=['POST'])
    def api_media_favorite():
        data = request.get_json() or {}
        media_type = data.get('type', 'videos')
        media_id = data.get('id')
        table_map = {'videos': 'videos', 'audio': 'audio', 'books': 'books'}
        table = table_map.get(media_type)
        if not table or not media_id:
            return jsonify({'error': 'Invalid request'}), 400
        db = get_db()
        try:
            row = db.execute(f'SELECT favorited FROM {table} WHERE id = ?', (media_id,)).fetchone()
            new_val = 0
            if row:
                new_val = 0 if row['favorited'] else 1
                db.execute(f'UPDATE {table} SET favorited = ? WHERE id = ?', (new_val, media_id))
                db.commit()
            return jsonify({'status': 'toggled', 'favorited': new_val})
        finally:
            db.close()

    @app.route('/api/media/batch-delete', methods=['POST'])
    def api_media_batch_delete():
        data = request.get_json() or {}
        media_type = data.get('type', 'videos')
        ids = data.get('ids', [])
        if not ids:
            return jsonify({'error': 'No IDs provided'}), 400
        table_map = {'videos': 'videos', 'audio': 'audio', 'books': 'books'}
        dir_map = {'videos': get_video_dir, 'audio': get_audio_dir, 'books': get_books_dir}
        table = table_map.get(media_type)
        get_dir = dir_map.get(media_type)
        if not table or not get_dir:
            return jsonify({'error': 'Invalid type'}), 400
        db = get_db()
        try:
            media_dir = get_dir()
            deleted = 0
            for mid in ids:
                row = db.execute(f'SELECT filename FROM {table} WHERE id = ?', (mid,)).fetchone()
                if row:
                    filepath = os.path.join(media_dir, row['filename'])
                    if os.path.isfile(filepath):
                        try:
                            os.remove(filepath)
                        except Exception:
                            pass
                    db.execute(f'DELETE FROM {table} WHERE id = ?', (mid,))
                    deleted += 1
            db.commit()
            return jsonify({'status': 'deleted', 'count': deleted})
        finally:
            db.close()

    @app.route('/api/media/batch-move', methods=['POST'])
    def api_media_batch_move():
        data = request.get_json() or {}
        media_type = data.get('type', 'videos')
        ids = data.get('ids', [])
        folder = data.get('folder', '')
        table_map = {'videos': 'videos', 'audio': 'audio', 'books': 'books'}
        table = table_map.get(media_type)
        if not table or not ids:
            return jsonify({'error': 'Invalid request'}), 400
        db = get_db()
        try:
            for mid in ids:
                db.execute(f'UPDATE {table} SET folder = ? WHERE id = ?', (folder, mid))
            db.commit()
            return jsonify({'status': 'moved', 'count': len(ids)})
        finally:
            db.close()

    # ─── yt-dlp Integration ──────────────────────────────────────────

    @app.route('/api/ytdlp/status')
    def api_ytdlp_status():
        exe = get_ytdlp_path()
        installed = os.path.isfile(exe)
        version = ''
        if installed:
            try:
                result = subprocess.run([exe, '--version'], capture_output=True, text=True, timeout=5,
                                        **_CREATION_FLAGS)
                version = result.stdout.strip()
            except Exception:
                pass
        return jsonify({'installed': installed, 'version': version, 'path': exe})

    _ytdlp_install_state = {'status': 'idle', 'percent': 0, 'error': None}

    @app.route('/api/ytdlp/install', methods=['POST'])
    def api_ytdlp_install():
        exe = get_ytdlp_path()
        if os.path.isfile(exe):
            return jsonify({'status': 'already_installed'})
        ytdlp_dir = os.path.dirname(exe)
        os.makedirs(ytdlp_dir, exist_ok=True)

        def do_install():
            try:
                _ytdlp_install_state.update({'status': 'downloading', 'percent': 10, 'error': None})
                import requests as req
                resp = req.get(_get_ytdlp_url(), stream=True, timeout=120, allow_redirects=True)
                resp.raise_for_status()
                total = int(resp.headers.get('content-length', 0))
                downloaded = 0
                with open(exe, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            _ytdlp_install_state['percent'] = int(downloaded / total * 90) + 10
                from platform_utils import make_executable
                make_executable(exe)
                _ytdlp_install_state.update({'status': 'complete', 'percent': 100, 'error': None})
                log.info('yt-dlp installed')
            except Exception as e:
                _ytdlp_install_state.update({'status': 'error', 'percent': 0, 'error': str(e)})
                log.error(f'yt-dlp install failed: {e}')

        threading.Thread(target=do_install, daemon=True).start()
        return jsonify({'status': 'installing'})

    @app.route('/api/ytdlp/install-progress')
    def api_ytdlp_install_progress():
        return jsonify(_ytdlp_install_state)

    @app.route('/api/ytdlp/download', methods=['POST'])
    def api_ytdlp_download():
        nonlocal _ytdlp_dl_counter
        exe = get_ytdlp_path()
        if not os.path.isfile(exe):
            return jsonify({'error': 'yt-dlp is not installed. Click "Setup Video Downloader" first.'}), 400

        data = request.get_json() or {}
        url = data.get('url', '').strip()
        folder = data.get('folder', '')
        category = data.get('category', 'general')
        if not url:
            return jsonify({'error': 'No URL provided'}), 400

        with _ytdlp_dl_lock:
            _ytdlp_dl_counter += 1
            dl_id = str(_ytdlp_dl_counter)

        _ytdlp_downloads[dl_id] = {'status': 'starting', 'percent': 0, 'title': '', 'speed': '', 'error': ''}

        def do_download():
            vdir = get_video_dir()
            dl_url = url
            try:
                # Get video info first
                _ytdlp_downloads[dl_id]['status'] = 'fetching info'
                info_result = subprocess.run(
                    [exe, '--no-download', '--print', '%(title)s|||%(duration_string)s|||%(filesize_approx)s', dl_url],
                    capture_output=True, text=True, timeout=30, **_CREATION_FLAGS,
                )
                if info_result.returncode != 0:
                    # Video unavailable — report error with clear message
                    _ytdlp_downloads[dl_id] = {'status': 'error', 'percent': 0,
                        'title': 'Video unavailable', 'speed': '',
                        'error': 'This video is unavailable on YouTube. Try searching for it by name.'}
                    return
                parts = info_result.stdout.strip().split('|||')
                video_title = parts[0] if parts else dl_url
                video_duration = parts[1] if len(parts) > 1 else ''
                _ytdlp_downloads[dl_id]['title'] = video_title

                # Download with progress — include thumbnail + subtitles
                _ytdlp_downloads[dl_id]['status'] = 'downloading'
                output_tmpl = os.path.join(vdir, '%(title)s.%(ext)s')
                proc = subprocess.Popen(
                    [exe, '-f', 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best',
                     '--merge-output-format', 'mp4', '--newline', '--no-playlist',
                     '--write-thumbnail', '--convert-thumbnails', 'jpg',
                     '--write-subs', '--write-auto-subs', '--sub-langs', 'en', '--convert-subs', 'srt',
                     '-o', output_tmpl, dl_url],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                    **_CREATION_FLAGS,
                )

                for line in proc.stdout:
                    line = line.strip()
                    if '[download]' in line and '%' in line:
                        try:
                            pct_str = line.split('%')[0].split()[-1]
                            pct = float(pct_str)
                            _ytdlp_downloads[dl_id]['percent'] = min(int(pct), 99)
                            # Extract speed
                            if 'at' in line:
                                speed_part = line.split('at')[-1].strip().split('ETA')[0].strip()
                                _ytdlp_downloads[dl_id]['speed'] = speed_part
                        except (ValueError, IndexError):
                            pass
                    elif '[Merger]' in line or '[ExtractAudio]' in line:
                        _ytdlp_downloads[dl_id].update({'status': 'merging', 'percent': 95})

                proc.wait(timeout=3600)

                if proc.returncode != 0:
                    # Capture stderr for error details
                    err_detail = 'Download failed (exit code %d)' % proc.returncode
                    _ytdlp_downloads[dl_id] = {'status': 'error', 'percent': 0, 'title': video_title, 'speed': '', 'error': err_detail}
                    return

                # Find the downloaded file
                safe_title = secure_filename(video_title + '.mp4') if video_title else None
                downloaded_file = None
                for f in os.listdir(vdir):
                    fpath = os.path.join(vdir, f)
                    if os.path.isfile(fpath) and f.endswith('.mp4'):
                        # Find recently modified files (within last 60s)
                        if time.time() - os.path.getmtime(fpath) < 60:
                            downloaded_file = f
                            break

                if not downloaded_file:
                    # Try matching by title
                    for f in os.listdir(vdir):
                        if video_title and video_title.lower()[:30] in f.lower():
                            downloaded_file = f
                            break

                if downloaded_file:
                    filesize = os.path.getsize(os.path.join(vdir, downloaded_file))
                    # Find thumbnail (jpg/webp next to the video)
                    base_name = os.path.splitext(downloaded_file)[0]
                    thumb_file = ''
                    for ext in ('.jpg', '.webp', '.png'):
                        candidate = base_name + ext
                        if os.path.isfile(os.path.join(vdir, candidate)):
                            thumb_file = candidate
                            break
                    # Find subtitle file
                    srt_file = ''
                    for f2 in os.listdir(vdir):
                        if f2.startswith(base_name) and f2.endswith('.srt'):
                            srt_file = f2
                            break
                    db = get_db()
                    db.execute('INSERT INTO videos (title, filename, category, folder, duration, url, filesize, thumbnail) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                               (video_title, downloaded_file, category, folder, video_duration, dl_url, filesize, thumb_file))
                    db.commit()
                    db.close()
                    log_activity('video_download', 'media', video_title)
                    _ytdlp_downloads[dl_id] = {'status': 'complete', 'percent': 100, 'title': video_title, 'speed': '', 'error': ''}
                else:
                    _ytdlp_downloads[dl_id] = {'status': 'error', 'percent': 0, 'title': video_title, 'speed': '', 'error': 'File not found after download'}

            except subprocess.TimeoutExpired:
                _ytdlp_downloads[dl_id] = {'status': 'error', 'percent': 0, 'title': '', 'speed': '', 'error': 'Download timed out'}
            except Exception as e:
                _ytdlp_downloads[dl_id] = {'status': 'error', 'percent': 0, 'title': '', 'speed': '', 'error': str(e)}

        threading.Thread(target=do_download, daemon=True).start()
        return jsonify({'status': 'started', 'id': dl_id})

    @app.route('/api/ytdlp/progress')
    def api_ytdlp_progress():
        with _state_lock:
            snapshot = dict(_ytdlp_downloads)
        return jsonify(snapshot)

    @app.route('/api/ytdlp/progress/<dl_id>')
    def api_ytdlp_progress_single(dl_id):
        with _state_lock:
            entry = _ytdlp_downloads.get(dl_id, {'status': 'unknown'})
        return jsonify(entry)

    @app.route('/api/videos/catalog')
    def api_videos_catalog():
        return jsonify(PREPPER_CATALOG)

    @app.route('/api/ytdlp/download-catalog', methods=['POST'])
    def api_ytdlp_download_catalog():
        """Download multiple catalog videos sequentially."""
        nonlocal _ytdlp_dl_counter
        exe = get_ytdlp_path()
        if not os.path.isfile(exe):
            return jsonify({'error': 'yt-dlp is not installed'}), 400

        data = request.get_json() or {}
        items = data.get('items', [])
        if not items:
            return jsonify({'error': 'No items selected'}), 400

        # Check which are already downloaded
        db = get_db()
        existing_urls = set(r['url'] for r in db.execute('SELECT url FROM videos WHERE url != ""').fetchall())
        db.close()
        to_download = [it for it in items if it.get('url') not in existing_urls]
        if not to_download:
            return jsonify({'status': 'all_downloaded', 'count': 0})

        with _ytdlp_dl_lock:
            _ytdlp_dl_counter += 1
            queue_id = str(_ytdlp_dl_counter)

        _ytdlp_downloads[queue_id] = {'status': 'queued', 'percent': 0, 'title': f'Queue: 0/{len(to_download)}',
                                       'speed': '', 'error': '', 'queue_total': len(to_download), 'queue_pos': 0}

        def do_queue():
            vdir = get_video_dir()
            succeeded = 0
            failed = 0
            for i, item in enumerate(to_download):
                title = item.get('title', '...')
                _ytdlp_downloads[queue_id].update({
                    'status': 'downloading', 'percent': 0, 'queue_pos': i + 1,
                    'title': f'[{i+1}/{len(to_download)}] {title}', 'speed': '',
                })

                # Try direct URL first, then search fallback if unavailable
                url = item['url']
                use_search = False
                try:
                    check = subprocess.run(
                        [exe, '--simulate', '--no-playlist', url],
                        capture_output=True, text=True, timeout=15, **_CREATION_FLAGS,
                    )
                    if check.returncode != 0:
                        # URL is dead — search for the video by title instead
                        use_search = True
                        _ytdlp_downloads[queue_id]['title'] = f'[{i+1}/{len(to_download)}] Searching: {title}'
                        search_result = subprocess.run(
                            [exe, '--flat-playlist', '--dump-json', f'ytsearch1:{title}'],
                            capture_output=True, text=True, timeout=20, **_CREATION_FLAGS,
                        )
                        if search_result.returncode == 0 and search_result.stdout.strip():
                            found = json.loads(search_result.stdout.strip().split('\n')[0])
                            url = f"https://www.youtube.com/watch?v={found['id']}"
                            title = found.get('title', title)
                            _ytdlp_downloads[queue_id]['title'] = f'[{i+1}/{len(to_download)}] {title}'
                        else:
                            log.warning(f'Video unavailable and search failed: {item.get("title")}')
                            failed += 1
                            continue
                except Exception:
                    pass  # If check fails, try downloading anyway

                try:
                    output_tmpl = os.path.join(vdir, '%(title)s.%(ext)s')
                    proc = subprocess.Popen(
                        [exe, '-f', 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best',
                         '--merge-output-format', 'mp4', '--newline', '--no-playlist',
                         '--write-thumbnail', '--convert-thumbnails', 'jpg',
                         '--write-subs', '--write-auto-subs', '--sub-langs', 'en', '--convert-subs', 'srt',
                         '-o', output_tmpl, url],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                        **_CREATION_FLAGS,
                    )
                    for line in proc.stdout:
                        line = line.strip()
                        if '[download]' in line and '%' in line:
                            try:
                                pct = float(line.split('%')[0].split()[-1])
                                _ytdlp_downloads[queue_id]['percent'] = min(int(pct), 99)
                                if 'at' in line:
                                    _ytdlp_downloads[queue_id]['speed'] = line.split('at')[-1].strip().split('ETA')[0].strip()
                            except (ValueError, IndexError):
                                pass
                    proc.wait(timeout=3600)

                    if proc.returncode == 0:
                        succeeded += 1
                        # Find the file + thumbnail
                        for f in sorted(os.listdir(vdir), key=lambda x: os.path.getmtime(os.path.join(vdir, x)), reverse=True):
                            fpath = os.path.join(vdir, f)
                            if os.path.isfile(fpath) and f.endswith('.mp4') and time.time() - os.path.getmtime(fpath) < 120:
                                filesize = os.path.getsize(fpath)
                                base = os.path.splitext(f)[0]
                                thumb = ''
                                for tx in ('.jpg', '.webp', '.png'):
                                    if os.path.isfile(os.path.join(vdir, base + tx)):
                                        thumb = base + tx
                                        break
                                db = get_db()
                                db.execute('INSERT INTO videos (title, filename, category, folder, url, filesize, thumbnail) VALUES (?, ?, ?, ?, ?, ?, ?)',
                                           (title, f, item.get('category', 'general'), item.get('folder', ''), url, filesize, thumb))
                                db.commit()
                                db.close()
                                break
                except Exception as e:
                    log.error(f'Catalog download failed for {item.get("title")}: {e}')

            summary = f'Done — {succeeded} downloaded'
            if failed:
                summary += f', {failed} unavailable'
            _ytdlp_downloads[queue_id] = {'status': 'complete', 'percent': 100, 'title': summary,
                                           'speed': '', 'error': '', 'queue_total': len(to_download), 'queue_pos': len(to_download)}

        threading.Thread(target=do_queue, daemon=True).start()
        return jsonify({'status': 'queued', 'id': queue_id, 'count': len(to_download)})

    # ─── Audio Library API ─────────────────────────────────────────────

    def get_audio_dir():
        path = os.path.join(get_data_dir(), 'audio')
        os.makedirs(path, exist_ok=True)
        return path

    AUDIO_CATEGORIES = ['general', 'survival', 'medical', 'radio', 'podcast', 'audiobook', 'music', 'training']

    def _get_ffmpeg_url():
        from platform_utils import IS_WINDOWS, IS_MACOS
        if IS_MACOS:
            return 'https://evermeet.cx/ffmpeg/getrelease/zip'
        elif IS_WINDOWS:
            return 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip'
        return 'https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz'

    def get_ffmpeg_path():
        from platform_utils import exe_name
        return os.path.join(get_services_dir(), 'ffmpeg', exe_name('ffmpeg'))

    @app.route('/api/audio')
    def api_audio_list():
        db = get_db()
        rows = db.execute('SELECT * FROM audio ORDER BY folder, title').fetchall()
        db.close()
        adir = get_audio_dir()
        return jsonify([{**dict(r), 'exists': os.path.isfile(os.path.join(adir, r['filename']))} for r in rows])

    @app.route('/api/audio/upload', methods=['POST'])
    def api_audio_upload():
        if 'file' not in request.files:
            return jsonify({'error': 'No file'}), 400
        file = request.files['file']
        filename = secure_filename(file.filename)
        if not filename:
            return jsonify({'error': 'Invalid filename'}), 400
        filepath = os.path.join(get_audio_dir(), filename)
        file.save(filepath)
        filesize = os.path.getsize(filepath) if os.path.isfile(filepath) else 0
        title = request.form.get('title', filename.rsplit('.', 1)[0])
        category = request.form.get('category', 'general')
        folder = request.form.get('folder', '')
        artist = request.form.get('artist', '')
        db = get_db()
        cur = db.execute('INSERT INTO audio (title, filename, category, folder, artist, filesize) VALUES (?, ?, ?, ?, ?, ?)',
                         (title, filename, category, folder, artist, filesize))
        db.commit()
        db.close()
        log_activity('audio_upload', 'media', title)
        return jsonify({'status': 'uploaded', 'id': cur.lastrowid}), 201

    @app.route('/api/audio/<int:aid>', methods=['DELETE'])
    def api_audio_delete(aid):
        db = get_db()
        row = db.execute('SELECT filename, title FROM audio WHERE id = ?', (aid,)).fetchone()
        if row:
            filepath = os.path.join(get_audio_dir(), row['filename'])
            if os.path.isfile(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
            db.execute('DELETE FROM audio WHERE id = ?', (aid,))
            db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    @app.route('/api/audio/<int:aid>', methods=['PATCH'])
    def api_audio_update(aid):
        data = request.get_json() or {}
        ALLOWED_COLS = {'title', 'folder', 'category', 'artist', 'album'}
        fields = []
        vals = []
        for col in ALLOWED_COLS:
            if col in data:
                fields.append(f'{col} = ?')
                vals.append(data[col])
        if not fields:
            return jsonify({'status': 'no changes'})
        vals.append(aid)
        db = get_db()
        db.execute(f'UPDATE audio SET {", ".join(fields)} WHERE id = ?', vals)
        db.commit()
        db.close()
        return jsonify({'status': 'updated'})

    @app.route('/api/audio/serve/<path:filename>')
    def api_audio_serve(filename):
        adir = get_audio_dir()
        safe = os.path.normpath(os.path.join(adir, filename))
        if not safe.startswith(os.path.normpath(adir)) or not os.path.isfile(safe):
            return jsonify({'error': 'Not found'}), 404
        from flask import send_file
        return send_file(safe)

    @app.route('/api/audio/stats')
    def api_audio_stats():
        db = get_db()
        total = db.execute('SELECT COUNT(*) as c FROM audio').fetchone()['c']
        total_size = db.execute('SELECT COALESCE(SUM(filesize),0) as s FROM audio').fetchone()['s']
        by_folder = db.execute('SELECT folder, COUNT(*) as c FROM audio GROUP BY folder ORDER BY folder').fetchall()
        db.close()
        return jsonify({'total': total, 'total_size': total_size, 'total_size_fmt': format_size(total_size),
                        'by_folder': [{'folder': r['folder'] or 'Unsorted', 'count': r['c']} for r in by_folder]})

    @app.route('/api/audio/folders')
    def api_audio_folders():
        db = get_db()
        rows = db.execute('SELECT DISTINCT folder FROM audio WHERE folder != "" ORDER BY folder').fetchall()
        db.close()
        return jsonify([r['folder'] for r in rows])

    @app.route('/api/ytdlp/download-audio', methods=['POST'])
    def api_ytdlp_download_audio():
        """Download audio-only from a URL via yt-dlp."""
        nonlocal _ytdlp_dl_counter
        exe = get_ytdlp_path()
        if not os.path.isfile(exe):
            return jsonify({'error': 'yt-dlp is not installed'}), 400

        data = request.get_json() or {}
        url = data.get('url', '').strip()
        folder = data.get('folder', '')
        category = data.get('category', 'general')
        if not url:
            return jsonify({'error': 'No URL provided'}), 400

        with _ytdlp_dl_lock:
            _ytdlp_dl_counter += 1
            dl_id = str(_ytdlp_dl_counter)

        _ytdlp_downloads[dl_id] = {'status': 'starting', 'percent': 0, 'title': '', 'speed': '', 'error': ''}

        def do_audio_dl():
            adir = get_audio_dir()
            try:
                _ytdlp_downloads[dl_id]['status'] = 'fetching info'
                info_result = subprocess.run(
                    [exe, '--no-download', '--print', '%(title)s|||%(duration_string)s|||%(uploader)s', url],
                    capture_output=True, text=True, timeout=30, **_CREATION_FLAGS,
                )
                parts = info_result.stdout.strip().split('|||')
                audio_title = parts[0] if parts else url
                audio_duration = parts[1] if len(parts) > 1 else ''
                audio_artist = parts[2] if len(parts) > 2 else ''
                _ytdlp_downloads[dl_id]['title'] = audio_title

                _ytdlp_downloads[dl_id]['status'] = 'downloading'
                output_tmpl = os.path.join(adir, '%(title)s.%(ext)s')
                ffmpeg = get_ffmpeg_path()
                if os.path.isfile(ffmpeg):
                    # FFmpeg available — convert to MP3
                    cmd = [exe, '-x', '--audio-format', 'mp3', '--audio-quality', '0',
                           '--newline', '--no-playlist', '--ffmpeg-location', os.path.dirname(ffmpeg),
                           '-o', output_tmpl, url]
                else:
                    # No FFmpeg — download best audio as-is (m4a/opus/webm)
                    cmd = [exe, '-f', 'bestaudio[ext=m4a]/bestaudio',
                           '--newline', '--no-playlist',
                           '-o', output_tmpl, url]

                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, **_CREATION_FLAGS)
                for line in proc.stdout:
                    line = line.strip()
                    if '[download]' in line and '%' in line:
                        try:
                            pct = float(line.split('%')[0].split()[-1])
                            _ytdlp_downloads[dl_id]['percent'] = min(int(pct), 99)
                            if 'at' in line:
                                _ytdlp_downloads[dl_id]['speed'] = line.split('at')[-1].strip().split('ETA')[0].strip()
                        except (ValueError, IndexError):
                            pass
                proc.wait(timeout=1800)

                if proc.returncode == 0:
                    for f in sorted(os.listdir(adir), key=lambda x: os.path.getmtime(os.path.join(adir, x)), reverse=True):
                        fpath = os.path.join(adir, f)
                        if os.path.isfile(fpath) and time.time() - os.path.getmtime(fpath) < 120:
                            filesize = os.path.getsize(fpath)
                            db = get_db()
                            db.execute('INSERT INTO audio (title, filename, category, folder, artist, duration, url, filesize) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                                       (audio_title, f, category, folder, audio_artist, audio_duration, url, filesize))
                            db.commit()
                            db.close()
                            _ytdlp_downloads[dl_id] = {'status': 'complete', 'percent': 100, 'title': audio_title, 'speed': '', 'error': ''}
                            return
                _ytdlp_downloads[dl_id] = {'status': 'error', 'percent': 0, 'title': audio_title, 'speed': '', 'error': f'Download failed (exit code {proc.returncode})'}
            except Exception as e:
                _ytdlp_downloads[dl_id] = {'status': 'error', 'percent': 0, 'title': '', 'speed': '', 'error': str(e)}

        threading.Thread(target=do_audio_dl, daemon=True).start()
        return jsonify({'status': 'started', 'id': dl_id})

    @app.route('/api/ffmpeg/status')
    def api_ffmpeg_status():
        return jsonify({'installed': os.path.isfile(get_ffmpeg_path())})

    @app.route('/api/ffmpeg/install', methods=['POST'])
    def api_ffmpeg_install():
        ffmpeg = get_ffmpeg_path()
        if os.path.isfile(ffmpeg):
            return jsonify({'status': 'already_installed'})
        ffmpeg_dir = os.path.dirname(ffmpeg)
        os.makedirs(ffmpeg_dir, exist_ok=True)

        _ffmpeg_install = {'status': 'downloading', 'percent': 0}

        def do_install():
            try:
                import requests as req
                from platform_utils import exe_name, IS_WINDOWS, make_executable
                url = _get_ffmpeg_url()
                arc_ext = '.zip' if IS_WINDOWS else ('.tar.xz' if 'tar.xz' in url or 'static' in url else '.zip')
                arc_path = os.path.join(ffmpeg_dir, 'ffmpeg' + arc_ext)
                resp = req.get(url, stream=True, timeout=300, allow_redirects=True)
                resp.raise_for_status()
                total = int(resp.headers.get('content-length', 0))
                downloaded = 0
                with open(arc_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=131072):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            _ffmpeg_install['percent'] = int(downloaded / total * 80)
                _ffmpeg_install.update({'status': 'extracting', 'percent': 85})
                ffmpeg_name = exe_name('ffmpeg')
                ffprobe_name = exe_name('ffprobe')
                if arc_path.endswith('.zip'):
                    import zipfile
                    with zipfile.ZipFile(arc_path, 'r') as zf:
                        for member in zf.namelist():
                            basename = os.path.basename(member)
                            if basename in (ffmpeg_name, ffprobe_name):
                                data = zf.read(member)
                                dest = os.path.join(ffmpeg_dir, basename)
                                with open(dest, 'wb') as out:
                                    out.write(data)
                                make_executable(dest)
                else:
                    import tarfile
                    mode = 'r:xz' if arc_path.endswith('.tar.xz') else 'r:gz'
                    with tarfile.open(arc_path, mode) as tf:
                        for member in tf.getnames():
                            basename = os.path.basename(member)
                            if basename in (ffmpeg_name, ffprobe_name, 'ffmpeg', 'ffprobe'):
                                tf.extract(member, ffmpeg_dir)
                                extracted = os.path.join(ffmpeg_dir, member)
                                dest = os.path.join(ffmpeg_dir, exe_name(basename.split('.')[0]))
                                if extracted != dest:
                                    shutil.move(extracted, dest)
                                make_executable(dest)
                os.remove(arc_path)
                _ffmpeg_install.update({'status': 'complete', 'percent': 100})
                log.info('FFmpeg installed')
            except Exception as e:
                _ffmpeg_install.update({'status': 'error', 'percent': 0, 'error': str(e)})
                log.error(f'FFmpeg install failed: {e}')

        threading.Thread(target=do_install, daemon=True).start()
        return jsonify({'status': 'installing', '_ref': id(_ffmpeg_install)})

    # ─── Books / Reference Library API ────────────────────────────────

    def get_books_dir():
        path = os.path.join(get_data_dir(), 'books')
        os.makedirs(path, exist_ok=True)
        return path

    BOOK_CATEGORIES = ['survival', 'medical', 'farming', 'repair', 'radio', 'cooking', 'defense', 'reference', 'fiction', 'general']

    REFERENCE_CATALOG = [
        # Army Field Manuals (Public Domain)
        {'title': 'FM 3-05.70 Survival (Army Survival Manual)', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'survival', 'folder': 'Army Field Manuals',
         'url': 'https://archive.org/download/Fm21-76SurvivalManual/FM%2021-76%20-%20Survival%20Manual.pdf', 'description': 'The definitive military survival guide — shelter, water, food, navigation, signaling. 676 pages.'},
        {'title': 'FM 21-11 First Aid for Soldiers', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'medical', 'folder': 'Army Field Manuals',
         'url': 'https://archive.org/download/fm-21-11-first-aid-for-soldiers/FM%2021-11%20First%20Aid%20for%20Soldiers.pdf', 'description': 'Military first aid — bleeding control, fractures, burns, shock, CPR, field hygiene.'},
        {'title': 'FM 21-76-1 Survival, Evasion, and Recovery', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'survival', 'folder': 'Army Field Manuals',
         'url': 'https://archive.org/download/FM21-76-1/FM%2021-76-1.pdf', 'description': 'Pocket survival guide — evasion, signaling, water procurement, shelter, fire.'},
        {'title': 'FM 5-34 Engineer Field Data', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'repair', 'folder': 'Army Field Manuals',
         'url': 'https://archive.org/download/FM5-34/FM5-34.pdf', 'description': 'Construction, demolition, water supply, power generation, rope and rigging.'},
        # FEMA Guides (Public Domain)
        {'title': 'FEMA: Are You Ready? Emergency Preparedness Guide', 'author': 'FEMA', 'format': 'pdf', 'category': 'survival', 'folder': 'FEMA Guides',
         'url': 'https://www.fema.gov/pdf/areyouready/areyouready_full.pdf', 'description': '204-page comprehensive emergency preparedness guide covering all major disaster types.'},
        # Medical References
        {'title': 'Where There Is No Doctor', 'author': 'David Werner', 'format': 'pdf', 'category': 'medical', 'folder': 'Medical References',
         'url': 'https://archive.org/download/WTINDen2011/WTIND%20en%202011.pdf', 'description': 'Village health care handbook — the standard off-grid medical reference. CC-licensed.'},
        {'title': 'Where There Is No Dentist', 'author': 'Murray Dickson', 'format': 'pdf', 'category': 'medical', 'folder': 'Medical References',
         'url': 'https://archive.org/download/WhereThereIsNoDentist/WhereThereIsNoDentist.pdf', 'description': 'Dental care in remote areas — tooth extraction, fillings, oral health.'},
        # Practical Skills
        {'title': 'The SAS Survival Handbook', 'author': 'John Wiseman', 'format': 'pdf', 'category': 'survival', 'folder': 'Survival Guides',
         'url': 'https://archive.org/download/sas-survival-guide/SAS%20Survival%20Guide.pdf', 'description': 'Comprehensive wilderness survival — climate, terrain, shelter, food, navigation.'},
        {'title': 'Bushcraft 101: Field Guide to Wilderness Survival', 'author': 'Dave Canterbury', 'format': 'pdf', 'category': 'survival', 'folder': 'Survival Guides',
         'url': 'https://archive.org/download/bushcraft-101/Bushcraft%20101.pdf', 'description': 'Modern bushcraft essentials — 5 Cs of survivability, tools, shelter, fire, water.'},
        {'title': 'US Army Ranger Handbook', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'defense', 'folder': 'Army Field Manuals',
         'url': 'https://archive.org/download/ranger-handbook-2017/Ranger%20Handbook%202017.pdf', 'description': 'Ranger operations — leadership, planning, patrols, demolitions, comms, first aid.'},
        # Radio & Communications
        {'title': 'ARRL Ham Radio License Manual', 'author': 'ARRL', 'format': 'pdf', 'category': 'radio', 'folder': 'Radio & Communications',
         'url': 'https://archive.org/download/arrl-ham-radio-license-manual/ARRL%20Ham%20Radio%20License%20Manual.pdf', 'description': 'Study guide for amateur radio Technician license — FCC rules, electronics, operations.'},
        # Homesteading & Food
        {'title': 'Ball Complete Book of Home Preserving', 'author': 'Judi Kingry', 'format': 'pdf', 'category': 'cooking', 'folder': 'Homesteading',
         'url': 'https://archive.org/download/ball-complete-book-home-preserving/Ball%20Complete%20Book%20of%20Home%20Preserving.pdf', 'description': '400 recipes for canning, preserving, pickling — long-term food storage.'},
        {'title': 'Square Foot Gardening', 'author': 'Mel Bartholomew', 'format': 'pdf', 'category': 'farming', 'folder': 'Homesteading',
         'url': 'https://archive.org/download/square-foot-gardening/Square%20Foot%20Gardening.pdf', 'description': 'Revolutionary approach to small-space gardening — grow more in less space.'},
        # Nuclear / CBRN (Public Domain)
        {'title': 'Nuclear War Survival Skills', 'author': 'Cresson Kearny / ORNL', 'format': 'pdf', 'category': 'survival', 'folder': 'Nuclear & CBRN',
         'url': 'https://archive.org/download/NuclearWarSurvivalSkillsCressonKearny1987/Nuclear%20War%20Survival%20Skills%20Cresson%20Kearny%201987.pdf', 'description': 'Uncopyrighted Oak Ridge National Laboratory guide — shelters, ventilation, KFM fallout meter construction, radiation protection, food/water. 18 chapters.'},
        {'title': 'Planning Guide for Response to Nuclear Detonation', 'author': 'FEMA / DHHS', 'format': 'pdf', 'category': 'survival', 'folder': 'Nuclear & CBRN',
         'url': 'https://www.ready.gov/sites/default/files/2022-09/planning-guidance-for-response-to-nuclear-detonation.pdf', 'description': 'FEMA 2022 edition — blast zones, fallout shelter-in-place timing, evacuation decisions, decontamination, mass care.'},
        {'title': 'FM 3-11 NBC Defense Operations', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'survival', 'folder': 'Nuclear & CBRN',
         'url': 'https://irp.fas.org/doddir/army/fm3_11.pdf', 'description': 'Nuclear, biological, and chemical defense — contamination avoidance, protection, decontamination, collective protection.'},
        # Advanced Military Medical
        {'title': 'Emergency War Surgery (5th US Revision)', 'author': 'U.S. Army / Borden Institute', 'format': 'pdf', 'category': 'medical', 'folder': 'Medical References',
         'url': 'https://apps.dtic.mil/sti/tr/pdf/ADA305002.pdf', 'description': 'NATO handbook, free from Borden Institute. Ballistic wound care, burns, blast, cold injury, mass casualties, field surgery. The definitive austere medicine surgical reference.'},
        {'title': 'Special Forces Medical Handbook (ST 31-91B)', 'author': 'U.S. Army Special Forces', 'format': 'pdf', 'category': 'medical', 'folder': 'Medical References',
         'url': 'https://archive.org/download/SpecialForcesMedicalHandbook/Special%20Forces%20Medical%20Handbook%20ST%2031-91B.pdf', 'description': 'Gold standard field medicine reference — clinical diagnosis, tropical medicine, trauma, anesthesia, field pharmacy, lab procedures.'},
        {'title': 'ATP 4-02.5 Casualty Care', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'medical', 'folder': 'Medical References',
         'url': 'https://archive.org/download/ATP4-25x13/ATP%204-02.5%20Casualty%20Care.pdf', 'description': 'Current Army casualty care doctrine — TCCC protocols, point-of-injury care, blood products, CBRN patient treatment.'},
        # Navigation & Land Nav
        {'title': 'FM 3-25.26 Map Reading and Land Navigation', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'survival', 'folder': 'Army Field Manuals',
         'url': 'https://archive.org/download/fm-3-25.26-map-reading-and-land-navigation/FM%203-25.26%20Map%20Reading%20and%20Land%20Navigation.pdf', 'description': 'Definitive military land navigation — topographic maps, UTM/MGRS coordinates, compass, GPS, field sketching, night navigation.'},
        # Emergency Management
        {'title': 'CERT Basic Training Participant Manual', 'author': 'FEMA / Ready.gov', 'format': 'pdf', 'category': 'survival', 'folder': 'FEMA Guides',
         'url': 'https://www.ready.gov/sites/default/files/2019-12/cert_pm_unit-1.pdf', 'description': 'Community Emergency Response Team curriculum — disaster preparedness, fire suppression, medical operations, light search and rescue, ICS, disaster psychology.'},
        {'title': 'LDS Preparedness Manual', 'author': 'LDS Church (via ThesurvivalMom)', 'format': 'pdf', 'category': 'survival', 'folder': 'FEMA Guides',
         'url': 'https://thesurvivalmom.com/wp-content/uploads/2010/08/LDS-Preparedness-Manual.pdf', 'description': 'Comprehensive LDS preparedness guide — 72-hour kits, 3-month food supply, long-term storage (wheat, rice, beans), water, medical, communications, financial.'},
        # Homesteading & Food Production
        {'title': 'USDA Complete Guide to Home Canning (2015)', 'author': 'USDA', 'format': 'pdf', 'category': 'cooking', 'folder': 'Homesteading',
         'url': 'https://archive.org/download/usda-complete-guide-to-home-canning-2015-revision/USDA%20Complete%20Guide%20to%20Home%20Canning%202015%20Revision.pdf', 'description': 'Official USDA safe canning reference — water bath and pressure canning for fruits, vegetables, meats, pickles, jams. Processing times and altitude adjustments.'},
        # Security & Tactics
        {'title': 'FM 3-19.30 Physical Security', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'defense', 'folder': 'Army Field Manuals',
         'url': 'https://irp.fas.org/doddir/army/fm3-19-30.pdf', 'description': 'Physical security planning — threat assessment, perimeter design, access control, barriers, alarms, guard operations.'},
        {'title': 'FM 20-3 Camouflage, Concealment, and Decoys', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'defense', 'folder': 'Army Field Manuals',
         'url': 'https://irp.fas.org/doddir/army/fm20-3.pdf', 'description': 'Military camouflage techniques — individual camouflage, vehicle/equipment concealment, decoys, light and noise discipline, thermal signature management.'},
        # Additional Army Field Manuals
        {'title': 'FM 21-60 Visual Signals', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'survival', 'folder': 'Army Field Manuals',
         'url': 'https://archive.org/download/FM21-60VisualSignals/FM%2021-60%20Visual%20Signals.pdf', 'description': 'Military visual signaling — arm and hand signals, panel signals, pyrotechnics, mirrors, smoke, and air-ground signals. Essential for rescue signaling and unit communications.'},
        {'title': 'FM 5-125 Rigging Techniques, Procedures, and Applications', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'repair', 'folder': 'Army Field Manuals',
         'url': 'https://archive.org/download/FM5-125RiggingTechniques/FM%205-125.pdf', 'description': 'Complete rigging manual — rope construction, knots, blocks and tackles, hoisting, slings, wire rope, load calculation, rope bridges, expedient rigging for heavy loads.'},
        {'title': 'FM 5-426 Carpentry', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'repair', 'folder': 'Army Field Manuals',
         'url': 'https://archive.org/download/FM5-426Carpentry/FM%205-426.pdf', 'description': 'Military carpentry — framing, roofing, floors, doors, windows, concrete forms, scaffolding, and rough construction techniques for field-expedient buildings.'},
        {'title': 'FM 31-70 Basic Cold Weather Manual', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'survival', 'folder': 'Army Field Manuals',
         'url': 'https://archive.org/download/FM31-70BasicColdWeatherManual/FM%2031-70.pdf', 'description': 'Cold weather survival — hypothermia/frostbite prevention and treatment, snow shelters (quinzhee, snow trench, igloo), movement on ice and snow, cold-weather equipment.'},
        {'title': 'FM 90-3 Desert Operations', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'survival', 'folder': 'Army Field Manuals',
         'url': 'https://archive.org/download/FM90-3DesertOperations/FM%2090-3.pdf', 'description': 'Desert survival — heat casualties and prevention, water procurement in arid environments, navigation in featureless terrain, desert shelter, camouflage, and vehicle operations.'},
        {'title': 'FM 10-52 Water Supply in Theaters of Operations', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'survival', 'folder': 'Army Field Manuals',
         'url': 'https://archive.org/download/FM10-52WaterSupply/FM%2010-52.pdf', 'description': 'Large-scale water supply — source reconnaissance, purification systems (reverse osmosis, chlorination), quality testing, storage, distribution networks, decontamination.'},
        {'title': 'FM 21-150 Combatives', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'defense', 'folder': 'Army Field Manuals',
         'url': 'https://archive.org/download/FM21-150Combatives/FM%2021-150%20Combatives.pdf', 'description': 'Hand-to-hand combat — unarmed defense, disarming techniques, bayonet fighting, improvised weapon use, prisoner control, ground fighting, fighting in close quarters.'},
        {'title': 'TC 31-29/A Special Forces Operational Techniques', 'author': 'U.S. Army Special Forces', 'format': 'pdf', 'category': 'survival', 'folder': 'Army Field Manuals',
         'url': 'https://archive.org/download/TC31-29SpecialForcesOperationalTechniques/TC-31-29.pdf', 'description': 'SF field craft — cover and concealment, movement techniques, base camp operations, cache construction, improvised equipment, surveillance, counter-tracking.'},
        {'title': 'FM 3-11.9 Potential Military Chemical/Biological Agents', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'survival', 'folder': 'Nuclear & CBRN',
         'url': 'https://irp.fas.org/doddir/army/fm3-11-9.pdf', 'description': 'CBRN agent recognition — nerve agents (GA/GB/GD/VX), blister agents, blood agents, choking agents, biological threats. Detection, medical management, decontamination protocols.'},
        # Foxfire Series — Appalachian Traditional Skills (essential offline library)
        {'title': 'Foxfire 1 — Hog Dressing, Log Cabin Building, Mountain Crafts', 'author': 'Eliot Wigginton (ed.)', 'format': 'pdf', 'category': 'survival', 'folder': 'Foxfire Series',
         'url': 'https://archive.org/download/foxfireup00foxf/foxfireup00foxf.pdf', 'description': 'Volume 1 of the landmark Foxfire series — log cabin building, hog dressing, mountain crafts, planting by signs, snake lore, hunting, wild plant foods. Appalachian traditional knowledge from elders.'},
        {'title': 'Foxfire 2 — Ghost Stories, Spinning and Weaving, Midwifery, Burial Customs', 'author': 'Eliot Wigginton (ed.)', 'format': 'pdf', 'category': 'survival', 'folder': 'Foxfire Series',
         'url': 'https://archive.org/download/foxfireup02foxf/foxfireup02foxf.pdf', 'description': 'Volume 2 — spinning and weaving, midwifery and childbirth, burial customs, corn shucking, wagon making, butter churning, and Appalachian ghost stories.'},
        {'title': 'Foxfire 3 — Animal Care, Hide Tanning, Summer and Fall Wild Plant Foods', 'author': 'Eliot Wigginton (ed.)', 'format': 'pdf', 'category': 'farming', 'folder': 'Foxfire Series',
         'url': 'https://archive.org/download/foxfire3foxfire3/foxfire3.pdf', 'description': 'Volume 3 — animal care (mules, sheep, hogs), hide tanning, summer/fall wild plant foods, preserving vegetables, banjos and dulcimers, water systems.'},
        {'title': 'Foxfire 4 — Fiddle Making, Springhouses, Horse Trading', 'author': 'Eliot Wigginton (ed.)', 'format': 'pdf', 'category': 'repair', 'folder': 'Foxfire Series',
         'url': 'https://archive.org/download/foxfire4foxfire/foxfire4.pdf', 'description': 'Volume 4 — fiddle making, springhouses and wet-weather springs, horse trading, sassafras tea, wood carving, basket making, blacksmithing.'},
        {'title': 'Foxfire 5 — Ironmaking, Blacksmithing, Flintlock Rifles, Bear Hunting', 'author': 'Eliot Wigginton (ed.)', 'format': 'pdf', 'category': 'repair', 'folder': 'Foxfire Series',
         'url': 'https://archive.org/download/foxfire5foxfire5/foxfire5.pdf', 'description': 'Volume 5 — ironmaking, blacksmithing, flintlock rifles, bear hunting with dogs, ginseng harvesting, faith healing, mountain voices.'},
        {'title': 'Foxfire 6 — Shoemaking, Gourd Banjos, Sorghum, Wine Making', 'author': 'Eliot Wigginton (ed.)', 'format': 'pdf', 'category': 'cooking', 'folder': 'Foxfire Series',
         'url': 'https://archive.org/download/foxfire6foxfire6/foxfire6.pdf', 'description': 'Volume 6 — shoemaking and cobbling, gourd banjos and dulcimers, sorghum syrup making, wine making, dyes, furniture making, log cabin restoration.'},
        # Homesteading Classics
        {'title': 'The Encyclopedia of Country Living', 'author': 'Carla Emery', 'format': 'pdf', 'category': 'farming', 'folder': 'Homesteading',
         'url': 'https://archive.org/download/encyclopediaofcountryliving/Encyclopedia_of_Country_Living.pdf', 'description': 'THE bible of self-sufficient living — 900+ pages covering gardening, grain growing, animal husbandry, food preservation, soap making, butchering, foraging, beekeeping, and more.'},
        {'title': 'Root Cellaring: Natural Cold Storage of Fruits and Vegetables', 'author': 'Mike & Nancy Bubel', 'format': 'pdf', 'category': 'cooking', 'folder': 'Homesteading',
         'url': 'https://archive.org/download/rootcellaringnaturalcoldstorage/Root_Cellaring.pdf', 'description': 'Complete guide to root cellaring — cellar design, temperature zones, what to store (70+ crops), how long each lasts, troubleshooting spoilage without electricity.'},
        {'title': 'Small-Scale Grain Raising', 'author': 'Gene Logsdon', 'format': 'pdf', 'category': 'farming', 'folder': 'Homesteading',
         'url': 'https://archive.org/download/smallscalegraing00logs/small-scale-grain-raising.pdf', 'description': 'Growing grain on 1–5 acres — wheat, corn, oats, barley, rye, sorghum. Hand tools, threshing, milling, storing. The missing link between garden and farm-scale food production.'},
        {'title': 'Storey\'s Guide to Raising Chickens', 'author': 'Gail Damerow', 'format': 'pdf', 'category': 'farming', 'folder': 'Homesteading',
         'url': 'https://archive.org/download/storeysguidetoraising/Storeys_Guide_Raising_Chickens.pdf', 'description': 'Complete chicken keeping — breeds, housing, feeding, health care, egg production, meat birds, incubation, butchering. The definitive backyard poultry reference.'},
        {'title': 'Keeping Bees', 'author': 'John Vivian', 'format': 'pdf', 'category': 'farming', 'folder': 'Homesteading',
         'url': 'https://archive.org/download/keepingbees00vivi/keeping_bees.pdf', 'description': 'Practical beekeeping — hive management, swarm control, disease, honey extraction, wax processing, winter preparation. Bees provide pollination AND calories for the homestead.'},
        {'title': 'Four-Season Harvest', 'author': 'Eliot Coleman', 'format': 'pdf', 'category': 'farming', 'folder': 'Homesteading',
         'url': 'https://archive.org/download/fourseasonharvest/Four_Season_Harvest.pdf', 'description': 'Year-round vegetable growing without electricity — cold frames, low tunnels, unheated greenhouses, variety selection. Harvest fresh food in snow with minimal infrastructure.'},
        {'title': 'Postharvest Technology of Fruits and Vegetables', 'author': 'FAO', 'format': 'pdf', 'category': 'farming', 'folder': 'Homesteading',
         'url': 'https://www.fao.org/3/x5056e/x5056e.pdf', 'description': 'FAO guide to extending the life of harvested crops — storage, cooling, packaging, grading, transport. Prevents post-harvest losses critical when food production is your lifeline.'},
        # Water & Sanitation
        {'title': 'Slow Sand Filtration — Technical Brief', 'author': 'WEDC / Loughborough University', 'format': 'pdf', 'category': 'survival', 'folder': 'Water & Sanitation',
         'url': 'https://www.ircwash.org/sites/default/files/Visscher-1990-Slow.pdf', 'description': 'Design and construction of slow sand filters — low-tech, highly effective water purification requiring no chemicals or electricity. Proven technology for village-scale clean water.'},
        {'title': 'Emergency Water Supply Manual', 'author': 'AWWA / FEMA', 'format': 'pdf', 'category': 'survival', 'folder': 'Water & Sanitation',
         'url': 'https://www.fema.gov/pdf/plan/prevent/rms/154/fema154.pdf', 'description': 'Emergency water supply planning — source assessment, treatment, storage, distribution. Covers contingency planning for utilities and improvised community water supply after disasters.'},
        {'title': 'Solar Water Disinfection (SODIS) — A Guide', 'author': 'Eawag/Sandec', 'format': 'pdf', 'category': 'survival', 'folder': 'Water & Sanitation',
         'url': 'https://www.sodis.ch/methode/anwendung/ausbildungsmaterial/dokumente_material/mannual_e.pdf', 'description': 'Using sunlight to disinfect drinking water — PET bottles, exposure times by season and turbidity, verification. Works anywhere with sunlight, costs nothing.'},
        {'title': 'Small Community Water Supplies', 'author': 'IRC International Water and Sanitation Centre', 'format': 'pdf', 'category': 'survival', 'folder': 'Water & Sanitation',
         'url': 'https://www.ircwash.org/sites/default/files/211.1-82SC-15055.pdf', 'description': 'Complete guide to small-community water supply systems — springs, wells, rainwater, pumps, piping, treatment, management. Everything needed for village-scale water infrastructure.'},
        {'title': 'Rainwater Collection for the Mechanically Challenged', 'author': 'Suzy Banks & Richard Heinichen', 'format': 'pdf', 'category': 'survival', 'folder': 'Water & Sanitation',
         'url': 'https://archive.org/download/rainwatercollection00bank/rainwater_collection.pdf', 'description': 'Practical rainwater harvesting — catchment areas, first-flush diverters, storage tanks, filtration, legality by state. Building systems for Texas and drought-prone regions.'},
        # Energy / Power
        {'title': 'Biogas Technology — FAO Agricultural Services Bulletin', 'author': 'FAO', 'format': 'pdf', 'category': 'repair', 'folder': 'Energy & Power',
         'url': 'https://www.fao.org/3/w7046e/w7046e.pdf', 'description': 'Building and operating biogas digesters — generating cooking and lighting gas from animal manure and organic waste. Complete construction plans for family-scale biogas plants.'},
        {'title': 'Micro-Hydropower Systems: A Handbook', 'author': 'Natural Resources Canada', 'format': 'pdf', 'category': 'repair', 'folder': 'Energy & Power',
         'url': 'https://www.nrcan.gc.ca/sites/www.nrcan.gc.ca/files/canmetenergy/files/pubs/Micro-HydropowerSystemsHandbook.pdf', 'description': 'Complete guide to small hydroelectric systems — site assessment, flow measurement, head calculation, turbine selection, penstock design, electrical systems. 24/7 renewable power from streams.'},
        {'title': 'Wind Power Workshop', 'author': 'Hugh Piggott', 'format': 'pdf', 'category': 'repair', 'folder': 'Energy & Power',
         'url': 'https://archive.org/download/windpowerworkshop/Wind_Power_Workshop.pdf', 'description': 'Build your own wind turbine from scratch — blade carving, alternator winding, tower construction. The classic DIY wind power manual from the off-grid community.'},
        {'title': 'Solar Photovoltaic Systems Technical Training Manual', 'author': 'USAID / IT Power', 'format': 'pdf', 'category': 'repair', 'folder': 'Energy & Power',
         'url': 'https://archive.org/download/solarpvsystems/Solar_PV_Technical_Training.pdf', 'description': 'Complete PV system design — site analysis, load calculation, panel sizing, battery banks, charge controllers, inverters, wiring, troubleshooting. From theory to field installation.'},
        # Additional Medical References
        {'title': 'The Ship Captain\'s Medical Guide (22nd Edition)', 'author': 'UK Maritime & Coastguard Agency', 'format': 'pdf', 'category': 'medical', 'folder': 'Medical References',
         'url': 'https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/915232/Ship_captains_medical_guide.pdf', 'description': 'Medical care at sea with no physician — diagnosis and treatment for 200+ conditions, surgical procedures, childbirth, medications, resuscitation. Free from UK government. Excellent austere-environment reference.'},
        {'title': 'Medical Management of Radiological Casualties', 'author': 'Armed Forces Radiobiology Research Institute', 'format': 'pdf', 'category': 'medical', 'folder': 'Medical References',
         'url': 'https://www.usuhs.edu/sites/default/files/media/afrri/pdf/4edmmrchandbook.pdf', 'description': 'AFRRI handbook — radiation injury diagnosis, ARS staging, treatment protocols, contamination decontamination, combined injuries (blast+radiation), triage criteria.'},
        {'title': 'Psychological First Aid Field Operations Guide (2nd Ed.)', 'author': 'National Child Traumatic Stress Network / NCPTSD', 'format': 'pdf', 'category': 'medical', 'folder': 'Medical References',
         'url': 'https://www.ptsd.va.gov/professional/treat/type/PFA/PFA_2ndEditionwithappendices.pdf', 'description': 'Mental health first aid for disaster survivors — Listen, Protect, Connect model. Practical, evidence-based psychological support for acute traumatic stress without professional resources.'},
        {'title': 'Merck Manual of Medical Information (1899 Edition — Public Domain)', 'author': 'Merck & Co.', 'format': 'pdf', 'category': 'medical', 'folder': 'Medical References',
         'url': 'https://archive.org/download/merckmanualmedic00merc/merck_manual_1899.pdf', 'description': 'The original Merck Manual — fully public domain. Diseases, symptoms, treatments, pharmacology from the late 1800s. Historical perspective on medicine without modern supplies.'},
        {'title': 'Hand to Hand Health Care — A Primary Health Care Manual', 'author': 'Peace Corps', 'format': 'pdf', 'category': 'medical', 'folder': 'Medical References',
         'url': 'https://files.peacecorps.gov/multimedia/pdf/library/M0006_handtohandhealth.pdf', 'description': 'Peace Corps community health manual — nutrition, water sanitation, maternal/child health, common diseases, oral rehydration, immunization, first aid. Designed for non-medical community health workers.'},
        {'title': 'Management of Dead Bodies After Disasters', 'author': 'PAHO / WHO', 'format': 'pdf', 'category': 'medical', 'folder': 'Medical References',
         'url': 'https://iris.paho.org/bitstream/handle/10665.2/721/9789275116227_eng.pdf', 'description': 'Critical but overlooked disaster skill — field identification, proper handling, mass fatality management, preventing disease. PAHO/WHO guide for mass casualty incidents.'},
        # Construction & Infrastructure
        {'title': 'The Owner-Built Home', 'author': 'Ken Kern', 'format': 'pdf', 'category': 'repair', 'folder': 'Construction',
         'url': 'https://archive.org/download/theownerbuilthome/The_Owner_Built_Home.pdf', 'description': 'Classic owner-builder guide — site selection, foundation types, adobe, rammed earth, cob, stone, timber frame. Philosophy of building your own home with available materials and hand tools.'},
        {'title': 'USDA Wood Handbook — Wood as an Engineering Material', 'author': 'USDA Forest Products Laboratory', 'format': 'pdf', 'category': 'repair', 'folder': 'Construction',
         'url': 'https://www.fpl.fs.fed.us/documnts/fplgtr/fplgtr282.pdf', 'description': 'Complete wood properties reference — species characteristics, moisture effects, mechanical properties, fasteners, joints, gluing, wood composites. Essential for building with locally-sourced timber.'},
        {'title': 'Village Technology Handbook', 'author': 'VITA (Volunteers in Technical Assistance)', 'format': 'pdf', 'category': 'repair', 'folder': 'Construction',
         'url': 'https://archive.org/download/villagetechnology/Village_Technology_Handbook.pdf', 'description': 'VITA\'s classic — building construction, water supply, sanitation, small-scale food processing, appropriate technology for self-sufficient villages. Practical guides for post-grid scenarios.'},
        {'title': 'Earthbag Construction — The Tools, Tricks, and Techniques', 'author': 'Kaki Hunter & Donald Kiffmeyer', 'format': 'pdf', 'category': 'repair', 'folder': 'Construction',
         'url': 'https://archive.org/download/earthbagconstruction/earthbag_construction.pdf', 'description': 'Build strong, low-cost structures from polypropylene bags filled with earth — foundations, domes, walls, arches. Minimal tools, locally available materials, earthquake/hurricane resistant.'},
        # Navigation & Communications
        {'title': 'National Interoperability Field Operations Guide (NIFOG)', 'author': 'DHS / FEMA', 'format': 'pdf', 'category': 'radio', 'folder': 'Radio & Communications',
         'url': 'https://www.dhs.gov/sites/default/files/publications/nifog.pdf', 'description': 'Emergency communications interoperability guide — NIMS radio channels, frequencies, ICS communications, plain language, common protocols for multi-agency disasters. Every prepper\'s communications reference.'},
        {'title': 'Emergency Response Guidebook (ERG 2020)', 'author': 'DOT / Transport Canada', 'format': 'pdf', 'category': 'survival', 'folder': 'FEMA Guides',
         'url': 'https://www.phmsa.dot.gov/sites/phmsa.dot.gov/files/2020ERG.pdf', 'description': 'First responder guide to 3,000+ hazardous materials — identification, safe distances, protective action zones, fire/spill response. Essential for CBRN incidents from vehicle accidents or industrial disasters.'},
        {'title': 'ICS 100: Introduction to the Incident Command System', 'author': 'FEMA Emergency Management Institute', 'format': 'pdf', 'category': 'survival', 'folder': 'FEMA Guides',
         'url': 'https://training.fema.gov/is/courseoverview.aspx?code=is-100.c', 'description': 'FEMA free ICS course — unified command structure, span of control, communication, resource management. The organizational system used to manage any disaster response effectively.'},
        {'title': 'ARRL Antenna Book for Radio Communications (older edition)', 'author': 'ARRL', 'format': 'pdf', 'category': 'radio', 'folder': 'Radio & Communications',
         'url': 'https://archive.org/download/ARRLAntennaBook/ARRL_Antenna_Book.pdf', 'description': 'ARRL\'s definitive antenna reference — dipoles, verticals, Yagis, loops, wire antennas, propagation, feedlines, construction. Build effective communications antennas with available materials.'},
        # Agricultural Extension / USDA
        {'title': 'USDA Farmers Bulletin: Canning and Preserving (No. 1762)', 'author': 'USDA', 'format': 'pdf', 'category': 'cooking', 'folder': 'USDA Publications',
         'url': 'https://archive.org/download/CAT87206536/CAT87206536.pdf', 'description': 'USDA classic canning bulletin — water bath and pressure canning, acidity, processing times, spoilage indicators. Public domain from the era of kitchen self-sufficiency.'},
        {'title': 'USDA Farmers Bulletin: Poultry Keeping (No. 2009)', 'author': 'USDA', 'format': 'pdf', 'category': 'farming', 'folder': 'USDA Publications',
         'url': 'https://archive.org/download/farmersbulletin2009/farmers_bulletin_2009.pdf', 'description': 'USDA guide to small-flock chicken and turkey keeping — housing, feeding, breeding, disease management, egg and meat production on a small scale.'},
        {'title': 'USDA Farmers Bulletin: Beekeeping for Beginners', 'author': 'USDA', 'format': 'pdf', 'category': 'farming', 'folder': 'USDA Publications',
         'url': 'https://archive.org/download/usda-beekeeping-beginners/usda_beekeeping.pdf', 'description': 'Classic USDA beekeeping introduction — hive types, bees biology, seasonal management, honey extraction, disease recognition. Essential for honey production and crop pollination.'},
        {'title': 'USDA Farmers Bulletin: Home Drying of Fruits and Vegetables', 'author': 'USDA', 'format': 'pdf', 'category': 'cooking', 'folder': 'USDA Publications',
         'url': 'https://archive.org/download/usda-home-drying/home_drying_fruits_vegetables.pdf', 'description': 'Sun drying, air drying, and oven drying fruits, vegetables, herbs, and meat. Traditional dehydration methods requiring no electricity for 1-2 year shelf life.'},
        # Additional Survival / General
        {'title': 'How to Survive the End of the World as We Know It', 'author': 'James Wesley Rawles', 'format': 'pdf', 'category': 'survival', 'folder': 'Survival Guides',
         'url': 'https://archive.org/download/howtosurvivetend00rawl/how_to_survive.pdf', 'description': 'Comprehensive prepper reference — food storage, water, medical, weapons, communications, financial preparedness, retreat location selection, community building. From SurvivalBlog founder.'},
        {'title': 'Wilderness Navigation (2nd Ed.)', 'author': 'Bob Burns & Mike Burns', 'format': 'pdf', 'category': 'survival', 'folder': 'Survival Guides',
         'url': 'https://archive.org/download/wildernessnavigation/Wilderness_Navigation.pdf', 'description': 'Navigation beyond GPS — compass use, map reading, triangulation, altimeter navigation, GPS backup, route-finding by terrain features. For hiking, hunting, and when GPS fails.'},
        {'title': 'Tom Brown\'s Field Guide to Wilderness Survival', 'author': 'Tom Brown Jr.', 'format': 'pdf', 'category': 'survival', 'folder': 'Survival Guides',
         'url': 'https://archive.org/download/tombrownssurvival/Tom_Browns_Survival.pdf', 'description': 'Tom Brown\'s Tracker School teachings — tracking, fire by friction, water finding, shelter construction, plant foods, primitive trapping. Apache-tradition wilderness survival philosophy.'},
        {'title': 'Primitive Wilderness Living and Survival Skills', 'author': 'John & Geri McPherson', 'format': 'pdf', 'category': 'survival', 'folder': 'Survival Guides',
         'url': 'https://archive.org/download/primitivewilderness/Primitive_Wilderness_Survival.pdf', 'description': 'Deep wilderness living — tanning hides, making buckskin, bone and stone tools, primitive pottery, atlatl construction, hide glue, traditional fire craft.'},
        {'title': 'The Disaster Preparedness Handbook', 'author': 'Arthur Bradley, PhD', 'format': 'pdf', 'category': 'survival', 'folder': 'Survival Guides',
         'url': 'https://archive.org/download/disasterpreparedness/Disaster_Preparedness_Handbook.pdf', 'description': 'Systematic preparedness planning — threat analysis, supplies prioritization, financial preparedness, communication planning, home hardening, community resilience. Engineer\'s approach to prepping.'},
        # Chemical/Industrial Safety
        {'title': 'NIOSH Pocket Guide to Chemical Hazards', 'author': 'CDC / NIOSH', 'format': 'pdf', 'category': 'survival', 'folder': 'Nuclear & CBRN',
         'url': 'https://www.cdc.gov/niosh/npg/pdfs/npg.pdf', 'description': '729 chemicals — exposure limits, health hazards, protective equipment, emergency response, physical properties. Identify and respond to industrial chemical exposures from accidents or CBRN incidents.'},
        {'title': 'Recognition and Management of Pesticide Poisonings', 'author': 'EPA', 'format': 'pdf', 'category': 'medical', 'folder': 'Medical References',
         'url': 'https://www.epa.gov/sites/default/files/documents/rmpp_6thed_final_lowresopt.pdf', 'description': 'EPA guide for clinicians — organophosphates, carbamates, pyrethroids, herbicides, fumigants. Toxidrome recognition, antidotes (atropine, pralidoxime), decontamination, supportive care.'},
        # Weather & Meteorology
        {'title': 'Aviation Weather (AC 00-6B)', 'author': 'FAA', 'format': 'pdf', 'category': 'survival', 'folder': 'Weather & Meteorology',
         'url': 'https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_00-6B.pdf', 'description': 'Definitive FAA weather guide — cloud types and formation, pressure systems, fronts, thunderstorm lifecycle, turbulence, wind shear, icing, fog. Best plain-English meteorology reference for non-pilots too.'},
        {'title': 'NOAA Skywarn Storm Spotter Training Manual', 'author': 'NOAA / NWS', 'format': 'pdf', 'category': 'survival', 'folder': 'Weather & Meteorology',
         'url': 'https://www.weather.gov/media/owlie/spottershome0916.pdf', 'description': 'Official NWS severe weather spotter training — supercell identification, tornado signatures, wall clouds, shelf clouds, hail shafts, flooding, winter storms. Report severe weather accurately to NWS.'},
        {'title': 'The AMS Glossary of Meteorology (3rd Ed.)', 'author': 'American Meteorological Society', 'format': 'pdf', 'category': 'survival', 'folder': 'Weather & Meteorology',
         'url': 'https://archive.org/download/glossaryofmeteor00hube/glossaryofmeteor00hube.pdf', 'description': '12,000 weather terms defined — pressure gradients, lapse rates, vorticity, hodographs, orographic lift, CAPE. The complete reference for understanding NWS forecast discussions and meteorology literature.'},
        {'title': 'NWS Training Manual — Observing and Forecasting', 'author': 'NOAA / NWS', 'format': 'pdf', 'category': 'survival', 'folder': 'Weather & Meteorology',
         'url': 'https://www.weather.gov/media/training/nwstm_a32.pdf', 'description': 'Official NWS observer training — measuring temperature, precipitation, visibility, cloud cover, pressure. How to set up and run a personal weather station and contribute to COCORAHS network.'},
        {'title': 'Mariner\'s Weather Handbook', 'author': 'Steve and Linda Dashew', 'format': 'pdf', 'category': 'survival', 'folder': 'Weather & Meteorology',
         'url': 'https://archive.org/download/marinersweatherh00dash/marinersweatherh00dash.pdf', 'description': 'Offshore weather prediction — reading barometer, interpreting GRIB files, squall lines, gale avoidance, tropical weather, storm tactics. Critical for coastal survival and maritime emergency operations.'},
        {'title': 'Understanding Weather and Climate (2nd Ed.)', 'author': 'Aguado & Burt', 'format': 'pdf', 'category': 'survival', 'folder': 'Weather & Meteorology',
         'url': 'https://archive.org/download/understandingwea00agua/understandingwea00agua.pdf', 'description': 'College-level meteorology textbook — atmosphere composition, solar radiation, humidity, clouds, precipitation, pressure, wind, air masses, fronts, storms. Complete meteorological education.'},
        {'title': 'Weather Analysis and Forecasting Handbook', 'author': 'Tim Vasquez', 'format': 'pdf', 'category': 'survival', 'folder': 'Weather & Meteorology',
         'url': 'https://archive.org/download/weatheranalysisf00vasq/weatheranalysisf00vasq.pdf', 'description': 'Forecaster\'s reference — surface analysis, upper-air charts, satellite interpretation, radar patterns, model output statistics, sounding analysis, severe weather parameters (CAPE, SRH, STP).'},
        {'title': 'NOAA Weather Radio — Complete User Guide', 'author': 'NOAA', 'format': 'pdf', 'category': 'survival', 'folder': 'Weather & Meteorology',
         'url': 'https://www.weather.gov/nwr/nwrbrochure.pdf', 'description': 'Programming and using NOAA Weather Radio All Hazards — SAME codes, specific alert types, tone alert frequencies, portable unit selection, backup power operation. Your lifeline when internet is down.'},
        {'title': 'Field Guide to the Atmosphere', 'author': 'Vincent Schaefer & John Day', 'format': 'pdf', 'category': 'survival', 'folder': 'Weather & Meteorology',
         'url': 'https://archive.org/download/fieldguidetoatmo00scha/fieldguidetoatmo00scha.pdf', 'description': 'Peterson Field Guide — identify clouds, precipitation types, optical phenomena (halos, rainbows, coronas), lightning, dust and sand features. Read the sky to forecast weather without instruments.'},
        {'title': 'Tornado Preparedness and Response (FEMA 431)', 'author': 'FEMA', 'format': 'pdf', 'category': 'survival', 'folder': 'Weather & Meteorology',
         'url': 'https://www.fema.gov/sites/default/files/2020-07/fema_tornado-preparedness-and-response_431.pdf', 'description': 'Comprehensive tornado preparedness — shelter construction standards, mobile home risks, warning systems, search and rescue, mass casualty planning. Includes safe room design specifications.'},
        {'title': 'Hurricane Preparedness Guide (FEMA)', 'author': 'FEMA / NOAA', 'format': 'pdf', 'category': 'survival', 'folder': 'Weather & Meteorology',
         'url': 'https://www.fema.gov/sites/default/files/2020-07/fema_hurricane-preparedness.pdf', 'description': 'Complete hurricane readiness — Saffir-Simpson scale, storm surge risk, evacuation zones, shelter-in-place criteria, post-storm hazards (floodwater, mold, CO). Applicable to any major storm scenario.'},
        # Maps & Navigation Guides
        {'title': 'USGS Topographic Map Symbols', 'author': 'USGS', 'format': 'pdf', 'category': 'survival', 'folder': 'Maps & Navigation',
         'url': 'https://pubs.usgs.gov/gip/TopographicMapSymbols/topomapsymbols.pdf', 'description': 'Official guide to USGS topo map symbols — contours, water features, vegetation, structures, roads, boundaries, survey markers. Read any 7.5-minute USGS quad map accurately for land navigation.'},
        {'title': 'FAA Aeronautical Chart User\'s Guide', 'author': 'FAA', 'format': 'pdf', 'category': 'survival', 'folder': 'Maps & Navigation',
         'url': 'https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/aero_guide/media/cug-complete.pdf', 'description': 'Complete guide to reading FAA sectional and IFR enroute charts — terrain symbols, obstruction towers, airspace boundaries, VORs, emergency landing strips, restricted areas. Understand all aviation charts.'},
        {'title': 'FEMA Flood Map Reading Guide', 'author': 'FEMA', 'format': 'pdf', 'category': 'survival', 'folder': 'Maps & Navigation',
         'url': 'https://www.fema.gov/sites/default/files/2020-07/howto1.pdf', 'description': 'How to read FIRM flood maps — identify your flood zone, base flood elevation, floodway vs. flood fringe, LOMA process. Know if your property floods before you buy or before the water rises.'},
        {'title': 'Map and Compass (Orienteering Handbook)', 'author': 'Kjellström', 'format': 'pdf', 'category': 'survival', 'folder': 'Maps & Navigation',
         'url': 'https://archive.org/download/beorienteering00kjel/beorienteering00kjel.pdf', 'description': 'The definitive orienteering reference — magnetic declination, bearings, resection, night navigation, contour interpretation, pace counting, terrain association. From Sweden\'s orienteering master.'},
        {'title': 'Land Navigation (TC 3-25.26)', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'survival', 'folder': 'Maps & Navigation',
         'url': 'https://archive.org/download/tc-3-25.26-land-navigation/TC_3-25.26_Land_Navigation.pdf', 'description': 'Updated Army land navigation manual — MGRS/UTM coordinates, GPS receiver operation, terrain association, route planning, night navigation, map overlays. Supersedes FM 3-25.26.'},
        {'title': 'USGS Introduction to GIS and Spatial Analysis', 'author': 'USGS / ESRI', 'format': 'pdf', 'category': 'survival', 'folder': 'Maps & Navigation',
         'url': 'https://archive.org/download/introductiontogi00usgs/introductiontogi00usgs.pdf', 'description': 'Using GIS for spatial analysis — loading topo maps, elevation analysis, watershed delineation, route optimization. Applicable to QGIS (free) for creating custom offline maps and terrain analysis.'},
        {'title': 'Geologic Hazards — USGS Field Guide', 'author': 'USGS', 'format': 'pdf', 'category': 'survival', 'folder': 'Maps & Navigation',
         'url': 'https://pubs.usgs.gov/fs/2013/3094/pdf/fs2013-3094.pdf', 'description': 'Reading geologic maps for hazard identification — landslide susceptibility, earthquake fault zones, volcanic hazards, ground subsidence, debris flows. Identify dangerous terrain from published maps.'},
        {'title': 'Nautical Chart User\'s Guide (NOAA)', 'author': 'NOAA', 'format': 'pdf', 'category': 'survival', 'folder': 'Maps & Navigation',
         'url': 'https://nauticalcharts.noaa.gov/publications/docs/chart-users-guide.pdf', 'description': 'Reading NOAA nautical charts — depth soundings, hazard symbols, anchorage areas, aids to navigation, tidal datum, bridge clearances. Navigate coastal and inland waterways without GPS.'},
        # Amateur Radio & Communications
        {'title': 'ARRL Handbook for Radio Communications', 'author': 'ARRL', 'format': 'pdf', 'category': 'radio', 'folder': 'Amateur Radio',
         'url': 'https://archive.org/download/arrl-handbook-1964/arrl_handbook_1964.pdf', 'description': 'The bible of amateur radio — antenna theory, propagation, transmitter/receiver design, digital modes, emergency communication. Public domain 1964 edition; principles unchanged for HF/VHF survival comms.'},
        {'title': 'NIFOG — National Interoperability Field Operations Guide', 'author': 'DHS / SAFECOM', 'format': 'pdf', 'category': 'radio', 'folder': 'Amateur Radio',
         'url': 'https://www.dhs.gov/sites/default/files/publications/NIFOG_v1.7.pdf', 'description': 'Standardized radio channels for multi-agency emergency operations — NPSPAC, VCALL, interoperability channels, programming codes. Know what channels first responders and emergency managers use.'},
        {'title': 'ARRL Emergency Communication Handbook (2nd Ed.)', 'author': 'ARRL', 'format': 'pdf', 'category': 'radio', 'folder': 'Amateur Radio',
         'url': 'https://archive.org/download/arrl-emergency-comm/arrl_emergency_comm_handbook.pdf', 'description': 'ARES/RACES emergency communication protocols — net operations, traffic handling, ICS integration, shelter and EOC setup, disaster communication planning. For serious emergency preparedness.'},
        {'title': 'Introduction to Radio Frequency (RF) Propagation', 'author': 'John Volakis', 'format': 'pdf', 'category': 'radio', 'folder': 'Amateur Radio',
         'url': 'https://archive.org/download/intro-rf-propagation/rf_propagation_intro.pdf', 'description': 'Understanding how radio waves travel — ground wave, sky wave, NVIS, troposcatter, ducting, ionospheric layers. Know when HF will reach across the continent vs. when it won\'t.'},
        {'title': 'Winlink Emergency Digital Radio Email — User Guide', 'author': 'Winlink.org', 'format': 'pdf', 'category': 'radio', 'folder': 'Amateur Radio',
         'url': 'https://winlink.org/sites/default/files/UserGuide/Winlink_Manual.pdf', 'description': 'Email without internet — Winlink 2000 global radio email system. Setup, routing, message templates, ICS forms, peer-to-peer mode (RMS Express/Vara). Works from solar-powered HF radio anywhere on Earth.'},
        {'title': 'JS8Call Digital Messaging — User Manual', 'author': 'Jordan Sherer KN4CRD', 'format': 'pdf', 'category': 'radio', 'folder': 'Amateur Radio',
         'url': 'https://js8call.com/docs/JS8Call_User_Manual.pdf', 'description': 'Store-and-forward text messaging over radio — no repeaters, no internet. JS8Call heartbeat beaconing, directed messages, group messaging, relay through other stations. Designed for off-grid emergency communication.'},
        {'title': 'FCC Part 97 Amateur Radio Rules — Complete Annotated Text', 'author': 'FCC', 'format': 'pdf', 'category': 'radio', 'folder': 'Amateur Radio',
         'url': 'https://www.ecfr.gov/current/title-47/chapter-I/subchapter-D/part-97', 'description': 'Complete FCC Part 97 amateur radio regulations — station identification rules, third-party traffic, emergency communications exemptions, power limits by band, prohibited transmissions, RACES and ARES authorization. Know what you can legally transmit in an emergency.'},
        # Legal & Governance (Post-Disaster)
        {'title': 'FEMA Comprehensive Preparedness Guide CPG 101 (v2.0)', 'author': 'FEMA', 'format': 'pdf', 'category': 'survival', 'folder': 'Legal & Governance',
         'url': 'https://www.fema.gov/sites/default/files/2020-04/CPG_101_V2_30NOV2010_FINAL.pdf', 'description': 'Official emergency operations planning guide — threat/hazard identification, capability assessment, plan development, training and exercise framework. How governments organize emergency response.'},
        {'title': 'Incident Command System (ICS) Reference Guide', 'author': 'FEMA / NIMS', 'format': 'pdf', 'category': 'survival', 'folder': 'Legal & Governance',
         'url': 'https://training.fema.gov/emiweb/is/icsresource/assets/ics%20forms/ics%20form%20201,%20incident%20briefing%20(v3).pdf', 'description': 'ICS organizational structure — command, operations, planning, logistics, finance. ICS forms 201-225. Integrate with any municipal emergency response as a volunteer or team leader.'},
        {'title': 'FEMA Emergency Operations Center (EOC) Reference Guide', 'author': 'FEMA', 'format': 'pdf', 'category': 'survival', 'folder': 'Legal & Governance',
         'url': 'https://www.fema.gov/sites/default/files/2020-07/NIMS_EOC_Reference_Guide.pdf', 'description': 'How Emergency Operations Centers work — staffing, coordination with field teams, resource ordering, situation reports, WebEOC-style status boards. Blueprint for setting up a community command post.'},
        {'title': 'Extreme Heat: A Prevention Guide (CDC)', 'author': 'CDC', 'format': 'pdf', 'category': 'medical', 'folder': 'Legal & Governance',
         'url': 'https://www.cdc.gov/disasters/extremeheat/pdf/extremeheat.pdf', 'description': 'Comprehensive heat emergency guide — heat index thresholds, cooling center setup, identifying heat exhaustion vs. heat stroke, at-risk populations, community notification systems.'},
        # Energy & Power (additional)
        {'title': 'Micro-Hydro Power Systems: Design, Installation and Operation', 'author': 'ITDG / Practical Action', 'format': 'pdf', 'category': 'survival', 'folder': 'Energy & Power',
         'url': 'https://archive.org/download/micro-hydro-power-systems/micro_hydro_power_design.pdf', 'description': 'Generating electricity from streams and rivers — head and flow calculations, turbine selection (Pelton, Turgo, crossflow), penstock sizing, generator wiring, governor control, battery charging integration. Works at any scale from 100W to 10kW.'},
        {'title': 'Wind Energy Basics: A Guide to Home and Community-Scale Wind Energy Systems', 'author': 'Paul Gipe', 'format': 'pdf', 'category': 'survival', 'folder': 'Energy & Power',
         'url': 'https://archive.org/download/wind-energy-basics-gipe/wind_energy_basics.pdf', 'description': 'Small wind turbine fundamentals — site assessment with anemometer, tower height vs. output, horizontal vs. vertical axis designs, battery bank integration, grid-tie vs. off-grid. Covers DIY turbine builds from salvaged alternators.'},
        {'title': 'Battery Storage for Renewable Energy Systems — Lead-Acid and Lithium Compared', 'author': 'NREL / Sandia National Labs', 'format': 'pdf', 'category': 'survival', 'folder': 'Energy & Power',
         'url': 'https://www.nrel.gov/docs/fy19osti/74426.pdf', 'description': 'Practical battery technology comparison — flooded lead-acid vs AGM vs LiFePO4 vs NMC, cycle life at different depths of discharge, temperature effects, BMS requirements, safety and thermal runaway risks, true cost per kWh over lifespan.'},
        # Construction (additional)
        {'title': 'Timber Framing for the Rest of Us: A Guide to Contemporary Post and Beam Construction', 'author': 'Rob Roy', 'format': 'pdf', 'category': 'survival', 'folder': 'Construction',
         'url': 'https://archive.org/download/timber-framing-rest-of-us/timber_framing_rest_of_us.pdf', 'description': 'Traditional timber joinery without modern fasteners — mortise and tenon, dovetail, and scarf joints; timber selection and curing; raising techniques for small crews; structural calculations for simple bents. Build a permanent shelter from standing dead timber.'},
        {'title': 'Adobe and Rammed Earth Buildings: Design and Construction', 'author': 'Paul Graham McHenry', 'format': 'pdf', 'category': 'survival', 'folder': 'Construction',
         'url': 'https://archive.org/download/adobe-rammed-earth-buildings/adobe_rammed_earth.pdf', 'description': 'Building with earth — adobe brick mixing and firing, wall thickness for thermal mass, rammed earth forms and compaction, foundation requirements, weatherproofing, seismic reinforcement, and finish plasters. Build a permanent blast-resistant structure from dirt.'},
        {'title': 'Stone Masonry: A Guide to Dry-Stack, Mortar, and Foundation Construction', 'author': 'Charles McRaven', 'format': 'pdf', 'category': 'survival', 'folder': 'Construction',
         'url': 'https://archive.org/download/stone-masonry-mcraven/stone_masonry_guide.pdf', 'description': 'Building with natural stone — selecting and shaping fieldstone, dry-stack wall techniques, lime and Portland mortar mixes, rubble trench foundations, arch construction, fireplace and chimney building. No quarrying equipment required.'},
        # Radio & Communications (additional)
        {'title': 'APRS — Automatic Packet Reporting System: The Complete Guide', 'author': 'Bob Bruninga WB4APR', 'format': 'pdf', 'category': 'radio', 'folder': 'Radio & Communications',
         'url': 'https://archive.org/download/aprs-complete-guide/aprs_complete_guide.pdf', 'description': 'Real-time digital position and data reporting over amateur radio — iGate setup, digipeater configuration, mobile tracking, weather station integration, message passing, and tactical use during disasters. Works without internet infrastructure.'},
        {'title': 'Emergency Communications with NVIS Antennas', 'author': 'Jerry Sevick W2FMI', 'format': 'pdf', 'category': 'radio', 'folder': 'Radio & Communications',
         'url': 'https://archive.org/download/nvis-antenna-emergency-comms/nvis_emergency_communications.pdf', 'description': 'Near Vertical Incidence Skywave — the emergency communicator\'s most important antenna concept. Explains why low HF antennas (dipoles 10-15 ft high) provide reliable regional coverage 100-400 miles, while high antennas skip over nearby stations. Essential for ARES/RACES net control.'},
        {'title': 'DMR Digital Mobile Radio — Complete Hotspot and Programming Guide', 'author': 'F5UII / DMR-MARC Community', 'format': 'pdf', 'category': 'radio', 'folder': 'Radio & Communications',
         'url': 'https://archive.org/download/dmr-digital-radio-guide/dmr_hotspot_programming_guide.pdf', 'description': 'Digital Mobile Radio from the ground up — Pi-Star hotspot setup, Brandmeister and DMR-MARC network configuration, talk group management, radio programming with CHIRP and CPS, TDMA time slots, color codes, and roaming. Includes Pi-Star offline configuration.'},
        # Legal & Governance (additional)
        {'title': 'FEMA Voluntary Agency Coordination Field Guide', 'author': 'FEMA / National VOAD', 'format': 'pdf', 'category': 'survival', 'folder': 'Legal & Governance',
         'url': 'https://www.nvoad.org/wp-content/uploads/2014/04/long_term_recovery_guide.pdf', 'description': 'Coordinating volunteer organizations during disaster recovery — National VOAD long-term recovery framework, case management, unmet needs assessment, donations management, integration with government EOC. How to work effectively with Red Cross, Salvation Army, and faith-based organizations.'},
        {'title': 'Individual and Family Preparedness Legal Guide — Insurance, Wills, and Documents', 'author': 'FEMA / Ready.gov', 'format': 'pdf', 'category': 'survival', 'folder': 'Legal & Governance',
         'url': 'https://www.ready.gov/sites/default/files/2020-03/ready_family-emergency-plan_2020.pdf', 'description': 'Legal preparedness — which documents to protect (birth certificates, deeds, insurance), power of attorney for emergencies, accessing financial accounts when banks close, insurance claim documentation, and establishing out-of-area contacts for family reunification.'},
        # Aquaponics & Hydroponics
        {'title': 'Aquaponics — Integration of Hydroponics with Aquaculture', 'author': 'FAO', 'format': 'pdf', 'category': 'farming', 'folder': 'Homesteading',
         'url': 'https://www.fao.org/3/i4021e/i4021e.pdf', 'description': 'Combined fish and plant production system — system design, fish species selection (tilapia, catfish, carp), nutrient cycling, pH management, media beds vs. NFT vs. DWC, troubleshooting. High-yield food production in small footprints with minimal water.'},
        {'title': 'Small-Scale Aquaponic Food Production — Integrated Fish and Plant Farming', 'author': 'FAO', 'format': 'pdf', 'category': 'farming', 'folder': 'Homesteading',
         'url': 'https://www.fao.org/3/i4021e/i4021e00.htm', 'description': 'Practical aquaponics manual — system sizing for family food production, species pairing, seasonal management, pest control in a closed system, water quality testing, emergency protocols for fish illness. Build and maintain a productive year-round food source.'},
        # Blacksmithing & Metalworking
        {'title': 'The Backyard Blacksmith — Traditional Techniques for the Modern Smith', 'author': 'Lorelei Sims', 'format': 'pdf', 'category': 'repair', 'folder': 'Construction',
         'url': 'https://archive.org/download/backyard-blacksmith-sims/backyard_blacksmith.pdf', 'description': 'Forge setup and coal/propane selection, anvil and hammer techniques, basic forging operations (drawing, upsetting, bending, punching), tool making (tongs, chisels, punches), blade and knife forging, forge welding. Essential skills for repairing and fabricating metal tools.'},
        {'title': 'FM 3-34.343 Military Nonstandard Fixed Bridging — Welding and Metal Fabrication', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'repair', 'folder': 'Army Field Manuals',
         'url': 'https://armypubs.army.mil/epubs/DR_pubs/DR_a/pdf/web/fm3_34x343.pdf', 'description': 'Military field welding — SMAW (stick), MIG setup, cutting torches, metal identification, joint design, welding defects and inspection, underwater cutting, field expedient equipment. Practical metal joining without an ideal shop environment.'},
        # Additional Army Field Manuals
        {'title': 'FM 4-25.11 First Aid (Soldiers Manual of Common Tasks)', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'medical', 'folder': 'Army Field Manuals',
         'url': 'https://armypubs.army.mil/epubs/DR_pubs/DR_a/pdf/web/fm4_25x11.pdf', 'description': 'Comprehensive soldier first aid — controlling hemorrhage with pressure, tourniquet, and packing; airway management; treating burns, fractures, shock, heat and cold injuries; buddy aid and self-aid; litter construction. Updated TCCC-aligned procedures.'},
        {'title': 'FM 7-22.7 The NCO Guide — Leadership, Training, and Discipline', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'survival', 'folder': 'Army Field Manuals',
         'url': 'https://armypubs.army.mil/epubs/DR_pubs/DR_a/pdf/web/fm7_22x7.pdf', 'description': 'Small-unit leadership principles — conducting training, counseling, establishing standards, enforcing discipline, managing stress, after-action review process. Directly applicable to organizing and leading a survival group under stress.'},
        {'title': 'TC 21-3 Soldier\'s Guide for Field Expedient Methods', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'survival', 'folder': 'Army Field Manuals',
         'url': 'https://archive.org/download/tc-21-3-soldiers-guide/tc_21_3_field_expedient.pdf', 'description': 'Field-expedient construction and improvisation — rope bridges, water crossing aids, improvised shelters, material recovery and re-use, tools from natural materials, expedient stoves and heating. How to do more with less in field conditions.'},
        # Sanitation & Waste Management
        {'title': 'Sanitation Manual for Isolated Regions — Latrines, Composting, and Grey Water', 'author': 'WHO / UNICEF', 'format': 'pdf', 'category': 'survival', 'folder': 'Water & Sanitation',
         'url': 'https://www.who.int/water_sanitation_health/hygiene/emergencies/emergencychap3.pdf', 'description': 'Emergency sanitation without utilities — simple pit latrines (depth, siting, cover), ventilated improved pit (VIP) design, pour-flush toilets, handwashing station construction, grey water disposal, solid waste management, and preventing cholera and diarrheal disease outbreaks.'},
        # Foraging & Wild Plants
        {'title': 'A Field Guide to Edible Wild Plants: Eastern and Central North America', 'author': 'Lee Allen Peterson', 'format': 'pdf', 'category': 'survival', 'folder': 'Survival Guides',
         'url': 'https://archive.org/download/field-guide-edible-wild-plants-peterson/peterson_edible_wild_plants.pdf', 'description': 'Comprehensive edible plant identification — 370 species with descriptions, range maps, and preparation notes; poisonous look-alike warnings for each; seasonal availability; roots, berries, leaves, and fungi. Essential for emergency foraging in eastern North America.'},
        {'title': 'Identifying and Harvesting Edible and Medicinal Plants in Wild (and Not So Wild) Places', 'author': 'Steve Brill', 'format': 'pdf', 'category': 'survival', 'folder': 'Survival Guides',
         'url': 'https://archive.org/download/identifying-harvesting-edible-medicinal-brill/brill_edible_medicinal.pdf', 'description': 'Foraging field guide with strong medicinal focus — over 500 wild species by habitat and season; detailed identification features; cooking and preparation methods; medicinal uses backed by ethnobotany; legal considerations for collecting. Covers urban, suburban, and wilderness environments.'},
        # Community Resilience
        {'title': 'Building Community Resilience — A Neighborhood Preparedness Toolkit', 'author': 'FEMA / Citizen Corps', 'format': 'pdf', 'category': 'survival', 'folder': 'FEMA Guides',
         'url': 'https://www.citizencorps.gov/downloads/pdf/ready/neighbor_toolkit.pdf', 'description': 'Organizing your neighborhood for disaster — block captain roles, neighborhood needs assessments, skill and resource inventories, communication trees, mutual aid agreements, working with first responders. Step-by-step guide to building a prepared community from scratch.'},
        # Veterinary & Animal Medicine
        {'title': 'Where There Is No Animal Doctor', 'author': 'Peter Quesenberry / Christian Veterinary Mission', 'format': 'pdf', 'category': 'farming', 'folder': 'Medical References',
         'url': 'https://archive.org/download/where-no-animal-doctor/where_there_is_no_animal_doctor.pdf', 'description': 'Tropical and rural livestock health without a vet — common diseases by species (cattle, goats, sheep, chickens, pigs), vaccinations, internal parasites, wound care, birthing complications, hoof problems. Illustrated with clear diagnostic flowcharts for non-veterinarians.'},
        {'title': 'The Merck Veterinary Manual — Home Edition', 'author': 'Merck & Co.', 'format': 'pdf', 'category': 'farming', 'folder': 'Medical References',
         'url': 'https://archive.org/download/merck-vet-manual-home/merck_vet_manual_home_ed.pdf', 'description': 'Comprehensive veterinary reference covering all common domesticated species — dogs, cats, horses, cattle, sheep, goats, poultry, swine, rabbits. Disease identification, treatment protocols, drug dosages, nutrition, zoonotic diseases (diseases transmissible to humans).'},
        # Mechanics & Repair
        {'title': 'Audel Millwrights and Mechanics Guide', 'author': 'Thomas Davis', 'format': 'pdf', 'category': 'repair', 'folder': 'Construction',
         'url': 'https://archive.org/download/audel-millwrights-mechanics-guide/audel_millwrights_mechanics.pdf', 'description': 'Complete mechanical reference — bearings, gears, pumps, motors, rigging, alignment, belts and chains, hydraulics, pneumatics, welding, pipe fitting, concrete work. The one book a community mechanic needs for maintaining equipment without parts suppliers.'},
        {'title': 'FM 5-412 Project Management for Field Construction', 'author': 'U.S. Army', 'format': 'pdf', 'category': 'repair', 'folder': 'Army Field Manuals',
         'url': 'https://armypubs.army.mil/epubs/DR_pubs/DR_a/pdf/web/fm5_412.pdf', 'description': 'Planning and executing construction projects with limited resources — site layout, earthwork calculations, concrete mixing and curing, masonry, basic electrical and plumbing, safety, material estimation, work scheduling. Applicable to building community infrastructure post-disaster.'},
        # Traditional Skills & Crafts
        {'title': 'Foxfire 7 — Plowing, Groundhog Day, Snake Lore, Hunting Tales, Moonshining', 'author': 'Eliot Wigginton (ed.)', 'format': 'pdf', 'category': 'survival', 'folder': 'Foxfire Series',
         'url': 'https://archive.org/download/foxfire-7/foxfire_7.pdf', 'description': 'Appalachian traditional knowledge — horse-drawn plowing techniques, moonshine distillation (for fuel and medicine), traditional weather forecasting, hunting with dogs, building pole barns. Living history that preserves skills largely lost to industrialization.'},
        {'title': 'Foxfire 8 — Pickles, Churning, Wood Carving, Pig Skinning', 'author': 'Eliot Wigginton (ed.)', 'format': 'pdf', 'category': 'cooking', 'folder': 'Foxfire Series',
         'url': 'https://archive.org/download/foxfire-8/foxfire_8.pdf', 'description': 'Food preservation and handcraft — traditional pickling without vinegar, butter churning and cheese making, wood carving tools and techniques, hog processing from slaughter to sausage. Essential old-time skills for food security and self-sufficiency.'},
        # Textiles & Fiber
        {'title': 'Handspinning: A Complete Guide to the Craft of Spinning', 'author': 'Eliza Leadbeater', 'format': 'pdf', 'category': 'repair', 'folder': 'Construction',
         'url': 'https://archive.org/download/handspinning-complete-guide/handspinning_leadbeater.pdf', 'description': 'Fiber processing without industrial equipment — preparing raw wool, cotton, and plant fibers; drop spindle and spinning wheel operation; plying; dyeing with natural materials. Make rope, cord, thread, and yarn from raw materials for clothing repair and net making.'},
        # Navigation — Advanced
        {'title': 'Dutton\'s Nautical Navigation (Abridged)', 'author': 'Maloney / Cutler', 'format': 'pdf', 'category': 'survival', 'folder': 'Maps & Navigation',
         'url': 'https://archive.org/download/duttons-navigation-abridged/duttons_navigation.pdf', 'description': 'Celestial navigation — determining position from sun, moon, stars, and planets using sextant; dead reckoning; current corrections; piloting techniques; chart work. Complete position-finding method that works with zero electronics.'},
    ]

    @app.route('/api/books')
    def api_books_list():
        db = get_db()
        rows = db.execute('SELECT * FROM books ORDER BY folder, title').fetchall()
        db.close()
        bdir = get_books_dir()
        return jsonify([{**dict(r), 'exists': os.path.isfile(os.path.join(bdir, r['filename']))} for r in rows])

    @app.route('/api/books/upload', methods=['POST'])
    def api_books_upload():
        if 'file' not in request.files:
            return jsonify({'error': 'No file'}), 400
        file = request.files['file']
        filename = secure_filename(file.filename)
        if not filename:
            return jsonify({'error': 'Invalid filename'}), 400
        filepath = os.path.join(get_books_dir(), filename)
        file.save(filepath)
        filesize = os.path.getsize(filepath) if os.path.isfile(filepath) else 0
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'pdf'
        fmt = ext if ext in ('pdf', 'epub', 'mobi', 'txt') else 'pdf'
        title = request.form.get('title', filename.rsplit('.', 1)[0])
        author = request.form.get('author', '')
        category = request.form.get('category', 'general')
        folder = request.form.get('folder', '')
        db = get_db()
        cur = db.execute('INSERT INTO books (title, author, filename, format, category, folder, filesize) VALUES (?, ?, ?, ?, ?, ?, ?)',
                         (title, author, filename, fmt, category, folder, filesize))
        db.commit()
        db.close()
        log_activity('book_upload', 'media', title)
        return jsonify({'status': 'uploaded', 'id': cur.lastrowid}), 201

    @app.route('/api/books/<int:bid>', methods=['DELETE'])
    def api_books_delete(bid):
        db = get_db()
        row = db.execute('SELECT filename FROM books WHERE id = ?', (bid,)).fetchone()
        if row:
            filepath = os.path.join(get_books_dir(), row['filename'])
            if os.path.isfile(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
            db.execute('DELETE FROM books WHERE id = ?', (bid,))
            db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    @app.route('/api/books/<int:bid>', methods=['PATCH'])
    def api_books_update(bid):
        data = request.get_json() or {}
        ALLOWED_COLS = {'title', 'folder', 'category', 'author', 'last_position'}
        fields = []
        vals = []
        for col in ALLOWED_COLS:
            if col in data:
                fields.append(f'{col} = ?')
                vals.append(data[col])
        if not fields:
            return jsonify({'status': 'no changes'})
        vals.append(bid)
        db = get_db()
        db.execute(f'UPDATE books SET {", ".join(fields)} WHERE id = ?', vals)
        db.commit()
        db.close()
        return jsonify({'status': 'updated'})

    @app.route('/api/books/serve/<path:filename>')
    def api_books_serve(filename):
        bdir = get_books_dir()
        safe = os.path.normpath(os.path.join(bdir, filename))
        if not safe.startswith(os.path.normpath(bdir)) or not os.path.isfile(safe):
            return jsonify({'error': 'Not found'}), 404
        from flask import send_file
        return send_file(safe)

    @app.route('/api/books/stats')
    def api_books_stats():
        db = get_db()
        total = db.execute('SELECT COUNT(*) as c FROM books').fetchone()['c']
        total_size = db.execute('SELECT COALESCE(SUM(filesize),0) as s FROM books').fetchone()['s']
        by_folder = db.execute('SELECT folder, COUNT(*) as c FROM books GROUP BY folder ORDER BY folder').fetchall()
        db.close()
        return jsonify({'total': total, 'total_size': total_size, 'total_size_fmt': format_size(total_size),
                        'by_folder': [{'folder': r['folder'] or 'Unsorted', 'count': r['c']} for r in by_folder]})

    @app.route('/api/books/catalog')
    def api_books_catalog():
        return jsonify(REFERENCE_CATALOG)

    @app.route('/api/books/download-ref', methods=['POST'])
    def api_books_download_ref():
        """Download a reference book from the catalog."""
        nonlocal _ytdlp_dl_counter
        data = request.get_json() or {}
        url = data.get('url', '').strip()
        title = data.get('title', '')
        author = data.get('author', '')
        folder = data.get('folder', '')
        category = data.get('category', 'reference')
        fmt = data.get('format', 'pdf')
        if not url:
            return jsonify({'error': 'No URL'}), 400

        # Check if already downloaded
        db = get_db()
        existing = db.execute('SELECT id FROM books WHERE url = ?', (url,)).fetchone()
        db.close()
        if existing:
            return jsonify({'status': 'already_downloaded'})

        with _ytdlp_dl_lock:
            _ytdlp_dl_counter += 1
            dl_id = str(_ytdlp_dl_counter)

        _ytdlp_downloads[dl_id] = {'status': 'downloading', 'percent': 0, 'title': title, 'speed': '', 'error': ''}

        def do_dl():
            bdir = get_books_dir()
            try:
                filename = secure_filename(f'{title}.{fmt}') or f'book_{dl_id}.{fmt}'
                filepath = os.path.join(bdir, filename)
                import requests as req
                resp = req.get(url, stream=True, timeout=120, allow_redirects=True)
                resp.raise_for_status()
                total = int(resp.headers.get('content-length', 0))
                downloaded = 0
                with open(filepath, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            _ytdlp_downloads[dl_id]['percent'] = int(downloaded / total * 100)
                filesize = os.path.getsize(filepath)
                db = get_db()
                db.execute('INSERT INTO books (title, author, filename, format, category, folder, url, filesize) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                           (title, author, filename, fmt, category, folder, url, filesize))
                db.commit()
                db.close()
                _ytdlp_downloads[dl_id] = {'status': 'complete', 'percent': 100, 'title': title, 'speed': '', 'error': ''}
                log_activity('book_download', 'media', title)
            except Exception as e:
                _ytdlp_downloads[dl_id] = {'status': 'error', 'percent': 0, 'title': title, 'speed': '', 'error': str(e)}

        threading.Thread(target=do_dl, daemon=True).start()
        return jsonify({'status': 'started', 'id': dl_id})

    @app.route('/api/books/download-all-refs', methods=['POST'])
    def api_books_download_all_refs():
        """Download all reference catalog books sequentially."""
        nonlocal _ytdlp_dl_counter
        db = get_db()
        existing_urls = set(r['url'] for r in db.execute('SELECT url FROM books WHERE url != ""').fetchall())
        db.close()
        to_download = [b for b in REFERENCE_CATALOG if b['url'] not in existing_urls]
        if not to_download:
            return jsonify({'status': 'all_downloaded', 'count': 0})

        with _ytdlp_dl_lock:
            _ytdlp_dl_counter += 1
            queue_id = str(_ytdlp_dl_counter)

        _ytdlp_downloads[queue_id] = {'status': 'queued', 'percent': 0, 'title': f'Queue: 0/{len(to_download)}',
                                       'speed': '', 'error': '', 'queue_total': len(to_download), 'queue_pos': 0}

        def do_queue():
            bdir = get_books_dir()
            for i, item in enumerate(to_download):
                _ytdlp_downloads[queue_id].update({
                    'status': 'downloading', 'percent': 0, 'queue_pos': i + 1,
                    'title': f'[{i+1}/{len(to_download)}] {item["title"]}',
                })
                try:
                    filename = secure_filename(f'{item["title"]}.{item.get("format","pdf")}')
                    filepath = os.path.join(bdir, filename)
                    import requests as req
                    resp = req.get(item['url'], stream=True, timeout=120, allow_redirects=True)
                    resp.raise_for_status()
                    total = int(resp.headers.get('content-length', 0))
                    downloaded = 0
                    with open(filepath, 'wb') as f:
                        for chunk in resp.iter_content(chunk_size=65536):
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                _ytdlp_downloads[queue_id]['percent'] = int(downloaded / total * 100)
                    filesize = os.path.getsize(filepath)
                    db = get_db()
                    db.execute('INSERT INTO books (title, author, filename, format, category, folder, url, filesize) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                               (item['title'], item.get('author',''), filename, item.get('format','pdf'),
                                item.get('category','reference'), item.get('folder',''), item['url'], filesize))
                    db.commit()
                    db.close()
                except Exception as e:
                    log.error(f'Reference download failed for {item["title"]}: {e}')

            _ytdlp_downloads[queue_id] = {'status': 'complete', 'percent': 100, 'title': f'Done — {len(to_download)} books',
                                           'speed': '', 'error': '', 'queue_total': len(to_download), 'queue_pos': len(to_download)}

        threading.Thread(target=do_queue, daemon=True).start()
        return jsonify({'status': 'queued', 'id': queue_id, 'count': len(to_download)})

    @app.route('/api/media/stats')
    def api_media_stats():
        """Combined stats for all media types."""
        db = get_db()
        v_count = db.execute('SELECT COUNT(*) as c FROM videos').fetchone()['c']
        v_size = db.execute('SELECT COALESCE(SUM(filesize),0) as s FROM videos').fetchone()['s']
        a_count = db.execute('SELECT COUNT(*) as c FROM audio').fetchone()['c']
        a_size = db.execute('SELECT COALESCE(SUM(filesize),0) as s FROM audio').fetchone()['s']
        b_count = db.execute('SELECT COUNT(*) as c FROM books').fetchone()['c']
        b_size = db.execute('SELECT COALESCE(SUM(filesize),0) as s FROM books').fetchone()['s']
        db.close()
        total_size = v_size + a_size + b_size
        return jsonify({
            'videos': {'count': v_count, 'size': v_size, 'size_fmt': format_size(v_size)},
            'audio': {'count': a_count, 'size': a_size, 'size_fmt': format_size(a_size)},
            'books': {'count': b_count, 'size': b_size, 'size_fmt': format_size(b_size)},
            'total_size': total_size, 'total_size_fmt': format_size(total_size),
        })

    # ─── Media Enhancements (v5.0 Phase 6) ──────────────────────────

    @app.route('/api/media/progress/<media_type>/<int:media_id>', methods=['GET'])
    def api_media_progress_get(media_type, media_id):
        """Get playback progress for a media item."""
        if media_type not in ('video', 'audio', 'book'):
            return jsonify({'error': 'Invalid media type'}), 400
        db = get_db()
        try:
            row = db.execute('SELECT * FROM media_progress WHERE media_type = ? AND media_id = ?', (media_type, media_id)).fetchone()
            return jsonify(dict(row) if row else {'position_sec': 0, 'duration_sec': 0, 'completed': 0})
        finally:
            db.close()

    @app.route('/api/media/progress/<media_type>/<int:media_id>', methods=['PUT'])
    def api_media_progress_update(media_type, media_id):
        """Update playback progress for a media item."""
        if media_type not in ('video', 'audio', 'book'):
            return jsonify({'error': 'Invalid media type'}), 400
        d = request.json or {}
        db = get_db()
        try:
            db.execute(
                '''INSERT INTO media_progress (media_type, media_id, position_sec, duration_sec, completed, updated_at)
                   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(media_type, media_id) DO UPDATE SET
                   position_sec = excluded.position_sec, duration_sec = excluded.duration_sec,
                   completed = excluded.completed, updated_at = CURRENT_TIMESTAMP''',
                (media_type, media_id, d.get('position_sec', 0), d.get('duration_sec', 0), d.get('completed', 0))
            )
            db.commit()
            return jsonify({'status': 'ok'})
        finally:
            db.close()

    @app.route('/api/media/resume')
    def api_media_resume_list():
        """Get all in-progress media for 'Continue Watching/Listening' section."""
        db = get_db()
        try:
            rows = db.execute(
                '''SELECT mp.*,
                   CASE mp.media_type
                     WHEN 'video' THEN (SELECT title FROM videos WHERE id = mp.media_id)
                     WHEN 'audio' THEN (SELECT title FROM audio WHERE id = mp.media_id)
                     WHEN 'book' THEN (SELECT title FROM books WHERE id = mp.media_id)
                   END as title
                   FROM media_progress mp
                   WHERE mp.completed = 0 AND mp.position_sec > 10
                   ORDER BY mp.updated_at DESC LIMIT 20'''
            ).fetchall()
            return jsonify([dict(r) for r in rows])
        finally:
            db.close()

    @app.route('/api/playlists', methods=['GET'])
    def api_playlists():
        """List all playlists."""
        media_type = request.args.get('type', '')
        db = get_db()
        try:
            if media_type:
                rows = db.execute('SELECT * FROM playlists WHERE media_type = ? ORDER BY updated_at DESC', (media_type,)).fetchall()
            else:
                rows = db.execute('SELECT * FROM playlists ORDER BY updated_at DESC').fetchall()
            return jsonify([dict(r) for r in rows])
        finally:
            db.close()

    @app.route('/api/playlists', methods=['POST'])
    def api_playlist_create():
        """Create a new playlist."""
        d = request.json or {}
        name = d.get('name', 'New Playlist').strip()
        media_type = d.get('media_type', 'audio')
        db = get_db()
        try:
            db.execute('INSERT INTO playlists (name, media_type, items) VALUES (?, ?, ?)',
                       (name, media_type, json.dumps(d.get('items', []))))
            db.commit()
            pid = db.execute('SELECT last_insert_rowid()').fetchone()[0]
            return jsonify({'id': pid, 'status': 'ok'})
        finally:
            db.close()

    @app.route('/api/playlists/<int:pid>', methods=['PUT'])
    def api_playlist_update(pid):
        """Update a playlist."""
        d = request.json or {}
        db = get_db()
        try:
            updates = []
            params = []
            for field in ('name', 'items'):
                if field in d:
                    updates.append(f'{field} = ?')
                    params.append(json.dumps(d[field]) if field == 'items' else d[field])
            if updates:
                updates.append('updated_at = CURRENT_TIMESTAMP')
                params.append(pid)
                db.execute(f'UPDATE playlists SET {", ".join(updates)} WHERE id = ?', params)
                db.commit()
            return jsonify({'status': 'ok'})
        finally:
            db.close()

    @app.route('/api/playlists/<int:pid>', methods=['DELETE'])
    def api_playlist_delete(pid):
        """Delete a playlist."""
        db = get_db()
        try:
            db.execute('DELETE FROM playlists WHERE id = ?', (pid,))
            db.commit()
            return jsonify({'status': 'ok'})
        finally:
            db.close()

    # ─── Sneakernet Sync API ─────────────────────────────────────────

    @app.route('/api/sync/export', methods=['POST'])
    def api_sync_export():
        """Export selected data as a portable content pack ZIP."""
        data = request.get_json() or {}
        ALLOWED_SYNC_TABLES = {'inventory', 'contacts', 'checklists', 'notes', 'incidents', 'waypoints'}
        include = [t for t in data.get('include', list(ALLOWED_SYNC_TABLES)) if t in ALLOWED_SYNC_TABLES]
        import io
        import zipfile as zf
        buf = io.BytesIO()
        db = get_db()
        with zf.ZipFile(buf, 'w', zf.ZIP_DEFLATED) as z:
            manifest = {'version': VERSION, 'exported_at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'tables': []}
            for table in include:
                try:
                    rows = db.execute(f'SELECT * FROM {table}').fetchall()
                    table_data = [dict(r) for r in rows]
                    z.writestr(f'{table}.json', json.dumps(table_data, indent=2, default=str))
                    manifest['tables'].append({'name': table, 'count': len(table_data)})
                except Exception:
                    pass
            z.writestr('manifest.json', json.dumps(manifest, indent=2))
        db.close()
        buf.seek(0)
        fname = f'nomad-sync-{time.strftime("%Y%m%d-%H%M%S")}.zip'
        return Response(buf.read(), mimetype='application/zip',
                       headers={'Content-Disposition': f'attachment; filename="{fname}"'})

    @app.route('/api/sync/import', methods=['POST'])
    def api_sync_import():
        """Import a content pack ZIP (merge mode — adds data, doesn't overwrite)."""
        if 'file' not in request.files:
            return jsonify({'error': 'No file'}), 400
        import zipfile as zf
        import io
        file = request.files['file']
        db = None
        try:
            with zf.ZipFile(io.BytesIO(file.read())) as z:
                if 'manifest.json' not in z.namelist():
                    return jsonify({'error': 'Invalid sync file (no manifest)'}), 400
                manifest = json.loads(z.read('manifest.json'))
                db = get_db()
                imported = {}
                for table_info in manifest.get('tables', []):
                    tname = table_info['name']
                    if tname not in ('inventory', 'contacts', 'checklists', 'notes', 'incidents', 'waypoints'):
                        continue
                    fname = f'{tname}.json'
                    if fname not in z.namelist():
                        continue
                    rows = json.loads(z.read(fname))
                    # Get valid column names from the actual table schema
                    schema_cols = {row[1] for row in db.execute(f"PRAGMA table_info({tname})").fetchall()}
                    count = 0
                    for row in rows:
                        row.pop('id', None)
                        row.pop('created_at', None)
                        row.pop('updated_at', None)
                        # Only allow columns that exist in the table schema
                        safe_row = {k: v for k, v in row.items() if k in schema_cols}
                        if not safe_row:
                            continue
                        cols = list(safe_row.keys())
                        vals = list(safe_row.values())
                        placeholders = ','.join(['?'] * len(cols))
                        try:
                            db.execute(f'INSERT INTO {tname} ({",".join(cols)}) VALUES ({placeholders})', vals)
                            count += 1
                        except Exception:
                            pass
                    imported[tname] = count
                db.commit()
                return jsonify({'status': 'imported', 'tables': imported})
        except Exception as e:
            return jsonify({'error': str(e)}), 400
        finally:
            if db:
                try: db.close()
                except Exception: pass

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

    @app.route('/api/services/health-summary')
    def api_services_health_summary():
        """Detailed health info for all services."""
        services = []
        for sid, mod in SERVICE_MODULES.items():
            installed = mod.is_installed()
            running = mod.running() if installed else False
            install_dir = os.path.join(get_services_dir(), sid)
            disk = get_dir_size(install_dir) if installed else 0
            port_val = getattr(mod, f'{sid.upper()}_PORT', None)
            services.append({
                'id': sid, 'installed': installed, 'running': running,
                'disk_bytes': disk, 'disk_str': format_size(disk),
                'port': port_val,
                'port_responding': mod.running() if installed else False,
            })
        # Uptime
        from db import get_db as gdb
        db = gdb()
        recent_crashes = db.execute("SELECT service, COUNT(*) as c FROM activity_log WHERE event = 'service_crash_detected' AND created_at >= datetime('now', '-24 hours') GROUP BY service").fetchall()
        recent_restarts = db.execute("SELECT service, COUNT(*) as c FROM activity_log WHERE event = 'service_autorestarted' AND created_at >= datetime('now', '-24 hours') GROUP BY service").fetchall()
        db.close()
        crash_map = {r['service']: r['c'] for r in recent_crashes}
        restart_map = {r['service']: r['c'] for r in recent_restarts}
        for s in services:
            s['crashes_24h'] = crash_map.get(s['id'], 0)
            s['restarts_24h'] = restart_map.get(s['id'], 0)
        return jsonify(services)

    # ─── GPX Waypoint Export ─────────────────────────────────────────

    @app.route('/api/waypoints/export-gpx')
    def api_waypoints_gpx():
        db = get_db()
        rows = db.execute('SELECT * FROM waypoints ORDER BY created_at').fetchall()
        db.close()
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
        db = get_db()
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
        db.close()
        return jsonify({'status': 'imported', 'count': count})

    # ─── Enhanced Dashboard API ───────────────────────────────────────

    @app.route('/api/dashboard/critical')
    def api_dashboard_critical():
        """Return actual critical items for the command dashboard."""
        db = get_db()
        from datetime import datetime, timedelta
        today = datetime.now().strftime('%Y-%m-%d')
        soon = (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')

        low_items = db.execute('SELECT name, quantity, unit, category FROM inventory WHERE quantity <= min_quantity AND min_quantity > 0 LIMIT 5').fetchall()
        expiring_items = db.execute("SELECT name, expiration, category FROM inventory WHERE expiration != '' AND expiration <= ? AND expiration >= ? ORDER BY expiration LIMIT 5", (soon, today)).fetchall()
        critical_burn = db.execute("SELECT name, quantity, daily_usage, category FROM inventory WHERE daily_usage > 0 AND (quantity / daily_usage) < 7 ORDER BY (quantity / daily_usage) LIMIT 5").fetchall()

        db.close()
        return jsonify({
            'low_items': [dict(r) for r in low_items],
            'expiring_items': [dict(r) for r in expiring_items],
            'critical_burn': [{'name': r['name'], 'days_left': round(r['quantity']/r['daily_usage'], 1) if r['daily_usage'] else 0, 'category': r['category']} for r in critical_burn],
        })

    # ─── Proactive Alert System ──────────────────────────────────────

    _alert_check_running = False

    def _run_alert_checks():
        """Background alert engine — checks inventory, weather, incidents every 5 minutes."""
        nonlocal _alert_check_running
        if _alert_check_running:
            return
        _alert_check_running = True
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
                    'SELECT name, quantity, daily_usage, category FROM inventory WHERE daily_usage > 0 AND (quantity / daily_usage) < 7 ORDER BY (quantity / daily_usage)'
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
                    'SELECT name, quantity, unit, min_quantity FROM inventory WHERE quantity <= min_quantity AND min_quantity > 0'
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
                    db = get_db()
                    for alert in alerts:
                        existing = db.execute(
                            "SELECT id, dismissed FROM alerts WHERE alert_type = ? AND title = ? AND created_at >= ? ORDER BY created_at DESC LIMIT 1",
                            (alert['type'], alert['title'], (now - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S'))
                        ).fetchone()
                        if not existing:
                            db.execute(
                                'INSERT INTO alerts (alert_type, severity, title, message) VALUES (?, ?, ?, ?)',
                                (alert['type'], alert['severity'], alert['title'], alert['message'])
                            )
                    db.commit()
                    db.close()

                # Prune old dismissed alerts (>7 days)
                db = get_db()
                db.execute("DELETE FROM alerts WHERE dismissed = 1 AND created_at < ?",
                           ((now - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S'),))
                db.commit()
                db.close()

            except Exception as e:
                log.error(f'Alert engine error: {e}')
            _t.sleep(300)  # Check every 5 minutes

    threading.Thread(target=_run_alert_checks, daemon=True).start()

    @app.route('/api/alerts')
    def api_alerts():
        """Get active (non-dismissed) alerts."""
        db = get_db()
        rows = db.execute('SELECT * FROM alerts WHERE dismissed = 0 ORDER BY severity DESC, created_at DESC LIMIT 50').fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/alerts/<int:alert_id>/dismiss', methods=['POST'])
    def api_alert_dismiss(alert_id):
        db = get_db()
        db.execute('UPDATE alerts SET dismissed = 1 WHERE id = ?', (alert_id,))
        db.commit()
        db.close()
        return jsonify({'status': 'dismissed'})

    @app.route('/api/alerts/dismiss-all', methods=['POST'])
    def api_alerts_dismiss_all():
        db = get_db()
        db.execute('UPDATE alerts SET dismissed = 1 WHERE dismissed = 0')
        db.commit()
        db.close()
        return jsonify({'status': 'dismissed'})

    @app.route('/api/alerts/generate-summary', methods=['POST'])
    def api_alerts_generate_summary():
        """Use AI to generate a natural language situation summary from active alerts."""
        db = get_db()
        alerts = db.execute('SELECT * FROM alerts WHERE dismissed = 0 ORDER BY severity DESC').fetchall()
        db.close()
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

    # ─── Deep Document Understanding ───────────────────────────────────

    DOC_CATEGORIES = ['medical', 'property', 'vehicle', 'financial', 'legal', 'reference', 'personal', 'other']

    def _analyze_document(doc_id, text, filename):
        """Background: classify, summarize, extract entities from a document using AI."""
        db = get_db()
        try:
            if not ollama.running() or not ollama.list_models():
                db.execute("UPDATE documents SET doc_category = 'other', summary = 'AI analysis unavailable — start Ollama for document intelligence.' WHERE id = ?", (doc_id,))
                db.commit()
                db.close()
                return

            model = ollama.list_models()[0]['name']
            import requests as req
            text_sample = text[:3000]  # Use first 3000 chars for analysis

            # Step 1: Classify
            classify_prompt = f"""Classify this document into ONE category: medical, property, vehicle, financial, legal, reference, personal, other.

Document filename: {filename}
Document text (first 3000 chars):
{text_sample}

Respond with ONLY the category word, nothing else."""

            r = req.post(f'http://localhost:{ollama.OLLAMA_PORT}/api/generate',
                        json={'model': model, 'prompt': classify_prompt, 'stream': False}, timeout=20)
            cat_words = r.json().get('response', '').strip().lower().split() if r.ok else []
            category = cat_words[0] if cat_words else 'other'
            if category not in DOC_CATEGORIES:
                category = 'other'

            # Step 2: Summarize
            summary_prompt = f"""Write a 2-3 sentence summary of this document. Be concise and factual.

Document: {filename}
Text: {text_sample}

Summary:"""

            r = req.post(f'http://localhost:{ollama.OLLAMA_PORT}/api/generate',
                        json={'model': model, 'prompt': summary_prompt, 'stream': False}, timeout=20)
            summary = r.json().get('response', '').strip()[:500] if r.ok else ''

            # Step 3: Extract entities
            entity_prompt = f"""Extract key entities from this document as a JSON array. Include: names (people), dates, medications, addresses, phone numbers, vehicle info (make/model/year/VIN), dollar amounts, and GPS coordinates if present.

Document: {filename}
Text: {text_sample}

Respond with ONLY a JSON array of objects, each with "type" and "value" keys. Example: [{{"type":"person","value":"John Smith"}},{{"type":"medication","value":"Lisinopril 10mg"}}]
If no entities found, respond with: []"""

            r = req.post(f'http://localhost:{ollama.OLLAMA_PORT}/api/generate',
                        json={'model': model, 'prompt': entity_prompt, 'stream': False, 'format': 'json'}, timeout=25)
            entities_raw = r.json().get('response', '[]') if r.ok else '[]'
            try:
                entities = json.loads(entities_raw)
                if not isinstance(entities, list):
                    entities = []
            except Exception:
                entities = []

            # Step 4: Cross-reference entities against existing contacts/inventory
            linked = []
            if entities:
                contacts = [dict(r) for r in db.execute('SELECT id, name FROM contacts').fetchall()]
                contact_names = {c['name'].lower(): c['id'] for c in contacts}
                for ent in entities:
                    if ent.get('type') == 'person' and ent.get('value', '').lower() in contact_names:
                        linked.append({'type': 'contact', 'id': contact_names[ent['value'].lower()], 'name': ent['value']})

            db.execute("UPDATE documents SET doc_category = ?, summary = ?, entities = ?, linked_records = ? WHERE id = ?",
                       (category, summary, json.dumps(entities), json.dumps(linked), doc_id))
            db.commit()
            log.info(f'Document {doc_id} analyzed: {category}, {len(entities)} entities, {len(linked)} links')
        except Exception as e:
            log.error(f'Document analysis failed for {doc_id}: {e}')
            db.execute("UPDATE documents SET doc_category = 'other', summary = ? WHERE id = ?",
                       (f'Analysis failed: {e}', doc_id))
            db.commit()
        finally:
            db.close()

    @app.route('/api/kb/documents/<int:doc_id>/analyze', methods=['POST'])
    def api_kb_analyze(doc_id):
        """Trigger AI analysis (classify, summarize, extract) for a document."""
        db = get_db()
        doc = db.execute('SELECT * FROM documents WHERE id = ?', (doc_id,)).fetchone()
        db.close()
        if not doc:
            return jsonify({'error': 'Not found'}), 404

        # Read the file text
        filepath = os.path.join(get_kb_upload_dir(), doc['filename'])
        if not os.path.isfile(filepath):
            return jsonify({'error': 'File not found on disk'}), 404

        text = extract_text_from_file(filepath, doc['content_type'])
        threading.Thread(target=_analyze_document, args=(doc_id, text, doc['filename']), daemon=True).start()
        return jsonify({'status': 'analyzing'})

    @app.route('/api/kb/documents/<int:doc_id>/details')
    def api_kb_doc_details(doc_id):
        """Get full document details including analysis results."""
        db = get_db()
        doc = db.execute('SELECT * FROM documents WHERE id = ?', (doc_id,)).fetchone()
        db.close()
        if not doc:
            return jsonify({'error': 'Not found'}), 404
        d = dict(doc)
        try:
            d['entities'] = json.loads(d.get('entities', '[]') or '[]')
        except Exception:
            d['entities'] = []
        try:
            d['linked_records'] = json.loads(d.get('linked_records', '[]') or '[]')
        except Exception:
            d['linked_records'] = []
        return jsonify(d)

    @app.route('/api/kb/analyze-all', methods=['POST'])
    def api_kb_analyze_all():
        """Analyze all unanalyzed documents."""
        db = get_db()
        docs = db.execute("SELECT * FROM documents WHERE (doc_category IS NULL OR doc_category = '') AND status = 'ready'").fetchall()
        db.close()
        count = 0
        for doc in docs:
            filepath = os.path.join(get_kb_upload_dir(), doc['filename'])
            if os.path.isfile(filepath):
                text = extract_text_from_file(filepath, doc['content_type'])
                threading.Thread(target=_analyze_document, args=(doc['id'], text, doc['filename']), daemon=True).start()
                count += 1
                time.sleep(0.5)  # Stagger to avoid overloading Ollama
        return jsonify({'status': 'analyzing', 'count': count})

    # ─── Security Module ──────────────────────────────────────────────

    @app.route('/api/security/cameras')
    def api_cameras_list():
        db = get_db()
        rows = db.execute('SELECT * FROM cameras ORDER BY name').fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/security/cameras', methods=['POST'])
    def api_cameras_create():
        data = request.get_json() or {}
        if not data.get('name') or not data.get('url'):
            return jsonify({'error': 'Name and URL required'}), 400
        db = get_db()
        db.execute('INSERT INTO cameras (name, url, stream_type, location, zone, notes) VALUES (?,?,?,?,?,?)',
                   (data['name'], data['url'], data.get('stream_type', 'mjpeg'),
                    data.get('location', ''), data.get('zone', ''), data.get('notes', '')))
        db.commit()
        db.close()
        return jsonify({'status': 'created'}), 201

    @app.route('/api/security/cameras/<int:cid>', methods=['DELETE'])
    def api_cameras_delete(cid):
        db = get_db()
        db.execute('DELETE FROM cameras WHERE id = ?', (cid,))
        db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    @app.route('/api/security/access-log')
    def api_access_log():
        db = get_db()
        rows = db.execute('SELECT * FROM access_log ORDER BY created_at DESC LIMIT 200').fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/security/access-log', methods=['POST'])
    def api_access_log_create():
        data = request.get_json() or {}
        db = get_db()
        db.execute('INSERT INTO access_log (person, direction, location, method, notes) VALUES (?,?,?,?,?)',
                   (data.get('person', ''), data.get('direction', 'entry'),
                    data.get('location', ''), data.get('method', 'visual'), data.get('notes', '')))
        db.commit()
        db.close()
        log_activity('access_logged', detail=f'{data.get("direction","entry")}: {data.get("person","")} at {data.get("location","")}')
        return jsonify({'status': 'logged'}), 201

    @app.route('/api/security/access-log/clear', methods=['POST'])
    def api_access_log_clear():
        db = get_db()
        db.execute('DELETE FROM access_log')
        db.commit()
        db.close()
        return jsonify({'status': 'cleared'})

    @app.route('/api/security/dashboard')
    def api_security_dashboard():
        """Security overview: camera status, recent access, incident summary."""
        db = get_db()
        from datetime import datetime, timedelta
        cameras = db.execute('SELECT COUNT(*) as c FROM cameras WHERE status = ?', ('active',)).fetchone()['c']
        access_24h = db.execute("SELECT COUNT(*) as c FROM access_log WHERE created_at >= ?",
                                ((datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S'),)).fetchone()['c']
        sec_incidents = db.execute("SELECT COUNT(*) as c FROM incidents WHERE category = 'security' AND created_at >= ?",
                                  ((datetime.now() - timedelta(hours=48)).strftime('%Y-%m-%d %H:%M:%S'),)).fetchone()['c']
        # Get situation board security level
        sit_raw = db.execute("SELECT value FROM settings WHERE key = 'sit_board'").fetchone()
        security_level = 'green'
        if sit_raw and sit_raw['value']:
            try:
                sit = json.loads(sit_raw['value'] or '{}')
                security_level = sit.get('security', 'green')
            except Exception:
                pass
        db.close()
        return jsonify({
            'cameras_active': cameras, 'access_24h': access_24h,
            'security_incidents_48h': sec_incidents, 'security_level': security_level,
        })

    # ─── Power Management ─────────────────────────────────────────────

    @app.route('/api/power/devices')
    def api_power_devices():
        db = get_db()
        rows = db.execute('SELECT * FROM power_devices ORDER BY device_type, name').fetchall()
        db.close()
        return jsonify([{**dict(r), 'specs': json.loads(r['specs'] or '{}')} for r in rows])

    @app.route('/api/power/devices', methods=['POST'])
    def api_power_devices_create():
        data = request.get_json() or {}
        if not data.get('name') or not data.get('device_type'):
            return jsonify({'error': 'Name and type required'}), 400
        db = get_db()
        db.execute('INSERT INTO power_devices (device_type, name, specs, notes) VALUES (?,?,?,?)',
                   (data['device_type'], data['name'], json.dumps(data.get('specs', {})), data.get('notes', '')))
        db.commit()
        db.close()
        return jsonify({'status': 'created'}), 201

    @app.route('/api/power/devices/<int:did>', methods=['DELETE'])
    def api_power_devices_delete(did):
        db = get_db()
        db.execute('DELETE FROM power_devices WHERE id = ?', (did,))
        db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    @app.route('/api/power/log')
    def api_power_log():
        db = get_db()
        rows = db.execute('SELECT * FROM power_log ORDER BY created_at DESC LIMIT 100').fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/power/log', methods=['POST'])
    def api_power_log_create():
        data = request.get_json() or {}
        db = get_db()
        db.execute('INSERT INTO power_log (battery_voltage, battery_soc, solar_watts, solar_wh_today, load_watts, load_wh_today, generator_running, notes) VALUES (?,?,?,?,?,?,?,?)',
                   (data.get('battery_voltage'), data.get('battery_soc'), data.get('solar_watts'),
                    data.get('solar_wh_today'), data.get('load_watts'), data.get('load_wh_today'),
                    1 if data.get('generator_running') else 0, data.get('notes', '')))
        db.commit()
        db.close()
        return jsonify({'status': 'logged'}), 201

    @app.route('/api/power/dashboard')
    def api_power_dashboard():
        """Power budget summary with autonomy projection."""
        db = get_db()
        devices = db.execute('SELECT * FROM power_devices WHERE status = ?', ('active',)).fetchall()
        logs = [dict(r) for r in db.execute('SELECT * FROM power_log ORDER BY created_at DESC LIMIT 24').fetchall()]
        db.close()

        # Calculate totals from device registry
        total_solar_w = 0
        total_battery_wh = 0
        for d in devices:
            specs = json.loads(d['specs'] or '{}')
            if d['device_type'] == 'solar_panel':
                total_solar_w += specs.get('watts', 0) * specs.get('count', 1)
            elif d['device_type'] == 'battery':
                total_battery_wh += specs.get('capacity_wh', 0) * specs.get('count', 1)

        # Average consumption from recent logs
        avg_load_w = 0
        avg_solar_w = 0
        latest_voltage = None
        latest_soc = None
        if logs:
            load_readings = [l['load_watts'] for l in logs if l['load_watts']]
            solar_readings = [l['solar_watts'] for l in logs if l['solar_watts']]
            avg_load_w = sum(load_readings) / len(load_readings) if load_readings else 0
            avg_solar_w = sum(solar_readings) / len(solar_readings) if solar_readings else 0
            latest_voltage = logs[0].get('battery_voltage')
            latest_soc = logs[0].get('battery_soc')

        # Autonomy calculation
        daily_consumption_wh = avg_load_w * 24 if avg_load_w else 0
        daily_solar_wh = avg_solar_w * 5 if avg_solar_w else 0  # ~5 sun hours avg
        usable_battery_wh = total_battery_wh * 0.8  # 80% depth of discharge
        net_daily = daily_solar_wh - daily_consumption_wh

        if daily_consumption_wh > 0 and net_daily < 0:
            autonomy_days = usable_battery_wh / abs(net_daily) if abs(net_daily) > 0 else 999
        elif daily_consumption_wh > 0:
            autonomy_days = 999  # solar covers load
        else:
            autonomy_days = 999

        return jsonify({
            'total_solar_w': total_solar_w, 'total_battery_wh': total_battery_wh,
            'avg_load_w': round(avg_load_w, 1), 'avg_solar_w': round(avg_solar_w, 1),
            'daily_consumption_wh': round(daily_consumption_wh), 'daily_solar_wh': round(daily_solar_wh),
            'net_daily_wh': round(net_daily), 'autonomy_days': round(min(autonomy_days, 999), 1),
            'latest_voltage': latest_voltage, 'latest_soc': latest_soc,
            'device_count': len(devices), 'log_count': len(logs),
        })

    # ─── Multi-Node Federation ─────────────────────────────────────────

    import uuid as _uuid

    def _get_node_id():
        db = get_db()
        row = db.execute("SELECT value FROM settings WHERE key = 'node_id'").fetchone()
        if row and row['value']:
            db.close()
            return row['value']
        node_id = str(_uuid.uuid4())[:8]
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('node_id', ?)", (node_id,))
        db.commit()
        db.close()
        return node_id

    def _get_node_name():
        db = get_db()
        row = db.execute("SELECT value FROM settings WHERE key = 'node_name'").fetchone()
        db.close()
        return (row['value'] if row and row['value'] else platform.node()) or 'NOMAD Node'

    @app.route('/api/node/identity')
    def api_node_identity():
        return jsonify({'node_id': _get_node_id(), 'node_name': _get_node_name(), 'version': VERSION})

    @app.route('/api/node/identity', methods=['PUT'])
    def api_node_identity_update():
        data = request.get_json() or {}
        name = data.get('name', '').strip()
        if name:
            db = get_db()
            db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('node_name', ?)", (name,))
            db.commit()
            db.close()
        return jsonify({'status': 'updated', 'node_name': name})

    # UDP Discovery
    _discovered_peers = {}

    @app.route('/api/node/discover', methods=['POST'])
    def api_node_discover():
        """Broadcast UDP to find other N.O.M.A.D. nodes on LAN."""
        import socket
        _discovered_peers.clear()
        node_id = _get_node_id()
        node_name = _get_node_name()
        msg = json.dumps({'type': 'nomad_discover', 'node_id': node_id, 'node_name': node_name, 'port': 8080}).encode()

        # Broadcast on UDP port 5353 (common mDNS-adjacent)
        DISCOVERY_PORT = 18080
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(3)
            sock.sendto(msg, ('<broadcast>', DISCOVERY_PORT))

            # Listen for responses for 3 seconds
            end_time = time.time() + 3
            while time.time() < end_time:
                try:
                    data, addr = sock.recvfrom(1024)
                    peer = json.loads(data.decode())
                    if peer.get('type') == 'nomad_announce' and peer.get('node_id') != node_id:
                        _discovered_peers[peer['node_id']] = {
                            'node_id': peer['node_id'], 'node_name': peer.get('node_name', 'Unknown'),
                            'ip': addr[0], 'port': peer.get('port', 8080), 'version': peer.get('version', '?'),
                        }
                except socket.timeout:
                    break
                except Exception:
                    continue
            sock.close()
        except Exception as e:
            log.warning(f'Discovery broadcast failed: {e}')

        return jsonify({'peers': list(_discovered_peers.values()), 'self': {'node_id': node_id, 'node_name': node_name}})

    @app.route('/api/node/peers')
    def api_node_peers():
        return jsonify(list(_discovered_peers.values()))

    @app.route('/api/node/announce', methods=['POST'])
    def api_node_announce():
        """Respond to a discovery broadcast (called by peers via HTTP as fallback)."""
        return jsonify({
            'type': 'nomad_announce', 'node_id': _get_node_id(),
            'node_name': _get_node_name(), 'port': 8080, 'version': VERSION,
        })

    @app.route('/api/node/sync-push', methods=['POST'])
    def api_node_sync_push():
        """Push data TO a peer node."""
        data = request.get_json() or {}
        peer_ip = data.get('ip')
        peer_port = data.get('port', 8080)
        if not peer_ip:
            return jsonify({'error': 'No peer IP'}), 400

        import requests as req
        SYNC_TABLES = ['inventory', 'contacts', 'checklists', 'notes', 'incidents', 'waypoints']
        node_id = _get_node_id()
        node_name = _get_node_name()

        # Collect our data
        db = get_db()
        payload = {'source_node_id': node_id, 'source_node_name': node_name, 'tables': {}}
        total_items = 0
        for table in SYNC_TABLES:
            try:
                rows = db.execute(f'SELECT * FROM {table}').fetchall()
                table_data = [dict(r) for r in rows]
                # Strip local IDs — peer will assign new ones
                for row in table_data:
                    row.pop('id', None)
                    row['_source_node'] = node_id
                payload['tables'][table] = table_data
                total_items += len(table_data)
            except Exception:
                pass
        db.close()

        # Push to peer
        try:
            r = req.post(f'http://{peer_ip}:{peer_port}/api/node/sync-receive',
                        json=payload, timeout=30)
            result = r.json()
            # Log sync
            db = get_db()
            db.execute('INSERT INTO sync_log (direction, peer_node_id, peer_name, peer_ip, tables_synced, items_count, status) VALUES (?,?,?,?,?,?,?)',
                       ('push', result.get('node_id', ''), result.get('node_name', ''), peer_ip,
                        json.dumps({t: len(d) for t, d in payload['tables'].items()}), total_items, 'success'))
            db.commit()
            db.close()
            return jsonify({'status': 'pushed', 'items': total_items, 'peer': result.get('node_name', peer_ip)})
        except Exception as e:
            return jsonify({'error': f'Push failed: {e}'}), 500

    @app.route('/api/node/sync-receive', methods=['POST'])
    def api_node_sync_receive():
        """Receive data FROM a peer node (merge mode)."""
        data = request.get_json() or {}
        source_node = data.get('source_node_id', '')
        source_name = data.get('source_node_name', '')
        tables = data.get('tables', {})

        ALLOWED = {'inventory', 'contacts', 'checklists', 'notes', 'incidents', 'waypoints'}
        db = get_db()
        imported = {}
        total = 0
        for tname, rows in tables.items():
            if tname not in ALLOWED:
                continue
            # Get valid column names from the actual table schema
            schema_cols = {r[1] for r in db.execute(f"PRAGMA table_info({tname})").fetchall()}
            count = 0
            for row in rows:
                row.pop('id', None)
                row.pop('created_at', None)
                row.pop('updated_at', None)
                row.pop('_source_node', None)
                safe_row = {k: v for k, v in row.items() if k in schema_cols}
                if not safe_row:
                    continue
                cols = list(safe_row.keys())
                vals = list(safe_row.values())
                placeholders = ','.join(['?'] * len(cols))
                try:
                    db.execute(f'INSERT INTO {tname} ({",".join(cols)}) VALUES ({placeholders})', vals)
                    count += 1
                except Exception:
                    pass
            imported[tname] = count
            total += count
        db.commit()

        # Log receipt
        db.execute('INSERT INTO sync_log (direction, peer_node_id, peer_name, peer_ip, tables_synced, items_count, status) VALUES (?,?,?,?,?,?,?)',
                   ('receive', source_node, source_name, request.remote_addr or '',
                    json.dumps(imported), total, 'success'))
        db.commit()
        db.close()

        log_activity('sync_received', detail=f'From {source_name} ({source_node}): {total} items')
        return jsonify({'status': 'received', 'imported': imported, 'total': total,
                       'node_id': _get_node_id(), 'node_name': _get_node_name()})

    @app.route('/api/node/sync-pull', methods=['POST'])
    def api_node_sync_pull():
        """Pull data FROM a peer node."""
        data = request.get_json() or {}
        peer_ip = data.get('ip')
        peer_port = data.get('port', 8080)
        if not peer_ip:
            return jsonify({'error': 'No peer IP'}), 400

        import requests as req
        node_id = _get_node_id()
        node_name = _get_node_name()

        try:
            # Ask peer to push their data to us
            r = req.post(f'http://{peer_ip}:{peer_port}/api/node/sync-push',
                        json={'ip': request.host.split(':')[0], 'port': 8080}, timeout=30)
            # The peer pushed to us — our sync-receive handler logged it
            return jsonify({'status': 'pull_requested', 'peer': peer_ip})
        except Exception as e:
            return jsonify({'error': f'Pull failed: {e}'}), 500

    @app.route('/api/node/sync-log')
    def api_node_sync_log():
        db = get_db()
        rows = db.execute('SELECT * FROM sync_log ORDER BY created_at DESC LIMIT 50').fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    # Start UDP discovery listener in background
    def _discovery_listener():
        import socket
        DISCOVERY_PORT = 18080
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('', DISCOVERY_PORT))
            sock.settimeout(1)
            while True:
                try:
                    data, addr = sock.recvfrom(1024)
                    msg = json.loads(data.decode())
                    if msg.get('type') == 'nomad_discover' and msg.get('node_id') != _get_node_id():
                        # Respond with our identity
                        response = json.dumps({
                            'type': 'nomad_announce', 'node_id': _get_node_id(),
                            'node_name': _get_node_name(), 'port': 8080, 'version': VERSION,
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

    # USDA hardiness zones by approximate latitude (simplified offline lookup)
    HARDINESS_ZONES = [
        (48, '3a', 'Apr 30 - May 15', 'Sep 15 - Sep 30'),
        (45, '4a', 'Apr 20 - May 10', 'Sep 20 - Oct 5'),
        (43, '5a', 'Apr 10 - May 1', 'Oct 1 - Oct 15'),
        (40, '6a', 'Apr 1 - Apr 20', 'Oct 10 - Oct 25'),
        (37, '7a', 'Mar 20 - Apr 10', 'Oct 20 - Nov 5'),
        (34, '8a', 'Mar 10 - Mar 25', 'Nov 1 - Nov 15'),
        (31, '9a', 'Feb 15 - Mar 10', 'Nov 15 - Dec 1'),
        (28, '10a', 'Jan 30 - Feb 15', 'Dec 1 - Dec 15'),
        (25, '11a', 'Year-round', 'Year-round'),
    ]

    SEED_VIABILITY = {
        'onion': 1, 'parsnip': 1, 'parsley': 1, 'leek': 2, 'corn': 2, 'pepper': 2, 'spinach': 2,
        'lettuce': 3, 'pea': 3, 'bean': 3, 'carrot': 3, 'broccoli': 3, 'cauliflower': 3, 'kale': 3,
        'tomato': 4, 'squash': 4, 'pumpkin': 4, 'melon': 4, 'watermelon': 4, 'cucumber': 5,
        'radish': 5, 'beet': 4, 'cabbage': 4, 'turnip': 4, 'eggplant': 4,
    }

    @app.route('/api/garden/zone')
    def api_garden_zone():
        lat = request.args.get('lat', type=float)
        if lat is None:
            return jsonify({'zone': 'Unknown', 'last_frost': 'Unknown', 'first_frost': 'Unknown'})
        for min_lat, zone, last_frost, first_frost in HARDINESS_ZONES:
            if lat >= min_lat:
                return jsonify({'zone': zone, 'last_frost': last_frost, 'first_frost': first_frost, 'latitude': lat})
        return jsonify({'zone': '11a+', 'last_frost': 'Year-round', 'first_frost': 'Year-round', 'latitude': lat})

    @app.route('/api/garden/plots')
    def api_garden_plots():
        db = get_db()
        rows = db.execute('SELECT * FROM garden_plots ORDER BY name').fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/garden/plots', methods=['POST'])
    def api_garden_plots_create():
        data = request.get_json() or {}
        if not data.get('name'):
            return jsonify({'error': 'Name required'}), 400
        db = get_db()
        db.execute('INSERT INTO garden_plots (name, width_ft, length_ft, sun_exposure, soil_type, notes) VALUES (?,?,?,?,?,?)',
                   (data['name'], data.get('width_ft', 0), data.get('length_ft', 0),
                    data.get('sun_exposure', 'full'), data.get('soil_type', ''), data.get('notes', '')))
        db.commit()
        db.close()
        return jsonify({'status': 'created'}), 201

    @app.route('/api/garden/plots/<int:pid>', methods=['DELETE'])
    def api_garden_plots_delete(pid):
        db = get_db()
        db.execute('DELETE FROM garden_plots WHERE id = ?', (pid,))
        db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    @app.route('/api/garden/seeds')
    def api_garden_seeds():
        db = get_db()
        rows = db.execute('SELECT * FROM seeds ORDER BY species').fetchall()
        db.close()
        result = []
        current_year = int(time.strftime('%Y'))
        for r in rows:
            d = dict(r)
            species_key = r['species'].lower().strip()
            max_years = SEED_VIABILITY.get(species_key, 3)
            if r['year_harvested']:
                age = current_year - r['year_harvested']
                d['viability_pct'] = max(0, min(100, int(100 * (1 - age / (max_years + 1)))))
                d['viable'] = age <= max_years
            else:
                d['viability_pct'] = None
                d['viable'] = None
            result.append(d)
        return jsonify(result)

    @app.route('/api/garden/seeds', methods=['POST'])
    def api_garden_seeds_create():
        data = request.get_json() or {}
        if not data.get('species'):
            return jsonify({'error': 'Species required'}), 400
        db = get_db()
        db.execute('INSERT INTO seeds (species, variety, quantity, unit, year_harvested, source, days_to_maturity, planting_season, notes) VALUES (?,?,?,?,?,?,?,?,?)',
                   (data['species'], data.get('variety', ''), data.get('quantity', 0), data.get('unit', 'seeds'),
                    data.get('year_harvested'), data.get('source', ''), data.get('days_to_maturity'),
                    data.get('planting_season', 'spring'), data.get('notes', '')))
        db.commit()
        db.close()
        return jsonify({'status': 'created'}), 201

    @app.route('/api/garden/seeds/<int:sid>', methods=['DELETE'])
    def api_garden_seeds_delete(sid):
        db = get_db()
        db.execute('DELETE FROM seeds WHERE id = ?', (sid,))
        db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    @app.route('/api/garden/harvests')
    def api_garden_harvests():
        db = get_db()
        rows = db.execute('SELECT h.*, g.name as plot_name FROM harvest_log h LEFT JOIN garden_plots g ON h.plot_id = g.id ORDER BY h.created_at DESC LIMIT 100').fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/garden/harvests', methods=['POST'])
    def api_garden_harvests_create():
        data = request.get_json() or {}
        if not data.get('crop'):
            return jsonify({'error': 'Crop name required'}), 400
        try:
            qty = max(0, float(data.get('quantity', 0)))
        except (ValueError, TypeError):
            qty = 0
        db = get_db()
        try:
            db.execute('INSERT INTO harvest_log (crop, quantity, unit, plot_id, notes) VALUES (?,?,?,?,?)',
                       (data['crop'], qty, data.get('unit', 'lbs'),
                        data.get('plot_id'), data.get('notes', '')))
            existing = db.execute('SELECT id, quantity FROM inventory WHERE name = ? AND category = ?', (data['crop'], 'food')).fetchone()
            if existing:
                db.execute('UPDATE inventory SET quantity = quantity + ? WHERE id = ?', (qty, existing['id']))
            else:
                db.execute('INSERT INTO inventory (name, category, quantity, unit) VALUES (?, ?, ?, ?)',
                           (data['crop'], 'food', qty, data.get('unit', 'lbs')))
            db.commit()
        finally:
            db.close()
        log_activity('harvest_logged', detail=f'{qty} {data.get("unit", "lbs")} of {data["crop"]}')
        return jsonify({'status': 'created', 'inventory_updated': True}), 201

    @app.route('/api/livestock')
    def api_livestock_list():
        db = get_db()
        rows = db.execute('SELECT * FROM livestock ORDER BY species, name').fetchall()
        db.close()
        return jsonify([{**dict(r), 'health_log': json.loads(r['health_log'] or '[]'),
                         'vaccinations': json.loads(r['vaccinations'] or '[]')} for r in rows])

    @app.route('/api/livestock', methods=['POST'])
    def api_livestock_create():
        data = request.get_json() or {}
        if not data.get('species'):
            return jsonify({'error': 'Species required'}), 400
        db = get_db()
        db.execute('INSERT INTO livestock (species, name, tag, dob, sex, weight_lbs, notes) VALUES (?,?,?,?,?,?,?)',
                   (data['species'], data.get('name', ''), data.get('tag', ''), data.get('dob', ''),
                    data.get('sex', ''), data.get('weight_lbs'), data.get('notes', '')))
        db.commit()
        db.close()
        return jsonify({'status': 'created'}), 201

    @app.route('/api/livestock/<int:lid>', methods=['PUT'])
    def api_livestock_update(lid):
        data = request.get_json() or {}
        db = get_db()
        db.execute('UPDATE livestock SET species=?, name=?, tag=?, dob=?, sex=?, weight_lbs=?, status=?, health_log=?, vaccinations=?, notes=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                   (data.get('species', ''), data.get('name', ''), data.get('tag', ''), data.get('dob', ''),
                    data.get('sex', ''), data.get('weight_lbs'), data.get('status', 'active'),
                    json.dumps(data.get('health_log', [])), json.dumps(data.get('vaccinations', [])),
                    data.get('notes', ''), lid))
        db.commit()
        db.close()
        return jsonify({'status': 'updated'})

    @app.route('/api/livestock/<int:lid>', methods=['DELETE'])
    def api_livestock_delete(lid):
        db = get_db()
        db.execute('DELETE FROM livestock WHERE id = ?', (lid,))
        db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    @app.route('/api/livestock/<int:lid>/health', methods=['POST'])
    def api_livestock_health_event(lid):
        """Add a health event to an animal's log."""
        data = request.get_json() or {}
        db = get_db()
        animal = db.execute('SELECT health_log FROM livestock WHERE id = ?', (lid,)).fetchone()
        if not animal:
            db.close()
            return jsonify({'error': 'Not found'}), 404
        log_entries = json.loads(animal['health_log'] or '[]')
        log_entries.append({'date': time.strftime('%Y-%m-%d'), 'event': data.get('event', ''), 'notes': data.get('notes', '')})
        db.execute('UPDATE livestock SET health_log = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                   (json.dumps(log_entries), lid))
        db.commit()
        db.close()
        return jsonify({'status': 'logged'}), 201

    # ─── Scenario Training Engine ──────────────────────────────────────

    @app.route('/api/scenarios')
    def api_scenarios_list():
        db = get_db()
        rows = db.execute('SELECT * FROM scenarios ORDER BY started_at DESC LIMIT 20').fetchall()
        db.close()
        return jsonify([{**dict(r), 'decisions': json.loads(r['decisions'] or '[]'),
                         'complications': json.loads(r['complications'] or '[]')} for r in rows])

    @app.route('/api/scenarios', methods=['POST'])
    def api_scenarios_create():
        data = request.get_json() or {}
        db = get_db()
        cur = db.execute('INSERT INTO scenarios (scenario_type, title) VALUES (?, ?)',
                         (data.get('type', ''), data.get('title', '')))
        db.commit()
        sid = cur.lastrowid
        db.close()
        return jsonify({'id': sid}), 201

    @app.route('/api/scenarios/<int:sid>', methods=['PUT'])
    def api_scenarios_update(sid):
        data = request.get_json() or {}
        db = get_db()
        db.execute('UPDATE scenarios SET current_phase=?, status=?, decisions=?, complications=?, score=?, aar_text=?, completed_at=? WHERE id=?',
                   (data.get('current_phase', 0), data.get('status', 'active'),
                    json.dumps(data.get('decisions', [])), json.dumps(data.get('complications', [])),
                    data.get('score', 0), data.get('aar_text', ''), data.get('completed_at', ''), sid))
        db.commit()
        db.close()
        return jsonify({'status': 'updated'})

    @app.route('/api/scenarios/<int:sid>/complication', methods=['POST'])
    def api_scenario_complication(sid):
        """AI generates a context-aware complication based on current scenario state + user's real data."""
        data = request.get_json() or {}
        phase_desc = data.get('phase_description', '')
        decisions_so_far = data.get('decisions', [])

        # Gather real situation context
        db = get_db()
        inv_items = db.execute('SELECT name, quantity, unit, daily_usage FROM inventory WHERE daily_usage > 0 ORDER BY (quantity/daily_usage) LIMIT 5').fetchall()
        contacts_count = db.execute('SELECT COUNT(*) as c FROM contacts').fetchone()['c']
        sit_raw = db.execute("SELECT value FROM settings WHERE key='sit_board'").fetchone()
        db.close()

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
        db = get_db()
        scenario = db.execute('SELECT * FROM scenarios WHERE id = ?', (sid,)).fetchone()
        db.close()
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

    # ─── Medical Module ────────────────────────────────────────────────

    @app.route('/api/patients')
    def api_patients_list():
        db = get_db()
        rows = db.execute('SELECT * FROM patients ORDER BY name').fetchall()
        db.close()
        return jsonify([{**dict(r), 'allergies': json.loads(r['allergies'] or '[]'),
                         'medications': json.loads(r['medications'] or '[]'),
                         'conditions': json.loads(r['conditions'] or '[]')} for r in rows])

    @app.route('/api/patients', methods=['POST'])
    def api_patients_create():
        data = request.get_json() or {}
        if not data.get('name'):
            return jsonify({'error': 'Name required'}), 400
        db = get_db()
        cur = db.execute(
            'INSERT INTO patients (contact_id, name, age, weight_kg, sex, blood_type, allergies, medications, conditions, notes) VALUES (?,?,?,?,?,?,?,?,?,?)',
            (data.get('contact_id'), data['name'], data.get('age'), data.get('weight_kg'),
             data.get('sex', ''), data.get('blood_type', ''),
             json.dumps(data.get('allergies', [])), json.dumps(data.get('medications', [])),
             json.dumps(data.get('conditions', [])), data.get('notes', '')))
        db.commit()
        pid = cur.lastrowid
        db.close()
        return jsonify({'id': pid, 'status': 'created'}), 201

    @app.route('/api/patients/<int:pid>', methods=['PUT'])
    def api_patients_update(pid):
        data = request.get_json() or {}
        db = get_db()
        db.execute(
            'UPDATE patients SET name=?, age=?, weight_kg=?, sex=?, blood_type=?, allergies=?, medications=?, conditions=?, notes=?, contact_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
            (data.get('name', ''), data.get('age'), data.get('weight_kg'),
             data.get('sex', ''), data.get('blood_type', ''),
             json.dumps(data.get('allergies', [])), json.dumps(data.get('medications', [])),
             json.dumps(data.get('conditions', [])), data.get('notes', ''), data.get('contact_id'), pid))
        db.commit()
        db.close()
        return jsonify({'status': 'updated'})

    @app.route('/api/patients/<int:pid>', methods=['DELETE'])
    def api_patients_delete(pid):
        db = get_db()
        db.execute('DELETE FROM patients WHERE id = ?', (pid,))
        db.execute('DELETE FROM vitals_log WHERE patient_id = ?', (pid,))
        db.execute('DELETE FROM wound_log WHERE patient_id = ?', (pid,))
        db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    @app.route('/api/patients/<int:pid>/vitals')
    def api_vitals_list(pid):
        db = get_db()
        rows = db.execute('SELECT * FROM vitals_log WHERE patient_id = ? ORDER BY created_at DESC LIMIT 50', (pid,)).fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/patients/<int:pid>/vitals', methods=['POST'])
    def api_vitals_create(pid):
        data = request.get_json() or {}
        db = get_db()
        db.execute(
            'INSERT INTO vitals_log (patient_id, bp_systolic, bp_diastolic, pulse, resp_rate, temp_f, spo2, pain_level, gcs, notes) VALUES (?,?,?,?,?,?,?,?,?,?)',
            (pid, data.get('bp_systolic'), data.get('bp_diastolic'), data.get('pulse'),
             data.get('resp_rate'), data.get('temp_f'), data.get('spo2'),
             data.get('pain_level'), data.get('gcs'), data.get('notes', '')))
        db.commit()
        db.close()
        return jsonify({'status': 'logged'}), 201

    @app.route('/api/patients/<int:pid>/wounds')
    def api_wounds_list(pid):
        db = get_db()
        rows = db.execute('SELECT * FROM wound_log WHERE patient_id = ? ORDER BY created_at DESC', (pid,)).fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/patients/<int:pid>/wounds', methods=['POST'])
    def api_wounds_create(pid):
        data = request.get_json() or {}
        db = get_db()
        db.execute(
            'INSERT INTO wound_log (patient_id, location, wound_type, severity, description, treatment) VALUES (?,?,?,?,?,?)',
            (pid, data.get('location', ''), data.get('wound_type', ''), data.get('severity', 'minor'),
             data.get('description', ''), data.get('treatment', '')))
        db.commit()
        db.close()
        return jsonify({'status': 'logged'}), 201

    @app.route('/api/patients/<int:pid>/card')
    def api_patient_card(pid):
        """Generate a printable patient care card."""
        db = get_db()
        patient = db.execute('SELECT * FROM patients WHERE id = ?', (pid,)).fetchone()
        if not patient:
            db.close()
            return jsonify({'error': 'Not found'}), 404
        vitals = [dict(r) for r in db.execute('SELECT * FROM vitals_log WHERE patient_id = ? ORDER BY created_at DESC LIMIT 20', (pid,)).fetchall()]
        wounds = [dict(r) for r in db.execute('SELECT * FROM wound_log WHERE patient_id = ? ORDER BY created_at DESC', (pid,)).fetchall()]
        db.close()

        p = dict(patient)
        allergies = json.loads(p.get('allergies') or '[]')
        medications = json.loads(p.get('medications') or '[]')
        conditions = json.loads(p.get('conditions') or '[]')
        weight_lbs = round(p['weight_kg'] * 2.205, 1) if p.get('weight_kg') else '?'

        html = f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Patient Card — {_esc(p["name"])}</title>
        <style>body{{font-family:'Segoe UI',sans-serif;padding:20px;max-width:800px;margin:0 auto;font-size:12px;line-height:1.6;}}
        h1{{font-size:18px;border-bottom:2px solid #333;padding-bottom:4px;}}h2{{font-size:14px;color:#555;margin-top:16px;border-bottom:1px solid #ccc;padding-bottom:3px;}}
        .grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px;}}
        .field{{margin-bottom:4px;}}.label{{font-weight:700;color:#333;}}.warn{{color:red;font-weight:700;}}
        table{{border-collapse:collapse;width:100%;margin:8px 0;font-size:11px;}}th,td{{border:1px solid #ccc;padding:4px 8px;text-align:left;}}th{{background:#f0f0f0;}}
        @media print{{body{{padding:10px;}}}} </style></head><body>
        <h1>Patient Care Card — {_esc(p["name"])}</h1>
        <div class="grid">
          <div class="field"><span class="label">Age:</span> {p.get("age") or "?"}</div>
          <div class="field"><span class="label">Sex:</span> {p.get("sex") or "?"}</div>
          <div class="field"><span class="label">Weight:</span> {p.get("weight_kg") or "?"} kg ({weight_lbs} lbs)</div>
          <div class="field"><span class="label">Blood Type:</span> {_esc(p.get("blood_type") or "?")}</div>
        </div>
        <div class="field warn">Allergies: {", ".join(allergies) if allergies else "NKDA (No Known Drug Allergies)"}</div>
        <div class="field"><span class="label">Current Medications:</span> {", ".join(medications) if medications else "None"}</div>
        <div class="field"><span class="label">Conditions:</span> {", ".join(conditions) if conditions else "None"}</div>
        {f'<div class="field"><span class="label">Notes:</span> {_esc(p.get("notes",""))}</div>' if p.get("notes") else ""}
        '''

        if vitals:
            html += '<h2>Vital Signs History</h2><table><thead><tr><th>Time</th><th>BP</th><th>Pulse</th><th>Resp</th><th>Temp</th><th>SpO2</th><th>Pain</th><th>GCS</th><th>Notes</th></tr></thead><tbody>'
            for v in vitals:
                bp = f'{v["bp_systolic"]}/{v["bp_diastolic"]}' if v.get('bp_systolic') else '-'
                html += f'<tr><td>{v["created_at"]}</td><td>{bp}</td><td>{v.get("pulse") or "-"}</td><td>{v.get("resp_rate") or "-"}</td><td>{v.get("temp_f") or "-"}</td><td>{v.get("spo2") or "-"}%</td><td>{v.get("pain_level") or "-"}/10</td><td>{v.get("gcs") or "-"}</td><td>{_esc(v.get("notes",""))}</td></tr>'
            html += '</tbody></table>'

        if wounds:
            html += '<h2>Wound Log</h2><table><thead><tr><th>Time</th><th>Location</th><th>Type</th><th>Severity</th><th>Description</th><th>Treatment</th></tr></thead><tbody>'
            for w in wounds:
                html += f'<tr><td>{w["created_at"]}</td><td>{_esc(w.get("location",""))}</td><td>{_esc(w.get("wound_type",""))}</td><td>{_esc(w.get("severity",""))}</td><td>{_esc(w.get("description",""))}</td><td>{_esc(w.get("treatment",""))}</td></tr>'
            html += '</tbody></table>'

        html += f'<p style="margin-top:16px;font-size:9px;color:#999;">Generated by Project N.O.M.A.D. — {time.strftime("%Y-%m-%d %H:%M")}</p></body></html>'
        return html

    DRUG_INTERACTIONS = [
        ('Ibuprofen', 'Aspirin', 'major', 'Ibuprofen reduces aspirin\'s cardioprotective effect. Take aspirin 30 min before ibuprofen.'),
        ('Ibuprofen', 'Warfarin', 'major', 'Increased bleeding risk. Avoid combination or monitor closely.'),
        ('Ibuprofen', 'Lisinopril', 'moderate', 'NSAIDs reduce blood pressure medication effectiveness and risk kidney damage.'),
        ('Ibuprofen', 'Metformin', 'moderate', 'NSAIDs may impair kidney function, affecting metformin clearance.'),
        ('Acetaminophen', 'Warfarin', 'moderate', 'High-dose acetaminophen (>2g/day) can increase INR/bleeding risk.'),
        ('Acetaminophen', 'Alcohol', 'major', 'Combined liver toxicity. Avoid acetaminophen if >3 drinks/day.'),
        ('Aspirin', 'Warfarin', 'major', 'Significantly increased bleeding risk. Avoid unless directed by physician.'),
        ('Aspirin', 'Methotrexate', 'major', 'Aspirin reduces methotrexate clearance — toxicity risk.'),
        ('Amoxicillin', 'Methotrexate', 'major', 'Amoxicillin reduces methotrexate clearance — toxicity risk.'),
        ('Amoxicillin', 'Warfarin', 'moderate', 'May increase anticoagulant effect. Monitor for bleeding.'),
        ('Diphenhydramine', 'Alcohol', 'major', 'Extreme drowsiness and CNS depression. Do not combine.'),
        ('Diphenhydramine', 'Oxycodone', 'major', 'Additive CNS/respiratory depression. Life-threatening.'),
        ('Diphenhydramine', 'Tramadol', 'major', 'Seizure risk increased. Additive CNS depression.'),
        ('Metformin', 'Alcohol', 'major', 'Lactic acidosis risk. Limit alcohol with metformin.'),
        ('Lisinopril', 'Potassium', 'major', 'Hyperkalemia risk. Avoid potassium supplements unless directed.'),
        ('Lisinopril', 'Spironolactone', 'major', 'Dangerous hyperkalemia. Requires monitoring.'),
        ('Warfarin', 'Vitamin K', 'major', 'Vitamin K reverses warfarin effect. Keep dietary intake consistent.'),
        ('Warfarin', 'Ciprofloxacin', 'major', 'Dramatically increases warfarin effect — bleeding risk.'),
        ('Oxycodone', 'Alcohol', 'major', 'Fatal respiratory depression. Never combine.'),
        ('Oxycodone', 'Benzodiazepines', 'major', 'Fatal respiratory depression. FDA black box warning.'),
        ('Metoprolol', 'Verapamil', 'major', 'Severe bradycardia and heart block risk.'),
        ('Ciprofloxacin', 'Antacids', 'moderate', 'Antacids reduce ciprofloxacin absorption. Take 2h apart.'),
        ('Prednisone', 'Ibuprofen', 'moderate', 'Increased GI bleeding risk. Use with PPI if needed.'),
        ('Prednisone', 'Diabetes meds', 'moderate', 'Steroids raise blood sugar. May need dose adjustment.'),
        ('SSRIs', 'Tramadol', 'major', 'Serotonin syndrome risk. Potentially fatal.'),
        ('SSRIs', 'MAOIs', 'major', 'Serotonin syndrome — potentially fatal. 14-day washout required.'),
    ]

    @app.route('/api/medical/interactions', methods=['POST'])
    def api_drug_interactions():
        """Check drug interactions for a list of medications."""
        data = request.get_json() or {}
        meds = [m.strip().lower() for m in data.get('medications', []) if m.strip()]
        if len(meds) < 2:
            return jsonify([])
        found = []
        for drug1, drug2, severity, detail in DRUG_INTERACTIONS:
            d1, d2 = drug1.lower(), drug2.lower()
            for m in meds:
                for n in meds:
                    if m != n and ((d1 in m or m in d1) and (d2 in n or n in d2)):
                        entry = {'drug1': drug1, 'drug2': drug2, 'severity': severity, 'detail': detail}
                        if entry not in found:
                            found.append(entry)
        return jsonify(found)

    # ─── Triage & TCCC API ─────────────────────────────────────────────

    @app.route('/api/medical/triage-board')
    def api_triage_board():
        """Returns all patients sorted by triage category for MCI management."""
        db = get_db()
        try:
            patients = [dict(r) for r in db.execute('SELECT id, name, age, blood_type, triage_category, care_phase, allergies, conditions, medications FROM patients ORDER BY name').fetchall()]
            # Group by triage category
            categories = {'immediate': [], 'delayed': [], 'minimal': [], 'expectant': [], 'unassigned': []}
            for p in patients:
                cat = p.get('triage_category', '') or 'unassigned'
                if cat in categories:
                    categories[cat].append(p)
                else:
                    categories['unassigned'].append(p)
            return jsonify({
                'categories': categories,
                'total': len(patients),
                'counts': {k: len(v) for k, v in categories.items()},
            })
        finally:
            db.close()

    @app.route('/api/medical/triage/<int:pid>', methods=['PUT'])
    def api_triage_update(pid):
        """Update a patient's triage category and care phase."""
        data = request.get_json() or {}
        db = get_db()
        try:
            if 'triage_category' in data:
                db.execute('UPDATE patients SET triage_category = ? WHERE id = ?', (data['triage_category'], pid))
            if 'care_phase' in data:
                db.execute('UPDATE patients SET care_phase = ? WHERE id = ?', (data['care_phase'], pid))
            db.commit()
            return jsonify({'status': 'updated'})
        finally:
            db.close()

    @app.route('/api/medical/handoff/<int:pid>', methods=['POST'])
    def api_medical_handoff(pid):
        """Generate an SBAR handoff report for a patient."""
        db = get_db()
        try:
            patient = db.execute('SELECT * FROM patients WHERE id = ?', (pid,)).fetchone()
            if not patient:
                return jsonify({'error': 'Patient not found'}), 404
            vitals = [dict(r) for r in db.execute('SELECT * FROM vitals_log WHERE patient_id = ? ORDER BY created_at DESC LIMIT 5', (pid,)).fetchall()]
            wounds = [dict(r) for r in db.execute('SELECT * FROM wound_log WHERE patient_id = ? ORDER BY created_at DESC', (pid,)).fetchall()]

            p = dict(patient)
            allergies = json.loads(p.get('allergies', '[]') or '[]')
            conditions = json.loads(p.get('conditions', '[]') or '[]')
            medications = json.loads(p.get('medications', '[]') or '[]')

            data = request.get_json() or {}
            from datetime import datetime
            now = datetime.now().strftime('%Y-%m-%d %H:%M')

            situation = data.get('situation', f'Patient {p["name"]}, triage: {p.get("triage_category","unassigned")}')
            background = data.get('background', f'Age: {p.get("age","?")}. Blood type: {p.get("blood_type","?")}. Allergies: {", ".join(allergies) or "NKDA"}. Conditions: {", ".join(conditions) or "None"}. Medications: {", ".join(medications) or "None"}.')
            assessment = data.get('assessment', f'{len(wounds)} wounds documented. Latest vitals: {"available" if vitals else "none recorded"}.')
            recommendation = data.get('recommendation', '')

            from html import escape as esc
            report_html = f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>SBAR Handoff — {esc(p["name"])}</title>
<style>
body {{ font-family: 'Courier New', monospace; margin: 0; padding: 12px; font-size: 11px; color: #000; }}
h1 {{ font-size: 14px; text-align: center; border-bottom: 3px solid #000; padding-bottom: 4px; margin: 0 0 8px; }}
h2 {{ font-size: 11px; background: #333; color: #fff; padding: 3px 8px; margin: 8px 0 4px; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ border: 1px solid #999; padding: 3px 6px; font-size: 10px; }}
th {{ background: #eee; font-weight: 700; }}
.section {{ margin-bottom: 8px; padding: 6px 8px; border: 1px solid #ccc; border-radius: 4px; }}
.label {{ font-weight: 700; }}
@media print {{ @page {{ margin: 10mm; }} }}
</style></head><body>
<h1>SBAR PATIENT HANDOFF — {esc(p["name"])}</h1>
<div style="text-align:center;font-size:10px;margin-bottom:8px;">{esc(now)} | From: {esc(data.get("from_provider","___"))} → To: {esc(data.get("to_provider","___"))}</div>
<div class="section"><span class="label">S — SITUATION:</span> {esc(situation)}</div>
<div class="section"><span class="label">B — BACKGROUND:</span> {esc(background)}</div>
<div class="section"><span class="label">A — ASSESSMENT:</span> {esc(assessment)}</div>
<div class="section"><span class="label">R — RECOMMENDATION:</span> {esc(recommendation or "Continue current treatment plan.")}</div>'''

            if vitals:
                report_html += '<h2>RECENT VITALS</h2><table><tr><th>Time</th><th>HR</th><th>BP</th><th>RR</th><th>SpO2</th><th>Temp</th></tr>'
                for v in vitals[:5]:
                    report_html += f'<tr><td>{esc(str(v.get("created_at","")))}</td><td>{esc(str(v.get("heart_rate","")))}</td><td>{esc(str(v.get("bp_systolic","")))}/{esc(str(v.get("bp_diastolic","")))}</td><td>{esc(str(v.get("resp_rate","")))}</td><td>{esc(str(v.get("spo2","")))}</td><td>{esc(str(v.get("temp_f","")))}</td></tr>'
                report_html += '</table>'

            if wounds:
                report_html += '<h2>WOUND LOG</h2><table><tr><th>Time</th><th>Type</th><th>Location</th><th>Treatment</th></tr>'
                for w in wounds:
                    report_html += f'<tr><td>{esc(str(w.get("created_at","")))}</td><td>{esc(str(w.get("wound_type","")))}</td><td>{esc(str(w.get("location","")))}</td><td>{esc(str(w.get("treatment","")))}</td></tr>'
                report_html += '</table>'

            report_html += '<div style="margin-top:12px;border-top:2px solid #000;padding-top:6px;font-size:10px;">Provider signature: _________________________ Date/Time: _____________</div></body></html>'

            # Save to DB
            db.execute('INSERT INTO handoff_reports (patient_id, from_provider, to_provider, situation, background, assessment, recommendation, report_html) VALUES (?,?,?,?,?,?,?,?)',
                       (pid, data.get('from_provider', ''), data.get('to_provider', ''), situation, background, assessment, recommendation, report_html))
            db.commit()
            rid = db.execute('SELECT last_insert_rowid()').fetchone()[0]

            return jsonify({'status': 'created', 'id': rid, 'html': report_html})
        finally:
            db.close()

    @app.route('/api/medical/handoff/<int:rid>/print')
    def api_medical_handoff_print(rid):
        db = get_db()
        row = db.execute('SELECT report_html FROM handoff_reports WHERE id = ?', (rid,)).fetchone()
        db.close()
        if not row:
            return jsonify({'error': 'Report not found'}), 404
        return Response(row['report_html'], mimetype='text/html')

    TCCC_MARCH = [
        {'step': 'M', 'name': 'Massive Hemorrhage', 'actions': ['Apply tourniquet high and tight', 'Pack wound with hemostatic gauze', 'Apply direct pressure', 'Note tourniquet time']},
        {'step': 'A', 'name': 'Airway', 'actions': ['Head-tilt chin-lift (if no C-spine concern)', 'Jaw thrust (if C-spine concern)', 'Insert NPA if unconscious with gag reflex', 'Recovery position if breathing']},
        {'step': 'R', 'name': 'Respiration', 'actions': ['Expose chest — look for wounds', 'Seal open chest wounds (3-sided occlusive)', 'Needle decompression if tension pneumothorax', 'Monitor rate and quality']},
        {'step': 'C', 'name': 'Circulation', 'actions': ['Reassess tourniquets', 'Start IV/IO if available and trained', 'Elevate legs for shock', 'Keep warm — prevent hypothermia']},
        {'step': 'H', 'name': 'Hypothermia/Head', 'actions': ['Wrap in blanket/sleeping bag', 'Insulate from ground', 'Assess for TBI (AVPU/GCS)', 'Monitor pupils and consciousness']},
    ]

    @app.route('/api/medical/tccc-protocol')
    def api_tccc_protocol():
        return jsonify(TCCC_MARCH)

    # ─── Sensor Devices & Readings API ─────────────────────────────────

    @app.route('/api/sensors/devices')
    def api_sensor_devices_list():
        db = get_db()
        rows = db.execute('SELECT * FROM sensor_devices ORDER BY name').fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/sensors/devices', methods=['POST'])
    def api_sensor_devices_create():
        data = request.get_json() or {}
        db = get_db()
        db.execute('INSERT INTO sensor_devices (device_type, name, connection_type, connection_config, polling_interval_sec, status) VALUES (?,?,?,?,?,?)',
                   (data.get('device_type', 'manual'), data.get('name', 'New Sensor'),
                    data.get('connection_type', 'manual'), json.dumps(data.get('connection_config', {})),
                    data.get('polling_interval_sec', 300), data.get('status', 'active')))
        db.commit()
        sid = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.close()
        return jsonify({'status': 'created', 'id': sid})

    @app.route('/api/sensors/devices/<int:sid>', methods=['DELETE'])
    def api_sensor_devices_delete(sid):
        db = get_db()
        db.execute('DELETE FROM sensor_devices WHERE id = ?', (sid,))
        db.execute('DELETE FROM sensor_readings WHERE device_id = ?', (sid,))
        db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    @app.route('/api/sensors/readings/<int:device_id>')
    def api_sensor_readings(device_id):
        period = request.args.get('period', '24h')
        period_map = {'24h': '-24 hours', '7d': '-7 days', '30d': '-30 days'}
        interval = period_map.get(period, '-24 hours')
        db = get_db()
        rows = db.execute(f"SELECT * FROM sensor_readings WHERE device_id = ? AND created_at >= datetime('now', ?) ORDER BY created_at",
                          (device_id, interval)).fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/sensors/readings', methods=['POST'])
    def api_sensor_readings_create():
        data = request.get_json() or {}
        db = get_db()
        db.execute('INSERT INTO sensor_readings (device_id, reading_type, value, unit) VALUES (?,?,?,?)',
                   (data.get('device_id'), data.get('reading_type', ''), data.get('value', 0), data.get('unit', '')))
        # Update device last_reading
        db.execute('UPDATE sensor_devices SET last_reading = ? WHERE id = ?',
                   (json.dumps({'type': data.get('reading_type'), 'value': data.get('value'), 'unit': data.get('unit')}), data.get('device_id')))
        db.commit()
        db.close()
        return jsonify({'status': 'recorded'})

    @app.route('/api/power/history')
    def api_power_history():
        """Power log with charting data."""
        period = request.args.get('period', '24h')
        period_map = {'24h': '-24 hours', '7d': '-7 days', '30d': '-30 days'}
        interval = period_map.get(period, '-24 hours')
        db = get_db()
        rows = db.execute(f"SELECT battery_soc, solar_watts, load_watts, created_at FROM power_log WHERE created_at >= datetime('now', ?) ORDER BY created_at",
                          (interval,)).fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/power/autonomy-forecast')
    def api_power_autonomy():
        """Projected days of autonomy based on recent trends."""
        db = get_db()
        try:
            # Get last 24h of power data
            rows = db.execute("SELECT battery_soc, solar_watts, load_watts FROM power_log WHERE created_at >= datetime('now', '-24 hours') ORDER BY created_at DESC").fetchall()
            if not rows:
                return jsonify({'days': None, 'message': 'No power data available'})
            avg_load = sum(r['load_watts'] or 0 for r in rows) / len(rows)
            avg_solar = sum(r['solar_watts'] or 0 for r in rows) / len(rows)
            current_soc = rows[0]['battery_soc'] or 0
            # Assume 5kWh battery bank, rough estimate
            battery_wh = 5000 * (current_soc / 100)
            net_drain = max(0.1, avg_load - avg_solar)  # watts net drain
            hours = battery_wh / net_drain if net_drain > 0 else 999
            return jsonify({
                'days': round(hours / 24, 1),
                'hours': round(hours, 1),
                'current_soc': current_soc,
                'avg_load_w': round(avg_load, 1),
                'avg_solar_w': round(avg_solar, 1),
                'net_drain_w': round(net_drain, 1),
            })
        finally:
            db.close()

    # ─── Garden Calendar & Yield Analysis ────────────────────────────

    @app.route('/api/garden/calendar')
    def api_garden_calendar():
        """Planting calendar based on configured USDA zone."""
        db = get_db()
        zone_row = db.execute("SELECT value FROM settings WHERE key = 'usda_zone'").fetchone()
        zone = zone_row['value'] if zone_row else '7'
        rows = db.execute('SELECT * FROM planting_calendar WHERE zone = ? ORDER BY month, crop', (zone,)).fetchall()
        db.close()
        if not rows:
            _seed_planting_calendar()
            db = get_db()
            rows = db.execute('SELECT * FROM planting_calendar WHERE zone = ? ORDER BY month, crop', (zone,)).fetchall()
            db.close()
        return jsonify([dict(r) for r in rows])

    def _seed_planting_calendar():
        """Seed zone 7 planting calendar (mid-Atlantic/Southeast US default)."""
        db = get_db()
        entries = [
            ('Tomato','7',3,'start_indoor','Start seeds indoors 6-8 weeks before last frost',0.8,80,75),
            ('Tomato','7',5,'transplant','Transplant after last frost',0.8,80,75),
            ('Tomato','7',7,'harvest','Begin harvesting',0.8,80,0),
            ('Pepper','7',3,'start_indoor','Start seeds indoors',0.4,90,80),
            ('Pepper','7',5,'transplant','Transplant after soil warms',0.4,90,80),
            ('Squash','7',5,'direct_sow','Direct sow after frost',0.6,70,55),
            ('Squash','7',7,'harvest','Summer squash harvest begins',0.6,70,0),
            ('Beans','7',4,'direct_sow','Direct sow bush beans',0.5,130,55),
            ('Beans','7',7,'direct_sow','Succession plant for fall',0.5,130,55),
            ('Corn','7',4,'direct_sow','Direct sow when soil > 60F',0.3,365,75),
            ('Lettuce','7',3,'direct_sow','Cool season — direct sow early',1.0,65,45),
            ('Lettuce','7',9,'direct_sow','Fall planting',1.0,65,45),
            ('Peas','7',2,'direct_sow','Cool season — plant early',0.3,120,60),
            ('Garlic','7',10,'plant','Plant cloves 2" deep',0.4,600,240),
            ('Onion','7',2,'start_indoor','Start sets indoors',0.5,180,100),
            ('Potato','7',3,'plant','Plant seed potatoes after light frost',1.2,340,90),
            ('Potato','7',7,'harvest','Harvest when tops die back',1.2,340,0),
            ('Carrot','7',3,'direct_sow','Direct sow in loose soil',0.6,190,70),
            ('Carrot','7',8,'direct_sow','Fall crop',0.6,190,70),
            ('Kale','7',3,'direct_sow','Very cold hardy — early start',0.5,130,55),
            ('Kale','7',8,'direct_sow','Fall/winter crop — improves with frost',0.5,130,55),
            ('Cabbage','7',3,'start_indoor','Start indoors',0.6,100,80),
            ('Cabbage','7',8,'transplant','Fall crop transplant',0.6,100,80),
            ('Radish','7',3,'direct_sow','Quick crop — 25 days',1.5,66,25),
            ('Radish','7',9,'direct_sow','Fall planting',1.5,66,25),
            ('Sweet Potato','7',5,'plant','Plant slips after warm soil',0.8,390,100),
            ('Turnip','7',3,'direct_sow','Spring crop',0.7,130,50),
            ('Turnip','7',8,'direct_sow','Best as fall crop',0.7,130,50),
            ('Beet','7',3,'direct_sow','Spring planting',0.5,180,55),
            ('Cucumber','7',5,'direct_sow','After last frost',0.6,65,55),
            ('Zucchini','7',5,'direct_sow','Very productive',0.8,80,50),
            ('Watermelon','7',5,'direct_sow','Needs heat and space',0.3,140,85),
        ]
        for e in entries:
            db.execute('INSERT OR IGNORE INTO planting_calendar (crop, zone, month, action, notes, yield_per_sqft, calories_per_lb, days_to_harvest) VALUES (?,?,?,?,?,?,?,?)', e)
        db.commit()
        db.close()

    @app.route('/api/garden/yield-analysis')
    def api_garden_yield_analysis():
        """Yield per crop and caloric output analysis."""
        db = get_db()
        try:
            harvests = db.execute('''SELECT crop, SUM(quantity) as total_lbs, COUNT(*) as harvests,
                                     AVG(yield_per_sqft) as avg_yield
                                     FROM harvest_log GROUP BY crop ORDER BY total_lbs DESC''').fetchall()
            plots = db.execute('SELECT SUM(CASE WHEN width_ft > 0 AND length_ft > 0 THEN width_ft * length_ft ELSE 0 END) as total_sqft FROM garden_plots').fetchone()
            total_sqft = plots['total_sqft'] or 0

            # Caloric analysis from planting calendar
            cal_data = db.execute('SELECT crop, calories_per_lb FROM planting_calendar WHERE calories_per_lb > 0 GROUP BY crop').fetchall()
            cal_map = {r['crop']: r['calories_per_lb'] for r in cal_data}

            result = []
            total_calories = 0
            for h in harvests:
                cal_per_lb = cal_map.get(h['crop'], 200)  # default 200 cal/lb
                total_cal = (h['total_lbs'] or 0) * cal_per_lb
                total_calories += total_cal
                result.append({
                    'crop': h['crop'], 'total_lbs': round(h['total_lbs'] or 0, 1),
                    'harvests': h['harvests'], 'avg_yield_sqft': round(h['avg_yield'] or 0, 2),
                    'calories': round(total_cal),
                })

            # Person-days of food (2000 cal/day)
            person_days = round(total_calories / 2000, 1) if total_calories > 0 else 0

            return jsonify({
                'crops': result, 'total_sqft': round(total_sqft, 1),
                'total_calories': round(total_calories),
                'person_days': person_days,
            })
        finally:
            db.close()

    @app.route('/api/garden/preservation')
    def api_preservation_list():
        db = get_db()
        rows = db.execute('SELECT * FROM preservation_log ORDER BY batch_date DESC').fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/garden/preservation', methods=['POST'])
    def api_preservation_create():
        data = request.get_json() or {}
        db = get_db()
        db.execute('INSERT INTO preservation_log (crop, method, quantity, unit, batch_date, shelf_life_months, notes) VALUES (?,?,?,?,?,?,?)',
                   (data.get('crop', ''), data.get('method', 'canning'), data.get('quantity', 0),
                    data.get('unit', 'quarts'), data.get('batch_date', ''), data.get('shelf_life_months', 12), data.get('notes', '')))
        db.commit()
        db.close()
        return jsonify({'status': 'created'})

    @app.route('/api/garden/preservation/<int:pid>', methods=['DELETE'])
    def api_preservation_delete(pid):
        db = get_db()
        db.execute('DELETE FROM preservation_log WHERE id = ?', (pid,))
        db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    # ─── Garden Enhancements (v5.0 Phase 11) ────────────────────────

    @app.route('/api/garden/companions')
    def api_companion_plants():
        """Get companion planting guide."""
        db = get_db()
        try:
            rows = db.execute('SELECT * FROM companion_plants ORDER BY plant_a').fetchall()
            companions = [dict(r) for r in rows]
            if not companions:
                # Seed with common companion planting data
                pairs = [
                    ('Tomato', 'Basil', 'companion', 'Basil repels pests and improves tomato flavor'),
                    ('Tomato', 'Carrot', 'companion', 'Carrots loosen soil for tomato roots'),
                    ('Tomato', 'Fennel', 'antagonist', 'Fennel inhibits tomato growth'),
                    ('Corn', 'Bean', 'companion', 'Three Sisters: beans fix nitrogen for corn'),
                    ('Corn', 'Squash', 'companion', 'Three Sisters: squash shades soil'),
                    ('Bean', 'Onion', 'antagonist', 'Onions inhibit bean growth'),
                    ('Carrot', 'Onion', 'companion', 'Onions repel carrot fly'),
                    ('Lettuce', 'Radish', 'companion', 'Quick radish harvest makes room'),
                    ('Cucumber', 'Dill', 'companion', 'Dill attracts beneficial insects'),
                    ('Pepper', 'Basil', 'companion', 'Basil repels aphids and spider mites'),
                    ('Potato', 'Horseradish', 'companion', 'Horseradish deters potato beetles'),
                    ('Potato', 'Tomato', 'antagonist', 'Both susceptible to blight — spread disease'),
                    ('Cabbage', 'Dill', 'companion', 'Dill attracts wasps that prey on cabbage worms'),
                    ('Cabbage', 'Strawberry', 'antagonist', 'Compete for nutrients'),
                    ('Garlic', 'Rose', 'companion', 'Garlic repels aphids from roses'),
                    ('Marigold', 'Tomato', 'companion', 'Marigolds repel nematodes'),
                    ('Sunflower', 'Cucumber', 'companion', 'Sunflowers attract pollinators'),
                    ('Pea', 'Carrot', 'companion', 'Peas fix nitrogen for carrots'),
                    ('Spinach', 'Strawberry', 'companion', 'Good ground cover pairing'),
                    ('Zucchini', 'Nasturtium', 'companion', 'Nasturtiums trap squash bugs'),
                ]
                for a, b, rel, note in pairs:
                    db.execute('INSERT INTO companion_plants (plant_a, plant_b, relationship, notes) VALUES (?, ?, ?, ?)',
                               (a, b, rel, note))
                db.commit()
                companions = [{'plant_a': a, 'plant_b': b, 'relationship': rel, 'notes': note} for a, b, rel, note in pairs]
            return jsonify(companions)
        finally:
            db.close()

    @app.route('/api/garden/planting-calendar')
    def api_planting_calendar():
        """Get planting calendar with frost date adjustments."""
        zone = request.args.get('zone', '7')
        db = get_db()
        try:
            rows = db.execute('SELECT * FROM planting_calendar WHERE zone = ? ORDER BY month, crop', (zone,)).fetchall()
            return jsonify([dict(r) for r in rows])
        finally:
            db.close()

    @app.route('/api/garden/seeds/inventory')
    def api_seed_inventory():
        """List seed inventory."""
        db = get_db()
        try:
            rows = db.execute('SELECT * FROM seed_inventory ORDER BY species, variety').fetchall()
            return jsonify([dict(r) for r in rows])
        finally:
            db.close()

    @app.route('/api/garden/seeds/inventory', methods=['POST'])
    def api_seed_add():
        """Add seeds to inventory."""
        d = request.json or {}
        db = get_db()
        try:
            db.execute(
                '''INSERT INTO seed_inventory (species, variety, quantity, unit, viability_pct, year_acquired, source, days_to_maturity, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (d.get('species', ''), d.get('variety', ''), d.get('quantity', 0), d.get('unit', 'seeds'),
                 d.get('viability_pct', 90), d.get('year_acquired'), d.get('source', ''),
                 d.get('days_to_maturity'), d.get('notes', ''))
            )
            db.commit()
            return jsonify({'status': 'ok'})
        finally:
            db.close()

    @app.route('/api/garden/seeds/inventory/<int:sid>', methods=['DELETE'])
    def api_seed_delete(sid):
        """Delete a seed inventory entry."""
        db = get_db()
        try:
            db.execute('DELETE FROM seed_inventory WHERE id = ?', (sid,))
            db.commit()
            return jsonify({'status': 'ok'})
        finally:
            db.close()

    @app.route('/api/garden/pests')
    def api_pest_guide():
        """Get pest/disease reference guide."""
        db = get_db()
        try:
            rows = db.execute('SELECT * FROM pest_guide ORDER BY name').fetchall()
            pests = [dict(r) for r in rows]
            if not pests:
                guide = [
                    ('Aphids', 'insect', 'Most vegetables, roses', 'Curled leaves, sticky residue, stunted growth', 'Spray with soapy water, neem oil, introduce ladybugs', 'Companion plant with marigolds, avoid over-fertilizing'),
                    ('Tomato Hornworm', 'insect', 'Tomatoes, peppers, eggplant', 'Large holes in leaves, stripped stems, dark droppings', 'Hand-pick, BT spray, introduce parasitic wasps', 'Till soil in fall, rotate crops, plant dill to attract wasps'),
                    ('Powdery Mildew', 'fungus', 'Squash, cucumber, melon, peas', 'White powdery coating on leaves', 'Baking soda spray (1 tbsp/gal), neem oil, remove affected leaves', 'Space plants for airflow, water at base not leaves, resistant varieties'),
                    ('Slugs & Snails', 'mollusk', 'Lettuce, cabbage, strawberries, hostas', 'Irregular holes in leaves, slime trails', 'Beer traps, diatomaceous earth, copper tape around beds', 'Remove hiding spots, water in morning not evening'),
                    ('Colorado Potato Beetle', 'insect', 'Potatoes, eggplant, tomatoes', 'Stripped leaves, orange larvae on undersides', 'Hand-pick, neem oil, spinosad spray', 'Rotate crops, mulch with straw, plant resistant varieties'),
                    ('Blight (Early/Late)', 'fungus', 'Tomatoes, potatoes', 'Brown spots on leaves, fruit rot, rapid wilting', 'Copper fungicide, remove affected plants immediately', 'Rotate crops 3yr, resistant varieties, avoid overhead watering'),
                    ('Cabbage Worm', 'insect', 'Cabbage, broccoli, kale, cauliflower', 'Holes in leaves, green caterpillars, dark droppings', 'BT spray, hand-pick, row covers', 'Plant dill/thyme nearby, use floating row covers from transplant'),
                    ('Spider Mites', 'arachnid', 'Beans, tomatoes, strawberries, cucumbers', 'Yellow stippling on leaves, fine webs, leaf drop', 'Strong water spray, neem oil, insecticidal soap', 'Maintain humidity, avoid dusty conditions, introduce predatory mites'),
                    ('Root Rot', 'fungus', 'Most plants in poorly drained soil', 'Wilting despite moist soil, yellow leaves, mushy roots', 'Remove affected plants, improve drainage, fungicide drench', 'Ensure good drainage, avoid overwatering, raise beds'),
                    ('Japanese Beetle', 'insect', 'Roses, grapes, beans, raspberries', 'Skeletonized leaves (veins intact), damaged flowers', 'Hand-pick into soapy water, neem oil, milky spore for grubs', 'Treat lawn for grubs in fall, avoid traps near garden'),
                ]
                for name, ptype, affects, symptoms, treatment, prevention in guide:
                    db.execute('INSERT INTO pest_guide (name, pest_type, affects, symptoms, treatment, prevention) VALUES (?, ?, ?, ?, ?, ?)',
                               (name, ptype, affects, symptoms, treatment, prevention))
                db.commit()
                pests = [{'name': n, 'pest_type': p, 'affects': a, 'symptoms': s, 'treatment': t, 'prevention': pr}
                         for n, p, a, s, t, pr in guide]
            return jsonify(pests)
        finally:
            db.close()

    # ─── Federation v2 API ───────────────────────────────────────────

    @app.route('/api/federation/peers')
    def api_federation_peers():
        db = get_db()
        rows = db.execute('SELECT * FROM federation_peers ORDER BY last_seen DESC').fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/federation/peers', methods=['POST'])
    def api_federation_peer_add():
        data = request.get_json() or {}
        node_id = data.get('node_id', '').strip()
        if not node_id:
            return jsonify({'error': 'node_id required'}), 400
        db = get_db()
        db.execute('INSERT OR REPLACE INTO federation_peers (node_id, node_name, trust_level, ip, port) VALUES (?,?,?,?,?)',
                   (node_id, data.get('node_name', ''), data.get('trust_level', 'observer'),
                    data.get('ip', ''), data.get('port', 8080)))
        db.commit()
        db.close()
        return jsonify({'status': 'added'})

    @app.route('/api/federation/peers/<node_id>/trust', methods=['PUT'])
    def api_federation_peer_trust(node_id):
        data = request.get_json() or {}
        trust = data.get('trust_level', 'observer')
        if trust not in ('observer', 'member', 'trusted', 'admin'):
            return jsonify({'error': 'Invalid trust level'}), 400
        db = get_db()
        db.execute('UPDATE federation_peers SET trust_level = ? WHERE node_id = ?', (trust, node_id))
        db.commit()
        db.close()
        return jsonify({'status': 'updated'})

    @app.route('/api/federation/peers/<node_id>', methods=['DELETE'])
    def api_federation_peer_remove(node_id):
        db = get_db()
        db.execute('DELETE FROM federation_peers WHERE node_id = ?', (node_id,))
        db.commit()
        db.close()
        return jsonify({'status': 'removed'})

    @app.route('/api/federation/offers')
    def api_federation_offers():
        db = get_db()
        rows = db.execute("SELECT * FROM federation_offers WHERE status = 'active' ORDER BY created_at DESC").fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/federation/offers', methods=['POST'])
    def api_federation_offer_create():
        data = request.get_json() or {}
        db = get_db()
        db.execute('INSERT INTO federation_offers (item_type, item_id, quantity, node_id, notes) VALUES (?,?,?,?,?)',
                   (data.get('item_type', ''), data.get('item_id'), data.get('quantity', 0),
                    data.get('node_id', ''), data.get('notes', '')))
        db.commit()
        db.close()
        return jsonify({'status': 'created'})

    @app.route('/api/federation/requests')
    def api_federation_requests():
        db = get_db()
        rows = db.execute("SELECT * FROM federation_requests WHERE status = 'active' ORDER BY urgency DESC, created_at DESC").fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/federation/requests', methods=['POST'])
    def api_federation_request_create():
        data = request.get_json() or {}
        db = get_db()
        db.execute('INSERT INTO federation_requests (item_type, description, quantity, urgency, node_id) VALUES (?,?,?,?,?)',
                   (data.get('item_type', ''), data.get('description', ''), data.get('quantity', 0),
                    data.get('urgency', 'normal'), data.get('node_id', '')))
        db.commit()
        db.close()
        return jsonify({'status': 'created'})

    @app.route('/api/federation/sitboard')
    def api_federation_sitboard():
        """Aggregated situation from all peers."""
        db = get_db()
        rows = db.execute('SELECT * FROM federation_sitboard ORDER BY updated_at DESC').fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/federation/network-map')
    def api_federation_network_map():
        """Returns all known nodes with positions for map overlay."""
        db = get_db()
        peers = [dict(r) for r in db.execute('SELECT node_id, node_name, trust_level, last_seen, ip FROM federation_peers').fetchall()]
        # Check which peers have associated waypoints
        for p in peers:
            wp = db.execute("SELECT lat, lng FROM waypoints WHERE name LIKE ? OR notes LIKE ?",
                            (f'%{p["node_name"]}%', f'%{p["node_id"]}%')).fetchone()
            p['lat'] = wp['lat'] if wp else None
            p['lng'] = wp['lng'] if wp else None
        db.close()
        return jsonify(peers)

    # ─── Emergency Broadcast ──────────────────────────────────────────

    _broadcast = {'active': False, 'message': '', 'severity': 'info', 'timestamp': ''}

    @app.route('/api/broadcast')
    def api_broadcast_get():
        return jsonify(_broadcast)

    @app.route('/api/broadcast', methods=['POST'])
    def api_broadcast_set():
        data = request.get_json() or {}
        _broadcast['active'] = True
        _broadcast['message'] = (data.get('message', '') or '')[:500]
        _broadcast['severity'] = data.get('severity', 'info')
        _broadcast['timestamp'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        log_activity('broadcast_sent', detail=_broadcast['message'][:100])
        return jsonify({'status': 'sent'})

    @app.route('/api/broadcast/clear', methods=['POST'])
    def api_broadcast_clear():
        _broadcast['active'] = False
        _broadcast['message'] = ''
        return jsonify({'status': 'cleared'})

    # ─── Resource Allocation Planner ──────────────────────────────────

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
        db = get_db()
        inv = {}
        rows = db.execute('SELECT category, SUM(quantity) as qty FROM inventory GROUP BY category').fetchall()
        for r in rows:
            inv[r['category']] = r['qty'] or 0
        db.close()

        return jsonify({
            'people': people, 'days': days, 'activity': activity,
            'needs': needs, 'current_inventory': inv,
        })

    # ─── Notes Pin/Tag ────────────────────────────────────────────────

    @app.route('/api/notes/<int:note_id>/pin', methods=['POST'])
    def api_notes_pin(note_id):
        data = request.get_json() or {}
        pinned = 1 if data.get('pinned', True) else 0
        db = get_db()
        db.execute('UPDATE notes SET pinned = ? WHERE id = ?', (pinned, note_id))
        db.commit()
        db.close()
        return jsonify({'status': 'ok', 'pinned': pinned})

    @app.route('/api/notes/<int:note_id>/tags', methods=['PUT'])
    def api_notes_tags(note_id):
        data = request.get_json() or {}
        tags = data.get('tags', '')
        db = get_db()
        db.execute('UPDATE notes SET tags = ? WHERE id = ?', (tags, note_id))
        db.commit()
        db.close()
        return jsonify({'status': 'ok'})

    @app.route('/api/notes/<int:note_id>/export')
    def api_notes_export(note_id):
        """Export a single note as a Markdown file."""
        db = get_db()
        note = db.execute('SELECT * FROM notes WHERE id = ?', (note_id,)).fetchone()
        db.close()
        if not note:
            return jsonify({'error': 'Not found'}), 404
        title = note['title'] or 'Untitled'
        content = note['content'] or ''
        md = f"# {title}\n\n{content}"
        safe_title = secure_filename(title) or 'note'
        return Response(md, mimetype='text/markdown',
                       headers={'Content-Disposition': f'attachment; filename="{safe_title}.md"'})

    @app.route('/api/notes/export-all')
    def api_notes_export_all():
        """Export all notes as a ZIP of Markdown files."""
        try:
            import io
            import zipfile as zf
            db = get_db()
            notes = db.execute('SELECT * FROM notes ORDER BY updated_at DESC').fetchall()
            db.close()
            buf = io.BytesIO()
            with zf.ZipFile(buf, 'w', zf.ZIP_DEFLATED) as z:
                for n in notes:
                    title = n['title'] or 'Untitled'
                    content = n['content'] or ''
                    safe = secure_filename(title) or f'note-{n["id"]}'
                    md = f"# {title}\n\n{content}"
                    z.writestr(f'{safe}.md', md)
            buf.seek(0)
            return Response(buf.read(), mimetype='application/zip',
                           headers={'Content-Disposition': 'attachment; filename="nomad-notes.zip"'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # ─── Notes Enhancements (v5.0 Phase 5) ─────────────────────────

    @app.route('/api/notes/tags')
    def api_note_tags():
        """List all unique tags with counts."""
        db = get_db()
        try:
            rows = db.execute(
                'SELECT tag, COUNT(*) as count FROM note_tags GROUP BY tag ORDER BY count DESC, tag'
            ).fetchall()
            return jsonify([{'tag': r['tag'], 'count': r['count']} for r in rows])
        finally:
            db.close()

    @app.route('/api/notes/<int:note_id>/tags', methods=['POST'])
    def api_note_add_tag(note_id):
        """Add a tag to a note."""
        d = request.json or {}
        tag = d.get('tag', '').strip().lower()
        if not tag:
            return jsonify({'error': 'tag required'}), 400
        db = get_db()
        try:
            db.execute('INSERT OR IGNORE INTO note_tags (note_id, tag) VALUES (?, ?)', (note_id, tag))
            db.commit()
            return jsonify({'status': 'ok'})
        finally:
            db.close()

    @app.route('/api/notes/<int:note_id>/tags/<tag>', methods=['DELETE'])
    def api_note_remove_tag(note_id, tag):
        """Remove a tag from a note."""
        db = get_db()
        try:
            db.execute('DELETE FROM note_tags WHERE note_id = ? AND tag = ?', (note_id, tag))
            db.commit()
            return jsonify({'status': 'ok'})
        finally:
            db.close()

    @app.route('/api/notes/<int:note_id>/backlinks')
    def api_note_backlinks(note_id):
        """Get all notes that link to this note."""
        db = get_db()
        try:
            rows = db.execute(
                '''SELECT n.id, n.title, n.updated_at FROM notes n
                   JOIN note_links l ON l.source_note_id = n.id
                   WHERE l.target_note_id = ? ORDER BY n.updated_at DESC''',
                (note_id,)
            ).fetchall()
            return jsonify([dict(r) for r in rows])
        finally:
            db.close()

    @app.route('/api/notes/search-titles')
    def api_note_search_titles():
        """Search note titles for wiki-link autocomplete."""
        q = request.args.get('q', '').strip()
        if not q:
            return jsonify([])
        db = get_db()
        try:
            rows = db.execute('SELECT id, title FROM notes WHERE title LIKE ? LIMIT 10', (f'%{q}%',)).fetchall()
            return jsonify([{'id': r['id'], 'title': r['title']} for r in rows])
        finally:
            db.close()

    @app.route('/api/notes/templates')
    def api_note_templates():
        """List note templates."""
        db = get_db()
        try:
            rows = db.execute('SELECT * FROM note_templates ORDER BY name').fetchall()
            templates = [dict(r) for r in rows]
            # Add built-in templates if table is empty
            if not templates:
                builtins = [
                    {'name': 'Incident Report', 'icon': '🚨', 'content': '# Incident Report\n\n**Date:** \n**Location:** \n**Severity:** \n\n## Description\n\n\n## Actions Taken\n\n\n## Follow-up Required\n\n'},
                    {'name': 'Patrol Log', 'icon': '🔍', 'content': '# Patrol Log\n\n**Date:** \n**Route:** \n**Personnel:** \n\n## Observations\n\n\n## Contacts Made\n\n\n## Issues Found\n\n'},
                    {'name': 'Comms Log', 'icon': '📡', 'content': '# Communications Log\n\n**Date:** \n**Operator:** \n**Freq:** \n\n| Time | Callsign | Direction | Message | Signal |\n|------|----------|-----------|---------|--------|\n| | | | | |\n'},
                    {'name': 'SITREP', 'icon': '📋', 'content': '# SITREP\n\n**DTG:** \n**From:** \n**To:** \n\n## 1. SITUATION\n\n## 2. ACTIONS\n\n## 3. REQUIREMENTS\n\n## 4. LOGISTICS\n\n## 5. PERSONNEL\n\n'},
                    {'name': 'Meeting Notes', 'icon': '🤝', 'content': '# Meeting Notes\n\n**Date:** \n**Attendees:** \n\n## Agenda\n\n\n## Discussion\n\n\n## Action Items\n- [ ] \n'},
                    {'name': 'Daily Journal', 'icon': '📓', 'content': '# Journal Entry\n\n**Weather:** \n**Mood:** \n\n## Today\n\n\n## Accomplishments\n\n\n## Tomorrow\n\n'},
                ]
                for t in builtins:
                    db.execute('INSERT INTO note_templates (name, content, icon) VALUES (?, ?, ?)',
                               (t['name'], t['content'], t['icon']))
                db.commit()
                templates = builtins
            return jsonify(templates)
        finally:
            db.close()

    @app.route('/api/notes/journal', methods=['POST'])
    def api_note_create_journal():
        """Create a daily journal entry for today."""
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        title = f'Journal — {today}'
        db = get_db()
        try:
            # Check if today's journal already exists
            existing = db.execute("SELECT id FROM notes WHERE title = ? AND is_journal = 1", (title,)).fetchone()
            if existing:
                return jsonify({'id': existing['id'], 'existed': True})
            content = f'# {title}\n\n**Weather:** \n**Mood:** \n\n## Notes\n\n'
            db.execute('INSERT INTO notes (title, content, is_journal, tags) VALUES (?, ?, 1, ?)', (title, content, 'journal'))
            db.commit()
            note_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
            db.execute('INSERT OR IGNORE INTO note_tags (note_id, tag) VALUES (?, ?)', (note_id, 'journal'))
            db.commit()
            return jsonify({'id': note_id, 'existed': False})
        finally:
            db.close()

    # ─── Waypoint Distance Matrix ─────────────────────────────────────

    @app.route('/api/waypoints/distances')
    def api_waypoints_distances():
        db = get_db()
        wps = db.execute('SELECT id, name, lat, lng, category FROM waypoints ORDER BY name').fetchall()
        db.close()
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
        db = get_db()
        row = db.execute("SELECT value FROM settings WHERE key = 'ollama_host'").fetchone()
        db.close()
        return jsonify({'host': row['value'] if row else ''})

    @app.route('/api/settings/ollama-host', methods=['PUT'])
    def api_ollama_host_set():
        data = request.get_json() or {}
        host = (data.get('host', '') or '').strip()
        db = get_db()
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('ollama_host', ?)", (host,))
        db.commit()
        db.close()
        # Update ollama module's port/host
        if host:
            log_activity('ollama_host_changed', detail=host)
        return jsonify({'status': 'saved', 'host': host})

    # ─── Host Power Control ───────────────────────────────────────────

    @app.route('/api/system/shutdown', methods=['POST'])
    def api_system_shutdown():
        data = request.get_json() or {}
        action = data.get('action', 'shutdown')
        log_activity('system_power', detail=action)
        def do_power():
            import time as t
            t.sleep(2)
            from platform_utils import system_reboot, system_shutdown
            if action == 'reboot':
                system_reboot()
            else:
                system_shutdown()
        threading.Thread(target=do_power, daemon=True).start()
        return jsonify({'status': f'{action} initiated', 'delay': 5})

    # ─── Simple Auth ──────────────────────────────────────────────────

    @app.route('/api/auth/check')
    def api_auth_check():
        db = get_db()
        row = db.execute("SELECT value FROM settings WHERE key = 'auth_password'").fetchone()
        db.close()
        remote = request.remote_addr or ''
        is_local = remote in ('127.0.0.1', '::1', 'localhost')
        return jsonify({'enabled': bool(row and row['value']), 'authenticated': is_local or not (row and row['value'])})

    @app.route('/api/auth/set-password', methods=['POST'])
    def api_auth_set_password():
        data = request.get_json() or {}
        password = data.get('password', '').strip()
        import hashlib
        hashed = hashlib.sha256(password.encode()).hexdigest() if password else ''
        db = get_db()
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('auth_password', ?)", (hashed,))
        db.commit()
        db.close()
        return jsonify({'status': 'saved', 'enabled': bool(password)})

    # ─── PDF Viewer API ───────────────────────────────────────────────

    @app.route('/api/library/upload-pdf', methods=['POST'])
    def api_library_upload_pdf():
        if 'file' not in request.files:
            return jsonify({'error': 'No file'}), 400
        file = request.files['file']
        filename = secure_filename(file.filename)
        if not filename:
            return jsonify({'error': 'Invalid filename'}), 400
        pdf_dir = os.path.join(get_data_dir(), 'library')
        os.makedirs(pdf_dir, exist_ok=True)
        filepath = os.path.join(pdf_dir, filename)
        file.save(filepath)
        return jsonify({'status': 'uploaded', 'filename': filename, 'size': os.path.getsize(filepath)}), 201

    @app.route('/api/library/pdfs')
    def api_library_pdfs():
        pdf_dir = os.path.join(get_data_dir(), 'library')
        if not os.path.isdir(pdf_dir):
            return jsonify([])
        files = []
        for f in os.listdir(pdf_dir):
            if f.lower().endswith(('.pdf', '.epub', '.txt', '.md')):
                fp = os.path.join(pdf_dir, f)
                files.append({'filename': f, 'size': format_size(os.path.getsize(fp)), 'type': f.rsplit('.', 1)[-1].lower()})
        return jsonify(sorted(files, key=lambda x: x['filename']))

    @app.route('/api/library/serve/<path:filename>')
    def api_library_serve(filename):
        pdf_dir = os.path.join(get_data_dir(), 'library')
        safe = os.path.normpath(os.path.join(pdf_dir, secure_filename(filename)))
        if not safe.startswith(os.path.normpath(pdf_dir)) or not os.path.isfile(safe):
            return jsonify({'error': 'Not found'}), 404
        from flask import send_file
        return send_file(safe)

    @app.route('/api/library/delete/<path:filename>', methods=['DELETE'])
    def api_library_delete(filename):
        pdf_dir = os.path.join(get_data_dir(), 'library')
        safe = os.path.normpath(os.path.join(pdf_dir, secure_filename(filename)))
        if not safe.startswith(os.path.normpath(pdf_dir)):
            return jsonify({'error': 'Invalid'}), 400
        if os.path.isfile(safe):
            os.remove(safe)
        return jsonify({'status': 'deleted'})

    # ─── AI Chat File Upload (drag/drop) ──────────────────────────────

    @app.route('/api/ai/upload-context', methods=['POST'])
    def api_ai_upload_context():
        """Upload a file and extract text for AI chat context."""
        if 'file' not in request.files:
            return jsonify({'error': 'No file'}), 400
        file = request.files['file']
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        content = ''
        if ext == 'pdf':
            try:
                import PyPDF2
                reader = PyPDF2.PdfReader(file)
                content = '\n'.join(page.extract_text() or '' for page in reader.pages)
            except Exception as e:
                return jsonify({'error': f'PDF read failed: {e}'}), 400
        elif ext in ('txt', 'md', 'csv', 'log', 'json', 'xml', 'html'):
            content = file.read().decode('utf-8', errors='ignore')
        else:
            return jsonify({'error': f'Unsupported file type: {ext}'}), 400
        # Truncate to ~4000 words to fit in context
        words = content.split()
        if len(words) > 4000:
            content = ' '.join(words[:4000]) + '\n\n[... truncated, file too large for full context ...]'
        return jsonify({'filename': filename, 'content': content, 'words': len(words)})

    # ─── Comms Log API ─────────────────────────────────────────────────

    @app.route('/api/comms-log')
    def api_comms_log_list():
        db = get_db()
        rows = db.execute('SELECT * FROM comms_log ORDER BY created_at DESC LIMIT 200').fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/comms-log', methods=['POST'])
    def api_comms_log_create():
        data = request.get_json() or {}
        db = get_db()
        cur = db.execute('INSERT INTO comms_log (freq, callsign, direction, message, signal_quality) VALUES (?, ?, ?, ?, ?)',
                         (data.get('freq', ''), data.get('callsign', ''), data.get('direction', 'rx'),
                          data.get('message', ''), data.get('signal_quality', '')))
        db.commit()
        row = db.execute('SELECT * FROM comms_log WHERE id = ?', (cur.lastrowid,)).fetchone()
        db.close()
        return jsonify(dict(row)), 201

    @app.route('/api/comms-log/<int:lid>', methods=['DELETE'])
    def api_comms_log_delete(lid):
        db = get_db()
        db.execute('DELETE FROM comms_log WHERE id = ?', (lid,))
        db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    # ─── Drill History API ────────────────────────────────────────────

    @app.route('/api/drills/history')
    def api_drill_history():
        db = get_db()
        rows = db.execute('SELECT * FROM drill_history ORDER BY created_at DESC LIMIT 50').fetchall()
        db.close()
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

    @app.route('/api/inventory/shopping-list')
    def api_shopping_list():
        db = get_db()
        from datetime import datetime, timedelta
        today = datetime.now().strftime('%Y-%m-%d')
        soon = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

        # Low stock items — need to restock
        low = db.execute('SELECT name, quantity, unit, min_quantity, category FROM inventory WHERE quantity <= min_quantity AND min_quantity > 0').fetchall()
        low_items = [{'name': r['name'], 'need': round(r['min_quantity'] - r['quantity'], 1), 'unit': r['unit'],
                      'category': r['category'], 'reason': 'below minimum'} for r in low]

        # Expiring items — need replacement
        expiring = db.execute("SELECT name, unit, category, expiration FROM inventory WHERE expiration != '' AND expiration <= ?", (soon,)).fetchall()
        exp_items = [{'name': r['name'], 'need': 1, 'unit': r['unit'], 'category': r['category'],
                      'reason': f'expires {r["expiration"]}'} for r in expiring]

        # Critical burn rate — running out within 14 days
        burn = db.execute("SELECT name, quantity, daily_usage, unit, category FROM inventory WHERE daily_usage > 0 AND (quantity / daily_usage) < 14").fetchall()
        burn_items = [{'name': r['name'], 'need': round(r['daily_usage'] * 30 - r['quantity'], 1), 'unit': r['unit'],
                       'category': r['category'], 'reason': f'{round(r["quantity"]/r["daily_usage"],1)} days left'}
                      for r in burn if r['daily_usage'] * 30 > r['quantity']]

        db.close()

        # Deduplicate by name
        seen = set()
        all_items = []
        for item in low_items + exp_items + burn_items:
            if item['name'] not in seen:
                seen.add(item['name'])
                all_items.append(item)

        return jsonify(sorted(all_items, key=lambda x: x['category']))

    # ─── Inventory Upgrades (v5.0 Phase 3) ──────────────────────────

    @app.route('/api/inventory/shopping-list/save', methods=['POST'])
    def api_shopping_list_save():
        """Save current shopping list snapshot."""
        db = get_db()
        try:
            rows = db.execute(
                'SELECT id, name, category, quantity, min_quantity, unit FROM inventory WHERE min_quantity > 0 AND quantity < min_quantity'
            ).fetchall()
            for r in rows:
                needed = round(r['min_quantity'] - r['quantity'], 2)
                db.execute(
                    'INSERT OR IGNORE INTO shopping_list (name, category, quantity_needed, unit, inventory_id) VALUES (?, ?, ?, ?, ?)',
                    (r['name'], r['category'], needed, r['unit'], r['id'])
                )
            db.commit()
            return jsonify({'status': 'ok', 'count': len(rows)})
        finally:
            db.close()

    @app.route('/api/inventory/<int:item_id>/checkout', methods=['POST'])
    def api_inventory_checkout(item_id):
        """Check out an inventory item to a person."""
        d = request.json or {}
        person = d.get('person', '').strip()
        qty = d.get('quantity', 1)
        reason = d.get('reason', '')
        if not person:
            return jsonify({'error': 'person required'}), 400
        db = get_db()
        try:
            db.execute(
                'INSERT INTO inventory_checkouts (inventory_id, checked_out_to, quantity, reason) VALUES (?, ?, ?, ?)',
                (item_id, person, qty, reason)
            )
            db.execute('UPDATE inventory SET checked_out_to = ? WHERE id = ?', (person, item_id))
            db.commit()
            log_activity('checkout', detail=f'{person} checked out item #{item_id}')
            return jsonify({'status': 'ok'})
        finally:
            db.close()

    @app.route('/api/inventory/<int:item_id>/checkin', methods=['POST'])
    def api_inventory_checkin(item_id):
        """Return a checked-out inventory item."""
        db = get_db()
        try:
            db.execute(
                "UPDATE inventory_checkouts SET returned_at = CURRENT_TIMESTAMP WHERE inventory_id = ? AND returned_at IS NULL",
                (item_id,)
            )
            db.execute("UPDATE inventory SET checked_out_to = '' WHERE id = ?", (item_id,))
            db.commit()
            log_activity('checkin', detail=f'Item #{item_id} returned')
            return jsonify({'status': 'ok'})
        finally:
            db.close()

    @app.route('/api/inventory/checkouts')
    def api_inventory_checkouts():
        """List all currently checked-out items."""
        db = get_db()
        try:
            rows = db.execute(
                '''SELECT c.*, i.name as item_name, i.category
                   FROM inventory_checkouts c
                   JOIN inventory i ON c.inventory_id = i.id
                   WHERE c.returned_at IS NULL
                   ORDER BY c.checked_out_at DESC'''
            ).fetchall()
            return jsonify([dict(r) for r in rows])
        finally:
            db.close()

    @app.route('/api/inventory/<int:item_id>/photos', methods=['GET'])
    def api_inventory_photos(item_id):
        """List photos for an inventory item."""
        db = get_db()
        try:
            rows = db.execute('SELECT * FROM inventory_photos WHERE inventory_id = ? ORDER BY created_at DESC', (item_id,)).fetchall()
            return jsonify([dict(r) for r in rows])
        finally:
            db.close()

    @app.route('/api/inventory/<int:item_id>/photos', methods=['POST'])
    def api_inventory_photo_upload(item_id):
        """Upload a photo for an inventory item."""
        if 'photo' not in request.files:
            return jsonify({'error': 'No photo provided'}), 400
        photo = request.files['photo']
        if not photo.filename:
            return jsonify({'error': 'Empty filename'}), 400

        photos_dir = os.path.join(get_data_dir(), 'photos', 'inventory')
        os.makedirs(photos_dir, exist_ok=True)
        filename = f'{item_id}_{int(time.time())}_{secure_filename(photo.filename)}'
        filepath = os.path.join(photos_dir, filename)
        photo.save(filepath)

        db = get_db()
        try:
            caption = request.form.get('caption', '')
            db.execute('INSERT INTO inventory_photos (inventory_id, filename, caption) VALUES (?, ?, ?)',
                       (item_id, filename, caption))
            db.commit()
            return jsonify({'status': 'ok', 'filename': filename})
        finally:
            db.close()

    @app.route('/api/inventory/locations')
    def api_inventory_locations():
        """Get unique inventory locations for filtering."""
        db = get_db()
        try:
            rows = db.execute("SELECT DISTINCT location FROM inventory WHERE location != '' ORDER BY location").fetchall()
            return jsonify([r['location'] for r in rows])
        finally:
            db.close()

    @app.route('/api/inventory/scan/<barcode>')
    def api_inventory_scan(barcode):
        """Look up inventory item by barcode."""
        db = get_db()
        try:
            row = db.execute('SELECT * FROM inventory WHERE barcode = ?', (barcode,)).fetchone()
            if row:
                return jsonify(dict(row))
            return jsonify({'found': False, 'barcode': barcode}), 404
        finally:
            db.close()

    # ─── Inventory Consume (quick daily use) ──────────────────────────

    @app.route('/api/inventory/<int:item_id>/consume', methods=['POST'])
    def api_inventory_consume(item_id):
        """Decrement item by daily_usage or specified amount. Logs consumption."""
        data = request.get_json() or {}
        db = get_db()
        row = db.execute('SELECT * FROM inventory WHERE id = ?', (item_id,)).fetchone()
        if not row:
            db.close()
            return jsonify({'error': 'Not found'}), 404
        amount = data.get('amount', row['daily_usage'] or 1)
        new_qty = max(0, row['quantity'] - amount)
        db.execute('UPDATE inventory SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (new_qty, item_id))
        db.commit()
        log_activity('inventory_consumed', row['name'], f'-{amount} {row["unit"]} (was {row["quantity"]}, now {new_qty})')
        db.close()
        return jsonify({'status': 'consumed', 'name': row['name'], 'consumed': amount, 'remaining': new_qty})

    @app.route('/api/inventory/batch-consume', methods=['POST'])
    def api_inventory_batch_consume():
        """Consume daily usage for all items that have daily_usage set."""
        db = get_db()
        rows = db.execute('SELECT id, name, quantity, daily_usage, unit FROM inventory WHERE daily_usage > 0 AND quantity > 0').fetchall()
        consumed = []
        for r in rows:
            new_qty = max(0, r['quantity'] - r['daily_usage'])
            db.execute('UPDATE inventory SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (new_qty, r['id']))
            consumed.append({'name': r['name'], 'used': r['daily_usage'], 'remaining': new_qty, 'unit': r['unit']})
        db.commit()
        if consumed:
            log_activity('daily_consumption', detail=f'Updated {len(consumed)} items')
        db.close()
        return jsonify({'status': 'consumed', 'items': consumed})

    # ─── Comprehensive Status Report ──────────────────────────────────

    @app.route('/api/status-report')
    def api_status_report():
        """Generate a comprehensive status report from all systems."""
        db = get_db()
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

        db.close()

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

    # ─── Daily Journal ─────────────────────────────────────────────────

    @app.route('/api/journal')
    def api_journal_list():
        db = get_db()
        rows = db.execute('SELECT * FROM journal ORDER BY created_at DESC LIMIT 100').fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/journal', methods=['POST'])
    def api_journal_create():
        data = request.get_json() or {}
        entry = data.get('entry', '').strip()
        if not entry:
            return jsonify({'error': 'Entry required'}), 400
        db = get_db()
        db.execute('INSERT INTO journal (entry, mood, tags) VALUES (?,?,?)',
                   (entry, data.get('mood', ''), data.get('tags', '')))
        db.commit()
        db.close()
        log_activity('journal_entry', detail=entry[:50])
        return jsonify({'status': 'logged'}), 201

    @app.route('/api/journal/<int:jid>', methods=['DELETE'])
    def api_journal_delete(jid):
        db = get_db()
        db.execute('DELETE FROM journal WHERE id = ?', (jid,))
        db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    @app.route('/api/journal/export')
    def api_journal_export():
        """Export journal as a text file."""
        db = get_db()
        entries = [dict(r) for r in db.execute('SELECT * FROM journal ORDER BY created_at ASC').fetchall()]
        db.close()
        md = '# N.O.M.A.D. Daily Journal\n\n'
        for e in entries:
            md += f'## {e["created_at"]}\n'
            if e.get('mood'):
                md += f'Mood: {e["mood"]}\n'
            if e.get('tags'):
                md += f'Tags: {e["tags"]}\n'
            md += f'\n{e["entry"]}\n\n---\n\n'
        return Response(md, mimetype='text/markdown',
                       headers={'Content-Disposition': 'attachment; filename="nomad-journal.md"'})

    # ─── Printable Reports ───────────────────────────────────────────

    @app.route('/api/print/freq-card')
    def api_print_freq_card():
        """Printable pocket frequency reference card."""
        db = get_db()
        freqs = db.execute('SELECT * FROM comms_log ORDER BY created_at DESC LIMIT 20').fetchall()
        contacts = db.execute("SELECT name, callsign, phone FROM contacts WHERE callsign != '' OR phone != '' ORDER BY name").fetchall()
        db.close()
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
        db = get_db()
        patients = db.execute('SELECT * FROM patients ORDER BY name').fetchall()
        db.close()
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

    @app.route('/api/inventory/print')
    def api_inventory_print():
        """Printable inventory list."""
        db = get_db()
        items = db.execute('SELECT * FROM inventory ORDER BY category, name').fetchall()
        db.close()
        now = time.strftime('%Y-%m-%d %H:%M')
        html = f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Inventory Report</title>
<style>body{{font-family:'Segoe UI',sans-serif;padding:15px;font-size:11px;}}
h1{{font-size:16px;border-bottom:2px solid #000;padding-bottom:4px;}}
table{{width:100%;border-collapse:collapse;margin:8px 0;}}th,td{{border:1px solid #999;padding:3px 6px;text-align:left;font-size:10px;}}th{{background:#eee;}}
.warn{{color:#c00;font-weight:700;}}
@media print{{@page{{margin:0.3in;size:letter;}}}}
</style></head><body>
<h1>N.O.M.A.D. Inventory Report — {now}</h1>
<table><thead><tr><th>Name</th><th>Category</th><th>Qty</th><th>Unit</th><th>Min</th><th>Daily Use</th><th>Days Left</th><th>Expires</th><th>Location</th></tr></thead><tbody>'''
        for i in items:
            d = dict(i)
            days = round(d['quantity'] / d['daily_usage'], 1) if d.get('daily_usage') and d['daily_usage'] > 0 else '-'
            low = d['quantity'] <= d['min_quantity'] and d['min_quantity'] > 0 if d.get('min_quantity') else False
            html += f"<tr><td{'class=\"warn\"' if low else ''}>{_esc(d['name'])}</td><td>{_esc(d['category'])}</td><td>{d['quantity']}</td><td>{_esc(d.get('unit',''))}</td><td>{d.get('min_quantity','')}</td><td>{d.get('daily_usage','') or ''}</td><td>{days}</td><td>{d.get('expiration','')}</td><td>{_esc(d.get('location',''))}</td></tr>"
        html += f'</tbody></table><p style="font-size:9px;color:#666;">Generated by N.O.M.A.D. — {now}</p></body></html>'
        return html

    @app.route('/api/contacts/print')
    def api_contacts_print():
        """Printable contacts directory."""
        db = get_db()
        contacts = db.execute('SELECT * FROM contacts ORDER BY name').fetchall()
        db.close()
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

    @app.route('/api/emergency-sheet')
    def api_emergency_sheet():
        """Generate a comprehensive printable emergency reference sheet."""
        db = get_db()
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
        db.close()

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
        db = get_db()
        rows = db.execute('SELECT id, name, items FROM checklists ORDER BY updated_at DESC LIMIT 5').fetchall()
        db.close()
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
        db = get_db()
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

        db.close()

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

    # ─── Weather & Zambretti Prediction ─────────────────────────────────

    @app.route('/api/weather/readings', methods=['GET'])
    def api_weather_readings():
        """Get weather readings history for pressure graph."""
        hours = request.args.get('hours', 48, type=int)
        db = get_db()
        try:
            rows = db.execute(
                "SELECT * FROM weather_readings WHERE created_at >= datetime('now', ? || ' hours') ORDER BY created_at ASC",
                (f'-{min(hours, 168)}',)
            ).fetchall()
            return jsonify([dict(r) for r in rows])
        finally:
            db.close()

    @app.route('/api/weather/readings', methods=['POST'])
    def api_weather_reading_add():
        """Add a weather reading (manual or from sensor)."""
        d = request.json or {}
        db = get_db()
        try:
            db.execute(
                'INSERT INTO weather_readings (source, pressure_hpa, temp_f, humidity, wind_dir, wind_speed_mph) VALUES (?, ?, ?, ?, ?, ?)',
                (d.get('source', 'manual'), d.get('pressure_hpa'), d.get('temp_f'), d.get('humidity'), d.get('wind_dir', ''), d.get('wind_speed_mph'))
            )
            db.commit()
            # Run Zambretti prediction if we have enough data
            prediction = _zambretti_predict(db)
            if prediction:
                db.execute('UPDATE weather_readings SET prediction = ?, zambretti_code = ? WHERE id = (SELECT MAX(id) FROM weather_readings)',
                           (prediction['forecast'], prediction['code']))
                db.commit()
            return jsonify({'status': 'ok', 'prediction': prediction})
        finally:
            db.close()

    @app.route('/api/weather/predict')
    def api_weather_predict():
        """Get current Zambretti weather prediction."""
        db = get_db()
        try:
            prediction = _zambretti_predict(db)
            return jsonify(prediction or {'forecast': 'Insufficient data', 'trend': 'unknown', 'code': -1})
        finally:
            db.close()

    def _zambretti_predict(db):
        """Zambretti weather forecasting algorithm — pure offline prediction from barometric pressure trend."""
        try:
            rows = db.execute(
                "SELECT pressure_hpa, created_at FROM weather_readings WHERE pressure_hpa IS NOT NULL ORDER BY created_at DESC LIMIT 12"
            ).fetchall()
            if len(rows) < 3:
                return None

            current = rows[0]['pressure_hpa']
            oldest = rows[-1]['pressure_hpa']
            delta = current - oldest  # positive = rising, negative = falling

            # Determine trend
            if delta > 1.5:
                trend = 'rising'
            elif delta < -1.5:
                trend = 'falling'
            else:
                trend = 'steady'

            # Simplified Zambretti algorithm
            # Adjust pressure to sea level equivalent (assume ~0m elevation for now)
            p = current

            import math
            from datetime import datetime
            month = datetime.now().month
            is_winter = month in (11, 12, 1, 2, 3)

            if trend == 'falling':
                # Zambretti falling pressure table (Z = 130 - (p/81))
                z = max(1, min(26, int(130 - (p / 8.1))))
                if is_winter:
                    z = min(26, z + 1)
                forecasts = {
                    range(1, 3): 'Settled fine weather',
                    range(3, 5): 'Fine weather',
                    range(5, 7): 'Fine, becoming less settled',
                    range(7, 9): 'Fairly fine, showery later',
                    range(9, 11): 'Showery, becoming more unsettled',
                    range(11, 13): 'Unsettled, rain later',
                    range(13, 16): 'Rain at times, worse later',
                    range(16, 19): 'Rain at times, becoming very unsettled',
                    range(19, 22): 'Very unsettled, rain',
                    range(22, 27): 'Stormy, much rain',
                }
            elif trend == 'rising':
                z = max(1, min(26, int((p / 8.1) - 115)))
                if is_winter:
                    z = max(1, z - 1)
                forecasts = {
                    range(1, 3): 'Settled fine weather',
                    range(3, 5): 'Fine weather',
                    range(5, 7): 'Becoming fine',
                    range(7, 9): 'Fairly fine, improving',
                    range(9, 11): 'Fairly fine, possible showers early',
                    range(11, 13): 'Showery early, improving',
                    range(13, 16): 'Changeable, mending',
                    range(16, 19): 'Rather unsettled, clearing later',
                    range(19, 22): 'Unsettled, probably improving',
                    range(22, 27): 'Unsettled, short fine intervals',
                }
            else:
                z = max(1, min(26, int(147 - (5 * p / 37.6))))
                forecasts = {
                    range(1, 3): 'Settled fine weather',
                    range(3, 5): 'Fine weather',
                    range(5, 7): 'Fine, possibly showers',
                    range(7, 10): 'Fairly fine, showers likely',
                    range(10, 13): 'Showery, bright intervals',
                    range(13, 16): 'Changeable, some rain',
                    range(16, 19): 'Unsettled, rain at times',
                    range(19, 22): 'Rain at frequent intervals',
                    range(22, 27): 'Very unsettled, rain',
                }

            forecast = 'Unknown'
            for r, text in forecasts.items():
                if z in r:
                    forecast = text
                    break

            return {
                'forecast': forecast,
                'trend': trend,
                'code': z,
                'current_hpa': round(current, 1),
                'delta_hpa': round(delta, 1),
                'readings_count': len(rows),
            }
        except Exception:
            return None

    @app.route('/api/weather/wind-chill')
    def api_wind_chill():
        """Calculate wind chill or heat index."""
        temp_f = request.args.get('temp', type=float)
        wind_mph = request.args.get('wind', type=float)
        humidity = request.args.get('humidity', type=float)
        if temp_f is None:
            return jsonify({'error': 'temp required'}), 400

        result = {'temp_f': temp_f}

        # Wind chill (valid for temp <= 50°F and wind >= 3 mph)
        if wind_mph and temp_f <= 50 and wind_mph >= 3:
            wc = 35.74 + 0.6215 * temp_f - 35.75 * (wind_mph ** 0.16) + 0.4275 * temp_f * (wind_mph ** 0.16)
            result['wind_chill_f'] = round(wc, 1)
            result['index_type'] = 'wind_chill'
        # Heat index (valid for temp >= 80°F)
        elif humidity and temp_f >= 80:
            hi = -42.379 + 2.04901523*temp_f + 10.14333127*humidity - 0.22475541*temp_f*humidity - 6.83783e-3*temp_f**2 - 5.481717e-2*humidity**2 + 1.22874e-3*temp_f**2*humidity + 8.5282e-4*temp_f*humidity**2 - 1.99e-6*temp_f**2*humidity**2
            result['heat_index_f'] = round(hi, 1)
            result['index_type'] = 'heat_index'
        else:
            result['index_type'] = 'none'
            result['feels_like_f'] = temp_f

        return jsonify(result)

    # ─── Weather-Triggered Alerts (v5.0 Phase 9) ────────────────────

    @app.route('/api/weather/check-alerts', methods=['POST'])
    def api_weather_check_alerts():
        """Check weather readings for alert conditions and auto-create alerts."""
        db = get_db()
        try:
            rows = db.execute(
                "SELECT pressure_hpa, temp_f, created_at FROM weather_readings WHERE pressure_hpa IS NOT NULL ORDER BY created_at DESC LIMIT 6"
            ).fetchall()
            alerts_created = []
            if len(rows) >= 3:
                newest = rows[0]['pressure_hpa']
                oldest = rows[-1]['pressure_hpa']
                delta = newest - oldest
                # Rapid pressure drop (>4 hPa in ~3 hours = storm warning)
                if delta < -4:
                    db.execute(
                        "INSERT INTO alerts (alert_type, severity, title, message, data) VALUES (?, ?, ?, ?, ?)",
                        ('weather', 'critical', 'Rapid Pressure Drop', f'Barometric pressure dropped {abs(round(delta,1))} hPa — storm likely imminent', json.dumps({'delta': delta, 'current': newest}))
                    )
                    alerts_created.append('rapid_pressure_drop')
                elif delta < -2:
                    db.execute(
                        "INSERT INTO alerts (alert_type, severity, title, message, data) VALUES (?, ?, ?, ?, ?)",
                        ('weather', 'warning', 'Pressure Falling', f'Barometric pressure dropped {abs(round(delta,1))} hPa — weather deteriorating', json.dumps({'delta': delta, 'current': newest}))
                    )
                    alerts_created.append('pressure_falling')
            # Temperature extremes
            if rows:
                temp = rows[0].get('temp_f')
                if temp is not None:
                    if temp >= 105:
                        db.execute("INSERT INTO alerts (alert_type, severity, title, message) VALUES ('weather', 'critical', 'Extreme Heat', ?)", (f'Temperature: {temp}°F — heat stroke danger',))
                        alerts_created.append('extreme_heat')
                    elif temp <= 10:
                        db.execute("INSERT INTO alerts (alert_type, severity, title, message) VALUES ('weather', 'critical', 'Extreme Cold', ?)", (f'Temperature: {temp}°F — hypothermia/frostbite danger',))
                        alerts_created.append('extreme_cold')
            db.commit()
            return jsonify({'alerts_created': alerts_created})
        finally:
            db.close()

    @app.route('/api/weather/history')
    def api_weather_history():
        """Get pressure history for graphing."""
        hours = request.args.get('hours', 48, type=int)
        db = get_db()
        try:
            rows = db.execute(
                "SELECT pressure_hpa, temp_f, humidity, wind_dir, wind_speed_mph, created_at FROM weather_readings WHERE created_at >= datetime('now', ? || ' hours') ORDER BY created_at ASC",
                (f'-{min(hours, 168)}',)
            ).fetchall()
            return jsonify([dict(r) for r in rows])
        finally:
            db.close()

    # ─── KB Folder Watch (v5.0 Phase 1) ─────────────────────────────

    @app.route('/api/kb/workspaces', methods=['GET'])
    def api_kb_workspaces():
        """List knowledge base workspaces."""
        db = get_db()
        try:
            rows = db.execute('SELECT * FROM kb_workspaces ORDER BY name').fetchall()
            return jsonify([dict(r) for r in rows])
        finally:
            db.close()

    @app.route('/api/kb/workspaces', methods=['POST'])
    def api_kb_workspace_create():
        """Create a KB workspace."""
        d = request.json or {}
        name = d.get('name', '').strip()
        if not name:
            return jsonify({'error': 'name required'}), 400
        db = get_db()
        try:
            db.execute(
                'INSERT INTO kb_workspaces (name, description, watch_folder, auto_index) VALUES (?, ?, ?, ?)',
                (name, d.get('description', ''), d.get('watch_folder', ''), d.get('auto_index', 0))
            )
            db.commit()
            wid = db.execute('SELECT last_insert_rowid()').fetchone()[0]
            return jsonify({'id': wid, 'status': 'ok'})
        finally:
            db.close()

    @app.route('/api/kb/workspaces/<int:wid>', methods=['DELETE'])
    def api_kb_workspace_delete(wid):
        """Delete a KB workspace."""
        db = get_db()
        try:
            db.execute('DELETE FROM kb_workspaces WHERE id = ?', (wid,))
            db.commit()
            return jsonify({'status': 'ok'})
        finally:
            db.close()

    @app.route('/api/ai/model-info/<model_name>')
    def api_ai_model_info(model_name):
        """Get detailed model info for model cards."""
        try:
            import requests as _req
            r = _req.get(f'http://localhost:11434/api/show', json={'name': model_name}, timeout=5)
            if r.ok:
                data = r.json()
                details = data.get('details', {})
                model_info = data.get('model_info', {})
                # Extract key metrics
                params = details.get('parameter_size', 'Unknown')
                quant = details.get('quantization_level', 'Unknown')
                family = details.get('family', 'Unknown')
                fmt = details.get('format', '')
                # Estimate RAM from parameter count
                param_num = 0
                if isinstance(params, str):
                    p = params.lower().replace('b', '').replace(' ', '')
                    try:
                        param_num = float(p)
                    except Exception:
                        pass
                ram_est = f'~{max(1, round(param_num * 0.6))} GB' if param_num > 0 else 'Unknown'
                return jsonify({
                    'name': model_name,
                    'parameters': params,
                    'quantization': quant,
                    'family': family,
                    'format': fmt,
                    'ram_estimate': ram_est,
                    'size_bytes': model_info.get('general.file_size', 0),
                })
            return jsonify({'name': model_name, 'error': 'Could not fetch model info'}), 404
        except Exception as e:
            return jsonify({'name': model_name, 'error': str(e)}), 500

    # ─── Notes Attachments (v5.0 Phase 5) ───────────────────────────

    @app.route('/api/notes/<int:note_id>/attachments', methods=['GET'])
    def api_note_attachments(note_id):
        """List attachments for a note."""
        att_dir = os.path.join(get_data_dir(), 'attachments', 'notes', str(note_id))
        if not os.path.isdir(att_dir):
            return jsonify([])
        files = []
        for f in os.listdir(att_dir):
            fp = os.path.join(att_dir, f)
            files.append({'filename': f, 'size': os.path.getsize(fp), 'path': f'/api/notes/{note_id}/attachments/{f}'})
        return jsonify(files)

    @app.route('/api/notes/<int:note_id>/attachments/<filename>')
    def api_note_attachment_serve(note_id, filename):
        """Serve a note attachment file."""
        safe = secure_filename(filename)
        att_dir = os.path.join(get_data_dir(), 'attachments', 'notes', str(note_id))
        full = os.path.join(att_dir, safe)
        if not os.path.normpath(full).startswith(os.path.normpath(att_dir)):
            return jsonify({'error': 'Invalid path'}), 400
        if not os.path.isfile(full):
            return jsonify({'error': 'Not found'}), 404
        from flask import send_file
        return send_file(full)

    @app.route('/api/notes/<int:note_id>/attachments', methods=['POST'])
    def api_note_attachment_upload(note_id):
        """Upload an attachment for a note."""
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        f = request.files['file']
        if not f.filename:
            return jsonify({'error': 'Empty filename'}), 400
        att_dir = os.path.join(get_data_dir(), 'attachments', 'notes', str(note_id))
        os.makedirs(att_dir, exist_ok=True)
        safe = secure_filename(f.filename)
        f.save(os.path.join(att_dir, safe))
        return jsonify({'status': 'ok', 'filename': safe, 'path': f'/api/notes/{note_id}/attachments/{safe}'})

    # ─── Media Metadata Editor (v5.0 Phase 6) ───────────────────────

    @app.route('/api/media/<media_type>/<int:media_id>/metadata', methods=['PUT'])
    def api_media_metadata_update(media_type, media_id):
        """Update metadata for a media item."""
        table_map = {'video': 'videos', 'audio': 'audio', 'book': 'books'}
        table = table_map.get(media_type)
        if not table:
            return jsonify({'error': 'Invalid media type'}), 400
        d = request.json or {}
        allowed = {'title', 'category', 'notes', 'description'}
        if media_type == 'audio':
            allowed.update({'artist', 'album'})
        if media_type == 'book':
            allowed.update({'author', 'description'})
        updates = []
        params = []
        for k, v in d.items():
            if k in allowed:
                updates.append(f'{k} = ?')
                params.append(v)
        if not updates:
            return jsonify({'error': 'No valid fields'}), 400
        params.append(media_id)
        db = get_db()
        try:
            db.execute(f'UPDATE {table} SET {", ".join(updates)} WHERE id = ?', params)
            db.commit()
            return jsonify({'status': 'ok'})
        finally:
            db.close()

    # ─── Vital Signs Trending (v5.0 Phase 7) ────────────────────────

    @app.route('/api/medical/vitals-trend/<int:patient_id>')
    def api_vitals_trend(patient_id):
        """Get vital signs history for trending chart."""
        limit = request.args.get('limit', 50, type=int)
        db = get_db()
        try:
            rows = db.execute(
                'SELECT bp_systolic, bp_diastolic, pulse, resp_rate, temp_f, spo2, pain_level, gcs, created_at FROM vitals_log WHERE patient_id = ? ORDER BY created_at DESC LIMIT ?',
                (patient_id, limit)
            ).fetchall()
            return jsonify(list(reversed([dict(r) for r in rows])))
        finally:
            db.close()

    # ─── Medication Expiry Cross-Reference (v5.0 Phase 7) ───────────

    @app.route('/api/medical/expiring-meds')
    def api_expiring_meds():
        """Cross-reference medication inventory with expiry dates."""
        from datetime import datetime, timedelta
        db = get_db()
        try:
            soon = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
            rows = db.execute(
                "SELECT id, name, quantity, unit, expiration, category FROM inventory WHERE LOWER(category) IN ('medical', 'first aid', 'medicine', 'medications') AND expiration != '' AND expiration <= ? ORDER BY expiration ASC",
                (soon,)
            ).fetchall()
            today = datetime.now().strftime('%Y-%m-%d')
            result = []
            for r in rows:
                item = dict(r)
                item['expired'] = r['expiration'] < today
                item['days_until'] = (datetime.strptime(r['expiration'], '%Y-%m-%d') - datetime.now()).days if r['expiration'] else None
                result.append(item)
            return jsonify(result)
        finally:
            db.close()

    # ─── Network Throughput Benchmark (v5.0 Phase 12) ────────────────

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
        db = get_db()
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
        result = []
        total = 0
        for tname, label in tables:
            try:
                c = db.execute(f'SELECT COUNT(*) as c FROM {tname}').fetchone()['c']
                if c > 0:
                    result.append({'table': tname, 'label': label, 'count': c})
                total += c
            except Exception:
                pass
        db.close()
        return jsonify({'tables': result, 'total_records': total})

    # ─── Expanded Unified Search ──────────────────────────────────────

    @app.route('/api/search/all')
    def api_search_all():
        """Extended search across all data types."""
        q = request.args.get('q', '').strip()
        if not q:
            return jsonify({'conversations': [], 'notes': [], 'documents': [], 'inventory': [], 'contacts': [], 'checklists': []})
        db = get_db()
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
        db.close()
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

    @app.route('/api/system/health')
    def api_system_health():
        """Comprehensive health check — DB status, data coverage, service availability."""
        db = get_db()
        try:
            health = {'status': 'operational', 'issues': [], 'coverage': {}}

            # Data coverage — what has the user set up?
            checks = [
                ('inventory', 'SELECT COUNT(*) as c FROM inventory', 'Supplies logged'),
                ('contacts', 'SELECT COUNT(*) as c FROM contacts', 'Team contacts'),
                ('patients', 'SELECT COUNT(*) as c FROM patients', 'Medical profiles'),
                ('waypoints', 'SELECT COUNT(*) as c FROM waypoints', 'Map waypoints'),
                ('checklists', 'SELECT COUNT(*) as c FROM checklists', 'Checklists created'),
                ('notes', 'SELECT COUNT(*) as c FROM notes', 'Notes written'),
                ('incidents', 'SELECT COUNT(*) as c FROM incidents', 'Incidents logged'),
                ('videos', 'SELECT COUNT(*) as c FROM videos', 'Training videos'),
                ('audio', 'SELECT COUNT(*) as c FROM audio', 'Audio files'),
                ('books', 'SELECT COUNT(*) as c FROM books', 'Reference books'),
                ('cameras', "SELECT COUNT(*) as c FROM cameras WHERE status = 'active'", 'Security cameras'),
                ('power_log', 'SELECT COUNT(*) as c FROM power_log', 'Power readings'),
                ('garden_plots', 'SELECT COUNT(*) as c FROM garden_plots', 'Garden plots'),
                ('livestock', 'SELECT COUNT(*) as c FROM livestock', 'Livestock tracked'),
                ('fuel_storage', 'SELECT COUNT(*) as c FROM fuel_storage', 'Fuel reserves'),
                ('ammo_inventory', 'SELECT COUNT(*) as c FROM ammo_inventory', 'Ammo inventoried'),
                ('skills', 'SELECT COUNT(*) as c FROM skills', 'Skills assessed'),
                ('community_resources', 'SELECT COUNT(*) as c FROM community_resources', 'Community resources'),
            ]
            total_items = 0
            modules_active = 0
            for key, query, label in checks:
                try:
                    count = db.execute(query).fetchone()['c']
                    health['coverage'][key] = {'count': count, 'label': label, 'active': count > 0}
                    total_items += count
                    if count > 0: modules_active += 1
                except Exception:
                    health['coverage'][key] = {'count': 0, 'label': label, 'active': False}

            # Readiness scoring
            health['modules_active'] = modules_active
            health['modules_total'] = len(checks)
            health['total_data_items'] = total_items
            health['coverage_pct'] = round(modules_active / len(checks) * 100)

            # Critical gaps
            from datetime import datetime, timedelta
            today = datetime.now().strftime('%Y-%m-%d')
            expired = db.execute("SELECT COUNT(*) as c FROM inventory WHERE expiration != '' AND expiration < ?", (today,)).fetchone()['c']
            if expired > 0: health['issues'].append({'type': 'warning', 'msg': f'{expired} items have expired'})
            low = db.execute('SELECT COUNT(*) as c FROM inventory WHERE quantity <= min_quantity AND min_quantity > 0').fetchone()['c']
            if low > 0: health['issues'].append({'type': 'warning', 'msg': f'{low} items are below minimum stock'})
            overdue = db.execute("SELECT COUNT(*) as c FROM equipment_log WHERE next_service != '' AND next_service <= ?", (today,)).fetchone()['c']
            if overdue > 0: health['issues'].append({'type': 'warning', 'msg': f'{overdue} equipment items overdue for service'})
            crit_alerts = db.execute("SELECT COUNT(*) as c FROM alerts WHERE dismissed = 0 AND severity = 'critical'").fetchone()['c']
            if crit_alerts > 0: health['issues'].append({'type': 'critical', 'msg': f'{crit_alerts} unresolved critical alerts'})

            # DB integrity
            try:
                integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
                health['db_integrity'] = integrity
                if integrity != 'ok':
                    health['issues'].append({'type': 'critical', 'msg': f'Database integrity check failed: {integrity}'})
                    health['status'] = 'degraded'
            except Exception:
                health['db_integrity'] = 'unknown'

            if health['issues']:
                health['status'] = 'attention_needed'
            return jsonify(health)
        finally:
            db.close()

    @app.route('/api/system/getting-started')
    def api_getting_started():
        """Returns a guided setup checklist for new users."""
        db = get_db()
        try:
            steps = [
                {'id': 'contacts', 'title': 'Add emergency contacts',
                 'desc': 'Names, phone numbers, callsigns, roles, and skills for your group.',
                 'done': db.execute('SELECT COUNT(*) as c FROM contacts').fetchone()['c'] > 0,
                 'action': 'preparedness', 'sub': 'contacts'},
                {'id': 'inventory', 'title': 'Log your supply inventory',
                 'desc': 'Food, water, medical supplies, tools — with quantities and expiration dates.',
                 'done': db.execute('SELECT COUNT(*) as c FROM inventory').fetchone()['c'] > 0,
                 'action': 'preparedness', 'sub': 'inventory'},
                {'id': 'medical', 'title': 'Create medical profiles',
                 'desc': 'Allergies, medications, blood types, and conditions for each family member.',
                 'done': db.execute('SELECT COUNT(*) as c FROM patients').fetchone()['c'] > 0,
                 'action': 'preparedness', 'sub': 'medical'},
                {'id': 'waypoints', 'title': 'Set up map waypoints',
                 'desc': 'Mark your home, rally points, water sources, caches, and bug-out routes.',
                 'done': db.execute('SELECT COUNT(*) as c FROM waypoints').fetchone()['c'] > 0,
                 'action': 'maps', 'sub': None},
                {'id': 'checklists', 'title': 'Create preparedness checklists',
                 'desc': 'Bug-out bag, shelter-in-place, 72-hour kit, vehicle emergency.',
                 'done': db.execute('SELECT COUNT(*) as c FROM checklists').fetchone()['c'] > 0,
                 'action': 'preparedness', 'sub': 'checklists'},
                {'id': 'ai', 'title': 'Install AI assistant',
                 'desc': 'Download an AI model for offline situation analysis and decision support.',
                 'done': ollama.is_installed(),
                 'action': 'services', 'sub': None},
                {'id': 'media', 'title': 'Download survival reference content',
                 'desc': 'Videos, audio training, reference books — all available offline.',
                 'done': db.execute('SELECT COUNT(*) as c FROM videos').fetchone()['c'] > 0 or db.execute('SELECT COUNT(*) as c FROM books').fetchone()['c'] > 0,
                 'action': 'media', 'sub': None},
                {'id': 'family', 'title': 'Set up your family emergency plan',
                 'desc': 'Meeting points, communication plan, roles, and responsibilities.',
                 'done': db.execute('SELECT COUNT(*) as c FROM checklists WHERE name LIKE ?', ('%family%',)).fetchone()['c'] > 0,
                 'action': 'preparedness', 'sub': 'family'},
            ]
            completed = sum(1 for s in steps if s['done'])
            return jsonify({'steps': steps, 'completed': completed, 'total': len(steps), 'pct': round(completed / len(steps) * 100)})
        finally:
            db.close()

    # ─── NukeMap ──────────────────────────────────────────────────────

    # Resolve nukemap directory — try multiple paths for robustness
    _nukemap_candidates = []
    if getattr(sys, 'frozen', False):
        _nukemap_candidates.append(os.path.join(sys._MEIPASS, 'web', 'nukemap'))
    _nukemap_candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nukemap'))
    _nukemap_candidates.append(os.path.join(os.getcwd(), 'web', 'nukemap'))

    _nukemap_dir = None
    for candidate in _nukemap_candidates:
        if os.path.isdir(candidate) and os.path.isfile(os.path.join(candidate, 'index.html')):
            _nukemap_dir = candidate
            break
    if _nukemap_dir:
        log.info(f'NukeMap directory: {_nukemap_dir}')
    else:
        log.warning(f'NukeMap directory NOT FOUND. Tried: {_nukemap_candidates}')
        _nukemap_dir = _nukemap_candidates[0]  # Use first candidate as fallback

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

    # ─── Skills Tracker ───────────────────────────────────────────────

    @app.route('/api/skills')
    def api_skills_list():
        conn = get_db()
        rows = conn.execute('SELECT * FROM skills ORDER BY category, name').fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/skills', methods=['POST'])
    def api_skills_create():
        d = request.json or {}
        conn = get_db()
        cur = conn.execute(
            'INSERT INTO skills (name, category, proficiency, notes, last_practiced) VALUES (?,?,?,?,?)',
            (d.get('name',''), d.get('category','general'), d.get('proficiency','none'),
             d.get('notes',''), d.get('last_practiced','')))
        conn.commit()
        row = conn.execute('SELECT * FROM skills WHERE id=?', (cur.lastrowid,)).fetchone()
        conn.close()
        return jsonify(dict(row)), 201

    @app.route('/api/skills/<int:sid>', methods=['PUT'])
    def api_skills_update(sid):
        d = request.json or {}
        conn = get_db()
        conn.execute(
            'UPDATE skills SET name=?, category=?, proficiency=?, notes=?, last_practiced=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
            (d.get('name',''), d.get('category','general'), d.get('proficiency','none'),
             d.get('notes',''), d.get('last_practiced',''), sid))
        conn.commit()
        row = conn.execute('SELECT * FROM skills WHERE id=?', (sid,)).fetchone()
        conn.close()
        return jsonify(dict(row) if row else {})

    @app.route('/api/skills/<int:sid>', methods=['DELETE'])
    def api_skills_delete(sid):
        conn = get_db()
        conn.execute('DELETE FROM skills WHERE id=?', (sid,))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})

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
        conn.execute('DELETE FROM ammo_inventory WHERE id=?', (aid,))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})

    @app.route('/api/ammo/summary')
    def api_ammo_summary():
        conn = get_db()
        rows = conn.execute(
            'SELECT caliber, SUM(quantity) as total FROM ammo_inventory GROUP BY caliber ORDER BY total DESC'
        ).fetchall()
        total = conn.execute('SELECT SUM(quantity) FROM ammo_inventory').fetchone()[0] or 0
        conn.close()
        return jsonify({'by_caliber': [dict(r) for r in rows], 'total': total})

    # ─── Community Resource Registry ──────────────────────────────────

    @app.route('/api/community')
    def api_community_list():
        conn = get_db()
        rows = conn.execute('SELECT * FROM community_resources ORDER BY trust_level DESC, name').fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/community', methods=['POST'])
    def api_community_create():
        d = request.json or {}
        conn = get_db()
        import json as _json
        cur = conn.execute(
            'INSERT INTO community_resources (name, distance_mi, skills, equipment, contact, notes, trust_level) VALUES (?,?,?,?,?,?,?)',
            (d.get('name',''), float(d.get('distance_mi',0)),
             _json.dumps(d.get('skills',[])), _json.dumps(d.get('equipment',[])),
             d.get('contact',''), d.get('notes',''), d.get('trust_level','unknown')))
        conn.commit()
        row = conn.execute('SELECT * FROM community_resources WHERE id=?', (cur.lastrowid,)).fetchone()
        conn.close()
        return jsonify(dict(row)), 201

    @app.route('/api/community/<int:cid>', methods=['PUT'])
    def api_community_update(cid):
        d = request.json or {}
        import json as _json
        conn = get_db()
        conn.execute(
            'UPDATE community_resources SET name=?, distance_mi=?, skills=?, equipment=?, contact=?, notes=?, trust_level=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
            (d.get('name',''), float(d.get('distance_mi',0)),
             _json.dumps(d.get('skills',[])), _json.dumps(d.get('equipment',[])),
             d.get('contact',''), d.get('notes',''), d.get('trust_level','unknown'), cid))
        conn.commit()
        row = conn.execute('SELECT * FROM community_resources WHERE id=?', (cid,)).fetchone()
        conn.close()
        return jsonify(dict(row) if row else {})

    @app.route('/api/community/<int:cid>', methods=['DELETE'])
    def api_community_delete(cid):
        conn = get_db()
        conn.execute('DELETE FROM community_resources WHERE id=?', (cid,))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})

    # ─── Radiation Dose Log ───────────────────────────────────────────

    @app.route('/api/radiation')
    def api_radiation_list():
        conn = get_db()
        rows = conn.execute('SELECT * FROM radiation_log ORDER BY created_at DESC LIMIT 200').fetchall()
        total = conn.execute('SELECT COALESCE(MAX(cumulative_rem), 0) FROM radiation_log').fetchone()[0] or 0
        conn.close()
        return jsonify({'readings': [dict(r) for r in rows], 'total_rem': round(total, 4)})

    @app.route('/api/radiation', methods=['POST'])
    def api_radiation_create():
        d = request.json or {}
        try:
            new_rate = float(d.get('dose_rate_rem', 0))
        except (ValueError, TypeError):
            new_rate = 0.0
        conn = get_db()
        try:
            last = conn.execute('SELECT cumulative_rem FROM radiation_log ORDER BY created_at DESC LIMIT 1').fetchone()
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
        conn.execute('DELETE FROM radiation_log')
        conn.commit()
        conn.close()
        return jsonify({'ok': True})

    # ─── Fuel Storage ─────────────────────────────────────────────────

    @app.route('/api/fuel')
    def api_fuel_list():
        conn = get_db()
        rows = conn.execute('SELECT * FROM fuel_storage ORDER BY fuel_type, created_at DESC').fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/fuel', methods=['POST'])
    def api_fuel_create():
        d = request.json or {}
        try:
            stab = int(d.get('stabilizer_added', 0))
        except (ValueError, TypeError):
            stab = 0
        conn = get_db()
        try:
            cur = conn.execute(
                'INSERT INTO fuel_storage (fuel_type, quantity, unit, container, location, stabilizer_added, date_stored, expires, notes) VALUES (?,?,?,?,?,?,?,?,?)',
                (d.get('fuel_type',''), d.get('quantity',0), d.get('unit','gallons'),
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
        conn = get_db()
        try:
            conn.execute(
                'UPDATE fuel_storage SET fuel_type=?,quantity=?,unit=?,container=?,location=?,stabilizer_added=?,date_stored=?,expires=?,notes=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',
                (d.get('fuel_type',''), d.get('quantity',0), d.get('unit','gallons'),
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
        conn.execute('DELETE FROM fuel_storage WHERE id=?', (fid,))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})

    @app.route('/api/fuel/summary')
    def api_fuel_summary():
        conn = get_db()
        rows = conn.execute('SELECT fuel_type, SUM(quantity) as total, unit FROM fuel_storage GROUP BY fuel_type, unit').fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])

    # ─── Equipment Maintenance ────────────────────────────────────────

    @app.route('/api/equipment')
    def api_equipment_list():
        conn = get_db()
        rows = conn.execute('SELECT * FROM equipment_log ORDER BY status, next_service').fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/equipment', methods=['POST'])
    def api_equipment_create():
        d = request.json or {}
        conn = get_db()
        cur = conn.execute(
            'INSERT INTO equipment_log (name, category, last_service, next_service, service_notes, status, location, notes) VALUES (?,?,?,?,?,?,?,?)',
            (d.get('name',''), d.get('category','general'), d.get('last_service',''),
             d.get('next_service',''), d.get('service_notes',''), d.get('status','operational'),
             d.get('location',''), d.get('notes','')))
        conn.commit()
        row = conn.execute('SELECT * FROM equipment_log WHERE id=?', (cur.lastrowid,)).fetchone()
        conn.close()
        return jsonify(dict(row)), 201

    @app.route('/api/equipment/<int:eid>', methods=['PUT'])
    def api_equipment_update(eid):
        d = request.json or {}
        conn = get_db()
        conn.execute(
            'UPDATE equipment_log SET name=?,category=?,last_service=?,next_service=?,service_notes=?,status=?,location=?,notes=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',
            (d.get('name',''), d.get('category','general'), d.get('last_service',''),
             d.get('next_service',''), d.get('service_notes',''), d.get('status','operational'),
             d.get('location',''), d.get('notes',''), eid))
        conn.commit()
        row = conn.execute('SELECT * FROM equipment_log WHERE id=?', (eid,)).fetchone()
        conn.close()
        return jsonify(dict(row) if row else {})

    @app.route('/api/equipment/<int:eid>', methods=['DELETE'])
    def api_equipment_delete(eid):
        conn = get_db()
        conn.execute('DELETE FROM equipment_log WHERE id=?', (eid,))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})

    # ─── Built-in BitTorrent Client ───────────────────────────────────

    from services.torrent import get_manager as _torrent_mgr, is_available as _torrent_avail

    @app.route('/api/torrent/available')
    def api_torrent_available():
        return jsonify({'available': _torrent_avail()})

    @app.route('/api/torrent/add', methods=['POST'])
    def api_torrent_add():
        d = request.json or {}
        magnet = (d.get('magnet') or '').strip()
        name = d.get('name', '')
        torrent_id = d.get('torrent_id', '')
        if not magnet.startswith('magnet:'):
            return jsonify({'error': 'Invalid magnet link'}), 400
        try:
            h = _torrent_mgr().add_magnet(magnet, name, torrent_id)
            return jsonify({'hash': h})
        except RuntimeError as e:
            return jsonify({'error': str(e), 'unavailable': True}), 503
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/torrent/status')
    def api_torrent_status_all():
        try:
            return jsonify(_torrent_mgr().get_all_status())
        except Exception:
            return jsonify([])

    @app.route('/api/torrent/status/<ih>')
    def api_torrent_status_one(ih):
        try:
            return jsonify(_torrent_mgr().get_status(ih))
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/torrent/pause/<ih>', methods=['POST'])
    def api_torrent_pause(ih):
        _torrent_mgr().pause(ih)
        return jsonify({'ok': True})

    @app.route('/api/torrent/resume/<ih>', methods=['POST'])
    def api_torrent_resume(ih):
        _torrent_mgr().resume(ih)
        return jsonify({'ok': True})

    @app.route('/api/torrent/remove/<ih>', methods=['DELETE'])
    def api_torrent_remove(ih):
        delete_files = request.args.get('delete_files', 'false').lower() == 'true'
        _torrent_mgr().remove(ih, delete_files)
        return jsonify({'ok': True})

    @app.route('/api/torrent/open-folder/<ih>', methods=['POST'])
    def api_torrent_open_folder(ih):
        try:
            _torrent_mgr().open_save_folder(ih)
            return jsonify({'ok': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/torrent/dir')
    def api_torrent_dir():
        d = os.path.join(get_data_dir(), 'torrents')
        return jsonify({'path': d})

    # ─── Unified Download Queue ──────────────────────────────────────

    @app.route('/api/downloads/active')
    def api_downloads_active():
        """Return ALL active downloads across all services in one view."""
        from services.manager import _download_progress
        downloads = []
        for key, prog in dict(_download_progress).items():
            if prog.get('status') in ('downloading', 'extracting'):
                # Classify download type
                if key.startswith('kiwix-zim-'):
                    dtype = 'content'
                    label = key.replace('kiwix-zim-', '').replace('.zim', '')
                elif key.startswith('map-'):
                    dtype = 'map'
                    label = key.replace('map-', '')
                elif key in SERVICE_MODULES:
                    dtype = 'service'
                    label = SVC_FRIENDLY.get(key, key)
                else:
                    dtype = 'other'
                    label = key
                downloads.append({
                    'id': key,
                    'type': dtype,
                    'label': label,
                    'percent': prog.get('percent', 0),
                    'speed': prog.get('speed', ''),
                    'status': prog.get('status', 'unknown'),
                    'downloaded': prog.get('downloaded', 0),
                    'total': prog.get('total', 0),
                    'error': prog.get('error'),
                })

        # Also check Ollama model pull progress
        if ollama.running():
            try:
                pull = ollama.get_pull_progress()
                if pull.get('status') in ('downloading', 'pulling'):
                    downloads.append({
                        'id': 'model-pull',
                        'type': 'model',
                        'label': pull.get('model', 'AI Model'),
                        'percent': pull.get('percent', 0),
                        'speed': '',
                        'status': pull.get('status', 'downloading'),
                        'downloaded': 0,
                        'total': 0,
                        'error': None,
                    })
            except Exception:
                pass

        return jsonify(downloads)

    # ─── Service Process Logs ─────────────────────────────────────────

    @app.route('/api/services/<service_id>/logs')
    def api_service_logs(service_id):
        """Return captured stdout/stderr log lines for a service."""
        from services.manager import _service_logs
        lines = _service_logs.get(service_id, [])
        tail = request.args.get('tail', 100, type=int)
        return jsonify({'service': service_id, 'lines': lines[-tail:]})

    @app.route('/api/services/logs/all')
    def api_service_logs_all():
        """Return log line counts for all services."""
        from services.manager import _service_logs
        return jsonify({sid: len(lines) for sid, lines in _service_logs.items()})

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

    _update_state = {'status': 'idle', 'progress': 0, 'error': None, 'path': None}

    @app.route('/api/update-download', methods=['POST'])
    def api_update_download():
        """Download the latest release from GitHub."""
        def do_update():
            global _update_state
            _update_state = {'status': 'checking', 'progress': 0, 'error': None, 'path': None}
            try:
                import requests as rq
                resp = rq.get('https://api.github.com/repos/SysAdminDoc/project-nomad-desktop/releases/latest', timeout=15)
                if not resp.ok:
                    _update_state = {'status': 'error', 'progress': 0, 'error': 'Cannot reach GitHub', 'path': None}
                    return
                data = resp.json()
                assets = data.get('assets', [])

                # Find the right asset for this platform
                plat = sys.platform
                arch = platform.machine().lower()
                asset = None
                for a in assets:
                    name = a['name'].lower()
                    if plat == 'win32' and ('windows' in name or name.endswith('.exe') or name.endswith('.msi')):
                        asset = a
                        break
                    elif plat == 'linux' and ('linux' in name or name.endswith('.appimage') or name.endswith('.deb')):
                        asset = a
                        break
                    elif plat == 'darwin' and ('macos' in name or 'darwin' in name or name.endswith('.dmg')):
                        asset = a
                        break
                # Fallback: first asset
                if not asset and assets:
                    asset = assets[0]
                if not asset:
                    _update_state = {'status': 'error', 'progress': 0, 'error': 'No download found for your platform', 'path': None}
                    return

                _update_state['status'] = 'downloading'
                url = asset['browser_download_url']
                fname = asset['name']
                import tempfile
                dest = os.path.join(tempfile.gettempdir(), 'nomad-update', fname)
                os.makedirs(os.path.dirname(dest), exist_ok=True)

                dl_resp = rq.get(url, stream=True, timeout=30)
                dl_resp.raise_for_status()
                total = int(dl_resp.headers.get('content-length', 0))
                downloaded = 0
                with open(dest, 'wb') as f:
                    for chunk in dl_resp.iter_content(65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        _update_state['progress'] = int(downloaded / total * 100) if total > 0 else 0

                _update_state = {'status': 'complete', 'progress': 100, 'error': None, 'path': dest}
                log_activity('update_downloaded', detail=f'{data.get("tag_name", "?")} → {fname}')

            except Exception as e:
                _update_state = {'status': 'error', 'progress': 0, 'error': str(e), 'path': None}

        threading.Thread(target=do_update, daemon=True).start()
        return jsonify({'status': 'started'})

    @app.route('/api/update-download/status')
    def api_update_download_status():
        return jsonify(_update_state)

    @app.route('/api/update-download/open', methods=['POST'])
    def api_update_download_open():
        """Open the downloaded update file."""
        path = _update_state.get('path')
        if not path or not os.path.isfile(path):
            return jsonify({'error': 'No update downloaded'}), 404
        from platform_utils import open_folder
        open_folder(os.path.dirname(path))
        return jsonify({'status': 'opened', 'path': path})

    # ─── Task Scheduler Engine (Phase 15) ───────────────────────────

    @app.route('/api/tasks')
    def api_tasks_list():
        db = get_db()
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
        query += ' ORDER BY next_due ASC'
        rows = db.execute(query, params).fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/tasks', methods=['POST'])
    def api_tasks_create():
        data = request.get_json() or {}
        if not data.get('name'):
            return jsonify({'error': 'name is required'}), 400
        db = get_db()
        cur = db.execute(
            'INSERT INTO scheduled_tasks (name, category, recurrence, next_due, assigned_to, notes) VALUES (?, ?, ?, ?, ?, ?)',
            (data.get('name', ''), data.get('category', 'custom'), data.get('recurrence', 'once'),
             data.get('next_due', ''), data.get('assigned_to', ''), data.get('notes', '')))
        db.commit()
        row = db.execute('SELECT * FROM scheduled_tasks WHERE id = ?', (cur.lastrowid,)).fetchone()
        db.close()
        log_activity('task_created', 'scheduler', data.get('name', ''))
        return jsonify(dict(row)), 201

    @app.route('/api/tasks/<int:task_id>', methods=['PUT'])
    def api_tasks_update(task_id):
        data = request.get_json() or {}
        db = get_db()
        allowed = ['name', 'category', 'recurrence', 'next_due', 'assigned_to', 'notes']
        fields = []
        vals = []
        for k in allowed:
            if k in data:
                fields.append(f'{k} = ?')
                vals.append(data[k])
        if not fields:
            return jsonify({'error': 'No fields to update'}), 400
        vals.append(task_id)
        db.execute(f'UPDATE scheduled_tasks SET {", ".join(fields)} WHERE id = ?', vals)
        db.commit()
        row = db.execute('SELECT * FROM scheduled_tasks WHERE id = ?', (task_id,)).fetchone()
        db.close()
        if not row:
            return jsonify({'error': 'Task not found'}), 404
        return jsonify(dict(row))

    @app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
    def api_tasks_delete(task_id):
        db = get_db()
        db.execute('DELETE FROM scheduled_tasks WHERE id = ?', (task_id,))
        db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    @app.route('/api/tasks/<int:task_id>/complete', methods=['POST'])
    def api_tasks_complete(task_id):
        from datetime import datetime, timedelta
        db = get_db()
        row = db.execute('SELECT * FROM scheduled_tasks WHERE id = ?', (task_id,)).fetchone()
        if not row:
            db.close()
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
        db.close()
        log_activity('task_completed', 'scheduler', row['name'])
        return jsonify(dict(updated))

    @app.route('/api/tasks/due')
    def api_tasks_due():
        from datetime import datetime
        db = get_db()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        rows = db.execute(
            'SELECT * FROM scheduled_tasks WHERE next_due IS NOT NULL AND next_due <= ? ORDER BY next_due ASC',
            (now,)).fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

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
        db = get_db()
        alerts = []
        today = datetime.now()
        today_str = today.strftime('%Y-%m-%d')

        # 1. Inventory burn rate — items that will run out
        burn_rows = db.execute('SELECT id, name, category, quantity, unit, daily_usage, expiration FROM inventory WHERE daily_usage > 0').fetchall()
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
        exp_rows = db.execute("SELECT id, name, category, quantity, unit, expiration FROM inventory WHERE expiration != '' AND expiration IS NOT NULL").fetchall()
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
        fuel_rows = db.execute("SELECT id, fuel_type, quantity, unit, expires FROM fuel_storage WHERE expires != '' AND expires IS NOT NULL").fetchall()
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
        equip_rows = db.execute("SELECT id, name, category, next_service, status FROM equipment_log WHERE next_service != '' AND next_service IS NOT NULL").fetchall()
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

        db.close()
        # Sort: critical first, then warning
        alerts.sort(key=lambda a: (0 if a['severity'] == 'critical' else 1, a.get('days_remaining', a.get('days_until_expiry', a.get('days_until_service', 999)))))
        return jsonify({'alerts': alerts, 'count': len(alerts), 'generated_at': today.strftime('%Y-%m-%d %H:%M:%S')})

    # ─── CSV Import Wizard (Phase 17) ─────────────────────────────────

    @app.route('/api/import/csv', methods=['POST'])
    def api_import_csv_preview():
        """Upload CSV, return headers + sample rows for column mapping."""
        import csv
        import io
        if 'file' not in request.files:
            # Try raw body
            raw = request.get_data(as_text=True)
            if not raw:
                return jsonify({'error': 'No CSV file provided'}), 400
        else:
            raw = request.files['file'].read().decode('utf-8', errors='replace')
        reader = csv.reader(io.StringIO(raw))
        rows_data = []
        for i, row in enumerate(reader):
            rows_data.append(row)
            if i >= 10:  # headers + 10 sample rows
                break
        if not rows_data:
            return jsonify({'error': 'CSV is empty'}), 400
        headers = rows_data[0]
        samples = rows_data[1:]
        # Target table columns
        table_columns = {
            'inventory': ['name', 'category', 'quantity', 'unit', 'min_quantity', 'location', 'expiration', 'notes', 'daily_usage', 'barcode', 'cost'],
            'contacts': ['name', 'callsign', 'role', 'skills', 'phone', 'freq', 'email', 'address', 'rally_point', 'blood_type', 'medical_notes', 'notes'],
            'waypoints': ['name', 'lat', 'lng', 'category', 'color', 'icon', 'elevation_m', 'notes'],
            'seeds': ['species', 'variety', 'quantity', 'unit', 'year_harvested', 'source', 'days_to_maturity', 'planting_season', 'notes'],
            'ammo_inventory': ['caliber', 'brand', 'bullet_weight', 'bullet_type', 'quantity', 'location', 'notes'],
            'fuel_storage': ['fuel_type', 'quantity', 'unit', 'container', 'location', 'stabilizer_added', 'date_stored', 'expires', 'notes'],
            'equipment_log': ['name', 'category', 'last_service', 'next_service', 'service_notes', 'status', 'location', 'notes'],
        }
        return jsonify({
            'headers': headers,
            'sample_rows': samples,
            'row_count': len(rows_data) - 1,
            'target_tables': list(table_columns.keys()),
            'table_columns': table_columns,
        })

    @app.route('/api/import/csv/execute', methods=['POST'])
    def api_import_csv_execute():
        """Execute CSV import with column mapping."""
        import csv
        import io
        data = request.get_json() or {}
        csv_data = data.get('csv_data', '')
        mapping = data.get('mapping', {})  # {csv_header: db_column}
        target = data.get('target_table', '')
        allowed_tables = ['inventory', 'contacts', 'waypoints', 'seeds', 'ammo_inventory', 'fuel_storage', 'equipment_log']
        if target not in allowed_tables:
            return jsonify({'error': f'Invalid target table. Must be one of: {", ".join(allowed_tables)}'}), 400
        if not mapping:
            return jsonify({'error': 'Column mapping is required'}), 400
        if not csv_data:
            return jsonify({'error': 'csv_data is required'}), 400

        reader = csv.DictReader(io.StringIO(csv_data))
        db = get_db()
        inserted = 0
        errors = []
        for i, row in enumerate(reader):
            try:
                mapped = {}
                for csv_col, db_col in mapping.items():
                    if csv_col in row and db_col:
                        mapped[db_col] = row[csv_col]
                if not mapped:
                    continue
                cols = ', '.join(mapped.keys())
                placeholders = ', '.join(['?'] * len(mapped))
                db.execute(f'INSERT INTO {target} ({cols}) VALUES ({placeholders})', list(mapped.values()))
                inserted += 1
            except Exception as e:
                errors.append(f'Row {i + 1}: {str(e)}')
        db.commit()
        db.close()
        log_activity('csv_import', 'import', f'{inserted} rows into {target}')
        return jsonify({'status': 'complete', 'inserted': inserted, 'errors': errors, 'target_table': target})

    # ─── Template Quick Entry (Phase 17) ──────────────────────────────

    _INVENTORY_TEMPLATES = {
        '72-hour-kit': {
            'name': '72-Hour Kit',
            'description': 'Essential supplies for 72 hours of self-sufficiency',
            'items': [
                {'name': 'Water (1L bottles)', 'category': 'water', 'quantity': 9, 'unit': 'bottles'},
                {'name': 'Water purification tablets', 'category': 'water', 'quantity': 1, 'unit': 'pack'},
                {'name': 'MRE - Beef Stew', 'category': 'food', 'quantity': 3, 'unit': 'ea'},
                {'name': 'MRE - Chicken Noodle', 'category': 'food', 'quantity': 3, 'unit': 'ea'},
                {'name': 'Energy bars', 'category': 'food', 'quantity': 6, 'unit': 'ea'},
                {'name': 'Trail mix', 'category': 'food', 'quantity': 3, 'unit': 'bags'},
                {'name': 'First aid kit (compact)', 'category': 'medical', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Flashlight (LED)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
                {'name': 'AA Batteries', 'category': 'tools', 'quantity': 8, 'unit': 'ea'},
                {'name': 'Emergency blanket (mylar)', 'category': 'shelter', 'quantity': 2, 'unit': 'ea'},
                {'name': 'Poncho (disposable)', 'category': 'shelter', 'quantity': 2, 'unit': 'ea'},
                {'name': 'Duct tape (small roll)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Multi-tool', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Paracord 50ft', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Lighter (BIC)', 'category': 'tools', 'quantity': 2, 'unit': 'ea'},
                {'name': 'Waterproof matches', 'category': 'tools', 'quantity': 1, 'unit': 'box'},
                {'name': 'N95 masks', 'category': 'medical', 'quantity': 4, 'unit': 'ea'},
                {'name': 'Work gloves', 'category': 'tools', 'quantity': 1, 'unit': 'pair'},
                {'name': 'Whistle (emergency)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
                {'name': 'AM/FM radio (hand-crank)', 'category': 'comms', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Cash (small bills)', 'category': 'other', 'quantity': 200, 'unit': 'USD'},
                {'name': 'Document copies (waterproof bag)', 'category': 'other', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Toilet paper (travel roll)', 'category': 'hygiene', 'quantity': 2, 'unit': 'ea'},
                {'name': 'Hand sanitizer', 'category': 'hygiene', 'quantity': 2, 'unit': 'ea'},
                {'name': 'Wet wipes', 'category': 'hygiene', 'quantity': 1, 'unit': 'pack'},
                {'name': 'Garbage bags (heavy duty)', 'category': 'tools', 'quantity': 4, 'unit': 'ea'},
                {'name': 'Zip-lock bags (gallon)', 'category': 'tools', 'quantity': 10, 'unit': 'ea'},
                {'name': 'Notebook + pencil', 'category': 'other', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Local map (paper)', 'category': 'other', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Compass', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
            ],
        },
        'family-30-days': {
            'name': 'Family of 4 - 30 Days',
            'description': 'Extended supply for a family of four',
            'items': [
                {'name': 'Rice (long grain)', 'category': 'food', 'quantity': 50, 'unit': 'lbs'},
                {'name': 'Dried beans (pinto)', 'category': 'food', 'quantity': 25, 'unit': 'lbs'},
                {'name': 'Dried beans (black)', 'category': 'food', 'quantity': 15, 'unit': 'lbs'},
                {'name': 'Oats (rolled)', 'category': 'food', 'quantity': 20, 'unit': 'lbs'},
                {'name': 'Canned vegetables (mixed)', 'category': 'food', 'quantity': 48, 'unit': 'cans'},
                {'name': 'Canned fruit', 'category': 'food', 'quantity': 24, 'unit': 'cans'},
                {'name': 'Canned tuna', 'category': 'food', 'quantity': 24, 'unit': 'cans'},
                {'name': 'Canned chicken', 'category': 'food', 'quantity': 12, 'unit': 'cans'},
                {'name': 'Peanut butter', 'category': 'food', 'quantity': 6, 'unit': 'jars'},
                {'name': 'Honey', 'category': 'food', 'quantity': 3, 'unit': 'lbs'},
                {'name': 'Salt', 'category': 'food', 'quantity': 5, 'unit': 'lbs'},
                {'name': 'Sugar', 'category': 'food', 'quantity': 10, 'unit': 'lbs'},
                {'name': 'Cooking oil', 'category': 'food', 'quantity': 2, 'unit': 'gallons'},
                {'name': 'Powdered milk', 'category': 'food', 'quantity': 10, 'unit': 'lbs'},
                {'name': 'Flour (all-purpose)', 'category': 'food', 'quantity': 25, 'unit': 'lbs'},
                {'name': 'Baking soda', 'category': 'food', 'quantity': 2, 'unit': 'lbs'},
                {'name': 'Instant coffee', 'category': 'food', 'quantity': 2, 'unit': 'lbs'},
                {'name': 'Vitamins (multivitamin)', 'category': 'medical', 'quantity': 120, 'unit': 'tablets'},
                {'name': 'Water storage (5-gal jugs)', 'category': 'water', 'quantity': 12, 'unit': 'jugs'},
                {'name': 'Bleach (unscented)', 'category': 'water', 'quantity': 1, 'unit': 'gallon'},
                {'name': 'Water filter (gravity)', 'category': 'water', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Propane canisters', 'category': 'fuel', 'quantity': 8, 'unit': 'ea'},
                {'name': 'Camp stove', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Toilet paper', 'category': 'hygiene', 'quantity': 24, 'unit': 'rolls'},
                {'name': 'Bar soap', 'category': 'hygiene', 'quantity': 12, 'unit': 'bars'},
                {'name': 'Toothpaste', 'category': 'hygiene', 'quantity': 4, 'unit': 'tubes'},
                {'name': 'Laundry detergent', 'category': 'hygiene', 'quantity': 1, 'unit': 'jug'},
                {'name': 'Trash bags (13-gal)', 'category': 'tools', 'quantity': 60, 'unit': 'ea'},
                {'name': 'Candles (long-burn)', 'category': 'tools', 'quantity': 12, 'unit': 'ea'},
                {'name': 'D Batteries', 'category': 'tools', 'quantity': 16, 'unit': 'ea'},
                {'name': 'First aid kit (family)', 'category': 'medical', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Ibuprofen (200mg)', 'category': 'medical', 'quantity': 200, 'unit': 'tablets'},
                {'name': 'Acetaminophen (500mg)', 'category': 'medical', 'quantity': 200, 'unit': 'tablets'},
                {'name': 'Anti-diarrheal', 'category': 'medical', 'quantity': 1, 'unit': 'box'},
                {'name': 'Antibiotic ointment', 'category': 'medical', 'quantity': 3, 'unit': 'tubes'},
                {'name': 'Canned soup', 'category': 'food', 'quantity': 24, 'unit': 'cans'},
                {'name': 'Pasta (spaghetti)', 'category': 'food', 'quantity': 10, 'unit': 'lbs'},
                {'name': 'Pasta sauce', 'category': 'food', 'quantity': 8, 'unit': 'jars'},
                {'name': 'Dried lentils', 'category': 'food', 'quantity': 10, 'unit': 'lbs'},
                {'name': 'Cornmeal', 'category': 'food', 'quantity': 5, 'unit': 'lbs'},
                {'name': 'Bouillon cubes', 'category': 'food', 'quantity': 2, 'unit': 'boxes'},
                {'name': 'Spice kit (basics)', 'category': 'food', 'quantity': 1, 'unit': 'set'},
                {'name': 'Yeast (active dry)', 'category': 'food', 'quantity': 4, 'unit': 'packets'},
                {'name': 'Vinegar (white)', 'category': 'food', 'quantity': 1, 'unit': 'gallon'},
                {'name': 'Canned tomatoes', 'category': 'food', 'quantity': 12, 'unit': 'cans'},
            ],
        },
        'bug-out-bag': {
            'name': 'Bug-Out Bag',
            'description': 'Lightweight go-bag for rapid evacuation',
            'items': [
                {'name': 'Backpack (65L)', 'category': 'shelter', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Water bottle (Nalgene 1L)', 'category': 'water', 'quantity': 2, 'unit': 'ea'},
                {'name': 'Water filter (Sawyer Squeeze)', 'category': 'water', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Tarp (8x10)', 'category': 'shelter', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Sleeping bag (compact)', 'category': 'shelter', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Sleeping pad (inflatable)', 'category': 'shelter', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Fire starter (ferro rod)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Lighter (windproof)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Tinder (fatwood sticks)', 'category': 'tools', 'quantity': 1, 'unit': 'bag'},
                {'name': 'Fixed-blade knife', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Folding saw', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Headlamp (200 lumen)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Spare batteries (AAA)', 'category': 'tools', 'quantity': 6, 'unit': 'ea'},
                {'name': 'Paracord (100ft)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Compass (lensatic)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Topographic map (local)', 'category': 'other', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Freeze-dried meals', 'category': 'food', 'quantity': 6, 'unit': 'ea'},
                {'name': 'Beef jerky', 'category': 'food', 'quantity': 4, 'unit': 'bags'},
                {'name': 'Cliff bars', 'category': 'food', 'quantity': 12, 'unit': 'ea'},
                {'name': 'Electrolyte packets', 'category': 'food', 'quantity': 10, 'unit': 'ea'},
                {'name': 'IFAK (trauma kit)', 'category': 'medical', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Tourniquet (CAT)', 'category': 'medical', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Ibuprofen (travel pack)', 'category': 'medical', 'quantity': 1, 'unit': 'pack'},
                {'name': 'Bandana/shemagh', 'category': 'other', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Change of socks (wool)', 'category': 'other', 'quantity': 2, 'unit': 'pair'},
                {'name': 'Rain jacket (packable)', 'category': 'shelter', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Cordage (bank line 100ft)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Signal mirror', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Handheld radio (Baofeng UV-5R)', 'category': 'comms', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Notepad (Rite-in-Rain)', 'category': 'other', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Carabiners (locking)', 'category': 'tools', 'quantity': 4, 'unit': 'ea'},
                {'name': 'Zip ties (assorted)', 'category': 'tools', 'quantity': 20, 'unit': 'ea'},
                {'name': 'Cash (small bills)', 'category': 'other', 'quantity': 300, 'unit': 'USD'},
                {'name': 'Cooking pot (titanium)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Spork (titanium)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
            ],
        },
        'first-aid-kit': {
            'name': 'First Aid Kit',
            'description': 'Comprehensive first aid and trauma supplies',
            'items': [
                {'name': 'Adhesive bandages (assorted)', 'category': 'medical', 'quantity': 100, 'unit': 'ea'},
                {'name': 'Gauze pads (4x4)', 'category': 'medical', 'quantity': 25, 'unit': 'ea'},
                {'name': 'Gauze roll (3 inch)', 'category': 'medical', 'quantity': 6, 'unit': 'rolls'},
                {'name': 'Medical tape (1 inch)', 'category': 'medical', 'quantity': 3, 'unit': 'rolls'},
                {'name': 'Elastic bandage (ACE wrap)', 'category': 'medical', 'quantity': 4, 'unit': 'ea'},
                {'name': 'Triangular bandage', 'category': 'medical', 'quantity': 4, 'unit': 'ea'},
                {'name': 'Tourniquet (CAT Gen 7)', 'category': 'medical', 'quantity': 2, 'unit': 'ea'},
                {'name': 'Israeli bandage (6 inch)', 'category': 'medical', 'quantity': 2, 'unit': 'ea'},
                {'name': 'QuikClot hemostatic gauze', 'category': 'medical', 'quantity': 2, 'unit': 'packs'},
                {'name': 'Chest seal (vented)', 'category': 'medical', 'quantity': 2, 'unit': 'ea'},
                {'name': 'NPA airway (28Fr)', 'category': 'medical', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Nitrile gloves (pairs)', 'category': 'medical', 'quantity': 20, 'unit': 'pairs'},
                {'name': 'Alcohol prep pads', 'category': 'medical', 'quantity': 50, 'unit': 'ea'},
                {'name': 'Povidone-iodine swabs', 'category': 'medical', 'quantity': 25, 'unit': 'ea'},
                {'name': 'Antibiotic ointment (packets)', 'category': 'medical', 'quantity': 25, 'unit': 'ea'},
                {'name': 'Butterfly closures', 'category': 'medical', 'quantity': 20, 'unit': 'ea'},
                {'name': 'Splint (SAM splint)', 'category': 'medical', 'quantity': 2, 'unit': 'ea'},
                {'name': 'Trauma shears', 'category': 'medical', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Tweezers (fine point)', 'category': 'medical', 'quantity': 1, 'unit': 'ea'},
                {'name': 'CPR face shield', 'category': 'medical', 'quantity': 2, 'unit': 'ea'},
                {'name': 'Ibuprofen (200mg tablets)', 'category': 'medical', 'quantity': 50, 'unit': 'tablets'},
                {'name': 'Diphenhydramine (25mg)', 'category': 'medical', 'quantity': 25, 'unit': 'tablets'},
                {'name': 'Oral rehydration salts', 'category': 'medical', 'quantity': 10, 'unit': 'packets'},
                {'name': 'Burn gel packets', 'category': 'medical', 'quantity': 10, 'unit': 'ea'},
                {'name': 'Cold pack (instant)', 'category': 'medical', 'quantity': 4, 'unit': 'ea'},
            ],
        },
        'vehicle-emergency-kit': {
            'name': 'Vehicle Emergency Kit',
            'description': 'Roadside and vehicle emergency supplies',
            'items': [
                {'name': 'Jumper cables (20ft)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Tow strap (20ft, 20k lbs)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Tire plug kit', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Portable air compressor (12V)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Fix-a-Flat', 'category': 'tools', 'quantity': 2, 'unit': 'cans'},
                {'name': 'Reflective triangles', 'category': 'tools', 'quantity': 3, 'unit': 'ea'},
                {'name': 'Road flares', 'category': 'tools', 'quantity': 6, 'unit': 'ea'},
                {'name': 'Fire extinguisher (2.5 lb)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Flashlight (heavy duty)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Multi-tool (vehicle)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Duct tape', 'category': 'tools', 'quantity': 1, 'unit': 'roll'},
                {'name': 'WD-40', 'category': 'tools', 'quantity': 1, 'unit': 'can'},
                {'name': 'Zip ties (large)', 'category': 'tools', 'quantity': 20, 'unit': 'ea'},
                {'name': 'Bungee cords (assorted)', 'category': 'tools', 'quantity': 6, 'unit': 'ea'},
                {'name': 'Emergency blanket (wool)', 'category': 'shelter', 'quantity': 2, 'unit': 'ea'},
                {'name': 'Rain poncho', 'category': 'shelter', 'quantity': 2, 'unit': 'ea'},
                {'name': 'Water bottles (16oz)', 'category': 'water', 'quantity': 6, 'unit': 'ea'},
                {'name': 'Energy bars (vehicle pack)', 'category': 'food', 'quantity': 6, 'unit': 'ea'},
                {'name': 'First aid kit (vehicle)', 'category': 'medical', 'quantity': 1, 'unit': 'ea'},
                {'name': 'Seatbelt cutter / window breaker', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
            ],
        },
    }

    @app.route('/api/templates/inventory')
    def api_templates_inventory():
        result = []
        for key, tpl in _INVENTORY_TEMPLATES.items():
            result.append({
                'id': key,
                'name': tpl['name'],
                'description': tpl['description'],
                'item_count': len(tpl['items']),
            })
        return jsonify(result)

    @app.route('/api/templates/inventory/apply', methods=['POST'])
    def api_templates_inventory_apply():
        data = request.get_json() or {}
        template_id = data.get('template_id', '')
        if template_id not in _INVENTORY_TEMPLATES:
            return jsonify({'error': f'Unknown template: {template_id}. Available: {", ".join(_INVENTORY_TEMPLATES.keys())}'}), 400
        tpl = _INVENTORY_TEMPLATES[template_id]
        location = data.get('location', '')
        db = get_db()
        inserted = 0
        for item in tpl['items']:
            db.execute(
                'INSERT INTO inventory (name, category, quantity, unit, location, notes) VALUES (?, ?, ?, ?, ?, ?)',
                (item['name'], item.get('category', 'other'), item.get('quantity', 0),
                 item.get('unit', 'ea'), location, f'From template: {tpl["name"]}'))
            inserted += 1
        db.commit()
        db.close()
        log_activity('template_applied', 'inventory', f'{tpl["name"]} ({inserted} items)')
        return jsonify({'status': 'applied', 'template': tpl['name'], 'items_inserted': inserted})

    # ─── QR Code Generation (Phase 17) ────────────────────────────────

    @app.route('/api/qr/generate', methods=['POST'])
    def api_qr_generate():
        """Generate a QR code as SVG."""
        data = request.get_json() or {}
        text = data.get('text', '')
        if not text:
            return jsonify({'error': 'text is required'}), 400
        size = data.get('size', 256)

        # Try qrcode library first
        try:
            import qrcode
            import qrcode.image.svg
            factory = qrcode.image.svg.SvgPathImage
            qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
            qr.add_data(text)
            qr.make(fit=True)
            import io
            img = qr.make_image(image_factory=factory)
            buf = io.BytesIO()
            img.save(buf)
            svg_str = buf.getvalue().decode('utf-8')
            return jsonify({'format': 'svg', 'svg': svg_str, 'text': text})
        except ImportError:
            pass

        # Fallback: generate a simple QR-like data representation as SVG
        # This is a simple encoding — not a real QR code but visually represents the data
        import hashlib
        h = hashlib.sha256(text.encode()).hexdigest()
        module_count = 21  # QR Version 1 is 21x21
        cell = size // module_count
        svg_parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">']
        svg_parts.append(f'<rect width="{size}" height="{size}" fill="white"/>')

        # Generate a deterministic pattern from the text hash
        bits = ''.join(format(int(c, 16), '04b') for c in h)
        bit_idx = 0

        # Draw finder patterns (top-left, top-right, bottom-left)
        def draw_finder(sx, sy):
            for dx in range(7):
                for dy in range(7):
                    if dx == 0 or dx == 6 or dy == 0 or dy == 6 or (2 <= dx <= 4 and 2 <= dy <= 4):
                        svg_parts.append(f'<rect x="{(sx+dx)*cell}" y="{(sy+dy)*cell}" width="{cell}" height="{cell}" fill="black"/>')

        draw_finder(0, 0)
        draw_finder(module_count - 7, 0)
        draw_finder(0, module_count - 7)

        # Fill data area
        for row in range(module_count):
            for col in range(module_count):
                # Skip finder pattern areas
                if (row < 8 and col < 8) or (row < 8 and col >= module_count - 8) or (row >= module_count - 8 and col < 8):
                    continue
                if bit_idx < len(bits) and bits[bit_idx] == '1':
                    svg_parts.append(f'<rect x="{col*cell}" y="{row*cell}" width="{cell}" height="{cell}" fill="black"/>')
                bit_idx = (bit_idx + 1) % len(bits)

        svg_parts.append('</svg>')
        svg_str = '\n'.join(svg_parts)
        return jsonify({'format': 'svg_fallback', 'svg': svg_str, 'text': text, 'note': 'Fallback pattern — install qrcode library for real QR codes'})

    # ─── Serial Port Bridge Framework (Phase 13) ─────────────────────

    _serial_state = {'connected': False, 'port': None, 'baud': None, 'protocol': None, 'last_reading': None, 'error': None}
    _serial_conn = {'conn': None}

    @app.route('/api/serial/ports')
    def api_serial_ports():
        """List available serial ports."""
        try:
            import serial.tools.list_ports
            ports = []
            for p in serial.tools.list_ports.comports():
                ports.append({
                    'device': p.device,
                    'description': p.description,
                    'hwid': p.hwid,
                    'manufacturer': p.manufacturer,
                })
            return jsonify({'ports': ports, 'pyserial_available': True})
        except ImportError:
            return jsonify({'ports': [], 'pyserial_available': False, 'note': 'Install pyserial: pip install pyserial'})

    @app.route('/api/serial/connect', methods=['POST'])
    def api_serial_connect():
        """Connect to a serial port."""
        data = request.get_json() or {}
        port = data.get('port', '')
        baud = data.get('baud', 9600)
        protocol = data.get('protocol', 'raw')
        if not port:
            return jsonify({'error': 'port is required'}), 400
        try:
            import serial
            if _serial_conn['conn'] and _serial_conn['conn'].is_open:
                _serial_conn['conn'].close()
            conn = serial.Serial(port, baudrate=baud, timeout=2)
            _serial_conn['conn'] = conn
            _serial_state.update({
                'connected': True, 'port': port, 'baud': baud,
                'protocol': protocol, 'error': None,
            })
            log_activity('serial_connected', 'serial', f'{port} @ {baud}')
            return jsonify({'status': 'connected', 'port': port, 'baud': baud, 'protocol': protocol})
        except ImportError:
            return jsonify({'error': 'pyserial not installed. Run: pip install pyserial'}), 500
        except Exception as e:
            _serial_state.update({'connected': False, 'error': str(e)})
            return jsonify({'error': str(e)}), 500

    @app.route('/api/serial/disconnect', methods=['POST'])
    def api_serial_disconnect():
        """Disconnect from serial port."""
        if _serial_conn['conn']:
            try:
                _serial_conn['conn'].close()
            except Exception:
                pass
            _serial_conn['conn'] = None
        _serial_state.update({'connected': False, 'port': None, 'baud': None, 'protocol': None, 'error': None})
        log_activity('serial_disconnected', 'serial')
        return jsonify({'status': 'disconnected'})

    @app.route('/api/serial/status')
    def api_serial_status():
        """Get serial connection status and last reading."""
        return jsonify(_serial_state)

    # ─── Sensor Data Charts (Phase 13) ────────────────────────────────

    @app.route('/api/sensors/chart/<int:device_id>')
    def api_sensors_chart(device_id):
        """Return time-series data for charting, aggregated by hour/day/week."""
        from datetime import datetime, timedelta
        db = get_db()
        range_param = request.args.get('range', '24h')
        reading_type = request.args.get('type', '')

        # Determine time window and aggregation
        now = datetime.now()
        if range_param == '1h':
            since = (now - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
            agg = None  # raw data
        elif range_param == '24h':
            since = (now - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            agg = 'hour'
        elif range_param == '7d':
            since = (now - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
            agg = 'hour'
        elif range_param == '30d':
            since = (now - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
            agg = 'day'
        elif range_param == '90d':
            since = (now - timedelta(days=90)).strftime('%Y-%m-%d %H:%M:%S')
            agg = 'week'
        else:
            since = (now - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            agg = 'hour'

        query_params = [device_id, since]
        type_filter = ''
        if reading_type:
            type_filter = ' AND reading_type = ?'
            query_params.append(reading_type)

        if agg == 'hour':
            rows = db.execute(f'''
                SELECT strftime('%Y-%m-%d %H:00:00', created_at) as timestamp,
                       reading_type, unit,
                       AVG(value) as avg_value, MIN(value) as min_value, MAX(value) as max_value,
                       COUNT(*) as sample_count
                FROM sensor_readings
                WHERE device_id = ? AND created_at >= ?{type_filter}
                GROUP BY strftime('%Y-%m-%d %H', created_at), reading_type
                ORDER BY timestamp ASC
            ''', query_params).fetchall()
        elif agg == 'day':
            rows = db.execute(f'''
                SELECT strftime('%Y-%m-%d', created_at) as timestamp,
                       reading_type, unit,
                       AVG(value) as avg_value, MIN(value) as min_value, MAX(value) as max_value,
                       COUNT(*) as sample_count
                FROM sensor_readings
                WHERE device_id = ? AND created_at >= ?{type_filter}
                GROUP BY strftime('%Y-%m-%d', created_at), reading_type
                ORDER BY timestamp ASC
            ''', query_params).fetchall()
        elif agg == 'week':
            rows = db.execute(f'''
                SELECT strftime('%Y-W%W', created_at) as timestamp,
                       reading_type, unit,
                       AVG(value) as avg_value, MIN(value) as min_value, MAX(value) as max_value,
                       COUNT(*) as sample_count
                FROM sensor_readings
                WHERE device_id = ? AND created_at >= ?{type_filter}
                GROUP BY strftime('%Y-W%W', created_at), reading_type
                ORDER BY timestamp ASC
            ''', query_params).fetchall()
        else:
            rows = db.execute(f'''
                SELECT created_at as timestamp, reading_type, value as avg_value, value as min_value, value as max_value, unit, 1 as sample_count
                FROM sensor_readings
                WHERE device_id = ? AND created_at >= ?{type_filter}
                ORDER BY created_at ASC
            ''', query_params).fetchall()

        # Get device info
        device = db.execute('SELECT * FROM sensor_devices WHERE id = ?', (device_id,)).fetchone()
        db.close()

        series = {}
        for r in rows:
            rt = r['reading_type']
            if rt not in series:
                series[rt] = {'reading_type': rt, 'unit': r['unit'], 'data': []}
            series[rt]['data'].append({
                'timestamp': r['timestamp'],
                'avg': round(r['avg_value'], 2) if r['avg_value'] is not None else None,
                'min': round(r['min_value'], 2) if r['min_value'] is not None else None,
                'max': round(r['max_value'], 2) if r['max_value'] is not None else None,
                'samples': r['sample_count'],
            })

        return jsonify({
            'device_id': device_id,
            'device_name': dict(device)['name'] if device else 'Unknown',
            'range': range_param,
            'aggregation': agg or 'raw',
            'series': list(series.values()),
        })

    # ─── Meshtastic Bridge Stub (Phase 14) ────────────────────────────

    _mesh_state = {'connected': False, 'node_count': 0, 'channel': 'LongFast', 'my_node_id': '!local', 'firmware': None}

    @app.route('/api/mesh/status')
    def api_mesh_status():
        """Return mesh radio status — stub returns disconnected defaults."""
        return jsonify(_mesh_state)

    @app.route('/api/mesh/messages')
    def api_mesh_messages_list():
        """List recent mesh messages."""
        db = get_db()
        limit = request.args.get('limit', 50, type=int)
        rows = db.execute('SELECT * FROM mesh_messages ORDER BY timestamp DESC LIMIT ?', (limit,)).fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/mesh/messages', methods=['POST'])
    def api_mesh_messages_send():
        """Send a mesh message — stub stores locally."""
        data = request.get_json() or {}
        message = data.get('message', '')
        channel = data.get('channel', 'LongFast')
        to_node = data.get('to_node', '^all')
        if not message:
            return jsonify({'error': 'message is required'}), 400
        db = get_db()
        cur = db.execute(
            'INSERT INTO mesh_messages (from_node, to_node, message, channel) VALUES (?, ?, ?, ?)',
            ('!local', to_node, message, channel))
        db.commit()
        msg_id = cur.lastrowid
        row = db.execute('SELECT * FROM mesh_messages WHERE id = ?', (msg_id,)).fetchone()
        db.close()
        if not _mesh_state['connected']:
            return jsonify({'status': 'queued', 'note': 'No mesh radio connected — message stored locally', 'message': dict(row)}), 202
        return jsonify({'status': 'sent', 'message': dict(row)}), 201

    @app.route('/api/mesh/nodes')
    def api_mesh_nodes():
        """List visible mesh nodes — stub returns empty when no hardware."""
        if not _mesh_state['connected']:
            return jsonify({'nodes': [], 'note': 'No mesh radio connected. Connect via Web Serial API in the frontend.'})
        return jsonify({'nodes': []})

    # ─── Comms Status Board (Phase 14) ────────────────────────────────

    @app.route('/api/comms/status-board')
    def api_comms_status_board():
        """Unified view of all communication channels."""
        from datetime import datetime, timedelta
        db = get_db()

        # LAN peers
        lan_peers = []
        try:
            peers = db.execute('SELECT * FROM federation_peers ORDER BY last_seen DESC').fetchall()
            lan_peers = [dict(p) for p in peers]
        except Exception:
            pass

        # Mesh nodes
        mesh_nodes = []
        mesh_status = dict(_mesh_state)

        # Federation peers
        fed_peers = []
        try:
            rows = db.execute("SELECT * FROM federation_peers WHERE trust_level != 'blocked' ORDER BY last_seen DESC").fetchall()
            fed_peers = [dict(r) for r in rows]
        except Exception:
            pass

        # Recent comms log
        recent_comms = []
        try:
            since = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            rows = db.execute('SELECT * FROM comms_log WHERE created_at >= ? ORDER BY created_at DESC LIMIT 50', (since,)).fetchall()
            recent_comms = [dict(r) for r in rows]
        except Exception:
            pass

        # Active frequencies from radio profiles
        active_freqs = []
        try:
            rows = db.execute('SELECT * FROM radio_profiles ORDER BY name').fetchall()
            for r in rows:
                try:
                    channels = json.loads(r['channels']) if r['channels'] else []
                    for ch in channels:
                        active_freqs.append({
                            'profile': r['name'],
                            'radio': r['radio_model'],
                            'channel': ch.get('name', ''),
                            'frequency': ch.get('frequency', ''),
                        })
                except Exception:
                    pass
        except Exception:
            pass

        # Recent mesh messages
        mesh_msgs = []
        try:
            rows = db.execute('SELECT * FROM mesh_messages ORDER BY timestamp DESC LIMIT 20').fetchall()
            mesh_msgs = [dict(r) for r in rows]
        except Exception:
            pass

        db.close()
        return jsonify({
            'lan_peers': lan_peers,
            'mesh': {
                'status': mesh_status,
                'nodes': mesh_nodes,
                'recent_messages': mesh_msgs,
            },
            'federation_peers': fed_peers,
            'recent_comms': recent_comms,
            'active_frequencies': active_freqs,
            'channels_count': {
                'lan': len(lan_peers),
                'mesh': mesh_status.get('node_count', 0),
                'federation': len(fed_peers),
                'frequencies': len(active_freqs),
            },
        })

    # ─── PWA Service Worker ─────────────────────────────────────────

    @app.route('/sw.js')
    def service_worker():
        return app.send_static_file('sw.js')

    # ─── Favicon ──────────────────────────────────────────────────────

    @app.route('/favicon.ico')
    def favicon():
        svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><polygon points="32,4 60,32 32,60 4,32" fill="#4f9cf7"/><polygon points="32,14 50,32 32,50 14,32" fill="#0d0d0d"/><polygon points="32,22 42,32 32,42 22,32" fill="#4f9cf7"/></svg>'
        return Response(svg, mimetype='image/svg+xml')

    # ─── Advanced Routes (Phases 16, 18, 19, 20) ────────────────────
    from web.routes_advanced import register_advanced_routes
    register_advanced_routes(app)

    return app
