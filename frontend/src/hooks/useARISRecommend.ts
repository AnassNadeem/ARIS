import { apiPost } from "../api/client";
import { recommendSchema, type RecommendResponse } from "../api/types";
import { useAsync } from "./useAsync";

export function useARISRecommend(
  year: number,
  round: number,
  driver: string,
  lap: number,
  enabled: boolean,
  mode: "live" | "replay" | "pre_race" = "replay",
  sessionKey?: string | number | null,
) {
  return useAsync(
    () =>
      apiPost<RecommendResponse>(
        "/api/aris/recommend",
        {
          year,
          round_number: round,
          session_type: "R",
          driver_code: driver,
          current_lap: lap,
          mode,
          session_key: sessionKey != null ? String(sessionKey) : undefined,
        },
        { schema: recommendSchema, timeout: 60_000 },
      ),
    [year, round, driver, lap, mode, sessionKey],
    enabled,
  );
}
