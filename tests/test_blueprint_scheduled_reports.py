"""Smoke tests for the scheduled_reports blueprint.

Covers all 7 routes:
  GET    /api/reports                — list + ?type filter + pagination clamps
  GET    /api/reports/<id>           — detail (404 + happy)
  DELETE /api/reports/<id>           — 404 + happy
  POST   /api/reports/generate       — 400 type, 503 ollama-down, 201 happy
  GET    /api/reports/schedule       — defaults + stored
  POST   /api/reports/schedule       — 400 bad interval, persist + clamp 1..168
  GET    /api/reports/summary        — total + latest

While writing this suite I surfaced a real bug: `_build_sitrep_context`
was orphan dead code inside `_generate_sitrep` after `return None` —
the `def` line had been lost. Every manual + scheduled SITREP NameError'd
silently into the broad `except` and returned 503 'AI service may not
be running'. Fixed in the same commit by restoring the function at
module scope. The happy-path test below catches the regression: a
working ollama mock + a successful generate would have continued to
return 503 with the bug; now it returns 201 + report_id.
"""

import json
import pytest

from db import db_session


# ── SHARED HELPERS ────────────────────────────────────────────────────────

@pytest.fixture
def fake_ollama(monkeypatch):
    """Mock services.ollama for SITREP generation.

    The `_generate_sitrep` helper does `from services import ollama as
    ollama_svc` inside the function body, so we patch the module
    attributes directly — they're read every call."""
    state = {'running': True, 'reply': '# SITREP\n\n## 1. SITUATION\nAll quiet.'}
    import services.ollama as ollama_svc
    monkeypatch.setattr(ollama_svc, 'running', lambda: state['running'])
    monkeypatch.setattr(ollama_svc, 'DEFAULT_MODEL', 'llama3:8b')
    monkeypatch.setattr(ollama_svc, 'chat',
                        lambda model, msgs, stream=False: {
                            'message': {'content': state['reply']}
                        })
    return state


# ── /api/reports GET ──────────────────────────────────────────────────────

class TestReportsList:
    def test_empty_returns_empty_list(self, client):
        resp = client.get('/api/reports')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_returns_inserted_rows_newest_first(self, client):
        with db_session() as db:
            db.execute(
                "INSERT INTO scheduled_reports (report_type, title, content, "
                " model, status, word_count, generated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                ('sitrep', 'Old', 'old body', 'llama3', 'complete', 50,
                 '2026-01-01 00:00:00')
            )
            db.execute(
                "INSERT INTO scheduled_reports (report_type, title, content, "
                " model, status, word_count, generated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                ('sitrep', 'New', 'new body', 'llama3', 'complete', 60,
                 '2026-04-25 12:00:00')
            )
            db.commit()
        rows = client.get('/api/reports').get_json()
        # Newest first
        assert rows[0]['title'] == 'New'
        assert rows[1]['title'] == 'Old'
        # List route does NOT include the bulky `content` column
        assert 'content' not in rows[0]

    def test_type_filter(self, client):
        with db_session() as db:
            db.execute(
                "INSERT INTO scheduled_reports (report_type, title, status) "
                "VALUES ('sitrep', 'A', 'complete')"
            )
            db.execute(
                "INSERT INTO scheduled_reports (report_type, title, status) "
                "VALUES ('intel', 'B', 'complete')"
            )
            db.commit()
        rows = client.get('/api/reports?type=sitrep').get_json()
        types = {r['report_type'] for r in rows}
        assert types == {'sitrep'}

    def test_garbage_pagination_falls_back(self, client):
        """limit=NaN and offset=NaN silently fall back to defaults."""
        resp = client.get('/api/reports?limit=NaN&offset=NaN')
        assert resp.status_code == 200

    def test_limit_clamps_to_100(self, client):
        resp = client.get('/api/reports?limit=999')
        assert resp.status_code == 200
        # No assertion on body length (DB may be empty), just contract


# ── /api/reports/<id> GET (detail) ────────────────────────────────────────

class TestReportDetail:
    def test_404_unknown(self, client):
        resp = client.get('/api/reports/99999')
        assert resp.status_code == 404
        assert resp.get_json()['error'] == 'Report not found'

    def test_happy_includes_content(self, client):
        with db_session() as db:
            cur = db.execute(
                "INSERT INTO scheduled_reports (report_type, title, content, "
                " status) VALUES (?,?,?,?)",
                ('sitrep', 'Detail', 'long body text here', 'complete')
            )
            db.commit()
            rid = cur.lastrowid
        body = client.get(f'/api/reports/{rid}').get_json()
        assert body['title'] == 'Detail'
        assert body['content'] == 'long body text here'


# ── /api/reports/<id> DELETE ──────────────────────────────────────────────

class TestReportDelete:
    def test_404_unknown(self, client):
        resp = client.delete('/api/reports/99999')
        assert resp.status_code == 404

    def test_happy(self, client):
        with db_session() as db:
            cur = db.execute(
                "INSERT INTO scheduled_reports (report_type, title, status) "
                "VALUES (?,?,?)",
                ('sitrep', 'GoneSoon', 'complete')
            )
            db.commit()
            rid = cur.lastrowid
        resp = client.delete(f'/api/reports/{rid}')
        assert resp.status_code == 200
        with db_session() as db:
            row = db.execute(
                "SELECT id FROM scheduled_reports WHERE id = ?", (rid,)
            ).fetchone()
        assert row is None


# ── /api/reports/generate POST ────────────────────────────────────────────

