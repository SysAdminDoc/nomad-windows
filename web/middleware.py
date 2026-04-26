"""Flask middleware — rate limiting, CSRF, auth, and security headers.

All hooks are registered by calling ``setup_middleware(app)`` from ``create_app()``.
"""

import os
import time
import logging
import threading
import collections

from flask import request, jsonify, abort, session, Response

from config import Config
from db import db_session
from web.utils import (
    check_origin as _check_origin,
    is_loopback_addr as _is_loopback,
    hash_local_secret as _hash_local_secret,
    local_secret_needs_rehash as _local_secret_needs_rehash,
    verify_local_secret as _verify_local_secret,
)

log = logging.getLogger('nomad.web')

# HTTP methods that can mutate server state.
MUTATING_METHODS = ('POST', 'PUT', 'PATCH', 'DELETE')

# Hand-picked CSP for a single-origin desktop/LAN app. `unsafe-inline`
# + `unsafe-eval` are required by the current UI (inline <script>/onclick
# handlers, Leaflet/Cesium wasm). `blob:` and `data:` accommodate offline
# tile previews and inline SVG favicons. `connect-src https:` is required
# by embedded apps (VIPTrack ADS-B feeds, NukeMap, weather/aviation APIs,
# CORS proxies) — the trust model is local desktop, not internet-facing.
_CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' blob:; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob: https:; "
    "font-src 'self' data:; "
    "connect-src 'self' blob: ws: wss: https: http://127.0.0.1:* http://localhost:*; "
    "media-src 'self' blob: https:; "
    "worker-src 'self' blob:; "
    "frame-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)
_EMBED_CSP_POLICY = _CSP_POLICY.replace("frame-ancestors 'none'; ", "frame-ancestors 'self'; ")


def setup_middleware(app):
    """Register all before/after-request hooks and error handlers with *app*."""
    _setup_rate_limiting(app)
    _setup_csrf(app)
    _setup_host_validation(app)
    _setup_auth_required_api_guard(app)
    _setup_lan_auth(app)
    _setup_security_headers(app)
    _setup_db_cleanup(app)
    _setup_error_handlers(app)


# ─── Rate Limiting ────────────────────────────────────────────────────────────

def _setup_rate_limiting(app):
    """Attach flask-limiter + custom sliding-window guard for mutating requests."""
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address

        limiter = Limiter(
            app=app,
            key_func=get_remote_address,
            default_limits=[Config.RATELIMIT_DEFAULT],
            storage_uri='memory://',
        )

        @limiter.request_filter
        def _exempt_localhost():
            addr = get_remote_address()
            return _is_loopback(addr)

        # Per-client sliding-window counter for mutating methods — localhost exempt.
        _mutating_window = int(os.environ.get('NOMAD_RATELIMIT_MUTATING_WINDOW', 60))
        _mutating_max = 60
        try:
            _n, _per = Config.RATELIMIT_MUTATING.split('/')
            _mutating_max = int(_n.strip())
        except (ValueError, AttributeError):
            pass
        _mutating_hits = collections.defaultdict(collections.deque)
        _mutating_lock = threading.Lock()

        @app.before_request
        def _check_mutating_rate_limit():
            if request.method not in MUTATING_METHODS:
                return
            addr = get_remote_address()
            if _is_loopback(addr):
                return
            now = time.time()
            cutoff = now - _mutating_window
            with _mutating_lock:
                q = _mutating_hits[addr]
                while q and q[0] < cutoff:
                    q.popleft()
                if len(q) >= _mutating_max:
                    return jsonify({'error': 'Rate limit exceeded for mutating requests',
                                    'retry_after': _mutating_window}), 429
                q.append(now)
                if len(_mutating_hits) > 500:
                    stale = [a for a, dq in _mutating_hits.items() if not dq]
                    for a in stale:
                        del _mutating_hits[a]

        app.extensions['limiter'] = limiter
    except ImportError:
        log.info('flask-limiter not installed — rate limiting disabled')


# ─── CSRF Protection ─────────────────────────────────────────────────────────

def _setup_csrf(app):
    """Register CSRF cookie SameSite, origin check, and token validation hooks."""

    @app.after_request
    def _set_cookie_samesite(response):
        cookies = response.headers.getlist('Set-Cookie')
        if cookies:
            new_cookies = []
            for cookie in cookies:
                if 'SameSite' not in cookie:
                    cookie += '; SameSite=Strict'
                new_cookies.append(cookie)
            response.headers.pop('Set-Cookie')
            for c in new_cookies:
                response.headers.add('Set-Cookie', c)
        return response

    @app.before_request
    def _csrf_origin_check():
        if request.method in MUTATING_METHODS:
            _check_origin(request)

    @app.before_request
    def _csrf_token_check():
        if request.method not in MUTATING_METHODS:
            return
        remote = request.remote_addr or ''
        if _is_loopback(remote):
            return
        import hmac as _hmac
        token = request.headers.get('X-CSRF-Token', '')
        expected = session.get('csrf_token', '')
        if not token or not expected or not _hmac.compare_digest(token, expected):
            abort(403, 'CSRF token missing or invalid')

    @app.route('/api/csrf-token')
    def api_csrf_token():
        """Generate and return a CSRF token for the current session."""
        import secrets as _secrets
        if 'csrf_token' not in session:
            session['csrf_token'] = _secrets.token_hex(32)
        return jsonify({'csrf_token': session['csrf_token']})


# ─── Host Header Validation ───────────────────────────────────────────────────

