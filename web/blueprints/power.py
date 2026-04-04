"""Power management and sensor routes."""

import json
import math
import time
from collections import defaultdict
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify

from db import db_session, log_activity
from web.state import broadcast_event

power_bp = Blueprint('power', __name__)


# ─── Power Devices CRUD ─────────────────────────────────────────────

@power_bp.route('/api/power/devices')
def api_power_devices():
    with db_session() as db:
        rows = db.execute('SELECT * FROM power_devices ORDER BY device_type, name LIMIT 10000').fetchall()
    def _safe_json(val, default):
        try:
            return json.loads(val or default)
        except (json.JSONDecodeError, TypeError, ValueError):
            return json.loads(default)
    return jsonify([{**dict(r), 'specs': _safe_json(r['specs'], '{}')} for r in rows])


@power_bp.route('/api/power/devices', methods=['POST'])
def api_power_devices_create():
    data = request.get_json() or {}
    if not data.get('name') or not data.get('device_type'):
        return jsonify({'error': 'Name and type required'}), 400
    with db_session() as db:
        db.execute('INSERT INTO power_devices (device_type, name, specs, notes) VALUES (?,?,?,?)',
                   (data['device_type'], data['name'], json.dumps(data.get('specs', {})), data.get('notes', '')))
        db.commit()
    return jsonify({'status': 'created'}), 201


@power_bp.route('/api/power/devices/<int:did>', methods=['DELETE'])
def api_power_devices_delete(did):
    with db_session() as db:
        db.execute('DELETE FROM power_devices WHERE id = ?', (did,))
        db.commit()
    return jsonify({'status': 'deleted'})


# ─── Power Log ───────────────────────────────────────────────────────

@power_bp.route('/api/power/log')
def api_power_log():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM power_log ORDER BY created_at DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    return jsonify([dict(r) for r in rows])


@power_bp.route('/api/power/log', methods=['POST'])
def api_power_log_create():
    data = request.get_json() or {}
    with db_session() as db:
        db.execute('INSERT INTO power_log (battery_voltage, battery_soc, solar_watts, solar_wh_today, load_watts, load_wh_today, generator_running, notes) VALUES (?,?,?,?,?,?,?,?)',
                   (data.get('battery_voltage'), data.get('battery_soc'), data.get('solar_watts'),
                    data.get('solar_wh_today'), data.get('load_watts'), data.get('load_wh_today'),
                    1 if data.get('generator_running') else 0, data.get('notes', '')))
        db.commit()
    return jsonify({'status': 'logged'}), 201


# ─── Power Dashboard ────────────────────────────────────────────────

@power_bp.route('/api/power/dashboard')
def api_power_dashboard():
    """Power budget summary with autonomy projection."""
    with db_session() as db:
        devices = db.execute('SELECT * FROM power_devices WHERE status = ?', ('active',)).fetchall()
        logs = [dict(r) for r in db.execute('SELECT * FROM power_log ORDER BY created_at DESC LIMIT 24').fetchall()]

    # Calculate totals from device registry
    total_solar_w = 0
    total_battery_wh = 0
    for d in devices:
        specs = json.loads(d['specs'] or '{}')
        if d['device_type'] == 'solar_panel':
            total_solar_w += specs.get('watts', 0) * specs.get('count', 1)
        elif d['device_type'] == 'battery':
            total_battery_wh += specs.get('capacity_wh', 0) * specs.get('count', 1)

    # Average consumption from recent logs
    avg_load_w = 0
    avg_solar_w = 0
    latest_voltage = None
    latest_soc = None
    if logs:
        load_readings = [l['load_watts'] for l in logs if l['load_watts']]
        solar_readings = [l['solar_watts'] for l in logs if l['solar_watts']]
        avg_load_w = sum(load_readings) / len(load_readings) if load_readings else 0
        avg_solar_w = sum(solar_readings) / len(solar_readings) if solar_readings else 0
        latest_voltage = logs[0].get('battery_voltage')
        latest_soc = logs[0].get('battery_soc')

    # Autonomy calculation
    daily_consumption_wh = avg_load_w * 24 if avg_load_w else 0
    daily_solar_wh = avg_solar_w * 5 if avg_solar_w else 0  # ~5 sun hours avg
    usable_battery_wh = total_battery_wh * 0.8  # 80% depth of discharge
    net_daily = daily_solar_wh - daily_consumption_wh

    if daily_consumption_wh > 0 and net_daily < 0:
        autonomy_days = usable_battery_wh / abs(net_daily) if abs(net_daily) > 0 else 999
    elif daily_consumption_wh > 0:
        autonomy_days = 999  # solar covers load
    else:
        autonomy_days = 999

    return jsonify({
        'total_solar_w': total_solar_w, 'total_battery_wh': total_battery_wh,
        'avg_load_w': round(avg_load_w, 1), 'avg_solar_w': round(avg_solar_w, 1),
        'daily_consumption_wh': round(daily_consumption_wh), 'daily_solar_wh': round(daily_solar_wh),
        'net_daily_wh': round(net_daily), 'autonomy_days': round(min(autonomy_days, 999), 1),
        'latest_voltage': latest_voltage, 'latest_soc': latest_soc,
        'device_count': len(devices), 'log_count': len(logs),
    })


