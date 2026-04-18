"""Meal planning, recipes, burn rate analysis, inventory audit, and standardization."""

import json
import logging
import math
from flask import Blueprint, request, jsonify
from db import db_session, log_activity
from web.blueprints import get_pagination

meal_planning_bp = Blueprint('meal_planning', __name__)
_log = logging.getLogger('nomad.meal_planning')


# ═══════ RECIPES CRUD ═══════════════════════════════════════════

@meal_planning_bp.route('/api/recipes')
def api_recipes_list():
    category = request.args.get('category', '')
    limit, offset = get_pagination()
    with db_session() as db:
        if category:
            rows = db.execute(
                'SELECT * FROM recipes WHERE category = ? ORDER BY name LIMIT ? OFFSET ?',
                (category, limit, offset)
            ).fetchall()
        else:
            rows = db.execute(
                'SELECT * FROM recipes ORDER BY name LIMIT ? OFFSET ?', (limit, offset)
            ).fetchall()
    return jsonify([_format_recipe(r) for r in rows])


@meal_planning_bp.route('/api/recipes/<int:rid>')
def api_recipe_detail(rid):
    with db_session() as db:
        recipe = db.execute('SELECT * FROM recipes WHERE id = ?', (rid,)).fetchone()
        if not recipe:
            return jsonify({'error': 'not found'}), 404
        ingredients = db.execute(
            'SELECT * FROM recipe_ingredients WHERE recipe_id = ? ORDER BY id', (rid,)
        ).fetchall()
    result = _format_recipe(recipe)
    result['ingredients'] = [dict(i) for i in ingredients]
    return jsonify(result)


@meal_planning_bp.route('/api/recipes', methods=['POST'])
def api_recipe_create():
    data = request.get_json() or {}
    if not data.get('name'):
        return jsonify({'error': 'Name required'}), 400

    tags = data.get('tags', [])
    if isinstance(tags, list):
        tags = json.dumps(tags)

    with db_session() as db:
        cur = db.execute('''
            INSERT INTO recipes (name, category, servings, prep_time_min, cook_time_min,
                                 method, instructions, calories_per_serving, tags, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        ''', (
            data['name'], data.get('category', 'meal'),
            data.get('servings', 4),
            data.get('prep_time_min', 0), data.get('cook_time_min', 0),
            data.get('method', ''), data.get('instructions', ''),
            data.get('calories_per_serving', 0), tags, data.get('notes', ''),
        ))
        recipe_id = cur.lastrowid

        for ing in data.get('ingredients', []):
            if not ing.get('name'):
                continue
            db.execute('''
                INSERT INTO recipe_ingredients (recipe_id, inventory_id, fdc_id, name, quantity, unit, optional)
                VALUES (?,?,?,?,?,?,?)
            ''', (recipe_id, ing.get('inventory_id'), ing.get('fdc_id'),
                  ing['name'], ing.get('quantity', 1), ing.get('unit', ''),
                  1 if ing.get('optional') else 0))
        db.commit()

    log_activity('recipe_created', detail=f"Created recipe: {data['name']}")
    return jsonify({'status': 'created', 'id': recipe_id}), 201


