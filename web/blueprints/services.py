"""Service management routes (install, start, stop, restart, uninstall)."""

import os
import sys
import time
import platform
import threading
import logging

from flask import Blueprint, request, jsonify

from db import db_session, log_activity
from services import ollama, kiwix, cyberchef, kolibri, qdrant, stirling, flatnotes
from services.manager import (
    get_download_progress, get_dir_size, format_size, uninstall_service,
    get_services_dir, ensure_dependencies,
)
from web.state import _installing, _installing_lock, _update_state
import web.state as _state

log = logging.getLogger('nomad.web')

SVC_FRIENDLY = {
    'ollama': 'AI Chat', 'kiwix': 'Offline Encyclopedia', 'cyberchef': 'Data Toolkit',
    'kolibri': 'Education Platform', 'qdrant': 'Document Search', 'stirling': 'PDF Tools',
    'flatnotes': 'Notes App',
}

SERVICE_MODULES = {
    'ollama': ollama,
    'kiwix': kiwix,
    'cyberchef': cyberchef,
    'kolibri': kolibri,
    'qdrant': qdrant,
    'stirling': stirling,
    'flatnotes': flatnotes,
}

services_bp = Blueprint('services', __name__)

@services_bp.route('/api/services')
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

@services_bp.route('/api/services/<service_id>/install', methods=['POST'])
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

@services_bp.route('/api/services/<service_id>/start', methods=['POST'])
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
        log.exception('Service start failed for %s', service_id)
        return jsonify({'error': 'Service start failed'}), 500

@services_bp.route('/api/services/<service_id>/stop', methods=['POST'])
def api_stop_service(service_id):
    mod = SERVICE_MODULES.get(service_id)
    if not mod:
        return jsonify({'error': 'Unknown service'}), 404
    try:
        mod.stop()
        return jsonify({'status': 'stopped'})
    except Exception as e:
        log.exception('Service stop failed for %s', service_id)
        return jsonify({'error': 'Service stop failed'}), 500

@services_bp.route('/api/services/<service_id>/restart', methods=['POST'])
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
        log.exception('Service restart failed for %s', service_id)
        return jsonify({'error': 'Service restart failed'}), 500

@services_bp.route('/api/services/<service_id>/uninstall', methods=['POST'])
def api_uninstall_service(service_id):
    if service_id not in SERVICE_MODULES:
        return jsonify({'error': 'Unknown service'}), 404
    try:
        uninstall_service(service_id)
        return jsonify({'status': 'uninstalled'})
    except Exception as e:
        log.exception('Uninstall failed for %s', service_id)
        return jsonify({'error': 'Uninstall failed'}), 500

@services_bp.route('/api/services/start-all', methods=['POST'])
def api_start_all():
    started = []
    errors = []
    for sid, mod in SERVICE_MODULES.items():
        if mod.is_installed() and not mod.running():
            try:
                mod.start()
                started.append(sid)
            except Exception as e:
                log.exception('Start failed for %s', sid)
                errors.append(f'{sid}: start failed')
    return jsonify({'started': started, 'errors': errors})

@services_bp.route('/api/services/stop-all', methods=['POST'])
def api_stop_all():
    stopped = []
    errors = []
    for sid, mod in SERVICE_MODULES.items():
        if mod.is_installed() and mod.running():
            try:
                mod.stop()
                stopped.append(sid)
            except Exception as e:
                log.exception('Stop failed for %s', sid)
                errors.append(f'{sid}: stop failed')
    return jsonify({'stopped': stopped, 'errors': errors})

@services_bp.route('/api/services/<service_id>/progress')
def api_service_progress(service_id):
    return jsonify(get_download_progress(service_id))

@services_bp.route('/api/services/<service_id>/prereqs')
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

@services_bp.route('/api/services/health-summary')
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
    with db_session() as db:
        recent_crashes = db.execute("SELECT service, COUNT(*) as c FROM activity_log WHERE event = 'service_crash_detected' AND created_at >= datetime('now', '-24 hours') GROUP BY service").fetchall()
        recent_restarts = db.execute("SELECT service, COUNT(*) as c FROM activity_log WHERE event = 'service_autorestarted' AND created_at >= datetime('now', '-24 hours') GROUP BY service").fetchall()
    crash_map = {r['service']: r['c'] for r in recent_crashes}
    restart_map = {r['service']: r['c'] for r in recent_restarts}
    for s in services:
        s['crashes_24h'] = crash_map.get(s['id'], 0)
        s['restarts_24h'] = restart_map.get(s['id'], 0)
    return jsonify(services)

@services_bp.route('/api/downloads/active')
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

@services_bp.route('/api/services/<service_id>/logs')
def api_service_logs(service_id):
    """Return captured stdout/stderr log lines for a service."""
    from services.manager import _service_logs
    lines = _service_logs.get(service_id, [])
    tail = request.args.get('tail', 100, type=int)
    return jsonify({'service': service_id, 'lines': lines[-tail:]})

@services_bp.route('/api/services/logs/all')
def api_service_logs_all():
    """Return log line counts for all services."""
    from services.manager import _service_logs
    return jsonify({sid: len(lines) for sid, lines in _service_logs.items()})


@services_bp.route('/api/update-download', methods=['POST'])
def api_update_download():
    """Download the latest release from GitHub."""
    def do_update():
        _state._update_state = {'status': 'checking', 'progress': 0, 'error': None, 'path': None}
        try:
            import requests as rq
            resp = rq.get('https://api.github.com/repos/SysAdminDoc/project-nomad-desktop/releases/latest', timeout=15)
            if not resp.ok:
                _state._update_state = {'status': 'error', 'progress': 0, 'error': 'Cannot reach GitHub', 'path': None}
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
                _state._update_state = {'status': 'error', 'progress': 0, 'error': 'No download found for your platform', 'path': None}
                return

            _state._update_state['status'] = 'downloading'
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
                    _state._update_state['progress'] = int(downloaded / total * 100) if total > 0 else 0

            _state._update_state = {'status': 'complete', 'progress': 100, 'error': None, 'path': dest}
            log_activity('update_downloaded', detail=f'{data.get("tag_name", "?")} → {fname}')

        except Exception as e:
            log.exception('Update download failed')
            _state._update_state = {'status': 'error', 'progress': 0, 'error': 'Update download failed', 'path': None}

    threading.Thread(target=do_update, daemon=True).start()
    return jsonify({'status': 'started'})

@services_bp.route('/api/update-download/status')
def api_update_download_status():
    return jsonify(_state._update_state)

@services_bp.route('/api/update-download/open', methods=['POST'])
def api_update_download_open():
    """Open the downloaded update file."""
    path = _state._update_state.get('path')
    if not path or not os.path.isfile(path):
        return jsonify({'error': 'No update downloaded'}), 404
    from platform_utils import open_folder
    open_folder(os.path.dirname(path))
    return jsonify({'status': 'opened', 'path': path})

# ─── Task Scheduler Engine (Phase 15) ───────────────────────────

