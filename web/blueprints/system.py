"""System info, settings, wizard, dashboard, backup, startup, and admin routes."""

import json
import os
import sys
import time
import shutil
import platform
import threading
import logging

from flask import Blueprint, request, jsonify, Response

from web.blueprints import error_response
from db import get_db_path, db_session, log_activity
from config import APP_DISPLAY_NAME, APP_EXECUTABLE_BASENAME, APP_STORAGE_DIRNAME, get_data_dir, set_data_dir
from platform_utils import get_data_base
from services import ollama, kiwix, cyberchef, kolibri, qdrant, stirling, flatnotes
from services.manager import (
    get_download_progress, get_dir_size, format_size,
    get_services_dir, ensure_dependencies, is_running,
    get_service_resources, SERVICE_HEALTH_URLS, is_healthy,
)
import config
from web.auth import require_auth
from web.utils import (
    clone_json_fallback as _clone_json_fallback,
    get_query_int as _get_query_int,
    hash_local_secret as _hash_local_secret,
    local_secret_needs_rehash as _local_secret_needs_rehash,
    require_json_body as _require_json_body,
    safe_json_value as _safe_json_value,
    verify_local_secret as _verify_local_secret,
)
from web.state import (
    _auto_backup_timer,
    _update_state,
    broadcast_event,
    wizard_append_list_item,
    wizard_reset,
    wizard_snapshot,
    wizard_update,
)
import web.state as _state

log = logging.getLogger('nomad.web')


def _format_host_for_url(host):
    host = (host or '').strip()
    if ':' in host and not host.startswith('['):
        return f'[{host}]'
    return host


