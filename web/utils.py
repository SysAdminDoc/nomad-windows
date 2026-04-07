"""Shared utility functions for web routes and blueprints."""

import json
import logging
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
