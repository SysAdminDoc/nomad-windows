"""
Built-in BitTorrent client for NOMAD Field Desk.
Uses libtorrent (python-libtorrent) for downloading torrent content.
Install: pip install python-libtorrent

Provides a singleton TorrentManager that the Flask app queries for status.
"""

import os
import re
import time
import base64
import threading
import logging
from typing import Optional

log = logging.getLogger('nomad.torrent')

try:
    import libtorrent as lt
    _LT_AVAILABLE = True
    log.info('libtorrent %s loaded', lt.__version__)
except ImportError:
    lt = None
    _LT_AVAILABLE = False
    log.info('libtorrent not installed — built-in torrent client unavailable. '
             'Install with: pip install python-libtorrent')


def _extract_hash_from_magnet(magnet: str) -> Optional[str]:
    """Extract the info-hash hex string from a magnet URI."""
    # Standard hex form
    m = re.search(r'xt=urn:btih:([a-fA-F0-9]{40})', magnet)
    if m:
        return m.group(1).lower()
    # Base32 form (32 chars)
    m = re.search(r'xt=urn:btih:([a-zA-Z2-7]{32})', magnet)
    if m:
        try:
            return base64.b32decode(m.group(1).upper()).hex()
        except Exception:
            pass
    return None


class TorrentManager:
    """Thread-safe libtorrent session manager."""

    # State codes libtorrent uses
    _STATE_NAMES = {
        0: 'Queued',
        1: 'Checking',
        2: 'Getting info',
        3: 'Downloading',
        4: 'Finished',
        5: 'Seeding',
        6: 'Allocating',
        7: 'Checking resume',
    }

    def __init__(self):
        self._session = None
        self._lock = threading.RLock()
        # hash -> lt handle
        self._handles: dict[str, object] = {}
        # hash -> metadata dict
        self._meta: dict[str, dict] = {}
        self._monitor_thread = None
        self._monitor_active = False

    # ── Session lifecycle ─────────────────────────────────────────────

    def _get_session(self):
        with self._lock:
            if self._session is None:
                settings = lt.settings_pack()
                settings[lt.settings_pack.user_agent] = 'NOMAD/1.3'
                settings[lt.settings_pack.alert_mask] = (
                    lt.alert.category_t.error_notification |
                    lt.alert.category_t.status_notification |
                    lt.alert.category_t.storage_notification
                )
                self._session = lt.session(settings)
                log.info('libtorrent session created')
            return self._session

    def shutdown(self):
        """Gracefully pause session on app exit."""
        monitor = None
        with self._lock:
            self._monitor_active = False
            monitor = self._monitor_thread
            self._monitor_thread = None
            if self._session:
                log.info('Shutting down libtorrent session')
                self._session.pause()
                self._session = None
            self._handles.clear()
            self._meta.clear()
        # Wait for monitor thread to exit outside the lock
        if monitor and monitor.is_alive():
            monitor.join(timeout=5)

    # ── Public API ────────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        return _LT_AVAILABLE

    def get_save_dir(self) -> str:
        from config import get_data_dir
        d = os.path.join(get_data_dir(), 'torrents')
        os.makedirs(d, exist_ok=True)
        return d

    def add_magnet(self, magnet: str, name: str = '', torrent_id: str = '') -> str:
        """
        Add a magnet link and start downloading.
        Returns the info-hash hex string used as the key.
        Raises RuntimeError if libtorrent is unavailable.
        """
        if not _LT_AVAILABLE:
            raise RuntimeError(
                'libtorrent is not installed. '
                'Run: pip install python-libtorrent'
            )

        info_hash = _extract_hash_from_magnet(magnet)
        if not info_hash:
            raise ValueError('Could not parse info hash from magnet link')

        with self._lock:
            if info_hash in self._handles:
                # Already added — just resume if paused
                h = self._handles[info_hash]
                if h.is_valid():
                    h.resume()
                return info_hash

        save_path = self.get_save_dir()

        ses = self._get_session()

        atp = lt.parse_magnet_uri(magnet)
        atp.save_path = save_path
        # Don't auto-manage so we control start/stop
        atp.flags &= ~lt.torrent_flags.auto_managed
        atp.flags |= lt.torrent_flags.sequential_download

        with self._lock:
            handle = ses.add_torrent(atp)
            handle.resume()
            self._handles[info_hash] = handle
            self._meta[info_hash] = {
                'name': name or 'Fetching metadata...',
                'torrent_id': torrent_id,
                'magnet': magnet,
                'added': time.time(),
                'save_path': save_path,
                'error': '',
            }

        self._ensure_monitor()
        log.info('Torrent added: %s  hash=%s', name, info_hash)
        return info_hash

    def get_status(self, info_hash: str) -> dict:
        """Return a status dict for one torrent."""
        with self._lock:
            handle = self._handles.get(info_hash)
            meta = dict(self._meta.get(info_hash, {}))

        if not handle or not handle.is_valid():
            return {'error': 'not found', 'hash': info_hash}

        try:
            s = handle.status()
        except Exception as e:
            return {'error': str(e), 'hash': info_hash}

        # State name — handle both int-style and enum-style
        state_val = int(s.state)
        state_name = self._STATE_NAMES.get(state_val, str(s.state))

        # Name from status or meta
        name = (s.name or '').strip() or meta.get('name', 'Unknown')

        total = max(s.total_wanted, 0)
        done = max(s.total_wanted_done, 0)
        progress = round(s.progress * 100, 1)

        dl_rate = max(s.download_rate, 0)   # bytes/s
        ul_rate = max(s.upload_rate, 0)

        eta_sec = None
        if dl_rate > 0 and total > done:
            eta_sec = int((total - done) / dl_rate)

        return {
            'hash': info_hash,
            'torrent_id': meta.get('torrent_id', ''),
            'name': name,
            'state': state_name,
            'progress': progress,
            'total': total,
            'done': done,
            'dl_rate': dl_rate,
            'ul_rate': ul_rate,
            'peers': s.num_peers,
            'seeds': s.num_seeds,
            'eta_sec': eta_sec,
            'save_path': meta.get('save_path', ''),
            'paused': bool(s.paused),
            'error': meta.get('error', '') or (s.errc.message() if s.errc else ''),
            'added': meta.get('added', 0),
        }

    def get_all_status(self) -> list:
        with self._lock:
            keys = list(self._handles.keys())
        return [self.get_status(h) for h in keys]

    def pause(self, info_hash: str):
        with self._lock:
            h = self._handles.get(info_hash)
        if h and h.is_valid():
            h.pause()

    def resume(self, info_hash: str):
        with self._lock:
            h = self._handles.get(info_hash)
        if h and h.is_valid():
            h.resume()

    def remove(self, info_hash: str, delete_files: bool = False):
        with self._lock:
            h = self._handles.pop(info_hash, None)
            self._meta.pop(info_hash, None)
            session = self._session
        if h and h.is_valid() and session:
            flags = lt.session.delete_files if delete_files else 0
            session.remove_torrent(h, flags)
        log.info('Torrent removed: hash=%s delete_files=%s', info_hash, delete_files)

    def open_save_folder(self, info_hash: str):
        """Open the save folder in the platform's file manager."""
        from platform_utils import open_folder
        with self._lock:
            meta = self._meta.get(info_hash, {})
        folder = meta.get('save_path', self.get_save_dir())
        open_folder(folder)

    # ── Monitor thread ────────────────────────────────────────────────

    def _ensure_monitor(self):
        with self._lock:
            if not self._monitor_active:
                self._monitor_active = True
                t = threading.Thread(target=self._monitor_loop, daemon=True, name='torrent-monitor')
                t.start()
                self._monitor_thread = t

    def _monitor_loop(self):
        """Background loop: process libtorrent alerts, log completion."""
        while self._monitor_active:
            time.sleep(1)
            with self._lock:
                session = self._session
            if not session:
                break

            try:
                alerts = session.pop_alerts()
                for a in alerts:
                    if isinstance(a, lt.torrent_error_alert):
                        ih = str(a.handle.info_hash())
                        with self._lock:
                            if ih in self._meta:
                                self._meta[ih]['error'] = a.message()
                        log.error('Torrent error [%s]: %s', ih[:8], a.message())

                    elif isinstance(a, lt.torrent_finished_alert):
                        name = a.handle.status().name or '?'
                        log.info('Torrent finished: %s', name)

                    elif isinstance(a, lt.metadata_received_alert):
                        ih = str(a.handle.info_hash())
                        s = a.handle.status()
                        if s.name:
                            with self._lock:
                                if ih in self._meta:
                                    self._meta[ih]['name'] = s.name
            except Exception as e:
                log.debug('Monitor loop error: %s', e)

            # Stop monitor when nothing is downloading or pending
            with self._lock:
                active = bool(self._handles)
                if not active:
                    self._monitor_active = False
            if not active:
                break

        log.debug('Torrent monitor thread exited')


# ── Singleton ─────────────────────────────────────────────────────────

_manager = TorrentManager()


def get_manager() -> TorrentManager:
    return _manager


def is_available() -> bool:
    return _LT_AVAILABLE
