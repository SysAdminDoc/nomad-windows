"""Shared utility functions for web routes and blueprints."""

import hashlib
import hmac
import json
import logging
import os
import platform
import uuid as _uuid
from urllib.parse import urlparse
from html import escape as _html_escape

log = logging.getLogger('nomad.web')
_PBKDF2_PREFIX = 'pbkdf2$'
_PBKDF2_ITERATIONS = 100_000


def esc(s):
    """Escape HTML for print/template output (None-safe)."""
    return _html_escape(str(s)) if s else ''


def clone_json_fallback(fallback):
    """Return a shallow copy of a dict/list fallback, or the value unchanged."""
    if isinstance(fallback, dict):
        return dict(fallback)
    if isinstance(fallback, list):
        return list(fallback)
    return fallback


def safe_json_value(value, fallback=None):
    """Parse JSON safely, returning a cloned fallback for invalid or mismatched values.

    Handles str, bytes, bytearray, and already-parsed dicts/lists.
    """
    if isinstance(value, (bytes, bytearray)):
        value = value.decode('utf-8', errors='ignore')
    if value in (None, ''):
        return clone_json_fallback(fallback)
    if isinstance(value, (dict, list)):
        return clone_json_fallback(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return clone_json_fallback(fallback)
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, TypeError, ValueError):
            return clone_json_fallback(fallback)
    else:
        return clone_json_fallback(fallback)
    if parsed is None:
        return clone_json_fallback(fallback)
    if isinstance(fallback, dict) and not isinstance(parsed, dict):
        return clone_json_fallback(fallback)
    if isinstance(fallback, list) and not isinstance(parsed, list):
        return clone_json_fallback(fallback)
    return parsed


def safe_json_list(value, fallback=None):
    """Parse a JSON string into a list, returning fallback on any error."""
    if fallback is None:
        fallback = []
    parsed = safe_json_value(value, None)
    return list(parsed) if isinstance(parsed, list) else clone_json_fallback(fallback)


def safe_json_object(value, fallback=None):
    """Parse a JSON string into a dict, returning fallback on any error."""
    if fallback is None:
        fallback = {}
    parsed = safe_json_value(value, None)
    return dict(parsed) if isinstance(parsed, dict) else clone_json_fallback(fallback)


def safe_id_list(value):
    """Parse a JSON list of IDs into a list of ints, skipping invalid entries."""
    ids = []
    for raw in safe_json_list(value, []):
        try:
            ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    return ids


def require_json_body(req):
    """Return parsed JSON or a standard 400 response for malformed JSON bodies."""
    data = req.get_json(silent=True)
    if data is None:
        from flask import jsonify
        return None, (jsonify({'error': 'Request body must be valid JSON'}), 400)
    return data, None


def coerce_int(value, default, minimum=None, maximum=None):
    """Safely coerce an integer and apply defensive bounds.

    Invalid values fall back to ``default``. Values below ``minimum`` also
    fall back to ``default`` when the default itself is in range; otherwise the
    lower bound wins. Values above ``maximum`` are capped.
    """
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    if minimum is not None and result < minimum:
        result = default if default >= minimum else minimum
    if maximum is not None and result > maximum:
        result = maximum
    return result


def get_query_int(req, name, default, minimum=None, maximum=None):
    """Read and bound an integer query parameter from a Flask request."""
    return coerce_int(req.args.get(name, default), default, minimum, maximum)


