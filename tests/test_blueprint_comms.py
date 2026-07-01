"""Tests for comms/radio blueprint routes."""

from db import db_session


class TestFrequenciesCRUD:
    def test_list_frequencies(self, client):
        resp = client.get('/api/comms/frequencies')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        # Should auto-seed with 100+ entries
        assert len(data) > 50

    def test_frequency_fields(self, client):
        freqs = client.get('/api/comms/frequencies').get_json()
        f = freqs[0]
        assert 'frequency' in f
        assert 'service' in f
        assert 'mode' in f

    def test_create_frequency(self, client):
        resp = client.post('/api/comms/frequencies', json={
            'frequency': 146.520,
            'mode': 'FM',
            'bandwidth': '25',
            'service': '2m National Simplex',
            'description': 'Ham radio calling frequency',
            'region': 'US',
            'license_required': 1,
            'priority': 3,
            'notes': 'VHF simplex',
        })
        assert resp.status_code in (200, 201)

    def test_create_frequency_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/comms/frequencies',
            data='not-json',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_create_frequency_rejects_container_frequency(self, client):
        resp = client.post('/api/comms/frequencies', json={'frequency': ['146.520']})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_delete_frequency(self, client):
        client.post('/api/comms/frequencies', json={
            'frequency': 888.888,
            'service': 'Temp Freq',
            'mode': 'FM',
            'bandwidth': '12.5',
            'description': 'Temp',
            'region': 'US',
            'license_required': 0,
            'priority': 1,
            'notes': '',
        })
        freqs = client.get('/api/comms/frequencies').get_json()
        temp = next((f for f in freqs if f['frequency'] == 888.888), None)
        assert temp is not None
        resp = client.delete(f'/api/comms/frequencies/{temp["id"]}')
        assert resp.status_code == 200


class TestRadioProfiles:
    def test_list_profiles(self, client):
        resp = client.get('/api/comms/radio-profiles')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_profile(self, client):
        resp = client.post('/api/comms/radio-profiles', json={
            'name': 'Patrol Team Bravo',
            'frequencies': '462.5625,462.5875,462.6125',
            'notes': 'FRS channels for patrol',
        })
        assert resp.status_code in (200, 201)

    def test_delete_profile(self, client):
        client.post('/api/comms/radio-profiles', json={'name': 'Delete Profile'})
        profiles = client.get('/api/comms/radio-profiles').get_json()
        target = next((p for p in profiles if p['name'] == 'Delete Profile'), None)
        assert target is not None
        resp = client.delete(f'/api/comms/radio-profiles/{target["id"]}')
        assert resp.status_code == 200

    def test_create_profile_minimal(self, client):
        resp = client.post('/api/comms/radio-profiles', json={'name': 'Minimal'})
        assert resp.status_code in (200, 201)

    def test_create_profile_rejects_non_list_channels(self, client):
        resp = client.post('/api/comms/radio-profiles', json={
            'name': 'Bad Channels',
            'channels': '462.5625,462.5875',
        })
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_list_profiles_recovers_from_corrupted_channels(self, client):
        with db_session() as db:
            db.execute(
                'INSERT INTO radio_profiles (radio_model, name, channels) VALUES (?, ?, ?)',
                ('Baofeng', 'Broken Channels', '{broken'),
            )
            db.commit()

        resp = client.get('/api/comms/radio-profiles')
        assert resp.status_code == 200
        data = resp.get_json()
        target = next((p for p in data if p['name'] == 'Broken Channels'), None)
        assert target is not None
        assert target['channels'] == []

    def test_status_board_recovers_from_corrupted_radio_profile_channels(self, client):
        with db_session() as db:
            db.execute(
                'INSERT INTO radio_profiles (radio_model, name, channels) VALUES (?, ?, ?)',
                ('Yaesu', 'Status Board Broken', '{broken'),
            )
            db.commit()

        resp = client.get('/api/comms/status-board')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data['active_frequencies'], list)


class TestPropagation:
    def test_propagation_prediction(self, client):
        resp = client.get('/api/radio/propagation')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)


