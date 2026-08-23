"use client";

import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useRaceStore } from "@/store/raceStore";
import { driverLaps } from "@/lib/mockRaceHistory";
import { MOCK_DRIVERS_2025 } from "@/lib/mockData";

export function SectorTimes() {
  const arisDriver = useRaceStore((s) => s.arisDriver) ?? "VER";
  const [driver, setDriver] = useState(arisDriver);
  const laps = driverLaps(driver);

  const pbs = useMemo(() => {
    let s1 = Infinity, s2 = Infinity, s3 = Infinity;
    for (const l of laps) {
      s1 = Math.min(s1, l.s1);
      s2 = Math.min(s2, l.s2);
      s3 = Math.min(s3, l.s3);
    }
    return { s1, s2, s3 };
  }, [laps]);

  const data = laps.map((l) => ({
    lap: l.lap,
    s1: Number(l.s1.toFixed(3)),
    s2: Number(l.s2.toFixed(3)),
    s3: Number(l.s3.toFixed(3)),
    s1Delta: Number((l.s1 - pbs.s1).toFixed(3)),
    s2Delta: Number((l.s2 - pbs.s2).toFixed(3)),
    s3Delta: Number((l.s3 - pbs.s3).toFixed(3)),
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
        <span className="text-muted">PB S1 {pbs.s1.toFixed(3)} · S2 {pbs.s2.toFixed(3)} · S3 {pbs.s3.toFixed(3)}</span>
      </div>
      <div className="min-h-0 flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -12 }}>
            <CartesianGrid stroke="#2a2a2a" strokeDasharray="2 4" />
            <XAxis dataKey="lap" stroke="#888888" tick={{ fontFamily: "var(--font-jbmono)", fontSize: 9 }} />
            <YAxis stroke="#888888" tick={{ fontFamily: "var(--font-jbmono)", fontSize: 9 }} width={40} />
            <Tooltip
              contentStyle={{ background: "#1a1a1a", border: "1px solid #2a2a2a", fontFamily: "var(--font-jbmono)", fontSize: 11 }}
            />
            <Bar dataKey="s1" stackId="a" fill="#39ff14" name="S1" isAnimationActive={false} />
            <Bar dataKey="s2" stackId="a" fill="#f5a623" name="S2" isAnimationActive={false} />
            <Bar dataKey="s3" stackId="a" fill="#e8002d" name="S3" isAnimationActive={false} />
            <Legend wrapperStyle={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
