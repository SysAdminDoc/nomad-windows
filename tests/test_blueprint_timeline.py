"""Smoke tests for the timeline blueprint.

Covers all 4 routes:
  GET /api/timeline            — aggregate events with optional date/type filter
  GET /api/timeline/upcoming   — next N events from today
  GET /api/timeline/overdue    — past-due tasks, maintenance, expired inventory
  GET /api/timeline/summary    — counts: overdue_tasks, expiring_week/month, maint_due_week

Timeline aggregates across 10+ source tables; tests seed only the minimal rows
needed to exercise each source and verify the contract shape.
"""

from datetime import date, timedelta

import pytest
from db import db_session


# ── helpers ──────────────────────────────────────────────────────────────────

def _future(days=30):
    return (date.today() + timedelta(days=days)).isoformat()


def _past(days=10):
    return (date.today() - timedelta(days=days)).isoformat()


def _today():
    return date.today().isoformat()


# ── /api/timeline ─────────────────────────────────────────────────────────────

class TestTimeline:
    def test_empty_returns_valid_envelope(self, client):
        resp = client.get('/api/timeline')
        assert resp.status_code == 200
        body = resp.get_json()
        assert 'events' in body
        assert 'total' in body
        assert body['events'] == []
        assert body['total'] == 0

    def test_inventory_expiration_included(self, client):
        with db_session() as db:
            db.execute(
                "INSERT INTO inventory (name, category, quantity, expiration) VALUES (?,?,?,?)",
                ('Emergency Rice', 'Food', 10, _future(45))
            )
            db.commit()
        resp = client.get(f'/api/timeline?start={_today()}&end={_future(90)}')
        body = resp.get_json()
        events = [e for e in body['events'] if e['type'] == 'expiration']
        assert len(events) >= 1
        evt = events[0]
        assert evt['source'] == 'inventory'
        assert 'Emergency Rice' in evt['title']
        assert evt['severity'] in ('low', 'info', 'warning', 'critical')

    def test_scheduled_task_included(self, client):
        task_date = _future(10)
        with db_session() as db:
            db.execute(
                "INSERT INTO scheduled_tasks (name, next_due, category) VALUES (?,?,?)",
                ('Oil Change', task_date, 'maintenance')
            )
            db.commit()
        resp = client.get(f'/api/timeline?start={_today()}&end={_future(90)}')
        body = resp.get_json()
        tasks = [e for e in body['events'] if e['type'] == 'task']
        assert len(tasks) >= 1
        assert tasks[0]['severity'] in ('low', 'info', 'warning', 'critical')

    def test_vehicle_maintenance_included(self, client):
        maint_date = _future(7)
        with db_session() as db:
            db.execute("INSERT INTO vehicles (name, make, model, year, fuel_type) VALUES (?,?,?,?,?)",
                       ('Tacoma-1', 'Toyota', 'Tacoma', 2018, 'gasoline'))
            vid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute(
                "INSERT INTO vehicle_maintenance (vehicle_id, service_type, next_due_date, status) VALUES (?,?,?,?)",
                (vid, 'Oil Filter', maint_date, 'pending')
            )
            db.commit()
        resp = client.get(f'/api/timeline?start={_today()}&end={_future(90)}')
        body = resp.get_json()
        maint = [e for e in body['events'] if e['type'] == 'maintenance']
        assert len(maint) >= 1
        assert maint[0]['source'] == 'vehicle_maintenance'

    def test_type_filter_returns_only_matching(self, client):
        """Only 'task' events should appear when types=task is set."""
        task_date = _future(5)
        inv_date = _future(15)
        with db_session() as db:
            db.execute(
                "INSERT INTO scheduled_tasks (name, next_due) VALUES (?,?)",
                ('Rotate Supplies', task_date)
            )
            db.execute(
                "INSERT INTO inventory (name, category, quantity, expiration) VALUES (?,?,?,?)",
                ('Water Tabs', 'Water', 20, inv_date)
            )
            db.commit()
        resp = client.get(f'/api/timeline?start={_today()}&end={_future(90)}&types=task')
        body = resp.get_json()
        assert all(e['type'] == 'task' for e in body['events'])

    def test_events_sorted_by_date(self, client):
        """Events must be in ascending date order."""
        with db_session() as db:
            db.execute(
                "INSERT INTO scheduled_tasks (name, next_due) VALUES (?,?)",
                ('Later Task', _future(60))
            )
            db.execute(
                "INSERT INTO scheduled_tasks (name, next_due) VALUES (?,?)",
                ('Early Task', _future(5))
            )
            db.commit()
        resp = client.get(f'/api/timeline?start={_today()}&end={_future(90)}')
        body = resp.get_json()
        dates = [e['date'] for e in body['events']]
        assert dates == sorted(dates)

    def test_date_range_excludes_out_of_range(self, client):
        """Events outside the start/end window should not appear."""
        with db_session() as db:
            db.execute(
                "INSERT INTO inventory (name, category, quantity, expiration) VALUES (?,?,?,?)",
                ('Far Future Can', 'Food', 5, _future(365))
            )
            db.commit()
        # Narrow window: only next 30 days
        resp = client.get(f'/api/timeline?start={_today()}&end={_future(30)}')
        body = resp.get_json()
        titles = [e.get('title', '') for e in body['events']]
        assert not any('Far Future Can' in t for t in titles)

    def test_fuel_expiration_included(self, client):
        fuel_date = _future(20)
        with db_session() as db:
            db.execute(
                "INSERT INTO fuel_storage (fuel_type, quantity, expires) VALUES (?,?,?)",
                ('Gasoline', 25.0, fuel_date)
            )
            db.commit()
        resp = client.get(f'/api/timeline?start={_today()}&end={_future(90)}')
        body = resp.get_json()
        fuel = [e for e in body['events'] if e['type'] == 'fuel_expiration']
        assert len(fuel) >= 1
        assert 'Gasoline' in fuel[0]['title']


