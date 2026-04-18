"""Tests for threat_intel — feeds CRUD, entries CRUD with severity
scoring, filter behavior, toggle/resolve state transitions, dashboard
threat-level logic, map-data endpoint, summary."""

import json


def _make_feed(client, **overrides):
    body = {
        'name':      overrides.pop('name', 'USGS Quakes'),
        'feed_type': overrides.pop('feed_type', 'manual'),
        'url':       overrides.pop('url', ''),
        'category':  overrides.pop('category', 'natural_disaster'),
    }
    body.update(overrides)
    resp = client.post('/api/threat-intel/feeds', json=body)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()


def _make_entry(client, **overrides):
    body = {
        'title':    overrides.pop('title', 'M6.2 Earthquake'),
        'category': overrides.pop('category', 'natural_disaster'),
        'severity': overrides.pop('severity', 'high'),
    }
    body.update(overrides)
    resp = client.post('/api/threat-intel/entries', json=body)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()


class TestThreatFeeds:
    def test_list_empty(self, client):
        assert client.get('/api/threat-intel/feeds').get_json() == []

    def test_create_requires_name(self, client):
        resp = client.post('/api/threat-intel/feeds',
                           json={'feed_type': 'manual'})
        assert resp.status_code == 400

    def test_create_and_list_ordered_by_enabled(self, client):
        _make_feed(client, name='Disabled', enabled=False)
        _make_feed(client, name='Enabled')
        feeds = client.get('/api/threat-intel/feeds').get_json()
        assert feeds[0]['name'] == 'Enabled'
        assert feeds[0]['enabled'] == 1

    def test_update(self, client):
        f = _make_feed(client)
        resp = client.put(f'/api/threat-intel/feeds/{f["id"]}',
                          json={'refresh_interval_min': 15})
        assert resp.status_code == 200
        assert resp.get_json()['refresh_interval_min'] == 15

    def test_update_404(self, client):
        resp = client.put('/api/threat-intel/feeds/99999',
                          json={'name': 'X'})
        assert resp.status_code == 404

    def test_update_empty_body(self, client):
        f = _make_feed(client)
        resp = client.put(f'/api/threat-intel/feeds/{f["id"]}', json={})
        assert resp.status_code == 400

    def test_toggle_flips_enabled(self, client):
        f = _make_feed(client, enabled=True)
        resp = client.post(f'/api/threat-intel/feeds/{f["id"]}/toggle')
        assert resp.status_code == 200
        assert resp.get_json()['enabled'] == 0
        again = client.post(f'/api/threat-intel/feeds/{f["id"]}/toggle')
        assert again.get_json()['enabled'] == 1

    def test_toggle_404(self, client):
        assert client.post('/api/threat-intel/feeds/99999/toggle').status_code == 404

    def test_delete_cascades_entries(self, client, db):
        f = _make_feed(client)
        _make_entry(client, feed_id=f['id'])
        _make_entry(client, title='Another', feed_id=f['id'])
        assert db.execute(
            'SELECT COUNT(*) FROM threat_entries WHERE feed_id = ?',
            (f['id'],),
        ).fetchone()[0] == 2

        resp = client.delete(f'/api/threat-intel/feeds/{f["id"]}')
        assert resp.status_code == 200

        assert db.execute(
            'SELECT COUNT(*) FROM threat_entries WHERE feed_id = ?',
            (f['id'],),
        ).fetchone()[0] == 0

    def test_delete_404(self, client):
        assert client.delete('/api/threat-intel/feeds/99999').status_code == 404


class TestThreatEntries:
    def test_list_empty(self, client):
        assert client.get('/api/threat-intel/entries').get_json() == []

    def test_create_requires_title(self, client):
        resp = client.post('/api/threat-intel/entries', json={'severity': 'high'})
        assert resp.status_code == 400

    def test_create_computes_severity_score(self, client):
        e = _make_entry(client, severity='critical')
        # critical is index 4 in SEVERITY_LEVELS = ['info','low','medium','high','critical']
        assert e['severity_score'] == 4
        e2 = _make_entry(client, severity='info', title='Minor')
        assert e2['severity_score'] == 0

    def test_create_falls_back_for_unknown_severity(self, client):
        # Unknown severities default to medium (index 2)
        e = _make_entry(client, severity='apocalyptic')
        assert e['severity_score'] == 2

    def test_create_stores_tags_as_json(self, client):
        _make_entry(client, tags=['seismic', 'pacific'])
        rows = client.get('/api/threat-intel/entries').get_json()
        assert json.loads(rows[0]['tags']) == ['seismic', 'pacific']

    def test_list_default_filters_unresolved(self, client):
        e1 = _make_entry(client, title='A')
        _make_entry(client, title='B')
        # Resolve A
        client.post(f'/api/threat-intel/entries/{e1["id"]}/resolve')
        data = client.get('/api/threat-intel/entries').get_json()
        assert [e['title'] for e in data] == ['B']

    def test_list_active_zero_shows_resolved(self, client):
        e = _make_entry(client)
        client.post(f'/api/threat-intel/entries/{e["id"]}/resolve')
        all_entries = client.get('/api/threat-intel/entries?active=0').get_json()
        assert len(all_entries) == 1

    def test_list_filter_by_severity(self, client):
        _make_entry(client, title='Info', severity='info')
        _make_entry(client, title='High', severity='high')
        high = client.get('/api/threat-intel/entries?severity=high').get_json()
        assert [e['title'] for e in high] == ['High']

    def test_list_filter_by_category(self, client):
        _make_entry(client, title='Quake', category='natural_disaster')
        _make_entry(client, title='Recession', category='economic')
        econ = client.get('/api/threat-intel/entries?category=economic').get_json()
        assert [e['title'] for e in econ] == ['Recession']

    def test_list_orders_by_severity_desc(self, client):
        _make_entry(client, title='Info', severity='info')
        _make_entry(client, title='Critical', severity='critical')
        _make_entry(client, title='Medium', severity='medium')
        names = [e['title'] for e in client.get('/api/threat-intel/entries').get_json()]
        assert names[0] == 'Critical'  # severity_score=4 first

    def test_update_severity_recomputes_score(self, client):
        e = _make_entry(client, severity='medium')
        resp = client.put(f'/api/threat-intel/entries/{e["id"]}',
                          json={'severity': 'critical'})
        assert resp.status_code == 200
        assert resp.get_json()['severity'] == 'critical'
        assert resp.get_json()['severity_score'] == 4

    def test_update_404(self, client):
        resp = client.put('/api/threat-intel/entries/99999', json={'title': 'X'})
        assert resp.status_code == 404

    def test_update_empty_body(self, client):
        e = _make_entry(client)
        resp = client.put(f'/api/threat-intel/entries/{e["id"]}', json={})
        assert resp.status_code == 400

    def test_resolve_flips_state(self, client):
        e = _make_entry(client)
        r1 = client.post(f'/api/threat-intel/entries/{e["id"]}/resolve').get_json()
        assert r1['resolved'] == 1
        assert r1['resolved_at'] is not None
        r2 = client.post(f'/api/threat-intel/entries/{e["id"]}/resolve').get_json()
        assert r2['resolved'] == 0
        assert r2['resolved_at'] is None

    def test_resolve_404(self, client):
        assert client.post('/api/threat-intel/entries/99999/resolve').status_code == 404

    def test_delete(self, client):
        e = _make_entry(client)
        assert client.delete(f'/api/threat-intel/entries/{e["id"]}').status_code == 200

    def test_delete_404(self, client):
        assert client.delete('/api/threat-intel/entries/99999').status_code == 404


