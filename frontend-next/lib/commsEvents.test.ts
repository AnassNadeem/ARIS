import { describe, expect, it } from "vitest";
import { detectCommsEvents, type CommsSnapshot } from "./commsEvents";
import type { CarState } from "./types";

function car(partial: Partial<CarState> & { driver_code: string }): CarState {
  return {
    driver_number: 1,
    full_name: partial.driver_code,
    team: "",
    team_colour: "#fff",
    position: 2,
    lap_number: 12,
    compound: "MEDIUM",
    tyre_life: 10,
    gap_to_leader_s: 4,
    gap_ahead_s: 1.2,
    gap_ahead_history: [],
    last_lap_s: 72,
    pit_stops: 0,
    is_pitted: false,
    is_dnf: false,
    status: "RUNNING",
    x: 0,
    y: 0,
    speed_kph: 280,
    heading_rad: 0,
    laps_remaining: 50,
    total_laps: 72,
    ...partial,
  };
}

function snap(over: Partial<CommsSnapshot> = {}): CommsSnapshot {
  const ham = car({ driver_code: "HAM", position: 2, sector2_s: 24.4, gap_ahead_s: 1.1 });
  const nor = car({ driver_code: "NOR", position: 1, sector2_s: 23.9, gap_to_leader_s: 0, gap_ahead_s: 0 });
  return {
    lap: 12,
    phase: "GREEN",
    rainfall: false,
    cars: { HAM: ham, NOR: nor },
    focus: "HAM",
    rec: null,
    ...over,
  };
}

describe("detectCommsEvents", () => {
  it("narrates SC deployment", () => {
    const msgs = detectCommsEvents(snap(), snap({ phase: "SC" }), 1);
    expect(msgs.some((m) => m.text.includes("SC deployed"))).toBe(true);
  });

  it("narrates rain start/stop", () => {
    const start = detectCommsEvents(snap({ rainfall: false }), snap({ rainfall: true }), 1);
    expect(start[0]?.text).toContain("Rain started");
    const stop = detectCommsEvents(snap({ rainfall: true }), snap({ rainfall: false }), 1);
    expect(stop[0]?.text).toContain("Rain stopped");
  });

  it("narrates a new DNF", () => {
    const prev = snap();
    const next = snap({
      cars: {
        ...prev.cars,
        ALO: car({ driver_code: "ALO", is_dnf: true, status: "DNF", position: 20 }),
      },
    });
    const msgs = detectCommsEvents(prev, next, 1);
    expect(msgs.some((m) => m.text.includes("DNF: ALO"))).toBe(true);
  });

  it("narrates sector loss vs car ahead on a new lap", () => {
    const prev = snap({ lap: 11 });
    const next = snap({ lap: 12 });
    const msgs = detectCommsEvents(prev, next, 1);
    expect(msgs.some((m) => m.text.includes("Lost") && m.text.includes("S2"))).toBe(true);
  });

  it("narrates undercut from a new recommendation", () => {
    const rec = {
      id: "r1",
      lap: 12,
      rank: 1,
      label: "Pit now",
      action: { kind: "pit_now" as const, pit_lap: 12, pit_compound: "HARD" as const },
      delta_vs_stay_out_s: -2.1,
      mean_race_time_s: 0,
      confidence_std_s: 0.4,
      p10_delta_s: -3,
      p90_delta_s: -1,
      evidence: "dynamic undercut bonus",
      narration_context: {},
      tactical: "Undercut window open",
      extrapolation_beyond_laps: 0,
      extrapolation_weight: 1,
      wet_heuristic: false,
      cql_q_delta: 0,
      rank_score: 0.8,
    };
    const msgs = detectCommsEvents(snap(), snap({ rec }), 1);
    expect(msgs.some((m) => m.text.includes("Undercut opportunity vs NOR"))).toBe(true);
  });
});