# ── /api/timeline/upcoming ────────────────────────────────────────────────────

class TestTimelineUpcoming:
    def test_empty_db_returns_empty_list(self, client):
        resp = client.get('/api/timeline/upcoming')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['events'] == []
        assert body['total'] == 0

    def test_returns_future_tasks(self, client):
        with db_session() as db:
            db.execute(
                "INSERT INTO scheduled_tasks (name, next_due) VALUES (?,?)",
                ('Next Task', _future(3))
            )
            db.commit()
        resp = client.get('/api/timeline/upcoming?limit=10')
        body = resp.get_json()
        assert body['total'] >= 1

    def test_limit_parameter_respected(self, client):
        with db_session() as db:
            for i in range(5):
                db.execute(
                    "INSERT INTO scheduled_tasks (name, next_due) VALUES (?,?)",
                    (f'Task {i}', _future(i + 1))
                )
            db.commit()
        resp = client.get('/api/timeline/upcoming?limit=2')
        body = resp.get_json()
        assert len(body['events']) <= 2

    def test_results_sorted_ascending(self, client):
        with db_session() as db:
            db.execute(
                "INSERT INTO scheduled_tasks (name, next_due) VALUES (?,?)",
                ('Task A', _future(10))
            )
            db.execute(
                "INSERT INTO scheduled_tasks (name, next_due) VALUES (?,?)",
                ('Task B', _future(3))
            )
            db.commit()
        resp = client.get('/api/timeline/upcoming?limit=50')
        body = resp.get_json()
        dates = [e['date'] for e in body['events']]
        assert dates == sorted(dates)

    def test_past_events_excluded(self, client):
        """Only future events (today+) should appear."""
        with db_session() as db:
            db.execute(
                "INSERT INTO scheduled_tasks (name, next_due) VALUES (?,?)",
                ('Past Task', _past(5))
            )
            db.commit()
        resp = client.get('/api/timeline/upcoming?limit=50')
        body = resp.get_json()
        titles = [e.get('title', '') for e in body['events']]
        assert 'Past Task' not in titles


# ── /api/timeline/overdue ─────────────────────────────────────────────────────

