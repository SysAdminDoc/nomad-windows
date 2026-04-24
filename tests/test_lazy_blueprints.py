"""Regression tests for the H-09 / V8-11 lazy blueprint dispatcher.

The dispatcher MUST:
  1. Not import deferred modules during create_app().
  2. Trigger import + register_blueprint exactly once per matching prefix.
  3. Dispatch the triggering request to the now-registered blueprint.
  4. Pass through unrelated paths without side effects.
  5. Tolerate concurrent first-hits without double-registration.
"""

import sys
import threading

import pytest


@pytest.fixture
def fresh_app(monkeypatch):
    """Force a clean import of web.app so deferred-module sys.modules state
    is observable. Restore the prior state on teardown."""
    snapshot = {k: v for k, v in sys.modules.items()
                if k.startswith('web.') or k in ('config', 'db')}
    for key in list(sys.modules):
        if key.startswith('web.') or key in ('config', 'db'):
            del sys.modules[key]
    try:
        from web.app import create_app
        app = create_app()
        yield app
    finally:
        for key in list(sys.modules):
            if key.startswith('web.') or key in ('config', 'db'):
                del sys.modules[key]
        sys.modules.update(snapshot)


def test_deferred_modules_not_imported_during_boot(fresh_app):
    assert 'web.blueprints.platform_security' not in sys.modules
    assert 'web.blueprints.hunting_foraging' not in sys.modules


def test_first_hit_lazy_registers_platform_security(fresh_app):
    client = fresh_app.test_client()
    assert 'platform_security' not in fresh_app.blueprints
    r = client.get('/api/platform/users')
    assert r.status_code == 200
    assert 'platform_security' in fresh_app.blueprints
    assert 'web.blueprints.platform_security' in sys.modules


def test_first_hit_lazy_registers_hunting_foraging(fresh_app):
    client = fresh_app.test_client()
    assert 'hunting_foraging' not in fresh_app.blueprints
    r = client.get('/api/hunting/game/stats')
    assert r.status_code == 200
    assert 'hunting_foraging' in fresh_app.blueprints


def test_second_hit_does_not_double_register(fresh_app):
    client = fresh_app.test_client()
    client.get('/api/platform/users')
    client.get('/api/platform/users')
    # blueprints is a dict keyed by name; double-register would raise on
    # the second call. Confirm only one registration.
    matching = [n for n in fresh_app.blueprints if n == 'platform_security']
    assert len(matching) == 1


def test_unrelated_path_does_not_trigger_load(fresh_app):
    client = fresh_app.test_client()
    r = client.get('/api/i18n/languages')
    assert r.status_code == 200
    # No deferred prefix matched, so neither deferred module should have
    # been imported.
    assert 'web.blueprints.platform_security' not in sys.modules
    assert 'web.blueprints.hunting_foraging' not in sys.modules


def test_concurrent_first_hits_register_exactly_once(fresh_app):
    client = fresh_app.test_client()
    statuses = []
    barrier = threading.Barrier(8)

    def hit():
        barrier.wait()
        r = client.get('/api/platform/users')
        statuses.append(r.status_code)

    threads = [threading.Thread(target=hit) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert all(s == 200 for s in statuses), statuses
    matching = [n for n in fresh_app.blueprints if n == 'platform_security']
    assert len(matching) == 1


def test_prefix_match_is_path_separator_bounded(fresh_app):
    """A request to /api/platformOTHER must NOT match /api/platform."""
    from web.lazy_blueprints import LazyBlueprintDispatcher
    dispatcher = LazyBlueprintDispatcher.__new__(LazyBlueprintDispatcher)
    dispatcher._pending = {'/api/platform': ('mod', 'attr')}
    assert dispatcher._match('/api/platformOTHER') is None
    assert dispatcher._match('/api/platform') == '/api/platform'
    assert dispatcher._match('/api/platform/') == '/api/platform'
    assert dispatcher._match('/api/platform/users') == '/api/platform'
