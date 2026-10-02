import {
  BYOK_MAX_KEY_LENGTH,
  PROVIDER_HEADERS,
  byokCount,
  byokHeaders,
  clearByok,
  clearByokKey,
  isByokProvider,
  loadByokKeys,
  preferMyKeys,
  saveByokKey,
  setPreferMyKeys,
} from '../byok';

const SECRET = 'sk-or-v1-DO-NOT-LEAK-8f3a';
const GOOGLE_SECRET = 'AIza-DO-NOT-LEAK-91b2';
const GROK_SECRET = 'xai-DO-NOT-LEAK-c3d4';

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
  setPreferMyKeys(true);
});

describe('byokHeaders', () => {
  it('sends nothing when no key is saved, so callers stay on server keys', () => {
    expect(byokHeaders()).toEqual({});
  });

  it('uses one header name per provider', () => {
    expect(PROVIDER_HEADERS).toEqual({
      openrouter: 'X-OpenRouter-Key',
      google: 'X-Google-Key',
      grok: 'X-Grok-Key',
    });

    saveByokKey('google', GOOGLE_SECRET);
    expect(byokHeaders()).toEqual({ 'X-Google-Key': GOOGLE_SECRET });
  });

  it('attaches every saved key on the same request', () => {
    saveByokKey('openrouter', SECRET);
    saveByokKey('google', GOOGLE_SECRET);
    saveByokKey('grok', GROK_SECRET);

    expect(byokHeaders()).toEqual({
      'X-OpenRouter-Key': SECRET,
      'X-Google-Key': GOOGLE_SECRET,
      'X-Grok-Key': GROK_SECRET,
    });
  });

  it('clears back to no headers', () => {
    saveByokKey('grok', SECRET);
    clearByok();
    expect(byokHeaders()).toEqual({});
    expect(loadByokKeys()).toEqual({});
  });

  it('drops a single provider without touching the others', () => {
    saveByokKey('openrouter', SECRET);
    saveByokKey('google', GOOGLE_SECRET);

    clearByokKey('openrouter');

    expect(byokHeaders()).toEqual({ 'X-Google-Key': GOOGLE_SECRET });
    expect(byokCount()).toBe(1);
  });

  it('sends no headers when "prefer my keys" is off', () => {
    saveByokKey('openrouter', SECRET);
    setPreferMyKeys(false);

    expect(preferMyKeys()).toBe(false);
    expect(byokHeaders()).toEqual({});

    // The key is still saved — opting out only stops it being attached.
    expect(byokCount()).toBe(1);
    setPreferMyKeys(true);
    expect(byokHeaders()).toEqual({ 'X-OpenRouter-Key': SECRET });
  });
});

describe('saveByokKey', () => {
  it('rejects an empty or whitespace-only key', () => {
    expect(saveByokKey('openrouter', '   ')).toBe(false);
    expect(byokHeaders()).toEqual({});
  });

  it('rejects a key longer than the server will accept', () => {
    // providers.py treats an oversized key as absent, so accepting it here
    // would show "saved" while every request silently used the server's keys.
    const tooLong = 'x'.repeat(BYOK_MAX_KEY_LENGTH + 1);
    expect(saveByokKey('openrouter', tooLong)).toBe(false);
    expect(byokHeaders()).toEqual({});
  });

  it('accepts a key at exactly the limit', () => {
    const exact = 'x'.repeat(BYOK_MAX_KEY_LENGTH);
    expect(saveByokKey('openrouter', exact)).toBe(true);
    expect(byokHeaders()['X-OpenRouter-Key']).toBe(exact);
  });

  it('trims surrounding whitespace before storing', () => {
    saveByokKey('openrouter', `  ${SECRET}  `);
    expect(byokHeaders()['X-OpenRouter-Key']).toBe(SECRET);
  });

  it('refuses a provider the backend has no endpoint for', () => {
    // There is no OpenAI/Groq/Anthropic provider to route to; silently
    // re-routing such a key would send it to the wrong company's API.
    expect(isByokProvider('azure')).toBe(false);
    expect(saveByokKey('azure' as never, SECRET)).toBe(false);
    expect(byokHeaders()).toEqual({});
  });
});

describe('the original single-key format', () => {
  it('still produces a header so an existing key is not silently lost', () => {
    sessionStorage.setItem('ecoquery.byok.key', SECRET);
    sessionStorage.setItem('ecoquery.byok.provider', 'google');

    expect(byokHeaders()).toEqual({ 'X-Google-Key': SECRET });
  });

  it('is dropped once a new key is saved', () => {
    sessionStorage.setItem('ecoquery.byok.key', SECRET);
    sessionStorage.setItem('ecoquery.byok.provider', 'google');

    saveByokKey('grok', GROK_SECRET);

    expect(sessionStorage.getItem('ecoquery.byok.key')).toBeNull();
    expect(byokHeaders()).toEqual({ 'X-Grok-Key': GROK_SECRET });
  });

  it('recovers from a corrupted provider value instead of dropping the key', () => {
    sessionStorage.setItem('ecoquery.byok.key', SECRET);
    sessionStorage.setItem('ecoquery.byok.provider', 'not-a-provider');

    expect(byokHeaders()['X-OpenRouter-Key']).toBe(SECRET);
  });
});

describe('storage guarantee', () => {
  it('never writes a key to localStorage', () => {
    saveByokKey('openrouter', SECRET);
    saveByokKey('google', GOOGLE_SECRET);

    // Walk every stored entry rather than asserting the store is empty —
    // jsdom reports its own internal properties through Object.keys.
    const stored: string[] = [];
    for (let i = 0; i < localStorage.length; i += 1) {
      const name = localStorage.key(i);
      if (name) stored.push(`${name}=${localStorage.getItem(name)}`);
    }
    expect(stored.join('&')).not.toContain(SECRET);
    expect(stored.join('&')).not.toContain(GOOGLE_SECRET);
  });

  it('keeps each key under its own provider slot and nowhere else', () => {
    saveByokKey('grok', GROK_SECRET);

    const entries: string[] = [];
    for (let i = 0; i < sessionStorage.length; i += 1) {
      const name = sessionStorage.key(i);
      if (name) entries.push(`${name}=${sessionStorage.getItem(name)}`);
    }

    // The secret may only appear in its own slot — never in a provider-name
    // slot, a preference slot, or any other entry.
    expect(entries).toContain(`ecoquery.byok.key.grok=${GROK_SECRET}`);
    expect(entries.filter((e) => e.includes(GROK_SECRET))).toHaveLength(1);
    expect(entries.filter((e) => e.includes(SECRET))).toHaveLength(0);
  });

  it('drops an oversized value rather than sending a key the server ignores', () => {
    sessionStorage.setItem('ecoquery.byok.key.openrouter', 'x'.repeat(BYOK_MAX_KEY_LENGTH + 1));

    expect(loadByokKeys()).toEqual({});
    expect(byokHeaders()).toEqual({});
    expect(sessionStorage.getItem('ecoquery.byok.key.openrouter')).toBeNull();
  });
});
