"""Centralized configuration — data directory management and app settings.

This module has ZERO internal imports to avoid circular dependency issues.
Everything else imports get_data_dir() from here.

The Config class provides environment-variable-overridable defaults for all
hardcoded values used throughout the application.
"""

import os
import json
import logging
import threading

# Optional .env support — gracefully skip if python-dotenv is not installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

log = logging.getLogger('nomad.config')

APP_DISPLAY_NAME = 'NOMAD Field Desk'
APP_SHORT_NAME = 'NOMAD'
APP_EXECUTABLE_BASENAME = 'NOMADFieldDesk'
APP_STORAGE_DIRNAME = 'NOMADFieldDesk'
LEGACY_STORAGE_DIRNAMES = ('ProjectNOMAD',)


# ---------------------------------------------------------------------------
# Application Settings (class-based, env-overridable)
# ---------------------------------------------------------------------------

def _env_int(name, default):
    """Read an int from the environment, falling back to `default` on missing
    or non-numeric values rather than crashing at import time."""
    raw = os.environ.get(name)
    if raw is None or raw == '':
        return default
    try:
        return int(raw)
    except (ValueError, TypeError):
        log.warning('Invalid int for %s=%r — using default %d', name, raw, default)
        return default


class Config:
    """Central configuration with environment variable overrides."""

    # --- App Identity ---
    VERSION = os.environ.get('NOMAD_VERSION', '7.35.0')

    # --- Upload / Content Limits ---
    MAX_CONTENT_LENGTH = _env_int('NOMAD_MAX_CONTENT_LENGTH', 100 * 1024 * 1024)  # 100 MB

    # --- Knowledge Base / RAG ---
    EMBED_MODEL = os.environ.get('NOMAD_EMBED_MODEL', 'nomic-embed-text:v1.5')
    CHUNK_SIZE = _env_int('NOMAD_CHUNK_SIZE', 500)
    CHUNK_OVERLAP = _env_int('NOMAD_CHUNK_OVERLAP', 50)

    # --- SSE ---
    MAX_SSE_CLIENTS = _env_int('NOMAD_MAX_SSE_CLIENTS', 20)

    # --- Service Ports ---
    APP_PORT = _env_int('NOMAD_PORT', 8080)
    APP_HOST = os.environ.get('NOMAD_HOST', '127.0.0.1')
    OLLAMA_PORT = _env_int('NOMAD_OLLAMA_PORT', 11434)
    KIWIX_PORT = _env_int('NOMAD_KIWIX_PORT', 8888)
    CYBERCHEF_PORT = _env_int('NOMAD_CYBERCHEF_PORT', 8889)
    FLATNOTES_PORT = _env_int('NOMAD_FLATNOTES_PORT', 8890)
    KOLIBRI_PORT = _env_int('NOMAD_KOLIBRI_PORT', 8300)
    QDRANT_PORT = _env_int('NOMAD_QDRANT_PORT', 6333)
    STIRLING_PORT = _env_int('NOMAD_STIRLING_PORT', 8443)
    DISCOVERY_PORT = _env_int('NOMAD_DISCOVERY_PORT', 18080)

    # --- Map Extensions ---
    ALLOWED_MAP_EXTENSIONS = set(
        os.environ.get('NOMAD_ALLOWED_MAP_EXTENSIONS', 'pmtiles,mbtiles').split(',')
    )

    # --- Security ---
    SECRET_KEY = os.environ.get('NOMAD_SECRET_KEY', '')

    # --- Rate Limiting ---
    RATELIMIT_DEFAULT = os.environ.get('NOMAD_RATELIMIT_DEFAULT', '200/minute')
    RATELIMIT_MUTATING = os.environ.get('NOMAD_RATELIMIT_MUTATING', '60/minute')

    # --- Misc Magic Numbers ---
    CPU_MONITOR_INTERVAL = _env_int('NOMAD_CPU_MONITOR_INTERVAL', 2)
    OCR_PIPELINE_INTERVAL = _env_int('NOMAD_OCR_PIPELINE_INTERVAL', 60)

    @classmethod
    def secret_key(cls):
        """Return a secret key, generating one if not configured."""
        if not cls.SECRET_KEY:
            cls.SECRET_KEY = os.urandom(32).hex()
            log.debug('No NOMAD_SECRET_KEY set — generated random secret key for this session')
        return cls.SECRET_KEY

