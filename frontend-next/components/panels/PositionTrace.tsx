"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { usePanelHistory } from "@/lib/usePanelHistory";
import { PanelEmpty, PanelSkeleton, usePanelFeedLoading } from "@/components/ui/PanelStates";
import { AXIS_TICK, xAxisLabel, yAxisLabel } from "@/lib/chartAxis";

export function PositionTrace() {
  const { laps, drivers } = usePanelHistory();
  const loading = usePanelFeedLoading();
  const codes = drivers.map((d) => d.driver_code);
  const maxPos = Math.max(
    1,
    codes.length,
    ...laps.map((l) => l.position).filter((p) => Number.isFinite(p)),
  );

  const byLap: Record<number, Record<string, number>> = {};
  for (const l of laps) {
    byLap[l.lap] = { ...(byLap[l.lap] ?? { lap: l.lap }), [l.driverCode]: l.position };
  }
  const data = Object.values(byLap).sort((a, b) => a.lap - b.lap);

  return (
    <div className="flex h-full flex-col bg-carbon p-2">
      <div className="min-h-0 flex-1">
        {loading && data.length === 0 ? (
          <PanelSkeleton />
        ) : data.length === 0 ? (
          <PanelEmpty
            title="Position trace"
            detail="Position (P1–P20) per lap for the field. Empty until lap positions arrive from the session feed."
          />
        ) : (
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -12 }}>
            <CartesianGrid stroke="#2a2a2a" strokeDasharray="2 4" />
            <XAxis
              dataKey="lap"
              stroke="#888888"
              tick={AXIS_TICK}
              label={xAxisLabel("Lap")}
            />
            <YAxis
              reversed
              domain={[1, maxPos]}
              stroke="#888888"
              tick={AXIS_TICK}
              width={40}
              label={yAxisLabel("Position")}
            />
            <Tooltip contentStyle={{ background: "#1a1a1a", border: "1px solid #2a2a2a", fontFamily: "var(--font-jbmono)", fontSize: 11 }} />
            {codes.map((code) => {
              const meta = drivers.find((d) => d.driver_code === code);
              return (
                <Line
                  key={code}
                  type="stepAfter"
                  dataKey={code}
                  stroke={meta?.team_colour ?? "#888888"}
                  dot={false}
                  strokeWidth={1.5}
                  isAnimationActive={false}
                />
              );
            })}
          </LineChart>
        </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
