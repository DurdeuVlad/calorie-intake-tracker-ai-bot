import { ApiClient, type FetchResponse } from '../src/api/client';
import { disableDevice, listDevices, registerDevice } from '../src/api/devices';
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

const DEVICE = {
  id: 5,
  platform: 'android',
  app_version: '1.0.0',
  locale: 'en-US',
  created_at: '2026-10-12T09:00:00Z',
  last_seen_at: '2026-10-12T09:00:00Z',
  disabled_at: null,
};

describe('ApiClient.registerDevice', () => {
  it('POSTs the device payload as JSON with the bearer token', async () => {
    const store = new MemoryStore();
    const { impl, calls } = fetchQueue(jsonResponse(200, DEVICE));
    const client = makeClient(store, impl);

    const input = {
      platform: 'android' as const,
      push_token: 'ExponentPushToken[abc]',
      app_version: '1.0.0',
      locale: 'en-US',
    };
    const res = await client.registerDevice(input);

    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe('http://localhost:8000/api/v1/devices');
    expect(calls[0].init!.method).toBe('POST');
    expect(JSON.parse(calls[0].init!.body as string)).toEqual(input);
    const headers = calls[0].init!.headers as Record<string, string>;
    expect(headers['Content-Type']).toBe('application/json');
    expect(headers.Authorization).toBe('Bearer access-1');
    expect(res.id).toBe(5);
  });
});

describe('ApiClient.listDevices', () => {
  it('GETs /api/v1/devices with the bearer token', async () => {
    const store = new MemoryStore();
    const { impl, calls } = fetchQueue(jsonResponse(200, { devices: [DEVICE] }));
    const client = makeClient(store, impl);

    const res = await client.listDevices();

    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe('http://localhost:8000/api/v1/devices');
    expect(calls[0].init!.method).toBe('GET');
    const headers = calls[0].init!.headers as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer access-1');
    expect(res.devices).toEqual([DEVICE]);
  });
});

describe('ApiClient.disableDevice', () => {
  it('DELETEs the device id and resolves void on 204', async () => {
    const store = new MemoryStore();
    const { impl, calls } = fetchQueue(jsonResponse(204, undefined));
    const client = makeClient(store, impl);

    await expect(client.disableDevice(5)).resolves.toBeUndefined();

    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe('http://localhost:8000/api/v1/devices/5');
    expect(calls[0].init!.method).toBe('DELETE');
    const headers = calls[0].init!.headers as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer access-1');
  });

  it('throws ApiError with the server detail on 404', async () => {
    const store = new MemoryStore();
    const { impl } = fetchQueue(jsonResponse(404, { detail: 'device not found' }));
    const client = makeClient(store, impl);

    await expect(client.disableDevice(99)).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
      detail: 'device not found',
    });
  });
});

describe('api/devices module', () => {
  it('registerDevice issues a JSON POST through the supplied request executor', async () => {
    const request: jest.Mock = jest.fn(async () => DEVICE);
    const input = {
      platform: 'ios' as const,
      push_token: 'ExponentPushToken[xyz]',
      app_version: '1.0.0',
      locale: 'ro-RO',
    };

    const res = await registerDevice(request, input);

    expect(request).toHaveBeenCalledWith('/api/v1/devices', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(input),
    });
    expect(res).toBe(DEVICE);
  });

  it('listDevices issues a GET through the supplied request executor', async () => {
    const body = { devices: [DEVICE] };
    const request: jest.Mock = jest.fn(async () => body);

    const res = await listDevices(request);

    expect(request).toHaveBeenCalledWith('/api/v1/devices', { method: 'GET' });
    expect(res).toBe(body);
  });

  it('disableDevice issues a DELETE for the given id through the supplied executor', async () => {
    const request: jest.Mock = jest.fn(async () => undefined);

    await disableDevice(request, 9);

    expect(request).toHaveBeenCalledWith('/api/v1/devices/9', { method: 'DELETE' });
  });
});
