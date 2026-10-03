/**
 * Shared client for POST /api/chat/stream.
 *
 * Both chat surfaces — the public homepage demo (LiveDemo) and the dashboard
 * workspace (WorkspaceChat) — consume the same event stream, and each used to
 * carry its own copy of the parser and of the Metadata shape.
 *
 * The read loop is deliberately frame-buffered. One `reader.read()` can return
 * in the middle of a JSON payload, so splitting each chunk on newlines (the
 * original implementation) dropped every frame whose boundary landed mid-read,
 * silently truncating replies. Frames are instead split on the blank-line
 * delimiter across a buffer that persists between reads.
 *
 * Silence is treated as a fault. The server writes a keepalive comment every
 * 10s whenever it has no token to send, so an open socket that has produced
 * nothing for `IDLE_TIMEOUT_MS` — three missed keepalives — is dead rather than
 * merely slow, and is reported as `STREAM_IDLE` instead of hanging the caller
 * on a spinner forever.
 */

/** How long the stream may go without a single byte before it is called dead.
 *  Deliberately a whole number of keepalives (10s) so that a live server
 *  cannot trip it: three in a row missed means the socket, not the model. */
export const IDLE_TIMEOUT_MS = 45_000;

/** Metadata attached to the final `done` frame. Union of every field either
 *  surface renders, and every field the backend actually sends. */
export interface Metadata {
  model_used?: string;
  model_id?: string;
  model_tier?: string;
  carbon_score?: number;
  region?: string;
  energy_source?: string;
  co2_estimated_g?: number;
  co2_saved_g?: number;
  tier?: string;
  confidence?: number;
  api_cost?: number;
  api_cost_is_estimate?: boolean;
  api_cost_basis?: string;
  latency_seconds?: number;
  estimated_latency_s?: number;
  verification_status?: string;
  verification_reason?: string;
  observed_tps?: number;
  routing_mode?: string;
  answer_source?: string;
  knowledge_match?: boolean;
  knowledge_confidence?: number;
  llm_used?: boolean;
  cache_hit?: boolean;
  prompt_tokens?: number;
  completion_tokens?: number;
  grid_source?: string;
  grid_timestamp?: string;
  measurement_type?: 'measured' | 'provider_reported' | 'estimated';
  energy_kwh?: number;
  energy_measurement_source?: string;
  energy_assumption_kwh_per_1000_tokens?: number;
  carbon_formula?: string;
  carbon_assumptions?: string[];
  requested_provider?: string;
  attempted_providers?: Array<{
    provider?: string;
    model?: string;
    status?: string;
    failure_reason?: string;
  }>;
  final_provider?: string;
  final_model?: string;
  carbon_estimate_is_approximate?: boolean;
  carbon_estimate_basis?: string;
  fallback_reason?: string;
  uncertainty_range_g?: { min: number; max: number };
  uncertainty_components?: Record<string, number>;
  /** Relative uncertainty as a fraction (0.62 → ±62%). Zero when no LLM ran. */
  uncertainty_relative?: number;
  what_if?: {
    baseline_model: string;
    baseline_region: string;
    baseline_co2_g: number;
    actual_model: string;
    actual_region: string;
    actual_co2_g: number;
    co2_saved_g: number;
    baseline_cost: number;
    actual_cost: number;
  };
}

export interface SSECallbacks {
  /** Full reply text so far — already accumulated, callers just render it. */
  onText?: (text: string) => void;
  /** Final metadata frame. */
  onMetadata?: (metadata: Metadata) => void;
  /** Every configured provider key has expired or hit its limit. */
  onKeysExpired?: () => void;
  /** Provider failed; `code` is the backend's error_code, `message` its own
   *  human-readable copy (prefer `errorCodeMessage(code)` for the display). */
  onError?: (code: string, message?: string) => void;
  /** Called when the stream ends after a successful completion frame. */
  onComplete?: () => void;
}

export interface SSEOptions {
  /** Maximum silence in ms before the stream is declared dead. Defaults to
   *  {@link IDLE_TIMEOUT_MS}; tests shorten it rather than wait 45s. */
  idleTimeoutMs?: number;
}

/** Tags one user action — a click of Send, or of Retry.
 *
 *  Reused when that same send is attempted again, so the server can hand back
 *  what it already produced instead of paying to produce it twice. A new
 *  message, or a deliberate re-ask, gets a fresh key: reusing one there would
 *  turn the second answer into a replay of the first. */
export function newIdempotencyKey(): string {
  // randomUUID is unavailable on insecure origins, and this key is a
  // de-duplication hint rather than a credential, so a fallback is acceptable.
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  let out = '';
  for (let i = 0; i < 32; i += 1) {
    out += Math.floor(Math.random() * 16).toString(16);
  }
  return out;
}

