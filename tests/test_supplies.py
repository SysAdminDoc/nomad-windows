"""Tests for supplies API routes."""

import json


def _export_json(resp):
    return json.loads(resp.get_data(as_text=True))


class TestVault:
    def test_vault_lifecycle_keeps_secret_material_out_of_list(self, client):
        resp = client.post('/api/vault', json={
            'title': 'Radio codes',
            'encrypted_data': 'ciphertext-v1',
            'iv': 'iv-v1',
            'salt': 'salt-v1',
        })
        assert resp.status_code == 201
        eid = resp.get_json()['id']

        list_resp = client.get('/api/vault')
        assert list_resp.status_code == 200
        listed = next(row for row in list_resp.get_json() if row['id'] == eid)
        assert listed['title'] == 'Radio codes'
        assert 'encrypted_data' not in listed
        assert 'iv' not in listed
        assert 'salt' not in listed

        get_resp = client.get(f'/api/vault/{eid}')
        assert get_resp.status_code == 200
        assert get_resp.get_json()['encrypted_data'] == 'ciphertext-v1'

        update_resp = client.put(f'/api/vault/{eid}', json={
            'title': 'Updated codes',
            'encrypted_data': 'ciphertext-v2',
            'iv': 'iv-v2',
            'salt': 'salt-v2',
        })
        assert update_resp.status_code == 200
        assert client.get(f'/api/vault/{eid}').get_json()['title'] == 'Updated codes'

        delete_resp = client.delete(f'/api/vault/{eid}')
        assert delete_resp.status_code == 200
        assert client.get(f'/api/vault/{eid}').status_code == 404

    def test_vault_rejects_missing_required_crypto_fields(self, client):
        resp = client.post('/api/vault', json={
            'title': 'Incomplete',
            'encrypted_data': 'ciphertext',
            'iv': 'iv',
        })
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Missing required field: salt'


class TestSkills:
    def test_seed_default_skills_is_idempotent(self, client):
        first = client.post('/api/skills/seed-defaults')
        assert first.status_code == 200
        assert first.get_json()['seeded'] >= 60

        second = client.post('/api/skills/seed-defaults')
        assert second.status_code == 200
        assert second.get_json() == {'seeded': 0}

    def test_skills_create_update_export_and_bulk_delete(self, client):
        created = [
            client.post('/api/skills', json={
                'name': 'Water filter repair',
                'category': 'Water',
                'proficiency': 'basic',
            }).get_json(),
            client.post('/api/skills', json={
                'name': 'Battery rotation',
                'category': 'Power',
                'proficiency': 'none',
            }).get_json(),
        ]
        assert {row['name'] for row in created} == {'Water filter repair', 'Battery rotation'}

        update = client.put(f"/api/skills/{created[0]['id']}", json={
            'name': 'Water filter repair',
            'category': 'Water',
            'proficiency': 'advanced',
            'notes': 'Can rebuild field filters',
            'last_practiced': '2026-04-01',
        })
        assert update.status_code == 200
        assert update.get_json()['proficiency'] == 'advanced'

        export = client.get('/api/skills/export')
        assert export.status_code == 200
        assert 'skills_export.json' in export.headers['Content-Disposition']
        exported_names = {row['name'] for row in _export_json(export)}
        assert {'Water filter repair', 'Battery rotation'} <= exported_names

        bulk = client.post('/api/skills/bulk-delete', json={'ids': [row['id'] for row in created]})
        assert bulk.status_code == 200
        assert bulk.get_json()['count'] == 2

    def test_skills_import_and_validation(self, client):
        import_resp = client.post('/api/skills/import', json=[
            {'name': 'Generator maintenance', 'category': 'Power', 'proficiency': 'basic'},
            {'name': 'Map reading', 'category': 'Navigation', 'last_practiced': '2026-03-20'},
        ])
        assert import_resp.status_code == 200
        assert import_resp.get_json() == {'status': 'imported', 'count': 2}

        listed = client.get('/api/skills?sort_by=name&sort_dir=asc').get_json()
        assert 'Generator maintenance' in {row['name'] for row in listed}

        missing = client.post('/api/skills', json={'name': '   '})
        assert missing.status_code == 400
        assert missing.get_json()['error'] == 'name is required'

        malformed = client.post('/api/skills/import', data='{bad', content_type='application/json')
        assert malformed.status_code == 400
        assert malformed.get_json()['error'] == 'Request body must be valid JSON'


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

    def test_fuel_bulk_delete_success_and_quantity_fallback(self, client):
        first = client.post('/api/fuel', json={'fuel_type': 'kerosene', 'quantity': 'bad'}).get_json()
        second = client.post('/api/fuel', json={'fuel_type': 'kerosene', 'quantity': 2}).get_json()
        assert first['quantity'] == 0.0

        resp = client.post('/api/fuel/bulk-delete', json={'ids': [first['id'], second['id']]})
        assert resp.status_code == 200
        assert resp.get_json() == {'status': 'deleted', 'count': 2}

    def test_create_fuel_rejects_missing_type(self, client):
        resp = client.post('/api/fuel', json={'quantity': 5})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'fuel_type is required'


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

    def test_equipment_import_export_and_bulk_delete(self, client):
        import_resp = client.post('/api/equipment/import', json=[
            {
                'name': 'Generator',
                'category': 'power',
                'status': 'operational',
                'next_service': '2026-08-01',
            },
            {
                'name': 'Berkey filter',
                'category': 'water',
                'status': 'needs_service',
            },
        ])
        assert import_resp.status_code == 200
        assert import_resp.get_json() == {'status': 'imported', 'count': 2}

        export = client.get('/api/equipment/export')
        assert export.status_code == 200
        exported = _export_json(export)
        exported_rows = [row for row in exported if row['name'] in {'Generator', 'Berkey filter'}]
        assert len(exported_rows) == 2

        resp = client.post('/api/equipment/bulk-delete', json={'ids': [row['id'] for row in exported_rows]})
        assert resp.status_code == 200
        assert resp.get_json()['count'] == 2

    def test_create_equipment_rejects_missing_name(self, client):
        resp = client.post('/api/equipment', json={'category': 'power'})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'name is required'


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

    def test_ammo_import_export_and_bulk_delete(self, client):
        import_resp = client.post('/api/ammo/import', json=[
            {'caliber': '12ga', 'brand': 'Federal', 'quantity': '25', 'location': 'Safe'},
            {'caliber': '12ga', 'brand': 'Training', 'quantity': 'bad'},
        ])
        assert import_resp.status_code == 200
        assert import_resp.get_json() == {'status': 'imported', 'count': 2}

        summary = client.get('/api/ammo/summary').get_json()
        assert any(row['caliber'] == '12ga' and row['total'] >= 25 for row in summary['by_caliber'])

        export = client.get('/api/ammo/export')
        assert export.status_code == 200
        exported = [row for row in _export_json(export) if row['caliber'] == '12ga']
        assert {row['quantity'] for row in exported} >= {0, 25}

        resp = client.post('/api/ammo/bulk-delete', json={'ids': [row['id'] for row in exported]})
        assert resp.status_code == 200
        assert resp.get_json()['count'] == len(exported)

    def test_create_ammo_rejects_overlong_caliber(self, client):
        resp = client.post('/api/ammo', json={'caliber': 'x' * 201})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'caliber too long (max 200)'