class TestMeshTransportStatus:
    def test_mesh_status_reports_installable_transport(self, client, monkeypatch):
        from services import reticulum as rns_svc

        monkeypatch.setattr(rns_svc, 'get_status', lambda: {
            'state': 'installable',
            'available': False,
            'installable': True,
            'running': False,
            'ready': False,
            'identity': None,
            'peer_count': 0,
            'known_destinations': 0,
            'active_interfaces': 0,
            'interfaces': [],
            'install_hint': 'pip install rns lxmf',
        })

        resp = client.get('/api/mesh/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['state'] == 'installable'
        assert data['installable'] is True
        assert data['install_hint'] == 'pip install rns lxmf'
        assert data['connected'] is False
        assert data['my_node_id'] == '!local'

    def test_mesh_status_reports_running_identity_and_counts(self, client, monkeypatch):
        from services import reticulum as rns_svc

        monkeypatch.setattr(rns_svc, 'get_status', lambda: {
            'state': 'running',
            'available': True,
            'installable': False,
            'running': True,
            'ready': True,
            'identity': 'abcdef123456',
            'peer_count': 3,
            'known_destinations': 3,
            'active_interfaces': 2,
            'interfaces': [
                {'name': 'AutoInterface', 'online': True, 'type': 'AutoInterface'},
                {'name': 'TCPInterface', 'online': True, 'type': 'TCPInterface'},
            ],
        })

        resp = client.get('/api/mesh/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['state'] == 'running'
        assert data['connected'] is True
        assert data['my_node_id'] == 'abcdef123456'
        assert data['peer_count'] == 3
        assert data['node_count'] == 3
        assert data['active_interfaces'] == 2
        assert len(data['interfaces']) == 2

    def test_mesh_start_unavailable_returns_install_guidance(self, client, monkeypatch):
        from services import reticulum as rns_svc

        monkeypatch.setattr(rns_svc, 'available', lambda: False)
        monkeypatch.setattr(rns_svc, 'get_status', lambda: {
            'state': 'installable',
            'available': False,
            'installable': True,
            'running': False,
            'ready': False,
            'install_hint': 'pip install rns lxmf',
            'error': 'RNS not installed. Install with: pip install rns lxmf',
        })

        resp = client.post('/api/mesh/start', json={})
        assert resp.status_code == 503
        data = resp.get_json()
        assert data['state'] == 'installable'
        assert data['install_hint'] == 'pip install rns lxmf'

    def test_reticulum_status_degrades_without_online_interfaces(self, monkeypatch):
        from services import reticulum as rns_svc

        class FakeIdentity:
            hexhash = 'abcdef123456'

        class FakeTransport:
            destinations_table = {'peer': object()}

        class FakeRns:
            Transport = FakeTransport

        class FakeReticulum:
            def is_transport_instance(self):
                return False

            def get_interfaces(self):
                return []

        monkeypatch.setattr(rns_svc, 'available', lambda: True)
        monkeypatch.setattr(rns_svc, '_rns', FakeRns)
        monkeypatch.setattr(rns_svc, '_identity', FakeIdentity())
        monkeypatch.setattr(rns_svc, '_reticulum', FakeReticulum())

        data = rns_svc.get_status()
        assert data['state'] == 'degraded'
        assert data['running'] is True
        assert data['ready'] is False
        assert data['connected'] is False
        assert data['peer_count'] == 1
        assert 'No active Reticulum interfaces are online' in data['issues']


class TestPrintFreqCard:
    def test_freq_card_print(self, client):
        resp = client.get('/api/print/freq-card')
        assert resp.status_code == 200


class TestCommsPayloadValidation:
    def test_lan_message_rejects_non_string_content(self, client):
        resp = client.post('/api/lan/messages', json={'content': {'bad': 'shape'}})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_lan_channel_rejects_non_object_body(self, client):
        resp = client.post('/api/lan/channels', json=['General'])
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be a JSON object'

    def test_schedule_rejects_container_priority(self, client):
        resp = client.post('/api/comms/schedules', json={
            'frequency': '146.520',
            'priority': ['high'],
        })
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_comms_log_rejects_unknown_direction(self, client):
        resp = client.post('/api/comms-log', json={
            'freq': '146.520',
            'direction': 'sideways',
            'message': 'Check-in',
        })
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_pace_create_rejects_wrong_type_name(self, client):
        resp = client.post('/api/comms/pace', json={'name': ['bad']})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_pace_create_accepts_valid_minimal_plan(self, client):
        resp = client.post('/api/comms/pace', json={'name': 'Storm Net'})
        assert resp.status_code == 201
        assert resp.get_json()['name'] == 'Storm Net'

    def test_serial_connect_requires_port_before_backend_connect(self, client):
        resp = client.post('/api/serial/connect', json={})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_mesh_message_rejects_non_string_message(self, client):
        resp = client.post('/api/mesh/messages', json={'message': ['bad']})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_broadcast_rejects_non_string_message(self, client):
        resp = client.post('/api/broadcast', json={'message': {'bad': 'shape'}})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'
