"""
Cross-platform process manager for NOMAD Field Desk services.
Downloads, installs, starts, and stops services as native processes.
Includes dependency graph, auto-restart, download resume, GPU detection.
"""

import os
import subprocess
import signal
import time
import threading
import socket
import requests
import zipfile
import shutil
import logging
from collections import deque
from urllib.parse import urlparse
from db import get_db, log_activity
from config import get_data_dir

log = logging.getLogger('nomad.manager')

# Track running processes — guarded by _lock for thread safety
_processes: dict[str, subprocess.Popen] = {}
_download_progress: dict[str, dict] = {}
_service_logs: dict[str, deque] = {}
_lock = threading.Lock()
_dl_progress_lock = threading.Lock()
_svc_logs_lock = threading.Lock()

# Service dependency graph: service -> list of services it requires
DEPENDENCIES = {
    'ollama': [],
    'kiwix': [],
    'cyberchef': [],
    'kolibri': [],
    'qdrant': ['ollama'],      # Qdrant needs Ollama for embeddings
    'stirling': [],
    'flatnotes': [],
    'torrent': [],
}

# Reverse: which services depend on this one (for ordered shutdown)
DEPENDENTS = {
    'ollama': ['qdrant'],      # Stopping Ollama affects Qdrant
}

# Restart policy: max restart attempts within a window
MAX_RESTARTS = 3
RESTART_WINDOW = 300  # seconds
_restart_tracker: dict[str, list[float]] = {}  # service_id -> list of restart timestamps

# Service start timestamps for uptime display
_start_times: dict[str, float] = {}  # service_id -> time.time() when started


def get_services_dir():
    svc_dir = os.path.join(get_data_dir(), 'services')
    os.makedirs(svc_dir, exist_ok=True)
    return svc_dir


# Shared identity header for every outbound GitHub API call. GitHub
# rejects requests without a User-Agent with HTTP 403, which surfaces as
# a confusing "release not found" failure in the install flow. Setting
# it here keeps every service module consistent.
GITHUB_USER_AGENT = 'NOMAD-FieldDesk/1.0 (+https://github.com/SysAdminDoc)'
GITHUB_API_HEADERS = {
    'User-Agent': GITHUB_USER_AGENT,
    'Accept': 'application/vnd.github+json',
}


# ─── GPU Detection ────────────────────────────────────────────────────

_gpu_info = None
_gpu_lock = threading.Lock()


def detect_gpu() -> dict:
    """Detect GPU type and capabilities (cross-platform)."""
    global _gpu_info
    if _gpu_info is not None:
        return _gpu_info
    with _gpu_lock:
        if _gpu_info is not None:
            return _gpu_info
        from platform_utils import detect_gpu as _detect_gpu
        _gpu_info = _detect_gpu()
        return _gpu_info


def get_ollama_gpu_env() -> dict:
    """Get environment variables for Ollama based on detected GPU."""
    from platform_utils import get_ollama_gpu_env as _get_gpu_env
    return _get_gpu_env()


# ─── Download with Resume ─────────────────────────────────────────────

