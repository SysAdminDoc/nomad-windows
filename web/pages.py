"""Page routes — workspace HTML rendering, language detection, first-run state.

Extracted from web/app.py::create_app() in v7.65.0 as part of H-14.
Call ``register_pages(app)`` from ``create_app()`` after middleware is set up
but before the blueprint registry runs.

All caches are stored on ``app.config`` so per-app state never leaks between
test harness apps. Module-level state is limited to the esbuild bundle
manifest (pure file-system read, safe to share across processes).
"""

import json
import os
import time
import threading
import logging

from flask import render_template, request, Response, current_app, jsonify

from config import Config
from db import db_session
from web.utils import require_json_body as _require_json_body

log = logging.getLogger('nomad.web')

# ─── Workspace page metadata ───────────────────────────────────────────

WORKSPACE_PAGES = {
    'services': {
        'route': '/',
        'aliases': ['/home'],
        'title': 'Home',
        'partial': 'index_partials/_tab_services.html',
    },
    'situation-room': {
        'route': '/situation-room',
        'aliases': ['/briefing'],
        'title': 'Situation Room',
        'partial': 'index_partials/_tab_situation_room.html',
    },
    'readiness': {
        'route': '/readiness',
        'aliases': [],
        'title': 'Readiness',
        'partial': 'index_partials/_tab_readiness.html',
    },
    'preparedness': {
        'route': '/preparedness',
        'aliases': ['/operations'],
        'title': 'Preparedness',
        'partial': 'index_partials/_tab_preparedness.html',
    },
    'maps': {
        'route': '/maps',
        'aliases': [],
        'title': 'Maps',
        'partial': 'index_partials/_tab_maps.html',
    },
    'tools': {
        'route': '/tools',
        'aliases': [],
        'title': 'Tools',
        'partial': 'index_partials/_tab_tools.html',
    },
    'loadout': {
        'route': '/loadout',
        'aliases': [],
        'title': 'Loadout',
        'partial': 'index_partials/_tab_loadout.html',
    },
    'kiwix-library': {
        'route': '/library',
        'aliases': ['/knowledge'],
        'title': 'Library',
        'partial': 'index_partials/_tab_library.html',
    },
    'notes': {
        'route': '/notes',
        'aliases': [],
        'title': 'Notes',
        'partial': 'index_partials/_tab_notes.html',
    },
    'media': {
        'route': '/media',
        'aliases': [],
        'title': 'Media',
        'partial': 'index_partials/_tab_media.html',
    },
    'ai-chat': {
        'route': '/copilot',
        'aliases': ['/assistant'],
        'title': 'Copilot',
        'partial': 'index_partials/_tab_ai_chat.html',
    },
    'benchmark': {
        'route': '/diagnostics',
        'aliases': [],
        'title': 'Diagnostics',
        'partial': 'index_partials/_tab_benchmark.html',
    },
    'settings': {
        'route': '/settings',
        'aliases': ['/system'],
        'title': 'Settings',
        'partial': 'index_partials/_tab_settings.html',
    },
    'nukemap': {
        'route': '/nukemap-tab',
        'aliases': [],
        'title': 'NukeMap',
        'partial': 'index_partials/_tab_nukemap.html',
    },
    'viptrack': {
        'route': '/viptrack-tab',
        'aliases': [],
        'title': 'VIPTrack',
        'partial': 'index_partials/_tab_viptrack.html',
    },
    'training-knowledge': {
        'route': '/training-knowledge',
        'aliases': ['/training'],
        'title': 'Training & Knowledge',
        'partial': 'index_partials/_tab_training_knowledge.html',
    },
    'interoperability': {
        'route': '/interoperability',
        'aliases': ['/data-exchange'],
        'title': 'Interoperability',
        'partial': 'index_partials/_tab_interoperability.html',
    },
}

WORKSPACE_ROUTES = {tab: meta['route'] for tab, meta in WORKSPACE_PAGES.items()}

_PAGE_CACHE_TTL = 5.0
_MEDIA_SUBS = {'channels', 'videos', 'audio', 'books', 'torrents'}

# ─── Bundle manifest (shared across apps — pure FS read) ──────────────

_bundle_manifest: dict | None = None
_bundle_manifest_mtime: float | None = None
_bundle_manifest_lock = threading.Lock()


def load_bundle_manifest() -> dict:
    """Read the esbuild manifest, refreshing when the file mtime changes."""
    global _bundle_manifest, _bundle_manifest_mtime
    manifest_path = os.path.join(
        os.path.dirname(__file__), 'static', 'dist', 'manifest.json'
    )
    try:
        manifest_mtime = os.path.getmtime(manifest_path)
    except OSError:
        with _bundle_manifest_lock:
            _bundle_manifest = {}
            _bundle_manifest_mtime = None
        return {}

    with _bundle_manifest_lock:
        if _bundle_manifest is not None and _bundle_manifest_mtime == manifest_mtime:
            return _bundle_manifest
        try:
            with open(manifest_path, 'r') as f:
                _bundle_manifest = json.load(f)
            _bundle_manifest_mtime = manifest_mtime
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            _bundle_manifest = {}
            _bundle_manifest_mtime = None
        return _bundle_manifest


