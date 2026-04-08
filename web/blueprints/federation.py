"""Federation, sync, node discovery, and dead drop routes."""

import hashlib
import hmac
import json
import logging
import os
import platform
import time
import uuid as _uuid

from flask import Blueprint, request, jsonify, Response

from config import Config
from db import db_session, log_activity
from web.state import _discovered_peers, broadcast_event
from web.utils import clone_json_fallback as _clone_json_fallback, safe_json_value as _safe_json_value, safe_json_object as _safe_json_object, safe_json_list as _safe_json_list, check_origin as _check_origin, get_node_id as _get_node_id, get_node_name as _get_node_name

log = logging.getLogger('nomad.web')

federation_bp = Blueprint('federation', __name__)


# ─── Version (read from app module at import time if possible) ──────
def _get_version():
    try:
        from web.app import VERSION
        return VERSION
    except Exception:
        return '0.0.0'


def _safe_clock(value):
    clock = {}
    for node, raw_val in _safe_json_object(value, {}).items():
        if not isinstance(node, str) or not node:
            continue
        if isinstance(raw_val, bool):
            continue
        if isinstance(raw_val, (int, float)):
            parsed_val = int(raw_val)
        elif isinstance(raw_val, str) and raw_val.strip().lstrip('-').isdigit():
            parsed_val = int(raw_val.strip())
        else:
            continue
        clock[node] = max(0, parsed_val)
    return clock


def _safe_conflict_list(value):
    conflicts = []
    for item in _safe_json_list(value, []):
        if isinstance(item, dict):
            conflicts.append(dict(item))
    return conflicts


def _safe_response_payload(response, fallback=None):
    if fallback is None:
        fallback = {}
    try:
        parsed = response.json()
    except Exception:
        return _clone_json_fallback(fallback)
    if isinstance(parsed, (dict, list)):
        return parsed
    return _clone_json_fallback(fallback)


def _vc_dominates(a, b):
    """Check if vector clock a dominates b (a >= b for all keys, a > b for at least one)."""
    all_keys = set(list(a.keys()) + list(b.keys()))
    if not all_keys:
        return False
    at_least_one_greater = False
    for k in all_keys:
        av = a.get(k, 0)
        bv = b.get(k, 0)
        if av < bv:
            return False
        if av > bv:
            at_least_one_greater = True
    return at_least_one_greater


# ─── Cryptographic Node Identity ─────────────────────────────────

