import { type ZodType } from "zod";
import { replayYears } from "../years";
import {
  calendarSchema,
  driversSchema,
  nextRaceSchema,
  roundSessionsSchema,
  type CalendarResponse,
  type NextRace,
  type RoundSessions,
} from "./types";

const DEFAULT_TIMEOUT = 60_000;

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

function publicApiBase(): string {
  const raw = String(import.meta.env.VITE_API_BASE_URL ?? "")
    .trim()
    .replace(/\/$/, "");
  if (!raw) return "";
  // A leftover frontend/.env must never ship localhost into the Cloudflare build.
  // The Worker proxies same-origin /api to the home tunnel.
  if (import.meta.env.PROD) {
    try {
      const host = new URL(raw).hostname;
      if (host === "127.0.0.1" || host === "localhost") return "";
    } catch {
      return "";
    }
  }
  return raw;
}

export const API_BASE = publicApiBase();

let inFlight = 0;
const trafficListeners = new Set<() => void>();

export function subscribeTraffic(cb: () => void): () => void {
  trafficListeners.add(cb);
  return () => {
    trafficListeners.delete(cb);
  };
}

export function inFlightCount(): number {
  return inFlight;
}

function beginTraffic() {
  inFlight += 1;
  trafficListeners.forEach((cb) => cb());
}

function endTraffic() {
  inFlight = Math.max(0, inFlight - 1);
  trafficListeners.forEach((cb) => cb());
}

