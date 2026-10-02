import { ApiFailure, apiFailure, describeApiError, errorCodeMessage } from '../apiError';

/**
 * `Response` is not implemented in every test environment, and the contract
 * under test only touches `status`, `headers.get` and `text()`.
 */
function makeResponse(
  status: number,
  body: string,
  headers: Record<string, string> = {},
): Response {
  const lower: Record<string, string> = {};
  for (const [name, value] of Object.entries(headers)) {
    lower[name.toLowerCase()] = value;
  }
  return {
    status,
    headers: { get: (name: string) => lower[name.toLowerCase()] ?? null },
    text: async () => body,
  } as unknown as Response;
}

describe('apiFailure', () => {
  it('keeps the server-written sentence and the structured fields', async () => {
    const failure = await apiFailure(makeResponse(404, JSON.stringify({
      detail: 'That certificate no longer exists.',
      error_code: 'NOT_FOUND',
      success: false,
    })));

    expect(failure.message).toBe('That certificate no longer exists.');
    expect(failure.status).toBe(404);
    expect(failure.code).toBe('NOT_FOUND');
  });

  it('turns a 429 with Retry-After into an exact wait', async () => {
    const failure = await apiFailure(
      makeResponse(
        429,
        JSON.stringify({
          detail: 'Rate limit exceeded. Try again later.',
          error_code: 'RATE_LIMITED',
        }),
        { 'Retry-After': '30' },
      ),
    );

    expect(failure.message).toBe('Too many requests. Try again in 30 seconds.');
    expect(failure.retryAfterSeconds).toBe(30);
  });

  it('singularises a one-second wait', async () => {
    const failure = await apiFailure(
      makeResponse(429, JSON.stringify({ error_code: 'RATE_LIMITED' }), { 'Retry-After': '1' }),
    );
    expect(failure.message).toBe('Too many requests. Try again in 1 second.');
  });

  it('keeps the server sentence when no Retry-After was sent', async () => {
    const failure = await apiFailure(makeResponse(
      429,
      JSON.stringify({ detail: 'Rate limit exceeded. Try again later.' }),
    ));
    expect(failure.message).toBe('Rate limit exceeded. Try again later.');
    expect(failure.retryAfterSeconds).toBeNull();
  });

  it('reads a date-form Retry-After header', async () => {
    const failure = await apiFailure(
      makeResponse(
        429,
        JSON.stringify({ error_code: 'RATE_LIMITED' }),
        { 'Retry-After': new Date(Date.now() + 60_000).toUTCString() },
      ),
    );
    expect(failure.retryAfterSeconds).toBeGreaterThan(0);
    expect(failure.retryAfterSeconds).toBeLessThanOrEqual(60);
  });

  it('never shows a bare error code when no sentence was sent', async () => {
    const failure = await apiFailure(
      makeResponse(503, JSON.stringify({ error_code: 'PROVIDER_UNAVAILABLE' })),
    );

    expect(failure.message).toBe(
      'No AI provider is available right now. Please try again in a moment.',
    );
    expect(failure.message).not.toContain('PROVIDER_UNAVAILABLE');
  });

  it('survives a proxy HTML error page without leaking markup', async () => {
    const failure = await apiFailure(
      makeResponse(502, '<html><body><h1>502 Bad Gateway</h1></body></html>'),
    );

    expect(failure.message).toBe(
      'The service is having trouble right now. Please try again shortly.',
    );
    expect(failure.message).not.toContain('<');
  });

  it('survives an empty body on an unmapped status', async () => {
    const failure = await apiFailure(
      makeResponse(418, '', {}),
      'Teapot unavailable',
    );
    expect(failure.message).toBe('Teapot unavailable');
    expect(failure.status).toBe(418);
  });

  it('flattens list-shaped detail to a readable sentence', async () => {
    const failure = await apiFailure(makeResponse(422, JSON.stringify({
      // Shape stock FastAPI produces when no custom validation handler ran.
      detail: [{ loc: ['body', 'email'], msg: 'value is not a valid email address' }],
      error_code: 'VALIDATION_ERROR',
    })));

    expect(failure.message).toBe('value is not a valid email address');
    expect(failure.code).toBe('VALIDATION_ERROR');
  });
});

describe('describeApiError', () => {
  it('passes our own failures straight through', () => {
    const failure = new ApiFailure('Too many requests. Try again in 30 seconds.', {
      status: 429, code: 'RATE_LIMITED', retryAfterSeconds: 30,
    });
    expect(describeApiError(failure)).toBe('Too many requests. Try again in 30 seconds.');
  });

  it('explains a network failure instead of the browser wording', () => {
    expect(describeApiError(new TypeError('Failed to fetch'))).toBe(
      'You appear to be offline. Check your connection and try again.',
    );
  });

  it('never forwards an internal error message to the user', () => {
    const bug = new Error("Cannot read properties of undefined (reading 'map')");
    expect(describeApiError(bug, 'Something went wrong')).toBe('Something went wrong');
    expect(describeApiError(bug, 'Something went wrong')).not.toContain('undefined');
  });

  it('uses the caller fallback for non-errors', () => {
    expect(describeApiError('nope', 'Login failed')).toBe('Login failed');
    expect(describeApiError(undefined, 'Login failed')).toBe('Login failed');
  });
});

describe('errorCodeMessage', () => {
  it('translates known codes', () => {
    expect(errorCodeMessage('RATE_LIMITED')).toContain('Too many requests');
    expect(errorCodeMessage('UNAUTHORIZED')).toContain('session has expired');
  });

  it('translates a client-detected truncated stream', () => {
    const copy = errorCodeMessage('STREAM_TRUNCATED');
    expect(copy).toContain('incomplete');
    expect(copy).not.toContain('STREAM_TRUNCATED');
  });

  it('translates a client-detected idle stream', () => {
    // Distinct from truncation: the socket did not close, it stopped talking.
    const copy = errorCodeMessage('STREAM_IDLE');
    expect(copy).toContain('went quiet');
    expect(copy).toContain('incomplete');
    expect(copy).not.toContain('STREAM_IDLE');
  });

  it('prefers a supplied server sentence for an unknown code', () => {
    expect(errorCodeMessage('SOME_NEW_CODE', 'The backend said this.'))
      .toBe('The backend said this.');
  });

  it('falls back to generic copy rather than the raw code', () => {
    expect(errorCodeMessage('SOME_NEW_CODE')).toBe(
      'That request failed. Please try again.',
    );
    expect(errorCodeMessage('SOME_NEW_CODE')).not.toContain('SOME_NEW_CODE');
  });
});
