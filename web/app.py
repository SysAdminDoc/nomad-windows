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
                for attr in ['OLLAMA_PORT', 'KIWIX_PORT', 'CYBERCHEF_PORT', 'KOLIBRI_PORT']:
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
        data = request.get_json()
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
        data = request.get_json()
        model_name = data.get('model')
        if not model_name:
            return jsonify({'error': 'No model specified'}), 400
        success = ollama.delete_model(model_name)
        return jsonify({'status': 'deleted' if success else 'error'})

    @app.route('/api/ai/chat', methods=['POST'])
    def api_ai_chat():
        data = request.get_json()
        model = data.get('model', ollama.DEFAULT_MODEL)
        messages = data.get('messages', [])
        system_prompt = data.get('system_prompt', '')
        use_kb = data.get('knowledge_base', False)

        if not ollama.running():
            return jsonify({'error': 'Ollama is not running'}), 503

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
        data = request.get_json()
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
        data = request.get_json()
        filename = data.get('filename')
        if not filename:
            return jsonify({'error': 'No filename'}), 400
        success = kiwix.delete_zim(filename)
        return jsonify({'status': 'deleted' if success else 'error'})

    # ─── Notes API ─────────────────────────────────────────────────────

    @app.route('/api/notes')
    def api_notes_list():
        db = get_db()
        notes = db.execute('SELECT * FROM notes ORDER BY updated_at DESC').fetchall()
        db.close()
        return jsonify([dict(n) for n in notes])

    @app.route('/api/notes', methods=['POST'])
    def api_notes_create():
        data = request.get_json()
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
        data = request.get_json()
        db = get_db()
        db.execute('UPDATE notes SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                   (data.get('title'), data.get('content'), note_id))
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
        data = request.get_json()
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
        data = request.get_json()
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
        data = request.get_json()
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
        data = request.get_json()
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
                    results['disk_write_score'] = round(written / write_elapsed / (1024 * 1024))

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
        data = request.get_json()
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

        return Response(open(safe_path, 'rb').read(), mimetype='application/octet-stream')

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

        filename = file.filename
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
        data = request.get_json()
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
        data = request.get_json()
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

    # ─── Favicon ──────────────────────────────────────────────────────

    @app.route('/favicon.ico')
    def favicon():
        svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><polygon points="32,4 60,32 32,60 4,32" fill="#4f9cf7"/><polygon points="32,14 50,32 32,50 14,32" fill="#0d0d0d"/><polygon points="32,22 42,32 32,42 22,32" fill="#4f9cf7"/></svg>'
        return Response(svg, mimetype='image/svg+xml')

    return app
