import { describe, expect, it } from "vitest";
import { autoDecisionStatement, buildStintPlan, currentStintIndex } from "@/lib/arisRecommend";
import type { ARISRecommendation, StratPlan } from "@/lib/types";

function plan(overrides: Partial<StratPlan> = {}): StratPlan {
  return {
    id: "p1",
    name: "Plan A",
    pit_laps: [20],
    pit_compounds: ["HARD"],
    start_compound: "MEDIUM",
    ...overrides,
  };
}

function rec(overrides: Partial<ARISRecommendation> = {}): ARISRecommendation {
  return {
    id: "r1",
    lap: 20,
    rank: 1,
    label: "Pit lap 20 for HARD",
    action: { kind: "pit_lap", pit_lap: 20, pit_compound: "HARD" },
    delta_vs_stay_out_s: 3.2,
    mean_race_time_s: 0,
    confidence_std_s: 1.1,
    p10_delta_s: 1,
    p90_delta_s: 5,
    evidence: "evidence",
    narration_context: {},
    tactical: null,
    extrapolation_beyond_laps: 0,
    extrapolation_weight: 1,
    wet_heuristic: false,
    cql_q_delta: 0,
    rank_score: 0.8,
    ...overrides,
  };
}

describe("buildStintPlan", () => {
  it("returns a single open stint for a plan with no pits", () => {
    const segs = buildStintPlan(plan({ pit_laps: [], pit_compounds: [] }), 50);
    expect(segs).toEqual([{ index: 0, compound: "MEDIUM", startLap: 1, endLap: 50 }]);
  });

  it("splits stints at each pit lap and carries compounds forward", () => {
    const segs = buildStintPlan(
      plan({ pit_laps: [15, 35], pit_compounds: ["HARD", "SOFT"], start_compound: "MEDIUM" }),
      52,
    );
    expect(segs).toEqual([
      { index: 0, compound: "MEDIUM", startLap: 1, endLap: 15 },
      { index: 1, compound: "HARD", startLap: 16, endLap: 35 },
      { index: 2, compound: "SOFT", startLap: 36, endLap: 52 },
    ]);
  });

  it("returns an empty list for a null plan", () => {
    expect(buildStintPlan(null, 50)).toEqual([]);
  });
});

describe("currentStintIndex", () => {
  const segs = buildStintPlan(plan({ pit_laps: [15, 35], pit_compounds: ["HARD", "SOFT"] }), 52);

  it("picks the stint containing the current lap", () => {
    expect(currentStintIndex(segs, 1)).toBe(0);
    expect(currentStintIndex(segs, 16)).toBe(1);
    expect(currentStintIndex(segs, 40)).toBe(2);
  });
});

describe("autoDecisionStatement", () => {
  it("tells the user during a red flag rather than asking", () => {
    const { text, kind } = autoDecisionStatement(rec(), { phase: "RED_FLAG" });
    expect(kind).toBe("red_flag_reset");
    expect(text).toMatch(/RED FLAG/);
    expect(text).not.toMatch(/\?/);
  });

  it("labels an SC pit call as an SC window decision", () => {
    const { text, kind } = autoDecisionStatement(rec(), { phase: "SC" });
    expect(kind).toBe("sc_window");
    expect(text).toMatch(/SC WINDOW/);
  });

  it("labels a wet-heuristic call by current rainfall state", () => {
    const wet = rec({ wet_heuristic: true, action: { kind: "pit_now", pit_compound: "INTERMEDIATE" } });
    expect(autoDecisionStatement(wet, { phase: "GREEN", rainfall: true }).text).toMatch(/RAIN DETECTED/);
    expect(autoDecisionStatement(wet, { phase: "GREEN", rainfall: false }).text).toMatch(/TRACK DRYING/);
  });

  it("falls back to a plain declarative strategy statement", () => {
    const { text, kind } = autoDecisionStatement(rec(), { phase: "GREEN" });
    expect(kind).toBe("strategy_change");
    expect(text).toMatch(/ARIS is pitting on lap 20 for HARD/);
    expect(text).not.toMatch(/\?/);
  });
});
