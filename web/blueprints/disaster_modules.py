"""Disaster-Specific Modules — Phase 14 of NOMAD Field Desk.

Disaster plans, checklists, energy systems, construction projects,
building materials, fortifications, and calculators."""

import json
import math
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify
from db import db_session, log_activity
from web.blueprints import get_pagination

disaster_modules_bp = Blueprint('disaster_modules', __name__, url_prefix='/api/disaster')


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


def _row(r, json_arrays=None, json_objects=None):
    """Convert row to dict, parsing specified JSON columns."""
    d = dict(r)
    for k in (json_arrays or []):
        if k in d and d[k]:
            d[k] = _jp(d[k])
    for k in (json_objects or []):
        if k in d and d[k]:
            d[k] = _jo(d[k])
    return d


PLAN_JSON_ARRAYS = ['immediate_actions', 'sustained_actions', 'resources_required',
                    'personnel_assignments']
CHECKLIST_JSON_ARRAYS = ['items']
CONSTRUCTION_JSON_ARRAYS = ['materials']
FORTIFICATION_JSON_ARRAYS = ['materials_used']

# ─── Disaster Reference Data ────────────────────────────────────────

DISASTER_REFERENCE = {
    'earthquake': {'name': 'Earthquake', 'description': 'Seismic event', 'key_actions': ['Drop/Cover/Hold', 'Check gas lines', 'Inspect structure', 'Be ready for aftershocks'], 'typical_duration': 'Minutes (event), weeks (recovery)'},
    'hurricane': {'name': 'Hurricane', 'description': 'Tropical cyclone', 'key_actions': ['Board windows', 'Fill water containers', 'Evacuate if ordered', 'Shelter in interior room'], 'typical_duration': '12-48 hours (event), weeks-months (recovery)'},
    'tornado': {'name': 'Tornado', 'description': 'Violent rotating column', 'key_actions': ['Get to lowest floor', 'Avoid windows', 'Cover head/neck', 'Have shoes accessible'], 'typical_duration': 'Minutes (event), days-weeks (recovery)'},
    'wildfire': {'name': 'Wildfire', 'description': 'Uncontrolled fire in vegetation', 'key_actions': ['Evacuate early', 'Close all windows/vents', 'Defensible space cleared', 'Wet down structures if time'], 'typical_duration': 'Days-weeks'},
    'flood': {'name': 'Flood', 'description': 'Water overflow', 'key_actions': ['Move to high ground', 'Never drive through water', 'Disconnect utilities', 'Document damage'], 'typical_duration': 'Hours-days (event), weeks (recovery)'},
    'pandemic': {'name': 'Pandemic', 'description': 'Widespread disease outbreak', 'key_actions': ['Isolate/quarantine', 'PPE and hygiene', 'Stockpile medications', 'Limit travel'], 'typical_duration': 'Months-years'},
    'emp_solar': {'name': 'EMP / Solar Event', 'description': 'Electromagnetic pulse or solar flare', 'key_actions': ['Protect electronics in Faraday', 'Manual alternatives ready', 'Cash on hand', 'Expect no grid for months'], 'typical_duration': 'Months-years'},
    'economic_collapse': {'name': 'Economic Collapse', 'description': 'Currency/market failure', 'key_actions': ['Barter goods ready', 'Physical cash reserves', 'Reduce dependencies', 'Community mutual aid'], 'typical_duration': 'Months-years'},
    'volcanic': {'name': 'Volcanic Ashfall', 'description': 'Volcanic eruption with ash', 'key_actions': ['Seal buildings from ash', 'N95 masks for all', 'Protect water supply', 'Clear ash from roofs regularly'], 'typical_duration': 'Days-weeks'},
    'drought': {'name': 'Drought', 'description': 'Extended dry period', 'key_actions': ['Water rationing plan', 'Rainwater collection', 'Drought-resistant crops', 'Reduce water-intensive activities'], 'typical_duration': 'Months-years'},
}

# ─── Default Checklist Seeds ────────────────────────────────────────

