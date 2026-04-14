"""Group Operations & Governance — pods, members, roles, SOPs, duty roster,
disputes/voting, ICS forms, CERT teams, damage assessments, shelters, and
community warnings (Phase 11)."""

import json
import logging
from datetime import datetime, date, timedelta

from flask import Blueprint, request, jsonify

from db import db_session, log_activity

group_ops_bp = Blueprint('group_ops', __name__, url_prefix='/api/group')
_log = logging.getLogger('nomad.group_ops')


def _jp(val):
    """Parse a JSON column value, returning [] on failure."""
    try:
        return json.loads(val)
    except Exception:
        return []


def _jo(val):
    """Parse a JSON column value expected to be an object, returning {} on failure."""
    try:
        return json.loads(val)
    except Exception:
        return {}


ICS_TEMPLATES = {
    'ICS-201': {'name': 'Incident Briefing', 'fields': ['incident_name', 'date_time', 'map_sketch', 'current_situation', 'initial_objectives', 'current_actions', 'resources_ordered', 'resources_on_scene', 'org_chart']},
    'ICS-202': {'name': 'Incident Objectives', 'fields': ['incident_name', 'operational_period', 'objectives', 'weather_forecast', 'safety_message', 'attachments']},
    'ICS-204': {'name': 'Assignment List', 'fields': ['incident_name', 'operational_period', 'branch', 'division_group', 'staging_area', 'resources_assigned', 'work_assignments', 'special_instructions', 'communications']},
    'ICS-205': {'name': 'Communications Plan', 'fields': ['incident_name', 'operational_period', 'basic_comms', 'channels', 'frequencies', 'assignments', 'special_instructions']},
    'ICS-206': {'name': 'Medical Plan', 'fields': ['incident_name', 'operational_period', 'medical_aid_stations', 'transportation', 'hospitals', 'medical_procedures', 'prepared_by']},
    'ICS-213': {'name': 'General Message', 'fields': ['incident_name', 'to', 'from_field', 'subject', 'date_time', 'message', 'approved_by', 'reply']},
    'ICS-214': {'name': 'Activity Log', 'fields': ['incident_name', 'operational_period', 'name', 'ics_position', 'home_agency', 'activity_log_entries']},
    'ICS-215': {'name': 'Operational Planning Worksheet', 'fields': ['incident_name', 'operational_period', 'branches', 'divisions', 'work_assignments', 'resources_required', 'reporting_location', 'transport_needed']},
}


# ═══════════════════════════════════════════════════════════════════
# POD MANAGEMENT
# ═══════════════════════════════════════════════════════════════════

@group_ops_bp.route('/pods')
def api_pods_list():
    status = request.args.get('status', '')
    with db_session() as db:
        if status:
            rows = db.execute('SELECT * FROM pods WHERE status = ? ORDER BY name', (status,)).fetchall()
        else:
            rows = db.execute('SELECT * FROM pods ORDER BY name').fetchall()
    return jsonify([dict(r) for r in rows])


@group_ops_bp.route('/pods/<int:pid>')
def api_pod_detail(pid):
    with db_session() as db:
        pod = db.execute('SELECT * FROM pods WHERE id = ?', (pid,)).fetchone()
        if not pod:
            return jsonify({'error': 'Pod not found'}), 404
        members = db.execute('SELECT * FROM pod_members WHERE pod_id = ? ORDER BY role, person_name', (pid,)).fetchall()
    result = dict(pod)
    result['members'] = [_format_member(m) for m in members]
    return jsonify(result)


