"""CyberChef service — data encoding, encryption, and analysis tools."""

import os
import http.server
import threading
import logging
import requests
from services.manager import (
    get_services_dir, download_file, check_port, _download_progress, _dl_progress_lock,
)
from db import get_db

log = logging.getLogger('nomad.cyberchef')

SERVICE_ID = 'cyberchef'
CYBERCHEF_PORT = 8889
CYBERCHEF_RELEASE_API = 'https://api.github.com/repos/gchq/CyberChef/releases/latest'

_server_thread = None
_httpd = None
_cyberchef_lock = threading.Lock()


def _safe_response_payload(response, fallback=None):
    if fallback is None:
        fallback = {}
    try:
        parsed = response.json()
    except Exception:
        if isinstance(fallback, dict):
            return dict(fallback)
        if isinstance(fallback, list):
            return list(fallback)
        return fallback
    if isinstance(parsed, (dict, list)):
        return parsed
    if isinstance(fallback, dict):
        return dict(fallback)
    if isinstance(fallback, list):
        return list(fallback)
    return fallback


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

    with _dl_progress_lock:
        _download_progress[SERVICE_ID] = {'percent': 0, 'status': 'downloading', 'error': None, 'speed': '', 'downloaded': 0, 'total': 0}

    try:
        # Resolve actual zip URL from GitHub releases API
        from services.manager import GITHUB_API_HEADERS
        _api_resp = requests.get(CYBERCHEF_RELEASE_API, timeout=15, headers=GITHUB_API_HEADERS)
        _api_resp.raise_for_status()
        release = _safe_response_payload(_api_resp, {})
        zip_url = None
        assets = release.get('assets', []) if isinstance(release, dict) else []
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            asset_name = str(asset.get('name', '') or '')
            if asset_name.endswith('.zip') and 'CyberChef' in asset_name:
                zip_url = asset.get('browser_download_url', '')
                break
        if not zip_url:
            if not assets:
                raise RuntimeError('No CyberChef release assets found')
            first_asset = next((asset for asset in assets if isinstance(asset, dict) and asset.get('browser_download_url')), None)
            if not first_asset:
                raise RuntimeError('No CyberChef release assets found')
            zip_url = first_asset['browser_download_url']
        download_file(zip_url, zip_path, SERVICE_ID)

        with _dl_progress_lock:
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

        with _dl_progress_lock:
            _download_progress[SERVICE_ID] = {'percent': 100, 'status': 'complete', 'error': None}
        log.info('CyberChef installed successfully')

    except Exception as e:
        with _dl_progress_lock:
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
        httpd_local = _httpd
        thread_local = _server_thread
        _httpd = None
        _server_thread = None
    # Shut down and release the socket outside the module lock so stop() can't
    # deadlock against a serve_forever callback that calls back into us, and
    # so the socket is freed even if the thread is slow to notice.
    if httpd_local is not None:
        try:
            httpd_local.shutdown()
        except Exception as e:
            log.debug('CyberChef shutdown signal failed: %s', e)
        try:
            httpd_local.server_close()
        except Exception as e:
            log.debug('CyberChef server_close failed: %s', e)
    if thread_local is not None and thread_local.is_alive():
        thread_local.join(timeout=5)
        if thread_local.is_alive():
            log.warning('CyberChef server thread did not exit within 5s')

    db = get_db()
    try:
        db.execute('UPDATE services SET running = 0 WHERE id = ?', (SERVICE_ID,))
        db.commit()
    finally:
        db.close()


def running():
    return _httpd is not None and _server_thread is not None and _server_thread.is_alive() and check_port(CYBERCHEF_PORT)
