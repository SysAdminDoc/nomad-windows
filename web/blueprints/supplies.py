"""Fuel, equipment, ammo, community, radiation, vault, and skills routes."""

import json
import logging

from flask import Blueprint, request, jsonify, Response
from db import db_session
from web.utils import require_json_body as _require_json_body, validate_bulk_ids as _validate_bulk_ids

_log = logging.getLogger(__name__)

supplies_bp = Blueprint('supplies', __name__)


# ─── Vault ─────────────────────────────────────────────────────────

@supplies_bp.route('/api/vault')
def api_vault_list():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
    except (ValueError, TypeError):
        limit = 50
    try:
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        offset = 0
    with db_session() as db:
        rows = db.execute('SELECT id, title, created_at, updated_at FROM vault_entries ORDER BY updated_at DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    return jsonify([dict(r) for r in rows])

@supplies_bp.route('/api/vault', methods=['POST'])
def api_vault_create():
    data = request.get_json() or {}
    for field in ('encrypted_data', 'iv', 'salt'):
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
        if len(data.get(field, '') or '') > 1_000_000:
            return jsonify({'error': f'{field} too large (max 1MB)'}), 400
    with db_session() as db:
        cur = db.execute('INSERT INTO vault_entries (title, encrypted_data, iv, salt) VALUES (?, ?, ?, ?)',
                         (data.get('title', 'Untitled'), data['encrypted_data'], data['iv'], data['salt']))
        db.commit()
        eid = cur.lastrowid
    return jsonify({'id': eid, 'status': 'saved'}), 201

@supplies_bp.route('/api/vault/<int:eid>')
def api_vault_get(eid):
    with db_session() as db:
        row = db.execute('SELECT * FROM vault_entries WHERE id = ?', (eid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(dict(row))

@supplies_bp.route('/api/vault/<int:eid>', methods=['PUT'])
def api_vault_update(eid):
    data = request.get_json() or {}
    for field in ('encrypted_data', 'iv', 'salt'):
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
        if len(data.get(field, '') or '') > 1_000_000:
            return jsonify({'error': f'{field} too large (max 1MB)'}), 400
    with db_session() as db:
        r = db.execute('UPDATE vault_entries SET title = ?, encrypted_data = ?, iv = ?, salt = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                   (data.get('title', ''), data['encrypted_data'], data['iv'], data['salt'], eid))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'saved'})

@supplies_bp.route('/api/vault/<int:eid>', methods=['DELETE'])
def api_vault_delete(eid):
    with db_session() as db:
        r = db.execute('DELETE FROM vault_entries WHERE id = ?', (eid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


# ─── Skills ────────────────────────────────────────────────────────

@supplies_bp.route('/api/skills')
def api_skills_list():
    SKILL_SORT_FIELDS = {'name', 'category', 'proficiency', 'created_at', 'updated_at'}
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
    except (ValueError, TypeError):
        limit = 50
    try:
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        offset = 0
    sort_by = request.args.get('sort_by', 'category')
    sort_dir = 'DESC' if request.args.get('sort_dir', 'asc').lower() == 'desc' else 'ASC'
    if sort_by not in SKILL_SORT_FIELDS:
        sort_by = 'category'
    with db_session() as conn:
        rows = conn.execute(f'SELECT * FROM skills ORDER BY {sort_by} {sort_dir}, name ASC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
        return jsonify([dict(r) for r in rows])

@supplies_bp.route('/api/skills', methods=['POST'])
def api_skills_create():
    d = request.json or {}
    if len(d.get('name', '') or '') > 200:
        return jsonify({'error': 'name too long (max 200)'}), 400
    if not d.get('name', '').strip():
        return jsonify({'error': 'name is required'}), 400
    with db_session() as conn:
        cur = conn.execute(
            'INSERT INTO skills (name, category, proficiency, notes, last_practiced) VALUES (?,?,?,?,?)',
            (d['name'].strip(), d.get('category','general'), d.get('proficiency','none'),
             d.get('notes',''), d.get('last_practiced','')))
        conn.commit()
        row = conn.execute('SELECT * FROM skills WHERE id=?', (cur.lastrowid,)).fetchone()
        return jsonify(dict(row)), 201

@supplies_bp.route('/api/skills/<int:sid>', methods=['PUT'])
def api_skills_update(sid):
    d = request.json or {}
    if len(d.get('name', '') or '') > 200:
        return jsonify({'error': 'name too long (max 200)'}), 400
    with db_session() as conn:
        conn.execute(
            'UPDATE skills SET name=?, category=?, proficiency=?, notes=?, last_practiced=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
            (d.get('name',''), d.get('category','general'), d.get('proficiency','none'),
             d.get('notes',''), d.get('last_practiced',''), sid))
        conn.commit()
        row = conn.execute('SELECT * FROM skills WHERE id=?', (sid,)).fetchone()
        return jsonify(dict(row) if row else {})

@supplies_bp.route('/api/skills/<int:sid>', methods=['DELETE'])
def api_skills_delete(sid):
    with db_session() as conn:
        r = conn.execute('DELETE FROM skills WHERE id=?', (sid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        conn.commit()
        return jsonify({'ok': True})

@supplies_bp.route('/api/skills/bulk-delete', methods=['POST'])
def api_skills_bulk_delete():
    data, error = _require_json_body(request)
    if error:
        return error
    ids = _validate_bulk_ids(data)
    if ids is None:
        return jsonify({'error': 'ids array of integers required (max 100)'}), 400
    with db_session() as conn:
        placeholders = ','.join('?' * len(ids))
        r = conn.execute(f'DELETE FROM skills WHERE id IN ({placeholders})', ids)
        conn.commit()
    return jsonify({'status': 'deleted', 'count': r.rowcount})

@supplies_bp.route('/api/skills/export')
def api_skills_export():
    with db_session() as conn:
        rows = conn.execute('SELECT * FROM skills ORDER BY category, name LIMIT 10000').fetchall()
    data = [dict(r) for r in rows]
    return Response(json.dumps(data, indent=2, default=str),
                    mimetype='application/json',
                    headers={'Content-Disposition': 'attachment; filename=skills_export.json'})

@supplies_bp.route('/api/skills/import', methods=['POST'])
def api_skills_import():
    data, error = _require_json_body(request)
    if error:
        return error
    if not isinstance(data, list):
        return jsonify({'error': 'expected JSON array'}), 400
    if len(data) > 1000:
        return jsonify({'error': 'max 1000 items'}), 400
    imported = 0
    with db_session() as conn:
        for item in data:
            conn.execute(
                'INSERT INTO skills (name, category, proficiency, notes, last_practiced) VALUES (?,?,?,?,?)',
                (item.get('name', ''), item.get('category', 'general'),
                 item.get('proficiency', 'none'), item.get('notes', ''),
                 item.get('last_practiced', '')))
            imported += 1
        conn.commit()
    return jsonify({'status': 'imported', 'count': imported})

@supplies_bp.route('/api/skills/seed-defaults', methods=['POST'])
def api_skills_seed():
    """Seed the default 60-skill list if table is empty."""
    with db_session() as conn:
        count = conn.execute('SELECT COUNT(*) FROM skills').fetchone()[0]
        if count > 0:
            return jsonify({'seeded': 0})
        defaults = [
            # Fire
            ('Fire Starting (friction/bow drill)', 'Fire'), ('Fire Starting (ferro rod)', 'Fire'),
            ('Fire Starting (flint & steel)', 'Fire'), ('Fire Starting (magnification)', 'Fire'),
            ('Maintaining a fire for 12+ hours', 'Fire'), ('Building a fire in rain/wind', 'Fire'),
            # Water
            ('Water sourcing (streams, dew, transpiration)', 'Water'),
            ('Water purification (boiling)', 'Water'), ('Water purification (chemical)', 'Water'),
            ('Water purification (filtration)', 'Water'), ('Rainwater collection setup', 'Water'),
            ('Solar disinfection (SODIS)', 'Water'),
            # Shelter
            ('Debris hut construction', 'Shelter'), ('Tarp shelter rigging', 'Shelter'),
            ('Cold-weather shelter (snow trench, quinzhee)', 'Shelter'),
            ('Knot tying (8 essential knots)', 'Shelter'), ('Rope/cordage making', 'Shelter'),
            # Food
            ('Foraging wild edibles', 'Food'), ('Identifying poisonous plants', 'Food'),
            ('Small game trapping (snares)', 'Food'), ('Hunting / firearms proficiency', 'Food'),
            ('Fishing (without conventional tackle)', 'Food'), ('Food preservation (canning)', 'Food'),
            ('Food preservation (dehydrating)', 'Food'), ('Food preservation (smoking)', 'Food'),
            ('Butchering / game processing', 'Food'), ('Gardening (seed-to-harvest)', 'Food'),
            # Navigation
            ('Map and compass navigation', 'Navigation'), ('Celestial navigation (stars/sun)', 'Navigation'),
            ('GPS use and offline mapping', 'Navigation'), ('Dead reckoning', 'Navigation'),
            ('Terrain association', 'Navigation'), ('Creating a field sketch map', 'Navigation'),
            # Medical
            ('CPR (adult, child, infant)', 'Medical'), ('Tourniquet application', 'Medical'),
            ('Wound packing / pressure bandage', 'Medical'), ('Splinting fractures', 'Medical'),
            ('Suturing / wound closure (improvised)', 'Medical'),
            ('Burn treatment', 'Medical'), ('Triage (START method)', 'Medical'),
            ('Managing shock', 'Medical'), ('Drug interaction awareness', 'Medical'),
            ('Childbirth assistance', 'Medical'), ('Dental emergency management', 'Medical'),
            # Communications
            ('Ham radio operation (Technician)', 'Communications'),
            ('Ham radio operation (General/HF)', 'Communications'),
            ('Morse code (sending & receiving)', 'Communications'),
            ('Meshtastic / LoRa mesh setup', 'Communications'),
            ('Radio programming (CHIRP)', 'Communications'),
            ('ICS / ARES net procedures', 'Communications'),
            # Security
            ('Threat assessment / situational awareness', 'Security'),
            ('Perimeter security setup', 'Security'),
            ('Night operations', 'Security'), ('Gray man / OPSEC', 'Security'),
            # Mechanical
            ('Vehicle maintenance (basic)', 'Mechanical'),
            ('Small engine repair', 'Mechanical'),
            ('Improvised tool fabrication', 'Mechanical'),
            ('Electrical / solar system wiring', 'Mechanical'),
            ('Water system plumbing', 'Mechanical'),
            # Homesteading
            ('Livestock care (chickens)', 'Homesteading'),
            ('Livestock care (goats/pigs/cattle)', 'Homesteading'),
            ('Composting', 'Homesteading'), ('Seed saving', 'Homesteading'),
            ('Natural building (adobe/cob)', 'Homesteading'),
        ]
        for name, cat in defaults:
            conn.execute('INSERT OR IGNORE INTO skills (name, category, proficiency) VALUES (?,?,?)',
                         (name, cat, 'none'))
        conn.commit()
    return jsonify({'seeded': len(defaults)})


# ─── Ammo Inventory ───────────────────────────────────────────────

@supplies_bp.route('/api/ammo')
def api_ammo_list():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
    except (ValueError, TypeError):
        limit = 50
    try:
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        offset = 0
    with db_session() as conn:
        rows = conn.execute('SELECT * FROM ammo_inventory ORDER BY caliber, brand LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    return jsonify([dict(r) for r in rows])

@supplies_bp.route('/api/ammo', methods=['POST'])
def api_ammo_create():
    d = request.json or {}
    if len(d.get('caliber', '') or '') > 200:
        return jsonify({'error': 'caliber too long (max 200)'}), 400
    try:
        qty = int(d.get('quantity', 0))
    except (ValueError, TypeError):
        qty = 0
    with db_session() as conn:
        cur = conn.execute(
            'INSERT INTO ammo_inventory (caliber, brand, bullet_weight, bullet_type, quantity, location, notes) VALUES (?,?,?,?,?,?,?)',
            (d.get('caliber',''), d.get('brand',''), d.get('bullet_weight',''),
             d.get('bullet_type',''), qty, d.get('location',''), d.get('notes','')))
        conn.commit()
        row = conn.execute('SELECT * FROM ammo_inventory WHERE id=?', (cur.lastrowid,)).fetchone()
        return jsonify(dict(row)), 201

@supplies_bp.route('/api/ammo/<int:aid>', methods=['PUT'])
def api_ammo_update(aid):
    d = request.json or {}
    if len(d.get('caliber', '') or '') > 200:
        return jsonify({'error': 'caliber too long (max 200)'}), 400
    try:
        qty = int(d.get('quantity', 0))
    except (ValueError, TypeError):
        qty = 0
    with db_session() as conn:
        conn.execute(
            'UPDATE ammo_inventory SET caliber=?, brand=?, bullet_weight=?, bullet_type=?, quantity=?, location=?, notes=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
            (d.get('caliber',''), d.get('brand',''), d.get('bullet_weight',''),
             d.get('bullet_type',''), qty, d.get('location',''), d.get('notes',''), aid))
        conn.commit()
        row = conn.execute('SELECT * FROM ammo_inventory WHERE id=?', (aid,)).fetchone()
        return jsonify(dict(row) if row else {})

@supplies_bp.route('/api/ammo/<int:aid>', methods=['DELETE'])
def api_ammo_delete(aid):
    with db_session() as conn:
        r = conn.execute('DELETE FROM ammo_inventory WHERE id=?', (aid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        conn.commit()
        return jsonify({'ok': True})

@supplies_bp.route('/api/ammo/bulk-delete', methods=['POST'])
def api_ammo_bulk_delete():
    data, error = _require_json_body(request)
    if error:
        return error
    ids = _validate_bulk_ids(data)
    if ids is None:
        return jsonify({'error': 'ids array of integers required (max 100)'}), 400
    with db_session() as conn:
        placeholders = ','.join('?' * len(ids))
        r = conn.execute(f'DELETE FROM ammo_inventory WHERE id IN ({placeholders})', ids)
        conn.commit()
    return jsonify({'status': 'deleted', 'count': r.rowcount})

@supplies_bp.route('/api/ammo/export')
def api_ammo_export():
    with db_session() as conn:
        rows = conn.execute('SELECT * FROM ammo_inventory ORDER BY caliber, brand LIMIT 10000').fetchall()
    data = [dict(r) for r in rows]
    return Response(json.dumps(data, indent=2, default=str),
                    mimetype='application/json',
                    headers={'Content-Disposition': 'attachment; filename=ammo_export.json'})

@supplies_bp.route('/api/ammo/import', methods=['POST'])
def api_ammo_import():
    data, error = _require_json_body(request)
    if error:
        return error
    if not isinstance(data, list):
        return jsonify({'error': 'expected JSON array'}), 400
    if len(data) > 1000:
        return jsonify({'error': 'max 1000 items'}), 400
    imported = 0
    with db_session() as conn:
        for item in data:
            try:
                qty = int(item.get('quantity', 0))
            except (ValueError, TypeError):
                qty = 0
            conn.execute(
                'INSERT INTO ammo_inventory (caliber, brand, bullet_weight, bullet_type, quantity, location, notes) VALUES (?,?,?,?,?,?,?)',
                (item.get('caliber', ''), item.get('brand', ''),
                 item.get('bullet_weight', ''), item.get('bullet_type', ''),
                 qty, item.get('location', ''), item.get('notes', '')))
            imported += 1
        conn.commit()
    return jsonify({'status': 'imported', 'count': imported})

@supplies_bp.route('/api/ammo/summary')
def api_ammo_summary():
    with db_session() as conn:
        rows = conn.execute(
            'SELECT caliber, SUM(quantity) as total FROM ammo_inventory GROUP BY caliber ORDER BY total DESC'
        ).fetchall()
        total = conn.execute('SELECT SUM(quantity) FROM ammo_inventory').fetchone()[0] or 0
        return jsonify({'by_caliber': [dict(r) for r in rows], 'total': total})


# ─── Community Resource Registry ──────────────────────────────────

@supplies_bp.route('/api/community')
def api_community_list():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
    except (ValueError, TypeError):
        limit = 50
    try:
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        offset = 0
    with db_session() as conn:
        rows = conn.execute('SELECT * FROM community_resources ORDER BY trust_level DESC, name LIMIT ? OFFSET ?', (limit, offset)).fetchall()
        return jsonify([dict(r) for r in rows])

@supplies_bp.route('/api/community', methods=['POST'])
def api_community_create():
    d = request.json or {}
    if len(d.get('name', '') or '') > 200:
        return jsonify({'error': 'name too long (max 200)'}), 400
    if not d.get('name', '').strip():
        return jsonify({'error': 'name is required'}), 400
    try:
        dist = float(d.get('distance_mi', 0))
    except (ValueError, TypeError):
        dist = 0.0
    with db_session() as conn:
        cur = conn.execute(
            'INSERT INTO community_resources (name, distance_mi, skills, equipment, contact, notes, trust_level) VALUES (?,?,?,?,?,?,?)',
            (d['name'].strip(), dist,
             json.dumps(d.get('skills',[])), json.dumps(d.get('equipment',[])),
             d.get('contact',''), d.get('notes',''), d.get('trust_level','unknown')))
        conn.commit()
        row = conn.execute('SELECT * FROM community_resources WHERE id=?', (cur.lastrowid,)).fetchone()
        return jsonify(dict(row)), 201

@supplies_bp.route('/api/community/<int:cid>', methods=['PUT'])
def api_community_update(cid):
    d = request.json or {}
    if len(d.get('name', '') or '') > 200:
        return jsonify({'error': 'name too long (max 200)'}), 400
    try:
        dist = float(d.get('distance_mi', 0))
    except (ValueError, TypeError):
        dist = 0.0
    with db_session() as conn:
        conn.execute(
            'UPDATE community_resources SET name=?, distance_mi=?, skills=?, equipment=?, contact=?, notes=?, trust_level=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
            (d.get('name',''), dist,
             json.dumps(d.get('skills',[])), json.dumps(d.get('equipment',[])),
             d.get('contact',''), d.get('notes',''), d.get('trust_level','unknown'), cid))
        conn.commit()
        row = conn.execute('SELECT * FROM community_resources WHERE id=?', (cid,)).fetchone()
        return jsonify(dict(row) if row else {})

@supplies_bp.route('/api/community/<int:cid>', methods=['DELETE'])
def api_community_delete(cid):
    with db_session() as conn:
        r = conn.execute('DELETE FROM community_resources WHERE id=?', (cid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        conn.commit()
        return jsonify({'ok': True})

@supplies_bp.route('/api/community/bulk-delete', methods=['POST'])
def api_community_bulk_delete():
    data, error = _require_json_body(request)
    if error:
        return error
    ids = _validate_bulk_ids(data)
    if ids is None:
        return jsonify({'error': 'ids array of integers required (max 100)'}), 400
    with db_session() as conn:
        placeholders = ','.join('?' * len(ids))
        r = conn.execute(f'DELETE FROM community_resources WHERE id IN ({placeholders})', ids)
        conn.commit()
    return jsonify({'status': 'deleted', 'count': r.rowcount})


# ─── Radiation Dose Log ───────────────────────────────────────────

@supplies_bp.route('/api/radiation')
def api_radiation_list():
    with db_session() as conn:
        rows = conn.execute('SELECT * FROM radiation_log ORDER BY created_at DESC LIMIT 200').fetchall()
        total = conn.execute('SELECT COALESCE(MAX(cumulative_rem), 0) FROM radiation_log').fetchone()[0] or 0
        return jsonify({'readings': [dict(r) for r in rows], 'total_rem': round(total, 4)})

@supplies_bp.route('/api/radiation', methods=['POST'])
def api_radiation_create():
    d = request.json or {}
    try:
        new_rate = float(d.get('dose_rate_rem', 0))
    except (ValueError, TypeError):
        new_rate = 0.0
    try:
        duration_hours = float(d.get('duration_hours', 1.0))
    except (ValueError, TypeError):
        duration_hours = 1.0
    dose = round(new_rate * duration_hours, 4)
    with db_session() as conn:
        last = conn.execute('SELECT cumulative_rem FROM radiation_log ORDER BY id DESC LIMIT 1').fetchone()
        prev_cum = (last['cumulative_rem'] or 0) if last else 0
        new_cum = round(prev_cum + dose, 4)
        cur = conn.execute(
            'INSERT INTO radiation_log (dose_rate_rem, location, cumulative_rem, notes) VALUES (?,?,?,?)',
            (new_rate, d.get('location',''), new_cum, d.get('notes','')))
        conn.commit()
        row = conn.execute('SELECT * FROM radiation_log WHERE id=?', (cur.lastrowid,)).fetchone()
        return jsonify(dict(row)), 201

@supplies_bp.route('/api/radiation/clear', methods=['POST'])
def api_radiation_clear():
    with db_session() as conn:
        conn.execute('DELETE FROM radiation_log')
        conn.commit()
        return jsonify({'ok': True})


# ─── Fuel Storage ─────────────────────────────────────────────────

@supplies_bp.route('/api/fuel')
def api_fuel_list():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
    except (ValueError, TypeError):
        limit = 50
    try:
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        offset = 0
    with db_session() as conn:
        rows = conn.execute('SELECT * FROM fuel_storage ORDER BY fuel_type, created_at DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
        return jsonify([dict(r) for r in rows])

@supplies_bp.route('/api/fuel', methods=['POST'])
def api_fuel_create():
    d = request.json or {}
    if len(d.get('fuel_type', '') or '') > 200:
        return jsonify({'error': 'fuel_type too long (max 200)'}), 400
    if not d.get('fuel_type', '').strip():
        return jsonify({'error': 'fuel_type is required'}), 400
    try:
        stab = int(d.get('stabilizer_added', 0))
    except (ValueError, TypeError):
        stab = 0
    try:
        qty = float(d.get('quantity', 0))
    except (ValueError, TypeError):
        qty = 0.0
    with db_session() as conn:
        cur = conn.execute(
            'INSERT INTO fuel_storage (fuel_type, quantity, unit, container, location, stabilizer_added, date_stored, expires, notes) VALUES (?,?,?,?,?,?,?,?,?)',
            (d['fuel_type'].strip(), qty, d.get('unit','gallons'),
             d.get('container',''), d.get('location',''), stab,
             d.get('date_stored',''), d.get('expires',''), d.get('notes','')))
        conn.commit()
        row = conn.execute('SELECT * FROM fuel_storage WHERE id=?', (cur.lastrowid,)).fetchone()
        return jsonify(dict(row)), 201

@supplies_bp.route('/api/fuel/<int:fid>', methods=['PUT'])
def api_fuel_update(fid):
    d = request.json or {}
    if len(d.get('fuel_type', '') or '') > 200:
        return jsonify({'error': 'fuel_type too long (max 200)'}), 400
    try:
        stab = int(d.get('stabilizer_added', 0))
    except (ValueError, TypeError):
        stab = 0
    try:
        qty = float(d.get('quantity', 0))
    except (ValueError, TypeError):
        qty = 0.0
    with db_session() as conn:
        conn.execute(
            'UPDATE fuel_storage SET fuel_type=?,quantity=?,unit=?,container=?,location=?,stabilizer_added=?,date_stored=?,expires=?,notes=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',
            (d.get('fuel_type',''), qty, d.get('unit','gallons'),
             d.get('container',''), d.get('location',''), stab,
             d.get('date_stored',''), d.get('expires',''), d.get('notes',''), fid))
        conn.commit()
        row = conn.execute('SELECT * FROM fuel_storage WHERE id=?', (fid,)).fetchone()
        return jsonify(dict(row) if row else {})

@supplies_bp.route('/api/fuel/<int:fid>', methods=['DELETE'])
def api_fuel_delete(fid):
    with db_session() as conn:
        r = conn.execute('DELETE FROM fuel_storage WHERE id=?', (fid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        conn.commit()
        return jsonify({'ok': True})

@supplies_bp.route('/api/fuel/bulk-delete', methods=['POST'])
def api_fuel_bulk_delete():
    data, error = _require_json_body(request)
    if error:
        return error
    ids = _validate_bulk_ids(data)
    if ids is None:
        return jsonify({'error': 'ids array of integers required (max 100)'}), 400
    with db_session() as conn:
        placeholders = ','.join('?' * len(ids))
        r = conn.execute(f'DELETE FROM fuel_storage WHERE id IN ({placeholders})', ids)
        conn.commit()
    return jsonify({'status': 'deleted', 'count': r.rowcount})

@supplies_bp.route('/api/fuel/summary')
def api_fuel_summary():
    with db_session() as conn:
        rows = conn.execute('SELECT fuel_type, SUM(quantity) as total, unit FROM fuel_storage GROUP BY fuel_type, unit').fetchall()
        return jsonify([dict(r) for r in rows])


# ─── Equipment Maintenance ────────────────────────────────────────

@supplies_bp.route('/api/equipment')
def api_equipment_list():
    EQUIPMENT_SORT_FIELDS = {'name', 'category', 'status', 'next_service', 'created_at', 'updated_at'}
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
    except (ValueError, TypeError):
        limit = 50
    try:
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        offset = 0
    sort_by = request.args.get('sort_by', 'status')
    sort_dir = 'DESC' if request.args.get('sort_dir', 'asc').lower() == 'desc' else 'ASC'
    if sort_by not in EQUIPMENT_SORT_FIELDS:
        sort_by = 'status'
    with db_session() as conn:
        rows = conn.execute(f'SELECT * FROM equipment_log ORDER BY {sort_by} {sort_dir}, next_service ASC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
        return jsonify([dict(r) for r in rows])

@supplies_bp.route('/api/equipment', methods=['POST'])
def api_equipment_create():
    d = request.json or {}
    if len(d.get('name', '') or '') > 200:
        return jsonify({'error': 'name too long (max 200)'}), 400
    if not d.get('name', '').strip():
        return jsonify({'error': 'name is required'}), 400
    with db_session() as conn:
        cur = conn.execute(
            'INSERT INTO equipment_log (name, category, last_service, next_service, service_notes, status, location, notes) VALUES (?,?,?,?,?,?,?,?)',
            (d['name'].strip(), d.get('category','general'), d.get('last_service',''),
             d.get('next_service',''), d.get('service_notes',''), d.get('status','operational'),
             d.get('location',''), d.get('notes','')))
        conn.commit()
        row = conn.execute('SELECT * FROM equipment_log WHERE id=?', (cur.lastrowid,)).fetchone()
        return jsonify(dict(row)), 201

@supplies_bp.route('/api/equipment/<int:eid>', methods=['PUT'])
def api_equipment_update(eid):
    d = request.json or {}
    if len(d.get('name', '') or '') > 200:
        return jsonify({'error': 'name too long (max 200)'}), 400
    with db_session() as conn:
        conn.execute(
            'UPDATE equipment_log SET name=?,category=?,last_service=?,next_service=?,service_notes=?,status=?,location=?,notes=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',
            (d.get('name',''), d.get('category','general'), d.get('last_service',''),
             d.get('next_service',''), d.get('service_notes',''), d.get('status','operational'),
             d.get('location',''), d.get('notes',''), eid))
        conn.commit()
        row = conn.execute('SELECT * FROM equipment_log WHERE id=?', (eid,)).fetchone()
        return jsonify(dict(row) if row else {})

@supplies_bp.route('/api/equipment/<int:eid>', methods=['DELETE'])
def api_equipment_delete(eid):
    with db_session() as conn:
        r = conn.execute('DELETE FROM equipment_log WHERE id=?', (eid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        conn.commit()
        return jsonify({'ok': True})

@supplies_bp.route('/api/equipment/bulk-delete', methods=['POST'])
def api_equipment_bulk_delete():
    data, error = _require_json_body(request)
    if error:
        return error
    ids = _validate_bulk_ids(data)
    if ids is None:
        return jsonify({'error': 'ids array of integers required (max 100)'}), 400
    with db_session() as conn:
        placeholders = ','.join('?' * len(ids))
        r = conn.execute(f'DELETE FROM equipment_log WHERE id IN ({placeholders})', ids)
        conn.commit()
    return jsonify({'status': 'deleted', 'count': r.rowcount})

@supplies_bp.route('/api/equipment/export')
def api_equipment_export():
    with db_session() as conn:
        rows = conn.execute('SELECT * FROM equipment_log ORDER BY category, name LIMIT 10000').fetchall()
    data = [dict(r) for r in rows]
    return Response(json.dumps(data, indent=2, default=str),
                    mimetype='application/json',
                    headers={'Content-Disposition': 'attachment; filename=equipment_export.json'})

@supplies_bp.route('/api/equipment/import', methods=['POST'])
def api_equipment_import():
    data, error = _require_json_body(request)
    if error:
        return error
    if not isinstance(data, list):
        return jsonify({'error': 'expected JSON array'}), 400
    if len(data) > 1000:
        return jsonify({'error': 'max 1000 items'}), 400
    imported = 0
    with db_session() as conn:
        for item in data:
            conn.execute(
                'INSERT INTO equipment_log (name, category, last_service, next_service, service_notes, status, location, notes) VALUES (?,?,?,?,?,?,?,?)',
                (item.get('name', ''), item.get('category', 'general'),
                 item.get('last_service', ''), item.get('next_service', ''),
                 item.get('service_notes', ''), item.get('status', 'operational'),
                 item.get('location', ''), item.get('notes', '')))
            imported += 1
        conn.commit()
    return jsonify({'status': 'imported', 'count': imported})
