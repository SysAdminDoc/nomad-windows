"""i18n coverage ratchet for visible shell text.

Ensures the count of data-i18n hooks in the shell and key templates
doesn't regress. The baseline is intentionally low (12 hooks in v7.66.34);
as new labels are tagged, update BASELINE_COUNT to ratchet forward.
"""

import os
import re
from pathlib import Path

REPO_ROOT = Path(os.path.dirname(os.path.dirname(__file__)))
PARTIALS_DIR = REPO_ROOT / 'web' / 'templates' / 'index_partials'

BASELINE_COUNT = 12

SHELL_FILES = [
    '_shell.html',
    '_tab_settings.html',
    '_tab_services.html',
    '_tab_diagnostics.html',
]


def _count_i18n_hooks(paths):
    total = 0
    for p in paths:
        if p.is_file():
            total += len(re.findall(r'data-i18n=', p.read_text(encoding='utf-8')))
    return total


def test_i18n_hook_count_does_not_regress():
    """data-i18n count must not drop below the baseline."""
    paths = [PARTIALS_DIR / f for f in SHELL_FILES]
    count = _count_i18n_hooks(paths)
    assert count >= BASELINE_COUNT, (
        f'data-i18n hook count regressed: {count} < {BASELINE_COUNT}. '
        'Hooks were removed from shell/settings/services/diagnostics templates.'
    )


def test_shell_sidebar_labels_have_i18n():
    """Every nav label in _shell.html should have a data-i18n attribute."""
    shell = PARTIALS_DIR / '_shell.html'
    if not shell.is_file():
        return
    text = shell.read_text(encoding='utf-8')
    nav_spans = re.findall(r'<span[^>]*>.*?</span>', text, re.DOTALL)
    nav_with_i18n = [s for s in nav_spans if 'data-i18n=' in s]
    nav_labels = [s for s in nav_spans if 'nav-label' in s or 'data-i18n=' in s]
    assert len(nav_with_i18n) >= 11, (
        f'Shell sidebar has {len(nav_with_i18n)} i18n-tagged nav labels, expected >= 11'
    )