@group_ops_bp.route('/pods', methods=['POST'])
def api_pod_create():
    data = request.get_json() or {}
    if not data.get('name'):
        return jsonify({'error': 'Name required'}), 400
    now = datetime.utcnow().isoformat()
    with db_session() as db:
        db.execute('''
            INSERT INTO pods (name, description, location, status, leader_contact_id,
                              member_count, resource_sharing_policy, communication_plan,
                              meeting_schedule, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            data['name'], data.get('description', ''), data.get('location', ''),
            data.get('status', 'active'), data.get('leader_contact_id'),
            data.get('member_count', 0), data.get('resource_sharing_policy', ''),
            data.get('communication_plan', ''), data.get('meeting_schedule', ''),
            now, now,
        ))
        db.commit()
        row = db.execute('SELECT * FROM pods WHERE id = last_insert_rowid()').fetchone()
    log_activity('pod_created', service='group', detail=f'Created pod: {data["name"]}')
    return jsonify(dict(row)), 201


@group_ops_bp.route('/pods/<int:pid>', methods=['PUT'])
def api_pod_update(pid):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT * FROM pods WHERE id = ?', (pid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Pod not found'}), 404
        db.execute('''
            UPDATE pods SET name=?, description=?, location=?, status=?,
                leader_contact_id=?, member_count=?, resource_sharing_policy=?,
                communication_plan=?, meeting_schedule=?, updated_at=?
            WHERE id=?
        ''', (
            data.get('name', existing['name']),
            data.get('description', existing['description']),
            data.get('location', existing['location']),
            data.get('status', existing['status']),
            data.get('leader_contact_id', existing['leader_contact_id']),
            data.get('member_count', existing['member_count']),
            data.get('resource_sharing_policy', existing['resource_sharing_policy']),
            data.get('communication_plan', existing['communication_plan']),
            data.get('meeting_schedule', existing['meeting_schedule']),
            datetime.utcnow().isoformat(), pid,
        ))
        db.commit()
        row = db.execute('SELECT * FROM pods WHERE id = ?', (pid,)).fetchone()
    log_activity('pod_updated', service='group', detail=f'Updated pod {pid}')
    return jsonify(dict(row))


@group_ops_bp.route('/pods/<int:pid>', methods=['DELETE'])
def api_pod_delete(pid):
    with db_session() as db:
        r = db.execute('DELETE FROM pods WHERE id = ?', (pid,))
        if r.rowcount == 0:
            return jsonify({'error': 'Pod not found'}), 404
        db.commit()
    log_activity('pod_deleted', service='group', detail=f'Deleted pod {pid}')
    return jsonify({'status': 'deleted'})


@group_ops_bp.route('/pods/<int:pid>/summary')
def api_pod_summary(pid):
    with db_session() as db:
        pod = db.execute('SELECT * FROM pods WHERE id = ?', (pid,)).fetchone()
        if not pod:
            return jsonify({'error': 'Pod not found'}), 404
        member_count = db.execute('SELECT COUNT(*) as c FROM pod_members WHERE pod_id = ? AND status = ?', (pid, 'active')).fetchone()['c']
        active_duties = db.execute("SELECT COUNT(*) as c FROM duty_roster WHERE pod_id = ? AND status IN ('scheduled','active')", (pid,)).fetchone()['c']
        open_disputes = db.execute("SELECT COUNT(*) as c FROM disputes WHERE pod_id = ? AND status NOT IN ('resolved')", (pid,)).fetchone()['c']
        active_warnings = db.execute("SELECT COUNT(*) as c FROM community_warnings WHERE pod_id = ? AND status = 'active'", (pid,)).fetchone()['c']
    return jsonify({
        'pod': dict(pod),
        'active_members': member_count,
        'active_duties': active_duties,
        'open_disputes': open_disputes,
        'active_warnings': active_warnings,
    })


# ═══════════════════════════════════════════════════════════════════
# POD MEMBERS
# ═══════════════════════════════════════════════════════════════════

def _format_member(row):
    d = dict(row)
    d['skills'] = _jp(d.get('skills'))
    return d


@group_ops_bp.route('/pods/<int:pid>/members')
def api_pod_members_list(pid):
    with db_session() as db:
        rows = db.execute('SELECT * FROM pod_members WHERE pod_id = ? ORDER BY role, person_name', (pid,)).fetchall()
    return jsonify([_format_member(r) for r in rows])


@group_ops_bp.route('/pods/<int:pid>/members', methods=['POST'])
def api_pod_member_create(pid):
    data = request.get_json() or {}
    if not data.get('person_name'):
        return jsonify({'error': 'person_name required'}), 400
    skills = json.dumps(data.get('skills', []))
    now = datetime.utcnow().isoformat()
    with db_session() as db:
        db.execute('''
            INSERT INTO pod_members (pod_id, contact_id, person_name, role, skills,
                                     responsibilities, joined_date, status, notes, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        ''', (
            pid, data.get('contact_id'), data['person_name'],
            data.get('role', 'member'), skills,
            data.get('responsibilities', ''),
            data.get('joined_date', date.today().isoformat()),
            data.get('status', 'active'), data.get('notes', ''), now,
        ))
        db.commit()
        row = db.execute('SELECT * FROM pod_members WHERE id = last_insert_rowid()').fetchone()
    log_activity('pod_member_added', service='group', detail=f'Added {data["person_name"]} to pod {pid}')
    return jsonify(_format_member(row)), 201


@group_ops_bp.route('/members/<int:mid>', methods=['PUT'])
def api_pod_member_update(mid):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT * FROM pod_members WHERE id = ?', (mid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Member not found'}), 404
        skills = json.dumps(data['skills']) if 'skills' in data else existing['skills']
        db.execute('''
            UPDATE pod_members SET contact_id=?, person_name=?, role=?, skills=?,
                responsibilities=?, joined_date=?, status=?, notes=?
            WHERE id=?
        ''', (
            data.get('contact_id', existing['contact_id']),
            data.get('person_name', existing['person_name']),
            data.get('role', existing['role']),
            skills,
            data.get('responsibilities', existing['responsibilities']),
            data.get('joined_date', existing['joined_date']),
            data.get('status', existing['status']),
            data.get('notes', existing['notes']),
            mid,
        ))
        db.commit()
        row = db.execute('SELECT * FROM pod_members WHERE id = ?', (mid,)).fetchone()
    log_activity('pod_member_updated', service='group', detail=f'Updated member {mid}')
    return jsonify(_format_member(row))


@group_ops_bp.route('/members/<int:mid>', methods=['DELETE'])
def api_pod_member_delete(mid):
    with db_session() as db:
        r = db.execute('DELETE FROM pod_members WHERE id = ?', (mid,))
        if r.rowcount == 0:
            return jsonify({'error': 'Member not found'}), 404
        db.commit()
    log_activity('pod_member_removed', service='group', detail=f'Removed member {mid}')
    return jsonify({'status': 'deleted'})


# ═══════════════════════════════════════════════════════════════════
# GOVERNANCE ROLES
# ═══════════════════════════════════════════════════════════════════

def _format_role(row):
    d = dict(row)
    d['chain_of_command'] = _jp(d.get('chain_of_command'))
    return d


@group_ops_bp.route('/pods/<int:pid>/roles')
def api_governance_roles_list(pid):
    with db_session() as db:
        rows = db.execute('SELECT * FROM governance_roles WHERE pod_id = ? ORDER BY authority_level DESC', (pid,)).fetchall()
    return jsonify([_format_role(r) for r in rows])


@group_ops_bp.route('/pods/<int:pid>/roles', methods=['POST'])
def api_governance_role_create(pid):
    data = request.get_json() or {}
    if not data.get('role_title') or not data.get('person_name'):
        return jsonify({'error': 'role_title and person_name required'}), 400
    chain = json.dumps(data.get('chain_of_command', []))
    now = datetime.utcnow().isoformat()
    with db_session() as db:
        db.execute('''
            INSERT INTO governance_roles (pod_id, role_title, person_name, authority_level,
                responsibilities, chain_of_command, succession_order, term_start,
                term_end, status, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            pid, data['role_title'], data['person_name'],
            data.get('authority_level', 1), data.get('responsibilities', ''),
            chain, data.get('succession_order', 0),
            data.get('term_start', date.today().isoformat()),
            data.get('term_end', ''), data.get('status', 'active'),
            now, now,
        ))
        db.commit()
        row = db.execute('SELECT * FROM governance_roles WHERE id = last_insert_rowid()').fetchone()
    log_activity('governance_role_created', service='group', detail=f'Created role: {data["role_title"]} in pod {pid}')
    return jsonify(_format_role(row)), 201


@group_ops_bp.route('/roles/<int:rid>', methods=['PUT'])
def api_governance_role_update(rid):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT * FROM governance_roles WHERE id = ?', (rid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Role not found'}), 404
        chain = json.dumps(data['chain_of_command']) if 'chain_of_command' in data else existing['chain_of_command']
        db.execute('''
            UPDATE governance_roles SET role_title=?, person_name=?, authority_level=?,
                responsibilities=?, chain_of_command=?, succession_order=?,
                term_start=?, term_end=?, status=?, updated_at=?
            WHERE id=?
        ''', (
            data.get('role_title', existing['role_title']),
            data.get('person_name', existing['person_name']),
            data.get('authority_level', existing['authority_level']),
            data.get('responsibilities', existing['responsibilities']),
            chain,
            data.get('succession_order', existing['succession_order']),
            data.get('term_start', existing['term_start']),
            data.get('term_end', existing['term_end']),
            data.get('status', existing['status']),
            datetime.utcnow().isoformat(), rid,
        ))
        db.commit()
        row = db.execute('SELECT * FROM governance_roles WHERE id = ?', (rid,)).fetchone()
    log_activity('governance_role_updated', service='group', detail=f'Updated role {rid}')
    return jsonify(_format_role(row))


