"""Daily Living & Quality of Life — schedules, chores, clothing, sanitation,
morale tracking, sleep management, performance monitoring, and grid-down recipes."""

import json
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify
from db import db_session, log_activity
from web.blueprints import get_pagination

_log = logging.getLogger(__name__)

daily_living_bp = Blueprint('daily_living', __name__, url_prefix='/api/daily-living')

_DAILY_SCHEDULES_ALLOWED_FIELDS = frozenset({'name', 'schedule_type', 'description', 'assigned_to',
                                             'start_date', 'end_date', 'status'})
_CHORE_ASSIGNMENTS_ALLOWED_FIELDS = frozenset({'schedule_id', 'chore_name', 'category', 'assigned_to',
                                               'frequency', 'time_slot', 'duration_minutes', 'priority',
                                               'instructions', 'rotation_group', 'last_completed', 'status'})
_CLOTHING_INVENTORY_ALLOWED_FIELDS = frozenset({'person', 'item_name', 'category', 'size', 'quantity',
                                                'condition', 'season', 'warmth_rating', 'material',
                                                'location', 'notes'})
_SANITATION_SUPPLIES_ALLOWED_FIELDS = frozenset({'name', 'category', 'quantity', 'unit', 'min_stock',
                                                 'daily_usage_rate', 'persons_served', 'location',
                                                 'expiration_date', 'notes'})
_GRID_DOWN_RECIPES_ALLOWED_FIELDS = frozenset({'name', 'category', 'cooking_method', 'prep_time_minutes',
                                               'cook_time_minutes', 'servings', 'calories_per_serving',
                                               'protein_per_serving', 'instructions', 'water_required_ml',
                                               'fuel_required', 'rating', 'notes'})

# ─── Work/Rest Reference Data ──────────────────────────────────────────

WORK_REST_REFERENCE = {
    'light_work': {'work_minutes': 50, 'rest_minutes': 10, 'description': 'Light physical activity (camp tasks, cooking)'},
    'moderate_work': {'work_minutes': 40, 'rest_minutes': 20, 'description': 'Moderate physical activity (construction, hauling)'},
    'heavy_work': {'work_minutes': 30, 'rest_minutes': 30, 'description': 'Heavy physical activity (digging, chopping)'},
    'extreme_heat': {'work_minutes': 20, 'rest_minutes': 40, 'description': 'Any work in extreme heat (>100°F / 38°C)'},
    'extreme_cold': {'work_minutes': 40, 'rest_minutes': 20, 'description': 'Work in extreme cold (<0°F / -18°C)'},
    'night_ops': {'work_minutes': 45, 'rest_minutes': 15, 'description': 'Night operations with reduced visibility'},
}

# ─── Seed Recipes ───────────────────────────────────────────────────────

SEED_RECIPES = [
    {
        'name': 'Campfire Rice & Beans',
        'category': 'main',
        'cooking_method': 'campfire',
        'prep_time_minutes': 10,
        'cook_time_minutes': 45,
        'servings': 4,
        'calories_per_serving': 380,
        'protein_per_serving': 14,
        'ingredients': json.dumps([
            {'item': 'white rice', 'amount': '2 cups'},
            {'item': 'canned black beans', 'amount': '2 cans (15 oz)'},
            {'item': 'salt', 'amount': '1 tsp'},
            {'item': 'cumin', 'amount': '1 tsp'},
            {'item': 'garlic powder', 'amount': '0.5 tsp'},
        ]),
        'instructions': '1. Bring 4 cups water to boil over campfire. 2. Add rice, reduce to simmer for 20 min. 3. Drain and rinse beans. 4. Add beans and spices to rice, cook 10 min more. 5. Let stand 5 min before serving.',
        'water_required_ml': 950,
        'fuel_required': 'Medium campfire, 1 hour burn time',
        'equipment_needed': json.dumps(['pot with lid', 'stirring spoon', 'can opener']),
        'shelf_stable_only': 1,
        'tags': json.dumps(['shelf-stable', 'high-protein', 'easy']),
        'rating': 4,
        'notes': 'Reliable staple meal. Add hot sauce or canned vegetables for variety.',
    },
    {
        'name': 'No-Cook Trail Mix Energy Balls',
        'category': 'snack',
        'cooking_method': 'no_cook',
        'prep_time_minutes': 15,
        'cook_time_minutes': 0,
        'servings': 12,
        'calories_per_serving': 210,
        'protein_per_serving': 7,
        'ingredients': json.dumps([
            {'item': 'rolled oats', 'amount': '2 cups'},
            {'item': 'peanut butter', 'amount': '1 cup'},
            {'item': 'honey', 'amount': '0.5 cup'},
            {'item': 'raisins', 'amount': '0.5 cup'},
            {'item': 'sunflower seeds', 'amount': '0.25 cup'},
        ]),
        'instructions': '1. Combine oats, peanut butter, and honey in a bowl. 2. Mix in raisins and sunflower seeds. 3. Roll into 12 balls. 4. Chill if possible or eat immediately.',
        'water_required_ml': 0,
        'fuel_required': 'None',
        'equipment_needed': json.dumps(['mixing bowl', 'spoon']),
        'shelf_stable_only': 1,
        'tags': json.dumps(['no-cook', 'portable', 'high-energy']),
        'rating': 5,
        'notes': 'Great for on-the-go energy. Keeps 5-7 days without refrigeration.',
    },
    {
        'name': 'Dutch Oven Bread',
        'category': 'bread',
        'cooking_method': 'dutch_oven',
        'prep_time_minutes': 20,
        'cook_time_minutes': 40,
        'servings': 8,
        'calories_per_serving': 180,
        'protein_per_serving': 5,
        'ingredients': json.dumps([
            {'item': 'all-purpose flour', 'amount': '3 cups'},
            {'item': 'instant yeast', 'amount': '1 packet (2.25 tsp)'},
            {'item': 'salt', 'amount': '1.5 tsp'},
            {'item': 'sugar', 'amount': '1 tbsp'},
            {'item': 'warm water', 'amount': '1.25 cups'},
        ]),
        'instructions': '1. Mix dry ingredients. 2. Add warm water, stir until shaggy dough forms. 3. Knead 8-10 min. 4. Let rise 1 hr in warm spot. 5. Shape into round, place in greased dutch oven. 6. Let rise 30 min. 7. Cover and bake over coals 35-40 min. 8. Check for golden crust.',
        'water_required_ml': 300,
        'fuel_required': 'Charcoal or campfire coals, top and bottom heat',
        'equipment_needed': json.dumps(['dutch oven', 'mixing bowl', 'charcoal/coals']),
        'shelf_stable_only': 0,
        'tags': json.dumps(['dutch-oven', 'comfort-food', 'morale-booster']),
        'rating': 5,
        'notes': 'Fresh bread is a massive morale booster. Yeast packets store well long-term.',
    },
    {
        'name': 'Boiled Pasta with Canned Sauce',
        'category': 'main',
        'cooking_method': 'camp_stove',
        'prep_time_minutes': 5,
        'cook_time_minutes': 15,
        'servings': 4,
        'calories_per_serving': 340,
        'protein_per_serving': 10,
        'ingredients': json.dumps([
            {'item': 'dried pasta', 'amount': '1 lb (16 oz)'},
            {'item': 'canned marinara sauce', 'amount': '1 jar (24 oz)'},
            {'item': 'salt', 'amount': '1 tsp'},
        ]),
        'instructions': '1. Bring large pot of salted water to boil on camp stove. 2. Add pasta, cook 8-10 min until tender. 3. Drain pasta. 4. Heat sauce in same pot or separate pan. 5. Combine and serve.',
        'water_required_ml': 2000,
        'fuel_required': 'Camp stove, ~20 min burn time',
        'equipment_needed': json.dumps(['large pot', 'strainer or lid for draining', 'camp stove']),
        'shelf_stable_only': 1,
        'tags': json.dumps(['shelf-stable', 'quick', 'easy', 'familiar']),
        'rating': 4,
        'notes': 'Comfort food. Dried pasta stores indefinitely. Add canned meat for protein.',
    },
    {
        'name': 'Hardtack',
        'category': 'bread',
        'cooking_method': 'campfire',
        'prep_time_minutes': 10,
        'cook_time_minutes': 30,
        'servings': 12,
        'calories_per_serving': 120,
        'protein_per_serving': 3,
        'ingredients': json.dumps([
            {'item': 'all-purpose flour', 'amount': '4 cups'},
            {'item': 'salt', 'amount': '2 tsp'},
            {'item': 'water', 'amount': '1.5 cups'},
        ]),
        'instructions': '1. Mix flour and salt. 2. Add water gradually until stiff dough forms. 3. Roll out to 0.5 inch thickness. 4. Cut into 3x3 inch squares. 5. Poke holes with fork in grid pattern. 6. Bake over low campfire heat or coals for 30 min per side. 7. Cool completely — should be rock hard.',
        'water_required_ml': 350,
        'fuel_required': 'Low campfire or coals, 1 hour',
        'equipment_needed': json.dumps(['flat baking surface', 'rolling pin or bottle', 'fork', 'knife']),
        'shelf_stable_only': 1,
        'tags': json.dumps(['shelf-stable', 'long-storage', 'survival', 'historical']),
        'rating': 3,
        'notes': 'Stores for years if kept dry. Soak in water, coffee, or stew to soften before eating. Civil War era ration.',
    },
]


