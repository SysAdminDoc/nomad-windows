"""Stirling PDF service — offline PDF toolkit for merge, split, compress, convert, OCR, and more."""

import os
import subprocess
import shutil
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


def get_jar_path():
    install_dir = get_install_dir()
    jar = os.path.join(install_dir, 'Stirling-PDF.jar')
    if os.path.isfile(jar):
        return jar
    # Check for any jar file
    if os.path.isdir(install_dir):
        for f in os.listdir(install_dir):
            if f.endswith('.jar') and 'stirling' in f.lower():
                return os.path.join(install_dir, f)
    return jar


def _find_java():
    """Find a Java runtime. Stirling-PDF requires Java 17+."""
    java = shutil.which('java')
    if java:
        return java
    # Check common Windows paths
    for base in [os.environ.get('JAVA_HOME', ''), r'C:\Program Files\Java', r'C:\Program Files\Eclipse Adoptium']:
        if base and os.path.isdir(base):
            for root, dirs, files in os.walk(base):
                if 'java.exe' in files:
                    return os.path.join(root, 'java.exe')
    return None


def is_installed():
    return os.path.isfile(get_jar_path())


def install(callback=None):
    """Download Stirling-PDF jar from GitHub releases."""
    install_dir = get_install_dir()
    os.makedirs(install_dir, exist_ok=True)
    jar_path = os.path.join(install_dir, 'Stirling-PDF.jar')

    _download_progress[SERVICE_ID] = {
        'percent': 0, 'status': 'downloading', 'error': None,
        'speed': '', 'downloaded': 0, 'total': 0,
    }

    try:
        # Resolve download URL from GitHub releases
        rel = req.get(STIRLING_RELEASE_API, timeout=15).json()
        jar_url = None
        for asset in rel.get('assets', []):
            # Get the standalone jar (not -with-login, not -server)
            if asset['name'] == 'Stirling-PDF.jar':
                jar_url = asset['browser_download_url']
                break
        if not jar_url:
            # Fallback: any jar that isn't -with-login or -server
            for asset in rel.get('assets', []):
                name = asset['name']
                if name.endswith('.jar') and 'login' not in name.lower() and 'server' not in name.lower():
                    jar_url = asset['browser_download_url']
                    break
        if not jar_url:
            raise RuntimeError('Could not find Stirling-PDF jar in release assets')

        download_file(jar_url, jar_path, SERVICE_ID)

        db = get_db()
        db.execute('''
            INSERT OR REPLACE INTO services (id, name, description, icon, category, installed, port, install_path, exe_path, url)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
        ''', (
            SERVICE_ID, 'Stirling PDF',
            'Offline PDF toolkit — merge, split, compress, convert, OCR, and 50+ tools',
            'file', 'tools', STIRLING_PORT, install_dir, jar_path,
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
    """Start Stirling-PDF server via Java."""
    if not is_installed():
        raise RuntimeError('Stirling-PDF is not installed')

    java = _find_java()
    if not java:
        raise RuntimeError('Java not found — Stirling PDF requires Java 17+ installed on your system')

    jar = get_jar_path()
    install_dir = get_install_dir()

    CREATE_NO_WINDOW = 0x08000000
    env = os.environ.copy()
    env['STIRLING_PDF_DESKTOP_UI'] = 'false'

    proc = subprocess.Popen(
        [java, '-jar', jar, f'--server.port={STIRLING_PORT}'],
        cwd=install_dir,
        env=env,
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

    # Stirling PDF (Spring Boot) takes longer to start
    for _ in range(60):
        if proc.poll() is not None:
            stderr = proc.stderr.read().decode(errors='replace')[-500:]
            raise RuntimeError(f'Stirling-PDF exited immediately: {stderr}')
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
