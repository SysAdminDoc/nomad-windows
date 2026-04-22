"""Tests for evac_drills blueprint routes."""


class TestEvacDrillsCRUD:
    def test_list_drills(self, client):
        resp = client.get('/api/evac-drills')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_drill(self, client):
        resp = client.post('/api/evac-drills', json={
            'name': 'Full Evac Drill #1', 'drill_type': 'full_evacuation'
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['id'] is not None
        assert data['name'] == 'Full Evac Drill #1'

    def test_create_requires_name(self, client):
        resp = client.post('/api/evac-drills', json={'drill_type': 'shelter_in_place'})
        assert resp.status_code == 400

    def test_update_drill(self, client):
        create_resp = client.post('/api/evac-drills', json={'name': 'Draft Drill'})
        did = create_resp.get_json()['id']
        resp = client.put(f'/api/evac-drills/{did}', json={'notes': 'Updated notes', 'status': 'completed'})
        assert resp.status_code == 200

    def test_delete_drill(self, client):
        create_resp = client.post('/api/evac-drills', json={'name': 'Temp Drill'})
        did = create_resp.get_json()['id']
        resp = client.delete(f'/api/evac-drills/{did}')
        assert resp.status_code == 200


class TestEvacDrillsStatus:
    def test_drill_status(self, client):
        create_resp = client.post('/api/evac-drills', json={
            'name': 'Status Drill', 'participants': 5
        })
        did = create_resp.get_json()['id']
        resp = client.get(f'/api/evac-drills/{did}/status')
        assert resp.status_code == 200

    def test_performance_endpoint(self, client):
        resp = client.get('/api/evac-drills/performance')
        assert resp.status_code == 200

    def test_summary_endpoint(self, client):
        resp = client.get('/api/evac-drills/summary')
        assert resp.status_code == 200