# ─── Power History ──────────────────────────────────────────────────

@power_bp.route('/api/power/history')
def api_power_history():
    """Power log with charting data."""
    period = request.args.get('period', '24h')
    period_map = {'24h': '-24 hours', '7d': '-7 days', '30d': '-30 days'}
    interval = period_map.get(period, '-24 hours')
    with db_session() as db:
        rows = db.execute(f"SELECT battery_soc, solar_watts, load_watts, created_at FROM power_log WHERE created_at >= datetime('now', ?) ORDER BY created_at",
                          (interval,)).fetchall()
    return jsonify([dict(r) for r in rows])


# ─── Autonomy Forecast ──────────────────────────────────────────────

@power_bp.route('/api/power/autonomy-forecast')
def api_power_autonomy():
    """Projected days of autonomy based on recent trends."""
    with db_session() as db:
        # Get last 24h of power data
        rows = db.execute("SELECT battery_soc, solar_watts, load_watts FROM power_log WHERE created_at >= datetime('now', '-24 hours') ORDER BY created_at DESC").fetchall()
        if not rows:
            return jsonify({'days': None, 'message': 'No power data available'})
        avg_load = sum(r['load_watts'] or 0 for r in rows) / len(rows)
        avg_solar = sum(r['solar_watts'] or 0 for r in rows) / len(rows)
        current_soc = rows[0]['battery_soc'] or 0
        # Sum actual battery capacity from registered devices, fallback to 5kWh
        bat_rows = db.execute(
            "SELECT specs FROM power_devices WHERE device_type = 'battery' AND status = 'active'"
        ).fetchall()
        total_battery_wh = 0
        for br in bat_rows:
            specs = json.loads(br['specs'] or '{}')
            total_battery_wh += specs.get('capacity_wh', 0) * specs.get('count', 1)
        if total_battery_wh <= 0:
            total_battery_wh = 5000  # fallback default
        battery_wh = total_battery_wh * (current_soc / 100)
        net_drain = max(0.1, avg_load - avg_solar)  # watts net drain
        hours = battery_wh / net_drain if net_drain > 0 else 999
        return jsonify({
            'days': round(hours / 24, 1),
            'hours': round(hours, 1),
            'current_soc': current_soc,
            'avg_load_w': round(avg_load, 1),
            'avg_solar_w': round(avg_solar, 1),
            'net_drain_w': round(net_drain, 1),
        })
# ─── Solar Forecast Helper ──────────────────────────────────────────

