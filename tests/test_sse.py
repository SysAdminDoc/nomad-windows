"""Tests for SSE (Server-Sent Events) event bus."""

import queue
import threading
import time


class TestSSEEndpoint:
    def test_event_stream_content_type(self, client):
        # SSE endpoint streams indefinitely; buffered=False prevents the test
        # client from trying to consume the entire response body.
        resp = client.get('/api/events/stream', buffered=False)
        try:
            assert resp.content_type.startswith('text/event-stream')
        finally:
            resp.close()

    def test_event_test_endpoint(self, client):
        resp = client.get('/api/events/test')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'sent'
        assert 'clients' in data

    def test_event_test_reports_client_count(self, client):
        resp = client.get('/api/events/test')
        data = resp.get_json()
        assert isinstance(data['clients'], int)


class TestSSEClientLimit:
    def test_max_sse_clients_constant(self, app):
        from web.state import MAX_SSE_CLIENTS
        assert MAX_SSE_CLIENTS == 20

    def test_sse_429_when_at_capacity(self, app):
        from web.state import _sse_clients, _sse_lock, MAX_SSE_CLIENTS
        client = app.test_client()
        # Fill up the SSE client list
        fake_queues = []
        with _sse_lock:
            for _ in range(MAX_SSE_CLIENTS):
                q = queue.Queue(maxsize=50)
                _sse_clients.append(q)
                fake_queues.append(q)
        try:
            resp = client.get('/api/events/stream')
            assert resp.status_code == 429
            data = resp.get_json()
            assert 'error' in data
        finally:
            with _sse_lock:
                for q in fake_queues:
                    if q in _sse_clients:
                        _sse_clients.remove(q)


class TestBroadcastEvent:
    def test_broadcast_event_sends_to_queue(self, app):
        from web.state import broadcast_event, _sse_clients, _sse_lock
        q = queue.Queue(maxsize=50)
        with _sse_lock:
            _sse_clients.append(q)
        try:
            broadcast_event('test', {'msg': 'hello'})
            msg = q.get_nowait()
            assert 'event: test' in msg
            assert 'hello' in msg
        finally:
            with _sse_lock:
                if q in _sse_clients:
                    _sse_clients.remove(q)

    def test_broadcast_event_multiple_clients(self, app):
        from web.state import broadcast_event, _sse_clients, _sse_lock
        q1 = queue.Queue(maxsize=50)
        q2 = queue.Queue(maxsize=50)
        with _sse_lock:
            _sse_clients.append(q1)
            _sse_clients.append(q2)
        try:
            broadcast_event('alert', {'level': 'info'})
            assert not q1.empty()
            assert not q2.empty()
        finally:
            with _sse_lock:
                for q in [q1, q2]:
                    if q in _sse_clients:
                        _sse_clients.remove(q)

    def test_broadcast_removes_full_queues(self, app):
        from web.state import broadcast_event, _sse_clients, _sse_lock
        full_q = queue.Queue(maxsize=1)
        full_q.put('filler')  # fill the queue
        with _sse_lock:
            _sse_clients.append(full_q)
        try:
            broadcast_event('test', {'data': 'overflow'})
            # Full queue should be removed
            with _sse_lock:
                assert full_q not in _sse_clients
        finally:
            with _sse_lock:
                if full_q in _sse_clients:
                    _sse_clients.remove(full_q)


class TestSSEClientLifecycle:
    def test_register_and_unregister_client(self, app):
        from web.state import (
            sse_register_client, sse_unregister_client,
            _sse_clients, _sse_client_last_active, _sse_lock,
        )
        q = queue.Queue(maxsize=50)
        sse_register_client(q)
        try:
            with _sse_lock:
                assert q in _sse_clients
                assert id(q) in _sse_client_last_active
            sse_unregister_client(q)
            with _sse_lock:
                assert q not in _sse_clients
                assert id(q) not in _sse_client_last_active
        finally:
            with _sse_lock:
                if q in _sse_clients:
                    _sse_clients.remove(q)
                _sse_client_last_active.pop(id(q), None)

    def test_touch_updates_timestamp(self, app):
        from web.state import (
            sse_register_client, sse_unregister_client, sse_touch_client,
            _sse_client_last_active, _sse_lock,
        )
        q = queue.Queue(maxsize=50)
        sse_register_client(q)
        try:
            with _sse_lock:
                ts1 = _sse_client_last_active[id(q)]
            time.sleep(0.05)
            sse_touch_client(q)
            with _sse_lock:
                ts2 = _sse_client_last_active[id(q)]
            assert ts2 > ts1
        finally:
            sse_unregister_client(q)

    def test_cleanup_stale_removes_old_clients(self, app):
        from web.state import (
            sse_register_client, sse_cleanup_stale_clients,
            _sse_clients, _sse_client_last_active, _sse_lock,
            SSE_STALE_TIMEOUT,
        )
        q = queue.Queue(maxsize=50)
        sse_register_client(q)
        # Backdate the timestamp to simulate staleness
        with _sse_lock:
            _sse_client_last_active[id(q)] = time.time() - SSE_STALE_TIMEOUT - 10
        removed = sse_cleanup_stale_clients()
        assert removed >= 1
        with _sse_lock:
            assert q not in _sse_clients

    def test_cleanup_keeps_active_clients(self, app):
        from web.state import (
            sse_register_client, sse_unregister_client,
            sse_cleanup_stale_clients, _sse_clients, _sse_lock,
        )
        q = queue.Queue(maxsize=50)
        sse_register_client(q)
        try:
            removed = sse_cleanup_stale_clients()
            assert removed == 0
            with _sse_lock:
                assert q in _sse_clients
        finally:
            sse_unregister_client(q)

    def test_unregister_idempotent(self, app):
        from web.state import sse_register_client, sse_unregister_client
        q = queue.Queue(maxsize=50)
        sse_register_client(q)
        sse_unregister_client(q)
        # Second call should not raise
        sse_unregister_client(q)
