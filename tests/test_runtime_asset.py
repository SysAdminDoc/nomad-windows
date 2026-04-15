def test_workspace_page_uses_shared_runtime_script(client):
    response = client.get('/preparedness')

    assert response.status_code == 200

    html = response.get_data(as_text=True)
    assert '<script src="/app-runtime.js?v=' in html
    assert 'window.NOMAD_VERSION =' in html
    assert "const VERSION = '" not in html
    assert len(response.get_data()) < 1_000_000


def test_shared_runtime_script_renders_javascript(client):
    response = client.get('/app-runtime.js?v=test')

    assert response.status_code == 200
    assert response.mimetype == 'application/javascript'
    assert 'public, max-age=86400' in response.headers.get('Cache-Control', '')
    assert response.headers.get('X-Content-Type-Options') == 'nosniff'

    body = response.get_data(as_text=True)
    assert '{{ version }}' not in body
    assert "const VERSION = window.NOMAD_VERSION || '0.0.0';" in body
    assert 'function inferButtonAriaLabel(button, text)' in body
    assert "if (!button.hasAttribute('type')) button.type = 'button';" in body
    assert "return 'Delete item';" in body
    assert 'function observeShellAccessibilityDefaults()' in body
    assert "observer.observe(document.body, { childList: true, subtree: true });" in body
