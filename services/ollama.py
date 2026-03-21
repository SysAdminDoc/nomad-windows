"""Ollama service — local AI chat with LLMs."""

import os
import subprocess
import threading
import time
import logging
import requests
from services.manager import (
    get_services_dir, download_file, start_process, stop_process,
    is_running, check_port, _download_progress
)
from db import get_db

log = logging.getLogger('nomad.ollama')

SERVICE_ID = 'ollama'
OLLAMA_PORT = 11434
OLLAMA_URL = 'https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip'
DEFAULT_MODEL = 'llama3.2:3b'


def get_install_dir():
    return os.path.join(get_services_dir(), 'ollama')


def get_exe_path():
    return os.path.join(get_install_dir(), 'ollama.exe')


def is_installed():
    return os.path.isfile(get_exe_path())


def install(callback=None):
    """Download and install Ollama."""
    install_dir = get_install_dir()
    os.makedirs(install_dir, exist_ok=True)
    zip_path = os.path.join(install_dir, 'ollama.zip')

    _download_progress[SERVICE_ID] = {'percent': 0, 'status': 'downloading', 'error': None}

    try:
        download_file(OLLAMA_URL, zip_path, SERVICE_ID)

        _download_progress[SERVICE_ID]['status'] = 'extracting'
        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(install_dir)
        os.remove(zip_path)

        # Register in DB
        db = get_db()
        db.execute('''
            INSERT OR REPLACE INTO services (id, name, description, icon, category, installed, port, install_path, exe_path, url)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
        ''', (
            SERVICE_ID, 'Ollama (AI Chat)', 'Local AI chat powered by large language models',
            'brain', 'ai', OLLAMA_PORT, install_dir, get_exe_path(),
            f'http://localhost:{OLLAMA_PORT}'
        ))
        db.commit()
        db.close()

        _download_progress[SERVICE_ID] = {'percent': 100, 'status': 'complete', 'error': None}
        log.info('Ollama installed successfully')

    except Exception as e:
        _download_progress[SERVICE_ID] = {'percent': 0, 'status': 'error', 'error': str(e)}
        log.error(f'Ollama install failed: {e}')
        raise


def start():
    """Start Ollama server."""
    if not is_installed():
        raise RuntimeError('Ollama is not installed')

    env = os.environ.copy()
    env['OLLAMA_HOST'] = f'0.0.0.0:{OLLAMA_PORT}'
    env['OLLAMA_MODELS'] = os.path.join(get_install_dir(), 'models')

    CREATE_NO_WINDOW = 0x08000000
    proc = subprocess.Popen(
        [get_exe_path(), 'serve'],
        cwd=get_install_dir(),
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

    # Wait for port
    for _ in range(30):
        if check_port(OLLAMA_PORT):
            log.info(f'Ollama running on port {OLLAMA_PORT} (PID {proc.pid})')
            return proc.pid
        time.sleep(1)

    log.warning('Ollama started but port not yet responding')
    return proc.pid


def stop():
    return stop_process(SERVICE_ID)


def running():
    return is_running(SERVICE_ID) and check_port(OLLAMA_PORT)


def list_models():
    """Get list of downloaded models."""
    try:
        resp = requests.get(f'http://localhost:{OLLAMA_PORT}/api/tags', timeout=5)
        if resp.ok:
            return resp.json().get('models', [])
    except Exception:
        pass
    return []


def pull_model(model_name: str):
    """Pull/download a model."""
    try:
        resp = requests.post(
            f'http://localhost:{OLLAMA_PORT}/api/pull',
            json={'name': model_name, 'stream': False},
            timeout=600,
        )
        return resp.ok
    except Exception as e:
        log.error(f'Model pull failed: {e}')
        return False


def chat(model: str, messages: list[dict], stream: bool = True):
    """Send chat request to Ollama."""
    resp = requests.post(
        f'http://localhost:{OLLAMA_PORT}/api/chat',
        json={'model': model, 'messages': messages, 'stream': stream},
        stream=stream,
        timeout=300,
    )
    resp.raise_for_status()

    if stream:
        return resp.iter_lines()
    else:
        return resp.json()
