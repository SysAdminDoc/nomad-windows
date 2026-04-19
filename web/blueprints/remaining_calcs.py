"""Remaining calculators and reference tools — bulk S/M-effort roadmap items.

Covers: Navigation (GPS-denied), Outdoor Cooking, Financial Prep,
Economy & Recovery, Weather parsing, OPSEC, Environmental Monitoring,
Hardware Catalogs, Health & Family remaining.
"""

import json
import logging
import math
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
from db import db_session, log_activity

remaining_calcs_bp = Blueprint('remaining_calcs', __name__)
_log = logging.getLogger('nomad.remaining_calcs')


# ═══════════════════════════════════════════════════════════════════
# Navigation (GPS-denied) — AJ2, AJ3, AJ4, AJ8
# ═══════════════════════════════════════════════════════════════════

@remaining_calcs_bp.route('/api/calculators/polaris-latitude', methods=['POST'])
def api_polaris_latitude():
    """AJ2: Determine latitude from Polaris altitude (Northern Hemisphere)
    or Southern Cross (Southern Hemisphere)."""
    data = request.get_json() or {}
    try:
        altitude_deg = float(data.get('polaris_altitude_deg', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'polaris_altitude_deg required'}), 400

    hemisphere = data.get('hemisphere', 'north')

    if hemisphere == 'north':
        # Polaris is within ~0.7° of true north celestial pole
        latitude = altitude_deg
        correction = -0.7 * math.cos(math.radians(altitude_deg))  # simplified precession correction
        return jsonify({
            'method': 'Polaris Altitude',
            'measured_altitude_deg': altitude_deg,
            'estimated_latitude': round(latitude + correction, 1),
            'accuracy_deg': 1.0,
            'steps': [
                '1. Find Polaris using Big Dipper pointer stars (Dubhe + Merak)',
                '2. Measure angle from horizon to Polaris (fist at arm\'s length ≈ 10°)',
                '3. That angle equals your latitude (±1°)',
            ],
        })
    else:
        # Southern Cross method
        return jsonify({
            'method': 'Southern Cross',
            'steps': [
                '1. Find the Southern Cross (Crux) — 4 bright stars in cross pattern',
                '2. Extend the long axis 4.5× its length toward the horizon',
                '3. Drop a perpendicular to the horizon — that point is due south',
                '4. The altitude of the South Celestial Pole ≈ your latitude south',
                '5. Use a clinometer or fist-widths to measure the altitude',
            ],
            'note': 'Less precise than Polaris — Southern Cross is ~4° from true pole',
        })


@remaining_calcs_bp.route('/api/calculators/lunar-azimuth')
def api_lunar_azimuth():
    """AJ3: Approximate direction from moon phase + position."""
    return jsonify({
        'method': 'Lunar Direction Finding',
        'rules': [
            {'phase': 'First Quarter (half moon, right side lit)', 'rule': 'Moon is due south at sunset (6 PM), due west at midnight'},
            {'phase': 'Full Moon', 'rule': 'Moon rises in the east at sunset, due south at midnight, sets in the west at sunrise'},
            {'phase': 'Last Quarter (half moon, left side lit)', 'rule': 'Moon is due east at midnight, due south at sunrise (6 AM)'},
            {'phase': 'Crescent Moon', 'rule': 'Draw a line through the horns to the horizon — indicates roughly south (N hemisphere)'},
        ],
        'accuracy': 'Within ~15-20° — use for general orientation, not precise navigation',
    })


@remaining_calcs_bp.route('/api/calculators/sun-clock', methods=['POST'])
def api_sun_clock():
    """AJ4: Estimate time from sun position (no watch)."""
    data = request.get_json() or {}
    try:
        sun_altitude_deg = float(data.get('sun_altitude_deg', 45))
        sun_azimuth_deg = float(data.get('sun_azimuth_deg', 180))
        lat = float(data.get('lat', 40))
    except (TypeError, ValueError):
        return jsonify({'error': 'sun_altitude_deg and sun_azimuth_deg required'}), 400

    # Rough hour angle from azimuth (south = noon in N hemisphere)
    if lat >= 0:
        hour_angle = (sun_azimuth_deg - 180) / 15  # 15° per hour
    else:
        hour_angle = (sun_azimuth_deg) / 15

    estimated_hour = 12 + hour_angle
    estimated_hour = estimated_hour % 24

    return jsonify({
        'method': 'Sun Position Clock',
        'estimated_time': f'{int(estimated_hour):02d}:{int((estimated_hour % 1) * 60):02d}',
        'accuracy': '±30-60 minutes depending on season and latitude',
        'quick_methods': [
            'Fist method: each fist-width between sun and horizon ≈ 1 hour until sunset',
            'Shadow length: your shadow = your height → ~45° sun → mid-morning/afternoon',
            'Shadow direction: shortest shadow = solar noon (not always 12:00 clock time)',
        ],
    })


