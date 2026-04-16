#!/usr/bin/env python3
"""
NOMAD Field Desk desktop launcher.

Desktop-first preparedness, reference, and local operations workspace.
"""

import sys
import os
import subprocess
import threading
import time
import logging
from logging.handlers import RotatingFileHandler

from log_utils import SensitiveDataFilter, install_scrubbing_filter

LOG_FORMAT = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
MAX_LOG_BYTES = 5 * 1024 * 1024  # 5 MB per file
LOG_BACKUP_COUNT = 3

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[logging.StreamHandler()],
)
install_scrubbing_filter()
log = logging.getLogger('nomad')


def _check_deps():
    """Verify required dependencies are installed. Log errors for missing ones."""
    if getattr(sys, 'frozen', False):
        return  # Bundled exe has everything
    missing = []
    deps = {'flask': 'flask', 'requests': 'requests', 'webview': 'pywebview',
            'PIL': 'pillow', 'pystray': 'pystray', 'psutil': 'psutil'}
    for module, package in deps.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    if missing:
        print(f'ERROR: Missing required packages: {", ".join(missing)}')
        print(f'Install with: pip install {" ".join(missing)}')
        print(f'Or install all: pip install -r requirements.txt')
        sys.exit(1)

_check_deps()

import webview
import pystray
from PIL import Image, ImageDraw
from config import APP_DISPLAY_NAME, APP_SHORT_NAME, Config, get_data_dir
from web.app import create_app, set_version
from db import init_db, get_db, log_activity, backup_db

VERSION = Config.VERSION
PORT = Config.APP_PORT
HOST = Config.APP_HOST

_tray_icon = None
_window = None
_shutdown_event = threading.Event()  # Signals daemon threads to stop

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
    draw.polygon([(32, 4), (60, 32), (32, 60), (4, 32)], fill='#d5c59d', outline='#1a221b')
    draw.polygon([(32, 14), (50, 32), (32, 50), (14, 32)], fill='#182119')
    draw.line([(23, 41), (32, 23), (41, 41)], fill='#90a55f', width=5, joint='curve')
    draw.ellipse((28, 28, 36, 36), fill='#dfe7c0', outline='#1a221b', width=2)
    draw.ellipse((20, 38, 26, 44), fill='#dfe7c0', outline='#1a221b', width=1)
    draw.ellipse((38, 38, 44, 44), fill='#dfe7c0', outline='#1a221b', width=1)
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

    # Signal all daemon threads (health_monitor, etc.) to stop
    _shutdown_event.set()

    try:
        log_activity('app_shutdown', detail='User requested quit')
    except Exception:
        pass

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

    # Shutdown built-in torrent client
    try:
        from services.torrent import get_manager as _tm
        _tm().shutdown()
    except Exception as e:
        log.warning(f'Torrent manager shutdown error: {e}')

    # Final DB backup
    try:
        backup_db()
    except Exception as e:
        log.warning(f'Final DB backup failed: {e}')

    if _window:
        try:
            _window.destroy()
        except Exception:
            pass
    icon.stop()
    # Flush log handlers before exiting
    for handler in logging.getLogger().handlers:
        try:
            handler.flush()
        except Exception:
            pass
    # sys.exit() runs normal interpreter shutdown (context managers, atexit,
    # buffered writes) so any in-flight DB work committed via db_session()
    # actually lands. os._exit() bypassed this and could drop WAL frames.
    sys.exit(0)


