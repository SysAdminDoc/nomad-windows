"""Communications, radio, LAN messaging, serial, and mesh networking routes."""

import json
import os
import time
import threading
import logging

from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

from web.blueprints import error_response
from db import db_session, log_activity
from config import get_data_dir
from services.manager import format_size
from web.state import (
    _broadcast,
    _serial_state, _serial_conn,
    _mesh_state,
)
import web.state as _state
from web.utils import clone_json_fallback as _clone_json_fallback, safe_json_list as _safe_json_list

log = logging.getLogger('nomad.web')

comms_bp = Blueprint('comms', __name__)


def _normalize_radio_channels(value):
    channels = []
    for item in _safe_json_list(value, []):
        if isinstance(item, dict):
            channels.append(dict(item))
    return channels

@comms_bp.route('/api/lan/transfer/send', methods=['POST'])
def api_lan_transfer_send():
    """Send a file to another NOMAD node on the LAN."""
    if 'file' not in request.files:
        return error_response('No file provided')
    f = request.files['file']
    peer_ip = request.form.get('peer_ip', '').strip()
    if not peer_ip:
        return error_response('peer_ip required')
    # SSRF protection: reject loopback, link-local, and non-private-LAN IPs
    import ipaddress as _ipa
    try:
        ip_obj = _ipa.ip_address(peer_ip)
        if ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved or ip_obj.is_unspecified:
            return error_response('Invalid peer IP address')
    except ValueError:
        return error_response('Invalid IP address format')

    # Save locally first
    transfer_dir = os.path.join(get_data_dir(), 'transfers', 'outgoing')
    os.makedirs(transfer_dir, exist_ok=True)
    safe = secure_filename(f.filename)
    local_path = os.path.join(transfer_dir, safe)
    f.save(local_path)
    file_size = os.path.getsize(local_path)

    with db_session() as db:
        db.execute(
            'INSERT INTO lan_transfers (filename, file_size, direction, peer_ip, status) VALUES (?, ?, ?, ?, ?)',
            (safe, file_size, 'outgoing', peer_ip, 'sending')
        )
        db.commit()
        tid = db.execute('SELECT last_insert_rowid()').fetchone()[0]
    # Send in background
    def do_send():
        import requests as _req
        try:
            with open(local_path, 'rb') as fh:
                port = 8080
                _req.post(f'http://{peer_ip}:{port}/api/lan/transfer/receive',
                          files={'file': (safe, fh)}, timeout=300)
            with db_session() as db2:
                db2.execute('UPDATE lan_transfers SET status = ? WHERE id = ?', ('completed', tid))
                db2.commit()
        except Exception:
            with db_session() as db2:
                db2.execute('UPDATE lan_transfers SET status = ? WHERE id = ?', ('failed', tid))
                db2.commit()
    threading.Thread(target=do_send, daemon=True).start()
    return jsonify({'status': 'sending', 'transfer_id': tid, 'filename': safe})

