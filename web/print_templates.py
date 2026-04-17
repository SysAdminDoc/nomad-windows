"""Shared print/export document templates for framed app reports."""

from html import escape as _escape


def render_print_document(
    title,
    subtitle,
    body_html,
    *,
    eyebrow='NOMAD Field Desk',
    meta_items=None,
    stat_items=None,
    accent_start='#10263d',
    accent_end='#255777',
    max_width='980px',
    page_size='letter',
    landscape=False,
):
    """Render a polished standalone HTML document used by iframe print views."""
    meta_html = ''.join(
        f'<span class="doc-meta-chip">{_escape(str(item))}</span>'
        for item in (meta_items or [])
        if item not in (None, '')
    )
    stats_html = ''
    if stat_items:
        stats = []
        for label, value in stat_items:
            stats.append(
                '<div class="doc-stat">'
                f'<div class="doc-stat-label">{_escape(str(label))}</div>'
                f'<div class="doc-stat-value">{_escape(str(value))}</div>'
                '</div>'
            )
        stats_html = f'<div class="doc-stats">{"".join(stats)}</div>'

    orientation = 'landscape' if landscape else 'portrait'
    return f'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>{_escape(str(title))}</title>
<style>
:root {{ color-scheme: light; }}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  padding: 20px;
  background: #edf2f7;
  color: #142132;
  font-family: 'Segoe UI', sans-serif;
  font-size: 12px;
  line-height: 1.5;
}}
.doc-shell {{
  max-width: {max_width};
  margin: 0 auto;
  background: #ffffff;
  border: 1px solid #d7e0ea;
  border-radius: 24px;
  overflow: hidden;
  box-shadow: 0 24px 58px rgba(15, 23, 42, 0.12);
}}
.doc-header {{
  padding: 22px 26px;
  background: linear-gradient(155deg, {accent_start} 0%, {accent_end} 100%);
  color: #f6fbff;
}}
.doc-eyebrow {{
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  opacity: 0.76;
}}
.doc-title-row {{
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-end;
  margin-top: 10px;
}}
.doc-title {{
  margin: 0;
  font-size: 31px;
  line-height: 1.06;
  letter-spacing: -0.03em;
}}
.doc-subtitle {{
  margin-top: 8px;
  max-width: 42rem;
  font-size: 13px;
  color: rgba(240, 248, 255, 0.82);
}}
.doc-meta {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}}
.doc-meta-chip {{
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 7px 12px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 999px;
  background: rgba(9, 17, 27, 0.18);
  color: rgba(246, 251, 255, 0.9);
  font-size: 11px;
}}
.doc-stats {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px;
  margin-top: 20px;
}}
.doc-stat {{
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(9, 17, 27, 0.18);
  border: 1px solid rgba(255, 255, 255, 0.12);
}}
.doc-stat-label {{
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: rgba(240, 248, 255, 0.7);
}}
.doc-stat-value {{
  margin-top: 8px;
  font-size: 19px;
  font-weight: 700;
  color: #ffffff;
}}
.doc-content {{
  padding: 22px 26px 26px;
}}
.doc-section {{
  margin-bottom: 18px;
}}
.doc-section:last-child {{
  margin-bottom: 0;
}}
.doc-section-title {{
  margin: 0 0 12px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #596a7f;
}}
.doc-grid-2 {{
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}}
.doc-grid-3 {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}}
.doc-panel {{
  padding: 16px 18px;
  border: 1px solid #dbe4ee;
  border-radius: 18px;
  background: #f8fbfd;
}}
.doc-panel-strong {{
  background: linear-gradient(135deg, #f8fbfd 0%, #eef4fa 100%);
}}
.doc-chip-list {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}}
.doc-chip {{
  display: inline-flex;
  align-items: center;
  min-height: 31px;
  padding: 6px 12px;
  border: 1px solid #d4e1ee;
  border-radius: 999px;
  background: #edf3f9;
  color: #17324a;
  font-size: 12px;
  font-weight: 600;
}}
.doc-chip-alert {{
  background: #fff1f2;
  border-color: #f2bcc3;
  color: #8d2f3d;
}}
.doc-chip-muted {{
  background: #f8fafc;
  border-color: #e5ebf2;
  color: #687a8d;
}}
.doc-note-box {{
  padding: 16px 18px;
  border: 1px solid #dae4ef;
  border-radius: 18px;
  background: #f7f9fc;
  color: #223141;
  white-space: pre-wrap;
}}
.doc-table-shell {{
  border: 1px solid #d9e2ec;
  border-radius: 18px;
  overflow: hidden;
  background: #ffffff;
}}
table {{
  width: 100%;
  border-collapse: collapse;
}}
th, td {{
  padding: 10px 12px;
  text-align: left;
  vertical-align: top;
  border-bottom: 1px solid #e5ebf2;
}}
th {{
  background: #eef4fa;
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #526174;
}}
td {{
  font-size: 12px;
  color: #1f2c3c;
}}
tbody tr:nth-child(even) td {{
  background: #fbfdff;
}}
tbody tr:last-child td {{
  border-bottom: none;
}}
.doc-empty {{
  padding: 18px;
  border: 1px dashed #cfdae6;
  border-radius: 18px;
  background: #f7f9fc;
  color: #617286;
}}
.doc-checklist {{
  display: grid;
  gap: 10px;
}}
.doc-check-item {{
  display: grid;
  grid-template-columns: 24px minmax(110px, 0.85fr) minmax(0, 2fr);
  gap: 12px;
  align-items: start;
  padding: 12px 14px;
  border: 1px solid #dae3ed;
  border-radius: 16px;
  background: #f8fbfd;
}}
.doc-check-box {{
  width: 18px;
  height: 18px;
  border: 2px solid #31465a;
  border-radius: 4px;
  margin-top: 2px;
}}
.doc-check-label {{
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #13304c;
}}
.doc-check-copy {{
  color: #334255;
}}
.doc-kv {{
  display: grid;
  gap: 10px;
}}
.doc-kv-row {{
  display: grid;
  grid-template-columns: minmax(100px, 0.55fr) minmax(0, 1fr);
  gap: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid #e5ebf2;
}}
.doc-kv-row:last-child {{
  padding-bottom: 0;
  border-bottom: none;
}}
.doc-kv-key {{
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #607285;
}}
.doc-footer {{
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  font-size: 10px;
  color: #748496;
}}
.doc-strong {{
  font-weight: 700;
}}
.doc-alert {{
  color: #af2f37;
  font-weight: 700;
}}
@media (max-width: 760px) {{
  body {{ padding: 12px; }}
  .doc-shell {{ border-radius: 18px; }}
  .doc-grid-2,
  .doc-grid-3,
  .doc-check-item,
  .doc-kv-row {{
    grid-template-columns: 1fr;
  }}
  .doc-header,
  .doc-content {{
    padding: 18px;
  }}
  .doc-title {{
    font-size: 26px;
  }}
  .doc-meta {{
    justify-content: flex-start;
  }}
}}
@media print {{
  @page {{ size: {page_size} {orientation}; margin: 12mm 10mm 14mm; }}
  @page :first {{ margin-top: 14mm; }}
  body {{
    padding: 0;
    background: #ffffff;
    /* Tighten body copy so paragraphs do not strand a single
       line at the top or bottom of a page. */
    orphans: 3;
    widows: 3;
  }}
  .doc-shell {{
    max-width: none;
    border: none;
    border-radius: 0;
    box-shadow: none;
  }}
  .doc-header {{
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }}
  .doc-section,
  .doc-panel,
  .doc-table-shell,
  .doc-check-item,
  .doc-kv-row,
  .doc-note-box {{
    page-break-inside: avoid;
    break-inside: avoid-page;
  }}
  /* Repeat table chrome on every printed page so multi-page
     rosters / inventories stay legible without scrolling back. */
  thead {{
    display: table-header-group;
  }}
  tfoot {{
    display: table-footer-group;
  }}
  tr {{
    page-break-inside: avoid;
    break-inside: avoid-page;
  }}
  /* Headings should not be the last thing on a page. */
  h1, h2, h3 {{
    page-break-after: avoid;
    break-after: avoid-page;
  }}
  /* Hide chrome that has no value on paper. */
  .no-print {{
    display: none !important;
  }}
  /* Class hooks for callers to force breaks where the layout demands. */
  .page-break-before {{
    page-break-before: always;
    break-before: page;
  }}
  .page-break-after {{
    page-break-after: always;
    break-after: page;
  }}
}}
/* ─── Body utility classes (apply on screen + print) ───
   Keeps the print blueprints free of one-off inline styles. */
