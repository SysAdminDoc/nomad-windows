"""Vehicle & Bug-Out Vehicle Manager — CRUD, maintenance, fuel log, and readiness calculators."""

import logging
from datetime import timedelta

from flask import Blueprint, request, jsonify

from db import db_session, log_activity
from web.validation import validate_json
from web.utils import utc_now as _utc_now

# Audit H2 — vehicle data validation.
#
# The base schemas are partial-update-friendly (no `required` fields).
# Separate `_CREATE` schemas layer `required=True` on top for the POST
# routes. This mirrors the pattern in contacts.py / inventory.py and
# fixes the bug where PUT used to reject partial updates that omitted
# `name` / `service_type`.
_VEHICLE_SCHEMA = {
    'name': {'type': str, 'min_length': 1, 'max_length': 200},
    'year': {'type': int, 'min': 1900, 'max': 2100},
    'make': {'type': str, 'max_length': 100},
    'model': {'type': str, 'max_length': 100},
    'vin': {'type': str, 'max_length': 30},
    'fuel_type': {'type': str, 'max_length': 30},
    'tank_capacity_gal': {'type': (int, float), 'min': 0, 'max': 10000},
    'mpg': {'type': (int, float), 'min': 0, 'max': 1000},
    'odometer': {'type': (int, float), 'min': 0, 'max': 10_000_000},
    'color': {'type': str, 'max_length': 50},
    'plate': {'type': str, 'max_length': 20},
    'insurance_exp': {'type': str, 'max_length': 50},
    'registration_exp': {'type': str, 'max_length': 50},
    'location': {'type': str, 'max_length': 200},
    'role': {'type': str, 'max_length': 50},
    'notes': {'type': str, 'max_length': 5000},
}
_VEHICLE_CREATE_SCHEMA = dict(
    _VEHICLE_SCHEMA,
    name={'type': str, 'required': True, 'max_length': 200},
)
_MAINTENANCE_SCHEMA = {
    'service_type': {'type': str, 'min_length': 1, 'max_length': 100},
    'service_date': {'type': str, 'max_length': 50},
    'mileage': {'type': (int, float), 'min': 0, 'max': 10_000_000},
    'next_due_mileage': {'type': (int, float), 'min': 0, 'max': 10_000_000},
    'next_due_date': {'type': str, 'max_length': 50},
    'cost': {'type': (int, float), 'min': 0, 'max': 1_000_000},
    'notes': {'type': str, 'max_length': 2000},
}
_MAINTENANCE_CREATE_SCHEMA = dict(
    _MAINTENANCE_SCHEMA,
    service_type={'type': str, 'required': True, 'max_length': 100},
)
from web.sql_safety import safe_columns

_log = logging.getLogger(__name__)

vehicles_bp = Blueprint('vehicles', __name__)

VEHICLE_ALLOWED = [
    'name', 'year', 'make', 'model', 'vin', 'fuel_type', 'tank_capacity_gal',
    'mpg', 'odometer', 'color', 'plate', 'insurance_exp', 'registration_exp',
    'location', 'role', 'notes',
]
MAINTENANCE_ALLOWED = [
    'service_type', 'description', 'mileage', 'cost', 'service_date',
    'next_due_date', 'next_due_mileage', 'status', 'notes',
]
VALID_FUEL_TYPES = {'gasoline', 'diesel', 'electric', 'hybrid', 'propane'}
VALID_ROLES = {'daily', 'bugout', 'backup', 'utility'}
VALID_MAINT_STATUSES = {'completed', 'scheduled', 'overdue'}


# ─── Vehicle CRUD ────────────────────────────────────────────────────