@remaining_calcs_bp.route('/api/calculators/barometric-altimeter', methods=['POST'])
def api_barometric_altimeter():
    """AJ8: Calibrate barometric altimeter from known elevation or pressure."""
    data = request.get_json() or {}
    try:
        pressure_hpa = float(data.get('pressure_hpa', 1013.25))
        known_elevation_ft = data.get('known_elevation_ft')
        temperature_c = float(data.get('temperature_c', 15))
    except (TypeError, ValueError):
        return jsonify({'error': 'pressure_hpa required'}), 400

    # Standard atmosphere: P = P0 * (1 - L*h/T0)^(g*M/(R*L))
    # Simplified: elevation_ft ≈ (1 - (P/1013.25)^0.190284) * 145366.45
    if known_elevation_ft is not None:
        # Calibration mode — calculate what sea-level pressure should be
        h = float(known_elevation_ft)
        ratio = (1 - h / 145366.45)
        sea_level_pressure = pressure_hpa / (ratio ** (1 / 0.190284)) if ratio > 0 else 1013.25
        return jsonify({
            'mode': 'calibration',
            'station_pressure_hpa': pressure_hpa,
            'known_elevation_ft': h,
            'calculated_sea_level_pressure_hpa': round(sea_level_pressure, 2),
            'note': 'Set your altimeter to this sea-level value for accurate readings',
        })
    else:
        # Measurement mode — calculate elevation from pressure
        elevation_ft = 145366.45 * (1 - (pressure_hpa / 1013.25) ** 0.190284)
        # Temperature correction
        temp_correction = (temperature_c - 15) * elevation_ft * 0.00012
        corrected = elevation_ft + temp_correction

        return jsonify({
            'mode': 'measurement',
            'station_pressure_hpa': pressure_hpa,
            'estimated_elevation_ft': round(corrected),
            'estimated_elevation_m': round(corrected * 0.3048),
            'temperature_correction_ft': round(temp_correction),
            'note': 'Accuracy degrades with weather changes — recalibrate at known elevations',
        })


# ═══════════════════════════════════════════════════════════════════
# Outdoor Cooking — AL1, AL3, AL4, AL6, AL7, AL8
# ═══════════════════════════════════════════════════════════════════

@remaining_calcs_bp.route('/api/reference/fire-heat')
def api_fire_heat_chart():
    """AL1: Fire-heat temperature reference by method."""
    return jsonify({
        'methods': {
            'hand_test': [
                {'seconds': 1,  'temp_f': '600+', 'level': 'Very hot', 'use': 'Searing, wok cooking'},
                {'seconds': 2,  'temp_f': '500-600', 'level': 'Hot', 'use': 'Grilling steaks, pizza'},
                {'seconds': 3,  'temp_f': '400-500', 'level': 'Medium-hot', 'use': 'Most grilling'},
                {'seconds': 5,  'temp_f': '300-400', 'level': 'Medium', 'use': 'Baking, roasting'},
                {'seconds': 7,  'temp_f': '250-300', 'level': 'Medium-low', 'use': 'Slow cooking, smoking'},
                {'seconds': 10, 'temp_f': '200-250', 'level': 'Low', 'use': 'Warming, dehydrating'},
            ],
            'coal_readiness': {
                'black_with_flame': 'Not ready — still producing volatile gases',
                'gray_with_red_glow': 'Ready for cooking — peak heat, stable temp',
                'white_ash_covered': 'Past peak — good for slow cooking, reduce heat',
                'crumbling_ash': 'Nearly spent — add fresh coals underneath',
            },
        },
    })


