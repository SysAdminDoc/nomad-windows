"""Platform security — users, auth, sessions, access logs, deployment configs,
performance metrics, and role management."""

import json
import logging
import hashlib
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify

from db import db_session, log_activity

_log = logging.getLogger(__name__)

platform_security_bp = Blueprint('platform_security', __name__, url_prefix='/api/platform')


# ─── Constants ──────────────────────────────────────────────────────

ROLES = {
    'admin': {'description': 'Full access to all features', 'level': 100},
    'user': {'description': 'Standard access', 'level': 50},
    'viewer': {'description': 'Read-only access', 'level': 20},
    'guest': {'description': 'Limited guest access', 'level': 10},
}

SESSION_TIMEOUT_HOURS = 24
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

_USER_SAFE_COLUMNS = [
    'id', 'username', 'display_name', 'role', 'permissions', 'is_active',
    'last_login', 'login_count', 'failed_attempts', 'locked_until',
    'settings', 'created_at', 'updated_at',
]


# ─── Helpers ────────────────────────────────────────────────────────

def _hash_pin(pin):
    """Hash a PIN using SHA-256."""
    return hashlib.sha256(pin.encode()).hexdigest()


def _verify_pin(pin, pin_hash):
    """Compare a plain PIN against a stored hash."""
    return _hash_pin(pin) == pin_hash


def _safe_user(row):
    """Return a user dict with pin_hash and password_hash stripped."""
    return {k: row[k] for k in _USER_SAFE_COLUMNS if k in row.keys()}


def _get_current_session(db):
    """Extract and validate session token from Authorization header or query param."""
    token = None
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        token = auth[7:].strip()
    if not token:
        token = request.args.get('token', '').strip()
    if not token:
        return None, None
    now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    sess = db.execute(
        'SELECT * FROM app_sessions WHERE session_token = ? AND is_active = 1',
        (token,)
    ).fetchone()
    if not sess:
        return None, None
    if sess['expires_at'] and sess['expires_at'] < now:
        db.execute('UPDATE app_sessions SET is_active = 0 WHERE id = ?', (sess['id'],))
        db.commit()
        return None, None
    return dict(sess), token


# ═══════════════════════════════════════════════════════════════════════
#  Users
# ═══════════════════════════════════════════════════════════════════════

@platform_security_bp.route('/users')
def users_list():
    """List all users (exclude pin_hash and password_hash)."""
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM app_users ORDER BY username'
        ).fetchall()
    return jsonify([_safe_user(r) for r in rows])


@platform_security_bp.route('/users', methods=['POST'])
def users_create():
    """Create a new user."""
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    if not username:
        return jsonify({'error': 'username is required'}), 400
    role = data.get('role', 'user')
    if role not in ROLES:
        return jsonify({'error': f'invalid role, must be one of: {", ".join(ROLES)}'}), 400
    pin = (data.get('pin') or '').strip()
    pin_hash = _hash_pin(pin) if pin else ''
    password = (data.get('password') or '').strip()
    password_hash = hashlib.sha256(password.encode()).hexdigest() if password else ''
    permissions = json.dumps(data.get('permissions', []))
    settings = json.dumps(data.get('settings', {}))
    with db_session() as db:
        existing = db.execute(
            'SELECT id FROM app_users WHERE username = ?', (username,)
        ).fetchone()
        if existing:
            return jsonify({'error': 'username already exists'}), 409
        cur = db.execute(
            '''INSERT INTO app_users
               (username, display_name, pin_hash, password_hash, role,
                permissions, is_active, settings)
               VALUES (?,?,?,?,?,?,?,?)''',
            (username,
             (data.get('display_name') or '')[:200],
             pin_hash,
             password_hash,
             role,
             permissions,
             1 if data.get('is_active', True) else 0,
             settings)
        )
        db.commit()
        row_id = cur.lastrowid
    log_activity('user_created', service='platform_security',
                 detail=f'Created user {username} (id={row_id}, role={role})')
    return jsonify({'id': row_id, 'status': 'created'}), 201


