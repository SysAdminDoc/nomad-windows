"""
Native Windows process manager for N.O.M.A.D. services.
Downloads, installs, starts, and stops services as native processes.
"""

import os
import subprocess
import signal
import time
import threading
import requests
import zipfile
import shutil
import logging
from db import get_db

log = logging.getLogger('nomad.manager')

DATA_DIR = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'ProjectNOMAD')
SERVICES_DIR = os.path.join(DATA_DIR, 'services')

# Track running processes
_processes: dict[str, subprocess.Popen] = {}
_download_progress: dict[str, dict] = {}


def get_services_dir():
    os.makedirs(SERVICES_DIR, exist_ok=True)
    return SERVICES_DIR


def download_file(url: str, dest: str, service_id: str = '') -> str:
    """Download a file with progress tracking."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    _download_progress[service_id] = {'percent': 0, 'status': 'downloading', 'error': None}

    try:
        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()
        total = int(resp.headers.get('content-length', 0))
        downloaded = 0

        with open(dest, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    _download_progress[service_id]['percent'] = int(downloaded / total * 100)

        _download_progress[service_id] = {'percent': 100, 'status': 'complete', 'error': None}
        return dest
    except Exception as e:
        _download_progress[service_id] = {'percent': 0, 'status': 'error', 'error': str(e)}
        raise


def extract_zip(zip_path: str, dest_dir: str):
    """Extract a zip file."""
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(dest_dir)
    os.remove(zip_path)


def start_process(service_id: str, exe_path: str, args: list[str] = None,
                  cwd: str = None, port: int = None) -> int:
    """Start a native process and track it."""
    if service_id in _processes and _processes[service_id].poll() is None:
        return _processes[service_id].pid

    cmd = [exe_path] + (args or [])
    log.info(f'Starting {service_id}: {" ".join(cmd)}')

    # Use CREATE_NO_WINDOW to hide console
    CREATE_NO_WINDOW = 0x08000000
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=CREATE_NO_WINDOW,
    )
    _processes[service_id] = proc

    db = get_db()
    db.execute('UPDATE services SET running = 1, pid = ? WHERE id = ?', (proc.pid, service_id))
    db.commit()
    db.close()

    return proc.pid


def stop_process(service_id: str) -> bool:
    """Stop a tracked process."""
    proc = _processes.get(service_id)
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    # Also try by PID from DB
    db = get_db()
    row = db.execute('SELECT pid FROM services WHERE id = ?', (service_id,)).fetchone()
    if row and row['pid']:
        try:
            os.kill(row['pid'], signal.SIGTERM)
        except (OSError, ProcessLookupError):
            pass

    db.execute('UPDATE services SET running = 0, pid = NULL WHERE id = ?', (service_id,))
    db.commit()
    db.close()

    _processes.pop(service_id, None)
    return True


def is_running(service_id: str) -> bool:
    """Check if a service process is alive."""
    proc = _processes.get(service_id)
    if proc and proc.poll() is None:
        return True

    db = get_db()
    row = db.execute('SELECT pid FROM services WHERE id = ?', (service_id,)).fetchone()
    db.close()

    if row and row['pid']:
        try:
            os.kill(row['pid'], 0)
            return True
        except (OSError, ProcessLookupError):
            pass

    return False


def get_download_progress(service_id: str) -> dict:
    return _download_progress.get(service_id, {'percent': 0, 'status': 'idle', 'error': None})


def check_port(port: int) -> bool:
    """Check if a port is responding."""
    import socket
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=2):
            return True
    except (ConnectionRefusedError, OSError, socket.timeout):
        return False
