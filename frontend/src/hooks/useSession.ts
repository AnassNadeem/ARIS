import { apiGet, peekGet } from "../api/client";
import { lapsSchema, liveTimingSchema, type LapsResponse, type LiveTiming } from "../api/types";
import { useAsync } from "./useAsync";

export function useSessionLaps(year: number, round: number, sessionType: string, enabled = true) {
  const path = `/api/session/${year}/${round}/${sessionType}/laps`;
  return useAsync(
    () =>
      apiGet<LapsResponse>(path, {
        schema: lapsSchema,
        timeout: 120_000,
      }),
    [year, round, sessionType],
    enabled,
    () => peekGet<LapsResponse>(path),
  );
}

export function useReplayTiming(
  year: number,
  round: number,
  sessionType: string,
  lap: number,
  enabled = true,
) {
  const path = `/api/session/${year}/${round}/${sessionType}/timing?lap=${lap}`;
  return useAsync(
    () =>
      apiGet<LiveTiming>(path, {
        schema: liveTimingSchema,
        timeout: 120_000,
      }),
    [year, round, sessionType, lap],
    enabled,
    () => peekGet<LiveTiming>(path),
  );
}