class TestCommunity:
    def test_community_create_update_delete_and_json_fields(self, client):
        create = client.post('/api/community', json={
            'name': 'North well team',
            'distance_mi': '3.5',
            'skills': ['water', 'radio'],
            'equipment': ['pump'],
            'trust_level': 'trusted',
        })
        assert create.status_code == 201
        row = create.get_json()
        assert row['distance_mi'] == 3.5
        assert json.loads(row['skills']) == ['water', 'radio']

        update = client.put(f"/api/community/{row['id']}", json={
            'name': 'North well team',
            'distance_mi': 'bad',
            'skills': ['water'],
            'equipment': ['pump', 'hose'],
            'trust_level': 'vetted',
        })
        assert update.status_code == 200
        updated = update.get_json()
        assert updated['distance_mi'] == 0.0
        assert json.loads(updated['equipment']) == ['pump', 'hose']

        delete = client.delete(f"/api/community/{row['id']}")
        assert delete.status_code == 200
        assert client.delete(f"/api/community/{row['id']}").status_code == 404

    def test_community_bulk_delete_and_validation(self, client):
        first = client.post('/api/community', json={'name': 'Medical neighbor'}).get_json()
        second = client.post('/api/community', json={'name': 'Tool library'}).get_json()

        bulk = client.post('/api/community/bulk-delete', json={'ids': [first['id'], second['id']]})
        assert bulk.status_code == 200
        assert bulk.get_json() == {'status': 'deleted', 'count': 2}

        missing = client.post('/api/community', json={'name': ''})
        assert missing.status_code == 400
        assert missing.get_json()['error'] == 'name is required'


class TestRadiation:
    def test_radiation_cumulative_total_and_clear(self, client):
        first = client.post('/api/radiation', json={
            'dose_rate_rem': 0.5,
            'duration_hours': 2,
            'location': 'Basement',
        })
        assert first.status_code == 201
        assert first.get_json()['cumulative_rem'] == 1.0

        second = client.post('/api/radiation', json={
            'dose_rate_rem': '2',
            'duration_hours': '1.5',
        })
        assert second.status_code == 201
        assert second.get_json()['cumulative_rem'] == 4.0

        listed = client.get('/api/radiation')
        assert listed.status_code == 200
        assert listed.get_json()['total_rem'] == 4.0

        clear = client.post('/api/radiation/clear')
        assert clear.status_code == 200
        assert client.get('/api/radiation').get_json() == {'readings': [], 'total_rem': 0}

    def test_radiation_bad_numeric_input_falls_back_to_zero(self, client):
        resp = client.post('/api/radiation', json={
            'dose_rate_rem': 'bad',
            'duration_hours': 'bad',
        })
        assert resp.status_code == 201
        assert resp.get_json()['cumulative_rem'] == 0.0