@group_ops_bp.route('/pods/<int:pid>/chain-of-command')
def api_chain_of_command(pid):
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM governance_roles WHERE pod_id = ? AND status = ? ORDER BY authority_level DESC, succession_order ASC',
            (pid, 'active'),
        ).fetchall()
    hierarchy = []
    for r in rows:
        hierarchy.append({
            'id': r['id'],
            'role_title': r['role_title'],
            'person_name': r['person_name'],
            'authority_level': r['authority_level'],
            'succession_order': r['succession_order'],
            'responsibilities': r['responsibilities'],
            'chain_of_command': _jp(r['chain_of_command']),
        })
    return jsonify({'pod_id': pid, 'chain': hierarchy})


# ═══════════════════════════════════════════════════════════════════
# GOVERNANCE SOPs
# ═══════════════════════════════════════════════════════════════════

@group_ops_bp.route('/sops')
def api_sops_list():
    pod_id = request.args.get('pod_id', '')
    category = request.args.get('category', '')
    status = request.args.get('status', '')
    with db_session() as db:
        q = 'SELECT * FROM governance_sops WHERE 1=1'
        params = []
        if pod_id:
            q += ' AND pod_id = ?'; params.append(pod_id)
        if category:
            q += ' AND category = ?'; params.append(category)
        if status:
            q += ' AND status = ?'; params.append(status)
        q += ' ORDER BY title'
        rows = db.execute(q, params).fetchall()
    return jsonify([dict(r) for r in rows])


