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

# Curated ZIM catalog — tiered categories matching Project N.O.M.A.D.
ZIM_CATALOG = [
    {
        'category': 'Wikipedia',
        'tiers': {
            'essential': [
                {'name': 'Wikipedia Mini (Top 100)', 'filename': 'wikipedia_en_100_mini_2025-06.zim',
                 'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_en_100_mini_2025-06.zim',
                 'size': '1.2 MB', 'desc': 'Top 100 articles — quick reference'},
            ],
            'standard': [
                {'name': 'Wikipedia Top 100k (No Pics)', 'filename': 'wikipedia_en_top_nopic_2025-05.zim',
                 'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_en_top_nopic_2025-05.zim',
                 'size': '~3 GB', 'desc': 'Top 100,000 articles without images'},
            ],
            'comprehensive': [
                {'name': 'Wikipedia Full (No Pics)', 'filename': 'wikipedia_en_all_nopic_2025-05.zim',
                 'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_en_all_nopic_2025-05.zim',
                 'size': '~25 GB', 'desc': 'Complete English Wikipedia without images'},
                {'name': 'Wikipedia Full (With Pics)', 'filename': 'wikipedia_en_all_maxi_2025-05.zim',
                 'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_en_all_maxi_2025-05.zim',
                 'size': '~102 GB', 'desc': 'Complete English Wikipedia with all images'},
            ],
        },
    },
    {
        'category': 'Medicine',
        'tiers': {
            'essential': [
                {'name': 'WikiMed Medical Encyclopedia', 'filename': 'wikipedia_en_medicine_nopic_2025-05.zim',
                 'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_en_medicine_nopic_2025-05.zim',
                 'size': '~800 MB', 'desc': 'Medical articles from Wikipedia'},
            ],
            'standard': [
                {'name': 'WikiMed Medical Encyclopedia', 'filename': 'wikipedia_en_medicine_nopic_2025-05.zim',
                 'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_en_medicine_nopic_2025-05.zim',
                 'size': '~800 MB', 'desc': 'Medical articles from Wikipedia'},
                {'name': 'MedlinePlus Health Topics', 'filename': 'medlineplus.gov_en_all_2024-10.zim',
                 'url': 'https://download.kiwix.org/zim/other/medlineplus.gov_en_all_2024-10.zim',
                 'size': '~500 MB', 'desc': 'NIH consumer health information'},
            ],
            'comprehensive': [
                {'name': 'WikiMed Medical Encyclopedia', 'filename': 'wikipedia_en_medicine_nopic_2025-05.zim',
                 'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_en_medicine_nopic_2025-05.zim',
                 'size': '~800 MB', 'desc': 'Medical articles from Wikipedia'},
                {'name': 'MedlinePlus Health Topics', 'filename': 'medlineplus.gov_en_all_2024-10.zim',
                 'url': 'https://download.kiwix.org/zim/other/medlineplus.gov_en_all_2024-10.zim',
                 'size': '~500 MB', 'desc': 'NIH consumer health information'},
                {'name': 'WHO Factsheets', 'filename': 'who.int_en_all_2024-06.zim',
                 'url': 'https://download.kiwix.org/zim/other/who.int_en_all_2024-06.zim',
                 'size': '~1.5 GB', 'desc': 'World Health Organization resources'},
            ],
        },
    },
    {
        'category': 'Survival & Preparedness',
        'tiers': {
            'essential': [
                {'name': 'Wikibooks (Guides & Manuals)', 'filename': 'wikibooks_en_all_nopic_2025-05.zim',
                 'url': 'https://download.kiwix.org/zim/wikibooks/wikibooks_en_all_nopic_2025-05.zim',
                 'size': '~400 MB', 'desc': 'How-to guides, textbooks, field manuals'},
            ],
            'standard': [
                {'name': 'Wikibooks (Guides & Manuals)', 'filename': 'wikibooks_en_all_nopic_2025-05.zim',
                 'url': 'https://download.kiwix.org/zim/wikibooks/wikibooks_en_all_nopic_2025-05.zim',
                 'size': '~400 MB', 'desc': 'How-to guides, textbooks, field manuals'},
                {'name': 'Wikivoyage Travel Guide', 'filename': 'wikivoyage_en_all_nopic_2025-05.zim',
                 'url': 'https://download.kiwix.org/zim/wikivoyage/wikivoyage_en_all_nopic_2025-05.zim',
                 'size': '~600 MB', 'desc': 'Worldwide travel and survival information'},
            ],
            'comprehensive': [
                {'name': 'Wikibooks (Guides & Manuals)', 'filename': 'wikibooks_en_all_nopic_2025-05.zim',
                 'url': 'https://download.kiwix.org/zim/wikibooks/wikibooks_en_all_nopic_2025-05.zim',
                 'size': '~400 MB', 'desc': 'How-to guides, textbooks, field manuals'},
                {'name': 'Wikivoyage Travel Guide', 'filename': 'wikivoyage_en_all_nopic_2025-05.zim',
                 'url': 'https://download.kiwix.org/zim/wikivoyage/wikivoyage_en_all_nopic_2025-05.zim',
                 'size': '~600 MB', 'desc': 'Worldwide travel and survival information'},
                {'name': 'iFixit Repair Guides', 'filename': 'ifixit_en_all_2024-10.zim',
                 'url': 'https://download.kiwix.org/zim/other/ifixit_en_all_2024-10.zim',
                 'size': '~3 GB', 'desc': 'Electronics and device repair guides'},
            ],
        },
    },
    {
        'category': 'Computing & Technology',
        'tiers': {
            'essential': [
                {'name': 'Stack Overflow', 'filename': 'stackoverflow.com_en_all_2025-05.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/stackoverflow.com_en_all_2025-05.zim',
                 'size': '~55 GB', 'desc': 'Full Stack Overflow Q&A archive'},
            ],
            'standard': [
                {'name': 'Stack Overflow', 'filename': 'stackoverflow.com_en_all_2025-05.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/stackoverflow.com_en_all_2025-05.zim',
                 'size': '~55 GB', 'desc': 'Full Stack Overflow Q&A archive'},
                {'name': 'DevDocs API Documentation', 'filename': 'devdocs.io_en_all_2024-09.zim',
                 'url': 'https://download.kiwix.org/zim/other/devdocs.io_en_all_2024-09.zim',
                 'size': '~800 MB', 'desc': 'Offline API docs for 100+ languages'},
            ],
            'comprehensive': [
                {'name': 'Stack Overflow', 'filename': 'stackoverflow.com_en_all_2025-05.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/stackoverflow.com_en_all_2025-05.zim',
                 'size': '~55 GB', 'desc': 'Full Stack Overflow Q&A archive'},
                {'name': 'DevDocs API Documentation', 'filename': 'devdocs.io_en_all_2024-09.zim',
                 'url': 'https://download.kiwix.org/zim/other/devdocs.io_en_all_2024-09.zim',
                 'size': '~800 MB', 'desc': 'Offline API docs for 100+ languages'},
                {'name': 'Super User', 'filename': 'superuser.com_en_all_2025-05.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/superuser.com_en_all_2025-05.zim',
                 'size': '~5 GB', 'desc': 'Computer power user Q&A'},
            ],
        },
    },
    {
        'category': 'Science & Engineering',
        'tiers': {
            'essential': [
                {'name': 'Wikipedia Science Portal', 'filename': 'wikipedia_en_science_nopic_2025-05.zim',
                 'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_en_science_nopic_2025-05.zim',
                 'size': '~1.5 GB', 'desc': 'Science-focused Wikipedia articles'},
            ],
            'standard': [
                {'name': 'Wikipedia Science Portal', 'filename': 'wikipedia_en_science_nopic_2025-05.zim',
                 'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_en_science_nopic_2025-05.zim',
                 'size': '~1.5 GB', 'desc': 'Science-focused Wikipedia articles'},
                {'name': 'Wiktionary', 'filename': 'wiktionary_en_all_nopic_2025-05.zim',
                 'url': 'https://download.kiwix.org/zim/wiktionary/wiktionary_en_all_nopic_2025-05.zim',
                 'size': '~5 GB', 'desc': 'Complete English dictionary'},
            ],
            'comprehensive': [
                {'name': 'Wikipedia Science Portal', 'filename': 'wikipedia_en_science_nopic_2025-05.zim',
                 'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_en_science_nopic_2025-05.zim',
                 'size': '~1.5 GB', 'desc': 'Science-focused Wikipedia articles'},
                {'name': 'Wiktionary', 'filename': 'wiktionary_en_all_nopic_2025-05.zim',
                 'url': 'https://download.kiwix.org/zim/wiktionary/wiktionary_en_all_nopic_2025-05.zim',
                 'size': '~5 GB', 'desc': 'Complete English dictionary'},
                {'name': 'Mathematics SE', 'filename': 'math.stackexchange.com_en_all_2025-05.zim',
                 'url': 'https://download.kiwix.org/zim/stack_exchange/math.stackexchange.com_en_all_2025-05.zim',
                 'size': '~8 GB', 'desc': 'Mathematics Q&A from Stack Exchange'},
            ],
        },
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


def get_catalog_flat():
    """Return a flat list of all ZIM items across all tiers (for backward compat)."""
    items = []
    seen = set()
    for cat in ZIM_CATALOG:
        for tier_name, tier_items in cat.get('tiers', {}).items():
            for item in tier_items:
                if item['filename'] not in seen:
                    seen.add(item['filename'])
                    items.append({**item, 'category': cat['category'], 'tier': tier_name})
    return items


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
