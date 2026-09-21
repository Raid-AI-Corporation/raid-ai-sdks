import type { ErrorEnvelope } from "./types.js";

/**
 * Every non-2xx response from the Raid AI API is surfaced as a `RaidApiError`.
 *
 * The API returns a `{ error: { code, message } }` envelope, but middleware,
 * controller catch-blocks, and proxies can each emit a slightly different shape
 * (`{ message }`, `{ error: "…" }`, or a raw string body). `.message` is unwrapped
 * from whichever shape came back; `.code` is the stable machine-readable code when
 * present (e.g. `IMAGE_FORENSICS:FILE_TOO_LARGE`, `api_key.scope_missing`).
 */
export class RaidApiError extends Error {
  readonly status: number;
  readonly code: string | undefined;
  readonly body: unknown;
  readonly requestId: string | undefined;

  constructor(status: number, message: string, opts: { code?: string; body?: unknown; requestId?: string } = {}) {
    super(message);
    this.name = "RaidApiError";
    this.status = status;
    this.code = opts.code;
    this.body = opts.body;
    this.requestId = opts.requestId;
  }

  /** True for 401/403 — the token is missing, invalid, or lacks the endpoint's scope. */
  get isAuth(): boolean {
    return this.status === 401 || this.status === 403;
  }

  /** True for 402 — a credit/quota/paywall limit (e.g. `USER_CREDIT_LIMIT_REACHED`). */
  get isPaymentRequired(): boolean {
    return this.status === 402;
  }

  /** True for 429 — rate limited. */
  get isRateLimited(): boolean {
    return this.status === 429;
  }
}

/** Raised when a `submitAndWait` poll loop exceeds its timeout before the job reaches a terminal state. */
export class RaidTimeoutError extends Error {
  readonly lastStatus: string | undefined;

  constructor(message: string, lastStatus?: string) {
    super(message);
    this.name = "RaidTimeoutError";
    this.lastStatus = lastStatus;
  }
}

/**
 * Pull a human-readable message out of any backend error body.
 *
 * Handles every error shape the API can return: `{ error: { code, message } }`,
 * `{ message }`, `{ error: "str" }`, `{ code }`, and a raw string body.
 */
export function extractError(body: unknown): { message?: string; code?: string } {
  if (typeof body === "string") {
    return { message: body || undefined };
  }
  if (body && typeof body === "object") {
    const b = body as {
      message?: unknown;
      code?: unknown;
      error?: unknown;
    };
    // { error: { code, message } }
    if (b.error && typeof b.error === "object") {
      const inner = b.error as ErrorEnvelope["error"];
      return {
        message: typeof inner.message === "string" ? inner.message : undefined,
        code: typeof inner.code === "string" ? inner.code : undefined,
      };
    }
    // { error: "string" }
    if (typeof b.error === "string") {
      return { message: b.error, code: typeof b.code === "string" ? b.code : undefined };
    }
    // { message, code }
    if (typeof b.message === "string") {
      return { message: b.message, code: typeof b.code === "string" ? b.code : undefined };
    }
    // { code } only
    if (typeof b.code === "string") {
      return { code: b.code };
    }
  }
  return {};
}
