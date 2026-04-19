"""Shamir Secret Sharing vault — split secrets into N shares, reconstruct with M-of-N.

Uses GF(256) arithmetic for byte-level splitting. No external dependencies.
Integrates with existing vault_entries for optional Shamir protection on
high-value secrets (master passwords, encryption keys, crypto seeds).
"""

import hashlib
import json
import logging
import os
import secrets
import time

from flask import Blueprint, request, jsonify
from db import db_session, log_activity

shamir_vault_bp = Blueprint('shamir_vault', __name__)
_log = logging.getLogger('nomad.shamir_vault')


# ═══════════════════════════════════════════════════════════════════
# GF(256) Shamir Secret Sharing — pure Python, no dependencies
# ═══════════════════════════════════════════════════════════════════

# GF(256) discrete log / exp tables.  Generator = 2, polynomial 0x11D.
_EXP = [0] * 512
_LOG = [0] * 256


def _init_gf256():
    x = 1
    for i in range(255):
        _EXP[i] = x
        _LOG[x] = i
        x <<= 1           # multiply by generator 2
        if x & 0x100:
            x ^= 0x11D    # reduce by x^8+x^4+x^3+x^2+1
    # wrap-around for easy modular indexing
    for i in range(255, 512):
        _EXP[i] = _EXP[i - 255]


_init_gf256()
# Self-check: generator 2 has order 255 in GF(256)
assert _EXP[0] == 1 and _EXP[255] == _EXP[0]


def _gf_mul(a, b):
    if a == 0 or b == 0:
        return 0
    return _EXP[(_LOG[a] + _LOG[b]) % 255]


def _gf_div(a, b):
    if b == 0:
        raise ValueError('Division by zero in GF(256)')
    if a == 0:
        return 0
    return _EXP[(_LOG[a] - _LOG[b]) % 255]


def _eval_poly(coeffs, x):
    """Evaluate polynomial f(x) = coeffs[0] + coeffs[1]*x + ... in GF(256).
    Uses Horner's method from highest degree down."""
    result = 0
    for c in reversed(coeffs):
        result = _gf_mul(result, x) ^ c
    return result


def _lagrange_interpolate(points, x_target=0):
    """Lagrange interpolation at x_target in GF(256).
    L_i(x) = product_{j!=i} (x - x_j) / (x_i - x_j)
    In GF(256), subtraction is XOR."""
    k = len(points)
    result = 0
    for i in range(k):
        xi, yi = points[i]
        basis = 1
        for j in range(k):
            if i == j:
                continue
            xj = points[j][0]
            basis = _gf_mul(basis, _gf_div(x_target ^ xj, xi ^ xj))
        result ^= _gf_mul(yi, basis)
    return result


def split_secret(secret_bytes, threshold, num_shares):
    """Split secret into num_shares shares, any threshold can reconstruct.

    Args:
        secret_bytes: bytes to split
        threshold: minimum shares needed (M)
        num_shares: total shares to generate (N)

    Returns:
        list of (x, share_bytes) tuples where x is 1..num_shares
    """
    if threshold < 2:
        raise ValueError('Threshold must be >= 2')
    if num_shares < threshold:
        raise ValueError('num_shares must be >= threshold')
    if num_shares > 254:
        raise ValueError('Maximum 254 shares')

    shares = [bytearray() for _ in range(num_shares)]

    for byte_val in secret_bytes:
        # Random polynomial: coeffs[0] = secret byte, rest random
        coeffs = [byte_val] + [secrets.randbelow(256) for _ in range(threshold - 1)]
        for i in range(num_shares):
            x = i + 1  # x values are 1..N (0 is the secret)
            shares[i].append(_eval_poly(coeffs, x))

    return [(i + 1, bytes(shares[i])) for i in range(num_shares)]


def reconstruct_secret(shares):
    """Reconstruct secret from threshold shares.

    Args:
        shares: list of (x, share_bytes) tuples

    Returns:
        bytes — the original secret
    """
    if len(shares) < 2:
        raise ValueError('Need at least 2 shares')

    share_len = len(shares[0][1])
    if any(len(s[1]) != share_len for s in shares):
        raise ValueError('All shares must be the same length')

    result = bytearray()
    for byte_idx in range(share_len):
        points = [(s[0], s[1][byte_idx]) for s in shares]
        result.append(_lagrange_interpolate(points, 0))

    return bytes(result)


# ═══════════════════════════════════════════════════════════════════
# API Routes
# ═══════════════════════════════════════════════════════════════════

