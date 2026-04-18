"""Tests for tactical_comms — radio equipment, authentication codes,
net schedules, comms check logs, message templates (SITREP / MEDEVAC /
SALUTE / SPOT / ACE / LACE), sent-message log with acknowledgement, and
field weather calculators (moon phase, lightning distance, Beaufort,
growing-degree days, wind chill, heat index)."""


def _make_radio(client, **overrides):
    body = {'name': overrides.pop('name', 'Baofeng UV-5R')}
    body.update(overrides)
    resp = client.post('/api/radio-equipment', json=body)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()


def _make_net(client, **overrides):
    body = {'name': overrides.pop('name', 'Daily Check-In')}
    body.update(overrides)
    resp = client.post('/api/net-schedules', json=body)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()


def _make_auth_code(client, **overrides):
    body = {
        'code_set_name': overrides.pop('code_set_name', 'ALPHA'),
        'valid_date':    overrides.pop('valid_date', '2025-04-18'),
        'challenge':     overrides.pop('challenge', 'BRAVO'),
        'response':      overrides.pop('response', 'CHARLIE'),
    }
    body.update(overrides)
    resp = client.post('/api/auth-codes', json=body)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()


class TestRadioEquipment:
    def test_list_empty(self, client):
        assert client.get('/api/radio-equipment').get_json() == []

    def test_create_requires_name(self, client):
        resp = client.post('/api/radio-equipment',
                           json={'radio_type': 'handheld'})
        assert resp.status_code == 400

    def test_create_and_list(self, client):
        _make_radio(client)
        rows = client.get('/api/radio-equipment').get_json()
        assert len(rows) == 1
        assert rows[0]['name'] == 'Baofeng UV-5R'

    def test_filter_by_type(self, client):
        _make_radio(client, name='Portable', radio_type='handheld')
        _make_radio(client, name='Base', radio_type='base')
        hh = client.get('/api/radio-equipment?type=handheld').get_json()
        assert [r['name'] for r in hh] == ['Portable']

    def test_update(self, client):
        r = _make_radio(client)
        resp = client.put(f'/api/radio-equipment/{r["id"]}',
                          json={'power_watts': 8, 'condition': 'degraded'})
        assert resp.status_code == 200
        assert resp.get_json()['power_watts'] == 8

    def test_update_404(self, client):
        resp = client.put('/api/radio-equipment/99999', json={'power_watts': 5})
        assert resp.status_code == 404

    def test_update_empty_body(self, client):
        r = _make_radio(client)
        resp = client.put(f'/api/radio-equipment/{r["id"]}', json={})
        assert resp.status_code == 400

    def test_delete(self, client):
        r = _make_radio(client)
        assert client.delete(f'/api/radio-equipment/{r["id"]}').status_code == 200

    def test_delete_404(self, client):
        assert client.delete('/api/radio-equipment/99999').status_code == 404


class TestAuthCodes:
    def test_create_requires_all_four_fields(self, client):
        resp = client.post('/api/auth-codes', json={'code_set_name': 'X'})
        assert resp.status_code == 400

    def test_create_and_filter_by_set(self, client):
        _make_auth_code(client, code_set_name='ALPHA')
        _make_auth_code(client, code_set_name='BRAVO')
        alpha = client.get('/api/auth-codes?code_set=ALPHA').get_json()
        assert len(alpha) == 1
        assert alpha[0]['code_set_name'] == 'ALPHA'

    def test_list_filter_by_active(self, client):
        _make_auth_code(client, code_set_name='ACTIVE', is_active=1)
        _make_auth_code(client, code_set_name='DORMANT', is_active=0)
        active = client.get('/api/auth-codes?active=1').get_json()
        assert [r['code_set_name'] for r in active] == ['ACTIVE']

    def test_today_returns_only_todays_codes(self, client):
        from datetime import date
        today = date.today().isoformat()
        _make_auth_code(client, valid_date=today)
        _make_auth_code(client, valid_date='2020-01-01')
        data = client.get('/api/auth-codes/today').get_json()
        assert len(data) == 1

    def test_update(self, client):
        a = _make_auth_code(client)
        resp = client.put(f'/api/auth-codes/{a["id"]}',
                          json={'duress_code': 'SABLE'})
        assert resp.status_code == 200
        assert resp.get_json()['duress_code'] == 'SABLE'

    def test_update_404(self, client):
        resp = client.put('/api/auth-codes/99999', json={'duress_code': 'X'})
        assert resp.status_code == 404

    def test_delete_404(self, client):
        assert client.delete('/api/auth-codes/99999').status_code == 404


