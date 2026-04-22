"""Tests for security blueprint routes (cameras, access-log, zones, dashboard)."""


class TestSecurityCameras:
    def test_list_cameras(self, client):
        resp = client.get('/api/security/cameras')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_camera(self, client):
        resp = client.post('/api/security/cameras', json={
            'name': 'Front Gate', 'url': 'http://192.168.1.10/stream'
        })
        assert resp.status_code == 201

    def test_create_camera_requires_name_and_url(self, client):
        resp = client.post('/api/security/cameras', json={'name': 'No URL'})
        assert resp.status_code == 400

    def test_delete_camera(self, client):
        client.post('/api/security/cameras', json={
            'name': 'Temp Cam', 'url': 'http://192.168.1.99/stream'
        })
        cams = client.get('/api/security/cameras').get_json()
        cid = next(c['id'] for c in cams if c['name'] == 'Temp Cam')
        resp = client.delete(f'/api/security/cameras/{cid}')
        assert resp.status_code == 200


class TestSecurityAccessLog:
    def test_list_access_log(self, client):
        resp = client.get('/api/security/access-log')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_access_entry(self, client):
        resp = client.post('/api/security/access-log', json={
            'person': 'Alpha Team', 'direction': 'entry', 'location': 'Main Gate'
        })
        assert resp.status_code == 201


class TestSecurityDashboard:
    def test_dashboard_returns_summary(self, client):
        resp = client.get('/api/security/dashboard')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'cameras_active' in data
        assert 'access_24h' in data
        assert 'security_level' in data


class TestSecurityZones:
    def test_list_zones(self, client):
        resp = client.get('/api/security/zones')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)
