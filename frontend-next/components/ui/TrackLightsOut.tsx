"use client";

import { useEffect, useState } from "react";
import { useRaceStore } from "@/store/raceStore";

const LIGHT_INTERVAL_MS = 520;
const HOLD_MS = 700;
const AFTER_OFF_MS = 220;

/**
 * Five red lights over the track map only. Does not cover the rest of the console.
 * Header Start sets consolePlayState to "starting"; after lights-out this starts racing.
 */
export function TrackLightsOut() {
  const phase = useRaceStore((s) => s.consolePlayState);
  const startRacing = useRaceStore((s) => s.startRacing);
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
    timers.push(
      window.setTimeout(() => {
        const store = useRaceStore.getState();
        store.startRacing();
        if (store.isARISOn) {
          store.setARISModeLocked(true);
          store.pushComms({
            id: `lights-${Date.now()}`,
            lap: 1,
            source: "FIELD",
            text: `Lights out. ARIS is live on ${store.arisDriver ?? store.session?.driverCode ?? "the field"}.`,
            timestamp: Date.now(),
          });
        }
      }, offAt + AFTER_OFF_MS),
    );
    return () => {
      for (const t of timers) window.clearTimeout(t);
    };
  }, [phase, startRacing]);

  if (phase !== "starting") return null;

  return (
    <div className="pointer-events-none absolute inset-0 z-20 flex items-end justify-center pb-10">
      <div className="flex flex-col items-center gap-3 rounded-[10px] border border-border bg-carbon/80 px-5 py-3 backdrop-blur-[2px]">
        <div className="font-mono-data text-[10px] uppercase tracking-[0.2em] text-muted">Lights out</div>
        <div className="flex gap-2">
          {Array.from({ length: 5 }, (_, i) => {
            const on = !extinguished && lit > i;
            return (
              <span
                key={i}
                className="h-7 w-7 rounded-full border-2 transition-colors duration-150"
                style={{
                  borderColor: on ? "#e8002d" : "#2a2a2a",
                  background: on ? "#e8002d" : "#1a1a1a",
                  boxShadow: on ? "0 0 14px #e8002d" : "none",
                }}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}
