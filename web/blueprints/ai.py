"""AI chat, conversations, and model management routes."""

import json
import os
import re
import time
import threading
import logging
from collections import defaultdict
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, Response, stream_with_context
from werkzeug.utils import secure_filename

from db import db_session, get_db_path, log_activity
from config import get_data_dir
from services import ollama, qdrant
from services.manager import format_size
from web.auth import require_auth
from web.state import _pull_queue, _pull_queue_lock
from web.validation import validate_json
from web.sql_safety import safe_columns
import web.state as _state
from web.utils import clone_json_fallback as _clone_json_fallback, safe_json_list as _safe_json_list

log = logging.getLogger('nomad.web')

ai_bp = Blueprint('ai', __name__)

# ─── Context Window Helpers ──────────────────────────────────────────

def _estimate_tokens(text):
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4

def _trim_messages_to_fit(messages, max_tokens=4096, system_tokens=0):
    """Keep system message + most recent messages that fit within token budget."""
    if not messages:
        return messages
    budget = max_tokens - system_tokens - 200  # Reserve 200 for response
    # Preserve system message if present — must never be dropped
    system_msg = None
    rest = messages
    if messages[0].get('role') == 'system':
        system_msg = messages[0]
        rest = messages[1:]
        budget -= _estimate_tokens(system_msg.get('content', ''))
    result = []
    total = 0
    for msg in reversed(rest):
        msg_tokens = _estimate_tokens(msg.get('content', ''))
        if total + msg_tokens > budget and result:
            break
        result.insert(0, msg)
        total += msg_tokens
    if system_msg:
        result.insert(0, system_msg)
    return result


def _load_jsonl_samples(path, limit=5):
    samples = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for raw_line in f:
                if len(samples) >= limit:
                    break
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
                if isinstance(parsed, dict):
                    samples.append(parsed)
    except Exception as exc:
        log.warning('Could not read training dataset samples: %s', exc)
    return samples


def _safe_response_payload(response, fallback=None):
    if fallback is None:
        fallback = {}
    try:
        parsed = response.json()
    except Exception:
        return _clone_json_fallback(fallback)
    if isinstance(parsed, (dict, list)):
        return parsed
    return _clone_json_fallback(fallback)

# ─── Copilot Session Memory ─────────────────────────────────────────

# Intentionally in-memory only: copilot sessions are ephemeral and do not
# need to survive restarts.  Memory is bounded (trimmed to last 5 entries
# when exceeding 10) in the copilot endpoint handler.
_copilot_sessions = defaultdict(list)  # session_id -> list of {q, a}
_copilot_lock = threading.Lock()

@ai_bp.route('/api/ai/models')
def api_ai_models():
    if not ollama.is_installed() or not ollama.running():
        return jsonify([])
    return jsonify(ollama.list_models())

@ai_bp.route('/api/ai/pull', methods=['POST'])
def api_ai_pull():
    data = request.get_json() or {}
    model_name = data.get('model', ollama.DEFAULT_MODEL)
    if not isinstance(model_name, str) or not model_name.strip():
        return jsonify({'error': 'Invalid model name'}), 400
    model_name = model_name.strip()
    if len(model_name) > 200:
        return jsonify({'error': 'Model name too long'}), 400
    if not re.match(r'^[a-zA-Z0-9._:/-]+$', model_name):
        return jsonify({'error': 'Model name contains invalid characters'}), 400

    def do_pull():
        ollama.pull_model(model_name)

    threading.Thread(target=do_pull, daemon=True).start()
    return jsonify({'status': 'pulling', 'model': model_name})

@ai_bp.route('/api/ai/pull-queue', methods=['POST'])
def api_ai_pull_queue():
    """Queue multiple models for sequential download."""
    data = request.get_json() or {}
    models = data.get('models', [])
    if not models:
        return jsonify({'error': 'No models specified'}), 400
    # Filter out already-installed models
    try:
        installed = set(m['name'] for m in ollama.list_models())
    except Exception:
        installed = set()
    to_pull = [m for m in models if m not in installed]
    if not to_pull:
        return jsonify({'status': 'all_installed', 'count': 0})
    with _pull_queue_lock:
        if _state._pull_queue_active:
            return jsonify({'error': 'A download queue is already running. Wait for it to finish.'}), 409
        _pull_queue.clear()
        _pull_queue.extend(to_pull)
        _state._pull_queue_active = True

    def do_queue():
        try:
            for i, model_name in enumerate(to_pull):
                ollama._pull_progress = {
                    'status': 'pulling', 'model': model_name, 'percent': 0,
                    'detail': f'Queue: {i+1}/{len(to_pull)} — Starting {model_name}...',
                    'queue_pos': i + 1, 'queue_total': len(to_pull),
                }
                ollama.pull_model(model_name)
                # Wait for pull to finish
                for _ in range(7200):
                    p = ollama.get_pull_progress()
                    if p.get('status') in ('complete', 'error', 'idle'):
                        break
                    time.sleep(1)
        finally:
            with _pull_queue_lock:
                _pull_queue.clear()
                _state._pull_queue_active = False

    threading.Thread(target=do_queue, daemon=True).start()
    return jsonify({'status': 'queued', 'count': len(to_pull), 'models': to_pull})

@ai_bp.route('/api/ai/pull-progress')
def api_ai_pull_progress():
    progress = ollama.get_pull_progress()
    progress['queue'] = list(_pull_queue)
    progress['queue_active'] = _state._pull_queue_active
    return jsonify(progress)

@ai_bp.route('/api/ai/delete', methods=['POST'])
def api_ai_delete():
    data = request.get_json() or {}
    model_name = data.get('model')
    if not model_name or not isinstance(model_name, str):
        return jsonify({'error': 'No model specified'}), 400
    # Defensive cap — prevents sending megabyte-sized names to Ollama, which
    # would still reject them but log noisy errors.
    if len(model_name) > 200:
        return jsonify({'error': 'Model name too long'}), 400
    success = ollama.delete_model(model_name)
    if not success:
        return jsonify({'error': 'Failed to delete model'}), 500
    return jsonify({'status': 'deleted'})


def _safe_message_list(val, default=None):
    """Return a normalized list of chat message dicts."""
    messages = _safe_json_list(val, default if default is not None else [])
    normalized = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get('role', '') or '').strip()
        if not role:
            continue
        normalized_msg = dict(msg)
        content = normalized_msg.get('content', '')
        normalized_msg['role'] = role
        normalized_msg['content'] = '' if content is None else str(content)
        normalized.append(normalized_msg)
    return normalized


def _safe_memory_entries(val):
    """Return persisted AI memory entries as a list of fact dicts."""
    memories = _safe_json_list(val, [])
    normalized = []
    for memory in memories:
        if isinstance(memory, dict):
            fact = str(memory.get('fact', '') or '').strip()
            if not fact:
                continue
            normalized_memory = dict(memory)
            normalized_memory['fact'] = fact
            normalized.append(normalized_memory)
            continue
        fact = str(memory or '').strip()
        if fact:
            normalized.append({'fact': fact})
    return normalized

# ═══════════════════════════════════════════════════════════════════════════
# v7.33.0 — Phase A3: RAG scope manager
#
# Before A3 the RAG context builder was a hard-coded waterfall over 10 tables.
# It now reads `rag_scope` rows (table_name, label, enabled, weight, max_rows,
# formatter) and dispatches to either a per-table builtin formatter
# (preserving the original output verbatim) or a generic formatter that runs
# SELECT over a user-configured column set. 90+ other tables become
# visible to the LLM by toggling scope entries in Settings.
# ═══════════════════════════════════════════════════════════════════════════

_RAG_IDENT_RE = re.compile(r'^[a-zA-Z_]\w*$')


def _rag_inventory(db, max_rows):
    rows = db.execute(
        'SELECT name, quantity, unit, category, daily_usage, min_quantity, expiration '
        'FROM inventory ORDER BY category, name LIMIT ?',
        (max_rows,),
    ).fetchall()
    if not rows:
        return ''
    lines = []
    for r in rows:
        line = f'{r["name"]}: {r["quantity"]} {r["unit"]} ({r["category"]})'
        if r['daily_usage'] and r['daily_usage'] > 0:
            days = round(r['quantity'] / r['daily_usage'], 1)
            line += f' — {days} days supply at {r["daily_usage"]}/day'
        if r['min_quantity'] and r['quantity'] <= r['min_quantity']:
            line += ' [LOW STOCK]'
        if r['expiration']:
            line += f' expires {r["expiration"]}'
        lines.append(line)
    return 'INVENTORY:\n' + '\n'.join(lines)


def _rag_contacts(db, max_rows):
    rows = db.execute(
        'SELECT name, role, skills, phone, callsign, blood_type FROM contacts LIMIT ?',
        (max_rows,),
    ).fetchall()
    if not rows:
        return ''
    lines = [
        f'{c["name"]} — {c["role"] or "unassigned"}'
        + (f', skills: {c["skills"]}' if c["skills"] else '')
        + (f', callsign: {c["callsign"]}' if c["callsign"] else '')
        + (f', blood: {c["blood_type"]}' if c["blood_type"] else '')
        for c in rows
    ]
    return 'TEAM CONTACTS:\n' + '\n'.join(lines)