def download_file(url: str, dest: str, service_id: str = '') -> str:
    """Download a file with progress tracking, speed display, and resume support."""
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        raise ValueError(f'Unsupported URL scheme: {parsed.scheme}')
    dest_dir = os.path.dirname(dest)
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)

    # Check for partial download
    partial_size = 0
    if os.path.isfile(dest):
        partial_size = os.path.getsize(dest)

    with _dl_progress_lock:
        _download_progress[service_id] = {
            'percent': 0, 'status': 'downloading', 'error': None,
            'speed': '', 'downloaded': partial_size, 'total': 0,
        }

    try:
        headers = {}
        if partial_size > 0:
            headers['Range'] = f'bytes={partial_size}-'
            log.info(f'Resuming download for {service_id} from {partial_size} bytes')

        resp = requests.get(url, stream=True, timeout=30, headers=headers)

        if resp.status_code == 416:
            with _dl_progress_lock:
                _download_progress[service_id] = {
                    'percent': 100, 'status': 'complete', 'error': None,
                    'speed': '', 'downloaded': partial_size, 'total': partial_size,
                }
            return dest

        if partial_size > 0 and resp.status_code != 206:
            partial_size = 0

        resp.raise_for_status()

        total = int(resp.headers.get('content-length', 0)) + partial_size
        downloaded = partial_size
        start_time = time.time()

        mode = 'ab' if partial_size > 0 and resp.status_code == 206 else 'wb'
        with open(dest, mode) as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
                downloaded += len(chunk)
                elapsed = time.time() - start_time
                speed = (downloaded - partial_size) / elapsed if elapsed > 0 else 0

                if speed > 1024 * 1024:
                    speed_str = f'{speed / (1024 * 1024):.1f} MB/s'
                elif speed > 1024:
                    speed_str = f'{speed / 1024:.0f} KB/s'
                else:
                    speed_str = f'{speed:.0f} B/s'

                with _dl_progress_lock:
                    _download_progress[service_id].update({
                        'percent': min(int(downloaded / total * 100), 100) if total > 0 else 0,
                        'speed': speed_str,
                        'downloaded': downloaded,
                        'total': total,
                    })

        with _dl_progress_lock:
            _download_progress[service_id] = {
                'percent': 100, 'status': 'complete', 'error': None,
                'speed': '', 'downloaded': total, 'total': total,
                '_finished_at': time.time(),
            }
        return dest
    except Exception as e:
        with _dl_progress_lock:
            _download_progress[service_id] = {
                'percent': 0, 'status': 'error', 'error': str(e),
                'speed': '', 'downloaded': 0, 'total': 0,
                '_finished_at': time.time(),
            }
        # Keep partial file for resume on next attempt
        log.warning(f'Download failed for {service_id}, partial file kept for resume: {e}')
        raise


def extract_zip(zip_path: str, dest_dir: str):
    """Extract a zip file with path traversal protection."""
    dest = os.path.realpath(dest_dir)
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for member in zf.infolist():
            member_path = os.path.realpath(os.path.join(dest, member.filename))
            if not member_path.startswith(dest + os.sep) and member_path != dest:
                raise ValueError(f'Zip Slip detected: {member.filename} escapes {dest_dir}')
        # Use the resolved dest (realpath) for extraction to prevent TOCTOU
        # where dest_dir is a symlink that changes between validation and extract.
        zf.extractall(dest)
    os.remove(zip_path)


# ─── Process Management ────────────────────────────────────────────────

def start_process(service_id: str, exe_path, args: list[str] = None,
                  cwd: str = None, port: int = None, env: dict = None) -> int:
    """Start a native process and track it. Captures stdout/stderr for log viewer."""
    with _lock:
        if service_id in _processes and _processes[service_id].poll() is None:
            return _processes[service_id].pid

        # Support exe_path as either a string or a list (for [python, -m, module] style)
        if isinstance(exe_path, list):
            cmd = exe_path + (args or [])
        else:
            cmd = [exe_path] + (args or [])
        log.info(f'Starting {service_id}: {" ".join(cmd)}')

        from platform_utils import popen_kwargs
        # Capture stdout/stderr with PIPE for log viewer
        proc = subprocess.Popen(
            cmd,
            **popen_kwargs(cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT),
        )

        # Start background thread to read output into _service_logs
        # NOTE: service logs may contain filesystem paths — acceptable for local desktop app
        with _svc_logs_lock:
            log_deque = _service_logs.setdefault(service_id, deque(maxlen=500))
        def _read_output():
            try:
                for line in iter(proc.stdout.readline, b''):
                    if not line:
                        break
                    decoded = line.decode('utf-8', errors='replace').rstrip('\n\r')
                    if decoded:
                        log_deque.append(decoded)
            except Exception:
                pass
        threading.Thread(target=_read_output, daemon=True).start()

        _processes[service_id] = proc

    db = get_db()
    try:
        db.execute('UPDATE services SET running = 1, pid = ? WHERE id = ?', (proc.pid, service_id))
        db.commit()
    except Exception as e:
        log.error(f'Failed to update DB for {service_id}: {e}')
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        if proc.stdout:
            try:
                proc.stdout.close()
            except Exception:
                pass
        with _lock:
            _processes.pop(service_id, None)
        raise
    finally:
        db.close()

    _start_times[service_id] = time.time()
    log_activity('service_started', service_id, f'PID {proc.pid}')
    return proc.pid