def _to_int(value, default=0):
    """Safe int conversion that returns default on ValueError/TypeError."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _safe_response_json(response, fallback=None):
    if fallback is None:
        fallback = {}
    try:
        parsed = response.json()
    except Exception:
        return _clone_json_fallback(fallback)
    if isinstance(parsed, (dict, list)):
        return parsed
    return _clone_json_fallback(fallback)

STARTUP_VALUE_NAME = APP_EXECUTABLE_BASENAME
LEGACY_STARTUP_VALUE_NAMES = ('ProjectNOMAD',)
MAC_AUTOSTART_LABEL = 'com.sysadmindoc.nomadfielddesk'
LEGACY_MAC_AUTOSTART_LABEL = 'com.sysadmindoc.projectnomad'
LINUX_AUTOSTART_FILENAME = f'{APP_EXECUTABLE_BASENAME}.desktop'
LEGACY_LINUX_AUTOSTART_FILENAMES = ('ProjectNOMAD.desktop',)


def _get_version():
    """Get VERSION from the main app module (lazy import to avoid circular deps)."""
    import web.app as _app
    return _app.VERSION

SERVICE_MODULES = {
    'ollama': ollama,
    'kiwix': kiwix,
    'cyberchef': cyberchef,
    'kolibri': kolibri,
    'qdrant': qdrant,
    'stirling': stirling,
    'flatnotes': flatnotes,
}

# These module-level vars are accessed by system routes
_benchmark_state = {'status': 'idle', 'progress': 0, 'stage': '', 'results': None}

# _cpu_percent is maintained by the CPU monitor thread started in web.app.create_app().
# Import it from web.app so there is only one monitor thread.

def _get_cpu_percent():
    """Lazy accessor for app-level _cpu_percent to avoid circular imports."""
    import web.app as _app
    return _app._cpu_percent

system_bp = Blueprint('system', __name__)

_app_start_time = time.time()


@system_bp.route('/healthz')
def api_healthz():
    """Lightweight health check for external monitors (UptimeKuma, Prometheus)."""
    db_ok = False
    try:
        with db_session() as db:
            db.execute('SELECT 1').fetchone()
            db_ok = True
    except Exception:
        pass
    running_count = sum(1 for mod in (ollama, kiwix, cyberchef, kolibri, qdrant, stirling, flatnotes) if mod.is_installed() and mod.running())
    status = 'healthy' if db_ok else 'degraded'
    code = 200 if db_ok else 503
    return jsonify({
        'status': status,
        'version': config.Config.VERSION,
        'uptime': int(time.time() - _app_start_time),
        'db_ok': db_ok,
        'services_running': running_count,
    }), code


@system_bp.route('/api/settings')
def api_settings():
    with db_session() as db:
        rows = db.execute('SELECT key, value FROM settings').fetchall()
    return jsonify({r['key']: r['value'] for r in rows})

SETTINGS_WHITELIST = {
    'dashboard_mode', 'node_name', 'node_id', 'theme', 'sidebar_collapsed',
    'map_style', 'map_center', 'map_zoom', 'ai_model', 'ai_system_prompt',
    'ai_memory_enabled', 'ai_memory', 'wizard_tier', 'first_run_complete',
    'lan_name', 'lan_sharing', 'lan_password_enabled', 'workspace_memory',
    'household_size', 'location', 'timezone', 'units',
    # Home coordinates + proximity radius — used by weather, sun calc, and
    # the Situation Room "Proximity Board" to filter global feeds to threats
    # within a given distance of the user's location.
    'latitude', 'longitude', 'proximity_radius_km',
    # Emergency Mode state — managed by /api/emergency/enter and /exit,
    # whitelisted here so a factory-reset / config-restore round-trip
    # can include them.
    'emergency_active', 'emergency_started_at', 'emergency_reason',
    'emergency_incident_id',
}

@system_bp.route('/api/settings', methods=['PUT'])
def api_settings_update():
    data = request.get_json() or {}
    with db_session() as db:
        rejected = [key for key in data if key not in SETTINGS_WHITELIST]
        allowed = [(key, str(value)) for key, value in data.items() if key in SETTINGS_WHITELIST]
        if allowed:
            db.executemany('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', allowed)
        db.commit()
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

@system_bp.route('/api/dashboard/mode')
def api_dashboard_mode():
    with db_session() as db:
        row = db.execute("SELECT value FROM settings WHERE key = 'dashboard_mode'").fetchone()
    mode = row['value'] if row else 'command'
    if mode not in DASHBOARD_MODES:
        mode = 'command'
    return jsonify({'mode': mode, 'config': DASHBOARD_MODES[mode], 'available': {k: {'label': v['label'], 'desc': v['desc'], 'icon': v['icon']} for k, v in DASHBOARD_MODES.items()}})

@system_bp.route('/api/settings/wizard-complete', methods=['POST'])
def api_wizard_complete():
    with db_session() as db:
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('first_run_complete', '1')")
        db.commit()
    return jsonify({'status': 'ok'})

# ─── Drives API ───────────────────────────────────────────────────

@system_bp.route('/api/drives')
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
                pass  # individual mountpoint may be unavailable (network drive, etc.)
    except Exception as e:
        log.debug('disk_partitions failed: %s', e)

@system_bp.route('/api/settings/data-dir', methods=['POST'])
def api_set_data_dir():
    """Set custom data directory (wizard only)."""
    data = request.get_json() or {}
    path = data.get('path', '')
    if not path:
        return error_response('No path provided')
    try:
        full_path = os.path.join(path, APP_STORAGE_DIRNAME)
        os.makedirs(full_path, exist_ok=True)
        # Test write
        test_file = os.path.join(full_path, '.write_test')
        with open(test_file, 'w') as f:
            f.write('ok')
        os.remove(test_file)
        set_data_dir(full_path)
        return jsonify({'status': 'ok', 'path': full_path})
    except Exception as e:
        return error_response(f'Cannot write to {path}: {e}')


# ─── Wizard Setup API ─────────────────────────────────────────────

@system_bp.route('/api/wizard/setup', methods=['POST'])
def api_wizard_setup():
    """Full turnkey setup — installs services, downloads content, pulls models."""
    # Guard: prevent re-triggering if wizard is already running or setup is complete
    snap = wizard_snapshot()
    if snap.get('status') == 'running':
        return jsonify({'error': 'Wizard is already running'}), 409
    with db_session() as _chk:
        _fr = _chk.execute("SELECT value FROM settings WHERE key = 'first_run_complete'").fetchone()
        if _fr and _fr['value'] == '1':
            return jsonify({'error': 'First-run setup already completed. Use individual service controls to make changes.'}), 400

    data = request.get_json() or {}
    services_list = data.get('services', ['ollama', 'kiwix', 'cyberchef', 'stirling'])
    zims = data.get('zims', [])
    models = data.get('models', ['llama3.2:3b'])

    def do_setup():
      try:
        total = len(services_list) + len(zims) + len(models)
        wizard_reset(status='running', phase='services', total_items=total, overall_progress=0)
        done = 0

        # Phase 1: Install services
        for sid in services_list:
            mod = SERVICE_MODULES.get(sid)
            if not mod:
                continue
            wizard_update(current_item=f'Installing {SVC_FRIENDLY.get(sid, sid)}', item_progress=0)
            try:
                if not mod.is_installed():
                    mod.install()
                    # Wait for install to complete
                    import time
                    for _ in range(300):
                        p = get_download_progress(sid)
                        wizard_update(item_progress=p.get('percent', 0))
                        if p.get('status') in ('complete', 'error'):
                            break
                        time.sleep(1)
                    if get_download_progress(sid).get('status') == 'error':
                        err_msg = get_download_progress(sid).get("error", "unknown")
                        wizard_append_list_item('errors', f'{sid}: Download failed — {err_msg}. You can retry from the Home tab.')
            except Exception as e:
                wizard_append_list_item('errors', f'{sid}: Setup failed — check your internet connection and try again from the Home tab.')
            done += 1
            wizard_update(overall_progress=int(done / total * 100) if total > 0 else 100)
            wizard_append_list_item('completed', sid)

        # Phase 2: Start services that CAN start now (skip Kiwix — needs content first)
        wizard_update(phase='starting')
        import time
        for sid in services_list:
            if sid == 'kiwix':
                continue  # Kiwix needs ZIM files before it can start — handled after downloads
            mod = SERVICE_MODULES.get(sid)
            if mod and mod.is_installed() and not mod.running():
                wizard_update(current_item=f'Starting {SVC_FRIENDLY.get(sid, sid)}...')
                try:
                    mod.start()
                    time.sleep(2)
                except Exception as e:
                    # Non-fatal — service may need prerequisites, will auto-start later
                    log.warning(f'Wizard: non-fatal start error for {sid}: {e}')

        # Phase 3: Download ZIM content
        if zims:
            wizard_update(phase='content')
            for zim in zims:
                url = zim.get('url', '')
                filename = zim.get('filename', '')
                name = zim.get('name', filename)
                wizard_update(current_item=f'Downloading {name}', item_progress=0)
                try:
                    kiwix.download_zim(url, filename)
                    # Poll progress
                    prog_key = f'kiwix-zim-{filename}'
                    for _ in range(7200):  # up to 2 hours per ZIM
                        p = get_download_progress(prog_key)
                        wizard_update(item_progress=p.get('percent', 0))
                        if p.get('status') in ('complete', 'error'):
                            break
                        time.sleep(1)
                except Exception as e:
                    wizard_append_list_item('errors', f'ZIM {filename}: {e}')
                done += 1
                wizard_update(overall_progress=int(done / total * 100) if total > 0 else 100)
                wizard_append_list_item('completed', filename)

            # NOW start Kiwix — it has content to serve
            wizard_update(current_item='Starting Kiwix with downloaded content...')
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
            wizard_update(current_item='Kiwix installed (add content from Library tab to start it)')

        # Phase 4: Pull AI models
        if models:
            wizard_update(phase='models')
            for model_name in models:
                wizard_update(current_item=f'Downloading AI model: {model_name}', item_progress=0)
                try:
                    if not ollama.running():
                        wizard_append_list_item('errors', f'Model {model_name}: Skipped — AI service is not running. Start it from the Services tab and download models from AI Chat.')
                    else:
                        ollama.pull_model(model_name)
                        # Poll pull progress
                        for _ in range(3600):
                            p = ollama.get_pull_progress()
                            wizard_update(item_progress=p.get('percent', 0))
                            if p.get('status') in ('complete', 'error'):
                                break
                            time.sleep(1)
                except Exception as e:
                    wizard_append_list_item('errors', f'Model {model_name}: {e}')
                done += 1
                wizard_update(overall_progress=int(done / total * 100) if total > 0 else 100)
                wizard_append_list_item('completed', model_name)

        # Mark wizard complete
        with db_session() as db:
            db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('first_run_complete', '1')")
            db.commit()
        wizard_update(status='complete', phase='done', overall_progress=100, current_item='Setup complete!')
      except Exception as e:
        # Catch-all so the wizard thread never dies silently — the user sees
        # an error state instead of being stuck on "running" forever.
        log.exception(f'Wizard setup crashed: {e}')
        wizard_append_list_item('errors', f'Setup process crashed: {type(e).__name__}: {e}')
        wizard_update(status='error', phase='failed', current_item='Setup failed — see errors above')

    threading.Thread(target=do_setup, daemon=True).start()
    return jsonify({'status': 'started'})

@system_bp.route('/api/wizard/progress')
def api_wizard_progress():
    return jsonify(wizard_snapshot())

@system_bp.route('/api/content-tiers')
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

@system_bp.route('/api/system')
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
        cpu_percent = _get_cpu_percent()  # non-blocking, from background monitor
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

    # CPU/GPU temperature (P4-13)
    cpu_temp = None
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for name in ('coretemp', 'k10temp', 'cpu_thermal', 'acpitz'):
                if name in temps and temps[name]:
                    cpu_temp = round(temps[name][0].current, 1)
                    break
            if cpu_temp is None:
                first = next(iter(temps.values()), [])
                if first:
                    cpu_temp = round(first[0].current, 1)
    except (AttributeError, Exception):
        pass  # sensors_temperatures() not available on Windows/macOS

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
                pass  # individual mountpoint may be unavailable
    except Exception as e:
        log.debug('disk_partitions failed: %s', e)
    try:
        uptime_secs = time.time() - psutil.boot_time()
        days = int(uptime_secs // 86400)
        hours = int((uptime_secs % 86400) // 3600)
        mins = int((uptime_secs % 3600) // 60)
        uptime_str = f'{days}d {hours}h {mins}m' if days else f'{hours}h {mins}m'
    except Exception:
        uptime_str = 'Unknown'

    return jsonify({
        'version': _get_version(),
        'platform': f'{platform.system()} {platform.release()}',
        'os_version': platform.version(),
        'hostname': platform.node(),
        'arch': platform.machine(),
        'cpu': cpu_name or f'{cpu_count} cores',
        'cpu_cores': cpu_count,
        'cpu_cores_physical': cpu_count_phys,
        'cpu_percent': cpu_percent,
        'cpu_temp': cpu_temp,
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

@system_bp.route('/api/system/live')
def api_system_live():
    """Lightweight live metrics for real-time gauges."""
    import psutil
    try:
        return jsonify({
            'cpu_percent': _get_cpu_percent(),  # non-blocking, from background monitor
            'ram_percent': psutil.virtual_memory().percent,
            'swap_percent': psutil.swap_memory().percent,
        })
    except Exception:
        return jsonify({'cpu_percent': 0, 'ram_percent': 0, 'swap_percent': 0})


@system_bp.route('/api/content-summary')
def api_content_summary():
    """Human-readable summary of offline knowledge capacity."""
    with db_session() as db:
        row = db.execute('''SELECT
            (SELECT COUNT(*) FROM conversations) as convos,
            (SELECT COUNT(*) FROM notes) as notes,
            (SELECT COUNT(*) FROM documents WHERE status = 'ready') as docs,
            (SELECT COALESCE(SUM(chunks_count), 0) FROM documents WHERE status = 'ready') as chunks
        ''').fetchone()
        convo_count, note_count, doc_count, doc_chunks = row['convos'], row['notes'], row['docs'], row['chunks']
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

@system_bp.route('/api/network')
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

    bind_host = getattr(config.Config, 'APP_HOST', '127.0.0.1') or '127.0.0.1'
    bind_port = getattr(config.Config, 'APP_PORT', 8080) or 8080
    dashboard_host = bind_host if bind_host in {'127.0.0.1', 'localhost', '::1'} else lan_ip
    return jsonify({
        'online': online,
        'lan_ip': lan_ip,
        'dashboard_url': f'http://{_format_host_for_url(dashboard_host)}:{bind_port}',
    })

# [EXTRACTED to blueprint] KB upload/documents/status/search + helpers


# ─── Activity Log ──────────────────────────────────────────────────

@system_bp.route('/api/activity')
def api_activity():
    limit = _get_query_int(request, 'limit', 50, minimum=1, maximum=500)
    filter_val = request.args.get('filter', '')
    with db_session() as db:
        if filter_val:
            rows = db.execute('SELECT * FROM activity_log WHERE event LIKE ? OR service LIKE ? ORDER BY created_at DESC LIMIT ?',
                              (f'%{filter_val}%', f'%{filter_val}%', limit)).fetchall()
        else:
            rows = db.execute('SELECT * FROM activity_log ORDER BY created_at DESC LIMIT ?', (limit,)).fetchall()
    return jsonify([dict(r) for r in rows])

# ─── GPU Info ──────────────────────────────────────────────────────

@system_bp.route('/api/gpu')
def api_gpu():
    from platform_utils import detect_gpu as _detect_gpu
    return jsonify(_detect_gpu())

# ─── Health ────────────────────────────────────────────────────────

@system_bp.route('/api/health')
def api_health():
    return jsonify({'status': 'ok', 'version': _get_version()})

# ─── Update Checker ───────────────────────────────────────────────

@system_bp.route('/api/update-check')
def api_update_check():
    """Check GitHub for newer release."""
    try:
        import requests as rq
        resp = rq.get('https://api.github.com/repos/SysAdminDoc/project-nomad-desktop/releases/latest', timeout=5)
        if resp.ok:
            data = _safe_response_json(resp, {})
            if not isinstance(data, dict):
                raise ValueError('Malformed release metadata')
            latest = str(data.get('tag_name', '') or '').lstrip('v')
            current = _get_version()
            if not latest:
                return jsonify({
                    'current': current,
                    'latest': current,
                    'update_available': False,
                    'download_url': data.get('html_url', ''),
                    'release_name': data.get('name', ''),
                })
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
    return jsonify({'current': _get_version(), 'latest': _get_version(), 'update_available': False})

# ─── Startup Toggle (Cross-Platform) ─────────────────────────────

def _get_autostart_path():
    """Get the platform-specific autostart file/registry path."""
    if sys.platform == 'win32':
        return 'registry'
    elif sys.platform == 'darwin':
        return os.path.expanduser(f'~/Library/LaunchAgents/{MAC_AUTOSTART_LABEL}.plist')
    else:  # Linux
        xdg = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
        return os.path.join(xdg, 'autostart', LINUX_AUTOSTART_FILENAME)


def _get_legacy_autostart_paths():
    if sys.platform == 'win32':
        return list(LEGACY_STARTUP_VALUE_NAMES)
    if sys.platform == 'darwin':
        return [os.path.expanduser(f'~/Library/LaunchAgents/{LEGACY_MAC_AUTOSTART_LABEL}.plist')]
    xdg = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
    return [os.path.join(xdg, 'autostart', name) for name in LEGACY_LINUX_AUTOSTART_FILENAMES]

@system_bp.route('/api/startup')
def api_startup_get():
    """Check if app is set to start at login (cross-platform)."""
    try:
        if sys.platform == 'win32':
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r'Software\Microsoft\Windows\CurrentVersion\Run', 0, winreg.KEY_READ)
            try:
                for value_name in (STARTUP_VALUE_NAME, *LEGACY_STARTUP_VALUE_NAMES):
                    try:
                        winreg.QueryValueEx(key, value_name)
                        return jsonify({'enabled': True, 'platform': 'windows'})
                    except FileNotFoundError:
                        continue
            finally:
                winreg.CloseKey(key)
            return jsonify({'enabled': False, 'platform': 'windows'})
        else:
            path = _get_autostart_path()
            enabled = os.path.isfile(path) or any(os.path.isfile(p) for p in _get_legacy_autostart_paths())
            return jsonify({'enabled': enabled, 'platform': sys.platform})
    except Exception:
        return jsonify({'enabled': False, 'platform': sys.platform})

@system_bp.route('/api/startup', methods=['PUT'])
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
                    winreg.SetValueEx(key, STARTUP_VALUE_NAME, 0, winreg.REG_SZ, f'"{exe_path}"')
                else:
                    winreg.SetValueEx(key, STARTUP_VALUE_NAME, 0, winreg.REG_SZ, f'"{sys.executable}" "{exe_path}"')
            else:
                for value_name in (STARTUP_VALUE_NAME, *LEGACY_STARTUP_VALUE_NAMES):
                    try:
                        winreg.DeleteValue(key, value_name)
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
<string>{MAC_AUTOSTART_LABEL}</string>
<key>ProgramArguments</key>
<array>
    {program_args}
</array>
<key>RunAtLoad</key>
<true/>
</dict>
</plist>''')
            else:
                for candidate in [plist_path, *_get_legacy_autostart_paths()]:
                    if os.path.isfile(candidate):
                        os.remove(candidate)

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
Name={APP_DISPLAY_NAME}
Comment=Desktop-first offline preparedness and field operations workspace
Exec={exec_line}
Terminal=false
X-GNOME-Autostart-enabled=true
''')
            else:
                for candidate in [desktop_path, *_get_legacy_autostart_paths()]:
                    if os.path.isfile(candidate):
                        os.remove(candidate)

        return jsonify({'status': 'ok', 'enabled': enabled})
    except Exception as e:
        log.exception('Startup toggle failed')
        return jsonify({'error': 'Failed to toggle startup'}), 500

# ─── Export / Import Config ───────────────────────────────────────

@system_bp.route('/api/export-config')
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
        log.exception('Export config failed')
        return jsonify({'error': 'Export failed'}), 500

@system_bp.route('/api/import-config', methods=['POST'])
def api_import_config():
    """Import a config backup ZIP."""
    import zipfile as zf
    import io
    from db import get_db_path

    if 'file' not in request.files:
        return error_response('No file provided')
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
                return error_response('Invalid backup file')
    except Exception as e:
        log.exception('Config restore failed')
        return error_response('Restore failed', 500)

# ─── Database Restore from Auto-Backups ──────────────────────────

@system_bp.route('/api/backups')
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

@system_bp.route('/api/backups/restore', methods=['POST'])
def api_backups_restore():
    """Restore database from an automatic backup file.

    Two-phase commit: without ``confirmed: true`` the endpoint returns a
    preview describing exactly what would happen (source file, size, and the
    fact that the current DB will be auto-backed-up). The restore only runs
    when ``confirmed: true`` is sent, preventing accidental data loss from a
    misclick. The current DB is *always* backed up before the replace.
    """
    from db import get_db_path, backup_db
    data = request.get_json() or {}
    filename = data.get('filename', '')
    confirmed = bool(data.get('confirmed'))
    # Use basename to strip any path components — safer than a character blacklist
    filename = os.path.basename(filename) if filename else ''
    if not filename:
        return jsonify({'error': 'Invalid filename'}), 400
    backup_dir = os.path.join(os.path.dirname(get_db_path()), 'backups')
    backup_path = os.path.join(backup_dir, filename)
    if not os.path.isfile(backup_path):
        return jsonify({'error': 'Backup not found'}), 404

    if not confirmed:
        try:
            size_bytes = os.path.getsize(backup_path)
        except OSError:
            size_bytes = 0
        return jsonify({
            'status': 'preview',
            'requires_confirmation': True,
            'filename': filename,
            'size_bytes': size_bytes,
            'current_db_will_be_backed_up': True,
            'message': (
                f'Restoring "{filename}" will overwrite your current database. '
                'The current database will be automatically backed up first. '
                'Re-POST with "confirmed": true to proceed.'
            ),
        })

    # Safety: back up current DB first
    backup_db()
    # Replace current DB with backup
    import shutil
    db_path = get_db_path()
    shutil.copy2(backup_path, db_path)
    log_activity('database_restored', detail=f'Restored from {filename}')
    return jsonify({'status': 'ok', 'message': f'Database restored from {filename}. Restart app to fully apply.'})


@system_bp.route('/api/backup', methods=['POST'])
def api_backup_create_simple():
    """Create an immediate database backup."""
    try:
        from db import backup_db
        backup_db()
        # Find the most recent backup to return its path
        backup_dir = os.path.join(os.path.dirname(get_db_path()), 'backups')
        if os.path.isdir(backup_dir):
            files = sorted(
                [f for f in os.listdir(backup_dir) if f.endswith('.db')],
                key=lambda f: os.path.getmtime(os.path.join(backup_dir, f)),
                reverse=True,
            )
            if files:
                return jsonify({'ok': True, 'path': os.path.join(backup_dir, files[0])})
        return jsonify({'ok': True, 'path': ''})
    except Exception as e:
        log.exception('Backup failed')
        return jsonify({'ok': False, 'error': 'Backup failed'}), 500


@system_bp.route('/api/backup/restore', methods=['POST'])
def api_backup_restore_alt():
    """Alias for /api/backups/restore — accepts {"filename": "..."}."""
    import re
    from db import backup_db as _backup_db
    data = request.get_json() or {}
    filename = data.get('filename', '')
    if not filename or not re.match(r'^[\w.]+$', filename):
        return jsonify({'error': 'Invalid filename'}), 400
    backup_dir = os.path.join(os.path.dirname(get_db_path()), 'backups')
    backup_path = os.path.join(backup_dir, filename)
    if not os.path.isfile(backup_path):
        return jsonify({'error': 'Backup not found'}), 404
    try:
        _backup_db()
        shutil.copy2(backup_path, get_db_path())
        log_activity('database_restored', detail=f'Restored from {filename}')
        return jsonify({'ok': True, 'message': 'Restart the app to complete restore'})
    except Exception as e:
        log.exception('Restore failed')
        return jsonify({'ok': False, 'error': 'Restore failed'}), 500


@system_bp.route('/api/logs')
def api_logs():
    """Return the last N lines of the application log file.

    The launcher writes to ``{data_dir}/logs/nomad.log`` — the previous
    version looked in ``{data_dir}/nomad.log`` and always returned
    "Log file not found" to the Settings panel.
    """
    try:
        lines_requested = min(int(request.args.get('lines', 100)), 500)
    except (ValueError, TypeError):
        lines_requested = 100
    try:
        data_dir = get_data_dir()
        # Primary location (matches nomad.py's RotatingFileHandler path).
        candidates = [
            os.path.join(data_dir, 'logs', 'nomad.log'),
            os.path.join(data_dir, 'nomad.log'),
        ]
        log_path = next((p for p in candidates if os.path.isfile(p)), candidates[0])
        if not os.path.isfile(log_path):
            return jsonify({'lines': [], 'path': log_path, 'error': 'Log file not found'})
        with open(log_path, 'r', errors='replace') as f:
            all_lines = f.readlines()
        tail = [l.rstrip('\n') for l in all_lines[-lines_requested:]]
        return jsonify({'lines': tail, 'path': log_path})
    except Exception as e:
        log.exception('Log read failed')
        return jsonify({'lines': [], 'error': 'Failed to read logs'}), 500


@system_bp.route('/api/health/detailed')
def api_health_detailed():
    """Detailed health dashboard with DB stats, disk space, and service status."""
    try:
        import psutil
    except ImportError:
        psutil = None
    result = {}
    try:
        # DB size
        db_path = get_db_path()
        result['db_size_mb'] = round(os.path.getsize(db_path) / (1024 * 1024), 2) if os.path.isfile(db_path) else 0

        # Table count
        with db_session() as db:
            tables = db.execute("SELECT COUNT(*) as c FROM sqlite_master WHERE type='table'").fetchone()
            result['db_tables'] = tables['c'] if tables else 0

        # Backup count
        backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
        if os.path.isdir(backup_dir):
            result['backups'] = len([f for f in os.listdir(backup_dir) if f.endswith('.db')])
        else:
            result['backups'] = 0

        # Disk free space
        data_dir = get_data_dir()
        disk = shutil.disk_usage(data_dir)
        result['disk_free_gb'] = round(disk.free / (1024 ** 3), 1)

        # Uptime
        if psutil:
            import time as _time
            boot = psutil.boot_time()
            result['uptime_seconds'] = int(_time.time() - boot)
        else:
            result['uptime_seconds'] = 0

        # Python version
        result['python'] = platform.python_version()

        # Service status
        services_status = {}
        for sid, mod in SERVICE_MODULES.items():
            try:
                if not mod.is_installed():
                    services_status[sid] = 'not_installed'
                elif is_healthy(sid):
                    services_status[sid] = 'running'
                elif is_running(sid):
                    services_status[sid] = 'unhealthy'
                else:
                    services_status[sid] = 'stopped'
            except Exception:
                services_status[sid] = 'unknown'
        result['services'] = services_status

        return jsonify(result)
    except Exception as e:
        log.exception('Health detailed failed')
        return jsonify({'error': 'Health check failed'}), 500


# ─── Auto-pull default model after Ollama install ─────────────────


@system_bp.route('/api/dashboard/overview')
def api_dashboard_overview():
    """Quick overview for command dashboard."""
    with db_session() as db:
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
        sit = _safe_json_value(settings.get('sit_board'), {})

        # Weather trend
        pressure_rows = db.execute('SELECT pressure_hpa FROM weather_log WHERE pressure_hpa IS NOT NULL ORDER BY created_at DESC LIMIT 3').fetchall()


    return jsonify({
        'timers': timer_count, 'low_stock': low_stock, 'expiring': expiring,
        'recent_incidents': recent_incidents, 'situation': sit,
        'pressure_current': pressure_rows[0]['pressure_hpa'] if pressure_rows else None,
    })

@system_bp.route('/api/dashboard/live')
def api_dashboard_live():
    """Single aggregated endpoint for the live situational dashboard.
    Returns data from all modules in one request — designed for auto-refresh."""
    with db_session() as db:
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
        situation = _safe_json_value(sit_raw['value'] if sit_raw else None, {})

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
# ─── CSV Import API ────────────────────────────────────────────────


@system_bp.route('/api/export-all')
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
        log.exception('Full export failed')
        return jsonify({'error': 'Export failed'}), 500


@system_bp.route('/api/dashboard/critical')
def api_dashboard_critical():
    """Return actual critical items for the command dashboard."""
    with db_session() as db:
        from datetime import datetime, timedelta
        today = datetime.now().strftime('%Y-%m-%d')
        soon = (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')

        low_items = db.execute('SELECT name, quantity, unit, category FROM inventory WHERE quantity <= min_quantity AND min_quantity > 0 LIMIT 5').fetchall()
        expiring_items = db.execute("SELECT name, expiration, category FROM inventory WHERE expiration != '' AND expiration <= ? AND expiration >= ? ORDER BY expiration LIMIT 5", (soon, today)).fetchall()
        critical_burn = db.execute("SELECT name, quantity, daily_usage, category FROM inventory WHERE daily_usage > 0 AND (quantity / daily_usage) < 7 ORDER BY (quantity / daily_usage) LIMIT 5").fetchall()

    return jsonify({
        'low_items': [dict(r) for r in low_items],
        'expiring_items': [dict(r) for r in expiring_items],
        'critical_burn': [{'name': r['name'], 'days_left': round(r['quantity']/r['daily_usage'], 1) if r['daily_usage'] else 0, 'category': r['category']} for r in critical_burn],
    })

# ─── Analytics Dashboard Endpoints ────────────────────────────────

@system_bp.route('/api/analytics/inventory-trends')
def api_analytics_inventory_trends():
    """Inventory add/remove trends over past 30 days + category breakdown."""
    with db_session() as db:
        from datetime import datetime, timedelta
        # Daily inventory activity from activity_log
        daily = db.execute("""
            SELECT date(created_at) as dt,
                   SUM(CASE WHEN event IN ('inventory_added','item_added','add') THEN 1 ELSE 0 END) as added,
                   SUM(CASE WHEN event IN ('inventory_removed','item_removed','item_deleted','remove','delete') THEN 1 ELSE 0 END) as removed,
                   COUNT(*) as total
            FROM activity_log
            WHERE created_at >= datetime('now', '-30 days')
              AND (service = 'inventory' OR event LIKE '%inventory%' OR event LIKE '%item_%')
            GROUP BY date(created_at)
            ORDER BY dt
        """).fetchall()
        daily_counts = [{'date': r['dt'], 'added': r['added'], 'removed': r['removed'], 'total': r['total']} for r in daily]

        # Category distribution
        cats = db.execute("""
            SELECT category as name, COUNT(*) as count, COALESCE(SUM(quantity * cost), 0) as value
            FROM inventory
            GROUP BY category
            ORDER BY count DESC
        """).fetchall()
        categories = [{'name': r['name'], 'count': r['count'], 'value': round(r['value'], 2)} for r in cats]

        # Totals
        totals = db.execute('SELECT COUNT(*) as items, COUNT(DISTINCT category) as cats FROM inventory').fetchone()
        today = datetime.now().strftime('%Y-%m-%d')
        soon30 = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        expiring = db.execute("SELECT COUNT(*) as c FROM inventory WHERE expiration != '' AND expiration <= ? AND expiration >= ?", (soon30, today)).fetchone()['c']
    return jsonify({
        'daily_counts': daily_counts,
        'categories': categories,
        'total_items': totals['items'],
        'total_categories': totals['cats'],
        'expiring_30d': expiring,
    })

@system_bp.route('/api/analytics/consumption-rate')
def api_analytics_consumption_rate():
    """Burn rate analysis — daily consumption per category with projections."""
    with db_session() as db:
        rows = db.execute("""
            SELECT category as name,
                   SUM(daily_usage) as daily_rate,
                   SUM(quantity) as current_stock
            FROM inventory
            WHERE daily_usage > 0
            GROUP BY category
            ORDER BY category
        """).fetchall()
        categories = []
        overall_min = float('inf')
        for r in rows:
            dr = r['daily_rate'] if r['daily_rate'] else 0
            stock = r['current_stock'] if r['current_stock'] else 0
            days_rem = round(stock / dr, 1) if dr > 0 else 9999
            categories.append({
                'name': r['name'],
                'daily_rate': round(dr, 2),
                'current_stock': round(stock, 1),
                'days_remaining': days_rem,
            })
            if days_rem < overall_min:
                overall_min = days_rem
    return jsonify({
        'categories': categories,
        'overall_days': overall_min if overall_min != float('inf') else None,
    })

@system_bp.route('/api/analytics/weather-history')
def api_analytics_weather_history():
    """Weather readings for past 30 days."""
    with db_session() as db:
        rows = db.execute("""
            SELECT date(created_at) as dt,
                   AVG(temp_f) as temp,
                   AVG(humidity) as humidity,
                   AVG(pressure_hpa) as pressure,
                   GROUP_CONCAT(DISTINCT clouds) as conditions
            FROM weather_log
            WHERE created_at >= datetime('now', '-30 days')
            GROUP BY date(created_at)
            ORDER BY dt
        """).fetchall()
        readings = [{
            'date': r['dt'],
            'temp': round(r['temp'], 1) if r['temp'] else None,
            'humidity': round(r['humidity'], 1) if r['humidity'] else None,
            'pressure': round(r['pressure'], 1) if r['pressure'] else None,
            'conditions': r['conditions'] or '',
        } for r in rows]
    return jsonify({'readings': readings})

@system_bp.route('/api/analytics/power-history')
def api_analytics_power_history():
    """Power generation/consumption trends for past 30 days."""
    with db_session() as db:
        rows = db.execute("""
            SELECT date(created_at) as dt,
                   AVG(solar_wh_today) as generated_kwh,
                   AVG(load_wh_today) as consumed_kwh,
                   AVG(battery_soc) as battery_level
            FROM power_log
            WHERE created_at >= datetime('now', '-30 days')
            GROUP BY date(created_at)
            ORDER BY dt
        """).fetchall()
        daily = [{
            'date': r['dt'],
            'generated_kwh': round(r['generated_kwh'] / 1000, 2) if r['generated_kwh'] else 0,
            'consumed_kwh': round(r['consumed_kwh'] / 1000, 2) if r['consumed_kwh'] else 0,
            'battery_level': round(r['battery_level'], 1) if r['battery_level'] else None,
        } for r in rows]
    return jsonify({'daily': daily})

@system_bp.route('/api/analytics/medical-vitals')
def api_analytics_medical_vitals():
    """Patient vitals trending over past 30 days."""
    with db_session() as db:
        patients = db.execute('SELECT id, name FROM patients').fetchall()
        result = []
        for p in patients:
            vitals = db.execute("""
                SELECT date(created_at) as dt,
                       AVG(bp_systolic) as bp_sys, AVG(bp_diastolic) as bp_dia,
                       AVG(pulse) as pulse, AVG(temp_f) as temp, AVG(spo2) as spo2
                FROM vitals_log
                WHERE patient_id = ? AND created_at >= datetime('now', '-30 days')
                GROUP BY date(created_at)
                ORDER BY dt
            """, (p['id'],)).fetchall()
            if vitals:
                readings = [{
                    'date': v['dt'],
                    'bp': f"{int(v['bp_sys'])}/{int(v['bp_dia'])}" if v['bp_sys'] and v['bp_dia'] else None,
                    'pulse': round(v['pulse']) if v['pulse'] else None,
                    'temp': round(v['temp'], 1) if v['temp'] else None,
                    'spo2': round(v['spo2']) if v['spo2'] else None,
                } for v in vitals]
                result.append({'name': p['name'], 'readings': readings})
    return jsonify({'patients': result})

# ─── Dashboard Widget Configuration ───────────────────────────────

DEFAULT_WIDGETS = [
    {'id': 'weather', 'title': 'Weather', 'icon': '\U0001f324', 'visible': True, 'order': 0, 'size': 'normal'},
    {'id': 'inventory', 'title': 'Inventory', 'icon': '\U0001f4e6', 'visible': True, 'order': 1, 'size': 'normal'},
    {'id': 'power', 'title': 'Power', 'icon': '\u26a1', 'visible': True, 'order': 2, 'size': 'normal'},
    {'id': 'medical', 'title': 'Medical', 'icon': '\U0001f3e5', 'visible': True, 'order': 3, 'size': 'normal'},
    {'id': 'comms', 'title': 'Communications', 'icon': '\U0001f4e1', 'visible': True, 'order': 4, 'size': 'normal'},
    {'id': 'tasks', 'title': 'Tasks', 'icon': '\u2705', 'visible': True, 'order': 5, 'size': 'normal'},
    {'id': 'map', 'title': 'Map', 'icon': '\U0001f5fa', 'visible': True, 'order': 6, 'size': 'wide'},
    {'id': 'alerts', 'title': 'Alerts', 'icon': '\U0001f6a8', 'visible': True, 'order': 7, 'size': 'normal'},
    {'id': 'contacts', 'title': 'Contacts', 'icon': '\U0001f465', 'visible': True, 'order': 8, 'size': 'normal'},
    {'id': 'solar', 'title': 'Solar Forecast', 'icon': '\u2600', 'visible': True, 'order': 9, 'size': 'normal'},
]

@system_bp.route('/api/dashboard/widgets', methods=['GET'])
def api_dashboard_widgets_get():
    """Return the user's dashboard widget configuration."""
    with db_session() as db:
      row = db.execute("SELECT value FROM settings WHERE key = 'dashboard_widgets'").fetchone()
      widgets = _safe_json_value(row['value'] if row else None, DEFAULT_WIDGETS)
    return jsonify({'widgets': widgets})

