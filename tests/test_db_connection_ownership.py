"""Static DB ownership guardrails for web blueprints."""

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT_DIR = REPO_ROOT / 'web' / 'blueprints'


def test_web_blueprints_do_not_open_bare_get_db_connections():
    offenders = []
    for path in sorted(BLUEPRINT_DIR.glob('*.py')):
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == 'get_db'
            ):
                offenders.append(f'{path.relative_to(REPO_ROOT)}:{node.lineno}')

    assert not offenders, 'Use db_session() in blueprints instead of bare get_db(): ' + ', '.join(offenders)
