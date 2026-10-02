import { consumeSSE } from '../sse';

function streamOf(text: string): ReadableStream<Uint8Array> {
  const payload = new TextEncoder().encode(text);
  return new ReadableStream({
    start(controller) {
      controller.enqueue(payload);
      controller.close();
    },
  });
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
