import { afterEach, describe, expect, it } from "vitest";
import { clearLiveReplayGhost, finalizeGhostCar, LiveSseFeed } from "./liveFeed";
import { useRaceStore } from "@/store/raceStore";
import type { CarState, GhostData, GhostR2Tick } from "./types";

const leftoverGhost: GhostData = {
  driver: "VER",
  strategy: { pit_laps: [20], compounds: ["HARD"], label: "replay leftover" },
  ticks: [],
  outcome: { aris_action: "", real_action: "", verdict: null },
};

const leftoverTick: GhostR2Tick = {
  lap: 12,
  position: 3,
  gap_to_leader_s: 4.2,
  compound: "MEDIUM",
  tyre_life: 8,
  stint: 1,
  cumulative_delta_s: -1.1,
  aris_action: "stay_out",
  aris_confidence: 0.8,
};

function plantReplayGhost() {
  useRaceStore.getState().reset();
  useRaceStore.setState({
    selectedDriver: "NOR",
    arisDriver: "NOR",
    r2Ghost: leftoverGhost,
    ghostTicksByLap: { 12: leftoverTick },
    ghostLapS: [Number.NaN, 90, 91],
    ghostCumulativeS: [0, 90, 181],
    ghostCar: { driver_code: "VER", is_ghost: true } as CarState,
  });
}

afterEach(() => {
  useRaceStore.getState().reset();
});

describe("live replay ghost leak", () => {
  it("clears only ghost data fields, leaving driver selection intact", () => {
    plantReplayGhost();
    clearLiveReplayGhost();
    const s = useRaceStore.getState();
    expect(s.r2Ghost).toBeNull();
    expect(s.ghostTicksByLap).toEqual({});
    expect(s.ghostLapS).toEqual([]);
    expect(s.ghostCumulativeS).toEqual([0]);
    expect(s.ghostCar).toBeNull();
    expect(s.selectedDriver).toBe("NOR");
    expect(s.arisDriver).toBe("NOR");
  });

  it("clears leftover replay ghost when the live SSE feed connects, not on payload", () => {
    plantReplayGhost();
    const feed = new LiveSseFeed();
    feed.connect();
    const s = useRaceStore.getState();
    expect(s.r2Ghost).toBeNull();
    expect(s.ghostTicksByLap).toEqual({});
    expect(s.ghostLapS).toEqual([]);
    expect(s.ghostCumulativeS).toEqual([0]);
    expect(s.ghostCar).toBeNull();
    expect(s.selectedDriver).toBe("NOR");
    feed.disconnect();

    expect(String(LiveSseFeed.prototype.connect)).toContain("clearLiveReplayGhost");
    const apply = (LiveSseFeed.prototype as unknown as { applyPayload?: () => void }).applyPayload;
    if (typeof apply === "function") {
      expect(String(apply)).not.toContain("clearLiveReplayGhost");
    }
  });
});

describe("live ghost tower position", () => {
  function car(over: Partial<CarState>): CarState {
    return {
      driver_code: "NOR",
      driver_number: 4,
      full_name: "Lando",
      team: "MCL",
      team_colour: "#ff8000",
      position: 2,
      lap_number: 18,
      compound: "MEDIUM",
      tyre_life: 8,
      gap_to_leader_s: 1.2,
      gap_ahead_s: 1.2,
      gap_ahead_history: [],
      last_lap_s: 83,
      pit_stops: 0,
      is_pitted: false,
      is_dnf: false,
      x: 0,
      y: 0,
      speed_kph: 300,
      heading_rad: 0,
      laps_remaining: 35,
      total_laps: 53,
      ...over,
    };
  }

  it("keeps simulated tick position when the real driver loses places (live, elapsed=0)", () => {
    const field = {
      VER: car({ driver_code: "VER", position: 1, gap_to_leader_s: 0, gap_ahead_s: 0 }),
      NOR: car({ driver_code: "NOR", position: 7, gap_to_leader_s: 22, gap_ahead_s: 4 }),
      LEC: car({ driver_code: "LEC", position: 2, gap_to_leader_s: 1.4 }),
      HAM: car({ driver_code: "HAM", position: 3, gap_to_leader_s: 2.1 }),
      RUS: car({ driver_code: "RUS", position: 4, gap_to_leader_s: 3 }),
      PIA: car({ driver_code: "PIA", position: 5, gap_to_leader_s: 8 }),
      ALO: car({ driver_code: "ALO", position: 6, gap_to_leader_s: 12 }),
    };
    useRaceStore.setState({
      consoleMode: "live",
      replayElapsedS: 0,
      currentLap: 18,
      cars: field,
      isARISOn: true,
    });
    const ghost = car({
      driver_code: "A_NOR",
      is_ghost: true,
      position: 7,
      ghost_cumulative_delta: -0.4,
    });
    const placed = finalizeGhostCar(ghost, field.NOR, 2);
    expect(placed.position).toBe(2);
    expect(placed.position).not.toBe(field.NOR.position);
  });
});
