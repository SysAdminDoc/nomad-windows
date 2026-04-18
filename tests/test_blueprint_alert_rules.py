"""Tests for the custom alert-rules engine.

Covers CRUD + validation + toggle + evaluate (per condition type) +
cooldown semantics + triggers history + condition-type catalog +
summary + the custom_sql safety gate."""

import json


def _make_rule(client, **overrides):
    """Create an alert rule and return the JSON body of the 201 response."""
    body = {
        'name': overrides.pop('name', 'Low Water'),
        'condition_type': overrides.pop('condition_type', 'water_low'),
        'threshold': overrides.pop('threshold', 50),
        'comparison': overrides.pop('comparison', 'lt'),
    }
    body.update(overrides)
    resp = client.post('/api/alert-rules', json=body)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()


class TestAlertRulesCRUD:
    def test_list_empty(self, client):
        resp = client.get('/api/alert-rules')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_create_minimal(self, client):
        rule = _make_rule(client)
        assert rule['id'] > 0
        assert rule['name'] == 'Low Water'
        assert rule['condition_type'] == 'water_low'
        assert rule['enabled'] == 1
        # Defaults applied
        assert rule['comparison'] == 'lt'
        assert rule['severity'] == 'warning'
        assert rule['cooldown_minutes'] == 60

    def test_create_requires_name(self, client):
        resp = client.post('/api/alert-rules', json={'condition_type': 'water_low'})
        assert resp.status_code == 400

    def test_create_requires_condition_type(self, client):
        resp = client.post('/api/alert-rules', json={'name': 'Nameless'})
        assert resp.status_code == 400

    def test_create_rejects_unknown_condition_type(self, client):
        resp = client.post('/api/alert-rules', json={
            'name': 'Bogus', 'condition_type': 'aliens_invading',
        })
        assert resp.status_code == 400
        assert 'condition_type' in resp.get_json()['error']

    def test_create_stores_action_data_as_json(self, client):
        rule = _make_rule(client, action_data={'category': 'Food'})
        # Round-trips as JSON-serialized text, parseable by JSON.loads
        parsed = json.loads(rule['action_data'])
        assert parsed == {'category': 'Food'}

    def test_list_returns_created_rules_ordered(self, client):
        _make_rule(client, name='Zeta', enabled=False)
        _make_rule(client, name='Alpha')
        resp = client.get('/api/alert-rules')
        rules = resp.get_json()
        # Enabled rules first; tied by name ASC
        assert rules[0]['name'] == 'Alpha'
        assert rules[0]['enabled'] == 1
        assert rules[-1]['name'] == 'Zeta'

    def test_update_changes_field(self, client):
        rule = _make_rule(client)
        resp = client.put(f'/api/alert-rules/{rule["id"]}', json={
            'threshold': 25, 'severity': 'critical',
        })
        assert resp.status_code == 200
        updated = resp.get_json()
        assert updated['threshold'] == 25
        assert updated['severity'] == 'critical'

    def test_update_rejects_unknown_condition_type(self, client):
        rule = _make_rule(client)
        resp = client.put(f'/api/alert-rules/{rule["id"]}', json={
            'condition_type': 'unknown_thing',
        })
        assert resp.status_code == 400
        assert 'condition_type' in resp.get_json()['error']

    def test_update_rejects_unknown_comparison(self, client):
        rule = _make_rule(client)
        resp = client.put(f'/api/alert-rules/{rule["id"]}', json={
            'comparison': 'approximately',
        })
        assert resp.status_code == 400

    def test_update_404_when_missing(self, client):
        resp = client.put('/api/alert-rules/99999', json={'threshold': 1})
        assert resp.status_code == 404

    def test_update_with_no_fields_is_400(self, client):
        rule = _make_rule(client)
        resp = client.put(f'/api/alert-rules/{rule["id"]}', json={})
        assert resp.status_code == 400

    def test_update_normalizes_enabled_truthy(self, client):
        rule = _make_rule(client)
        # Pass a non-boolean truthy value; blueprint should normalize to 1
        resp = client.put(f'/api/alert-rules/{rule["id"]}', json={'enabled': 'yes'})
        assert resp.status_code == 200
        assert resp.get_json()['enabled'] == 1

    def test_delete_removes_rule(self, client):
        rule = _make_rule(client)
        resp = client.delete(f'/api/alert-rules/{rule["id"]}')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'deleted'
        listing = client.get('/api/alert-rules').get_json()
        assert all(r['id'] != rule['id'] for r in listing)

    def test_delete_404_when_missing(self, client):
        resp = client.delete('/api/alert-rules/99999')
        assert resp.status_code == 404

    def test_toggle_flips_enabled(self, client):
        rule = _make_rule(client)
        resp = client.post(f'/api/alert-rules/{rule["id"]}/toggle')
        assert resp.status_code == 200
        assert resp.get_json()['enabled'] == 0
        resp2 = client.post(f'/api/alert-rules/{rule["id"]}/toggle')
        assert resp2.get_json()['enabled'] == 1

    def test_toggle_404_when_missing(self, client):
        resp = client.post('/api/alert-rules/99999/toggle')
        assert resp.status_code == 404


