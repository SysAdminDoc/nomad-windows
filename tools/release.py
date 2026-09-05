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
        check=False,
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
        check=False,
    )
    if result.returncode != 0:
        print('  npm build FAILED')
        print(result.stderr[-500:] if result.stderr else '')
        return False
    print('  Bundle built')
    return True


def write_windows_version_info(build_dir, version):
    """Write the Windows version resource consumed by PyInstaller."""
    numeric = [int(part) for part in version.split('.')]
    if len(numeric) > 4:
        raise ValueError(f'Windows version has too many components: {version}')
    numeric.extend([0] * (4 - len(numeric)))
    version_tuple = ', '.join(str(part) for part in numeric)
    version_info = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({version_tuple}),
    prodvers=({version_tuple}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0),
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', 'SysAdminDoc'),
        StringStruct('FileDescription', 'NOMAD Field Desk'),
        StringStruct('FileVersion', '{version}'),
        StringStruct('InternalName', 'NOMADFieldDesk'),
        StringStruct('LegalCopyright', 'Copyright SysAdminDoc'),
        StringStruct('OriginalFilename', 'NOMADFieldDesk.exe'),
        StringStruct('ProductName', 'NOMAD Field Desk'),
        StringStruct('ProductVersion', '{version}'),
      ]),
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])]),
  ],
)
"""
    version_path = build_dir / 'version_info.txt'
    version_path.write_text(version_info, encoding='utf-8')
    return version_path


def run_pyinstaller(version):
    print('Building PyInstaller executable...')
    dist_dir = REPO_ROOT / 'dist'
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    build_dir = REPO_ROOT / 'build'
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True)
    if sys.platform == 'win32':
        version_info = write_windows_version_info(build_dir, version)
        print(f'  Version resource: {version_info.relative_to(REPO_ROOT)}')

    result = subprocess.run(
        [sys.executable, '-m', 'PyInstaller', 'build.spec', '--noconfirm'],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
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


def find_inno_compiler():
    """Return the installed Inno Setup compiler on Windows."""
    if sys.platform != 'win32':
        return None
    candidates = [
        Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Inno Setup 6' / 'ISCC.exe',
        Path(os.environ.get('ProgramFiles(x86)', '')) / 'Inno Setup 6' / 'ISCC.exe',
        Path(os.environ.get('ProgramFiles', '')) / 'Inno Setup 6' / 'ISCC.exe',
    ]
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def run_inno_setup():
    """Build the Windows installer and place it beside the portable executable."""
    if sys.platform != 'win32':
        return True
    compiler = find_inno_compiler()
    if not compiler:
        print('  ERROR: Inno Setup 6 was not found')
        return False

    root_installer = REPO_ROOT / 'NOMAD-Setup.exe'
    dist_installer = REPO_ROOT / 'dist' / 'NOMAD-Setup.exe'
    root_installer.unlink(missing_ok=True)
    dist_installer.unlink(missing_ok=True)

    print('Building Inno Setup installer...')
    result = subprocess.run(
        [str(compiler), '/Qp', 'installer.iss'],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if result.returncode != 0 or not root_installer.exists():
        print('  Inno Setup FAILED')
        print((result.stdout or result.stderr)[-1000:])
        return False

    shutil.move(str(root_installer), str(dist_installer))
    size_mb = dist_installer.stat().st_size / (1024 * 1024)
    print(f'  Built: {dist_installer.name} ({size_mb:.1f} MB)')

    portable_path = REPO_ROOT / 'dist' / 'NOMADFieldDesk.exe'
    release_portable_path = REPO_ROOT / 'dist' / 'NOMADFieldDesk-Windows.exe'
    if not portable_path.is_file():
        print(f'  ERROR: {portable_path} is missing before release naming')
        return False
    release_portable_path.unlink(missing_ok=True)
    portable_path.replace(release_portable_path)
    print(f'  Release portable: {release_portable_path.name}')
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
        if not run_pyinstaller(version):
            print('\nABORTED: fix PyInstaller build before release.')
            sys.exit(1)
        if not run_inno_setup():
            print('\nABORTED: fix the Windows installer build before release.')
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
