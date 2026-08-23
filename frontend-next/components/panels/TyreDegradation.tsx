"use client";

import { useCallback, useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  ReferenceLine,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ResponsiveContainer,
} from "recharts";
import { useRaceStore } from "@/store/raceStore";
import { driverLaps, getRaceHistoryMock } from "@/lib/mockRaceHistory";
import { COMPOUND_COLOUR, MOCK_DRIVERS_2025 } from "@/lib/mockData";
import type { Compound } from "@/lib/types";

const SLOPES: Record<Compound, number> = { SOFT: 0.08, MEDIUM: 0.05, HARD: 0.03, INTERMEDIATE: 0.02, WET: 0.02 };
const COMPOUNDS: Compound[] = ["SOFT", "MEDIUM", "HARD"];

export function TyreDegradation() {
  const arisDriver = useRaceStore((s) => s.arisDriver) ?? "VER";
  const [driver, setDriver] = useState(arisDriver);
  const [compareDriver, setCompareDriver] = useState<string>("");

  const { stints } = getRaceHistoryMock();

  const pointsFor = useCallback(
    (code: string) => {
      const driverStints = stints.filter((s) => s.driverCode === code);
      const laps = driverLaps(code);
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
    [stints],
  );

  const series = useMemo(() => pointsFor(driver), [driver, pointsFor]);
  const compareSeries = useMemo(
    () => (compareDriver ? pointsFor(compareDriver) : null),
    [compareDriver, pointsFor],
  );

  return (
    <div className="flex h-full flex-col bg-carbon p-2">
      <div className="mb-2 flex flex-wrap items-center gap-2 font-mono-data text-[10px]">
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
        <span className="text-muted">vs</span>
        <select
          value={compareDriver}
          onChange={(e) => setCompareDriver(e.target.value)}
          className="rounded border border-border bg-surface px-1.5 py-0.5 text-white"
        >
          <option value="">—</option>
          {MOCK_DRIVERS_2025.filter((d) => d.driver_code !== driver).map((d) => (
            <option key={d.driver_code} value={d.driver_code}>{d.driver_code}</option>
          ))}
        </select>
      </div>
      <div className="min-h-0 flex-1">
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
            {COMPOUNDS.map((c) => (
              <ReferenceLine
                key={`slope-${c}`}
                segment={[{ x: 1, y: -SLOPES[c] * 5 }, { x: 20, y: SLOPES[c] * 15 }]}
                stroke={COMPOUND_COLOUR[c]}
                strokeDasharray="4 3"
                strokeOpacity={0.5}
              />
            ))}
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
      </div>
    </div>
  );
}
