import { apiGet, peekGet } from "../api/client";
import type { CircuitCharacteristics, CircuitHistoryYear } from "../api/types";
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
    async () => {
      const data = await apiGet<{ years: CircuitHistoryYear[] }>(histPath, { timeout: 60_000 });
      return data.years;
    },
    [histPath],
    on,
    () => peekGet<{ years: CircuitHistoryYear[] }>(histPath)?.years,
  );
  return { chars, history };
}