def hash_local_secret(value):
    """Hash a local auth secret using PBKDF2-SHA256 with a random salt."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac('sha256', value.encode(), salt, _PBKDF2_ITERATIONS)
    return f'{_PBKDF2_PREFIX}{salt.hex()}${digest.hex()}'


def local_secret_needs_rehash(stored_hash):
    """Return True when a stored local auth secret uses the legacy SHA-256 format."""
    return bool(stored_hash) and not str(stored_hash).startswith(_PBKDF2_PREFIX)


def verify_local_secret(value, stored_hash):
    """Verify a local auth secret against PBKDF2 or legacy SHA-256 storage."""
    if not value or not stored_hash:
        return False
    stored_hash = str(stored_hash)
    if stored_hash.startswith(_PBKDF2_PREFIX):
        parts = stored_hash.split('$')
        if len(parts) != 3:
            return False
        try:
            salt = bytes.fromhex(parts[1])
        except ValueError:
            return False
        digest = hashlib.pbkdf2_hmac('sha256', value.encode(), salt, _PBKDF2_ITERATIONS).hex()
        return hmac.compare_digest(digest, parts[2])
    legacy = hashlib.sha256(value.encode()).hexdigest()
    return hmac.compare_digest(legacy, stored_hash)


def close_db_safely(db, context='database connection'):
    """Best-effort DB close with debug logging instead of silent failure."""
    if not db:
        return
    try:
        db.close()
    except Exception as exc:
        log.debug('Failed to close %s: %s', context, exc)


def validate_bulk_ids(data):
    """Validate and return integer IDs from a bulk-delete request, or None."""
    ids = data.get('ids', [])
    if not ids or not isinstance(ids, list):
        return None
    if len(ids) > 100:
        return None
    try:
        return [int(i) for i in ids]
    except (ValueError, TypeError):
        return None


def check_origin(req):
    """Block cross-origin state-changing requests (CSRF protection).

    Only the actual app origin is allowed. Loopback aliases are treated as the
    same origin only when the scheme and port also match, which keeps the
    desktop shell flexible without allowing unrelated localhost dev servers to
    bypass CSRF checks.
    """
    import ipaddress
    origin = req.headers.get('Origin', '')
    if not origin:
        return

    parsed_origin = urlparse(origin)
    parsed_request = urlparse(f'{req.scheme}://{req.host}')

    def _port(parsed):
        if parsed.port is not None:
            return parsed.port
        if parsed.scheme == 'https':
            return 443
        return 80

    def _is_loopback(hostname):
        host = (hostname or '').strip().lower()
        if host == 'localhost':
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    same_origin = (
        parsed_origin.scheme in ('http', 'https')
        and parsed_origin.hostname
        and parsed_origin.scheme == parsed_request.scheme
        and parsed_origin.netloc.lower() == parsed_request.netloc.lower()
    )
    same_loopback_origin = (
        parsed_origin.scheme in ('http', 'https')
        and parsed_origin.scheme == parsed_request.scheme
        and _is_loopback(parsed_origin.hostname)
        and _is_loopback(parsed_request.hostname)
        and _port(parsed_origin) == _port(parsed_request)
    )
    if same_origin or same_loopback_origin:
        return

    from flask import abort
    abort(403, 'Cross-origin request blocked')


def validate_download_url(url):
    """Validate that a download URL is safe (SSRF protection).

    Raises ValueError if the URL uses a non-https scheme or points to a
    private/internal IP address.
    """
    import ipaddress
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in ('https', 'http'):
        raise ValueError(f'Unsupported URL scheme: {parsed.scheme}')
    hostname = parsed.hostname or ''
    if hostname in ('localhost', '') or hostname.endswith('.local'):
        raise ValueError('URLs pointing to internal hosts are not allowed')
    try:
        import socket
        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(5)
        try:
            resolved = socket.getaddrinfo(hostname, None)
        finally:
            socket.setdefaulttimeout(old_timeout)
        for _family, _type, _proto, _canonname, sockaddr in resolved:
            ip = ipaddress.ip_address(sockaddr[0])
            if (ip.is_private or ip.is_loopback or ip.is_link_local
                    or ip.is_reserved or ip.is_multicast):
                raise ValueError('URL resolves to a blocked IP range')
    except (socket.gaierror, OSError):
        raise ValueError(f'Cannot resolve hostname: {hostname}')
    return url


def get_node_id():
    """Get or create a persistent node ID for federation."""
    from db import db_session
    with db_session() as db:
        row = db.execute("SELECT value FROM settings WHERE key = 'node_id'").fetchone()
        if row and row['value']:
            return row['value']
        node_id = str(_uuid.uuid4())[:8]
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('node_id', ?)", (node_id,))
        db.commit()
        return node_id


def get_node_name():
    """Get the configured node name, falling back to hostname."""
    from db import db_session
    with db_session() as db:
        row = db.execute("SELECT value FROM settings WHERE key = 'node_name'").fetchone()
    return (row['value'] if row and row['value'] else platform.node()) or 'NOMAD Node'


def read_household_size(db, default=1):
    """Return a sanitized household size from settings, falling back to a safe default."""
    safe_default = max(1, int(default))
    try:
        hs = db.execute("SELECT value FROM settings WHERE key='household_size'").fetchone()
        if not hs or hs['value'] in (None, ''):
            return safe_default
        return max(1, int(hs['value']))
    except (TypeError, ValueError, KeyError) as exc:
        log.debug('Invalid household_size setting encountered: %s', exc)
    except Exception as exc:
        log.debug('Failed to read household_size setting: %s', exc)
    return safe_default
