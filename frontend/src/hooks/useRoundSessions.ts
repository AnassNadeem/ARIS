import { apiGet, asOfFromUrl, peekGet, withAsOf } from "../api/client";
import { roundSessionsSchema, type RoundSessions } from "../api/types";
import { useAsync } from "./useAsync";

export function useRoundSessions(year: number, roundNumber: number | null) {
  const asOf = asOfFromUrl();
  const path =
    roundNumber == null ? "" : withAsOf(`/api/calendar/${year}/${roundNumber}/sessions`, asOf);
  return useAsync(
    () =>
      apiGet<RoundSessions>(path, {
        schema: roundSessionsSchema,
        timeout: 30_000,
      }),
    [path],
    Boolean(path),
    () => (path ? peekGet<RoundSessions>(path) : undefined),
  );
}
