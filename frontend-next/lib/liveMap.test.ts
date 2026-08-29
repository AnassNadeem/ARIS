import { describe, expect, it } from "vitest";
import { filterReplayRounds, replayYears, defaultReplayYear, startFinishMarker, isReplayableRound, chequeredSfFlag } from "./replayFilter";
import { mapTimingAndPositions, sessionFlagToPhase, timingFingerprint } from "./mapCars";
import { normalizeCompound, msToSeconds } from "./compounds";
import { countryFlag } from "./flags";
import { commsTabs, nextSelectorStep } from "./sessionFlow";
import { driverOutOfRace, fmtGap, fmtSectorTime, sectorClass } from "./timingDisplay";
import { buildPath, fractionAtPoint, lerpFrac, pointAtFraction } from "./trackGeometry";
import { PathCarAnimator } from "./deadReckoning";
import { isFullCircuitOutline, shouldApplyFallbackOutline } from "./circuitCache";
import { lapRecordsFromApi, stintsFromLapRecords } from "./panelData";
import { mergeByDriverCode, mergeCars, timingEqual } from "./mapCars";
import { sectorPathsFromOutline } from "./trackGeometry";
import { withCache, clearHttpCache, dedupe } from "./httpCache";
import { mapRecommendResponse, recommendNarration, shouldFetchRecommend } from "./arisRecommend";
import type { RoundCard, CarState, RecommendApiResponse } from "./types";

describe("replayYears", () => {
  it("returns only 2024–2026, newest first", () => {
    const years = replayYears(new Date("2026-08-26T12:00:00Z"));
    expect(years).toEqual([2026, 2025, 2024]);
  });
});

describe("defaultReplayYear", () => {
  it("picks the most recent completed season inside the window", () => {
    expect(defaultReplayYear(new Date("2026-08-27T12:00:00Z"))).toBe(2025);
    expect(defaultReplayYear(new Date("2026-12-15T12:00:00Z"))).toBe(2026);
    expect(defaultReplayYear(new Date("2024-03-01T12:00:00Z"))).toBe(2024);
  });
});

describe("filterReplayRounds", () => {
  const rounds: RoundCard[] = [
    { round: 1, circuitName: "Australia", countryFlag: "🇦🇺", date: "2026-03-15", sessionType: "R", isSprint: false, arisEligible: true, status: "COMPLETED" },
    { round: 2, circuitName: "Bahrain", countryFlag: "🇧🇭", date: "2026-03-22", sessionType: "R", isSprint: false, arisEligible: false, status: "CANCELLED" },
    { round: 3, circuitName: "Saudi Arabia", countryFlag: "🇸🇦", date: "2026-03-29", sessionType: "R", isSprint: false, arisEligible: false, status: "CANCELLED" },
    { round: 15, circuitName: "Netherlands", countryFlag: "🇳🇱", date: "2026-08-23", sessionType: "R", isSprint: true, arisEligible: true, status: "COMPLETED" },
    { round: 16, circuitName: "Italy", countryFlag: "🇮🇹", date: "2026-09-06", sessionType: "R", isSprint: false, arisEligible: false, status: "UPCOMING" },
  ];

  it("drops cancelled and upcoming 2026 rounds", () => {
    const keep = filterReplayRounds(rounds).map((r) => r.round);
    expect(keep).toEqual([1, 15]);
    expect(isReplayableRound(rounds[1])).toBe(false);
  });
});

describe("startFinishMarker", () => {
  it("uses the sf marker from the circuit map", () => {
    const m = startFinishMarker(
      [{ kind: "sf", x: 10, y: 20, label: "S/F" }],
      [0, 1],
      [0, 1],
    );
    expect(m.label).toBe("S/F");
    expect(m.x).toBe(10);
  });

  it("falls back to the first track point", () => {
    const m = startFinishMarker([], [4, 5], [6, 7]);
    expect(m.x).toBe(4);
    expect(m.y).toBe(6);
  });
});

