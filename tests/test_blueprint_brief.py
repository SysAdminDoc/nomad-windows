"""Smoke tests for brief blueprint (Daily Operations Brief).

Covers both routes:
- GET /api/brief/daily -> JSON payload with all 6 sections (weather,
  proximity, inventory, tasks, family, emergency).
- GET /api/brief/daily/print -> printable HTML version.

Each section is a pure DB composition — graceful degradation is a
core guarantee ("no data => section still returns a stable shape").
The suite seeds targeted rows table-by-table to verify each section
lights up, and verifies the empty-DB baseline.

Pattern matches tests/test_blueprint_agriculture.py.
"""

from db import db_session


# ── HELPERS ───────────────────────────────────────────────────────────────

def _set_setting(key, value):
    with db_session() as db:
        db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, str(value))
        )
        db.commit()


# ── BASELINE (EMPTY DB) ───────────────────────────────────────────────────

class TestBriefBaseline:
    def test_daily_returns_stable_shape_on_empty_db(self, client):
        """With no rows in weather/tasks/inventory/family etc., the brief
        still returns 200 with the top-level envelope intact."""
        resp = client.get('/api/brief/daily')
        assert resp.status_code == 200
        body = resp.get_json()
        # Top-level shape is stable regardless of section population
        for key in ('generated_at', 'node_name', 'date', 'sections'):
            assert key in body
        assert isinstance(body['sections'], dict)

    def test_daily_print_returns_html(self, client):
        resp = client.get('/api/brief/daily/print')
        assert resp.status_code == 200
        assert resp.mimetype == 'text/html'
        # Heuristic: printable output carries the brief title
        assert b'Daily' in resp.data or b'Brief' in resp.data


# ── WEATHER SECTION ───────────────────────────────────────────────────────

class TestWeatherSection:
    def test_weather_section_maps_schema_to_brief_payload(self, client):
        """Schema-fix landed 2026-04-24 — brief.py now reads `temp_f` /
        `pressure_hpa` from the actual weather_log columns and emits
        BOTH the legacy `temp_c` (Fahrenheit→Celsius converted) plus
        canonical `temp_f` / `pressure` / `conditions` (synthesized
        from clouds + precip). Earlier the section silently emitted
        all-None data fields."""
        with db_session() as db:
            db.execute(
                "INSERT INTO weather_log "
                "(temp_f, pressure_hpa, clouds, precip, wind_dir, wind_speed, "
                " visibility, notes) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (68.0, 1013.0, 'partly cloudy', 'light rain',
                 'NW', '15 km/h', '10 km', 'morning reading')
            )
            db.commit()
        s = client.get('/api/brief/daily').get_json()['sections'].get('weather')
        assert s is not None
        assert s['temp_f'] == 68.0
        # 68 F -> 20.0 C (Fahrenheit→Celsius conversion)
        assert s['temp_c'] == 20.0
        assert s['pressure'] == 1013.0
        assert s['wind_dir'] == 'NW'
        assert s['wind_speed'] == '15 km/h'
        assert s['visibility'] == '10 km'
        # conditions synthesizes from clouds + precip
        assert 'partly cloudy' in s['conditions']
        assert 'light rain' in s['conditions']
        assert s['notes'] == 'morning reading'

    def test_weather_section_handles_partial_data(self, client):
        """Sparse weather rows don't crash — missing temp_f leaves
        temp_c None, missing clouds/precip yields empty conditions."""
        with db_session() as db:
            db.execute(
                "INSERT INTO weather_log (notes) VALUES (?)", ('sparse',)
            )
            db.commit()
        s = client.get('/api/brief/daily').get_json()['sections'].get('weather')
        assert s is not None
        assert s['temp_c'] is None
        assert s['conditions'] == ''
        assert s['notes'] == 'sparse'

    def test_weather_picks_most_recent_row(self, client):
        """ORDER BY created_at DESC LIMIT 1. Explicit created_at values
        because SQLite CURRENT_TIMESTAMP rounds to seconds and back-to-back
        inserts in a test tie."""
        with db_session() as db:
            db.execute("INSERT INTO weather_log (temp_f, notes, created_at) "
                       "VALUES (?,?,?)", (50.0, 'older', '2026-04-23 12:00:00'))
            db.execute("INSERT INTO weather_log (temp_f, notes, created_at) "
                       "VALUES (?,?,?)", (75.0, 'newer', '2026-04-24 12:00:00'))
            db.commit()
        s = client.get('/api/brief/daily').get_json()['sections'].get('weather')
        assert s['notes'] == 'newer'
        assert s['temp_f'] == 75.0


