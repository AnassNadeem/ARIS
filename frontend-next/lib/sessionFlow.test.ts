import { describe, expect, it } from "vitest";
import {
  SESSION_OPTIONS,
  canStartRace,
  canToggleArisInConsole,
  circuitBadge,
  isArisCapableSession,
  nextSelectorStep,
  sessionAvailability,
  sessionLabel,
  sessionNeedsStrategyPick,
} from "./sessionFlow";

describe("isArisCapableSession", () => {
  it("allows Race and the FP2 live-wiring probe", () => {
    expect(isArisCapableSession("R")).toBe(true);
    expect(isArisCapableSession("FP2")).toBe(true);
    expect(isArisCapableSession("S")).toBe(false);
    expect(isArisCapableSession("Q")).toBe(false);
    expect(isArisCapableSession("FP1")).toBe(false);
    expect(isArisCapableSession("SQ")).toBe(false);
  });
});

describe("canToggleArisInConsole", () => {
  it("allows Race and FP2 in the console, including after a replay enter", () => {
    expect(canToggleArisInConsole("R")).toBe(true);
    expect(canToggleArisInConsole("FP2")).toBe(true);
    expect(canToggleArisInConsole("FP1")).toBe(false);
    expect(canToggleArisInConsole("Q")).toBe(false);
  });
});

describe("sessionNeedsStrategyPick", () => {
  it("is Race-only", () => {
    expect(sessionNeedsStrategyPick("R")).toBe(true);
    expect(sessionNeedsStrategyPick("FP2")).toBe(false);
  });
});

describe("sessionAvailability", () => {
  const race = SESSION_OPTIONS.find((o) => o.id === "R")!;

  it("blocks upcoming races", () => {
    expect(sessionAvailability(race, false, { R: "UPCOMING" }).enabled).toBe(false);
  });

  it("enables completed races", () => {
    expect(sessionAvailability(race, false, { R: "COMPLETED" }).enabled).toBe(true);
  });
});

describe("circuitBadge", () => {
  it("labels race weekends", () => {
    expect(circuitBadge({ isSprint: true }, "R")).toBe("RACE");
    expect(circuitBadge({ isSprint: false }, "R")).toBe("RACE");
  });
});

describe("sessionLabel", () => {
  it("maps backend codes to UI labels", () => {
    expect(sessionLabel("R")).toBe("Race");
    expect(sessionLabel("Q")).toBe("Quali");
    expect(sessionLabel("FP1")).toBe("FP1");
    expect(sessionLabel("FP2")).toBe("FP2");
    expect(sessionLabel("FP3")).toBe("FP3");
  });
});

describe("nextSelectorStep", () => {
  it("data-only skips driver and strategies", () => {
    expect(nextSelectorStep("circuit", "replay", { arisEnabled: false })).toBe("loading");
    expect(nextSelectorStep("circuit", "select", { arisEnabled: false })).toBe("loading");
  });

  it("ARIS walks circuit → driver → strategies → loading", () => {
    expect(nextSelectorStep("circuit", "select", { arisEnabled: true })).toBe("driver");
    expect(nextSelectorStep("driver", "lock")).toBe("strategies");
    expect(nextSelectorStep("strategies", "continue")).toBe("loading");
    expect(nextSelectorStep("driver", "back")).toBe("circuit");
  });
});

describe("canStartRace", () => {
  it("requires a chosen driver, fetched strategies, and a selected plan when ARIS is on", () => {
    expect(
      canStartRace({
        arisEnabled: true,
        selectedDriver: "VER",
        strategies: [{ id: "a" }],
        selectedStrategy: { id: "a" },
      }),
    ).toBe(true);
    expect(
      canStartRace({
        arisEnabled: true,
        selectedDriver: "VER",
        strategies: [{ id: "a" }],
        selectedStrategy: null,
      }),
    ).toBe(false);
    expect(canStartRace({ arisEnabled: false, selectedDriver: null, strategies: null, selectedStrategy: null })).toBe(
      true,
    );
  });
});
