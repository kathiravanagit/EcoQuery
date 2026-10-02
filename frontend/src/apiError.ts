/**
 * One place that turns a failed request into a sentence a person can act on.
 *
 * Before this existed every call site re-implemented the same three steps —
 * read the body, `JSON.parse` it, fall back to `detail` — and the ones that
 * got it wrong leaked browser internals ("Failed to fetch") or bare status
 * codes ("Server error (500)") at the user. It also gives us a single spot to
 * honour what the backend sends *alongside* the body: the machine-readable
 * `error_code`, and the `Retry-After` header that rides on a 429.
 *
 * The rule this module enforces: a user only ever sees text we wrote. Raw
 * exception messages, stack traces and proxy error pages are collapsed to a
 * safe sentence, while the structured fields stay available for logging.
 */

const OFFLINE_MESSAGE =
  'You appear to be offline. Check your connection and try again.';

/** `fetch` rejects with a `TypeError` for DNS/CORS/offline failures rather
 *  than a `Response`, so this is the only way to tell "no network" from
 *  "our own bug". Matched loosely because browsers word it differently. */
const NETWORK_FAILURE =
  /(failed to fetch|networkerror|network request failed|fetch failed|load failed|connection refused|no internet|network error)/i;

/** Copy for machine-readable `error_code` values the backend emits. */
const CODE_COPY: Record<string, string> = {
  BAD_REQUEST: 'That request could not be understood. Please check it and try again.',
  UNAUTHORIZED: 'Your session has expired. Please sign in again.',
  FORBIDDEN: 'You do not have permission to do that.',
  NOT_FOUND: 'That could not be found.',
  CONFLICT: 'That conflicts with something that already exists.',
  VALIDATION_ERROR: 'Some of the values you sent were invalid.',
  RATE_LIMITED: 'Too many requests. Please slow down and try again shortly.',
  PAYLOAD_TOO_LARGE: 'That is too large to send. Please try a smaller request.',
  INTERNAL_ERROR: 'Something went wrong on our side. Please try again.',
  BAD_GATEWAY: 'The service is having trouble right now. Please try again shortly.',
  SERVICE_UNAVAILABLE:
    'The service is temporarily unavailable. Please try again shortly.',
  PROVIDER_UNAVAILABLE:
    'No AI provider is available right now. Please try again in a moment.',
  PROVIDER_KEY_REJECTED:
    'The provider rejected your API key. Check it and try again.',
  REQUEST_FAILED: 'That request failed. Please try again.',
  // Client-detected, not a backend error_code: the SSE socket closed before
  // the terminal done frame, so the reply on screen is incomplete.
  STREAM_TRUNCATED:
    'The connection dropped before the reply finished, so that answer is incomplete. Please try again.',
  // Client-detected: the socket stayed open but nothing arrived for longer
  // than the server's keepalive interval, so it is dead rather than slow.
  STREAM_IDLE:
    'The connection went quiet before the reply finished, so that answer is incomplete. Please try again.',
};

/** Copy for responses we could not parse — typically a proxy or platform
 *  error page served as HTML instead of our JSON contract. */
const STATUS_COPY: Record<number, string> = {
  400: 'That request was rejected as invalid.',
  401: 'Your session has expired. Please sign in again.',
  403: 'You do not have permission to do that.',
  404: 'That could not be found.',
  409: 'That conflicts with something that already exists.',
  413: 'That is too large to send.',
  422: 'Some of the values you sent were invalid.',
  429: 'Too many requests. Please slow down and try again shortly.',
  500: 'Something went wrong on our side. Please try again.',
  502: 'The service is having trouble right now. Please try again shortly.',
  503: 'The service is temporarily unavailable. Please try again shortly.',
};

export interface ApiFailureOptions {
  status: number;
  code: string;
  retryAfterSeconds: number | null;
}

/**
 * A request that failed, already reduced to user-facing copy.
 *
 * Structured fields are kept for callers that want to branch (a 401 should
 * log you out; a 429 should disable a button for a few seconds).
 */
export class ApiFailure extends Error {
  readonly status: number;
  readonly code: string;
  readonly retryAfterSeconds: number | null;

