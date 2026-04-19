"""Field tools — calculators and utilities for Tier 3 roadmap items.

3.1 Codeplug builder with per-radio zones
3.2 Propagation-aware HF scheduler
3.4 Rainwater catchment calculator
"""

import csv
import io
import json
import logging
import math
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, Response
from db import db_session, log_activity

field_tools_bp = Blueprint('field_tools', __name__)
_log = logging.getLogger('nomad.field_tools')


# ═══════════════════════════════════════════════════════════════════
# 3.1 — Codeplug Builder
# Build radio programming files with zones, channels, and scan lists.
# Exports CHIRP-compatible CSV with zone grouping.
# ═══════════════════════════════════════════════════════════════════

@field_tools_bp.route('/api/codeplug/radios')
def api_codeplug_radios():
    """List configured radios."""
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM codeplug_radios ORDER BY name'
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@field_tools_bp.route('/api/codeplug/radios', methods=['POST'])
def api_codeplug_radio_create():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400

    with db_session() as db:
        cur = db.execute('''
            INSERT INTO codeplug_radios (name, brand, model, max_channels, freq_range_mhz, notes)
            VALUES (?,?,?,?,?,?)
        ''', (
            name,
            data.get('brand', ''),
            data.get('model', ''),
            data.get('max_channels', 128),
            data.get('freq_range_mhz', ''),
            data.get('notes', ''),
        ))
        db.commit()
        row = db.execute('SELECT * FROM codeplug_radios WHERE id = ?', (cur.lastrowid,)).fetchone()

    log_activity('codeplug_radio_added', detail=name)
    return jsonify(dict(row)), 201


@field_tools_bp.route('/api/codeplug/radios/<int:radio_id>', methods=['DELETE'])
def api_codeplug_radio_delete(radio_id):
    with db_session() as db:
        r = db.execute('DELETE FROM codeplug_radios WHERE id = ?', (radio_id,))
        if r.rowcount == 0:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM codeplug_zones WHERE radio_id = ?', (radio_id,))
        db.execute('DELETE FROM codeplug_channels WHERE radio_id = ?', (radio_id,))
        db.commit()
    return jsonify({'status': 'deleted'})


@field_tools_bp.route('/api/codeplug/<int:radio_id>/zones')
def api_codeplug_zones(radio_id):
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM codeplug_zones WHERE radio_id = ? ORDER BY sort_order, name',
            (radio_id,)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@field_tools_bp.route('/api/codeplug/<int:radio_id>/zones', methods=['POST'])