@comms_bp.route('/api/lan/transfer/receive', methods=['POST'])
def api_lan_transfer_receive():
    """Receive a file from another NOMAD node."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    f = request.files['file']
    recv_dir = os.path.join(get_data_dir(), 'transfers', 'incoming')
    os.makedirs(recv_dir, exist_ok=True)
    safe = secure_filename(f.filename)
    f.save(os.path.join(recv_dir, safe))
    file_size = os.path.getsize(os.path.join(recv_dir, safe))

    with db_session() as db:
        db.execute(
            'INSERT INTO lan_transfers (filename, file_size, direction, peer_ip, peer_name, status) VALUES (?, ?, ?, ?, ?, ?)',
            (safe, file_size, 'incoming', request.remote_addr or '', request.form.get('sender', ''), 'completed')
        )
        db.commit()
        log_activity('lan_transfer', detail=f'Received {safe} ({file_size} bytes)')
    return jsonify({'status': 'received', 'filename': safe})

@comms_bp.route('/api/lan/transfers')
def api_lan_transfers():
    """List file transfers."""
    with db_session() as db:
        rows = db.execute('SELECT * FROM lan_transfers ORDER BY created_at DESC LIMIT 50').fetchall()
        return jsonify([dict(r) for r in rows])
# ─── HF Propagation Prediction (v5.0 Phase 8) ───────────────────

@comms_bp.route('/api/radio/propagation')
def api_radio_propagation():
    """Basic HF propagation prediction based on time, date, and estimated solar activity."""
    from datetime import datetime
    import math

    hour = datetime.now().hour
    month = datetime.now().month
    lat = request.args.get('lat', 40, type=float)

    # Solar angle approximation
    is_day = 6 <= hour <= 18
    solar_angle = 90 - abs(12 - hour) * 7.5

    # Seasonal ionosphere density factor
    summer_months = {5, 6, 7, 8}
    equinox_months = {3, 4, 9, 10}
    if month in summer_months:
        season_factor = 1.2
    elif month in equinox_months:
        season_factor = 1.0  # equinox = best propagation
    else:
        season_factor = 0.8

    # Estimate MUF (Maximum Usable Frequency)
    # Simplified: MUF peaks during day, drops at night
    base_muf = 15 if is_day else 5
    muf = base_muf * season_factor * (1 + math.sin(math.radians(max(solar_angle, 0))) * 0.5)

    bands = []
    band_list = [
        {'name': '160m', 'freq': 1.8, 'best': 'night', 'range': '500-2000 mi'},
        {'name': '80m', 'freq': 3.5, 'best': 'night', 'range': '100-1500 mi'},
        {'name': '40m', 'freq': 7.0, 'best': 'night/day', 'range': '300-3000 mi'},
        {'name': '20m', 'freq': 14.0, 'best': 'day', 'range': '1000-10000 mi'},
        {'name': '15m', 'freq': 21.0, 'best': 'day', 'range': '1500-12000 mi'},
        {'name': '10m', 'freq': 28.0, 'best': 'day peak', 'range': '2000-15000 mi'},
        {'name': '6m', 'freq': 50.0, 'best': 'sporadic', 'range': '100-1500 mi'},
    ]
    for b in band_list:
        if b['freq'] <= muf:
            status = 'OPEN'
            quality = 'excellent' if b['freq'] < muf * 0.7 else 'good' if b['freq'] < muf * 0.9 else 'marginal'
        else:
            status = 'CLOSED'
            quality = 'closed'
        bands.append({**b, 'status': status, 'quality': quality})

    return jsonify({
        'muf_estimate': round(muf, 1),
        'is_day': is_day,
        'solar_angle': round(solar_angle, 1),
        'season_factor': season_factor,
        'hour': hour,
        'bands': bands,
        'note': 'Simplified prediction — actual conditions depend on solar flux (SFI), K-index, and real-time ionospheric data.'
    })

@comms_bp.route('/api/lan/messages')
def api_lan_messages():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    after_id = request.args.get('after', 0, type=int)
    with db_session() as db:
        if after_id:
            rows = db.execute('SELECT * FROM lan_messages WHERE id > ? ORDER BY id ASC LIMIT ? OFFSET ?', (after_id, limit, offset)).fetchall()
        else:
            rows = db.execute('SELECT * FROM lan_messages ORDER BY id DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
            rows = list(reversed(rows))
        return jsonify([dict(r) for r in rows])
@comms_bp.route('/api/lan/messages', methods=['POST'])
def api_lan_send():
    data = request.get_json() or {}
    content = (data.get('content', '') or '').strip()
    if not content:
        return error_response('Empty message')
    sender = (data.get('sender', '') or '').strip() or 'Anonymous'
    msg_type = data.get('msg_type', 'text')
    with db_session() as db:
        cur = db.execute('INSERT INTO lan_messages (sender, content, msg_type) VALUES (?, ?, ?)',
                         (sender[:50], content[:2000], msg_type))
        db.commit()
        msg = db.execute('SELECT * FROM lan_messages WHERE id = ?', (cur.lastrowid,)).fetchone()
        return jsonify(dict(msg)), 201
@comms_bp.route('/api/lan/messages/clear', methods=['POST'])
def api_lan_clear():
    with db_session() as db:
        db.execute('DELETE FROM lan_messages')
        db.commit()
        log_activity('lan_messages_cleared', detail='Cleared LAN messages')
        return jsonify({'status': 'cleared'})
# ─── LAN Enhancements (v5.0 Phase 10) ──────────────────────────

@comms_bp.route('/api/lan/channels')
def api_lan_channels():
    """List LAN chat channels."""
    with db_session() as db:
        rows = db.execute('SELECT * FROM lan_channels ORDER BY name LIMIT 5000').fetchall()
        channels = [dict(r) for r in rows]
        if not channels:
            db.executemany('INSERT OR IGNORE INTO lan_channels (name) VALUES (?)',
                          [(ch,) for ch in ['General', 'Security', 'Medical', 'Logistics']])
            db.commit()
            channels = [{'name': ch} for ch in ['General', 'Security', 'Medical', 'Logistics']]
        return jsonify(channels)
@comms_bp.route('/api/lan/channels', methods=['POST'])
def api_lan_channel_create():
    """Create a LAN chat channel."""
    d = request.json or {}
    name = d.get('name', '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400
    with db_session() as db:
        db.execute('INSERT OR IGNORE INTO lan_channels (name, description) VALUES (?, ?)',
                   (name, d.get('description', '')))
        db.commit()
        return jsonify({'status': 'ok'})
@comms_bp.route('/api/lan/presence')
def api_lan_presence():
    """List known LAN nodes and their status."""
    with db_session() as db:
        rows = db.execute(
            "SELECT * FROM lan_presence WHERE last_seen >= datetime('now', '-5 minutes') ORDER BY node_name LIMIT 500"
        ).fetchall()
        return jsonify([dict(r) for r in rows])
@comms_bp.route('/api/lan/presence/heartbeat', methods=['POST'])
def api_lan_heartbeat():
    """Register/update LAN presence."""
    d = request.json or {}
    ip = request.remote_addr or d.get('ip', '')
    name = d.get('name', 'Unknown')
    version = d.get('version', '')
    with db_session() as db:
        db.execute(
            '''INSERT INTO lan_presence (node_name, ip, status, version, last_seen)
               VALUES (?, ?, 'online', ?, CURRENT_TIMESTAMP)
               ON CONFLICT(ip) DO UPDATE SET
               node_name = excluded.node_name, status = 'online', version = excluded.version, last_seen = CURRENT_TIMESTAMP''',
            (name, ip, version)
        )
        db.commit()
        return jsonify({'status': 'ok'})
@comms_bp.route('/api/comms/frequencies')
def api_comms_frequencies():
    try:
        limit = min(int(request.args.get('limit', 500)), 1000)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 500, 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM freq_database ORDER BY service, frequency LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    if not rows and offset == 0:
        _seed_frequencies()
        with db_session() as db:
            rows = db.execute('SELECT * FROM freq_database ORDER BY service, frequency LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    return jsonify([dict(r) for r in rows])

@comms_bp.route('/api/comms/frequencies', methods=['POST'])
def api_comms_freq_create():
    data = request.get_json() or {}
    with db_session() as db:
        db.execute('INSERT INTO freq_database (frequency, mode, bandwidth, service, description, region, license_required, priority, notes) VALUES (?,?,?,?,?,?,?,?,?)',
                   (data.get('frequency', 0), data.get('mode', 'FM'), data.get('bandwidth', ''),
                    data.get('service', ''), data.get('description', ''), data.get('region', 'US'),
                    data.get('license_required', 0), data.get('priority', 0), data.get('notes', '')))
        db.commit()
        return jsonify({'status': 'created'})
@comms_bp.route('/api/comms/frequencies/<int:fid>', methods=['DELETE'])
def api_comms_freq_delete(fid):
    with db_session() as db:
        r = db.execute('DELETE FROM freq_database WHERE id = ?', (fid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
        log_activity('frequency_deleted', 'comms', 'Deleted frequency')
        return jsonify({'status': 'deleted'})
def _seed_frequencies():
    """Seed standard emergency/preparedness frequencies (~340 entries covering 20+ services)."""
    freqs = [
        # ── FRS (Family Radio Service) — 22 channels ─────────────────
        (462.5625,'FM','12.5','FRS Ch 1','Family Radio — primary','US',0,10,'Most common FRS channel; shared with GMRS'),
        (462.5875,'FM','12.5','FRS Ch 2','Family Radio — secondary','US',0,5,'Shared with GMRS'),
        (462.6125,'FM','12.5','FRS Ch 3','Family Radio — neighborhood','US',0,5,'Shared with GMRS'),
        (462.6375,'FM','12.5','FRS Ch 4','Family Radio','US',0,3,'Shared with GMRS'),
        (462.6625,'FM','12.5','FRS Ch 5','Family Radio','US',0,3,'Shared with GMRS'),
        (462.6875,'FM','12.5','FRS Ch 6','Family Radio','US',0,3,'Shared with GMRS'),
        (462.7125,'FM','12.5','FRS Ch 7','Family Radio','US',0,3,'Shared with GMRS'),
        (467.5625,'FM','12.5','FRS Ch 8','FRS only (low power)','US',0,2,'0.5W max'),
        (467.5875,'FM','12.5','FRS Ch 9','FRS only (low power)','US',0,2,'0.5W max'),
        (467.6125,'FM','12.5','FRS Ch 10','FRS only (low power)','US',0,2,'0.5W max'),
        (467.6375,'FM','12.5','FRS Ch 11','FRS only (low power)','US',0,2,'0.5W max'),
        (467.6625,'FM','12.5','FRS Ch 12','FRS only (low power)','US',0,2,'0.5W max'),
        (467.6875,'FM','12.5','FRS Ch 13','FRS only (low power)','US',0,2,'0.5W max'),
        (467.7125,'FM','12.5','FRS Ch 14','FRS only (low power)','US',0,2,'0.5W max'),
        (462.5500,'FM','12.5','FRS Ch 15','Family Radio','US',0,3,'Shared with GMRS'),
        (462.5750,'FM','12.5','FRS Ch 16','Family Radio','US',0,3,'Shared with GMRS'),
        (462.6000,'FM','12.5','FRS Ch 17','Family Radio','US',0,3,'Shared with GMRS'),
        (462.6250,'FM','12.5','FRS Ch 18','Family Radio','US',0,3,'Shared with GMRS'),
        (462.6500,'FM','12.5','FRS Ch 19','Family Radio','US',0,3,'Shared with GMRS'),
        (462.6750,'FM','12.5','FRS Ch 20','Family Radio','US',0,3,'Shared with GMRS'),
        (462.7000,'FM','12.5','FRS Ch 21','Family Radio','US',0,3,'Shared with GMRS'),
        (462.7250,'FM','12.5','FRS Ch 22','Family Radio','US',0,3,'Shared with GMRS'),
        # ── GMRS Repeater Pairs (8 channels) ────────────────────────
        # Output (talk-around) on 462.xxx, input on 467.xxx
        (462.5500,'FM','25','GMRS RPT 15R','GMRS repeater output Ch 15R','US',1,4,'Input 467.5500; GMRS license required'),
        (462.5750,'FM','25','GMRS RPT 16R','GMRS repeater output Ch 16R','US',1,4,'Input 467.5750'),
        (462.6000,'FM','25','GMRS RPT 17R','GMRS repeater output Ch 17R','US',1,4,'Input 467.6000'),
        (462.6250,'FM','25','GMRS RPT 18R','GMRS repeater output Ch 18R','US',1,4,'Input 467.6250'),
        (462.6500,'FM','25','GMRS RPT 19R','GMRS repeater output Ch 19R','US',1,4,'Input 467.6500'),
        (462.6750,'FM','25','GMRS RPT 20R','GMRS repeater output Ch 20R','US',1,4,'Input 467.6750'),
        (462.7000,'FM','25','GMRS RPT 21R','GMRS repeater output Ch 21R','US',1,4,'Input 467.7000'),
        (462.7250,'FM','25','GMRS RPT 22R','GMRS repeater output Ch 22R','US',1,4,'Input 467.7250'),
        # ── MURS — 5 channels ────────────────────────────────────────
        (151.820,'FM','11.25','MURS Ch 1','Multi-Use Radio — no license','US',0,8,'5W max; good for property/neighborhood'),
        (151.880,'FM','11.25','MURS Ch 2','Multi-Use Radio','US',0,5,'5W max'),
        (151.940,'FM','11.25','MURS Ch 3','Multi-Use Radio','US',0,5,'5W max'),
        (154.570,'FM','20','MURS Ch 4','Multi-Use Radio (wide)','US',0,4,'5W max; 20 kHz bandwidth'),
        (154.600,'FM','20','MURS Ch 5','Multi-Use Radio (wide)','US',0,4,'5W max; 20 kHz bandwidth'),
        # ── Marine VHF — 20 common channels ─────────────────────────
        (156.800,'FM','25','Marine Ch 16','Intl distress/safety/calling','US',0,10,'Monitored by USCG; primary marine emergency'),
        (156.300,'FM','25','Marine Ch 6','Intership safety','US',0,7,'Ship-to-ship safety comms'),
        (156.450,'FM','25','Marine Ch 9','Secondary calling/boater','US',0,5,'Non-commercial calling'),
        (156.650,'FM','25','Marine Ch 13','Bridge-to-bridge navigation','US',0,8,'1W; nav safety near bridges/locks'),
        (157.100,'FM','25','Marine Ch 22A','USCG liaison','US',0,7,'Coast Guard marine info broadcasts'),
        (156.425,'FM','25','Marine Ch 68','Non-commercial','US',0,4,'Recreational boaters'),
        (156.475,'FM','25','Marine Ch 69','Non-commercial','US',0,3,'Recreational boaters'),
        (156.525,'FM','25','Marine Ch 70','DSC (Digital Selective Calling)','US',0,6,'Automated digital distress; do not voice'),
        (156.575,'FM','25','Marine Ch 71','Non-commercial','US',0,3,'Recreational boaters'),
        (156.625,'FM','25','Marine Ch 72','Non-commercial (ship-to-ship)','US',0,4,'Common ship-to-ship'),
        (156.925,'FM','25','Marine Ch 78A','Non-commercial','US',0,3,''),
        (156.975,'FM','25','Marine Ch 79A','Non-commercial','US',0,3,''),
        (157.025,'FM','25','Marine Ch 80A','Non-commercial','US',0,3,''),
        (157.075,'FM','25','Marine Ch 81A','Non-commercial','US',0,3,''),
        (157.125,'FM','25','Marine Ch 82A','Non-commercial','US',0,3,''),
        (157.175,'FM','25','Marine Ch 83A','USCG working','US',0,4,'Coast Guard working channel'),
        (156.750,'FM','25','Marine Ch 15','Environmental/ship movement','US',0,3,'1W; towing operations'),
        (156.550,'FM','25','Marine Ch 67','Commercial/bridge','US',0,3,'Commercial vessel ops'),
        (156.375,'FM','25','Marine Ch 7A','Commercial','US',0,3,'Commercial vessel ops'),
        (157.150,'FM','25','Marine Ch 84','Public correspondence','US',0,2,''),
        # ── CB Radio — 40 channels ───────────────────────────────────
        (26.965,'AM','8','CB Ch 1','Citizens Band','US',0,2,''),
        (26.975,'AM','8','CB Ch 2','Citizens Band','US',0,2,''),
        (26.985,'AM','8','CB Ch 3','Citizens Band','US',0,2,''),
        (27.005,'AM','8','CB Ch 4','Citizens Band','US',0,2,''),
        (27.015,'AM','8','CB Ch 5','Citizens Band','US',0,2,''),
        (27.025,'AM','8','CB Ch 6','Citizens Band — SSB calling','US',0,4,'Unofficial SSB calling'),
        (27.035,'AM','8','CB Ch 7','Citizens Band','US',0,2,''),
        (27.055,'AM','8','CB Ch 8','Citizens Band','US',0,2,''),
        (27.065,'AM','8','CB Ch 9','CB Emergency channel','US',0,8,'Official emergency; monitored by REACT'),
        (27.075,'AM','8','CB Ch 10','Citizens Band — truckers','US',0,3,'Regional trucker channel'),
        (27.085,'AM','8','CB Ch 11','Citizens Band','US',0,2,''),
        (27.105,'AM','8','CB Ch 12','Citizens Band','US',0,2,''),
        (27.115,'AM','8','CB Ch 13','Citizens Band','US',0,2,''),
        (27.125,'AM','8','CB Ch 14','Citizens Band','US',0,2,''),
        (27.135,'AM','8','CB Ch 15','Citizens Band','US',0,2,''),
        (27.155,'AM','8','CB Ch 16','Citizens Band','US',0,2,''),
        (27.165,'AM','8','CB Ch 17','Citizens Band','US',0,2,''),
        (27.175,'AM','8','CB Ch 18','Citizens Band','US',0,2,''),
        (27.185,'AM','8','CB Ch 19','Highway/trucker channel','US',0,6,'Primary trucker channel; good for road intel'),
        (27.205,'AM','8','CB Ch 20','Citizens Band','US',0,2,''),
        (27.215,'AM','8','CB Ch 21','Citizens Band','US',0,2,''),
        (27.225,'AM','8','CB Ch 22','Citizens Band','US',0,2,''),
        (27.255,'AM','8','CB Ch 23','Citizens Band','US',0,2,''),
        (27.235,'AM','8','CB Ch 24','Citizens Band','US',0,2,''),
        (27.245,'AM','8','CB Ch 25','Citizens Band','US',0,2,''),
        (27.265,'AM','8','CB Ch 26','Citizens Band','US',0,2,''),
        (27.275,'AM','8','CB Ch 27','Citizens Band','US',0,2,''),
        (27.285,'AM','8','CB Ch 28','Citizens Band','US',0,2,''),
        (27.295,'AM','8','CB Ch 29','Citizens Band','US',0,2,''),
        (27.305,'AM','8','CB Ch 30','Citizens Band','US',0,2,''),
        (27.315,'AM','8','CB Ch 31','Citizens Band','US',0,2,''),
        (27.325,'AM','8','CB Ch 32','Citizens Band','US',0,2,''),
        (27.335,'AM','8','CB Ch 33','Citizens Band','US',0,2,''),
        (27.345,'AM','8','CB Ch 34','Citizens Band','US',0,2,''),
        (27.355,'AM','8','CB Ch 35','Citizens Band — SSB','US',0,3,'Unofficial SSB activity'),
        (27.365,'AM','8','CB Ch 36','Citizens Band — SSB','US',0,3,'Unofficial SSB activity'),
        (27.375,'AM','8','CB Ch 37','Citizens Band — SSB','US',0,3,'Unofficial SSB activity'),
        (27.385,'AM','8','CB Ch 38','Citizens Band — SSB','US',0,3,'LSB common; SSB DX'),
        (27.395,'AM','8','CB Ch 39','Citizens Band','US',0,2,''),
        (27.405,'AM','8','CB Ch 40','Citizens Band','US',0,2,''),
        # ── NOAA Weather Radio — 7 channels ─────────────────────────
        (162.400,'FM','','NOAA WX 1','Weather broadcast (WX1)','US',0,10,'Check NOAA for your local transmitter'),
        (162.425,'FM','','NOAA WX 2','Weather broadcast (WX2)','US',0,10,''),
        (162.450,'FM','','NOAA WX 3','Weather broadcast (WX3)','US',0,10,''),
        (162.475,'FM','','NOAA WX 4','Weather broadcast (WX4)','US',0,10,''),
        (162.500,'FM','','NOAA WX 5','Weather broadcast (WX5)','US',0,10,''),
        (162.525,'FM','','NOAA WX 6','Weather broadcast (WX6)','US',0,10,''),
        (162.550,'FM','','NOAA WX 7','Weather broadcast (WX7)','US',0,10,''),
        # ── 2m Amateur (144-148 MHz) — 20 common frequencies ────────
        (144.390,'FM','12.5','2m APRS','APRS digital (packet)','US',1,8,'Automatic Packet Reporting System'),
        (146.520,'FM','15','2m Simplex Call','National VHF calling frequency','US',1,10,'Primary simplex; ham license required'),
        (146.550,'FM','15','2m Simplex','Common simplex — ARES/RACES','US',1,7,'Emergency/public service'),
        (146.580,'FM','15','2m Simplex','Simplex','US',1,4,''),
        (146.460,'FM','15','2m Simplex','Simplex','US',1,4,''),
        (146.490,'FM','15','2m Simplex','Simplex','US',1,4,''),
        (147.420,'FM','15','2m Simplex','Emergency simplex','US',1,6,'ARES/RACES emergency'),
        (147.450,'FM','15','2m Simplex','Simplex','US',1,3,''),
        (147.480,'FM','15','2m Simplex','Simplex','US',1,3,''),
        (147.510,'FM','15','2m Simplex','Simplex','US',1,3,''),
        (147.540,'FM','15','2m Simplex','Simplex','US',1,3,''),
        (147.570,'FM','15','2m Simplex','Simplex','US',1,3,''),
        (145.010,'FM','15','2m Repeater In','Common repeater input','US',1,3,'Output +600 kHz'),
        (145.610,'FM','15','2m Repeater Out','Common repeater output','US',1,3,'Input -600 kHz'),
        (146.610,'FM','15','2m Repeater Out','Common repeater output','US',1,4,'Input -600 kHz'),
        (146.670,'FM','15','2m Repeater Out','Common repeater output','US',1,4,'Input -600 kHz'),
        (146.760,'FM','15','2m Repeater Out','Common repeater output','US',1,4,'Input -600 kHz'),
        (146.820,'FM','15','2m Repeater Out','Common repeater output','US',1,4,'Input -600 kHz'),
        (146.880,'FM','15','2m Repeater Out','Common repeater output','US',1,4,'Input -600 kHz'),
        (146.940,'FM','15','2m Repeater Out','Common repeater output','US',1,4,'Input -600 kHz'),
        # ── 70cm Amateur (420-450 MHz) — 15 common frequencies ──────
        (446.000,'FM','12.5','70cm Simplex Call','National UHF calling frequency','US',1,9,'Primary UHF simplex; ham license required'),
        (446.500,'FM','12.5','70cm Simplex','Common UHF simplex','US',1,5,''),
        (447.000,'FM','12.5','70cm Simplex','UHF simplex','US',1,3,''),
        (446.050,'FM','12.5','70cm Simplex','UHF simplex','US',1,3,''),
        (446.100,'FM','12.5','70cm Simplex','UHF simplex','US',1,3,''),
        (446.150,'FM','12.5','70cm Simplex','UHF simplex','US',1,3,''),
        (443.000,'FM','12.5','70cm Repeater Out','Common repeater output','US',1,3,'Input +5 MHz'),
        (443.200,'FM','12.5','70cm Repeater Out','Common repeater output','US',1,3,'Input +5 MHz'),
        (443.500,'FM','12.5','70cm Repeater Out','Common repeater output','US',1,3,'Input +5 MHz'),
        (443.800,'FM','12.5','70cm Repeater Out','Common repeater output','US',1,3,'Input +5 MHz'),
        (444.000,'FM','12.5','70cm Repeater Out','Common repeater output','US',1,3,'Input +5 MHz'),
        (444.200,'FM','12.5','70cm Repeater Out','Common repeater output','US',1,3,'Input +5 MHz'),
        (444.500,'FM','12.5','70cm Repeater Out','Common repeater output','US',1,3,'Input +5 MHz'),
        (444.800,'FM','12.5','70cm Repeater Out','Common repeater output','US',1,3,'Input +5 MHz'),
        (444.950,'FM','12.5','70cm Repeater Out','Common repeater output','US',1,3,'Input +5 MHz'),
        # ── HF Amateur — 20 common frequencies ──────────────────────
        (1.900,'LSB','3','160m SSB','Top Band — night local','US',1,3,'Night propagation; 200-500 mi'),
        (3.860,'LSB','3','75m SSB','Emergency/traffic net','US',1,8,'Night propagation; ARES nets'),
        (3.885,'LSB','3','75m SSB','AM calling/ragchew','US',1,4,'Night; popular AM window'),
        (3.985,'LSB','3','75m SSB','SSB net frequency','US',1,4,'Night propagation'),
        (7.185,'LSB','3','40m SSB','General SSB activity','US',1,5,'Day/night; 300-1000 mi'),
        (7.260,'LSB','3','40m SSB','Emergency HF net — regional','US',1,10,'Primary 40m emergency; day propagation'),
        (7.290,'LSB','3','40m SSB','Traffic/NTS nets','US',1,5,'National Traffic System'),
        (10.130,'USB','3','30m Digital','Digital modes (PSK, FT8)','US',1,3,'CW/digital only band'),
        (14.060,'CW','0.5','20m CW','QRP calling frequency','US',1,3,'CW; low-power ops'),
        (14.285,'USB','3','20m SSB','SSB activity center','US',1,4,'Day; worldwide propagation'),
        (14.300,'USB','3','20m SSB','Intl emergency/maritime mobile net','US',1,9,'Primary HF emergency; long-distance day'),
        (14.313,'USB','3','20m SSB','Intercon/maritime net','US',1,5,'Commonly active net'),
        (14.346,'USB','3','20m SSB','Survival net','US',1,4,'Prepper/survival community'),
        (18.130,'USB','3','17m SSB','SSB activity','US',1,3,'Day; DX propagation'),
        (21.360,'USB','3','15m SSB','SSB activity','US',1,3,'Day; solar-cycle dependent'),
        (21.390,'USB','3','15m SSB','SSB net frequency','US',1,4,'Day propagation'),
        (24.960,'USB','3','12m SSB','SSB activity','US',1,2,'Day; solar-cycle dependent'),
        (28.400,'USB','3','10m SSB','SSB calling frequency','US',1,5,'Day; 10m band opening indicator'),
        (28.600,'FM','15','10m FM Call','FM simplex calling','US',1,3,'29.6 FM repeater subband'),
        (50.125,'USB','3','6m SSB','SSB calling frequency','US',1,4,'Magic band; sporadic E propagation'),
        # ── Emergency & Special ──────────────────────────────────────
        (121.500,'AM','','Aviation Distress','Aircraft emergency/guard (121.5)','US',0,10,'Intl aviation distress; ELT freq'),
        (123.100,'AM','','Aviation SAR','Search and Rescue','US',0,6,'SAR operations'),
        (156.800,'FM','25','Marine Distress','Marine Ch 16 — distress/safety','US',0,10,'Monitored by USCG worldwide'),
        (243.000,'AM','','Military Distress','Military UHF guard frequency','US',0,7,'Military emergency; NATO standard'),
        (462.675,'FM','12.5','GMRS Emergency','GMRS Ch 20 — emergency/travel','US',1,8,'GMRS emergency calling; widely recognized'),
        (155.160,'FM','','SAR Primary','Search and Rescue — ground','US',0,5,'SAR ground teams'),
        (138.225,'FM','','FEMA Primary','Federal Emergency Mgmt Agency','US',0,5,'Federal disaster coordination'),
        (155.475,'FM','','Red Cross Disaster','American Red Cross','US',0,5,'Disaster relief coordination'),
        (163.100,'FM','','Natl Guard Emer','National Guard emergency','US',0,4,'State emergency activation'),
        (462.950,'FM','12.5','Itinerant Business','Common business/event frequency','US',0,3,'Part 90; no license needed for itinerant'),
        # ── Meshtastic / LoRa ────────────────────────────────────────
        (906.875,'LoRa','125','Meshtastic US','Default Meshtastic — off-grid mesh text','US',0,9,'No license; 1W; 915 ISM band'),
        # ── PMR446 (EU license-free) — 16 channels ─────────────────
        (446.00625,'FM','12.5','PMR446 Ch 1','EU license-free radio','EU',0,7,'0.5W; European equivalent of FRS'),
        (446.01875,'FM','12.5','PMR446 Ch 2','EU license-free radio','EU',0,5,''),
        (446.03125,'FM','12.5','PMR446 Ch 3','EU license-free radio','EU',0,5,''),
        (446.04375,'FM','12.5','PMR446 Ch 4','EU license-free radio','EU',0,4,''),
        (446.05625,'FM','12.5','PMR446 Ch 5','EU license-free radio','EU',0,4,''),
        (446.06875,'FM','12.5','PMR446 Ch 6','EU license-free radio','EU',0,4,''),
        (446.08125,'FM','12.5','PMR446 Ch 7','EU license-free radio','EU',0,4,''),
        (446.09375,'FM','12.5','PMR446 Ch 8','EU license-free radio','EU',0,4,'Emergency calling channel in some countries'),
        (446.10625,'FM','6.25','PMR446 Ch 9','Digital PMR446','EU',0,3,'dPMR446 digital'),
        (446.11875,'FM','6.25','PMR446 Ch 10','Digital PMR446','EU',0,3,''),
        (446.13125,'FM','6.25','PMR446 Ch 11','Digital PMR446','EU',0,3,''),
        (446.14375,'FM','6.25','PMR446 Ch 12','Digital PMR446','EU',0,3,''),
        (446.15625,'FM','6.25','PMR446 Ch 13','Digital PMR446','EU',0,3,''),
        (446.16875,'FM','6.25','PMR446 Ch 14','Digital PMR446','EU',0,3,''),
        (446.18125,'FM','6.25','PMR446 Ch 15','Digital PMR446','EU',0,3,''),
        (446.19375,'FM','6.25','PMR446 Ch 16','Digital PMR446','EU',0,3,''),
        # ── LPD433 (EU low-power) — 10 key channels ────────────────
        (433.075,'FM','25','LPD433 Ch 1','EU low-power device','EU',0,3,'10mW; unlicensed; short range'),
        (433.100,'FM','25','LPD433 Ch 2','EU low-power device','EU',0,3,''),
        (433.125,'FM','25','LPD433 Ch 3','EU low-power device','EU',0,2,''),
        (433.150,'FM','25','LPD433 Ch 4','EU low-power device','EU',0,2,''),
        (433.175,'FM','25','LPD433 Ch 5','EU low-power device','EU',0,2,''),
        (433.200,'FM','25','LPD433 Ch 6','EU low-power device','EU',0,2,''),
        (433.225,'FM','25','LPD433 Ch 7','EU low-power device','EU',0,2,''),
        (433.250,'FM','25','LPD433 Ch 8','EU low-power device','EU',0,2,''),
        (433.275,'FM','25','LPD433 Ch 9','EU low-power device','EU',0,2,''),
        (433.300,'FM','25','LPD433 Ch 10','EU low-power device','EU',0,2,''),
        # ── Aviation (AM) — 15 common frequencies ──────────────────
        (118.000,'AM','25','Aviation Approach','Common approach control','Intl',0,3,'ATC approach frequency'),
        (119.100,'AM','25','Aviation Approach','Busy metro approach','Intl',0,3,''),
        (120.500,'AM','25','Aviation Tower','Common tower frequency','Intl',0,3,''),
        (121.500,'AM','25','Aviation ELT','Emergency Locator Transmitter','Intl',0,10,'International distress; satellite-monitored'),
        (121.600,'AM','25','Aviation Ground','Civil air patrol','Intl',0,3,''),
        (121.950,'AM','25','Aviation Unicom','Airport advisory','Intl',0,4,'Uncontrolled airports'),
        (122.750,'AM','25','Aviation Air-Air','Air-to-air communication','Intl',0,4,'Pilot-to-pilot'),
        (122.800,'AM','25','Aviation Unicom','Airport advisory','Intl',0,4,'Common Unicom'),
        (122.900,'AM','25','Aviation Multicom','No tower — common traffic','Intl',0,5,'Self-announce at uncontrolled fields'),
        (123.025,'AM','25','Aviation Heli','Helicopter air-to-air','Intl',0,3,''),
        (123.100,'AM','25','Aviation SAR','Search and Rescue','Intl',0,6,'SAR operations coordination'),
        (123.450,'AM','25','Aviation Air-Air 2','Unofficial pilot frequency','Intl',0,3,'Common air-to-air chat'),
        (126.200,'AM','25','Aviation Approach','Common center frequency','Intl',0,3,''),
        (128.825,'AM','25','Aviation ATIS','Automated Terminal Info','Intl',0,3,'Weather and airport info'),
        (135.000,'AM','25','Aviation Oceanic','Oceanic control','Intl',0,2,'Long-range HF/VHF position reports'),
        # ── Railroad — 8 common frequencies ────────────────────────
        (160.215,'FM','12.5','Railroad Ch 1','AAR Channel 1 — road','US',0,4,'Railroad dispatch/road operations'),
        (160.245,'FM','12.5','Railroad Ch 2','AAR Channel 2 — road','US',0,4,''),
        (160.320,'FM','12.5','Railroad Yard','Common yard frequency','US',0,3,'Yard switching operations'),
        (160.560,'FM','12.5','Railroad Dispatch','Dispatch channel','US',0,3,''),
        (160.800,'FM','12.5','Railroad Emer','Railroad emergency','US',0,5,'Emergency coordination'),
        (161.100,'FM','12.5','Railroad End-Train','End-of-train device','US',0,2,'EOT telemetry'),
        (161.205,'FM','12.5','Railroad Ch 3','AAR Channel 3','US',0,3,''),
        (161.370,'FM','12.5','Railroad Police','Railroad police','US',0,3,'Law enforcement/security'),
        # ── Shortwave Broadcast Bands — 15 key frequencies ─────────
        (3.330,'AM','5','CHU Canada 3.3','Canadian time signal','Intl',0,6,'24/7 time signal; useful for clock sync'),
        (5.000,'AM','5','WWV 5 MHz','NIST time signal','US',0,8,'Official US time; propagation indicator'),
        (7.850,'AM','5','SW Radio Int','Shortwave broadcast band','Intl',0,2,'41m band; evening listening'),
        (9.650,'AM','5','SW BBC/VOA','Shortwave broadcast band','Intl',0,3,'31m band; international broadcasts'),
        (10.000,'AM','5','WWV 10 MHz','NIST time signal','US',0,8,'Most reliable WWV frequency'),
        (11.750,'AM','5','SW Broadcast 25m','Shortwave broadcast band','Intl',0,2,'25m band; afternoon/evening'),
        (13.570,'AM','5','SW Broadcast 22m','Shortwave broadcast band','Intl',0,2,'22m band; daytime'),
        (15.000,'AM','5','WWV 15 MHz','NIST time signal','US',0,7,'Daytime propagation'),
        (15.400,'AM','5','SW Broadcast 19m','Shortwave broadcast band','Intl',0,2,'19m band; daytime; news services'),
        (17.800,'AM','5','SW Broadcast 16m','Shortwave broadcast band','Intl',0,2,'16m band; midday'),
        (2.500,'AM','5','WWV 2.5 MHz','NIST time signal','US',0,5,'Night only; short range'),
        (20.000,'AM','5','WWV 20 MHz','NIST time signal','US',0,5,'Daytime only; MUF indicator'),
        (25.000,'AM','5','WWV 25 MHz','NIST time signal','US',0,3,'Rarely heard; high solar activity only'),
        (4.996,'AM','5','RWM Russia','Russian time signal','Intl',0,3,'Useful for propagation checking'),
        (9.996,'AM','5','RWM Russia 10','Russian time signal','Intl',0,3,'10 MHz Russian time standard'),
        # ── ISM / Unlicensed Bands — 10 key entries ────────────────
        (27.120,'AM','','ISM 27 MHz','Industrial/Scientific/Medical','Intl',0,2,'RC toys, baby monitors, low-power devices'),
        (40.680,'FM','','ISM 40 MHz','ISM band','Intl',0,1,'Industrial heating'),
        (315.000,'OOK','','ISM 315','Garage doors/key fobs (US)','US',0,2,'One-way devices; no voice'),
        (433.920,'OOK','','ISM 433','Remote controls/sensors (EU)','EU',0,2,'Weather stations, remotes, LoRa'),
        (868.000,'LoRa','125','LoRaWAN EU','LoRa/IoT devices (EU)','EU',0,4,'Meshtastic EU; IoT sensors'),
        (915.000,'LoRa','125','LoRaWAN US','LoRa/IoT devices (US)','US',0,4,'IoT sensors; mesh networking'),
        (2400.000,'FM','','ISM 2.4 GHz','WiFi / Bluetooth / Zigbee','Intl',0,3,'Crowded band; WiFi Ch 1-14'),
        (5800.000,'FM','','ISM 5.8 GHz','WiFi 5 GHz / FPV drones','Intl',0,2,'802.11a/ac/ax; less crowded'),
        (900.000,'FM','','ISM 900 MHz','Cordless phones/LoRa','US',0,2,'900 MHz ISM devices'),
        (869.525,'FM','','SRD 869','EU short-range alarm freq','EU',0,3,'Emergency/alarm applications; 500mW'),
        # ── GMRS Simplex (additional common) ───────────────────────
        (462.5625,'FM','25','GMRS Ch 1','GMRS simplex (wideband)','US',1,5,'5W; shared with FRS; GMRS license allows 5W'),
        (462.5875,'FM','25','GMRS Ch 2','GMRS simplex','US',1,4,''),
        (462.6125,'FM','25','GMRS Ch 3','GMRS simplex','US',1,4,''),
        (462.6375,'FM','25','GMRS Ch 4','GMRS simplex','US',1,3,''),
        (462.6625,'FM','25','GMRS Ch 5','GMRS simplex','US',1,3,''),
        (462.6875,'FM','25','GMRS Ch 6','GMRS simplex','US',1,3,''),
        (462.7125,'FM','25','GMRS Ch 7','GMRS simplex','US',1,3,''),
        # ── Additional Amateur HF (disaster prep) ──────────────────
        (3.818,'LSB','3','75m Intl Assistance','Maritime mobile/international assistance','Intl',1,5,'Disaster relief net'),
        (5.3305,'USB','3','60m Ch 1','60m channelized — emergency','US',1,6,'SHARES/FEMA HF emergency; 100W ERP'),
        (5.3465,'USB','3','60m Ch 2','60m channelized','US',1,5,'SHARES secondary'),
        (5.3570,'USB','3','60m Ch 3','60m channelized','US',1,4,''),
        (5.3715,'USB','3','60m Ch 4','60m channelized','US',1,4,''),
        (5.4035,'USB','3','60m Ch 5','60m channelized','US',1,4,''),
        (7.095,'LSB','3','40m Waterway Net','Marine/waterway net','Intl',1,4,'Cruisers, maritime mobile'),
        (14.236,'USB','3','20m SATERN','Salvation Army emergency','Intl',1,5,'Disaster relief coordination'),
        (14.325,'USB','3','20m Maritime Mobile','Maritime mobile net','Intl',1,4,'Ship-to-shore comms'),
        (21.285,'USB','3','15m Salvation Army','SATERN 15m net','Intl',1,3,'Disaster relief'),
        (28.303,'USB','3','10m Simplex','10m SSB activity','US',1,3,'Daytime; solar-cycle dependent'),
        (50.400,'USB','3','6m SSB','6m general SSB activity','US',1,3,''),
        (52.525,'FM','15','6m FM Call','National 6m FM simplex','US',1,4,'FM simplex calling'),
        (145.585,'FM','15','2m ISS','ISS APRS digipeater','Intl',1,6,'International Space Station packet radio'),
        (145.800,'FM','15','2m ISS Voice','ISS voice downlink','Intl',1,5,'Astronaut contacts; special events'),
        (223.500,'FM','','1.25m Simplex','222 MHz national simplex','US',1,3,'Low-activity band; less congested'),
        (927.500,'FM','','33cm Simplex','902 MHz simplex','US',1,2,'Rarely used; UHF experimentation'),
        # ── Weather/Environmental Monitoring ───────────────────────
        (137.100,'FM','','NOAA APT 1','NOAA-15 weather satellite','Intl',0,4,'APT image downlink; needs SDR + antenna'),
        (137.620,'FM','','NOAA APT 2','NOAA-18 weather satellite','Intl',0,4,'Weather satellite image reception'),
        (137.912,'FM','','NOAA APT 3','NOAA-19 weather satellite','Intl',0,4,'Most active NOAA satellite'),
        (1090.000,'AM','','ADS-B','Aircraft transponder','Intl',0,3,'Track aircraft with SDR; FlightAware feed'),
        (162.000,'FM','','SAME Alerts','EAS/SAME weather alerts','US',0,5,'Specific Area Message Encoding on NOAA freqs'),
        # ── Public Safety — Scanner Interest ───────────────────────
        (155.475,'FM','12.5','Natl Interop Call','National interoperability calling','US',0,5,'Police/fire mutual aid calling'),
        (155.7525,'FM','12.5','Natl Interop Tac','Interop tactical','US',0,4,'Mutual aid tactical'),
        (151.625,'FM','12.5','ITAC Ch 1','Interoperability TAC 1','US',0,4,'Fire/EMS interop'),
        (154.452,'FM','12.5','Natl Fire Emer','Fire emergency','US',0,4,''),
        (155.340,'FM','12.5','Natl Police Emer','Police emergency/mutual aid','US',0,4,''),
        (156.075,'FM','12.5','Natl SAR','Search and Rescue coord','US',0,5,'SAR operations'),
        (158.7375,'FM','12.5','Fed Law Enforce','Federal law enforcement','US',0,3,''),
        (164.500,'FM','12.5','DOI Emerg','Dept of Interior emergency','US',0,3,'National parks, BLM'),
        (166.250,'FM','12.5','DOT Emerg','Dept of Transportation','US',0,3,'Highway/infrastructure'),
        (168.625,'FM','12.5','FEMA Ops','FEMA field operations','US',0,4,'Disaster response coordination'),
        # ── Meshtastic Additional ──────────────────────────────────
        (869.525,'LoRa','125','Meshtastic EU','Meshtastic default (EU 868)','EU',0,7,'EU ISM band; mesh text messaging'),
        (923.875,'LoRa','125','Meshtastic US Alt','Meshtastic alt US channel','US',0,4,'Alternative to default 906.875'),
        (916.800,'LoRa','125','Meshtastic US LR','Meshtastic long range','US',0,5,'Long-range preset'),
    ]
    with db_session() as db:
        db.executemany('INSERT OR IGNORE INTO freq_database (frequency, mode, bandwidth, service, description, region, license_required, priority, notes) VALUES (?,?,?,?,?,?,?,?,?)', freqs)
        db.commit()


# ─── Comms Window Scheduling ─────────────────────────────────────

@comms_bp.route('/api/comms/schedules', methods=['GET'])
def api_comms_schedules_list():
    with db_session() as db:
        rows = db.execute('SELECT * FROM comms_schedules WHERE active = 1 ORDER BY check_in_time LIMIT 5000').fetchall()
        return jsonify([dict(r) for r in rows])
@comms_bp.route('/api/comms/schedules', methods=['POST'])
def api_comms_schedules_create():
    d = request.json or {}
    with db_session() as db:
        cur = db.execute('INSERT INTO comms_schedules (frequency, mode, net_name, check_in_time, assigned_operator, priority, notes) VALUES (?,?,?,?,?,?,?)',
            (d.get('frequency',''), d.get('mode',''), d.get('net_name',''), d.get('check_in_time',''), d.get('assigned_operator',''), d.get('priority', 5), d.get('notes','')))
        db.commit()
        row = db.execute('SELECT * FROM comms_schedules WHERE id = ?', (cur.lastrowid,)).fetchone()
        return jsonify(dict(row)), 201
@comms_bp.route('/api/comms/schedules/<int:sid>', methods=['DELETE'])
def api_comms_schedules_delete(sid):
    with db_session() as db:
        r = db.execute('DELETE FROM comms_schedules WHERE id = ?', (sid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
        return jsonify({'deleted': True})
@comms_bp.route('/api/comms/schedules/overdue', methods=['GET'])
def api_comms_schedules_overdue():
    with db_session() as db:
        # Find schedules where check_in_time has passed today with no comms_log entry
        rows = db.execute("""
            SELECT cs.* FROM comms_schedules cs
            WHERE cs.active = 1 AND cs.check_in_time <= time('now')
            AND NOT EXISTS (
                SELECT 1 FROM comms_log cl
                WHERE cl.freq = cs.frequency
                AND cl.created_at >= date('now')
            )
        """).fetchall()
        return jsonify([dict(r) for r in rows])
# ─── Frequency Scan Lists ────────────────────────────────────────

@comms_bp.route('/api/comms/frequencies/priority', methods=['GET'])
def api_comms_freq_priority():
    with db_session() as db:
        rows = db.execute('SELECT * FROM freq_database WHERE priority >= 7 ORDER BY frequency LIMIT 5000').fetchall()
        return jsonify([dict(r) for r in rows])
# ─── Mesh/LAN Bridging ──────────────────────────────────────────

@comms_bp.route('/api/comms/bridge', methods=['POST'])
def api_comms_bridge():
    d = request.json or {}
    msg = d.get('message', '')
    source = d.get('source', 'lan')  # 'lan' or 'mesh'
    with db_session() as db:
        if source == 'lan':
            # Bridge LAN message to mesh
            db.execute('INSERT INTO mesh_messages (content, sender, source) VALUES (?, ?, ?)',
                (msg[:200], d.get('sender', 'Bridge'), 'bridged'))
        else:
            # Bridge mesh message to LAN
            db.execute('INSERT INTO lan_messages (content, sender, source) VALUES (?, ?, ?)',
                (msg, d.get('sender', 'Bridge'), 'bridged'))
        db.commit()
        return jsonify({'bridged': True})
@comms_bp.route('/api/comms/dashboard')
def api_comms_dashboard():
    """Comms status overview — last contacts, active frequencies, mesh status."""
    with db_session() as db:
        last_logs = [dict(r) for r in db.execute('SELECT callsign, freq, direction, created_at FROM comms_log ORDER BY created_at DESC LIMIT 5').fetchall()]
        freq_count = db.execute('SELECT COUNT(*) as c FROM freq_database').fetchone()['c']
        contacts_with_radio = db.execute("SELECT COUNT(*) as c FROM contacts WHERE callsign != ''").fetchone()['c']
        profiles = db.execute('SELECT COUNT(*) as c FROM radio_profiles').fetchone()['c']
        return jsonify({
            'recent_logs': last_logs,
            'freq_count': freq_count,
            'radio_contacts': contacts_with_radio,
            'radio_profiles': profiles,
        })
@comms_bp.route('/api/comms/radio-profiles')
def api_comms_profiles_list():
    with db_session() as db:
        rows = db.execute('SELECT * FROM radio_profiles ORDER BY name').fetchall()
        profiles = []
        for row in rows:
            entry = dict(row)
            entry['channels'] = _normalize_radio_channels(entry.get('channels'))
            profiles.append(entry)
        return jsonify(profiles)
@comms_bp.route('/api/comms/radio-profiles', methods=['POST'])
def api_comms_profiles_create():
    data = request.get_json() or {}
    with db_session() as db:
        db.execute('INSERT INTO radio_profiles (radio_model, name, channels) VALUES (?,?,?)',
                   (
                       data.get('radio_model', ''),
                       data.get('name', 'New Profile'),
                       json.dumps(_normalize_radio_channels(data.get('channels', []))),
                   ))
        db.commit()
        return jsonify({'status': 'created'})
@comms_bp.route('/api/comms/radio-profiles/<int:pid>', methods=['DELETE'])
def api_comms_profiles_delete(pid):
    with db_session() as db:
        r = db.execute('DELETE FROM radio_profiles WHERE id = ?', (pid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
        return jsonify({'status': 'deleted'})
@comms_bp.route('/api/broadcast')
def api_broadcast_get():
    return jsonify(_broadcast)

@comms_bp.route('/api/broadcast', methods=['POST'])
def api_broadcast_set():
    data = request.get_json() or {}
    _broadcast['active'] = True
    _broadcast['message'] = (data.get('message', '') or '')[:500]
    _broadcast['severity'] = data.get('severity', 'info')
    _broadcast['timestamp'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    log_activity('broadcast_sent', detail=_broadcast['message'][:100])
    return jsonify({'status': 'sent'})

@comms_bp.route('/api/broadcast/clear', methods=['POST'])
def api_broadcast_clear():
    _broadcast['active'] = False
    _broadcast['message'] = ''
    return jsonify({'status': 'cleared'})

# ─── Resource Allocation Planner ──────────────────────────────────


@comms_bp.route('/api/comms-log')
def api_comms_log_list():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM comms_log ORDER BY created_at DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
        return jsonify([dict(r) for r in rows])
@comms_bp.route('/api/comms-log', methods=['POST'])
def api_comms_log_create():
    data = request.get_json() or {}
    with db_session() as db:
        cur = db.execute('INSERT INTO comms_log (freq, callsign, direction, message, signal_quality) VALUES (?, ?, ?, ?, ?)',
                         (data.get('freq', ''), data.get('callsign', ''), data.get('direction', 'rx'),
                          data.get('message', ''), data.get('signal_quality', '')))
        db.commit()
        row = db.execute('SELECT * FROM comms_log WHERE id = ?', (cur.lastrowid,)).fetchone()
        return jsonify(dict(row)), 201
@comms_bp.route('/api/comms-log/<int:lid>', methods=['DELETE'])
def api_comms_log_delete(lid):
    with db_session() as db:
        r = db.execute('DELETE FROM comms_log WHERE id = ?', (lid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
        return jsonify({'status': 'deleted'})
# ─── Drill History API ────────────────────────────────────────────


# ─── Serial Port Bridge Framework (Phase 13) ─────────────────────

@comms_bp.route('/api/serial/ports')
def api_serial_ports():
    """List available serial ports."""
    try:
        import serial.tools.list_ports
        ports = []
        for p in serial.tools.list_ports.comports():
            ports.append({
                'device': p.device,
                'description': p.description,
                'hwid': p.hwid,
                'manufacturer': p.manufacturer,
            })
        return jsonify({'ports': ports, 'pyserial_available': True})
    except ImportError:
        return jsonify({'ports': [], 'pyserial_available': False, 'note': 'Install pyserial: pip install pyserial'})

@comms_bp.route('/api/serial/connect', methods=['POST'])
def api_serial_connect():
    """Connect to a serial port."""
    data = request.get_json() or {}
    port = data.get('port', '')
    baud = data.get('baud', 9600)
    protocol = data.get('protocol', 'raw')
    if not port:
        return jsonify({'error': 'port is required'}), 400
    try:
        import serial
        if _serial_conn['conn'] and _serial_conn['conn'].is_open:
            _serial_conn['conn'].close()
        conn = serial.Serial(port, baudrate=baud, timeout=2)
        _serial_conn['conn'] = conn
        _serial_state.update({
            'connected': True, 'port': port, 'baud': baud,
            'protocol': protocol, 'error': None,
        })
        log_activity('serial_connected', 'serial', f'{port} @ {baud}')
        return jsonify({'status': 'connected', 'port': port, 'baud': baud, 'protocol': protocol})
    except ImportError:
        return jsonify({'error': 'pyserial not installed. Run: pip install pyserial'}), 500
    except Exception as e:
        _serial_state.update({'connected': False, 'error': str(e)})
        import logging
        logging.getLogger(__name__).exception('Serial connect failed')
        return jsonify({'error': 'Serial connection failed'}), 500

@comms_bp.route('/api/serial/disconnect', methods=['POST'])
def api_serial_disconnect():
    """Disconnect from serial port."""
    if _serial_conn['conn']:
        try:
            _serial_conn['conn'].close()
        except Exception:
            pass
        _serial_conn['conn'] = None
    _serial_state.update({'connected': False, 'port': None, 'baud': None, 'protocol': None, 'error': None})
    log_activity('serial_disconnected', 'serial')
    return jsonify({'status': 'disconnected'})

@comms_bp.route('/api/serial/status')
def api_serial_status():
    """Get serial connection status and last reading."""
    return jsonify(_serial_state)

# [EXTRACTED to blueprint] Sensor chart route


# ─── Meshtastic Bridge Stub (Phase 14) ────────────────────────────

@comms_bp.route('/api/mesh/status')
def api_mesh_status():
    """Return mesh radio status — stub returns disconnected defaults."""
    return jsonify(_mesh_state)

@comms_bp.route('/api/mesh/messages')
def api_mesh_messages_list():
    """List recent mesh messages."""
    with db_session() as db:
        limit = request.args.get('limit', 50, type=int)
        rows = db.execute('SELECT * FROM mesh_messages ORDER BY timestamp DESC LIMIT ?', (limit,)).fetchall()
        return jsonify([dict(r) for r in rows])
@comms_bp.route('/api/mesh/messages', methods=['POST'])
def api_mesh_messages_send():
    """Send a mesh message — stub stores locally."""
    data = request.get_json() or {}
    message = data.get('message', '')
    channel = data.get('channel', 'LongFast')
    to_node = data.get('to_node', '^all')
    if not message:
        return jsonify({'error': 'message is required'}), 400
    with db_session() as db:
        cur = db.execute(
            'INSERT INTO mesh_messages (from_node, to_node, message, channel) VALUES (?, ?, ?, ?)',
            ('!local', to_node, message, channel))
        db.commit()
        msg_id = cur.lastrowid
        row = db.execute('SELECT * FROM mesh_messages WHERE id = ?', (msg_id,)).fetchone()
    if not _mesh_state['connected']:
        return jsonify({'status': 'queued', 'note': 'No mesh radio connected — message stored locally', 'message': dict(row)}), 202
    return jsonify({'status': 'sent', 'message': dict(row)}), 201

@comms_bp.route('/api/mesh/nodes')
def api_mesh_nodes():
    """List visible mesh nodes — stub returns empty when no hardware."""
    if not _mesh_state['connected']:
        return jsonify({'nodes': [], 'note': 'No mesh radio connected. Connect via Web Serial API in the frontend.'})
    return jsonify({'nodes': []})

# ─── Comms Status Board (Phase 14) ────────────────────────────────

@comms_bp.route('/api/comms/status-board')
def api_comms_status_board():
    """Unified view of all communication channels."""
    from datetime import datetime, timedelta
    with db_session() as db:
        # LAN peers
        lan_peers = []
        try:
            peers = db.execute('SELECT * FROM federation_peers ORDER BY last_seen DESC').fetchall()
            lan_peers = [dict(p) for p in peers]
        except Exception:
            pass

        # Mesh nodes
        mesh_nodes = []
        mesh_status = dict(_mesh_state)

        # Federation peers
        fed_peers = []
        try:
            rows = db.execute("SELECT * FROM federation_peers WHERE trust_level != 'blocked' ORDER BY last_seen DESC LIMIT 500").fetchall()
            fed_peers = [dict(r) for r in rows]
        except Exception:
            pass

        # Recent comms log
        recent_comms = []
        try:
            since = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            rows = db.execute('SELECT * FROM comms_log WHERE created_at >= ? ORDER BY created_at DESC LIMIT 50', (since,)).fetchall()
            recent_comms = [dict(r) for r in rows]
        except Exception:
            pass

        # Active frequencies from radio profiles
        active_freqs = []
        try:
            rows = db.execute('SELECT * FROM radio_profiles ORDER BY name').fetchall()
            for r in rows:
                channels = _normalize_radio_channels(r['channels'])
                for ch in channels:
                    active_freqs.append({
                        'profile': r['name'],
                        'radio': r['radio_model'],
                        'channel': ch.get('name', ''),
                        'frequency': ch.get('frequency', ''),
                    })
        except Exception:
            pass

        # Recent mesh messages
        mesh_msgs = []
        try:
            rows = db.execute('SELECT * FROM mesh_messages ORDER BY timestamp DESC LIMIT 20').fetchall()
            mesh_msgs = [dict(r) for r in rows]
        except Exception:
            pass

        return jsonify({
        'lan_peers': lan_peers,
        'mesh': {
            'status': mesh_status,
            'nodes': mesh_nodes,
            'recent_messages': mesh_msgs,
        },
        'federation_peers': fed_peers,
        'recent_comms': recent_comms,
        'active_frequencies': active_freqs,
        'channels_count': {
            'lan': len(lan_peers),
            'mesh': mesh_status.get('node_count', 0),
            'federation': len(fed_peers),
            'frequencies': len(active_freqs),
            },
        })
