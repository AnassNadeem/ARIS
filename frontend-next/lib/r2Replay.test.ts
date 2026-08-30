import { describe, expect, it } from "vitest";
import { annotateVsActivePlan, shouldFetchRecommend } from "./arisRecommend";
import { mapTimingAndPositions } from "./mapCars";
import { fieldToDrivers, fieldToLapRows, interpolatedPosFrac, nearestPosSample, plansMatch, r2Configured, r2FrameAt, raceDurationS, sectorSecondsForLap, speedKphFromPath } from "./r2Replay";
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
    expect(pos?.path_frac).toBeCloseTo(0.4825, 5);
    const cars = mapTimingAndPositions(frame.timing, frame.positions, fieldToDrivers(field), 22, frame.lap);
    expect(cars.VER.path_frac).toBeCloseTo(0.4825, 5);
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

  it("returns the exact sample at the first lap_frac", () => {
    expect(interpolatedPosFrac(samples, 20.0)).toBe(0.1);
  });

  it("returns the exact sample at the last lap_frac", () => {
    expect(interpolatedPosFrac(samples, 20.8)).toBe(0.72);
  });

  it("clamps to the last sample after the range", () => {
    expect(interpolatedPosFrac(samples, 21.0)).toBe(0.72);
  });
});
