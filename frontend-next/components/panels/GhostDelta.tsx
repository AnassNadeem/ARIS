"use client";

import { useMemo } from "react";
import {
  Area,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useRaceStore } from "@/store/raceStore";
import { PanelEmpty, PanelSkeleton, usePanelFeedLoading } from "@/components/ui/PanelStates";
import { useAnalyticsReady } from "@/lib/usePanelHistory";
import { AXIS_TICK, xAxisLabel, yAxisLabel } from "@/lib/chartAxis";
import { ghostDeltaChartPoints, ghostUnavailableMessage } from "@/lib/r2Replay";

function formatDelta(v: number): string {
  if (v >= 0) return `+${v.toFixed(2)}s`;
  return `${v.toFixed(2)}s`;
}

interface TooltipPayloadItem {
  value: number;
  name: string;
}

function GhostTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: number;
}) {
  if (!active || !payload?.length) return null;
  const delta = payload[0]?.value ?? 0;
  return (
    <div className="rounded border border-border bg-surface px-2 py-1.5 font-mono-data text-[10px]">
      <div className="text-muted">Lap {label}</div>
      <div className={delta >= 0 ? "text-green-400" : "text-red-400"}>
        Δ {formatDelta(delta)}
      </div>
    </div>
  );
}

export function GhostDelta() {
  const ghostData = useRaceStore((s) => s.ghostData);
  const ghostTicks = useRaceStore((s) => s.ghostTicksByLap);
  const currentLap = useRaceStore((s) => s.currentLap);
  const isARISOn = useRaceStore((s) => s.isARISOn);
  const ghostReason = useRaceStore((s) => s.ghostReason);
  const arisDriver = useRaceStore((s) => s.arisDriver ?? s.selectedDriver ?? s.focusDriver);
  const loading = usePanelFeedLoading();
  const ready = useAnalyticsReady();

  const chartData = useMemo(
    () => (ready ? ghostDeltaChartPoints(ghostData, ghostTicks, currentLap) : []),
    [ghostData, ghostTicks, currentLap, ready],
  );
  const hasGhost = Boolean(ghostData) || (isARISOn && Object.keys(ghostTicks).length > 0);

  if (!ready) {
    return (
      <PanelEmpty
        title="Ghost delta"
        detail="Time delta between the real driver and the ARIS ghost. Click Start Race in the header — the chart stays blank until lights-out."
      />
    );
  }

  if (loading && !hasGhost) {
    return <PanelSkeleton />;
  }

  if (!isARISOn || !hasGhost) {
    return (
      <PanelEmpty
        title="Ghost delta"
        detail={ghostUnavailableMessage(ghostReason, arisDriver ?? null, isARISOn)}
      />
    );
  }

  const divLap = ghostData?.divergence_lap ?? 1;
  const outcome = ghostData?.outcome;
  const pitLaps = ghostData?.plan_pit_laps ?? [];
  const pitCompounds = ghostData?.plan_pit_compounds ?? [];
  const driverCode = ghostData?.driver_code ?? arisDriver ?? "—";
  const arisAction = ghostData?.aris_action ?? "STAY_OUT";
  const realAction = ghostData?.real_action ?? "STAY_OUT";

  const outcomeLabel =
    outcome === "ARIS_CORRECT"
      ? "ARIS CORRECT ✓"
      : outcome === "ARIS_INCORRECT"
        ? "ARIS INCORRECT ✗"
        : null;

  const resolutionLap =
    chartData.length > 0 ? chartData[chartData.length - 1].lap : null;

  return (
    <div className="flex h-full flex-col bg-carbon">
      {/* Header */}
      <div className="shrink-0 border-b border-border px-4 py-2">
        <div className="flex items-center justify-between">
          <span className="font-sans text-xs text-white">
            Ghost Δ — <span className="font-mono-data">{driverCode}</span>
          </span>
          <span className="font-mono-data text-[10px] text-muted">
            Div. L{divLap}: {arisAction}{" "}
            <span className="text-amber">vs</span> {realAction}
          </span>
        </div>
        {outcome && (
          <div
            className={`mt-0.5 font-mono-data text-[10px] font-semibold ${
              outcome === "ARIS_CORRECT" ? "text-green-400" : "text-red-400"
            }`}
          >
            {outcomeLabel}
          </div>
        )}
      </div>

      {/* Chart */}
      <div className="min-h-0 flex-1 px-1 pb-2 pt-3">
        {chartData.length === 0 ? (
          <PanelEmpty
            title="Collecting ghost delta"
            detail="Ghost appears when ARIS's strategy diverges from the real driver's call. History fills in as laps complete after divergence."
          />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 8, right: 12, bottom: 8, left: 4 }}>
              <XAxis
                dataKey="lap"
                tick={AXIS_TICK}
                tickLine={false}
                axisLine={false}
                label={xAxisLabel("Lap")}
              />
              <YAxis
                tick={AXIS_TICK}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v) => `${v > 0 ? "+" : ""}${v.toFixed(0)}s`}
                width={44}
                label={yAxisLabel("Ghost Δ vs real (s)")}
              />
              <Tooltip content={<GhostTooltip />} cursor={{ strokeDasharray: "3 3" }} />

              {/* Zero reference line — ghost is running exactly the real driver's pace */}
              <ReferenceLine
                y={0}
                stroke="rgba(255,255,255,0.4)"
                strokeDasharray="4 4"
                label={{
                  value: "Same as real driver",
                  position: "insideBottomLeft",
                  fontSize: 8,
                  fill: "rgba(255,255,255,0.6)",
                  fontFamily: "var(--font-jbmono)",
                }}
              />

              {/* Ghost pit-stop laps */}
              {pitLaps.map((lap, i) => (
                <ReferenceLine
                  key={`pit-${lap}`}
                  x={lap}
                  stroke="#4FA8E0"
                  strokeDasharray="2 3"
                  label={{
                    value: `PIT ${pitCompounds[i] ?? ""}`.trim(),
                    position: "insideTopLeft",
                    fontSize: 8,
                    fill: "#4FA8E0",
                    fontFamily: "var(--font-jbmono)",
                  }}
                />
              ))}

              {/* Divergence lap marker */}
              <ReferenceLine
                x={divLap}
                stroke="#e8002d"
                strokeDasharray="3 4"
                label={{
                  value: `Divergence L${divLap}`,
                  position: "insideTopLeft",
                  fontSize: 8,
                  fill: "#e8002d",
                  fontFamily: "var(--font-jbmono)",
                }}
              />

              {/* Resolution lap marker */}
              {outcome && resolutionLap && resolutionLap !== divLap && (
                <ReferenceLine
                  x={resolutionLap}
                  stroke={outcome === "ARIS_CORRECT" ? "#22c55e" : "#ef4444"}
                  strokeDasharray="3 4"
                  label={{
                    value: outcomeLabel ?? "",
                    position: "insideTopRight",
                    fontSize: 8,
                    fill: outcome === "ARIS_CORRECT" ? "#22c55e" : "#ef4444",
                    fontFamily: "var(--font-jbmono)",
                  }}
                />
              )}

              {/* Area fill — red above zero, dark below */}
              <Area
                type="monotone"
                dataKey="delta"
                name="Ghost delta area"
                stroke="none"
                fill="url(#ghostGradient)"
                fillOpacity={1}
                animationDuration={280}
              />

              {/* Delta line */}
              <Line
                type="monotone"
                dataKey="delta"
                name="Ghost delta"
                stroke="#e8002d"
                strokeWidth={1.5}
                dot={false}
                activeDot={{ r: 3 }}
                animationDuration={280}
              />
              <Legend wrapperStyle={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }} />

              <defs>
                <linearGradient id="ghostGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#e8002d" stopOpacity={0.25} />
                  <stop offset="50%" stopColor="#e8002d" stopOpacity={0.05} />
                  <stop offset="100%" stopColor="#333333" stopOpacity={0.15} />
                </linearGradient>
              </defs>
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
