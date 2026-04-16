"""Flask blueprints for NOMAD Field Desk route modules."""

from flask import jsonify, request
from web.utils import get_query_int


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
    limit = get_query_int(request, 'limit', default_limit, minimum=1, maximum=max_limit)
    offset = get_query_int(request, 'offset', 0, minimum=0)
    return limit, offset