@platform_security_bp.route('/users/<int:uid>')
def users_get(uid):
    """Get a single user (exclude hashes)."""
    with db_session() as db:
        row = db.execute('SELECT * FROM app_users WHERE id = ?', (uid,)).fetchone()
        if not row:
            return jsonify({'error': 'user not found'}), 404
    return jsonify(_safe_user(row))


@platform_security_bp.route('/users/<int:uid>', methods=['PUT'])
def users_update(uid):
    """Update a user. Rehash PIN/password if provided."""
    data = request.get_json() or {}
    allowed = [
        'display_name', 'role', 'permissions', 'is_active',
        'settings', 'locked_until',
    ]
    sets, params = [], []
    for col in allowed:
        if col in data:
            val = data[col]
            if col == 'permissions':
                val = json.dumps(val) if isinstance(val, (list, dict)) else val
            elif col == 'settings':
                val = json.dumps(val) if isinstance(val, dict) else val
            elif col == 'role' and val not in ROLES:
                return jsonify({'error': f'invalid role, must be one of: {", ".join(ROLES)}'}), 400
            sets.append(f'{col} = ?')
            params.append(val)
    if 'pin' in data:
        pin = (data['pin'] or '').strip()
        if pin:
            sets.append('pin_hash = ?')
            params.append(_hash_pin(pin))
    if 'password' in data:
        password = (data['password'] or '').strip()
        if password:
            sets.append('password_hash = ?')
            params.append(hashlib.sha256(password.encode()).hexdigest())
    if not sets:
        return jsonify({'error': 'no fields to update'}), 400
    sets.append("updated_at = datetime('now')")
    params.append(uid)
    with db_session() as db:
        r = db.execute(
            f"UPDATE app_users SET {', '.join(sets)} WHERE id = ?", params
        )
        if r.rowcount == 0:
            return jsonify({'error': 'user not found'}), 404
        db.commit()
    log_activity('user_updated', service='platform_security', detail=f'Updated user id={uid}')
    return jsonify({'updated': True})


@platform_security_bp.route('/users/<int:uid>', methods=['DELETE'])
def users_delete(uid):
    """Delete a user and cascade their sessions."""
    with db_session() as db:
        r = db.execute('SELECT username FROM app_users WHERE id = ?', (uid,)).fetchone()
        if not r:
            return jsonify({'error': 'user not found'}), 404
        username = r['username']
        db.execute('DELETE FROM app_sessions WHERE user_id = ?', (uid,))
        db.execute('DELETE FROM app_users WHERE id = ?', (uid,))
        db.commit()
    log_activity('user_deleted', service='platform_security',
                 detail=f'Deleted user {username} (id={uid})')
    return jsonify({'deleted': True})


@platform_security_bp.route('/users/<int:uid>/reset-pin', methods=['POST'])
def users_reset_pin(uid):
    """Reset a user's PIN to a new value."""
    data = request.get_json() or {}
    pin = (data.get('pin') or '').strip()
    if not pin:
        return jsonify({'error': 'pin is required'}), 400
    with db_session() as db:
        r = db.execute(
            "UPDATE app_users SET pin_hash = ?, failed_attempts = 0, "
            "locked_until = '', updated_at = datetime('now') WHERE id = ?",
            (_hash_pin(pin), uid)
        )
        if r.rowcount == 0:
            return jsonify({'error': 'user not found'}), 404
        db.commit()
    log_activity('pin_reset', service='platform_security', detail=f'Reset PIN for user id={uid}')
    return jsonify({'reset': True})


# ═══════════════════════════════════════════════════════════════════════
#  Auth
# ═══════════════════════════════════════════════════════════════════════

