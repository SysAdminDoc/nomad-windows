"""Goal-based readiness system — target vs actual per category with % scoring."""

from flask import Blueprint, request, jsonify
from db import db_session, log_activity
from web.blueprints import get_pagination

readiness_goals_bp = Blueprint('readiness_goals', __name__)


# ─── Readiness Goals CRUD ──────────────────────────────────────────

@readiness_goals_bp.route('/api/readiness-goals')
def api_readiness_goals_list():
    with db_session() as db:
        rows = db.execute('SELECT * FROM readiness_goals ORDER BY category, name LIMIT ? OFFSET ?', get_pagination()).fetchall()
    return jsonify([dict(r) for r in rows])


@readiness_goals_bp.route('/api/readiness-goals', methods=['POST'])
def api_readiness_goals_create():
    data = request.get_json() or {}
    if not data.get('name') or not data.get('category'):
        return jsonify({'error': 'Name and category required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO readiness_goals
               (name, category, target_days, target_quantity, target_unit,
                metric_source, metric_query, priority, notes)
               VALUES (?,?,?,?,?,?,?,?,?)''',
            (data['name'], data['category'],
             data.get('target_days', 30), data.get('target_quantity', 0),
             data.get('target_unit', ''), data.get('metric_source', 'inventory'),
             data.get('metric_query', ''), data.get('priority', 'medium'),
             data.get('notes', ''))
        )
        db.commit()
        log_activity('readiness_goal_created', detail=data['name'])
        row = db.execute('SELECT * FROM readiness_goals WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@readiness_goals_bp.route('/api/readiness-goals/<int:gid>', methods=['PUT'])
def api_readiness_goals_update(gid):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT id FROM readiness_goals WHERE id = ?', (gid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        allowed = ['name', 'category', 'target_days', 'target_quantity', 'target_unit',
                    'metric_source', 'metric_query', 'priority', 'notes']
        sets, vals = [], []
        for col in allowed:
            if col in data:
                sets.append(f'{col} = ?')
                vals.append(data[col])
        if not sets:
            return jsonify({'error': 'No fields to update'}), 400
        sets.append('updated_at = CURRENT_TIMESTAMP')
        vals.append(gid)
        db.execute(f'UPDATE readiness_goals SET {", ".join(sets)} WHERE id = ?', vals)
        db.commit()
        row = db.execute('SELECT * FROM readiness_goals WHERE id = ?', (gid,)).fetchone()
    return jsonify(dict(row))


@readiness_goals_bp.route('/api/readiness-goals/<int:gid>', methods=['DELETE'])
def api_readiness_goals_delete(gid):
    with db_session() as db:
        existing = db.execute('SELECT id, name FROM readiness_goals WHERE id = ?', (gid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM readiness_goals WHERE id = ?', (gid,))
        db.commit()
        log_activity('readiness_goal_deleted', detail=existing['name'])
    return jsonify({'status': 'deleted'})


# ─── Readiness Dashboard — Compute % of Goal Met ───────────────────

@readiness_goals_bp.route('/api/readiness-goals/dashboard')
def api_readiness_goals_dashboard():
    """Compute current vs target for every goal. Returns per-goal and aggregate scores."""
    with db_session() as db:
        goals = db.execute('SELECT * FROM readiness_goals ORDER BY category, name').fetchall()
        results = []
        for g in goals:
            g = dict(g)
            current = _compute_current(db, g)
            target = g['target_quantity'] if g['target_quantity'] > 0 else (g['target_days'] if g['target_days'] > 0 else 1)
            pct = min(round((current / target) * 100, 1), 100) if target > 0 else 0
            g['current_value'] = round(current, 2)
            g['target_value'] = target
            g['percent'] = pct
            g['status'] = 'met' if pct >= 100 else ('warning' if pct >= 60 else 'critical')
            results.append(g)

        # Aggregate by category
        categories = {}
        for r in results:
            cat = r['category']
            if cat not in categories:
                categories[cat] = {'category': cat, 'goals': 0, 'met': 0, 'total_pct': 0}
            categories[cat]['goals'] += 1
            categories[cat]['total_pct'] += r['percent']
            if r['percent'] >= 100:
                categories[cat]['met'] += 1
        for cat in categories.values():
            cat['avg_pct'] = round(cat['total_pct'] / cat['goals'], 1) if cat['goals'] > 0 else 0

        overall = round(sum(r['percent'] for r in results) / len(results), 1) if results else 0

    return jsonify({
        'goals': results,
        'categories': list(categories.values()),
        'overall_pct': overall,
        'total_goals': len(results),
        'goals_met': sum(1 for r in results if r['percent'] >= 100),
    })


def _compute_current(db, goal):
    """Look up actual quantity from the metric source."""
    src = goal.get('metric_source', 'inventory')
    query = goal.get('metric_query', '')
    category = goal.get('category', '')

    if src == 'inventory':
        # Sum quantity from inventory where category matches
        cat_filter = query if query else category
        row = db.execute(
            'SELECT COALESCE(SUM(quantity), 0) AS total FROM inventory WHERE category = ?',
            (cat_filter,)
        ).fetchone()
        return row['total'] if row else 0

    elif src == 'inventory_days':
        # Days of supply: total quantity / daily usage
        cat_filter = query if query else category
        row = db.execute(
            '''SELECT COALESCE(SUM(quantity), 0) AS total,
                      COALESCE(SUM(CASE WHEN daily_usage > 0 THEN daily_usage ELSE 0 END), 0) AS usage
               FROM inventory WHERE category = ?''',
            (cat_filter,)
        ).fetchone()
        if row and row['usage'] > 0:
            return row['total'] / row['usage']
        return row['total'] if row else 0

    elif src == 'water':
        # Total gallons from water storage
        row = db.execute(
            'SELECT COALESCE(SUM(current_gallons), 0) AS total FROM water_storage'
        ).fetchone()
        return row['total'] if row else 0

    elif src == 'water_days':
        # Water days: total gallons / gallons per person per day (1 gal/person)
        row = db.execute(
            'SELECT COALESCE(SUM(current_gallons), 0) AS total FROM water_storage'
        ).fetchone()
        return row['total'] if row else 0

    elif src == 'financial_cash':
        row = db.execute(
            'SELECT COALESCE(SUM(amount), 0) AS total FROM financial_cash'
        ).fetchone()
        return row['total'] if row else 0

    elif src == 'financial_metals':
        row = db.execute(
            'SELECT COALESCE(SUM(weight_oz * spot_price), 0) AS total FROM financial_metals'
        ).fetchone()
        return row['total'] if row else 0

    elif src == 'loadout_bags':
        row = db.execute(
            'SELECT COUNT(*) AS total FROM loadout_bags'
        ).fetchone()
        return row['total'] if row else 0

    elif src == 'loadout_packed':
        # Percentage of items packed
        row = db.execute(
            '''SELECT COUNT(*) AS total,
                      SUM(CASE WHEN packed = 1 THEN 1 ELSE 0 END) AS packed
               FROM loadout_items'''
        ).fetchone()
        if row and row['total'] > 0:
            return (row['packed'] / row['total']) * 100
        return 0

    elif src == 'vehicles':
        row = db.execute(
            'SELECT COUNT(*) AS total FROM vehicles'
        ).fetchone()
        return row['total'] if row else 0

    elif src == 'fuel':
        row = db.execute(
            'SELECT COALESCE(SUM(quantity_gallons), 0) AS total FROM fuel_storage'
        ).fetchone()
        return row['total'] if row else 0

    elif src == 'medical':
        cat_filter = query if query else 'Medical'
        row = db.execute(
            'SELECT COALESCE(SUM(quantity), 0) AS total FROM inventory WHERE category = ?',
            (cat_filter,)
        ).fetchone()
        return row['total'] if row else 0

    elif src == 'contacts':
        row = db.execute('SELECT COUNT(*) AS total FROM contacts').fetchone()
        return row['total'] if row else 0

    elif src == 'custom_sql':
        # Advanced: run arbitrary read-only query (must return single 'total' column)
        if query:
            try:
                row = db.execute(query).fetchone()
                return row[0] if row else 0
            except Exception:
                return 0
        return 0

    return 0


# ─── Readiness Presets (quick-start goal templates) ─────────────────

@readiness_goals_bp.route('/api/readiness-goals/presets')
def api_readiness_goals_presets():
    """Return recommended goal presets for common preparedness levels."""
    presets = {
        '72_hour': [
            {'name': '3 days of water', 'category': 'Water', 'target_days': 3, 'target_quantity': 3, 'metric_source': 'water_days', 'priority': 'critical'},
            {'name': '3 days of food', 'category': 'Food', 'target_days': 3, 'target_quantity': 3, 'metric_source': 'inventory_days', 'metric_query': 'Food', 'priority': 'critical'},
            {'name': 'First aid kit', 'category': 'Medical', 'target_quantity': 10, 'metric_source': 'medical', 'priority': 'high'},
            {'name': 'Bug-out bag ready', 'category': 'Loadout', 'target_quantity': 1, 'metric_source': 'loadout_bags', 'priority': 'high'},
            {'name': 'Emergency cash', 'category': 'Financial', 'target_quantity': 200, 'metric_source': 'financial_cash', 'priority': 'medium'},
        ],
        '2_week': [
            {'name': '14 days of water', 'category': 'Water', 'target_days': 14, 'target_quantity': 14, 'metric_source': 'water_days', 'priority': 'critical'},
            {'name': '14 days of food', 'category': 'Food', 'target_days': 14, 'target_quantity': 14, 'metric_source': 'inventory_days', 'metric_query': 'Food', 'priority': 'critical'},
            {'name': 'Medical supplies (30 items)', 'category': 'Medical', 'target_quantity': 30, 'metric_source': 'medical', 'priority': 'high'},
            {'name': 'Emergency fund $500', 'category': 'Financial', 'target_quantity': 500, 'metric_source': 'financial_cash', 'priority': 'high'},
            {'name': 'Vehicle ready', 'category': 'Transport', 'target_quantity': 1, 'metric_source': 'vehicles', 'priority': 'medium'},
            {'name': 'Fuel reserve (10 gal)', 'category': 'Fuel', 'target_quantity': 10, 'metric_source': 'fuel', 'priority': 'medium'},
        ],
        '90_day': [
            {'name': '90 days of water', 'category': 'Water', 'target_days': 90, 'target_quantity': 90, 'metric_source': 'water_days', 'priority': 'critical'},
            {'name': '90 days of food', 'category': 'Food', 'target_days': 90, 'target_quantity': 90, 'metric_source': 'inventory_days', 'metric_query': 'Food', 'priority': 'critical'},
            {'name': 'Medical stockpile (100 items)', 'category': 'Medical', 'target_quantity': 100, 'metric_source': 'medical', 'priority': 'high'},
            {'name': 'Emergency fund $2000', 'category': 'Financial', 'target_quantity': 2000, 'metric_source': 'financial_cash', 'priority': 'high'},
            {'name': 'Precious metals ($500)', 'category': 'Financial', 'target_quantity': 500, 'metric_source': 'financial_metals', 'priority': 'medium'},
            {'name': 'Fuel reserve (25 gal)', 'category': 'Fuel', 'target_quantity': 25, 'metric_source': 'fuel', 'priority': 'medium'},
            {'name': 'Barter inventory (20 items)', 'category': 'Barter', 'target_quantity': 20, 'metric_source': 'inventory', 'metric_query': 'Barter', 'priority': 'low'},
            {'name': 'Emergency contacts (10)', 'category': 'Network', 'target_quantity': 10, 'metric_source': 'contacts', 'priority': 'medium'},
        ],
    }
    return jsonify(presets)


@readiness_goals_bp.route('/api/readiness-goals/apply-preset', methods=['POST'])
def api_readiness_goals_apply_preset():
    """Apply a preset template, creating goals that don't already exist."""
    data = request.get_json() or {}
    preset_name = data.get('preset', '72_hour')
    presets = {
        '72_hour': 'api_readiness_goals_presets',
        '2_week': 'api_readiness_goals_presets',
        '90_day': 'api_readiness_goals_presets',
    }
    if preset_name not in presets:
        return jsonify({'error': 'Unknown preset'}), 400

    # Get presets inline
    all_presets = api_readiness_goals_presets().get_json()
    goals = all_presets.get(preset_name, [])
    created = 0
    with db_session() as db:
        for g in goals:
            existing = db.execute(
                'SELECT id FROM readiness_goals WHERE name = ?', (g['name'],)
            ).fetchone()
            if not existing:
                db.execute(
                    '''INSERT INTO readiness_goals
                       (name, category, target_days, target_quantity, target_unit,
                        metric_source, metric_query, priority, notes)
                       VALUES (?,?,?,?,?,?,?,?,?)''',
                    (g['name'], g['category'], g.get('target_days', 0),
                     g.get('target_quantity', 0), g.get('target_unit', ''),
                     g.get('metric_source', 'inventory'), g.get('metric_query', ''),
                     g.get('priority', 'medium'), '')
                )
                created += 1
        db.commit()
        log_activity('readiness_preset_applied', detail=f'{preset_name}: {created} goals created')
    return jsonify({'preset': preset_name, 'created': created}), 201


# ─── Summary ───────────────────────────────────────────────────────

@readiness_goals_bp.route('/api/readiness-goals/summary')
def api_readiness_goals_summary():
    with db_session() as db:
        total = db.execute('SELECT COUNT(*) FROM readiness_goals').fetchone()[0]
    return jsonify({'readiness_goals_count': total})
