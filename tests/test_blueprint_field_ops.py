"""Payload validation tests for the field_ops blueprint."""


class TestFieldOpsPayloadValidation:
    def test_ics_comms_plan_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/ics/comms-plan',
            data='{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_ics_comms_plan_rejects_non_object(self, client):
        resp = client.post(
            '/api/ics/comms-plan',
            data='[]',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be a JSON object'

    def test_sar_clue_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/sar/clues',
            data='{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_sar_clue_rejects_non_object(self, client):
        resp = client.post(
            '/api/sar/clues',
            data='"string"',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be a JSON object'

    def test_sar_clue_rejects_wrong_shape(self, client):
        for payload in [{'description': 123}, {'lat': 'not_a_number'}]:
            resp = client.post('/api/sar/clues', json=payload)
            assert resp.status_code == 400, payload
            assert resp.get_json()['error'] == 'Validation failed'

    def test_containment_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/sar/containment',
            data='{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_containment_rejects_wrong_shape(self, client):
        resp = client.post('/api/sar/containment', json={'sector': 123})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_tire_pressure_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/calculators/tire-pressure',
            data='{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_tides_rejects_non_object(self, client):
        resp = client.post(
            '/api/calculators/tides',
            data='[1]',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be a JSON object'

    def test_density_altitude_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/calculators/density-altitude',
            data='{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_density_altitude_rejects_wrong_shape(self, client):
        resp = client.post('/api/calculators/density-altitude', json={'field_elevation_ft': 'bad'})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'
