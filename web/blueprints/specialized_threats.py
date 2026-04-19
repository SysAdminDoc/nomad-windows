"""Specialized threats — CBRN, epidemiology, avalanche, forensics, cyber threat intel (Tier 5).

5.1 Gaussian plume estimator (ALOHA-style)
5.2 Household epi line list + Rt tracker
5.3 Avalanche ATES + elevation-banded weather
5.4 Chain-of-custody evidence ledger
5.5 MISP-lite IOC ingest + ATT&CK mapping
"""

import hashlib
import json
import logging
import math
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
from db import db_session, log_activity

specialized_threats_bp = Blueprint('specialized_threats2', __name__)
_log = logging.getLogger('nomad.specialized_threats')


# ═══════════════════════════════════════════════════════════════════
# 5.1 — Gaussian Plume Estimator
# Simplified ALOHA-style atmospheric dispersion model.
# Estimates downwind concentration from a point-source release.
# ═══════════════════════════════════════════════════════════════════

# Pasquill-Gifford stability classes → sigma coefficients
# sigma_y = a * x^b, sigma_z = c * x^d (x in km)
_PG_COEFFS = {
    'A': {'a': 0.22, 'b': 0.894, 'c': 0.20, 'd': 1.000},  # Very unstable
    'B': {'a': 0.16, 'b': 0.894, 'c': 0.14, 'd': 0.920},  # Unstable
    'C': {'a': 0.11, 'b': 0.894, 'c': 0.08, 'd': 0.850},  # Slightly unstable
    'D': {'a': 0.08, 'b': 0.894, 'c': 0.06, 'd': 0.780},  # Neutral
    'E': {'a': 0.06, 'b': 0.894, 'c': 0.03, 'd': 0.730},  # Slightly stable
    'F': {'a': 0.04, 'b': 0.894, 'c': 0.016, 'd': 0.670}, # Stable
}


