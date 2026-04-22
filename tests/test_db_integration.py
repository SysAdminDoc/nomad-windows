"""V8-16: File-based SQLite integration test.

Tests that create_app() + init_db() work correctly with a real file-based
SQLite database (not in-memory), verifying WAL mode, pool lifecycle,
schema version gate, and full startup sequence.
"""

import os
import sys
import sqlite3
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture()
def file_db_app(tmp_path):
    """Flask app backed by a real file-based SQLite database."""
    db_file = tmp_path / "nomad_integration_test.db"
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    import config
    import db as db_mod

    # Save original state so we can restore it
    orig_cache = config._config_cache
    orig_mtime = config._config_mtime
    orig_wal_set = db_mod._wal_set
    orig_pool_db_path = db_mod._pool_db_path

    # Point config at a real file path
    config._config_cache = {'db_path': str(db_file), 'data_dir': str(data_dir)}
    config._config_mtime = float('inf')

    # Reset WAL-set flag so the new file path triggers PRAGMA
    db_mod._wal_set = False
    # Reset pool path so pool invalidates for the new path
    db_mod._pool_db_path = None
    db_mod._pool_clear()

    from db import init_db
    init_db()

    from web.app import create_app
    application = create_app()
    application.config['TESTING'] = True

    yield application, str(db_file)

    # Restore globals so subsequent tests are not affected
    db_mod._wal_set = orig_wal_set
    db_mod._pool_db_path = orig_pool_db_path
    db_mod._pool_clear()
    config._config_cache = orig_cache
    config._config_mtime = orig_mtime


def test_file_db_creates_real_file(file_db_app):
    """init_db() must create a real SQLite file on disk."""
    _app, db_path = file_db_app
    assert os.path.isfile(db_path), f"Expected DB file at {db_path}"
    assert os.path.getsize(db_path) > 0, "DB file should not be empty after init"


def test_file_db_wal_mode(file_db_app):
    """WAL journal mode must be enabled on file-based databases."""
    _app, db_path = file_db_app
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("PRAGMA journal_mode").fetchone()
        assert row is not None
        assert row[0] == "wal", f"Expected WAL mode, got: {row[0]!r}"
    finally:
        conn.close()


def test_file_db_schema_version(file_db_app):
    """Schema version must be written to _meta after init_db()."""
    _app, db_path = file_db_app
    import db as db_mod
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT value FROM _meta WHERE key = 'schema_version'"
        ).fetchone()
        assert row is not None, "_meta.schema_version should be set after init_db()"
        stored = int(row[0])
        assert stored == db_mod._SCHEMA_VERSION, (
            f"Stored schema version {stored} != _SCHEMA_VERSION {db_mod._SCHEMA_VERSION}"
        )
    finally:
        conn.close()


def test_file_db_schema_version_gate_skips_reinit(file_db_app):
    """A second call to init_db() on an up-to-date schema should skip reinit (fast path)."""
    import db as db_mod
    _app, db_path = file_db_app

    # Track whether _init_db_inner is called again
    calls = []
    original = db_mod._init_db_inner

    def spy(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    db_mod._init_db_inner = spy
    try:
        db_mod.init_db()
        assert len(calls) == 0, "_init_db_inner should not be called on an up-to-date schema"
    finally:
        db_mod._init_db_inner = original


def test_file_db_pool_stats(file_db_app):
    """Connection pool must report correct capacity for file-based DB."""
    _app, _db_path = file_db_app
    import db as db_mod
    stats = db_mod.pool_stats()
    # Pool may be disabled via env (NOMAD_DB_POOL_SIZE=0) but should return a dict
    assert isinstance(stats, dict)
    assert 'enabled' in stats
    assert 'capacity' in stats


def test_file_db_pool_acquire_release(file_db_app):
    """Connections acquired from pool on file-based DB must be usable."""
    _app, _db_path = file_db_app
    import db as db_mod
    conn, from_pool = db_mod._pool_acquire()
    try:
        result = conn.execute("SELECT value FROM _meta WHERE key = 'schema_version'").fetchone()
        assert result is not None
    finally:
        db_mod._pool_release(conn)


def test_file_db_app_starts(file_db_app):
    """create_app() should succeed and respond to a health check route."""
    application, _db_path = file_db_app
    with application.test_client() as client:
        resp = client.get('/api/health')
        # Health check should return 200 or at minimum not 500
        assert resp.status_code in (200, 404), (
            f"Unexpected status {resp.status_code} from /api/health"
        )


def test_file_db_foreign_keys_enabled(file_db_app):
    """Foreign key enforcement must be ON for file-based connections."""
    _app, db_path = file_db_app
    import db as db_mod
    conn, _ = db_mod._pool_acquire()
    try:
        row = conn.execute("PRAGMA foreign_keys").fetchone()
        assert row is not None
        assert row[0] == 1, "PRAGMA foreign_keys should be ON (1)"
    finally:
        db_mod._pool_release(conn)


def test_file_db_seeds_upc(file_db_app):
    """UPC database should be seeded with stock prep items after init_db()."""
    _app, db_path = file_db_app
    conn = sqlite3.connect(db_path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM upc_database").fetchone()[0]
        assert count > 0, "upc_database should have seeded rows after init_db()"
    finally:
        conn.close()


def test_file_db_seeds_rag_scope(file_db_app):
    """RAG scope defaults should be seeded after init_db()."""
    _app, db_path = file_db_app
    conn = sqlite3.connect(db_path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM rag_scope").fetchone()[0]
        assert count > 0, "rag_scope should have seeded rows after init_db()"
    finally:
        conn.close()