def setup_tray():
    global _tray_icon
    icon_img = create_tray_icon()
    menu = pystray.Menu(
        pystray.MenuItem(f'Show {APP_DISPLAY_NAME}', tray_show_window, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Quit', tray_quit),
    )
    _tray_icon = pystray.Icon('nomad', icon_img, APP_DISPLAY_NAME, menu)
    _tray_icon.run_detached()


def auto_start_services():
    """Start all installed services on launch (turnkey behavior)."""
    mods = _get_service_modules()
    db = get_db()
    try:
        rows = db.execute('SELECT id FROM services WHERE installed = 1').fetchall()
    finally:
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
    """Background thread: detects crashed services and auto-restarts them.

    Respects _shutdown_event so the thread exits cleanly during graceful
    shutdown rather than relying on daemon-thread force-kill.
    """
    from services.manager import unregister_process, should_restart, record_restart, prune_completed_downloads

    # Wait long enough for auto_start_services to finish (Stirling can take 60s+)
    # Use Event.wait() instead of time.sleep() so we can be interrupted on shutdown.
    if _shutdown_event.wait(timeout=90):
        return
    mods = _get_service_modules()

    while not _shutdown_event.is_set():
        db = None
        try:
            db = get_db()
            rows = db.execute('SELECT id FROM services WHERE running = 1 AND installed = 1').fetchall()
            for row in rows:
                if _shutdown_event.is_set():
                    break
                sid = row['id']
                mod = mods.get(sid)
                if mod and not mod.running():
                    if should_restart(sid):
                        log.warning(f'Service {sid} crashed — attempting auto-restart')
                        log_activity('service_crash_detected', sid, 'Attempting auto-restart', 'warning')
                        record_restart(sid)
                        unregister_process(sid)
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
                        from services.manager import MAX_RESTARTS
                        log.error(f'Service {sid} crashed — restart limit reached ({MAX_RESTARTS} in 5min)')
                        log_activity('service_restart_limit', sid, 'Max restarts exceeded', 'error')
                        db.execute('UPDATE services SET running = 0, pid = NULL WHERE id = ?', (sid,))
                        db.commit()
                        unregister_process(sid)
        except Exception as e:
            log.error(f'Health monitor error: {e}')
        finally:
            if db:
                try:
                    db.close()
                except Exception:
                    pass
        # Prune stale download progress entries to prevent unbounded dict growth
        try:
            prune_completed_downloads()
        except Exception:
            pass
        # Use Event.wait() so shutdown interrupts the sleep immediately
        if _shutdown_event.wait(timeout=10):
            break
    log.info('Health monitor stopped')


def first_run_check():
    db = get_db()
    try:
        row = db.execute("SELECT value FROM settings WHERE key = 'first_run_complete'").fetchone()
        if not row:
            db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('first_run_complete', '0')")
            db.commit()
        return not row or row['value'] != '1'
    finally:
        db.close()


def main():
    os.makedirs(get_data_dir(), exist_ok=True)

    # File logging with rotation (5 MB max, keep 3 backups)
    file_handler = RotatingFileHandler(
        get_log_path(), maxBytes=MAX_LOG_BYTES, backupCount=LOG_BACKUP_COUNT, encoding='utf-8'
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    file_handler.addFilter(SensitiveDataFilter('file_scrub'))
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

    # Start Flask on a configurable host. Default to localhost for safer desktop behavior.
    flask_thread = threading.Thread(
        target=lambda: app.run(host=HOST, port=PORT, debug=False, use_reloader=False),
        daemon=True,
    )
    flask_thread.start()

    # Wait for Flask to be ready
    import requests
    flask_ready = False
    for _ in range(30):
        try:
            requests.get(f'http://127.0.0.1:{PORT}/api/health', timeout=1)
            flask_ready = True
            break
        except Exception:
            time.sleep(0.2)
    if not flask_ready:
        log.error('Flask failed to start within 6 seconds — services may not work correctly')

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
    splash_html = f'''<html><body style="margin:0;background:radial-gradient(circle at top,#171c19 0%,#090a0c 62%);display:flex;align-items:center;justify-content:center;height:100vh;font-family:'Segoe UI',sans-serif;">
    <div style="text-align:center;padding:32px 40px;border:1px solid rgba(235,225,198,.1);border-radius:26px;background:rgba(8,10,12,.78);box-shadow:0 28px 80px rgba(0,0,0,.38);backdrop-filter:blur(8px);">
      <div style="width:88px;height:88px;margin:0 auto 22px;">
        <svg viewBox="0 0 128 128">
          <defs>
            <linearGradient id="shell" x1="18" y1="16" x2="108" y2="112" gradientUnits="userSpaceOnUse">
              <stop offset="0" stop-color="#f4edda"/><stop offset="1" stop-color="#d5c59d"/>
            </linearGradient>
            <linearGradient id="core" x1="48" y1="36" x2="82" y2="94" gradientUnits="userSpaceOnUse">
              <stop offset="0" stop-color="#273327"/><stop offset="1" stop-color="#131914"/>
            </linearGradient>
            <linearGradient id="route" x1="44" y1="84" x2="84" y2="44" gradientUnits="userSpaceOnUse">
              <stop offset="0" stop-color="#b8c98a"/><stop offset="1" stop-color="#7e9550"/>
            </linearGradient>
          </defs>
          <path d="M64 8 106 64 64 120 22 64Z" fill="url(#shell)" stroke="#1a221b" stroke-width="4"/>
          <path d="M64 24 88 64 64 104 40 64Z" fill="url(#core)" stroke="#f4edda" stroke-opacity=".18" stroke-width="2"/>
          <path d="M64 20v15" stroke="#1a221b" stroke-linecap="round" stroke-width="4"/>
          <path d="M46 82 64 46l18 36" stroke="url(#route)" stroke-linecap="round" stroke-linejoin="round" stroke-width="8"/>
          <circle cx="64" cy="64" r="7" fill="#dfe7c0" stroke="#1a221b" stroke-width="3"/>
          <circle cx="46" cy="82" r="4" fill="#dfe7c0" stroke="#1a221b" stroke-width="2"/>
          <circle cx="82" cy="82" r="4" fill="#dfe7c0" stroke="#1a221b" stroke-width="2"/>
        </svg>
      </div>
      <div style="color:#b6c0aa;font-size:11px;letter-spacing:.22em;text-transform:uppercase;margin:0 0 10px;">Offline Field Desk</div>
      <h1 style="color:#f6f2e6;font-size:24px;font-weight:700;letter-spacing:.04em;margin:0 0 8px;">{APP_SHORT_NAME}</h1>
      <p style="color:#9ba58f;font-size:13px;max-width:340px;line-height:1.65;margin:0 0 24px;">Bringing your preparedness, reference, and local operations workspace online...</p>
      <div style="width:220px;height:4px;background:#1a1f1c;border-radius:999px;margin:0 auto;overflow:hidden;">
        <div style="width:40%;height:100%;background:linear-gradient(90deg,#b8c98a,#d5c59d);border-radius:999px;animation:load 1.5s ease infinite;"></div>
      </div>
    </div>
    <style>@keyframes load{{0%{{transform:translateX(-100%)}}100%{{transform:translateX(350%)}}}}</style>
    </body></html>'''

    global _window
    _window = webview.create_window(
        f'{APP_DISPLAY_NAME} v{VERSION}',
        html=splash_html,
        width=1280,
        height=860,
        min_size=(900, 600),
        background_color='#060608',
    )

    def _navigate_when_ready():
        """Navigate to dashboard once Flask is serving.

        Polls for up to ~30 seconds (100 × 0.3s) to accommodate slow DB
        init or service startup. Respects _shutdown_event to avoid racing
        against a closing window.
        """
        import requests as rq
        for _ in range(100):
            if _shutdown_event.is_set():
                return
            try:
                rq.get(f'http://127.0.0.1:{PORT}/api/health', timeout=1)
                w = _window
                if w and not _shutdown_event.is_set():
                    try:
                        w.load_url(start_url)
                    except Exception:
                        pass
                return
            except Exception:
                time.sleep(0.3)
        log.error('Flask not reachable after 30 seconds — showing error in window')
        w = _window
        if w and not _shutdown_event.is_set():
            try:
                w.load_html(f'<html><body style="margin:0;background:#060608;display:flex;align-items:center;justify-content:center;height:100vh;font-family:Segoe UI,sans-serif;"><div style="text-align:center;"><h1 style="color:#ff6b6b;font-size:20px;">{APP_SHORT_NAME} failed to start</h1><p style="color:#7f8791;font-size:14px;">The local web server did not respond. Check the log file for details.</p></div></body></html>')
            except Exception:
                pass

    _window.events.closing += on_window_closing
    threading.Thread(target=_navigate_when_ready, daemon=True).start()

    from platform_utils import get_webview_gui
    gui = get_webview_gui()
    webview.start(gui=gui, debug=False)


if __name__ == '__main__':
    main()
