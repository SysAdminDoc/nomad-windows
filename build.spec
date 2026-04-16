# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for NOMAD Field Desk
# Build: pyinstaller build.spec

import os
import sys
import importlib.util

_is_windows = sys.platform == 'win32'
_is_macos = sys.platform == 'darwin'

_hiddenimports = [
    'flask',
    'requests',
    'webview',
    'pystray',
    'PIL',
    'psutil',
    'PyPDF2',
    'sqlite3',
    'http.server',
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
    'web.state',
    'web.sql_safety',
    'web.validation',
    'web.translations',
    'web.blueprints',
    'web.blueprints.ai',
    'web.blueprints.benchmark',
    'web.blueprints.checklists',
    'web.blueprints.comms',
    'web.blueprints.contacts',
    'web.blueprints.exercises',
    'web.blueprints.federation',
    'web.blueprints.garden',
    'web.blueprints.inventory',
    'web.blueprints.kb',
    'web.blueprints.kiwix',
    'web.blueprints.maps',
    'web.blueprints.media',
    'web.blueprints.medical',
    'web.blueprints.notes',
    'web.blueprints.power',
    'web.blueprints.preparedness',
    'web.blueprints.print_routes',
    'web.blueprints.security',
    'web.blueprints.services',
    'web.blueprints.situation_room',
    'web.blueprints.supplies',
    'web.blueprints.system',
    'web.blueprints.tasks',
    'web.blueprints.undo',
    'web.blueprints.weather',
    'web.blueprints.kit_builder',
    'web.blueprints.emergency',
    'web.blueprints.family',
    'web.blueprints.brief',
    'web.blueprints.water_mgmt',
    'web.blueprints.financial',
    'web.blueprints.vehicles',
    'web.blueprints.loadout',
    'web.blueprints.readiness_goals',
    'web.blueprints.alert_rules',
    'web.blueprints.timeline',
    'web.blueprints.threat_intel',
    'web.blueprints.evac_drills',
    'web.blueprints.data_packs',
    'web.blueprints.regional_profile',
    'web.blueprints.nutrition',
    'web.blueprints.consumption',
    'web.blueprints.meal_planning',
    'web.blueprints.movement_ops',
    'web.blueprints.tactical_comms',
    'web.blueprints.land_assessment',
    'web.blueprints.medical_phase2',
    'web.blueprints.training_knowledge',
    'web.blueprints.group_ops',
    'web.blueprints.security_opsec',
    'web.blueprints.agriculture',
    'web.blueprints.disaster_modules',
    'web.blueprints.daily_living',
    'web.blueprints.interoperability',
    'web.blueprints.hunting_foraging',
    'web.blueprints.hardware_sensors',
    'web.blueprints.platform_security',
    'web.blueprints.specialized_modules',
    'web.auth',
    'web.print_templates',
    'web.utils',
    'web.checklist_templates_data',
    'platform_utils',
    'log_utils',
    'config',
    'yt_dlp',
]

for _optional_hiddenimport in (
    'engineio.async_drivers.threading',
    'libtorrent',
):
    try:
        _optional_spec = importlib.util.find_spec(_optional_hiddenimport)
    except ModuleNotFoundError:
        _optional_spec = None
    if _optional_spec:
        _hiddenimports.append(_optional_hiddenimport)


a = Analysis(
    ['nomad.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('web/templates', 'web/templates'),
        ('web/static', 'web/static'),
        ('web/nukemap', 'web/nukemap'),
        ('web/viptrack', 'web/viptrack'),
        ('web/__init__.py', 'web'),
        ('web/app.py', 'web'),
        ('web/catalog.py', 'web'),
        ('web/state.py', 'web'),
        ('web/sql_safety.py', 'web'),
        ('web/validation.py', 'web'),
        ('web/translations.py', 'web'),
        ('web/blueprints', 'web/blueprints'),
        ('web/routes_advanced.py', 'web'),
        ('web/utils.py', 'web'),
        ('web/auth.py', 'web'),
        ('web/plugins.py', 'web'),
        ('web/print_templates.py', 'web'),
        ('web/checklist_templates_data.py', 'web'),
        ('services', 'services'),
        # Root-level modules — bundled once each.
        ('db.py', '.'),
        ('db_migrations', 'db_migrations'),
        ('config.py', '.'),
        ('platform_utils.py', '.'),
        ('log_utils.py', '.'),
    ],
    hiddenimports=_hiddenimports,
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
    name='NOMADFieldDesk',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
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
