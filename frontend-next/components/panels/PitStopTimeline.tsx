"use client";

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
  ZAxis,
} from "recharts";
import { usePanelHistory } from "@/lib/usePanelHistory";
import { useRaceStore } from "@/store/raceStore";
import { PanelEmpty, PanelSkeleton, usePanelFeedLoading } from "@/components/ui/PanelStates";
import { AXIS_TICK, xAxisLabel, yAxisLabel } from "@/lib/chartAxis";

export function PitStopTimeline() {
  const { pitStops, drivers, totalLaps } = usePanelHistory();
  const isARISOn = useRaceStore((s) => s.isARISOn);
  const ghostTicks = useRaceStore((s) => s.ghostTicksByLap);
  const loading = usePanelFeedLoading();
  const distance = Math.max(1, totalLaps);
  const data = pitStops.map((p) => {
    const meta = drivers.find((d) => d.driver_code === p.driverCode);
    return { ...p, colour: meta?.team_colour ?? "#888888", kind: "field" as const };
  });
  const ghostPitData = isARISOn
    ? Object.values(ghostTicks)
        .sort((a, b) => a.lap - b.lap)
        .flatMap((tick, i, arr) => {
          if (i <= 0) return [];
          const prev = arr[i - 1];
          if (prev && prev.compound !== tick.compound) {
            return [{ driverCode: "ARIS", lap: tick.lap, durationS: 2.4, colour: "#e8002d", kind: "aris" as const }];
          }
          return [];
        })
    : [];
  const combined = [...data, ...ghostPitData];
  const avgStop =
    data.length > 0 ? Number((data.reduce((sum, item) => sum + item.durationS, 0) / data.length).toFixed(2)) : null;

  return (
    <div className="flex h-full flex-col bg-carbon p-2">
      <div className="min-h-0 flex-1">
        {loading && combined.length === 0 ? (
          <PanelSkeleton />
        ) : combined.length === 0 ? (
          <PanelEmpty
            title="Pit stop timeline"
            detail="Pit stops plotted as lap versus duration. Empty when nobody has boxed yet, or pit-in laps have not arrived."
          />
        ) : (
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 8, bottom: 24, left: 4 }}>
            <CartesianGrid stroke="#2a2a2a" strokeDasharray="2 4" />
            <XAxis
              type="number"
              dataKey="lap"
              name="Lap"
              stroke="#888888"
              tick={AXIS_TICK}
              domain={[1, distance]}
              label={xAxisLabel("Lap")}
            />
            <YAxis
              type="number"
              dataKey="durationS"
              name="Duration (s)"
              stroke="#888888"
              tick={AXIS_TICK}
              width={48}
              label={yAxisLabel("Pit duration (s)")}
            />
            {avgStop != null && (
              <ReferenceLine
                y={avgStop}
                stroke="#888888"
                strokeDasharray="3 3"
                label={{ value: `Field avg ${avgStop}s`, position: "right", fill: "#888888", fontSize: 10 }}
              />
            )}
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
              data={combined}
              animationDuration={300}
              legendType="circle"
              name="Pit events"
              shape={(props: { cx?: number; cy?: number; payload?: { colour: string; kind?: "field" | "aris" } }) => (
                <circle
                  cx={props.cx}
                  cy={props.cy}
                  r={5}
                  fill={props.payload?.kind === "aris" ? "transparent" : props.payload?.colour ?? "#e8002d"}
                  stroke={props.payload?.kind === "aris" ? "#e8002d" : "#0a0a0a"}
                  strokeDasharray={props.payload?.kind === "aris" ? "2 2" : undefined}
                  strokeWidth={props.payload?.kind === "aris" ? 2 : 1}
                />
              )}
            />
            <Legend wrapperStyle={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }} />
          </ScatterChart>
        </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
