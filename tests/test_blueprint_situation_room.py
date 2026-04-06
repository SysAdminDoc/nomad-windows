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
