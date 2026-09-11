import { describe, expect, it } from "vitest";
import {
  analyticsLockedOnTimedSession,
  defaultAnalyticsIds,
  moveAnalyticsSlot,
  REPLAY_ONLY_HINT,
} from "@/lib/analyticsSlots";

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

  it("keeps race defaults on a live race and only sector times on FP/Q", () => {
    expect(defaultAnalyticsIds({ arisOn: false, sessionType: "R" })).toEqual([
      "tyredeg",
      "sectortimes",
      "gapchart",
    ]);
    expect(defaultAnalyticsIds({ arisOn: false, sessionType: "FP2" })).toEqual(["sectortimes"]);
    expect(defaultAnalyticsIds({ arisOn: false, sessionType: "Q" })).toEqual(["sectortimes"]);
  });
});

describe("analyticsLockedOnTimedSession", () => {
  it("locks race-distance charts on FP/Q and leaves them open on race", () => {
    expect(analyticsLockedOnTimedSession("gapchart", true)).toBe(true);
    expect(analyticsLockedOnTimedSession("tyredeg", true)).toBe(true);
    expect(analyticsLockedOnTimedSession("sectortimes", true)).toBe(false);
    expect(analyticsLockedOnTimedSession("weatheroverlay", true)).toBe(false);
    expect(analyticsLockedOnTimedSession("gapchart", false)).toBe(false);
    expect(REPLAY_ONLY_HINT).toBe("available on arisf1.tech/replay");
  });
});