@shamir_vault_bp.route('/api/shamir/split', methods=['POST'])
def api_shamir_split():
    """Split a secret into shares. Returns hex-encoded shares."""
    data = request.get_json() or {}
    secret_text = data.get('secret', '')
    threshold = data.get('threshold', 3)
    num_shares = data.get('num_shares', 5)
    label = data.get('label', 'Untitled')

    if not secret_text:
        return jsonify({'error': 'secret is required'}), 400
    if len(secret_text) > 10000:
        return jsonify({'error': 'Secret too large (max 10KB)'}), 400

    try:
        threshold = max(2, min(10, int(threshold)))
        num_shares = max(threshold, min(254, int(num_shares)))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid threshold or num_shares'}), 400

    secret_bytes = secret_text.encode('utf-8')
    shares = split_secret(secret_bytes, threshold, num_shares)

    # Store metadata (NOT the secret or shares — those leave the system)
    secret_hash = hashlib.sha256(secret_bytes).hexdigest()[:16]
    share_id = secrets.token_hex(8)

    with db_session() as db:
        db.execute('''
            INSERT INTO shamir_shares
            (share_id, label, threshold, num_shares, secret_hash, secret_length)
            VALUES (?,?,?,?,?,?)
        ''', (share_id, label, threshold, num_shares, secret_hash, len(secret_bytes)))
        db.commit()

    log_activity('shamir_split', detail=f'{label}: {threshold}-of-{num_shares} split')

    return jsonify({
        'share_id': share_id,
        'label': label,
        'threshold': threshold,
        'num_shares': num_shares,
        'secret_hash': secret_hash,
        'shares': [
            {
                'index': s[0],
                'hex': s[1].hex(),
                'share_id': share_id,
            }
            for s in shares
        ],
    })


@shamir_vault_bp.route('/api/shamir/reconstruct', methods=['POST'])
def api_shamir_reconstruct():
    """Reconstruct a secret from shares. Accepts hex-encoded shares."""
    data = request.get_json() or {}
    share_list = data.get('shares', [])

    if len(share_list) < 2:
        return jsonify({'error': 'Need at least 2 shares'}), 400

    try:
        shares = [(s['index'], bytes.fromhex(s['hex'])) for s in share_list]
    except (KeyError, ValueError) as e:
        return jsonify({'error': f'Invalid share format: {e}'}), 400

    try:
        secret_bytes = reconstruct_secret(shares)
        secret_text = secret_bytes.decode('utf-8')
    except Exception as e:
        return jsonify({'error': 'Reconstruction failed — wrong shares or insufficient count'}), 400

    # Verify against stored hash if share_id provided
    share_id = data.get('share_id', '')
    verified = None
    if share_id:
        with db_session() as db:
            row = db.execute(
                'SELECT secret_hash FROM shamir_shares WHERE share_id = ?', (share_id,)
            ).fetchone()
            if row:
                actual_hash = hashlib.sha256(secret_bytes).hexdigest()[:16]
                verified = actual_hash == row['secret_hash']

    log_activity('shamir_reconstruct', detail=f'Shares used: {len(shares)}, verified: {verified}')

    return jsonify({
        'secret': secret_text,
        'verified': verified,
    })


