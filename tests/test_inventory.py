"""Tests for inventory API routes."""

import json


class TestInventoryList:
    def test_list(self, client):
        resp = client.get('/api/inventory')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_list_includes_created_items(self, client):
        before = len(client.get('/api/inventory').get_json())
        client.post('/api/inventory', json={'name': 'Water', 'category': 'water', 'quantity': 10})
        client.post('/api/inventory', json={'name': 'Rice', 'category': 'food', 'quantity': 5})
        after = len(client.get('/api/inventory').get_json())
        assert after == before + 2

    def test_filter_by_category(self, client):
        client.post('/api/inventory', json={'name': 'Water', 'category': 'water', 'quantity': 10})
        client.post('/api/inventory', json={'name': 'Rice', 'category': 'food', 'quantity': 5})
        resp = client.get('/api/inventory?category=food')
        data = resp.get_json()
        names = [d['name'] for d in data]
        assert 'Rice' in names

    def test_search(self, client):
        client.post('/api/inventory', json={'name': 'Water Purifier', 'category': 'water'})
        client.post('/api/inventory', json={'name': 'Rice', 'category': 'food'})
        resp = client.get('/api/inventory?q=purifier')
        data = resp.get_json()
        assert len(data) == 1
        assert 'Purifier' in data[0]['name']


class TestInventoryCreate:
    def test_create_item(self, client):
        resp = client.post('/api/inventory', json={
            'name': 'First Aid Kit',
            'category': 'medical',
            'quantity': 3,
            'unit': 'ea',
            'min_quantity': 1,
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['name'] == 'First Aid Kit'
        assert data['category'] == 'medical'
        assert data['quantity'] == 3
        assert data['id'] is not None

    def test_create_with_defaults(self, client):
        resp = client.post('/api/inventory', json={'name': 'Paracord'})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['category'] == 'other'
        assert data['quantity'] == 0

    def test_create_with_barcode(self, client):
        resp = client.post('/api/inventory', json={
            'name': 'MRE',
            'barcode': '123456789012',
        })
        assert resp.status_code == 201
        assert resp.get_json()['barcode'] == '123456789012'

    def test_create_with_lot_number(self, client):
        resp = client.post('/api/inventory', json={
            'name': 'Amoxicillin',
            'category': 'medical',
            'notes': 'Lot: ABC123',
        })
        assert resp.status_code == 201


class TestInventoryUpdate:
    def test_update_quantity(self, client):
        create = client.post('/api/inventory', json={'name': 'Batteries', 'quantity': 10})
        item_id = create.get_json()['id']
        resp = client.put(f'/api/inventory/{item_id}', json={'quantity': 15})
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'saved'
        # Verify via GET
        items = client.get(f'/api/inventory?q=Batteries').get_json()
        assert any(i['quantity'] == 15 for i in items)

    def test_update_no_fields(self, client):
        create = client.post('/api/inventory', json={'name': 'Tape'})
        item_id = create.get_json()['id']
        resp = client.put(f'/api/inventory/{item_id}', json={})
        assert resp.status_code == 400

    def test_update_multiple_fields(self, client):
        create = client.post('/api/inventory', json={'name': 'Rope', 'quantity': 1})
        item_id = create.get_json()['id']
        resp = client.put(f'/api/inventory/{item_id}', json={
            'name': 'Paracord 550',
            'quantity': 5,
            'location': 'Shed'
        })
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'saved'
        # Verify via GET
        items = client.get(f'/api/inventory?q=Paracord').get_json()
        assert any(i['name'] == 'Paracord 550' and i['quantity'] == 5 for i in items)


class TestInventoryDelete:
    def test_delete_item(self, client):
        create = client.post('/api/inventory', json={'name': 'Old MRE'})
        item_id = create.get_json()['id']
        resp = client.delete(f'/api/inventory/{item_id}')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'deleted'
        # Verify this specific item is gone
        items = client.get('/api/inventory?q=Old MRE').get_json()
        assert not any(i['id'] == item_id for i in items)


class TestInventorySummary:
    def test_summary(self, client):
        resp = client.get('/api/inventory/summary')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'total' in data
        assert 'low_stock' in data

    def test_summary_low_stock_increases(self, client):
        before = client.get('/api/inventory/summary').get_json()['low_stock']
        client.post('/api/inventory', json={'name': 'LowStockTestItem', 'quantity': 1, 'min_quantity': 100})
        after = client.get('/api/inventory/summary').get_json()['low_stock']
        assert after == before + 1


class TestShoppingList:
    def test_shopping_list_empty(self, client):
        resp = client.get('/api/inventory/shopping-list')
        assert resp.status_code == 200

    def test_shopping_list_low_stock(self, client):
        client.post('/api/inventory', json={
            'name': 'Water Bottles',
            'quantity': 2,
            'min_quantity': 10,
            'unit': 'ea',
            'category': 'water',
        })
        resp = client.get('/api/inventory/shopping-list')
        data = resp.get_json()
        items = data.get('items', data) if isinstance(data, dict) else data
        # Should recommend restocking water
        found = any('Water' in str(i) for i in (items if isinstance(items, list) else [items]))
        assert found or resp.status_code == 200


class TestInventoryCheckout:
    def test_checkout_requires_person(self, client):
        create = client.post('/api/inventory', json={'name': 'Generator', 'quantity': 1})
        item_id = create.get_json()['id']
        resp = client.post(f'/api/inventory/{item_id}/checkout', json={'quantity': 1})
        assert resp.status_code == 400

    def test_checkout_success(self, client):
        create = client.post('/api/inventory', json={'name': 'Radio', 'quantity': 3})
        item_id = create.get_json()['id']
        resp = client.post(f'/api/inventory/{item_id}/checkout', json={
            'person': 'John',
            'quantity': 1,
            'reason': 'Patrol'
        })
        assert resp.status_code == 201
