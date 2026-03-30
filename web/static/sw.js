const CACHE_NAME = 'nomad-v2';
const SITROOM_CACHE = 'nomad-sitroom-v1';
const SITROOM_CACHE_TTL = 300000; // 5 minutes

const STATIC_ASSETS = [
  '/static/manifest.json',
  '/static/css/app.css',
  '/static/css/premium.css',
  '/static/css/app/45_situation_room.css',
  '/static/logo.png',
  '/static/maplibre-gl.js',
  '/static/maplibre-gl.css',
  '/static/pmtiles.js',
  '/static/js/epub.min.js'
];

// Cache static assets on install
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

// Clean up old caches on activate
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Situation Room API — dedicated cache with TTL for offline intelligence
  if (url.pathname.startsWith('/api/sitroom/')) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          const clone = response.clone();
          caches.open(SITROOM_CACHE).then(cache => {
            const headers = new Headers(clone.headers);
            headers.set('sw-cached-at', Date.now().toString());
            const cachedResponse = new Response(clone.body, {status: clone.status, statusText: clone.statusText, headers});
            cache.put(event.request, cachedResponse);
          });
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

  // Other API calls — network-first with general cache fallback
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Cache-first for static assets
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(event.request).then(cached => {
        return cached || fetch(event.request).then(response => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
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

  // Default: network with cache fallback
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});

// Handle push-alert messages from the main page for background notifications
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'push-alert') {
self.registration.showNotification(event.data.title || 'NOMAD Alert', {
      body: event.data.body || 'New alert received',
      icon: '/static/logo.png',
      badge: '/static/logo.png',
      tag: 'nomad-alert',
      renotify: true,
      requireInteraction: true,
    });
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
