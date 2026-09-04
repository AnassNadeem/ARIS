import { describe, expect, it } from "vitest";
import {
  applyLiveHubSessionWindows,
  official2026SessionTimes,
  sessionClockStatus,
  sessionIsLiveNow,
} from "./sessionWindow";
import type { HubSession, LiveHub } from "./types";

function sess(partial: Partial<HubSession> & Pick<HubSession, "session_type">): HubSession {
  return {
    session_name: partial.session_type,
    datetime_utc: null,
    status: "UPCOMING",
    replayable: false,
    live: false,
    ...partial,
  };
}

const MONZA_HUB: LiveHub = {
  mode: "waiting_for_session",
  waiting_reason: "Waiting for Free Practice 1.",
  countdown_seconds: 2147,
  countdown_target: "2026-09-04T11:30:00Z",
  live: {
    is_live: false,
    year: 2026,
    round_number: 13,
    session_type: "FP1",
    session_name: "Free Practice 1",
    gp_name: "Italy",
    current_lap: null,
    total_laps: null,
    session_flag: null,
    session_ended: false,
  },
  next: {
    year: 2026,
    round_number: 13,
    name: "Italy",
    circuit_name: "Autodromo Nazionale Monza",
    circuit_key: "italy",
    country: "Italy",
    city: "Monza",
    date_race: "2026-09-06T13:00:00Z",
    status: "UPCOMING",
    is_sprint_weekend: false,
    is_this_weekend: true,
    countdown_seconds: 2147,
    next_session_name: "Free Practice 1",
    next_session_datetime: "2026-09-04T11:30:00Z",
    notes: [],
  },
  weekend_sessions: [
    sess({ session_type: "FP1", session_name: "Free Practice 1", datetime_utc: "2026-09-04T11:30:00Z" }),
    sess({ session_type: "FP2", session_name: "Free Practice 2", datetime_utc: "2026-09-04T15:00:00Z" }),
    sess({ session_type: "R", session_name: "Race", datetime_utc: "2026-09-06T13:00:00Z" }),
  ],
  circuit: {
    circuit_key: "italy",
    circuit_name: "Autodromo Nazionale Monza",
    country: "Italy",
    country_flag: "🇮🇹",
    length_km: 5.793,
    total_laps: 53,
    turns: 11,
    pit_loss_seconds: 21,
    tyre_stress_rating: "MEDIUM",
    strategy_patterns: [],
    race_history: [],
    notes: [],
  },
  as_of: "2026-09-04T10:54:00Z",
};

describe("official2026SessionTimes", () => {
  it("maps Monza FP1 to 10:30 UTC, not the 11:30 estimate", () => {
    const times = official2026SessionTimes("Autodromo Nazionale Monza", "italy", 2026);
    expect(times?.FP1).toBe("2026-09-04T10:30:00Z");
    expect(times?.FP2).toBe("2026-09-04T14:00:00Z");
  });
});

describe("sessionClockStatus", () => {
  const start = "2026-09-04T10:30:00Z";

  it("is live shortly after the official FP1 start", () => {
    expect(sessionClockStatus(start, "FP1", Date.parse("2026-09-04T10:45:00Z"))).toBe("LIVE");
  });

  it("is upcoming before lights out", () => {
    expect(sessionClockStatus(start, "FP1", Date.parse("2026-09-04T10:29:00Z"))).toBe("UPCOMING");
  });

  it("completes after the practice window", () => {
    expect(sessionClockStatus(start, "FP1", Date.parse("2026-09-04T12:00:00Z"))).toBe("COMPLETED");
  });
});

describe("applyLiveHubSessionWindows", () => {
  it("flips Monza to live_session during official FP1 even if the API still counts down to 11:30", () => {
    const hub = applyLiveHubSessionWindows(MONZA_HUB, Date.parse("2026-09-04T10:54:00Z"));
    expect(hub.mode).toBe("live_session");
    expect(hub.waiting_reason).toBeNull();
    expect(hub.live.is_live).toBe(true);
    const fp1 = hub.weekend_sessions.find((s) => s.session_type === "FP1");
    expect(fp1?.datetime_utc).toBe("2026-09-04T10:30:00Z");
    expect(fp1?.live).toBe(true);
    expect(fp1?.status).toBe("LIVE");
    expect(hub.countdown_target).toBe("2026-09-04T10:30:00Z");
  });

  it("keeps the countdown before FP1", () => {
    const hub = applyLiveHubSessionWindows(MONZA_HUB, Date.parse("2026-09-04T10:00:00Z"));
    expect(hub.mode).toBe("waiting_for_session");
    expect(hub.weekend_sessions[0]?.live).toBe(false);
    expect(hub.countdown_seconds).toBeGreaterThan(0);
  });

  it("after FP1, counts down to FP2 instead of staying live", () => {
    const hub = applyLiveHubSessionWindows(MONZA_HUB, Date.parse("2026-09-04T12:00:00Z"));
    expect(hub.mode).toBe("waiting_for_session");
    expect(hub.live.is_live).toBe(false);
    const fp1 = hub.weekend_sessions.find((s) => s.session_type === "FP1");
    const fp2 = hub.weekend_sessions.find((s) => s.session_type === "FP2");
    expect(fp1?.status).toBe("COMPLETED");
    expect(fp1?.replayable).toBe(true);
    expect(fp2?.status).toBe("UPCOMING");
    expect(hub.countdown_target).toBe("2026-09-04T14:00:00Z");
  });

  it("marks FP2 replayable after the practice window", () => {
    const hub = applyLiveHubSessionWindows(MONZA_HUB, Date.parse("2026-09-04T15:20:00Z"));
    const fp2 = hub.weekend_sessions.find((s) => s.session_type === "FP2");
    expect(fp2?.status).toBe("COMPLETED");
    expect(fp2?.replayable).toBe(true);
    expect(hub.live.is_live).toBe(false);
  });

  it("opens FP2 as live at the official 16:00 CEST start", () => {
    const hub = applyLiveHubSessionWindows(MONZA_HUB, Date.parse("2026-09-04T14:05:00Z"));
    expect(hub.mode).toBe("live_session");
    const fp2 = hub.weekend_sessions.find((s) => s.session_type === "FP2");
    expect(fp2?.status).toBe("LIVE");
    expect(fp2?.live).toBe(true);
  });
});

describe("sessionIsLiveNow", () => {
  it("treats a live flag as live during the window", () => {
    expect(
      sessionIsLiveNow(
        sess({
          session_type: "FP1",
          live: true,
          status: "LIVE",
          datetime_utc: "2026-09-04T10:30:00Z",
        }),
        Date.parse("2026-09-04T10:50:00Z"),
      ),
    ).toBe(true);
  });
});