@remaining_calcs_bp.route('/api/calculators/rocket-stove', methods=['POST'])
def api_rocket_stove():
    """AL3: Rocket stove design calculator."""
    data = request.get_json() or {}
    try:
        pot_diameter_in = float(data.get('pot_diameter_in', 10))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid input'}), 400

    # Rocket stove proportions (Dr. Larry Winiarski principles)
    combustion_chamber_in = max(4, pot_diameter_in * 0.5)
    chimney_height_in = combustion_chamber_in * 3
    feed_tube_length_in = combustion_chamber_in * 2.5
    gap_above_fire_in = combustion_chamber_in * 0.5
    insulation_thickness_in = max(2, combustion_chamber_in * 0.5)

    return jsonify({
        'pot_diameter_in': pot_diameter_in,
        'combustion_chamber_diameter_in': round(combustion_chamber_in, 1),
        'chimney_internal_height_in': round(chimney_height_in, 1),
        'feed_tube_length_in': round(feed_tube_length_in, 1),
        'gap_pot_to_chimney_in': round(gap_above_fire_in, 1),
        'insulation_thickness_in': round(insulation_thickness_in, 1),
        'fuel_efficiency': '3-5× better than open fire',
        'materials': ['Metal cans (paint/coffee cans)', 'Vermiculite or perlite insulation',
                      'Clay/mud', 'Pot support (rebar or flat metal)'],
        'principles': [
            'Insulate the combustion chamber — heat stays in the burn, not the walls',
            'Narrow feed tube starves the fire of excess air — cleaner burn',
            'Chimney draft pulls air through fuel — self-feeding',
            'Small diameter sticks (1-2 inch) burn cleaner than large logs',
        ],
    })


@remaining_calcs_bp.route('/api/reference/solar-oven')
def api_solar_oven():
    """AL4: Solar oven performance curves."""
    return jsonify({
        'performance': {
            'box_cooker': {'max_temp_f': 350, 'time_factor': 1.5, 'cost': '$20-50 DIY',
                           'notes': 'Reflective panels + insulated box. Best for casseroles, rice, beans.'},
            'panel_cooker': {'max_temp_f': 275, 'time_factor': 2.0, 'cost': '$5-15 DIY',
                             'notes': 'Folding reflective panels + dark pot in bag. Lightest, most portable.'},
            'parabolic_cooker': {'max_temp_f': 600, 'time_factor': 1.0, 'cost': '$50-200',
                                 'notes': 'Focused beam — can fry and boil. Requires tracking. Burn risk.'},
        },
        'conditions': {
            'full_sun': {'factor': 1.0, 'note': 'Clear sky, direct sun — optimal'},
            'partly_cloudy': {'factor': 0.6, 'note': 'Intermittent clouds — 50-60% longer cook times'},
            'hazy': {'factor': 0.7, 'note': 'Thin overcast — still works but slower'},
            'overcast': {'factor': 0.0, 'note': 'Will not reach cooking temperature'},
        },
        'tips': [
            'Dark, thin-walled pots absorb heat best (avoid shiny)',
            'Pre-heat oven 30 min before adding food',
            'Don\'t open to check — each opening loses 10-15 min of heat',
            'Best hours: 10 AM - 2 PM (sun angle > 45°)',
            'Use an oven thermometer — don\'t guess',
        ],
    })


@remaining_calcs_bp.route('/api/reference/pit-cooking')
def api_pit_cooking():
    """AL6: Pit cooking SOPs (hangi, bean-hole, imu)."""
    return jsonify({
        'methods': {
            'bean_hole': {
                'description': 'New England method — beans baked underground overnight',
                'steps': ['Dig pit 2ft × 2ft × 2ft', 'Build hardwood fire in pit, burn 2-3 hours',
                          'Remove coals, line bottom with flat rocks', 'Place sealed cast-iron pot on rocks',
                          'Cover with remaining coals', 'Bury with 6+ inches of dirt', 'Cook 8-12 hours'],
                'time_hours': '8-12', 'temp_f': '225-275',
            },
            'hangi': {
                'description': 'Maori earth oven — meat and vegetables on hot stones',
                'steps': ['Dig pit 3ft × 3ft × 3ft', 'Heat volcanic/river rocks in fire 2+ hours',
                          'Line pit with hot rocks', 'Layer: cabbage leaves → meat → root veg → greens',
                          'Cover with wet sacks/burlap', 'Bury with dirt — seal completely', 'Cook 3-4 hours'],
                'time_hours': '3-4', 'temp_f': '300-350',
            },
            'imu': {
                'description': 'Hawaiian underground oven — traditional for kalua pig',
                'steps': ['Dig pit 4ft × 4ft × 3ft', 'Line with lava rocks, build fire 3+ hours',
                          'Remove fire, leave hot rocks', 'Wrap food in banana/ti leaves',
                          'Place on rocks, cover with more leaves', 'Cover with wet burlap, then dirt',
                          'Cook 6-12 hours depending on size'],
                'time_hours': '6-12', 'temp_f': '300-400',
            },
        },
        'safety': [
            'NEVER use river rocks that may contain moisture — they can explode when heated',
            'Use only non-porous rocks (granite, basalt). Avoid sandstone, limestone, shale',
            'Ensure all food reaches 165°F internal temperature (check with thermometer)',
            'Keep pit away from tree roots and dry brush',
        ],
    })