describe("chequeredSfFlag", () => {
  it("returns a 2x8 checkerboard at the first track point", () => {
    const g = chequeredSfFlag([0, 10], [0, 0]);
    expect(g.cx).toBe(0);
    expect(g.cy).toBe(0);
    expect(g.cols).toBe(8);
    expect(g.rows).toBe(2);
    expect(g.angle).toBe(0);
  });
});

describe("mapTimingAndPositions", () => {
  it("places cars on GPS coordinates from positions", () => {
    const cars = mapTimingAndPositions(
      [{
        position: 1,
        driver_code: "VER",
        gap_to_leader_s: 0,
        gap_to_ahead_s: 0,
        last_lap_ms: 71234,
        best_lap_ms: 71000,
        fastest_lap: true,
        s1_colour: "purple",
        sector1_ms: 23100,
        compound: "M",
        tyre_life: 8,
        pit_count: 0,
        team_colour: "#3671C6",
        in_pit: false,
        lap_number: 12,
        speed_kph: 280,
      }],
      [{ driver_code: "VER", x: 120, y: 80, team_colour: "#3671C6", is_pitted: false, is_dnf: false, path_frac: 0.2, speed_ms: 70 }],
      [{ driver_number: 1, driver_code: "VER", full_name: "Max Verstappen", team: "Red Bull", team_colour: "#3671C6" }],
      72,
      12,
    );
    expect(cars.VER.x).toBe(120);
    expect(cars.VER.y).toBe(80);
    expect(cars.VER.compound).toBe("MEDIUM");
    expect(cars.VER.last_lap_s).toBeCloseTo(71.234);
    expect(cars.VER.fastest_lap).toBe(true);
    expect(cars.VER.s1_colour).toBe("purple");
    expect(cars.VER.path_frac).toBe(0.2);
  });

  it("marks DNF cars so the map can hide them", () => {
    const cars = mapTimingAndPositions(
      [{
        position: 18,
        driver_code: "GAS",
        gap_to_leader_s: null,
        gap_to_ahead_s: null,
        last_lap_ms: null,
        compound: null,
        tyre_life: null,
        pit_count: 0,
        team_colour: null,
        in_pit: false,
        lap_number: 8,
        speed_kph: null,
        status: "DNF",
        eliminated: true,
      }],
      [],
      [{ driver_number: 10, driver_code: "GAS", full_name: "Pierre Gasly", team: "Alpine", team_colour: "#0093d0" }],
      57,
      20,
    );
    expect(cars.GAS.is_dnf).toBe(true);
    expect(cars.GAS.status).toBe("DNF");
  });
});

describe("helpers", () => {
  it("normalises compounds and session flags", () => {
    expect(normalizeCompound("S")).toBe("SOFT");
    expect(msToSeconds(1000)).toBe(1);
    expect(sessionFlagToPhase("SC")).toBe("SC");
    expect(countryFlag("Netherlands")).toBe("🇳🇱");
  });
});

describe("timing display", () => {
  it("colours sectors and formats gaps", () => {
    expect(sectorClass("purple")).toContain("c44dff");
    expect(sectorClass("green")).toContain("39ff14");
    expect(fmtGap(0)).toBe("LEADER");
    expect(fmtGap(1.2, 1)).toBe("+1L");
    expect(fmtSectorTime(25.123)).toBe("25.123");
    expect(fmtSectorTime(null)).toBe("—");
    expect(driverOutOfRace("DNF", false)).toBe(true);
    expect(driverOutOfRace("RUNNING", false)).toBe(false);
  });
});