@system_bp.route('/api/dashboard/widgets', methods=['POST'])
def api_dashboard_widgets_save():
    """Save user's dashboard widget configuration."""
    data, error = _require_json_body(request)
    if error:
        return error
    widgets = data if isinstance(data, list) else data.get('widgets', [])

    # Validate
    if not isinstance(widgets, list):
        return jsonify({'error': 'widgets must be a list'}), 400
    if len(widgets) > 20:
        return jsonify({'error': 'Maximum 20 widgets allowed'}), 400
    for w in widgets:
        if not isinstance(w, dict):
            return jsonify({'error': 'Each widget must be an object'}), 400
        if not isinstance(w.get('id'), str) or not w['id']:
            return jsonify({'error': 'Each widget must have a string id'}), 400
        if not isinstance(w.get('visible'), bool):
            return jsonify({'error': 'Each widget must have a boolean visible field'}), 400
        if not isinstance(w.get('order'), int):
            return jsonify({'error': 'Each widget must have an integer order field'}), 400

    with db_session() as db:
        db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('dashboard_widgets', ?)",
            (json.dumps(widgets),)
        )
        db.commit()
    return jsonify({'ok': True, 'widgets': widgets})

@system_bp.route('/api/dashboard/widgets/reset', methods=['POST'])
def api_dashboard_widgets_reset():
    """Reset dashboard widget configuration to defaults."""
    with db_session() as db:
        db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('dashboard_widgets', ?)",
            (json.dumps(DEFAULT_WIDGETS),)
        )
        db.commit()
    return jsonify({'ok': True, 'widgets': DEFAULT_WIDGETS})

