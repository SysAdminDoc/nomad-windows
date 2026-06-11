"""Tests for Security/OPSEC mutation route validation."""


BASE = '/api/security-ops'


class TestOpsecCompartments:
    def test_compartment_create_round_trips_authorized_persons(self, client):
        resp = client.post(f'{BASE}/opsec/compartments', json={
            'name': 'Radio Room',
            'authorized_persons': ['Taylor', 'Morgan'],
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['name'] == 'Radio Room'
        assert data['authorized_persons'] == ['Taylor', 'Morgan']

    def test_compartment_create_rejects_malformed_json(self, client):
        resp = client.post(
            f'{BASE}/opsec/compartments',
            data='not-json',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_compartment_create_rejects_container_name(self, client):
        resp = client.post(f'{BASE}/opsec/compartments', json={'name': ['Radio Room']})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'


class TestOpsecChecklists:
    def test_checklist_update_scores_only_object_items(self, client):
        created = client.post(f'{BASE}/opsec/checklists', json={'title': 'Audit'}).get_json()

        resp = client.put(f'{BASE}/opsec/checklists/{created["id"]}', json={
            'items': [{'item': 'Passwords rotated', 'checked': True}, 'bad item'],
        })
        assert resp.status_code == 200
        assert resp.get_json()['score'] == 50


class TestThreatMatrix:
    def test_threat_create_coerces_numeric_strings_for_risk_score(self, client):
        resp = client.post(f'{BASE}/threat-matrix', json={
            'threat_name': 'Gate breach',
            'likelihood': '2',
            'impact': '3',
        })
        assert resp.status_code == 201
        assert resp.get_json()['risk_score'] == 6

    def test_threat_update_rejects_container_likelihood(self, client):
        created = client.post(f'{BASE}/threat-matrix', json={'threat_name': 'Flood'}).get_json()

        resp = client.put(f'{BASE}/threat-matrix/{created["id"]}', json={'likelihood': ['high']})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'


class TestObservationAndLogs:
    def test_observation_post_rejects_container_sectors(self, client):
        resp = client.post(f'{BASE}/observation-posts', json={
            'name': 'North Ridge',
            'sectors': {'north': True},
        })
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_op_log_rejects_non_object_body(self, client):
        resp = client.post(f'{BASE}/op-log', json=['sighting'])
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be a JSON object'


class TestSignaturesAndNightOps:
    def test_signature_create_coerces_string_intensity(self, client):
        resp = client.post(f'{BASE}/signatures', json={
            'location': 'Generator shed',
            'visual_signatures': [{'intensity_1_5': '4'}],
        })
        assert resp.status_code == 201
        assert resp.get_json()['overall_score'] == 80

    def test_night_ops_rejects_container_signals(self, client):
        resp = client.post(f'{BASE}/night-ops', json={
            'name': 'Quiet movement',
            'signals': ['bad'],
        })
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'


class TestCbrnAndEmp:
    def test_cbrn_equipment_rejects_container_quantity(self, client):
        resp = client.post(f'{BASE}/cbrn/equipment', json={
            'equipment_name': 'Survey meter',
            'quantity': ['2'],
        })
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_cbrn_procedure_rejects_container_steps(self, client):
        resp = client.post(f'{BASE}/cbrn/procedures', json={
            'title': 'Mask drill',
            'steps': {'step': 'mask'},
        })
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_emp_inventory_rejects_container_grid_dependent(self, client):
        resp = client.post(f'{BASE}/emp/inventory', json={
            'item_name': 'Handheld radio',
            'grid_dependent': ['yes'],
        })
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'