  constructor(message: string, options: ApiFailureOptions) {
    super(message);
    this.name = 'ApiFailure';
    this.status = options.status;
    this.code = options.code;
    this.retryAfterSeconds = options.retryAfterSeconds;
  }
}

/**
 * Read a failed response into an {@link ApiFailure}.
 *
 * Consumes the body, so call this *instead of* reading `response.text()` /
 * `response.json()` yourself — a `Response` body can only be read once.
 */
export async function apiFailure(
  response: Response,
  fallback = 'That request failed. Please try again.',
): Promise<ApiFailure> {
  const retryAfterSeconds = parseRetryAfter(response.headers.get('Retry-After'));
  const payload = await readJson(response);

  const code = typeof payload?.error_code === 'string' ? payload.error_code : '';
  const detail = pickMessage(payload);
  const status = response.status;

  // Rate limiting is the one case where our generic sentence is worse than
  // the header: the user is told exactly how long to wait.
  let message: string;
  if (code === 'RATE_LIMITED') {
    message =
      retryAfterSeconds === null
        ? (detail || CODE_COPY.RATE_LIMITED)
        : `Too many requests. Try again in ${retryAfterSeconds} second${
            retryAfterSeconds === 1 ? '' : 's'
          }.`;
  } else if (detail) {
    // Server-written sentences are more specific than our generic copy
    // (validation errors name the field), so they win when present.
    message = detail;
  } else {
    message = errorCodeMessage(code, STATUS_COPY[status] || fallback);
  }

  return new ApiFailure(message, { status, code, retryAfterSeconds });
}

/**
 * Turn whatever a `catch` block received into user-facing copy.
 *
 * Anything that is not one of our own failures — a swallowed library error, a
 * `TypeError` from our code — is deliberately *not* forwarded: "Cannot read
 * properties of undefined" is a bug report, not UI copy.
 */
export function describeApiError(
  error: unknown,
  fallback = 'That request failed. Please try again.',
): string {
  if (error instanceof ApiFailure) return error.message;
  if (error instanceof Error && NETWORK_FAILURE.test(error.message)) {
    return OFFLINE_MESSAGE;
  }
  return fallback;
}

/** Copy for a backend `error_code`. Falls back to `fallback`, then to a
 *  generic sentence — never to the bare code (`PROVIDER_UNAVAILABLE`). */
export function errorCodeMessage(code: string, fallback?: string): string {
  if (code && CODE_COPY[code]) return CODE_COPY[code];
  return fallback || CODE_COPY.REQUEST_FAILED;
}

/** `Retry-After` is either a delta in seconds (what we send) or an HTTP date. */
function parseRetryAfter(value: string | null): number | null {
  if (!value) return null;
  const seconds = Number(value);
  if (Number.isFinite(seconds) && seconds >= 0) return Math.ceil(seconds);
  const at = Date.parse(value);
  if (!Number.isNaN(at)) return Math.max(0, Math.ceil((at - Date.now()) / 1000));
  return null;
}

async function readJson(
  response: Response,
): Promise<Record<string, unknown> | null> {
  try {
    const text = await response.text();
    if (!text) return null;
    const parsed: unknown = JSON.parse(text);
    if (parsed && typeof parsed === 'object') return parsed as Record<string, unknown>;
    return null;
  } catch {
    // An HTML error page (Render/nginx/platform 5xx) or a truncated body.
    return null;
  }
}

/** `detail` is normally a string, but stock FastAPI returns a list of
 *  `{loc, msg}` objects when no custom validation handler ran. */
function pickMessage(payload: Record<string, unknown> | null): string {
  if (!payload) return '';
  for (const candidate of [payload.detail, payload.message]) {
    const text = asText(candidate);
    if (text) return text;
  }
  return '';
}

function asText(value: unknown): string {
  if (typeof value === 'string') return value.trim();
  if (Array.isArray(value)) {
    for (const entry of value) {
      if (typeof entry === 'string' && entry.trim()) return entry.trim();
      if (entry && typeof entry === 'object') {
        const msg = (entry as { msg?: unknown }).msg;
        if (typeof msg === 'string' && msg.trim()) return msg.trim();
      }
    }
  }
  return '';
}
