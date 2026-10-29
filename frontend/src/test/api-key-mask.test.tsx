import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import ApiKeyManager, { maskKey } from '../components/ApiKeyManager';

/**
 * The key used to sit in full on the dashboard forever — visible in a screen
 * share, a screenshot or over a shoulder. It is now masked on load, shown in
 * full only right after it is generated, and masked again once copied.
 */

const FULL_KEY = 'eq_0123456789abcdef0123456789abcdef0123456789abcdef';

function stubFetch(key: string) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (String(url).endsWith('/api/user/api-key/stats')) {
      return { ok: true, json: async () => ({ queries: 0, co2_saved_g: 0, cost: 0 }) } as Response;
    }
    if (init?.method === 'POST') {
      return { ok: true, json: async () => ({ api_key: FULL_KEY }) } as Response;
    }
    return { ok: true, json: async () => ({ api_key: key }) } as Response;
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('maskKey', () => {
  it('keeps enough prefix to tell keys apart and hides the secret', () => {
    const masked = maskKey(FULL_KEY);

    expect(masked.startsWith('eq_0123456')).toBe(true);
    expect(masked).not.toContain('abcdef0123456789');
    expect(masked.replace(/\*/g, '')).toHaveLength(10);
  });

  it('masks short and empty values completely', () => {
    expect(maskKey('')).toBe('');
    expect(maskKey('eq_abc')).toBe('******');
  });
});

describe('ApiKeyManager', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('hides an existing key on load but still copies the real one', async () => {
    const writeText = vi.fn(async () => {});
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    stubFetch(FULL_KEY);

    render(<ApiKeyManager token="t" API="http://api" />);

    expect(await screen.findByText(maskKey(FULL_KEY))).toBeInTheDocument();
    expect(screen.queryByText(FULL_KEY)).not.toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('Copy API key'));

    await waitFor(() => expect(writeText).toHaveBeenCalledWith(FULL_KEY));
  });

  it('shows the whole key right after generating, and masks it again after copying', async () => {
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn(async () => {}) },
      configurable: true,
    });
    stubFetch('');

    render(<ApiKeyManager token="t" API="http://api" />);

    fireEvent.click(await screen.findByLabelText('Generate API key'));

    expect(await screen.findByText(FULL_KEY)).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('Copy API key'));

    expect(await screen.findByText(maskKey(FULL_KEY))).toBeInTheDocument();
    expect(screen.queryByText(FULL_KEY)).not.toBeInTheDocument();
  });

  it('never prints the full key in the curl hint', async () => {
    stubFetch(FULL_KEY);

    render(<ApiKeyManager token="t" API="http://api" />);

    await screen.findByText(maskKey(FULL_KEY));
    expect(screen.getByText(/Authorization: Bearer/).textContent).not.toContain(FULL_KEY);
  });
});