def stop_process(service_id: str) -> bool:
    """Stop a tracked process."""
    with _lock:
        proc = _processes.get(service_id)
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            log.warning(f'{service_id} did not terminate within 10s, sending SIGKILL')
            proc.kill()
    # Explicitly close the captured stdout PIPE so the reader thread's FD is
    # released — avoids briefly leaked file descriptors on rapid stop/start.
    if proc and proc.stdout:
        try:
            proc.stdout.close()
        except Exception:
            pass

    # Also try by PID from DB — but only if we didn't already stop a tracked process
    db = get_db()
    try:
        row = db.execute('SELECT pid FROM services WHERE id = ?', (service_id,)).fetchone()
        if row and row['pid'] and not proc:
            # Only kill DB-tracked PID if we didn't already have a tracked process,
            # to avoid killing a recycled PID. Use kill_pid() so Windows uses
            # taskkill instead of os.kill() (SIGTERM is not supported on Windows).
            from platform_utils import pid_alive, kill_pid
            if pid_alive(row['pid']):
                try:
                    kill_pid(row['pid'])
                except Exception as e:
                    log.debug('kill_pid(%s) failed: %s', row['pid'], e)

        db.execute('UPDATE services SET running = 0, pid = NULL WHERE id = ?', (service_id,))
        db.commit()
    finally:
        db.close()

    with _lock:
        _processes.pop(service_id, None)
    _start_times.pop(service_id, None)
    log_activity('service_stopped', service_id)
    return True


def is_running(service_id: str) -> bool:
    """Check if a service process is alive.

    When falling back to the DB-stored PID, also verify the PID still maps to a
    process whose executable matches the service's recorded `exe_path`. This
    avoids false positives after a crash when the OS recycles the PID to an
    unrelated process.
    """
    with _lock:
        proc = _processes.get(service_id)
        if proc and proc.poll() is None:
            return True

    db = get_db()
    try:
        row = db.execute('SELECT pid, exe_path FROM services WHERE id = ?', (service_id,)).fetchone()
    finally:
        db.close()

    if row and row['pid']:
        if _pid_alive(row['pid']) and _pid_matches_exe(row['pid'], row['exe_path']):
            # Re-register the process so we track it going forward
            return True

    return False


def _pid_alive(pid: int) -> bool:
    """Check if a process with the given PID is alive (cross-platform)."""
    from platform_utils import pid_alive
    return pid_alive(pid)


def _pid_matches_exe(pid: int, exe_path: str) -> bool:
    """Verify the PID's process executable matches the expected service exe.

    Returns True if we can't positively disprove the match (psutil unavailable,
    permission denied, or no exe_path recorded) — the caller has already
    confirmed the PID is alive via `_pid_alive`, so this is a second-line
    sanity check against recycled PIDs, not a hard gate.
    """
    if not exe_path:
        return True
    try:
        import psutil
    except ImportError:
        return True
    try:
        proc = psutil.Process(pid)
        proc_exe = (proc.exe() or '').lower()
        expected = os.path.basename(exe_path).lower()
        if not expected:
            return True
        # Match by basename — full paths may differ after install-dir moves.
        return os.path.basename(proc_exe) == expected
    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        return False
    except (psutil.AccessDenied, OSError):
        # Can't introspect — don't second-guess _pid_alive's positive result.
        return True


# ─── Auto-Restart ──────────────────────────────────────────────────────

def should_restart(service_id: str) -> bool:
    """Check if a service should be auto-restarted (rate-limited).

    NOTE: prefer `try_reserve_restart()` over the check-then-act pattern of
    calling this followed by `record_restart()`. Two concurrent callers can
    both pass this check before either records — defeating the cap.
    """
    with _lock:
        now = time.time()
        timestamps = _restart_tracker.get(service_id, [])
        # Prune old timestamps outside the window
        timestamps = [t for t in timestamps if now - t < RESTART_WINDOW]
        _restart_tracker[service_id] = timestamps
        if len(timestamps) >= MAX_RESTARTS:
            return False
        return True


def record_restart(service_id: str):
    """Record a restart attempt."""
    with _lock:
        if service_id not in _restart_tracker:
            _restart_tracker[service_id] = []
        _restart_tracker[service_id].append(time.time())