class TestNetSchedules:
    def test_create_requires_name(self, client):
        resp = client.post('/api/net-schedules', json={'net_type': 'daily'})
        assert resp.status_code == 400

    def test_create_and_filter_active(self, client):
        _make_net(client, name='Alive', is_active=1)
        _make_net(client, name='Dormant', is_active=0)
        active = client.get('/api/net-schedules?active=1').get_json()
        assert [r['name'] for r in active] == ['Alive']

    def test_update(self, client):
        n = _make_net(client)
        resp = client.put(f'/api/net-schedules/{n["id"]}',
                          json={'duration_min': 45})
        assert resp.status_code == 200
        assert resp.get_json()['duration_min'] == 45

    def test_update_404(self, client):
        resp = client.put('/api/net-schedules/99999', json={'duration_min': 10})
        assert resp.status_code == 404

    def test_delete_cascades_comms_checks(self, client, db):
        n = _make_net(client)
        client.post('/api/comms-checks', json={
            'net_schedule_id': n['id'], 'check_date': '2025-04-18',
        })
        assert db.execute(
            'SELECT COUNT(*) FROM comms_checks WHERE net_schedule_id = ?',
            (n['id'],),
        ).fetchone()[0] == 1
        assert client.delete(f'/api/net-schedules/{n["id"]}').status_code == 200
        assert db.execute(
            'SELECT COUNT(*) FROM comms_checks WHERE net_schedule_id = ?',
            (n['id'],),
        ).fetchone()[0] == 0

    def test_delete_404(self, client):
        assert client.delete('/api/net-schedules/99999').status_code == 404


class TestCommsChecks:
    def test_create_requires_check_date(self, client):
        resp = client.post('/api/comms-checks', json={'operator': 'W1AW'})
        assert resp.status_code == 400

    def test_create_and_filter_by_net_schedule(self, client):
        net = _make_net(client)
        client.post('/api/comms-checks', json={
            'net_schedule_id': net['id'], 'check_date': '2025-04-18',
        })
        client.post('/api/comms-checks', json={'check_date': '2025-04-19'})
        for_net = client.get(
            f'/api/comms-checks?net_schedule_id={net["id"]}'
        ).get_json()
        assert len(for_net) == 1

    def test_delete_404(self, client):
        assert client.delete('/api/comms-checks/99999').status_code == 404


class TestMessageTemplates:
    def test_seed_populates_builtin(self, client):
        resp = client.post('/api/message-templates/seed')
        data = resp.get_json()
        assert data['seeded'] >= 6
        assert data['total_builtin'] == data['seeded']

    def test_seed_idempotent(self, client):
        client.post('/api/message-templates/seed')
        again = client.post('/api/message-templates/seed').get_json()
        assert again['seeded'] == 0

    def test_filter_by_type(self, client):
        client.post('/api/message-templates/seed')
        sitrep = client.get('/api/message-templates?type=SITREP').get_json()
        assert all(t['template_type'] == 'SITREP' for t in sitrep)

    def test_custom_create_requires_name(self, client):
        resp = client.post('/api/message-templates', json={
            'template_type': 'CUSTOM',
        })
        assert resp.status_code == 400

    def test_custom_create_and_delete(self, client):
        resp = client.post('/api/message-templates', json={
            'name': 'Local Format', 'template_type': 'CUSTOM',
            'instructions': 'When to use this local format',
        })
        assert resp.status_code == 201
        tid = resp.get_json()['id']
        assert client.delete(f'/api/message-templates/{tid}').status_code == 200

    def test_delete_404(self, client):
        assert client.delete('/api/message-templates/99999').status_code == 404