class TestThreatIntelDashboard:
    def test_dashboard_empty_is_NORMAL(self, client):
        data = client.get('/api/threat-intel/dashboard').get_json()
        assert data['active_threats'] == 0
        assert data['threat_level'] == 'NORMAL'
        assert data['by_severity'] == {}
        assert data['by_category'] == []
        assert data['recent'] == []

    def test_dashboard_low_threat(self, client):
        _make_entry(client, severity='low')
        data = client.get('/api/threat-intel/dashboard').get_json()
        assert data['threat_level'] == 'LOW'

    def test_dashboard_escalates_to_ELEVATED_on_high(self, client):
        for i in range(2):
            _make_entry(client, title=f'H{i}', severity='high')
        data = client.get('/api/threat-intel/dashboard').get_json()
        assert data['threat_level'] == 'ELEVATED'

    def test_dashboard_escalates_to_CRITICAL_on_critical(self, client):
        _make_entry(client, severity='critical')
        data = client.get('/api/threat-intel/dashboard').get_json()
        assert data['threat_level'] == 'CRITICAL'

    def test_dashboard_escalates_to_GUARDED_on_6_info_entries(self, client):
        for i in range(6):
            _make_entry(client, title=f'Minor{i}', severity='info')
        data = client.get('/api/threat-intel/dashboard').get_json()
        assert data['threat_level'] == 'GUARDED'

    def test_dashboard_resolved_do_not_count(self, client):
        e = _make_entry(client, severity='critical')
        client.post(f'/api/threat-intel/entries/{e["id"]}/resolve')
        data = client.get('/api/threat-intel/dashboard').get_json()
        assert data['active_threats'] == 0
        assert data['threat_level'] == 'NORMAL'

    def test_dashboard_recent_ordered_by_severity(self, client):
        _make_entry(client, title='A', severity='info')
        _make_entry(client, title='B', severity='critical')
        _make_entry(client, title='C', severity='medium')
        data = client.get('/api/threat-intel/dashboard').get_json()
        assert data['recent'][0]['title'] == 'B'

    def test_dashboard_active_feeds_counts_enabled_only(self, client):
        _make_feed(client, name='Enabled', enabled=True)
        _make_feed(client, name='Disabled', enabled=False)
        data = client.get('/api/threat-intel/dashboard').get_json()
        assert data['active_feeds'] == 1


class TestThreatIntelMapData:
    def test_returns_only_geolocated_active_threats(self, client):
        _make_entry(client, title='No geo', lat=None, lng=None)
        _make_entry(client, title='Has geo', lat=37.7749, lng=-122.4194)
        resolved = _make_entry(client, title='Resolved', lat=40, lng=-74)
        client.post(f'/api/threat-intel/entries/{resolved["id"]}/resolve')
        data = client.get('/api/threat-intel/map-data').get_json()
        titles = [d['title'] for d in data]
        assert titles == ['Has geo']


class TestThreatIntelCatalog:
    def test_categories_includes_expected(self, client):
        data = client.get('/api/threat-intel/categories').get_json()
        for c in ('natural_disaster', 'cyber', 'pandemic', 'military'):
            assert c in data


class TestThreatIntelSummary:
    def test_summary(self, client):
        e = _make_entry(client)
        _make_feed(client)
        client.post(f'/api/threat-intel/entries/{e["id"]}/resolve')
        data = client.get('/api/threat-intel/summary').get_json()
        assert data['threat_entries_total'] == 1
        assert data['threat_entries_active'] == 0
        assert data['threat_feeds'] == 1