@system_bp.route('/api/system/backup/create', methods=['POST'])
def api_backup_create():
    """Create an immediate database backup."""
    import sqlite3 as _sqlite3
    from datetime import datetime

    data = request.get_json() or {}
    encrypt = data.get('encrypt', False)
    password = data.get('password', '')

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

    encrypted = False
    final_path = backup_path

    if encrypt and password:
        try:
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            from cryptography.hazmat.primitives import hashes
            import hashlib, base64
            # Use PBKDF2 key derivation (must match restore path)
            with db_session() as db_cfg:
                cfg_row = db_cfg.execute("SELECT value FROM settings WHERE key = 'auto_backup_config'").fetchone()
            salt = ''
            cfg_data = _safe_json_value(cfg_row['value'] if cfg_row else None, {})
            salt = cfg_data.get('_salt', '')
            if not salt:
                import secrets
                salt = secrets.token_hex(16)
            kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt.encode(), iterations=100000)
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            f = Fernet(key)
            with open(backup_path, 'rb') as fp:
                raw = fp.read()
            enc_data = f.encrypt(raw)
            enc_path = backup_path + '.enc'
            with open(enc_path, 'wb') as fp:
                fp.write(enc_data)
            os.remove(backup_path)
            final_path = enc_path
            encrypted = True
        except ImportError:
            log.warning('cryptography package not installed — backup saved unencrypted')
        except Exception as e:
            log.warning(f'Encryption failed: {e}')

    size = os.path.getsize(final_path)
    fname = os.path.basename(final_path)
    log_activity('backup_created', detail=f'{fname} ({size} bytes, encrypted={encrypted})')

    broadcast_event('backup_complete', {'filename': fname})
    return jsonify({
        'status': 'ok', 'filename': fname,
        'size_bytes': size, 'encrypted': encrypted,
    })

