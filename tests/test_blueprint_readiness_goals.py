"""Tests for readiness_goals blueprint routes."""


class TestReadinessGoalsCRUD:
    def test_list_goals(self, client):
        resp = client.get('/api/readiness-goals')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_goal(self, client):
        resp = client.post('/api/readiness-goals', json={
            'name': '30-Day Food Supply', 'category': 'food'
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['id'] is not None

    def test_create_requires_name_and_category(self, client):
        resp = client.post('/api/readiness-goals', json={'name': 'Water'})
        assert resp.status_code == 400

    def test_update_goal(self, client):
        create_resp = client.post('/api/readiness-goals', json={
            'name': 'Medical Supplies', 'category': 'medical'
        })
        gid = create_resp.get_json()['id']
        resp = client.put(f'/api/readiness-goals/{gid}', json={'priority': 'high'})
        assert resp.status_code == 200

    def test_delete_goal(self, client):
        create_resp = client.post('/api/readiness-goals', json={
            'name': 'Temp Goal', 'category': 'security'
        })
        gid = create_resp.get_json()['id']
        resp = client.delete(f'/api/readiness-goals/{gid}')
        assert resp.status_code == 200


class TestReadinessGoalsDashboard:
    def test_dashboard_endpoint(self, client):
        resp = client.get('/api/readiness-goals/dashboard')
        assert resp.status_code == 200

    def test_presets_endpoint(self, client):
        resp = client.get('/api/readiness-goals/presets')
        assert resp.status_code == 200

    def test_summary_endpoint(self, client):
        resp = client.get('/api/readiness-goals/summary')
        assert resp.status_code == 200
