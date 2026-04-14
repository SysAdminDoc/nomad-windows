"""Security, OPSEC & Night Operations — Phase 12 of NOMAD Field Desk."""

import json
import math
from datetime import datetime, date, timedelta

from flask import Blueprint, request, jsonify
from db import db_session, log_activity

security_opsec_bp = Blueprint('security_opsec', __name__, url_prefix='/api/security-ops')


def _jp(val):
    """Parse a JSON array column."""
    try:
        return json.loads(val)
    except Exception:
        return []


def _jo(val):
    """Parse a JSON object column."""
    try:
        return json.loads(val)
    except Exception:
        return {}


# ─── Built-in Data ───────────────────────────────────────────────

BUILTIN_CHECKLISTS = [
    {'title': 'Digital Security Audit', 'category': 'digital', 'items': [
        {'item': 'All devices have strong passwords/PINs', 'checked': False, 'notes': ''},
        {'item': 'Full-disk encryption enabled on all devices', 'checked': False, 'notes': ''},
        {'item': 'Two-factor authentication on all accounts', 'checked': False, 'notes': ''},
        {'item': 'VPN used for all internet traffic', 'checked': False, 'notes': ''},
        {'item': 'No location services enabled unless needed', 'checked': False, 'notes': ''},
        {'item': 'Social media accounts sanitized', 'checked': False, 'notes': ''},
        {'item': 'Secure messaging app for sensitive comms', 'checked': False, 'notes': ''},
        {'item': 'Regular data backups on encrypted media', 'checked': False, 'notes': ''}
    ]},
    {'title': 'Physical Security Audit', 'category': 'physical', 'items': [
        {'item': 'All entry points secured (locks, bars, reinforcement)', 'checked': False, 'notes': ''},
        {'item': 'Perimeter lighting functional', 'checked': False, 'notes': ''},
        {'item': 'Security cameras operational and recording', 'checked': False, 'notes': ''},
        {'item': 'Safe room identified and stocked', 'checked': False, 'notes': ''},
        {'item': 'Sensitive documents in fireproof safe', 'checked': False, 'notes': ''},
        {'item': 'Vehicle always fueled above half tank', 'checked': False, 'notes': ''},
        {'item': 'Go-bag accessible within 60 seconds', 'checked': False, 'notes': ''},
        {'item': 'Neighbors and approaches observed daily', 'checked': False, 'notes': ''}
    ]},
    {'title': 'Communications Security Audit', 'category': 'communications', 'items': [
        {'item': 'Primary/alternate/contingency/emergency comms plan documented', 'checked': False, 'notes': ''},
        {'item': 'Radio frequencies and call signs changed regularly', 'checked': False, 'notes': ''},
        {'item': 'No sensitive info discussed on unsecured channels', 'checked': False, 'notes': ''},
        {'item': 'Authentication codes current and distributed', 'checked': False, 'notes': ''},
        {'item': 'Radio discipline enforced (brevity, no names)', 'checked': False, 'notes': ''},
        {'item': 'Backup communication methods tested monthly', 'checked': False, 'notes': ''}
    ]}
]

BUILTIN_CBRN = [
    {'title': 'Chemical Decontamination — Personal', 'procedure_type': 'decon', 'threat_agent': 'chemical',
     'mopp_level': 4, 'steps': [
         'Don full MOPP gear if not already equipped',
         'Move upwind/uphill from contaminated area',
         'Remove outer clothing layer (cut away if necessary)',
         'Blot (do not rub) liquid contamination with absorbent material',
         'Apply M291 decon kit or 0.5% bleach solution to skin',
         'Flush eyes with clean water for 15+ minutes if exposed',
         'Monitor for symptoms: difficulty breathing, pupil constriction, convulsions',
         'Administer nerve agent antidote (atropine/2-PAM) if symptomatic'],
     'equipment_required': ['MOPP suit', 'M291 decon kit or bleach', 'Clean water',
                            'Atropine auto-injector', 'Absorbent material'],
     'time_estimate_minutes': 20,
     'warnings': 'Do NOT re-enter contaminated area. Decon wash water is also contaminated.'},
    {'title': 'Biological — Shelter in Place', 'procedure_type': 'shelter', 'threat_agent': 'biological',
     'mopp_level': 2, 'steps': [
         'Seal all windows and doors with plastic sheeting and duct tape',
         'Turn off HVAC system', 'Close all vents and fireplace dampers',
         'Seal gaps under doors with wet towels',
         'Move to interior room (fewest windows)',
         'Monitor official channels for all-clear',
         'Maintain 3+ days of food and water inside',
         'Use HEPA filter if available'],
     'equipment_required': ['Plastic sheeting', 'Duct tape', 'HEPA air purifier',
                            '3-day food/water supply', 'N95/N100 masks', 'Radio'],
     'time_estimate_minutes': 15,
     'warnings': 'Do NOT open shelter until official all-clear. Monitor for symptoms.'},
    {'title': 'Radiological — KI Administration', 'procedure_type': 'medical', 'threat_agent': 'radiological',
     'mopp_level': 0, 'steps': [
         'Confirm radiological threat (dosimeter or official alert)',
         'Determine dose based on age (see KI dosage calculator)',
         'Administer KI tablets within 4 hours of exposure (ideally before)',
         'Adults: 130mg, Children 3-18: 65mg, Children 1-3: 32mg, Infants: 16mg',
         'Repeat daily only if ongoing exposure and directed by authorities',
         'Shelter in place or evacuate as directed',
         'Monitor dosimeter readings',
         'Seek medical attention if symptoms develop'],
     'equipment_required': ['KI tablets (130mg)', 'Personal dosimeter', 'Radio for official updates'],
     'time_estimate_minutes': 5,
     'warnings': 'KI only protects thyroid from radioactive iodine. Does NOT protect against other isotopes.'},
    {'title': 'Nuclear Fallout — Shelter Protocol', 'procedure_type': 'shelter', 'threat_agent': 'nuclear',
     'mopp_level': 4, 'steps': [
         'Get inside the nearest substantial building immediately',
         'Move to center of building, below ground if possible',
         'Stay away from windows and exterior walls',
         'Remove and bag contaminated outer clothing',
         'Shower or wipe down with wet cloth (do not use conditioner)',
         'Seal room if possible (plastic, duct tape)',
         'Remain sheltered minimum 24 hours (48-72 preferred)',
         'Use 7-10 rule: every 7x increase in time, radiation drops 10x',
         'After 48 hours, radiation is ~1% of initial level'],
     'equipment_required': ['Substantial building (concrete/brick preferred)', 'Plastic sheeting',
                            'Duct tape', '72-hour supply kit', 'Dosimeter', 'Radio', 'KI tablets'],
     'time_estimate_minutes': 10,
     'warnings': 'Do NOT go outside for first 24 hours. 7-10 rule: 7h=10x reduction, 49h=100x reduction.'}
]

