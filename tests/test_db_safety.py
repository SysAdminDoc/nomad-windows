"""Focused regression tests for DB connection setup safety."""

import sqlite3
from types import SimpleNamespace
import sys

import pytest


class _FakeConn:
    def __init__(self, fail_on_execute=False):
        self.fail_on_execute = fail_on_execute
        self.closed = False
        self.row_factory = None
        self.executed = []

    def execute(self, sql):
        self.executed.append(sql)
        if self.fail_on_execute:
            raise RuntimeError('pragma failed')
        return None

    def close(self):
        self.closed = True


class _RaceAwareMigrationConn:
    def __init__(self, inner, filename):
        self._inner = inner
        self._filename = filename
        self._injected = False

    def execute(self, sql, params=()):
        normalized = ' '.join(sql.strip().split())
        if normalized.startswith('INSERT OR IGNORE INTO _migrations') and not self._injected:
            self._inner.execute('INSERT INTO _migrations (filename) VALUES (?)', (self._filename,))
            self._inner.commit()
            self._injected = True
        return self._inner.execute(sql, params)

    def executescript(self, sql):
        return self._inner.executescript(sql)

    def commit(self):
        return self._inner.commit()

    def rollback(self):
        return self._inner.rollback()


def test_get_db_closes_connection_if_setup_fails(monkeypatch, tmp_path):
    import db

    fake = _FakeConn(fail_on_execute=True)
    monkeypatch.setattr(db, 'get_db_path', lambda: str(tmp_path / 'nomad.db'))
    monkeypatch.setattr(db.sqlite3, 'connect', lambda *args, **kwargs: fake)
    monkeypatch.setattr(db, '_wal_set', False)

    with pytest.raises(RuntimeError, match='pragma failed'):
        db.get_db()

    assert fake.closed is True


def test_get_db_keeps_connection_open_if_flask_context_binding_fails(monkeypatch, tmp_path):
    import db

    fake = _FakeConn()

    class _BrokenG:
        def __setattr__(self, name, value):
            raise RuntimeError('no flask context binding')

    fake_flask = SimpleNamespace(g=_BrokenG(), has_app_context=lambda: True)

    monkeypatch.setattr(db, 'get_db_path', lambda: str(tmp_path / 'nomad.db'))
    monkeypatch.setattr(db.sqlite3, 'connect', lambda *args, **kwargs: fake)
    monkeypatch.setitem(sys.modules, 'flask', fake_flask)
    # Reset WAL flag so the pragma executes in this test
    monkeypatch.setattr(db, '_wal_set', False)

    conn = db.get_db()

    assert conn is fake
    assert fake.closed is False
    assert fake.executed == ['PRAGMA journal_mode=WAL', 'PRAGMA foreign_keys=ON']


def test_apply_migrations_tolerates_filename_being_recorded_mid_run(monkeypatch, tmp_path):
    import db

    migration = tmp_path / '001_test_race.sql'
    migration.write_text('CREATE TABLE IF NOT EXISTS migration_race_probe (id INTEGER PRIMARY KEY);', encoding='utf-8')

    monkeypatch.setattr(db, '_get_migrations_dir', lambda: str(tmp_path))

    inner = sqlite3.connect(':memory:')
    proxy = _RaceAwareMigrationConn(inner, migration.name)

    db.apply_migrations(proxy)

    rows = inner.execute('SELECT filename FROM _migrations WHERE filename = ?', (migration.name,)).fetchall()
    assert len(rows) == 1
    assert inner.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='migration_race_probe'"
    ).fetchone()
