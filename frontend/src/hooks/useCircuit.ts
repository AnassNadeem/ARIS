import { apiGet, peekGet } from "../api/client";
import type { CircuitCharacteristics, CircuitHistoryResponse } from "../api/types";
import { useAsync } from "./useAsync";

export function useCircuit(circuitKey: string | undefined, year?: number, enabled = true) {
  const q = year ? `?year=${year}` : "";
  const charsPath = circuitKey ? `/api/circuit/${circuitKey}/characteristics${q}` : "";
  const histPath = circuitKey ? `/api/circuit/${circuitKey}/history` : "";
  const on = Boolean(circuitKey) && enabled;
  const chars = useAsync(
    () => apiGet<CircuitCharacteristics>(charsPath, { timeout: 60_000 }),
    [charsPath],
    on,
    () => peekGet<CircuitCharacteristics>(charsPath),
  );
  const history = useAsync(
    () => apiGet<CircuitHistoryResponse>(histPath, { timeout: 90_000 }),
    [histPath],
    on,
    () => peekGet<CircuitHistoryResponse>(histPath),
  );
  return { chars, history };
}
