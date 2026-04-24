"""Static serving for bundled sub-apps (NukeMap + VIPTrack).

Both live as self-contained HTML/JS bundles inside ``web/`` — NukeMap as
``web/nukemap/`` (18 modules + Leaflet + data) and VIPTrack as
``web/viptrack/`` (copied from the separate VIPTrack repo during builds).
Neither is a Flask blueprint in its own right; they each expose an index
route (``/nukemap/`` and ``/viptrack/``) and a catch-all file-serving
route, with a commonpath-based path-traversal guard.

Directory resolution walks three candidates — ``sys._MEIPASS`` (frozen
PyInstaller bundle), the directory next to this module, and the cwd
fallback. VIPTrack adds a fourth candidate (the sibling VIPTrack repo
at ``../../VIPTrack`` for local development).
"""

import logging
import os
import sys

from flask import jsonify, redirect, send_from_directory

log = logging.getLogger('nomad.web')


def _resolve_bundle_dir(name, extra_candidates=None):
    """Pick the first directory that contains ``index.html`` for a bundle.

    Returns the first candidate unconditionally if none match so callers
    can log + fall back — mirrors the prior inline behavior.
    """
    candidates = []
    if getattr(sys, 'frozen', False):
        candidates.append(os.path.join(sys._MEIPASS, 'web', name))
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), name))
    candidates.append(os.path.join(os.getcwd(), 'web', name))
    if extra_candidates:
        candidates.extend(extra_candidates)
    for candidate in candidates:
        if os.path.isdir(candidate) and os.path.isfile(os.path.join(candidate, 'index.html')):
            return candidate, candidates
    return None, candidates


def _serve_within(base_dir, filepath):
    """Serve ``filepath`` from ``base_dir`` with a commonpath guard.

    Windows-safe — ``commonpath`` raises ``ValueError`` when paths sit on
    different drives, which we treat as a traversal attempt.
    """
    full_path = os.path.realpath(os.path.join(base_dir, filepath))
    base_real = os.path.realpath(base_dir)
    try:
        if os.path.commonpath([full_path, base_real]) != base_real:
            return jsonify({'error': 'Forbidden'}), 403
    except ValueError:
        return jsonify({'error': 'Forbidden'}), 403
    if not os.path.isfile(full_path):
        return jsonify({'error': 'Not found'}), 404
    return send_from_directory(os.path.dirname(full_path), os.path.basename(full_path))


def register_bundled_assets(app):
    """Wire /nukemap/* and /viptrack/* onto ``app``."""

    # ─── NukeMap ──────────────────────────────────────────────────────
    nukemap_dir, nukemap_candidates = _resolve_bundle_dir('nukemap')
    if nukemap_dir is None:
        nukemap_dir = nukemap_candidates[0]  # fallback — matches prior behavior

    @app.route('/nukemap')
    def nukemap_redirect():
        """Redirect /nukemap to /nukemap/ so relative CSS/JS paths resolve correctly."""
        return redirect('/nukemap/', code=301)

    @app.route('/nukemap/')
    @app.route('/nukemap/<path:filepath>')
    def nukemap_serve(filepath='index.html'):
        resp = _serve_within(nukemap_dir, filepath)
        # Preserve the prior not-found log line for parity with earlier behavior.
        if isinstance(resp, tuple) and resp[1] == 404:
            log.warning('NukeMap file not found: %s',
                        os.path.realpath(os.path.join(nukemap_dir, filepath)))
        return resp

    # ─── VIPTrack ─────────────────────────────────────────────────────
    # External repo path (development) — sibling checkout at ../../VIPTrack.
    _viptrack_external = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'VIPTrack')
    )
    viptrack_dir, viptrack_candidates = _resolve_bundle_dir('viptrack', [_viptrack_external])
    if viptrack_dir:
        log.info(f'VIPTrack directory: {viptrack_dir}')
    else:
        log.warning(f'VIPTrack directory NOT FOUND. Tried: {viptrack_candidates}')
        viptrack_dir = viptrack_candidates[0]  # fallback — matches prior behavior

    @app.route('/viptrack')
    def viptrack_redirect():
        """Redirect /viptrack to /viptrack/ so relative paths resolve correctly."""
        return redirect('/viptrack/', code=301)

    @app.route('/viptrack/')
    @app.route('/viptrack/<path:filepath>')
    def viptrack_serve(filepath='index.html'):
        return _serve_within(viptrack_dir, filepath)
