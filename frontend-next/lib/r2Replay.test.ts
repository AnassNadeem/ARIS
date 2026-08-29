import { describe, expect, it } from "vitest";
import { annotateVsActivePlan, shouldFetchRecommend } from "./arisRecommend";
import { plansMatch, r2Configured, raceDurationS } from "./r2Replay";
import type { ARISRecommendation, GhostData, RaceField } from "./types";

function rec(over: Partial<ARISRecommendation> = {}): ARISRecommendation {
  return {
    id: "r1",
    lap: 24,
    rank: 1,
    label: "Pit lap 24 for HARD",
    action: { kind: "pit_lap", pit_lap: 24, pit_compound: "HARD" },
    delta_vs_stay_out_s: -2,
    mean_race_time_s: 0,
    confidence_std_s: 1,
    p10_delta_s: -2,
    p90_delta_s: -1,
    evidence: "x",
    narration_context: {},
    tactical: null,
    extrapolation_beyond_laps: 0,
    extrapolation_weight: 1,
    wet_heuristic: false,
    cql_q_delta: 0,
    rank_score: 0.7,
    ...over,
  };
}

describe("shouldFetchRecommend with active strategy", () => {
  it("skips independent lap-1 recommend when a plan is already selected", () => {
    expect(
      shouldFetchRecommend({
        isARISOn: true,
        playState: "racing",
        lap: 1,
        lastLap: null,
        tyreLife: 1,
        phase: "GREEN",
        lastPhase: null,
        hasActiveStrategy: true,
      }),
    ).toBe(false);
  });

  it("still fetches mid-race for re-evaluation", () => {
    expect(
      shouldFetchRecommend({
        isARISOn: true,
        playState: "racing",
        lap: 18,
        lastLap: 2,
        tyreLife: 17,
        phase: "GREEN",
        lastPhase: "GREEN",
        hasActiveStrategy: true,
      }),
    ).toBe(true);
  });
});

describe("annotateVsActivePlan", () => {
  it("keeps the selected stop when recommend agrees", () => {
    expect(annotateVsActivePlan(rec({ action: { kind: "pit_lap", pit_lap: 28, pit_compound: "HARD" } }), { pit_laps: [28] })).toMatch(
      /lap 28 stop is still optimal/i,
    );
  });

  it("suggests moving without replacing the plan", () => {
    expect(annotateVsActivePlan(rec(), { pit_laps: [28] })).toMatch(/Consider moving to lap 24/);
  });
});

describe("plansMatch", () => {
  const ghost: GhostData = {
    driver: "VER",
    strategy: { pit_laps: [20], compounds: ["HARD"], label: "top" },
    ticks: [],
    outcome: { aris_action: "PIT", real_action: "STAY_OUT", verdict: null },
  };
  it("matches selected pit laps to the R2 ghost plan", () => {
    expect(plansMatch({ id: "a", name: "x", pit_laps: [20], pit_compounds: ["HARD"], start_compound: "MEDIUM" }, ghost)).toBe(true);
    expect(plansMatch({ id: "a", name: "x", pit_laps: [18], pit_compounds: ["HARD"], start_compound: "MEDIUM" }, ghost)).toBe(false);
  });
});

describe("R2 fallback when NEXT_PUBLIC_R2_BASE_URL is unset", () => {
  it("reports unconfigured so ReplayFrameFeed uses Heroku pack-status", () => {
    expect(r2Configured()).toBe(false);
  });

  it("raceDurationS is the end of the last lap, not the start", () => {
    const field = {
      meta: {
        year: 2025,
        round: 15,
        session_type: "R",
        circuit_name: "Zandvoort",
        total_laps: 2,
        date_race: "2025-08-31",
        green_flag_s: 0,
        session_key: 1,
      },
      outline: { x: [], y: [] },
      drivers: [],
      laps: [
        { lap: 1, driver: "VER", position: 1, gap_to_leader_s: 0, gap_ahead_s: 0, compound: "MEDIUM", tyre_life: 1, stint_number: 1, pit_this_lap: false, is_dnf: false, is_dsq: false, track_status: "1", lap_time_s: 74 },
        { lap: 2, driver: "VER", position: 1, gap_to_leader_s: 0, gap_ahead_s: 0, compound: "MEDIUM", tyre_life: 2, stint_number: 1, pit_this_lap: false, is_dnf: false, is_dsq: false, track_status: "1", lap_time_s: 75 },
      ],
      stints: [],
      weather: [],
      race_control: [],
      pos_samples: {},
    } as RaceField;
    expect(raceDurationS(field)).toBe(149);
  });
});
