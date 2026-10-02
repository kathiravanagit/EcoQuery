/**
 * Browser half of bring-your-own-key (BYOK).
 *
 * The backend accepts one header per provider — `X-OpenRouter-Key`,
 * `X-Google-Key`, `X-Grok-Key` — plus the original `X-Provider-Key` +
 * `X-Provider` form, in `backend/providers.py`. Every supplied key is tried
 * before that provider's own server keys, and none is ever logged, stored or
 * cached server-side.
 *
 * This module holds the keys for the current tab and turns them into request
 * headers. Keys live in sessionStorage, so they die with the tab; they are
 * never written to localStorage, never rendered back after being saved, and are
 * never sent anywhere except as headers on a chat request.
 */

export const BYOK_PROVIDERS = ['openrouter', 'google', 'grok'] as const;
export type ByokProvider = (typeof BYOK_PROVIDERS)[number];

export type ByokKeys = Partial<Record<ByokProvider, string>>;

/** Header name per provider — the browser half of `BYOK_HEADERS` in
 *  backend/providers.py. Grok here is xAI; there is no Groq. */
export const PROVIDER_HEADERS: Record<ByokProvider, string> = {
  openrouter: 'X-OpenRouter-Key',
  google: 'X-Google-Key',
  grok: 'X-Grok-Key',
};

export const PROVIDER_LABELS: Record<ByokProvider, string> = {
  openrouter: 'OpenRouter',
  google: 'Google AI Studio',
  grok: 'Grok (xAI)',
};

/** Suggested first characters, so a wrong key in the wrong row is visible. */
export const PROVIDER_KEY_HINTS: Record<ByokProvider, string> = {
  openrouter: 'sk-or-v1-...',
  google: 'AIza...',
  grok: 'xai-...',
};

/** Mirrors BYOK_MAX_KEY_LENGTH in backend/providers.py. The server treats an
 *  oversized key as absent, so it would fail silently — reject it here. */
export const BYOK_MAX_KEY_LENGTH = 512;

const KEY_PREFIX = 'ecoquery.byok.key.';
const PREFER_STORAGE = 'ecoquery.byok.prefer';

/** Single-key storage from the first BYOK revision. Read as a fallback so a
 *  key saved minutes ago survives this change, then dropped on the next write
 *  or clear. */
const LEGACY_KEY_STORAGE = 'ecoquery.byok.key';
const LEGACY_PROVIDER_STORAGE = 'ecoquery.byok.provider';

/** sessionStorage throws in some privacy modes; treat that as "no storage". */
function store(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.sessionStorage;
  } catch {
    return null;
  }
}

function read(name: string): string {
  const s = store();
  if (!s) return '';
  try {
    return s.getItem(name) ?? '';
  } catch {
    return '';
  }
}

function write(name: string, value: string): void {
  const s = store();
  if (!s) return;
  try {
    if (value) s.setItem(name, value);
    else s.removeItem(name);
  } catch {
    // Denied storage just means BYOK headers are not sent; the request still
    // succeeds on the server's own keys.
  }
}

function remove(name: string): void {
  write(name, '');
}

export function isByokProvider(value: string): value is ByokProvider {
  return (BYOK_PROVIDERS as readonly string[]).includes(value);
}

/** Every key saved for this tab, keyed by provider. Never logged, never
 *  returned to a caller that renders it — the UI only asks for the count. */
export function loadByokKeys(): ByokKeys {
  const keys: ByokKeys = {};

  const legacy = read(LEGACY_KEY_STORAGE);
  if (legacy && legacy.length <= BYOK_MAX_KEY_LENGTH) {
    const stored = read(LEGACY_PROVIDER_STORAGE);
    keys[isByokProvider(stored) ? stored : 'openrouter'] = legacy;
  }

  for (const provider of BYOK_PROVIDERS) {
    const key = read(KEY_PREFIX + provider);
    if (key && key.length <= BYOK_MAX_KEY_LENGTH) keys[provider] = key;
    else if (key) remove(KEY_PREFIX + provider);
  }

  return keys;
}

export function byokCount(): number {
  return Object.keys(loadByokKeys()).length;
}

/** Returns false when the key is empty or too long to be honoured. */
export function saveByokKey(provider: ByokProvider, key: string): boolean {
  const trimmed = key.trim();
  if (!trimmed || trimmed.length > BYOK_MAX_KEY_LENGTH) return false;
  if (!isByokProvider(provider)) return false;
  write(KEY_PREFIX + provider, trimmed);
  // Writing the new format makes the single-key entry redundant.
  remove(LEGACY_KEY_STORAGE);
  remove(LEGACY_PROVIDER_STORAGE);
  return true;
}

export function clearByokKey(provider: ByokProvider): void {
  remove(KEY_PREFIX + provider);
  remove(LEGACY_KEY_STORAGE);
  remove(LEGACY_PROVIDER_STORAGE);
}

export function clearByok(): void {
  for (const provider of BYOK_PROVIDERS) remove(KEY_PREFIX + provider);
  remove(LEGACY_KEY_STORAGE);
  remove(LEGACY_PROVIDER_STORAGE);
}

/**
 * "Prefer my keys when available", on by default. Turning it off stops the
 * headers being attached, which is the only place the preference could take
 * effect — the server always tries a supplied key first.
 */
export function preferMyKeys(): boolean {
  const stored = read(PREFER_STORAGE);
  return stored !== '0';
}

export function setPreferMyKeys(on: boolean): void {
  write(PREFER_STORAGE, on ? '' : '0');
}

/**
 * Headers to add to a chat request: one per saved key, or empty when there are
 * none or the user has opted out, so callers can spread it unconditionally.
 */
export function byokHeaders(): Record<string, string> {
  if (!preferMyKeys()) return {};
  const keys = loadByokKeys();
  const headers: Record<string, string> = {};
  for (const provider of BYOK_PROVIDERS) {
    const key = keys[provider];
    if (key) headers[PROVIDER_HEADERS[provider]] = key;
  }
  return headers;
}
