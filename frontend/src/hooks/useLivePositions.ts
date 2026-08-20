import { useEffect, useRef, useState } from "react";
import { apiGet, asOfFromUrl, withAsOf } from "../api/client";
import type { CarPosition } from "../api/types";

export function useLivePositions(active: boolean) {
  const [positions, setPositions] = useState<CarPosition[]>([]);
  const [circuitPath, setCircuitPath] = useState<{ x: number[]; y: number[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const lastRef = useRef<Map<string, CarPosition>>(new Map());
  const missRef = useRef<Map<string, number>>(new Map());
  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    const asOf = asOfFromUrl();
    const poll = async () => {
      try {
        const data = await apiGet<{
          positions: CarPosition[];
          circuit_path?: { x: number[]; y: number[] } | null;
        }>(withAsOf("/api/live/positions", asOf), {
          timeout: 30_000,
          cache: false,
        });
        if (cancelled) return;
        if (data.circuit_path?.x?.length) setCircuitPath(data.circuit_path);
        const incoming = new Set(data.positions.map((p) => p.driver_code));
        const merged: CarPosition[] = [];
        for (const p of data.positions) {
          missRef.current.set(p.driver_code, 0);
          lastRef.current.set(p.driver_code, p);
          merged.push(p);
        }
        for (const [code, prev] of lastRef.current) {
          if (incoming.has(code)) continue;
          const misses = (missRef.current.get(code) ?? 0) + 1;
          missRef.current.set(code, misses);
          merged.push({ ...prev, is_pitted: misses >= 3 ? true : prev.is_pitted });
        }
        setPositions(merged);
        setError(null);
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
  return { positions, circuitPath, error };
}