class TestAlertRulesCatalog:
    def test_condition_types_endpoint(self, client):
        resp = client.get('/api/alert-rules/condition-types')
        assert resp.status_code == 200
        data = resp.get_json()
        for ctype in ('inventory_low', 'water_low', 'fuel_low', 'custom_sql'):
            assert ctype in data


class TestAlertRulesSummary:
    def test_summary_reflects_creation(self, client):
        assert client.get('/api/alert-rules/summary').get_json() == {
            'alert_rules_total': 0,
            'alert_rules_enabled': 0,
            'alert_rule_triggers': 0,
        }
        _make_rule(client, name='One', enabled=True)
        _make_rule(client, name='Two', enabled=False)
        summary = client.get('/api/alert-rules/summary').get_json()
        assert summary['alert_rules_total'] == 2
        assert summary['alert_rules_enabled'] == 1
        assert summary['alert_rule_triggers'] == 0


class TestAlertRulesEvaluate:
    def test_evaluate_empty_returns_none_triggered(self, client):
        resp = client.post('/api/alert-rules/evaluate')
        assert resp.status_code == 200
        assert resp.get_json() == {'triggered': [], 'evaluated': 0}

    def test_evaluate_water_low_triggers(self, client, db):
        # Seed zero water storage → total 0; rule threshold 10, compare lt
        _make_rule(client, name='LowH2O', condition_type='water_low',
                   threshold=10, comparison='lt')
        resp = client.post('/api/alert-rules/evaluate')
        data = resp.get_json()
        assert data['evaluated'] == 1
        assert len(data['triggered']) == 1
        assert data['triggered'][0]['name'] == 'LowH2O'
        # Trigger row was logged
        hist = client.get('/api/alert-rules/triggers').get_json()
        assert len(hist) == 1
        assert hist[0]['rule_name'] == 'LowH2O'

    def test_evaluate_not_triggered_when_gt_threshold(self, client, db):
        _make_rule(client, condition_type='water_low', threshold=0, comparison='lt')
        # Threshold 0 with comparison lt → 0 < 0 is False → not triggered
        data = client.post('/api/alert-rules/evaluate').get_json()
        assert data['triggered'] == []

    def test_evaluate_respects_disabled(self, client):
        _make_rule(client, name='Disabled', condition_type='water_low',
                   threshold=100, enabled=False)
        data = client.post('/api/alert-rules/evaluate').get_json()
        assert data['evaluated'] == 0

    def test_evaluate_cooldown_prevents_double_trigger(self, client, db):
        _make_rule(client, name='Cool', condition_type='water_low',
                   threshold=100, comparison='lt', cooldown_minutes=60)
        first = client.post('/api/alert-rules/evaluate').get_json()
        assert len(first['triggered']) == 1
        # Second evaluate within cooldown — no new trigger
        second = client.post('/api/alert-rules/evaluate').get_json()
        assert second['triggered'] == []
        # History still shows only the first trigger
        hist = client.get('/api/alert-rules/triggers').get_json()
        assert len(hist) == 1

    def test_evaluate_inventory_low_respects_category(self, client, db):
        db.execute(
            "INSERT INTO inventory (name, quantity, unit, category) "
            "VALUES ('Rice', 5, 'lbs', 'Food')"
        )
        db.commit()
        _make_rule(client, name='LowFood', condition_type='inventory_low',
                   threshold=10, comparison='lt',
                   action_data={'category': 'Food'})
        data = client.post('/api/alert-rules/evaluate').get_json()
        assert len(data['triggered']) == 1

    def test_evaluate_custom_sql_safe_select(self, client, db):
        db.execute(
            "INSERT INTO inventory (name, quantity, unit, category) "
            "VALUES ('Water Bottles', 100, 'ea', 'Water')"
        )
        db.commit()
        _make_rule(
            client,
            name='Q',
            condition_type='custom_sql',
            threshold=50,
            comparison='gt',
            action_data={'query': "SELECT SUM(quantity) FROM inventory WHERE category='Water'"},
        )
        data = client.post('/api/alert-rules/evaluate').get_json()
        assert len(data['triggered']) == 1
        assert data['triggered'][0]['current_value'] == 100

    def test_evaluate_custom_sql_refuses_destructive(self, client, db):
        _make_rule(
            client,
            name='Evil',
            condition_type='custom_sql',
            threshold=-1,
            comparison='gt',
            action_data={'query': "DROP TABLE inventory"},
        )
        # _is_safe_select should block → returns 0 → 0 > -1 → True
        # but the key guarantee is the DROP was *not* executed:
        client.post('/api/alert-rules/evaluate')
        # inventory still exists and is queryable
        assert db.execute("SELECT COUNT(*) FROM inventory").fetchone()[0] == 0  # noqa: E712

    def test_evaluate_custom_sql_rejects_chained_statements(self, client, db):
        _make_rule(
            client,
            name='Chain',
            condition_type='custom_sql',
            threshold=-1,
            comparison='gt',
            action_data={'query': "SELECT 1; DELETE FROM inventory"},
        )
        client.post('/api/alert-rules/evaluate')
        # DELETE was refused; schema intact. (inventory is empty-but-existing.)
        assert db.execute("SELECT COUNT(*) FROM inventory").fetchone()[0] == 0

    def test_evaluate_inventory_expiring_uses_threshold_as_days(self, client, db):
        # Threshold acts as "N days" when condition_type is inventory_expiring
        db.execute(
            "INSERT INTO inventory (name, quantity, unit, category, expiration) "
            "VALUES ('Cans', 10, 'ea', 'Food', date('now', '+5 days'))"
        )
        db.commit()
        _make_rule(client, name='Expire',
                   condition_type='inventory_expiring',
                   threshold=10, comparison='gte')
        # 5-day-out item counted → 1 >= N? threshold=10 means "count items
        # expiring within 10 days"; with 1 such item + comparison 'gte 10'
        # (i.e. 1 >= 10) → not triggered.
        data = client.post('/api/alert-rules/evaluate').get_json()
        assert data['triggered'] == []

        # Add more expiring items until count >= threshold
        for _ in range(10):
            db.execute(
                "INSERT INTO inventory (name, quantity, unit, category, expiration) "
                "VALUES ('More', 1, 'ea', 'Food', date('now', '+5 days'))"
            )
        db.commit()
        # Re-enable the rule in case it's in cooldown from a previous trigger
        rule = client.get('/api/alert-rules').get_json()[0]
        db.execute('UPDATE alert_rules SET last_triggered = "" WHERE id = ?', (rule['id'],))
        db.commit()
        data2 = client.post('/api/alert-rules/evaluate').get_json()
        assert len(data2['triggered']) == 1
