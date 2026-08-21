import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { LapsResponse } from "../api/types";
import { C, T } from "../theme";
import { Panel, PanelError, SkeletonPanel } from "./atoms";

export function LapTimeChart({
  laps,
  upTo,
  focus,
  colourBy,
  pitLaps,
  scRanges,
}: {
  laps: { status: string; data?: LapsResponse; error?: string; retry: () => void };
  upTo: number;
  focus?: string;
  colourBy: Map<string, string>;
  pitLaps: number[];
  scRanges: [number, number][];
}) {
  const allCodes = useMemo(() => {
    if (laps.status !== "ok" || !laps.data) return [] as string[];
    return [...new Set(laps.data.laps.map((l) => l.driver_code))];
  }, [laps]);
  const [visible, setVisible] = useState<string[] | null>(null);
  const shown = visible ?? allCodes;

  const rows = useMemo(() => {
    if (laps.status !== "ok" || !laps.data) return [] as Record<string, number>[];
    const byLap = new Map<number, Record<string, number>>();
    for (const lap of laps.data.laps) {
      if (lap.lap_number > upTo || lap.lap_time_ms == null) continue;
      if (!shown.includes(lap.driver_code)) continue;
      const row = byLap.get(lap.lap_number) ?? { lap: lap.lap_number };
      row[lap.driver_code] = lap.lap_time_ms / 1000;
      byLap.set(lap.lap_number, row);
    }
    return [...byLap.values()].sort((a, b) => a.lap - b.lap);
  }, [laps, upTo, shown]);

  const lastLap = rows.length ? Number(rows[rows.length - 1].lap) : upTo;
  const chartWidth = Math.max(560, lastLap * 36);

  const toggle = (code: string) => {
    setVisible((cur) => {
      const base = cur ?? allCodes;
      return base.includes(code) ? base.filter((c) => c !== code) : [...base, code];
    });
  };

  return (
    <Panel
      title="LAP TIME TREND"
      right={<span style={{ fontFamily: T.mono, fontSize: 9, color: C.faint }}>SCROLL →</span>}
    >
      {laps.status === "loading" && (
        <SkeletonPanel rows={8} label="Loading laps — this may take a moment on first load as data is being cached..." />
      )}
      {laps.status === "error" && <PanelError message={laps.error || ""} onRetry={laps.retry} />}
      {laps.status === "ok" && (
        <div style={{ height: "100%", minHeight: 0, display: "flex", flexDirection: "column" }}>
          <div
            style={{
              display: "flex",
              flexWrap: "nowrap",
              gap: 4,
              padding: "6px 8px",
              overflowX: "auto",
              flexShrink: 0,
            }}
          >
            <button onClick={() => setVisible(allCodes)} style={chip(true)}>
              ALL
            </button>
            <button onClick={() => setVisible([])} style={chip(false)}>
              CLEAR
            </button>
            {allCodes.map((code) => {
              const on = shown.includes(code);
              const col = colourBy.get(code) || C.signal;
              return (
                <button
                  key={code}
                  onClick={() => toggle(code)}
                  style={{
                    ...chip(on),
                    background: on ? col : "transparent",
                    border: `1px solid ${col}`,
                    color: on ? C.ink : col,
                    flexShrink: 0,
                  }}
                >
                  {code}
                </button>
              );
            })}
          </div>
          <div style={{ flex: 1, minHeight: 120, overflowX: "auto", overflowY: "hidden" }}>
            <div style={{ width: chartWidth, height: "100%", minHeight: 120 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={rows} margin={{ top: 8, right: 28, left: 4, bottom: 12 }}>
                  <CartesianGrid stroke={C.ghost} strokeDasharray="2 4" vertical={false} />
                  <XAxis
                    dataKey="lap"
                    tick={{ fill: C.faint, fontSize: 9 }}
                    axisLine={false}
                    tickLine={false}
                    interval={Math.max(0, Math.floor(lastLap / 20))}
                  />
                  <YAxis
                    tick={{ fill: C.faint, fontSize: 9 }}
                    domain={["dataMin - 0.3", "dataMax + 0.5"]}
                    axisLine={false}
                    tickLine={false}
                    width={42}
                  />
                  <Tooltip contentStyle={{ background: C.panel2, border: `1px solid ${C.border}`, fontSize: 10 }} />
                  {scRanges.map(([a, b], i) => (
                    <ReferenceArea key={i} x1={a} x2={b} fill={C.ghost} fillOpacity={0.45} />
                  ))}
                  {pitLaps.map((lap) => (
                    <ReferenceLine key={lap} x={lap} stroke={C.signal} strokeDasharray="4 4" />
                  ))}
                  {shown.map((code) => (
                    <Line
                      key={code}
                      type="monotone"
                      dataKey={code}
                      stroke={colourBy.get(code) || C.signal}
                      strokeWidth={code === focus ? 2.2 : 1.2}
                      dot={false}
                      isAnimationActive={false}
                      connectNulls
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
    </Panel>
  );
}

function chip(on: boolean) {
  return {
    padding: "2px 7px",
    cursor: "pointer" as const,
    fontFamily: T.mono,
    fontSize: 9,
    background: on ? C.signalMid : "transparent",
    border: `1px solid ${on ? C.signal : C.border}`,
    color: on ? C.signal : C.mist,
  };
}
