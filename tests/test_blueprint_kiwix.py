"""Smoke tests for kiwix blueprint routes.

Covers: ZIM listing (empty when not installed), catalog passthrough,
download-zim SSRF guard + happy-path thread kickoff, zim-downloads
progress filter, delete-zim path-traversal guard + 400/500 guards,
check-updates prefix-match logic, wikipedia-options tier flattening.

Uses monkeypatch to mock the `services.kiwix` module so tests stay
hermetic (no real kiwix binary, no network, no filesystem side-effects).

Pattern matches tests/test_blueprint_agriculture.py structure.
"""

import pytest


# ── SHARED HELPERS ────────────────────────────────────────────────────────

@pytest.fixture
def fake_kiwix(monkeypatch):
    """Swap the kiwix service module with deterministic in-memory state.

    The blueprint calls into services.kiwix for install status, ZIM listing,
    catalog, download, delete, and run-state.  Test-time we want deterministic
    pure-Python stand-ins that don't touch the filesystem or network.
    """
    state = {
        'installed': True,
        'zims': [
            {'name': 'wikipedia_en_mini_2026-01.zim', 'size_mb': 1200},
            {'name': 'wiktionary_en_all_2025-06.zim', 'size_mb': 650},
        ],
        'catalog': [
            {
                'category': 'Wikipedia',
                'tiers': {
                    'mini': [
                        {'filename': 'wikipedia_en_mini_2026-02.zim',
                         'name': 'Wikipedia EN Mini', 'size': '1.3GB',
                         'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_en_mini_2026-02.zim'},
                    ],
                    'all': [
                        {'filename': 'wikipedia_en_all_maxi_2026-02.zim',
                         'name': 'Wikipedia EN All', 'size': '115GB',
                         'url': 'https://download.kiwix.org/zim/wikipedia/wikipedia_en_all_maxi_2026-02.zim'},
                    ],
                },
            },
            {
                'category': 'Medical Reference',
                'tiers': {
                    'standard': [
                        {'filename': 'medicine_en_all_2025-09.zim',
                         'name': 'Medicine Reference', 'size': '8GB',
                         'url': 'https://download.kiwix.org/zim/medicine/medicine_en_all_2025-09.zim'},
                    ],
                },
            },
        ],
        'download_calls': [],
        'delete_calls': [],
        'running': False,
        'starts': 0,
        'stops': 0,
    }
    import services.kiwix as kiwix_svc
    monkeypatch.setattr(kiwix_svc, 'is_installed', lambda: state['installed'])
    monkeypatch.setattr(kiwix_svc, 'list_zim_files', lambda: list(state['zims']))
    monkeypatch.setattr(kiwix_svc, 'get_catalog', lambda: list(state['catalog']))
    monkeypatch.setattr(kiwix_svc, 'running', lambda: state['running'])
    monkeypatch.setattr(kiwix_svc, 'download_zim',
                        lambda url, filename=None: state['download_calls'].append((url, filename)))
    monkeypatch.setattr(kiwix_svc, 'delete_zim',
                        lambda fn: (state['delete_calls'].append(fn) or True) if fn and '..' not in fn else False)

    def _stop():
        state['stops'] += 1
        state['running'] = False
    def _start():
        state['starts'] += 1
        state['running'] = True
    monkeypatch.setattr(kiwix_svc, 'stop', _stop)
    monkeypatch.setattr(kiwix_svc, 'start', _start)
    return state


# ── ZIM LISTING ───────────────────────────────────────────────────────────

class TestZimListing:
    def test_zims_returns_list_when_installed(self, client, fake_kiwix):
        resp = client.get('/api/kiwix/zims')
        assert resp.status_code == 200
        rows = resp.get_json()
        names = {r['name'] for r in rows}
        assert 'wikipedia_en_mini_2026-01.zim' in names

    def test_zims_returns_empty_when_not_installed(self, client, fake_kiwix):
        fake_kiwix['installed'] = False
        resp = client.get('/api/kiwix/zims')
        assert resp.status_code == 200
        assert resp.get_json() == []


# ── CATALOG ───────────────────────────────────────────────────────────────

class TestCatalog:
    def test_catalog_passthrough(self, client, fake_kiwix):
        resp = client.get('/api/kiwix/catalog')
        assert resp.status_code == 200
        cats = resp.get_json()
        categories = {c['category'] for c in cats}
        assert 'Wikipedia' in categories
        assert 'Medical Reference' in categories


