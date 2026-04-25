"""Smoke tests for the group_exercises blueprint.

Covers all 7 routes:
  GET  /api/group-exercises                                  — list
  POST /api/group-exercises                                  — create + broadcast
  POST /api/group-exercises/invite                           — receive invite
  POST /api/group-exercises/<id>/join                        — join + notify
  POST /api/group-exercises/<id>/participant-joined          — receive notify
  POST /api/group-exercises/<id>/update-state                — phase/event/decision
  POST /api/group-exercises/<id>/sync-state                  — peer state push

The blueprint fires `requests.post(...)` to federation peers in three
paths (create / join / update-state). Since `_get_trusted_peers()`
returns [] when the federation_peers table is empty (the default for
a fresh test DB), the broadcast loops are no-ops by default. The two
routes that DO need peer interaction (invite / sync-state) verify the
trust-gate by seeding rows directly.
"""

import json
import pytest

from db import db_session


# ── /api/group-exercises GET (list) ───────────────────────────────────────

class TestList:
    def test_empty_returns_empty_list(self, client):
        resp = client.get('/api/group-exercises')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_returns_inserted_rows_with_normalized_json_fields(self, client):
        with db_session() as db:
            db.execute(
                "INSERT INTO group_exercises (exercise_id, title, scenario_type, "
                " description, initiator_node, initiator_name, participants, "
                " status, shared_state, decisions_log) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                ('ex-001', 'Test Exercise', 'grid_down', 'desc',
                 'node-a', 'Alpha', json.dumps([{'node_id': 'a'}]),
                 'active', json.dumps({'phase': 2}), json.dumps([]))
            )
            db.commit()
        rows = client.get('/api/group-exercises').get_json()
        assert len(rows) == 1
        # JSON columns are deserialized in the response
        assert rows[0]['participants'] == [{'node_id': 'a'}]
        assert rows[0]['shared_state'] == {'phase': 2}
        assert rows[0]['decisions_log'] == []


# ── /api/group-exercises POST (create) ────────────────────────────────────

class TestCreate:
    def test_create_returns_exercise_id_and_invited_count(self, client):
        """No federation peers seeded → invited count is 0; the row
        lands with status='recruiting' and the initiator is the only
        participant."""
        resp = client.post('/api/group-exercises',
                           json={'title': 'Drill Alpha',
                                 'scenario_type': 'flood',
                                 'description': 'flash flood EMA drill'})
        assert resp.status_code == 201
        body = resp.get_json()
        assert isinstance(body['exercise_id'], str)
        assert len(body['exercise_id']) == 12
        assert body['invited'] == 0
        # Row landed
        with db_session() as db:
            row = db.execute(
                "SELECT title, status, scenario_type FROM group_exercises "
                "WHERE exercise_id = ?", (body['exercise_id'],)
            ).fetchone()
        assert row['title'] == 'Drill Alpha'
        assert row['status'] == 'recruiting'
        assert row['scenario_type'] == 'flood'

    def test_create_uses_default_title_when_missing(self, client):
        """`(data.get('title','') or 'Group Exercise').strip()` — the
        default kicks in only when the field is absent / falsy. A
        whitespace-only string is truthy, so it strips to '' instead.
        Pinning the default-fallback path."""
        resp = client.post('/api/group-exercises', json={})
        assert resp.status_code == 201
        ex_id = resp.get_json()['exercise_id']
        with db_session() as db:
            row = db.execute(
                "SELECT title FROM group_exercises WHERE exercise_id = ?",
                (ex_id,)
            ).fetchone()
        assert row['title'] == 'Group Exercise'

    def test_whitespace_title_strips_to_empty(self, client):
        """Mirror of the above — pinning the surprising whitespace path."""
        resp = client.post('/api/group-exercises', json={'title': '   '})
        ex_id = resp.get_json()['exercise_id']
        with db_session() as db:
            row = db.execute(
                "SELECT title FROM group_exercises WHERE exercise_id = ?",
                (ex_id,)
            ).fetchone()
        assert row['title'] == ''


