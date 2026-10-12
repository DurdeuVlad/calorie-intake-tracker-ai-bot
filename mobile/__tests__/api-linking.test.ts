import { ApiClient, type FetchResponse } from '../src/api/client';
import { ApiError } from '../src/api/errors';
import { issueLinkCode, linkStatus, redeemLinkCode } from '../src/api/linking';
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

describe('ApiClient.getLinkStatus', () => {
  it('GETs /api/v1/link/status with the bearer token', async () => {
    const store = new MemoryStore();
    const { impl, calls } = fetchQueue(
      jsonResponse(200, { linkedProviders: ['telegram'] }),
    );
    const client = makeClient(store, impl);

    const res = await client.getLinkStatus();

    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe('http://localhost:8000/api/v1/link/status');
    expect(calls[0].init!.method).toBe('GET');
    const headers = calls[0].init!.headers as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer access-1');
    expect(res.linkedProviders).toEqual(['telegram']);
  });
});

describe('ApiClient.issueLinkCode', () => {
  it('POSTs /api/v1/link/issue and returns the code and expiry', async () => {
    const store = new MemoryStore();
    const { impl, calls } = fetchQueue(
      jsonResponse(200, { code: 'ABCD1234', expiresAt: '2026-10-12T10:10:00Z' }),
    );
    const client = makeClient(store, impl);

    const res = await client.issueLinkCode();

    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe('http://localhost:8000/api/v1/link/issue');
    expect(calls[0].init!.method).toBe('POST');
    const headers = calls[0].init!.headers as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer access-1');
    expect(res.code).toBe('ABCD1234');
    expect(res.expiresAt).toBe('2026-10-12T10:10:00Z');
  });
});

describe('ApiClient.redeemLinkCode', () => {
  it('POSTs JSON {code} to /api/v1/link/redeem and returns provider status', async () => {
    const store = new MemoryStore();
    const { impl, calls } = fetchQueue(
      jsonResponse(200, { linkedProviders: ['telegram'] }),
    );
    const client = makeClient(store, impl);

    const res = await client.redeemLinkCode('WXYZ9876');

    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe('http://localhost:8000/api/v1/link/redeem');
    expect(calls[0].init!.method).toBe('POST');
    expect(JSON.parse(calls[0].init!.body as string)).toEqual({ code: 'WXYZ9876' });
    const headers = calls[0].init!.headers as Record<string, string>;
    expect(headers['Content-Type']).toBe('application/json');
    expect(headers.Authorization).toBe('Bearer access-1');
    expect(res.linkedProviders).toEqual(['telegram']);
  });

  it('surfaces 409 conflicts as ApiError status 409', async () => {
    const store = new MemoryStore();
    const { impl } = fetchQueue(
      jsonResponse(409, {
        detail: 'this account already has journal data and cannot be linked',
      }),
    );
    const client = makeClient(store, impl);

    const err = await client.redeemLinkCode('WXYZ9876').catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(409);
    expect(err.detail).toContain('journal data');
  });

  it('surfaces invalid/expired codes as ApiError status 400', async () => {
    const store = new MemoryStore();
    const { impl } = fetchQueue(
      jsonResponse(400, { detail: 'invalid or expired link code' }),
    );
    const client = makeClient(store, impl);

    const err = await client.redeemLinkCode('BADCODE1').catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(400);
  });
});

describe('api/linking module', () => {
  it('linkStatus issues a GET through the supplied request executor', async () => {
    const body = { linkedProviders: [] };
    const request: jest.Mock = jest.fn(async () => body);

    const res = await linkStatus(request);

    expect(request).toHaveBeenCalledWith('/api/v1/link/status', { method: 'GET' });
    expect(res).toBe(body);
  });

  it('issueLinkCode issues a POST through the supplied request executor', async () => {
    const body = { code: 'ABCD1234', expiresAt: '2026-10-12T10:10:00Z' };
    const request: jest.Mock = jest.fn(async () => body);

    const res = await issueLinkCode(request);

    expect(request).toHaveBeenCalledWith('/api/v1/link/issue', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    });
    expect(res).toBe(body);
  });

  it('redeemLinkCode issues a JSON POST through the supplied request executor', async () => {
    const body = { linkedProviders: ['telegram'] };
    const request: jest.Mock = jest.fn(async () => body);

    const res = await redeemLinkCode(request, 'WXYZ9876');

    expect(request).toHaveBeenCalledWith('/api/v1/link/redeem', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ code: 'WXYZ9876' }),
    });
    expect(res).toBe(body);
  });
});
