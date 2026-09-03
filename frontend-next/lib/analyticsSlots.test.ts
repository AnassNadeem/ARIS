import { describe, expect, it } from "vitest";
import { defaultAnalyticsIds, moveAnalyticsSlot } from "@/lib/analyticsSlots";

describe("moveAnalyticsSlot", () => {
  it("moves a panel up and down", () => {
    expect(moveAnalyticsSlot(["a", "b", "c"], "c", -1)).toEqual(["a", "c", "b"]);
    expect(moveAnalyticsSlot(["a", "b", "c"], "a", 1)).toEqual(["b", "a", "c"]);
  });

  it("is a no-op at the ends", () => {
    const ids = ["a", "b", "c"];
    expect(moveAnalyticsSlot(ids, "a", -1)).toBe(ids);
    expect(moveAnalyticsSlot(ids, "c", 1)).toBe(ids);
  });
});

describe("defaultAnalyticsIds", () => {
  it("puts Ghost Δ first when ARIS is on", () => {
    expect(defaultAnalyticsIds({ arisOn: true })[0]).toBe("ghostdelta");
    expect(defaultAnalyticsIds({ arisOn: true })).not.toContain("explain");
    expect(defaultAnalyticsIds({ arisOn: false })).not.toContain("ghostdelta");
  });
});
