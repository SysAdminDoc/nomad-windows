"""Blueprint for print/document generation routes and emergency sheet."""

import json
import platform
import logging
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, Response

from db import db_session
from web.print_templates import render_print_document
from web.utils import (
    esc as _esc,
    safe_json_value as _safe_json_value,
    get_node_name as _get_node_name,
)
from services import ollama, kiwix, cyberchef, kolibri, qdrant, stirling, flatnotes

log = logging.getLogger('nomad.web')

print_routes_bp = Blueprint('print_routes', __name__)

SERVICE_MODULES = {
    'ollama': ollama,
    'kiwix': kiwix,
    'cyberchef': cyberchef,
    'kolibri': kolibri,
    'qdrant': qdrant,
    'stirling': stirling,
    'flatnotes': flatnotes,
}


def _get_version():
    from web.app import VERSION
    return VERSION


def _pdf_setup():
    """Import ReportLab modules and return them as a namespace dict.

    Returns None if reportlab is not installed.
    """
    try:
        import io
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak,
        )
    except ImportError:
        return None
    return {
        'io': io, 'letter': letter, 'inch': inch,
        'getSampleStyleSheet': getSampleStyleSheet, 'ParagraphStyle': ParagraphStyle,
        'colors': colors, 'SimpleDocTemplate': SimpleDocTemplate,
        'Table': Table, 'TableStyle': TableStyle, 'Paragraph': Paragraph,
        'Spacer': Spacer, 'PageBreak': PageBreak,
    }


# ─── Preparedness Print ───────────────────────────────────────────

@print_routes_bp.route('/api/preparedness/print')
def api_preparedness_print():
    """Generate printable emergency summary page."""
    with db_session() as db:
        contacts = db.execute('SELECT * FROM contacts ORDER BY name LIMIT 10000').fetchall()
        settings = {r['key']: r['value'] for r in db.execute('SELECT key, value FROM settings').fetchall()}

        # Burn rate summary
        burn_rows = db.execute('SELECT category, name, quantity, unit, daily_usage FROM inventory WHERE daily_usage > 0 ORDER BY category LIMIT 5000').fetchall()
        burn = {}
        for r in burn_rows:
            cat = r['category']
            days = round(r['quantity'] / r['daily_usage'], 1) if r['daily_usage'] > 0 else 999
            if cat not in burn or days < burn[cat]:
                burn[cat] = days

        # Low stock items
        low = db.execute('SELECT name, quantity, unit, category FROM inventory WHERE quantity <= min_quantity AND min_quantity > 0 LIMIT 5000').fetchall()

        # Expiring items
        soon = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        expiring = db.execute("SELECT name, expiration, category FROM inventory WHERE expiration != '' AND expiration <= ? ORDER BY expiration LIMIT 5000", (soon,)).fetchall()

    # Situation board
    sit = _safe_json_value(settings.get('sit_board'), {})

    sit_colors = {'green': '#2d6a2d', 'yellow': '#8a7a00', 'orange': '#a84a12', 'red': '#993333'}
    sit_labels = {'green': 'GOOD', 'yellow': 'CAUTION', 'orange': 'CONCERN', 'red': 'CRITICAL'}

    generated_at = datetime.now().strftime('%Y-%m-%d %H:%M')
    sit_html = '<div class="doc-empty">Situation board is not configured yet.</div>'
    if sit:
        sit_html = '<div class="doc-chip-list">'
        for domain in ['security', 'water', 'food', 'medical', 'power', 'comms']:
            lvl = sit.get(domain, 'green')
            color = sit_colors.get(lvl, '#4b5563')
            sit_html += (
                f'<span class="doc-chip" style="background:{color};border-color:{color};color:#fff;">'
                f'{domain.upper()}: {sit_labels.get(lvl, "?")}'
                '</span>'
            )
        sit_html += '</div>'

    contacts_html = '<div class="doc-empty">No emergency contacts are available yet.</div>'
    if contacts:
        contacts_html = '<div class="doc-table-shell"><table><thead><tr><th>Name</th><th>Role</th><th>Callsign</th><th>Phone</th><th>Freq</th><th>Blood</th><th>Rally Point</th></tr></thead><tbody>'
        for c in contacts:
            contacts_html += (
                f'<tr><td class="doc-strong">{_esc(c["name"])}</td><td>{_esc(c["role"])}</td>'
                f'<td>{_esc(c["callsign"]) or "-"}</td><td>{_esc(c["phone"]) or "-"}</td>'
                f'<td>{_esc(c["freq"]) or "-"}</td><td>{_esc(c["blood_type"]) or "-"}</td>'
                f'<td>{_esc(c["rally_point"]) or "-"}</td></tr>'
            )
        contacts_html += '</tbody></table></div>'

    supply_html = '<div class="doc-empty">No burn-rate tracked inventory is available.</div>'
    if burn:
        supply_html = '<div class="doc-table-shell"><table><thead><tr><th>Resource</th><th>Days Left</th></tr></thead><tbody>'
        for cat, days in sorted(burn.items()):
            marker = ' class="doc-alert"' if days < 7 else ''
            supply_html += f'<tr><td class="doc-strong">{_esc(cat.upper())}</td><td{marker}>{days}</td></tr>'
        supply_html += '</tbody></table></div>'

    low_html = '<div class="doc-empty">No low-stock alerts at the moment.</div>'
    if low:
        low_html = '<div class="doc-table-shell"><table><thead><tr><th>Item</th><th>Qty</th><th>Category</th></tr></thead><tbody>'
        for r in low:
            low_html += (
                f'<tr><td class="doc-alert">{_esc(r["name"])}</td><td>{r["quantity"]} {_esc(r["unit"])}</td>'
                f'<td>{_esc(r["category"])}</td></tr>'
            )
        low_html += '</tbody></table></div>'

    expiring_html = '<div class="doc-empty">No items are expiring in the next 30 days.</div>'
    if expiring:
        expiring_html = '<div class="doc-table-shell"><table><thead><tr><th>Item</th><th>Expires</th><th>Category</th></tr></thead><tbody>'
        for r in expiring:
            expiring_html += f'<tr><td class="doc-strong">{_esc(r["name"])}</td><td>{_esc(r["expiration"])}</td><td>{_esc(r["category"])}</td></tr>'
        expiring_html += '</tbody></table></div>'

    body = f'''<section class="doc-section">
  <h2 class="doc-section-title">Situation Status</h2>
  {sit_html}
</section>
<section class="doc-section">
  <div class="doc-grid-2">
    <div class="doc-panel doc-panel-strong">
      <h2 class="doc-section-title">Supply Burn Snapshot</h2>
      {supply_html}
    </div>
    <div class="doc-panel doc-panel-strong">
      <h2 class="doc-section-title">Expiring Soon</h2>
      {expiring_html}
    </div>
  </div>
</section>
<section class="doc-section">
  <div class="doc-grid-2">
    <div class="doc-panel">
      <h2 class="doc-section-title">Low Stock Alerts</h2>
      {low_html}
    </div>
    <div class="doc-panel">
      <h2 class="doc-section-title">Key Frequencies</h2>
      <div class="doc-table-shell"><table><thead><tr><th>Use</th><th>Freq / Ch</th></tr></thead><tbody>
        <tr><td class="doc-strong">FRS Rally</td><td>Ch 1 / 462.5625 MHz</td></tr>
        <tr><td class="doc-strong">FRS Emergency</td><td>Ch 3 / 462.6125 MHz</td></tr>
        <tr><td class="doc-strong">GMRS Emergency</td><td>Ch 20 / 462.6750 MHz</td></tr>
        <tr><td class="doc-strong">CB Emergency</td><td>Ch 9 / 27.065 MHz</td></tr>
        <tr><td class="doc-strong">CB Highway</td><td>Ch 19 / 27.185 MHz</td></tr>
        <tr><td class="doc-strong">2m Calling</td><td>146.520 MHz</td></tr>
        <tr><td class="doc-strong">2m Emergency</td><td>146.550 MHz</td></tr>
        <tr><td class="doc-strong">NOAA Weather</td><td>162.400 - 162.550 MHz</td></tr>
      </tbody></table></div>
    </div>
  </div>
</section>
<section class="doc-section">
  <h2 class="doc-section-title">Emergency Contacts</h2>
  {contacts_html}
</section>
<section class="doc-section">
  <div class="doc-footer">
    <span>Offline operations snapshot for rapid reference and print carry.</span>
    <span>NOMAD Field Desk Ready Card</span>
  </div>
</section>'''
    html = render_print_document(
        'Emergency Card',
        'Compact operational snapshot covering status, contacts, supply risk, and critical comms references.',
        body,
        eyebrow='NOMAD Field Desk Ready Card',
        meta_items=[f'Generated {generated_at}', 'Keep accessible'],
        stat_items=[
            ('Contacts', len(contacts)),
            ('Low Stock', len(low)),
            ('Expiring', len(expiring)),
            ('Supply Categories', len(burn)),
        ],
        accent_start='#14304a',
        accent_end='#2f6480',
        max_width='1000px',
    )
    return Response(html, mimetype='text/html')


