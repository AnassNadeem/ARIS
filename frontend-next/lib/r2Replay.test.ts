import { describe, expect, it } from "vitest";
import { annotateVsActivePlan, shouldFetchRecommend } from "./arisRecommend";
import { mapTimingAndPositions } from "./mapCars";
import { fieldToDrivers, fieldToLapRows, interpolatedPosFrac, nearestPosSample, normalizeR2Base, plansMatch, r2Configured, r2FrameAt, r2TickToGhostTick, raceDurationS, sectorSecondsForLap, speedKphFromPath, deriveGhostLapTimes, pitLossForCircuit, realLapTimesByDriver, GRID_START_LAP_FRAC, blendedPathFrac, gridPathFrac, replayDisplayFrac, ghostTickAtOrBefore, ghostDeltaChartPoints, r2FetchErrorMessage, RaceFieldNotFoundError, R2_LOAD_ERROR, R2_RACE_UNAVAILABLE } from "./r2Replay";
import type { ARISRecommendation, GhostData, RaceField, RaceFieldLap } from "./types";

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

describe("normalizeR2Base", () => {
  it("keeps /r2replay relative so localhost vs 127.0.0.1 does not CORS-fail", () => {
    expect(normalizeR2Base("/r2replay")).toBe("/r2replay");
    expect(normalizeR2Base("http://127.0.0.1:3000/r2replay")).toBe("/r2replay");
    expect(normalizeR2Base("http://localhost:3000/r2replay/")).toBe("/r2replay");
  });

  it("keeps the public R2 origin for production", () => {
    expect(normalizeR2Base("https://pub-9429cde26be84c4c8034f0b5873b9a7d.r2.dev")).toBe(
      "https://pub-9429cde26be84c4c8034f0b5873b9a7d.r2.dev",
    );
  });
});

describe("r2FetchErrorMessage", () => {
  it("maps a race_field 404 to the unavailable copy for any race", () => {
    expect(r2FetchErrorMessage(new RaceFieldNotFoundError())).toBe(R2_RACE_UNAVAILABLE);
    expect(r2FetchErrorMessage(new Error("HTTP 404"))).toBe(R2_RACE_UNAVAILABLE);
  });

  it("keeps connection copy for other failures", () => {
    expect(r2FetchErrorMessage(new Error("HTTP 503"))).toBe(R2_LOAD_ERROR);
    expect(r2FetchErrorMessage(new Error("Timed out after 30s"))).toBe(R2_LOAD_ERROR);
  });
});

describe("R2 fallback when NEXT_PUBLIC_R2_BASE_URL is unset", () => {
  it("reports unconfigured so ReplayFrameFeed uses Heroku pack-status", () => {
    if (process.env.NEXT_PUBLIC_R2_BASE_URL) {
      expect(r2Configured()).toBe(true);
      return;
    }
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
        { lap: 1, driver: "VER", position: 1, gap_to_leader_s: 0, gap_ahead_s: 0, compound: "MEDIUM", tyre_life: 1, stint_number: 1, pit_this_lap: false, is_dnf: false, is_dsq: false, track_status: "1", lap_time_s: 74, sector_1_s: null, sector_2_s: null, sector_3_s: null },
        { lap: 2, driver: "VER", position: 1, gap_to_leader_s: 0, gap_ahead_s: 0, compound: "MEDIUM", tyre_life: 2, stint_number: 1, pit_this_lap: false, is_dnf: false, is_dsq: false, track_status: "1", lap_time_s: 75, sector_1_s: null, sector_2_s: null, sector_3_s: null },
      ],
      stints: [],
      weather: [],
      race_control: [],
      pos_samples: {},
    } as RaceField;
    expect(raceDurationS(field)).toBe(149);
  });
});