@specialized_threats_bp.route('/api/calculators/plume', methods=['POST'])
def api_plume_estimator():
    """Gaussian plume dispersion model.

    Input:
        source_rate_gs: Source emission rate (grams/second)
        wind_speed_ms: Wind speed (m/s)
        wind_dir_deg: Wind direction (degrees, meteorological — where wind comes FROM)
        stability_class: Pasquill-Gifford class A-F
        source_height_m: Effective stack/release height (meters)
        source_lat, source_lng: Release point coordinates
        distances_km: List of downwind distances to calculate (default [0.1, 0.5, 1, 2, 5, 10])

    Returns: Concentration at each distance + hazard corridor GeoJSON.
    """
    data = request.get_json() or {}

    try:
        Q = float(data.get('source_rate_gs', 100))  # g/s
        u = max(0.5, float(data.get('wind_speed_ms', 3)))  # m/s
        wind_dir = float(data.get('wind_dir_deg', 0))
        H = float(data.get('source_height_m', 0))  # effective height
        src_lat = float(data.get('source_lat', 0))
        src_lng = float(data.get('source_lng', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid numeric input'}), 400

    stability = data.get('stability_class', 'D').upper()
    if stability not in _PG_COEFFS:
        stability = 'D'

    distances = data.get('distances_km', [0.1, 0.5, 1, 2, 5, 10])
    if not isinstance(distances, list):
        distances = [0.1, 0.5, 1, 2, 5, 10]

    coeff = _PG_COEFFS[stability]
    results = []

    for x_km in distances:
        x_m = x_km * 1000
        if x_m <= 0:
            continue

        # Sigma calculations (meters)
        sigma_y = coeff['a'] * (x_km ** coeff['b']) * 1000  # convert to meters
        sigma_z = coeff['c'] * (x_km ** coeff['d']) * 1000

        # Centerline ground-level concentration (y=0, z=0)
        # C = Q / (2*pi*u*sigma_y*sigma_z) * exp(-H^2 / (2*sigma_z^2))
        if sigma_y > 0 and sigma_z > 0:
            concentration = (Q / (2 * math.pi * u * sigma_y * sigma_z)) * \
                            math.exp(-H**2 / (2 * sigma_z**2))
        else:
            concentration = 0

        # Convert g/m3 to mg/m3 and ppm (assuming air density ~1.2 kg/m3, MW ~29)
        conc_mg = concentration * 1000
        conc_ppm = conc_mg * 24.45 / 29  # approximate for generic gas

        results.append({
            'distance_km': x_km,
            'concentration_gm3': round(concentration, 6),
            'concentration_mgm3': round(conc_mg, 4),
            'concentration_ppm': round(conc_ppm, 4),
            'sigma_y_m': round(sigma_y, 1),
            'sigma_z_m': round(sigma_z, 1),
            'plume_width_m': round(4 * sigma_y, 1),  # ~95% of mass within 2*sigma
        })

    # Generate hazard corridor GeoJSON (downwind centerline + width)
    corridor = None
    if src_lat and src_lng and results:
        corridor = _plume_geojson(src_lat, src_lng, wind_dir, results)

    return jsonify({
        'source_rate_gs': Q,
        'wind_speed_ms': u,
        'wind_direction_deg': wind_dir,
        'stability_class': stability,
        'source_height_m': H,
        'concentrations': results,
        'corridor_geojson': corridor,
        'disclaimer': 'Simplified Gaussian model — NOT a substitute for ALOHA/CAMEO or professional HAZMAT assessment.',
    })


def _plume_geojson(lat, lng, wind_dir, results):
    """Generate a plume corridor polygon as GeoJSON."""
    # Wind direction: meteorological (where FROM) → bearing (where TO)
    bearing = (wind_dir + 180) % 360
    bearing_rad = math.radians(bearing)

    features = []
    for r in results:
        d_km = r['distance_km']
        width_km = r['plume_width_m'] / 1000

        # Point downwind at distance d_km
        dlat = d_km / 111.32 * math.cos(bearing_rad)
        dlng = d_km / (111.32 * math.cos(math.radians(lat))) * math.sin(bearing_rad)

        center_lat = lat + dlat
        center_lng = lng + dlng

        features.append({
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [round(center_lng, 6), round(center_lat, 6)],
            },
            'properties': {
                'distance_km': d_km,
                'concentration_ppm': r['concentration_ppm'],
                'plume_width_m': r['plume_width_m'],
                'radius_m': r['plume_width_m'] / 2,
            },
        })

    return {'type': 'FeatureCollection', 'features': features}


# ═══════════════════════════════════════════════════════════════════
# 5.2 — Household Epi Line List + Rt Tracker
# Track illness in a household/community. Estimate reproduction number.
# ═══════════════════════════════════════════════════════════════════

@specialized_threats_bp.route('/api/epi/cases')
def api_epi_cases():
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM epi_line_list ORDER BY onset_date DESC LIMIT 500'
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@specialized_threats_bp.route('/api/epi/cases', methods=['POST'])
def api_epi_case_create():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400

    with db_session() as db:
        cur = db.execute('''
            INSERT INTO epi_line_list
            (name, age, sex, onset_date, symptoms, diagnosis, outcome, isolation_start,
             isolation_end, exposure_source, household, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            name,
            data.get('age'),
            data.get('sex', ''),
            data.get('onset_date', datetime.now(timezone.utc).strftime('%Y-%m-%d')),
            data.get('symptoms', ''),
            data.get('diagnosis', ''),
            data.get('outcome', 'active'),
            data.get('isolation_start', ''),
            data.get('isolation_end', ''),
            data.get('exposure_source', ''),
            data.get('household', ''),
            data.get('notes', ''),
        ))
        db.commit()
        row = db.execute('SELECT * FROM epi_line_list WHERE id = ?', (cur.lastrowid,)).fetchone()

    log_activity('epi_case_logged', detail=f'{name}: {data.get("diagnosis", "unknown")}')
    return jsonify(dict(row)), 201


@specialized_threats_bp.route('/api/epi/cases/<int:case_id>', methods=['PUT'])
def api_epi_case_update(case_id):
    data = request.get_json() or {}
    allowed = ['name', 'age', 'sex', 'onset_date', 'symptoms', 'diagnosis', 'outcome',
               'isolation_start', 'isolation_end', 'exposure_source', 'household', 'notes']
    updates = []
    values = []
    for k in allowed:
        if k in data:
            updates.append(f'{k} = ?')
            values.append(data[k])
    if not updates:
        return jsonify({'error': 'No fields to update'}), 400

    values.append(case_id)
    with db_session() as db:
        r = db.execute(f"UPDATE epi_line_list SET {', '.join(updates)} WHERE id = ?", values)
        if r.rowcount == 0:
            return jsonify({'error': 'Not found'}), 404
        db.commit()
    return jsonify({'status': 'updated'})


@specialized_threats_bp.route('/api/epi/cases/<int:case_id>', methods=['DELETE'])
def api_epi_case_delete(case_id):
    with db_session() as db:
        r = db.execute('DELETE FROM epi_line_list WHERE id = ?', (case_id,))
        if r.rowcount == 0:
            return jsonify({'error': 'Not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


@specialized_threats_bp.route('/api/epi/rt')
def api_epi_rt():
    """Estimate reproduction number (Rt) from case onset dates.
    Uses simple ratio method: Rt = cases_this_period / cases_last_period.
    """
    window_days = max(1, min(30, int(request.args.get('window', 7))))

    with db_session() as db:
        recent = db.execute(
            "SELECT COUNT(*) as c FROM epi_line_list WHERE onset_date >= date('now', ?)",
            (f'-{window_days} days',)
        ).fetchone()['c']

        previous = db.execute(
            "SELECT COUNT(*) as c FROM epi_line_list WHERE onset_date >= date('now', ?) AND onset_date < date('now', ?)",
            (f'-{window_days * 2} days', f'-{window_days} days')
        ).fetchone()['c']

        total = db.execute('SELECT COUNT(*) as c FROM epi_line_list').fetchone()['c']
        active = db.execute(
            "SELECT COUNT(*) as c FROM epi_line_list WHERE outcome = 'active'"
        ).fetchone()['c']

    rt = recent / previous if previous > 0 else (1.0 if recent == 0 else float('inf'))
    trend = 'growing' if rt > 1.1 else 'declining' if rt < 0.9 else 'stable'

    return jsonify({
        'rt': round(rt, 2) if rt != float('inf') else None,
        'trend': trend,
        'window_days': window_days,
        'cases_current_period': recent,
        'cases_previous_period': previous,
        'total_cases': total,
        'active_cases': active,
    })


@specialized_threats_bp.route('/api/epi/curve')
def api_epi_curve():
    """Epidemic curve — cases per day."""
    with db_session() as db:
        rows = db.execute(
            "SELECT onset_date, COUNT(*) as cases FROM epi_line_list "
            "WHERE onset_date != '' GROUP BY onset_date ORDER BY onset_date"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# ═══════════════════════════════════════════════════════════════════
# 5.3 — Avalanche ATES + Elevation-Banded Weather
# Avalanche Terrain Exposure Scale rating for routes.
# ═══════════════════════════════════════════════════════════════════

ATES_CLASSES = {
    'simple': {
        'class': 1,
        'description': 'Exposure to low-angle or forested terrain. No exposure to avalanche paths.',
        'slope_range': '0-25°',
        'travel_advice': 'Generally safe for all winter travelers with basic avalanche awareness.',
    },
    'challenging': {
        'class': 2,
        'description': 'Exposure to well-defined avalanche paths, steep rollovers, or terrain traps.',
        'slope_range': '25-35°',
        'travel_advice': 'Suitable for trained winter backcountry travelers with rescue gear.',
    },
    'complex': {
        'class': 3,
        'description': 'Exposure to multiple overlapping avalanche paths or large expanses of steep terrain.',
        'slope_range': '35-45°+',
        'travel_advice': 'Expert-only terrain. Full rescue gear, formal avalanche training required.',
    },
}


@specialized_threats_bp.route('/api/calculators/avalanche-ates', methods=['POST'])
def api_avalanche_ates():
    """Rate a route using the Avalanche Terrain Exposure Scale.

    Input: slope_angle, terrain_traps, forest_cover_pct, aspect, elevation_m
    Returns: ATES class + recommendations.
    """
    data = request.get_json() or {}

    try:
        slope = float(data.get('slope_angle', 0))
        traps = bool(data.get('terrain_traps', False))
        forest = float(data.get('forest_cover_pct', 0))
        elevation = float(data.get('elevation_m', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid input'}), 400

    aspect = data.get('aspect', '').upper()

    # Classify
    if slope >= 35 or (slope >= 30 and traps):
        ates_key = 'complex'
    elif slope >= 25 or traps or forest < 30:
        ates_key = 'challenging'
    else:
        ates_key = 'simple'

    ates = ATES_CLASSES[ates_key]

    # Aspect risk (N-facing holds cold snow longer)
    aspect_risk = 'low'
    if aspect in ('N', 'NE', 'NW'):
        aspect_risk = 'high'
        ates_note = 'North-facing slopes hold cold, faceted snow longer — persistent slab risk'
    elif aspect in ('E', 'SE'):
        aspect_risk = 'medium'
        ates_note = 'East-facing slopes load from prevailing westerly winds'
    else:
        ates_note = 'South/west aspects consolidate faster but can produce wet avalanches in spring'

    # Elevation band risk
    if elevation > 2500:
        elev_risk = 'alpine'
        elev_note = 'Above treeline — wind-loaded, exposed, minimal anchoring'
    elif elevation > 1800:
        elev_risk = 'treeline'
        elev_note = 'Near treeline — transitional zone, wind effects variable'
    else:
        elev_risk = 'below_treeline'
        elev_note = 'Below treeline — generally lower risk but terrain traps still dangerous'

    return jsonify({
        'ates_class': ates['class'],
        'ates_name': ates_key,
        'description': ates['description'],
        'slope_range': ates['slope_range'],
        'travel_advice': ates['travel_advice'],
        'input': {
            'slope_angle': slope,
            'terrain_traps': traps,
            'forest_cover_pct': forest,
            'aspect': aspect,
            'elevation_m': elevation,
        },
        'aspect_risk': aspect_risk,
        'aspect_note': ates_note,
        'elevation_band': elev_risk,
        'elevation_note': elev_note,
        'essential_gear': ['Avalanche transceiver', 'Probe', 'Shovel', 'Airbag pack (recommended for Class 2-3)'],
    })


# ═══════════════════════════════════════════════════════════════════
# 5.4 — Chain-of-Custody Evidence Ledger
# Timestamped, hash-verified evidence chain for post-incident docs.
# ═══════════════════════════════════════════════════════════════════

@specialized_threats_bp.route('/api/evidence')
def api_evidence_list():
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM evidence_ledger ORDER BY logged_at DESC LIMIT 200'
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@specialized_threats_bp.route('/api/evidence', methods=['POST'])
def api_evidence_create():
    data = request.get_json() or {}
    desc = data.get('description', '').strip()
    if not desc:
        return jsonify({'error': 'description is required'}), 400

    now = datetime.now(timezone.utc).isoformat()

    # Create integrity hash: SHA-256 of description + timestamp + collector
    collector = data.get('collected_by', '').strip()
    hash_input = f'{desc}|{now}|{collector}'.encode('utf-8')
    integrity_hash = hashlib.sha256(hash_input).hexdigest()

    with db_session() as db:
        cur = db.execute('''
            INSERT INTO evidence_ledger
            (description, evidence_type, location, lat, lng, collected_by,
             chain_of_custody, integrity_hash, photo_ref, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        ''', (
            desc,
            data.get('evidence_type', 'physical'),
            data.get('location', ''),
            data.get('lat'),
            data.get('lng'),
            collector,
            json.dumps([{
                'action': 'collected',
                'by': collector,
                'timestamp': now,
                'notes': data.get('collection_notes', ''),
            }]),
            integrity_hash,
            data.get('photo_ref', ''),
            data.get('notes', ''),
        ))
        db.commit()
        row = db.execute('SELECT * FROM evidence_ledger WHERE id = ?', (cur.lastrowid,)).fetchone()

    log_activity('evidence_logged', detail=f'{data.get("evidence_type","physical")}: {desc[:50]}')
    return jsonify(dict(row)), 201


@specialized_threats_bp.route('/api/evidence/<int:eid>/transfer', methods=['POST'])
def api_evidence_transfer(eid):
    """Record a custody transfer — append to chain."""
    data = request.get_json() or {}
    transferred_to = data.get('transferred_to', '').strip()
    if not transferred_to:
        return jsonify({'error': 'transferred_to is required'}), 400

    now = datetime.now(timezone.utc).isoformat()

    with db_session() as db:
        row = db.execute('SELECT chain_of_custody FROM evidence_ledger WHERE id = ?', (eid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404

        try:
            chain = json.loads(row['chain_of_custody'] or '[]')
        except (json.JSONDecodeError, TypeError):
            chain = []

        chain.append({
            'action': 'transferred',
            'by': data.get('transferred_by', ''),
            'to': transferred_to,
            'timestamp': now,
            'notes': data.get('notes', ''),
        })

        db.execute(
            'UPDATE evidence_ledger SET chain_of_custody = ? WHERE id = ?',
            (json.dumps(chain), eid)
        )
        db.commit()

    log_activity('evidence_transferred', detail=f'Item #{eid} → {transferred_to}')
    return jsonify({'status': 'transferred', 'chain_length': len(chain)})


@specialized_threats_bp.route('/api/evidence/<int:eid>/verify')
def api_evidence_verify(eid):
    """Verify evidence integrity hash."""
    with db_session() as db:
        row = db.execute('SELECT * FROM evidence_ledger WHERE id = ?', (eid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404

    # Re-compute hash from original fields
    chain = json.loads(row['chain_of_custody'] or '[]')
    original = chain[0] if chain else {}
    original_ts = original.get('timestamp', row['logged_at'])
    hash_input = f'{row["description"]}|{original_ts}|{row["collected_by"]}'.encode('utf-8')
    computed = hashlib.sha256(hash_input).hexdigest()

    return jsonify({
        'verified': computed == row['integrity_hash'],
        'stored_hash': row['integrity_hash'],
        'computed_hash': computed,
        'chain_length': len(chain),
    })


@specialized_threats_bp.route('/api/evidence/<int:eid>', methods=['DELETE'])
def api_evidence_delete(eid):
    with db_session() as db:
        r = db.execute('DELETE FROM evidence_ledger WHERE id = ?', (eid,))
        if r.rowcount == 0:
            return jsonify({'error': 'Not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


# ═══════════════════════════════════════════════════════════════════
# 5.5 — IOC Tracker + ATT&CK Mapping
# Lightweight indicator of compromise tracking with MITRE mapping.
# ═══════════════════════════════════════════════════════════════════

@specialized_threats_bp.route('/api/ioc')
def api_ioc_list():
    ioc_type = request.args.get('type', '')
    with db_session() as db:
        if ioc_type:
            rows = db.execute(
                'SELECT * FROM ioc_tracker WHERE ioc_type = ? ORDER BY created_at DESC LIMIT 500',
                (ioc_type,)
            ).fetchall()
        else:
            rows = db.execute(
                'SELECT * FROM ioc_tracker ORDER BY created_at DESC LIMIT 500'
            ).fetchall()
    return jsonify([dict(r) for r in rows])


@specialized_threats_bp.route('/api/ioc', methods=['POST'])
def api_ioc_create():
    data = request.get_json() or {}
    value = data.get('value', '').strip()
    ioc_type = data.get('ioc_type', '').strip()

    if not value or not ioc_type:
        return jsonify({'error': 'value and ioc_type required'}), 400

    valid_types = {'ip', 'domain', 'url', 'hash_md5', 'hash_sha256', 'email', 'file_name', 'cve', 'other'}
    if ioc_type not in valid_types:
        return jsonify({'error': f'Invalid type. Valid: {", ".join(sorted(valid_types))}'}), 400

    with db_session() as db:
        cur = db.execute('''
            INSERT INTO ioc_tracker
            (value, ioc_type, source, confidence, tlp, attack_tactic, attack_technique,
             attack_id, description, first_seen, last_seen, status, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            value, ioc_type,
            data.get('source', ''),
            data.get('confidence', 'medium'),
            data.get('tlp', 'amber'),
            data.get('attack_tactic', ''),
            data.get('attack_technique', ''),
            data.get('attack_id', ''),
            data.get('description', ''),
            data.get('first_seen', ''),
            data.get('last_seen', ''),
            data.get('status', 'active'),
            data.get('notes', ''),
        ))
        db.commit()
        row = db.execute('SELECT * FROM ioc_tracker WHERE id = ?', (cur.lastrowid,)).fetchone()

    log_activity('ioc_added', detail=f'{ioc_type}: {value[:50]}')
    return jsonify(dict(row)), 201


@specialized_threats_bp.route('/api/ioc/<int:ioc_id>', methods=['DELETE'])
def api_ioc_delete(ioc_id):
    with db_session() as db:
        r = db.execute('DELETE FROM ioc_tracker WHERE id = ?', (ioc_id,))
        if r.rowcount == 0:
            return jsonify({'error': 'Not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


@specialized_threats_bp.route('/api/ioc/attack-matrix')
def api_ioc_attack_matrix():
    """Group IOCs by MITRE ATT&CK tactic for a heat-map view."""
    with db_session() as db:
        rows = db.execute(
            "SELECT attack_tactic, attack_technique, attack_id, COUNT(*) as count "
            "FROM ioc_tracker WHERE attack_tactic != '' "
            "GROUP BY attack_tactic, attack_technique ORDER BY count DESC"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@specialized_threats_bp.route('/api/ioc/summary')
def api_ioc_summary():
    with db_session() as db:
        total = db.execute('SELECT COUNT(*) as c FROM ioc_tracker').fetchone()['c']
        active = db.execute("SELECT COUNT(*) as c FROM ioc_tracker WHERE status = 'active'").fetchone()['c']
        by_type = db.execute(
            'SELECT ioc_type, COUNT(*) as count FROM ioc_tracker GROUP BY ioc_type ORDER BY count DESC'
        ).fetchall()
    return jsonify({
        'total': total,
        'active': active,
        'by_type': [dict(r) for r in by_type],
    })
