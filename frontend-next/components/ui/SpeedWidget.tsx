"use client";

import { useState } from "react";
import { DraggableHud } from "@/components/ui/DraggableHud";
import { fmtSectorTime } from "@/lib/timingDisplay";
import { useRaceStore } from "@/store/raceStore";

/** Car speed and last sectors for the ARIS / focus driver — snaps to sides and corners. */
export function SpeedWidget() {
  const driver = useRaceStore((s) => s.arisDriver ?? s.focusDriver);
  const kph = useRaceStore((s) => {
    const code = s.arisDriver ?? s.focusDriver;
    const v = code ? s.cars[code]?.speed_kph : 0;
    return v && v > 0.5 ? Math.round(v) : 0;
  });
  const s1 = useRaceStore((s) => {
    const code = s.arisDriver ?? s.focusDriver;
    return code ? (s.cars[code]?.sector1_s ?? null) : null;
  });
  const s2 = useRaceStore((s) => {
    const code = s.arisDriver ?? s.focusDriver;
    return code ? (s.cars[code]?.sector2_s ?? null) : null;
  });
  const s3 = useRaceStore((s) => {
    const code = s.arisDriver ?? s.focusDriver;
    return code ? (s.cars[code]?.sector3_s ?? null) : null;
  });
  const [mph, setMph] = useState(false);

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
        <div className="mt-1 grid grid-cols-3 gap-1 font-mono-data text-[8px] uppercase tracking-wide text-muted">
          <span>S1 {fmtSectorTime(s1)}</span>
          <span>S2 {fmtSectorTime(s2)}</span>
          <span>S3 {fmtSectorTime(s3)}</span>
        </div>
      </div>
    </DraggableHud>
  );
}
