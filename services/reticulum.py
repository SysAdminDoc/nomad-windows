"""Reticulum Network Stack (RNS) service manager.

Manages a local RNS instance for mesh networking. Supports multiple
interface types: TCP (LAN/WAN), UDP (broadcast), Serial (LoRa radios),
and AutoInterface (automatic local peer discovery).

RNS + LXMF enable fully off-grid, encrypted, delay-tolerant messaging
between NOMAD nodes without requiring internet or centralized infrastructure.

Dependencies: rns, lxmf (pip install rns lxmf)
"""

import json
import logging
import os
import threading
import time

_log = logging.getLogger('nomad.reticulum')

# Lazy imports — RNS may not be installed
_rns = None
_lxmf = None
_rns_available = None

# Singleton state
_reticulum = None        # RNS.Reticulum instance
_identity = None         # RNS.Identity — this node's keypair
_lxmf_router = None      # LXMF.LXMRouter
_lxmf_delivery = None    # LXMF delivery callback destination
_message_callback = None # Callable for incoming messages
_lock = threading.Lock()
_announce_interval = 600  # seconds between re-announcements


def available():
    """Check if RNS + LXMF packages are installed."""
    global _rns_available, _rns, _lxmf
    if _rns_available is not None:
        return _rns_available
    try:
        import RNS
        import LXMF
        _rns = RNS
        _lxmf = LXMF
        _rns_available = True
    except ImportError:
        _rns_available = False
    return _rns_available


def running():
    """Check if Reticulum is initialized and running."""
    return _reticulum is not None


def get_identity_hash():
    """Return this node's RNS identity hash as hex string."""
    if _identity:
        return _identity.hexhash
    return None


def get_status():
    """Return current Reticulum status dict."""
    if not available():
        return {
            'available': False,
            'running': False,
            'error': 'RNS not installed. Install with: pip install rns lxmf',
        }

    if not running():
        return {
            'available': True,
            'running': False,
            'identity': None,
        }

    status = {
        'available': True,
        'running': True,
        'identity': _identity.hexhash if _identity else None,
        'transport_enabled': _reticulum.is_transport_instance() if _reticulum else False,
    }

    # Count known destinations and active interfaces
    try:
        status['known_destinations'] = len(_rns.Transport.destinations_table) if hasattr(_rns.Transport, 'destinations_table') else 0
        status['active_interfaces'] = len([i for i in _reticulum.get_interfaces() if i.online]) if _reticulum else 0
        status['interfaces'] = []
        if _reticulum:
            for iface in _reticulum.get_interfaces():
                status['interfaces'].append({
                    'name': str(iface),
                    'online': iface.online,
                    'type': type(iface).__name__,
                })
    except Exception:
        pass

    return status


def start(config_dir=None, transport=False):
    """Initialize Reticulum and LXMF.

    Args:
        config_dir: Directory for RNS config and identity. Defaults to NOMAD data dir.
        transport: If True, enable Transport mode (relay packets for other nodes).
    """
    global _reticulum, _identity, _lxmf_router, _lxmf_delivery

    if not available():
        raise RuntimeError('RNS not installed. Install with: pip install rns lxmf')

    if running():
        _log.info('Reticulum already running')
        return

    with _lock:
        if running():
            return

        if not config_dir:
            import config as nomad_config
            config_dir = os.path.join(nomad_config.get_data_dir(), 'reticulum')
        os.makedirs(config_dir, exist_ok=True)

        _log.info('Starting Reticulum (config_dir=%s, transport=%s)', config_dir, transport)

        try:
            # Initialize RNS
            _reticulum = _rns.Reticulum(configdir=config_dir)

            if transport:
                _reticulum.enable_transport()

            # Load or create identity
            identity_path = os.path.join(config_dir, 'nomad_identity')
            if os.path.isfile(identity_path):
                _identity = _rns.Identity.from_file(identity_path)
                _log.info('Loaded existing identity: %s', _identity.hexhash)
            else:
                _identity = _rns.Identity()
                _identity.to_file(identity_path)
                _log.info('Created new identity: %s', _identity.hexhash)

            # Set up LXMF router for messaging
            storage_path = os.path.join(config_dir, 'lxmf_storage')
            os.makedirs(storage_path, exist_ok=True)

            _lxmf_router = _lxmf.LXMRouter(
                identity=_identity,
                storagepath=storage_path,
            )

            # Register delivery destination (receive messages)
            _lxmf_delivery = _lxmf_router.register_delivery_identity(
                _identity,
                display_name='NOMAD Node',
            )
            _lxmf_router.register_delivery_callback(_on_lxmf_message)

            _log.info('Reticulum + LXMF started. Identity: %s', _identity.hexhash)

        except Exception as e:
            _log.exception('Failed to start Reticulum')
            _reticulum = None
            _identity = None
            raise RuntimeError(f'Reticulum start failed: {type(e).__name__}')


