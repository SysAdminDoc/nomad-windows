"""Regression tests for Pass 21 hardening — lifecycle, DB safety, loopback
detection, path traversal, and federation table-name validation."""

import os
import sys
import threading

import pytest


# ``import nomad`` pulls in ``webview`` and ``pystray``, which on Linux query
# the X display at module-import time (Xlib.error.DisplayNameError: Bad
# display name "" on headless CI runners). Skip the two ``import nomad``
# tests when no DISPLAY is set on Linux — the invariants they pin are
# exercised on Windows/macOS CI and local dev machines.
_HEADLESS_LINUX = sys.platform.startswith('linux') and not os.environ.get('DISPLAY')
requires_display = pytest.mark.skipif(
    _HEADLESS_LINUX,
    reason='nomad.py imports webview/pystray which need an X display on Linux',
)


# ─── nomad.SERVICE_MODULES covers every service ID ──────────────────

class TestServiceModulesCoverage:
    """nomad._get_service_modules() must return a module for every service
    id in services.manager.DEPENDENCIES. get_shutdown_order() iterates that
    dict and tray_quit() looks each id up in SERVICE_MODULES — a missing
    entry silently orphans the process on graceful quit."""

    @requires_display
    def test_every_service_id_has_a_module(self):
        import nomad
        from services.manager import DEPENDENCIES

        # Reset the lazy cache so the test isn't affected by prior imports.
        nomad.SERVICE_MODULES = None
        mods = nomad._get_service_modules()

        # torrent has its own shutdown path (services.torrent.get_manager)
        # so it's intentionally excluded from the tray_quit loop; every
        # *other* dependency id must map to a module.
        expected = set(DEPENDENCIES.keys()) - {'torrent'}
        missing = expected - set(mods.keys())
        assert not missing, (
            f'nomad.SERVICE_MODULES is missing entries: {missing}. '
            'tray_quit() will silently skip mod.stop() for these on graceful '
            'shutdown, leaving the child processes orphaned.'
        )

    @requires_display
    def test_every_returned_module_exposes_stop(self):
        import nomad
        nomad.SERVICE_MODULES = None
        mods = nomad._get_service_modules()
        for sid, mod in mods.items():
            assert hasattr(mod, 'stop'), f'{sid} module has no stop()'
            assert hasattr(mod, 'running'), f'{sid} module has no running()'
            assert hasattr(mod, 'is_installed'), f'{sid} module has no is_installed()'


# ─── is_loopback_addr (unified loopback helper) ──────────────────────

class TestIsLoopbackAddr:
    """web.utils.is_loopback_addr must cover all loopback variants."""

    def _check(self, addr):
        from web.utils import is_loopback_addr
        return is_loopback_addr(addr)

    def test_ipv4_loopback(self):
        assert self._check('127.0.0.1') is True

    def test_ipv4_loopback_other(self):
        assert self._check('127.0.0.2') is True

    def test_ipv6_loopback(self):
        assert self._check('::1') is True

    def test_ipv4_mapped_ipv6_loopback(self):
        assert self._check('::ffff:127.0.0.1') is True

    def test_private_ip_not_loopback(self):
        assert self._check('192.168.1.1') is False

    def test_public_ip_not_loopback(self):
        assert self._check('8.8.8.8') is False

    def test_empty_string(self):
        assert self._check('') is False

    def test_none(self):
        assert self._check(None) is False

    def test_garbage(self):
        assert self._check('not-an-ip') is False

    def test_localhost_string_not_ip(self):
        assert self._check('localhost') is False


# ─── Path traversal: backup endpoints use basename ───────────────────

