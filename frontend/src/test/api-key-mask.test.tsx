import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import ApiKeyManager, { maskKey } from '../components/ApiKeyManager';

/**
 * A stored key is only ever returned masked: the sole response carrying the
 * whole key is the POST that creates it. Otherwise it sat on the dashboard
 * forever, readable from a screen share, a screenshot or a shoulder.
 */

const FULL_KEY = 'eq_0123456789abcdef0123456789abcdef0123456789abcdef';
const MASKED_KEY = maskKey(FULL_KEY);

function stubFetch(existingKey: string) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (String(url).endsWith('/api/user/api-key/stats')) {
      return { ok: true, json: async () => ({ queries: 0, co2_saved_g: 0, cost: 0 }) } as Response;
    }
    if (init?.method === 'POST') {
      return { ok: true, json: async () => ({ api_key: FULL_KEY }) } as Response;
    }
    return { ok: true, json: async () => ({ api_key: existingKey }) } as Response;
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('maskKey', () => {
  it('keeps enough prefix to tell keys apart and hides the secret', () => {
    expect(MASKED_KEY.startsWith('eq_0123456')).toBe(true);
    expect(MASKED_KEY).not.toContain('abcdef0123456789');
    expect(MASKED_KEY.replace(/\*/g, '')).toHaveLength(10);
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

  it('cannot copy or reveal a stored key, because it only has the masked one', async () => {
    stubFetch(MASKED_KEY);

    render(<ApiKeyManager token="t" API="http://api" />);

    expect(await screen.findByText(MASKED_KEY)).toBeInTheDocument();
    expect(screen.queryByLabelText('Copy API key')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Show API key')).not.toBeInTheDocument();
    expect(screen.getByText(/only shown when it is created/)).toBeInTheDocument();
  });

  it('shows the whole key right after generating, and masks it again after copying', async () => {
    const writeText = vi.fn(async () => {});
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    stubFetch('');

    render(<ApiKeyManager token="t" API="http://api" />);

    fireEvent.click(await screen.findByLabelText('Generate API key'));

    expect(await screen.findByText(FULL_KEY)).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('Copy API key'));

    await waitFor(() => expect(writeText).toHaveBeenCalledWith(FULL_KEY));
    expect(await screen.findByText(MASKED_KEY)).toBeInTheDocument();
    expect(screen.queryByText(FULL_KEY)).not.toBeInTheDocument();
  });

  it('never prints the full key in the curl hint', async () => {
    stubFetch(MASKED_KEY);

    render(<ApiKeyManager token="t" API="http://api" />);

    await screen.findByText(MASKED_KEY);
    expect(screen.getByText(/Authorization: Bearer/).textContent).not.toContain(FULL_KEY);
  });
});
