import { describe, expect, it } from "vitest";
import { asSessionType, pickDefaultHubSession } from "./liveSetup";
import type { HubSession } from "./types";

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

  it("falls back to the soonest upcoming session", () => {
    const sessions = [
      sess({ session_type: "FP1", status: "COMPLETED", replayable: true }),
      sess({ session_type: "R", status: "UPCOMING", datetime_utc: "2099-01-02T12:00:00Z" }),
      sess({ session_type: "Q", status: "UPCOMING", datetime_utc: "2099-01-01T12:00:00Z" }),
    ];
    expect(pickDefaultHubSession(sessions)?.session_type).toBe("Q");
  });
});

describe("asSessionType", () => {
  it("maps known codes and defaults unknown to Race", () => {
    expect(asSessionType("fp1")).toBe("FP1");
    expect(asSessionType("XX")).toBe("R");
  });
});