@group_ops_bp.route('/sops', methods=['POST'])
def api_sop_create():
    data = request.get_json() or {}
    if not data.get('title') or not data.get('pod_id'):
        return jsonify({'error': 'title and pod_id required'}), 400
    now = datetime.utcnow().isoformat()
    with db_session() as db:
        db.execute('''
            INSERT INTO governance_sops (pod_id, title, category, content, version,
                effective_date, review_date, approved_by, status, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            data['pod_id'], data['title'], data.get('category', 'admin'),
            data.get('content', ''), data.get('version', '1.0'),
            data.get('effective_date', date.today().isoformat()),
            data.get('review_date', ''), data.get('approved_by', ''),
            data.get('status', 'draft'), now, now,
        ))
        db.commit()
        row = db.execute('SELECT * FROM governance_sops WHERE id = last_insert_rowid()').fetchone()
    log_activity('sop_created', service='group', detail=f'Created SOP: {data["title"]}')
    return jsonify(dict(row)), 201


@group_ops_bp.route('/sops/<int:sid>', methods=['PUT'])
def api_sop_update(sid):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT * FROM governance_sops WHERE id = ?', (sid,)).fetchone()
        if not existing:
            return jsonify({'error': 'SOP not found'}), 404
        db.execute('''
            UPDATE governance_sops SET pod_id=?, title=?, category=?, content=?, version=?,
                effective_date=?, review_date=?, approved_by=?, status=?, updated_at=?
            WHERE id=?
        ''', (
            data.get('pod_id', existing['pod_id']),
            data.get('title', existing['title']),
            data.get('category', existing['category']),
            data.get('content', existing['content']),
            data.get('version', existing['version']),
            data.get('effective_date', existing['effective_date']),
            data.get('review_date', existing['review_date']),
            data.get('approved_by', existing['approved_by']),
            data.get('status', existing['status']),
            datetime.utcnow().isoformat(), sid,
        ))
        db.commit()
        row = db.execute('SELECT * FROM governance_sops WHERE id = ?', (sid,)).fetchone()
    log_activity('sop_updated', service='group', detail=f'Updated SOP {sid}')
    return jsonify(dict(row))


@group_ops_bp.route('/sops/<int:sid>', methods=['DELETE'])
def api_sop_delete(sid):
    with db_session() as db:
        r = db.execute('DELETE FROM governance_sops WHERE id = ?', (sid,))
        if r.rowcount == 0:
            return jsonify({'error': 'SOP not found'}), 404
        db.commit()
    log_activity('sop_deleted', service='group', detail=f'Deleted SOP {sid}')
    return jsonify({'status': 'deleted'})


# ═══════════════════════════════════════════════════════════════════
# DUTY ROSTER
# ═══════════════════════════════════════════════════════════════════

@group_ops_bp.route('/duties')
def api_duties_list():
    pod_id = request.args.get('pod_id', '')
    day = request.args.get('date', '')
    status = request.args.get('status', '')
    with db_session() as db:
        q = 'SELECT * FROM duty_roster WHERE 1=1'
        params = []
        if pod_id:
            q += ' AND pod_id = ?'; params.append(pod_id)
        if day:
            q += ' AND date(shift_start) = ?'; params.append(day)
        if status:
            q += ' AND status = ?'; params.append(status)
        q += ' ORDER BY shift_start'
        rows = db.execute(q, params).fetchall()
    return jsonify([dict(r) for r in rows])


@group_ops_bp.route('/duties', methods=['POST'])
def api_duty_create():
    data = request.get_json() or {}
    if not data.get('pod_id') or not data.get('person_name') or not data.get('duty_type'):
        return jsonify({'error': 'pod_id, person_name, and duty_type required'}), 400
    now = datetime.utcnow().isoformat()
    with db_session() as db:
        db.execute('''
            INSERT INTO duty_roster (pod_id, person_name, duty_type, shift_start,
                shift_end, location, notes, status, created_at)
            VALUES (?,?,?,?,?,?,?,?,?)
        ''', (
            data['pod_id'], data['person_name'], data['duty_type'],
            data.get('shift_start', ''), data.get('shift_end', ''),
            data.get('location', ''), data.get('notes', ''),
            data.get('status', 'scheduled'), now,
        ))
        db.commit()
        row = db.execute('SELECT * FROM duty_roster WHERE id = last_insert_rowid()').fetchone()
    log_activity('duty_created', service='group', detail=f'{data["person_name"]} assigned {data["duty_type"]}')
    return jsonify(dict(row)), 201


@group_ops_bp.route('/duties/<int:did>', methods=['PUT'])
def api_duty_update(did):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT * FROM duty_roster WHERE id = ?', (did,)).fetchone()
        if not existing:
            return jsonify({'error': 'Duty not found'}), 404
        db.execute('''
            UPDATE duty_roster SET person_name=?, duty_type=?, shift_start=?,
                shift_end=?, location=?, notes=?, status=?
            WHERE id=?
        ''', (
            data.get('person_name', existing['person_name']),
            data.get('duty_type', existing['duty_type']),
            data.get('shift_start', existing['shift_start']),
            data.get('shift_end', existing['shift_end']),
            data.get('location', existing['location']),
            data.get('notes', existing['notes']),
            data.get('status', existing['status']),
            did,
        ))
        db.commit()
        row = db.execute('SELECT * FROM duty_roster WHERE id = ?', (did,)).fetchone()
    log_activity('duty_updated', service='group', detail=f'Updated duty {did}')
    return jsonify(dict(row))


@group_ops_bp.route('/duties/<int:did>', methods=['DELETE'])
def api_duty_delete(did):
    with db_session() as db:
        r = db.execute('DELETE FROM duty_roster WHERE id = ?', (did,))
        if r.rowcount == 0:
            return jsonify({'error': 'Duty not found'}), 404
        db.commit()
    log_activity('duty_deleted', service='group', detail=f'Deleted duty {did}')
    return jsonify({'status': 'deleted'})


# ═══════════════════════════════════════════════════════════════════
# DISPUTES & VOTING
# ═══════════════════════════════════════════════════════════════════

def _format_dispute(row):
    d = dict(row)
    d['parties_involved'] = _jp(d.get('parties_involved'))
    return d


def _format_vote(row):
    d = dict(row)
    d['options'] = _jp(d.get('options'))
    d['results'] = _jo(d.get('results'))
    return d


@group_ops_bp.route('/disputes')
def api_disputes_list():
    pod_id = request.args.get('pod_id', '')
    status = request.args.get('status', '')
    with db_session() as db:
        q = 'SELECT * FROM disputes WHERE 1=1'
        params = []
        if pod_id:
            q += ' AND pod_id = ?'; params.append(pod_id)
        if status:
            q += ' AND status = ?'; params.append(status)
        q += ' ORDER BY created_at DESC'
        rows = db.execute(q, params).fetchall()
    return jsonify([_format_dispute(r) for r in rows])


@group_ops_bp.route('/disputes', methods=['POST'])
def api_dispute_create():
    data = request.get_json() or {}
    if not data.get('pod_id') or not data.get('title'):
        return jsonify({'error': 'pod_id and title required'}), 400
    parties = json.dumps(data.get('parties_involved', []))
    now = datetime.utcnow().isoformat()
    with db_session() as db:
        db.execute('''
            INSERT INTO disputes (pod_id, title, description, parties_involved, dispute_type,
                severity, resolution_method, resolution, resolved_by, status,
                opened_date, resolved_date, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            data['pod_id'], data['title'], data.get('description', ''),
            parties, data.get('dispute_type', 'resource'),
            data.get('severity', 'medium'), data.get('resolution_method', 'mediation'),
            data.get('resolution', ''), data.get('resolved_by', ''),
            data.get('status', 'open'),
            data.get('opened_date', date.today().isoformat()),
            data.get('resolved_date', ''), now, now,
        ))
        db.commit()
        row = db.execute('SELECT * FROM disputes WHERE id = last_insert_rowid()').fetchone()
    log_activity('dispute_opened', service='group', detail=f'Dispute: {data["title"]}')
    return jsonify(_format_dispute(row)), 201