describe("session flow", () => {
  it("walks circuit → ARIS driver → strategies → loading", () => {
    expect(nextSelectorStep("circuit", "select", { arisEnabled: true })).toBe("driver");
    expect(nextSelectorStep("driver", "lock")).toBe("strategies");
    expect(nextSelectorStep("strategies", "continue")).toBe("loading");
    expect(nextSelectorStep("driver", "back")).toBe("circuit");
  });

  it("skips driver setup for data-only replay", () => {
    expect(nextSelectorStep("circuit", "replay", { arisEnabled: false })).toBe("loading");
    expect(nextSelectorStep("circuit", "select", { arisEnabled: false })).toBe("loading");
  });

  it("consolidates comms to two tabs", () => {
    const tabs = commsTabs({ arisOn: true, copilotOn: true, copilotDocked: false });
    expect(tabs.map((t) => t.id)).toEqual(["main", "chat"]);
    expect(tabs[1].label).toBe("Copilot");
  });
});

describe("circuit outline", () => {
  it("rejects 20-point previews so the map waits for the real racing line", () => {
    expect(isFullCircuitOutline({ x: Array(21).fill(0), y: Array(21).fill(0) })).toBe(false);
    expect(isFullCircuitOutline({ x: Array(80).fill(0), y: Array(80).fill(1) })).toBe(true);
    expect(shouldApplyFallbackOutline({ x: Array(20).fill(0) })).toBe(true);
    expect(shouldApplyFallbackOutline({ x: Array(49).fill(0) })).toBe(true);
    expect(shouldApplyFallbackOutline({ x: Array(50).fill(0) })).toBe(false);
    expect(shouldApplyFallbackOutline({ x: Array(80).fill(0) })).toBe(false);
    expect(shouldApplyFallbackOutline(null)).toBe(true);
  });
});

describe("path interpolation", () => {
  it("keeps cars on the racing line", () => {
    const path = buildPath([0, 10, 10, 0], [0, 0, 10, 10]);
    const mid = pointAtFraction(path, 0.125);
    expect(mid.x).toBeGreaterThan(0);
    const frac = fractionAtPoint(path, 10, 0);
    expect(frac).toBeGreaterThanOrEqual(0);
    expect(lerpFrac(0.9, 0.1, 0.5)).toBeCloseTo(0, 5);
    const anim = new PathCarAnimator(path, 0, 200);
    anim.onTick(0.25, 0);
    const pos = anim.currentPosition(200);
    expect(Number.isFinite(pos.x)).toBe(true);
    expect(Number.isFinite(pos.y)).toBe(true);
    anim.onTick(0.3, 250);
    const later = anim.currentPosition(500);
    expect(later.frac).toBeGreaterThan(0.2);
    expect(later.frac).toBeLessThan(0.5);
    const onLine = fractionAtPoint(path, later.x, later.y);
    expect(Math.abs(onLine - later.frac) < 0.02 || Math.abs(onLine - later.frac) > 0.98).toBe(true);
  });

  it("eases toward a new tick instead of snapping", () => {
    const path = buildPath([0, 10, 10, 0], [0, 0, 10, 10]);
    const anim = new PathCarAnimator(path, 0, 140);
    anim.onTick(0.2, 0);
    const a = anim.currentPosition(16);
    const b = anim.currentPosition(32);
    expect(a.frac).toBeGreaterThan(0);
    expect(a.frac).toBeLessThan(0.2);
    expect(b.frac).toBeGreaterThan(a.frac);
    expect(b.frac).toBeLessThan(0.2);
  });

  it("fingerprints timing so unchanged SSE ticks can be skipped", () => {
    const row = {
      position: 1,
      driver_code: "VER",
      gap_to_leader_s: 0,
      gap_to_ahead_s: 0,
      last_lap_ms: 71000,
      compound: "M",
      tyre_life: 1,
      pit_count: 0,
      team_colour: "#000",
      in_pit: false,
      lap_number: 2,
      speed_kph: 200,
    };
    const pos = [{ driver_code: "VER", x: 1, y: 2, team_colour: null, is_pitted: false, is_dnf: false, path_frac: 0.1, speed_ms: 50 }];
    expect(timingFingerprint([row], pos)).toBe(timingFingerprint([row], pos));
  });
});

