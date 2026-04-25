"""Specialized Modules — Supply caches, pets, youth programs, end-of-life plans,
procurement, intel, fabrication, badges, awards, seasonal events, legal docs,
drones, flights, fitness, and content packs."""

import json
import logging
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify
from db import db_session, log_activity

_log = logging.getLogger(__name__)

specialized_modules_bp = Blueprint('specialized_modules', __name__,
                                   url_prefix='/api/specialized')

_PETS_ALLOWED_FIELDS = frozenset({'name', 'species', 'breed', 'age_years', 'weight_lbs',
                                   'microchip_id', 'medical_conditions', 'medications',
                                   'vaccination_dates', 'food_type', 'daily_food_amount',
                                   'food_supply_days', 'veterinarian', 'evacuation_carrier',
                                   'temperament', 'special_needs', 'photo_ref', 'status', 'notes'})
_END_OF_LIFE_PLANS_ALLOWED_FIELDS = frozenset({'person', 'plan_type', 'wishes', 'medical_directives', 'organ_donor',
                                               'body_disposition', 'memorial_wishes', 'important_documents',
                                               'digital_accounts', 'beneficiaries', 'executor', 'attorney',
                                               'insurance_info', 'last_updated_by', 'status', 'notes'})
_PROCUREMENT_LISTS_ALLOWED_FIELDS = frozenset({'name', 'list_type', 'priority', 'items', 'budget', 'spent',
                                               'supplier', 'due_date', 'assigned_to', 'status', 'notes'})
_INTEL_COLLECTION_ALLOWED_FIELDS = frozenset({'title', 'intel_type', 'priority_info_req', 'source',
                                              'source_reliability', 'info_credibility', 'classification',
                                              'date_collected', 'location', 'summary', 'raw_data', 'analysis',
                                              'actionable', 'dissemination', 'expiry_date', 'status'})
_FABRICATION_PROJECTS_ALLOWED_FIELDS = frozenset({'name', 'project_type', 'description', 'file_path', 'material',
                                                  'material_amount', 'printer_model', 'print_settings',
                                                  'estimated_time_hours', 'actual_time_hours', 'copies_made',
                                                  'priority', 'status', 'notes'})
_SUPPLY_CACHES_ALLOWED_FIELDS = frozenset({'name', 'cache_type', 'location_description', 'gps_coords',
                                           'access_instructions', 'concealment_method', 'container_type',
                                           'contents', 'last_checked', 'condition', 'known_by',
                                           'expiration_date', 'security_level', 'notes'})
_YOUTH_PROGRAMS_ALLOWED_FIELDS = frozenset({'name', 'program_type', 'age_range', 'description', 'curriculum',
                                            'materials_needed', 'instructor', 'schedule', 'participants',
                                            'skills_taught', 'progress_notes', 'status'})
_BADGES_ALLOWED_FIELDS = frozenset({'name', 'category', 'description', 'icon', 'criteria', 'points', 'rarity'})
_SEASONAL_EVENTS_ALLOWED_FIELDS = frozenset({'name', 'event_type', 'date', 'recurrence', 'description',
                                             'tasks', 'reminders', 'category', 'completed', 'notes'})
_LEGAL_DOCUMENTS_ALLOWED_FIELDS = frozenset({'title', 'doc_type', 'person', 'issuing_authority',
                                             'document_number', 'issue_date', 'expiry_date', 'file_path',
                                             'storage_location', 'renewal_reminder', 'notes'})
_DRONES_ALLOWED_FIELDS = frozenset({'name', 'drone_type', 'manufacturer', 'model', 'serial_number',
                                    'registration', 'weight_grams', 'max_flight_time_min',
                                    'max_range_m', 'camera_specs', 'battery_count', 'battery_type',
                                    'firmware_version', 'total_flights', 'total_flight_hours',
                                    'last_flight', 'condition', 'notes'})
_CONTENT_PACKS_ALLOWED_FIELDS = frozenset({'name', 'pack_type', 'version', 'author', 'description',
                                           'contents_manifest', 'size_bytes', 'install_date',
                                           'source_url', 'checksum', 'status', 'notes'})


# ── helpers ────────────────────────────────────────────────────────────

def _jp(val):
    """Parse JSON array column."""
    try:
        return json.loads(val)
    except Exception:
        return []


def _jo(val):
    """Parse JSON object column."""
    try:
        return json.loads(val)
    except Exception:
        return {}


def _row(r, json_arrays=None, json_objects=None):
    """Convert sqlite Row to dict, parsing specified JSON columns."""
    d = dict(r)
    for k in (json_arrays or []):
        if k in d and d[k]:
            d[k] = _jp(d[k])
    for k in (json_objects or []):
        if k in d and d[k]:
            d[k] = _jo(d[k])
    return d


def _paginate():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
    except (ValueError, TypeError):
        limit = 50
    try:
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        offset = 0
    return limit, offset


# ═══════════════════════════════════════════════════════════════════════
#  SUPPLY CACHES
# ═══════════════════════════════════════════════════════════════════════

CACHE_JSON_ARRAYS = ['contents', 'known_by']


@specialized_modules_bp.route('/caches')
def api_caches_list():
    limit, offset = _paginate()
    clauses, params = [], []
    ct = request.args.get('type')
    if ct:
        clauses.append('cache_type = ?')
        params.append(ct)
    sec = request.args.get('security')
    if sec:
        clauses.append('security_level = ?')
        params.append(sec)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ''
    params += [limit, offset]
    with db_session() as db:
        rows = db.execute(
            f'SELECT * FROM supply_caches{where} ORDER BY updated_at DESC LIMIT ? OFFSET ?',
            params
        ).fetchall()
    return jsonify([_row(r, json_arrays=CACHE_JSON_ARRAYS) for r in rows])


@specialized_modules_bp.route('/caches', methods=['POST'])
def api_caches_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO supply_caches
               (name, cache_type, location_description, gps_coords,
                access_instructions, concealment_method, container_type,
                contents, last_checked, condition, known_by,
                expiration_date, security_level, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('cache_type', 'general'),
             data.get('location_description', ''), data.get('gps_coords', ''),
             data.get('access_instructions', ''), data.get('concealment_method', ''),
             data.get('container_type', ''),
             json.dumps(data.get('contents', [])),
             data.get('last_checked', ''), data.get('condition', 'good'),
             json.dumps(data.get('known_by', [])),
             data.get('expiration_date', ''), data.get('security_level', 'standard'),
             data.get('notes', ''))
        )
        db.commit()
        row = db.execute('SELECT * FROM supply_caches WHERE id = ?',
                         (cur.lastrowid,)).fetchone()
    log_activity('cache_created', service='specialized', detail=name)
    return jsonify(_row(row, json_arrays=CACHE_JSON_ARRAYS)), 201


