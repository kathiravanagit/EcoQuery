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
});
