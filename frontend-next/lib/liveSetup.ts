import type { HubSession, LiveHub, SessionType } from "@/lib/types";
import { isArisCapableSession, sessionLabel } from "@/lib/sessionFlow";
import { sessionIsLiveNow } from "@/lib/sessionWindow";

const SESSION_TYPES = new Set<string>(["R", "S", "Q", "FP1", "FP2", "FP3", "SS", "SQ"]);

export function asSessionType(raw: string | null | undefined): SessionType {
  const t = String(raw ?? "R").toUpperCase();
  return (SESSION_TYPES.has(t) ? t : "R") as SessionType;
}

export function pickDefaultHubSession(sessions: HubSession[]): HubSession | null {
  if (!sessions.length) return null;
  const live = sessions.find((s) => sessionIsLiveNow(s));
  if (live) return live;
  const upcoming = sessions
    .filter((s) => s.status === "UPCOMING" && s.datetime_utc)
    .slice()
    .sort((a, b) => String(a.datetime_utc).localeCompare(String(b.datetime_utc)));
  if (upcoming[0]) return upcoming[0];
  const completed = sessions.filter((s) => s.status === "COMPLETED" || s.replayable);
  if (completed.length) return completed[completed.length - 1] ?? null;
  return sessions[0];
}

/** Prefer a live ARIS session, else the next upcoming FP2/Race. */
export function pickArisHubSession(sessions: HubSession[]): HubSession | null {
  const live = sessions.find((s) => sessionIsLiveNow(s) && isArisCapableSession(s.session_type));
  if (live) return live;
  const upcoming = sessions
    .filter((s) => isArisCapableSession(s.session_type) && s.status === "UPCOMING")
    .slice()
    .sort((a, b) => String(a.datetime_utc ?? "").localeCompare(String(b.datetime_utc ?? "")));
  if (upcoming[0]) return upcoming[0];
  return sessions.find((s) => isArisCapableSession(s.session_type)) ?? null;
}

export function hubSessionCta(session: HubSession, now = Date.now()): "live" | "replay" | "wait" {
  if (sessionIsLiveNow(session, now)) return "live";
  if (session.status === "COMPLETED" || session.replayable) return "replay";
  // Join Live only when the session window is live (feed is up). Upcoming
  // Race used to unlock early; keep it disabled until then.
  return "wait";
}

export function hubSessionCtaCopy(session: HubSession, now = Date.now()): { label: string; disabled: boolean } {
  const name = sessionLabel(session.session_type);
  const cta = hubSessionCta(session, now);
  if (cta === "live") return { label: `Join Live · ${name}`, disabled: false };
  if (cta === "replay") {
    if (!isRaceSession(session.session_type)) {
      return { label: `${name} has ended`, disabled: true };
    }
    return { label: `Replay ${name}`, disabled: false };
  }
  return { label: "Waiting for Live Feed", disabled: true };
}

export function liveHubSession(hub: LiveHub, now = Date.now()): HubSession | null {
  return hub.weekend_sessions.find((s) => sessionIsLiveNow(s, now)) ?? null;
}

/** Race-only: homepage Watch Live may skip the picker. /live itself never auto-starts. */
export function shouldAutoStartLiveSession(
  hub: LiveHub,
  now = Date.now(),
  opts?: { watch?: boolean; session?: string | null },
): boolean {
  if (!opts?.watch) return false;
  const wanted = asSessionType(opts.session);
  if (wanted !== "R") return false;
  const live = liveHubSession(hub, now);
  return Boolean(live && asSessionType(live.session_type) === "R");
}

/** Live ARIS is deferred - always false until live strategy architecture ships. */
export function autoArisForHubSession(_session: HubSession | null | undefined): boolean {
  return false;
}

export function isRaceSession(sessionType: string | null | undefined): boolean {
  return asSessionType(sessionType) === "R";
}

export function hubEndedSessionCopy(session: HubSession): string {
  return `This session has ended. ${sessionLabel(session.session_type)} is no longer available for live viewing.`;
}

export function hubNonRaceReplayCopy(session: HubSession): string | null {
  if (isRaceSession(session.session_type)) return null;
  return "Practice and qualifying replays are not available. Race replays are on Replay for 2024-2026.";
}

/** Practice packs load from OpenF1 only (FastF1 has no recent FP data). */
export function replayPackWaitMs(sessionType: string | null | undefined): number {
  const t = asSessionType(sessionType);
  if (t === "FP1" || t === "FP2" || t === "FP3") return 90_000;
  return 20_000;
}

/** Homepage live card: Race can skip the picker; other live sessions only preselect. */
export function liveHubEnterHref(
  session: HubSession | null,
  _opts?: { arisOn?: boolean; driver?: string | null },
): string {
  if (!session) return "/live";
  const qs = new URLSearchParams({ session: session.session_type });
  if (isRaceSession(session.session_type)) {
    qs.set("watch", "1");
    // Live ARIS is deferred - never auto-enable strategy via query params.
  }
  return `/live?${qs.toString()}`;
}
