"""Regression checks for Situation Room API resilience."""


class TestSituationRoomResilience:
    def test_space_weather_skips_corrupted_cached_rows(self, client, db):
        db.execute(
            "INSERT INTO sitroom_space_weather (data_type, value_json) VALUES (?, ?)",
            ('kp_index', '{"latest":[0,0,0,0,"5"]}'),
        )
        db.execute(
            "INSERT INTO sitroom_space_weather (data_type, value_json) VALUES (?, ?)",
            ('noaa_scales', '{broken'),
        )
        db.commit()

        resp = client.get('/api/sitroom/space-weather')

        assert resp.status_code == 200
        data = resp.get_json()
        assert 'kp_index' in data
        assert 'noaa_scales' not in data

    def test_summary_recovers_from_corrupted_space_weather_cache(self, client, db):
        db.execute(
            "INSERT INTO sitroom_space_weather (data_type, value_json) VALUES (?, ?)",
            ('noaa_scales', '{broken'),
        )
        db.commit()

        resp = client.get('/api/sitroom/summary')

        assert resp.status_code == 200
        assert resp.get_json()['space_weather'] is None

    def test_cii_geo_skips_corrupted_event_details(self, client, db):
        db.execute(
            "INSERT INTO sitroom_events (event_type, title, magnitude, detail_json) VALUES (?, ?, ?, ?)",
            ('earthquake', 'Broken Quake', 4.5, '{broken'),
        )
        db.execute(
            "INSERT INTO sitroom_events (event_type, title, magnitude, detail_json) VALUES (?, ?, ?, ?)",
            ('fire', 'France Fire', 2.0, '{"country":"France"}'),
        )
        db.commit()

        resp = client.get('/api/sitroom/cii-geo')

        assert resp.status_code == 200
        assert resp.get_json()['scores']['France'] == 100

    def test_risk_radar_recovers_from_corrupted_space_weather_payload(self, client, db):
        db.execute(
            "INSERT INTO sitroom_space_weather (data_type, value_json) VALUES (?, ?)",
            ('kp_index', '{broken'),
        )
        db.commit()

        resp = client.get('/api/sitroom/risk-radar')

        assert resp.status_code == 200
        assert resp.get_json()['domains']['space_weather']['score'] == 0

    def test_ai_briefing_recovers_from_corrupted_space_weather_payload(self, client, db, monkeypatch):
        from services import ollama as ollama_service

        db.execute(
            "INSERT INTO sitroom_space_weather (data_type, value_json) VALUES (?, ?)",
            ('noaa_scales', '{broken'),
        )
        db.commit()
        monkeypatch.setattr(
            ollama_service,
            'chat',
            lambda *args, **kwargs: {'response': 'SITUATION REPORT\nAll clear.'},
        )

        resp = client.post('/api/sitroom/ai-briefing')

        assert resp.status_code == 200
        assert 'SITUATION REPORT' in resp.get_json()['briefing']

    def test_fetch_earthquakes_ignores_malformed_remote_payload(self, db, monkeypatch):
        from web.blueprints import situation_room

        class _BadResponse:
            def json(self):
                raise ValueError('bad earthquake payload')

        monkeypatch.setattr(situation_room, '_can_fetch', lambda source_key: True)
        monkeypatch.setattr(situation_room, '_set_last_fetch', lambda source_key: None)
        monkeypatch.setattr(situation_room, '_fetch_with_retry', lambda *args, **kwargs: _BadResponse())

        situation_room._fetch_earthquakes()

        count = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'earthquake'").fetchone()[0]
        assert count == 0

    def test_fetch_market_data_ignores_malformed_remote_payloads(self, db, monkeypatch):
        from web.blueprints import situation_room

        class _BadResponse:
            ok = True

            def json(self):
                raise ValueError('bad market payload')

        monkeypatch.setattr(situation_room, '_can_fetch', lambda source_key: True)
        monkeypatch.setattr(situation_room, '_set_last_fetch', lambda source_key: None)
        monkeypatch.setattr(situation_room._http_session, 'get', lambda *args, **kwargs: _BadResponse())
        monkeypatch.setattr(situation_room, '_fetch_with_retry', lambda *args, **kwargs: _BadResponse())
        before = db.execute('SELECT COUNT(*) FROM sitroom_markets').fetchone()[0]

        situation_room._fetch_market_data()

        after = db.execute('SELECT COUNT(*) FROM sitroom_markets').fetchone()[0]
        assert after == before

    def test_fetch_space_weather_ignores_malformed_remote_payloads(self, db, monkeypatch):
        from web.blueprints import situation_room

        class _BadResponse:
            ok = True

            def json(self):
                raise ValueError('bad space weather payload')

        monkeypatch.setattr(situation_room, '_can_fetch', lambda source_key: True)
        monkeypatch.setattr(situation_room, '_set_last_fetch', lambda source_key: None)
        monkeypatch.setattr(situation_room._http_session, 'get', lambda *args, **kwargs: _BadResponse())
        before = db.execute('SELECT COUNT(*) FROM sitroom_space_weather').fetchone()[0]

        situation_room._fetch_space_weather()

        after = db.execute('SELECT COUNT(*) FROM sitroom_space_weather').fetchone()[0]
        assert after == before

    def test_fetch_predictions_ignores_malformed_remote_payload(self, db, monkeypatch):
        from web.blueprints import situation_room

        class _BadResponse:
            ok = True

            def json(self):
                raise ValueError('bad predictions payload')

        monkeypatch.setattr(situation_room, '_can_fetch', lambda source_key: True)
        monkeypatch.setattr(situation_room, '_set_last_fetch', lambda source_key: None)
        monkeypatch.setattr(situation_room._http_session, 'get', lambda *args, **kwargs: _BadResponse())
        before = db.execute('SELECT COUNT(*) FROM sitroom_predictions').fetchone()[0]

        situation_room._fetch_predictions()

        after = db.execute('SELECT COUNT(*) FROM sitroom_predictions').fetchone()[0]
        assert after == before

    def test_fetch_internet_outages_ignores_malformed_remote_payloads(self, db, monkeypatch):
        from web.blueprints import situation_room

        class _BadResponse:
            ok = True

            def json(self):
                raise ValueError('bad outage payload')

        monkeypatch.setattr(situation_room, '_can_fetch', lambda source_key: True)
        monkeypatch.setattr(situation_room, '_set_last_fetch', lambda source_key: None)
        monkeypatch.setattr(situation_room._http_session, 'get', lambda *args, **kwargs: _BadResponse())
        before = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'internet_outage'").fetchone()[0]

        situation_room._fetch_internet_outages()

        after = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'internet_outage'").fetchone()[0]
        assert after == before

    def test_fetch_gdelt_events_ignores_malformed_remote_payloads(self, db, monkeypatch):
        from web.blueprints import situation_room

        class _BadResponse:
            ok = True

            def json(self):
                raise ValueError('bad gdelt payload')

        monkeypatch.setattr(situation_room, '_can_fetch', lambda source_key: True)
        monkeypatch.setattr(situation_room, '_set_last_fetch', lambda source_key: None)
        monkeypatch.setattr(situation_room._http_session, 'get', lambda *args, **kwargs: _BadResponse())
        db.execute(
            'CREATE TABLE IF NOT EXISTS sitroom_gdelt (id INTEGER PRIMARY KEY, data_type TEXT UNIQUE, value_json TEXT, cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)'
        )
        db.commit()
        before = db.execute('SELECT COUNT(*) FROM sitroom_gdelt').fetchone()[0]

        situation_room._fetch_gdelt_events()

        after = db.execute('SELECT COUNT(*) FROM sitroom_gdelt').fetchone()[0]
        assert after == before

    def test_stock_analysis_ignores_malformed_remote_payload(self, client, db, monkeypatch):
        from web.blueprints import situation_room

        db.execute(
            'INSERT INTO sitroom_markets (symbol, price, change_24h, market_type, label) VALUES (?, ?, ?, ?, ?)',
            ('SPY', 500.0, 1.2, 'index', 'S&P ETF'),
        )
        db.commit()

        class _BadResponse:
            ok = True

            def json(self):
                raise ValueError('bad yahoo payload')

        monkeypatch.setattr(situation_room._http_session, 'get', lambda *args, **kwargs: _BadResponse())

        resp = client.get('/api/sitroom/stock-analysis/SPY')

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['symbol'] == 'SPY'
        assert data['current']['symbol'] == 'SPY'

    def test_national_debt_ignores_malformed_remote_payload(self, client, monkeypatch):
        from web.blueprints import situation_room

        class _BadResponse:
            ok = True

            def json(self):
                raise ValueError('bad debt payload')

        monkeypatch.setattr(situation_room._http_session, 'get', lambda *args, **kwargs: _BadResponse())

        resp = client.get('/api/sitroom/national-debt')

        assert resp.status_code == 200
        assert resp.get_json()['debt'] == {}


