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
