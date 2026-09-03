export class ApiError extends Error {
  status: number;
  code?: string;
  detail?: string;

  constructor(status: number, detail?: string, code?: string) {
    super(detail ?? `HTTP ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.code = code;
  }
}

export interface ApiOpts {
  method?: string;
  body?: unknown;
  token?: string | null;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  /**
   * When true, a successful (2xx) response body is resolved verbatim via
   * `res.text()` and returned as `T` instead of being `JSON.parse`d. Needed for
   * endpoints that return non-JSON (e.g. the `text/html` audit export). The
   * error path (non-2xx) is unaffected.
   */
  raw?: boolean;
  /**
   * Internal: set by the auth layer on the `/auth/refresh` request itself so a
   * 401 from that call doesn't recurse back into a refresh.
   */
  skipRefresh?: boolean;
}

/**
 * A handler the auth layer registers so a 401 can trigger a single silent
 * refresh. It returns a fresh access token on success, or null to give up
 * (which the auth layer pairs with a logout + redirect).
 */
type RefreshHandler = () => Promise<string | null>;

let refreshHandler: RefreshHandler | null = null;
// A single in-flight refresh shared by every request that 401s while it runs,
// so a burst of concurrent 401s triggers exactly one `/auth/refresh` call and
// they all retry with its result.
let inFlightRefresh: Promise<string | null> | null = null;

export function setRefreshHandler(fn: RefreshHandler | null): void {
  refreshHandler = fn;
}

function runRefresh(): Promise<string | null> {
  if (!inFlightRefresh) {
    inFlightRefresh = (refreshHandler as RefreshHandler)().finally(() => {
      inFlightRefresh = null;
    });
  }
  return inFlightRefresh;
}

function apiBase(): string {
  return import.meta.env.VITE_API_BASE ?? "/api/v1";
}

export async function apiFetch<T = unknown>(path: string, opts: ApiOpts = {}): Promise<T> {
  const url = /^https?:/i.test(path) ? path : `${apiBase()}${path}`;

  const run = (token?: string | null): Promise<Response> => {
    const headers: Record<string, string> = { ...(opts.headers ?? {}) };
    if (token) headers.Authorization = `Bearer ${token}`;
    let body: string | undefined;
    if (opts.body !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(opts.body);
    }
    const method = opts.method ?? (opts.body !== undefined ? "POST" : "GET");
    return fetch(url, { method, headers, body, signal: opts.signal });
  };

  let res = await run(opts.token);

  if (res.status === 401 && refreshHandler && !opts.skipRefresh) {
    const fresh = await runRefresh();
    if (fresh) res = await run(fresh);
  }

  if (!res.ok) {
    let detail: string | undefined;
    const raw = await res.text().catch(() => "");
    if (raw) {
      try {
        const parsed = JSON.parse(raw) as { detail?: unknown; code?: unknown };
        if (typeof parsed.detail === "string") {
          detail = parsed.detail;
        } else if (Array.isArray(parsed.detail)) {
          // FastAPI 422: [{ loc, msg, type }, …] — surface the messages, not JSON.
          const msgs = parsed.detail
            .map((e) => (e && typeof (e as { msg?: unknown }).msg === "string" ? (e as { msg: string }).msg : null))
            .filter((m): m is string => m !== null);
          detail = msgs.length ? msgs.join("; ") : raw;
        } else {
          detail = raw;
        }
        throw new ApiError(
          res.status,
          detail,
          typeof parsed.code === "string" ? parsed.code : undefined,
        );
      } catch (err) {
        if (err instanceof ApiError) throw err;
        detail = raw;
      }
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  const text = await res.text();
  if (opts.raw) return text as T;
  return (text ? JSON.parse(text) : undefined) as T;
}