@system_bp.route('/api/system/backup/list')
def api_backup_list():
    """List available backups sorted by date desc."""
    from datetime import datetime
    db_path = get_db_path()
    backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
    if not os.path.isdir(backup_dir):
        return jsonify([])
    backups = []
    for f in os.listdir(backup_dir):
        if not f.startswith('nomad_backup_'):
            continue
        path = os.path.join(backup_dir, f)
        try:
            stat = os.stat(path)
            backups.append({
                'filename': f,
                'size_bytes': stat.st_size,
                'created_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'encrypted': f.endswith('.enc'),
            })
        except Exception as exc:
            log.debug('Skipping backup list entry %s: %s', f, exc)
    backups.sort(key=lambda b: b['created_at'], reverse=True)
    return jsonify(backups[:50])

@system_bp.route('/api/system/backup/restore', methods=['POST'])
def api_backup_restore():
    """Restore database from a backup file."""
    import sqlite3 as _sqlite3

    data = request.get_json() or {}
    filename = data.get('filename', '')
    password = data.get('password', '')

    filename = os.path.basename(filename) if filename else ''
    if not filename:
        return jsonify({'error': 'Invalid filename'}), 400

    db_path = get_db_path()
    backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
    backup_path = os.path.join(backup_dir, filename)

    if not os.path.isfile(backup_path):
        return jsonify({'error': 'Backup not found'}), 404

    restore_data = None
    if filename.endswith('.enc'):
        if not password:
            return jsonify({'error': 'Password required for encrypted backup'}), 400
        try:
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            from cryptography.hazmat.primitives import hashes
            import base64
            # Load stored salt from backup config
            with db_session() as db2:
                cfg_row = db2.execute("SELECT value FROM settings WHERE key = 'auto_backup_config'").fetchone()
            salt = ''
            cfg_data = _safe_json_value(cfg_row['value'] if cfg_row else None, {})
            salt = cfg_data.get('_salt', '')
            if not salt:
                return jsonify({'error': 'No encryption salt found in backup config'}), 400
            kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt.encode(), iterations=100000)
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            f = Fernet(key)
            with open(backup_path, 'rb') as fp:
                restore_data = f.decrypt(fp.read())
        except ImportError:
            return jsonify({'error': 'cryptography package not installed'}), 500
        except Exception:
            return jsonify({'error': 'Decryption failed — wrong password?'}), 400
    else:
        with open(backup_path, 'rb') as fp:
            restore_data = fp.read()

    if not restore_data or restore_data[:16] != b'SQLite format 3\x00':
        return jsonify({'error': 'Invalid SQLite database file'}), 400

    # Write to temp file first and validate. The prior version leaked the
    # temp file whenever integrity-check or missing-tables returned a 400:
    # the early ``return`` skipped the cleanup line below the try/finally.
    import tempfile
    temp_fd, temp_path = tempfile.mkstemp(suffix='.db')
    try:
        with os.fdopen(temp_fd, 'wb') as f:
            f.write(restore_data)
        test_conn = _sqlite3.connect(temp_path)
        try:
            integrity = test_conn.execute('PRAGMA integrity_check').fetchone()[0]
            if integrity != 'ok':
                return jsonify({'error': f'Backup failed integrity check: {integrity}'}), 400
            tables = [r[0] for r in test_conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            required = ['settings', 'inventory', 'contacts', 'activity_log']
            missing = [t for t in required if t not in tables]
            if missing:
                return jsonify({'error': f'Backup missing tables: {", ".join(missing)}'}), 400
        finally:
            test_conn.close()
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass

    # Pre-restore safety backup
    pre_restore_path = db_path + '.pre-restore'
    try:
        src = _sqlite3.connect(db_path, timeout=30)
        try:
            dst = _sqlite3.connect(pre_restore_path)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
    except Exception as e:
        log.warning(f'Could not create pre-restore backup: {e}')

    try:
        with open(db_path, 'wb') as fp:
            fp.write(restore_data)
    except Exception as e:
        return jsonify({'error': f'Restore failed: {e}'}), 500

    log_activity('database_restored', detail=f'Restored from {filename}')
    return jsonify({'status': 'ok', 'message': f'Restored from {filename}. Restart app to fully apply.'})

@system_bp.route('/api/system/backup/<filename>', methods=['DELETE'])
@require_auth('admin')
def api_backup_delete(filename):
    """Delete a specific backup file.

    Uses basename + whitelisted prefix + commonpath containment so an
    attacker can't traverse out of the backups directory even if the URL
    decoder passes through unexpected sequences.
    """
    filename = os.path.basename(filename) if filename else ''
    if not filename:
        return jsonify({'error': 'Invalid filename'}), 400
    if not filename.startswith('nomad_backup_'):
        return jsonify({'error': 'Invalid backup filename'}), 400
    # Reject any residual traversal characters — a belt-and-braces check on
    # top of basename().
    if '/' in filename or '\\' in filename or '\x00' in filename:
        return jsonify({'error': 'Invalid filename'}), 400
    db_path = get_db_path()
    backup_dir = os.path.realpath(os.path.join(os.path.dirname(db_path), 'backups'))
    backup_path = os.path.realpath(os.path.join(backup_dir, filename))
    try:
        if os.path.commonpath([backup_path, backup_dir]) != backup_dir:
            return jsonify({'error': 'Invalid filename'}), 400
    except ValueError:
        return jsonify({'error': 'Invalid filename'}), 400
    if not os.path.isfile(backup_path):
        return jsonify({'error': 'Backup not found'}), 404
    try:
        os.remove(backup_path)
        log_activity('backup_deleted', detail=filename)
        return jsonify({'status': 'deleted'})
    except Exception:
        log.exception('Backup delete failed')
        return jsonify({'error': 'Delete failed'}), 500

@system_bp.route('/api/system/backup/configure', methods=['POST'])
def api_backup_configure():
    """Configure auto-backup schedule."""
    data = request.get_json() or {}
    config = {
        'enabled': bool(data.get('enabled', False)),
        'interval': data.get('interval', 'daily') if data.get('interval') in ('daily', 'weekly') else 'daily',
        'keep_count': max(1, min(30, _to_int(data.get('keep_count', 7), 7))),
        'encrypt': bool(data.get('encrypt', False)),
    }
    if data.get('password'):
        import hashlib, base64, os as _os
        salt = base64.urlsafe_b64encode(_os.urandom(16)).decode()
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt.encode(), iterations=100000)
        derived = base64.urlsafe_b64encode(kdf.derive(data['password'].encode())).decode()
        config['_derived_key'] = derived
        config['_salt'] = salt
    with db_session() as db:
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('auto_backup_config', ?)",
                   (json.dumps(config),))
        db.commit()
    from flask import current_app
    schedule_fn = current_app.config.get('_schedule_auto_backup')
    if schedule_fn:
        schedule_fn()
    log_activity('backup_configured', detail=f"enabled={config['enabled']}, interval={config['interval']}")
    return jsonify({'status': 'configured', 'config': config})