# ── DOWNLOAD ──────────────────────────────────────────────────────────────

class TestDownloadZim:
    def test_ssrf_rejects_localhost(self, client, fake_kiwix):
        """validate_download_url blocks localhost per SSRF protection."""
        resp = client.post('/api/kiwix/download-zim',
                           json={'url': 'http://localhost/evil.zim'})
        assert resp.status_code == 400
        assert 'Invalid download URL' in resp.get_json()['error']

    def test_ssrf_rejects_private_ip(self, client, fake_kiwix):
        resp = client.post('/api/kiwix/download-zim',
                           json={'url': 'http://127.0.0.1/evil.zim'})
        assert resp.status_code == 400

    def test_ssrf_rejects_non_http_scheme(self, client, fake_kiwix):
        resp = client.post('/api/kiwix/download-zim',
                           json={'url': 'file:///etc/passwd'})
        assert resp.status_code == 400

    def test_ssrf_rejects_mdns_suffix(self, client, fake_kiwix):
        resp = client.post('/api/kiwix/download-zim',
                           json={'url': 'http://printer.local/zim'})
        assert resp.status_code == 400

    def test_happy_path_starts_background_thread(self, client, fake_kiwix):
        """On a valid URL the blueprint kicks off a background download.

        We verify the route returns {'status': 'downloading'} and that the
        mocked download_zim gets invoked when the thread runs.  The thread
        is daemon, so we join it by polling the fake state briefly.
        """
        import time
        url = 'https://download.kiwix.org/zim/wikipedia/wikipedia_en_mini_2026-02.zim'
        resp = client.post('/api/kiwix/download-zim',
                           json={'url': url, 'filename': 'wiki.zim'})
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'downloading'
        # Thread should complete near-instantly since the fake download_zim
        # is a no-op; give it up to 2 s to land the call.
        deadline = time.time() + 2.0
        while not fake_kiwix['download_calls'] and time.time() < deadline:
            time.sleep(0.05)
        assert fake_kiwix['download_calls'] == [(url, 'wiki.zim')]

    def test_running_kiwix_is_restarted_after_download(self, client, fake_kiwix):
        """If kiwix is currently running, the post-download hook
        stops + starts it so the new ZIM is loaded. The blueprint sleeps
        1s between stop() and start(), so we need to wait for starts=1
        (which implies stops=1 already landed)."""
        import time
        fake_kiwix['running'] = True
        url = 'https://download.kiwix.org/zim/wikipedia/wikipedia_en_mini_2026-02.zim'
        client.post('/api/kiwix/download-zim', json={'url': url})
        deadline = time.time() + 5.0
        while fake_kiwix['starts'] < 1 and time.time() < deadline:
            time.sleep(0.05)
        assert fake_kiwix['stops'] == 1
        assert fake_kiwix['starts'] == 1


# ── PROGRESS FILTER ───────────────────────────────────────────────────────

class TestZimDownloads:
    def test_filter_strips_prefix(self, client, monkeypatch):
        """/api/kiwix/zim-downloads returns only kiwix-zim-prefixed
        progress entries, with the prefix stripped.

        Note: the blueprint does `from services.manager import _download_progress`
        at module load, binding a local name. Patching the services.manager
        attribute doesn't reach the blueprint's local reference, so we
        patch BOTH (the blueprint-local name is the one that matters for
        this test; patching manager as well keeps state consistent)."""
        from web.blueprints import kiwix as kiwix_bp_mod
        from services import manager as mgr
        fake = {
            'kiwix-zim-abc': {'pct': 50, 'bytes': 100},
            'kiwix-zim-def': {'pct': 100, 'bytes': 200},
            'ollama-model-xyz': {'pct': 25, 'bytes': 50},  # not kiwix, ignored
        }
        monkeypatch.setattr(kiwix_bp_mod, '_download_progress', fake)
        monkeypatch.setattr(mgr, '_download_progress', fake)
        resp = client.get('/api/kiwix/zim-downloads')
        assert resp.status_code == 200
        body = resp.get_json()
        assert set(body.keys()) == {'abc', 'def'}
        assert body['abc']['pct'] == 50

    def test_empty_progress_map(self, client, monkeypatch):
        from web.blueprints import kiwix as kiwix_bp_mod
        from services import manager as mgr
        monkeypatch.setattr(kiwix_bp_mod, '_download_progress', {})
        monkeypatch.setattr(mgr, '_download_progress', {})
        resp = client.get('/api/kiwix/zim-downloads')
        assert resp.status_code == 200
        assert resp.get_json() == {}


