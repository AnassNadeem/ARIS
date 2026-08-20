import { apiGet, asOfFromUrl, peekGet, withAsOf } from "../api/client";
import { calendarSchema, type CalendarResponse } from "../api/types";
import { useAsync } from "./useAsync";

export function useCalendar(year: number) {
  const asOf = asOfFromUrl();
  const path = withAsOf(`/api/calendar/${year}`, asOf);
  return useAsync(
    () =>
      apiGet<CalendarResponse>(path, {
        schema: calendarSchema,
        timeout: 60_000,
      }),
    [year, asOf],
    true,
    () => peekGet<CalendarResponse>(path),
  );
}