# Config cache — avoids re-reading config.json from disk on every get_data_dir() call
_config_cache = None
_config_mtime = 0
_config_lock = threading.Lock()


def get_config_path():
    """Fixed location for config pointer (outside data dir to solve bootstrap)."""
    from platform_utils import get_config_base
    base = get_config_base()
    preferred = os.path.join(base, APP_STORAGE_DIRNAME, 'config.json')
    if os.path.isfile(preferred):
        return preferred
    for legacy_name in LEGACY_STORAGE_DIRNAMES:
        legacy = os.path.join(base, legacy_name, 'config.json')
        if os.path.isfile(legacy):
            return legacy
    return preferred


def load_config() -> dict:
    global _config_cache, _config_mtime
    path = get_config_path()
    with _config_lock:
        if not os.path.isfile(path):
            return _config_cache if _config_cache is not None else {}
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return _config_cache if _config_cache is not None else {}
        # Return cached version if file hasn't changed
        if _config_cache is not None and mtime == _config_mtime:
            return _config_cache
        try:
            with open(path, 'r') as f:
                _config_cache = json.load(f)
                _config_mtime = mtime
                return _config_cache
        except (json.JSONDecodeError, OSError) as e:
            log.warning(f'Could not load config from {path}: {e}')
            # Try recovering from .tmp backup
            tmp_path = path + '.tmp'
            if os.path.isfile(tmp_path):
                try:
                    with open(tmp_path, 'r') as f:
                        data = json.load(f)
                    log.info(f'Recovered config from {tmp_path}')
                    _config_cache = data
                    return data
                except (json.JSONDecodeError, OSError):
                    pass
        return _config_cache if _config_cache is not None else {}


def get_config_value(key: str, default=None):
    """Get a single config value with a default."""
    return load_config().get(key, default)


def save_config(data: dict):
    global _config_cache, _config_mtime
    path = get_config_path()
    with _config_lock:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp_path = path + '.tmp'
        with open(tmp_path, 'w') as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        import sys
        try:
            os.replace(tmp_path, path)
        except PermissionError:
            if sys.platform == 'win32':
                # Windows: retry with backoff — antivirus may briefly lock the file
                import time as _time
                replaced = False
                for _attempt in range(3):
                    _time.sleep(0.1 * (_attempt + 1))
                    try:
                        os.replace(tmp_path, path)
                        replaced = True
                        break
                    except PermissionError:
                        pass
                if not replaced:
                    # Clean up stale .tmp before re-raising so future loads
                    # don't accidentally recover an outdated temp file.
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
                    raise PermissionError(f'Could not write config after retries: {path}')
            else:
                raise
        # Update cache immediately so subsequent reads are consistent
        _config_cache = data
        try:
            _config_mtime = os.path.getmtime(path)
        except OSError:
            _config_mtime = 0


def get_data_dir() -> str:
    """Single source of truth for the NOMAD data directory."""
    # Portable mode — store data next to the executable
    from platform_utils import is_portable_mode, get_portable_data_dir
    if is_portable_mode():
        return get_portable_data_dir()

    cfg = load_config()
    data_dir = cfg.get('data_dir', '')
    if data_dir and os.path.isabs(data_dir):
        try:
            os.makedirs(data_dir, exist_ok=True)
            return data_dir
        except OSError as exc:
            log.warning('Configured data directory unavailable, falling back to default: %s (%s)', data_dir, exc)
    from platform_utils import get_data_base
    data_base = get_data_base()
    default = os.path.join(data_base, APP_STORAGE_DIRNAME)
    if not os.path.isdir(default):
        for legacy_name in LEGACY_STORAGE_DIRNAMES:
            legacy_dir = os.path.join(data_base, legacy_name)
            if os.path.isdir(legacy_dir):
                default = legacy_dir
                break
    os.makedirs(default, exist_ok=True)
    return default


def set_data_dir(path: str):
    """Set a custom data directory. Only call during first-run wizard."""
    path = os.path.abspath(path)
    os.makedirs(path, exist_ok=True)
    # Validate directory is writable
    test_file = os.path.join(path, '.nomad_write_test')
    try:
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
    except OSError as e:
        raise ValueError(f'Data directory is not writable: {path} — {e}')
    cfg = load_config()
    cfg['data_dir'] = path
    save_config(cfg)
