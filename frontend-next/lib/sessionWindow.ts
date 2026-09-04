import type { HubSession, HubMode, LiveHub, SessionStatus } from "@/lib/types";

const MIN = 60_000;
const HOUR = 60 * MIN;

/** Generous windows so chequered + a few extra laps still count as live. */
const DURATION_MS: Record<string, number> = {
  FP1: 70 * MIN,
  FP2: 70 * MIN,
  FP3: 70 * MIN,
  SQ: 50 * MIN,
  SS: 50 * MIN,
  S: 70 * MIN,
  Q: 90 * MIN,
  R: 150 * MIN,
};

/**
 * Official 2026 weekend UTC stamps. Applied in the UI so a stale Heroku
 * calendar (old 13:30 CEST FP1 estimate) cannot keep counting down after
 * the session has already started.
 */
const OFFICIAL_2026_SESSIONS: { needles: string[]; times: Record<string, string> }[] = [
  {
    needles: ["monza", "italy", "nazionale"],
    times: {
      FP1: "2026-09-04T10:30:00Z",
      FP2: "2026-09-04T14:00:00Z",
      FP3: "2026-09-05T10:30:00Z",
      Q: "2026-09-05T14:00:00Z",
      R: "2026-09-06T13:00:00Z",
    },
  },
];

function slug(value: string | null | undefined): string {
  return (value || "").toLowerCase().replace(/[^a-z0-9]+/g, "");
}

export function official2026SessionTimes(
  circuitName: string | null | undefined,
  circuitKey: string | null | undefined = null,
  year: number | null | undefined = 2026,
): Record<string, string> | null {
  if (year !== 2026) return null;
  const hay = `${slug(circuitName)} ${slug(circuitKey)}`;
  const hit = OFFICIAL_2026_SESSIONS.find((row) => row.needles.some((n) => hay.includes(n)));
  return hit?.times ?? null;
}

export function sessionClockStatus(
  datetimeUtc: string | null | undefined,
  sessionType: string,
  now = Date.now(),
): SessionStatus {
  if (!datetimeUtc) return "UPCOMING";
  const start = new Date(datetimeUtc).getTime();
  if (Number.isNaN(start)) return "UPCOMING";
  if (now < start) return "UPCOMING";
  const dur = DURATION_MS[sessionType] ?? HOUR;
  if (now <= start + dur) return "LIVE";
  return "COMPLETED";
}

export function sessionIsLiveNow(session: HubSession, now = Date.now()): boolean {
  if (session.live || session.status === "LIVE") {
    const clock = sessionClockStatus(session.datetime_utc, session.session_type, now);
    if (clock === "COMPLETED") return false;
    return true;
  }
  return sessionClockStatus(session.datetime_utc, session.session_type, now) === "LIVE";
}

function stampSession(session: HubSession, iso: string | null, now: number): HubSession {
  const datetime_utc = iso ?? session.datetime_utc;
  const status = sessionClockStatus(datetime_utc, session.session_type, now);
  return {
    ...session,
    datetime_utc,
    status,
    live: status === "LIVE",
    replayable: status === "COMPLETED",
  };
}

export function applyLiveHubSessionWindows(hub: LiveHub, now = Date.now()): LiveHub {
  const overlay = official2026SessionTimes(hub.next.circuit_name, hub.next.circuit_key, hub.next.year);
  const weekend = hub.weekend_sessions.map((s) => stampSession(s, overlay?.[s.session_type] ?? null, now));
  const liveSess = weekend.find((s) => s.live);
  const nextOpen = weekend.find((s) => s.status === "UPCOMING" || s.live);
  const target = nextOpen?.datetime_utc ?? hub.countdown_target;
  const targetMs = target ? new Date(target).getTime() : NaN;
  const secs = Number.isFinite(targetMs) ? Math.max(0, Math.floor((targetMs - now) / 1000)) : hub.countdown_seconds;
  const mode: HubMode = liveSess ? "live_session" : hub.mode;
  return {
    ...hub,
    mode,
    waiting_reason: liveSess ? null : hub.waiting_reason,
    countdown_seconds: secs,
    countdown_target: target,
    weekend_sessions: weekend,
    live: {
      ...hub.live,
      is_live: Boolean(liveSess) || hub.live.is_live,
      session_type: liveSess?.session_type ?? hub.live.session_type,
      session_name: liveSess?.session_name ?? hub.live.session_name,
    },
    next: {
      ...hub.next,
      countdown_seconds: secs,
      next_session_datetime: target,
      next_session_name: nextOpen?.session_name ?? hub.next.next_session_name,
    },
  };
}