@group_ops_bp.route('/disputes/<int:did>', methods=['PUT'])
def api_dispute_update(did):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT * FROM disputes WHERE id = ?', (did,)).fetchone()
        if not existing:
            return jsonify({'error': 'Dispute not found'}), 404
        parties = json.dumps(data['parties_involved']) if 'parties_involved' in data else existing['parties_involved']
        db.execute('''
            UPDATE disputes SET title=?, description=?, parties_involved=?, dispute_type=?,
                severity=?, resolution_method=?, resolution=?, resolved_by=?,
                status=?, opened_date=?, resolved_date=?, updated_at=?
            WHERE id=?
        ''', (
            data.get('title', existing['title']),
            data.get('description', existing['description']),
            parties,
            data.get('dispute_type', existing['dispute_type']),
            data.get('severity', existing['severity']),
            data.get('resolution_method', existing['resolution_method']),
            data.get('resolution', existing['resolution']),
            data.get('resolved_by', existing['resolved_by']),
            data.get('status', existing['status']),
            data.get('opened_date', existing['opened_date']),
            data.get('resolved_date', existing['resolved_date']),
            datetime.utcnow().isoformat(), did,
        ))
        db.commit()
        row = db.execute('SELECT * FROM disputes WHERE id = ?', (did,)).fetchone()
    log_activity('dispute_updated', service='group', detail=f'Updated dispute {did}')
    return jsonify(_format_dispute(row))


@group_ops_bp.route('/disputes/<int:did>/vote', methods=['POST'])
def api_dispute_vote_create(did):
    data = request.get_json() or {}
    if not data.get('question'):
        return jsonify({'error': 'question required'}), 400
    options = json.dumps(data.get('options', []))
    results = json.dumps(data.get('results', {}))
    now = datetime.utcnow().isoformat()
    with db_session() as db:
        dispute = db.execute('SELECT id FROM disputes WHERE id = ?', (did,)).fetchone()
        if not dispute:
            return jsonify({'error': 'Dispute not found'}), 404
        db.execute('''
            INSERT INTO votes (dispute_id, question, vote_type, options, results,
                total_voters, votes_cast, status, deadline, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        ''', (
            did, data['question'], data.get('vote_type', 'simple_majority'),
            options, results,
            data.get('total_voters', 0), 0,
            data.get('status', 'open'), data.get('deadline', ''), now,
        ))
        db.commit()
        row = db.execute('SELECT * FROM votes WHERE id = last_insert_rowid()').fetchone()
    log_activity('vote_created', service='group', detail=f'Vote on dispute {did}: {data["question"]}')
    return jsonify(_format_vote(row)), 201


@group_ops_bp.route('/votes/<int:vid>', methods=['PUT'])
def api_vote_update(vid):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT * FROM votes WHERE id = ?', (vid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Vote not found'}), 404
        options = json.dumps(data['options']) if 'options' in data else existing['options']
        results = json.dumps(data['results']) if 'results' in data else existing['results']
        db.execute('''
            UPDATE votes SET question=?, vote_type=?, options=?, results=?,
                total_voters=?, votes_cast=?, status=?, deadline=?
            WHERE id=?
        ''', (
            data.get('question', existing['question']),
            data.get('vote_type', existing['vote_type']),
            options, results,
            data.get('total_voters', existing['total_voters']),
            data.get('votes_cast', existing['votes_cast']),
            data.get('status', existing['status']),
            data.get('deadline', existing['deadline']),
            vid,
        ))
        db.commit()
        row = db.execute('SELECT * FROM votes WHERE id = ?', (vid,)).fetchone()
    log_activity('vote_updated', service='group', detail=f'Updated vote {vid}')
    return jsonify(_format_vote(row))


@group_ops_bp.route('/votes/<int:vid>/cast', methods=['POST'])
def api_vote_cast(vid):
    data = request.get_json() or {}
    if not data.get('voter') or not data.get('choice'):
        return jsonify({'error': 'voter and choice required'}), 400
    with db_session() as db:
        vote = db.execute('SELECT * FROM votes WHERE id = ?', (vid,)).fetchone()
        if not vote:
            return jsonify({'error': 'Vote not found'}), 404
        if vote['status'] != 'open':
            return jsonify({'error': 'Vote is not open'}), 400
        results = _jo(vote['results'])
        choice = data['choice']
        if choice not in results:
            results[choice] = []
        if data['voter'] in results[choice]:
            return jsonify({'error': 'Already voted for this choice'}), 409
        # Remove voter from any previous choice
        for k in results:
            if isinstance(results[k], list) and data['voter'] in results[k]:
                results[k].remove(data['voter'])
        results[choice].append(data['voter'])
        total_cast = sum(len(v) for v in results.values() if isinstance(v, list))
        db.execute(
            'UPDATE votes SET results = ?, votes_cast = ? WHERE id = ?',
            (json.dumps(results), total_cast, vid),
        )
        db.commit()
        row = db.execute('SELECT * FROM votes WHERE id = ?', (vid,)).fetchone()
    log_activity('vote_cast', service='group', detail=f'{data["voter"]} voted on {vid}')
    return jsonify(_format_vote(row))


# ═══════════════════════════════════════════════════════════════════
# ICS FORMS
# ═══════════════════════════════════════════════════════════════════

def _format_ics(row):
    d = dict(row)
    d['form_data'] = _jo(d.get('form_data'))
    return d


@group_ops_bp.route('/ics-forms')
def api_ics_forms_list():
    pod_id = request.args.get('pod_id', '')
    form_type = request.args.get('form_type', '')
    with db_session() as db:
        q = 'SELECT * FROM ics_forms WHERE 1=1'
        params = []
        if pod_id:
            q += ' AND pod_id = ?'; params.append(pod_id)
        if form_type:
            q += ' AND form_type = ?'; params.append(form_type)
        q += ' ORDER BY created_at DESC'
        rows = db.execute(q, params).fetchall()
    return jsonify([_format_ics(r) for r in rows])


