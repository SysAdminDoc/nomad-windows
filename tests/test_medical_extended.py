"""Tests for medical blueprint routes (extended coverage beyond test_medical.py)."""


class TestVitalsTrend:
    def test_vitals_trend(self, client):
        patient = client.post('/api/patients', json={'name': 'Trend Test'}).get_json()
        pid = patient['id']
        client.post(f'/api/patients/{pid}/vitals', json={'heart_rate': 70})
        client.post(f'/api/patients/{pid}/vitals', json={'heart_rate': 75})
        resp = client.get(f'/api/medical/vitals-trend/{pid}')
        assert resp.status_code == 200


class TestDosageCalculator:
    def test_dosage_calculator_known_drug(self, client):
        resp = client.post('/api/medical/dosage-calculator', json={
            'drug': 'Ibuprofen',
            'weight_kg': 70,
            'age': 35,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'drug' in data

    def test_dosage_calculator_unknown_drug(self, client):
        resp = client.post('/api/medical/dosage-calculator', json={
            'drug': 'NonExistentDrug',
        })
        assert resp.status_code == 400

    def test_dosage_drugs_list(self, client):
        resp = client.get('/api/medical/dosage-drugs')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert 'drug' in data[0]

    def test_dosage_calculator_with_patient_allergies(self, client):
        patient = client.post('/api/patients', json={
            'name': 'Allergy Test',
            'allergies': ['aspirin'],
        }).get_json()
        resp = client.post('/api/medical/dosage-calculator', json={
            'drug': 'Ibuprofen',
            'patient_id': patient['id'],
            'weight_kg': 70,
            'age': 35,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        # Should include allergy warnings
        assert 'warnings' in data or 'drug' in data

    def test_dosage_calculator_recovers_from_corrupted_patient_lists(self, client, db):
        patient = client.post('/api/patients', json={
            'name': 'Broken Dosage Lists',
        }).get_json()
        db.execute(
            'UPDATE patients SET allergies = ?, medications = ? WHERE id = ?',
            ('{broken', '{broken', patient['id']),
        )
        db.commit()

        resp = client.post('/api/medical/dosage-calculator', json={
            'drug': 'Ibuprofen',
            'patient_id': patient['id'],
            'weight_kg': 70,
            'age': 35,
        })

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['drug'] == 'Ibuprofen'
        assert isinstance(data['warnings'], list)


class TestMedicalReference:
    def test_medical_reference(self, client):
        resp = client.get('/api/medical/reference')
        assert resp.status_code == 200

    def test_medical_reference_search(self, client):
        resp = client.get('/api/medical/reference/search?q=bleeding')
        assert resp.status_code == 200

    def test_medical_reference_search_survives_non_json_reference_response(self, client, monkeypatch):
        from flask import Response
        from web.blueprints import medical as medical_module

        monkeypatch.setattr(
            medical_module,
            'api_medical_reference',
            lambda: Response('{broken', mimetype='application/json'),
        )

        resp = client.get('/api/medical/reference/search?q=bleeding')

        assert resp.status_code == 200
        assert resp.get_json() == []


class TestPatientCard:
    def test_patient_card(self, client):
        patient = client.post('/api/patients', json={
            'name': 'Card Test',
            'age': 40,
            'blood_type': 'B+',
        }).get_json()
        resp = client.get(f'/api/patients/{patient["id"]}/card')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Patient Care Card' in html
        assert 'Immediate Alerts' in html
        assert 'Card Test' in html

    def test_patient_card_recovers_from_corrupted_list_fields(self, client, db):
        patient = client.post('/api/patients', json={
            'name': 'Broken Card Test',
            'age': 40,
            'blood_type': 'B+',
        }).get_json()
        db.execute(
            'UPDATE patients SET allergies = ?, medications = ?, conditions = ? WHERE id = ?',
            ('{broken', '{broken', '{broken', patient['id']),
        )
        db.commit()

        resp = client.get(f'/api/patients/{patient["id"]}/card')

        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Patient Care Card' in html
        assert 'Broken Card Test' in html
        assert '{broken' not in html


class TestExpiringMeds:
    def test_expiring_meds_endpoint(self, client):
        resp = client.get('/api/medical/expiring-meds')
        assert resp.status_code == 200


class TestHandoff:
    def test_handoff_create(self, client):
        patient = client.post('/api/patients', json={'name': 'Handoff Test'}).get_json()
        pid = patient['id']
        resp = client.post(f'/api/medical/handoff/{pid}', json={
            'receiving_provider': 'Dr. Smith',
            'condition_summary': 'Stable',
        })
        assert resp.status_code in (200, 201)
        data = resp.get_json()
        assert 'SBAR Handoff - Handoff Test' in data['html']
        assert 'From ___ to Dr. Smith' in data['html']
        assert 'Stable' in data['html']

    def test_handoff_print(self, client):
        patient = client.post('/api/patients', json={'name': 'Print Handoff'}).get_json()
        create_resp = client.post(f'/api/medical/handoff/{patient["id"]}', json={
            'from_provider': 'Medic A',
            'to_provider': 'ER Team',
            'situation': 'Needs transfer',
        })
        assert create_resp.status_code in (200, 201)
        rid = create_resp.get_json()['id']

        print_resp = client.get(f'/api/medical/handoff/{rid}/print')
        assert print_resp.status_code == 200
        html = print_resp.get_data(as_text=True)
        assert 'NOMAD Field Desk Transfer Brief' in html
        assert 'From Medic A to ER Team' in html
        assert 'Needs transfer' in html


class TestTriageBoardExtended:
    def test_triage_board_with_patient(self, client):
        patient = client.post('/api/patients', json={'name': 'Triage Test'}).get_json()
        pid = patient['id']
        client.put(f'/api/medical/triage/{pid}', json={
            'triage_category': 'immediate',
            'care_phase': 'treatment',
        })
        resp = client.get('/api/medical/triage-board')
        assert resp.status_code == 200
