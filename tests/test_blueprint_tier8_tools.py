"""Payload validation tests for the tier8_tools blueprint."""


class TestTier8ToolsPayloadValidation:
    def test_ooda_create_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/doctrine/ooda',
            data='{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_ooda_create_rejects_non_object(self, client):
        resp = client.post(
            '/api/doctrine/ooda',
            data='[]',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be a JSON object'

    def test_ooda_create_rejects_wrong_shape(self, client):
        resp = client.post('/api/doctrine/ooda', json={'situation': 123})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_aar_create_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/doctrine/aar',
            data='{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_aar_create_rejects_non_object(self, client):
        resp = client.post(
            '/api/doctrine/aar',
            data='"string"',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be a JSON object'

    def test_aar_create_rejects_wrong_shape(self, client):
        resp = client.post('/api/doctrine/aar', json={'event_name': 123})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_cynefin_classify_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/doctrine/cynefin/classify',
            data='{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_pack_animal_rejects_non_object(self, client):
        resp = client.post(
            '/api/calculators/pack-animal',
            data='[1]',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be a JSON object'

    def test_portage_rejects_wrong_shape(self, client):
        resp = client.post('/api/calculators/portage', json={'distance_mi': 'bad'})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_ebike_range_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/calculators/ebike-range',
            data='{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_dutch_oven_rejects_wrong_shape(self, client):
        resp = client.post('/api/calculators/dutch-oven', json={'diameter_in': 'bad'})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_emergency_fund_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/calculators/emergency-fund',
            data='{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_debt_snowball_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/calculators/debt-snowball',
            data='{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_debt_snowball_rejects_non_object(self, client):
        resp = client.post(
            '/api/calculators/debt-snowball',
            data='[]',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be a JSON object'

    def test_debt_snowball_rejects_wrong_shape(self, client):
        resp = client.post('/api/calculators/debt-snowball', json={'debts': 'not_a_list'})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_shadow_stick_rejects_non_object(self, client):
        resp = client.post(
            '/api/calculators/shadow-stick',
            data='99',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be a JSON object'

    def test_dead_reckoning_rejects_wrong_shape(self, client):
        resp = client.post('/api/calculators/dead-reckoning', json={'distance_mi': 'bad'})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'