# ── PROXIMITY SECTION ─────────────────────────────────────────────────────

class TestProximitySection:
    def test_proximity_absent_without_home_coords(self, client):
        """If home lat/lng settings aren't configured, the proximity
        section is omitted entirely (no division, no radius default)."""
        body = client.get('/api/brief/daily').get_json()
        assert 'proximity' not in body['sections']

    def test_proximity_filters_by_radius(self, client):
        """Events within radius are included; events outside are dropped.
        Note: the backend SQL filters `lat != 0 AND lng != 0`, so we
        use non-zero coords for both home and events. Haversine from
        (40,-100) to (40.5,-100) is ~55.6 km; to (45,-100) is ~555 km.
        A 200 km radius includes the first but not the second."""
        _set_setting('latitude', '40')
        _set_setting('longitude', '-100')
        _set_setting('proximity_radius_km', '200')
        with db_session() as db:
            db.execute(
                "INSERT INTO sitroom_events "
                "(event_type, title, magnitude, lat, lng) VALUES (?,?,?,?,?)",
                ('earthquake', 'Near event', 5.5, 40.5, -100.0)
            )
            db.execute(
                "INSERT INTO sitroom_events "
                "(event_type, title, magnitude, lat, lng) VALUES (?,?,?,?,?)",
                ('earthquake', 'Far event', 6.0, 45.0, -100.0)
            )
            db.commit()
        prox = client.get('/api/brief/daily').get_json()['sections']['proximity']
        assert prox['radius_km'] == 200.0
        assert prox['count'] == 1
        titles = {e['title'] for e in prox['events']}
        assert 'Near event' in titles
        assert 'Far event' not in titles

    def test_proximity_skips_zero_and_null_coords(self, client):
        """Events with lat=0 AND lng=0 are treated as 'no coord' (the
        SQL filter excludes them alongside explicit NULL)."""
        _set_setting('latitude', '40')
        _set_setting('longitude', '-100')
        _set_setting('proximity_radius_km', '1000')
        with db_session() as db:
            db.execute(
                "INSERT INTO sitroom_events "
                "(event_type, title, magnitude, lat, lng) VALUES (?,?,?,?,?)",
                ('fire', 'No coords', 0, 0.0, 0.0)
            )
            db.commit()
        prox = client.get('/api/brief/daily').get_json()['sections']['proximity']
        assert prox['count'] == 0

    def test_proximity_sorts_by_distance(self, client):
        _set_setting('latitude', '40')
        _set_setting('longitude', '-100')
        _set_setting('proximity_radius_km', '5000')
        with db_session() as db:
            db.execute(
                "INSERT INTO sitroom_events (event_type, title, lat, lng) "
                "VALUES (?,?,?,?)", ('fire', 'Far', 60.0, -100.0)
            )
            db.execute(
                "INSERT INTO sitroom_events (event_type, title, lat, lng) "
                "VALUES (?,?,?,?)", ('fire', 'Near', 42.0, -100.0)
            )
            db.commit()
        events = client.get('/api/brief/daily').get_json()['sections']['proximity']['events']
        # Sorted ascending by distance → Near comes first
        assert events[0]['title'] == 'Near'
        assert events[1]['title'] == 'Far'


# ── INVENTORY SECTION ─────────────────────────────────────────────────────

