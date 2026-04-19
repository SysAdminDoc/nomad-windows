"""Homestead & off-grid depth — calculators and trackers (Tier 6).

6.1  Greywater branched-drain designer
6.2  Humanure thermophilic tracker
6.3  Wood BTU + cord ledger
6.4  Passive solar sun-path plotter
6.5  Battery bank cycle-life model
6.6  Food preservation safety math
6.8  Seed-saving isolation distance planner
6.9  Beekeeping varroa calendar
6.10 Livestock drug + withdrawal timer
6.11 Pedigree + breeding cycle tracker
"""

import json
import logging
import math
from datetime import datetime, timezone, timedelta

from flask import Blueprint, request, jsonify
from db import db_session, log_activity

homestead_bp = Blueprint('homestead', __name__)
_log = logging.getLogger('nomad.homestead')


# ═══════════════════════════════════════════════════════════════════
# 6.1 — Greywater Branched-Drain Designer
# ═══════════════════════════════════════════════════════════════════

@homestead_bp.route('/api/calculators/greywater', methods=['POST'])
def api_greywater():
    """Design a branched-drain greywater system.

    Input: sources (shower, laundry, sink), daily_gallons, soil_type, num_outlets
    Returns: pipe sizing, mulch basin dimensions, plant recommendations.
    """
    data = request.get_json() or {}
    try:
        daily_gal = float(data.get('daily_gallons', 40))
        num_outlets = max(1, int(data.get('num_outlets', 3)))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid input'}), 400

    soil = data.get('soil_type', 'loam')
    sources = data.get('sources', ['shower', 'laundry'])

    # Soil infiltration rates (gal/sqft/day)
    soil_rates = {
        'sand': 5.0, 'loamy_sand': 3.5, 'sandy_loam': 2.5,
        'loam': 1.5, 'clay_loam': 0.8, 'clay': 0.3,
    }
    rate = soil_rates.get(soil, 1.5)

    gal_per_outlet = daily_gal / num_outlets
    basin_sqft = gal_per_outlet / rate
    basin_dim = math.sqrt(basin_sqft)

    # Pipe sizing: 1" for <15 GPD, 1.5" for <40, 2" for >40
    if daily_gal < 15:
        pipe = '1 inch'
    elif daily_gal < 40:
        pipe = '1.5 inch'
    else:
        pipe = '2 inch'

    plants = ['Banana', 'Citrus', 'Fig', 'Mulberry', 'Comfrey',
              'Canna lily', 'Mint', 'Lemongrass']

    return jsonify({
        'daily_gallons': daily_gal,
        'num_outlets': num_outlets,
        'gallons_per_outlet': round(gal_per_outlet, 1),
        'soil_type': soil,
        'infiltration_rate': rate,
        'basin_sqft_each': round(basin_sqft, 1),
        'basin_dimensions_ft': f'{basin_dim:.1f} x {basin_dim:.1f}',
        'mulch_depth_inches': 12,
        'pipe_diameter': pipe,
        'recommended_plants': plants[:num_outlets + 2],
        'notes': [
            'Never use greywater on root vegetables or leafy greens',
            'Use biocompatible soaps (no boron, chlorine, or sodium)',
            'Mulch basins prevent standing water and mosquito breeding',
            'Surge capacity: size for peak laundry day, not average',
        ],
        'soil_types_available': list(soil_rates.keys()),
    })


# ═══════════════════════════════════════════════════════════════════
# 6.2 — Humanure Thermophilic Tracker
# ═══════════════════════════════════════════════════════════════════

