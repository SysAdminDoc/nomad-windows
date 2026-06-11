"""Download hardening regressions for managed service installers."""

import hashlib

import pytest

from services import manager


class _FakeResponse:
    def __init__(self, body: bytes | str, *, status_code: int = 200, headers: dict | None = None):
        self.status_code = status_code
        self._body = body.encode('utf-8') if isinstance(body, str) else body
        self.headers = headers or {'content-length': str(len(self._body))}
        self.text = self._body.decode('utf-8', errors='replace')
        self.content = self._body
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')

    def iter_content(self, chunk_size=65536):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    def close(self):
        self.closed = True


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_download_file_verifies_expected_sha256(monkeypatch, tmp_path):
    payload = b'verified service payload'
    calls = []
    response = _FakeResponse(payload)

    def _get(url, **kwargs):
        calls.append((url, kwargs))
        return response

    monkeypatch.setattr(manager.requests, 'get', _get)

    dest = tmp_path / 'payload.zip'
    result = manager.download_file(
        'https://example.test/payload.zip',
        str(dest),
        'checksum-success',
        expected_sha256=_sha256(payload),
    )

    assert result == str(dest)
    assert dest.read_bytes() == payload
    assert calls[0][1]['headers'] == {}
    assert response.closed is True
    assert manager.get_download_progress('checksum-success')['status'] == 'complete'


def test_download_file_rejects_and_removes_bad_sha256(monkeypatch, tmp_path):
    payload = b'tampered service payload'

    monkeypatch.setattr(
        manager.requests,
        'get',
        lambda *_args, **_kwargs: _FakeResponse(payload),
    )

    dest = tmp_path / 'payload.zip'
    with pytest.raises(ValueError, match='SHA256 checksum mismatch'):
        manager.download_file(
            'https://example.test/payload.zip',
            str(dest),
            'checksum-failure',
            expected_sha256=_sha256(b'expected payload'),
        )

    assert not dest.exists()
    progress = manager.get_download_progress('checksum-failure')
    assert progress['status'] == 'error'
    assert 'SHA256 checksum mismatch' in progress['error']


def test_download_file_restarts_partial_when_checksum_expected(monkeypatch, tmp_path):
    full_payload = b'complete signed payload'
    headers_seen = []

    def _get(url, **kwargs):
        headers_seen.append(dict(kwargs.get('headers') or {}))
        return _FakeResponse(full_payload)

    monkeypatch.setattr(manager.requests, 'get', _get)

    dest = tmp_path / 'payload.zip'
    dest.write_bytes(b'partial')

    manager.download_file(
        'https://example.test/payload.zip',
        str(dest),
        'checksum-restart',
        expected_sha256=_sha256(full_payload),
    )

    assert headers_seen == [{}]
    assert dest.read_bytes() == full_payload


def test_download_file_keeps_resume_for_unsigned_downloads(monkeypatch, tmp_path):
    headers_seen = []

    def _get(url, **kwargs):
        headers_seen.append(dict(kwargs.get('headers') or {}))
        return _FakeResponse(b'suffix', status_code=206, headers={'content-length': '6'})

    monkeypatch.setattr(manager.requests, 'get', _get)

    dest = tmp_path / 'payload.zip'
    dest.write_bytes(b'prefix-')

    manager.download_file(
        'https://example.test/payload.zip',
        str(dest),
        'unsigned-resume',
    )

    assert headers_seen == [{'Range': 'bytes=7-'}]
    assert dest.read_bytes() == b'prefix-suffix'


def test_parse_sha256_checksum_text_matches_common_manifest_formats():
    digest = _sha256(b'payload')

    assert manager.parse_sha256_checksum_text(f'{digest} *payload.zip', 'payload.zip') == digest
    assert manager.parse_sha256_checksum_text(
        f'SHA256 (payload.zip) = {digest}',
        'payload.zip',
    ) == digest
    assert manager.parse_sha256_checksum_text(
        digest,
        'payload.zip',
        allow_single_hash=True,
    ) == digest


def test_resolve_release_asset_checksum_uses_github_digest_field():
    digest = _sha256(b'payload')
    assets = [
        {'name': 'payload.zip', 'digest': f'sha256:{digest}', 'browser_download_url': 'https://example.test/payload.zip'},
    ]

    assert manager.resolve_release_asset_checksum(assets, 'payload.zip') == digest


def test_resolve_release_asset_checksum_reads_checksum_manifest():
    digest = _sha256(b'payload')
    assets = [
        {'name': 'payload.zip', 'browser_download_url': 'https://example.test/payload.zip'},
        {'name': 'SHA256SUMS.txt', 'browser_download_url': 'https://example.test/SHA256SUMS.txt'},
    ]
    calls = []

    def _get(url, **kwargs):
        calls.append((url, kwargs))
        return _FakeResponse(f'{digest}  payload.zip\n')

    assert manager.resolve_release_asset_checksum(
        assets,
        'payload.zip',
        request_get=_get,
    ) == digest
    assert calls[0][0].endswith('SHA256SUMS.txt')
    assert calls[0][1]['headers'] == manager.GITHUB_API_HEADERS


def test_resolve_release_asset_checksum_rejects_bad_exact_sidecar():
    assets = [
        {'name': 'payload.zip', 'browser_download_url': 'https://example.test/payload.zip'},
        {'name': 'payload.zip.sha256', 'browser_download_url': 'https://example.test/payload.zip.sha256'},
    ]

    with pytest.raises(ValueError, match='did not contain a SHA256'):
        manager.resolve_release_asset_checksum(
            assets,
            'payload.zip',
            request_get=lambda *_args, **_kwargs: _FakeResponse('not a checksum'),
        )


def test_resolve_url_sidecar_checksum_reads_asset_sidecar():
    digest = _sha256(b'payload')
    calls = []

    def _get(url, **kwargs):
        calls.append((url, kwargs))
        return _FakeResponse(f'{digest}  payload.zip\n')

    assert manager.resolve_url_sidecar_checksum(
        'https://example.test/payload.zip',
        request_get=_get,
    ) == digest
    assert calls[0][0] == 'https://example.test/payload.zip.sha256'
