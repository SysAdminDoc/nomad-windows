"""
Project N.O.M.A.D. for Windows v0.1.0
Node for Offline Media, Archives, and Data
Native Windows edition — no Docker required.
"""

import sys
import os
import subprocess
import threading
import time


def _bootstrap():
    """Auto-install dependencies before imports."""
    deps = ['flask', 'requests', 'webview']
    pkg_names = {'webview': 'pywebview'}
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
from web.app import create_app
from db import init_db

VERSION = '0.1.0'
PORT = 8080


def get_data_dir():
    return os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'ProjectNOMAD')


def main():
    os.makedirs(get_data_dir(), exist_ok=True)
    init_db()

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

    # Launch embedded WebView2 window
    window = webview.create_window(
        f'Project N.O.M.A.D. v{VERSION}',
        f'http://127.0.0.1:{PORT}',
        width=1280,
        height=860,
        min_size=(900, 600),
        background_color='#0d0d0d',
    )
    webview.start(gui='edgechromium', debug=False)


if __name__ == '__main__':
    main()
