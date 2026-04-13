"""Family Check-in Board (v7.6.0).

A dedicated status board for each household member. In a real crisis the
hardest single question is "where's everyone and are they OK?" — this
answers it at a glance. Integrates with Emergency Mode (v7.5.0): the
banner summarizes "3 OK / 1 unaccounted" when active.

Status values (enforced in code, not DB CHECK so we can evolve them):
    ok            — safe, at expected location
    needs_help    — injured or in trouble, help needed
    en_route      — moving toward rally point
    unaccounted   — no contact, location unknown (the urgent bucket)

The status is intentionally coarse. Field-op checklists live-or-die on
4–6 clear buckets, not 20 subtle ones.
"""

import logging
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify

from db import db_session, log_activity

family_bp = Blueprint('family', __name__)
log = logging.getLogger('nomad.family')

_VALID_STATUS = ('ok', 'needs_help', 'en_route', 'unaccounted')


def _broadcast(event_type, payload):
    try:
        from web.app import _broadcast_event
        _broadcast_event(event_type, payload)
    except Exception:
        pass


def _row_to_dict(row):
    if row is None:
        return None
    return {
        'id': row['id'],
        'name': row['name'],
        'status': row['status'],
        'location': row['location'] or '',
        'note': row['note'] or '',
        'phone': row['phone'] or '',
        'updated_at': row['updated_at'],
        'created_at': row['created_at'],
    }


@family_bp.route('/api/family-checkins')
def api_family_checkins_list():
    """Return all family members with their current check-in state,
    plus a summary count by status for the dashboard badge."""
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM family_checkins ORDER BY '
            "  CASE status "
            "    WHEN 'unaccounted' THEN 0 "
            "    WHEN 'needs_help' THEN 1 "
            "    WHEN 'en_route' THEN 2 "
            "    ELSE 3 END, name"
        ).fetchall()
    members = [_row_to_dict(r) for r in rows]
    summary = {s: 0 for s in _VALID_STATUS}
    for m in members:
        summary[m['status']] = summary.get(m['status'], 0) + 1
    return jsonify({'members': members, 'summary': summary, 'total': len(members)})


@family_bp.route('/api/family-checkins', methods=['POST'])
def api_family_checkins_create():
    """Create a new family member slot.

    Body: ``{name, phone?, status?, location?, note?}``.

    Names are UNIQUE — repeat POSTs return 409 rather than silently
    creating duplicates. Use PUT to update existing members.
    """
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()[:200]
    if not name:
        return jsonify({'error': 'name required'}), 400
    status = (data.get('status') or 'ok').lower()
    if status not in _VALID_STATUS:
        return jsonify({'error': f'status must be one of {list(_VALID_STATUS)}'}), 400
    location = (data.get('location') or '').strip()[:500]
    note = (data.get('note') or '').strip()[:2000]
    phone = (data.get('phone') or '').strip()[:50]

    with db_session() as db:
        existing = db.execute('SELECT id FROM family_checkins WHERE name = ?', (name,)).fetchone()
        if existing:
            return jsonify({'error': f'member "{name}" already exists — use PUT to update'}), 409
        cur = db.execute(
            'INSERT INTO family_checkins (name, status, location, note, phone) VALUES (?, ?, ?, ?, ?)',
            (name, status, location, note, phone),
        )
        db.commit()
        row = db.execute('SELECT * FROM family_checkins WHERE id = ?', (cur.lastrowid,)).fetchone()
    try:
        log_activity('family_checkin_create', f'Added family member: {name}')
    except Exception:
        pass
    _broadcast('family_checkin', {'action': 'create', 'name': name, 'status': status})
    return jsonify(_row_to_dict(row)), 201


@family_bp.route('/api/family-checkins/<int:mid>', methods=['PUT'])
def api_family_checkins_update(mid):
    """Update any subset of {status, location, note, phone, name}.

    The common path — "mark Alice as OK at rally point" — is usually
    just ``{status: 'ok', location: 'Rally 1'}``. Only non-None fields
    in the body are applied; others are left alone.
    """
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT * FROM family_checkins WHERE id = ?', (mid,)).fetchone()
        if not existing:
            return jsonify({'error': 'not found'}), 404

        fields = []
        params = []
        if 'status' in data:
            status = (data.get('status') or '').lower()
            if status not in _VALID_STATUS:
                return jsonify({'error': f'status must be one of {list(_VALID_STATUS)}'}), 400
            fields.append('status = ?'); params.append(status)
        for key in ('location', 'note', 'phone', 'name'):
            if key in data:
                val = (data.get(key) or '').strip()[:2000]
                if key == 'name' and not val:
                    return jsonify({'error': 'name cannot be empty'}), 400
                fields.append(f'{key} = ?'); params.append(val)
        if not fields:
            return jsonify({'error': 'no fields to update'}), 400
        fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(mid)
        db.execute(f'UPDATE family_checkins SET {", ".join(fields)} WHERE id = ?', params)
        db.commit()
        row = db.execute('SELECT * FROM family_checkins WHERE id = ?', (mid,)).fetchone()
    result = _row_to_dict(row)
    _broadcast('family_checkin', {'action': 'update', 'name': result['name'], 'status': result['status']})
    return jsonify(result)


@family_bp.route('/api/family-checkins/<int:mid>', methods=['DELETE'])
def api_family_checkins_delete(mid):
    with db_session() as db:
        row = db.execute('SELECT name FROM family_checkins WHERE id = ?', (mid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM family_checkins WHERE id = ?', (mid,))
        db.commit()
    _broadcast('family_checkin', {'action': 'delete', 'name': row['name']})
    return jsonify({'status': 'deleted', 'id': mid})


@family_bp.route('/api/family-checkins/reset-all', methods=['POST'])
def api_family_checkins_reset_all():
    """Reset every member back to ``ok`` status. Used on Emergency Mode
    exit, and manually from the UI when a drill ends."""
    with db_session() as db:
        db.execute("UPDATE family_checkins SET status = 'ok', updated_at = CURRENT_TIMESTAMP")
        db.commit()
        count = db.execute('SELECT COUNT(*) as c FROM family_checkins').fetchone()['c']
    _broadcast('family_checkin', {'action': 'reset_all'})
    return jsonify({'status': 'ok', 'reset_count': count})
