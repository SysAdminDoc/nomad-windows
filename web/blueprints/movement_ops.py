"""Movement & Route Planning — march rates, convoy SOPs, alt vehicles,
route hazards/recon, vehicle loading plans, and go/no-go decision matrix."""

import logging
from flask import Blueprint, request, jsonify
from db import db_session, log_activity
from web.blueprints import get_pagination

_log = logging.getLogger(__name__)

movement_ops_bp = Blueprint('movement_ops', __name__)

ALT_VEHICLE_TYPES = [
    'bicycle', 'horse', 'mule', 'boat', 'canoe', 'kayak',
    'atv', 'motorcycle', 'cart', 'sled', 'other',
]
HAZARD_TYPES = [
    'bridge', 'tunnel', 'chokepoint', 'flood_zone', 'landslide',
    'roadblock', 'checkpoint', 'construction', 'washout', 'other',
]
PLAN_TYPES = ['foot', 'vehicle', 'convoy', 'mixed', 'waterborne']
ROAD_CONDITIONS = ['excellent', 'good', 'passable', 'degraded', 'impassable']
THREAT_LEVELS = ['none', 'low', 'moderate', 'elevated', 'high', 'extreme']


# ─── Movement Plans CRUD ─────────────────────────────────────────────

@movement_ops_bp.route('/api/movement-plans')
def api_movement_plans_list():
    plan_type = request.args.get('type', '').strip()
    status = request.args.get('status', '').strip()
    with db_session() as db:
        q = 'SELECT * FROM movement_plans WHERE 1=1'
        params = []
        if plan_type:
            q += ' AND plan_type = ?'
            params.append(plan_type)
        if status:
            q += ' AND status = ?'
            params.append(status)
        q += ' ORDER BY updated_at DESC'
        rows = db.execute(q, params).fetchall()
    return jsonify([dict(r) for r in rows])


