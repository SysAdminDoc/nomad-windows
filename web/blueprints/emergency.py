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
from web.blueprints import get_pagination
from web.utils import coerce_int as _ci

emergency_bp = Blueprint('emergency', __name__)
log = logging.getLogger('nomad.emergency')

# Module-level column allowlists (V8-14) — auditable field whitelists for
# UPDATE/INSERT payload filtering. Keep in sync with the underlying schema
# in db.py (evac_plans / evac_rally_points / evac_assignments).
ALLOWED_EVAC_PLAN_FIELDS = frozenset({
    'name', 'plan_type', 'is_active', 'destination', 'primary_route',
    'alternate_route', 'distance_miles', 'estimated_time_min',
    'trigger_conditions', 'notes',
})
ALLOWED_EVAC_RALLY_FIELDS = frozenset({
    'name', 'location', 'lat', 'lng', 'point_type', 'sequence_order', 'notes',
})
ALLOWED_EVAC_ASSIGNMENT_FIELDS = frozenset({
    'person_name', 'role', 'vehicle', 'go_bag', 'notes',
})

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
    try:
        return int(v) if v not in (None, '') else None
    except (TypeError, ValueError):
        return None


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
        # web.state.broadcast_event is the canonical SSE publisher. An earlier
        # import path (`from web.app import _broadcast_event`) referenced a
        # name that was never exported — the try/except below was silently
        # swallowing the ImportError on every call, so Emergency-mode
        # broadcasts never reached any client. Fixed by importing the real
        # symbol directly.
        from web.state import broadcast_event
        broadcast_event(event_type, payload)
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
        except Exception as e:
            log.debug('log_activity failed: %s', e)

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
        except Exception as e:
            log.debug('log_activity failed: %s', e)

    _broadcast('emergency_exit', {'duration_hours': duration})
    return jsonify({
        'active': False,
        'duration_hours': duration,
        'reason': exit_reason,
    })


# ─── Evacuation Planning ─────────────────────────────────────────────

