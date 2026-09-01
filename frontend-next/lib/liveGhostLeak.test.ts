import { afterEach, describe, expect, it } from "vitest";
import { clearLiveReplayGhost, LiveSseFeed } from "./liveFeed";
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
