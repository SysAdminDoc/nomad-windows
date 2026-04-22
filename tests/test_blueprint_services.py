"""Tests for services blueprint routes."""


class TestServicesList:
    def test_list_services(self, client):
        resp = client.get('/api/services')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_services_have_expected_fields(self, client):
        resp = client.get('/api/services')
        assert resp.status_code == 200
        for svc in resp.get_json():
            assert 'id' in svc
            assert 'installed' in svc
            assert 'running' in svc


class TestServicesHealth:
    def test_health_summary(self, client):
        resp = client.get('/api/services/health-summary')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_health_summary_fields(self, client):
        resp = client.get('/api/services/health-summary')
        assert resp.status_code == 200
        for svc in resp.get_json():
            assert 'id' in svc
            assert 'crashes_24h' in svc
            assert 'restarts_24h' in svc


class TestServicesPrereqs:
    def test_prereqs_unknown_service(self, client):
        resp = client.get('/api/services/nonexistent/prereqs')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['met'] is True

    def test_prereqs_stirling(self, client):
        resp = client.get('/api/services/stirling/prereqs')
        assert resp.status_code == 200
        assert 'met' in resp.get_json()


class TestServicesActions:
    def test_start_unknown_service_returns_404(self, client):
        resp = client.post('/api/services/doesnotexist/start')
        assert resp.status_code == 404

    def test_stop_unknown_service_returns_404(self, client):
        resp = client.post('/api/services/doesnotexist/stop')
        assert resp.status_code == 404