class TestInventorySection:
    def test_expiring_14d_picks_only_items_within_window(self, client):
        """Items with expiration <= now+14d land in expiring_14d;
        items past that window don't."""
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        soon = (now + timedelta(days=7)).strftime('%Y-%m-%d')
        later = (now + timedelta(days=30)).strftime('%Y-%m-%d')
        with db_session() as db:
            db.execute(
                "INSERT INTO inventory (name, quantity, unit, expiration) "
                "VALUES (?,?,?,?)", ('Canned soup', 4, 'cans', soon)
            )
            db.execute(
                "INSERT INTO inventory (name, quantity, unit, expiration) "
                "VALUES (?,?,?,?)", ('Dry rice', 10, 'lbs', later)
            )
            db.commit()
        inv = client.get('/api/brief/daily').get_json()['sections']['inventory']
        names = {r['name'] for r in inv['expiring_14d']}
        assert 'Canned soup' in names
        assert 'Dry rice' not in names

    def test_low_stock_flags_items_at_or_below_minimum(self, client):
        """quantity <= min_quantity AND min_quantity > 0 → appears in low_stock."""
        with db_session() as db:
            db.execute(
                "INSERT INTO inventory (name, quantity, min_quantity, unit) "
                "VALUES (?,?,?,?)", ('Below min', 2, 5, 'ea')
            )
            db.execute(
                "INSERT INTO inventory (name, quantity, min_quantity, unit) "
                "VALUES (?,?,?,?)", ('At min', 5, 5, 'ea')
            )
            db.execute(
                "INSERT INTO inventory (name, quantity, min_quantity, unit) "
                "VALUES (?,?,?,?)", ('Above min', 10, 5, 'ea')
            )
            db.execute(
                "INSERT INTO inventory (name, quantity, min_quantity, unit) "
                "VALUES (?,?,?,?)", ('No min set', 1, 0, 'ea')
            )
            db.commit()
        inv = client.get('/api/brief/daily').get_json()['sections']['inventory']
        names = {r['name'] for r in inv['low_stock']}
        assert 'Below min' in names
        assert 'At min' in names
        assert 'Above min' not in names
        assert 'No min set' not in names  # min_quantity=0 excluded


# ── TASKS SECTION ─────────────────────────────────────────────────────────

class TestTasksSection:
    """Tasks section was silently broken before 2026-04-24 — brief.py
    queried legacy column names that didn't exist (title / due_at /
    completed_at). Schema-fix landed in the same continuation: the
    query now uses canonical columns (name / next_due / last_completed)
    and emits a payload with both legacy aliases (title, due_at) AND
    canonical names so renderers keep working unchanged."""

    def test_tasks_due_today_includes_today_and_overdue(self, client):
        from datetime import datetime, timezone, timedelta
        today = datetime.now(timezone.utc).date().isoformat()
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
        tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()
        with db_session() as db:
            db.execute(
                "INSERT INTO scheduled_tasks (name, category, recurrence, next_due) "
                "VALUES (?,?,?,?)", ('Today task', 'high', 'once', today + 'T09:00:00')
            )
            db.execute(
                "INSERT INTO scheduled_tasks (name, category, recurrence, next_due) "
                "VALUES (?,?,?,?)", ('Overdue', 'critical', 'once', yesterday)
            )
            db.execute(
                "INSERT INTO scheduled_tasks (name, category, recurrence, next_due) "
                "VALUES (?,?,?,?)", ('Future', 'low', 'once', tomorrow)
            )
            db.commit()
        due = client.get('/api/brief/daily').get_json()['sections']['tasks']['due_today']
        titles = {t['title'] for t in due}
        assert 'Today task' in titles
        assert 'Overdue' in titles
        assert 'Future' not in titles

    def test_completed_tasks_excluded(self, client):
        """A task whose last_completed >= today's ISO date is filtered
        out of due_today (already done this cycle)."""
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).date().isoformat()
        with db_session() as db:
            db.execute(
                "INSERT INTO scheduled_tasks "
                "(name, category, recurrence, next_due, last_completed) "
                "VALUES (?,?,?,?,?)",
                ('Done today', 'low', 'once', today, today + 'T08:00:00')
            )
            db.commit()
        due = client.get('/api/brief/daily').get_json()['sections']['tasks']['due_today']
        assert not any(t['title'] == 'Done today' for t in due)

    def test_payload_carries_legacy_and_canonical_field_names(self, client):
        """Schema-fix backwards-compat: payload includes both legacy
        aliases (title, due_at, priority) and canonical names (name,
        next_due, category) so renderers built against either era
        keep working."""
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).date().isoformat()
        with db_session() as db:
            db.execute(
                "INSERT INTO scheduled_tasks (name, category, recurrence, next_due) "
                "VALUES (?,?,?,?)", ('Sample', 'medical', 'weekly', today)
            )
            db.commit()
        due = client.get('/api/brief/daily').get_json()['sections']['tasks']['due_today']
        assert len(due) == 1
        t = due[0]
        # Legacy + canonical name fields point to the same value
        assert t['title'] == 'Sample' and t['name'] == 'Sample'
        assert t['due_at'] == today and t['next_due'] == today
        assert t['priority'] == 'medical' and t['category'] == 'medical'


