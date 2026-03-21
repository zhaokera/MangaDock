import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
  const url = typeof input === 'string' ? input : input.toString();

  if (url.includes('/api/platforms')) {
    return new Response(JSON.stringify({ platforms: [] }), {
      headers: { 'Content-Type': 'application/json' },
    });
  }

  if (url.includes('/api/history')) {
    return new Response(JSON.stringify({ history: [] }), {
      headers: { 'Content-Type': 'application/json' },
    });
  }

  return new Response(JSON.stringify({}), {
    headers: { 'Content-Type': 'application/json' },
  });
});

const EventSourceMock = vi.fn(function MockEventSource(this: { url: string }, url: string | URL) {
  this.url = String(url);
}) as unknown as typeof EventSource;

vi.stubGlobal('fetch', fetchMock);
vi.stubGlobal('EventSource', EventSourceMock);