DEFAULT_CHECKLISTS = {
    'earthquake': [
        {'item': 'Secure heavy furniture to walls', 'checked': False, 'priority': 'high', 'notes': ''},
        {'item': 'Store emergency water supply', 'checked': False, 'priority': 'high', 'notes': ''},
        {'item': 'Identify safe spots in each room', 'checked': False, 'priority': 'medium', 'notes': ''},
        {'item': 'Gas shutoff wrench accessible', 'checked': False, 'priority': 'high', 'notes': ''},
        {'item': 'Practice drop/cover/hold drill', 'checked': False, 'priority': 'medium', 'notes': ''},
    ],
    'hurricane': [
        {'item': 'Plywood cut for all windows', 'checked': False, 'priority': 'high', 'notes': ''},
        {'item': 'Fill bathtubs and containers with water', 'checked': False, 'priority': 'high', 'notes': ''},
        {'item': 'Secure outdoor furniture and objects', 'checked': False, 'priority': 'medium', 'notes': ''},
        {'item': 'Charge all devices and battery packs', 'checked': False, 'priority': 'high', 'notes': ''},
        {'item': 'Verify evacuation route and destination', 'checked': False, 'priority': 'high', 'notes': ''},
    ],
    'tornado': [
        {'item': 'Identify lowest interior room/closet', 'checked': False, 'priority': 'high', 'notes': ''},
        {'item': 'Store helmets and shoes near shelter spot', 'checked': False, 'priority': 'medium', 'notes': ''},
        {'item': 'Weather radio with fresh batteries', 'checked': False, 'priority': 'high', 'notes': ''},
        {'item': 'Practice tornado drill with family', 'checked': False, 'priority': 'medium', 'notes': ''},
        {'item': 'Mattress or heavy blanket staged for cover', 'checked': False, 'priority': 'medium', 'notes': ''},
    ],
    'wildfire': [
        {'item': 'Clear 30ft defensible space around structures', 'checked': False, 'priority': 'high', 'notes': ''},
        {'item': 'Garden hoses connected and accessible', 'checked': False, 'priority': 'medium', 'notes': ''},
        {'item': 'Important documents in fireproof container', 'checked': False, 'priority': 'high', 'notes': ''},
        {'item': 'N95 masks stocked for smoke', 'checked': False, 'priority': 'high', 'notes': ''},
        {'item': 'Vehicle loaded with go-bags facing exit', 'checked': False, 'priority': 'high', 'notes': ''},
    ],
    'flood': [
        {'item': 'Sandbags and fill material staged', 'checked': False, 'priority': 'high', 'notes': ''},
        {'item': 'Sump pump tested and backup ready', 'checked': False, 'priority': 'high', 'notes': ''},
        {'item': 'Valuables elevated above flood line', 'checked': False, 'priority': 'medium', 'notes': ''},
        {'item': 'Know location of utility shutoffs', 'checked': False, 'priority': 'high', 'notes': ''},
        {'item': 'Waterproof bags for electronics/documents', 'checked': False, 'priority': 'medium', 'notes': ''},
    ],
    'pandemic': [
        {'item': '90-day medication supply secured', 'checked': False, 'priority': 'high', 'notes': ''},
        {'item': 'N95/P100 masks for all household members', 'checked': False, 'priority': 'high', 'notes': ''},
        {'item': 'Quarantine room designated and supplied', 'checked': False, 'priority': 'medium', 'notes': ''},
        {'item': 'Disinfection supplies stocked', 'checked': False, 'priority': 'high', 'notes': ''},
        {'item': 'Communication plan if internet degrades', 'checked': False, 'priority': 'medium', 'notes': ''},
    ],
    'emp_solar': [
        {'item': 'Faraday cage built and tested', 'checked': False, 'priority': 'high', 'notes': ''},
        {'item': 'Backup radios stored in Faraday', 'checked': False, 'priority': 'high', 'notes': ''},
        {'item': 'Cash reserve in small bills', 'checked': False, 'priority': 'high', 'notes': ''},
        {'item': 'Manual tools for all critical tasks', 'checked': False, 'priority': 'medium', 'notes': ''},
        {'item': 'Paper maps of local and regional area', 'checked': False, 'priority': 'medium', 'notes': ''},
    ],
    'economic_collapse': [
        {'item': 'Barter inventory cataloged', 'checked': False, 'priority': 'high', 'notes': ''},
        {'item': 'Precious metals or trade goods secured', 'checked': False, 'priority': 'medium', 'notes': ''},
        {'item': 'Debt minimized or eliminated', 'checked': False, 'priority': 'high', 'notes': ''},
        {'item': 'Skill-based income alternatives identified', 'checked': False, 'priority': 'medium', 'notes': ''},
        {'item': 'Community mutual aid network established', 'checked': False, 'priority': 'high', 'notes': ''},
    ],
    'volcanic': [
        {'item': 'N95 masks for all household members', 'checked': False, 'priority': 'high', 'notes': ''},
        {'item': 'Plastic sheeting and tape for sealing', 'checked': False, 'priority': 'high', 'notes': ''},
        {'item': 'Eye protection (goggles) for each person', 'checked': False, 'priority': 'medium', 'notes': ''},
        {'item': 'Roof reinforcement or clearing plan', 'checked': False, 'priority': 'high', 'notes': ''},
        {'item': 'Water supply covered/protected from ash', 'checked': False, 'priority': 'high', 'notes': ''},
    ],
    'drought': [
        {'item': 'Rainwater collection system installed', 'checked': False, 'priority': 'high', 'notes': ''},
        {'item': 'Low-flow fixtures on all taps', 'checked': False, 'priority': 'medium', 'notes': ''},
        {'item': 'Greywater recycling plan in place', 'checked': False, 'priority': 'medium', 'notes': ''},
        {'item': 'Drought-resistant garden planted', 'checked': False, 'priority': 'high', 'notes': ''},
        {'item': 'Water storage capacity assessed', 'checked': False, 'priority': 'high', 'notes': ''},
    ],
}

