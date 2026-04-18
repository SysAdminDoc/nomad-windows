"""Tests for meal_planning — recipes with ingredients, meals-remaining
calculator, due-score expiry ranker, burn-rate consumption analysis,
standardization advisor, inventory audit workflow, and substitute
items."""


def _make_recipe(client, **overrides):
    body = {
        'name':     overrides.pop('name', 'Rice and Beans'),
        'category': overrides.pop('category', 'meal'),
        'servings': overrides.pop('servings', 4),
    }
    body.update(overrides)
    resp = client.post('/api/recipes', json=body)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()


class TestRecipeCRUD:
    def test_list_empty(self, client):
        assert client.get('/api/recipes').get_json() == []

    def test_create_requires_name(self, client):
        resp = client.post('/api/recipes', json={'category': 'meal'})
        assert resp.status_code == 400

    def test_create_and_detail(self, client):
        _make_recipe(client, ingredients=[
            {'name': 'Rice', 'quantity': 1, 'unit': 'cup'},
            {'name': 'Beans', 'quantity': 0.5, 'unit': 'cup', 'optional': True},
        ])
        rid = client.get('/api/recipes').get_json()[0]['id']
        detail = client.get(f'/api/recipes/{rid}').get_json()
        assert detail['name'] == 'Rice and Beans'
        assert len(detail['ingredients']) == 2
        assert detail['ingredients'][1]['optional'] == 1

    def test_create_stores_tags_as_json(self, client):
        _make_recipe(client, tags=['gluten-free', 'pantry'])
        rid = client.get('/api/recipes').get_json()[0]['id']
        detail = client.get(f'/api/recipes/{rid}').get_json()
        assert detail['tags'] == ['gluten-free', 'pantry']

    def test_detail_404(self, client):
        assert client.get('/api/recipes/99999').status_code == 404

    def test_list_filter_by_category(self, client):
        _make_recipe(client, name='R1', category='breakfast')
        _make_recipe(client, name='R2', category='dinner')
        bfast = client.get('/api/recipes?category=breakfast').get_json()
        assert [r['name'] for r in bfast] == ['R1']

    def test_update_replaces_ingredients(self, client):
        _make_recipe(client, ingredients=[
            {'name': 'Rice', 'quantity': 1, 'unit': 'cup'},
        ])
        rid = client.get('/api/recipes').get_json()[0]['id']
        resp = client.put(f'/api/recipes/{rid}', json={
            'servings': 6,
            'ingredients': [{'name': 'Quinoa', 'quantity': 1, 'unit': 'cup'}],
        })
        assert resp.status_code == 200
        detail = client.get(f'/api/recipes/{rid}').get_json()
        assert detail['servings'] == 6
        assert [i['name'] for i in detail['ingredients']] == ['Quinoa']

    def test_update_preserves_ingredients_when_omitted(self, client):
        _make_recipe(client, ingredients=[
            {'name': 'Rice', 'quantity': 1, 'unit': 'cup'},
        ])
        rid = client.get('/api/recipes').get_json()[0]['id']
        client.put(f'/api/recipes/{rid}', json={'servings': 8})
        detail = client.get(f'/api/recipes/{rid}').get_json()
        assert len(detail['ingredients']) == 1

    def test_update_404(self, client):
        resp = client.put('/api/recipes/99999', json={'servings': 2})
        assert resp.status_code == 404

    def test_update_empty_body(self, client):
        rid = _make_recipe(client)['id']
        resp = client.put(f'/api/recipes/{rid}', json={})
        assert resp.status_code == 400

    def test_delete(self, client):
        rid = _make_recipe(client)['id']
        assert client.delete(f'/api/recipes/{rid}').status_code == 200

    def test_delete_404(self, client):
        assert client.delete('/api/recipes/99999').status_code == 404


