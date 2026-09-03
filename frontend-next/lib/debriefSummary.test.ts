import { describe, expect, it } from "vitest";
import { ghostVsRealFromField, lastClassifiedLap, raceFinishSummary, buildRaceStory } from "./debriefSummary";
import type { CarState, GhostR2Tick, RaceField } from "./types";

function field(): RaceField {
  return {
    meta: {
      year: 2026,
      round: 14,
      session_type: "R",
      circuit_name: "Hungaroring",
      total_laps: 2,
      date_race: "2026-07-26",
      green_flag_s: 0,
      session_key: 1,
    },
    outline: { x: [], y: [] },
    drivers: [
      { code: "PIA", name: "Piastri", team: "MCL", colour: "#f80", grid_position: 1 },
      { code: "NOR", name: "Norris", team: "MCL", colour: "#f80", grid_position: 2 },
      { code: "VER", name: "Verstappen", team: "RBR", colour: "#00f", grid_position: 3 },
    ],
    laps: [
      { lap: 1, driver: "PIA", position: 1, gap_to_leader_s: 0, gap_ahead_s: 0, compound: "MEDIUM", tyre_life: 1, stint_number: 1, pit_this_lap: false, is_dnf: false, is_dsq: false, track_status: "1", lap_time_s: 80, sector_1_s: null, sector_2_s: null, sector_3_s: null },
      { lap: 1, driver: "NOR", position: 2, gap_to_leader_s: 0.9, gap_ahead_s: 0.9, compound: "MEDIUM", tyre_life: 1, stint_number: 1, pit_this_lap: false, is_dnf: false, is_dsq: false, track_status: "1", lap_time_s: 81, sector_1_s: null, sector_2_s: null, sector_3_s: null },
      { lap: 1, driver: "VER", position: 3, gap_to_leader_s: 2.0, gap_ahead_s: 1.1, compound: "MEDIUM", tyre_life: 1, stint_number: 1, pit_this_lap: false, is_dnf: false, is_dsq: false, track_status: "1", lap_time_s: 82, sector_1_s: null, sector_2_s: null, sector_3_s: null },
      { lap: 2, driver: "PIA", position: 1, gap_to_leader_s: 0, gap_ahead_s: 0, compound: "MEDIUM", tyre_life: 2, stint_number: 1, pit_this_lap: false, is_dnf: false, is_dsq: false, track_status: "1", lap_time_s: 80, sector_1_s: null, sector_2_s: null, sector_3_s: null },
      { lap: 2, driver: "NOR", position: 3, gap_to_leader_s: 12.3, gap_ahead_s: 4, compound: "HARD", tyre_life: 1, stint_number: 2, pit_this_lap: true, is_dnf: false, is_dsq: false, track_status: "1", lap_time_s: 100, sector_1_s: null, sector_2_s: null, sector_3_s: null },
      { lap: 2, driver: "VER", position: 2, gap_to_leader_s: 8.0, gap_ahead_s: 8, compound: "MEDIUM", tyre_life: 2, stint_number: 1, pit_this_lap: false, is_dnf: false, is_dsq: false, track_status: "1", lap_time_s: 81, sector_1_s: null, sector_2_s: null, sector_3_s: null },
    ],
    stints: [],
    weather: [],
    race_control: [],
    pos_samples: {},
  };
}

const baseCar = {
  driver_number: 4,
  full_name: "Lando",
  team: "MCL",
  team_colour: "#f80",
  lap_number: 2,
  compound: "HARD" as const,
  tyre_life: 1,
  gap_ahead_s: 4,
  gap_ahead_history: [],
  last_lap_s: 100,
  pit_stops: 1,
  is_pitted: false,
  is_dnf: false,
  x: 0,
  y: 0,
  speed_kph: 0,
  heading_rad: 0,
  laps_remaining: 0,
  total_laps: 2,
} satisfies Omit<CarState, "driver_code" | "position" | "gap_to_leader_s">;

describe("raceFinishSummary", () => {
  it("uses the pack finishing position for real and the tower ghost car for ARIS", () => {
    const pack = field();
    const cars = {
      NOR: { ...baseCar, driver_code: "NOR", position: 3, gap_to_leader_s: 12.3 },
    };
    const ghost: CarState = {
      ...baseCar,
      driver_code: "A_NOR",
      is_ghost: true,
      position: 2,
      gap_to_leader_s: 11.3,
      ghost_cumulative_delta: 1.0,
    };
    const summary = raceFinishSummary({ driver: "NOR", field: pack, cars, ghostCar: ghost });
    expect(lastClassifiedLap(pack, "NOR")?.position).toBe(3);
    expect(summary.realPos).toBe(3);
    expect(summary.realGap).toBe(12.3);
    expect(summary.ghostPos).toBe(2);
    expect(summary.ghostGap).toBe(11.3);
  });

  it("ranks from the last ghost tick when the tower car is missing", () => {
    const pack = field();
    const ticks: Record<number, GhostR2Tick> = {
      2: {
        lap: 2,
        position: 23,
        gap_to_leader_s: 999,
        compound: "HARD",
        tyre_life: 1,
        stint: 2,
        cumulative_delta_s: 5.0,
        aris_action: "STAY_OUT",
        aris_confidence: 1,
      },
    };
    const summary = raceFinishSummary({
      driver: "NOR",
      field: pack,
      cars: {},
      ghostCar: null,
      ghostTicks: ticks,
    });
    expect(summary.realPos).toBe(3);
    expect(summary.ghostGap).toBeCloseTo(7.3, 5);
    expect(summary.ghostPos).toBe(2);
  });
});

describe("ghostVsRealFromField", () => {
  it("does not use stale tick position; real series is classified laps", () => {
    const pack = field();
    const ticks: Record<number, GhostR2Tick> = {
      1: { lap: 1, position: 23, gap_to_leader_s: 0, compound: "MEDIUM", tyre_life: 1, stint: 1, cumulative_delta_s: 0, aris_action: "STAY_OUT", aris_confidence: 1 },
      2: { lap: 2, position: 23, gap_to_leader_s: 0, compound: "HARD", tyre_life: 1, stint: 2, cumulative_delta_s: 5, aris_action: "STAY_OUT", aris_confidence: 1 },
    };
    const series = ghostVsRealFromField(pack, "NOR", ticks);
    expect(series?.real.position).toEqual([2, 3]);
    expect(series?.ghost.position[0]).toBe(2);
    expect(series?.ghost.position[1]).toBe(2);
  });
});

describe("buildRaceStory", () => {
  it("explains a pit drop as an overtake and a stop", () => {
    const story = buildRaceStory({ driver: "NOR", field: field(), compare: null });
    expect(story.headline).toContain("NOR");
    expect(story.lines.some((l) => /pitted/i.test(l) && /P2/i.test(l))).toBe(true);
  });
});
