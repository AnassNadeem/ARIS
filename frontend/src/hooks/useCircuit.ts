import { apiGet } from "../api/client";
import type { CircuitCharacteristics, CircuitHistoryYear } from "../api/types";
import { useAsync } from "./useAsync";

export function useCircuit(circuitKey: string | undefined, year?: number) {
  const chars = useAsync(async () => {
    if (!circuitKey) throw new Error("No circuit");
    const q = year ? `?year=${year}` : "";
    return apiGet<CircuitCharacteristics>(`/api/circuit/${circuitKey}/characteristics${q}`, {
      timeout: 60_000,
    });
  }, [circuitKey, year]);
  const history = useAsync(async () => {
    if (!circuitKey) throw new Error("No circuit");
    const data = await apiGet<{ years: CircuitHistoryYear[] }>(`/api/circuit/${circuitKey}/history`, {
      timeout: 60_000,
    });
    return data.years;
  }, [circuitKey]);
  return { chars, history };
}