@remaining_calcs_bp.route('/api/calculators/haybox', methods=['POST'])
def api_haybox():
    """AL7: Haybox (retained-heat) cooker calculator."""
    data = request.get_json() or {}
    try:
        initial_temp_f = float(data.get('initial_temp_f', 212))
        target_temp_f = float(data.get('target_temp_f', 180))
        pot_volume_qt = float(data.get('pot_volume_qt', 4))
        insulation = data.get('insulation', 'good')
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid input'}), 400

    # Heat loss rate depends on insulation quality
    loss_rates = {'poor': 8, 'fair': 5, 'good': 3, 'excellent': 1.5}  # °F/hour
    rate = loss_rates.get(insulation, 3)

    # Larger pots retain heat better (thermal mass)
    mass_factor = max(0.5, 1.0 - (pot_volume_qt - 2) * 0.05)
    effective_rate = rate * mass_factor

    hours_above_target = (initial_temp_f - target_temp_f) / effective_rate if effective_rate > 0 else 0

    return jsonify({
        'initial_temp_f': initial_temp_f,
        'target_temp_f': target_temp_f,
        'insulation_quality': insulation,
        'heat_loss_rate_f_per_hour': round(effective_rate, 1),
        'hours_above_target': round(hours_above_target, 1),
        'suitable_foods': ['Rice', 'Beans', 'Stews', 'Oatmeal', 'Pasta', 'Soups', 'Grains'],
        'instructions': [
            f'Bring food to a full rolling boil on stove/fire',
            f'Boil for 5-10 minutes to ensure 212°F throughout',
            f'Transfer sealed pot immediately into insulated box',
            f'Food will stay above {target_temp_f}°F for ~{round(hours_above_target, 1)} hours',
            'Saves 50-80% of cooking fuel compared to continuous heating',
        ],
        'insulation_options': {
            'excellent': 'Styrofoam cooler or commercial thermal cooker',
            'good': 'Dense hay/straw, wool blankets, sleeping bag',
            'fair': 'Newspaper layers, towels, cushions',
            'poor': 'Single blanket or thin insulation',
        },
    })


@remaining_calcs_bp.route('/api/calculators/bulk-cooking', methods=['POST'])
def api_bulk_cooking():
    """AL8: Bulk cooking scaling math."""
    data = request.get_json() or {}
    try:
        recipe_servings = max(1, int(data.get('recipe_servings', 4)))
        target_servings = max(1, int(data.get('target_servings', 20)))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid input'}), 400

    scale = target_servings / recipe_servings
    ingredients = data.get('ingredients', [])

    scaled = []
    for ing in ingredients:
        try:
            amt = float(ing.get('amount', 0))
            scaled.append({
                'name': ing.get('name', ''),
                'original': amt,
                'scaled': round(amt * scale, 2),
                'unit': ing.get('unit', ''),
            })
        except (TypeError, ValueError):
            continue

    return jsonify({
        'scale_factor': round(scale, 2),
        'recipe_servings': recipe_servings,
        'target_servings': target_servings,
        'scaled_ingredients': scaled,
        'seasoning_note': f'Scale seasonings by {round(scale * 0.75, 2)}× (75% of linear scale) — seasoning doesn\'t scale linearly',
        'cooking_time_note': 'Larger volumes need longer cooking but NOT proportionally — increase by 25-50% max',
    })


# ═══════════════════════════════════════════════════════════════════
# Financial Preparedness — AT1, AT2, AT5, AT6, AT7
# ═══════════════════════════════════════════════════════════════════

