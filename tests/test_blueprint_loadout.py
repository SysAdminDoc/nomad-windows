"""Tests for the Bug-Out Bag Loadout Manager.

Covers bag CRUD + item CRUD + enum validation (bag_type / season /
category) + clone (deep-copy with items, unpacked by default) +
mark-inspected + pack-all / unpack-all + weight breakdown + printable
checklist + expiring items + dashboard + summary."""


def _make_bag(client, **overrides):
    body = {
        'name':     overrides.pop('name', 'Primary 72h'),
        'bag_type': overrides.pop('bag_type', '72hour'),
        'season':   overrides.pop('season', 'all'),
    }
    body.update(overrides)
    resp = client.post('/api/loadout/bags', json=body)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()


def _add_item(client, bag_id, **overrides):
    body = {'name': overrides.pop('name', 'Water bottle'),
            'category': overrides.pop('category', 'water'),
            'quantity': overrides.pop('quantity', 1),
            'weight_oz': overrides.pop('weight_oz', 12),
            'packed': overrides.pop('packed', False)}
    body.update(overrides)
    resp = client.post(f'/api/loadout/bags/{bag_id}/items', json=body)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()


class TestLoadoutBagCRUD:
    def test_list_empty(self, client):
        assert client.get('/api/loadout/bags').get_json() == []

    def test_create_minimal(self, client):
        bag = _make_bag(client)
        assert bag['id'] > 0
        assert bag['name'] == 'Primary 72h'
        assert bag['bag_type'] == '72hour'

    def test_create_requires_name(self, client):
        resp = client.post('/api/loadout/bags', json={'bag_type': '72hour'})
        assert resp.status_code == 400

    def test_create_rejects_invalid_bag_type(self, client):
        resp = client.post('/api/loadout/bags',
                           json={'name': 'X', 'bag_type': 'unicorn'})
        assert resp.status_code == 400

    def test_create_rejects_invalid_season(self, client):
        resp = client.post('/api/loadout/bags',
                           json={'name': 'X', 'season': 'monsoon'})
        assert resp.status_code == 400

    def test_create_accepts_case_insensitive_enum(self, client):
        resp = client.post('/api/loadout/bags',
                           json={'name': 'X', 'bag_type': 'GET-HOME'})
        assert resp.status_code == 201
        assert resp.get_json()['bag_type'] == 'get-home'

    def test_list_includes_computed_weight(self, client):
        bag = _make_bag(client)
        _add_item(client, bag['id'], weight_oz=24, quantity=2)
        listing = client.get('/api/loadout/bags').get_json()
        row = next(r for r in listing if r['id'] == bag['id'])
        assert row['item_count'] == 1
        assert row['total_weight_oz'] == 48
        assert row['total_weight_lb'] == 3.0

    def test_get_includes_items_and_stats(self, client):
        bag = _make_bag(client)
        _add_item(client, bag['id'], name='Bottle', weight_oz=12, quantity=1)
        _add_item(client, bag['id'], name='Bars', category='food',
                  weight_oz=2, quantity=6, packed=True)
        full = client.get(f'/api/loadout/bags/{bag["id"]}').get_json()
        assert full['item_count'] == 2
        assert full['total_weight_oz'] == 24  # 12 + (2*6)
        assert full['packed_count'] == 1
        assert full['unpacked_count'] == 1
        assert full['weight_by_category'] == {'food': 12, 'water': 12}

    def test_get_404_when_missing(self, client):
        assert client.get('/api/loadout/bags/99999').status_code == 404

    def test_update_changes_field(self, client):
        bag = _make_bag(client)
        resp = client.put(f'/api/loadout/bags/{bag["id"]}',
                          json={'location': 'front closet'})
        assert resp.status_code == 200
        assert resp.get_json()['location'] == 'front closet'

    def test_update_rejects_invalid_bag_type(self, client):
        bag = _make_bag(client)
        resp = client.put(f'/api/loadout/bags/{bag["id"]}',
                          json={'bag_type': 'space-kit'})
        assert resp.status_code == 400

    def test_update_empty_is_400(self, client):
        bag = _make_bag(client)
        resp = client.put(f'/api/loadout/bags/{bag["id"]}', json={})
        assert resp.status_code == 400

    def test_delete_cascades_items(self, client, db):
        bag = _make_bag(client)
        _add_item(client, bag['id'])
        _add_item(client, bag['id'], name='B2')
        assert db.execute(
            'SELECT COUNT(*) FROM loadout_items WHERE bag_id = ?',
            (bag['id'],)).fetchone()[0] == 2
        assert client.delete(f'/api/loadout/bags/{bag["id"]}').status_code == 200
        assert db.execute(
            'SELECT COUNT(*) FROM loadout_items WHERE bag_id = ?',
            (bag['id'],)).fetchone()[0] == 0

    def test_delete_404_when_missing(self, client):
        assert client.delete('/api/loadout/bags/99999').status_code == 404