# ─── Status Report ─────────────────────────────────────────────────

@print_routes_bp.route('/api/status-report')
def api_status_report():
    """Generate a comprehensive status report from all systems."""
    VERSION = _get_version()
    with db_session() as db:

        report = {'generated': datetime.now().isoformat(), 'version': VERSION}

        # Situation board
        sit_row = db.execute("SELECT value FROM settings WHERE key = 'sit_board'").fetchone()
        report['situation'] = _safe_json_value(sit_row['value'] if sit_row else None, {})

        # Services
        report['services'] = {}
        for sid, mod in SERVICE_MODULES.items():
            report['services'][sid] = {'installed': mod.is_installed(), 'running': mod.running() if mod.is_installed() else False}

        # Inventory summary
        inv = db.execute('SELECT category, COUNT(*) as cnt, SUM(quantity) as qty FROM inventory GROUP BY category').fetchall()
        report['inventory'] = {r['category']: {'count': r['cnt'], 'quantity': r['qty'] or 0} for r in inv}

        low = db.execute('SELECT COUNT(*) as c FROM inventory WHERE quantity <= min_quantity AND min_quantity > 0').fetchone()['c']
        report['low_stock_count'] = low

        # Burn rates
        burns = db.execute('SELECT category, MIN(quantity/daily_usage) as min_days FROM inventory WHERE daily_usage > 0 GROUP BY category').fetchall()
        report['burn_rates'] = {r['category']: round(r['min_days'], 1) for r in burns if r['min_days'] is not None}

        # Contacts
        report['contact_count'] = db.execute('SELECT COUNT(*) as c FROM contacts').fetchone()['c']

        # Recent incidents
        report['incidents_24h'] = db.execute("SELECT COUNT(*) as c FROM incidents WHERE created_at >= datetime('now', '-24 hours')").fetchone()['c']

        # Active checklists
        cls = db.execute('SELECT name, items FROM checklists').fetchall()
        cl_summary = []
        for c in cls:
            items = json.loads(c['items'] or '[]')
            total = len(items)
            checked = sum(1 for i in items if i.get('checked'))
            cl_summary.append({'name': c['name'], 'pct': round(checked / total * 100) if total > 0 else 0})
        report['checklists'] = cl_summary

        # Weather
        wx = db.execute('SELECT pressure_hpa, temp_f, created_at FROM weather_log ORDER BY created_at DESC LIMIT 1').fetchone()
        if wx:
            report['weather'] = {'pressure': wx['pressure_hpa'], 'temp_f': wx['temp_f'], 'time': wx['created_at']}

        # Timers
        report['active_timers'] = db.execute('SELECT COUNT(*) as c FROM timers').fetchone()['c']

        # Notes and conversations
        report['notes_count'] = db.execute('SELECT COUNT(*) as c FROM notes').fetchone()['c']
        report['conversations_count'] = db.execute('SELECT COUNT(*) as c FROM conversations').fetchone()['c']


    # Generate text report
    txt = f"===== NOMAD FIELD DESK STATUS REPORT =====\nGenerated: {report['generated']}\nVersion: {report['version']}\n\n"

    if report['situation']:
        txt += "SITUATION BOARD:\n"
        for domain, level in report['situation'].items():
            txt += f"  {domain.upper()}: {level.upper()}\n"
        txt += "\n"

    txt += "SERVICES:\n"
    for sid, info in report['services'].items():
        status = 'RUNNING' if info['running'] else 'INSTALLED' if info['installed'] else 'NOT INSTALLED'
        txt += f"  {sid}: {status}\n"
    txt += "\n"

    if report['inventory']:
        txt += f"INVENTORY ({report['low_stock_count']} low stock):\n"
        for cat, info in report['inventory'].items():
            burn = report['burn_rates'].get(cat, '')
            burn_str = f" ({burn} days)" if burn else ''
            txt += f"  {cat}: {info['count']} items, {info['quantity']} total{burn_str}\n"
        txt += "\n"

    txt += f"TEAM: {report['contact_count']} contacts\n"
    txt += f"INCIDENTS (24h): {report['incidents_24h']}\n"
    txt += f"ACTIVE TIMERS: {report['active_timers']}\n"
    txt += f"NOTES: {report['notes_count']} | CONVERSATIONS: {report['conversations_count']}\n"

    if report.get('weather'):
        txt += f"\nWEATHER: {report['weather']['pressure']} hPa, {report['weather']['temp_f']}F\n"

    if report['checklists']:
        txt += "\nCHECKLISTS:\n"
        for cl in report['checklists']:
            txt += f"  {cl['name']}: {cl['pct']}% complete\n"

    txt += "\n===== END REPORT ====="

    report['text'] = txt
    return jsonify(report)


# ─── Printable Reports ─────────────────────────────────────────────

