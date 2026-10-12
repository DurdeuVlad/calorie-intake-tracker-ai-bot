export class ApiError extends Error {
  readonly status: number;
  /** Server-provided `detail`, when FastAPI sent one. */
  readonly detail: string | undefined;

  constructor(status: number, message: string, detail?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

/** Any 401 — bad credentials on login, or an expired session elsewhere. */
export class AuthError extends ApiError {
  constructor(message: string, detail?: string) {
    super(401, message, detail);
    this.name = 'AuthError';
  }
}

/**
 * Maps an error thrown by ApiClient to a string the user can act on.
 * Status codes mirror python-app/app/mobile/messages.py.
 */
export function userFacingMessage(error: unknown): string {
  if (error instanceof AuthError) {
    return 'Your session expired. Please sign in again.';
  }
  if (error instanceof ApiError) {
    switch (error.status) {
      case 413:
        return 'That recording is too large — voice notes must stay under 20 MB.';
      case 415:
        return 'Unsupported message format.';
      case 422:
        return error.detail ?? 'That message could not be read — please try again.';
      case 429:
        return 'Too many messages — wait a moment and try again.';
      case 502:
        return 'The assistant could not process that — please try again.';
      case 503:
        return 'Voice transcription is unavailable right now — try typing instead.';
      default:
        return error.detail ?? `Something went wrong (${error.status}).`;
    }
  }
  return 'Could not reach the server. Check your connection and try again.';
}
