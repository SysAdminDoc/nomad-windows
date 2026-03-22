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

VERSION = '2.9.0'


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


def create_app():
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')

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

    @app.route('/api/services/<service_id>/install', methods=['POST'])
    def api_install_service(service_id):
        mod = SERVICE_MODULES.get(service_id)
        if not mod:
            return jsonify({'error': 'Unknown service'}), 404
        if mod.is_installed():
            return jsonify({'status': 'already_installed'})

        def do_install():
            try:
                mod.install()
            except Exception as e:
                log.error(f'Install failed for {service_id}: {e}')

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
        uninstall_service(service_id)
        return jsonify({'status': 'uninstalled'})

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
        for sid, mod in SERVICE_MODULES.items():
            if mod.is_installed() and mod.running():
                try:
                    mod.stop()
                    stopped.append(sid)
                except Exception:
                    pass
        return jsonify({'stopped': stopped})

    @app.route('/api/services/<service_id>/progress')
    def api_service_progress(service_id):
        return jsonify(get_download_progress(service_id))

    @app.route('/api/services/<service_id>/prereqs')
    def api_service_prereqs(service_id):
        """Check prerequisites for a service."""
        if service_id == 'stirling':
            java = stirling._find_java()
            return jsonify({'met': java is not None, 'java_found': java is not None, 'java_path': java,
                            'message': None if java else 'Java 17+ required. Install from https://adoptium.net'})
        if service_id == 'kolibri':
            import shutil
            py = shutil.which('python') or shutil.which('python3')
            return jsonify({'met': py is not None, 'python_found': py is not None,
                            'message': None if py else 'Python required on PATH for Kolibri'})
        return jsonify({'met': True, 'message': None})

    # ─── Ollama AI Chat API ───────────────────────────────────────────

    @app.route('/api/ai/models')
    def api_ai_models():
        if not ollama.is_installed() or not ollama.running():
            return jsonify([])
        return jsonify(ollama.list_models())

    @app.route('/api/ai/pull', methods=['POST'])
    def api_ai_pull():
        data = request.get_json() or {}
        model_name = data.get('model', ollama.DEFAULT_MODEL)

        def do_pull():
            ollama.pull_model(model_name)

        threading.Thread(target=do_pull, daemon=True).start()
        return jsonify({'status': 'pulling', 'model': model_name})

    @app.route('/api/ai/pull-progress')
    def api_ai_pull_progress():
        return jsonify(ollama.get_pull_progress())

    @app.route('/api/ai/delete', methods=['POST'])
    def api_ai_delete():
        data = request.get_json() or {}
        model_name = data.get('model')
        if not model_name:
            return jsonify({'error': 'No model specified'}), 400
        success = ollama.delete_model(model_name)
        return jsonify({'status': 'deleted' if success else 'error'})

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
                    sit = json.loads(settings_row['value'])
                    sit_parts.append('SITUATION STATUS: ' + ', '.join(f'{k}: {v}' for k, v in sit.items()))
                db_ctx.close()
                if sit_parts:
                    ctx = '\n'.join(sit_parts)
                    system_prompt = (system_prompt + '\n\n' if system_prompt else '') + \
                        f'You have access to the user\'s current preparedness data. Use this to give specific, actionable advice based on their actual situation:\n\n--- Current Situation ---\n{ctx}\n--- End Situation ---'
            except Exception as e:
                log.warning(f'Situation context injection failed: {e}')

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
        return jsonify({'status': 'deleted' if success else 'error'})

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
                            _wizard_state['errors'].append(f'{sid}: {get_download_progress(sid).get("error", "unknown")}')
                except Exception as e:
                    _wizard_state['errors'].append(f'{sid}: {e}')
                done += 1
                _wizard_state['overall_progress'] = int(done / total * 100)
                _wizard_state['completed'].append(sid)

            # Phase 2: Start all installed services
            _wizard_state['phase'] = 'starting'
            _wizard_state['current_item'] = 'Starting services...'
            import time
            for sid in services_list:
                mod = SERVICE_MODULES.get(sid)
                if mod and mod.is_installed() and not mod.running():
                    try:
                        mod.start()
                        time.sleep(2)
                    except Exception as e:
                        _wizard_state['errors'].append(f'Start {sid}: {e}')

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
                    _wizard_state['overall_progress'] = int(done / total * 100)
                    _wizard_state['completed'].append(filename)

                # Restart Kiwix to load new content
                if kiwix.is_installed():
                    try:
                        if kiwix.running():
                            kiwix.stop()
                            time.sleep(1)
                        kiwix.start()
                    except Exception:
                        pass

            # Phase 4: Pull AI models
            if models:
                _wizard_state['phase'] = 'models'
                for model_name in models:
                    _wizard_state.update({'current_item': f'Downloading AI model: {model_name}', 'item_progress': 0})
                    try:
                        if ollama.running():
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
                    _wizard_state['overall_progress'] = int(done / total * 100)
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
            cpu_percent = psutil.cpu_percent(interval=0.5)
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
                'cpu_percent': psutil.cpu_percent(interval=0.3),
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

    @app.route('/api/search')
    def api_unified_search():
        q = request.args.get('q', '').strip()
        if not q:
            return jsonify({'conversations': [], 'notes': [], 'documents': []})
        db = get_db()
        convos = db.execute(
            "SELECT id, title, 'conversation' as type FROM conversations WHERE title LIKE ? OR messages LIKE ? ORDER BY updated_at DESC LIMIT 10",
            (f'%{q}%', f'%{q}%')
        ).fetchall()
        notes = db.execute(
            "SELECT id, title, 'note' as type FROM notes WHERE title LIKE ? OR content LIKE ? ORDER BY updated_at DESC LIMIT 10",
            (f'%{q}%', f'%{q}%')
        ).fetchall()
        docs = db.execute(
            "SELECT id, filename as title, 'document' as type FROM documents WHERE filename LIKE ? AND status = 'ready' ORDER BY created_at DESC LIMIT 10",
            (f'%{q}%',)
        ).fetchall()
        db.close()
        return jsonify({
            'conversations': [dict(r) for r in convos],
            'notes': [dict(r) for r in notes],
            'documents': [dict(r) for r in docs],
        })

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
        {'id': 'us-pacific', 'name': 'Pacific', 'states': 'AK, CA, HI, OR, WA'},
        {'id': 'us-mountain', 'name': 'Mountain', 'states': 'AZ, CO, ID, MT, NV, NM, UT, WY'},
        {'id': 'us-west-north-central', 'name': 'West North Central', 'states': 'IA, KS, MN, MO, NE, ND, SD'},
        {'id': 'us-east-north-central', 'name': 'East North Central', 'states': 'IL, IN, MI, OH, WI'},
        {'id': 'us-west-south-central', 'name': 'West South Central', 'states': 'AR, LA, OK, TX'},
        {'id': 'us-east-south-central', 'name': 'East South Central', 'states': 'AL, KY, MS, TN'},
        {'id': 'us-south-atlantic', 'name': 'South Atlantic', 'states': 'DE, FL, GA, MD, NC, SC, VA, DC, WV'},
        {'id': 'us-middle-atlantic', 'name': 'Middle Atlantic', 'states': 'NJ, NY, PA'},
        {'id': 'us-new-england', 'name': 'New England', 'states': 'CT, ME, MA, NH, RI, VT'},
    ]

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
        files = []
        for f in os.listdir(maps_dir):
            if f.endswith('.pmtiles'):
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
            byte_range = range_header.replace('bytes=', '').split('-')
            start = int(byte_range[0])
            end = int(byte_range[1]) if byte_range[1] else file_size - 1
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

    # ─── Connectivity & Network ───────────────────────────────────────

    @app.route('/api/network')
    def api_network():
        import socket
        online = False
        try:
            socket.create_connection(('1.1.1.1', 443), timeout=3).close()
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
        db = get_db()
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
            'INSERT INTO inventory (name, category, quantity, unit, min_quantity, daily_usage, location, expiration, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (data.get('name', ''), data.get('category', 'other'), data.get('quantity', 0),
             data.get('unit', 'ea'), data.get('min_quantity', 0), data.get('daily_usage', 0),
             data.get('location', ''), data.get('expiration', ''), data.get('notes', '')))
        db.commit()
        item_id = cur.lastrowid
        row = db.execute('SELECT * FROM inventory WHERE id = ?', (item_id,)).fetchone()
        db.close()
        return jsonify(dict(row)), 201

    @app.route('/api/inventory/<int:item_id>', methods=['PUT'])
    def api_inventory_update(item_id):
        data = request.get_json() or {}
        db = get_db()
        allowed = ['name', 'category', 'quantity', 'unit', 'min_quantity', 'daily_usage', 'location', 'expiration', 'notes']
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
            started = datetime.fromisoformat(r['started_at'])
            elapsed = (now - started).total_seconds()
            remaining = max(0, r['duration_sec'] - elapsed)
            result.append({**dict(r), 'remaining_sec': remaining, 'done': remaining <= 0})
        return jsonify(result)

    @app.route('/api/timers', methods=['POST'])
    def api_timers_create():
        data = request.get_json() or {}
        from datetime import datetime
        db = get_db()
        cur = db.execute('INSERT INTO timers (name, duration_sec, started_at) VALUES (?, ?, ?)',
                         (data.get('name', 'Timer'), int(data.get('duration_sec', 300)),
                          datetime.now().isoformat()))
        db.commit()
        row = db.execute('SELECT * FROM timers WHERE id = ?', (cur.lastrowid,)).fetchone()
        db.close()
        return jsonify(dict(row)), 201

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
        content = file.read().decode('utf-8-sig')
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

    @app.route('/api/contacts/import-csv', methods=['POST'])
    def api_contacts_import_csv():
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        import csv, io
        file = request.files['file']
        content = file.read().decode('utf-8-sig')
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

    # ─── Full Data Export ─────────────────────────────────────────────

    @app.route('/api/export-all')
    def api_export_all():
        """Export complete database + settings as a single ZIP."""
        import io
        import zipfile as zf
        from db import get_db_path

        buf = io.BytesIO()
        with zf.ZipFile(buf, 'w', zf.ZIP_DEFLATED) as z:
            db_path = get_db_path()
            if os.path.isfile(db_path):
                z.write(db_path, 'nomad.db')
            # Export config
            from config import get_config_path
            cfg_path = get_config_path()
            if os.path.isfile(cfg_path):
                z.write(cfg_path, 'config.json')
        buf.seek(0)
        from datetime import datetime
        fname = f'nomad-full-backup-{datetime.now().strftime("%Y%m%d-%H%M%S")}.zip'
        return Response(buf.read(), mimetype='application/zip',
                       headers={'Content-Disposition': f'attachment; filename="{fname}"'})

    # ─── Video Library API ─────────────────────────────────────────────

    def get_video_dir():
        path = os.path.join(get_data_dir(), 'videos')
        os.makedirs(path, exist_ok=True)
        return path

    VIDEO_CATEGORIES = ['survival', 'medical', 'repair', 'bushcraft', 'cooking', 'radio', 'farming', 'defense', 'general']

    @app.route('/api/videos')
    def api_videos_list():
        db = get_db()
        rows = db.execute('SELECT * FROM videos ORDER BY category, title').fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

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
        category = request.form.get('category', 'general')
        title = request.form.get('title', filename.rsplit('.', 1)[0])
        db = get_db()
        cur = db.execute('INSERT INTO videos (title, filename, category) VALUES (?, ?, ?)', (title, filename, category))
        db.commit()
        db.close()
        return jsonify({'status': 'uploaded', 'id': cur.lastrowid}), 201

    @app.route('/api/videos/<int:vid>', methods=['DELETE'])
    def api_videos_delete(vid):
        db = get_db()
        row = db.execute('SELECT filename FROM videos WHERE id = ?', (vid,)).fetchone()
        if row:
            filepath = os.path.join(get_video_dir(), row['filename'])
            if os.path.isfile(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
            db.execute('DELETE FROM videos WHERE id = ?', (vid,))
            db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    @app.route('/api/videos/serve/<path:filename>')
    def api_videos_serve(filename):
        vdir = get_video_dir()
        safe = os.path.normpath(os.path.join(vdir, secure_filename(filename)))
        if not safe.startswith(os.path.normpath(vdir)) or not os.path.isfile(safe):
            return jsonify({'error': 'Not found'}), 404
        from flask import send_file
        return send_file(safe)

    @app.route('/api/videos/categories')
    def api_videos_categories():
        return jsonify(VIDEO_CATEGORIES)

    # ─── Sneakernet Sync API ─────────────────────────────────────────

    @app.route('/api/sync/export', methods=['POST'])
    def api_sync_export():
        """Export selected data as a portable content pack ZIP."""
        data = request.get_json() or {}
        include = data.get('include', ['inventory', 'contacts', 'checklists', 'notes', 'incidents', 'waypoints'])
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
                    count = 0
                    for row in rows:
                        row.pop('id', None)
                        row.pop('created_at', None)
                        row.pop('updated_at', None)
                        cols = list(row.keys())
                        vals = list(row.values())
                        placeholders = ','.join(['?'] * len(cols))
                        try:
                            db.execute(f'INSERT INTO {tname} ({",".join(cols)}) VALUES ({placeholders})', vals)
                            count += 1
                        except Exception:
                            pass
                    imported[tname] = count
                db.commit()
                db.close()
                return jsonify({'status': 'imported', 'tables': imported})
        except Exception as e:
            return jsonify({'error': str(e)}), 400

    # ─── Community Sharing API ────────────────────────────────────────

    @app.route('/api/checklists/<int:cid>/export-json')
    def api_checklist_export_json(cid):
        db = get_db()
        row = db.execute('SELECT * FROM checklists WHERE id = ?', (cid,)).fetchone()
        db.close()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        export = {'type': 'nomad_checklist', 'version': 1,
                  'name': row['name'], 'template': row['template'],
                  'items': json.loads(row['items'] or '[]')}
        return Response(json.dumps(export, indent=2), mimetype='application/json',
                       headers={'Content-Disposition': f'attachment; filename="{row["name"]}.json"'})

    @app.route('/api/checklists/import-json', methods=['POST'])
    def api_checklist_import_json():
        if 'file' not in request.files:
            return jsonify({'error': 'No file'}), 400
        file = request.files['file']
        try:
            data = json.loads(file.read().decode('utf-8'))
            if data.get('type') != 'nomad_checklist':
                return jsonify({'error': 'Invalid checklist file'}), 400
            db = get_db()
            cur = db.execute('INSERT INTO checklists (name, template, items) VALUES (?, ?, ?)',
                             (data['name'], data.get('template', 'imported'), json.dumps(data['items'])))
            db.commit()
            db.close()
            return jsonify({'status': 'imported', 'id': cur.lastrowid})
        except Exception as e:
            return jsonify({'error': str(e)}), 400

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
        db.close()
        return jsonify({
            'conversations': [dict(r) for r in convos], 'notes': [dict(r) for r in notes],
            'documents': [dict(r) for r in docs], 'inventory': [dict(r) for r in inv],
            'contacts': [dict(r) for r in contacts], 'checklists': [dict(r) for r in checklists],
        })

    # ─── Favicon ──────────────────────────────────────────────────────

    @app.route('/favicon.ico')
    def favicon():
        svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><polygon points="32,4 60,32 32,60 4,32" fill="#4f9cf7"/><polygon points="32,14 50,32 32,50 14,32" fill="#0d0d0d"/><polygon points="32,22 42,32 32,42 22,32" fill="#4f9cf7"/></svg>'
        return Response(svg, mimetype='image/svg+xml')

    return app