@print_routes_bp.route('/api/print/freq-card')
def api_print_freq_card():
    """Printable pocket frequency reference card."""
    with db_session() as db:
        freqs = db.execute('SELECT * FROM comms_log ORDER BY created_at DESC LIMIT 20').fetchall()
        contacts = db.execute("SELECT name, callsign, phone FROM contacts WHERE callsign != '' OR phone != '' ORDER BY name").fetchall()
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    standard_rows = [
        ('FRS Ch 1', '462.5625 MHz', 'Family rally primary'),
        ('FRS Ch 3', '462.6125 MHz', 'Neighborhood emergency net'),
        ('GMRS Ch 20', '462.6750 MHz', 'High-power emergency channel'),
        ('MURS Ch 1', '151.820 MHz', 'No-license local simplex'),
        ('2m Calling', '146.520 MHz', 'National ham calling'),
        ('70cm Calling', '446.000 MHz', 'National UHF calling'),
        ('HF 40m', '7.260 MHz', 'Regional emergency traffic'),
        ('Marine 16', '156.800 MHz', 'Distress and calling'),
        ('CB Ch 9', '27.065 MHz', 'Emergency channel'),
        ('CB Ch 19', '27.185 MHz', 'Road and highway traffic'),
        ('NOAA WX', '162.550 MHz', 'Weather broadcast'),
    ]

    standard_html = '<div class="doc-table-shell"><table><thead><tr><th>Service</th><th>Frequency</th><th>Use</th></tr></thead><tbody>'
    for service, freq, notes in standard_rows:
        standard_html += f'<tr><td class="doc-strong">{service}</td><td>{freq}</td><td>{notes}</td></tr>'
    standard_html += '</tbody></table></div>'

    traffic_html = '<div class="doc-empty">No recent radio logs have been recorded yet.</div>'
    if freqs:
        traffic_html = '<div class="doc-table-shell"><table><thead><tr><th>Time</th><th>Callsign</th><th>Freq</th><th>Dir</th><th>Signal</th></tr></thead><tbody>'
        for entry in freqs[:10]:
            traffic_html += (
                f'<tr><td>{_esc(str(entry["created_at"]))}</td><td class="doc-strong">{_esc(entry["callsign"] or "-")}</td>'
                f'<td>{_esc(entry["freq"] or "-")}</td><td>{_esc(entry["direction"] or "-")}</td>'
                f'<td>{_esc(str(entry["signal_quality"] or "-"))}</td></tr>'
            )
        traffic_html += '</tbody></table></div>'

    contacts_html = '<div class="doc-empty">No radio contacts with a callsign or phone are on file.</div>'
    if contacts:
        contacts_html = '<div class="doc-table-shell"><table><thead><tr><th>Name</th><th>Callsign</th><th>Phone</th></tr></thead><tbody>'
        for c in contacts:
            contacts_html += f'<tr><td class="doc-strong">{_esc(c["name"])}</td><td>{_esc(c["callsign"] or "-")}</td><td>{_esc(c["phone"] or "-")}</td></tr>'
        contacts_html += '</tbody></table></div>'

    body = f'''<section class="doc-section">
  <div class="doc-grid-2">
    <div class="doc-panel doc-panel-strong">
      <h2 class="doc-section-title">Standard Frequencies</h2>
      {standard_html}
    </div>
    <div class="doc-panel doc-panel-strong">
      <h2 class="doc-section-title">Recent Traffic</h2>
      {traffic_html}
    </div>
  </div>
</section>
<section class="doc-section">
  <div class="doc-grid-2">
    <div class="doc-panel">
      <h2 class="doc-section-title">Team Contacts</h2>
      {contacts_html}
    </div>
    <div class="doc-panel">
      <h2 class="doc-section-title">Radio Notes</h2>
      <div class="doc-kv">
        <div class="doc-kv-row"><div class="doc-kv-key">Call Format</div><div>&quot;This is [callsign], on [channel/freq], over.&quot;</div></div>
        <div class="doc-kv-row"><div class="doc-kv-key">Priority</div><div>Emergency traffic first, logistics second, routine last.</div></div>
        <div class="doc-kv-row"><div class="doc-kv-key">Fallback</div><div>If no answer on the primary channel, try the neighborhood emergency net, then 2m calling.</div></div>
        <div class="doc-kv-row"><div class="doc-kv-key">Logging</div><div>Record time, callsign, direction, signal quality, and any action taken.</div></div>
      </div>
    </div>
  </div>
</section>
<section class="doc-section">
  <div class="doc-footer">
    <span>Field comms cheat sheet for print carry and quick app-frame reference.</span>
    <span>Monitor before transmit when possible.</span>
  </div>
</section>'''
    html = render_print_document(
        'Frequency Reference Card',
        'Pocket comms quick-reference covering standard channels, recent traffic, and team contact lookups.',
        body,
        eyebrow='NOMAD Field Desk Comms Reference',
        meta_items=[f'Generated {now}', 'A5 landscape', 'Offline reference'],
        stat_items=[
            ('Recent Logs', len(freqs)),
            ('Contacts', len(contacts)),
            ('Primary Net', 'FRS 1'),
            ('Calling', '146.520'),
        ],
        accent_start='#16324a',
        accent_end='#2b657e',
        max_width='1120px',
        page_size='A5',
        landscape=True,
    )
    return Response(html, mimetype='text/html')


@print_routes_bp.route('/api/print/medical-cards')
def api_print_medical_cards():
    """Printable wallet-sized medical cards for each person."""
    with db_session() as db:
        patients = db.execute('SELECT * FROM patients ORDER BY name LIMIT 10000').fetchall()
    now = datetime.now().strftime('%Y-%m-%d')
    card_grid = '<div class="doc-grid-3">'
    allergy_count = 0
    medication_count = 0
    for p in patients:
        record = dict(p)
        try: allergies = json.loads(record['allergies'] or '[]')
        except (json.JSONDecodeError, TypeError): allergies = []
        try: conditions = json.loads(record['conditions'] or '[]')
        except (json.JSONDecodeError, TypeError): conditions = []
        try: medications = json.loads(record['medications'] or '[]')
        except (json.JSONDecodeError, TypeError): medications = []
        if allergies:
            allergy_count += 1
        if medications:
            medication_count += 1
        allergy_html = ''.join(f'<span class="doc-chip doc-chip-alert">{_esc(str(a))}</span>' for a in allergies) or '<span class="doc-chip doc-chip-muted">NKDA</span>'
        conditions_html = ''.join(f'<span class="doc-chip">{_esc(str(c))}</span>' for c in conditions) or '<span class="doc-chip doc-chip-muted">None recorded</span>'
        meds_html = ''.join(f'<span class="doc-chip">{_esc(str(m))}</span>' for m in medications) or '<span class="doc-chip doc-chip-muted">None recorded</span>'
        card_grid += f'''<div class="doc-panel doc-panel-strong">
  <h2 class="doc-section-title">Medical Card</h2>
  <div class="doc-note-box" style="background:#fff;border-style:solid;">
    <div class="doc-strong" style="font-size:18px;">{_esc(record["name"])}</div>
    <div style="margin-top:10px;" class="doc-chip-list">
      <span class="doc-chip">DOB: {_esc(str(record.get("dob","\u2014")))}</span>
      <span class="doc-chip">Blood: {_esc(str(record.get("blood_type","\u2014")))}</span>
      <span class="doc-chip">Weight: {_esc(str(record.get("weight_kg","?")))} kg</span>
    </div>
    <div style="margin-top:12px;">
      <div class="doc-section-title" style="margin-bottom:8px;">Allergies</div>
      <div class="doc-chip-list">{allergy_html}</div>
    </div>
    <div style="margin-top:12px;">
      <div class="doc-section-title" style="margin-bottom:8px;">Conditions</div>
      <div class="doc-chip-list">{conditions_html}</div>
    </div>
    <div style="margin-top:12px;">
      <div class="doc-section-title" style="margin-bottom:8px;">Medications</div>
      <div class="doc-chip-list">{meds_html}</div>
    </div>
  </div>
</div>'''
    card_grid += '</div>'
    if not patients:
        card_grid = '<div class="doc-empty">No patients registered. Add medical profiles in the Medical workspace to generate cards.</div>'
    body = f'''<section class="doc-section">
  <h2 class="doc-section-title">Patient Medical Cards</h2>
  {card_grid}
</section>
<section class="doc-section">
  <div class="doc-footer">
    <span>Bulk print view for grab-kit inserts, clipboard packets, and rapid patient reference.</span>
    <span>Generated by NOMAD Field Desk.</span>
  </div>
</section>'''
    html = render_print_document(
        'Medical Cards',
        'Bulk patient card sheet for fast print review before assembling wallet cards, binders, or transfer packets.',
        body,
        eyebrow='NOMAD Field Desk Medical Cards',
        meta_items=[f'Generated {now}', 'Bulk print view'],
        stat_items=[
            ('Patients', len(patients)),
            ('With Allergies', allergy_count),
            ('With Medications', medication_count),
            ('Updated', now),
        ],
        accent_start='#3b2030',
        accent_end='#7a3346',
        max_width='1160px',
    )
    return Response(html, mimetype='text/html')


