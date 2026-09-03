"use client";

import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useRaceStore } from "@/store/raceStore";
import { usePanelHistory, useAnalyticsReady } from "@/lib/usePanelHistory";
import { useFocusDriver } from "@/lib/useFocusDriver";
import { pitLossForCircuit } from "@/lib/r2Replay";
import { AXIS_TICK, xAxisLabel, yAxisLabel } from "@/lib/chartAxis";
import { PanelEmpty, PanelSkeleton, usePanelFeedLoading } from "@/components/ui/PanelStates";

const UNDERCUT_GAIN_S = 1.2;

export function UndercutWindow() {
  const focused = useFocusDriver();
  const [driver, setDriver] = useState(focused);
  const { laps, drivers } = usePanelHistory();
  const ready = useAnalyticsReady();
  const loading = usePanelFeedLoading();
  const circuit = useRaceStore((s) => s.session?.circuitName ?? "");
  const pitLoss = pitLossForCircuit(circuit);

  const data = useMemo(() => {
    const threshold = Math.max(2, pitLoss - UNDERCUT_GAIN_S);
    return laps
      .filter((l) => l.driverCode === driver)
      .map((l) => {
        const gap = l.gapAheadS;
        const open = gap != null && gap > 0.15 && gap < threshold;
        return {
          lap: l.lap,
          gap: gap != null ? Number(gap.toFixed(2)) : null,
          window: open ? threshold : null,
        };
      });
  }, [laps, driver, pitLoss]);

  const openLaps = data.filter((d) => d.window != null).map((d) => d.lap);

  if (!ready) {
    return (
      <PanelEmpty
        title="Undercut window"
        detail="Laps where the gap ahead is inside a typical undercut (pit-loss minus ~1.2s). Empty until you click Start Race."
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
          Pit loss {pitLoss.toFixed(1)}s · window &lt; {(pitLoss - UNDERCUT_GAIN_S).toFixed(1)}s
          {openLaps.length ? ` · open L${openLaps[0]}–L${openLaps[openLaps.length - 1]}` : " · closed"}
        </span>
      </div>
      <div className="relative min-h-0 flex-1">
        {data.length === 0 && loading ? (
          <PanelSkeleton />
        ) : data.length === 0 ? (
          <PanelEmpty title="Undercut window" detail="Need gap-ahead laps before the window can be drawn." />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: 4 }}>
              <CartesianGrid stroke="#2a2a2a" strokeDasharray="2 4" />
              <XAxis dataKey="lap" stroke="#888888" tick={AXIS_TICK} label={xAxisLabel("Lap")} />
              <YAxis stroke="#888888" tick={AXIS_TICK} width={44} label={yAxisLabel("Gap ahead (s)")} />
              <Tooltip
                cursor={{ strokeDasharray: "3 3" }}
                contentStyle={{ background: "#1a1a1a", border: "1px solid #2a2a2a", fontFamily: "var(--font-jbmono)", fontSize: 11 }}
              />
              <ReferenceLine
                y={Math.max(2, pitLoss - UNDERCUT_GAIN_S)}
                stroke="#f5a623"
                strokeDasharray="4 3"
                label={{ value: "Window ceiling", fill: "#f5a623", fontSize: 9, position: "insideTopRight" }}
              />
              <Line type="monotone" dataKey="gap" name="Gap ahead" stroke="#e8002d" dot={false} activeDot={{ r: 3 }} strokeWidth={2} animationDuration={280} connectNulls />
              <Legend wrapperStyle={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