class TestGenerate:
    def test_400_for_unsupported_type(self, client):
        resp = client.post('/api/reports/generate',
                           json={'type': 'narrative'})
        assert resp.status_code == 400
        assert 'sitrep' in resp.get_json()['error']

    def test_503_when_ollama_not_running(self, client, fake_ollama):
        fake_ollama['running'] = False
        resp = client.post('/api/reports/generate',
                           json={'type': 'sitrep'})
        assert resp.status_code == 503
        assert 'AI service' in resp.get_json()['error']

    def test_happy_path_creates_report_201(self, client, fake_ollama):
        """End-to-end: ollama returns a SITREP, route persists it as a
        complete row, response carries report_id. This test would have
        FAILED before the _build_sitrep_context fix — every generate
        returned 503 due to the orphan-def bug."""
        resp = client.post('/api/reports/generate',
                           json={'type': 'sitrep', 'model': 'llama3:8b'})
        assert resp.status_code == 201
        body = resp.get_json()
        assert body['status'] == 'generated'
        assert isinstance(body['report_id'], int)
        # Row landed
        with db_session() as db:
            row = db.execute(
                "SELECT report_type, status, word_count, model, trigger "
                "FROM scheduled_reports WHERE id = ?",
                (body['report_id'],)
            ).fetchone()
        assert row['report_type'] == 'sitrep'
        assert row['status'] == 'complete'
        assert row['model'] == 'llama3:8b'
        assert row['trigger'] == 'manual'
        assert row['word_count'] > 0

    def test_default_type_is_sitrep(self, client, fake_ollama):
        """Omitting `type` defaults to 'sitrep' (no 400 on missing key)."""
        resp = client.post('/api/reports/generate', json={})
        assert resp.status_code == 201

    def test_happy_path_pulls_real_context_from_db(self, client, fake_ollama):
        """The fixed _build_sitrep_context must actually read from DB
        and inject the context blob into the system prompt. We seed
        an inventory low-stock row and capture the chat() call to
        confirm the SQL was executed."""
        captured = []
        import services.ollama as _o
        original_chat = _o.chat
        def _capture(model, msgs, stream=False):
            captured.append(msgs)
            return {'message': {'content': '# SITREP'}}
        import importlib
        # monkeypatch already replaced chat; replace again here
        _o.chat = _capture
        try:
            with db_session() as db:
                db.execute(
                    "INSERT INTO inventory (name, category, quantity, "
                    " min_quantity, unit) VALUES (?,?,?,?,?)",
                    ('CanaryItem', 'food', 1, 10, 'ea')  # low stock trigger
                )
                db.commit()
            resp = client.post('/api/reports/generate', json={})
            assert resp.status_code == 201
            # System prompt should contain the LOW STOCK section because
            # CanaryItem.quantity (1) <= min_quantity (10)
            assert captured, 'ollama.chat was never called'
            sys_prompt = captured[0][0]['content']
            assert 'CanaryItem' in sys_prompt
            assert 'LOW STOCK' in sys_prompt
        finally:
            _o.chat = original_chat


# ── /api/reports/schedule GET / POST ──────────────────────────────────────

class TestSchedule:
    def test_get_returns_default_when_unset(self, client):
        body = client.get('/api/reports/schedule').get_json()
        assert body == {
            'enabled': False,
            'interval_hours': 24,
            'model': '',
            'last_run': '',
        }

    def test_get_returns_default_when_corrupt(self, client):
        """Malformed JSON in the settings row falls back to the default
        instead of crashing."""
        with db_session() as db:
            db.execute(
                "INSERT INTO settings (key, value) "
                "VALUES ('report_schedule', '{not json')"
            )
            db.commit()
        body = client.get('/api/reports/schedule').get_json()
        assert body['enabled'] is False
        assert body['interval_hours'] == 24

    def test_post_persists_schedule(self, client):
        resp = client.post('/api/reports/schedule',
                           json={'enabled': True,
                                 'interval_hours': 12,
                                 'model': 'llama3:70b'})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['status'] == 'saved'
        assert body['enabled'] is True
        assert body['interval_hours'] == 12
        assert body['model'] == 'llama3:70b'
        # GET round-trip
        body2 = client.get('/api/reports/schedule').get_json()
        assert body2['enabled'] is True
        assert body2['interval_hours'] == 12

    def test_400_on_bad_interval_string(self, client):
        resp = client.post('/api/reports/schedule',
                           json={'interval_hours': 'NOT-AN-INT'})
        assert resp.status_code == 400
        assert 'interval_hours' in resp.get_json()['error']

    def test_interval_clamps_below_1(self, client):
        """interval_hours < 1 is clamped to 1, not rejected."""
        resp = client.post('/api/reports/schedule',
                           json={'interval_hours': 0})
        assert resp.status_code == 200
        assert resp.get_json()['interval_hours'] == 1

    def test_interval_clamps_above_168(self, client):
        """168 hours = 1 week is the documented maximum."""
        resp = client.post('/api/reports/schedule',
                           json={'interval_hours': 9999})
        assert resp.status_code == 200
        assert resp.get_json()['interval_hours'] == 168


# ── /api/reports/summary ──────────────────────────────────────────────────

class TestSummary:
    def test_empty_summary(self, client):
        body = client.get('/api/reports/summary').get_json()
        assert body['total_reports'] == 0
        assert body['latest'] is None

    def test_returns_total_and_latest(self, client):
        with db_session() as db:
            db.execute(
                "INSERT INTO scheduled_reports (report_type, title, status, "
                " generated_at) VALUES ('sitrep', 'A', 'complete', "
                " '2026-01-01 00:00:00')"
            )
            db.execute(
                "INSERT INTO scheduled_reports (report_type, title, status, "
                " generated_at) VALUES ('sitrep', 'NewerOne', 'complete', "
                " '2026-04-25 06:00:00')"
            )
            db.commit()
        body = client.get('/api/reports/summary').get_json()
        assert body['total_reports'] == 2
        assert body['latest']['title'] == 'NewerOne'
