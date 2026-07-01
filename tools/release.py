#!/usr/bin/env python3
"""Local release packaging pipeline for NOMAD Field Desk.

Usage: py -3.12 tools/release.py [--skip-tests] [--skip-build]

Produces release artifacts in dist/ with SHA256SUMS.txt and build manifest.
Refuses to produce output if version strings are inconsistent or tests fail.
"""

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

VERSION_FILES = {
    'config.py': re.compile(r"'NOMAD_VERSION',\s*'([^']+)'"),
    'pyproject.toml': re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE),
    'installer.iss': re.compile(r'#define\s+MyAppVersion\s+"([^"]+)"'),
    'README.md': re.compile(r'# NOMAD Field Desk v([\d.]+)'),
}


def read_versions():
    versions = {}
    for filename, pattern in VERSION_FILES.items():
        path = REPO_ROOT / filename
        if not path.exists():
            print(f'  MISSING: {filename}')
            continue
        text = path.read_text(encoding='utf-8')
        m = pattern.search(text)
        if m:
            versions[filename] = m.group(1)
        else:
            print(f'  NO MATCH: {filename}')
    return versions


def check_version_consistency():
    print('Checking version consistency...')
    versions = read_versions()
    if not versions:
        print('  ERROR: no version strings found')
        return None
    unique = set(versions.values())
    if len(unique) != 1:
        print('  ERROR: version mismatch:')
        for f, v in versions.items():
            print(f'    {f}: {v}')
        return None
    version = unique.pop()
    print(f'  Version: {version} (consistent across {len(versions)} files)')
    return version


def run_tests():
    print('Running test suite...')
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', 'tests/', '-q', '--timeout=120',
         '--timeout-method=thread', '-x'],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=900,
    )
    if result.returncode != 0:
        print('  TESTS FAILED:')
        for line in result.stdout.splitlines()[-10:]:
            print(f'    {line}')
        return False
    last = [l for l in result.stdout.splitlines() if l.strip()]
    if last:
        print(f'  {last[-1]}')
    return True


def run_npm_build():
    print('Building JS/CSS bundle...')
    result = subprocess.run(
        ['npm', 'run', 'build'],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
        shell=True,
    )
    if result.returncode != 0:
        print('  npm build FAILED')
        print(result.stderr[-500:] if result.stderr else '')
        return False
    print('  Bundle built')
    return True


def run_pyinstaller():
    print('Building PyInstaller executable...')
    dist_dir = REPO_ROOT / 'dist'
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    build_dir = REPO_ROOT / 'build'
    if build_dir.exists():
        shutil.rmtree(build_dir)

    result = subprocess.run(
        [sys.executable, '-m', 'PyInstaller', 'build.spec', '--noconfirm'],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        print('  PyInstaller FAILED')
        print(result.stderr[-500:] if result.stderr else '')
        return False

    exe_name = 'NOMADFieldDesk.exe' if sys.platform == 'win32' else 'NOMADFieldDesk'
    exe_path = dist_dir / exe_name
    if not exe_path.exists():
        print(f'  ERROR: {exe_path} not found after build')
        return False
    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f'  Built: {exe_name} ({size_mb:.1f} MB)')
    return True


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def generate_checksums(dist_dir):
    print('Generating SHA256SUMS.txt...')
    sums = []
    for p in sorted(dist_dir.iterdir()):
        if p.name in ('SHA256SUMS.txt', 'build-manifest.json'):
            continue
        if p.is_file():
            digest = sha256_file(p)
            sums.append(f'{digest}  {p.name}')
            print(f'  {digest[:16]}...  {p.name}')
    sums_path = dist_dir / 'SHA256SUMS.txt'
    sums_path.write_text('\n'.join(sums) + '\n', encoding='utf-8')
    return sums_path


def generate_manifest(dist_dir, version):
    manifest = {
        'version': version,
        'built_at': datetime.now(timezone.utc).isoformat(),
        'platform': platform.system(),
        'python': platform.python_version(),
        'artifacts': [],
    }
    for p in sorted(dist_dir.iterdir()):
        if p.name == 'build-manifest.json':
            continue
        if p.is_file():
            manifest['artifacts'].append({
                'name': p.name,
                'size': p.stat().st_size,
                'sha256': sha256_file(p),
            })
    manifest_path = dist_dir / 'build-manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'  Manifest: {manifest_path.name}')
    return manifest_path


def main():
    parser = argparse.ArgumentParser(description='Local release packaging pipeline')
    parser.add_argument('--skip-tests', action='store_true')
    parser.add_argument('--skip-build', action='store_true')
    args = parser.parse_args()

    print('=' * 60)
    print('NOMAD Field Desk — Local Release Pipeline')
    print('=' * 60)

    version = check_version_consistency()
    if not version:
        print('\nABORTED: fix version inconsistency before release.')
        sys.exit(1)

    if not args.skip_tests:
        if not run_tests():
            print('\nABORTED: fix test failures before release.')
            sys.exit(1)
    else:
        print('Skipping tests (--skip-tests)')

    if not run_npm_build():
        print('\nABORTED: fix npm build before release.')
        sys.exit(1)

    if not args.skip_build:
        if not run_pyinstaller():
            print('\nABORTED: fix PyInstaller build before release.')
            sys.exit(1)
    else:
        print('Skipping PyInstaller build (--skip-build)')

    dist_dir = REPO_ROOT / 'dist'
    if not dist_dir.exists() or not any(dist_dir.iterdir()):
        print('\nABORTED: dist/ is empty — no artifacts to package.')
        sys.exit(1)

    generate_checksums(dist_dir)
    generate_manifest(dist_dir, version)

    print('\n' + '=' * 60)
    print(f'Release v{version} artifacts ready in dist/')
    print('=' * 60)
    for p in sorted(dist_dir.iterdir()):
        if p.is_file():
            print(f'  {p.name} ({p.stat().st_size / 1024:.0f} KB)')


if __name__ == '__main__':
    main()
