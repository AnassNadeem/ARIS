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
import { usePanelHistory, useAnalyticsReady } from "@/lib/usePanelHistory";
import { useFocusDriver } from "@/lib/useFocusDriver";
import { AXIS_TICK, xAxisLabel, yAxisLabel } from "@/lib/chartAxis";
import { PanelEmpty, PanelSkeleton, usePanelFeedLoading } from "@/components/ui/PanelStates";

const DIRTY_S = 1.0;

export function DirtyAir() {
  const focused = useFocusDriver();
  const [driver, setDriver] = useState(focused);
  const { laps, drivers } = usePanelHistory();
  const ready = useAnalyticsReady();
  const loading = usePanelFeedLoading();

  const data = useMemo(() => {
    return laps
      .filter((l) => l.driverCode === driver)
      .map((l) => ({
        lap: l.lap,
        gap: l.gapAheadS != null ? Number(l.gapAheadS.toFixed(2)) : null,
        dirty: l.gapAheadS != null && l.gapAheadS > 0 && l.gapAheadS < DIRTY_S ? 1 : 0,
      }));
  }, [laps, driver]);

  const dirtyLaps = data.filter((d) => d.dirty).map((d) => d.lap);

  if (!ready) {
    return (
      <PanelEmpty
        title="Dirty air zone"
        detail="Laps where the gap to the car ahead is under 1.0s. Empty until you click Start Race."
      />
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-carbon p-2">
      <div className="mb-2 flex flex-wrap items-center gap-2 font-sans text-xs">
        <span className="text-muted">Driver</span>
        <select
          value={driver}
          onChange={(e) => setDriver(e.target.value)}
          className="rounded border border-border bg-surface px-2 py-0.5 font-mono-data text-xs text-white"
        >
          {drivers.map((d) => (
            <option key={d.driver_code} value={d.driver_code}>
              {d.driver_code}
            </option>
          ))}
        </select>
        <span className="font-mono-data text-[10px] text-muted">
          {dirtyLaps.length ? `${dirtyLaps.length} dirty-air lap${dirtyLaps.length === 1 ? "" : "s"}` : "No dirty-air laps yet"}
        </span>
      </div>
      <div className="relative min-h-0 flex-1">
        {data.length === 0 && loading ? (
          <PanelSkeleton />
        ) : data.length === 0 ? (
          <PanelEmpty title="Dirty air zone" detail="Gap-ahead data has not arrived for this driver." />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: 4 }}>
              <CartesianGrid stroke="#2a2a2a" strokeDasharray="2 4" />
              <XAxis dataKey="lap" stroke="#888888" tick={AXIS_TICK} label={xAxisLabel("Lap")} />
              <YAxis
                stroke="#888888"
                tick={AXIS_TICK}
                width={44}
                label={yAxisLabel("Gap ahead (s)")}
              />
              <Tooltip
                cursor={{ fill: "rgba(255,255,255,0.06)" }}
                contentStyle={{ background: "#1a1a1a", border: "1px solid #2a2a2a", fontFamily: "var(--font-jbmono)", fontSize: 11 }}
                formatter={(v, name) => [name === "gap" ? `${Number(v).toFixed(2)}s` : v, name === "gap" ? "Gap ahead" : "Dirty air"]}
              />
              <Bar dataKey="gap" name="Gap ahead" fill="#4FA8E0" animationDuration={260} />
              <Legend wrapperStyle={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
