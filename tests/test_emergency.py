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

    def test_enter_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/emergency/enter',
            data='not-json',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_enter_rejects_non_string_reason(self, client):
        resp = client.post('/api/emergency/enter', json={'reason': {'bad': 'shape'}})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_exit_rejects_non_object_body(self, client):
        resp = client.post('/api/emergency/exit', json=['closeout'])
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be a JSON object'


class TestEmergencyPayloadValidation:
    def test_evac_plan_rejects_wrong_type_name(self, client):
        resp = client.post('/api/emergency/evac-plans', json={'name': ['bad']})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_evac_plan_rejects_non_object_update(self, client):
        create = client.post('/api/emergency/evac-plans', json={'name': 'Go North'})
        plan_id = create.get_json()['id']

        resp = client.put(f'/api/emergency/evac-plans/{plan_id}', json=['bad'])

        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be a JSON object'

    def test_rally_point_preserves_numeric_string_coordinates(self, client):
        create = client.post('/api/emergency/evac-plans', json={'name': 'Bugout'})
        plan_id = create.get_json()['id']

        resp = client.post(f'/api/emergency/evac-plans/{plan_id}/rally-points', json={
            'name': 'North gate',
            'lat': '44.98',
            'lng': '-93.26',
        })

        assert resp.status_code == 201
        assert resp.get_json()['name'] == 'North gate'

    def test_rally_point_rejects_container_coordinates(self, client):
        create = client.post('/api/emergency/evac-plans', json={'name': 'Bugout'})
        plan_id = create.get_json()['id']

        resp = client.post(f'/api/emergency/evac-plans/{plan_id}/rally-points', json={
            'name': 'Bad gate',
            'lat': ['44.98'],
        })

        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_assignment_rejects_wrong_type_person_name(self, client):
        create = client.post('/api/emergency/evac-plans', json={'name': 'Accountability'})
        plan_id = create.get_json()['id']

        resp = client.post(f'/api/emergency/evac-plans/{plan_id}/assignments', json={
            'person_name': ['bad'],
        })

        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'