@system_bp.route('/api/system/backup/config')
def api_backup_config_get():
    """Get current auto-backup configuration."""
    with db_session() as db:
        row = db.execute("SELECT value FROM settings WHERE key = 'auto_backup_config'").fetchone()
    default_config = {'enabled': False, 'interval': 'daily', 'keep_count': 7, 'encrypt': False, 'has_password': False}
    config = _safe_json_value(row['value'] if row else None, default_config)
    config['has_password'] = bool(config.get('_derived_key'))
    config.pop('password', None)
    config.pop('_derived_key', None)
    config.pop('_salt', None)
    return jsonify(config)

# [EXTRACTED to blueprint] Federation v2 API


# ─── Emergency Broadcast ──────────────────────────────────────────

@system_bp.route('/api/system/shutdown', methods=['POST'])
@require_auth('admin')
def api_system_shutdown():
    """Shut down or reboot the host machine. Admin-only — a single HTTP
    request on a LAN with auth disabled would otherwise power off the box."""
    data, error = _require_json_body(request)
    if error:
        return error
    action = (data.get('action') or '').strip().lower()
    if action not in {'shutdown', 'reboot'}:
        return jsonify({'error': 'action must be shutdown or reboot'}), 400
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

@system_bp.route('/api/auth/check')
def api_auth_check():
    with db_session() as db:
        row = db.execute("SELECT value FROM settings WHERE key = 'auth_password'").fetchone()
        stored = row['value'] if row else ''
        token = request.headers.get('X-Auth-Token', '')
        token_valid = _verify_local_secret(token, stored) if stored and token else False
        if token_valid and _local_secret_needs_rehash(stored):
            db.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('auth_password', ?)",
                (_hash_local_secret(token),)
            )
            db.commit()
    remote = request.remote_addr or ''
    # Use ipaddress module for robust loopback detection (covers IPv4-mapped
    # IPv6 like ::ffff:127.0.0.1, and any 127.x.x.x address).
    try:
        import ipaddress
        is_local = ipaddress.ip_address(remote).is_loopback
    except (ValueError, TypeError):
        is_local = False
    enabled = bool(row and row['value'])
    return jsonify({'enabled': enabled, 'authenticated': (is_local or token_valid or not enabled)})