@remaining_calcs_bp.route('/api/calculators/portfolio-stress', methods=['POST'])
def api_portfolio_stress():
    """AT1: Portfolio stress-test against historical scenarios."""
    data = request.get_json() or {}
    assets = data.get('assets', [])
    if not assets:
        return jsonify({'error': 'assets array required (each: {name, value, type})'}), 400

    total = sum(float(a.get('value', 0)) for a in assets)

    scenarios = {
        '2008_financial_crisis': {'stocks': -0.55, 'bonds': 0.05, 'real_estate': -0.30, 'gold': 0.05, 'cash': 0, 'crypto': 0},
        '2020_covid_crash': {'stocks': -0.34, 'bonds': 0.03, 'real_estate': -0.05, 'gold': 0.25, 'cash': 0, 'crypto': -0.50},
        'stagflation_1970s': {'stocks': -0.45, 'bonds': -0.15, 'real_estate': -0.10, 'gold': 1.5, 'cash': -0.12, 'crypto': 0},
        'hyperinflation': {'stocks': -0.30, 'bonds': -0.60, 'real_estate': 0.20, 'gold': 2.0, 'cash': -0.90, 'crypto': -0.70},
        'grid_down_prolonged': {'stocks': -0.80, 'bonds': -0.50, 'real_estate': -0.40, 'gold': 0.50, 'cash': -0.30, 'crypto': -1.0},
    }

    results = {}
    for scenario_name, impacts in scenarios.items():
        new_total = 0
        for a in assets:
            val = float(a.get('value', 0))
            atype = a.get('type', 'cash').lower()
            impact = impacts.get(atype, 0)
            new_total += val * (1 + impact)
        results[scenario_name] = {
            'new_value': round(new_total),
            'loss_pct': round((new_total - total) / total * 100, 1) if total > 0 else 0,
        }

    return jsonify({
        'current_total': round(total),
        'scenarios': results,
        'recommendation': 'Diversify across asset classes. Physical assets (gold, land, supplies) hedge grid-down scenarios.',
    })


@remaining_calcs_bp.route('/api/reference/insurance-audit')
def api_insurance_audit():
    """AT2: Insurance coverage audit checklist."""
    return jsonify({
        'categories': {
            'homeowners_renters': ['Dwelling coverage ≥ rebuild cost', 'Personal property (actual cash vs replacement)',
                                    'Liability ≥ $300K', 'Loss of use / additional living expenses',
                                    'Flood coverage (separate policy)', 'Earthquake coverage (separate rider)',
                                    'Sewer backup rider', 'Home business rider if applicable'],
            'auto': ['Liability ≥ 100/300/100', 'Uninsured/underinsured motorist',
                     'Comprehensive (theft, weather, animals)', 'Rental reimbursement', 'GAP coverage if financed'],
            'health': ['Max out-of-pocket affordable?', 'Prescription coverage adequate?',
                       'Emergency/urgent care network', 'Telehealth available?', 'Mental health parity'],
            'life': ['Coverage ≥ 10× annual income', 'Term vs whole (term usually better value)',
                     'Beneficiaries updated?', 'Employer-provided sufficient or supplemental needed?'],
            'disability': ['Short-term disability (employer or private)', 'Long-term disability (60-70% income replacement)',
                           'Own-occupation vs any-occupation definition'],
            'umbrella': ['$1M minimum recommended', 'Covers above auto + home liability limits',
                         'Protects assets from lawsuits'],
        },
        'review_frequency': 'Annually, plus after any major life event (marriage, birth, home purchase, job change)',
    })


@remaining_calcs_bp.route('/api/reference/asset-portability')
def api_asset_portability():
    """AT5: Asset portability classifier for evacuation scenarios."""
    return jsonify({
        'tiers': {
            'immediately_portable': {
                'description': 'Can carry on your person during evacuation',
                'examples': ['Cash (small bills)', 'Gold/silver coins', 'USB drives with documents',
                             'Crypto hardware wallet', 'Jewelry', 'Passport/ID'],
                'max_weight': '2-5 lbs',
            },
            'vehicle_portable': {
                'description': 'Fits in bug-out vehicle',
                'examples': ['Important documents box', 'Gun safe contents', 'Silver bars',
                             'Laptop/tablet', 'Hard drives with backups', 'Medication supply'],
                'max_weight': '50-200 lbs',
            },
            'relocatable': {
                'description': 'Can be moved with effort and time',
                'examples': ['Firearms collection', 'Tools', 'Food storage', 'Generator',
                             'Solar panels', 'Water filtration system'],
                'time_needed': '1-4 hours with vehicle',
            },
            'fixed': {
                'description': 'Cannot be moved — value lost in evacuation',
                'examples': ['Real estate', 'Improvements/structures', 'Wells', 'Gardens/orchards',
                             'Buried caches (may be recoverable later)', 'Heavy equipment'],
            },
        },
        'recommendation': 'Maintain at least 3 months expenses in immediately_portable assets',
    })


