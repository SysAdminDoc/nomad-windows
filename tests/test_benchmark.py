"""Tests for benchmark API routes."""

import web.blueprints.benchmark as benchmark_module


class TestBenchmarkStatus:
    def test_benchmark_status(self, client):
        resp = client.get('/api/benchmark/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'status' in data


class TestBenchmarkHistory:
    def test_benchmark_history(self, client):
        resp = client.get('/api/benchmark/history')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)


class TestBenchmarkResults:
    def test_results_empty(self, client):
        resp = client.get('/api/benchmark/results')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_results_with_type_filter(self, client):
        resp = client.get('/api/benchmark/results?type=storage')
        assert resp.status_code == 200

    def test_results_with_limit(self, client):
        resp = client.get('/api/benchmark/results?limit=5')
        assert resp.status_code == 200


class TestStorageBenchmark:
    def test_storage_benchmark(self, client):
        resp = client.post('/api/benchmark/storage')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'read_mbps' in data
        assert 'write_mbps' in data
        assert data['read_mbps'] > 0


class TestBenchmarkRunResilience:
    def test_ai_benchmark_ignores_malformed_stream_lines(self, client, monkeypatch):
        class _ImmediateThread:
            def __init__(self, target=None, daemon=None):
                self._target = target

            def start(self):
                if self._target:
                    self._target()

        class _FakeResponse:
            def raise_for_status(self):
                return None

            def iter_lines(self):
                return iter([b'{broken', b'{"response":"hello"}', b'{"done":true}'])

        monkeypatch.setattr(benchmark_module.threading, 'Thread', _ImmediateThread)
        monkeypatch.setattr(benchmark_module.ollama, 'is_installed', lambda: True)
        monkeypatch.setattr(benchmark_module.ollama, 'running', lambda: True)
        monkeypatch.setattr(benchmark_module.ollama, 'list_models', lambda: [{'name': 'test-model'}])
        monkeypatch.setattr('requests.post', lambda *args, **kwargs: _FakeResponse())

        resp = client.post('/api/benchmark/run', json={'mode': 'ai'})

        assert resp.status_code == 200
        status = client.get('/api/benchmark/status')
        assert status.status_code == 200
        data = status.get_json()
        assert data['status'] == 'complete'
        assert data['results']['ai_tps'] >= 0
