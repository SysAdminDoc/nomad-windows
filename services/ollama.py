"""Ollama service — local AI chat with LLMs."""

import json
import os
import time
import logging
import threading
import requests
from services.manager import (
    get_services_dir, download_file, start_process, stop_process,
    is_running, check_port, _download_progress, _dl_progress_lock,
)
from db import get_db

log = logging.getLogger('nomad.ollama')

SERVICE_ID = 'ollama'
OLLAMA_PORT = 11434
def _get_ollama_url():
    from platform_utils import get_ollama_url
    return get_ollama_url()
DEFAULT_MODEL = 'llama3.2:3b'

_pull_progress = {'status': 'idle', 'model': '', 'percent': 0, 'detail': ''}

# Serializes concurrent start()/stop() so a second caller can't race past the
# double-start guard and kill our own port holder while the first call is
# still mid-launch. Also pairs with the guard inside start() itself.
_start_lock = threading.Lock()

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


def _load_stream_json_line(line):
    if isinstance(line, (bytes, bytearray)):
        text = line.decode('utf-8', errors='ignore')
    elif isinstance(line, str):
        text = line
    else:
        return None
    text = text.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _safe_response_payload(response, fallback=None):
    """Parse a Response body as JSON with a caller-supplied fallback.

    Narrowed from bare ``Exception`` to the real failure surface:
    ``ValueError`` covers both ``json.JSONDecodeError`` and the
    ``requests.exceptions.JSONDecodeError`` subclass;
    ``TypeError`` / ``AttributeError`` cover a malformed Response object.
    A programming error (NameError, ImportError) must still surface.
    """
    if fallback is None:
        fallback = {}
    if response is None:
        if isinstance(fallback, dict):
            return dict(fallback)
        if isinstance(fallback, list):
            return list(fallback)
        return fallback
    try:
        parsed = response.json()
    except (ValueError, TypeError, AttributeError):
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


def get_models_dir():
    """Return the app's models directory (always uses configured data dir)."""
    app_dir = os.path.join(get_install_dir(), 'models')
    os.makedirs(app_dir, exist_ok=True)
    return app_dir


def get_install_dir():
    return os.path.join(get_services_dir(), 'ollama')


def get_exe_path():
    from platform_utils import exe_name
    binary = exe_name('ollama')
    install_dir = get_install_dir()
    exe = os.path.join(install_dir, binary)
    if os.path.isfile(exe):
        return exe
    # Ollama tarballs may extract to bin/ subdirectory
    for root, dirs, files in os.walk(install_dir):
        if binary in files:
            return os.path.join(root, binary)
    return exe


def is_installed():
    return os.path.isfile(get_exe_path())


def install(callback=None):
    """Download and install Ollama."""
    install_dir = get_install_dir()
    os.makedirs(install_dir, exist_ok=True)
    from platform_utils import IS_WINDOWS, extract_archive, make_executable

    with _dl_progress_lock:
        _download_progress[SERVICE_ID] = {
            'percent': 0, 'status': 'downloading', 'error': None,
            'speed': '', 'downloaded': 0, 'total': 0,
        }

    try:
        arc_ext = '.zip' if IS_WINDOWS else '.tgz'
        arc_path = os.path.join(install_dir, 'ollama' + arc_ext)
        download_file(_get_ollama_url(), arc_path, SERVICE_ID)
        with _dl_progress_lock:
            _download_progress[SERVICE_ID]['status'] = 'extracting'
        extract_archive(arc_path, install_dir)
        make_executable(get_exe_path())

        db = get_db()
        try:
            db.execute('''
                INSERT OR REPLACE INTO services (id, name, description, icon, category, installed, port, install_path, exe_path, url)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
            ''', (
                SERVICE_ID, 'Ollama (AI Chat)', 'Local AI chat powered by large language models',
                'brain', 'ai', OLLAMA_PORT, install_dir, get_exe_path(),
                f'http://localhost:{OLLAMA_PORT}'
            ))
            db.commit()
        finally:
            db.close()

        with _dl_progress_lock:
            _download_progress[SERVICE_ID] = {
                'percent': 100, 'status': 'complete', 'error': None,
                'speed': '', 'downloaded': 0, 'total': 0,
            }
        log.info('Ollama installed successfully')

    except Exception as e:
        with _dl_progress_lock:
            _download_progress[SERVICE_ID] = {
                'percent': 0, 'status': 'error', 'error': str(e),
                'speed': '', 'downloaded': 0, 'total': 0,
            }
        log.error(f'Ollama install failed: {e}')
        raise


