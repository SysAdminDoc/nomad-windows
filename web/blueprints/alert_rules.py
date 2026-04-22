"""Custom alert rules engine — generalized condition/action system across all data sources."""

from flask import Blueprint, request, jsonify
from db import db_session, log_activity
from web.blueprints import get_pagination
import json

alert_rules_bp = Blueprint('alert_rules', __name__)

# Supported condition types and their data sources
CONDITION_SOURCES = {
    'inventory_low': 'Inventory quantity below threshold',
    'inventory_expiring': 'Inventory items expiring within N days',
    'water_low': 'Water storage below threshold (gallons)',
    'fuel_low': 'Fuel storage below threshold (gallons)',
    'maintenance_due': 'Vehicle maintenance due within N days',
    'loadout_unpacked': 'Loadout bag has unpacked items above threshold %',
    'medical_expiring': 'Medical supplies expiring within N days',
    'financial_low': 'Cash reserves below threshold',
    'task_overdue': 'Scheduled tasks overdue by N days',
    'pressure_drop': 'Barometric pressure drop (weather)',
    'temperature_extreme': 'Temperature outside range',
    'humidity_high': 'Humidity above threshold',
    'custom_sql': 'Custom SQL query returning numeric value',
}

COMPARISONS = {'lt': '<', 'lte': '<=', 'gt': '>', 'gte': '>=', 'eq': '=', 'ne': '!='}
ACTIONS = ['alert', 'sse_event', 'log_activity', 'set_emergency_level']

_ALERT_RULES_ALLOWED_FIELDS = frozenset({'name', 'condition_type', 'threshold', 'comparison', 'action_type',
                                          'action_data', 'enabled', 'cooldown_minutes', 'severity', 'category', 'description'})


# ─── Rules CRUD ────────────────────────────────────────────────────