# ── /api/group-exercises/invite (receive) ────────────────────────────────

class TestInvite:
    def test_missing_exercise_id_400(self, client):
        resp = client.post('/api/group-exercises/invite', json={})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Missing exercise_id'

    def test_first_invite_inserts_with_status_invited(self, client):
        resp = client.post('/api/group-exercises/invite',
                           json={'exercise_id': 'ex-002',
                                 'title': 'Inbound Drill',
                                 'scenario_type': 'evac',
                                 'initiator_name': 'Bravo'})
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'invited'
        with db_session() as db:
            row = db.execute(
                "SELECT title, status FROM group_exercises "
                "WHERE exercise_id = ?", ('ex-002',)
            ).fetchone()
        assert row['status'] == 'invited'
        assert row['title'] == 'Inbound Drill'

    def test_repeat_invite_returns_already_known(self, client):
        client.post('/api/group-exercises/invite',
                    json={'exercise_id': 'ex-003', 'title': 'Once'})
        resp = client.post('/api/group-exercises/invite',
                           json={'exercise_id': 'ex-003', 'title': 'Twice'})
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'already_known'

    def test_blocked_initiator_returns_403(self, client):
        with db_session() as db:
            db.execute(
                "INSERT INTO federation_peers (node_id, node_name, ip, port, "
                " trust_level) VALUES (?,?,?,?,?)",
                ('blocked-1', 'BlockedNode', '10.0.0.99', 8080, 'blocked')
            )
            db.commit()
        resp = client.post('/api/group-exercises/invite',
                           json={'exercise_id': 'ex-004',
                                 'initiator_node': 'blocked-1'})
        assert resp.status_code == 403
        assert resp.get_json()['error'] == 'Peer is blocked'


# ── /api/group-exercises/<id>/join ────────────────────────────────────────

class TestJoin:
    def test_404_when_exercise_missing(self, client):
        resp = client.post('/api/group-exercises/does-not-exist/join')
        assert resp.status_code == 404

    def test_join_appends_self_and_flips_status_to_active(self, client):
        client.post('/api/group-exercises/invite',
                    json={'exercise_id': 'ex-005', 'title': 'Joinable'})
        resp = client.post('/api/group-exercises/ex-005/join')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['status'] == 'joined'
        assert body['participants'] >= 1
        with db_session() as db:
            row = db.execute(
                "SELECT status, participants FROM group_exercises "
                "WHERE exercise_id = ?", ('ex-005',)
            ).fetchone()
        assert row['status'] == 'active'

    def test_join_is_idempotent_for_self(self, client):
        """Joining twice from the same node doesn't append a duplicate
        participant entry — the route checks node_id uniqueness."""
        client.post('/api/group-exercises/invite',
                    json={'exercise_id': 'ex-006', 'title': 'Idem'})
        client.post('/api/group-exercises/ex-006/join')
        b2 = client.post('/api/group-exercises/ex-006/join').get_json()
        # Same participant count both calls (1 — the self-node)
        assert b2['participants'] == 1


# ── /api/group-exercises/<id>/participant-joined ──────────────────────────

class TestParticipantJoined:
    def test_404_when_exercise_missing(self, client):
        resp = client.post('/api/group-exercises/missing/participant-joined',
                           json={'node_id': 'x'})
        assert resp.status_code == 404

    def test_appends_participant_when_known_exercise(self, client):
        client.post('/api/group-exercises/invite',
                    json={'exercise_id': 'ex-007', 'title': 'Notify'})
        resp = client.post('/api/group-exercises/ex-007/participant-joined',
                           json={'node_id': 'remote-node-1',
                                 'node_name': 'RemoteOne'})
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'noted'
        with db_session() as db:
            row = db.execute(
                "SELECT participants FROM group_exercises "
                "WHERE exercise_id = ?", ('ex-007',)
            ).fetchone()
        parts = json.loads(row['participants'])
        node_ids = {p.get('node_id') for p in parts if isinstance(p, dict)}
        assert 'remote-node-1' in node_ids