class TestMealsRemaining:
    def test_empty_inventory_yields_zero_batches(self, client):
        _make_recipe(client, ingredients=[
            {'name': 'Rice', 'quantity': 1, 'unit': 'cup'},
        ])
        data = client.get('/api/recipes/meals-remaining').get_json()
        # Non-inventory-linked ingredients have available=0
        assert data[0]['batches_possible'] == 0

    def test_batches_bounded_by_scarcest_ingredient(self, client, db):
        # Seed two linked inventory rows
        db.execute(
            "INSERT INTO inventory (name, quantity, unit, category) VALUES ('Rice', 3, 'cup', 'Food')"
        )
        db.execute(
            "INSERT INTO inventory (name, quantity, unit, category) VALUES ('Beans', 1, 'cup', 'Food')"
        )
        db.commit()
        inv_ids = [r['id'] for r in db.execute('SELECT id FROM inventory ORDER BY id').fetchall()]
        _make_recipe(client, servings=4, ingredients=[
            {'name': 'Rice', 'quantity': 1, 'unit': 'cup', 'inventory_id': inv_ids[0]},
            {'name': 'Beans', 'quantity': 1, 'unit': 'cup', 'inventory_id': inv_ids[1]},
        ])
        data = client.get('/api/recipes/meals-remaining').get_json()
        # 3 cups rice / 1 per batch = 3, 1 cup beans / 1 per batch = 1 → min 1 batch
        assert data[0]['batches_possible'] == 1
        assert data[0]['total_servings'] == 4

    def test_optional_ingredients_do_not_limit_batches(self, client, db):
        db.execute(
            "INSERT INTO inventory (name, quantity, unit, category) VALUES ('Rice', 5, 'cup', 'Food')"
        )
        db.commit()
        inv_id = db.execute('SELECT id FROM inventory').fetchone()['id']
        _make_recipe(client, servings=2, ingredients=[
            {'name': 'Rice', 'quantity': 1, 'unit': 'cup', 'inventory_id': inv_id},
            {'name': 'Salt', 'quantity': 1, 'optional': True},
        ])
        data = client.get('/api/recipes/meals-remaining').get_json()
        assert data[0]['batches_possible'] == 5


class TestDueScore:
    def test_skips_recipes_without_expiring_ingredients(self, client):
        _make_recipe(client, ingredients=[{'name': 'Salt', 'quantity': 1}])
        data = client.get('/api/recipes/due-score').get_json()
        assert data == []

    def test_ranks_by_soonest_expiration(self, client, db):
        db.execute(
            "INSERT INTO inventory (name, quantity, unit, category, expiration) "
            "VALUES ('Milk', 1, 'gal', 'Food', date('now', '+3 days'))"
        )
        db.execute(
            "INSERT INTO inventory (name, quantity, unit, category, expiration) "
            "VALUES ('Flour', 5, 'lbs', 'Food', date('now', '+200 days'))"
        )
        db.commit()
        milk_id, flour_id = [r['id'] for r in db.execute('SELECT id FROM inventory ORDER BY id').fetchall()]
        _make_recipe(client, name='Pancakes', ingredients=[
            {'name': 'Flour', 'quantity': 1, 'inventory_id': flour_id},
        ])
        _make_recipe(client, name='Smoothie', ingredients=[
            {'name': 'Milk', 'quantity': 1, 'inventory_id': milk_id},
        ])
        data = client.get('/api/recipes/due-score').get_json()
        # Smoothie (milk expiring in 3 days) should rank higher than pancakes (200 days)
        assert data[0]['name'] == 'Smoothie'
        assert data[0]['urgency'] == 'critical'