@emergency_bp.route('/api/emergency/evac-plans')
def api_evac_plans_list():
    """List all evacuation plans, active ones first."""
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM evac_plans ORDER BY is_active DESC, updated_at DESC LIMIT ? OFFSET ?',
            get_pagination()
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@emergency_bp.route('/api/emergency/evac-plans', methods=['POST'])
def api_evac_plans_create():
    """Create a new evacuation plan. If is_active=1, deactivate all others."""
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400

    plan_type = data.get('plan_type', 'evacuate')
    is_active = int(bool(data.get('is_active', 0)))
    # Safe numeric coercion — raw float()/int() on user JSON raises 500 on
    # non-numeric input. Fall back to 0 for malformed values.
    try:
        distance_miles = float(data.get('distance_miles', 0) or 0)
    except (TypeError, ValueError):
        distance_miles = 0.0
    try:
        estimated_time_min = int(data.get('estimated_time_min', 0) or 0)
    except (TypeError, ValueError):
        estimated_time_min = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    with db_session() as db:
        if is_active:
            db.execute('UPDATE evac_plans SET is_active = 0')

        cur = db.execute(
            '''INSERT INTO evac_plans
               (name, plan_type, is_active, destination, primary_route,
                alternate_route, distance_miles, estimated_time_min,
                trigger_conditions, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                name,
                plan_type,
                is_active,
                data.get('destination', ''),
                data.get('primary_route', ''),
                data.get('alternate_route', ''),
                distance_miles,
                estimated_time_min,
                data.get('trigger_conditions', ''),
                data.get('notes', ''),
                now_iso,
                now_iso,
            ),
        )
        plan_id = cur.lastrowid
        db.commit()
        try:
            log_activity('evac_plan_create', f'Created evac plan: {name}')
        except Exception as e:
            log.debug('log_activity failed: %s', e)

    return jsonify({'id': plan_id, 'name': name}), 201


@emergency_bp.route('/api/emergency/evac-plans/<int:pid>')
def api_evac_plan_detail(pid):
    """Get a single plan with its rally points and assignments."""
    with db_session() as db:
        plan = db.execute(
            'SELECT * FROM evac_plans WHERE id = ?', (pid,)
        ).fetchone()
        if not plan:
            return jsonify({'error': 'plan not found'}), 404

        rally_points = db.execute(
            'SELECT * FROM rally_points WHERE evac_plan_id = ? ORDER BY sequence_order',
            (pid,),
        ).fetchall()

        assignments = db.execute(
            'SELECT * FROM evac_assignments WHERE evac_plan_id = ? ORDER BY role, person_name',
            (pid,),
        ).fetchall()

    result = dict(plan)
    result['rally_points'] = [dict(r) for r in rally_points]
    result['assignments'] = [dict(a) for a in assignments]
    return jsonify(result)


@emergency_bp.route('/api/emergency/evac-plans/<int:pid>', methods=['PUT'])
def api_evac_plan_update(pid):
    """Update an existing evacuation plan."""
    data = request.get_json() or {}
    fields = {k: v for k, v in data.items() if k in ALLOWED_EVAC_PLAN_FIELDS}
    if not fields:
        return jsonify({'error': 'no valid fields to update'}), 400

    now_iso = datetime.now(timezone.utc).isoformat()
    fields['updated_at'] = now_iso

    with db_session() as db:
        existing = db.execute(
            'SELECT id FROM evac_plans WHERE id = ?', (pid,)
        ).fetchone()
        if not existing:
            return jsonify({'error': 'plan not found'}), 404

        if fields.get('is_active'):
            db.execute('UPDATE evac_plans SET is_active = 0')
            fields['is_active'] = 1

        set_clause = ', '.join(f'{k} = ?' for k in fields)
        values = list(fields.values()) + [pid]
        db.execute(f'UPDATE evac_plans SET {set_clause} WHERE id = ?', values)
        db.commit()
        try:
            log_activity('evac_plan_update', f'Updated evac plan id={pid}')
        except Exception as e:
            log.debug('log_activity failed: %s', e)

    return jsonify({'updated': True, 'id': pid})


@emergency_bp.route('/api/emergency/evac-plans/<int:pid>', methods=['DELETE'])
def api_evac_plan_delete(pid):
    """Delete a plan and cascade-delete its rally points and assignments."""
    with db_session() as db:
        existing = db.execute(
            'SELECT id, name FROM evac_plans WHERE id = ?', (pid,)
        ).fetchone()
        if not existing:
            return jsonify({'error': 'plan not found'}), 404

        db.execute('DELETE FROM rally_points WHERE evac_plan_id = ?', (pid,))
        db.execute('DELETE FROM evac_assignments WHERE evac_plan_id = ?', (pid,))
        db.execute('DELETE FROM evac_plans WHERE id = ?', (pid,))
        db.commit()
        try:
            log_activity('evac_plan_delete', f'Deleted evac plan: {existing["name"]}')
        except Exception as e:
            log.debug('log_activity failed: %s', e)

    return jsonify({'deleted': True, 'id': pid})


@emergency_bp.route('/api/emergency/evac-plans/<int:pid>/activate', methods=['POST'])
def api_evac_plan_activate(pid):
    """Activate a plan — deactivates all others first."""
    with db_session() as db:
        existing = db.execute(
            'SELECT id, name FROM evac_plans WHERE id = ?', (pid,)
        ).fetchone()
        if not existing:
            return jsonify({'error': 'plan not found'}), 404

        now_iso = datetime.now(timezone.utc).isoformat()
        db.execute('UPDATE evac_plans SET is_active = 0')
        db.execute(
            'UPDATE evac_plans SET is_active = 1, updated_at = ? WHERE id = ?',
            (now_iso, pid),
        )
        db.commit()
        try:
            log_activity('evac_plan_activate', f'Activated evac plan: {existing["name"]}')
        except Exception as e:
            log.debug('log_activity failed: %s', e)

    return jsonify({'activated': True, 'id': pid, 'name': existing['name']})


# ─── Rally Points ────────────────────────────────────────────────────

@emergency_bp.route('/api/emergency/evac-plans/<int:pid>/rally-points')
def api_rally_points_list(pid):
    """List rally points for a plan, ordered by sequence."""
    with db_session() as db:
        plan = db.execute(
            'SELECT id FROM evac_plans WHERE id = ?', (pid,)
        ).fetchone()
        if not plan:
            return jsonify({'error': 'plan not found'}), 404

        rows = db.execute(
            'SELECT * FROM rally_points WHERE evac_plan_id = ? ORDER BY sequence_order',
            (pid,),
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@emergency_bp.route('/api/emergency/evac-plans/<int:pid>/rally-points', methods=['POST'])
def api_rally_point_create(pid):
    """Create a rally point for a plan."""
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400

    # Validate coordinates if provided
    lat = data.get('lat')
    lng = data.get('lng')
    if lat is not None or lng is not None:
        try:
            lat = float(lat) if lat is not None else None
            lng = float(lng) if lng is not None else None
        except (ValueError, TypeError):
            return jsonify({'error': 'lat and lng must be numeric'}), 400
        if lat is not None and not (-90 <= lat <= 90):
            return jsonify({'error': 'lat must be -90..90'}), 400
        if lng is not None and not (-180 <= lng <= 180):
            return jsonify({'error': 'lng must be -180..180'}), 400

    with db_session() as db:
        plan = db.execute(
            'SELECT id FROM evac_plans WHERE id = ?', (pid,)
        ).fetchone()
        if not plan:
            return jsonify({'error': 'plan not found'}), 404

        now_iso = datetime.now(timezone.utc).isoformat()
        cur = db.execute(
            '''INSERT INTO rally_points
               (evac_plan_id, name, location, lat, lng, point_type,
                sequence_order, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                pid,
                name,
                data.get('location', ''),
                lat,
                lng,
                data.get('point_type', 'assembly'),
                _ci(data.get('sequence_order', 0), 0, minimum=0),
                data.get('notes', ''),
                now_iso,
            ),
        )
        point_id = cur.lastrowid
        db.commit()
        try:
            log_activity('rally_point_create', f'Created rally point: {name}')
        except Exception as e:
            log.debug('log_activity failed: %s', e)

    return jsonify({'id': point_id, 'name': name}), 201