class TestTimelineOverdue:
    def test_empty_returns_empty(self, client):
        resp = client.get('/api/timeline/overdue')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['events'] == []

    def test_overdue_task_returned(self, client):
        with db_session() as db:
            db.execute(
                "INSERT INTO scheduled_tasks (name, next_due, category) VALUES (?,?,?)",
                ('Overdue Check', _past(3), 'safety')
            )
            db.commit()
        resp = client.get('/api/timeline/overdue')
        body = resp.get_json()
        overdue = [e for e in body['events'] if e['type'] == 'task_overdue']
        assert len(overdue) >= 1
        assert overdue[0]['severity'] == 'critical'
        assert 'Overdue Check' in overdue[0]['title']

    def test_expired_inventory_in_stock_returned(self, client):
        with db_session() as db:
            db.execute(
                "INSERT INTO inventory (name, category, quantity, expiration) VALUES (?,?,?,?)",
                ('Expired Tuna', 'Food', 3, _past(5))
            )
            db.commit()
        resp = client.get('/api/timeline/overdue')
        body = resp.get_json()
        expired = [e for e in body['events'] if e['type'] == 'expired_inventory']
        assert len(expired) >= 1
        assert 'Expired Tuna' in expired[0]['title']
        assert expired[0]['severity'] == 'critical'

    def test_overdue_maintenance_returned(self, client):
        with db_session() as db:
            db.execute("INSERT INTO vehicles (name, make, model, year, fuel_type) VALUES (?,?,?,?,?)",
                       ('F150-1', 'Ford', 'F-150', 2015, 'gasoline'))
            vid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute(
                "INSERT INTO vehicle_maintenance (vehicle_id, service_type, next_due_date, status) VALUES (?,?,?,?)",
                (vid, 'Brake Pads', _past(14), 'pending')
            )
            db.commit()
        resp = client.get('/api/timeline/overdue')
        body = resp.get_json()
        maint = [e for e in body['events'] if e['type'] == 'maintenance_overdue']
        assert len(maint) >= 1

    def test_future_tasks_not_in_overdue(self, client):
        with db_session() as db:
            db.execute(
                "INSERT INTO scheduled_tasks (name, next_due) VALUES (?,?)",
                ('Future Task', _future(10))
            )
            db.commit()
        resp = client.get('/api/timeline/overdue')
        body = resp.get_json()
        titles = [e.get('title', '') for e in body['events']]
        assert 'Future Task' not in titles

    def test_zero_quantity_expired_inventory_excluded(self, client):
        """Expired items with quantity=0 should not appear (nothing left to worry about)."""
        with db_session() as db:
            db.execute(
                "INSERT INTO inventory (name, category, quantity, expiration) VALUES (?,?,?,?)",
                ('Gone Item', 'Food', 0, _past(2))
            )
            db.commit()
        resp = client.get('/api/timeline/overdue')
        body = resp.get_json()
        titles = [e.get('title', '') for e in body['events']]
        assert not any('Gone Item' in t for t in titles)


# ── /api/timeline/summary ─────────────────────────────────────────────────────

class TestTimelineSummary:
    def test_returns_expected_keys(self, client):
        resp = client.get('/api/timeline/summary')
        assert resp.status_code == 200
        body = resp.get_json()
        for key in ('overdue_tasks', 'expiring_this_week', 'expiring_this_month',
                    'maintenance_due_this_week'):
            assert key in body, f"Missing key: {key}"

    def test_counts_zero_on_empty_db(self, client):
        resp = client.get('/api/timeline/summary')
        body = resp.get_json()
        assert body['overdue_tasks'] == 0
        assert body['expiring_this_week'] == 0
        assert body['expiring_this_month'] == 0
        assert body['maintenance_due_this_week'] == 0

    def test_overdue_task_count(self, client):
        with db_session() as db:
            db.execute(
                "INSERT INTO scheduled_tasks (name, next_due) VALUES (?,?)",
                ('Overdue One', _past(1))
            )
            db.execute(
                "INSERT INTO scheduled_tasks (name, next_due) VALUES (?,?)",
                ('Overdue Two', _past(2))
            )
            db.commit()
        resp = client.get('/api/timeline/summary')
        body = resp.get_json()
        assert body['overdue_tasks'] >= 2

    def test_expiring_this_week_count(self, client):
        with db_session() as db:
            db.execute(
                "INSERT INTO inventory (name, category, quantity, expiration) VALUES (?,?,?,?)",
                ('Soon Item', 'Food', 2, _future(3))
            )
            db.commit()
        resp = client.get('/api/timeline/summary')
        body = resp.get_json()
        assert body['expiring_this_week'] >= 1
        assert body['expiring_this_month'] >= 1

    def test_maintenance_due_this_week_count(self, client):
        with db_session() as db:
            db.execute("INSERT INTO vehicles (name, make, model, year, fuel_type) VALUES (?,?,?,?,?)",
                       ('Wrangler-1', 'Jeep', 'Wrangler', 2019, 'gasoline'))
            vid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute(
                "INSERT INTO vehicle_maintenance (vehicle_id, service_type, next_due_date, status) VALUES (?,?,?,?)",
                (vid, 'Timing Belt', _future(4), 'pending')
            )
            db.commit()
        resp = client.get('/api/timeline/summary')
        body = resp.get_json()
        assert body['maintenance_due_this_week'] >= 1
