"""Verify freeze_support() is called before any heavy imports in nomad.py."""

import ast
import os


def test_freeze_support_precedes_heavy_imports():
    """multiprocessing.freeze_support() must appear before the first
    non-stdlib import so PyInstaller frozen builds don't relaunch child
    processes that re-execute the entire module-level code."""
    nomad_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'nomad.py'
    )
    with open(nomad_path) as f:
        tree = ast.parse(f.read())

    freeze_line = None
    first_heavy_import_line = None

    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            func = node.value.func
            if (isinstance(func, ast.Attribute) and func.attr == 'freeze_support'
                    and isinstance(func.value, ast.Name)
                    and func.value.id == 'multiprocessing'):
                freeze_line = node.lineno
                break

    stdlib_prefixes = {
        'sys', 'os', 'subprocess', 'threading', 'time', 'logging',
        'multiprocessing', 'json', 'pathlib', 'math', 'datetime',
        'importlib', 'collections', 'functools', 'io', 're',
    }

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split('.')[0]
                if root not in stdlib_prefixes:
                    first_heavy_import_line = node.lineno
                    break
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split('.')[0]
            if root not in stdlib_prefixes:
                first_heavy_import_line = node.lineno
                break
        if first_heavy_import_line:
            break

    assert freeze_line is not None, (
        'multiprocessing.freeze_support() not found in nomad.py'
    )
    assert first_heavy_import_line is not None, (
        'No non-stdlib imports found in nomad.py (unexpected)'
    )
    assert freeze_line < first_heavy_import_line, (
        f'freeze_support() at line {freeze_line} must come before '
        f'first non-stdlib import at line {first_heavy_import_line}'
    )


def test_runtime_hook_exists():
    """build.spec references runtime_hook.py — verify it exists and calls
    freeze_support()."""
    hook_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'runtime_hook.py'
    )
    assert os.path.isfile(hook_path), 'runtime_hook.py missing from project root'
    with open(hook_path) as f:
        content = f.read()
    assert 'freeze_support' in content, (
        'runtime_hook.py must call multiprocessing.freeze_support()'
    )


def test_build_spec_references_runtime_hook():
    """build.spec must include runtime_hook.py in runtime_hooks."""
    spec_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'build.spec'
    )
    with open(spec_path) as f:
        content = f.read()
    assert 'runtime_hook.py' in content, (
        'build.spec must reference runtime_hook.py in runtime_hooks'
    )


def test_pyinstaller_floor_pinned():
    """requirements-dev.txt must pin PyInstaller >= 6.10.0 (CVE-2025-59042)."""
    req_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'requirements-dev.txt'
    )
    with open(req_path) as f:
        content = f.read().lower()
    assert 'pyinstaller>=6.10.0' in content.replace(' ', ''), (
        'requirements-dev.txt must pin pyinstaller>=6.10.0'
    )
