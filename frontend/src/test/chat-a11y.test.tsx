/**
 * Accessibility and cancellation behaviour of the streaming chat surfaces.
 *
 * Two guarantees under test:
 *
 *  - each surface owns a persistent `aria-live="polite"` region that announces
 *    a *settled* outcome — the finished reply, the failure copy produced by
 *    `errorCodeMessage`, or the cancellation — and stays silent while tokens
 *    are still streaming in;
 *  - the homepage Live demo can abort its in-flight request through a real,
 *    labelled button and restarts cleanly afterwards (no stuck spinner, no
 *    half-written reply left behind).
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import LiveDemo from '../components/LiveDemo';
import WorkspaceChat from '../components/dashboard/WorkspaceChat';

const fetchMock = vi.fn();

function jsonResponse(payload: unknown): Response {
  return { ok: true, json: async () => payload } as unknown as Response;
}

interface StreamHandle {
  response: Response;
  /** Spy on the underlying source's `cancel`, i.e. the reader being torn down. */
  cancel: ReturnType<typeof vi.fn>;
  /** Enqueue one raw SSE frame (`data: {...}\n\n`). */
  push: (frame: string) => void;
  close: () => void;
}

/** A stream the test drives frame by frame, so "mid-stream" is a real state. */
function openStream(): StreamHandle {
  let ctrl!: ReadableStreamDefaultController<Uint8Array>;
  const cancel = vi.fn();
  const stream = new ReadableStream<Uint8Array>({
    start(c) { ctrl = c; },
    cancel,
  });
  const encoder = new TextEncoder();
  return {
    response: { ok: true, body: stream } as unknown as Response,
    cancel,
    push: (frame) => ctrl.enqueue(encoder.encode(frame)),
    close: () => ctrl.close(),
  };
}

/** The stream handed to the next `/api/chat/stream` call. */
let nextStream: StreamHandle | null = null;

type FetchCall = [input: unknown, init?: RequestInit];

beforeEach(() => {
  nextStream = null;
  fetchMock.mockReset();
  fetchMock.mockImplementation(async (input: unknown) => {
    const url = String(input);
    if (url.includes('/api/models')) return jsonResponse({ models: [] });
    if (url.includes('/api/chat/stream')) {
      if (!nextStream) throw new Error(`no stream prepared for ${url}`);
      return nextStream.response;
    }
    throw new Error(`unexpected fetch: ${url}`);
  });
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function chatCalls(): FetchCall[] {
  return fetchMock.mock.calls.filter(c => String(c[0]).includes('/api/chat/stream')) as FetchCall[];
}

function requestSignal(call: FetchCall): AbortSignal {
  return (call[1] as RequestInit).signal as AbortSignal;
}

function liveRegion(container: HTMLElement): Element | null {
  return container.querySelector('[aria-live="polite"]');
}

async function askInDemo(question: string): Promise<void> {
  fireEvent.change(screen.getByLabelText('Chat message'), { target: { value: question } });
  fireEvent.click(screen.getByRole('button', { name: 'Send message' }));
}

describe('Live demo cancellation', () => {
  it('offers a labelled cancel control only while a run is in flight', async () => {
    nextStream = openStream();
    render(<LiveDemo />);

    expect(screen.queryByRole('button', { name: 'Stop generating' })).toBeNull();

    await askInDemo('Why is the sky blue?');
    await screen.findByRole('button', { name: 'Stop generating' });
    expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled();

    nextStream.push('data: {"token":"Rayleigh scattering"}\n\n');
    await screen.findByText('Rayleigh scattering');
    expect(screen.getByRole('button', { name: 'Stop generating' })).toBeInTheDocument();
  });

  it('aborts the in-flight request and returns to a restartable state', async () => {
    const stream = openStream();
    nextStream = stream;
    const { container } = render(<LiveDemo />);

    await askInDemo('Why is the sky blue?');
    stream.push('data: {"token":"Rayleigh scattering"}\n\n');
    await screen.findByText('Rayleigh scattering');

    const signal = requestSignal(chatCalls()[0]);
    expect(signal.aborted).toBe(false);

    fireEvent.click(screen.getByRole('button', { name: 'Stop generating' }));

    // The request itself is aborted, not just hidden behind a state flag.
    await waitFor(() => expect(signal.aborted).toBe(true));
    await waitFor(() => expect(stream.cancel).toHaveBeenCalled());

    // …and the component lands back on a clean, restartable footing.
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Stop generating' })).toBeNull();
    });
    // Send is disabled only because the input was cleared by the cancelled
    // run; typing again re-enables it (asserted below).
    expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled();

    const messages = container.querySelector('.chat-messages');
    expect(messages?.textContent).toContain('Why is the sky blue?');
    // The partial reply is gone rather than presented as a finished answer,
    // and no failure/retry affordance was invented for a deliberate cancel.
    expect(messages?.textContent).not.toContain('Rayleigh scattering');
    expect(container.querySelector('.retry-button')).toBeNull();
    expect(liveRegion(container)?.textContent).toContain('Response cancelled.');

    // A second run starts normally with its own fresh request: typing
    // re-enables Send, and the new request is not already aborted.
    nextStream = openStream();
    fireEvent.change(screen.getByLabelText('Chat message'), { target: { value: 'And the grass?' } });
    expect(screen.getByRole('button', { name: 'Send message' })).not.toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));
    await screen.findByRole('button', { name: 'Stop generating' });
    expect(chatCalls().length).toBe(2);
    const secondSignal = requestSignal(chatCalls()[1]);
    expect(secondSignal.aborted).toBe(false);

    // Clean up the second run so nothing dangles past the test.
    fireEvent.click(screen.getByRole('button', { name: 'Stop generating' }));
    await waitFor(() => expect(secondSignal.aborted).toBe(true));
  });
});

