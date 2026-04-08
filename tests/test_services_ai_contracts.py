"""Static regressions for the shared Services/AI runtime script."""

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_services_ai_uses_guarded_json_helpers_for_key_requests():
    js = (REPO_ROOT / 'web' / 'templates' / 'index_partials' / 'js' / '_app_services_ai.js').read_text(encoding='utf-8')

    assert 'async function fetchJsonStrict' in js
    assert 'async function fetchJsonSafe' in js
    assert "await fetchJsonStrict('/api/services'" in js
    assert "await fetchJsonSafe('/api/ai/pull-progress'" in js
    assert "await fetchJsonStrict('/api/ai/models'" in js
    assert "await fetchJsonSafe('/api/kiwix/zim-downloads'" in js


def test_ollama_list_models_returns_empty_list_on_bad_json(monkeypatch):
    from services import ollama

    class _BadJsonResponse:
        ok = True
        status_code = 200

        def json(self):
            raise ValueError('bad json payload')

    monkeypatch.setattr(ollama.requests, 'get', lambda *args, **kwargs: _BadJsonResponse())

    assert ollama.list_models() == []


def test_ollama_list_models_returns_empty_list_when_models_payload_is_invalid(monkeypatch):
    from services import ollama

    class _OddJsonResponse:
        ok = True
        status_code = 200

        def json(self):
            return {'models': 'not-a-list'}

    monkeypatch.setattr(ollama.requests, 'get', lambda *args, **kwargs: _OddJsonResponse())

    assert ollama.list_models() == []


def test_ollama_pull_model_returns_error_on_unreadable_stream(monkeypatch):
    from services import ollama

    class _UnreadableStreamResponse:
        ok = True
        status_code = 200

        def raise_for_status(self):
            return None

        def iter_lines(self):
            yield b'{broken'
            yield b''

    monkeypatch.setattr(ollama.requests, 'post', lambda *args, **kwargs: _UnreadableStreamResponse())

    assert ollama.pull_model('demo:model') is False
    progress = ollama.get_pull_progress()
    assert progress['status'] == 'error'
    assert 'unreadable pull progress' in progress['detail'].lower()


def test_ollama_pull_model_ignores_bad_chunks_when_success_arrives(monkeypatch):
    from services import ollama

    class _MixedStreamResponse:
        ok = True
        status_code = 200

        def raise_for_status(self):
            return None

        def iter_lines(self):
            yield b'{broken'
            yield json.dumps({'status': 'pulling manifest'}).encode('utf-8')
            yield json.dumps({'status': 'success'}).encode('utf-8')

    monkeypatch.setattr(ollama.requests, 'post', lambda *args, **kwargs: _MixedStreamResponse())

    assert ollama.pull_model('demo:model') is True
    progress = ollama.get_pull_progress()
    assert progress['status'] == 'complete'
    assert progress['percent'] == 100


def test_ollama_chat_returns_empty_dict_on_bad_json_when_not_streaming(monkeypatch):
    from services import ollama

    class _BadJsonResponse:
        ok = True
        status_code = 200

        def raise_for_status(self):
            return None

        def close(self):
            return None

        def json(self):
            raise ValueError('bad chat payload')

    monkeypatch.setattr(ollama.requests, 'post', lambda *args, **kwargs: _BadJsonResponse())

    assert ollama.chat('demo:model', [{'role': 'user', 'content': 'hello'}], stream=False) == {}
