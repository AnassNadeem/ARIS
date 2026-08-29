"use client";

import { useEffect, useState } from "react";
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
import { usePanelHistory } from "@/lib/usePanelHistory";
import { useFocusDriver } from "@/lib/useFocusDriver";
import { PanelEmpty, PanelSkeleton, usePanelFeedLoading } from "@/components/ui/PanelStates";

export function GapChart() {
  const focused = useFocusDriver();
  const [driver, setDriver] = useState(focused);
  const { laps, drivers } = usePanelHistory();
  const loading = usePanelFeedLoading();

  useEffect(() => {
    if (focused) setDriver(focused);
  }, [focused]);
  const data = laps.filter((l) => l.driverCode === driver).map((l) => ({
    lap: l.lap,
    ahead: l.gapAheadS != null ? Number(l.gapAheadS.toFixed(2)) : null,
    behind: l.gapBehindS != null ? Number(l.gapBehindS.toFixed(2)) : null,
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
      </div>
      <div className="relative min-h-0 flex-1">
        {data.length === 0 && loading ? (
          <PanelSkeleton />
        ) : data.length === 0 ? (
          <PanelEmpty
            title="Gap chart"
            detail="Gap to the car ahead and behind over race distance. Empty until lap gaps are available for this driver."
          />
        ) : (
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -12 }}>
            <CartesianGrid stroke="#2a2a2a" strokeDasharray="2 4" />
            <XAxis dataKey="lap" stroke="#888888" tick={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }} />
            <YAxis stroke="#888888" tick={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }} width={40} />
            <Tooltip contentStyle={{ background: "#1a1a1a", border: "1px solid #2a2a2a", fontFamily: "var(--font-jbmono)", fontSize: 11 }} />
            <Line type="monotone" dataKey="ahead" stroke="#e8002d" name="Gap ahead" dot={false} strokeWidth={2} isAnimationActive={false} connectNulls />
            <Line type="monotone" dataKey="behind" stroke="#39ff14" name="Gap behind" dot={false} strokeWidth={2} isAnimationActive={false} connectNulls />
            <Legend wrapperStyle={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }} />
          </LineChart>
        </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
