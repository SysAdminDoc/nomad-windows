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


ADOPTIUM_JRE_URL = 'https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jre/hotspot/normal/eclipse'


def _get_bundled_java_dir():
    """Path where we store our own portable JRE."""
    return os.path.join(get_install_dir(), 'jre')


def _find_java():
    """Find a Java runtime. Auto-downloads portable JRE if not found."""
    # 1. Check our bundled JRE first
    bundled_dir = _get_bundled_java_dir()
    if os.path.isdir(bundled_dir):
        for root, dirs, files in os.walk(bundled_dir):
            if 'java.exe' in files:
                return os.path.join(root, 'java.exe')

    # 2. Check system PATH
    java = shutil.which('java')
    if java:
        return java

    # 3. Check common Windows paths
    for base in [os.environ.get('JAVA_HOME', ''), r'C:\Program Files\Java', r'C:\Program Files\Eclipse Adoptium']:
        if base and os.path.isdir(base):
            for root, dirs, files in os.walk(base):
                if 'java.exe' in files:
                    return os.path.join(root, 'java.exe')

    return None


def _auto_install_java():
    """Download a portable Adoptium JRE 21 into our install directory."""
    import zipfile
    jre_dir = _get_bundled_java_dir()
    os.makedirs(jre_dir, exist_ok=True)
    zip_path = os.path.join(jre_dir, 'jre.zip')

    log.info('Auto-downloading portable Java JRE 21 from Adoptium...')
    try:
        resp = req.get(ADOPTIUM_JRE_URL, stream=True, timeout=30, allow_redirects=True)
        resp.raise_for_status()
        with open(zip_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)

        log.info('Extracting JRE...')
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(jre_dir)
        os.remove(zip_path)

        # Find java.exe in extracted tree
        java = _find_java()
        if java:
            log.info(f'Portable JRE installed: {java}')
            return java
        else:
            log.error('JRE extracted but java.exe not found')
            return None
    except Exception as e:
        log.error(f'Auto-install JRE failed: {e}')
        if os.path.isfile(zip_path):
            os.remove(zip_path)
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

        # Auto-install Java if not found
        if not _find_java():
            _download_progress[SERVICE_ID].update({'status': 'installing Java runtime...', 'percent': 90})
            _auto_install_java()

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
    """Start Stirling-PDF server via Java. Auto-downloads JRE if needed."""
    if not is_installed():
        raise RuntimeError('Stirling-PDF is not installed')

    java = _find_java()
    if not java:
        log.info('Java not found — auto-installing portable JRE...')
        java = _auto_install_java()
        if not java:
            raise RuntimeError('Java not found and auto-install failed — check your internet connection')

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