@group_ops_bp.route('/ics-forms', methods=['POST'])
def api_ics_form_create():
    data = request.get_json() or {}
    if not data.get('pod_id') or not data.get('form_type'):
        return jsonify({'error': 'pod_id and form_type required'}), 400
    if data['form_type'] not in ICS_TEMPLATES:
        return jsonify({'error': f'Invalid form_type. Valid: {", ".join(ICS_TEMPLATES.keys())}'}), 400
    form_data = json.dumps(data.get('form_data', {}))
    now = datetime.utcnow().isoformat()
    with db_session() as db:
        db.execute('''
            INSERT INTO ics_forms (pod_id, form_type, incident_name, operational_period,
                prepared_by, form_data, status, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?)
        ''', (
            data['pod_id'], data['form_type'],
            data.get('incident_name', ''), data.get('operational_period', ''),
            data.get('prepared_by', ''), form_data,
            data.get('status', 'draft'), now, now,
        ))
        db.commit()
        row = db.execute('SELECT * FROM ics_forms WHERE id = last_insert_rowid()').fetchone()
    log_activity('ics_form_created', service='group', detail=f'{data["form_type"]} created')
    return jsonify(_format_ics(row)), 201


@group_ops_bp.route('/ics-forms/<int:fid>', methods=['PUT'])
def api_ics_form_update(fid):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT * FROM ics_forms WHERE id = ?', (fid,)).fetchone()
        if not existing:
            return jsonify({'error': 'ICS form not found'}), 404
        form_data = json.dumps(data['form_data']) if 'form_data' in data else existing['form_data']
        db.execute('''
            UPDATE ics_forms SET incident_name=?, operational_period=?, prepared_by=?,
                form_data=?, status=?, updated_at=?
            WHERE id=?
        ''', (
            data.get('incident_name', existing['incident_name']),
            data.get('operational_period', existing['operational_period']),
            data.get('prepared_by', existing['prepared_by']),
            form_data,
            data.get('status', existing['status']),
            datetime.utcnow().isoformat(), fid,
        ))
        db.commit()
        row = db.execute('SELECT * FROM ics_forms WHERE id = ?', (fid,)).fetchone()
    log_activity('ics_form_updated', service='group', detail=f'Updated ICS form {fid}')
    return jsonify(_format_ics(row))


@group_ops_bp.route('/ics-forms/templates')
def api_ics_templates():
    return jsonify(ICS_TEMPLATES)


# ═══════════════════════════════════════════════════════════════════
# CERT TEAMS & DAMAGE ASSESSMENT
# ═══════════════════════════════════════════════════════════════════

def _format_cert(row):
    d = dict(row)
    d['members'] = _jp(d.get('members'))
    d['equipment'] = _jp(d.get('equipment'))
    return d


def _format_damage(row):
    d = dict(row)
    d['utilities'] = _jo(d.get('utilities'))
    d['hazards'] = _jp(d.get('hazards'))
    d['photo_refs'] = _jp(d.get('photo_refs'))
    return d


@group_ops_bp.route('/cert-teams')
def api_cert_teams_list():
    pod_id = request.args.get('pod_id', '')
    status = request.args.get('status', '')
    with db_session() as db:
        q = 'SELECT * FROM cert_teams WHERE 1=1'
        params = []
        if pod_id:
            q += ' AND pod_id = ?'; params.append(pod_id)
        if status:
            q += ' AND status = ?'; params.append(status)
        q += ' ORDER BY team_name'
        rows = db.execute(q, params).fetchall()
    return jsonify([_format_cert(r) for r in rows])


@group_ops_bp.route('/cert-teams', methods=['POST'])
def api_cert_team_create():
    data = request.get_json() or {}
    if not data.get('pod_id') or not data.get('team_name'):
        return jsonify({'error': 'pod_id and team_name required'}), 400
    members = json.dumps(data.get('members', []))
    equipment = json.dumps(data.get('equipment', []))
    now = datetime.utcnow().isoformat()
    with db_session() as db:
        db.execute('''
            INSERT INTO cert_teams (pod_id, team_name, team_type, leader_name, members,
                equipment, status, deployment_location, notes, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            data['pod_id'], data['team_name'], data.get('team_type', 'logistics'),
            data.get('leader_name', ''), members, equipment,
            data.get('status', 'active'), data.get('deployment_location', ''),
            data.get('notes', ''), now, now,
        ))
        db.commit()
        row = db.execute('SELECT * FROM cert_teams WHERE id = last_insert_rowid()').fetchone()
    log_activity('cert_team_created', service='group', detail=f'CERT team: {data["team_name"]}')
    return jsonify(_format_cert(row)), 201


@group_ops_bp.route('/cert-teams/<int:tid>', methods=['PUT'])
def api_cert_team_update(tid):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT * FROM cert_teams WHERE id = ?', (tid,)).fetchone()
        if not existing:
            return jsonify({'error': 'CERT team not found'}), 404
        members = json.dumps(data['members']) if 'members' in data else existing['members']
        equipment = json.dumps(data['equipment']) if 'equipment' in data else existing['equipment']
        db.execute('''
            UPDATE cert_teams SET team_name=?, team_type=?, leader_name=?, members=?,
                equipment=?, status=?, deployment_location=?, notes=?, updated_at=?
            WHERE id=?
        ''', (
            data.get('team_name', existing['team_name']),
            data.get('team_type', existing['team_type']),
            data.get('leader_name', existing['leader_name']),
            members, equipment,
            data.get('status', existing['status']),
            data.get('deployment_location', existing['deployment_location']),
            data.get('notes', existing['notes']),
            datetime.utcnow().isoformat(), tid,
        ))
        db.commit()
        row = db.execute('SELECT * FROM cert_teams WHERE id = ?', (tid,)).fetchone()
    log_activity('cert_team_updated', service='group', detail=f'Updated CERT team {tid}')
    return jsonify(_format_cert(row))


@group_ops_bp.route('/damage-assessments')
def api_damage_assessments_list():
    pod_id = request.args.get('pod_id', '')
    cert_team_id = request.args.get('cert_team_id', '')
    with db_session() as db:
        q = 'SELECT * FROM damage_assessments WHERE 1=1'
        params = []
        if pod_id:
            q += ' AND pod_id = ?'; params.append(pod_id)
        if cert_team_id:
            q += ' AND cert_team_id = ?'; params.append(cert_team_id)
        q += ' ORDER BY assessment_date DESC'
        rows = db.execute(q, params).fetchall()
    return jsonify([_format_damage(r) for r in rows])


@group_ops_bp.route('/damage-assessments', methods=['POST'])
def api_damage_assessment_create():
    data = request.get_json() or {}
    if not data.get('pod_id') or not data.get('location'):
        return jsonify({'error': 'pod_id and location required'}), 400
    utilities = json.dumps(data.get('utilities', {'power': 'ok', 'water': 'ok', 'gas': 'ok', 'sewer': 'ok'}))
    hazards = json.dumps(data.get('hazards', []))
    photo_refs = json.dumps(data.get('photo_refs', []))
    now = datetime.utcnow().isoformat()
    with db_session() as db:
        db.execute('''
            INSERT INTO damage_assessments (pod_id, cert_team_id, location, assessment_date,
                damage_type, severity, occupancy_status, utilities, hazards, photo_refs,
                notes, assessor_name, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            data['pod_id'], data.get('cert_team_id'),
            data['location'],
            data.get('assessment_date', date.today().isoformat()),
            data.get('damage_type', 'other'), data.get('severity', 'none'),
            data.get('occupancy_status', 'occupied'),
            utilities, hazards, photo_refs,
            data.get('notes', ''), data.get('assessor_name', ''), now,
        ))
        db.commit()
        row = db.execute('SELECT * FROM damage_assessments WHERE id = last_insert_rowid()').fetchone()
    log_activity('damage_assessment_created', service='group', detail=f'Assessment at {data["location"]}')
    return jsonify(_format_damage(row)), 201


