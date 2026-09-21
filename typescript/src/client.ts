import { RaidApiError, extractError } from "./errors.js";
import { Images } from "./resources/images.js";
import { Audio } from "./resources/audio.js";
import { Video } from "./resources/video.js";
import { Documents } from "./resources/documents.js";
import { FactChecking } from "./resources/factChecking.js";
import type { BinaryResponse } from "./types.js";

/** Minimal `fetch` signature the SDK depends on — the global `fetch` satisfies it. */
export type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

export interface RaidClientOptions {
  /** Your developer token. Keep it server-side; never ship it in client code. */
  apiKey: string;
  /** The Raid AI API base URL. Defaults to the production API; override to target another tier. */
  baseUrl?: string;
  /** Per-request timeout in milliseconds (default 60_000). Raise it for large uploads. */
  timeoutMs?: number;
  /** Number of automatic retries for 429 / 5xx responses and transport errors (default 2). */
  maxRetries?: number;
  /**
   * How to present the token. `"bearer"` (default) sends `Authorization: Bearer <token>`;
   * `"x-api-key"` sends `X-Api-Key: <token>`. Both are accepted by the API.
   */
  authHeader?: "bearer" | "x-api-key";
  /** Inject a `fetch` implementation (e.g. `node-fetch`) when the global one is unavailable. */
  fetch?: FetchLike;
}

export interface RequestOptions {
  method: string;
  path: string;
  /** JSON body — serialized and sent with `Content-Type: application/json`. */
  json?: unknown;
  /** Multipart body — sent as-is (do not also set `json`). */
  form?: FormData;
  /** Query-string params; `undefined`/`null` values are dropped. */
  query?: Record<string, string | number | boolean | undefined | null>;
  /** Override the client timeout for this call. */
  timeoutMs?: number;
  /**
   * Expect raw bytes rather than JSON (the document page-image / evidence rasters).
   * Resolves to a `BinaryResponse`; a non-2xx still maps to a `RaidApiError` with the
   * JSON error body decoded, so error handling is identical to a JSON call.
   */
  binary?: boolean;
}

const DEFAULT_TIMEOUT_MS = 60_000;
const DEFAULT_MAX_RETRIES = 2;
const DEFAULT_BASE_URL = "https://api.raidxai.com";

/**
 * Client for the Raid AI detection API.
 *
 * ```ts
 * const raid = new RaidClient({
 *   apiKey: process.env.RAID_API_KEY!,
 * });
 * const res = await raid.images.process([{ data: bytes, fileName: "photo.jpg" }]);
 * console.log(res.images[0]?.verdict);
 * ```
 */
export class RaidClient {
  readonly images: Images;
  readonly audio: Audio;
  readonly video: Video;
  readonly documents: Documents;
  readonly factChecking: FactChecking;

  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly timeoutMs: number;
  private readonly maxRetries: number;
  private readonly authHeader: "bearer" | "x-api-key";
  private readonly fetchImpl: FetchLike;

  constructor(options: RaidClientOptions) {
    if (!options?.apiKey) {
      throw new Error("RaidClient: `apiKey` is required (your developer token).");
    }
    this.apiKey = options.apiKey;
    this.baseUrl = (options.baseUrl ?? DEFAULT_BASE_URL).replace(/\/+$/, "");
    this.timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    this.maxRetries = options.maxRetries ?? DEFAULT_MAX_RETRIES;
    this.authHeader = options.authHeader ?? "bearer";

    const f = options.fetch ?? (globalThis.fetch as FetchLike | undefined);
    if (!f) {
      throw new Error(
        "RaidClient: no global `fetch` found. Pass a `fetch` implementation via options.fetch (Node < 18).",
      );
    }
    this.fetchImpl = f;

    this.images = new Images(this);
    this.audio = new Audio(this);
    this.video = new Video(this);
    this.documents = new Documents(this);
    this.factChecking = new FactChecking(this);
  }