@alert_rules_bp.route('/api/alert-rules')
def api_alert_rules_list():
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM alert_rules ORDER BY enabled DESC, name LIMIT ? OFFSET ?',
            get_pagination()
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@alert_rules_bp.route('/api/alert-rules', methods=['POST'])
def api_alert_rules_create():
    data = request.get_json() or {}
    if not data.get('name') or not data.get('condition_type'):
        return jsonify({'error': 'Name and condition_type required'}), 400
    if data['condition_type'] not in CONDITION_SOURCES:
        return jsonify({'error': f'Unknown condition_type. Valid: {", ".join(CONDITION_SOURCES.keys())}'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO alert_rules
               (name, condition_type, threshold, comparison, action_type, action_data,
                enabled, cooldown_minutes, severity, category, description)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            (data['name'], data['condition_type'],
             data.get('threshold', 0), data.get('comparison', 'lt'),
             data.get('action_type', 'alert'),
             json.dumps(data.get('action_data', {})) if isinstance(data.get('action_data'), dict) else data.get('action_data', '{}'),
             1 if data.get('enabled', True) else 0,
             data.get('cooldown_minutes', 60),
             data.get('severity', 'warning'),
             data.get('category', ''),
             data.get('description', ''))
        )
        db.commit()
        log_activity('alert_rule_created', detail=data['name'])
        row = db.execute('SELECT * FROM alert_rules WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@alert_rules_bp.route('/api/alert-rules/<int:rid>', methods=['PUT'])
def api_alert_rules_update(rid):
    data = request.get_json() or {}
    # POST validates condition_type and comparison against allowlists; PUT
    # originally skipped those checks, which let a bad value silently break
    # evaluate(). Validate here with the same rules POST uses.
    if 'condition_type' in data and data['condition_type'] not in CONDITION_SOURCES:
        return jsonify({
            'error': f'Unknown condition_type. Valid: {", ".join(CONDITION_SOURCES.keys())}'
        }), 400
    if 'comparison' in data and data['comparison'] not in COMPARISONS:
        return jsonify({
            'error': f'Unknown comparison. Valid: {", ".join(COMPARISONS.keys())}'
        }), 400
    with db_session() as db:
        existing = db.execute('SELECT id FROM alert_rules WHERE id = ?', (rid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        allowed = _ALERT_RULES_ALLOWED_FIELDS
        sets, vals = [], []
        for col in allowed:
            if col in data:
                val = data[col]
                if col == 'action_data' and isinstance(val, dict):
                    val = json.dumps(val)
                elif col == 'enabled':
                    val = 1 if val else 0
                sets.append(f'{col} = ?')
                vals.append(val)
        if not sets:
            return jsonify({'error': 'No fields to update'}), 400
        sets.append('updated_at = CURRENT_TIMESTAMP')
        vals.append(rid)
        db.execute(f'UPDATE alert_rules SET {", ".join(sets)} WHERE id = ?', vals)
        db.commit()
        row = db.execute('SELECT * FROM alert_rules WHERE id = ?', (rid,)).fetchone()
    return jsonify(dict(row))


@alert_rules_bp.route('/api/alert-rules/<int:rid>', methods=['DELETE'])
def api_alert_rules_delete(rid):
    with db_session() as db:
        existing = db.execute('SELECT id, name FROM alert_rules WHERE id = ?', (rid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM alert_rules WHERE id = ?', (rid,))
        db.commit()
        log_activity('alert_rule_deleted', detail=existing['name'])
    return jsonify({'status': 'deleted'})


@alert_rules_bp.route('/api/alert-rules/<int:rid>/toggle', methods=['POST'])
def api_alert_rules_toggle(rid):
    with db_session() as db:
        existing = db.execute('SELECT id, enabled FROM alert_rules WHERE id = ?', (rid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        new_state = 0 if existing['enabled'] else 1
        db.execute('UPDATE alert_rules SET enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (new_state, rid))
        db.commit()
        row = db.execute('SELECT * FROM alert_rules WHERE id = ?', (rid,)).fetchone()
    return jsonify(dict(row))


# ─── Rule Evaluation Engine ────────────────────────────────────────

@alert_rules_bp.route('/api/alert-rules/evaluate', methods=['POST'])
def api_alert_rules_evaluate():
    """Evaluate all enabled rules and return triggered ones."""
    with db_session() as db:
        rules = db.execute('SELECT * FROM alert_rules WHERE enabled = 1').fetchall()
        triggered = []
        for rule in rules:
            rule = dict(rule)
            current_value = _evaluate_condition(db, rule)
            threshold = rule['threshold']
            comp = rule['comparison']
            is_triggered = _compare(current_value, comp, threshold)

            if is_triggered:
                # Atomic cooldown check-and-set: only claim the trigger if
                # last_triggered is still old enough (or NULL).  This prevents
                # concurrent evaluate() calls from double-firing the same rule.
                cooldown_minutes = rule['cooldown_minutes']
                claimed = db.execute(
                    '''UPDATE alert_rules
                       SET last_triggered = CURRENT_TIMESTAMP
                       WHERE id = ? AND (
                           last_triggered IS NULL
                           OR last_triggered = ''
                           OR CAST((julianday(CURRENT_TIMESTAMP) - julianday(last_triggered)) * 1440 AS REAL) >= ?
                       )''',
                    (rule['id'], cooldown_minutes)
                )
                if claimed.rowcount == 0:
                    continue  # Another caller already claimed it, or still in cooldown

                rule['current_value'] = round(current_value, 2) if isinstance(current_value, float) else current_value
                triggered.append(rule)
                # Log trigger
                db.execute(
                    '''INSERT INTO alert_rule_triggers
                       (rule_id, condition_value, threshold_value, action_taken)
                       VALUES (?,?,?,?)''',
                    (rule['id'], current_value, threshold, rule['action_type'])
                )
        db.commit()
    return jsonify({'triggered': triggered, 'evaluated': len(rules)})


@alert_rules_bp.route('/api/alert-rules/triggers')
def api_alert_rules_triggers():
    """History of rule triggers."""
    limit, _ = get_pagination(default_limit=50, max_limit=500)
    with db_session() as db:
        rows = db.execute(
            '''SELECT t.*, r.name AS rule_name, r.severity, r.category
               FROM alert_rule_triggers t
               LEFT JOIN alert_rules r ON r.id = t.rule_id
               ORDER BY t.triggered_at DESC LIMIT ?''',
            (limit,)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@alert_rules_bp.route('/api/alert-rules/condition-types')
def api_alert_rules_condition_types():
    return jsonify(CONDITION_SOURCES)


def _compare(value, comparison, threshold):
    try:
        v, t = float(value), float(threshold)
    except (ValueError, TypeError):
        return False
    ops = {'lt': v < t, 'lte': v <= t, 'gt': v > t, 'gte': v >= t, 'eq': v == t, 'ne': v != t}
    return ops.get(comparison, False)


def _evaluate_condition(db, rule):
    """Evaluate a rule's condition against current data."""
    ctype = rule['condition_type']
    action_data = {}
    try:
        action_data = json.loads(rule.get('action_data', '{}') or '{}')
    except (json.JSONDecodeError, TypeError):
        pass

    if ctype == 'inventory_low':
        cat = action_data.get('category', '')
        if cat:
            row = db.execute('SELECT COALESCE(SUM(quantity), 0) AS total FROM inventory WHERE category = ?', (cat,)).fetchone()
        else:
            row = db.execute('SELECT COALESCE(SUM(quantity), 0) AS total FROM inventory').fetchone()
        return row['total'] if row else 0

    elif ctype == 'inventory_expiring':
        days = int(rule['threshold'])
        row = db.execute(
            "SELECT COUNT(*) AS total FROM inventory WHERE expiration != '' AND expiration <= date('now', '+' || ? || ' days')",
            (days,)
        ).fetchone()
        return row['total'] if row else 0

    elif ctype == 'water_low':
        row = db.execute('SELECT COALESCE(SUM(current_gallons), 0) AS total FROM water_storage').fetchone()
        return row['total'] if row else 0

    elif ctype == 'fuel_low':
        row = db.execute('SELECT COALESCE(SUM(quantity_gallons), 0) AS total FROM fuel_storage').fetchone()
        return row['total'] if row else 0

    elif ctype == 'maintenance_due':
        days = int(rule['threshold'])
        row = db.execute(
            "SELECT COUNT(*) AS total FROM vehicle_maintenance WHERE status = 'pending' AND next_due_date != '' AND next_due_date <= date('now', '+' || ? || ' days')",
            (days,)
        ).fetchone()
        return row['total'] if row else 0

    elif ctype == 'loadout_unpacked':
        row = db.execute(
            '''SELECT COUNT(*) AS total,
                      SUM(CASE WHEN packed = 0 THEN 1 ELSE 0 END) AS unpacked
               FROM loadout_items'''
        ).fetchone()
        if row and row['total'] > 0:
            return (row['unpacked'] / row['total']) * 100
        return 0

    elif ctype == 'medical_expiring':
        days = int(rule['threshold'])
        row = db.execute(
            "SELECT COUNT(*) AS total FROM inventory WHERE category = 'Medical' AND expiration != '' AND expiration <= date('now', '+' || ? || ' days')",
            (days,)
        ).fetchone()
        return row['total'] if row else 0

    elif ctype == 'financial_low':
        row = db.execute('SELECT COALESCE(SUM(amount), 0) AS total FROM financial_cash').fetchone()
        return row['total'] if row else 0

    elif ctype == 'task_overdue':
        row = db.execute(
            "SELECT COUNT(*) AS total FROM scheduled_tasks WHERE next_due != '' AND next_due < date('now')"
        ).fetchone()
        return row['total'] if row else 0

    elif ctype == 'pressure_drop':
        # Last two pressure readings, return drop
        rows = db.execute(
            'SELECT pressure FROM weather_readings WHERE pressure IS NOT NULL ORDER BY created_at DESC LIMIT 2'
        ).fetchall()
        if len(rows) >= 2:
            return rows[1]['pressure'] - rows[0]['pressure']
        return 0

    elif ctype == 'temperature_extreme':
        row = db.execute(
            'SELECT temperature FROM weather_readings WHERE temperature IS NOT NULL ORDER BY created_at DESC LIMIT 1'
        ).fetchone()
        return row['temperature'] if row else 0

    elif ctype == 'humidity_high':
        row = db.execute(
            'SELECT humidity FROM weather_readings WHERE humidity IS NOT NULL ORDER BY created_at DESC LIMIT 1'
        ).fetchone()
        return row['humidity'] if row else 0

    elif ctype == 'custom_sql':
        query = action_data.get('query', '')
        if not _is_safe_select(query):
            return 0
        try:
            import time as _time
            _deadline = _time.monotonic() + _CUSTOM_SQL_TIMEOUT

            def _check_timeout():
                return 1 if _time.monotonic() > _deadline else 0

            db.set_progress_handler(_check_timeout, 1000)
            try:
                row = db.execute(query).fetchone()
                return row[0] if row else 0
            finally:
                db.set_progress_handler(None, 0)
        except Exception:
            return 0

    return 0


_FORBIDDEN_SQL_KEYWORDS = (
    'insert', 'update', 'delete', 'drop', 'alter', 'create', 'attach',
    'detach', 'replace', 'pragma', 'vacuum', 'reindex',
    'load_extension', 'savepoint',
)

_CUSTOM_SQL_TIMEOUT = 5  # seconds


def _is_safe_select(query):
    """Return True if *query* is a single read-only SELECT/WITH statement.

    Custom alert rules run on every evaluation tick, so a malicious or
    mistakenly-destructive statement would be replayed forever. We accept
    only a single statement that starts with SELECT or WITH ... SELECT,
    rejects semicolons (no statement chaining), and refuses any DDL/DML
    keyword even in subqueries.
    """
    if not isinstance(query, str):
        return False
    q = query.strip().rstrip(';').strip()
    if not q:
        return False
    # No statement chaining
    if ';' in q:
        return False
    lowered = q.lower()
    head = lowered.split(None, 1)[0] if lowered else ''
    if head not in ('select', 'with'):
        return False
    # Reject any forbidden keyword surrounded by word boundaries. This is a
    # conservative check — it will refuse columns literally named "update"
    # even when quoted, which is acceptable for a power-user feature.
    import re as _re
    for kw in _FORBIDDEN_SQL_KEYWORDS:
        if _re.search(rf'\b{kw}\b', lowered):
            return False
    return True


# ─── Summary ───────────────────────────────────────────────────────

@alert_rules_bp.route('/api/alert-rules/summary')
def api_alert_rules_summary():
    with db_session() as db:
        total = db.execute('SELECT COUNT(*) FROM alert_rules').fetchone()[0]
        enabled = db.execute('SELECT COUNT(*) FROM alert_rules WHERE enabled = 1').fetchone()[0]
        triggers = db.execute('SELECT COUNT(*) FROM alert_rule_triggers').fetchone()[0]
    return jsonify({
        'alert_rules_total': total,
        'alert_rules_enabled': enabled,
        'alert_rule_triggers': triggers,
    })