@print_routes_bp.route('/api/print/bug-out-checklist')
def api_print_bugout():
    """Printable bug-out grab-and-go checklist."""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    items = [
        ('WATER','2+ gallons per person, filter/purification tabs, collapsible container'),
        ('FOOD','72-hour supply, MREs/bars/freeze-dried, can opener, utensils'),
        ('FIRST AID','IFAK, tourniquet, hemostatic gauze, meds, Rx copies'),
        ('SHELTER','Tent/tarp, sleeping bag/bivvy, emergency blankets, cordage'),
        ('FIRE','Lighter, ferro rod, tinder, stormproof matches, candle'),
        ('COMMS','Radio (GMRS/ham), extra batteries, frequencies card, whistle'),
        ('NAVIGATION','Maps (paper), compass, GPS (charged), waypoints list'),
        ('DOCUMENTS','IDs, insurance, deeds, cash ($small bills), USB backup'),
        ('CLOTHING','Season-appropriate layers, rain gear, boots, extra socks, hat, gloves'),
        ('TOOLS','Knife, multi-tool, flashlight (2+), headlamp, duct tape, zip ties'),
        ('DEFENSE','Per your plan and training'),
        ('POWER','Battery bank, solar charger, cables, crank radio'),
        ('HYGIENE','Toilet paper, soap, toothbrush, medications, feminine products, trash bags'),
        ('SPECIALTY','Glasses, hearing aids, pet supplies, infant needs, prescription meds'),
    ]
    checklist_html = '<div class="doc-checklist">'
    for cat, desc in items:
        checklist_html += (
            '<div class="doc-check-item">'
            '<div class="doc-check-box"></div>'
            f'<div class="doc-check-label">{cat}</div>'
            f'<div class="doc-check-copy">{desc}</div>'
            '</div>'
        )
    checklist_html += '</div>'

    body = f'''<section class="doc-section">
  <div class="doc-panel doc-panel-strong">
    <h2 class="doc-section-title">Load Checklist</h2>
    {checklist_html}
  </div>
</section>
<section class="doc-section">
  <div class="doc-grid-2">
    <div class="doc-panel">
      <h2 class="doc-section-title">Movement Plan</h2>
      <div class="doc-kv">
        <div class="doc-kv-row"><div class="doc-kv-key">Primary Route</div><div>______________________________________</div></div>
        <div class="doc-kv-row"><div class="doc-kv-key">Alternate Route</div><div>______________________________________</div></div>
        <div class="doc-kv-row"><div class="doc-kv-key">Departure Trigger</div><div>______________________________________</div></div>
      </div>
    </div>
    <div class="doc-panel">
      <h2 class="doc-section-title">Rally Points</h2>
      <div class="doc-kv">
        <div class="doc-kv-row"><div class="doc-kv-key">Primary</div><div>______________________________________</div></div>
        <div class="doc-kv-row"><div class="doc-kv-key">Secondary</div><div>______________________________________</div></div>
        <div class="doc-kv-row"><div class="doc-kv-key">Tertiary</div><div>______________________________________</div></div>
      </div>
    </div>
  </div>
</section>
<section class="doc-section">
  <div class="doc-footer">
    <span>Check items as they are staged or loaded.</span>
    <span>Target departure time: 15 minutes or less.</span>
  </div>
</section>'''
    html = render_print_document(
        'Bug-Out Checklist',
        'Rapid departure packing sheet for go-bags, vehicles, and family movement planning.',
        body,
        eyebrow='NOMAD Field Desk Go-Bag Checklist',
        meta_items=[f'Generated {now}', 'Review monthly'],
        stat_items=[
            ('Checklist Items', len(items)),
            ('Goal', '15 min'),
            ('Routes', 2),
            ('Rally Points', 3),
        ],
        accent_start='#5c2b15',
        accent_end='#9b4a1f',
        max_width='980px',
    )
    return Response(html, mimetype='text/html')


# ─── PDF Generation (ReportLab) ──────────────────────────────────

