import { describe, expect, it } from "vitest";
import {
  asSessionType,
  autoArisForHubSession,
  hubSessionCta,
  liveHubSession,
  pickArisHubSession,
  pickDefaultHubSession,
  shouldAutoStartLiveSession,
} from "./liveSetup";
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

describe("pickDefaultHubSession", () => {
  it("prefers a live session", () => {
    const sessions = [
      sess({ session_type: "FP1", status: "COMPLETED", replayable: true }),
      sess({ session_type: "Q", live: true, status: "LIVE" }),
      sess({ session_type: "R", status: "UPCOMING", datetime_utc: "2099-01-01T12:00:00Z" }),
    ];
    expect(pickDefaultHubSession(sessions)?.session_type).toBe("Q");
  });

  it("falls back to the most recent completed session for replay", () => {
    const sessions = [
      sess({ session_type: "FP1", status: "COMPLETED", replayable: true }),
      sess({ session_type: "FP2", status: "COMPLETED", replayable: true }),
      sess({ session_type: "R", status: "UPCOMING", datetime_utc: "2099-01-02T12:00:00Z" }),
    ];
    expect(pickDefaultHubSession(sessions)?.session_type).toBe("FP2");
  });

  it("falls back to the soonest upcoming session when nothing has run", () => {
    const sessions = [
      sess({ session_type: "R", status: "UPCOMING", datetime_utc: "2099-01-02T12:00:00Z" }),
      sess({ session_type: "Q", status: "UPCOMING", datetime_utc: "2099-01-01T12:00:00Z" }),
    ];
    expect(pickDefaultHubSession(sessions)?.session_type).toBe("Q");
  });

  it("treats an in-window session as live even if the API flag lagged", () => {
    const start = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    const sessions = [
      sess({ session_type: "FP1", status: "UPCOMING", datetime_utc: start }),
      sess({ session_type: "R", status: "UPCOMING", datetime_utc: "2099-01-01T12:00:00Z" }),
    ];
    expect(pickDefaultHubSession(sessions)?.session_type).toBe("FP1");
  });
});

describe("asSessionType", () => {
  it("maps known codes and defaults unknown to Race", () => {
    expect(asSessionType("fp1")).toBe("FP1");
    expect(asSessionType("XX")).toBe("R");
  });
});

describe("shouldAutoStartLiveSession", () => {
  const hub = {
    mode: "waiting_for_session",
    live: { is_live: false },
    weekend_sessions: [
      sess({ session_type: "FP1", status: "UPCOMING" }),
      sess({ session_type: "R", status: "UPCOMING", datetime_utc: "2099-01-01T12:00:00Z" }),
    ],
  } as LiveHub;

  it("auto-starts a live hub mode", () => {
    expect(shouldAutoStartLiveSession({ ...hub, mode: "live_session" })).toBe(true);
  });

  it("auto-starts when a weekend session is in the live window", () => {
    const start = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    expect(
      shouldAutoStartLiveSession({
        ...hub,
        weekend_sessions: [sess({ session_type: "FP1", status: "UPCOMING", datetime_utc: start })],
      }),
    ).toBe(true);
  });

  it("waits when nothing is live", () => {
    expect(shouldAutoStartLiveSession(hub)).toBe(false);
  });

  it("auto-starts FP2 in its live window", () => {
    const start = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    const liveHub = {
      ...hub,
      weekend_sessions: [
        sess({ session_type: "FP1", status: "COMPLETED", replayable: true }),
        sess({ session_type: "FP2", status: "UPCOMING", datetime_utc: start }),
        sess({ session_type: "R", status: "UPCOMING", datetime_utc: "2099-01-01T12:00:00Z" }),
      ],
    } as LiveHub;
    expect(shouldAutoStartLiveSession(liveHub)).toBe(true);
    expect(liveHubSession(liveHub)?.session_type).toBe("FP2");
    expect(autoArisForHubSession(liveHubSession(liveHub))).toBe(true);
  });
});

describe("hubSessionCta", () => {
  it("labels live, completed, and upcoming sessions", () => {
    const start = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    expect(hubSessionCta(sess({ session_type: "FP2", live: true, status: "LIVE", datetime_utc: start }))).toBe("live");
    expect(hubSessionCta(sess({ session_type: "FP1", status: "COMPLETED", replayable: true }))).toBe("replay");
    expect(hubSessionCta(sess({ session_type: "R", status: "UPCOMING", datetime_utc: "2099-01-01T12:00:00Z" }))).toBe(
      "wait",
    );
  });
});

describe("pickArisHubSession", () => {
  it("prefers live FP2, else upcoming Race", () => {
    const start = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    expect(
      pickArisHubSession([
        sess({ session_type: "FP1", status: "COMPLETED", replayable: true }),
        sess({ session_type: "FP2", status: "UPCOMING", datetime_utc: start }),
        sess({ session_type: "R", status: "UPCOMING", datetime_utc: "2099-01-01T12:00:00Z" }),
      ])?.session_type,
    ).toBe("FP2");
    expect(
      pickArisHubSession([
        sess({ session_type: "FP1", status: "COMPLETED", replayable: true }),
        sess({ session_type: "FP2", status: "COMPLETED", replayable: true }),
        sess({ session_type: "R", status: "UPCOMING", datetime_utc: "2099-01-01T12:00:00Z" }),
      ])?.session_type,
    ).toBe("R");
  });
});
