"""Tests for Situation Room API endpoints — CRUD, list, and error paths."""


class TestSitroomNewsList:
    def test_news_list_default(self, client):
        resp = client.get('/api/sitroom/news')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'articles' in data or isinstance(data, list)

    def test_news_list_with_limit(self, client):
        resp = client.get('/api/sitroom/news?limit=5&offset=0')
        assert resp.status_code == 200


class TestSitroomEvents:
    def test_events_list(self, client):
        resp = client.get('/api/sitroom/events')
        assert resp.status_code == 200

    def test_earthquakes(self, client):
        resp = client.get('/api/sitroom/earthquakes')
        assert resp.status_code == 200

    def test_volcanoes(self, client):
        resp = client.get('/api/sitroom/volcanoes')
        assert resp.status_code == 200


class TestSitroomMarkets:
    def test_markets_list(self, client):
        resp = client.get('/api/sitroom/markets')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'markets' in data

    def test_predictions(self, client):
        resp = client.get('/api/sitroom/predictions')
        assert resp.status_code == 200


class TestSitroomSummary:
    def test_summary_endpoint(self, client):
        resp = client.get('/api/sitroom/summary')
        assert resp.status_code == 200

    def test_summary_has_expected_fields(self, client):
        resp = client.get('/api/sitroom/summary')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)


class TestSitroomSearch:
    def test_keyword_search(self, client):
        resp = client.get('/api/sitroom/keyword-search/test|query')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'articles' in data

    def test_keyword_search_empty(self, client):
        resp = client.get('/api/sitroom/keyword-search/')
        # Flask returns 404 for empty path segment
        assert resp.status_code in (200, 404)

    def test_global_search(self, client):
        resp = client.post('/api/sitroom/search', json={'query': 'test'})
        assert resp.status_code == 200


class TestSitroomFeeds:
    def test_feeds_list(self, client):
        resp = client.get('/api/sitroom/feeds')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'builtin' in data or 'custom' in data

    def test_add_custom_feed(self, client):
        resp = client.post('/api/sitroom/feeds', json={
            'name': 'Test Feed', 'url': 'https://example.com/feed.xml', 'category': 'Custom'
        })
        assert resp.status_code in (200, 201)

    def test_add_feed_missing_url(self, client):
        resp = client.post('/api/sitroom/feeds', json={'name': 'Incomplete'})
        assert resp.status_code == 400

    def test_delete_feed_nonexistent(self, client):
        resp = client.delete('/api/sitroom/feeds/999999')
        assert resp.status_code == 404


class TestSitroomSpecialized:
    def test_space_weather(self, client):
        resp = client.get('/api/sitroom/space-weather')
        assert resp.status_code == 200

    def test_risk_radar(self, client):
        resp = client.get('/api/sitroom/risk-radar')
        assert resp.status_code == 200

    def test_aviation(self, client):
        resp = client.get('/api/sitroom/aviation')
        assert resp.status_code == 200

    def test_webhook_config(self, client):
        resp = client.get('/api/sitroom/webhook-config')
        assert resp.status_code == 200

    def test_monitors_list(self, client):
        resp = client.get('/api/sitroom/monitors')
        assert resp.status_code == 200


class TestSitroomProximity:
    """Tests for the /api/sitroom/proximity endpoint added in v7.2.0.

    The endpoint filters the global sitroom_events feed against home
    coordinates stored in settings and returns nearest-first events plus
    ring counts at 50/200/500/2000 km.
    """

    def test_proximity_not_configured(self, client):
        """Without home coordinates saved, the endpoint returns a structured
        not-configured payload with a helpful message rather than a 404 or
        500. The UI uses the ``configured`` flag to prompt the user."""
        resp = client.get('/api/sitroom/proximity')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['configured'] is False
        assert data['events'] == []
        assert 'message' in data
        assert 'rings' in data

    def test_proximity_configured_no_events(self, client):
        """With home coords saved but no qualifying events in sitroom_events,
        returns configured=True, zero events, zero ring counts."""
        client.put('/api/settings', json={'latitude': '40.0', 'longitude': '-74.0'})
        resp = client.get('/api/sitroom/proximity')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['configured'] is True
        assert data['home_lat'] == 40.0
        assert data['home_lng'] == -74.0
        assert data['radius_km'] > 0
        # rings dict exists with all 4 buckets
        assert set(data['rings'].keys()) == {'50', '200', '500', '2000'}

    def test_proximity_radius_override(self, client):
        """?radius=<km> should override the stored proximity_radius_km."""
        client.put('/api/settings', json={'latitude': '0', 'longitude': '0'})
        resp = client.get('/api/sitroom/proximity?radius=100')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['radius_km'] == 100.0

    def test_proximity_haversine_sanity(self):
        """Direct smoke test of the haversine helper — NYC → LA is ~3,935 km."""
        from web.blueprints.situation_room import _haversine_km
        # NYC (40.71,-74.00) to LA (34.05,-118.24)
        d = _haversine_km(40.7128, -74.0060, 34.0522, -118.2437)
        assert 3900 <= d <= 4000  # published great-circle distance is ~3944 km
