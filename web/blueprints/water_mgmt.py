"""Water management system routes."""

from flask import Blueprint, request, jsonify
from db import get_db, db_session, log_activity

water_mgmt_bp = Blueprint('water_mgmt', __name__)


# ─── Water Storage CRUD ─────────────────────────────────────────────

@water_mgmt_bp.route('/api/water/storage')
def api_water_storage_list():
    with db_session() as db:
        location = request.args.get('location')
        if location:
            rows = db.execute(
                'SELECT * FROM water_storage WHERE location = ? ORDER BY name',
                (location,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM water_storage ORDER BY name').fetchall()
    return jsonify([dict(r) for r in rows])


@water_mgmt_bp.route('/api/water/storage', methods=['POST'])
def api_water_storage_create():
    data = request.get_json() or {}
    if not data.get('name'):
        return jsonify({'error': 'Name required'}), 400
    with db_session() as db:
        db.execute(
            '''INSERT INTO water_storage
               (name, container_type, capacity_gallons, current_gallons,
                fill_date, treatment_method, location, expiration, notes)
               VALUES (?,?,?,?,?,?,?,?,?)''',
            (data['name'], data.get('container_type', ''),
             data.get('capacity_gallons', 0), data.get('current_gallons', 0),
             data.get('fill_date', ''), data.get('treatment_method', ''),
             data.get('location', ''), data.get('expiration', ''),
             data.get('notes', ''))
        )
        db.commit()
    log_activity('water_storage_added', detail=f"Added {data['name']}")
    return jsonify({'status': 'created'}), 201


@water_mgmt_bp.route('/api/water/storage/<int:sid>', methods=['PUT'])
def api_water_storage_update(sid):
    data = request.get_json() or {}
    allowed = ['name', 'container_type', 'capacity_gallons', 'current_gallons',
               'fill_date', 'treatment_method', 'location', 'expiration', 'notes']
    updates = []
    values = []
    for key in allowed:
        if key in data:
            updates.append(f'{key} = ?')
            values.append(data[key])
    if not updates:
        return jsonify({'error': 'No fields to update'}), 400
    with db_session() as db:
        if not db.execute('SELECT 1 FROM water_storage WHERE id = ?', (sid,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        values.append(sid)
        db.execute(
            f"UPDATE water_storage SET {', '.join(updates)}, updated_at = datetime('now') WHERE id = ?",
            values
        )
        db.commit()
    return jsonify({'status': 'updated'})


@water_mgmt_bp.route('/api/water/storage/<int:sid>', methods=['DELETE'])
def api_water_storage_delete(sid):
    with db_session() as db:
        r = db.execute('DELETE FROM water_storage WHERE id = ?', (sid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


# ─── Water Filters CRUD ─────────────────────────────────────────────

@water_mgmt_bp.route('/api/water/filters')
def api_water_filters_list():
    with db_session() as db:
        rows = db.execute('SELECT * FROM water_filters ORDER BY name').fetchall()
    return jsonify([dict(r) for r in rows])


@water_mgmt_bp.route('/api/water/filters', methods=['POST'])
def api_water_filters_create():
    data = request.get_json() or {}
    if not data.get('name'):
        return jsonify({'error': 'Name required'}), 400
    with db_session() as db:
        db.execute(
            '''INSERT INTO water_filters
               (name, filter_type, brand, max_gallons, gallons_processed,
                install_date, replacement_date, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?)''',
            (data['name'], data.get('filter_type', ''), data.get('brand', ''),
             data.get('max_gallons', 0), data.get('gallons_processed', 0),
             data.get('install_date', ''), data.get('replacement_date', ''),
             data.get('status', 'active'), data.get('notes', ''))
        )
        db.commit()
    log_activity('water_filter_added', detail=f"Added filter {data['name']}")
    return jsonify({'status': 'created'}), 201


@water_mgmt_bp.route('/api/water/filters/<int:fid>', methods=['PUT'])
def api_water_filters_update(fid):
    data = request.get_json() or {}
    allowed = ['name', 'filter_type', 'brand', 'max_gallons', 'gallons_processed',
               'install_date', 'replacement_date', 'status', 'notes']
    updates = []
    values = []
    for key in allowed:
        if key in data:
            updates.append(f'{key} = ?')
            values.append(data[key])
    if not updates:
        return jsonify({'error': 'No fields to update'}), 400
    with db_session() as db:
        if not db.execute('SELECT 1 FROM water_filters WHERE id = ?', (fid,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        values.append(fid)
        db.execute(
            f"UPDATE water_filters SET {', '.join(updates)}, updated_at = datetime('now') WHERE id = ?",
            values
        )
        db.commit()
    return jsonify({'status': 'updated'})


@water_mgmt_bp.route('/api/water/filters/<int:fid>', methods=['DELETE'])
def api_water_filters_delete(fid):
    with db_session() as db:
        r = db.execute('DELETE FROM water_filters WHERE id = ?', (fid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


# ─── Water Sources CRUD ─────────────────────────────────────────────

@water_mgmt_bp.route('/api/water/sources')
def api_water_sources_list():
    with db_session() as db:
        rows = db.execute('SELECT * FROM water_sources ORDER BY name').fetchall()
    return jsonify([dict(r) for r in rows])


@water_mgmt_bp.route('/api/water/sources', methods=['POST'])
def api_water_sources_create():
    data = request.get_json() or {}
    if not data.get('name'):
        return jsonify({'error': 'Name required'}), 400
    with db_session() as db:
        db.execute(
            '''INSERT INTO water_sources
               (name, source_type, lat, lng, waypoint_id, flow_rate_gph,
                potable, treatment_required, seasonal, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (data['name'], data.get('source_type', 'unknown'),
             data.get('lat'), data.get('lng'), data.get('waypoint_id'),
             data.get('flow_rate_gph', 0),
             1 if data.get('potable') else 0,
             1 if data.get('treatment_required', True) else 0,
             1 if data.get('seasonal') else 0,
             data.get('notes', ''))
        )
        db.commit()
    log_activity('water_source_added', detail=f"Added source {data['name']}")
    return jsonify({'status': 'created'}), 201


@water_mgmt_bp.route('/api/water/sources/<int:sid>', methods=['PUT'])
def api_water_sources_update(sid):
    data = request.get_json() or {}
    allowed = ['name', 'source_type', 'lat', 'lng', 'waypoint_id', 'flow_rate_gph',
               'potable', 'treatment_required', 'seasonal', 'notes']
    updates = []
    values = []
    for key in allowed:
        if key in data:
            updates.append(f'{key} = ?')
            val = data[key]
            if key in ('potable', 'treatment_required', 'seasonal'):
                val = 1 if val else 0
            values.append(val)
    if not updates:
        return jsonify({'error': 'No fields to update'}), 400
    with db_session() as db:
        if not db.execute('SELECT 1 FROM water_sources WHERE id = ?', (sid,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        values.append(sid)
        db.execute(
            f"UPDATE water_sources SET {', '.join(updates)}, updated_at = datetime('now') WHERE id = ?",
            values
        )
        db.commit()
    return jsonify({'status': 'updated'})


@water_mgmt_bp.route('/api/water/sources/<int:sid>', methods=['DELETE'])
def api_water_sources_delete(sid):
    with db_session() as db:
        r = db.execute('DELETE FROM water_sources WHERE id = ?', (sid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


# ─── Water Quality Tests ────────────────────────────────────────────

@water_mgmt_bp.route('/api/water/quality')
def api_water_quality_list():
    with db_session() as db:
        source_id = request.args.get('source_id')
        if source_id:
            rows = db.execute(
                'SELECT q.*, s.name as source_name FROM water_quality_tests q '
                'LEFT JOIN water_sources s ON q.source_id = s.id '
                'WHERE q.source_id = ? ORDER BY q.test_date DESC',
                (source_id,)
            ).fetchall()
        else:
            rows = db.execute(
                'SELECT q.*, s.name as source_name FROM water_quality_tests q '
                'LEFT JOIN water_sources s ON q.source_id = s.id '
                'ORDER BY q.test_date DESC'
            ).fetchall()
    return jsonify([dict(r) for r in rows])


@water_mgmt_bp.route('/api/water/quality', methods=['POST'])
def api_water_quality_create():
    data = request.get_json() or {}
    if not data.get('source_id'):
        return jsonify({'error': 'source_id required'}), 400
    with db_session() as db:
        if not db.execute('SELECT 1 FROM water_sources WHERE id = ?', (data['source_id'],)).fetchone():
            return jsonify({'error': 'Source not found'}), 404
        db.execute(
            '''INSERT INTO water_quality_tests
               (source_id, test_date, ph, tds_ppm, turbidity_ntu, coliform, notes)
               VALUES (?,?,?,?,?,?,?)''',
            (data['source_id'], data.get('test_date', ''),
             data.get('ph'), data.get('tds_ppm'), data.get('turbidity_ntu'),
             1 if data.get('coliform') else 0,
             data.get('notes', ''))
        )
        db.commit()
    log_activity('water_quality_test', detail=f"Tested source #{data['source_id']}")
    return jsonify({'status': 'created'}), 201


# ─── Dashboard ──────────────────────────────────────────────────────

def _get_household_size(db):
    row = db.execute("SELECT value FROM settings WHERE key = 'household_size'").fetchone()
    try:
        return int(row['value']) if row else 4
    except (TypeError, ValueError):
        return 4


@water_mgmt_bp.route('/api/water/dashboard')
def api_water_dashboard():
    with db_session() as db:
        # Storage totals
        storage = db.execute(
            'SELECT COALESCE(SUM(capacity_gallons), 0) as total_capacity, '
            'COALESCE(SUM(current_gallons), 0) as total_current '
            'FROM water_storage'
        ).fetchone()
        total_capacity = storage['total_capacity']
        total_current = storage['total_current']

        # Source count
        source_count = db.execute('SELECT COUNT(*) as cnt FROM water_sources').fetchone()['cnt']

        # Filters needing replacement (>80% used)
        filters_needing = db.execute(
            'SELECT COUNT(*) as cnt FROM water_filters '
            'WHERE max_gallons > 0 AND (CAST(gallons_processed AS REAL) / max_gallons) > 0.8'
        ).fetchone()['cnt']

        # Days of water estimate
        household_size = _get_household_size(db)
        daily_usage = household_size * 1.0
        days_of_water = round(total_current / daily_usage, 1) if daily_usage > 0 else 0

        # Latest quality tests (one per source)
        latest_tests = db.execute(
            'SELECT q.*, s.name as source_name FROM water_quality_tests q '
            'LEFT JOIN water_sources s ON q.source_id = s.id '
            'WHERE q.id IN (SELECT MAX(id) FROM water_quality_tests GROUP BY source_id) '
            'ORDER BY q.test_date DESC LIMIT 10'
        ).fetchall()

    return jsonify({
        'total_capacity': total_capacity,
        'total_current': total_current,
        'total_sources': source_count,
        'filters_needing_replacement': filters_needing,
        'household_size': household_size,
        'days_of_water': days_of_water,
        'latest_quality_tests': [dict(r) for r in latest_tests],
    })


# ─── Water Budget Calculator ────────────────────────────────────────

@water_mgmt_bp.route('/api/water/budget')
def api_water_budget():
    try:
        people = int(request.args.get('people', 4))
        days = int(request.args.get('days', 14))
    except (ValueError, TypeError):
        people, days = 4, 14

    drinking = round(0.5 * people * days, 2)
    cooking = round(0.25 * people * days, 2)
    hygiene = round(0.25 * people * days, 2)
    medical = round(0.1 * people * days, 2)
    total_needed = round(drinking + cooking + hygiene + medical, 2)

    with db_session() as db:
        row = db.execute(
            'SELECT COALESCE(SUM(current_gallons), 0) as total FROM water_storage'
        ).fetchone()
        total_available = row['total']

    surplus_deficit = round(total_available - total_needed, 2)

    return jsonify({
        'people': people,
        'days': days,
        'breakdown': {
            'drinking': drinking,
            'cooking': cooking,
            'hygiene': hygiene,
            'medical': medical,
        },
        'total_needed': total_needed,
        'total_available': total_available,
        'surplus_deficit': surplus_deficit,
        'status': 'surplus' if surplus_deficit >= 0 else 'deficit',
    })


# ─── Purification Reference ─────────────────────────────────────────

@water_mgmt_bp.route('/api/water/purification-reference')
def api_water_purification_reference():
    methods = [
        {
            'method': 'Boiling',
            'instructions': 'Rolling boil for 1 minute (3 min above 6,562 ft / 2,000 m)',
            'kills': 'Bacteria, viruses, protozoa',
            'limitations': 'Does not remove chemicals or heavy metals',
        },
        {
            'method': 'Bleach (sodium hypochlorite)',
            'instructions': '8 drops (1/8 tsp) per gallon of clear water, 16 drops for cloudy. Wait 30 min.',
            'kills': 'Bacteria, viruses',
            'limitations': 'Less effective against Cryptosporidium. Use unscented 5-8.25% bleach only.',
        },
        {
            'method': 'Iodine tablets',
            'instructions': '1 tablet per quart, wait 30 min (cold/cloudy water: 2 tablets, wait 60 min)',
            'kills': 'Bacteria, viruses, Giardia',
            'limitations': 'Not effective against Cryptosporidium. Not for pregnant women or thyroid conditions.',
        },
        {
            'method': 'UV (SteriPEN)',
            'instructions': 'Stir pen in 1L for 90 seconds',
            'kills': 'Bacteria, viruses, protozoa',
            'limitations': 'Requires clear water. Battery dependent.',
        },
        {
            'method': 'Filtration (0.1 micron)',
            'instructions': 'Pump or gravity-feed through filter',
            'kills': 'Bacteria, protozoa',
            'limitations': 'Most filters do NOT remove viruses. Check filter rating.',
        },
        {
            'method': 'SODIS (solar disinfection)',
            'instructions': 'Fill clear PET bottle, lay in direct sun for 6+ hours (2 days if cloudy)',
            'kills': 'Bacteria, viruses, protozoa',
            'limitations': 'Requires clear water and strong sunlight. Slow.',
        },
    ]
    return jsonify(methods)


# ─── Summary (external consumption) ─────────────────────────────────

@water_mgmt_bp.route('/api/water/summary')
def api_water_summary():
    with db_session() as db:
        storage = db.execute(
            'SELECT COALESCE(SUM(current_gallons), 0) as total FROM water_storage'
        ).fetchone()
        total_gallons = storage['total']

        filter_count = db.execute('SELECT COUNT(*) as cnt FROM water_filters').fetchone()['cnt']
        source_count = db.execute('SELECT COUNT(*) as cnt FROM water_sources').fetchone()['cnt']

        household_size = _get_household_size(db)
        daily_usage = household_size * 1.0
        days_estimate = round(total_gallons / daily_usage, 1) if daily_usage > 0 else 0

    return jsonify({
        'total_gallons_stored': total_gallons,
        'filter_count': filter_count,
        'source_count': source_count,
        'days_of_water_estimate': days_estimate,
    })
