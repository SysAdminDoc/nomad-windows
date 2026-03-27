"""Shared fixtures for Project N.O.M.A.D. API tests."""

import os
import sys
import tempfile

import pytest

# Ensure project root is on sys.path so imports work
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture()
def app():
    """Create a Flask app backed by a temporary SQLite database."""
    db_dir = tempfile.mkdtemp(prefix='nomad_test_')

    # Point config at temp directory before any imports touch it
    import config
    config._config_cache = {'data_dir': db_dir}
    config._config_mtime = float('inf')  # prevent re-read from disk

    original_get_data_dir = config.get_data_dir
    config.get_data_dir = lambda: db_dir

    # Initialize the DB schema in the temp directory
    from db import init_db
    init_db()

    # Create the Flask app
    from web.app import create_app
    application = create_app()
    application.config['TESTING'] = True

    yield application

    # Restore
    config.get_data_dir = original_get_data_dir
    # Cleanup temp dir
    import shutil
    shutil.rmtree(db_dir, ignore_errors=True)


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
