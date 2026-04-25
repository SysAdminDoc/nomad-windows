"""Tests for the hardware_sensors blueprint.

Covers IoT sensors/readings/dashboard, network topology, mesh node upsert/map
stats, weather station JSON payloads, GPS fixes, wearable filters, integration
validation, and reference data.
"""

from datetime import datetime as real_datetime

from db import db_session
from web.blueprints import hardware_sensors as hw


def _create_sensor(client, **overrides):
    body = {
        'name': overrides.pop('name', 'Freezer probe'),
        'sensor_type': overrides.pop('sensor_type', 'temperature'),
        'battery_pct': overrides.pop('battery_pct', 15),
        'alert_enabled': overrides.pop('alert_enabled', True),
    }
    body.update(overrides)
    resp = client.post('/api/hardware/sensors', json=body)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()['id']


def _create_network_device(client, **overrides):
    body = {
        'name': overrides.pop('name', 'Gateway'),
        'device_type': overrides.pop('device_type', 'router'),
        'status': overrides.pop('status', 'online'),
    }
    body.update(overrides)
    resp = client.post('/api/hardware/network', json=body)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()['id']


def _create_gps(client, **overrides):
    body = {'name': overrides.pop('name', 'Field GPS')}
    body.update(overrides)
    resp = client.post('/api/hardware/gps', json=body)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()['id']


class TestHardwareReferenceAndSensors:
    def test_sensor_types_reference(self, client):
        data = client.get('/api/hardware/reference/sensor-types').get_json()

        assert data['temperature']['unit'] == '\u00b0F'
        assert data['radiation']['typical_range'] == [0.0, 100.0]
        assert 'soil_moisture' in data

    def test_sensor_create_defaults_and_filters(self, client):
        freezer_id = _create_sensor(client)
        _create_sensor(client, name='Cistern level', sensor_type='water_level',
                       status='inactive', alert_enabled=False, battery_pct=88)

        freezer = client.get(f'/api/hardware/sensors/{freezer_id}').get_json()
        assert freezer['name'] == 'Freezer probe'
        assert freezer['unit'] == '\u00b0F'
        assert freezer['alert_enabled'] == 1

        active = client.get('/api/hardware/sensors?status=active').get_json()
        assert [row['name'] for row in active] == ['Freezer probe']

        water = client.get('/api/hardware/sensors?type=water_level').get_json()
        assert [row['name'] for row in water] == ['Cistern level']

    def test_sensor_validation_update_delete(self, client):
        assert client.post('/api/hardware/sensors', json={'name': '   '}).status_code == 400

        sid = _create_sensor(client)
        assert client.put(f'/api/hardware/sensors/{sid}', json={}).status_code == 400
        resp = client.put(f'/api/hardware/sensors/{sid}',
                          json={'status': 'maintenance', 'battery_pct': 55})
        assert resp.status_code == 200

        updated = client.get(f'/api/hardware/sensors/{sid}').get_json()
        assert updated['status'] == 'maintenance'
        assert updated['battery_pct'] == 55

        assert client.delete(f'/api/hardware/sensors/{sid}').status_code == 200
        assert client.get(f'/api/hardware/sensors/{sid}').status_code == 404

    def test_sensor_reading_updates_current_value_and_recent_list(self, client):
        sid = _create_sensor(client)

        resp = client.post(f'/api/hardware/sensors/{sid}/reading',
                           json={'value': '72.5', 'raw_value': '72.50F'})
        assert resp.status_code == 201

        sensor = client.get(f'/api/hardware/sensors/{sid}').get_json()
        assert sensor['current_value'] == '72.5'
        assert sensor['recent_readings'][0]['value'] == 72.5
        assert sensor['recent_readings'][0]['raw_value'] == '72.50F'

    def test_sensor_reading_validation(self, client):
        sid = _create_sensor(client)

        assert client.post(f'/api/hardware/sensors/{sid}/reading', json={}).status_code == 400
        resp = client.post(f'/api/hardware/sensors/{sid}/reading',
                           json={'value': 'not-numeric'})
        assert resp.status_code == 400
        assert client.post('/api/hardware/sensors/99999/reading',
                           json={'value': 1}).status_code == 404

    def test_readings_and_dashboard_use_sql_timestamp_cutoff(self, client, monkeypatch):
        class FrozenDateTime(real_datetime):
            @classmethod
            def utcnow(cls):
                return real_datetime(2026, 1, 1, 12, 0, 0)

        monkeypatch.setattr(hw, 'datetime', FrozenDateTime)
        sid = _create_sensor(client)
        with db_session() as db:
            db.execute(
                '''INSERT INTO iot_sensor_readings
                   (sensor_id, value, raw_value, unit, quality, timestamp, created_at)
                   VALUES (?,?,?,?,?,?,?)''',
                (sid, 41.0, '41', '\u00b0F', 'good',
                 '2026-01-01T11:30:00Z', '2026-01-01 11:30:00')
            )
            db.commit()

        readings = client.get(f'/api/hardware/sensors/{sid}/readings?hours=1').get_json()
        assert [row['value'] for row in readings] == [41.0]

        dashboard = client.get('/api/hardware/sensors/dashboard').get_json()
        assert dashboard['total_sensors'] == 1
        assert dashboard['by_type'] == {'temperature': 1}
        assert dashboard['alerts_enabled'] == 1
        assert dashboard['low_battery'][0]['name'] == 'Freezer probe'
        assert dashboard['readings_24h'] == 1


