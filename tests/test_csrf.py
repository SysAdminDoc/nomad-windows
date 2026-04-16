"""Tests for CSRF origin-check protection."""


class TestCSRFBlocking:
    def test_post_from_foreign_origin_blocked(self, client):
        resp = client.post('/api/inventory',
                          json={'name': 'CSRF Test'},
                          headers={'Origin': 'https://evil.example.com'})
        assert resp.status_code == 403

    def test_put_from_foreign_origin_blocked(self, client):
        resp = client.put('/api/inventory/1',
                          json={'name': 'CSRF Test'},
                          headers={'Origin': 'https://attacker.io'})
        assert resp.status_code == 403

    def test_delete_from_foreign_origin_blocked(self, client):
        resp = client.delete('/api/inventory/1',
                            headers={'Origin': 'https://malicious.site'})
        assert resp.status_code == 403

    def test_patch_from_foreign_origin_blocked(self, client):
        # PATCH must be treated the same as POST/PUT/DELETE. Earlier versions
        # of the app only guarded POST/PUT/DELETE, which let cross-origin
        # PATCH requests slip through on routes like /api/videos/<int:vid>.
        resp = client.patch('/api/videos/1',
                           json={'title': 'CSRF Test'},
                           headers={'Origin': 'https://evil.example.com'})
        assert resp.status_code == 403

    def test_post_from_file_origin_blocked(self, client):
        resp = client.post('/api/contacts',
                          json={'name': 'Test'},
                          headers={'Origin': 'file://'})
        assert resp.status_code == 403

    def test_post_from_localhost_different_port_blocked(self, client):
        resp = client.post(
            '/api/inventory',
            json={'name': 'CSRF Test'},
            base_url='http://127.0.0.1:8080',
            headers={'Origin': 'http://localhost:3000'},
        )
        assert resp.status_code == 403


class TestCSRFAllowed:
    def test_post_from_same_origin_allowed(self, client):
        resp = client.post(
            '/api/inventory',
            json={'name': 'Local Test'},
            base_url='http://localhost:8080',
            headers={'Origin': 'http://localhost:8080'},
        )
        assert resp.status_code != 403

    def test_post_from_loopback_alias_same_port_allowed(self, client):
        resp = client.post(
            '/api/inventory',
            json={'name': 'Loopback Test'},
            base_url='http://127.0.0.1:8080',
            headers={'Origin': 'http://localhost:8080'},
        )
        assert resp.status_code != 403

    def test_post_no_origin_allowed(self, client):
        # No Origin header (same-origin or non-browser client)
        resp = client.post('/api/inventory', json={'name': 'No Origin'})
        assert resp.status_code != 403


class TestCSRFGetNotAffected:
    def test_get_with_foreign_origin_allowed(self, client):
        resp = client.get('/api/inventory',
                         headers={'Origin': 'https://evil.example.com'})
        assert resp.status_code == 200

    def test_get_with_no_origin_allowed(self, client):
        resp = client.get('/api/inventory')
        assert resp.status_code == 200
