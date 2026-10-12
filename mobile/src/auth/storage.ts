import * as Crypto from 'expo-crypto';
import * as SecureStore from 'expo-secure-store';

import type { AuthTokens } from '../api/types';

export interface StoredSession {
  email?: string;
  accessToken: string;
  refreshToken: string;
}

/**
 * Persistence port for the auth session. Tokens MUST live in expo-secure-store
 * (Keychain / EncryptedSharedPreferences) — never AsyncStorage.
 */
export interface SessionStore {
  /** Stable, device-bound identifier sent with every auth request. Survives sign-out. */
  getDeviceId(): Promise<string>;
  getSession(): Promise<StoredSession | null>;
  saveSession(session: StoredSession): Promise<void>;
  /** Merge rotated tokens into the stored session (keeps email + device id). */
  updateTokens(tokens: AuthTokens): Promise<void>;
  clearSession(): Promise<void>;
}

const SESSION_KEY = 'auth.session';
const DEVICE_ID_KEY = 'auth.device_id';

export class SecureSessionStore implements SessionStore {
  async getDeviceId(): Promise<string> {
    const existing = await SecureStore.getItemAsync(DEVICE_ID_KEY);
    if (existing) return existing;
    const id = await Crypto.randomUUID();
    await SecureStore.setItemAsync(DEVICE_ID_KEY, id);
    return id;
  }

  async getSession(): Promise<StoredSession | null> {
    const raw = await SecureStore.getItemAsync(SESSION_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as StoredSession;
    } catch {
      return null;
    }
  }

  async saveSession(session: StoredSession): Promise<void> {
    await SecureStore.setItemAsync(SESSION_KEY, JSON.stringify(session));
  }

  async updateTokens(tokens: AuthTokens): Promise<void> {
    const existing = (await this.getSession()) ?? {};
    await this.saveSession({ ...existing, ...tokens });
  }

  async clearSession(): Promise<void> {
    await SecureStore.deleteItemAsync(SESSION_KEY);
  }
}
