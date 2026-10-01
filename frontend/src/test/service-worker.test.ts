import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * The service worker is a plain script in `public/`, so it cannot be imported
 * as a module. This loads the real source and runs it against a stub worker
 * global, then dispatches install/activate/fetch events at it — the same
 * events a browser would send.
 *
 * What this protects against is not hypothetical: the previous version was
 * cache-first for every request under a cache name that never changed and an
 * `activate` that deleted nothing. After any deploy it served a cached
 * index.html pointing at a bundle Vercel had already removed, so returning
 * visitors got a permanent blank page, and — because vercel.json rewrites
 * `/api/*` through this origin — health, carbon, models and impact stats were
 * all frozen at their first value.
 */

const ORIGIN = 'https://eco2query.vercel.app';

// Vitest serves modules from an http origin under jsdom, so `import.meta.url`
// is not a file URL here — resolve from the working directory instead.
const SW_PATH = ['public/sw.js', 'frontend/public/sw.js']
  .map((candidate) => resolve(process.cwd(), candidate))
  .find((candidate) => existsSync(candidate));

if (!SW_PATH) {
  throw new Error('could not locate public/sw.js from ' + process.cwd());
}

const SOURCE = readFileSync(SW_PATH, 'utf8');

function makeResponse(status: number, body: string): Response {
  const build = (): Response =>
    ({
      status,
      ok: status >= 200 && status < 300,
      body,
      text: async () => body,
      clone: build,
    }) as unknown as Response;
  return build();
}

interface Harness {
  listeners: Record<string, (event: any) => void>;
  /** Cache names the worker created, in order. */
  opened: string[];
  /** Cache names the worker deleted in activate. */
  deleted: string[];
  /** URLs the worker asked the network for. */
  networkCalls: string[];
  /** Replace the network behaviour partway through a test. */
  setNetwork: (fn: ((url: string) => Promise<Response>) | null) => void;
  skipWaitingCalls: () => number;
  claimed: () => boolean;
}

function loadServiceWorker(
  options: { cacheNames?: string[]; network?: ((url: string) => Promise<Response>) | null } = {},
): Harness {
  const cacheNames = options.cacheNames ?? [];
  const deleted: string[] = [];
  const opened: string[] = [];
  const networkCalls: string[] = [];
  const entries = new Map<string, Map<string, Response>>();
  const listeners: Record<string, (event: any) => void> = {};
  let network = options.network ?? null;
  let skipWaitingCalls = 0;
  let claimed = false;

  const keyOf = (input: any): string =>
    new URL(typeof input === 'string' ? input : input.url, ORIGIN).href;

  const caches = {
    open: async (name: string) => {
      opened.push(name);
      if (!entries.has(name)) entries.set(name, new Map());
      const bucket = entries.get(name) as Map<string, Response>;
      return {
        match: async (input: any) => bucket.get(keyOf(input)) ?? null,
        put: async (input: any, response: Response) => {
          bucket.set(keyOf(input), response);
        },
        addAll: async (urls: string[]) => {
          for (const url of urls) bucket.set(keyOf(url), makeResponse(200, url));
        },
      };
    },
    keys: async () => [...cacheNames],
    delete: async (name: string) => {
      deleted.push(name);
      entries.delete(name);
      return true;
    },
    match: async () => null,
  };

  const fetchStub = async (input: any) => {
    const url = keyOf(input);
    networkCalls.push(url);
    if (!network) throw new TypeError('Failed to fetch');
    return network(url);
  };

  const self: any = {
    location: { origin: ORIGIN },
    addEventListener: (type: string, fn: (event: any) => void) => {
      listeners[type] = fn;
    },
    skipWaiting: () => {
      skipWaitingCalls += 1;
    },
    clients: { claim: async () => { claimed = true; } },
  };

  // The source declares its own consts/functions, so it needs the worker
  // globals injected as parameters rather than imported.
  new Function('self', 'caches', 'fetch', 'URL', SOURCE)(self, caches, fetchStub, URL);

  return {
    listeners,
    opened,
    deleted,
    networkCalls,
    setNetwork: (fn) => { network = fn; },
    skipWaitingCalls: () => skipWaitingCalls,
    claimed: () => claimed,
  };
}

async function runLifecycle(harness: Harness, type: 'install' | 'activate'): Promise<void> {
  const waits: Promise<unknown>[] = [];
  harness.listeners[type]({ waitUntil: (p: Promise<unknown>) => waits.push(p) });
  await Promise.all(waits);
}

/** Dispatches a fetch and returns the promise the worker responded with, or
 *  null when the worker deliberately left the request alone. */
function dispatchFetch(harness: Harness, request: { url: string; method?: string }) {
  let handled: Promise<Response> | null = null;
  harness.listeners.fetch({
    request: { method: 'GET', ...request },
    respondWith: (p: Promise<Response>) => { handled = p; },
  });
  return handled;
}

const get = (path: string) => ({ url: `${ORIGIN}${path}` });