# ═══════════════════════════════════════════════════════════════════
# SHELTERS
# ═══════════════════════════════════════════════════════════════════

def _format_shelter(row):
    d = dict(row)
    d['amenities'] = _jp(d.get('amenities'))
    return d


@group_ops_bp.route('/shelters')
def api_shelters_list():
    pod_id = request.args.get('pod_id', '')
    status = request.args.get('status', '')
    with db_session() as db:
        q = 'SELECT * FROM shelters WHERE 1=1'
        params = []
        if pod_id:
            q += ' AND pod_id = ?'; params.append(pod_id)
        if status:
            q += ' AND status = ?'; params.append(status)
        q += ' ORDER BY name'
        rows = db.execute(q, params).fetchall()
    return jsonify([_format_shelter(r) for r in rows])


@group_ops_bp.route('/shelters', methods=['POST'])
def api_shelter_create():
    data = request.get_json() or {}
    if not data.get('pod_id') or not data.get('name'):
        return jsonify({'error': 'pod_id and name required'}), 400
    amenities = json.dumps(data.get('amenities', []))
    now = datetime.utcnow().isoformat()
    with db_session() as db:
        db.execute('''
            INSERT INTO shelters (pod_id, name, location, capacity, current_occupancy,
                shelter_type, amenities, supplies_status, manager_name, status,
                opened_date, notes, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            data['pod_id'], data['name'], data.get('location', ''),
            data.get('capacity', 0), data.get('current_occupancy', 0),
            data.get('shelter_type', 'emergency'), amenities,
            data.get('supplies_status', 'adequate'),
            data.get('manager_name', ''), data.get('status', 'open'),
            data.get('opened_date', date.today().isoformat()),
            data.get('notes', ''), now, now,
        ))
        db.commit()
        row = db.execute('SELECT * FROM shelters WHERE id = last_insert_rowid()').fetchone()
    log_activity('shelter_created', service='group', detail=f'Shelter: {data["name"]}')
    return jsonify(_format_shelter(row)), 201


@group_ops_bp.route('/shelters/<int:sid>', methods=['PUT'])
def api_shelter_update(sid):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT * FROM shelters WHERE id = ?', (sid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Shelter not found'}), 404
        amenities = json.dumps(data['amenities']) if 'amenities' in data else existing['amenities']
        db.execute('''
            UPDATE shelters SET name=?, location=?, capacity=?, current_occupancy=?,
                shelter_type=?, amenities=?, supplies_status=?, manager_name=?,
                status=?, opened_date=?, notes=?, updated_at=?
            WHERE id=?
        ''', (
            data.get('name', existing['name']),
            data.get('location', existing['location']),
            data.get('capacity', existing['capacity']),
            data.get('current_occupancy', existing['current_occupancy']),
            data.get('shelter_type', existing['shelter_type']),
            amenities,
            data.get('supplies_status', existing['supplies_status']),
            data.get('manager_name', existing['manager_name']),
            data.get('status', existing['status']),
            data.get('opened_date', existing['opened_date']),
            data.get('notes', existing['notes']),
            datetime.utcnow().isoformat(), sid,
        ))
        db.commit()
        row = db.execute('SELECT * FROM shelters WHERE id = ?', (sid,)).fetchone()
    log_activity('shelter_updated', service='group', detail=f'Updated shelter {sid}')
    return jsonify(_format_shelter(row))


@group_ops_bp.route('/shelters/capacity')
def api_shelters_capacity():
    with db_session() as db:
        rows = db.execute("SELECT * FROM shelters WHERE status IN ('open', 'full')").fetchall()
    total_capacity = sum(r['capacity'] or 0 for r in rows)
    total_occupancy = sum(r['current_occupancy'] or 0 for r in rows)
    shelters = []
    for r in rows:
        cap = r['capacity'] or 0
        occ = r['current_occupancy'] or 0
        shelters.append({
            'id': r['id'],
            'name': r['name'],
            'location': r['location'] or '',
            'capacity': cap,
            'current_occupancy': occ,
            'available': max(0, cap - occ),
            'status': r['status'],
        })
    return jsonify({
        'total_capacity': total_capacity,
        'total_occupancy': total_occupancy,
        'total_available': max(0, total_capacity - total_occupancy),
        'shelter_count': len(shelters),
        'shelters': shelters,
    })


# ═══════════════════════════════════════════════════════════════════
# COMMUNITY WARNINGS
# ═══════════════════════════════════════════════════════════════════

def _format_warning(row):
    d = dict(row)
    d['delivery_methods'] = _jp(d.get('delivery_methods'))
    d['acknowledged_by'] = _jp(d.get('acknowledged_by'))
    return d


@group_ops_bp.route('/warnings')
def api_warnings_list():
    pod_id = request.args.get('pod_id', '')
    status = request.args.get('status', '')
    with db_session() as db:
        q = 'SELECT * FROM community_warnings WHERE 1=1'
        params = []
        if pod_id:
            q += ' AND pod_id = ?'; params.append(pod_id)
        if status:
            q += ' AND status = ?'; params.append(status)
        q += ' ORDER BY issued_at DESC'
        rows = db.execute(q, params).fetchall()
    return jsonify([_format_warning(r) for r in rows])


@group_ops_bp.route('/warnings', methods=['POST'])
def api_warning_create():
    data = request.get_json() or {}
    if not data.get('pod_id') or not data.get('title') or not data.get('message'):
        return jsonify({'error': 'pod_id, title, and message required'}), 400
    delivery = json.dumps(data.get('delivery_methods', []))
    acknowledged = json.dumps(data.get('acknowledged_by', []))
    now = datetime.utcnow().isoformat()
    with db_session() as db:
        db.execute('''
            INSERT INTO community_warnings (pod_id, title, message, severity, target_area,
                issued_by, issued_at, expires_at, delivery_methods, acknowledged_by,
                status, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            data['pod_id'], data['title'], data['message'],
            data.get('severity', 'info'), data.get('target_area', ''),
            data.get('issued_by', ''),
            data.get('issued_at', now), data.get('expires_at', ''),
            delivery, acknowledged,
            data.get('status', 'active'), now,
        ))
        db.commit()
        row = db.execute('SELECT * FROM community_warnings WHERE id = last_insert_rowid()').fetchone()
    log_activity('warning_issued', service='group', detail=f'Warning: {data["title"]} [{data.get("severity", "info")}]')
    return jsonify(_format_warning(row)), 201


