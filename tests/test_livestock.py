"""Tests for livestock API routes."""


class TestLivestockList:
    def test_list_livestock(self, client):
        resp = client.get('/api/livestock')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)


class TestLivestockCreate:
    def test_create_animal(self, client):
        resp = client.post('/api/livestock', json={
            'species': 'Chicken',
            'name': 'Henrietta',
            'tag': 'CH-001',
            'sex': 'female',
        })
        assert resp.status_code == 201
        assert resp.get_json()['status'] == 'created'

    def test_create_requires_species(self, client):
        resp = client.post('/api/livestock', json={'name': 'No Species'})
        assert resp.status_code == 400

    def test_create_defaults(self, client):
        resp = client.post('/api/livestock', json={'species': 'Goat'})
        assert resp.status_code == 201


class TestLivestockUpdate:
    def test_update_animal(self, client):
        client.post('/api/livestock', json={'species': 'Cow', 'name': 'Bessie'})
        animals = client.get('/api/livestock').get_json()
        cow = next((a for a in animals if a['name'] == 'Bessie'), None)
        assert cow is not None
        resp = client.put(f'/api/livestock/{cow["id"]}', json={
            'species': 'Cow',
            'name': 'Bessie',
            'weight_lbs': 1200,
            'status': 'active',
        })
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'updated'


class TestLivestockDelete:
    def test_delete_animal(self, client):
        client.post('/api/livestock', json={'species': 'Duck', 'name': 'Quackers'})
        animals = client.get('/api/livestock').get_json()
        duck = next((a for a in animals if a['name'] == 'Quackers'), None)
        assert duck is not None
        resp = client.delete(f'/api/livestock/{duck["id"]}')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'deleted'

    def test_bulk_delete_rejects_malformed_json(self, client):
        resp = client.post('/api/livestock/bulk-delete', data='{bad', content_type='application/json')
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'


class TestLivestockHealth:
    def test_log_health_event(self, client):
        client.post('/api/livestock', json={'species': 'Horse', 'name': 'Spirit'})
        animals = client.get('/api/livestock').get_json()
        horse = next((a for a in animals if a['name'] == 'Spirit'), None)
        assert horse is not None
        resp = client.post(f'/api/livestock/{horse["id"]}/health', json={
            'event': 'Vaccination',
            'notes': 'Annual rabies shot',
        })
        assert resp.status_code == 201
        assert resp.get_json()['status'] == 'logged'

    def test_health_log_nonexistent_returns_404(self, client):
        resp = client.post('/api/livestock/99999/health', json={
            'event': 'Checkup',
        })
        assert resp.status_code == 404
