"""Tests for system-level routes: settings, i18n, system info, etc."""

import hashlib
import json


class TestSettingsEndpoint:
    def test_get_settings(self, client):
        resp = client.get('/api/settings')
        assert resp.status_code == 200

    def test_save_setting(self, client):
        resp = client.put('/api/settings', json={'theme': 'dark'})
        assert resp.status_code == 200

    def test_save_and_read_setting(self, client):
        client.put('/api/settings', json={'dashboard_mode': 'compact'})
        resp = client.get('/api/settings')
        assert resp.status_code == 200

    def test_save_and_read_workspace_memory(self, client):
        payload = {'current': {'key': 'preparedness:checklists', 'tab': 'preparedness'}, 'recent': [], 'pinned': []}
        resp = client.put('/api/settings', json={'workspace_memory': json.dumps(payload)})
        assert resp.status_code == 200
        data = client.get('/api/settings').get_json()
        assert 'workspace_memory' in data


class TestOllamaHostSettings:
    def test_get_ollama_host(self, client):
        resp = client.get('/api/settings/ollama-host')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'host' in data

    def test_set_ollama_host(self, client):
        resp = client.put('/api/settings/ollama-host', json={'host': 'http://192.168.1.100:11434'})
        assert resp.status_code == 200


class TestI18nLanguages:
    def test_list_languages(self, client):
        resp = client.get('/api/i18n/languages')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'languages' in data
        assert 'en' in data['languages']

    def test_get_translations(self, client):
        resp = client.get('/api/i18n/translations/en')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'translations' in data
        assert data['language'] == 'en'

    def test_translations_not_found(self, client):
        resp = client.get('/api/i18n/translations/zz')
        assert resp.status_code == 404

    def test_get_current_language(self, client):
        resp = client.get('/api/i18n/language')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'language' in data

    def test_set_language(self, client):
        resp = client.post('/api/i18n/language', json={'language': 'es'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['language'] == 'es'

    def test_set_invalid_language(self, client):
        resp = client.post('/api/i18n/language', json={'language': 'zz'})
        assert resp.status_code == 400

    def test_set_language_rejects_malformed_json(self, client):
        resp = client.post('/api/i18n/language', data='{bad', content_type='application/json')
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['error'] == 'Request body must be valid JSON'

    def test_dashboard_widgets_rejects_malformed_json(self, client):
        resp = client.post('/api/dashboard/widgets', data='{bad', content_type='application/json')
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['error'] == 'Request body must be valid JSON'


class TestSystemInfo:
    def test_system_self_test(self, client):
        resp = client.get('/api/system/self-test')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'checks' in data or isinstance(data, dict)

    def test_system_db_check(self, client):
        resp = client.post('/api/system/db-check')
        assert resp.status_code == 200

    def test_system_db_vacuum(self, client):
        resp = client.post('/api/system/db-vacuum')
        assert resp.status_code == 200


class TestVersionEndpoint:
    def test_version(self, client):
        resp = client.get('/api/version')
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'version' in data

    def test_update_check_recovers_from_malformed_release_json(self, client, monkeypatch):
        class _BadResponse:
            ok = True

            def json(self):
                raise ValueError('bad github payload')

        monkeypatch.setattr('requests.get', lambda *args, **kwargs: _BadResponse())

        resp = client.get('/api/update-check')

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['update_available'] is False
        assert data['latest'] == data['current']


class TestStatusReport:
    def test_status_report(self, client):
        resp = client.get('/api/status-report')
        assert resp.status_code == 200

    def test_status_report_recovers_from_corrupted_situation_json(self, client, db):
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('sit_board', ?)", ('{broken',))
        db.commit()

        resp = client.get('/api/status-report')

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['situation'] == {}


class TestDashboardAndBackupConfigFallbacks:
    def test_dashboard_widgets_fall_back_when_setting_is_corrupted(self, client, db):
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('dashboard_widgets', ?)", ('not-json',))
        db.commit()

        resp = client.get('/api/dashboard/widgets')

        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data['widgets'], list)
        assert len(data['widgets']) == 10
        assert any(widget['id'] == 'weather' for widget in data['widgets'])

    def test_backup_config_falls_back_when_setting_is_corrupted(self, client, db):
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('auto_backup_config', ?)", ('{oops',))
        db.commit()

        resp = client.get('/api/system/backup/config')

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['enabled'] is False
        assert data['interval'] == 'daily'
        assert data['keep_count'] == 7
        assert data['encrypt'] is False
        assert data['has_password'] is False

    def test_dashboard_live_recovers_from_corrupted_situation_json(self, client, db):
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('sit_board', ?)", ('not valid json',))
        db.commit()

        resp = client.get('/api/dashboard/live')

        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)
        assert data['situation'] == {}

    def test_readiness_score_recovers_from_corrupted_checklist_json(self, client, db):
        db.execute('INSERT INTO checklists (name, items) VALUES (?, ?)', ('Broken Readiness Checklist', '{broken'))
        db.commit()

        resp = client.get('/api/readiness-score')

        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)
        assert data['categories']['planning']['score'] >= 0
        assert 'checklists' in data['categories']['planning']['detail']


