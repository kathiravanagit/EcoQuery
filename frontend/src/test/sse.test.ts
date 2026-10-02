import { consumeSSE, IDLE_TIMEOUT_MS } from '../sse';

function streamOf(text: string): ReadableStream<Uint8Array> {
  const payload = new TextEncoder().encode(text);
  return new ReadableStream({
    start(controller) {
      controller.enqueue(payload);
      controller.close();
    },
  });
}

/** Never sends a byte and never closes — a socket whose peer has vanished. */
function deadSocket(): { stream: ReadableStream<Uint8Array>; cancel: ReturnType<typeof vi.fn> } {
  const cancel = vi.fn();
  const stream = new ReadableStream<Uint8Array>({ start() {}, cancel });
  return { stream, cancel };
}

describe('consumeSSE error frames', () => {
  it('hands both the code and the server sentence to onError', async () => {
    const onError = vi.fn();

    await consumeSSE(
      streamOf('data: {"error_code":"RATE_LIMITED","message":"Slow down a moment."}\n\n'),
      { onError },
    );

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledWith('RATE_LIMITED', 'Slow down a moment.');
  });

  it('still reports the code when the server sent no sentence', async () => {
    const onError = vi.fn();

    await consumeSSE(
      streamOf('data: {"error_code":"PROVIDER_UNAVAILABLE"}\n\n'),
      { onError },
    );

    expect(onError).toHaveBeenCalledWith('PROVIDER_UNAVAILABLE', undefined);
  });

  it('stops reading the socket after an error frame', async () => {
    const onError = vi.fn();
    const onText = vi.fn();

    await consumeSSE(
      streamOf('data: {"error_code":"PROVIDER_UNAVAILABLE"}\n\ndata: {"token":"ignored"}\n\n'),
      { onError, onText },
    );

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onText).not.toHaveBeenCalled();
  });

  it('supports aborting an active stream and reports completion only for done frames', async () => {
    const controller = new AbortController();
    const onComplete = vi.fn();
    const stream = new ReadableStream<Uint8Array>({
      start(streamController) {
        streamController.enqueue(new TextEncoder().encode('data: {"token":"partial"}\n\n'));
      },
      cancel: vi.fn(),
    });

    const consuming = consumeSSE(stream, { onComplete }, controller.signal);
    controller.abort();
    await consuming;

    expect(onComplete).not.toHaveBeenCalled();
  });

  it('calls onComplete after the terminal metadata frame', async () => {
    const onComplete = vi.fn();

    await consumeSSE(
      streamOf('data: {"done":true,"metadata":{"model_used":"test"}}\n\n'),
      { onComplete },
    );

    expect(onComplete).toHaveBeenCalledTimes(1);
  });
});

describe('consumeSSE truncation', () => {
  it('reports STREAM_TRUNCATED when the socket closes before the done frame', async () => {
    const onError = vi.fn();
    const onComplete = vi.fn();

    await consumeSSE(streamOf('data: {"token":"half an ans"}\n\n'), {
      onError,
      onComplete,
    });

    expect(onComplete).not.toHaveBeenCalled();
    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledWith('STREAM_TRUNCATED');
  });

  it('reports STREAM_TRUNCATED when the stream yields no frames at all', async () => {
    const onError = vi.fn();

    await consumeSSE(streamOf(''), { onError });

    expect(onError).toHaveBeenCalledWith('STREAM_TRUNCATED');
  });

  it('does not double-report after a server error frame', async () => {
    const onError = vi.fn();

    await consumeSSE(
      streamOf('data: {"error_code":"PROVIDER_UNAVAILABLE"}\n\n'),
      { onError },
    );

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledWith('PROVIDER_UNAVAILABLE', undefined);
  });

  it('does not report truncation when the user aborts', async () => {
    const controller = new AbortController();
    const onError = vi.fn();
    const stream = new ReadableStream<Uint8Array>({
      start(streamController) {
        streamController.enqueue(new TextEncoder().encode('data: {"token":"partial"}\n\n'));
      },
      cancel: vi.fn(),
    });

    const consuming = consumeSSE(stream, { onError }, controller.signal);
    controller.abort();
    await consuming;

    expect(onError).not.toHaveBeenCalled();
  });

  it('does not report truncation for a completed stream', async () => {
    const onError = vi.fn();

    await consumeSSE(
      streamOf('data: {"done":true,"metadata":{"model_used":"test"}}\n\n'),
      { onError },
    );

    expect(onError).not.toHaveBeenCalled();
  });
});

