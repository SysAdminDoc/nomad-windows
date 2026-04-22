"""Tests for power blueprint routes."""


class TestPowerDevices:
    def test_list_devices(self, client):
        resp = client.get('/api/power/devices')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_device(self, client):
        resp = client.post('/api/power/devices', json={
            'name': 'Solar Panel 200W', 'device_type': 'solar'
        })
        assert resp.status_code == 201

    def test_create_requires_name_and_type(self, client):
        resp = client.post('/api/power/devices', json={'name': 'Panel Only'})
        assert resp.status_code == 400

    def test_delete_device(self, client):
        create_resp = client.post('/api/power/devices', json={
            'name': 'Temp Device', 'device_type': 'battery'
        })
        assert create_resp.status_code == 201
        devices = client.get('/api/power/devices').get_json()
        did = next(d['id'] for d in devices if d['name'] == 'Temp Device')
        resp = client.delete(f'/api/power/devices/{did}')
        assert resp.status_code == 200


class TestPowerLog:
    def test_list_log(self, client):
        resp = client.get('/api/power/log')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_log_entry(self, client):
        resp = client.post('/api/power/log', json={
            'battery_voltage': 12.6, 'battery_soc': 85, 'solar_watts': 150
        })
        assert resp.status_code == 201


class TestPowerDashboard:
    def test_dashboard_endpoint(self, client):
        resp = client.get('/api/power/dashboard')
        assert resp.status_code == 200

    def test_history_endpoint(self, client):
        resp = client.get('/api/power/history')
        assert resp.status_code == 200