describe("panelData", () => {
  it("computes gaps and derives stints from lap rows", () => {
    const laps = lapRecordsFromApi([
      { driver_code: "VER", lap_number: 1, lap_time_ms: 72000, sector1_ms: 25000, sector2_ms: 23000, sector3_ms: 24000, compound: "M", tyre_life: 1, pit_in_lap: false, pit_out_lap: false, position: 1, end_time_ms: 72000 },
      { driver_code: "HAM", lap_number: 1, lap_time_ms: 72500, sector1_ms: 25100, sector2_ms: 23100, sector3_ms: 24300, compound: "M", tyre_life: 1, pit_in_lap: false, pit_out_lap: false, position: 2, end_time_ms: 72500 },
      { driver_code: "VER", lap_number: 2, lap_time_ms: 72100, sector1_ms: 25000, sector2_ms: 23000, sector3_ms: 24100, compound: "H", tyre_life: 1, pit_in_lap: false, pit_out_lap: true, position: 1, end_time_ms: 144100 },
    ]);
    const ver1 = laps.find((l) => l.driverCode === "VER" && l.lap === 1);
    const ham1 = laps.find((l) => l.driverCode === "HAM" && l.lap === 1);
    expect(ver1?.gapAheadS).toBe(0);
    expect(ham1?.gapAheadS).toBeCloseTo(0.5, 5);
    const stints = stintsFromLapRecords(laps);
    expect(stints.filter((s) => s.driverCode === "VER").length).toBe(2);
  });
});

describe("http cache", () => {
  it("dedupes inflight requests and serves a later hit from memory", async () => {
    clearHttpCache();
    let calls = 0;
    const fn = () => {
      calls += 1;
      return new Promise<{ n: number }>((resolve) => setTimeout(() => resolve({ n: calls }), 20));
    };
    const [a, b] = await Promise.all([withCache("t-cal", 60_000, fn), withCache("t-cal", 60_000, fn)]);
    expect(calls).toBe(1);
    expect(a).toEqual({ n: 1 });
    expect(b).toEqual({ n: 1 });
    const c = await withCache("t-cal", 60_000, fn);
    expect(calls).toBe(1);
    expect(c).toEqual({ n: 1 });
  });

  it("shares a POST in flight without caching a null miss", async () => {
    clearHttpCache();
    let calls = 0;
    const [a, b] = await Promise.all([
      dedupe("post-rec", async () => {
        calls += 1;
        await new Promise((r) => setTimeout(r, 15));
        return { ok: true };
      }),
      dedupe("post-rec", async () => {
        calls += 1;
        return { ok: false };
      }),
    ]);
    expect(calls).toBe(1);
    expect(a).toEqual({ ok: true });
    expect(b).toEqual({ ok: true });
  });
});

describe("sector paths", () => {
  it("falls back to equal-distance thirds without markers", () => {
    const xs = [0, 10, 20, 30, 40, 50, 60, 70, 80];
    const ys = [0, 0, 0, 0, 0, 0, 0, 0, 0];
    const { paths, usedFallback } = sectorPathsFromOutline(xs, ys, []);
    expect(usedFallback).toBe(true);
    expect(paths.map((p) => p.kind)).toEqual(["s1", "s2", "s3"]);
    expect(paths.every((p) => p.x.length >= 2)).toBe(true);
  });

  it("uses s1/s2 markers when they are in order", () => {
    const xs = [0, 10, 20, 30, 40, 50, 60];
    const ys = [0, 0, 0, 0, 0, 0, 0];
    const { paths, usedFallback } = sectorPathsFromOutline(xs, ys, [
      { kind: "s1", x: 20, y: 0 },
      { kind: "s2", x: 40, y: 0 },
    ]);
    expect(usedFallback).toBe(false);
    expect(paths[0].x[paths[0].x.length - 1]).toBe(20);
    expect(paths[1].x[paths[1].x.length - 1]).toBe(40);
  });
});

