const CACHE_NAME = 'nomad-v4';
const SITROOM_CACHE = 'nomad-sitroom-v2';
const SITROOM_CACHE_TTL = 300000; // 5 minutes

const STATIC_ASSETS = [
  '/',
  // Manifest & top-level assets
  '/static/manifest.json',
  '/static/logo.png',
  '/static/nomad-mark.svg',
  // App CSS
  '/static/css/app.css',
  '/static/css/app/00_theme_tokens.css',
  '/static/css/app/10_shell_layout.css',
  '/static/css/app/20_primary_workspaces.css',
  '/static/css/app/30_secondary_workspaces.css',
  '/static/css/app/40_preparedness_media.css',
  '/static/css/app/45_situation_room.css',
  '/static/css/app/50_home_customize.css',
  '/static/css/app/60_accessibility_platform.css',
  '/static/css/app/70_cleanup_utilities.css',
  // Premium CSS
  '/static/css/premium.css',
  '/static/css/premium/00_base.css',
  '/static/css/premium/10_refresh.css',
  '/static/css/premium/20_workspaces.css',
  '/static/css/premium/30_preparedness_ops.css',
  '/static/css/premium/40_customize_maps.css',
  '/static/css/premium/50_settings.css',
  '/static/css/premium/60_benchmark_tools.css',
  '/static/css/premium/70_layout_hardening.css',
  '/static/css/premium/80_dark_theme_overrides.css',
  '/static/css/premium/90_theme_consistency.css',
  // Vendor libraries
  '/static/maplibre-gl.js',
  '/static/maplibre-gl.css',
  '/static/pmtiles.js',
  // App JS
  '/static/js/api.js',
  '/static/js/battery.js',
  '/static/js/chart.js',
  '/static/js/epub.min.js',
  '/static/js/events.js',
  '/static/js/i18n.js',
  '/static/js/offline.js',
  '/static/js/toast.js',
];

// Cache static assets on install
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS)).then(() => self.skipWaiting())
  );
});

// Clean up old caches on activate + evict stale sitroom entries + prune main cache
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME && k !== SITROOM_CACHE).map(k => caches.delete(k)))
    ).then(() => _evictStaleSitroomCache()).then(() => _pruneCacheIfNeeded()).then(() => self.clients.claim())
  );
});

// Prune main cache if it grows too large (max 100 static assets + API responses)
async function _pruneCacheIfNeeded() {
  try {
    const cache = await caches.open(CACHE_NAME);
    const keys = await cache.keys();
    const MAX_CACHE_ENTRIES = 150; // 100 statics + 50 API responses
    if (keys.length > MAX_CACHE_ENTRIES) {
      const excess = keys.slice(0, keys.length - MAX_CACHE_ENTRIES);
      for (const req of excess) await cache.delete(req);
    }
  } catch(e) { /* Cache pruning is best-effort */ }
}

// Evict sitroom cache entries older than TTL and cap total entries
async function _evictStaleSitroomCache() {
  try {
    const cache = await caches.open(SITROOM_CACHE);
    let keys = await cache.keys();
    const MAX_ENTRIES = 200;
    const now = Date.now();

    // First pass: delete expired entries by TTL
    const entriesToDelete = [];
    for (const req of keys) {
      const resp = await cache.match(req);
      if (!resp) {
        entriesToDelete.push(req);
        continue;
      }
      const cachedAt = parseInt(resp.headers.get('sw-cached-at') || '0');
      if (cachedAt && (now - cachedAt > SITROOM_CACHE_TTL)) {
        entriesToDelete.push(req);
      }
    }

    // Delete TTL-expired entries
    for (const req of entriesToDelete) await cache.delete(req);

    // Second pass: if still over limit, delete oldest entries (FIFO)
    keys = await cache.keys();
    if (keys.length > MAX_ENTRIES) {
      const excess = keys.slice(0, keys.length - MAX_ENTRIES);
      for (const req of excess) await cache.delete(req);
    }
  } catch(e) { /* SW cache eviction is best-effort */ }
}

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Periodically evict stale caches (every ~100 requests for sitroom, ~200 for main)
  if (Math.random() < 0.01) {
    if (url.pathname.startsWith('/api/sitroom/')) {
      _evictStaleSitroomCache();
    } else if (url.pathname.startsWith('/api/') && Math.random() < 0.5) {
      _pruneCacheIfNeeded();
    }
  }

  // Situation Room API — dedicated cache with TTL for offline intelligence
  if (url.pathname.startsWith('/api/sitroom/')) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(SITROOM_CACHE).then(cache => {
              const headers = new Headers(clone.headers);
              headers.set('sw-cached-at', Date.now().toString());
              const cachedResponse = new Response(clone.body, {status: clone.status, statusText: clone.statusText, headers});
              cache.put(event.request, cachedResponse);
            });
          }
          return response;
        })
        .catch(() => {
          return caches.open(SITROOM_CACHE).then(cache =>
            cache.match(event.request).then(cached => {
              if (cached) return cached;
              return new Response(JSON.stringify({error: 'Offline', cached: false}),
                {status: 503, headers: {'Content-Type': 'application/json'}});
            })
          );
        })
    );
    return;
  }

  // Other API calls — network-first with general cache fallback (GET only)
  // Only cache read-heavy endpoints, not all GETs (prevents unbounded cache growth)
  if (url.pathname.startsWith('/api/')) {
    if (event.request.method === 'GET') {
      const cacheable = /^\/(api\/(services|system|content-summary|settings|offline\/snapshot))/.test(url.pathname);
      event.respondWith(
        fetch(event.request)
          .then(response => {
            if (response.ok && cacheable) {
              const clone = response.clone();
              caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
            }
            return response;
          })
          .catch(() => caches.match(event.request))
      );
    }
    return;
  }

  // Cache-first for static assets
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(event.request).then(cached => {
        return cached || fetch(event.request).then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          }
          return response;
        });
      })
    );
    return;
  }

  // Offline fallback for index page
  if (url.pathname === '/' || url.pathname === '/index.html') {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          return response;
        })
        .catch(() => caches.match('/'))
    );
    return;
  }

  // Default: network with cache fallback (GET only — let mutations pass through)
  if (event.request.method !== 'GET') return;
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});

// Handle push-alert messages from the main page for background notifications
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'push-alert') {
    try {
      self.registration.showNotification(event.data.title || 'NOMAD Alert', {
        body: event.data.body || 'New alert received',
        icon: '/static/logo.png',
        badge: '/static/logo.png',
        tag: 'nomad-alert',
        renotify: true,
        requireInteraction: true,
      });
    } catch (e) {
      // Notification permission may have been revoked
    }
  }
});

// Handle notification click — focus the app window
self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({type: 'window', includeUncontrolled: true}).then(clients => {
      if (clients.length > 0) {
        return clients[0].focus();
      }
      return self.clients.openWindow('/');
    })
  );
});
