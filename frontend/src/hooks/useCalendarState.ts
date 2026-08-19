import { useMemo } from "react";
import { apiGet, asOfFromUrl, withAsOf } from "../api/client";
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

function classify(next: NextRace, live: LiveStatus, calendar: CalendarResponse): CalendarState {
  if (live.is_live || next.status === "LIVE") {
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
  const bundle = useAsync(async () => {
    const [next, live, calendar] = await Promise.all([
      apiGet(withAsOf("/api/next-race", asOf), { schema: nextRaceSchema, timeout: 60_000 }),
      apiGet(withAsOf("/api/live/status", asOf), { schema: liveStatusSchema, timeout: 60_000 }),
      apiGet(withAsOf(`/api/calendar/${year}`, asOf), { schema: calendarSchema, timeout: 60_000 }),
    ]);
    return { next, live, calendar };
  }, [year, asOf]);

  const state: CalendarState | undefined = useMemo(() => {
    if (bundle.status !== "ok") return undefined;
    return classify(bundle.data.next, bundle.data.live, bundle.data.calendar);
  }, [bundle]);

  return { ...bundle, calendarState: state, asOf };
}
