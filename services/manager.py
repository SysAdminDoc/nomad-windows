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
import hashlib
import re
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


# ─── GitHub release cache ─────────────────────────────────────────────

_release_cache_dir = None


def _get_release_cache_dir():
    global _release_cache_dir
    if _release_cache_dir is None:
        _release_cache_dir = os.path.join(get_services_dir(), '.release_cache')
        os.makedirs(_release_cache_dir, exist_ok=True)
    return _release_cache_dir


def resolve_github_release(api_url, service_id, *, request_get=None):
    """Fetch a GitHub release with cached fallback.

    On success the response payload is cached.  When the API is unreachable
    or returns an error, the most-recent cached payload is returned so that
    service installs survive transient GitHub outages.
    """
    import json as _json
    cache_path = os.path.join(_get_release_cache_dir(), f'{service_id}.json')
    getter = request_get or requests.get

    try:
        resp = getter(api_url, timeout=15, headers=GITHUB_API_HEADERS)
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, dict) and payload.get('assets'):
            try:
                with open(cache_path, 'w', encoding='utf-8') as fh:
                    _json.dump(payload, fh)
            except OSError:
                pass
        return payload
    except Exception as exc:
        log.warning('GitHub API unavailable for %s (%s), trying cache', service_id, exc)
        try:
            with open(cache_path, 'r', encoding='utf-8') as fh:
                cached = _json.load(fh)
            log.info('Using cached release metadata for %s', service_id)
            return cached
        except (OSError, ValueError):
            raise RuntimeError(
                f'GitHub API unreachable and no cached release for {service_id}'
            ) from exc


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

MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB default cap (P2-I19)
_SHA256_RE = re.compile(r'(?i)\b[a-f0-9]{64}\b')
_CHECKSUM_ASSET_HINTS = (
    'sha256',
    'sha256sum',
    'sha256sums',
    'checksums',
    'checksum',
    'shasums',
)


def _normalize_sha256(expected_sha256: str | None) -> str | None:
    if expected_sha256 is None:
        return None
    digest = str(expected_sha256).strip()
    if not digest:
        return None
    if digest.lower().startswith('sha256:'):
        digest = digest.split(':', 1)[1].strip()
    if not re.fullmatch(r'(?i)[a-f0-9]{64}', digest):
        raise ValueError('Invalid SHA256 checksum format')
    return digest.lower()


def file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file_sha256(path: str, expected_sha256: str) -> bool:
    expected = _normalize_sha256(expected_sha256)
    if expected is None:
        return True
    actual = file_sha256(path)
    if actual != expected:
        raise ValueError(
            f'SHA256 checksum mismatch for {os.path.basename(path)}: '
            f'expected {expected}, got {actual}'
        )
    return True


def _asset_basename(name: str) -> str:
    return os.path.basename(str(name or '').replace('\\', '/')).lower()


def parse_sha256_checksum_text(
    text: str,
    asset_name: str,
    *,
    allow_single_hash: bool = False,
) -> str | None:
    """Return the SHA256 digest in a checksum sidecar/manifest for asset_name."""
    target = _asset_basename(asset_name)
    fallback = None
    digest_lines = 0

    for raw_line in str(text or '').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue

        bsd = re.search(
            r'(?i)^SHA256\s*\((?P<name>[^)]+)\)\s*=\s*(?P<hash>[a-f0-9]{64})',
            line,
        )
        if bsd:
            digest_lines += 1
            digest = _normalize_sha256(bsd.group('hash'))
            if _asset_basename(bsd.group('name')) == target:
                return digest
            if fallback is None:
                fallback = digest
            continue

        hashes = _SHA256_RE.findall(line)
        if not hashes:
            continue
        digest_lines += 1
        digest = _normalize_sha256(hashes[0])

        remainder = _SHA256_RE.sub('', line).strip()
        tokens = [
            token.strip(' *\t\r\n')
            for token in re.split(r'\s+', remainder)
            if token.strip(' *\t\r\n')
        ]
        if any(_asset_basename(token) == target for token in tokens):
            return digest
        if not tokens and fallback is None:
            fallback = digest

    if allow_single_hash and digest_lines == 1:
        return fallback
    return None


