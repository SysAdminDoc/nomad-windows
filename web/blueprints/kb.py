"""Knowledge base, document management, and OCR pipeline routes."""

import json
import logging
import os
import shutil
import threading
import time

from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

from config import get_data_dir, Config
from platform_utils import get_data_base
from db import db_session, log_activity
from services import ollama, qdrant, stirling
from web.state import _embed_state, _ocr_pipeline_state, _ocr_processed_files, _OCR_PROCESSED_MAX

log = logging.getLogger('nomad.web')

kb_bp = Blueprint('kb', __name__)

EMBED_MODEL = Config.EMBED_MODEL
CHUNK_SIZE = Config.CHUNK_SIZE
CHUNK_OVERLAP = Config.CHUNK_OVERLAP

DOC_CATEGORIES = ['medical', 'property', 'vehicle', 'financial', 'legal', 'reference', 'personal', 'other']


# ─── Helper Functions ───────────────────────────────────────────────

def get_kb_upload_dir():
    path = os.path.join(get_data_dir(), 'kb_uploads')
    os.makedirs(path, exist_ok=True)
    return path


def _clone_json_fallback(fallback):
    if isinstance(fallback, list):
        return list(fallback)
    if isinstance(fallback, dict):
        return dict(fallback)
    return fallback


def _safe_json_list(value, fallback=None):
    if fallback is None:
        fallback = []
    if value in (None, ''):
        return _clone_json_fallback(fallback)
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return _clone_json_fallback(fallback)
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            return _clone_json_fallback(fallback)
        return list(parsed) if isinstance(parsed, list) else _clone_json_fallback(fallback)
    return _clone_json_fallback(fallback)


