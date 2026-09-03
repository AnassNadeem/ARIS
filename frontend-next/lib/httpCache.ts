/** In-memory HTTP cache with inflight dedup and optional localStorage. */

export const TTL_MS = {
  calendar: 60 * 60 * 1000,
  drivers: 60 * 60 * 1000,
  circuits: 7 * 24 * 60 * 60 * 1000,
  sessionCompleted: 24 * 60 * 60 * 1000,
  roundSessions: 60 * 60 * 1000,
} as const;

type CacheEntry<T> = { value: T; expiry: number };

const mem = new Map<string, CacheEntry<unknown>>();
const inflight = new Map<string, Promise<unknown>>();

const LS_PREFIX = "aris.http.v3.";

function lsGet(key: string): string | null {
  try {
    return globalThis.localStorage?.getItem(LS_PREFIX + key) ?? null;
  } catch {
    return null;
  }
}

function lsSet(key: string, value: string): void {
  try {
    globalThis.localStorage?.setItem(LS_PREFIX + key, value);
  } catch {
    /* quota / private mode */
  }
}

function readPersist<T>(key: string): CacheEntry<T> | null {
  const raw = lsGet(key);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as CacheEntry<T>;
    if (parsed && parsed.expiry > Date.now() && parsed.value !== undefined) return parsed;
  } catch {
    /* ignore */
  }
  return null;
}

function writePersist<T>(key: string, entry: CacheEntry<T>): void {
  lsSet(key, JSON.stringify(entry));
}

export function peekCache<T>(key: string): T | undefined {
  const hit = mem.get(key) as CacheEntry<T> | undefined;
  if (hit && hit.expiry > Date.now()) return hit.value;
  return undefined;
}

export function clearHttpCache(): void {
  mem.clear();
  inflight.clear();
}

/**
 * Return a cached value if fresh, otherwise run `fn`. Concurrent callers for
 * the same key share one in-flight promise. Null/undefined results are not stored.
 */
export function withCache<T>(
  key: string,
  ttlMs: number,
  fn: () => Promise<T | null>,
  persist = false,
): Promise<T | null> {
  const now = Date.now();
  const memHit = mem.get(key) as CacheEntry<T> | undefined;
  if (memHit && memHit.expiry > now) return Promise.resolve(memHit.value);
  if (persist) {
    const stored = readPersist<T>(key);
    if (stored && stored.expiry > now) {
      mem.set(key, stored);
      return Promise.resolve(stored.value);
    }
  }
  const pending = inflight.get(key);
  if (pending) return pending as Promise<T | null>;

  const run = fn()
    .then((value) => {
      inflight.delete(key);
      if (value != null && ttlMs > 0) {
        const entry: CacheEntry<T> = { value, expiry: Date.now() + ttlMs };
        mem.set(key, entry);
        if (persist) writePersist(key, entry);
      }
      return value;
    })
    .catch((err) => {
      inflight.delete(key);
      throw err;
    });
  inflight.set(key, run);
  return run;
}

/** Share one in-flight POST/GET even when the response should not be cached. */
export function dedupe<T>(key: string, fn: () => Promise<T>): Promise<T> {
  const pending = inflight.get(key);
  if (pending) return pending as Promise<T>;
  const run = fn().finally(() => {
    inflight.delete(key);
  });
  inflight.set(key, run);
  return run;
}