def _response_text(resp) -> str:
    text = getattr(resp, 'text', None)
    if isinstance(text, str):
        return text
    content = getattr(resp, 'content', b'')
    if isinstance(content, bytes):
        return content.decode('utf-8', errors='replace')
    return str(content or '')


def _close_response(resp):
    try:
        resp.close()
    except Exception:
        pass


def _asset_download_url(asset: dict) -> str:
    return str(asset.get('browser_download_url') or asset.get('url') or '')


def _asset_digest(asset: dict, asset_name: str) -> str | None:
    if _asset_basename(asset.get('name', '')) != _asset_basename(asset_name):
        return None
    digest = asset.get('digest')
    try:
        return _normalize_sha256(digest)
    except ValueError:
        return None


def _is_checksum_asset_name(name: str) -> bool:
    lowered = str(name or '').lower()
    return any(hint in lowered for hint in _CHECKSUM_ASSET_HINTS)


def _is_sidecar_checksum_name(checksum_name: str, asset_name: str) -> bool:
    checksum_base = _asset_basename(checksum_name)
    asset_base = _asset_basename(asset_name)
    sidecars = {
        f'{asset_base}.sha256',
        f'{asset_base}.sha256sum',
        f'{asset_base}.sha256.txt',
        f'{asset_base}.digest',
    }
    return checksum_base in sidecars or (
        checksum_base.startswith(f'{asset_base}.')
        and _is_checksum_asset_name(checksum_base)
    )


def resolve_release_asset_checksum(
    assets: list[dict],
    asset_name: str,
    *,
    request_get=None,
) -> str | None:
    """Resolve a SHA256 for a selected release asset when metadata publishes one."""
    if not asset_name or not isinstance(assets, list):
        return None

    for asset in assets:
        if not isinstance(asset, dict):
            continue
        digest = _asset_digest(asset, asset_name)
        if digest:
            return digest

    candidates = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get('name', '') or '')
        url = _asset_download_url(asset)
        if not name or not url or not _is_checksum_asset_name(name):
            continue
        candidates.append((0 if _is_sidecar_checksum_name(name, asset_name) else 1, asset))

    if not candidates:
        return None

    getter = request_get or requests.get
    for score, asset in sorted(candidates, key=lambda entry: entry[0]):
        name = str(asset.get('name', '') or '')
        url = _asset_download_url(asset)
        resp = None
        try:
            resp = getter(url, timeout=15, headers=GITHUB_API_HEADERS)
            if getattr(resp, 'status_code', 200) == 404:
                continue
            resp.raise_for_status()
            digest = parse_sha256_checksum_text(
                _response_text(resp),
                asset_name,
                allow_single_hash=(score == 0),
            )
            if digest:
                return digest
            if score == 0:
                raise ValueError(
                    f'Checksum sidecar {name} did not contain a SHA256 for {asset_name}'
                )
        finally:
            if resp is not None:
                _close_response(resp)
    return None


def resolve_url_sidecar_checksum(
    url: str,
    asset_name: str | None = None,
    *,
    request_get=None,
) -> str | None:
    """Best-effort SHA256 sidecar lookup for direct binary URLs."""
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return None
    target_name = asset_name or os.path.basename(parsed.path)
    if not target_name:
        return None

    getter = request_get or requests.get
    for sidecar_url in (
        f'{url}.sha256',
        f'{url}.sha256sum',
        f'{url}.sha256.txt',
    ):
        resp = None
        try:
            resp = getter(sidecar_url, timeout=15, headers={'User-Agent': GITHUB_USER_AGENT})
            if getattr(resp, 'status_code', 200) in (403, 404):
                continue
            resp.raise_for_status()
            digest = parse_sha256_checksum_text(
                _response_text(resp),
                target_name,
                allow_single_hash=True,
            )
            if digest:
                return digest
        except Exception as exc:
            log.debug('Checksum sidecar lookup failed for %s: %s', sidecar_url, exc)
        finally:
            if resp is not None:
                _close_response(resp)
    return None


