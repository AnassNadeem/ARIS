"use client";

import { useEffect, useState } from "react";

export type LightsOutPhase = "ready" | "starting" | "racing";

const LIGHT_INTERVAL_MS = 380;
const HOLD_MS = 420;
const AFTER_OFF_MS = 180;

/**
 * F1-style five red lights. Disabled until session, circuit, and at least
 * one replay/live frame are loaded. On click: lights on… on… on… on… on → off,
 * then `onGo`.
 */
export function StartLightsOut({
  phase,
  dataReady,
  readyHint,
  onBegin,
  onGo,
}: {
  phase: LightsOutPhase;
  dataReady: boolean;
  readyHint?: string;
  onBegin: () => void;
  onGo: () => void;
}) {
  const [lit, setLit] = useState(0);
  const [extinguished, setExtinguished] = useState(false);

  useEffect(() => {
    if (phase !== "starting") {
      setLit(0);
      setExtinguished(false);
      return;
    }
    const timers: number[] = [];
    for (let i = 1; i <= 5; i++) {
      timers.push(window.setTimeout(() => setLit(i), i * LIGHT_INTERVAL_MS));
    }
    const offAt = 5 * LIGHT_INTERVAL_MS + HOLD_MS;
    timers.push(
      window.setTimeout(() => {
        setExtinguished(true);
        setLit(0);
      }, offAt),
    );
    timers.push(window.setTimeout(() => onGo(), offAt + AFTER_OFF_MS));
    return () => {
      for (const t of timers) window.clearTimeout(t);
    };
  }, [phase, onGo]);

  if (phase === "racing") return null;

  const starting = phase === "starting";
  const disabled = !dataReady || starting;

  return (
    <div className="absolute inset-0 z-[80] flex flex-col items-center justify-center bg-carbon/92 backdrop-blur-[2px]">
      <div className="flex flex-col items-center gap-6 rounded-[12px] border border-border bg-surface-2 px-10 py-8 shadow-2xl">
        <div className="font-mono-data text-[11px] uppercase tracking-[0.2em] text-muted">Lights out</div>
        <div className="flex gap-3">
          {Array.from({ length: 5 }, (_, i) => {
            const on = !extinguished && lit > i;
            return (
              <span
                key={i}
                className="h-10 w-10 rounded-full border-2 transition-colors duration-150"
                style={{
                  borderColor: on ? "#e8002d" : "#2a2a2a",
                  background: on ? "#e8002d" : "#1a1a1a",
                  boxShadow: on ? "0 0 18px #e8002d" : "none",
                }}
              />
            );
          })}
        </div>
        <button
          type="button"
          disabled={disabled}
          onClick={() => {
            if (!disabled) onBegin();
          }}
          title={!dataReady ? (readyHint ?? "Waiting for session data…") : undefined}
          className={`rounded-[8px] px-8 py-3 font-mono-data text-sm uppercase tracking-wide ${
            disabled
              ? "cursor-not-allowed border border-border text-muted-2 opacity-50"
              : "bg-red text-white hover:brightness-110"
          }`}
        >
          {starting ? "Starting…" : "Start"}
        </button>
        <p className="max-w-xs text-center font-mono-data text-[10px] text-muted-2">
          {dataReady
            ? "Session loaded. Start for lights-out, then the replay runs at 1×."
            : (readyHint ?? "Waiting for laps, drivers, circuit map, and the first frame…")}
        </p>
      </div>
    </div>
  );
}
