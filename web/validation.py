"""Lightweight request validation for Flask routes."""

import functools
from flask import request, jsonify


def validate_json(schema):
    """Decorator that validates request JSON against a schema before route executes.

    Schema format:
        {
            'field_name': {
                'type': str/int/float/bool/list/dict,  # Python type
                'required': True/False,                  # default False
                'max_length': 200,                       # for str only
                'min_length': 1,                         # for str only
                'min': 0,                                # for int/float
                'max': 10000,                            # for int/float
                'choices': ['a', 'b', 'c'],              # enum validation
                'pattern': r'^[a-z]+$',                  # regex for str
            }
        }

    Usage:
        @app.route('/api/thing', methods=['POST'])
        @validate_json({'name': {'type': str, 'required': True, 'max_length': 200}})
        def create_thing():
            data = request.get_json()  # guaranteed to be valid
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            data = request.get_json(silent=True)
            if data is None:
                return jsonify({'error': 'Request body must be valid JSON'}), 400
            # JSON bodies may be lists, numbers, strings, or null — but our
            # schemas target object bodies. Reject anything else up front so
            # `_validate_data` doesn't crash on `data.get(field)`.
            if not isinstance(data, dict):
                return jsonify({'error': 'Request body must be a JSON object'}), 400

            errors = _validate_data(data, schema)
            if errors:
                return jsonify({'error': 'Validation failed', 'details': errors}), 400

            return f(*args, **kwargs)
        return wrapper
    return decorator


def _validate_data(data, schema):
    """Validate data dict against schema. Returns list of error strings."""
    import re
    errors = []

    for field, rules in schema.items():
        value = data.get(field)
        required = rules.get('required', False)

        # Check required
        if required and (value is None or value == ''):
            errors.append(f'{field} is required')
            continue

        # Skip optional missing fields
        if value is None:
            continue

        # Type check
        expected_type = rules.get('type')
        if expected_type:
            # Normalise to tuple for isinstance check
            type_tuple = expected_type if isinstance(expected_type, tuple) else (expected_type,)
            # Allow int where float is expected
            if float in type_tuple and isinstance(value, int):
                value = float(value)
            elif not isinstance(value, type_tuple):
                type_names = ', '.join(t.__name__ for t in type_tuple)
                errors.append(f'{field} must be {type_names}')
                continue

        # String validations
        if isinstance(value, str):
            max_len = rules.get('max_length')
            if max_len and len(value) > max_len:
                errors.append(f'{field} must be at most {max_len} characters')
            min_len = rules.get('min_length')
            if min_len and len(value) < min_len:
                errors.append(f'{field} must be at least {min_len} characters')
            pattern = rules.get('pattern')
            if pattern and not re.match(pattern, value):
                errors.append(f'{field} format is invalid')

        # Numeric validations
        if isinstance(value, (int, float)):
            min_val = rules.get('min')
            if min_val is not None and value < min_val:
                errors.append(f'{field} must be at least {min_val}')
            max_val = rules.get('max')
            if max_val is not None and value > max_val:
                errors.append(f'{field} must be at most {max_val}')

        # Choices
        choices = rules.get('choices')
        if choices and value not in choices:
            errors.append(f'{field} must be one of: {", ".join(str(c) for c in choices)}')

    return errors


def validate_file_upload(allowed_extensions=None, max_size_mb=100):
    """Decorator that validates file uploads.

    Usage:
        @app.route('/api/upload', methods=['POST'])
        @validate_file_upload(allowed_extensions={'.csv', '.json'}, max_size_mb=10)
        def upload_file():
            file = request.files['file']
    """
    max_bytes = max_size_mb * 1024 * 1024

    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400

            file = request.files['file']
            if not file.filename:
                return jsonify({'error': 'Empty filename'}), 400

            if allowed_extensions:
                import os
                ext = os.path.splitext(file.filename)[1].lower()
                if ext not in allowed_extensions:
                    return jsonify({'error': f'File type {ext} not allowed. Allowed: {", ".join(sorted(allowed_extensions))}'}), 400

            # Reject early on Content-Length header, but also measure the
            # actual stream — a client can send a misleading Content-Length.
            if request.content_length and request.content_length > max_bytes:
                return jsonify({'error': f'File too large. Maximum: {max_size_mb}MB'}), 413
            try:
                stream = file.stream
                stream.seek(0, 2)
                actual_size = stream.tell()
                stream.seek(0)
            except (OSError, AttributeError):
                actual_size = 0
            if actual_size > max_bytes:
                return jsonify({'error': f'File too large. Maximum: {max_size_mb}MB'}), 413

            return f(*args, **kwargs)
        return wrapper
    return decorator
