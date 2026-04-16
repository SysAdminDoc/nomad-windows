"""Cross-platform utilities — abstracts Windows/Linux/macOS differences.

This module has ZERO internal project imports to avoid circular dependencies.
"""

from __future__ import annotations

import os
import sys
import subprocess
import logging
import platform as _platform

log = logging.getLogger('nomad.platform')

IS_WINDOWS = sys.platform == 'win32'
IS_MACOS = sys.platform == 'darwin'
IS_LINUX = sys.platform.startswith('linux')

# ─── Subprocess Helpers ──────────────────────────────────────────────

# Windows needs CREATE_NO_WINDOW to hide console windows; other platforms ignore it
_CREATION_FLAGS = 0x08000000 if IS_WINDOWS else 0


def popen_kwargs(**extra) -> dict:
    """Return platform-appropriate kwargs for subprocess.Popen.

    Usage: proc = subprocess.Popen(cmd, **popen_kwargs(cwd=dir, env=env))
    """
    kwargs = {
        'stdout': subprocess.DEVNULL,
        'stderr': subprocess.DEVNULL,
    }
    if IS_WINDOWS:
        kwargs['creationflags'] = _CREATION_FLAGS
    kwargs.update(extra)
    return kwargs


def run_kwargs(**extra) -> dict:
    """Return platform-appropriate kwargs for subprocess.run.

    Usage: result = subprocess.run(cmd, **run_kwargs(capture_output=True, text=True, timeout=5))
    """
    kwargs = {}
    if IS_WINDOWS:
        kwargs['creationflags'] = _CREATION_FLAGS
    kwargs.update(extra)
    return kwargs


# ─── Executable Names ────────────────────────────────────────────────

def exe_name(base: str) -> str:
    """Return platform-appropriate executable name: 'foo' -> 'foo.exe' on Windows."""
    if IS_WINDOWS:
        return base + '.exe'
    return base


def java_binary() -> str:
    """Return the expected java binary name."""
    return exe_name('java')


def python_binary() -> str:
    """Return the expected python binary name."""
    if IS_WINDOWS:
        return 'python.exe'
    return 'python3'


# ─── File/Folder Opening ─────────────────────────────────────────────

def find_system_python() -> str | None:
    """Find a system Python 3 executable (for venv creation in frozen apps)."""
    import shutil
    for name in ('python3', 'python'):
        path = shutil.which(name)
        if path:
            try:
                result = subprocess.run([path, '--version'], **run_kwargs(capture_output=True, text=True, timeout=5))
                if result.returncode == 0 and 'Python 3' in result.stdout:
                    return path
            except Exception:
                continue
    return None


def open_folder(path: str):
    """Open a folder in the platform's file manager."""
    if IS_WINDOWS:
        os.startfile(path)
    elif IS_MACOS:
        proc = subprocess.Popen(['open', path])
        proc.wait()
    else:
        proc = subprocess.Popen(['xdg-open', path])
        proc.wait()


# ─── Process Management ──────────────────────────────────────────────

def pid_alive(pid: int) -> bool:
    """Check if a process with the given PID is alive (cross-platform)."""
    if IS_WINDOWS:
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if handle:
                try:
                    exit_code = ctypes.c_ulong()
                    if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                        return exit_code.value == STILL_ACTIVE
                    return True  # couldn't query exit code, assume alive
                finally:
                    kernel32.CloseHandle(handle)
            return False
        except Exception:
            return False
    # Unix fallback
    try:
        os.kill(pid, 0)
        # Check for zombie processes on Linux
        if IS_LINUX:
            try:
                with open(f'/proc/{pid}/status', 'r') as f:
                    for line in f:
                        if line.startswith('State:'):
                            if 'Z' in line.split(':')[1]:
                                return False  # zombie process
                            break
            except (OSError, IOError):
                pass
        return True
    except (OSError, ProcessLookupError):
        return False


