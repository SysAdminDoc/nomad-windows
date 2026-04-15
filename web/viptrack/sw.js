const CACHE_NAME = 'viptrack-v4.15';
const TILE_CACHE_NAME = `${CACHE_NAME}-tiles`;
const STATIC_ASSETS = [
  '/viptrack/lib/leaflet.css',
  '/viptrack/lib/leaflet.js',
  '/viptrack/lib/pako.min.js',
  '/viptrack/manifest.webmanifest',
  '/nukemap/data/offline_atlas.json',
  'https://raw.githubusercontent.com/SysAdminDoc/SkyTrack/refs/heads/main/assets/silhouettes/aircraft.png',
  'https://raw.githubusercontent.com/SysAdminDoc/SkyTrack/refs/heads/main/assets/logo/SkyTrack_Logo.ico',
  'https://raw.githubusercontent.com/SysAdminDoc/SkyTrack/refs/heads/main/assets/logo/SkyTrack_Logo-16x16.png',
  'https://raw.githubusercontent.com/SysAdminDoc/SkyTrack/refs/heads/main/assets/logo/SkyTrack_Logo-32x32.png',
  'https://raw.githubusercontent.com/SysAdminDoc/SkyTrack/refs/heads/main/assets/logo/SkyTrack_Logo-48x48.png',
  'https://raw.githubusercontent.com/SysAdminDoc/SkyTrack/refs/heads/main/assets/logo/SkyTrack_Logo-128x128.png'
];

function isLiveDataRequest(url) {
  return url.hostname.includes('airplanes.live') ||
    url.hostname.includes('opensky') ||
    url.hostname.includes('adsbexchange') ||
    url.hostname.includes('rainviewer') ||
    url.hostname.includes('planespotters') ||
    url.hostname.includes('wikipedia.org') ||
    url.pathname.includes('/traces/');
}

function isGithubDataRequest(url) {
  return url.hostname.includes('githubusercontent.com') &&
    (url.pathname.includes('/data/') || url.pathname.includes('/assets/'));
}

function isStaticAssetRequest(url, requestUrl) {
  return STATIC_ASSETS.some((asset) => requestUrl.includes(asset)) ||
    url.hostname.includes('cdnjs.cloudflare.com') ||
    (url.hostname.includes('githubusercontent.com') && url.pathname.includes('/logo/'));
}

function isTileRequest(url) {
  return url.hostname.includes('tile') ||
    url.hostname.includes('mt0.google') ||
    url.hostname.includes('mt1.google') ||
    url.hostname.includes('mt2.google') ||
    url.hostname.includes('mt3.google') ||
    url.pathname.includes('/{z}/{x}/{y}');
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME && key !== TILE_CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  if (isLiveDataRequest(url)) {
    event.respondWith(
      fetch(event.request).then((response) => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      }).catch(() => caches.match(event.request))
    );
    return;
  }

  if (isGithubDataRequest(url)) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        const fetchPromise = fetch(event.request).then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        }).catch(() => cached);
        return cached || fetchPromise;
      })
    );
    return;
  }

  if (isStaticAssetRequest(url, event.request.url)) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        if (cached) return cached;
        return fetch(event.request).then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        });
      })
    );
    return;
  }

  if (isTileRequest(url)) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        const fetchPromise = fetch(event.request).then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(TILE_CACHE_NAME).then((cache) => {
              cache.put(event.request, clone);
              setTimeout(() => {
                cache.keys().then((keys) => {
                  if (keys.length > 600) {
                    keys.slice(0, keys.length - 500).forEach((key) => cache.delete(key));
                  }
                });
              }, 5000);
            });
          }
          return response;
        }).catch(() => cached);
        return cached || fetchPromise;
      })
    );
    return;
  }

  event.respondWith(
    fetch(event.request).then((response) => {
      if (response.ok && event.request.method === 'GET') {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
      }
      return response;
    }).catch(() => caches.match(event.request))
  );
});