# ── FAMILY SECTION ────────────────────────────────────────────────────────

class TestFamilySection:
    def test_family_summary_groups_by_status(self, client):
        """family_checkins table uses `name` column (UNIQUE). Each row
        is a distinct household member with a status."""
        with db_session() as db:
            for st, who in [('ok', 'Alice'), ('ok', 'Bob'),
                            ('en_route', 'Carol'), ('needs_help', 'Dave')]:
                db.execute(
                    "INSERT INTO family_checkins (name, status) VALUES (?, ?)",
                    (who, st)
                )
            db.commit()
        fam = client.get('/api/brief/daily').get_json()['sections']['family']
        assert fam['total'] == 4
        assert fam['summary']['ok'] == 2
        assert fam['summary']['en_route'] == 1
        assert fam['summary']['needs_help'] == 1


# ── EMERGENCY SECTION ─────────────────────────────────────────────────────

class TestEmergencySection:
    def test_emergency_inactive_by_default(self, client):
        """Fresh DB has no emergency_active setting → section reports False."""
        emer = client.get('/api/brief/daily').get_json()['sections']['emergency']
        assert emer['active'] is False
        assert emer['reason'] == ''
        assert emer['started_at'] is None

    def test_emergency_active_flag_respected(self, client):
        _set_setting('emergency_active', 'True')
        _set_setting('emergency_reason', 'Wildfire approaching')
        _set_setting('emergency_started_at', '2026-04-24T12:00:00')
        emer = client.get('/api/brief/daily').get_json()['sections']['emergency']
        assert emer['active'] is True
        assert emer['reason'] == 'Wildfire approaching'
        assert emer['started_at'] == '2026-04-24T12:00:00'

    def test_emergency_banner_appears_in_print_when_active(self, client):
        _set_setting('emergency_active', 'True')
        _set_setting('emergency_reason', 'Flood watch')
        resp = client.get('/api/brief/daily/print')
        assert resp.status_code == 200
        # Printable HTML surfaces the banner + reason text
        assert b'Emergency Mode Active' in resp.data
        assert b'Flood watch' in resp.data

    def test_emergency_string_casing_lenient(self, client):
        """`'true'`, `'True'`, `'TRUE'` all activate the banner (lowercase
        comparison)."""
        for val in ('true', 'True', 'TRUE'):
            _set_setting('emergency_active', val)
            emer = client.get('/api/brief/daily').get_json()['sections']['emergency']
            assert emer['active'] is True, f'failed for value {val!r}'
        # And 'False' / '' / absent all deactivate
        _set_setting('emergency_active', 'False')
        assert client.get('/api/brief/daily').get_json()['sections']['emergency']['active'] is False


# ── NODE NAME / DATE ──────────────────────────────────────────────────────

class TestBriefEnvelope:
    def test_node_name_from_settings(self, client):
        _set_setting('node_name', 'Alpha Node')
        body = client.get('/api/brief/daily').get_json()
        assert body['node_name'] == 'Alpha Node'

    def test_node_name_default_when_unset(self, client):
        body = client.get('/api/brief/daily').get_json()
        assert body['node_name'] == 'NOMAD Node'

    def test_date_is_today(self, client):
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).date().isoformat()
        body = client.get('/api/brief/daily').get_json()
        assert body['date'] == today
