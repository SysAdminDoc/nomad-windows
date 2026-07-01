"""Tests for agriculture blueprint routes."""


def _agriculture_mutation_routes():
    return [
        ('post', '/api/agriculture/food-forest/guilds'),
        ('put', '/api/agriculture/food-forest/guilds/99999'),
        ('post', '/api/agriculture/food-forest/layers'),
        ('put', '/api/agriculture/food-forest/layers/99999'),
        ('post', '/api/agriculture/soil'),
        ('put', '/api/agriculture/soil/99999'),
        ('post', '/api/agriculture/perennials'),
        ('put', '/api/agriculture/perennials/99999'),
        ('post', '/api/agriculture/plans'),
        ('put', '/api/agriculture/plans/99999'),
        ('post', '/api/agriculture/breeding'),
        ('put', '/api/agriculture/breeding/99999'),
        ('post', '/api/agriculture/feed'),
        ('post', '/api/agriculture/homestead'),
        ('put', '/api/agriculture/homestead/99999'),
        ('post', '/api/agriculture/aquaponics'),
        ('put', '/api/agriculture/aquaponics/99999'),
        ('post', '/api/agriculture/recycling'),
        ('put', '/api/agriculture/recycling/99999'),
    ]


class TestAgriculturePayloadValidation:
    def test_mutation_routes_reject_malformed_json(self, client):
        for method, path in _agriculture_mutation_routes():
            resp = getattr(client, method)(
                path,
                data='{bad',
                content_type='application/json',
            )
            assert resp.status_code == 400, path
            assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_mutation_routes_reject_non_object_json(self, client):
        for method, path in _agriculture_mutation_routes():
            resp = getattr(client, method)(
                path,
                data='[]',
                content_type='application/json',
            )
            assert resp.status_code == 400, path
            assert resp.get_json()['error'] == 'Request body must be a JSON object'

    def test_mutation_routes_reject_wrong_shape_fields(self, client):
        cases = [
            ('post', '/api/agriculture/food-forest/guilds', {'support_species': 42}),
            ('put', '/api/agriculture/food-forest/guilds/99999', {'nitrogen_fixers': 42}),
            ('post', '/api/agriculture/food-forest/layers', {'spacing_ft': []}),
            ('put', '/api/agriculture/food-forest/layers/99999', {'years_to_production': []}),
            ('post', '/api/agriculture/soil', {'materials': 42}),
            ('put', '/api/agriculture/soil/99999', {'soil_test_before': 42}),
            ('post', '/api/agriculture/perennials', {'years_to_bearing': []}),
            ('put', '/api/agriculture/perennials/99999', {'years_to_bearing': []}),
            ('post', '/api/agriculture/plans', {'goals': 42}),
            ('put', '/api/agriculture/plans/99999', {'land_acres': []}),
            ('post', '/api/agriculture/breeding', {'offspring_names': 42}),
            ('put', '/api/agriculture/breeding/99999', {'offspring_count': []}),
            ('post', '/api/agriculture/feed', {'quantity_lbs': []}),
            ('post', '/api/agriculture/homestead', {'metrics': 42}),
            ('put', '/api/agriculture/homestead/99999', {'metrics': 42}),
            ('post', '/api/agriculture/aquaponics', {'plant_species': 42}),
            ('put', '/api/agriculture/aquaponics/99999', {'ph_level': []}),
            ('post', '/api/agriculture/recycling', {'input_sources': 42}),
            ('put', '/api/agriculture/recycling/99999', {'metrics': 42}),
        ]
        for method, path, payload in cases:
            resp = getattr(client, method)(path, json=payload)
            assert resp.status_code == 400, path
            assert resp.get_json()['error'] == 'Validation failed'


class TestFoodForestGuilds:
    def test_list_guilds(self, client):
        resp = client.get('/api/agriculture/food-forest/guilds')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_guild(self, client):
        resp = client.post('/api/agriculture/food-forest/guilds', json={
            'name': 'Three Sisters Guild', 'central_species': 'Corn'
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['id'] is not None

    def test_create_requires_name(self, client):
        resp = client.post('/api/agriculture/food-forest/guilds', json={})
        assert resp.status_code == 400

    def test_update_guild(self, client):
        create_resp = client.post('/api/agriculture/food-forest/guilds', json={'name': 'Old Guild'})
        gid = create_resp.get_json()['id']
        resp = client.put(f'/api/agriculture/food-forest/guilds/{gid}', json={'description': 'Updated'})
        assert resp.status_code == 200

    def test_delete_guild(self, client):
        create_resp = client.post('/api/agriculture/food-forest/guilds', json={'name': 'Delete Guild'})
        gid = create_resp.get_json()['id']
        resp = client.delete(f'/api/agriculture/food-forest/guilds/{gid}')
        assert resp.status_code == 200


class TestSoilProjects:
    def test_list_soil(self, client):
        resp = client.get('/api/agriculture/soil')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_soil_project(self, client):
        resp = client.post('/api/agriculture/soil', json={
            'name': 'Raised Bed 1', 'project_type': 'raised_bed'
        })
        assert resp.status_code == 201


class TestAgricultureSummary:
    def test_summary_endpoint(self, client):
        resp = client.get('/api/agriculture/summary')
        assert resp.status_code == 200
