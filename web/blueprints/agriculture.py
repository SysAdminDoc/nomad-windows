"""Agriculture & Permaculture — food forests, soil building, perennials,
multi-year plans, breeding, feed tracking, homestead systems, aquaponics,
and recycling/closed-loop systems."""

import json
import logging
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from db import db_session, log_activity
from web.blueprints import get_pagination

_log = logging.getLogger(__name__)

agriculture_bp = Blueprint('agriculture', __name__, url_prefix='/api/agriculture')

_FOOD_FOREST_GUILDS_ALLOWED_FIELDS = frozenset({'name', 'description', 'central_species', 'support_species',
                                                'nitrogen_fixers', 'dynamic_accumulators', 'pest_confusers',
                                                'ground_covers', 'notes'})
_FOOD_FOREST_LAYERS_ALLOWED_FIELDS = frozenset({'design_name', 'layer_type', 'species', 'spacing_ft',
                                                'mature_height_ft', 'yield_per_year', 'years_to_production',
                                                'guild_id', 'notes'})
_SOIL_PROJECTS_ALLOWED_FIELDS = frozenset({'name', 'project_type', 'location', 'dimensions', 'materials',
                                           'start_date', 'completion_date', 'soil_test_before',
                                           'soil_test_after', 'status', 'notes'})
_PERENNIAL_PLANTS_ALLOWED_FIELDS = frozenset({'name', 'species', 'variety', 'plant_type', 'planted_date',
                                              'location', 'rootstock', 'pollinator_group', 'years_to_bearing',
                                              'estimated_yield', 'last_pruned', 'last_fertilized',
                                              'health_status', 'notes'})
_MULTI_YEAR_PLANS_ALLOWED_FIELDS = frozenset({'name', 'description', 'start_year', 'end_year', 'goals',
                                              'milestones', 'carrying_capacity_persons', 'land_acres',
                                              'climate_zone', 'adaptation_strategies', 'status', 'notes'})
_BREEDING_RECORDS_ALLOWED_FIELDS = frozenset({'animal_name', 'species', 'breed', 'sex', 'sire', 'dam',
                                              'birth_date', 'breeding_date', 'expected_due', 'offspring_count',
                                              'offspring_names', 'genetic_notes', 'health_at_breeding',
                                              'status', 'notes'})
_HOMESTEAD_SYSTEMS_ALLOWED_FIELDS = frozenset({'system_name', 'system_type', 'location', 'capacity',
                                               'current_reading', 'last_maintenance', 'next_maintenance',
                                               'condition', 'metrics', 'notes'})
_AQUAPONICS_SYSTEMS_ALLOWED_FIELDS = frozenset({'name', 'system_type', 'location', 'fish_species', 'fish_count',
                                                'plant_species', 'water_volume_gal', 'ph_level', 'ammonia_ppm',
                                                'nitrite_ppm', 'nitrate_ppm', 'temperature_f',
                                                'last_water_change', 'feeding_schedule', 'status', 'notes'})
_RECYCLING_SYSTEMS_ALLOWED_FIELDS = frozenset({'name', 'system_type', 'location', 'capacity', 'input_sources',
                                               'output_products', 'processing_time_days', 'current_status',
                                               'last_turned', 'temperature_f', 'metrics', 'notes'})


def _jp(val):
    """Parse JSON array column."""
    try:
        return json.loads(val)
    except Exception:
        return []


def _jo(val):
    """Parse JSON object column."""
    try:
        return json.loads(val)
    except Exception:
        return {}


def _row(r, json_arrays=None, json_objects=None):
    """Convert row to dict, parsing specified JSON columns."""
    d = dict(r)
    for k in (json_arrays or []):
        if k in d and d[k]:
            d[k] = _jp(d[k])
    for k in (json_objects or []):
        if k in d and d[k]:
            d[k] = _jo(d[k])
    return d


# ─── Food Forest Guilds ───────────────────────────────────────────────

GUILD_JSON_ARRAYS = ['support_species', 'nitrogen_fixers', 'dynamic_accumulators',
                     'pest_confusers', 'ground_covers']


@agriculture_bp.route('/food-forest/guilds')
def api_guilds_list():
    with db_session() as db:
        rows = db.execute('SELECT * FROM food_forest_guilds ORDER BY name LIMIT ? OFFSET ?', get_pagination()).fetchall()
    return jsonify([_row(r, json_arrays=GUILD_JSON_ARRAYS) for r in rows])