def _calculate_solar(lat, lng, date_str, panel_watts=100, panel_count=1, efficiency=0.85):
    """Calculate solar energy production estimate from location + date (no hardware needed)."""
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    day_of_year = dt.timetuple().tm_yday

    # Solar declination (degrees)
    decl = 23.45 * math.sin(math.radians(360 / 365 * (day_of_year - 81)))
    decl_rad = math.radians(decl)
    lat_rad = math.radians(lat)

    # Hour angle at sunrise/sunset
    cos_ha = -math.tan(lat_rad) * math.tan(decl_rad)
    cos_ha = max(-1, min(1, cos_ha))  # clamp for polar regions

    if cos_ha <= -1:
        day_length_hours = 24.0
        ha_deg = 180.0
    elif cos_ha >= 1:
        day_length_hours = 0.0
        ha_deg = 0.0
    else:
        ha_deg = math.degrees(math.acos(cos_ha))
        day_length_hours = 2.0 * ha_deg / 15.0

    # Sunrise / sunset / solar noon
    solar_noon_offset = -lng / 15.0
    solar_noon_utc = 12.0 + solar_noon_offset
    sunrise_utc = solar_noon_utc - day_length_hours / 2
    sunset_utc = solar_noon_utc + day_length_hours / 2

    def fmt_time(h):
        h = h % 24
        hh = int(h)
        mm = int((h - hh) * 60)
        return f'{hh:02d}:{mm:02d}'

    max_altitude = 90 - abs(lat - decl)

    # Peak sun hours with air mass integration
    if day_length_hours <= 0:
        peak_sun_hours = 0.0
    else:
        steps = max(1, int(day_length_hours * 2))
        total_intensity = 0.0
        step_h = day_length_hours / steps
        for i in range(steps):
            t = -day_length_hours / 2 + step_h * (i + 0.5)
            hour_angle = math.radians(t * 15)
            sin_elev = (math.sin(lat_rad) * math.sin(decl_rad) +
                        math.cos(lat_rad) * math.cos(decl_rad) * math.cos(hour_angle))
            if sin_elev <= 0:
                continue
            elev = math.asin(sin_elev)
            elev_deg = math.degrees(elev)
            if elev_deg > 0:
                air_mass = 1 / (math.sin(elev) + 0.50572 * (elev_deg + 6.07995) ** -1.6364)
            else:
                air_mass = 40
            intensity = 0.7 ** (air_mass ** 0.678)
            total_intensity += intensity * step_h
        peak_sun_hours = total_intensity

    system_watts = panel_watts * panel_count
    clear_sky_kwh = round(system_watts * peak_sun_hours * efficiency / 1000, 2)

    # Cloud cover factor from recent weather observations
    cloud_factor = 1.0
    try:
        with db_session() as db:
            wx = db.execute(
                "SELECT clouds FROM weather_log WHERE created_at >= datetime('now', '-48 hours') ORDER BY created_at DESC LIMIT 10"
            ).fetchall()
        if wx:
            cloud_map = {'clear': 1.0, 'few': 0.9, 'scattered': 0.75, 'broken': 0.55, 'overcast': 0.3,
                         'heavy': 0.2, 'partly': 0.7, 'mostly': 0.45}
            factors = []
            for row in wx:
                c = (row['clouds'] or '').lower().strip()
                for key, val in cloud_map.items():
                    if key in c:
                        factors.append(val)
                        break
            if factors:
                cloud_factor = round(sum(factors) / len(factors), 2)
    except Exception:
        pass

    estimated_kwh = round(clear_sky_kwh * cloud_factor, 2)

    return {
        'date': date_str,
        'sunrise': fmt_time(sunrise_utc),
        'sunset': fmt_time(sunset_utc),
        'solar_noon': fmt_time(solar_noon_utc),
        'day_length_hours': round(day_length_hours, 2),
        'peak_sun_hours': round(peak_sun_hours, 2),
        'max_altitude_degrees': round(max_altitude, 1),
        'clear_sky_kwh': clear_sky_kwh,
        'estimated_kwh': estimated_kwh,
        'cloud_factor': cloud_factor,
    }


# ─── Solar Forecast ─────────────────────────────────────────────────

@power_bp.route('/api/power/solar-forecast')
def api_solar_forecast():
    """7-day solar energy forecast with hourly breakdown for today."""
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)

    # Auto-detect from settings or waypoints if not provided
    if lat is None or lng is None:
        with db_session() as db:
            mc = db.execute("SELECT value FROM settings WHERE key = 'map_center'").fetchone()
            if mc and mc['value']:
                try:
                    parts = json.loads(mc['value'])
                    if isinstance(parts, list) and len(parts) >= 2:
                        lat = lat if lat is not None else float(parts[0])
                        lng = lng if lng is not None else float(parts[1])
                    elif isinstance(parts, dict):
                        lat = lat if lat is not None else float(parts.get('lat', 0))
                        lng = lng if lng is not None else float(parts.get('lng', 0))
                except (json.JSONDecodeError, ValueError):
                    pass
            if lat is None or lng is None:
                wp = db.execute("SELECT lat, lng FROM waypoints ORDER BY created_at DESC LIMIT 1").fetchone()
                if wp:
                    lat = lat if lat is not None else wp['lat']
                    lng = lng if lng is not None else wp['lng']
    if lat is None or lng is None:
        return jsonify({'error': 'lat and lng required \u2014 set a map center or add a waypoint'}), 400

    date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    panel_watts = request.args.get('panel_watts', 100, type=int)
    panel_count = request.args.get('panel_count', 1, type=int)
    efficiency = request.args.get('efficiency', 0.85, type=float)

    try:
        base_date = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400

    today = _calculate_solar(lat, lng, date_str, panel_watts, panel_count, efficiency)

    # Hourly breakdown for today
    hourly = []
    today_dt = datetime.strptime(date_str, '%Y-%m-%d')
    day_of_year = today_dt.timetuple().tm_yday
    decl = 23.45 * math.sin(math.radians(360 / 365 * (day_of_year - 81)))
    lat_rad = math.radians(lat)
    decl_rad = math.radians(decl)

    for hour in range(24):
        solar_noon_offset = -lng / 15.0
        solar_hour = hour - (12.0 + solar_noon_offset)
        ha_rad = math.radians(solar_hour * 15)
        sin_elev = (math.sin(lat_rad) * math.sin(decl_rad) +
                    math.cos(lat_rad) * math.cos(decl_rad) * math.cos(ha_rad))
        if sin_elev <= 0:
            hourly.append({'hour': hour, 'watts': 0, 'elevation': 0})
            continue
        elev = math.asin(sin_elev)
        elev_deg = math.degrees(elev)
        air_mass = 1 / (math.sin(elev) + 0.50572 * (elev_deg + 6.07995) ** -1.6364)
        intensity = 0.7 ** (air_mass ** 0.678)
        watts = round(panel_watts * panel_count * intensity * efficiency * today['cloud_factor'])
        hourly.append({'hour': hour, 'watts': watts, 'elevation': round(elev_deg, 1)})

    today['hourly'] = hourly

    # 7-day forecast
    daily = []
    for i in range(7):
        d = base_date + timedelta(days=i)
        day_data = _calculate_solar(lat, lng, d.strftime('%Y-%m-%d'), panel_watts, panel_count, efficiency)
        daily.append(day_data)

    return jsonify({
        'lat': lat, 'lng': lng,
        'panel_watts': panel_watts, 'panel_count': panel_count, 'efficiency': efficiency,
        'today': today,
        'daily': daily,
    })


