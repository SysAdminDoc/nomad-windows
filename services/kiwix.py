"""Kiwix service — offline Wikipedia and reference libraries."""

import os
import subprocess
import time
import logging
import requests
from services.manager import (
    get_services_dir, download_file, start_process, stop_process,
    is_running, check_port, _download_progress
)
from db import get_db

log = logging.getLogger('nomad.kiwix')

SERVICE_ID = 'kiwix'
KIWIX_PORT = 8888
KIWIX_TOOLS_URL = 'https://download.kiwix.org/release/kiwix-tools/kiwix-tools_win-x86_64-3.8.1.zip'
STARTER_ZIM_URL = 'https://download.kiwix.org/zim/wikipedia/wikipedia_en_100_mini_2025-06.zim'

# Curated ZIM catalog — popular offline content packs
ZIM_CATALOG = [
    {
        'category': 'Wikipedia',
        'items': [
            {'name': 'Wikipedia Mini (Top 100)', 'filename': 'wikipedia_en_100_mini_2025-06.zim',
             'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_en_100_mini_2025-06.zim',
             'size': '1.2 MB', 'desc': 'Top 100 Wikipedia articles — great for testing'},
            {'name': 'Wikipedia Top 100k', 'filename': 'wikipedia_en_top_nopic_2025-05.zim',
             'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_en_top_nopic_2025-05.zim',
             'size': '~3 GB', 'desc': 'Top 100,000 articles without pictures'},
            {'name': 'Wikipedia Full (No Pics)', 'filename': 'wikipedia_en_all_nopic_2025-05.zim',
             'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_en_all_nopic_2025-05.zim',
             'size': '~25 GB', 'desc': 'Complete English Wikipedia without images'},
        ]
    },
    {
        'category': 'Medical & Survival',
        'items': [
            {'name': 'WikiMed Medical Encyclopedia', 'filename': 'wikipedia_en_medicine_nopic_2025-05.zim',
             'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_en_medicine_nopic_2025-05.zim',
             'size': '~800 MB', 'desc': 'Medical articles from Wikipedia'},
            {'name': 'Wikibooks', 'filename': 'wikibooks_en_all_nopic_2025-05.zim',
             'url': 'https://download.kiwix.org/zim/wikibooks/wikibooks_en_all_nopic_2025-05.zim',
             'size': '~400 MB', 'desc': 'How-to guides and textbooks'},
        ]
    },
    {
        'category': 'Reference',
        'items': [
            {'name': 'Wiktionary', 'filename': 'wiktionary_en_all_nopic_2025-05.zim',
             'url': 'https://download.kiwix.org/zim/wiktionary/wiktionary_en_all_nopic_2025-05.zim',
             'size': '~5 GB', 'desc': 'Complete English dictionary'},
            {'name': 'Stack Exchange', 'filename': 'stackoverflow.com_en_all_2025-05.zim',
             'url': 'https://download.kiwix.org/zim/stack_exchange/stackoverflow.com_en_all_2025-05.zim',
             'size': '~55 GB', 'desc': 'Full Stack Overflow Q&A archive'},
        ]
    },
]


def get_install_dir():
    return os.path.join(get_services_dir(), 'kiwix')


def get_library_dir():
    path = os.path.join(get_install_dir(), 'library')
    os.makedirs(path, exist_ok=True)
    return path


def get_exe_path():
    """Find kiwix-serve.exe (may be in a subdirectory after extraction)."""
    install_dir = get_install_dir()
    exe = os.path.join(install_dir, 'kiwix-serve.exe')
    if os.path.isfile(exe):
        return exe
    for root, dirs, files in os.walk(install_dir):
        if 'kiwix-serve.exe' in files:
            return os.path.join(root, 'kiwix-serve.exe')
    return exe


def is_installed():
    return os.path.isfile(get_exe_path())


