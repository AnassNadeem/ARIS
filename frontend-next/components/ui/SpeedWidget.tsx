"use client";

import { useEffect, useState } from "react";
import { DraggableHud } from "@/components/ui/DraggableHud";
import { useRaceStore } from "@/store/raceStore";

/** Car speed for the ARIS / focus driver — snaps to sides and corners. */
export function SpeedWidget() {
  const driver = useRaceStore((s) => s.arisDriver ?? s.focusDriver);
  const [kph, setKph] = useState(0);
  const [mph, setMph] = useState(false);

  useEffect(() => {
    const tick = () => {
      const code = useRaceStore.getState().arisDriver ?? useRaceStore.getState().focusDriver;
      const car = code ? useRaceStore.getState().cars[code] : null;
      setKph(car?.speed_kph ? Math.round(car.speed_kph) : 0);
    };
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [driver]);

  const value = mph ? Math.round(kph * 0.621371) : kph;
  const unit = mph ? "mph" : "km/h";

  return (
    <DraggableHud storageKey="aris-hud-speed" defaultX={8} defaultY={52} snapToEdges>
      <div className="rounded-[8px] border border-border bg-surface-2/95 px-2 py-1.5 shadow-lg backdrop-blur">
        <div className="mb-0.5 font-mono-data text-[8px] uppercase tracking-widest text-muted">Speed</div>
        <button
          type="button"
          title="Click to toggle km/h and mph"
          onClick={() => setMph((v) => !v)}
          className="flex flex-col items-start font-mono-data"
        >
          <span className="text-[8px] uppercase tracking-wide text-muted">{driver ?? "—"}</span>
          <span className="text-[13px] leading-none text-white">
            {value || "—"} <span className="text-[9px] text-muted">{unit}</span>
          </span>
        </button>
      </div>
    </DraggableHud>
  );
}
