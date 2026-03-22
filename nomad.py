"""
Project N.O.M.A.D. for Windows v2.4.0
Node for Offline Media, Archives, and Data
Native Windows edition — no Docker required.
"""

import sys
import os
import subprocess
import threading
import time
import ctypes
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger('nomad')


def _bootstrap():
    """Auto-install dependencies before imports. Skipped when running as frozen exe."""
    if getattr(sys, 'frozen', False):
        return
    deps = ['flask', 'requests', 'webview', 'PIL', 'pystray', 'psutil', 'PyPDF2']
    pkg_names = {'webview': 'pywebview', 'PIL': 'pillow', 'pystray': 'pystray', 'psutil': 'psutil', 'PyPDF2': 'PyPDF2'}
    for dep in deps:
        try:
            __import__(dep)
        except ImportError:
            pkg = pkg_names.get(dep, dep)
            for cmd in [
                [sys.executable, '-m', 'pip', 'install', pkg],
                [sys.executable, '-m', 'pip', 'install', '--user', pkg],
                [sys.executable, '-m', 'pip', 'install', '--break-system-packages', pkg],
            ]:
                try:
                    subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    break
                except Exception:
                    continue

_bootstrap()

import webview
import pystray
from PIL import Image, ImageDraw
from config import get_data_dir
from web.app import create_app, set_version
from db import init_db, get_db, log_activity, backup_db

VERSION = '2.4.0'
PORT = 8080

_tray_icon = None
_window = None

SERVICE_MODULES = None  # Lazy-loaded


def _get_service_modules():
    global SERVICE_MODULES
    if SERVICE_MODULES is None:
        from services import ollama, kiwix, cyberchef, kolibri, qdrant, stirling
        SERVICE_MODULES = {
            'ollama': ollama, 'kiwix': kiwix, 'cyberchef': cyberchef,
            'kolibri': kolibri, 'qdrant': qdrant, 'stirling': stirling,
        }
    return SERVICE_MODULES


def get_log_path():
    log_dir = os.path.join(get_data_dir(), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, 'nomad.log')


def create_tray_icon():
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.polygon([(32, 4), (60, 32), (32, 60), (4, 32)], fill='#4f9cf7')
    draw.polygon([(32, 14), (50, 32), (32, 50), (14, 32)], fill='#0d0d0d')
    draw.polygon([(32, 22), (42, 32), (32, 42), (22, 32)], fill='#4f9cf7')
    return img


def tray_show_window(icon, item):
    global _window
    if _window:
        _window.show()
        _window.restore()


def tray_quit(icon, item):
    """Graceful shutdown: ordered service stop, DB flush, then exit."""
    global _window
    log.info('Graceful shutdown initiated...')
    log_activity('app_shutdown', detail='User requested quit')

    mods = _get_service_modules()
    from services.manager import get_shutdown_order

    # Stop services in dependency order
    for sid in get_shutdown_order():
        mod = mods.get(sid)
        if mod:
            try:
                if mod.is_installed() and mod.running():
                    log.info(f'Stopping {sid}...')
                    mod.stop()
            except Exception as e:
                log.error(f'Error stopping {sid}: {e}')

    # Final DB backup
    try:
        backup_db()
    except Exception:
        pass

    icon.stop()
    if _window:
        _window.destroy()
    os._exit(0)


