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
import { getRaceHistoryMock, scLapRanges, TOTAL_LAPS_MOCK } from "@/lib/mockRaceHistory";
import { MOCK_DRIVERS_2025 } from "@/lib/mockData";

type Filter = "all" | "top5" | "aris";

export function LapTimesChart() {
  const arisDriver = useRaceStore((s) => s.arisDriver) ?? "VER";
  const isARISOn = useRaceStore((s) => s.isARISOn);
  const [filter, setFilter] = useState<Filter>("top5");

  const { laps } = getRaceHistoryMock();

  const driverCodes = useMemo(() => {
    if (filter === "aris") return [arisDriver];
    if (filter === "top5") return MOCK_DRIVERS_2025.slice(0, 5).map((d) => d.driver_code);
    return MOCK_DRIVERS_2025.map((d) => d.driver_code);
  }, [filter, arisDriver]);

  const data = useMemo(() => {
    const byLap: Record<number, Record<string, number | string>> = {};
    for (const rec of laps) {
      if (!driverCodes.includes(rec.driverCode)) continue;
      const row = byLap[rec.lap] ?? { lap: rec.lap };
      row[rec.driverCode] = Number(rec.lapTimeS.toFixed(3));
      row[`${rec.driverCode}__compound`] = rec.compound;
      row[`${rec.driverCode}__age`] = rec.tyreAge;
      if (rec.driverCode === arisDriver) {
        row.ghost = Number((rec.lapTimeS - (3.4 / TOTAL_LAPS_MOCK) * rec.lap).toFixed(3));
      }
      byLap[rec.lap] = row;
    }
    return Object.values(byLap).sort((a, b) => (a.lap as number) - (b.lap as number));
  }, [laps, driverCodes, arisDriver]);

  return (
    <div className="flex h-full flex-col bg-carbon p-2">
      <div className="mb-2 flex gap-1">
        {(["all", "top5", "aris"] as Filter[]).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded px-2 py-1 font-mono-data text-[10px] uppercase ${
              filter === f ? "bg-red text-white" : "bg-surface text-muted hover:text-white"
            }`}
          >
            {f === "all" ? "All drivers" : f === "top5" ? "Top 5" : "ARIS only"}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -12 }}>
            <CartesianGrid stroke="#2a2a2a" strokeDasharray="2 4" />
            <XAxis
              dataKey="lap"
              stroke="#888888"
              tick={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }}
            />
            <YAxis
              stroke="#888888"
              tick={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }}
              domain={["auto", "auto"]}
              width={40}
            />
            {scLapRanges().map((z, i) => (
              <ReferenceArea key={i} x1={z.startLap} x2={z.endLap} fill="#f5a623" fillOpacity={0.12} />
            ))}
            <Tooltip
              contentStyle={{ background: "#1a1a1a", border: "1px solid #2a2a2a", fontFamily: "var(--font-jbmono)", fontSize: 11 }}
              labelStyle={{ color: "#888888" }}
            />
            {driverCodes.map((code) => {
              const meta = MOCK_DRIVERS_2025.find((d) => d.driver_code === code);
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
      </div>
    </div>
  );
}