describe('consumeSSE idle watchdog', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('reports STREAM_IDLE when the socket goes quiet instead of hanging', async () => {
    vi.useFakeTimers();
    const onError = vi.fn();
    const { stream, cancel } = deadSocket();

    const consuming = consumeSSE(stream, { onError });
    await vi.advanceTimersByTimeAsync(IDLE_TIMEOUT_MS + 1_000);
    await consuming;

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledWith('STREAM_IDLE');
    // The read has to be cancelled, not merely timed out: a fired timer with
    // `read()` still pending would leave the caller awaiting forever.
    expect(cancel).toHaveBeenCalled();
  });

  it('uses the default interval, not an arbitrary one', async () => {
    vi.useFakeTimers();
    const onError = vi.fn();
    const { stream } = deadSocket();

    const consuming = consumeSSE(stream, { onError });
    await vi.advanceTimersByTimeAsync(IDLE_TIMEOUT_MS - 5_000);
    expect(onError).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(10_000);
    await consuming;
    expect(onError).toHaveBeenCalledWith('STREAM_IDLE');
  });

  it('treats a keepalive comment as activity, then dies on the silence after it', async () => {
    vi.useFakeTimers();
    const onError = vi.fn();
    const cancel = vi.fn();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(': hb\n\n'));
      },
      cancel,
    });

    const consuming = consumeSSE(stream, { onError });

    // The comment arrived and re-armed the watchdog — still alive.
    await vi.advanceTimersByTimeAsync(IDLE_TIMEOUT_MS - 5_000);
    expect(onError).not.toHaveBeenCalled();

    // Now nothing, past the deadline.
    await vi.advanceTimersByTimeAsync(10_000);
    await consuming;
    expect(onError).toHaveBeenCalledWith('STREAM_IDLE');
  });

  it('does not fire after the terminal done frame', async () => {
    vi.useFakeTimers();
    const onError = vi.fn();
    const onComplete = vi.fn();
    const cancel = vi.fn();
    // Delivered but never closed: without stopping at `done` this would sit
    // in read() with no watchdog left to end it.
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          new TextEncoder().encode('data: {"done":true,"metadata":{}}\n\n'),
        );
      },
      cancel,
    });

    const consuming = consumeSSE(stream, { onError, onComplete });
    await vi.advanceTimersByTimeAsync(IDLE_TIMEOUT_MS * 3);
    await consuming;

    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(onError).not.toHaveBeenCalled();
    expect(cancel).toHaveBeenCalled();
  });

  it('lets a user abort outrank the watchdog', async () => {
    vi.useFakeTimers();
    const controller = new AbortController();
    const onError = vi.fn();
    const { stream } = deadSocket();

    const consuming = consumeSSE(stream, { onError }, controller.signal);
    controller.abort();
    await vi.advanceTimersByTimeAsync(IDLE_TIMEOUT_MS * 2);
    await consuming;

    expect(onError).not.toHaveBeenCalled();
  });

  it('accepts a shorter interval so tests do not wait 45 seconds', async () => {
    const onError = vi.fn();
    const { stream } = deadSocket();

    await consumeSSE(stream, { onError }, undefined, { idleTimeoutMs: 30 });

    expect(onError).toHaveBeenCalledWith('STREAM_IDLE');
  });
});
