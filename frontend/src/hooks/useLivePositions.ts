import { useEffect, useState } from "react";
import { apiGet, asOfFromUrl, withAsOf } from "../api/client";
import type { CarPosition } from "../api/types";

export function useLivePositions(active: boolean) {
  const [positions, setPositions] = useState<CarPosition[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    const asOf = asOfFromUrl();
    const poll = async () => {
      try {
        const data = await apiGet<{ positions: CarPosition[] }>(withAsOf("/api/live/positions", asOf), {
          timeout: 30_000,
        });
        if (!cancelled) {
          setPositions(data.positions);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      }
    };
    void poll();
    const id = window.setInterval(() => void poll(), 2000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [active]);
  return { positions, error };
}
