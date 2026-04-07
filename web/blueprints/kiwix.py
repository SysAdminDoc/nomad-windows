"""Kiwix ZIM library routes — catalog, download, delete, updates, Wikipedia tiers."""

import time
import threading
import logging

from flask import Blueprint, request, jsonify

from services import kiwix
from services.manager import _download_progress

log = logging.getLogger('nomad.web')

kiwix_bp = Blueprint('kiwix', __name__)


def _validate_download_url(url):
    """Validate that a download URL is safe (SSRF protection).

    Raises ValueError if the URL uses a non-https scheme or points to a
    private/internal IP address.
    """
    import ipaddress
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in ('https', 'http'):
        raise ValueError(f'Unsupported URL scheme: {parsed.scheme}')
    hostname = parsed.hostname or ''
    # Block obvious private hostnames
    if hostname in ('localhost', '') or hostname.endswith('.local'):
        raise ValueError('URLs pointing to internal hosts are not allowed')
    # Resolve and check for private/internal IPs (SSRF protection)
    try:
        import socket
        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(5)
        try:
            resolved = socket.getaddrinfo(hostname, None)
        finally:
            socket.setdefaulttimeout(old_timeout)
        for _family, _type, _proto, _canonname, sockaddr in resolved:
            ip = ipaddress.ip_address(sockaddr[0])
            if (ip.is_private or ip.is_loopback or ip.is_link_local
                    or ip.is_reserved or ip.is_multicast):
                raise ValueError('URL resolves to a blocked IP range')
    except (socket.gaierror, OSError):
        raise ValueError(f'Cannot resolve hostname: {hostname}')
    return url


# ─── Kiwix ZIM API ─────────────────────────────────────────────────

@kiwix_bp.route('/api/kiwix/zims')
def api_kiwix_zims():
    if not kiwix.is_installed():
        return jsonify([])
    return jsonify(kiwix.list_zim_files())

@kiwix_bp.route('/api/kiwix/catalog')
def api_kiwix_catalog():
    return jsonify(kiwix.get_catalog())

@kiwix_bp.route('/api/kiwix/download-zim', methods=['POST'])
def api_kiwix_download_zim():
    data = request.get_json() or {}
    url = data.get('url', kiwix.STARTER_ZIM_URL)
    filename = data.get('filename')

    # SSRF protection -- validate URL before downloading
    try:
        _validate_download_url(url)
    except ValueError as e:
        return jsonify({'error': f'Invalid download URL: {e}'}), 400

    def do_download():
        try:
            kiwix.download_zim(url, filename)
            if kiwix.running():
                log.info('Restarting Kiwix to load new ZIM content...')
                kiwix.stop()
                time.sleep(1)
                kiwix.start()
        except Exception as e:
            log.error(f'ZIM download failed: {e}')

    threading.Thread(target=do_download, daemon=True).start()
    return jsonify({'status': 'downloading'})

@kiwix_bp.route('/api/kiwix/zim-downloads')
def api_kiwix_zim_downloads():
    """Return all active/recent ZIM download progress entries."""
    zim_entries = {
        k.replace('kiwix-zim-', ''): v
        for k, v in _download_progress.items()
        if k.startswith('kiwix-zim-')
    }
    return jsonify(zim_entries)

@kiwix_bp.route('/api/kiwix/delete-zim', methods=['POST'])
def api_kiwix_delete_zim():
    data = request.get_json() or {}
    filename = data.get('filename')
    if not filename:
        return jsonify({'error': 'No filename'}), 400
    success = kiwix.delete_zim(filename)
    if not success:
        return jsonify({'error': 'Failed to delete ZIM file'}), 500
    return jsonify({'status': 'deleted'})

# ─── Content Update Checker ───────────────────────────────────────

@kiwix_bp.route('/api/kiwix/check-updates')
def api_kiwix_check_updates():
    """Compare installed ZIMs against catalog for newer versions."""
    if not kiwix.is_installed():
        return jsonify([])
    installed = kiwix.list_zim_files()
    catalog = kiwix.get_catalog()
    updates = []

    # Build lookup of all catalog entries by filename prefix
    catalog_by_prefix = {}
    for cat in catalog:
        for tier_name, zims in cat.get('tiers', {}).items():
            for z in zims:
                # Extract base name (before date portion)
                fname = z.get('filename', '')
                # e.g. "wikipedia_en_all_maxi_2026-02.zim" -> "wikipedia_en_all_maxi"
                parts = fname.rsplit('_', 1)
                if len(parts) == 2:
                    prefix = parts[0]
                else:
                    prefix = fname.replace('.zim', '')
                catalog_by_prefix[prefix] = z

    for inst in installed:
        inst_fname = inst.get('name', '') if isinstance(inst, dict) else str(inst)
        parts = inst_fname.rsplit('_', 1)
        prefix = parts[0] if len(parts) == 2 else inst_fname.replace('.zim', '')
        if prefix in catalog_by_prefix:
            cat_entry = catalog_by_prefix[prefix]
            if cat_entry['filename'] != inst_fname:
                updates.append({
                    'installed': inst_fname,
                    'available': cat_entry['filename'],
                    'name': cat_entry.get('name', ''),
                    'size': cat_entry.get('size', ''),
                    'url': cat_entry.get('url', ''),
                })
    return jsonify(updates)

# ─── Wikipedia Tier Selection ─────────────────────────────────────

@kiwix_bp.route('/api/kiwix/wikipedia-options')
def api_kiwix_wikipedia_options():
    """Return Wikipedia download tiers for dedicated selector."""
    catalog = kiwix.get_catalog()
    for cat in catalog:
        if cat.get('category', '').startswith('Wikipedia'):
            # Flatten all tiers into a list with tier labels
            options = []
            for tier_name, zims in cat.get('tiers', {}).items():
                for z in zims:
                    options.append({**z, 'tier': tier_name})
            return jsonify(options)
    return jsonify([])
