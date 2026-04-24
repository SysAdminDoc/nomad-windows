"""Cross-module aggregation routes.

These seven endpoints answer questions that span the inventory, contacts,
books, patients, medical, comms, power, garden, and documents tables.
They were originally inline inside ``create_app()`` — extracted here so
the app factory stays a thin orchestrator and the aggregation surface has
a single audit point.

Routes:
    GET  /api/needs                 — per-category survival-need overview
    GET  /api/needs/<need_id>       — drill-down for one survival need
    GET  /api/guides/context        — live inventory + contacts payload for decision trees
    POST /api/planner/calculate     — people × days × activity → resource estimate
    GET  /api/readiness-score       — composite 0-100 readiness score with letter grade
    GET  /api/data-summary          — table-count roll-up for the settings dashboard
    GET  /api/search/all            — FTS5-accelerated unified search

Cache helpers come from ``web.state`` (shared with the rest of the app).
"""

from datetime import datetime

from flask import jsonify, request

from db import db_session
from web.sql_safety import safe_table
from web.state import cached_get, cached_set
from web.utils import (
    require_json_body as _require_json_body,
    safe_json_list as _safe_json_list,
)


SURVIVAL_NEEDS = {
    'water': {
        'label': 'Water & Hydration', 'icon': '\U0001F4A7', 'color': '#0288d1',
        'keywords': ['water','hydration','purif','filter','well','rain','cistern','dehydrat','boil','bleach','iodine','sodis','biosand'],
        'guides': ['water_purify','water_source_assessment'],
        'calcs': ['water-needs','water-storage','bleach-dosage'],
    },
    'food': {
        'label': 'Food & Nutrition', 'icon': '\U0001F372', 'color': '#558b2f',
        'keywords': ['food','calori','nutrition','canning','preserv','dehydrat','jerky','fermenting','seed','garden','harvest','livestock','chicken','goat','rabbit','grain','flour','rice','bean','MRE','freeze dry','smoking meat','salt cur'],
        'guides': ['food_preserve','food_safety_assessment'],
        'calcs': ['calorie-needs','food-storage','canning','composting','pasture'],
    },
    'medical': {
        'label': 'Medical & Health', 'icon': '\U0001FA79', 'color': '#c62828',
        'keywords': ['medical','first aid','wound','bleed','tourniquet','suture','fracture','burn','infection','antibiotic','medicine','triage','TCCC','CPR','AED','dental','eye','childbirth','diabetic','allergic','anaphyla','splint','vital','patient'],
        'guides': ['wound_assess','triage_start','antibiotic_selection','chest_trauma','envenomation','wound_infection','anaphylaxis','hypothermia_response'],
        'calcs': ['drug-dosage','burn-area','blood-loss','dehydration'],
    },
    'shelter': {
        'label': 'Shelter & Construction', 'icon': '\U0001F3E0', 'color': '#795548',
        'keywords': ['shelter','cabin','build','construct','adobe','timber','stone','masonry','insulation','roof','foundation','tent','tarp','debris hut','earthbag','cob','log'],
        'guides': ['shelter_build'],
        'calcs': ['shelter-sizing','insulation','concrete-mix'],
    },
    'security': {
        'label': 'Security & Defense', 'icon': '\U0001F6E1', 'color': '#d32f2f',
        'keywords': ['security','defense','perimeter','alarm','camera','night vision','firearm','ammo','ammunition','caliber','tactical','gray man','OPSEC','trip wire','home harden'],
        'guides': ['bugout_decision'],
        'calcs': ['ballistic','range','ammo-load'],
    },
    'comms': {
        'label': 'Communications', 'icon': '\U0001F4E1', 'color': '#6a1b9a',
        'keywords': ['radio','ham','amateur','frequency','antenna','HF','VHF','UHF','GMRS','FRS','MURS','Meshtastic','JS8Call','Winlink','APRS','morse','CW','SDR','repeater','net','callsign','comms','communication'],
        'guides': ['radio_setup'],
        'calcs': ['antenna-length','radio-range','power-budget'],
    },
    'power': {
        'label': 'Energy & Power', 'icon': '\u26A1', 'color': '#f9a825',
        'keywords': ['power','solar','battery','generator','inverter','watt','amp','volt','charge','fuel','diesel','propane','gasoline','wood gas','wind','hydro','off-grid','grid-down'],
        'guides': ['power_outage'],
        'calcs': ['solar-sizing','battery-bank','generator-fuel','wire-gauge'],
    },
    'navigation': {
        'label': 'Navigation & Maps', 'icon': '\U0001F310', 'color': '#0277bd',
        'keywords': ['map','compass','GPS','navigation','topographic','waypoint','route','bearing','MGRS','grid','coordinate','terrain','elevation','celestial','star','landmark'],
        'guides': [],
        'calcs': ['bearing','distance','pace-count','grid-to-latlong'],
    },
    'knowledge': {
        'label': 'Knowledge & Training', 'icon': '\U0001F4DA', 'color': '#37474f',
        'keywords': ['book','manual','reference','training','guide','course','encyclopedia','textbook','library','skill','learn','practice','drill'],
        'guides': [],
        'calcs': [],
    },
}