# ── /api/group-exercises/<id>/update-state ────────────────────────────────

class TestUpdateState:
    def test_404_when_missing(self, client):
        resp = client.post('/api/group-exercises/none/update-state',
                           json={'phase': 1})
        assert resp.status_code == 404

    def test_phase_event_and_decision_are_appended(self, client):
        ex_id = client.post('/api/group-exercises',
                            json={'title': 'StateTest'}).get_json()['exercise_id']
        resp = client.post(f'/api/group-exercises/{ex_id}/update-state',
                           json={'phase': 3,
                                 'event': 'first event',
                                 'decision': 'first decision'})
        assert resp.status_code == 200
        with db_session() as db:
            row = db.execute(
                "SELECT shared_state, decisions_log, current_phase "
                "FROM group_exercises WHERE exercise_id = ?", (ex_id,)
            ).fetchone()
        ss = json.loads(row['shared_state'])
        decisions = json.loads(row['decisions_log'])
        assert ss['phase'] == 3
        assert row['current_phase'] == 3
        assert any(e.get('event') == 'first event' for e in ss['events'])
        assert any(d.get('decision') == 'first decision' for d in decisions)


# ── /api/group-exercises/<id>/sync-state ──────────────────────────────────

class TestSyncState:
    def test_unknown_sender_403(self, client):
        """Sender's source_node_id is not in federation_peers (and isn't
        empty) → 403, since the trust-gate requires a known peer."""
        resp = client.post('/api/group-exercises/anything/sync-state',
                           json={'source_node_id': 'unknown-node',
                                 'shared_state': {'phase': 1}})
        assert resp.status_code == 403

    def test_blocked_sender_403(self, client):
        with db_session() as db:
            db.execute(
                "INSERT INTO federation_peers (node_id, node_name, ip, port, "
                " trust_level) VALUES (?,?,?,?,?)",
                ('block-x', 'BlockedX', '10.0.0.50', 8080, 'blocked')
            )
            db.commit()
        resp = client.post('/api/group-exercises/anything/sync-state',
                           json={'source_node_id': 'block-x',
                                 'shared_state': {}})
        assert resp.status_code == 403

    def test_trusted_sender_persists_state(self, client):
        """A trusted peer's sync-state push lands the row even if the
        exercise didn't exist before — the route is INSERT-or-UPDATE
        idempotent. We invite first to seed a row, then sync."""
        with db_session() as db:
            db.execute(
                "INSERT INTO federation_peers (node_id, node_name, ip, port, "
                " trust_level) VALUES (?,?,?,?,?)",
                ('trust-y', 'TrustedY', '10.0.0.51', 8080, 'trusted')
            )
            db.commit()
        # Seed the exercise row via invite
        client.post('/api/group-exercises/invite',
                    json={'exercise_id': 'ex-008', 'title': 'SyncTarget'})
        resp = client.post('/api/group-exercises/ex-008/sync-state',
                           json={'source_node_id': 'trust-y',
                                 'shared_state': {'phase': 7},
                                 'status': 'completed',
                                 'score': 95,
                                 'aar_text': 'all good'})
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'synced'
        with db_session() as db:
            row = db.execute(
                "SELECT current_phase, status, score, aar_text "
                "FROM group_exercises WHERE exercise_id = ?", ('ex-008',)
            ).fetchone()
        assert row['current_phase'] == 7
        assert row['status'] == 'completed'
        assert row['score'] == 95
        assert row['aar_text'] == 'all good'

    def test_empty_sender_id_passes_through(self, client):
        """An empty source_node_id skips the trust check entirely (the
        route only validates when sender is truthy)."""
        client.post('/api/group-exercises/invite',
                    json={'exercise_id': 'ex-009', 'title': 'BlankSender'})
        resp = client.post('/api/group-exercises/ex-009/sync-state',
                           json={'source_node_id': '',
                                 'shared_state': {'phase': 1}})
        assert resp.status_code == 200
