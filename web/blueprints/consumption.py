"""Consumption profiles — per-person caloric needs, what-if scenarios, macro analysis."""

import json
import logging
from flask import Blueprint, request, jsonify
from db import db_session, log_activity
from web.blueprints import get_pagination

consumption_bp = Blueprint('consumption', __name__)
_log = logging.getLogger('nomad.consumption')

# ─── Profile type defaults ────────────────────────────────────────

PROFILE_DEFAULTS = {
    'adult_male_sedentary':    {'calories': 2000, 'water_gal': 0.5},
    'adult_male_moderate':     {'calories': 2400, 'water_gal': 0.65},
    'adult_male_active':       {'calories': 3000, 'water_gal': 0.85},
    'adult_male_heavy_labor':  {'calories': 3500, 'water_gal': 1.0},
    'adult_female_sedentary':  {'calories': 1600, 'water_gal': 0.45},
    'adult_female_moderate':   {'calories': 2000, 'water_gal': 0.55},
    'adult_female_active':     {'calories': 2400, 'water_gal': 0.7},
    'adult_female_heavy_labor':{'calories': 3000, 'water_gal': 0.85},
    'child_1_3':               {'calories': 1000, 'water_gal': 0.25},
    'child_4_8':               {'calories': 1400, 'water_gal': 0.35},
    'child_9_13':              {'calories': 1800, 'water_gal': 0.45},
    'teen_14_18':              {'calories': 2200, 'water_gal': 0.55},
    'infant':                  {'calories': 800,  'water_gal': 0.2},
    'elderly':                 {'calories': 1800, 'water_gal': 0.45},
    'pregnant':                {'calories': 2400, 'water_gal': 0.6},
    'nursing':                 {'calories': 2700, 'water_gal': 0.7},
}

DIETARY_RESTRICTION_OPTIONS = [
    'gluten_free', 'dairy_free', 'nut_free', 'egg_free', 'soy_free',
    'vegetarian', 'vegan', 'kosher', 'halal', 'low_sodium',
    'diabetic', 'renal_diet', 'keto', 'paleo',
]

_CONSUMPTION_PROFILES_ALLOWED_FIELDS = frozenset({'name', 'profile_type', 'age_years', 'weight_lb', 'activity_level',
                                                   'daily_calories', 'daily_water_gal', 'notes'})


# ─── CRUD ─────────────────────────────────────────────────────────

@consumption_bp.route('/api/consumption/profiles')
def api_profiles_list():
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM consumption_profiles ORDER BY name LIMIT ? OFFSET ?',
            get_pagination()
        ).fetchall()
    return jsonify([_format_profile(r) for r in rows])


