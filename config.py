"""Centralized configuration — data directory management.

This module has ZERO internal imports to avoid circular dependency issues.
Everything else imports get_data_dir() from here.
"""

import os
import json
import logging

log = logging.getLogger('nomad.config')


def get_config_path():
    """Fixed location for config pointer (outside data dir to solve bootstrap)."""
    base = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
    return os.path.join(base, 'ProjectNOMAD', 'config.json')


def load_config() -> dict:
    path = get_config_path()
    if os.path.isfile(path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            log.warning(f'Could not load config from {path}: {e}')
    return {}


def save_config(data: dict):
    path = get_config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def get_data_dir() -> str:
    """Single source of truth for the N.O.M.A.D. data directory."""
    cfg = load_config()
    data_dir = cfg.get('data_dir', '')
    if data_dir and os.path.isabs(data_dir):
        os.makedirs(data_dir, exist_ok=True)
        return data_dir
    default = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'ProjectNOMAD')
    os.makedirs(default, exist_ok=True)
    return default


def set_data_dir(path: str):
    """Set a custom data directory. Only call during first-run wizard."""
    path = os.path.abspath(path)
    os.makedirs(path, exist_ok=True)
    cfg = load_config()
    cfg['data_dir'] = path
    save_config(cfg)