@vehicles_bp.route('/api/vehicles')
def api_vehicles_list():
    role = request.args.get('role', '').strip()
    with db_session() as db:
        if role:
            rows = db.execute(
                'SELECT * FROM vehicles WHERE role = ? ORDER BY name', (role,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM vehicles ORDER BY name').fetchall()
    return jsonify([dict(r) for r in rows])


@vehicles_bp.route('/api/vehicles', methods=['POST'])
@validate_json(_VEHICLE_CREATE_SCHEMA)
def api_vehicles_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    fuel_type = data.get('fuel_type', 'gasoline')
    if fuel_type not in VALID_FUEL_TYPES:
        return jsonify({'error': f'fuel_type must be one of {sorted(VALID_FUEL_TYPES)}'}), 400
    role = data.get('role', 'daily')
    if role not in VALID_ROLES:
        return jsonify({'error': f'role must be one of {sorted(VALID_ROLES)}'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO vehicles
               (name, year, make, model, vin, fuel_type, tank_capacity_gal, mpg,
                odometer, color, plate, insurance_exp, registration_exp,
                location, role, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (name, data.get('year'), data.get('make', ''), data.get('model', ''),
             data.get('vin', ''), fuel_type,
             data.get('tank_capacity_gal'), data.get('mpg'),
             data.get('odometer', 0), data.get('color', ''), data.get('plate', ''),
             data.get('insurance_exp', ''), data.get('registration_exp', ''),
             data.get('location', ''), role, data.get('notes', '')))
        db.commit()
        row = db.execute('SELECT * FROM vehicles WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('vehicle_created', service='vehicles', detail=f'{name} ({role})')
    return jsonify(dict(row)), 201


@vehicles_bp.route('/api/vehicles/<int:vid>')
def api_vehicles_get(vid):
    with db_session() as db:
        vehicle = db.execute('SELECT * FROM vehicles WHERE id = ?', (vid,)).fetchone()
        if not vehicle:
            return jsonify({'error': 'not found'}), 404
        maintenance = db.execute(
            'SELECT * FROM vehicle_maintenance WHERE vehicle_id = ? ORDER BY service_date DESC',
            (vid,)
        ).fetchall()
        fuel_rows = db.execute(
            'SELECT * FROM vehicle_fuel_log WHERE vehicle_id = ? ORDER BY fuel_date DESC',
            (vid,)
        ).fetchall()
        # Fuel stats
        fuel_stats = {'total_entries': 0, 'total_gallons': 0.0, 'total_cost': 0.0}
        for f in fuel_rows:
            fuel_stats['total_entries'] += 1
            fuel_stats['total_gallons'] += f['gallons'] or 0.0
            fuel_stats['total_cost'] += f['total_cost'] or 0.0
        fuel_stats['total_gallons'] = round(fuel_stats['total_gallons'], 2)
        fuel_stats['total_cost'] = round(fuel_stats['total_cost'], 2)
    result = dict(vehicle)
    result['maintenance'] = [dict(m) for m in maintenance]
    result['fuel_stats'] = fuel_stats
    return jsonify(result)


@vehicles_bp.route('/api/vehicles/<int:vid>', methods=['PUT'])
@validate_json(_VEHICLE_SCHEMA)
def api_vehicles_update(vid):
    data = request.get_json() or {}
    if 'fuel_type' in data and data['fuel_type'] not in VALID_FUEL_TYPES:
        return jsonify({'error': f'fuel_type must be one of {sorted(VALID_FUEL_TYPES)}'}), 400
    if 'role' in data and data['role'] not in VALID_ROLES:
        return jsonify({'error': f'role must be one of {sorted(VALID_ROLES)}'}), 400
    with db_session() as db:
        if not db.execute('SELECT 1 FROM vehicles WHERE id = ?', (vid,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        filtered = safe_columns(data, VEHICLE_ALLOWED)
        if not filtered:
            return jsonify({'error': 'No valid fields provided'}), 400
        set_clause = ', '.join(f'{col} = ?' for col in filtered)
        vals = list(filtered.values())
        vals.append(vid)
        db.execute(
            f'UPDATE vehicles SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            vals
        )
        db.commit()
        row = db.execute('SELECT * FROM vehicles WHERE id = ?', (vid,)).fetchone()
    log_activity('vehicle_updated', service='vehicles', detail=f'id={vid}')
    return jsonify(dict(row))


@vehicles_bp.route('/api/vehicles/<int:vid>', methods=['DELETE'])
def api_vehicles_delete(vid):
    with db_session() as db:
        if not db.execute('SELECT 1 FROM vehicles WHERE id = ?', (vid,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM vehicle_fuel_log WHERE vehicle_id = ?', (vid,))
        db.execute('DELETE FROM vehicle_maintenance WHERE vehicle_id = ?', (vid,))
        db.execute('DELETE FROM vehicles WHERE id = ?', (vid,))
        db.commit()
    log_activity('vehicle_deleted', service='vehicles', detail=f'id={vid}')
    return jsonify({'status': 'deleted'})


# ─── Maintenance CRUD ────────────────────────────────────────────────

@vehicles_bp.route('/api/vehicles/<int:vid>/maintenance')
def api_maintenance_list(vid):
    with db_session() as db:
        if not db.execute('SELECT 1 FROM vehicles WHERE id = ?', (vid,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        rows = db.execute(
            'SELECT * FROM vehicle_maintenance WHERE vehicle_id = ? ORDER BY service_date DESC',
            (vid,)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@vehicles_bp.route('/api/vehicles/<int:vid>/maintenance', methods=['POST'])
@validate_json(_MAINTENANCE_CREATE_SCHEMA)
def api_maintenance_create(vid):
    data = request.get_json() or {}
    service_type = (data.get('service_type') or '').strip()
    if not service_type:
        return jsonify({'error': 'service_type is required'}), 400
    status = data.get('status', 'completed')
    if status not in VALID_MAINT_STATUSES:
        return jsonify({'error': f'status must be one of {sorted(VALID_MAINT_STATUSES)}'}), 400
    with db_session() as db:
        if not db.execute('SELECT 1 FROM vehicles WHERE id = ?', (vid,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        cur = db.execute(
            '''INSERT INTO vehicle_maintenance
               (vehicle_id, service_type, description, mileage, cost,
                service_date, next_due_date, next_due_mileage, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (vid, service_type, data.get('description', ''),
             data.get('mileage'), data.get('cost'),
             data.get('service_date', ''), data.get('next_due_date', ''),
             data.get('next_due_mileage'), status, data.get('notes', ''))
        )
        db.commit()
        row = db.execute(
            'SELECT * FROM vehicle_maintenance WHERE id = ?', (cur.lastrowid,)
        ).fetchone()
    return jsonify(dict(row)), 201


@vehicles_bp.route('/api/vehicles/maintenance/<int:mid>', methods=['PUT'])
@validate_json(_MAINTENANCE_SCHEMA)
def api_maintenance_update(mid):
    data = request.get_json() or {}
    if 'status' in data and data['status'] not in VALID_MAINT_STATUSES:
        return jsonify({'error': f'status must be one of {sorted(VALID_MAINT_STATUSES)}'}), 400
    with db_session() as db:
        if not db.execute('SELECT 1 FROM vehicle_maintenance WHERE id = ?', (mid,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        filtered = safe_columns(data, MAINTENANCE_ALLOWED)
        if not filtered:
            return jsonify({'error': 'No valid fields provided'}), 400
        set_clause = ', '.join(f'{col} = ?' for col in filtered)
        vals = list(filtered.values())
        vals.append(mid)
        db.execute(
            f'UPDATE vehicle_maintenance SET {set_clause} WHERE id = ?', vals
        )
        db.commit()
        row = db.execute(
            'SELECT * FROM vehicle_maintenance WHERE id = ?', (mid,)
        ).fetchone()
    return jsonify(dict(row))


@vehicles_bp.route('/api/vehicles/maintenance/<int:mid>', methods=['DELETE'])
def api_maintenance_delete(mid):
    with db_session() as db:
        r = db.execute('DELETE FROM vehicle_maintenance WHERE id = ?', (mid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


# ─── Fuel Log ────────────────────────────────────────────────────────

@vehicles_bp.route('/api/vehicles/<int:vid>/fuel')
def api_fuel_list(vid):
    with db_session() as db:
        if not db.execute('SELECT 1 FROM vehicles WHERE id = ?', (vid,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        rows = db.execute(
            'SELECT * FROM vehicle_fuel_log WHERE vehicle_id = ? ORDER BY fuel_date DESC',
            (vid,)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@vehicles_bp.route('/api/vehicles/<int:vid>/fuel', methods=['POST'])
def api_fuel_create(vid):
    data = request.get_json() or {}
    gallons = data.get('gallons')
    if gallons is None:
        return jsonify({'error': 'gallons is required'}), 400
    try:
        gallons = float(gallons)
    except (ValueError, TypeError):
        return jsonify({'error': 'gallons must be a number'}), 400
    cost_per_gallon = data.get('cost_per_gallon')
    if cost_per_gallon is not None:
        try:
            cost_per_gallon = float(cost_per_gallon)
        except (ValueError, TypeError):
            return jsonify({'error': 'cost_per_gallon must be a number'}), 400
    total_cost = data.get('total_cost')
    if total_cost is not None:
        try:
            total_cost = float(total_cost)
        except (ValueError, TypeError):
            return jsonify({'error': 'total_cost must be a number'}), 400
    # Auto-calculate total_cost if not provided
    if total_cost is None and cost_per_gallon is not None:
        total_cost = round(gallons * cost_per_gallon, 2)
    with db_session() as db:
        if not db.execute('SELECT 1 FROM vehicles WHERE id = ?', (vid,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        cur = db.execute(
            '''INSERT INTO vehicle_fuel_log
               (vehicle_id, gallons, cost_per_gallon, total_cost,
                odometer, station, fuel_date, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (vid, gallons, cost_per_gallon, total_cost,
             data.get('odometer'), data.get('station', ''),
             data.get('fuel_date', ''), data.get('notes', ''))
        )
        db.commit()
        row = db.execute(
            'SELECT * FROM vehicle_fuel_log WHERE id = ?', (cur.lastrowid,)
        ).fetchone()
    return jsonify(dict(row)), 201


# ─── Calculators ─────────────────────────────────────────────────────

@vehicles_bp.route('/api/vehicles/<int:vid>/range')
def api_vehicles_range(vid):
    with db_session() as db:
        vehicle = db.execute('SELECT * FROM vehicles WHERE id = ?', (vid,)).fetchone()
        if not vehicle:
            return jsonify({'error': 'not found'}), 404
        tank = vehicle['tank_capacity_gal'] or 0.0
        mpg = vehicle['mpg'] or 0.0
        max_range = round(tank * mpg, 1)
        # Estimate current fuel based on last fill-up and miles driven since
        current_fuel_estimate = None
        miles_since_fill = None
        last_fill = db.execute(
            'SELECT * FROM vehicle_fuel_log WHERE vehicle_id = ? AND odometer IS NOT NULL ORDER BY fuel_date DESC LIMIT 1',
            (vid,)
        ).fetchone()
        if last_fill and vehicle['odometer'] and last_fill['odometer']:
            miles_since_fill = vehicle['odometer'] - last_fill['odometer']
            if miles_since_fill < 0:
                miles_since_fill = 0
            gallons_used = miles_since_fill / mpg if mpg > 0 else 0
            current_fuel_estimate = round(max(tank - gallons_used, 0.0), 2)
    result = {
        'vehicle_id': vid,
        'tank_capacity_gal': tank,
        'mpg': mpg,
        'max_range_miles': max_range,
        'current_fuel_estimate_gal': current_fuel_estimate,
        'miles_since_last_fill': miles_since_fill,
        'estimated_remaining_range': (
            round(current_fuel_estimate * mpg, 1)
            if current_fuel_estimate is not None and mpg > 0 else None
        ),
    }
    return jsonify(result)


@vehicles_bp.route('/api/vehicles/<int:vid>/fuel-economy')
def api_vehicles_fuel_economy(vid):
    with db_session() as db:
        vehicle = db.execute('SELECT * FROM vehicles WHERE id = ?', (vid,)).fetchone()
        if not vehicle:
            return jsonify({'error': 'not found'}), 404
        # Get fuel entries with odometer readings, oldest first for sequential calculation
        fuel_rows = db.execute(
            '''SELECT * FROM vehicle_fuel_log
               WHERE vehicle_id = ? AND odometer IS NOT NULL
               ORDER BY odometer ASC''',
            (vid,)
        ).fetchall()
    entries = []
    for i in range(1, len(fuel_rows)):
        prev = fuel_rows[i - 1]
        curr = fuel_rows[i]
        miles = (curr['odometer'] or 0) - (prev['odometer'] or 0)
        gallons = curr['gallons'] or 0
        if gallons > 0 and miles > 0:
            computed_mpg = round(miles / gallons, 2)
            entries.append({
                'fuel_log_id': curr['id'],
                'fuel_date': curr['fuel_date'],
                'odometer': curr['odometer'],
                'gallons': gallons,
                'miles_driven': miles,
                'computed_mpg': computed_mpg,
            })
    # Return last 10 entries, most recent first
    entries.reverse()
    entries = entries[:10]
    avg_mpg = round(sum(e['computed_mpg'] for e in entries) / len(entries), 2) if entries else None
    return jsonify({
        'vehicle_id': vid,
        'rated_mpg': vehicle['mpg'],
        'average_computed_mpg': avg_mpg,
        'entries': entries,
    })


# ─── Dashboard ───────────────────────────────────────────────────────

@vehicles_bp.route('/api/vehicles/dashboard')
def api_vehicles_dashboard():
    today = _utc_now().strftime('%Y-%m-%d')
    thirty_days = (_utc_now() + timedelta(days=30)).strftime('%Y-%m-%d')
    sixty_days = (_utc_now() + timedelta(days=60)).strftime('%Y-%m-%d')
    thirty_days_ago = (_utc_now() - timedelta(days=30)).strftime('%Y-%m-%d')
    with db_session() as db:
        # Total vehicles
        total = db.execute('SELECT COUNT(*) AS cnt FROM vehicles').fetchone()['cnt']

        # Vehicles by role
        role_rows = db.execute(
            'SELECT role, COUNT(*) AS cnt FROM vehicles GROUP BY role'
        ).fetchall()
        vehicles_by_role = {r['role']: r['cnt'] for r in role_rows}

        # All vehicles for mileage-based checks
        all_vehicles = db.execute('SELECT id, odometer, tank_capacity_gal, mpg FROM vehicles').fetchall()
        vehicle_odometers = {v['id']: v['odometer'] or 0 for v in all_vehicles}

        # Maintenance overdue (date-based)
        overdue_date = db.execute(
            '''SELECT vm.* FROM vehicle_maintenance vm
               WHERE vm.next_due_date != '' AND vm.next_due_date < ?
               AND vm.status != 'completed' ''',
            (today,)
        ).fetchall()
        # Maintenance overdue (mileage-based)
        overdue_mileage = db.execute(
            '''SELECT vm.* FROM vehicle_maintenance vm
               WHERE vm.next_due_mileage IS NOT NULL
               AND vm.status != 'completed' '''
        ).fetchall()
        overdue_by_mileage = [
            dict(m) for m in overdue_mileage
            if m['next_due_mileage'] and m['vehicle_id'] in vehicle_odometers
            and m['next_due_mileage'] < vehicle_odometers[m['vehicle_id']]
        ]
        maintenance_overdue = [dict(m) for m in overdue_date] + overdue_by_mileage
        # Deduplicate by id
        seen_ids = set()
        deduped_overdue = []
        for m in maintenance_overdue:
            if m['id'] not in seen_ids:
                seen_ids.add(m['id'])
                deduped_overdue.append(m)
        maintenance_overdue = deduped_overdue

        # Upcoming maintenance (next 30 days or next 3000 miles)
        upcoming_date = db.execute(
            '''SELECT vm.* FROM vehicle_maintenance vm
               WHERE vm.next_due_date != '' AND vm.next_due_date >= ? AND vm.next_due_date <= ?
               AND vm.status != 'completed' ''',
            (today, thirty_days)
        ).fetchall()
        upcoming_mileage = db.execute(
            '''SELECT vm.* FROM vehicle_maintenance vm
               WHERE vm.next_due_mileage IS NOT NULL
               AND vm.status != 'completed' '''
        ).fetchall()
        upcoming_by_mileage = [
            dict(m) for m in upcoming_mileage
            if m['next_due_mileage'] and m['vehicle_id'] in vehicle_odometers
            and vehicle_odometers[m['vehicle_id']] <= m['next_due_mileage'] <= vehicle_odometers[m['vehicle_id']] + 3000
        ]
        upcoming_maintenance = [dict(m) for m in upcoming_date] + upcoming_by_mileage
        seen_ids = set()
        deduped_upcoming = []
        for m in upcoming_maintenance:
            if m['id'] not in seen_ids:
                seen_ids.add(m['id'])
                deduped_upcoming.append(m)
        upcoming_maintenance = deduped_upcoming

        # Fuel cost last 30 days
        fuel_cost_row = db.execute(
            '''SELECT COALESCE(SUM(total_cost), 0) AS total
               FROM vehicle_fuel_log WHERE fuel_date >= ?''',
            (thirty_days_ago,)
        ).fetchone()
        total_fuel_cost_30d = round(fuel_cost_row['total'], 2)

        # Total range (sum of tank_capacity * mpg for all vehicles)
        total_range = 0.0
        for v in all_vehicles:
            tank = v['tank_capacity_gal'] or 0.0
            mpg = v['mpg'] or 0.0
            total_range += tank * mpg
        total_range = round(total_range, 1)

        # Expiring documents (insurance or registration within 60 days)
        expiring = db.execute(
            '''SELECT id, name, insurance_exp, registration_exp FROM vehicles
               WHERE (insurance_exp != '' AND insurance_exp <= ?)
               OR (registration_exp != '' AND registration_exp <= ?)''',
            (sixty_days, sixty_days)
        ).fetchall()
        expiring_docs = []
        for v in expiring:
            d = dict(v)
            reasons = []
            if d['insurance_exp'] and d['insurance_exp'] <= sixty_days:
                reasons.append('insurance')
            if d['registration_exp'] and d['registration_exp'] <= sixty_days:
                reasons.append('registration')
            if reasons:
                expiring_docs.append({
                    'vehicle_id': d['id'],
                    'vehicle_name': d['name'],
                    'expiring': reasons,
                    'insurance_exp': d['insurance_exp'],
                    'registration_exp': d['registration_exp'],
                })

    return jsonify({
        'total_vehicles': total,
        'vehicles_by_role': vehicles_by_role,
        'maintenance_overdue': maintenance_overdue,
        'upcoming_maintenance': upcoming_maintenance,
        'total_fuel_cost_30d': total_fuel_cost_30d,
        'total_range_miles': total_range,
        'expiring_documents': expiring_docs,
    })


# ─── Summary ─────────────────────────────────────────────────────────

@vehicles_bp.route('/api/vehicles/summary')
def api_vehicles_summary():
    today = _utc_now().strftime('%Y-%m-%d')
    with db_session() as db:
        total = db.execute('SELECT COUNT(*) AS cnt FROM vehicles').fetchone()['cnt']
        bugout = db.execute(
            "SELECT COUNT(*) AS cnt FROM vehicles WHERE role = 'bugout'"
        ).fetchone()['cnt']

        # Overdue count (date-based)
        overdue_date_count = db.execute(
            '''SELECT COUNT(*) AS cnt FROM vehicle_maintenance
               WHERE next_due_date != '' AND next_due_date < ?
               AND status != 'completed' ''',
            (today,)
        ).fetchone()['cnt']

        # Overdue count (mileage-based) — need to check against vehicle odometers
        all_vehicles = db.execute('SELECT id, odometer FROM vehicles').fetchall()
        vehicle_odometers = {v['id']: v['odometer'] or 0 for v in all_vehicles}
        mileage_overdue = db.execute(
            '''SELECT vehicle_id, next_due_mileage FROM vehicle_maintenance
               WHERE next_due_mileage IS NOT NULL AND status != 'completed' '''
        ).fetchall()
        overdue_mileage_count = sum(
            1 for m in mileage_overdue
            if m['vehicle_id'] in vehicle_odometers
            and m['next_due_mileage'] < vehicle_odometers[m['vehicle_id']]
        )

        # Total range
        range_rows = db.execute(
            'SELECT tank_capacity_gal, mpg FROM vehicles'
        ).fetchall()
        total_range = round(
            sum((r['tank_capacity_gal'] or 0) * (r['mpg'] or 0) for r in range_rows), 1
        )

    return jsonify({
        'total_vehicles': total,
        'bugout_vehicles': bugout,
        'maintenance_overdue_count': overdue_date_count + overdue_mileage_count,
        'total_range_miles': total_range,
    })
