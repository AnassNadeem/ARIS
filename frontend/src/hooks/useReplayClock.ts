import { useCallback, useEffect, useRef, useState } from "react";
import { SPEED_FACTOR, SPEED_OPTIONS } from "../theme";

export function useReplayClock({
  startIso,
  endIso,
  running,
  speed,
}: {
  startIso: string | null;
  endIso: string | null;
  running: boolean;
  speed: (typeof SPEED_OPTIONS)[number];
}) {
  const [elapsedMs, setElapsedMsState] = useState(0);
  const elapsedRef = useRef(0);
  const lastWallRef = useRef<number | null>(null);
  const start = startIso ? Date.parse(startIso) : Number.NaN;
  const end = endIso ? Date.parse(endIso) : Number.NaN;
  const durationMs = Number.isFinite(start) && Number.isFinite(end) ? Math.max(0, end - start) : 0;

  useEffect(() => {
    elapsedRef.current = 0;
    setElapsedMsState(0);
    lastWallRef.current = null;
  }, [startIso, endIso]);

  const setElapsedMs = useCallback(
    (ms: number) => {
      const next = Math.max(0, Math.min(durationMs, ms));
      elapsedRef.current = next;
      setElapsedMsState(next);
    },
    [durationMs],
  );

  useEffect(() => {
    if (!running || durationMs <= 0) {
      lastWallRef.current = null;
      return;
    }
    let raf = 0;
    const tick = (now: number) => {
      const last = lastWallRef.current ?? now;
      lastWallRef.current = now;
      const factor = SPEED_FACTOR[speed] ?? 1;
      const next = Math.min(durationMs, elapsedRef.current + (now - last) * factor);
      elapsedRef.current = next;
      setElapsedMsState(next);
      if (next < durationMs) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [running, speed, durationMs]);

  const asOf = Number.isFinite(start) ? new Date(start + elapsedMs).toISOString() : null;
  const ended = durationMs > 0 && elapsedMs >= durationMs - 16;
  return { elapsedMs, durationMs, asOf, ended, setElapsedMs };
}
