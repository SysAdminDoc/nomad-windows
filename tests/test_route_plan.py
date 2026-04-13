"""Tests for the Route Plan endpoint (v7.4.0).

Covers the happy path, error paths, pace scaling, and corridor search.
"""


def _create_route_with_waypoints(client, coords, name='Test Route'):
    """Create waypoints, then a route that references them in order.
    Returns (route_id, waypoint_ids)."""
    wp_ids = []
    for i, (lat, lng) in enumerate(coords):
        resp = client.post('/api/waypoints', json={
            'name': f'WP-{i}', 'lat': lat, 'lng': lng,
            'category': 'other', 'elevation_m': 100 + i * 10,
        })
        wp_ids.append(resp.get_json()['id'])
    import json
    resp = client.post('/api/maps/routes', json={
        'name': name,
        'waypoint_ids': json.dumps(wp_ids),
    })
    return resp.get_json()['id'], wp_ids


class TestRoutePlan:
    def test_missing_route_id(self, client):
        resp = client.post('/api/maps/route-plan', json={})
        assert resp.status_code == 400

    def test_unknown_route(self, client):
        resp = client.post('/api/maps/route-plan', json={'route_id': 99999})
        assert resp.status_code == 404

    def test_single_waypoint_rejected(self, client):
        """A route with fewer than 2 waypoints can't be planned."""
        rid, _ = _create_route_with_waypoints(client, [(40.0, -74.0)])
        resp = client.post('/api/maps/route-plan', json={'route_id': rid})
        assert resp.status_code == 400

    def test_happy_path(self, client):
        # NYC → Philadelphia approx 130 km
        rid, _ = _create_route_with_waypoints(client, [
            (40.7128, -74.0060),
            (39.9526, -75.1652),
        ])
        resp = client.post('/api/maps/route-plan', json={
            'route_id': rid, 'pace_kmh': 60, 'people': 2,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['route_id'] == rid
        assert len(data['milestones']) == 2
        assert data['totals']['distance_km'] > 100
        assert data['totals']['distance_km'] < 200
        # 2 people → 2× water
        assert data['totals']['water_l_total'] > 0
        # Sun data present
        assert len(data['sun']) >= 1

    def test_pace_affects_duration(self, client):
        rid, _ = _create_route_with_waypoints(client, [
            (40.0, -74.0), (41.0, -74.0),  # ~111 km north
        ])
        slow = client.post('/api/maps/route-plan', json={
            'route_id': rid, 'pace_kmh': 5,
        }).get_json()
        fast = client.post('/api/maps/route-plan', json={
            'route_id': rid, 'pace_kmh': 50,
        }).get_json()
        # Slower pace → longer duration
        assert slow['totals']['duration_hours'] > fast['totals']['duration_hours']

    def test_corridor_surfaces_nearby_waypoints(self, client):
        rid, _ = _create_route_with_waypoints(client, [
            (40.0, -74.0), (41.0, -74.0),
        ])
        # Create an off-route waypoint close to the start waypoint.
        # The corridor search measures from route waypoints (not segment
        # midpoints) so the candidate should be within the corridor of at
        # least one waypoint.
        client.post('/api/waypoints', json={
            'name': 'Resupply Alpha', 'lat': 40.05, 'lng': -74.05,
            'category': 'supply',
        })
        resp = client.post('/api/maps/route-plan', json={
            'route_id': rid, 'corridor_km': 20,
        })
        data = resp.get_json()
        names = [n['name'] for n in data.get('nearby_waypoints', [])]
        assert 'Resupply Alpha' in names

    def test_pace_clamped(self, client):
        rid, _ = _create_route_with_waypoints(client, [
            (40.0, -74.0), (40.1, -74.0),
        ])
        # Zero pace → clamped to 0.5 km/h minimum (not div/0)
        resp = client.post('/api/maps/route-plan', json={
            'route_id': rid, 'pace_kmh': 0,
        })
        assert resp.status_code == 200
        assert resp.get_json()['params']['pace_kmh'] >= 0.5
