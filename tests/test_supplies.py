"""Tests for fuel, equipment, and ammo API routes."""


class TestFuel:
    def test_list_fuel(self, client):
        resp = client.get('/api/fuel')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_fuel(self, client):
        resp = client.post('/api/fuel', json={
            'fuel_type': 'gasoline',
            'quantity': 20,
            'unit': 'gallons',
            'container': '5gal jerry can x4',
            'location': 'Garage',
            'stabilizer_added': 1,
            'date_stored': '2026-01-15',
            'expires': '2027-01-15',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['fuel_type'] == 'gasoline'
        assert data['id'] is not None

    def test_update_fuel(self, client):
        create = client.post('/api/fuel', json={'fuel_type': 'diesel', 'quantity': 10}).get_json()
        fid = create['id']
        resp = client.put(f'/api/fuel/{fid}', json={'quantity': 15, 'location': 'Shed'})
        assert resp.status_code == 200

    def test_delete_fuel(self, client):
        create = client.post('/api/fuel', json={'fuel_type': 'propane', 'quantity': 5}).get_json()
        fid = create['id']
        resp = client.delete(f'/api/fuel/{fid}')
        assert resp.status_code == 200

    def test_fuel_summary(self, client):
        client.post('/api/fuel', json={'fuel_type': 'gasoline', 'quantity': 20})
        client.post('/api/fuel', json={'fuel_type': 'gasoline', 'quantity': 10})
        client.post('/api/fuel', json={'fuel_type': 'diesel', 'quantity': 5})
        resp = client.get('/api/fuel/summary')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        gas = next((f for f in data if f['fuel_type'] == 'gasoline'), None)
        assert gas is not None
        assert gas['total'] >= 30

    def test_fuel_bulk_delete_rejects_malformed_json(self, client):
        resp = client.post('/api/fuel/bulk-delete', data='{bad', content_type='application/json')
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'


class TestEquipment:
    def test_list_equipment(self, client):
        resp = client.get('/api/equipment')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_equipment(self, client):
        resp = client.post('/api/equipment', json={
            'name': 'Honda EU2200i Generator',
            'category': 'power',
            'status': 'operational',
            'location': 'Garage',
            'last_service': '2026-01-01',
            'next_service': '2026-07-01',
            'service_notes': 'Oil change, spark plug',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['name'] == 'Honda EU2200i Generator'

    def test_update_equipment_mark_serviced(self, client):
        create = client.post('/api/equipment', json={
            'name': 'Water Filter',
            'status': 'needs_service',
        }).get_json()
        eid = create['id']
        resp = client.put(f'/api/equipment/{eid}', json={
            'status': 'operational',
            'last_service': '2026-03-26',
            'next_service': '2026-09-26',
        })
        assert resp.status_code == 200

    def test_delete_equipment(self, client):
        create = client.post('/api/equipment', json={'name': 'Old Pump'}).get_json()
        eid = create['id']
        resp = client.delete(f'/api/equipment/{eid}')
        assert resp.status_code == 200

    def test_equipment_bulk_delete_rejects_malformed_json(self, client):
        resp = client.post('/api/equipment/bulk-delete', data='{bad', content_type='application/json')
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'


class TestAmmo:
    def test_list_ammo(self, client):
        resp = client.get('/api/ammo')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_ammo(self, client):
        resp = client.post('/api/ammo', json={
            'caliber': '9mm',
            'brand': 'Federal',
            'bullet_weight': '124gr',
            'bullet_type': 'FMJ',
            'quantity': 500,
            'location': 'Safe',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['caliber'] == '9mm'
        assert data['quantity'] == 500

    def test_update_ammo(self, client):
        create = client.post('/api/ammo', json={'caliber': '.22 LR', 'quantity': 1000}).get_json()
        aid = create['id']
        resp = client.put(f'/api/ammo/{aid}', json={'quantity': 800, 'notes': 'Used 200 at range'})
        assert resp.status_code == 200

    def test_delete_ammo(self, client):
        create = client.post('/api/ammo', json={'caliber': '.45 ACP', 'quantity': 100}).get_json()
        aid = create['id']
        resp = client.delete(f'/api/ammo/{aid}')
        assert resp.status_code == 200

    def test_ammo_summary(self, client):
        client.post('/api/ammo', json={'caliber': '5.56', 'quantity': 500})
        client.post('/api/ammo', json={'caliber': '5.56', 'quantity': 300})
        resp = client.get('/api/ammo/summary')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'by_caliber' in data
        assert 'total' in data
        assert data['total'] >= 800

    def test_ammo_import_rejects_malformed_json(self, client):
        resp = client.post('/api/ammo/import', data='{bad', content_type='application/json')
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'