def _setup_host_validation(app):
    """Reject requests with unexpected Host headers (DNS rebinding protection)."""
    _allowed_hosts_raw = os.environ.get('NOMAD_ALLOWED_HOSTS', '')
    _allowed_hosts = set(
        h.strip().lower() for h in _allowed_hosts_raw.split(',') if h.strip()
    ) if _allowed_hosts_raw else None

    @app.before_request
    def _host_header_check():
        if _allowed_hosts is None:
            return
        raw = (request.host or '').lower().strip()
        # IPv6 literals are wrapped in brackets (RFC 3986 §3.2.2):
        # ``[::1]:8080``. A naive ``split(':')[0]`` returned ``[`` and broke
        # the check for every IPv6 host. Extract the literal between
        # brackets, falling back to split-at-last-colon for IPv4/hostname.
        if raw.startswith('['):
            end = raw.find(']')
            host = raw[1:end] if end > 0 else raw.lstrip('[').split(':')[0]
        elif ':' in raw:
            # ``host:port`` — port always on the right. rsplit for safety.
            host = raw.rsplit(':', 1)[0]
        else:
            host = raw
        if host not in _allowed_hosts and not _is_loopback(request.remote_addr or ''):
            abort(403, 'Host not allowed')


# ─── LAN Auth Guard ───────────────────────────────────────────────────────────

def _setup_auth_required_api_guard(app):
    """Require session auth for non-loopback API reads in multi-user mode."""

    _public_api_paths = {
        '/api/csrf-token',
        '/api/health',
    }

    def _auth_required():
        return os.environ.get('NOMAD_AUTH_REQUIRED', '0').strip() in ('1', 'true', 'yes', 'on')

    @app.before_request
    def _check_global_api_auth():
        if not _auth_required():
            return
        if request.method == 'OPTIONS':
            return
        if not request.path.startswith('/api/'):
            return
        if request.path in _public_api_paths:
            return
        if _is_loopback(request.remote_addr or ''):
            return

        from flask import g
        from web.auth import _resolve_proxy_user, _resolve_session

        proxy_user = _resolve_proxy_user()
        if proxy_user:
            g.current_user = proxy_user
            return
        user, _token = _resolve_session()
        if user:
            g.current_user = user
            return
        return jsonify({'error': 'Authentication required'}), 401


def _setup_lan_auth(app):
    """Require auth token for state-changing LAN requests when password is set."""

    @app.before_request
    def check_lan_auth():
        if os.environ.get('NOMAD_AUTH_REQUIRED', '0').strip() in ('1', 'true', 'yes', 'on'):
            return
        if request.method not in MUTATING_METHODS:
            return
        remote = request.remote_addr or ''
        if _is_loopback(remote):
            return
        try:
            with db_session() as db:
                row = db.execute(
                    "SELECT value FROM settings WHERE key = 'auth_password'"
                ).fetchone()
            if row and row['value']:
                token = request.headers.get('X-Auth-Token', '')
                if not _verify_local_secret(token, row['value']):
                    return jsonify({'error': 'Authentication required'}), 403
                if _local_secret_needs_rehash(row['value']):
                    with db_session() as db:
                        db.execute(
                            "INSERT OR REPLACE INTO settings (key, value) VALUES ('auth_password', ?)",
                            (_hash_local_secret(token),)
                        )
                        db.commit()
        except Exception as e:
            log.warning('Auth check failed (denying access): %s', e)
            return jsonify({'error': 'Auth check failed'}), 403

    @app.after_request
    def no_cache(response):
        """Prevent WebView2 from caching HTML/API responses."""
        if 'text/html' in response.content_type or 'application/json' in response.content_type:
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response


# ─── Security Headers ─────────────────────────────────────────────────────────

def _setup_security_headers(app):
    """Apply X-Content-Type-Options, X-Frame-Options, Permissions-Policy, and CSP."""

    @app.after_request
    def _set_security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('Referrer-Policy', 'same-origin')
        response.headers.setdefault(
            'Permissions-Policy',
            'camera=(self), microphone=(self), geolocation=(self), interest-cohort=()',
        )
        is_same_origin_embed = request.path.startswith('/viptrack/')
        response.headers['X-Frame-Options'] = 'SAMEORIGIN' if is_same_origin_embed else 'DENY'
        ctype = response.content_type or ''
        if 'text/html' in ctype:
            response.headers['Content-Security-Policy'] = (
                _EMBED_CSP_POLICY if is_same_origin_embed else _CSP_POLICY
            )
        return response


# ─── DB Connection Cleanup ────────────────────────────────────────────────────

def _setup_db_cleanup(app):
    """Auto-close DB connections left open on flask.g at end of each request."""

    @app.teardown_appcontext
    def close_leaked_db(exception):
        from flask import g
        db = g.pop('_db_conn', None)
        if db is not None:
            try:
                db.close()
            except Exception:
                pass


# ─── Error Handlers ───────────────────────────────────────────────────────────

def _setup_error_handlers(app):
    """Register catch-all and 404 error handlers."""

    @app.errorhandler(Exception)
    def handle_unhandled_exception(e):
        """Return JSON for API routes; re-raise for HTML routes."""
        if request.path.startswith('/api/'):
            status = getattr(e, 'code', 500) if hasattr(e, 'code') else 500
            log.warning('API error on %s %s (%s): %s', request.method, request.path, status, e)
            _http_messages = {
                400: 'Bad request', 403: 'Forbidden', 404: 'Not found',
                405: 'Method not allowed', 409: 'Conflict', 413: 'Payload too large',
                429: 'Too many requests',
            }
            msg = _http_messages.get(status, 'Request error' if status < 500 else 'Internal server error')
            return jsonify({'error': msg}), status
        raise e

    @app.errorhandler(404)
    def handle_404(e):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Not found'}), 404
        return e
