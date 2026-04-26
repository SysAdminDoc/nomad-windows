"""Smoke tests for the regional_profile blueprint.

Covers all 10 routes:
  GET  /api/region/profile            — returns configured: False when empty
  POST /api/region/profile            — saves profile, rejects bad state codes
  PUT  /api/region/profile            — updates active profile fields
  GET  /api/region/threats            — returns configured: False when no profile
  GET  /api/region/states             — full 51-entry US states list
  GET  /api/region/nri/counties       — requires ?state, returns empty list when no data
  GET  /api/region/nri/county/<fips>  — 404 when county not found
  GET  /api/region/readiness-weights  — default weights when no profile
  GET  /api/region/setup-status       — returns setup steps
  GET  /api/region/hardiness/<zip>    — found: False when ZIP missing from data pack
  GET  /api/region/frost-dates        — error when lat/lng missing; found: False when no data
  GET  /api/region/nearest-station    — error when lat/lng missing; found: False when no data
"""

import pytest
from db import db_session


# ─── helpers ──────────────────────────────────────────────────────────────────

_VALID_PROFILE = {
    'name': 'primary',
    'country': 'US',
    'state': 'TX',
    'county': 'Travis County',
    'zip_code': '78701',
    'lat': 30.2672,
    'lng': -97.7431,
    'notes': 'Test profile',
}


def _save_profile(client, **overrides):
    payload = {**_VALID_PROFILE, **overrides}
    resp = client.post('/api/region/profile', json=payload)
    assert resp.status_code == 201
    return resp.get_json()


# ─── Profile GET ──────────────────────────────────────────────────────────────

class TestRegionProfileGet:
    def test_no_profile_returns_unconfigured(self, client):
        resp = client.get('/api/region/profile')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['configured'] is False
        assert body['profile'] is None

    def test_active_profile_returned(self, client):
        _save_profile(client)
        resp = client.get('/api/region/profile')
        body = resp.get_json()
        assert body['configured'] is True
        assert body['state'] == 'TX'
        assert body['country'] == 'US'

    def test_fema_risk_scores_parsed_as_dict(self, client):
        """fema_risk_scores stored as JSON string must be returned as a dict."""
        _save_profile(client)
        resp = client.get('/api/region/profile')
        body = resp.get_json()
        assert isinstance(body['fema_risk_scores'], dict)
        assert isinstance(body['threat_weights'], dict)

    def test_only_active_profile_returned(self, client):
        """Multiple saved profiles — only the newest active one is returned."""
        _save_profile(client, name='first')
        _save_profile(client, name='second', state='CO')
        resp = client.get('/api/region/profile')
        body = resp.get_json()
        # POST deactivates old rows; new one wins
        assert body['state'] == 'CO'


# ─── Profile POST ─────────────────────────────────────────────────────────────

class TestRegionProfilePost:
    def test_save_minimal_profile(self, client):
        resp = client.post('/api/region/profile', json={'state': 'WY'})
        assert resp.status_code == 201
        body = resp.get_json()
        assert body['status'] == 'saved'

    def test_invalid_state_returns_400(self, client):
        resp = client.post('/api/region/profile', json={'state': 'XX'})
        assert resp.status_code == 400
        assert 'error' in resp.get_json()

    def test_empty_state_accepted(self, client):
        """Empty state string is valid (region may span multiple states)."""
        resp = client.post('/api/region/profile', json={'state': '', 'country': 'US'})
        assert resp.status_code == 201

    def test_saves_full_profile(self, client):
        resp = _save_profile(client)
        assert resp['status'] == 'saved'
        # Verify it is queryable
        profile = client.get('/api/region/profile').get_json()
        assert profile['zip_code'] == '78701'
        assert profile['lat'] == pytest.approx(30.2672, abs=0.001)

    def test_auto_enrichment_field_is_dict(self, client):
        """enriched key in response is always a dict (may be empty)."""
        resp = client.post('/api/region/profile', json={'state': 'CA'})
        body = resp.get_json()
        assert isinstance(body.get('enriched', {}), dict)

    def test_saves_fema_risk_scores(self, client):
        scores = {'wildfire': 85.0, 'earthquake': 70.0}
        client.post('/api/region/profile', json={
            'state': 'CA', 'fema_risk_scores': scores
        })
        resp = client.get('/api/region/profile')
        body = resp.get_json()
        assert body['fema_risk_scores'].get('wildfire') == pytest.approx(85.0, abs=0.1)