class TestHardwareNetworkAndMesh:
    def test_network_topology_and_scan(self, client):
        gateway_id = _create_network_device(client, vlan='10', port_count='24')
        repeater_id = _create_network_device(
            client, name='Repeater', device_type='switch', uplink_to=gateway_id,
            vlan='10', status='degraded'
        )

        scan = client.get('/api/hardware/network/scan').get_json()
        assert scan['total'] == 2
        assert scan['by_type'] == {'router': 1, 'switch': 1}
        assert scan['by_status'] == {'degraded': 1, 'online': 1}
        assert scan['by_vlan'] == {'10': 2}

        topology = client.get('/api/hardware/network/topology').get_json()
        assert topology[0]['id'] == gateway_id
        assert topology[0]['children'][0]['id'] == repeater_id

    def test_network_validation_update_delete(self, client):
        assert client.post('/api/hardware/network', json={'name': ''}).status_code == 400

        did = _create_network_device(client)
        assert client.put(f'/api/hardware/network/{did}', json={}).status_code == 400
        assert client.put('/api/hardware/network/99999', json={'status': 'offline'}).status_code == 404

        resp = client.put(f'/api/hardware/network/{did}', json={'status': 'offline'})
        assert resp.status_code == 200
        assert client.get(f'/api/hardware/network/{did}').get_json()['status'] == 'offline'

        assert client.delete(f'/api/hardware/network/{did}').status_code == 200
        assert client.delete(f'/api/hardware/network/{did}').status_code == 404

    def test_mesh_create_upsert_map_and_stats(self, client):
        created = client.post('/api/hardware/mesh', json={
            'node_id': '!abc123',
            'long_name': 'Ridge relay',
            'short_name': 'RIDG',
            'role': 'router',
            'latitude': 39.5,
            'longitude': -105.2,
            'battery_level': 80,
            'snr': 7.5,
            'hops_away': 2,
        })
        assert created.status_code == 201
        mid = created.get_json()['id']

        updated = client.post('/api/hardware/mesh', json={
            'node_id': '!abc123',
            'long_name': 'Ridge relay updated',
            'battery_level': 70,
        })
        assert updated.status_code == 200
        assert updated.get_json() == {'id': mid, 'status': 'updated'}

        mapped = client.get('/api/hardware/mesh/map').get_json()
        assert mapped[0]['long_name'] == 'Ridge relay updated'

        stats = client.get('/api/hardware/mesh/stats').get_json()
        assert stats['total_nodes'] == 1
        assert stats['by_role'] == {'router': 1}
        assert stats['avg_battery'] == 70.0
        assert stats['avg_snr'] == 7.5
        assert stats['max_hops'] == 2

        assert client.delete(f'/api/hardware/mesh/{mid}').status_code == 200

    def test_mesh_validation(self, client):
        assert client.post('/api/hardware/mesh', json={'long_name': 'missing id'}).status_code == 400
        assert client.get('/api/hardware/mesh/99999').status_code == 404


