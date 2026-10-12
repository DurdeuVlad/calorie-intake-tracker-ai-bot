import { ApiClient, type FetchResponse } from '../src/api/client';
import { ApiError, AuthError } from '../src/api/errors';
import type { AuthTokens } from '../src/api/types';
import type { SessionStore, StoredSession } from '../src/auth/storage';

class MemoryStore implements SessionStore {
  session: StoredSession | null = null;
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

const TOKENS = { access_token: 'access-1', token_type: 'bearer', expires_in: 900, refresh_token: 'refresh-1' };
const ROTATED = { access_token: 'access-2', token_type: 'bearer', expires_in: 900, refresh_token: 'refresh-2' };

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

function makeClient(store: MemoryStore, impl: jest.Mock, onSessionExpired?: () => void) {
  return new ApiClient({
    baseUrl: 'http://localhost:8000',
    store,
    fetchImpl: impl as never,
    onSessionExpired,
  });
}

describe('ApiClient auth endpoints', () => {
  it('logs in and persists the session with the device id', async () => {
    const store = new MemoryStore();
    const { impl, calls } = fetchQueue(jsonResponse(200, TOKENS));
    const client = makeClient(store, impl);

    await client.login('user@example.com', 'password123');

    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe('http://localhost:8000/api/v1/auth/login');
    expect(JSON.parse(calls[0].init!.body as string)).toEqual({
      email: 'user@example.com',
      password: 'password123',
      device_id: 'device-1',
    });
    expect(store.session).toEqual({
      email: 'user@example.com',
      accessToken: 'access-1',
      refreshToken: 'refresh-1',
    });
  });

  it('signs up and persists the session', async () => {
    const store = new MemoryStore();
    const { impl, calls } = fetchQueue(jsonResponse(201, TOKENS));
    const client = makeClient(store, impl);

    await client.signup('new@example.com', 'password123');

    expect(calls[0].url).toBe('http://localhost:8000/api/v1/auth/signup');
    expect(store.session?.accessToken).toBe('access-1');
  });

  it('surfaces the server detail on a 401 login', async () => {
    const store = new MemoryStore();
    const { impl } = fetchQueue(jsonResponse(401, { detail: 'invalid email or password' }));
    const client = makeClient(store, impl);

    await expect(client.login('a@b.co', 'wrong-pass')).rejects.toMatchObject({
      name: 'AuthError',
      status: 401,
      message: 'invalid email or password',
    });
    expect(store.session).toBeNull();
  });

  it('surfaces a 409 on duplicate signup', async () => {
    const store = new MemoryStore();
    const { impl } = fetchQueue(jsonResponse(409, { detail: 'email already registered' }));
    const client = makeClient(store, impl);

    await expect(client.signup('a@b.co', 'password123')).rejects.toMatchObject({
      name: 'ApiError',
      status: 409,
      message: 'email already registered',
    });
  });
});

describe('ApiClient authenticated requests', () => {
  function signedInStore() {
    const store = new MemoryStore();
    store.session = { email: 'user@example.com', accessToken: 'access-1', refreshToken: 'refresh-1' };
    return store;
  }

  it('attaches the bearer token to /link/status', async () => {
    const store = signedInStore();
    const { impl, calls } = fetchQueue(jsonResponse(200, { linkedProviders: ['telegram'] }));
    const client = makeClient(store, impl);

    const res = await client.getLinkStatus();

    expect(res.linkedProviders).toEqual(['telegram']);
    expect((calls[0].init!.headers as Record<string, string>).Authorization).toBe('Bearer access-1');
  });

  it('throws before any fetch when there is no session', async () => {
    const store = new MemoryStore();
    const { impl } = fetchQueue();
    const client = makeClient(store, impl);

    await expect(client.getLinkStatus()).rejects.toBeInstanceOf(AuthError);
    expect(impl).not.toHaveBeenCalled();
  });

  it('refreshes once on 401 and retries with the rotated token', async () => {
    const store = signedInStore();
    const { impl, calls } = fetchQueue(
      jsonResponse(401, { detail: 'invalid or expired access token' }),
      jsonResponse(200, ROTATED),
      jsonResponse(200, { linkedProviders: ['telegram', 'mobile'] }),
    );
    const client = makeClient(store, impl);

    const res = await client.getLinkStatus();

    expect(res.linkedProviders).toEqual(['telegram', 'mobile']);
    expect(calls.map((c) => c.url)).toEqual([
      'http://localhost:8000/api/v1/link/status',
      'http://localhost:8000/api/v1/auth/refresh',
      'http://localhost:8000/api/v1/link/status',
    ]);
    expect(JSON.parse(calls[1].init!.body as string)).toEqual({
      refresh_token: 'refresh-1',
      device_id: 'device-1',
    });
    expect((calls[2].init!.headers as Record<string, string>).Authorization).toBe('Bearer access-2');
    // Rotated pair is persisted; the session keeps its email.
    expect(store.session).toEqual({
      email: 'user@example.com',
      accessToken: 'access-2',
      refreshToken: 'refresh-2',
    });
  });

  it('clears the session and stops when refresh itself returns 401', async () => {
    const store = signedInStore();
    const expired = jest.fn();
    const { impl, calls } = fetchQueue(
      jsonResponse(401, { detail: 'expired' }),
      jsonResponse(401, { detail: 'invalid refresh token' }),
    );
    const client = makeClient(store, impl, expired);

    await expect(client.getLinkStatus()).rejects.toBeInstanceOf(AuthError);

    expect(calls).toHaveLength(2);
    expect(store.session).toBeNull();
    expect(expired).toHaveBeenCalledTimes(1);
  });

  it('does not loop: a second 401 after refresh ends the session', async () => {
    const store = signedInStore();
    const expired = jest.fn();
    const { impl, calls } = fetchQueue(
      jsonResponse(401, { detail: 'expired' }),
      jsonResponse(200, ROTATED),
      jsonResponse(401, { detail: 'still unauthorized' }),
    );
    const client = makeClient(store, impl, expired);

    await expect(client.getLinkStatus()).rejects.toBeInstanceOf(AuthError);

    // Exactly one /refresh call — the retried 401 never triggers another.
    expect(calls).toHaveLength(3);
    expect(calls.filter((c) => c.url.endsWith('/auth/refresh'))).toHaveLength(1);
    expect(store.session).toBeNull();
    expect(expired).toHaveBeenCalledTimes(1);
  });

  it('shares one refresh across concurrent 401s (rotation race)', async () => {
    const store = signedInStore();
    const { impl, calls } = fetchQueue(
      jsonResponse(401, { detail: 'expired' }),
      jsonResponse(401, { detail: 'expired' }),
      jsonResponse(200, ROTATED),
      jsonResponse(200, { linkedProviders: [] }),
      jsonResponse(200, { linkedProviders: [] }),
    );
    const client = makeClient(store, impl);

    const [a, b] = await Promise.all([client.getLinkStatus(), client.getLinkStatus()]);

    expect(a.linkedProviders).toEqual([]);
    expect(b.linkedProviders).toEqual([]);
    expect(calls.filter((c) => c.url.endsWith('/auth/refresh'))).toHaveLength(1);
    expect(store.session?.refreshToken).toBe('refresh-2');
  });

  it('propagates non-401 errors without refreshing', async () => {
    const store = signedInStore();
    const { impl, calls } = fetchQueue(jsonResponse(500, { detail: 'boom' }));
    const client = makeClient(store, impl);

    await expect(client.getLinkStatus()).rejects.toMatchObject({
      name: 'ApiError',
      status: 500,
      message: 'boom',
    });
    expect(calls).toHaveLength(1);
    expect(store.session).not.toBeNull();
  });
});
