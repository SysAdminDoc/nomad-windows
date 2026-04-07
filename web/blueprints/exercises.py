"""Multi-node group training exercises routes."""

import json
import logging
import platform
import time
import uuid as _uuid

from flask import Blueprint, request, jsonify

from db import db_session, log_activity
from web.utils import safe_json_list as _safe_json_list

log = logging.getLogger('nomad.web')

exercises_bp = Blueprint('exercises', __name__)


# ─── Node Identity Helpers ──────────────────────────────────────────

def _get_node_id():
    with db_session() as db:
        row = db.execute("SELECT value FROM settings WHERE key = 'node_id'").fetchone()
        if row and row['value']:
            return row['value']
        node_id = str(_uuid.uuid4())[:8]
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('node_id', ?)", (node_id,))
        db.commit()
        return node_id


def _get_node_name():
    with db_session() as db:
        row = db.execute("SELECT value FROM settings WHERE key = 'node_name'").fetchone()
    return (row['value'] if row and row['value'] else platform.node()) or 'NOMAD Node'


def _get_trusted_peers():
    """Get list of trusted federation peers."""
    with db_session() as db:
        peers = [dict(r) for r in db.execute(
            "SELECT node_id, node_name, ip, port FROM federation_peers WHERE trust_level IN ('trusted','admin','member') AND ip != ''").fetchall()]
    return peers


# ─── Multi-Node Group Training Exercises ─────────────────────────

@exercises_bp.route('/api/group-exercises')
def api_group_exercises_list():
    """List all group training exercises."""
    with db_session() as db:
        rows = db.execute('SELECT * FROM group_exercises ORDER BY updated_at DESC LIMIT 50').fetchall()
    result = []
    for r in rows:
        entry = dict(r)
        entry['participants'] = json.loads(entry.get('participants') or '[]')
        entry['decisions_log'] = json.loads(entry.get('decisions_log') or '[]')
        entry['shared_state'] = json.loads(entry.get('shared_state') or '{}')
        result.append(entry)
    return jsonify(result)

@exercises_bp.route('/api/group-exercises', methods=['POST'])
def api_group_exercises_create():
    """Create a new group exercise and broadcast to federation peers."""
    data = request.get_json() or {}
    exercise_id = str(_uuid.uuid4())[:12]
    node_id = _get_node_id()
    node_name = _get_node_name()
    title = (data.get('title', '') or 'Group Exercise').strip()[:200]
    scenario_type = data.get('scenario_type', 'grid_down')
    description = (data.get('description', '') or '').strip()[:1000]

    with db_session() as db:
        db.execute('''INSERT INTO group_exercises
            (exercise_id, title, scenario_type, description, initiator_node, initiator_name, participants, status, shared_state)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'recruiting', ?)''',
            (exercise_id, title, scenario_type, description, node_id, node_name,
             json.dumps([{'node_id': node_id, 'node_name': node_name, 'role': 'initiator', 'joined_at': time.strftime('%Y-%m-%dT%H:%M:%S')}]),
             json.dumps({'phase': 0, 'scenario_type': scenario_type, 'events': []})))
        db.commit()

    # Broadcast to federation peers
    peers = _get_trusted_peers()
    import requests as req
    invited = 0
    for peer in peers:
        try:
            req.post(f"http://{peer['ip']}:{peer.get('port', 8080)}/api/group-exercises/invite",
                     json={'exercise_id': exercise_id, 'title': title, 'scenario_type': scenario_type,
                           'description': description, 'initiator_node': node_id, 'initiator_name': node_name},
                     timeout=5)
            invited += 1
        except Exception:
            pass

    log_activity('group_exercise_created', 'training', f'Exercise "{title}" ({exercise_id}), invited {invited} peers')
    return jsonify({'exercise_id': exercise_id, 'invited': invited}), 201

@exercises_bp.route('/api/group-exercises/invite', methods=['POST'])
def api_group_exercises_invite():
    """Receive an exercise invitation from a peer."""
    data = request.get_json() or {}
    exercise_id = data.get('exercise_id', '')
    if not exercise_id:
        return jsonify({'error': 'Missing exercise_id'}), 400

    # Validate initiator is a known, non-blocked peer
    initiator = data.get('initiator_node', '')
    if initiator:
        with db_session() as db_check:
            peer = db_check.execute("SELECT trust_level FROM federation_peers WHERE node_id = ?", (initiator,)).fetchone()
        if peer and peer['trust_level'] == 'blocked':
            return jsonify({'error': 'Peer is blocked'}), 403

    with db_session() as db:
        existing = db.execute('SELECT id FROM group_exercises WHERE exercise_id = ?', (exercise_id,)).fetchone()
        if existing:
            return jsonify({'status': 'already_known'})
        db.execute('''INSERT INTO group_exercises
            (exercise_id, title, scenario_type, description, initiator_node, initiator_name, participants, status, shared_state)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'invited', '{}')''',
            (exercise_id, data.get('title', 'Group Exercise'), data.get('scenario_type', ''),
             data.get('description', ''), data.get('initiator_node', ''), data.get('initiator_name', ''),
             json.dumps([])))
        db.commit()
    log_activity('group_exercise_invited', 'training', f'Invited to "{data.get("title", "")}" by {data.get("initiator_name", "")}')
    return jsonify({'status': 'invited'})