@consumption_bp.route('/api/consumption/profiles/<int:pid>')
def api_profile_detail(pid):
    with db_session() as db:
        row = db.execute('SELECT * FROM consumption_profiles WHERE id = ?', (pid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(_format_profile(row))


@consumption_bp.route('/api/consumption/profiles', methods=['POST'])
def api_profile_create():
    data = request.get_json() or {}
    if not data.get('name'):
        return jsonify({'error': 'Name required'}), 400

    ptype = data.get('profile_type', 'adult_male')
    activity = data.get('activity_level', 'moderate')
    key = f"{ptype}_{activity}"
    defaults = PROFILE_DEFAULTS.get(key, {'calories': 2000, 'water_gal': 0.5})

    restrictions = data.get('dietary_restrictions', [])
    if isinstance(restrictions, list):
        restrictions = json.dumps(restrictions)

    with db_session() as db:
        db.execute('''
            INSERT INTO consumption_profiles
            (name, profile_type, age_years, weight_lb, activity_level,
             daily_calories, daily_water_gal, dietary_restrictions, notes)
            VALUES (?,?,?,?,?,?,?,?,?)
        ''', (
            data['name'],
            ptype,
            data.get('age_years', 30),
            data.get('weight_lb', 0),
            activity,
            data.get('daily_calories', defaults['calories']),
            data.get('daily_water_gal', defaults['water_gal']),
            restrictions,
            data.get('notes', ''),
        ))
        db.commit()

    log_activity('consumption_profile_created', detail=f"Created profile: {data['name']}")
    return jsonify({'status': 'created'}), 201


@consumption_bp.route('/api/consumption/profiles/<int:pid>', methods=['PUT'])
def api_profile_update(pid):
    data = request.get_json() or {}
    allowed = _CONSUMPTION_PROFILES_ALLOWED_FIELDS
    updates = []
    values = []
    for key in allowed:
        if key in data:
            updates.append(f'{key} = ?')
            values.append(data[key])
    if 'dietary_restrictions' in data:
        restrictions = data['dietary_restrictions']
        if isinstance(restrictions, list):
            restrictions = json.dumps(restrictions)
        updates.append('dietary_restrictions = ?')
        values.append(restrictions)

    if not updates:
        return jsonify({'error': 'No fields to update'}), 400

    with db_session() as db:
        if not db.execute('SELECT 1 FROM consumption_profiles WHERE id = ?', (pid,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        updates.append("updated_at = datetime('now')")
        values.append(pid)
        db.execute(
            f"UPDATE consumption_profiles SET {', '.join(updates)} WHERE id = ?",
            values
        )
        db.commit()
    return jsonify({'status': 'updated'})


@consumption_bp.route('/api/consumption/profiles/<int:pid>', methods=['DELETE'])
def api_profile_delete(pid):
    with db_session() as db:
        r = db.execute('DELETE FROM consumption_profiles WHERE id = ?', (pid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


# ─── Profile type defaults (for UI dropdowns) ────────────────────

@consumption_bp.route('/api/consumption/defaults')
def api_profile_defaults():
    return jsonify({
        'profile_types': list(PROFILE_DEFAULTS.keys()),
        'defaults': PROFILE_DEFAULTS,
        'dietary_options': DIETARY_RESTRICTION_OPTIONS,
    })


# ─── Household summary (aggregated across all profiles) ──────────

@consumption_bp.route('/api/consumption/summary')
def api_consumption_summary():
    with db_session() as db:
        profiles = db.execute('SELECT * FROM consumption_profiles ORDER BY name').fetchall()

        # If no profiles, fall back to household_size setting
        if not profiles:
            household_row = db.execute(
                "SELECT value FROM settings WHERE key = 'household_size'"
            ).fetchone()
            # int(household_row['value']) would crash if the value is '', None,
            # or non-numeric. Guard with try/except and a sane default.
            try:
                household_size = max(1, int(household_row['value'])) if household_row else 2
            except (TypeError, ValueError):
                household_size = 2
            return jsonify({
                'source': 'setting',
                'people': household_size,
                'total_daily_calories': household_size * 2000,
                'total_daily_water_gal': household_size * 0.5,
                'profiles': [],
            })

    total_cal = sum(p['daily_calories'] or 2000 for p in profiles)
    total_water = sum(p['daily_water_gal'] or 0.5 for p in profiles)

    return jsonify({
        'source': 'profiles',
        'people': len(profiles),
        'total_daily_calories': total_cal,
        'total_daily_water_gal': round(total_water, 2),
        'profiles': [_format_profile(p) for p in profiles],
    })


# ─── What-if scenario calculator ─────────────────────────────────

@consumption_bp.route('/api/consumption/what-if', methods=['POST'])
def api_consumption_what_if():
    """Calculate supply duration with hypothetical group changes."""
    data = request.get_json() or {}
    extra_adults = data.get('extra_adults', 0)
    extra_children = data.get('extra_children', 0)
    activity_override = data.get('activity_level', None)

    with db_session() as db:
        profiles = db.execute('SELECT * FROM consumption_profiles').fetchall()

        # Nutrition totals
        nutrition = db.execute('''
            SELECT
                COALESCE(SUM(i.quantity * l.servings_per_item * l.calories_per_serving), 0) as total_cal
            FROM inventory i
            JOIN inventory_nutrition_link l ON i.id = l.inventory_id
        ''').fetchone()
        total_food_cal = nutrition['total_cal'] or 0

        # Water totals
        water = db.execute(
            'SELECT COALESCE(SUM(current_gallons), 0) as total FROM water_storage'
        ).fetchone()
        total_water_gal = water['total'] or 0

        # Current daily need from profiles
        if profiles:
            daily_cal_need = sum(p['daily_calories'] or 2000 for p in profiles)
            daily_water_need = sum(p['daily_water_gal'] or 0.5 for p in profiles)
        else:
            household_row = db.execute(
                "SELECT value FROM settings WHERE key = 'household_size'"
            ).fetchone()
            h = int(household_row['value']) if household_row else 2
            daily_cal_need = h * 2000
            daily_water_need = h * 0.5

    # Add hypothetical people
    extra_cal_per_adult = 2400 if activity_override == 'active' else 2000
    extra_cal_per_child = 1400
    extra_water_per_adult = 0.65
    extra_water_per_child = 0.35

    scenario_daily_cal = daily_cal_need + (extra_adults * extra_cal_per_adult) + (extra_children * extra_cal_per_child)
    scenario_daily_water = daily_water_need + (extra_adults * extra_water_per_adult) + (extra_children * extra_water_per_child)

    baseline_food_days = total_food_cal / daily_cal_need if daily_cal_need > 0 else 0
    baseline_water_days = total_water_gal / daily_water_need if daily_water_need > 0 else 0
    scenario_food_days = total_food_cal / scenario_daily_cal if scenario_daily_cal > 0 else 0
    scenario_water_days = total_water_gal / scenario_daily_water if scenario_daily_water > 0 else 0

    return jsonify({
        'baseline': {
            'food_days': round(baseline_food_days, 1),
            'water_days': round(baseline_water_days, 1),
            'daily_calories': daily_cal_need,
            'daily_water_gal': round(daily_water_need, 2),
        },
        'scenario': {
            'extra_adults': extra_adults,
            'extra_children': extra_children,
            'food_days': round(scenario_food_days, 1),
            'water_days': round(scenario_water_days, 1),
            'daily_calories': scenario_daily_cal,
            'daily_water_gal': round(scenario_daily_water, 2),
        },
        'total_food_calories': round(total_food_cal, 0),
        'total_water_gallons': round(total_water_gal, 1),
    })


# ─── Caloric Gap Analysis (P2-27) ─────────────────────────────────

@consumption_bp.route('/api/consumption/caloric-gap')
def api_caloric_gap():
    """Compare stored calories vs daily need per food category."""
    with db_session() as db:
        # Daily caloric need from profiles or household_size
        profiles = db.execute('SELECT * FROM consumption_profiles').fetchall()
        if profiles:
            daily_cal_need = sum(p['daily_calories'] or 2000 for p in profiles)
            daily_water_need = sum(p['daily_water_gal'] or 0.5 for p in profiles)
            people = len(profiles)
        else:
            row = db.execute("SELECT value FROM settings WHERE key = 'household_size'").fetchone()
            try:
                people = max(1, int(row['value'])) if row else 2
            except (TypeError, ValueError):
                people = 2
            daily_cal_need = people * 2000
            daily_water_need = people * 0.5

        # Per-category caloric inventory
        cats = db.execute('''
            SELECT i.category,
                   COUNT(*) as items,
                   COALESCE(SUM(i.quantity), 0) as total_qty,
                   COALESCE(SUM(i.quantity * COALESCE(l.servings_per_item, 1) * COALESCE(l.calories_per_serving, 0)), 0) as total_cal
            FROM inventory i
            LEFT JOIN inventory_nutrition_link l ON i.id = l.inventory_id
            GROUP BY i.category
            ORDER BY total_cal DESC
        ''').fetchall()

        total_stored_cal = sum(c['total_cal'] for c in cats)
        coverage_days = round(total_stored_cal / daily_cal_need, 1) if daily_cal_need > 0 else 0

        # Water
        water_row = db.execute('SELECT COALESCE(SUM(current_gallons), 0) as total FROM water_storage').fetchone()
        total_water = water_row['total'] or 0
        water_days = round(total_water / daily_water_need, 1) if daily_water_need > 0 else 0

        return jsonify({
            'people': people,
            'daily_calories_needed': daily_cal_need,
            'daily_water_gal_needed': round(daily_water_need, 2),
            'total_stored_calories': round(total_stored_cal),
            'total_water_gallons': round(total_water, 1),
            'food_coverage_days': coverage_days,
            'water_coverage_days': water_days,
            'gap_calories': max(0, round(daily_cal_need * 30 - total_stored_cal)),
            'gap_description': f'{"Surplus" if coverage_days >= 30 else f"Need {max(0, round(daily_cal_need * 30 - total_stored_cal)):,} more cal for 30-day coverage"}',
            'categories': [{
                'category': c['category'] or 'Uncategorized',
                'items': c['items'],
                'total_calories': round(c['total_cal']),
                'coverage_days': round(c['total_cal'] / daily_cal_need, 1) if daily_cal_need > 0 else 0,
            } for c in cats],
        })


# ─── Helpers ──────────────────────────────────────────────────────

def _format_profile(row):
    d = dict(row)
    try:
        d['dietary_restrictions'] = json.loads(d.get('dietary_restrictions', '[]'))
    except (json.JSONDecodeError, TypeError):
        d['dietary_restrictions'] = []
    return d