class TestLoadoutItemCRUD:
    def test_create_and_list(self, client):
        bag = _make_bag(client)
        _add_item(client, bag['id'], name='Fire starter', category='fire')
        items = client.get(f'/api/loadout/bags/{bag["id"]}/items').get_json()
        assert len(items) == 1
        assert items[0]['name'] == 'Fire starter'
        assert items[0]['category'] == 'fire'

    def test_create_requires_name(self, client):
        bag = _make_bag(client)
        resp = client.post(f'/api/loadout/bags/{bag["id"]}/items',
                           json={'category': 'water'})
        assert resp.status_code == 400

    def test_create_rejects_invalid_category(self, client):
        bag = _make_bag(client)
        resp = client.post(f'/api/loadout/bags/{bag["id"]}/items',
                           json={'name': 'X', 'category': 'crystals'})
        assert resp.status_code == 400

    def test_create_404_on_missing_bag(self, client):
        resp = client.post('/api/loadout/bags/99999/items',
                           json={'name': 'X'})
        assert resp.status_code == 404

    def test_list_404_on_missing_bag(self, client):
        assert client.get('/api/loadout/bags/99999/items').status_code == 404

    def test_list_filter_by_category(self, client):
        bag = _make_bag(client)
        _add_item(client, bag['id'], name='Bottle', category='water')
        _add_item(client, bag['id'], name='Bars', category='food')
        water = client.get(
            f'/api/loadout/bags/{bag["id"]}/items?category=water'
        ).get_json()
        assert [i['name'] for i in water] == ['Bottle']

    def test_update_item(self, client):
        bag = _make_bag(client)
        item = _add_item(client, bag['id'])
        resp = client.put(f'/api/loadout/items/{item["id"]}',
                          json={'quantity': 5, 'notes': 'spare'})
        assert resp.status_code == 200
        assert resp.get_json()['quantity'] == 5
        assert resp.get_json()['notes'] == 'spare'

    def test_update_rejects_invalid_category(self, client):
        bag = _make_bag(client)
        item = _add_item(client, bag['id'])
        resp = client.put(f'/api/loadout/items/{item["id"]}',
                          json={'category': 'mystery'})
        assert resp.status_code == 400

    def test_update_404_when_missing(self, client):
        resp = client.put('/api/loadout/items/99999', json={'quantity': 1})
        assert resp.status_code == 404

    def test_update_empty_is_400(self, client):
        bag = _make_bag(client)
        item = _add_item(client, bag['id'])
        resp = client.put(f'/api/loadout/items/{item["id"]}', json={})
        assert resp.status_code == 400

    def test_delete_item(self, client):
        bag = _make_bag(client)
        item = _add_item(client, bag['id'])
        assert client.delete(f'/api/loadout/items/{item["id"]}').status_code == 200

    def test_delete_item_404(self, client):
        assert client.delete('/api/loadout/items/99999').status_code == 404


class TestLoadoutPackedToggle:
    def test_toggle_flips_packed(self, client):
        bag = _make_bag(client)
        item = _add_item(client, bag['id'], packed=False)
        resp1 = client.put(f'/api/loadout/items/{item["id"]}/toggle-packed')
        assert resp1.get_json()['packed'] == 1
        resp2 = client.put(f'/api/loadout/items/{item["id"]}/toggle-packed')
        assert resp2.get_json()['packed'] == 0

    def test_toggle_404_when_missing(self, client):
        assert client.put(
            '/api/loadout/items/99999/toggle-packed'
        ).status_code == 404

    def test_pack_all_sets_all_items(self, client):
        bag = _make_bag(client)
        _add_item(client, bag['id'], name='A', packed=False)
        _add_item(client, bag['id'], name='B', packed=False)
        resp = client.post(f'/api/loadout/bags/{bag["id"]}/pack-all')
        assert resp.status_code == 200
        full = client.get(f'/api/loadout/bags/{bag["id"]}').get_json()
        assert full['packed_count'] == 2
        assert full['unpacked_count'] == 0

    def test_unpack_all_resets(self, client):
        bag = _make_bag(client)
        _add_item(client, bag['id'], name='A', packed=True)
        client.post(f'/api/loadout/bags/{bag["id"]}/unpack-all')
        full = client.get(f'/api/loadout/bags/{bag["id"]}').get_json()
        assert full['packed_count'] == 0

    def test_pack_all_404_when_missing(self, client):
        assert client.post(
            '/api/loadout/bags/99999/pack-all'
        ).status_code == 404