def start():
    """Start Ollama server. No-op when our instance is already running.

    Concurrent callers serialize on ``_start_lock`` only for the mutating
    critical section (guard check → port reclaim → launch). The lock is
    released BEFORE the ~30 s port-responsiveness poll so a concurrent
    ``stop()`` or ``running()`` caller (e.g. shutdown handler, UI status
    tick) isn't blocked up to 30 s waiting for the launch confirmation.
    """
    if not is_installed():
        raise RuntimeError('Ollama is not installed')

    pid = None
    with _start_lock:
        # Fast path: our tracked instance is alive and the port answers.
        # Return the PID we already registered instead of relaunching.
        if is_running(SERVICE_ID) and check_port(OLLAMA_PORT):
            db = get_db()
            try:
                row = db.execute(
                    'SELECT pid FROM services WHERE id = ?', (SERVICE_ID,)
                ).fetchone()
                registered_pid = row['pid'] if row and row['pid'] else None
            finally:
                db.close()
            if registered_pid:
                log.debug(
                    'Ollama already running (PID %s) — start() returning existing instance',
                    registered_pid,
                )
                return registered_pid
            # Port answers but we have no PID — fall through to adoption below.

        models_dir = get_models_dir()

        # If something is already on our port (not tracked as ours), reclaim it.
        if check_port(OLLAMA_PORT):
            from platform_utils import find_pid_on_port
            holder_pid = find_pid_on_port(OLLAMA_PORT)
            db = get_db()
            try:
                row = db.execute('SELECT pid FROM services WHERE id = ?', (SERVICE_ID,)).fetchone()
                registered_pid = row['pid'] if row and row['pid'] else None
            finally:
                db.close()
            if holder_pid and holder_pid == registered_pid:
                log.info(f'Port {OLLAMA_PORT} held by our own registered PID {holder_pid} — stopping stale instance')
            elif holder_pid:
                log.warning(f'Port {OLLAMA_PORT} held by external PID {holder_pid} (not ours) — killing to reclaim port')
            else:
                log.info(f'Port {OLLAMA_PORT} in use — stopping existing process')
            _kill_port_holder(OLLAMA_PORT)
            time.sleep(1)

        from platform_utils import get_ollama_gpu_env
        env = get_ollama_gpu_env()
        from config import Config
        env['OLLAMA_HOST'] = f'{Config.APP_HOST}:{OLLAMA_PORT}'
        env['OLLAMA_MODELS'] = models_dir

        pid = start_process(SERVICE_ID, get_exe_path(), args=['serve'], cwd=get_install_dir(), env=env)
    # ── lock released — the process is launched + tracked; from here the
    # only work left is waiting for the port to answer, which must NOT
    # block other callers (stop, running, UI heartbeat).

    for _ in range(30):
        if check_port(OLLAMA_PORT):
            log.info(f'Ollama running on port {OLLAMA_PORT} (PID {pid})')
            return pid
        time.sleep(1)

    log.warning('Ollama started but port not yet responding')
    return pid


def stop():
    # stop_process has its own internal _lock in services.manager — we don't
    # need to take _start_lock here; doing so would risk deadlock if the
    # shutdown path is ever called while a launch is polling the port.
    return stop_process(SERVICE_ID)


def running():
    if is_running(SERVICE_ID) and check_port(OLLAMA_PORT):
        return True
    # Fallback: PID tracking may be stale after app restart — check if Ollama API responds
    if check_port(OLLAMA_PORT):
        resp = None
        try:
            resp = requests.get(f'http://localhost:{OLLAMA_PORT}/api/tags', timeout=2)
            if resp.ok:
                log.info('Ollama running (detected via API, updating PID tracking)')
                _adopt_running_instance()
                return True
        except Exception:
            pass
        finally:
            if resp is not None:
                try:
                    resp.close()
                except Exception:
                    pass
    return False


def _kill_port_holder(port):
    """Kill whatever process is holding the given port."""
    from platform_utils import find_pid_on_port, kill_pid
    try:
        pid = find_pid_on_port(port)
        if pid and pid > 0:
            log.info(f'Killing PID {pid} holding port {port}')
            kill_pid(pid)
    except Exception as e:
        log.warning(f'Could not kill port holder: {e}')


def _adopt_running_instance():
    """Update DB/process tracking when Ollama is running but PID tracking is stale."""
    from platform_utils import find_pid_on_port
    try:
        pid = find_pid_on_port(OLLAMA_PORT)
        if pid:
            db = get_db()
            try:
                db.execute('UPDATE services SET running = 1, pid = ? WHERE id = ?', (pid, SERVICE_ID))
                db.commit()
            finally:
                db.close()
            log.info(f'Adopted running Ollama instance (PID {pid})')
    except Exception as e:
        log.warning(f'Could not adopt Ollama PID: {e}')