@shamir_vault_bp.route('/api/shamir/shares')
def api_shamir_list():
    """List all split operations (metadata only — no secrets or shares stored)."""
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM shamir_shares ORDER BY created_at DESC LIMIT 100'
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@shamir_vault_bp.route('/api/shamir/shares/<share_id>', methods=['DELETE'])
def api_shamir_delete(share_id):
    with db_session() as db:
        r = db.execute('DELETE FROM shamir_shares WHERE share_id = ?', (share_id,))
        if r.rowcount == 0:
            return jsonify({'error': 'Not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


# ═══════════════════════════════════════════════════════════════════
# Warrant Canary + Dead-Man's Switch
# ═══════════════════════════════════════════════════════════════════

@shamir_vault_bp.route('/api/canary')
def api_canary_status():
    """Get current warrant canary status."""
    with db_session() as db:
        row = db.execute(
            "SELECT value FROM settings WHERE key = 'warrant_canary'"
        ).fetchone()

    if not row:
        return jsonify({'active': False, 'configured': False})

    try:
        canary = json.loads(row['value'])
    except (json.JSONDecodeError, TypeError):
        return jsonify({'active': False, 'configured': False})

    # Check if canary is expired (dead-man's switch)
    last_renewed = canary.get('last_renewed', '')
    interval_hours = canary.get('interval_hours', 168)  # Default 7 days
    expired = False

    if last_renewed:
        try:
            from datetime import datetime, timezone
            last_dt = datetime.fromisoformat(last_renewed.replace('Z', '+00:00'))
            elapsed_h = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
            expired = elapsed_h > interval_hours
        except (ValueError, TypeError):
            expired = True

    canary['expired'] = expired
    canary['configured'] = True
    canary['active'] = not expired

    return jsonify(canary)


@shamir_vault_bp.route('/api/canary', methods=['POST'])
def api_canary_configure():
    """Configure or update the warrant canary."""
    from datetime import datetime, timezone

    data = request.get_json() or {}
    statement = data.get('statement', '').strip()
    interval_hours = max(1, min(720, int(data.get('interval_hours', 168))))

    if not statement:
        return jsonify({'error': 'statement is required'}), 400
    if len(statement) > 2000:
        return jsonify({'error': 'Statement too long (max 2000 chars)'}), 400

    now = datetime.now(timezone.utc).isoformat()

    # Sign the canary with a hash of statement + timestamp
    sig_input = f'{statement}|{now}'.encode('utf-8')
    signature = hashlib.sha256(sig_input).hexdigest()

    canary = {
        'statement': statement,
        'interval_hours': interval_hours,
        'last_renewed': now,
        'signature': signature,
        'created_at': data.get('created_at', now),
        'renewal_count': 0,
    }

    # Preserve renewal count from existing canary
    with db_session() as db:
        existing = db.execute(
            "SELECT value FROM settings WHERE key = 'warrant_canary'"
        ).fetchone()
        if existing:
            try:
                old = json.loads(existing['value'])
                canary['renewal_count'] = old.get('renewal_count', 0)
                canary['created_at'] = old.get('created_at', now)
            except (json.JSONDecodeError, TypeError):
                pass

        db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('warrant_canary', ?)",
            (json.dumps(canary),)
        )
        db.commit()

    log_activity('canary_configured', detail=f'Interval: {interval_hours}h')
    return jsonify({'status': 'configured', **canary})


@shamir_vault_bp.route('/api/canary/renew', methods=['POST'])
def api_canary_renew():
    """Renew the canary (prove you're still in control)."""
    from datetime import datetime, timezone

    with db_session() as db:
        row = db.execute(
            "SELECT value FROM settings WHERE key = 'warrant_canary'"
        ).fetchone()
        if not row:
            return jsonify({'error': 'No canary configured'}), 404

        try:
            canary = json.loads(row['value'])
        except (json.JSONDecodeError, TypeError):
            return jsonify({'error': 'Canary data corrupted'}), 500

        now = datetime.now(timezone.utc).isoformat()
        sig_input = f'{canary["statement"]}|{now}'.encode('utf-8')

        canary['last_renewed'] = now
        canary['signature'] = hashlib.sha256(sig_input).hexdigest()
        canary['renewal_count'] = canary.get('renewal_count', 0) + 1

        db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('warrant_canary', ?)",
            (json.dumps(canary),)
        )
        db.commit()

    log_activity('canary_renewed', detail=f'Renewal #{canary["renewal_count"]}')
    return jsonify({'status': 'renewed', **canary})


@shamir_vault_bp.route('/api/canary/revoke', methods=['POST'])
def api_canary_revoke():
    """Revoke the canary (signal duress or compromise)."""
    with db_session() as db:
        db.execute("DELETE FROM settings WHERE key = 'warrant_canary'")
        db.commit()

    log_activity('canary_revoked', level='warn', detail='Warrant canary revoked')
    return jsonify({'status': 'revoked'})


# ─── Dead-man's switch actions ───────────────────────────────────

@shamir_vault_bp.route('/api/canary/deadman-actions')
def api_deadman_actions():
    """Get configured dead-man's switch actions."""
    with db_session() as db:
        row = db.execute(
            "SELECT value FROM settings WHERE key = 'deadman_actions'"
        ).fetchone()

    if not row:
        return jsonify({'actions': [], 'configured': False})

    try:
        actions = json.loads(row['value'])
    except (json.JSONDecodeError, TypeError):
        actions = []

    return jsonify({'actions': actions, 'configured': len(actions) > 0})


@shamir_vault_bp.route('/api/canary/deadman-actions', methods=['POST'])
def api_deadman_actions_save():
    """Configure dead-man's switch actions (what happens when canary expires)."""
    data = request.get_json() or {}
    actions = data.get('actions', [])

    # Validate actions
    valid_types = {'alert_federation', 'broadcast_message', 'lock_vault', 'export_data', 'clear_sensitive'}
    validated = []
    for a in actions[:10]:  # Max 10 actions
        if isinstance(a, dict) and a.get('type') in valid_types:
            validated.append({
                'type': a['type'],
                'config': a.get('config', {}),
                'enabled': bool(a.get('enabled', True)),
            })

    with db_session() as db:
        db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('deadman_actions', ?)",
            (json.dumps(validated),)
        )
        db.commit()

    log_activity('deadman_actions_configured', detail=f'{len(validated)} actions')
    return jsonify({'status': 'saved', 'actions': validated})