@platform_security_bp.route('/auth/login', methods=['POST'])
def auth_login():
    """Validate username + PIN/password and create a session token."""
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    pin = (data.get('pin') or '').strip()
    password = (data.get('password') or '').strip()
    if not username:
        return jsonify({'error': 'username is required'}), 400
    if not pin and not password:
        return jsonify({'error': 'pin or password is required'}), 400
    with db_session() as db:
        user = db.execute(
            'SELECT * FROM app_users WHERE username = ?', (username,)
        ).fetchone()
        if not user:
            return jsonify({'error': 'invalid credentials'}), 401
        if not user['is_active']:
            return jsonify({'error': 'account is disabled'}), 403
        # Check lockout
        now = datetime.utcnow()
        now_str = now.strftime('%Y-%m-%dT%H:%M:%SZ')
        if user['locked_until'] and user['locked_until'] > now_str:
            return jsonify({'error': 'account is locked, try again later',
                            'locked_until': user['locked_until']}), 423
        # Verify credentials
        valid = False
        if pin and user['pin_hash']:
            valid = _verify_pin(pin, user['pin_hash'])
        if not valid and password and user['password_hash']:
            valid = hashlib.sha256(password.encode()).hexdigest() == user['password_hash']
        if not valid:
            attempts = (user['failed_attempts'] or 0) + 1
            updates = {'failed_attempts': attempts}
            if attempts >= MAX_FAILED_ATTEMPTS:
                lockout = (now + timedelta(minutes=LOCKOUT_MINUTES)).strftime('%Y-%m-%dT%H:%M:%SZ')
                updates['locked_until'] = lockout
                db.execute(
                    "UPDATE app_users SET failed_attempts = ?, locked_until = ?, "
                    "updated_at = datetime('now') WHERE id = ?",
                    (attempts, lockout, user['id'])
                )
            else:
                db.execute(
                    "UPDATE app_users SET failed_attempts = ?, updated_at = datetime('now') WHERE id = ?",
                    (attempts, user['id'])
                )
            db.commit()
            log_activity('login_failed', service='platform_security',
                         detail=f'Failed login for {username} (attempt {attempts})')
            return jsonify({'error': 'invalid credentials'}), 401
        # Success — create session
        token = secrets.token_urlsafe(32)
        expires = (now + timedelta(hours=SESSION_TIMEOUT_HOURS)).strftime('%Y-%m-%dT%H:%M:%SZ')
        db.execute(
            '''INSERT INTO app_sessions
               (user_id, session_token, ip_address, user_agent, device_info,
                expires_at, is_active, last_activity)
               VALUES (?,?,?,?,?,?,1,?)''',
            (user['id'], token,
             request.remote_addr or '',
             request.headers.get('User-Agent', '')[:500],
             (data.get('device_info') or '')[:500],
             expires, now_str)
        )
        db.execute(
            "UPDATE app_users SET failed_attempts = 0, locked_until = '', "
            "login_count = login_count + 1, last_login = ?, updated_at = datetime('now') "
            "WHERE id = ?",
            (now_str, user['id'])
        )
        db.commit()
    log_activity('login_success', service='platform_security',
                 detail=f'User {username} logged in')
    return jsonify({
        'token': token,
        'expires_at': expires,
        'user': {
            'id': user['id'],
            'username': user['username'],
            'display_name': user['display_name'],
            'role': user['role'],
        }
    })


@platform_security_bp.route('/auth/logout', methods=['POST'])
def auth_logout():
    """Deactivate a session by token."""
    data = request.get_json() or {}
    token = (data.get('token') or '').strip()
    if not token:
        # Try Authorization header
        auth = request.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            token = auth[7:].strip()
    if not token:
        return jsonify({'error': 'token is required'}), 400
    with db_session() as db:
        r = db.execute(
            'UPDATE app_sessions SET is_active = 0 WHERE session_token = ?', (token,)
        )
        if r.rowcount == 0:
            return jsonify({'error': 'session not found'}), 404
        db.commit()
    log_activity('logout', service='platform_security', detail='Session deactivated')
    return jsonify({'logged_out': True})