# ═══════════════════════════════════════════════════════════════════════
#  DAILY SCHEDULES
# ═══════════════════════════════════════════════════════════════════════

@daily_living_bp.route('/schedules')
def api_schedules_list():
    with db_session() as db:
        stype = request.args.get('type')
        if stype:
            rows = db.execute(
                'SELECT * FROM daily_schedules WHERE schedule_type = ? ORDER BY id DESC',
                (stype,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM daily_schedules ORDER BY id DESC LIMIT ? OFFSET ?', get_pagination()).fetchall()
    return jsonify([dict(r) for r in rows])


@daily_living_bp.route('/schedules', methods=['POST'])
def api_schedules_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name required'}), 400
    now = datetime.utcnow().isoformat()
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO daily_schedules
               (name, schedule_type, description, time_blocks, assigned_to,
                is_template, active_days, start_date, end_date, status,
                created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('schedule_type', 'daily'),
             data.get('description', ''),
             json.dumps(data.get('time_blocks', [])),
             data.get('assigned_to', ''),
             1 if data.get('is_template') else 0,
             json.dumps(data.get('active_days', [])),
             data.get('start_date', ''), data.get('end_date', ''),
             data.get('status', 'active'), now, now)
        )
        db.commit()
        new_id = cur.lastrowid
    log_activity('schedule_created', service='daily_living', detail=name)
    return jsonify({'id': new_id, 'status': 'created'}), 201


@daily_living_bp.route('/schedules/templates')
def api_schedules_templates():
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM daily_schedules WHERE is_template = 1 ORDER BY name'
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@daily_living_bp.route('/schedules/<int:sid>')
def api_schedules_get(sid):
    with db_session() as db:
        row = db.execute('SELECT * FROM daily_schedules WHERE id = ?', (sid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(dict(row))


@daily_living_bp.route('/schedules/<int:sid>', methods=['PUT'])
def api_schedules_update(sid):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT * FROM daily_schedules WHERE id = ?', (sid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        allowed = _DAILY_SCHEDULES_ALLOWED_FIELDS
        updates = []
        values = []
        for key in allowed:
            if key in data:
                updates.append(f'{key} = ?')
                values.append(data[key])
        # JSON fields
        if 'time_blocks' in data:
            updates.append('time_blocks = ?')
            values.append(json.dumps(data['time_blocks']))
        if 'active_days' in data:
            updates.append('active_days = ?')
            values.append(json.dumps(data['active_days']))
        if 'is_template' in data:
            updates.append('is_template = ?')
            values.append(1 if data['is_template'] else 0)
        if not updates:
            return jsonify({'error': 'No fields to update'}), 400
        updates.append('updated_at = ?')
        values.append(datetime.utcnow().isoformat())
        values.append(sid)
        db.execute(
            f"UPDATE daily_schedules SET {', '.join(updates)} WHERE id = ?",
            values
        )
        db.commit()
    log_activity('schedule_updated', service='daily_living', detail=f'id={sid}')
    return jsonify({'status': 'updated'})


@daily_living_bp.route('/schedules/<int:sid>', methods=['DELETE'])
def api_schedules_delete(sid):
    with db_session() as db:
        row = db.execute('SELECT name FROM daily_schedules WHERE id = ?', (sid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM daily_schedules WHERE id = ?', (sid,))
        db.commit()
    log_activity('schedule_deleted', service='daily_living', detail=row['name'])
    return jsonify({'deleted': True})


# ═══════════════════════════════════════════════════════════════════════
#  CHORE ASSIGNMENTS
# ═══════════════════════════════════════════════════════════════════════

@daily_living_bp.route('/chores')
def api_chores_list():
    with db_session() as db:
        clauses = []
        params = []
        schedule_id = request.args.get('schedule_id')
        assigned_to = request.args.get('assigned_to')
        if schedule_id:
            clauses.append('schedule_id = ?')
            params.append(schedule_id)
        if assigned_to:
            clauses.append('assigned_to = ?')
            params.append(assigned_to)
        where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
        rows = db.execute(
            f'SELECT * FROM chore_assignments{where} ORDER BY id DESC', params
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@daily_living_bp.route('/chores', methods=['POST'])
def api_chores_create():
    data = request.get_json() or {}
    chore_name = (data.get('chore_name') or '').strip()
    if not chore_name:
        return jsonify({'error': 'chore_name required'}), 400
    now = datetime.utcnow().isoformat()
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO chore_assignments
               (schedule_id, chore_name, category, assigned_to, frequency,
                time_slot, duration_minutes, priority, instructions,
                rotation_group, last_completed, status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (data.get('schedule_id'), chore_name,
             data.get('category', ''), data.get('assigned_to', ''),
             data.get('frequency', 'daily'), data.get('time_slot', ''),
             data.get('duration_minutes', 30), data.get('priority', 'medium'),
             data.get('instructions', ''), data.get('rotation_group', ''),
             data.get('last_completed'), data.get('status', 'active'),
             now, now)
        )
        db.commit()
        new_id = cur.lastrowid
    log_activity('chore_created', service='daily_living', detail=chore_name)
    return jsonify({'id': new_id, 'status': 'created'}), 201


@daily_living_bp.route('/chores/<int:cid>')
def api_chores_get(cid):
    with db_session() as db:
        row = db.execute('SELECT * FROM chore_assignments WHERE id = ?', (cid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(dict(row))


@daily_living_bp.route('/chores/<int:cid>', methods=['PUT'])
def api_chores_update(cid):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT * FROM chore_assignments WHERE id = ?', (cid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        allowed = _CHORE_ASSIGNMENTS_ALLOWED_FIELDS
        updates = []
        values = []
        for key in allowed:
            if key in data:
                updates.append(f'{key} = ?')
                values.append(data[key])
        if not updates:
            return jsonify({'error': 'No fields to update'}), 400
        updates.append('updated_at = ?')
        values.append(datetime.utcnow().isoformat())
        values.append(cid)
        db.execute(
            f"UPDATE chore_assignments SET {', '.join(updates)} WHERE id = ?",
            values
        )
        db.commit()
    log_activity('chore_updated', service='daily_living', detail=f'id={cid}')
    return jsonify({'status': 'updated'})


@daily_living_bp.route('/chores/<int:cid>', methods=['DELETE'])
def api_chores_delete(cid):
    with db_session() as db:
        row = db.execute('SELECT chore_name FROM chore_assignments WHERE id = ?', (cid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM chore_assignments WHERE id = ?', (cid,))
        db.commit()
    log_activity('chore_deleted', service='daily_living', detail=row['chore_name'])
    return jsonify({'deleted': True})


@daily_living_bp.route('/chores/<int:cid>/complete', methods=['POST'])
def api_chores_complete(cid):
    now = datetime.utcnow().isoformat()
    with db_session() as db:
        existing = db.execute('SELECT * FROM chore_assignments WHERE id = ?', (cid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        db.execute(
            'UPDATE chore_assignments SET last_completed = ?, updated_at = ? WHERE id = ?',
            (now, now, cid)
        )
        db.commit()
    log_activity('chore_completed', service='daily_living', detail=existing['chore_name'])
    return jsonify({'status': 'completed', 'last_completed': now})


@daily_living_bp.route('/chores/rotate', methods=['POST'])
def api_chores_rotate():
    """Rotate chore assignments within each rotation group."""
    with db_session() as db:
        groups = db.execute(
            "SELECT DISTINCT rotation_group FROM chore_assignments "
            "WHERE rotation_group IS NOT NULL AND rotation_group != '' "
            "ORDER BY rotation_group"
        ).fetchall()
        rotated = 0
        now = datetime.utcnow().isoformat()
        for g in groups:
            group_name = g['rotation_group']
            chores = db.execute(
                'SELECT id, assigned_to FROM chore_assignments '
                'WHERE rotation_group = ? ORDER BY id',
                (group_name,)
            ).fetchall()
            if len(chores) < 2:
                continue
            # Shift assignments: each person gets the next chore's assignment
            people = [c['assigned_to'] for c in chores]
            # Rotate: last person goes to first slot
            rotated_people = [people[-1]] + people[:-1]
            for chore, new_person in zip(chores, rotated_people):
                db.execute(
                    'UPDATE chore_assignments SET assigned_to = ?, updated_at = ? WHERE id = ?',
                    (new_person, now, chore['id'])
                )
            rotated += len(chores)
        db.commit()
    log_activity('chores_rotated', service='daily_living', detail=f'{rotated} assignments rotated')
    return jsonify({'status': 'rotated', 'assignments_rotated': rotated})


# ═══════════════════════════════════════════════════════════════════════
#  CLOTHING INVENTORY
# ═══════════════════════════════════════════════════════════════════════

@daily_living_bp.route('/clothing')
def api_clothing_list():
    with db_session() as db:
        clauses = []
        params = []
        person = request.args.get('person')
        season = request.args.get('season')
        if person:
            clauses.append('person = ?')
            params.append(person)
        if season:
            clauses.append('season = ?')
            params.append(season)
        where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
        rows = db.execute(
            f'SELECT * FROM clothing_inventory{where} ORDER BY id DESC', params
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@daily_living_bp.route('/clothing', methods=['POST'])
def api_clothing_create():
    data = request.get_json() or {}
    item_name = (data.get('item_name') or '').strip()
    if not item_name:
        return jsonify({'error': 'item_name required'}), 400
    now = datetime.utcnow().isoformat()
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO clothing_inventory
               (person, item_name, category, size, quantity, condition, season,
                warmth_rating, waterproof, material, location, notes,
                created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (data.get('person', ''), item_name,
             data.get('category', ''), data.get('size', ''),
             data.get('quantity', 1), data.get('condition', 'good'),
             data.get('season', 'all'), data.get('warmth_rating', 5),
             1 if data.get('waterproof') else 0,
             data.get('material', ''), data.get('location', ''),
             data.get('notes', ''), now, now)
        )
        db.commit()
        new_id = cur.lastrowid
    log_activity('clothing_added', service='daily_living', detail=item_name)
    return jsonify({'id': new_id, 'status': 'created'}), 201


@daily_living_bp.route('/clothing/<int:cid>')
def api_clothing_get(cid):
    with db_session() as db:
        row = db.execute('SELECT * FROM clothing_inventory WHERE id = ?', (cid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(dict(row))


@daily_living_bp.route('/clothing/<int:cid>', methods=['PUT'])
def api_clothing_update(cid):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT * FROM clothing_inventory WHERE id = ?', (cid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        allowed = _CLOTHING_INVENTORY_ALLOWED_FIELDS
        updates = []
        values = []
        for key in allowed:
            if key in data:
                updates.append(f'{key} = ?')
                values.append(data[key])
        if 'waterproof' in data:
            updates.append('waterproof = ?')
            values.append(1 if data['waterproof'] else 0)
        if not updates:
            return jsonify({'error': 'No fields to update'}), 400
        updates.append('updated_at = ?')
        values.append(datetime.utcnow().isoformat())
        values.append(cid)
        db.execute(
            f"UPDATE clothing_inventory SET {', '.join(updates)} WHERE id = ?",
            values
        )
        db.commit()
    log_activity('clothing_updated', service='daily_living', detail=f'id={cid}')
    return jsonify({'status': 'updated'})


@daily_living_bp.route('/clothing/<int:cid>', methods=['DELETE'])
def api_clothing_delete(cid):
    with db_session() as db:
        row = db.execute('SELECT item_name FROM clothing_inventory WHERE id = ?', (cid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM clothing_inventory WHERE id = ?', (cid,))
        db.commit()
    log_activity('clothing_deleted', service='daily_living', detail=row['item_name'])
    return jsonify({'deleted': True})


@daily_living_bp.route('/clothing/assessment')
def api_clothing_assessment():
    """Cold weather readiness assessment: counts by warmth rating, waterproof gear, gaps."""
    with db_session() as db:
        rows = db.execute('SELECT * FROM clothing_inventory ORDER BY person LIMIT ? OFFSET ?', get_pagination()).fetchall()

    items = [dict(r) for r in rows]
    people = {}
    for item in items:
        p = item.get('person') or 'Unassigned'
        if p not in people:
            people[p] = {'total_items': 0, 'warmth_breakdown': {}, 'waterproof_count': 0, 'gaps': []}
        entry = people[p]
        entry['total_items'] += item.get('quantity', 1)
        wr = str(item.get('warmth_rating', 0))
        entry['warmth_breakdown'][wr] = entry['warmth_breakdown'].get(wr, 0) + item.get('quantity', 1)
        if item.get('waterproof'):
            entry['waterproof_count'] += item.get('quantity', 1)

    # Identify gaps: no waterproof items, no high-warmth items (rating >= 8)
    for p, entry in people.items():
        if entry['waterproof_count'] == 0:
            entry['gaps'].append('No waterproof items')
        high_warmth = sum(v for k, v in entry['warmth_breakdown'].items() if int(k) >= 8)
        if high_warmth == 0:
            entry['gaps'].append('No high-warmth items (rating >= 8)')
        # Check essential categories
        categories_present = set()
        for item in items:
            if (item.get('person') or 'Unassigned') == p:
                categories_present.add(item.get('category', '').lower())
        for essential in ['jacket', 'boots', 'gloves', 'hat']:
            if essential not in categories_present:
                entry['gaps'].append(f'Missing category: {essential}')

    return jsonify({
        'total_items': len(items),
        'by_person': people,
    })


# ═══════════════════════════════════════════════════════════════════════
#  SANITATION SUPPLIES
# ═══════════════════════════════════════════════════════════════════════

@daily_living_bp.route('/sanitation')
def api_sanitation_list():
    with db_session() as db:
        category = request.args.get('category')
        if category:
            rows = db.execute(
                'SELECT * FROM sanitation_supplies WHERE category = ? ORDER BY id DESC',
                (category,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM sanitation_supplies ORDER BY id DESC LIMIT ? OFFSET ?', get_pagination()).fetchall()
    return jsonify([dict(r) for r in rows])


@daily_living_bp.route('/sanitation', methods=['POST'])
def api_sanitation_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name required'}), 400
    now = datetime.utcnow().isoformat()
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO sanitation_supplies
               (name, category, quantity, unit, min_stock, daily_usage_rate,
                persons_served, location, expiration_date, notes,
                created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('category', ''),
             data.get('quantity', 0), data.get('unit', ''),
             data.get('min_stock', 0), data.get('daily_usage_rate', 0),
             data.get('persons_served', 1), data.get('location', ''),
             data.get('expiration_date', ''), data.get('notes', ''),
             now, now)
        )
        db.commit()
        new_id = cur.lastrowid
    log_activity('sanitation_added', service='daily_living', detail=name)
    return jsonify({'id': new_id, 'status': 'created'}), 201


@daily_living_bp.route('/sanitation/<int:sid>')
def api_sanitation_get(sid):
    with db_session() as db:
        row = db.execute('SELECT * FROM sanitation_supplies WHERE id = ?', (sid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(dict(row))


@daily_living_bp.route('/sanitation/<int:sid>', methods=['PUT'])
def api_sanitation_update(sid):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT * FROM sanitation_supplies WHERE id = ?', (sid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        allowed = _SANITATION_SUPPLIES_ALLOWED_FIELDS
        updates = []
        values = []
        for key in allowed:
            if key in data:
                updates.append(f'{key} = ?')
                values.append(data[key])
        if not updates:
            return jsonify({'error': 'No fields to update'}), 400
        updates.append('updated_at = ?')
        values.append(datetime.utcnow().isoformat())
        values.append(sid)
        db.execute(
            f"UPDATE sanitation_supplies SET {', '.join(updates)} WHERE id = ?",
            values
        )
        db.commit()
    log_activity('sanitation_updated', service='daily_living', detail=f'id={sid}')
    return jsonify({'status': 'updated'})


@daily_living_bp.route('/sanitation/<int:sid>', methods=['DELETE'])
def api_sanitation_delete(sid):
    with db_session() as db:
        row = db.execute('SELECT name FROM sanitation_supplies WHERE id = ?', (sid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM sanitation_supplies WHERE id = ?', (sid,))
        db.commit()
    log_activity('sanitation_deleted', service='daily_living', detail=row['name'])
    return jsonify({'deleted': True})


@daily_living_bp.route('/sanitation/projections')
def api_sanitation_projections():
    """Days of supply per item based on daily_usage_rate and current quantity."""
    with db_session() as db:
        rows = db.execute('SELECT * FROM sanitation_supplies ORDER BY name LIMIT ? OFFSET ?', get_pagination()).fetchall()

    projections = []
    for r in rows:
        item = dict(r)
        rate = item.get('daily_usage_rate', 0) or 0
        qty = item.get('quantity', 0) or 0
        min_stock = item.get('min_stock', 0) or 0
        days_remaining = round(qty / rate, 1) if rate > 0 else None
        days_until_min = round((qty - min_stock) / rate, 1) if rate > 0 and qty > min_stock else 0
        status = 'ok'
        if days_remaining is not None:
            if days_remaining <= 3:
                status = 'critical'
            elif days_remaining <= 7:
                status = 'warning'
            elif days_remaining <= 14:
                status = 'monitor'
        elif rate == 0 and qty > 0:
            status = 'no_usage_rate'
        elif qty <= 0:
            status = 'depleted'
        projections.append({
            'id': item['id'],
            'name': item['name'],
            'category': item.get('category', ''),
            'quantity': qty,
            'unit': item.get('unit', ''),
            'daily_usage_rate': rate,
            'days_remaining': days_remaining,
            'days_until_min_stock': days_until_min,
            'status': status,
        })
    return jsonify(projections)


# ═══════════════════════════════════════════════════════════════════════
#  MORALE LOGS
# ═══════════════════════════════════════════════════════════════════════

@daily_living_bp.route('/morale')
def api_morale_list():
    with db_session() as db:
        person = request.args.get('person')
        if person:
            rows = db.execute(
                'SELECT * FROM morale_logs WHERE person = ? ORDER BY date DESC',
                (person,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM morale_logs ORDER BY date DESC LIMIT ? OFFSET ?', get_pagination()).fetchall()
    return jsonify([dict(r) for r in rows])


@daily_living_bp.route('/morale', methods=['POST'])
def api_morale_create():
    data = request.get_json() or {}
    person = (data.get('person') or '').strip()
    if not person:
        return jsonify({'error': 'person required'}), 400
    now = datetime.utcnow().isoformat()
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO morale_logs
               (person, date, morale_score, stress_level, sleep_quality,
                physical_health, social_connection, activities, concerns,
                positive_notes, interventions, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (person, data.get('date', now[:10]),
             data.get('morale_score', 5), data.get('stress_level', 5),
             data.get('sleep_quality', 5), data.get('physical_health', 5),
             data.get('social_connection', 5),
             json.dumps(data.get('activities', [])),
             data.get('concerns', ''), data.get('positive_notes', ''),
             data.get('interventions', ''), now)
        )
        db.commit()
        new_id = cur.lastrowid
    log_activity('morale_logged', service='daily_living', detail=f'{person} score={data.get("morale_score", 5)}')
    return jsonify({'id': new_id, 'status': 'created'}), 201


@daily_living_bp.route('/morale/<int:mid>')
def api_morale_get(mid):
    with db_session() as db:
        row = db.execute('SELECT * FROM morale_logs WHERE id = ?', (mid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(dict(row))


@daily_living_bp.route('/morale/<int:mid>', methods=['DELETE'])
def api_morale_delete(mid):
    with db_session() as db:
        row = db.execute('SELECT person, date FROM morale_logs WHERE id = ?', (mid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM morale_logs WHERE id = ?', (mid,))
        db.commit()
    log_activity('morale_deleted', service='daily_living', detail=f"{row['person']} {row['date']}")
    return jsonify({'deleted': True})


@daily_living_bp.route('/morale/trends')
def api_morale_trends():
    """Average morale scores over last 7/14/30 days, grouped by person."""
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM morale_logs ORDER BY date DESC'
        ).fetchall()

    from datetime import timedelta
    today = datetime.utcnow().date()
    periods = {'7d': 7, '14d': 14, '30d': 30}
    people = {}

    for r in rows:
        d = dict(r)
        person = d.get('person', 'Unknown')
        try:
            log_date = datetime.fromisoformat(d['date']).date() if d.get('date') else None
        except (ValueError, TypeError):
            try:
                log_date = datetime.strptime(d['date'], '%Y-%m-%d').date()
            except Exception:
                continue
        if not log_date:
            continue

        if person not in people:
            people[person] = {p: {'morale': [], 'stress': [], 'sleep': [], 'physical': [], 'social': []}
                              for p in periods}

        for period_name, days in periods.items():
            if (today - log_date).days <= days:
                bucket = people[person][period_name]
                bucket['morale'].append(d.get('morale_score', 0) or 0)
                bucket['stress'].append(d.get('stress_level', 0) or 0)
                bucket['sleep'].append(d.get('sleep_quality', 0) or 0)
                bucket['physical'].append(d.get('physical_health', 0) or 0)
                bucket['social'].append(d.get('social_connection', 0) or 0)

    result = {}
    for person, period_data in people.items():
        result[person] = {}
        for period_name, metrics in period_data.items():
            avg = {}
            for metric, vals in metrics.items():
                avg[metric] = round(sum(vals) / len(vals), 1) if vals else None
            avg['entries'] = len(metrics['morale'])
            result[person][period_name] = avg

    return jsonify(result)


# ═══════════════════════════════════════════════════════════════════════
#  SLEEP LOGS
# ═══════════════════════════════════════════════════════════════════════

@daily_living_bp.route('/sleep')
def api_sleep_list():
    with db_session() as db:
        person = request.args.get('person')
        if person:
            rows = db.execute(
                'SELECT * FROM sleep_logs WHERE person = ? ORDER BY date DESC',
                (person,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM sleep_logs ORDER BY date DESC LIMIT ? OFFSET ?', get_pagination()).fetchall()
    return jsonify([dict(r) for r in rows])


@daily_living_bp.route('/sleep', methods=['POST'])
def api_sleep_create():
    data = request.get_json() or {}
    person = (data.get('person') or '').strip()
    if not person:
        return jsonify({'error': 'person required'}), 400
    now = datetime.utcnow().isoformat()
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO sleep_logs
               (person, date, sleep_start, sleep_end, duration_hours, quality,
                interruptions, watch_duty, watch_start, watch_end,
                sleep_debt_hours, environment, notes, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (person, data.get('date', now[:10]),
             data.get('sleep_start', ''), data.get('sleep_end', ''),
             data.get('duration_hours', 0), data.get('quality', 5),
             data.get('interruptions', 0),
             1 if data.get('watch_duty') else 0,
             data.get('watch_start', ''), data.get('watch_end', ''),
             data.get('sleep_debt_hours', 0), data.get('environment', ''),
             data.get('notes', ''), now)
        )
        db.commit()
        new_id = cur.lastrowid
    log_activity('sleep_logged', service='daily_living', detail=f'{person} {data.get("duration_hours", 0)}h')
    return jsonify({'id': new_id, 'status': 'created'}), 201


@daily_living_bp.route('/sleep/<int:sid>')
def api_sleep_get(sid):
    with db_session() as db:
        row = db.execute('SELECT * FROM sleep_logs WHERE id = ?', (sid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(dict(row))


@daily_living_bp.route('/sleep/<int:sid>', methods=['DELETE'])
def api_sleep_delete(sid):
    with db_session() as db:
        row = db.execute('SELECT person, date FROM sleep_logs WHERE id = ?', (sid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM sleep_logs WHERE id = ?', (sid,))
        db.commit()
    log_activity('sleep_deleted', service='daily_living', detail=f"{row['person']} {row['date']}")
    return jsonify({'deleted': True})


@daily_living_bp.route('/sleep/debt')
def api_sleep_debt():
    """Cumulative sleep debt per person (8hr target minus actual)."""
    target_hours = 8.0
    with db_session() as db:
        rows = db.execute(
            'SELECT person, date, duration_hours FROM sleep_logs ORDER BY person, date'
        ).fetchall()

    people = {}
    for r in rows:
        person = r['person']
        duration = r['duration_hours'] or 0
        if person not in people:
            people[person] = {'total_sleep': 0, 'days_tracked': 0, 'cumulative_debt': 0}
        people[person]['total_sleep'] += duration
        people[person]['days_tracked'] += 1
        people[person]['cumulative_debt'] += (target_hours - duration)

    result = []
    for person, stats in people.items():
        avg = round(stats['total_sleep'] / stats['days_tracked'], 1) if stats['days_tracked'] else 0
        result.append({
            'person': person,
            'days_tracked': stats['days_tracked'],
            'total_sleep_hours': round(stats['total_sleep'], 1),
            'avg_sleep_hours': avg,
            'cumulative_debt_hours': round(stats['cumulative_debt'], 1),
            'status': 'critical' if stats['cumulative_debt'] > 16 else
                      'warning' if stats['cumulative_debt'] > 8 else
                      'ok',
        })
    result.sort(key=lambda x: x['cumulative_debt_hours'], reverse=True)
    return jsonify(result)


@daily_living_bp.route('/sleep/watch-optimizer')
def api_sleep_watch_optimizer():
    """Suggest watch schedule to minimize fatigue (round-robin by least sleep debt)."""
    with db_session() as db:
        rows = db.execute(
            'SELECT person, duration_hours FROM sleep_logs ORDER BY person, date'
        ).fetchall()

    target_hours = 8.0
    people = {}
    for r in rows:
        person = r['person']
        duration = r['duration_hours'] or 0
        if person not in people:
            people[person] = {'cumulative_debt': 0, 'days': 0}
        people[person]['cumulative_debt'] += (target_hours - duration)
        people[person]['days'] += 1

    if not people:
        return jsonify({'schedule': [], 'note': 'No sleep data available'})

    # Sort by least debt first (most rested first for next watch)
    sorted_people = sorted(people.items(), key=lambda x: x[1]['cumulative_debt'])

    watches = ['22:00-02:00', '02:00-06:00', '06:00-10:00', '10:00-14:00',
               '14:00-18:00', '18:00-22:00']
    schedule = []
    for i, watch in enumerate(watches):
        person_idx = i % len(sorted_people)
        person_name = sorted_people[person_idx][0]
        debt = round(sorted_people[person_idx][1]['cumulative_debt'], 1)
        schedule.append({
            'watch': watch,
            'assigned_to': person_name,
            'sleep_debt_hours': debt,
            'note': 'Most rested' if person_idx == 0 else '',
        })

    return jsonify({
        'schedule': schedule,
        'personnel_by_readiness': [
            {'person': p, 'debt_hours': round(d['cumulative_debt'], 1)}
            for p, d in sorted_people
        ],
        'note': 'Assignments rotate least-debt-first. Adjust for operational needs.',
    })


# ═══════════════════════════════════════════════════════════════════════
#  PERFORMANCE CHECKS
# ═══════════════════════════════════════════════════════════════════════

def _calculate_risk(fatigue_level, hours_awake):
    """Determine risk assessment based on fatigue and wakefulness."""
    fatigue = fatigue_level or 0
    awake = hours_awake or 0
    if fatigue >= 8 or awake >= 18:
        return 'critical'
    if fatigue >= 6 or awake >= 14:
        return 'high'
    if fatigue >= 4 or awake >= 10:
        return 'moderate'
    return 'low'


@daily_living_bp.route('/performance')
def api_performance_list():
    with db_session() as db:
        person = request.args.get('person')
        if person:
            rows = db.execute(
                'SELECT * FROM performance_checks WHERE person = ? ORDER BY date DESC',
                (person,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM performance_checks ORDER BY date DESC LIMIT ? OFFSET ?', get_pagination()).fetchall()
    return jsonify([dict(r) for r in rows])


@daily_living_bp.route('/performance', methods=['POST'])
def api_performance_create():
    data = request.get_json() or {}
    person = (data.get('person') or '').strip()
    if not person:
        return jsonify({'error': 'person required'}), 400
    now = datetime.utcnow().isoformat()
    fatigue = data.get('fatigue_level', 0)
    hours_awake = data.get('hours_awake', 0)
    risk = _calculate_risk(fatigue, hours_awake)
    # Auto-generate recommendations based on risk
    recommendations = data.get('recommendations', '')
    if not recommendations:
        if risk == 'critical':
            recommendations = 'Immediate rest required. Remove from all duties. Minimum 6 hours sleep before reassignment.'
        elif risk == 'high':
            recommendations = 'Reduce workload. No safety-critical tasks. Schedule rest within 2 hours.'
        elif risk == 'moderate':
            recommendations = 'Monitor closely. Ensure adequate hydration and nutrition. Plan rest period.'

    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO performance_checks
               (person, date, check_type, reaction_time_ms, cognitive_score,
                physical_score, fatigue_level, hours_awake, hours_since_last_sleep,
                ambient_temp_f, hydration_status, caloric_intake,
                risk_assessment, recommendations, notes, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (person, data.get('date', now[:10]),
             data.get('check_type', 'routine'),
             data.get('reaction_time_ms'), data.get('cognitive_score'),
             data.get('physical_score'), fatigue,
             hours_awake, data.get('hours_since_last_sleep'),
             data.get('ambient_temp_f'), data.get('hydration_status', ''),
             data.get('caloric_intake'), risk, recommendations,
             data.get('notes', ''), now)
        )
        db.commit()
        new_id = cur.lastrowid
    log_activity('performance_check', service='daily_living',
                 detail=f'{person} risk={risk} fatigue={fatigue}')
    return jsonify({'id': new_id, 'risk_assessment': risk, 'status': 'created'}), 201


@daily_living_bp.route('/performance/<int:pid>')
def api_performance_get(pid):
    with db_session() as db:
        row = db.execute('SELECT * FROM performance_checks WHERE id = ?', (pid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(dict(row))


@daily_living_bp.route('/performance/<int:pid>', methods=['DELETE'])
def api_performance_delete(pid):
    with db_session() as db:
        row = db.execute('SELECT person, date FROM performance_checks WHERE id = ?', (pid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM performance_checks WHERE id = ?', (pid,))
        db.commit()
    log_activity('performance_deleted', service='daily_living', detail=f"{row['person']} {row['date']}")
    return jsonify({'deleted': True})


@daily_living_bp.route('/performance/risk-summary')
def api_performance_risk_summary():
    """Aggregate risk levels across all personnel from latest checks."""
    with db_session() as db:
        # Get most recent check per person
        rows = db.execute(
            '''SELECT p.* FROM performance_checks p
               INNER JOIN (
                   SELECT person, MAX(date) as max_date
                   FROM performance_checks GROUP BY person
               ) latest ON p.person = latest.person AND p.date = latest.max_date
               ORDER BY p.person'''
        ).fetchall()

    summary = {'critical': [], 'high': [], 'moderate': [], 'low': []}
    for r in rows:
        d = dict(r)
        risk = d.get('risk_assessment', 'low')
        entry = {
            'person': d['person'],
            'date': d.get('date'),
            'fatigue_level': d.get('fatigue_level'),
            'hours_awake': d.get('hours_awake'),
            'cognitive_score': d.get('cognitive_score'),
            'physical_score': d.get('physical_score'),
            'recommendations': d.get('recommendations', ''),
        }
        if risk in summary:
            summary[risk].append(entry)
        else:
            summary['low'].append(entry)

    return jsonify({
        'summary': summary,
        'counts': {k: len(v) for k, v in summary.items()},
        'total_personnel': sum(len(v) for v in summary.values()),
    })


# ═══════════════════════════════════════════════════════════════════════
#  GRID-DOWN RECIPES
# ═══════════════════════════════════════════════════════════════════════

@daily_living_bp.route('/recipes')
def api_recipes_list():
    with db_session() as db:
        clauses = []
        params = []
        category = request.args.get('category')
        method = request.args.get('method')
        shelf_stable = request.args.get('shelf_stable')
        if category:
            clauses.append('category = ?')
            params.append(category)
        if method:
            clauses.append('cooking_method = ?')
            params.append(method)
        if shelf_stable is not None and shelf_stable != '':
            clauses.append('shelf_stable_only = ?')
            params.append(1 if shelf_stable in ('1', 'true', 'yes') else 0)
        where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
        rows = db.execute(
            f'SELECT * FROM grid_down_recipes{where} ORDER BY id DESC', params
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@daily_living_bp.route('/recipes', methods=['POST'])
def api_recipes_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name required'}), 400
    now = datetime.utcnow().isoformat()
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO grid_down_recipes
               (name, category, cooking_method, prep_time_minutes,
                cook_time_minutes, servings, calories_per_serving,
                protein_per_serving, ingredients, instructions,
                water_required_ml, fuel_required, equipment_needed,
                shelf_stable_only, tags, rating, notes,
                created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('category', ''),
             data.get('cooking_method', ''),
             data.get('prep_time_minutes', 0), data.get('cook_time_minutes', 0),
             data.get('servings', 1), data.get('calories_per_serving', 0),
             data.get('protein_per_serving', 0),
             json.dumps(data.get('ingredients', [])),
             data.get('instructions', ''),
             data.get('water_required_ml', 0), data.get('fuel_required', ''),
             json.dumps(data.get('equipment_needed', [])),
             1 if data.get('shelf_stable_only') else 0,
             json.dumps(data.get('tags', [])),
             data.get('rating', 0), data.get('notes', ''),
             now, now)
        )
        db.commit()
        new_id = cur.lastrowid
    log_activity('recipe_created', service='daily_living', detail=name)
    return jsonify({'id': new_id, 'status': 'created'}), 201


@daily_living_bp.route('/recipes/<int:rid>')
def api_recipes_get(rid):
    with db_session() as db:
        row = db.execute('SELECT * FROM grid_down_recipes WHERE id = ?', (rid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(dict(row))


@daily_living_bp.route('/recipes/<int:rid>', methods=['PUT'])
def api_recipes_update(rid):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT * FROM grid_down_recipes WHERE id = ?', (rid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        allowed = _GRID_DOWN_RECIPES_ALLOWED_FIELDS
        updates = []
        values = []
        for key in allowed:
            if key in data:
                updates.append(f'{key} = ?')
                values.append(data[key])
        # JSON fields
        if 'ingredients' in data:
            updates.append('ingredients = ?')
            values.append(json.dumps(data['ingredients']))
        if 'equipment_needed' in data:
            updates.append('equipment_needed = ?')
            values.append(json.dumps(data['equipment_needed']))
        if 'tags' in data:
            updates.append('tags = ?')
            values.append(json.dumps(data['tags']))
        if 'shelf_stable_only' in data:
            updates.append('shelf_stable_only = ?')
            values.append(1 if data['shelf_stable_only'] else 0)
        if not updates:
            return jsonify({'error': 'No fields to update'}), 400
        updates.append('updated_at = ?')
        values.append(datetime.utcnow().isoformat())
        values.append(rid)
        db.execute(
            f"UPDATE grid_down_recipes SET {', '.join(updates)} WHERE id = ?",
            values
        )
        db.commit()
    log_activity('recipe_updated', service='daily_living', detail=f'id={rid}')
    return jsonify({'status': 'updated'})


@daily_living_bp.route('/recipes/<int:rid>', methods=['DELETE'])
def api_recipes_delete(rid):
    with db_session() as db:
        row = db.execute('SELECT name FROM grid_down_recipes WHERE id = ?', (rid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM grid_down_recipes WHERE id = ?', (rid,))
        db.commit()
    log_activity('recipe_deleted', service='daily_living', detail=row['name'])
    return jsonify({'deleted': True})


@daily_living_bp.route('/recipes/search')
def api_recipes_search():
    """Search recipes by name or ingredient."""
    q = (request.args.get('q') or '').strip()
    if not q:
        return jsonify({'error': 'Search query ?q= required'}), 400
    pattern = f'%{q}%'
    with db_session() as db:
        rows = db.execute(
            '''SELECT * FROM grid_down_recipes
               WHERE name LIKE ? OR ingredients LIKE ? OR tags LIKE ?
               ORDER BY rating DESC, name''',
            (pattern, pattern, pattern)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@daily_living_bp.route('/recipes/calculate-fuel', methods=['POST'])
def api_recipes_calculate_fuel():
    """Estimate fuel needed for a recipe at a given serving count."""
    data = request.get_json() or {}
    recipe_id = data.get('recipe_id')
    target_servings = data.get('servings')
    if not recipe_id or not target_servings:
        return jsonify({'error': 'recipe_id and servings required'}), 400
    with db_session() as db:
        row = db.execute('SELECT * FROM grid_down_recipes WHERE id = ?', (recipe_id,)).fetchone()
    if not row:
        return jsonify({'error': 'Recipe not found'}), 404

    recipe = dict(row)
    base_servings = recipe.get('servings', 1) or 1
    multiplier = target_servings / base_servings

    return jsonify({
        'recipe': recipe['name'],
        'base_servings': base_servings,
        'target_servings': target_servings,
        'multiplier': round(multiplier, 2),
        'water_required_ml': round((recipe.get('water_required_ml', 0) or 0) * multiplier),
        'fuel_required': recipe.get('fuel_required', ''),
        'fuel_note': f'Scale base fuel by {round(multiplier, 2)}x for {target_servings} servings',
        'cook_time_minutes': recipe.get('cook_time_minutes', 0),
        'prep_time_minutes': recipe.get('prep_time_minutes', 0),
        'total_calories': round((recipe.get('calories_per_serving', 0) or 0) * target_servings),
        'total_protein': round((recipe.get('protein_per_serving', 0) or 0) * target_servings),
    })


@daily_living_bp.route('/recipes/seed', methods=['POST'])
def api_recipes_seed():
    """Insert seed recipes if the table is empty."""
    with db_session() as db:
        count = db.execute('SELECT COUNT(*) as cnt FROM grid_down_recipes').fetchone()['cnt']
        if count > 0:
            return jsonify({'status': 'skipped', 'message': f'Table already has {count} recipes'})
        now = datetime.utcnow().isoformat()
        inserted = 0
        for recipe in SEED_RECIPES:
            db.execute(
                '''INSERT INTO grid_down_recipes
                   (name, category, cooking_method, prep_time_minutes,
                    cook_time_minutes, servings, calories_per_serving,
                    protein_per_serving, ingredients, instructions,
                    water_required_ml, fuel_required, equipment_needed,
                    shelf_stable_only, tags, rating, notes,
                    created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (recipe['name'], recipe['category'], recipe['cooking_method'],
                 recipe['prep_time_minutes'], recipe['cook_time_minutes'],
                 recipe['servings'], recipe['calories_per_serving'],
                 recipe['protein_per_serving'], recipe['ingredients'],
                 recipe['instructions'], recipe['water_required_ml'],
                 recipe['fuel_required'], recipe['equipment_needed'],
                 recipe['shelf_stable_only'], recipe['tags'],
                 recipe['rating'], recipe['notes'], now, now)
            )
            inserted += 1
        db.commit()
    log_activity('recipes_seeded', service='daily_living', detail=f'{inserted} seed recipes added')
    return jsonify({'status': 'seeded', 'count': inserted}), 201


# ═══════════════════════════════════════════════════════════════════════
#  WORK/REST REFERENCE
# ═══════════════════════════════════════════════════════════════════════

@daily_living_bp.route('/reference/work-rest')
def api_work_rest_reference():
    return jsonify(WORK_REST_REFERENCE)