class TestBurnRates:
    def test_empty_data(self, client):
        data = client.get('/api/inventory/burn-rates').get_json()
        assert data['window_days'] == 90
        assert data['items'] == []

    def test_respects_window_bounds(self, client):
        # 0 or negative days clamps to minimum 1
        data = client.get('/api/inventory/burn-rates?days=0').get_json()
        assert data['window_days'] == 1

        # Non-numeric falls back to default 90
        data2 = client.get('/api/inventory/burn-rates?days=abc').get_json()
        assert data2['window_days'] == 90

    def test_aggregates_consumption_log(self, client, db):
        db.execute(
            "INSERT INTO inventory (name, quantity, unit, category) VALUES ('Rice', 20, 'cup', 'Food')"
        )
        db.commit()
        inv_id = db.execute('SELECT id FROM inventory').fetchone()['id']
        # 9 cups consumed over the window
        for _ in range(3):
            db.execute(
                "INSERT INTO consumption_log (inventory_id, amount, consumed_at) "
                "VALUES (?, 3, datetime('now', '-5 days'))",
                (inv_id,)
            )
        db.commit()
        data = client.get('/api/inventory/burn-rates?days=90').get_json()
        assert len(data['items']) == 1
        item = data['items'][0]
        assert item['total_consumed'] == 9.0
        assert item['daily_rate'] == 0.1  # 9/90


class TestStandardization:
    def test_no_advisory_for_few_variants(self, client, db):
        db.execute(
            "INSERT INTO inventory (name, quantity, unit, category) VALUES ('Batteries', 10, 'ea', 'Tools')"
        )
        db.commit()
        assert client.get('/api/inventory/standardization').get_json() == []

    def test_advisory_when_three_or_more_variants(self, client, db):
        for name in ('AA', 'AAA', 'C', 'D'):
            db.execute(
                "INSERT INTO inventory (name, quantity, unit, category) VALUES (?, 10, 'ea', 'Batteries')",
                (name,)
            )
        db.commit()
        data = client.get('/api/inventory/standardization').get_json()
        assert len(data) == 1
        assert data[0]['category'] == 'Batteries'
        assert data[0]['variant_count'] == 4


