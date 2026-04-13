"""Tests for Emergency Mode (v7.5.0).

Covers idempotency (enter-while-active, exit-while-inactive), state
persistence across status/enter/exit cycles, and the incident side-
effects that make the feature auditable.
"""


class TestEmergencyMode:
    def test_status_defaults_inactive(self, client):
        resp = client.get('/api/emergency/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['active'] is False
        assert data['started_at'] is None
        assert data['reason'] == ''

    def test_enter_then_status_shows_active(self, client):
        resp = client.post('/api/emergency/enter', json={'reason': 'Severe weather'})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['active'] is True
        assert data['reason'] == 'Severe weather'
        assert data['started_at'] is not None

        # Status endpoint now reflects it
        status = client.get('/api/emergency/status').get_json()
        assert status['active'] is True
        assert status['reason'] == 'Severe weather'
        assert status['duration_hours'] is not None
        assert status['duration_hours'] >= 0

    def test_enter_when_already_active_is_idempotent(self, client):
        client.post('/api/emergency/enter', json={'reason': 'First reason'})
        resp = client.post('/api/emergency/enter', json={'reason': 'Second reason'})
        # Doesn't 400 or 500, doesn't overwrite the existing state
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('already_active') is True
        # Original reason preserved
        assert data['reason'] == 'First reason'

    def test_exit_when_not_active_is_idempotent(self, client):
        resp = client.post('/api/emergency/exit', json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['active'] is False
        assert data.get('already_inactive') is True

    def test_enter_then_exit(self, client):
        client.post('/api/emergency/enter', json={'reason': 'Test'})
        resp = client.post('/api/emergency/exit', json={'closeout_note': 'All clear'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['active'] is False
        assert data['duration_hours'] is not None
        # Status now reports inactive
        status = client.get('/api/emergency/status').get_json()
        assert status['active'] is False

    def test_enter_creates_incident(self, client):
        client.post('/api/emergency/enter', json={'reason': 'Tornado warning'})
        # There should now be at least one critical incident
        incidents = client.get('/api/incidents').get_json()
        assert any(
            i.get('severity') == 'critical' and 'Tornado warning' in (i.get('description') or '')
            for i in incidents
        ), 'Expected a critical incident for emergency entry'

    def test_exit_creates_closeout_incident(self, client):
        client.post('/api/emergency/enter', json={'reason': 'Fire'})
        client.post('/api/emergency/exit', json={'closeout_note': 'Fire extinguished'})
        incidents = client.get('/api/incidents').get_json()
        closeouts = [
            i for i in incidents
            if 'exited' in (i.get('description') or '').lower()
        ]
        assert closeouts, 'Expected a closeout incident on exit'
        assert any('Fire extinguished' in (i.get('description') or '') for i in closeouts)

    def test_default_reason_if_blank(self, client):
        resp = client.post('/api/emergency/enter', json={})
        data = resp.get_json()
        assert data['reason'] == 'Emergency'  # default

    def test_reason_truncated_to_500(self, client):
        """Reason longer than 500 chars should be truncated, not 500 error."""
        long_reason = 'x' * 1000
        resp = client.post('/api/emergency/enter', json={'reason': long_reason})
        assert resp.status_code == 201
        assert len(resp.get_json()['reason']) == 500