def api_codeplug_zone_create(radio_id):
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400

    with db_session() as db:
        cur = db.execute('''
            INSERT INTO codeplug_zones (radio_id, name, sort_order)
            VALUES (?,?,?)
        ''', (radio_id, name, data.get('sort_order', 0)))
        db.commit()
        row = db.execute('SELECT * FROM codeplug_zones WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@field_tools_bp.route('/api/codeplug/zones/<int:zone_id>', methods=['DELETE'])
def api_codeplug_zone_delete(zone_id):
    with db_session() as db:
        r = db.execute('DELETE FROM codeplug_zones WHERE id = ?', (zone_id,))
        if r.rowcount == 0:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM codeplug_channels WHERE zone_id = ?', (zone_id,))
        db.commit()
    return jsonify({'status': 'deleted'})


@field_tools_bp.route('/api/codeplug/<int:radio_id>/channels')
def api_codeplug_channels(radio_id):
    zone_id = request.args.get('zone_id', '')
    with db_session() as db:
        if zone_id:
            rows = db.execute(
                'SELECT c.*, z.name as zone_name FROM codeplug_channels c '
                'LEFT JOIN codeplug_zones z ON c.zone_id = z.id '
                'WHERE c.radio_id = ? AND c.zone_id = ? ORDER BY c.channel_number',
                (radio_id, zone_id)
            ).fetchall()
        else:
            rows = db.execute(
                'SELECT c.*, z.name as zone_name FROM codeplug_channels c '
                'LEFT JOIN codeplug_zones z ON c.zone_id = z.id '
                'WHERE c.radio_id = ? ORDER BY z.sort_order, c.channel_number',
                (radio_id,)
            ).fetchall()
    return jsonify([dict(r) for r in rows])


@field_tools_bp.route('/api/codeplug/<int:radio_id>/channels', methods=['POST'])
def api_codeplug_channel_create(radio_id):
    data = request.get_json() or {}
    freq = data.get('frequency_mhz', 0)
    if not freq:
        return jsonify({'error': 'frequency_mhz is required'}), 400

    with db_session() as db:
        cur = db.execute('''
            INSERT INTO codeplug_channels
            (radio_id, zone_id, channel_number, name, frequency_mhz, offset_mhz,
             offset_dir, tone_mode, ctcss_tone, dcs_code, power, mode, bandwidth_khz, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            radio_id,
            data.get('zone_id'),
            data.get('channel_number', 1),
            data.get('name', ''),
            freq,
            data.get('offset_mhz', 0),
            data.get('offset_dir', ''),
            data.get('tone_mode', ''),
            data.get('ctcss_tone', ''),
            data.get('dcs_code', ''),
            data.get('power', 'High'),
            data.get('mode', 'FM'),
            data.get('bandwidth_khz', 25),
            data.get('notes', ''),
        ))
        db.commit()
        row = db.execute('SELECT * FROM codeplug_channels WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@field_tools_bp.route('/api/codeplug/channels/<int:ch_id>', methods=['DELETE'])
def api_codeplug_channel_delete(ch_id):
    with db_session() as db:
        r = db.execute('DELETE FROM codeplug_channels WHERE id = ?', (ch_id,))
        if r.rowcount == 0:
            return jsonify({'error': 'Not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


@field_tools_bp.route('/api/codeplug/<int:radio_id>/import-frequencies', methods=['POST'])
def api_codeplug_import_freqs(radio_id):
    """Import frequencies from the freq_database into a codeplug zone."""
    data = request.get_json() or {}
    zone_id = data.get('zone_id')
    service = data.get('service', '')  # filter by service type (FRS, GMRS, etc.)

    with db_session() as db:
        query = 'SELECT * FROM freq_database'
        params = []
        if service:
            query += ' WHERE service = ?'
            params.append(service)
        query += ' ORDER BY freq_mhz'

        freqs = db.execute(query, params).fetchall()
        count = 0
        for i, f in enumerate(freqs):
            db.execute('''
                INSERT INTO codeplug_channels
                (radio_id, zone_id, channel_number, name, frequency_mhz, offset_mhz,
                 tone_mode, ctcss_tone, power, mode, bandwidth_khz)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ''', (
                radio_id, zone_id, i + 1,
                f['name'] or f['service'],
                f['freq_mhz'],
                0, '', '', 'High',
                f.get('mode', 'FM') or 'FM',
                25,
            ))
            count += 1
        db.commit()

    log_activity('codeplug_import', detail=f'{count} frequencies imported')
    return jsonify({'status': 'imported', 'count': count})


@field_tools_bp.route('/api/codeplug/<int:radio_id>/export/chirp')
def api_codeplug_export_chirp(radio_id):
    """Export codeplug as CHIRP-compatible CSV."""
    with db_session() as db:
        radio = db.execute('SELECT * FROM codeplug_radios WHERE id = ?', (radio_id,)).fetchone()
        if not radio:
            return jsonify({'error': 'Radio not found'}), 404

        channels = db.execute(
            'SELECT c.*, z.name as zone_name FROM codeplug_channels c '
            'LEFT JOIN codeplug_zones z ON c.zone_id = z.id '
            'WHERE c.radio_id = ? ORDER BY z.sort_order, c.channel_number',
            (radio_id,)
        ).fetchall()

    cols = ['Location', 'Name', 'Frequency', 'Duplex', 'Offset', 'Tone', 'rToneFreq',
            'cToneFreq', 'DtcsCode', 'DtcsPolarity', 'Mode', 'TStep', 'Skip',
            'Comment', 'URCALL', 'RPT1CALL', 'RPT2CALL', 'DVCODE']

    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()

    for i, ch in enumerate(channels):
        duplex = ''
        if ch['offset_dir'] == '+':
            duplex = '+'
        elif ch['offset_dir'] == '-':
            duplex = '-'

        w.writerow({
            'Location': i,
            'Name': (ch['name'] or '')[:8],
            'Frequency': f"{ch['frequency_mhz']:.6f}",
            'Duplex': duplex,
            'Offset': f"{abs(ch['offset_mhz'] or 0):.6f}",
            'Tone': ch['tone_mode'] or '',
            'rToneFreq': ch['ctcss_tone'] or '88.5',
            'cToneFreq': ch['ctcss_tone'] or '88.5',
            'DtcsCode': ch['dcs_code'] or '023',
            'DtcsPolarity': 'NN',
            'Mode': ch['mode'] or 'FM',
            'TStep': '5.00',
            'Skip': '',
            'Comment': ch.get('zone_name', ''),
            'URCALL': '', 'RPT1CALL': '', 'RPT2CALL': '', 'DVCODE': '',
        })

    log_activity('codeplug_exported', detail=f'{radio["name"]}: {len(channels)} channels')
    return Response(
        buf.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=codeplug_{radio["name"]}.csv'},
    )


# ═══════════════════════════════════════════════════════════════════
# 3.2 — Propagation-Aware HF Scheduler
# Recommend best HF frequencies for time-of-day + solar conditions.
# Integrates with net schedules to suggest optimal comm windows.
# ═══════════════════════════════════════════════════════════════════

# Band propagation characteristics by time of day (UTC hours)
_HF_BANDS = {
    '160m': {'freq': 1.9, 'day': False, 'night': True, 'range_mi': 500, 'noise': 'high'},
    '80m':  {'freq': 3.5, 'day': False, 'night': True, 'range_mi': 1000, 'noise': 'medium'},
    '60m':  {'freq': 5.3, 'day': True,  'night': True, 'range_mi': 1500, 'noise': 'low'},
    '40m':  {'freq': 7.0, 'day': True,  'night': True, 'range_mi': 2000, 'noise': 'medium'},
    '30m':  {'freq': 10.1, 'day': True,  'night': False, 'range_mi': 3000, 'noise': 'low'},
    '20m':  {'freq': 14.0, 'day': True,  'night': False, 'range_mi': 5000, 'noise': 'low'},
    '17m':  {'freq': 18.1, 'day': True,  'night': False, 'range_mi': 5000, 'noise': 'low'},
    '15m':  {'freq': 21.0, 'day': True,  'night': False, 'range_mi': 5000, 'noise': 'low'},
    '12m':  {'freq': 24.9, 'day': True,  'night': False, 'range_mi': 5000, 'noise': 'low'},
    '10m':  {'freq': 28.0, 'day': True,  'night': False, 'range_mi': 5000, 'noise': 'low'},
}


@field_tools_bp.route('/api/propagation/schedule')
def api_propagation_schedule():
    """Generate a 24-hour propagation schedule for all HF bands.
    Factors: time of day, season, estimated solar flux."""
    now = datetime.now(timezone.utc)
    month = now.month

    # Season factor (solar activity correlation)
    # Equinoxes (Mar/Sep) = best propagation, solstices = worst
    season_map = {1: 0.7, 2: 0.8, 3: 1.0, 4: 0.9, 5: 0.8, 6: 0.6,
                  7: 0.6, 8: 0.7, 9: 1.0, 10: 0.9, 11: 0.8, 12: 0.7}
    season = season_map.get(month, 0.8)

    # Estimated solar flux (default moderate — could be fed from space weather API)
    sfi = float(request.args.get('sfi', 120))
    sfi_factor = min(2.0, max(0.3, sfi / 100))

    schedule = []
    for hour in range(24):
        hour_bands = []
        is_day = 6 <= hour <= 18  # Simplified — real impl would use lat/lng

        for band_name, band in _HF_BANDS.items():
            score = 0.0

            # Time of day match
            if is_day and band['day']:
                score += 0.5
            elif not is_day and band['night']:
                score += 0.5
            elif is_day and band['night'] and not band['day']:
                score += 0.1  # Marginal
            elif not is_day and band['day'] and not band['night']:
                score += 0.1

            # Higher bands benefit more from high solar flux
            if band['freq'] >= 14:
                score *= sfi_factor
            elif band['freq'] >= 7:
                score *= (0.5 + sfi_factor * 0.5)

            # Season adjustment
            score *= season

            # Noise penalty
            noise_penalty = {'high': 0.7, 'medium': 0.85, 'low': 1.0}
            score *= noise_penalty.get(band['noise'], 1.0)

            quality = 'excellent' if score >= 0.8 else 'good' if score >= 0.5 else 'fair' if score >= 0.3 else 'poor'

            hour_bands.append({
                'band': band_name,
                'freq_mhz': band['freq'],
                'score': round(score, 2),
                'quality': quality,
                'range_mi': band['range_mi'],
            })

        hour_bands.sort(key=lambda x: x['score'], reverse=True)
        schedule.append({
            'hour_utc': hour,
            'is_day': is_day,
            'bands': hour_bands,
            'best_band': hour_bands[0]['band'] if hour_bands else None,
        })

    return jsonify({
        'schedule': schedule,
        'season_factor': season,
        'sfi': sfi,
        'generated_at': now.isoformat(),
    })


@field_tools_bp.route('/api/propagation/recommend')
def api_propagation_recommend():
    """Recommend best bands for right now."""
    now = datetime.now(timezone.utc)
    hour = now.hour
    is_day = 6 <= hour <= 18
    sfi = float(request.args.get('sfi', 120))
    target_range_mi = int(request.args.get('range', 500))

    recommendations = []
    for band_name, band in _HF_BANDS.items():
        score = 0.0
        if is_day and band['day']:
            score = 0.7
        elif not is_day and band['night']:
            score = 0.7
        else:
            score = 0.15

        # Range match bonus
        if band['range_mi'] >= target_range_mi:
            score += 0.2
        else:
            score *= 0.5  # Band can't reach target

        # SFI bonus for higher bands
        if band['freq'] >= 14:
            score *= min(2.0, sfi / 100)

        recommendations.append({
            'band': band_name,
            'freq_mhz': band['freq'],
            'score': round(score, 2),
            'quality': 'excellent' if score >= 0.8 else 'good' if score >= 0.5 else 'fair' if score >= 0.3 else 'poor',
            'range_mi': band['range_mi'],
            'suitable': score >= 0.3,
        })

    recommendations.sort(key=lambda x: x['score'], reverse=True)

    # Cross-reference with net schedules
    net_windows = []
    try:
        with db_session() as db:
            nets = db.execute(
                "SELECT * FROM net_schedules WHERE day_of_week = ? OR day_of_week = 'daily' ORDER BY start_time",
                (now.strftime('%A').lower(),)
            ).fetchall()
            for n in nets:
                net_windows.append({
                    'name': n['name'],
                    'frequency_mhz': n.get('frequency_mhz', 0),
                    'start_time': n['start_time'],
                    'band': _freq_to_band(n.get('frequency_mhz', 0)),
                })
    except Exception:
        pass

    return jsonify({
        'recommendations': recommendations,
        'current_hour_utc': hour,
        'is_day': is_day,
        'target_range_mi': target_range_mi,
        'net_windows': net_windows,
    })


def _freq_to_band(freq_mhz):
    if not freq_mhz:
        return ''
    for name, band in _HF_BANDS.items():
        if abs(freq_mhz - band['freq']) < 2:
            return name
    return ''


# ═══════════════════════════════════════════════════════════════════
# 3.4 — Rainwater Catchment Calculator
# Roof area + local rainfall → estimated annual yield.
# Tank sizing, first-flush diverter sizing.
# ═══════════════════════════════════════════════════════════════════

@field_tools_bp.route('/api/calculators/rainwater', methods=['POST'])
def api_rainwater_calculator():
    """Calculate rainwater catchment potential.

    Input:
        roof_sqft: Collection area in square feet
        annual_rainfall_in: Annual rainfall in inches (default 40)
        efficiency: Collection efficiency 0-1 (default 0.8 for metal roof)
        daily_usage_gal: Daily water usage in gallons (default 50)
        people: Number of people (default 2)

    Returns: Annual yield, tank sizing, first-flush volume, months of supply.
    """
    data = request.get_json() or {}

    try:
        roof_sqft = float(data.get('roof_sqft', 0))
        annual_rain_in = float(data.get('annual_rainfall_in', 40))
        efficiency = min(1.0, max(0.1, float(data.get('efficiency', 0.8))))
        daily_usage = float(data.get('daily_usage_gal', 50))
        people = max(1, int(data.get('people', 2)))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid numeric input'}), 400

    if roof_sqft <= 0:
        return jsonify({'error': 'roof_sqft must be > 0'}), 400

    # 1 inch of rain on 1 sqft = 0.623 gallons
    GAL_PER_SQFT_INCH = 0.623

    annual_yield_gal = roof_sqft * annual_rain_in * GAL_PER_SQFT_INCH * efficiency
    monthly_yield_gal = annual_yield_gal / 12
    daily_yield_gal = annual_yield_gal / 365

    total_daily_usage = daily_usage * people
    annual_usage = total_daily_usage * 365

    surplus_deficit = annual_yield_gal - annual_usage
    days_of_supply = annual_yield_gal / total_daily_usage if total_daily_usage > 0 else 0

    # Tank sizing — store 1 month of yield as recommended minimum
    recommended_tank_gal = monthly_yield_gal * 1.5  # 1.5 months buffer
    # Common tank sizes
    tank_sizes = [55, 100, 250, 500, 1000, 1500, 2500, 5000, 10000]
    best_tank = min((t for t in tank_sizes if t >= recommended_tank_gal), default=tank_sizes[-1])

    # First-flush diverter: 1 gallon per 100 sqft of roof (clears debris/bird droppings)
    first_flush_gal = max(1, roof_sqft / 100)

    # Monthly breakdown (rough — uses US average monthly distribution)
    monthly_pct = [0.06, 0.06, 0.08, 0.09, 0.10, 0.10, 0.09, 0.09, 0.08, 0.08, 0.08, 0.09]
    monthly_breakdown = []
    for i, pct in enumerate(monthly_pct):
        month_yield = annual_yield_gal * pct
        month_usage = total_daily_usage * 30
        monthly_breakdown.append({
            'month': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][i],
            'yield_gal': round(month_yield, 1),
            'usage_gal': round(month_usage, 1),
            'surplus': round(month_yield - month_usage, 1),
        })

    # Roof material efficiency guide
    material_guide = {
        'metal': 0.90,
        'tile': 0.80,
        'asphalt_shingle': 0.75,
        'flat_rubber': 0.85,
        'green_roof': 0.30,
        'concrete': 0.80,
    }

    return jsonify({
        'input': {
            'roof_sqft': roof_sqft,
            'annual_rainfall_in': annual_rain_in,
            'efficiency': efficiency,
            'daily_usage_gal': daily_usage,
            'people': people,
        },
        'annual_yield_gal': round(annual_yield_gal, 1),
        'monthly_yield_gal': round(monthly_yield_gal, 1),
        'daily_yield_gal': round(daily_yield_gal, 1),
        'annual_usage_gal': round(annual_usage, 1),
        'surplus_deficit_gal': round(surplus_deficit, 1),
        'days_of_supply': round(days_of_supply, 1),
        'self_sufficient': surplus_deficit >= 0,
        'recommended_tank_gal': round(recommended_tank_gal, 1),
        'best_tank_size_gal': best_tank,
        'first_flush_gal': round(first_flush_gal, 1),
        'monthly_breakdown': monthly_breakdown,
        'material_efficiencies': material_guide,
    })
