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
  const completed = sessions.filter((s) => s.status === "COMPLETED" || s.replayable);
  if (completed.length) return completed[completed.length - 1] ?? null;
  const upcoming = sessions
    .filter((s) => s.status === "UPCOMING" && s.datetime_utc)
    .slice()
    .sort((a, b) => String(a.datetime_utc).localeCompare(String(b.datetime_utc)));
  return upcoming[0] ?? sessions[0];
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
  return "wait";
}

export function hubSessionCtaCopy(session: HubSession, now = Date.now()): { label: string; disabled: boolean } {
  const name = sessionLabel(session.session_type);
  const cta = hubSessionCta(session, now);
  if (cta === "live") return { label: `Join Live · ${name}`, disabled: false };
  if (cta === "replay") return { label: `Replay ${name}`, disabled: false };
  return { label: "Waiting for Session to Start", disabled: true };
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

/** Race and FP2 can run ARIS from the live picker. */
export function autoArisForHubSession(session: HubSession | null | undefined): boolean {
  return isArisCapableSession(session?.session_type);
}

export function isRaceSession(sessionType: string | null | undefined): boolean {
  return asSessionType(sessionType) === "R";
}
