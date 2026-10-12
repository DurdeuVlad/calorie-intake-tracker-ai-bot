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