@platform_security_bp.route('/auth/session')
def auth_session():
    """Validate current session token and return user info."""
    with db_session() as db:
        sess, token = _get_current_session(db)
        if not sess:
            return jsonify({'error': 'invalid or expired session'}), 401
        user = db.execute(
            'SELECT * FROM app_users WHERE id = ?', (sess['user_id'],)
        ).fetchone()
        if not user:
            return jsonify({'error': 'user not found'}), 404
        # Update last activity
        now_str = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        db.execute(
            'UPDATE app_sessions SET last_activity = ? WHERE id = ?',
            (now_str, sess['id'])
        )
        db.commit()
    return jsonify({
        'session': {
            'id': sess['id'],
            'expires_at': sess['expires_at'],
            'last_activity': now_str,
        },
        'user': _safe_user(user),
    })


@platform_security_bp.route('/auth/change-password', methods=['POST'])
def auth_change_password():
    """Change password for authenticated user."""
    data = request.get_json() or {}
    new_password = (data.get('new_password') or '').strip()
    if not new_password:
        return jsonify({'error': 'new_password is required'}), 400
    with db_session() as db:
        sess, token = _get_current_session(db)
        if not sess:
            return jsonify({'error': 'invalid or expired session'}), 401
        # Verify current password if provided
        current = (data.get('current_password') or '').strip()
        if current:
            user = db.execute(
                'SELECT password_hash FROM app_users WHERE id = ?', (sess['user_id'],)
            ).fetchone()
            if user and user['password_hash']:
                if hashlib.sha256(current.encode()).hexdigest() != user['password_hash']:
                    return jsonify({'error': 'current password is incorrect'}), 401
        new_hash = hashlib.sha256(new_password.encode()).hexdigest()
        r = db.execute(
            "UPDATE app_users SET password_hash = ?, updated_at = datetime('now') WHERE id = ?",
            (new_hash, sess['user_id'])
        )
        if r.rowcount == 0:
            return jsonify({'error': 'user not found'}), 404
        db.commit()
    log_activity('password_changed', service='platform_security',
                 detail=f'Password changed for user id={sess["user_id"]}')
    return jsonify({'changed': True})


# ═══════════════════════════════════════════════════════════════════════
#  Sessions
# ═══════════════════════════════════════════════════════════════════════

@platform_security_bp.route('/sessions')
def sessions_list():
    """List active sessions."""
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM app_sessions WHERE is_active = 1 ORDER BY created_at DESC'
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@platform_security_bp.route('/sessions/<int:sid>', methods=['DELETE'])
def sessions_revoke(sid):
    """Revoke a session by ID."""
    with db_session() as db:
        r = db.execute(
            'UPDATE app_sessions SET is_active = 0 WHERE id = ?', (sid,)
        )
        if r.rowcount == 0:
            return jsonify({'error': 'session not found'}), 404
        db.commit()
    log_activity('session_revoked', service='platform_security',
                 detail=f'Revoked session id={sid}')
    return jsonify({'deleted': True})


@platform_security_bp.route('/sessions/cleanup', methods=['POST'])
def sessions_cleanup():
    """Expire old sessions past their expires_at."""
    now_str = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    with db_session() as db:
        r = db.execute(
            "UPDATE app_sessions SET is_active = 0 "
            "WHERE is_active = 1 AND expires_at != '' AND expires_at < ?",
            (now_str,)
        )
        cleaned = r.rowcount
        db.commit()
    log_activity('sessions_cleanup', service='platform_security',
                 detail=f'Expired {cleaned} sessions')
    return jsonify({'expired': cleaned})


# ═══════════════════════════════════════════════════════════════════════
#  Access Logs
# ═══════════════════════════════════════════════════════════════════════