# ─── Per-app caches (stashed on app.config to preserve test isolation) ─

_LANG_CACHE_TTL = 5.0
_FIRST_RUN_CACHE_TTL = 10.0


def _lang_cache(app):
    return app.config.setdefault('_nomad_lang_cache', {'value': 'en', 'expires': 0.0})


def _first_run_cache(app):
    return app.config.setdefault('_nomad_first_run_cache', {'value': False, 'expires': 0.0})


_page_render_state_init_lock = threading.Lock()


def _page_render_state(app):
    state = app.config.get('_nomad_page_render_state')
    if state is not None:
        return state
    with _page_render_state_init_lock:
        # setdefault under the init lock means a second concurrent caller
        # observes the first caller's lock+cache instead of creating a sibling.
        return app.config.setdefault(
            '_nomad_page_render_state',
            {'cache': {}, 'lock': threading.Lock()},
        )


def _get_translations_pair():
    try:
        from web.translations import SUPPORTED_LANGUAGES, TRANSLATIONS
    except ImportError:  # pragma: no cover — legacy layout fallback
        from translations import SUPPORTED_LANGUAGES, TRANSLATIONS
    return SUPPORTED_LANGUAGES, TRANSLATIONS


def get_current_language(app=None):
    """Return the currently-selected UI language, falling back to 'en'.

    Uses a short TTL cache per-app so high-RPS templates don't hit SQLite.
    """
    if app is None:
        app = current_app._get_current_object()
    cache = _lang_cache(app)
    now = time.monotonic()
    if now < cache['expires']:
        return cache['value']
    supported, _ = _get_translations_pair()
    lang = 'en'
    try:
        with db_session() as db:
            row = db.execute(
                "SELECT value FROM settings WHERE key = 'language'"
            ).fetchone()
            lang = (row['value'] if row else 'en') or 'en'
    except Exception:
        lang = 'en'
    lang = lang if lang in supported else 'en'
    cache['value'] = lang
    cache['expires'] = now + _LANG_CACHE_TTL
    return lang


def get_template_i18n_context(app=None):
    """Build the i18n dict injected into every Jinja render."""
    if app is None:
        app = current_app._get_current_object()
    _, TRANSLATIONS = _get_translations_pair()
    current_lang = get_current_language(app)
    fallback_translations = TRANSLATIONS.get('en', {})
    current_translations = TRANSLATIONS.get(current_lang, fallback_translations)

    def _tr(key, default=''):
        return (
            current_translations.get(key)
            or fallback_translations.get(key)
            or default
            or key
        )

    return {
        'current_lang': current_lang,
        'is_rtl': current_lang == 'ar',
        'current_translations': current_translations,
        'fallback_translations': fallback_translations,
        'i18n_bootstrap': {
            'lang': current_lang,
            'translations': current_translations,
            'fallback': fallback_translations,
        },
        'tr': _tr,
    }


def is_first_run_complete(app=None):
    if app is None:
        app = current_app._get_current_object()
    cache = _first_run_cache(app)
    now = time.monotonic()
    if now < cache['expires']:
        return cache['value']
    try:
        with db_session() as db:
            row = db.execute(
                "SELECT value FROM settings WHERE key = 'first_run_complete'"
            ).fetchone()
    except Exception:
        row = None
    value = (row['value'] if row else '') or ''
    result = str(value).strip().lower() in ('1', 'true', 'yes', 'on')
    cache['value'] = result
    cache['expires'] = now + _FIRST_RUN_CACHE_TTL
    return result


def render_workspace_page(tab_id, allow_launch_restore=False, app=None):
    """Render a workspace tab with a short-lived HTML cache."""
    if app is None:
        app = current_app._get_current_object()
    meta = WORKSPACE_PAGES[tab_id]
    manifest = load_bundle_manifest()
    first_run_complete = is_first_run_complete(app)

    active_media_sub = None
    if tab_id == 'media':
        requested_media_sub = (request.args.get('media') or '').strip().lower()
        active_media_sub = requested_media_sub if requested_media_sub in _MEDIA_SUBS else 'channels'

    bundle_js = manifest.get('nomad.bundle.js', '')
    lang = get_current_language(app)
    cache_key = (
        tab_id,
        lang,
        bundle_js,
        active_media_sub,
        allow_launch_restore,
        first_run_complete,
    )

    state = _page_render_state(app)
    cache = state['cache']
    lock = state['lock']

    now = time.monotonic()
    with lock:
        cached = cache.get(cache_key)
        if cached and now < cached[0]:
            return cached[1]

    # VERSION is looked up lazily so set_version() at boot is observed
    from web.app import VERSION

    html = render_template(
        'workspace_page.html',
        version=VERSION,
        bundle_js=bundle_js,
        runtime_js=manifest.get('nomad.runtime.js', ''),
        bundle_css=manifest.get('nomad.bundle.css', ''),
        active_tab=tab_id,
        page_title=meta['title'],
        workspace_partial=meta['partial'],
        workspace_routes=WORKSPACE_ROUTES,
        allow_launch_restore=allow_launch_restore,
        first_run_complete=first_run_complete,
        wizard_should_launch=(tab_id == 'services' and not first_run_complete),
        active_media_sub=active_media_sub,
    )

    with lock:
        # Prune stale entries when cache grows large (>200 keys is abnormal)
        if len(cache) > 200:
            stale = [k for k, (exp, _) in cache.items() if now >= exp]
            for k in stale:
                del cache[k]
        cache[cache_key] = (now + _PAGE_CACHE_TTL, html)

    return html


