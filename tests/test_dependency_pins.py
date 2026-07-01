"""Dependency floor regression tests."""

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _version_tuple(value):
    return tuple(int(part) for part in value.split('.'))


def _requirement_floor(filename, package, ceiling):
    requirements = (REPO_ROOT / filename).read_text(encoding='utf-8')
    pattern = rf'^{re.escape(package)}>=([0-9]+(?:\.[0-9]+)*),<{re.escape(ceiling)}$'
    match = re.search(pattern, requirements, re.IGNORECASE | re.MULTILINE)
    assert match, f'{filename} must pin {package} with an explicit >= floor and <{ceiling} ceiling'
    return _version_tuple(match.group(1))


def test_runtime_dependency_floors_stay_above_known_vulnerable_releases():
    assert _requirement_floor('requirements.txt', 'flask', '4.0') >= (3, 1, 3)
    assert _requirement_floor('requirements.txt', 'pillow', '13.0') >= (12, 2)
    assert _requirement_floor('requirements.txt', 'yt-dlp', '2027.0') >= (2026, 2, 21)


def test_development_dependency_floors_stay_auditable():
    assert _requirement_floor('requirements-dev.txt', 'pytest', '10.0') >= (9, 0, 3)
    assert _requirement_floor('requirements-dev.txt', 'pytest-cov', '8.0') >= (7, 1)
    assert _requirement_floor('requirements-dev.txt', 'pip-audit', '3.0') >= (2, 10, 1)


def test_security_audit_tooling_stays_local_only():
    assert not (REPO_ROOT / '.github' / 'workflows').exists()
    requirements_dev = (REPO_ROOT / 'requirements-dev.txt').read_text(encoding='utf-8')
    assert 'pip-audit>=2.10.1,<3.0' in requirements_dev
