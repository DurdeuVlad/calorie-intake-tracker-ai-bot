// Wire types for the FastAPI mobile surface (python-app/app/mobile/).
// Field names mirror the Pydantic schemas exactly.

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token: string;
}

export interface LinkStatusResponse {
  linkedProviders: string[];
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
}

// POST /api/v1/messages — JournalActionResult / MessageResponse.

export interface JournalActionEntry {
  id: number | null;
  calories: number | null;
  eaten_at: string | null;
  description: string | null;
}

export interface JournalActionResult {
  ok: boolean;
  type: string;
  entry: JournalActionEntry | null;
  date: string | null;
  message: string | null;
}

export interface MessageResponse {
  reply: string;
  actions: JournalActionResult[];
}

/**
 * Authenticated-request executor supplied by ApiClient — the api modules own
 * their endpoint's wire shape; the client owns bearer + refresh-on-401.
 */
export type AuthedRequest = <T>(path: string, init: RequestInit) => Promise<T>;

// GET/DELETE /api/v1/memories — CompanionMemoryItem / MemoryListResponse.

export interface CompanionMemoryItem {
  id: number;
  /** preference | restriction | goal | fact | other */
  kind: string;
  text: string;
  /** 'agent' | 'user' */
  source: string;
  created_at: string;
  updated_at: string;
}

export interface MemoryListResponse {
  memories: CompanionMemoryItem[];
}

// POST /api/v1/link/{issue,redeem} — LinkIssueResponse / LinkRedeemRequest.

export interface LinkIssueResponse {
  code: string;
  expiresAt: string;
}

export interface LinkRedeemRequest {
  code: string;
}

// /api/v1/devices — DeviceRegisterRequest / DeviceResponse / DeviceListResponse.

export interface DeviceRegisterInput {
  platform: 'ios' | 'android';
  push_token: string;
  app_version?: string | null;
  locale?: string | null;
}

export interface DeviceResponse {
  id: number;
  platform: string;
  app_version: string | null;
  locale: string | null;
  created_at: string;
  last_seen_at: string;
  disabled_at: string | null;
}

export interface DeviceListResponse {
  devices: DeviceResponse[];
}
