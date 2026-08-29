"use client";

import { useState } from "react";
import { useRaceStore } from "@/store/raceStore";
import { usePanelHistory } from "@/lib/usePanelHistory";
import { TyreIcon } from "@/components/ui/TyreIcon";
import { PanelEmpty, PanelSkeleton, usePanelFeedLoading } from "@/components/ui/PanelStates";

export function StintSummary() {
  const arisDriver = useRaceStore((s) => s.arisDriver) ?? "VER";
  const [driver, setDriver] = useState(arisDriver);
  const { stints, drivers } = usePanelHistory();
  const loading = usePanelFeedLoading();
  const rows = stints.filter((s) => s.driverCode === driver);

  return (
    <div className="flex h-full flex-col bg-carbon p-2 font-mono-data text-xs">
      <div className="mb-2 flex items-center gap-2 font-sans text-xs">
        <span className="text-muted">Driver</span>
        <select
          value={driver}
          onChange={(e) => setDriver(e.target.value)}
          className="rounded border border-border bg-surface px-2 py-0.5 font-mono-data text-xs text-white"
        >
          {drivers.map((d) => (
            <option key={d.driver_code} value={d.driver_code}>{d.driver_code}</option>
          ))}
        </select>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading && rows.length === 0 ? (
          <PanelSkeleton rows={6} />
        ) : rows.length === 0 ? (
          <PanelEmpty
            title="Stint summary"
            detail="Compound, start/end lap, and average lap time per stint. Empty until pit and stint data exist for this driver."
          />
        ) : (
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-border font-sans text-[10px] uppercase text-muted">
              <th className="py-1.5">Stint</th>
              <th>Compound</th>
              <th>Start</th>
              <th>End</th>
              <th>Laps</th>
              <th className="text-right">Avg lap</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.stintNumber} className="border-b border-border/60">
                <td className="py-1.5 text-white">{r.stintNumber}</td>
                <td>
                  <span className="flex items-center gap-1.5">
                    <TyreIcon compound={r.compound} /> {r.compound}
                  </span>
                </td>
                <td className="text-muted">L{r.startLap}</td>
                <td className="text-muted">L{r.endLap}</td>
                <td className="text-muted">{r.endLap - r.startLap + 1}</td>
                <td className="text-right text-white">{r.avgLapTimeS.toFixed(3)}s</td>
              </tr>
            ))}
          </tbody>
        </table>
        )}
      </div>
    </div>
  );
}
