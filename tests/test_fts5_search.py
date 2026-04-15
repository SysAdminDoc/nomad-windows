"""v7.29.0 — FTS5 full-text search + connection pool tests."""

import pytest


class TestFTS5Tables:
    def test_fts5_virtual_tables_created(self, db):
        """All 5 FTS5 tables should exist after init."""
        names = [r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_fts'"
        ).fetchall()]
        for t in ('notes_fts', 'inventory_fts', 'contacts_fts', 'documents_fts', 'waypoints_fts'):
            assert t in names

    def test_triggers_keep_fts_in_sync_on_insert(self, db):
        db.execute("INSERT INTO notes (title, content) VALUES ('Water Purification', 'Boil for 1 minute at altitude')")
        db.commit()
        row = db.execute(
            "SELECT n.id FROM notes n JOIN notes_fts f ON f.rowid = n.id WHERE notes_fts MATCH ?",
            ('purification',)
        ).fetchone()
        assert row is not None

    def test_triggers_keep_fts_in_sync_on_update(self, db):
        cur = db.execute("INSERT INTO notes (title, content) VALUES ('Initial', 'old body')")
        nid = cur.lastrowid
        db.execute("UPDATE notes SET content = 'renewed survival content' WHERE id = ?", (nid,))
        db.commit()
        row = db.execute(
            "SELECT rowid FROM notes_fts WHERE notes_fts MATCH ?", ('renewed',)
        ).fetchone()
        assert row is not None
        gone = db.execute(
            "SELECT rowid FROM notes_fts WHERE notes_fts MATCH ?", ('old',)
        ).fetchone()
        assert gone is None

    def test_triggers_keep_fts_in_sync_on_delete(self, db):
        cur = db.execute("INSERT INTO inventory (name, category) VALUES ('Paracord 550ft', 'gear')")
        iid = cur.lastrowid
        db.execute("DELETE FROM inventory WHERE id = ?", (iid,))
        db.commit()
        row = db.execute(
            "SELECT rowid FROM inventory_fts WHERE inventory_fts MATCH ?", ('paracord',)
        ).fetchone()
        assert row is None


class TestSearchEndpointFTS:
    def test_search_uses_fts5_and_returns_hit(self, client, db):
        db.execute("INSERT INTO notes (title, content) VALUES ('Evac Plan', 'rally point bravo')")
        db.execute("INSERT INTO inventory (name, category, location) VALUES ('Lifestraw Filter', 'water', 'BOB')")
        db.execute("INSERT INTO contacts (name, role) VALUES ('J. Rivera', 'medic')")
        db.commit()
        r = client.get('/api/search/all?q=rally')
        assert r.status_code == 200
        data = r.get_json()
        assert any('Evac Plan' == n['title'] for n in data['notes'])

    def test_search_empty_query_returns_empty(self, client):
        r = client.get('/api/search/all?q=')
        assert r.status_code == 200

    def test_search_special_chars_do_not_crash(self, client):
        # FTS5 MATCH is sensitive to quotes/asterisks — these must not 500
        for q in ['"quoted"', 'a OR b', "foo*", "x AND y", "'"]:
            r = client.get('/api/search/all', query_string={'q': q})
            assert r.status_code == 200


class TestConnectionPool:
    def test_pool_stats_shape(self):
        from db import pool_stats
        stats = pool_stats()
        assert 'enabled' in stats
        assert 'size' in stats
        assert 'capacity' in stats

    def test_db_session_roundtrip(self):
        from db import db_session
        with db_session() as conn:
            assert conn.execute('SELECT 1').fetchone()[0] == 1
        # Second acquisition — pool path should be hit without error
        with db_session() as conn:
            assert conn.execute('SELECT 1').fetchone()[0] == 1
