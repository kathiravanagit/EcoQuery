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
 */

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

export async function consumeSSE(
  body: ReadableStream<Uint8Array>,
  callbacks: SSECallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  let reply = '';
  // Error frames are terminal — stop pulling from the socket instead of
  // waiting for a stream the server has already finished writing.
  let stopped = false;
  let completed = false;

  const abort = () => {
    stopped = true;
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
        return;
      }
      const { value, done } = await reader.read();
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });

      const frames = buffer.replace(/\r\n/g, '\n').split('\n\n');
      buffer = frames.pop() || '';
      for (const frame of frames) {
        processFrame(frame);
        if (stopped) break;
      }
      if (stopped) return;

      if (done) {
        // Flush a trailing frame that was never followed by a blank line.
        processFrame(buffer);
        return;
      }
    }
  } finally {
    signal?.removeEventListener('abort', abort);
    if (!completed && !stopped) {
      await reader.cancel();
    }
  }
}