SIGNATURE_GUIDE = {
    'visual': ['Camouflage netting over structures/vehicles', 'Minimize movement during daylight',
               'Use terrain masking', 'Blackout discipline at night',
               'Avoid reflective surfaces', 'Break up outlines and shadows'],
    'audio': ['Enforce noise discipline near perimeter', 'Muffle generator exhaust',
              'Use hand signals within visual range', 'Sound-absorbing barriers around work areas',
              'Avoid metal-on-metal contact', 'Schedule noisy activities during high ambient noise'],
    'electronic': ['Minimize radio transmissions', 'Use directional antennas',
                   'Vary transmission schedules', 'Shield electronic equipment',
                   'Use wire communications when possible', 'Disable WiFi/Bluetooth when not needed'],
    'thermal': ['Insulate heat sources', 'Use thermal blankets/screens',
                'Cook under cover or at night', 'Vent exhaust through terrain features',
                'Limit vehicle engine idle time', 'Use cold water to cool exposed surfaces']
}


# ═══════════════════════════════════════════════════════════════════
#  OPSEC COMPARTMENTS
# ═══════════════════════════════════════════════════════════════════

@security_opsec_bp.route('/opsec/compartments')
def api_compartments_list():
    status = request.args.get('status')
    clauses, params = [], []
    if status:
        clauses.append('status = ?')
        params.append(status)
    where = f'WHERE {" AND ".join(clauses)}' if clauses else ''
    with db_session() as db:
        rows = db.execute(
            f'SELECT * FROM opsec_compartments {where} ORDER BY name', params
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d['authorized_persons'] = _jp(d.get('authorized_persons'))
        out.append(d)
    return jsonify(out)


@security_opsec_bp.route('/opsec/compartments', methods=['POST'])
def api_compartments_create():
    data = request.get_json() or {}
    if not data.get('name'):
        return jsonify({'error': 'Name required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO opsec_compartments
               (name, description, classification, authorized_persons, cover_story,
                duress_signal, review_date, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?)''',
            (data['name'], data.get('description', ''),
             data.get('classification', 'open'),
             json.dumps(data.get('authorized_persons', [])),
             data.get('cover_story', ''), data.get('duress_signal', ''),
             data.get('review_date', ''), data.get('status', 'active'),
             data.get('notes', ''))
        )
        db.commit()
        log_activity('compartment_created', service='security_ops', detail=data['name'])
        row = db.execute('SELECT * FROM opsec_compartments WHERE id = ?', (cur.lastrowid,)).fetchone()
    d = dict(row)
    d['authorized_persons'] = _jp(d.get('authorized_persons'))
    return jsonify(d), 201


@security_opsec_bp.route('/opsec/compartments/<int:cid>', methods=['PUT'])
def api_compartments_update(cid):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT id FROM opsec_compartments WHERE id = ?', (cid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        allowed = ['name', 'description', 'classification', 'authorized_persons',
                    'cover_story', 'duress_signal', 'review_date', 'status', 'notes']
        sets, vals = [], []
        for col in allowed:
            if col in data:
                sets.append(f'{col} = ?')
                if col == 'authorized_persons':
                    vals.append(json.dumps(data[col]) if isinstance(data[col], list) else data[col])
                else:
                    vals.append(data[col])
        if not sets:
            return jsonify({'error': 'No fields to update'}), 400
        sets.append('updated_at = CURRENT_TIMESTAMP')
        vals.append(cid)
        db.execute(f'UPDATE opsec_compartments SET {", ".join(sets)} WHERE id = ?', vals)
        db.commit()
        log_activity('compartment_updated', service='security_ops', detail=f'Updated compartment {cid}')
        row = db.execute('SELECT * FROM opsec_compartments WHERE id = ?', (cid,)).fetchone()
    d = dict(row)
    d['authorized_persons'] = _jp(d.get('authorized_persons'))
    return jsonify(d)


@security_opsec_bp.route('/opsec/compartments/<int:cid>', methods=['DELETE'])
def api_compartments_delete(cid):
    with db_session() as db:
        existing = db.execute('SELECT id, name FROM opsec_compartments WHERE id = ?', (cid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        db.execute('UPDATE opsec_checklists SET compartment_id = NULL WHERE compartment_id = ?', (cid,))
        db.execute('DELETE FROM opsec_compartments WHERE id = ?', (cid,))
        db.commit()
        log_activity('compartment_deleted', service='security_ops', detail=existing['name'])
    return jsonify({'status': 'deleted'})


# ═══════════════════════════════════════════════════════════════════
#  OPSEC CHECKLISTS
# ═══════════════════════════════════════════════════════════════════

@security_opsec_bp.route('/opsec/checklists')
def api_checklists_list():
    category = request.args.get('category')
    clauses, params = [], []
    if category:
        clauses.append('category = ?')
        params.append(category)
    where = f'WHERE {" AND ".join(clauses)}' if clauses else ''
    with db_session() as db:
        rows = db.execute(
            f'SELECT * FROM opsec_checklists {where} ORDER BY title', params
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d['items'] = _jp(d.get('items'))
        out.append(d)
    return jsonify(out)


@security_opsec_bp.route('/opsec/checklists', methods=['POST'])
def api_checklists_create():
    data = request.get_json() or {}
    if not data.get('title'):
        return jsonify({'error': 'Title required'}), 400
    items = data.get('items', [])
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO opsec_checklists
               (compartment_id, title, category, items, last_audit_date, next_audit_date,
                audited_by, score, status)
               VALUES (?,?,?,?,?,?,?,?,?)''',
            (data.get('compartment_id'), data['title'],
             data.get('category', 'digital'), json.dumps(items),
             data.get('last_audit_date', ''), data.get('next_audit_date', ''),
             data.get('audited_by', ''), data.get('score', 0),
             data.get('status', 'active'))
        )
        db.commit()
        log_activity('checklist_created', service='security_ops', detail=data['title'])
        row = db.execute('SELECT * FROM opsec_checklists WHERE id = ?', (cur.lastrowid,)).fetchone()
    d = dict(row)
    d['items'] = _jp(d.get('items'))
    return jsonify(d), 201


@security_opsec_bp.route('/opsec/checklists/<int:cid>', methods=['PUT'])
def api_checklists_update(cid):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT id FROM opsec_checklists WHERE id = ?', (cid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        allowed = ['compartment_id', 'title', 'category', 'items', 'last_audit_date',
                    'next_audit_date', 'audited_by', 'score', 'status']
        sets, vals = [], []
        for col in allowed:
            if col in data:
                sets.append(f'{col} = ?')
                if col == 'items':
                    vals.append(json.dumps(data[col]) if isinstance(data[col], list) else data[col])
                else:
                    vals.append(data[col])
        # Auto-compute score from items if items were provided
        if 'items' in data and isinstance(data['items'], list):
            total = len(data['items'])
            checked = sum(1 for i in data['items'] if i.get('checked'))
            score = round((checked / total) * 100) if total > 0 else 0
            sets.append('score = ?')
            vals.append(score)
        if not sets:
            return jsonify({'error': 'No fields to update'}), 400
        sets.append('updated_at = CURRENT_TIMESTAMP')
        vals.append(cid)
        db.execute(f'UPDATE opsec_checklists SET {", ".join(sets)} WHERE id = ?', vals)
        db.commit()
        log_activity('checklist_updated', service='security_ops', detail=f'Updated checklist {cid}')
        row = db.execute('SELECT * FROM opsec_checklists WHERE id = ?', (cid,)).fetchone()
    d = dict(row)
    d['items'] = _jp(d.get('items'))
    return jsonify(d)


@security_opsec_bp.route('/opsec/checklists/seed', methods=['POST'])
def api_checklists_seed():
    created = 0
    with db_session() as db:
        for cl in BUILTIN_CHECKLISTS:
            exists = db.execute(
                'SELECT id FROM opsec_checklists WHERE title = ?', (cl['title'],)
            ).fetchone()
            if exists:
                continue
            db.execute(
                '''INSERT INTO opsec_checklists (title, category, items, score, status)
                   VALUES (?,?,?,?,?)''',
                (cl['title'], cl['category'], json.dumps(cl['items']), 0, 'active')
            )
            created += 1
        db.commit()
        if created:
            log_activity('checklists_seeded', service='security_ops',
                         detail=f'Seeded {created} default checklists')
    return jsonify({'status': 'seeded', 'created': created}), 201


# ═══════════════════════════════════════════════════════════════════
#  THREAT MATRIX
# ═══════════════════════════════════════════════════════════════════

@security_opsec_bp.route('/threat-matrix')
def api_threat_matrix_list():
    status = request.args.get('status')
    clauses, params = [], []
    if status:
        clauses.append('status = ?')
        params.append(status)
    where = f'WHERE {" AND ".join(clauses)}' if clauses else ''
    with db_session() as db:
        rows = db.execute(
            f'SELECT * FROM threat_matrix {where} ORDER BY risk_score DESC, threat_name', params
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d['risk_score'] = (d.get('likelihood') or 0) * (d.get('impact') or 0)
        out.append(d)
    return jsonify(out)


@security_opsec_bp.route('/threat-matrix', methods=['POST'])
def api_threat_matrix_create():
    data = request.get_json() or {}
    if not data.get('threat_name'):
        return jsonify({'error': 'Threat name required'}), 400
    likelihood = data.get('likelihood', 1)
    impact = data.get('impact', 1)
    risk_score = likelihood * impact
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO threat_matrix
               (threat_name, threat_type, likelihood, impact, risk_score, vulnerability,
                countermeasure, status, assigned_to, review_date)
               VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (data['threat_name'], data.get('threat_type', 'human'),
             likelihood, impact, risk_score,
             data.get('vulnerability', ''), data.get('countermeasure', ''),
             data.get('status', 'active'), data.get('assigned_to', ''),
             data.get('review_date', ''))
        )
        db.commit()
        log_activity('threat_created', service='security_ops', detail=data['threat_name'])
        row = db.execute('SELECT * FROM threat_matrix WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@security_opsec_bp.route('/threat-matrix/<int:tid>', methods=['PUT'])
def api_threat_matrix_update(tid):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT id FROM threat_matrix WHERE id = ?', (tid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        allowed = ['threat_name', 'threat_type', 'likelihood', 'impact', 'vulnerability',
                    'countermeasure', 'status', 'assigned_to', 'review_date']
        sets, vals = [], []
        for col in allowed:
            if col in data:
                sets.append(f'{col} = ?')
                vals.append(data[col])
        # Recompute risk_score
        if 'likelihood' in data or 'impact' in data:
            cur_row = db.execute('SELECT likelihood, impact FROM threat_matrix WHERE id = ?', (tid,)).fetchone()
            lk = data.get('likelihood', cur_row['likelihood'])
            imp = data.get('impact', cur_row['impact'])
            sets.append('risk_score = ?')
            vals.append(lk * imp)
        if not sets:
            return jsonify({'error': 'No fields to update'}), 400
        sets.append('updated_at = CURRENT_TIMESTAMP')
        vals.append(tid)
        db.execute(f'UPDATE threat_matrix SET {", ".join(sets)} WHERE id = ?', vals)
        db.commit()
        log_activity('threat_updated', service='security_ops', detail=f'Updated threat {tid}')
        row = db.execute('SELECT * FROM threat_matrix WHERE id = ?', (tid,)).fetchone()
    return jsonify(dict(row))


@security_opsec_bp.route('/threat-matrix/<int:tid>', methods=['DELETE'])
def api_threat_matrix_delete(tid):
    with db_session() as db:
        existing = db.execute('SELECT id, threat_name FROM threat_matrix WHERE id = ?', (tid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM threat_matrix WHERE id = ?', (tid,))
        db.commit()
        log_activity('threat_deleted', service='security_ops', detail=existing['threat_name'])
    return jsonify({'status': 'deleted'})


# ═══════════════════════════════════════════════════════════════════
#  OBSERVATION POSTS
# ═══════════════════════════════════════════════════════════════════

@security_opsec_bp.route('/observation-posts')
def api_observation_posts_list():
    status = request.args.get('status')
    clauses, params = [], []
    if status:
        clauses.append('status = ?')
        params.append(status)
    where = f'WHERE {" AND ".join(clauses)}' if clauses else ''
    with db_session() as db:
        rows = db.execute(
            f'SELECT * FROM observation_posts {where} ORDER BY name', params
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d['sectors'] = _jp(d.get('sectors'))
        d['equipment'] = _jp(d.get('equipment'))
        out.append(d)
    return jsonify(out)


@security_opsec_bp.route('/observation-posts', methods=['POST'])
def api_observation_posts_create():
    data = request.get_json() or {}
    if not data.get('name'):
        return jsonify({'error': 'Name required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO observation_posts
               (name, location, coordinates, type, fields_of_fire, dead_space,
                sectors, equipment, communication, status, assigned_to, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (data['name'], data.get('location', ''), data.get('coordinates', ''),
             data.get('type', 'fixed'), data.get('fields_of_fire', ''),
             data.get('dead_space', ''),
             json.dumps(data.get('sectors', [])),
             json.dumps(data.get('equipment', [])),
             data.get('communication', ''), data.get('status', 'planned'),
             data.get('assigned_to', ''), data.get('notes', ''))
        )
        db.commit()
        log_activity('op_created', service='security_ops', detail=data['name'])
        row = db.execute('SELECT * FROM observation_posts WHERE id = ?', (cur.lastrowid,)).fetchone()
    d = dict(row)
    d['sectors'] = _jp(d.get('sectors'))
    d['equipment'] = _jp(d.get('equipment'))
    return jsonify(d), 201


@security_opsec_bp.route('/observation-posts/<int:pid>', methods=['PUT'])
def api_observation_posts_update(pid):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT id FROM observation_posts WHERE id = ?', (pid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        allowed = ['name', 'location', 'coordinates', 'type', 'fields_of_fire', 'dead_space',
                    'sectors', 'equipment', 'communication', 'status', 'assigned_to', 'notes']
        sets, vals = [], []
        for col in allowed:
            if col in data:
                sets.append(f'{col} = ?')
                if col in ('sectors', 'equipment'):
                    vals.append(json.dumps(data[col]) if isinstance(data[col], list) else data[col])
                else:
                    vals.append(data[col])
        if not sets:
            return jsonify({'error': 'No fields to update'}), 400
        sets.append('updated_at = CURRENT_TIMESTAMP')
        vals.append(pid)
        db.execute(f'UPDATE observation_posts SET {", ".join(sets)} WHERE id = ?', vals)
        db.commit()
        log_activity('op_updated', service='security_ops', detail=f'Updated post {pid}')
        row = db.execute('SELECT * FROM observation_posts WHERE id = ?', (pid,)).fetchone()
    d = dict(row)
    d['sectors'] = _jp(d.get('sectors'))
    d['equipment'] = _jp(d.get('equipment'))
    return jsonify(d)


# ═══════════════════════════════════════════════════════════════════
#  OP LOG ENTRIES
# ═══════════════════════════════════════════════════════════════════

@security_opsec_bp.route('/op-log')
def api_op_log_list():
    post_id = request.args.get('post_id', type=int)
    category = request.args.get('category')
    clauses, params = [], []
    if post_id:
        clauses.append('post_id = ?')
        params.append(post_id)
    if category:
        clauses.append('category = ?')
        params.append(category)
    where = f'WHERE {" AND ".join(clauses)}' if clauses else ''
    with db_session() as db:
        rows = db.execute(
            f'SELECT * FROM op_log_entries {where} ORDER BY entry_time DESC', params
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@security_opsec_bp.route('/op-log', methods=['POST'])
def api_op_log_create():
    data = request.get_json() or {}
    if not data.get('description'):
        return jsonify({'error': 'Description required'}), 400
    entry_time = data.get('entry_time', datetime.utcnow().isoformat())
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO op_log_entries
               (post_id, observer, entry_time, category, direction, distance,
                description, threat_level, action_taken, reported_to)
               VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (data.get('post_id'), data.get('observer', ''), entry_time,
             data.get('category', 'other'), data.get('direction', ''),
             data.get('distance', ''), data['description'],
             data.get('threat_level', 'none'), data.get('action_taken', ''),
             data.get('reported_to', ''))
        )
        db.commit()
        log_activity('op_log_entry', service='security_ops',
                     detail=f'{data.get("category", "other")}: {data["description"][:80]}')
        row = db.execute('SELECT * FROM op_log_entries WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@security_opsec_bp.route('/op-log/summary')
def api_op_log_summary():
    with db_session() as db:
        by_category = db.execute(
            'SELECT category, COUNT(*) as count FROM op_log_entries GROUP BY category'
        ).fetchall()
        by_threat = db.execute(
            'SELECT threat_level, COUNT(*) as count FROM op_log_entries GROUP BY threat_level'
        ).fetchall()
        recent = db.execute(
            'SELECT * FROM op_log_entries ORDER BY entry_time DESC LIMIT 10'
        ).fetchall()
    return jsonify({
        'entries_by_category': {r['category']: r['count'] for r in by_category},
        'entries_by_threat_level': {r['threat_level']: r['count'] for r in by_threat},
        'total_entries': sum(r['count'] for r in by_category),
        'recent_activity': [dict(r) for r in recent]
    })


# ═══════════════════════════════════════════════════════════════════
#  SIGNATURE ASSESSMENTS
# ═══════════════════════════════════════════════════════════════════

@security_opsec_bp.route('/signatures')
def api_signatures_list():
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM signature_assessments ORDER BY assessment_date DESC'
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d['visual_signatures'] = _jp(d.get('visual_signatures'))
        d['audio_signatures'] = _jp(d.get('audio_signatures'))
        d['electronic_signatures'] = _jp(d.get('electronic_signatures'))
        d['thermal_signatures'] = _jp(d.get('thermal_signatures'))
        out.append(d)
    return jsonify(out)


@security_opsec_bp.route('/signatures', methods=['POST'])
def api_signatures_create():
    data = request.get_json() or {}
    if not data.get('location'):
        return jsonify({'error': 'Location required'}), 400
    # Compute overall score from signature intensities (lower = better)
    overall = _compute_sig_score(data)
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO signature_assessments
               (location, assessment_date, visual_signatures, audio_signatures,
                electronic_signatures, thermal_signatures, overall_score,
                recommendations, assessed_by, status)
               VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (data['location'],
             data.get('assessment_date', date.today().isoformat()),
             json.dumps(data.get('visual_signatures', [])),
             json.dumps(data.get('audio_signatures', [])),
             json.dumps(data.get('electronic_signatures', [])),
             json.dumps(data.get('thermal_signatures', [])),
             overall,
             data.get('recommendations', ''), data.get('assessed_by', ''),
             data.get('status', 'draft'))
        )
        db.commit()
        log_activity('signature_assessed', service='security_ops', detail=data['location'])
        row = db.execute('SELECT * FROM signature_assessments WHERE id = ?', (cur.lastrowid,)).fetchone()
    d = dict(row)
    for col in ('visual_signatures', 'audio_signatures', 'electronic_signatures', 'thermal_signatures'):
        d[col] = _jp(d.get(col))
    return jsonify(d), 201


@security_opsec_bp.route('/signatures/<int:sid>', methods=['PUT'])
def api_signatures_update(sid):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT id FROM signature_assessments WHERE id = ?', (sid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        json_cols = ('visual_signatures', 'audio_signatures', 'electronic_signatures', 'thermal_signatures')
        allowed = ['location', 'assessment_date'] + list(json_cols) + [
            'overall_score', 'recommendations', 'assessed_by', 'status']
        sets, vals = [], []
        for col in allowed:
            if col in data:
                sets.append(f'{col} = ?')
                if col in json_cols:
                    vals.append(json.dumps(data[col]) if isinstance(data[col], list) else data[col])
                else:
                    vals.append(data[col])
        # Recompute overall score if any signatures changed
        sig_changed = any(c in data for c in json_cols)
        if sig_changed:
            score = _compute_sig_score(data)
            sets.append('overall_score = ?')
            vals.append(score)
        if not sets:
            return jsonify({'error': 'No fields to update'}), 400
        sets.append('updated_at = CURRENT_TIMESTAMP')
        vals.append(sid)
        db.execute(f'UPDATE signature_assessments SET {", ".join(sets)} WHERE id = ?', vals)
        db.commit()
        log_activity('signature_updated', service='security_ops', detail=f'Updated assessment {sid}')
        row = db.execute('SELECT * FROM signature_assessments WHERE id = ?', (sid,)).fetchone()
    d = dict(row)
    for col in json_cols:
        d[col] = _jp(d.get(col))
    return jsonify(d)


@security_opsec_bp.route('/signatures/guide')
def api_signatures_guide():
    return jsonify(SIGNATURE_GUIDE)


def _compute_sig_score(data):
    """Compute overall signature score 0-100 (lower = better concealment).
    Averages intensity values across all signature types."""
    all_intensities = []
    for key in ('visual_signatures', 'audio_signatures', 'electronic_signatures', 'thermal_signatures'):
        sigs = data.get(key, [])
        if isinstance(sigs, list):
            for s in sigs:
                if isinstance(s, dict) and 'intensity_1_5' in s:
                    all_intensities.append(s['intensity_1_5'])
    if not all_intensities:
        return 0
    avg = sum(all_intensities) / len(all_intensities)
    return round((avg / 5.0) * 100)


# ═══════════════════════════════════════════════════════════════════
#  NIGHT OPERATIONS
# ═══════════════════════════════════════════════════════════════════

@security_opsec_bp.route('/night-ops')
def api_night_ops_list():
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM night_ops_plans ORDER BY operation_date DESC'
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d['movement_routes'] = _jp(d.get('movement_routes'))
        d['rally_points'] = _jp(d.get('rally_points'))
        d['signals'] = _jo(d.get('signals'))
        out.append(d)
    return jsonify(out)


@security_opsec_bp.route('/night-ops', methods=['POST'])
def api_night_ops_create():
    data = request.get_json() or {}
    if not data.get('name'):
        return jsonify({'error': 'Name required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO night_ops_plans
               (name, operation_date, moonrise, moonset, moon_phase, moon_illumination,
                ambient_light_level, dark_adaptation_minutes, nvg_required,
                movement_routes, rally_points, signals, notes, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (data['name'], data.get('operation_date', ''),
             data.get('moonrise', ''), data.get('moonset', ''),
             data.get('moon_phase', ''), data.get('moon_illumination', 0),
             data.get('ambient_light_level', 'moonless'),
             data.get('dark_adaptation_minutes', 30),
             1 if data.get('nvg_required') else 0,
             json.dumps(data.get('movement_routes', [])),
             json.dumps(data.get('rally_points', [])),
             json.dumps(data.get('signals', {})),
             data.get('notes', ''), data.get('status', 'draft'))
        )
        db.commit()
        log_activity('night_op_created', service='security_ops', detail=data['name'])
        row = db.execute('SELECT * FROM night_ops_plans WHERE id = ?', (cur.lastrowid,)).fetchone()
    d = dict(row)
    d['movement_routes'] = _jp(d.get('movement_routes'))
    d['rally_points'] = _jp(d.get('rally_points'))
    d['signals'] = _jo(d.get('signals'))
    return jsonify(d), 201


@security_opsec_bp.route('/night-ops/<int:nid>', methods=['PUT'])
def api_night_ops_update(nid):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT id FROM night_ops_plans WHERE id = ?', (nid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        json_arr_cols = ('movement_routes', 'rally_points')
        json_obj_cols = ('signals',)
        allowed = ['name', 'operation_date', 'moonrise', 'moonset', 'moon_phase',
                    'moon_illumination', 'ambient_light_level', 'dark_adaptation_minutes',
                    'nvg_required', 'movement_routes', 'rally_points', 'signals',
                    'notes', 'status']
        sets, vals = [], []
        for col in allowed:
            if col in data:
                sets.append(f'{col} = ?')
                if col in json_arr_cols:
                    vals.append(json.dumps(data[col]) if isinstance(data[col], list) else data[col])
                elif col in json_obj_cols:
                    vals.append(json.dumps(data[col]) if isinstance(data[col], dict) else data[col])
                elif col == 'nvg_required':
                    vals.append(1 if data[col] else 0)
                else:
                    vals.append(data[col])
        if not sets:
            return jsonify({'error': 'No fields to update'}), 400
        sets.append('updated_at = CURRENT_TIMESTAMP')
        vals.append(nid)
        db.execute(f'UPDATE night_ops_plans SET {", ".join(sets)} WHERE id = ?', vals)
        db.commit()
        log_activity('night_op_updated', service='security_ops', detail=f'Updated plan {nid}')
        row = db.execute('SELECT * FROM night_ops_plans WHERE id = ?', (nid,)).fetchone()
    d = dict(row)
    d['movement_routes'] = _jp(d.get('movement_routes'))
    d['rally_points'] = _jp(d.get('rally_points'))
    d['signals'] = _jo(d.get('signals'))
    return jsonify(d)


@security_opsec_bp.route('/night-ops/conditions')
def api_night_ops_conditions():
    """Simplified lunar/night conditions calculator."""
    date_str = request.args.get('date', date.today().isoformat())
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    try:
        target = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        target = datetime.utcnow()
    # Simplified lunar phase calculation (Metonic cycle approximation)
    known_new_moon = datetime(2024, 1, 11, 11, 57)  # Known new moon reference
    lunar_cycle = 29.53058770576
    days_since = (target - known_new_moon).total_seconds() / 86400.0
    phase_fraction = (days_since % lunar_cycle) / lunar_cycle
    illumination = round((1 - math.cos(2 * math.pi * phase_fraction)) / 2 * 100)
    if phase_fraction < 0.03 or phase_fraction > 0.97:
        phase_name = 'new_moon'
        ambient = 'moonless'
    elif phase_fraction < 0.22:
        phase_name = 'waxing_crescent'
        ambient = 'starlight'
    elif phase_fraction < 0.28:
        phase_name = 'first_quarter'
        ambient = 'quarter_moon'
    elif phase_fraction < 0.47:
        phase_name = 'waxing_gibbous'
        ambient = 'half_moon'
    elif phase_fraction < 0.53:
        phase_name = 'full_moon'
        ambient = 'full_moon'
    elif phase_fraction < 0.72:
        phase_name = 'waning_gibbous'
        ambient = 'half_moon'
    elif phase_fraction < 0.78:
        phase_name = 'last_quarter'
        ambient = 'quarter_moon'
    else:
        phase_name = 'waning_crescent'
        ambient = 'starlight'
    # Darkness hours approximation based on latitude and date
    darkness_hours = 12.0
    if lat is not None:
        day_of_year = target.timetuple().tm_yday
        declination = 23.44 * math.sin(math.radians((360 / 365) * (day_of_year - 81)))
        lat_rad = math.radians(min(max(lat, -66), 66))
        dec_rad = math.radians(declination)
        cos_ha = -math.tan(lat_rad) * math.tan(dec_rad)
        cos_ha = max(-1, min(1, cos_ha))
        daylight = (2 * math.degrees(math.acos(cos_ha))) / 15.0
        darkness_hours = round(24.0 - daylight, 1)
    nvg_recommended = illumination < 25
    result = {
        'date': date_str,
        'moon_phase': phase_name,
        'moon_illumination_pct': illumination,
        'ambient_light_level': ambient,
        'estimated_darkness_hours': darkness_hours,
        'nvg_recommended': nvg_recommended,
        'dark_adaptation_minutes': 30,
        'notes': 'Best operations window: 2+ hours after sunset, before moonrise'
    }
    if lat is not None and lng is not None:
        result['lat'] = lat
        result['lng'] = lng
    return jsonify(result)


# ═══════════════════════════════════════════════════════════════════
#  CBRN EQUIPMENT
# ═══════════════════════════════════════════════════════════════════

@security_opsec_bp.route('/cbrn/equipment')
def api_cbrn_equipment_list():
    eq_type = request.args.get('type')
    clauses, params = [], []
    if eq_type:
        clauses.append('equipment_type = ?')
        params.append(eq_type)
    where = f'WHERE {" AND ".join(clauses)}' if clauses else ''
    with db_session() as db:
        rows = db.execute(
            f'SELECT * FROM cbrn_equipment {where} ORDER BY equipment_name', params
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@security_opsec_bp.route('/cbrn/equipment', methods=['POST'])
def api_cbrn_equipment_create():
    data = request.get_json() or {}
    if not data.get('equipment_name'):
        return jsonify({'error': 'Equipment name required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO cbrn_equipment
               (equipment_name, equipment_type, model, serial_number,
                calibration_date, calibration_due, condition, assigned_to,
                location, quantity, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            (data['equipment_name'], data.get('equipment_type', 'detector'),
             data.get('model', ''), data.get('serial_number', ''),
             data.get('calibration_date', ''), data.get('calibration_due', ''),
             data.get('condition', 'serviceable'), data.get('assigned_to', ''),
             data.get('location', ''), data.get('quantity', 1),
             data.get('notes', ''))
        )
        db.commit()
        log_activity('cbrn_equip_created', service='security_ops', detail=data['equipment_name'])
        row = db.execute('SELECT * FROM cbrn_equipment WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@security_opsec_bp.route('/cbrn/equipment/<int:eid>', methods=['PUT'])
def api_cbrn_equipment_update(eid):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT id FROM cbrn_equipment WHERE id = ?', (eid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        allowed = ['equipment_name', 'equipment_type', 'model', 'serial_number',
                    'calibration_date', 'calibration_due', 'condition', 'assigned_to',
                    'location', 'quantity', 'notes']
        sets, vals = [], []
        for col in allowed:
            if col in data:
                sets.append(f'{col} = ?')
                vals.append(data[col])
        if not sets:
            return jsonify({'error': 'No fields to update'}), 400
        sets.append('updated_at = CURRENT_TIMESTAMP')
        vals.append(eid)
        db.execute(f'UPDATE cbrn_equipment SET {", ".join(sets)} WHERE id = ?', vals)
        db.commit()
        log_activity('cbrn_equip_updated', service='security_ops', detail=f'Updated equipment {eid}')
        row = db.execute('SELECT * FROM cbrn_equipment WHERE id = ?', (eid,)).fetchone()
    return jsonify(dict(row))


# ═══════════════════════════════════════════════════════════════════
#  CBRN PROCEDURES
# ═══════════════════════════════════════════════════════════════════

@security_opsec_bp.route('/cbrn/procedures')
def api_cbrn_procedures_list():
    proc_type = request.args.get('type')
    agent = request.args.get('agent')
    clauses, params = [], []
    if proc_type:
        clauses.append('procedure_type = ?')
        params.append(proc_type)
    if agent:
        clauses.append('threat_agent = ?')
        params.append(agent)
    where = f'WHERE {" AND ".join(clauses)}' if clauses else ''
    with db_session() as db:
        rows = db.execute(
            f'SELECT * FROM cbrn_procedures {where} ORDER BY title', params
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d['steps'] = _jp(d.get('steps'))
        d['equipment_required'] = _jp(d.get('equipment_required'))
        out.append(d)
    return jsonify(out)


@security_opsec_bp.route('/cbrn/procedures', methods=['POST'])
def api_cbrn_procedures_create():
    data = request.get_json() or {}
    if not data.get('title'):
        return jsonify({'error': 'Title required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO cbrn_procedures
               (title, procedure_type, threat_agent, mopp_level, steps,
                equipment_required, time_estimate_minutes, warnings, reference, is_builtin)
               VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (data['title'], data.get('procedure_type', 'detection'),
             data.get('threat_agent', 'all'), data.get('mopp_level', 0),
             json.dumps(data.get('steps', [])),
             json.dumps(data.get('equipment_required', [])),
             data.get('time_estimate_minutes', 0),
             data.get('warnings', ''), data.get('reference', ''),
             1 if data.get('is_builtin') else 0)
        )
        db.commit()
        log_activity('cbrn_proc_created', service='security_ops', detail=data['title'])
        row = db.execute('SELECT * FROM cbrn_procedures WHERE id = ?', (cur.lastrowid,)).fetchone()
    d = dict(row)
    d['steps'] = _jp(d.get('steps'))
    d['equipment_required'] = _jp(d.get('equipment_required'))
    return jsonify(d), 201


@security_opsec_bp.route('/cbrn/procedures/seed', methods=['POST'])
def api_cbrn_procedures_seed():
    created = 0
    with db_session() as db:
        for proc in BUILTIN_CBRN:
            exists = db.execute(
                'SELECT id FROM cbrn_procedures WHERE title = ?', (proc['title'],)
            ).fetchone()
            if exists:
                continue
            db.execute(
                '''INSERT INTO cbrn_procedures
                   (title, procedure_type, threat_agent, mopp_level, steps,
                    equipment_required, time_estimate_minutes, warnings, is_builtin)
                   VALUES (?,?,?,?,?,?,?,?,?)''',
                (proc['title'], proc['procedure_type'], proc['threat_agent'],
                 proc['mopp_level'], json.dumps(proc['steps']),
                 json.dumps(proc['equipment_required']),
                 proc['time_estimate_minutes'], proc['warnings'], 1)
            )
            created += 1
        db.commit()
        if created:
            log_activity('cbrn_procs_seeded', service='security_ops',
                         detail=f'Seeded {created} built-in procedures')
    return jsonify({'status': 'seeded', 'created': created}), 201


@security_opsec_bp.route('/cbrn/calculators')
def api_cbrn_calculators():
    calc = request.args.get('calc', '')
    if calc == 'ki_dosage':
        return jsonify({'calculator': 'ki_dosage', 'dosages': [
            {'age_group': 'Adults (18+)', 'dose_mg': 130, 'tablets_130mg': 1},
            {'age_group': 'Adolescents (12-17, 150+ lbs)', 'dose_mg': 130, 'tablets_130mg': 1},
            {'age_group': 'Children (3-12)', 'dose_mg': 65, 'tablets_130mg': 0.5},
            {'age_group': 'Children (1-3)', 'dose_mg': 32, 'tablets_130mg': 0.25},
            {'age_group': 'Infants (1 month - 1 year)', 'dose_mg': 16, 'tablets_130mg': 0.125},
            {'age_group': 'Neonates (birth - 1 month)', 'dose_mg': 16, 'tablets_130mg': 0.125}
        ], 'notes': 'Administer within 4 hours of exposure. Single daily dose unless directed otherwise.'})
    elif calc == 'fallout_decay':
        initial_rate = request.args.get('initial_rate', 1000, type=float)
        hours = request.args.get('hours', 7, type=float)
        if hours <= 0:
            return jsonify({'error': 'Hours must be positive'}), 400
        # 7-10 rule: R(t) = R(1) * t^(-1.2)
        decay_factor = hours ** (-1.2)
        current_rate = round(initial_rate * decay_factor, 2)
        return jsonify({
            'calculator': 'fallout_decay',
            'initial_rate': initial_rate,
            'hours_elapsed': hours,
            'decay_factor': round(decay_factor, 6),
            'current_rate': current_rate,
            'rule': '7-10 rule: Every 7x increase in time yields 10x decrease in radiation',
            'milestones': [
                {'hours': 7, 'factor': round(7 ** -1.2, 4), 'rate': round(initial_rate * 7 ** -1.2, 2)},
                {'hours': 49, 'factor': round(49 ** -1.2, 4), 'rate': round(initial_rate * 49 ** -1.2, 2)},
                {'hours': 343, 'factor': round(343 ** -1.2, 4), 'rate': round(initial_rate * 343 ** -1.2, 2)}
            ]
        })
    elif calc == 'decon_time':
        agent_type = request.args.get('agent_type', 'chemical')
        personnel = request.args.get('personnel', 1, type=int)
        base_times = {'chemical': 20, 'biological': 30, 'radiological': 15, 'nuclear': 25}
        base = base_times.get(agent_type, 20)
        # Each additional person adds ~60% of base time (parallel processing)
        total = base + max(0, personnel - 1) * round(base * 0.6)
        return jsonify({
            'calculator': 'decon_time',
            'agent_type': agent_type,
            'personnel_count': personnel,
            'base_time_minutes': base,
            'estimated_total_minutes': total,
            'notes': f'Estimate for {personnel} personnel. Assumes trained decon team with proper equipment.'
        })
    else:
        return jsonify({
            'available_calculators': ['ki_dosage', 'fallout_decay', 'decon_time'],
            'usage': 'Pass ?calc=<name> to use a calculator'
        })


# ═══════════════════════════════════════════════════════════════════
#  EMP HARDENING INVENTORY
# ═══════════════════════════════════════════════════════════════════

@security_opsec_bp.route('/emp/inventory')
def api_emp_inventory_list():
    category = request.args.get('category')
    protected = request.args.get('protected')
    clauses, params = [], []
    if category:
        clauses.append('category = ?')
        params.append(category)
    if protected is not None and protected != '':
        clauses.append('is_protected = ?')
        params.append(int(protected))
    where = f'WHERE {" AND ".join(clauses)}' if clauses else ''
    with db_session() as db:
        rows = db.execute(
            f'SELECT * FROM emp_inventory {where} ORDER BY priority, item_name', params
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@security_opsec_bp.route('/emp/inventory', methods=['POST'])
def api_emp_inventory_create():
    data = request.get_json() or {}
    if not data.get('item_name'):
        return jsonify({'error': 'Item name required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO emp_inventory
               (item_name, category, description, protection_method, is_protected,
                grid_dependent, manual_alternative, priority, location, quantity,
                tested_date, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (data['item_name'], data.get('category', 'critical_spare'),
             data.get('description', ''), data.get('protection_method', ''),
             1 if data.get('is_protected') else 0,
             1 if data.get('grid_dependent', True) else 0,
             data.get('manual_alternative', ''),
             data.get('priority', 'medium'), data.get('location', ''),
             data.get('quantity', 1), data.get('tested_date', ''),
             data.get('notes', ''))
        )
        db.commit()
        log_activity('emp_item_created', service='security_ops', detail=data['item_name'])
        row = db.execute('SELECT * FROM emp_inventory WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@security_opsec_bp.route('/emp/inventory/<int:eid>', methods=['PUT'])
def api_emp_inventory_update(eid):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT id FROM emp_inventory WHERE id = ?', (eid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        allowed = ['item_name', 'category', 'description', 'protection_method',
                    'is_protected', 'grid_dependent', 'manual_alternative', 'priority',
                    'location', 'quantity', 'tested_date', 'notes']
        sets, vals = [], []
        for col in allowed:
            if col in data:
                sets.append(f'{col} = ?')
                if col in ('is_protected', 'grid_dependent'):
                    vals.append(1 if data[col] else 0)
                else:
                    vals.append(data[col])
        if not sets:
            return jsonify({'error': 'No fields to update'}), 400
        sets.append('updated_at = CURRENT_TIMESTAMP')
        vals.append(eid)
        db.execute(f'UPDATE emp_inventory SET {", ".join(sets)} WHERE id = ?', vals)
        db.commit()
        log_activity('emp_item_updated', service='security_ops', detail=f'Updated item {eid}')
        row = db.execute('SELECT * FROM emp_inventory WHERE id = ?', (eid,)).fetchone()
    return jsonify(dict(row))


@security_opsec_bp.route('/emp/inventory/<int:eid>', methods=['DELETE'])
def api_emp_inventory_delete(eid):
    with db_session() as db:
        existing = db.execute('SELECT id, item_name FROM emp_inventory WHERE id = ?', (eid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM emp_inventory WHERE id = ?', (eid,))
        db.commit()
        log_activity('emp_item_deleted', service='security_ops', detail=existing['item_name'])
    return jsonify({'status': 'deleted'})


@security_opsec_bp.route('/emp/analysis')
def api_emp_analysis():
    with db_session() as db:
        total = db.execute('SELECT COUNT(*) as c FROM emp_inventory').fetchone()['c']
        protected = db.execute('SELECT COUNT(*) as c FROM emp_inventory WHERE is_protected = 1').fetchone()['c']
        unprotected = total - protected
        grid_dep = db.execute('SELECT COUNT(*) as c FROM emp_inventory WHERE grid_dependent = 1').fetchone()['c']
        by_category = db.execute(
            'SELECT category, COUNT(*) as count FROM emp_inventory GROUP BY category'
        ).fetchall()
        by_priority = db.execute(
            'SELECT priority, COUNT(*) as count, '
            'SUM(CASE WHEN is_protected = 1 THEN 1 ELSE 0 END) as protected_count '
            'FROM emp_inventory GROUP BY priority'
        ).fetchall()
        has_alt = db.execute(
            "SELECT COUNT(*) as c FROM emp_inventory WHERE manual_alternative != '' AND manual_alternative IS NOT NULL"
        ).fetchone()['c']
    alt_coverage = round((has_alt / total) * 100) if total > 0 else 0
    protection_pct = round((protected / total) * 100) if total > 0 else 0
    return jsonify({
        'total_items': total,
        'protected': protected,
        'unprotected': unprotected,
        'protection_percentage': protection_pct,
        'grid_dependent': grid_dep,
        'manual_alternatives_coverage_pct': alt_coverage,
        'by_category': {r['category']: r['count'] for r in by_category},
        'by_priority': [{
            'priority': r['priority'],
            'count': r['count'],
            'protected': r['protected_count']
        } for r in by_priority]
    })


# ═══════════════════════════════════════════════════════════════════
#  MODULE SUMMARY
# ═══════════════════════════════════════════════════════════════════

@security_opsec_bp.route('/summary')
def api_security_ops_summary():
    with db_session() as db:
        # Compartments
        compartments = db.execute(
            'SELECT COUNT(*) as c FROM opsec_compartments WHERE status = ?', ('active',)
        ).fetchone()['c']
        # Threat matrix by risk tier
        threats = db.execute('SELECT * FROM threat_matrix WHERE status = ?', ('active',)).fetchall()
        high_risk = sum(1 for t in threats if (t['likelihood'] or 0) * (t['impact'] or 0) >= 15)
        med_risk = sum(1 for t in threats if 6 <= (t['likelihood'] or 0) * (t['impact'] or 0) < 15)
        low_risk = sum(1 for t in threats if (t['likelihood'] or 0) * (t['impact'] or 0) < 6)
        # OP activity (last 24h)
        recent_logs = db.execute(
            "SELECT COUNT(*) as c FROM op_log_entries WHERE entry_time >= datetime('now', '-1 day')"
        ).fetchone()['c']
        active_posts = db.execute(
            'SELECT COUNT(*) as c FROM observation_posts WHERE status = ?', ('active',)
        ).fetchone()['c']
        # Signature scores
        sig_rows = db.execute(
            'SELECT overall_score FROM signature_assessments WHERE status = ?', ('final',)
        ).fetchall()
        avg_sig = round(sum(r['overall_score'] for r in sig_rows) / len(sig_rows)) if sig_rows else 0
        # CBRN readiness
        cbrn_total = db.execute('SELECT COUNT(*) as c FROM cbrn_equipment').fetchone()['c']
        cbrn_serviceable = db.execute(
            'SELECT COUNT(*) as c FROM cbrn_equipment WHERE condition = ?', ('serviceable',)
        ).fetchone()['c']
        cbrn_overdue = db.execute(
            "SELECT COUNT(*) as c FROM cbrn_equipment WHERE calibration_due != '' AND calibration_due < date('now')"
        ).fetchone()['c']
        # EMP protection
        emp_total = db.execute('SELECT COUNT(*) as c FROM emp_inventory').fetchone()['c']
        emp_protected = db.execute(
            'SELECT COUNT(*) as c FROM emp_inventory WHERE is_protected = 1'
        ).fetchone()['c']
        emp_pct = round((emp_protected / emp_total) * 100) if emp_total > 0 else 0
        # Checklist average score
        cl_rows = db.execute(
            'SELECT score FROM opsec_checklists WHERE status = ?', ('active',)
        ).fetchall()
        avg_checklist = round(sum(r['score'] for r in cl_rows) / len(cl_rows)) if cl_rows else 0
    return jsonify({
        'active_compartments': compartments,
        'threat_matrix': {
            'total_active': len(threats),
            'high_risk': high_risk,
            'medium_risk': med_risk,
            'low_risk': low_risk
        },
        'observation_posts': {
            'active': active_posts,
            'log_entries_24h': recent_logs
        },
        'signature_avg_score': avg_sig,
        'checklist_avg_score': avg_checklist,
        'cbrn': {
            'total_equipment': cbrn_total,
            'serviceable': cbrn_serviceable,
            'calibration_overdue': cbrn_overdue
        },
        'emp_protection_pct': emp_pct
    })
