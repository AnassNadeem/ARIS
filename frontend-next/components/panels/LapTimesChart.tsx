"use client";

import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useRaceStore } from "@/store/raceStore";
import { usePanelHistory } from "@/lib/usePanelHistory";
import { useFocusDriver } from "@/lib/useFocusDriver";
import { PanelEmpty, PanelSkeleton, usePanelFeedLoading } from "@/components/ui/PanelStates";
import { topNDriverCodes } from "@/lib/panelData";

type Filter = "all" | "top5" | "aris";

/** Returns the fill colour and opacity for a race phase band. */
function phaseBandStyle(phase: string): { fill: string; fillOpacity: number } | null {
  switch (phase) {
    case "SC":
      return { fill: "#FF8700", fillOpacity: 0.35 };
    case "VSC":
      return { fill: "#FF8700", fillOpacity: 0.20 };
    case "RED_FLAG":
      return { fill: "#E8002D", fillOpacity: 0.25 };
    case "FORMATION_LAP":
      return { fill: "#FFFFFF", fillOpacity: 0.08 };
    default:
      return null;
  }
}

export function LapTimesChart() {
  const arisDriver = useFocusDriver();
  const isARISOn = useRaceStore((s) => s.isARISOn);
  const ghostData = useRaceStore((s) => s.ghostData);
  const phaseHistory = useRaceStore((s) => s.phaseHistory);
  const cars = useRaceStore((s) => s.cars);
  const [filter, setFilter] = useState<Filter>("top5");

  const { laps, drivers, currentLap } = usePanelHistory();
  const loading = usePanelFeedLoading();

  const driverCodes = useMemo(() => {
    if (filter === "aris") return arisDriver ? [arisDriver] : [];
    if (filter === "top5") {
      const top = topNDriverCodes(5, cars, laps, currentLap);
      if (top.length) return top;
    }
    return drivers.map((d) => d.driver_code);
  }, [filter, arisDriver, drivers, cars, laps, currentLap]);

  const data = useMemo(() => {
    const byLap: Record<number, Record<string, number | string>> = {};
    for (const rec of laps) {
      if (!driverCodes.includes(rec.driverCode)) continue;
      const row = byLap[rec.lap] ?? { lap: rec.lap };
      row[rec.driverCode] = Number(rec.lapTimeS.toFixed(3));
      row[`${rec.driverCode}__compound`] = rec.compound;
      row[`${rec.driverCode}__age`] = rec.tyreAge;
      if (rec.driverCode === arisDriver && ghostData?.delta_history?.length) {
        const pt = ghostData.delta_history.find((p) => p.lap === rec.lap);
        if (pt) row.ghost = Number((rec.lapTimeS + pt.delta).toFixed(3));
      }
      byLap[rec.lap] = row;
    }
    return Object.values(byLap).sort((a, b) => (a.lap as number) - (b.lap as number));
  }, [laps, driverCodes, arisDriver, ghostData]);

  // Build lap ranges from phaseHistory for non-GREEN phases.
  const phaseBands = useMemo(() => {
    if (!phaseHistory.length) return [];
    const bands: { startLap: number; endLap: number; phase: string }[] = [];
    let current: { startLap: number; phase: string } | null = null;
    for (const entry of phaseHistory) {
      if (entry.phase !== "GREEN") {
        if (!current || current.phase !== entry.phase) {
          if (current) bands.push({ ...current, endLap: entry.lap - 1 });
          current = { startLap: entry.lap, phase: entry.phase };
        }
      } else if (current) {
        bands.push({ ...current, endLap: entry.lap - 1 });
        current = null;
      }
    }
    if (current) {
      const lastLap = phaseHistory[phaseHistory.length - 1].lap;
      bands.push({ ...current, endLap: lastLap });
    }
    return bands;
  }, [phaseHistory]);

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-carbon p-2 [overflow-anchor:none]">
      <div className="mb-2 flex gap-2">
        {(["all", "top5", "aris"] as Filter[]).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded px-2 py-1 font-sans text-[10px] uppercase ${
              filter === f ? "bg-red text-white" : "bg-surface text-muted hover:text-white"
            }`}
          >
            {f === "all" ? "All drivers" : f === "top5" ? "Top 5" : "ARIS only"}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1">
        {loading && data.length === 0 ? (
          <PanelSkeleton />
        ) : data.length === 0 ? (
          <PanelEmpty
            title="Lap times"
            detail="Lap-time traces for the field, with safety-car bands overlaid. Empty until you click Start Race and completed laps arrive."
          />
        ) : (
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -12 }}>
            <CartesianGrid stroke="#2a2a2a" strokeDasharray="2 4" />
            <XAxis
              dataKey="lap"
              stroke="#888888"
              tick={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }}
              label={{ value: "Lap", position: "insideBottom", offset: -2, fill: "#888888", fontSize: 10 }}
            />
            <YAxis
              stroke="#888888"
              tick={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }}
              domain={["auto", "auto"]}
              width={48}
              label={{ value: "Lap time (s)", angle: -90, position: "insideLeft", fill: "#888888", fontSize: 10 }}
            />
            {/* FSM phase bands from live/replay phaseHistory */}
            {phaseBands.map((band, i) => {
              const style = phaseBandStyle(band.phase);
              if (!style) return null;
              return (
                <ReferenceArea
                  key={`phase-${i}`}
                  x1={band.startLap}
                  x2={band.endLap}
                  fill={style.fill}
                  fillOpacity={style.fillOpacity}
                />
              );
            })}
            <Tooltip
              contentStyle={{ background: "#1a1a1a", border: "1px solid #2a2a2a", fontFamily: "var(--font-jbmono)", fontSize: 11 }}
              labelStyle={{ color: "#888888" }}
            />
            {driverCodes.map((code) => {
              const meta = drivers.find((d) => d.driver_code === code);
              const isFocus = code === arisDriver;
              return (
                <Line
                  key={code}
                  type="monotone"
                  dataKey={code}
                  stroke={isFocus ? "#ffffff" : meta?.team_colour ?? "#888888"}
                  strokeOpacity={isFocus ? 1 : 0.5}
                  strokeWidth={isFocus ? 2 : 1.5}
                  dot={false}
                  isAnimationActive={false}
                />
              );
            })}
            {isARISOn && (
              <Line
                type="monotone"
                dataKey="ghost"
                stroke="#e8002d"
                strokeDasharray="5 4"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
                name="[A] ghost"
              />
            )}
            <Legend wrapperStyle={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }} />
          </LineChart>
        </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
