"""Regression tests pinning the SSE-broadcast fix in emergency + family.

Prior to this iteration both modules had
    from web.app import _broadcast_event
which raised ImportError (the symbol never existed). A broad try/except
in the `_broadcast` helper silently swallowed the failure, so Emergency
mode and Family check-in SSE events never reached any connected client.
The fix imports `broadcast_event` from `web.state` directly.
"""

import queue
import re

import pytest

from web.blueprints import emergency, family
from web.state import _sse_clients, _sse_lock


def _drain(q):
    out = []
    try:
        while True:
            out.append(q.get_nowait())
    except queue.Empty:
        pass
    return out


@pytest.fixture
def sse_client():
    q = queue.Queue(maxsize=16)
    with _sse_lock:
        _sse_clients.append(q)
    try:
        yield q
    finally:
        with _sse_lock:
            if q in _sse_clients:
                _sse_clients.remove(q)


def test_emergency_broadcast_reaches_sse_client(sse_client):
    emergency._broadcast('alert', {'level': 'critical', 'message': 'test'})
    msgs = _drain(sse_client)
    assert msgs, 'emergency._broadcast must deliver to SSE clients (was a silent no-op before the import fix)'
    assert any('"test"' in m for m in msgs)


def test_family_broadcast_reaches_sse_client(sse_client):
    family._broadcast('family_checkin', {'member': 'alice', 'status': 'ok'})
    msgs = _drain(sse_client)
    assert msgs, 'family._broadcast must deliver to SSE clients (was a silent no-op before the import fix)'
    assert any('"alice"' in m for m in msgs)


def test_broadcast_sse_event_type_is_sanitized(sse_client):
    """Control-char injection into the event type should not break the stream."""
    emergency._broadcast('alert\nX-Smuggle: yes', {'x': 1})
    msgs = _drain(sse_client)
    # The sanitizer strips the newline injection; the event line must still
    # parse as a single SSE event (exactly one 'event:' header per message).
    assert msgs
    for m in msgs:
        assert m.count('event:') == 1
        assert '\nX-Smuggle' not in m


def test_neither_module_imports_the_dead_symbol():
    """Guards against reintroducing `from web.app import _broadcast_event`."""
    import inspect

    def _non_comment_lines(src):
        out = []
        for line in src.splitlines():
            stripped = line.lstrip()
            if stripped.startswith('#'):
                continue
            # Strip inline trailing comments so `from foo import bar  # baz` still counts
            if '#' in stripped and not stripped.startswith(('"', "'")):
                stripped = stripped.split('#', 1)[0]
            out.append(stripped)
        return '\n'.join(out)

    for fn in (emergency._broadcast, family._broadcast):
        body = _non_comment_lines(inspect.getsource(fn))
        assert 'from web.app import _broadcast_event' not in body, (
            f'{fn.__module__}.{fn.__name__} reintroduced the dead import'
        )
        assert 'from web.state import broadcast_event' in body, (
            f'{fn.__module__}.{fn.__name__} must import broadcast_event from web.state'
        )
