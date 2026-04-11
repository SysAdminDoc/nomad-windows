"""Tests for incidents API routes."""


class TestPreparednessDashboard:
    """Cross-module snapshot endpoint /api/preparedness/dashboard (v7.0.5)."""

    def test_dashboard_returns_expected_sections(self, client):
        resp = client.get('/api/preparedness/dashboard')
        assert resp.status_code == 200
        data = resp.get_json()
        # Every top-level section the frontend reads must be present,
        # even on a fresh DB where counts are zero.
        for key in ('generated_at', 'inventory', 'medical', 'power', 'garden',
                    'contacts', 'tasks', 'incidents', 'alerts', 'readiness_hint'):
            assert key in data, f'missing section: {key}'
        assert data['readiness_hint'] in ('ok', 'needs-attention')

    def test_dashboard_reflects_incident_activity(self, client):
        # Baseline
        data0 = client.get('/api/preparedness/dashboard').get_json()
        assert data0['incidents']['total'] == 0
        # Log a critical incident, verify the snapshot reflects it
        client.post('/api/incidents', json={
            'description': 'Critical test event',
            'severity': 'critical',
            'category': 'security',
        })
        data1 = client.get('/api/preparedness/dashboard').get_json()
        assert data1['incidents']['total'] >= 1
        assert data1['incidents']['open_critical'] >= 1
        assert data1['readiness_hint'] == 'needs-attention'

    def test_dashboard_survives_missing_optional_tables(self, client):
        # The endpoint wraps every section in try/except so a partial
        # schema (missing power_log, alerts, etc.) still returns 200.
        resp = client.get('/api/preparedness/dashboard')
        assert resp.status_code == 200


class TestIncidentsList:
    def test_list_incidents(self, client):
        resp = client.get('/api/incidents')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_list_with_limit(self, client):
        for i in range(5):
            client.post('/api/incidents', json={'description': f'Incident {i}', 'severity': 'info'})
        resp = client.get('/api/incidents?limit=3')
        assert resp.status_code == 200
        assert len(resp.get_json()) <= 3

    def test_list_filter_by_category(self, client):
        client.post('/api/incidents', json={'description': 'Fire spotted', 'category': 'fire'})
        client.post('/api/incidents', json={'description': 'Medical emergency', 'category': 'medical'})
        resp = client.get('/api/incidents?category=fire')
        data = resp.get_json()
        assert all(i['category'] == 'fire' for i in data)


class TestIncidentsCreate:
    def test_create_incident(self, client):
        resp = client.post('/api/incidents', json={
            'description': 'Perimeter breach at north fence',
            'severity': 'high',
            'category': 'security',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['description'] == 'Perimeter breach at north fence'
        assert data['severity'] == 'high'
        assert data['id'] is not None

    def test_create_requires_description(self, client):
        resp = client.post('/api/incidents', json={'severity': 'low'})
        assert resp.status_code == 400

    def test_create_empty_description_rejected(self, client):
        resp = client.post('/api/incidents', json={'description': '   '})
        assert resp.status_code == 400

    def test_create_defaults(self, client):
        resp = client.post('/api/incidents', json={'description': 'Minor event'})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['severity'] == 'info'
        assert data['category'] == 'other'


class TestIncidentsDelete:
    def test_delete_incident(self, client):
        create = client.post('/api/incidents', json={'description': 'Temp incident'})
        iid = create.get_json()['id']
        resp = client.delete(f'/api/incidents/{iid}')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'deleted'


class TestIncidentsClear:
    def test_clear_all(self, client):
        client.post('/api/incidents', json={'description': 'Incident 1'})
        client.post('/api/incidents', json={'description': 'Incident 2'})
        resp = client.post('/api/incidents/clear')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'cleared'
        remaining = client.get('/api/incidents').get_json()
        assert len(remaining) == 0