# ── DELETE ────────────────────────────────────────────────────────────────

class TestDeleteZim:
    def test_requires_filename(self, client, fake_kiwix):
        assert client.post('/api/kiwix/delete-zim',
                           json={}).status_code == 400

    def test_empty_filename_400(self, client, fake_kiwix):
        assert client.post('/api/kiwix/delete-zim',
                           json={'filename': ''}).status_code == 400

    def test_happy_path(self, client, fake_kiwix):
        resp = client.post('/api/kiwix/delete-zim',
                           json={'filename': 'wikipedia_en_mini_2026-01.zim'})
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'deleted'
        assert fake_kiwix['delete_calls'] == ['wikipedia_en_mini_2026-01.zim']

    def test_service_failure_returns_500(self, client, fake_kiwix):
        """services.kiwix.delete_zim() returns False when the filename
        contains a path-traversal attempt ('..').  The blueprint maps
        that to 500 so the frontend can surface the error."""
        resp = client.post('/api/kiwix/delete-zim',
                           json={'filename': '../etc/passwd'})
        assert resp.status_code == 500


# ── CHECK-UPDATES ─────────────────────────────────────────────────────────

class TestCheckUpdates:
    def test_empty_when_not_installed(self, client, fake_kiwix):
        fake_kiwix['installed'] = False
        resp = client.get('/api/kiwix/check-updates')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_detects_newer_dated_zim(self, client, fake_kiwix):
        """installed 'wikipedia_en_mini_2026-01.zim' — catalog offers
        'wikipedia_en_mini_2026-02.zim' (same prefix, newer date). Expect
        exactly one update entry for that prefix."""
        resp = client.get('/api/kiwix/check-updates')
        assert resp.status_code == 200
        updates = resp.get_json()
        mini_update = [u for u in updates
                       if u['installed'] == 'wikipedia_en_mini_2026-01.zim']
        assert len(mini_update) == 1
        assert mini_update[0]['available'] == 'wikipedia_en_mini_2026-02.zim'
        assert mini_update[0]['name'] == 'Wikipedia EN Mini'

    def test_no_update_when_installed_matches_catalog(self, client, fake_kiwix):
        """If the installed ZIM filename is byte-identical to the
        catalog's offering, no update is reported."""
        fake_kiwix['zims'] = [
            {'name': 'wikipedia_en_mini_2026-02.zim', 'size_mb': 1300},
        ]
        updates = client.get('/api/kiwix/check-updates').get_json()
        assert updates == []

    def test_ignores_zims_not_in_catalog(self, client, fake_kiwix):
        """An installed ZIM with a prefix the catalog doesn't know about
        produces zero updates — no KeyError, no false positive."""
        fake_kiwix['zims'] = [
            {'name': 'personal_notes_2024-01.zim', 'size_mb': 50},
        ]
        updates = client.get('/api/kiwix/check-updates').get_json()
        assert updates == []


# ── WIKIPEDIA OPTIONS ─────────────────────────────────────────────────────

class TestWikipediaOptions:
    def test_flattens_tiers_with_labels(self, client, fake_kiwix):
        resp = client.get('/api/kiwix/wikipedia-options')
        assert resp.status_code == 200
        options = resp.get_json()
        # Fake catalog has 2 tiers ('mini', 'all') each with 1 ZIM = 2 rows
        assert len(options) == 2
        tiers = {o['tier'] for o in options}
        assert tiers == {'mini', 'all'}
        # Tier label is added on top of the ZIM's native keys
        for o in options:
            assert 'filename' in o and 'name' in o and 'tier' in o

    def test_empty_when_no_wikipedia_category(self, client, fake_kiwix):
        """If the catalog lacks a Wikipedia-prefixed category, return []."""
        fake_kiwix['catalog'] = [
            {'category': 'Medical Reference', 'tiers': {'standard': [{'filename': 'med.zim'}]}},
        ]
        resp = client.get('/api/kiwix/wikipedia-options')
        assert resp.status_code == 200
        assert resp.get_json() == []
