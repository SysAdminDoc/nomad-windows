"""Kolibri service — offline education platform (Khan Academy courses, etc)."""

import os
import sys
import subprocess
import time
import logging
import shutil
from services.manager import (
    get_services_dir, stop_process, is_running, check_port, _download_progress
)
from db import get_db

log = logging.getLogger('nomad.kolibri')

SERVICE_ID = 'kolibri'
KOLIBRI_PORT = 8300

# Python embeddable package for Windows (portable, no install needed)
PYTHON_EMBED_URL = 'https://www.python.org/ftp/python/3.12.8/python-3.12.8-embed-amd64.zip'
GET_PIP_URL = 'https://bootstrap.pypa.io/get-pip.py'


def _get_bundled_python_dir():
    """Path where we store our own portable Python."""
    return os.path.join(get_install_dir(), 'python')


def _python_exe():
    """Return a Python interpreter. Auto-installs portable Python if running from frozen exe."""
    # 1. If not frozen, use current Python
    if not getattr(sys, 'frozen', False):
        return sys.executable

    # 2. Check our bundled portable Python
    bundled = os.path.join(_get_bundled_python_dir(), 'python.exe')
    if os.path.isfile(bundled):
        return bundled

    # 3. Check system PATH
    p = shutil.which('python') or shutil.which('python3')
    if p:
        return p

    # 4. No Python found — will need auto-install
    raise RuntimeError('Python not available — will auto-install on next install attempt')


def _auto_install_python():
    """Download portable Python embeddable package and set up pip."""
    import zipfile
    import requests

    py_dir = _get_bundled_python_dir()
    os.makedirs(py_dir, exist_ok=True)
    zip_path = os.path.join(py_dir, 'python-embed.zip')

    log.info('Auto-downloading portable Python 3.12...')
    try:
        # Download embeddable Python
        resp = requests.get(PYTHON_EMBED_URL, stream=True, timeout=30)
        resp.raise_for_status()
        with open(zip_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)

        log.info('Extracting Python...')
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(py_dir)
        os.remove(zip_path)

        python_exe = os.path.join(py_dir, 'python.exe')
        if not os.path.isfile(python_exe):
            raise RuntimeError('Python extracted but python.exe not found')

        # Enable pip by modifying the ._pth file to include site-packages
        pth_files = [f for f in os.listdir(py_dir) if f.endswith('._pth')]
        for pth in pth_files:
            pth_path = os.path.join(py_dir, pth)
            with open(pth_path, 'r') as f:
                content = f.read()
            if '#import site' in content:
                content = content.replace('#import site', 'import site')
                with open(pth_path, 'w') as f:
                    f.write(content)
                log.info(f'Enabled site-packages in {pth}')

        # Install pip
        log.info('Installing pip...')
        get_pip = os.path.join(py_dir, 'get-pip.py')
        resp = requests.get(GET_PIP_URL, timeout=30)
        with open(get_pip, 'w') as f:
            f.write(resp.text)

        result = subprocess.run(
            [python_exe, get_pip, '--no-warn-script-location'],
            capture_output=True, text=True, timeout=120,
            creationflags=0x08000000,
        )
        if result.returncode != 0:
            log.warning(f'pip install output: {result.stderr}')

        os.remove(get_pip)
        log.info(f'Portable Python installed: {python_exe}')
        return python_exe

    except Exception as e:
        log.error(f'Auto-install Python failed: {e}')
        if os.path.isfile(zip_path):
            os.remove(zip_path)
        return None


def get_install_dir():
    return os.path.join(get_services_dir(), 'kolibri')


def get_home_dir():
    """Kolibri data directory (KOLIBRI_HOME)."""
    path = os.path.join(get_install_dir(), 'data')
    os.makedirs(path, exist_ok=True)
    return path


def is_installed():
    try:
        result = subprocess.run(
            [_python_exe(), '-m', 'kolibri', '--version'],
            capture_output=True, text=True, timeout=10,
            creationflags=0x08000000,
        )
        return result.returncode == 0
    except Exception:
        return False