@agriculture_bp.route('/food-forest/guilds', methods=['POST'])
def api_guilds_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO food_forest_guilds
               (name, description, central_species, support_species, nitrogen_fixers,
                dynamic_accumulators, pest_confusers, ground_covers, notes)
               VALUES (?,?,?,?,?,?,?,?,?)''',
            (name, data.get('description', ''), data.get('central_species', ''),
             json.dumps(data.get('support_species', [])),
             json.dumps(data.get('nitrogen_fixers', [])),
             json.dumps(data.get('dynamic_accumulators', [])),
             json.dumps(data.get('pest_confusers', [])),
             json.dumps(data.get('ground_covers', [])),
             data.get('notes', ''))
        )
        db.commit()
        row = db.execute('SELECT * FROM food_forest_guilds WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('guild_created', service='agriculture', detail=name)
    return jsonify(_row(row, json_arrays=GUILD_JSON_ARRAYS)), 201


@agriculture_bp.route('/food-forest/guilds/<int:gid>', methods=['PUT'])
def api_guilds_update(gid):
    data = request.get_json() or {}
    allowed = _FOOD_FOREST_GUILDS_ALLOWED_FIELDS
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            v = data[k]
            vals.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append("updated_at = CURRENT_TIMESTAMP")
    vals.append(gid)
    with db_session() as db:
        db.execute(f"UPDATE food_forest_guilds SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM food_forest_guilds WHERE id = ?', (gid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    log_activity('guild_updated', service='agriculture', detail=row['name'])
    return jsonify(_row(row, json_arrays=GUILD_JSON_ARRAYS))


@agriculture_bp.route('/food-forest/guilds/<int:gid>', methods=['DELETE'])
def api_guilds_delete(gid):
    with db_session() as db:
        row = db.execute('SELECT name FROM food_forest_guilds WHERE id = ?', (gid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM food_forest_layers WHERE guild_id = ?', (gid,))
        db.execute('DELETE FROM food_forest_guilds WHERE id = ?', (gid,))
        db.commit()
        log_activity('guild_deleted', service='agriculture', detail=row['name'])
    return jsonify({'ok': True})


# ─── Food Forest Layers ───────────────────────────────────────────────

@agriculture_bp.route('/food-forest/layers')
def api_layers_list():
    guild_id = request.args.get('guild_id', '').strip()
    with db_session() as db:
        if guild_id:
            rows = db.execute(
                'SELECT * FROM food_forest_layers WHERE guild_id = ? ORDER BY layer_type, species',
                (guild_id,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM food_forest_layers ORDER BY layer_type, species LIMIT ? OFFSET ?', get_pagination()).fetchall()
    return jsonify([dict(r) for r in rows])


@agriculture_bp.route('/food-forest/layers', methods=['POST'])
def api_layers_create():
    data = request.get_json() or {}
    species = (data.get('species') or '').strip()
    if not species:
        return jsonify({'error': 'species is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO food_forest_layers
               (design_name, layer_type, species, spacing_ft, mature_height_ft,
                yield_per_year, years_to_production, guild_id, notes)
               VALUES (?,?,?,?,?,?,?,?,?)''',
            (data.get('design_name', ''), data.get('layer_type', 'herbaceous'),
             species, data.get('spacing_ft', 0), data.get('mature_height_ft', 0),
             data.get('yield_per_year', ''), data.get('years_to_production', 0),
             data.get('guild_id'), data.get('notes', ''))
        )
        db.commit()
        row = db.execute('SELECT * FROM food_forest_layers WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('layer_created', service='agriculture', detail=species)
    return jsonify(dict(row)), 201


@agriculture_bp.route('/food-forest/layers/<int:lid>', methods=['PUT'])
def api_layers_update(lid):
    data = request.get_json() or {}
    allowed = _FOOD_FOREST_LAYERS_ALLOWED_FIELDS
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            vals.append(data[k])
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append("updated_at = CURRENT_TIMESTAMP")
    vals.append(lid)
    with db_session() as db:
        db.execute(f"UPDATE food_forest_layers SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM food_forest_layers WHERE id = ?', (lid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    log_activity('layer_updated', service='agriculture', detail=row['species'])
    return jsonify(dict(row))


# ─── Food Forest Yield Timeline ───────────────────────────────────────

@agriculture_bp.route('/food-forest/yield-timeline')
def api_yield_timeline():
    """Project yields per year for next 20 years based on planted layers."""
    with db_session() as db:
        layers = db.execute('SELECT * FROM food_forest_layers').fetchall()
    current_year = datetime.now().year
    timeline = {}
    for yr in range(current_year, current_year + 20):
        timeline[yr] = []
    for layer in layers:
        ytp = layer['years_to_production'] or 0
        start = current_year + ytp
        for yr in range(start, current_year + 20):
            timeline[yr].append({
                'species': layer['species'],
                'layer_type': layer['layer_type'],
                'yield_per_year': layer['yield_per_year'] or 'unknown',
                'years_producing': yr - start,
            })
    result = [{'year': yr, 'producing_species': len(items), 'species': items}
              for yr, items in sorted(timeline.items())]
    return jsonify(result)


# ─── Soil Projects ────────────────────────────────────────────────────

@agriculture_bp.route('/soil')
def api_soil_list():
    ptype = request.args.get('type', '').strip()
    status = request.args.get('status', '').strip()
    with db_session() as db:
        q, params = 'SELECT * FROM soil_projects WHERE 1=1', []
        if ptype:
            q += ' AND project_type = ?'
            params.append(ptype)
        if status:
            q += ' AND status = ?'
            params.append(status)
        q += ' ORDER BY created_at DESC'
        rows = db.execute(q, params).fetchall()
    return jsonify([_row(r, json_arrays=['materials'], json_objects=['soil_test_before', 'soil_test_after'])
                    for r in rows])


@agriculture_bp.route('/soil', methods=['POST'])
def api_soil_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO soil_projects
               (name, project_type, location, dimensions, materials, start_date,
                completion_date, soil_test_before, soil_test_after, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('project_type', 'compost'), data.get('location', ''),
             data.get('dimensions', ''), json.dumps(data.get('materials', [])),
             data.get('start_date', ''), data.get('completion_date', ''),
             json.dumps(data.get('soil_test_before', {})),
             json.dumps(data.get('soil_test_after', {})),
             data.get('status', 'planned'), data.get('notes', ''))
        )
        db.commit()
        row = db.execute('SELECT * FROM soil_projects WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('soil_project_created', service='agriculture', detail=name)
    return jsonify(_row(row, json_arrays=['materials'],
                        json_objects=['soil_test_before', 'soil_test_after'])), 201


@agriculture_bp.route('/soil/<int:sid>', methods=['PUT'])
def api_soil_update(sid):
    data = request.get_json() or {}
    allowed = _SOIL_PROJECTS_ALLOWED_FIELDS
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            v = data[k]
            vals.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append("updated_at = CURRENT_TIMESTAMP")
    vals.append(sid)
    with db_session() as db:
        db.execute(f"UPDATE soil_projects SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM soil_projects WHERE id = ?', (sid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    log_activity('soil_project_updated', service='agriculture', detail=row['name'])
    return jsonify(_row(row, json_arrays=['materials'],
                        json_objects=['soil_test_before', 'soil_test_after']))


@agriculture_bp.route('/soil/<int:sid>', methods=['DELETE'])
def api_soil_delete(sid):
    with db_session() as db:
        row = db.execute('SELECT name FROM soil_projects WHERE id = ?', (sid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM soil_projects WHERE id = ?', (sid,))
        db.commit()
        log_activity('soil_project_deleted', service='agriculture', detail=row['name'])
    return jsonify({'ok': True})


# ─── Perennial Plants ─────────────────────────────────────────────────

@agriculture_bp.route('/perennials')
def api_perennials_list():
    ptype = request.args.get('type', '').strip()
    health = request.args.get('health', '').strip()
    with db_session() as db:
        q, params = 'SELECT * FROM perennial_plants WHERE 1=1', []
        if ptype:
            q += ' AND plant_type = ?'
            params.append(ptype)
        if health:
            q += ' AND health_status = ?'
            params.append(health)
        q += ' ORDER BY name'
        rows = db.execute(q, params).fetchall()
    return jsonify([dict(r) for r in rows])


@agriculture_bp.route('/perennials', methods=['POST'])
def api_perennials_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO perennial_plants
               (name, species, variety, plant_type, planted_date, location,
                rootstock, pollinator_group, years_to_bearing, estimated_yield,
                last_pruned, last_fertilized, health_status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('species', ''), data.get('variety', ''),
             data.get('plant_type', 'fruit_tree'), data.get('planted_date', ''),
             data.get('location', ''), data.get('rootstock', ''),
             data.get('pollinator_group', ''), data.get('years_to_bearing', 0),
             data.get('estimated_yield', ''), data.get('last_pruned', ''),
             data.get('last_fertilized', ''), data.get('health_status', 'good'),
             data.get('notes', ''))
        )
        db.commit()
        row = db.execute('SELECT * FROM perennial_plants WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('perennial_created', service='agriculture', detail=name)
    return jsonify(dict(row)), 201


@agriculture_bp.route('/perennials/<int:pid>', methods=['PUT'])
def api_perennials_update(pid):
    data = request.get_json() or {}
    allowed = _PERENNIAL_PLANTS_ALLOWED_FIELDS
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            vals.append(data[k])
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append("updated_at = CURRENT_TIMESTAMP")
    vals.append(pid)
    with db_session() as db:
        db.execute(f"UPDATE perennial_plants SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM perennial_plants WHERE id = ?', (pid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    log_activity('perennial_updated', service='agriculture', detail=row['name'])
    return jsonify(dict(row))


@agriculture_bp.route('/perennials/<int:pid>', methods=['DELETE'])
def api_perennials_delete(pid):
    with db_session() as db:
        row = db.execute('SELECT name FROM perennial_plants WHERE id = ?', (pid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM perennial_plants WHERE id = ?', (pid,))
        db.commit()
        log_activity('perennial_deleted', service='agriculture', detail=row['name'])
    return jsonify({'ok': True})


# ─── Multi-Year Plans ─────────────────────────────────────────────────

PLAN_JSON_ARRAYS = ['goals', 'milestones', 'adaptation_strategies']


@agriculture_bp.route('/plans')
def api_plans_list():
    with db_session() as db:
        rows = db.execute('SELECT * FROM multi_year_plans ORDER BY start_year DESC LIMIT ? OFFSET ?', get_pagination()).fetchall()
    return jsonify([_row(r, json_arrays=PLAN_JSON_ARRAYS) for r in rows])


@agriculture_bp.route('/plans', methods=['POST'])
def api_plans_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO multi_year_plans
               (name, description, start_year, end_year, goals, milestones,
                carrying_capacity_persons, land_acres, climate_zone,
                adaptation_strategies, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('description', ''),
             data.get('start_year', datetime.now().year),
             data.get('end_year', datetime.now().year + 5),
             json.dumps(data.get('goals', [])),
             json.dumps(data.get('milestones', [])),
             data.get('carrying_capacity_persons', 0),
             data.get('land_acres', 0), data.get('climate_zone', ''),
             json.dumps(data.get('adaptation_strategies', [])),
             data.get('status', 'draft'), data.get('notes', ''))
        )
        db.commit()
        row = db.execute('SELECT * FROM multi_year_plans WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('plan_created', service='agriculture', detail=name)
    return jsonify(_row(row, json_arrays=PLAN_JSON_ARRAYS)), 201


@agriculture_bp.route('/plans/<int:pid>', methods=['PUT'])
def api_plans_update(pid):
    data = request.get_json() or {}
    allowed = _MULTI_YEAR_PLANS_ALLOWED_FIELDS
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            v = data[k]
            vals.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append("updated_at = CURRENT_TIMESTAMP")
    vals.append(pid)
    with db_session() as db:
        db.execute(f"UPDATE multi_year_plans SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM multi_year_plans WHERE id = ?', (pid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    log_activity('plan_updated', service='agriculture', detail=row['name'])
    return jsonify(_row(row, json_arrays=PLAN_JSON_ARRAYS))


@agriculture_bp.route('/plans/<int:pid>/progress')
def api_plans_progress(pid):
    """Milestone completion % and carrying capacity analysis."""
    with db_session() as db:
        row = db.execute('SELECT * FROM multi_year_plans WHERE id = ?', (pid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    plan = _row(row, json_arrays=PLAN_JSON_ARRAYS)
    milestones = plan.get('milestones', [])
    total = len(milestones)
    completed = sum(1 for m in milestones if m.get('status') == 'completed')
    pct = round((completed / total) * 100, 1) if total > 0 else 0
    capacity = plan.get('carrying_capacity_persons', 0)
    acres = plan.get('land_acres', 0)
    persons_per_acre = round(capacity / acres, 2) if acres > 0 else 0
    return jsonify({
        'plan_name': plan['name'],
        'total_milestones': total,
        'completed_milestones': completed,
        'completion_pct': pct,
        'carrying_capacity_persons': capacity,
        'land_acres': acres,
        'persons_per_acre': persons_per_acre,
        'status': plan['status'],
        'milestones': milestones,
    })


# ─── Breeding Records ─────────────────────────────────────────────────

@agriculture_bp.route('/breeding')
def api_breeding_list():
    species = request.args.get('species', '').strip()
    status = request.args.get('status', '').strip()
    with db_session() as db:
        q, params = 'SELECT * FROM breeding_records WHERE 1=1', []
        if species:
            q += ' AND species = ?'
            params.append(species)
        if status:
            q += ' AND status = ?'
            params.append(status)
        q += ' ORDER BY breeding_date DESC'
        rows = db.execute(q, params).fetchall()
    return jsonify([_row(r, json_arrays=['offspring_names']) for r in rows])


@agriculture_bp.route('/breeding', methods=['POST'])
def api_breeding_create():
    data = request.get_json() or {}
    name = (data.get('animal_name') or '').strip()
    if not name:
        return jsonify({'error': 'animal_name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO breeding_records
               (animal_name, species, breed, sex, sire, dam, birth_date,
                breeding_date, expected_due, offspring_count, offspring_names,
                genetic_notes, health_at_breeding, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('species', ''), data.get('breed', ''),
             data.get('sex', 'female'), data.get('sire', ''), data.get('dam', ''),
             data.get('birth_date', ''), data.get('breeding_date', ''),
             data.get('expected_due', ''), data.get('offspring_count', 0),
             json.dumps(data.get('offspring_names', [])),
             data.get('genetic_notes', ''), data.get('health_at_breeding', ''),
             data.get('status', 'active'), data.get('notes', ''))
        )
        db.commit()
        row = db.execute('SELECT * FROM breeding_records WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('breeding_created', service='agriculture', detail=f'{name} ({data.get("species", "")})')
    return jsonify(_row(row, json_arrays=['offspring_names'])), 201


@agriculture_bp.route('/breeding/<int:bid>', methods=['PUT'])
def api_breeding_update(bid):
    data = request.get_json() or {}
    allowed = _BREEDING_RECORDS_ALLOWED_FIELDS
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            v = data[k]
            vals.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append("updated_at = CURRENT_TIMESTAMP")
    vals.append(bid)
    with db_session() as db:
        db.execute(f"UPDATE breeding_records SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM breeding_records WHERE id = ?', (bid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    log_activity('breeding_updated', service='agriculture', detail=row['animal_name'])
    return jsonify(_row(row, json_arrays=['offspring_names']))


@agriculture_bp.route('/breeding/due')
def api_breeding_due():
    """Animals due within N days (default 30)."""
    try:
        days = max(1, min(3650, int(request.args.get('days', 30))))
    except (TypeError, ValueError):
        days = 30
    cutoff = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
    today = datetime.now().strftime('%Y-%m-%d')
    with db_session() as db:
        rows = db.execute(
            '''SELECT * FROM breeding_records
               WHERE expected_due != '' AND expected_due >= ? AND expected_due <= ?
               AND status IN ('bred', 'gestating')
               ORDER BY expected_due''',
            (today, cutoff)
        ).fetchall()
    return jsonify([_row(r, json_arrays=['offspring_names']) for r in rows])


# ─── Feed Tracking ────────────────────────────────────────────────────

@agriculture_bp.route('/feed')
def api_feed_list():
    group = request.args.get('animal_group', '').strip()
    start = request.args.get('start_date', '').strip()
    end = request.args.get('end_date', '').strip()
    with db_session() as db:
        q, params = 'SELECT * FROM feed_tracking WHERE 1=1', []
        if group:
            q += ' AND animal_group = ?'
            params.append(group)
        if start:
            q += ' AND fed_date >= ?'
            params.append(start)
        if end:
            q += ' AND fed_date <= ?'
            params.append(end)
        q += ' ORDER BY fed_date DESC'
        rows = db.execute(q, params).fetchall()
    return jsonify([dict(r) for r in rows])


@agriculture_bp.route('/feed', methods=['POST'])
def api_feed_create():
    data = request.get_json() or {}
    group = (data.get('animal_group') or '').strip()
    if not group:
        return jsonify({'error': 'animal_group is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO feed_tracking
               (animal_group, feed_type, quantity_lbs, cost_per_unit,
                fed_date, fed_by, notes)
               VALUES (?,?,?,?,?,?,?)''',
            (group, data.get('feed_type', ''), data.get('quantity_lbs', 0),
             data.get('cost_per_unit', 0), data.get('fed_date', ''),
             data.get('fed_by', ''), data.get('notes', ''))
        )
        db.commit()
        row = db.execute('SELECT * FROM feed_tracking WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('feed_logged', service='agriculture', detail=f'{group}: {data.get("quantity_lbs", 0)} lbs')
    return jsonify(dict(row)), 201


@agriculture_bp.route('/feed/summary')
def api_feed_summary():
    """Feed consumption summary by animal group with total cost."""
    with db_session() as db:
        rows = db.execute(
            '''SELECT animal_group,
                      COUNT(*) as entries,
                      ROUND(SUM(quantity_lbs), 1) as total_lbs,
                      ROUND(SUM(quantity_lbs * cost_per_unit), 2) as total_cost
               FROM feed_tracking
               GROUP BY animal_group
               ORDER BY total_cost DESC'''
        ).fetchall()
        grand_total = db.execute(
            'SELECT ROUND(SUM(quantity_lbs * cost_per_unit), 2) FROM feed_tracking'
        ).fetchone()[0] or 0
    return jsonify({
        'by_group': [dict(r) for r in rows],
        'grand_total_cost': grand_total,
    })


# ─── Homestead Systems ────────────────────────────────────────────────

@agriculture_bp.route('/homestead')
def api_homestead_list():
    stype = request.args.get('type', '').strip()
    with db_session() as db:
        if stype:
            rows = db.execute(
                'SELECT * FROM homestead_systems WHERE system_type = ? ORDER BY system_name',
                (stype,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM homestead_systems ORDER BY system_name').fetchall()
    return jsonify([_row(r, json_objects=['metrics']) for r in rows])


@agriculture_bp.route('/homestead', methods=['POST'])
def api_homestead_create():
    data = request.get_json() or {}
    name = (data.get('system_name') or '').strip()
    if not name:
        return jsonify({'error': 'system_name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO homestead_systems
               (system_name, system_type, location, capacity, current_reading,
                last_maintenance, next_maintenance, condition, metrics, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('system_type', 'other'), data.get('location', ''),
             data.get('capacity', ''), data.get('current_reading', ''),
             data.get('last_maintenance', ''), data.get('next_maintenance', ''),
             data.get('condition', 'good'), json.dumps(data.get('metrics', {})),
             data.get('notes', ''))
        )
        db.commit()
        row = db.execute('SELECT * FROM homestead_systems WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('homestead_system_created', service='agriculture', detail=name)
    return jsonify(_row(row, json_objects=['metrics'])), 201


@agriculture_bp.route('/homestead/<int:hid>', methods=['PUT'])
def api_homestead_update(hid):
    data = request.get_json() or {}
    allowed = _HOMESTEAD_SYSTEMS_ALLOWED_FIELDS
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            v = data[k]
            vals.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append("updated_at = CURRENT_TIMESTAMP")
    vals.append(hid)
    with db_session() as db:
        db.execute(f"UPDATE homestead_systems SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM homestead_systems WHERE id = ?', (hid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    log_activity('homestead_system_updated', service='agriculture', detail=row['system_name'])
    return jsonify(_row(row, json_objects=['metrics']))


@agriculture_bp.route('/homestead/dashboard')
def api_homestead_dashboard():
    """All systems status overview with maintenance due dates."""
    today = datetime.now().strftime('%Y-%m-%d')
    with db_session() as db:
        systems = db.execute('SELECT * FROM homestead_systems ORDER BY system_type, system_name').fetchall()
        total = len(systems)
        by_condition = {}
        by_type = {}
        maintenance_due = []
        for s in systems:
            cond = s['condition'] or 'unknown'
            by_condition[cond] = by_condition.get(cond, 0) + 1
            st = s['system_type'] or 'other'
            by_type[st] = by_type.get(st, 0) + 1
            if s['next_maintenance'] and s['next_maintenance'] <= today:
                maintenance_due.append({
                    'id': s['id'], 'system_name': s['system_name'],
                    'system_type': s['system_type'],
                    'next_maintenance': s['next_maintenance'],
                    'condition': s['condition'],
                })
    return jsonify({
        'total_systems': total,
        'by_condition': by_condition,
        'by_type': by_type,
        'maintenance_overdue': maintenance_due,
        'overdue_count': len(maintenance_due),
    })


# ─── Aquaponics Systems ───────────────────────────────────────────────

@agriculture_bp.route('/aquaponics')
def api_aquaponics_list():
    stype = request.args.get('type', '').strip()
    with db_session() as db:
        if stype:
            rows = db.execute(
                'SELECT * FROM aquaponics_systems WHERE system_type = ? ORDER BY name',
                (stype,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM aquaponics_systems ORDER BY name').fetchall()
    return jsonify([_row(r, json_arrays=['plant_species']) for r in rows])


@agriculture_bp.route('/aquaponics', methods=['POST'])
def api_aquaponics_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO aquaponics_systems
               (name, system_type, location, fish_species, fish_count,
                plant_species, water_volume_gal, ph_level, ammonia_ppm,
                nitrite_ppm, nitrate_ppm, temperature_f, last_water_change,
                feeding_schedule, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('system_type', 'aquaponics'),
             data.get('location', ''), data.get('fish_species', ''),
             data.get('fish_count', 0),
             json.dumps(data.get('plant_species', [])),
             data.get('water_volume_gal', 0), data.get('ph_level'),
             data.get('ammonia_ppm'), data.get('nitrite_ppm'),
             data.get('nitrate_ppm'), data.get('temperature_f'),
             data.get('last_water_change', ''),
             data.get('feeding_schedule', ''),
             data.get('status', 'active'), data.get('notes', ''))
        )
        db.commit()
        row = db.execute('SELECT * FROM aquaponics_systems WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('aquaponics_created', service='agriculture', detail=name)
    return jsonify(_row(row, json_arrays=['plant_species'])), 201


@agriculture_bp.route('/aquaponics/<int:aid>', methods=['PUT'])
def api_aquaponics_update(aid):
    data = request.get_json() or {}
    allowed = _AQUAPONICS_SYSTEMS_ALLOWED_FIELDS
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            v = data[k]
            vals.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append("updated_at = CURRENT_TIMESTAMP")
    vals.append(aid)
    with db_session() as db:
        db.execute(f"UPDATE aquaponics_systems SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM aquaponics_systems WHERE id = ?', (aid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    log_activity('aquaponics_updated', service='agriculture', detail=row['name'])
    return jsonify(_row(row, json_arrays=['plant_species']))


@agriculture_bp.route('/aquaponics/<int:aid>/water-quality')
def api_aquaponics_water_quality(aid):
    """Water quality snapshot and alert thresholds for a system."""
    with db_session() as db:
        row = db.execute('SELECT * FROM aquaponics_systems WHERE id = ?', (aid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    alerts = []
    ph = row['ph_level']
    if ph is not None:
        if ph < 6.0 or ph > 8.0:
            alerts.append({'param': 'pH', 'value': ph, 'level': 'critical',
                           'message': f'pH {ph} outside safe range (6.0-8.0)'})
        elif ph < 6.5 or ph > 7.5:
            alerts.append({'param': 'pH', 'value': ph, 'level': 'warning',
                           'message': f'pH {ph} outside optimal range (6.5-7.5)'})
    ammonia = row['ammonia_ppm']
    if ammonia is not None and ammonia > 0.5:
        level = 'critical' if ammonia > 1.0 else 'warning'
        alerts.append({'param': 'ammonia', 'value': ammonia, 'level': level,
                       'message': f'Ammonia {ammonia} ppm elevated (target <0.5)'})
    nitrite = row['nitrite_ppm']
    if nitrite is not None and nitrite > 0.5:
        level = 'critical' if nitrite > 1.0 else 'warning'
        alerts.append({'param': 'nitrite', 'value': nitrite, 'level': level,
                       'message': f'Nitrite {nitrite} ppm elevated (target <0.5)'})
    temp = row['temperature_f']
    if temp is not None:
        if temp < 55 or temp > 86:
            alerts.append({'param': 'temperature', 'value': temp, 'level': 'critical',
                           'message': f'Temp {temp}F outside safe range (55-86F)'})
    return jsonify({
        'system_name': row['name'],
        'ph_level': ph,
        'ammonia_ppm': ammonia,
        'nitrite_ppm': nitrite,
        'nitrate_ppm': row['nitrate_ppm'],
        'temperature_f': temp,
        'last_water_change': row['last_water_change'],
        'alerts': alerts,
        'alert_count': len(alerts),
    })


# ─── Recycling / Closed-Loop Systems ──────────────────────────────────

RECYCLING_JSON = {'arrays': ['input_sources', 'output_products'], 'objects': ['metrics']}


@agriculture_bp.route('/recycling')
def api_recycling_list():
    stype = request.args.get('type', '').strip()
    with db_session() as db:
        if stype:
            rows = db.execute(
                'SELECT * FROM recycling_systems WHERE system_type = ? ORDER BY name',
                (stype,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM recycling_systems ORDER BY name').fetchall()
    return jsonify([_row(r, json_arrays=RECYCLING_JSON['arrays'],
                         json_objects=RECYCLING_JSON['objects']) for r in rows])


@agriculture_bp.route('/recycling', methods=['POST'])
def api_recycling_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO recycling_systems
               (name, system_type, location, capacity, input_sources,
                output_products, processing_time_days, current_status,
                last_turned, temperature_f, metrics, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('system_type', 'compost'), data.get('location', ''),
             data.get('capacity', ''),
             json.dumps(data.get('input_sources', [])),
             json.dumps(data.get('output_products', [])),
             data.get('processing_time_days', 0),
             data.get('current_status', 'active'),
             data.get('last_turned', ''), data.get('temperature_f'),
             json.dumps(data.get('metrics', {})), data.get('notes', ''))
        )
        db.commit()
        row = db.execute('SELECT * FROM recycling_systems WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('recycling_created', service='agriculture', detail=name)
    return jsonify(_row(row, json_arrays=RECYCLING_JSON['arrays'],
                        json_objects=RECYCLING_JSON['objects'])), 201


@agriculture_bp.route('/recycling/<int:rid>', methods=['PUT'])
def api_recycling_update(rid):
    data = request.get_json() or {}
    allowed = _RECYCLING_SYSTEMS_ALLOWED_FIELDS
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            v = data[k]
            vals.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append("updated_at = CURRENT_TIMESTAMP")
    vals.append(rid)
    with db_session() as db:
        db.execute(f"UPDATE recycling_systems SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM recycling_systems WHERE id = ?', (rid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    log_activity('recycling_updated', service='agriculture', detail=row['name'])
    return jsonify(_row(row, json_arrays=RECYCLING_JSON['arrays'],
                        json_objects=RECYCLING_JSON['objects']))


@agriculture_bp.route('/recycling/summary')
def api_recycling_summary():
    """Active systems, output products, processing status."""
    with db_session() as db:
        systems = db.execute('SELECT * FROM recycling_systems ORDER BY system_type').fetchall()
    total = len(systems)
    active = 0
    by_type = {}
    all_outputs = []
    processing = []
    for s in systems:
        st = s['system_type'] or 'other'
        by_type[st] = by_type.get(st, 0) + 1
        if s['current_status'] == 'active':
            active += 1
        if s['current_status'] == 'processing':
            processing.append({
                'id': s['id'], 'name': s['name'], 'system_type': st,
                'processing_time_days': s['processing_time_days'],
            })
        outputs = _jp(s['output_products'])
        for o in outputs:
            if o and o not in all_outputs:
                all_outputs.append(o)
    return jsonify({
        'total_systems': total,
        'active_count': active,
        'by_type': by_type,
        'currently_processing': processing,
        'all_output_products': sorted(all_outputs),
    })


# ─── Overall Agriculture Summary ──────────────────────────────────────

@agriculture_bp.route('/summary')
def api_agriculture_summary():
    """Aggregate stats across all agriculture subsystems."""
    with db_session() as db:
        guild_count = db.execute('SELECT COUNT(*) FROM food_forest_guilds').fetchone()[0]
        layer_count = db.execute('SELECT COUNT(*) FROM food_forest_layers').fetchone()[0]
        perennial_health = {}
        for row in db.execute(
            'SELECT health_status, COUNT(*) as cnt FROM perennial_plants GROUP BY health_status'
        ).fetchall():
            perennial_health[row['health_status'] or 'unknown'] = row['cnt']
        perennial_total = sum(perennial_health.values())
        active_soil = db.execute(
            "SELECT COUNT(*) FROM soil_projects WHERE status IN ('planned', 'in_progress')"
        ).fetchone()[0]
        breeding_status = {}
        for row in db.execute(
            'SELECT status, COUNT(*) as cnt FROM breeding_records GROUP BY status'
        ).fetchall():
            breeding_status[row['status'] or 'unknown'] = row['cnt']
        homestead_health = {}
        for row in db.execute(
            'SELECT condition, COUNT(*) as cnt FROM homestead_systems GROUP BY condition'
        ).fetchall():
            homestead_health[row['condition'] or 'unknown'] = row['cnt']
        aqua_alerts = 0
        for row in db.execute(
            "SELECT ph_level, ammonia_ppm, nitrite_ppm, temperature_f FROM aquaponics_systems WHERE status = 'active'"
        ).fetchall():
            if row['ph_level'] is not None and (row['ph_level'] < 6.0 or row['ph_level'] > 8.0):
                aqua_alerts += 1
            elif row['ammonia_ppm'] is not None and row['ammonia_ppm'] > 1.0:
                aqua_alerts += 1
            elif row['nitrite_ppm'] is not None and row['nitrite_ppm'] > 1.0:
                aqua_alerts += 1
            elif row['temperature_f'] is not None and (row['temperature_f'] < 55 or row['temperature_f'] > 86):
                aqua_alerts += 1
        recycling_active = db.execute(
            "SELECT COUNT(*) FROM recycling_systems WHERE current_status = 'active'"
        ).fetchone()[0]
        active_plans = db.execute(
            "SELECT COUNT(*) FROM multi_year_plans WHERE status = 'active'"
        ).fetchone()[0]
    return jsonify({
        'food_forest': {'guilds': guild_count, 'layers': layer_count},
        'perennials': {'total': perennial_total, 'by_health': perennial_health},
        'soil_projects_active': active_soil,
        'breeding': breeding_status,
        'homestead_systems': homestead_health,
        'aquaponics_water_alerts': aqua_alerts,
        'recycling_active': recycling_active,
        'multi_year_plans_active': active_plans,
    })
