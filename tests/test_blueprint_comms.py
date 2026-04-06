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


class TestPrintFreqCard:
    def test_freq_card_print(self, client):
        resp = client.get('/api/print/freq-card')
        assert resp.status_code == 200