@specialized_modules_bp.route('/caches/<int:cid>')
def api_caches_get(cid):
    with db_session() as db:
        row = db.execute('SELECT * FROM supply_caches WHERE id = ?', (cid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(_row(row, json_arrays=CACHE_JSON_ARRAYS))


@specialized_modules_bp.route('/caches/<int:cid>', methods=['PUT'])
def api_caches_update(cid):
    data = request.get_json() or {}
    allowed = _SUPPLY_CACHES_ALLOWED_FIELDS
    sets, vals = [], []
    for k in allowed:
        if k in data:
            v = data[k]
            sets.append(f'{k} = ?')
            vals.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append('updated_at = CURRENT_TIMESTAMP')
    vals.append(cid)
    with db_session() as db:
        db.execute(f"UPDATE supply_caches SET {', '.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM supply_caches WHERE id = ?', (cid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    log_activity('cache_updated', service='specialized', detail=row['name'])
    return jsonify(_row(row, json_arrays=CACHE_JSON_ARRAYS))


@specialized_modules_bp.route('/caches/<int:cid>', methods=['DELETE'])
def api_caches_delete(cid):
    with db_session() as db:
        row = db.execute('SELECT name FROM supply_caches WHERE id = ?', (cid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM supply_caches WHERE id = ?', (cid,))
        db.commit()
    log_activity('cache_deleted', service='specialized', detail=row['name'])
    return jsonify({'deleted': True})


# ═══════════════════════════════════════════════════════════════════════
#  PETS & COMPANION ANIMALS
# ═══════════════════════════════════════════════════════════════════════

PET_JSON_ARRAYS = ['medical_conditions', 'medications']
PET_JSON_OBJECTS = ['vaccination_dates']


@specialized_modules_bp.route('/pets')
def api_pets_list():
    limit, offset = _paginate()
    clauses, params = [], []
    sp = request.args.get('species')
    if sp:
        clauses.append('species = ?')
        params.append(sp)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ''
    params += [limit, offset]
    with db_session() as db:
        rows = db.execute(
            f'SELECT * FROM pets{where} ORDER BY updated_at DESC LIMIT ? OFFSET ?',
            params
        ).fetchall()
    return jsonify([_row(r, json_arrays=PET_JSON_ARRAYS, json_objects=PET_JSON_OBJECTS) for r in rows])


@specialized_modules_bp.route('/pets', methods=['POST'])
def api_pets_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO pets
               (name, species, breed, age_years, weight_lbs, microchip_id,
                medical_conditions, medications, vaccination_dates, food_type,
                daily_food_amount, food_supply_days, veterinarian,
                evacuation_carrier, temperament, special_needs, photo_ref,
                status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('species', 'dog'), data.get('breed', ''),
             data.get('age_years', 0), data.get('weight_lbs', 0),
             data.get('microchip_id', ''),
             json.dumps(data.get('medical_conditions', [])),
             json.dumps(data.get('medications', [])),
             json.dumps(data.get('vaccination_dates', {})),
             data.get('food_type', ''), data.get('daily_food_amount', ''),
             data.get('food_supply_days', 0), data.get('veterinarian', ''),
             data.get('evacuation_carrier', ''), data.get('temperament', ''),
             data.get('special_needs', ''), data.get('photo_ref', ''),
             data.get('status', 'active'), data.get('notes', ''))
        )
        db.commit()
        row = db.execute('SELECT * FROM pets WHERE id = ?',
                         (cur.lastrowid,)).fetchone()
    log_activity('pet_created', service='specialized', detail=name)
    return jsonify(_row(row, json_arrays=PET_JSON_ARRAYS, json_objects=PET_JSON_OBJECTS)), 201


@specialized_modules_bp.route('/pets/<int:pid>')
def api_pets_get(pid):
    with db_session() as db:
        row = db.execute('SELECT * FROM pets WHERE id = ?', (pid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(_row(row, json_arrays=PET_JSON_ARRAYS, json_objects=PET_JSON_OBJECTS))


@specialized_modules_bp.route('/pets/<int:pid>', methods=['PUT'])
def api_pets_update(pid):
    data = request.get_json() or {}
    allowed = _PETS_ALLOWED_FIELDS
    sets, vals = [], []
    for k in allowed:
        if k in data:
            v = data[k]
            sets.append(f'{k} = ?')
            vals.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append('updated_at = CURRENT_TIMESTAMP')
    vals.append(pid)
    with db_session() as db:
        db.execute(f"UPDATE pets SET {', '.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM pets WHERE id = ?', (pid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    log_activity('pet_updated', service='specialized', detail=row['name'])
    return jsonify(_row(row, json_arrays=PET_JSON_ARRAYS, json_objects=PET_JSON_OBJECTS))


@specialized_modules_bp.route('/pets/<int:pid>', methods=['DELETE'])
def api_pets_delete(pid):
    with db_session() as db:
        row = db.execute('SELECT name FROM pets WHERE id = ?', (pid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM pets WHERE id = ?', (pid,))
        db.commit()
    log_activity('pet_deleted', service='specialized', detail=row['name'])
    return jsonify({'deleted': True})


@specialized_modules_bp.route('/pets/food-status')
def api_pets_food_status():
    with db_session() as db:
        rows = db.execute(
            "SELECT id, name, species, food_type, food_supply_days FROM pets WHERE status = 'active' ORDER BY food_supply_days ASC"
        ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        days = d['food_supply_days'] or 0
        if days <= 7:
            d['urgency'] = 'critical'
        elif days <= 14:
            d['urgency'] = 'low'
        else:
            d['urgency'] = 'ok'
        results.append(d)
    return jsonify(results)


# ═══════════════════════════════════════════════════════════════════════
#  YOUTH PROGRAMS
# ═══════════════════════════════════════════════════════════════════════

YOUTH_JSON_ARRAYS = ['curriculum', 'materials_needed', 'participants', 'skills_taught']


@specialized_modules_bp.route('/youth')
def api_youth_list():
    limit, offset = _paginate()
    clauses, params = [], []
    pt = request.args.get('type')
    if pt:
        clauses.append('program_type = ?')
        params.append(pt)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ''
    params += [limit, offset]
    with db_session() as db:
        rows = db.execute(
            f'SELECT * FROM youth_programs{where} ORDER BY updated_at DESC LIMIT ? OFFSET ?',
            params
        ).fetchall()
    return jsonify([_row(r, json_arrays=YOUTH_JSON_ARRAYS) for r in rows])


@specialized_modules_bp.route('/youth', methods=['POST'])
def api_youth_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO youth_programs
               (name, program_type, age_range, description, curriculum,
                materials_needed, instructor, schedule, participants,
                skills_taught, progress_notes, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('program_type', 'education'),
             data.get('age_range', ''), data.get('description', ''),
             json.dumps(data.get('curriculum', [])),
             json.dumps(data.get('materials_needed', [])),
             data.get('instructor', ''), data.get('schedule', ''),
             json.dumps(data.get('participants', [])),
             json.dumps(data.get('skills_taught', [])),
             data.get('progress_notes', ''), data.get('status', 'active'))
        )
        db.commit()
        row = db.execute('SELECT * FROM youth_programs WHERE id = ?',
                         (cur.lastrowid,)).fetchone()
    log_activity('youth_program_created', service='specialized', detail=name)
    return jsonify(_row(row, json_arrays=YOUTH_JSON_ARRAYS)), 201


@specialized_modules_bp.route('/youth/<int:yid>')
def api_youth_get(yid):
    with db_session() as db:
        row = db.execute('SELECT * FROM youth_programs WHERE id = ?', (yid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(_row(row, json_arrays=YOUTH_JSON_ARRAYS))


@specialized_modules_bp.route('/youth/<int:yid>', methods=['PUT'])
def api_youth_update(yid):
    data = request.get_json() or {}
    allowed = _YOUTH_PROGRAMS_ALLOWED_FIELDS
    sets, vals = [], []
    for k in allowed:
        if k in data:
            v = data[k]
            sets.append(f'{k} = ?')
            vals.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append('updated_at = CURRENT_TIMESTAMP')
    vals.append(yid)
    with db_session() as db:
        db.execute(f"UPDATE youth_programs SET {', '.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM youth_programs WHERE id = ?', (yid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    log_activity('youth_program_updated', service='specialized', detail=row['name'])
    return jsonify(_row(row, json_arrays=YOUTH_JSON_ARRAYS))


@specialized_modules_bp.route('/youth/<int:yid>', methods=['DELETE'])
def api_youth_delete(yid):
    with db_session() as db:
        row = db.execute('SELECT name FROM youth_programs WHERE id = ?', (yid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM youth_programs WHERE id = ?', (yid,))
        db.commit()
    log_activity('youth_program_deleted', service='specialized', detail=row['name'])
    return jsonify({'deleted': True})


# ═══════════════════════════════════════════════════════════════════════
#  END-OF-LIFE PLANS
# ═══════════════════════════════════════════════════════════════════════

EOL_JSON_ARRAYS = ['important_documents', 'digital_accounts', 'beneficiaries']


@specialized_modules_bp.route('/eol')
def api_eol_list():
    limit, offset = _paginate()
    clauses, params = [], []
    person = request.args.get('person')
    if person:
        clauses.append('person = ?')
        params.append(person)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ''
    params += [limit, offset]
    with db_session() as db:
        rows = db.execute(
            f'SELECT * FROM end_of_life_plans{where} ORDER BY updated_at DESC LIMIT ? OFFSET ?',
            params
        ).fetchall()
    return jsonify([_row(r, json_arrays=EOL_JSON_ARRAYS) for r in rows])


@specialized_modules_bp.route('/eol', methods=['POST'])
def api_eol_create():
    data = request.get_json() or {}
    person = (data.get('person') or '').strip()
    if not person:
        return jsonify({'error': 'person is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO end_of_life_plans
               (person, plan_type, wishes, medical_directives, organ_donor,
                body_disposition, memorial_wishes, important_documents,
                digital_accounts, beneficiaries, executor, attorney,
                insurance_info, last_updated_by, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (person, data.get('plan_type', 'general'),
             data.get('wishes', ''), data.get('medical_directives', ''),
             1 if data.get('organ_donor') else 0,
             data.get('body_disposition', ''), data.get('memorial_wishes', ''),
             json.dumps(data.get('important_documents', [])),
             json.dumps(data.get('digital_accounts', [])),
             json.dumps(data.get('beneficiaries', [])),
             data.get('executor', ''), data.get('attorney', ''),
             data.get('insurance_info', ''), data.get('last_updated_by', ''),
             data.get('status', 'draft'), data.get('notes', ''))
        )
        db.commit()
        row = db.execute('SELECT * FROM end_of_life_plans WHERE id = ?',
                         (cur.lastrowid,)).fetchone()
    log_activity('eol_plan_created', service='specialized', detail=person)
    return jsonify(_row(row, json_arrays=EOL_JSON_ARRAYS)), 201


@specialized_modules_bp.route('/eol/<int:eid>')
def api_eol_get(eid):
    with db_session() as db:
        row = db.execute('SELECT * FROM end_of_life_plans WHERE id = ?', (eid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(_row(row, json_arrays=EOL_JSON_ARRAYS))


@specialized_modules_bp.route('/eol/<int:eid>', methods=['PUT'])
def api_eol_update(eid):
    data = request.get_json() or {}
    allowed = _END_OF_LIFE_PLANS_ALLOWED_FIELDS
    sets, vals = [], []
    for k in allowed:
        if k in data:
            v = data[k]
            if k == 'organ_donor':
                sets.append(f'{k} = ?')
                vals.append(1 if v else 0)
            else:
                sets.append(f'{k} = ?')
                vals.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append('updated_at = CURRENT_TIMESTAMP')
    vals.append(eid)
    with db_session() as db:
        db.execute(f"UPDATE end_of_life_plans SET {', '.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM end_of_life_plans WHERE id = ?', (eid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    log_activity('eol_plan_updated', service='specialized', detail=row['person'])
    return jsonify(_row(row, json_arrays=EOL_JSON_ARRAYS))


@specialized_modules_bp.route('/eol/<int:eid>', methods=['DELETE'])
def api_eol_delete(eid):
    with db_session() as db:
        row = db.execute('SELECT person FROM end_of_life_plans WHERE id = ?', (eid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM end_of_life_plans WHERE id = ?', (eid,))
        db.commit()
    log_activity('eol_plan_deleted', service='specialized', detail=row['person'])
    return jsonify({'deleted': True})


# ═══════════════════════════════════════════════════════════════════════
#  PROCUREMENT LISTS
# ═══════════════════════════════════════════════════════════════════════

PROCUREMENT_JSON_ARRAYS = ['items']


@specialized_modules_bp.route('/procurement')
def api_procurement_list():
    limit, offset = _paginate()
    clauses, params = [], []
    status = request.args.get('status')
    if status:
        clauses.append('status = ?')
        params.append(status)
    priority = request.args.get('priority')
    if priority:
        clauses.append('priority = ?')
        params.append(priority)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ''
    params += [limit, offset]
    with db_session() as db:
        rows = db.execute(
            f'SELECT * FROM procurement_lists{where} ORDER BY updated_at DESC LIMIT ? OFFSET ?',
            params
        ).fetchall()
    return jsonify([_row(r, json_arrays=PROCUREMENT_JSON_ARRAYS) for r in rows])


@specialized_modules_bp.route('/procurement', methods=['POST'])
def api_procurement_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO procurement_lists
               (name, list_type, priority, items, budget, spent,
                supplier, due_date, assigned_to, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('list_type', 'shopping'),
             data.get('priority', 'medium'),
             json.dumps(data.get('items', [])),
             data.get('budget', 0), data.get('spent', 0),
             data.get('supplier', ''), data.get('due_date', ''),
             data.get('assigned_to', ''), data.get('status', 'pending'),
             data.get('notes', ''))
        )
        db.commit()
        row = db.execute('SELECT * FROM procurement_lists WHERE id = ?',
                         (cur.lastrowid,)).fetchone()
    log_activity('procurement_created', service='specialized', detail=name)
    return jsonify(_row(row, json_arrays=PROCUREMENT_JSON_ARRAYS)), 201


@specialized_modules_bp.route('/procurement/<int:pid>')
def api_procurement_get(pid):
    with db_session() as db:
        row = db.execute('SELECT * FROM procurement_lists WHERE id = ?', (pid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(_row(row, json_arrays=PROCUREMENT_JSON_ARRAYS))


@specialized_modules_bp.route('/procurement/<int:pid>', methods=['PUT'])
def api_procurement_update(pid):
    data = request.get_json() or {}
    allowed = _PROCUREMENT_LISTS_ALLOWED_FIELDS
    sets, vals = [], []
    for k in allowed:
        if k in data:
            v = data[k]
            sets.append(f'{k} = ?')
            vals.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append('updated_at = CURRENT_TIMESTAMP')
    vals.append(pid)
    with db_session() as db:
        db.execute(f"UPDATE procurement_lists SET {', '.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM procurement_lists WHERE id = ?', (pid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    log_activity('procurement_updated', service='specialized', detail=row['name'])
    return jsonify(_row(row, json_arrays=PROCUREMENT_JSON_ARRAYS))


@specialized_modules_bp.route('/procurement/<int:pid>', methods=['DELETE'])
def api_procurement_delete(pid):
    with db_session() as db:
        row = db.execute('SELECT name FROM procurement_lists WHERE id = ?', (pid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM procurement_lists WHERE id = ?', (pid,))
        db.commit()
    log_activity('procurement_deleted', service='specialized', detail=row['name'])
    return jsonify({'deleted': True})


@specialized_modules_bp.route('/procurement/budget-summary')
def api_procurement_budget_summary():
    with db_session() as db:
        row = db.execute(
            'SELECT COUNT(*) as total_lists, COALESCE(SUM(budget),0) as total_budget, COALESCE(SUM(spent),0) as total_spent FROM procurement_lists'
        ).fetchone()
    d = dict(row)
    d['remaining'] = d['total_budget'] - d['total_spent']
    d['utilization_pct'] = round((d['total_spent'] / d['total_budget'] * 100), 1) if d['total_budget'] > 0 else 0
    return jsonify(d)


# ═══════════════════════════════════════════════════════════════════════
#  INTEL COLLECTION
# ═══════════════════════════════════════════════════════════════════════

INTEL_JSON_ARRAYS = ['dissemination']


@specialized_modules_bp.route('/intel')
def api_intel_list():
    limit, offset = _paginate()
    clauses, params = [], []
    it = request.args.get('type')
    if it:
        clauses.append('intel_type = ?')
        params.append(it)
    cl = request.args.get('classification')
    if cl:
        clauses.append('classification = ?')
        params.append(cl)
    st = request.args.get('status')
    if st:
        clauses.append('status = ?')
        params.append(st)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ''
    params += [limit, offset]
    with db_session() as db:
        rows = db.execute(
            f'SELECT * FROM intel_collection{where} ORDER BY updated_at DESC LIMIT ? OFFSET ?',
            params
        ).fetchall()
    return jsonify([_row(r, json_arrays=INTEL_JSON_ARRAYS) for r in rows])


@specialized_modules_bp.route('/intel', methods=['POST'])
def api_intel_create():
    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'error': 'title is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO intel_collection
               (title, intel_type, priority_info_req, source,
                source_reliability, info_credibility, classification,
                date_collected, location, summary, raw_data, analysis,
                actionable, dissemination, expiry_date, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (title, data.get('intel_type', 'humint'),
             data.get('priority_info_req', ''), data.get('source', ''),
             data.get('source_reliability', 'unknown'),
             data.get('info_credibility', 'unknown'),
             data.get('classification', 'unclassified'),
             data.get('date_collected', ''), data.get('location', ''),
             data.get('summary', ''), data.get('raw_data', ''),
             data.get('analysis', ''),
             1 if data.get('actionable') else 0,
             json.dumps(data.get('dissemination', [])),
             data.get('expiry_date', ''), data.get('status', 'new'))
        )
        db.commit()
        row = db.execute('SELECT * FROM intel_collection WHERE id = ?',
                         (cur.lastrowid,)).fetchone()
    log_activity('intel_created', service='specialized', detail=title)
    return jsonify(_row(row, json_arrays=INTEL_JSON_ARRAYS)), 201


@specialized_modules_bp.route('/intel/<int:iid>')
def api_intel_get(iid):
    with db_session() as db:
        row = db.execute('SELECT * FROM intel_collection WHERE id = ?', (iid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(_row(row, json_arrays=INTEL_JSON_ARRAYS))


@specialized_modules_bp.route('/intel/<int:iid>', methods=['PUT'])
def api_intel_update(iid):
    data = request.get_json() or {}
    allowed = _INTEL_COLLECTION_ALLOWED_FIELDS
    sets, vals = [], []
    for k in allowed:
        if k in data:
            v = data[k]
            if k == 'actionable':
                sets.append(f'{k} = ?')
                vals.append(1 if v else 0)
            else:
                sets.append(f'{k} = ?')
                vals.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append('updated_at = CURRENT_TIMESTAMP')
    vals.append(iid)
    with db_session() as db:
        db.execute(f"UPDATE intel_collection SET {', '.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM intel_collection WHERE id = ?', (iid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    log_activity('intel_updated', service='specialized', detail=row['title'])
    return jsonify(_row(row, json_arrays=INTEL_JSON_ARRAYS))


@specialized_modules_bp.route('/intel/<int:iid>', methods=['DELETE'])
def api_intel_delete(iid):
    with db_session() as db:
        row = db.execute('SELECT title FROM intel_collection WHERE id = ?', (iid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM intel_collection WHERE id = ?', (iid,))
        db.commit()
    log_activity('intel_deleted', service='specialized', detail=row['title'])
    return jsonify({'deleted': True})


@specialized_modules_bp.route('/intel/summary')
def api_intel_summary():
    with db_session() as db:
        by_type = db.execute(
            'SELECT intel_type, COUNT(*) as count FROM intel_collection GROUP BY intel_type'
        ).fetchall()
        actionable = db.execute(
            'SELECT COUNT(*) as count FROM intel_collection WHERE actionable = 1'
        ).fetchone()
        pending = db.execute(
            "SELECT COUNT(*) as count FROM intel_collection WHERE status = 'new' OR analysis = ''"
        ).fetchone()
    return jsonify({
        'by_type': {r['intel_type']: r['count'] for r in by_type},
        'actionable_count': actionable['count'],
        'pending_analysis': pending['count'],
        'total': sum(r['count'] for r in by_type)
    })


# ═══════════════════════════════════════════════════════════════════════
#  FABRICATION PROJECTS
# ═══════════════════════════════════════════════════════════════════════

FAB_JSON_OBJECTS = ['print_settings']


@specialized_modules_bp.route('/fabrication')
def api_fabrication_list():
    limit, offset = _paginate()
    clauses, params = [], []
    ft = request.args.get('type')
    if ft:
        clauses.append('project_type = ?')
        params.append(ft)
    st = request.args.get('status')
    if st:
        clauses.append('status = ?')
        params.append(st)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ''
    params += [limit, offset]
    with db_session() as db:
        rows = db.execute(
            f'SELECT * FROM fabrication_projects{where} ORDER BY updated_at DESC LIMIT ? OFFSET ?',
            params
        ).fetchall()
    return jsonify([_row(r, json_objects=FAB_JSON_OBJECTS) for r in rows])


@specialized_modules_bp.route('/fabrication', methods=['POST'])
def api_fabrication_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO fabrication_projects
               (name, project_type, description, file_path, material,
                material_amount, printer_model, print_settings,
                estimated_time_hours, actual_time_hours, copies_made,
                priority, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('project_type', '3d_print'),
             data.get('description', ''), data.get('file_path', ''),
             data.get('material', 'pla'), data.get('material_amount', ''),
             data.get('printer_model', ''),
             json.dumps(data.get('print_settings', {})),
             data.get('estimated_time_hours', 0),
             data.get('actual_time_hours', 0),
             data.get('copies_made', 0),
             data.get('priority', 'medium'), data.get('status', 'queued'),
             data.get('notes', ''))
        )
        db.commit()
        row = db.execute('SELECT * FROM fabrication_projects WHERE id = ?',
                         (cur.lastrowid,)).fetchone()
    log_activity('fabrication_created', service='specialized', detail=name)
    return jsonify(_row(row, json_objects=FAB_JSON_OBJECTS)), 201


@specialized_modules_bp.route('/fabrication/<int:fid>')
def api_fabrication_get(fid):
    with db_session() as db:
        row = db.execute('SELECT * FROM fabrication_projects WHERE id = ?', (fid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(_row(row, json_objects=FAB_JSON_OBJECTS))


@specialized_modules_bp.route('/fabrication/<int:fid>', methods=['PUT'])
def api_fabrication_update(fid):
    data = request.get_json() or {}
    allowed = _FABRICATION_PROJECTS_ALLOWED_FIELDS
    sets, vals = [], []
    for k in allowed:
        if k in data:
            v = data[k]
            sets.append(f'{k} = ?')
            vals.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append('updated_at = CURRENT_TIMESTAMP')
    vals.append(fid)
    with db_session() as db:
        db.execute(f"UPDATE fabrication_projects SET {', '.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM fabrication_projects WHERE id = ?', (fid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    log_activity('fabrication_updated', service='specialized', detail=row['name'])
    return jsonify(_row(row, json_objects=FAB_JSON_OBJECTS))


@specialized_modules_bp.route('/fabrication/<int:fid>', methods=['DELETE'])
def api_fabrication_delete(fid):
    with db_session() as db:
        row = db.execute('SELECT name FROM fabrication_projects WHERE id = ?', (fid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM fabrication_projects WHERE id = ?', (fid,))
        db.commit()
    log_activity('fabrication_deleted', service='specialized', detail=row['name'])
    return jsonify({'deleted': True})


# ═══════════════════════════════════════════════════════════════════════
#  BADGES & ACHIEVEMENTS
# ═══════════════════════════════════════════════════════════════════════

@specialized_modules_bp.route('/badges')
def api_badges_list():
    limit, offset = _paginate()
    clauses, params = [], []
    cat = request.args.get('category')
    if cat:
        clauses.append('category = ?')
        params.append(cat)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ''
    params += [limit, offset]
    with db_session() as db:
        rows = db.execute(
            f'SELECT * FROM badges{where} ORDER BY created_at DESC LIMIT ? OFFSET ?',
            params
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@specialized_modules_bp.route('/badges', methods=['POST'])
def api_badges_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO badges
               (name, category, description, icon, criteria, points, rarity)
               VALUES (?,?,?,?,?,?,?)''',
            (name, data.get('category', 'general'),
             data.get('description', ''), data.get('icon', ''),
             data.get('criteria', ''), data.get('points', 10),
             data.get('rarity', 'common'))
        )
        db.commit()
        row = db.execute('SELECT * FROM badges WHERE id = ?',
                         (cur.lastrowid,)).fetchone()
    log_activity('badge_created', service='specialized', detail=name)
    return jsonify(dict(row)), 201


@specialized_modules_bp.route('/badges/<int:bid>')
def api_badges_get(bid):
    with db_session() as db:
        row = db.execute('SELECT * FROM badges WHERE id = ?', (bid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(dict(row))


@specialized_modules_bp.route('/badges/<int:bid>', methods=['PUT'])
def api_badges_update(bid):
    data = request.get_json() or {}
    allowed = _BADGES_ALLOWED_FIELDS
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            vals.append(data[k])
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    vals.append(bid)
    with db_session() as db:
        r = db.execute(f"UPDATE badges SET {', '.join(sets)} WHERE id = ?", vals)
        if r.rowcount == 0:
            return jsonify({'error': 'Not found'}), 404
        db.commit()
        row = db.execute('SELECT * FROM badges WHERE id = ?', (bid,)).fetchone()
    log_activity('badge_updated', service='specialized', detail=row['name'])
    return jsonify(dict(row))


@specialized_modules_bp.route('/badges/<int:bid>', methods=['DELETE'])
def api_badges_delete(bid):
    with db_session() as db:
        row = db.execute('SELECT name FROM badges WHERE id = ?', (bid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM badge_awards WHERE badge_id = ?', (bid,))
        db.execute('DELETE FROM badges WHERE id = ?', (bid,))
        db.commit()
    log_activity('badge_deleted', service='specialized', detail=row['name'])
    return jsonify({'deleted': True})


DEFAULT_BADGES = [
    {'name': 'First Inventory Item', 'category': 'milestone', 'description': 'Added your first inventory item', 'icon': 'package', 'criteria': 'Add 1 inventory item', 'points': 10, 'rarity': 'common'},
    {'name': 'Week of Logs', 'category': 'consistency', 'description': 'Logged activity for 7 consecutive days', 'icon': 'calendar-check', 'criteria': '7 days of logs', 'points': 25, 'rarity': 'uncommon'},
    {'name': 'Fire Starter', 'category': 'skill', 'description': 'Completed fire-starting training', 'icon': 'flame', 'criteria': 'Complete fire training module', 'points': 30, 'rarity': 'uncommon'},
    {'name': 'Water Wise', 'category': 'skill', 'description': 'Set up water purification system', 'icon': 'droplets', 'criteria': 'Configure water management', 'points': 30, 'rarity': 'uncommon'},
    {'name': 'Medical Ready', 'category': 'skill', 'description': 'Completed medical supply checklist', 'icon': 'heart-pulse', 'criteria': 'Full medical inventory', 'points': 40, 'rarity': 'rare'},
    {'name': 'Comms Check', 'category': 'skill', 'description': 'Configured communications plan', 'icon': 'radio', 'criteria': 'Set up comms module', 'points': 25, 'rarity': 'uncommon'},
    {'name': '100 Items', 'category': 'milestone', 'description': 'Tracked 100 inventory items', 'icon': 'boxes', 'criteria': 'Reach 100 items', 'points': 50, 'rarity': 'rare'},
    {'name': 'Night Watch', 'category': 'skill', 'description': 'Completed security watch schedule', 'icon': 'shield', 'criteria': 'Set up security rotation', 'points': 30, 'rarity': 'uncommon'},
    {'name': 'Green Thumb', 'category': 'skill', 'description': 'Started a garden plan', 'icon': 'sprout', 'criteria': 'Create garden module entry', 'points': 20, 'rarity': 'common'},
    {'name': 'Team Player', 'category': 'social', 'description': 'Added 5 contacts to your group', 'icon': 'users', 'criteria': '5 contacts added', 'points': 25, 'rarity': 'uncommon'},
]


@specialized_modules_bp.route('/badges/seed', methods=['POST'])
def api_badges_seed():
    with db_session() as db:
        count = db.execute('SELECT COUNT(*) as c FROM badges').fetchone()['c']
        if count > 0:
            return jsonify({'seeded': False, 'message': 'Badges already exist', 'count': count})
        for b in DEFAULT_BADGES:
            db.execute(
                'INSERT INTO badges (name, category, description, icon, criteria, points, rarity) VALUES (?,?,?,?,?,?,?)',
                (b['name'], b['category'], b['description'], b['icon'],
                 b['criteria'], b['points'], b['rarity'])
            )
        db.commit()
    log_activity('badges_seeded', service='specialized', detail=f'{len(DEFAULT_BADGES)} defaults')
    return jsonify({'seeded': True, 'count': len(DEFAULT_BADGES)}), 201


# ═══════════════════════════════════════════════════════════════════════
#  BADGE AWARDS
# ═══════════════════════════════════════════════════════════════════════

@specialized_modules_bp.route('/awards')
def api_awards_list():
    limit, offset = _paginate()
    clauses, params = [], []
    person = request.args.get('person')
    if person:
        clauses.append('ba.person = ?')
        params.append(person)
    badge_id = request.args.get('badge_id')
    if badge_id:
        # Bare ``int(badge_id)`` crashes the endpoint with a 500 on any
        # non-numeric query string. Coerce with a try/except and bail
        # with a clean 400 instead.
        try:
            badge_id_int = int(badge_id)
        except (TypeError, ValueError):
            return jsonify({'error': 'badge_id must be an integer'}), 400
        clauses.append('ba.badge_id = ?')
        params.append(badge_id_int)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ''
    params += [limit, offset]
    with db_session() as db:
        rows = db.execute(
            f'''SELECT ba.*, b.name as badge_name, b.icon, b.points, b.rarity
                FROM badge_awards ba
                LEFT JOIN badges b ON ba.badge_id = b.id
                {where}
                ORDER BY ba.created_at DESC LIMIT ? OFFSET ?''',
            params
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@specialized_modules_bp.route('/awards', methods=['POST'])
def api_awards_create():
    data = request.get_json() or {}
    badge_id = data.get('badge_id')
    person = (data.get('person') or '').strip()
    if not badge_id or not person:
        return jsonify({'error': 'badge_id and person are required'}), 400
    with db_session() as db:
        badge = db.execute('SELECT id, name FROM badges WHERE id = ?', (badge_id,)).fetchone()
        if not badge:
            return jsonify({'error': 'Badge not found'}), 404
        cur = db.execute(
            '''INSERT INTO badge_awards (badge_id, person, awarded_date, awarded_by, notes)
               VALUES (?,?,?,?,?)''',
            (badge_id, person,
             data.get('awarded_date', datetime.utcnow().strftime('%Y-%m-%d')),
             data.get('awarded_by', 'system'), data.get('notes', ''))
        )
        db.commit()
        row = db.execute(
            '''SELECT ba.*, b.name as badge_name, b.icon, b.points, b.rarity
               FROM badge_awards ba LEFT JOIN badges b ON ba.badge_id = b.id
               WHERE ba.id = ?''',
            (cur.lastrowid,)
        ).fetchone()
    log_activity('award_granted', service='specialized', detail=f'{person}: {badge["name"]}')
    return jsonify(dict(row)), 201


@specialized_modules_bp.route('/awards/<int:aid>')
def api_awards_get(aid):
    with db_session() as db:
        row = db.execute(
            '''SELECT ba.*, b.name as badge_name, b.icon, b.points, b.rarity
               FROM badge_awards ba LEFT JOIN badges b ON ba.badge_id = b.id
               WHERE ba.id = ?''',
            (aid,)
        ).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(dict(row))


@specialized_modules_bp.route('/awards/<int:aid>', methods=['DELETE'])
def api_awards_delete(aid):
    with db_session() as db:
        row = db.execute('SELECT person FROM badge_awards WHERE id = ?', (aid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM badge_awards WHERE id = ?', (aid,))
        db.commit()
    log_activity('award_revoked', service='specialized', detail=row['person'])
    return jsonify({'deleted': True})


@specialized_modules_bp.route('/awards/leaderboard')
def api_awards_leaderboard():
    with db_session() as db:
        rows = db.execute(
            '''SELECT ba.person, COUNT(*) as badge_count,
                      COALESCE(SUM(b.points), 0) as total_points
               FROM badge_awards ba
               LEFT JOIN badges b ON ba.badge_id = b.id
               GROUP BY ba.person
               ORDER BY total_points DESC'''
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# ═══════════════════════════════════════════════════════════════════════
#  SEASONAL EVENTS / CALENDAR
# ═══════════════════════════════════════════════════════════════════════

CALENDAR_JSON_ARRAYS = ['tasks', 'reminders']


@specialized_modules_bp.route('/calendar')
def api_calendar_list():
    limit, offset = _paginate()
    clauses, params = [], []
    cat = request.args.get('category')
    if cat:
        clauses.append('category = ?')
        params.append(cat)
    month = request.args.get('month')
    if month:
        clauses.append("date LIKE ?")
        params.append(f'%-{month.zfill(2)}-%')
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ''
    params += [limit, offset]
    with db_session() as db:
        rows = db.execute(
            f'SELECT * FROM seasonal_events{where} ORDER BY date ASC LIMIT ? OFFSET ?',
            params
        ).fetchall()
    return jsonify([_row(r, json_arrays=CALENDAR_JSON_ARRAYS) for r in rows])


@specialized_modules_bp.route('/calendar', methods=['POST'])
def api_calendar_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO seasonal_events
               (name, event_type, date, recurrence, description,
                tasks, reminders, category, completed, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('event_type', 'seasonal'),
             data.get('date', ''), data.get('recurrence', 'yearly'),
             data.get('description', ''),
             json.dumps(data.get('tasks', [])),
             json.dumps(data.get('reminders', [])),
             data.get('category', 'preparedness'),
             1 if data.get('completed') else 0,
             data.get('notes', ''))
        )
        db.commit()
        row = db.execute('SELECT * FROM seasonal_events WHERE id = ?',
                         (cur.lastrowid,)).fetchone()
    log_activity('calendar_event_created', service='specialized', detail=name)
    return jsonify(_row(row, json_arrays=CALENDAR_JSON_ARRAYS)), 201


@specialized_modules_bp.route('/calendar/<int:eid>')
def api_calendar_get(eid):
    with db_session() as db:
        row = db.execute('SELECT * FROM seasonal_events WHERE id = ?', (eid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(_row(row, json_arrays=CALENDAR_JSON_ARRAYS))


@specialized_modules_bp.route('/calendar/<int:eid>', methods=['PUT'])
def api_calendar_update(eid):
    data = request.get_json() or {}
    allowed = _SEASONAL_EVENTS_ALLOWED_FIELDS
    sets, vals = [], []
    for k in allowed:
        if k in data:
            v = data[k]
            if k == 'completed':
                sets.append(f'{k} = ?')
                vals.append(1 if v else 0)
            else:
                sets.append(f'{k} = ?')
                vals.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append('updated_at = CURRENT_TIMESTAMP')
    vals.append(eid)
    with db_session() as db:
        db.execute(f"UPDATE seasonal_events SET {', '.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM seasonal_events WHERE id = ?', (eid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    log_activity('calendar_event_updated', service='specialized', detail=row['name'])
    return jsonify(_row(row, json_arrays=CALENDAR_JSON_ARRAYS))


@specialized_modules_bp.route('/calendar/<int:eid>', methods=['DELETE'])
def api_calendar_delete(eid):
    with db_session() as db:
        row = db.execute('SELECT name FROM seasonal_events WHERE id = ?', (eid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM seasonal_events WHERE id = ?', (eid,))
        db.commit()
    log_activity('calendar_event_deleted', service='specialized', detail=row['name'])
    return jsonify({'deleted': True})


@specialized_modules_bp.route('/calendar/upcoming')
def api_calendar_upcoming():
    today = datetime.utcnow().strftime('%Y-%m-%d')
    cutoff = (datetime.utcnow() + timedelta(days=30)).strftime('%Y-%m-%d')
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM seasonal_events WHERE date >= ? AND date <= ? AND completed = 0 ORDER BY date ASC',
            (today, cutoff)
        ).fetchall()
    return jsonify([_row(r, json_arrays=CALENDAR_JSON_ARRAYS) for r in rows])


# ═══════════════════════════════════════════════════════════════════════
#  LEGAL DOCUMENTS
# ═══════════════════════════════════════════════════════════════════════

@specialized_modules_bp.route('/legal')
def api_legal_list():
    limit, offset = _paginate()
    clauses, params = [], []
    dt = request.args.get('type')
    if dt:
        clauses.append('doc_type = ?')
        params.append(dt)
    person = request.args.get('person')
    if person:
        clauses.append('person = ?')
        params.append(person)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ''
    params += [limit, offset]
    with db_session() as db:
        rows = db.execute(
            f'SELECT * FROM legal_documents{where} ORDER BY updated_at DESC LIMIT ? OFFSET ?',
            params
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@specialized_modules_bp.route('/legal', methods=['POST'])
def api_legal_create():
    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'error': 'title is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO legal_documents
               (title, doc_type, person, issuing_authority, document_number,
                issue_date, expiry_date, file_path, storage_location,
                renewal_reminder, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            (title, data.get('doc_type', 'general'),
             data.get('person', ''), data.get('issuing_authority', ''),
             data.get('document_number', ''), data.get('issue_date', ''),
             data.get('expiry_date', ''), data.get('file_path', ''),
             data.get('storage_location', ''),
             1 if data.get('renewal_reminder') else 0,
             data.get('notes', ''))
        )
        db.commit()
        row = db.execute('SELECT * FROM legal_documents WHERE id = ?',
                         (cur.lastrowid,)).fetchone()
    log_activity('legal_doc_created', service='specialized', detail=title)
    return jsonify(dict(row)), 201


@specialized_modules_bp.route('/legal/<int:lid>')
def api_legal_get(lid):
    with db_session() as db:
        row = db.execute('SELECT * FROM legal_documents WHERE id = ?', (lid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(dict(row))


@specialized_modules_bp.route('/legal/<int:lid>', methods=['PUT'])
def api_legal_update(lid):
    data = request.get_json() or {}
    allowed = _LEGAL_DOCUMENTS_ALLOWED_FIELDS
    sets, vals = [], []
    for k in allowed:
        if k in data:
            v = data[k]
            if k == 'renewal_reminder':
                sets.append(f'{k} = ?')
                vals.append(1 if v else 0)
            else:
                sets.append(f'{k} = ?')
                vals.append(v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append('updated_at = CURRENT_TIMESTAMP')
    vals.append(lid)
    with db_session() as db:
        db.execute(f"UPDATE legal_documents SET {', '.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM legal_documents WHERE id = ?', (lid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    log_activity('legal_doc_updated', service='specialized', detail=row['title'])
    return jsonify(dict(row))


@specialized_modules_bp.route('/legal/<int:lid>', methods=['DELETE'])
def api_legal_delete(lid):
    with db_session() as db:
        row = db.execute('SELECT title FROM legal_documents WHERE id = ?', (lid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM legal_documents WHERE id = ?', (lid,))
        db.commit()
    log_activity('legal_doc_deleted', service='specialized', detail=row['title'])
    return jsonify({'deleted': True})


@specialized_modules_bp.route('/legal/expiring')
def api_legal_expiring():
    today = datetime.utcnow().strftime('%Y-%m-%d')
    cutoff = (datetime.utcnow() + timedelta(days=90)).strftime('%Y-%m-%d')
    with db_session() as db:
        rows = db.execute(
            "SELECT * FROM legal_documents WHERE expiry_date != '' AND expiry_date >= ? AND expiry_date <= ? ORDER BY expiry_date ASC",
            (today, cutoff)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# ═══════════════════════════════════════════════════════════════════════
#  DRONES
# ═══════════════════════════════════════════════════════════════════════

@specialized_modules_bp.route('/drones')
def api_drones_list():
    limit, offset = _paginate()
    clauses, params = [], []
    dt = request.args.get('type')
    if dt:
        clauses.append('drone_type = ?')
        params.append(dt)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ''
    params += [limit, offset]
    with db_session() as db:
        rows = db.execute(
            f'SELECT * FROM drones{where} ORDER BY updated_at DESC LIMIT ? OFFSET ?',
            params
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@specialized_modules_bp.route('/drones', methods=['POST'])
def api_drones_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO drones
               (name, drone_type, manufacturer, model, serial_number,
                registration, weight_grams, max_flight_time_min, max_range_m,
                camera_specs, battery_count, battery_type, firmware_version,
                total_flights, total_flight_hours, last_flight, condition, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('drone_type', 'quadcopter'),
             data.get('manufacturer', ''), data.get('model', ''),
             data.get('serial_number', ''), data.get('registration', ''),
             data.get('weight_grams', 0), data.get('max_flight_time_min', 0),
             data.get('max_range_m', 0), data.get('camera_specs', ''),
             data.get('battery_count', 1), data.get('battery_type', ''),
             data.get('firmware_version', ''), data.get('total_flights', 0),
             data.get('total_flight_hours', 0), data.get('last_flight', ''),
             data.get('condition', 'operational'), data.get('notes', ''))
        )
        db.commit()
        row = db.execute('SELECT * FROM drones WHERE id = ?',
                         (cur.lastrowid,)).fetchone()
    log_activity('drone_created', service='specialized', detail=name)
    return jsonify(dict(row)), 201


@specialized_modules_bp.route('/drones/<int:did>')
def api_drones_get(did):
    with db_session() as db:
        row = db.execute('SELECT * FROM drones WHERE id = ?', (did,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(dict(row))


@specialized_modules_bp.route('/drones/<int:did>', methods=['PUT'])
def api_drones_update(did):
    data = request.get_json() or {}
    allowed = _DRONES_ALLOWED_FIELDS
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            vals.append(data[k])
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append('updated_at = CURRENT_TIMESTAMP')
    vals.append(did)
    with db_session() as db:
        db.execute(f"UPDATE drones SET {', '.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM drones WHERE id = ?', (did,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    log_activity('drone_updated', service='specialized', detail=row['name'])
    return jsonify(dict(row))


@specialized_modules_bp.route('/drones/<int:did>', methods=['DELETE'])
def api_drones_delete(did):
    with db_session() as db:
        row = db.execute('SELECT name FROM drones WHERE id = ?', (did,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM drone_flights WHERE drone_id = ?', (did,))
        db.execute('DELETE FROM drones WHERE id = ?', (did,))
        db.commit()
    log_activity('drone_deleted', service='specialized', detail=row['name'])
    return jsonify({'deleted': True})


# ═══════════════════════════════════════════════════════════════════════
#  DRONE FLIGHTS
# ═══════════════════════════════════════════════════════════════════════

FLIGHT_JSON_ARRAYS = ['media_captured']


@specialized_modules_bp.route('/flights')
def api_flights_list():
    limit, offset = _paginate()
    clauses, params = [], []
    drone_id = request.args.get('drone_id')
    if drone_id:
        try:
            drone_id_int = int(drone_id)
        except (TypeError, ValueError):
            return jsonify({'error': 'drone_id must be an integer'}), 400
        clauses.append('df.drone_id = ?')
        params.append(drone_id_int)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ''
    params += [limit, offset]
    with db_session() as db:
        rows = db.execute(
            f'''SELECT df.*, d.name as drone_name
                FROM drone_flights df
                LEFT JOIN drones d ON df.drone_id = d.id
                {where}
                ORDER BY df.created_at DESC LIMIT ? OFFSET ?''',
            params
        ).fetchall()
    return jsonify([_row(r, json_arrays=FLIGHT_JSON_ARRAYS) for r in rows])


@specialized_modules_bp.route('/drones/<int:did>/flights')
def api_drones_flights_nested(did):
    """Nested alias for `/flights?drone_id=<did>`.

    The frontend template (_tab_specialized_modules.html) constructs this
    nested path directly (`/drones/<id>/flights`), so expose it as an
    alias that routes through the existing filter logic. Added during the
    V8-06 hardening pass on 2026-04-24.
    """
    limit, offset = _paginate()
    with db_session() as db:
        rows = db.execute(
            '''SELECT df.*, d.name as drone_name
               FROM drone_flights df
               LEFT JOIN drones d ON df.drone_id = d.id
               WHERE df.drone_id = ?
               ORDER BY df.created_at DESC LIMIT ? OFFSET ?''',
            (did, limit, offset)
        ).fetchall()
    return jsonify([_row(r, json_arrays=FLIGHT_JSON_ARRAYS) for r in rows])


@specialized_modules_bp.route('/flights', methods=['POST'])
def api_flights_create():
    data = request.get_json() or {}
    drone_id = data.get('drone_id')
    if not drone_id:
        return jsonify({'error': 'drone_id is required'}), 400
    with db_session() as db:
        drone = db.execute('SELECT id, name FROM drones WHERE id = ?', (drone_id,)).fetchone()
        if not drone:
            return jsonify({'error': 'Drone not found'}), 404
        cur = db.execute(
            '''INSERT INTO drone_flights
               (drone_id, date, mission_type, location, gps_coords,
                duration_min, max_altitude_m, distance_km,
                battery_start_pct, battery_end_pct, weather_conditions,
                observations, media_captured, pilot, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (drone_id,
             data.get('date', datetime.utcnow().strftime('%Y-%m-%d')),
             data.get('mission_type', 'recon'),
             data.get('location', ''), data.get('gps_coords', ''),
             data.get('duration_min', 0), data.get('max_altitude_m', 0),
             data.get('distance_km', 0),
             data.get('battery_start_pct', 100),
             data.get('battery_end_pct', 0),
             data.get('weather_conditions', ''),
             data.get('observations', ''),
             json.dumps(data.get('media_captured', [])),
             data.get('pilot', ''), data.get('notes', ''))
        )
        # Update drone totals
        dur = data.get('duration_min', 0)
        dist = data.get('distance_km', 0)
        db.execute(
            '''UPDATE drones SET
               total_flights = total_flights + 1,
               total_flight_hours = total_flight_hours + ?,
               last_flight = ?,
               updated_at = CURRENT_TIMESTAMP
               WHERE id = ?''',
            (round(dur / 60.0, 2),
             data.get('date', datetime.utcnow().strftime('%Y-%m-%d')),
             drone_id)
        )
        db.commit()
        row = db.execute('SELECT * FROM drone_flights WHERE id = ?',
                         (cur.lastrowid,)).fetchone()
    log_activity('flight_logged', service='specialized', detail=f'{drone["name"]}: {data.get("mission_type", "recon")}')
    return jsonify(_row(row, json_arrays=FLIGHT_JSON_ARRAYS)), 201


@specialized_modules_bp.route('/flights/<int:fid>')
def api_flights_get(fid):
    with db_session() as db:
        row = db.execute(
            '''SELECT df.*, d.name as drone_name
               FROM drone_flights df
               LEFT JOIN drones d ON df.drone_id = d.id
               WHERE df.id = ?''',
            (fid,)
        ).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(_row(row, json_arrays=FLIGHT_JSON_ARRAYS))


@specialized_modules_bp.route('/flights/<int:fid>', methods=['DELETE'])
def api_flights_delete(fid):
    with db_session() as db:
        row = db.execute('SELECT drone_id, duration_min FROM drone_flights WHERE id = ?', (fid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM drone_flights WHERE id = ?', (fid,))
        # Decrement drone totals
        db.execute(
            '''UPDATE drones SET
               total_flights = MAX(0, total_flights - 1),
               total_flight_hours = MAX(0, total_flight_hours - ?),
               updated_at = CURRENT_TIMESTAMP
               WHERE id = ?''',
            (round((row['duration_min'] or 0) / 60.0, 2), row['drone_id'])
        )
        db.commit()
    log_activity('flight_deleted', service='specialized', detail=f'flight {fid}')
    return jsonify({'deleted': True})


@specialized_modules_bp.route('/flights/stats')
def api_flights_stats():
    with db_session() as db:
        rows = db.execute(
            '''SELECT d.id, d.name,
                      COUNT(df.id) as total_flights,
                      COALESCE(SUM(df.duration_min), 0) as total_minutes,
                      COALESCE(SUM(df.distance_km), 0) as total_distance_km
               FROM drones d
               LEFT JOIN drone_flights df ON d.id = df.drone_id
               GROUP BY d.id
               ORDER BY total_flights DESC'''
        ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d['total_hours'] = round(d['total_minutes'] / 60.0, 2)
        results.append(d)
    return jsonify(results)


# ═══════════════════════════════════════════════════════════════════════
#  FITNESS LOGS
# ═══════════════════════════════════════════════════════════════════════

@specialized_modules_bp.route('/fitness')
def api_fitness_list():
    limit, offset = _paginate()
    clauses, params = [], []
    person = request.args.get('person')
    if person:
        clauses.append('person = ?')
        params.append(person)
    et = request.args.get('type')
    if et:
        clauses.append('exercise_type = ?')
        params.append(et)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ''
    params += [limit, offset]
    with db_session() as db:
        rows = db.execute(
            f'SELECT * FROM fitness_logs{where} ORDER BY created_at DESC LIMIT ? OFFSET ?',
            params
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@specialized_modules_bp.route('/fitness', methods=['POST'])
def api_fitness_create():
    data = request.get_json() or {}
    person = (data.get('person') or '').strip()
    if not person:
        return jsonify({'error': 'person is required'}), 400
    # Accept frontend synonym aliases (the _tab_specialized_modules.html
    # template sends these short names; the DB columns are canonical).
    # Precedence: canonical field wins if both are present.
    exercise_type = data.get('exercise_type', data.get('workout_type', 'cardio'))
    duration_min = data.get('duration_min', data.get('duration', 0))
    distance_km = data.get('distance_km', data.get('distance', 0))
    calories_burned = data.get('calories_burned', data.get('calories', 0))
    heart_rate_avg = data.get('heart_rate_avg', data.get('heart_rate', 0))
    perceived_exertion = data.get('perceived_exertion', data.get('exertion', 5))
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO fitness_logs
               (person, date, exercise_type, activity, duration_min,
                distance_km, reps, sets, weight_lbs, calories_burned,
                heart_rate_avg, heart_rate_max, perceived_exertion, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (person,
             data.get('date', datetime.utcnow().strftime('%Y-%m-%d')),
             exercise_type, data.get('activity', ''), duration_min,
             distance_km, data.get('reps', 0), data.get('sets', 0),
             data.get('weight_lbs', 0), calories_burned,
             heart_rate_avg, data.get('heart_rate_max', 0),
             perceived_exertion, data.get('notes', ''))
        )
        db.commit()
        row = db.execute('SELECT * FROM fitness_logs WHERE id = ?',
                         (cur.lastrowid,)).fetchone()
    log_activity('fitness_logged', service='specialized',
                 detail=f'{person}: {data.get("activity", exercise_type)}')
    return jsonify(dict(row)), 201


@specialized_modules_bp.route('/fitness/<int:fid>')
def api_fitness_get(fid):
    with db_session() as db:
        row = db.execute('SELECT * FROM fitness_logs WHERE id = ?', (fid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(dict(row))


@specialized_modules_bp.route('/fitness/<int:fid>', methods=['DELETE'])
def api_fitness_delete(fid):
    with db_session() as db:
        row = db.execute('SELECT person FROM fitness_logs WHERE id = ?', (fid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM fitness_logs WHERE id = ?', (fid,))
        db.commit()
    log_activity('fitness_deleted', service='specialized', detail=f'log {fid}')
    return jsonify({'deleted': True})


@specialized_modules_bp.route('/fitness/weekly')
def api_fitness_weekly():
    """Per-person weekly fitness summary (frontend alias path).

    The `_tab_specialized_modules.html` template fetches
    `/fitness/weekly?person=<X>` and consumes
    `{workouts, total_duration, total_calories, total_distance, avg_exertion}`.
    Compute that shape directly from fitness_logs for the last 7 days.
    Added during the V8-06 hardening pass on 2026-04-24.
    """
    person = (request.args.get('person') or '').strip()
    if not person:
        return jsonify({'error': 'person is required'}), 400
    seven_days_ago = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')
    with db_session() as db:
        row = db.execute(
            '''SELECT COUNT(*) as workouts,
                      COALESCE(SUM(duration_min), 0) as total_duration,
                      COALESCE(SUM(calories_burned), 0) as total_calories,
                      COALESCE(SUM(distance_km), 0) as total_distance,
                      AVG(perceived_exertion) as avg_exertion
               FROM fitness_logs
               WHERE person = ? AND date >= ?''',
            (person, seven_days_ago)
        ).fetchone()
    data = dict(row) if row else {}
    # Sqlite may return None from AVG when no rows match — normalize to 0.
    if data.get('avg_exertion') is None:
        data['avg_exertion'] = 0
    data['week_start'] = seven_days_ago
    data['person'] = person
    return jsonify(data)


@specialized_modules_bp.route('/fitness/stats')
def api_fitness_stats():
    seven_days_ago = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')
    with db_session() as db:
        rows = db.execute(
            '''SELECT person, exercise_type,
                      COUNT(*) as sessions,
                      COALESCE(SUM(duration_min), 0) as total_duration_min,
                      COALESCE(SUM(calories_burned), 0) as total_calories
               FROM fitness_logs
               WHERE date >= ?
               GROUP BY person, exercise_type
               ORDER BY person, total_duration_min DESC''',
            (seven_days_ago,)
        ).fetchall()
    # Group by person
    stats = {}
    for r in rows:
        person = r['person'] or 'unknown'
        if person not in stats:
            stats[person] = {'total_duration_min': 0, 'total_calories': 0, 'by_type': {}}
        stats[person]['total_duration_min'] += r['total_duration_min']
        stats[person]['total_calories'] += r['total_calories']
        stats[person]['by_type'][r['exercise_type']] = {
            'sessions': r['sessions'],
            'duration_min': r['total_duration_min'],
            'calories': r['total_calories']
        }
    return jsonify({'week_start': seven_days_ago, 'per_person': stats})


# ═══════════════════════════════════════════════════════════════════════
#  CONTENT PACKS
# ═══════════════════════════════════════════════════════════════════════

PACK_JSON_ARRAYS = ['contents_manifest']


@specialized_modules_bp.route('/content-packs')
def api_content_packs_list():
    limit, offset = _paginate()
    clauses, params = [], []
    pt = request.args.get('type')
    if pt:
        clauses.append('pack_type = ?')
        params.append(pt)
    st = request.args.get('status')
    if st:
        clauses.append('status = ?')
        params.append(st)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ''
    params += [limit, offset]
    with db_session() as db:
        rows = db.execute(
            f'SELECT * FROM content_packs{where} ORDER BY updated_at DESC LIMIT ? OFFSET ?',
            params
        ).fetchall()
    return jsonify([_row(r, json_arrays=PACK_JSON_ARRAYS) for r in rows])


@specialized_modules_bp.route('/content-packs', methods=['POST'])
def api_content_packs_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO content_packs
               (name, pack_type, version, author, description,
                contents_manifest, size_bytes, install_date,
                source_url, checksum, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('pack_type', 'knowledge'),
             data.get('version', '1.0.0'), data.get('author', ''),
             data.get('description', ''),
             json.dumps(data.get('contents_manifest', [])),
             data.get('size_bytes', 0),
             data.get('install_date', datetime.utcnow().strftime('%Y-%m-%d')),
             data.get('source_url', ''), data.get('checksum', ''),
             data.get('status', 'installed'), data.get('notes', ''))
        )
        db.commit()
        row = db.execute('SELECT * FROM content_packs WHERE id = ?',
                         (cur.lastrowid,)).fetchone()
    log_activity('content_pack_created', service='specialized', detail=name)
    return jsonify(_row(row, json_arrays=PACK_JSON_ARRAYS)), 201


@specialized_modules_bp.route('/content-packs/<int:pid>')
def api_content_packs_get(pid):
    with db_session() as db:
        row = db.execute('SELECT * FROM content_packs WHERE id = ?', (pid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(_row(row, json_arrays=PACK_JSON_ARRAYS))


@specialized_modules_bp.route('/content-packs/<int:pid>', methods=['PUT'])
def api_content_packs_update(pid):
    data = request.get_json() or {}
    allowed = _CONTENT_PACKS_ALLOWED_FIELDS
    sets, vals = [], []
    for k in allowed:
        if k in data:
            v = data[k]
            sets.append(f'{k} = ?')
            vals.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append('updated_at = CURRENT_TIMESTAMP')
    vals.append(pid)
    with db_session() as db:
        db.execute(f"UPDATE content_packs SET {', '.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM content_packs WHERE id = ?', (pid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    log_activity('content_pack_updated', service='specialized', detail=row['name'])
    return jsonify(_row(row, json_arrays=PACK_JSON_ARRAYS))


@specialized_modules_bp.route('/content-packs/<int:pid>', methods=['DELETE'])
def api_content_packs_delete(pid):
    with db_session() as db:
        row = db.execute('SELECT name FROM content_packs WHERE id = ?', (pid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM content_packs WHERE id = ?', (pid,))
        db.commit()
    log_activity('content_pack_deleted', service='specialized', detail=row['name'])
    return jsonify({'deleted': True})
