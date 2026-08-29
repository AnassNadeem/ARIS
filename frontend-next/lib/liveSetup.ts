import type { HubSession, SessionType } from "@/lib/types";

const SESSION_TYPES = new Set<string>(["R", "S", "Q", "FP1", "FP2", "FP3", "SS", "SQ"]);

export function asSessionType(raw: string | null | undefined): SessionType {
  const t = String(raw ?? "R").toUpperCase();
  return (SESSION_TYPES.has(t) ? t : "R") as SessionType;
}

export function pickDefaultHubSession(sessions: HubSession[]): HubSession | null {
  if (!sessions.length) return null;
  const live = sessions.find((s) => s.live);
  if (live) return live;
  const upcoming = sessions
    .filter((s) => s.status === "UPCOMING" && s.datetime_utc)
    .slice()
    .sort((a, b) => String(a.datetime_utc).localeCompare(String(b.datetime_utc)));
  return upcoming[0] ?? sessions[0];
}
