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
_cyberchef_lock = threading.Lock()


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

    _download_progress[SERVICE_ID] = {'percent': 0, 'status': 'downloading', 'error': None, 'speed': '', 'downloaded': 0, 'total': 0}

    try:
        # Resolve actual zip URL from GitHub releases API
        import requests as req
        rel = req.get(CYBERCHEF_RELEASE_API, timeout=15).json()
        zip_url = None
        for asset in rel.get('assets', []):
            if asset['name'].endswith('.zip') and 'CyberChef' in asset['name']:
                zip_url = asset['browser_download_url']
                break
        if not zip_url:
            if not rel.get('assets'):
                raise RuntimeError('No CyberChef release assets found')
            zip_url = rel['assets'][0]['browser_download_url']
        download_file(zip_url, zip_path, SERVICE_ID)

        _download_progress[SERVICE_ID]['status'] = 'extracting'
        from platform_utils import _safe_zip_extract
        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as zf:
            _safe_zip_extract(zf, install_dir)
        os.remove(zip_path)

        db = get_db()
        try:
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
        finally:
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

    with _cyberchef_lock:
        if running():
            return

        # Clean up any stale server instance before starting fresh
        if _httpd is not None:
            try:
                _httpd.shutdown()
            except Exception:
                pass
            _httpd = None

        install_dir = get_install_dir()

        class QuietHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=install_dir, **kwargs)
            def log_message(self, format, *args):
                pass  # Suppress request logs

        try:
            _httpd = http.server.HTTPServer(('127.0.0.1', CYBERCHEF_PORT), QuietHandler)
        except OSError as e:
            _httpd = None
            raise RuntimeError(f'CyberChef port {CYBERCHEF_PORT} already in use: {e}')
        _server_thread = threading.Thread(target=_httpd.serve_forever, daemon=True)
        _server_thread.start()

    db = get_db()
    try:
        db.execute('UPDATE services SET running = 1 WHERE id = ?', (SERVICE_ID,))
        db.commit()
    finally:
        db.close()

    log.info(f'CyberChef serving on port {CYBERCHEF_PORT}')


def stop():
    global _httpd, _server_thread
    with _cyberchef_lock:
        if _httpd:
            _httpd.shutdown()
            _httpd = None
        _server_thread = None

    db = get_db()
    try:
        db.execute('UPDATE services SET running = 0 WHERE id = ?', (SERVICE_ID,))
        db.commit()
    finally:
        db.close()


def running():
    return _httpd is not None and _server_thread is not None and _server_thread.is_alive() and check_port(CYBERCHEF_PORT)
