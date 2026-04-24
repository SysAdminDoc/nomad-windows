"""File-based SQLite integration test (V8-16).

Complements the shared in-memory fixture in conftest.py by exercising
`init_db()` and `create_app()` against a real file-backed SQLite database.
Verifies WAL journal mode, the connection pool lifecycle, basic schema
integrity, and application startup against a fresh .db file.
"""

import os
import sys
import shutil
import sqlite3
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture()
def file_backed_app():
    """Create a Flask app backed by a real on-disk SQLite file."""
    tmp_dir = tempfile.mkdtemp(prefix='nomad_file_db_')
    db_path = os.path.join(tmp_dir, 'nomad.db')
    data_dir = os.path.join(tmp_dir, 'data')
    os.makedirs(data_dir, exist_ok=True)

    import config
    prev_cache = getattr(config, '_config_cache', None)
    prev_mtime = getattr(config, '_config_mtime', None)
    config._config_cache = {'db_path': db_path, 'data_dir': data_dir}
    try:
        config._config_mtime = os.path.getmtime(config.get_config_path())
    except OSError:
        config._config_mtime = 0

    import db as db_module
    prev_wal_set = db_module._wal_set
    prev_pool_db_path = db_module._pool_db_path
    db_module._wal_set = False
    db_module._pool_db_path = None
    if db_module._pool is not None:
        db_module._pool_clear()

    try:
        from db import init_db
        init_db()

        from web.app import create_app
        application = create_app()
        application.config['TESTING'] = True

        yield application, Path(db_path)
    finally:
        if db_module._pool is not None:
            db_module._pool_clear()
        db_module._wal_set = prev_wal_set
        db_module._pool_db_path = prev_pool_db_path
        config._config_cache = prev_cache
        config._config_mtime = prev_mtime
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_db_file_created(file_backed_app):
    """init_db() materializes the on-disk SQLite file."""
    _, db_path = file_backed_app
    assert db_path.exists(), f'expected {db_path} to exist after init_db()'
    assert db_path.stat().st_size > 0, 'expected non-empty DB file'


def test_wal_mode_active(file_backed_app):
    """WAL journal mode is applied and persists on the file."""
    _, db_path = file_backed_app
    conn = sqlite3.connect(str(db_path))
    try:
        mode = conn.execute('PRAGMA journal_mode').fetchone()[0]
    finally:
        conn.close()
    assert mode.lower() == 'wal', f'expected WAL journal mode, got {mode!r}'


def test_core_tables_exist(file_backed_app):
    """Key tables that underpin app startup are present after init_db()."""
    _, db_path = file_backed_app
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        tables = {r[0] for r in rows}
    finally:
        conn.close()

    # A small sentinel set — breadth of migrations is validated elsewhere.
    expected = {'settings', 'inventory', 'notes', 'contacts', 'waypoints'}
    missing = expected - tables
    assert not missing, f'missing core tables: {missing}'
    assert len(tables) > 50, (
        f'expected 50+ tables on a fully migrated DB, got {len(tables)}'
    )


def test_schema_version_set(file_backed_app):
    """`_meta.schema_version` is populated by init_db() (V8-01)."""
    _, db_path = file_backed_app
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT value FROM _meta WHERE key = 'schema_version'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None, "expected _meta.schema_version row after init_db()"
    assert int(row[0]) > 0, "schema_version must be a positive integer"


def test_app_root_responds(file_backed_app):
    """Smoke test: app responds on `/` against a file-backed DB."""
    application, _ = file_backed_app
    client = application.test_client()
    resp = client.get('/')
    assert resp.status_code == 200, (
        f'root route returned {resp.status_code} on file-backed DB'
    )


def test_connection_pool_survives_multiple_requests(file_backed_app):
    """Pool-backed get_db() returns working connections across requests."""
    application, _ = file_backed_app
    client = application.test_client()
    for _ in range(5):
        resp = client.get('/api/inventory?limit=1')
        # 200 is normal, 401 is acceptable if LAN auth is enforced in the
        # test env. What matters is that the app didn't 500 on pool reuse.
        assert resp.status_code in (200, 401), (
            f'unexpected status {resp.status_code} under pool reuse'
        )
