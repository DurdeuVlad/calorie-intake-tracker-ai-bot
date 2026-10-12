import { ApiClient, type FetchResponse } from '../src/api/client';
import { deleteMemory, listMemories } from '../src/api/memories';
import type { AuthTokens } from '../src/api/types';
import type { SessionStore, StoredSession } from '../src/auth/storage';

class MemoryStore implements SessionStore {
  session: StoredSession | null = {
    email: 'user@example.com',
    accessToken: 'access-1',
    refreshToken: 'refresh-1',
  };
  deviceId = 'device-1';

  async getDeviceId() {
    return this.deviceId;
  }
  async getSession() {
    return this.session;
  }
  async saveSession(session: StoredSession) {
    this.session = session;
  }
  async updateTokens(tokens: AuthTokens) {
    this.session = { ...(this.session ?? {}), ...tokens };
  }
  async clearSession() {
    this.session = null;
  }
}

function jsonResponse(status: number, body: unknown): FetchResponse {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

type FetchCall = { url: string; init?: RequestInit };

function fetchQueue(...responses: FetchResponse[]) {
  const calls: FetchCall[] = [];
  const queue = [...responses];
  const impl = jest.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    const next = queue.shift();
    if (!next) throw new Error(`unexpected fetch #${calls.length}: ${url}`);
    return next;
  });
  return { impl, calls };
}

function makeClient(store: MemoryStore, impl: jest.Mock) {
  return new ApiClient({
    baseUrl: 'http://localhost:8000',
    store,
    fetchImpl: impl as never,
  });
}

const MEMORY = {
  id: 3,
  kind: 'preference',
  text: 'prefers Romanian',
  source: 'agent',
  created_at: '2026-10-10T09:30:00Z',
  updated_at: '2026-10-10T09:30:00Z',
};

describe('ApiClient.listMemories', () => {
  it('GETs /api/v1/memories with the bearer token', async () => {
    const store = new MemoryStore();
    const { impl, calls } = fetchQueue(jsonResponse(200, { memories: [MEMORY] }));
    const client = makeClient(store, impl);

    const res = await client.listMemories();

    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe('http://localhost:8000/api/v1/memories');
    expect(calls[0].init!.method).toBe('GET');
    const headers = calls[0].init!.headers as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer access-1');
    expect(res.memories).toEqual([MEMORY]);
  });
});

describe('ApiClient.deleteMemory', () => {
  it('DELETEs the memory id and resolves void on 204', async () => {
    const store = new MemoryStore();
    const { impl, calls } = fetchQueue(jsonResponse(204, undefined));
    const client = makeClient(store, impl);

    await expect(client.deleteMemory(3)).resolves.toBeUndefined();

    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe('http://localhost:8000/api/v1/memories/3');
    expect(calls[0].init!.method).toBe('DELETE');
    const headers = calls[0].init!.headers as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer access-1');
  });

  it('throws ApiError with the server detail on 404', async () => {
    const store = new MemoryStore();
    const { impl } = fetchQueue(jsonResponse(404, { detail: 'memory not found' }));
    const client = makeClient(store, impl);

    await expect(client.deleteMemory(99)).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
      detail: 'memory not found',
    });
  });
});

describe('api/memories module', () => {
  it('listMemories issues a GET through the supplied request executor', async () => {
    const body = { memories: [MEMORY] };
    const request: jest.Mock = jest.fn(async () => body);

    const res = await listMemories(request);

    expect(request).toHaveBeenCalledWith('/api/v1/memories', { method: 'GET' });
    expect(res).toBe(body);
  });

  it('deleteMemory issues a DELETE for the given id through the supplied executor', async () => {
    const request: jest.Mock = jest.fn(async () => undefined);

    await deleteMemory(request, 7);

    expect(request).toHaveBeenCalledWith('/api/v1/memories/7', { method: 'DELETE' });
  });
});

describe('204 unwrapping', () => {
  it('does not attempt to parse a body on 204 responses', async () => {
    const store = new MemoryStore();
    const json = jest.fn(async () => {
      throw new Error('unexpected parse');
    });
    const impl = jest.fn(async () => ({ ok: true, status: 204, json }));
    const client = makeClient(store, impl);

    await expect(client.deleteMemory(1)).resolves.toBeUndefined();
    expect(json).not.toHaveBeenCalled();
  });
});