@system_bp.route('/api/auth/set-password', methods=['POST'])
def api_auth_set_password():
    data = request.get_json() or {}
    password = data.get('password', '').strip()
    hashed = _hash_local_secret(password) if password else ''
    with db_session() as db:
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('auth_password', ?)", (hashed,))
        db.commit()
    return jsonify({'status': 'saved', 'enabled': bool(password)})

# ─── PDF Viewer API ───────────────────────────────────────────────

@system_bp.route('/api/system/health')
def api_system_health():
    """Comprehensive health check — DB status, data coverage, service availability."""
    with db_session() as db:
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
                if count > 0:
                    modules_active += 1
            except Exception:
                health['coverage'][key] = {'count': 0, 'label': label, 'active': False}

        # Readiness scoring
        health['modules_active'] = modules_active
        health['modules_total'] = len(checks)
        health['total_data_items'] = total_items
        health['coverage_pct'] = round(modules_active / len(checks) * 100) if checks else 0

        # Critical gaps
        from datetime import datetime, timedelta
        today = datetime.now().strftime('%Y-%m-%d')
        expired = db.execute("SELECT COUNT(*) as c FROM inventory WHERE expiration != '' AND expiration < ?", (today,)).fetchone()['c']
        if expired > 0:
            health['issues'].append({'type': 'warning', 'msg': f'{expired} items have expired'})
        low = db.execute('SELECT COUNT(*) as c FROM inventory WHERE quantity <= min_quantity AND min_quantity > 0').fetchone()['c']
        if low > 0:
            health['issues'].append({'type': 'warning', 'msg': f'{low} items are below minimum stock'})
        overdue = db.execute("SELECT COUNT(*) as c FROM equipment_log WHERE next_service != '' AND next_service <= ?", (today,)).fetchone()['c']
        if overdue > 0:
            health['issues'].append({'type': 'warning', 'msg': f'{overdue} equipment items overdue for service'})
        crit_alerts = db.execute("SELECT COUNT(*) as c FROM alerts WHERE dismissed = 0 AND severity = 'critical'").fetchone()['c']
        if crit_alerts > 0:
            health['issues'].append({'type': 'critical', 'msg': f'{crit_alerts} unresolved critical alerts'})

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
@system_bp.route('/api/system/health-score', methods=['GET'])
def api_health_score():
    """Compute a numeric health score (0-100) with breakdown."""
    from db import db_session
    with db_session() as db:
        score = 0
        breakdown = {}

        # Data coverage (25 points)
        _READINESS_TABLES = frozenset({'inventory', 'contacts', 'patients', 'waypoints', 'notes', 'checklists'})
        tables_to_check = list(_READINESS_TABLES)
        populated = 0
        for t in tables_to_check:
            try:
                # Table names are from a hardcoded allowlist — validate anyway
                # to prevent future regressions if the set is ever sourced elsewhere.
                if t not in _READINESS_TABLES:
                    continue
                count = db.execute(f'SELECT COUNT(*) FROM [{t}]').fetchone()[0]
                if count > 0:
                    populated += 1
            except Exception:
                pass
        coverage = round((populated / len(tables_to_check)) * 25)
        breakdown['data_coverage'] = coverage
        score += coverage

        # Service availability (20 points)
        services_check = ['ollama', 'kiwix']
        running = sum(1 for s in services_check if is_running(s))
        svc_score = round((running / max(1, len(services_check))) * 20)
        breakdown['services'] = svc_score
        score += svc_score

        # Backup freshness (15 points)
        try:
            last_backup = db.execute("SELECT MAX(created_at) as latest FROM activity_log WHERE event = 'backup_created'").fetchone()
            if last_backup and last_backup['latest']:
                from datetime import datetime, timedelta
                backup_dt = datetime.fromisoformat(last_backup['latest'])
                hours_ago = (datetime.now() - backup_dt).total_seconds() / 3600
                if hours_ago < 24:
                    breakdown['backup'] = 15
                elif hours_ago < 48:
                    breakdown['backup'] = 10
                elif hours_ago < 168:
                    breakdown['backup'] = 5
                else:
                    breakdown['backup'] = 0
            else:
                breakdown['backup'] = 0
        except Exception:
            breakdown['backup'] = 0
        score += breakdown['backup']

        # Disk space (10 points)
        try:
            usage = shutil.disk_usage(config.get_data_dir())
            free_pct = (usage.free / usage.total) * 100
            if free_pct > 20:
                breakdown['disk'] = 10
            elif free_pct > 10:
                breakdown['disk'] = 7
            elif free_pct > 5:
                breakdown['disk'] = 3
            else:
                breakdown['disk'] = 0
        except Exception:
            breakdown['disk'] = 5
        score += breakdown['disk']

        # No expired items (10 points)
        try:
            expired = db.execute("SELECT COUNT(*) FROM inventory WHERE expiration IS NOT NULL AND expiration < date('now')").fetchone()[0]
            breakdown['no_expired'] = 10 if expired == 0 else max(0, 10 - expired)
        except Exception:
            breakdown['no_expired'] = 10
        score += breakdown['no_expired']

        # No overdue tasks (10 points)
        try:
            overdue = db.execute("SELECT COUNT(*) FROM scheduled_tasks WHERE next_due IS NOT NULL AND next_due < datetime('now') AND status != 'completed'").fetchone()[0]
            breakdown['no_overdue'] = 10 if overdue == 0 else max(0, 10 - overdue * 2)
        except Exception:
            breakdown['no_overdue'] = 10
        score += breakdown['no_overdue']

        # DB integrity (10 points)
        try:
            integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
            breakdown['db_integrity'] = 10 if integrity == 'ok' else 0
        except Exception:
            breakdown['db_integrity'] = 0
        score += breakdown['db_integrity']

        status = 'healthy' if score >= 75 else 'attention' if score >= 50 else 'degraded'
        return jsonify({'score': min(100, score), 'status': status, 'breakdown': breakdown})


# ─── Database Integrity Check (moved from routes_advanced) ───────

@system_bp.route('/api/system/db-check', methods=['POST'])
def api_system_db_check():
    """Run PRAGMA integrity_check and foreign_key_check."""
    with db_session() as db:
        integrity = db.execute('PRAGMA integrity_check').fetchall()
        fk_check = db.execute('PRAGMA foreign_key_check').fetchall()

    integrity_results = [dict(r) for r in integrity] if integrity else []
    fk_results = [dict(r) for r in fk_check] if fk_check else []

    # integrity_check returns [{'integrity_check': 'ok'}] when healthy
    ok = (len(integrity_results) == 1 and
          integrity_results[0].get('integrity_check') == 'ok' and
          len(fk_results) == 0)

    return jsonify({
        'status': 'ok' if ok else 'issues_found',
        'integrity_check': integrity_results,
        'foreign_key_check': fk_results,
    })