describe("SSE car merge", () => {
  const base = {
    driver_code: "VER",
    driver_number: 1,
    full_name: "Max",
    team: "RBR",
    team_colour: "#00f",
    position: 1,
    lap_number: 2,
    compound: "MEDIUM" as const,
    tyre_life: 2,
    gap_to_leader_s: 0,
    gap_ahead_s: 0,
    gap_ahead_history: [] as number[],
    last_lap_s: 71,
    pit_stops: 0,
    is_pitted: false,
    is_dnf: false,
    x: 10,
    y: 10,
    speed_kph: 200,
    heading_rad: 0,
    laps_remaining: 70,
    total_laps: 72,
    path_frac: 0.2,
  } satisfies CarState;

  it("keeps the previous object when a row is unchanged", () => {
    const prev = { VER: { ...base } };
    const next = { VER: { ...base } };
    const merged = mergeCars(prev, next);
    expect(merged).toBe(prev);
    expect(merged.VER).toBe(prev.VER);
  });

  it("replaces only the car that moved", () => {
    const prev = { VER: { ...base }, HAM: { ...base, driver_code: "HAM" } };
    const next = { VER: { ...base, path_frac: 0.3, x: 12 }, HAM: { ...base, driver_code: "HAM" } };
    const merged = mergeCars(prev, next);
    expect(merged.HAM).toBe(prev.HAM);
    expect(merged.VER).not.toBe(prev.VER);
    expect(merged.VER.path_frac).toBe(0.3);
    expect(timingEqual(prev.VER, { ...base, path_frac: 0.9 })).toBe(true);
  });
});

describe("ghostCarFromTick", () => {
  it("uses A_ prefix and offsets path_frac by delta", async () => {
    const { ghostCarFromTick, asGhostTick } = await import("./ghostCar");
    const tick = asGhostTick({
      driver_code: "HAM",
      divergence_lap: 18,
      aris_action: "PIT_NOW_HARD",
      real_action: "STAY_OUT",
      ghost_tyre: "HARD",
      ghost_tyre_age: 2,
      ghost_position: 3,
      ghost_cumulative_delta: 9,
      active: true,
      outcome: null,
      delta_history: [],
    });
    expect(tick?.driver_code).toBe("HAM");
    const real = {
      driver_code: "HAM",
      driver_number: 44,
      full_name: "Lewis",
      team: "MER",
      team_colour: "#00d2be",
      position: 4,
      lap_number: 20,
      compound: "MEDIUM" as const,
      tyre_life: 12,
      gap_to_leader_s: 8,
      gap_ahead_s: 1,
      gap_ahead_history: [] as number[],
      last_lap_s: 72,
      pit_stops: 1,
      is_pitted: false,
      is_dnf: false,
      status: "RUNNING" as const,
      x: 10,
      y: 10,
      speed_kph: 250,
      heading_rad: 0,
      laps_remaining: 52,
      total_laps: 72,
      path_frac: 0.1,
    };
    const car = ghostCarFromTick(tick!, real, 20, 72);
    expect(car.driver_code).toBe("A_HAM");
    expect(car.path_frac).toBeGreaterThan(0.1);
    expect(car.ghost_cumulative_delta).toBe(9);
  });

  it("uses ghost_position_on_track from the frame when present", async () => {
    const { ghostCarFromTick, asGhostTick } = await import("./ghostCar");
    const tick = asGhostTick({
      driver_code: "VER",
      divergence_lap: 1,
      aris_action: "PIT_L18_HARD",
      real_action: "STAY_OUT",
      ghost_tyre: "HARD",
      ghost_tyre_age: 4,
      ghost_position: 2,
      ghost_cumulative_delta: 4.5,
      ghost_position_on_track: 0.42,
      from_lap_one: true,
      typical_lap_s: 74,
      active: true,
      outcome: null,
      delta_history: [{ lap: 1, delta: 0, ghost_pos: 3, real_pos: 3 }],
    });
    expect(tick?.from_lap_one).toBe(true);
    expect(tick?.ghost_position_on_track).toBeCloseTo(0.42);
    const car = ghostCarFromTick(tick!, null, 1, 72);
    expect(car.driver_code).toBe("A_VER");
    expect(car.path_frac).toBeCloseTo(0.42);
    expect(car.last_lap_s).toBeNull();
  });

  it("syntheticGhostTick gives GhostDelta a point when only a recommendation exists", async () => {
    const { syntheticGhostTick, syntheticGhostCar } = await import("./ghostCar");
    const rec = {
      rank: 1,
      label: "Pit lap 18 for HARD",
      action: { kind: "pit_now" as const, pit_compound: "HARD" as const },
      delta_vs_stay_out_s: 2.4,
      mean_race_time_s: 0,
      confidence_std_s: 0,
      p10_delta_s: 0,
      p90_delta_s: 0,
      evidence: "",
      narration_context: {},
      extrapolation_beyond_laps: 0,
      extrapolation_weight: 0,
      wet_heuristic: false,
      cql_q_delta: 0,
      rank_score: 0,
      id: "r1",
      lap: 18,
    };
    const tick = syntheticGhostTick(rec, "HAM", 20);
    expect(tick.driver_code).toBe("HAM");
    expect(tick.delta_history).toHaveLength(1);
    expect(tick.delta_history[0].lap).toBe(20);
    const real = {
      driver_code: "HAM",
      driver_number: 44,
      full_name: "Lewis",
      team: "MER",
      team_colour: "#00d2be",
      position: 4,
      lap_number: 20,
      compound: "MEDIUM" as const,
      tyre_life: 12,
      gap_to_leader_s: 8,
      gap_ahead_s: 1,
      gap_ahead_history: [] as number[],
      last_lap_s: 72,
      pit_stops: 1,
      is_pitted: false,
      is_dnf: false,
      status: "RUNNING" as const,
      x: 10,
      y: 10,
      speed_kph: 250,
      heading_rad: 0,
      laps_remaining: 52,
      total_laps: 72,
      path_frac: 0.1,
    };
    const car = syntheticGhostCar(rec, real, 20, 72);
    expect(car.driver_code).toBe("A_HAM");
    expect(tick.ghost_cumulative_delta).toBe(car.ghost_cumulative_delta);
  });
});