@remaining_calcs_bp.route('/api/reference/credit-freeze')
def api_credit_freeze():
    """AT6: Credit freeze calendar and checklist."""
    return jsonify({
        'bureaus': {
            'equifax': {'phone': '800-685-1111', 'url': 'equifax.com/personal/credit-report-services/credit-freeze/', 'pin_required': True},
            'experian': {'phone': '888-397-3742', 'url': 'experian.com/freeze/center.html', 'pin_required': False},
            'transunion': {'phone': '888-909-8872', 'url': 'transunion.com/credit-freeze', 'pin_required': True},
            'innovis': {'phone': '800-540-2505', 'url': 'innovis.com/securityFreeze', 'pin_required': True},
            'nctue': {'phone': '866-349-5185', 'url': 'nctue.com', 'pin_required': False, 'note': 'Utility/telecom credit'},
        },
        'steps': [
            'Freeze all 5 bureaus (Equifax, Experian, TransUnion, Innovis, NCTUE)',
            'Save PINs/passwords securely (Shamir split recommended for PINs)',
            'Temporarily lift (thaw) when applying for credit — specify date range',
            'Re-freeze after application is processed',
            'Check annual credit reports at annualcreditreport.com',
        ],
        'free': True,
        'note': 'Credit freezes are free by federal law (2018 Economic Growth Act). No impact on credit score.',
    })


@remaining_calcs_bp.route('/api/calculators/income-diversification', methods=['POST'])
def api_income_diversification():
    """AT7: Income diversification tracker."""
    data = request.get_json() or {}
    streams = data.get('income_streams', [])

    if not streams:
        return jsonify({'error': 'income_streams array required (each: {name, monthly, type, risk})'}), 400

    total = sum(float(s.get('monthly', 0)) for s in streams)
    parsed = []
    for s in streams:
        monthly = float(s.get('monthly', 0))
        parsed.append({
            'name': s.get('name', ''),
            'monthly': monthly,
            'pct_of_total': round(monthly / total * 100, 1) if total > 0 else 0,
            'type': s.get('type', 'active'),  # active, passive, side, investment
            'risk': s.get('risk', 'medium'),  # low, medium, high
            'grid_resilient': s.get('grid_resilient', False),
        })

    # Concentration risk
    max_pct = max(p['pct_of_total'] for p in parsed) if parsed else 0
    concentration = 'dangerous' if max_pct > 80 else 'high' if max_pct > 60 else 'moderate' if max_pct > 40 else 'diversified'

    grid_resilient_pct = sum(p['monthly'] for p in parsed if p['grid_resilient']) / total * 100 if total > 0 else 0

    return jsonify({
        'total_monthly': round(total),
        'stream_count': len(parsed),
        'streams': parsed,
        'concentration_risk': concentration,
        'largest_stream_pct': round(max_pct, 1),
        'grid_resilient_pct': round(grid_resilient_pct, 1),
        'recommendation': 'No single stream should exceed 40% of total income. Maintain at least one grid-resilient stream.',
    })


# ═══════════════════════════════════════════════════════════════════
# Economy & Recovery — O2, O3
# ═══════════════════════════════════════════════════════════════════

@remaining_calcs_bp.route('/api/reference/hyperinflation')
def api_hyperinflation():
    """O2: Historical hyperinflation case studies."""
    return jsonify({
        'cases': {
            'weimar_germany_1923': {'peak_rate': '29,500% monthly', 'duration': '2 years', 'trigger': 'War reparations + money printing',
                                     'recovery': 'New currency (Rentenmark) backed by land/industrial assets'},
            'zimbabwe_2008': {'peak_rate': '79.6 billion% monthly', 'duration': '5 years', 'trigger': 'Land reform + money printing',
                               'recovery': 'Abandoned local currency, adopted USD/ZAR multi-currency'},
            'venezuela_2018': {'peak_rate': '130,000% annual', 'duration': 'Ongoing', 'trigger': 'Oil price collapse + fiscal policy',
                                'recovery': 'Partial dollarization, crypto adoption'},
            'argentina_recurring': {'peak_rate': '3,000% annual (1989)', 'duration': 'Recurring', 'trigger': 'Fiscal deficits + political instability',
                                     'recovery': 'Currency board (Convertibility Plan 1991) — later collapsed'},
        },
        'survival_strategies': [
            'Convert cash to tangible goods immediately upon onset',
            'Barter networks become primary economy within weeks',
            'Foreign currency (USD, EUR) holds value when local currency fails',
            'Precious metals maintain purchasing power across centuries',
            'Skills and labor become more valuable than paper currency',
            'Food production capability becomes ultimate insurance',
        ],
    })