@platform_security_bp.route('/access-logs')
def access_logs_list():
    """List access logs with optional filters: ?user_id=, ?action=, ?limit=100."""
    user_id = request.args.get('user_id', '').strip()
    action = request.args.get('action', '').strip()
    limit = int(request.args.get('limit', 100))
    clauses, params = [], []
    if user_id:
        clauses.append('user_id = ?')
        params.append(int(user_id))
    if action:
        clauses.append('action = ?')
        params.append(action)
    where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
    params.append(limit)
    with db_session() as db:
        rows = db.execute(
            f'SELECT * FROM access_logs{where} ORDER BY created_at DESC LIMIT ?',
            params
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@platform_security_bp.route('/access-logs', methods=['DELETE'])
def access_logs_clear():
    """Clear logs older than ?days=30."""
    days = int(request.args.get('days', 30))
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')
    with db_session() as db:
        r = db.execute(
            'DELETE FROM access_logs WHERE created_at < ?', (cutoff,)
        )
        deleted = r.rowcount
        db.commit()
    log_activity('access_logs_cleared', service='platform_security',
                 detail=f'Cleared {deleted} logs older than {days} days')
    return jsonify({'deleted': deleted})


@platform_security_bp.route('/access-logs/summary')
def access_logs_summary():
    """Count by action type, most active users, recent failures."""
    with db_session() as db:
        by_action = db.execute(
            'SELECT action, COUNT(*) as count FROM access_logs '
            'GROUP BY action ORDER BY count DESC'
        ).fetchall()
        active_users = db.execute(
            'SELECT user_id, COUNT(*) as count FROM access_logs '
            'WHERE user_id > 0 GROUP BY user_id ORDER BY count DESC LIMIT 10'
        ).fetchall()
        recent_failures = db.execute(
            'SELECT * FROM access_logs WHERE status_code >= 400 '
            'ORDER BY created_at DESC LIMIT 20'
        ).fetchall()
    return jsonify({
        'by_action': [dict(r) for r in by_action],
        'most_active_users': [dict(r) for r in active_users],
        'recent_failures': [dict(r) for r in recent_failures],
    })


# ═══════════════════════════════════════════════════════════════════════
#  Deployment Configs
# ═══════════════════════════════════════════════════════════════════════

@platform_security_bp.route('/configs')
def configs_list():
    """List all deployment configs."""
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM deployment_configs ORDER BY name'
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@platform_security_bp.route('/configs', methods=['POST'])
def configs_create():
    """Create a deployment config."""
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    config_type = data.get('config_type', 'general')
    if config_type not in ('general', 'network', 'backup', 'update', 'display'):
        return jsonify({'error': 'invalid config_type'}), 400
    config_data = json.dumps(data.get('config_data', {}))
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO deployment_configs
               (name, config_type, description, config_data, is_active, notes)
               VALUES (?,?,?,?,?,?)''',
            (name, config_type,
             (data.get('description') or '')[:2000],
             config_data,
             1 if data.get('is_active', True) else 0,
             (data.get('notes') or '')[:2000])
        )
        db.commit()
        row_id = cur.lastrowid
    log_activity('config_created', service='platform_security',
                 detail=f'Created config {name} (id={row_id}, type={config_type})')
    return jsonify({'id': row_id, 'status': 'created'}), 201


@platform_security_bp.route('/configs/<int:cid>')
def configs_get(cid):
    """Get a single deployment config."""
    with db_session() as db:
        row = db.execute(
            'SELECT * FROM deployment_configs WHERE id = ?', (cid,)
        ).fetchone()
        if not row:
            return jsonify({'error': 'config not found'}), 404
    return jsonify(dict(row))


@platform_security_bp.route('/configs/<int:cid>', methods=['PUT'])
def configs_update(cid):
    """Update a deployment config."""
    data = request.get_json() or {}
    allowed = ['name', 'config_type', 'description', 'config_data', 'is_active', 'applied_at', 'notes']
    sets, params = [], []
    for col in allowed:
        if col in data:
            val = data[col]
            if col == 'config_data':
                val = json.dumps(val) if isinstance(val, dict) else val
            elif col == 'config_type' and val not in ('general', 'network', 'backup', 'update', 'display'):
                return jsonify({'error': 'invalid config_type'}), 400
            sets.append(f'{col} = ?')
            params.append(val)
    if not sets:
        return jsonify({'error': 'no fields to update'}), 400
    sets.append("updated_at = datetime('now')")
    params.append(cid)
    with db_session() as db:
        r = db.execute(
            f"UPDATE deployment_configs SET {', '.join(sets)} WHERE id = ?", params
        )
        if r.rowcount == 0:
            return jsonify({'error': 'config not found'}), 404
        db.commit()
    log_activity('config_updated', service='platform_security', detail=f'Updated config id={cid}')
    return jsonify({'updated': True})


@platform_security_bp.route('/configs/<int:cid>', methods=['DELETE'])
def configs_delete(cid):
    """Delete a deployment config."""
    with db_session() as db:
        r = db.execute('DELETE FROM deployment_configs WHERE id = ?', (cid,))
        if r.rowcount == 0:
            return jsonify({'error': 'config not found'}), 404
        db.commit()
    log_activity('config_deleted', service='platform_security', detail=f'Deleted config id={cid}')
    return jsonify({'deleted': True})


# ═══════════════════════════════════════════════════════════════════════
#  Performance Metrics
# ═══════════════════════════════════════════════════════════════════════

@platform_security_bp.route('/metrics', methods=['POST'])
def metrics_record():
    """Record a performance metric."""
    data = request.get_json() or {}
    metric_name = (data.get('metric_name') or '').strip()
    if not metric_name:
        return jsonify({'error': 'metric_name is required'}), 400
    metric_type = data.get('metric_type', 'startup')
    if metric_type not in ('startup', 'request', 'db_query', 'memory', 'disk'):
        return jsonify({'error': 'invalid metric_type'}), 400
    context = json.dumps(data.get('context', {}))
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO performance_metrics
               (metric_type, metric_name, value, unit, context)
               VALUES (?,?,?,?,?)''',
            (metric_type,
             metric_name,
             float(data.get('value', 0)),
             data.get('unit', 'ms'),
             context)
        )
        db.commit()
        row_id = cur.lastrowid
    return jsonify({'id': row_id, 'status': 'recorded'}), 201


