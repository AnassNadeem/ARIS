"use client";

import { useState } from "react";
import { useRaceStore } from "@/store/raceStore";
import { getRaceHistoryMock } from "@/lib/mockRaceHistory";
import { MOCK_DRIVERS_2025 } from "@/lib/mockData";
import { TyreIcon } from "@/components/ui/TyreIcon";

export function StintSummary() {
  const arisDriver = useRaceStore((s) => s.arisDriver) ?? "VER";
  const [driver, setDriver] = useState(arisDriver);
  const { stints } = getRaceHistoryMock();
  const rows = stints.filter((s) => s.driverCode === driver);

  return (
    <div className="flex h-full flex-col bg-carbon p-2 font-mono-data text-[11px]">
      <div className="mb-2 flex items-center gap-2 text-[10px]">
        <span className="text-muted">Driver</span>
        <select
          value={driver}
          onChange={(e) => setDriver(e.target.value)}
          className="rounded border border-border bg-surface px-1.5 py-0.5 text-white"
        >
          {MOCK_DRIVERS_2025.map((d) => (
            <option key={d.driver_code} value={d.driver_code}>{d.driver_code}</option>
          ))}
        </select>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-border text-[10px] uppercase text-muted">
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
      </div>
    </div>
  );
}
