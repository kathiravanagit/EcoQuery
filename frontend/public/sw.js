/*
 * Service worker for EcoQuery.
 *
 * Why the three rules below exist: the first version of this file was
 * cache-first for *every* request, under a cache name that never changed and
 * an `activate` handler that deleted nothing. `vercel.json` rewrites `/api/*`
 * through this origin, so that meant:
 *
 *   - after every deploy, a visitor who had loaded the site once was served a
 *     cached index.html pointing at a hashed bundle Vercel had already
 *     deleted. The 404 meant React never mounted and the page stayed blank
 *     permanently, until site data was cleared by hand;
 *   - every `/api` GET — health, carbon intensity, the model catalog, impact
 *     stats — was frozen at its first response.
 *
 * Vercel already sends the right headers (no-cache for HTML, immutable for
 * /assets/*), so this worker's job is only to not undo them.
 */

const VERSION = 'v2';
const ASSET_CACHE = `ecoquery-assets-${VERSION}`;
const PAGE_CACHE = `ecoquery-page-${VERSION}`;
const ALLOWED_CACHES = [ASSET_CACHE, PAGE_CACHE];

self.addEventListener('install', (event) => {
  // Take over as soon as the new version installs rather than waiting for
  // every tab to close — otherwise a bad deploy keeps running.
  self.skipWaiting();
  // Precaching the shell is best effort: a failed install must not block the
  // update that would fix it.
  event.waitUntil(
    caches
      .open(PAGE_CACHE)
      .then((cache) => cache.addAll(['/']))
      .catch(() => undefined),
  );
});

self.addEventListener('activate', (event) => {
  // Drop every cache this version does not own. Without this, bumping VERSION
  // never reaches existing visitors — which is exactly how the stale-shell
  // bug survived.
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.filter((key) => !ALLOWED_CACHES.includes(key)).map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

// Keyed by path and query, never by the raw request, so a navigation fragment
// cannot make cache.put reject.
const cacheKey = (request) => {
  const url = new URL(request.url);
  return url.pathname + url.search;
};

self.addEventListener('fetch', (event) => {
  const { request } = event;

  // POST bodies (chat, auth) are never cached — cache.put rejects them.
  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  // The Render backend is reached through vercel.json's /api rewrite; leave
  // any direct cross-origin call alone.
  if (url.origin !== self.location.origin) return;

  // Live data: always the network. Caching this is what froze health, carbon
  // intensity, the model catalog and impact stats at their first value.
  if (url.pathname.startsWith('/api/') || url.pathname === '/health') return;

  // Never mediate our own script: the browser fetches it outside this handler
  // when looking for an update, and serving it from a cache is exactly how a
  // fixed worker stays unfixed.
  if (url.pathname === '/sw.js') return;

  // Content-hashed bundles are immutable, so cache-first is safe here and is
  // the only thing this worker is really for.
  if (url.pathname.startsWith('/assets/')) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // The HTML shell and everything else: network-first, so a deploy shows up on
  // the next reload, with the cached shell used only as an offline fallback.
  event.respondWith(networkFirst(request));
});

async function cacheFirst(request) {
  const cache = await caches.open(ASSET_CACHE);
  const key = cacheKey(request);
  const cached = await cache.match(key);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) await cache.put(key, response.clone());
  return response;
}

async function networkFirst(request) {
  const cache = await caches.open(PAGE_CACHE);
  const key = cacheKey(request);
  try {
    const response = await fetch(request);
    if (response.ok) await cache.put(key, response.clone());
    return response;
  } catch (error) {
    const cached = await cache.match(key);
    if (cached) return cached;
    const shell = await cache.match('/');
    if (shell) return shell;
    throw error;
  }
}
