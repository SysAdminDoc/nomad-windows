"""Undo/redo system blueprint (Phase 19, moved from routes_advanced)."""

import time
import threading
import logging
from collections import deque

from flask import Blueprint, jsonify

from db import db_session, log_activity

log = logging.getLogger('nomad.web')

undo_bp = Blueprint('undo', __name__)

# ─── Module-level state ──────────────────────────────────────────
_undo_stack = deque(maxlen=10)
_redo_stack = deque(maxlen=10)
_undo_lock = threading.Lock()

_UNDO_VALID_TABLES = {'inventory', 'contacts', 'notes', 'waypoints', 'documents',
                       'videos', 'audio', 'books', 'checklists', 'weather_log',
                       'sensor_devices', 'sensor_readings', 'iot_sensor_readings', 'journal', 'patients',
                       'vitals_log', 'wound_log', 'cameras', 'access_log',
                       'power_devices', 'power_log', 'incidents', 'comms_log',
                       'seeds', 'harvest_log', 'livestock', 'preservation_log',
                       'garden_plots', 'fuel_storage', 'equipment_log',
                       'ammo_inventory', 'community_resources', 'radiation_log',
                       'scheduled_tasks', 'skills', 'watch_schedules'}


# ─── Public API for other modules ────────────────────────────────

def push_undo(action_type, description, table, row_data):
    """Push an undoable action onto the stack.

    This is the public interface for other blueprints/modules to record
    destructive operations that can be undone within 30 seconds.
    """
    with _undo_lock:
        _undo_stack.append({
            'action_type': action_type,
            'description': description,
            'table': table,
            'row_data': row_data,
            'timestamp': time.time(),
        })


def _prune_expired():
    """Remove entries older than 30 seconds."""
    cutoff = time.time() - 30
    with _undo_lock:
        while _undo_stack and _undo_stack[0]['timestamp'] < cutoff:
            _undo_stack.popleft()


# ─── Routes ──────────────────────────────────────────────────────

@undo_bp.route('/api/undo', methods=['GET'])
def api_undo_peek():
    """Return the last undoable action (if within TTL)."""
    _prune_expired()
    with _undo_lock:
        if not _undo_stack:
            return jsonify({'available': False})
        entry = _undo_stack[-1]
        return jsonify({
            'available': True,
            'action_type': entry['action_type'],
            'description': entry['description'],
            'seconds_remaining': max(0, int(30 - (time.time() - entry['timestamp']))),
        })


@undo_bp.route('/api/undo', methods=['POST'])
def api_undo_execute():
    """Undo the last destructive action."""
    _prune_expired()
    with _undo_lock:
        if not _undo_stack:
            return jsonify({'error': 'Nothing to undo (expired or empty)'}), 404

        entry = _undo_stack.pop()

    table = entry['table']
    row_data = entry['row_data']

    if table not in _UNDO_VALID_TABLES:
        # Restore entry to stack since we couldn't process it
        with _undo_lock:
            _undo_stack.append(entry)
        return jsonify({'error': f'Undo refused: invalid table "{table}"'}), 400

    # Validate column names against actual table schema to prevent SQL injection
    try:
        with db_session() as db:
            valid_cols = {r['name'] for r in db.execute(f"PRAGMA table_info({table})").fetchall()}
            if not valid_cols:
                with _undo_lock:
                    _undo_stack.append(entry)
                return jsonify({'error': 'Undo failed: unknown table schema'}), 400

            if entry['action_type'] == 'delete':
                # Re-insert the deleted row — only use columns that exist in the table
                cols = [c for c in row_data.keys() if c in valid_cols]
                if not cols:
                    with _undo_lock:
                        _undo_stack.append(entry)
                    return jsonify({'error': 'Undo failed: no valid columns'}), 400
                placeholders = ', '.join(['?'] * len(cols))
                col_names = ', '.join(cols)
                db.execute(
                    f'INSERT INTO {table} ({col_names}) VALUES ({placeholders})',
                    [row_data[c] for c in cols])
                db.commit()
            elif entry['action_type'] == 'update':
                # Restore previous values — only use columns that exist in the table
                row_id = row_data.get('id')
                if row_id is not None:
                    safe_keys = [k for k in row_data if k != 'id' and k in valid_cols]
                    if not safe_keys:
                        with _undo_lock:
                            _undo_stack.append(entry)
                        return jsonify({'error': 'Undo failed: no valid columns'}), 400
                    sets = ', '.join(f'{k} = ?' for k in safe_keys)
                    vals = [row_data[k] for k in safe_keys]
                    vals.append(row_id)
                    db.execute(f'UPDATE {table} SET {sets} WHERE id = ?', vals)
                    db.commit()
            # Only move to redo stack after successful DB operation
            with _undo_lock:
                _redo_stack.append(entry)
            log_activity('undo', 'system', entry['description'])
    except Exception as e:
        # Restore entry to stack on failure
        with _undo_lock:
            _undo_stack.append(entry)
        log.error('Undo failed: %s', e)
        return jsonify({'error': 'Undo failed'}), 500

    return jsonify({
        'status': 'undone',
        'description': entry['description'],
    })


@undo_bp.route('/api/redo', methods=['POST'])
def api_redo():
    """Redo the last undone action."""
    with _undo_lock:
        if not _redo_stack:
            return jsonify({'error': 'Nothing to redo'}), 404

        entry = _redo_stack.pop()

    table = entry['table']
    row_data = entry['row_data']

    if table not in _UNDO_VALID_TABLES:
        with _undo_lock:
            _redo_stack.append(entry)
        return jsonify({'error': f'Redo refused: invalid table "{table}"'}), 400

    try:
        with db_session() as db:
            valid_cols = {r['name'] for r in db.execute(f"PRAGMA table_info({table})").fetchall()}
            if not valid_cols:
                with _undo_lock:
                    _redo_stack.append(entry)
                return jsonify({'error': 'Redo failed: unknown table schema'}), 400

            if entry['action_type'] == 'delete':
                # Original action was a delete — redo means delete the row again
                row_id = row_data.get('id')
                if row_id is not None:
                    db.execute(f'DELETE FROM {table} WHERE id = ?', [row_id])
                    db.commit()
                else:
                    with _undo_lock:
                        _redo_stack.append(entry)
                    return jsonify({'error': 'Redo failed: no row id'}), 400
            elif entry['action_type'] == 'update':
                with _undo_lock:
                    _redo_stack.append(entry)
                return jsonify({'error': 'Redo not supported for updates'}), 400

            # Only move to undo stack after successful DB operation
            with _undo_lock:
                _undo_stack.append(entry)
            log_activity('redo', 'system', entry['description'])
    except Exception as e:
        with _undo_lock:
            _redo_stack.append(entry)
        log.error('Redo failed: %s', e)
        return jsonify({'error': 'Redo failed'}), 500

    return jsonify({
        'status': 'redone',
        'description': entry['description'],
    })