@print_routes_bp.route('/api/print/pdf/operations-binder')
def api_print_pdf_operations_binder():
    """Generate a full operations binder as a PDF using ReportLab."""
    rl = _pdf_setup()
    if rl is None:
        return jsonify({'error': 'reportlab not installed', 'hint': 'pip install reportlab'}), 500
    io, letter, inch = rl['io'], rl['letter'], rl['inch']
    getSampleStyleSheet, ParagraphStyle = rl['getSampleStyleSheet'], rl['ParagraphStyle']
    colors = rl['colors']
    SimpleDocTemplate, Table, TableStyle = rl['SimpleDocTemplate'], rl['Table'], rl['TableStyle']
    Paragraph, Spacer, PageBreak = rl['Paragraph'], rl['Spacer'], rl['PageBreak']

    with db_session() as db:
        contacts = [dict(r) for r in db.execute('SELECT * FROM contacts ORDER BY name LIMIT 500').fetchall()]
        freqs = [dict(r) for r in db.execute('SELECT * FROM comms_log ORDER BY created_at DESC LIMIT 50').fetchall()]
        patients = [dict(r) for r in db.execute('SELECT * FROM patients ORDER BY name LIMIT 200').fetchall()]
        inventory = [dict(r) for r in db.execute('SELECT * FROM inventory ORDER BY category, name LIMIT 1000').fetchall()]
        checklists = [dict(r) for r in db.execute('SELECT name, items FROM checklists ORDER BY name LIMIT 200').fetchall()]
        waypoints = [dict(r) for r in db.execute('SELECT * FROM waypoints ORDER BY category, name LIMIT 500').fetchall()]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch,
                            leftMargin=0.6*inch, rightMargin=0.6*inch)
    styles = getSampleStyleSheet()
    mono = ParagraphStyle('Mono', parent=styles['Normal'], fontName='Courier', fontSize=8, leading=10)
    mono_bold = ParagraphStyle('MonoBold', parent=mono, fontName='Courier-Bold', fontSize=9, leading=11)
    title_style = ParagraphStyle('TitleMono', fontName='Courier-Bold', fontSize=18, leading=22, alignment=1, spaceAfter=12)
    subtitle_style = ParagraphStyle('SubtitleMono', fontName='Courier', fontSize=11, leading=14, alignment=1, spaceAfter=6, textColor=colors.grey)
    section_style = ParagraphStyle('SectionMono', fontName='Courier-Bold', fontSize=12, leading=15, spaceBefore=16, spaceAfter=8,
                                    borderWidth=1, borderColor=colors.black, borderPadding=4)
    toc_style = ParagraphStyle('TOCMono', fontName='Courier', fontSize=10, leading=14, spaceBefore=4)

    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    node_name = _get_node_name()
    elements = []

    # Cover page
    elements.append(Spacer(1, 2*inch))
    elements.append(Paragraph('NOMAD', title_style))
    elements.append(Paragraph('OPERATIONS BINDER', ParagraphStyle('Cover2', fontName='Courier-Bold', fontSize=14, alignment=1, spaceAfter=20)))
    elements.append(Paragraph(f'Node: {_esc(node_name)}', subtitle_style))
    elements.append(Paragraph(f'Generated: {now}', subtitle_style))
    elements.append(Paragraph('CLASSIFIED -- FOR AUTHORIZED PERSONNEL ONLY', ParagraphStyle('Warn', fontName='Courier-Bold', fontSize=9, alignment=1, textColor=colors.red, spaceBefore=40)))
    elements.append(PageBreak())

    # Table of Contents
    elements.append(Paragraph('TABLE OF CONTENTS', section_style))
    toc_items = ['1. Contacts Directory', '2. Communications / Frequencies', '3. Medical Patient Cards',
                 '4. Supply Inventory', '5. Checklists', '6. Waypoints / Navigation']
    for item in toc_items:
        elements.append(Paragraph(item, toc_style))
    elements.append(PageBreak())

    # 1. Contacts
    elements.append(Paragraph('1. CONTACTS DIRECTORY', section_style))
    if contacts:
        t_data = [['Name', 'Role', 'Callsign', 'Phone', 'Freq', 'Blood', 'Rally Point']]
        for c in contacts:
            t_data.append([c.get('name',''), c.get('role',''), c.get('callsign',''),
                          c.get('phone',''), c.get('freq',''), c.get('blood_type',''), c.get('rally_point','')])
        t = Table(t_data, repeatRows=1)
        t.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,0), 'Courier-Bold'), ('FONTSIZE', (0,0), (-1,-1), 7),
            ('FONTNAME', (0,1), (-1,-1), 'Courier'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BACKGROUND', (0,0), (-1,0), colors.Color(0.85, 0.85, 0.85)),
            ('VALIGN', (0,0), (-1,-1), 'TOP'), ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph('No contacts registered.', mono))
    elements.append(PageBreak())

    # 2. Frequencies
    elements.append(Paragraph('2. COMMUNICATIONS / FREQUENCIES', section_style))
    if freqs:
        t_data = [['Freq', 'Callsign', 'Direction', 'Message', 'Signal', 'Time']]
        for f in freqs:
            t_data.append([f.get('freq',''), f.get('callsign',''), f.get('direction',''),
                          (f.get('message','') or '')[:60], f.get('signal_quality',''), f.get('created_at','')])
        t = Table(t_data, repeatRows=1)
        t.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,0), 'Courier-Bold'), ('FONTSIZE', (0,0), (-1,-1), 7),
            ('FONTNAME', (0,1), (-1,-1), 'Courier'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BACKGROUND', (0,0), (-1,0), colors.Color(0.85, 0.85, 0.85)),
            ('VALIGN', (0,0), (-1,-1), 'TOP'), ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph('No communications logged.', mono))
    elements.append(PageBreak())

    # 3. Medical
    elements.append(Paragraph('3. MEDICAL PATIENT CARDS', section_style))
    if patients:
        for p in patients:
            elements.append(Paragraph(f'Patient: {_esc(p["name"])}', mono_bold))
            try: allergies = ', '.join(str(a) for a in json.loads(p.get('allergies') or '[]'))
            except (json.JSONDecodeError, TypeError): allergies = ''
            try: conditions = ', '.join(str(c) for c in json.loads(p.get('conditions') or '[]'))
            except (json.JSONDecodeError, TypeError): conditions = ''
            try: medications = ', '.join(str(m) for m in json.loads(p.get('medications') or '[]'))
            except (json.JSONDecodeError, TypeError): medications = ''
            info = [
                f'Blood Type: {p.get("blood_type","--")}  |  Weight: {p.get("weight_kg","?")} kg  |  Sex: {p.get("sex","--")}',
                f'Allergies: {allergies or "NKDA"}',
                f'Conditions: {conditions or "None"}',
                f'Medications: {medications or "None"}',
            ]
            for line in info:
                elements.append(Paragraph(line, mono))
            elements.append(Spacer(1, 12))
    else:
        elements.append(Paragraph('No patients registered.', mono))
    elements.append(PageBreak())

    # 4. Inventory
    elements.append(Paragraph('4. SUPPLY INVENTORY', section_style))
    if inventory:
        t_data = [['Name', 'Category', 'Qty', 'Unit', 'Min', 'Location', 'Expires']]
        for item in inventory:
            t_data.append([item.get('name',''), item.get('category',''), str(item.get('quantity',0)),
                          item.get('unit',''), str(item.get('min_quantity','')),
                          item.get('location',''), item.get('expiration','')])
        t = Table(t_data, repeatRows=1)
        t.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,0), 'Courier-Bold'), ('FONTSIZE', (0,0), (-1,-1), 7),
            ('FONTNAME', (0,1), (-1,-1), 'Courier'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BACKGROUND', (0,0), (-1,0), colors.Color(0.85, 0.85, 0.85)),
            ('VALIGN', (0,0), (-1,-1), 'TOP'), ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph('No inventory items.', mono))
    elements.append(PageBreak())

    # 5. Checklists
    elements.append(Paragraph('5. CHECKLISTS', section_style))
    if checklists:
        for cl in checklists:
            elements.append(Paragraph(f'[ ] {_esc(cl["name"])}', mono_bold))
            try:
                cl_items = json.loads(cl.get('items') or '[]')
                for it in cl_items:
                    label = it.get('text', it) if isinstance(it, dict) else str(it)
                    checked = it.get('checked', False) if isinstance(it, dict) else False
                    mark = '[X]' if checked else '[ ]'
                    elements.append(Paragraph(f'    {mark} {_esc(str(label))}', mono))
            except (json.JSONDecodeError, TypeError):
                pass
            elements.append(Spacer(1, 8))
    else:
        elements.append(Paragraph('No checklists.', mono))
    elements.append(PageBreak())

    # 6. Waypoints
    elements.append(Paragraph('6. WAYPOINTS / NAVIGATION', section_style))
    if waypoints:
        t_data = [['Name', 'Category', 'Latitude', 'Longitude', 'Elevation', 'Notes']]
        for w in waypoints:
            t_data.append([w.get('name',''), w.get('category',''), str(w.get('lat','')),
                          str(w.get('lng','')), str(w.get('elevation_m','') or ''),
                          (w.get('notes','') or '')[:40]])
        t = Table(t_data, repeatRows=1)
        t.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,0), 'Courier-Bold'), ('FONTSIZE', (0,0), (-1,-1), 7),
            ('FONTNAME', (0,1), (-1,-1), 'Courier'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BACKGROUND', (0,0), (-1,0), colors.Color(0.85, 0.85, 0.85)),
            ('VALIGN', (0,0), (-1,-1), 'TOP'), ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph('No waypoints.', mono))

    # Footer
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(f'End of Operations Binder -- Generated {now} by NOMAD Field Desk ({_esc(node_name)})', subtitle_style))

    doc.build(elements)
    buf.seek(0)
    return Response(buf.read(), mimetype='application/pdf',
                   headers={'Content-Disposition': f'attachment; filename="NOMAD-Operations-Binder-{datetime.now().strftime("%Y%m%d")}.pdf"'})


