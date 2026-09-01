"use client";

import { useMemo } from "react";
import {
  Area,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useRaceStore } from "@/store/raceStore";
import type { GhostDeltaPoint } from "@/lib/types";
import { PanelEmpty, PanelSkeleton, usePanelFeedLoading } from "@/components/ui/PanelStates";
import { useAnalyticsReady } from "@/lib/usePanelHistory";
import { AXIS_TICK, xAxisLabel, yAxisLabel } from "@/lib/chartAxis";

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

function ghostEmptyCopy(isARISOn: boolean, reason: string | null): string {
  if (!isARISOn || reason === "aris_disabled") {
    return "ARIS is off. Turn ARIS on and select a driver to compare the recommended strategy as a ghost.";
  }
  if (reason === "no_driver_selected") {
    return "Select a driver to compute the ARIS ghost.";
  }
  if (reason === "session_not_ingested") {
    return "This session isn't in the ARIS database yet, so the ghost can't be computed from lap 1. Ingested race sessions show ARIS's lights-out plan on the map and tower.";
  }
  if (reason === "no_divergence") {
    return "Computing the ARIS ghost from lap 1 — or waiting for the first replay frame. The ghost is ARIS's full-race plan, not only a later divergence.";
  }
  return "No active ghost driver. Turn ARIS on and select a driver; the ghost is ARIS's strategy from lights out.";
}

export function GhostDelta() {
  const ghostData = useRaceStore((s) => s.ghostData);
  const ghostTicks = useRaceStore((s) => s.ghostTicksByLap);
  const currentLap = useRaceStore((s) => s.currentLap);
  const isARISOn = useRaceStore((s) => s.isARISOn);
  const ghostReason = useRaceStore((s) => s.ghostReason);
  const loading = usePanelFeedLoading();
  const ready = useAnalyticsReady();

  const chartData = useMemo(() => {
    if (!ready) return [];
    if (ghostData?.delta_history?.length) {
      return ghostData.delta_history
        .filter((pt: GhostDeltaPoint) => pt.lap <= Math.max(1, currentLap))
        .map((pt: GhostDeltaPoint) => ({
          lap: pt.lap,
          delta: pt.delta,
        }));
    }
    return Object.values(ghostTicks)
      .filter((t) => t.lap <= Math.max(1, currentLap))
      .sort((a, b) => a.lap - b.lap)
      .map((t) => ({ lap: t.lap, delta: t.cumulative_delta_s }));
  }, [ghostData, ghostTicks, currentLap, ready]);

  if (!ready) {
    return (
      <PanelEmpty
        title="Ghost delta"
        detail="Time delta between the real driver and the ARIS ghost. Empty until you click Start Race."
      />
    );
  }

  if (loading && (!isARISOn || !ghostData)) {
    return <PanelSkeleton />;
  }

  if (!isARISOn || !ghostData) {
    return (
      <PanelEmpty
        title="Ghost delta"
        detail={ghostEmptyCopy(isARISOn, ghostReason)}
      />
    );
  }

  const divLap = ghostData.divergence_lap;
  const outcome = ghostData.outcome;
  const pitLaps = ghostData.plan_pit_laps ?? [];
  const pitCompounds = ghostData.plan_pit_compounds ?? [];

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
            Ghost Δ — <span className="font-mono-data">{ghostData.driver_code}</span>
          </span>
          <span className="font-mono-data text-[10px] text-muted">
            Div. L{divLap}: {ghostData.aris_action}{" "}
            <span className="text-amber">vs</span> {ghostData.real_action}
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
              <Tooltip content={<GhostTooltip />} />

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
                stroke="none"
                fill="url(#ghostGradient)"
                fillOpacity={1}
                isAnimationActive={false}
              />

              {/* Delta line */}
              <Line
                type="monotone"
                dataKey="delta"
                stroke="#e8002d"
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />

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
