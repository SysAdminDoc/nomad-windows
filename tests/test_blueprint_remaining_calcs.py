"""Payload validation tests for the remaining_calcs blueprint."""


class TestRemainingCalcsPayloadValidation:
    def test_polaris_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/calculators/polaris-latitude',
            data='{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_polaris_rejects_non_object(self, client):
        resp = client.post(
            '/api/calculators/polaris-latitude',
            data='[]',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be a JSON object'

    def test_sun_clock_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/calculators/sun-clock',
            data='{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_sun_clock_rejects_wrong_shape(self, client):
        resp = client.post('/api/calculators/sun-clock', json={'sun_altitude_deg': 'bad'})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_barometric_rejects_non_object(self, client):
        resp = client.post(
            '/api/calculators/barometric-altimeter',
            data='"string"',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be a JSON object'

    def test_rocket_stove_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/calculators/rocket-stove',
            data='{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_haybox_rejects_wrong_shape(self, client):
        resp = client.post('/api/calculators/haybox', json={'initial_temp_f': 'bad'})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_bulk_cooking_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/calculators/bulk-cooking',
            data='{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_portfolio_stress_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/calculators/portfolio-stress',
            data='{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_portfolio_stress_rejects_non_object(self, client):
        resp = client.post(
            '/api/calculators/portfolio-stress',
            data='[]',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be a JSON object'

    def test_portfolio_stress_rejects_wrong_shape(self, client):
        resp = client.post('/api/calculators/portfolio-stress', json={'assets': 'not_a_list'})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_income_diversification_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/calculators/income-diversification',
            data='{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_income_diversification_rejects_non_object(self, client):
        resp = client.post(
            '/api/calculators/income-diversification',
            data='[]',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be a JSON object'

    def test_income_diversification_rejects_wrong_shape(self, client):
        resp = client.post(
            '/api/calculators/income-diversification',
            json={'income_streams': 'not_a_list'},
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'