describe("recommend mapping", () => {
  it("builds narration from the API payload", () => {
    const res: RecommendApiResponse = {
      action: "BOX",
      compound_recommendation: "H",
      reasoning: "Cliff approaching",
      pace_gain_s: 4,
      pit_cost_s: 21,
      net_delta_s: -2.4,
      confidence: 0.7,
      decision_record_id: "DR-1",
      alternatives: [{ action: "BOX", compound: "H", net_delta_s: -2.4, note: "Pit lap 33 for HARD" }],
    };
    const rec = mapRecommendResponse(res, 33);
    expect(rec.label).toBe("Pit lap 33 for HARD");
    expect(recommendNarration(rec)).toContain("Δ -2.4 s vs stay");
    expect(
      shouldFetchRecommend({
        isARISOn: true,
        playState: "racing",
        lap: 1,
        lastLap: null,
        tyreLife: 1,
        phase: "GREEN",
        lastPhase: null,
      }),
    ).toBe(true);
    expect(
      shouldFetchRecommend({
        isARISOn: true,
        playState: "ready",
        lap: 1,
        lastLap: null,
        tyreLife: 1,
        phase: "GREEN",
        lastPhase: null,
      }),
    ).toBe(false);
  });
});

describe("mergeByDriverCode", () => {
  it("overlays changed cars and keeps the rest", () => {
    const prev = [
      { driver_code: "VER", x: 1, y: 1 },
      { driver_code: "HAM", x: 2, y: 2 },
    ];
    const merged = mergeByDriverCode(prev, [{ driver_code: "VER", x: 9, y: 1 }]);
    expect(merged).toEqual([
      { driver_code: "VER", x: 9, y: 1 },
      { driver_code: "HAM", x: 2, y: 2 },
    ]);
  });
});

