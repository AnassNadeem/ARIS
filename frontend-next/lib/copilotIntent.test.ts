import { describe, expect, it } from "vitest";
import { answerFactualLive, classifyIntent, historyLookupHint } from "./copilotIntent";
import type { CarState, SessionMeta } from "./types";

function car(over: Partial<CarState>): CarState {
  return {
    driver_code: "VER",
    driver_number: 1,
    full_name: "Max",
    team: "RBR",
    team_colour: "#3671C6",
    position: 1,
    lap_number: 12,
    compound: "MEDIUM",
    tyre_life: 8,
    gap_to_leader_s: 0,
    gap_ahead_s: 0,
    gap_ahead_history: [],
    last_lap_s: 90,
    pit_stops: 0,
    is_pitted: false,
    is_dnf: false,
    x: 0,
    y: 0,
    speed_kph: 280,
    heading_rad: 0,
    laps_remaining: 40,
    total_laps: 52,
    ...over,
  };
}

const session: SessionMeta = {
  year: 2026,
  round: 6,
  sessionType: "R",
  circuitName: "Miami",
  countryFlag: "🇺🇸",
  totalLaps: 57,
  date: "2026-05-03",
  driverCode: "ANT",
};

describe("classifyIntent", () => {
  it("routes gap/leader questions as live facts", () => {
    expect(classifyIntent("What's the gap to the leader?")).toBe("factual_live");
    expect(classifyIntent("Who's leading?")).toBe("factual_live");
  });
  it("routes last-year winner as history", () => {
    expect(classifyIntent("Who won last year?")).toBe("factual_history");
  });
  it("keeps strategy questions on the LLM/tool path", () => {
    expect(classifyIntent("What's the best strategy from here?")).toBe("strategic");
  });
});

describe("answerFactualLive", () => {
  const snap = {
    cars: {
      VER: car({ driver_code: "VER", position: 1, gap_to_leader_s: 0 }),
      NOR: car({ driver_code: "NOR", position: 2, gap_to_leader_s: 1.8, gap_ahead_s: 1.8, compound: "SOFT" as const, tyre_life: 12 }),
    },
    currentLap: 14,
    totalLaps: 57,
    racePhase: "GREEN" as const,
    rainfall: false,
    focusDriver: "NOR",
    session,
  };

  it("names the leader from the timing store", () => {
    expect(answerFactualLive("Who's leading?", snap)).toMatch(/VER is leading/);
  });

  it("reports gap to leader for the focus driver", () => {
    expect(answerFactualLive("What's the gap to the leader?", snap)).toMatch(/NOR is P2/);
  });

  it("returns null for strategy questions", () => {
    expect(answerFactualLive("Should we pit now?", snap)).toBeNull();
  });
});

describe("historyLookupHint", () => {
  it("subtracts a year for last-year questions", () => {
    expect(historyLookupHint("Who won last year?", session)).toEqual({
      year: 2025,
      round: 6,
      lastYear: true,
    });
  });
});