@platform_security_bp.route('/metrics')
def metrics_list():
    """List metrics with optional ?type= and ?hours=24 filters."""
    metric_type = request.args.get('type', '').strip()
    hours = int(request.args.get('hours', 24))
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).strftime('%Y-%m-%dT%H:%M:%SZ')
    clauses = ['recorded_at >= ?']
    params = [cutoff]
    if metric_type:
        clauses.append('metric_type = ?')
        params.append(metric_type)
    where = ' WHERE ' + ' AND '.join(clauses)
    with db_session() as db:
        rows = db.execute(
            f'SELECT * FROM performance_metrics{where} ORDER BY recorded_at DESC',
            params
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@platform_security_bp.route('/metrics/summary')
def metrics_summary():
    """Aggregate stats (avg/min/max) by metric type."""
    with db_session() as db:
        rows = db.execute(
            'SELECT metric_type, metric_name, '
            'COUNT(*) as count, '
            'ROUND(AVG(value), 2) as avg_value, '
            'ROUND(MIN(value), 2) as min_value, '
            'ROUND(MAX(value), 2) as max_value, '
            'unit '
            'FROM performance_metrics '
            'GROUP BY metric_type, metric_name '
            'ORDER BY metric_type, metric_name'
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@platform_security_bp.route('/metrics/cleanup', methods=['DELETE'])
def metrics_cleanup():
    """Delete metrics older than ?days=7."""
    days = int(request.args.get('days', 7))
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')
    with db_session() as db:
        r = db.execute(
            'DELETE FROM performance_metrics WHERE recorded_at < ?', (cutoff,)
        )
        deleted = r.rowcount
        db.commit()
    log_activity('metrics_cleanup', service='platform_security',
                 detail=f'Deleted {deleted} metrics older than {days} days')
    return jsonify({'deleted': deleted})


# ═══════════════════════════════════════════════════════════════════════
#  Reference
# ═══════════════════════════════════════════════════════════════════════

@platform_security_bp.route('/reference/roles')
def reference_roles():
    """Return roles reference."""
    return jsonify(ROLES)
