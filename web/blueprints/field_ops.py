"""Field operations — SAR, overland, maritime, aviation tools (Tier 4).

4.1 ICS-205/205A comms plan auto-builder
4.3 Clue log + containment tracker
4.4 Overland tire pressure + payload advisor
4.7 Maritime tide predictor (harmonic)
4.8 Aviation density altitude + takeoff distance
"""

import json
import logging
import math
from datetime import datetime, timezone, timedelta

from flask import Blueprint, request, jsonify
from db import db_session, log_activity

field_ops_bp = Blueprint('field_ops', __name__)
_log = logging.getLogger('nomad.field_ops')


# ═══════════════════════════════════════════════════════════════════
# 4.1 — ICS-205 Comms Plan Auto-Builder
# Generate ICS comms plans from radio equipment + frequencies.
# ═══════════════════════════════════════════════════════════════════

@field_ops_bp.route('/api/ics/comms-plan', methods=['POST'])
def api_ics_comms_plan():
    """Auto-generate an ICS-205 Communications Plan from existing data.

    Pulls radio equipment, frequencies, net schedules, and contacts
    to populate a complete ICS-205 form.
    """
    data = request.get_json() or {}
    incident_name = data.get('incident_name', 'Operations')
    op_period = data.get('operational_period', '')

    if not op_period:
        now = datetime.now(timezone.utc)
        op_period = f"{now.strftime('%Y-%m-%d %H%M')}Z — {(now + timedelta(hours=12)).strftime('%Y-%m-%d %H%M')}Z"

    with db_session() as db:
        # Radio equipment
        radios = db.execute(
            'SELECT * FROM radio_equipment ORDER BY name'
        ).fetchall()

        # Frequencies (prioritized by importance)
        freqs = db.execute(
            'SELECT * FROM freq_database WHERE importance >= 7 ORDER BY importance DESC, freq_mhz LIMIT 30'
        ).fetchall()

        # Net schedules
        nets = db.execute('SELECT * FROM net_schedules ORDER BY start_time').fetchall()

        # Contacts with comms roles
        contacts = db.execute(
            "SELECT name, callsign, role, radio_callsign FROM contacts "
            "WHERE callsign != '' OR role IN ('comms', 'communications', 'radio', 'net_control') "
            "ORDER BY name"
        ).fetchall()

    # Build channel assignments
    channels = []
    for i, f in enumerate(freqs):
        channels.append({
            'channel': i + 1,
            'function': f['name'] or f['service'],
            'frequency': f'{f["freq_mhz"]:.4f} MHz',
            'mode': f.get('mode', 'FM') or 'FM',
            'service': f['service'],
            'remarks': f.get('notes', '') or '',
        })

    # Build equipment inventory
    equipment = []
    for r in radios:
        equipment.append({
            'type': r.get('radio_type', 'HT'),
            'name': r['name'],
            'model': r.get('model', ''),
            'serial': r.get('serial_number', ''),
            'assigned_to': r.get('assigned_to', ''),
        })

    # Build net schedule
    net_list = []
    for n in nets:
        net_list.append({
            'name': n['name'],
            'frequency_mhz': n.get('frequency_mhz', 0),
            'day': n.get('day_of_week', ''),
            'start_time': n['start_time'],
            'net_control': n.get('net_control', ''),
        })

    # Build operator roster
    operators = []
    for c in contacts:
        operators.append({
            'name': c['name'],
            'callsign': c['callsign'] or '',
            'role': c['role'] or '',
        })

    plan = {
        'form': 'ICS-205',
        'incident_name': incident_name,
        'operational_period': op_period,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'channels': channels,
        'equipment': equipment,
        'net_schedules': net_list,
        'operators': operators,
        'special_instructions': data.get('special_instructions', ''),
        'prepared_by': data.get('prepared_by', ''),
    }

    log_activity('ics_205_generated', detail=f'{incident_name}: {len(channels)} channels')
    return jsonify(plan)