class TestLoadoutClone:
    def test_clone_deep_copies_items_as_unpacked(self, client):
        bag = _make_bag(client, name='Original')
        _add_item(client, bag['id'], name='A', packed=True)
        _add_item(client, bag['id'], name='B', packed=True)
        resp = client.post(f'/api/loadout/bags/{bag["id"]}/clone', json={})
        assert resp.status_code == 201
        cloned = resp.get_json()
        assert cloned['name'] == 'Original (copy)'
        assert cloned['item_count'] == 2

        # Items are present but marked unpacked
        full = client.get(f'/api/loadout/bags/{cloned["id"]}').get_json()
        assert full['packed_count'] == 0

    def test_clone_custom_name_and_owner(self, client):
        bag = _make_bag(client, owner='Alice')
        resp = client.post(f'/api/loadout/bags/{bag["id"]}/clone',
                           json={'name': 'For Bob', 'owner': 'Bob'})
        cloned = resp.get_json()
        assert cloned['name'] == 'For Bob'
        assert cloned['owner'] == 'Bob'

    def test_clone_404_when_missing(self, client):
        resp = client.post('/api/loadout/bags/99999/clone', json={})
        assert resp.status_code == 404


class TestLoadoutMaintenance:
    def test_mark_inspected_sets_today(self, client):
        bag = _make_bag(client)
        resp = client.post(f'/api/loadout/bags/{bag["id"]}/mark-inspected')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'inspected'
        assert data['last_inspected']
        full = client.get(f'/api/loadout/bags/{bag["id"]}').get_json()
        assert full['last_inspected'] == data['last_inspected']

    def test_mark_inspected_404(self, client):
        assert client.post(
            '/api/loadout/bags/99999/mark-inspected'
        ).status_code == 404


class TestLoadoutAnalytics:
    def test_weight_breakdown(self, client):
        bag = _make_bag(client)
        _add_item(client, bag['id'], name='Water', category='water', weight_oz=32)
        _add_item(client, bag['id'], name='Cans', category='food', weight_oz=8, quantity=4)
        data = client.get(
            f'/api/loadout/bags/{bag["id"]}/weight-breakdown'
        ).get_json()
        # Food is 32 oz, water is 32 oz
        by_cat = {r['category']: r for r in data}
        assert by_cat['water']['total_weight_oz'] == 32.0
        assert by_cat['food']['total_weight_oz'] == 32.0
        assert by_cat['water']['percentage'] == 50.0

    def test_weight_breakdown_404_when_missing(self, client):
        assert client.get(
            '/api/loadout/bags/99999/weight-breakdown'
        ).status_code == 404

    def test_checklist_groups_by_category(self, client):
        bag = _make_bag(client)
        _add_item(client, bag['id'], name='W1', category='water')
        _add_item(client, bag['id'], name='F1', category='food')
        _add_item(client, bag['id'], name='F2', category='food')
        data = client.get(
            f'/api/loadout/bags/{bag["id"]}/checklist'
        ).get_json()
        assert data['bag_name'] == 'Primary 72h'
        assert sorted(data['categories'].keys()) == ['food', 'water']
        assert len(data['categories']['food']) == 2

    def test_expiring_within_90_days(self, client, db):
        bag = _make_bag(client)
        _add_item(client, bag['id'], name='Keep', expiration='')  # no expiration
        # Seed an item expiring in 30 days via direct SQL so we can control date
        db.execute(
            "INSERT INTO loadout_items (bag_id, name, category, quantity, weight_oz, packed, expiration) "
            "VALUES (?, 'Soon', 'food', 1, 1, 0, date('now', '+30 days'))",
            (bag['id'],),
        )
        db.execute(
            "INSERT INTO loadout_items (bag_id, name, category, quantity, weight_oz, packed, expiration) "
            "VALUES (?, 'Later', 'food', 1, 1, 0, date('now', '+200 days'))",
            (bag['id'],),
        )
        db.commit()
        data = client.get(
            f'/api/loadout/bags/{bag["id"]}/expiring'
        ).get_json()
        names = [i['name'] for i in data]
        assert 'Soon' in names
        assert 'Later' not in names
        assert 'Keep' not in names


class TestLoadoutDashboardAndSummary:
    def test_dashboard_empty(self, client):
        data = client.get('/api/loadout/dashboard').get_json()
        assert data['total_bags'] == 0
        assert data['total_items'] == 0
        assert data['heaviest_bag'] is None
        assert data['overweight_bags'] == []

    def test_dashboard_flags_overweight(self, client):
        bag = _make_bag(client, target_weight_lb=1)
        _add_item(client, bag['id'], weight_oz=48)  # 3 lb against 1 lb target
        data = client.get('/api/loadout/dashboard').get_json()
        assert data['total_bags'] == 1
        assert len(data['overweight_bags']) == 1
        assert data['overweight_bags'][0]['actual_weight_lb'] == 3.0

    def test_summary_counts_ready_bags(self, client):
        bag = _make_bag(client)
        _add_item(client, bag['id'], packed=True)
        client.post(f'/api/loadout/bags/{bag["id"]}/mark-inspected')
        data = client.get('/api/loadout/summary').get_json()
        assert data['total_bags'] == 1
        assert data['total_items'] == 1
        assert data['bags_ready'] == 1
