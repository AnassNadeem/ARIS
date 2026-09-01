"use client";

import { useState } from "react";
import { DraggableHud } from "@/components/ui/DraggableHud";
import { fmtSectorTime } from "@/lib/timingDisplay";
import { driverReplaySpeedKph } from "@/lib/r2Replay";
import { useRaceStore } from "@/store/raceStore";

function chosenDriverCode(s: {
  focusDriver: string | null;
  arisDriver: string | null;
  selectedDriver: string | null;
  session: { driverCode?: string | null } | null;
}): string | null {
  return s.focusDriver ?? s.arisDriver ?? s.selectedDriver ?? s.session?.driverCode ?? null;
}

function fmtGhostDelta(v: number): string {
  if (v > 0) return `+${v.toFixed(1)}s`;
  if (v < 0) return `${v.toFixed(1)}s`;
  return "±0.0s";
}

/** Car speed and last sectors for the chosen / focus driver — snaps to sides and corners. */
export function SpeedWidget() {
  const racing = useRaceStore((s) => s.consolePlayState === "racing");
  const driver = useRaceStore((s) => chosenDriverCode(s));
  const kph = useRaceStore((s) => {
    const code = chosenDriverCode(s);
    if (!code) return 0;
    if (s.r2RaceField && s.consolePlayState === "racing") {
      const fromSamples = driverReplaySpeedKph(s.r2RaceField, code, s.replayElapsedS);
      if (fromSamples > 0.5) return Math.round(fromSamples);
    }
    const v = s.cars[code]?.speed_kph;
    return v && v > 0.5 ? Math.round(v) : 0;
  });
  const s1 = useRaceStore((s) => {
    const code = chosenDriverCode(s);
    return code ? (s.cars[code]?.sector1_s ?? null) : null;
  });
  const s2 = useRaceStore((s) => {
    const code = chosenDriverCode(s);
    return code ? (s.cars[code]?.sector2_s ?? null) : null;
  });
  const s3 = useRaceStore((s) => {
    const code = chosenDriverCode(s);
    return code ? (s.cars[code]?.sector3_s ?? null) : null;
  });
  const ghostDelta = useRaceStore((s) => {
    if (!s.isARISOn) return null;
    const v = s.ghostCar?.ghost_cumulative_delta ?? s.ghostData?.ghost_cumulative_delta;
    return v != null && Number.isFinite(v) ? v : null;
  });
  const [mph, setMph] = useState(false);

  const value = mph ? Math.round(kph * 0.621371) : kph;
  const unit = mph ? "mph" : "km/h";

  if (!racing) return null;

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
          <span className="text-[13px] leading-none text-white" data-testid="speed-hud-value">
            {value || "—"} <span className="text-[9px] text-muted">{unit}</span>
          </span>
        </button>
        {ghostDelta != null && (
          <div
            className={`mt-1 font-mono-data text-[10px] font-semibold ${
              ghostDelta >= 0 ? "text-green-400" : "text-red-400"
            }`}
            data-testid="speed-hud-ghost-delta"
            title="ARIS ghost cumulative gain/loss vs the real driver's actual strategy"
          >
            ARIS Δ {ghostDelta >= 0 ? "▲" : "▼"}
            {fmtGhostDelta(ghostDelta)}
          </div>
        )}
        <div className="mt-1 grid grid-cols-3 gap-1 font-mono-data text-[8px] uppercase tracking-wide text-muted">
          <span>S1 {fmtSectorTime(s1)}</span>
          <span>S2 {fmtSectorTime(s2)}</span>
          <span>S3 {fmtSectorTime(s3)}</span>
        </div>
      </div>
    </DraggableHud>
  );
}
