"""Authentication & authorization decorators (audit H4).

NOMAD ships in two modes:

1. **Desktop mode (default)** — single-user, no auth. The decorator is a
   no-op so existing installs continue to work without any session token.

2. **Multi-user mode** — opt-in via env var `NOMAD_AUTH_REQUIRED=1`. Every
   route protected by `@require_auth` then validates a session token from
   either the `Authorization: Bearer <token>` header or the `?token=<token>`
   query string against the `app_sessions` table provisioned by Phase 19's
   `platform_security` blueprint. Optional `role` argument enforces RBAC
   (admin > user > viewer > guest).

Localhost requests are exempted even in multi-user mode so the local
pywebview shell continues to work without separate login.

This is the missing enforcement layer for the Phase 19 auth system —
without it, the multi-user backend exists but no routes actually require
the user to be logged in.
"""

import functools
import logging
import os

from flask import g, request, jsonify

log = logging.getLogger('nomad.auth')

# Role hierarchy — higher value = more privileged.
_ROLE_RANK = {'guest': 0, 'viewer': 1, 'user': 2, 'admin': 3}


def _auth_required():
    """True if multi-user auth enforcement is active."""
    return os.environ.get('NOMAD_AUTH_REQUIRED', '0').strip() in ('1', 'true', 'yes', 'on')


def _is_localhost():
    """Localhost requests bypass auth so the pywebview shell works.

    Uses the shared ``is_loopback_addr`` helper for robust detection — covers
    127.0.0.0/8, ::1, and IPv4-mapped IPv6 like ::ffff:127.0.0.1.
    """
    from web.utils import is_loopback_addr
    return is_loopback_addr((request.remote_addr or '').strip())


def _resolve_session():
    """Look up the session token + user record for the current request.

    Returns (user_dict, token) or (None, None). Imported lazily to avoid
    circular imports — `db` and `platform_security` both pull in `web.app`
    at module level.
    """
    from db import db_session
    token = None
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        token = auth[7:].strip()
    if not token:
        token = request.args.get('token', '').strip()
    if not token:
        return None, None
    with db_session() as db:
        from datetime import datetime
        now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        sess = db.execute(
            'SELECT * FROM app_sessions WHERE session_token = ? AND is_active = 1',
            (token,),
        ).fetchone()
        if not sess:
            return None, None
        if sess['expires_at'] and sess['expires_at'] < now:
            db.execute('UPDATE app_sessions SET is_active = 0 WHERE id = ?', (sess['id'],))
            db.commit()
            return None, None
        user = db.execute(
            'SELECT id, username, role FROM app_users WHERE id = ?',
            (sess['user_id'],),
        ).fetchone()
        if not user:
            return None, None
        return dict(user), token


def require_auth(role='user'):
    """Decorator: require an authenticated session with at least `role`.

    Usage:
        @app.route('/api/sensitive', methods=['POST'])
        @require_auth('admin')
        def handler():
            user = g.current_user  # set by the decorator
            ...

    In desktop mode this is a no-op. In multi-user mode it returns 401 if
    no valid session is found, or 403 if the session role is below `role`.
    Localhost is always exempt.
    """
    min_rank = _ROLE_RANK.get(role, _ROLE_RANK['user'])

    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            if not _auth_required() or _is_localhost():
                # Desktop mode or local request — pass through. Set a
                # synthetic g.current_user so downstream code can rely on it.
                g.current_user = {'id': 0, 'username': 'local', 'role': 'admin'}
                return f(*args, **kwargs)
            user, _token = _resolve_session()
            if not user:
                return jsonify({'error': 'Authentication required'}), 401
            user_rank = _ROLE_RANK.get(user.get('role', 'user'), 0)
            if user_rank < min_rank:
                return jsonify({'error': 'Insufficient privileges',
                                'required_role': role}), 403
            g.current_user = user
            return f(*args, **kwargs)
        return wrapper
    return decorator
