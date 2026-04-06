"""Tests for weather API routes including Zambretti prediction."""

from db import db_session


class TestWeatherLog:
    def test_empty_list(self, client):
        resp = client.get('/api/weather')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_create_reading(self, client):
        resp = client.post('/api/weather', json={
            'pressure_hpa': 1013.25,
            'temp_f': 72,
            'wind_dir': 'NW',
            'wind_speed': '10',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['pressure_hpa'] == 1013.25
        assert data['temp_f'] == 72

    def test_list_with_limit(self, client):
        for i in range(5):
            client.post('/api/weather', json={'pressure_hpa': 1010 + i, 'temp_f': 70})
        resp = client.get('/api/weather?limit=3')
        assert len(resp.get_json()) == 3


class TestWeatherReadings:
    def test_add_reading(self, client):
        resp = client.post('/api/weather/readings', json={
            'source': 'manual',
            'pressure_hpa': 1015.0,
            'temp_f': 68,
            'humidity': 55,
        })
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'ok'

    def test_get_readings(self, client):
        client.post('/api/weather/readings', json={'pressure_hpa': 1013, 'temp_f': 70})
        resp = client.get('/api/weather/readings?hours=24')
        assert resp.status_code == 200


class TestWeatherTrend:
    def test_trend_returns_valid_response(self, client):
        resp = client.get('/api/weather/trend')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'trend' in data

    def test_trend_with_data(self, client):
        # Add multiple readings to establish trend
        for pressure in [1010, 1012, 1014, 1016, 1018]:
            client.post('/api/weather', json={'pressure_hpa': pressure, 'temp_f': 70})
        resp = client.get('/api/weather/trend')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'trend' in data


class TestZambrettiPredict:
    def test_predict_insufficient_data(self, client):
        resp = client.get('/api/weather/predict')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'forecast' in data or 'trend' in data

    def test_predict_with_rising_pressure(self, client):
        # Seed weather_readings with rising pressure pattern
        for i, pressure in enumerate([1005, 1008, 1010, 1013, 1016, 1018]):
            client.post('/api/weather/readings', json={
                'pressure_hpa': pressure,
                'temp_f': 65,
                'source': 'test',
            })
        resp = client.get('/api/weather/predict')
        assert resp.status_code == 200
        data = resp.get_json()
        # Rising pressure should predict fair/improving weather
        assert 'forecast' in data

    def test_predict_with_falling_pressure(self, client):
        for pressure in [1025, 1022, 1018, 1014, 1010, 1005]:
            client.post('/api/weather/readings', json={
                'pressure_hpa': pressure,
                'temp_f': 60,
                'source': 'test',
            })
        resp = client.get('/api/weather/predict')
        data = resp.get_json()
        assert 'forecast' in data


class TestWeatherActionRuleResilience:
    def test_action_rules_list_recovers_from_corrupted_action_data(self, client):
        with db_session() as db:
            db.execute(
                'INSERT INTO weather_action_rules (name, condition_type, threshold, comparison, action_type, action_data, cooldown_minutes) VALUES (?, ?, ?, ?, ?, ?, ?)',
                ('Broken Rule', 'temp_high', 90, 'gte', 'alert', '{broken', 60),
            )
            db.commit()

        resp = client.get('/api/weather/action-rules')
        assert resp.status_code == 200
        data = resp.get_json()
        target = next((rule for rule in data if rule['name'] == 'Broken Rule'), None)
        assert target is not None
        assert target['action_data'] == {}

    def test_evaluate_rules_recovers_from_corrupted_action_data(self, client):
        client.post('/api/weather/readings', json={'pressure_hpa': 1012, 'temp_f': 102, 'source': 'test'})
        with db_session() as db:
            db.execute(
                'INSERT INTO weather_action_rules (name, condition_type, threshold, comparison, action_type, action_data, cooldown_minutes) VALUES (?, ?, ?, ?, ?, ?, ?)',
                ('Hot Rule', 'temp_high', 100, 'gte', 'alert', '{broken', 0),
            )
            db.commit()

        resp = client.post('/api/weather/evaluate-rules')
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data['triggered']) == 1
        assert data['triggered'][0]['name'] == 'Hot Rule'

    def test_create_action_rule_accepts_json_string_action_data(self, client):
        resp = client.post('/api/weather/action-rules', json={
            'name': 'String Action Data',
            'condition_type': 'temp_high',
            'threshold': 95,
            'comparison': 'gte',
            'action_type': 'alert',
            'action_data': '{"severity":"critical","title":"Heat Alert"}',
        })
        assert resp.status_code == 201

        with db_session() as db:
            row = db.execute('SELECT action_data FROM weather_action_rules WHERE name = ?', ('String Action Data',)).fetchone()
        assert row is not None
        assert row['action_data'] == '{"severity": "critical", "title": "Heat Alert"}'
