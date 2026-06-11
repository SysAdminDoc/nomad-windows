"""Dependency floor regression tests."""

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _version_tuple(value):
    return tuple(int(part) for part in value.split('.'))


def test_flask_dependency_floor_stays_above_vulnerable_release():
    requirements = (REPO_ROOT / 'requirements.txt').read_text(encoding='utf-8')
    match = re.search(r'^flask>=([0-9]+(?:\.[0-9]+)*),<4\.0$', requirements, re.IGNORECASE | re.MULTILINE)
    assert match, 'requirements.txt must pin Flask with an explicit >= floor and <4.0 ceiling'
    assert _version_tuple(match.group(1)) >= (3, 1, 3)