def setup_tray():
    global _tray_icon
    icon_img = create_tray_icon()
    menu = pystray.Menu(
        pystray.MenuItem('Show N.O.M.A.D.', tray_show_window, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Quit', tray_quit),
    )
    _tray_icon = pystray.Icon('nomad', icon_img, 'Project N.O.M.A.D.', menu)
    _tray_icon.run_detached()


def auto_start_services():
    """Start all installed services on launch (turnkey behavior)."""
    mods = _get_service_modules()
    db = get_db()
    rows = db.execute('SELECT id FROM services WHERE installed = 1').fetchall()
    db.close()

    for row in rows:
        sid = row['id']
        mod = mods.get(sid)
        if mod and mod.is_installed() and not mod.running():
            try:
                log.info(f'Auto-starting {sid}...')
                mod.start()
                log_activity('service_autostarted', sid)
            except Exception as e:
                log.error(f'Auto-start failed for {sid}: {e}')
                log_activity('service_autostart_failed', sid, str(e), 'error')


def on_window_closing():
    global _window
    if _window:
        _window.hide()
    return False


def health_monitor():
    """Background thread: detects crashed services and auto-restarts them."""
    from services.manager import _processes, should_restart, record_restart

    time.sleep(10)
    mods = _get_service_modules()

    while True:
        try:
            db = get_db()
            rows = db.execute('SELECT id FROM services WHERE running = 1 AND installed = 1').fetchall()
            for row in rows:
                sid = row['id']
                mod = mods.get(sid)
                if mod and not mod.running():
                    if should_restart(sid):
                        log.warning(f'Service {sid} crashed — attempting auto-restart')
                        log_activity('service_crash_detected', sid, 'Attempting auto-restart', 'warning')
                        record_restart(sid)
                        _processes.pop(sid, None)
                        try:
                            mod.start()
                            log.info(f'Service {sid} auto-restarted successfully')
                            log_activity('service_autorestarted', sid)
                        except Exception as e:
                            log.error(f'Auto-restart failed for {sid}: {e}')
                            log_activity('service_autorestart_failed', sid, str(e), 'error')
                            db.execute('UPDATE services SET running = 0, pid = NULL WHERE id = ?', (sid,))
                            db.commit()
                    else:
                        log.error(f'Service {sid} crashed — restart limit reached ({3} in 5min)')
                        log_activity('service_restart_limit', sid, 'Max restarts exceeded', 'error')
                        db.execute('UPDATE services SET running = 0, pid = NULL WHERE id = ?', (sid,))
                        db.commit()
                        _processes.pop(sid, None)
            db.close()
        except Exception as e:
            log.error(f'Health monitor error: {e}')
        time.sleep(10)


def first_run_check():
    db = get_db()
    row = db.execute("SELECT value FROM settings WHERE key = 'first_run_complete'").fetchone()
    if not row:
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('first_run_complete', '0')")
        db.commit()
    db.close()
    return not row or row['value'] != '1'


def main():
    os.makedirs(get_data_dir(), exist_ok=True)

    # File logging
    file_handler = logging.FileHandler(get_log_path(), encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s'))
    logging.getLogger().addHandler(file_handler)

    init_db()

    # DB backup on startup
    try:
        backup_db()
        log.info('Database backed up')
    except Exception as e:
        log.warning(f'DB backup failed: {e}')

    log_activity('app_started', detail=f'v{VERSION}')

    # GPU detection at startup
    from services.manager import detect_gpu
    gpu = detect_gpu()
    log_activity('gpu_detected', detail=f'{gpu["type"]}: {gpu["name"]}')

    is_first_run = first_run_check()

    set_version(VERSION)
    app = create_app()

    # Start Flask — listen on 0.0.0.0 for LAN access
    flask_thread = threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False),
        daemon=True,
    )
    flask_thread.start()

    # Wait for Flask to be ready
    import requests
    for _ in range(30):
        try:
            requests.get(f'http://127.0.0.1:{PORT}/api/health', timeout=1)
            break
        except Exception:
            time.sleep(0.2)

    # Auto-start services from previous session
    threading.Thread(target=auto_start_services, daemon=True).start()

    # Health monitor — detect and auto-restart crashed services
    threading.Thread(target=health_monitor, daemon=True).start()

    # System tray
    setup_tray()

    # Determine start URL
    start_url = f'http://127.0.0.1:{PORT}'
    if is_first_run:
        start_url += '?wizard=1'

    # Launch embedded WebView2 window with splash
    splash_html = f'''<html><body style="margin:0;background:#060608;display:flex;align-items:center;justify-content:center;height:100vh;font-family:'Segoe UI',sans-serif;">
    <div style="text-align:center;">
      <div style="width:80px;height:80px;margin:0 auto 20px;">
        <svg viewBox="0 0 64 64"><polygon points="32,4 60,32 32,60 4,32" fill="#5b9fff"/><polygon points="32,14 50,32 32,50 14,32" fill="#0d0d0d"/><polygon points="32,22 42,32 32,42 22,32" fill="#5b9fff"/></svg>
      </div>
      <h1 style="color:#e8e8ed;font-size:22px;font-weight:600;margin:0 0 8px;">Project N.O.M.A.D.</h1>
      <p style="color:#55556a;font-size:13px;margin:0 0 24px;">Setting up your offline command center...</p>
      <div style="width:200px;height:3px;background:#1e1e26;border-radius:2px;margin:0 auto;overflow:hidden;">
        <div style="width:40%;height:100%;background:linear-gradient(90deg,#5b9fff,#b388ff);border-radius:2px;animation:load 1.5s ease infinite;"></div>
      </div>
    </div>
    <style>@keyframes load{{0%{{transform:translateX(-100%)}}100%{{transform:translateX(350%)}}}}</style>
    </body></html>'''

    global _window
    _window = webview.create_window(
        f'Project N.O.M.A.D. v{VERSION}',
        html=splash_html,
        width=1280,
        height=860,
        min_size=(900, 600),
        background_color='#060608',
    )

    def _navigate_when_ready():
        """Navigate to dashboard once Flask is serving."""
        import requests as rq
        for _ in range(60):
            try:
                rq.get(f'http://127.0.0.1:{PORT}/api/health', timeout=1)
                if _window:
                    _window.load_url(start_url)
                return
            except Exception:
                time.sleep(0.3)

    threading.Thread(target=_navigate_when_ready, daemon=True).start()
    _window.events.closing += on_window_closing

    webview.start(gui='edgechromium', debug=False)


if __name__ == '__main__':
    main()