def install(callback=None):
    """Install Kolibri via pip."""
    install_dir = get_install_dir()
    os.makedirs(install_dir, exist_ok=True)

    _download_progress[SERVICE_ID] = {
        'percent': 0, 'status': 'downloading', 'error': None,
        'speed': 'pip install...', 'downloaded': 0, 'total': 0,
    }

    try:
        # Ensure we have a Python interpreter
        try:
            py = _python_exe()
        except RuntimeError:
            _download_progress[SERVICE_ID].update({'percent': 5, 'speed': 'Installing Python runtime...'})
            py = _auto_install_python()
            if not py:
                raise RuntimeError('Could not install portable Python — check internet connection')

        _download_progress[SERVICE_ID].update({'percent': 10, 'speed': 'Installing Kolibri...'})

        result = subprocess.run(
            [py, '-m', 'pip', 'install', 'kolibri'],
            capture_output=True, text=True, timeout=600,
            creationflags=0x08000000,
        )
        if result.returncode != 0:
            # Try --user fallback
            result = subprocess.run(
                [py, '-m', 'pip', 'install', '--user', 'kolibri'],
                capture_output=True, text=True, timeout=600,
                creationflags=0x08000000,
            )
            if result.returncode != 0:
                raise RuntimeError(f'pip install failed: {result.stderr}')

        _download_progress[SERVICE_ID].update({'percent': 80, 'speed': 'Provisioning...'})

        # Run initial provisioning
        env = os.environ.copy()
        env['KOLIBRI_HOME'] = get_home_dir()
        subprocess.run(
            [py, '-m', 'kolibri', 'manage', 'migrate', '--noinput'],
            env=env, capture_output=True, text=True, timeout=120,
            creationflags=0x08000000,
        )

        db = get_db()
        try:
            db.execute('''
                INSERT OR REPLACE INTO services (id, name, description, icon, category, installed, port, install_path, url)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
            ''', (
                SERVICE_ID, 'Kolibri (Education)',
                'Offline education platform — Khan Academy courses, textbooks, and more',
                'graduation', 'education', KOLIBRI_PORT, install_dir,
                f'http://localhost:{KOLIBRI_PORT}'
            ))
            db.commit()
        finally:
            db.close()

        _download_progress[SERVICE_ID] = {
            'percent': 100, 'status': 'complete', 'error': None,
            'speed': '', 'downloaded': 0, 'total': 0,
        }
        log.info('Kolibri installed successfully')

    except Exception as e:
        _download_progress[SERVICE_ID] = {
            'percent': 0, 'status': 'error', 'error': str(e),
            'speed': '', 'downloaded': 0, 'total': 0,
        }
        log.error(f'Kolibri install failed: {e}')
        raise


def start():
    """Start Kolibri server."""
    if not is_installed():
        raise RuntimeError('Kolibri is not installed')

    env = os.environ.copy()
    env['KOLIBRI_HOME'] = get_home_dir()
    env['KOLIBRI_HTTP_PORT'] = str(KOLIBRI_PORT)
    env['KOLIBRI_LISTEN_PORT'] = str(KOLIBRI_PORT)

    CREATE_NO_WINDOW = 0x08000000
    proc = subprocess.Popen(
        [_python_exe(), '-m', 'kolibri', 'start', '--foreground', '--port', str(KOLIBRI_PORT)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW,
    )

    from services.manager import _processes
    _processes[SERVICE_ID] = proc

    db = get_db()
    try:
        db.execute('UPDATE services SET running = 1, pid = ? WHERE id = ?', (proc.pid, SERVICE_ID))
        db.commit()
    finally:
        db.close()

    for _ in range(30):
        if check_port(KOLIBRI_PORT):
            log.info(f'Kolibri running on port {KOLIBRI_PORT} (PID {proc.pid})')
            return proc.pid
        time.sleep(1)

    log.warning('Kolibri started but port not yet responding')
    return proc.pid


def stop():
    return stop_process(SERVICE_ID)


def running():
    return is_running(SERVICE_ID) and check_port(KOLIBRI_PORT)
