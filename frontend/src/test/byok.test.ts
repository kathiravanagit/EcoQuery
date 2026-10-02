import {
  BYOK_MAX_KEY_LENGTH,
  byokHeaders,
  clearByok,
  isByokProvider,
  loadByok,
  saveByok,
} from '../byok';

const SECRET = 'sk-or-v1-DO-NOT-LEAK-8f3a';

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
});

describe('byokHeaders', () => {
  it('sends nothing when no key is saved, so callers stay on server keys', () => {
    expect(byokHeaders()).toEqual({});
  });

  it('sends the provider and the key once one is saved', () => {
    expect(saveByok({ provider: 'google', key: SECRET })).toBe(true);
    expect(byokHeaders()).toEqual({
      'X-Provider': 'google',
      'X-Provider-Key': SECRET,
    });
  });

  it('clears back to no headers', () => {
    saveByok({ provider: 'grok', key: SECRET });
    clearByok();
    expect(byokHeaders()).toEqual({});
    expect(loadByok()).toBeNull();
  });
});

describe('saveByok', () => {
  it('rejects an empty or whitespace-only key', () => {
    expect(saveByok({ provider: 'openrouter', key: '   ' })).toBe(false);
    expect(byokHeaders()).toEqual({});
  });

  it('rejects a key longer than the server will accept', () => {
    // providers.py treats an oversized key as absent, so accepting it here
    // would show "saved" while every request silently used the server's keys.
    const tooLong = 'x'.repeat(BYOK_MAX_KEY_LENGTH + 1);
    expect(saveByok({ provider: 'openrouter', key: tooLong })).toBe(false);
    expect(byokHeaders()).toEqual({});
  });

  it('accepts a key at exactly the limit', () => {
    const exact = 'x'.repeat(BYOK_MAX_KEY_LENGTH);
    expect(saveByok({ provider: 'openrouter', key: exact })).toBe(true);
    expect(byokHeaders()['X-Provider-Key']).toBe(exact);
  });

  it('trims surrounding whitespace before storing', () => {
    saveByok({ provider: 'openrouter', key: `  ${SECRET}  ` });
    expect(byokHeaders()['X-Provider-Key']).toBe(SECRET);
  });

  it('falls back to openrouter for a provider the app does not know', () => {
    // The backend only honours ids in PROVIDER_BASE_URLS; anything else is
    // silently re-routed to openrouter, so the UI should say the same thing.
    expect(isByokProvider('azure')).toBe(false);
    expect(saveByok({ provider: 'azure' as never, key: SECRET })).toBe(true);
    expect(byokHeaders()['X-Provider']).toBe('openrouter');
  });
});

describe('storage guarantee', () => {
  it('never writes the key to localStorage', () => {
    saveByok({ provider: 'openrouter', key: SECRET });

    expect(localStorage.getItem('ecoquery.byok.key')).toBeNull();

    // Walk every stored entry rather than asserting the store is empty —
    // jsdom reports its own internal properties through Object.keys.
    const stored: string[] = [];
    for (let i = 0; i < localStorage.length; i += 1) {
      const name = localStorage.key(i);
      if (name) stored.push(`${name}=${localStorage.getItem(name)}`);
    }
    expect(stored.join('&')).not.toContain(SECRET);
  });

  it('keeps the key out of the provider slot', () => {
    saveByok({ provider: 'grok', key: SECRET });
    expect(sessionStorage.getItem('ecoquery.byok.provider')).toBe('grok');
    expect(sessionStorage.getItem('ecoquery.byok.provider')).not.toContain(SECRET);
  });

  it('recovers from a corrupted provider value instead of dropping the key', () => {
    sessionStorage.setItem('ecoquery.byok.key', SECRET);
    sessionStorage.setItem('ecoquery.byok.provider', 'not-a-provider');
    expect(loadByok()).toEqual({ provider: 'openrouter', key: SECRET });
  });
});
