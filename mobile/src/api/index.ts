import { ApiClient, type ApiClientOptions } from './client';
import { API_BASE_URL } from './config';
import { SecureSessionStore } from '../auth/storage';

export const sessionStore = new SecureSessionStore();

/** Compose the real client against app config + SecureStore. */
export function createApiClient(options?: Partial<Omit<ApiClientOptions, 'baseUrl' | 'store'>>) {
  return new ApiClient({ baseUrl: API_BASE_URL, store: sessionStore, ...options });
}
