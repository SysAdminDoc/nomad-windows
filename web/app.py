"""Flask web application — dashboard and API routes."""

import json
import os
import threading
import platform
import logging
import shutil
from flask import Flask, render_template, jsonify, request, Response

from db import get_db
from services import ollama, kiwix, cyberchef
from services.manager import (
    get_download_progress, get_dir_size, format_size, uninstall_service, get_services_dir
)

log = logging.getLogger('nomad.web')

SERVICE_MODULES = {
    'ollama': ollama,
    'kiwix': kiwix,
    'cyberchef': cyberchef,
}

VERSION = '0.2.0'


def create_app():
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')

    # ─── Pages ─────────────────────────────────────────────────────────

    @app.route('/')
    def dashboard():
        return render_template('index.html')

    # ─── Service API ───────────────────────────────────────────────────

    @app.route('/api/services')
    def api_services():
        """Get status of all services with disk usage."""
        services = []
        for sid, mod in SERVICE_MODULES.items():
            installed = mod.is_installed()
            install_dir = os.path.join(get_services_dir(), sid)
            disk_used = format_size(get_dir_size(install_dir)) if installed else '0 B'

            port_val = getattr(mod, f'{sid.upper()}_PORT', None)
            if port_val is None:
                port_val = getattr(mod, 'OLLAMA_PORT', None) or getattr(mod, 'KIWIX_PORT', None) or getattr(mod, 'CYBERCHEF_PORT', None)

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
            mod.start()
            return jsonify({'status': 'started'})
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
            import time
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

        if not ollama.running():
            return jsonify({'error': 'Ollama is not running'}), 503

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

    # ─── Kiwix ZIM API ─────────────────────────────────────────────────

    @app.route('/api/kiwix/zims')
    def api_kiwix_zims():
        if not kiwix.is_installed():
            return jsonify([])
        return jsonify(kiwix.list_zim_files())

    @app.route('/api/kiwix/catalog')
    def api_kiwix_catalog():
        """Get curated ZIM catalog for download."""
        return jsonify(kiwix.get_catalog())

    @app.route('/api/kiwix/download-zim', methods=['POST'])
    def api_kiwix_download_zim():
        data = request.get_json()
        url = data.get('url', kiwix.STARTER_ZIM_URL)
        filename = data.get('filename')

        def do_download():
            try:
                kiwix.download_zim(url, filename)
            except Exception as e:
                log.error(f'ZIM download failed: {e}')

        threading.Thread(target=do_download, daemon=True).start()
        return jsonify({'status': 'downloading'})

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
        settings = {r['key']: r['value'] for r in rows}
        return jsonify(settings)

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

    # ─── System Info ───────────────────────────────────────────────────

    @app.route('/api/system')
    def api_system():
        import psutil
        data_dir = os.path.join(os.environ.get('APPDATA', ''), 'ProjectNOMAD')
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
            cpu_count = psutil.cpu_count()
            cpu_name = platform.processor()
        except Exception:
            mem = None
            cpu_count = os.cpu_count()
            cpu_name = platform.processor()

        # GPU detection
        gpu_name = 'None detected'
        try:
            import subprocess
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                capture_output=True, text=True, timeout=5, creationflags=0x08000000,
            )
            if result.returncode == 0 and result.stdout.strip():
                gpu_name = result.stdout.strip()
        except Exception:
            pass

        return jsonify({
            'version': VERSION,
            'platform': f'{platform.system()} {platform.release()}',
            'cpu': cpu_name or f'{cpu_count} cores',
            'cpu_cores': cpu_count,
            'ram_total': format_size(mem.total) if mem else 'Unknown',
            'ram_used': format_size(mem.used) if mem else 'Unknown',
            'ram_percent': mem.percent if mem else 0,
            'gpu': gpu_name,
            'data_dir': data_dir,
            'nomad_disk_used': format_size(total_disk),
            'disk_free': format_size(disk_free),
            'disk_total': format_size(disk_total),
        })

    # ─── Health ────────────────────────────────────────────────────────

    @app.route('/api/health')
    def api_health():
        return jsonify({'status': 'ok', 'version': VERSION})

    return app
