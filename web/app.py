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
try:
    from web.catalog import CHANNEL_CATALOG, CHANNEL_CATEGORIES
except Exception:
    try:
        from catalog import CHANNEL_CATALOG, CHANNEL_CATEGORIES
    except Exception:
        CHANNEL_CATALOG = []
        CHANNEL_CATEGORIES = []
from db import get_db, log_activity
from services import ollama, kiwix, cyberchef, kolibri, qdrant, stirling
from services.manager import (
    get_download_progress, get_dir_size, format_size, uninstall_service, get_services_dir,
    ensure_dependencies, detect_gpu
)

log = logging.getLogger('nomad.web')

SERVICE_MODULES = {
    'ollama': ollama,
    'kiwix': kiwix,
    'cyberchef': cyberchef,
    'kolibri': kolibri,
    'qdrant': qdrant,
    'stirling': stirling,
}

VERSION = '1.0.0'


def set_version(v):
    global VERSION
    VERSION = v

# RAG / Knowledge Base state
_embed_state = {'status': 'idle', 'doc_id': None, 'progress': 0, 'detail': ''}
EMBED_MODEL = 'nomic-embed-text:v1.5'
CHUNK_SIZE = 500  # approximate tokens per chunk
CHUNK_OVERLAP = 50

# Benchmark state
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
            row = db.execute("SELECT value FROM settings WHERE key = 'auth_password'").fetchone()
            db.close()
            if row and row['value']:
                import hashlib
                token = request.headers.get('X-Auth-Token', '')
                if hashlib.sha256(token.encode()).hexdigest() != row['value']:
                    return jsonify({'error': 'Authentication required'}), 403
        except Exception:
            pass

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

    @app.route('/api/services/<service_id>/install', methods=['POST'])
    def api_install_service(service_id):
        mod = SERVICE_MODULES.get(service_id)
        if not mod:
            return jsonify({'error': 'Unknown service'}), 404
        if mod.is_installed():
            return jsonify({'status': 'already_installed'})
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
                    sit_parts.append('BURN RATES: ' + ', '.join(f'{r["name"]}: {round(r["quantity"]/r["daily_usage"],1)} days left' for r in burn))
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
                    sit = json.loads(settings_row['value'] or '{}')
                    sit_parts.append('SITUATION STATUS: ' + ', '.join(f'{k}: {v}' for k, v in sit.items()))
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
                    pt_str = ', '.join(f'{p["name"]} (allergies: {json.loads(p["allergies"] or "[]")}, conditions: {json.loads(p["conditions"] or "[]")})' for p in patients)
                    sit_parts.append(f'PATIENTS: {pt_str}')
                # Garden/harvest
                harvest_count = db_ctx.execute('SELECT COUNT(*) as c FROM harvest_log').fetchone()['c']
                if harvest_count:
                    sit_parts.append(f'GARDEN: {harvest_count} harvests logged')
                db_ctx.close()
                if sit_parts:
                    ctx = '\n'.join(sit_parts)
                    system_prompt = (system_prompt + '\n\n' if system_prompt else '') + \
                        f'You have access to the user\'s current preparedness data. Use this to give specific, actionable advice based on their actual situation:\n\n--- Current Situation ---\n{ctx}\n--- End Situation ---'
            except Exception as e:
                log.warning(f'Situation context injection failed: {e}')
            finally:
                if db_ctx:
                    try: db_ctx.close()
                    except: pass

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

    @app.route('/api/ai/recommended')
    def api_ai_recommended():
        return jsonify(ollama.RECOMMENDED_MODELS)

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
        notes = db.execute('SELECT * FROM notes ORDER BY pinned DESC, updated_at DESC').fetchall()
        db.close()
        return jsonify([dict(n) for n in notes])

    @app.route('/api/notes', methods=['POST'])
    def api_notes_create():
        data = request.get_json() or {}
        db = get_db()
        cur = db.execute('INSERT INTO notes (title, content) VALUES (?, ?)',
                         (data.get('title', 'Untitled'), data.get('content', '')))
        db.commit()
        note_id = cur.lastrowid
        note = db.execute('SELECT * FROM notes WHERE id = ?', (note_id,)).fetchone()
        db.close()
        return jsonify(dict(note)), 201

    @app.route('/api/notes/<int:note_id>', methods=['PUT'])
    def api_notes_update(note_id):
        data = request.get_json() or {}
        db = get_db()
        # Fetch current values to preserve on partial update
        current = db.execute('SELECT title, content FROM notes WHERE id = ?', (note_id,)).fetchone()
        if not current:
            db.close()
            return jsonify({'error': 'Not found'}), 404
        title = data.get('title') if data.get('title') is not None else current['title']
        content = data.get('content') if data.get('content') is not None else current['content']
        db.execute('UPDATE notes SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                   (title, content, note_id))
        db.commit()
        note = db.execute('SELECT * FROM notes WHERE id = ?', (note_id,)).fetchone()
        db.close()
        return jsonify(dict(note))

    @app.route('/api/notes/<int:note_id>', methods=['DELETE'])
    def api_notes_delete(note_id):
        db = get_db()
        db.execute('DELETE FROM notes WHERE id = ?', (note_id,))
        db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    # ─── Settings API ─────────────────────────────────────────────────

    @app.route('/api/settings')
    def api_settings():
        db = get_db()
        rows = db.execute('SELECT key, value FROM settings').fetchall()
        db.close()
        return jsonify({r['key']: r['value'] for r in rows})

    @app.route('/api/settings', methods=['PUT'])
    def api_settings_update():
        data = request.get_json() or {}
        db = get_db()
        for key, value in data.items():
            db.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, str(value)))
        db.commit()
        db.close()
        return jsonify({'status': 'saved'})

    @app.route('/api/settings/wizard-complete', methods=['POST'])
    def api_wizard_complete():
        db = get_db()
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('first_run_complete', '1')")
        db.commit()
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
            db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('first_run_complete', '1')")
            db.commit()
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

        # GPU detection
        gpu_name = 'None detected'
        gpu_vram = ''
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=5, creationflags=0x08000000,
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split(', ')
                gpu_name = parts[0]
                if len(parts) > 1:
                    gpu_vram = f'{int(parts[1])} MB'
        except Exception:
            pass

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
        convos = db.execute('SELECT id, title, model, created_at, updated_at FROM conversations ORDER BY updated_at DESC').fetchall()
        db.close()
        return jsonify([dict(c) for c in convos])

    @app.route('/api/conversations', methods=['POST'])
    def api_conversations_create():
        data = request.get_json() or {}
        db = get_db()
        cur = db.execute('INSERT INTO conversations (title, model, messages) VALUES (?, ?, ?)',
                         (data.get('title', 'New Chat'), data.get('model', ''), '[]'))
        db.commit()
        cid = cur.lastrowid
        convo = db.execute('SELECT * FROM conversations WHERE id = ?', (cid,)).fetchone()
        db.close()
        return jsonify(dict(convo)), 201

    @app.route('/api/conversations/<int:cid>')
    def api_conversations_get(cid):
        db = get_db()
        convo = db.execute('SELECT * FROM conversations WHERE id = ?', (cid,)).fetchone()
        db.close()
        if not convo:
            return jsonify({'error': 'Not found'}), 404
        return jsonify(dict(convo))

    @app.route('/api/conversations/<int:cid>', methods=['PUT'])
    def api_conversations_update(cid):
        data = request.get_json() or {}
        db = get_db()
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
        db.close()
        return jsonify({'status': 'saved'})

    @app.route('/api/conversations/<int:cid>', methods=['PATCH'])
    def api_conversation_rename(cid):
        data = request.get_json() or {}
        title = data.get('title', '').strip()
        if not title:
            return jsonify({'error': 'Title required'}), 400
        db = get_db()
        db.execute('UPDATE conversations SET title = ? WHERE id = ?', (title, cid))
        db.commit()
        db.close()
        return jsonify({'status': 'renamed'})

    @app.route('/api/conversations/<int:cid>', methods=['DELETE'])
    def api_conversations_delete(cid):
        db = get_db()
        db.execute('DELETE FROM conversations WHERE id = ?', (cid,))
        db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    @app.route('/api/conversations/all', methods=['DELETE'])
    def api_conversations_delete_all():
        db = get_db()
        db.execute('DELETE FROM conversations')
        db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    @app.route('/api/conversations/search')
    def api_conversations_search():
        q = request.args.get('q', '').strip()
        if not q:
            return jsonify([])
        db = get_db()
        rows = db.execute(
            "SELECT id, title, model, created_at FROM conversations WHERE title LIKE ? OR messages LIKE ? ORDER BY updated_at DESC LIMIT 20",
            (f'%{q}%', f'%{q}%')
        ).fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/conversations/<int:cid>/export')
    def api_conversations_export(cid):
        db = get_db()
        convo = db.execute('SELECT * FROM conversations WHERE id = ?', (cid,)).fetchone()
        db.close()
        if not convo:
            return jsonify({'error': 'Not found'}), 404
        messages = json.loads(convo['messages'] or '[]')
        md = f"# {convo['title']}\n\n"
        md += f"*Model: {convo['model'] or 'Unknown'} | {convo['created_at']}*\n\n---\n\n"
        for m in messages:
            role = 'You' if m['role'] == 'user' else 'AI'
            md += f"**{role}:**\n\n{m.get('content', '')}\n\n---\n\n"
        return Response(md, mimetype='text/markdown',
                       headers={'Content-Disposition': f'attachment; filename="{convo["title"]}.md"'})

    # ─── Unified Search API ────────────────────────────────────────────

    @app.route('/api/content-summary')
    def api_content_summary():
        """Human-readable summary of offline knowledge capacity."""
        db = get_db()
        convo_count = db.execute('SELECT COUNT(*) as c FROM conversations').fetchone()['c']
        note_count = db.execute('SELECT COUNT(*) as c FROM notes').fetchone()['c']
        doc_count = db.execute('SELECT COUNT(*) as c FROM documents WHERE status = ?', ('ready',)).fetchone()['c']
        doc_chunks = db.execute('SELECT COALESCE(SUM(chunks_count), 0) as c FROM documents WHERE status = ?', ('ready',)).fetchone()['c']
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

                try:
                    r = subprocess.run(
                        ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                        capture_output=True, text=True, timeout=5, creationflags=0x08000000,
                    )
                    hw['gpu'] = r.stdout.strip() if r.returncode == 0 else 'None'
                except Exception:
                    hw['gpu'] = 'None'

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
                    test_dir = os.path.join(os.environ.get('APPDATA', ''), 'ProjectNOMAD', 'benchmark')
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
                db.execute('''INSERT INTO benchmarks
                    (cpu_score, memory_score, disk_read_score, disk_write_score, ai_tps, ai_ttft, nomad_score, hardware, details)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (results.get('cpu_score', 0), results.get('memory_score', 0),
                     results.get('disk_read_score', 0), results.get('disk_write_score', 0),
                     results.get('ai_tps', 0), results.get('ai_ttft', 0),
                     results.get('nomad_score', 0), json.dumps(hw), json.dumps(results)))
                db.commit()
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
        rows = db.execute('SELECT * FROM benchmarks ORDER BY created_at DESC LIMIT 20').fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    # ─── Maps API ──────────────────────────────────────────────────────

    MAPS_DIR_NAME = 'maps'

    def get_maps_dir():
        path = os.path.join(os.environ.get('APPDATA', ''), 'ProjectNOMAD', MAPS_DIR_NAME)
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
        if not filename or '..' in filename:
            return jsonify({'error': 'Invalid filename'}), 400
        path = os.path.join(get_maps_dir(), filename)
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
        if not safe_path.startswith(os.path.normpath(maps_dir)):
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

        with open(safe_path, 'rb') as f:
            data = f.read()
        return Response(data, mimetype='application/octet-stream')

    @app.route('/api/maps/sources')
    def api_maps_sources():
        return jsonify(MAP_SOURCES)

    @app.route('/api/maps/download-progress')
    def api_maps_download_progress():
        return jsonify(_map_downloads)

    def _get_pmtiles_cli():
        """Get path to pmtiles CLI, auto-downloading if needed."""
        services_dir = get_services_dir()
        pmtiles_dir = os.path.join(services_dir, 'pmtiles')
        os.makedirs(pmtiles_dir, exist_ok=True)
        exe = os.path.join(pmtiles_dir, 'pmtiles.exe')
        if os.path.isfile(exe):
            return exe
        # Download from GitHub releases
        import urllib.request, zipfile, io, json as _json
        # Resolve latest release asset URL via GitHub API
        api_url = 'https://api.github.com/repos/protomaps/go-pmtiles/releases/latest'
        log.info('Resolving pmtiles CLI release from %s', api_url)
        req = urllib.request.Request(api_url, headers={'User-Agent': 'ProjectNOMAD/3.5.0', 'Accept': 'application/vnd.github+json'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            release = _json.loads(resp.read())
        url = None
        for asset in release.get('assets', []):
            if 'Windows' in asset['name'] and 'x86_64' in asset['name'] and asset['name'].endswith('.zip'):
                url = asset['browser_download_url']
                break
        if not url:
            log.error('No Windows x86_64 asset found in go-pmtiles release')
            return None
        log.info('Downloading pmtiles CLI from %s', url)
        req = urllib.request.Request(url, headers={'User-Agent': 'ProjectNOMAD/3.5.0'})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for name in zf.namelist():
                if name.endswith('pmtiles.exe') or name.endswith('pmtiles'):
                    extracted = zf.extract(name, pmtiles_dir)
                    # Move to expected location if in subdirectory
                    if extracted != exe:
                        shutil.move(extracted, exe)
                    break
        if os.path.isfile(exe):
            log.info('pmtiles CLI installed at %s', exe)
            return exe
        return None

    def _download_map_region_thread(region_id, bbox, maps_dir):
        """Background thread: extract a region from Protomaps planet using pmtiles CLI."""
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
            CREATE_NO_WINDOW = 0x08000000
            cmd = [pmtiles_exe, 'extract', source_url, temp_file, f'--bbox={bbox_str}', '--maxzoom=12']
            log.info('Running: %s', ' '.join(cmd))

            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    creationflags=CREATE_NO_WINDOW, text=True)

            # Monitor progress from output
            lines = []
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

    @app.route('/api/maps/import-file', methods=['POST'])
    def api_maps_import_file():
        """Import a local map file by copying it to the maps directory."""
        data = request.get_json() or {}
        source_path = data.get('path', '').strip()
        if not source_path or not os.path.isfile(source_path):
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
        path = os.path.join(os.environ.get('APPDATA', ''), 'ProjectNOMAD', 'kb_uploads')
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
        cur = db.execute('INSERT INTO documents (filename, content_type, file_size, status) VALUES (?, ?, ?, ?)',
                         (filename, content_type, file_size, 'pending'))
        db.commit()
        doc_id = cur.lastrowid
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
        docs = db.execute('SELECT * FROM documents ORDER BY created_at DESC').fetchall()
        db.close()
        return jsonify([dict(d) for d in docs])

    @app.route('/api/kb/documents/<int:doc_id>', methods=['DELETE'])
    def api_kb_document_delete(doc_id):
        db = get_db()
        doc = db.execute('SELECT filename FROM documents WHERE id = ?', (doc_id,)).fetchone()
        if doc:
            filepath = os.path.join(get_kb_upload_dir(), doc['filename'])
            if os.path.isfile(filepath):
                os.remove(filepath)
            qdrant.delete_by_doc_id(doc_id)
            db.execute('DELETE FROM documents WHERE id = ?', (doc_id,))
            db.commit()
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
        if filter_val:
            rows = db.execute('SELECT * FROM activity_log WHERE event LIKE ? OR service LIKE ? ORDER BY created_at DESC LIMIT ?',
                              (f'%{filter_val}%', f'%{filter_val}%', limit)).fetchall()
        else:
            rows = db.execute('SELECT * FROM activity_log ORDER BY created_at DESC LIMIT ?', (limit,)).fetchall()
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
            resp = rq.get('https://api.github.com/repos/SysAdminDoc/nomad-windows/releases/latest', timeout=10)
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
                    is_newer = latest != current and latest > current
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

    # ─── Windows Startup Toggle ───────────────────────────────────────

    @app.route('/api/startup')
    def api_startup_get():
        """Check if app is set to start with Windows."""
        import winreg
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r'Software\Microsoft\Windows\CurrentVersion\Run', 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, 'ProjectNOMAD')
            winreg.CloseKey(key)
            return jsonify({'enabled': True})
        except Exception:
            return jsonify({'enabled': False})

    @app.route('/api/startup', methods=['PUT'])
    def api_startup_set():
        """Enable or disable start with Windows."""
        import winreg
        data = request.get_json() or {}
        enabled = data.get('enabled', False)
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r'Software\Microsoft\Windows\CurrentVersion\Run', 0, winreg.KEY_SET_VALUE)
            if enabled:
                exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath('nomad.py')
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
        rows = db.execute('SELECT * FROM checklists ORDER BY updated_at DESC').fetchall()
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
        cur = db.execute('INSERT INTO checklists (name, template, items) VALUES (?, ?, ?)',
                         (name, template_id, items))
        db.commit()
        cid = cur.lastrowid
        row = db.execute('SELECT * FROM checklists WHERE id = ?', (cid,)).fetchone()
        db.close()
        return jsonify({**dict(row), 'items': json.loads(row['items'] or '[]')}), 201

    @app.route('/api/checklists/<int:cid>')
    def api_checklists_get(cid):
        db = get_db()
        row = db.execute('SELECT * FROM checklists WHERE id = ?', (cid,)).fetchone()
        db.close()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        return jsonify({**dict(row), 'items': json.loads(row['items'] or '[]')})

    @app.route('/api/checklists/<int:cid>', methods=['PUT'])
    def api_checklists_update(cid):
        data = request.get_json() or {}
        db = get_db()
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
        db.close()
        return jsonify({'status': 'saved'})

    @app.route('/api/checklists/<int:cid>', methods=['DELETE'])
    def api_checklists_delete(cid):
        db = get_db()
        db.execute('DELETE FROM checklists WHERE id = ?', (cid,))
        db.commit()
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
        db.close()
        return jsonify([dict(r) for r in rows])

    @app.route('/api/inventory', methods=['POST'])
    def api_inventory_create():
        data = request.get_json() or {}
        db = get_db()
        cur = db.execute(
            'INSERT INTO inventory (name, category, quantity, unit, min_quantity, daily_usage, location, expiration, barcode, cost, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (data.get('name', ''), data.get('category', 'other'), data.get('quantity', 0),
             data.get('unit', 'ea'), data.get('min_quantity', 0), data.get('daily_usage', 0),
             data.get('location', ''), data.get('expiration', ''), data.get('barcode', ''), data.get('cost', 0), data.get('notes', '')))
        db.commit()
        item_id = cur.lastrowid
        row = db.execute('SELECT * FROM inventory WHERE id = ?', (item_id,)).fetchone()
        db.close()
        return jsonify(dict(row)), 201

    @app.route('/api/inventory/<int:item_id>', methods=['PUT'])
    def api_inventory_update(item_id):
        data = request.get_json() or {}
        db = get_db()
        allowed = ['name', 'category', 'quantity', 'unit', 'min_quantity', 'daily_usage', 'location', 'expiration', 'barcode', 'cost', 'notes']
        fields = []
        vals = []
        for k in allowed:
            if k in data:
                fields.append(f'{k} = ?')
                vals.append(data[k])
        if not fields:
            return jsonify({'error': 'No fields to update'}), 400
        fields.append('updated_at = CURRENT_TIMESTAMP')
        vals.append(item_id)
        db.execute(f'UPDATE inventory SET {", ".join(fields)} WHERE id = ?', vals)
        db.commit()
        db.close()
        return jsonify({'status': 'saved'})

    @app.route('/api/inventory/<int:item_id>', methods=['DELETE'])
    def api_inventory_delete(item_id):
        db = get_db()
        db.execute('DELETE FROM inventory WHERE id = ?', (item_id,))
        db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    @app.route('/api/inventory/summary')
    def api_inventory_summary():
        db = get_db()
        total = db.execute('SELECT COUNT(*) as c FROM inventory').fetchone()['c']
        low_stock = db.execute('SELECT COUNT(*) as c FROM inventory WHERE quantity <= min_quantity AND min_quantity > 0').fetchone()['c']
        # Expiring within 30 days
        from datetime import datetime, timedelta
        soon = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        today = datetime.now().strftime('%Y-%m-%d')
        expiring = db.execute("SELECT COUNT(*) as c FROM inventory WHERE expiration != '' AND expiration <= ? AND expiration >= ?", (soon, today)).fetchone()['c']
        expired = db.execute("SELECT COUNT(*) as c FROM inventory WHERE expiration != '' AND expiration < ?", (today,)).fetchone()['c']
        cats = db.execute('SELECT category, COUNT(*) as c, SUM(quantity) as qty FROM inventory GROUP BY category ORDER BY category').fetchall()
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
        rows = db.execute('SELECT category, name, quantity, unit, daily_usage FROM inventory WHERE daily_usage > 0 ORDER BY category, name').fetchall()
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
        html += '<div style="text-align:center;margin-top:8px;font-size:9px;color:#999;">Project N.O.M.A.D. for Windows - Offline Survival Command Center</div>'
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
        return os.path.join(get_services_dir(), 'yt-dlp', 'yt-dlp.exe')

    VIDEO_CATEGORIES = ['survival', 'medical', 'repair', 'bushcraft', 'cooking', 'radio', 'farming', 'defense', 'general']

    YTDLP_URL = 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe'

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
        {'title': 'How to Suture a Wound - Survival Medicine', 'url': 'https://www.youtube.com/watch?v=mfWahyERGBo', 'channel': 'Prepper Nurse', 'category': 'medical', 'folder': 'First Aid & Medical'},
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
        {'title': 'Situational Awareness - Gray Man Concept', 'url': 'https://www.youtube.com/watch?v=_sRjSR_B2Bc', 'channel': 'City Prepping', 'category': 'defense', 'folder': 'Security'},
        {'title': 'Home Defense Strategies', 'url': 'https://www.youtube.com/watch?v=mSCGGr8B0W8', 'channel': 'Warrior Poet Society', 'category': 'defense', 'folder': 'Security'},
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
                capture_output=True, text=True, timeout=20, creationflags=0x08000000,
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
        limit = min(int(request.args.get('limit', '12')), 30)
        if not query:
            return jsonify([])
        exe = get_ytdlp_path()
        if not os.path.isfile(exe):
            return jsonify({'error': 'Downloader not installed'}), 400
        try:
            result = subprocess.run(
                [exe, '--flat-playlist', '--dump-json', f'ytsearch{limit}:{query}'],
                capture_output=True, text=True, timeout=30, creationflags=0x08000000,
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
        limit = min(int(request.args.get('limit', '12')), 50)
        if not channel_url:
            return jsonify([])
        exe = get_ytdlp_path()
        if not os.path.isfile(exe):
            return jsonify({'error': 'Downloader not installed'}), 400
        try:
            result = subprocess.run(
                [exe, '--flat-playlist', '--dump-json', '--playlist-end', str(limit),
                 channel_url + '/videos'],
                capture_output=True, text=True, timeout=45, creationflags=0x08000000,
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
        row = db.execute(f'SELECT favorited FROM {table} WHERE id = ?', (media_id,)).fetchone()
        if row:
            new_val = 0 if row['favorited'] else 1
            db.execute(f'UPDATE {table} SET favorited = ? WHERE id = ?', (new_val, media_id))
            db.commit()
        db.close()
        return jsonify({'status': 'toggled', 'favorited': new_val if row else 0})

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
        db.close()
        return jsonify({'status': 'deleted', 'count': deleted})

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
        for mid in ids:
            db.execute(f'UPDATE {table} SET folder = ? WHERE id = ?', (folder, mid))
        db.commit()
        db.close()
        return jsonify({'status': 'moved', 'count': len(ids)})

    # ─── yt-dlp Integration ──────────────────────────────────────────

    @app.route('/api/ytdlp/status')
    def api_ytdlp_status():
        exe = get_ytdlp_path()
        installed = os.path.isfile(exe)
        version = ''
        if installed:
            try:
                result = subprocess.run([exe, '--version'], capture_output=True, text=True, timeout=5,
                                        creationflags=0x08000000)
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
                resp = req.get(YTDLP_URL, stream=True, timeout=120, allow_redirects=True)
                resp.raise_for_status()
                total = int(resp.headers.get('content-length', 0))
                downloaded = 0
                with open(exe, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            _ytdlp_install_state['percent'] = int(downloaded / total * 90) + 10
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
                    capture_output=True, text=True, timeout=30, creationflags=0x08000000,
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
                    creationflags=0x08000000,
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
        return jsonify(_ytdlp_downloads)

    @app.route('/api/ytdlp/progress/<dl_id>')
    def api_ytdlp_progress_single(dl_id):
        return jsonify(_ytdlp_downloads.get(dl_id, {'status': 'unknown'}))

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
                        capture_output=True, text=True, timeout=15, creationflags=0x08000000,
                    )
                    if check.returncode != 0:
                        # URL is dead — search for the video by title instead
                        use_search = True
                        _ytdlp_downloads[queue_id]['title'] = f'[{i+1}/{len(to_download)}] Searching: {title}'
                        search_result = subprocess.run(
                            [exe, '--flat-playlist', '--dump-json', f'ytsearch1:{title}'],
                            capture_output=True, text=True, timeout=20, creationflags=0x08000000,
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
                        creationflags=0x08000000,
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

    FFMPEG_URL = 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip'

    def get_ffmpeg_path():
        return os.path.join(get_services_dir(), 'ffmpeg', 'ffmpeg.exe')

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
        db = get_db()
        for field in ['title', 'folder', 'category', 'artist', 'album']:
            if field in data:
                db.execute(f'UPDATE audio SET {field} = ? WHERE id = ?', (data[field], aid))
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
                    capture_output=True, text=True, timeout=30, creationflags=0x08000000,
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
                                        text=True, creationflags=0x08000000)
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
                zip_path = os.path.join(ffmpeg_dir, 'ffmpeg.zip')
                import requests as req
                resp = req.get(FFMPEG_URL, stream=True, timeout=300, allow_redirects=True)
                resp.raise_for_status()
                total = int(resp.headers.get('content-length', 0))
                downloaded = 0
                with open(zip_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=131072):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            _ffmpeg_install['percent'] = int(downloaded / total * 80)
                _ffmpeg_install.update({'status': 'extracting', 'percent': 85})
                import zipfile
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    for member in zf.namelist():
                        basename = os.path.basename(member)
                        if basename in ('ffmpeg.exe', 'ffprobe.exe'):
                            data = zf.read(member)
                            with open(os.path.join(ffmpeg_dir, basename), 'wb') as out:
                                out.write(data)
                os.remove(zip_path)
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
        db = get_db()
        for field in ['title', 'folder', 'category', 'author', 'last_position']:
            if field in data:
                db.execute(f'UPDATE books SET {field} = ? WHERE id = ?', (data[field], bid))
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
                except: pass

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
                except: pass

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
                except: pass

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
            'critical_burn': [{'name': r['name'], 'days_left': round(r['quantity']/r['daily_usage'], 1), 'category': r['category']} for r in critical_burn],
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
            count = 0
            for row in rows:
                row.pop('id', None)
                row.pop('created_at', None)
                row.pop('updated_at', None)
                row.pop('_source_node', None)
                cols = list(row.keys())
                vals = list(row.values())
                if not cols:
                    continue
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
        db = get_db()
        db.execute('INSERT INTO harvest_log (crop, quantity, unit, plot_id, notes) VALUES (?,?,?,?,?)',
                   (data['crop'], data.get('quantity', 0), data.get('unit', 'lbs'),
                    data.get('plot_id'), data.get('notes', '')))
        # Auto-add to inventory
        existing = db.execute('SELECT id, quantity FROM inventory WHERE name = ? AND category = ?', (data['crop'], 'food')).fetchone()
        if existing:
            db.execute('UPDATE inventory SET quantity = quantity + ? WHERE id = ?', (data.get('quantity', 0), existing['id']))
        else:
            db.execute('INSERT INTO inventory (name, category, quantity, unit) VALUES (?, ?, ?, ?)',
                       (data['crop'], 'food', data.get('quantity', 0), data.get('unit', 'lbs')))
        db.commit()
        db.close()
        log_activity('harvest_logged', detail=f'{data.get("quantity", 0)} {data.get("unit", "lbs")} of {data["crop"]}')
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
            if action == 'reboot':
                os.system('shutdown /r /t 5 /c "N.O.M.A.D. initiated reboot"')
            else:
                os.system('shutdown /s /t 5 /c "N.O.M.A.D. initiated shutdown"')
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

        # Quick Reference Footer
        html += '''<h2>QUICK REFERENCE</h2>
<div class="grid">
<div><strong>Water:</strong> 1 gal/person/day. Bleach: 8 drops/gal (clear), 16 drops/gal (cloudy). Wait 30 min.</div>
<div><strong>Food:</strong> 2,000 cal/person/day. Eat perishable first, then frozen, then shelf-stable.</div>
<div><strong>Radio:</strong> FRS Ch 1 (rally), Ch 3 (emergency). GMRS Ch 20 (emergency). HAM 146.520 MHz (calling).</div>
<div><strong>Medical:</strong> Direct pressure for bleeding. Tourniquet if limb bleeding won\'t stop. Note time applied.</div>
</div>
<div style="text-align:center;margin-top:8px;font-size:8px;color:#666;">Generated by Project N.O.M.A.D. for Windows — projectnomad.us</div>
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
        db.close()
        return jsonify({
            'conversations': [dict(r) for r in convos], 'notes': [dict(r) for r in notes],
            'documents': [dict(r) for r in docs], 'inventory': [dict(r) for r in inv],
            'contacts': [dict(r) for r in contacts], 'checklists': [dict(r) for r in checklists],
            'skills': [dict(r) for r in skills], 'ammo': [dict(r) for r in ammo],
            'equipment': [dict(r) for r in equipment],
        })

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
        conn = get_db()
        cur = conn.execute(
            'INSERT INTO ammo_inventory (caliber, brand, bullet_weight, bullet_type, quantity, location, notes) VALUES (?,?,?,?,?,?,?)',
            (d.get('caliber',''), d.get('brand',''), d.get('bullet_weight',''),
             d.get('bullet_type',''), int(d.get('quantity',0)), d.get('location',''), d.get('notes','')))
        conn.commit()
        row = conn.execute('SELECT * FROM ammo_inventory WHERE id=?', (cur.lastrowid,)).fetchone()
        conn.close()
        return jsonify(dict(row)), 201

    @app.route('/api/ammo/<int:aid>', methods=['PUT'])
    def api_ammo_update(aid):
        d = request.json or {}
        conn = get_db()
        conn.execute(
            'UPDATE ammo_inventory SET caliber=?, brand=?, bullet_weight=?, bullet_type=?, quantity=?, location=?, notes=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
            (d.get('caliber',''), d.get('brand',''), d.get('bullet_weight',''),
             d.get('bullet_type',''), int(d.get('quantity',0)), d.get('location',''), d.get('notes',''), aid))
        conn.commit()
        row = conn.execute('SELECT * FROM ammo_inventory WHERE id=?', (aid,)).fetchone()
        conn.close()
        return jsonify(dict(row) if row else {})

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
        total = conn.execute('SELECT SUM(dose_rate_rem) FROM radiation_log').fetchone()[0] or 0
        conn.close()
        return jsonify({'readings': [dict(r) for r in rows], 'total_rem': round(total, 4)})

    @app.route('/api/radiation', methods=['POST'])
    def api_radiation_create():
        d = request.json or {}
        conn = get_db()
        # Compute running cumulative
        last = conn.execute('SELECT cumulative_rem FROM radiation_log ORDER BY created_at DESC LIMIT 1').fetchone()
        prev_cum = last['cumulative_rem'] if last else 0
        new_rate = float(d.get('dose_rate_rem', 0))
        # cumulative = previous + this reading (assumed per-hour if not specified)
        new_cum = round(prev_cum + new_rate, 4)
        cur = conn.execute(
            'INSERT INTO radiation_log (dose_rate_rem, location, cumulative_rem, notes) VALUES (?,?,?,?)',
            (new_rate, d.get('location',''), new_cum, d.get('notes','')))
        conn.commit()
        row = conn.execute('SELECT * FROM radiation_log WHERE id=?', (cur.lastrowid,)).fetchone()
        conn.close()
        return jsonify(dict(row)), 201

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
        conn = get_db()
        cur = conn.execute(
            'INSERT INTO fuel_storage (fuel_type, quantity, unit, container, location, stabilizer_added, date_stored, expires, notes) VALUES (?,?,?,?,?,?,?,?,?)',
            (d.get('fuel_type',''), d.get('quantity',0), d.get('unit','gallons'),
             d.get('container',''), d.get('location',''), int(d.get('stabilizer_added',0)),
             d.get('date_stored',''), d.get('expires',''), d.get('notes','')))
        conn.commit()
        row = conn.execute('SELECT * FROM fuel_storage WHERE id=?', (cur.lastrowid,)).fetchone()
        conn.close()
        return jsonify(dict(row)), 201

    @app.route('/api/fuel/<int:fid>', methods=['PUT'])
    def api_fuel_update(fid):
        d = request.json or {}
        conn = get_db()
        conn.execute(
            'UPDATE fuel_storage SET fuel_type=?,quantity=?,unit=?,container=?,location=?,stabilizer_added=?,date_stored=?,expires=?,notes=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',
            (d.get('fuel_type',''), d.get('quantity',0), d.get('unit','gallons'),
             d.get('container',''), d.get('location',''), int(d.get('stabilizer_added',0)),
             d.get('date_stored',''), d.get('expires',''), d.get('notes',''), fid))
        conn.commit()
        row = conn.execute('SELECT * FROM fuel_storage WHERE id=?', (fid,)).fetchone()
        conn.close()
        return jsonify(dict(row) if row else {})

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

    # ─── Favicon ──────────────────────────────────────────────────────

    @app.route('/favicon.ico')
    def favicon():
        svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><polygon points="32,4 60,32 32,60 4,32" fill="#4f9cf7"/><polygon points="32,14 50,32 32,50 14,32" fill="#0d0d0d"/><polygon points="32,22 42,32 32,42 22,32" fill="#4f9cf7"/></svg>'
        return Response(svg, mimetype='image/svg+xml')

    return app
