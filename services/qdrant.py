"""Qdrant vector database service — enables RAG/knowledge base for AI chat."""

import os
import subprocess
import time
import logging
import requests as req
from services.manager import (
    get_services_dir, download_file, stop_process, is_running, check_port, _download_progress
)
from db import get_db

log = logging.getLogger('nomad.qdrant')

SERVICE_ID = 'qdrant'
QDRANT_PORT = 6333
QDRANT_GRPC_PORT = 6334
QDRANT_RELEASE_API = 'https://api.github.com/repos/qdrant/qdrant/releases/latest'

COLLECTION_NAME = 'nomad_kb'
VECTOR_SIZE = 768  # nomic-embed-text v1.5
EMBED_MODEL = 'nomic-embed-text:v1.5'


def get_install_dir():
    return os.path.join(get_services_dir(), 'qdrant')


def get_storage_dir():
    path = os.path.join(get_install_dir(), 'storage')
    os.makedirs(path, exist_ok=True)
    return path


def get_exe_path():
    install_dir = get_install_dir()
    exe = os.path.join(install_dir, 'qdrant.exe')
    if os.path.isfile(exe):
        return exe
    for root, dirs, files in os.walk(install_dir):
        if 'qdrant.exe' in files:
            return os.path.join(root, 'qdrant.exe')
    return exe


def is_installed():
    return os.path.isfile(get_exe_path())


def install(callback=None):
    """Download Qdrant from GitHub releases."""
    install_dir = get_install_dir()
    os.makedirs(install_dir, exist_ok=True)
    zip_path = os.path.join(install_dir, 'qdrant.zip')

    _download_progress[SERVICE_ID] = {
        'percent': 0, 'status': 'downloading', 'error': None,
        'speed': '', 'downloaded': 0, 'total': 0,
    }

    try:
        # Resolve download URL from GitHub releases
        rel = req.get(QDRANT_RELEASE_API, timeout=15).json()
        zip_url = None
        for asset in rel.get('assets', []):
            if 'windows' in asset['name'].lower() and asset['name'].endswith('.zip'):
                zip_url = asset['browser_download_url']
                break
        if not zip_url:
            raise RuntimeError('Could not find Qdrant download for Windows. Check your internet connection and try again.')

        download_file(zip_url, zip_path, SERVICE_ID)

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
            SERVICE_ID, 'Qdrant (Vector DB)',
            'Vector database for knowledge base semantic search and RAG',
            'database', 'ai', QDRANT_PORT, install_dir, get_exe_path(),
            f'http://localhost:{QDRANT_PORT}'
        ))
        db.commit()
        db.close()

        _download_progress[SERVICE_ID] = {
            'percent': 100, 'status': 'complete', 'error': None,
            'speed': '', 'downloaded': 0, 'total': 0,
        }
        log.info('Qdrant installed successfully')

    except Exception as e:
        _download_progress[SERVICE_ID] = {
            'percent': 0, 'status': 'error', 'error': str(e),
            'speed': '', 'downloaded': 0, 'total': 0,
        }
        log.error(f'Qdrant install failed: {e}')
        raise


def start():
    """Start Qdrant server."""
    if not is_installed():
        raise RuntimeError('Qdrant is not installed')

    exe = get_exe_path()
    storage = get_storage_dir()

    CREATE_NO_WINDOW = 0x08000000
    env = os.environ.copy()
    env['QDRANT__SERVICE__HTTP_PORT'] = str(QDRANT_PORT)
    env['QDRANT__SERVICE__GRPC_PORT'] = str(QDRANT_GRPC_PORT)
    env['QDRANT__STORAGE__STORAGE_PATH'] = storage

    proc = subprocess.Popen(
        [exe],
        cwd=os.path.dirname(exe),
        env=env,
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

    for _ in range(20):
        if check_port(QDRANT_PORT):
            log.info(f'Qdrant running on port {QDRANT_PORT} (PID {proc.pid})')
            ensure_collection()
            return proc.pid
        time.sleep(1)

    log.warning('Qdrant started but port not yet responding')
    return proc.pid


def stop():
    return stop_process(SERVICE_ID)


def running():
    return is_running(SERVICE_ID) and check_port(QDRANT_PORT)


def ensure_collection():
    """Create the KB collection if it doesn't exist."""
    try:
        r = req.get(f'http://localhost:{QDRANT_PORT}/collections/{COLLECTION_NAME}', timeout=5)
        if r.status_code == 200:
            return True
    except Exception:
        pass

    try:
        req.put(
            f'http://localhost:{QDRANT_PORT}/collections/{COLLECTION_NAME}',
            json={
                'vectors': {
                    'size': VECTOR_SIZE,
                    'distance': 'Cosine',
                }
            },
            timeout=10,
        )
        log.info(f'Created Qdrant collection: {COLLECTION_NAME}')
        return True
    except Exception as e:
        log.error(f'Failed to create collection: {e}')
        return False


def upsert_vectors(points: list[dict]):
    """Upsert points into the KB collection. Each point: {id, vector, payload}."""
    try:
        req.put(
            f'http://localhost:{QDRANT_PORT}/collections/{COLLECTION_NAME}/points',
            json={'points': points},
            timeout=30,
        )
        return True
    except Exception as e:
        log.error(f'Qdrant upsert failed: {e}')
        return False


def search(vector: list[float], limit: int = 5) -> list[dict]:
    """Search the KB collection by vector similarity."""
    try:
        r = req.post(
            f'http://localhost:{QDRANT_PORT}/collections/{COLLECTION_NAME}/points/search',
            json={
                'vector': vector,
                'limit': limit,
                'with_payload': True,
            },
            timeout=10,
        )
        if r.ok:
            return r.json().get('result', [])
    except Exception as e:
        log.error(f'Qdrant search failed: {e}')
    return []


def delete_by_doc_id(doc_id: int):
    """Delete all vectors for a given document ID."""
    try:
        req.post(
            f'http://localhost:{QDRANT_PORT}/collections/{COLLECTION_NAME}/points/delete',
            json={
                'filter': {
                    'must': [{'key': 'doc_id', 'match': {'value': doc_id}}]
                }
            },
            timeout=10,
        )
        return True
    except Exception as e:
        log.error(f'Qdrant delete failed: {e}')
        return False


def get_collection_info():
    """Get collection stats."""
    try:
        r = req.get(f'http://localhost:{QDRANT_PORT}/collections/{COLLECTION_NAME}', timeout=5)
        if r.ok:
            data = r.json().get('result', {})
            return {
                'points_count': data.get('points_count', 0),
                'vectors_count': data.get('vectors_count', 0),
            }
    except Exception:
        pass
    return {'points_count': 0, 'vectors_count': 0}
