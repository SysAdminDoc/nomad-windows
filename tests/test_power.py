"""Tests for power management API routes."""


class TestPowerDevices:
    def test_list_devices(self, client):
        resp = client.get('/api/power/devices')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_device(self, client):
        resp = client.post('/api/power/devices', json={
            'name': 'Goal Zero Yeti 1500',
            'device_type': 'battery',
            'specs': {'capacity_wh': 1500, 'output_w': 2000},
            'notes': 'Primary power station',
        })
        assert resp.status_code == 201
        assert resp.get_json()['status'] == 'created'

    def test_create_requires_name_and_type(self, client):
        resp = client.post('/api/power/devices', json={'name': 'Missing type'})
        assert resp.status_code == 400
        resp = client.post('/api/power/devices', json={'device_type': 'solar'})
        assert resp.status_code == 400

    def test_delete_device(self, client):
        client.post('/api/power/devices', json={
            'name': 'Temp Device',
            'device_type': 'generator',
        })
        devices = client.get('/api/power/devices').get_json()
        temp = next((d for d in devices if d['name'] == 'Temp Device'), None)
        assert temp is not None
        resp = client.delete(f'/api/power/devices/{temp["id"]}')
        assert resp.status_code == 200

    def test_list_devices_recovers_from_corrupted_specs(self, client, db):
        client.post('/api/power/devices', json={
            'name': 'Broken Specs Device',
            'device_type': 'battery',
            'specs': {'capacity_wh': 1200},
        })
        db.execute("UPDATE power_devices SET specs = ? WHERE name = ?", ('{broken', 'Broken Specs Device'))
        db.commit()

        resp = client.get('/api/power/devices')

        assert resp.status_code == 200
        device = next(item for item in resp.get_json() if item['name'] == 'Broken Specs Device')
        assert device['specs'] == {}


class TestPowerLog:
    def test_list_log(self, client):
        resp = client.get('/api/power/log')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_log_entry(self, client):
        resp = client.post('/api/power/log', json={
            'battery_voltage': 12.8,
            'battery_soc': 85,
            'solar_watts': 200,
            'load_watts': 150,
            'generator_running': False,
        })
        assert resp.status_code == 201
        assert resp.get_json()['status'] == 'logged'


class TestPowerDashboard:
    def test_dashboard(self, client):
        resp = client.get('/api/power/dashboard')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'total_solar_w' in data
        assert 'total_battery_wh' in data
        assert 'device_count' in data

    def test_dashboard_after_log(self, client):
        client.post('/api/power/devices', json={
            'name': 'Solar Panel',
            'device_type': 'solar',
            'specs': {'watts': 400},
        })
        client.post('/api/power/log', json={
            'battery_voltage': 13.2,
            'battery_soc': 95,
            'solar_watts': 380,
            'load_watts': 100,
        })
        resp = client.get('/api/power/dashboard')
        data = resp.get_json()
        assert data['device_count'] >= 1
        assert data['log_count'] >= 1

    def test_dashboard_recovers_from_corrupted_active_device_specs(self, client, db):
        client.post('/api/power/devices', json={
            'name': 'Broken Dashboard Battery',
            'device_type': 'battery',
            'specs': {'capacity_wh': 2000},
        })
        db.execute(
            "UPDATE power_devices SET status = 'active', specs = ? WHERE name = ?",
            ('{broken', 'Broken Dashboard Battery'),
        )
        db.commit()

        resp = client.get('/api/power/dashboard')

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['device_count'] >= 1
        assert data['total_battery_wh'] == 0


class TestPowerHistory:
    def test_history_default(self, client):
        resp = client.get('/api/power/history')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_history_7d(self, client):
        resp = client.get('/api/power/history?period=7d')
        assert resp.status_code == 200

    def test_history_30d(self, client):
        resp = client.get('/api/power/history?period=30d')
        assert resp.status_code == 200


class TestPowerAutonomy:
    def test_autonomy_forecast(self, client):
        resp = client.get('/api/power/autonomy-forecast')
        assert resp.status_code == 200
        data = resp.get_json()
        # Either has forecast data or "no data" message
        assert 'days' in data or 'message' in data

    def test_autonomy_forecast_recovers_from_corrupted_battery_specs(self, client, db):
        client.post('/api/power/log', json={
            'battery_soc': 80,
            'solar_watts': 100,
            'load_watts': 300,
        })
        client.post('/api/power/devices', json={
            'name': 'Broken Autonomy Battery',
            'device_type': 'battery',
            'specs': {'capacity_wh': 1500},
        })
        db.execute(
            "UPDATE power_devices SET status = 'active', specs = ? WHERE name = ?",
            ('{broken', 'Broken Autonomy Battery'),
        )
        db.commit()

        resp = client.get('/api/power/autonomy-forecast')

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['days'] is not None
        assert data['hours'] > 0


class TestSolarResilience:
    def test_solar_forecast_recovers_from_corrupted_map_center(self, client, db):
        client.post('/api/waypoints', json={'name': 'Solar Fallback', 'lat': 40.1, 'lng': -105.2})
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('map_center', ?)", ('{broken',))
        db.commit()

        resp = client.get('/api/power/solar-forecast')

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['lat'] == 40.1
        assert data['lng'] == -105.2

    def test_solar_history_recovers_from_corrupted_map_center(self, client, db):
        client.post('/api/waypoints', json={'name': 'Solar History Fallback', 'lat': 39.9, 'lng': -104.9})
        client.post('/api/power/log', json={'solar_wh_today': 900, 'solar_watts': 180})
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('map_center', ?)", ('{broken',))
        db.commit()

        resp = client.get('/api/power/solar-history')

        assert resp.status_code == 200
        history = resp.get_json()
        assert isinstance(history, list)
        assert len(history) == 30


class TestLoadScheduleResilience:
    def test_load_schedule_recovers_from_corrupted_specs(self, client, db):
        client.post('/api/power/devices', json={
            'name': 'Broken Load Device',
            'device_type': 'light',
            'specs': {'watts': 60, 'count': 2},
        })
        db.execute(
            "UPDATE power_devices SET status = 'active', specs = ? WHERE name = ?",
            ('{broken', 'Broken Load Device'),
        )
        db.commit()

        resp = client.get('/api/power/load-schedule')

        assert resp.status_code == 200
        data = resp.get_json()
        device = next(item for item in data['devices']['medium'] if item['name'] == 'Broken Load Device')
        assert device['specs'] == {}
        assert device['watts'] == 0