@print_routes_bp.route('/api/print/pdf/wallet-cards')
def api_print_pdf_wallet_cards():
    """Generate PDF wallet-sized cards (3.375 x 2.125 inches each)."""
    rl = _pdf_setup()
    if rl is None:
        return jsonify({'error': 'reportlab not installed', 'hint': 'pip install reportlab'}), 500
    io, letter, inch = rl['io'], rl['letter'], rl['inch']
    ParagraphStyle, colors = rl['ParagraphStyle'], rl['colors']
    SimpleDocTemplate, Table, TableStyle = rl['SimpleDocTemplate'], rl['Table'], rl['TableStyle']
    Paragraph, Spacer = rl['Paragraph'], rl['Spacer']

    with db_session() as db:
        patients = [dict(r) for r in db.execute('SELECT * FROM patients ORDER BY name LIMIT 10000').fetchall()]
        contacts = [dict(r) for r in db.execute("SELECT name, phone, callsign, freq, rally_point FROM contacts WHERE phone != '' OR callsign != '' ORDER BY name LIMIT 10").fetchall()]
        waypoints = [dict(r) for r in db.execute("SELECT name, lat, lng, category FROM waypoints WHERE category IN ('rally','shelter','cache','home','base') ORDER BY name LIMIT 6").fetchall()]
        freqs = [dict(r) for r in db.execute('SELECT freq, callsign, message FROM comms_log ORDER BY created_at DESC LIMIT 8').fetchall()]

    CARD_W = 3.375 * inch

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch,
                            leftMargin=0.5*inch, rightMargin=0.5*inch)
    card_title = ParagraphStyle('CardTitle', fontName='Courier-Bold', fontSize=8, leading=10, alignment=1, spaceAfter=2)
    card_body = ParagraphStyle('CardBody', fontName='Courier', fontSize=6, leading=7.5)
    card_label = ParagraphStyle('CardLabel', fontName='Courier-Bold', fontSize=6, leading=7.5)
    footer_style = ParagraphStyle('Footer', fontName='Courier', fontSize=5, leading=6, textColor=colors.grey, alignment=2)

    now = datetime.now().strftime('%Y-%m-%d')
    elements = []
    cards = []

    # ICE Card for each patient
    for p in patients:
        try: allergies = ', '.join(str(a) for a in json.loads(p.get('allergies') or '[]'))
        except (json.JSONDecodeError, TypeError): allergies = ''
        try: meds = ', '.join(str(m) for m in json.loads(p.get('medications') or '[]'))
        except (json.JSONDecodeError, TypeError): meds = ''
        try: conditions_str = ', '.join(str(c) for c in json.loads(p.get('conditions') or '[]'))
        except (json.JSONDecodeError, TypeError): conditions_str = ''

        card_data = [
            [Paragraph(f'ICE CARD -- {_esc(p["name"])}', card_title)],
            [Paragraph(f'<b>Blood:</b> {_esc(p.get("blood_type","--"))}  <b>Wt:</b> {p.get("weight_kg","?")}kg  <b>Sex:</b> {_esc(p.get("sex","--"))}', card_body)],
            [Paragraph(f'<b>Allergies:</b> {_esc(allergies) or "NKDA"}', card_body)],
            [Paragraph(f'<b>Conditions:</b> {_esc(conditions_str) or "None"}', card_body)],
            [Paragraph(f'<b>Medications:</b> {_esc(meds) or "None"}', card_body)],
            [Paragraph(f'NOMAD -- {now}', footer_style)],
        ]
        cards.append(card_data)

    # Rally Points card
    if waypoints:
        wp_lines = [[Paragraph('RALLY POINTS', card_title)]]
        for w in waypoints:
            wp_lines.append([Paragraph(f'{_esc(w["name"])} ({w["category"]}): {w["lat"]:.5f}, {w["lng"]:.5f}', card_body)])
        wp_lines.append([Paragraph(f'NOMAD -- {now}', footer_style)])
        cards.append(wp_lines)

    # Frequency Quick-Ref card
    freq_lines = [[Paragraph('FREQ QUICK REFERENCE', card_title)]]
    std_freqs = [('FRS 1', '462.5625'), ('GMRS 1', '462.5625'), ('2m Call', '146.520'),
                 ('70cm Call', '446.000'), ('CB 9', '27.065'), ('NOAA', '162.550')]
    for fname, fval in std_freqs:
        freq_lines.append([Paragraph(f'{fname}: {fval}', card_body)])
    if freqs:
        freq_lines.append([Paragraph('<b>-- Team Freqs --</b>', card_label)])
        for f in freqs[:4]:
            freq_lines.append([Paragraph(f'{f.get("freq","?")} ({_esc(f.get("callsign",""))})', card_body)])
    freq_lines.append([Paragraph(f'NOMAD -- {now}', footer_style)])
    cards.append(freq_lines)

    # Emergency Contacts card
    if contacts:
        ec_lines = [[Paragraph('EMERGENCY CONTACTS', card_title)]]
        for c in contacts:
            phone_or_call = c.get('phone') or c.get('callsign') or c.get('freq') or ''
            ec_lines.append([Paragraph(f'{_esc(c["name"])}: {_esc(phone_or_call)}', card_body)])
        ec_lines.append([Paragraph(f'NOMAD -- {now}', footer_style)])
        cards.append(ec_lines)

    # Build cards as tables with borders
    for card_data in cards:
        card_table = Table(card_data, colWidths=[CARD_W - 12])
        card_table.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 1.5, colors.black),
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        elements.append(card_table)
        elements.append(Spacer(1, 8))

    if not elements:
        elements.append(Paragraph('No data available for wallet cards.', card_body))

    doc.build(elements)
    buf.seek(0)
    return Response(buf.read(), mimetype='application/pdf',
                   headers={'Content-Disposition': f'attachment; filename="NOMAD-Wallet-Cards-{datetime.now().strftime("%Y%m%d")}.pdf"'})


@print_routes_bp.route('/api/print/pdf/soi')
def api_print_pdf_soi():
    """Generate Signal Operating Instructions (SOI) as PDF."""
    rl = _pdf_setup()
    if rl is None:
        return jsonify({'error': 'reportlab not installed', 'hint': 'pip install reportlab'}), 500
    io, letter, inch = rl['io'], rl['letter'], rl['inch']
    ParagraphStyle, colors = rl['ParagraphStyle'], rl['colors']
    SimpleDocTemplate, Table, TableStyle = rl['SimpleDocTemplate'], rl['Table'], rl['TableStyle']
    Paragraph, Spacer = rl['Paragraph'], rl['Spacer']

    with db_session() as db:
        contacts = [dict(r) for r in db.execute("SELECT name, callsign, freq, role FROM contacts WHERE callsign != '' OR freq != '' ORDER BY name").fetchall()]
        freqs = [dict(r) for r in db.execute('SELECT freq, callsign, direction, message, signal_quality, created_at FROM comms_log ORDER BY created_at DESC LIMIT 30').fetchall()]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch,
                            leftMargin=0.6*inch, rightMargin=0.6*inch)
    mono = ParagraphStyle('Mono', fontName='Courier', fontSize=8, leading=10)
    title_style = ParagraphStyle('TitleMono', fontName='Courier-Bold', fontSize=16, leading=20, alignment=1, spaceAfter=8)
    subtitle_style = ParagraphStyle('SubMono', fontName='Courier', fontSize=10, alignment=1, spaceAfter=4, textColor=colors.grey)
    section_style = ParagraphStyle('SectionMono', fontName='Courier-Bold', fontSize=11, leading=14, spaceBefore=14, spaceAfter=6,
                                    borderWidth=1, borderColor=colors.black, borderPadding=3)

    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    node_name = _get_node_name()
    elements = []

    # Header
    elements.append(Paragraph('SIGNAL OPERATING INSTRUCTIONS', title_style))
    elements.append(Paragraph(f'Node: {_esc(node_name)} | Generated: {now}', subtitle_style))
    elements.append(Paragraph('OPERATIONAL SECURITY -- DO NOT LEAVE UNATTENDED', ParagraphStyle('Warn', fontName='Courier-Bold', fontSize=8, alignment=1, textColor=colors.red, spaceBefore=8, spaceAfter=16)))

    # Standard Emergency Frequencies
    elements.append(Paragraph('STANDARD EMERGENCY FREQUENCIES', section_style))
    std_data = [
        ['Service', 'Frequency', 'Notes'],
        ['FRS Ch 1', '462.5625 MHz', 'Family Radio primary'],
        ['FRS Ch 3', '462.6125 MHz', 'Neighborhood net'],
        ['GMRS Ch 1', '462.5625 MHz', 'Higher power (5W)'],
        ['MURS Ch 1', '151.820 MHz', 'No license required'],
        ['2m Call', '146.520 MHz', 'National calling freq'],
        ['70cm Call', '446.000 MHz', 'National calling freq'],
        ['HF 40m', '7.260 MHz', 'Emergency net'],
        ['Marine 16', '156.800 MHz', 'Distress/calling'],
        ['CB Ch 9', '27.065 MHz', 'Emergency channel'],
        ['CB Ch 19', '27.185 MHz', 'Highway/trucker'],
        ['NOAA WX', '162.550 MHz', 'Weather broadcast'],
    ]
    t = Table(std_data, repeatRows=1, colWidths=[1.8*inch, 1.5*inch, 3*inch])
    t.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,0), 'Courier-Bold'), ('FONTSIZE', (0,0), (-1,-1), 8),
        ('FONTNAME', (0,1), (-1,-1), 'Courier'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (-1,0), colors.Color(0.85, 0.85, 0.85)),
        ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    elements.append(t)

    # Team Call Signs
    elements.append(Paragraph('TEAM CALLSIGNS / OPERATORS', section_style))
    if contacts:
        t_data = [['Name', 'Callsign', 'Frequency', 'Role']]
        for c in contacts:
            t_data.append([c.get('name',''), c.get('callsign',''), c.get('freq',''), c.get('role','')])
        t = Table(t_data, repeatRows=1)
        t.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,0), 'Courier-Bold'), ('FONTSIZE', (0,0), (-1,-1), 8),
            ('FONTNAME', (0,1), (-1,-1), 'Courier'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BACKGROUND', (0,0), (-1,0), colors.Color(0.85, 0.85, 0.85)),
            ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph('No team contacts with callsigns registered.', mono))

    # Recent Communications Log
    elements.append(Paragraph('RECENT COMMUNICATIONS LOG', section_style))
    if freqs:
        t_data = [['Time', 'Freq', 'Callsign', 'Dir', 'Message', 'Signal']]
        for f in freqs:
            t_data.append([f.get('created_at',''), f.get('freq',''), f.get('callsign',''),
                          f.get('direction',''), (f.get('message','') or '')[:50], f.get('signal_quality','')])
        t = Table(t_data, repeatRows=1)
        t.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,0), 'Courier-Bold'), ('FONTSIZE', (0,0), (-1,-1), 7),
            ('FONTNAME', (0,1), (-1,-1), 'Courier'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BACKGROUND', (0,0), (-1,0), colors.Color(0.85, 0.85, 0.85)),
            ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph('No communications logged.', mono))

    # Radio Procedures
    elements.append(Paragraph('RADIO PROCEDURES', section_style))
    procedures = [
        'PROWORDS: Roger (understood), Wilco (will comply), Over (your turn), Out (end)',
        'PHONETIC: Alpha, Bravo, Charlie, Delta, Echo, Foxtrot, Golf, Hotel...',
        'NET CALL: "[Callsign] this is [Callsign], radio check, over"',
        'EMERGENCY: "MAYDAY MAYDAY MAYDAY, this is [Callsign], [situation], over"',
        'MEDEVAC 9-LINE: Location, Freq, # Patients, Equipment, # by type, Security, Marking, Nationality, CBRN',
    ]
    for proc in procedures:
        elements.append(Paragraph(proc, mono))

    elements.append(Spacer(1, 20))
    elements.append(Paragraph(f'End of SOI -- {now} -- NOMAD Field Desk ({_esc(node_name)})', subtitle_style))

    doc.build(elements)
    buf.seek(0)
    return Response(buf.read(), mimetype='application/pdf',
                   headers={'Content-Disposition': f'attachment; filename="NOMAD-SOI-{datetime.now().strftime("%Y%m%d")}.pdf"'})


