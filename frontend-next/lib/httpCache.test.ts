import { afterEach, describe, expect, it } from "vitest";
import {
  CACHE_KEYS,
  TTL_MS,
  clearHttpCache,
  peekCache,
  withCache,
  withCacheSWR,
} from "./httpCache";

function installMemoryLocalStorage() {
  const store = new Map<string, string>();
  const ls = {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => {
      store.set(k, String(v));
    },
    removeItem: (k: string) => {
      store.delete(k);
    },
    clear: () => store.clear(),
    key: (i: number) => [...store.keys()][i] ?? null,
    get length() {
      return store.size;
    },
  };
  Object.defineProperty(globalThis, "localStorage", { value: ls, configurable: true });
}

afterEach(() => {
  clearHttpCache();
});

describe("httpCache SWR", () => {
  it("exposes the live-hub TTL and persist window", () => {
    expect(TTL_MS.liveHub).toBe(60_000);
    expect(TTL_MS.liveHubStale).toBe(60 * 60 * 1000);
    expect(TTL_MS.recentRaces).toBe(60 * 60 * 1000);
    expect(TTL_MS.standings).toBe(24 * 60 * 60 * 1000);
    expect(CACHE_KEYS.liveHub).toBe("GET:/api/live/hub");
  });

  it("peekCache returns a memory hit immediately, including after TTL expiry", async () => {
    await withCache("swr-mem", 1, async () => ({ n: 1 }), false);
    await new Promise((r) => setTimeout(r, 5));
    expect(peekCache("swr-mem", { persist: false })).toEqual({ n: 1 });
    const fresh = await withCache("swr-mem", 60_000, async () => ({ n: 2 }), false);
    expect(fresh).toEqual({ n: 2 });
  });

  it("peekCache hydrates from localStorage after memory is cleared", async () => {
    installMemoryLocalStorage();
    await withCache("swr-ls", 60_000, async () => ({ n: 7 }), true);
    clearHttpCache();
    expect(peekCache("swr-ls", { persist: true })).toEqual({ n: 7 });
  });

  it("withCacheSWR returns stale now and refreshes in the background", async () => {
    await withCache("swr-bg", 1, async () => ({ n: 1 }), false);
    await new Promise((r) => setTimeout(r, 5));
    let calls = 0;
    const first = withCacheSWR("swr-bg", 60_000, async () => {
      calls += 1;
      await new Promise((r) => setTimeout(r, 20));
      return { n: 2 };
    }, false);
    expect(await first).toEqual({ n: 1 });
    await new Promise((r) => setTimeout(r, 40));
    expect(calls).toBe(1);
    expect(peekCache("swr-bg", { persist: false })).toEqual({ n: 2 });
  });
});