# ─── H-13 _parse_feed malformed-input resilience ─────────────────────────────

class TestParseFeedResilience:
    """_parse_feed is called from 4 different fetch workers with ``resp.text``
    payloads that come from untrusted RSS/Atom feed authors. A single raise
    inside it aborts an entire concurrent pool of fetch workers via the
    `as_completed` path. These tests pin that _parse_feed returns an empty
    list for every shape of malformed input instead of propagating.
    """

    def test_parse_feed_rejects_doctype_declaration(self):
        """Billion-laughs vector: ET.fromstring still expands internal
        entities. RSS/Atom never legitimately ships with a DOCTYPE, so the
        parser short-circuits and returns []. Memory blowup closed.
        """
        from web.blueprints.situation_room import _parse_feed

        payload = '''<?xml version="1.0"?>
<!DOCTYPE rss [<!ENTITY lol "lol">]>
<rss><channel><item><title>&lol;</title></channel></rss>'''
        assert _parse_feed(payload, 'evil', 'Test') == []

    def test_parse_feed_rejects_entity_without_doctype(self):
        """Belt-and-braces: a bare ENTITY declaration upstream of <rss> also
        goes through the guard — parser substring match is loose enough to
        catch pre-<rss> ENTITY payloads.
        """
        from web.blueprints.situation_room import _parse_feed

        payload = '<!ENTITY a "x"><rss><channel></channel></rss>'
        assert _parse_feed(payload, 'evil2', 'Test') == []

    def test_parse_feed_empty_string_returns_empty_list(self):
        """Empty input goes to ET.fromstring → ParseError → [] (caught)."""
        from web.blueprints.situation_room import _parse_feed

        assert _parse_feed('', 'empty', 'Test') == []

    def test_parse_feed_non_xml_garbage_returns_empty_list(self):
        """Random bytes / HTML / JSON masquerading as a feed must not raise.

        Real-world cause: some CDNs return an HTML "you hit a rate limit"
        page with a 200 status + text/html content-type. The worker calls
        _parse_feed on whatever came back.
        """
        from web.blueprints.situation_room import _parse_feed

        for garbage in (
            '<html><body>429 Too Many Requests</body></html>',
            '{"error": "rate limited"}',
            'Gibberish that is not XML at all',
            '<rss><channel>unclosed',  # truncated mid-stream
        ):
            assert _parse_feed(garbage, 'garbage', 'Test') == [], (
                f'_parse_feed must return [] for malformed payload: {garbage[:60]!r}'
            )

    def test_parse_feed_rss_with_missing_title_is_skipped(self):
        """RSS items without a <title> are silently dropped (title is the
        primary key in our UPSERT), not raising on `None.strip()`.
        """
        from web.blueprints.situation_room import _parse_feed

        payload = '''<rss><channel>
          <item><title>keep this</title><link>https://ex/1</link></item>
          <item><link>https://ex/2</link></item>
        </channel></rss>'''
        items = _parse_feed(payload, 'mixed', 'Test')
        assert len(items) == 1
        assert items[0]['title'] == 'keep this'
        assert items[0]['link'] == 'https://ex/1'