class TestSimpleLanAuth:
    def test_set_password_stores_pbkdf2_hash(self, client, db):
        resp = client.post('/api/auth/set-password', json={'password': 'field-pass'})

        assert resp.status_code == 200
        row = db.execute("SELECT value FROM settings WHERE key = 'auth_password'").fetchone()
        assert row is not None
        assert row['value'].startswith('pbkdf2$')
        assert row['value'] != hashlib.sha256(b'field-pass').hexdigest()

    def test_auth_check_accepts_valid_remote_token(self, client):
        client.post('/api/auth/set-password', json={'password': 'field-pass'})

        resp = client.get(
            '/api/auth/check',
            headers={'X-Auth-Token': 'field-pass'},
            environ_overrides={'REMOTE_ADDR': '192.168.1.22'},
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['enabled'] is True
        assert data['authenticated'] is True

    def test_remote_mutation_requires_valid_auth_token(self, client):
        client.post('/api/auth/set-password', json={'password': 'field-pass'})
        remote_addr = '192.168.1.25'
        base_url = f'http://{remote_addr}:8080'
        csrf = client.get(
            '/api/csrf-token',
            base_url=base_url,
            environ_overrides={'REMOTE_ADDR': remote_addr},
        ).get_json()['csrf_token']

        denied = client.post(
            '/api/inventory',
            json={'name': 'Denied Remote'},
            base_url=base_url,
            headers={'Origin': base_url, 'X-CSRF-Token': csrf},
            environ_overrides={'REMOTE_ADDR': remote_addr},
        )
        allowed = client.post(
            '/api/inventory',
            json={'name': 'Allowed Remote'},
            base_url=base_url,
            headers={'Origin': base_url, 'X-CSRF-Token': csrf, 'X-Auth-Token': 'field-pass'},
            environ_overrides={'REMOTE_ADDR': remote_addr},
        )

        assert denied.status_code == 403
        assert denied.get_json()['error'] == 'Authentication required'
        assert allowed.status_code == 201

    def test_remote_mutation_accepts_legacy_hash_and_upgrades_it(self, client, db):
        legacy = hashlib.sha256(b'legacy-pass').hexdigest()
        db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('auth_password', ?)",
            (legacy,),
        )
        db.commit()
        remote_addr = '192.168.1.30'
        base_url = f'http://{remote_addr}:8080'
        csrf = client.get(
            '/api/csrf-token',
            base_url=base_url,
            environ_overrides={'REMOTE_ADDR': remote_addr},
        ).get_json()['csrf_token']

        resp = client.post(
            '/api/inventory',
            json={'name': 'Legacy Remote'},
            base_url=base_url,
            headers={'Origin': base_url, 'X-CSRF-Token': csrf, 'X-Auth-Token': 'legacy-pass'},
            environ_overrides={'REMOTE_ADDR': remote_addr},
        )

        assert resp.status_code == 201
        upgraded = db.execute("SELECT value FROM settings WHERE key = 'auth_password'").fetchone()['value']
        assert upgraded.startswith('pbkdf2$')
        assert upgraded != legacy


class TestPowerActions:
    def test_system_shutdown_rejects_invalid_action(self, client):
        resp = client.post('/api/system/shutdown', json={'action': 'explode'})

        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'action must be shutdown or reboot'

    def test_system_shutdown_rejects_malformed_json(self, client):
        resp = client.post('/api/system/shutdown', data='{bad', content_type='application/json')

        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'
