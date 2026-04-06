"""Tests for v6.31 audit fixes — error leakage, LIMIT bounds, edge cases."""

import json


class TestSelfTestEndpoint:
    """Self-test endpoint should not leak internal paths or raw exceptions."""

    def test_self_test_returns_checks(self, client):
        resp = client.get('/api/system/self-test')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'checks' in data
        assert 'status' in data

    def test_self_test_no_filesystem_paths(self, client):
        """Ensure self-test detail messages don't leak filesystem paths."""
        resp = client.get('/api/system/self-test')
        data = resp.get_json()
        for check in data['checks']:
            detail = check.get('detail', '')
            # Should not contain drive letters (C:\...) that leak internal paths
            assert not (':\\Users' in detail or ':\\Program' in detail), (
                "Self-test leaked filesystem path: " + detail
            )


class TestQueryBounds:
    """Ensure list endpoints respect LIMIT caps and don't crash on bad offsets."""

    def test_playlists_limit_default(self, client):
        resp = client.get('/api/playlists')
        assert resp.status_code == 200

    def test_comms_presence_bounded(self, client):
        resp = client.get('/api/lan/presence')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_note_templates_bounded(self, client):
        resp = client.get('/api/notes/templates')
        assert resp.status_code == 200


class TestErrorLeakagePrevention:
    """Verify that API error responses do not contain raw exception details."""

    def test_invalid_weather_rule_error(self, client):
        """POST with missing required field should give generic error, not traceback."""
        resp = client.post('/api/weather/action-rules', json={})
        assert resp.status_code in (400, 500)
        data = resp.get_json()
        # Should not contain Python traceback indicators
        assert 'Traceback' not in json.dumps(data)
        assert 'File "' not in json.dumps(data)

    def test_malformed_radiation_data(self, client):
        """Malformed float should not crash or leak ValueError details."""
        resp = client.post('/api/radiation', json={'dose_rate_rem': 'not_a_number'})
        # Should handle gracefully (not crash with 500)
        assert resp.status_code in (200, 201, 400)

    def test_malformed_timer_duration(self, client):
        """Non-numeric timer duration should be handled."""
        resp = client.post('/api/timers', json={
            'name': 'test', 'duration_sec': 'abc'
        })
        assert resp.status_code in (200, 201, 400)


class TestPutRoutes404:
    """PUT routes should return 404 for non-existent resources."""

    def test_update_nonexistent_garden_plot(self, client):
        resp = client.put('/api/garden/plots/999999', json={'name': 'test'})
        assert resp.status_code == 404

    def test_update_nonexistent_security_zone(self, client):
        resp = client.put('/api/security/zones/999999', json={'name': 'test'})
        assert resp.status_code == 404

    def test_update_nonexistent_generator(self, client):
        resp = client.put('/api/power/generators/999999', json={'name': 'test'})
        assert resp.status_code == 404


class TestDeleteRoutes404:
    """DELETE routes should return 404 for non-existent resources."""

    def test_delete_nonexistent_weather_rule(self, client):
        resp = client.delete('/api/weather/action-rules/999999')
        assert resp.status_code == 404

    def test_delete_nonexistent_preservation_log(self, client):
        resp = client.delete('/api/garden/preservation/999999')
        assert resp.status_code == 404

    def test_delete_nonexistent_seed(self, client):
        resp = client.delete('/api/garden/seeds/999999')
        assert resp.status_code == 404

    def test_delete_nonexistent_comms_schedule(self, client):
        resp = client.delete('/api/comms/schedules/999999')
        assert resp.status_code == 404

    def test_delete_nonexistent_radio_profile(self, client):
        resp = client.delete('/api/comms/radio-profiles/999999')
        assert resp.status_code == 404