def _safe_index_list(value):
    indices = []
    for item in _safe_json_list(value, []):
        if isinstance(item, bool):
            continue
        if isinstance(item, int):
            indices.append(item)
            continue
        if isinstance(item, str):
            text = item.strip()
            if text.lstrip('-').isdigit():
                indices.append(int(text))
    return indices


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Split text into chunks respecting paragraph boundaries and sentences."""
    if not text or not text.strip():
        return []

    # Split on paragraph boundaries (double newlines)
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

    chunks = []
    current_chunk = []
    current_words = 0
    current_heading = ''

    for para in paragraphs:
        # Detect headings (lines starting with # or all-caps short lines)
        lines = para.split('\n')
        if lines and (lines[0].startswith('#') or (len(lines[0]) < 80 and lines[0].isupper())):
            current_heading = lines[0].lstrip('#').strip()

        para_words = len(para.split())

        if current_words + para_words > chunk_size and current_chunk:
            # Emit current chunk
            chunk_text_str = '\n\n'.join(current_chunk)
            if current_heading:
                chunk_text_str = f'[{current_heading}]\n{chunk_text_str}'
            chunks.append(chunk_text_str)

            # Overlap: keep last paragraph if it's short
            if para_words < overlap:
                current_chunk = [current_chunk[-1]] if current_chunk else []
                current_words = len(current_chunk[0].split()) if current_chunk else 0
            else:
                current_chunk = []
                current_words = 0

        current_chunk.append(para)
        current_words += para_words

    # Emit remaining
    if current_chunk:
        chunk_text_str = '\n\n'.join(current_chunk)
        if current_heading:
            chunk_text_str = f'[{current_heading}]\n{chunk_text_str}'
        chunks.append(chunk_text_str)

    return chunks if chunks else [text[:chunk_size * 5]]


def embed_text(texts, prefix='search_document: '):
    """Embed texts using Ollama's embedding API."""
    import requests as rq
    prefixed = [prefix + t for t in texts]
    resp = rq.post(
        f'http://localhost:{ollama.OLLAMA_PORT}/api/embed',
        json={'model': EMBED_MODEL, 'input': prefixed},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json().get('embeddings', [])


def extract_text_from_file(filepath, content_type):
    """Extract text from uploaded file."""
    if content_type == 'pdf':
        try:
            import PyPDF2
            text = ''
            with open(filepath, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() or ''
            return text
        except Exception as e:
            log.error(f'PDF extraction failed: {e}')
            return ''
    else:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()


def _analyze_document(doc_id, text, filename):
    """Background: classify, summarize, extract entities from a document using AI."""
    with db_session() as db:
        try:
            models = ollama.list_models() if ollama.running() else []
            if not models:
                db.execute("UPDATE documents SET doc_category = 'other', summary = 'AI analysis unavailable \u2014 start Ollama for document intelligence.' WHERE id = ?", (doc_id,))
                db.commit()
                return

            model = models[0]['name']
            import requests as req
            text_sample = text[:3000]

            classify_prompt = f"""Classify this document into ONE category: medical, property, vehicle, financial, legal, reference, personal, other.

Document filename: {filename}
Document text (first 3000 chars):
{text_sample}

Respond with ONLY the category word, nothing else."""

            r = req.post(f'http://localhost:{ollama.OLLAMA_PORT}/api/generate',
                        json={'model': model, 'prompt': classify_prompt, 'stream': False}, timeout=20)
            cat_words = r.json().get('response', '').strip().lower().split() if r.ok else []
            category = cat_words[0] if cat_words else 'other'
            if category not in DOC_CATEGORIES:
                category = 'other'

            summary_prompt = f"""Write a 2-3 sentence summary of this document. Be concise and factual.

Document: {filename}
Text: {text_sample}

Summary:"""

            r = req.post(f'http://localhost:{ollama.OLLAMA_PORT}/api/generate',
                        json={'model': model, 'prompt': summary_prompt, 'stream': False}, timeout=20)
            summary = r.json().get('response', '').strip()[:500] if r.ok else ''

            entity_prompt = f"""Extract key entities from this document as a JSON array. Include: names (people), dates, medications, addresses, phone numbers, vehicle info (make/model/year/VIN), dollar amounts, and GPS coordinates if present.

Document: {filename}
Text: {text_sample}

Respond with ONLY a JSON array of objects, each with "type" and "value" keys. Example: [{{"type":"person","value":"John Smith"}},{{"type":"medication","value":"Lisinopril 10mg"}}]
If no entities found, respond with: []"""

            r = req.post(f'http://localhost:{ollama.OLLAMA_PORT}/api/generate',
                        json={'model': model, 'prompt': entity_prompt, 'stream': False, 'format': 'json'}, timeout=25)
            entities_raw = r.json().get('response', '[]') if r.ok else '[]'
            try:
                entities = json.loads(entities_raw)
                if not isinstance(entities, list):
                    entities = []
            except Exception:
                entities = []

            linked = []
            if entities:
                contacts = [dict(r) for r in db.execute('SELECT id, name FROM contacts').fetchall()]
                contact_names = {c['name'].lower(): c['id'] for c in contacts}
                for ent in entities:
                    if ent.get('type') == 'person' and ent.get('value', '').lower() in contact_names:
                        linked.append({'type': 'contact', 'id': contact_names[ent['value'].lower()], 'name': ent['value']})

            db.execute("UPDATE documents SET doc_category = ?, summary = ?, entities = ?, linked_records = ? WHERE id = ?",
                       (category, summary, json.dumps(entities), json.dumps(linked), doc_id))
            db.commit()
            log.info(f'Document {doc_id} analyzed: {category}, {len(entities)} entities, {len(linked)} links')
        except Exception as e:
            log.error(f'Document analysis failed for {doc_id}: {e}')
            db.execute("UPDATE documents SET doc_category = 'other', summary = ? WHERE id = ?",
                       (f'Analysis failed: {e}', doc_id))
            db.commit()
# ─── KB Upload ──────────────────────────────────────────────────────

@kb_bp.route('/api/kb/upload', methods=['POST'])
def api_kb_upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No filename'}), 400

    filename = secure_filename(file.filename)
    if not filename:
        return jsonify({'error': 'Invalid filename'}), 400
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    content_type = 'pdf' if ext == 'pdf' else 'text'

    upload_dir = get_kb_upload_dir()
    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)
    file_size = os.path.getsize(filepath)

    # Auto-OCR for PDFs via Stirling if available
    if filename.lower().endswith('.pdf') and stirling.running():
        try:
            import requests as _req
            with open(filepath, 'rb') as pdf_file:
                ocr_resp = _req.post(
                    f'http://localhost:8443/api/v1/misc/ocr-pdf',
                    files={'fileInput': (filename, pdf_file, 'application/pdf')},
                    data={'language': 'eng', 'sidecar': 'true'},
                    timeout=120
                )
                if ocr_resp.ok:
                    ocr_path = filepath + '.ocr.pdf'
                    with open(ocr_path, 'wb') as f:
                        f.write(ocr_resp.content)
                    os.replace(ocr_path, filepath)
                    log.info(f'Auto-OCR completed for {filename}')
        except Exception as e:
            log.warning(f'Auto-OCR failed for {filename}: {e}')

    with db_session() as db:
        cur = db.execute('INSERT INTO documents (filename, content_type, file_size, status) VALUES (?, ?, ?, ?)',
                         (filename, content_type, file_size, 'pending'))
        db.commit()
        doc_id = cur.lastrowid
    # Start embedding in background
    def do_embed():
        import web.state as _ws
        _ws._embed_state.clear()
        _ws._embed_state.update({'status': 'processing', 'doc_id': doc_id, 'progress': 0, 'detail': f'Processing {filename}...'})
        with db_session() as db2:
          try:
            _ws._embed_state['detail'] = 'Checking embedding model...'
            models = ollama.list_models()
            model_names = [m['name'] for m in models]
            if EMBED_MODEL not in model_names and EMBED_MODEL.split(':')[0] not in [m.split(':')[0] for m in model_names]:
                _ws._embed_state['detail'] = f'Pulling {EMBED_MODEL}...'
                ollama.pull_model(EMBED_MODEL)

            _ws._embed_state.update({'progress': 20, 'detail': 'Extracting text...'})
            text = extract_text_from_file(filepath, content_type)
            if not text.strip():
                raise ValueError('No text could be extracted from file')

            _ws._embed_state.update({'progress': 30, 'detail': 'Chunking text...'})
            chunks = chunk_text(text)
            total = len(chunks)

            _ws._embed_state.update({'progress': 40, 'detail': f'Embedding {total} chunks...'})
            batch_size = 8
            all_points = []
            import hashlib
            for i in range(0, total, batch_size):
                batch = chunks[i:i + batch_size]
                vectors = embed_text(batch)
                for j, (chunk, vec) in enumerate(zip(batch, vectors)):
                    point_id = int(hashlib.md5(f'{doc_id}:{i+j}'.encode()).hexdigest()[:8], 16)
                    all_points.append({
                        'id': point_id,
                        'vector': vec,
                        'payload': {
                            'doc_id': doc_id,
                            'filename': filename,
                            'chunk_index': i + j,
                            'text': chunk,
                        }
                    })
                pct = 40 + int(60 * min(i + batch_size, total) / total)
                _ws._embed_state.update({'progress': pct, 'detail': f'Embedded {min(i+batch_size, total)}/{total} chunks'})

            qdrant.upsert_vectors(all_points)

            db2.execute('UPDATE documents SET status = ?, chunks_count = ? WHERE id = ?',
                        ('ready', total, doc_id))
            db2.commit()
            _ws._embed_state.clear()
            _ws._embed_state.update({'status': 'complete', 'doc_id': doc_id, 'progress': 100, 'detail': f'{filename}: {total} chunks embedded'})

            threading.Thread(target=_analyze_document, args=(doc_id, text, filename), daemon=True).start()

          except Exception as e:
            log.error(f'Embedding failed for doc {doc_id}: {e}')
            db2.execute('UPDATE documents SET status = ?, error = ? WHERE id = ?', ('error', str(e), doc_id))
            db2.commit()
            _ws._embed_state.clear()
            _ws._embed_state.update({'status': 'error', 'doc_id': doc_id, 'progress': 0, 'detail': str(e)})
    threading.Thread(target=do_embed, daemon=True).start()
    return jsonify({'status': 'uploading', 'doc_id': doc_id}), 201


# ─── KB Documents CRUD ──────────────────────────────────────────────

@kb_bp.route('/api/kb/documents')
def api_kb_documents():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        docs = db.execute('SELECT * FROM documents ORDER BY created_at DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    return jsonify([dict(d) for d in docs])


@kb_bp.route('/api/kb/documents/<int:doc_id>', methods=['DELETE'])
def api_kb_document_delete(doc_id):
    with db_session() as db:
        doc = db.execute('SELECT filename FROM documents WHERE id = ?', (doc_id,)).fetchone()
        if doc:
            filepath = os.path.join(get_kb_upload_dir(), doc['filename'])
            if os.path.isfile(filepath):
                os.remove(filepath)
            qdrant.delete_by_doc_id(doc_id)
            db.execute('DELETE FROM documents WHERE id = ?', (doc_id,))
            db.commit()
    return jsonify({'status': 'deleted'})


# ─── KB Status & Search ────────────────────────────────────────────

@kb_bp.route('/api/kb/status')
def api_kb_status():
    info = qdrant.get_collection_info() if qdrant.running() else {'points_count': 0}
    return jsonify({**_embed_state, 'collection': info, 'qdrant_running': qdrant.running()})


@kb_bp.route('/api/kb/search', methods=['POST'])
def api_kb_search():
    data = request.get_json() or {}
    query = data.get('query', '')
    limit = data.get('limit', 5)
    workspace_id = data.get('workspace_id') or request.args.get('workspace_id')
    if not query:
        return jsonify([])
    try:
        vectors = embed_text([query], prefix='search_query: ')
        if not vectors:
            return jsonify([])
        # Build filter for workspace-scoped search
        filter_params = None
        if workspace_id:
            filter_params = {"must": [{"key": "workspace_id", "match": {"value": int(workspace_id)}}]}
        results = qdrant.search(vectors[0], limit=limit, filter_params=filter_params)
        return jsonify([{
            'text': r.get('payload', {}).get('text', ''),
            'filename': r.get('payload', {}).get('filename', ''),
            'score': r.get('score', 0),
        } for r in results])
    except Exception as e:
        log.error(f'KB search failed: {e}')
        return jsonify([])


# ─── Document Analysis ──────────────────────────────────────────────

@kb_bp.route('/api/kb/documents/<int:doc_id>/analyze', methods=['POST'])
def api_kb_analyze(doc_id):
    """Trigger AI analysis (classify, summarize, extract) for a document."""
    with db_session() as db:
        doc = db.execute('SELECT * FROM documents WHERE id = ?', (doc_id,)).fetchone()
    if not doc:
        return jsonify({'error': 'Not found'}), 404

    filepath = os.path.join(get_kb_upload_dir(), doc['filename'])
    if not os.path.isfile(filepath):
        return jsonify({'error': 'File not found on disk'}), 404

    text = extract_text_from_file(filepath, doc['content_type'])
    threading.Thread(target=_analyze_document, args=(doc_id, text, doc['filename']), daemon=True).start()
    return jsonify({'status': 'analyzing'})


@kb_bp.route('/api/kb/documents/<int:doc_id>/details')
def api_kb_doc_details(doc_id):
    """Get full document details including analysis results."""
    with db_session() as db:
        doc = db.execute('SELECT * FROM documents WHERE id = ?', (doc_id,)).fetchone()
    if not doc:
        return jsonify({'error': 'Not found'}), 404
    d = dict(doc)
    d['entities'] = _safe_json_list(d.get('entities'), [])
    d['linked_records'] = _safe_json_list(d.get('linked_records'), [])
    return jsonify(d)


@kb_bp.route('/api/kb/documents/<int:doc_id>/import-entities', methods=['POST'])
def api_kb_import_entities(doc_id):
    """Import extracted entities from a document into structured tables."""
    with db_session() as db:
        doc = db.execute('SELECT entities FROM documents WHERE id = ?', (doc_id,)).fetchone()
        if not doc:
            return jsonify({'error': 'Not found'}), 404

        entities = _safe_json_list(doc['entities'], [])

        if not entities:
            return jsonify({'error': 'No entities to import'}), 400

        data = request.get_json() or {}
        selected = _safe_index_list(data.get('entities'))
        if selected:
            entities = [entities[i] for i in selected if 0 <= i < len(entities)]

        imported = {'contacts': 0, 'inventory': 0, 'waypoints': 0, 'skipped': 0}

        for ent in entities:
            etype = ent.get('type', '').lower()
            value = ent.get('value', '').strip()
            if not value:
                imported['skipped'] += 1
                continue

            if etype == 'person':
                existing = db.execute('SELECT id FROM contacts WHERE LOWER(name) = LOWER(?)', (value,)).fetchone()
                if not existing:
                    db.execute('INSERT INTO contacts (name, role, notes) VALUES (?, ?, ?)',
                               (value, '', f'Auto-imported from document #{doc_id}'))
                    imported['contacts'] += 1
                else:
                    imported['skipped'] += 1

            elif etype == 'medication':
                existing = db.execute('SELECT id FROM inventory WHERE LOWER(name) = LOWER(?)', (value,)).fetchone()
                if not existing:
                    db.execute('INSERT INTO inventory (name, category, quantity, unit, notes) VALUES (?, ?, ?, ?, ?)',
                               (value, 'medical', 0, 'ea', f'Auto-imported from document #{doc_id}'))
                    imported['inventory'] += 1
                else:
                    imported['skipped'] += 1

            elif etype == 'coordinates':
                import re
                coords = re.findall(r'[-+]?\d+\.?\d*', value)
                if len(coords) >= 2:
                    try:
                        lat, lng = float(coords[0]), float(coords[1])
                        if -90 <= lat <= 90 and -180 <= lng <= 180:
                            db.execute('INSERT INTO waypoints (name, lat, lng, icon, notes) VALUES (?, ?, ?, ?, ?)',
                                       (f'Doc #{doc_id} location', lat, lng, 'pin', f'Auto-imported: {value}'))
                            imported['waypoints'] += 1
                        else:
                            imported['skipped'] += 1
                    except (ValueError, TypeError):
                        imported['skipped'] += 1
                else:
                    imported['skipped'] += 1

            elif etype == 'phone':
                person_entities = [e for e in entities if e.get('type') == 'person']
                if person_entities:
                    pname = person_entities[0]['value'].strip()
                    existing = db.execute('SELECT id FROM contacts WHERE LOWER(name) = LOWER(?)', (pname,)).fetchone()
                    if existing:
                        db.execute('UPDATE contacts SET phone = ? WHERE id = ? AND (phone IS NULL OR phone = "")',
                                   (value, existing['id']))
                        imported['contacts'] += 1
                    else:
                        imported['skipped'] += 1
                else:
                    imported['skipped'] += 1

            elif etype == 'address':
                imported['skipped'] += 1

            else:
                imported['skipped'] += 1

        db.commit()
        total = imported['contacts'] + imported['inventory'] + imported['waypoints']
        log_activity('entity_import', 'documents', f'Imported {total} entities from doc #{doc_id}')
        return jsonify({'status': 'imported', 'results': imported, 'total_imported': total})
@kb_bp.route('/api/kb/analyze-all', methods=['POST'])
def api_kb_analyze_all():
    """Analyze all unanalyzed documents."""
    with db_session() as db:
        docs = db.execute("SELECT * FROM documents WHERE (doc_category IS NULL OR doc_category = '') AND status = 'ready'").fetchall()
    count = 0
    for doc in docs:
        filepath = os.path.join(get_kb_upload_dir(), doc['filename'])
        if os.path.isfile(filepath):
            text = extract_text_from_file(filepath, doc['content_type'])
            threading.Thread(target=_analyze_document, args=(doc['id'], text, doc['filename']), daemon=True).start()
            count += 1
            time.sleep(0.5)
    return jsonify({'status': 'analyzing', 'count': count})


# ─── KB Workspaces ──────────────────────────────────────────────────

@kb_bp.route('/api/kb/workspaces', methods=['GET'])
def api_kb_workspaces():
    """List knowledge base workspaces."""
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM kb_workspaces ORDER BY name LIMIT ? OFFSET ?', (limit, offset)).fetchall()
        return jsonify([dict(r) for r in rows])
@kb_bp.route('/api/kb/workspaces', methods=['POST'])
def api_kb_workspace_create():
    """Create a KB workspace."""
    d = request.json or {}
    name = d.get('name', '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400
    with db_session() as db:
        db.execute(
            'INSERT INTO kb_workspaces (name, description, watch_folder, auto_index) VALUES (?, ?, ?, ?)',
            (name, d.get('description', ''), d.get('watch_folder', ''), d.get('auto_index', 0))
        )
        db.commit()
        wid = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        return jsonify({'id': wid, 'status': 'ok'})
@kb_bp.route('/api/kb/workspaces/<int:wid>', methods=['DELETE'])
def api_kb_workspace_delete(wid):
    """Delete a KB workspace."""
    with db_session() as db:
        r = db.execute('DELETE FROM kb_workspaces WHERE id = ?', (wid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
        return jsonify({'status': 'ok'})
# ─── Auto-OCR Pipeline ─────────────────────────────────────────────

def _ocr_pipeline_scan():
    """Scan watch folders for new files and process them."""
    import datetime
    with db_session() as db:
        workspaces = db.execute(
            'SELECT * FROM kb_workspaces WHERE auto_index = 1 AND watch_folder IS NOT NULL AND watch_folder != ""'
        ).fetchall()
    for ws in workspaces:
        folder = ws['watch_folder']
        if not os.path.isdir(folder):
            continue

        for fname in os.listdir(folder):
            fpath = os.path.join(folder, fname)
            if not os.path.isfile(fpath):
                continue
            ext = fname.rsplit('.', 1)[-1].lower() if '.' in fname else ''
            if ext not in ('pdf', 'txt', 'md', 'csv', 'html'):
                continue
            file_key = f'{ws["id"]}:{fpath}:{os.path.getmtime(fpath)}'
            if file_key in _ocr_processed_files:
                continue

            try:
                safe_name = secure_filename(fname)
                if not safe_name:
                    continue
                dest = os.path.join(get_kb_upload_dir(), safe_name)
                shutil.copy2(fpath, dest)

                content_type = 'pdf' if ext == 'pdf' else 'text'

                if ext == 'pdf' and stirling.running():
                    try:
                        import requests as _req
                        with open(dest, 'rb') as pdf_file:
                            ocr_resp = _req.post(
                                'http://localhost:8443/api/v1/misc/ocr-pdf',
                                files={'fileInput': (safe_name, pdf_file, 'application/pdf')},
                                data={'language': 'eng', 'sidecar': 'true'},
                                timeout=120
                            )
                            if ocr_resp.ok:
                                ocr_path = dest + '.ocr.pdf'
                                with open(ocr_path, 'wb') as f:
                                    f.write(ocr_resp.content)
                                os.replace(ocr_path, dest)
                                log.info(f'Auto-OCR pipeline: OCR completed for {safe_name}')
                    except Exception as e:
                        log.warning(f'Auto-OCR pipeline: OCR failed for {safe_name}: {e}')

                file_size = os.path.getsize(dest)
                with db_session() as db2:
                    db2.execute(
                        'INSERT INTO documents (filename, content_type, file_size, status, doc_category) VALUES (?, ?, ?, ?, ?)',
                        (safe_name, content_type, file_size, 'pending', f'watch:{ws["name"]}')
                    )
                    db2.commit()
                _ocr_processed_files.add(file_key)
                if len(_ocr_processed_files) > _OCR_PROCESSED_MAX:
                    # Shed half to avoid re-processing everything after eviction
                    to_remove = list(_ocr_processed_files)[:len(_ocr_processed_files) // 2]
                    _ocr_processed_files.difference_update(to_remove)
                _ocr_pipeline_state['processed'] += 1
                log_activity('ocr_pipeline', 'import', f'Auto-imported {safe_name} from {ws["name"]}')
            except Exception as e:
                _ocr_pipeline_state['errors'] += 1
                log.warning(f'Auto-OCR pipeline error for {fname}: {e}')

    _ocr_pipeline_state['last_scan'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _ocr_pipeline_loop():
    """Background loop that scans watch folders every 60 seconds."""
    _ocr_pipeline_state['running'] = True
    while _ocr_pipeline_state['running']:
        try:
            _ocr_pipeline_scan()
        except Exception as e:
            log.error(f'Auto-OCR pipeline loop error: {e}')
        time.sleep(60)


@kb_bp.route('/api/kb/ocr-pipeline/status')
def api_ocr_pipeline_status():
    return jsonify(_ocr_pipeline_state)


@kb_bp.route('/api/kb/ocr-pipeline/start', methods=['POST'])
def api_ocr_pipeline_start():
    if _ocr_pipeline_state['running']:
        return jsonify({'status': 'already_running'})
    t = threading.Thread(target=_ocr_pipeline_loop, daemon=True, name='ocr-pipeline')
    t.start()
    return jsonify({'status': 'started'})


@kb_bp.route('/api/kb/ocr-pipeline/stop', methods=['POST'])
def api_ocr_pipeline_stop():
    _ocr_pipeline_state['running'] = False
    return jsonify({'status': 'stopped'})


@kb_bp.route('/api/kb/ocr-pipeline/scan', methods=['POST'])
def api_ocr_pipeline_scan_now():
    """Trigger an immediate scan of watch folders."""
    _ocr_pipeline_scan()
    return jsonify({'status': 'scanned', 'processed': _ocr_pipeline_state['processed']})
