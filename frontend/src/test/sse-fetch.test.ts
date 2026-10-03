import { fetchStream, newIdempotencyKey } from '../sse';

const URL_PATH = '/api/chat/stream';
const KEY = 'idem-frontend-key-1';

function streamResponse(): Response {
  return new Response('data: {"token":"x"}\n\n', {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  });
}

function headersOf(call: unknown[]): Record<string, string> {
  return (call[1] as RequestInit).headers as Record<string, string>;
}

describe('newIdempotencyKey', () => {
  it('is different every time', () => {
    const keys = new Set(Array.from({ length: 100 }, () => newIdempotencyKey()));
    expect(keys.size).toBe(100);
  });

  it('meets the server acceptance rule', () => {
    // Mirrors `idempotency.normalise_key` in the backend: 8..128 characters
    // drawn from A-Za-z0-9-_. A key outside that set is not rejected — it is
    // silently treated as no key at all, which would switch deduplication off
    // with nothing on screen to say so.
    for (let i = 0; i < 200; i += 1) {
      const key = newIdempotencyKey();
      expect(key.length).toBeGreaterThanOrEqual(8);
      expect(key.length).toBeLessThanOrEqual(128);
      expect(key).toMatch(/^[A-Za-z0-9_-]+$/);
    }
  });

  it('still works where randomUUID is unavailable', () => {
    // Insecure origins have no crypto.randomUUID; a keyless fallback is what
    // keeps the header present there rather than crashing the send.
    vi.stubGlobal('crypto', {});
    try {
      expect(newIdempotencyKey()).toMatch(/^[0-9a-f]{32}$/);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});

describe('fetchStream', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('tags the request with the key and posts JSON', async () => {
    fetchMock.mockResolvedValue(streamResponse());

    await fetchStream(URL_PATH, { body: { message: 'hi' } }, KEY);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe('POST');
    expect(headersOf(fetchMock.mock.calls[0])['Idempotency-Key']).toBe(KEY);
    expect(headersOf(fetchMock.mock.calls[0])['Content-Type']).toBe('application/json');
    expect(JSON.parse(init.body)).toEqual({ message: 'hi' });
  });

  it('keeps the caller headers alongside the key', async () => {
    fetchMock.mockResolvedValue(streamResponse());

    await fetchStream(URL_PATH, {
      body: {},
      headers: { Authorization: 'Bearer token-123' },
    }, KEY);

    const headers = headersOf(fetchMock.mock.calls[0]);
    expect(headers.Authorization).toBe('Bearer token-123');
    expect(headers['Idempotency-Key']).toBe(KEY);
  });

  it('retries once on a network failure, reusing the same key', async () => {
    fetchMock
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(streamResponse());

    const response = await fetchStream(URL_PATH, { body: {} }, KEY);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(response.status).toBe(200);
    // Reusing the key across attempts is the whole feature: without it the
    // second attempt would be paid for twice.
    expect(fetchMock.mock.calls.map((call) => headersOf(call)['Idempotency-Key']))
      .toEqual([KEY, KEY]);
  });

  it('gives up after the single retry instead of looping', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));

    await expect(fetchStream(URL_PATH, { body: {} }, KEY)).rejects.toThrow();

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('does not retry once the caller has aborted', async () => {
    const controller = new AbortController();
    fetchMock.mockImplementation(() => {
      controller.abort();
      return Promise.reject(new DOMException('Aborted', 'AbortError'));
    });

    await expect(
      fetchStream(URL_PATH, { body: {}, signal: controller.signal }, KEY),
    ).rejects.toThrow();

    // Cancelling must never be answered with a fresh request.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('does not retry a response, even a server error', async () => {
    // A 500 means the server was reached and replied. Re-sending is guessing,
    // and on a failing provider it doubles a call that already ran.
    fetchMock.mockResolvedValue(new Response('{"detail":"boom"}', { status: 500 }));

    const response = await fetchStream(URL_PATH, { body: {} }, KEY);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(response.status).toBe(500);
  });

  it('does not retry a response with an empty body', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 500 }));

    await fetchStream(URL_PATH, { body: {} }, KEY);

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