def find_pid_on_port(port: int) -> int | None:
    """Find the PID of the process listening on a given port."""
    if IS_WINDOWS:
        try:
            result = subprocess.run(
                ['powershell', '-NoProfile', '-Command',
                 f"(Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess"],
                **run_kwargs(capture_output=True, text=True, timeout=5)
            )
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip())
        except Exception:
            pass
    else:
        try:
            result = subprocess.run(
                ['lsof', '-ti', f':{port}'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                # lsof may return multiple PIDs; take the first
                return int(result.stdout.strip().split('\n')[0])
        except Exception:
            # Try ss as fallback (common on minimal Linux installs)
            try:
                result = subprocess.run(
                    ['ss', '-tlnp', f'sport = :{port}'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    import re
                    m = re.search(r'pid=(\d+)', result.stdout)
                    if m:
                        return int(m.group(1))
            except Exception:
                pass
    return None


def kill_pid(pid: int):
    """Force-kill a process by PID."""
    if IS_WINDOWS:
        try:
            subprocess.run(
                ['taskkill', '/F', '/PID', str(pid)],
                **run_kwargs(capture_output=True, timeout=5)
            )
        except Exception as e:
            log.warning(f'taskkill failed for PID {pid}: {e}')
    else:
        import signal
        import time as _time
        try:
            os.kill(pid, signal.SIGTERM)
            # Give process 3 seconds to exit gracefully, then SIGKILL
            for _ in range(6):
                _time.sleep(0.5)
                try:
                    os.kill(pid, 0)  # check if still alive
                except OSError:
                    return  # process exited
            os.kill(pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass


# ─── GPU Detection ───────────────────────────────────────────────────

def detect_gpu() -> dict:
    """Detect GPU type and capabilities (cross-platform)."""
    info = {'type': 'cpu', 'name': 'None', 'vram_mb': 0, 'cuda': False, 'rocm': False}

    # Try NVIDIA first (nvidia-smi works on all platforms)
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader,nounits'],
            **run_kwargs(capture_output=True, text=True, timeout=5)
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(', ')
            info['type'] = 'nvidia'
            info['name'] = parts[0]
            info['vram_mb'] = int(parts[1]) if len(parts) > 1 else 0
            info['cuda'] = True
            if len(parts) > 2:
                info['driver_version'] = parts[2]
            log.info(f'GPU detected: NVIDIA {info["name"]} ({info["vram_mb"]}MB VRAM)')
            return info
    except Exception:
        pass

    if IS_WINDOWS:
        # Try AMD/Intel via WMI (Windows only)
        for pattern, gpu_type, flag in [
            ("*AMD*\" -or $_.Name -like \"*Radeon*", 'amd', 'rocm'),
            ("*Intel*Arc*", 'intel', None),
        ]:
            try:
                result = subprocess.run(
                    ['powershell', '-NoProfile', '-Command',
                     f'Get-WmiObject Win32_VideoController | Where-Object {{$_.Name -like "{pattern}"}} | Select-Object -First 1 -ExpandProperty Name'],
                    **run_kwargs(capture_output=True, text=True, timeout=5)
                )
                if result.returncode == 0 and result.stdout.strip():
                    info['type'] = gpu_type
                    info['name'] = result.stdout.strip()
                    if flag:
                        info[flag] = True
                    return info
            except Exception:
                pass
        # Fallback: any GPU via WMI
        try:
            result = subprocess.run(
                ['powershell', '-NoProfile', '-Command',
                 "Get-WmiObject Win32_VideoController | Select-Object -First 1 -ExpandProperty Name"],
                **run_kwargs(capture_output=True, text=True, timeout=5)
            )
            if result.returncode == 0 and result.stdout.strip():
                info['name'] = result.stdout.strip()
        except Exception:
            pass
    else:
        # Linux: try lspci for AMD/Intel
        try:
            result = subprocess.run(
                ['lspci'], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                # Prefer discrete GPU over integrated — scan all VGA/3D/display entries
                best_gpu = None
                for line in result.stdout.splitlines():
                    ll = line.lower()
                    if 'vga' in ll or '3d' in ll or 'display' in ll:
                        gpu_name = line.split(': ', 1)[-1] if ': ' in line else line
                        if 'amd' in ll or 'radeon' in ll:
                            best_gpu = {'type': 'amd', 'name': gpu_name, 'rocm': True}
                        elif 'intel' in ll and 'arc' in ll:
                            best_gpu = {'type': 'intel', 'name': gpu_name}
                        elif best_gpu is None:
                            best_gpu = {'type': info['type'], 'name': gpu_name}
                if best_gpu:
                    info['type'] = best_gpu.get('type', info['type'])
                    info['name'] = best_gpu['name']
                    if best_gpu.get('rocm'):
                        info['rocm'] = True
        except Exception:
            pass

    return info


def get_ollama_gpu_env() -> dict:
    """Get environment variables for Ollama based on detected GPU."""
    env = os.environ.copy()
    gpu = detect_gpu()
    if gpu['type'] == 'nvidia' and gpu['cuda']:
        env.pop('CUDA_VISIBLE_DEVICES', None)
        log.info('Ollama GPU config: NVIDIA CUDA')
    elif gpu['type'] == 'amd' and gpu['rocm']:
        env['HSA_OVERRIDE_GFX_VERSION'] = '11.0.0'
        log.info('Ollama GPU config: AMD ROCm')
    else:
        log.info('Ollama GPU config: CPU only')
    return env


# ─── Download URLs ───────────────────────────────────────────────────

def _arch() -> str:
    """Return 'arm64' or 'amd64' based on machine architecture."""
    m = _platform.machine().lower()
    if m in ('aarch64', 'arm64'):
        return 'arm64'
    return 'amd64'


def get_ollama_url() -> str:
    arch = _arch()
    if IS_MACOS:
        return 'https://github.com/ollama/ollama/releases/latest/download/ollama-darwin.tgz'
    elif IS_LINUX:
        return f'https://github.com/ollama/ollama/releases/latest/download/ollama-linux-{arch}.tgz'
    return 'https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip'


def get_kiwix_url() -> str:
    arch = 'aarch64' if _arch() == 'arm64' else 'x86_64'
    if IS_MACOS:
        return f'https://download.kiwix.org/release/kiwix-tools/kiwix-tools_macos-{arch}-3.8.1.tar.gz'
    elif IS_LINUX:
        return f'https://download.kiwix.org/release/kiwix-tools/kiwix-tools_linux-{arch}-3.8.1.tar.gz'
    return f'https://download.kiwix.org/release/kiwix-tools/kiwix-tools_win-{arch}-3.8.1.zip'


def get_adoptium_jre_url() -> str:
    arch = 'aarch64' if _arch() == 'arm64' else 'x64'
    if IS_MACOS:
        return f'https://api.adoptium.net/v3/binary/latest/21/ga/mac/{arch}/jre/hotspot/normal/eclipse'
    elif IS_LINUX:
        return f'https://api.adoptium.net/v3/binary/latest/21/ga/linux/{arch}/jre/hotspot/normal/eclipse'
    win_arch = 'aarch64' if _arch() == 'arm64' else 'x64'
    return f'https://api.adoptium.net/v3/binary/latest/21/ga/windows/{win_arch}/jre/hotspot/normal/eclipse'


def get_python_embed_url() -> str | None:
    """Python embeddable package — only available on Windows."""
    if IS_WINDOWS:
        win_arch = 'arm64' if _arch() == 'arm64' else 'amd64'
        return f'https://www.python.org/ftp/python/3.12.8/python-3.12.8-embed-{win_arch}.zip'
    return None  # Linux/macOS use system Python


def get_qdrant_asset_filter() -> str:
    """Return the keyword to match in Qdrant GitHub release asset names (arch-aware)."""
    arch = 'aarch64' if _arch() == 'arm64' else 'x86_64'
    if IS_MACOS:
        return f'{arch}-apple'
    elif IS_LINUX:
        return f'{arch}-unknown-linux'
    return 'windows'


# ─── System Power Commands ──────────────────────────────────────────

def system_shutdown():
    if IS_WINDOWS:
        os.system('shutdown /s /t 5 /c "NOMAD initiated shutdown"')
    elif IS_MACOS:
        os.system('sudo shutdown -h +1')
    else:
        os.system('sudo shutdown -h now')


def system_reboot():
    if IS_WINDOWS:
        os.system('shutdown /r /t 5 /c "NOMAD initiated reboot"')
    elif IS_MACOS:
        os.system('sudo shutdown -r +1')
    else:
        os.system('sudo shutdown -r now')


# ─── Config/Data Paths ──────────────────────────────────────────────

def get_config_base() -> str:
    """Platform-appropriate config directory base."""
    if IS_WINDOWS:
        return os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
    elif IS_MACOS:
        return os.path.join(os.path.expanduser('~'), 'Library', 'Application Support')
    else:
        return os.environ.get('XDG_CONFIG_HOME', os.path.join(os.path.expanduser('~'), '.config'))


def get_data_base() -> str:
    """Platform-appropriate data directory base."""
    if IS_WINDOWS:
        return os.environ.get('APPDATA', os.path.expanduser('~'))
    elif IS_MACOS:
        return os.path.join(os.path.expanduser('~'), 'Library', 'Application Support')
    else:
        return os.environ.get('XDG_DATA_HOME', os.path.join(os.path.expanduser('~'), '.local', 'share'))


# ─── Archive Extraction ────────────────────────────────────────────

def _safe_zip_extract(zf, dest_dir: str):
    """Extract zip with Zip Slip protection — reject entries that escape dest_dir."""
    dest = os.path.realpath(dest_dir)
    for member in zf.infolist():
        member_path = os.path.realpath(os.path.join(dest, member.filename))
        if not member_path.startswith(dest + os.sep) and member_path != dest:
            raise ValueError(f'Zip Slip detected: {member.filename} escapes {dest_dir}')
    zf.extractall(dest_dir)


def _safe_tar_extract(tf, dest_dir: str):
    """Extract tar with path traversal protection — reject entries that escape dest_dir."""
    dest = os.path.realpath(dest_dir)
    safe_members = []
    for member in tf.getmembers():
        member_path = os.path.realpath(os.path.join(dest, member.name))
        if not member_path.startswith(dest + os.sep) and member_path != dest:
            raise ValueError(f'Path traversal detected: {member.name} escapes {dest_dir}')
        if member.issym() or member.islnk():
            link_target = os.path.realpath(os.path.join(dest, os.path.dirname(member.name), member.linkname))
            if not link_target.startswith(dest + os.sep) and link_target != dest:
                raise ValueError(f'Symlink traversal detected: {member.name} -> {member.linkname}')
        safe_members.append(member)
    tf.extractall(dest_dir, members=safe_members)


def extract_archive(archive_path: str, dest_dir: str):
    """Extract a .zip, .tar.gz, .tar.xz, or .tar.bz2 archive with path traversal protection."""
    if archive_path.endswith('.zip'):
        import zipfile
        with zipfile.ZipFile(archive_path, 'r') as zf:
            _safe_zip_extract(zf, dest_dir)
            # zipfile does not preserve Unix permissions — fix execute bits
            if not IS_WINDOWS:
                for info in zf.infolist():
                    extracted = os.path.join(dest_dir, info.filename)
                    if not info.is_dir() and os.path.isfile(extracted):
                        unix_mode = info.external_attr >> 16
                        if unix_mode:
                            try:
                                os.chmod(extracted, unix_mode)
                            except OSError:
                                pass
    elif archive_path.endswith(('.tar.gz', '.tgz', '.tar.xz', '.tar.bz2')):
        import tarfile
        if archive_path.endswith('.tar.xz'):
            mode = 'r:xz'
        elif archive_path.endswith('.tar.bz2'):
            mode = 'r:bz2'
        else:
            mode = 'r:gz'
        with tarfile.open(archive_path, mode) as tf:
            _safe_tar_extract(tf, dest_dir)
    else:
        raise ValueError(f'Unknown archive format: {archive_path}')
    try:
        os.remove(archive_path)
    except OSError as e:
        log.warning(f'Could not remove archive after extraction: {e}')


def install_binary(src_path: str, dest_path: str):
    """Move a downloaded binary to its destination and make it executable."""
    import shutil
    shutil.move(src_path, dest_path)
    if not IS_WINDOWS:
        os.chmod(dest_path, 0o755)


def make_executable(path: str):
    """Ensure a file has execute permissions (no-op on Windows)."""
    if not IS_WINDOWS and os.path.isfile(path):
        os.chmod(path, 0o755)


# ─── WebView GUI Backend ────────────────────────────────────────────

def get_webview_gui() -> str | None:
    """Return the appropriate pywebview GUI backend for this platform."""
    if IS_WINDOWS:
        return 'edgechromium'
    # macOS and Linux: let pywebview auto-detect (uses WebKit on macOS, GTK/Qt on Linux)
    return None


# ─── USB Portable Mode Detection ─────────────────────────────────────

def is_portable_mode() -> bool:
    """Detect if running from a removable/USB drive (portable mode).

    Checks:
    1. Presence of 'portable.marker' file next to the executable/script
    2. Whether the drive is removable (Windows) or mounted under /media (Linux)
    """
    # Resolve symlinks so that a symlink from /media/... to a local path
    # doesn't falsely trigger removable-drive detection.
    app_dir = os.path.dirname(os.path.realpath(sys.argv[0] if sys.argv[0] else __file__))

    # Explicit marker file — most reliable method
    if os.path.isfile(os.path.join(app_dir, 'portable.marker')):
        return True
    if os.path.isfile(os.path.join(app_dir, 'PORTABLE')):
        return True
    if os.path.isfile(os.path.join(app_dir, 'portable.txt')):
        log.info('Portable mode: using local data directory')
        return True

    if IS_WINDOWS:
        try:
            import ctypes
            drive = os.path.splitdrive(app_dir)[0] + '\\'
            DRIVE_REMOVABLE = 2
            return ctypes.windll.kernel32.GetDriveTypeW(drive) == DRIVE_REMOVABLE
        except Exception:
            return False
    elif IS_LINUX:
        return '/media/' in app_dir or '/mnt/usb' in app_dir
    elif IS_MACOS:
        return '/Volumes/' in app_dir and app_dir.count('/') >= 2
    return False


def get_portable_data_dir() -> str:
    """Get data directory for portable mode — same directory as the app."""
    app_dir = os.path.dirname(os.path.realpath(sys.argv[0] if sys.argv[0] else __file__))
    data_dir = os.path.join(app_dir, 'nomad_data')
    os.makedirs(data_dir, exist_ok=True)
    return data_dir
