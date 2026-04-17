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
    safe_json_list as _safe_json_list,
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


def _join_safe_list(value, empty=''):
    items = [str(item).strip() for item in _safe_json_list(value, []) if str(item or '').strip()]
    return ', '.join(items) if items else empty


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


# ─── Shared data fetchers ─────────────────────────────────────────
#
# Historically, every print route re-implemented its own contact query,
# burn-rate query, low-stock query, etc. The originals used different
# LIMITs (sometimes 5000, sometimes 10000), slightly different column
# lists, and subtly different filters. Extracting the queries once
# guarantees that "the operations binder's contact table" and "the
# emergency sheet's contact table" see the same rows in the same order.

def _fetch_contacts(db, limit=10000):
    """All contacts ordered by name. One source of truth for every route."""
    return db.execute(
        'SELECT * FROM contacts ORDER BY name LIMIT ?',
        (limit,),
    ).fetchall()


def _fetch_burn_summary(db, limit=5000):
    """Compute min-days-left per category from inventory with daily_usage > 0.

    Returns a ``dict[category] -> days`` where ``days`` is the smallest
    (quantity / daily_usage) value in that category — the resource that
    will run out first, which is the tactically useful number.
    """
    burn_rows = db.execute(
        'SELECT category, name, quantity, unit, daily_usage FROM inventory '
        'WHERE daily_usage > 0 ORDER BY category LIMIT ?',
        (limit,),
    ).fetchall()
    burn = {}
    for r in burn_rows:
        cat = r['category']
        days = round(r['quantity'] / r['daily_usage'], 1) if r['daily_usage'] > 0 else 999
        if cat not in burn or days < burn[cat]:
            burn[cat] = days
    return burn


def _fetch_low_stock(db, limit=5000):
    """Inventory items currently at or below their min_quantity threshold."""
    return db.execute(
        'SELECT name, quantity, unit, category FROM inventory '
        'WHERE quantity <= min_quantity AND min_quantity > 0 LIMIT ?',
        (limit,),
    ).fetchall()


def _fetch_expiring(db, within_days=30, limit=5000):
    """Inventory items expiring within ``within_days`` days, oldest first."""
    threshold = (datetime.now() + timedelta(days=within_days)).strftime('%Y-%m-%d')
    return db.execute(
        "SELECT name, expiration, category FROM inventory "
        "WHERE expiration != '' AND expiration <= ? ORDER BY expiration LIMIT ?",
        (threshold, limit),
    ).fetchall()


# ─── Shared HTML renderers ────────────────────────────────────────
#
# Each renderer returns a fragment of print-document HTML. They all use
# the existing `.doc-*` CSS classes from `print_templates.py` so the
# visual output is identical to the hand-rolled copies that used to
# live inline in every route, they just aren't copy-pasted 9 times.

def _render_empty(message):
    """Consistent empty-state panel for a print section."""
    return f'<div class="doc-empty">{_esc(message)}</div>'


def _render_contacts_table(contacts, include_radio=True, empty_msg='No emergency contacts are available yet.'):
    """Render a contacts list as a print table.

    ``include_radio=True`` adds callsign / frequency / blood / rally columns
    (used by the full emergency card). ``include_radio=False`` returns a
    compact name + role + phone table for wallet cards and similar.
    """
    if not contacts:
        return _render_empty(empty_msg)
    if include_radio:
        head = ('<thead><tr><th>Name</th><th>Role</th><th>Callsign</th>'
                '<th>Phone</th><th>Freq</th><th>Blood</th><th>Rally Point</th></tr></thead>')
        rows = []
        for c in contacts:
            rows.append(
                f'<tr><td class="doc-strong">{_esc(c["name"])}</td>'
                f'<td>{_esc(c["role"])}</td>'
                f'<td>{_esc(c["callsign"]) or "-"}</td>'
                f'<td>{_esc(c["phone"]) or "-"}</td>'
                f'<td>{_esc(c["freq"]) or "-"}</td>'
                f'<td>{_esc(c["blood_type"]) or "-"}</td>'
                f'<td>{_esc(c["rally_point"]) or "-"}</td></tr>'
            )
    else:
        head = '<thead><tr><th>Name</th><th>Callsign</th><th>Phone</th></tr></thead>'
        rows = []
        for c in contacts:
            rows.append(
                f'<tr><td class="doc-strong">{_esc(c["name"])}</td>'
                f'<td>{_esc(c["callsign"] or "-")}</td>'
                f'<td>{_esc(c["phone"] or "-")}</td></tr>'
            )
    return '<div class="doc-table-shell"><table>' + head + '<tbody>' + ''.join(rows) + '</tbody></table></div>'