# ─── Registration ──────────────────────────────────────────────────────

def register_pages(app):
    """Wire the i18n context processor, the app-runtime JS route, and every
    workspace page route onto ``app``."""

    @app.context_processor
    def _inject_i18n_context():  # noqa: D401 — Flask hook
        return get_template_i18n_context(app)

    @app.route('/app-runtime.js')
    def app_runtime_js():
        from web.app import VERSION
        response = Response(
            render_template('index_partials/_app_inline.js', version=VERSION),
            mimetype='application/javascript',
        )
        response.headers['Cache-Control'] = (
            'no-cache' if app.config.get('DEBUG') else 'public, max-age=86400'
        )
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.route('/')
    def dashboard():
        return render_workspace_page('services', allow_launch_restore=True, app=app)

    @app.route('/home')
    def home_page():
        return render_workspace_page('services', app=app)

    @app.route('/situation-room')
    @app.route('/briefing')
    def situation_room_page():
        return render_workspace_page('situation-room', app=app)

    @app.route('/readiness')
    def readiness_page():
        return render_workspace_page('readiness', app=app)

    @app.route('/preparedness')
    @app.route('/operations')
    def preparedness_page():
        return render_workspace_page('preparedness', app=app)

    @app.route('/maps')
    def maps_page():
        return render_workspace_page('maps', app=app)

    @app.route('/tools')
    def tools_page():
        return render_workspace_page('tools', app=app)

    @app.route('/loadout')
    def loadout_page():
        return render_workspace_page('loadout', app=app)

    @app.route('/library')
    @app.route('/knowledge')
    def library_page():
        return render_workspace_page('kiwix-library', app=app)

    @app.route('/notes')
    def notes_page():
        return render_workspace_page('notes', app=app)

    @app.route('/media')
    def media_page():
        return render_workspace_page('media', app=app)

    @app.route('/copilot')
    @app.route('/assistant')
    def copilot_page():
        return render_workspace_page('ai-chat', app=app)

    @app.route('/diagnostics')
    def diagnostics_page():
        return render_workspace_page('benchmark', app=app)

    @app.route('/settings')
    @app.route('/system')
    def settings_page():
        return render_workspace_page('settings', app=app)

    @app.route('/nukemap-tab')
    def nukemap_tab_page():
        return render_workspace_page('nukemap', app=app)

    @app.route('/viptrack-tab')
    def viptrack_tab_page():
        return render_workspace_page('viptrack', app=app)

    @app.route('/training-knowledge')
    @app.route('/training')
    def training_knowledge_page():
        return render_workspace_page('training-knowledge', app=app)

    @app.route('/interoperability')
    @app.route('/data-exchange')
    def interoperability_page():
        return render_workspace_page('interoperability', app=app)

    # ─── i18n API ─────────────────────────────────────────────────────
    SUPPORTED_LANGUAGES, TRANSLATIONS = _get_translations_pair()

    @app.route('/api/i18n/languages')
    def api_i18n_languages():
        return jsonify({'languages': SUPPORTED_LANGUAGES})

    @app.route('/api/i18n/translations/<lang>')
    def api_i18n_translations(lang):
        if lang not in TRANSLATIONS:
            return jsonify({'error': f'Language not found: {lang}'}), 404
        return jsonify({'language': lang, 'translations': TRANSLATIONS[lang]})

    @app.route('/api/i18n/language', methods=['GET'])
    def api_i18n_get_language():
        return jsonify({'language': get_current_language(app)})

    @app.route('/api/i18n/language', methods=['POST'])
    def api_i18n_set_language():
        data, error = _require_json_body(request)
        if error:
            return error
        lang = data.get('language', '').strip()
        if lang not in SUPPORTED_LANGUAGES:
            return jsonify({'error': f'Unsupported language: {lang}'}), 400
        with db_session() as db:
            db.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('language', ?)",
                (lang,),
            )
            db.commit()
        # Invalidate the cached language so the next request picks up the new value
        cache = _lang_cache(app)
        cache['value'] = lang
        cache['expires'] = 0.0
        return jsonify({'status': 'ok', 'language': lang})
