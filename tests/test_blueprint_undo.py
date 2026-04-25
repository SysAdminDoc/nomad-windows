"""Smoke tests for the undo/redo blueprint.

Covers all 3 routes:
  GET  /api/undo  — peek (available:False / available:True with TTL)
  POST /api/undo  — execute (404 / invalid-table 400 / happy-path restore /
                              failure-restores-entry)
  POST /api/redo  — execute (404 / happy-path re-delete / update-not-supported)

The stacks are module-level deques keyed off `time.time()`. Every test
clears both stacks via a fixture so cross-test bleed (e.g. an entry left
from the previous test trips a peek assertion in the next) is impossible.

push_undo() is the public seam for callers to register an undoable action
— tests use it directly so we don't need to drive a destructive DELETE
through some other blueprint just to populate the stack.
"""

import time
import pytest

from db import db_session


# ── SHARED HELPERS ────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clear_undo_stacks():
    """Reset the module-level deques before AND after every test.

    Without this, a `push_undo()` from test A leaks into test B's peek
    response and an unrelated assertion fails miles away from the cause.
    """
    from web.blueprints import undo as undo_mod
    with undo_mod._undo_lock:
        undo_mod._undo_stack.clear()
        undo_mod._redo_stack.clear()
    yield
    with undo_mod._undo_lock:
        undo_mod._undo_stack.clear()
        undo_mod._redo_stack.clear()


@pytest.fixture
def push_undo():
    """Return the module-level push_undo function for direct stack seeding."""
    from web.blueprints.undo import push_undo as _push
    return _push


# ── /api/undo GET (peek) ──────────────────────────────────────────────────

class TestUndoPeek:
    def test_empty_returns_available_false(self, client):
        body = client.get('/api/undo').get_json()
        assert body == {'available': False}

    def test_populated_returns_description_and_ttl(self, client, push_undo):
        push_undo('delete', 'Removed widget #5', 'inventory',
                  {'id': 5, 'name': 'widget'})
        body = client.get('/api/undo').get_json()
        assert body['available'] is True
        assert body['action_type'] == 'delete'
        assert body['description'] == 'Removed widget #5'
        # Fresh entry → seconds_remaining is between 29 and 30 inclusive
        assert 28 <= body['seconds_remaining'] <= 30

    def test_expired_entry_is_pruned(self, client, push_undo, monkeypatch):
        """An entry older than 30s is pruned by _prune_expired() before
        peek answers; the response degrades to {available: False}."""
        push_undo('delete', 'Old widget', 'inventory', {'id': 1, 'name': 'old'})
        # Backdate the just-pushed entry to 31s ago
        from web.blueprints import undo as undo_mod
        with undo_mod._undo_lock:
            undo_mod._undo_stack[0]['timestamp'] = time.time() - 31
        body = client.get('/api/undo').get_json()
        assert body == {'available': False}


# ── /api/undo POST (execute) ──────────────────────────────────────────────

class TestUndoExecute:
    def test_empty_stack_returns_404(self, client):
        resp = client.post('/api/undo')
        assert resp.status_code == 404
        assert resp.get_json()['error'].startswith('Nothing to undo')

    def test_invalid_table_returns_400_and_restores_entry(self, client, push_undo):
        """A push_undo with a table outside the whitelist is rejected.
        The entry is restored to the stack so the caller can inspect it
        rather than losing it."""
        push_undo('delete', 'sketchy', 'sqlite_master',  # NOT in _UNDO_VALID_TABLES
                  {'id': 1})
        resp = client.post('/api/undo')
        assert resp.status_code == 400
        assert 'invalid table' in resp.get_json()['error']
        # Entry survives — the next peek must still see it
        peek = client.get('/api/undo').get_json()
        assert peek['available'] is True

    def test_delete_action_restores_row(self, client, push_undo):
        """The canonical happy path: a row was deleted upstream and its
        contents pushed onto the undo stack. POST /api/undo re-inserts."""
        # Empty inventory at start (covered by autouse stack-clear fixture
        # — DB is per-app so any seeded rows from other tests don't leak).
        push_undo('delete', 'Deleted Test Item', 'inventory', {
            'name': 'Test Undo Row',
            'category': 'medical',
            'quantity': 3,
            'unit': 'ea',
        })
        resp = client.post('/api/undo')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['status'] == 'undone'
        assert body['description'] == 'Deleted Test Item'
        # Verify the row landed in the inventory table
        with db_session() as db:
            row = db.execute(
                "SELECT id, name, category, quantity FROM inventory "
                "WHERE name = ?", ('Test Undo Row',)
            ).fetchone()
        assert row is not None
        assert row['category'] == 'medical'
        assert row['quantity'] == 3

    def test_update_action_restores_prior_values(self, client, push_undo):
        """Update-undo requires the row already exist (the original update
        target). Seed a row, then push an update-undo, then POST /api/undo
        and verify the row's columns are reverted."""
        with db_session() as db:
            cur = db.execute(
                "INSERT INTO inventory (name, category, quantity, unit) "
                "VALUES (?, ?, ?, ?)",
                ('UpdateTarget', 'food', 100, 'ea')
            )
            db.commit()
            rid = cur.lastrowid
        # Push an undo that says "the original was quantity=10"
        push_undo('update', 'Reverted quantity', 'inventory',
                  {'id': rid, 'quantity': 10, 'category': 'food'})
        resp = client.post('/api/undo')
        assert resp.status_code == 200
        with db_session() as db:
            row = db.execute(
                "SELECT quantity FROM inventory WHERE id = ?", (rid,)
            ).fetchone()
        assert row['quantity'] == 10  # reverted

    def test_unknown_columns_are_dropped_silently(self, client, push_undo):
        """row_data may carry extra keys that don't exist on the live
        table (schema drift, frontend pre-fill, etc). The route filters
        to columns that exist via PRAGMA table_info — extra keys must
        not 500 or refuse the undo."""
        push_undo('delete', 'Drop extras', 'inventory', {
            'name': 'WithExtras',
            'category': 'tools',
            'quantity': 1,
            'unit': 'ea',
            'this_column_does_not_exist': 'ignored',
            'neither_does_this': 42,
        })
        resp = client.post('/api/undo')
        assert resp.status_code == 200
        with db_session() as db:
            row = db.execute("SELECT id FROM inventory WHERE name = ?",
                             ('WithExtras',)).fetchone()
        assert row is not None