def install(callback=None):
    """Download and install kiwix-tools."""
    install_dir = get_install_dir()
    os.makedirs(install_dir, exist_ok=True)
    zip_path = os.path.join(install_dir, 'kiwix-tools.zip')

    _download_progress[SERVICE_ID] = {
        'percent': 0, 'status': 'downloading kiwix-tools', 'error': None,
        'speed': '', 'downloaded': 0, 'total': 0,
    }

    try:
        download_file(KIWIX_TOOLS_URL, zip_path, SERVICE_ID)

        _download_progress[SERVICE_ID]['status'] = 'extracting'
        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(install_dir)
        os.remove(zip_path)

        db = get_db()
        db.execute('''
            INSERT OR REPLACE INTO services (id, name, description, icon, category, installed, port, install_path, exe_path, url)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
        ''', (
            SERVICE_ID, 'Kiwix (Information Library)',
            'Offline Wikipedia, medical references, survival guides, and ebooks',
            'book', 'knowledge', KIWIX_PORT, install_dir, get_exe_path(),
            f'http://localhost:{KIWIX_PORT}'
        ))
        db.commit()
        db.close()

        _download_progress[SERVICE_ID] = {
            'percent': 100, 'status': 'complete', 'error': None,
            'speed': '', 'downloaded': 0, 'total': 0,
        }
        log.info('Kiwix installed successfully')

    except Exception as e:
        _download_progress[SERVICE_ID] = {
            'percent': 0, 'status': 'error', 'error': str(e),
            'speed': '', 'downloaded': 0, 'total': 0,
        }
        log.error(f'Kiwix install failed: {e}')
        raise


def list_zim_files():
    """List available ZIM files in the library directory."""
    library_dir = get_library_dir()
    zims = []
    for f in os.listdir(library_dir):
        if f.endswith('.zim'):
            path = os.path.join(library_dir, f)
            zims.append({
                'filename': f,
                'path': path,
                'size_mb': round(os.path.getsize(path) / (1024 * 1024), 1),
            })
    return zims


def get_catalog():
    """Return the curated ZIM catalog."""
    return ZIM_CATALOG


def download_zim(url: str, filename: str = None):
    """Download a ZIM file to the library directory."""
    if not filename:
        filename = url.split('/')[-1]
    dest = os.path.join(get_library_dir(), filename)
    download_file(url, dest, f'kiwix-zim-{filename}')
    return dest


def delete_zim(filename: str) -> bool:
    """Delete a ZIM file from the library."""
    path = os.path.join(get_library_dir(), filename)
    try:
        if os.path.isfile(path):
            os.remove(path)
            return True
    except Exception as e:
        log.error(f'Failed to delete ZIM {filename}: {e}')
    return False


def start():
    """Start kiwix-serve with all ZIM files in the library."""
    if not is_installed():
        raise RuntimeError('Kiwix is not installed')

    zims = list_zim_files()
    zim_paths = [z['path'] for z in zims]

    if not zim_paths:
        log.warning('No ZIM files found — kiwix-serve will start with no content')

    args = ['--port', str(KIWIX_PORT), '--address', '0.0.0.0'] + zim_paths
    exe = get_exe_path()

    CREATE_NO_WINDOW = 0x08000000
    proc = subprocess.Popen(
        [exe] + args,
        cwd=os.path.dirname(exe),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=CREATE_NO_WINDOW,
    )

    from services.manager import _processes
    _processes[SERVICE_ID] = proc

    db = get_db()
    db.execute('UPDATE services SET running = 1, pid = ? WHERE id = ?', (proc.pid, SERVICE_ID))
    db.commit()
    db.close()

    for _ in range(15):
        if check_port(KIWIX_PORT):
            log.info(f'Kiwix running on port {KIWIX_PORT} (PID {proc.pid})')
            return proc.pid
        time.sleep(1)

    return proc.pid


def stop():
    return stop_process(SERVICE_ID)


def running():
    return is_running(SERVICE_ID) and check_port(KIWIX_PORT)
