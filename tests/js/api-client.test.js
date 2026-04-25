import { describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { Script, createContext } from 'node:vm';

const API_SOURCE = readFileSync(join(process.cwd(), 'web/static/js/api.js'), 'utf8');

function jsonResponse(body, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status >= 200 && status < 300 ? 'OK' : 'Failed',
    headers: {
      get(name) {
        if (String(name).toLowerCase() === 'content-type') return 'application/json';
        return '';
      },
    },
    json: async () => body,
    text: async () => JSON.stringify(body),
  };
}

function loadApi(fetchImpl, extras = {}) {
  const context = {
    AbortController,
    FormData: class FormData {},
    clearTimeout,
    console: { error: vi.fn(), warn: vi.fn() },
    fetch: fetchImpl,
    setTimeout,
    ...extras,
  };
  context.window = context;
  createContext(context);
  new Script(API_SOURCE).runInContext(context);
  return context;
}

describe('api client reliability', () => {
  it('normalizes network-level fetch failures', async () => {
    const fetchImpl = vi.fn(async (url) => {
      if (url === '/api/csrf-token') return jsonResponse({ csrf_token: 'csrf-token' });
      throw new TypeError('Failed to fetch');
    });
    const api = loadApi(fetchImpl);

    await expect(api.apiFetch('/api/offline/snapshot')).rejects.toMatchObject({
      status: 0,
      network: true,
    });
  });

  it('routes apiJson failures through the managed toast recovery copy', async () => {
    const toastError = vi.fn();
    const fetchImpl = vi.fn(async (url) => {
      if (url === '/api/csrf-token') return jsonResponse({ csrf_token: 'csrf-token' });
      throw new TypeError('Failed to fetch');
    });
    const api = loadApi(fetchImpl, { toastError });

    await expect(api.apiJson('/api/hardware/sensors', {}, 'Load sensors')).rejects.toMatchObject({
      status: 0,
      network: true,
    });

    expect(toastError).toHaveBeenCalledTimes(1);
    const [action, error, options] = toastError.mock.calls[0];
    expect(action).toBe('Load sensors');
    expect(error.status).toBe(0);
    expect(options.recovery).toContain('NOMAD is still running locally');
  });

  it('keeps CSRF protection on mutating shared helper calls', async () => {
    const fetchImpl = vi.fn(async (url) => {
      if (url === '/api/csrf-token') return jsonResponse({ csrf_token: 'csrf-token' });
      return jsonResponse({ ok: true });
    });
    const api = loadApi(fetchImpl);

    await expect(api.apiPost('/api/tasks', { title: 'Water check' })).resolves.toEqual({ ok: true });

    expect(fetchImpl).toHaveBeenLastCalledWith('/api/tasks', expect.objectContaining({
      method: 'POST',
      headers: expect.objectContaining({
        'Content-Type': 'application/json',
        'X-CSRF-Token': 'csrf-token',
      }),
    }));
  });
});
