# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Project N.O.M.A.D. Desktop
# Build: pyinstaller build.spec

import os
import sys

_is_windows = sys.platform == 'win32'
_is_macos = sys.platform == 'darwin'

a = Analysis(
    ['nomad.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('web/templates', 'web/templates'),
        ('web/static', 'web/static'),
        ('web/nukemap', 'web/nukemap'),
        ('web/__init__.py', 'web'),
        ('web/catalog.py', 'web'),
        ('web/routes_advanced.py', 'web'),
        ('services', 'services'),
        ('db.py', '.'),
        ('config.py', '.'),
        ('platform_utils.py', '.'),
    ],
    hiddenimports=[
        'flask',
        'requests',
        'webview',
        'pystray',
        'PIL',
        'psutil',
        'PyPDF2',
        'sqlite3',
        'http.server',
        'engineio.async_drivers.threading',
        'services',
        'services.ollama',
        'services.kiwix',
        'services.cyberchef',
        'services.kolibri',
        'services.qdrant',
        'services.stirling',
        'services.manager',
        'services.torrent',
        'services.flatnotes',
        'web.catalog',
        'web.routes_advanced',
        'libtorrent',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'test'],
    noarchive=False,
)

pyz = PYZ(a.pure)

# Platform-appropriate icon
_icon = None
if _is_windows and os.path.isfile('icon.ico'):
    _icon = 'icon.ico'
elif _is_macos and os.path.isfile('icon.icns'):
    _icon = 'icon.icns'

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ProjectNOMAD',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
)
