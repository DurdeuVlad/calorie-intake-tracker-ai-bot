import Constants from 'expo-constants';

const DEFAULT_BASE_URL = 'http://localhost:8000';

const extra = (Constants.expoConfig?.extra ?? {}) as { apiBaseUrl?: unknown };

export const API_BASE_URL: string =
  typeof extra.apiBaseUrl === 'string' && extra.apiBaseUrl.length > 0
    ? extra.apiBaseUrl
    : DEFAULT_BASE_URL;
