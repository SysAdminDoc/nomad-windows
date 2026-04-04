"""Focused regression tests for DB connection setup safety."""

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


def test_get_db_closes_connection_if_setup_fails(monkeypatch, tmp_path):
    import db

    fake = _FakeConn(fail_on_execute=True)
    monkeypatch.setattr(db, 'get_db_path', lambda: str(tmp_path / 'nomad.db'))
    monkeypatch.setattr(db.sqlite3, 'connect', lambda *args, **kwargs: fake)

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

    conn = db.get_db()

    assert conn is fake
    assert fake.closed is False
    assert fake.executed == ['PRAGMA journal_mode=WAL', 'PRAGMA foreign_keys=ON']