def _get_or_create_node_key():
    """Get or create node signing key. Returns (private_key_hex, public_key_hex)."""
    with db_session() as db:
        row = db.execute("SELECT value FROM settings WHERE key='node_private_key'").fetchone()
        if row:
            pub = db.execute("SELECT value FROM settings WHERE key='node_public_key'").fetchone()
            return row['value'], pub['value']
        private_key = os.urandom(32).hex()
        public_key = hashlib.sha256(bytes.fromhex(private_key)).hexdigest()
        db.executemany("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                      [('node_private_key', private_key), ('node_public_key', public_key)])
        db.commit()
        return private_key, public_key


def _sign_payload(data_str, private_key_hex):
    """Sign a payload string using HMAC-SHA256 with the node private key."""
    return hmac.new(bytes.fromhex(private_key_hex), data_str.encode(), hashlib.sha256).hexdigest()


def _verify_signature(data_str, signature, public_key_hex):
    """Verify signature against a known peer public key using HMAC-SHA256."""
    expected = hmac.new(bytes.fromhex(public_key_hex), data_str.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# ─── Node Identity ──────────────────────────────────────────────────

@federation_bp.route('/api/node/identity')
def api_node_identity():
    return jsonify({'node_id': _get_node_id(), 'node_name': _get_node_name(), 'version': _get_version()})


@federation_bp.route('/api/node/identity', methods=['PUT'])
def api_node_identity_update():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if name:
        with db_session() as db:
            db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('node_name', ?)", (name,))
            db.commit()
    return jsonify({'status': 'updated', 'node_name': name})


# ─── UDP Discovery ──────────────────────────────────────────────────

@federation_bp.route('/api/node/discover', methods=['POST'])
def api_node_discover():
    """Broadcast UDP to find other NOMAD Field Desk nodes on the LAN."""
    import socket
    _discovered_peers.clear()
    node_id = _get_node_id()
    node_name = _get_node_name()
    msg = json.dumps({'type': 'nomad_discover', 'node_id': node_id, 'node_name': node_name, 'port': Config.APP_PORT}).encode()

    discovery_port = Config.DISCOVERY_PORT
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(3)
        sock.sendto(msg, ('<broadcast>', discovery_port))

        end_time = time.time() + 3
        while time.time() < end_time:
            try:
                data, addr = sock.recvfrom(1024)
                peer = _safe_json_object(data, {})
                if peer.get('type') == 'nomad_announce' and peer.get('node_id') != node_id:
                    _discovered_peers[peer['node_id']] = {
                        'node_id': peer['node_id'], 'node_name': peer.get('node_name', 'Unknown'),
                        'ip': addr[0], 'port': peer.get('port', 8080), 'version': peer.get('version', '?'),
                    }
            except socket.timeout:
                break
            except Exception:
                continue
        sock.close()
    except Exception as e:
        log.warning(f'Discovery broadcast failed: {e}')

    return jsonify({'peers': list(_discovered_peers.values()), 'self': {'node_id': node_id, 'node_name': node_name}})


@federation_bp.route('/api/node/peers')
def api_node_peers():
    return jsonify(list(_discovered_peers.values()))


@federation_bp.route('/api/node/announce', methods=['POST'])
def api_node_announce():
    """Respond to a discovery broadcast (called by peers via HTTP as fallback)."""
    return jsonify({
        'type': 'nomad_announce', 'node_id': _get_node_id(),
        'node_name': _get_node_name(), 'port': 8080, 'version': _get_version(),
    })


# ─── Sync Push/Pull/Receive ────────────────────────────────────────

@federation_bp.route('/api/node/sync-push', methods=['POST'])
def api_node_sync_push():
    """Push data TO a peer node. Supports delta sync via optional 'since' parameter."""
    data = request.get_json() or {}
    peer_ip = data.get('ip')
    peer_port = data.get('port', 8080)
    since = data.get('since')  # ISO timestamp for delta sync
    if not peer_ip:
        return jsonify({'error': 'No peer IP'}), 400
    import ipaddress as _ipa
    try:
        ip_obj = _ipa.ip_address(peer_ip)
        if ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved or ip_obj.is_unspecified:
            return jsonify({'error': 'Invalid peer IP address'}), 400
    except ValueError:
        return jsonify({'error': 'Invalid IP address format'}), 400

    import requests as req
    SYNC_TABLES = ['inventory', 'contacts', 'checklists', 'notes', 'incidents', 'waypoints']
    node_id = _get_node_id()
    node_name = _get_node_name()

    # If no explicit 'since', check last_synced_at for this peer
    peer_id = data.get('peer_id', '')
    if not since and peer_id:
        with db_session() as db:
            sp = db.execute('SELECT last_synced_at FROM sync_peers WHERE peer_id = ?', (peer_id,)).fetchone()
            if sp and sp['last_synced_at']:
                since = sp['last_synced_at']

    with db_session() as db:
        payload = {'source_node_id': node_id, 'source_node_name': node_name, 'tables': {}}
        total_items = 0
        for table in SYNC_TABLES:
            try:
                # Delta sync: only rows updated/created after 'since'
                if since:
                    schema_cols = {r[1] for r in db.execute(f"PRAGMA table_info({table})").fetchall()}
                    if 'updated_at' in schema_cols:
                        rows = db.execute(f'SELECT * FROM {table} WHERE updated_at > ? LIMIT 10000', (since,)).fetchall()
                    elif 'created_at' in schema_cols:
                        rows = db.execute(f'SELECT * FROM {table} WHERE created_at > ? LIMIT 10000', (since,)).fetchall()
                    else:
                        rows = db.execute(f'SELECT * FROM {table} LIMIT 10000').fetchall()
                else:
                    rows = db.execute(f'SELECT * FROM {table} LIMIT 10000').fetchall()
                table_data = [dict(r) for r in rows]
                for row in table_data:
                    row.pop('id', None)
                    row['_source_node'] = node_id
                payload['tables'][table] = table_data
                total_items += len(table_data)
                for row in table_data:
                    row_key = hashlib.sha256(json.dumps(row, sort_keys=True, default=str).encode()).hexdigest()[:16]
                    existing = db.execute('SELECT clock FROM vector_clocks WHERE table_name = ? AND row_hash = ?', (table, row_key)).fetchone()
                    clock = _safe_clock(existing['clock'] if existing else None)
                    clock[node_id] = clock.get(node_id, 0) + 1
                    db.execute('INSERT OR REPLACE INTO vector_clocks (table_name, row_hash, clock, last_node, updated_at) VALUES (?, ?, ?, ?, datetime("now"))',
                               (table, row_key, json.dumps(clock), node_id))
                db.commit()
            except Exception as e:
                log.error('Sync push failed for table %s: %s', table, e)

        vc_rows = db.execute('SELECT table_name, row_hash, clock FROM vector_clocks LIMIT 50000').fetchall()
        payload['vector_clocks'] = {r['table_name']: {} for r in vc_rows}
        for r in vc_rows:
            payload['vector_clocks'][r['table_name']][r['row_hash']] = _safe_clock(r['clock'])

    # Sign the payload
    priv_key, pub_key = _get_or_create_node_key()
    payload_str = json.dumps(payload, sort_keys=True, default=str)
    payload['_signature'] = _sign_payload(payload_str, priv_key)
    payload['_public_key'] = pub_key

    try:
        r = req.post(f'http://{peer_ip}:{peer_port}/api/node/sync-receive',
                    json=payload, timeout=30)
        if not r.ok:
            raise RuntimeError(f'Peer sync receive returned HTTP {r.status_code}')
        result = _safe_response_payload(r, {})
        if not isinstance(result, dict) or not result:
            raise ValueError('Peer returned malformed sync payload')
        if result.get('error'):
            raise RuntimeError(str(result.get('error')))
        sync_ts = time.strftime('%Y-%m-%dT%H:%M:%S')
        with db_session() as db:
            db.execute('INSERT INTO sync_log (direction, peer_node_id, peer_name, peer_ip, tables_synced, items_count, status) VALUES (?,?,?,?,?,?,?)',
                       ('push', result.get('node_id', ''), result.get('node_name', ''), peer_ip,
                        json.dumps({t: len(d) for t, d in payload['tables'].items()}), total_items, 'success'))
            # Track last sync time per peer
            result_peer_id = peer_id or result.get('node_id', '')
            if result_peer_id:
                db.execute('INSERT OR REPLACE INTO sync_peers (peer_id, last_synced_at) VALUES (?, ?)',
                           (result_peer_id, sync_ts))
            db.commit()
        return jsonify({'status': 'pushed', 'items': total_items, 'peer': result.get('node_name', peer_ip),
                        'delta': since is not None, 'synced_at': sync_ts})
    except Exception as e:
        log.error('Sync push to peer failed: %s', e)
        return jsonify({'error': 'Push to peer failed'}), 500


@federation_bp.route('/api/node/sync-receive', methods=['POST'])
def api_node_sync_receive():
    """Receive data FROM a peer node (merge mode)."""
    data = request.get_json() or {}
    source_node = data.get('source_node_id', '')
    source_name = data.get('source_node_name', '')
    tables = data.get('tables', {})
    if not isinstance(tables, dict):
        tables = {}

    if not source_node:
        return jsonify({'error': 'source_node_id required'}), 400
    with db_session() as db_check:
        peer = db_check.execute("SELECT trust_level FROM federation_peers WHERE node_id = ?", (source_node,)).fetchone()
    if not peer or peer['trust_level'] == 'blocked':
        return jsonify({'error': 'Unknown or blocked peer'}), 403

    ALLOWED = {'inventory', 'contacts', 'checklists', 'notes', 'incidents', 'waypoints'}
    # Build a lookup of incoming rows by table+hash for conflict detail
    incoming_by_hash = {}
    for tname, rows in tables.items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_copy = {k: v for k, v in row.items() if k != 'id'}
            row_key = hashlib.sha256(json.dumps(row_copy, sort_keys=True, default=str).encode()).hexdigest()[:16]
            incoming_by_hash[(tname, row_key)] = row_copy

    with db_session() as db:
        imported = {}
        total = 0
        for tname, rows in tables.items():
            if tname not in ALLOWED:
                continue
            if not isinstance(rows, list):
                continue
            schema_cols = {r[1] for r in db.execute(f"PRAGMA table_info({tname})").fetchall()}
            count = 0
            for row in rows[:10000]:
                if not isinstance(row, dict):
                    continue
                row.pop('id', None)
                row.pop('created_at', None)
                row.pop('updated_at', None)
                row.pop('_source_node', None)
                safe_row = {k: v for k, v in row.items() if k in schema_cols}
                if not safe_row:
                    continue
                cols = list(safe_row.keys())
                vals = list(safe_row.values())
                placeholders = ','.join(['?'] * len(cols))
                try:
                    db.execute(f'INSERT INTO {tname} ({",".join(cols)}) VALUES ({placeholders})', vals)
                    count += 1
                except Exception as e:
                    log.warning('Federation sync insert failed for %s: %s', tname, e)
            imported[tname] = count
            total += count
        db.commit()

        incoming_clocks = data.get('vector_clocks', {})
        if not isinstance(incoming_clocks, dict):
            incoming_clocks = {}
        conflicts = []
        for tname, hashes in incoming_clocks.items():
            if not isinstance(hashes, dict):
                continue
            for row_hash, incoming_clock in hashes.items():
                incoming_clock = _safe_clock(incoming_clock)
                local_vc_row = db.execute('SELECT clock FROM vector_clocks WHERE table_name = ? AND row_hash = ?', (tname, row_hash)).fetchone()
                local_clock = _safe_clock(local_vc_row['clock'] if local_vc_row else None)
                if local_vc_row:
                    if not _vc_dominates(local_clock, incoming_clock) and not _vc_dominates(incoming_clock, local_clock) and local_clock != incoming_clock:
                        # Fetch actual local row data for conflict details
                        local_row_data = None
                        try:
                            local_rows = db.execute(f'SELECT * FROM {tname} LIMIT 50000').fetchall()
                            for lr in local_rows:
                                lr_dict = dict(lr)
                                lr_dict.pop('id', None)
                                lr_key = hashlib.sha256(json.dumps(lr_dict, sort_keys=True, default=str).encode()).hexdigest()[:16]
                                if lr_key == row_hash:
                                    local_row_data = lr_dict
                                    break
                        except Exception:
                            pass
                        incoming_row_data = incoming_by_hash.get((tname, row_hash))
                        conflicts.append({
                            'table': tname,
                            'row_hash': row_hash,
                            'local_row': local_row_data,
                            'incoming_row': incoming_row_data,
                            'local_clock': local_clock,
                            'incoming_clock': incoming_clock,
                            'resolution': 'last-write-wins',
                        })
                merged = dict(local_clock)
                for node, val in incoming_clock.items():
                    merged[node] = max(merged.get(node, 0), val)
                db.execute('INSERT OR REPLACE INTO vector_clocks (table_name, row_hash, clock, last_node, updated_at) VALUES (?, ?, ?, ?, datetime("now"))',
                           (tname, row_hash, json.dumps(merged), source_node))
        db.commit()

        db.execute('INSERT INTO sync_log (direction, peer_node_id, peer_name, peer_ip, tables_synced, items_count, status, conflicts_detected, conflict_details) VALUES (?,?,?,?,?,?,?,?,?)',
                   ('receive', source_node, source_name, request.remote_addr or '',
                    json.dumps(imported), total, 'success', len(conflicts), json.dumps(conflicts, default=str)))
        db.commit()

    log_activity('sync_received', detail=f'From {source_name} ({source_node}): {total} items')
    return jsonify({'status': 'received', 'imported': imported, 'total': total,
                   'node_id': _get_node_id(), 'node_name': _get_node_name()})


@federation_bp.route('/api/node/sync-pull', methods=['POST'])
def api_node_sync_pull():
    """Pull data FROM a peer node."""
    data = request.get_json() or {}
    peer_ip = data.get('ip')
    peer_port = data.get('port', 8080)
    if not peer_ip:
        return jsonify({'error': 'No peer IP'}), 400
    import ipaddress as _ipa
    try:
        ip_obj = _ipa.ip_address(peer_ip)
        if ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved or ip_obj.is_unspecified:
            return jsonify({'error': 'Invalid peer IP address'}), 400
    except ValueError:
        return jsonify({'error': 'Invalid IP address format'}), 400

    import requests as req

    try:
        r = req.post(f'http://{peer_ip}:{peer_port}/api/node/sync-push',
                    json={'ip': request.host.split(':')[0], 'port': 8080}, timeout=30)
        return jsonify({'status': 'pull_requested', 'peer': peer_ip})
    except Exception as e:
        return jsonify({'error': f'Pull failed: {e}'}), 500


# ─── Vector Clock / Conflicts ───────────────────────────────────────

@federation_bp.route('/api/node/vector-clock')
def api_node_vector_clock():
    """Get the current vector clock state for all tracked tables."""
    with db_session() as db:
        rows = db.execute('SELECT table_name, row_hash, clock, last_node, updated_at FROM vector_clocks ORDER BY table_name LIMIT 10000').fetchall()
    clocks = {}
    for r in rows:
        tname = r['table_name']
        if tname not in clocks:
            clocks[tname] = []
        clock_val = _safe_clock(r['clock'])
        clocks[tname].append({'row_hash': r['row_hash'], 'clock': clock_val, 'last_node': r['last_node'], 'updated_at': r['updated_at']})
    return jsonify(clocks)


@federation_bp.route('/api/node/vector-clock/conflicts')
def api_node_vector_clock_conflicts():
    """Get recent sync conflicts."""
    with db_session() as db:
        rows = db.execute("SELECT * FROM sync_log WHERE conflicts_detected > 0 ORDER BY created_at DESC LIMIT 50").fetchall()
    result = []
    for r in rows:
        entry = dict(r)
        entry['conflict_details'] = _safe_conflict_list(entry.get('conflict_details'))
        result.append(entry)
    return jsonify(result)


@federation_bp.route('/api/node/conflicts')
def api_node_conflicts():
    """Get unresolved sync conflicts for the three-way merge UI."""
    with db_session() as db:
        rows = db.execute(
            "SELECT * FROM sync_log WHERE conflicts_detected > 0 AND (resolved IS NULL OR resolved = 0) ORDER BY created_at DESC LIMIT 100"
        ).fetchall()
        result = []
        for r in rows:
            entry = dict(r)
            entry['conflict_details'] = _safe_conflict_list(entry.get('conflict_details'))
            for conflict in entry['conflict_details']:
                tname = conflict.get('table', '')
                row_hash = conflict.get('row_hash', '')
                if tname and row_hash:
                    vc_row = db.execute('SELECT * FROM vector_clocks WHERE table_name = ? AND row_hash = ?', (tname, row_hash)).fetchone()
                    if vc_row:
                        conflict['local_node'] = vc_row['last_node']
                        conflict['local_updated'] = vc_row['updated_at']
            result.append(entry)
    return jsonify(result)


@federation_bp.route('/api/node/conflicts/<int:conflict_id>/resolve', methods=['POST'])
def api_node_conflict_resolve(conflict_id):
    """Resolve a sync conflict."""
    _check_origin(request)
    data = request.get_json() or {}
    resolution = data.get('resolution', '')
    if resolution not in ('local', 'remote', 'merged'):
        return jsonify({'error': 'resolution must be one of: local, remote, merged'}), 400

    with db_session() as db:
        row = db.execute('SELECT * FROM sync_log WHERE id = ?', (conflict_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Conflict not found'}), 404

        conflicts = _safe_conflict_list(row['conflict_details'])

        if resolution == 'remote':
            tables_synced = _safe_json_object(row['tables_synced'], {})
            for conflict in conflicts:
                tname = conflict.get('table', '')
                incoming_clock = _safe_clock(conflict.get('incoming_clock'))
                row_hash = conflict.get('row_hash', '')
                if tname and row_hash:
                    db.execute(
                        'INSERT OR REPLACE INTO vector_clocks (table_name, row_hash, clock, last_node, updated_at) VALUES (?, ?, ?, ?, datetime("now"))',
                        (tname, row_hash, json.dumps(incoming_clock), row['peer_node_id'])
                    )
        elif resolution == 'merged':
            merged_data = data.get('merged_data', {})
            if not merged_data:
                return jsonify({'error': 'merged_data required for merged resolution'}), 400
            import re as _re
            MERGE_ALLOWED = {'inventory', 'contacts', 'checklists', 'notes', 'incidents', 'waypoints'}
            for tname, rows_to_merge in merged_data.items():
                if tname not in MERGE_ALLOWED:
                    continue
                schema_cols = {r[1] for r in db.execute(f"PRAGMA table_info({tname})").fetchall()}
                for merge_row in (rows_to_merge if isinstance(rows_to_merge, list) else [rows_to_merge]):
                    safe_row = {k: v for k, v in merge_row.items() if k in schema_cols and _re.match(r'^[a-zA-Z_]\w*$', k)}
                    if not safe_row:
                        continue
                    if 'id' in safe_row:
                        row_id = safe_row.pop('id')
                        if safe_row:
                            set_clause = ', '.join(f'{k} = ?' for k in safe_row.keys())
                            db.execute(f'UPDATE {tname} SET {set_clause} WHERE id = ?', list(safe_row.values()) + [row_id])
                    else:
                        cols = list(safe_row.keys())
                        placeholders = ','.join(['?'] * len(cols))
                        db.execute(f'INSERT INTO {tname} ({",".join(cols)}) VALUES ({placeholders})', list(safe_row.values()))

        db.execute('UPDATE sync_log SET resolved = 1, resolution = ? WHERE id = ?', (resolution, conflict_id))
        db.commit()
    log_activity('conflict_resolved', detail=f'Sync conflict #{conflict_id} resolved as {resolution}')
    return jsonify({'status': 'resolved', 'resolution': resolution})


@federation_bp.route('/api/node/sync-log')
def api_node_sync_log():
    with db_session() as db:
        rows = db.execute('SELECT * FROM sync_log ORDER BY created_at DESC LIMIT 50').fetchall()
    return jsonify([dict(r) for r in rows])


@federation_bp.route('/api/node/conflicts/<int:cid>/diff', methods=['GET'])
def api_conflict_diff(cid):
    """Compute field-by-field differences for a sync conflict."""
    with db_session() as db:
        row = db.execute('SELECT * FROM sync_log WHERE id = ?', (cid,)).fetchone()
    if not row:
        return jsonify({'error': 'Conflict not found'}), 404
    details = _safe_conflict_list(row['conflict_details'])
    result_conflicts = []
    for conflict in details:
        local_row = conflict.get('local_row') if isinstance(conflict.get('local_row'), dict) else {}
        incoming_row = conflict.get('incoming_row') if isinstance(conflict.get('incoming_row'), dict) else {}
        all_fields = set(list(local_row.keys()) + list(incoming_row.keys()))
        fields = []
        for name in sorted(all_fields):
            local_val = local_row.get(name)
            remote_val = incoming_row.get(name)
            fields.append({
                'name': name,
                'local_value': local_val,
                'remote_value': remote_val,
                'differs': local_val != remote_val,
            })
        result_conflicts.append({
            'table': conflict.get('table', ''),
            'row_hash': conflict.get('row_hash', ''),
            'fields': fields,
        })
    return jsonify({'conflicts': result_conflicts})


@federation_bp.route('/api/node/sync-status/<peer_id>', methods=['GET'])
def api_sync_status(peer_id):
    """Return last sync time, rows pending, and estimated payload size for a peer."""
    SYNC_TABLES = ['inventory', 'contacts', 'checklists', 'notes', 'incidents', 'waypoints']
    with db_session() as db:
        sp = db.execute('SELECT last_synced_at FROM sync_peers WHERE peer_id = ?', (peer_id,)).fetchone()
        last_synced = sp['last_synced_at'] if sp else None
        pending = 0
        size_estimate = 0
        for table in SYNC_TABLES:
            try:
                schema_cols = {r[1] for r in db.execute(f"PRAGMA table_info({table})").fetchall()}
                if last_synced:
                    if 'updated_at' in schema_cols:
                        cnt = db.execute(f'SELECT COUNT(*) as c FROM {table} WHERE updated_at > ?', (last_synced,)).fetchone()
                    elif 'created_at' in schema_cols:
                        cnt = db.execute(f'SELECT COUNT(*) as c FROM {table} WHERE created_at > ?', (last_synced,)).fetchone()
                    else:
                        cnt = db.execute(f'SELECT COUNT(*) as c FROM {table}').fetchone()
                else:
                    cnt = db.execute(f'SELECT COUNT(*) as c FROM {table}').fetchone()
                row_count = cnt['c'] if cnt else 0
                pending += row_count
                size_estimate += row_count * 256  # rough estimate bytes per row
            except Exception:
                pass
    return jsonify({
        'peer_id': peer_id,
        'last_synced_at': last_synced,
        'rows_pending': pending,
        'estimated_payload_bytes': size_estimate,
    })


# ─── Sneakernet Sync ────────────────────────────────────────────────

@federation_bp.route('/api/sync/export', methods=['POST'])
def api_sync_export():
    """Export selected data as a portable content pack ZIP."""
    data = request.get_json() or {}
    ALLOWED_SYNC_TABLES = {'inventory', 'contacts', 'checklists', 'notes', 'incidents', 'waypoints'}
    include = [t for t in data.get('include', list(ALLOWED_SYNC_TABLES)) if t in ALLOWED_SYNC_TABLES]
    import io
    import zipfile as zf
    buf = io.BytesIO()
    with db_session() as db:
        VERSION = _get_version()
        with zf.ZipFile(buf, 'w', zf.ZIP_DEFLATED) as z:
            manifest = {'version': VERSION, 'exported_at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'tables': []}
            for table in include:
                try:
                    rows = db.execute(f'SELECT * FROM {table} LIMIT 50000').fetchall()
                    table_data = [dict(r) for r in rows]
                    z.writestr(f'{table}.json', json.dumps(table_data, indent=2, default=str))
                    manifest['tables'].append({'name': table, 'count': len(table_data)})
                except Exception:
                    pass
            z.writestr('manifest.json', json.dumps(manifest, indent=2))
    buf.seek(0)
    fname = f'nomad-sync-{time.strftime("%Y%m%d-%H%M%S")}.zip'
    return Response(buf.read(), mimetype='application/zip',
                   headers={'Content-Disposition': f'attachment; filename="{fname}"'})


@federation_bp.route('/api/sync/import', methods=['POST'])
def api_sync_import():
    """Import a content pack ZIP (merge mode)."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    import zipfile as zf
    import io
    file = request.files['file']
    try:
        with zf.ZipFile(io.BytesIO(file.read())) as z:
            if 'manifest.json' not in z.namelist():
                return jsonify({'error': 'Invalid sync file (no manifest)'}), 400
            manifest = _safe_json_object(z.read('manifest.json'), {})
            with db_session() as db:
                imported = {}
                for table_info in _safe_json_list(manifest.get('tables'), []):
                    if not isinstance(table_info, dict):
                        continue
                    tname = table_info['name']
                    if tname not in ('inventory', 'contacts', 'checklists', 'notes', 'incidents', 'waypoints'):
                        continue
                    fname = f'{tname}.json'
                    if fname not in z.namelist():
                        continue
                    rows = _safe_json_list(z.read(fname), [])
                    schema_cols = {row[1] for row in db.execute(f"PRAGMA table_info({tname})").fetchall()}
                    count = 0
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        row.pop('id', None)
                        row.pop('created_at', None)
                        row.pop('updated_at', None)
                        safe_row = {k: v for k, v in row.items() if k in schema_cols}
                        if not safe_row:
                            continue
                        cols = list(safe_row.keys())
                        vals = list(safe_row.values())
                        placeholders = ','.join(['?'] * len(cols))
                        try:
                            db.execute(f'INSERT INTO {tname} ({",".join(cols)}) VALUES ({placeholders})', vals)
                            count += 1
                        except Exception:
                            pass
                    imported[tname] = count
                db.commit()
                return jsonify({'status': 'imported', 'tables': imported})
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception('Sync receive failed')
        return jsonify({'error': 'Sync import failed'}), 400


# ─── Federation Peers CRUD ──────────────────────────────────────────

@federation_bp.route('/api/federation/peers')
def api_federation_peers():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM federation_peers ORDER BY last_seen DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    return jsonify([dict(r) for r in rows])


@federation_bp.route('/api/federation/peers', methods=['POST'])
def api_federation_peer_add():
    data = request.get_json() or {}
    node_id = data.get('node_id', '').strip()
    if not node_id:
        return jsonify({'error': 'node_id required'}), 400
    # Validate peer IP to prevent SSRF when relay/sync contacts peers
    peer_ip = data.get('ip', '').strip()
    if peer_ip:
        import ipaddress as _ipa
        try:
            ip_obj = _ipa.ip_address(peer_ip)
            if ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved or ip_obj.is_unspecified:
                return jsonify({'error': 'Invalid peer IP address (private/reserved)'}), 400
        except ValueError:
            return jsonify({'error': 'Invalid IP address format'}), 400
    with db_session() as db:
        db.execute('INSERT OR REPLACE INTO federation_peers (node_id, node_name, trust_level, ip, port, lat, lng) VALUES (?,?,?,?,?,?,?)',
                   (node_id, data.get('node_name', ''), data.get('trust_level', 'observer'),
                    peer_ip, data.get('port', 8080),
                    data.get('lat'), data.get('lng')))
        db.commit()
    return jsonify({'status': 'added'})


@federation_bp.route('/api/federation/peers/<node_id>/trust', methods=['PUT'])
def api_federation_peer_trust(node_id):
    data = request.get_json() or {}
    trust = data.get('trust_level', 'observer')
    if trust not in ('observer', 'member', 'trusted', 'admin'):
        return jsonify({'error': 'Invalid trust level'}), 400
    with db_session() as db:
        db.execute('UPDATE federation_peers SET trust_level = ? WHERE node_id = ?', (trust, node_id))
        db.commit()
    return jsonify({'status': 'updated'})


@federation_bp.route('/api/federation/peers/<node_id>', methods=['DELETE'])
def api_federation_peer_remove(node_id):
    with db_session() as db:
        r = db.execute('DELETE FROM federation_peers WHERE node_id = ?', (node_id,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'removed'})


@federation_bp.route('/api/federation/peers/<peer_id>/verify', methods=['POST'])
def api_verify_peer(peer_id):
    """Verify a peer's identity by challenge-response using HMAC signatures."""
    with db_session() as db:
        peer = db.execute('SELECT * FROM federation_peers WHERE node_id = ?', (peer_id,)).fetchone()
    if not peer:
        return jsonify({'error': 'Peer not found'}), 404

    data = request.get_json() or {}
    # If this is a challenge request (no response yet), generate a nonce
    if 'response' not in data:
        nonce = os.urandom(16).hex()
        return jsonify({'challenge': nonce, 'peer_id': peer_id})

    # Verify the response: peer should have signed the challenge with their key
    challenge = data.get('challenge', '')
    response_sig = data.get('response', '')
    peer_public_key = peer['public_key'] if peer['public_key'] else ''
    if not peer_public_key:
        return jsonify({'error': 'Peer has no public key on file', 'verified': False}), 400

    # We cannot directly verify HMAC without the private key, but we can store
    # the peer's public key and check it matches what they claim
    priv_key, pub_key = _get_or_create_node_key()
    expected = _sign_payload(challenge, priv_key)

    # If the peer sent back our own signature as proof they know us, verify
    verified = response_sig == expected if data.get('self_verify') else False
    if verified:
        with db_session() as db:
            db.execute("UPDATE federation_peers SET last_seen = datetime('now') WHERE node_id = ?", (peer_id,))
            db.commit()

    return jsonify({'verified': verified, 'peer_id': peer_id, 'public_key': peer_public_key})


# ─── Supply Chain GeoJSON ───────────────────────────────────────────

@federation_bp.route('/api/federation/supply-chain')
def api_federation_supply_chain():
    """Return federation peers, offers, and requests as GeoJSON for map visualization."""
    with db_session() as db:
        peers = db.execute('SELECT * FROM federation_peers WHERE lat IS NOT NULL AND lng IS NOT NULL LIMIT 5000').fetchall()
        offers = db.execute("SELECT * FROM federation_offers WHERE status = 'active' LIMIT 5000").fetchall()
        requests_rows = db.execute("SELECT * FROM federation_requests WHERE status = 'active' LIMIT 500").fetchall()

    peer_map = {}
    features = []
    trust_colors = {'observer': '#888', 'member': '#5b9fff', 'trusted': '#4caf50', 'admin': '#ffc107'}

    for p in peers:
        d = dict(p)
        peer_map[d['node_id']] = d
        p_offers = [dict(o) for o in offers if o['node_id'] == d['node_id']]
        p_requests = [dict(r) for r in requests_rows if r['node_id'] == d['node_id']]
        features.append({
            'type': 'Feature',
            'geometry': {'type': 'Point', 'coordinates': [d['lng'], d['lat']]},
            'properties': {
                'type': 'peer', 'node_id': d['node_id'], 'name': d.get('node_name', d['node_id']),
                'trust_level': d.get('trust_level', 'observer'),
                'color': trust_colors.get(d.get('trust_level', 'observer'), '#888'),
                'offers': [{'item': o['item_type'], 'qty': o['quantity']} for o in p_offers],
                'requests': [{'item': r['item_type'], 'qty': r['quantity'], 'urgency': r.get('urgency', 'normal')} for r in p_requests],
            }
        })

    peer_ids = list(peer_map.keys())
    for i, pid1 in enumerate(peer_ids):
        for pid2 in peer_ids[i+1:]:
            p1_offers = {o['item_type'] for o in offers if o['node_id'] == pid1}
            p2_requests = {r['item_type'] for r in requests_rows if r['node_id'] == pid2}
            p2_offers = {o['item_type'] for o in offers if o['node_id'] == pid2}
            p1_requests = {r['item_type'] for r in requests_rows if r['node_id'] == pid1}
            matches = (p1_offers & p2_requests) | (p2_offers & p1_requests)
            if matches:
                features.append({
                    'type': 'Feature',
                    'geometry': {'type': 'LineString', 'coordinates': [
                        [peer_map[pid1]['lng'], peer_map[pid1]['lat']],
                        [peer_map[pid2]['lng'], peer_map[pid2]['lat']]
                    ]},
                    'properties': {
                        'type': 'trade_route',
                        'from': peer_map[pid1].get('node_name', pid1),
                        'to': peer_map[pid2].get('node_name', pid2),
                        'matched_items': list(matches),
                        'match_count': len(matches),
                    }
                })

    return jsonify({'type': 'FeatureCollection', 'features': features})


# ─── Federation Offers/Requests ─────────────────────────────────────

@federation_bp.route('/api/federation/offers')
def api_federation_offers():
    with db_session() as db:
        rows = db.execute("SELECT * FROM federation_offers WHERE status = 'active' ORDER BY created_at DESC LIMIT 5000").fetchall()
    return jsonify([dict(r) for r in rows])


@federation_bp.route('/api/federation/offers', methods=['POST'])
def api_federation_offer_create():
    data = request.get_json() or {}
    with db_session() as db:
        db.execute('INSERT INTO federation_offers (item_type, item_id, quantity, node_id, notes) VALUES (?,?,?,?,?)',
                   (data.get('item_type', ''), data.get('item_id'), data.get('quantity', 0),
                    data.get('node_id', ''), data.get('notes', '')))
        db.commit()
    log_activity('mutual_aid_offer_created', 'federation', f'Created mutual aid offer: {data.get("item_type", "")}')
    return jsonify({'status': 'created'})


@federation_bp.route('/api/federation/requests')
def api_federation_requests():
    with db_session() as db:
        rows = db.execute("SELECT * FROM federation_requests WHERE status = 'active' ORDER BY urgency DESC, created_at DESC LIMIT 500").fetchall()
    return jsonify([dict(r) for r in rows])


@federation_bp.route('/api/federation/requests', methods=['POST'])
def api_federation_request_create():
    data = request.get_json() or {}
    with db_session() as db:
        db.execute('INSERT INTO federation_requests (item_type, description, quantity, urgency, node_id) VALUES (?,?,?,?,?)',
                   (data.get('item_type', ''), data.get('description', ''), data.get('quantity', 0),
                    data.get('urgency', 'normal'), data.get('node_id', '')))
        db.commit()
    log_activity('mutual_aid_request_created', 'federation', f'Created mutual aid request: {data.get("item_type", "")}')
    return jsonify({'status': 'created'})


# ─── Federation Transactions ──────────────────────────────────────

@federation_bp.route('/api/federation/transactions')
def api_federation_transactions_list():
    """List all federation transactions with status."""
    with db_session() as db:
        rows = db.execute('SELECT * FROM federation_transactions ORDER BY created_at DESC LIMIT 200').fetchall()
    return jsonify([dict(r) for r in rows])


@federation_bp.route('/api/federation/transactions', methods=['POST'])
def api_federation_transactions_propose():
    """Match an offer to a request, create transaction with status='proposed'."""
    data = request.get_json() or {}
    offer_id = data.get('offer_id')
    request_id = data.get('request_id')
    if not data.get('item_type'):
        return jsonify({'error': 'item_type required'}), 400
    if not data.get('from_node_id') or not data.get('to_node_id'):
        return jsonify({'error': 'from_node_id and to_node_id required'}), 400
    with db_session() as db:
        cur = db.execute(
            'INSERT INTO federation_transactions (offer_id, request_id, from_node_id, to_node_id, item_type, quantity, status, notes) '
            'VALUES (?,?,?,?,?,?,?,?)',
            (offer_id, request_id, data['from_node_id'], data['to_node_id'],
             data['item_type'], data.get('quantity', 0), 'proposed', data.get('notes', '')))
        db.commit()
        tid = cur.lastrowid
    log_activity('federation_transaction', 'federation', f'Transaction #{tid} proposed: {data["item_type"]}')
    return jsonify({'id': tid, 'status': 'proposed'}), 201


@federation_bp.route('/api/federation/transactions/<int:tid>/accept', methods=['PUT'])
def api_federation_transactions_accept(tid):
    """Accept a proposed transaction."""
    with db_session() as db:
        row = db.execute('SELECT * FROM federation_transactions WHERE id = ?', (tid,)).fetchone()
        if not row:
            return jsonify({'error': 'Transaction not found'}), 404
        if row['status'] != 'proposed':
            return jsonify({'error': f'Cannot accept transaction in status: {row["status"]}'}), 400
        db.execute("UPDATE federation_transactions SET status = 'accepted', accepted_at = datetime('now'), updated_at = datetime('now') WHERE id = ?", (tid,))
        db.commit()
    log_activity('federation_transaction', 'federation', f'Transaction #{tid} accepted')
    return jsonify({'id': tid, 'status': 'accepted'})


@federation_bp.route('/api/federation/transactions/<int:tid>/deliver', methods=['PUT'])
def api_federation_transactions_deliver(tid):
    """Mark a transaction as delivered."""
    with db_session() as db:
        row = db.execute('SELECT * FROM federation_transactions WHERE id = ?', (tid,)).fetchone()
        if not row:
            return jsonify({'error': 'Transaction not found'}), 404
        if row['status'] != 'accepted':
            return jsonify({'error': f'Cannot deliver transaction in status: {row["status"]}'}), 400
        db.execute("UPDATE federation_transactions SET status = 'delivered', delivered_at = datetime('now'), updated_at = datetime('now') WHERE id = ?", (tid,))
        db.commit()
    log_activity('federation_transaction', 'federation', f'Transaction #{tid} delivered')
    return jsonify({'id': tid, 'status': 'delivered'})


@federation_bp.route('/api/federation/transactions/<int:tid>/confirm', methods=['PUT'])
def api_federation_transactions_confirm(tid):
    """Confirm delivery, update offer/request quantities."""
    with db_session() as db:
        row = db.execute('SELECT * FROM federation_transactions WHERE id = ?', (tid,)).fetchone()
        if not row:
            return jsonify({'error': 'Transaction not found'}), 404
        if row['status'] != 'delivered':
            return jsonify({'error': f'Cannot confirm transaction in status: {row["status"]}'}), 400
        db.execute("UPDATE federation_transactions SET status = 'confirmed', confirmed_at = datetime('now'), updated_at = datetime('now') WHERE id = ?", (tid,))
        # Decrement offer quantity
        if row['offer_id']:
            db.execute('UPDATE federation_offers SET quantity = MAX(0, quantity - ?) WHERE id = ?',
                       (row['quantity'], row['offer_id']))
        # Decrement request quantity
        if row['request_id']:
            db.execute('UPDATE federation_requests SET quantity = MAX(0, quantity - ?) WHERE id = ?',
                       (row['quantity'], row['request_id']))
        db.commit()
    log_activity('federation_transaction', 'federation', f'Transaction #{tid} confirmed')
    return jsonify({'id': tid, 'status': 'confirmed'})


# ─── Mutual Aid Agreements ──────────────────────────────────────────

@federation_bp.route('/api/federation/mutual-aid')
def api_mutual_aid_list():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM mutual_aid_agreements ORDER BY updated_at DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        for k in ('our_commitments', 'their_commitments'):
            d[k] = _safe_json_list(d[k], [])
        result.append(d)
    return jsonify(result)


@federation_bp.route('/api/federation/mutual-aid', methods=['POST'])
def api_mutual_aid_create():
    data = request.get_json() or {}
    if not data.get('title'):
        return jsonify({'error': 'Title required'}), 400
    with db_session() as db:
        cur = db.execute(
            'INSERT INTO mutual_aid_agreements (peer_node_id, peer_name, title, description, '
            'our_commitments, their_commitments, status, effective_date, expiry_date) '
            'VALUES (?,?,?,?,?,?,?,?,?)',
            (data.get('peer_node_id', ''), data.get('peer_name', ''), data['title'],
             data.get('description', ''),
             json.dumps(_safe_json_list(data.get('our_commitments'), [])),
             json.dumps(_safe_json_list(data.get('their_commitments'), [])),
             data.get('status', 'draft'),
             data.get('effective_date', ''), data.get('expiry_date', '')))
        db.commit()
        aid = cur.lastrowid
    log_activity('mutual_aid_create', 'federation', f'Agreement "{data["title"]}" created')
    return jsonify({'id': aid, 'status': 'created'}), 201


@federation_bp.route('/api/federation/mutual-aid/<int:aid>', methods=['PUT'])
def api_mutual_aid_update(aid):
    data = request.get_json() or {}
    with db_session() as db:
        fields, vals = [], []
        for k in ('title', 'description', 'status', 'effective_date', 'expiry_date', 'peer_name'):
            if k in data:
                fields.append(f'{k} = ?')
                vals.append(data[k])
        for k in ('our_commitments', 'their_commitments'):
            if k in data:
                fields.append(f'{k} = ?')
                vals.append(json.dumps(_safe_json_list(data[k], [])))
        if 'signed_by_us' in data:
            fields.append('signed_by_us = ?')
            vals.append(1 if data['signed_by_us'] else 0)
        if fields:
            fields.append("updated_at = datetime('now')")
            vals.append(aid)
            db.execute(f'UPDATE mutual_aid_agreements SET {", ".join(fields)} WHERE id = ?', vals)
            db.commit()
    return jsonify({'status': 'updated'})


@federation_bp.route('/api/federation/mutual-aid/<int:aid>', methods=['DELETE'])
def api_mutual_aid_delete(aid):
    with db_session() as db:
        r = db.execute('DELETE FROM mutual_aid_agreements WHERE id = ?', (aid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


@federation_bp.route('/api/federation/mutual-aid/<int:aid>/sign', methods=['POST'])
def api_mutual_aid_sign(aid):
    """Mark agreement as signed by us, update status to active if both signed."""
    with db_session() as db:
        db.execute("UPDATE mutual_aid_agreements SET signed_by_us = 1, updated_at = datetime('now') WHERE id = ?", (aid,))
        row = db.execute('SELECT signed_by_us, signed_by_peer FROM mutual_aid_agreements WHERE id = ?', (aid,)).fetchone()
        if row and row['signed_by_us'] and row['signed_by_peer']:
            db.execute("UPDATE mutual_aid_agreements SET status = 'active', updated_at = datetime('now') WHERE id = ?", (aid,))
        db.commit()
    log_activity('mutual_aid_sign', 'federation', f'Agreement #{aid} signed')
    return jsonify({'status': 'signed'})


# ─── Sit Board / Network Map ───────────────────────────────────────

@federation_bp.route('/api/federation/sitboard')
def api_federation_sitboard():
    """Aggregated situation from all peers."""
    with db_session() as db:
        rows = db.execute('SELECT * FROM federation_sitboard ORDER BY updated_at DESC LIMIT 5000').fetchall()
    return jsonify([dict(r) for r in rows])


@federation_bp.route('/api/federation/network-map')
def api_federation_network_map():
    """Returns all known nodes with positions for map overlay."""
    with db_session() as db:
        peers = [dict(r) for r in db.execute('SELECT node_id, node_name, trust_level, last_seen, ip FROM federation_peers LIMIT 1000').fetchall()]
        for p in peers:
            safe_name = p["node_name"].replace('%', '\\%').replace('_', '\\_')
            safe_id = p["node_id"].replace('%', '\\%').replace('_', '\\_')
            wp = db.execute("SELECT lat, lng FROM waypoints WHERE name LIKE ? ESCAPE '\\' OR notes LIKE ? ESCAPE '\\'",
                            (f'%{safe_name}%', f'%{safe_id}%')).fetchone()
            p['lat'] = wp['lat'] if wp else None
            p['lng'] = wp['lng'] if wp else None
    return jsonify(peers)


# ─── Dead Drop Encrypted Messaging ─────────────────────────────────

@federation_bp.route('/api/deaddrop/compose', methods=['POST'])
def api_deaddrop_compose():
    """Compose an encrypted message for dead drop exchange."""
    import hashlib, base64, os as _os
    data = request.get_json() or {}
    message = data.get('message', '').strip()
    recipient = data.get('recipient', '').strip()
    secret = data.get('secret', '').strip()
    if not message or not secret:
        return jsonify({'error': 'Message and shared secret are required'}), 400
    salt = _os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', secret.encode(), salt, 100000)
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        nonce = _os.urandom(12)
        aesgcm = AESGCM(key)
        encrypted = aesgcm.encrypt(nonce, message.encode('utf-8'), None)
        enc_data = base64.b64encode(salt + nonce + encrypted).decode()
    except ImportError:
        return jsonify({'error': 'cryptography package not installed \u2014 run: pip install cryptography'}), 500
    payload = {
        'version': 2,
        'type': 'nomad-deaddrop',
        'from_node': _get_node_id(),
        'from_name': _get_node_name(),
        'recipient': recipient,
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'data': enc_data,
        'checksum': hashlib.sha256(message.encode()).hexdigest()[:16]
    }
    return jsonify({'payload': payload, 'filename': f'deaddrop-{_get_node_id()[:4]}-{int(time.time())}.json'})


@federation_bp.route('/api/deaddrop/decrypt', methods=['POST'])
def api_deaddrop_decrypt():
    """Decrypt a dead drop message."""
    import hashlib, base64
    data = request.get_json() or {}
    payload = data.get('payload', {})
    secret = data.get('secret', '').strip()
    if not payload or not secret:
        return jsonify({'error': 'Payload and shared secret are required'}), 400
    if payload.get('type') != 'nomad-deaddrop':
        return jsonify({'error': 'Invalid dead drop message format'}), 400
    try:
        raw = base64.b64decode(payload['data'])
        version = payload.get('version', 1)
        if version >= 2:
            salt = raw[:16]
            key = hashlib.pbkdf2_hmac('sha256', secret.encode(), salt, 100000)
            try:
                from cryptography.hazmat.primitives.ciphers.aead import AESGCM
                nonce = raw[16:28]
                ciphertext = raw[28:]
                aesgcm = AESGCM(key)
                decrypted = aesgcm.decrypt(nonce, ciphertext, None).decode('utf-8')
            except ImportError:
                return jsonify({'error': 'cryptography package not installed \u2014 run: pip install cryptography'}), 500
        else:
            key = hashlib.sha256(secret.encode()).digest()
            decrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(raw)).decode('utf-8')
        expected = hashlib.sha256(decrypted.encode()).hexdigest()[:16]
        if expected != payload.get('checksum', ''):
            return jsonify({'error': 'Wrong secret or corrupted message'}), 400
        return jsonify({'message': decrypted, 'from_node': payload.get('from_node'), 'from_name': payload.get('from_name'), 'timestamp': payload.get('timestamp')})
    except Exception:
        return jsonify({'error': 'Decryption failed \u2014 wrong secret or corrupted data'}), 400


@federation_bp.route('/api/deaddrop/messages')
def api_deaddrop_messages():
    """List received dead drop messages."""
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM dead_drop_messages ORDER BY created_at DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    return jsonify([dict(r) for r in rows])


@federation_bp.route('/api/deaddrop/import', methods=['POST'])
def api_deaddrop_import():
    """Import a dead drop JSON file and store it."""
    data = request.get_json() or {}
    payload = data.get('payload', {})
    if payload.get('type') != 'nomad-deaddrop':
        return jsonify({'error': 'Invalid dead drop format'}), 400
    with db_session() as db:
        db.execute('INSERT INTO dead_drop_messages (from_node_id, from_name, recipient, encrypted_data, checksum, message_timestamp) VALUES (?,?,?,?,?,?)',
                   (payload.get('from_node', ''), payload.get('from_name', ''), payload.get('recipient', ''),
                    payload.get('data', ''), payload.get('checksum', ''), payload.get('timestamp', '')))
        db.commit()
    log_activity('deaddrop_import', 'comms', f'Imported message from {payload.get("from_name", "unknown")}')
    return jsonify({'status': 'imported'})


# ─── Community Readiness Dashboard (moved from routes_advanced) ──

@federation_bp.route('/api/federation/community-readiness')
def api_federation_community_readiness():
    """Aggregate readiness scores across all federated nodes."""
    with db_session() as db:
        rows = db.execute(
            'SELECT node_id, node_name, situation, updated_at FROM federation_sitboard '
            'ORDER BY updated_at DESC LIMIT 200').fetchall()

    CATEGORIES = ['water', 'food', 'medical', 'shelter', 'security', 'comms', 'power']
    nodes = []
    network_totals = {cat: [] for cat in CATEGORIES}

    for row in rows:
        sit = _safe_json_object(row['situation'], {})

        node_readiness = {}
        for cat in CATEGORIES:
            # Try to extract a readiness value (0-100) from the situation data
            val = sit.get(cat, sit.get(f'{cat}_readiness', sit.get(f'{cat}_status', None)))
            if val is not None:
                try:
                    val = float(val)
                except (ValueError, TypeError):
                    # Map text statuses to numbers
                    status_map = {'green': 100, 'good': 100, 'yellow': 60, 'caution': 60,
                                  'orange': 40, 'degraded': 40, 'red': 20, 'critical': 20,
                                  'black': 0, 'none': 0}
                    val = status_map.get(str(val).lower(), 50)
                node_readiness[cat] = val
                network_totals[cat].append(val)
            else:
                node_readiness[cat] = None

        nodes.append({
            'node_id': row['node_id'],
            'node_name': row['node_name'] or row['node_id'],
            'readiness': node_readiness,
            'updated_at': row['updated_at'],
        })

    # Compute network-wide averages
    network_summary = {}
    for cat in CATEGORIES:
        vals = network_totals[cat]
        if vals:
            network_summary[cat] = {
                'average': round(sum(vals) / len(vals), 1),
                'min': min(vals),
                'max': max(vals),
                'reporting': len(vals),
            }
        else:
            network_summary[cat] = {'average': None, 'min': None, 'max': None, 'reporting': 0}

    overall_vals = [v for vals in network_totals.values() for v in vals]
    overall_avg = round(sum(overall_vals) / len(overall_vals), 1) if overall_vals else None

    return jsonify({
        'overall_readiness': overall_avg,
        'categories': network_summary,
        'nodes': nodes,
        'node_count': len(nodes),
    })


# ─── Skill Matching (moved from routes_advanced) ────────────────

@federation_bp.route('/api/federation/skill-search')
def api_federation_skill_search():
    """Search for skills across local contacts and federation peers."""
    query = request.args.get('skill', '').strip().lower()
    if not query:
        return jsonify({'error': 'skill query param required'}), 400

    results = []
    with db_session() as db:
        # Local contacts with matching skills
        contacts = db.execute(
            "SELECT name, callsign, role, skills, phone FROM contacts "
            "WHERE LOWER(skills) LIKE ? OR LOWER(role) LIKE ?",
            (f'%{query}%', f'%{query}%')
        ).fetchall()
        for c in contacts:
            results.append({
                'source': 'local',
                'name': c['name'],
                'callsign': c['callsign'] or '',
                'role': c['role'] or '',
                'skills': c['skills'] or '',
                'phone': c['phone'] or '',
            })

        # Federation peer shared data (from sitboard situation JSON)
        peers = db.execute(
            'SELECT node_id, node_name, situation FROM federation_sitboard LIMIT 200').fetchall()
        for peer in peers:
            sit = _safe_json_object(peer['situation'], {})
            # Check shared_contacts or skills in situation data
            shared_contacts = _safe_json_list(sit.get('contacts', sit.get('shared_contacts', [])), [])
            for sc in shared_contacts:
                if isinstance(sc, dict):
                    sc_skills = str(sc.get('skills', '')).lower()
                    sc_role = str(sc.get('role', '')).lower()
                    if query in sc_skills or query in sc_role:
                        results.append({
                            'source': f'federation:{peer["node_name"] or peer["node_id"]}',
                            'name': sc.get('name', 'Unknown'),
                            'callsign': sc.get('callsign', ''),
                            'role': sc.get('role', ''),
                            'skills': sc.get('skills', ''),
                            'phone': '',
                        })

        # Also check community_resources table
        community = db.execute(
            "SELECT name, skills, contact, trust_level FROM community_resources "
            "WHERE LOWER(skills) LIKE ? LIMIT 200", (f'%{query}%',)
        ).fetchall()
        for cr in community:
            results.append({
                'source': 'community',
                'name': cr['name'],
                'callsign': '',
                'role': '',
                'skills': cr['skills'] or '',
                'phone': cr['contact'] or '',
            })

    return jsonify({'query': query, 'results': results, 'count': len(results)})


# ─── Distributed Alert Relay (moved from routes_advanced) ────────

@federation_bp.route('/api/federation/relay-alert', methods=['POST'])
def api_federation_relay_alert():
    """Send an alert to all trusted federation peers."""
    from datetime import datetime
    data = request.get_json() or {}
    alert_title = data.get('title', '').strip()
    alert_message = data.get('message', '').strip()
    alert_severity = data.get('severity', 'warning')

    if not alert_title or not alert_message:
        return jsonify({'error': 'title and message required'}), 400

    with db_session() as db:
        # Get node identity for the sender
        node_id_row = db.execute("SELECT value FROM settings WHERE key = 'node_id'").fetchone()
        node_name_row = db.execute("SELECT value FROM settings WHERE key = 'node_name'").fetchone()
        sender_id = node_id_row['value'] if node_id_row and node_id_row['value'] else 'unknown'
        sender_name = (node_name_row['value'] if node_name_row and node_name_row['value']
                       else platform.node()) or 'NOMAD'

        # Get trusted peers
        peers = [dict(r) for r in db.execute(
            "SELECT node_id, node_name, ip, port FROM federation_peers "
            "WHERE trust_level IN ('trusted', 'admin', 'member') "
            "AND ip != '' ORDER BY node_name").fetchall()]

    if not peers:
        return jsonify({'error': 'No trusted peers configured', 'sent': 0}), 404

    alert_payload = {
        'title': alert_title,
        'message': alert_message,
        'severity': alert_severity,
        'sender_id': sender_id,
        'sender_name': sender_name,
        'timestamp': datetime.now().isoformat(),
    }

    import requests as http_requests

    sent = 0
    failed = []
    for peer in peers:
        url = f'http://{peer["ip"]}:{peer["port"]}/api/federation/receive-alert'
        try:
            resp = http_requests.post(url, json=alert_payload, timeout=5)
            if resp.status_code < 300:
                sent += 1
            else:
                failed.append({'node': peer['node_name'] or peer['node_id'],
                               'error': f'HTTP {resp.status_code}'})
        except Exception:
            failed.append({'node': peer['node_name'] or peer['node_id'],
                           'error': 'Connection failed'})

    log_activity('alert_relayed', 'federation',
                 f'Alert "{alert_title}" sent to {sent}/{len(peers)} peers')

    return jsonify({
        'status': 'relayed',
        'sent': sent,
        'total_peers': len(peers),
        'failed': failed,
    })