class TestHardwareFieldDevices:
    def test_weather_station_json_payload_round_trips(self, client):
        created = client.post('/api/hardware/weather-stations', json={
            'name': 'Barn station',
            'current_data': {'temp_f': 65.5, 'wind_mph': 8},
            'polling_interval_sec': 0,
        })
        assert created.status_code == 201
        wid = created.get_json()['id']

        station = client.get(f'/api/hardware/weather-stations/{wid}').get_json()
        assert station['current_data'] == {'temp_f': 65.5, 'wind_mph': 8}
        assert station['polling_interval_sec'] == 60

        resp = client.put(f'/api/hardware/weather-stations/{wid}',
                          json={'current_data': {'rain_in': 0.2}})
        assert resp.status_code == 200
        assert client.get(f'/api/hardware/weather-stations/{wid}').get_json()['current_data'] == {
            'rain_in': 0.2,
        }

    def test_gps_fix_accepts_zero_coordinates(self, client):
        gid = _create_gps(client)

        resp = client.post(f'/api/hardware/gps/{gid}/fix', json={
            'lat': 0,
            'lon': 0,
            'alt': 12,
            'accuracy_m': 3.5,
            'satellites': 9,
        })
        assert resp.status_code == 200, resp.get_data(as_text=True)

        gps = client.get(f'/api/hardware/gps/{gid}').get_json()
        assert gps['last_fix_lat'] == 0.0
        assert gps['last_fix_lon'] == 0.0
        assert gps['last_fix_alt'] == 12.0
        assert gps['accuracy_m'] == 3.5
        assert gps['satellites'] == 9
        assert gps['status'] == 'fix'

    def test_gps_fix_validation(self, client):
        gid = _create_gps(client)

        assert client.post(f'/api/hardware/gps/{gid}/fix', json={'lat': 1}).status_code == 400
        assert client.post(f'/api/hardware/gps/{gid}/fix',
                           json={'lat': 'north', 'lon': 1}).status_code == 400
        assert client.post('/api/hardware/gps/99999/fix',
                           json={'lat': 1, 'lon': 2}).status_code == 404

    def test_wearables_current_data_and_wearer_filter(self, client):
        created = client.post('/api/hardware/wearables', json={
            'name': 'Pulse band',
            'wearer': 'Alex',
            'current_data': {'hr': 72, 'spo2': 98},
            'battery_pct': 101,
        })
        assert created.status_code == 201
        wid = created.get_json()['id']

        wearable = client.get(f'/api/hardware/wearables/{wid}').get_json()
        assert wearable['current_data'] == {'hr': 72, 'spo2': 98}
        assert wearable['battery_pct'] == 100

        alex = client.get('/api/hardware/wearables?wearer=Alex').get_json()
        assert [row['name'] for row in alex] == ['Pulse band']
        assert client.get('/api/hardware/wearables?wearer=Sam').get_json() == []


class TestHardwareIntegrations:
    def test_integration_validation_failure_and_recovery(self, client):
        created = client.post('/api/hardware/integrations', json={
            'name': 'REST bridge',
            'integration_type': 'rest',
            'config_json': {'topic': 'sensors/freezer'},
        })
        assert created.status_code == 201
        iid = created.get_json()['id']

        failed = client.post(f'/api/hardware/integrations/{iid}/test').get_json()
        assert failed['success'] is False
        assert failed['errors'] == [
            'endpoint_url is empty',
            'no api_key or auth_token configured',
        ]
        assert client.get(f'/api/hardware/integrations/{iid}').get_json()['status'] == 'error'

        resp = client.put(f'/api/hardware/integrations/{iid}', json={
            'endpoint_url': 'https://example.invalid/api',
            'api_key': 'test-key',
        })
        assert resp.status_code == 200

        passed = client.post(f'/api/hardware/integrations/{iid}/test').get_json()
        assert passed['success'] is True
        integration = client.get(f'/api/hardware/integrations/{iid}').get_json()
        assert integration['status'] == 'active'
        assert integration['config_json'] == {'topic': 'sensors/freezer'}

    def test_integration_rejects_invalid_json_config_on_test(self, client):
        created = client.post('/api/hardware/integrations', json={
            'name': 'Webhook bridge',
            'integration_type': 'webhook',
            'endpoint_url': 'https://example.invalid/hook',
            'auth_token': 'token',
            'config_json': '{bad',
        })
        assert created.status_code == 201
        iid = created.get_json()['id']

        result = client.post(f'/api/hardware/integrations/{iid}/test').get_json()
        assert result == {'success': False, 'errors': ['config_json is not valid JSON']}

    def test_integration_validation_update_delete(self, client):
        assert client.post('/api/hardware/integrations', json={'name': ''}).status_code == 400

        created = client.post('/api/hardware/integrations', json={'name': 'MQTT bridge'})
        iid = created.get_json()['id']
        assert client.put(f'/api/hardware/integrations/{iid}', json={}).status_code == 400
        assert client.put('/api/hardware/integrations/99999',
                          json={'status': 'active'}).status_code == 404
        assert client.delete(f'/api/hardware/integrations/{iid}').status_code == 200
        assert client.post(f'/api/hardware/integrations/{iid}/test').status_code == 404
