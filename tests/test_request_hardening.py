"""Regression tests for request hardening and bounded query handling."""


def test_coerce_int_uses_safe_bounds():
    from web.utils import coerce_int

    assert coerce_int('-1', 50, minimum=1, maximum=500) == 50
    assert coerce_int('900', 50, minimum=1, maximum=500) == 500
    assert coerce_int('nope', 50, minimum=1, maximum=500) == 50


def test_activity_negative_limit_falls_back_to_default(client, db):
    db.execute('DELETE FROM activity_log')
    for idx in range(80):
        db.execute(
            'INSERT INTO activity_log (event, service, detail, level) VALUES (?, ?, ?, ?)',
            (f'event-{idx}', 'tests', f'detail-{idx}', 'info'),
        )
    db.commit()

    resp = client.get('/api/activity?limit=-1')

    assert resp.status_code == 200
    assert len(resp.get_json()) == 50


def test_service_logs_negative_tail_falls_back_to_default(client, monkeypatch):
    import services.manager as manager

    monkeypatch.setattr(
        manager,
        '_service_logs',
        {'demo': [f'line {idx}' for idx in range(150)]},
        raising=False,
    )

    resp = client.get('/api/services/demo/logs?tail=-1')
    data = resp.get_json()

    assert resp.status_code == 200
    assert len(data['lines']) == 100
    assert data['lines'][0] == 'line 50'


def test_network_dashboard_url_respects_bind_host_and_port(client, monkeypatch):
    import config

    class _FakeConn:
        def close(self):
            return None

    class _FakeSocket:
        def connect(self, _addr):
            return None

        def getsockname(self):
            return ('192.168.50.10', 54321)

        def close(self):
            return None

    monkeypatch.setattr('socket.create_connection', lambda *args, **kwargs: _FakeConn())
    monkeypatch.setattr('socket.socket', lambda *args, **kwargs: _FakeSocket())
    monkeypatch.setattr(config.Config, 'APP_HOST', '127.0.0.1', raising=False)
    monkeypatch.setattr(config.Config, 'APP_PORT', 9090, raising=False)

    resp = client.get('/api/network')

    assert resp.status_code == 200
    assert resp.get_json()['dashboard_url'] == 'http://127.0.0.1:9090'


def test_network_dashboard_url_uses_lan_ip_when_bound_externally(client, monkeypatch):
    import config

    class _FakeConn:
        def close(self):
            return None

    class _FakeSocket:
        def connect(self, _addr):
            return None

        def getsockname(self):
            return ('192.168.50.10', 54321)

        def close(self):
            return None

    monkeypatch.setattr('socket.create_connection', lambda *args, **kwargs: _FakeConn())
    monkeypatch.setattr('socket.socket', lambda *args, **kwargs: _FakeSocket())
    monkeypatch.setattr(config.Config, 'APP_HOST', '0.0.0.0', raising=False)
    monkeypatch.setattr(config.Config, 'APP_PORT', 9090, raising=False)

    resp = client.get('/api/network')

    assert resp.status_code == 200
    assert resp.get_json()['dashboard_url'] == 'http://192.168.50.10:9090'


def test_auth_required_blocks_remote_api_reads_without_session(client, monkeypatch):
    monkeypatch.setenv('NOMAD_AUTH_REQUIRED', '1')

    resp = client.get(
        '/api/offline/snapshot',
        environ_overrides={'REMOTE_ADDR': '192.168.1.50'},
    )

    assert resp.status_code == 401
    assert resp.get_json()['error'] == 'Authentication required'


def test_auth_required_keeps_bootstrap_and_health_public(client, monkeypatch):
    monkeypatch.setenv('NOMAD_AUTH_REQUIRED', '1')
    remote = {'REMOTE_ADDR': '192.168.1.51'}

    csrf = client.get('/api/csrf-token', environ_overrides=remote)
    health = client.get('/api/health', environ_overrides=remote)

    assert csrf.status_code == 200
    assert 'csrf_token' in csrf.get_json()
    assert health.status_code == 200
    assert health.get_json()['status'] == 'ok'


def test_auth_required_allows_remote_api_reads_with_session(client, db, monkeypatch):
    monkeypatch.setenv('NOMAD_AUTH_REQUIRED', '1')
    db.execute(
        """INSERT INTO app_users (username, display_name, role, is_active)
           VALUES (?, ?, ?, 1)""",
        ('field-admin', 'Field Admin', 'admin'),
    )
    user_id = db.execute('SELECT id FROM app_users WHERE username = ?', ('field-admin',)).fetchone()['id']
    db.execute(
        """INSERT INTO app_sessions
           (user_id, session_token, expires_at, is_active, last_activity)
           VALUES (?, ?, ?, 1, ?)""",
        (user_id, 'review-token', '2999-01-01T00:00:00Z', '2026-04-24T00:00:00Z'),
    )
    db.commit()

    resp = client.get(
        '/api/offline/snapshot',
        headers={'Authorization': 'Bearer review-token'},
        environ_overrides={'REMOTE_ADDR': '192.168.1.52'},
    )

    assert resp.status_code == 200
    assert 'contacts' in resp.get_json()
