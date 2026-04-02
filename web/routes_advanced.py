"""Advanced API routes — Phases 16, 18, 19, 20.

Registered via register_advanced_routes(app) to keep app.py manageable.
"""

import json
import re
import os
import sys
import time
import platform
import logging
import shutil
import threading
from collections import deque
from datetime import datetime, timedelta
from html import escape as esc
from flask import jsonify, request, Response

from db import db_session, log_activity
from services import ollama
from web.print_templates import render_print_document

log = logging.getLogger('nomad.web')

# ─── Undo System (Phase 19) ─────────────────────────────────────────
# Module-level deque: stores last 10 destructive operations with 30s TTL
_undo_stack = deque(maxlen=10)
_redo_stack = []
_undo_lock = threading.Lock()

_UNDO_VALID_TABLES = {'inventory', 'contacts', 'notes', 'waypoints', 'documents',
                       'videos', 'audio', 'books', 'checklists', 'weather_log',
                       'sensor_devices', 'sensor_readings', 'journal', 'patients',
                       'vitals_log', 'wound_log', 'cameras', 'access_log',
                       'power_devices', 'power_log', 'incidents', 'comms_log',
                       'seeds', 'harvest_log', 'livestock', 'preservation_log',
                       'garden_plots', 'fuel_storage', 'equipment_log',
                       'ammo_inventory', 'community_resources', 'radiation_log',
                       'scheduled_tasks', 'skills', 'watch_schedules'}


def _push_undo(action_type, description, table, row_data):
    """Push an undoable action onto the stack."""
    with _undo_lock:
        _undo_stack.append({
            'action_type': action_type,
            'description': description,
            'table': table,
            'row_data': row_data,
            'timestamp': time.time(),
        })


def _prune_expired():
    """Remove entries older than 30 seconds."""
    cutoff = time.time() - 30
    with _undo_lock:
        while _undo_stack and _undo_stack[0]['timestamp'] < cutoff:
            _undo_stack.popleft()


def _is_expired_date(value):
    """Return True when a YYYY-MM-DD date is in the past."""
    if not value:
        return False
    try:
        return datetime.strptime(value, '%Y-%m-%d').date() < datetime.now().date()
    except (TypeError, ValueError):
        return False


