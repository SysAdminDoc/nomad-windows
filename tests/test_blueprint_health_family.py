"""Tests for health_family blueprint routes (child-id, reunification, community)."""


class TestChildIdPackets:
    def test_list_child_id(self, client):
        resp = client.get('/api/family/child-id')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_child_id(self, client):
        resp = client.post('/api/family/child-id', json={
            'name': 'Child One', 'dob': '2018-03-15', 'blood_type': 'A+'
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['id'] is not None
        assert data['name'] == 'Child One'

    def test_create_requires_name(self, client):
        resp = client.post('/api/family/child-id', json={'dob': '2020-01-01'})
        assert resp.status_code == 400

    def test_update_child_id(self, client):
        create_resp = client.post('/api/family/child-id', json={'name': 'Update Child'})
        cid = create_resp.get_json()['id']
        resp = client.put(f'/api/family/child-id/{cid}', json={'hair_color': 'brown'})
        assert resp.status_code == 200

    def test_delete_child_id(self, client):
        create_resp = client.post('/api/family/child-id', json={'name': 'Delete Child'})
        cid = create_resp.get_json()['id']
        resp = client.delete(f'/api/family/child-id/{cid}')
        assert resp.status_code == 200


class TestReunificationPlan:
    def test_get_reunification(self, client):
        resp = client.get('/api/family/reunification')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'plan' in data

    def test_save_reunification(self, client):
        resp = client.post('/api/family/reunification', json={
            'primary_rally': 'Community Center',
            'secondary_rally': 'High School',
            'out_of_area_contact': '555-0100',
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'saved'


class TestPediatricDose:
    def test_pediatric_dose_by_weight(self, client):
        resp = client.post('/api/medical/pediatric-dose', json={'weight_kg': 20})
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'doses' in data or isinstance(data, list) or len(data) > 0
