"use client";

import { useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useRaceStore } from "@/store/raceStore";
import { driverLaps } from "@/lib/mockRaceHistory";
import { MOCK_DRIVERS_2025 } from "@/lib/mockData";

export function GapChart() {
  const arisDriver = useRaceStore((s) => s.arisDriver) ?? "VER";
  const [driver, setDriver] = useState(arisDriver);
  const laps = driverLaps(driver);
  const data = laps.map((l) => ({
    lap: l.lap,
    ahead: l.gapAheadS != null ? Number(l.gapAheadS.toFixed(2)) : null,
    behind: l.gapBehindS != null ? Number(l.gapBehindS.toFixed(2)) : null,
  }));

  return (
    <div className="flex h-full flex-col bg-carbon p-2">
      <div className="mb-2 flex items-center gap-2 font-mono-data text-[10px]">
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
      <div className="min-h-0 flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -12 }}>
            <CartesianGrid stroke="#2a2a2a" strokeDasharray="2 4" />
            <XAxis dataKey="lap" stroke="#888888" tick={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }} />
            <YAxis stroke="#888888" tick={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }} width={40} />
            <Tooltip contentStyle={{ background: "#1a1a1a", border: "1px solid #2a2a2a", fontFamily: "var(--font-jbmono)", fontSize: 11 }} />
            <Line type="monotone" dataKey="ahead" stroke="#e8002d" name="Gap ahead" dot={false} strokeWidth={2} isAnimationActive={false} />
            <Line type="monotone" dataKey="behind" stroke="#39ff14" name="Gap behind" dot={false} strokeWidth={2} isAnimationActive={false} />
            <Legend wrapperStyle={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