def _render_burn_table(burn, empty_msg='No burn-rate tracked inventory is available.'):
    """Render the output of :func:`_fetch_burn_summary` as a print table.

    Categories with fewer than 7 days left are flagged with the
    ``doc-alert`` class so the printed copy can highlight them in red.
    """
    if not burn:
        return _render_empty(empty_msg)
    html = '<div class="doc-table-shell"><table><thead><tr><th>Resource</th><th>Days Left</th></tr></thead><tbody>'
    for cat, days in sorted(burn.items()):
        marker = ' class="doc-alert"' if days < 7 else ''
        html += f'<tr><td class="doc-strong">{_esc(cat.upper())}</td><td{marker}>{days}</td></tr>'
    html += '</tbody></table></div>'
    return html


def _render_low_stock_table(low, empty_msg='No low-stock alerts at the moment.'):
    """Render a low-stock inventory list as a print table."""
    if not low:
        return _render_empty(empty_msg)
    html = '<div class="doc-table-shell"><table><thead><tr><th>Item</th><th>Qty</th><th>Category</th></tr></thead><tbody>'
    for r in low:
        html += (
            f'<tr><td class="doc-alert">{_esc(r["name"])}</td>'
            f'<td>{r["quantity"]} {_esc(r["unit"])}</td>'
            f'<td>{_esc(r["category"])}</td></tr>'
        )
    html += '</tbody></table></div>'
    return html


def _render_expiring_table(expiring, empty_msg='No items are expiring in the next 30 days.'):
    """Render an expiring-items list as a print table."""
    if not expiring:
        return _render_empty(empty_msg)
    html = '<div class="doc-table-shell"><table><thead><tr><th>Item</th><th>Expires</th><th>Category</th></tr></thead><tbody>'
    for r in expiring:
        html += (
            f'<tr><td class="doc-strong">{_esc(r["name"])}</td>'
            f'<td>{_esc(r["expiration"])}</td>'
            f'<td>{_esc(r["category"])}</td></tr>'
        )
    html += '</tbody></table></div>'
    return html


#: Shared standard-frequency reference used by the freq card, the
#: emergency card, the operations binder, and the wallet cards. Kept
#: as a module constant so every print document quotes the same text.
STANDARD_FREQUENCIES = [
    ('FRS Rally', 'Ch 1 / 462.5625 MHz'),
    ('FRS Emergency', 'Ch 3 / 462.6125 MHz'),
    ('GMRS Emergency', 'Ch 20 / 462.6750 MHz'),
    ('CB Emergency', 'Ch 9 / 27.065 MHz'),
    ('CB Highway', 'Ch 19 / 27.185 MHz'),
    ('2m Calling', '146.520 MHz'),
    ('2m Emergency', '146.550 MHz'),
    ('NOAA Weather', '162.400 - 162.550 MHz'),
]


def _render_standard_frequencies_table():
    """Render the shared STANDARD_FREQUENCIES constant as a print table."""
    html = '<div class="doc-table-shell"><table><thead><tr><th>Use</th><th>Freq / Ch</th></tr></thead><tbody>'
    for label, freq in STANDARD_FREQUENCIES:
        html += f'<tr><td class="doc-strong">{_esc(label)}</td><td>{_esc(freq)}</td></tr>'
    html += '</tbody></table></div>'
    return html


