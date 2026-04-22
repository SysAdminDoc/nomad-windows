"""Tests for weather blueprint routes."""


class TestWeatherCRUD:
    def test_list_empty(self, client):
        resp = client.get('/api/weather')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_reading(self, client):
        resp = client.post('/api/weather', json={
            'temp_f': 72.5, 'pressure_hpa': 1013.2, 'wind_dir': 'NW', 'clouds': 'partly'
        })
        assert resp.status_code == 201

    def test_create_and_list(self, client):
        client.post('/api/weather', json={'temp_f': 65.0, 'notes': 'Clear skies'})
        resp = client.get('/api/weather')
        assert resp.status_code == 200
        assert len(resp.get_json()) >= 1


class TestWeatherAnalysis:
    def test_trend_insufficient_data(self, client):
        resp = client.get('/api/weather/trend')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'trend' in data

    def test_trend_with_data(self, client):
        for p in [1015.0, 1012.0, 1009.0]:
            client.post('/api/weather', json={'pressure_hpa': p})
        resp = client.get('/api/weather/trend')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['trend'] in ('rising', 'rising_fast', 'falling', 'falling_fast', 'steady', 'insufficient')

    def test_readings_endpoint(self, client):
        resp = client.get('/api/weather/readings')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_predict_endpoint(self, client):
        resp = client.get('/api/weather/predict')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'forecast' in data


class TestWeatherHistory:
    def test_history_endpoint(self, client):
        resp = client.get('/api/weather/history')
        assert resp.status_code == 200