describe('Live demo aria-live announcements', () => {
  it('exposes a polite, atomic status region', () => {
    nextStream = openStream();
    const { container } = render(<LiveDemo />);

    const region = liveRegion(container);
    expect(region).not.toBeNull();
    expect(region).toHaveAttribute('role', 'status');
    expect(region).toHaveAttribute('aria-live', 'polite');
    expect(region).toHaveAttribute('aria-atomic', 'true');
  });

  it('stays silent while tokens stream, then announces the finished answer once', async () => {
    const stream = openStream();
    nextStream = stream;
    const { container } = render(<LiveDemo />);

    await askInDemo('Explain photosynthesis');
    stream.push('data: {"token":"Plants turn light into sugar."}\n\n');
    await screen.findByText('Plants turn light into sugar.');
    // Not one announcement per token — that would be unusable.
    expect(liveRegion(container)?.textContent).toBe('');

    stream.push('data: {"token":" It also releases oxygen."}\n\n');
    await screen.findByText('Plants turn light into sugar. It also releases oxygen.');
    expect(liveRegion(container)?.textContent).toBe('');

    stream.push('data: {"done":true,"metadata":{"model_used":"test-model"}}\n\n');
    stream.close();

    await waitFor(() => {
      expect(liveRegion(container)?.textContent).toBe(
        'Plants turn light into sugar. It also releases oxygen.',
      );
    });
  });

  it('announces the CODE_COPY copy for a server error frame', async () => {
    const stream = openStream();
    nextStream = stream;
    const { container } = render(<LiveDemo />);

    await askInDemo('Explain photosynthesis');
    stream.push('data: {"error_code":"PROVIDER_UNAVAILABLE"}\n\n');

    await waitFor(() => {
      expect(liveRegion(container)?.textContent).toContain(
        'No AI provider is available right now. Please try again in a moment.',
      );
    });
  });

  it('announces a truncated stream as an incomplete answer', async () => {
    const stream = openStream();
    nextStream = stream;
    const { container } = render(<LiveDemo />);

    await askInDemo('Explain photosynthesis');
    stream.push('data: {"token":"Half an ans"}\n\n');
    stream.close();

    await waitFor(() => {
      expect(liveRegion(container)?.textContent).toContain('incomplete');
    });
  });
});

describe('Workspace chat aria-live announcements', () => {
  it('exposes a polite, atomic status region', () => {
    nextStream = openStream();
    const { container } = render(<WorkspaceChat token="test-token" />);

    const region = liveRegion(container);
    expect(region).not.toBeNull();
    expect(region).toHaveAttribute('role', 'status');
    expect(region).toHaveAttribute('aria-live', 'polite');
    expect(region).toHaveAttribute('aria-atomic', 'true');
  });

  it('announces the completed reply and stays silent while streaming', async () => {
    const stream = openStream();
    nextStream = stream;
    const { container } = render(<WorkspaceChat token="test-token" />);

    fireEvent.change(screen.getByPlaceholderText('Ask anything...'), {
      target: { value: 'Explain photosynthesis' },
    });
    const form = container.querySelector('form');
    expect(form).not.toBeNull();
    fireEvent.submit(form!);

    stream.push('data: {"token":"Plants turn light into sugar."}\n\n');
    await screen.findByText('Plants turn light into sugar.');
    expect(liveRegion(container)?.textContent).toBe('');

    stream.push('data: {"done":true,"metadata":{"model_used":"test-model"}}\n\n');
    stream.close();

    await waitFor(() => {
      expect(liveRegion(container)?.textContent).toBe('Plants turn light into sugar.');
    });
  });
});
