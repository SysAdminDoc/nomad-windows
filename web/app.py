"""Flask web application — dashboard and API routes."""

import json
import os
import sys
import time
import threading
import platform
import logging
import shutil
import subprocess
from flask import Flask, render_template, jsonify, request, Response

from db import get_db
from services import ollama, kiwix, cyberchef, kolibri
from services.manager import (
    get_download_progress, get_dir_size, format_size, uninstall_service, get_services_dir
)

log = logging.getLogger('nomad.web')

SERVICE_MODULES = {
    'ollama': ollama,
    'kiwix': kiwix,
    'cyberchef': cyberchef,
    'kolibri': kolibri,
}

VERSION = '0.4.0'

# Benchmark state
_benchmark_state = {'status': 'idle', 'progress': 0, 'stage': '', 'results': None}


def create_app():
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')

    # ─── Pages ─────────────────────────────────────────────────────────

    @app.route('/')
    def dashboard():
        return render_template('index.html')

    # ─── Service API ───────────────────────────────────────────────────

    @app.route('/api/services')
    def api_services():
        services = []
        for sid, mod in SERVICE_MODULES.items():
            installed = mod.is_installed()
            install_dir = os.path.join(get_services_dir(), sid)
            disk_used = format_size(get_dir_size(install_dir)) if installed else '0 B'

            port_val = getattr(mod, f'{sid.upper()}_PORT', None)
            if port_val is None:
                for attr in ['OLLAMA_PORT', 'KIWIX_PORT', 'CYBERCHEF_PORT', 'KOLIBRI_PORT']:
                    port_val = getattr(mod, attr, None)
                    if port_val:
                        break

            services.append({
                'id': sid,
                'name': getattr(mod, 'SERVICE_ID', sid),
                'installed': installed,
                'running': mod.running() if installed else False,
                'port': port_val,
                'progress': get_download_progress(sid),
                'disk_used': disk_used,
            })
        return jsonify(services)

    @app.route('/api/services/<service_id>/install', methods=['POST'])
    def api_install_service(service_id):
        mod = SERVICE_MODULES.get(service_id)
        if not mod:
            return jsonify({'error': 'Unknown service'}), 404
        if mod.is_installed():
            return jsonify({'status': 'already_installed'})

        def do_install():
            try:
                mod.install()
            except Exception as e:
                log.error(f'Install failed for {service_id}: {e}')

        threading.Thread(target=do_install, daemon=True).start()
        return jsonify({'status': 'installing'})

    @app.route('/api/services/<service_id>/start', methods=['POST'])
    def api_start_service(service_id):
        mod = SERVICE_MODULES.get(service_id)
        if not mod:
            return jsonify({'error': 'Unknown service'}), 404
        if not mod.is_installed():
            return jsonify({'error': 'Not installed'}), 400
        try:
            mod.start()
            return jsonify({'status': 'started'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/services/<service_id>/stop', methods=['POST'])
    def api_stop_service(service_id):
        mod = SERVICE_MODULES.get(service_id)
        if not mod:
            return jsonify({'error': 'Unknown service'}), 404
        try:
            mod.stop()
            return jsonify({'status': 'stopped'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/services/<service_id>/restart', methods=['POST'])
    def api_restart_service(service_id):
        mod = SERVICE_MODULES.get(service_id)
        if not mod:
            return jsonify({'error': 'Unknown service'}), 404
        try:
            mod.stop()
            time.sleep(1)
            mod.start()
            return jsonify({'status': 'restarted'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/services/<service_id>/uninstall', methods=['POST'])
    def api_uninstall_service(service_id):
        if service_id not in SERVICE_MODULES:
            return jsonify({'error': 'Unknown service'}), 404
        uninstall_service(service_id)
        return jsonify({'status': 'uninstalled'})

    @app.route('/api/services/<service_id>/progress')
    def api_service_progress(service_id):
        return jsonify(get_download_progress(service_id))

    # ─── Ollama AI Chat API ───────────────────────────────────────────

    @app.route('/api/ai/models')
    def api_ai_models():
        if not ollama.is_installed() or not ollama.running():
            return jsonify([])
        return jsonify(ollama.list_models())

    @app.route('/api/ai/pull', methods=['POST'])
    def api_ai_pull():
        data = request.get_json()
        model_name = data.get('model', ollama.DEFAULT_MODEL)

        def do_pull():
            ollama.pull_model(model_name)

        threading.Thread(target=do_pull, daemon=True).start()
        return jsonify({'status': 'pulling', 'model': model_name})

    @app.route('/api/ai/pull-progress')
    def api_ai_pull_progress():
        return jsonify(ollama.get_pull_progress())

    @app.route('/api/ai/delete', methods=['POST'])
    def api_ai_delete():
        data = request.get_json()
        model_name = data.get('model')
        if not model_name:
            return jsonify({'error': 'No model specified'}), 400
        success = ollama.delete_model(model_name)
        return jsonify({'status': 'deleted' if success else 'error'})

    @app.route('/api/ai/chat', methods=['POST'])
    def api_ai_chat():
        data = request.get_json()
        model = data.get('model', ollama.DEFAULT_MODEL)
        messages = data.get('messages', [])
        system_prompt = data.get('system_prompt', '')

        if not ollama.running():
            return jsonify({'error': 'Ollama is not running'}), 503

        if system_prompt:
            messages = [{'role': 'system', 'content': system_prompt}] + messages

        def generate():
            try:
                for line in ollama.chat(model, messages, stream=True):
                    if line:
                        yield line.decode('utf-8') + '\n'
            except Exception as e:
                yield json.dumps({'error': str(e)}) + '\n'

        return Response(generate(), mimetype='text/event-stream')

    @app.route('/api/ai/recommended')
    def api_ai_recommended():
        return jsonify(ollama.RECOMMENDED_MODELS)

    # ─── Kiwix ZIM API ─────────────────────────────────────────────────

    @app.route('/api/kiwix/zims')
    def api_kiwix_zims():
        if not kiwix.is_installed():
            return jsonify([])
        return jsonify(kiwix.list_zim_files())

    @app.route('/api/kiwix/catalog')
    def api_kiwix_catalog():
        return jsonify(kiwix.get_catalog())

    @app.route('/api/kiwix/download-zim', methods=['POST'])
    def api_kiwix_download_zim():
        data = request.get_json()
        url = data.get('url', kiwix.STARTER_ZIM_URL)
        filename = data.get('filename')

        def do_download():
            try:
                kiwix.download_zim(url, filename)
                if kiwix.running():
                    log.info('Restarting Kiwix to load new ZIM content...')
                    kiwix.stop()
                    time.sleep(1)
                    kiwix.start()
            except Exception as e:
                log.error(f'ZIM download failed: {e}')

        threading.Thread(target=do_download, daemon=True).start()
        return jsonify({'status': 'downloading'})

    @app.route('/api/kiwix/delete-zim', methods=['POST'])
    def api_kiwix_delete_zim():
        data = request.get_json()
        filename = data.get('filename')
        if not filename:
            return jsonify({'error': 'No filename'}), 400
        success = kiwix.delete_zim(filename)
        return jsonify({'status': 'deleted' if success else 'error'})

    # ─── Notes API ─────────────────────────────────────────────────────

    @app.route('/api/notes')
    def api_notes_list():
        db = get_db()
        notes = db.execute('SELECT * FROM notes ORDER BY updated_at DESC').fetchall()
        db.close()
        return jsonify([dict(n) for n in notes])

    @app.route('/api/notes', methods=['POST'])
    def api_notes_create():
        data = request.get_json()
        db = get_db()
        cur = db.execute('INSERT INTO notes (title, content) VALUES (?, ?)',
                         (data.get('title', 'Untitled'), data.get('content', '')))
        db.commit()
        note_id = cur.lastrowid
        note = db.execute('SELECT * FROM notes WHERE id = ?', (note_id,)).fetchone()
        db.close()
        return jsonify(dict(note)), 201

    @app.route('/api/notes/<int:note_id>', methods=['PUT'])
    def api_notes_update(note_id):
        data = request.get_json()
        db = get_db()
        db.execute('UPDATE notes SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                   (data.get('title'), data.get('content'), note_id))
        db.commit()
        note = db.execute('SELECT * FROM notes WHERE id = ?', (note_id,)).fetchone()
        db.close()
        return jsonify(dict(note))

    @app.route('/api/notes/<int:note_id>', methods=['DELETE'])
    def api_notes_delete(note_id):
        db = get_db()
        db.execute('DELETE FROM notes WHERE id = ?', (note_id,))
        db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    # ─── Settings API ─────────────────────────────────────────────────

    @app.route('/api/settings')
    def api_settings():
        db = get_db()
        rows = db.execute('SELECT key, value FROM settings').fetchall()
        db.close()
        return jsonify({r['key']: r['value'] for r in rows})

    @app.route('/api/settings', methods=['PUT'])
    def api_settings_update():
        data = request.get_json()
        db = get_db()
        for key, value in data.items():
            db.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, str(value)))
        db.commit()
        db.close()
        return jsonify({'status': 'saved'})

    @app.route('/api/settings/wizard-complete', methods=['POST'])
    def api_wizard_complete():
        db = get_db()
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('first_run_complete', '1')")
        db.commit()
        db.close()
        return jsonify({'status': 'ok'})

    # ─── System Info ───────────────────────────────────────────────────

    @app.route('/api/system')
    def api_system():
        import psutil
        data_dir = os.path.join(os.environ.get('APPDATA', ''), 'ProjectNOMAD')
        total_disk = get_dir_size(data_dir)

        try:
            disk = shutil.disk_usage(data_dir)
            disk_free = disk.free
            disk_total = disk.total
        except Exception:
            disk_free = 0
            disk_total = 0

        try:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            cpu_count = psutil.cpu_count()
            cpu_count_phys = psutil.cpu_count(logical=False)
            cpu_name = platform.processor()
            cpu_percent = psutil.cpu_percent(interval=0.5)
        except Exception:
            mem = swap = None
            cpu_count = os.cpu_count()
            cpu_count_phys = cpu_count
            cpu_name = platform.processor()
            cpu_percent = 0

        # GPU detection
        gpu_name = 'None detected'
        gpu_vram = ''
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=5, creationflags=0x08000000,
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split(', ')
                gpu_name = parts[0]
                if len(parts) > 1:
                    gpu_vram = f'{int(parts[1])} MB'
        except Exception:
            pass

        # Disk partitions
        disk_devices = []
        try:
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    disk_devices.append({
                        'device': part.device,
                        'mountpoint': part.mountpoint,
                        'fstype': part.fstype,
                        'total': format_size(usage.total),
                        'used': format_size(usage.used),
                        'free': format_size(usage.free),
                        'percent': usage.percent,
                    })
                except Exception:
                    pass
        except Exception:
            pass

        # Uptime
        try:
            uptime_secs = time.time() - psutil.boot_time()
            days = int(uptime_secs // 86400)
            hours = int((uptime_secs % 86400) // 3600)
            mins = int((uptime_secs % 3600) // 60)
            uptime_str = f'{days}d {hours}h {mins}m' if days else f'{hours}h {mins}m'
        except Exception:
            uptime_str = 'Unknown'

        return jsonify({
            'version': VERSION,
            'platform': f'{platform.system()} {platform.release()}',
            'os_version': platform.version(),
            'hostname': platform.node(),
            'arch': platform.machine(),
            'cpu': cpu_name or f'{cpu_count} cores',
            'cpu_cores': cpu_count,
            'cpu_cores_physical': cpu_count_phys,
            'cpu_percent': cpu_percent,
            'ram_total': format_size(mem.total) if mem else 'Unknown',
            'ram_used': format_size(mem.used) if mem else 'Unknown',
            'ram_available': format_size(mem.available) if mem else 'Unknown',
            'ram_percent': mem.percent if mem else 0,
            'swap_total': format_size(swap.total) if swap else '0 B',
            'swap_used': format_size(swap.used) if swap else '0 B',
            'swap_percent': swap.percent if swap else 0,
            'gpu': gpu_name,
            'gpu_vram': gpu_vram,
            'data_dir': data_dir,
            'nomad_disk_used': format_size(total_disk),
            'disk_free': format_size(disk_free),
            'disk_total': format_size(disk_total),
            'disk_devices': disk_devices,
            'uptime': uptime_str,
        })

    @app.route('/api/system/live')
    def api_system_live():
        """Lightweight live metrics for real-time gauges."""
        import psutil
        try:
            return jsonify({
                'cpu_percent': psutil.cpu_percent(interval=0.3),
                'ram_percent': psutil.virtual_memory().percent,
                'swap_percent': psutil.swap_memory().percent,
            })
        except Exception:
            return jsonify({'cpu_percent': 0, 'ram_percent': 0, 'swap_percent': 0})

    # ─── Conversations API ────────────────────────────────────────────

    @app.route('/api/conversations')
    def api_conversations_list():
        db = get_db()
        convos = db.execute('SELECT id, title, model, created_at, updated_at FROM conversations ORDER BY updated_at DESC').fetchall()
        db.close()
        return jsonify([dict(c) for c in convos])

    @app.route('/api/conversations', methods=['POST'])
    def api_conversations_create():
        data = request.get_json() or {}
        db = get_db()
        cur = db.execute('INSERT INTO conversations (title, model, messages) VALUES (?, ?, ?)',
                         (data.get('title', 'New Chat'), data.get('model', ''), '[]'))
        db.commit()
        cid = cur.lastrowid
        convo = db.execute('SELECT * FROM conversations WHERE id = ?', (cid,)).fetchone()
        db.close()
        return jsonify(dict(convo)), 201

    @app.route('/api/conversations/<int:cid>')
    def api_conversations_get(cid):
        db = get_db()
        convo = db.execute('SELECT * FROM conversations WHERE id = ?', (cid,)).fetchone()
        db.close()
        if not convo:
            return jsonify({'error': 'Not found'}), 404
        return jsonify(dict(convo))

    @app.route('/api/conversations/<int:cid>', methods=['PUT'])
    def api_conversations_update(cid):
        data = request.get_json()
        db = get_db()
        fields = []
        vals = []
        if 'title' in data:
            fields.append('title = ?')
            vals.append(data['title'])
        if 'model' in data:
            fields.append('model = ?')
            vals.append(data['model'])
        if 'messages' in data:
            fields.append('messages = ?')
            vals.append(json.dumps(data['messages']))
        fields.append('updated_at = CURRENT_TIMESTAMP')
        vals.append(cid)
        db.execute(f'UPDATE conversations SET {", ".join(fields)} WHERE id = ?', vals)
        db.commit()
        db.close()
        return jsonify({'status': 'saved'})

    @app.route('/api/conversations/<int:cid>', methods=['DELETE'])
    def api_conversations_delete(cid):
        db = get_db()
        db.execute('DELETE FROM conversations WHERE id = ?', (cid,))
        db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    @app.route('/api/conversations/all', methods=['DELETE'])
    def api_conversations_delete_all():
        db = get_db()
        db.execute('DELETE FROM conversations')
        db.commit()
        db.close()
        return jsonify({'status': 'deleted'})

    # ─── Benchmark API ─────────────────────────────────────────────────

    @app.route('/api/benchmark/run', methods=['POST'])
    def api_benchmark_run():
        data = request.get_json() or {}
        mode = data.get('mode', 'full')  # full, system, ai

        def do_benchmark():
            import psutil
            global _benchmark_state
            _benchmark_state = {'status': 'running', 'progress': 0, 'stage': 'Starting...', 'results': None}
            results = {}
            hw = {}

            try:
                # Hardware detection
                hw['cpu'] = platform.processor() or f'{os.cpu_count()} cores'
                hw['cpu_cores'] = psutil.cpu_count()
                hw['ram_gb'] = round(psutil.virtual_memory().total / (1024**3), 1)

                try:
                    r = subprocess.run(
                        ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                        capture_output=True, text=True, timeout=5, creationflags=0x08000000,
                    )
                    hw['gpu'] = r.stdout.strip() if r.returncode == 0 else 'None'
                except Exception:
                    hw['gpu'] = 'None'

                if mode in ('full', 'system'):
                    # CPU benchmark — prime calculation
                    _benchmark_state.update({'progress': 10, 'stage': 'CPU benchmark...'})
                    start = time.time()
                    count = 0
                    while time.time() - start < 10:
                        n = 2
                        for _ in range(10000):
                            n = (n * 1103515245 + 12345) & 0x7FFFFFFF
                        count += 10000
                    cpu_score = count / 10
                    results['cpu_score'] = round(cpu_score)

                    # Memory benchmark — sequential allocation
                    _benchmark_state.update({'progress': 30, 'stage': 'Memory benchmark...'})
                    start = time.time()
                    block_size = 1024 * 1024  # 1MB
                    blocks = 0
                    while time.time() - start < 5:
                        data_block = bytearray(block_size)
                        for i in range(0, block_size, 4096):
                            data_block[i] = 0xFF
                        blocks += 1
                    mem_score = blocks * block_size / (1024 * 1024)  # MB/s
                    results['memory_score'] = round(mem_score)

                    # Disk benchmark
                    _benchmark_state.update({'progress': 50, 'stage': 'Disk benchmark...'})
                    test_dir = os.path.join(os.environ.get('APPDATA', ''), 'ProjectNOMAD', 'benchmark')
                    os.makedirs(test_dir, exist_ok=True)
                    test_file = os.path.join(test_dir, 'bench.tmp')

                    # Write
                    chunk = os.urandom(1024 * 1024)
                    start = time.time()
                    written = 0
                    with open(test_file, 'wb') as f:
                        while time.time() - start < 5:
                            f.write(chunk)
                            written += len(chunk)
                    write_elapsed = time.time() - start
                    results['disk_write_score'] = round(written / write_elapsed / (1024 * 1024))

                    # Read
                    _benchmark_state.update({'progress': 65, 'stage': 'Disk read benchmark...'})
                    start = time.time()
                    read_bytes = 0
                    with open(test_file, 'rb') as f:
                        while True:
                            d = f.read(1024 * 1024)
                            if not d:
                                break
                            read_bytes += len(d)
                    read_elapsed = time.time() - start
                    results['disk_read_score'] = round(read_bytes / read_elapsed / (1024 * 1024)) if read_elapsed > 0 else 0

                    try:
                        os.remove(test_file)
                        os.rmdir(test_dir)
                    except Exception:
                        pass

                if mode in ('full', 'ai'):
                    _benchmark_state.update({'progress': 80, 'stage': 'AI benchmark...'})
                    results['ai_tps'] = 0
                    results['ai_ttft'] = 0

                    if ollama.is_installed() and ollama.running():
                        models = ollama.list_models()
                        if models:
                            test_model = models[0]['name']
                            try:
                                import requests
                                start = time.time()
                                resp = requests.post(
                                    f'http://localhost:{ollama.OLLAMA_PORT}/api/generate',
                                    json={'model': test_model, 'prompt': 'Write a paragraph about the history of computing.', 'stream': True},
                                    stream=True, timeout=120,
                                )
                                ttft = None
                                tokens = 0
                                for line in resp.iter_lines():
                                    if line:
                                        try:
                                            d = json.loads(line)
                                            if d.get('response') and ttft is None:
                                                ttft = time.time() - start
                                            if d.get('response'):
                                                tokens += 1
                                            if d.get('done'):
                                                break
                                        except Exception:
                                            pass
                                elapsed = time.time() - start
                                results['ai_tps'] = round(tokens / elapsed, 1) if elapsed > 0 else 0
                                results['ai_ttft'] = round(ttft * 1000) if ttft else 0
                            except Exception as e:
                                log.error(f'AI benchmark failed: {e}')

                # Calculate NOMAD Score (0-100, weighted)
                _benchmark_state.update({'progress': 95, 'stage': 'Calculating score...'})
                import math

                def norm(val, ref):
                    if val <= 0:
                        return 0
                    return min(100, math.log(val / ref + 1) / math.log(2) * 100)

                cpu_n = norm(results.get('cpu_score', 0), 500000)
                mem_n = norm(results.get('memory_score', 0), 500)
                dr_n = norm(results.get('disk_read_score', 0), 500)
                dw_n = norm(results.get('disk_write_score', 0), 300)
                ai_n = norm(results.get('ai_tps', 0), 10)
                ttft_n = max(0, 100 - results.get('ai_ttft', 5000) / 50) if results.get('ai_ttft', 0) > 0 else 0

                nomad_score = (
                    ai_n * 0.30 + cpu_n * 0.25 + mem_n * 0.15 +
                    ttft_n * 0.10 + dr_n * 0.10 + dw_n * 0.10
                )
                results['nomad_score'] = round(nomad_score, 1)

                # Save to DB
                db = get_db()
                db.execute('''INSERT INTO benchmarks
                    (cpu_score, memory_score, disk_read_score, disk_write_score, ai_tps, ai_ttft, nomad_score, hardware, details)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (results.get('cpu_score', 0), results.get('memory_score', 0),
                     results.get('disk_read_score', 0), results.get('disk_write_score', 0),
                     results.get('ai_tps', 0), results.get('ai_ttft', 0),
                     results.get('nomad_score', 0), json.dumps(hw), json.dumps(results)))
                db.commit()
                db.close()

                _benchmark_state = {'status': 'complete', 'progress': 100, 'stage': 'Done', 'results': results, 'hardware': hw}

            except Exception as e:
                log.error(f'Benchmark failed: {e}')
                _benchmark_state = {'status': 'error', 'progress': 0, 'stage': str(e), 'results': None}

        threading.Thread(target=do_benchmark, daemon=True).start()
        return jsonify({'status': 'started'})

    @app.route('/api/benchmark/status')
    def api_benchmark_status():
        return jsonify(_benchmark_state)

    @app.route('/api/benchmark/history')
    def api_benchmark_history():
        db = get_db()
        rows = db.execute('SELECT * FROM benchmarks ORDER BY created_at DESC LIMIT 20').fetchall()
        db.close()
        return jsonify([dict(r) for r in rows])

    # ─── Maps API ──────────────────────────────────────────────────────

    MAPS_DIR_NAME = 'maps'

    def get_maps_dir():
        path = os.path.join(os.environ.get('APPDATA', ''), 'ProjectNOMAD', MAPS_DIR_NAME)
        os.makedirs(path, exist_ok=True)
        return path

    MAP_REGIONS = [
        {'id': 'us-pacific', 'name': 'Pacific', 'states': 'AK, CA, HI, OR, WA'},
        {'id': 'us-mountain', 'name': 'Mountain', 'states': 'AZ, CO, ID, MT, NV, NM, UT, WY'},
        {'id': 'us-west-north-central', 'name': 'West North Central', 'states': 'IA, KS, MN, MO, NE, ND, SD'},
        {'id': 'us-east-north-central', 'name': 'East North Central', 'states': 'IL, IN, MI, OH, WI'},
        {'id': 'us-west-south-central', 'name': 'West South Central', 'states': 'AR, LA, OK, TX'},
        {'id': 'us-east-south-central', 'name': 'East South Central', 'states': 'AL, KY, MS, TN'},
        {'id': 'us-south-atlantic', 'name': 'South Atlantic', 'states': 'DE, FL, GA, MD, NC, SC, VA, DC, WV'},
        {'id': 'us-middle-atlantic', 'name': 'Middle Atlantic', 'states': 'NJ, NY, PA'},
        {'id': 'us-new-england', 'name': 'New England', 'states': 'CT, ME, MA, NH, RI, VT'},
    ]

    @app.route('/api/maps/regions')
    def api_maps_regions():
        maps_dir = get_maps_dir()
        result = []
        for r in MAP_REGIONS:
            pmtiles = os.path.join(maps_dir, f'{r["id"]}.pmtiles')
            result.append({
                **r,
                'downloaded': os.path.isfile(pmtiles),
                'size': format_size(os.path.getsize(pmtiles)) if os.path.isfile(pmtiles) else None,
            })
        return jsonify(result)

    @app.route('/api/maps/files')
    def api_maps_files():
        maps_dir = get_maps_dir()
        files = []
        for f in os.listdir(maps_dir):
            if f.endswith('.pmtiles'):
                fp = os.path.join(maps_dir, f)
                files.append({'filename': f, 'size': format_size(os.path.getsize(fp))})
        return jsonify(files)

    @app.route('/api/maps/delete', methods=['POST'])
    def api_maps_delete():
        data = request.get_json()
        filename = data.get('filename')
        if not filename or '..' in filename:
            return jsonify({'error': 'Invalid filename'}), 400
        path = os.path.join(get_maps_dir(), filename)
        try:
            if os.path.isfile(path):
                os.remove(path)
            return jsonify({'status': 'deleted'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/maps/tiles/<path:filepath>')
    def api_maps_serve_tile(filepath):
        """Serve local PMTiles files."""
        maps_dir = get_maps_dir()
        safe_path = os.path.normpath(os.path.join(maps_dir, filepath))
        if not safe_path.startswith(os.path.normpath(maps_dir)):
            return jsonify({'error': 'Forbidden'}), 403
        if not os.path.isfile(safe_path):
            return jsonify({'error': 'Not found'}), 404

        # Support range requests for PMTiles
        range_header = request.headers.get('Range')
        file_size = os.path.getsize(safe_path)

        if range_header:
            byte_range = range_header.replace('bytes=', '').split('-')
            start = int(byte_range[0])
            end = int(byte_range[1]) if byte_range[1] else file_size - 1
            length = end - start + 1

            with open(safe_path, 'rb') as f:
                f.seek(start)
                data = f.read(length)

            resp = Response(data, 206, mimetype='application/octet-stream')
            resp.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
            resp.headers['Accept-Ranges'] = 'bytes'
            resp.headers['Content-Length'] = length
            return resp

        return Response(open(safe_path, 'rb').read(), mimetype='application/octet-stream')

    # ─── Connectivity & Network ───────────────────────────────────────

    @app.route('/api/network')
    def api_network():
        import socket
        online = False
        try:
            socket.create_connection(('1.1.1.1', 443), timeout=3).close()
            online = True
        except Exception:
            pass

        lan_ip = '127.0.0.1'
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            lan_ip = s.getsockname()[0]
            s.close()
        except Exception:
            pass

        return jsonify({'online': online, 'lan_ip': lan_ip, 'dashboard_url': f'http://{lan_ip}:8080'})

    # ─── Health ────────────────────────────────────────────────────────

    @app.route('/api/health')
    def api_health():
        return jsonify({'status': 'ok', 'version': VERSION})

    # ─── Favicon ──────────────────────────────────────────────────────

    @app.route('/favicon.ico')
    def favicon():
        svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><polygon points="32,4 60,32 32,60 4,32" fill="#4f9cf7"/><polygon points="32,14 50,32 32,50 14,32" fill="#0d0d0d"/><polygon points="32,22 42,32 32,42 22,32" fill="#4f9cf7"/></svg>'
        return Response(svg, mimetype='image/svg+xml')

    return app
