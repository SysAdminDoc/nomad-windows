"""CyberChef service — data encoding, encryption, and analysis tools."""

import os
import http.server
import threading
import logging
from services.manager import (
    get_services_dir, download_file, check_port, _download_progress
)
from db import get_db

log = logging.getLogger('nomad.cyberchef')

SERVICE_ID = 'cyberchef'
CYBERCHEF_PORT = 8889
CYBERCHEF_RELEASE_API = 'https://api.github.com/repos/gchq/CyberChef/releases/latest'

_server_thread = None
_httpd = None


def get_install_dir():
    return os.path.join(get_services_dir(), 'cyberchef')


def is_installed():
    install_dir = get_install_dir()
    # Look for CyberChef*.html
    if os.path.isdir(install_dir):
        for f in os.listdir(install_dir):
            if f.lower().startswith('cyberchef') and f.endswith('.html'):
                return True
    return False


def install(callback=None):
    """Download and extract CyberChef."""
    install_dir = get_install_dir()
    os.makedirs(install_dir, exist_ok=True)
    zip_path = os.path.join(install_dir, 'CyberChef.zip')

    _download_progress[SERVICE_ID] = {'percent': 0, 'status': 'downloading', 'error': None}

    try:
        # Resolve actual zip URL from GitHub releases API
        import requests as req
        rel = req.get(CYBERCHEF_RELEASE_API, timeout=15).json()
        zip_url = rel['assets'][0]['browser_download_url']
        download_file(zip_url, zip_path, SERVICE_ID)

        _download_progress[SERVICE_ID]['status'] = 'extracting'
        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(install_dir)
        os.remove(zip_path)

        db = get_db()
        db.execute('''
            INSERT OR REPLACE INTO services (id, name, description, icon, category, installed, port, install_path, url)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
        ''', (
            SERVICE_ID, 'CyberChef (Data Tools)',
            'Encryption, encoding, hashing, and data analysis toolkit',
            'shield', 'tools', CYBERCHEF_PORT, install_dir,
            f'http://localhost:{CYBERCHEF_PORT}'
        ))
        db.commit()
        db.close()

        _download_progress[SERVICE_ID] = {'percent': 100, 'status': 'complete', 'error': None}
        log.info('CyberChef installed successfully')

    except Exception as e:
        _download_progress[SERVICE_ID] = {'percent': 0, 'status': 'error', 'error': str(e)}
        raise


def start():
    """Serve CyberChef via a simple HTTP server."""
    global _server_thread, _httpd

    if not is_installed():
        raise RuntimeError('CyberChef is not installed')

    if running():
        return

    install_dir = get_install_dir()

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=install_dir, **kwargs)
        def log_message(self, format, *args):
            pass  # Suppress request logs

    _httpd = http.server.HTTPServer(('0.0.0.0', CYBERCHEF_PORT), QuietHandler)
    _server_thread = threading.Thread(target=_httpd.serve_forever, daemon=True)
    _server_thread.start()

    db = get_db()
    db.execute('UPDATE services SET running = 1 WHERE id = ?', (SERVICE_ID,))
    db.commit()
    db.close()

    log.info(f'CyberChef serving on port {CYBERCHEF_PORT}')


def stop():
    global _httpd
    if _httpd:
        _httpd.shutdown()
        _httpd = None

    db = get_db()
    db.execute('UPDATE services SET running = 0 WHERE id = ?', (SERVICE_ID,))
    db.commit()
    db.close()


def running():
    return check_port(CYBERCHEF_PORT)
