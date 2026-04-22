#!/usr/bin/env python3
"""
Extract the in-app Help Guide from _app_ops_support.js into
MkDocs-compatible markdown files under docs/guide/.

Run from the project root:
    python scripts/extract_guide_to_docs.py
"""
import re
import os
import html
from html.parser import HTMLParser


# ── paths ──────────────────────────────────────────────────────────────────────
REPO_ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_JS      = os.path.join(REPO_ROOT, 'web', 'templates', 'index_partials', 'js',
                            '_app_ops_support.js')
DOCS_GUIDE  = os.path.join(REPO_ROOT, 'docs', 'guide')


# ── HTML → Markdown converter ──────────────────────────────────────────────────
class _H2MParser(HTMLParser):
    """Minimal HTML-to-Markdown converter for the guide."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self._stack = []          # current open tags
        self._text_buf = ''       # text accumulator
        self._list_depth = 0
        self._ol_counter = []     # stack of ordered-list counters
        self._in_step = False
        self._in_tip  = False
        self._in_warn = False
        self._skip    = False     # skip content of toc div, style, head
        self._row_cells = []      # accumulate cells in current table row
        self._in_header_row = False

    # ── helpers ──

    def _flush(self):
        t = self._text_buf.strip()
        self._text_buf = ''
        return t

    def _push_line(self, line):
        self.out.append(line)

    def _peek(self):
        return self._stack[-1] if self._stack else None

    def _has_cls(self, cls_str, name):
        """True if `name` is an exact word in a space-separated class string."""
        return name in cls_str.split()

    # ── parser events ──

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        cls = attrs_dict.get('class', '')

        if tag in ('html', 'head', 'meta', 'title', 'style'):
            self._skip = True
            return
        if tag == 'body':
            self._skip = False
            return
        if tag == 'div' and self._has_cls(cls, 'toc'):
            self._stack.append('toc')
            self._skip = True
            return
        if tag == 'div' and self._has_cls(cls, 'step'):
            self._in_step = True
            self._stack.append('step')
            return
        if tag == 'div' and self._has_cls(cls, 'step-num'):
            self._stack.append('step-num')
            return
        if tag == 'div' and self._has_cls(cls, 'step-text'):
            self._stack.append('step-text')
            self._text_buf = '- '   # start bullet for this step
            return
        if tag == 'div' and (self._has_cls(cls, 'tip') or self._has_cls(cls, 'guide-tip')):
            self._in_tip = True
            self._stack.append('tip')
            self._push_line('')
            return
        if tag == 'div' and (self._has_cls(cls, 'warn') or self._has_cls(cls, 'warning')):
            self._in_warn = True
            self._stack.append('warn')
            self._push_line('')
            return

        self._stack.append(tag)

        if tag in ('h1', 'h2', 'h3', 'h4', 'h5'):
            self._push_line('')
            level = int(tag[1])
            self._text_buf = '#' * level + ' '
        elif tag == 'p':
            self._push_line('')
        elif tag == 'ul':
            self._list_depth += 1
        elif tag == 'ol':
            self._list_depth += 1
            self._ol_counter.append(0)
        elif tag == 'li':
            parent_tag = None
            for t in reversed(self._stack[:-1]):
                if t in ('ul', 'ol'):
                    parent_tag = t
                    break
            indent = '  ' * (self._list_depth - 1)
            if parent_tag == 'ol' and self._ol_counter:
                self._ol_counter[-1] += 1
                prefix = f'{indent}{self._ol_counter[-1]}. '
            else:
                prefix = f'{indent}- '
            self._text_buf = prefix
        elif tag == 'strong' or tag == 'b':
            self._text_buf += '**'
        elif tag == 'em' or tag == 'i':
            self._text_buf += '_'
        elif tag == 'code':
            self._text_buf += '`'
        elif tag == 'kbd':
            self._text_buf += '<kbd>'
        elif tag == 'a':
            href = attrs_dict.get('href', '')
            if href.startswith('#'):
                href = ''         # strip intra-doc anchors — irrelevant in MkDocs
            self._stack[-1] = ('a', href)
        elif tag == 'table':
            self._push_line('')
            self._row_cells = []
        elif tag == 'thead':
            self._in_header_row = True
        elif tag == 'tbody':
            self._in_header_row = False
        elif tag == 'tr':
            self._row_cells = []
            self._row_has_th = False
        elif tag in ('th', 'td'):
            # track header cells; start fresh cell accumulation
            if tag == 'th':
                self._row_has_th = True
            self._text_buf = ''
        elif tag == 'br':
            self._push_line(self._flush())
        elif tag == 'hr':
            self._push_line('\n---\n')

    def handle_endtag(self, tag):
        if not self._stack:
            return
        top = self._stack[-1]

        # handle toc div
        if top == 'toc':
            if tag == 'div':
                self._stack.pop()
                self._skip = False
            return
        if self._skip:
            return

        if isinstance(top, tuple) and top[0] == 'a':
            # close anchor
            txt = self._flush()
            href = top[1]
            self._stack.pop()
            if href:
                self._text_buf += f'[{txt}]({href})'
            else:
                self._text_buf += txt
            return

        # step-num: just pop, no output
        if top == 'step-num' and tag == 'div':
            self._stack.pop()
            return

        # step-text: flush accumulated text as a bullet
        if top == 'step-text' and tag == 'div':
            t = self._flush()
            if t:
                self._push_line(t)
            else:
                # text_buf still has the '- ' prefix, emit it
                self._push_line(self._text_buf.strip())
                self._text_buf = ''
            self._stack.pop()
            return

        if top == 'step':
            if tag == 'div':
                self._stack.pop()
                self._in_step = False
                self._push_line('')
            return
        if top in ('tip', 'warn') and tag == 'div':
            self._stack.pop()
            # flush any text placed directly inside the div (not wrapped in <p>)
            t = self._flush()
            if t:
                if self._in_tip:
                    self._push_line(f'> {t}')
                else:
                    self._push_line(f'> {t}')
            self._in_tip  = False
            self._in_warn = False
            self._push_line('')
            return

        self._stack.pop()

        if tag in ('h1', 'h2', 'h3', 'h4', 'h5'):
            self._push_line(self._flush())
        elif tag == 'p':
            t = self._flush()
            if t:
                if self._in_tip:
                    self._push_line(f'> **Tip:** {t}')
                elif self._in_warn:
                    self._push_line(f'> **Warning:** {t}')
                else:
                    self._push_line(t)
        elif tag == 'li':
            t = self._flush()
            if t:
                self._push_line(t)
        elif tag == 'ul':
            self._list_depth = max(0, self._list_depth - 1)
            self._push_line('')
        elif tag == 'ol':
            self._list_depth = max(0, self._list_depth - 1)
            if self._ol_counter:
                self._ol_counter.pop()
            self._push_line('')
        elif tag == 'strong' or tag == 'b':
            self._text_buf += '**'
        elif tag == 'em' or tag == 'i':
            self._text_buf += '_'
        elif tag == 'code':
            self._text_buf += '`'
        elif tag == 'kbd':
            self._text_buf += '</kbd>'
        elif tag in ('th', 'td'):
            # save finished cell to row accumulator
            self._row_cells.append(self._text_buf.strip())
            self._text_buf = ''
        elif tag == 'tr':
            # emit the full row as a pipe-delimited markdown table row
            if self._row_cells:
                row = '| ' + ' | '.join(self._row_cells) + ' |'
                self._push_line(row)
                # auto-emit separator after the first (header) row
                if self._row_has_th:
                    sep = '| ' + ' | '.join(['---'] * len(self._row_cells)) + ' |'
                    self._push_line(sep)
                self._row_cells = []
                self._row_has_th = False
        elif tag == 'thead':
            self._in_header_row = False

    def handle_data(self, data):
        if self._skip:
            return
        # skip content of the step-num badge
        top = self._stack[-1] if self._stack else ''
        if top == 'step-num':
            return
        cleaned = re.sub(r'\s+', ' ', data)
        self._text_buf += cleaned

    def get_markdown(self):
        if self._text_buf.strip():
            self.out.append(self._text_buf.strip())
        # collapse multiple blank lines
        lines = self.out
        result = []
        prev_blank = False
        for line in lines:
            is_blank = line.strip() == ''
            if is_blank and prev_blank:
                continue
            result.append(line)
            prev_blank = is_blank
        return '\n'.join(result).strip() + '\n'


def html_to_md(html_str):
    p = _H2MParser()
    p.feed(html_str)
    return p.get_markdown()


# ── section metadata ───────────────────────────────────────────────────────────
SECTIONS = [
    ('01-getting-started',      'Getting Started'),
    ('02-home-dashboard',       'Home Dashboard'),
    ('03-readiness-score',      'Readiness Score'),
    ('04-ai-assistant',         'AI Assistant'),
    ('05-library',              'Information Library'),
    ('06-maps',                 'Offline Maps'),
    ('07-notes',                'Notes'),
    ('08-tools',                'Tools'),
    ('09-preparedness',         'Preparedness (25 Sub-Tabs)'),
    ('10-alerts',               'Proactive Alerts'),
    ('11-sync',                 'Connecting Multiple Systems'),
    ('12-scenarios',            'Training Scenarios'),
    ('13-themes',               'Themes'),
    ('14-settings',             'Settings & Backup'),
    ('15-diagnostics',          'Diagnostics'),
    ('16-keyboard-shortcuts',   'Keyboard Shortcuts'),
    ('17-data-privacy',         'Data & Privacy'),
    ('18-troubleshooting',      'Troubleshooting'),
    ('19-day-one',              'Day One Checklist'),
    ('20-ai-models',            'Choosing an AI Model'),
    ('21-inventory-best-practices', 'Inventory Best Practices'),
    ('22-printable-reports',    'Printable Reports'),
    ('23-lan',                  'LAN & Multi-Device'),
    ('24-services',             'Understanding Services'),
    ('25-use-cases',            'Common Use Cases'),
    ('26-calculators',          'Calculators Reference'),
    ('27-nukemap',              'NukeMap Guide'),
    ('28-notes-guide',          'Notes & Documentation'),
    ('29-faq',                  'FAQ'),
    ('30-medical',              'Medical Module In Depth'),
    ('31-food-production',      'Food Production Guide'),
    ('32-power',                'Power Management Guide'),
    ('33-security',             'Security Module Guide'),
    ('34-weather',              'Weather Tracking Guide'),
    ('35-comms',                'Communications & Radio'),
    ('36-vault',                'Secure Vault Guide'),
    ('37-scenarios-deep',       'Training Scenarios In Depth'),
    ('38-task-scheduler',       'Task Scheduler'),
    ('39-ai-memory',            'AI Memory System'),
    ('40-printable-field-docs', 'Printable Field Documents'),
    ('41-glossary',             'Glossary'),
]


def extract_html_from_js(js_path):
    """Extract the guide HTML template literal from _app_ops_support.js."""
    with open(js_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # The template literal is opened with:  openAppFrameHTML('Help Guide', `
    # Find start of HTML content
    start_marker = "openAppFrameHTML('Help Guide', `"
    start = content.find(start_marker)
    if start == -1:
        raise RuntimeError('Could not find openAppFrameHTML template literal start')

    html_start = start + len(start_marker)

    # Find the closing backtick for this template literal.
    # It is followed by `, section);` on the same line.
    # We search for a backtick that is followed by `, section)` (with possible spaces)
    closing = re.search(r'`\s*,\s*section\s*\)', content[html_start:])
    if not closing:
        raise RuntimeError('Could not find end of template literal (`, section)`)')

    html_str = content[html_start: html_start + closing.start()]

    # Strip JS template expressions like ${bg}, ${VERSION}, etc.
    html_str = re.sub(r'\$\{[^}]+\}', '', html_str)

    # Unescape HTML entities already present
    html_str = html_str.replace('&amp;', '&').replace('&mdash;', '\u2014') \
                       .replace('&gt;', '>').replace('&lt;', '<') \
                       .replace('&nbsp;', '\u00a0').replace('&#39;', "'") \
                       .replace('&ldquo;', '\u201c').replace('&rdquo;', '\u201d')

    return html_str


def split_into_sections(html_str):
    """
    Split the full guide HTML at each <h2 id="..."> boundary.
    Returns list of (h2_id, section_html) tuples.
    """
    pattern = re.compile(r'(<h2\s[^>]*id="([^"]*)"[^>]*>)', re.IGNORECASE)
    pieces = pattern.split(html_str)
    # pieces: [preamble, h2_tag, h2_id, section_body, h2_tag, h2_id, section_body, ...]
    sections = []
    i = 1
    while i < len(pieces) - 2:
        h2_tag = pieces[i]
        h2_id  = pieces[i + 1]
        body   = pieces[i + 2]
        sections.append((h2_id, h2_tag + body))
        i += 3
    return sections


def write_section(slug, title, section_html, out_dir):
    md_content = html_to_md(section_html)
    # Ensure h2 heading text at top is correct (don't duplicate number from header)
    path = os.path.join(out_dir, slug + '.md')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    return path


def main():
    os.makedirs(DOCS_GUIDE, exist_ok=True)

    print(f'Reading {SRC_JS}')
    guide_html = extract_html_from_js(SRC_JS)
    print(f'  Extracted {len(guide_html):,} characters of HTML')

    sections = split_into_sections(guide_html)
    print(f'  Found {len(sections)} h2 sections')

    for i, (h2_id, html_str) in enumerate(sections):
        if i < len(SECTIONS):
            slug, title = SECTIONS[i]
        else:
            slug = f'{i+1:02d}-section-{i+1}'
            title = f'Section {i+1}'
        path = write_section(slug, title, html_str, DOCS_GUIDE)
        print(f'  [{i+1:2d}] {slug}.md  ({os.path.getsize(path):,} bytes)')

    print(f'\nDone — {len(sections)} files written to {DOCS_GUIDE}')


if __name__ == '__main__':
    main()