def register_aggregation_routes(app):
    """Register the seven cross-module aggregation routes on ``app``."""

    @app.route('/api/needs')
    def api_needs_overview():
        """Returns all survival need categories with item counts from each module."""
        cached = cached_get('needs', 60)
        if cached:
            return jsonify(cached)
        with db_session() as db:
            result = {}
            for need_id, need in SURVIVAL_NEEDS.items():
                kw = need['keywords']
                # Count matching inventory items
                kw_inv = kw[:5]
                if kw_inv:
                    like_clauses = ' OR '.join(['name LIKE ? OR category LIKE ?' for _ in kw_inv])
                    like_vals = [v for k in kw_inv for v in (f'%{k}%', f'%{k}%')]
                    inv_count = db.execute(f'SELECT COUNT(*) as c FROM inventory WHERE {like_clauses}', like_vals).fetchone()['c']
                else:
                    inv_count = 0

                # Count matching contacts by skills/role
                kw_con = kw[:3]
                if kw_con:
                    like_clauses = ' OR '.join(['role LIKE ? OR skills LIKE ?' for _ in kw_con])
                    like_vals = [v for k in kw_con for v in (f'%{k}%', f'%{k}%')]
                    contact_count = db.execute(f'SELECT COUNT(*) as c FROM contacts WHERE {like_clauses}', like_vals).fetchone()['c']
                else:
                    contact_count = 0

                # Count matching books (from reference catalog)
                kw_book = kw[:3]
                if kw_book:
                    like_clauses = ' OR '.join(['title LIKE ? OR category LIKE ?' for _ in kw_book])
                    like_vals = [v for k in kw_book for v in (f'%{k}%', f'%{k}%')]
                    book_count = db.execute(f'SELECT COUNT(*) as c FROM books WHERE {like_clauses}', like_vals).fetchone()['c']
                else:
                    book_count = 0

                # Decision guides count
                guide_count = len(need.get('guides', []))

                result[need_id] = {
                    'label': need['label'], 'icon': need['icon'], 'color': need['color'],
                    'inventory': min(inv_count, 999), 'contacts': min(contact_count, 99),
                    'books': min(book_count, 99), 'guides': guide_count,
                    'total': min(inv_count + contact_count + book_count + guide_count, 9999),
                }
            cached_set('needs', result)
            return jsonify(result)

    @app.route('/api/needs/<need_id>')
    def api_need_detail(need_id):
        """Returns detailed cross-module data for a specific survival need."""
        need = SURVIVAL_NEEDS.get(need_id)
        if not need:
            return jsonify({'error': 'Unknown need category'}), 404
        with db_session() as db:
            kw = need['keywords']
            like_clauses = ' OR '.join(['name LIKE ?' for _ in kw[:5]])
            like_vals = [f'%{k}%' for k in kw[:5]]

            # Inventory items
            kw_inv = kw[:5]
            if kw_inv:
                like_clauses = ' OR '.join(['name LIKE ? OR category LIKE ?' for _ in kw_inv])
                like_vals = [v for k in kw_inv for v in (f'%{k}%', f'%{k}%')]
                rows = db.execute(f'SELECT id, name, quantity, unit, category FROM inventory WHERE {like_clauses} LIMIT 100', like_vals).fetchall()
                seen_ids = set()
                inv_items = []
                for r in rows:
                    if r['id'] not in seen_ids:
                        seen_ids.add(r['id'])
                        inv_items.append(dict(r))
            else:
                inv_items = []

            # Contacts
            kw_con = kw[:3]
            if kw_con:
                like_clauses = ' OR '.join(['role LIKE ? OR skills LIKE ?' for _ in kw_con])
                like_vals = [v for k in kw_con for v in (f'%{k}%', f'%{k}%')]
                rows = db.execute(f'SELECT id, name, role, skills FROM contacts WHERE {like_clauses} LIMIT 30', like_vals).fetchall()
                seen_ids = set()
                contacts = []
                for r in rows:
                    if r['id'] not in seen_ids:
                        seen_ids.add(r['id'])
                        contacts.append(dict(r))
            else:
                contacts = []

            # Books
            kw_book = kw[:3]
            if kw_book:
                like_clauses = ' OR '.join(['title LIKE ? OR category LIKE ?' for _ in kw_book])
                like_vals = [v for k in kw_book for v in (f'%{k}%', f'%{k}%')]
                rows = db.execute(f'SELECT id, title, author, category FROM books WHERE {like_clauses} LIMIT 30', like_vals).fetchall()
                seen_ids = set()
                books = []
                for r in rows:
                    if r['id'] not in seen_ids:
                        seen_ids.add(r['id'])
                        books.append(dict(r))
            else:
                books = []

            # Decision guides (from hardcoded list)
            guides = [{'id': gid, 'title': gid.replace('_', ' ').title()} for gid in need.get('guides', [])]

            return jsonify({
                'need': {'id': need_id, 'label': need['label'], 'icon': need['icon'], 'color': need['color']},
                'inventory': inv_items[:30],
                'contacts': contacts[:10],
                'books': books[:15],
                'guides': guides,
            })

    @app.route('/api/guides/context')
    def api_guides_context():
        """Return live inventory/contacts data for context-aware decision tree rendering."""
        with db_session() as db:
            # Relevant inventory items grouped by category
            items = db.execute("SELECT name, quantity, unit, category, expiration FROM inventory WHERE quantity > 0 ORDER BY category, name LIMIT 500").fetchall()
            inv_by_cat = {}
            for it in items:
                cat = it['category'] or 'other'
                if cat not in inv_by_cat:
                    inv_by_cat[cat] = []
                inv_by_cat[cat].append({'name': it['name'], 'qty': it['quantity'], 'unit': it['unit'] or 'ea', 'expiration': it['expiration'] or ''})

            # Key contacts by role
            contacts = db.execute("SELECT name, role, callsign, phone FROM contacts ORDER BY name LIMIT 200").fetchall()
            contacts_by_role = {}
            for c in contacts:
                role = (c['role'] or 'general').lower()
                if role not in contacts_by_role:
                    contacts_by_role[role] = []
                contacts_by_role[role].append({'name': c['name'], 'callsign': c['callsign'] or '', 'phone': c['phone'] or ''})

            # Key stats
            water_items = [i for i in items if i['category'] == 'water']
            medical_items = [i for i in items if i['category'] == 'medical']
            food_items = [i for i in items if i['category'] == 'food']

            return jsonify({
                'inventory': inv_by_cat,
                'contacts': contacts_by_role,
                'summary': {
                    'water_items': len(water_items),
                    'medical_items': len(medical_items),
                    'food_items': len(food_items),
                    'total_contacts': len(contacts),
                    'medic': next((c['name'] for c in contacts if 'medic' in (c['role'] or '').lower() or 'doctor' in (c['role'] or '').lower() or 'nurse' in (c['role'] or '').lower()), None),
                    'comms_officer': next((c['name'] for c in contacts if 'comms' in (c['role'] or '').lower() or 'radio' in (c['role'] or '').lower()), None),
                },
            })

    @app.route('/api/planner/calculate', methods=['POST'])
    def api_planner_calculate():
        """Calculate resource needs for X people over Y days."""
        data, error = _require_json_body(request)
        if error:
            return error
        try:
            people = max(1, int(data.get('people', 4)))
            days = max(1, int(data.get('days', 14)))
        except (ValueError, TypeError):
            return jsonify({'error': 'people and days must be integers'}), 400
        activity = data.get('activity', 'moderate')  # sedentary, moderate, heavy

        cal_mult = {'sedentary': 1800, 'moderate': 2200, 'heavy': 3000}.get(activity, 2200)
        water_mult = {'sedentary': 0.75, 'moderate': 1.0, 'heavy': 1.5}.get(activity, 1.0)

        needs = {
            'water_gal': round(people * days * water_mult, 1),
            'food_cal': people * days * cal_mult,
            'food_lbs_rice': round(people * days * cal_mult / 1800 * 0.45, 1),  # ~0.45 lb rice/1800cal
            'food_cans': people * days * 2,  # ~2 cans per person per day
            'tp_rolls': max(1, round(people * days / 5)),  # ~1 roll per 5 person-days
            'bleach_oz': round(people * days * 0.1, 1),  # ~0.1 oz per person-day for water treatment
            'batteries_aa': people * 2 + days,  # rough estimate
            'trash_bags': max(1, round(people * days / 3)),
            'first_aid_kits': max(1, round(people / 4)),
        }

        # Compare with current inventory
        with db_session() as db:
            inv = {}
            rows = db.execute('SELECT category, SUM(quantity) as qty FROM inventory GROUP BY category').fetchall()
            for r in rows:
                inv[r['category']] = r['qty'] or 0

        return jsonify({
            'people': people, 'days': days, 'activity': activity,
            'needs': needs, 'current_inventory': inv,
        })

    @app.route('/api/readiness-score')
    def api_readiness_score():
        """Cross-module readiness assessment (0-100) with category breakdown."""
        cached = cached_get('readiness', 60)
        if cached:
            return jsonify(cached)
        with db_session() as db:
            scores = {}

            # 1. Water (20 pts) — based on water-category inventory vs people
            water_items = db.execute("SELECT SUM(quantity) as qty FROM inventory WHERE LOWER(category) IN ('water', 'hydration')").fetchone()
            water_qty = water_items['qty'] or 0
            contacts_count = max(db.execute('SELECT COUNT(*) as c FROM contacts').fetchone()['c'], 1)
            water_days = water_qty / max(contacts_count, 1)  # rough gal/person
            scores['water'] = {'score': min(round(water_days / 14 * 20), 20), 'detail': f'{round(water_days, 1)} gal/person'}

            # 2. Food (20 pts) — based on food-category inventory with usage tracking
            food_items = db.execute("SELECT COUNT(*) as c FROM inventory WHERE LOWER(category) IN ('food', 'food storage', 'canned goods')").fetchone()
            food_count = food_items['c'] or 0
            food_with_usage = db.execute("SELECT COUNT(*) as c FROM inventory WHERE LOWER(category) IN ('food', 'food storage', 'canned goods') AND daily_usage > 0").fetchone()['c']
            today = datetime.now().strftime('%Y-%m-%d')
            food_expired = db.execute("SELECT COUNT(*) as c FROM inventory WHERE LOWER(category) IN ('food', 'food storage', 'canned goods') AND expiration != '' AND expiration < ?", (today,)).fetchone()['c']
            food_score = min(food_count * 2, 14) + (3 if food_with_usage > 0 else 0) + (3 if food_expired == 0 else 0)
            scores['food'] = {'score': min(food_score, 20), 'detail': f'{food_count} items, {food_expired} expired'}

            # 3. Medical (15 pts) — patients, meds inventory, contacts with blood types
            med_items = db.execute("SELECT COUNT(*) as c FROM inventory WHERE LOWER(category) IN ('medical', 'first aid', 'medicine')").fetchone()['c']
            patients = db.execute('SELECT COUNT(*) as c FROM patients').fetchone()['c']
            blood_typed = db.execute("SELECT COUNT(*) as c FROM contacts WHERE blood_type != ''").fetchone()['c']
            med_score = min(med_items, 8) + (4 if patients > 0 else 0) + min(blood_typed, 3)
            scores['medical'] = {'score': min(med_score, 15), 'detail': f'{med_items} supplies, {patients} patients'}

            # 4. Security (10 pts) — cameras, access logging, incidents, ammo reserve
            cameras = db.execute('SELECT COUNT(*) as c FROM cameras').fetchone()['c']
            access_entries = db.execute("SELECT COUNT(*) as c FROM access_log WHERE created_at >= datetime('now', '-7 days')").fetchone()['c']
            recent_incidents = db.execute("SELECT COUNT(*) as c FROM incidents WHERE created_at >= datetime('now', '-7 days')").fetchone()['c']
            ammo_total = db.execute('SELECT COALESCE(SUM(quantity),0) as q FROM ammo_inventory').fetchone()['q']
            ammo_pts = min(2 if ammo_total >= 500 else (1 if ammo_total > 0 else 0), 2)
            sec_score = min(cameras * 2, 3) + (2 if access_entries > 0 else 0) + (3 if recent_incidents == 0 else 1) + ammo_pts
            scores['security'] = {'score': min(sec_score, 10), 'detail': f'{cameras} cameras, {int(ammo_total)} rounds'}

            # 5. Communications (10 pts) — contacts, comms log, radio ref usage
            contact_count = db.execute('SELECT COUNT(*) as c FROM contacts').fetchone()['c']
            comms_entries = db.execute('SELECT COUNT(*) as c FROM comms_log').fetchone()['c']
            comm_score = min(contact_count, 5) + (3 if comms_entries > 0 else 0) + (2 if contact_count >= 5 else 0)
            scores['comms'] = {'score': min(comm_score, 10), 'detail': f'{contact_count} contacts, {comms_entries} radio logs'}

            # 6. Shelter & Power (10 pts) — power devices, garden, waypoints, fuel reserve
            power_devices = db.execute('SELECT COUNT(*) as c FROM power_devices').fetchone()['c']
            garden_plots = db.execute('SELECT COUNT(*) as c FROM garden_plots').fetchone()['c']
            waypoints = db.execute('SELECT COUNT(*) as c FROM waypoints').fetchone()['c']
            fuel_total = db.execute('SELECT COALESCE(SUM(quantity),0) as q FROM fuel_storage').fetchone()['q']
            fuel_pts = min(2 if fuel_total >= 20 else (1 if fuel_total > 0 else 0), 2)
            shelter_score = min(power_devices * 2, 3) + min(garden_plots * 2, 3) + min(waypoints, 2) + fuel_pts
            scores['shelter'] = {'score': min(shelter_score, 10), 'detail': f'{power_devices} power devices, {round(fuel_total,1)} gal fuel'}

            # 7. Planning & Knowledge (15 pts) — checklists, notes, documents, drills, skills proficiency
            checklists = db.execute('SELECT items FROM checklists').fetchall()
            cl_total = 0
            cl_checked = 0
            for cl in checklists:
                items = _safe_json_list(cl['items'], [])
                cl_total += len(items)
                cl_checked += sum(1 for i in items if i.get('checked'))
            cl_pct = (cl_checked / cl_total * 100) if cl_total > 0 else 0
            notes_count = db.execute('SELECT COUNT(*) as c FROM notes').fetchone()['c']
            docs_count = db.execute("SELECT COUNT(*) as c FROM documents WHERE status = 'ready'").fetchone()['c']
            drills = db.execute('SELECT COUNT(*) as c FROM drill_history').fetchone()['c']
            skilled = db.execute("SELECT COUNT(*) as c FROM skills WHERE proficiency IN ('intermediate','expert')").fetchone()['c']
            skill_pts = min(skilled // 5, 3)  # 1 pt per 5 skilled areas, max 3
            community_count = db.execute("SELECT COUNT(*) as c FROM community_resources WHERE trust_level IN ('trusted','inner-circle')").fetchone()['c']
            plan_score = min(round(cl_pct / 10), 5) + min(notes_count, 2) + min(docs_count, 3) + min(drills, 2) + skill_pts + min(community_count, 1)
            scores['planning'] = {'score': min(plan_score, 15), 'detail': f'{round(cl_pct)}% checklists, {skilled} skilled areas, {drills} drills'}

        total = sum(s['score'] for s in scores.values())
        max_total = 100

        # Letter grade
        if total >= 90:
            grade = 'A'
        elif total >= 80:
            grade = 'B'
        elif total >= 65:
            grade = 'C'
        elif total >= 50:
            grade = 'D'
        else:
            grade = 'F'

        result = {
            'total': total, 'max': max_total, 'grade': grade,
            'categories': scores,
        }
        cached_set('readiness', result)
        return jsonify(result)

    @app.route('/api/data-summary')
    def api_data_summary():
        """Counts across all major tables for the settings data summary card."""
        with db_session() as db:
            tables = [
                ('inventory', 'Inventory Items'), ('contacts', 'Contacts'), ('notes', 'Notes'),
                ('conversations', 'AI Conversations'), ('checklists', 'Checklists'),
                ('incidents', 'Incidents'), ('patients', 'Patients'),
                ('waypoints', 'Waypoints'), ('documents', 'Documents'),
                ('garden_plots', 'Garden Plots'), ('seeds', 'Seeds'),
                ('harvest_log', 'Harvests'), ('livestock', 'Livestock'),
                ('power_devices', 'Power Devices'), ('cameras', 'Cameras'),
                ('comms_log', 'Radio Logs'), ('weather_log', 'Weather Entries'),
                ('journal', 'Journal Entries'), ('drill_history', 'Drills'),
                ('scenarios', 'Scenarios'), ('videos', 'Videos'),
                ('activity_log', 'Activity Events'), ('alerts', 'Alerts'),
                ('skills', 'Skills'), ('ammo_inventory', 'Ammo Inventory'),
                ('community_resources', 'Community Resources'), ('radiation_log', 'Radiation Entries'),
                ('fuel_storage', 'Fuel Storage'), ('equipment_log', 'Equipment'),
            ]
            _SUMMARY_TABLES = {t for t, _ in tables}
            result = []
            total = 0
            for tname, label in tables:
                try:
                    safe_table(tname, _SUMMARY_TABLES)
                    c = db.execute(f'SELECT COUNT(*) as c FROM {tname}').fetchone()['c']
                    if c > 0:
                        result.append({'table': tname, 'label': label, 'count': c})
                    total += c
                except Exception:
                    pass
        return jsonify({'tables': result, 'total_records': total})

    @app.route('/api/search/all')
    def api_search_all():
        """Extended search across all data types — single UNION ALL query.

        v7.29.0: uses FTS5 for notes/inventory/contacts/documents/waypoints
        when available (O(log n) vs LIKE's O(n) full scan). Remaining targets
        still use LIKE until their FTS5 indexes are added incrementally.
        """
        q = request.args.get('q', '').strip()[:200]
        if not q:
            return jsonify({'conversations': [], 'notes': [], 'documents': [], 'inventory': [], 'contacts': [], 'checklists': []})
        with db_session() as db:
            q_escaped = q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            like = f'%{q_escaped}%'
            esc = "ESCAPE '\\'"
            # FTS5 MATCH expression: strip special chars, double-quote the
            # query for phrase matching, and append * for prefix search.
            import re as _re
            _fts_clean = _re.sub(r'[*"():^{}~\[\]]', '', q).strip()
            fts_q = '"' + _fts_clean.replace('"', '') + '"' + '*' if _fts_clean else None
            use_fts = False
            if fts_q:
                try:
                    use_fts = db.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='notes_fts'"
                    ).fetchone() is not None
                except Exception:
                    use_fts = False
            # Single UNION ALL — 1 round-trip instead of 14
            if use_fts:
                _search_parts = [
                    (f"SELECT * FROM (SELECT id, title, 'conversation' as type FROM conversations WHERE title LIKE ? {esc} OR messages LIKE ? {esc} LIMIT 10)", (like, like)),
                    ("SELECT * FROM (SELECT n.id, n.title, 'note' as type FROM notes n JOIN notes_fts f ON f.rowid = n.id WHERE notes_fts MATCH ? LIMIT 10)", (fts_q,)),
                    ("SELECT * FROM (SELECT d.id, d.filename as title, 'document' as type FROM documents d JOIN documents_fts f ON f.rowid = d.id WHERE documents_fts MATCH ? AND d.status = 'ready' LIMIT 10)", (fts_q,)),
                    ("SELECT * FROM (SELECT i.id, i.name as title, 'inventory' as type FROM inventory i JOIN inventory_fts f ON f.rowid = i.id WHERE inventory_fts MATCH ? LIMIT 10)", (fts_q,)),
                    ("SELECT * FROM (SELECT c.id, c.name as title, 'contact' as type FROM contacts c JOIN contacts_fts f ON f.rowid = c.id WHERE contacts_fts MATCH ? LIMIT 10)", (fts_q,)),
                ]
            else:
                _search_parts = [
                    (f"SELECT * FROM (SELECT id, title, 'conversation' as type FROM conversations WHERE title LIKE ? {esc} OR messages LIKE ? {esc} LIMIT 10)", (like, like)),
                    (f"SELECT * FROM (SELECT id, title, 'note' as type FROM notes WHERE title LIKE ? {esc} OR content LIKE ? {esc} LIMIT 10)", (like, like)),
                    (f"SELECT * FROM (SELECT id, filename as title, 'document' as type FROM documents WHERE filename LIKE ? {esc} AND status = 'ready' LIMIT 10)", (like,)),
                    (f"SELECT * FROM (SELECT id, name as title, 'inventory' as type FROM inventory WHERE name LIKE ? {esc} OR location LIKE ? {esc} OR notes LIKE ? {esc} LIMIT 10)", (like, like, like)),
                    (f"SELECT * FROM (SELECT id, name as title, 'contact' as type FROM contacts WHERE name LIKE ? {esc} OR callsign LIKE ? {esc} OR role LIKE ? {esc} OR skills LIKE ? {esc} LIMIT 10)", (like, like, like, like)),
                ]
            _search_parts.extend([
                (f"SELECT * FROM (SELECT id, name as title, 'checklist' as type FROM checklists WHERE name LIKE ? {esc} LIMIT 10)", (like,)),
                (f"SELECT * FROM (SELECT id, name as title, 'skill' as type FROM skills WHERE name LIKE ? {esc} OR category LIKE ? {esc} OR notes LIKE ? {esc} LIMIT 5)", (like, like, like)),
                (f"SELECT * FROM (SELECT id, caliber as title, 'ammo' as type FROM ammo_inventory WHERE caliber LIKE ? {esc} OR brand LIKE ? {esc} OR location LIKE ? {esc} LIMIT 5)", (like, like, like)),
                (f"SELECT * FROM (SELECT id, name as title, 'equipment' as type FROM equipment_log WHERE name LIKE ? {esc} OR category LIKE ? {esc} OR location LIKE ? {esc} LIMIT 5)", (like, like, like)),
                (f"SELECT * FROM (SELECT id, name as title, 'waypoint' as type FROM waypoints WHERE name LIKE ? {esc} OR notes LIKE ? {esc} OR category LIKE ? {esc} LIMIT 5)", (like, like, like)),
                (f"SELECT * FROM (SELECT id, service as title, 'frequency' as type FROM freq_database WHERE service LIKE ? {esc} OR description LIKE ? {esc} OR notes LIKE ? {esc} LIMIT 5)", (like, like, like)),
                (f"SELECT * FROM (SELECT id, name as title, 'patient' as type FROM patients WHERE name LIKE ? {esc} LIMIT 5)", (like,)),
                (f"SELECT * FROM (SELECT id, description as title, 'incident' as type FROM incidents WHERE description LIKE ? {esc} OR category LIKE ? {esc} LIMIT 5)", (like, like)),
                (f"SELECT * FROM (SELECT id, fuel_type as title, 'fuel' as type FROM fuel_storage WHERE fuel_type LIKE ? {esc} OR location LIKE ? {esc} LIMIT 5)", (like, like)),
            ])
            union_sql = ' UNION ALL '.join(sql for sql, _ in _search_parts)
            union_params = []
            for _, params in _search_parts:
                union_params.extend(params)
            rows = db.execute(union_sql, tuple(union_params)).fetchall()

        # Group results by type
        result = {}
        _type_keys = {
            'conversation': 'conversations', 'note': 'notes', 'document': 'documents',
            'inventory': 'inventory', 'contact': 'contacts', 'checklist': 'checklists',
            'skill': 'skills', 'ammo': 'ammo', 'equipment': 'equipment',
            'waypoint': 'waypoints', 'frequency': 'frequencies', 'patient': 'patients',
            'incident': 'incidents', 'fuel': 'fuel',
        }
        for key in _type_keys.values():
            result[key] = []
        for r in rows:
            key = _type_keys.get(r['type'])
            if key:
                result[key].append(dict(r))
        return jsonify(result)