@field_ops_bp.route('/api/ics/comms-plan/print')
def api_ics_comms_plan_print():
    """Generate printable HTML ICS-205."""
    # Re-use the JSON endpoint internally
    with field_ops_bp.ensure_sync(api_ics_comms_plan)() if hasattr(field_ops_bp, 'ensure_sync') else None or True:
        pass

    # Build from stored data directly for the print route
    with db_session() as db:
        freqs = db.execute(
            'SELECT * FROM freq_database WHERE importance >= 7 ORDER BY importance DESC, freq_mhz LIMIT 30'
        ).fetchall()

    incident = request.args.get('incident', 'Operations')
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>ICS-205 — {incident}</title>
<style>
body {{ font-family: 'Courier New', monospace; font-size: 11px; margin: 20px; }}
h1 {{ font-size: 16px; text-align: center; border-bottom: 2px solid #000; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
th, td {{ border: 1px solid #000; padding: 4px 6px; text-align: left; font-size: 10px; }}
th {{ background: #ddd; font-weight: bold; }}
.header {{ display: flex; justify-content: space-between; }}
@media print {{ body {{ margin: 0.5in; }} }}
</style></head><body>
<h1>ICS 205 — INCIDENT RADIO COMMUNICATIONS PLAN</h1>
<div class="header">
<p><b>Incident Name:</b> {incident}</p>
<p><b>Date/Time:</b> {datetime.now(timezone.utc).strftime('%d %b %Y %H%MZ')}</p>
</div>
<table>
<tr><th>Ch</th><th>Function</th><th>Frequency</th><th>Mode</th><th>Service</th><th>Remarks</th></tr>"""

    for i, f in enumerate(freqs):
        html += f"<tr><td>{i+1}</td><td>{f['name'] or f['service']}</td>"
        html += f"<td>{f['freq_mhz']:.4f}</td><td>{f.get('mode','FM') or 'FM'}</td>"
        html += f"<td>{f['service']}</td><td>{f.get('notes','') or ''}</td></tr>"

    html += """</table>
<p style="margin-top: 30px;"><b>Prepared by:</b> _________________ <b>Date/Time:</b> _________________</p>
</body></html>"""

    return html, 200, {'Content-Type': 'text/html'}


# ═══════════════════════════════════════════════════════════════════
# 4.3 — SAR Clue Log + Containment Tracker
# ═══════════════════════════════════════════════════════════════════

@field_ops_bp.route('/api/sar/clues')
def api_sar_clues():
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM sar_clue_log ORDER BY found_at DESC LIMIT 200'
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@field_ops_bp.route('/api/sar/clues', methods=['POST'])
def api_sar_clue_create():
    data = request.get_json() or {}
    desc = data.get('description', '').strip()
    if not desc:
        return jsonify({'error': 'description is required'}), 400

    with db_session() as db:
        cur = db.execute('''
            INSERT INTO sar_clue_log
            (description, clue_type, lat, lng, elevation_ft, found_by, sector, significance, photo_ref, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        ''', (
            desc,
            data.get('clue_type', 'physical'),
            data.get('lat'),
            data.get('lng'),
            data.get('elevation_ft'),
            data.get('found_by', ''),
            data.get('sector', ''),
            data.get('significance', 'medium'),
            data.get('photo_ref', ''),
            data.get('notes', ''),
        ))
        db.commit()
        row = db.execute('SELECT * FROM sar_clue_log WHERE id = ?', (cur.lastrowid,)).fetchone()

    log_activity('sar_clue_logged', detail=f'{data.get("clue_type","physical")}: {desc[:50]}')
    return jsonify(dict(row)), 201


@field_ops_bp.route('/api/sar/clues/<int:clue_id>', methods=['DELETE'])
def api_sar_clue_delete(clue_id):
    with db_session() as db:
        r = db.execute('DELETE FROM sar_clue_log WHERE id = ?', (clue_id,))
        if r.rowcount == 0:
            return jsonify({'error': 'Not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


@field_ops_bp.route('/api/sar/clues/geojson')
def api_sar_clues_geojson():
    """Export clue log as GeoJSON for map overlay."""
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM sar_clue_log WHERE lat IS NOT NULL AND lng IS NOT NULL ORDER BY found_at DESC'
        ).fetchall()

    features = []
    for r in rows:
        features.append({
            'type': 'Feature',
            'geometry': {'type': 'Point', 'coordinates': [r['lng'], r['lat']]},
            'properties': {
                'id': r['id'],
                'description': r['description'],
                'type': r['clue_type'],
                'significance': r['significance'],
                'found_by': r['found_by'],
                'sector': r['sector'],
                'found_at': r['found_at'],
            },
        })

    return jsonify({'type': 'FeatureCollection', 'features': features})


@field_ops_bp.route('/api/sar/containment')
def api_sar_containment():
    """Get containment status — sectors with search coverage."""
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM sar_containment ORDER BY sector'
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@field_ops_bp.route('/api/sar/containment', methods=['POST'])
def api_sar_containment_update():
    data = request.get_json() or {}
    sector = data.get('sector', '').strip()
    if not sector:
        return jsonify({'error': 'sector is required'}), 400

    with db_session() as db:
        db.execute('''
            INSERT OR REPLACE INTO sar_containment
            (sector, status, pod, searchers, search_type, started_at, completed_at, notes)
            VALUES (?,?,?,?,?,?,?,?)
        ''', (
            sector,
            data.get('status', 'uncleared'),
            data.get('pod', 0),
            data.get('searchers', 0),
            data.get('search_type', 'hasty'),
            data.get('started_at', ''),
            data.get('completed_at', ''),
            data.get('notes', ''),
        ))
        db.commit()

    return jsonify({'status': 'updated', 'sector': sector})


# ═══════════════════════════════════════════════════════════════════
# 4.4 — Overland Tire Pressure + Payload Advisor
# ═══════════════════════════════════════════════════════════════════

@field_ops_bp.route('/api/calculators/tire-pressure', methods=['POST'])
def api_tire_pressure():
    """Calculate recommended tire pressure for terrain type.

    Input: tire_size, vehicle_weight_lb, terrain, load_pct
    Returns: recommended PSI front/rear + explanation.
    """
    data = request.get_json() or {}

    try:
        base_psi = float(data.get('base_psi', 35))
        vehicle_weight_lb = float(data.get('vehicle_weight_lb', 4500))
        load_pct = min(1.5, max(0.5, float(data.get('load_pct', 1.0))))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid input'}), 400

    terrain = data.get('terrain', 'highway')

    # Terrain adjustment factors
    terrain_factors = {
        'highway':    {'factor': 1.00, 'notes': 'Manufacturer spec — optimal fuel economy and tire life'},
        'gravel':     {'factor': 0.90, 'notes': 'Slight reduction for better grip on loose surface'},
        'dirt':       {'factor': 0.85, 'notes': 'Lower pressure for larger contact patch'},
        'mud':        {'factor': 0.70, 'notes': 'Significant reduction — wider footprint prevents sinking'},
        'sand':       {'factor': 0.50, 'notes': 'Half pressure — maximum flotation on soft sand'},
        'rock':       {'factor': 0.75, 'notes': 'Lower for conforming to rocks, but not too low (pinch flats)'},
        'snow':       {'factor': 0.80, 'notes': 'Moderate reduction for better snow traction'},
        'ice':        {'factor': 0.95, 'notes': 'Near highway — tire flex helps minimal on ice'},
    }

    t = terrain_factors.get(terrain, terrain_factors['highway'])
    adjusted_psi = base_psi * t['factor'] * load_pct

    # Weight distribution (approximate 55/45 front/rear for most trucks)
    front_psi = round(adjusted_psi * 1.05, 1)
    rear_psi = round(adjusted_psi * 0.95, 1)

    # Payload capacity (simplified — GVWR minus curb weight)
    gvwr = float(data.get('gvwr_lb', vehicle_weight_lb * 1.3))
    payload_capacity = gvwr - vehicle_weight_lb
    current_payload = vehicle_weight_lb * (load_pct - 1.0) if load_pct > 1.0 else 0
    payload_remaining = payload_capacity - current_payload

    return jsonify({
        'terrain': terrain,
        'terrain_notes': t['notes'],
        'base_psi': base_psi,
        'load_factor': load_pct,
        'recommended_front_psi': front_psi,
        'recommended_rear_psi': rear_psi,
        'min_safe_psi': round(base_psi * 0.4, 1),
        'payload_capacity_lb': round(payload_capacity),
        'current_payload_lb': round(current_payload),
        'payload_remaining_lb': round(payload_remaining),
        'overloaded': payload_remaining < 0,
        'terrains_available': list(terrain_factors.keys()),
    })


# ═══════════════════════════════════════════════════════════════════
# 4.7 — Maritime: Tide Predictor (Harmonic)
# Simple tide estimation from lunar position.
# ═══════════════════════════════════════════════════════════════════

@field_ops_bp.route('/api/calculators/tides', methods=['POST'])
def api_tide_predictor():
    """Estimate tide times from lunar position.

    Input: lat, lng, date (optional)
    Returns: Approximate high/low tide times for the day.

    Uses simplified lunar tide model — NOT for navigation.
    For actual navigation, use official NOAA tide tables.
    """
    data = request.get_json() or {}

    try:
        lat = float(data.get('lat', 0))
        lng = float(data.get('lng', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'lat and lng required'}), 400

    date_str = data.get('date', '')
    if date_str:
        try:
            target = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        except ValueError:
            target = datetime.now(timezone.utc)
    else:
        target = datetime.now(timezone.utc)

    # Simplified lunar tide: period ~12h 25m
    # Moon transit time approximation
    LUNAR_DAY_HOURS = 24.8417  # lunar day in solar hours
    HALF_LUNAR = LUNAR_DAY_HOURS / 2

    # Days since J2000.0 epoch
    j2000 = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    days_since = (target - j2000).total_seconds() / 86400

    # Approximate moon hour angle (simplified)
    moon_phase_days = days_since % 29.53059  # synodic month
    moon_transit_hour = (moon_phase_days / 29.53059) * LUNAR_DAY_HOURS

    # Longitude correction (4 minutes per degree)
    lng_correction = lng / 15.0  # hours

    # High tide ~0h and ~12.42h after moon transit
    # Low tide ~6.21h and ~18.63h after moon transit
    base_hour = (moon_transit_hour + lng_correction) % 24

    tides = []
    for offset, tide_type in [(0, 'high'), (HALF_LUNAR / 2, 'low'),
                               (HALF_LUNAR, 'high'), (HALF_LUNAR * 1.5, 'low')]:
        h = (base_hour + offset) % 24
        hour = int(h)
        minute = int((h - hour) * 60)
        tides.append({
            'type': tide_type,
            'time_utc': f'{hour:02d}:{minute:02d}',
            'hour_decimal': round(h, 2),
        })

    tides.sort(key=lambda t: t['hour_decimal'])

    # Spring/neap indicator
    phase_pct = moon_phase_days / 29.53059
    if phase_pct < 0.05 or abs(phase_pct - 0.5) < 0.05:
        tide_strength = 'spring'
        strength_note = 'New/full moon — expect larger tidal range'
    elif abs(phase_pct - 0.25) < 0.05 or abs(phase_pct - 0.75) < 0.05:
        tide_strength = 'neap'
        strength_note = 'Quarter moon — expect smaller tidal range'
    else:
        tide_strength = 'moderate'
        strength_note = 'Moderate tidal range'

    return jsonify({
        'date': target.strftime('%Y-%m-%d'),
        'lat': lat,
        'lng': lng,
        'tides': tides,
        'tide_strength': tide_strength,
        'strength_note': strength_note,
        'moon_phase_pct': round(phase_pct * 100, 1),
        'disclaimer': 'Approximate lunar model — NOT for navigation. Use official NOAA tide tables for safety.',
    })


# ═══════════════════════════════════════════════════════════════════
# 4.8 — Aviation: Density Altitude + Takeoff Distance
# ═══════════════════════════════════════════════════════════════════

@field_ops_bp.route('/api/calculators/density-altitude', methods=['POST'])
def api_density_altitude():
    """Calculate density altitude and estimated takeoff distance.

    Input:
        field_elevation_ft: Field elevation in feet MSL
        temperature_c: OAT in Celsius
        altimeter_inhg: Altimeter setting in inches Hg (default 29.92)
        runway_length_ft: Available runway (optional)
        weight_lb: Aircraft weight (optional, default 2400)

    Returns: Pressure altitude, density altitude, takeoff roll estimate.
    """
    data = request.get_json() or {}

    try:
        field_elev = float(data.get('field_elevation_ft', 0))
        temp_c = float(data.get('temperature_c', 15))
        altimeter = float(data.get('altimeter_inhg', 29.92))
        runway = float(data.get('runway_length_ft', 0))
        weight = float(data.get('weight_lb', 2400))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid input'}), 400

    # Pressure altitude: field elevation + (29.92 - altimeter) * 1000
    pressure_alt = field_elev + (29.92 - altimeter) * 1000

    # Standard temperature at pressure altitude: 15 - (pressure_alt * 2 / 1000)
    std_temp = 15 - (pressure_alt * 0.002)
    temp_deviation = temp_c - std_temp

    # Density altitude: pressure_alt + (120 * temp_deviation)
    density_alt = pressure_alt + (120 * temp_deviation)

    # Takeoff distance estimation (Koch chart approximation)
    # Base: 1000 ft at sea level, standard day, for a typical single-engine
    base_roll = float(data.get('base_takeoff_ft', 1000))

    # Density altitude factor: +12% per 1000 ft DA
    da_factor = 1.0 + (density_alt / 1000 * 0.12)

    # Weight factor (deviation from gross weight)
    gross_weight = float(data.get('gross_weight_lb', weight))
    weight_factor = (weight / gross_weight) ** 2 if gross_weight > 0 else 1.0

    estimated_roll = base_roll * da_factor * weight_factor

    # 50-ft obstacle clearance distance (roughly 1.5x ground roll)
    clearance_dist = estimated_roll * 1.5

    # Runway assessment
    runway_adequate = True
    runway_margin = 0
    if runway > 0:
        runway_margin = runway - clearance_dist
        runway_adequate = runway_margin > 0

    return jsonify({
        'field_elevation_ft': field_elev,
        'pressure_altitude_ft': round(pressure_alt),
        'density_altitude_ft': round(density_alt),
        'standard_temp_c': round(std_temp, 1),
        'temp_deviation_c': round(temp_deviation, 1),
        'oat_c': temp_c,
        'altimeter_inhg': altimeter,
        'estimated_ground_roll_ft': round(estimated_roll),
        'estimated_clearance_50ft_ft': round(clearance_dist),
        'weight_lb': weight,
        'da_factor': round(da_factor, 2),
        'runway_length_ft': runway,
        'runway_adequate': runway_adequate,
        'runway_margin_ft': round(runway_margin) if runway > 0 else None,
        'warnings': _da_warnings(density_alt, temp_deviation, runway_adequate),
    })


def _da_warnings(da, temp_dev, runway_ok):
    warnings = []
    if da > 8000:
        warnings.append('CRITICAL: Density altitude exceeds 8,000 ft — significant performance degradation')
    elif da > 5000:
        warnings.append('CAUTION: High density altitude — reduced climb and takeoff performance')
    if temp_dev > 15:
        warnings.append('Hot day — engine power output reduced')
    if not runway_ok:
        warnings.append('WARNING: Insufficient runway for estimated takeoff distance')
    return warnings
