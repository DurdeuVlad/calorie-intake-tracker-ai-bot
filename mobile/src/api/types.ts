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