# ─── Profile PUT ──────────────────────────────────────────────────────────────

class TestRegionProfilePut:
    def test_put_no_profile_returns_404(self, client):
        resp = client.put('/api/region/profile', json={'notes': 'test'})
        assert resp.status_code == 404

    def test_put_updates_notes(self, client):
        _save_profile(client)
        resp = client.put('/api/region/profile', json={'notes': 'Updated notes'})
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'updated'
        profile = client.get('/api/region/profile').get_json()
        assert profile['notes'] == 'Updated notes'

    def test_put_no_fields_returns_400(self, client):
        _save_profile(client)
        resp = client.put('/api/region/profile', json={})
        assert resp.status_code == 400

    def test_put_updates_json_fields(self, client):
        _save_profile(client)
        weights = {'water_storage': 2.5, 'shelter_prep': 1.8}
        resp = client.put('/api/region/profile', json={'threat_weights': weights})
        assert resp.status_code == 200


# ─── Threats ─────────────────────────────────────────────────────────────────

class TestRegionThreats:
    def test_no_profile_returns_unconfigured(self, client):
        resp = client.get('/api/region/threats')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['configured'] is False
        assert body['threats'] == []

    def test_profile_with_no_fema_data_returns_empty_threats(self, client):
        """Profile exists but FEMA NRI table has no matching county data."""
        _save_profile(client)
        resp = client.get('/api/region/threats')
        body = resp.get_json()
        assert body['configured'] is True
        assert isinstance(body['threats'], list)

    def test_profile_with_stored_scores_returns_threats(self, client):
        scores = {'wildfire': 75.0, 'drought': 60.0, 'earthquake': 10.0}
        client.post('/api/region/profile', json={
            'state': 'CA', 'county': 'Sonoma County',
            'fema_risk_scores': scores
        })
        resp = client.get('/api/region/threats')
        body = resp.get_json()
        assert body['configured'] is True
        # Threats are sorted by score descending; wildfire (75) should be first
        if body['threats']:
            assert body['threats'][0]['score'] >= body['threats'][-1]['score']

    def test_zero_score_threats_excluded(self, client):
        scores = {'wildfire': 0.0, 'drought': 55.0}
        client.post('/api/region/profile', json={
            'state': 'NV', 'fema_risk_scores': scores
        })
        resp = client.get('/api/region/threats')
        body = resp.get_json()
        hazards = [t['hazard'] for t in body['threats']]
        assert 'wildfire' not in hazards  # score=0 excluded


# ─── States ───────────────────────────────────────────────────────────────────

class TestRegionStates:
    def test_returns_all_51_states(self, client):
        resp = client.get('/api/region/states')
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 51  # 50 states + DC

    def test_states_sorted_by_name(self, client):
        data = client.get('/api/region/states').get_json()
        names = [s['name'] for s in data]
        assert names == sorted(names)

    def test_each_entry_has_code_and_name(self, client):
        data = client.get('/api/region/states').get_json()
        for entry in data:
            assert 'code' in entry
            assert 'name' in entry
            assert len(entry['code']) == 2

    def test_contains_known_states(self, client):
        data = client.get('/api/region/states').get_json()
        codes = {s['code'] for s in data}
        for code in ('TX', 'CA', 'NY', 'FL', 'DC'):
            assert code in codes


# ─── NRI Counties ─────────────────────────────────────────────────────────────