def register_advanced_routes(app):
    """Register Phase 16/18/19/20 routes on the Flask app."""

    # ═════════════════════════════════════════════════════════════════
    # PHASE 16 — AI SITREP, Action Execution, Memory
    # ═════════════════════════════════════════════════════════════════

    # ─── AI SITREP Generator ─────────────────────────────────────────

    @app.route('/api/ai/sitrep', methods=['POST'])
    def api_ai_sitrep():
        """Generate a daily situation report from all data changes."""
        if not ollama.running():
            return jsonify({'error': 'AI service not running'}), 503

        data = request.get_json() or {}
        model = data.get('model', ollama.DEFAULT_MODEL)

        with db_session() as db:
            ctx_parts = []

            # Recent activity log (last 24h)
            activity = db.execute(
                "SELECT event, service, detail, level, created_at FROM activity_log "
                "WHERE created_at >= datetime('now', '-24 hours') ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
            if activity:
                lines = [f'[{a["level"]}] {a["event"]}' + (f' ({a["service"]})' if a["service"] else '') +
                         (f' — {a["detail"][:80]}' if a["detail"] else '') for a in activity]
                ctx_parts.append('ACTIVITY LOG (24h):\n' + '\n'.join(lines))

            # Inventory — low stock items
            low_stock = db.execute(
                'SELECT name, quantity, unit, category, min_quantity FROM inventory '
                'WHERE quantity <= min_quantity AND min_quantity > 0 ORDER BY category LIMIT 50'
            ).fetchall()
            if low_stock:
                ctx_parts.append('LOW STOCK ALERTS:\n' + '\n'.join(
                    f'  {r["name"]} ({r["category"]}): {r["quantity"]} {r["unit"]} (min: {r["min_quantity"]})'
                    for r in low_stock))

            # Inventory — newly expired (expiration within last 7 days or already expired)
            expired = db.execute(
                "SELECT name, quantity, unit, expiration FROM inventory "
                "WHERE expiration != '' AND expiration <= date('now') ORDER BY expiration LIMIT 50"
            ).fetchall()
            if expired:
                ctx_parts.append('EXPIRED ITEMS:\n' + '\n'.join(
                    f'  {r["name"]}: {r["quantity"]} {r["unit"]} (expired {r["expiration"]})'
                    for r in expired))

            # Incidents in last 24h
            incidents = db.execute(
                "SELECT severity, category, description, created_at FROM incidents "
                "WHERE created_at >= datetime('now', '-24 hours') ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
            if incidents:
                ctx_parts.append('INCIDENTS (24h):\n' + '\n'.join(
                    f'  [{r["severity"]}] {r["category"]}: {r["description"][:100]}'
                    for r in incidents))

            # Weather trends
            weather = db.execute(
                "SELECT pressure_hpa, temp_f, wind_dir, wind_speed, clouds, precip, created_at "
                "FROM weather_log WHERE created_at >= datetime('now', '-24 hours') "
                "ORDER BY created_at DESC LIMIT 10"
            ).fetchall()
            if weather:
                latest = weather[0]
                ctx_parts.append(
                    f'WEATHER: {latest["temp_f"]}F, Pressure {latest["pressure_hpa"]} hPa, '
                    f'Wind {latest["wind_dir"]} {latest["wind_speed"]}, '
                    f'Clouds {latest["clouds"]}, Precip {latest["precip"]} '
                    f'({len(weather)} readings in 24h)')
                if len(weather) >= 2:
                    oldest = weather[-1]
                    if latest['pressure_hpa'] and oldest['pressure_hpa']:
                        delta = round(latest['pressure_hpa'] - oldest['pressure_hpa'], 1)
                        trend = 'RISING' if delta > 0 else 'FALLING' if delta < 0 else 'STEADY'
                        ctx_parts.append(f'PRESSURE TREND: {trend} ({delta:+.1f} hPa over period)')

            # Power status
            power = db.execute(
                'SELECT battery_soc, solar_watts, load_watts, solar_wh_today, load_wh_today, '
                'generator_running, created_at FROM power_log ORDER BY created_at DESC LIMIT 1'
            ).fetchone()
            if power:
                gen = 'ON' if power['generator_running'] else 'OFF'
                ctx_parts.append(
                    f'POWER: Battery {power["battery_soc"] or "?"}%, '
                    f'Solar {power["solar_watts"] or 0}W ({power["solar_wh_today"] or 0} Wh today), '
                    f'Load {power["load_watts"] or 0}W ({power["load_wh_today"] or 0} Wh today), '
                    f'Generator {gen}')

            # Medical alerts — recent vitals
            vitals = db.execute(
                "SELECT p.name, v.bp_systolic, v.bp_diastolic, v.pulse, v.spo2, v.temp_f, v.created_at "
                "FROM vitals_log v JOIN patients p ON v.patient_id = p.id "
                "WHERE v.created_at >= datetime('now', '-24 hours') ORDER BY v.created_at DESC LIMIT 10"
            ).fetchall()
            if vitals:
                ctx_parts.append('MEDICAL VITALS (24h):\n' + '\n'.join(
                    f'  {v["name"]}: BP {v["bp_systolic"]}/{v["bp_diastolic"]}, '
                    f'HR {v["pulse"]}, SpO2 {v["spo2"]}%, Temp {v["temp_f"]}F'
                    for v in vitals))

            # Active alerts
            alerts = db.execute(
                'SELECT title, severity, message FROM alerts WHERE dismissed = 0 ORDER BY severity DESC LIMIT 10'
            ).fetchall()
            if alerts:
                ctx_parts.append('ACTIVE ALERTS:\n' + '\n'.join(
                    f'  [{a["severity"]}] {a["title"]}: {a["message"][:100]}' for a in alerts))

            # Inventory summary by category
            inv_summary = db.execute(
                'SELECT category, COUNT(*) as cnt, SUM(quantity) as total FROM inventory GROUP BY category LIMIT 50'
            ).fetchall()
            if inv_summary:
                ctx_parts.append('INVENTORY SUMMARY: ' + ', '.join(
                    f'{r["category"]}: {r["cnt"]} items' for r in inv_summary))

            # Team count
            team_count = db.execute('SELECT COUNT(*) as c FROM contacts').fetchone()['c']
            if team_count:
                ctx_parts.append(f'TEAM: {team_count} contacts registered')

        context = '\n\n'.join(ctx_parts) if ctx_parts else 'No operational data recorded yet.'

        system_prompt = f"""You are a military-style intelligence officer generating a SITREP (Situation Report) for a preparedness and field-operations workspace called NOMAD Field Desk.

Generate a formatted SITREP in markdown using this exact structure:

# SITREP — {datetime.now().strftime('%d %b %Y %H%M')}Z

## 1. SITUATION
(Overall assessment — 2-3 sentences summarizing current conditions)

## 2. SUPPLY STATUS
(Inventory highlights, low stock, expired items — use exact numbers from data)

## 3. PERSONNEL & MEDICAL
(Team count, any medical alerts, patient status)

## 4. INFRASTRUCTURE
(Power, weather, comms status)

## 5. INCIDENTS & ALERTS
(Any incidents in last 24h, active alerts)

## 6. RECOMMENDED ACTIONS
(3-5 prioritized actionable items based on the data — be specific)

RULES:
- Use ONLY the data provided below. Never fabricate information.
- Use exact quantities and names from the data.
- If a section has no relevant data, write "No data available."
- Be concise, direct, military-style briefing tone.

--- OPERATIONAL DATA ---
{context}
--- END DATA ---"""

        try:
            result = ollama.chat(model, [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': 'Generate the daily SITREP.'}
            ], stream=False)
            sitrep_text = result.get('message', {}).get('content', '') if isinstance(result, dict) else ''
            log_activity('sitrep_generated', 'ai', 'Daily SITREP generated')
            return jsonify({'sitrep': sitrep_text.strip()})
        except Exception as e:
            log.error('SITREP generation failed: %s', e)
            return jsonify({'error': 'SITREP generation failed'}), 500

    # ─── AI Action Execution ─────────────────────────────────────────

    @app.route('/api/ai/execute-action', methods=['POST'])
    def api_ai_execute_action():
        """Parse and execute a natural-language action command."""
        data = request.get_json() or {}
        action = data.get('action', '').strip()
        if not action:
            return jsonify({'error': 'No action provided'}), 400
        if len(action) > 500:
            return jsonify({'error': 'Action too long (max 500 chars)'}), 400

        # Pattern: "add [qty] [item] to inventory"
        m = re.match(r'add\s+(\d+)\s+(.+?)\s+to\s+inventory', action, re.IGNORECASE)
        if m:
            qty = int(m.group(1))
            item_name = m.group(2).strip()
            with db_session() as db:
                db.execute(
                    'INSERT INTO inventory (name, quantity, category) VALUES (?, ?, ?)',
                    (item_name, qty, 'other'))
                db.commit()
                row_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
                log_activity('inventory_added', 'ai', f'Added {qty} {item_name} via AI action')
            return jsonify({
                'status': 'executed',
                'action': 'add_inventory',
                'detail': f'Added {qty} {item_name} to inventory',
                'id': row_id,
            })

        # Pattern: "log incident [desc]"
        m = re.match(r'log\s+incident\s+(.+)', action, re.IGNORECASE)
        if m:
            desc = m.group(1).strip()
            with db_session() as db:
                db.execute(
                    'INSERT INTO incidents (severity, category, description) VALUES (?, ?, ?)',
                    ('info', 'other', desc))
                db.commit()
                row_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
                log_activity('incident_logged', 'ai', f'Incident: {desc[:80]}')
            return jsonify({
                'status': 'executed',
                'action': 'log_incident',
                'detail': f'Logged incident: {desc}',
                'id': row_id,
            })

        # Pattern: "create note [title]"
        m = re.match(r'create\s+note\s+(.+)', action, re.IGNORECASE)
        if m:
            title = m.group(1).strip()
            with db_session() as db:
                db.execute('INSERT INTO notes (title, content) VALUES (?, ?)', (title, ''))
                db.commit()
                row_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
                log_activity('note_created', 'ai', f'Note: {title}')
            return jsonify({
                'status': 'executed',
                'action': 'create_note',
                'detail': f'Created note: {title}',
                'id': row_id,
            })

        # Pattern: "add waypoint [name] at [lat],[lng]"
        m = re.match(r'add\s+waypoint\s+(.+?)\s+at\s+([-\d.]+)\s*,\s*([-\d.]+)', action, re.IGNORECASE)
        if m:
            wp_name = m.group(1).strip()
            try:
                lat = float(m.group(2))
                lng = float(m.group(3))
            except ValueError:
                return jsonify({'error': 'Invalid coordinates — lat and lng must be numbers'}), 400
            with db_session() as db:
                db.execute(
                    'INSERT INTO waypoints (name, lat, lng) VALUES (?, ?, ?)',
                    (wp_name, lat, lng))
                db.commit()
                row_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
                log_activity('waypoint_added', 'ai', f'Waypoint: {wp_name} ({lat},{lng})')
            return jsonify({
                'status': 'executed',
                'action': 'add_waypoint',
                'detail': f'Added waypoint {wp_name} at {lat},{lng}',
                'id': row_id,
            })

        return jsonify({
            'status': 'unrecognized',
            'error': 'Could not parse action. Supported: "add [qty] [item] to inventory", '
                     '"log incident [desc]", "create note [title]", "add waypoint [name] at [lat],[lng]"',
        }), 400

    # ─── AI Memory ───────────────────────────────────────────────────

    @app.route('/api/ai/memory', methods=['GET'])
    def api_ai_memory_list():
        """List persistent AI memory facts."""
        with db_session() as db:
            row = db.execute("SELECT value FROM settings WHERE key = 'ai_memory'").fetchone()
        memories = []
        if row and row['value']:
            try:
                memories = json.loads(row['value'])
            except (json.JSONDecodeError, TypeError):
                pass
        return jsonify({'memories': memories})

    @app.route('/api/ai/memory', methods=['POST'])
    def api_ai_memory_save():
        """Save a fact to AI memory."""
        data = request.get_json() or {}
        fact = data.get('fact', '').strip()
        if not fact:
            return jsonify({'error': 'No fact provided'}), 400
        with db_session() as db:
            row = db.execute("SELECT value FROM settings WHERE key = 'ai_memory'").fetchone()
            memories = []
            if row and row['value']:
                try:
                    memories = json.loads(row['value'])
                except (json.JSONDecodeError, TypeError):
                    pass
            memories.append({'fact': fact, 'saved_at': datetime.now().isoformat()})
            # Cap memory size to prevent unbounded growth
            if len(memories) > 200:
                memories = memories[-200:]
            db.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('ai_memory', ?)",
                (json.dumps(memories),))
            db.commit()
        log_activity('ai_memory_saved', 'ai', f'Memory: {fact[:60]}')
        return jsonify({'status': 'saved', 'count': len(memories)})

    @app.route('/api/ai/memory', methods=['DELETE'])
    def api_ai_memory_clear():
        """Clear all AI memory."""
        with db_session() as db:
            db.execute("DELETE FROM settings WHERE key = 'ai_memory'")
            db.commit()
        log_activity('ai_memory_cleared', 'ai', 'All AI memories cleared')
        return jsonify({'status': 'cleared'})

    # ═════════════════════════════════════════════════════════════════
    # PHASE 18 — Print / Operations Binder, Wallet Cards, SOI
    # ═════════════════════════════════════════════════════════════════

    # ─── Operations Binder ───────────────────────────────────────────

    @app.route('/api/print/operations-binder')
    def api_print_operations_binder():
        """Generate a comprehensive printable operations binder."""
        with db_session() as db:
            # Node identity
            node_name_row = db.execute("SELECT value FROM settings WHERE key = 'node_name'").fetchone()
            node_name = (node_name_row['value'] if node_name_row and node_name_row['value'] else platform.node()) or 'NOMAD Node'

            # Emergency contacts
            contacts = [dict(r) for r in db.execute(
                "SELECT name, callsign, role, phone, email, freq, blood_type, rally_point "
                "FROM contacts ORDER BY name").fetchall()]

            # Frequencies
            freqs = [dict(r) for r in db.execute(
                'SELECT frequency, mode, service, description FROM freq_database ORDER BY frequency'
            ).fetchall()]

            # Patients
            patients = [dict(r) for r in db.execute(
                'SELECT * FROM patients ORDER BY name').fetchall()]

            # Inventory by category
            inventory = [dict(r) for r in db.execute(
                'SELECT name, category, quantity, unit, location, expiration '
                'FROM inventory ORDER BY category, name').fetchall()]

            # Active checklists
            checklists = [dict(r) for r in db.execute(
                'SELECT name, items, updated_at FROM checklists ORDER BY name').fetchall()]

            # Waypoints
            waypoints = [dict(r) for r in db.execute(
                'SELECT name, lat, lng, category, notes FROM waypoints ORDER BY category, name'
            ).fetchall()]

            # Emergency procedures (top 6 notes tagged or titled with "emergency"/"procedure")
            procedures = [dict(r) for r in db.execute(
                "SELECT title, content FROM notes WHERE title LIKE '%emergency%' "
                "OR title LIKE '%procedure%' OR tags LIKE '%emergency%' "
                "ORDER BY pinned DESC, updated_at DESC LIMIT 6").fetchall()]

            # Family emergency plan
            family_plan_row = db.execute(
                "SELECT value FROM settings WHERE key = 'family_emergency_plan'").fetchone()
            family_plan = family_plan_row['value'] if family_plan_row and family_plan_row['value'] else ''

        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        date_str = datetime.now().strftime('%d %B %Y')
        contacts_html = '<div class="doc-empty">No contacts registered.</div>'
        if contacts:
            contacts_html = '<div class="doc-table-shell"><table><thead><tr><th>Name</th><th>Callsign</th><th>Role</th><th>Phone</th><th>Email</th><th>Freq</th><th>Blood</th><th>Rally Point</th></tr></thead><tbody>'
            for c in contacts:
                contacts_html += (
                    f'<tr><td class="doc-strong">{esc(c["name"])}</td><td>{esc(c.get("callsign","") or "-")}</td>'
                    f'<td>{esc(c.get("role","") or "-")}</td><td>{esc(c.get("phone","") or "-")}</td>'
                    f'<td>{esc(c.get("email","") or "-")}</td><td>{esc(c.get("freq","") or "-")}</td>'
                    f'<td>{esc(c.get("blood_type","") or "-")}</td><td>{esc(c.get("rally_point","") or "-")}</td></tr>'
                )
            contacts_html += '</tbody></table></div>'

        freq_html = '<div class="doc-table-shell"><table><thead><tr><th>Service</th><th>Freq (MHz)</th><th>Mode</th><th>Description</th></tr></thead><tbody>'
        if freqs:
            for f in freqs:
                freq_html += (
                    f'<tr><td class="doc-strong">{esc(f["service"])}</td><td>{esc(str(f["frequency"]))}</td>'
                    f'<td>{esc(f.get("mode","") or "-")}</td><td>{esc(f.get("description","") or "-")}</td></tr>'
                )
        else:
            fallback_freqs = [
                ('FRS Ch 1', '462.5625', 'FM', 'Family Radio primary'),
                ('MURS Ch 1', '151.820', 'FM', 'No license required'),
                ('2m Call', '146.520', 'FM', 'National simplex calling'),
                ('70cm Call', '446.000', 'FM', 'National simplex calling'),
                ('CB Ch 9', '27.065', 'AM', 'Emergency channel'),
                ('NOAA WX', '162.550', 'WX', 'Weather broadcast'),
            ]
            for service, freq, mode, notes in fallback_freqs:
                freq_html += f'<tr><td class="doc-strong">{service}</td><td>{freq}</td><td>{mode}</td><td>{notes}</td></tr>'
        freq_html += '</tbody></table></div>'

        patient_cards_html = '<div class="doc-empty">No patients registered.</div>'
        if patients:
            patient_cards_html = '<div class="doc-grid-2">'
            for p in patients:
                try:
                    allergies = json.loads(p.get('allergies') or '[]')
                except (json.JSONDecodeError, TypeError):
                    allergies = []
                try:
                    conditions = json.loads(p.get('conditions') or '[]')
                except (json.JSONDecodeError, TypeError):
                    conditions = []
                try:
                    medications = json.loads(p.get('medications') or '[]')
                except (json.JSONDecodeError, TypeError):
                    medications = []
                allergy_html = ''.join(f'<span class="doc-chip doc-chip-alert">{esc(str(a))}</span>' for a in allergies) or '<span class="doc-chip doc-chip-muted">NKDA</span>'
                condition_html = ''.join(f'<span class="doc-chip">{esc(str(c))}</span>' for c in conditions) or '<span class="doc-chip doc-chip-muted">None recorded</span>'
                medication_html = ''.join(f'<span class="doc-chip">{esc(str(m))}</span>' for m in medications) or '<span class="doc-chip doc-chip-muted">None recorded</span>'
                patient_cards_html += f'''<div class="doc-panel doc-panel-strong">
  <h2 class="doc-section-title">{esc(p["name"])}</h2>
  <div class="doc-chip-list">
    <span class="doc-chip">Age: {esc(str(p.get("age") or "-"))}</span>
    <span class="doc-chip">Sex: {esc(str(p.get("sex") or "-"))}</span>
    <span class="doc-chip">Weight: {esc(str(p.get("weight_kg") or "?"))} kg</span>
    <span class="doc-chip">Blood: {esc(str(p.get("blood_type") or "-"))}</span>
  </div>
  <div style="margin-top:12px;" class="doc-chip-list">{allergy_html}</div>
  <div style="margin-top:12px;" class="doc-chip-list">{condition_html}</div>
  <div style="margin-top:12px;" class="doc-chip-list">{medication_html}</div>
  <div style="margin-top:12px;" class="doc-note-box">{esc(str(p.get("notes") or "No additional notes recorded."))}</div>
</div>'''
            patient_cards_html += '</div>'

        inventory_cards = '<div class="doc-empty">No inventory items.</div>'
        if inventory:
            categories = {}
            for item in inventory:
                cat = item.get('category', 'other') or 'other'
                categories.setdefault(cat, []).append(item)
            inventory_cards = '<div class="doc-grid-2">'
            for cat in sorted(categories.keys()):
                items = categories[cat]
                table_html = '<div class="doc-table-shell"><table><thead><tr><th>Item</th><th>Qty</th><th>Unit</th><th>Location</th><th>Expiration</th></tr></thead><tbody>'
                for item in items:
                    exp = item.get('expiration', '') or ''
                    exp_class = ' class="doc-alert"' if exp and _is_expired_date(exp) else ''
                    table_html += (
                        f'<tr><td class="doc-strong">{esc(item["name"])}</td><td>{esc(str(item["quantity"]))}</td>'
                        f'<td>{esc(item.get("unit","") or "-")}</td><td>{esc(item.get("location","") or "-")}</td>'
                        f'<td{exp_class}>{esc(exp) if exp else "-"}</td></tr>'
                    )
                table_html += '</tbody></table></div>'
                inventory_cards += f'<div class="doc-panel"><h2 class="doc-section-title">{esc(cat.upper())} ({len(items)})</h2>{table_html}</div>'
            inventory_cards += '</div>'

        checklist_cards = '<div class="doc-empty">No checklists.</div>'
        if checklists:
            checklist_cards = '<div class="doc-grid-2">'
            for cl in checklists:
                try:
                    items = json.loads(cl.get('items') or '[]')
                except (json.JSONDecodeError, TypeError):
                    items = []
                panel = f'<div class="doc-panel"><h2 class="doc-section-title">{esc(cl["name"])}</h2>'
                if items:
                    panel += '<div class="doc-table-shell"><table><thead><tr><th style="width:60px;">Done</th><th>Task</th></tr></thead><tbody>'
                    for item in items:
                        if isinstance(item, dict):
                            text = item.get('text', item.get('name', str(item)))
                            done = item.get('done', item.get('checked', False))
                        else:
                            text = str(item)
                            done = False
                        check = 'Done' if done else 'Open'
                        panel += f'<tr><td class="doc-strong">{check}</td><td>{esc(str(text))}</td></tr>'
                    panel += '</tbody></table></div>'
                else:
                    panel += '<div class="doc-empty">No items.</div>'
                panel += '</div>'
                checklist_cards += panel
            checklist_cards += '</div>'

        waypoint_html = '<div class="doc-empty">No waypoints registered.</div>'
        if waypoints:
            waypoint_html = '<div class="doc-table-shell"><table><thead><tr><th>Name</th><th>Latitude</th><th>Longitude</th><th>Category</th><th>Notes</th></tr></thead><tbody>'
            for wp in waypoints:
                lat = f'{wp["lat"]:.6f}' if wp.get('lat') is not None else '-'
                lng = f'{wp["lng"]:.6f}' if wp.get('lng') is not None else '-'
                waypoint_html += (
                    f'<tr><td class="doc-strong">{esc(wp["name"])}</td><td>{lat}</td><td>{lng}</td>'
                    f'<td>{esc(wp.get("category","") or "-")}</td><td>{esc(wp.get("notes","") or "-")}</td></tr>'
                )
            waypoint_html += '</tbody></table></div>'
            rally = [w for w in waypoints if (w.get('category', '') or '').lower() in ('rally', 'rally point', 'rallypoint')]
            if rally:
                waypoint_html += '<div style="margin-top:12px;" class="doc-note-box">Rally points are present. Print the dedicated map view from the Maps workspace for terrain detail and route overlays.</div>'

        procedure_html = '<div class="doc-empty">No emergency procedures are documented yet.</div>'
        if procedures:
            procedure_html = '<div class="doc-grid-2">'
            for proc in procedures:
                content = proc.get('content', '') or ''
                procedure_html += f'<div class="doc-panel"><h2 class="doc-section-title">{esc(proc["title"])}</h2><div class="doc-note-box">{esc(content)}</div></div>'
            procedure_html += '</div>'

        family_plan_html = f'<div class="doc-note-box">{esc(family_plan)}</div>' if family_plan else '<div class="doc-empty">No family emergency plan is configured. Save one in Settings.</div>'

        toc_html = '''<div class="doc-kv">
  <div class="doc-kv-row"><div class="doc-kv-key">1</div><div>Emergency Contacts Directory</div></div>
  <div class="doc-kv-row"><div class="doc-kv-key">2</div><div>Frequency Reference</div></div>
  <div class="doc-kv-row"><div class="doc-kv-key">3</div><div>Medical Patient Cards</div></div>
  <div class="doc-kv-row"><div class="doc-kv-key">4</div><div>Inventory Summary</div></div>
  <div class="doc-kv-row"><div class="doc-kv-key">5</div><div>Active Checklists</div></div>
  <div class="doc-kv-row"><div class="doc-kv-key">6</div><div>Waypoints and Rally Points</div></div>
  <div class="doc-kv-row"><div class="doc-kv-key">7</div><div>Emergency Procedures</div></div>
  <div class="doc-kv-row"><div class="doc-kv-key">8</div><div>Family Emergency Plan</div></div>
</div>'''

        body = f'''<section class="doc-section">
  <div class="doc-grid-2">
    <div class="doc-panel doc-panel-strong">
      <h2 class="doc-section-title">Operations Binder Overview</h2>
      <div class="doc-note-box">Comprehensive offline reference for contacts, frequencies, patients, supplies, rally points, procedures, and family planning. Treat as confidential operational material.</div>
    </div>
    <div class="doc-panel doc-panel-strong">
      <h2 class="doc-section-title">Contents</h2>
      {toc_html}
    </div>
  </div>
</section>
<section class="doc-section" style="page-break-before:always;">
  <div class="doc-grid-2">
    <div class="doc-panel">
      <h2 class="doc-section-title">1. Emergency Contacts Directory</h2>
      {contacts_html}
    </div>
    <div class="doc-panel">
      <h2 class="doc-section-title">2. Frequency Reference</h2>
      {freq_html}
    </div>
  </div>
</section>
<section class="doc-section" style="page-break-before:always;">
  <h2 class="doc-section-title">3. Medical Patient Cards</h2>
  {patient_cards_html}
</section>
<section class="doc-section" style="page-break-before:always;">
  <h2 class="doc-section-title">4. Inventory Summary</h2>
  {inventory_cards}
</section>
<section class="doc-section" style="page-break-before:always;">
  <h2 class="doc-section-title">5. Active Checklists</h2>
  {checklist_cards}
</section>
<section class="doc-section" style="page-break-before:always;">
  <h2 class="doc-section-title">6. Waypoints and Rally Points</h2>
  {waypoint_html}
</section>
<section class="doc-section" style="page-break-before:always;">
  <h2 class="doc-section-title">7. Emergency Procedures</h2>
  {procedure_html}
</section>
<section class="doc-section" style="page-break-before:always;">
  <h2 class="doc-section-title">8. Family Emergency Plan</h2>
  {family_plan_html}
</section>
<section class="doc-section">
  <div class="doc-note-box" style="border-color:#e9b7b7;background:#fff5f5;color:#7a1d1d;">
    <div class="doc-strong" style="letter-spacing:0.12em;text-transform:uppercase;">Confidential Handling</div>
    <div style="margin-top:6px;">Protect this binder accordingly and replace printed copies when the plan or roster changes.</div>
  </div>
</section>
<section class="doc-section">
  <div class="doc-footer">
    <span>End of Operations Binder - {esc(node_name)}</span>
    <span>Generated {esc(now)} by NOMAD Field Desk.</span>
  </div>
</section>'''

        html = render_print_document(
            f'Operations Binder - {node_name}',
            'Comprehensive binder for command-post reference, go-bag print packets, and family emergency continuity.',
            body,
            eyebrow='NOMAD Field Desk Operations Binder',
            meta_items=[f'Generated {esc(now)}', f'Node {esc(node_name)}', 'Confidential'],
            stat_items=[
                ('Contacts', len(contacts)),
                ('Frequencies', len(freqs)),
                ('Patients', len(patients)),
                ('Inventory', len(inventory)),
                ('Checklists', len(checklists)),
                ('Waypoints', len(waypoints)),
            ],
            accent_start='#13263a',
            accent_end='#35556f',
            max_width='1180px',
        )

        return Response(html, mimetype='text/html')

    # ─── Lamination / Wallet Cards ───────────────────────────────────

    @app.route('/api/print/wallet-cards')
    def api_print_wallet_cards():
        """Generate credit-card-sized reference cards for printing and laminating."""
        with db_session() as db:
            # Node identity
            node_name_row = db.execute("SELECT value FROM settings WHERE key = 'node_name'").fetchone()
            node_name = (node_name_row['value'] if node_name_row and node_name_row['value'] else platform.node()) or 'NOMAD'

            # Primary contact (first patient or contact as "self")
            self_patient = db.execute('SELECT * FROM patients ORDER BY id LIMIT 1').fetchone()
            self_contact = db.execute('SELECT * FROM contacts ORDER BY id LIMIT 1').fetchone()

            # Emergency contacts
            ice_contacts = [dict(r) for r in db.execute(
                "SELECT name, phone, role FROM contacts WHERE phone != '' ORDER BY id LIMIT 3").fetchall()]

            # Medications from first patient
            medications = []
            blood_type = ''
            allergies = []
            if self_patient:
                self_patient = dict(self_patient)
                blood_type = self_patient.get('blood_type', '') or ''
                try:
                    medications = json.loads(self_patient.get('medications') or '[]')
                except (json.JSONDecodeError, TypeError):
                    pass
                try:
                    allergies = json.loads(self_patient.get('allergies') or '[]')
                except (json.JSONDecodeError, TypeError):
                    pass

            # Rally points
            rally_points = [dict(r) for r in db.execute(
                "SELECT name, lat, lng FROM waypoints WHERE category LIKE '%rally%' "
                "ORDER BY id LIMIT 4").fetchall()]
            if not rally_points:
                rally_points = [dict(r) for r in db.execute(
                    'SELECT name, lat, lng FROM waypoints ORDER BY id LIMIT 4').fetchall()]

            # Frequencies
            custom_freqs = [dict(r) for r in db.execute(
                'SELECT frequency, service, mode FROM freq_database ORDER BY priority DESC, frequency LIMIT 8'
            ).fetchall()]

        now = datetime.now().strftime('%Y-%m-%d')
        patient_name = ''
        if self_patient:
            patient_name = self_patient['name']
        elif self_contact:
            patient_name = self_contact['name']
        contact_list_html = ''.join(
            f'<div style="margin-top:6px;"><span class="doc-strong">{i + 1}.</span> {esc(c["name"])}'
            f' ({esc(c.get("role","") or "Contact")}) - {esc(c["phone"])}</div>'
            for i, c in enumerate(ice_contacts[:3])
        ) or '<div class="doc-empty">No emergency contacts are on file.</div>'

        medication_html = ''.join(f'<span class="doc-chip">{esc(str(med))}</span>' for med in medications[:8]) or '<span class="doc-chip doc-chip-muted">None recorded</span>'
        allergy_html = ''.join(f'<span class="doc-chip doc-chip-alert">{esc(str(item))}</span>' for item in allergies) or '<span class="doc-chip doc-chip-muted">NKDA</span>'

        rally_html = '<div class="doc-empty">No rally points are configured.</div>'
        if rally_points:
            rally_html = '<div class="doc-table-shell"><table><thead><tr><th>Point</th><th>Lat</th><th>Lng</th></tr></thead><tbody>'
            for rp in rally_points:
                rally_html += f'<tr><td class="doc-strong">{esc(rp["name"])}</td><td>{rp["lat"]:.5f}</td><td>{rp["lng"]:.5f}</td></tr>'
            rally_html += '</tbody></table></div>'

        freq_html = '<div class="doc-table-shell"><table><thead><tr><th>Service</th><th>Freq</th><th>Mode</th></tr></thead><tbody>'
        if custom_freqs:
            for f in custom_freqs:
                freq_html += f'<tr><td class="doc-strong">{esc(f["service"])}</td><td>{esc(str(f["frequency"]))}</td><td>{esc(f.get("mode","") or "-")}</td></tr>'
        else:
            fallback_freqs = [
                ('FRS Ch 1', '462.5625', 'FM'),
                ('MURS Ch 1', '151.820', 'FM'),
                ('2m Call', '146.520', 'FM'),
                ('CB Ch 9', '27.065', 'AM'),
                ('NOAA WX', '162.550', 'WX'),
            ]
            for service, freq, mode in fallback_freqs:
                freq_html += f'<tr><td class="doc-strong">{service}</td><td>{freq}</td><td>{mode}</td></tr>'
        freq_html += '</tbody></table></div>'

        body = f'''<section class="doc-section">
  <h2 class="doc-section-title">Wallet Card Sheet</h2>
  <div class="doc-grid-3">
    <div class="doc-panel doc-panel-strong">
      <h2 class="doc-section-title">ICE Card</h2>
      <div class="doc-note-box" style="background:#fff;border-style:solid;">
        <div class="doc-strong" style="font-size:18px;">{esc(patient_name or "Unassigned")}</div>
        <div style="margin-top:10px;" class="doc-chip-list">
          <span class="doc-chip">Blood: {esc(blood_type or "?")}</span>
          <span class="doc-chip">Allergies</span>
        </div>
        <div style="margin-top:10px;" class="doc-chip-list">{allergy_html}</div>
        <div style="margin-top:12px;">
          <div class="doc-section-title" style="margin-bottom:6px;">Emergency Contacts</div>
          {contact_list_html}
        </div>
      </div>
    </div>
    <div class="doc-panel doc-panel-strong">
      <h2 class="doc-section-title">Blood Type Card</h2>
      <div class="doc-note-box" style="background:#fff;border-style:solid;text-align:center;">
        <div style="font-size:44px;line-height:1;font-weight:800;color:#7a1520;">{esc(blood_type or "?")}</div>
        <div style="margin-top:12px;" class="doc-strong">{esc(patient_name or "Name pending")}</div>
        <div class="doc-chip-list" style="margin-top:10px;justify-content:center;">{allergy_html}</div>
      </div>
    </div>
    <div class="doc-panel doc-panel-strong">
      <h2 class="doc-section-title">Medication Card</h2>
      <div class="doc-note-box" style="background:#fff;border-style:solid;">
        <div class="doc-strong">Patient: {esc(patient_name or "Unassigned")}</div>
        <div style="margin-top:12px;" class="doc-chip-list">{medication_html}</div>
      </div>
    </div>
    <div class="doc-panel">
      <h2 class="doc-section-title">Rally Card</h2>
      {rally_html}
    </div>
    <div class="doc-panel">
      <h2 class="doc-section-title">Frequency Card</h2>
      {freq_html}
    </div>
  </div>
</section>
<section class="doc-section">
  <div class="doc-footer">
    <span>Reference-card sheet for laminating, go-bags, and glovebox carry.</span>
    <span>NOMAD Field Desk</span>
  </div>
</section>'''

        html = render_print_document(
            'Wallet Reference Cards',
            'Compact carry-card sheet combining ICE info, blood type, medications, rally points, and quick comms references.',
            body,
            eyebrow='NOMAD Field Desk Reference Cards',
            meta_items=[f'Generated {esc(now)}', 'Letter print layout'],
            stat_items=[
                ('ICE Contacts', len(ice_contacts)),
                ('Rally Points', len(rally_points)),
                ('Custom Freqs', len(custom_freqs)),
                ('Patient', patient_name or 'Unassigned'),
            ],
            accent_start='#23243c',
            accent_end='#5d375d',
            max_width='1160px',
        )

        return Response(html, mimetype='text/html')

    # ─── SOI Generator ───────────────────────────────────────────────

    @app.route('/api/print/soi')
    def api_print_soi():
        """Generate a Signal Operating Instructions document."""
        with db_session() as db:
            # Node identity
            node_name_row = db.execute("SELECT value FROM settings WHERE key = 'node_name'").fetchone()
            node_name = (node_name_row['value'] if node_name_row and node_name_row['value'] else platform.node()) or 'NOMAD Node'
            node_id_row = db.execute("SELECT value FROM settings WHERE key = 'node_id'").fetchone()
            node_id = node_id_row['value'] if node_id_row and node_id_row['value'] else '???'

            # Frequencies
            freqs = [dict(r) for r in db.execute(
                'SELECT frequency, mode, bandwidth, service, description, notes '
                'FROM freq_database ORDER BY frequency').fetchall()]

            # Radio profiles
            profiles = [dict(r) for r in db.execute(
                'SELECT radio_model, name, channels FROM radio_profiles ORDER BY name').fetchall()]

            # Contacts with callsigns
            contacts = [dict(r) for r in db.execute(
                "SELECT name, callsign, role, freq FROM contacts "
                "WHERE callsign != '' OR freq != '' ORDER BY callsign, name").fetchall()]

        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        date_str = datetime.now().strftime('%d %B %Y')
        frequency_html = '<div class="doc-empty">No frequencies are configured yet. Add them in Comms > Frequencies.</div>'
        if freqs:
            frequency_html = '<div class="doc-table-shell"><table><thead><tr><th>Freq (MHz)</th><th>Mode</th><th>BW</th><th>Service / Net</th><th>Description</th><th>Notes</th></tr></thead><tbody>'
            for f in freqs:
                frequency_html += (
                    f'<tr><td>{esc(str(f["frequency"]))}</td><td>{esc(f.get("mode","") or "-")}</td>'
                    f'<td>{esc(f.get("bandwidth","") or "-")}</td><td class="doc-strong">{esc(f["service"])}</td>'
                    f'<td>{esc(f.get("description","") or "-")}</td><td>{esc(f.get("notes","") or "-")}</td></tr>'
                )
            frequency_html += '</tbody></table></div>'

        contact_html = '<div class="doc-empty">No contacts with callsigns are registered.</div>'
        if contacts:
            contact_html = '<div class="doc-table-shell"><table><thead><tr><th>Callsign</th><th>Operator</th><th>Role</th><th>Primary Freq</th></tr></thead><tbody>'
            for c in contacts:
                contact_html += (
                    f'<tr><td class="doc-strong">{esc(c.get("callsign","") or "-")}</td><td>{esc(c["name"])}</td>'
                    f'<td>{esc(c.get("role","") or "-")}</td><td>{esc(c.get("freq","") or "-")}</td></tr>'
                )
            contact_html += '</tbody></table></div>'

        profile_html = '<div class="doc-empty">No radio profiles are configured.</div>'
        if profiles:
            profile_html = ''
            for prof in profiles:
                heading = esc(prof["name"]) + (f' ({esc(prof["radio_model"])})' if prof.get('radio_model') else '')
                try:
                    channels = json.loads(prof.get('channels') or '[]')
                except (json.JSONDecodeError, TypeError):
                    channels = []
                panel = f'<div class="doc-panel"><h2 class="doc-section-title">{heading}</h2>'
                if channels:
                    panel += '<div class="doc-table-shell"><table><thead><tr><th>Ch</th><th>Freq</th><th>Name / Service</th></tr></thead><tbody>'
                    for i, ch in enumerate(channels):
                        if isinstance(ch, dict):
                            panel += (
                                f'<tr><td>{i + 1}</td><td>{esc(str(ch.get("frequency", ch.get("freq","")))) or "-"}</td>'
                                f'<td>{esc(str(ch.get("name", ch.get("service","")))) or "-"}</td></tr>'
                            )
                        else:
                            panel += f'<tr><td>{i + 1}</td><td colspan="2">{esc(str(ch))}</td></tr>'
                    panel += '</tbody></table></div>'
                else:
                    panel += '<div class="doc-empty">No channels programmed.</div>'
                panel += '</div>'
                profile_html += panel

        body = f'''<section class="doc-section">
  <div class="doc-note-box" style="border-color:#e9b7b7;background:#fff5f5;color:#7a1d1d;">
    <div class="doc-strong" style="letter-spacing:0.12em;text-transform:uppercase;">Restricted</div>
    <div style="margin-top:6px;">Carry only as needed. Destroy when compromised, superseded, or no longer operationally relevant.</div>
  </div>
</section>
<section class="doc-section">
  <h2 class="doc-section-title">Section 1 - Frequency Assignments</h2>
  {frequency_html}
</section>
<section class="doc-section">
  <div class="doc-grid-2">
    <div class="doc-panel doc-panel-strong">
      <h2 class="doc-section-title">Section 2 - Call Sign Matrix</h2>
      {contact_html}
    </div>
    <div class="doc-panel doc-panel-strong">
      <h2 class="doc-section-title">Section 4 - Net Schedule</h2>
      <div class="doc-table-shell"><table><thead><tr><th>Time (Local)</th><th>Net</th><th>Purpose</th></tr></thead><tbody>
        <tr><td>0600</td><td class="doc-strong">Morning Check-in</td><td>Accountability and weather</td></tr>
        <tr><td>1200</td><td class="doc-strong">Midday SITREP</td><td>Status updates</td></tr>
        <tr><td>1800</td><td class="doc-strong">Evening Net</td><td>Planning and coordination</td></tr>
        <tr><td>2100</td><td class="doc-strong">Night Watch</td><td>Security check-in</td></tr>
      </tbody></table></div>
      <div style="margin-top:10px;" class="doc-note-box">All times are local. Modify as needed and monitor the primary net continuously when conditions warrant it.</div>
    </div>
  </div>
</section>
<section class="doc-section">
  <h2 class="doc-section-title">Section 3 - Radio Profiles / Channel Plans</h2>
  <div class="doc-grid-2">{profile_html}</div>
</section>
<section class="doc-section">
  <h2 class="doc-section-title">Section 5 - Authentication &amp; Procedures</h2>
  <div class="doc-table-shell"><table><thead><tr><th>Procedure</th><th>Protocol</th></tr></thead><tbody>
    <tr><td class="doc-strong">Station Identification</td><td>Use callsign at the start and end of each transmission.</td></tr>
    <tr><td class="doc-strong">Emergency Traffic</td><td>&quot;BREAK BREAK BREAK&quot; - all routine traffic stands by.</td></tr>
    <tr><td class="doc-strong">Priority Traffic</td><td>Use a &quot;PRIORITY&quot; prefix so routine traffic yields.</td></tr>
    <tr><td class="doc-strong">Radio Check</td><td>&quot;[Callsign], radio check, over&quot; - respond with signal quality.</td></tr>
    <tr><td class="doc-strong">Relay Request</td><td>Ask the nearest station to &quot;RELAY TO [callsign]&quot; when direct comms fail.</td></tr>
  </tbody></table></div>
</section>
<section class="doc-section">
  <div class="doc-footer">
    <span>SOI generated {esc(now)} for {esc(node_name)} ({esc(node_id)}).</span>
    <span>Restricted handling.</span>
  </div>
</section>'''

        html = render_print_document(
            f'SOI - {node_name}',
            'Signal operating instructions for frequency assignments, callsign mapping, channel plans, net schedules, and radio procedures.',
            body,
            eyebrow='NOMAD Field Desk Communications',
            meta_items=[f'Effective {date_str}', f'Generated {now}', f'Node ID {node_id}', 'Restricted'],
            stat_items=[
                ('Frequencies', len(freqs)),
                ('Operators', len(contacts)),
                ('Profiles', len(profiles)),
                ('Primary Node', node_name),
            ],
            accent_start='#151515',
            accent_end='#444444',
            max_width='1180px',
        )

        return Response(html, mimetype='text/html')

    # ─── Medical Reference Flipbook ─────────────────────────────────

    @app.route('/api/print/medical-flipbook')
    def api_print_medical_flipbook():
        """Generate a printable pocket-sized medical reference flipbook."""
        html = '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Medical Reference Flipbook — NOMAD Field Desk</title>
<style>
@page { size: 4in 6in; margin: 0.25in; }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 9px; line-height: 1.45; margin: 0; padding: 12px; color: #162233; background: #e9eef4; }
.page { width: 3.5in; min-height: 5.5in; padding: 0.28in; page-break-after: always; border: 1px solid #d4dee8; border-radius: 18px; margin: 10px auto; background: linear-gradient(180deg, #fbfdff 0%, #f4f8fb 100%); box-shadow: 0 16px 40px rgba(15, 23, 42, 0.14); position: relative; overflow: hidden; }
.page::before { content: ""; position: absolute; inset: 0 auto auto 0; width: 100%; height: 10px; background: linear-gradient(90deg, #7a1d2a 0%, #b2404d 100%); }
@media print { body { padding: 0; background: #fff; } .page { border: none; border-radius: 0; margin: 0; box-shadow: none; } .page::before { -webkit-print-color-adjust: exact; print-color-adjust: exact; } }
h1 { font-size: 16px; text-align: center; border-bottom: 2px solid #1b3954; padding-bottom: 6px; margin: 0 0 10px 0; color: #152f47; letter-spacing: 0.05em; }
h2 { font-size: 11px; color: #7a1d2a; border-bottom: 1px solid #d7a7af; padding-bottom: 2px; margin: 10px 0 5px 0; text-transform: uppercase; letter-spacing: 0.05em; }
h3 { font-size: 10px; margin: 7px 0 3px 0; color: #28445d; }
table { width: 100%; border-collapse: collapse; font-size: 8px; margin: 5px 0; }
th, td { border: 1px solid #cad6e2; padding: 3px 4px; text-align: left; }
th { background: #eaf1f7; font-weight: bold; color: #30475f; }
.warn { color: #9d2131; font-weight: bold; }
.note { font-size: 8px; color: #586b80; font-style: italic; margin: 3px 0; }
ul, ol { margin: 3px 0; padding-left: 16px; }
li { margin: 2px 0; }
.footer { font-size: 7px; color: #66778a; text-align: center; margin-top: 10px; border-top: 1px solid #dbe4ed; padding-top: 6px; }
.cover-mark { text-align: center; font-size: 8px; text-transform: uppercase; letter-spacing: 0.18em; color: #7a1d2a; margin-top: 14px; }
.cover-subtitle { text-align: center; font-size: 10px; margin: 12px 0; color: #41586f; }
</style></head><body>

<!-- Page 1: Cover + Vital Sign Ranges -->
<div class="page">
<div class="cover-mark">Field Medical Quick Reference</div>
<h1>MEDICAL REFERENCE<br>POCKET FLIPBOOK</h1>
<p class="cover-subtitle">NOMAD Field Desk pocket guide for treatment, triage, and handoff support.</p>

<h2>Normal Vital Sign Ranges</h2>
<table>
<tr><th>Parameter</th><th>Adult</th><th>Child (1-10y)</th><th>Infant (&lt;1y)</th></tr>
<tr><td>Heart Rate</td><td>60-100</td><td>70-120</td><td>100-160</td></tr>
<tr><td>Respiratory Rate</td><td>12-20</td><td>18-30</td><td>30-60</td></tr>
<tr><td>Systolic BP</td><td>90-140</td><td>80-110</td><td>70-90</td></tr>
<tr><td>SpO2</td><td>95-100%</td><td>95-100%</td><td>95-100%</td></tr>
<tr><td>Temperature</td><td>97.8-99.1°F</td><td>97.4-99.6°F</td><td>97.4-99.6°F</td></tr>
<tr><td>GCS</td><td colspan="3">15 (normal), &lt;8 = coma, intubate</td></tr>
</table>

<h2>Glasgow Coma Scale (GCS)</h2>
<table>
<tr><th>Response</th><th>Score</th><th>Description</th></tr>
<tr><td rowspan="4">Eye (E)</td><td>4</td><td>Spontaneous</td></tr>
<tr><td>3</td><td>To voice</td></tr>
<tr><td>2</td><td>To pain</td></tr>
<tr><td>1</td><td>None</td></tr>
<tr><td rowspan="5">Verbal (V)</td><td>5</td><td>Oriented</td></tr>
<tr><td>4</td><td>Confused</td></tr>
<tr><td>3</td><td>Inappropriate words</td></tr>
<tr><td>2</td><td>Incomprehensible sounds</td></tr>
<tr><td>1</td><td>None</td></tr>
<tr><td rowspan="6">Motor (M)</td><td>6</td><td>Obeys commands</td></tr>
<tr><td>5</td><td>Localizes pain</td></tr>
<tr><td>4</td><td>Withdraws from pain</td></tr>
<tr><td>3</td><td>Abnormal flexion</td></tr>
<tr><td>2</td><td>Extension</td></tr>
<tr><td>1</td><td>None</td></tr>
</table>
<div class="footer">Page 1 of 8</div>
</div>

<!-- Page 2: TCCC MARCH Protocol -->
<div class="page">
<h2>TCCC MARCH Protocol</h2>
<h3>M — Massive Hemorrhage</h3>
<ul>
<li>Apply tourniquet HIGH and TIGHT for life-threatening limb bleeding</li>
<li>Note time of application — do NOT remove</li>
<li>Pack junctional wounds with hemostatic gauze</li>
</ul>
<h3>A — Airway</h3>
<ul>
<li>Conscious: let patient assume position of comfort</li>
<li>Unconscious: chin-lift/jaw-thrust, NPA (28Fr), recovery position</li>
<li>Do NOT hyperextend neck if spinal injury suspected</li>
</ul>
<h3>R — Respiration</h3>
<ul>
<li>Expose chest — check for wounds, equal rise</li>
<li>Sucking chest wound → vented chest seal (3 sides taped)</li>
<li>Tension pneumothorax → needle decompression (2nd ICS, MCL)</li>
</ul>
<h3>C — Circulation</h3>
<ul>
<li>Reassess tourniquets</li>
<li>IV/IO access if trained — TXA 1g IV over 10 min</li>
<li>Treat for shock: elevate legs, keep warm, minimize movement</li>
</ul>
<h3>H — Hypothermia / Head Injury</h3>
<ul>
<li>Prevent heat loss — wrap in blankets, remove wet clothing</li>
<li>Head injury: elevate head 30°, monitor GCS q15min</li>
<li>Document all treatments on TCCC card with times</li>
</ul>

<h2>START Triage</h2>
<table>
<tr><th>Category</th><th>Color</th><th>Criteria</th></tr>
<tr><td class="warn">Immediate</td><td style="background:#ff0000;color:white;">RED</td><td>RR &gt;30, no radial pulse, can't follow commands</td></tr>
<tr><td>Delayed</td><td style="background:#ff0;">YELLOW</td><td>Walking: No. Breathing, pulse, follows commands</td></tr>
<tr><td>Minor</td><td style="background:#0f0;">GREEN</td><td>Walking wounded — can walk to treatment area</td></tr>
<tr><td>Expectant</td><td style="background:#333;color:white;">BLACK</td><td>Not breathing after airway opened</td></tr>
</table>
<div class="footer">Page 2 of 8</div>
</div>

<!-- Page 3: Common Drug Dosages -->
<div class="page">
<h2>Common Drug Dosages</h2>
<table>
<tr><th>Drug</th><th>Adult Dose</th><th>Pediatric</th><th>Max/Day</th></tr>
<tr><td>Ibuprofen</td><td>200-400mg q4-6h</td><td>10mg/kg q6-8h</td><td>1200mg</td></tr>
<tr><td>Acetaminophen</td><td>500-1000mg q4-6h</td><td>15mg/kg q4-6h</td><td>3000mg</td></tr>
<tr><td>Diphenhydramine</td><td>25-50mg q4-6h</td><td>1.25mg/kg q6h</td><td>300mg</td></tr>
<tr><td>Amoxicillin</td><td>500mg q8h</td><td>25mg/kg/day ÷3</td><td>3000mg</td></tr>
<tr><td>Loperamide</td><td>4mg then 2mg prn</td><td>See age chart</td><td>16mg</td></tr>
<tr><td>Aspirin</td><td>325-650mg q4h</td><td>NOT &lt;18yo</td><td>4000mg</td></tr>
<tr><td>Prednisone</td><td>5-60mg/day</td><td>1-2mg/kg/day</td><td>60mg</td></tr>
</table>
<p class="warn">ALWAYS check allergies before administering ANY medication!</p>

<h2>Critical Drug Interactions</h2>
<table>
<tr><th>Combination</th><th>Risk</th></tr>
<tr><td>Opioid + Benzo</td><td class="warn">FATAL respiratory depression</td></tr>
<tr><td>Opioid + Alcohol</td><td class="warn">FATAL respiratory depression</td></tr>
<tr><td>SSRI + MAOI</td><td class="warn">Serotonin syndrome — FATAL</td></tr>
<tr><td>Warfarin + NSAIDs</td><td class="warn">Major bleeding risk</td></tr>
<tr><td>ACE inhibitor + K+</td><td class="warn">Hyperkalemia — cardiac arrest</td></tr>
<tr><td>Metformin + Alcohol</td><td>Lactic acidosis risk</td></tr>
<tr><td>Ciprofloxacin + Antacids</td><td>Reduced absorption — separate 2h</td></tr>
</table>

<h2>Pediatric Weight Estimation</h2>
<p><strong>Broselow formula:</strong> Weight (kg) = (Age × 2) + 8<br>
<strong>Example:</strong> 5-year-old ≈ 18 kg</p>
<div class="footer">Page 3 of 8</div>
</div>

<!-- Page 4: Wound Care -->
<div class="page">
<h2>Wound Care Quick Reference</h2>
<h3>Wound Cleaning</h3>
<ul>
<li>Irrigate with clean water — min 250ml under pressure (syringe)</li>
<li>Remove visible debris with tweezers</li>
<li>Do NOT remove embedded objects — stabilize in place</li>
<li>Apply povidone-iodine or dilute betadine around (not in) wound</li>
</ul>

<h3>Wound Closure Decision</h3>
<table>
<tr><th>Close (suture/strips)</th><th>Leave Open</th></tr>
<tr><td>Clean, &lt;6h old</td><td>Contaminated / animal bite</td></tr>
<tr><td>Sharp edge, face</td><td>&gt;6h old (12h face)</td></tr>
<tr><td>Low infection risk</td><td>Crush / devitalized tissue</td></tr>
</table>

<h3>Infection Signs (watch for)</h3>
<ul>
<li>Increasing redness spreading from wound (cellulitis)</li>
<li>Warmth, swelling, purulent drainage</li>
<li>Red streaks (lymphangitis) — <span class="warn">URGENT — start antibiotics</span></li>
<li>Fever &gt;100.4°F with wound — systemic infection</li>
</ul>

<h3>Burn Classification</h3>
<table>
<tr><th>Degree</th><th>Appearance</th><th>Treatment</th></tr>
<tr><td>1st (Superficial)</td><td>Red, painful, no blisters</td><td>Cool water, aloe, ibuprofen</td></tr>
<tr><td>2nd (Partial)</td><td>Blisters, very painful</td><td>Do NOT pop blisters, loose dressing</td></tr>
<tr><td>3rd (Full)</td><td>White/charred, painless</td><td class="warn">Evac — needs grafting</td></tr>
</table>
<p class="note">Rule of 9s (BSA): Head 9%, each arm 9%, chest 18%, back 18%, each leg 18%, groin 1%</p>

<h3>Tourniquet Rules</h3>
<ul>
<li>Apply 2-3 inches above wound, NEVER on joint</li>
<li>Tighten until bleeding stops — it WILL hurt</li>
<li>Write "T" and TIME on forehead or tourniquet</li>
<li class="warn">Do NOT remove in field — leave for surgeon</li>
</ul>
<div class="footer">Page 4 of 8</div>
</div>

<!-- Page 5: Allergic Reactions & Anaphylaxis -->
<div class="page">
<h2>Anaphylaxis Protocol</h2>
<h3>Signs (any 2+ systems = anaphylaxis)</h3>
<ul>
<li><strong>Skin:</strong> Hives, flushing, itching, swelling</li>
<li><strong>Respiratory:</strong> Wheezing, stridor, throat tightness, SOB</li>
<li><strong>Cardiovascular:</strong> Hypotension, tachycardia, pale, dizzy</li>
<li><strong>GI:</strong> Nausea, vomiting, cramping, diarrhea</li>
</ul>
<h3>Treatment — IMMEDIATE</h3>
<ol>
<li><strong>Epinephrine IM</strong> — lateral thigh<br>
Adult: 0.3mg (EpiPen) | Child: 0.15mg (EpiPen Jr) | Infant: 0.01mg/kg</li>
<li>Call for evacuation — this is life-threatening</li>
<li>Position: supine with legs elevated (sitting if breathing difficulty)</li>
<li>Diphenhydramine 50mg PO/IM (adult) — secondary, NOT a substitute for epi</li>
<li>Monitor airway, repeat epi q5-15min if no improvement</li>
<li>After epi — observe min 4 hours (biphasic reaction risk)</li>
</ol>

<h2>Choking (Heimlich / BLS)</h2>
<h3>Conscious Adult/Child</h3>
<ul>
<li>Encourage coughing if partial obstruction</li>
<li>Complete obstruction: 5 back blows → 5 abdominal thrusts, repeat</li>
<li>Pregnant/obese: chest thrusts instead of abdominal</li>
</ul>
<h3>Infant (&lt;1 year)</h3>
<ul>
<li>5 back slaps (face down, head lower) → 5 chest thrusts (face up)</li>
<li class="warn">NO abdominal thrusts on infants</li>
</ul>
<h3>Unconscious</h3>
<ul>
<li>Begin CPR — 30 compressions : 2 breaths</li>
<li>Check mouth for visible object before each breath</li>
</ul>

<h2>CPR Quick Reference</h2>
<table>
<tr><th></th><th>Adult</th><th>Child</th><th>Infant</th></tr>
<tr><td>Rate</td><td colspan="3">100-120/min</td></tr>
<tr><td>Depth</td><td>2-2.4 in</td><td>2 in (~1/3 chest)</td><td>1.5 in</td></tr>
<tr><td>Ratio</td><td colspan="3">30:2 (1 rescuer) / 15:2 (2 rescuer child/infant)</td></tr>
<tr><td>Hands</td><td>2 hands</td><td>1-2 hands</td><td>2 fingers</td></tr>
</table>
<div class="footer">Page 5 of 8</div>
</div>

<!-- Page 6: Fractures, Splinting, Spine -->
<div class="page">
<h2>Fracture & Splinting</h2>
<h3>Assessment</h3>
<ul>
<li>Check <strong>CSM</strong> distal to injury: Circulation (pulse, color), Sensation, Movement</li>
<li>Deformity, swelling, crepitus, point tenderness</li>
<li>Open fracture (bone visible) = <span class="warn">HIGH infection risk — cover, do NOT push back</span></li>
</ul>
<h3>Splinting Principles</h3>
<ul>
<li>Splint in position found — do NOT straighten angulated fractures</li>
<li>Immobilize joint ABOVE and BELOW fracture</li>
<li>Pad all bony prominences</li>
<li>Check CSM before AND after splinting</li>
<li>Elevate if possible, ice 20 min on / 20 off</li>
</ul>

<h2>Spinal Motion Restriction</h2>
<h3>Suspect if:</h3>
<ul>
<li>Fall &gt;3× body height, diving injury, high-speed MVC</li>
<li>Neck pain, numbness/tingling in extremities</li>
<li>Altered mental status with trauma mechanism</li>
</ul>
<h3>Management:</h3>
<ul>
<li>Manual in-line stabilization — hold head in neutral</li>
<li>Log-roll with 3+ people</li>
<li>Improvised collar: SAM splint + tape, towel rolls + tape</li>
</ul>

<h2>Hypothermia Staging</h2>
<table>
<tr><th>Stage</th><th>Temp</th><th>Signs</th><th>Treatment</th></tr>
<tr><td>Mild</td><td>90-95°F</td><td>Shivering, cold</td><td>Warm drinks, blankets, active movement</td></tr>
<tr><td>Moderate</td><td>82-90°F</td><td>Shivering stops, confused</td><td>Gentle warming, warm IV, no active movement</td></tr>
<tr><td>Severe</td><td>&lt;82°F</td><td>Unconscious, barely alive</td><td class="warn">Handle GENTLY — evac. No rough movement</td></tr>
</table>
<p class="warn">Cold patients are NOT dead until warm and dead. Continue CPR.</p>

<h2>Heat Emergencies</h2>
<table>
<tr><th>Condition</th><th>Signs</th><th>Treatment</th></tr>
<tr><td>Heat Exhaustion</td><td>Heavy sweat, weak, nausea, temp &lt;104°F</td><td>Cool, rest, ORS, fans, remove clothing</td></tr>
<tr><td class="warn">Heat Stroke</td><td>Hot/dry skin, AMS, temp &gt;104°F</td><td class="warn">EMERGENCY — ice packs (neck/groin/axilla), cold water immersion, evac</td></tr>
</table>
<div class="footer">Page 6 of 8</div>
</div>

<!-- Page 7: Envenomation & Environmental -->
<div class="page">
<h2>Snake Bite Protocol</h2>
<ul>
<li>Keep calm, immobilize limb below heart level</li>
<li>Mark edge of swelling with pen + time</li>
<li>Remove rings/jewelry before swelling</li>
<li>Do NOT: tourniquet, cut, suck, ice, or apply electricity</li>
<li>Photograph the snake if safe to do so</li>
<li><span class="warn">Evacuate for antivenom — time is critical</span></li>
</ul>

<h2>Insect Stings</h2>
<ul>
<li>Remove stinger by scraping (don't squeeze)</li>
<li>Clean, ice, diphenhydramine for reaction</li>
<li>Watch for anaphylaxis (see page 5)</li>
</ul>

<h2>Drowning / Submersion</h2>
<ul>
<li>Remove from water — protect YOUR safety first</li>
<li>Assume spinal injury if diving/unknown</li>
<li>Begin CPR immediately — even if water in lungs</li>
<li>5 rescue breaths first (drowning = respiratory arrest)</li>
<li>Do NOT attempt abdominal thrusts to clear water</li>
</ul>

<h2>Chest Pain / Suspected MI</h2>
<ul>
<li>Aspirin 325mg chewed (if no allergy/bleeding)</li>
<li>Position of comfort (usually sitting up)</li>
<li>Loosen clothing, reassure</li>
<li>Nitroglycerin if prescribed (NOT with ED meds in past 48h)</li>
<li>Prepare for CPR — cardiac arrest common</li>
</ul>

<h2>Seizure Management</h2>
<ul>
<li>Protect from injury — clear area, pad head</li>
<li>Turn on side (recovery position) after seizure</li>
<li>Time the seizure — <span class="warn">&gt;5 min = status epilepticus = EMERGENCY</span></li>
<li>Do NOT restrain or put anything in mouth</li>
</ul>

<h2>Diabetic Emergencies</h2>
<table>
<tr><th></th><th>Hypoglycemia (Low)</th><th>Hyperglycemia (High)</th></tr>
<tr><td>Onset</td><td>Rapid (minutes)</td><td>Gradual (hours/days)</td></tr>
<tr><td>Signs</td><td>Shaky, sweaty, confused, seizure</td><td>Thirsty, frequent urination, fruity breath</td></tr>
<tr><td>Treatment</td><td class="warn">Sugar NOW — glucose tabs, juice, candy</td><td>Fluids, insulin if available, evac</td></tr>
</table>
<p class="note">When in doubt between high/low sugar, GIVE SUGAR — low sugar kills faster.</p>
<div class="footer">Page 7 of 8</div>
</div>

<!-- Page 8: SBAR + Notes -->
<div class="page">
<h2>SBAR Handoff Format</h2>
<table>
<tr><th>S</th><td><strong>Situation</strong> — "I'm calling about [patient]. They are [current state]."</td></tr>
<tr><th>B</th><td><strong>Background</strong> — Age, conditions, allergies, medications, events leading here</td></tr>
<tr><th>A</th><td><strong>Assessment</strong> — "I think the problem is..." Vitals, exam findings</td></tr>
<tr><th>R</th><td><strong>Recommendation</strong> — "I need you to..." What you want done</td></tr>
</table>

<h2>9-Line MEDEVAC Request</h2>
<table>
<tr><td>Line 1</td><td>Location (grid/GPS)</td></tr>
<tr><td>Line 2</td><td>Radio frequency + call sign</td></tr>
<tr><td>Line 3</td><td># patients by precedence (A=Urgent, B=Priority, C=Routine)</td></tr>
<tr><td>Line 4</td><td>Special equipment (A=None, B=Hoist, C=Extraction, D=Ventilator)</td></tr>
<tr><td>Line 5</td><td># patients by type (L=Litter, A=Ambulatory)</td></tr>
<tr><td>Line 6</td><td>Security at pickup (N=No enemy, P=Possible, E=Enemy, X=Armed escort)</td></tr>
<tr><td>Line 7</td><td>Method of marking (A=Panels, B=Pyro, C=Smoke, D=None, E=Other)</td></tr>
<tr><td>Line 8</td><td>Patient nationality + status</td></tr>
<tr><td>Line 9</td><td>Terrain / obstacles (NBC contamination if applicable)</td></tr>
</table>

<h2>Personal Notes</h2>
<div style="min-height:120px;border:1px dashed #999;padding:4px;margin:4px 0;">
<!-- Blank space for handwritten notes -->
</div>

<div class="footer" style="margin-top:16px;">
<strong>NOMAD Field Desk</strong> — Offline Medical Reference Flipbook<br>
''' + f'Generated {__import__("time").strftime("%Y-%m-%d %H:%M")}' + '''<br>
<em>This is a reference guide, not a substitute for medical training. Seek professional care when available.</em>
</div>
</div>

</body></html>'''
        return Response(html, mimetype='text/html')

    # ═════════════════════════════════════════════════════════════════
    # PHASE 19 — Database Integrity, Self-Test, Undo
    # ═════════════════════════════════════════════════════════════════

    # ─── Database Integrity Check ────────────────────────────────────

    @app.route('/api/system/db-check', methods=['POST'])
    def api_system_db_check():
        """Run PRAGMA integrity_check and foreign_key_check."""
        with db_session() as db:
            integrity = db.execute('PRAGMA integrity_check').fetchall()
            fk_check = db.execute('PRAGMA foreign_key_check').fetchall()

        integrity_results = [dict(r) for r in integrity] if integrity else []
        fk_results = [dict(r) for r in fk_check] if fk_check else []

        # integrity_check returns [{'integrity_check': 'ok'}] when healthy
        ok = (len(integrity_results) == 1 and
              integrity_results[0].get('integrity_check') == 'ok' and
              len(fk_results) == 0)

        return jsonify({
            'status': 'ok' if ok else 'issues_found',
            'integrity_check': integrity_results,
            'foreign_key_check': fk_results,
        })

    @app.route('/api/system/db-vacuum', methods=['POST'])
    def api_system_db_vacuum():
        """Run VACUUM and REINDEX to optimize the database."""
        with db_session() as db:
            db.execute('VACUUM')
            db.execute('REINDEX')
        log_activity('db_vacuum', 'system', 'Database vacuumed and reindexed')
        return jsonify({'status': 'ok', 'message': 'VACUUM and REINDEX completed'})

    # ─── Startup Self-Test ───────────────────────────────────────────

    @app.route('/api/system/self-test')
    def api_system_self_test():
        """Run comprehensive self-test and return pass/fail per check."""
        results = []

        # 1. Database accessible
        try:
            with db_session() as db:
                db.execute('SELECT 1').fetchone()
            results.append({'check': 'database', 'status': 'pass', 'detail': 'Database accessible'})
        except Exception as e:
            results.append({'check': 'database', 'status': 'fail', 'detail': str(e)})

        # 2. Disk space > 100MB free
        try:
            from config import get_data_dir
            stat = shutil.disk_usage(get_data_dir())
            free_mb = stat.free / (1024 * 1024)
            if free_mb > 100:
                results.append({'check': 'disk_space', 'status': 'pass',
                                'detail': f'{free_mb:.0f} MB free'})
            else:
                results.append({'check': 'disk_space', 'status': 'fail',
                                'detail': f'Only {free_mb:.0f} MB free (need >100 MB)'})
        except Exception as e:
            results.append({'check': 'disk_space', 'status': 'fail', 'detail': str(e)})

        # 3. Service binaries exist (if installed)
        from services import ollama as _ollama, kiwix as _kiwix
        for svc_name, svc_mod in [('ollama', _ollama), ('kiwix', _kiwix)]:
            try:
                if svc_mod.is_installed():
                    exe = getattr(svc_mod, 'get_exe_path', None)
                    if exe:
                        path = exe()
                        if os.path.isfile(path):
                            results.append({'check': f'{svc_name}_binary', 'status': 'pass',
                                            'detail': f'Binary exists at {path}'})
                        else:
                            results.append({'check': f'{svc_name}_binary', 'status': 'fail',
                                            'detail': f'Binary missing: {path}'})
                    else:
                        results.append({'check': f'{svc_name}_binary', 'status': 'pass',
                                        'detail': 'Installed (no exe check)'})
            except Exception as e:
                results.append({'check': f'{svc_name}_binary', 'status': 'fail', 'detail': str(e)})

        # 4. Port conflicts
        import socket
        for port, label in [(5000, 'flask'), (11434, 'ollama')]:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1)
                result_code = s.connect_ex(('127.0.0.1', port))
                s.close()
                if result_code == 0:
                    results.append({'check': f'port_{port}', 'status': 'pass',
                                    'detail': f'{label} port {port} responding'})
                else:
                    results.append({'check': f'port_{port}', 'status': 'warn',
                                    'detail': f'{label} port {port} not responding'})
            except Exception as e:
                results.append({'check': f'port_{port}', 'status': 'warn', 'detail': str(e)})

        # 5. Python version
        py_ver = platform.python_version()
        py_ok = sys.version_info >= (3, 9)
        results.append({'check': 'python_version', 'status': 'pass' if py_ok else 'warn',
                        'detail': f'Python {py_ver}'})

        # 6. Critical tables exist
        critical_tables = [
            'settings', 'inventory', 'contacts', 'incidents', 'activity_log',
            'weather_log', 'patients', 'waypoints', 'alerts', 'power_log',
        ]
        try:
            with db_session() as db:
                existing = [r[0] for r in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            missing = [t for t in critical_tables if t not in existing]
            if not missing:
                results.append({'check': 'critical_tables', 'status': 'pass',
                                'detail': f'All {len(critical_tables)} critical tables present'})
            else:
                results.append({'check': 'critical_tables', 'status': 'fail',
                                'detail': f'Missing tables: {", ".join(missing)}'})
        except Exception as e:
            results.append({'check': 'critical_tables', 'status': 'fail', 'detail': str(e)})

        all_pass = all(r['status'] == 'pass' for r in results)
        any_fail = any(r['status'] == 'fail' for r in results)

        return jsonify({
            'overall': 'pass' if all_pass else ('fail' if any_fail else 'warn'),
            'checks': results,
            'timestamp': datetime.now().isoformat(),
        })

    # ─── Undo System ─────────────────────────────────────────────────

    @app.route('/api/undo', methods=['GET'])
    def api_undo_peek():
        """Return the last undoable action (if within TTL)."""
        _prune_expired()
        with _undo_lock:
            if not _undo_stack:
                return jsonify({'available': False})
            entry = _undo_stack[-1]
            return jsonify({
                'available': True,
                'action_type': entry['action_type'],
                'description': entry['description'],
                'seconds_remaining': max(0, int(30 - (time.time() - entry['timestamp']))),
            })

    @app.route('/api/undo', methods=['POST'])
    def api_undo_execute():
        """Undo the last destructive action."""
        _prune_expired()
        with _undo_lock:
            if not _undo_stack:
                return jsonify({'error': 'Nothing to undo (expired or empty)'}), 404

            entry = _undo_stack.pop()

        table = entry['table']
        row_data = entry['row_data']

        if table not in _UNDO_VALID_TABLES:
            # Restore entry to stack since we couldn't process it
            with _undo_lock:
                _undo_stack.append(entry)
            return jsonify({'error': f'Undo refused: invalid table "{table}"'}), 400

        # Validate column names against actual table schema to prevent SQL injection
        try:
            with db_session() as db:
                valid_cols = {r['name'] for r in db.execute(f"PRAGMA table_info({table})").fetchall()}
                if not valid_cols:
                    with _undo_lock:
                        _undo_stack.append(entry)
                    return jsonify({'error': 'Undo failed: unknown table schema'}), 400

                if entry['action_type'] == 'delete':
                    # Re-insert the deleted row — only use columns that exist in the table
                    cols = [c for c in row_data.keys() if c in valid_cols]
                    if not cols:
                        with _undo_lock:
                            _undo_stack.append(entry)
                        return jsonify({'error': 'Undo failed: no valid columns'}), 400
                    placeholders = ', '.join(['?'] * len(cols))
                    col_names = ', '.join(cols)
                    db.execute(
                        f'INSERT INTO {table} ({col_names}) VALUES ({placeholders})',
                        [row_data[c] for c in cols])
                    db.commit()
                elif entry['action_type'] == 'update':
                    # Restore previous values — only use columns that exist in the table
                    row_id = row_data.get('id')
                    if row_id is not None:
                        safe_keys = [k for k in row_data if k != 'id' and k in valid_cols]
                        if not safe_keys:
                            with _undo_lock:
                                _undo_stack.append(entry)
                            return jsonify({'error': 'Undo failed: no valid columns'}), 400
                        sets = ', '.join(f'{k} = ?' for k in safe_keys)
                        vals = [row_data[k] for k in safe_keys]
                        vals.append(row_id)
                        db.execute(f'UPDATE {table} SET {sets} WHERE id = ?', vals)
                        db.commit()
                # Only move to redo stack after successful DB operation
                with _undo_lock:
                    _redo_stack.append(entry)
                log_activity('undo', 'system', entry['description'])
        except Exception as e:
            # Restore entry to stack on failure
            with _undo_lock:
                _undo_stack.append(entry)
            log.error('Undo failed: %s', e)
            return jsonify({'error': 'Undo failed'}), 500

        return jsonify({
            'status': 'undone',
            'description': entry['description'],
        })

    @app.route('/api/redo', methods=['POST'])
    def api_redo():
        """Redo the last undone action."""
        with _undo_lock:
            if not _redo_stack:
                return jsonify({'error': 'Nothing to redo'}), 404

            entry = _redo_stack.pop()

        table = entry['table']
        row_data = entry['row_data']

        if table not in _UNDO_VALID_TABLES:
            with _undo_lock:
                _redo_stack.append(entry)
            return jsonify({'error': f'Redo refused: invalid table "{table}"'}), 400

        try:
            with db_session() as db:
                valid_cols = {r['name'] for r in db.execute(f"PRAGMA table_info({table})").fetchall()}
                if not valid_cols:
                    with _undo_lock:
                        _redo_stack.append(entry)
                    return jsonify({'error': 'Redo failed: unknown table schema'}), 400

                if entry['action_type'] == 'delete':
                    # Original action was a delete — redo means delete the row again
                    row_id = row_data.get('id')
                    if row_id is not None:
                        db.execute(f'DELETE FROM {table} WHERE id = ?', [row_id])
                        db.commit()
                    else:
                        with _undo_lock:
                            _redo_stack.append(entry)
                        return jsonify({'error': 'Redo failed: no row id'}), 400
                elif entry['action_type'] == 'update':
                    with _undo_lock:
                        _redo_stack.append(entry)
                    return jsonify({'error': 'Redo not supported for updates'}), 400

                # Only move to undo stack after successful DB operation
                with _undo_lock:
                    _undo_stack.append(entry)
                log_activity('redo', 'system', entry['description'])
        except Exception as e:
            with _undo_lock:
                _redo_stack.append(entry)
            log.error('Redo failed: %s', e)
            return jsonify({'error': 'Redo failed'}), 500

        return jsonify({
            'status': 'redone',
            'description': entry['description'],
        })

    # ═════════════════════════════════════════════════════════════════
    # PHASE 20 — Federation: Community Readiness, Skills, Alert Relay
    # ═════════════════════════════════════════════════════════════════

    # ─── Community Readiness Dashboard ───────────────────────────────

    @app.route('/api/federation/community-readiness')
    def api_federation_community_readiness():
        """Aggregate readiness scores across all federated nodes."""
        with db_session() as db:
            rows = db.execute(
                'SELECT node_id, node_name, situation, updated_at FROM federation_sitboard '
                'ORDER BY updated_at DESC').fetchall()

        CATEGORIES = ['water', 'food', 'medical', 'shelter', 'security', 'comms', 'power']
        nodes = []
        network_totals = {cat: [] for cat in CATEGORIES}

        for row in rows:
            try:
                sit = json.loads(row['situation'] or '{}')
            except (json.JSONDecodeError, TypeError):
                sit = {}

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

    # ─── Skill Matching ──────────────────────────────────────────────

    @app.route('/api/federation/skill-search')
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
                'SELECT node_id, node_name, situation FROM federation_sitboard').fetchall()
            for peer in peers:
                try:
                    sit = json.loads(peer['situation'] or '{}')
                except (json.JSONDecodeError, TypeError):
                    sit = {}
                # Check shared_contacts or skills in situation data
                shared_contacts = sit.get('contacts', sit.get('shared_contacts', []))
                if isinstance(shared_contacts, list):
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
                "WHERE LOWER(skills) LIKE ?", (f'%{query}%',)
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

    # ─── Distributed Alert Relay ─────────────────────────────────────

    @app.route('/api/federation/relay-alert', methods=['POST'])
    def api_federation_relay_alert():
        """Send an alert to all trusted federation peers."""
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
            except Exception as e:
                failed.append({'node': peer['node_name'] or peer['node_id'],
                               'error': str(e)})

        log_activity('alert_relayed', 'federation',
                     f'Alert "{alert_title}" sent to {sent}/{len(peers)} peers')

        return jsonify({
            'status': 'relayed',
            'sent': sent,
            'total_peers': len(peers),
            'failed': failed,
        })

    # ─── Expose undo push helper for other routes ────────────────────
    # Attach to app so app.py routes can use it if needed
    app.push_undo = _push_undo
