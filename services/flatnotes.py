"""FlatNotes service — simple markdown note-taking app (Docker-free, standalone)."""

import os
import sys
import subprocess
import threading
import logging
from services.manager import (
    get_services_dir, download_file, check_port, start_process, stop_process,
    is_running as _is_running, _download_progress, _dl_progress_lock,
)
from db import get_db

log = logging.getLogger('nomad.flatnotes')

SERVICE_ID = 'flatnotes'
FLATNOTES_PORT = 8890
FLATNOTES_RELEASE_API = 'https://api.github.com/repos/dullage/flatnotes/releases/latest'


def get_install_dir():
    return os.path.join(get_services_dir(), 'flatnotes')


def _get_data_dir():
    """FlatNotes data directory (where notes are stored)."""
    d = os.path.join(get_install_dir(), 'data')
    os.makedirs(d, exist_ok=True)
    return d


def is_installed():
    install_dir = get_install_dir()
    # Check for flatnotes Python package or binary
    if os.path.isdir(install_dir):
        venv = os.path.join(install_dir, 'venv')
        if os.path.isdir(venv):
            return True
        # Check for standalone binary (executable files only)
        for f in os.listdir(install_dir):
            fpath = os.path.join(install_dir, f)
            if 'flatnotes' in f.lower() and os.path.isfile(fpath) and (
                f.endswith('.exe') or os.access(fpath, os.X_OK)
            ):
                return True
    return False


def install(callback=None):
    """Install FlatNotes using pip in a venv."""
    install_dir = get_install_dir()
    os.makedirs(install_dir, exist_ok=True)
    venv_dir = os.path.join(install_dir, 'venv')

    with _dl_progress_lock:
        _download_progress[SERVICE_ID] = {'percent': 0, 'status': 'downloading', 'error': None, 'speed': '', 'downloaded': 0, 'total': 0}

    def do_install():
        try:
            with _dl_progress_lock:
                _download_progress[SERVICE_ID].update({'percent': 10, 'status': 'downloading', 'speed': 'Creating venv...'})

            # Find Python executable
            python = sys.executable
            if getattr(sys, 'frozen', False):
                # Frozen app — find system Python
                from platform_utils import find_system_python
                python = find_system_python()
                if not python:
                    raise RuntimeError('Python 3 not found. Install Python 3.9+ to use FlatNotes.')

            # Create venv — use platform_utils helper so future platform
            # changes propagate here automatically (previously this hardcoded
            # the Windows CREATE_NO_WINDOW flag and duplicated the check).
            from platform_utils import run_kwargs
            subprocess.run([python, '-m', 'venv', venv_dir], check=True,
                           **run_kwargs(capture_output=True))

            # Get pip path in venv
            if sys.platform == 'win32':
                pip = os.path.join(venv_dir, 'Scripts', 'pip.exe')
                venv_python = os.path.join(venv_dir, 'Scripts', 'python.exe')
            else:
                pip = os.path.join(venv_dir, 'bin', 'pip')
                venv_python = os.path.join(venv_dir, 'bin', 'python')

            with _dl_progress_lock:
                _download_progress[SERVICE_ID].update({'percent': 30, 'speed': 'Installing flatnotes...'})

            # Install flatnotes
            subprocess.run([pip, 'install', 'flatnotes'], check=True,
                           **run_kwargs(capture_output=True))

            with _dl_progress_lock:
                _download_progress[SERVICE_ID].update({'percent': 80, 'speed': 'Configuring...'})

            # Create data directory
            _get_data_dir()

            # Register in DB
            db = get_db()
            try:
                db.execute('''
                    INSERT OR REPLACE INTO services (id, name, description, icon, category, installed, port, install_path, exe_path, url)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                ''', (
                    SERVICE_ID, 'FlatNotes (Notes App)',
                    'Simple, beautiful markdown note-taking with tags and search',
                    'note', 'tools', FLATNOTES_PORT, install_dir, venv_python,
                    f'http://localhost:{FLATNOTES_PORT}'
                ))
                db.commit()
            finally:
                db.close()

            with _dl_progress_lock:
                _download_progress[SERVICE_ID] = {'percent': 100, 'status': 'complete', 'error': None}
            log.info('FlatNotes installed successfully')

        except Exception as e:
            log.error(f'FlatNotes install failed: {e}')
            with _dl_progress_lock:
                _download_progress[SERVICE_ID] = {'percent': 0, 'status': 'error', 'error': str(e)}
            raise

    do_install()


def start():
    """Start FlatNotes server."""
    if not is_installed():
        raise RuntimeError('FlatNotes is not installed')
    if running():
        return

    install_dir = get_install_dir()
    venv_dir = os.path.join(install_dir, 'venv')

    if sys.platform == 'win32':
        flatnotes_bin = os.path.join(venv_dir, 'Scripts', 'flatnotes.exe')
        python_bin = os.path.join(venv_dir, 'Scripts', 'python.exe')
    else:
        flatnotes_bin = os.path.join(venv_dir, 'bin', 'flatnotes')
        python_bin = os.path.join(venv_dir, 'bin', 'python')

    data_dir = _get_data_dir()
    env = os.environ.copy()
    env['FLATNOTES_PATH'] = data_dir
    env['FLATNOTES_PORT'] = str(FLATNOTES_PORT)
    # Bind to the same interface as the rest of NOMAD so FlatNotes is not
    # inadvertently exposed to the LAN when auth is disabled.
    from config import Config
    env['FLATNOTES_HOST'] = Config.APP_HOST
    # Disable authentication for local use
    env['FLATNOTES_AUTH_TYPE'] = 'none'

    if os.path.isfile(flatnotes_bin):
        cmd = [flatnotes_bin]
    else:
        cmd = [python_bin, '-m', 'flatnotes']

    start_process(SERVICE_ID, cmd, port=FLATNOTES_PORT, env=env)
    log.info(f'FlatNotes started on port {FLATNOTES_PORT}')


def stop():
    stop_process(SERVICE_ID)
    log.info('FlatNotes stopped')


def running():
    return _is_running(SERVICE_ID) and check_port(FLATNOTES_PORT)


def get_url():
    return f'http://localhost:{FLATNOTES_PORT}'