class TestInventoryAudit:
    def test_start_creates_audit_with_items(self, client, db):
        db.execute(
            "INSERT INTO inventory (name, quantity, unit, category) VALUES ('A', 10, 'ea', 'Food')"
        )
        db.execute(
            "INSERT INTO inventory (name, quantity, unit, category) VALUES ('B', 20, 'ea', 'Food')"
        )
        db.commit()
        resp = client.post('/api/inventory/audit/start')
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['total_items'] == 2
        audit = client.get(f'/api/inventory/audit/{data["audit_id"]}').get_json()
        assert len(audit['items']) == 2

    def test_detail_404(self, client):
        assert client.get('/api/inventory/audit/99999').status_code == 404

    def test_verify_flags_discrepancy(self, client, db):
        db.execute(
            "INSERT INTO inventory (name, quantity, unit, category) VALUES ('A', 10, 'ea', 'Food')"
        )
        db.commit()
        audit = client.post('/api/inventory/audit/start').get_json()
        item_id = client.get(
            f'/api/inventory/audit/{audit["audit_id"]}'
        ).get_json()['items'][0]['id']

        # Matching qty - no discrepancy
        ok = client.post(f'/api/inventory/audit/{audit["audit_id"]}/verify', json={
            'item_id': item_id, 'actual_qty': 10,
        }).get_json()
        assert ok['discrepancy'] is False

        # Mismatch qty - discrepancy flagged
        bad = client.post(f'/api/inventory/audit/{audit["audit_id"]}/verify', json={
            'item_id': item_id, 'actual_qty': 8,
        }).get_json()
        assert bad['discrepancy'] is True

    def test_verify_requires_item_and_qty(self, client):
        audit = client.post('/api/inventory/audit/start').get_json()
        resp = client.post(
            f'/api/inventory/audit/{audit["audit_id"]}/verify', json={}
        )
        assert resp.status_code == 400

    def test_verify_rejects_non_numeric(self, client, db):
        db.execute(
            "INSERT INTO inventory (name, quantity, unit, category) VALUES ('A', 10, 'ea', 'Food')"
        )
        db.commit()
        audit = client.post('/api/inventory/audit/start').get_json()
        resp = client.post(
            f'/api/inventory/audit/{audit["audit_id"]}/verify',
            json={'item_id': 'foo', 'actual_qty': 'bar'},
        )
        assert resp.status_code == 400

    def test_verify_404_for_missing_audit_item(self, client):
        audit = client.post('/api/inventory/audit/start').get_json()
        resp = client.post(
            f'/api/inventory/audit/{audit["audit_id"]}/verify',
            json={'item_id': 99999, 'actual_qty': 1},
        )
        assert resp.status_code == 404

    def test_complete_applies_corrections(self, client, db):
        db.execute(
            "INSERT INTO inventory (name, quantity, unit, category) VALUES ('A', 10, 'ea', 'Food')"
        )
        db.commit()
        inv_id = db.execute('SELECT id FROM inventory').fetchone()['id']
        audit = client.post('/api/inventory/audit/start').get_json()
        item_id = client.get(
            f'/api/inventory/audit/{audit["audit_id"]}'
        ).get_json()['items'][0]['id']
        client.post(f'/api/inventory/audit/{audit["audit_id"]}/verify',
                    json={'item_id': item_id, 'actual_qty': 7})

        resp = client.post(
            f'/api/inventory/audit/{audit["audit_id"]}/complete',
            json={'apply_corrections': True},
        )
        assert resp.status_code == 200
        # Inventory quantity was corrected
        qty = db.execute(
            'SELECT quantity FROM inventory WHERE id = ?', (inv_id,)
        ).fetchone()['quantity']
        assert qty == 7

    def test_complete_without_corrections_leaves_inventory(self, client, db):
        db.execute(
            "INSERT INTO inventory (name, quantity, unit, category) VALUES ('A', 10, 'ea', 'Food')"
        )
        db.commit()
        inv_id = db.execute('SELECT id FROM inventory').fetchone()['id']
        audit = client.post('/api/inventory/audit/start').get_json()
        item_id = client.get(
            f'/api/inventory/audit/{audit["audit_id"]}'
        ).get_json()['items'][0]['id']
        client.post(f'/api/inventory/audit/{audit["audit_id"]}/verify',
                    json={'item_id': item_id, 'actual_qty': 7})

        client.post(
            f'/api/inventory/audit/{audit["audit_id"]}/complete',
            json={'apply_corrections': False},
        )
        qty = db.execute(
            'SELECT quantity FROM inventory WHERE id = ?', (inv_id,)
        ).fetchone()['quantity']
        assert qty == 10

    def test_complete_404(self, client):
        resp = client.post('/api/inventory/audit/99999/complete', json={})
        assert resp.status_code == 404


class TestSubstitutes:
    def test_create_requires_both_ids(self, client):
        resp = client.post('/api/inventory/substitutes', json={'inventory_id': 1})
        assert resp.status_code == 400

    def test_create_rejects_self_substitute(self, client):
        resp = client.post('/api/inventory/substitutes', json={
            'inventory_id': 1, 'substitute_id': 1,
        })
        assert resp.status_code == 400

    def test_create_list_delete_roundtrip(self, client, db):
        db.execute("INSERT INTO inventory (name, quantity, unit, category) VALUES ('Rice', 10, 'lb', 'Food')")
        db.execute("INSERT INTO inventory (name, quantity, unit, category) VALUES ('Quinoa', 5, 'lb', 'Food')")
        db.commit()
        ids = [r['id'] for r in db.execute('SELECT id FROM inventory ORDER BY id').fetchall()]
        resp = client.post('/api/inventory/substitutes', json={
            'inventory_id': ids[0], 'substitute_id': ids[1],
            'ratio': 1.0, 'notes': 'Substitute 1:1',
        })
        assert resp.status_code == 201
        subs = client.get(f'/api/inventory/substitutes/{ids[0]}').get_json()
        assert len(subs) == 1
        assert subs[0]['substitute_name'] == 'Quinoa'
        sub_id = subs[0]['id']
        assert client.delete(f'/api/inventory/substitutes/{sub_id}').status_code == 200

    def test_delete_404(self, client):
        assert client.delete('/api/inventory/substitutes/99999').status_code == 404