describe("nearestPosSample", () => {
  it("at lap_frac=20.5 selects the nearest VER pos_sample", () => {
    const verSamples = [
      { lap_frac: 20.0, path_frac: 0.1 },
      { lap_frac: 20.4, path_frac: 0.41 },
      { lap_frac: 20.8, path_frac: 0.7 },
    ];
    const hit = nearestPosSample(verSamples, 20.5);
    expect(hit?.lap_frac).toBe(20.4);
    expect(hit?.path_frac).toBe(0.41);

    const lapRow = (n: number): RaceFieldLap => ({
      lap: n,
      driver: "VER",
      position: 1,
      gap_to_leader_s: 0,
      gap_ahead_s: 0,
      compound: "MEDIUM",
      tyre_life: n,
      stint_number: 1,
      pit_this_lap: false,
      is_dnf: false,
      is_dsq: false,
      track_status: "1",
      lap_time_s: 90,
      sector_1_s: null,
      sector_2_s: null,
      sector_3_s: null,
    });
    const field: RaceField = {
      meta: {
        year: 2025,
        round: 15,
        session_type: "R",
        circuit_name: "Zandvoort",
        total_laps: 22,
        date_race: "2025-08-31",
        green_flag_s: 0,
        session_key: 1,
      },
      outline: { x: [0, 100], y: [0, 0] },
      drivers: [{ code: "VER", name: "Max Verstappen", team: "Red Bull Racing", colour: "#3671C6", grid_position: 3, number: 1 }],
      laps: Array.from({ length: 22 }, (_, i) => lapRow(i + 1)),
      stints: [],
      weather: [],
      race_control: [],
      pos_samples: { VER: verSamples },
    };
    // 90s laps: elapsed 1845s is lap 21, 50% → lapFrac 20.5
    const frame = r2FrameAt(field, 20 * 90 + 45);
    const pos = frame.positions.find((p) => p.driver_code === "VER");
    expect(pos?.path_frac).toBeCloseTo(0.5, 2);
    const cars = mapTimingAndPositions(frame.timing, frame.positions, fieldToDrivers(field), 22, frame.lap);
    expect(cars.VER.path_frac).toBeCloseTo(0.5, 2);
    expect(cars.VER.team_colour).toBe("#3671C6");
    expect(cars.VER.speed_kph).toBeGreaterThan(50);
    expect(Object.keys(cars)).toEqual(["VER"]);
  });

  it("copies FastF1 sector times from the previous completed lap", () => {
    const lapRow = (n: number, sectors: [number | null, number | null, number | null]): RaceFieldLap => ({
      lap: n,
      driver: "VER",
      position: 1,
      gap_to_leader_s: 0,
      gap_ahead_s: 0,
      compound: "MEDIUM",
      tyre_life: n,
      stint_number: 1,
      pit_this_lap: false,
      is_dnf: false,
      is_dsq: false,
      track_status: "1",
      lap_time_s: 90,
      sector_1_s: sectors[0],
      sector_2_s: sectors[1],
      sector_3_s: sectors[2],
    });
    const field: RaceField = {
      meta: {
        year: 2025,
        round: 15,
        session_type: "R",
        circuit_name: "Zandvoort",
        total_laps: 3,
        date_race: "2025-08-31",
        green_flag_s: 0,
        session_key: 1,
      },
      outline: { x: [0, 100], y: [0, 0] },
      drivers: [{ code: "VER", name: "Max Verstappen", team: "Red Bull Racing", colour: "#3671C6", grid_position: 3, number: 1 }],
      laps: [
        lapRow(1, [25.78, 27.305, 22.861]),
        lapRow(2, [26.1, 27.0, 23.0]),
        lapRow(3, [null, null, null]),
      ],
      stints: [],
      weather: [],
      race_control: [],
      pos_samples: { VER: [{ lap_frac: 0, path_frac: 0 }, { lap_frac: 2.5, path_frac: 0.5 }] },
    };
    const frame = r2FrameAt(field, 90 + 45);
    const row = frame.timing.find((r) => r.driver_code === "VER");
    expect(row?.sector1_ms).toBe(25780);
    expect(row?.sector2_ms).toBe(27305);
    expect(row?.sector3_ms).toBe(22861);
    const mapped = fieldToLapRows(field);
    expect(mapped[0].sector1_ms).toBe(25780);
  });
});