@emergency_bp.route('/api/emergency/rally-points/<int:rid>', methods=['PUT'])
def api_rally_point_update(rid):
    """Update a rally point."""
    data = request.get_json() or {}
    allowed = ALLOWED_EVAC_RALLY_FIELDS
    fields = {k: v for k, v in data.items() if k in allowed}
    if not fields:
        return jsonify({'error': 'no valid fields to update'}), 400
    # Validate coordinates if provided
    if 'lat' in fields or 'lng' in fields:
        try:
            if 'lat' in fields:
                lat_val = float(fields['lat'])
                if not (-90 <= lat_val <= 90):
                    return jsonify({'error': 'lat must be -90..90'}), 400
            if 'lng' in fields:
                lng_val = float(fields['lng'])
                if not (-180 <= lng_val <= 180):
                    return jsonify({'error': 'lng must be -180..180'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'lat and lng must be numeric'}), 400

    with db_session() as db:
        existing = db.execute(
            'SELECT id FROM rally_points WHERE id = ?', (rid,)
        ).fetchone()
        if not existing:
            return jsonify({'error': 'rally point not found'}), 404

        set_clause = ', '.join(f'{k} = ?' for k in fields)
        values = list(fields.values()) + [rid]
        db.execute(f'UPDATE rally_points SET {set_clause} WHERE id = ?', values)
        db.commit()
        try:
            log_activity('rally_point_update', f'Updated rally point id={rid}')
        except Exception as e:
            log.debug('log_activity failed: %s', e)

    return jsonify({'updated': True, 'id': rid})


