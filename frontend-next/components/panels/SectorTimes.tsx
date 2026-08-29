"use client";

import { useEffect, useMemo, useState } from "react";
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
import { usePanelHistory } from "@/lib/usePanelHistory";
import { useFocusDriver } from "@/lib/useFocusDriver";
import { PanelEmpty, PanelSkeleton, usePanelFeedLoading } from "@/components/ui/PanelStates";

export function SectorTimes() {
  const focused = useFocusDriver();
  const [driver, setDriver] = useState(focused);
  const { laps: allLaps, drivers } = usePanelHistory();
  const loading = usePanelFeedLoading();

  useEffect(() => {
    if (focused) setDriver(focused);
  }, [focused]);
  const laps = allLaps.filter((l) => l.driverCode === driver && (l.s1 > 0 || l.s2 > 0 || l.s3 > 0));

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
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-carbon p-2 [overflow-anchor:none]">
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
        <span className="font-mono-data text-muted">
          {Number.isFinite(pbs.s1)
            ? `PB S1 ${pbs.s1.toFixed(3)} · S2 ${pbs.s2.toFixed(3)} · S3 ${pbs.s3.toFixed(3)}`
            : "Waiting for lap data…"}
        </span>
      </div>
      <div className="relative min-h-0 flex-1">
        {data.length === 0 && loading ? (
          <PanelSkeleton />
        ) : data.length === 0 ? (
          <PanelEmpty
            title="Sector times"
            detail="S1/S2/S3 stacked per lap, compared to personal best. Empty until sector times are in the lap feed for this driver."
          />
        ) : (
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
        )}
      </div>
    </div>
  );
}