@meal_planning_bp.route('/api/recipes/<int:rid>', methods=['PUT'])
def api_recipe_update(rid):
    data = request.get_json() or {}
    allowed = ['name', 'category', 'servings', 'prep_time_min', 'cook_time_min',
               'method', 'instructions', 'calories_per_serving', 'notes']
    updates = []
    values = []
    for key in allowed:
        if key in data:
            updates.append(f'{key} = ?')
            values.append(data[key])
    if 'tags' in data:
        tags = data['tags']
        if isinstance(tags, list):
            tags = json.dumps(tags)
        updates.append('tags = ?')
        values.append(tags)
    if not updates:
        return jsonify({'error': 'No fields to update'}), 400

    with db_session() as db:
        if not db.execute('SELECT 1 FROM recipes WHERE id = ?', (rid,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        updates.append("updated_at = datetime('now')")
        values.append(rid)
        db.execute(f"UPDATE recipes SET {', '.join(updates)} WHERE id = ?", values)

        if 'ingredients' in data:
            db.execute('DELETE FROM recipe_ingredients WHERE recipe_id = ?', (rid,))
            for ing in data['ingredients']:
                if not ing.get('name'):
                    continue
                db.execute('''
                    INSERT INTO recipe_ingredients (recipe_id, inventory_id, fdc_id, name, quantity, unit, optional)
                    VALUES (?,?,?,?,?,?,?)
                ''', (rid, ing.get('inventory_id'), ing.get('fdc_id'),
                      ing['name'], ing.get('quantity', 1), ing.get('unit', ''),
                      1 if ing.get('optional') else 0))
        db.commit()
    return jsonify({'status': 'updated'})


@meal_planning_bp.route('/api/recipes/<int:rid>', methods=['DELETE'])
def api_recipe_delete(rid):
    with db_session() as db:
        r = db.execute('DELETE FROM recipes WHERE id = ?', (rid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


# ═══════ MEALS REMAINING CALCULATOR ═════════════════════════════

@meal_planning_bp.route('/api/recipes/meals-remaining')
def api_meals_remaining():
    """For each recipe, calculate how many full batches can be made from current inventory."""
    with db_session() as db:
        recipes = db.execute('SELECT * FROM recipes ORDER BY name').fetchall()
        result = []
        for recipe in recipes:
            ingredients = db.execute(
                'SELECT * FROM recipe_ingredients WHERE recipe_id = ?', (recipe['id'],)
            ).fetchall()
            if not ingredients:
                continue

            batches_possible = float('inf')
            ingredient_status = []
            for ing in ingredients:
                if ing['optional']:
                    ingredient_status.append({
                        'name': ing['name'], 'needed': ing['quantity'],
                        'available': None, 'optional': True, 'batches': None
                    })
                    continue

                available = 0
                if ing['inventory_id']:
                    row = db.execute(
                        'SELECT quantity FROM inventory WHERE id = ?', (ing['inventory_id'],)
                    ).fetchone()
                    if row:
                        available = row['quantity'] or 0

                needed = ing['quantity'] or 1
                item_batches = available / needed if needed > 0 else 0
                batches_possible = min(batches_possible, item_batches)
                ingredient_status.append({
                    'name': ing['name'], 'needed': needed,
                    'available': available, 'optional': False,
                    'batches': round(item_batches, 1),
                })

            if batches_possible == float('inf'):
                batches_possible = 0

            result.append({
                'recipe_id': recipe['id'],
                'name': recipe['name'],
                'servings_per_batch': recipe['servings'],
                'batches_possible': math.floor(batches_possible),
                'total_servings': math.floor(batches_possible) * recipe['servings'],
                'ingredients': ingredient_status,
            })

        result.sort(key=lambda x: x['batches_possible'], reverse=True)
    return jsonify(result)


# ═══════ DUE SCORE (cook what expires soonest) ══════════════════

@meal_planning_bp.route('/api/recipes/due-score')
def api_recipes_due_score():
    """Rank recipes by urgency — prioritize those using soon-to-expire ingredients."""
    with db_session() as db:
        recipes = db.execute('SELECT * FROM recipes ORDER BY name').fetchall()
        scored = []
        for recipe in recipes:
            ingredients = db.execute(
                'SELECT ri.*, i.expiration, i.quantity FROM recipe_ingredients ri '
                'LEFT JOIN inventory i ON ri.inventory_id = i.id '
                'WHERE ri.recipe_id = ?', (recipe['id'],)
            ).fetchall()

            if not ingredients:
                continue

            min_days_to_expire = float('inf')
            has_expiring = False
            for ing in ingredients:
                if ing['expiration']:
                    try:
                        from datetime import datetime
                        exp = datetime.strptime(ing['expiration'], '%Y-%m-%d')
                        days = (exp - datetime.now()).days
                        if days < min_days_to_expire:
                            min_days_to_expire = days
                            has_expiring = True
                    except (ValueError, TypeError):
                        pass

            if not has_expiring:
                continue

            scored.append({
                'recipe_id': recipe['id'],
                'name': recipe['name'],
                'days_to_soonest_expiry': min_days_to_expire if min_days_to_expire != float('inf') else None,
                'urgency': 'critical' if min_days_to_expire <= 7 else ('warning' if min_days_to_expire <= 30 else 'ok'),
            })

        scored.sort(key=lambda x: x['days_to_soonest_expiry'] if x['days_to_soonest_expiry'] is not None else 9999)
    return jsonify(scored)


# ═══════ BURN RATE ANALYSIS ═════════════════════════════════════

@meal_planning_bp.route('/api/inventory/burn-rates')
def api_inventory_burn_rates():
    """Calculate actual consumption rates from consumption_log and project durations."""
    try:
        days = max(1, min(3650, int(request.args.get('days', 90))))
    except (TypeError, ValueError):
        days = 90

    with db_session() as db:
        # Aggregate consumption over the window. The consumption_log table
        # stores the usage in the `amount` column; the prior version of
        # this query referenced cl.quantity which does not exist, so every
        # call to /api/inventory/burn-rates returned 500 until v7.36.
        rows = db.execute('''
            SELECT cl.inventory_id, i.name, i.quantity as current_qty, i.category,
                   SUM(cl.amount) as total_consumed,
                   COUNT(cl.id) as consumption_events
            FROM consumption_log cl
            JOIN inventory i ON cl.inventory_id = i.id
            WHERE cl.consumed_at >= datetime('now', ?)
            GROUP BY cl.inventory_id
            ORDER BY total_consumed DESC
        ''', (f'-{days} days',)).fetchall()

    result = []
    for r in rows:
        consumed = r['total_consumed'] or 0
        daily_rate = consumed / days if days > 0 else 0
        current = r['current_qty'] or 0
        days_remaining = current / daily_rate if daily_rate > 0 else None
        reorder_point = daily_rate * 14  # 2-week lead time

        result.append({
            'inventory_id': r['inventory_id'],
            'name': r['name'],
            'category': r['category'],
            'current_qty': current,
            'total_consumed': round(consumed, 1),
            'daily_rate': round(daily_rate, 2),
            'days_remaining': round(days_remaining, 1) if days_remaining else None,
            'reorder_point': round(reorder_point, 1),
            'below_reorder': current < reorder_point if reorder_point > 0 else False,
            'consumption_events': r['consumption_events'],
        })

    return jsonify({'window_days': days, 'items': result})


# ═══════ STANDARDIZATION ADVISOR ════════════════════════════════

@meal_planning_bp.route('/api/inventory/standardization')
def api_inventory_standardization():
    """Identify categories with too many variants and suggest consolidation."""
    with db_session() as db:
        # Find categories with multiple distinct sub-types
        rows = db.execute('''
            SELECT category, COUNT(DISTINCT name) as variants, SUM(quantity) as total_qty
            FROM inventory
            WHERE category != '' AND quantity > 0
            GROUP BY category
            HAVING variants >= 3
            ORDER BY variants DESC
        ''').fetchall()

    advisories = []
    for r in rows:
        advisories.append({
            'category': r['category'],
            'variant_count': r['variants'],
            'total_quantity': r['total_qty'],
            'advice': f"You have {r['variants']} different items in '{r['category']}'. "
                      f"Consider standardizing to reduce complexity and simplify resupply.",
        })

    return jsonify(advisories)


# ═══════ INVENTORY AUDIT ════════════════════════════════════════

@meal_planning_bp.route('/api/inventory/audit/start', methods=['POST'])
def api_inventory_audit_start():
    """Start a new inventory audit — creates audit run with all items to verify."""
    with db_session() as db:
        items = db.execute(
            'SELECT id, quantity FROM inventory WHERE quantity > 0 ORDER BY category, name'
        ).fetchall()

        cur = db.execute(
            "INSERT INTO inventory_audits (total_items) VALUES (?)",
            (len(items),)
        )
        audit_id = cur.lastrowid

        for item in items:
            db.execute(
                '''INSERT INTO inventory_audit_items (audit_id, inventory_id, expected_qty)
                   VALUES (?,?,?)''',
                (audit_id, item['id'], item['quantity'])
            )
        db.commit()

    log_activity('inventory_audit_started', detail=f"Audit #{audit_id} with {len(items)} items")
    return jsonify({'status': 'started', 'audit_id': audit_id, 'total_items': len(items)}), 201


@meal_planning_bp.route('/api/inventory/audit/<int:audit_id>')
def api_inventory_audit_detail(audit_id):
    with db_session() as db:
        audit = db.execute('SELECT * FROM inventory_audits WHERE id = ?', (audit_id,)).fetchone()
        if not audit:
            return jsonify({'error': 'not found'}), 404
        items = db.execute('''
            SELECT ai.*, i.name, i.category
            FROM inventory_audit_items ai
            JOIN inventory i ON ai.inventory_id = i.id
            WHERE ai.audit_id = ?
            ORDER BY i.category, i.name
        ''', (audit_id,)).fetchall()
    result = dict(audit)
    result['items'] = [dict(i) for i in items]
    return jsonify(result)


@meal_planning_bp.route('/api/inventory/audit/<int:audit_id>/verify', methods=['POST'])
def api_inventory_audit_verify(audit_id):
    """Verify a single item in an audit."""
    data = request.get_json() or {}
    item_id = data.get('item_id')
    actual_qty = data.get('actual_qty')
    if item_id is None or actual_qty is None:
        return jsonify({'error': 'item_id and actual_qty required'}), 400
    # Coerce up front — float(non-numeric) would otherwise raise 500.
    try:
        actual_qty_val = float(actual_qty)
        item_id_val = int(item_id)
    except (TypeError, ValueError):
        return jsonify({'error': 'item_id must be int, actual_qty must be numeric'}), 400

    with db_session() as db:
        row = db.execute(
            'SELECT * FROM inventory_audit_items WHERE id = ? AND audit_id = ?',
            (item_id_val, audit_id)
        ).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404

        try:
            expected = float(row['expected_qty'])
        except (TypeError, ValueError):
            expected = 0.0
        discrepancy = abs(actual_qty_val - expected) > 0.01
        db.execute('''
            UPDATE inventory_audit_items
            SET actual_qty = ?, verified = 1, discrepancy_notes = ?
            WHERE id = ?
        ''', (actual_qty_val, data.get('notes', '') if discrepancy else '', item_id_val))

        # Update audit totals
        verified = db.execute(
            'SELECT COUNT(*) as cnt FROM inventory_audit_items WHERE audit_id = ? AND verified = 1',
            (audit_id,)
        ).fetchone()['cnt']
        discrepancies = db.execute(
            'SELECT COUNT(*) as cnt FROM inventory_audit_items WHERE audit_id = ? AND verified = 1 AND actual_qty != expected_qty',
            (audit_id,)
        ).fetchone()['cnt']
        db.execute(
            'UPDATE inventory_audits SET verified = ?, discrepancies = ? WHERE id = ?',
            (verified, discrepancies, audit_id)
        )
        db.commit()

    return jsonify({'status': 'verified', 'discrepancy': discrepancy})


@meal_planning_bp.route('/api/inventory/audit/<int:audit_id>/complete', methods=['POST'])
def api_inventory_audit_complete(audit_id):
    """Complete an audit and optionally apply corrections to inventory quantities."""
    data = request.get_json() or {}
    apply_corrections = data.get('apply_corrections', False)

    with db_session() as db:
        audit = db.execute('SELECT * FROM inventory_audits WHERE id = ?', (audit_id,)).fetchone()
        if not audit:
            return jsonify({'error': 'not found'}), 404

        if apply_corrections:
            items = db.execute(
                'SELECT * FROM inventory_audit_items WHERE audit_id = ? AND verified = 1 AND actual_qty IS NOT NULL',
                (audit_id,)
            ).fetchall()
            for item in items:
                if abs(float(item['actual_qty']) - float(item['expected_qty'])) > 0.01:
                    db.execute(
                        'UPDATE inventory SET quantity = ? WHERE id = ?',
                        (item['actual_qty'], item['inventory_id'])
                    )

        db.execute(
            "UPDATE inventory_audits SET status = 'completed', completed_at = datetime('now') WHERE id = ?",
            (audit_id,)
        )
        db.commit()

    log_activity('inventory_audit_completed',
                 detail=f"Audit #{audit_id} complete, corrections={'applied' if apply_corrections else 'skipped'}")
    return jsonify({'status': 'completed', 'corrections_applied': apply_corrections})


# ═══════ SUBSTITUTES ════════════════════════════════════════════

@meal_planning_bp.route('/api/inventory/substitutes/<int:inv_id>')
def api_inventory_substitutes(inv_id):
    with db_session() as db:
        rows = db.execute('''
            SELECT s.*, i.name as substitute_name, i.category, i.quantity
            FROM inventory_substitutes s
            JOIN inventory i ON s.substitute_id = i.id
            WHERE s.inventory_id = ?
        ''', (inv_id,)).fetchall()
    return jsonify([dict(r) for r in rows])


@meal_planning_bp.route('/api/inventory/substitutes', methods=['POST'])
def api_inventory_substitute_create():
    data = request.get_json() or {}
    inv_id = data.get('inventory_id')
    sub_id = data.get('substitute_id')
    if not inv_id or not sub_id:
        return jsonify({'error': 'inventory_id and substitute_id required'}), 400
    if inv_id == sub_id:
        return jsonify({'error': 'Cannot substitute with self'}), 400

    with db_session() as db:
        db.execute('''
            INSERT OR REPLACE INTO inventory_substitutes (inventory_id, substitute_id, ratio, notes)
            VALUES (?,?,?,?)
        ''', (inv_id, sub_id, data.get('ratio', 1.0), data.get('notes', '')))
        db.commit()
    return jsonify({'status': 'created'}), 201


@meal_planning_bp.route('/api/inventory/substitutes/<int:sid>', methods=['DELETE'])
def api_inventory_substitute_delete(sid):
    with db_session() as db:
        r = db.execute('DELETE FROM inventory_substitutes WHERE id = ?', (sid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


# ═══════ HELPERS ════════════════════════════════════════════════

def _format_recipe(row):
    d = dict(row)
    try:
        d['tags'] = json.loads(d.get('tags', '[]'))
    except (json.JSONDecodeError, TypeError):
        d['tags'] = []
    return d
