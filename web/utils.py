"""Shared utility functions for web routes and blueprints."""

import json
import logging
import platform
import uuid as _uuid
from html import escape as _html_escape

log = logging.getLogger('nomad.web')


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
    """Block cross-origin state-changing requests (CSRF protection)."""
    origin = req.headers.get('Origin', '')
    if origin and not origin.startswith(('http://localhost:', 'http://127.0.0.1:')):
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