.doc-mt-6  {{ margin-top: 6px; }}
.doc-mt-8  {{ margin-top: 8px; }}
.doc-mt-10 {{ margin-top: 10px; }}
.doc-mt-12 {{ margin-top: 12px; }}
.doc-mt-16 {{ margin-top: 16px; }}
.doc-mb-8  {{ margin-bottom: 8px; }}
.doc-mb-12 {{ margin-bottom: 12px; }}
.doc-text-lg {{ font-size: 18px; }}
.doc-eyebrow-text {{
  letter-spacing: 0.12em;
  text-transform: uppercase;
}}
.doc-page-break {{
  /* Hint to the print engine to start a new page before this element. */
  page-break-before: always;
  break-before: page;
}}
.doc-panel-alert {{
  border-color: #e9b7b7;
  background: #fff5f5;
  color: #7a1d1d;
}}
.doc-cell-fixed-60 {{ width: 60px; }}
.doc-list-flat {{
  margin: 0;
  padding-left: 18px;
}}
.doc-signature-box {{
  min-height: 120px;
  border: 1px dashed #999;
  padding: 4px;
  margin: 4px 0;
}}
.doc-checkbox-cell {{
  background: #fff;
  border-style: solid;
}}
</style>
</head>
<body>
  <div class="doc-shell">
    <header class="doc-header">
      <div class="doc-eyebrow">{_escape(str(eyebrow))}</div>
      <div class="doc-title-row">
        <div>
          <h1 class="doc-title">{_escape(str(title))}</h1>
          <div class="doc-subtitle">{_escape(str(subtitle))}</div>
        </div>
        <div class="doc-meta">{meta_html}</div>
      </div>
      {stats_html}
    </header>
    <main class="doc-content">{body_html}</main>
  </div>
</body>
</html>'''
