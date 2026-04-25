"""Smoke tests for the data_packs blueprint.

Covers all 5 routes:
  GET  /api/data-packs                       — catalog merged with install status
  GET  /api/data-packs/<pack_id>             — single-pack detail (404 + happy)
  POST /api/data-packs/<pack_id>/install     — 404 + already-installed + 201
  POST /api/data-packs/<pack_id>/uninstall   — 404 + happy
  GET  /api/data-packs/summary               — count, total size, tier1 count

The catalog is a hard-coded module-level list (PACK_CATALOG, 8 packs).
Tests pin two well-known pack_ids: 'usda_sr_legacy' (tier 1) and
'usgs_topo_index' (tier 3). If those rename in the catalog, the tests
break loudly — that's by design; the contract is the pack_id surface.
"""

import pytest

from db import db_session


# ── /api/data-packs (list, catalog + install status) ──────────────────────

class TestDataPacksList:
    def test_returns_full_catalog_when_nothing_installed(self, client):
        rows = client.get('/api/data-packs').get_json()
        assert isinstance(rows, list)
        # All 8 catalog packs surface even with zero installed
        assert len(rows) == 8
        # Every entry has a status (available when not installed)
        for r in rows:
            assert r['status'] in ('available', 'installed')
            assert 'size_display' in r
            assert 'compressed_size_display' in r
        # Specific pack survives the merge
        usda = next(r for r in rows if r['pack_id'] == 'usda_sr_legacy')
        assert usda['status'] == 'available'
        assert usda['installed_at'] == ''
        assert usda['tier'] == 1

    def test_marks_installed_packs(self, client):
        """A row inserted into data_packs with status='installed' must
        show up as installed in the merged response, with the version
        from the row (not the catalog) in installed_version."""
        with db_session() as db:
            db.execute(
                "INSERT INTO data_packs (pack_id, name, description, tier, "
                " category, size_bytes, compressed_size_bytes, version, "
                " status, installed_at, manifest) "
                "VALUES (?,?,?,?,?,?,?,?,?,datetime('now'),'{}')",
                ('usda_sr_legacy', 'USDA FoodData SR Legacy', 'desc',
                 1, 'nutrition', 78_643_200, 26_214_400, '2017.99',
                 'installed')
            )
            db.commit()
        rows = client.get('/api/data-packs').get_json()
        usda = next(r for r in rows if r['pack_id'] == 'usda_sr_legacy')
        assert usda['status'] == 'installed'
        assert usda['installed_version'] == '2017.99'
        assert usda['installed_at']  # non-empty timestamp


# ── /api/data-packs/<pack_id> (detail) ────────────────────────────────────

class TestDataPackDetail:
    def test_404_on_unknown_pack(self, client):
        resp = client.get('/api/data-packs/does_not_exist')
        assert resp.status_code == 404
        assert resp.get_json()['error'] == 'Pack not found'

    def test_happy_path_includes_size_display(self, client):
        body = client.get('/api/data-packs/fema_nri').get_json()
        assert body['pack_id'] == 'fema_nri'
        assert body['tier'] == 1
        assert body['status'] == 'available'
        # _format_bytes() converts to MB — 52428800 bytes = 50.0 MB
        assert 'MB' in body['size_display']

    def test_status_reflects_install_row(self, client):
        with db_session() as db:
            db.execute(
                "INSERT INTO data_packs (pack_id, name, status, installed_at) "
                "VALUES ('fema_nri', 'FEMA NRI', 'installed', datetime('now'))"
            )
            db.commit()
        body = client.get('/api/data-packs/fema_nri').get_json()
        assert body['status'] == 'installed'


# ── /api/data-packs/<pack_id>/install ────────────────────────────────────

class TestDataPackInstall:
    def test_404_on_unknown_pack(self, client):
        resp = client.post('/api/data-packs/does_not_exist/install')
        assert resp.status_code == 404

    def test_install_creates_row_201(self, client):
        resp = client.post('/api/data-packs/usgs_topo_index/install')
        assert resp.status_code == 201
        body = resp.get_json()
        assert body == {'status': 'installed', 'pack_id': 'usgs_topo_index'}
        # Row landed
        with db_session() as db:
            row = db.execute(
                "SELECT status, version, tier, category FROM data_packs "
                "WHERE pack_id = ?", ('usgs_topo_index',)
            ).fetchone()
        assert row is not None
        assert row['status'] == 'installed'
        assert row['tier'] == 3
        assert row['category'] == 'maps'

    def test_install_idempotent(self, client):
        """A second install for the same pack returns
        {status: 'already_installed'} (200) instead of 201."""
        client.post('/api/data-packs/noaa_frost_dates/install')
        resp = client.post('/api/data-packs/noaa_frost_dates/install')
        assert resp.status_code == 200
        assert resp.get_json() == {'status': 'already_installed'}


# ── /api/data-packs/<pack_id>/uninstall ───────────────────────────────────

class TestDataPackUninstall:
    def test_404_when_not_installed(self, client):
        resp = client.post('/api/data-packs/usda_sr_legacy/uninstall')
        assert resp.status_code == 404
        assert resp.get_json()['error'] == 'Pack not installed'

    def test_happy_path_removes_row(self, client):
        # Seed via install path so the row shape matches production
        client.post('/api/data-packs/repeaterbook_us/install')
        resp = client.post('/api/data-packs/repeaterbook_us/uninstall')
        assert resp.status_code == 200
        assert resp.get_json() == {'status': 'uninstalled'}
        # Row gone
        with db_session() as db:
            row = db.execute(
                "SELECT id FROM data_packs WHERE pack_id = ?",
                ('repeaterbook_us',)
            ).fetchone()
        assert row is None


# ── /api/data-packs/summary ───────────────────────────────────────────────

class TestSummary:
    def test_zero_installed(self, client):
        body = client.get('/api/data-packs/summary').get_json()
        assert body['installed_count'] == 0
        assert body['installed_size_bytes'] == 0
        assert body['total_available'] == 8
        # 6 of the 8 catalog packs are tier-1
        assert body['tier1_total'] == 6
        assert body['installed_size_display'] == '0 B'

    def test_counts_and_sums_after_install(self, client):
        client.post('/api/data-packs/usda_sr_legacy/install')   # 78.64 MB
        client.post('/api/data-packs/usda_hardiness_zones/install')  # 3.14 MB
        body = client.get('/api/data-packs/summary').get_json()
        assert body['installed_count'] == 2
        # Sum of catalog sizes for the two installed
        assert body['installed_size_bytes'] == 78_643_200 + 3_145_728
        assert 'MB' in body['installed_size_display']
