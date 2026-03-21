"""Stirling PDF service — offline PDF toolkit for merge, split, compress, convert, OCR, and more."""

import os
import subprocess
import time
import logging
import requests as req
from services.manager import (
    get_services_dir, download_file, stop_process, is_running, check_port, _download_progress
)
from db import get_db

log = logging.getLogger('nomad.stirling')

SERVICE_ID = 'stirling'
STIRLING_PORT = 8443
STIRLING_RELEASE_API = 'https://api.github.com/repos/Stirling-Tools/Stirling-PDF/releases/latest'


def get_install_dir():
    return os.path.join(get_services_dir(), 'stirling')


def get_exe_path():
    return os.path.join(get_install_dir(), 'stirling.exe')


def is_installed():
    return os.path.isfile(get_exe_path())


def install(callback=None):
    """Download Stirling-PDF from GitHub releases."""
    install_dir = get_install_dir()
    os.makedirs(install_dir, exist_ok=True)
    exe_path = get_exe_path()

    _download_progress[SERVICE_ID] = {
        'percent': 0, 'status': 'downloading', 'error': None,
        'speed': '', 'downloaded': 0, 'total': 0,
    }

    try:
        # Resolve download URL from GitHub releases
        rel = req.get(STIRLING_RELEASE_API, timeout=15).json()
        exe_url = None
        for asset in rel.get('assets', []):
            name = asset['name'].lower()
            if 'win' in name and asset['name'].endswith('.exe'):
                exe_url = asset['browser_download_url']
                break
        if not exe_url:
            raise RuntimeError('Could not find Stirling-PDF Windows release')

        download_file(exe_url, exe_path, SERVICE_ID)

        db = get_db()
        db.execute('''
            INSERT OR REPLACE INTO services (id, name, description, icon, category, installed, port, install_path, exe_path, url)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
        ''', (
            SERVICE_ID, 'Stirling PDF',
            'Offline PDF toolkit — merge, split, compress, convert, OCR, and 50+ tools',
            'file', 'tools', STIRLING_PORT, install_dir, exe_path,
            f'http://localhost:{STIRLING_PORT}'
        ))
        db.commit()
        db.close()

        _download_progress[SERVICE_ID] = {
            'percent': 100, 'status': 'complete', 'error': None,
            'speed': '', 'downloaded': 0, 'total': 0,
        }
        log.info('Stirling-PDF installed successfully')

    except Exception as e:
        _download_progress[SERVICE_ID] = {
            'percent': 0, 'status': 'error', 'error': str(e),
            'speed': '', 'downloaded': 0, 'total': 0,
        }
        log.error(f'Stirling-PDF install failed: {e}')
        raise


def start():
    """Start Stirling-PDF server."""
    if not is_installed():
        raise RuntimeError('Stirling-PDF is not installed')

    exe = get_exe_path()

    CREATE_NO_WINDOW = 0x08000000
    proc = subprocess.Popen(
        [exe, f'--server.port={STIRLING_PORT}'],
        cwd=os.path.dirname(exe),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=CREATE_NO_WINDOW,
    )

    from services.manager import _processes
    _processes[SERVICE_ID] = proc

    db = get_db()
    db.execute('UPDATE services SET running = 1, pid = ? WHERE id = ?', (proc.pid, SERVICE_ID))
    db.commit()
    db.close()

    for _ in range(30):
        if check_port(STIRLING_PORT):
            log.info(f'Stirling-PDF running on port {STIRLING_PORT} (PID {proc.pid})')
            return proc.pid
        time.sleep(1)

    log.warning('Stirling-PDF started but port not yet responding')
    return proc.pid


def stop():
    return stop_process(SERVICE_ID)


def running():
    return is_running(SERVICE_ID) and check_port(STIRLING_PORT)