# ─── Solar History ──────────────────────────────────────────────────

@power_bp.route('/api/power/solar-history')
def api_solar_history():
    """Actual vs estimated solar data for the past 30 days."""
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    panel_watts = request.args.get('panel_watts', 100, type=int)
    panel_count = request.args.get('panel_count', 1, type=int)
    efficiency = request.args.get('efficiency', 0.85, type=float)

    if lat is None or lng is None:
        with db_session() as db:
            mc = db.execute("SELECT value FROM settings WHERE key = 'map_center'").fetchone()
            if mc and mc['value']:
                try:
                    parts = json.loads(mc['value'])
                    if isinstance(parts, list) and len(parts) >= 2:
                        lat = lat if lat is not None else float(parts[0])
                        lng = lng if lng is not None else float(parts[1])
                except (json.JSONDecodeError, ValueError):
                    pass
    with db_session() as db:
        rows = db.execute(
            "SELECT solar_wh_today, solar_watts, created_at FROM power_log "
            "WHERE created_at >= datetime('now', '-30 days') ORDER BY created_at"
        ).fetchall()
    by_date = defaultdict(list)
    for r in rows:
        try:
            d = r['created_at'][:10]
            by_date[d].append(dict(r))
        except Exception:
            pass

    history = []
    now = datetime.now()
    for i in range(30):
        d = (now - timedelta(days=29 - i)).strftime('%Y-%m-%d')
        entries = by_date.get(d, [])
        actual_wh = None
        if entries:
            wh_vals = [e.get('solar_wh_today') for e in entries if e.get('solar_wh_today')]
            if wh_vals:
                actual_wh = max(wh_vals)
            else:
                sw = [e.get('solar_watts') for e in entries if e.get('solar_watts')]
                if sw:
                    actual_wh = round(sum(sw) / len(sw) * 5)

        estimated = None
        if lat is not None and lng is not None:
            try:
                est = _calculate_solar(lat, lng, d, panel_watts, panel_count, efficiency)
                estimated = est['estimated_kwh'] * 1000
            except Exception:
                pass

        history.append({
            'date': d,
            'actual_wh': actual_wh,
            'estimated_wh': round(estimated) if estimated else None,
            'readings': len(entries),
        })

    return jsonify(history)


# ─── Sensor Devices CRUD ────────────────────────────────────────────

@power_bp.route('/api/sensors/devices')
def api_sensor_devices_list():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM sensor_devices ORDER BY name LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    return jsonify([dict(r) for r in rows])


@power_bp.route('/api/sensors/devices', methods=['POST'])
def api_sensor_devices_create():
    data = request.get_json() or {}
    with db_session() as db:
        db.execute('INSERT INTO sensor_devices (device_type, name, connection_type, connection_config, polling_interval_sec, status) VALUES (?,?,?,?,?,?)',
                   (data.get('device_type', 'manual'), data.get('name', 'New Sensor'),
                    data.get('connection_type', 'manual'), json.dumps(data.get('connection_config', {})),
                    data.get('polling_interval_sec', 300), data.get('status', 'active')))
        db.commit()
        sid = db.execute('SELECT last_insert_rowid()').fetchone()[0]
    return jsonify({'status': 'created', 'id': sid})