def _rag_patients(db, max_rows):
    rows = db.execute(
        'SELECT name, age, weight_kg, blood_type, allergies, conditions, medications '
        'FROM patients LIMIT ?',
        (max_rows,),
    ).fetchall()
    if not rows:
        return ''
    lines = []
    for p in rows:
        line = f'{p["name"]}'
        if p['age']:
            line += f', age {p["age"]}'
        if p['blood_type']:
            line += f', blood {p["blood_type"]}'
        allg = _safe_json_list(p['allergies'])
        if allg:
            line += f', ALLERGIES: {", ".join(allg)}'
        cond = _safe_json_list(p['conditions'])
        if cond:
            line += f', conditions: {", ".join(cond)}'
        meds = _safe_json_list(p['medications'])
        if meds:
            line += f', meds: {", ".join(meds)}'
        lines.append(line)
    return 'PATIENTS:\n' + '\n'.join(lines)


def _rag_fuel(db, max_rows):
    rows = db.execute(
        'SELECT fuel_type, quantity, unit, location FROM fuel_storage LIMIT ?',
        (max_rows,),
    ).fetchall()
    if not rows:
        return ''
    return 'FUEL: ' + ', '.join(
        f'{f["fuel_type"]}: {f["quantity"]} {f["unit"]} at {f["location"]}' for f in rows
    )


def _rag_ammo(db, max_rows):
    rows = db.execute(
        'SELECT caliber, quantity, location FROM ammo_inventory LIMIT ?',
        (max_rows,),
    ).fetchall()
    if not rows:
        return ''
    return 'AMMO: ' + ', '.join(
        f'{a["caliber"]}: {a["quantity"]} rounds ({a["location"]})' for a in rows
    )


def _rag_equipment(db, max_rows):
    rows = db.execute(
        "SELECT name, status, next_service FROM equipment_log "
        "WHERE next_service != '' ORDER BY next_service LIMIT ?",
        (max_rows,),
    ).fetchall()
    if not rows:
        return ''
    return 'EQUIPMENT: ' + ', '.join(
        f'{e["name"]}: {e["status"]}, service due {e["next_service"]}' for e in rows
    )


def _rag_alerts(db, max_rows):
    rows = db.execute(
        'SELECT title, severity, message FROM alerts WHERE dismissed = 0 LIMIT ?',
        (max_rows,),
    ).fetchall()
    if not rows:
        return ''
    return 'ACTIVE ALERTS:\n' + '\n'.join(
        f'[{a["severity"]}] {a["title"]}: {(a["message"] or "")[:100]}' for a in rows
    )


def _rag_weather(db, max_rows):
    # max_rows usually 1 — latest reading
    row = db.execute(
        'SELECT * FROM weather_log ORDER BY created_at DESC LIMIT ?',
        (max_rows,),
    ).fetchone()
    if not row:
        return ''
    return f'WEATHER: {dict(row)}'


def _rag_power(db, max_rows):
    row = db.execute(
        'SELECT * FROM power_log ORDER BY created_at DESC LIMIT ?',
        (max_rows,),
    ).fetchone()
    if not row:
        return ''
    return (
        f'POWER: Battery {row["battery_soc"] or "?"}%, '
        f'Solar {row["solar_watts"] or 0}W, Load {row["load_watts"] or 0}W'
    )


def _rag_incidents(db, max_rows):
    rows = db.execute(
        "SELECT severity, category, description FROM incidents "
        "WHERE created_at >= datetime('now', '-24 hours') "
        "ORDER BY created_at DESC LIMIT ?",
        (max_rows,),
    ).fetchall()
    if not rows:
        return ''
    return 'RECENT INCIDENTS (24h): ' + ' | '.join(
        f'[{r["severity"]}] {r["category"]}: {(r["description"] or "")[:60]}' for r in rows
    )


_BUILTIN_RAG_FORMATTERS = {
    'inventory':      _rag_inventory,
    'contacts':       _rag_contacts,
    'patients':       _rag_patients,
    'fuel_storage':   _rag_fuel,
    'ammo_inventory': _rag_ammo,
    'equipment_log':  _rag_equipment,
    'alerts':         _rag_alerts,
    'weather_log':    _rag_weather,
    'power_log':      _rag_power,
    'incidents':      _rag_incidents,
}


def _rag_generic(db, table_name, columns, label, max_rows):
    """Generic formatter for user-added tables. Validates table+columns
    against live PRAGMA schema before building the SELECT — defense in depth
    against SQL injection even though table_name comes from rag_scope which
    is admin-gated."""
    if not _RAG_IDENT_RE.match(table_name):
        return ''
    if not columns:
        return ''
    try:
        live_cols = {r['name'] for r in db.execute(f'PRAGMA table_info({table_name})').fetchall()}
    except Exception:
        return ''
    if not live_cols:
        return ''
    safe = [c for c in columns if c in live_cols and _RAG_IDENT_RE.match(c)]
    if not safe:
        return ''
    try:
        rows = db.execute(
            f'SELECT {", ".join(safe)} FROM {table_name} LIMIT ?',
            (int(max_rows),),
        ).fetchall()
    except Exception:
        return ''
    if not rows:
        return ''
    lines = []
    for row in rows:
        parts = []
        for col in safe:
            val = row[col]
            if val in (None, ''):
                continue
            parts.append(f'{col}={val}')
        if parts:
            lines.append(' | '.join(parts))
    if not lines:
        return ''
    return f'{label}:\n' + '\n'.join(lines)


def _rag_scope_rows(db):
    """Return enabled rag_scope rows ordered for emission. Returns [] if the
    table is missing (pre-migration DB) so the LLM still works on a stale DB."""
    try:
        return db.execute(
            'SELECT table_name, label, weight, max_rows, formatter, columns_json '
            'FROM rag_scope WHERE enabled = 1 '
            'ORDER BY weight DESC, table_name ASC'
        ).fetchall()
    except Exception as e:
        log.debug(f'rag_scope unavailable: {e}')
        return []


def build_situation_context(db, detail_level='full') -> list[str]:
    """Build rich situation context from DB for AI consumption, driven by
    the `rag_scope` table. Each enabled row contributes one section.

    detail_level:
      - 'full'    — honors each row's configured max_rows as-is
      - 'summary' — caps each row's max_rows at 10 for a compact payload
                    (used for chat, where latency + token cost matter)
    Returns an ordered list of context section strings (weight DESC)."""
    ctx_parts = []
    summary_cap = 10 if detail_level == 'summary' else None

    for r in _rag_scope_rows(db):
        table_name = r['table_name']
        max_rows = int(r['max_rows'] or 10)
        if summary_cap is not None and max_rows > summary_cap:
            max_rows = summary_cap
        if max_rows < 1:
            max_rows = 1

        formatter = r['formatter'] or 'generic'
        try:
            if formatter == 'builtin' and table_name in _BUILTIN_RAG_FORMATTERS:
                section = _BUILTIN_RAG_FORMATTERS[table_name](db, max_rows)
            else:
                cols = _safe_json_list(r['columns_json']) if r['columns_json'] else []
                section = _rag_generic(db, table_name, cols, r['label'], max_rows)
        except Exception as e:
            log.debug(f'RAG formatter failed for {table_name}: {e}')
            section = ''

        if section:
            ctx_parts.append(section)

    return ctx_parts

def get_ai_memory_text() -> str:
    """Load AI memory facts from settings, return formatted string or empty."""
    try:
        with db_session() as mem_db:
            mem_row = mem_db.execute("SELECT value FROM settings WHERE key = 'ai_memory'").fetchone()
        if mem_row and mem_row['value']:
            memories = _safe_memory_entries(mem_row['value'])
            if memories:
                lines = '\n'.join(f'- {m["fact"] if isinstance(m, dict) else m}' for m in memories)
                return f'\n\n--- OPERATOR NOTES ---\n{lines}\n--- END NOTES ---'
    except Exception:
        pass
    return ''


