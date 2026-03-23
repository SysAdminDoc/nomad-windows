"""Ollama service — local AI chat with LLMs."""

import os
import subprocess
import time
import logging
import requests
from services.manager import (
    get_services_dir, download_file, start_process, stop_process,
    is_running, check_port, _download_progress, get_ollama_gpu_env
)
from db import get_db

log = logging.getLogger('nomad.ollama')

SERVICE_ID = 'ollama'
OLLAMA_PORT = 11434
OLLAMA_URL = 'https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip'
DEFAULT_MODEL = 'llama3.2:3b'

_pull_progress = {'status': 'idle', 'model': '', 'percent': 0, 'detail': ''}

RECOMMENDED_MODELS = [
    # Small (under 4GB) — fast, practical knowledge
    {'name': 'qwen3:4b', 'size': '2.5 GB', 'desc': 'Best small model — dual thinking mode, rivals 72B on reasoning'},
    {'name': 'gemma3:4b', 'size': '3.3 GB', 'desc': 'Google Gemma 3 — multimodal (analyzes images), 128K context'},
    {'name': 'phi4-mini', 'size': '2.3 GB', 'desc': 'Microsoft Phi-4 Mini — exceptional instruction following'},
    {'name': 'llama3.2:3b', 'size': '2.0 GB', 'desc': 'Meta Llama — reliable, battle-tested, great starting point'},
    {'name': 'llama3.2:1b', 'size': '1.3 GB', 'desc': 'Ultra-light for low-RAM systems (4GB RAM OK)'},
    # Medium (4-8GB) — detailed technical answers
    {'name': 'qwen3:8b', 'size': '5.2 GB', 'desc': 'Best medium model — thinking mode for step-by-step procedures'},
    {'name': 'deepseek-r1:8b', 'size': '5.2 GB', 'desc': 'DeepSeek reasoning — chain-of-thought problem solving'},
    {'name': 'gemma3:12b', 'size': '8.1 GB', 'desc': 'Google Gemma 3 12B — multimodal, strong medical/technical'},
    {'name': 'llama3.1:8b', 'size': '4.7 GB', 'desc': 'Most battle-tested model on Ollama (108M+ downloads)'},
    {'name': 'mistral:7b', 'size': '4.1 GB', 'desc': 'Strong reasoning, great for step-by-step procedures'},
    # Specialized — medical, agriculture
    {'name': 'alibayram/medgemma', 'size': '3.3 GB', 'desc': 'Medical AI — can analyze wound photos, X-rays, symptoms'},
    {'name': 'meditron:7b', 'size': '3.8 GB', 'desc': 'Medical AI by EPFL — clinical knowledge, drug interactions'},
]


def get_models_dir():
    """Return the app's models directory (always uses configured data dir)."""
    app_dir = os.path.join(get_install_dir(), 'models')
    os.makedirs(app_dir, exist_ok=True)
    return app_dir


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

    _download_progress[SERVICE_ID] = {
        'percent': 0, 'status': 'downloading', 'error': None,
        'speed': '', 'downloaded': 0, 'total': 0,
    }

    try:
        download_file(OLLAMA_URL, zip_path, SERVICE_ID)

        _download_progress[SERVICE_ID]['status'] = 'extracting'
        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(install_dir)
        os.remove(zip_path)

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

        _download_progress[SERVICE_ID] = {
            'percent': 100, 'status': 'complete', 'error': None,
            'speed': '', 'downloaded': 0, 'total': 0,
        }
        log.info('Ollama installed successfully')

    except Exception as e:
        _download_progress[SERVICE_ID] = {
            'percent': 0, 'status': 'error', 'error': str(e),
            'speed': '', 'downloaded': 0, 'total': 0,
        }
        log.error(f'Ollama install failed: {e}')
        raise


def start():
    """Start Ollama server."""
    if not is_installed():
        raise RuntimeError('Ollama is not installed')

    models_dir = get_models_dir()

    # If something is already on our port, kill it so we can start with correct OLLAMA_MODELS
    if check_port(OLLAMA_PORT):
        log.info('Port 11434 in use — stopping existing Ollama to ensure correct models directory')
        _kill_port_holder(OLLAMA_PORT)
        time.sleep(1)

    env = get_ollama_gpu_env()
    env['OLLAMA_HOST'] = f'0.0.0.0:{OLLAMA_PORT}'
    env['OLLAMA_MODELS'] = models_dir

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
    if is_running(SERVICE_ID) and check_port(OLLAMA_PORT):
        return True
    # Fallback: PID tracking may be stale after app restart — check if Ollama API responds
    if check_port(OLLAMA_PORT):
        try:
            resp = requests.get(f'http://localhost:{OLLAMA_PORT}/api/tags', timeout=2)
            if resp.ok:
                log.info('Ollama running (detected via API, updating PID tracking)')
                _adopt_running_instance()
                return True
        except Exception:
            pass
    return False


