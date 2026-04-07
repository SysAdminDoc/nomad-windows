"""Security cameras, access log, perimeter zones, and motion detection routes."""

import json
import logging
import threading
import time

from flask import Blueprint, request, jsonify

from db import db_session, log_activity
from web.sql_safety import safe_columns, build_update
from web.state import _motion_detectors, _motion_config
from web.utils import clone_json_fallback as _clone_json_fallback, safe_json_value as _safe_json_value, safe_json_object as _safe_json_object, safe_json_list as _safe_json_list, safe_id_list as _safe_id_list

log = logging.getLogger(__name__)

security_bp = Blueprint('security', __name__)


# ─── Helper ────────────────────────────────────────────────────────

def _check_origin(req):
    """Block cross-origin state-changing requests (CSRF protection)."""
    origin = req.headers.get('Origin', '')
    if origin and not origin.startswith(('http://localhost:', 'http://127.0.0.1:')):
        from flask import abort
        abort(403, 'Cross-origin request blocked')


# ─── Security Cameras CRUD ─────────────────────────────────────────

@security_bp.route('/api/security/cameras')
def api_cameras_list():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM cameras ORDER BY name LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    return jsonify([dict(r) for r in rows])


@security_bp.route('/api/security/cameras', methods=['POST'])
def api_cameras_create():
    data = request.get_json() or {}
    if not data.get('name') or not data.get('url'):
        return jsonify({'error': 'Name and URL required'}), 400
    name = (data.get('name') or '')[:200]
    url = (data.get('url') or '')[:2000]
    notes = (data.get('notes') or '')[:2000]
    with db_session() as db:
        db.execute('INSERT INTO cameras (name, url, stream_type, location, zone, notes) VALUES (?,?,?,?,?,?)',
                   (name, url, data.get('stream_type', 'mjpeg'),
                    data.get('location', ''), data.get('zone', ''), notes))
        db.commit()
    return jsonify({'status': 'created'}), 201