  /**
   * Perform a request with auth, retries, timeout, and typed error mapping.
   * Retries 429 / ≥500 / transport errors with exponential backoff (0.5·2ⁿ s);
   * fails fast on other 4xx (401/403/400 won't self-heal).
   */
  async request<T>(opts: RequestOptions): Promise<T> {
    const url = this.buildUrl(opts.path, opts.query);
    // A binary endpoint still answers errors as JSON, so accept both rather than
    // narrowing to one image type.
    const headers: Record<string, string> = {
      Accept: opts.binary ? "*/*" : "application/json",
    };
    if (this.authHeader === "x-api-key") {
      headers["X-Api-Key"] = this.apiKey;
    } else {
      headers["Authorization"] = `Bearer ${this.apiKey}`;
    }

    let body: BodyInit | undefined;
    if (opts.form) {
      body = opts.form; // fetch sets the multipart boundary Content-Type automatically
    } else if (opts.json !== undefined) {
      body = JSON.stringify(opts.json);
      headers["Content-Type"] = "application/json";
    }

    const timeoutMs = opts.timeoutMs ?? this.timeoutMs;
    const attempts = this.maxRetries + 1;
    let lastError: unknown;

    for (let attempt = 1; attempt <= attempts; attempt++) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);
      let res: Response;
      let text: string;
      let bytes: ArrayBuffer | undefined;
      try {
        res = await this.fetchImpl(url, {
          method: opts.method,
          headers,
          body,
          signal: controller.signal,
        });
        // Read the body inside the try so the timeout covers the FULL request — a
        // response that sends headers then stalls its body triggers the abort here
        // rather than hanging forever.
        if (opts.binary && res.status !== 204) {
          bytes = await res.arrayBuffer();
          // Only a failure carries a (JSON) message worth decoding; decoding a raster
          // would allocate a second copy of the image for nothing.
          text = res.ok ? "" : new TextDecoder().decode(bytes);
        } else {
          text = res.status === 204 ? "" : await res.text();
        }
      } catch (err) {
        // Transport error, or a timeout abort during connect / headers / body read — retryable.
        lastError = err;
        if (attempt < attempts) {
          await sleep(backoffMs(attempt));
          continue;
        }
        throw new RaidApiError(0, `Request to ${opts.path} failed: ${errMessage(err)}`, { body: err });
      } finally {
        clearTimeout(timer);
      }

      // Retry transient server-side conditions; everything else resolves now.
      if ((res.status === 429 || res.status >= 500) && attempt < attempts) {
        lastError = res;
        await sleep(retryAfterMs(res) ?? backoffMs(attempt));
        continue;
      }

      return this.parseBody<T>(res, text, bytes);
    }

    // Unreachable in practice (the loop returns or throws), but keeps the type checker happy.
    throw new RaidApiError(0, `Request to ${opts.path} failed after ${attempts} attempts`, { body: lastError });
  }

  /** Parse an already-read response body (no I/O) into `T`, or throw a mapped `RaidApiError`. */
  private parseBody<T>(res: Response, text: string, bytes?: ArrayBuffer): T {
    const requestId = res.headers.get("request-id") ?? res.headers.get("x-request-id") ?? undefined;

    if (res.status === 204) {
      return undefined as T;
    }

    if (bytes !== undefined && res.ok) {
      const binary: BinaryResponse = {
        data: new Uint8Array(bytes),
        contentType: res.headers.get("content-type") ?? "application/octet-stream",
      };
      return binary as T;
    }

    let parsed: unknown = text;
    const contentType = res.headers.get("content-type") ?? "";
    if (contentType.includes("application/json") && text) {
      try {
        parsed = JSON.parse(text);
      } catch {
        parsed = text;
      }
    }

    if (!res.ok) {
      const { message, code } = extractError(parsed);
      throw new RaidApiError(res.status, message ?? `API error ${res.status}: ${res.statusText}`, {
        code,
        body: parsed,
        requestId,
      });
    }

    return parsed as T;
  }

  private buildUrl(path: string, query?: RequestOptions["query"]): string {
    let url = `${this.baseUrl}${path.startsWith("/") ? path : `/${path}`}`;
    if (query) {
      const qs = new URLSearchParams();
      for (const [key, value] of Object.entries(query)) {
        if (value !== undefined && value !== null) {
          qs.append(key, String(value));
        }
      }
      const s = qs.toString();
      if (s) url += `?${s}`;
    }
    return url;
  }
}

function backoffMs(attempt: number): number {
  // 0.5s, 1s, 2s, … (attempt is 1-based)
  return 500 * 2 ** (attempt - 1);
}

function retryAfterMs(res: Response): number | undefined {
  const header = res.headers.get("retry-after");
  if (!header) return undefined;
  const seconds = Number(header);
  if (Number.isFinite(seconds)) return seconds * 1000;
  const date = Date.parse(header);
  if (Number.isFinite(date)) return Math.max(0, date - Date.now());
  return undefined;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function errMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}
