import { File } from 'expo-file-system';

import type { SessionStore } from '../auth/storage';
import { ApiError, AuthError } from './errors';
import type {
  AuthTokens,
  LinkStatusResponse,
  MessageResponse,
  TokenResponse,
} from './types';

/** Minimal fetch surface the client needs — keeps tests free of real Response objects. */
export interface FetchResponse {
  ok: boolean;
  status: number;
  json(): Promise<unknown>;
}

export type FetchLike = (url: string, init?: RequestInit) => Promise<FetchResponse>;

export interface ApiClientOptions {
  baseUrl: string;
  store: SessionStore;
  fetchImpl?: FetchLike;
  /** Called once when the session is unrecoverably expired (refresh or retry 401). */
  onSessionExpired?: () => void;
}

export interface AudioMessageInput {
  /** Local URI of the recording (expo-audio `recorder.uri`). */
  uri: string;
  /** Becomes the multipart part's Content-Type; falls back to the file's own type. */
  mimeType?: string;
  /** Optional note the backend appends to the transcript, like a Telegram caption. */
  caption?: string;
}

const JSON_HEADERS = {
  'Content-Type': 'application/json',
  Accept: 'application/json',
};

async function extractDetail(res: FetchResponse): Promise<string | undefined> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    // FastAPI sends detail as a string (HTTPException) or a list of validation errors (422).
    if (typeof body.detail === 'string') return body.detail;
    if (Array.isArray(body.detail) && body.detail.length > 0) {
      const first = body.detail[0] as { msg?: unknown };
      if (typeof first.msg === 'string') return first.msg;
    }
  } catch {
    // Non-JSON error body — fall through to the generic message.
  }
  return undefined;
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly store: SessionStore;
  private readonly fetchImpl: FetchLike;
  private readonly onSessionExpired?: () => void;
  private refreshInFlight: Promise<AuthTokens> | null = null;

  constructor(options: ApiClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, '');
    this.store = options.store;
    this.fetchImpl = options.fetchImpl ?? (fetch as unknown as FetchLike);
    this.onSessionExpired = options.onSessionExpired;
  }

  async login(email: string, password: string): Promise<void> {
    const deviceId = await this.store.getDeviceId();
    const res = await this.post<TokenResponse>('/api/v1/auth/login', {
      email,
      password,
      device_id: deviceId,
    });
    await this.store.saveSession({
      email,
      accessToken: res.access_token,
      refreshToken: res.refresh_token,
    });
  }

  async signup(email: string, password: string): Promise<void> {
    const deviceId = await this.store.getDeviceId();
    const res = await this.post<TokenResponse>('/api/v1/auth/signup', {
      email,
      password,
      device_id: deviceId,
    });
    await this.store.saveSession({
      email,
      accessToken: res.access_token,
      refreshToken: res.refresh_token,
    });
  }

  async getLinkStatus(): Promise<LinkStatusResponse> {
    return this.authedRequest<LinkStatusResponse>('/api/v1/link/status', { method: 'GET' });
  }

  /** Typed meal logging — POST /api/v1/messages as JSON {text}. */
  async sendMessage(text: string): Promise<MessageResponse> {
    return this.authedRequest<MessageResponse>('/api/v1/messages', {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({ text }),
    });
  }

  /**
   * Voice note meal logging — POST /api/v1/messages as multipart with the
   * recording in the `audio` field (plus optional `caption`). Serialized by
   * the Expo fetch runtime installed as the global fetch; RN's stock fetch
   * cannot send File/Blob form parts.
   */
  async sendAudioMessage({ uri, mimeType, caption }: AudioMessageInput): Promise<MessageResponse> {
    const file = new File(uri);
    const audio = new Blob([await file.arrayBuffer()], {
      type: mimeType || file.type || 'audio/m4a',
    });
    const filename = file.name || 'voice.m4a';
    // `name` also becomes the part filename on the stock RN FormData path,
    // which ignores the third append argument but reads a `name` property.
    (audio as Blob & { name?: string }).name = filename;

    const form = new FormData();
    form.append('audio', audio, filename);
    const trimmedCaption = caption?.trim();
    if (trimmedCaption) form.append('caption', trimmedCaption);

    return this.authedRequest<MessageResponse>('/api/v1/messages', {
      method: 'POST',
      body: form,
    });
  }

  async signOut(): Promise<void> {
    await this.store.clearSession();
  }

  private async post<T>(path: string, body: unknown): Promise<T> {
    const res = await this.fetchImpl(this.baseUrl + path, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    });
    return this.unwrap<T>(res);
  }

  /**
   * GET/POST an authenticated endpoint. On a 401 the refresh token is exchanged
   * once and the request retried once — a second 401 ends the session. No loop:
   * the retry path never triggers another refresh.
   */
  private async authedRequest<T>(path: string, init: RequestInit): Promise<T> {
    const session = await this.store.getSession();
    if (!session) throw new AuthError('Not signed in.');

    const res = await this.fetchImpl(this.baseUrl + path, this.withBearer(init, session.accessToken));
    if (res.status !== 401) return this.unwrap<T>(res);

    const tokens = await this.refreshTokens(session.refreshToken);
    const retry = await this.fetchImpl(this.baseUrl + path, this.withBearer(init, tokens.accessToken));
    if (retry.status === 401) {
      await this.expire();
      throw new AuthError('Session expired. Please sign in again.');
    }
    return this.unwrap<T>(retry);
  }

  /** Concurrent 401s share one /refresh call so a rotation is never raced. */
  private async refreshTokens(refreshToken: string): Promise<AuthTokens> {
    if (!this.refreshInFlight) {
      this.refreshInFlight = this.doRefresh(refreshToken).finally(() => {
        this.refreshInFlight = null;
      });
    }
    return this.refreshInFlight;
  }

  private async doRefresh(refreshToken: string): Promise<AuthTokens> {
    const deviceId = await this.store.getDeviceId();
    try {
      const res = await this.post<TokenResponse>('/api/v1/auth/refresh', {
        refresh_token: refreshToken,
        device_id: deviceId,
      });
      const tokens: AuthTokens = {
        accessToken: res.access_token,
        refreshToken: res.refresh_token,
      };
      await this.store.updateTokens(tokens);
      return tokens;
    } catch (err) {
      if (err instanceof AuthError) await this.expire();
      throw err;
    }
  }

  private async expire(): Promise<void> {
    await this.store.clearSession();
    this.onSessionExpired?.();
  }

  private withBearer(init: RequestInit, accessToken: string): RequestInit {
    return {
      ...init,
      headers: { ...(init.headers ?? {}), Authorization: `Bearer ${accessToken}` },
    };
  }

  private async unwrap<T>(res: FetchResponse): Promise<T> {
    if (res.ok) return (await res.json()) as T;
    const detail = await extractDetail(res);
    if (res.status === 401) throw new AuthError(detail ?? 'Unauthorized', detail);
    throw new ApiError(res.status, detail ?? `Request failed (${res.status})`, detail);
  }
}