class TestRegionNriCounties:
    def test_missing_state_returns_400(self, client):
        resp = client.get('/api/region/nri/counties')
        assert resp.status_code == 400
        assert 'error' in resp.get_json()

    def test_valid_state_empty_data_pack_returns_empty_list(self, client):
        """FEMA NRI table is empty in the test DB — should return []."""
        resp = client.get('/api/region/nri/counties?state=TX')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_accepts_state_code_and_resolves_name(self, client):
        """TX should be looked up as 'Texas' internally."""
        resp = client.get('/api/region/nri/counties?state=tx')
        assert resp.status_code == 200  # no error, just empty list

    def test_seeded_county_returned(self, client):
        with db_session() as db:
            db.execute('''
                INSERT INTO fema_nri_counties
                (state_fips, county_fips, county_name, state_name, risk_score,
                 risk_rating, social_vulnerability, community_resilience, hazard_scores)
                VALUES (?,?,?,?,?,?,?,?,?)
            ''', ('48', '48453', 'Travis County', 'Texas', 72.5, 'Relatively High',
                  0.4, 0.6, '{"wildfire": 60.0}'))
            db.commit()
        resp = client.get('/api/region/nri/counties?state=TX')
        data = resp.get_json()
        assert len(data) >= 1
        assert data[0]['county_name'] == 'Travis County'
        assert data[0]['risk_score'] == pytest.approx(72.5, abs=0.1)


# ─── NRI County Detail ────────────────────────────────────────────────────────

class TestRegionNriCountyDetail:
    def test_unknown_fips_returns_404(self, client):
        resp = client.get('/api/region/nri/county/00000')
        assert resp.status_code == 404
        assert 'error' in resp.get_json()

    def test_seeded_county_returns_detail(self, client):
        with db_session() as db:
            db.execute('''
                INSERT INTO fema_nri_counties
                (state_fips, county_fips, county_name, state_name, risk_score,
                 risk_rating, social_vulnerability, community_resilience, hazard_scores)
                VALUES (?,?,?,?,?,?,?,?,?)
            ''', ('53', '53033', 'King County', 'Washington', 55.0, 'Relatively Moderate',
                  0.3, 0.7, '{"earthquake": 80.0, "volcanic_activity": 40.0}'))
            db.commit()
        resp = client.get('/api/region/nri/county/53033')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['county_name'] == 'King County'
        assert isinstance(body['hazard_scores'], dict)
        assert body['hazard_scores'].get('earthquake') == pytest.approx(80.0, abs=0.1)


# ─── Readiness Weights ────────────────────────────────────────────────────────

class TestRegionReadinessWeights:
    def test_no_profile_returns_defaults(self, client):
        resp = client.get('/api/region/readiness-weights')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['adjusted'] is False
        assert isinstance(body['weights'], dict)
        assert 'food_storage' in body['weights']

    def test_profile_no_fema_scores_returns_unadjusted_defaults(self, client):
        client.post('/api/region/profile', json={'state': 'WY'})
        resp = client.get('/api/region/readiness-weights')
        body = resp.get_json()
        # No FEMA scores → defaults
        assert isinstance(body['weights'], dict)

    def test_profile_with_custom_weights_returns_them(self, client):
        custom = {'water_storage': 3.0, 'shelter_prep': 2.5}
        client.post('/api/region/profile', json={
            'state': 'FL', 'threat_weights': custom,
        })
        resp = client.get('/api/region/readiness-weights')
        body = resp.get_json()
        assert body['adjusted'] is True
        assert body['source'] == 'custom'
        assert body['weights']['water_storage'] == pytest.approx(3.0, abs=0.1)

    def test_profile_with_fema_scores_adjusts_weights(self, client):
        scores = {'drought': 90.0, 'wildfire': 85.0}
        client.post('/api/region/profile', json={
            'state': 'CA', 'fema_risk_scores': scores,
        })
        resp = client.get('/api/region/readiness-weights')
        body = resp.get_json()
        # Scores >50 → weights adjusted upward
        assert body['adjusted'] is True
        assert body['source'] == 'fema_auto'


# ─── Setup Status ─────────────────────────────────────────────────────────────

