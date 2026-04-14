"""Nutrition database — USDA FoodData search, inventory linking, and analysis."""

import json
import logging
from flask import Blueprint, request, jsonify
from db import get_db, db_session, log_activity

nutrition_bp = Blueprint('nutrition', __name__)
_log = logging.getLogger('nomad.nutrition')


# ─── Search foods ────────────────────────────────────────────────

@nutrition_bp.route('/api/nutrition/search')
def api_nutrition_search():
    q = request.args.get('q', '').strip()
    limit = min(int(request.args.get('limit', 25)), 100)
    group = request.args.get('group', '')

    if not q and not group:
        return jsonify([])

    with db_session() as db:
        if q and group:
            rows = db.execute(
                '''SELECT * FROM nutrition_foods
                   WHERE description LIKE ? AND food_group = ?
                   ORDER BY description LIMIT ?''',
                (f'%{q}%', group, limit)
            ).fetchall()
        elif q:
            rows = db.execute(
                '''SELECT * FROM nutrition_foods
                   WHERE description LIKE ?
                   ORDER BY description LIMIT ?''',
                (f'%{q}%', limit)
            ).fetchall()
        else:
            rows = db.execute(
                '''SELECT * FROM nutrition_foods
                   WHERE food_group = ?
                   ORDER BY description LIMIT ?''',
                (group, limit)
            ).fetchall()

    return jsonify([dict(r) for r in rows])


@nutrition_bp.route('/api/nutrition/lookup/<int:fdc_id>')
def api_nutrition_lookup(fdc_id):
    with db_session() as db:
        food = db.execute('SELECT * FROM nutrition_foods WHERE fdc_id = ?', (fdc_id,)).fetchone()
        if not food:
            return jsonify({'error': 'Food not found'}), 404

        nutrients = db.execute(
            'SELECT * FROM nutrition_nutrients WHERE fdc_id = ? ORDER BY nutrient_name',
            (fdc_id,)
        ).fetchall()

    result = dict(food)
    result['nutrients'] = [dict(n) for n in nutrients]
    return jsonify(result)


@nutrition_bp.route('/api/nutrition/food-groups')
def api_nutrition_food_groups():
    with db_session() as db:
        rows = db.execute(
            "SELECT DISTINCT food_group FROM nutrition_foods WHERE food_group != '' ORDER BY food_group"
        ).fetchall()
    return jsonify([r['food_group'] for r in rows])


# ─── Inventory ↔ Nutrition Link ──────────────────────────────────

@nutrition_bp.route('/api/nutrition/link', methods=['POST'])
def api_nutrition_link():
    data = request.get_json() or {}
    inv_id = data.get('inventory_id')
    fdc_id = data.get('fdc_id')
    if not inv_id or not fdc_id:
        return jsonify({'error': 'inventory_id and fdc_id required'}), 400

    with db_session() as db:
        # Verify inventory item exists
        if not db.execute('SELECT 1 FROM inventory WHERE id = ?', (inv_id,)).fetchone():
            return jsonify({'error': 'Inventory item not found'}), 404
        # Verify food exists
        food = db.execute('SELECT * FROM nutrition_foods WHERE fdc_id = ?', (fdc_id,)).fetchone()
        if not food:
            return jsonify({'error': 'Food not found'}), 404

        # Remove existing link if any
        db.execute('DELETE FROM inventory_nutrition_link WHERE inventory_id = ?', (inv_id,))

        db.execute('''
            INSERT INTO inventory_nutrition_link
            (inventory_id, fdc_id, servings_per_item, calories_per_serving,
             protein_per_serving, fat_per_serving, carbs_per_serving)
            VALUES (?,?,?,?,?,?,?)
        ''', (
            inv_id, fdc_id,
            data.get('servings_per_item', 1),
            food['calories'],
            food['protein_g'],
            food['fat_g'],
            food['carbs_g'],
        ))
        db.commit()

    log_activity('nutrition_linked', detail=f"Inventory #{inv_id} → FDC #{fdc_id}")
    return jsonify({'status': 'linked'}), 201


@nutrition_bp.route('/api/nutrition/link/<int:inv_id>', methods=['DELETE'])
def api_nutrition_unlink(inv_id):
    with db_session() as db:
        r = db.execute('DELETE FROM inventory_nutrition_link WHERE inventory_id = ?', (inv_id,))
        if r.rowcount == 0:
            return jsonify({'error': 'No link found'}), 404
        db.commit()
    return jsonify({'status': 'unlinked'})


@nutrition_bp.route('/api/nutrition/link/<int:inv_id>')
def api_nutrition_link_detail(inv_id):
    with db_session() as db:
        link = db.execute(
            '''SELECT l.*, f.description, f.food_group, f.serving_size, f.serving_unit
               FROM inventory_nutrition_link l
               JOIN nutrition_foods f ON l.fdc_id = f.fdc_id
               WHERE l.inventory_id = ?''',
            (inv_id,)
        ).fetchone()
    if not link:
        return jsonify({'linked': False})
    result = dict(link)
    result['linked'] = True
    return jsonify(result)