describe("r2FrameAt grid_position at start", () => {
  const lap = (
    driver: string,
    n: number,
    position: number,
  ): RaceFieldLap => ({
    lap: n,
    driver,
    position,
    gap_to_leader_s: 0,
    gap_ahead_s: 0,
    compound: "MEDIUM",
    tyre_life: n,
    stint_number: 1,
    pit_this_lap: false,
    is_dnf: false,
    is_dsq: false,
    track_status: "1",
    lap_time_s: 90,
    sector_1_s: null,
    sector_2_s: null,
    sector_3_s: null,
  });

  const field: RaceField = {
    meta: {
      year: 2026,
      round: 6,
      session_type: "R",
      circuit_name: "Miami",
      total_laps: 2,
      date_race: "2026-05-03",
      green_flag_s: 0,
      session_key: 1,
    },
    outline: { x: [0, 100], y: [0, 0] },
    drivers: [
      { code: "ANT", name: "Kimi Antonelli", team: "Mercedes", colour: "#27F4D2", grid_position: 1, number: 12 },
      { code: "NOR", name: "Lando Norris", team: "McLaren", colour: "#FF8000", grid_position: 2, number: 4 },
    ],
    laps: [
      lap("ANT", 1, 2),
      lap("NOR", 1, 1),
      lap("ANT", 2, 2),
      lap("NOR", 2, 1),
    ],
    stints: [],
    weather: [],
    race_control: [],
    pos_samples: {},
  };

  it("uses qualifying grid_position at lights-out, not lap-1 classified", () => {
    const frame = r2FrameAt(field, 0);
    expect(GRID_START_LAP_FRAC).toBeGreaterThan(0);
    expect(frame.timing.find((r) => r.driver_code === "ANT")?.position).toBe(1);
    expect(frame.timing.find((r) => r.driver_code === "NOR")?.position).toBe(2);
    expect(frame.timing.map((r) => r.driver_code)).toEqual(["ANT", "NOR"]);
  });

  it("uses classified position once the race is underway", () => {
    const frame = r2FrameAt(field, 45);
    expect(frame.timing.find((r) => r.driver_code === "ANT")?.position).toBe(2);
    expect(frame.timing.find((r) => r.driver_code === "NOR")?.position).toBe(1);
  });

  it("places cars on the start/finish line at lights-out", () => {
    const withGps: RaceField = {
      ...field,
      pos_samples: {
        ANT: [{ lap_frac: 0, path_frac: 0.97 }, { lap_frac: 0.5, path_frac: 0.4 }],
        NOR: [{ lap_frac: 0, path_frac: 0.96 }, { lap_frac: 0.5, path_frac: 0.4 }],
      },
    };
    const frame = r2FrameAt(withGps, 0);
    const ant = frame.positions.find((p) => p.driver_code === "ANT");
    const nor = frame.positions.find((p) => p.driver_code === "NOR");
    expect(ant?.path_frac).toBeCloseTo(0, 2);
    expect(nor?.path_frac).toBeGreaterThan(0.98);
    expect(nor?.path_frac).toBeLessThan(1);
  });

  it("blends grid onto the timing target after lights-out instead of a hard cut", () => {
    const pole = gridPathFrac(1);
    const gps = 0.12;
    expect(blendedPathFrac(gps, 1, 0.01)).toBeCloseTo(pole, 5);
    const mid = blendedPathFrac(gps, 1, GRID_START_LAP_FRAC + 0.0175);
    expect(mid).toBeGreaterThan(pole);
    expect(mid).toBeLessThan(gps);
    expect(blendedPathFrac(gps, 1, 0.2)).toBeCloseTo(gps, 5);
  });

  it("replayDisplayFrac holds the grid at t=0 even when GPS wraps to 0.97", () => {
    const withGps: RaceField = {
      ...field,
      pos_samples: {
        ANT: [{ lap_frac: 0, path_frac: 0.97 }, { lap_frac: 0.5, path_frac: 0.4 }],
      },
    };
    expect(replayDisplayFrac(withGps, "ANT", 0)).toBeCloseTo(0, 2);
  });

  it("replayDisplayFrac discards a GPS hairpin snap once underway", () => {
    const withGps: RaceField = {
      ...field,
      pos_samples: {
        ANT: [{ lap_frac: 0, path_frac: 0.02 }, { lap_frac: 0.5, path_frac: 0.4 }],
      },
    };
    expect(replayDisplayFrac(withGps, "ANT", 45)).toBeCloseTo(0.5, 2);
  });

  it("lists DNS drivers who have no laps", () => {
    const withDns: RaceField = {
      ...field,
      drivers: [
        ...field.drivers,
        { code: "HUL", name: "Nico Hulkenberg", team: "Sauber", colour: "#52E252", grid_position: 0, is_dns: true },
      ],
    };
    const frame = r2FrameAt(withDns, 0);
    expect(frame.timing.find((r) => r.driver_code === "HUL")?.status).toBe("DNS");
    expect(frame.positions.find((p) => p.driver_code === "HUL")).toBeUndefined();
  });
});

