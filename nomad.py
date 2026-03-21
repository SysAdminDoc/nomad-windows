"""
Project N.O.M.A.D. for Windows v0.2.0
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
    """Auto-install dependencies before imports."""
    deps = ['flask', 'requests', 'webview', 'PIL', 'pystray', 'psutil']
    pkg_names = {'webview': 'pywebview', 'PIL': 'pillow', 'pystray': 'pystray', 'psutil': 'psutil'}
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
from web.app import create_app
from db import init_db, get_db

VERSION = '0.3.0'
PORT = 8080

_tray_icon = None
_window = None


def get_data_dir():
    return os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'ProjectNOMAD')


def get_log_path():
    log_dir = os.path.join(get_data_dir(), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, 'nomad.log')


def create_tray_icon():
    """Create a 64x64 icon for the system tray."""
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Draw a diamond/compass shape
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
    global _window
    # Stop all running services
    from services import ollama, kiwix, cyberchef
    for mod in [ollama, kiwix, cyberchef]:
        try:
            if mod.is_installed() and mod.running():
                mod.stop()
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
    """Start services that were running when the app last closed."""
    from services import ollama, kiwix, cyberchef
    from db import get_db as gdb

    db = gdb()
    rows = db.execute('SELECT id FROM services WHERE running = 1 AND installed = 1').fetchall()
    db.close()

    mods = {'ollama': ollama, 'kiwix': kiwix, 'cyberchef': cyberchef}
    for row in rows:
        sid = row['id']
        mod = mods.get(sid)
        if mod and mod.is_installed():
            try:
                log.info(f'Auto-starting {sid}...')
                mod.start()
            except Exception as e:
                log.error(f'Auto-start failed for {sid}: {e}')


def on_window_closing():
    """Handle window close — minimize to tray instead of quitting."""
    global _window
    if _window:
        _window.hide()
    return False  # Prevent actual close


def health_monitor():
    """Background thread that detects crashed services and updates DB status."""
    from services import ollama, kiwix, cyberchef
    from services.manager import _processes

    time.sleep(10)  # Wait for initial startup
    mods = {'ollama': ollama, 'kiwix': kiwix, 'cyberchef': cyberchef}

    while True:
        try:
            db = get_db()
            rows = db.execute('SELECT id FROM services WHERE running = 1 AND installed = 1').fetchall()
            for row in rows:
                sid = row['id']
                mod = mods.get(sid)
                if mod and not mod.running():
                    log.warning(f'Service {sid} crashed — marking as stopped')
                    db.execute('UPDATE services SET running = 0, pid = NULL WHERE id = ?', (sid,))
                    db.commit()
                    _processes.pop(sid, None)
            db.close()
        except Exception as e:
            log.error(f'Health monitor error: {e}')
        time.sleep(15)


def first_run_check():
    """Check if this is the first run and mark it."""
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

    is_first_run = first_run_check()

    app = create_app()

    # Start Flask in a background thread
    flask_thread = threading.Thread(
        target=lambda: app.run(host='127.0.0.1', port=PORT, debug=False, use_reloader=False),
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

    # Health monitor — detect crashed services
    threading.Thread(target=health_monitor, daemon=True).start()

    # System tray
    setup_tray()

    # Determine start URL
    start_url = f'http://127.0.0.1:{PORT}'
    if is_first_run:
        start_url += '?wizard=1'

    # Launch embedded WebView2 window
    global _window
    _window = webview.create_window(
        f'Project N.O.M.A.D. v{VERSION}',
        start_url,
        width=1280,
        height=860,
        min_size=(900, 600),
        background_color='#0d0d0d',
    )
    _window.events.closing += on_window_closing

    webview.start(gui='edgechromium', debug=False)


if __name__ == '__main__':
    main()
