import { apiPost } from "../api/client";
import { recommendSchema, type RecommendResponse } from "../api/types";
import { useAsync } from "./useAsync";

export function useARISRecommend(
  year: number,
  round: number,
  driver: string,
  lap: number,
  enabled: boolean,
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
          mode: "replay",
        },
        { schema: recommendSchema, timeout: 60_000 },
      ),
    [year, round, driver, lap],
    enabled,
  );
}