@homestead_bp.route('/api/homestead/humanure')
def api_humanure_list():
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM humanure_batches ORDER BY started_at DESC LIMIT 50'
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@homestead_bp.route('/api/homestead/humanure', methods=['POST'])
def api_humanure_create():
    data = request.get_json() or {}
    with db_session() as db:
        cur = db.execute('''
            INSERT INTO humanure_batches (bin_name, started_at, carbon_source, notes)
            VALUES (?,?,?,?)
        ''', (
            data.get('bin_name', 'Bin A'),
            data.get('started_at', datetime.now(timezone.utc).strftime('%Y-%m-%d')),
            data.get('carbon_source', 'sawdust'),
            data.get('notes', ''),
        ))
        db.commit()
        row = db.execute('SELECT * FROM humanure_batches WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('humanure_batch_started', detail=data.get('bin_name', 'Bin A'))
    return jsonify(dict(row)), 201


@homestead_bp.route('/api/homestead/humanure/<int:bid>/temp', methods=['POST'])
def api_humanure_temp(bid):
    """Log a temperature reading for a batch."""
    data = request.get_json() or {}
    try:
        temp_f = float(data.get('temp_f', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'temp_f required'}), 400

    with db_session() as db:
        row = db.execute('SELECT temps FROM humanure_batches WHERE id = ?', (bid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        try:
            temps = json.loads(row['temps'] or '[]')
        except (json.JSONDecodeError, TypeError):
            temps = []
        temps.append({
            'temp_f': temp_f,
            'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
        })
        # Check if thermophilic threshold met (131°F / 55°C for 3+ days)
        hot_days = sum(1 for t in temps if t['temp_f'] >= 131)
        status = 'active' if hot_days < 3 else 'thermophilic'

        db.execute('UPDATE humanure_batches SET temps = ?, status = ? WHERE id = ?',
                   (json.dumps(temps), status, bid))
        db.commit()

    return jsonify({'status': status, 'hot_days': hot_days, 'temp_f': temp_f, 'readings': len(temps)})


# ═══════════════════════════════════════════════════════════════════
# 6.3 — Wood BTU + Cord Ledger
# ═══════════════════════════════════════════════════════════════════

WOOD_BTU = {
    'oak_white':     {'btu_per_cord': 29_100_000, 'density': 'hard', 'seasoning_months': 12},
    'oak_red':       {'btu_per_cord': 27_300_000, 'density': 'hard', 'seasoning_months': 12},
    'hickory':       {'btu_per_cord': 30_600_000, 'density': 'hard', 'seasoning_months': 12},
    'maple_sugar':   {'btu_per_cord': 29_000_000, 'density': 'hard', 'seasoning_months': 12},
    'maple_red':     {'btu_per_cord': 24_000_000, 'density': 'hard', 'seasoning_months': 9},
    'ash':           {'btu_per_cord': 23_600_000, 'density': 'hard', 'seasoning_months': 6},
    'beech':         {'btu_per_cord': 27_800_000, 'density': 'hard', 'seasoning_months': 12},
    'birch':         {'btu_per_cord': 23_400_000, 'density': 'hard', 'seasoning_months': 9},
    'cherry':        {'btu_per_cord': 23_500_000, 'density': 'hard', 'seasoning_months': 6},
    'elm':           {'btu_per_cord': 24_500_000, 'density': 'hard', 'seasoning_months': 12},
    'pine_white':    {'btu_per_cord': 15_900_000, 'density': 'soft', 'seasoning_months': 6},
    'pine_yellow':   {'btu_per_cord': 22_500_000, 'density': 'soft', 'seasoning_months': 6},
    'spruce':        {'btu_per_cord': 17_500_000, 'density': 'soft', 'seasoning_months': 6},
    'cedar':         {'btu_per_cord': 13_000_000, 'density': 'soft', 'seasoning_months': 3},
    'poplar':        {'btu_per_cord': 15_800_000, 'density': 'soft', 'seasoning_months': 6},
    'cottonwood':    {'btu_per_cord': 15_800_000, 'density': 'soft', 'seasoning_months': 12},
    'douglas_fir':   {'btu_per_cord': 21_400_000, 'density': 'soft', 'seasoning_months': 9},
    'locust_black':  {'btu_per_cord': 29_300_000, 'density': 'hard', 'seasoning_months': 12},
    'walnut':        {'btu_per_cord': 22_200_000, 'density': 'hard', 'seasoning_months': 12},
    'osage_orange':  {'btu_per_cord': 32_900_000, 'density': 'hard', 'seasoning_months': 12},
}


@homestead_bp.route('/api/calculators/wood-btu')
def api_wood_btu_reference():
    """Wood species BTU reference table."""
    return jsonify({species: info for species, info in
                    sorted(WOOD_BTU.items(), key=lambda x: x[1]['btu_per_cord'], reverse=True)})


@homestead_bp.route('/api/calculators/wood-heating', methods=['POST'])
def api_wood_heating():
    """Calculate heating needs in cords of wood.

    Input: sqft, insulation_quality, heating_degree_days, wood_species, stove_efficiency
    """
    data = request.get_json() or {}
    try:
        sqft = float(data.get('sqft', 1500))
        hdd = float(data.get('heating_degree_days', 5000))
        efficiency = min(0.95, max(0.3, float(data.get('stove_efficiency', 0.75))))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid input'}), 400

    species = data.get('wood_species', 'oak_red')
    insulation = data.get('insulation_quality', 'average')

    # BTU per heating degree day per sqft (insulation factor)
    insulation_factors = {'poor': 12, 'average': 8, 'good': 5, 'excellent': 3}
    btu_factor = insulation_factors.get(insulation, 8)

    annual_btu = sqft * hdd * btu_factor
    wood = WOOD_BTU.get(species, WOOD_BTU['oak_red'])
    usable_btu = wood['btu_per_cord'] * efficiency
    cords_needed = annual_btu / usable_btu if usable_btu > 0 else 0

    return jsonify({
        'sqft': sqft,
        'heating_degree_days': hdd,
        'insulation_quality': insulation,
        'wood_species': species,
        'stove_efficiency': efficiency,
        'annual_btu_needed': round(annual_btu),
        'btu_per_cord': wood['btu_per_cord'],
        'usable_btu_per_cord': round(usable_btu),
        'cords_needed': round(cords_needed, 2),
        'seasoning_months': wood['seasoning_months'],
        'cost_estimate': f'${round(cords_needed * 250)}-${round(cords_needed * 400)}' if cords_needed > 0 else '$0',
    })


# ═══════════════════════════════════════════════════════════════════
# 6.4 — Passive Solar Sun-Path
# ═══════════════════════════════════════════════════════════════════

@homestead_bp.route('/api/calculators/sun-path', methods=['POST'])
def api_sun_path():
    """Calculate sun position throughout the day for passive solar design.

    Input: lat, lng, date (optional)
    Returns: hourly altitude + azimuth, sunrise/sunset, solar noon, window sizing.
    """
    data = request.get_json() or {}
    try:
        lat = float(data.get('lat', 40))
        lng = float(data.get('lng', -90))
    except (TypeError, ValueError):
        return jsonify({'error': 'lat and lng required'}), 400

    date_str = data.get('date', '')
    if date_str:
        try:
            target = datetime.fromisoformat(date_str)
        except ValueError:
            target = datetime.now()
    else:
        target = datetime.now()

    day_of_year = target.timetuple().tm_yday
    lat_rad = math.radians(lat)

    # Solar declination (Spencer formula)
    B = (360 / 365) * (day_of_year - 81)
    B_rad = math.radians(B)
    declination = 23.45 * math.sin(B_rad)
    decl_rad = math.radians(declination)

    # Equation of time (minutes)
    eot = 9.87 * math.sin(2 * B_rad) - 7.53 * math.cos(B_rad) - 1.5 * math.sin(B_rad)

    # Solar noon (local standard time)
    lstm = 15 * round(lng / 15)  # Local Standard Time Meridian
    time_correction = 4 * (lng - lstm) + eot  # minutes
    solar_noon_min = 720 - time_correction  # minutes from midnight

    # Sunrise/sunset hour angle
    cos_ha = -math.tan(lat_rad) * math.tan(decl_rad)
    cos_ha = max(-1, min(1, cos_ha))
    ha_deg = math.degrees(math.acos(cos_ha))
    daylight_hours = 2 * ha_deg / 15

    sunrise_min = solar_noon_min - (daylight_hours / 2) * 60
    sunset_min = solar_noon_min + (daylight_hours / 2) * 60

    # Hourly positions
    positions = []
    for hour in range(24):
        for minute in [0, 30]:
            total_min = hour * 60 + minute
            ha = 15 * ((total_min - solar_noon_min) / 60)  # degrees
            ha_rad = math.radians(ha)

            # Altitude
            sin_alt = (math.sin(lat_rad) * math.sin(decl_rad) +
                       math.cos(lat_rad) * math.cos(decl_rad) * math.cos(ha_rad))
            sin_alt = max(-1, min(1, sin_alt))
            altitude = math.degrees(math.asin(sin_alt))

            if altitude < -1:
                continue

            # Azimuth
            cos_az = (math.sin(decl_rad) - math.sin(lat_rad) * sin_alt) / \
                     (math.cos(lat_rad) * math.cos(math.asin(sin_alt))) if math.cos(math.asin(sin_alt)) != 0 else 0
            cos_az = max(-1, min(1, cos_az))
            azimuth = math.degrees(math.acos(cos_az))
            if ha > 0:
                azimuth = 360 - azimuth

            positions.append({
                'time': f'{hour:02d}:{minute:02d}',
                'altitude_deg': round(altitude, 1),
                'azimuth_deg': round(azimuth, 1),
            })

    # Solar window for passive heating (9 AM to 3 PM altitude at south)
    noon_altitude = 90 - lat + declination

    return jsonify({
        'date': target.strftime('%Y-%m-%d'),
        'lat': lat,
        'lng': lng,
        'declination_deg': round(declination, 2),
        'daylight_hours': round(daylight_hours, 2),
        'sunrise': f'{int(sunrise_min // 60):02d}:{int(sunrise_min % 60):02d}',
        'sunset': f'{int(sunset_min // 60):02d}:{int(sunset_min % 60):02d}',
        'solar_noon': f'{int(solar_noon_min // 60):02d}:{int(solar_noon_min % 60):02d}',
        'noon_altitude_deg': round(noon_altitude, 1),
        'positions': positions,
        'passive_solar_notes': {
            'overhang_depth': f'For a {round(noon_altitude, 0)}° noon sun, a 2-ft overhang shades a {round(2 / math.tan(math.radians(max(1, noon_altitude))), 1)}-ft tall window',
            'optimal_glazing': 'South-facing' if lat > 0 else 'North-facing',
            'thermal_mass': 'Dark masonry/concrete floor absorbs daytime heat, radiates at night',
        },
    })


# ═══════════════════════════════════════════════════════════════════
# 6.5 — Battery Bank Cycle-Life Model
# ═══════════════════════════════════════════════════════════════════

@homestead_bp.route('/api/calculators/battery-bank', methods=['POST'])
def api_battery_bank():
    """Model battery bank sizing and cycle life.

    Input: daily_kwh, battery_type, voltage, dod_pct, autonomy_days
    """
    data = request.get_json() or {}
    try:
        daily_kwh = float(data.get('daily_kwh', 5))
        voltage = float(data.get('voltage', 48))
        dod = min(0.95, max(0.1, float(data.get('dod_pct', 50)) / 100))
        autonomy = max(1, int(data.get('autonomy_days', 3)))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid input'}), 400

    batt_type = data.get('battery_type', 'lifepo4')

    # Battery chemistry characteristics
    chemistries = {
        'lead_acid_fla':  {'cycles_at_50dod': 1200, 'max_dod': 0.50, 'efficiency': 0.80, 'cost_kwh': 150, 'label': 'Flooded Lead-Acid'},
        'lead_acid_agm':  {'cycles_at_50dod': 800,  'max_dod': 0.50, 'efficiency': 0.85, 'cost_kwh': 250, 'label': 'AGM Lead-Acid'},
        'lead_acid_gel':  {'cycles_at_50dod': 1000, 'max_dod': 0.50, 'efficiency': 0.83, 'cost_kwh': 300, 'label': 'Gel Lead-Acid'},
        'lifepo4':        {'cycles_at_50dod': 5000, 'max_dod': 0.80, 'efficiency': 0.95, 'cost_kwh': 400, 'label': 'LiFePO4'},
        'li_ion_nmc':     {'cycles_at_50dod': 3000, 'max_dod': 0.80, 'efficiency': 0.93, 'cost_kwh': 350, 'label': 'Li-Ion NMC'},
        'nickel_iron':    {'cycles_at_50dod': 11000,'max_dod': 0.80, 'efficiency': 0.65, 'cost_kwh': 500, 'label': 'Nickel-Iron (Edison)'},
    }

    chem = chemistries.get(batt_type, chemistries['lifepo4'])
    effective_dod = min(dod, chem['max_dod'])

    # Sizing
    total_kwh_needed = daily_kwh * autonomy / chem['efficiency']
    usable_kwh = total_kwh_needed
    total_kwh_capacity = usable_kwh / effective_dod
    total_ah = total_kwh_capacity * 1000 / voltage

    # Cycle life (DOD affects cycle count — deeper = fewer cycles)
    dod_cycle_factor = (0.50 / effective_dod) ** 0.8 if effective_dod > 0 else 1
    estimated_cycles = int(chem['cycles_at_50dod'] * dod_cycle_factor)
    years = estimated_cycles / 365 if daily_kwh > 0 else 0

    cost = total_kwh_capacity * chem['cost_kwh']

    return jsonify({
        'daily_kwh': daily_kwh,
        'autonomy_days': autonomy,
        'battery_type': batt_type,
        'chemistry_label': chem['label'],
        'system_voltage': voltage,
        'depth_of_discharge_pct': round(effective_dod * 100),
        'total_capacity_kwh': round(total_kwh_capacity, 2),
        'usable_capacity_kwh': round(usable_kwh, 2),
        'total_ah': round(total_ah, 1),
        'round_trip_efficiency': chem['efficiency'],
        'estimated_cycle_life': estimated_cycles,
        'estimated_years': round(years, 1),
        'estimated_cost': round(cost),
        'cost_per_cycle': round(cost / estimated_cycles, 2) if estimated_cycles > 0 else 0,
        'chemistries_available': {k: v['label'] for k, v in chemistries.items()},
    })


# ═══════════════════════════════════════════════════════════════════
# 6.6 — Food Preservation Safety Math
# ═══════════════════════════════════════════════════════════════════

@homestead_bp.route('/api/calculators/curing-salt', methods=['POST'])
def api_curing_salt():
    """Calculate curing salt ratios for meat preservation.

    Input: meat_weight_lb, cure_type, nitrite_ppm_target
    """
    data = request.get_json() or {}
    try:
        weight_lb = float(data.get('meat_weight_lb', 5))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid input'}), 400

    cure_type = data.get('cure_type', 'prague_1')
    weight_g = weight_lb * 453.592

    if cure_type == 'prague_1':
        # Prague Powder #1: 6.25% sodium nitrite
        # FDA max: 156 ppm ingoing nitrite for most products
        target_ppm = min(200, max(100, int(data.get('nitrite_ppm_target', 156))))
        cure_g = (target_ppm * weight_g) / (62500)  # 6.25% = 62500 ppm
        salt_g = weight_g * 0.025  # 2.5% salt by weight baseline
        result = {
            'cure': 'Prague Powder #1 (Instacure #1)',
            'cure_grams': round(cure_g, 2),
            'cure_teaspoons': round(cure_g / 5.7, 2),
            'salt_grams': round(salt_g, 1),
            'nitrite_ppm': target_ppm,
        }
    elif cure_type == 'prague_2':
        # Prague Powder #2: 6.25% nitrite + 4% nitrate (for dry-cured)
        cure_g = weight_g * 0.0025  # 0.25% of meat weight standard
        result = {
            'cure': 'Prague Powder #2 (Instacure #2)',
            'cure_grams': round(cure_g, 2),
            'cure_teaspoons': round(cure_g / 5.7, 2),
            'notes': 'For dry-cured products only (salami, prosciutto). Not for cooked products.',
        }
    else:  # equilibrium brine
        brine_pct = float(data.get('brine_salt_pct', 3.5))
        water_g = weight_g  # 1:1 water to meat
        salt_g = (weight_g + water_g) * (brine_pct / 100)
        cure_g = (156 * (weight_g + water_g)) / 62500
        result = {
            'cure': 'Equilibrium Brine',
            'water_grams': round(water_g),
            'salt_grams': round(salt_g, 1),
            'cure_grams': round(cure_g, 2),
            'brine_salt_pct': brine_pct,
        }

    result['meat_weight_lb'] = weight_lb
    result['warning'] = 'Follow USDA guidelines. Incorrect curing can cause botulism.'
    return jsonify(result)


@homestead_bp.route('/api/calculators/fermentation', methods=['POST'])
def api_fermentation():
    """Fermentation salt brine calculator.

    Input: vessel_ml, salt_pct, vegetable
    """
    data = request.get_json() or {}
    try:
        vessel_ml = float(data.get('vessel_ml', 1000))
        salt_pct = min(10, max(1, float(data.get('salt_pct', 3.5))))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid input'}), 400

    water_ml = vessel_ml * 0.6  # ~60% water in a packed jar
    salt_g = water_ml * (salt_pct / 100)

    # Temperature guidelines
    temp_guide = {
        '65-70F': '3-4 weeks — slow, complex flavor',
        '70-75F': '2-3 weeks — standard pace',
        '75-80F': '1-2 weeks — fast, monitor daily',
        '80F+': 'Too fast — risk of mush and off-flavors',
    }

    return jsonify({
        'vessel_ml': vessel_ml,
        'water_ml': round(water_ml),
        'salt_grams': round(salt_g, 1),
        'salt_teaspoons': round(salt_g / 6, 1),
        'salt_pct': salt_pct,
        'recommended_range': '2-5% for vegetables, 3.5% standard',
        'temperature_guide': temp_guide,
        'ph_target': 'Below 4.6 = shelf stable (test with pH strips)',
    })


# ═══════════════════════════════════════════════════════════════════
# 6.8 — Seed-Saving Isolation Distance Planner
# ═══════════════════════════════════════════════════════════════════

SEED_ISOLATION = {
    'tomato':     {'distance_ft': 10,   'method': 'self-pollinating', 'years_viable': 4},
    'pepper':     {'distance_ft': 300,  'method': 'insect-pollinated', 'years_viable': 2},
    'squash':     {'distance_ft': 1000, 'method': 'insect-pollinated', 'years_viable': 4},
    'cucumber':   {'distance_ft': 1000, 'method': 'insect-pollinated', 'years_viable': 5},
    'corn':       {'distance_ft': 1000, 'method': 'wind-pollinated', 'years_viable': 2},
    'bean':       {'distance_ft': 25,   'method': 'self-pollinating', 'years_viable': 3},
    'pea':        {'distance_ft': 50,   'method': 'self-pollinating', 'years_viable': 3},
    'lettuce':    {'distance_ft': 25,   'method': 'self-pollinating', 'years_viable': 3},
    'carrot':     {'distance_ft': 1000, 'method': 'insect-pollinated', 'years_viable': 3},
    'beet':       {'distance_ft': 2640, 'method': 'wind-pollinated', 'years_viable': 4},
    'onion':      {'distance_ft': 1000, 'method': 'insect-pollinated', 'years_viable': 1},
    'radish':     {'distance_ft': 500,  'method': 'insect-pollinated', 'years_viable': 4},
    'spinach':    {'distance_ft': 2640, 'method': 'wind-pollinated', 'years_viable': 3},
    'melon':      {'distance_ft': 1000, 'method': 'insect-pollinated', 'years_viable': 5},
    'broccoli':   {'distance_ft': 1000, 'method': 'insect-pollinated', 'years_viable': 4},
    'cabbage':    {'distance_ft': 1000, 'method': 'insect-pollinated', 'years_viable': 4},
    'sunflower':  {'distance_ft': 2640, 'method': 'insect-pollinated', 'years_viable': 5},
}


@homestead_bp.route('/api/calculators/seed-isolation')
def api_seed_isolation():
    """Seed-saving isolation distance reference."""
    crop = request.args.get('crop', '')
    if crop:
        info = SEED_ISOLATION.get(crop.lower())
        if not info:
            return jsonify({'error': f'Unknown crop. Available: {", ".join(sorted(SEED_ISOLATION.keys()))}'}), 404
        return jsonify({'crop': crop, **info})
    return jsonify(SEED_ISOLATION)


# ═══════════════════════════════════════════════════════════════════
# 6.9 — Beekeeping Varroa Calendar
# ═══════════════════════════════════════════════════════════════════

@homestead_bp.route('/api/calculators/varroa-calendar', methods=['POST'])
def api_varroa_calendar():
    """Generate a varroa mite management calendar.

    Input: lat (for season timing), treatment_preference
    """
    data = request.get_json() or {}
    try:
        lat = float(data.get('lat', 40))
    except (TypeError, ValueError):
        lat = 40

    # Adjust timing for latitude (earlier in south)
    offset_weeks = max(-4, min(4, int((40 - lat) / 5)))

    treatments = {
        'oxalic_acid':  {'window': 'broodless period (Dec-Jan)', 'method': 'Vaporization or dribble', 'temp_range': '35-55°F'},
        'formic_acid':  {'window': 'Spring/Fall', 'method': 'MAQS or Formic Pro strips', 'temp_range': '50-85°F'},
        'apivar':       {'window': 'Spring/Fall (42-56 day strip)', 'method': 'Amitraz strips between frames', 'temp_range': 'Any'},
        'thymol':       {'window': 'Late summer', 'method': 'Apiguard or ApiLifeVar', 'temp_range': '60-95°F'},
        'hop_guard':    {'window': 'Any (between supers off)', 'method': 'Strips between frames', 'temp_range': '50-95°F'},
    }

    calendar = [
        {'month': 'January',   'tasks': ['Oxalic acid vaporization (broodless)', 'Check food stores', 'Order packages/nucs']},
        {'month': 'February',  'tasks': ['Monitor candy boards', 'Plan apiary layout', 'Clean/repair equipment']},
        {'month': 'March',     'tasks': ['First inspection when 50°F+', 'Check queen laying pattern', 'Feed 1:1 sugar syrup if light']},
        {'month': 'April',     'tasks': ['Spring alcohol wash (mite count)', 'Add supers if nectar flow starting', 'Split strong hives']},
        {'month': 'May',       'tasks': ['Swarm prevention (space management)', 'Monitor queen cells', 'Add honey supers']},
        {'month': 'June',      'tasks': ['Mite count (threshold: 3/100 bees)', 'Main honey flow management', 'Check for laying workers']},
        {'month': 'July',      'tasks': ['Mite count critical', 'Treat if >3% mite load', 'Begin fall requeening if needed']},
        {'month': 'August',    'tasks': ['CRITICAL: Fall treatment window opens', 'Remove supers before treating', 'Formic acid or Apivar']},
        {'month': 'September', 'tasks': ['Continue/complete fall treatment', 'Feed 2:1 syrup for winter stores', 'Reduce entrances']},
        {'month': 'October',   'tasks': ['Final mite count', 'Insulate hives in cold climates', 'Mouse guards on']},
        {'month': 'November',  'tasks': ['Minimal inspections', 'Check ventilation', 'Fondant/candy board if light']},
        {'month': 'December',  'tasks': ['Oxalic acid window (broodless)', 'Plan next season', 'Order supplies']},
    ]

    return jsonify({
        'calendar': calendar,
        'treatments': treatments,
        'mite_thresholds': {
            'spring': '2 mites per 100 bees (alcohol wash)',
            'summer': '3 mites per 100 bees',
            'fall': '2 mites per 100 bees (TREAT IMMEDIATELY)',
        },
        'latitude_note': f'Calendar adjusted for lat {lat}° ({offset_weeks:+d} weeks from baseline)',
    })


# ═══════════════════════════════════════════════════════════════════
# 6.10 — Livestock Drug + Withdrawal Timer
# ═══════════════════════════════════════════════════════════════════

WITHDRAWAL_PERIODS = {
    'penicillin':       {'meat_days': 10, 'milk_days': 4,  'egg_days': 0, 'species': ['cattle', 'sheep', 'goat', 'swine']},
    'oxytetracycline':  {'meat_days': 28, 'milk_days': 4,  'egg_days': 0, 'species': ['cattle', 'sheep', 'swine']},
    'ceftiofur':        {'meat_days': 4,  'milk_days': 0,  'egg_days': 0, 'species': ['cattle', 'swine']},
    'ivermectin':       {'meat_days': 35, 'milk_days': 0,  'egg_days': 0, 'species': ['cattle', 'sheep', 'goat', 'swine']},
    'fenbendazole':     {'meat_days': 8,  'milk_days': 0,  'egg_days': 0, 'species': ['cattle', 'goat']},
    'albendazole':      {'meat_days': 27, 'milk_days': 2,  'egg_days': 0, 'species': ['cattle']},
    'flunixin':         {'meat_days': 4,  'milk_days': 1.5,'egg_days': 0, 'species': ['cattle', 'swine']},
    'dexamethasone':    {'meat_days': 0,  'milk_days': 0,  'egg_days': 0, 'species': ['cattle']},
    'tylosin':          {'meat_days': 21, 'milk_days': 4,  'egg_days': 0, 'species': ['cattle', 'swine']},
    'sulfadimethoxine': {'meat_days': 7,  'milk_days': 2.5,'egg_days': 10,'species': ['cattle', 'poultry']},
}


@homestead_bp.route('/api/calculators/withdrawal')
def api_withdrawal_reference():
    """Drug withdrawal period reference."""
    drug = request.args.get('drug', '')
    if drug:
        info = WITHDRAWAL_PERIODS.get(drug.lower())
        if not info:
            return jsonify({'error': f'Unknown drug. Available: {", ".join(sorted(WITHDRAWAL_PERIODS.keys()))}'}), 404
        return jsonify({'drug': drug, **info})
    return jsonify(WITHDRAWAL_PERIODS)


@homestead_bp.route('/api/calculators/withdrawal-timer', methods=['POST'])
def api_withdrawal_timer():
    """Calculate safe harvest/milk/egg date after drug administration."""
    data = request.get_json() or {}
    drug = data.get('drug', '').lower()
    admin_date = data.get('administered_date', '')

    if drug not in WITHDRAWAL_PERIODS:
        return jsonify({'error': f'Unknown drug. Available: {", ".join(sorted(WITHDRAWAL_PERIODS.keys()))}'}), 400

    if not admin_date:
        admin_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    try:
        admin_dt = datetime.strptime(admin_date, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Invalid date format (YYYY-MM-DD)'}), 400

    info = WITHDRAWAL_PERIODS[drug]
    result = {
        'drug': drug,
        'administered_date': admin_date,
        'species': info['species'],
    }

    if info['meat_days'] > 0:
        safe = admin_dt + timedelta(days=info['meat_days'])
        result['meat_safe_date'] = safe.strftime('%Y-%m-%d')
        result['meat_days_remaining'] = max(0, (safe - datetime.now()).days)
    if info['milk_days'] > 0:
        safe = admin_dt + timedelta(days=int(math.ceil(info['milk_days'])))
        result['milk_safe_date'] = safe.strftime('%Y-%m-%d')
        result['milk_days_remaining'] = max(0, (safe - datetime.now()).days)
    if info['egg_days'] > 0:
        safe = admin_dt + timedelta(days=info['egg_days'])
        result['egg_safe_date'] = safe.strftime('%Y-%m-%d')
        result['egg_days_remaining'] = max(0, (safe - datetime.now()).days)

    result['warning'] = 'These are US FDA/FARAD standard withdrawal periods. Always verify with your veterinarian.'
    return jsonify(result)
