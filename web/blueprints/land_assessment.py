"""Land Assessment & Property — site scoring, property features, development
planning, BOL comparison, and multi-criteria weighted evaluation."""

import json
import logging
from flask import Blueprint, request, jsonify
from db import db_session, log_activity
from web.blueprints import get_pagination

_log = logging.getLogger(__name__)

land_assessment_bp = Blueprint('land_assessment', __name__)

PROPERTY_TYPES = ['rural', 'suburban', 'urban', 'agricultural', 'wooded', 'desert', 'coastal', 'mountain']
FEATURE_TYPES = [
    'building', 'well', 'spring', 'pond', 'creek', 'fence', 'gate', 'road',
    'trail', 'garden', 'orchard', 'solar', 'generator', 'septic', 'cistern',
    'root_cellar', 'barn', 'shed', 'tower', 'bunker', 'other',
]
ASSESSMENT_CATEGORIES = [
    'water', 'soil', 'agriculture', 'defensibility', 'access', 'timber',
    'climate', 'hazards', 'neighbors', 'legal', 'infrastructure', 'wildlife',
]
DEFAULT_CRITERIA = [
    ('Water availability', 'water', 1.5),
    ('Water quality', 'water', 1.2),
    ('Soil quality for agriculture', 'soil', 1.3),
    ('Growing season length', 'agriculture', 1.0),
    ('Existing agricultural infrastructure', 'agriculture', 0.8),
    ('Defensibility / terrain advantage', 'defensibility', 1.4),
    ('Lines of sight', 'defensibility', 1.0),
    ('Concealment from roads', 'defensibility', 0.9),
    ('Road access quality', 'access', 1.1),
    ('Distance to main highway', 'access', 0.7),
    ('Number of egress routes', 'access', 1.2),
    ('Timber / firewood availability', 'timber', 0.8),
    ('Climate suitability', 'climate', 1.0),
    ('Natural hazard exposure', 'hazards', 1.3),
    ('Flood risk', 'hazards', 1.2),
    ('Wildfire risk', 'hazards', 1.1),
    ('Neighbor density / distance', 'neighbors', 0.9),
    ('Community character', 'neighbors', 0.6),
    ('Zoning / code restrictions', 'legal', 0.7),
    ('Existing structures', 'infrastructure', 0.8),
    ('Power availability', 'infrastructure', 0.7),
    ('Solar potential', 'infrastructure', 0.9),
    ('Game / hunting potential', 'wildlife', 0.6),
]


# ─── Properties CRUD ────────────────────────────────────────────────