@remaining_calcs_bp.route('/api/reference/blackstart-sop')
def api_blackstart_sop():
    """O3: Microgrid black-start SOP."""
    return jsonify({
        'procedure': [
            {'step': 1, 'action': 'Verify utility power is disconnected (transfer switch in GENERATOR position)',
             'safety': 'NEVER back-feed utility lines — electrocution risk to line workers'},
            {'step': 2, 'action': 'Start generator with NO load connected. Let stabilize 2-3 minutes.',
             'safety': 'Check oil, fuel, coolant before starting'},
            {'step': 3, 'action': 'Connect critical loads first: refrigeration, medical devices, communications',
             'safety': 'Do not exceed 80% of generator rated capacity'},
            {'step': 4, 'action': 'Add loads incrementally — wait 30 seconds between each',
             'safety': 'Watch voltage/frequency for sag (below 110V or 58Hz = overloaded)'},
            {'step': 5, 'action': 'If solar/battery system: start inverter, verify sync, then enable solar charging',
             'safety': 'Some inverters need grid-forming mode enabled for off-grid operation'},
            {'step': 6, 'action': 'Establish fuel management plan: consumption rate, remaining supply, resupply timeline',
             'safety': 'Never refuel a running generator'},
            {'step': 7, 'action': 'When utility power returns: shed loads, disconnect generator, switch transfer switch back',
             'safety': 'Allow generator to run unloaded 5 min before shutdown (cool-down)'},
        ],
        'load_priority': [
            '1. Medical devices (CPAP, O2 concentrator, refrigerated meds)',
            '2. Refrigeration/freezer (food preservation)',
            '3. Communications (radio, phone charging)',
            '4. Water pump (if well-dependent)',
            '5. Lighting (minimal)',
            '6. Heating/cooling (life safety dependent on climate)',
            '7. Everything else',
        ],
    })


# ═══════════════════════════════════════════════════════════════════
# OPSEC / Privacy — AE1-AE7
# ═══════════════════════════════════════════════════════════════════

@remaining_calcs_bp.route('/api/reference/opsec-checklists')
def api_opsec_checklists():
    """AE1-AE7: OPSEC and privacy reference material."""
    return jsonify({
        'gray_man_checklist': [
            'Clothing: neutral colors, no brands/logos, no military/tactical gear in public',
            'Vehicle: common make/model, no bumper stickers, no aftermarket modifications visible',
            'Behavior: match pace and demeanor of crowd, no scanning/counter-surveillance indicators',
            'Communication: no discussing preps in public, limit social media exposure',
            'Home: no visible antennas, generators, or stockpiles from street view',
            'Shopping: vary stores, pay cash for sensitive items, no loyalty cards',
        ],
        'social_footprint_audit': [
            'Google your name + city — what comes up?',
            'Check all social media privacy settings',
            'Remove home address from data broker sites (DeleteMe, Privacy Duck)',
            'Google reverse-image search your profile photos',
            'Check voter registration records (often public)',
            'Review property tax records (county assessor — public)',
            'Search court records for your name',
            'Check Have I Been Pwned for email breaches',
        ],
        'address_privacy': [
            'PO Box or UPS Store mailbox for all deliveries',
            'LLC or trust for property ownership (hides name from tax records)',
            'Registered agent for business filings',
            'Remove from whitepages, spokeo, been verified, intellius',
            'Opt out of data brokers quarterly (they re-add you)',
        ],
        'vehicle_profile_audit': [
            'No identifying bumper stickers or decals',
            'No aftermarket accessories that indicate interests (gun racks, ham antennas)',
            'License plate frames: remove dealer frames (identifies where you shop)',
            'Park in garage when possible',
            'Consider a common vehicle color (white, black, silver = 60% of all cars)',
        ],
        'compartmentalization': [
            'Separate email addresses for: personal, financial, prepping, public',
            'Separate phone numbers: personal, public-facing, burner for sensitive',
            'Don\'t cross-contaminate: never log into prep accounts from work network',
            'VPN for all prep-related browsing',
            'Separate browsers or profiles for each compartment',
        ],
    })


# ═══════════════════════════════════════════════════════════════════
# Health & Family remaining — CISM, Grief
# ═══════════════════════════════════════════════════════════════════

