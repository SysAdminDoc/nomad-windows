"""Kolibri service — offline education platform (Khan Academy courses, etc)."""

import os
import sys
import subprocess
import time
import logging
from services.manager import (
    get_services_dir, stop_process, is_running, check_port, _download_progress
)
from db import get_db

log = logging.getLogger('nomad.kolibri')

SERVICE_ID = 'kolibri'
KOLIBRI_PORT = 8300


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
            [sys.executable, '-m', 'kolibri', '--version'],
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
        _download_progress[SERVICE_ID].update({'percent': 10, 'speed': 'Installing Kolibri...'})

        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', 'kolibri'],
            capture_output=True, text=True, timeout=600,
            creationflags=0x08000000,
        )
        if result.returncode != 0:
            # Try --user fallback
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '--user', 'kolibri'],
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
            [sys.executable, '-m', 'kolibri', 'manage', 'migrate', '--noinput'],
            env=env, capture_output=True, text=True, timeout=120,
            creationflags=0x08000000,
        )

        db = get_db()
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
        [sys.executable, '-m', 'kolibri', 'start', '--foreground', '--port', str(KOLIBRI_PORT)],
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
