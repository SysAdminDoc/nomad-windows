"""Tests for comms, weather, and power blueprint endpoints."""


class TestCommsFrequencies:
    def test_freq_list(self, client):
        resp = client.get('/api/comms/frequencies')
        assert resp.status_code == 200

    def test_freq_create(self, client):
        resp = client.post('/api/comms/frequencies', json={
            'frequency': 146.52, 'mode': 'FM', 'service': 'Ham 2m',
            'description': 'National Simplex', 'license_required': 1
        })
        assert resp.status_code in (200, 201)

    def test_freq_delete_nonexistent(self, client):
        resp = client.delete('/api/comms/frequencies/999999')
        assert resp.status_code == 404


class TestCommsSchedules:
    def test_schedules_list(self, client):
        resp = client.get('/api/comms/schedules')
        assert resp.status_code == 200

    def test_schedule_create(self, client):
        resp = client.post('/api/comms/schedules', json={
            'frequency': '146.520', 'mode': 'FM', 'net_name': 'Morning Net',
            'check_in_time': '08:00', 'priority': 5
        })
        assert resp.status_code in (200, 201)

    def test_schedule_delete_nonexistent(self, client):
        resp = client.delete('/api/comms/schedules/999999')
        assert resp.status_code == 404


class TestCommsRadioProfiles:
    def test_profiles_list(self, client):
        resp = client.get('/api/comms/radio-profiles')
        assert resp.status_code == 200

    def test_profile_create(self, client):
        resp = client.post('/api/comms/radio-profiles', json={
            'name': 'GMRS Profile', 'channels': [
                {'channel': 1, 'frequency': '462.5625', 'name': 'GMRS1'}
            ]
        })
        assert resp.status_code in (200, 201)

    def test_profile_delete_nonexistent(self, client):
        resp = client.delete('/api/comms/radio-profiles/999999')
        assert resp.status_code == 404


class TestCommsLog:
    def test_log_list(self, client):
        resp = client.get('/api/comms-log')
        assert resp.status_code == 200

    def test_log_create(self, client):
        resp = client.post('/api/comms-log', json={
            'freq': '146.520', 'callsign': 'W1ABC',
            'direction': 'rx', 'message': 'Check-in received',
        })
        assert resp.status_code in (200, 201)

    def test_log_delete_nonexistent(self, client):
        resp = client.delete('/api/comms-log/999999')
        assert resp.status_code == 404


class TestCommsPresence:
    def test_presence_list(self, client):
        resp = client.get('/api/lan/presence')
        assert resp.status_code == 200


class TestCommsStatusBoard:
    def test_status_board(self, client):
        resp = client.get('/api/comms/status-board')
        assert resp.status_code == 200


class TestWeatherStorms:
    def test_storm_list(self, client):
        resp = client.get('/api/weather/storms')
        assert resp.status_code == 200


class TestWeatherActionRules:
    def test_rules_list(self, client):
        resp = client.get('/api/weather/action-rules')
        assert resp.status_code == 200

    def test_rule_create(self, client):
        resp = client.post('/api/weather/action-rules', json={
            'name': 'Cold Alert', 'condition_type': 'temp_low',
            'threshold': 32, 'comparison': 'lt',
            'action_type': 'alert',
        })
        assert resp.status_code in (200, 201)
        data = resp.get_json()
        assert data.get('id') or data.get('name')

    def test_rule_delete_nonexistent(self, client):
        resp = client.delete('/api/weather/action-rules/999999')
        assert resp.status_code == 404


class TestPowerGenerators:
    def test_generator_create(self, client):
        resp = client.post('/api/power/generators', json={
            'name': 'Honda EU2200i', 'rated_watts': 2200,
            'fuel_type': 'gasoline', 'tank_capacity_gal': 0.95,
        })
        assert resp.status_code in (200, 201)

    def test_generator_list(self, client):
        resp = client.get('/api/power/generators')
        assert resp.status_code == 200

    def test_generator_update_nonexistent(self, client):
        resp = client.put('/api/power/generators/999999', json={'name': 'X'})
        assert resp.status_code == 404

    def test_generator_delete_nonexistent(self, client):
        resp = client.delete('/api/power/generators/999999')
        assert resp.status_code == 404


class TestPowerSolar:
    def test_solar_forecast(self, client):
        resp = client.get('/api/power/solar-forecast?lat=40.0&lng=-74.0&panel_watts=300')
        assert resp.status_code == 200

    def test_solar_forecast_missing_lat(self, client):
        resp = client.get('/api/power/solar-forecast')
        assert resp.status_code in (200, 400)

    def test_solar_history(self, client):
        resp = client.get('/api/power/solar-history')
        assert resp.status_code == 200