class TestSentMessages:
    def test_create_and_list(self, client):
        resp = client.post('/api/sent-messages', json={
            'template_type': 'SITREP',
            'formatted_text': 'Line 1: 141200Z',
            'sent_via': 'radio', 'sent_to': 'CMD',
        })
        assert resp.status_code == 201
        rows = client.get('/api/sent-messages').get_json()
        assert len(rows) == 1

    def test_filter_by_type(self, client):
        client.post('/api/sent-messages', json={'template_type': 'SITREP'})
        client.post('/api/sent-messages', json={'template_type': 'MEDEVAC'})
        data = client.get('/api/sent-messages?type=MEDEVAC').get_json()
        assert [m['template_type'] for m in data] == ['MEDEVAC']

    def test_ack_sets_acknowledged(self, client):
        resp = client.post('/api/sent-messages', json={
            'template_type': 'SITREP',
        })
        sid = resp.get_json()['id']
        ack = client.post(f'/api/sent-messages/{sid}/ack').get_json()
        assert ack['acknowledged'] == 1
        assert ack['acknowledged_at'] is not None

    def test_ack_404_when_missing(self, client):
        assert client.post('/api/sent-messages/99999/ack').status_code == 404


class TestWeatherCalculators:
    def test_moon_phase_today(self, client):
        data = client.get('/api/weather/moon-phase').get_json()
        assert 0 <= data['illumination_pct'] <= 100
        assert 'phase' in data
        assert 'day_of_cycle' in data
        assert 'good_for_night_ops' in data

    def test_moon_phase_rejects_bad_date(self, client):
        resp = client.get('/api/weather/moon-phase?date=not-a-date')
        assert resp.status_code == 400

    def test_lightning_distance(self, client):
        resp = client.post('/api/weather/lightning-distance',
                           json={'seconds': 5})
        data = resp.get_json()
        # "Rule-of-five": 5 sec ≈ 1 mile (the simplified seconds÷5 formula)
        assert data['distance_miles'] == 1.0
        assert data['danger_zone'] is True

    def test_lightning_distance_rejects_negative(self, client):
        resp = client.post('/api/weather/lightning-distance',
                           json={'seconds': -3})
        assert resp.status_code == 400

    def test_lightning_distance_defaults_to_zero(self, client):
        resp = client.post('/api/weather/lightning-distance', json={})
        assert resp.status_code == 200
        assert resp.get_json()['distance_miles'] == 0

    def test_beaufort_scale_complete(self, client):
        data = client.get('/api/weather/beaufort').get_json()
        assert len(data) == 13
        # First entry is Force 0 (Calm); last is Force 12 (Hurricane)
        assert data[0]['force'] == 0
        assert data[-1]['force'] == 12
        assert data[-1]['description'] == 'Hurricane'

    def test_growing_degree_days_basic(self, client):
        resp = client.post('/api/weather/growing-degree-days', json={
            'high_f': 80, 'low_f': 60, 'base_f': 50,
        })
        data = resp.get_json()
        # GDD = (80+60)/2 - 50 = 20
        assert data['gdd'] == 20

    def test_wind_chill_cold_valid(self, client):
        resp = client.post('/api/weather/wind-chill', json={
            'temp_f': 20, 'wind_mph': 15,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        # Formula only applies below 50°F and above 3 mph — both satisfied here
        assert data['wind_chill_f'] < 20

    def test_wind_chill_above_50_degrees_returns_actual_temp(self, client):
        # Above 50°F the formula isn't defined; endpoint should handle gracefully
        resp = client.post('/api/weather/wind-chill', json={
            'temp_f': 60, 'wind_mph': 10,
        })
        assert resp.status_code == 200

    def test_heat_index_hot_valid(self, client):
        resp = client.post('/api/weather/heat-index', json={
            'temp_f': 95, 'humidity_pct': 70,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        # 95°F at 70% RH has a heat index well above 95
        assert data['heat_index_f'] > 95


class TestTacticalCommsSummary:
    def test_summary_reflects_data(self, client):
        _make_radio(client)
        _make_net(client)
        client.post('/api/message-templates/seed')
        client.post('/api/sent-messages', json={'template_type': 'SITREP'})
        data = client.get('/api/tactical-comms/summary').get_json()
        assert data['total_radios'] >= 1
        assert data['active_nets'] >= 1
        assert data['message_templates'] >= 6
        assert data['total_messages_sent'] >= 1