export function apiUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  const base = String(API_BASE).replace(/\/$/, "");
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${base}${suffix}`;
}

const FIRST_LOAD_MSG = "This may take a moment on first load as data is being cached.";

type CacheEntry = { data: unknown; expiresAt: number };

const memory = new Map<string, CacheEntry>();
const inflight = new Map<string, Promise<unknown>>();
let reloadDepth = 0;

export type GetOpts<T> = { timeout?: number; schema?: ZodType<T>; cache?: number | false };

function pathTtlMs(path: string, override?: number | false): number {
  if (override === false) return 0;
  if (typeof override === "number") return override;
  const p = path.split("?")[0];
  if (p.includes("/api/live/status")) return 8_000;
  if (p.includes("/api/live/replay-ready") || p.includes("/api/live/session-key")) return 10 * 60_000;
  if (p.includes("/api/live/replay-path")) return 30 * 60_000;
  if (p.includes("/api/live/replay-frame")) return 2 * 60_000;
  if (p.includes("/api/live/")) return 0;
  if (p.includes("/api/aris/recommend")) return 0;
  if (p.includes("/api/circuit/") && (p.endsWith("/map") || p.endsWith("/preview"))) return 30 * 60_000;
  if (p.includes("/api/circuit/")) return 30 * 60_000;
  if (p.includes("/api/calendar/")) return 10 * 60_000;
  if (p.includes("/api/drivers/") || p.includes("/api/teams/")) return 10 * 60_000;
  if (p.includes("/api/standings/")) return 5 * 60_000;
  if (p.includes("/api/next-race")) return 15_000;
  if (p.includes("/api/aris/stats")) return 30 * 60_000;
  if (p.includes("/api/session/") || p.includes("/api/race/")) return 30 * 60_000;
  if (p.includes("/api/aris/")) return 5 * 60_000;
  return 60_000;
}

export function peekGet<T>(path: string): T | undefined {
  const hit = memory.get(path);
  if (!hit) return undefined;
  return hit.data as T;
}

export function withReload<T>(fn: () => Promise<T>): Promise<T> {
  reloadDepth += 1;
  return Promise.resolve()
    .then(fn)
    .finally(() => {
      reloadDepth -= 1;
    });
}

function remember<T>(path: string, data: T, ttl: number) {
  if (ttl <= 0) return;
  memory.set(path, { data, expiresAt: Date.now() + ttl });
}

export async function apiGet<T>(path: string, opts?: GetOpts<T>): Promise<T> {
  const ttl = pathTtlMs(path, opts?.cache);
  const skipCache = reloadDepth > 0 || opts?.cache === false;
  const hit = skipCache ? undefined : memory.get(path);
  const stale = hit?.data as T | undefined;
  const fresh = Boolean(hit && Date.now() <= hit.expiresAt);
  if (!skipCache && stale !== undefined && fresh) {
    if (opts?.schema) {
      const parsed = opts.schema.safeParse(stale);
      if (parsed.success) return parsed.data;
      memory.delete(path);
    } else {
      return stale;
    }
  }

  const existing = inflight.get(path);
  if (existing) {
    if (!skipCache && stale !== undefined) return stale;
    return existing as Promise<T>;
  }

  const promise = (async () => {
    const ctrl = new AbortController();
    const timeout = opts?.timeout ?? DEFAULT_TIMEOUT;
    const timer = setTimeout(() => ctrl.abort(), timeout);
    const url = apiUrl(path);
    beginTraffic();
    try {
      const res = await fetch(url, { signal: ctrl.signal });
      const data = await parseOrThrow(res, path, opts?.schema);
      remember(path, data, ttl);
      return data;
    } catch (err) {
      if (err instanceof ApiError) {
        throw err;
      }
      const aborted = err instanceof DOMException && err.name === "AbortError";
      throw new ApiError(
        aborted ? FIRST_LOAD_MSG : `Could not reach the ARIS backend. ${FIRST_LOAD_MSG}`,
        aborted ? 408 : null,
        path,
      );
    } finally {
      endTraffic();
      clearTimeout(timer);
      inflight.delete(path);
    }
  })();

  inflight.set(path, promise);
  if (!skipCache && stale !== undefined) return stale;
  return promise;
}

export async function apiPost<T>(
  path: string,
  body: unknown,
  opts?: { timeout?: number; schema?: ZodType<T> },
): Promise<T> {
  const ctrl = new AbortController();
  const timeout = opts?.timeout ?? DEFAULT_TIMEOUT;
  const timer = setTimeout(() => ctrl.abort(), timeout);
  const url = apiUrl(path);
  beginTraffic();
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: ctrl.signal,
    });
    return await parseOrThrow(res, path, opts?.schema);
  } catch (err) {
    if (err instanceof ApiError) {
      throw err;
    }
    throw new ApiError(`Could not reach the ARIS backend. ${FIRST_LOAD_MSG}`, null, path);
  } finally {
    endTraffic();
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

function swallow(p: Promise<unknown>) {
  void p.catch(() => undefined);
}

export async function warmReplaySession(year: number, round: number, sessionType: string): Promise<void> {
  const meta = await apiGet<{ session_key: number; date_start?: string | null; green_flag_s?: number | null }>(
    `/api/live/session-key?year=${year}&round_number=${round}&session_type=${sessionType}`,
    { timeout: 60_000 },
  );
  if (meta.session_key == null) return;
  const ready = await apiGet<{ date_start?: string | null; green_flag_s?: number | null }>(
    `/api/live/replay-ready?session_key=${meta.session_key}&year=${year}&round_number=${round}`,
    { timeout: 180_000 },
  ).catch(() => null);
  swallow(apiGet(`/api/live/replay-path?session_key=${meta.session_key}&year=${year}&round_number=${round}&src=fastf1`));
  const startIso = ready?.date_start || meta.date_start;
  const startMs = startIso ? Date.parse(startIso) : Number.NaN;
  const offset = Number(ready?.green_flag_s ?? meta.green_flag_s ?? 0);
  const asOf =
    Number.isFinite(startMs) && offset > 0
      ? new Date(startMs + offset * 1000).toISOString()
      : startIso || new Date().toISOString();
  await apiGet(
    `/api/live/replay-frame?session_key=${meta.session_key}&as_of=${encodeURIComponent(asOf)}&year=${year}&round_number=${round}`,
    { timeout: 90_000 },
  );
}

async function warmWeekend(year: number, round: number) {
  swallow(apiGet(`/api/circuit/${year}/${round}/map`));
  swallow(apiGet(`/api/circuit/${year}/${round}/preview`));
  const weekend = await apiGet<RoundSessions>(`/api/calendar/${year}/${round}/sessions`, {
    schema: roundSessionsSchema,
    timeout: 30_000,
  }).catch(() => null);
  const list = weekend?.sessions ?? [];
  for (const sess of list) {
    if (sess.status !== "COMPLETED") continue;
    try {
      await warmReplaySession(year, round, sess.session_type);
    } catch {
      /* keep going — later sessions still help */
    }
  }
}

/** Kick off catalog + weekend packs in pieces so replay/standings are already warm. */
export function prefetchAppData() {
  const asOf = asOfFromUrl();
  swallow(apiGet(withAsOf("/api/live/status", asOf)));
  swallow(apiGet("/api/aris/stats"));
  swallow(
    apiGet<NextRace>(withAsOf("/api/next-race", asOf), { schema: nextRaceSchema }).then((nxt) => {
      swallow(apiGet(withAsOf(`/api/calendar/${nxt.year}`, asOf), { schema: calendarSchema }));
      swallow(apiGet(`/api/standings/drivers/${nxt.year}`));
      swallow(apiGet(`/api/drivers/${nxt.year}`, { schema: driversSchema }));
      if (nxt.round_number) void warmWeekend(nxt.year, nxt.round_number);
    }),
  );
  void (async () => {
    for (const year of replayYears()) {
      await new Promise((r) => window.setTimeout(r, 120));
      swallow(apiGet(withAsOf(`/api/calendar/${year}`, asOf), { schema: calendarSchema }));
      swallow(apiGet(`/api/standings/drivers/${year}`));
      swallow(apiGet(`/api/standings/constructors/${year}`));
      if (year >= 2024) swallow(apiGet(`/api/drivers/${year}`, { schema: driversSchema }));
    }
  })();
}
