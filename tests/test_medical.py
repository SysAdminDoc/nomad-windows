"""Tests for medical module API routes."""


class TestPatientsList:
    def test_empty_list(self, client):
        resp = client.get('/api/patients')
        assert resp.status_code == 200
        assert resp.get_json() == []


class TestPatientsCreate:
    def test_create_patient(self, client):
        resp = client.post('/api/patients', json={
            'name': 'John Doe',
            'age': 35,
            'blood_type': 'A+',
            'allergies': ['Penicillin'],
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['id'] is not None
        assert data['status'] == 'created'

    def test_create_minimal(self, client):
        resp = client.post('/api/patients', json={'name': 'Jane'})
        assert resp.status_code == 201


class TestPatientsUpdate:
    def test_update_patient(self, client):
        create = client.post('/api/patients', json={'name': 'Bob', 'age': 40})
        pid = create.get_json()['id']
        resp = client.put(f'/api/patients/{pid}', json={'age': 41, 'blood_type': 'O-'})
        assert resp.status_code == 200

    def test_update_patient_recovers_from_corrupted_list_fields(self, client, db):
        create = client.post('/api/patients', json={'name': 'Corrupted Lists'}).get_json()
        pid = create['id']
        db.execute(
            'UPDATE patients SET allergies = ?, medications = ?, conditions = ? WHERE id = ?',
            ('{broken', '{broken', '{broken', pid),
        )
        db.commit()

        resp = client.put(f'/api/patients/{pid}', json={'age': 41})

        assert resp.status_code == 200


class TestPatientsDelete:
    def test_delete_patient(self, client):
        create = client.post('/api/patients', json={'name': 'Temp Patient Delete'})
        pid = create.get_json()['id']
        resp = client.delete(f'/api/patients/{pid}')
        assert resp.status_code == 200
        patients = client.get('/api/patients').get_json()
        assert not any(p['id'] == pid for p in patients)


class TestVitals:
    def test_add_vitals(self, client):
        patient = client.post('/api/patients', json={'name': 'Vitals Test'}).get_json()
        pid = patient['id']
        resp = client.post(f'/api/patients/{pid}/vitals', json={
            'bp_systolic': 120,
            'bp_diastolic': 80,
            'heart_rate': 72,
            'temp_f': 98.6,
            'spo2': 98,
            'resp_rate': 16,
        })
        assert resp.status_code == 201

    def test_list_vitals(self, client):
        patient = client.post('/api/patients', json={'name': 'V Test'}).get_json()
        pid = patient['id']
        client.post(f'/api/patients/{pid}/vitals', json={'heart_rate': 72})
        resp = client.get(f'/api/patients/{pid}/vitals')
        assert resp.status_code == 200
        assert len(resp.get_json()) >= 1


class TestWounds:
    def test_add_wound(self, client):
        patient = client.post('/api/patients', json={'name': 'Wound Test'}).get_json()
        pid = patient['id']
        resp = client.post(f'/api/patients/{pid}/wounds', json={
            'location': 'Left arm',
            'type': 'Laceration',
            'severity': 'moderate',
            'notes': 'Cleaned and dressed',
        })
        assert resp.status_code == 201

    def test_list_wounds(self, client):
        patient = client.post('/api/patients', json={'name': 'W Test'}).get_json()
        pid = patient['id']
        client.post(f'/api/patients/{pid}/wounds', json={'location': 'Head', 'type': 'Bruise'})
        resp = client.get(f'/api/patients/{pid}/wounds')
        assert resp.status_code == 200
        assert len(resp.get_json()) >= 1

    def test_wound_photos_list_recovers_from_corrupted_photo_path(self, client, db):
        patient = client.post('/api/patients', json={'name': 'Broken Photos'}).get_json()
        pid = patient['id']
        wound = client.post(f'/api/patients/{pid}/wounds', json={'location': 'Arm', 'type': 'Cut'}).get_json()
        db.execute('UPDATE wound_log SET photo_path = ? WHERE id = ?', ('{broken', wound['id']))
        db.commit()

        resp = client.get(f'/api/patients/{pid}/wounds/{wound["id"]}/photos')

        assert resp.status_code == 200
        assert resp.get_json()['photos'] == []


class TestDrugInteractions:
    def test_check_interactions(self, client):
        resp = client.post('/api/medical/interactions', json={
            'medications': ['aspirin', 'warfarin']
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'interactions' in data or isinstance(data, list)

    def test_no_interactions(self, client):
        resp = client.post('/api/medical/interactions', json={
            'medications': ['acetaminophen']
        })
        assert resp.status_code == 200


class TestTriageBoard:
    def test_triage_board(self, client):
        resp = client.get('/api/medical/triage-board')
        assert resp.status_code == 200

    def test_update_triage(self, client):
        patient = client.post('/api/patients', json={'name': 'Triage Test'}).get_json()
        pid = patient['id']
        resp = client.put(f'/api/medical/triage/{pid}', json={
            'triage_category': 'immediate',
            'care_phase': 'treatment',
        })
        assert resp.status_code == 200


class TestTCCCProtocol:
    def test_get_protocol(self, client):
        resp = client.get('/api/medical/tccc-protocol')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, (list, dict))


class TestExpiringMeds:
    def test_expiring_meds_empty(self, client):
        resp = client.get('/api/medical/expiring-meds')
        assert resp.status_code == 200


class TestTriageUpdate404:
    def test_triage_update_nonexistent_returns_404(self, client):
        resp = client.put('/api/medical/triage/99999', json={
            'triage_category': 'immediate',
        })
        assert resp.status_code == 404
