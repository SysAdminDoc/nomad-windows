"""
Native Windows process manager for N.O.M.A.D. services.
Downloads, installs, starts, and stops services as native processes.
Includes dependency graph, auto-restart, download resume, GPU detection.
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
from db import get_db, log_activity
from config import get_data_dir

log = logging.getLogger('nomad.manager')

# Track running processes
_processes: dict[str, subprocess.Popen] = {}
_download_progress: dict[str, dict] = {}

# Service dependency graph: service -> list of services it requires
DEPENDENCIES = {
    'qdrant': [],
    'ollama': [],
    'kiwix': [],
    'cyberchef': [],
    'kolibri': [],
    'stirling': [],
}

# Reverse: which services depend on this one (for ordered shutdown)
DEPENDENTS = {
    'ollama': ['qdrant'],  # If ollama stops, qdrant's embeddings won't work but it can stay up
    'qdrant': [],
}

# Restart policy: max restart attempts within a window
MAX_RESTARTS = 3
RESTART_WINDOW = 300  # seconds
_restart_tracker: dict[str, list[float]] = {}  # service_id -> list of restart timestamps


def get_services_dir():
    svc_dir = os.path.join(get_data_dir(), 'services')
    os.makedirs(svc_dir, exist_ok=True)
    return svc_dir


# ─── GPU Detection ────────────────────────────────────────────────────

_gpu_info = None


def detect_gpu() -> dict:
    """Detect GPU type and capabilities for Ollama configuration."""
    global _gpu_info
    if _gpu_info is not None:
        return _gpu_info

    info = {'type': 'cpu', 'name': 'None', 'vram_mb': 0, 'cuda': False, 'rocm': False}

    # Try NVIDIA first
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5, creationflags=0x08000000,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(', ')
            info['type'] = 'nvidia'
            info['name'] = parts[0]
            info['vram_mb'] = int(parts[1]) if len(parts) > 1 else 0
            info['cuda'] = True
            if len(parts) > 2:
                info['driver_version'] = parts[2]
            _gpu_info = info
            log.info(f'GPU detected: NVIDIA {info["name"]} ({info["vram_mb"]}MB VRAM)')
            return info
    except Exception:
        pass

    # Try AMD
    try:
        # Check for AMD via WMI
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             "Get-WmiObject Win32_VideoController | Where-Object {$_.Name -like '*AMD*' -or $_.Name -like '*Radeon*'} | Select-Object -First 1 -ExpandProperty Name"],
            capture_output=True, text=True, timeout=5, creationflags=0x08000000,
        )
        if result.returncode == 0 and result.stdout.strip():
            info['type'] = 'amd'
            info['name'] = result.stdout.strip()
            info['rocm'] = True
            _gpu_info = info
            log.info(f'GPU detected: AMD {info["name"]}')
            return info
    except Exception:
        pass

    # Try Intel Arc
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             "Get-WmiObject Win32_VideoController | Where-Object {$_.Name -like '*Intel*Arc*'} | Select-Object -First 1 -ExpandProperty Name"],
            capture_output=True, text=True, timeout=5, creationflags=0x08000000,
        )
        if result.returncode == 0 and result.stdout.strip():
            info['type'] = 'intel'
            info['name'] = result.stdout.strip()
            _gpu_info = info
            log.info(f'GPU detected: Intel {info["name"]}')
            return info
    except Exception:
        pass

    # Fallback: any GPU
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             "Get-WmiObject Win32_VideoController | Select-Object -First 1 -ExpandProperty Name"],
            capture_output=True, text=True, timeout=5, creationflags=0x08000000,
        )
        if result.returncode == 0 and result.stdout.strip():
            info['name'] = result.stdout.strip()
    except Exception:
        pass

    _gpu_info = info
    return info


def get_ollama_gpu_env() -> dict:
    """Get environment variables for Ollama based on detected GPU."""
    env = os.environ.copy()
    gpu = detect_gpu()

    if gpu['type'] == 'nvidia' and gpu['cuda']:
        # NVIDIA CUDA — Ollama uses this by default, just ensure no blockers
        env.pop('CUDA_VISIBLE_DEVICES', None)  # Don't restrict
        log.info('Ollama GPU config: NVIDIA CUDA')
    elif gpu['type'] == 'amd' and gpu['rocm']:
        env['HSA_OVERRIDE_GFX_VERSION'] = '11.0.0'  # Common ROCm compatibility
        log.info('Ollama GPU config: AMD ROCm')
    else:
        # CPU only
        log.info('Ollama GPU config: CPU only')

    return env


# ─── Download with Resume ─────────────────────────────────────────────

def download_file(url: str, dest: str, service_id: str = '') -> str:
    """Download a file with progress tracking, speed display, and resume support."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    # Check for partial download
    partial_size = 0
    if os.path.isfile(dest):
        partial_size = os.path.getsize(dest)

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

        # If server doesn't support resume (no 206), start fresh
        if partial_size > 0 and resp.status_code != 206:
            partial_size = 0

        if resp.status_code == 416:
            # Range not satisfiable — file already complete
            _download_progress[service_id] = {
                'percent': 100, 'status': 'complete', 'error': None,
                'speed': '', 'downloaded': partial_size, 'total': partial_size,
            }
            return dest

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

                _download_progress[service_id].update({
                    'percent': int(downloaded / total * 100) if total > 0 else 0,
                    'speed': speed_str,
                    'downloaded': downloaded,
                    'total': total,
                })

        _download_progress[service_id] = {
            'percent': 100, 'status': 'complete', 'error': None,
            'speed': '', 'downloaded': total, 'total': total,
        }
        return dest
    except Exception as e:
        _download_progress[service_id] = {
            'percent': 0, 'status': 'error', 'error': str(e),
            'speed': '', 'downloaded': 0, 'total': 0,
        }
        raise


