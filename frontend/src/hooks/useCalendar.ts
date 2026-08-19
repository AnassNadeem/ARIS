import { apiGet, asOfFromUrl, withAsOf } from "../api/client";
import { calendarSchema, type CalendarResponse } from "../api/types";
import { useAsync } from "./useAsync";

export function useCalendar(year: number) {
  const asOf = asOfFromUrl();
  return useAsync(
    () =>
      apiGet<CalendarResponse>(withAsOf(`/api/calendar/${year}`, asOf), {
        schema: calendarSchema,
        timeout: 60_000,
      }),
    [year, asOf],
  );
}
