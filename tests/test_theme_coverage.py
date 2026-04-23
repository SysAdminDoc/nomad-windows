"""Theme coverage tests.

Every declared theme must define the full set of semantic tokens so no
component renders a token-less fallback in a specific theme (the classic
"this card works in dark mode but is invisible in light mode" bug).

Also enforces two component-level guards:

1. Status colors (kit-builder, daily-brief, family-checkin, triage-step)
   must not be hardcoded hex — they have to route through semantic tokens
   (--red / --green / --warning / --info / --warning-dim etc.) so they
   track each theme's palette.
2. The five theme buttons must exist in the shell markup so a user can
   reach every theme from the UI.
"""

from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parents[1]
CSS_DIR = REPO_ROOT / 'web' / 'static' / 'css'
TOKEN_FILE = CSS_DIR / 'app' / '00_theme_tokens.css'

THEMES = ['nomad', 'nightops', 'redlight', 'cyber', 'eink']

# Semantic tokens that every theme MUST define so components can pick
# them up consistently. Keep this list tight — only the tokens that are
# actually referenced by non-theme-specific components.
REQUIRED_TOKENS = [
    '--bg', '--surface', '--surface-solid', '--surface2', '--surface3',
    '--surface-panel', '--surface-field', '--surface-field-soft',
    '--border', '--border-hover',
    '--text', '--text-dim', '--text-muted', '--text-inverse',
    '--accent', '--accent-hover', '--accent-dim',
    '--green', '--green-dim',
    '--red', '--red-dim',
    '--orange', '--orange-dim',
    '--warning', '--warning-dim', '--warning-border',
    '--info', '--info-dim',
    '--gradient-accent', '--gradient-card',
    '--sidebar-bg', '--overlay-scrim',
]


def _theme_block(css_text: str, theme: str) -> str:
    """Extract the declaration block of a given [data-theme="..."] rule."""
    # Handle the :root, [data-theme="nomad"] combined selector as well.
    pattern = (
        r'(?:(?::root,\s*)?\[data-theme="' + re.escape(theme) + r'"\]\s*,?\s*)+'
        r'\{([^}]+)\}'
    )
    m = re.search(pattern, css_text)
    if not m:
        # Try the combined :root form
        if theme == 'nomad':
            m = re.search(r':root,\s*\[data-theme="nomad"\]\s*\{([^}]+)\}', css_text)
    return m.group(1) if m else ''


class TestThemeTokens:
    def test_all_five_themes_are_declared(self):
        css = TOKEN_FILE.read_text(encoding='utf-8')
        for theme in THEMES:
            # Either standalone [data-theme="x"] block OR :root combined block.
            pattern = rf'\[data-theme="{theme}"\]'
            assert re.search(pattern, css), f'Theme {theme!r} not declared in 00_theme_tokens.css'

    def test_each_theme_defines_required_semantic_tokens(self):
        css = TOKEN_FILE.read_text(encoding='utf-8')
        missing = {}
        for theme in THEMES:
            block = _theme_block(css, theme)
            assert block, f'Could not locate block for theme {theme!r}'
            gone = [t for t in REQUIRED_TOKENS if t not in block]
            if gone:
                missing[theme] = gone
        assert not missing, (
            'Themes missing required semantic tokens — components that read '
            'these will render without a value in the affected theme:\n'
            + '\n'.join(f'  {theme}: {tokens}' for theme, tokens in missing.items())
        )

    def test_each_theme_declares_color_scheme(self):
        """`color-scheme` lets native form controls + scrollbars pick the right
        base style for the theme. Missing it produces a dark form in a light
        theme (or vice versa) even though the surrounding page colors flip."""
        css = TOKEN_FILE.read_text(encoding='utf-8')
        for theme in THEMES:
            block = _theme_block(css, theme)
            assert 'color-scheme' in block, (
                f'Theme {theme!r} is missing `color-scheme:` — native controls '
                'will mismatch the theme.'
            )


class TestNoHardcodedStatusColors:
    """Status indicators (ok/warn/danger/info) must use semantic tokens so
    they follow the active theme's palette. These were previously
    hardcoded (#ff5757, #ffc857, #4aedc4, #8ac7ff), which rendered tactical
    greens/reds on top of a light sepia or paper (e-ink) theme — unreadable
    or simply wrong-signaling. Guard the fixed files from regressing."""

    FILES = [
        CSS_DIR / 'app' / '40_preparedness_media.css',
        CSS_DIR / 'premium' / '30_preparedness_ops.css',
        CSS_DIR / 'premium' / '50_settings.css',
    ]
    FORBIDDEN_HEX = ['#ff5757', '#ffc857', '#4aedc4', '#8ac7ff']

    def test_no_forbidden_status_hex_in_guarded_files(self):
        offenders = []
        for path in self.FILES:
            text = path.read_text(encoding='utf-8')
            for hex_code in self.FORBIDDEN_HEX:
                # Case-insensitive search — but skip matches that sit inside a
                # var() fallback (e.g. `var(--red, #ff5757)`) since those are
                # still token-first.
                for m in re.finditer(re.escape(hex_code), text, re.IGNORECASE):
                    line_start = text.rfind('\n', 0, m.start()) + 1
                    line_end = text.find('\n', m.end())
                    line = text[line_start:line_end]
                    if 'var(--' in line and ',' in line.split(hex_code, 1)[0].rsplit('var(--', 1)[-1]:
                        continue
                    offenders.append(f'{path.name}:{text[:m.start()].count(chr(10)) + 1}: {hex_code}')
        assert not offenders, (
            'Hardcoded status colors found in theme-aware files — these will '
            'break in light/e-ink themes:\n' + '\n'.join(offenders)
        )


class TestThemeSwitcherMarkup:
    def test_all_themes_have_switcher_buttons(self):
        shell = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / '_shell.html').read_text(encoding='utf-8')
        for theme in THEMES:
            assert f'data-t="{theme}"' in shell, (
                f'Theme {theme!r} has no switcher button in the shell — user '
                'cannot reach it from the UI.'
            )

    def test_js_theme_names_match_css_themes(self):
        """THEME_NAMES in the JS shell must list the same themes that the CSS
        declares — an extra CSS theme with no JS label renders as its raw key
        ("nightops") in the footer indicator; an extra JS label with no CSS
        block silently applies nothing when clicked."""
        core_shell = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_core_shell.js').read_text(encoding='utf-8')
        # Parse the THEME_NAMES object keys between `const THEME_NAMES = {` and `};`
        m = re.search(r'const\s+THEME_NAMES\s*=\s*\{([^}]+)\}', core_shell)
        assert m, 'THEME_NAMES not found in _app_core_shell.js'
        js_keys = set(re.findall(r'(\w+)\s*:', m.group(1)))
        css_set = set(THEMES)
        missing_in_js = css_set - js_keys
        missing_in_css = js_keys - css_set
        assert not missing_in_js, (
            f'Themes declared in CSS but missing a JS label: {missing_in_js}. '
            'The active-theme indicator will show the raw key instead of a name.'
        )
        assert not missing_in_css, (
            f'JS labels for themes with no CSS block: {missing_in_css}. '
            'Clicking the switcher will set data-theme to a key that matches no rules.'
        )