@group_ops_bp.route('/warnings/<int:wid>', methods=['PUT'])
def api_warning_update(wid):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT * FROM community_warnings WHERE id = ?', (wid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Warning not found'}), 404
        delivery = json.dumps(data['delivery_methods']) if 'delivery_methods' in data else existing['delivery_methods']
        acknowledged = json.dumps(data['acknowledged_by']) if 'acknowledged_by' in data else existing['acknowledged_by']
        db.execute('''
            UPDATE community_warnings SET title=?, message=?, severity=?, target_area=?,
                issued_by=?, issued_at=?, expires_at=?, delivery_methods=?,
                acknowledged_by=?, status=?
            WHERE id=?
        ''', (
            data.get('title', existing['title']),
            data.get('message', existing['message']),
            data.get('severity', existing['severity']),
            data.get('target_area', existing['target_area']),
            data.get('issued_by', existing['issued_by']),
            data.get('issued_at', existing['issued_at']),
            data.get('expires_at', existing['expires_at']),
            delivery, acknowledged,
            data.get('status', existing['status']),
            wid,
        ))
        db.commit()
        row = db.execute('SELECT * FROM community_warnings WHERE id = ?', (wid,)).fetchone()
    log_activity('warning_updated', service='group', detail=f'Updated warning {wid}')
    return jsonify(_format_warning(row))


# ═══════════════════════════════════════════════════════════════════
# OVERALL SUMMARY
# ═══════════════════════════════════════════════════════════════════

@group_ops_bp.route('/summary')
def api_group_summary():
    with db_session() as db:
        pod_count = db.execute('SELECT COUNT(*) as c FROM pods').fetchone()['c']
        total_members = db.execute("SELECT COUNT(*) as c FROM pod_members WHERE status = 'active'").fetchone()['c']
        active_duties = db.execute("SELECT COUNT(*) as c FROM duty_roster WHERE status IN ('scheduled','active')").fetchone()['c']
        open_disputes = db.execute("SELECT COUNT(*) as c FROM disputes WHERE status NOT IN ('resolved')").fetchone()['c']
        active_warnings = db.execute("SELECT COUNT(*) as c FROM community_warnings WHERE status = 'active'").fetchone()['c']
        shelter_cap = db.execute("SELECT COALESCE(SUM(capacity),0) as cap, COALESCE(SUM(current_occupancy),0) as occ FROM shelters WHERE status IN ('open','full')").fetchone()
        active_cert = db.execute("SELECT COUNT(*) as c FROM cert_teams WHERE status IN ('active','deployed')").fetchone()['c']
        active_sops = db.execute("SELECT COUNT(*) as c FROM governance_sops WHERE status = 'active'").fetchone()['c']
    return jsonify({
        'pods': pod_count,
        'total_members': total_members,
        'active_duties': active_duties,
        'open_disputes': open_disputes,
        'active_warnings': active_warnings,
        'shelter_capacity': shelter_cap['cap'],
        'shelter_occupancy': shelter_cap['occ'],
        'shelter_available': max(0, shelter_cap['cap'] - shelter_cap['occ']),
        'active_cert_teams': active_cert,
        'active_sops': active_sops,
    })
