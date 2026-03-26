"""Centralized configuration — data directory management.

This module has ZERO internal imports to avoid circular dependency issues.
Everything else imports get_data_dir() from here.
"""

import os
import json
import logging

log = logging.getLogger('nomad.config')

# Config cache — avoids re-reading config.json from disk on every get_data_dir() call
_config_cache = None
_config_mtime = 0


def get_config_path():
    """Fixed location for config pointer (outside data dir to solve bootstrap)."""
    from platform_utils import get_config_base
    base = get_config_base()
    return os.path.join(base, 'ProjectNOMAD', 'config.json')


def load_config() -> dict:
    global _config_cache, _config_mtime
    path = get_config_path()
    if not os.path.isfile(path):
        return {}
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
            # Windows: retry once — antivirus may briefly lock the file
            import time as _time
            _time.sleep(0.1)
            os.replace(tmp_path, path)
        else:
            raise
    # Update cache immediately so subsequent reads are consistent
    _config_cache = data
    try:
        _config_mtime = os.path.getmtime(path)
    except OSError:
        _config_mtime = 0


def get_data_dir() -> str:
    """Single source of truth for the N.O.M.A.D. data directory."""
    cfg = load_config()
    data_dir = cfg.get('data_dir', '')
    if data_dir and os.path.isabs(data_dir):
        os.makedirs(data_dir, exist_ok=True)
        return data_dir
    from platform_utils import get_data_base
    default = os.path.join(get_data_base(), 'ProjectNOMAD')
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