def stop():
    """Shut down Reticulum."""
    global _reticulum, _identity, _lxmf_router, _lxmf_delivery

    with _lock:
        if _lxmf_router:
            try:
                # Prefer the official teardown hook; fall back to __del__ only
                # if the installed version doesn't expose it.
                if hasattr(_lxmf_router, 'teardown'):
                    _lxmf_router.teardown()
                elif hasattr(_lxmf_router, 'exit_handler'):
                    _lxmf_router.exit_handler()
            except Exception:
                pass
            _lxmf_router = None
            _lxmf_delivery = None

        _reticulum = None
        _identity = None
        _log.info('Reticulum stopped')


def announce(display_name='NOMAD Node'):
    """Announce this node's LXMF delivery destination on the network."""
    if not running() or not _lxmf_delivery:
        return False
    try:
        _lxmf_delivery.announce(app_data=display_name.encode('utf-8'))
        _log.info('Announced as "%s" (%s)', display_name, _identity.hexhash)
        return True
    except Exception:
        _log.exception('Announce failed')
        return False


def send_message(destination_hash_hex, content, title='', fields=None):
    """Send an LXMF message to a destination.

    Args:
        destination_hash_hex: Hex string of the recipient's identity hash
        content: Message text
        title: Optional message title
        fields: Optional dict of LXMF fields

    Returns:
        dict with message_id and status
    """
    if not running() or not _lxmf_router:
        raise RuntimeError('Reticulum not running')

    try:
        dest_hash = bytes.fromhex(destination_hash_hex)
        dest_identity = _rns.Identity.recall(dest_hash)

        if not dest_identity:
            # Try to resolve — this may take time on mesh networks
            _rns.Transport.request_path(dest_hash)
            # Wait briefly for path resolution
            time.sleep(2)
            dest_identity = _rns.Identity.recall(dest_hash)

        if not dest_identity:
            return {'status': 'error', 'error': 'Destination not found on network'}

        dest = _rns.Destination(
            dest_identity,
            _rns.Destination.OUT,
            _rns.Destination.SINGLE,
            'lxmf', 'delivery'
        )

        lxmf_msg = _lxmf.LXMessage(
            dest,
            _lxmf_delivery,
            content,
            title=title or '',
            fields=fields or {},
            desired_method=_lxmf.LXMessage.DIRECT,
        )
        lxmf_msg.try_propagation_on_fail = True

        _lxmf_router.handle_outbound(lxmf_msg)

        return {
            'status': 'sent',
            'message_hash': lxmf_msg.hash.hex() if lxmf_msg.hash else '',
            'destination': destination_hash_hex,
            'method': 'direct',
        }

    except Exception as e:
        _log.exception('Failed to send LXMF message')
        return {'status': 'error', 'error': str(type(e).__name__)}


def get_known_peers():
    """Return list of known LXMF destinations (peers we've seen announces from)."""
    if not running():
        return []

    peers = []
    try:
        known = _rns.Transport.destinations_table if hasattr(_rns.Transport, 'destinations_table') else {}
        for dest_hash, entry in known.items():
            peers.append({
                'hash': dest_hash.hex() if isinstance(dest_hash, bytes) else str(dest_hash),
                'timestamp': entry[0] if isinstance(entry, (list, tuple)) else 0,
                'hops': entry[2] if isinstance(entry, (list, tuple)) and len(entry) > 2 else 0,
            })
    except Exception:
        _log.exception('Error reading known peers')

    return peers


def set_message_callback(callback):
    """Register a callback for incoming LXMF messages.
    Callback signature: callback(sender_hash, content, title, timestamp, fields)
    """
    global _message_callback
    _message_callback = callback


# ─── Internal ────────────────────────────────────────────────────

def _on_lxmf_message(message):
    """Handle incoming LXMF message."""
    try:
        sender = message.source_hash.hex() if message.source_hash else 'unknown'
        content = message.content_as_string() if hasattr(message, 'content_as_string') else str(message.content)
        title = message.title_as_string() if hasattr(message, 'title_as_string') else ''
        ts = message.timestamp if hasattr(message, 'timestamp') else time.time()
        fields = message.fields if hasattr(message, 'fields') else {}

        _log.info('LXMF message from %s: %s', sender[:12], title or content[:50])

        # Store in mesh_messages table
        try:
            from db import db_session
            with db_session() as db:
                db.execute('''
                    INSERT INTO mesh_messages (from_node, to_node, message, channel, timestamp)
                    VALUES (?, ?, ?, ?, datetime('now'))
                ''', (sender, get_identity_hash() or 'self', content, 'lxmf'))
                db.commit()
        except Exception:
            _log.exception('Failed to store incoming LXMF message')

        # Fire callback if registered
        if _message_callback:
            try:
                _message_callback(sender, content, title, ts, fields)
            except Exception:
                _log.exception('Message callback error')

        # Broadcast SSE event for real-time UI
        try:
            from web.state import broadcast_event
            broadcast_event('mesh_message', {
                'from': sender[:12],
                'content': content[:200],
                'title': title,
            })
        except Exception:
            pass

    except Exception:
        _log.exception('Error handling incoming LXMF message')
