import { describe, expect, it } from "vitest";
import { sessionFlagToPhase } from "./mapCars";
import { resolveSessionFlag, raceDurationS, lapToElapsed, STANDING_START_HOLD_S } from "./r2Replay";
import type { RaceField } from "./types";

describe("sessionFlagToPhase standing start", () => {
  it("maps STANDING_START", () => {
    expect(sessionFlagToPhase("STANDING_START")).toBe("STANDING_START");
    expect(sessionFlagToPhase("STANDING START")).toBe("STANDING_START");
  });

  it("does not treat RED FLAG CLEARED as red", () => {
    expect(sessionFlagToPhase("RED FLAG CLEARED")).toBe("GREEN");
  });

  it("does not treat CHEQUERED FLAG as red", () => {
    expect(sessionFlagToPhase("CHEQUERED FLAG")).toBe("GREEN");
    expect(sessionFlagToPhase("FINISHED")).toBe("GREEN");
  });

  it("maps YELLOW", () => {
    expect(sessionFlagToPhase("YELLOW")).toBe("YELLOW");
  });
});

describe("resolveSessionFlag + red-flag playback compression", () => {
  const field = {
    meta: {
      year: 2026,
      round: 16,
      session_type: "R",
      circuit_name: "Monza",
      total_laps: 5,
      date_race: "",
      green_flag_s: 0,
      session_key: null,
    },
    outline: { x: [0, 1], y: [0, 1] },
    drivers: [{ code: "NOR", name: "Norris", team: "MCL", colour: "#f80", grid_position: 1 }],
    laps: [
      { lap: 1, driver: "NOR", position: 1, gap_to_leader_s: 0, gap_ahead_s: 0, compound: "M", tyre_life: 1, stint_number: 1, pit_this_lap: false, is_dnf: false, is_dsq: false, track_status: "1", lap_time_s: 90, sector_1_s: null, sector_2_s: null, sector_3_s: null },
      { lap: 2, driver: "NOR", position: 1, gap_to_leader_s: 0, gap_ahead_s: 0, compound: "M", tyre_life: 2, stint_number: 1, pit_this_lap: false, is_dnf: false, is_dsq: false, track_status: "1", lap_time_s: 90, sector_1_s: null, sector_2_s: null, sector_3_s: null },
      { lap: 3, driver: "NOR", position: 1, gap_to_leader_s: 0, gap_ahead_s: 0, compound: "M", tyre_life: 3, stint_number: 1, pit_this_lap: false, is_dnf: false, is_dsq: false, track_status: "5", lap_time_s: 150, sector_1_s: null, sector_2_s: null, sector_3_s: null },
      { lap: 4, driver: "NOR", position: 1, gap_to_leader_s: 0, gap_ahead_s: 0, compound: "M", tyre_life: 4, stint_number: 1, pit_this_lap: false, is_dnf: false, is_dsq: false, track_status: "1", lap_time_s: 1948, sector_1_s: null, sector_2_s: null, sector_3_s: null },
      { lap: 5, driver: "NOR", position: 1, gap_to_leader_s: 0, gap_ahead_s: 0, compound: "M", tyre_life: 5, stint_number: 1, pit_this_lap: false, is_dnf: false, is_dsq: false, track_status: "1", lap_time_s: 90, sector_1_s: null, sector_2_s: null, sector_3_s: null },
    ],
    stints: [],
    weather: [],
    race_control: [
      { lap: 3, message: "RED FLAG - RACE SUSPENDED", flag: null, category: null },
      { lap: 4, message: "STANDING START", flag: null, category: null },
    ],
    pos_samples: {},
  } as RaceField;

  it("shows RED on the red-flag lap", () => {
    const t = lapToElapsed(field, 3) + 1;
    expect(resolveSessionFlag(field, 3, t)).toBe("RED");
  });

  it("shows STANDING_START briefly then clears on that lap", () => {
    const start = lapToElapsed(field, 4);
    expect(resolveSessionFlag(field, 4, start + 1)).toBe("STANDING_START");
    expect(resolveSessionFlag(field, 4, start + STANDING_START_HOLD_S + 0.5)).toBe("GREEN");
  });

  it("does not keep STANDING_START on later laps", () => {
    const t = lapToElapsed(field, 5) + 1;
    expect(resolveSessionFlag(field, 5, t)).toBe("GREEN");
  });

  it("compresses the 1948s standing-start hold for playback", () => {
    const lap4 = lapToElapsed(field, 5) - lapToElapsed(field, 4);
    const lap3 = lapToElapsed(field, 4) - lapToElapsed(field, 3);
    expect(lap4).toBeLessThanOrEqual(8);
    expect(lap3).toBeLessThanOrEqual(16);
    expect(raceDurationS(field)).toBeLessThan(90 * 3 + 16 + 8 + 1);
  });

  it("marks a lap with sector yellows as YELLOW when not SC/red", () => {
    const yellowField = {
      ...field,
      race_control: [{ lap: 2, message: "YELLOW IN TRACK SECTOR 2", flag: "YELLOW", category: "Flag" }],
    } as RaceField;
    const t = lapToElapsed(yellowField, 2) + 1;
    expect(resolveSessionFlag(yellowField, 2, t)).toBe("YELLOW");
  });
});

describe("resolveSessionFlag chequered is not red", () => {
  const field = {
    meta: {
      year: 2026,
      round: 16,
      session_type: "R",
      circuit_name: "Monza",
      total_laps: 53,
      date_race: "",
      green_flag_s: 0,
      session_key: null,
    },
    outline: { x: [0, 1], y: [0, 1] },
    drivers: [{ code: "VER", name: "Verstappen", team: "RBR", colour: "#00f", grid_position: 5 }],
    laps: Array.from({ length: 53 }, (_, i) => ({
      lap: i + 1,
      driver: "VER",
      position: 1,
      gap_to_leader_s: 0,
      gap_ahead_s: 0,
      compound: "H",
      tyre_life: i + 1,
      stint_number: 1,
      pit_this_lap: false,
      is_dnf: false,
      is_dsq: false,
      track_status: "1",
      lap_time_s: 80,
      sector_1_s: null,
      sector_2_s: null,
      sector_3_s: null,
    })),
    stints: [],
    weather: [],
    race_control: [
      { lap: 53, message: "CHEQUERED FLAG", flag: "CHEQUERED", category: "Flag" },
    ],
    pos_samples: {},
  } as RaceField;

  it("shows FINISHED, not RED, on CHEQUERED FLAG", () => {
    const t = lapToElapsed(field, 53) + 1;
    expect(resolveSessionFlag(field, 53, t)).toBe("FINISHED");
  });
});
