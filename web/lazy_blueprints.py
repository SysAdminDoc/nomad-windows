"""WSGI-level lazy blueprint loader.

Flask's URL map is built at blueprint-registration time, but registration
is safe to do on the fly — ``app.register_blueprint()`` simply appends to
``app.url_map``. The dispatcher below peeks at the incoming request path
BEFORE Flask's WSGI entrypoint runs, registers the matching deferred
blueprint (once), and then forwards the request. By the time Flask
matches the URL, the routes are present, so the cold-hit request returns
the same response as the warmed-up path.

Motivation (H-09 / V8-11): two blueprints dominate boot — ``platform_security``
(~21 ms) and ``hunting_foraging`` (~14 ms) per ``python -X importtime``
profiling on 2026-04-24. Neither is on the dashboard's hot path. Deferring
their imports until the first hit shaves ~35 ms off every cold start
(roughly 7% of the 500 ms ``create_app()`` budget) while keeping the
steady-state behavior and all test suites unchanged.

Usage:
    from web.lazy_blueprints import LazyBlueprintDispatcher, DEFERRED_BLUEPRINTS
    app.wsgi_app = LazyBlueprintDispatcher(app, DEFERRED_BLUEPRINTS)
"""

import importlib
import logging
import threading

log = logging.getLogger('nomad.web')


# Prefix -> (module path, blueprint attribute name).
# Keep small — the registry should list blueprints that are:
#   1. measurable import-cost contributors during boot, AND
#   2. NOT on the dashboard's landing path (otherwise the first-request
#      registration cost hits the user's time-to-interactive).
DEFERRED_BLUEPRINTS: dict[str, tuple[str, str]] = {
    '/api/platform': ('web.blueprints.platform_security', 'platform_security_bp'),
    '/api/hunting': ('web.blueprints.hunting_foraging', 'hunting_foraging_bp'),
}


class LazyBlueprintDispatcher:
    """WSGI middleware that lazy-loads blueprints on first matching request."""

    def __init__(self, app, deferred_map):
        self.app = app
        self.wsgi = app.wsgi_app
        # Copy so the caller's dict can't be mutated mid-request.
        self._pending = dict(deferred_map)
        self._lock = threading.Lock()

    def __call__(self, environ, start_response):
        if self._pending:
            path = environ.get('PATH_INFO', '') or ''
            matched = self._match(path)
            if matched is not None:
                self._load(matched)
        return self.wsgi(environ, start_response)

    def _match(self, path):
        # Exact prefix match OR path-separator-bounded match to avoid
        # '/api/platformsomething' false-matching '/api/platform'.
        # Snapshot the keys so a concurrent ``del self._pending[prefix]`` in
        # another thread can't raise RuntimeError mid-iteration.
        for prefix in tuple(self._pending):
            if path == prefix or path.startswith(prefix + '/'):
                return prefix
        return None

    def _load(self, prefix):
        # IMPORTANT: keep the prefix in ``_pending`` until ``register_blueprint``
        # has fully completed. Otherwise a third thread arriving between the
        # pop and the registration would see ``_pending`` clean for this
        # prefix, skip the load path entirely, and forward to Flask before
        # the URL map is updated — yielding a 404 on what should be a 200.
        with self._lock:
            info = self._pending.get(prefix)
            if info is None:  # Another thread already registered this prefix.
                return
            module_path, bp_attr = info
            module = importlib.import_module(module_path)
            blueprint = getattr(module, bp_attr)
            # Flask guards ``register_blueprint`` after the first request has
            # been dispatched (``_got_first_request``). Temporarily flip the
            # flag so the registration is permitted, then restore. This is
            # the documented workaround for runtime extension registration
            # and is stable across Flask 2.x / 3.x.
            was_first = getattr(self.app, '_got_first_request', False)
            self.app._got_first_request = False
            try:
                self.app.register_blueprint(blueprint)
            finally:
                self.app._got_first_request = was_first
            # Only NOW is it safe to drop the pending entry. Any thread that
            # observes the entry already gone has, by happens-before through
            # this same lock, also observed the completed register_blueprint.
            del self._pending[prefix]
            log.info('lazy-registered blueprint %s at %s', bp_attr, prefix)