describe("speedKphFromPath", () => {
  const samples = [
    { lap_frac: 20.0, path_frac: 0.1 },
    { lap_frac: 20.4, path_frac: 0.41 },
    { lap_frac: 20.8, path_frac: 0.72 },
  ];

  it("is positive while path_frac advances through a 90s lap", () => {
    expect(speedKphFromPath(samples, 20.2, 90)).toBeGreaterThan(80);
  });

  it("prefers telemetry speed_kph on the nearest sample", () => {
    const withSpeed = [
      { lap_frac: 20.0, path_frac: 0.1, speed_kph: 274 },
      { lap_frac: 20.4, path_frac: 0.41, speed_kph: 281 },
      { lap_frac: 20.8, path_frac: 0.72, speed_kph: 190 },
    ];
    expect(speedKphFromPath(withSpeed, 20.2, 90)).toBe(274);
  });

  it("falls back to lap-average speed when GPS path does not advance", () => {
    const stuck = [
      { lap_frac: 1.0, path_frac: 0.4 },
      { lap_frac: 1.5, path_frac: 0.4 },
    ];
    expect(speedKphFromPath(stuck, 1.2, 90)).toBeGreaterThan(50);
    expect(speedKphFromPath(stuck, 0.0, 90)).toBe(0);
  });
});

describe("sectorSecondsForLap", () => {
  it("splits a 90s lap at the 1/3 and 2/3 path crossings", () => {
    const samples = [
      { lap_frac: 4.0, path_frac: 0.0 },
      { lap_frac: 4.33, path_frac: 0.33 },
      { lap_frac: 4.66, path_frac: 0.66 },
      { lap_frac: 4.99, path_frac: 0.99 },
    ];
    const secs = sectorSecondsForLap(samples, 5, 90, 22);
    expect(secs.s1).toBeGreaterThan(25);
    expect(secs.s1).toBeLessThan(35);
    expect(secs.s2).toBeGreaterThan(25);
    expect(secs.s3).toBeGreaterThan(20);
    expect((secs.s1 ?? 0) + (secs.s2 ?? 0) + (secs.s3 ?? 0)).toBeCloseTo(90, 0);
  });
});

describe("interpolatedPosFrac", () => {
  const samples = [
    { lap_frac: 20.0, path_frac: 0.1 },
    { lap_frac: 20.4, path_frac: 0.41 },
    { lap_frac: 20.8, path_frac: 0.72 },
  ];

  it("interpolates the midpoint between bracketing samples", () => {
    expect(interpolatedPosFrac(samples, 20.2)).toBeCloseTo(0.255, 10);
  });

  it("does not treat a >0.5 forward jump as reverse", () => {
    const wrapish = [
      { lap_frac: 1.0, path_frac: 0.1 },
      { lap_frac: 1.5, path_frac: 0.9 },
    ];
    expect(interpolatedPosFrac(wrapish, 1.25)).toBeCloseTo(0.5, 5);
  });

  it("returns the exact sample at the first lap_frac", () => {
    expect(interpolatedPosFrac(samples, 20.0)).toBe(0.1);
  });

  it("returns the exact sample at the last lap_frac", () => {
    expect(interpolatedPosFrac(samples, 20.8)).toBe(0.72);
  });

  it("clamps to the last sample after the range", () => {
    expect(interpolatedPosFrac(samples, 21.0)).toBe(0.72);
  });

  it("clamps to the last sample when lapFrac is not finite", () => {
    expect(interpolatedPosFrac(samples, Number.NaN)).toBe(0.72);
  });
});

