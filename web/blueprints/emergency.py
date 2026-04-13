"""Emergency Mode — the "balloon went up" orchestrator (v7.5.0).

NOMAD has every component you need in an active crisis (SITREP, watch
rotation, incidents, contacts, AI, Situation Room alerts, proximity,
etc.) but nothing that *orchestrates* them for a live event. The user
shouldn't have to remember to start a watch schedule, log an incident,
and generate a SITREP separately. Emergency Mode does it for you.

Entering Emergency Mode:
  1. Writes a persistent state flag to settings (emergency_active=true,
     emergency_started_at, emergency_reason).
  2. Auto-creates an incident log entry with severity=critical and the
     user-supplied reason.
  3. Broadcasts an SSE event so every open tab can enter red-mode UI
     without polling.

Exiting Emergency Mode:
  1. Clears the state flags.
  2. Appends a close-out incident log entry with total duration.
  3. Broadcasts an SSE event so UI drops out of red mode.

All operations are idempotent — entering while already active is a
no-op (returns the existing state); exiting while inactive is a no-op.
This matters because a page reload during active emergency mode must
restore the banner without double-entering.
"""

import logging
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, current_app

from db import db_session, log_activity

emergency_bp = Blueprint('emergency', __name__)
log = logging.getLogger('nomad.emergency')

_STATE_KEYS = {
    'emergency_active':     'False',
    'emergency_started_at': '',
    'emergency_reason':     '',
    'emergency_incident_id': '',
}


def _read_state(db):
    """Load the emergency state dict from settings. Missing keys default."""
    keys = tuple(_STATE_KEYS.keys())
    placeholders = ','.join('?' * len(keys))
    rows = db.execute(
        f'SELECT key, value FROM settings WHERE key IN ({placeholders})',
        keys,
    ).fetchall()
    got = {r['key']: r['value'] for r in rows}
    return {
        'active': (got.get('emergency_active', 'False') or '').lower() == 'true',
        'started_at': got.get('emergency_started_at') or None,
        'reason': got.get('emergency_reason') or '',
        'incident_id': _parse_int(got.get('emergency_incident_id')),
    }


def _write_state(db, **kwargs):
    """Upsert any subset of the emergency_* settings keys."""
    for key, val in kwargs.items():
        full_key = f'emergency_{key}'
        if full_key not in _STATE_KEYS:
            continue
        db.execute(
            'INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
            (full_key, str(val) if val is not None else ''),
        )


def _parse_int(v):
    try: return int(v) if v not in (None, '') else None
    except (TypeError, ValueError): return None


def _duration_hours(started_iso):
    """Hours (float) between started_iso and now. None on bad input."""
    if not started_iso:
        return None
    try:
        started = datetime.fromisoformat(started_iso.replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    return round((datetime.now(timezone.utc) - started).total_seconds() / 3600, 2)


def _broadcast(event_type, payload):
    """Fire an SSE event so every open tab syncs without polling."""
    try:
        from web.app import _broadcast_event  # circular-safe: only imported at call-time
        _broadcast_event(event_type, payload)
    except Exception:
        # SSE is a nice-to-have; never let a broadcast error block state change
        pass


# ─── Routes ─────────────────────────────────────────────────────────

@emergency_bp.route('/api/emergency/status')
def api_emergency_status():
    """Return the current emergency state + derived duration.

    Also used on page load so every tab can pick up the banner after
    a reload without separately querying settings.
    """
    with db_session() as db:
        state = _read_state(db)
    state['duration_hours'] = _duration_hours(state['started_at'])
    return jsonify(state)


@emergency_bp.route('/api/emergency/enter', methods=['POST'])
def api_emergency_enter():
    """Enter emergency mode. Idempotent — returns current state if
    already active. Body: ``{reason}`` (optional, default 'Emergency').
    """
    data = request.get_json() or {}
    reason = (data.get('reason') or 'Emergency').strip()[:500]
    now_iso = datetime.now(timezone.utc).isoformat()

    with db_session() as db:
        state = _read_state(db)
        if state['active']:
            # Already active — return current state without mutation
            state['duration_hours'] = _duration_hours(state['started_at'])
            return jsonify({**state, 'already_active': True})

        # Create a critical incident for the timeline
        incident_id = None
        try:
            cur = db.execute(
                'INSERT INTO incidents (severity, category, description) VALUES (?, ?, ?)',
                ('critical', 'emergency', f'Emergency mode entered: {reason}'),
            )
            incident_id = cur.lastrowid
        except Exception as e:
            log.warning(f'Could not create incident on emergency enter: {e}')

        _write_state(db,
            active='True',
            started_at=now_iso,
            reason=reason,
            incident_id=incident_id if incident_id is not None else '',
        )
        db.commit()
        try:
            log_activity('emergency_enter', f'Emergency mode activated: {reason}')
        except Exception:
            pass

    _broadcast('emergency_enter', {'reason': reason, 'started_at': now_iso})
    return jsonify({
        'active': True,
        'started_at': now_iso,
        'reason': reason,
        'incident_id': incident_id,
        'duration_hours': 0.0,
    }), 201


@emergency_bp.route('/api/emergency/exit', methods=['POST'])
def api_emergency_exit():
    """Exit emergency mode. Idempotent — no-op if not currently active.
    Body: ``{closeout_note}`` (optional) gets logged to the incident.
    """
    data = request.get_json() or {}
    closeout = (data.get('closeout_note') or '').strip()[:2000]

    with db_session() as db:
        state = _read_state(db)
        if not state['active']:
            return jsonify({**state, 'already_inactive': True})

        duration = _duration_hours(state['started_at'])
        duration_str = f'{duration}h' if duration is not None else 'unknown duration'
        exit_reason = state['reason'] or 'Emergency'

        # Log the closeout as a second incident entry for the timeline
        try:
            msg = f'Emergency mode exited ({duration_str}): {exit_reason}'
            if closeout:
                msg += f' — {closeout}'
            db.execute(
                'INSERT INTO incidents (severity, category, description) VALUES (?, ?, ?)',
                ('info', 'emergency', msg),
            )
        except Exception as e:
            log.warning(f'Could not create incident on emergency exit: {e}')

        _write_state(db, active='False', started_at='', reason='', incident_id='')
        db.commit()
        try:
            log_activity('emergency_exit', f'Emergency mode deactivated ({duration_str})')
        except Exception:
            pass

    _broadcast('emergency_exit', {'duration_hours': duration})
    return jsonify({
        'active': False,
        'duration_hours': duration,
        'reason': exit_reason,
    })
