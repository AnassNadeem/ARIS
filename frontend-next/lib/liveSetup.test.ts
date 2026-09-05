import { describe, expect, it } from "vitest";
import {
  asSessionType,
  autoArisForHubSession,
  hubEndedSessionCopy,
  hubNonRaceReplayCopy,
  hubSessionCta,
  hubSessionCtaCopy,
  liveHubSession,
  pickArisHubSession,
  pickDefaultHubSession,
  replayPackWaitMs,
  shouldAutoStartLiveSession,
  liveHubEnterHref,
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

  it("does not skip the /live picker just because a session is live", () => {
    expect(shouldAutoStartLiveSession({ ...hub, mode: "live_session" })).toBe(false);
  });

  it("does not auto-start FP1/FP3 from the Live nav", () => {
    const start = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    expect(
      shouldAutoStartLiveSession(
        {
          ...hub,
          weekend_sessions: [sess({ session_type: "FP3", status: "UPCOMING", datetime_utc: start })],
        },
        Date.now(),
        { watch: true, session: "FP3" },
      ),
    ).toBe(false);
  });

  it("auto-starts only a live Race from the homepage Watch Live link", () => {
    const start = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    const liveHub = {
      ...hub,
      weekend_sessions: [
        sess({ session_type: "FP3", status: "COMPLETED", replayable: true }),
        sess({ session_type: "R", status: "LIVE", live: true, datetime_utc: start }),
      ],
    } as LiveHub;
    expect(shouldAutoStartLiveSession(liveHub)).toBe(false);
    expect(shouldAutoStartLiveSession(liveHub, Date.now(), { watch: true, session: "R" })).toBe(true);
    expect(liveHubSession(liveHub)?.session_type).toBe("R");
    expect(autoArisForHubSession(liveHubSession(liveHub))).toBe(true);
  });

  it("waits when nothing is live", () => {
    expect(shouldAutoStartLiveSession(hub)).toBe(false);
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

  it("shows Join Live, Replay, or a disabled wait label", () => {
    const start = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    expect(hubSessionCtaCopy(sess({ session_type: "FP3", live: true, status: "LIVE", datetime_utc: start }))).toEqual({
      label: "Join Live · FP3",
      disabled: false,
    });
    expect(hubSessionCtaCopy(sess({ session_type: "FP1", status: "COMPLETED", replayable: true }))).toEqual({
      label: "FP1 has ended",
      disabled: true,
    });
    expect(hubSessionCtaCopy(sess({ session_type: "R", status: "COMPLETED", replayable: true }))).toEqual({
      label: "Replay Race",
      disabled: false,
    });
    expect(
      hubSessionCtaCopy(sess({ session_type: "R", status: "UPCOMING", datetime_utc: "2099-01-01T12:00:00Z" })),
    ).toEqual({
      label: "Waiting for Session to Start",
      disabled: true,
    });
  });

  it("explains ended practice sessions and points race replays to /replay", () => {
    const fp1 = sess({ session_type: "FP1", status: "COMPLETED", replayable: true });
    expect(hubEndedSessionCopy(fp1)).toBe(
      "This session has ended — FP1 is no longer available for live viewing.",
    );
    expect(hubNonRaceReplayCopy(fp1)).toMatch(/Practice and qualifying replays are not available/);
    expect(hubNonRaceReplayCopy(sess({ session_type: "R", status: "COMPLETED", replayable: true }))).toBeNull();
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

describe("liveHubEnterHref", () => {
  it("preselects a live FP session without skipping the picker", () => {
    expect(liveHubEnterHref(sess({ session_type: "FP2", status: "LIVE", live: true }))).toBe("/live?session=FP2");
  });

  it("skips the picker for a live Race from the homepage Watch Live link", () => {
    expect(
      liveHubEnterHref(sess({ session_type: "R", status: "LIVE", live: true }), { arisOn: true, driver: "VER" }),
    ).toBe("/live?session=R&watch=1&aris=1&driver=VER");
  });

  it("falls back to the live hub when nothing is live", () => {
    expect(liveHubEnterHref(null)).toBe("/live");
  });
});

describe("replayPackWaitMs", () => {
  it("waits longer for OpenF1 practice packs than for race R2", () => {
    expect(replayPackWaitMs("FP1")).toBe(90_000);
    expect(replayPackWaitMs("FP2")).toBe(90_000);
    expect(replayPackWaitMs("R")).toBe(20_000);
  });
});
