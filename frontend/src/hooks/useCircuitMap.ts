import { apiGet } from "../api/client";
import type { CarPosition, CircuitMap } from "../api/types";
import { useAsync } from "./useAsync";

export function useCircuitMap(year: number, round: number, enabled = true) {
  return useAsync(
    () => apiGet<CircuitMap>(`/api/circuit/${year}/${round}/map`, { timeout: 120_000 }),
    [year, round],
    enabled,
  );
}

export function useCircuitPreview(year: number, round: number, enabled = true) {
  return useAsync(
    () => apiGet<CircuitMap>(`/api/circuit/${year}/${round}/preview`, { timeout: 8_000 }),
    [year, round],
    enabled,
  );
}

export function useAllLapPositions(year: number, round: number, enabled = true) {
  return useAsync(
    () =>
      apiGet<{ laps: Record<string, CarPosition[]> }>(
        `/api/session/${year}/${round}/R/positions/all`,
        { timeout: 120_000 },
      ),
    [year, round],
    enabled,
  );
}