# ═════════════════════════════════════════════════════════════════════
#  DISASTER PLANS
# ═════════════════════════════════════════════════════════════════════

@disaster_modules_bp.route('/plans')
def api_plans_list():
    dt = request.args.get('disaster_type', '').strip()
    et = request.args.get('environment_type', '').strip()
    st = request.args.get('status', '').strip()
    clauses, vals = [], []
    if dt:
        clauses.append('disaster_type = ?'); vals.append(dt)
    if et:
        clauses.append('environment_type = ?'); vals.append(et)
    if st:
        clauses.append('status = ?'); vals.append(st)
    where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
    with db_session() as db:
        rows = db.execute(f'SELECT * FROM disaster_plans{where} ORDER BY name', vals).fetchall()
    return jsonify([_row(r, json_arrays=PLAN_JSON_ARRAYS) for r in rows])


@disaster_modules_bp.route('/plans/<int:pid>')
def api_plans_get(pid):
    with db_session() as db:
        row = db.execute('SELECT * FROM disaster_plans WHERE id = ?', (pid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        checklists = db.execute(
            'SELECT * FROM disaster_checklists WHERE plan_id = ? ORDER BY category, title',
            (pid,)
        ).fetchall()
    plan = _row(row, json_arrays=PLAN_JSON_ARRAYS)
    plan['checklists'] = [_row(c, json_arrays=CHECKLIST_JSON_ARRAYS) for c in checklists]
    return jsonify(plan)


@disaster_modules_bp.route('/plans', methods=['POST'])
def api_plans_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO disaster_plans
               (name, disaster_type, environment_type, description, trigger_conditions,
                immediate_actions, sustained_actions, resources_required, shelter_plan,
                evacuation_triggers, communication_plan, estimated_duration,
                personnel_assignments, last_reviewed, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('disaster_type', 'earthquake'),
             data.get('environment_type', 'general'),
             data.get('description', ''), data.get('trigger_conditions', ''),
             json.dumps(data.get('immediate_actions', [])),
             json.dumps(data.get('sustained_actions', [])),
             json.dumps(data.get('resources_required', [])),
             data.get('shelter_plan', ''), data.get('evacuation_triggers', ''),
             data.get('communication_plan', ''), data.get('estimated_duration', ''),
             json.dumps(data.get('personnel_assignments', [])),
             data.get('last_reviewed', ''), data.get('status', 'draft'))
        )
        db.commit()
        row = db.execute('SELECT * FROM disaster_plans WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('disaster_plan_created', service='disaster', detail=name)
    return jsonify(_row(row, json_arrays=PLAN_JSON_ARRAYS)), 201


@disaster_modules_bp.route('/plans/<int:pid>', methods=['PUT'])
def api_plans_update(pid):
    data = request.get_json() or {}
    allowed = ['name', 'disaster_type', 'environment_type', 'description',
               'trigger_conditions', 'immediate_actions', 'sustained_actions',
               'resources_required', 'shelter_plan', 'evacuation_triggers',
               'communication_plan', 'estimated_duration', 'personnel_assignments',
               'last_reviewed', 'status']
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            v = data[k]
            vals.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append('updated_at = CURRENT_TIMESTAMP')
    vals.append(pid)
    with db_session() as db:
        db.execute(f"UPDATE disaster_plans SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM disaster_plans WHERE id = ?', (pid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    log_activity('disaster_plan_updated', service='disaster', detail=row['name'])
    return jsonify(_row(row, json_arrays=PLAN_JSON_ARRAYS))


@disaster_modules_bp.route('/plans/<int:pid>', methods=['DELETE'])
def api_plans_delete(pid):
    with db_session() as db:
        row = db.execute('SELECT name FROM disaster_plans WHERE id = ?', (pid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM disaster_checklists WHERE plan_id = ?', (pid,))
        db.execute('DELETE FROM disaster_plans WHERE id = ?', (pid,))
        db.commit()
    log_activity('disaster_plan_deleted', service='disaster', detail=row['name'])
    return jsonify({'ok': True})


@disaster_modules_bp.route('/plans/reference')
def api_plans_reference():
    return jsonify(DISASTER_REFERENCE)


# ═════════════════════════════════════════════════════════════════════
#  DISASTER CHECKLISTS
# ═════════════════════════════════════════════════════════════════════

@disaster_modules_bp.route('/checklists')
def api_checklists_list():
    plan_id = request.args.get('plan_id', '').strip()
    cat = request.args.get('category', '').strip()
    st = request.args.get('status', '').strip()
    clauses, vals = [], []
    if plan_id:
        clauses.append('plan_id = ?'); vals.append(plan_id)
    if cat:
        clauses.append('category = ?'); vals.append(cat)
    if st:
        clauses.append('status = ?'); vals.append(st)
    where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
    with db_session() as db:
        rows = db.execute(f'SELECT * FROM disaster_checklists{where} ORDER BY title', vals).fetchall()
    return jsonify([_row(r, json_arrays=CHECKLIST_JSON_ARRAYS) for r in rows])


@disaster_modules_bp.route('/checklists', methods=['POST'])
def api_checklists_create():
    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'error': 'title is required'}), 400
    items = data.get('items', [])
    checked = sum(1 for i in items if i.get('checked'))
    pct = int(checked / len(items) * 100) if items else 0
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO disaster_checklists
               (plan_id, title, category, items, assigned_to, due_date,
                completion_pct, status)
               VALUES (?,?,?,?,?,?,?,?)''',
            (data.get('plan_id'), title, data.get('category', 'pre_event'),
             json.dumps(items), data.get('assigned_to', ''),
             data.get('due_date', ''), pct, data.get('status', 'pending'))
        )
        db.commit()
        row = db.execute('SELECT * FROM disaster_checklists WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('disaster_checklist_created', service='disaster', detail=title)
    return jsonify(_row(row, json_arrays=CHECKLIST_JSON_ARRAYS)), 201


@disaster_modules_bp.route('/checklists/<int:cid>', methods=['PUT'])
def api_checklists_update(cid):
    data = request.get_json() or {}
    allowed = ['plan_id', 'title', 'category', 'items', 'assigned_to',
               'due_date', 'status']
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            v = data[k]
            vals.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    # Auto-compute completion_pct from items
    if 'items' in data:
        items = data['items']
        checked = sum(1 for i in items if i.get('checked'))
        pct = int(checked / len(items) * 100) if items else 0
        sets.append('completion_pct = ?'); vals.append(pct)
        # Auto-status
        if pct >= 100:
            sets.append("status = 'complete'")
    sets.append('updated_at = CURRENT_TIMESTAMP')
    vals.append(cid)
    with db_session() as db:
        db.execute(f"UPDATE disaster_checklists SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM disaster_checklists WHERE id = ?', (cid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    log_activity('disaster_checklist_updated', service='disaster', detail=row['title'])
    return jsonify(_row(row, json_arrays=CHECKLIST_JSON_ARRAYS))


@disaster_modules_bp.route('/checklists/seed', methods=['POST'])
def api_checklists_seed():
    count = 0
    with db_session() as db:
        for dtype, items in DEFAULT_CHECKLISTS.items():
            ref = DISASTER_REFERENCE.get(dtype, {})
            title = f"{ref.get('name', dtype)} - Pre-Event Checklist"
            existing = db.execute(
                'SELECT id FROM disaster_checklists WHERE title = ?', (title,)
            ).fetchone()
            if existing:
                continue
            db.execute(
                '''INSERT INTO disaster_checklists
                   (plan_id, title, category, items, assigned_to, due_date,
                    completion_pct, status)
                   VALUES (?,?,?,?,?,?,?,?)''',
                (None, title, 'pre_event', json.dumps(items), '', '', 0, 'pending')
            )
            count += 1
        db.commit()
    log_activity('disaster_checklists_seeded', service='disaster', detail=f'{count} checklists')
    return jsonify({'ok': True, 'seeded': count}), 201


# ═════════════════════════════════════════════════════════════════════
#  ENERGY SYSTEMS
# ═════════════════════════════════════════════════════════════════════

@disaster_modules_bp.route('/energy')
def api_energy_list():
    et = request.args.get('type', '').strip()
    if et:
        with db_session() as db:
            rows = db.execute(
                'SELECT * FROM energy_systems WHERE energy_type = ? ORDER BY name', (et,)
            ).fetchall()
    else:
        with db_session() as db:
            rows = db.execute('SELECT * FROM energy_systems ORDER BY name LIMIT ? OFFSET ?', get_pagination()).fetchall()
    return jsonify([dict(r) for r in rows])


@disaster_modules_bp.route('/energy', methods=['POST'])
def api_energy_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO energy_systems
               (name, energy_type, location, capacity, fuel_source, output_rating,
                efficiency_pct, installation_date, condition, maintenance_schedule,
                inventory_link, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('energy_type', 'wood'), data.get('location', ''),
             data.get('capacity', ''), data.get('fuel_source', ''),
             data.get('output_rating', ''), data.get('efficiency_pct', 0),
             data.get('installation_date', ''), data.get('condition', 'planned'),
             data.get('maintenance_schedule', ''), data.get('inventory_link', ''),
             data.get('notes', ''))
        )
        db.commit()
        row = db.execute('SELECT * FROM energy_systems WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('energy_system_created', service='disaster', detail=name)
    return jsonify(dict(row)), 201


@disaster_modules_bp.route('/energy/<int:eid>', methods=['PUT'])
def api_energy_update(eid):
    data = request.get_json() or {}
    allowed = ['name', 'energy_type', 'location', 'capacity', 'fuel_source',
               'output_rating', 'efficiency_pct', 'installation_date', 'condition',
               'maintenance_schedule', 'inventory_link', 'notes']
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            vals.append(data[k])
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append('updated_at = CURRENT_TIMESTAMP')
    vals.append(eid)
    with db_session() as db:
        db.execute(f"UPDATE energy_systems SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM energy_systems WHERE id = ?', (eid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    log_activity('energy_system_updated', service='disaster', detail=row['name'])
    return jsonify(dict(row))


@disaster_modules_bp.route('/energy/summary')
def api_energy_summary():
    with db_session() as db:
        rows = db.execute(
            '''SELECT energy_type, COUNT(*) as count, condition
               FROM energy_systems GROUP BY energy_type, condition
               ORDER BY energy_type'''
        ).fetchall()
    by_type = {}
    for r in rows:
        et = r['energy_type']
        if et not in by_type:
            by_type[et] = {'total': 0, 'operational': 0, 'offline': 0, 'degraded': 0, 'planned': 0}
        by_type[et]['total'] += r['count']
        cond = r['condition'] if r['condition'] in ('operational', 'offline', 'degraded', 'planned') else 'planned'
        by_type[et][cond] += r['count']
    return jsonify(by_type)


# ═════════════════════════════════════════════════════════════════════
#  CONSTRUCTION PROJECTS
# ═════════════════════════════════════════════════════════════════════

@disaster_modules_bp.route('/construction')
def api_construction_list():
    pt = request.args.get('type', '').strip()
    st = request.args.get('status', '').strip()
    clauses, vals = [], []
    if pt:
        clauses.append('project_type = ?'); vals.append(pt)
    if st:
        clauses.append('status = ?'); vals.append(st)
    where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
    with db_session() as db:
        rows = db.execute(f'SELECT * FROM construction_projects{where} ORDER BY priority, name', vals).fetchall()
    return jsonify([_row(r, json_arrays=CONSTRUCTION_JSON_ARRAYS) for r in rows])


@disaster_modules_bp.route('/construction', methods=['POST'])
def api_construction_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO construction_projects
               (name, project_type, location, description, materials,
                labor_hours_estimated, labor_hours_actual, start_date, target_date,
                completion_date, assigned_to, blueprint_ref, status, priority, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('project_type', 'shelter'), data.get('location', ''),
             data.get('description', ''), json.dumps(data.get('materials', [])),
             data.get('labor_hours_estimated', 0), data.get('labor_hours_actual', 0),
             data.get('start_date', ''), data.get('target_date', ''),
             data.get('completion_date', ''), data.get('assigned_to', ''),
             data.get('blueprint_ref', ''), data.get('status', 'planned'),
             data.get('priority', 'medium'), data.get('notes', ''))
        )
        db.commit()
        row = db.execute('SELECT * FROM construction_projects WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('construction_project_created', service='disaster', detail=name)
    return jsonify(_row(row, json_arrays=CONSTRUCTION_JSON_ARRAYS)), 201


@disaster_modules_bp.route('/construction/<int:cid>', methods=['PUT'])
def api_construction_update(cid):
    data = request.get_json() or {}
    allowed = ['name', 'project_type', 'location', 'description', 'materials',
               'labor_hours_estimated', 'labor_hours_actual', 'start_date',
               'target_date', 'completion_date', 'assigned_to', 'blueprint_ref',
               'status', 'priority', 'notes']
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            v = data[k]
            vals.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append('updated_at = CURRENT_TIMESTAMP')
    vals.append(cid)
    with db_session() as db:
        db.execute(f"UPDATE construction_projects SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM construction_projects WHERE id = ?', (cid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    log_activity('construction_project_updated', service='disaster', detail=row['name'])
    return jsonify(_row(row, json_arrays=CONSTRUCTION_JSON_ARRAYS))


@disaster_modules_bp.route('/construction/<int:cid>', methods=['DELETE'])
def api_construction_delete(cid):
    with db_session() as db:
        row = db.execute('SELECT name FROM construction_projects WHERE id = ?', (cid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM construction_projects WHERE id = ?', (cid,))
        db.commit()
    log_activity('construction_project_deleted', service='disaster', detail=row['name'])
    return jsonify({'ok': True})


@disaster_modules_bp.route('/construction/<int:cid>/materials')
def api_construction_materials(cid):
    with db_session() as db:
        row = db.execute('SELECT name, materials FROM construction_projects WHERE id = ?', (cid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    materials = _jp(row['materials'])
    acquired = sum(1 for m in materials if m.get('acquired'))
    total = len(materials)
    return jsonify({
        'project': row['name'],
        'materials': materials,
        'total_items': total,
        'acquired': acquired,
        'needed': total - acquired,
        'completion_pct': int(acquired / total * 100) if total else 0,
    })


# ═════════════════════════════════════════════════════════════════════
#  BUILDING MATERIALS
# ═════════════════════════════════════════════════════════════════════

@disaster_modules_bp.route('/materials')
def api_materials_list():
    cat = request.args.get('category', '').strip()
    if cat:
        with db_session() as db:
            rows = db.execute(
                'SELECT * FROM building_materials WHERE category = ? ORDER BY name', (cat,)
            ).fetchall()
    else:
        with db_session() as db:
            rows = db.execute('SELECT * FROM building_materials ORDER BY category, name LIMIT ? OFFSET ?', get_pagination()).fetchall()
    return jsonify([dict(r) for r in rows])


@disaster_modules_bp.route('/materials', methods=['POST'])
def api_materials_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO building_materials
               (name, category, quantity, unit, location, cost_per_unit,
                supplier, min_stock, notes)
               VALUES (?,?,?,?,?,?,?,?,?)''',
            (name, data.get('category', 'other'), data.get('quantity', 0),
             data.get('unit', 'ea'), data.get('location', ''),
             data.get('cost_per_unit', 0), data.get('supplier', ''),
             data.get('min_stock', 0), data.get('notes', ''))
        )
        db.commit()
        row = db.execute('SELECT * FROM building_materials WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('building_material_created', service='disaster', detail=name)
    return jsonify(dict(row)), 201


@disaster_modules_bp.route('/materials/<int:mid>', methods=['PUT'])
def api_materials_update(mid):
    data = request.get_json() or {}
    allowed = ['name', 'category', 'quantity', 'unit', 'location',
               'cost_per_unit', 'supplier', 'min_stock', 'notes']
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            vals.append(data[k])
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append('updated_at = CURRENT_TIMESTAMP')
    vals.append(mid)
    with db_session() as db:
        db.execute(f"UPDATE building_materials SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM building_materials WHERE id = ?', (mid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    log_activity('building_material_updated', service='disaster', detail=row['name'])
    return jsonify(dict(row))


@disaster_modules_bp.route('/materials/low-stock')
def api_materials_low_stock():
    with db_session() as db:
        rows = db.execute(
            '''SELECT * FROM building_materials
               WHERE min_stock > 0 AND quantity < min_stock
               ORDER BY (quantity * 1.0 / min_stock) ASC'''
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# ═════════════════════════════════════════════════════════════════════
#  FORTIFICATIONS
# ═════════════════════════════════════════════════════════════════════

@disaster_modules_bp.route('/fortifications')
def api_fortifications_list():
    ft = request.args.get('type', '').strip()
    st = request.args.get('status', '').strip()
    clauses, vals = [], []
    if ft:
        clauses.append('fortification_type = ?'); vals.append(ft)
    if st:
        clauses.append('status = ?'); vals.append(st)
    where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
    with db_session() as db:
        rows = db.execute(f'SELECT * FROM fortifications{where} ORDER BY name', vals).fetchall()
    return jsonify([_row(r, json_arrays=FORTIFICATION_JSON_ARRAYS) for r in rows])


@disaster_modules_bp.route('/fortifications', methods=['POST'])
def api_fortifications_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO fortifications
               (name, fortification_type, location, protection_level, dimensions,
                materials_used, capacity_persons, construction_time_hours, condition,
                last_inspection, vulnerabilities, improvements_needed, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('fortification_type', 'safe_room'),
             data.get('location', ''), data.get('protection_level', 'basic'),
             data.get('dimensions', ''), json.dumps(data.get('materials_used', [])),
             data.get('capacity_persons', 0), data.get('construction_time_hours', 0),
             data.get('condition', 'planned'), data.get('last_inspection', ''),
             data.get('vulnerabilities', ''), data.get('improvements_needed', ''),
             data.get('status', 'planned'), data.get('notes', ''))
        )
        db.commit()
        row = db.execute('SELECT * FROM fortifications WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('fortification_created', service='disaster', detail=name)
    return jsonify(_row(row, json_arrays=FORTIFICATION_JSON_ARRAYS)), 201


@disaster_modules_bp.route('/fortifications/<int:fid>', methods=['PUT'])
def api_fortifications_update(fid):
    data = request.get_json() or {}
    allowed = ['name', 'fortification_type', 'location', 'protection_level',
               'dimensions', 'materials_used', 'capacity_persons',
               'construction_time_hours', 'condition', 'last_inspection',
               'vulnerabilities', 'improvements_needed', 'status', 'notes']
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            v = data[k]
            vals.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append('updated_at = CURRENT_TIMESTAMP')
    vals.append(fid)
    with db_session() as db:
        db.execute(f"UPDATE fortifications SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM fortifications WHERE id = ?', (fid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    log_activity('fortification_updated', service='disaster', detail=row['name'])
    return jsonify(_row(row, json_arrays=FORTIFICATION_JSON_ARRAYS))


@disaster_modules_bp.route('/fortifications/assessment')
def api_fortifications_assessment():
    with db_session() as db:
        rows = db.execute('SELECT * FROM fortifications').fetchall()
    if not rows:
        return jsonify({'total': 0, 'by_type': {}, 'by_level': {}, 'avg_condition': None,
                        'inspection_overdue': 0})
    by_type, by_level = {}, {}
    cond_scores = {'excellent': 4, 'good': 3, 'fair': 2, 'poor': 1, 'planned': 0}
    cond_total, cond_count = 0, 0
    overdue = 0
    cutoff = (datetime.utcnow() - timedelta(days=90)).strftime('%Y-%m-%d')
    for r in rows:
        ft = r['fortification_type']
        by_type[ft] = by_type.get(ft, 0) + 1
        pl = r['protection_level']
        by_level[pl] = by_level.get(pl, 0) + 1
        c = r['condition']
        if c in cond_scores:
            cond_total += cond_scores[c]; cond_count += 1
        li = r['last_inspection'] or ''
        if li and li < cutoff:
            overdue += 1
        elif not li and r['status'] == 'operational':
            overdue += 1
    cond_names = {4: 'excellent', 3: 'good', 2: 'fair', 1: 'poor', 0: 'planned'}
    avg_score = round(cond_total / cond_count) if cond_count else None
    return jsonify({
        'total': len(rows),
        'by_type': by_type,
        'by_level': by_level,
        'avg_condition': cond_names.get(avg_score) if avg_score is not None else None,
        'inspection_overdue': overdue,
    })


# ═════════════════════════════════════════════════════════════════════
#  CALCULATORS
# ═════════════════════════════════════════════════════════════════════

@disaster_modules_bp.route('/calculators/heating')
def api_calc_heating():
    """Wood heating calculator.

    Estimates cords of wood needed per heating season based on square footage,
    insulation quality, target indoor temperature, and average outside temperature.
    One cord of hardwood ~ 20 million BTU.  Typical wood stove efficiency ~60-70%.
    """
    try:
        sq_ft = float(request.args.get('sq_ft', 0))
        insulation = request.args.get('insulation_rating', 'average')
        target = float(request.args.get('target_temp', 68))
        outside = float(request.args.get('outside_temp', 30))
    except (ValueError, TypeError):
        return jsonify({'error': 'invalid numeric parameters'}), 400

    # Heat-loss factor per sq_ft per degree-F per hour (BTU)
    loss_factors = {'poor': 0.035, 'average': 0.025, 'good': 0.018, 'excellent': 0.012}
    factor = loss_factors.get(insulation, 0.025)

    delta_t = max(target - outside, 0)
    heating_hours = 24 * 180  # ~6-month heating season
    total_btu = sq_ft * factor * delta_t * heating_hours
    stove_efficiency = 0.65
    btu_per_cord = 20_000_000
    cords = total_btu / (btu_per_cord * stove_efficiency)

    return jsonify({
        'sq_ft': sq_ft,
        'insulation_rating': insulation,
        'target_temp_f': target,
        'outside_temp_f': outside,
        'delta_t': delta_t,
        'heating_season_days': 180,
        'total_btu_needed': round(total_btu),
        'stove_efficiency_pct': 65,
        'cords_needed': round(cords, 2),
        'cords_rounded_up': math.ceil(cords),
    })


@disaster_modules_bp.route('/calculators/sandbag')
def api_calc_sandbag():
    """Sandbag wall calculator.

    Standard sandbag: ~14x26 inches filled, ~40 lbs.
    Bags per linear foot per course: ~1.6.
    Each course is ~6 inches high.  1 cubic yard of fill ~ 20 bags.
    """
    try:
        length_ft = float(request.args.get('wall_length_ft', 0))
        height_ft = float(request.args.get('wall_height_ft', 0))
    except (ValueError, TypeError):
        return jsonify({'error': 'invalid numeric parameters'}), 400

    bags_per_ft_per_course = 1.6
    course_height_in = 6
    courses = math.ceil((height_ft * 12) / course_height_in)
    total_bags = math.ceil(length_ft * bags_per_ft_per_course * courses)
    fill_cubic_yards = round(total_bags / 20, 2)

    return jsonify({
        'wall_length_ft': length_ft,
        'wall_height_ft': height_ft,
        'courses': courses,
        'sandbags_needed': total_bags,
        'fill_material_cubic_yards': fill_cubic_yards,
        'estimated_weight_lbs': total_bags * 40,
    })


# ═════════════════════════════════════════════════════════════════════
#  SUMMARY
# ═════════════════════════════════════════════════════════════════════

@disaster_modules_bp.route('/summary')
def api_disaster_summary():
    with db_session() as db:
        # Plans by disaster type
        plan_rows = db.execute(
            'SELECT disaster_type, COUNT(*) as count FROM disaster_plans GROUP BY disaster_type'
        ).fetchall()
        plans_by_type = {r['disaster_type']: r['count'] for r in plan_rows}
        total_plans = sum(plans_by_type.values())

        # Active checklists
        cl_rows = db.execute(
            '''SELECT status, COUNT(*) as count FROM disaster_checklists
               GROUP BY status'''
        ).fetchall()
        checklists = {r['status']: r['count'] for r in cl_rows}

        # Energy capacity
        energy_rows = db.execute(
            '''SELECT energy_type, COUNT(*) as count,
                      SUM(CASE WHEN condition = 'operational' THEN 1 ELSE 0 END) as operational
               FROM energy_systems GROUP BY energy_type'''
        ).fetchall()
        energy = {r['energy_type']: {'total': r['count'], 'operational': r['operational']}
                  for r in energy_rows}

        # Construction progress
        con_rows = db.execute(
            'SELECT status, COUNT(*) as count FROM construction_projects GROUP BY status'
        ).fetchall()
        construction = {r['status']: r['count'] for r in con_rows}

        # Material stock levels
        mat_total = db.execute('SELECT COUNT(*) as c FROM building_materials').fetchone()['c']
        mat_low = db.execute(
            'SELECT COUNT(*) as c FROM building_materials WHERE min_stock > 0 AND quantity < min_stock'
        ).fetchone()['c']

        # Fortification readiness
        fort_rows = db.execute(
            'SELECT status, COUNT(*) as count FROM fortifications GROUP BY status'
        ).fetchall()
        fortifications = {r['status']: r['count'] for r in fort_rows}

    return jsonify({
        'plans': {'total': total_plans, 'by_disaster_type': plans_by_type},
        'checklists': checklists,
        'energy': energy,
        'construction': construction,
        'materials': {'total_items': mat_total, 'low_stock': mat_low},
        'fortifications': fortifications,
    })
