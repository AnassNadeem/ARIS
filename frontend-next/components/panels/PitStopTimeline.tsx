"use client";

import {
  CartesianGrid,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ResponsiveContainer,
  ZAxis,
} from "recharts";
import { getRaceHistoryMock } from "@/lib/mockRaceHistory";
import { MOCK_DRIVERS_2025 } from "@/lib/mockData";

export function PitStopTimeline() {
  const { pitStops } = getRaceHistoryMock();
  const data = pitStops.map((p) => {
    const meta = MOCK_DRIVERS_2025.find((d) => d.driver_code === p.driverCode);
    return { ...p, colour: meta?.team_colour ?? "#888888" };
  });

  return (
    <div className="flex h-full flex-col bg-carbon p-2">
      <div className="min-h-0 flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 4, right: 8, bottom: 0, left: -12 }}>
            <CartesianGrid stroke="#2a2a2a" strokeDasharray="2 4" />
            <XAxis
              type="number"
              dataKey="lap"
              name="Lap"
              stroke="#888888"
              tick={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }}
              domain={[1, 72]}
            />
            <YAxis
              type="number"
              dataKey="durationS"
              name="Duration (s)"
              stroke="#888888"
              tick={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }}
              width={40}
            />
            <ZAxis range={[60, 60]} />
            <Tooltip
              cursor={{ strokeDasharray: "3 3" }}
              contentStyle={{ background: "#1a1a1a", border: "1px solid #2a2a2a", fontFamily: "var(--font-jbmono)", fontSize: 11 }}
              formatter={(value, name, entry) => {
                const payload = entry?.payload as { driverCode?: string } | undefined;
                const num = typeof value === "number" ? value : Number(value);
                return [name === "durationS" ? `${num.toFixed(1)}s` : String(value), payload?.driverCode ?? String(name)];
              }}
            />
            <Scatter
              data={data}
              isAnimationActive={false}
              shape={(props: { cx?: number; cy?: number; payload?: { colour: string } }) => (
                <circle cx={props.cx} cy={props.cy} r={5} fill={props.payload?.colour ?? "#e8002d"} stroke="#0a0a0a" />
              )}
            />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
