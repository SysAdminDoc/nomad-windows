"""Flask blueprints for NOMAD Field Desk route modules."""

from flask import jsonify, request


def error_response(message, status_code=400, details=None):
    """Standardized JSON error response."""
    body = {'error': message, 'status': status_code}
    if details:
        body['details'] = details
    return jsonify(body), status_code


def get_pagination(default_limit=100, max_limit=1000):
    """Parse ?limit=N&offset=N from the request with sane caps.

    Addresses audit M1 — blueprints were returning unbounded result sets,
    which caused memory spikes and UI freezes on constrained hardware.
    Callers should pass the returned values into `LIMIT ? OFFSET ?`.
    """
    try:
        limit = int(request.args.get('limit', default_limit))
    except (TypeError, ValueError):
        limit = default_limit
    try:
        offset = int(request.args.get('offset', 0))
    except (TypeError, ValueError):
        offset = 0
    limit = max(1, min(limit, max_limit))
    offset = max(0, offset)
    return limit, offset