def try_reserve_restart(service_id: str) -> bool:
    """Atomic check-and-record: returns True if a restart slot was reserved.

    Combines `should_restart` + `record_restart` under a single lock so two
    crashes arriving within the restart-monitor tick cannot both slip past
    the MAX_RESTARTS cap. Callers that use this do NOT need to call
    `record_restart` afterwards.
    """
    with _lock:
        now = time.time()
        timestamps = [t for t in _restart_tracker.get(service_id, []) if now - t < RESTART_WINDOW]
        if len(timestamps) >= MAX_RESTARTS:
            _restart_tracker[service_id] = timestamps
            return False
        timestamps.append(now)
        _restart_tracker[service_id] = timestamps
        return True


# ─── Dependency Management ─────────────────────────────────────────────

def ensure_dependencies(service_id: str, service_modules: dict) -> list[str]:
    """Start any dependencies that aren't running. Returns list of started services."""
    started = []
    deps = DEPENDENCIES.get(service_id, [])
    for dep_id in deps:
        mod = service_modules.get(dep_id)
        if mod and mod.is_installed() and not mod.running():
            try:
                log.info(f'Auto-starting dependency {dep_id} for {service_id}')
                mod.start()
                started.append(dep_id)
                log_activity('dependency_started', dep_id, f'Required by {service_id}')
            except Exception as e:
                log.error(f'Failed to start dependency {dep_id}: {e}')
    return started


def get_shutdown_order() -> list[str]:
    """Get ordered list of services for graceful shutdown (dependents first)."""
    # Simple topological sort: services with dependents shut down last
    order = []
    remaining = set(DEPENDENCIES.keys())

    while remaining:
        # Find services that no remaining service depends on
        batch = []
        for sid in remaining:
            deps_of_others = set()
            for other_id in remaining:
                if other_id != sid:
                    deps_of_others.update(DEPENDENCIES.get(other_id, []))
            if sid not in deps_of_others:
                batch.append(sid)

        if not batch:
            # Circular dependency or all remaining — just add them
            batch = list(remaining)

        order.extend(batch)
        remaining -= set(batch)

    return order


# ─── Resource Monitoring ──────────────────────────────────────────


def get_service_resources(service_id):
    """Get CPU and memory usage for a running service."""
    try:
        import psutil
    except ImportError:
        return {}
    with _lock:
        entry = _processes.get(service_id)
    if not entry:
        return None
    pid = entry.pid if hasattr(entry, 'pid') else None
    if not pid:
        return None
    try:
        proc = psutil.Process(pid)
        mem = proc.memory_info()
        return {
            'pid': pid,
            'cpu_percent': proc.cpu_percent(interval=0.1),
            'memory_mb': round(mem.rss / (1024 * 1024), 1),
            'memory_rss': mem.rss,
            'num_threads': proc.num_threads(),
        }
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def warn_dependents(service_id):
    """Return list of running services that depend on this service."""
    deps = DEPENDENTS.get(service_id, [])
    affected = []
    for dep_id in deps:
        if is_running(dep_id):
            affected.append(dep_id)
    return affected


# ─── Utilities ─────────────────────────────────────────────────────────

def register_process(service_id: str, proc: subprocess.Popen):
    """Thread-safe registration of a process started by individual service modules."""
    with _lock:
        _processes[service_id] = proc
    _start_times.setdefault(service_id, time.time())


def unregister_process(service_id: str):
    """Thread-safe removal of a process entry."""
    with _lock:
        _processes.pop(service_id, None)


def get_download_progress(service_id: str) -> dict:
    with _dl_progress_lock:
        return _download_progress.get(service_id, {
            'percent': 0, 'status': 'idle', 'error': None,
            'speed': '', 'downloaded': 0, 'total': 0,
        })


def prune_completed_downloads(max_age: float = 3600):
    """Remove download progress entries that completed/errored more than max_age seconds ago."""
    now = time.time()
    with _dl_progress_lock:
        stale = [
            k for k, v in _download_progress.items()
            if v.get('status') in ('complete', 'error')
            and v.get('_finished_at', 0) and now - v['_finished_at'] > max_age
        ]
        for k in stale:
            _download_progress.pop(k, None)


def get_service_uptime(service_id: str) -> float | None:
    """Return seconds since service was started, or None if not running."""
    started = _start_times.get(service_id)
    if started is None:
        return None
    return time.time() - started


