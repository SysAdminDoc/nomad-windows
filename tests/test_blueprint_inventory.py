"""Tests for inventory blueprint routes (extended coverage)."""


class TestInventoryCRUD:
    def test_create_and_list(self, client):
        client.post('/api/inventory', json={'name': 'Flashlight', 'category': 'gear', 'quantity': 2})
        resp = client.get('/api/inventory')
        assert resp.status_code == 200
        items = resp.get_json()
        assert any(i['name'] == 'Flashlight' for i in items)

    def test_create_returns_id(self, client):
        resp = client.post('/api/inventory', json={'name': 'Compass', 'quantity': 1})
        assert resp.status_code == 201
        assert resp.get_json()['id'] is not None

    def test_update_name(self, client):
        create = client.post('/api/inventory', json={'name': 'Old Name'})
        item_id = create.get_json()['id']
        resp = client.put(f'/api/inventory/{item_id}', json={'name': 'New Name'})
        assert resp.status_code == 200

    def test_delete_item(self, client):
        create = client.post('/api/inventory', json={'name': 'Disposable'})
        item_id = create.get_json()['id']
        resp = client.delete(f'/api/inventory/{item_id}')
        assert resp.status_code == 200


class TestInventoryCategories:
    def test_filter_by_category(self, client):
        client.post('/api/inventory', json={'name': 'Med Kit', 'category': 'medical'})
        client.post('/api/inventory', json={'name': 'Jerky', 'category': 'food'})
        resp = client.get('/api/inventory?category=medical')
        data = resp.get_json()
        assert all(i['category'] == 'medical' for i in data)

    def test_default_category(self, client):
        resp = client.post('/api/inventory', json={'name': 'Unknown Item'})
        data = resp.get_json()
        assert data['category'] == 'other'


class TestInventorySearch:
    def test_search_by_name(self, client):
        client.post('/api/inventory', json={'name': 'Solar Panel'})
        resp = client.get('/api/inventory?q=solar')
        data = resp.get_json()
        assert len(data) >= 1
        assert 'Solar' in data[0]['name']

    def test_search_no_results(self, client):
        resp = client.get('/api/inventory?q=ZZZNONEXISTENT')
        data = resp.get_json()
        assert len(data) == 0


class TestShoppingList:
    def test_shopping_list_endpoint(self, client):
        resp = client.get('/api/inventory/shopping-list')
        assert resp.status_code == 200

    def test_shopping_list_with_low_stock(self, client):
        client.post('/api/inventory', json={
            'name': 'Low Stock Batteries',
            'quantity': 1,
            'min_quantity': 50,
        })
        resp = client.get('/api/inventory/shopping-list')
        assert resp.status_code == 200


class TestCheckoutCheckin:
    def test_checkout_requires_person(self, client):
        create = client.post('/api/inventory', json={'name': 'Checkout Test', 'quantity': 5})
        item_id = create.get_json()['id']
        resp = client.post(f'/api/inventory/{item_id}/checkout', json={'quantity': 1})
        assert resp.status_code == 400

    def test_checkout_success(self, client):
        create = client.post('/api/inventory', json={'name': 'Checkout OK', 'quantity': 5})
        item_id = create.get_json()['id']
        resp = client.post(f'/api/inventory/{item_id}/checkout', json={
            'person': 'Jane',
            'quantity': 2,
            'reason': 'Supply run',
        })
        assert resp.status_code == 201


class TestInventorySummary:
    def test_summary_endpoint(self, client):
        resp = client.get('/api/inventory/summary')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'total' in data
        assert 'low_stock' in data

    def test_summary_tracks_items(self, client):
        before = client.get('/api/inventory/summary').get_json()['total']
        client.post('/api/inventory', json={'name': 'Summary Test Item'})
        after = client.get('/api/inventory/summary').get_json()['total']
        assert after == before + 1
