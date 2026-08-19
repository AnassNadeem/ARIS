import { type ZodType } from "zod";

const DEFAULT_TIMEOUT = 10_000;

export class ApiError extends Error {
  readonly status: number | null;
  readonly path: string;
  constructor(message: string, status: number | null, path: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.path = path;
  }
}

async function parseOrThrow<T>(res: Response, path: string, schema?: ZodType<T>): Promise<T> {
  const text = await res.text();
  if (!res.ok) {
    throw new ApiError(`${res.status} ${path}: ${text.slice(0, 240)}`, res.status, path);
  }
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    throw new ApiError(`Invalid JSON from ${path}`, res.status, path);
  }
  if (schema) {
    const parsed = schema.safeParse(data);
    if (!parsed.success) {
      console.error("Zod error", path, parsed.error.flatten());
      throw new ApiError(`Response validation failed for ${path}`, res.status, path);
    }
    return parsed.data;
  }
  return data as T;
}

export async function apiGet<T>(
  path: string,
  opts?: { timeout?: number; schema?: ZodType<T> },
): Promise<T> {
  const ctrl = new AbortController();
  const timeout = opts?.timeout ?? DEFAULT_TIMEOUT;
  const timer = setTimeout(() => ctrl.abort(), timeout);
  try {
    const res = await fetch(path, { signal: ctrl.signal });
    return await parseOrThrow(res, path, opts?.schema);
  } catch (err) {
    if (err instanceof ApiError) {
      console.error("API error", { path, status: err.status, message: err.message });
      throw err;
    }
    const aborted = err instanceof DOMException && err.name === "AbortError";
    const wrapped = new ApiError(
      aborted ? `Timeout (${timeout}ms) ${path}` : `Network error ${path}: ${String(err)}`,
      aborted ? 408 : null,
      path,
    );
    console.error("API error", { path, message: wrapped.message });
    throw wrapped;
  } finally {
    clearTimeout(timer);
  }
}

export async function apiPost<T>(
  path: string,
  body: unknown,
  opts?: { timeout?: number; schema?: ZodType<T> },
): Promise<T> {
  const ctrl = new AbortController();
  const timeout = opts?.timeout ?? DEFAULT_TIMEOUT;
  const timer = setTimeout(() => ctrl.abort(), timeout);
  try {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: ctrl.signal,
    });
    return await parseOrThrow(res, path, opts?.schema);
  } catch (err) {
    if (err instanceof ApiError) {
      console.error("API error", { path, status: err.status, message: err.message });
      throw err;
    }
    throw new ApiError(`Network error ${path}: ${String(err)}`, null, path);
  } finally {
    clearTimeout(timer);
  }
}

export function withAsOf(path: string, asOf: string | null): string {
  if (!asOf) return path;
  const join = path.includes("?") ? "&" : "?";
  return `${path}${join}as_of=${encodeURIComponent(asOf)}`;
}

export function asOfFromUrl(): string | null {
  const allow = import.meta.env.DEV || import.meta.env.VITE_ALLOW_ASOF === "1";
  if (!allow) return null;
  const q = new URLSearchParams(window.location.search);
  return q.get("asOf") || q.get("as_of");
}

export function replaySessionKeyFromUrl(): number | null {
  const allow = import.meta.env.DEV || import.meta.env.VITE_ALLOW_ASOF === "1";
  if (!allow) return null;
  const raw = new URLSearchParams(window.location.search).get("replay_session_key");
  if (!raw) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}
