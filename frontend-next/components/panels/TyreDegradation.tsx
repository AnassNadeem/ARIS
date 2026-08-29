"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ResponsiveContainer,
} from "recharts";
import { COMPOUND_COLOUR } from "@/lib/mockData";
import { usePanelHistory } from "@/lib/usePanelHistory";
import { useFocusDriver } from "@/lib/useFocusDriver";
import { PanelEmpty, PanelSkeleton, usePanelFeedLoading } from "@/components/ui/PanelStates";
import type { Compound } from "@/lib/types";

const COMPOUNDS: Compound[] = ["SOFT", "MEDIUM", "HARD"];

export function TyreDegradation() {
  const focused = useFocusDriver();
  const [driver, setDriver] = useState(focused);
  const [compareDriver, setCompareDriver] = useState<string>("");

  const { stints, laps: allLaps, drivers } = usePanelHistory();
  const loading = usePanelFeedLoading();

  useEffect(() => {
    if (focused) setDriver(focused);
  }, [focused]);

  const pointsFor = useCallback(
    (code: string) => {
      const driverStints = stints.filter((s) => s.driverCode === code);
      const laps = allLaps.filter((l) => l.driverCode === code);
      return COMPOUNDS.map((compound) => {
        const pts: { age: number; delta: number }[] = [];
        for (const stint of driverStints.filter((s) => s.compound === compound)) {
          for (const lap of laps.filter((l) => l.lap >= stint.startLap && l.lap <= stint.endLap && !l.isSC)) {
            pts.push({ age: lap.tyreAge, delta: Number((lap.lapTimeS - stint.avgLapTimeS).toFixed(3)) });
          }
        }
        return { compound, pts };
      });
    },
    [stints, allLaps],
  );

  const series = useMemo(() => pointsFor(driver), [driver, pointsFor]);
  const compareSeries = useMemo(
    () => (compareDriver ? pointsFor(compareDriver) : null),
    [compareDriver, pointsFor],
  );
  const hasPoints = series.some((s) => s.pts.length > 0);

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-carbon p-2 [overflow-anchor:none]">
      <div className="mb-2 flex flex-wrap items-center gap-2 font-sans text-xs">
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
        <span className="text-muted">vs</span>
        <select
          value={compareDriver}
          onChange={(e) => setCompareDriver(e.target.value)}
          className="rounded border border-border bg-surface px-2 py-0.5 font-mono-data text-xs text-white"
        >
          <option value="">—</option>
          {drivers.filter((d) => d.driver_code !== driver).map((d) => (
            <option key={d.driver_code} value={d.driver_code}>{d.driver_code}</option>
          ))}
        </select>
      </div>
      <div className="relative min-h-0 flex-1">
        {!hasPoints && loading ? (
          <PanelSkeleton />
        ) : !hasPoints ? (
          <PanelEmpty
            title="Tyre degradation"
            detail="Lap-time delta versus tyre age, per compound, for the selected driver. Empty until stint and lap data exist — typically after a few completed laps."
          />
        ) : (
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 4, right: 8, bottom: 0, left: -12 }}>
            <CartesianGrid stroke="#2a2a2a" strokeDasharray="2 4" />
            <XAxis
              type="number"
              dataKey="age"
              name="Tyre age"
              stroke="#888888"
              tick={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }}
              label={{ value: "Tyre age (laps)", position: "insideBottom", offset: -2, fill: "#888888", fontSize: 10 }}
            />
            <YAxis
              type="number"
              dataKey="delta"
              name="Δ vs stint avg"
              stroke="#888888"
              tick={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }}
              width={40}
            />
            <Tooltip
              cursor={{ strokeDasharray: "3 3" }}
              contentStyle={{ background: "#1a1a1a", border: "1px solid #2a2a2a", fontFamily: "var(--font-jbmono)", fontSize: 11 }}
            />
            {series.map((s) => (
              <Scatter
                key={s.compound}
                name={`${driver} ${s.compound}`}
                data={s.pts}
                fill={COMPOUND_COLOUR[s.compound]}
                isAnimationActive={false}
              />
            ))}
            {compareSeries?.map((s) => (
              <Scatter
                key={`cmp-${s.compound}`}
                name={`${compareDriver} ${s.compound}`}
                data={s.pts}
                fill={COMPOUND_COLOUR[s.compound]}
                fillOpacity={0.35}
                shape="cross"
                isAnimationActive={false}
              />
            ))}
            <Legend wrapperStyle={{ fontFamily: "var(--font-jbmono)", fontSize: 9 }} />
          </ScatterChart>
        </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