@system_bp.route('/api/system/db-vacuum', methods=['POST'])
@require_auth('admin')
def api_system_db_vacuum():
    """Run VACUUM and REINDEX to optimize the database.

    VACUUM holds an exclusive lock on the database — do not run concurrent
    writes. The raw connection is wrapped in try/finally so the DB is not
    left locked if VACUUM raises (previously a failed VACUUM leaked the
    handle).
    """
    import sqlite3
    path = get_db_path()
    # P2-I20: Disk space check — VACUUM creates a full copy of the DB
    try:
        db_size = os.path.getsize(path) if not path.startswith('file:') else 0
        disk = shutil.disk_usage(os.path.dirname(path) or '.')
        if db_size > 0 and disk.free < db_size * 2:
            return jsonify({'error': f'Insufficient disk space ({format_size(disk.free)} free, need ~{format_size(db_size * 2)})'}), 507
    except Exception:
        pass  # proceed anyway on stat failure
    conn = sqlite3.connect(path, uri=path.startswith('file:'), timeout=30)
    try:
        conn.execute('VACUUM')
        conn.execute('REINDEX')
    except sqlite3.Error as e:
        log.warning('VACUUM/REINDEX failed: %s', e)
        return jsonify({'error': 'Database optimization failed'}), 500
    finally:
        try:
            conn.close()
        except Exception:
            pass
    log_activity('db_vacuum', 'system', 'Database vacuumed and reindexed')
    return jsonify({'status': 'ok', 'message': 'VACUUM and REINDEX completed'})


@system_bp.route('/api/system/self-test', methods=['GET'])
def api_self_test():
    """Run a comprehensive self-test of all system components."""
    import sqlite3 as _sqlite3
    results = {'status': 'ok', 'checks': []}

    # Check all services via SERVICE_HEALTH_URLS
    for svc_id, (url, expected_status) in SERVICE_HEALTH_URLS.items():
        check = {'name': f'service_{svc_id}', 'status': 'skip', 'detail': 'Not running'}
        if is_running(svc_id):
            if is_healthy(svc_id):
                check['status'] = 'pass'
                check['detail'] = f'{svc_id} responding on {url}'
            else:
                check['status'] = 'fail'
                check['detail'] = f'{svc_id} running but not responding'
                results['status'] = 'degraded'
        results['checks'].append(check)

    # Also check services without health URLs
    for svc_id in SERVICE_MODULES:
        if svc_id not in SERVICE_HEALTH_URLS:
            check = {'name': f'service_{svc_id}', 'status': 'skip', 'detail': 'Not running'}
            if is_running(svc_id):
                check['status'] = 'pass'
                check['detail'] = f'{svc_id} process alive (no HTTP health endpoint)'
            results['checks'].append(check)

    # Backup freshness
    with db_session() as db:
        try:
            last_backup = db.execute("SELECT MAX(created_at) as latest FROM activity_log WHERE event = 'backup_created'").fetchone()
            if last_backup and last_backup['latest']:
                from datetime import datetime, timedelta
                backup_dt = datetime.fromisoformat(last_backup['latest'])
                hours_ago = (datetime.now() - backup_dt).total_seconds() / 3600
                if hours_ago > 48:
                    results['checks'].append({
                        'name': 'backup_freshness', 'status': 'warn',
                        'detail': f'Last backup was {hours_ago:.0f} hours ago (>48h)',
                    })
                    if results['status'] == 'ok':
                        results['status'] = 'attention'
                else:
                    results['checks'].append({
                        'name': 'backup_freshness', 'status': 'pass',
                        'detail': f'Last backup {hours_ago:.0f} hours ago',
                    })
            else:
                results['checks'].append({
                    'name': 'backup_freshness', 'status': 'warn',
                    'detail': 'No backups found',
                })
                if results['status'] == 'ok':
                    results['status'] = 'attention'
        except Exception:
            results['checks'].append({
                'name': 'backup_freshness', 'status': 'skip',
                'detail': 'Could not check backup status',
            })

        # DB integrity check
        try:
            integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
            if integrity == 'ok':
                results['checks'].append({
                    'name': 'db_integrity', 'status': 'pass',
                    'detail': 'Database integrity check passed',
                })
            else:
                results['checks'].append({
                    'name': 'db_integrity', 'status': 'fail',
                    'detail': f'Database integrity check failed: {integrity}',
                })
                results['status'] = 'degraded'
        except Exception as e:
            log.warning('Self-test integrity check failed: %s', e)
            results['checks'].append({
                'name': 'db_integrity', 'status': 'fail',
                'detail': 'Could not run integrity check',
            })
            results['status'] = 'degraded'
    # Check write permission on data directory
    data_dir = config.get_data_dir()
    try:
        test_file = os.path.join(data_dir, '.write_test_selftest')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        results['checks'].append({
            'name': 'data_dir_writable', 'status': 'pass',
            'detail': 'Data directory writable',
        })
    except Exception as e:
        log.warning('Self-test data dir write check failed: %s', e)
        results['checks'].append({
            'name': 'data_dir_writable', 'status': 'fail',
            'detail': 'Cannot write to data directory',
        })
        results['status'] = 'degraded'

    return jsonify(results)


@system_bp.route('/api/services/resources', methods=['GET'])
def api_services_resources():
    """Get CPU, memory, and thread usage for all running services."""
    result = {}
    for svc_id in ['ollama', 'kiwix', 'cyberchef', 'kolibri', 'qdrant', 'stirling', 'flatnotes']:
        if is_running(svc_id):
            result[svc_id] = get_service_resources(svc_id)
    return jsonify(result)


@system_bp.route('/api/system/getting-started')
def api_getting_started():
    """Returns a guided setup checklist for new users."""
    with db_session() as db:
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
        return jsonify({'steps': steps, 'completed': completed, 'total': len(steps), 'pct': round(completed / len(steps) * 100) if steps else 0})
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


@system_bp.route('/api/qr/generate', methods=['POST'])
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

@system_bp.route('/api/system/portable-mode')
def api_system_portable_mode():
    """Check if running in USB portable mode."""
    from platform_utils import is_portable_mode, get_portable_data_dir
    portable = is_portable_mode()
    return jsonify({
        'portable': portable,
        'data_dir': get_portable_data_dir() if portable else get_data_dir(),
        'app_dir': os.path.dirname(os.path.abspath(sys.argv[0] if sys.argv[0] else '')),
    })

# ─── Offline Geocoding ───────────────────────────────────────────

# ─── Internationalization (i18n) ─────────────────────────────────────
try:
    from web.translations import SUPPORTED_LANGUAGES, TRANSLATIONS
except ImportError:
    from translations import SUPPORTED_LANGUAGES, TRANSLATIONS

@system_bp.route('/api/i18n/languages')
def api_i18n_languages():
    return jsonify({'languages': SUPPORTED_LANGUAGES})

@system_bp.route('/api/i18n/translations/<lang>')
def api_i18n_translations(lang):
    if lang not in TRANSLATIONS:
        return jsonify({'error': f'Language not found: {lang}'}), 404
    return jsonify({'language': lang, 'translations': TRANSLATIONS[lang]})

@system_bp.route('/api/i18n/language', methods=['GET'])
def api_i18n_get_language():
    with db_session() as db:
      try:
        row = db.execute("SELECT value FROM settings WHERE key = 'language'").fetchone()
        lang = row['value'] if row else 'en'
      except Exception:
        lang = 'en'
    return jsonify({'language': lang})

@system_bp.route('/api/i18n/language', methods=['POST'])
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


# ─── Plugins ────────────────────────────────────────────────────────

@system_bp.route('/api/plugins')
def api_plugins():
    """Return list of loaded plugins with name, path, and status."""
    from web.plugins import list_plugins
    return jsonify({'plugins': list_plugins()})


# ─── External Ollama Host ─────────────────────────────────────────


@system_bp.route('/api/settings/ollama-host')
def api_ollama_host_get():
    with db_session() as db:
        row = db.execute("SELECT value FROM settings WHERE key = 'ollama_host'").fetchone()
    return jsonify({'host': row['value'] if row else ''})


@system_bp.route('/api/settings/ollama-host', methods=['PUT'])
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


# [EXTRACTED to blueprint] drills/history + training/progression

# ─── Shopping List Generator ──────────────────────────────────────

# [EXTRACTED to blueprint]


# ─── Print / Status / PDF Routes ─────────────────────────────────
# [EXTRACTED to print_routes blueprint]

