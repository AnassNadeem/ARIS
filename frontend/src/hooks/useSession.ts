import { apiGet } from "../api/client";
import { lapsSchema, liveTimingSchema, type LapsResponse, type LiveTiming } from "../api/types";
import { useAsync } from "./useAsync";

export function useSessionLaps(year: number, round: number, sessionType: string, enabled = true) {
  return useAsync(
    () =>
      apiGet<LapsResponse>(`/api/session/${year}/${round}/${sessionType}/laps`, {
        schema: lapsSchema,
        timeout: 120_000,
      }),
    [year, round, sessionType],
    enabled,
  );
}

export function useReplayTiming(
  year: number,
  round: number,
  sessionType: string,
  lap: number,
  enabled = true,
) {
  return useAsync(
    () =>
      apiGet<LiveTiming>(`/api/session/${year}/${round}/${sessionType}/timing?lap=${lap}`, {
        schema: liveTimingSchema,
        timeout: 120_000,
      }),
    [year, round, sessionType, lap],
    enabled,
  );
}
