"""Tests for medical/patients blueprint routes."""


class TestPatientsCRUD:
    def test_list_empty(self, client):
        resp = client.get('/api/patients')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_returns_id(self, client):
        resp = client.post('/api/patients', json={'name': 'John Doe', 'age': 35})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['id'] is not None

    def test_create_and_list(self, client):
        client.post('/api/patients', json={'name': 'Jane Doe', 'blood_type': 'O+'})
        resp = client.get('/api/patients')
        assert resp.status_code == 200
        names = [p['name'] for p in resp.get_json()]
        assert 'Jane Doe' in names

    def test_create_requires_name(self, client):
        resp = client.post('/api/patients', json={'age': 40})
        assert resp.status_code == 400

    def test_update_patient(self, client):
        create_resp = client.post('/api/patients', json={'name': 'Bob Smith'})
        pid = create_resp.get_json()['id']
        resp = client.put(f'/api/patients/{pid}', json={'blood_type': 'A-'})
        assert resp.status_code == 200

    def test_delete_patient(self, client):
        create_resp = client.post('/api/patients', json={'name': 'Delete Me'})
        pid = create_resp.get_json()['id']
        resp = client.delete(f'/api/patients/{pid}')
        assert resp.status_code == 200


class TestPatientVitals:
    def test_vitals_list(self, client):
        create_resp = client.post('/api/patients', json={'name': 'Vitals Patient'})
        pid = create_resp.get_json()['id']
        resp = client.get(f'/api/patients/{pid}/vitals')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_vitals_create(self, client):
        create_resp = client.post('/api/patients', json={'name': 'Vitals Patient 2'})
        pid = create_resp.get_json()['id']
        resp = client.post(f'/api/patients/{pid}/vitals', json={
            'pulse': 72, 'bp_sys': 120, 'bp_dia': 80, 'temp_f': 98.6
        })
        assert resp.status_code in (200, 201)


class TestTriageBoard:
    def test_triage_board(self, client):
        resp = client.get('/api/medical/triage-board')
        assert resp.status_code == 200
