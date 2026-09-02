import { describe, expect, it } from "vitest";
import { filterReplayRounds, replayYears, defaultReplayYear, startFinishMarker, isReplayableRound, chequeredSfFlag, keepRoundsWithPack } from "./replayFilter";
import { annotateGhostTower, mapTimingAndPositions, mergeByDriverCode, mergeCars, onTrackCarCodes, orderTimingTower, rankGhostByGap, realClassifiedCars, sessionFlagToPhase, timingEqual, timingFingerprint } from "./mapCars";
import { normalizeCompound, msToSeconds } from "./compounds";
import { countryFlag } from "./flags";
import { commsTabs, nextSelectorStep } from "./sessionFlow";
import { driverOutOfRace, fmtGap, fmtSectorTime, sectorClass } from "./timingDisplay";
import { buildPath, fractionAtPoint, lerpFrac, pointAtFraction } from "./trackGeometry";
import { PathCarAnimator, wrappedDelta } from "./deadReckoning";
import { isFullCircuitOutline, shouldApplyFallbackOutline } from "./circuitCache";
import { lapRecordsFromApi, stintsFromLapRecords } from "./panelData";
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
    const keep = filterReplayRounds(rounds, { now: new Date("2026-09-03T12:00:00Z") }).map((r) => r.round);
    expect(keep).toEqual([1, 15]);
    expect(isReplayableRound(rounds[1])).toBe(false);
  });

  it("hides a COMPLETED race whose date is still in the future", () => {
    const monza: RoundCard = {
      round: 16,
      circuitName: "Italy",
      countryFlag: "🇮🇹",
      date: "2026-09-06T13:00:00Z",
      sessionType: "R",
      isSprint: false,
      arisEligible: true,
      status: "COMPLETED",
    };
    expect(filterReplayRounds([monza], { now: new Date("2026-09-03T12:00:00Z") })).toEqual([]);
    expect(filterReplayRounds([monza], { now: new Date("2026-09-06T18:00:00Z") }).map((r) => r.round)).toEqual([16]);
  });

  it("hides Imola 2026 even when the API marks it completed", () => {
    const imola: RoundCard = {
      round: 7,
      circuitName: "Imola",
      countryFlag: "🇮🇹",
      date: "2026-05-24T13:00:00Z",
      sessionType: "R",
      isSprint: false,
      arisEligible: true,
      status: "COMPLETED",
    };
    expect(filterReplayRounds([imola], { year: 2026, now: new Date("2026-09-03T12:00:00Z") })).toEqual([]);
  });
});

