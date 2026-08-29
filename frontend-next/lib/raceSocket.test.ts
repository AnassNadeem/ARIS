import { afterEach, describe, expect, it, vi } from "vitest";
import { publicWsBase } from "./raceSocket";

describe("publicWsBase", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("uses NEXT_PUBLIC_WS_BASE when set", () => {
    vi.stubEnv("NEXT_PUBLIC_WS_BASE", "wss://aris.example.com");
    vi.stubEnv("NEXT_PUBLIC_API_BASE", "https://ignored.example.com");
    expect(publicWsBase()).toBe("wss://aris.example.com");
  });

  it("derives wss from NEXT_PUBLIC_API_BASE", () => {
    vi.stubEnv("NEXT_PUBLIC_WS_BASE", "");
    vi.stubEnv("NEXT_PUBLIC_API_BASE", "https://app.herokuapp.com");
    expect(publicWsBase()).toBe("wss://app.herokuapp.com");
  });

  it("does not default to localhost", () => {
    vi.stubEnv("NEXT_PUBLIC_WS_BASE", "");
    vi.stubEnv("NEXT_PUBLIC_API_BASE", "");
    expect(publicWsBase()).not.toContain("localhost");
    expect(publicWsBase()).not.toContain("8000");
  });
});
