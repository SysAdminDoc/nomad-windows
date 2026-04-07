"""Benchmark routes — CPU, memory, disk, AI inference, storage, network."""

import json
import logging
import math
import os
import platform
import socket
import threading
import time

from flask import Blueprint, request, jsonify

from config import get_data_dir
from db import db_session, log_activity
from services import ollama

log = logging.getLogger('nomad.web')

benchmark_bp = Blueprint('benchmark', __name__)

# Benchmark state — protected by lock for thread safety
_benchmark_state = {'status': 'idle', 'progress': 0, 'stage': '', 'results': None}
_benchmark_lock = threading.Lock()
_benchmark_net_lock = threading.Lock()


@benchmark_bp.route('/api/benchmark/run', methods=['POST'])
def api_benchmark_run():
    data = request.get_json() or {}
    mode = data.get('mode', 'full')  # full, system, ai

    def do_benchmark():
        import psutil
        global _benchmark_state
        with _benchmark_lock:
            _benchmark_state = {'status': 'running', 'progress': 0, 'stage': 'Starting...', 'results': None}
        results = {}
        hw = {}

        try:
            # Hardware detection
            hw['cpu'] = platform.processor() or f'{os.cpu_count()} cores'
            hw['cpu_cores'] = psutil.cpu_count()
            hw['ram_gb'] = round(psutil.virtual_memory().total / (1024**3), 1)

            from platform_utils import detect_gpu as _bench_gpu
            _bg = _bench_gpu()
            hw['gpu'] = _bg.get('name', 'None')

            if mode in ('full', 'system'):
                # CPU benchmark — prime calculation
                with _benchmark_lock: _benchmark_state.update({'progress': 10, 'stage': 'CPU benchmark...'})
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
                with _benchmark_lock: _benchmark_state.update({'progress': 30, 'stage': 'Memory benchmark...'})
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
                with _benchmark_lock: _benchmark_state.update({'progress': 50, 'stage': 'Disk benchmark...'})
                test_dir = os.path.join(get_data_dir(), 'benchmark')
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
                results['disk_write_score'] = round(written / write_elapsed / (1024 * 1024)) if write_elapsed > 0 else 0

                # Read
                with _benchmark_lock: _benchmark_state.update({'progress': 65, 'stage': 'Disk read benchmark...'})
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
                with _benchmark_lock: _benchmark_state.update({'progress': 80, 'stage': 'AI benchmark...'})
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
            with _benchmark_lock: _benchmark_state.update({'progress': 95, 'stage': 'Calculating score...'})

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
            with db_session() as db:
                db.execute('''INSERT INTO benchmarks
                    (cpu_score, memory_score, disk_read_score, disk_write_score, ai_tps, ai_ttft, nomad_score, hardware, details)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (results.get('cpu_score', 0), results.get('memory_score', 0),
                     results.get('disk_read_score', 0), results.get('disk_write_score', 0),
                     results.get('ai_tps', 0), results.get('ai_ttft', 0),
                     results.get('nomad_score', 0), json.dumps(hw), json.dumps(results)))
                db.commit()

            with _benchmark_lock:
                _benchmark_state = {'status': 'complete', 'progress': 100, 'stage': 'Done', 'results': results, 'hardware': hw}

        except Exception as e:
            log.error(f'Benchmark failed: {e}')
            with _benchmark_lock:
                _benchmark_state = {'status': 'error', 'progress': 0, 'stage': 'Benchmark failed', 'results': None}

    threading.Thread(target=do_benchmark, daemon=True).start()
    return jsonify({'status': 'started'})


@benchmark_bp.route('/api/benchmark/status')
def api_benchmark_status():
    with _benchmark_lock:
        state = dict(_benchmark_state)
    return jsonify(state)


@benchmark_bp.route('/api/benchmark/history')
def api_benchmark_history():
    with db_session() as db:
        rows = db.execute('SELECT * FROM benchmarks ORDER BY created_at DESC LIMIT 20').fetchall()
    return jsonify([dict(r) for r in rows])


# ─── Benchmark Enhancements (v5.0 Phase 12) ─────────────────────

@benchmark_bp.route('/api/benchmark/ai-inference', methods=['POST'])
def api_benchmark_ai_inference():
    """Benchmark AI inference speed (tokens/second) for installed models."""
    model = (request.json or {}).get('model', '')
    if not model:
        return jsonify({'error': 'model required'}), 400
    try:
        import time as _time
        prompt = 'Write a short paragraph about weather forecasting in exactly 100 words.'
        start = _time.time()
        resp = ollama.chat(model, [{'role': 'user', 'content': prompt}])
        elapsed = _time.time() - start
        text = resp.get('message', {}).get('content', '') if isinstance(resp, dict) else str(resp)
        tokens = len(text.split())  # approximate
        tps = round(tokens / elapsed, 1) if elapsed > 0 else 0
        ttft = round(elapsed, 2)

        with db_session() as db:
            db.execute(
                'INSERT INTO benchmark_results (test_type, scores, details) VALUES (?, ?, ?)',
                ('ai_inference', json.dumps({'tps': tps, 'ttft': ttft, 'model': model}),
                 json.dumps({'tokens': tokens, 'elapsed': elapsed, 'text_length': len(text)}))
            )
            db.execute('DELETE FROM benchmark_results WHERE id NOT IN (SELECT id FROM benchmark_results ORDER BY created_at DESC LIMIT 100)')
            db.commit()

        return jsonify({'model': model, 'tokens_per_sec': tps, 'time_to_complete': ttft, 'tokens': tokens})
    except Exception as e:
        log.error('Request failed: %s', e)
        return jsonify({'error': 'Internal server error'}), 500


@benchmark_bp.route('/api/benchmark/storage', methods=['POST'])
def api_benchmark_storage():
    """Benchmark storage I/O speed."""
    import tempfile
    import time as _time

    test_dir = os.path.join(get_data_dir(), 'benchmark_tmp')
    os.makedirs(test_dir, exist_ok=True)
    test_file = os.path.join(test_dir, 'io_test.bin')

    try:
        # Write test (32MB)
        data = os.urandom(32 * 1024 * 1024)
        start = _time.perf_counter()
        with open(test_file, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        write_time = max(_time.perf_counter() - start, 1e-9)
        write_mbps = round(32 / write_time, 1) if write_time > 0 else 0

        # Read test
        start = _time.perf_counter()
        with open(test_file, 'rb') as f:
            _ = f.read()
        read_time = max(_time.perf_counter() - start, 1e-9)
        read_mbps = round(32 / read_time, 1) if read_time > 0 else 0

        os.remove(test_file)

        with db_session() as db:
            db.execute(
                'INSERT INTO benchmark_results (test_type, scores) VALUES (?, ?)',
                ('storage', json.dumps({'read_mbps': read_mbps, 'write_mbps': write_mbps}))
            )
            db.execute('DELETE FROM benchmark_results WHERE id NOT IN (SELECT id FROM benchmark_results ORDER BY created_at DESC LIMIT 100)')
            db.commit()

        return jsonify({'read_mbps': read_mbps, 'write_mbps': write_mbps})
    except Exception as e:
        log.error('Request failed: %s', e)
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        try:
            os.rmdir(test_dir)
        except Exception:
            pass


@benchmark_bp.route('/api/benchmark/results')
def api_benchmark_results_history():
    """Get benchmark results history for charting."""
    test_type = request.args.get('type', '')
    limit = min(request.args.get('limit', 20, type=int), 500)
    with db_session() as db:
        if test_type:
            rows = db.execute('SELECT * FROM benchmark_results WHERE test_type = ? ORDER BY created_at DESC LIMIT ?', (test_type, limit)).fetchall()
        else:
            rows = db.execute('SELECT * FROM benchmark_results ORDER BY created_at DESC LIMIT ?', (limit,)).fetchall()
        return jsonify([dict(r) for r in rows])


@benchmark_bp.route('/api/benchmark/network', methods=['POST'])
def api_benchmark_network():
    """Benchmark local network throughput."""
    import time as _time
    if not _benchmark_net_lock.acquire(blocking=False):
        return jsonify({'error': 'Benchmark already running'}), 409
    server_sock = None
    conn = None
    try:
        peer = (request.json or {}).get('peer', '127.0.0.1')
        import ipaddress
        try:
            addr = ipaddress.ip_address(peer)
            if addr.is_loopback or addr.is_multicast:
                return jsonify({'error': 'Invalid peer address'}), 400
        except ValueError:
            return jsonify({'error': 'Invalid IP address'}), 400
        chunk = b'X' * (1024 * 1024)  # 1MB chunks
        total_mb = 10

        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(('127.0.0.1', 0))
        port = server_sock.getsockname()[1]
        server_sock.listen(1)
        server_sock.settimeout(5)

        def send_data():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    s.connect((peer, port))
                    for _ in range(total_mb):
                        s.sendall(chunk)
                finally:
                    s.close()
            except Exception:
                pass

        t = threading.Thread(target=send_data, daemon=True)
        t.start()

        conn, _ = server_sock.accept()
        start = _time.time()
        received = 0
        while received < total_mb * 1024 * 1024:
            data = conn.recv(65536)
            if not data:
                break
            received += len(data)
        elapsed = _time.time() - start
        t.join(timeout=2)

        mbps = round((received / 1024 / 1024) / elapsed * 8, 1) if elapsed > 0 else 0

        with db_session() as db:
            db.execute('INSERT INTO benchmark_results (test_type, scores) VALUES (?, ?)',
                       ('network', json.dumps({'throughput_mbps': mbps, 'peer': peer, 'data_mb': total_mb})))
            db.execute('DELETE FROM benchmark_results WHERE id NOT IN (SELECT id FROM benchmark_results ORDER BY created_at DESC LIMIT 100)')
            db.commit()

        return jsonify({'throughput_mbps': mbps, 'data_mb': round(received/1024/1024, 1), 'elapsed_sec': round(elapsed, 2)})
    except Exception as e:
        log.error('Request failed: %s', e)
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        if server_sock:
            try:
                server_sock.close()
            except Exception:
                pass
        _benchmark_net_lock.release()