def download_file(url: str, dest: str, service_id: str = '',
                  max_bytes: int = 0,
                  expected_sha256: str | None = None) -> str:
    """Download a file with progress tracking, speed display, resume, and optional SHA256 verification."""
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        raise ValueError(f'Unsupported URL scheme: {parsed.scheme}')
    expected_sha256 = _normalize_sha256(expected_sha256)
    cap = max_bytes or MAX_DOWNLOAD_BYTES
    dest_dir = os.path.dirname(dest)
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)

    # Check for partial download
    partial_size = 0
    if os.path.isfile(dest):
        partial_size = os.path.getsize(dest)
        if expected_sha256 and partial_size > 0:
            try:
                verify_file_sha256(dest, expected_sha256)
                with _dl_progress_lock:
                    _download_progress[service_id] = {
                        'percent': 100, 'status': 'complete', 'error': None,
                        'speed': '', 'downloaded': partial_size, 'total': partial_size,
                        '_finished_at': time.time(),
                    }
                return dest
            except ValueError:
                os.remove(dest)
                partial_size = 0

    with _dl_progress_lock:
        _download_progress[service_id] = {
            'percent': 0, 'status': 'downloading', 'error': None,
            'speed': '', 'downloaded': partial_size, 'total': 0,
        }

    resp = None
    try:
        headers = {}
        if partial_size > 0:
            headers['Range'] = f'bytes={partial_size}-'
            log.info(f'Resuming download for {service_id} from {partial_size} bytes')

        # Tuple timeout: (connect, read) — a single scalar applies to the
        # INITIAL connect only when streaming. Without an explicit read
        # timeout, a TCP connection that stalls mid-body (server still
        # dribbling keepalives) would block the download worker forever,
        # leaving the UI with a stuck "Downloading…" status.
        resp = requests.get(
            url, stream=True, timeout=(30, 60), headers=headers,
        )

        if resp.status_code == 416:
            if expected_sha256:
                verify_file_sha256(dest, expected_sha256)
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
        if total > cap:
            raise ValueError(f'File too large ({total} bytes > {cap} byte limit)')
        # Fail fast when the disk clearly can't hold the remaining bytes —
        # otherwise a 2 GB service download dies halfway with a cryptic
        # OSError and leaves the user to diagnose a full disk.
        if total > partial_size:
            try:
                free = shutil.disk_usage(dest_dir or '.').free
            except OSError:
                free = None
            if free is not None and (total - partial_size) > free - 256 * 1024 * 1024:
                raise ValueError(
                    f'Insufficient disk space: need {(total - partial_size) // (1024 * 1024)} MB, '
                    f'only {free // (1024 * 1024)} MB free'
                )
        downloaded = partial_size
        start_time = time.time()

        mode = 'ab' if partial_size > 0 and resp.status_code == 206 else 'wb'
        with open(dest, mode) as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
                downloaded += len(chunk)
                if downloaded > cap:
                    raise ValueError(f'Download exceeded size limit ({cap} bytes)')
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

        if expected_sha256:
            verify_file_sha256(dest, expected_sha256)

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
        if expected_sha256 and os.path.isfile(dest):
            try:
                os.remove(dest)
            except OSError:
                pass
            log.warning(f'Download failed for {service_id}; removed unverified partial file: {e}')
        else:
            # Keep partial file for resume on next attempt
            log.warning(f'Download failed for {service_id}, partial file kept for resume: {e}')
        raise
    finally:
        if resp is not None:
            _close_response(resp)


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

    try:
        db = get_db()
    except Exception as e:
        # DB unavailable — kill and untrack the just-launched process so
        # we don't leave a running orphan that nothing knows how to stop.
        log.error(f'Failed to open DB after starting {service_id}: {e}')
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
            # Process is alive via DB-tracked PID. We can't reconstruct a
            # Popen handle from just a PID, but we CAN seed _start_times so
            # uptime calculations are valid on the next call.
            _start_times.setdefault(service_id, time.time())
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

    DEPRECATED: Use `try_reserve_restart()` instead. This function has a
    TOCTOU race — two concurrent callers can both pass the check before
    either records a restart, defeating the cap. It is kept only for
    backward compatibility with any external callers.
    """
    import warnings
    warnings.warn(
        'should_restart() has a TOCTOU race; use try_reserve_restart() instead.',
        DeprecationWarning,
        stacklevel=2,
    )
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


# Maps service_id -> (module_path, constant_name) for port resolution.
# Add new services here — no if/elif chains needed.
_SERVICE_PORT_ATTRS: dict[str, tuple[str, str]] = {
    'ollama':     ('services.ollama',    'OLLAMA_PORT'),
    'kiwix':      ('services.kiwix',     'KIWIX_PORT'),
    'qdrant':     ('services.qdrant',    'QDRANT_PORT'),
    'stirling':   ('services.stirling',  'STIRLING_PORT'),
    'cyberchef':  ('services.cyberchef', 'CYBERCHEF_PORT'),
    'flatnotes':  ('services.flatnotes', 'FLATNOTES_PORT'),
    'kolibri':    ('services.kolibri',   'KOLIBRI_PORT'),
    # 'torrent' intentionally absent — libtorrent is an embedded library,
    # not an HTTP server on a port.
}


def _get_service_port(service_id: str) -> int:
    """Return the configured port for a service, falling back to default.

    Uses lazy imports to avoid circular import cycles (each service module
    imports from manager at its own top level).
    """
    entry = _SERVICE_PORT_ATTRS.get(service_id)
    if entry:
        module_path, attr = entry
        try:
            import importlib
            mod = importlib.import_module(module_path)
            return int(getattr(mod, attr))
        except (ImportError, AttributeError, TypeError, ValueError):
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


def _rmtree_with_retry(path: str, attempts: int = 5, delay: float = 0.25) -> bool:
    """Best-effort recursive delete that survives transient Windows locks.

    On Windows, a just-stopped process can leave file handles held for a few
    hundred milliseconds after ``Popen.terminate()`` returns — antivirus
    scanners, explorer.exe thumbnail cache, and indexers compound this.
    ``shutil.rmtree(ignore_errors=True)`` swallows the error and returns
    with the directory still on disk, so the next install thinks the
    service is already present.

    Retries up to *attempts* times with exponential-ish backoff. On the
    final failure, a stubborn ``.delete-pending`` marker is left so the
    next startup can retry cleanup instead of silently succeeding.
    """
    import time as _time
    if not os.path.isdir(path):
        return True
    last_exc = None
    for attempt in range(attempts):
        try:
            shutil.rmtree(path)
            return True
        except OSError as exc:
            last_exc = exc
            _time.sleep(delay * (attempt + 1))
    # Final best-effort — ignore_errors to clean what we can.
    shutil.rmtree(path, ignore_errors=True)
    if os.path.isdir(path):
        log.warning('Could not fully remove %s after %d attempts: %s',
                    path, attempts, last_exc)
        try:
            with open(os.path.join(path, '.delete-pending'), 'w') as f:
                f.write(f'retry at next startup: {last_exc}')
        except OSError:
            pass
        return False
    return True


def uninstall_service(service_id: str) -> bool:
    """Uninstall a service by removing its files and DB entry."""
    stop_process(service_id)

    install_dir = os.path.join(get_services_dir(), service_id)
    _rmtree_with_retry(install_dir)

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