@power_bp.route('/api/sensors/devices/<int:sid>', methods=['DELETE'])
def api_sensor_devices_delete(sid):
    with db_session() as db:
        db.execute('DELETE FROM sensor_devices WHERE id = ?', (sid,))
        db.execute('DELETE FROM sensor_readings WHERE device_id = ?', (sid,))
        db.commit()
    return jsonify({'status': 'deleted'})


# ─── Sensor Readings ────────────────────────────────────────────────

@power_bp.route('/api/sensors/readings/<int:device_id>')
def api_sensor_readings(device_id):
    period = request.args.get('period', '24h')
    period_map = {'24h': '-24 hours', '7d': '-7 days', '30d': '-30 days'}
    interval = period_map.get(period, '-24 hours')
    with db_session() as db:
        rows = db.execute(f"SELECT * FROM sensor_readings WHERE device_id = ? AND created_at >= datetime('now', ?) ORDER BY created_at",
                          (device_id, interval)).fetchall()
    return jsonify([dict(r) for r in rows])


@power_bp.route('/api/sensors/readings', methods=['POST'])
def api_sensor_readings_create():
    data = request.get_json() or {}
    with db_session() as db:
        db.execute('INSERT INTO sensor_readings (device_id, reading_type, value, unit) VALUES (?,?,?,?)',
                   (data.get('device_id'), data.get('reading_type', ''), data.get('value', 0), data.get('unit', '')))
        # Update device last_reading
        db.execute('UPDATE sensor_devices SET last_reading = ? WHERE id = ?',
                   (json.dumps({'type': data.get('reading_type'), 'value': data.get('value'), 'unit': data.get('unit')}), data.get('device_id')))
        db.commit()
    return jsonify({'status': 'recorded'})


# ─── Sensor Chart ───────────────────────────────────────────────────

