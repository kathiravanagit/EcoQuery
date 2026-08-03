const cache = new Map<string, { data: unknown; expiry: number }>();

export async function cachedFetch(
  url: string,
  options?: RequestInit,
  ttlMs: number = 60_000,
): Promise<unknown> {
  const key = `${options?.method || 'GET'}:${url}`;
  const now = Date.now();
  const cached = cache.get(key);
  if (cached && cached.expiry > now) return cached.data;

  const res = await fetch(url, options);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  cache.set(key, { data, expiry: now + ttlMs });
  return data;
}

export function invalidateCache(pattern?: string) {
  if (!pattern) { cache.clear(); return; }
  for (const key of cache.keys()) {
    if (key.includes(pattern)) cache.delete(key);
  }
}
