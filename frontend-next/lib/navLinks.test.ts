import { describe, expect, it } from "vitest";
import { NAV_LINKS } from "@/lib/navLinks";

describe("production nav", () => {
  it("does not link to /test-replay", () => {
    expect(NAV_LINKS.map((l) => l.href)).toEqual(["/", "/live", "/replay", "/standings"]);
    expect(NAV_LINKS.some((l) => l.href.includes("test-replay"))).toBe(false);
  });
});