def _render_allergy_chips(allergies):
    """Allergy chip list with NKDA fallback. Identical across every card that shows
    allergies so every printed copy speaks the same language (No Known Drug
    Allergies) rather than six near-duplicate strings."""
    if not allergies:
        return '<span class="doc-chip doc-chip-muted">NKDA</span>'
    return ''.join(f'<span class="doc-chip doc-chip-alert">{_esc(str(a))}</span>' for a in allergies)


def _render_medication_chips(medications, limit=None):
    """Medication chip list with "None recorded" fallback. ``limit`` optionally
    truncates — wallet cards cap at 8 to fit the physical card; binders don't."""
    if not medications:
        return '<span class="doc-chip doc-chip-muted">None recorded</span>'
    items = medications[:limit] if limit else medications
    return ''.join(f'<span class="doc-chip">{_esc(str(m))}</span>' for m in items)


def _render_condition_chips(conditions):
    """Condition chip list with "None recorded" fallback."""
    if not conditions:
        return '<span class="doc-chip doc-chip-muted">None recorded</span>'
    return ''.join(f'<span class="doc-chip">{_esc(str(c))}</span>' for c in conditions)


# ─── Preparedness Print ───────────────────────────────────────────

@print_routes_bp.route('/api/preparedness/print')
def api_preparedness_print():
    """Generate printable emergency summary page."""
    with db_session() as db:
        contacts = _fetch_contacts(db)
        settings = {r['key']: r['value'] for r in db.execute('SELECT key, value FROM settings').fetchall()}
        burn = _fetch_burn_summary(db)
        low = _fetch_low_stock(db)
        expiring = _fetch_expiring(db, within_days=30)

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

    contacts_html = _render_contacts_table(contacts, include_radio=True)
    supply_html = _render_burn_table(burn)
    low_html = _render_low_stock_table(low)
    expiring_html = _render_expiring_table(expiring)
    freq_html = _render_standard_frequencies_table()

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
      {freq_html}
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
            items = _safe_json_list(c['items'], [])
            total = len(items)
            checked = sum(1 for i in items if isinstance(i, dict) and i.get('checked'))
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

    contacts_html = _render_contacts_table(
        contacts,
        include_radio=False,
        empty_msg='No radio contacts with a callsign or phone are on file.',
    )

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
        allergies = _safe_json_list(record.get('allergies'), [])
        conditions = _safe_json_list(record.get('conditions'), [])
        medications = _safe_json_list(record.get('medications'), [])
        if allergies:
            allergy_count += 1
        if medications:
            medication_count += 1
        allergy_html = _render_allergy_chips(allergies)
        conditions_html = _render_condition_chips(conditions)
        meds_html = _render_medication_chips(medications)
        card_grid += f'''<div class="doc-panel doc-panel-strong">
  <h2 class="doc-section-title">Medical Card</h2>
  <div class="doc-note-box doc-checkbox-cell">
    <div class="doc-strong doc-text-lg">{_esc(record["name"])}</div>
    <div class="doc-mt-10 doc-chip-list">
      <span class="doc-chip">DOB: {_esc(str(record.get("dob","\u2014")))}</span>
      <span class="doc-chip">Blood: {_esc(str(record.get("blood_type","\u2014")))}</span>
      <span class="doc-chip">Weight: {_esc(str(record.get("weight_kg","?")))} kg</span>
    </div>
    <div class="doc-mt-12">
      <div class="doc-section-title doc-mb-8">Allergies</div>
      <div class="doc-chip-list">{allergy_html}</div>
    </div>
    <div class="doc-mt-12">
      <div class="doc-section-title doc-mb-8">Conditions</div>
      <div class="doc-chip-list">{conditions_html}</div>
    </div>
    <div class="doc-mt-12">
      <div class="doc-section-title doc-mb-8">Medications</div>
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
            allergies = _join_safe_list(p.get('allergies'))
            conditions = _join_safe_list(p.get('conditions'))
            medications = _join_safe_list(p.get('medications'))
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
            cl_items = _safe_json_list(cl.get('items'), [])
            for it in cl_items:
                label = it.get('text', it) if isinstance(it, dict) else str(it)
                checked = it.get('checked', False) if isinstance(it, dict) else False
                mark = '[X]' if checked else '[ ]'
                elements.append(Paragraph(f'    {mark} {_esc(str(label))}', mono))
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
        allergies = _join_safe_list(p.get('allergies'))
        meds = _join_safe_list(p.get('medications'))
        conditions_str = _join_safe_list(p.get('conditions'))

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

    # Refactored to use shared _render_contacts_table helper (v7.0.9).
    # Column order is now standardised across every print document — Name,
    # Role, Callsign, Phone, Freq, Blood, Rally Point — so the Emergency
    # Sheet and Preparedness Print match visually instead of each carrying
    # its own slightly-different column layout.
    contacts_html = _render_contacts_table(
        contacts, include_radio=True, empty_msg='No contacts registered.',
    )

    patients_html = '<div class="doc-empty">No patient profiles are recorded.</div>'
    if patients:
        patients_html = '<div class="doc-table-shell"><table><thead><tr><th>Name</th><th>Age</th><th>Weight</th><th>Blood</th><th>Allergies</th><th>Medications</th><th>Conditions</th></tr></thead><tbody>'
        for p in patients:
            allergies = _safe_json_list(p.get('allergies'), [])
            meds = _safe_json_list(p.get('medications'), [])
            conds = _safe_json_list(p.get('conditions'), [])
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
            items = _safe_json_list(cl.get('items'), [])
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
  <div class="doc-note-box"><ul class="doc-list-flat">{note_list}</ul></div>
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
      <div class="doc-mt-12">{inventory_summary_html}</div>
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
    <div class="doc-panel"><span class="doc-strong">Water</span><div class="doc-mt-8">1 gal/person/day. Bleach: 8 drops/gal for clear water, 16 drops/gal for cloudy water. Wait 30 minutes.</div></div>
    <div class="doc-panel"><span class="doc-strong">Food</span><div class="doc-mt-8">Target 2,000 cal/person/day. Eat perishables first, then frozen, then shelf-stable stores.</div></div>
    <div class="doc-panel"><span class="doc-strong">Radio</span><div class="doc-mt-8">FRS Ch 1 for rally, Ch 3 for emergency, GMRS Ch 20 for emergency, HAM 146.520 MHz for calling.</div></div>
    <div class="doc-panel"><span class="doc-strong">Medical</span><div class="doc-mt-8">Use direct pressure for bleeding. Apply a tourniquet for uncontrolled limb bleeding and note the application time.</div></div>
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


# ─── Helpers (moved from routes_advanced) ────────────────────────

def _is_expired_date(value):
    """Return True when a YYYY-MM-DD date is in the past."""
    if not value:
        return False
    try:
        return datetime.strptime(value, '%Y-%m-%d').date() < datetime.now().date()
    except (TypeError, ValueError):
        return False


# ─── Operations Binder ───────────────────────────────────────────

@print_routes_bp.route('/api/print/operations-binder')
def api_print_operations_binder():
    """Generate a comprehensive printable operations binder."""
    with db_session() as db:
        # Node identity
        node_name_row = db.execute("SELECT value FROM settings WHERE key = 'node_name'").fetchone()
        node_name = (node_name_row['value'] if node_name_row and node_name_row['value'] else platform.node()) or 'NOMAD Node'

        # Emergency contacts
        contacts = [dict(r) for r in db.execute(
            "SELECT name, callsign, role, phone, email, freq, blood_type, rally_point "
            "FROM contacts ORDER BY name LIMIT 500").fetchall()]

        # Frequencies
        freqs = [dict(r) for r in db.execute(
            'SELECT frequency, mode, service, description FROM freq_database ORDER BY frequency LIMIT 500'
        ).fetchall()]

        # Patients
        patients = [dict(r) for r in db.execute(
            'SELECT * FROM patients ORDER BY name LIMIT 200').fetchall()]

        # Inventory by category
        inventory = [dict(r) for r in db.execute(
            'SELECT name, category, quantity, unit, location, expiration '
            'FROM inventory ORDER BY category, name LIMIT 2000').fetchall()]

        # Active checklists
        checklists = [dict(r) for r in db.execute(
            'SELECT name, items, updated_at FROM checklists ORDER BY name LIMIT 200').fetchall()]

        # Waypoints
        waypoints = [dict(r) for r in db.execute(
            'SELECT name, lat, lng, category, notes FROM waypoints ORDER BY category, name LIMIT 500'
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

    esc = _esc
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
            allergies = _safe_json_list(p.get('allergies'), [])
            conditions = _safe_json_list(p.get('conditions'), [])
            medications = _safe_json_list(p.get('medications'), [])
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
  <div class="doc-mt-12 doc-chip-list">{allergy_html}</div>
  <div class="doc-mt-12 doc-chip-list">{condition_html}</div>
  <div class="doc-mt-12 doc-chip-list">{medication_html}</div>
  <div class="doc-mt-12 doc-note-box">{esc(str(p.get("notes") or "No additional notes recorded."))}</div>
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
            items = _safe_json_list(cl.get('items'), [])
            panel = f'<div class="doc-panel"><h2 class="doc-section-title">{esc(cl["name"])}</h2>'
            if items:
                panel += '<div class="doc-table-shell"><table><thead><tr><th class="doc-cell-fixed-60">Done</th><th>Task</th></tr></thead><tbody>'
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
            waypoint_html += '<div class="doc-mt-12 doc-note-box">Rally points are present. Print the dedicated map view from the Maps workspace for terrain detail and route overlays.</div>'

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
<section class="doc-section doc-page-break">
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
<section class="doc-section doc-page-break">
  <h2 class="doc-section-title">3. Medical Patient Cards</h2>
  {patient_cards_html}
</section>
<section class="doc-section doc-page-break">
  <h2 class="doc-section-title">4. Inventory Summary</h2>
  {inventory_cards}
</section>
<section class="doc-section doc-page-break">
  <h2 class="doc-section-title">5. Active Checklists</h2>
  {checklist_cards}
</section>
<section class="doc-section doc-page-break">
  <h2 class="doc-section-title">6. Waypoints and Rally Points</h2>
  {waypoint_html}
</section>
<section class="doc-section doc-page-break">
  <h2 class="doc-section-title">7. Emergency Procedures</h2>
  {procedure_html}
</section>
<section class="doc-section doc-page-break">
  <h2 class="doc-section-title">8. Family Emergency Plan</h2>
  {family_plan_html}
</section>
<section class="doc-section">
  <div class="doc-note-box doc-panel-alert">
    <div class="doc-strong doc-eyebrow-text">Confidential Handling</div>
    <div class="doc-mt-6">Protect this binder accordingly and replace printed copies when the plan or roster changes.</div>
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

@print_routes_bp.route('/api/print/wallet-cards')
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
            medications = _safe_json_list(self_patient.get('medications'), [])
            allergies = _safe_json_list(self_patient.get('allergies'), [])

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

    esc = _esc
    now = datetime.now().strftime('%Y-%m-%d')
    patient_name = ''
    if self_patient:
        patient_name = self_patient['name']
    elif self_contact:
        patient_name = self_contact['name']
    contact_list_html = ''.join(
        f'<div class="doc-mt-6"><span class="doc-strong">{i + 1}.</span> {esc(c["name"])}'
        f' ({esc(c.get("role","") or "Contact")}) - {esc(c["phone"])}</div>'
        for i, c in enumerate(ice_contacts[:3])
    ) or '<div class="doc-empty">No emergency contacts are on file.</div>'

    medication_html = _render_medication_chips(medications, limit=8)
    allergy_html = _render_allergy_chips(allergies)

    rally_html = '<div class="doc-empty">No rally points are configured.</div>'
    if rally_points:
        rally_html = '<div class="doc-table-shell"><table><thead><tr><th>Point</th><th>Lat</th><th>Lng</th></tr></thead><tbody>'
        for rp in rally_points:
            lat_str = f'{rp["lat"]:.5f}' if rp["lat"] is not None else 'N/A'
            lng_str = f'{rp["lng"]:.5f}' if rp["lng"] is not None else 'N/A'
            rally_html += f'<tr><td class="doc-strong">{esc(rp["name"])}</td><td>{lat_str}</td><td>{lng_str}</td></tr>'
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
      <div class="doc-note-box doc-checkbox-cell">
        <div class="doc-strong doc-text-lg">{esc(patient_name or "Unassigned")}</div>
        <div class="doc-mt-10 doc-chip-list">
          <span class="doc-chip">Blood: {esc(blood_type or "?")}</span>
          <span class="doc-chip">Allergies</span>
        </div>
        <div class="doc-mt-10 doc-chip-list">{allergy_html}</div>
        <div class="doc-mt-12">
          <div class="doc-section-title" style="margin-bottom:6px;">Emergency Contacts</div>
          {contact_list_html}
        </div>
      </div>
    </div>
    <div class="doc-panel doc-panel-strong">
      <h2 class="doc-section-title">Blood Type Card</h2>
      <div class="doc-note-box" style="background:#fff;border-style:solid;text-align:center;">
        <div style="font-size:44px;line-height:1;font-weight:800;color:#7a1520;">{esc(blood_type or "?")}</div>
        <div class="doc-mt-12 doc-strong">{esc(patient_name or "Name pending")}</div>
        <div class="doc-chip-list" style="margin-top:10px;justify-content:center;">{allergy_html}</div>
      </div>
    </div>
    <div class="doc-panel doc-panel-strong">
      <h2 class="doc-section-title">Medication Card</h2>
      <div class="doc-note-box doc-checkbox-cell">
        <div class="doc-strong">Patient: {esc(patient_name or "Unassigned")}</div>
        <div class="doc-mt-12 doc-chip-list">{medication_html}</div>
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

@print_routes_bp.route('/api/print/soi')
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
            'FROM freq_database ORDER BY frequency LIMIT 500').fetchall()]

        # Radio profiles
        profiles = [dict(r) for r in db.execute(
            'SELECT radio_model, name, channels FROM radio_profiles ORDER BY name LIMIT 100').fetchall()]

        # Contacts with callsigns
        contacts = [dict(r) for r in db.execute(
            "SELECT name, callsign, role, freq FROM contacts "
            "WHERE callsign != '' OR freq != '' ORDER BY callsign, name LIMIT 500").fetchall()]

    esc = _esc
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
            channels = _safe_json_list(prof.get('channels'), [])
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
  <div class="doc-note-box doc-panel-alert">
    <div class="doc-strong doc-eyebrow-text">Restricted</div>
    <div class="doc-mt-6">Carry only as needed. Destroy when compromised, superseded, or no longer operationally relevant.</div>
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
      <div class="doc-mt-10 doc-note-box">All times are local. Modify as needed and monitor the primary net continuously when conditions warrant it.</div>
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

@print_routes_bp.route('/api/print/medical-flipbook')
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
<div class="doc-signature-box">
<!-- Blank space for handwritten notes -->
</div>

<div class="footer doc-mt-16">
<strong>NOMAD Field Desk</strong> — Offline Medical Reference Flipbook<br>
''' + f'Generated {__import__("time").strftime("%Y-%m-%d %H:%M")}' + '''<br>
<em>This is a reference guide, not a substitute for medical training. Seek professional care when available.</em>
</div>
</div>

</body></html>'''
    return Response(html, mimetype='text/html')
