"""Tests for maps/waypoints/routes blueprint routes."""

import json


class TestWaypointCRUD:
    def test_list_waypoints(self, client):
        resp = client.get('/api/waypoints')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_waypoint(self, client):
        resp = client.post('/api/waypoints', json={
            'name': 'Observation Post',
            'lat': 38.8977,
            'lng': -77.0365,
            'category': 'rally',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['id'] is not None
        assert data['name'] == 'Observation Post'

    def test_create_waypoint_minimal(self, client):
        resp = client.post('/api/waypoints', json={
            'name': 'Minimal WP',
            'lat': 40.0,
            'lng': -105.0,
        })
        assert resp.status_code == 201

    def test_delete_waypoint(self, client):
        create = client.post('/api/waypoints', json={
            'name': 'Temp WP Delete',
            'lat': 39.5,
            'lng': -105.5,
        })
        wid = create.get_json()['id']
        resp = client.delete(f'/api/waypoints/{wid}')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'deleted'

    def test_waypoint_categories(self, client):
        for cat in ['water', 'cache', 'shelter', 'hazard']:
            resp = client.post('/api/waypoints', json={
                'name': f'Cat {cat}',
                'lat': 39.0,
                'lng': -104.0,
                'category': cat,
            })
            assert resp.status_code == 201


class TestMapRoutes:
    def test_list_routes(self, client):
        resp = client.get('/api/maps/routes')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_route(self, client):
        wp1 = client.post('/api/waypoints', json={
            'name': 'Route Start', 'lat': 39.0, 'lng': -104.0
        }).get_json()
        wp2 = client.post('/api/waypoints', json={
            'name': 'Route End', 'lat': 39.1, 'lng': -104.1
        }).get_json()
        resp = client.post('/api/maps/routes', json={
            'name': 'Supply Route',
            'waypoint_ids': json.dumps([wp1['id'], wp2['id']]),
            'terrain_difficulty': 'moderate',
        })
        assert resp.status_code in (200, 201)
        assert resp.get_json()['id'] is not None

    def test_delete_route(self, client):
        create = client.post('/api/maps/routes', json={'name': 'Temp Route'})
        rid = create.get_json()['id']
        resp = client.delete(f'/api/maps/routes/{rid}')
        assert resp.status_code == 200


class TestElevationProfile:
    def test_elevation_profile_empty_route(self, client):
        route = client.post('/api/maps/routes', json={
            'name': 'Empty Elevation',
            'waypoint_ids': json.dumps([]),
        }).get_json()
        resp = client.get(f'/api/maps/elevation-profile/{route["id"]}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['points'] == []

    def test_elevation_profile_not_found(self, client):
        resp = client.get('/api/maps/elevation-profile/99999')
        assert resp.status_code == 404

    def test_elevation_profile_recovers_from_corrupted_waypoint_ids(self, client, db):
        route = client.post('/api/maps/routes', json={'name': 'Broken Elevation Route'}).get_json()
        db.execute('UPDATE map_routes SET waypoint_ids = ? WHERE id = ?', ('{broken', route['id']))
        db.commit()

        resp = client.get(f'/api/maps/elevation-profile/{route["id"]}')

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['points'] == []
        assert data['total_ascent'] == 0
        assert data['total_descent'] == 0


class TestWaypointDistances:
    def test_distances_endpoint(self, client):
        client.post('/api/waypoints', json={'name': 'D1', 'lat': 39.0, 'lng': -104.0})
        client.post('/api/waypoints', json={'name': 'D2', 'lat': 39.1, 'lng': -104.1})
        resp = client.get('/api/waypoints/distances')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'points' in data
        assert 'matrix' in data


class TestGeofenceResilience:
    def test_geofences_list_recovers_from_corrupted_properties(self, client, db):
        created = client.post('/api/geofences', json={'name': 'Broken Fence', 'lat': 39.2, 'lng': -104.8}).get_json()
        db.execute('UPDATE map_annotations SET properties = ? WHERE id = ?', ('{broken', created['id']))
        db.commit()

        resp = client.get('/api/geofences')

        assert resp.status_code == 200
        fence = next(item for item in resp.get_json() if item['id'] == created['id'])
        assert fence['properties'] == {}

    def test_geofences_check_recovers_from_corrupted_properties(self, client, db):
        created = client.post('/api/geofences', json={'name': 'Broken Trigger', 'lat': 39.3, 'lng': -104.7}).get_json()
        db.execute('UPDATE map_annotations SET properties = ? WHERE id = ?', ('{broken', created['id']))
        db.commit()

        resp = client.post('/api/geofences/check', json={'lat': 39.3, 'lng': -104.7})

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['checked_count'] >= 1
        assert data['triggered'][0]['properties'] == {}


class TestGpxExportResilience:
    def test_export_gpx_skips_corrupted_route_and_track_payloads(self, client, db):
        waypoint = client.post('/api/waypoints', json={
            'name': 'Export Point',
            'lat': 39.4,
            'lng': -104.6,
        }).get_json()
        route = client.post('/api/maps/routes', json={
            'name': 'Broken Export Route',
            'waypoint_ids': json.dumps([waypoint['id']]),
        }).get_json()
        track = client.post('/api/tracks', json={'name': 'Broken Export Track'}).get_json()
        db.execute('UPDATE map_routes SET waypoint_ids = ? WHERE id = ?', ('{broken', route['id']))
        db.execute('UPDATE gps_tracks SET geojson = ? WHERE id = ?', ('{broken', track['id']))
        db.commit()

        resp = client.get('/api/maps/export-gpx')

        assert resp.status_code == 200
        gpx = resp.get_data(as_text=True)
        assert '<gpx version="1.1"' in gpx
        assert '<name>Broken Export Route</name>' in gpx
        assert '<name>Broken Export Track</name>' in gpx


class TestOfflineMapBootstrapResilience:
    def test_get_pmtiles_cli_returns_none_on_malformed_release_metadata(self, monkeypatch, tmp_path):
        from web.blueprints import maps

        class _BadReleaseResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{broken'

        monkeypatch.setattr(maps, 'get_services_dir', lambda: str(tmp_path))
        monkeypatch.setattr('urllib.request.urlopen', lambda *args, **kwargs: _BadReleaseResponse())

        assert maps._get_pmtiles_cli() is None
