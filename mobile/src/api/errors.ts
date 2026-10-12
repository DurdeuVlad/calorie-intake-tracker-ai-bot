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