export interface StreamFetchOptions {
  /** Encoded as JSON here rather than requiring a pre-stringified body. */
  body: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

/** POSTs the stream request, retrying once when the connection itself fails.
 *
 *  The `Idempotency-Key` is carried across both attempts, and that is what
 *  makes the retry safe: if the first attempt reached a finished answer and
 *  only the response was lost, the second receives that answer rather than
 *  paying for a second generation of the same send.
 *
 *  Only a rejected `fetch` is retried. Any response — a 4xx or 5xx, an empty
 *  body or a malformed one — means the server was reached and replied, so
 *  re-sending would be guessing instead of recovering, and could double a
 *  provider call that already ran. Retrying those is how a client turns one
 *  failing server into a stampede. */
export async function fetchStream(
  url: string,
  options: StreamFetchOptions,
  key: string,
): Promise<Response> {
  const attempt = () =>
    fetch(url, {
      method: 'POST',
      signal: options.signal,
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': key,
        ...options.headers,
      },
      body: JSON.stringify(options.body),
    });

  try {
    return await attempt();
  } catch (error) {
    // A caller-initiated abort is an answer, not a transport failure. Retrying
    // one would issue a fresh request immediately after cancellation.
    if (options.signal?.aborted) throw error;
    return await attempt();
  }
}

export async function consumeSSE(
  body: ReadableStream<Uint8Array>,
  callbacks: SSECallbacks,
  signal?: AbortSignal,
  options?: SSEOptions,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  let reply = '';
  // Error frames are terminal — stop pulling from the socket instead of
  // waiting for a stream the server has already finished writing.
  let stopped = false;
  let completed = false;
  // Set only by the watchdog, so a user abort is never mistaken for a dead
  // connection — cancellation already has its own announcement.
  let idle = false;

  const idleTimeoutMs = options?.idleTimeoutMs ?? IDLE_TIMEOUT_MS;
  let idleTimer: ReturnType<typeof setTimeout> | undefined;

  const clearIdleTimer = () => {
    if (idleTimer !== undefined) {
      clearTimeout(idleTimer);
      idleTimer = undefined;
    }
  };

  /** Armed immediately before every `read()`, so the timer covers exactly the
   *  window in which nothing can arrive. Cancelling the reader is what ends
   *  the loop: a timer on its own would fire and leave `read()` pending
   *  forever, which is the hang this exists to prevent. */
  const armIdleTimer = () => {
    if (stopped || completed) return;
    clearIdleTimer();
    idleTimer = setTimeout(() => {
      idle = true;
      stopped = true;
      void reader.cancel();
    }, idleTimeoutMs);
  };

  const abort = () => {
    stopped = true;
    // User intent outranks the watchdog: without this the timer could fire
    // after cancellation and report a dead socket for one the caller closed.
    clearIdleTimer();
    void reader.cancel();
  };
  signal?.addEventListener('abort', abort, { once: true });

  const processFrame = (frame: string) => {
    const dataLine = frame.split('\n').find((line) => line.startsWith('data: '));
    if (!dataLine) return;

    let data: Record<string, any>;
    try {
      data = JSON.parse(dataLine.slice(6));
    } catch (error) {
      console.error('Error parsing SSE', error);
      return;
    }

    if (data.error === 'ALL_KEYS_EXPIRED') {
      callbacks.onKeysExpired?.();
      stopped = true;
      return;
    }
    if (data.error_code) {
      callbacks.onError?.(
        String(data.error_code),
        typeof data.message === 'string' ? data.message : undefined,
      );
      stopped = true;
      return;
    }
    if (data.token) {
      reply += data.token;
      callbacks.onText?.(reply);
    }
    if (data.done && data.metadata) {
      callbacks.onMetadata?.(data.metadata);
      completed = true;
      callbacks.onComplete?.();
    }
  };

  try {
    for (;;) {
      if (signal?.aborted) {
        abort();
        break;
      }
      armIdleTimer();
      const { value, done } = await reader.read();
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });

      const frames = buffer.replace(/\r\n/g, '\n').split('\n\n');
      buffer = frames.pop() || '';
      for (const frame of frames) {
        processFrame(frame);
        // `done` is terminal just as an error frame is: nothing follows it, so
        // stop pulling rather than sit in `read()` waiting on a socket the
        // server may never bother to close.
        if (stopped || completed) break;
      }
      if (stopped || completed) break;

      if (done) {
        // Flush a trailing frame that was never followed by a blank line.
        processFrame(buffer);
        break;
      }
    }
  } finally {
    clearIdleTimer();
    signal?.removeEventListener('abort', abort);
    // `cancel()` is idempotent, and every exit path — normal end, terminal
    // frame, server error, user abort, idle kill — leaves the reader holding
    // a socket nobody will read from again.
    await reader.cancel();
  }

  // Distinguishes the three ways a stream fails to finish:
  //   - the server sent an error frame, or the caller aborted  -> `stopped`
  //   - the socket went quiet for longer than any keepalive     -> `STREAM_IDLE`
  //   - the socket closed while partial text was on screen      -> `STREAM_TRUNCATED`
  // Without these the loop returned normally and partial text was displayed
  // as a finished answer behind a transport-level HTTP 200.
  //
  // Deliberately after the try/finally: if read() threw, the caller's catch
  // handles it and firing onError here as well would double-report.
  if (idle && !completed) {
    callbacks.onError?.('STREAM_IDLE');
  } else if (!completed && !stopped) {
    callbacks.onError?.('STREAM_TRUNCATED');
  }
}