@ai_bp.route('/api/ai/chat', methods=['POST'])
def api_ai_chat():
    data = request.get_json() or {}
    model = data.get('model', ollama.DEFAULT_MODEL)
    messages = _safe_message_list(data.get('messages', []))
    system_prompt = data.get('system_prompt', '')
    use_kb = data.get('knowledge_base', False)

    if not ollama.running():
        return jsonify({'error': 'Ollama is not running'}), 503

    # Situation-aware context injection (consolidated via build_situation_context)
    use_situation = data.get('situation_context', False)
    if use_situation:
        try:
            with db_session() as db_ctx:
                sit_parts = build_situation_context(db_ctx, detail_level='summary')
                if sit_parts:
                    ctx = '\n'.join(sit_parts)
                    system_prompt = (system_prompt + '\n\n' if system_prompt else '') + \
                        f'You have access to the user\'s current preparedness data. Use this to give specific, actionable advice based on their actual situation:\n\n--- Current Situation ---\n{ctx}\n--- End Situation ---'
        except Exception as e:
            log.warning(f'Situation context injection failed: {e}')

    # RAG: inject knowledge base context if enabled, with source citations
    _rag_citations = []
    if use_kb and qdrant.running() and messages:
        last_user_msg = next((m.get('content', '') for m in reversed(messages) if m.get('role') == 'user'), '')
        if last_user_msg:
            try:
                from web.blueprints.kb import embed_text as _embed_text
                vectors = _embed_text([last_user_msg], prefix='search_query: ')
                if vectors:
                    results = qdrant.search(vectors[0], limit=6)
                    if results:
                        context_parts = []
                        seen_files = set()
                        for r in results:
                            if r.get('score', 0) <= 0.3:
                                continue
                            payload = r.get('payload', {})
                            text = payload.get('text', '')
                            filename = payload.get('filename', 'Unknown')
                            doc_id = payload.get('doc_id')
                            if text:
                                context_parts.append(f'[Source: {filename}]\n{text}')
                                if filename not in seen_files:
                                    seen_files.add(filename)
                                    _rag_citations.append({
                                        'filename': filename,
                                        'doc_id': doc_id,
                                        'score': round(r.get('score', 0), 3),
                                        'excerpt': text[:150] + ('...' if len(text) > 150 else ''),
                                    })
                        if context_parts:
                            kb_context = '\n\n---\n\n'.join(context_parts[:4])
                            system_prompt = (system_prompt + '\n\n' if system_prompt else '') + \
                                f'Use the following knowledge base context to help answer the question. Cite sources by mentioning the document name when relevant. If the context is not relevant, ignore it.\n\n--- Knowledge Base ---\n{kb_context}\n--- End Knowledge Base ---'
            except Exception as e:
                log.warning(f'RAG context injection failed: {e}')

    # AI Memory: inject persistent facts the user has stored
    try:
        with db_session() as mem_db:
            mem_row = mem_db.execute("SELECT value FROM settings WHERE key = 'ai_memory'").fetchone()
        if mem_row and mem_row['value']:
            memories = _safe_memory_entries(mem_row['value'])
            if memories:
                mem_text = '\n'.join(f'- {m["fact"] if isinstance(m, dict) else m}' for m in memories)
                system_prompt = (system_prompt + '\n\n' if system_prompt else '') + \
                    f'Important context the user has asked you to remember:\n{mem_text}'
    except Exception as e:
        log.warning(f'AI memory injection failed: {e}')

    if system_prompt:
        messages = [{'role': 'system', 'content': system_prompt}] + messages

    # Trim messages to fit within context window. system_tokens is not passed
    # separately because the system message is already prepended to `messages`
    # and _trim_messages_to_fit() deducts it internally. Passing it again
    # would cause a double-subtraction, halving the effective context budget.
    messages = _trim_messages_to_fit(messages, max_tokens=4096)

    def generate():
        try:
            # Send RAG citations as first chunk if available
            if _rag_citations:
                yield json.dumps({'citations': _rag_citations}) + '\n'
            for line in ollama.chat(model, messages, stream=True):
                if not line:
                    continue
                # Ollama can emit partial/corrupt frames if the backend crashes
                # mid-response. Validate each chunk parses as JSON before
                # forwarding so the client-side reader doesn't choke.
                try:
                    decoded = line.decode('utf-8')
                    json.loads(decoded)
                except (UnicodeDecodeError, ValueError):
                    log.debug('Skipping malformed Ollama stream chunk')
                    continue
                yield decoded + '\n'
        except RuntimeError as e:
            yield json.dumps({'error': str(e)}) + '\n'
        except Exception as e:
            log.exception('AI chat streaming error')
            yield json.dumps({'error': 'AI service error'}) + '\n'

    return Response(generate(), mimetype='text/event-stream')

