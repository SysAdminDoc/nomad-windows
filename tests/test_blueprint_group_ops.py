"""Tests for group_ops blueprint routes (pods, SOPs, duties)."""


class TestGroupPods:
    def test_list_pods(self, client):
        resp = client.get('/api/group/pods')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_pod(self, client):
        resp = client.post('/api/group/pods', json={
            'name': 'Alpha Pod', 'location': 'Sector 1'
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['id'] is not None
        assert data['name'] == 'Alpha Pod'

    def test_create_requires_name(self, client):
        resp = client.post('/api/group/pods', json={'location': 'HQ'})
        assert resp.status_code == 400

    def test_get_pod_detail(self, client):
        create_resp = client.post('/api/group/pods', json={'name': 'Bravo Pod'})
        pid = create_resp.get_json()['id']
        resp = client.get(f'/api/group/pods/{pid}')
        assert resp.status_code == 200
        assert resp.get_json()['name'] == 'Bravo Pod'

    def test_update_pod(self, client):
        create_resp = client.post('/api/group/pods', json={'name': 'Charlie Pod'})
        pid = create_resp.get_json()['id']
        resp = client.put(f'/api/group/pods/{pid}', json={'description': 'Medical team'})
        assert resp.status_code == 200

    def test_delete_pod(self, client):
        create_resp = client.post('/api/group/pods', json={'name': 'Delta Pod'})
        pid = create_resp.get_json()['id']
        resp = client.delete(f'/api/group/pods/{pid}')
        assert resp.status_code == 200


class TestGroupSOPs:
    def test_list_sops(self, client):
        resp = client.get('/api/group/sops')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_sop(self, client):
        pod_resp = client.post('/api/group/pods', json={'name': 'SOP Pod'})
        pod_id = pod_resp.get_json()['id']
        resp = client.post('/api/group/sops', json={
            'title': 'Patrol SOP', 'pod_id': pod_id, 'category': 'security'
        })
        assert resp.status_code == 201

    def test_create_sop_requires_title_and_pod(self, client):
        resp = client.post('/api/group/sops', json={'title': 'No Pod'})
        assert resp.status_code == 400


class TestGroupSummary:
    def test_group_summary(self, client):
        resp = client.get('/api/group/summary')
        assert resp.status_code == 200
