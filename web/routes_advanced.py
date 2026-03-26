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
from collections import deque
from datetime import datetime, timedelta
from html import escape as esc
from flask import jsonify, request, Response

from db import get_db, log_activity
from services import ollama

log = logging.getLogger('nomad.web')

# ─── Undo System (Phase 19) ─────────────────────────────────────────
# Module-level deque: stores last 10 destructive operations with 30s TTL
_undo_stack = deque(maxlen=10)

_UNDO_VALID_TABLES = {'inventory', 'contacts', 'notes', 'waypoints', 'documents',
                       'videos', 'audio', 'books', 'checklists', 'weather_log',
                       'sensor_devices', 'sensor_readings', 'journal', 'patients',
                       'vitals_log', 'wound_log', 'cameras', 'access_log',
                       'power_devices', 'power_log', 'incidents', 'comms_log',
                       'seeds', 'harvest_log', 'livestock', 'preservation_log',
                       'garden_plots', 'fuel_storage', 'equipment_log',
                       'ammo_inventory', 'community_resources', 'radiation_log',
                       'scheduled_tasks', 'skills'}


def _push_undo(action_type, description, table, row_data):
    """Push an undoable action onto the stack."""
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
    while _undo_stack and _undo_stack[0]['timestamp'] < cutoff:
        _undo_stack.popleft()


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

        db = get_db()
        try:
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
                'WHERE quantity <= min_quantity AND min_quantity > 0 ORDER BY category'
            ).fetchall()
            if low_stock:
                ctx_parts.append('LOW STOCK ALERTS:\n' + '\n'.join(
                    f'  {r["name"]} ({r["category"]}): {r["quantity"]} {r["unit"]} (min: {r["min_quantity"]})'
                    for r in low_stock))

            # Inventory — newly expired (expiration within last 7 days or already expired)
            expired = db.execute(
                "SELECT name, quantity, unit, expiration FROM inventory "
                "WHERE expiration != '' AND expiration <= date('now') ORDER BY expiration"
            ).fetchall()
            if expired:
                ctx_parts.append('EXPIRED ITEMS:\n' + '\n'.join(
                    f'  {r["name"]}: {r["quantity"]} {r["unit"]} (expired {r["expiration"]})'
                    for r in expired))

            # Incidents in last 24h
            incidents = db.execute(
                "SELECT severity, category, description, created_at FROM incidents "
                "WHERE created_at >= datetime('now', '-24 hours') ORDER BY created_at DESC"
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
                'SELECT category, COUNT(*) as cnt, SUM(quantity) as total FROM inventory GROUP BY category'
            ).fetchall()
            if inv_summary:
                ctx_parts.append('INVENTORY SUMMARY: ' + ', '.join(
                    f'{r["category"]}: {r["cnt"]} items' for r in inv_summary))

            # Team count
            team_count = db.execute('SELECT COUNT(*) as c FROM contacts').fetchone()['c']
            if team_count:
                ctx_parts.append(f'TEAM: {team_count} contacts registered')

        finally:
            db.close()

        context = '\n\n'.join(ctx_parts) if ctx_parts else 'No operational data recorded yet.'

        system_prompt = f"""You are a military-style intelligence officer generating a SITREP (Situation Report) for a survival/preparedness command center called N.O.M.A.D.

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
            return jsonify({'error': str(e)}), 500

    # ─── AI Action Execution ─────────────────────────────────────────

    @app.route('/api/ai/execute-action', methods=['POST'])
    def api_ai_execute_action():
        """Parse and execute a natural-language action command."""
        data = request.get_json() or {}
        action = data.get('action', '').strip()
        if not action:
            return jsonify({'error': 'No action provided'}), 400

        # Pattern: "add [qty] [item] to inventory"
        m = re.match(r'add\s+(\d+)\s+(.+?)\s+to\s+inventory', action, re.IGNORECASE)
        if m:
            qty = int(m.group(1))
            item_name = m.group(2).strip()
            db = get_db()
            try:
                db.execute(
                    'INSERT INTO inventory (name, quantity, category) VALUES (?, ?, ?)',
                    (item_name, qty, 'other'))
                db.commit()
                row_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
                log_activity('inventory_added', 'ai', f'Added {qty} {item_name} via AI action')
            finally:
                db.close()
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
            db = get_db()
            try:
                db.execute(
                    'INSERT INTO incidents (severity, category, description) VALUES (?, ?, ?)',
                    ('info', 'other', desc))
                db.commit()
                row_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
                log_activity('incident_logged', 'ai', f'Incident: {desc[:80]}')
            finally:
                db.close()
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
            db = get_db()
            try:
                db.execute('INSERT INTO notes (title, content) VALUES (?, ?)', (title, ''))
                db.commit()
                row_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
                log_activity('note_created', 'ai', f'Note: {title}')
            finally:
                db.close()
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
            lat = float(m.group(2))
            lng = float(m.group(3))
            db = get_db()
            try:
                db.execute(
                    'INSERT INTO waypoints (name, lat, lng) VALUES (?, ?, ?)',
                    (wp_name, lat, lng))
                db.commit()
                row_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
                log_activity('waypoint_added', 'ai', f'Waypoint: {wp_name} ({lat},{lng})')
            finally:
                db.close()
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
        db = get_db()
        try:
            row = db.execute("SELECT value FROM settings WHERE key = 'ai_memory'").fetchone()
        finally:
            db.close()
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
        db = get_db()
        try:
            row = db.execute("SELECT value FROM settings WHERE key = 'ai_memory'").fetchone()
            memories = []
            if row and row['value']:
                try:
                    memories = json.loads(row['value'])
                except (json.JSONDecodeError, TypeError):
                    pass
            memories.append({'fact': fact, 'saved_at': datetime.now().isoformat()})
            db.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('ai_memory', ?)",
                (json.dumps(memories),))
            db.commit()
        finally:
            db.close()
        log_activity('ai_memory_saved', 'ai', f'Memory: {fact[:60]}')
        return jsonify({'status': 'saved', 'count': len(memories)})

    @app.route('/api/ai/memory', methods=['DELETE'])
    def api_ai_memory_clear():
        """Clear all AI memory."""
        db = get_db()
        try:
            db.execute("DELETE FROM settings WHERE key = 'ai_memory'")
            db.commit()
        finally:
            db.close()
        log_activity('ai_memory_cleared', 'ai', 'All AI memories cleared')
        return jsonify({'status': 'cleared'})

    # ═════════════════════════════════════════════════════════════════
    # PHASE 18 — Print / Operations Binder, Wallet Cards, SOI
    # ═════════════════════════════════════════════════════════════════

    # ─── Operations Binder ───────────────────────────────────────────

    @app.route('/api/print/operations-binder')
    def api_print_operations_binder():
        """Generate a comprehensive printable operations binder."""
        db = get_db()
        try:
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

        finally:
            db.close()

        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        date_str = datetime.now().strftime('%d %B %Y')

        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Operations Binder — {esc(node_name)}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Courier New', Courier, monospace; font-size: 10px; color: #000; line-height: 1.4; }}
h1 {{ font-size: 20px; margin-bottom: 4px; }}
h2 {{ font-size: 14px; background: #222; color: #fff; padding: 4px 8px; margin: 12px 0 6px; page-break-after: avoid; }}
h3 {{ font-size: 11px; margin: 8px 0 4px; border-bottom: 1px solid #999; }}
table {{ width: 100%; border-collapse: collapse; margin-bottom: 8px; }}
th, td {{ border: 1px solid #999; padding: 2px 5px; font-size: 9px; text-align: left; }}
th {{ background: #ddd; font-weight: 700; }}
.cover {{ text-align: center; padding: 120px 40px; page-break-after: always; }}
.cover h1 {{ font-size: 36px; border-bottom: 4px solid #000; padding-bottom: 8px; display: inline-block; }}
.cover .date {{ font-size: 16px; margin-top: 20px; }}
.cover .subtitle {{ font-size: 14px; margin-top: 8px; color: #555; }}
.toc {{ page-break-after: always; padding: 20px; }}
.toc h2 {{ background: none; color: #000; border-bottom: 2px solid #000; padding: 0 0 4px; }}
.toc ol {{ padding-left: 20px; font-size: 12px; line-height: 2; }}
.section {{ padding: 10px 15px; }}
.page-break {{ page-break-before: always; }}
.card {{ border: 2px solid #000; border-radius: 4px; padding: 6px 8px; margin-bottom: 6px; page-break-inside: avoid; }}
.card h3 {{ border: none; margin: 0 0 4px; }}
.field {{ margin-bottom: 2px; }}
.label {{ font-weight: 700; }}
.status-good {{ color: #060; }}
.status-warn {{ color: #960; }}
.status-bad {{ color: #c00; }}
.map-placeholder {{ border: 2px dashed #999; padding: 20px; text-align: center; color: #666; margin: 8px 0; }}
@media print {{
    body {{ margin: 0; }}
    @page {{ size: letter; margin: 15mm; }}
    .no-print {{ display: none; }}
}}
@media screen {{
    body {{ max-width: 8.5in; margin: 0 auto; padding: 10px; background: #f5f5f5; }}
    .section {{ background: #fff; margin-bottom: 10px; border: 1px solid #ccc; }}
}}
</style>
</head>
<body>

<!-- COVER PAGE -->
<div class="cover">
<h1>OPERATIONS BINDER</h1>
<div class="subtitle">N.O.M.A.D. Survival Command Center</div>
<div class="date" style="font-size:20px; margin-top:30px;">{esc(node_name)}</div>
<div class="date">{esc(date_str)}</div>
<div style="margin-top:60px; font-size:10px; color:#999;">Generated {esc(now)} &mdash; CONFIDENTIAL</div>
</div>

<!-- TABLE OF CONTENTS -->
<div class="toc">
<h2>TABLE OF CONTENTS</h2>
<ol>
<li>Emergency Contacts Directory</li>
<li>Frequency Reference Card</li>
<li>Medical Patient Cards</li>
<li>Inventory Summary</li>
<li>Active Checklists</li>
<li>Waypoints &amp; Rally Points</li>
<li>Emergency Procedures</li>
<li>Family Emergency Plan</li>
</ol>
</div>

<!-- 1. EMERGENCY CONTACTS -->
<div class="section page-break">
<h2>1. EMERGENCY CONTACTS DIRECTORY</h2>'''

        if contacts:
            html += '''<table>
<tr><th>Name</th><th>Callsign</th><th>Role</th><th>Phone</th><th>Email</th><th>Freq</th><th>Blood</th><th>Rally Point</th></tr>'''
            for c in contacts:
                html += (f'<tr><td>{esc(c["name"])}</td><td>{esc(c.get("callsign","") or "")}</td>'
                         f'<td>{esc(c.get("role","") or "")}</td><td>{esc(c.get("phone","") or "")}</td>'
                         f'<td>{esc(c.get("email","") or "")}</td><td>{esc(c.get("freq","") or "")}</td>'
                         f'<td>{esc(c.get("blood_type","") or "")}</td>'
                         f'<td>{esc(c.get("rally_point","") or "")}</td></tr>')
            html += '</table>'
        else:
            html += '<p style="color:#999;">No contacts registered.</p>'

        # 2. FREQUENCY REFERENCE
        html += '''</div>
<div class="section page-break">
<h2>2. FREQUENCY REFERENCE CARD</h2>'''
        if freqs:
            html += '<table><tr><th>Frequency</th><th>Mode</th><th>Service</th><th>Description</th></tr>'
            for f in freqs:
                html += (f'<tr><td>{esc(str(f["frequency"]))}</td><td>{esc(f.get("mode","") or "")}</td>'
                         f'<td>{esc(f["service"])}</td><td>{esc(f.get("description","") or "")}</td></tr>')
            html += '</table>'
        else:
            html += '''<p style="color:#666;">No custom frequencies in database. Standard reference:</p>
<table><tr><th>Service</th><th>Freq (MHz)</th><th>Notes</th></tr>
<tr><td>FRS Ch 1</td><td>462.5625</td><td>Family Radio primary</td></tr>
<tr><td>MURS Ch 1</td><td>151.820</td><td>No license required</td></tr>
<tr><td>2m Call</td><td>146.520</td><td>National simplex calling</td></tr>
<tr><td>70cm Call</td><td>446.000</td><td>National simplex calling</td></tr>
<tr><td>CB Ch 9</td><td>27.065</td><td>Emergency channel</td></tr>
<tr><td>NOAA WX</td><td>162.550</td><td>Weather broadcast</td></tr>
</table>'''

        # 3. MEDICAL PATIENT CARDS
        html += '''</div>
<div class="section page-break">
<h2>3. MEDICAL PATIENT CARDS</h2>'''
        if patients:
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
                html += f'''<div class="card">
<h3>{esc(p["name"])}</h3>
<div class="field"><span class="label">Age:</span> {esc(str(p.get("age") or "—"))} | <span class="label">Sex:</span> {esc(str(p.get("sex") or "—"))} | <span class="label">Weight:</span> {esc(str(p.get("weight_kg") or "?"))}kg | <span class="label">Blood:</span> {esc(str(p.get("blood_type") or "—"))}</div>
<div class="field"><span class="label">Allergies:</span> {esc(", ".join(str(a) for a in allergies)) if allergies else "NKDA"}</div>
<div class="field"><span class="label">Conditions:</span> {esc(", ".join(str(c) for c in conditions)) if conditions else "None"}</div>
<div class="field"><span class="label">Medications:</span> {esc(", ".join(str(m) for m in medications)) if medications else "None"}</div>
<div class="field"><span class="label">Notes:</span> {esc(str(p.get("notes") or "—"))}</div>
</div>'''
        else:
            html += '<p style="color:#999;">No patients registered.</p>'

        # 4. INVENTORY SUMMARY
        html += '''</div>
<div class="section page-break">
<h2>4. INVENTORY SUMMARY</h2>'''
        if inventory:
            # Group by category
            categories = {}
            for item in inventory:
                cat = item.get('category', 'other') or 'other'
                categories.setdefault(cat, []).append(item)
            for cat in sorted(categories.keys()):
                items = categories[cat]
                html += f'<h3>{esc(cat.upper())} ({len(items)} items)</h3>'
                html += '<table><tr><th>Item</th><th>Qty</th><th>Unit</th><th>Location</th><th>Expiration</th></tr>'
                for item in items:
                    exp = item.get('expiration', '') or ''
                    exp_class = ''
                    if exp:
                        try:
                            if datetime.strptime(exp, '%Y-%m-%d') < datetime.now():
                                exp_class = ' class="status-bad"'
                        except ValueError:
                            pass
                    html += (f'<tr><td>{esc(item["name"])}</td><td>{esc(str(item["quantity"]))}</td>'
                             f'<td>{esc(item.get("unit","") or "")}</td>'
                             f'<td>{esc(item.get("location","") or "")}</td>'
                             f'<td{exp_class}>{esc(exp) if exp else "—"}</td></tr>')
                html += '</table>'
        else:
            html += '<p style="color:#999;">No inventory items.</p>'

        # 5. ACTIVE CHECKLISTS
        html += '''</div>
<div class="section page-break">
<h2>5. ACTIVE CHECKLISTS</h2>'''
        if checklists:
            for cl in checklists:
                html += f'<h3>{esc(cl["name"])}</h3>'
                try:
                    items = json.loads(cl.get('items') or '[]')
                except (json.JSONDecodeError, TypeError):
                    items = []
                if items:
                    html += '<table><tr><th style="width:30px;">Done</th><th>Task</th></tr>'
                    for item in items:
                        if isinstance(item, dict):
                            text = item.get('text', item.get('name', str(item)))
                            done = item.get('done', item.get('checked', False))
                        else:
                            text = str(item)
                            done = False
                        check = '&#9745;' if done else '&#9744;'
                        html += f'<tr><td style="text-align:center;">{check}</td><td>{esc(str(text))}</td></tr>'
                    html += '</table>'
                else:
                    html += '<p style="color:#999;">No items.</p>'
        else:
            html += '<p style="color:#999;">No checklists.</p>'

        # 6. WAYPOINTS
        html += '''</div>
<div class="section page-break">
<h2>6. WAYPOINTS &amp; RALLY POINTS</h2>'''
        if waypoints:
            html += '<table><tr><th>Name</th><th>Latitude</th><th>Longitude</th><th>Category</th><th>Notes</th></tr>'
            for wp in waypoints:
                html += (f'<tr><td>{esc(wp["name"])}</td><td>{wp["lat"]:.6f}</td><td>{wp["lng"]:.6f}</td>'
                         f'<td>{esc(wp.get("category","") or "")}</td>'
                         f'<td>{esc(wp.get("notes","") or "")}</td></tr>')
            html += '</table>'
            # Rally point map placeholder
            rally = [w for w in waypoints if (w.get('category', '') or '').lower() in ('rally', 'rally point', 'rallypoint')]
            if rally:
                html += '<div class="map-placeholder">Rally Point Map — Print map from the Maps tab for full detail</div>'
        else:
            html += '<p style="color:#999;">No waypoints registered.</p>'

        # 7. EMERGENCY PROCEDURES
        html += '''</div>
<div class="section page-break">
<h2>7. EMERGENCY PROCEDURES</h2>'''
        if procedures:
            for proc in procedures:
                html += f'<div class="card"><h3>{esc(proc["title"])}</h3>'
                content = proc.get('content', '') or ''
                html += f'<div style="white-space:pre-wrap;font-size:9px;">{esc(content)}</div></div>'
        else:
            html += '<p style="color:#999;">No emergency procedures documented. Create notes with "emergency" or "procedure" in the title.</p>'

        # 8. FAMILY EMERGENCY PLAN
        html += '''</div>
<div class="section page-break">
<h2>8. FAMILY EMERGENCY PLAN</h2>'''
        if family_plan:
            html += f'<div style="white-space:pre-wrap;">{esc(family_plan)}</div>'
        else:
            html += '<p style="color:#999;">No family emergency plan configured. Save one in Settings.</p>'

        html += f'''</div>

<div style="text-align:center; margin-top:20px; font-size:8px; color:#999; page-break-before:always; padding-top:40px;">
<p>End of Operations Binder &mdash; {esc(node_name)}</p>
<p>Generated {esc(now)} by N.O.M.A.D. Survival Command Center</p>
<p>CONFIDENTIAL &mdash; Protect accordingly</p>
</div>

</body>
</html>'''

        return Response(html, mimetype='text/html')

    # ─── Lamination / Wallet Cards ───────────────────────────────────

    @app.route('/api/print/wallet-cards')
    def api_print_wallet_cards():
        """Generate credit-card-sized reference cards for printing and laminating."""
        db = get_db()
        try:
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

        finally:
            db.close()

        now = datetime.now().strftime('%Y-%m-%d')
        patient_name = ''
        if self_patient:
            patient_name = self_patient['name']
        elif self_contact:
            patient_name = self_contact['name']

        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Wallet Reference Cards</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Courier New', Courier, monospace; color: #000; padding: 10px; }}
.card-grid {{ display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }}
.card {{
    width: 3.375in; height: 2.125in;
    border: 2px solid #000; border-radius: 6px;
    padding: 6px 8px; font-size: 7.5px; line-height: 1.3;
    overflow: hidden; page-break-inside: avoid;
    position: relative;
}}
.card h3 {{ font-size: 9px; margin: 0 0 3px; border-bottom: 1.5px solid #000; padding-bottom: 2px; text-transform: uppercase; }}
.card .field {{ margin-bottom: 1px; }}
.card .label {{ font-weight: 700; }}
.card .footer {{ position: absolute; bottom: 3px; left: 8px; right: 8px; font-size: 6px; color: #888; text-align: center; }}
.card-ice {{ border-color: #c00; }}
.card-ice h3 {{ color: #c00; border-color: #c00; }}
.card-blood {{ border-color: #900; }}
.card-blood h3 {{ color: #900; border-color: #900; }}
.card-meds {{ border-color: #069; }}
.card-meds h3 {{ color: #069; border-color: #069; }}
.card-rally {{ border-color: #060; }}
.card-rally h3 {{ color: #060; border-color: #060; }}
.card-freq {{ border-color: #339; }}
.card-freq h3 {{ color: #339; border-color: #339; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ border: 1px solid #ccc; padding: 1px 3px; font-size: 7px; }}
th {{ background: #eee; font-weight: 700; }}
@media print {{
    body {{ margin: 0; padding: 5mm; }}
    @page {{ size: letter; margin: 10mm; }}
}}
</style>
</head>
<body>
<div class="card-grid">

<!-- ICE CARD -->
<div class="card card-ice">
<h3>ICE — In Case of Emergency</h3>
<div class="field"><span class="label">Name:</span> {esc(patient_name or "_______________")}</div>
<div class="field"><span class="label">Blood Type:</span> {esc(blood_type or "______")} | <span class="label">Allergies:</span> {esc(", ".join(str(a) for a in allergies) if allergies else "NKDA")}</div>
<div style="margin-top:3px;"><span class="label">Emergency Contacts:</span></div>'''

        for i, c in enumerate(ice_contacts):
            html += f'<div class="field">{i+1}. {esc(c["name"])} ({esc(c.get("role","") or "")}) — {esc(c["phone"])}</div>'
        for i in range(len(ice_contacts), 3):
            html += f'<div class="field">{i+1}. ________________________________</div>'

        html += f'''<div class="footer">Generated {esc(now)} &mdash; N.O.M.A.D.</div>
</div>

<!-- BLOOD TYPE CARD -->
<div class="card card-blood">
<h3>Blood Type Card</h3>
<div style="text-align:center; margin-top:8px;">
<div style="font-size:28px; font-weight:700; border:3px solid #900; display:inline-block; padding:6px 16px; border-radius:4px;">{esc(blood_type or "?")}</div>
</div>
<div style="text-align:center; margin-top:6px; font-size:9px;"><span class="label">{esc(patient_name or "Name: _______________")}</span></div>
<div style="text-align:center; margin-top:3px;">Allergies: {esc(", ".join(str(a) for a in allergies) if allergies else "NKDA")}</div>
<div class="footer">Generated {esc(now)} &mdash; N.O.M.A.D.</div>
</div>

<!-- MEDICATION LIST CARD -->
<div class="card card-meds">
<h3>Medication List</h3>
<div class="field"><span class="label">Patient:</span> {esc(patient_name or "_______________")}</div>'''

        if medications:
            for med in medications[:8]:
                html += f'<div class="field">&#8226; {esc(str(med))}</div>'
        else:
            html += '<div class="field" style="color:#999;">No medications recorded.</div>'

        html += f'''<div class="footer">Generated {esc(now)} &mdash; N.O.M.A.D.</div>
</div>

<!-- RALLY POINT CARD -->
<div class="card card-rally">
<h3>Rally Points</h3>'''

        if rally_points:
            html += '<table><tr><th>Point</th><th>Lat</th><th>Lng</th></tr>'
            for rp in rally_points:
                html += f'<tr><td>{esc(rp["name"])}</td><td>{rp["lat"]:.5f}</td><td>{rp["lng"]:.5f}</td></tr>'
            html += '</table>'
        else:
            html += '''<div class="field">Primary: ________________________________</div>
<div class="field">Alternate: ________________________________</div>
<div class="field">Contingency: ________________________________</div>'''

        html += f'''<div class="footer">Generated {esc(now)} &mdash; N.O.M.A.D.</div>
</div>

<!-- FREQUENCY QUICK-REF CARD -->
<div class="card card-freq">
<h3>Frequency Quick Reference</h3>'''

        if custom_freqs:
            html += '<table><tr><th>Service</th><th>Freq</th><th>Mode</th></tr>'
            for f in custom_freqs:
                html += f'<tr><td>{esc(f["service"])}</td><td>{esc(str(f["frequency"]))}</td><td>{esc(f.get("mode","") or "")}</td></tr>'
            html += '</table>'
        else:
            html += '''<table><tr><th>Service</th><th>Freq</th></tr>
<tr><td>FRS Ch 1</td><td>462.5625</td></tr>
<tr><td>MURS Ch 1</td><td>151.820</td></tr>
<tr><td>2m Call</td><td>146.520</td></tr>
<tr><td>CB Ch 9</td><td>27.065</td></tr>
<tr><td>NOAA WX</td><td>162.550</td></tr>
</table>'''

        html += f'''<div class="footer">Generated {esc(now)} &mdash; N.O.M.A.D.</div>
</div>

</div><!-- end card-grid -->
</body>
</html>'''

        return Response(html, mimetype='text/html')

    # ─── SOI Generator ───────────────────────────────────────────────

    @app.route('/api/print/soi')
    def api_print_soi():
        """Generate a Signal Operating Instructions document."""
        db = get_db()
        try:
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

        finally:
            db.close()

        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        date_str = datetime.now().strftime('%d %B %Y')

        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>SOI — {esc(node_name)}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Courier New', Courier, monospace; font-size: 10px; color: #000; line-height: 1.4; padding: 15px; }}
.header {{ text-align: center; border: 3px solid #000; padding: 12px; margin-bottom: 15px; }}
.header h1 {{ font-size: 18px; letter-spacing: 2px; }}
.header .classification {{ font-size: 12px; color: #c00; font-weight: 700; margin-top: 4px; letter-spacing: 3px; }}
.header .meta {{ font-size: 9px; margin-top: 6px; color: #555; }}
h2 {{ font-size: 12px; background: #000; color: #fff; padding: 3px 8px; margin: 12px 0 6px; letter-spacing: 1px; }}
h3 {{ font-size: 10px; margin: 8px 0 4px; border-bottom: 1px solid #000; }}
table {{ width: 100%; border-collapse: collapse; margin-bottom: 10px; }}
th, td {{ border: 1px solid #666; padding: 2px 5px; font-size: 9px; }}
th {{ background: #ddd; font-weight: 700; text-transform: uppercase; }}
.time-slot {{ display: inline-block; border: 1px solid #000; padding: 1px 4px; margin: 1px; font-size: 8px; }}
.destruction {{ border: 2px solid #c00; padding: 8px; margin-top: 15px; text-align: center; color: #c00; font-weight: 700; }}
@media print {{
    body {{ margin: 0; padding: 10mm; }}
    @page {{ size: letter; margin: 12mm; }}
}}
</style>
</head>
<body>

<div class="header">
<div class="classification">RESTRICTED</div>
<h1>SIGNAL OPERATING INSTRUCTIONS</h1>
<div class="meta">
Node: {esc(node_name)} ({esc(node_id)}) | Effective: {esc(date_str)} | Generated: {esc(now)}
</div>
<div class="classification">RESTRICTED</div>
</div>

<h2>SECTION 1 — FREQUENCY ASSIGNMENTS</h2>'''

        if freqs:
            html += '''<table>
<tr><th>Freq (MHz)</th><th>Mode</th><th>BW</th><th>Service/Net</th><th>Description</th><th>Notes</th></tr>'''
            for f in freqs:
                html += (f'<tr><td>{esc(str(f["frequency"]))}</td><td>{esc(f.get("mode","") or "")}</td>'
                         f'<td>{esc(f.get("bandwidth","") or "")}</td><td>{esc(f["service"])}</td>'
                         f'<td>{esc(f.get("description","") or "")}</td>'
                         f'<td>{esc(f.get("notes","") or "")}</td></tr>')
            html += '</table>'
        else:
            html += '''<p style="color:#666;">No frequencies in database. Add them in the Comms &gt; Frequencies tab.</p>
<table><tr><th>Freq</th><th>Mode</th><th>Service</th></tr>
<tr><td>462.5625</td><td>FM</td><td>FRS Ch 1 (Primary)</td></tr>
<tr><td>146.520</td><td>FM</td><td>2m National Calling</td></tr>
<tr><td>446.000</td><td>FM</td><td>70cm National Calling</td></tr>
<tr><td>27.065</td><td>AM</td><td>CB Ch 9 (Emergency)</td></tr>
</table>'''

        html += '<h2>SECTION 2 — CALL SIGN MATRIX</h2>'

        if contacts:
            html += '''<table>
<tr><th>Callsign</th><th>Operator</th><th>Role</th><th>Primary Freq</th></tr>'''
            for c in contacts:
                html += (f'<tr><td><strong>{esc(c.get("callsign","") or "—")}</strong></td>'
                         f'<td>{esc(c["name"])}</td><td>{esc(c.get("role","") or "")}</td>'
                         f'<td>{esc(c.get("freq","") or "—")}</td></tr>')
            html += '</table>'
        else:
            html += '<p style="color:#666;">No contacts with callsigns registered.</p>'

        html += '<h2>SECTION 3 — RADIO PROFILES / CHANNEL PLANS</h2>'

        if profiles:
            for prof in profiles:
                html += f'<h3>{esc(prof["name"])}' + (f' ({esc(prof["radio_model"])})' if prof.get('radio_model') else '') + '</h3>'
                try:
                    channels = json.loads(prof.get('channels') or '[]')
                except (json.JSONDecodeError, TypeError):
                    channels = []
                if channels:
                    html += '<table><tr><th>Ch</th><th>Freq</th><th>Name/Service</th></tr>'
                    for i, ch in enumerate(channels):
                        if isinstance(ch, dict):
                            html += (f'<tr><td>{i+1}</td>'
                                     f'<td>{esc(str(ch.get("frequency", ch.get("freq",""))))}</td>'
                                     f'<td>{esc(str(ch.get("name", ch.get("service",""))))}</td></tr>')
                        else:
                            html += f'<tr><td>{i+1}</td><td colspan="2">{esc(str(ch))}</td></tr>'
                    html += '</table>'
                else:
                    html += '<p style="color:#999;">No channels programmed.</p>'
        else:
            html += '<p style="color:#666;">No radio profiles configured.</p>'

        html += '''<h2>SECTION 4 — NET SCHEDULE / TIME SLOTS</h2>
<table>
<tr><th>Time (Local)</th><th>Net</th><th>Purpose</th></tr>
<tr><td>0600</td><td>Morning Check-in</td><td>Accountability &amp; weather</td></tr>
<tr><td>1200</td><td>Midday SITREP</td><td>Status updates</td></tr>
<tr><td>1800</td><td>Evening Net</td><td>Planning &amp; coordination</td></tr>
<tr><td>2100</td><td>Night Watch</td><td>Security check-in</td></tr>
</table>
<p style="font-size:8px;color:#666;margin-top:4px;">Modify schedule as needed. All times local. Monitor primary freq continuously.</p>

<h2>SECTION 5 — AUTHENTICATION &amp; PROCEDURES</h2>
<table>
<tr><th>Procedure</th><th>Protocol</th></tr>
<tr><td>Station Identification</td><td>Callsign at start and end of each transmission</td></tr>
<tr><td>Emergency Traffic</td><td>"BREAK BREAK BREAK" — all stations stand by</td></tr>
<tr><td>Priority Traffic</td><td>"PRIORITY" prefix — routine traffic yields</td></tr>
<tr><td>Radio Check</td><td>"[Callsign], radio check, over" — respond with signal quality</td></tr>
<tr><td>Relay Request</td><td>"RELAY TO [callsign]" via nearest station</td></tr>
</table>'''

        html += f'''
<div class="destruction">
DESTROY THIS DOCUMENT WHEN COMPROMISED OR SUPERSEDED<br>
Do not transmit contents over unsecured channels
</div>

<div style="text-align:center; margin-top:12px; font-size:8px; color:#999;">
SOI Generated {esc(now)} by N.O.M.A.D. &mdash; {esc(node_name)} ({esc(node_id)})
</div>

</body>
</html>'''

        return Response(html, mimetype='text/html')

    # ═════════════════════════════════════════════════════════════════
    # PHASE 19 — Database Integrity, Self-Test, Undo
    # ═════════════════════════════════════════════════════════════════

    # ─── Database Integrity Check ────────────────────────────────────

    @app.route('/api/system/db-check', methods=['POST'])
    def api_system_db_check():
        """Run PRAGMA integrity_check and foreign_key_check."""
        db = get_db()
        try:
            integrity = db.execute('PRAGMA integrity_check').fetchall()
            fk_check = db.execute('PRAGMA foreign_key_check').fetchall()
        finally:
            db.close()

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
        db = get_db()
        try:
            db.execute('VACUUM')
            db.execute('REINDEX')
        finally:
            db.close()
        log_activity('db_vacuum', 'system', 'Database vacuumed and reindexed')
        return jsonify({'status': 'ok', 'message': 'VACUUM and REINDEX completed'})

    # ─── Startup Self-Test ───────────────────────────────────────────

    @app.route('/api/system/self-test')
    def api_system_self_test():
        """Run comprehensive self-test and return pass/fail per check."""
        results = []

        # 1. Database accessible
        try:
            db = get_db()
            db.execute('SELECT 1').fetchone()
            db.close()
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
            db = get_db()
            existing = [r[0] for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            db.close()
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
        if not _undo_stack:
            return jsonify({'error': 'Nothing to undo (expired or empty)'}), 404

        entry = _undo_stack.pop()
        table = entry['table']
        row_data = entry['row_data']

        if table not in _UNDO_VALID_TABLES:
            return jsonify({'error': f'Undo refused: invalid table "{table}"'}), 400

        db = get_db()
        try:
            if entry['action_type'] == 'delete':
                # Re-insert the deleted row
                cols = list(row_data.keys())
                placeholders = ', '.join(['?'] * len(cols))
                col_names = ', '.join(cols)
                db.execute(
                    f'INSERT INTO {table} ({col_names}) VALUES ({placeholders})',
                    [row_data[c] for c in cols])
                db.commit()
            elif entry['action_type'] == 'update':
                # Restore previous values
                row_id = row_data.get('id')
                if row_id is not None:
                    sets = ', '.join(f'{k} = ?' for k in row_data if k != 'id')
                    vals = [row_data[k] for k in row_data if k != 'id']
                    vals.append(row_id)
                    db.execute(f'UPDATE {table} SET {sets} WHERE id = ?', vals)
                    db.commit()
            log_activity('undo', 'system', entry['description'])
        except Exception as e:
            return jsonify({'error': f'Undo failed: {str(e)}'}), 500
        finally:
            db.close()

        return jsonify({
            'status': 'undone',
            'description': entry['description'],
        })

    # ═════════════════════════════════════════════════════════════════
    # PHASE 20 — Federation: Community Readiness, Skills, Alert Relay
    # ═════════════════════════════════════════════════════════════════

    # ─── Community Readiness Dashboard ───────────────────────────────

    @app.route('/api/federation/community-readiness')
    def api_federation_community_readiness():
        """Aggregate readiness scores across all federated nodes."""
        db = get_db()
        try:
            rows = db.execute(
                'SELECT node_id, node_name, situation, updated_at FROM federation_sitboard '
                'ORDER BY updated_at DESC').fetchall()
        finally:
            db.close()

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
        db = get_db()
        try:
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

        finally:
            db.close()

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

        db = get_db()
        try:
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
        finally:
            db.close()

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