def _kill_port_holder(port):
    """Kill whatever process is holding the given port."""
    try:
        import subprocess as _sp
        result = _sp.run(
            ['powershell', '-NoProfile', '-Command',
             f"(Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess"],
            capture_output=True, text=True, timeout=5, creationflags=0x08000000,
        )
        pid = int(result.stdout.strip()) if result.returncode == 0 and result.stdout.strip() else None
        if pid and pid > 0:
            log.info(f'Killing PID {pid} holding port {port}')
            _sp.run(['taskkill', '/F', '/PID', str(pid)],
                    capture_output=True, timeout=5, creationflags=0x08000000)
    except Exception as e:
        log.warning(f'Could not kill port holder: {e}')


def _adopt_running_instance():
    """Update DB/process tracking when Ollama is running but PID tracking is stale."""
    from services.manager import _processes
    try:
        # Find the actual Ollama PID via the port
        import subprocess as _sp
        result = _sp.run(
            ['powershell', '-NoProfile', '-Command',
             f"(Get-NetTCPConnection -LocalPort {OLLAMA_PORT} -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess"],
            capture_output=True, text=True, timeout=5, creationflags=0x08000000,
        )
        pid = int(result.stdout.strip()) if result.returncode == 0 and result.stdout.strip() else None
        if pid:
            db = get_db()
            db.execute('UPDATE services SET running = 1, pid = ? WHERE id = ?', (pid, SERVICE_ID))
            db.commit()
            db.close()
            log.info(f'Adopted running Ollama instance (PID {pid})')
    except Exception as e:
        log.warning(f'Could not adopt Ollama PID: {e}')


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
    """Pull/download a model with progress tracking."""
    global _pull_progress
    _pull_progress = {'status': 'pulling', 'model': model_name, 'percent': 0, 'detail': 'Starting...'}

    try:
        resp = requests.post(
            f'http://localhost:{OLLAMA_PORT}/api/pull',
            json={'name': model_name, 'stream': True},
            stream=True,
            timeout=1800,
        )
        resp.raise_for_status()

        import json
        import time as _time
        _pull_max_pct = 0
        _pull_last_bytes = 0
        _pull_last_time = _time.time()
        for line in resp.iter_lines():
            if not line:
                continue
            try:
                data = json.loads(line)
                status = data.get('status', '')
                total = data.get('total', 0)
                completed = data.get('completed', 0)
                pct = int(completed / total * 100) if total > 0 else 0
                # Prevent backward jumps when Ollama switches layers
                _pull_max_pct = max(_pull_max_pct, pct)

                # Calculate speed
                speed_str = ''
                now = _time.time()
                if completed > 0 and total > 0 and now - _pull_last_time >= 1:
                    bytes_delta = completed - _pull_last_bytes
                    time_delta = now - _pull_last_time
                    if bytes_delta > 0 and time_delta > 0:
                        bps = bytes_delta / time_delta
                        speed_str = f'{bps/1024/1024:.1f} MB/s' if bps > 1024*1024 else f'{bps/1024:.0f} KB/s'
                    _pull_last_bytes = completed
                    _pull_last_time = now

                # Build size display
                size_str = ''
                if total > 0:
                    size_str = f'{completed/1024/1024/1024:.1f}/{total/1024/1024/1024:.1f} GB' if total > 1024**3 else f'{completed/1024/1024:.0f}/{total/1024/1024:.0f} MB'

                _pull_progress = {
                    'status': 'pulling',
                    'model': model_name,
                    'percent': _pull_max_pct,
                    'detail': f'{status} {size_str} {speed_str}'.strip(),
                }
            except Exception:
                pass

        _pull_progress = {'status': 'complete', 'model': model_name, 'percent': 100, 'detail': 'Done'}
        log.info(f'Model {model_name} pulled successfully')
        return True
    except Exception as e:
        detail = str(e)
        if 'Connection refused' in detail or 'ConnectionError' in detail:
            detail = 'AI service is not running. Start Ollama from the Home tab first.'
        elif 'not found' in detail.lower():
            detail = f'Model "{model_name}" not found. Check the name and try again.'
        _pull_progress = {'status': 'error', 'model': model_name, 'percent': 0, 'detail': detail}
        log.error(f'Model pull failed: {e}')
        return False


def get_pull_progress():
    return _pull_progress


def delete_model(model_name: str) -> bool:
    """Delete a downloaded model."""
    try:
        resp = requests.delete(
            f'http://localhost:{OLLAMA_PORT}/api/delete',
            json={'name': model_name},
            timeout=30,
        )
        return resp.ok
    except Exception as e:
        log.error(f'Model delete failed: {e}')
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