def extract_zip(zip_path: str, dest_dir: str):
    """Extract a zip file."""
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(dest_dir)
    os.remove(zip_path)


# ─── Process Management ────────────────────────────────────────────────

def start_process(service_id: str, exe_path: str, args: list[str] = None,
                  cwd: str = None, port: int = None, env: dict = None) -> int:
    """Start a native process and track it."""
    if service_id in _processes and _processes[service_id].poll() is None:
        return _processes[service_id].pid

    cmd = [exe_path] + (args or [])
    log.info(f'Starting {service_id}: {" ".join(cmd)}')

    CREATE_NO_WINDOW = 0x08000000
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW,
    )
    _processes[service_id] = proc

    db = get_db()
    db.execute('UPDATE services SET running = 1, pid = ? WHERE id = ?', (proc.pid, service_id))
    db.commit()
    db.close()

    log_activity('service_started', service_id, f'PID {proc.pid}')
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
    log_activity('service_stopped', service_id)
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
        if _pid_alive(row['pid']):
            return True

    return False


def _pid_alive(pid: int) -> bool:
    """Check if a process with the given PID is alive (Windows-compatible)."""
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    except Exception:
        # Fallback for non-Windows
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


# ─── Auto-Restart ──────────────────────────────────────────────────────

def should_restart(service_id: str) -> bool:
    """Check if a service should be auto-restarted (rate-limited)."""
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
    if service_id not in _restart_tracker:
        _restart_tracker[service_id] = []
    _restart_tracker[service_id].append(time.time())


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


# ─── Utilities ─────────────────────────────────────────────────────────

def get_download_progress(service_id: str) -> dict:
    return _download_progress.get(service_id, {
        'percent': 0, 'status': 'idle', 'error': None,
        'speed': '', 'downloaded': 0, 'total': 0,
    })


def check_port(port: int) -> bool:
    """Check if a port is responding."""
    import socket
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=2):
            return True
    except (ConnectionRefusedError, OSError, socket.timeout):
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
    db.execute('DELETE FROM services WHERE id = ?', (service_id,))
    db.commit()
    db.close()

    _download_progress.pop(service_id, None)
    log_activity('service_uninstalled', service_id)
    log.info(f'Uninstalled {service_id}')
    return True
