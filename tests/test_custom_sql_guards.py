"""Regression coverage for the stored-SQL guards on alert rules and
readiness goals.

Both modules let power users attach a SQL snippet to a rule and evaluate
it on every tick. The underlying `_is_safe_select` guard must accept a
single read-only SELECT/WITH and refuse anything that mutates data or
chains statements — otherwise a single poisoned rule re-runs forever.
"""

import json


def test_alert_rules_custom_sql_accepts_select(client, db):
    """A plain SELECT in a custom_sql rule should evaluate without erroring."""
    # Seed a row we can COUNT.
    db.execute("INSERT INTO inventory (name, category, quantity) VALUES (?, ?, ?)",
               ("alert-rule-probe-item", "food", 1))
    db.commit()

    resp = client.post('/api/alert-rules', json={
        'name': 'Probe: count inventory',
        'condition_type': 'custom_sql',
        'threshold': 0,
        'comparison': 'gt',
        'action_type': 'alert',
        'action_data': {
            'query': "SELECT COUNT(*) FROM inventory WHERE name = 'alert-rule-probe-item'"
        },
    })
    assert resp.status_code == 201, resp.get_data(as_text=True)


def test_alert_rules_custom_sql_refuses_ddl():
    """_is_safe_select should reject DDL/DML even inside a custom_sql rule."""
    from web.blueprints.alert_rules import _is_safe_select
    assert _is_safe_select('SELECT 1') is True
    assert _is_safe_select('WITH t AS (SELECT 1) SELECT * FROM t') is True
    assert _is_safe_select('SELECT 1; DROP TABLE users') is False
    assert _is_safe_select('DROP TABLE users') is False
    assert _is_safe_select('UPDATE inventory SET quantity = 0') is False
    assert _is_safe_select('DELETE FROM alerts') is False
    assert _is_safe_select('INSERT INTO inventory VALUES (1)') is False
    assert _is_safe_select('PRAGMA journal_mode=DELETE') is False
    assert _is_safe_select('') is False
    assert _is_safe_select(None) is False


def test_readiness_goals_custom_sql_refuses_ddl():
    """Readiness goals share the same guard pattern."""
    from web.blueprints.readiness_goals import _is_safe_select
    assert _is_safe_select('SELECT 1') is True
    assert _is_safe_select('DROP TABLE readiness_goals') is False
    assert _is_safe_select('DELETE FROM readiness_goals') is False
    assert _is_safe_select('UPDATE readiness_goals SET threshold=0') is False
    assert _is_safe_select('SELECT 1; DELETE FROM readiness_goals') is False
