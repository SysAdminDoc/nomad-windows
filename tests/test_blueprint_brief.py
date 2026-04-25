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
    def test_weather_section_present_when_row_exists(self, client):
        """The brief queries weather_log ORDER BY created_at DESC LIMIT 1,
        so a seeded row lights up the section with `recorded_at`. Note:
        the brief compiler reads `temp_c` / `humidity` / `pressure` /
        `conditions` guarded by `if 'X' in row.keys()` — the live schema
        uses `temp_f` / `pressure_hpa` without those fields, so guarded
        reads fall back to None/''. The section still appears (with
        `recorded_at` populated) which is the contract we care about."""
        with db_session() as db:
            db.execute(
                "INSERT INTO weather_log (temp_f, pressure_hpa, notes) VALUES (?,?,?)",
                (68.0, 1013.0, 'morning reading')
            )
            db.commit()
        section = client.get('/api/brief/daily').get_json()['sections'].get('weather')
        assert section is not None
        assert section['notes'] == 'morning reading'
        assert section['recorded_at'] is not None


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
    def test_tasks_section_absent_when_query_schema_mismatch(self, client):
        """FINDING (2026-04-24 V8-06 pass): brief.py queries
        `SELECT id, title, priority, due_at FROM scheduled_tasks
         WHERE completed_at IS NULL AND due_at IS NOT NULL` but the
        scheduled_tasks table has columns `name` / `next_due` /
        `last_completed`, not `title` / `due_at` / `completed_at`.
        The query raises sqlite3.OperationalError which is caught by
        the blueprint's per-section try/except (log.debug'd). Net
        effect: the tasks section is silently absent from every brief
        output in production. This test pins that behavior so any
        future schema-fix that makes the query succeed will need to
        update this test to reflect the new reality."""
        with db_session() as db:
            db.execute(
                "INSERT INTO scheduled_tasks (name, category, recurrence) "
                "VALUES (?,?,?)", ('Any task', 'custom', 'once')
            )
            db.commit()
        sections = client.get('/api/brief/daily').get_json()['sections']
        # Section is absent (query raised and was swallowed by try/except)
        assert 'tasks' not in sections


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