def list_models():
    """Get list of downloaded models."""
    resp = None
    try:
        resp = requests.get(f'http://localhost:{OLLAMA_PORT}/api/tags', timeout=5)
        if resp.ok:
            payload = _safe_response_payload(resp, {})
            models = payload.get('models', []) if isinstance(payload, dict) else []
            return models if isinstance(models, list) else []
        log.debug('Ollama model list returned HTTP %s', resp.status_code)
    except (requests.RequestException, ValueError) as exc:
        log.debug('Could not list Ollama models: %s', exc)
    finally:
        # Always release the socket/FD. try/finally (rather than ``with``)
        # keeps compatibility with test fixtures that return simple mock
        # objects not implementing the context-manager protocol.
        if resp is not None:
            try:
                resp.close()
            except Exception:
                pass
    return []


def pull_model(model_name: str):
    """Pull/download a model with progress tracking."""
    global _pull_progress
    _pull_progress = {'status': 'pulling', 'model': model_name, 'percent': 0, 'detail': 'Starting...'}

    resp = None
    try:
        resp = requests.post(
            f'http://localhost:{OLLAMA_PORT}/api/pull',
            json={'name': model_name, 'stream': True},
            stream=True,
            timeout=1800,
        )
        resp.raise_for_status()

        import time as _time
        _pull_max_pct = 0
        _pull_last_bytes = 0
        _pull_last_time = _time.time()
        saw_valid_chunk = False
        saw_success = False
        for line in resp.iter_lines():
            if not line:
                continue
            data = _load_stream_json_line(line)
            if not data:
                logging.debug('pull_model parse error: unreadable chunk')
                continue
            saw_valid_chunk = True
            status = str(data.get('status', ''))
            total = int(data.get('total', 0) or 0)
            completed = int(data.get('completed', 0) or 0)
            pct = int(completed / total * 100) if total > 0 else 0
            # Prevent backward jumps when Ollama switches layers
            _pull_max_pct = max(_pull_max_pct, pct)
            if status.lower() in {'success', 'complete', 'completed', 'done'} or (total > 0 and completed >= total):
                saw_success = True

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

        if not saw_valid_chunk:
            _pull_progress = {
                'status': 'error',
                'model': model_name,
                'percent': 0,
                'detail': 'AI service returned unreadable pull progress data.',
            }
            log.warning('Model pull failed: unreadable progress stream for %s', model_name)
            return False
        _pull_progress = {'status': 'complete', 'model': model_name, 'percent': 100, 'detail': 'Done'}
        if not saw_success:
            log.debug('Model pull stream ended without explicit success marker for %s', model_name)
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
    finally:
        if resp is not None:
            try:
                resp.close()
            except Exception:
                pass


def get_pull_progress():
    return _pull_progress


def delete_model(model_name: str) -> bool:
    """Delete a downloaded model."""
    import re
    if not re.match(r'^[a-zA-Z0-9._:/-]+$', model_name):
        log.warning('Invalid model name rejected: %s', model_name)
        return False
    # Defensive length cap — the route already limits this, but callers
    # that bypass the HTTP layer (tests, future helpers) shouldn't be
    # able to flood Ollama with a multi-megabyte name.
    if len(model_name) > 200:
        log.warning('Model name exceeds 200 chars — rejected')
        return False
    resp = None
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
    finally:
        if resp is not None:
            try:
                resp.close()
            except Exception:
                pass


def chat(model: str, messages: list[dict], stream: bool = True):
    """Send chat request to Ollama. Caller must consume or close the response for streaming."""
    try:
        resp = requests.post(
            f'http://localhost:{OLLAMA_PORT}/api/chat',
            json={'model': model, 'messages': messages, 'stream': stream},
            stream=stream,
            timeout=300,
        )
    except requests.ConnectionError:
        raise RuntimeError('AI service is not running. Start Ollama from the Home tab.')
    except requests.Timeout:
        raise RuntimeError('AI request timed out. The model may be too large for your system.')
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        # Always release the socket before raising — earlier the 404 branch
        # bailed without closing, leaking one FD per model-not-found call.
        resp.close()
        if e.response is not None and e.response.status_code == 404:
            raise RuntimeError(f'Model "{model}" not found. Pull it first from the AI Models tab.')
        raise

    if stream:
        def _streaming_lines():
            try:
                yield from resp.iter_lines()
            finally:
                resp.close()
        return _streaming_lines()
    # Non-streaming path — make sure the socket is released once we've
    # materialised the JSON payload. Previously the caller never closed it
    # and we leaked one FD per synchronous chat call.
    try:
        return _safe_response_payload(resp, {})
    finally:
        resp.close()