@land_assessment_bp.route('/api/properties')
def api_properties_list():
    status = request.args.get('status', '').strip()
    with db_session() as db:
        if status:
            rows = db.execute(
                'SELECT * FROM properties WHERE status = ? ORDER BY total_score DESC', (status,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM properties ORDER BY total_score DESC LIMIT ? OFFSET ?', get_pagination()).fetchall()
    return jsonify([dict(r) for r in rows])


@land_assessment_bp.route('/api/properties', methods=['POST'])
def api_properties_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    cols = [
        'name', 'property_type', 'address', 'county', 'state', 'lat', 'lng',
        'acreage', 'purchase_price', 'current_value', 'ownership', 'access_road',
        'distance_from_home_miles', 'travel_time_hours', 'nearest_town',
        'nearest_town_miles', 'population_density', 'zoning', 'water_rights',
        'mineral_rights', 'status', 'notes',
    ]
    fields, vals = [], []
    for c in cols:
        if c in data:
            fields.append(c)
            vals.append(data[c])
    placeholders = ','.join('?' * len(fields))
    with db_session() as db:
        cur = db.execute(
            f"INSERT INTO properties ({','.join(fields)}) VALUES ({placeholders})", vals
        )
        db.commit()
        log_activity('property_created', detail=name)
        row = db.execute('SELECT * FROM properties WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@land_assessment_bp.route('/api/properties/<int:pid>')
def api_properties_detail(pid):
    with db_session() as db:
        row = db.execute('SELECT * FROM properties WHERE id = ?', (pid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        prop = dict(row)
        prop['assessments'] = [dict(r) for r in db.execute(
            'SELECT * FROM property_assessments WHERE property_id = ? ORDER BY category, criterion',
            (pid,)
        ).fetchall()]
        prop['features'] = [dict(r) for r in db.execute(
            'SELECT * FROM property_features WHERE property_id = ? ORDER BY feature_type, name',
            (pid,)
        ).fetchall()]
        prop['development_plans'] = [dict(r) for r in db.execute(
            'SELECT * FROM development_plans WHERE property_id = ? ORDER BY priority DESC, name',
            (pid,)
        ).fetchall()]
    return jsonify(prop)


@land_assessment_bp.route('/api/properties/<int:pid>', methods=['PUT'])
def api_properties_update(pid):
    data = request.get_json() or {}
    allowed = [
        'name', 'property_type', 'address', 'county', 'state', 'lat', 'lng',
        'acreage', 'purchase_price', 'current_value', 'ownership', 'access_road',
        'distance_from_home_miles', 'travel_time_hours', 'nearest_town',
        'nearest_town_miles', 'population_density', 'zoning', 'water_rights',
        'mineral_rights', 'total_score', 'status', 'notes',
    ]
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
        db.execute(f"UPDATE properties SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM properties WHERE id = ?', (pid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    log_activity('property_updated', detail=row['name'])
    return jsonify(dict(row))


@land_assessment_bp.route('/api/properties/<int:pid>', methods=['DELETE'])
def api_properties_delete(pid):
    with db_session() as db:
        row = db.execute('SELECT name FROM properties WHERE id = ?', (pid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM property_assessments WHERE property_id = ?', (pid,))
        db.execute('DELETE FROM property_features WHERE property_id = ?', (pid,))
        db.execute('DELETE FROM development_plans WHERE property_id = ?', (pid,))
        db.execute('DELETE FROM properties WHERE id = ?', (pid,))
        db.commit()
        log_activity('property_deleted', detail=row['name'])
    return jsonify({'ok': True})


# ─── Property Assessments CRUD ──────────────────────────────────────

@land_assessment_bp.route('/api/properties/<int:pid>/assessments')
def api_assessments_list(pid):
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM property_assessments WHERE property_id = ? ORDER BY category',
            (pid,)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@land_assessment_bp.route('/api/properties/<int:pid>/assessments/seed', methods=['POST'])
def api_assessments_seed(pid):
    """Seed default assessment criteria for a property."""
    seeded = 0
    with db_session() as db:
        for criterion, category, weight in DEFAULT_CRITERIA:
            exists = db.execute(
                'SELECT id FROM property_assessments WHERE property_id = ? AND criterion = ?',
                (pid, criterion)
            ).fetchone()
            if not exists:
                db.execute(
                    '''INSERT INTO property_assessments
                       (property_id, criterion, category, score, weight)
                       VALUES (?,?,?,5,?)''',
                    (pid, criterion, category, weight)
                )
                seeded += 1
        db.commit()
    return jsonify({'seeded': seeded})


@land_assessment_bp.route('/api/properties/<int:pid>/assessments', methods=['POST'])
def api_assessments_create(pid):
    data = request.get_json() or {}
    criterion = (data.get('criterion') or '').strip()
    if not criterion:
        return jsonify({'error': 'criterion is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO property_assessments
               (property_id, criterion, category, score, weight, notes, assessed_date)
               VALUES (?,?,?,?,?,?,?)''',
            (pid, criterion, data.get('category', 'general'),
             data.get('score', 5), data.get('weight', 1.0),
             data.get('notes', ''), data.get('assessed_date', ''))
        )
        db.commit()
        row = db.execute('SELECT * FROM property_assessments WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@land_assessment_bp.route('/api/property-assessments/<int:aid>', methods=['PUT'])
def api_assessments_update(aid):
    data = request.get_json() or {}
    allowed = ['criterion', 'category', 'score', 'weight', 'notes', 'assessed_date']
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            vals.append(data[k])
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    vals.append(aid)
    with db_session() as db:
        db.execute(f"UPDATE property_assessments SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM property_assessments WHERE id = ?', (aid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(row))


@land_assessment_bp.route('/api/property-assessments/<int:aid>', methods=['DELETE'])
def api_assessments_delete(aid):
    with db_session() as db:
        db.execute('DELETE FROM property_assessments WHERE id = ?', (aid,))
        db.commit()
    return jsonify({'ok': True})


# ─── Score Calculation ──────────────────────────────────────────────

@land_assessment_bp.route('/api/properties/<int:pid>/score', methods=['POST'])
def api_properties_score(pid):
    """Recalculate weighted score for a property from its assessments."""
    with db_session() as db:
        rows = db.execute(
            'SELECT score, weight FROM property_assessments WHERE property_id = ?', (pid,)
        ).fetchall()
        if not rows:
            return jsonify({'total_score': 0, 'max_possible': 0, 'percentage': 0})
        weighted_sum = sum(r['score'] * r['weight'] for r in rows)
        max_possible = sum(10 * r['weight'] for r in rows)
        total = round((weighted_sum / max_possible) * 10, 2) if max_possible > 0 else 0
        db.execute('UPDATE properties SET total_score = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                   (total, pid))
        db.commit()
    return jsonify({
        'total_score': total,
        'weighted_sum': round(weighted_sum, 2),
        'max_possible': round(max_possible, 2),
        'percentage': round((weighted_sum / max_possible) * 100, 1) if max_possible > 0 else 0,
        'criteria_count': len(rows),
    })


# ─── Property Features CRUD ────────────────────────────────────────

@land_assessment_bp.route('/api/properties/<int:pid>/features')
def api_features_list(pid):
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM property_features WHERE property_id = ? ORDER BY feature_type', (pid,)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@land_assessment_bp.route('/api/properties/<int:pid>/features', methods=['POST'])
def api_features_create(pid):
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO property_features
               (property_id, feature_type, name, description, lat, lng,
                condition, value_estimate, notes)
               VALUES (?,?,?,?,?,?,?,?,?)''',
            (pid, data.get('feature_type', 'building'), name,
             data.get('description', ''), data.get('lat'), data.get('lng'),
             data.get('condition', 'good'), data.get('value_estimate', 0),
             data.get('notes', ''))
        )
        db.commit()
        row = db.execute('SELECT * FROM property_features WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@land_assessment_bp.route('/api/property-features/<int:fid>', methods=['DELETE'])
def api_features_delete(fid):
    with db_session() as db:
        db.execute('DELETE FROM property_features WHERE id = ?', (fid,))
        db.commit()
    return jsonify({'ok': True})


# ─── Development Plans CRUD ─────────────────────────────────────────

@land_assessment_bp.route('/api/properties/<int:pid>/plans')
def api_dev_plans_list(pid):
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM development_plans WHERE property_id = ? ORDER BY priority DESC, name',
            (pid,)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@land_assessment_bp.route('/api/properties/<int:pid>/plans', methods=['POST'])
def api_dev_plans_create(pid):
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO development_plans
               (property_id, name, category, priority, estimated_cost,
                start_date, target_date, status, impact_score, description,
                materials, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (pid, name, data.get('category', 'infrastructure'),
             data.get('priority', 'medium'), data.get('estimated_cost', 0),
             data.get('start_date', ''), data.get('target_date', ''),
             data.get('status', 'planned'), data.get('impact_score', 5),
             data.get('description', ''),
             str(data.get('materials', '[]')), data.get('notes', ''))
        )
        db.commit()
        log_activity('dev_plan_created', detail=name)
        row = db.execute('SELECT * FROM development_plans WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@land_assessment_bp.route('/api/development-plans/<int:did>', methods=['PUT'])
def api_dev_plans_update(did):
    data = request.get_json() or {}
    allowed = [
        'name', 'category', 'priority', 'estimated_cost', 'actual_cost',
        'start_date', 'target_date', 'completed_date', 'status',
        'impact_score', 'description', 'materials', 'notes',
    ]
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            v = data[k]
            vals.append(str(v) if isinstance(v, (list, dict)) else v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append("updated_at = CURRENT_TIMESTAMP")
    vals.append(did)
    with db_session() as db:
        db.execute(f"UPDATE development_plans SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM development_plans WHERE id = ?', (did,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(row))


@land_assessment_bp.route('/api/development-plans/<int:did>', methods=['DELETE'])
def api_dev_plans_delete(did):
    with db_session() as db:
        db.execute('DELETE FROM development_plans WHERE id = ?', (did,))
        db.commit()
    return jsonify({'ok': True})


# ─── BOL Comparison ─────────────────────────────────────────────────

@land_assessment_bp.route('/api/properties/compare')
def api_properties_compare():
    """Side-by-side comparison of all scored properties."""
    with db_session() as db:
        props = db.execute(
            'SELECT * FROM properties ORDER BY total_score DESC'
        ).fetchall()
        result = []
        for p in props:
            pid = p['id']
            assessments = db.execute(
                'SELECT criterion, category, score, weight FROM property_assessments WHERE property_id = ?',
                (pid,)
            ).fetchall()
            features_count = db.execute(
                'SELECT COUNT(*) FROM property_features WHERE property_id = ?', (pid,)
            ).fetchone()[0]
            plans_count = db.execute(
                'SELECT COUNT(*) FROM development_plans WHERE property_id = ?', (pid,)
            ).fetchone()[0]
            total_dev_cost = db.execute(
                'SELECT COALESCE(SUM(estimated_cost),0) FROM development_plans WHERE property_id = ?',
                (pid,)
            ).fetchone()[0]
            cat_scores = {}
            for a in assessments:
                cat = a['category']
                if cat not in cat_scores:
                    cat_scores[cat] = {'total': 0, 'weight': 0}
                cat_scores[cat]['total'] += a['score'] * a['weight']
                cat_scores[cat]['weight'] += a['weight']
            category_averages = {}
            for cat, vals in cat_scores.items():
                category_averages[cat] = round(
                    (vals['total'] / vals['weight']) if vals['weight'] > 0 else 0, 1
                )
            result.append({
                **dict(p),
                'category_scores': category_averages,
                'features_count': features_count,
                'plans_count': plans_count,
                'total_dev_cost': total_dev_cost,
            })
    return jsonify(result)


# ─── Summary ────────────────────────────────────────────────────────

@land_assessment_bp.route('/api/properties/summary')
def api_properties_summary():
    with db_session() as db:
        total = db.execute('SELECT COUNT(*) FROM properties').fetchone()[0]
        owned = db.execute("SELECT COUNT(*) FROM properties WHERE ownership = 'owned'").fetchone()[0]
        avg_score = db.execute('SELECT AVG(total_score) FROM properties').fetchone()[0] or 0
        features = db.execute('SELECT COUNT(*) FROM property_features').fetchone()[0]
        plans = db.execute('SELECT COUNT(*) FROM development_plans').fetchone()[0]
        active_plans = db.execute(
            "SELECT COUNT(*) FROM development_plans WHERE status IN ('planned','in_progress')"
        ).fetchone()[0]
    return jsonify({
        'total_properties': total,
        'owned': owned,
        'avg_score': round(avg_score, 1),
        'total_features': features,
        'total_dev_plans': plans,
        'active_dev_plans': active_plans,
    })


@land_assessment_bp.route('/api/properties/criteria-defaults')
def api_criteria_defaults():
    """Return default assessment criteria with weights."""
    return jsonify([
        {'criterion': c, 'category': cat, 'weight': w}
        for c, cat, w in DEFAULT_CRITERIA
    ])