describe("deriveGhostLapTimes", () => {
  it("uses ghost_lap_s[L] = real[L] - (delta[L] - delta[L-1]) with delta[0]=0", () => {
    const ticks = [
      { lap: 1, position: 1, gap_to_leader_s: 0, compound: "SOFT", tyre_life: 1, stint: 1, cumulative_delta_s: 0, aris_action: "STAY_OUT", aris_confidence: 1 },
      { lap: 2, position: 1, gap_to_leader_s: 0, compound: "SOFT", tyre_life: 2, stint: 1, cumulative_delta_s: 2, aris_action: "STAY_OUT", aris_confidence: 1 },
    ];
    const derived = deriveGhostLapTimes(ticks, [NaN, 90, 90]);
    expect(derived.ghost_lap_s[1]).toBe(90);
    expect(derived.ghost_lap_s[2]).toBe(88);
    expect(derived.ghost_cumulative_s[0]).toBe(0);
    expect(derived.ghost_cumulative_s[1]).toBe(90);
    expect(derived.ghost_cumulative_s[2]).toBe(178);
    expect(derived.implausible_laps).toEqual([]);
  });

  it("does not add pit loss again — it is already in the delta step", () => {
    const ticks = [
      { lap: 8, position: 3, gap_to_leader_s: 0, compound: "SOFT", tyre_life: 9, stint: 1, cumulative_delta_s: 0.848, aris_action: "STAY_OUT", aris_confidence: 1 },
      { lap: 9, position: 3, gap_to_leader_s: 0, compound: "HARD", tyre_life: 1, stint: 2, cumulative_delta_s: -20.633, aris_action: "PIT", aris_confidence: 1 },
    ];
    const real = new Array(10).fill(90);
    real[0] = NaN;
    const derived = deriveGhostLapTimes(ticks, real);
    expect(derived.ghost_lap_s[9]).toBeCloseTo(90 - (-20.633 - 0.848), 5);
    expect(derived.ghost_lap_s[9]).toBeGreaterThan(100);
  });

  it("flags negative ghost_lap_s without clamping", () => {
    const ticks = [
      { lap: 1, position: 1, gap_to_leader_s: 0, compound: "SOFT", tyre_life: 1, stint: 1, cumulative_delta_s: 100, aris_action: "STAY_OUT", aris_confidence: 1 },
    ];
    const derived = deriveGhostLapTimes(ticks, [NaN, 90]);
    expect(derived.ghost_lap_s[1]).toBe(-10);
    expect(derived.implausible_laps).toEqual([
      { lap: 1, ghost_lap_s: -10, real_lap_s: 90, delta_step_s: 100 },
    ]);

    const long = deriveGhostLapTimes(
      [{ lap: 1, position: 1, gap_to_leader_s: 0, compound: "SOFT", tyre_life: 1, stint: 1, cumulative_delta_s: 6.72, aris_action: "STAY_OUT", aris_confidence: 1 }],
      [NaN, 900],
    );
    expect(long.ghost_lap_s[1]).toBe(300);
    expect(long.ghost_cumulative_s[1]).toBe(300);
    expect(long.implausible_laps[0]?.ghost_lap_s).toBe(900 - 6.72);
  });

  it("re-deriving from current_lap forward keeps early laps when early ticks are unchanged", () => {
    const early = [
      { lap: 1, position: 1, gap_to_leader_s: 0, compound: "SOFT", tyre_life: 1, stint: 1, cumulative_delta_s: 1, aris_action: "STAY_OUT", aris_confidence: 1 },
      { lap: 2, position: 1, gap_to_leader_s: 0, compound: "SOFT", tyre_life: 2, stint: 1, cumulative_delta_s: 2, aris_action: "STAY_OUT", aris_confidence: 1 },
    ];
    const merged = [
      ...early,
      { lap: 3, position: 2, gap_to_leader_s: 0, compound: "HARD", tyre_life: 1, stint: 2, cumulative_delta_s: -18, aris_action: "PIT", aris_confidence: 1 },
    ];
    const real = [NaN, 90, 91, 92];
    const before = deriveGhostLapTimes(early, real);
    const after = deriveGhostLapTimes(merged, real);
    expect(after.ghost_lap_s[1]).toBe(before.ghost_lap_s[1]);
    expect(after.ghost_lap_s[2]).toBe(before.ghost_lap_s[2]);
    expect(after.ghost_lap_s[3]).not.toBe(before.ghost_lap_s[3]);
  });

  it("reads real lap times from laps[].lap_time_s (no real_lap_s key on race_field)", () => {
    const field = {
      meta: {
        year: 2025,
        round: 1,
        session_type: "R",
        circuit_name: "Melbourne",
        total_laps: 2,
        date_race: "2025-03-16",
        green_flag_s: 0,
        session_key: 1,
      },
      outline: { x: [], y: [] },
      drivers: [],
      laps: [
        { lap: 1, driver: "NOR", position: 1, gap_to_leader_s: 0, gap_ahead_s: 0, compound: "MEDIUM", tyre_life: 1, stint_number: 1, pit_this_lap: false, is_dnf: false, is_dsq: false, track_status: "1", lap_time_s: 90, sector_1_s: null, sector_2_s: null, sector_3_s: null },
        { lap: 2, driver: "NOR", position: 1, gap_to_leader_s: 0, gap_ahead_s: 0, compound: "MEDIUM", tyre_life: 2, stint_number: 1, pit_this_lap: false, is_dnf: false, is_dsq: false, track_status: "1", lap_time_s: 88, sector_1_s: null, sector_2_s: null, sector_3_s: null },
      ],
      stints: [],
      weather: [],
      race_control: [],
      pos_samples: {},
    } as RaceField;
    const real = realLapTimesByDriver(field, "NOR");
    expect(real[1]).toBe(90);
    expect(real[2]).toBe(88);
    const ticks = [
      { lap: 1, position: 1, gap_to_leader_s: 0, compound: "SOFT", tyre_life: 1, stint: 1, cumulative_delta_s: 0, aris_action: "STAY_OUT", aris_confidence: 1 },
      { lap: 2, position: 1, gap_to_leader_s: 0, compound: "SOFT", tyre_life: 2, stint: 1, cumulative_delta_s: 1, aris_action: "STAY_OUT", aris_confidence: 1 },
    ];
    const derived = deriveGhostLapTimes(ticks, real);
    expect(derived.ghost_lap_s.length).toBeGreaterThan(1);
    expect(derived.ghost_lap_s[1]).toBe(90);
    expect(derived.ghost_cumulative_s[1]).toBe(90);
    expect(derived.ghost_cumulative_s[2]).toBe(177);
  });

  it("fills NaN ghost_lap_s with the median of finite positive laps", () => {
    const tick = (lap: number) => ({
      lap,
      position: 1,
      gap_to_leader_s: 0,
      compound: "SOFT",
      tyre_life: lap,
      stint: 1,
      cumulative_delta_s: 0,
      aris_action: "STAY_OUT",
      aris_confidence: 1,
    });
    const derived = deriveGhostLapTimes([tick(1), tick(2), tick(3), tick(4)], [NaN, 90, 92, NaN, 94]);
    expect(derived.ghost_lap_s[1]).toBe(90);
    expect(derived.ghost_lap_s[2]).toBe(92);
    expect(derived.ghost_lap_s[3]).toBe(92);
    expect(derived.ghost_lap_s[4]).toBe(94);
    expect(derived.ghost_lap_s.slice(1).every((v) => Number.isFinite(v))).toBe(true);
    expect(derived.ghost_cumulative_s[3]).toBe(90 + 92 + 92);
    expect(derived.ghost_cumulative_s[4]).toBe(90 + 92 + 92 + 94);
    for (let i = 1; i < derived.ghost_cumulative_s.length; i++) {
      expect(derived.ghost_cumulative_s[i]).toBeGreaterThan(derived.ghost_cumulative_s[i - 1]);
    }
  });

  it("clamps non-monotonic cumulative when ghost_lap_s is negative", () => {
    const derived = deriveGhostLapTimes(
      [{ lap: 1, position: 1, gap_to_leader_s: 0, compound: "SOFT", tyre_life: 1, stint: 1, cumulative_delta_s: 100, aris_action: "STAY_OUT", aris_confidence: 1 }],
      [NaN, 90],
    );
    expect(derived.ghost_lap_s[1]).toBe(-10);
    expect(derived.ghost_cumulative_s[1]).toBeGreaterThan(0);
  });
});

