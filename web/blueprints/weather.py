"""Weather observation, prediction, and action-rule routes."""

import json
import math
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify
from db import db_session

weather_bp = Blueprint('weather', __name__)


def _clone_json_fallback(fallback):
    if isinstance(fallback, list):
        return list(fallback)
    if isinstance(fallback, dict):
        return dict(fallback)
    return fallback


def _safe_json_object(value, fallback=None):
    if fallback is None:
        fallback = {}
    if value in (None, ''):
        return _clone_json_fallback(fallback)
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return _clone_json_fallback(fallback)
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            return _clone_json_fallback(fallback)
        return dict(parsed) if isinstance(parsed, dict) else _clone_json_fallback(fallback)
    return _clone_json_fallback(fallback)


@weather_bp.route('/api/weather')
def api_weather_list():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM weather_log ORDER BY created_at DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    return jsonify([dict(r) for r in rows])


@weather_bp.route('/api/weather', methods=['POST'])
def api_weather_create():
    data = request.get_json() or {}
    with db_session() as db:
        cur = db.execute(
            'INSERT INTO weather_log (pressure_hpa, temp_f, wind_dir, wind_speed, clouds, precip, visibility, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (data.get('pressure_hpa'), data.get('temp_f'), data.get('wind_dir', ''),
             data.get('wind_speed', ''), data.get('clouds', ''), data.get('precip', ''),
             data.get('visibility', ''), data.get('notes', '')))
        db.commit()
        row = db.execute('SELECT * FROM weather_log WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@weather_bp.route('/api/weather/trend')
def api_weather_trend():
    """Return pressure trend for weather prediction."""
    with db_session() as db:
        rows = db.execute('SELECT pressure_hpa, created_at FROM weather_log WHERE pressure_hpa IS NOT NULL ORDER BY created_at DESC LIMIT 10').fetchall()
    if len(rows) < 2:
        return jsonify({'trend': 'insufficient', 'prediction': 'Need at least 2 pressure readings', 'readings': len(rows)})
    newest = rows[0]['pressure_hpa']
    oldest = rows[-1]['pressure_hpa']
    diff = newest - oldest
    if diff > 3:
        trend, pred = 'rising_fast', 'Fair weather coming. Clearing skies likely.'
    elif diff > 1:
        trend, pred = 'rising', 'Weather improving. Gradual clearing.'
    elif diff < -3:
        trend, pred = 'falling_fast', 'Storm approaching! Prepare for severe weather within 12-24 hours.'
    elif diff < -1:
        trend, pred = 'falling', 'Weather deteriorating. Rain/wind likely within 24 hours.'
    else:
        trend, pred = 'steady', 'Stable conditions. Current weather pattern continuing.'
    return jsonify({'trend': trend, 'prediction': pred, 'diff_hpa': round(diff, 1),
                   'current': newest, 'readings': len(rows)})


# --- Weather & Zambretti Prediction ---

@weather_bp.route('/api/weather/readings', methods=['GET'])
def api_weather_readings():
    """Get weather readings history for pressure graph."""
    hours = request.args.get('hours', 48, type=int)
    with db_session() as db:
        rows = db.execute(
            "SELECT * FROM weather_readings WHERE created_at >= datetime('now', ? || ' hours') ORDER BY created_at ASC",
            (f'-{min(hours, 168)}',)
        ).fetchall()
        return jsonify([dict(r) for r in rows])
@weather_bp.route('/api/weather/readings', methods=['POST'])
def api_weather_reading_add():
    """Add a weather reading (manual or from sensor)."""
    d = request.json or {}
    with db_session() as db:
        db.execute(
            'INSERT INTO weather_readings (source, pressure_hpa, temp_f, humidity, wind_dir, wind_speed_mph) VALUES (?, ?, ?, ?, ?, ?)',
            (d.get('source', 'manual'), d.get('pressure_hpa'), d.get('temp_f'), d.get('humidity'), d.get('wind_dir', ''), d.get('wind_speed_mph'))
        )
        db.commit()
        # Run Zambretti prediction if we have enough data
        prediction = _zambretti_predict(db)
        if prediction:
            db.execute('UPDATE weather_readings SET prediction = ?, zambretti_code = ? WHERE id = (SELECT MAX(id) FROM weather_readings)',
                       (prediction['forecast'], prediction['code']))
            db.commit()
        # Auto-evaluate weather action rules
        try:
            _evaluate_weather_action_rules(db)
        except Exception:
            pass
        return jsonify({'status': 'ok', 'prediction': prediction})
@weather_bp.route('/api/weather/predict')
def api_weather_predict():
    """Get current Zambretti weather prediction."""
    with db_session() as db:
        prediction = _zambretti_predict(db)
        return jsonify(prediction or {'forecast': 'Insufficient data', 'trend': 'unknown', 'code': -1})
def _zambretti_predict(db):
    """Zambretti weather forecasting algorithm -- pure offline prediction from barometric pressure trend."""
    try:
        rows = db.execute(
            "SELECT pressure_hpa, created_at FROM weather_readings WHERE pressure_hpa IS NOT NULL ORDER BY created_at DESC LIMIT 12"
        ).fetchall()
        if len(rows) < 3:
            return None

        current = rows[0]['pressure_hpa']
        oldest = rows[-1]['pressure_hpa']
        delta = current - oldest  # positive = rising, negative = falling

        # Determine trend
        if delta > 1.5:
            trend = 'rising'
        elif delta < -1.5:
            trend = 'falling'
        else:
            trend = 'steady'

        # Simplified Zambretti algorithm
        # Adjust pressure to sea level equivalent (assume ~0m elevation for now)
        p = current

        month = datetime.now().month
        is_winter = month in (11, 12, 1, 2, 3)

        if trend == 'falling':
            # Zambretti falling pressure table (Z = 130 - (p/81))
            z = max(1, min(26, int(130 - (p / 8.1))))
            if is_winter:
                z = min(26, z + 1)
            forecasts = {
                range(1, 3): 'Settled fine weather',
                range(3, 5): 'Fine weather',
                range(5, 7): 'Fine, becoming less settled',
                range(7, 9): 'Fairly fine, showery later',
                range(9, 11): 'Showery, becoming more unsettled',
                range(11, 13): 'Unsettled, rain later',
                range(13, 16): 'Rain at times, worse later',
                range(16, 19): 'Rain at times, becoming very unsettled',
                range(19, 22): 'Very unsettled, rain',
                range(22, 27): 'Stormy, much rain',
            }
        elif trend == 'rising':
            z = max(1, min(26, int((p / 8.1) - 115)))
            if is_winter:
                z = max(1, z - 1)
            forecasts = {
                range(1, 3): 'Settled fine weather',
                range(3, 5): 'Fine weather',
                range(5, 7): 'Becoming fine',
                range(7, 9): 'Fairly fine, improving',
                range(9, 11): 'Fairly fine, possible showers early',
                range(11, 13): 'Showery early, improving',
                range(13, 16): 'Changeable, mending',
                range(16, 19): 'Rather unsettled, clearing later',
                range(19, 22): 'Unsettled, probably improving',
                range(22, 27): 'Unsettled, short fine intervals',
            }
        else:
            z = max(1, min(26, int(147 - (5 * p / 37.6))))
            forecasts = {
                range(1, 3): 'Settled fine weather',
                range(3, 5): 'Fine weather',
                range(5, 7): 'Fine, possibly showers',
                range(7, 10): 'Fairly fine, showers likely',
                range(10, 13): 'Showery, bright intervals',
                range(13, 16): 'Changeable, some rain',
                range(16, 19): 'Unsettled, rain at times',
                range(19, 22): 'Rain at frequent intervals',
                range(22, 27): 'Very unsettled, rain',
            }

        forecast = 'Unknown'
        for r, text in forecasts.items():
            if z in r:
                forecast = text
                break

        return {
            'forecast': forecast,
            'trend': trend,
            'code': z,
            'current_hpa': round(current, 1),
            'delta_hpa': round(delta, 1),
            'readings_count': len(rows),
        }
    except Exception:
        return None


@weather_bp.route('/api/weather/wind-chill')
def api_wind_chill():
    """Calculate wind chill or heat index."""
    temp_f = request.args.get('temp', type=float)
    wind_mph = request.args.get('wind', type=float)
    humidity = request.args.get('humidity', type=float)
    if temp_f is None:
        return jsonify({'error': 'temp required'}), 400

    result = {'temp_f': temp_f}

    # Wind chill (valid for temp <= 50F and wind >= 3 mph)
    if wind_mph and temp_f <= 50 and wind_mph >= 3:
        wc = 35.74 + 0.6215 * temp_f - 35.75 * (wind_mph ** 0.16) + 0.4275 * temp_f * (wind_mph ** 0.16)
        result['wind_chill_f'] = round(wc, 1)
        result['index_type'] = 'wind_chill'
    # Heat index (valid for temp >= 80F)
    elif humidity and temp_f >= 80:
        hi = -42.379 + 2.04901523*temp_f + 10.14333127*humidity - 0.22475541*temp_f*humidity - 6.83783e-3*temp_f**2 - 5.481717e-2*humidity**2 + 1.22874e-3*temp_f**2*humidity + 8.5282e-4*temp_f*humidity**2 - 1.99e-6*temp_f**2*humidity**2
        result['heat_index_f'] = round(hi, 1)
        result['index_type'] = 'heat_index'
    else:
        result['index_type'] = 'none'
        result['feels_like_f'] = temp_f

    return jsonify(result)


# --- Weather-Triggered Alerts (v5.0 Phase 9) ---

@weather_bp.route('/api/weather/check-alerts', methods=['POST'])
def api_weather_check_alerts():
    """Check weather readings for alert conditions and auto-create alerts."""
    with db_session() as db:
        rows = db.execute(
            "SELECT pressure_hpa, temp_f, created_at FROM weather_readings WHERE pressure_hpa IS NOT NULL ORDER BY created_at DESC LIMIT 6"
        ).fetchall()
        alerts_created = []
        if len(rows) >= 3:
            newest = rows[0]['pressure_hpa']
            oldest = rows[-1]['pressure_hpa']
            delta = newest - oldest
            # Rapid pressure drop (>4 hPa in ~3 hours = storm warning)
            if delta < -4:
                db.execute(
                    "INSERT INTO alerts (alert_type, severity, title, message, data) VALUES (?, ?, ?, ?, ?)",
                    ('weather', 'critical', 'Rapid Pressure Drop', f'Barometric pressure dropped {abs(round(delta,1))} hPa \u2014 storm likely imminent', json.dumps({'delta': delta, 'current': newest})))
                alerts_created.append('rapid_pressure_drop')
            elif delta < -2:
                db.execute(
                    "INSERT INTO alerts (alert_type, severity, title, message, data) VALUES (?, ?, ?, ?, ?)",
                    ('weather', 'warning', 'Pressure Falling', f'Barometric pressure dropped {abs(round(delta,1))} hPa \u2014 weather deteriorating', json.dumps({'delta': delta, 'current': newest})))
                alerts_created.append('pressure_falling')
        # Temperature extremes
        if rows:
            temp = rows[0].get('temp_f')
            if temp is not None:
                if temp >= 105:
                    db.execute("INSERT INTO alerts (alert_type, severity, title, message) VALUES ('weather', 'critical', 'Extreme Heat', ?)", (f'Temperature: {temp}\u00b0F \u2014 heat stroke danger',))
                    alerts_created.append('extreme_heat')
                elif temp <= 10:
                    db.execute("INSERT INTO alerts (alert_type, severity, title, message) VALUES ('weather', 'critical', 'Extreme Cold', ?)", (f'Temperature: {temp}\u00b0F \u2014 hypothermia/frostbite danger',))
                    alerts_created.append('extreme_cold')
        db.commit()
        return jsonify({'alerts_created': alerts_created})
# --- Weather-Triggered Actions (Phase 15) ---

def _evaluate_weather_action_rules(db):
    """Evaluate all enabled weather action rules against current conditions. Internal helper."""
    rules = db.execute('SELECT id, name, condition_type, threshold, comparison, action_type, action_data, cooldown_minutes, last_triggered FROM weather_action_rules WHERE enabled = 1').fetchall()
    if not rules:
        return []

    readings = db.execute(
        'SELECT pressure_hpa, temp_f, humidity, wind_speed_mph, created_at FROM weather_readings ORDER BY created_at DESC LIMIT 6'
    ).fetchall()
    if not readings:
        return []

    latest = dict(readings[0])
    triggered = []
    now = datetime.now()

    for rule in rules:
        rule = dict(rule)
        # Check cooldown
        if rule['last_triggered']:
            try:
                last = datetime.strptime(rule['last_triggered'], '%Y-%m-%d %H:%M:%S')
                if (now - last).total_seconds() < rule['cooldown_minutes'] * 60:
                    continue
            except (ValueError, TypeError):
                pass

        # Evaluate condition
        value = None
        ctype = rule['condition_type']
        if ctype == 'pressure_drop' and len(readings) >= 3:
            value = readings[0]['pressure_hpa'] - readings[-1]['pressure_hpa']  # negative = dropping
        elif ctype == 'pressure_rise' and len(readings) >= 3:
            value = readings[0]['pressure_hpa'] - readings[-1]['pressure_hpa']  # positive = rising
        elif ctype == 'temp_high' and latest.get('temp_f') is not None:
            value = latest['temp_f']
        elif ctype == 'temp_low' and latest.get('temp_f') is not None:
            value = latest['temp_f']
        elif ctype == 'wind_chill' and latest.get('temp_f') is not None and latest.get('wind_speed_mph') is not None:
            t, w = latest['temp_f'], latest['wind_speed_mph']
            if t <= 50 and w > 3:
                value = 35.74 + 0.6215*t - 35.75*(w**0.16) + 0.4275*t*(w**0.16)
            else:
                value = t
        elif ctype == 'heat_index' and latest.get('temp_f') is not None and latest.get('humidity') is not None:
            t, h = latest['temp_f'], latest['humidity']
            if t >= 80:
                value = -42.379 + 2.04901523*t + 10.14333127*h - 0.22475541*t*h - 0.00683783*t**2 - 0.05481717*h**2 + 0.00122874*t**2*h + 0.00085282*t*h**2 - 0.00000199*t**2*h**2
            else:
                value = t

        if value is None:
            continue

        threshold = rule['threshold']
        comp = rule['comparison']
        matched = False
        if comp == 'lt' and value < threshold: matched = True
        elif comp == 'gt' and value > threshold: matched = True
        elif comp == 'lte' and value <= threshold: matched = True
        elif comp == 'gte' and value >= threshold: matched = True

        if matched:
            action_data = _safe_json_object(rule['action_data'], {})

            atype = rule['action_type']

            # Create alert
            if atype in ('alert', 'both'):
                sev = action_data.get('severity', 'warning')
                title = action_data.get('title', f'Weather rule triggered: {rule["name"]}')
                msg = action_data.get('message', f'{ctype} condition met: value={round(value, 1)}, threshold={threshold}')
                db.execute(
                    'INSERT INTO alerts (alert_type, severity, title, message) VALUES (?, ?, ?, ?)',
                    ('weather_action', sev, title, msg))

            # Create task
            if atype in ('task', 'both'):
                task_name = action_data.get('task_name', f'Weather action: {rule["name"]}')
                task_cat = action_data.get('task_category', 'weather')
                due = now.strftime('%Y-%m-%d %H:%M:%S')
                db.execute(
                    'INSERT INTO scheduled_tasks (name, category, next_due, notes) VALUES (?, ?, ?, ?)',
                    (task_name, task_cat, due, f'Auto-created by weather rule: {rule["name"]}'))

            # Update last triggered
            db.execute('UPDATE weather_action_rules SET last_triggered = ? WHERE id = ?',
                       (now.strftime('%Y-%m-%d %H:%M:%S'), rule['id']))

            triggered.append({'rule_id': rule['id'], 'name': rule['name'], 'value': round(value, 1), 'action_type': atype})

    if triggered:
        db.commit()
    return triggered


@weather_bp.route('/api/weather/action-rules')
def api_weather_action_rules():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM weather_action_rules ORDER BY created_at DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d['action_data'] = _safe_json_object(d.get('action_data'), {})
            result.append(d)
        return jsonify(result)
@weather_bp.route('/api/weather/action-rules', methods=['POST'])
def api_weather_action_rules_create():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    condition_type = data.get('condition_type', 'pressure_drop')
    valid_conditions = ['pressure_drop', 'pressure_rise', 'temp_high', 'temp_low', 'wind_chill', 'heat_index']
    if condition_type not in valid_conditions:
        return jsonify({'error': f'Invalid condition_type. Must be one of: {", ".join(valid_conditions)}'}), 400
    try:
        threshold = float(data.get('threshold', 0))
    except (ValueError, TypeError):
        return jsonify({'error': 'threshold must be a number'}), 400
    comparison = data.get('comparison', 'lt')
    if comparison not in ('lt', 'gt', 'lte', 'gte'):
        return jsonify({'error': 'comparison must be lt, gt, lte, or gte'}), 400
    action_type = data.get('action_type', 'alert')
    if action_type not in ('alert', 'task', 'both'):
        return jsonify({'error': 'action_type must be alert, task, or both'}), 400
    action_data = _safe_json_object(data.get('action_data'), {})
    try:
        cooldown = int(data.get('cooldown_minutes', 60))
    except (ValueError, TypeError):
        cooldown = 60

    with db_session() as db:
        cur = db.execute(
            'INSERT INTO weather_action_rules (name, condition_type, threshold, comparison, action_type, action_data, cooldown_minutes) VALUES (?,?,?,?,?,?,?)',
            (name, condition_type, threshold, comparison, action_type, json.dumps(action_data), cooldown))
        db.commit()
        return jsonify({'id': cur.lastrowid, 'name': name}), 201
@weather_bp.route('/api/weather/action-rules/<int:rid>', methods=['DELETE'])
def api_weather_action_rules_delete(rid):
    with db_session() as db:
        db.execute('DELETE FROM weather_action_rules WHERE id = ?', (rid,))
        db.commit()
        return jsonify({'status': 'deleted'})
@weather_bp.route('/api/weather/action-rules/<int:rid>/toggle', methods=['POST'])
def api_weather_action_rules_toggle(rid):
    with db_session() as db:
        db.execute('UPDATE weather_action_rules SET enabled = CASE WHEN enabled = 1 THEN 0 ELSE 1 END WHERE id = ?', (rid,))
        db.commit()
        row = db.execute('SELECT enabled FROM weather_action_rules WHERE id = ?', (rid,)).fetchone()
        return jsonify({'enabled': row['enabled'] if row else 0})
@weather_bp.route('/api/weather/evaluate-rules', methods=['POST'])
def api_weather_evaluate_rules():
    """Evaluate all enabled weather action rules against current conditions."""
    with db_session() as db:
        triggered = _evaluate_weather_action_rules(db)
        return jsonify({'triggered': triggered})
# --- Storm Lifecycle Tracking ---

@weather_bp.route('/api/weather/storm-status', methods=['GET'])
def api_storm_status():
    with db_session() as db:
        # Check recent pressure readings for storm indicators
        readings = db.execute(
            'SELECT pressure_hpa, wind_speed_mph, created_at FROM weather_readings ORDER BY created_at DESC LIMIT 12'
        ).fetchall()
        if len(readings) < 2:
            return jsonify({'state': 'clear', 'confidence': 'low'})

        # Calculate pressure change rate (hPa per 3 hours)
        pressures = [(r['pressure_hpa'], r['created_at']) for r in readings if r['pressure_hpa']]
        if len(pressures) < 2:
            return jsonify({'state': 'clear', 'confidence': 'low'})

        recent_p = pressures[0][0]
        older_p = pressures[min(3, len(pressures) - 1)][0]
        pressure_change = recent_p - older_p

        max_wind = max((r['wind_speed_mph'] or 0) for r in readings)

        # State machine
        if pressure_change < -4 or max_wind > 50:
            state = 'active'
        elif pressure_change < -2 or max_wind > 30:
            state = 'warning'
        elif pressure_change < -1:
            state = 'watch'
        elif pressure_change > 1 and any(r['pressure_hpa'] and r['pressure_hpa'] < 1000 for r in readings[:3]):
            state = 'clearing'
        else:
            state = 'clear'

        # Check for active storm event
        active_storm = db.execute("SELECT * FROM storm_events WHERE ended_at IS NULL ORDER BY started_at DESC LIMIT 1").fetchone()

        # Auto-create/close storm events
        if state in ('warning', 'active') and not active_storm:
            db.execute("INSERT INTO storm_events (started_at, storm_type, total_pressure_drop, min_pressure) VALUES (datetime('now'), ?, ?, ?)",
                ('developing', abs(pressure_change), recent_p))
            db.commit()
        elif state == 'clear' and active_storm:
            db.execute("UPDATE storm_events SET ended_at = datetime('now'), peak_intensity = ? WHERE id = ?",
                (state, active_storm['id']))
            db.commit()

        return jsonify({
            'state': state,
            'pressure_change_3h': round(pressure_change, 2),
            'current_pressure': recent_p,
            'max_wind': max_wind,
            'active_storm': dict(active_storm) if active_storm else None
        })
@weather_bp.route('/api/weather/storms', methods=['GET'])
def api_storm_history():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM storm_events ORDER BY started_at DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
        return jsonify([dict(r) for r in rows])
@weather_bp.route('/api/weather/history')
def api_weather_history():
    """Get pressure history for graphing."""
    hours = request.args.get('hours', 48, type=int)
    with db_session() as db:
        rows = db.execute(
            "SELECT pressure_hpa, temp_f, humidity, wind_dir, wind_speed_mph, created_at FROM weather_readings WHERE created_at >= datetime('now', ? || ' hours') ORDER BY created_at ASC",
            (f'-{min(hours, 168)}',)
        ).fetchall()
        return jsonify([dict(r) for r in rows])
