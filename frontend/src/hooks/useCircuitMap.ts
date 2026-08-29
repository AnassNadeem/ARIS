import { apiGet, peekGet } from "../api/client";
import type { CarPosition, CircuitMap, ReplayPath } from "../api/types";
import { useAsync } from "./useAsync";

export function useCircuitMap(year: number, round: number, enabled = true) {
  const path = `/api/circuit/${year}/${round}/map`;
  return useAsync(
    () => apiGet<CircuitMap>(path, { timeout: 120_000 }),
    [year, round],
    enabled,
    () => peekGet<CircuitMap>(path),
  );
}

export function useCircuitPreview(year: number, round: number, enabled = true) {
  const path = `/api/circuit/${year}/${round}/preview`;
  return useAsync(
    () => apiGet<CircuitMap>(path, { timeout: 8_000 }),
    [year, round],
    enabled,
    () => peekGet<CircuitMap>(path),
  );
}

export function useReplayPath(
  sessionKey: number | null,
  year?: number | null,
  round?: number | null,
  source?: string | null,
) {
  const path =
    sessionKey == null
      ? ""
      : `/api/live/replay-path?session_key=${sessionKey}${year != null ? `&year=${year}` : ""}${
          round != null ? `&round_number=${round}` : ""
        }&src=${source || "fastf1"}`;
  return useAsync(
    () => apiGet<ReplayPath>(path, { timeout: 120_000 }),
    [path],
    Boolean(path),
    () => (path ? peekGet<ReplayPath>(path) : undefined),
  );
}

export function useAllLapPositions(year: number, round: number, enabled = true) {
  const path = `/api/session/${year}/${round}/R/positions/all`;
  return useAsync(
    () =>
      apiGet<{ laps: Record<string, CarPosition[]>; circuit_path?: { x: number[]; y: number[] } }>(path, {
        timeout: 120_000,
      }),
    [year, round],
    enabled,
    () => peekGet<{ laps: Record<string, CarPosition[]>; circuit_path?: { x: number[]; y: number[] } }>(path),
  );
}