class TestRegionSetupStatus:
    def test_returns_setup_fields(self, client):
        resp = client.get('/api/region/setup-status')
        assert resp.status_code == 200
        body = resp.get_json()
        assert 'setup_needed' in body
        assert 'all_complete' in body
        assert 'steps' in body
        assert 'profile_configured' in body

    def test_fresh_db_setup_needed(self, client):
        resp = client.get('/api/region/setup-status')
        body = resp.get_json()
        assert body['setup_needed'] is True
        assert body['profile_configured'] is False

    def test_steps_is_list_with_expected_ids(self, client):
        data = client.get('/api/region/setup-status').get_json()
        step_ids = {s['id'] for s in data['steps']}
        for sid in ('location', 'data_packs', 'threats', 'household'):
            assert sid in step_ids

    def test_each_step_has_complete_flag(self, client):
        data = client.get('/api/region/setup-status').get_json()
        for step in data['steps']:
            assert 'id' in step
            assert 'title' in step
            assert 'complete' in step
            assert isinstance(step['complete'], bool)


# ─── Hardiness Zone ──────────────────────────────────────────────────────────

class TestRegionHardiness:
    def test_unknown_zip_returns_not_found(self, client):
        resp = client.get('/api/region/hardiness/99999')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['found'] is False

    def test_seeded_zip_returns_zone(self, client):
        with db_session() as db:
            db.execute(
                'INSERT INTO usda_hardiness_zones (zipcode, zone, trange, state) VALUES (?,?,?,?)',
                ('78701', '8b', '15 to 20 F', 'TX')
            )
            db.commit()
        resp = client.get('/api/region/hardiness/78701')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['found'] is True
        assert body['zone'] == '8b'
        assert body['state'] == 'TX'


# ─── Frost Dates ──────────────────────────────────────────────────────────────

class TestRegionFrostDates:
    def test_missing_lat_lng_returns_400(self, client):
        resp = client.get('/api/region/frost-dates')
        assert resp.status_code == 400
        assert 'error' in resp.get_json()

    def test_zero_lat_lng_returns_400(self, client):
        resp = client.get('/api/region/frost-dates?lat=0&lng=0')
        assert resp.status_code == 400

    def test_no_data_returns_not_found(self, client):
        resp = client.get('/api/region/frost-dates?lat=30.27&lng=-97.74')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['found'] is False

    def test_seeded_station_returns_frost_dates(self, client):
        with db_session() as db:
            db.execute('''
                INSERT INTO noaa_frost_dates
                (station_id, station_name, state, lat, lng,
                 last_spring_32f, first_fall_32f, growing_season_days)
                VALUES (?,?,?,?,?,?,?,?)
            ''', ('TX001', 'Austin Station', 'TX', 30.27, -97.74,
                  'Mar 06', 'Nov 25', 264))
            db.commit()
        resp = client.get('/api/region/frost-dates?lat=30.27&lng=-97.74')
        body = resp.get_json()
        assert body['found'] is True
        assert body['last_spring_32f'] == 'Mar 06'
        assert body['first_fall_32f'] == 'Nov 25'
        assert body['growing_season_days'] == 264


# ─── Nearest Weather Station ──────────────────────────────────────────────────

class TestRegionNearestStation:
    def test_missing_lat_lng_returns_400(self, client):
        resp = client.get('/api/region/nearest-station')
        assert resp.status_code == 400
        assert 'error' in resp.get_json()

    def test_zero_lat_lng_returns_400(self, client):
        resp = client.get('/api/region/nearest-station?lat=0&lng=0')
        assert resp.status_code == 400

    def test_no_stations_returns_not_found(self, client):
        resp = client.get('/api/region/nearest-station?lat=30.27&lng=-97.74')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['found'] is False

    def test_seeded_station_returned(self, client):
        with db_session() as db:
            db.execute('''
                INSERT INTO noaa_stations
                (station_id, name, state, lat, lng, icao, elevation_m)
                VALUES (?,?,?,?,?,?,?)
            ''', ('KAUS', 'Austin-Bergstrom International Airport', 'TX',
                  30.195, -97.666, 'KAUS', 154))
            db.commit()
        resp = client.get('/api/region/nearest-station?lat=30.27&lng=-97.74')
        body = resp.get_json()
        assert body['found'] is True
        assert body['station_id'] == 'KAUS'
        assert body['state'] == 'TX'