describe("pitLossForCircuit", () => {
  it("maps Sakhir to Bahrain YAML pit_loss_s", () => {
    expect(pitLossForCircuit("Sakhir")).toBe(21.8);
    expect(pitLossForCircuit("Bahrain")).toBe(21.8);
  });

  it("falls back to 22s when unknown", () => {
    expect(pitLossForCircuit("Unknown GP")).toBe(22);
  });
});

describe("r2TickToGhostTick", () => {
  it("fills delta_history from ticks up to the current lap", () => {
    const ghost: GhostData = {
      driver: "ANT",
      strategy: { pit_laps: [18], compounds: ["HARD"], label: "1-stop" },
      ticks: [
        { lap: 1, position: 2, gap_to_leader_s: 0.4, compound: "MEDIUM", tyre_life: 1, stint: 1, cumulative_delta_s: 0, aris_action: "STAY_OUT", aris_confidence: 1 },
        { lap: 2, position: 2, gap_to_leader_s: 0.5, compound: "MEDIUM", tyre_life: 2, stint: 1, cumulative_delta_s: -0.3, aris_action: "STAY_OUT", aris_confidence: 1 },
        { lap: 3, position: 3, gap_to_leader_s: 1.1, compound: "MEDIUM", tyre_life: 3, stint: 1, cumulative_delta_s: 0.8, aris_action: "STAY_OUT", aris_confidence: 1 },
      ],
      outcome: { aris_action: "PIT", real_action: "STAY_OUT", verdict: null },
    };
    const mapped = r2TickToGhostTick(ghost.ticks[1], "ANT", ghost);
    expect(mapped.delta_history).toHaveLength(2);
    expect(mapped.delta_history[0]).toEqual({ lap: 1, delta: 0, ghost_pos: 2, real_pos: 0 });
    expect(mapped.delta_history[1].delta).toBe(-0.3);
    expect(mapped.ghost_cumulative_delta).toBe(-0.3);
  });
});

