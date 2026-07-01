"""Payload validation tests for the field_tools blueprint."""


class TestFieldToolsPayloadValidation:
    def test_radio_create_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/codeplug/radios',
            data='{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_radio_create_rejects_non_object_json(self, client):
        resp = client.post(
            '/api/codeplug/radios',
            data='[]',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be a JSON object'

    def test_radio_create_rejects_wrong_shape(self, client):
        for payload in [{'name': 123}, {'max_channels': 'not_a_number'}]:
            resp = client.post('/api/codeplug/radios', json=payload)
            assert resp.status_code == 400, payload
            assert resp.get_json()['error'] == 'Validation failed'

    def test_zone_create_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/codeplug/1/zones',
            data='{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_zone_create_rejects_non_object(self, client):
        resp = client.post(
            '/api/codeplug/1/zones',
            data='"just a string"',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be a JSON object'

    def test_channel_create_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/codeplug/1/channels',
            data='{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_channel_create_rejects_wrong_shape(self, client):
        resp = client.post('/api/codeplug/1/channels', json={'frequency_mhz': 'not_a_number'})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_import_freqs_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/codeplug/1/import-frequencies',
            data='{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_import_freqs_rejects_non_object(self, client):
        resp = client.post(
            '/api/codeplug/1/import-frequencies',
            data='[1,2,3]',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be a JSON object'

    def test_rainwater_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/calculators/rainwater',
            data='{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_rainwater_rejects_wrong_shape(self, client):
        resp = client.post('/api/calculators/rainwater', json={'roof_sqft': 'not_a_number'})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'