describe('service worker lifecycle', () => {
  it('takes over immediately instead of waiting for tabs to close', async () => {
    const harness = loadServiceWorker();
    await runLifecycle(harness, 'install');
    expect(harness.skipWaitingCalls()).toBe(1);
  });

  it('precache of the shell must never block the update', async () => {
    const harness = loadServiceWorker({ network: async () => makeResponse(200, 'shell') });
    // install precaches '/'; a resolved waitUntil proves it was attempted.
    await expect(runLifecycle(harness, 'install')).resolves.toBeUndefined();
  });

  it('deletes caches left behind by an older version', async () => {
    const harness = loadServiceWorker({
      cacheNames: ['ecoquery-v1', 'ecoquery-assets-v2', 'ecoquery-page-v2'],
    });

    await runLifecycle(harness, 'activate');

    // ecoquery-v1 is the name that made a stale shell permanent.
    expect(harness.deleted).toEqual(['ecoquery-v1']);
  });

  it('claims open clients so the fix reaches the tab that is already blank', async () => {
    const harness = loadServiceWorker({ cacheNames: ['ecoquery-v1'] });
    await runLifecycle(harness, 'activate');
    expect(harness.claimed()).toBe(true);
  });
});

describe('service worker requests left to the network', () => {
  it('never intercepts an API call', () => {
    const harness = loadServiceWorker();

    expect(dispatchFetch(harness, get('/api/health'))).toBeNull();
    expect(dispatchFetch(harness, get('/api/models'))).toBeNull();
    expect(dispatchFetch(harness, get('/api/carbon?zone=SE'))).toBeNull();
    expect(harness.networkCalls).toEqual([]);
  });

  it('never intercepts a POST', () => {
    const harness = loadServiceWorker();
    expect(dispatchFetch(harness, { ...get('/api/chat'), method: 'POST' })).toBeNull();
    expect(dispatchFetch(harness, { ...get('/'), method: 'POST' })).toBeNull();
  });

  it('never intercepts a cross-origin request', () => {
    const harness = loadServiceWorker();
    expect(dispatchFetch(harness, { url: 'https://ecoquery.onrender.com/api/health' })).toBeNull();
  });

  it('never intercepts the worker script itself', () => {
    const harness = loadServiceWorker();
    expect(dispatchFetch(harness, get('/sw.js'))).toBeNull();
  });
});

describe('service worker cached assets', () => {
  it('serves a hashed bundle from cache without hitting the network', async () => {
    const harness = loadServiceWorker({
      network: async () => makeResponse(200, 'network'),
    });
    const first = dispatchFetch(harness, get('/assets/index-AbCd.js'));
    await first;
    expect(harness.networkCalls).toHaveLength(1);

    // Network is now dead: the cached copy has to be what comes back.
    harness.setNetwork(null);
    const second = dispatchFetch(harness, get('/assets/index-AbCd.js'));
    await expect(second).resolves.toMatchObject({ body: 'network' });
    expect(harness.networkCalls).toHaveLength(1);
  });

  it('fetches a bundle it has never seen', async () => {
    const harness = loadServiceWorker({
      network: async () => makeResponse(200, 'fresh'),
    });

    const handled = dispatchFetch(harness, get('/assets/new-Chunk.js'));
    await expect(handled).resolves.toMatchObject({ body: 'fresh' });
    expect(harness.networkCalls).toEqual([`${ORIGIN}/assets/new-Chunk.js`]);
  });

  it('does not cache a failed bundle response', async () => {
    const harness = loadServiceWorker({
      network: async () => makeResponse(404, 'gone'),
    });

    const handled = dispatchFetch(harness, get('/assets/deleted-Build.js'));
    await expect(handled).resolves.toMatchObject({ status: 404 });

    // A 404 must not become the cached answer: once the network is back the
    // same request has to reach it again.
    harness.setNetwork(async () => makeResponse(200, 'restored'));
    await expect(dispatchFetch(harness, get('/assets/deleted-Build.js')))
      .resolves.toMatchObject({ body: 'restored' });
  });
});

describe('service worker page shell', () => {
  it('prefers the network over a cached shell so a deploy shows up', async () => {
    const harness = loadServiceWorker({
      network: async () => makeResponse(200, 'old build'),
    });
    await dispatchFetch(harness, get('/'));

    // The deploy happened: the network now has different HTML.
    harness.setNetwork(async () => makeResponse(200, 'new build'));

    await expect(dispatchFetch(harness, get('/'))).resolves.toMatchObject({ body: 'new build' });
  });

  it('serves a navigation from cache only when the network fails', async () => {
    const harness = loadServiceWorker({
      network: async () => makeResponse(200, 'shipped html'),
    });
    await dispatchFetch(harness, get('/pricing'));

    harness.setNetwork(null);
    const offline = dispatchFetch(harness, get('/pricing'));
    await expect(offline).resolves.toMatchObject({ body: 'shipped html' });
  });

  it('falls back to the cached shell for an uncached route when offline', async () => {
    const harness = loadServiceWorker({
      network: async () => makeResponse(200, 'the shell'),
    });
    await dispatchFetch(harness, get('/'));

    harness.setNetwork(null);
    const offline = dispatchFetch(harness, get('/blog/some-post'));
    await expect(offline).resolves.toMatchObject({ body: 'the shell' });
  });

  it('still reports the failure when nothing is cached', async () => {
    const harness = loadServiceWorker({ network: null });
    const handled = dispatchFetch(harness, get('/'));
    await expect(handled).rejects.toThrow('Failed to fetch');
  });

  it('does not cache an error page as the shell', async () => {
    const harness = loadServiceWorker({ network: async () => makeResponse(500, 'oops') });

    await expect(dispatchFetch(harness, get('/'))).resolves.toMatchObject({ status: 500 });

    harness.setNetwork(null);
    await expect(dispatchFetch(harness, get('/'))).rejects.toThrow('Failed to fetch');
  });
});