@movement_ops_bp.route('/api/movement-plans', methods=['POST'])
def api_movement_plans_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    cols = [
        'name', 'plan_type', 'origin', 'origin_lat', 'origin_lng',
        'destination', 'destination_lat', 'destination_lng', 'distance_miles',
        'pace_count_per_100m', 'march_rate_mph', 'estimated_hours', 'rest_plan',
        'water_stops', 'waypoints', 'convoy_sop', 'convoy_order', 'comm_plan',
        'hand_signals', 'night_movement', 'vehicle_id', 'evac_plan_id',
        'status', 'notes',
    ]
    fields, vals = [], []
    for c in cols:
        if c in data:
            fields.append(c)
            vals.append(str(data[c]) if isinstance(data[c], (list, dict)) else data[c])
    placeholders = ','.join('?' * len(fields))
    with db_session() as db:
        cur = db.execute(
            f"INSERT INTO movement_plans ({','.join(fields)}) VALUES ({placeholders})", vals
        )
        db.commit()
        log_activity('movement_plan_created', detail=name)
        row = db.execute('SELECT * FROM movement_plans WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@movement_ops_bp.route('/api/movement-plans/<int:pid>')
def api_movement_plans_detail(pid):
    with db_session() as db:
        row = db.execute('SELECT * FROM movement_plans WHERE id = ?', (pid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(row))


@movement_ops_bp.route('/api/movement-plans/<int:pid>', methods=['PUT'])
def api_movement_plans_update(pid):
    data = request.get_json() or {}
    allowed = [
        'name', 'plan_type', 'origin', 'origin_lat', 'origin_lng',
        'destination', 'destination_lat', 'destination_lng', 'distance_miles',
        'pace_count_per_100m', 'march_rate_mph', 'estimated_hours', 'rest_plan',
        'water_stops', 'waypoints', 'convoy_sop', 'convoy_order', 'comm_plan',
        'hand_signals', 'night_movement', 'vehicle_id', 'evac_plan_id',
        'status', 'notes',
    ]
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            vals.append(str(data[k]) if isinstance(data[k], (list, dict)) else data[k])
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append("updated_at = CURRENT_TIMESTAMP")
    vals.append(pid)
    with db_session() as db:
        db.execute(f"UPDATE movement_plans SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM movement_plans WHERE id = ?', (pid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    log_activity('movement_plan_updated', detail=row['name'])
    return jsonify(dict(row))


@movement_ops_bp.route('/api/movement-plans/<int:pid>', methods=['DELETE'])
def api_movement_plans_delete(pid):
    with db_session() as db:
        row = db.execute('SELECT name FROM movement_plans WHERE id = ?', (pid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM route_hazards WHERE movement_plan_id = ?', (pid,))
        db.execute('DELETE FROM route_recon WHERE movement_plan_id = ?', (pid,))
        db.execute('DELETE FROM movement_plans WHERE id = ?', (pid,))
        db.commit()
        log_activity('movement_plan_deleted', detail=row['name'])
    return jsonify({'ok': True})


# ─── March Rate Calculator ───────────────────────────────────────────

@movement_ops_bp.route('/api/movement/march-rate', methods=['POST'])
def api_march_rate_calc():
    """Calculate march time: distance / rate with rest stops factored in."""
    data = request.get_json() or {}
    distance = float(data.get('distance_miles', 0))
    rate = float(data.get('march_rate_mph', 3.0))
    rest_min_per_hour = int(data.get('rest_min_per_hour', 10))
    load_lb = float(data.get('load_lb', 0))
    terrain = data.get('terrain', 'road')
    # Terrain multipliers
    terrain_mult = {'road': 1.0, 'trail': 0.85, 'cross_country': 0.6,
                    'mountain': 0.4, 'swamp': 0.3, 'snow': 0.5}
    mult = terrain_mult.get(terrain, 1.0)
    # Load penalty: -5% per 10 lb over 30 lb
    if load_lb > 30:
        load_penalty = max(0.3, 1.0 - ((load_lb - 30) / 10) * 0.05)
        mult *= load_penalty
    effective_rate = rate * mult
    if effective_rate <= 0:
        return jsonify({'error': 'effective rate is zero'}), 400
    moving_hours = distance / effective_rate
    # Factor in rest: e.g., 10 min rest per 50 min moving
    move_fraction = (60 - rest_min_per_hour) / 60.0
    total_hours = moving_hours / move_fraction if move_fraction > 0 else moving_hours
    return jsonify({
        'distance_miles': distance,
        'effective_rate_mph': round(effective_rate, 2),
        'terrain_multiplier': mult,
        'moving_hours': round(moving_hours, 2),
        'total_hours': round(total_hours, 2),
        'arrival_estimate': f"{int(total_hours)}h {int((total_hours % 1) * 60)}m",
    })


# ─── Pace Count Calculator ──────────────────────────────────────────

@movement_ops_bp.route('/api/movement/pace-count', methods=['POST'])
def api_pace_count_calc():
    """Convert distance using personal pace count."""
    data = request.get_json() or {}
    pace_per_100m = int(data.get('pace_per_100m', 65))
    distance_m = float(data.get('distance_meters', 0))
    if pace_per_100m <= 0:
        return jsonify({'error': 'invalid pace count'}), 400
    total_paces = (distance_m / 100.0) * pace_per_100m
    return jsonify({
        'distance_meters': distance_m,
        'pace_per_100m': pace_per_100m,
        'total_paces': round(total_paces),
        'beads_dropped': int(total_paces / pace_per_100m),
    })


# ─── Alternative Vehicles CRUD ───────────────────────────────────────

@movement_ops_bp.route('/api/alt-vehicles')
def api_alt_vehicles_list():
    vtype = request.args.get('type', '').strip()
    with db_session() as db:
        if vtype:
            rows = db.execute(
                'SELECT * FROM alt_vehicles WHERE vehicle_type = ? ORDER BY name', (vtype,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM alt_vehicles ORDER BY name LIMIT ? OFFSET ?', get_pagination()).fetchall()
    return jsonify([dict(r) for r in rows])


@movement_ops_bp.route('/api/alt-vehicles', methods=['POST'])
def api_alt_vehicles_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO alt_vehicles
               (name, vehicle_type, capacity_lb, range_miles, speed_mph,
                fuel_type, fuel_consumption, feed_requirements, condition,
                maintenance_due, storage_location, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('vehicle_type', 'bicycle'),
             data.get('capacity_lb', 0), data.get('range_miles', 0),
             data.get('speed_mph', 0), data.get('fuel_type', 'human'),
             data.get('fuel_consumption', ''), data.get('feed_requirements', ''),
             data.get('condition', 'good'), data.get('maintenance_due', ''),
             data.get('storage_location', ''), data.get('notes', ''))
        )
        db.commit()
        log_activity('alt_vehicle_created', detail=name)
        row = db.execute('SELECT * FROM alt_vehicles WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@movement_ops_bp.route('/api/alt-vehicles/<int:vid>', methods=['PUT'])
def api_alt_vehicles_update(vid):
    data = request.get_json() or {}
    allowed = [
        'name', 'vehicle_type', 'capacity_lb', 'range_miles', 'speed_mph',
        'fuel_type', 'fuel_consumption', 'feed_requirements', 'condition',
        'maintenance_due', 'storage_location', 'notes',
    ]
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            vals.append(data[k])
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append("updated_at = CURRENT_TIMESTAMP")
    vals.append(vid)
    with db_session() as db:
        db.execute(f"UPDATE alt_vehicles SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM alt_vehicles WHERE id = ?', (vid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    log_activity('alt_vehicle_updated', detail=row['name'])
    return jsonify(dict(row))


@movement_ops_bp.route('/api/alt-vehicles/<int:vid>', methods=['DELETE'])
def api_alt_vehicles_delete(vid):
    with db_session() as db:
        row = db.execute('SELECT name FROM alt_vehicles WHERE id = ?', (vid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM alt_vehicles WHERE id = ?', (vid,))
        db.commit()
        log_activity('alt_vehicle_deleted', detail=row['name'])
    return jsonify({'ok': True})


# ─── Route Hazards CRUD ─────────────────────────────────────────────

@movement_ops_bp.route('/api/route-hazards')
def api_route_hazards_list():
    plan_id = request.args.get('movement_plan_id', type=int)
    with db_session() as db:
        if plan_id:
            rows = db.execute(
                'SELECT * FROM route_hazards WHERE movement_plan_id = ? ORDER BY severity DESC',
                (plan_id,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM route_hazards ORDER BY created_at DESC LIMIT ? OFFSET ?', get_pagination()).fetchall()
    return jsonify([dict(r) for r in rows])


@movement_ops_bp.route('/api/route-hazards', methods=['POST'])
def api_route_hazards_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO route_hazards
               (movement_plan_id, name, hazard_type, lat, lng, severity,
                description, bypass_route, seasonal, active_months,
                last_verified, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (data.get('movement_plan_id'), name,
             data.get('hazard_type', 'chokepoint'),
             data.get('lat'), data.get('lng'),
             data.get('severity', 'moderate'),
             data.get('description', ''), data.get('bypass_route', ''),
             data.get('seasonal', 0), data.get('active_months', ''),
             data.get('last_verified', ''), data.get('notes', ''))
        )
        db.commit()
        log_activity('route_hazard_created', detail=name)
        row = db.execute('SELECT * FROM route_hazards WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@movement_ops_bp.route('/api/route-hazards/<int:hid>', methods=['PUT'])
def api_route_hazards_update(hid):
    data = request.get_json() or {}
    allowed = [
        'movement_plan_id', 'name', 'hazard_type', 'lat', 'lng', 'severity',
        'description', 'bypass_route', 'seasonal', 'active_months',
        'last_verified', 'notes',
    ]
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            vals.append(data[k])
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    vals.append(hid)
    with db_session() as db:
        db.execute(f"UPDATE route_hazards SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM route_hazards WHERE id = ?', (hid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(row))


@movement_ops_bp.route('/api/route-hazards/<int:hid>', methods=['DELETE'])
def api_route_hazards_delete(hid):
    with db_session() as db:
        row = db.execute('SELECT name FROM route_hazards WHERE id = ?', (hid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM route_hazards WHERE id = ?', (hid,))
        db.commit()
        log_activity('route_hazard_deleted', detail=row['name'])
    return jsonify({'ok': True})


# ─── Route Recon CRUD ───────────────────────────────────────────────

@movement_ops_bp.route('/api/route-recon')
def api_route_recon_list():
    plan_id = request.args.get('movement_plan_id', type=int)
    with db_session() as db:
        if plan_id:
            rows = db.execute(
                'SELECT * FROM route_recon WHERE movement_plan_id = ? ORDER BY recon_date DESC',
                (plan_id,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM route_recon ORDER BY recon_date DESC LIMIT ? OFFSET ?', get_pagination()).fetchall()
    return jsonify([dict(r) for r in rows])


@movement_ops_bp.route('/api/route-recon', methods=['POST'])
def api_route_recon_create():
    data = request.get_json() or {}
    recon_date = (data.get('recon_date') or '').strip()
    if not recon_date:
        return jsonify({'error': 'recon_date is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO route_recon
               (movement_plan_id, recon_date, observer, road_condition,
                bridge_status, water_crossings, obstacles, threat_level,
                population_density, fuel_available, water_available,
                shelter_available, photos, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (data.get('movement_plan_id'), recon_date,
             data.get('observer', ''), data.get('road_condition', 'passable'),
             data.get('bridge_status', 'intact'),
             str(data.get('water_crossings', '[]')),
             str(data.get('obstacles', '[]')),
             data.get('threat_level', 'low'),
             data.get('population_density', 'rural'),
             data.get('fuel_available', 0), data.get('water_available', 0),
             data.get('shelter_available', 0),
             str(data.get('photos', '[]')), data.get('notes', ''))
        )
        db.commit()
        log_activity('route_recon_created', detail=f"Recon {recon_date}")
        row = db.execute('SELECT * FROM route_recon WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@movement_ops_bp.route('/api/route-recon/<int:rid>', methods=['DELETE'])
def api_route_recon_delete(rid):
    with db_session() as db:
        row = db.execute('SELECT id FROM route_recon WHERE id = ?', (rid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM route_recon WHERE id = ?', (rid,))
        db.commit()
        log_activity('route_recon_deleted', detail=str(rid))
    return jsonify({'ok': True})


# ─── Vehicle Loading Plans CRUD ─────────────────────────────────────

@movement_ops_bp.route('/api/vehicle-loading')
def api_vehicle_loading_list():
    evac_id = request.args.get('evac_plan_id', type=int)
    with db_session() as db:
        if evac_id:
            rows = db.execute(
                'SELECT * FROM vehicle_loading_plans WHERE evac_plan_id = ? ORDER BY load_order',
                (evac_id,)
            ).fetchall()
        else:
            rows = db.execute(
                'SELECT * FROM vehicle_loading_plans ORDER BY created_at DESC'
            ).fetchall()
    return jsonify([dict(r) for r in rows])


@movement_ops_bp.route('/api/vehicle-loading', methods=['POST'])
def api_vehicle_loading_create():
    data = request.get_json() or {}
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO vehicle_loading_plans
               (evac_plan_id, vehicle_id, vehicle_name, load_order,
                assigned_persons, assigned_bags, assigned_items,
                total_weight_lb, max_weight_lb, fuel_level_pct, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            (data.get('evac_plan_id'), data.get('vehicle_id'),
             data.get('vehicle_name', ''), data.get('load_order', 0),
             str(data.get('assigned_persons', '[]')),
             str(data.get('assigned_bags', '[]')),
             str(data.get('assigned_items', '[]')),
             data.get('total_weight_lb', 0), data.get('max_weight_lb', 0),
             data.get('fuel_level_pct', 100), data.get('notes', ''))
        )
        db.commit()
        log_activity('vehicle_loading_created', detail=data.get('vehicle_name', ''))
        row = db.execute(
            'SELECT * FROM vehicle_loading_plans WHERE id = ?', (cur.lastrowid,)
        ).fetchone()
    return jsonify(dict(row)), 201


@movement_ops_bp.route('/api/vehicle-loading/<int:lid>', methods=['PUT'])
def api_vehicle_loading_update(lid):
    data = request.get_json() or {}
    allowed = [
        'evac_plan_id', 'vehicle_id', 'vehicle_name', 'load_order',
        'assigned_persons', 'assigned_bags', 'assigned_items',
        'total_weight_lb', 'max_weight_lb', 'fuel_level_pct', 'notes',
    ]
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            v = data[k]
            vals.append(str(v) if isinstance(v, (list, dict)) else v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append("updated_at = CURRENT_TIMESTAMP")
    vals.append(lid)
    with db_session() as db:
        db.execute(f"UPDATE vehicle_loading_plans SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM vehicle_loading_plans WHERE id = ?', (lid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(row))


@movement_ops_bp.route('/api/vehicle-loading/<int:lid>', methods=['DELETE'])
def api_vehicle_loading_delete(lid):
    with db_session() as db:
        row = db.execute('SELECT id FROM vehicle_loading_plans WHERE id = ?', (lid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM vehicle_loading_plans WHERE id = ?', (lid,))
        db.commit()
        log_activity('vehicle_loading_deleted', detail=str(lid))
    return jsonify({'ok': True})


# ─── Go/No-Go Decision Matrix ──────────────────────────────────────

@movement_ops_bp.route('/api/go-nogo')
def api_go_nogo_list():
    evac_id = request.args.get('evac_plan_id', type=int)
    with db_session() as db:
        if evac_id:
            rows = db.execute(
                'SELECT * FROM go_nogo_matrix WHERE evac_plan_id = ? ORDER BY weight DESC',
                (evac_id,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM go_nogo_matrix ORDER BY created_at DESC').fetchall()
    return jsonify([dict(r) for r in rows])


@movement_ops_bp.route('/api/go-nogo', methods=['POST'])
def api_go_nogo_create():
    data = request.get_json() or {}
    criterion = (data.get('criterion') or '').strip()
    if not criterion:
        return jsonify({'error': 'criterion is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO go_nogo_matrix
               (evac_plan_id, criterion, category, weight,
                go_threshold, nogo_threshold, current_value,
                current_status, data_source, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (data.get('evac_plan_id'), criterion,
             data.get('category', 'security'), data.get('weight', 1.0),
             data.get('go_threshold', ''), data.get('nogo_threshold', ''),
             data.get('current_value', ''), data.get('current_status', 'unknown'),
             data.get('data_source', 'manual'), data.get('notes', ''))
        )
        db.commit()
        log_activity('go_nogo_created', detail=criterion)
        row = db.execute('SELECT * FROM go_nogo_matrix WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@movement_ops_bp.route('/api/go-nogo/<int:gid>', methods=['PUT'])
def api_go_nogo_update(gid):
    data = request.get_json() or {}
    allowed = [
        'evac_plan_id', 'criterion', 'category', 'weight',
        'go_threshold', 'nogo_threshold', 'current_value',
        'current_status', 'data_source', 'last_updated', 'notes',
    ]
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            vals.append(data[k])
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    vals.append(gid)
    with db_session() as db:
        db.execute(f"UPDATE go_nogo_matrix SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM go_nogo_matrix WHERE id = ?', (gid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(row))


@movement_ops_bp.route('/api/go-nogo/<int:gid>', methods=['DELETE'])
def api_go_nogo_delete(gid):
    with db_session() as db:
        row = db.execute('SELECT id FROM go_nogo_matrix WHERE id = ?', (gid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM go_nogo_matrix WHERE id = ?', (gid,))
        db.commit()
        log_activity('go_nogo_deleted', detail=str(gid))
    return jsonify({'ok': True})


@movement_ops_bp.route('/api/go-nogo/evaluate')
def api_go_nogo_evaluate():
    """Evaluate all criteria for an evac plan and return go/no-go recommendation."""
    evac_id = request.args.get('evac_plan_id', type=int)
    if not evac_id:
        return jsonify({'error': 'evac_plan_id required'}), 400
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM go_nogo_matrix WHERE evac_plan_id = ?', (evac_id,)
        ).fetchall()
    if not rows:
        return jsonify({'recommendation': 'unknown', 'criteria': [],
                        'message': 'No criteria defined'})
    criteria = [dict(r) for r in rows]
    total_weight = sum(c['weight'] for c in criteria)
    go_score = sum(c['weight'] for c in criteria if c['current_status'] == 'go')
    nogo_count = sum(1 for c in criteria if c['current_status'] == 'nogo')
    unknown_count = sum(1 for c in criteria if c['current_status'] == 'unknown')
    pct = (go_score / total_weight * 100) if total_weight > 0 else 0
    if nogo_count > 0:
        rec = 'NO-GO'
        msg = f'{nogo_count} criteria flagged NO-GO'
    elif unknown_count > len(criteria) * 0.3:
        rec = 'HOLD'
        msg = f'{unknown_count} criteria still unverified'
    elif pct >= 80:
        rec = 'GO'
        msg = f'{pct:.0f}% criteria met'
    else:
        rec = 'HOLD'
        msg = f'Only {pct:.0f}% criteria met — recommend waiting'
    return jsonify({
        'recommendation': rec,
        'go_percentage': round(pct, 1),
        'nogo_count': nogo_count,
        'unknown_count': unknown_count,
        'total_criteria': len(criteria),
        'message': msg,
        'criteria': criteria,
    })


# ─── Movement Summary ───────────────────────────────────────────────

@movement_ops_bp.route('/api/movement/summary')
def api_movement_summary():
    with db_session() as db:
        plans = db.execute('SELECT COUNT(*) FROM movement_plans').fetchone()[0]
        active = db.execute(
            "SELECT COUNT(*) FROM movement_plans WHERE status = 'active'"
        ).fetchone()[0]
        alt_v = db.execute('SELECT COUNT(*) FROM alt_vehicles').fetchone()[0]
        hazards = db.execute('SELECT COUNT(*) FROM route_hazards').fetchone()[0]
        recon = db.execute('SELECT COUNT(*) FROM route_recon').fetchone()[0]
        loading = db.execute('SELECT COUNT(*) FROM vehicle_loading_plans').fetchone()[0]
    return jsonify({
        'total_plans': plans,
        'active_plans': active,
        'alt_vehicles': alt_v,
        'route_hazards': hazards,
        'recon_entries': recon,
        'loading_plans': loading,
    })