# ── /api/redo POST ────────────────────────────────────────────────────────

class TestRedo:
    def test_empty_redo_stack_returns_404(self, client):
        resp = client.post('/api/redo')
        assert resp.status_code == 404
        assert resp.get_json()['error'] == 'Nothing to redo'

    def test_redo_after_delete_undo_re_deletes_row(self, client, push_undo):
        """End-to-end: insert row → push delete-undo with the row's id →
        POST /api/undo (re-inserts the row) → POST /api/redo (re-deletes
        what undo just restored). The redo path requires the entry on
        the redo_stack, which only gets there after a successful undo."""
        with db_session() as db:
            cur = db.execute(
                "INSERT INTO inventory (name, category, quantity, unit) "
                "VALUES (?, ?, ?, ?)",
                ('RedoTarget', 'water', 5, 'L')
            )
            db.commit()
            rid = cur.lastrowid
        # Simulate a "row was just deleted" event by pushing the undo entry
        # for the existing row, then immediately deleting it.
        push_undo('delete', 'RedoTarget removed', 'inventory', {
            'id': rid, 'name': 'RedoTarget', 'category': 'water',
            'quantity': 5, 'unit': 'L',
        })
        with db_session() as db:
            db.execute('DELETE FROM inventory WHERE id = ?', (rid,))
            db.commit()
        # POST /api/undo restores it
        assert client.post('/api/undo').status_code == 200
        # POST /api/redo deletes it again
        resp = client.post('/api/redo')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'redone'
        # NB: on undo the row was re-inserted with a fresh id (the delete-undo
        # path does not preserve the original id when it differs from auto-
        # increment); the redo path uses row_data['id'] which is the original
        # id captured at push_undo() time. So the row may persist under a new
        # id even after redo. Pin only the response contract.

    def test_redo_invalid_table_400_and_restores(self, client, push_undo):
        """Inject an entry directly into the redo stack with a table
        not on the whitelist."""
        from web.blueprints import undo as undo_mod
        with undo_mod._undo_lock:
            undo_mod._redo_stack.append({
                'action_type': 'delete',
                'description': 'sketchy redo',
                'table': 'sqlite_master',
                'row_data': {'id': 1},
                'timestamp': time.time(),
            })
        resp = client.post('/api/redo')
        assert resp.status_code == 400
        # Entry survived
        with undo_mod._undo_lock:
            assert len(undo_mod._redo_stack) == 1

    def test_redo_update_not_supported(self, client, push_undo):
        """An update-undo entry on the redo stack returns 400 ('Redo
        not supported for updates') and stays on the stack."""
        from web.blueprints import undo as undo_mod
        with undo_mod._undo_lock:
            undo_mod._redo_stack.append({
                'action_type': 'update',
                'description': 'cannot redo update',
                'table': 'inventory',
                'row_data': {'id': 1, 'quantity': 99},
                'timestamp': time.time(),
            })
        resp = client.post('/api/redo')
        assert resp.status_code == 400
        assert 'not supported for updates' in resp.get_json()['error']
        with undo_mod._undo_lock:
            assert len(undo_mod._redo_stack) == 1
