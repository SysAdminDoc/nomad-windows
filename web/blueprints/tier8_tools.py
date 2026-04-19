"""Tier 8 deep domain tools — cherry-picked high-value calculators and references.

Groups built:
- Leadership & Doctrine (L1-L3)
- Transportation calculators (P1-P3)
- Outdoor cooking math (AL1-AL5)
- Financial preparedness (AT1, AT3-AT4)
- Navigation GPS-denied (AJ1, AJ4-AJ5)
- OPSEC (AE4 EXIF scrubber concept, AE5 gray-man)
"""

import json
import logging
import math
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
from db import db_session, log_activity

tier8_bp = Blueprint('tier8_tools', __name__)
_log = logging.getLogger('nomad.tier8')


# ═══════════════════════════════════════════════════════════════════
# L1 — OODA Loop Tracker
# ═══════════════════════════════════════════════════════════════════

@tier8_bp.route('/api/doctrine/ooda')
def api_ooda_list():
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM ooda_cycles ORDER BY created_at DESC LIMIT 50'
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@tier8_bp.route('/api/doctrine/ooda', methods=['POST'])
def api_ooda_create():
    data = request.get_json() or {}
    situation = data.get('situation', '').strip()
    if not situation:
        return jsonify({'error': 'situation required'}), 400

    with db_session() as db:
        cur = db.execute('''
            INSERT INTO ooda_cycles
            (situation, observe, orient, decide, act, outcome, cycle_time_min, notes)
            VALUES (?,?,?,?,?,?,?,?)
        ''', (
            situation,
            data.get('observe', ''),
            data.get('orient', ''),
            data.get('decide', ''),
            data.get('act', ''),
            data.get('outcome', ''),
            data.get('cycle_time_min', 0),
            data.get('notes', ''),
        ))
        db.commit()
        row = db.execute('SELECT * FROM ooda_cycles WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('ooda_cycle', detail=situation[:50])
    return jsonify(dict(row)), 201


@tier8_bp.route('/api/doctrine/ooda/<int:oid>', methods=['DELETE'])
def api_ooda_delete(oid):
    with db_session() as db:
        r = db.execute('DELETE FROM ooda_cycles WHERE id = ?', (oid,))
        if r.rowcount == 0:
            return jsonify({'error': 'Not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


# ═══════════════════════════════════════════════════════════════════
# L2 — AAR Template Engine (Army 4-question)
# ═══════════════════════════════════════════════════════════════════

@tier8_bp.route('/api/doctrine/aar')
def api_aar_list():
    with db_session() as db:
        rows = db.execute(
            'SELECT id, event_name, event_date, facilitator, status, created_at '
            'FROM aar_reports ORDER BY created_at DESC LIMIT 50'
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@tier8_bp.route('/api/doctrine/aar', methods=['POST'])
def api_aar_create():
    data = request.get_json() or {}
    event_name = data.get('event_name', '').strip()
    if not event_name:
        return jsonify({'error': 'event_name required'}), 400

    with db_session() as db:
        cur = db.execute('''
            INSERT INTO aar_reports
            (event_name, event_date, facilitator, participants,
             q1_plan, q2_happened, q3_why, q4_improve,
             sustains, improves, action_items, status, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            event_name,
            data.get('event_date', datetime.now(timezone.utc).strftime('%Y-%m-%d')),
            data.get('facilitator', ''),
            json.dumps(data.get('participants', [])),
            data.get('q1_plan', ''),        # What was planned?
            data.get('q2_happened', ''),     # What actually happened?
            data.get('q3_why', ''),          # Why was there a difference?
            data.get('q4_improve', ''),      # What can we do next time?
            json.dumps(data.get('sustains', [])),
            json.dumps(data.get('improves', [])),
            json.dumps(data.get('action_items', [])),
            data.get('status', 'draft'),
            data.get('notes', ''),
        ))
        db.commit()
        row = db.execute('SELECT * FROM aar_reports WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('aar_created', detail=event_name)
    return jsonify(dict(row)), 201


@tier8_bp.route('/api/doctrine/aar/<int:aid>')
def api_aar_detail(aid):
    with db_session() as db:
        row = db.execute('SELECT * FROM aar_reports WHERE id = ?', (aid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    result = dict(row)
    for f in ('participants', 'sustains', 'improves', 'action_items'):
        try:
            result[f] = json.loads(result.get(f, '[]'))
        except (json.JSONDecodeError, TypeError):
            result[f] = []
    return jsonify(result)


@tier8_bp.route('/api/doctrine/aar/<int:aid>', methods=['DELETE'])
def api_aar_delete(aid):
    with db_session() as db:
        r = db.execute('DELETE FROM aar_reports WHERE id = ?', (aid,))
        if r.rowcount == 0:
            return jsonify({'error': 'Not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


# ═══════════════════════════════════════════════════════════════════
# L3 — Cynefin Domain Classifier
# ═══════════════════════════════════════════════════════════════════

CYNEFIN_DOMAINS = {
    'clear': {
        'name': 'Clear (Simple)',
        'description': 'Cause and effect obvious. Best practices exist.',
        'approach': 'Sense → Categorize → Respond',
        'leadership': 'Delegate. Apply established procedures.',
        'examples': ['Standard resupply', 'Routine maintenance', 'Shift handover'],
        'danger': 'Complacency — treating novel situations as simple.',
    },
    'complicated': {
        'name': 'Complicated',
        'description': 'Cause and effect discoverable but requires expertise.',
        'approach': 'Sense → Analyze → Respond',
        'leadership': 'Consult experts. Good practice (not best practice).',
        'examples': ['Equipment failure diagnosis', 'Route planning with constraints', 'Medical triage'],
        'danger': 'Analysis paralysis — over-studying when action is needed.',
    },
    'complex': {
        'name': 'Complex',
        'description': 'Cause and effect only obvious in retrospect. Emergent patterns.',
        'approach': 'Probe → Sense → Respond',
        'leadership': 'Create safe-to-fail experiments. Amplify what works, dampen what doesn\'t.',
        'examples': ['Community morale collapse', 'Multi-group coordination', 'Resource scarcity adaptation'],
        'danger': 'Temptation to impose order — kills emergence.',
    },
    'chaotic': {
        'name': 'Chaotic',
        'description': 'No cause-effect relationship perceivable. Crisis.',
        'approach': 'Act → Sense → Respond',
        'leadership': 'Take decisive action NOW. Establish order. Communicate clearly.',
        'examples': ['Active shooter', 'Building collapse', 'Flash flood', 'CBRN incident'],
        'danger': 'Freezing — inaction kills in chaos. Any action > no action.',
    },
    'confused': {
        'name': 'Confused (Disorder)',
        'description': 'Don\'t know which domain applies. Most dangerous state.',
        'approach': 'Break situation into parts → classify each part separately',
        'leadership': 'Gather information. Resist applying a single framework to the whole situation.',
        'examples': ['Novel disaster type', 'Conflicting reports from multiple sources'],
        'danger': 'Defaulting to your comfort zone domain regardless of reality.',
    },
}


@tier8_bp.route('/api/doctrine/cynefin')
def api_cynefin_reference():
    return jsonify(CYNEFIN_DOMAINS)


@tier8_bp.route('/api/doctrine/cynefin/classify', methods=['POST'])
def api_cynefin_classify():
    """Guided Cynefin classification from situation indicators."""
    data = request.get_json() or {}

    # Simple scoring heuristic from indicators
    indicators = {
        'known_solution': bool(data.get('known_solution', False)),
        'expert_needed': bool(data.get('expert_needed', False)),
        'unpredictable': bool(data.get('unpredictable', False)),
        'time_critical': bool(data.get('time_critical', False)),
        'multiple_valid_approaches': bool(data.get('multiple_valid_approaches', False)),
        'never_seen_before': bool(data.get('never_seen_before', False)),
    }

    if indicators['time_critical'] and indicators['never_seen_before']:
        domain = 'chaotic'
    elif indicators['known_solution'] and not indicators['expert_needed']:
        domain = 'clear'
    elif indicators['expert_needed'] and not indicators['unpredictable']:
        domain = 'complicated'
    elif indicators['unpredictable'] or indicators['multiple_valid_approaches']:
        domain = 'complex'
    else:
        domain = 'confused'

    return jsonify({
        'domain': domain,
        'detail': CYNEFIN_DOMAINS[domain],
        'indicators': indicators,
    })


# ═══════════════════════════════════════════════════════════════════
# P1-P3 — Transportation Calculators
# ═══════════════════════════════════════════════════════════════════

@tier8_bp.route('/api/calculators/pack-animal', methods=['POST'])
def api_pack_animal():
    """Pack animal load calculator."""
    data = request.get_json() or {}
    animal = data.get('animal', 'horse')

    specs = {
        'horse':  {'max_load_lb': 200, 'daily_miles': 20, 'water_gal_day': 10, 'feed_lb_day': 20},
        'mule':   {'max_load_lb': 250, 'daily_miles': 20, 'water_gal_day': 8,  'feed_lb_day': 15},
        'donkey': {'max_load_lb': 100, 'daily_miles': 15, 'water_gal_day': 5,  'feed_lb_day': 10},
        'llama':  {'max_load_lb': 75,  'daily_miles': 12, 'water_gal_day': 2,  'feed_lb_day': 5},
        'goat':   {'max_load_lb': 30,  'daily_miles': 8,  'water_gal_day': 2,  'feed_lb_day': 3},
    }

    s = specs.get(animal, specs['horse'])
    try:
        load_lb = float(data.get('load_lb', 0))
        trip_days = max(1, int(data.get('trip_days', 1)))
        num_animals = max(1, int(data.get('num_animals', 1)))
        terrain = data.get('terrain', 'trail')
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid input'}), 400

    terrain_factor = {'trail': 1.0, 'road': 1.1, 'cross_country': 0.6, 'mountain': 0.4}.get(terrain, 1.0)

    per_animal = load_lb / num_animals if num_animals > 0 else load_lb
    overloaded = per_animal > s['max_load_lb']
    daily_range = s['daily_miles'] * terrain_factor
    total_water = s['water_gal_day'] * trip_days * num_animals
    total_feed = s['feed_lb_day'] * trip_days * num_animals

    return jsonify({
        'animal': animal,
        'num_animals': num_animals,
        'load_per_animal_lb': round(per_animal, 1),
        'max_load_lb': s['max_load_lb'],
        'overloaded': overloaded,
        'daily_range_miles': round(daily_range, 1),
        'trip_days': trip_days,
        'total_water_gal': round(total_water, 1),
        'total_feed_lb': round(total_feed, 1),
        'terrain': terrain,
        'animals_available': list(specs.keys()),
    })


@tier8_bp.route('/api/calculators/portage', methods=['POST'])
def api_portage():
    """Canoe/kayak portage planner."""
    data = request.get_json() or {}
    try:
        distance_mi = float(data.get('distance_mi', 0))
        boat_lb = float(data.get('boat_lb', 75))
        gear_lb = float(data.get('gear_lb', 50))
        people = max(1, int(data.get('people', 2)))
        carries = max(1, int(data.get('carries_per_person', 2)))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid input'}), 400

    total_lb = boat_lb + gear_lb
    per_carry_lb = total_lb / (people * carries) if (people * carries) > 0 else total_lb
    portage_walking_mi = distance_mi * carries * 2 - distance_mi  # back-and-forth
    portage_time_min = portage_walking_mi * 30  # ~30 min/mile loaded on rough terrain

    return jsonify({
        'portage_distance_mi': distance_mi,
        'total_weight_lb': round(total_lb, 1),
        'per_carry_lb': round(per_carry_lb, 1),
        'total_walking_mi': round(portage_walking_mi, 1),
        'estimated_time_min': round(portage_time_min),
        'carries_per_person': carries,
        'people': people,
        'tip': 'Cache gear at far end, return empty for boat. Heaviest items closest to body.',
    })


@tier8_bp.route('/api/calculators/ebike-range', methods=['POST'])
def api_ebike_range():
    """E-bike range calculator."""
    data = request.get_json() or {}
    try:
        battery_wh = float(data.get('battery_wh', 500))
        motor_w = float(data.get('motor_w', 500))
        rider_lb = float(data.get('rider_lb', 180))
        cargo_lb = float(data.get('cargo_lb', 0))
        terrain = data.get('terrain', 'flat')
        assist_level = data.get('assist_level', 'medium')
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid input'}), 400

    # Wh/mile estimates by terrain + assist
    base_rates = {'flat': 15, 'rolling': 22, 'hilly': 30, 'mountain': 45}
    assist_factors = {'eco': 0.6, 'low': 0.8, 'medium': 1.0, 'high': 1.3, 'turbo': 1.6}

    base = base_rates.get(terrain, 15)
    af = assist_factors.get(assist_level, 1.0)
    weight_factor = 1 + (rider_lb + cargo_lb - 180) * 0.002  # heavier = more consumption

    wh_per_mile = base * af * max(0.8, weight_factor)
    range_miles = battery_wh / wh_per_mile if wh_per_mile > 0 else 0
    runtime_hours = battery_wh / motor_w if motor_w > 0 else 0

    return jsonify({
        'battery_wh': battery_wh,
        'estimated_range_miles': round(range_miles, 1),
        'wh_per_mile': round(wh_per_mile, 1),
        'runtime_hours': round(runtime_hours, 2),
        'terrain': terrain,
        'assist_level': assist_level,
        'total_weight_lb': rider_lb + cargo_lb,
        'terrains': list(base_rates.keys()),
        'assist_levels': list(assist_factors.keys()),
    })


# ═══════════════════════════════════════════════════════════════════
# AL — Outdoor Cooking Calculators
# ═══════════════════════════════════════════════════════════════════

@tier8_bp.route('/api/calculators/dutch-oven', methods=['POST'])
def api_dutch_oven():
    """Dutch oven coal calculator — top/bottom split for baking."""
    data = request.get_json() or {}
    try:
        oven_diameter_in = int(data.get('diameter_in', 12))
        target_temp_f = int(data.get('target_temp_f', 350))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid input'}), 400

    # Rule of thumb: diameter × 2 = total briquettes for 325°F
    # Each briquette adds ~15°F. Top gets 2/3, bottom gets 1/3 for baking.
    base_coals = oven_diameter_in * 2
    temp_diff = target_temp_f - 325
    extra = round(temp_diff / 15)
    total = max(base_coals + extra, 6)

    top = round(total * 2 / 3)
    bottom = total - top

    return jsonify({
        'diameter_in': oven_diameter_in,
        'target_temp_f': target_temp_f,
        'total_coals': total,
        'top_coals': top,
        'bottom_coals': bottom,
        'pattern': f'Ring of {top} on lid, {bottom} underneath in ring',
        'notes': [
            'Rotate lid 90° and oven 90° opposite every 15 min for even heat',
            'Each coal removed drops ~15°F',
            'Wind increases heat loss — use windscreen',
            'Replenish coals every 45-60 min for long bakes',
        ],
    })


@tier8_bp.route('/api/calculators/altitude-boiling')
def api_altitude_boiling():
    """Altitude boiling point + canning safety reference."""
    try:
        elevation_ft = float(request.args.get('elevation', 0))
    except (TypeError, ValueError):
        elevation_ft = 0

    # Boiling point drops ~1.8°F per 1000 ft
    bp_f = 212 - (elevation_ft / 1000 * 1.8)
    bp_c = (bp_f - 32) * 5 / 9

    # Canning pressure adjustment: +1 PSI per 2000 ft above 1000 ft
    canning_psi_extra = max(0, math.ceil((elevation_ft - 1000) / 2000)) if elevation_ft > 1000 else 0

    # Cooking time adjustment
    time_factor = 1.0 + (elevation_ft / 5000 * 0.25)  # +25% per 5000 ft

    return jsonify({
        'elevation_ft': elevation_ft,
        'boiling_point_f': round(bp_f, 1),
        'boiling_point_c': round(bp_c, 1),
        'canning_psi_adjustment': canning_psi_extra,
        'canning_note': f'Add {canning_psi_extra} PSI to sea-level recipe' if canning_psi_extra > 0 else 'No adjustment needed below 1000 ft',
        'cooking_time_factor': round(time_factor, 2),
        'cooking_note': f'Increase cooking time by {round((time_factor - 1) * 100)}%' if time_factor > 1 else 'No adjustment needed',
        'water_bath_safe': elevation_ft < 1000,
        'water_bath_note': 'Water-bath canning unreliable above 1000 ft — use pressure canner for all low-acid foods',
    })


# ═══════════════════════════════════════════════════════════════════
# AT — Financial Preparedness Calculators
# ═══════════════════════════════════════════════════════════════════

@tier8_bp.route('/api/calculators/emergency-fund', methods=['POST'])
def api_emergency_fund():
    """Emergency fund tier calculator."""
    data = request.get_json() or {}
    try:
        monthly_expenses = float(data.get('monthly_expenses', 3000))
        current_savings = float(data.get('current_savings', 0))
        monthly_contribution = float(data.get('monthly_contribution', 500))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid input'}), 400

    tiers = [
        {'name': 'Starter',    'months': 1,  'amount': monthly_expenses * 1},
        {'name': 'Basic',      'months': 3,  'amount': monthly_expenses * 3},
        {'name': 'Standard',   'months': 6,  'amount': monthly_expenses * 6},
        {'name': 'Enhanced',   'months': 9,  'amount': monthly_expenses * 9},
        {'name': 'Full',       'months': 12, 'amount': monthly_expenses * 12},
        {'name': 'Extended',   'months': 24, 'amount': monthly_expenses * 24},
    ]

    current_tier = 'None'
    next_tier = tiers[0]
    for t in tiers:
        if current_savings >= t['amount']:
            current_tier = t['name']
            next_idx = tiers.index(t) + 1
            next_tier = tiers[next_idx] if next_idx < len(tiers) else None
        t['reached'] = current_savings >= t['amount']
        t['amount'] = round(t['amount'])

    months_to_next = 0
    if next_tier and monthly_contribution > 0:
        gap = next_tier['amount'] - current_savings
        months_to_next = max(0, math.ceil(gap / monthly_contribution))

    return jsonify({
        'monthly_expenses': monthly_expenses,
        'current_savings': current_savings,
        'current_tier': current_tier,
        'months_to_next_tier': months_to_next,
        'next_tier': next_tier['name'] if next_tier else 'MAX',
        'tiers': tiers,
    })


@tier8_bp.route('/api/calculators/debt-snowball', methods=['POST'])
def api_debt_snowball():
    """Debt elimination calculator (snowball method)."""
    data = request.get_json() or {}
    debts = data.get('debts', [])
    extra_payment = float(data.get('extra_monthly', 0))

    if not debts:
        return jsonify({'error': 'debts array required (each: {name, balance, rate_pct, min_payment})'}), 400

    # Sort by balance ascending (snowball) or by rate descending (avalanche)
    method = data.get('method', 'snowball')
    parsed = []
    for d in debts:
        try:
            parsed.append({
                'name': d.get('name', 'Debt'),
                'balance': float(d.get('balance', 0)),
                'rate': float(d.get('rate_pct', 0)) / 100 / 12,  # monthly rate
                'min_payment': float(d.get('min_payment', 0)),
            })
        except (TypeError, ValueError):
            continue

    if method == 'avalanche':
        parsed.sort(key=lambda x: x['rate'], reverse=True)
    else:
        parsed.sort(key=lambda x: x['balance'])

    # Simulate payoff
    total_paid = 0
    months = 0
    payoff_order = []

    active = [dict(d) for d in parsed]
    while any(d['balance'] > 0 for d in active) and months < 600:
        months += 1
        freed = extra_payment

        for d in active:
            if d['balance'] <= 0:
                continue
            interest = d['balance'] * d['rate']
            payment = d['min_payment'] + freed
            freed = 0

            if payment >= d['balance'] + interest:
                total_paid += d['balance'] + interest
                freed = payment - (d['balance'] + interest)
                d['balance'] = 0
                payoff_order.append({'name': d['name'], 'month': months})
            else:
                d['balance'] = d['balance'] + interest - payment
                total_paid += payment

    return jsonify({
        'method': method,
        'total_months': months,
        'total_years': round(months / 12, 1),
        'total_paid': round(total_paid),
        'payoff_order': payoff_order,
        'extra_monthly': extra_payment,
    })


# ═══════════════════════════════════════════════════════════════════
# AJ — GPS-Denied Navigation
# ═══════════════════════════════════════════════════════════════════

@tier8_bp.route('/api/calculators/shadow-stick', methods=['POST'])
def api_shadow_stick():
    """Shadow stick compass — find true north from sun shadow movement."""
    data = request.get_json() or {}
    try:
        lat = float(data.get('lat', 40))
    except (TypeError, ValueError):
        lat = 40

    hemisphere = 'north' if lat >= 0 else 'south'

    return jsonify({
        'method': 'Shadow Stick Compass',
        'hemisphere': hemisphere,
        'steps': [
            '1. Place a straight stick (3-4 ft) vertically in flat ground',
            '2. Mark the tip of the shadow with a stone (Point A)',
            '3. Wait 15-20 minutes',
            '4. Mark the new shadow tip (Point B)',
            f'5. Draw a line from A to B — this line runs {"West → East" if hemisphere == "north" else "East → West"}',
            f'6. Stand with Point A to your {"left" if hemisphere == "north" else "right"} — you face {"North" if hemisphere == "north" else "South"}',
        ],
        'accuracy': 'Within ~15° of true north. More accurate closer to noon.',
        'limitations': [
            'Requires direct sunlight — not usable on overcast days',
            'Less accurate at high latitudes (>60°)',
            'Less accurate near equinoxes when sun path is steep',
        ],
    })


@tier8_bp.route('/api/calculators/dead-reckoning', methods=['POST'])
def api_dead_reckoning():
    """Dead reckoning error budget calculator."""
    data = request.get_json() or {}
    try:
        distance_mi = float(data.get('distance_mi', 1))
        pace_count_per_100m = float(data.get('pace_count', 65))
        compass_error_deg = float(data.get('compass_error_deg', 5))
        terrain = data.get('terrain', 'trail')
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid input'}), 400

    # Pace count error: typically ±5% on trail, ±15% cross-country
    pace_errors = {'trail': 0.05, 'road': 0.03, 'cross_country': 0.15, 'dense_brush': 0.25, 'snow': 0.20}
    pace_err = pace_errors.get(terrain, 0.10)

    distance_m = distance_mi * 1609.34
    paces = distance_m / (100 / pace_count_per_100m)

    # Lateral error from compass deviation
    lateral_error_m = distance_m * math.sin(math.radians(compass_error_deg))

    # Distance error from pace count
    distance_error_m = distance_m * pace_err

    # Combined error circle radius (RSS)
    total_error_m = math.sqrt(lateral_error_m**2 + distance_error_m**2)

    return jsonify({
        'distance_mi': distance_mi,
        'total_paces': round(paces),
        'pace_count_per_100m': pace_count_per_100m,
        'compass_error_deg': compass_error_deg,
        'terrain': terrain,
        'lateral_error_m': round(lateral_error_m, 1),
        'distance_error_m': round(distance_error_m, 1),
        'total_error_radius_m': round(total_error_m, 1),
        'error_circle_acres': round(math.pi * (total_error_m**2) / 4047, 2),
        'tips': [
            'Aiming off: intentionally aim left/right of target, then follow linear feature',
            'Handrail: follow terrain features (ridgeline, stream, road) to reduce lateral error',
            'Catching feature: identify a feature beyond your target to know if you overshoot',
            f'At {distance_mi} mi, your error circle is ~{round(total_error_m)} meters radius',
        ],
    })