class TestBackupPathTraversal:
    """Backup filename parameters must be sanitised via os.path.basename."""

    def test_restore_strips_path_components(self, client, db):
        resp = client.post('/api/system/backup/restore',
                           json={'filename': '../../etc/passwd'})
        # basename('../../etc/passwd') == 'passwd' which won't match a backup
        assert resp.status_code in (400, 404)

    def test_restore_dotdot_in_name(self, client, db):
        resp = client.post('/api/system/backup/restore',
                           json={'filename': '../nomad.db'})
        assert resp.status_code in (400, 404)

    def test_restore_empty_filename(self, client, db):
        resp = client.post('/api/system/backup/restore',
                           json={'filename': ''})
        assert resp.status_code == 400

    def test_delete_rejects_traversal(self, client):
        resp = client.delete('/api/system/backup/../../etc/passwd')
        # basename strips path — result doesn't start with 'nomad_backup_'
        assert resp.status_code in (400, 404)

    def test_delete_requires_nomad_prefix(self, client):
        resp = client.delete('/api/system/backup/evil.db')
        assert resp.status_code == 400


# ─── Auth check uses robust loopback detection ──────────────────────

class TestAuthCheckLoopback:
    def test_auth_check_returns_authenticated_for_local(self, client):
        resp = client.get('/api/auth/check')
        data = resp.get_json()
        assert data['authenticated'] is True


# ─── Federation table-name injection blocked ─────────────────────────

class TestFederationTableValidation:
    """The incoming sync endpoint must reject table names not in the ALLOWED set."""

    def _seed_federation_peer(self, db):
        db.execute("""
            INSERT OR IGNORE INTO federation_peers (node_id, node_name, trust_level)
            VALUES ('test-peer', 'Test', 'trusted')
        """)
        db.commit()

    def test_sync_rejects_unknown_table_in_vector_clocks(self, client, db):
        self._seed_federation_peer(db)
        payload = {
            'source_node_id': 'test-peer',
            'tables': {},
            'vector_clocks': {
                'sqlite_master': {'abc123': {'test-peer': 1}},
            },
        }
        resp = client.post('/api/node/sync-receive', json=payload)
        data = resp.get_json()
        if resp.status_code == 200 and 'conflicts' in data:
            for conflict in data['conflicts']:
                assert conflict.get('table') != 'sqlite_master'

    def test_sync_accepts_allowed_table(self, client, db):
        self._seed_federation_peer(db)
        payload = {
            'source_node_id': 'test-peer',
            'tables': {},
            'vector_clocks': {
                'inventory': {'somehash': {'test-peer': 1}},
            },
        }
        resp = client.post('/api/node/sync-receive', json=payload)
        assert resp.status_code in (200, 201)


# ─── Readiness score endpoint works ─────────────────────────────────

class TestReadinessScoreSQL:
    def test_readiness_score_returns_valid_response(self, client):
        resp = client.get('/api/readiness-score')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'total' in data or 'score' in data
        assert 'categories' in data or 'breakdown' in data


# ─── Shutdown event ──────────────────────────────────────────────────

class TestShutdownEvent:
    def test_shutdown_event_exists(self):
        # nomad.py sets _shutdown_event at module level — import may trigger
        # heavyweight side effects so just verify the source code instead.
        import inspect, importlib
        spec = importlib.util.find_spec('nomad')
        if spec and spec.origin:
            source = open(spec.origin, encoding='utf-8').read()
            assert '_shutdown_event = threading.Event()' in source
        else:
            pytest.skip('nomad module not found on sys.path')


# ─── DB: backup uses TRUNCATE checkpoint ─────────────────────────────

class TestBackupCheckpoint:
    def test_backup_mentions_truncate(self):
        import inspect
        from db import backup_db
        source = inspect.getsource(backup_db)
        assert 'TRUNCATE' in source


# ─── DB: migration uses explicit transaction ─────────────────────────

class TestMigrationTransaction:
    def test_migration_uses_begin_immediate(self):
        import inspect, re
        from db import apply_migrations
        source = inspect.getsource(apply_migrations)
        assert 'BEGIN IMMEDIATE' in source
        # The execution path should not call executescript(sql) on user-provided
        # migration SQL. Ignore comments (lines starting with #).
        code_lines = [ln for ln in source.splitlines()
                       if ln.strip() and not ln.strip().startswith('#')]
        active_calls = [ln for ln in code_lines if 'executescript(sql)' in ln
                        or 'executescript(sql ' in ln]
        assert not active_calls, f'Found active executescript call: {active_calls}'


# ─── DB: log_activity catches all sqlite3 errors ─────────────────────

