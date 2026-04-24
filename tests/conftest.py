"""Shared fixtures for NOMAD Field Desk API tests."""

import os
import sys
import uuid
import shutil
from pathlib import Path

import pytest

# Ensure project root is on sys.path so imports work
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

TEST_TMP_ROOT = Path(PROJECT_ROOT) / "test_runtime"
TEST_TMP_ROOT.mkdir(exist_ok=True)

@pytest.fixture()
def app():
    """Create a Flask app backed by a temporary SQLite database."""
    db_uri = f'file:nomad_test_{uuid.uuid4().hex}?mode=memory&cache=shared'
    data_dir = TEST_TMP_ROOT / f'nomad_data_{uuid.uuid4().hex}'
    data_dir.mkdir()
    keeper = None

    # Point config at temp directory before any imports touch it
    import config
    config._config_cache = {'db_path': db_uri, 'data_dir': str(data_dir)}
    try:
        config._config_mtime = os.path.getmtime(config.get_config_path())
    except OSError:
        config._config_mtime = 0

    # Keep one connection open so the shared in-memory database persists
    import sqlite3
    keeper = sqlite3.connect(db_uri, uri=True)

    # Initialize the DB schema in the shared in-memory database
    from db import init_db
    init_db()

    # Create the Flask app
    from web.app import create_app
    application = create_app()
    application.config['TESTING'] = True

    yield application

    if keeper is not None:
        keeper.close()
    shutil.rmtree(data_dir, ignore_errors=True)


@pytest.fixture()
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture()
def db(app):
    """Direct DB connection for seeding test data."""
    from db import get_db
    conn = get_db()
    yield conn
    conn.close()


# ─── V8-23: Explicit seed fixtures ───────────────────────────────────────────
# Tests that need seeded rows should declare these fixtures explicitly rather
# than relying on init_db() side-effects. This makes data dependencies visible
# in the test signature.

@pytest.fixture()
def seed_upc_entry(db):
    """Insert a single known UPC entry for tests that exercise UPC lookup.

    Returns the inserted row as a dict with keys: upc, name, category, brand,
    size, unit, default_shelf_life_days.
    """
    entry = {
        'upc': '000000000001',
        'name': 'Test Item',
        'category': 'Test',
        'brand': 'TestBrand',
        'size': '1 oz',
        'unit': 'each',
        'default_shelf_life_days': 365,
    }
    db.execute(
        '''INSERT OR IGNORE INTO upc_database
           (upc, name, category, brand, size, unit, default_shelf_life_days)
           VALUES (:upc, :name, :category, :brand, :size, :unit, :default_shelf_life_days)''',
        entry,
    )
    db.commit()
    return entry


@pytest.fixture()
def seed_rag_scope_row(db):
    """Insert a single known rag_scope row for tests that exercise RAG context.

    Returns the inserted row as a dict with keys matching the rag_scope schema.
    """
    import json
    row = {
        'table_name': '_test_rag_table',
        'label': 'Test RAG Table',
        'enabled': 1,
        'weight': 1,
        'max_rows': 10,
        'formatter': 'default',
        'columns_json': json.dumps(['id', 'name']),
        'source': 'test',
    }
    db.execute(
        '''INSERT OR IGNORE INTO rag_scope
           (table_name, label, enabled, weight, max_rows, formatter, columns_json, source)
           VALUES (:table_name, :label, :enabled, :weight, :max_rows,
                   :formatter, :columns_json, :source)''',
        row,
    )
    db.commit()
    return row


@pytest.fixture()
def assert_upc_seeded(db):
    """Assert that init_db() has seeded the UPC database.

    Use this fixture in tests that need the full seeded UPC set but want to
    declare that dependency explicitly rather than assuming init_db() ran.
    """
    count = db.execute('SELECT COUNT(*) FROM upc_database').fetchone()[0]
    assert count > 0, (
        "upc_database is empty — init_db() seed did not run. "
        "Ensure the 'app' fixture is listed before this fixture."
    )
    return count


@pytest.fixture()
def assert_rag_scope_seeded(db):
    """Assert that init_db() has seeded the rag_scope defaults.

    Use this fixture in tests that need the full default RAG scope rows but
    want to declare that dependency explicitly.
    """
    count = db.execute('SELECT COUNT(*) FROM rag_scope').fetchone()[0]
    assert count > 0, (
        "rag_scope is empty — init_db() seed did not run. "
        "Ensure the 'app' fixture is listed before this fixture."
    )
    return count
