/**
 * Browser half of bring-your-own-key (BYOK).
 *
 * The backend already accepts `X-Provider-Key` + `X-Provider` (and the
 * `X-OpenRouter-Key` shorthand) in `backend/providers.py`: the supplied key is
 * tried before the server's own keys, and it is never logged, stored or cached
 * server-side.
 *
 * This module only holds a key for the current tab and turns it into request
 * headers. The key lives in sessionStorage, so it dies with the tab; it is
 * never written to localStorage, never rendered back after being saved, and is
 * never sent anywhere except as a header on a chat request.
 */

export const BYOK_PROVIDERS = ['openrouter', 'google', 'grok'] as const;
export type ByokProvider = (typeof BYOK_PROVIDERS)[number];

/** Mirrors BYOK_MAX_KEY_LENGTH in backend/providers.py. The server treats an
 *  oversized key as absent, so it would fail silently — reject it here. */
export const BYOK_MAX_KEY_LENGTH = 512;

const PROVIDER_STORAGE = 'ecoquery.byok.provider';
const KEY_STORAGE = 'ecoquery.byok.key';

export interface ByokCredentials {
  provider: ByokProvider;
  key: string;
}

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

export function isByokProvider(value: string): value is ByokProvider {
  return (BYOK_PROVIDERS as readonly string[]).includes(value);
}

export function loadByok(): ByokCredentials | null {
  const key = read(KEY_STORAGE);
  if (!key) return null;
  const stored = read(PROVIDER_STORAGE);
  return { provider: isByokProvider(stored) ? stored : 'openrouter', key };
}

/** Returns false when the key is empty or too long to be honoured. */
export function saveByok(credentials: ByokCredentials): boolean {
  const key = credentials.key.trim();
  if (!key || key.length > BYOK_MAX_KEY_LENGTH) return false;
  write(KEY_STORAGE, key);
  write(PROVIDER_STORAGE, isByokProvider(credentials.provider) ? credentials.provider : 'openrouter');
  return true;
}

export function clearByok(): void {
  write(KEY_STORAGE, '');
  write(PROVIDER_STORAGE, '');
}

/**
 * Headers to add to a chat request. Empty when no key is saved, so callers can
 * spread it unconditionally.
 */
export function byokHeaders(): Record<string, string> {
  const credentials = loadByok();
  if (!credentials) return {};
  return {
    'X-Provider': credentials.provider,
    'X-Provider-Key': credentials.key,
  };
}
