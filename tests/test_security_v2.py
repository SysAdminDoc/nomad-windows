"""Tests for perimeter zones and motion detection API routes."""

import json


class TestPerimeterZones:
    def test_security_dashboard_recovers_from_corrupted_sit_board(self, client, db):
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('sit_board', ?)", ('{broken',))
        db.commit()

        resp = client.get('/api/security/dashboard')

        assert resp.status_code == 200
        assert resp.get_json()['security_level'] == 'green'

    def test_perimeter_zones_list(self, client):
        resp = client.get('/api/security/zones')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_perimeter_zone_create(self, client):
        resp = client.post('/api/security/zones', json={
            'name': 'North Perimeter',
            'zone_type': 'perimeter',
            'threat_level': 'elevated',
            'color': '#ff8800',
            'notes': 'Fence line along highway',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert 'id' in data

    def test_perimeter_zone_create_no_name(self, client):
        # An empty-string name after strip should fall through to the default 'New Zone'
        # but a truly blank name="" with strip gives '', which the code defaults to 'New Zone'
        # The code does: name = (data.get('name','') or 'New Zone').strip()[:200]
        # So empty string becomes 'New Zone', not 400. Let's test that a zone is created.
        resp = client.post('/api/security/zones', json={'name': ''})
        # The code defaults empty name to 'New Zone' — so this succeeds
        assert resp.status_code == 201

    def test_perimeter_zone_update(self, client):
        create = client.post('/api/security/zones', json={'name': 'South Wall'})
        zid = create.get_json()['id']
        resp = client.put(f'/api/security/zones/{zid}', json={
            'name': 'South Wall — Reinforced',
            'threat_level': 'high',
        })
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'updated'

    def test_perimeter_zone_delete(self, client):
        create = client.post('/api/security/zones', json={'name': 'Temp Zone'})
        zid = create.get_json()['id']
        resp = client.delete(f'/api/security/zones/{zid}')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'deleted'

    def test_perimeter_zones_geo(self, client):
        # Create a zone with GeoJSON boundary
        client.post('/api/security/zones', json={
            'name': 'Geo Test Zone',
            'boundary_geojson': json.dumps({
                'type': 'Polygon',
                'coordinates': [[[-104.0, 39.0], [-104.0, 39.1], [-103.9, 39.1], [-103.9, 39.0], [-104.0, 39.0]]],
            }),
        })
        resp = client.get('/api/security/zones/geo')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['type'] == 'FeatureCollection'
        assert isinstance(data['features'], list)

    def test_perimeter_zones_list_recovers_from_corrupted_link_ids(self, client, db):
        created = client.post('/api/security/zones', json={
            'name': 'Broken Link Zone',
            'camera_ids': [1, 2],
            'waypoint_ids': [3, 4],
        }).get_json()
        db.execute('UPDATE perimeter_zones SET camera_ids = ?, waypoint_ids = ? WHERE id = ?', ('{broken', '{broken', created['id']))
        db.commit()

        resp = client.get('/api/security/zones')

        assert resp.status_code == 200
        zone = next(item for item in resp.get_json() if item['id'] == created['id'])
        assert zone['camera_ids'] == []
        assert zone['waypoint_ids'] == []

    def test_perimeter_zones_geo_skips_corrupted_boundary_geojson(self, client, db):
        valid = client.post('/api/security/zones', json={
            'name': 'Valid Geo Zone',
            'boundary_geojson': json.dumps({
                'type': 'Polygon',
                'coordinates': [[[-104.0, 39.0], [-104.0, 39.1], [-103.9, 39.1], [-103.9, 39.0], [-104.0, 39.0]]],
            }),
        }).get_json()
        broken = client.post('/api/security/zones', json={'name': 'Broken Geo Zone'}).get_json()
        db.execute('UPDATE perimeter_zones SET boundary_geojson = ? WHERE id = ?', ('{broken', broken['id']))
        db.commit()

        resp = client.get('/api/security/zones/geo')

        assert resp.status_code == 200
        data = resp.get_json()
        names = {feature['properties']['name'] for feature in data['features']}
        assert 'Valid Geo Zone' in names
        assert 'Broken Geo Zone' not in names

    def test_perimeter_zone_geojson_size_limit(self, client):
        # A boundary larger than 500KB should be rejected
        huge_geojson = 'x' * 600000
        resp = client.post('/api/security/zones', json={
            'name': 'Huge Zone',
            'boundary_geojson': huge_geojson,
        })
        assert resp.status_code == 400
        assert '500KB' in resp.get_json()['error']

    def test_perimeter_zone_invalid_color(self, client):
        # An invalid color should be sanitized to the default #ff0000
        resp = client.post('/api/security/zones', json={
            'name': 'Bad Color Zone',
            'color': 'not-a-color',
        })
        assert resp.status_code == 201
        # Verify the zone was saved (color would default to #ff0000 internally)
        zones = client.get('/api/security/zones').get_json()
        bad_zone = [z for z in zones if z['name'] == 'Bad Color Zone']
        assert len(bad_zone) == 1

    def test_check_breach_recovers_from_corrupted_camera_ids(self, client, db):
        broken = client.post('/api/security/zones', json={'name': 'Broken Breach Zone'}).get_json()
        valid = client.post('/api/security/zones', json={
            'name': 'Valid Breach Zone',
            'camera_ids': [7],
            'alert_on_entry': True,
        }).get_json()
        db.execute('UPDATE perimeter_zones SET camera_ids = ?, alert_on_entry = 1 WHERE id = ?', ('{broken', broken['id']))
        db.commit()

        resp = client.post('/api/security/zones/check-breach', json={'camera_id': 7})

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['breaches'] == [{
            'zone_id': valid['id'],
            'zone_name': 'Valid Breach Zone',
            'zone_type': 'perimeter',
        }]


class TestMotionDetection:
    def test_motion_status(self, client):
        resp = client.get('/api/security/motion/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'detectors' in data
        assert 'config' in data
        assert isinstance(data['detectors'], dict)

    def test_motion_start_no_opencv(self, client):
        # In a test environment cv2 is typically not installed, so we expect 503
        resp = client.post('/api/security/motion/start/1')
        # Either 503 (no cv2) or 404 (no camera found) are valid
        assert resp.status_code in (503, 404)

    def test_motion_configure_valid(self, client):
        resp = client.post('/api/security/motion/configure', json={
            'threshold': 50,
            'check_interval': 10,
            'cooldown': 30,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['config']['threshold'] == 50
        assert data['config']['check_interval'] == 10
        assert data['config']['cooldown'] == 30

    def test_motion_configure_invalid_type(self, client):
        resp = client.post('/api/security/motion/configure', json={
            'threshold': 'not_a_number',
        })
        assert resp.status_code == 400

    def test_motion_configure_clamps_values(self, client):
        resp = client.post('/api/security/motion/configure', json={
            'threshold': 999,
            'check_interval': 0,
            'cooldown': 1,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['config']['threshold'] == 100
        assert data['config']['check_interval'] == 1
        assert data['config']['cooldown'] == 5
