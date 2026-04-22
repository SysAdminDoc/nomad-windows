"""Hardware sensors — IoT sensors, network devices, mesh nodes, weather stations,
GPS devices, wearables, integrations, and reference data."""

import json
import logging
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify

from db import db_session, log_activity
from web.blueprints import get_pagination
from web.utils import coerce_int as _ci, coerce_float as _cf

_log = logging.getLogger(__name__)

hardware_sensors_bp = Blueprint('hardware_sensors', __name__, url_prefix='/api/hardware')


# ─── Reference Constants ─────────────────────────────────────────────

SENSOR_TYPES = {
    'temperature': {
        'unit': '\u00b0F',
        'icon': 'thermometer',
        'typical_range': [-40, 140],
    },
    'humidity': {
        'unit': '%RH',
        'icon': 'droplet',
        'typical_range': [0, 100],
    },
    'soil_moisture': {
        'unit': '%',
        'icon': 'sprout',
        'typical_range': [0, 100],
    },
    'water_level': {
        'unit': 'in',
        'icon': 'waves',
        'typical_range': [0, 120],
    },
    'air_quality': {
        'unit': 'AQI',
        'icon': 'wind',
        'typical_range': [0, 500],
    },
    'radiation': {
        'unit': 'uSv/h',
        'icon': 'radiation',
        'typical_range': [0.0, 100.0],
    },
    'pressure': {
        'unit': 'hPa',
        'icon': 'gauge',
        'typical_range': [870, 1084],
    },
    'light': {
        'unit': 'lux',
        'icon': 'sun',
        'typical_range': [0, 100000],
    },
    'motion': {
        'unit': 'bool',
        'icon': 'activity',
        'typical_range': [0, 1],
    },
    'door': {
        'unit': 'bool',
        'icon': 'door-open',
        'typical_range': [0, 1],
    },
    'smoke': {
        'unit': 'ppm',
        'icon': 'flame',
        'typical_range': [0, 1000],
    },
    'co2': {
        'unit': 'ppm',
        'icon': 'cloud',
        'typical_range': [400, 5000],
    },
}


# ═══════════════════════════════════════════════════════════════════════
#  IoT Sensors
# ═══════════════════════════════════════════════════════════════════════