describe("ghostTickAtOrBefore", () => {
  const ticks = {
    1: { lap: 1, position: 2, gap_to_leader_s: 0, compound: "M", tyre_life: 1, stint: 1, cumulative_delta_s: 0, aris_action: "STAY_OUT", aris_confidence: 1 },
    3: { lap: 3, position: 3, gap_to_leader_s: 1, compound: "M", tyre_life: 3, stint: 1, cumulative_delta_s: 0.8, aris_action: "STAY_OUT", aris_confidence: 1 },
  };

  it("returns the exact lap when present", () => {
    expect(ghostTickAtOrBefore(ticks, 3)?.lap).toBe(3);
  });

  it("returns the previous tick when the current lap has no row", () => {
    expect(ghostTickAtOrBefore(ticks, 2)?.lap).toBe(1);
  });
});

describe("ghostDeltaChartPoints", () => {
  it("uses ghost ticks when ghostData is missing", () => {
    const pts = ghostDeltaChartPoints(null, {
      1: { lap: 1, position: 1, gap_to_leader_s: 0, compound: "M", tyre_life: 1, stint: 1, cumulative_delta_s: 0, aris_action: "STAY_OUT", aris_confidence: 1 },
      2: { lap: 2, position: 2, gap_to_leader_s: 0.4, compound: "M", tyre_life: 2, stint: 1, cumulative_delta_s: -0.4, aris_action: "STAY_OUT", aris_confidence: 1 },
    }, 2);
    expect(pts).toEqual([
      { lap: 1, delta: 0 },
      { lap: 2, delta: -0.4 },
    ]);
  });
});
