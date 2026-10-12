import { ApiClient, type FetchResponse } from '../src/api/client';
import { ApiError, AuthError, userFacingMessage } from '../src/api/errors';
import { sendAudioMessage, sendMessage } from '../src/api/messages';
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

const REPLY = {
  reply: 'Logged two eggs.',
  actions: [
    {
      ok: true,
      type: 'ADD_ENTRY',
      entry: { id: 7, calories: 140, eaten_at: null, description: 'two eggs' },
      date: '2026-10-12',
      message: null,
    },
  ],
};

describe('ApiClient.sendMessage', () => {
  it('POSTs JSON {text} with the bearer token', async () => {
    const store = new MemoryStore();
    const { impl, calls } = fetchQueue(jsonResponse(200, REPLY));
    const client = makeClient(store, impl);

    const res = await client.sendMessage({ text: 'two eggs' });

    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe('http://localhost:8000/api/v1/messages');
    expect(calls[0].init!.method).toBe('POST');
    expect(JSON.parse(calls[0].init!.body as string)).toEqual({ text: 'two eggs' });
    const headers = calls[0].init!.headers as Record<string, string>;
    expect(headers['Content-Type']).toBe('application/json');
    expect(headers.Authorization).toBe('Bearer access-1');
    expect(res.reply).toBe('Logged two eggs.');
    expect(res.actions[0].entry?.calories).toBe(140);
  });
});

describe('ApiClient.sendAudioMessage', () => {
  it('POSTs multipart with the recording in the audio field', async () => {
    const store = new MemoryStore();
    const { impl, calls } = fetchQueue(jsonResponse(200, REPLY));
    const client = makeClient(store, impl);

    await client.sendAudioMessage({
      uri: 'file:///cache/rec-1.m4a',
      mimeType: 'audio/m4a',
      caption: 'forgot to mention the toast',
    });

    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe('http://localhost:8000/api/v1/messages');
    expect(calls[0].init!.method).toBe('POST');
    const headers = calls[0].init!.headers as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer access-1');
    // The boundary-bearing Content-Type is set by fetch, not by us.
    expect(headers['Content-Type']).toBeUndefined();

    const form = calls[0].init!.body as FormData;
    const [audio] = form.getAll('audio') as (Blob & { name?: string })[];
    expect(audio).toBeDefined();
    expect(audio.type).toBe('audio/m4a');
    // A filename is what makes Starlette parse the part as an UploadFile.
    expect(audio.name).toBe('rec-1.m4a');
    expect(form.getAll('caption')).toEqual(['forgot to mention the toast']);
  });

  it('omits the caption field when none is given', async () => {
    const store = new MemoryStore();
    const { impl, calls } = fetchQueue(jsonResponse(200, REPLY));
    const client = makeClient(store, impl);

    await client.sendAudioMessage({ uri: 'file:///cache/rec-2.m4a' });

    const form = calls[0].init!.body as FormData;
    expect(form.getAll('audio')).toHaveLength(1);
    expect(form.getAll('caption')).toEqual([]);
  });

  it('shares the refresh-on-401 path with the rest of the client', async () => {
    const store = new MemoryStore();
    const { impl, calls } = fetchQueue(
      jsonResponse(401, { detail: 'expired' }),
      jsonResponse(200, {
        access_token: 'access-2',
        token_type: 'bearer',
        expires_in: 900,
        refresh_token: 'refresh-2',
      }),
      jsonResponse(200, REPLY),
    );
    const client = makeClient(store, impl);

    const res = await client.sendAudioMessage({ uri: 'file:///cache/rec-3.m4a' });

    expect(res.reply).toBe('Logged two eggs.');
    expect(calls.map((c) => c.url)).toEqual([
      'http://localhost:8000/api/v1/messages',
      'http://localhost:8000/api/v1/auth/refresh',
      'http://localhost:8000/api/v1/messages',
    ]);
    // The retried upload reuses the same FormData with the rotated bearer.
    const retryHeaders = calls[2].init!.headers as Record<string, string>;
    expect(retryHeaders.Authorization).toBe('Bearer access-2');
  });
});

describe('api/messages module', () => {
  it('sendMessage issues the JSON POST through the supplied request executor', async () => {
    const request = jest.fn(async (_path: string, _init: RequestInit) => REPLY);

    const res = await sendMessage(request, { text: 'supă de pui' });

    expect(request).toHaveBeenCalledWith('/api/v1/messages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ text: 'supă de pui' }),
    });
    expect(res).toBe(REPLY);
  });

  it('sendAudioMessage uploads multipart form data through the supplied executor', async () => {
    const request = jest.fn(async (_path: string, _init: RequestInit) => REPLY);

    await sendAudioMessage(request, { uri: 'file:///cache/rec.m4a', caption: '  lunch  ' });

    const [path, init] = request.mock.calls[0];
    expect(path).toBe('/api/v1/messages');
    expect(init.method).toBe('POST');
    const form = init.body as FormData;
    expect(form.getAll('audio')).toHaveLength(1);
    expect(form.getAll('caption')).toEqual(['lunch']);
  });
});

describe('userFacingMessage', () => {
  it('maps backend statuses to user-readable strings', async () => {
    const store = new MemoryStore();
    const { impl } = fetchQueue(
      jsonResponse(413, { detail: 'audio exceeds the 20 MB limit' }),
      jsonResponse(422, { detail: 'invalid message body' }),
      jsonResponse(429, { detail: 'rate limit exceeded' }),
      jsonResponse(502, { detail: 'the journal agent could not process this message' }),
    );
    const client = makeClient(store, impl);

    const messages: string[] = [];
    for (let i = 0; i < 4; i++) {
      try {
        await client.sendMessage({ text: 'ping' });
        messages.push('no error');
      } catch (err) {
        messages.push(userFacingMessage(err));
      }
    }

    expect(messages).toEqual([
      'That recording is too large — voice notes must stay under 20 MB.',
      'invalid message body',
      'Too many messages — wait a moment and try again.',
      'The assistant could not process that — please try again.',
    ]);
  });

  it('keeps ApiError details available and falls back for unknown errors', () => {
    const apiError = new ApiError(502, 'x');
    expect(userFacingMessage(apiError)).toContain('could not process');
    expect(userFacingMessage(new AuthError('Session expired.'))).toContain('session expired');
    expect(userFacingMessage(new TypeError('network down'))).toContain('Check your connection');
  });
});
