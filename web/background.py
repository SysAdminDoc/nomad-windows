"""Background daemon threads wired into the Flask app.

Extracted from web/app.py::create_app() in v7.65.0 as part of H-14.
Each ``start_*`` function is idempotent: repeated calls (e.g. across
``create_app()`` invocations in the test suite) will not spawn duplicate
threads thanks to module-level guards protected by locks.

Call order from ``create_app()``:
    start_discovery_listener(app)
    start_auto_backup(app)
    start_sse_cleanup(app)
"""

import json
import os
import threading
import time
import logging
from datetime import datetime

from config import Config
from db import db_session, get_db_path
from web.state import (
    _auto_backup_timer,
    sse_cleanup_stale_clients,
)
from web.utils import (
    safe_json_value as _safe_json_value,
    get_node_id as _get_node_id,
    get_node_name as _get_node_name,
)

log = logging.getLogger('nomad.web')

# ─── Discovery listener ────────────────────────────────────────────────

_discovery_listener_lock = threading.Lock()
_discovery_listener_started = False


def _discovery_listener():
    """UDP listener for LAN node discovery (federation).

    Binds loopback by default; set ``NOMAD_DISCOVERY_BIND=0.0.0.0`` to expose
    to the LAN. Runs as a daemon thread.
    """
    import socket

    # Imported lazily so set_version() at boot is observed
    from web.app import VERSION

    discovery_port = Config.DISCOVERY_PORT
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        bind_addr = os.environ.get('NOMAD_DISCOVERY_BIND', '127.0.0.1').strip() or '127.0.0.1'
        sock.bind((bind_addr, discovery_port))
        sock.settimeout(1)
        while True:
            try:
                data, addr = sock.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                # Socket closed by shutdown or OS-level error — exit loop
                break
            except Exception as loop_err:
                log.debug('Discovery listener recv error: %s', loop_err)
                continue
            try:
                msg = _safe_json_value(data, {})
                if not isinstance(msg, dict):
                    continue
                if msg.get('type') == 'nomad_discover' and msg.get('node_id') != _get_node_id():
                    response = json.dumps({
                        'type': 'nomad_announce',
                        'node_id': _get_node_id(),
                        'node_name': _get_node_name(),
                        'port': Config.APP_PORT,
                        'version': VERSION,
                    }).encode()
                    sock.sendto(response, addr)
            except Exception as loop_err:
                log.debug('Discovery listener handle error: %s', loop_err)
                continue
    except OSError as e:
        log.warning('Discovery listener not available (port %s in use?): %s',
                    Config.DISCOVERY_PORT, e)
    except Exception as e:
        log.warning('Discovery listener failed to start: %s', e)
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


def start_discovery_listener(app):  # noqa: ARG001 — app kept for symmetry
    global _discovery_listener_started
    if _discovery_listener_started:
        return
    with _discovery_listener_lock:
        if _discovery_listener_started:
            return
        threading.Thread(target=_discovery_listener, daemon=True).start()
        _discovery_listener_started = True


# ─── Auto-backup scheduler ─────────────────────────────────────────────

def _load_auto_backup_config():
    """Load backup settings, skipping quietly if the DB is unavailable."""
    try:
        with db_session() as db:
            row = db.execute(
                "SELECT value FROM settings WHERE key = 'auto_backup_config'"
            ).fetchone()
    except Exception as e:
        log.debug('Auto-backup config unavailable: %s', e)
        return None

    if not row or not row['value']:
        return None

    try:
        return _safe_json_value(row['value'], None)
    except (TypeError, ValueError) as e:
        log.warning('Invalid auto-backup config — skipping schedule: %s', e)
        return None


def _rotate_backups(backup_dir, keep_count):
    """Delete oldest backups exceeding ``keep_count``."""
    try:
        files = sorted(
            [f for f in os.listdir(backup_dir) if f.startswith('nomad_backup_')],
            key=lambda f: os.path.getmtime(os.path.join(backup_dir, f)),
            reverse=True,
        )
        for old_file in files[keep_count:]:
            try:
                os.remove(os.path.join(backup_dir, old_file))
            except OSError:
                pass
    except OSError:
        pass


def _run_auto_backup():
    """Execute a scheduled auto-backup and reschedule the next one."""
    import sqlite3 as _sqlite3

    try:
        cfg = _load_auto_backup_config()
        if not cfg or not cfg.get('enabled'):
            return

        db_path = get_db_path()
        data_dir = os.path.dirname(db_path)
        backup_dir = os.path.join(data_dir, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(backup_dir, f'nomad_backup_{ts}.db')

        src = _sqlite3.connect(db_path, timeout=30)
        try:
            dst = _sqlite3.connect(backup_path)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()

        if cfg.get('encrypt') and cfg.get('_derived_key'):
            try:
                from cryptography.fernet import Fernet
                key = cfg['_derived_key'].encode()
                f = Fernet(key)
                with open(backup_path, 'rb') as fp:
                    data = fp.read()
                encrypted = f.encrypt(data)
                enc_path = backup_path + '.enc'
                with open(enc_path, 'wb') as fp:
                    fp.write(encrypted)
                os.remove(backup_path)
            except ImportError:
                log.warning('cryptography package not installed — backup saved unencrypted')
            except Exception as e:
                log.warning('Encryption failed — backup saved unencrypted: %s', e)

        keep_count = cfg.get('keep_count', 7)
        _rotate_backups(backup_dir, keep_count)
        log.info('Auto-backup created: %s', os.path.basename(backup_path))
    except Exception as e:
        log.error('Auto-backup failed: %s', e)
    finally:
        _schedule_auto_backup()


def _schedule_auto_backup():
    """Schedule the next auto-backup based on persisted settings."""
    if _auto_backup_timer.get('timer'):
        _auto_backup_timer['timer'].cancel()
        _auto_backup_timer['timer'] = None
    try:
        cfg = _load_auto_backup_config()
        if not cfg:
            return
        if not cfg.get('enabled'):
            return
        interval = cfg.get('interval', 'daily')
        seconds = 86400 if interval == 'daily' else 604800
        timer = threading.Timer(seconds, _run_auto_backup)
        timer.daemon = True
        timer.start()
        _auto_backup_timer['timer'] = timer
    except Exception as e:
        log.debug('Failed to schedule auto-backup: %s', e)


def start_auto_backup(app):
    """Expose the scheduler hook + kick off the first schedule."""
    app.config['_schedule_auto_backup'] = _schedule_auto_backup
    try:
        _schedule_auto_backup()
    except Exception:  # pragma: no cover — schedule is best-effort at boot
        pass


# ─── SSE stale client cleanup ──────────────────────────────────────────

_sse_cleanup_lock = threading.Lock()
_sse_cleanup_started = False


def start_sse_cleanup(app):
    """Start the stale-client sweeper and wire a stop event for shutdown."""
    global _sse_cleanup_started

    stop_event = app.config.get('_sse_cleanup_stop')
    if stop_event is None:
        stop_event = threading.Event()
        app.config['_sse_cleanup_stop'] = stop_event

    def _loop():
        while not stop_event.is_set():
            if stop_event.wait(timeout=30):
                return
            try:
                sse_cleanup_stale_clients()
            except Exception as e:
                log.debug('SSE cleanup error: %s', e)

    if _sse_cleanup_started:
        return
    with _sse_cleanup_lock:
        if _sse_cleanup_started:
            return
        threading.Thread(target=_loop, daemon=True).start()
        _sse_cleanup_started = True