def get_service_logs(service_id: str) -> list[str]:
    """Return a snapshot of captured stdout/stderr lines for a service."""
    with _svc_logs_lock:
        return list(_service_logs.get(service_id, []))


def check_port(port: int) -> bool:
    """Check if a port is responding."""
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=2):
            return True
    except (ConnectionRefusedError, OSError, socket.timeout):
        return False


def wait_for_port(port: int, timeout: float = 30, interval: float = 1.0) -> bool:
    """Block until a port is accepting connections, or timeout.

    Returns True if port became available, False if timed out.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if check_port(port):
            return True
        time.sleep(interval)
    return False


# Service health endpoint templates — {port} is replaced at runtime
# so health checks follow any port changes in service modules.
SERVICE_HEALTH_URLS = _SERVICE_HEALTH_TEMPLATES = {
    'ollama': ('http://127.0.0.1:{port}/api/tags', 200),
    'kiwix': ('http://127.0.0.1:{port}/', 200),
    'qdrant': ('http://127.0.0.1:{port}/healthz', 200),
    'stirling': ('http://127.0.0.1:{port}/', 200),
    'cyberchef': ('http://127.0.0.1:{port}/', 200),
}

# Default ports — overridden by service module constants when available
_DEFAULT_SERVICE_PORTS = {
    'ollama': 11434,
    'kiwix': 8888,
    'qdrant': 6333,
    'stirling': 8443,
    'cyberchef': 8889,
}


def _get_service_port(service_id: str) -> int:
    """Return the configured port for a service, falling back to default."""
    try:
        if service_id == 'ollama':
            from services.ollama import OLLAMA_PORT
            return OLLAMA_PORT
        elif service_id == 'kiwix':
            from services.kiwix import KIWIX_PORT
            return KIWIX_PORT
        elif service_id == 'qdrant':
            from services.qdrant import QDRANT_PORT
            return QDRANT_PORT
        elif service_id == 'stirling':
            from services.stirling import STIRLING_PORT
            return STIRLING_PORT
        elif service_id == 'cyberchef':
            from services.cyberchef import CYBERCHEF_PORT
            return CYBERCHEF_PORT
    except (ImportError, AttributeError):
        pass
    return _DEFAULT_SERVICE_PORTS.get(service_id, 0)


def is_healthy(service_id: str, timeout: float = 3.0) -> bool:
    """Check if a service is alive AND responding on its HTTP endpoint."""
    if not is_running(service_id):
        return False
    template = _SERVICE_HEALTH_TEMPLATES.get(service_id)
    if not template:
        return True  # No health endpoint defined — PID check is all we can do
    url_template, expected_status = template
    port = _get_service_port(service_id)
    if not port:
        return True
    url = url_template.format(port=port)
    health = (url, expected_status)
    try:
        resp = requests.get(url, timeout=timeout)
        return resp.status_code == expected_status
    except Exception:
        return False


def get_dir_size(path: str) -> int:
    """Get total size of a directory in bytes."""
    total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
    except OSError:
        pass
    return total


def format_size(size_bytes: int) -> str:
    """Format bytes into human-readable string."""
    if size_bytes >= 1024 ** 3:
        return f'{size_bytes / (1024 ** 3):.1f} GB'
    elif size_bytes >= 1024 ** 2:
        return f'{size_bytes / (1024 ** 2):.1f} MB'
    elif size_bytes >= 1024:
        return f'{size_bytes / 1024:.0f} KB'
    return f'{size_bytes} B'


def uninstall_service(service_id: str) -> bool:
    """Uninstall a service by removing its files and DB entry."""
    stop_process(service_id)

    install_dir = os.path.join(get_services_dir(), service_id)
    if os.path.isdir(install_dir):
        shutil.rmtree(install_dir, ignore_errors=True)

    db = get_db()
    try:
        db.execute('DELETE FROM services WHERE id = ?', (service_id,))
        db.commit()
    finally:
        db.close()
        # Always clean up tracking state, even if DB delete failed
        with _dl_progress_lock:
            _download_progress.pop(service_id, None)
        with _lock:
            _restart_tracker.pop(service_id, None)
        with _svc_logs_lock:
            _service_logs.pop(service_id, None)

    log_activity('service_uninstalled', service_id)
    log.info(f'Uninstalled {service_id}')
    return True
