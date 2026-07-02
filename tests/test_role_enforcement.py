"""Tests for workspace role policy enforcement across domains.

Verifies that when NOMAD_AUTH_REQUIRED=1 is set, mutation routes in
Medical, Services, KB, System, Financial, and Inventory require proper
authentication and role level.
Localhost requests are always exempt (desktop mode).
"""

from unittest.mock import patch

from db import db_session


def _make_user(db, username, role='user'):
    """Create a test user and session, return the bearer token."""
    import hashlib
    import secrets
    from datetime import datetime, timezone, timedelta
    token = secrets.token_hex(32)
    expires = (datetime.now(timezone.utc) + timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%SZ')
    db.execute(
        'INSERT OR IGNORE INTO app_users (username, password_hash, role) VALUES (?, ?, ?)',
        (username, 'pbkdf2$600000$salt$' + hashlib.sha256(b'test').hexdigest(), role)
    )
    db.commit()
    user = db.execute('SELECT id FROM app_users WHERE username = ?', (username,)).fetchone()
    db.execute(
        'INSERT INTO app_sessions (user_id, session_token, expires_at, is_active) VALUES (?, ?, ?, 1)',
        (user['id'], token, expires)
    )
    db.commit()
    return token


def _non_localhost():
    """Patch target: makes the auth decorator think we're on LAN, not localhost."""
    return False


class TestMedicalRoleEnforcement:
    def test_patient_create_allowed_for_localhost(self, client):
        resp = client.post('/api/patients', json={'name': 'Test Patient'})
        assert resp.status_code in (200, 201)

    @patch('web.auth._is_localhost', _non_localhost)
    def test_patient_create_requires_auth_when_enforced(self, client, monkeypatch):
        monkeypatch.setenv('NOMAD_AUTH_REQUIRED', '1')
        resp = client.post('/api/patients', json={'name': 'Test'})
        assert resp.status_code == 401


class TestServicesRoleEnforcement:
    def test_service_start_allowed_for_localhost(self, client):
        resp = client.post('/api/services/ollama/start')
        assert resp.status_code != 401

    @patch('web.auth._is_localhost', _non_localhost)
    def test_service_start_requires_admin_when_enforced(self, client, monkeypatch):
        monkeypatch.setenv('NOMAD_AUTH_REQUIRED', '1')
        with db_session() as db:
            token = _make_user(db, 'viewer_svc', role='viewer')
        resp = client.post('/api/services/ollama/start',
                           headers={'Authorization': f'Bearer {token}'})
        assert resp.status_code == 403

    @patch('web.auth._is_localhost', _non_localhost)
    def test_service_start_passes_for_admin(self, client, monkeypatch):
        monkeypatch.setenv('NOMAD_AUTH_REQUIRED', '1')
        with db_session() as db:
            token = _make_user(db, 'admin_svc', role='admin')
        resp = client.post('/api/services/ollama/start',
                           headers={'Authorization': f'Bearer {token}'})
        assert resp.status_code != 401
        assert resp.status_code != 403


class TestKBRoleEnforcement:
    @patch('web.auth._is_localhost', _non_localhost)
    def test_kb_purge_requires_admin_when_enforced(self, client, monkeypatch):
        monkeypatch.setenv('NOMAD_AUTH_REQUIRED', '1')
        with db_session() as db:
            token = _make_user(db, 'regular_kb', role='user')
        resp = client.post('/api/kb/purge', json={'all': True},
                           headers={'Authorization': f'Bearer {token}'})
        assert resp.status_code == 403

    @patch('web.auth._is_localhost', _non_localhost)
    def test_kb_purge_unauthenticated_gets_401(self, client, monkeypatch):
        monkeypatch.setenv('NOMAD_AUTH_REQUIRED', '1')
        resp = client.post('/api/kb/purge', json={'all': True})
        assert resp.status_code == 401

    def test_kb_estimate_needs_no_auth(self, client, monkeypatch):
        monkeypatch.setenv('NOMAD_AUTH_REQUIRED', '1')
        resp = client.post('/api/kb/estimate', json={'file_size': 5000})
        assert resp.status_code == 200


class TestSystemRoleEnforcement:
    @patch('web.auth._is_localhost', _non_localhost)
    def test_settings_update_requires_auth(self, client, monkeypatch):
        monkeypatch.setenv('NOMAD_AUTH_REQUIRED', '1')
        resp = client.put('/api/settings', json={'theme': 'nightops'})
        assert resp.status_code == 401

    @patch('web.auth._is_localhost', _non_localhost)
    def test_backup_create_requires_admin(self, client, monkeypatch):
        monkeypatch.setenv('NOMAD_AUTH_REQUIRED', '1')
        with db_session() as db:
            token = _make_user(db, 'viewer_sys', role='viewer')
        resp = client.post('/api/backup',
                           headers={'Authorization': f'Bearer {token}'})
        assert resp.status_code == 403

    @patch('web.auth._is_localhost', _non_localhost)
    def test_backup_create_passes_for_admin(self, client, monkeypatch):
        monkeypatch.setenv('NOMAD_AUTH_REQUIRED', '1')
        with db_session() as db:
            token = _make_user(db, 'admin_sys', role='admin')
        resp = client.post('/api/backup',
                           headers={'Authorization': f'Bearer {token}'})
        assert resp.status_code != 401
        assert resp.status_code != 403

    @patch('web.auth._is_localhost', _non_localhost)
    def test_db_check_requires_admin(self, client, monkeypatch):
        monkeypatch.setenv('NOMAD_AUTH_REQUIRED', '1')
        with db_session() as db:
            token = _make_user(db, 'user_sys', role='user')
        resp = client.post('/api/system/db-check',
                           headers={'Authorization': f'Bearer {token}'})
        assert resp.status_code == 403

    @patch('web.auth._is_localhost', _non_localhost)
    def test_startup_set_requires_admin(self, client, monkeypatch):
        monkeypatch.setenv('NOMAD_AUTH_REQUIRED', '1')
        with db_session() as db:
            token = _make_user(db, 'user_startup', role='user')
        resp = client.put('/api/startup', json={'enabled': False},
                          headers={'Authorization': f'Bearer {token}'})
        assert resp.status_code == 403

    @patch('web.auth._is_localhost', _non_localhost)
    def test_ollama_host_requires_admin(self, client, monkeypatch):
        monkeypatch.setenv('NOMAD_AUTH_REQUIRED', '1')
        with db_session() as db:
            token = _make_user(db, 'user_ollama', role='user')
        resp = client.put('/api/settings/ollama-host', json={'host': 'http://bad'},
                          headers={'Authorization': f'Bearer {token}'})
        assert resp.status_code == 403

    @patch('web.auth._is_localhost', _non_localhost)
    def test_guidance_sources_requires_admin(self, client, monkeypatch):
        monkeypatch.setenv('NOMAD_AUTH_REQUIRED', '1')
        with db_session() as db:
            token = _make_user(db, 'user_guide', role='user')
        resp = client.post('/api/guidance-sources',
                           json={'domain': 'test', 'content_key': 'k'},
                           headers={'Authorization': f'Bearer {token}'})
        assert resp.status_code == 403

    def test_wizard_works_without_auth(self, client, monkeypatch):
        """Wizard routes must work pre-auth for first-run setup."""
        monkeypatch.setenv('NOMAD_AUTH_REQUIRED', '1')
        resp = client.post('/api/settings/wizard-complete', json={})
        assert resp.status_code != 401

    @patch('web.auth._is_localhost', _non_localhost)
    def test_dashboard_widgets_requires_user(self, client, monkeypatch):
        monkeypatch.setenv('NOMAD_AUTH_REQUIRED', '1')
        resp = client.post('/api/dashboard/widgets', json={'widgets': []})
        assert resp.status_code == 401

    @patch('web.auth._is_localhost', _non_localhost)
    def test_dashboard_widgets_viewer_denied(self, client, monkeypatch):
        monkeypatch.setenv('NOMAD_AUTH_REQUIRED', '1')
        with db_session() as db:
            token = _make_user(db, 'viewer_widget', role='viewer')
        resp = client.post('/api/dashboard/widgets', json={'widgets': []},
                           headers={'Authorization': f'Bearer {token}'})
        assert resp.status_code == 403


class TestFinancialRoleEnforcement:
    @patch('web.auth._is_localhost', _non_localhost)
    def test_cash_create_requires_admin(self, client, monkeypatch):
        monkeypatch.setenv('NOMAD_AUTH_REQUIRED', '1')
        with db_session() as db:
            token = _make_user(db, 'user_fin', role='user')
        resp = client.post('/api/financial/cash',
                           json={'amount': 100, 'currency': 'USD', 'location': 'safe'},
                           headers={'Authorization': f'Bearer {token}'})
        assert resp.status_code == 403

    @patch('web.auth._is_localhost', _non_localhost)
    def test_cash_delete_unauthenticated(self, client, monkeypatch):
        monkeypatch.setenv('NOMAD_AUTH_REQUIRED', '1')
        resp = client.delete('/api/financial/cash/1')
        assert resp.status_code == 401


class TestInventoryRoleEnforcement:
    @patch('web.auth._is_localhost', _non_localhost)
    def test_inventory_create_requires_admin(self, client, monkeypatch):
        monkeypatch.setenv('NOMAD_AUTH_REQUIRED', '1')
        with db_session() as db:
            token = _make_user(db, 'user_inv', role='user')
        resp = client.post('/api/inventory',
                           json={'name': 'Test', 'quantity': 1, 'category': 'food'},
                           headers={'Authorization': f'Bearer {token}'})
        assert resp.status_code == 403
