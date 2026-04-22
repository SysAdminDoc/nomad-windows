"""Tests for checklists blueprint routes."""


class TestChecklistsCRUD:
    def test_list_empty(self, client):
        resp = client.get('/api/checklists')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_returns_id(self, client):
        resp = client.post('/api/checklists', json={'name': 'Go-Bag'})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['id'] is not None

    def test_create_and_list(self, client):
        client.post('/api/checklists', json={'name': 'Evacuation'})
        resp = client.get('/api/checklists')
        assert resp.status_code == 200
        names = [c['name'] for c in resp.get_json()]
        assert 'Evacuation' in names

    def test_get_by_id(self, client):
        create_resp = client.post('/api/checklists', json={'name': 'Medical'})
        cid = create_resp.get_json()['id']
        resp = client.get(f'/api/checklists/{cid}')
        assert resp.status_code == 200
        assert resp.get_json()['id'] == cid

    def test_update_checklist(self, client):
        create_resp = client.post('/api/checklists', json={'name': 'Old Name'})
        cid = create_resp.get_json()['id']
        resp = client.put(f'/api/checklists/{cid}', json={'name': 'New Name'})
        assert resp.status_code == 200

    def test_delete_checklist(self, client):
        create_resp = client.post('/api/checklists', json={'name': 'Disposable'})
        cid = create_resp.get_json()['id']
        resp = client.delete(f'/api/checklists/{cid}')
        assert resp.status_code == 200

    def test_clone_checklist(self, client):
        create_resp = client.post('/api/checklists', json={'name': 'Original'})
        cid = create_resp.get_json()['id']
        resp = client.post(f'/api/checklists/{cid}/clone')
        assert resp.status_code == 200
        assert resp.get_json()['id'] is not None


class TestChecklistsTemplates:
    def test_templates_endpoint(self, client):
        resp = client.get('/api/checklists/templates')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), dict)

    def test_dashboard_endpoint(self, client):
        resp = client.get('/api/dashboard/checklists')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)
