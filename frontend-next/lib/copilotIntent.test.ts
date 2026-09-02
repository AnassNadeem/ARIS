import { describe, expect, it } from "vitest";
import { answerFactualLive, classifyIntent, historyLookupHint } from "./copilotIntent";
import type { ARISRecommendation, CarState, SessionMeta } from "./types";

function car(over: Partial<CarState>): CarState {
  return {
    driver_code: "VER",
    driver_number: 1,
    full_name: "Max Verstappen",
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

const rec: ARISRecommendation = {
  id: "r1",
  lap: 28,
  rank: 1,
  label: "Pit lap 28 for HARD",
  action: { kind: "pit_lap", pit_lap: 28, pit_compound: "HARD" },
  delta_vs_stay_out_s: -3.4,
  mean_race_time_s: 0,
  confidence_std_s: 1.1,
  p10_delta_s: -5.1,
  p90_delta_s: -1.7,
  evidence: "Gap ahead 1.8s, undercut window open",
  narration_context: {},
  tactical: "Undercut window open",
  extrapolation_beyond_laps: 0,
  extrapolation_weight: 1,
  wet_heuristic: false,
  cql_q_delta: 0,
  rank_score: 0.82,
};

describe("classifyIntent", () => {
  it("routes gap/leader questions as live facts", () => {
    expect(classifyIntent("What's the gap to the leader?")).toBe("factual_live");
    expect(classifyIntent("Who's leading?")).toBe("factual_live");
    expect(classifyIntent("Who is in the lead?")).toBe("factual_live");
    expect(classifyIntent("Who leads?")).toBe("factual_live");
  });
  it("routes tyre questions as live facts", () => {
    expect(classifyIntent("What tyres is VER on?")).toBe("factual_live");
    expect(classifyIntent("What tyres is Verstappen on?")).toBe("factual_live");
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
      VER: car({ driver_code: "VER", position: 1, gap_to_leader_s: 0, full_name: "Max Verstappen" }),
      NOR: car({
        driver_code: "NOR",
        position: 2,
        gap_to_leader_s: 1.8,
        gap_ahead_s: 1.8,
        compound: "SOFT" as const,
        tyre_life: 12,
        full_name: "Lando Norris",
      }),
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
    expect(answerFactualLive("Who is in the lead?", snap)).toMatch(/VER is leading/);
    expect(answerFactualLive("Who leads?", snap)).toMatch(/VER is leading/);
  });

  it("reports gap to leader for the focus driver", () => {
    expect(answerFactualLive("What's the gap to the leader?", snap)).toMatch(/NOR is P2/);
  });

  it("answers tyre questions from the store by code and surname", () => {
    expect(answerFactualLive("What tyres is VER on?", snap)).toBe(
      "VER is on MEDIUM, tyre life 8 laps.",
    );
    expect(answerFactualLive("What tyres is Verstappen on?", snap)).toBe(
      "VER is on MEDIUM, tyre life 8 laps.",
    );
  });

  it("uses the focus driver when no one is named", () => {
    expect(answerFactualLive("What tyres are we on?", snap)).toBe(
      "NOR is on SOFT, tyre life 12 laps.",
    );
  });

  it("says when the named driver is in the pit lane", () => {
    const pitted = {
      ...snap,
      cars: {
        ...snap.cars,
        VER: car({ driver_code: "VER", is_pitted: true, full_name: "Max Verstappen" }),
      },
    };
    expect(answerFactualLive("What tyres is VER on?", pitted)).toBe(
      "VER is currently in the pit lane.",
    );
  });

  it("falls through when a named driver is not in the frame", () => {
    expect(answerFactualLive("What tyres is HAM on?", snap)).toBeNull();
  });

  it("reports position for a named driver", () => {
    expect(answerFactualLive("What position is Verstappen?", snap)).toMatch(/VER is P1/);
  });

  it("reports laps remaining from the store", () => {
    expect(answerFactualLive("How many laps remaining?", snap)).toBe(
      "Lap 14 of 57. 43 laps remaining.",
    );
    expect(answerFactualLive("How many laps left?", snap)).toMatch(/43 laps remaining/);
  });

  it("does not treat two-compound rules as a live tyre lookup", () => {
    expect(answerFactualLive("Do drivers have to use two compounds in a dry race?", snap)).toBeNull();
  });

  it("leaves Copilot tool questions on the API path", () => {
    expect(answerFactualLive("What's the best strategy from here?", snap)).toBeNull();
  });

  it("answers should-I-pit from lastRecommendation", () => {
    const withRec = { ...snap, lastRecommendation: rec, ghostPosition: 4 };
    const text = answerFactualLive("Should I pit now?", withRec);
    expect(text).toMatch(/Pit lap 28 for HARD/);
    expect(text).toMatch(/-3\.4s vs stay-out/);
    expect(text).toMatch(/Confidence: 82%/);
    expect(text).toMatch(/ARIS ghost is currently P4/);
    expect(text).not.toMatch(/recommend button/);
  });

  it("says ARIS has not recommended yet when the store is empty", () => {
    const empty = { ...snap, lastRecommendation: null };
    expect(answerFactualLive("Should we pit now?", empty)).toMatch(/has not made a recommendation/);
    expect(answerFactualLive("Should I pit now?", empty)).toMatch(/has not made a recommendation/);
  });

  it("does not intercept pit questions on the Copilot path", () => {
    expect(answerFactualLive("Should we pit now?", snap)).toBeNull();
  });

  it("answers why-recommend from evidence, not lap count", () => {
    const withRec = { ...snap, lastRecommendation: rec };
    const text = answerFactualLive("Why did ARIS recommend pitting on lap 28?", withRec);
    expect(text).toMatch(/ARIS recommended Pit lap 28 for HARD because:/);
    expect(text).toMatch(/undercut window open/i);
    expect(text).not.toMatch(/laps remaining/);
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