# ─── Emergency Sheet ───────────────────────────────────────────────

@print_routes_bp.route('/api/emergency-sheet')
def api_emergency_sheet():
    """Generate a comprehensive printable emergency reference sheet."""
    with db_session() as db:

        # Gather all critical data
        contacts = [dict(r) for r in db.execute('SELECT * FROM contacts ORDER BY name LIMIT 10000').fetchall()]
        inventory = [dict(r) for r in db.execute('SELECT * FROM inventory ORDER BY category, name').fetchall()]
        burn_items = [dict(r) for r in db.execute('SELECT name, quantity, unit, daily_usage, category FROM inventory WHERE daily_usage > 0 ORDER BY (quantity/daily_usage)').fetchall()]
        patients = [dict(r) for r in db.execute('SELECT * FROM patients ORDER BY name LIMIT 10000').fetchall()]
        waypoints = [dict(r) for r in db.execute('SELECT * FROM waypoints ORDER BY category, name LIMIT 10000').fetchall()]
        checklists = [dict(r) for r in db.execute('SELECT name, items FROM checklists ORDER BY name').fetchall()]
        sit_raw = db.execute("SELECT value FROM settings WHERE key = 'sit_board'").fetchone()
        sit = _safe_json_value(sit_raw['value'] if sit_raw else None, {})
        wx = [dict(r) for r in db.execute('SELECT * FROM weather_log ORDER BY created_at DESC LIMIT 5').fetchall()]

    sit_labels = {'green': 'GOOD', 'yellow': 'CAUTION', 'orange': 'CONCERN', 'red': 'CRITICAL'}
    sit_colors = {'green': '#2e7d32', 'yellow': '#f9a825', 'orange': '#ef6c00', 'red': '#c62828'}
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    sit_html = '<div class="doc-empty">Situation board is not configured yet.</div>'
    if sit:
        sit_html = '<div class="doc-chip-list">'
        for domain, level in sit.items():
            color = sit_colors.get(level, '#64748b')
            sit_html += (
                f'<span class="doc-chip" style="background:{color};border-color:{color};color:#fff;">'
                f'{_esc(domain.upper())}: {sit_labels.get(level, level.upper())}'
                '</span>'
            )
        sit_html += '</div>'

    contacts_html = '<div class="doc-empty">No contacts registered.</div>'
    if contacts:
        contacts_html = '<div class="doc-table-shell"><table><thead><tr><th>Name</th><th>Role</th><th>Phone</th><th>Callsign</th><th>Radio Freq</th><th>Blood</th><th>Rally Point</th></tr></thead><tbody>'
        for c in contacts:
            contacts_html += (
                f"<tr><td class=\"doc-strong\">{_esc(c.get('name',''))}</td><td>{_esc(c.get('role','')) or '-'}</td>"
                f"<td>{_esc(c.get('phone','')) or '-'}</td><td>{_esc(c.get('callsign','')) or '-'}</td>"
                f"<td>{_esc(c.get('freq','')) or '-'}</td><td>{_esc(c.get('blood_type','')) or '-'}</td>"
                f"<td>{_esc(c.get('rally_point','')) or '-'}</td></tr>"
            )
        contacts_html += '</tbody></table></div>'

    patients_html = '<div class="doc-empty">No patient profiles are recorded.</div>'
    if patients:
        patients_html = '<div class="doc-table-shell"><table><thead><tr><th>Name</th><th>Age</th><th>Weight</th><th>Blood</th><th>Allergies</th><th>Medications</th><th>Conditions</th></tr></thead><tbody>'
        for p in patients:
            try:
                allergies = json.loads(p.get('allergies') or '[]')
            except (json.JSONDecodeError, TypeError):
                allergies = []
            try:
                meds = json.loads(p.get('medications') or '[]')
            except (json.JSONDecodeError, TypeError):
                meds = []
            try:
                conds = json.loads(p.get('conditions') or '[]')
            except (json.JSONDecodeError, TypeError):
                conds = []
            allergy_str = ', '.join(allergies) if allergies else 'NKDA'
            patients_html += (
                f"<tr><td class=\"doc-strong\">{_esc(p.get('name',''))}</td><td>{p.get('age','') or '-'}</td>"
                f"<td>{p.get('weight_kg','') or '-'}{' kg' if p.get('weight_kg') else ''}</td><td>{_esc(p.get('blood_type','')) or '-'}</td>"
                f"<td class=\"doc-alert\">{_esc(allergy_str)}</td><td>{_esc(', '.join(meds)) or '-'}</td><td>{_esc(', '.join(conds)) or '-'}</td></tr>"
            )
        patients_html += '</tbody></table></div>'

    supply_html = '<div class="doc-empty">No inventory burn-rate data is available.</div>'
    if burn_items:
        supply_html = '<div class="doc-table-shell"><table><thead><tr><th>Item</th><th>Category</th><th>Quantity</th><th>Daily Use</th><th>Days Left</th></tr></thead><tbody>'
        for b in burn_items[:15]:
            days = round(b['quantity'] / b['daily_usage'], 1) if b['daily_usage'] > 0 else 999
            marker = ' class="doc-alert"' if days < 7 else ''
            supply_html += (
                f"<tr><td class=\"doc-strong\">{_esc(b['name'])}</td><td>{_esc(b['category'])}</td>"
                f"<td>{b['quantity']} {_esc(b.get('unit',''))}</td><td>{b['daily_usage']}/day</td><td{marker}>{days}d</td></tr>"
            )
        supply_html += '</tbody></table></div>'

    cats = {}
    for item in inventory:
        cat = item.get('category', 'other')
        if cat not in cats:
            cats[cat] = {'count': 0, 'items': []}
        cats[cat]['count'] += 1
        cats[cat]['items'].append(item)
    inventory_summary_html = '<div class="doc-empty">No categorized inventory summary available.</div>'
    if cats:
        inventory_summary_html = '<div class="doc-chip-list">' + ''.join(
            f'<span class="doc-chip">{_esc(cat)}: {info["count"]}</span>'
            for cat, info in sorted(cats.items())
        ) + '</div>'

    waypoints_html = '<div class="doc-empty">No waypoints or rally points have been saved.</div>'
    if waypoints:
        waypoints_html = '<div class="doc-table-shell"><table><thead><tr><th>Name</th><th>Category</th><th>Lat</th><th>Lng</th><th>Notes</th></tr></thead><tbody>'
        for w in waypoints:
            waypoints_html += (
                f"<tr><td class=\"doc-strong\">{_esc(w.get('name',''))}</td><td>{_esc(w.get('category','')) or '-'}</td>"
                f"<td>{w.get('lat','') or '-'}</td><td>{w.get('lng','') or '-'}</td><td>{_esc(w.get('notes','')) or '-'}</td></tr>"
            )
        waypoints_html += '</tbody></table></div>'

    checklist_html = '<div class="doc-empty">No checklists are available.</div>'
    if checklists:
        checklist_html = '<div class="doc-table-shell"><table><thead><tr><th>Checklist</th><th>Progress</th></tr></thead><tbody>'
        for cl in checklists:
            items = json.loads(cl.get('items') or '[]')
            total = len(items)
            checked = sum(1 for i in items if isinstance(i, dict) and i.get('checked'))
            pct = round(checked / total * 100) if total > 0 else 0
            checklist_html += f"<tr><td class=\"doc-strong\">{_esc(cl['name'])}</td><td>{checked}/{total} ({pct}%)</td></tr>"
        checklist_html += '</tbody></table></div>'

    weather_html = '<div class="doc-empty">No recent weather readings are on file.</div>'
    if wx:
        weather_html = '<div class="doc-table-shell"><table><thead><tr><th>Time</th><th>Pressure</th><th>Temp</th><th>Wind</th><th>Clouds</th></tr></thead><tbody>'
        for w in wx:
            wind_text = f"{w.get('wind_dir','') or '-'} {w.get('wind_speed','') or ''}".strip()
            weather_html += (
                f"<tr><td>{_esc(w.get('created_at','')) or '-'}</td><td>{w.get('pressure_hpa','') or '-'}</td>"
                f"<td>{w.get('temp_f','') or '-'}</td><td>{_esc(wind_text) or '-'}</td><td>{_esc(w.get('clouds','')) or '-'}</td></tr>"
            )
        weather_html += '</tbody></table></div>'

    tasks_html = ''
    try:
        with db_session() as db2:
            tasks = [dict(r) for r in db2.execute("SELECT name, category, next_due, assigned_to FROM scheduled_tasks WHERE next_due IS NOT NULL ORDER BY next_due LIMIT 15").fetchall()]
        if tasks:
            task_table = '<div class="doc-table-shell"><table><thead><tr><th>Task</th><th>Category</th><th>Due</th><th>Assigned</th></tr></thead><tbody>'
            for t in tasks:
                task_table += (
                    f"<tr><td class=\"doc-strong\">{_esc(t.get('name',''))}</td><td>{_esc(t.get('category','')) or '-'}</td>"
                    f"<td>{_esc(t.get('next_due','')) or '-'}</td><td>{_esc(t.get('assigned_to','') or 'Unassigned')}</td></tr>"
                )
            task_table += '</tbody></table></div>'
            tasks_html = f'''<section class="doc-section">
  <h2 class="doc-section-title">Scheduled Tasks</h2>
  {task_table}
</section>'''
    except Exception:
        pass

    notes_html = ''
    try:
        with db_session() as db3:
            mem_row = db3.execute("SELECT value FROM settings WHERE key = 'ai_memory'").fetchone()
        if mem_row and mem_row['value']:
            memories = _safe_json_value(mem_row['value'], [])
            if not isinstance(memories, list):
                memories = []
            facts = []
            for memory in memories:
                fact = memory.get('fact') if isinstance(memory, dict) else memory
                fact = str(fact or '').strip()
                if fact:
                    facts.append(fact)
            if facts:
                note_list = ''.join(
                    f'<li>{_esc(fact)}</li>'
                    for fact in facts
                )
                notes_html = f'''<section class="doc-section">
  <h2 class="doc-section-title">Operator Notes</h2>
  <div class="doc-note-box"><ul style="margin:0;padding-left:18px;">{note_list}</ul></div>
</section>'''
    except Exception:
        pass

    body = f'''<section class="doc-section">
  <h2 class="doc-section-title">Situation Status</h2>
  {sit_html}
</section>
<section class="doc-section">
  <div class="doc-grid-2">
    <div class="doc-panel doc-panel-strong">
      <h2 class="doc-section-title">Emergency Contacts</h2>
      {contacts_html}
    </div>
    <div class="doc-panel doc-panel-strong">
      <h2 class="doc-section-title">Medical Profiles</h2>
      {patients_html}
    </div>
  </div>
</section>
<section class="doc-section">
  <div class="doc-grid-2">
    <div class="doc-panel">
      <h2 class="doc-section-title">Supply Status</h2>
      {supply_html}
      <div style="margin-top:12px;">{inventory_summary_html}</div>
    </div>
    <div class="doc-panel">
      <h2 class="doc-section-title">Waypoints &amp; Rally Points</h2>
      {waypoints_html}
    </div>
  </div>
</section>
<section class="doc-section">
  <div class="doc-grid-2">
    <div class="doc-panel">
      <h2 class="doc-section-title">Checklist Status</h2>
      {checklist_html}
    </div>
    <div class="doc-panel">
      <h2 class="doc-section-title">Recent Weather</h2>
      {weather_html}
    </div>
  </div>
</section>
{tasks_html}
{notes_html}
<section class="doc-section">
  <h2 class="doc-section-title">Quick Reference</h2>
  <div class="doc-grid-2">
    <div class="doc-panel"><span class="doc-strong">Water</span><div style="margin-top:8px;">1 gal/person/day. Bleach: 8 drops/gal for clear water, 16 drops/gal for cloudy water. Wait 30 minutes.</div></div>
    <div class="doc-panel"><span class="doc-strong">Food</span><div style="margin-top:8px;">Target 2,000 cal/person/day. Eat perishables first, then frozen, then shelf-stable stores.</div></div>
    <div class="doc-panel"><span class="doc-strong">Radio</span><div style="margin-top:8px;">FRS Ch 1 for rally, Ch 3 for emergency, GMRS Ch 20 for emergency, HAM 146.520 MHz for calling.</div></div>
    <div class="doc-panel"><span class="doc-strong">Medical</span><div style="margin-top:8px;">Use direct pressure for bleeding. Apply a tourniquet for uncontrolled limb bleeding and note the application time.</div></div>
  </div>
</section>
<section class="doc-section">
  <div class="doc-footer">
    <span>Emergency binder sheet for fast cross-module reference in the field or at the command post.</span>
    <span>NOMAD Field Desk Emergency Binder</span>
  </div>
</section>'''

    html = render_print_document(
        'Emergency Reference Sheet',
        'Comprehensive single-document snapshot covering contacts, medical status, supply burn, rally points, tasks, and quick-reference guidance.',
        body,
        eyebrow='NOMAD Field Desk Emergency Binder',
        meta_items=[f'Generated {now}', 'Keep in go-bag', 'Refresh monthly'],
        stat_items=[
            ('Contacts', len(contacts)),
            ('Patients', len(patients)),
            ('Inventory', len(inventory)),
            ('Waypoints', len(waypoints)),
            ('Checklists', len(checklists)),
            ('Weather Logs', len(wx)),
        ],
        accent_start='#12324a',
        accent_end='#3b6a57',
        max_width='1160px',
    )

    return html