# ─── Nutrition Summary (across all linked inventory) ─────────────

@nutrition_bp.route('/api/nutrition/summary')
def api_nutrition_summary():
    """Calculate total nutrition across all food inventory with nutrition links."""
    with db_session() as db:
        rows = db.execute('''
            SELECT
                i.name, i.quantity,
                l.servings_per_item, l.calories_per_serving,
                l.protein_per_serving, l.fat_per_serving, l.carbs_per_serving
            FROM inventory i
            JOIN inventory_nutrition_link l ON i.id = l.inventory_id
            WHERE i.category IN ('food', 'Food', 'food storage', 'Food Storage', 'provisions')
               OR l.fdc_id IS NOT NULL
        ''').fetchall()

        # Read household size for person-days calculation
        household_row = db.execute(
            "SELECT value FROM settings WHERE key = 'household_size'"
        ).fetchone()
        household_size = int(household_row['value']) if household_row else 2

    total_calories = 0
    total_protein = 0
    total_fat = 0
    total_carbs = 0
    linked_items = 0

    for r in rows:
        qty = r['quantity'] or 1
        servings = r['servings_per_item'] or 1
        total_calories += qty * servings * (r['calories_per_serving'] or 0)
        total_protein += qty * servings * (r['protein_per_serving'] or 0)
        total_fat += qty * servings * (r['fat_per_serving'] or 0)
        total_carbs += qty * servings * (r['carbs_per_serving'] or 0)
        linked_items += 1

    daily_need = 2000
    person_days = total_calories / (household_size * daily_need) if household_size > 0 else 0

    return jsonify({
        'linked_items': linked_items,
        'household_size': household_size,
        'total_calories': round(total_calories, 1),
        'total_protein_g': round(total_protein, 1),
        'total_fat_g': round(total_fat, 1),
        'total_carbs_g': round(total_carbs, 1),
        'person_days_of_food': round(person_days, 1),
        'daily_calorie_assumption': daily_need,
    })


# ─── Micronutrient gap analysis ──────────────────────────────────

@nutrition_bp.route('/api/nutrition/gaps')
def api_nutrition_gaps():
    """Identify micronutrient gaps — vitamins/minerals with fewer than 30 days supply."""
    key_nutrients = {
        'Vitamin C': {'rda': 90, 'unit': 'mg'},
        'Vitamin D': {'rda': 15, 'unit': 'mcg'},
        'Vitamin A': {'rda': 900, 'unit': 'mcg'},
        'Iron': {'rda': 8, 'unit': 'mg'},
        'Calcium': {'rda': 1000, 'unit': 'mg'},
        'Zinc': {'rda': 11, 'unit': 'mg'},
        'Potassium': {'rda': 2600, 'unit': 'mg'},
        'Magnesium': {'rda': 420, 'unit': 'mg'},
        'Vitamin B-12': {'rda': 2.4, 'unit': 'mcg'},
        'Folate': {'rda': 400, 'unit': 'mcg'},
    }

    with db_session() as db:
        # Get all linked inventory FDC IDs with quantities
        links = db.execute('''
            SELECT l.fdc_id, i.quantity, l.servings_per_item
            FROM inventory_nutrition_link l
            JOIN inventory i ON i.id = l.inventory_id
        ''').fetchall()

        if not links:
            return jsonify({'has_data': False, 'gaps': []})

        household_row = db.execute(
            "SELECT value FROM settings WHERE key = 'household_size'"
        ).fetchone()
        household_size = max(int(household_row['value']) if household_row else 2, 1)

        # Aggregate nutrient totals from all linked items
        nutrient_totals = {}
        for link in links:
            nutrients = db.execute(
                'SELECT nutrient_name, amount, unit FROM nutrition_nutrients WHERE fdc_id = ?',
                (link['fdc_id'],)
            ).fetchall()
            qty = (link['quantity'] or 1) * (link['servings_per_item'] or 1)
            for n in nutrients:
                name = n['nutrient_name']
                if name in key_nutrients:
                    nutrient_totals[name] = nutrient_totals.get(name, 0) + (n['amount'] or 0) * qty

    gaps = []
    for name, info in key_nutrients.items():
        total = nutrient_totals.get(name, 0)
        daily_need = info['rda'] * household_size
        days_supply = total / daily_need if daily_need > 0 else 0
        status = 'green' if days_supply >= 30 else ('amber' if days_supply >= 7 else 'red')
        gaps.append({
            'nutrient': name,
            'total_amount': round(total, 1),
            'unit': info['unit'],
            'daily_need_per_person': info['rda'],
            'days_supply': round(days_supply, 1),
            'status': status,
        })

    gaps.sort(key=lambda x: x['days_supply'])
    return jsonify({'has_data': True, 'household_size': household_size, 'gaps': gaps})
