/**
 * Centralized API client for NOMAD Field Desk.
 * Replaces raw fetch() calls with consistent error handling.
 */

// CSRF token — fetched once on load, included in all mutating requests
let _csrfToken = null;

async function _fetchCsrfToken() {
    try {
        const ac = new AbortController();
        setTimeout(() => ac.abort(), 5000);
        const resp = await fetch('/api/csrf-token', { signal: ac.signal });
        if (resp.ok) {
            const data = await resp.json();
            _csrfToken = data.csrf_token;
        }
    } catch (e) {
        if (e.name !== 'AbortError') console.warn('[API] Could not fetch CSRF token:', e.message);
    }
}

// Fetch CSRF token on page load
_fetchCsrfToken();

async function apiFetch(url, options = {}) {
    const defaults = {
        headers: { 'Content-Type': 'application/json' },
    };

    // Merge headers
    const mergedOptions = {
        ...defaults,
        ...options,
        headers: { ...defaults.headers, ...(options.headers || {}) },
    };

    // Include CSRF token on mutating requests
    const method = (mergedOptions.method || 'GET').toUpperCase();
    if (_csrfToken && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
        mergedOptions.headers['X-CSRF-Token'] = _csrfToken;
    }

    // Don't set Content-Type for FormData
    if (options.body instanceof FormData) {
        delete mergedOptions.headers['Content-Type'];
    }

    // Default 30s timeout unless caller provides their own signal
    let controller;
    if (!mergedOptions.signal) {
        controller = new AbortController();
        setTimeout(() => controller.abort(), 30000);
        mergedOptions.signal = controller.signal;
    }

    try {
        const resp = await fetch(url, mergedOptions);

        if (!resp.ok) {
            let errorData;
            try {
                errorData = await resp.json();
            } catch {
                errorData = { error: resp.statusText };
            }
            const err = new Error(errorData.error || `HTTP ${resp.status}`);
            err.status = resp.status;
            err.data = errorData;
            throw err;
        }

        // Handle streaming responses
        const contentType = resp.headers.get('content-type') || '';
        if (contentType.includes('text/event-stream') ||
            contentType.includes('text/html') ||
            contentType.includes('application/octet-stream')) {
            return resp;
        }

        return await resp.json();
    } catch (err) {
        if (err.status) throw err; // Re-throw API errors
        // Network error
        console.error('[API]', url, err.message);
        throw err;
    }
}

function apiPost(url, data) {
    return apiFetch(url, { method: 'POST', body: JSON.stringify(data) });
}

function apiPut(url, data) {
    return apiFetch(url, { method: 'PUT', body: JSON.stringify(data) });
}

function apiDelete(url) {
    return apiFetch(url, { method: 'DELETE' });
}

function apiUpload(url, formData) {
    return apiFetch(url, { method: 'POST', body: formData });
}

// Attach to window for backward compatibility
window.apiFetch = apiFetch;
window.apiPost = apiPost;
window.apiPut = apiPut;
window.apiDelete = apiDelete;
window.apiUpload = apiUpload;
