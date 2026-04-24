"""Server-Sent Events stream + test endpoints.

Extracted from web/app.py::create_app() in v7.65.0 as part of H-14.
Call ``register_sse_routes(app)`` after middleware so rate-limit headers
and CSRF guards apply.
"""

import queue
import time
import logging

from flask import Response, jsonify, request

from web.state import (
    _sse_clients,
    _sse_lock,
    broadcast_event,
    sse_register_client,
    sse_unregister_client,
    sse_touch_client,
)
from web.utils import is_loopback_addr as _is_loopback

log = logging.getLogger('nomad.web')


def register_sse_routes(app):
    # Per-app rate-limit ledger so multiple test apps don't share state.
    app.config.setdefault('_sse_connects', {})

    @app.route('/api/events/stream')
    def event_stream():
        """SSE endpoint — pushes real-time events to connected clients."""
        ip = request.remote_addr or 'unknown'
        now = time.time()
        sse_connects = app.config['_sse_connects']
        if not _is_loopback(ip):
            with _sse_lock:
                connects = sse_connects.get(ip, [])
                connects = [t for t in connects if now - t < 60]
                if len(connects) >= 10:
                    return jsonify({'error': 'rate limited'}), 429
                connects.append(now)
                sse_connects[ip] = connects
                # Prune IPs with no recent connections
                stale_ips = [
                    k for k, v in sse_connects.items()
                    if all(now - t > 60 for t in v)
                ]
                for k in stale_ips:
                    del sse_connects[k]

        q = queue.Queue(maxsize=50)
        if not sse_register_client(q):
            return jsonify({'error': 'Too many SSE connections'}), 429

        def generate():
            try:
                # Yield an initial keepalive so clients (and test harnesses)
                # receive the response headers + first chunk immediately.
                yield ": connected\n\n"
                while True:
                    try:
                        msg = q.get(timeout=30)
                        sse_touch_client(q)
                        yield msg
                    except queue.Empty:
                        sse_touch_client(q)
                        yield ": keepalive\n\n"
            finally:
                sse_unregister_client(q)

        return Response(
            generate(),
            mimetype='text/event-stream',
            headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
        )

    @app.route('/api/events/test')
    def event_test():
        """Broadcast a test event (useful for debugging SSE)."""
        broadcast_event('alert', {'level': 'info', 'message': 'SSE test event'})
        return jsonify({'status': 'sent', 'clients': len(_sse_clients)})