@ai_bp.route('/api/ai/quick-query', methods=['POST'])
def api_ai_quick_query():
    """Answer a focused question using real data without full chat context.
    Designed for the dashboard copilot widget with session memory."""
    data = request.get_json() or {}
    question = data.get('question', '').strip()
    if not question:
        return jsonify({'error': 'No question'}), 400
    if not ollama.running():
        return jsonify({'error': 'AI service not running'}), 503

    session_id = data.get('session_id', 'default')

    # Build rich data context from DB using shared helper
    with db_session() as db:
        ctx_parts = build_situation_context(db)
    context = '\n\n'.join(ctx_parts) if ctx_parts else 'No data has been entered yet.'
    memory_text = get_ai_memory_text()

    system = f"""You are the NOMAD Survival Operations Copilot — an AI embedded in a desktop-first preparedness and field-operations workspace. Your role is to provide actionable intelligence based on the operator's REAL supply data, team roster, medical records, and equipment status.

RULES:
- Answer using ONLY the data below. Never fabricate items, quantities, or people.
- Use exact names, quantities, and numbers from the data.
- If a supply has daily_usage, calculate and report days remaining.
- Flag anything critical: items below 7 days supply, expired items, overdue equipment.
- Keep responses concise (2-4 sentences). Be direct — this is an ops brief, not a conversation.
- If asked about something not in the data, say "No data available for that" — don't guess.

--- OPERATOR'S LIVE DATA ---
{context}
--- END DATA ---{memory_text}"""

    # Include recent copilot session history for continuity
    with _copilot_lock:
        history = _copilot_sessions[session_id][-5:]
    if history:
        history_text = '\n'.join(f'Q: {h["q"]}\nA: {h["a"]}' for h in history)
        system += f'\n\nRecent copilot conversation:\n{history_text}'

    try:
        model = data.get('model', ollama.DEFAULT_MODEL)
        result = ollama.chat(model, [{'role': 'system', 'content': system}, {'role': 'user', 'content': question}], stream=False)
        response_text = result.get('message', {}).get('content', '') if isinstance(result, dict) else ''

        # Save to copilot session history
        with _copilot_lock:
            _copilot_sessions[session_id].append({'q': question, 'a': response_text.strip()})
            if len(_copilot_sessions[session_id]) > 10:
                _copilot_sessions[session_id] = _copilot_sessions[session_id][-5:]
            # Evict oldest half of sessions if too many accumulate
            if len(_copilot_sessions) > 100:
                keys = list(_copilot_sessions.keys())
                for k in keys[:len(keys) // 2]:
                    del _copilot_sessions[k]

        return jsonify({'answer': response_text.strip(), 'data_sources': list(set(p.split(':')[0] for p in ctx_parts))})
    except Exception as e:
        log.exception('Quick query failed')
        return jsonify({'error': 'AI query failed'}), 500

@ai_bp.route('/api/ai/suggested-actions')
def api_ai_suggested_actions():
    """Generate suggested actions based on current alerts and data state."""
    with db_session() as db:
        suggestions = []
        from datetime import datetime, timedelta
        today = datetime.now().strftime('%Y-%m-%d')
        soon7 = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        soon30 = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

        # Low stock items
        low = db.execute('SELECT name, quantity, unit FROM inventory WHERE quantity <= min_quantity AND min_quantity > 0 LIMIT 3').fetchall()
        for r in low:
            suggestions.append({'type': 'warning', 'action': f'Restock {r["name"]} — only {r["quantity"]} {r["unit"]} remaining', 'module': 'inventory'})

        # Expiring items (7 days)
        expiring = db.execute("SELECT name, expiration FROM inventory WHERE expiration != '' AND expiration <= ? AND expiration >= ? LIMIT 3", (soon7, today)).fetchall()
        for r in expiring:
            suggestions.append({'type': 'urgent', 'action': f'Rotate {r["name"]} — expires {r["expiration"]}', 'module': 'inventory'})

        # Equipment overdue
        overdue = db.execute("SELECT name, next_service FROM equipment_log WHERE next_service != '' AND next_service <= ? LIMIT 3", (today,)).fetchall()
        for r in overdue:
            suggestions.append({'type': 'warning', 'action': f'Service {r["name"]} — overdue since {r["next_service"]}', 'module': 'equipment'})

        # Unresolved critical alerts
        crit = db.execute("SELECT title FROM alerts WHERE dismissed = 0 AND severity = 'critical' LIMIT 3").fetchall()
        for r in crit:
            suggestions.append({'type': 'critical', 'action': f'Resolve alert: {r["title"]}', 'module': 'alerts'})

        # Fuel expiring
        fuel_exp = db.execute("SELECT fuel_type, expires FROM fuel_storage WHERE expires != '' AND expires <= ? LIMIT 2", (soon30,)).fetchall()
        for r in fuel_exp:
            suggestions.append({'type': 'warning', 'action': f'Rotate {r["fuel_type"]} fuel — expires {r["expires"]}', 'module': 'fuel'})

        return jsonify({'suggestions': suggestions[:8]})
@ai_bp.route('/api/ai/recommended')
def api_ai_recommended():
    return jsonify(ollama.RECOMMENDED_MODELS)

@ai_bp.route('/api/ai/context-usage', methods=['POST'])
def api_context_usage():
    """Estimate token usage for a set of messages against a model's context window."""
    d = request.json or {}
    messages = _safe_message_list(d.get('messages', []))
    system_prompt = d.get('system_prompt', '')
    total_tokens = _estimate_tokens(system_prompt)
    for msg in messages:
        total_tokens += _estimate_tokens(msg.get('content', ''))
    max_ctx = 4096  # Default
    # Try to get actual context size from model info
    model = d.get('model', '')
    if model:
        try:
            import requests as req
            r = req.post(f'http://localhost:{ollama.OLLAMA_PORT}/api/show', json={'name': model}, timeout=5)
            if r.ok:
                info = _safe_response_payload(r, {})
                params = info.get('parameters', '')
                if 'num_ctx' in params:
                    import re
                    m = re.search(r'num_ctx\s+(\d+)', params)
                    if m:
                        max_ctx = int(m.group(1))
        except Exception:
            pass
    return jsonify({
        'used_tokens': total_tokens,
        'max_tokens': max_ctx,
        'usage_pct': round((total_tokens / max_ctx) * 100, 1),
        'remaining': max(0, max_ctx - total_tokens)
    })

# ─── Conversation Branching (v5.0 Phase 1) ──────────────────────

@ai_bp.route('/api/conversations/<int:cid>/branch', methods=['POST'])
def api_conversation_branch(cid):
    """Fork a conversation from a specific message index."""
    d = request.json or {}
    raw_idx = d.get('message_index', d.get('from_index', 0))
    try:
        msg_idx = int(raw_idx)
    except (TypeError, ValueError):
        msg_idx = 0
    with db_session() as db:
        convo = db.execute('SELECT id, messages FROM conversations WHERE id = ?', (cid,)).fetchone()
        if not convo:
            return jsonify({'error': 'Conversation not found'}), 404
        messages = _safe_message_list(convo['messages'])
        if msg_idx < 0:
            msg_idx = 0
        if messages:
            msg_idx = min(msg_idx, len(messages) - 1)
        # Keep messages up to and including the branch point
        branched = messages[:msg_idx + 1] if messages else []
        db.execute(
            'INSERT INTO conversation_branches (conversation_id, parent_message_idx, messages) VALUES (?, ?, ?)',
            (cid, msg_idx, json.dumps(branched))
        )
        branch_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.execute('UPDATE conversations SET branch_count = branch_count + 1 WHERE id = ?', (cid,))
        db.commit()
        return jsonify({'branch_id': branch_id, 'messages': branched})
@ai_bp.route('/api/conversations/<int:cid>/branches')
def api_conversation_branches(cid):
    """List all branches of a conversation."""
    with db_session() as db:
        rows = db.execute(
            'SELECT id, parent_message_idx, created_at FROM conversation_branches WHERE conversation_id = ? ORDER BY created_at DESC',
            (cid,)
        ).fetchall()
        return jsonify([dict(r) for r in rows])
@ai_bp.route('/api/conversations/branches/<int:bid>')
def api_conversation_branch_get(bid):
    """Get a specific conversation branch."""
    with db_session() as db:
        row = db.execute('SELECT * FROM conversation_branches WHERE id = ?', (bid,)).fetchone()
        if not row:
            return jsonify({'error': 'Branch not found'}), 404
        return jsonify(dict(row))
@ai_bp.route('/api/conversations/branches/<int:bid>', methods=['PUT'])
def api_conversation_branch_update(bid):
    """Update branch messages (append new messages to branch)."""
    d = request.json or {}
    with db_session() as db:
        db.execute('UPDATE conversation_branches SET messages = ? WHERE id = ?',
                   (json.dumps(_safe_message_list(d.get('messages', []))), bid))
        db.commit()
        return jsonify({'status': 'ok'})
# ─── AI Image Input / Multimodal (v5.0 Phase 1) ─────────────────

_MAX_AI_IMAGE_BYTES = 20 * 1024 * 1024  # 20 MB: comfortably covers camera JPEGs,
                                         # tight enough to stop a 1-GB upload from
                                         # consuming RAM during base64 encoding.


@ai_bp.route('/api/ai/chat-with-image', methods=['POST'])
def api_ai_chat_image():
    """Send a message with an image to a multimodal model (llava, gemma3, etc.)."""
    if 'image' not in request.files and 'image_base64' not in (request.form or {}):
        return jsonify({'error': 'No image provided'}), 400

    model = request.form.get('model', '')
    message = request.form.get('message', 'Describe this image.')

    if not model:
        return jsonify({'error': 'model required'}), 400

    # Get image as base64
    import base64
    if 'image' in request.files:
        img_file = request.files['image']
        # Measure true stream size before loading into RAM — Content-Length
        # from the client is advisory and request.files.read() would gladly
        # load a 1-GB upload before we could reject it.
        try:
            img_file.stream.seek(0, 2)
            img_size = img_file.stream.tell()
            img_file.stream.seek(0)
        except (OSError, AttributeError):
            img_size = 0
        if img_size > _MAX_AI_IMAGE_BYTES:
            return jsonify({
                'error': f'Image too large (max {_MAX_AI_IMAGE_BYTES // (1024*1024)} MB)'
            }), 413
        img_data = base64.b64encode(img_file.read()).decode('utf-8')
    else:
        img_data = request.form.get('image_base64', '')
        # base64 expands binary by 4/3 — cap accordingly.
        if len(img_data) > _MAX_AI_IMAGE_BYTES * 4 // 3 + 16:
            return jsonify({
                'error': f'Image too large (max {_MAX_AI_IMAGE_BYTES // (1024*1024)} MB decoded)'
            }), 413

    try:
        import requests as _req
        resp = _req.post(f'http://localhost:{ollama.OLLAMA_PORT}/api/chat', json={
            'model': model,
            'messages': [{
                'role': 'user',
                'content': message,
                'images': [img_data]
            }],
            'stream': False
        }, timeout=120)
        if resp.ok:
            data = _safe_response_payload(resp, {})
            answer = data.get('message', {}).get('content', 'No response')
            return jsonify({'answer': answer, 'model': model})
        return jsonify({'error': f'Model returned {resp.status_code}'}), 500
    except Exception:
        log.exception('AI image chat failed')
        return jsonify({'error': 'AI query failed'}), 500


@ai_bp.route('/api/conversations')
def api_conversations_list():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        convos = db.execute('SELECT id, title, model, tags, created_at, updated_at, branch_count FROM conversations ORDER BY updated_at DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    result = []
    for c in convos:
        d = dict(c)
        try:
            d['tags'] = json.loads(d.get('tags') or '[]')
        except (json.JSONDecodeError, TypeError):
            d['tags'] = []
        result.append(d)
    return jsonify(result)

@ai_bp.route('/api/conversations', methods=['POST'])
def api_conversations_create():
    data = request.get_json() or {}
    with db_session() as db:
        cur = db.execute('INSERT INTO conversations (title, model, messages) VALUES (?, ?, ?)',
                         (data.get('title', 'New Chat'), data.get('model', ''), '[]'))
        db.commit()
        cid = cur.lastrowid
        convo = db.execute('SELECT * FROM conversations WHERE id = ?', (cid,)).fetchone()
    return jsonify(dict(convo)), 201

@ai_bp.route('/api/conversations/<int:cid>')
def api_conversations_get(cid):
    with db_session() as db:
        convo = db.execute('SELECT * FROM conversations WHERE id = ?', (cid,)).fetchone()
    if not convo:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(dict(convo))

@ai_bp.route('/api/conversations/<int:cid>', methods=['PUT'])
def api_conversations_update(cid):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT id FROM conversations WHERE id = ?', (cid,)).fetchone()
        if not existing:
            return jsonify({'error': 'not found'}), 404
        update_data = {}
        if 'title' in data:
            update_data['title'] = data['title']
        if 'model' in data:
            update_data['model'] = data['model']
        if 'messages' in data:
            update_data['messages'] = json.dumps(_safe_message_list(data['messages']))
        if 'tags' in data:
            tags = data['tags']
            if isinstance(tags, list):
                update_data['tags'] = json.dumps([str(t)[:50] for t in tags[:20]])
            elif isinstance(tags, str):
                update_data['tags'] = tags
        filtered = safe_columns(update_data, ['title', 'model', 'messages', 'tags'])
        if filtered:
            set_clause = ', '.join(f'{col} = ?' for col in filtered)
            vals = list(filtered.values())
            vals.append(cid)
            db.execute(f'UPDATE conversations SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?', vals)
        db.commit()
    return jsonify({'status': 'saved'})

@ai_bp.route('/api/conversations/<int:cid>', methods=['PATCH'])
def api_conversation_rename(cid):
    data = request.get_json() or {}
    title = data.get('title', '').strip()
    if not title:
        return jsonify({'error': 'Title required'}), 400
    with db_session() as db:
        db.execute('UPDATE conversations SET title = ? WHERE id = ?', (title, cid))
        db.commit()
    return jsonify({'status': 'renamed'})

@ai_bp.route('/api/conversations/<int:cid>', methods=['DELETE'])
def api_conversations_delete(cid):
    with db_session() as db:
        r = db.execute('DELETE FROM conversations WHERE id = ?', (cid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})

@ai_bp.route('/api/conversations/all', methods=['DELETE'])
def api_conversations_delete_all():
    with db_session() as db:
        db.execute('DELETE FROM conversations')
        db.commit()
    log_activity('conversations_cleared', detail='Cleared all conversations')
    return jsonify({'status': 'deleted'})

@ai_bp.route('/api/conversations/search')
def api_conversations_search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    # Escape LIKE wildcard characters to prevent unintended pattern matching
    q_escaped = q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    with db_session() as db:
        rows = db.execute(
            "SELECT id, title, model, created_at FROM conversations WHERE title LIKE ? ESCAPE '\\' OR messages LIKE ? ESCAPE '\\' ORDER BY updated_at DESC LIMIT 20",
            (f'%{q_escaped}%', f'%{q_escaped}%')
        ).fetchall()
    return jsonify([dict(r) for r in rows])

@ai_bp.route('/api/conversations/<int:cid>/export')
def api_conversations_export(cid):
    with db_session() as db:
        convo = db.execute('SELECT id, title, model, messages, created_at FROM conversations WHERE id = ?', (cid,)).fetchone()
    if not convo:
        return jsonify({'error': 'Not found'}), 404
    messages = _safe_message_list(convo['messages'])
    md = f"# {convo['title']}\n\n"
    md += f"*Model: {convo['model'] or 'Unknown'} | {convo['created_at']}*\n\n---\n\n"
    for m in messages:
        role = 'You' if m.get('role') == 'user' else 'AI'
        md += f"**{role}:**\n\n{m.get('content', '')}\n\n---\n\n"
    safe_title = ''.join(c for c in (convo['title'] or 'export') if c.isalnum() or c in ' _-').strip() or 'export'
    return Response(md, mimetype='text/markdown',
                   headers={'Content-Disposition': f'attachment; filename="{safe_title}.md"'})

@ai_bp.route('/api/ai/auto-setup', methods=['POST'])
def api_ai_auto_setup():
    """Auto-pull default model. Called after wizard installs Ollama."""
    if not ollama.is_installed():
        return jsonify({'error': 'Ollama not installed'}), 400

    def do_setup():
        # Wait for Ollama to be ready
        for _ in range(30):
            if ollama.running():
                break
            time.sleep(1)
        if ollama.running():
            log.info('Auto-pulling default model llama3.2:3b...')
            log_activity('auto_model_pull', 'ollama', 'llama3.2:3b')
            ollama.pull_model('llama3.2:3b')

    threading.Thread(target=do_setup, daemon=True).start()
    return jsonify({'status': 'started'})

@ai_bp.route('/api/library/upload-pdf', methods=['POST'])
def api_library_upload_pdf():
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    filename = secure_filename(file.filename)
    if not filename:
        return jsonify({'error': 'Invalid filename'}), 400
    pdf_dir = os.path.join(get_data_dir(), 'library')
    os.makedirs(pdf_dir, exist_ok=True)
    filepath = os.path.join(pdf_dir, filename)
    file.save(filepath)
    return jsonify({'status': 'uploaded', 'filename': filename, 'size': os.path.getsize(filepath)}), 201

@ai_bp.route('/api/library/pdfs')
def api_library_pdfs():
    pdf_dir = os.path.join(get_data_dir(), 'library')
    if not os.path.isdir(pdf_dir):
        return jsonify([])
    files = []
    for f in os.listdir(pdf_dir):
        if f.lower().endswith(('.pdf', '.epub', '.txt', '.md')):
            fp = os.path.join(pdf_dir, f)
            files.append({'filename': f, 'size': format_size(os.path.getsize(fp)), 'type': f.rsplit('.', 1)[-1].lower()})
    return jsonify(sorted(files, key=lambda x: x['filename']))

@ai_bp.route('/api/library/serve/<path:filename>')
def api_library_serve(filename):
    pdf_dir = os.path.join(get_data_dir(), 'library')
    safe = os.path.normcase(os.path.normpath(os.path.join(pdf_dir, secure_filename(filename))))
    if not safe.startswith(os.path.normcase(os.path.normpath(pdf_dir)) + os.sep) or not os.path.isfile(safe):
        return jsonify({'error': 'Not found'}), 404
    from flask import send_file
    return send_file(safe)

@ai_bp.route('/api/library/delete/<path:filename>', methods=['DELETE'])
def api_library_delete(filename):
    pdf_dir = os.path.join(get_data_dir(), 'library')
    safe = os.path.normcase(os.path.normpath(os.path.join(pdf_dir, secure_filename(filename))))
    if not safe.startswith(os.path.normcase(os.path.normpath(pdf_dir)) + os.sep):
        return jsonify({'error': 'Invalid'}), 400
    if os.path.isfile(safe):
        os.remove(safe)
    return jsonify({'status': 'deleted'})

# ─── AI Chat File Upload (drag/drop) ──────────────────────────────

@ai_bp.route('/api/ai/upload-context', methods=['POST'])
def api_ai_upload_context():
    """Upload a file and extract text for AI chat context."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    filename = secure_filename(file.filename)
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    content = ''
    if ext == 'pdf':
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(file)
            content = '\n'.join(page.extract_text() or '' for page in reader.pages)
        except Exception as e:
            log.warning('PDF read failed: %s', e)
            return jsonify({'error': 'PDF read failed — file may be encrypted or corrupt'}), 400
    elif ext in ('txt', 'md', 'csv', 'log', 'json', 'xml', 'html'):
        content = file.read().decode('utf-8', errors='ignore')
    else:
        return jsonify({'error': f'Unsupported file type: {ext}'}), 400
    # Truncate to ~4000 words to fit in context
    words = content.split()
    if len(words) > 4000:
        content = ' '.join(words[:4000]) + '\n\n[... truncated, file too large for full context ...]'
    return jsonify({'filename': filename, 'content': content, 'words': len(words)})

# ─── Comms Log API ─────────────────────────────────────────────────


@ai_bp.route('/api/ai/model-info/<model_name>')
def api_ai_model_info(model_name):
    """Get detailed model info for model cards."""
    try:
        import requests as _req
        r = _req.post(f'http://localhost:{ollama.OLLAMA_PORT}/api/show', json={'name': model_name}, timeout=5)
        if r.ok:
            data = _safe_response_payload(r, {})
            details = data.get('details', {})
            model_info = data.get('model_info', {})
            # Extract key metrics
            params = details.get('parameter_size', 'Unknown')
            quant = details.get('quantization_level', 'Unknown')
            family = details.get('family', 'Unknown')
            fmt = details.get('format', '')
            # Estimate RAM from parameter count
            param_num = 0
            if isinstance(params, str):
                p = params.lower().replace('b', '').replace(' ', '')
                try:
                    param_num = float(p)
                except Exception:
                    pass
            ram_est = f'~{max(1, round(param_num * 0.6))} GB' if param_num > 0 else 'Unknown'
            return jsonify({
                'name': model_name,
                'parameters': params,
                'quantization': quant,
                'family': family,
                'format': fmt,
                'ram_estimate': ram_est,
                'size_bytes': model_info.get('general.file_size', 0),
            })
        return jsonify({'name': model_name, 'error': 'Could not fetch model info'}), 404
    except Exception as e:
        log.exception('Model info fetch failed for %s', model_name)
        return jsonify({'name': model_name, 'error': 'Failed to fetch model info'}), 500

# ─── Media Metadata Editor (v5.0 Phase 6) ───────────────────────


@ai_bp.route('/api/ai/training/datasets')
def api_training_datasets():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM training_datasets ORDER BY created_at DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    return jsonify([dict(r) for r in rows])

@ai_bp.route('/api/ai/training/datasets', methods=['POST'])
def api_training_datasets_create():
    """Create a training dataset from conversation history or uploaded JSONL."""
    data = request.get_json() or {}
    name = (data.get('name', '') or 'Training Dataset').strip()[:200]
    source = data.get('source', 'conversations')  # 'conversations' or 'upload'
    base_model = data.get('base_model', '')

    with db_session() as db:
        records = []
        if source == 'conversations':
            # Extract Q&A pairs from conversation history (messages stored as JSON array in conversations.messages)
            convos = db.execute('SELECT messages FROM conversations ORDER BY updated_at DESC LIMIT 20').fetchall()
            for c in convos:
                msgs = _safe_message_list(c['messages'])
                for i in range(len(msgs) - 1):
                    if isinstance(msgs[i], dict) and isinstance(msgs[i+1], dict) and msgs[i].get('role') == 'user' and msgs[i+1].get('role') == 'assistant':
                        records.append({'instruction': (msgs[i].get('content', '') or '')[:2000], 'output': (msgs[i+1].get('content', '') or '')[:2000]})

        # Save dataset file
        ds_dir = os.path.join(get_data_dir(), 'training_datasets')
        os.makedirs(ds_dir, exist_ok=True)
        import re as _re
        safe_name = _re.sub(r'[^a-z0-9_-]', '', name.replace(' ', '_').lower())[:100] or 'dataset'
        ds_file = os.path.join(ds_dir, f'{safe_name}_{int(time.time())}.jsonl')
        with open(ds_file, 'w') as f:
            for rec in records:
                f.write(json.dumps(rec) + '\n')

        db.execute('INSERT INTO training_datasets (name, description, format, record_count, file_path, base_model, status) VALUES (?,?,?,?,?,?,?)',
                   (name, data.get('description', ''), 'jsonl', len(records), ds_file, base_model, 'ready'))
        db.commit()
        did = db.execute('SELECT last_insert_rowid()').fetchone()[0]
    log_activity('training_dataset_created', 'ai', f'Dataset "{name}" with {len(records)} records')
    return jsonify({'id': did, 'records': len(records)}), 201

@ai_bp.route('/api/ai/training/jobs')
def api_training_jobs():
    with db_session() as db:
        rows = db.execute('SELECT j.*, d.name as dataset_name FROM training_jobs j LEFT JOIN training_datasets d ON j.dataset_id = d.id ORDER BY j.created_at DESC LIMIT 50').fetchall()
    return jsonify([dict(r) for r in rows])

@ai_bp.route('/api/ai/training/jobs', methods=['POST'])
def api_training_jobs_create():
    """Create a training job. Generates an Ollama Modelfile for the custom model."""
    data = request.get_json() or {}
    dataset_id = data.get('dataset_id')
    import re as _re
    base_model = _re.sub(r'[^a-zA-Z0-9._:-]', '', data.get('base_model', 'llama3.2'))[:100] or 'llama3.2'
    output_model = _re.sub(r'[^a-zA-Z0-9_-]', '', data.get('output_model', f'nomad-custom-{int(time.time())}'))[:100] or f'nomad-custom-{int(time.time())}'
    try:
        epochs = min(max(int(data.get('epochs', 3)), 1), 20)
    except (ValueError, TypeError):
        epochs = 3
    try:
        lr = float(data.get('learning_rate', 0.0002))
    except (ValueError, TypeError):
        lr = 0.0002

    with db_session() as db:
        ds = db.execute('SELECT id, name, file_path FROM training_datasets WHERE id = ?', (dataset_id,)).fetchone() if dataset_id else None

        # Generate Ollama Modelfile
        modelfile_dir = os.path.join(get_data_dir(), 'modelfiles')
        os.makedirs(modelfile_dir, exist_ok=True)
        modelfile_path = os.path.join(modelfile_dir, f'{output_model}.Modelfile')

        system_prompt = "You are NOMAD, a survival and preparedness AI assistant. You provide practical, actionable advice for emergency preparedness, off-grid living, and disaster response."
        if ds:
            # Read sample records for system prompt enhancement
            samples = _load_jsonl_samples(ds['file_path'], limit=5)
            if samples:
                topics = ', '.join(set(s.get('instruction', '')[:50] for s in samples[:3] if str(s.get('instruction', '')).strip()))
                if topics:
                    system_prompt += f" Your training focused on: {topics}."

        with open(modelfile_path, 'w') as f:
            f.write(f'FROM {base_model}\n')
            f.write(f'SYSTEM """{system_prompt}"""\n')
            f.write(f'PARAMETER temperature 0.7\n')
            f.write(f'PARAMETER top_p 0.9\n')
            f.write(f'PARAMETER num_ctx 4096\n')

        db.execute('INSERT INTO training_jobs (dataset_id, base_model, output_model, method, epochs, learning_rate, status, log_text) VALUES (?,?,?,?,?,?,?,?)',
                   (dataset_id, base_model, output_model, 'modelfile', epochs, lr, 'ready',
                    f'Modelfile created at {modelfile_path}\nBase model: {base_model}\nRun: ollama create {output_model} -f {modelfile_path}'))
        db.commit()
        jid = db.execute('SELECT last_insert_rowid()').fetchone()[0]
    log_activity('training_job_created', 'ai', f'Job for {output_model} from {base_model}')
    return jsonify({'id': jid, 'output_model': output_model}), 201

@ai_bp.route('/api/ai/training/jobs/<int:jid>/run', methods=['POST'])
def api_training_jobs_run(jid):
    """Execute training job — runs ollama create with the Modelfile."""
    with db_session() as db:
        job = db.execute('SELECT id, output_model FROM training_jobs WHERE id = ? AND status = ?', (jid, 'ready')).fetchone()
        if not job:
            return jsonify({'error': 'Job not found or not in ready state'}), 404

        db.execute("UPDATE training_jobs SET status = 'running', started_at = datetime('now') WHERE id = ?", (jid,))
        db.commit()

    def do_train():
        try:
            import requests as req
            # Use Ollama create API
            modelfile_path = os.path.join(get_data_dir(), 'modelfiles', f'{job["output_model"]}.Modelfile')
            with open(modelfile_path, 'r') as f:
                modelfile_content = f.read()
            resp = req.post(f'http://localhost:{ollama.OLLAMA_PORT}/api/create',
                           json={'name': job['output_model'], 'modelfile': modelfile_content},
                           timeout=300)
            with db_session() as db2:
                if resp.status_code == 200:
                    db2.execute("UPDATE training_jobs SET status = 'completed', progress = 100, completed_at = datetime('now'), log_text = log_text || ? WHERE id = ?",
                               (f'\nModel {job["output_model"]} created successfully!', jid))
                else:
                    db2.execute("UPDATE training_jobs SET status = 'failed', log_text = log_text || ? WHERE id = ?",
                               (f'\nFailed: {resp.text[:500]}', jid))
                db2.commit()
        except Exception as e:
            try:
                with db_session() as db2:
                    db2.execute("UPDATE training_jobs SET status = 'failed', log_text = log_text || ? WHERE id = ?",
                               (f'\nError: {str(e)[:500]}', jid))
                    db2.commit()
            except Exception:
                pass

    t = threading.Thread(target=do_train, daemon=True)
    t.start()
    return jsonify({'status': 'running'})


# ─── AI Memory helpers (moved from routes_advanced) ──────────────────

def _safe_ai_memories(value):
    """Return stored AI memory entries as normalized fact dicts."""
    try:
        parsed = json.loads(value or '[]') if isinstance(value, str) else value
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    memories = []
    for entry in parsed:
        if isinstance(entry, dict):
            fact = str(entry.get('fact', '') or '').strip()
            if not fact:
                continue
            normalized = dict(entry)
            normalized['fact'] = fact
            memories.append(normalized)
            continue
        fact = str(entry or '').strip()
        if fact:
            memories.append({'fact': fact})
    return memories


# ─── AI SITREP Generator ─────────────────────────────────────────

@ai_bp.route('/api/ai/sitrep', methods=['POST'])
def api_ai_sitrep():
    """Generate a daily situation report from all data changes."""
    if not ollama.running():
        return jsonify({'error': 'AI service not running'}), 503

    data = request.get_json() or {}
    model = data.get('model', ollama.DEFAULT_MODEL)

    with db_session() as db:
        ctx_parts = []

        # Recent activity log (last 24h)
        activity = db.execute(
            "SELECT event, service, detail, level, created_at FROM activity_log "
            "WHERE created_at >= datetime('now', '-24 hours') ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
        if activity:
            lines = [f'[{a["level"]}] {a["event"]}' + (f' ({a["service"]})' if a["service"] else '') +
                     (f' — {a["detail"][:80]}' if a["detail"] else '') for a in activity]
            ctx_parts.append('ACTIVITY LOG (24h):\n' + '\n'.join(lines))

        # Inventory — low stock items
        low_stock = db.execute(
            'SELECT name, quantity, unit, category, min_quantity FROM inventory '
            'WHERE quantity <= min_quantity AND min_quantity > 0 ORDER BY category LIMIT 50'
        ).fetchall()
        if low_stock:
            ctx_parts.append('LOW STOCK ALERTS:\n' + '\n'.join(
                f'  {r["name"]} ({r["category"]}): {r["quantity"]} {r["unit"]} (min: {r["min_quantity"]})'
                for r in low_stock))

        # Inventory — newly expired (expiration within last 7 days or already expired)
        expired = db.execute(
            "SELECT name, quantity, unit, expiration FROM inventory "
            "WHERE expiration != '' AND expiration <= date('now') ORDER BY expiration LIMIT 50"
        ).fetchall()
        if expired:
            ctx_parts.append('EXPIRED ITEMS:\n' + '\n'.join(
                f'  {r["name"]}: {r["quantity"]} {r["unit"]} (expired {r["expiration"]})'
                for r in expired))

        # Incidents in last 24h
        incidents = db.execute(
            "SELECT severity, category, description, created_at FROM incidents "
            "WHERE created_at >= datetime('now', '-24 hours') ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
        if incidents:
            ctx_parts.append('INCIDENTS (24h):\n' + '\n'.join(
                f'  [{r["severity"]}] {r["category"]}: {r["description"][:100]}'
                for r in incidents))

        # Weather trends
        weather = db.execute(
            "SELECT pressure_hpa, temp_f, wind_dir, wind_speed, clouds, precip, created_at "
            "FROM weather_log WHERE created_at >= datetime('now', '-24 hours') "
            "ORDER BY created_at DESC LIMIT 10"
        ).fetchall()
        if weather:
            latest = weather[0]
            ctx_parts.append(
                f'WEATHER: {latest["temp_f"]}F, Pressure {latest["pressure_hpa"]} hPa, '
                f'Wind {latest["wind_dir"]} {latest["wind_speed"]}, '
                f'Clouds {latest["clouds"]}, Precip {latest["precip"]} '
                f'({len(weather)} readings in 24h)')
            if len(weather) >= 2:
                oldest = weather[-1]
                if latest['pressure_hpa'] and oldest['pressure_hpa']:
                    delta = round(latest['pressure_hpa'] - oldest['pressure_hpa'], 1)
                    trend = 'RISING' if delta > 0 else 'FALLING' if delta < 0 else 'STEADY'
                    ctx_parts.append(f'PRESSURE TREND: {trend} ({delta:+.1f} hPa over period)')

        # Power status
        power = db.execute(
            'SELECT battery_soc, solar_watts, load_watts, solar_wh_today, load_wh_today, '
            'generator_running, created_at FROM power_log ORDER BY created_at DESC LIMIT 1'
        ).fetchone()
        if power:
            gen = 'ON' if power['generator_running'] else 'OFF'
            ctx_parts.append(
                f'POWER: Battery {power["battery_soc"] or "?"}%, '
                f'Solar {power["solar_watts"] or 0}W ({power["solar_wh_today"] or 0} Wh today), '
                f'Load {power["load_watts"] or 0}W ({power["load_wh_today"] or 0} Wh today), '
                f'Generator {gen}')

        # Medical alerts — recent vitals
        vitals = db.execute(
            "SELECT p.name, v.bp_systolic, v.bp_diastolic, v.pulse, v.spo2, v.temp_f, v.created_at "
            "FROM vitals_log v JOIN patients p ON v.patient_id = p.id "
            "WHERE v.created_at >= datetime('now', '-24 hours') ORDER BY v.created_at DESC LIMIT 10"
        ).fetchall()
        if vitals:
            ctx_parts.append('MEDICAL VITALS (24h):\n' + '\n'.join(
                f'  {v["name"]}: BP {v["bp_systolic"]}/{v["bp_diastolic"]}, '
                f'HR {v["pulse"]}, SpO2 {v["spo2"]}%, Temp {v["temp_f"]}F'
                for v in vitals))

        # Active alerts
        alerts = db.execute(
            'SELECT title, severity, message FROM alerts WHERE dismissed = 0 ORDER BY severity DESC LIMIT 10'
        ).fetchall()
        if alerts:
            ctx_parts.append('ACTIVE ALERTS:\n' + '\n'.join(
                f'  [{a["severity"]}] {a["title"]}: {a["message"][:100]}' for a in alerts))

        # Inventory summary by category
        inv_summary = db.execute(
            'SELECT category, COUNT(*) as cnt, SUM(quantity) as total FROM inventory GROUP BY category LIMIT 50'
        ).fetchall()
        if inv_summary:
            ctx_parts.append('INVENTORY SUMMARY: ' + ', '.join(
                f'{r["category"]}: {r["cnt"]} items' for r in inv_summary))

        # Team count
        team_count = db.execute('SELECT COUNT(*) as c FROM contacts').fetchone()['c']
        if team_count:
            ctx_parts.append(f'TEAM: {team_count} contacts registered')

    context = '\n\n'.join(ctx_parts) if ctx_parts else 'No operational data recorded yet.'

    system_prompt = f"""You are a military-style intelligence officer generating a SITREP (Situation Report) for a preparedness and field-operations workspace called NOMAD Field Desk.

Generate a formatted SITREP in markdown using this exact structure:

# SITREP — {datetime.now(timezone.utc).strftime('%d %b %Y %H%M')}Z

## 1. SITUATION
(Overall assessment — 2-3 sentences summarizing current conditions)

## 2. SUPPLY STATUS
(Inventory highlights, low stock, expired items — use exact numbers from data)

## 3. PERSONNEL & MEDICAL
(Team count, any medical alerts, patient status)

## 4. INFRASTRUCTURE
(Power, weather, comms status)

## 5. INCIDENTS & ALERTS
(Any incidents in last 24h, active alerts)

## 6. RECOMMENDED ACTIONS
(3-5 prioritized actionable items based on the data — be specific)

RULES:
- Use ONLY the data provided below. Never fabricate information.
- Use exact quantities and names from the data.
- If a section has no relevant data, write "No data available."
- Be concise, direct, military-style briefing tone.

--- OPERATIONAL DATA ---
{context}
--- END DATA ---"""

    try:
        result = ollama.chat(model, [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': 'Generate the daily SITREP.'}
        ], stream=False)
        sitrep_text = result.get('message', {}).get('content', '') if isinstance(result, dict) else ''
        log_activity('sitrep_generated', 'ai', 'Daily SITREP generated')
        return jsonify({'sitrep': sitrep_text.strip()})
    except Exception as e:
        log.error('SITREP generation failed: %s', e)
        return jsonify({'error': 'SITREP generation failed'}), 500


# ─── AI Action Execution ─────────────────────────────────────────

def _parse_ai_action(action: str):
    """Pure parser — returns (action_type, detail, exec_fn) or (None, error_message, None).

    exec_fn takes no args and performs the DB mutation + activity log, returning the new row id.
    """
    # Pattern: "add [qty] [item] to inventory"
    m = re.match(r'add\s+(\d+)\s+(.+?)\s+to\s+inventory', action, re.IGNORECASE)
    if m:
        qty = max(1, min(int(m.group(1)), 100000))
        item_name = m.group(2).strip()[:200]

        def _exec():
            with db_session() as db:
                db.execute(
                    'INSERT INTO inventory (name, quantity, category) VALUES (?, ?, ?)',
                    (item_name, qty, 'other'))
                db.commit()
                row_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
                log_activity('inventory_added', 'ai', f'Added {qty} {item_name} via AI action')
            return row_id
        return 'add_inventory', f'Add {qty} {item_name} to inventory', _exec

    # Pattern: "log incident [desc]"
    m = re.match(r'log\s+incident\s+(.+)', action, re.IGNORECASE)
    if m:
        desc = m.group(1).strip()

        def _exec():
            with db_session() as db:
                db.execute(
                    'INSERT INTO incidents (severity, category, description) VALUES (?, ?, ?)',
                    ('info', 'other', desc))
                db.commit()
                row_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
                log_activity('incident_logged', 'ai', f'Incident: {desc[:80]}')
            return row_id
        return 'log_incident', f'Log incident: {desc}', _exec

    # Pattern: "create note [title]"
    m = re.match(r'create\s+note\s+(.+)', action, re.IGNORECASE)
    if m:
        title = m.group(1).strip()

        def _exec():
            with db_session() as db:
                db.execute('INSERT INTO notes (title, content) VALUES (?, ?)', (title, ''))
                db.commit()
                row_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
                log_activity('note_created', 'ai', f'Note: {title}')
            return row_id
        return 'create_note', f'Create note: {title}', _exec

    # Pattern: "add waypoint [name] at [lat],[lng]"
    m = re.match(r'add\s+waypoint\s+(.+?)\s+at\s+([-\d.]+)\s*,\s*([-\d.]+)', action, re.IGNORECASE)
    if m:
        wp_name = m.group(1).strip()
        try:
            lat = float(m.group(2))
            lng = float(m.group(3))
        except ValueError:
            return None, 'Invalid coordinates — lat and lng must be numbers', None
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            return None, 'Coordinates out of range (lat: -90..90, lng: -180..180)', None
        wp_name = wp_name[:200]

        def _exec():
            with db_session() as db:
                db.execute(
                    'INSERT INTO waypoints (name, lat, lng) VALUES (?, ?, ?)',
                    (wp_name, lat, lng))
                db.commit()
                row_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
                log_activity('waypoint_added', 'ai', f'Waypoint: {wp_name} ({lat},{lng})')
            return row_id
        return 'add_waypoint', f'Add waypoint {wp_name} at {lat},{lng}', _exec

    return None, None, None


@ai_bp.route('/api/ai/execute-action', methods=['POST'])
def api_ai_execute_action():
    """Parse and execute a natural-language action command.

    Two-phase commit: without ``confirmed: true`` the endpoint returns a
    preview of the parsed action so the frontend can display a confirmation
    dialog. Only when ``confirmed: true`` is passed does the action actually
    mutate the database. This prevents accidental or hallucinated AI writes.
    """
    data = request.get_json() or {}
    action = data.get('action', '').strip()
    confirmed = bool(data.get('confirmed'))
    if not action:
        return jsonify({'error': 'No action provided'}), 400
    if len(action) > 500:
        return jsonify({'error': 'Action too long (max 500 chars)'}), 400

    action_type, detail, exec_fn = _parse_ai_action(action)

    if action_type is None:
        # detail holds the error message if parsing recognised the pattern but
        # the arguments were invalid; otherwise it's None (unrecognised).
        if detail:
            return jsonify({'error': detail}), 400
        return jsonify({
            'status': 'unrecognized',
            'error': 'Could not parse action. Supported: "add [qty] [item] to inventory", '
                     '"log incident [desc]", "create note [title]", "add waypoint [name] at [lat],[lng]"',
        }), 400

    if not confirmed:
        # Preview phase — describe what would happen without mutating state.
        return jsonify({
            'status': 'preview',
            'action': action_type,
            'detail': detail,
            'requires_confirmation': True,
            'message': 'Re-POST with "confirmed": true to execute this action.',
        })

    # Execute phase — user has explicitly confirmed.
    try:
        row_id = exec_fn()
    except Exception:
        log.exception('AI action execution failed for action_type=%s', action_type)
        return jsonify({'error': 'Action failed — database write error. Check logs for details.'}), 500
    return jsonify({
        'status': 'executed',
        'action': action_type,
        'detail': detail,
        'id': row_id,
    })


# ─── AI Memory ───────────────────────────────────────────────────

@ai_bp.route('/api/ai/memory', methods=['GET'])
@require_auth('user')
def api_ai_memory_list():
    """List persistent AI memory facts."""
    with db_session() as db:
        row = db.execute("SELECT value FROM settings WHERE key = 'ai_memory'").fetchone()
    memories = _safe_ai_memories(row['value'] if row else None)
    return jsonify({'memories': memories})


@ai_bp.route('/api/ai/memory', methods=['POST'])
@require_auth('admin')
def api_ai_memory_save():
    """Save a fact to AI memory.

    AI memory is concatenated into every SITREP/chat system prompt, so
    write-access is effectively prompt injection into all future AI
    responses. Admin-gated in multi-user mode; local pywebview shell
    bypasses via the loopback exemption.
    """
    data = request.get_json() or {}
    fact = data.get('fact', '').strip()
    if not fact:
        return jsonify({'error': 'No fact provided'}), 400
    if len(fact) > 2000:
        return jsonify({'error': 'Fact too long (max 2000 chars)'}), 400
    with db_session() as db:
        row = db.execute("SELECT value FROM settings WHERE key = 'ai_memory'").fetchone()
        memories = _safe_ai_memories(row['value'] if row else None)
        memories.append({'fact': fact, 'saved_at': datetime.now().isoformat()})
        # Cap memory size to prevent unbounded growth
        if len(memories) > 200:
            memories = memories[-200:]
        db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('ai_memory', ?)",
            (json.dumps(memories),))
        db.commit()
    log_activity('ai_memory_saved', 'ai', f'Memory: {fact[:60]}')
    return jsonify({'status': 'saved', 'count': len(memories)})


@ai_bp.route('/api/ai/memory', methods=['DELETE'])
@require_auth('admin')
def api_ai_memory_clear():
    """Clear all AI memory."""
    with db_session() as db:
        db.execute("DELETE FROM settings WHERE key = 'ai_memory'")
        db.commit()
    log_activity('ai_memory_cleared', 'ai', 'All AI memories cleared')
    return jsonify({'status': 'cleared'})


# ─── RAG scope manager (Phase A3) ─────────────────────────────────────────

def _rag_scope_row_to_dict(row):
    return {
        'table_name':   row['table_name'],
        'label':        row['label'],
        'enabled':      bool(row['enabled']),
        'weight':       int(row['weight']),
        'max_rows':     int(row['max_rows']),
        'formatter':    row['formatter'],
        'columns_json': row['columns_json'],
        'source':       row['source'],
    }


@ai_bp.route('/api/ai/rag/scope', methods=['GET'])
def api_ai_rag_scope_list():
    """Return all rag_scope entries ordered by weight (emission order)."""
    with db_session() as db:
        try:
            rows = db.execute(
                'SELECT table_name, label, enabled, weight, max_rows, '
                'formatter, columns_json, source FROM rag_scope '
                'ORDER BY weight DESC, table_name ASC'
            ).fetchall()
        except Exception:
            rows = []
    return jsonify({'scope': [_rag_scope_row_to_dict(r) for r in rows]})


@ai_bp.route('/api/ai/rag/scope', methods=['POST'])
@require_auth('admin')
def api_ai_rag_scope_update():
    """Update a single rag_scope row, or create a custom entry.

    Request body:
        table_name (required, identifier)
        label        (optional — required on custom-insert)
        enabled      (optional, 0/1/bool)
        weight       (optional, int)
        max_rows     (optional, int, clamped to 1..500)
        formatter    (optional, 'builtin' | 'generic'; defaults to 'generic')
        columns_json (optional, JSON array of column names)
    """
    data = request.get_json(silent=True) or {}
    table_name = str(data.get('table_name') or '').strip()
    if not table_name or not _RAG_IDENT_RE.match(table_name):
        return jsonify({'error': 'Invalid table_name'}), 400

    with db_session() as db:
        existing = db.execute(
            'SELECT * FROM rag_scope WHERE table_name = ?',
            (table_name,),
        ).fetchone()

        if existing is None:
            # Custom insert — require label so the section has a header
            label = str(data.get('label') or '').strip()
            if not label:
                return jsonify({'error': 'label is required for a new scope entry'}), 400
            # Verify the table actually exists in the live schema before persisting
            try:
                live = db.execute(f'PRAGMA table_info({table_name})').fetchall()
            except Exception:
                live = []
            if not live:
                return jsonify({'error': f'Unknown table: {table_name}'}), 400

            enabled = 1 if bool(data.get('enabled', True)) else 0
            weight = int(data.get('weight', 20))
            max_rows = max(1, min(500, int(data.get('max_rows', 10))))
            formatter = data.get('formatter', 'generic')
            if formatter not in ('builtin', 'generic'):
                formatter = 'generic'
            cols = data.get('columns_json')
            if isinstance(cols, list):
                cols = json.dumps(cols)
            elif cols is not None and not isinstance(cols, str):
                cols = None
            db.execute(
                '''INSERT INTO rag_scope
                   (table_name, label, enabled, weight, max_rows, formatter, columns_json, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'custom')''',
                (table_name, label, enabled, weight, max_rows, formatter, cols),
            )
            db.commit()
            log_activity('rag_scope_created', 'ai', f'Added custom RAG table: {table_name}')
            return jsonify({'status': 'created', 'table_name': table_name})

        # Update path — only update fields explicitly provided
        sets, params = [], []
        if 'enabled' in data:
            sets.append('enabled = ?')
            params.append(1 if bool(data['enabled']) else 0)
        if 'weight' in data:
            try:
                sets.append('weight = ?')
                params.append(int(data['weight']))
            except (TypeError, ValueError):
                return jsonify({'error': 'weight must be integer'}), 400
        if 'max_rows' in data:
            try:
                params.append(max(1, min(500, int(data['max_rows']))))
                sets.append('max_rows = ?')
            except (TypeError, ValueError):
                return jsonify({'error': 'max_rows must be integer'}), 400
        if 'label' in data:
            label = str(data['label'] or '').strip()
            if label:
                sets.append('label = ?')
                params.append(label)
        if 'columns_json' in data:
            cols = data['columns_json']
            if isinstance(cols, list):
                cols = json.dumps(cols)
            elif cols is not None and not isinstance(cols, str):
                cols = None
            sets.append('columns_json = ?')
            params.append(cols)

        if not sets:
            return jsonify({'error': 'No updatable fields in request'}), 400

        sets.append("updated_at = CURRENT_TIMESTAMP")
        params.append(table_name)
        db.execute(
            f'UPDATE rag_scope SET {", ".join(sets)} WHERE table_name = ?',
            params,
        )
        db.commit()
    log_activity('rag_scope_updated', 'ai', f'Updated RAG scope: {table_name}')
    return jsonify({'status': 'updated', 'table_name': table_name})


@ai_bp.route('/api/ai/rag/scope/<table_name>', methods=['DELETE'])
@require_auth('admin')
def api_ai_rag_scope_delete(table_name):
    """Delete a custom scope entry. Builtin entries cannot be deleted —
    disable them instead (so the seeder won't re-create an entry that was
    intentionally removed)."""
    if not _RAG_IDENT_RE.match(table_name or ''):
        return jsonify({'error': 'Invalid table_name'}), 400
    with db_session() as db:
        row = db.execute(
            'SELECT source FROM rag_scope WHERE table_name = ?',
            (table_name,),
        ).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        if row['source'] != 'custom':
            return jsonify({'error': 'Cannot delete builtin entry — disable it instead'}), 400
        db.execute('DELETE FROM rag_scope WHERE table_name = ?', (table_name,))
        db.commit()
    log_activity('rag_scope_deleted', 'ai', f'Removed custom RAG table: {table_name}')
    return jsonify({'status': 'deleted'})


@ai_bp.route('/api/ai/rag/scope/reset', methods=['POST'])
@require_auth('admin')
def api_ai_rag_scope_reset():
    """Reset all builtin entries to defaults. Leaves custom entries intact."""
    from db import _RAG_SCOPE_DEFAULTS  # local import to avoid circularity at module load
    with db_session() as db:
        for (table_name, label, enabled, weight, max_rows, formatter, columns_json) in _RAG_SCOPE_DEFAULTS:
            db.execute(
                '''UPDATE rag_scope
                   SET label = ?, enabled = ?, weight = ?, max_rows = ?,
                       formatter = ?, columns_json = ?,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE table_name = ? AND source = 'builtin' ''',
                (label, enabled, weight, max_rows, formatter, columns_json, table_name),
            )
        db.commit()
    log_activity('rag_scope_reset', 'ai', 'RAG scope reset to defaults')
    return jsonify({'status': 'reset'})


@ai_bp.route('/api/ai/rag/preview', methods=['GET'])
def api_ai_rag_preview():
    """Return the exact context the LLM would receive, for debugging.
    ?detail_level=summary|full (default 'full')."""
    detail = request.args.get('detail_level', 'full')
    if detail not in ('summary', 'full'):
        detail = 'full'
    with db_session() as db:
        sections = build_situation_context(db, detail_level=detail)
    payload = '\n\n'.join(sections)
    return jsonify({
        'detail_level':  detail,
        'section_count': len(sections),
        'char_count':    len(payload),
        'sections':      sections,
        'payload':       payload,
    })