@emergency_bp.route('/api/emergency/rally-points/<int:rid>', methods=['DELETE'])
def api_rally_point_delete(rid):
    """Delete a rally point."""
    with db_session() as db:
        existing = db.execute(
            'SELECT id FROM rally_points WHERE id = ?', (rid,)
        ).fetchone()
        if not existing:
            return jsonify({'error': 'rally point not found'}), 404

        db.execute('DELETE FROM rally_points WHERE id = ?', (rid,))
        db.commit()
        try:
            log_activity('rally_point_delete', f'Deleted rally point id={rid}')
        except Exception as e:
            log.debug('log_activity failed: %s', e)

    return jsonify({'deleted': True, 'id': rid})


# ─── Evacuation Assignments ──────────────────────────────────────────

@emergency_bp.route('/api/emergency/evac-plans/<int:pid>/assignments')
def api_assignments_list(pid):
    """List personnel assignments for a plan."""
    with db_session() as db:
        plan = db.execute(
            'SELECT id FROM evac_plans WHERE id = ?', (pid,)
        ).fetchone()
        if not plan:
            return jsonify({'error': 'plan not found'}), 404

        rows = db.execute(
            'SELECT * FROM evac_assignments WHERE evac_plan_id = ? ORDER BY role, person_name',
            (pid,),
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@emergency_bp.route('/api/emergency/evac-plans/<int:pid>/assignments', methods=['POST'])
def api_assignment_create(pid):
    """Create a personnel assignment for a plan."""
    data = request.get_json() or {}
    person_name = (data.get('person_name') or '').strip()
    if not person_name:
        return jsonify({'error': 'person_name is required'}), 400

    with db_session() as db:
        plan = db.execute(
            'SELECT id FROM evac_plans WHERE id = ?', (pid,)
        ).fetchone()
        if not plan:
            return jsonify({'error': 'plan not found'}), 404

        now_iso = datetime.now(timezone.utc).isoformat()
        cur = db.execute(
            '''INSERT INTO evac_assignments
               (evac_plan_id, person_name, role, vehicle, go_bag,
                checked_in, checked_in_at, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                pid,
                person_name,
                data.get('role', 'member'),
                data.get('vehicle', ''),
                data.get('go_bag', ''),
                0,
                '',
                data.get('notes', ''),
                now_iso,
            ),
        )
        assignment_id = cur.lastrowid
        db.commit()
        try:
            log_activity('evac_assignment_create', f'Assigned {person_name} to evac plan')
        except Exception as e:
            log.debug('log_activity failed: %s', e)

    return jsonify({'id': assignment_id, 'person_name': person_name}), 201


@emergency_bp.route('/api/emergency/assignments/<int:aid>', methods=['PUT'])
def api_assignment_update(aid):
    """Update a personnel assignment."""
    data = request.get_json() or {}
    allowed = ALLOWED_EVAC_ASSIGNMENT_FIELDS
    fields = {k: v for k, v in data.items() if k in allowed}
    if not fields:
        return jsonify({'error': 'no valid fields to update'}), 400

    with db_session() as db:
        existing = db.execute(
            'SELECT id FROM evac_assignments WHERE id = ?', (aid,)
        ).fetchone()
        if not existing:
            return jsonify({'error': 'assignment not found'}), 404

        set_clause = ', '.join(f'{k} = ?' for k in fields)
        values = list(fields.values()) + [aid]
        db.execute(f'UPDATE evac_assignments SET {set_clause} WHERE id = ?', values)
        db.commit()
        try:
            log_activity('evac_assignment_update', f'Updated assignment id={aid}')
        except Exception as e:
            log.debug('log_activity failed: %s', e)

    return jsonify({'updated': True, 'id': aid})


@emergency_bp.route('/api/emergency/assignments/<int:aid>', methods=['DELETE'])
def api_assignment_delete(aid):
    """Delete a personnel assignment."""
    with db_session() as db:
        existing = db.execute(
            'SELECT id FROM evac_assignments WHERE id = ?', (aid,)
        ).fetchone()
        if not existing:
            return jsonify({'error': 'assignment not found'}), 404

        db.execute('DELETE FROM evac_assignments WHERE id = ?', (aid,))
        db.commit()
        try:
            log_activity('evac_assignment_delete', f'Deleted assignment id={aid}')
        except Exception as e:
            log.debug('log_activity failed: %s', e)

    return jsonify({'deleted': True, 'id': aid})


@emergency_bp.route('/api/emergency/assignments/<int:aid>/check-in', methods=['POST'])
def api_assignment_checkin(aid):
    """Mark a person as checked in."""
    with db_session() as db:
        existing = db.execute(
            'SELECT id, person_name FROM evac_assignments WHERE id = ?', (aid,)
        ).fetchone()
        if not existing:
            return jsonify({'error': 'assignment not found'}), 404

        now_iso = datetime.now(timezone.utc).isoformat()
        db.execute(
            'UPDATE evac_assignments SET checked_in = 1, checked_in_at = ? WHERE id = ?',
            (now_iso, aid),
        )
        db.commit()
        try:
            log_activity('evac_checkin', f'{existing["person_name"]} checked in')
        except Exception as e:
            log.debug('log_activity failed: %s', e)

    return jsonify({'checked_in': True, 'id': aid, 'checked_in_at': now_iso})


@emergency_bp.route('/api/emergency/evac-plans/<int:pid>/reset-checkins', methods=['POST'])
def api_evac_plan_reset_checkins(pid):
    """Reset all check-ins for a plan."""
    with db_session() as db:
        plan = db.execute(
            'SELECT id, name FROM evac_plans WHERE id = ?', (pid,)
        ).fetchone()
        if not plan:
            return jsonify({'error': 'plan not found'}), 404

        db.execute(
            "UPDATE evac_assignments SET checked_in = 0, checked_in_at = '' WHERE evac_plan_id = ?",
            (pid,),
        )
        db.commit()
        try:
            log_activity('evac_reset_checkins', f'Reset check-ins for plan: {plan["name"]}')
        except Exception as e:
            log.debug('log_activity failed: %s', e)

    return jsonify({'reset': True, 'plan_id': pid})


# ─── Accountability & Summary ────────────────────────────────────────

@emergency_bp.route('/api/emergency/evac-plans/<int:pid>/accountability')
def api_evac_plan_accountability(pid):
    """Accountability report: total, checked-in, missing, personnel list."""
    with db_session() as db:
        plan = db.execute(
            'SELECT id, name FROM evac_plans WHERE id = ?', (pid,)
        ).fetchone()
        if not plan:
            return jsonify({'error': 'plan not found'}), 404

        rows = db.execute(
            'SELECT person_name, role, checked_in, checked_in_at '
            'FROM evac_assignments WHERE evac_plan_id = ? ORDER BY role, person_name',
            (pid,),
        ).fetchall()

    personnel = [dict(r) for r in rows]
    total = len(personnel)
    checked_in = sum(1 for p in personnel if p['checked_in'])
    missing = total - checked_in

    return jsonify({
        'total': total,
        'checked_in': checked_in,
        'missing': missing,
        'personnel': personnel,
    })


@emergency_bp.route('/api/emergency/evac/summary')
def api_evac_summary():
    """Compact evacuation summary for dashboard widgets."""
    with db_session() as db:
        plans = db.execute('SELECT * FROM evac_plans').fetchall()
        total_plans = len(plans)

        active_plan = None
        for p in plans:
            if p['is_active']:
                active_plan = p
                break

        has_active = active_plan is not None
        active_name = active_plan['name'] if active_plan else ''

        total_personnel = 0
        checked_in_count = 0
        if active_plan:
            rows = db.execute(
                'SELECT checked_in FROM evac_assignments WHERE evac_plan_id = ?',
                (active_plan['id'],),
            ).fetchall()
            total_personnel = len(rows)
            checked_in_count = sum(1 for r in rows if r['checked_in'])

    return jsonify({
        'total_plans': total_plans,
        'has_active_plan': has_active,
        'active_plan_name': active_name,
        'total_personnel': total_personnel,
        'checked_in_count': checked_in_count,
    })
