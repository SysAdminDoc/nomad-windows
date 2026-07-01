"""Verify MkDocs guide pages mention all registered workspaces/blueprints.

This test catches drift when new blueprints are added but docs don't
mention the workspace. It does NOT require docs to be complete — only
that the workspace name appears somewhere in the guide pages.
"""

import ast
import os
from pathlib import Path

REPO_ROOT = Path(os.path.dirname(os.path.dirname(__file__)))

KNOWN_INTERNAL = {
    'benchmark', 'print_routes', 'undo', 'pack_importers',
    'remaining_features', 'remaining_refs', 'remaining_calcs',
    'roadmap_features', 'lazy_blueprints', 'plugins',
}

KNOWN_UNDOCUMENTED = {
    'disaster_modules', 'evac_drills', 'field_ops', 'field_tools',
    'hardware_sensors', 'health_family', 'land_assessment',
    'medical_phase2', 'movement_ops', 'readiness_goals',
    'regional_profile', 'scheduled_reports', 'security_opsec',
    'shamir_vault', 'specialized_threats', 'tactical_comms',
    'tier8_tools', 'training_knowledge', 'water_mgmt',
}


def _extract_blueprint_names():
    """Parse blueprint_registry.py to extract all registered blueprint module names."""
    registry = REPO_ROOT / 'web' / 'blueprint_registry.py'
    tree = ast.parse(registry.read_text(encoding='utf-8'))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith('web.blueprints.'):
            mod = node.module.split('.')[-1]
            names.add(mod)
    return names


def _load_docs_text():
    """Concatenate all guide markdown files into one searchable blob."""
    guide_dir = REPO_ROOT / 'docs' / 'guide'
    if not guide_dir.is_dir():
        return ''
    texts = []
    for md in sorted(guide_dir.glob('*.md')):
        texts.append(md.read_text(encoding='utf-8').lower())
    return '\n'.join(texts)


def _load_readme_text():
    readme = REPO_ROOT / 'README.md'
    if readme.is_file():
        return readme.read_text(encoding='utf-8').lower()
    return ''


def test_no_new_undocumented_blueprints():
    """New blueprints must be mentioned in docs or README.

    KNOWN_UNDOCUMENTED grandfathers existing gaps. Adding a blueprint
    without documenting it fails this test — add a docs reference or
    add it to KNOWN_UNDOCUMENTED with a comment explaining why.
    """
    bp_names = _extract_blueprint_names() - KNOWN_INTERNAL
    docs = _load_docs_text() + '\n' + _load_readme_text()

    search_terms = {}
    for name in bp_names:
        readable = name.replace('_', ' ').replace('-', ' ')
        search_terms[name] = [
            name.lower(),
            readable.lower(),
            name.replace('_', '-').lower(),
        ]

    missing = []
    for name, terms in search_terms.items():
        if not any(t in docs for t in terms):
            missing.append(name)

    new_undocumented = set(missing) - KNOWN_UNDOCUMENTED
    assert not new_undocumented, (
        f'New blueprints not mentioned in docs/guide/ or README.md: {sorted(new_undocumented)}. '
        'Add a reference to the relevant guide page or add to KNOWN_UNDOCUMENTED.'
    )
