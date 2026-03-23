# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Project N.O.M.A.D. for Windows
# Build: pyinstaller build.spec

import os

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
        ('services', 'services'),
        ('db.py', '.'),
        ('config.py', '.'),
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
        'web.catalog',
        'libtorrent',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'test'],
    noarchive=False,
)

pyz = PYZ(a.pure)

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
    icon='icon.ico',
)
