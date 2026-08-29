import { useEffect, useMemo } from "react";
import { apiGet, asOfFromUrl, peekGet, withAsOf } from "../api/client";
import {
  calendarSchema,
  liveStatusSchema,
  nextRaceSchema,
  type CalendarResponse,
  type CalendarState,
  type LiveStatus,
  type NextRace,
} from "../api/types";
import { useAsync } from "./useAsync";

function liveKind(next: NextRace, live: LiveStatus): CalendarState {
  const fromLive = (live.session_type || "").toUpperCase();
  const fromWeekend = next.sessions_this_weekend.find((s) => s.status === "LIVE")?.session_type?.toUpperCase();
  const st = fromLive || fromWeekend || (next.next_session_name || "").toUpperCase();
  if (st === "R" || st === "S" || (st.includes("RACE") && !st.includes("QUALI"))) {
    return { type: "LIVE_RACE", next, live };
  }
  if (st === "Q" || st === "SQ" || st.includes("QUALI")) {
    return { type: "LIVE_QUALI", next, live };
  }
  const fp = st === "FP2" || st.includes("PRACTICE 2") ? 2 : st === "FP3" || st.includes("PRACTICE 3") ? 3 : 1;
  return { type: "LIVE_PRACTICE", next, live, fpNumber: fp };
}

function nextFromCalendar(calendar: CalendarResponse): NextRace | null {
  const rnd =
    calendar.rounds.find((r) => r.status === "LIVE") ??
    calendar.rounds.find((r) => r.status === "UPCOMING");
  if (!rnd) return null;
  const start = rnd.date_race ? Date.parse(rnd.date_race) : Number.NaN;
  const countdown = Number.isFinite(start) ? Math.max(0, Math.floor((start - Date.now()) / 1000)) : 0;
  return {
    year: calendar.year,
    round_number: rnd.round_number,
    name: rnd.name,
    circuit_name: rnd.circuit_name,
    circuit_key: rnd.circuit_key,
    country: rnd.country,
    city: rnd.city,
    date_race: rnd.date_race,
    status: rnd.status === "CANCELLED" ? "CANCELLED" : rnd.status,
    is_sprint_weekend: rnd.is_sprint_weekend,
    is_this_weekend: rnd.status === "LIVE",
    countdown_seconds: countdown,
    days_until: Math.floor(countdown / 86400),
    hours_until: Math.floor(countdown / 3600),
    sessions_this_weekend: [],
    notes: rnd.notes ?? [],
    as_of: calendar.as_of,
    off_season: false,
  };
}

function classify(next: NextRace, live: LiveStatus, calendar: CalendarResponse): CalendarState {
  const sessionLive = Boolean(live.is_live) && !live.session_ended;
  if (sessionLive) {
    return liveKind(next, live);
  }

  const now = Date.parse(calendar.as_of) || Date.now();
  const completed = [...calendar.rounds]
    .filter((r) => r.status === "COMPLETED" && r.date_race)
    .sort((a, b) => Date.parse(a.date_race || "") - Date.parse(b.date_race || ""));
  const last = completed[completed.length - 1];
  if (last?.date_race) {
    const end = Date.parse(last.date_race) + 4 * 3600 * 1000;
    const hoursAgo = (now - end) / 3600000;
    if (hoursAgo >= 0 && hoursAgo < 24) {
      return { type: "POST_RACE", completed: last, hoursAgo, year: calendar.year };
    }
  }

  if (next.off_season) {
    return { type: "OFF_SEASON", nextYear: next.year, next };
  }

  if (next.is_this_weekend || next.days_until <= 3) {
    return { type: "RACE_WEEKEND", next, daysUntilRace: next.days_until };
  }

  const upcoming = calendar.rounds.some((r) => r.status === "UPCOMING" || r.status === "LIVE");
  if (!upcoming) {
    return { type: "OFF_SEASON", nextYear: next.year, next };
  }

  return { type: "BETWEEN_ROUNDS", next, daysUntil: next.days_until };
}

export function useCalendarState(year: number) {
  const asOf = asOfFromUrl();
  const nextPath = withAsOf("/api/next-race", asOf);
  const livePath = withAsOf("/api/live/status", asOf);
  const calPath = withAsOf(`/api/calendar/${year}`, asOf);
  const bundle = useAsync(
    async () => {
      const settled = await Promise.allSettled([
        apiGet(nextPath, { schema: nextRaceSchema, timeout: 20_000 }),
        apiGet(livePath, { schema: liveStatusSchema, timeout: 12_000 }),
        apiGet(calPath, { schema: calendarSchema, timeout: 20_000 }),
      ]);
      const next =
        settled[0].status === "fulfilled"
          ? settled[0].value
          : peekGet<NextRace>(nextPath);
      const live =
        settled[1].status === "fulfilled"
          ? settled[1].value
          : peekGet<LiveStatus>(livePath) ?? {
              is_live: false,
              session_ended: true,
              replay_preparing: true,
            };
      const calendar =
        settled[2].status === "fulfilled"
          ? settled[2].value
          : peekGet<CalendarResponse>(calPath);
      if (!calendar) {
        throw new Error("Waiting for ARIS calendar. The live session may have just ended.");
      }
      const resolved = next ?? nextFromCalendar(calendar);
      if (!resolved) {
        throw new Error("Waiting for ARIS calendar. The live session may have just ended.");
      }
      return { next: resolved, live, calendar };
    },
    [year, asOf],
    true,
    () => {
      const calendar = peekGet<CalendarResponse>(calPath);
      const next = peekGet<NextRace>(nextPath) ?? (calendar ? nextFromCalendar(calendar) : null);
      const live = peekGet<LiveStatus>(livePath);
      if (next && live && calendar) return { next, live, calendar };
      return undefined;
    },
  );

  const state: CalendarState | undefined = useMemo(() => {
    if (bundle.status !== "ok") return undefined;
    return classify(bundle.data.next, bundle.data.live, bundle.data.calendar);
  }, [bundle]);

  useEffect(() => {
    const id = window.setInterval(() => bundle.retry(), 5_000);
    return () => window.clearInterval(id);
  }, [bundle.retry]);

  return { ...bundle, calendarState: state, asOf };
}