@power_bp.route('/api/sensors/chart/<int:device_id>')
def api_sensors_chart(device_id):
    """Return time-series data for charting, aggregated by hour/day/week."""
    with db_session() as db:
        range_param = request.args.get('range', '24h')
        reading_type = request.args.get('type', '')

        # Determine time window and aggregation
        now = datetime.now()
        if range_param == '1h':
            since = (now - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
            agg = None  # raw data
        elif range_param == '24h':
            since = (now - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            agg = 'hour'
        elif range_param == '7d':
            since = (now - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
            agg = 'hour'
        elif range_param == '30d':
            since = (now - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
            agg = 'day'
        elif range_param == '90d':
            since = (now - timedelta(days=90)).strftime('%Y-%m-%d %H:%M:%S')
            agg = 'week'
        else:
            since = (now - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            agg = 'hour'

        query_params = [device_id, since]
        type_filter = ''
        if reading_type:
            type_filter = ' AND reading_type = ?'
            query_params.append(reading_type)

        if agg == 'hour':
            rows = db.execute(f'''
                SELECT strftime('%Y-%m-%d %H:00:00', created_at) as timestamp,
                       reading_type, unit,
                       AVG(value) as avg_value, MIN(value) as min_value, MAX(value) as max_value,
                       COUNT(*) as sample_count
                FROM sensor_readings
                WHERE device_id = ? AND created_at >= ?{type_filter}
                GROUP BY strftime('%Y-%m-%d %H', created_at), reading_type
                ORDER BY timestamp ASC
            ''', query_params).fetchall()
        elif agg == 'day':
            rows = db.execute(f'''
                SELECT strftime('%Y-%m-%d', created_at) as timestamp,
                       reading_type, unit,
                       AVG(value) as avg_value, MIN(value) as min_value, MAX(value) as max_value,
                       COUNT(*) as sample_count
                FROM sensor_readings
                WHERE device_id = ? AND created_at >= ?{type_filter}
                GROUP BY strftime('%Y-%m-%d', created_at), reading_type
                ORDER BY timestamp ASC
            ''', query_params).fetchall()
        elif agg == 'week':
            rows = db.execute(f'''
                SELECT strftime('%Y-W%W', created_at) as timestamp,
                       reading_type, unit,
                       AVG(value) as avg_value, MIN(value) as min_value, MAX(value) as max_value,
                       COUNT(*) as sample_count
                FROM sensor_readings
                WHERE device_id = ? AND created_at >= ?{type_filter}
                GROUP BY strftime('%Y-W%W', created_at), reading_type
                ORDER BY timestamp ASC
            ''', query_params).fetchall()
        else:
            rows = db.execute(f'''
                SELECT created_at as timestamp, reading_type, value as avg_value, value as min_value, value as max_value, unit, 1 as sample_count
                FROM sensor_readings
                WHERE device_id = ? AND created_at >= ?{type_filter}
                ORDER BY created_at ASC
            ''', query_params).fetchall()

        # Get device info
        device = db.execute('SELECT * FROM sensor_devices WHERE id = ?', (device_id,)).fetchone()

    series = {}
    for r in rows:
        rt = r['reading_type']
        if rt not in series:
            series[rt] = {'reading_type': rt, 'unit': r['unit'], 'data': []}
        series[rt]['data'].append({
            'timestamp': r['timestamp'],
            'avg': round(r['avg_value'], 2) if r['avg_value'] is not None else None,
            'min': round(r['min_value'], 2) if r['min_value'] is not None else None,
            'max': round(r['max_value'], 2) if r['max_value'] is not None else None,
            'samples': r['sample_count'],
        })

    return jsonify({
        'device_id': device_id,
        'device_name': dict(device)['name'] if device else 'Unknown',
        'range': range_param,
        'aggregation': agg or 'raw',
        'series': list(series.values()),
    })


# ─── Generator Management ─────────────────────────────────────────

@power_bp.route('/api/power/generators', methods=['GET'])
def api_generators_list():
    with db_session() as db:
        rows = db.execute('SELECT * FROM generators ORDER BY name LIMIT 10000').fetchall()
        return jsonify([dict(r) for r in rows])


@power_bp.route('/api/power/generators', methods=['POST'])
def api_generators_create():
    data = request.get_json() or {}
    if not data.get('name'):
        return jsonify({'error': 'Name is required'}), 400
    with db_session() as db:
        db.execute(
            'INSERT INTO generators (name, rated_watts, fuel_type, tank_capacity_gal, fuel_consumption_gph, oil_change_interval_hours, notes) VALUES (?,?,?,?,?,?,?)',
            (data['name'], data.get('rated_watts', 0), data.get('fuel_type', 'gasoline'),
             data.get('tank_capacity_gal', 0), data.get('fuel_consumption_gph', 0),
             data.get('oil_change_interval_hours', 100), data.get('notes', '')))
        db.commit()
        gid = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        return jsonify({'status': 'created', 'id': gid}), 201


@power_bp.route('/api/power/generators/<int:gid>', methods=['PUT'])
def api_generators_update(gid):
    data = request.get_json() or {}
    with db_session() as db:
        gen = db.execute('SELECT * FROM generators WHERE id = ?', (gid,)).fetchone()
        if not gen:
            return jsonify({'error': 'Generator not found'}), 404
        fields = ['name', 'rated_watts', 'fuel_type', 'tank_capacity_gal',
                  'fuel_consumption_gph', 'oil_change_interval_hours', 'notes']
        updates = []
        values = []
        for f in fields:
            if f in data:
                updates.append(f'{f} = ?')
                values.append(data[f])
        if not updates:
            return jsonify({'error': 'No fields to update'}), 400
        values.append(gid)
        db.execute(f"UPDATE generators SET {', '.join(updates)} WHERE id = ?", values)
        db.commit()
        return jsonify({'status': 'updated'})


@power_bp.route('/api/power/generators/<int:gid>', methods=['DELETE'])
def api_generators_delete(gid):
    with db_session() as db:
        db.execute('DELETE FROM generator_sessions WHERE generator_id = ?', (gid,))
        db.execute('DELETE FROM generators WHERE id = ?', (gid,))
        db.commit()
        return jsonify({'status': 'deleted'})


@power_bp.route('/api/power/generators/<int:gid>/start', methods=['POST'])
def api_generator_start(gid):
    with db_session() as db:
        gen = db.execute('SELECT * FROM generators WHERE id = ?', (gid,)).fetchone()
        if not gen:
            return jsonify({'error': 'Generator not found'}), 404
        # Check for already-open session
        open_session = db.execute(
            'SELECT id FROM generator_sessions WHERE generator_id = ? AND ended_at IS NULL', (gid,)
        ).fetchone()
        if open_session:
            return jsonify({'error': 'Generator already running'}), 409
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.execute('INSERT INTO generator_sessions (generator_id, started_at) VALUES (?, ?)', (gid, now))
        db.execute('UPDATE generators SET last_started = ? WHERE id = ?', (now, gid))
        db.commit()
        return jsonify({'status': 'started', 'started_at': now})


@power_bp.route('/api/power/generators/<int:gid>/stop', methods=['POST'])
def api_generator_stop(gid):
    with db_session() as db:
        gen = db.execute('SELECT * FROM generators WHERE id = ?', (gid,)).fetchone()
        if not gen:
            return jsonify({'error': 'Generator not found'}), 404
        session = db.execute(
            'SELECT * FROM generator_sessions WHERE generator_id = ? AND ended_at IS NULL ORDER BY started_at DESC LIMIT 1',
            (gid,)
        ).fetchone()
        if not session:
            return jsonify({'error': 'Generator is not running'}), 409
        now = datetime.now()
        try:
            started = datetime.strptime(session['started_at'], '%Y-%m-%d %H:%M:%S')
        except (ValueError, KeyError):
            return jsonify({'error': 'Generator session has a missing or malformed start time'}), 400
        runtime_hours = (now - started).total_seconds() / 3600.0
        fuel_consumption_gph = gen['fuel_consumption_gph'] or 0
        fuel_used_gal = fuel_consumption_gph * runtime_hours
        now_str = now.strftime('%Y-%m-%d %H:%M:%S')
        db.execute(
            'UPDATE generator_sessions SET ended_at = ?, runtime_hours = ?, fuel_used_gal = ? WHERE id = ?',
            (now_str, round(runtime_hours, 3), round(fuel_used_gal, 3), session['id']))
        new_total = (gen['total_runtime_hours'] or 0) + runtime_hours
        db.execute('UPDATE generators SET total_runtime_hours = ? WHERE id = ?', (round(new_total, 3), gid))
        db.commit()
        return jsonify({
            'status': 'stopped',
            'runtime_hours': round(runtime_hours, 3),
            'fuel_used_gal': round(fuel_used_gal, 3),
            'total_runtime_hours': round(new_total, 3),
        })


@power_bp.route('/api/power/generators/<int:gid>/status', methods=['GET'])
def api_generator_status(gid):
    with db_session() as db:
        gen = db.execute('SELECT * FROM generators WHERE id = ?', (gid,)).fetchone()
        if not gen:
            return jsonify({'error': 'Generator not found'}), 404
        gen_dict = dict(gen)
        session = db.execute(
            'SELECT * FROM generator_sessions WHERE generator_id = ? AND ended_at IS NULL ORDER BY started_at DESC LIMIT 1',
            (gid,)
        ).fetchone()
        running = session is not None
        current_runtime_hours = 0
        if running:
            started = datetime.strptime(session['started_at'], '%Y-%m-%d %H:%M:%S')
            current_runtime_hours = (datetime.now() - started).total_seconds() / 3600.0

        tank_gal = gen_dict['tank_capacity_gal'] or 0
        consumption_gph = gen_dict['fuel_consumption_gph'] or 0
        total_runtime = gen_dict['total_runtime_hours'] or 0
        oil_interval = gen_dict['oil_change_interval_hours'] or 100

        # Estimate fuel remaining (assumes full tank at start of current session)
        fuel_remaining_gal = max(0, tank_gal - (consumption_gph * current_runtime_hours)) if running else tank_gal
        estimated_runtime_hours = fuel_remaining_gal / consumption_gph if consumption_gph > 0 else None
        hours_until_oil_change = max(0, oil_interval - (total_runtime % oil_interval))

        return jsonify({
            'generator': gen_dict,
            'running': running,
            'current_runtime_hours': round(current_runtime_hours, 3),
            'fuel_remaining_gal': round(fuel_remaining_gal, 2),
            'estimated_runtime_hours': round(estimated_runtime_hours, 1) if estimated_runtime_hours is not None else None,
            'hours_until_oil_change': round(hours_until_oil_change, 1),
        })


# ─── Battery Health ────────────────────────────────────────────────

@power_bp.route('/api/power/battery-health', methods=['GET'])
def api_battery_health():
    """Battery health analysis based on historical power log data."""
    with db_session() as db:
        rows = db.execute(
            "SELECT battery_voltage, battery_soc, created_at FROM power_log "
            "WHERE battery_soc IS NOT NULL ORDER BY created_at ASC"
        ).fetchall()

        if not rows:
            return jsonify({'error': 'No battery data available'}), 404

        # Count charge cycles: SOC dropping below 30% then rising above 80%
        cycle_count = 0
        was_low = False
        for r in rows:
            soc = r['battery_soc'] or 0
            if soc < 30:
                was_low = True
            elif soc > 80 and was_low:
                cycle_count += 1
                was_low = False

        # Voltage trend analysis for capacity estimation
        # Compare average voltage of first 10% of readings vs last 10%
        voltages = [r['battery_voltage'] for r in rows if r['battery_voltage']]
        estimated_capacity_pct = 100.0
        if len(voltages) >= 20:
            chunk = max(1, len(voltages) // 10)
            early_avg = sum(voltages[:chunk]) / chunk
            recent_avg = sum(voltages[-chunk:]) / chunk
            if early_avg > 0:
                # Voltage degradation roughly correlates with capacity loss
                voltage_ratio = recent_avg / early_avg
                estimated_capacity_pct = round(min(100, max(0, voltage_ratio * 100)), 1)

        # Replacement forecast based on typical LiFePO4 ~3000 cycles
        typical_cycle_life = 3000
        remaining_cycles = max(0, typical_cycle_life - cycle_count)
        # Estimate cycles per year from data span
        if len(rows) >= 2:
            first_dt = datetime.strptime(rows[0]['created_at'][:19], '%Y-%m-%d %H:%M:%S')
            last_dt = datetime.strptime(rows[-1]['created_at'][:19], '%Y-%m-%d %H:%M:%S')
            span_days = max(1, (last_dt - first_dt).days)
            cycles_per_year = (cycle_count / span_days) * 365 if span_days > 0 else 0
            years_remaining = remaining_cycles / cycles_per_year if cycles_per_year > 0 else None
        else:
            cycles_per_year = 0
            years_remaining = None

        return jsonify({
            'cycle_count': cycle_count,
            'estimated_capacity_pct': estimated_capacity_pct,
            'total_readings': len(rows),
            'cycles_per_year': round(cycles_per_year, 1) if cycles_per_year else 0,
            'replacement_forecast': {
                'typical_cycle_life': typical_cycle_life,
                'remaining_cycles': remaining_cycles,
                'estimated_years_remaining': round(years_remaining, 1) if years_remaining is not None else None,
            },
        })


# ─── Load Scheduling ──────────────────────────────────────────────

@power_bp.route('/api/power/load-schedule', methods=['GET'])
def api_power_load_schedule():
    """Optimal load scheduling based on device priorities and solar forecast."""
    with db_session() as db:
        devices = db.execute(
            "SELECT * FROM power_devices WHERE status = 'active' ORDER BY device_type, name"
        ).fetchall()

        # Categorize devices by priority based on device_type
        priority_map = {
            'inverter': 'critical', 'charge_controller': 'critical', 'battery': 'critical',
            'fridge': 'high', 'router': 'high', 'water_pump': 'high',
            'laptop': 'medium', 'fan': 'medium', 'light': 'medium',
            'tv': 'low', 'heater': 'low', 'air_conditioner': 'low',
        }

        categorized = {'critical': [], 'high': [], 'medium': [], 'low': []}
        total_load_w = 0
        for d in devices:
            d_dict = dict(d)
            specs = json.loads(d_dict.get('specs') or '{}')
            watts = specs.get('watts', 0) * specs.get('count', 1)
            d_dict['watts'] = watts
            d_dict['specs'] = specs
            priority = priority_map.get(d_dict['device_type'], 'medium')
            d_dict['priority'] = priority
            categorized[priority].append(d_dict)
            total_load_w += watts

        # Get solar production estimate per hour (use recent averages)
        logs = db.execute(
            "SELECT solar_watts, load_watts, created_at FROM power_log "
            "WHERE created_at >= datetime('now', '-7 days') ORDER BY created_at"
        ).fetchall()

        # Build hourly solar profile from historical data
        hourly_solar = defaultdict(list)
        hourly_load = defaultdict(list)
        for log in logs:
            try:
                hour = int(log['created_at'][11:13])
                if log['solar_watts']:
                    hourly_solar[hour].append(log['solar_watts'])
                if log['load_watts']:
                    hourly_load[hour].append(log['load_watts'])
            except (ValueError, IndexError):
                pass

        # Generate 24-hour schedule
        schedule = []
        for hour in range(24):
            solar_readings = hourly_solar.get(hour, [])
            load_readings = hourly_load.get(hour, [])
            avg_solar = sum(solar_readings) / len(solar_readings) if solar_readings else 0
            avg_load = sum(load_readings) / len(load_readings) if load_readings else 0
            surplus = avg_solar - avg_load

            # Determine which priority levels can run
            recommended = ['critical']
            if surplus > 0:
                recommended.append('high')
            if surplus > total_load_w * 0.3:
                recommended.append('medium')
            if surplus > total_load_w * 0.6:
                recommended.append('low')

            schedule.append({
                'hour': hour,
                'avg_solar_w': round(avg_solar, 1),
                'avg_load_w': round(avg_load, 1),
                'surplus_w': round(surplus, 1),
                'recommended_priorities': recommended,
            })

        return jsonify({
            'devices': categorized,
            'total_load_w': total_load_w,
            'schedule': schedule,
        })