class TestLogActivityExceptionScope:
    def test_catches_sqlite_error_base_class(self):
        import inspect
        from db import log_activity
        source = inspect.getsource(log_activity)
        assert 'sqlite3.Error' in source


# ─── web/auth.py uses is_loopback_addr ───────────────────────────────

class TestAuthModuleLoopback:
    def test_auth_uses_loopback_helper(self):
        import inspect
        from web.auth import _is_localhost
        source = inspect.getsource(_is_localhost)
        assert 'is_loopback_addr' in source


# ─── Pass 21b: Wizard crash safety ──────────────────────────────────

class TestWizardCrashSafety:
    """Wizard daemon thread has a top-level exception wrapper."""

    def test_wizard_do_setup_has_crash_wrapper(self):
        import inspect
        from web.blueprints.system import api_wizard_setup
        source = inspect.getsource(api_wizard_setup)
        # The do_setup function must have a catch-all exception handler
        assert "status='error'" in source
        assert 'phase=' in source and 'failed' in source

    def test_wizard_rejects_when_already_complete(self, client, db):
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('first_run_complete', '1')")
        db.commit()
        resp = client.post('/api/wizard/setup', json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'already completed' in data.get('error', '').lower()

    def test_wizard_rejects_when_running(self, client, db):
        from web.state import wizard_update
        wizard_update(status='running')
        try:
            resp = client.post('/api/wizard/setup', json={})
            assert resp.status_code == 409
        finally:
            # Reset wizard state so it doesn't affect other tests
            from web.state import wizard_reset
            wizard_reset()


# ─── Pass 21b: Ollama pull_model response cleanup ───────────────────

class TestOllamaPullModelCleanup:
    def test_pull_model_has_finally_close(self):
        import inspect
        from services.ollama import pull_model
        source = inspect.getsource(pull_model)
        assert 'finally:' in source
        assert 'resp.close()' in source


# ─── Pass 21b: Service process cleanup on DB failure ────────────────

class TestServiceProcessCleanup:
    """All subprocess-based service start() functions must kill the process
    if the DB update fails, preventing orphaned processes."""

    def _check_service_start(self, module_name):
        import importlib
        mod = importlib.import_module(f'services.{module_name}')
        import inspect
        source = inspect.getsource(mod.start)
        assert 'unregister_process' in source, f'{module_name}.start() missing unregister_process on DB error'
        assert 'proc.terminate()' in source, f'{module_name}.start() missing proc.terminate() on DB error'

    def test_ollama_cleanup(self):
        # ollama.start() delegates to manager.start_process(), which owns
        # DB-failure cleanup for all services that use it.  Verify the
        # cleanup contract is satisfied there.
        import inspect
        from services import manager
        source = inspect.getsource(manager.start_process)
        assert 'proc.terminate()' in source, 'manager.start_process() missing proc.terminate() on DB error'
        # unregister_process is the old per-service cleanup pattern;
        # start_process() uses _processes.pop() instead — verify that.
        assert '_processes.pop(' in source, 'manager.start_process() missing _processes.pop() cleanup on DB error'

    def test_stirling_cleanup(self):
        self._check_service_start('stirling')

    def test_kiwix_cleanup(self):
        self._check_service_start('kiwix')

    def test_kolibri_cleanup(self):
        self._check_service_start('kolibri')

    def test_qdrant_cleanup(self):
        self._check_service_start('qdrant')


# ─── Pass 21b: Portable mode uses realpath ──────────────────────────

class TestPortableModeSymlink:
    def test_is_portable_mode_uses_realpath(self):
        import inspect
        from platform_utils import is_portable_mode
        source = inspect.getsource(is_portable_mode)
        assert 'os.path.realpath(' in source

    def test_get_portable_data_dir_uses_realpath(self):
        import inspect
        from platform_utils import get_portable_data_dir
        source = inspect.getsource(get_portable_data_dir)
        assert 'os.path.realpath(' in source


# ─── Pass 21b: Config temp file cleanup ─────────────────────────────

class TestConfigTempCleanup:
    def test_save_config_cleans_tmp_on_failure(self):
        import inspect
        from config import save_config
        source = inspect.getsource(save_config)
        assert 'os.remove(tmp_path)' in source
