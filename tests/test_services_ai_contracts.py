"""Static regressions for the shared Services/AI runtime script."""

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