@exercises_bp.route('/api/group-exercises/<exercise_id>/join', methods=['POST'])
def api_group_exercises_join(exercise_id):
    """Join an exercise — notifies initiator."""
    with db_session() as db:
        row = db.execute('SELECT * FROM group_exercises WHERE exercise_id = ?', (exercise_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Exercise not found'}), 404

        node_id = _get_node_id()
        node_name = _get_node_name()
        participants = _safe_json_list(row['participants'])
        if not any(isinstance(p, dict) and p.get('node_id') == node_id for p in participants):
            participants.append({'node_id': node_id, 'node_name': node_name, 'role': 'participant', 'joined_at': time.strftime('%Y-%m-%dT%H:%M:%S')})

        db.execute("UPDATE group_exercises SET participants = ?, status = 'active', updated_at = datetime('now') WHERE exercise_id = ?",
                   (json.dumps(participants), exercise_id))
        db.commit()
        initiator_node = row['initiator_node']

    # Notify initiator
    peers = _get_trusted_peers()
    import requests as req
    for peer in peers:
        if peer.get('node_id') == initiator_node:
            try:
                req.post(f"http://{peer['ip']}:{peer.get('port', 8080)}/api/group-exercises/{exercise_id}/participant-joined",
                         json={'node_id': node_id, 'node_name': node_name}, timeout=5)
            except Exception:
                pass
            break

    return jsonify({'status': 'joined', 'participants': len(participants)})

@exercises_bp.route('/api/group-exercises/<exercise_id>/participant-joined', methods=['POST'])
def api_group_exercises_participant_joined(exercise_id):
    """Receive notification that a peer joined."""
    data = request.get_json() or {}
    with db_session() as db:
        row = db.execute('SELECT participants FROM group_exercises WHERE exercise_id = ?', (exercise_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        participants = _safe_json_list(row['participants'])
        node_id = data.get('node_id', '')
        if not any(isinstance(p, dict) and p.get('node_id') == node_id for p in participants):
            participants.append({'node_id': node_id, 'node_name': data.get('node_name', ''), 'role': 'participant', 'joined_at': time.strftime('%Y-%m-%dT%H:%M:%S')})
        db.execute("UPDATE group_exercises SET participants = ?, updated_at = datetime('now') WHERE exercise_id = ?",
                   (json.dumps(participants), exercise_id))
        db.commit()
    return jsonify({'status': 'noted'})

@exercises_bp.route('/api/group-exercises/<exercise_id>/update-state', methods=['POST'])
def api_group_exercises_update_state(exercise_id):
    """Update shared exercise state (phase advance, decision, etc.)."""
    data = request.get_json() or {}
    with db_session() as db:
        row = db.execute('SELECT * FROM group_exercises WHERE exercise_id = ?', (exercise_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404

        try:
            shared_state = json.loads(row['shared_state'] or '{}')
            if not isinstance(shared_state, dict):
                shared_state = {}
        except (json.JSONDecodeError, TypeError, ValueError):
            shared_state = {}
        decisions_log = _safe_json_list(row['decisions_log'])

        if 'phase' in data:
            shared_state['phase'] = data['phase']
        if 'event' in data:
            shared_state.setdefault('events', []).append({
                'node': _get_node_id(), 'name': _get_node_name(),
                'event': data['event'], 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S')
            })
        if 'decision' in data:
            decisions_log.append({
                'node': _get_node_id(), 'name': _get_node_name(),
                'decision': data['decision'], 'phase': shared_state.get('phase', 0),
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S')
            })

        status = data.get('status', row['status'])
        score = data.get('score', row['score'])
        aar_text = data.get('aar_text', row['aar_text'])

        db.execute("""UPDATE group_exercises SET shared_state = ?, decisions_log = ?, current_phase = ?,
                      status = ?, score = ?, aar_text = ?, updated_at = datetime('now') WHERE exercise_id = ?""",
                   (json.dumps(shared_state), json.dumps(decisions_log), shared_state.get('phase', 0),
                    status, score, aar_text, exercise_id))
        db.commit()
        participants = _safe_json_list(row['participants'])

    # Broadcast state to all participants
    peers = _get_trusted_peers()
    import requests as req
    for p in participants:
        if p['node_id'] == _get_node_id():
            continue
        for peer in peers:
            if peer.get('node_id') == p['node_id']:
                try:
                    req.post(f"http://{peer['ip']}:{peer.get('port', 8080)}/api/group-exercises/{exercise_id}/sync-state",
                             json={'shared_state': shared_state, 'decisions_log': decisions_log,
                                   'status': status, 'score': score, 'aar_text': aar_text,
                                   'phase': shared_state.get('phase', 0),
                                   'source_node_id': _get_node_id()}, timeout=5)
                except Exception:
                    pass
                break

    return jsonify({'status': 'updated'})

@exercises_bp.route('/api/group-exercises/<exercise_id>/sync-state', methods=['POST'])
def api_group_exercises_sync_state(exercise_id):
    """Receive state update from another participant."""
    data = request.get_json() or {}
    # Validate sender is a known, non-blocked peer
    sender = data.get('source_node_id', '')
    if sender:
        with db_session() as db_check:
            peer = db_check.execute("SELECT trust_level FROM federation_peers WHERE node_id = ?", (sender,)).fetchone()
        if not peer or peer['trust_level'] == 'blocked':
            return jsonify({'error': 'Peer is blocked'}), 403
    with db_session() as db:
        db.execute("""UPDATE group_exercises SET shared_state = ?, decisions_log = ?, current_phase = ?,
                      status = ?, score = ?, aar_text = ?, updated_at = datetime('now') WHERE exercise_id = ?""",
                   (json.dumps(data.get('shared_state', {})), json.dumps(data.get('decisions_log', [])),
                    data.get('phase', 0), data.get('status', 'active'),
                    data.get('score', 0), data.get('aar_text', ''), exercise_id))
        db.commit()
    return jsonify({'status': 'synced'})