@remaining_calcs_bp.route('/api/reference/cism-debrief')
def api_cism_debrief():
    """CISM Critical Incident Stress Management debrief template."""
    return jsonify({
        'model': 'Mitchell Model (CISD) — 7 Phases',
        'phases': [
            {'phase': 1, 'name': 'Introduction', 'duration': '5 min',
             'facilitator_script': 'Welcome. This is a confidential debriefing. Nothing said here leaves this room. This is NOT an investigation or critique. Purpose: process what happened together.'},
            {'phase': 2, 'name': 'Fact Phase', 'duration': '10-15 min',
             'prompt': 'What happened? Walk us through the event from your perspective. What did you see, hear, do?'},
            {'phase': 3, 'name': 'Thought Phase', 'duration': '10 min',
             'prompt': 'What was your first thought when you realized what was happening?'},
            {'phase': 4, 'name': 'Reaction Phase', 'duration': '15-20 min',
             'prompt': 'What was the worst part for you personally? What image or moment stays with you?'},
            {'phase': 5, 'name': 'Symptom Phase', 'duration': '10 min',
             'prompt': 'Have you noticed any changes since the event? Sleep, appetite, concentration, irritability, flashbacks?'},
            {'phase': 6, 'name': 'Teaching Phase', 'duration': '10 min',
             'facilitator_script': 'What you\'re experiencing is a NORMAL reaction to an ABNORMAL event. Common reactions include: sleep disturbance, hypervigilance, emotional numbness, irritability, difficulty concentrating. These typically resolve in 2-4 weeks.'},
            {'phase': 7, 'name': 'Re-entry Phase', 'duration': '5 min',
             'facilitator_script': 'Summarize key themes. Remind: seek help if symptoms persist beyond 4 weeks. Buddy system check-ins. Next gathering date.'},
        ],
        'when_to_use': 'Within 24-72 hours of a critical incident. NOT during the event.',
        'who_facilitates': 'Trained peer support member or mental health professional preferred. Any trusted leader in austere conditions.',
        'contraindications': ['Active crisis (handle safety first)', 'Less than 24 hours post-event (too raw)',
                               'Perpetrator present', 'Mandatory participation (must be voluntary)'],
    })


@remaining_calcs_bp.route('/api/reference/grief-protocol')
def api_grief_protocol():
    """Age-banded grief/loss explainer cards."""
    return jsonify({
        'age_bands': {
            'toddler_2_4': {
                'understanding': 'Death is like sleeping or going away. No concept of permanence.',
                'reactions': ['Regression (bedwetting, thumb-sucking)', 'Clingy behavior', 'Sleep disruption', 'Repetitive questions'],
                'approach': ['Use simple, concrete language: "died" not "passed away" or "lost"',
                             'Maintain routines — predictability is security',
                             'Allow comfort objects', 'Expect them to ask the same questions repeatedly — answer patiently each time'],
            },
            'child_5_9': {
                'understanding': 'Beginning to understand permanence. May think death is contagious or their fault.',
                'reactions': ['Magical thinking (I caused this)', 'Fear of own death or parent death', 'Anger', 'School problems'],
                'approach': ['Reassure: "You did not cause this. Nothing you did or didn\'t do made this happen"',
                             'Answer questions honestly but age-appropriately',
                             'Allow them to attend memorial services (their choice)',
                             'Monitor for prolonged behavioral changes (>6 weeks)'],
            },
            'preteen_10_13': {
                'understanding': 'Understands permanence. May intellectualize to avoid emotion.',
                'reactions': ['Withdrawal from family', 'Acting out', 'Peer comparison ("no one understands")', 'Academic decline'],
                'approach': ['Validate feelings without minimizing', 'Offer journaling or art as outlets',
                             'Don\'t force conversation — be available when they\'re ready',
                             'Watch for risk-taking behavior'],
            },
            'teen_14_18': {
                'understanding': 'Adult understanding of death. Heightened emotional intensity.',
                'reactions': ['Existential questioning', 'Risk-taking', 'Substance use risk', 'Social withdrawal OR intense socializing'],
                'approach': ['Treat as a near-adult — include in decisions', 'Acknowledge their grief is real and valid',
                             'Watch for signs of depression vs normal grief', 'Professional support if symptoms persist >4 weeks'],
            },
            'adult': {
                'understanding': 'Full understanding. Prior losses may compound.',
                'reactions': ['Varies widely by individual', 'Physical symptoms (fatigue, appetite changes, chest pain)',
                              'Complicated grief if multiple losses in short period'],
                'approach': ['No timeline for grief — "move on" is harmful', 'Buddy check-ins weekly for first month',
                             'Practical support (meals, childcare, chores) > words',
                             'Professional help if unable to function after 6 weeks'],
            },
        },
        'universal_rules': [
            'Say "died" — not "passed", "lost", "went to sleep", "in a better place"',
            'Don\'t say "I know how you feel" — you don\'t',
            'Don\'t say "at least they\'re not suffering" — minimizes grief',
            'DO say: "I\'m sorry. I\'m here. What do you need?"',
            'Presence > words. Sitting silently together is powerful.',
        ],
    })