@hardware_sensors_bp.route('/sensors')
def sensors_list():
    """List IoT sensors with optional ?type= and ?status= filters."""
    sensor_type = request.args.get('type', '').strip()
    status = request.args.get('status', '').strip()
    clauses, params = [], []
    if sensor_type:
        clauses.append('sensor_type = ?')
        params.append(sensor_type)
    if status:
        clauses.append('status = ?')
        params.append(status)
    where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
    limit, offset = get_pagination()
    with db_session() as db:
        rows = db.execute(
            f'SELECT * FROM iot_sensors{where} ORDER BY name LIMIT ? OFFSET ?',
            (*params, limit, offset)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


def _sensor_float(val, default):
    """Coerce sensor thresholds/offsets; non-numeric input falls back to default."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return float(default)


def _sensor_int(val, default):
    try:
        return int(val)
    except (TypeError, ValueError):
        return int(default)


@hardware_sensors_bp.route('/sensors', methods=['POST'])
def sensors_create():
    """Create a new IoT sensor."""
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    sensor_type = data.get('sensor_type', 'temperature')
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO iot_sensors
               (name, sensor_type, protocol, device_id, location, topic, unit,
                current_value, last_reading_at, min_threshold, max_threshold,
                alert_enabled, calibration_offset, battery_pct, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, sensor_type,
             data.get('protocol', 'mqtt'),
             (data.get('device_id') or '')[:200],
             (data.get('location') or '')[:200],
             (data.get('topic') or '')[:500],
             data.get('unit', SENSOR_TYPES.get(sensor_type, {}).get('unit', '')),
             data.get('current_value', ''),
             data.get('last_reading_at', ''),
             _sensor_float(data.get('min_threshold', 0), 0),
             _sensor_float(data.get('max_threshold', 0), 0),
             1 if data.get('alert_enabled') else 0,
             _sensor_float(data.get('calibration_offset', 0), 0),
             _sensor_int(data.get('battery_pct', 100), 100),
             data.get('status', 'active'),
             (data.get('notes') or '')[:2000])
        )
        db.commit()
        row_id = cur.lastrowid
    log_activity('sensor_created', service='hardware_sensors', detail=f'Created sensor {name} (id={row_id})')
    return jsonify({'id': row_id, 'status': 'created'}), 201


@hardware_sensors_bp.route('/sensors/<int:sid>')
def sensors_get(sid):
    """Get a single IoT sensor including its last 10 readings."""
    with db_session() as db:
        row = db.execute('SELECT * FROM iot_sensors WHERE id = ?', (sid,)).fetchone()
        if not row:
            return jsonify({'error': 'sensor not found'}), 404
        sensor = dict(row)
        readings = db.execute(
            'SELECT * FROM iot_sensor_readings WHERE sensor_id = ? ORDER BY created_at DESC LIMIT 10',
            (sid,)
        ).fetchall()
        sensor['recent_readings'] = [dict(r) for r in readings]
    return jsonify(sensor)


@hardware_sensors_bp.route('/sensors/<int:sid>', methods=['PUT'])
def sensors_update(sid):
    """Update an IoT sensor."""
    data = request.get_json() or {}
    allowed = [
        'name', 'sensor_type', 'protocol', 'device_id', 'location', 'topic',
        'unit', 'current_value', 'last_reading_at', 'min_threshold',
        'max_threshold', 'alert_enabled', 'calibration_offset', 'battery_pct',
        'status', 'notes',
    ]
    sets, params = [], []
    for col in allowed:
        if col in data:
            sets.append(f'{col} = ?')
            params.append(data[col])
    if not sets:
        return jsonify({'error': 'no fields to update'}), 400
    sets.append("updated_at = datetime('now')")
    params.append(sid)
    with db_session() as db:
        r = db.execute(
            f"UPDATE iot_sensors SET {', '.join(sets)} WHERE id = ?", params
        )
        if r.rowcount == 0:
            return jsonify({'error': 'sensor not found'}), 404
        db.commit()
    log_activity('sensor_updated', service='hardware_sensors', detail=f'Updated sensor id={sid}')
    return jsonify({'updated': True})


@hardware_sensors_bp.route('/sensors/<int:sid>', methods=['DELETE'])
def sensors_delete(sid):
    """Delete an IoT sensor and cascade its readings."""
    with db_session() as db:
        db.execute('DELETE FROM iot_sensor_readings WHERE sensor_id = ?', (sid,))
        r = db.execute('DELETE FROM iot_sensors WHERE id = ?', (sid,))
        if r.rowcount == 0:
            return jsonify({'error': 'sensor not found'}), 404
        db.commit()
    log_activity('sensor_deleted', service='hardware_sensors', detail=f'Deleted sensor id={sid}')
    return jsonify({'deleted': True})


@hardware_sensors_bp.route('/sensors/<int:sid>/reading', methods=['POST'])
def sensors_add_reading(sid):
    """Post a new reading for a sensor and update current_value/last_reading_at."""
    data = request.get_json() or {}
    value = data.get('value')
    if value is None:
        return jsonify({'error': 'value is required'}), 400
    try:
        value_f = float(value)
    except (TypeError, ValueError):
        return jsonify({'error': 'value must be numeric'}), 400
    now_str = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    with db_session() as db:
        sensor = db.execute('SELECT id, unit FROM iot_sensors WHERE id = ?', (sid,)).fetchone()
        if not sensor:
            return jsonify({'error': 'sensor not found'}), 404
        db.execute(
            '''INSERT INTO iot_sensor_readings (sensor_id, value, raw_value, unit, quality, timestamp)
               VALUES (?,?,?,?,?,?)''',
            (sid, value_f,
             str(data.get('raw_value', value)),
             data.get('unit', sensor['unit'] or ''),
             data.get('quality', 'good'),
             data.get('timestamp', now_str))
        )
        db.execute(
            "UPDATE iot_sensors SET current_value = ?, last_reading_at = ?, updated_at = datetime('now') WHERE id = ?",
            (str(value), now_str, sid)
        )
        db.commit()
    return jsonify({'recorded': True}), 201


@hardware_sensors_bp.route('/sensors/<int:sid>/readings')
def sensors_readings(sid):
    """Get readings for a sensor. Default last 24 hours, override with ?hours=."""
    try:
        # Cap at ~1 year so an enormous ?hours= value doesn't trigger a full
        # readings-table scan with no other bound.
        hours = max(1, min(int(request.args.get('hours', 24)), 24 * 365))
    except (ValueError, TypeError):
        hours = 24
    try:
        limit = max(1, min(int(request.args.get('limit', 5000)), 50000))
    except (ValueError, TypeError):
        limit = 5000
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).strftime('%Y-%m-%dT%H:%M:%SZ')
    with db_session() as db:
        sensor = db.execute('SELECT id FROM iot_sensors WHERE id = ?', (sid,)).fetchone()
        if not sensor:
            return jsonify({'error': 'sensor not found'}), 404
        rows = db.execute(
            'SELECT * FROM iot_sensor_readings WHERE sensor_id = ? AND created_at >= ? ORDER BY created_at DESC LIMIT ?',
            (sid, cutoff, limit)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@hardware_sensors_bp.route('/sensors/dashboard')
def sensors_dashboard():
    """Aggregate dashboard: counts by type, status, alerts, battery warnings."""
    with db_session() as db:
        total = db.execute('SELECT COUNT(*) as c FROM iot_sensors').fetchone()['c']
        by_type = db.execute(
            'SELECT sensor_type, COUNT(*) as c FROM iot_sensors GROUP BY sensor_type ORDER BY c DESC'
        ).fetchall()
        by_status = db.execute(
            'SELECT status, COUNT(*) as c FROM iot_sensors GROUP BY status ORDER BY c DESC'
        ).fetchall()
        alert_count = db.execute(
            'SELECT COUNT(*) as c FROM iot_sensors WHERE alert_enabled = 1'
        ).fetchone()['c']
        low_battery = db.execute(
            'SELECT id, name, battery_pct FROM iot_sensors WHERE battery_pct < 20 ORDER BY battery_pct'
        ).fetchall()
        recent_readings = db.execute(
            'SELECT COUNT(*) as c FROM iot_sensor_readings WHERE created_at >= ?',
            ((datetime.utcnow() - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%SZ'),)
        ).fetchone()['c']
    return jsonify({
        'total_sensors': total,
        'by_type': {r['sensor_type']: r['c'] for r in by_type},
        'by_status': {r['status']: r['c'] for r in by_status},
        'alerts_enabled': alert_count,
        'low_battery': [dict(r) for r in low_battery],
        'readings_24h': recent_readings,
    })


# ═══════════════════════════════════════════════════════════════════════
#  Network Devices
# ═══════════════════════════════════════════════════════════════════════

@hardware_sensors_bp.route('/network')
def network_list():
    """List network devices."""
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM network_devices ORDER BY name LIMIT ? OFFSET ?',
            get_pagination()
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@hardware_sensors_bp.route('/network', methods=['POST'])
def network_create():
    """Add a network device."""
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO network_devices
               (name, device_type, ip_address, mac_address, hostname, manufacturer,
                model, firmware_version, location, vlan, role, port_count, uplink_to,
                last_seen, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name,
             data.get('device_type', 'router'),
             (data.get('ip_address') or '')[:45],
             (data.get('mac_address') or '')[:17],
             (data.get('hostname') or '')[:200],
             (data.get('manufacturer') or '')[:200],
             (data.get('model') or '')[:200],
             (data.get('firmware_version') or '')[:100],
             (data.get('location') or '')[:200],
             (data.get('vlan') or '')[:50],
             data.get('role', 'infrastructure'),
             _ci(data.get('port_count', 0), 0),
             _ci(data.get('uplink_to', 0), 0),
             data.get('last_seen', ''),
             data.get('status', 'online'),
             (data.get('notes') or '')[:2000])
        )
        db.commit()
        row_id = cur.lastrowid
    log_activity('network_device_created', service='hardware_sensors', detail=f'Created device {name} (id={row_id})')
    return jsonify({'id': row_id, 'status': 'created'}), 201


@hardware_sensors_bp.route('/network/<int:did>')
def network_get(did):
    """Get a single network device."""
    with db_session() as db:
        row = db.execute('SELECT * FROM network_devices WHERE id = ?', (did,)).fetchone()
    if not row:
        return jsonify({'error': 'device not found'}), 404
    return jsonify(dict(row))


@hardware_sensors_bp.route('/network/<int:did>', methods=['PUT'])
def network_update(did):
    """Update a network device."""
    data = request.get_json() or {}
    allowed = [
        'name', 'device_type', 'ip_address', 'mac_address', 'hostname',
        'manufacturer', 'model', 'firmware_version', 'location', 'vlan',
        'role', 'port_count', 'uplink_to', 'last_seen', 'status', 'notes',
    ]
    sets, params = [], []
    for col in allowed:
        if col in data:
            sets.append(f'{col} = ?')
            params.append(data[col])
    if not sets:
        return jsonify({'error': 'no fields to update'}), 400
    sets.append("updated_at = datetime('now')")
    params.append(did)
    with db_session() as db:
        r = db.execute(
            f"UPDATE network_devices SET {', '.join(sets)} WHERE id = ?", params
        )
        if r.rowcount == 0:
            return jsonify({'error': 'device not found'}), 404
        db.commit()
    log_activity('network_device_updated', service='hardware_sensors', detail=f'Updated device id={did}')
    return jsonify({'updated': True})


@hardware_sensors_bp.route('/network/<int:did>', methods=['DELETE'])
def network_delete(did):
    """Delete a network device."""
    with db_session() as db:
        r = db.execute('DELETE FROM network_devices WHERE id = ?', (did,))
        if r.rowcount == 0:
            return jsonify({'error': 'device not found'}), 404
        db.commit()
    log_activity('network_device_deleted', service='hardware_sensors', detail=f'Deleted device id={did}')
    return jsonify({'deleted': True})


@hardware_sensors_bp.route('/network/topology')
def network_topology():
    """Build a tree from uplink_to relationships."""
    with db_session() as db:
        rows = db.execute(
            'SELECT id, name, device_type, ip_address, location, uplink_to, status FROM network_devices ORDER BY name'
        ).fetchall()
    devices = [dict(r) for r in rows]
    by_id = {d['id']: d for d in devices}
    children = {}
    roots = []
    for d in devices:
        parent = d['uplink_to']
        if parent and parent in by_id:
            children.setdefault(parent, []).append(d)
        else:
            roots.append(d)

    def _build(node):
        node['children'] = [_build(c) for c in children.get(node['id'], [])]
        return node

    tree = [_build(r) for r in roots]
    return jsonify(tree)


@hardware_sensors_bp.route('/network/scan')
def network_scan():
    """Counts by device_type, status, and vlan."""
    with db_session() as db:
        total = db.execute('SELECT COUNT(*) as c FROM network_devices').fetchone()['c']
        by_type = db.execute(
            'SELECT device_type, COUNT(*) as c FROM network_devices GROUP BY device_type ORDER BY c DESC'
        ).fetchall()
        by_status = db.execute(
            'SELECT status, COUNT(*) as c FROM network_devices GROUP BY status ORDER BY c DESC'
        ).fetchall()
        by_vlan = db.execute(
            "SELECT vlan, COUNT(*) as c FROM network_devices WHERE vlan != '' GROUP BY vlan ORDER BY c DESC"
        ).fetchall()
    return jsonify({
        'total': total,
        'by_type': {r['device_type']: r['c'] for r in by_type},
        'by_status': {r['status']: r['c'] for r in by_status},
        'by_vlan': {r['vlan']: r['c'] for r in by_vlan},
    })


# ═══════════════════════════════════════════════════════════════════════
#  Meshtastic Mesh Nodes
# ═══════════════════════════════════════════════════════════════════════

@hardware_sensors_bp.route('/mesh')
def mesh_list():
    """List all mesh nodes."""
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM mesh_nodes ORDER BY long_name LIMIT ? OFFSET ?',
            get_pagination()
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@hardware_sensors_bp.route('/mesh', methods=['POST'])
def mesh_create():
    """Create or upsert a mesh node by node_id."""
    data = request.get_json() or {}
    node_id = (data.get('node_id') or '').strip()
    if not node_id:
        return jsonify({'error': 'node_id is required'}), 400
    with db_session() as db:
        existing = db.execute('SELECT id FROM mesh_nodes WHERE node_id = ?', (node_id,)).fetchone()
        if existing:
            # Upsert: update the existing record
            upsert_cols = [
                'long_name', 'short_name', 'hardware_model', 'firmware_version',
                'role', 'latitude', 'longitude', 'altitude_m', 'battery_level',
                'voltage', 'channel_utilization', 'air_util_tx', 'snr', 'rssi',
                'hops_away', 'last_heard', 'status', 'notes',
            ]
            sets, params = [], []
            for col in upsert_cols:
                if col in data:
                    sets.append(f'{col} = ?')
                    params.append(data[col])
            if sets:
                sets.append("updated_at = datetime('now')")
                params.append(existing['id'])
                db.execute(
                    f"UPDATE mesh_nodes SET {', '.join(sets)} WHERE id = ?", params
                )
                db.commit()
            return jsonify({'id': existing['id'], 'status': 'updated'})
        else:
            cur = db.execute(
                '''INSERT INTO mesh_nodes
                   (node_id, long_name, short_name, hardware_model, firmware_version,
                    role, latitude, longitude, altitude_m, battery_level, voltage,
                    channel_utilization, air_util_tx, snr, rssi, hops_away,
                    last_heard, status, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (node_id,
                 (data.get('long_name') or '')[:200],
                 (data.get('short_name') or '')[:10],
                 (data.get('hardware_model') or '')[:100],
                 (data.get('firmware_version') or '')[:50],
                 data.get('role', 'client'),
                 _cf(data.get('latitude', 0), 0.0),
                 _cf(data.get('longitude', 0), 0.0),
                 _cf(data.get('altitude_m', 0), 0.0),
                 _ci(data.get('battery_level', 0), 0),
                 _cf(data.get('voltage', 0), 0.0),
                 _cf(data.get('channel_utilization', 0), 0.0),
                 _cf(data.get('air_util_tx', 0), 0.0),
                 _cf(data.get('snr', 0), 0.0),
                 _ci(data.get('rssi', 0), 0),
                 _ci(data.get('hops_away', 0), 0),
                 data.get('last_heard', ''),
                 data.get('status', 'online'),
                 (data.get('notes') or '')[:2000])
            )
            db.commit()
            row_id = cur.lastrowid
    log_activity('mesh_node_created', service='hardware_sensors', detail=f'Created/upserted node {node_id}')
    return jsonify({'id': row_id, 'status': 'created'}), 201


@hardware_sensors_bp.route('/mesh/<int:mid>')
def mesh_get(mid):
    """Get a single mesh node."""
    with db_session() as db:
        row = db.execute('SELECT * FROM mesh_nodes WHERE id = ?', (mid,)).fetchone()
    if not row:
        return jsonify({'error': 'mesh node not found'}), 404
    return jsonify(dict(row))


@hardware_sensors_bp.route('/mesh/<int:mid>', methods=['PUT'])
def mesh_update(mid):
    """Update a mesh node."""
    data = request.get_json() or {}
    allowed = [
        'node_id', 'long_name', 'short_name', 'hardware_model', 'firmware_version',
        'role', 'latitude', 'longitude', 'altitude_m', 'battery_level', 'voltage',
        'channel_utilization', 'air_util_tx', 'snr', 'rssi', 'hops_away',
        'last_heard', 'status', 'notes',
    ]
    sets, params = [], []
    for col in allowed:
        if col in data:
            sets.append(f'{col} = ?')
            params.append(data[col])
    if not sets:
        return jsonify({'error': 'no fields to update'}), 400
    sets.append("updated_at = datetime('now')")
    params.append(mid)
    with db_session() as db:
        r = db.execute(
            f"UPDATE mesh_nodes SET {', '.join(sets)} WHERE id = ?", params
        )
        if r.rowcount == 0:
            return jsonify({'error': 'mesh node not found'}), 404
        db.commit()
    log_activity('mesh_node_updated', service='hardware_sensors', detail=f'Updated mesh node id={mid}')
    return jsonify({'updated': True})


@hardware_sensors_bp.route('/mesh/<int:mid>', methods=['DELETE'])
def mesh_delete(mid):
    """Delete a mesh node."""
    with db_session() as db:
        r = db.execute('DELETE FROM mesh_nodes WHERE id = ?', (mid,))
        if r.rowcount == 0:
            return jsonify({'error': 'mesh node not found'}), 404
        db.commit()
    log_activity('mesh_node_deleted', service='hardware_sensors', detail=f'Deleted mesh node id={mid}')
    return jsonify({'deleted': True})


@hardware_sensors_bp.route('/mesh/map')
def mesh_map():
    """Return nodes that have lat/lon for map display."""
    with db_session() as db:
        rows = db.execute(
            '''SELECT id, node_id, long_name, short_name, hardware_model, role,
                      latitude, longitude, altitude_m, battery_level, snr, rssi,
                      hops_away, last_heard, status
               FROM mesh_nodes
               WHERE latitude != 0 OR longitude != 0
               ORDER BY long_name'''
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@hardware_sensors_bp.route('/mesh/stats')
def mesh_stats():
    """Mesh network statistics: counts, roles, battery, signal quality."""
    with db_session() as db:
        total = db.execute('SELECT COUNT(*) as c FROM mesh_nodes').fetchone()['c']
        by_role = db.execute(
            'SELECT role, COUNT(*) as c FROM mesh_nodes GROUP BY role ORDER BY c DESC'
        ).fetchall()
        by_status = db.execute(
            'SELECT status, COUNT(*) as c FROM mesh_nodes GROUP BY status ORDER BY c DESC'
        ).fetchall()
        avg_battery = db.execute(
            'SELECT AVG(battery_level) as avg_bat FROM mesh_nodes WHERE battery_level > 0'
        ).fetchone()['avg_bat']
        avg_snr = db.execute(
            'SELECT AVG(snr) as avg_snr FROM mesh_nodes WHERE snr != 0'
        ).fetchone()['avg_snr']
        max_hops = db.execute(
            'SELECT MAX(hops_away) as mh FROM mesh_nodes'
        ).fetchone()['mh']
    return jsonify({
        'total_nodes': total,
        'by_role': {r['role']: r['c'] for r in by_role},
        'by_status': {r['status']: r['c'] for r in by_status},
        'avg_battery': round(avg_battery or 0, 1),
        'avg_snr': round(avg_snr or 0, 1),
        'max_hops': max_hops or 0,
    })


# ═══════════════════════════════════════════════════════════════════════
#  Weather Stations
# ═══════════════════════════════════════════════════════════════════════

@hardware_sensors_bp.route('/weather-stations')
def weather_list():
    """List all weather stations."""
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM weather_stations ORDER BY name LIMIT ? OFFSET ?',
            get_pagination()
        ).fetchall()
    result = []
    for r in rows:
        entry = dict(r)
        try:
            entry['current_data'] = json.loads(entry.get('current_data') or '{}')
        except (json.JSONDecodeError, TypeError):
            entry['current_data'] = {}
        result.append(entry)
    return jsonify(result)


@hardware_sensors_bp.route('/weather-stations', methods=['POST'])
def weather_create():
    """Add a weather station."""
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    current_data = data.get('current_data')
    if isinstance(current_data, dict):
        current_data = json.dumps(current_data)
    else:
        current_data = current_data or '{}'
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO weather_stations
               (name, station_type, brand, model, protocol, ip_address, api_key,
                location, latitude, longitude, elevation_ft, polling_interval_sec,
                last_poll, current_data, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name,
             data.get('station_type', 'personal'),
             (data.get('brand') or '')[:100],
             (data.get('model') or '')[:100],
             data.get('protocol', 'ecowitt'),
             (data.get('ip_address') or '')[:45],
             (data.get('api_key') or '')[:500],
             (data.get('location') or '')[:200],
             _cf(data.get('latitude', 0), 0.0),
             _cf(data.get('longitude', 0), 0.0),
             _cf(data.get('elevation_ft', 0), 0.0),
             _ci(data.get('polling_interval_sec', 60), 60, minimum=1),
             data.get('last_poll', ''),
             current_data,
             data.get('status', 'active'),
             (data.get('notes') or '')[:2000])
        )
        db.commit()
        row_id = cur.lastrowid
    log_activity('weather_station_created', service='hardware_sensors', detail=f'Created station {name} (id={row_id})')
    return jsonify({'id': row_id, 'status': 'created'}), 201


@hardware_sensors_bp.route('/weather-stations/<int:wid>')
def weather_get(wid):
    """Get a single weather station."""
    with db_session() as db:
        row = db.execute('SELECT * FROM weather_stations WHERE id = ?', (wid,)).fetchone()
    if not row:
        return jsonify({'error': 'weather station not found'}), 404
    entry = dict(row)
    try:
        entry['current_data'] = json.loads(entry.get('current_data') or '{}')
    except (json.JSONDecodeError, TypeError):
        entry['current_data'] = {}
    return jsonify(entry)


@hardware_sensors_bp.route('/weather-stations/<int:wid>', methods=['PUT'])
def weather_update(wid):
    """Update a weather station."""
    data = request.get_json() or {}
    allowed = [
        'name', 'station_type', 'brand', 'model', 'protocol', 'ip_address',
        'api_key', 'location', 'latitude', 'longitude', 'elevation_ft',
        'polling_interval_sec', 'last_poll', 'current_data', 'status', 'notes',
    ]
    sets, params = [], []
    for col in allowed:
        if col in data:
            val = data[col]
            if col == 'current_data' and isinstance(val, dict):
                val = json.dumps(val)
            sets.append(f'{col} = ?')
            params.append(val)
    if not sets:
        return jsonify({'error': 'no fields to update'}), 400
    sets.append("updated_at = datetime('now')")
    params.append(wid)
    with db_session() as db:
        r = db.execute(
            f"UPDATE weather_stations SET {', '.join(sets)} WHERE id = ?", params
        )
        if r.rowcount == 0:
            return jsonify({'error': 'weather station not found'}), 404
        db.commit()
    log_activity('weather_station_updated', service='hardware_sensors', detail=f'Updated station id={wid}')
    return jsonify({'updated': True})


@hardware_sensors_bp.route('/weather-stations/<int:wid>', methods=['DELETE'])
def weather_delete(wid):
    """Delete a weather station."""
    with db_session() as db:
        r = db.execute('DELETE FROM weather_stations WHERE id = ?', (wid,))
        if r.rowcount == 0:
            return jsonify({'error': 'weather station not found'}), 404
        db.commit()
    log_activity('weather_station_deleted', service='hardware_sensors', detail=f'Deleted station id={wid}')
    return jsonify({'deleted': True})


# ═══════════════════════════════════════════════════════════════════════
#  GPS Devices
# ═══════════════════════════════════════════════════════════════════════

@hardware_sensors_bp.route('/gps')
def gps_list():
    """List GPS devices."""
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM gps_devices ORDER BY name LIMIT ? OFFSET ?',
            get_pagination()
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@hardware_sensors_bp.route('/gps', methods=['POST'])
def gps_create():
    """Add a GPS device."""
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO gps_devices
               (name, device_type, brand, model, serial_number, connection_type,
                port, baud_rate, last_fix_lat, last_fix_lon, last_fix_alt,
                last_fix_time, accuracy_m, satellites, battery_pct, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name,
             data.get('device_type', 'handheld'),
             (data.get('brand') or '')[:100],
             (data.get('model') or '')[:100],
             (data.get('serial_number') or '')[:100],
             data.get('connection_type', 'usb'),
             (data.get('port') or '')[:50],
             _ci(data.get('baud_rate', 9600), 9600, minimum=0),
             _cf(data.get('last_fix_lat', 0), 0.0),
             _cf(data.get('last_fix_lon', 0), 0.0),
             _cf(data.get('last_fix_alt', 0), 0.0),
             data.get('last_fix_time', ''),
             _cf(data.get('accuracy_m', 0), 0.0),
             _ci(data.get('satellites', 0), 0, minimum=0),
             _ci(data.get('battery_pct', 100), 100, minimum=0, maximum=100),
             data.get('status', 'disconnected'),
             (data.get('notes') or '')[:2000])
        )
        db.commit()
        row_id = cur.lastrowid
    log_activity('gps_device_created', service='hardware_sensors', detail=f'Created GPS device {name} (id={row_id})')
    return jsonify({'id': row_id, 'status': 'created'}), 201


@hardware_sensors_bp.route('/gps/<int:gid>')
def gps_get(gid):
    """Get a single GPS device."""
    with db_session() as db:
        row = db.execute('SELECT * FROM gps_devices WHERE id = ?', (gid,)).fetchone()
    if not row:
        return jsonify({'error': 'GPS device not found'}), 404
    return jsonify(dict(row))


@hardware_sensors_bp.route('/gps/<int:gid>', methods=['PUT'])
def gps_update(gid):
    """Update a GPS device."""
    data = request.get_json() or {}
    allowed = [
        'name', 'device_type', 'brand', 'model', 'serial_number',
        'connection_type', 'port', 'baud_rate', 'last_fix_lat', 'last_fix_lon',
        'last_fix_alt', 'last_fix_time', 'accuracy_m', 'satellites',
        'battery_pct', 'status', 'notes',
    ]
    sets, params = [], []
    for col in allowed:
        if col in data:
            sets.append(f'{col} = ?')
            params.append(data[col])
    if not sets:
        return jsonify({'error': 'no fields to update'}), 400
    sets.append("updated_at = datetime('now')")
    params.append(gid)
    with db_session() as db:
        r = db.execute(
            f"UPDATE gps_devices SET {', '.join(sets)} WHERE id = ?", params
        )
        if r.rowcount == 0:
            return jsonify({'error': 'GPS device not found'}), 404
        db.commit()
    log_activity('gps_device_updated', service='hardware_sensors', detail=f'Updated GPS device id={gid}')
    return jsonify({'updated': True})


@hardware_sensors_bp.route('/gps/<int:gid>', methods=['DELETE'])
def gps_delete(gid):
    """Delete a GPS device."""
    with db_session() as db:
        r = db.execute('DELETE FROM gps_devices WHERE id = ?', (gid,))
        if r.rowcount == 0:
            return jsonify({'error': 'GPS device not found'}), 404
        db.commit()
    log_activity('gps_device_deleted', service='hardware_sensors', detail=f'Deleted GPS device id={gid}')
    return jsonify({'deleted': True})


@hardware_sensors_bp.route('/gps/<int:gid>/fix', methods=['POST'])
def gps_record_fix(gid):
    """Record a new GPS fix (lat, lon, alt, accuracy, satellites)."""
    data = request.get_json() or {}
    lat = data.get('lat') or data.get('latitude')
    lon = data.get('lon') or data.get('longitude')
    if lat is None or lon is None:
        return jsonify({'error': 'lat and lon are required'}), 400
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return jsonify({'error': 'lat and lon must be numeric'}), 400
    now_str = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    with db_session() as db:
        device = db.execute('SELECT id FROM gps_devices WHERE id = ?', (gid,)).fetchone()
        if not device:
            return jsonify({'error': 'GPS device not found'}), 404
        db.execute(
            '''UPDATE gps_devices SET
               last_fix_lat = ?, last_fix_lon = ?, last_fix_alt = ?,
               last_fix_time = ?, accuracy_m = ?, satellites = ?,
               status = 'fix', updated_at = datetime('now')
               WHERE id = ?''',
            (lat_f, lon_f,
             _cf(data.get('alt', data.get('altitude', 0)), 0.0),
             data.get('timestamp', now_str),
             _cf(data.get('accuracy_m', 0), 0.0),
             _ci(data.get('satellites', 0), 0, minimum=0),
             gid)
        )
        db.commit()
    log_activity('gps_fix_recorded', service='hardware_sensors', detail=f'Fix for device id={gid}: {lat},{lon}')
    return jsonify({'recorded': True})


# ═══════════════════════════════════════════════════════════════════════
#  Wearable Devices
# ═══════════════════════════════════════════════════════════════════════

@hardware_sensors_bp.route('/wearables')
def wearables_list():
    """List wearable devices with optional ?wearer= filter."""
    wearer = request.args.get('wearer', '').strip()
    limit, offset = get_pagination()
    with db_session() as db:
        if wearer:
            rows = db.execute(
                'SELECT * FROM wearable_devices WHERE wearer = ? ORDER BY name LIMIT ? OFFSET ?',
                (wearer, limit, offset)
            ).fetchall()
        else:
            rows = db.execute(
                'SELECT * FROM wearable_devices ORDER BY name LIMIT ? OFFSET ?',
                (limit, offset)
            ).fetchall()
    result = []
    for r in rows:
        entry = dict(r)
        try:
            entry['current_data'] = json.loads(entry.get('current_data') or '{}')
        except (json.JSONDecodeError, TypeError):
            entry['current_data'] = {}
        result.append(entry)
    return jsonify(result)


@hardware_sensors_bp.route('/wearables', methods=['POST'])
def wearables_create():
    """Add a wearable device."""
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    current_data = data.get('current_data')
    if isinstance(current_data, dict):
        current_data = json.dumps(current_data)
    else:
        current_data = current_data or '{}'
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO wearable_devices
               (name, device_type, brand, model, wearer, connection_type,
                last_sync, battery_pct, current_data, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            (name,
             data.get('device_type', 'fitness_tracker'),
             (data.get('brand') or '')[:100],
             (data.get('model') or '')[:100],
             (data.get('wearer') or '')[:200],
             data.get('connection_type', 'bluetooth'),
             data.get('last_sync', ''),
             _ci(data.get('battery_pct', 100), 100, minimum=0, maximum=100),
             current_data,
             data.get('status', 'paired'),
             (data.get('notes') or '')[:2000])
        )
        db.commit()
        row_id = cur.lastrowid
    log_activity('wearable_created', service='hardware_sensors', detail=f'Created wearable {name} (id={row_id})')
    return jsonify({'id': row_id, 'status': 'created'}), 201


@hardware_sensors_bp.route('/wearables/<int:wid>')
def wearables_get(wid):
    """Get a single wearable device."""
    with db_session() as db:
        row = db.execute('SELECT * FROM wearable_devices WHERE id = ?', (wid,)).fetchone()
    if not row:
        return jsonify({'error': 'wearable not found'}), 404
    entry = dict(row)
    try:
        entry['current_data'] = json.loads(entry.get('current_data') or '{}')
    except (json.JSONDecodeError, TypeError):
        entry['current_data'] = {}
    return jsonify(entry)


@hardware_sensors_bp.route('/wearables/<int:wid>', methods=['PUT'])
def wearables_update(wid):
    """Update a wearable device."""
    data = request.get_json() or {}
    allowed = [
        'name', 'device_type', 'brand', 'model', 'wearer', 'connection_type',
        'last_sync', 'battery_pct', 'current_data', 'status', 'notes',
    ]
    sets, params = [], []
    for col in allowed:
        if col in data:
            val = data[col]
            if col == 'current_data' and isinstance(val, dict):
                val = json.dumps(val)
            sets.append(f'{col} = ?')
            params.append(val)
    if not sets:
        return jsonify({'error': 'no fields to update'}), 400
    sets.append("updated_at = datetime('now')")
    params.append(wid)
    with db_session() as db:
        r = db.execute(
            f"UPDATE wearable_devices SET {', '.join(sets)} WHERE id = ?", params
        )
        if r.rowcount == 0:
            return jsonify({'error': 'wearable not found'}), 404
        db.commit()
    log_activity('wearable_updated', service='hardware_sensors', detail=f'Updated wearable id={wid}')
    return jsonify({'updated': True})


@hardware_sensors_bp.route('/wearables/<int:wid>', methods=['DELETE'])
def wearables_delete(wid):
    """Delete a wearable device."""
    with db_session() as db:
        r = db.execute('DELETE FROM wearable_devices WHERE id = ?', (wid,))
        if r.rowcount == 0:
            return jsonify({'error': 'wearable not found'}), 404
        db.commit()
    log_activity('wearable_deleted', service='hardware_sensors', detail=f'Deleted wearable id={wid}')
    return jsonify({'deleted': True})


# ═══════════════════════════════════════════════════════════════════════
#  Integration Configs
# ═══════════════════════════════════════════════════════════════════════

@hardware_sensors_bp.route('/integrations')
def integrations_list():
    """List all integration configs."""
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM integration_configs ORDER BY name LIMIT ? OFFSET ?',
            get_pagination()
        ).fetchall()
    result = []
    for r in rows:
        entry = dict(r)
        try:
            entry['config_json'] = json.loads(entry.get('config_json') or '{}')
        except (json.JSONDecodeError, TypeError):
            entry['config_json'] = {}
        result.append(entry)
    return jsonify(result)


@hardware_sensors_bp.route('/integrations', methods=['POST'])
def integrations_create():
    """Add an integration config."""
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    config_json = data.get('config_json')
    if isinstance(config_json, dict):
        config_json = json.dumps(config_json)
    else:
        config_json = config_json or '{}'
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO integration_configs
               (name, integration_type, endpoint_url, api_key, username, auth_token,
                config_json, polling_interval_sec, last_sync, sync_count, status,
                error_message, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name,
             data.get('integration_type', 'mqtt'),
             (data.get('endpoint_url') or '')[:2000],
             (data.get('api_key') or '')[:500],
             (data.get('username') or '')[:200],
             (data.get('auth_token') or '')[:1000],
             config_json,
             _ci(data.get('polling_interval_sec', 60), 60, minimum=1),
             data.get('last_sync', ''),
             _ci(data.get('sync_count', 0), 0, minimum=0),
             data.get('status', 'disabled'),
             (data.get('error_message') or '')[:2000],
             (data.get('notes') or '')[:2000])
        )
        db.commit()
        row_id = cur.lastrowid
    log_activity('integration_created', service='hardware_sensors', detail=f'Created integration {name} (id={row_id})')
    return jsonify({'id': row_id, 'status': 'created'}), 201


@hardware_sensors_bp.route('/integrations/<int:iid>')
def integrations_get(iid):
    """Get a single integration config."""
    with db_session() as db:
        row = db.execute('SELECT * FROM integration_configs WHERE id = ?', (iid,)).fetchone()
    if not row:
        return jsonify({'error': 'integration not found'}), 404
    entry = dict(row)
    try:
        entry['config_json'] = json.loads(entry.get('config_json') or '{}')
    except (json.JSONDecodeError, TypeError):
        entry['config_json'] = {}
    return jsonify(entry)


@hardware_sensors_bp.route('/integrations/<int:iid>', methods=['PUT'])
def integrations_update(iid):
    """Update an integration config."""
    data = request.get_json() or {}
    allowed = [
        'name', 'integration_type', 'endpoint_url', 'api_key', 'username',
        'auth_token', 'config_json', 'polling_interval_sec', 'last_sync',
        'sync_count', 'status', 'error_message', 'notes',
    ]
    sets, params = [], []
    for col in allowed:
        if col in data:
            val = data[col]
            if col == 'config_json' and isinstance(val, dict):
                val = json.dumps(val)
            sets.append(f'{col} = ?')
            params.append(val)
    if not sets:
        return jsonify({'error': 'no fields to update'}), 400
    sets.append("updated_at = datetime('now')")
    params.append(iid)
    with db_session() as db:
        r = db.execute(
            f"UPDATE integration_configs SET {', '.join(sets)} WHERE id = ?", params
        )
        if r.rowcount == 0:
            return jsonify({'error': 'integration not found'}), 404
        db.commit()
    log_activity('integration_updated', service='hardware_sensors', detail=f'Updated integration id={iid}')
    return jsonify({'updated': True})


@hardware_sensors_bp.route('/integrations/<int:iid>', methods=['DELETE'])
def integrations_delete(iid):
    """Delete an integration config."""
    with db_session() as db:
        r = db.execute('DELETE FROM integration_configs WHERE id = ?', (iid,))
        if r.rowcount == 0:
            return jsonify({'error': 'integration not found'}), 404
        db.commit()
    log_activity('integration_deleted', service='hardware_sensors', detail=f'Deleted integration id={iid}')
    return jsonify({'deleted': True})


@hardware_sensors_bp.route('/integrations/<int:iid>/test', methods=['POST'])
def integrations_test(iid):
    """Validate integration config and return a mock success/failure."""
    with db_session() as db:
        row = db.execute('SELECT * FROM integration_configs WHERE id = ?', (iid,)).fetchone()
    if not row:
        return jsonify({'error': 'integration not found'}), 404
    entry = dict(row)
    errors = []
    if not entry.get('endpoint_url'):
        errors.append('endpoint_url is empty')
    int_type = entry.get('integration_type', '')
    if int_type in ('rest', 'webhook') and not entry.get('api_key') and not entry.get('auth_token'):
        errors.append('no api_key or auth_token configured')
    try:
        cfg = json.loads(entry.get('config_json') or '{}')
    except (json.JSONDecodeError, TypeError):
        cfg = {}
        errors.append('config_json is not valid JSON')
    if errors:
        with db_session() as db:
            db.execute(
                "UPDATE integration_configs SET status = 'error', error_message = ?, updated_at = datetime('now') WHERE id = ?",
                ('; '.join(errors), iid)
            )
            db.commit()
        return jsonify({'success': False, 'errors': errors})
    # Mark as tested-OK
    with db_session() as db:
        db.execute(
            "UPDATE integration_configs SET status = 'active', error_message = '', updated_at = datetime('now') WHERE id = ?",
            (iid,)
        )
        db.commit()
    log_activity('integration_tested', service='hardware_sensors', detail=f'Test passed for integration id={iid}')
    return jsonify({'success': True, 'message': f'Integration {entry["name"]} validated successfully'})


# ═══════════════════════════════════════════════════════════════════════
#  Reference Data
# ═══════════════════════════════════════════════════════════════════════

@hardware_sensors_bp.route('/reference/sensor-types')
def reference_sensor_types():
    """Return the SENSOR_TYPES constant for UI dropdowns and validation."""
    return jsonify(SENSOR_TYPES)