@security_bp.route('/api/security/cameras/<int:cid>', methods=['DELETE'])
def api_cameras_delete(cid):
    with db_session() as db:
        db.execute('DELETE FROM motion_events WHERE camera_id = ?', (cid,))
        r = db.execute('DELETE FROM cameras WHERE id = ?', (cid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    log_activity('camera_deleted', 'security', f'Deleted camera {cid}')
    return jsonify({'status': 'deleted'})


@security_bp.route('/api/security/cameras/<int:cid>/ping', methods=['POST'])
def api_camera_ping(cid):
    with db_session() as db:
        cam = db.execute('SELECT * FROM cameras WHERE id = ?', (cid,)).fetchone()
        if not cam:
            return jsonify({'error': 'Camera not found'}), 404
        url = cam['url'] or cam.get('stream_url', '')
        is_reachable = False
        if url:
            try:
                import requests as req
                resp = req.head(url, timeout=5)
                is_reachable = resp.status_code < 500
            except Exception:
                pass
        status = 'active' if is_reachable else 'offline'
        db.execute('UPDATE cameras SET status = ?, last_seen = datetime("now") WHERE id = ?', (status, cid))
        db.commit()
        return jsonify({'status': status, 'reachable': is_reachable})
# ─── Access Log ────────────────────────────────────────────────────

@security_bp.route('/api/security/access-log')
def api_access_log():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM access_log ORDER BY created_at DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    return jsonify([dict(r) for r in rows])


@security_bp.route('/api/security/access-log', methods=['POST'])
def api_access_log_create():
    data = request.get_json() or {}
    person = (data.get('person') or '')[:200]
    location = (data.get('location') or '')[:200]
    notes = (data.get('notes') or '')[:2000]
    with db_session() as db:
        db.execute('INSERT INTO access_log (person, direction, location, method, notes) VALUES (?,?,?,?,?)',
                   (person, data.get('direction', 'entry'),
                    location, data.get('method', 'visual'), notes))
        db.commit()
    log_activity('access_logged', detail=f'{data.get("direction","entry")}: {data.get("person","")} at {data.get("location","")}')
    return jsonify({'status': 'logged'}), 201


@security_bp.route('/api/security/access-log/clear', methods=['POST'])
def api_access_log_clear():
    with db_session() as db:
        db.execute('DELETE FROM access_log')
        db.commit()
    log_activity('access_log_cleared', detail='Cleared access log')
    return jsonify({'status': 'cleared'})


# ─── Security Dashboard ───────────────────────────────────────────

@security_bp.route('/api/security/dashboard')
def api_security_dashboard():
    """Security overview: camera status, recent access, incident summary."""
    with db_session() as db:
        from datetime import datetime, timedelta
        cameras = db.execute('SELECT COUNT(*) as c FROM cameras WHERE status = ?', ('active',)).fetchone()['c']
        access_24h = db.execute("SELECT COUNT(*) as c FROM access_log WHERE created_at >= ?",
                                ((datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S'),)).fetchone()['c']
        sec_incidents = db.execute("SELECT COUNT(*) as c FROM incidents WHERE category = 'security' AND created_at >= ?",
                                  ((datetime.now() - timedelta(hours=48)).strftime('%Y-%m-%d %H:%M:%S'),)).fetchone()['c']
        # Get situation board security level
        sit_raw = db.execute("SELECT value FROM settings WHERE key = 'sit_board'").fetchone()
        security_level = 'green'
        if sit_raw and sit_raw['value']:
            sit = _safe_json_object(sit_raw['value'], {})
            security_level = sit.get('security', 'green')
    return jsonify({
        'cameras_active': cameras, 'access_24h': access_24h,
        'security_incidents_48h': sec_incidents, 'security_level': security_level,
    })


# ─── Perimeter Security Zones ─────────────────────────────────────

@security_bp.route('/api/security/zones')
def api_security_zones():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute('SELECT id, name, zone_type, camera_ids, waypoint_ids, alert_on_entry, alert_on_exit, threat_level, color, notes FROM perimeter_zones ORDER BY name LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    result = []
    for r in rows:
        entry = dict(r)
        entry['camera_ids'] = _safe_id_list(entry.get('camera_ids'))
        entry['waypoint_ids'] = _safe_id_list(entry.get('waypoint_ids'))
        result.append(entry)
    return jsonify(result)


@security_bp.route('/api/security/zones', methods=['POST'])
def api_security_zones_create():
    data = request.get_json() or {}
    name = (data.get('name', '') or 'New Zone').strip()[:200]
    if not name:
        return jsonify({'error': 'Name required'}), 400
    import re as _re
    boundary = data.get('boundary_geojson', '')
    if len(boundary) > 500000:
        return jsonify({'error': 'GeoJSON too large (max 500KB)'}), 400
    zone_type = data.get('zone_type', 'perimeter')
    if zone_type not in ('perimeter', 'patrol', 'restricted', 'observation', 'buffer'):
        zone_type = 'perimeter'
    threat_level = data.get('threat_level', 'normal')
    if threat_level not in ('normal', 'elevated', 'high', 'critical'):
        threat_level = 'normal'
    color = data.get('color', '#ff0000')
    if not _re.match(r'^#[0-9a-fA-F]{3,8}$', color):
        color = '#ff0000'
    with db_session() as db:
        db.execute('''INSERT INTO perimeter_zones (name, zone_type, boundary_geojson, camera_ids, waypoint_ids,
                      alert_on_entry, alert_on_exit, threat_level, color, notes) VALUES (?,?,?,?,?,?,?,?,?,?)''',
                   (name, zone_type, boundary,
                    json.dumps(_safe_id_list(data.get('camera_ids'))), json.dumps(_safe_id_list(data.get('waypoint_ids'))),
                    1 if data.get('alert_on_entry', True) else 0,
                    1 if data.get('alert_on_exit', False) else 0,
                    threat_level, color,
                    (data.get('notes', '') or '')[:2000]))
        db.commit()
        zid = db.execute('SELECT last_insert_rowid()').fetchone()[0]
    log_activity('perimeter_zone_created', 'security', f'Zone "{name}"')
    return jsonify({'id': zid}), 201


@security_bp.route('/api/security/zones/<int:zid>', methods=['PUT'])
def api_security_zones_update(zid):
    data = request.get_json() or {}
    with db_session() as db:
        if not db.execute('SELECT 1 FROM perimeter_zones WHERE id = ?', (zid,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        allowed = ['name', 'zone_type', 'boundary_geojson', 'threat_level', 'color', 'notes', 'camera_ids', 'waypoint_ids', 'alert_on_entry', 'alert_on_exit']
        update_data = {}
        for col in ['name', 'zone_type', 'boundary_geojson', 'threat_level', 'color', 'notes']:
            if col in data:
                update_data[col] = data[col]
        if 'camera_ids' in data:
            update_data['camera_ids'] = json.dumps(_safe_id_list(data['camera_ids']))
        if 'waypoint_ids' in data:
            update_data['waypoint_ids'] = json.dumps(_safe_id_list(data['waypoint_ids']))
        if 'alert_on_entry' in data:
            update_data['alert_on_entry'] = 1 if data['alert_on_entry'] else 0
        if 'alert_on_exit' in data:
            update_data['alert_on_exit'] = 1 if data['alert_on_exit'] else 0
        filtered = safe_columns(update_data, allowed)
        if filtered:
            sql, params = build_update('perimeter_zones', filtered, allowed, where_val=zid)
            db.execute(sql, params)
            db.commit()
    return jsonify({'status': 'updated'})


@security_bp.route('/api/security/zones/<int:zid>', methods=['DELETE'])
def api_security_zones_delete(zid):
    with db_session() as db:
        r = db.execute('DELETE FROM perimeter_zones WHERE id = ?', (zid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


@security_bp.route('/api/security/zones/geo')
def api_security_zones_geo():
    """Return perimeter zones as GeoJSON for map overlay."""
    with db_session() as db:
        zones = db.execute('SELECT * FROM perimeter_zones LIMIT 200').fetchall()
    features = []
    for z in zones:
        geojson = z['boundary_geojson']
        if geojson:
            geometry = _safe_json_value(geojson, None)
            if isinstance(geometry, dict):
                features.append({
                    'type': 'Feature',
                    'geometry': geometry,
                    'properties': {
                        'id': z['id'], 'name': z['name'], 'zone_type': z['zone_type'],
                        'threat_level': z['threat_level'], 'color': z['color'],
                        'alert_on_entry': z['alert_on_entry']
                    }
                })
    return jsonify({'type': 'FeatureCollection', 'features': features})


# ─── Motion Detection API ─────────────────────────────────────────

@security_bp.route('/api/security/motion/start/<int:camera_id>', methods=['POST'])
def api_motion_start(camera_id):
    """Start motion detection on a camera feed using OpenCV."""
    _check_origin(request)
    try:
        import cv2
    except ImportError:
        return jsonify({
            'error': 'OpenCV not installed',
            'instructions': 'Install OpenCV: pip install opencv-python-headless'
        }), 503

    if camera_id in _motion_detectors and _motion_detectors[camera_id].get('running'):
        return jsonify({'status': 'already_running', 'camera_id': camera_id})

    with db_session() as db:
        cam = db.execute('SELECT * FROM cameras WHERE id = ?', (camera_id,)).fetchone()
    if not cam:
        return jsonify({'error': 'Camera not found'}), 404

    cam_url = cam['url']
    cam_name = cam['name']

    _motion_detectors[camera_id] = {
        'running': True,
        'stop_flag': threading.Event(),
        'last_check': None,
        'detections_count': 0,
        'last_detection_time': None,
        'camera_name': cam_name,
    }

    def _motion_loop(cid, url, name):
        import cv2 as _cv2
        stop_flag = _motion_detectors[cid]['stop_flag']
        cap = _cv2.VideoCapture(url)
        if not cap.isOpened():
            _motion_detectors[cid]['running'] = False
            _motion_detectors[cid]['error'] = 'Could not open video stream'
            log.warning(f'Motion detection: failed to open stream for camera {cid} ({url})')
            return

        prev_gray = None
        last_alert_time = 0

        try:
            while not stop_flag.is_set():
                ret, frame = cap.read()
                if not ret:
                    # Try to reconnect
                    cap.release()
                    stop_flag.wait(_motion_config['check_interval'])
                    if stop_flag.is_set():
                        break
                    cap = _cv2.VideoCapture(url)
                    continue

                _motion_detectors[cid]['last_check'] = time.strftime('%Y-%m-%d %H:%M:%S')

                gray = _cv2.cvtColor(frame, _cv2.COLOR_BGR2GRAY)
                gray = _cv2.GaussianBlur(gray, (21, 21), 0)

                if prev_gray is not None:
                    diff = _cv2.absdiff(prev_gray, gray)
                    mean_diff = diff.mean()

                    if mean_diff > _motion_config['threshold']:
                        now = time.time()
                        if now - last_alert_time > _motion_config['cooldown']:
                            last_alert_time = now
                            _motion_detectors[cid]['detections_count'] += 1
                            _motion_detectors[cid]['last_detection_time'] = time.strftime('%Y-%m-%d %H:%M:%S')
                            log_activity(
                                f'Motion detected on camera "{name}"',
                                service='security',
                                detail=f'Camera {cid}: mean diff {mean_diff:.1f} (threshold {_motion_config["threshold"]})',
                                level='warning'
                            )

                            # Save frame as JPEG
                            import os
                            from datetime import datetime as _dt
                            from config import get_data_dir as _get_data_dir
                            capture_dir = os.path.join(_get_data_dir(), 'motion_captures')
                            os.makedirs(capture_dir, exist_ok=True)
                            filename = f'cam{cid}_{_dt.now().strftime("%Y%m%d_%H%M%S")}.jpg'
                            filepath = os.path.join(capture_dir, filename)
                            _cv2.imwrite(filepath, frame)

                            # Log to motion_events table
                            with db_session() as _db:
                                _db.execute('INSERT INTO motion_events (camera_id, mean_diff, image_path, created_at) VALUES (?, ?, ?, datetime("now"))',
                                    (cid, mean_diff, filepath))
                                _db.commit()
                prev_gray = gray
                stop_flag.wait(_motion_config['check_interval'])
        except Exception as e:
            log.error(f'Motion detection error on camera {cid}: {e}')
            _motion_detectors[cid]['error'] = str(e)
        finally:
            cap.release()
            _motion_detectors[cid]['running'] = False

    t = threading.Thread(target=_motion_loop, args=(camera_id, cam_url, cam_name), daemon=True)
    _motion_detectors[camera_id]['thread'] = t
    t.start()

    log_activity(f'Motion detection started on camera "{cam_name}"', service='security')
    return jsonify({'status': 'started', 'camera_id': camera_id})


@security_bp.route('/api/security/motion/stop/<int:camera_id>', methods=['POST'])
def api_motion_stop(camera_id):
    """Stop motion detection on a camera."""
    _check_origin(request)
    if camera_id not in _motion_detectors:
        return jsonify({'error': 'Motion detection not active for this camera'}), 404

    det = _motion_detectors[camera_id]
    if det.get('stop_flag'):
        det['stop_flag'].set()
    det['running'] = False

    cam_name = det.get('camera_name', f'Camera {camera_id}')
    log_activity(f'Motion detection stopped on camera "{cam_name}"', service='security')
    return jsonify({'status': 'stopped', 'camera_id': camera_id})


@security_bp.route('/api/security/motion/status')
def api_motion_status():
    """Return status of all motion detectors."""
    result = {}
    for cid, det in _motion_detectors.items():
        result[str(cid)] = {
            'running': det.get('running', False),
            'camera_name': det.get('camera_name', ''),
            'last_check': det.get('last_check'),
            'detections_count': det.get('detections_count', 0),
            'last_detection_time': det.get('last_detection_time'),
            'error': det.get('error'),
        }
    return jsonify({
        'detectors': result,
        'config': {
            'threshold': _motion_config['threshold'],
            'check_interval': _motion_config['check_interval'],
            'cooldown': _motion_config['cooldown'],
        }
    })


@security_bp.route('/api/security/motion/configure', methods=['POST'])
def api_motion_configure():
    """Set motion detection parameters."""
    _check_origin(request)
    data = request.get_json() or {}
    try:
        if 'threshold' in data:
            val = max(5, min(100, int(data['threshold'])))
            _motion_config['threshold'] = val
        if 'check_interval' in data:
            val = max(1, min(30, int(data['check_interval'])))
            _motion_config['check_interval'] = val
        if 'cooldown' in data:
            val = max(5, min(600, int(data['cooldown'])))
            _motion_config['cooldown'] = val
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid numeric value'}), 400

    # Persist to settings
    with db_session() as db:
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('motion_config', ?)",
                   (json.dumps(_motion_config),))
        db.commit()
    return jsonify({'status': 'configured', 'config': _motion_config})


@security_bp.route('/api/security/motion/events', methods=['GET'])
def api_motion_events():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM motion_events ORDER BY created_at DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
        return jsonify([dict(r) for r in rows])
# ─── Perimeter Breach Alert Integration ──────────────────────────

@security_bp.route('/api/security/zones/check-breach', methods=['POST'])
def api_check_perimeter_breach():
    d = request.json or {}
    camera_id = d.get('camera_id')
    with db_session() as db:
        # Find zones linked to this camera
        zones = db.execute('SELECT * FROM perimeter_zones').fetchall()
        breaches = []
        for z in zones:
            camera_ids = _safe_id_list(z['camera_ids'])
            if camera_id and camera_id in camera_ids:
                if z['alert_on_entry']:
                    breaches.append({'zone_id': z['id'], 'zone_name': z['name'], 'zone_type': z['zone_type']})
        return jsonify({'breaches': breaches})