describe("keepRoundsWithPack", () => {
  it("drops only confirmed missing race_field.json packs", () => {
    const rounds: RoundCard[] = [
      { round: 6, circuitName: "Miami", countryFlag: "🇺🇸", date: "2026-05-10", sessionType: "R", isSprint: true, arisEligible: true, status: "COMPLETED" },
      { round: 9, circuitName: "Spain", countryFlag: "🇪🇸", date: "2026-06-14", sessionType: "R", isSprint: false, arisEligible: true, status: "COMPLETED" },
    ];
    const exists = new Map<number, boolean | null>([
      [6, true],
      [9, false],
    ]);
    expect(keepRoundsWithPack(rounds, exists).map((r) => r.round)).toEqual([6]);
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
    expect(fmtGap(-0.4)).toBe("LEADER");
    expect(fmtGap(1.2)).toBe("+1.2s");
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
    expect(lerpFrac(0.1, 0.9, 0.5)).toBeCloseTo(0.5, 5);
    const anim = new PathCarAnimator(path, 0, 200);
    anim.onTick(0.25, 0, { playbackSpeed: 4 });
    const pos = anim.currentPosition(200);
    expect(Number.isFinite(pos.x)).toBe(true);
    expect(Number.isFinite(pos.y)).toBe(true);
    anim.onTick(0.3, 250, { playbackSpeed: 4 });
    const later = anim.currentPosition(500);
    expect(later.frac).toBeGreaterThan(0.05);
    expect(later.frac).toBeLessThan(0.5);
    const onLine = fractionAtPoint(path, later.x, later.y);
    expect(Math.abs(onLine - later.frac) < 0.02 || Math.abs(onLine - later.frac) > 0.98).toBe(true);
  });

  it("keeps S/F wrap forward and does not reverse a >0.5 jump", () => {
    expect(wrappedDelta(0.9, 0.1)).toBeCloseTo(0.2, 5);
    expect(wrappedDelta(0.1, 0.9)).toBeCloseTo(0.8, 5);
  });

  it("eases toward a new tick instead of snapping", () => {
    const path = buildPath([0, 10, 10, 0], [0, 0, 10, 10]);
    const anim = new PathCarAnimator(path, 0, 140);
    anim.onTick(0.2, 0, { playbackSpeed: 4 });
    const a = anim.currentPosition(16);
    const b = anim.currentPosition(32);
    expect(a.frac).toBeGreaterThan(0);
    expect(a.frac).toBeLessThan(0.2);
    expect(b.frac).toBeGreaterThan(a.frac);
    expect(b.frac).toBeLessThan(0.2);
  });

  it("caps per-frame motion so a GPS hole does not teleport", () => {
    const path = buildPath([0, 10, 10, 0], [0, 0, 10, 10]);
    const anim = new PathCarAnimator(path, 0, 140);
    anim.onTick(0.5, 0, { playbackSpeed: 1 });
    const a = anim.currentPosition(16, true);
    expect(a.frac).toBeLessThan(0.05);
  });

  it("follows a 1x GPS-sized bump instead of lagging it", () => {
    const path = buildPath([0, 10, 10, 0], [0, 0, 10, 10]);
    const anim = new PathCarAnimator(path, 0, 140);
    anim.onTick(0.01, 0, { playbackSpeed: 1 });
    const a = anim.currentPosition(16, true);
    expect(a.frac).toBeGreaterThan(0.005);
    expect(a.frac).toBeLessThan(0.012);
  });

  it("snaps onto the new target when playback speed drops", () => {
    const path = buildPath([0, 10, 10, 0], [0, 0, 10, 10]);
    const anim = new PathCarAnimator(path, 0.4, 140);
    anim.onTick(0.4, 0, { playbackSpeed: 50 });
    anim.onTick(0.28, 16, { playbackSpeed: 1 });
    const pos = anim.currentPosition(32, true);
    expect(pos.frac).toBeCloseTo(0.28, 3);
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

  it("keeps last path_frac when the next frame omits it", () => {
    const prev = { VER: { ...base, path_frac: 0.42, x: 9, y: 8 } };
    const next = { VER: { ...base, path_frac: undefined as unknown as number, x: 0, y: 0 } };
    const merged = mergeCars(prev, next);
    expect(merged.VER.path_frac).toBe(0.42);
    expect(merged.VER.x).toBe(9);
    expect(merged.VER.y).toBe(8);
  });
});

describe("orderTimingTower", () => {
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

  function car(over: Partial<CarState>): CarState {
    return { ...base, ...over };
  }

  it("puts is_dnf drivers below classified and inserts the ghost among classified", () => {
    const rows = orderTimingTower(
      [
        car({ driver_code: "HAM", position: null, is_dnf: true, laps_completed: 16, lap_number: 16 }),
        car({ driver_code: "VER", position: 1, is_dnf: false, laps_completed: 57 }),
        car({ driver_code: "LEC", position: 2, is_dnf: false, laps_completed: 57 }),
        car({ driver_code: "GAS", position: 19, is_dnf: true, laps_completed: 4, lap_number: 4 }),
      ],
      car({ driver_code: "A_VER", position: 2, is_dnf: false }),
    );
    expect(rows.map((r) => r.driver_code)).toEqual(["VER", "A_VER", "LEC", "HAM", "GAS"]);
  });

  it("sorts a ghost already in the cars array like a classified car", () => {
    const rows = orderTimingTower([
      car({ driver_code: "VER", position: 1, gap_to_leader_s: 0 }),
      car({ driver_code: "NOR", position: 2, gap_to_leader_s: 0.8 }),
      car({ driver_code: "LEC", position: 3, gap_to_leader_s: 1.5 }),
      car({ driver_code: "A_NOR", position: 2, is_ghost: true, gap_to_leader_s: 0.8 }),
    ]);
    expect(rows.map((r) => r.driver_code)).toEqual(["VER", "A_NOR", "NOR", "LEC"]);
  });

  it("excludes the ghost from real classified count", () => {
    const rows = orderTimingTower(
      [
        car({ driver_code: "VER", position: 1 }),
        car({ driver_code: "NOR", position: 2 }),
        car({ driver_code: "GAS", position: 3, is_dnf: true }),
      ],
      car({ driver_code: "A_VER", position: 2, is_ghost: true }),
    );
    expect(rows).toHaveLength(4);
    expect(realClassifiedCars(rows).map((r) => r.driver_code)).toEqual(["VER", "NOR"]);
  });
});

describe("annotateGhostTower", () => {
  const base = {
    driver_code: "VER",
    driver_number: 1,
    full_name: "Max",
    team: "RBR",
    team_colour: "#00f",
    position: 1,
    lap_number: 12,
    compound: "MEDIUM" as const,
    tyre_life: 12,
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
    laps_remaining: 45,
    total_laps: 57,
    path_frac: 0.2,
  } satisfies CarState;

  function car(over: Partial<CarState>): CarState {
    return { ...base, ...over };
  }

  const field = {
    VER: car({ driver_code: "VER", position: 1, gap_to_leader_s: 0, gap_ahead_s: 0 }),
    NOR: car({ driver_code: "NOR", position: 2, gap_to_leader_s: 1.2, gap_ahead_s: 1.2 }),
    LEC: car({ driver_code: "LEC", position: 3, gap_to_leader_s: 2.4, gap_ahead_s: 1.2 }),
    GAS: car({ driver_code: "GAS", position: 4, gap_to_leader_s: 8, is_dnf: true }),
  };

  it("ranks by classified gap_to_leader, ignoring stale tick position and path_frac", () => {
    const ghost = car({
      driver_code: "A_NOR",
      is_ghost: true,
      position: 23,
      gap_to_leader_s: 6742,
      ghost_cumulative_delta: 0.5,
      path_frac: 0.91,
    });
    const placed = annotateGhostTower(ghost, field, field.NOR);
    expect(placed.is_ghost).toBe(true);
    expect(placed.position).toBe(2);
    expect(placed.gap_to_leader_s).toBeCloseTo(0.7, 5);
    expect(placed.ghost_delta_vs).toBe("VER");
    expect(placed.ghost_delta_s).toBeCloseTo(-0.7, 5);
    expect(placed.gap_ahead_s).toBeCloseTo(0.7, 5);
  });

  it("uses +delta (ahead) / −delta (behind) vs the adjacent real car", () => {
    const behind = annotateGhostTower(
      car({ driver_code: "A_NOR", ghost_cumulative_delta: 0.5, position: 23 }),
      field,
      field.NOR,
    );
    expect(behind.ghost_delta_s).toBeLessThan(0);
    expect(fmtGap(behind.gap_to_leader_s)).toBe("+0.7s");

    const ahead = annotateGhostTower(
      car({ driver_code: "A_NOR", ghost_cumulative_delta: 1.5, position: 23 }),
      field,
      field.NOR,
    );
    expect(ahead.position).toBe(1);
    expect(ahead.ghost_delta_vs).toBe("VER");
    expect(ahead.ghost_delta_s).toBeCloseTo(0.3, 5);
    expect(ahead.ghost_delta_s).toBeGreaterThan(0);
    expect(fmtGap(ahead.gap_to_leader_s)).toBe("LEADER");
  });

  it("matches the focus driver's classified position when cumulative_delta is 0", () => {
    const placed = annotateGhostTower(
      car({ driver_code: "A_NOR", ghost_cumulative_delta: 0, position: 23 }),
      field,
      field.NOR,
    );
    expect(placed.position).toBe(2);
    expect(placed.gap_to_leader_s).toBe(1.2);
  });

  it("does not change rank when path_frac / pos_samples on the inputs change", () => {
    const ghost = car({
      driver_code: "A_NOR",
      ghost_cumulative_delta: 0.5,
      path_frac: 0.1,
    });
    const a = annotateGhostTower(ghost, field, field.NOR);
    const shifted = {
      VER: { ...field.VER, path_frac: 0.99, x: 1, y: 2 },
      NOR: { ...field.NOR, path_frac: 0.02, x: 3, y: 4 },
      LEC: { ...field.LEC, path_frac: 0.5 },
      GAS: { ...field.GAS, path_frac: 0.7 },
    };
    const b = annotateGhostTower({ ...ghost, path_frac: 0.77, x: 9, y: 9 }, shifted, shifted.NOR);
    expect(b.position).toBe(a.position);
    expect(b.gap_to_leader_s).toBe(a.gap_to_leader_s);
    expect(b.ghost_delta_s).toBe(a.ghost_delta_s);
    expect(b.ghost_delta_vs).toBe(a.ghost_delta_vs);
  });

  it("rankGhostByGap ignores DNF-sized gaps that are not in the classified snapshot", () => {
    expect(rankGhostByGap(0.7, [0, 1.2, 2.4], 99)).toBe(2);
    expect(rankGhostByGap(0, [0, 1.2, 2.4], 99)).toBe(1);
  });
});

describe("onTrackCarCodes", () => {
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

  it("hides pitted and DNF/DNS cars from the map", () => {
    const cars = {
      VER: { ...base, is_pitted: false, is_dnf: false },
      HAM: { ...base, driver_code: "HAM", is_pitted: true, is_dnf: false },
      GAS: { ...base, driver_code: "GAS", is_pitted: false, is_dnf: true, status: "DNF" as const },
    };
    expect(onTrackCarCodes(cars, "A_VER")).toBe("A_VER,VER");
  });
});

describe("ghostCarFromTick", () => {
  it("uses A_ prefix and independent path_frac from playback, not the real car", async () => {
    const { ghostCarFromTick, asGhostTick, ghostPlaybackAt } = await import("./ghostCar");
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
      path_frac: 0.9,
    };
    const playback = ghostPlaybackAt({
      elapsedS: 45,
      ghostLapS: [NaN, 90],
      ghostCumulativeS: [0, 90],
      totalLaps: 72,
      pitLaps: [],
      pitLossS: 22,
    });
    const car = ghostCarFromTick(tick!, real, 20, 72, playback);
    expect(car.driver_code).toBe("A_HAM");
    expect(car.is_ghost).toBe(true);
    expect(car.full_name).toBe("ARIS");
    expect(car.driver_number).toBe(0);
    expect(car.path_frac).toBeCloseTo(0.5, 5);
    expect(car.path_frac).not.toBeCloseTo(0.9, 2);
    expect(car.ghost_cumulative_delta).toBe(9);
  });

  it("does not follow ghost_position_on_track or typical_lap_s when playback is supplied", async () => {
    const { ghostCarFromTick, asGhostTick, ghostPlaybackAt } = await import("./ghostCar");
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
    const playback = ghostPlaybackAt({
      elapsedS: 0,
      ghostLapS: [NaN, 90],
      ghostCumulativeS: [0, 90],
      totalLaps: 72,
      pitLaps: [],
      pitLossS: 22,
    });
    const car = ghostCarFromTick(tick!, null, 1, 72, playback);
    expect(car.driver_code).toBe("A_VER");
    expect(car.path_frac).toBeCloseTo(0, 5);
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
    expect(car.path_frac).toBe(0);
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

