"use client";

import { useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useRaceStore } from "@/store/raceStore";
import { AXIS_TICK, xAxisLabel, yAxisLabel } from "@/lib/chartAxis";
import { PanelEmpty, PanelSkeleton, usePanelFeedLoading } from "@/components/ui/PanelStates";
import { useAnalyticsReady } from "@/lib/usePanelHistory";

export function WeatherForecast() {
  const totalLaps = useRaceStore((s) => s.totalLaps);
  const currentLap = useRaceStore((s) => s.currentLap);
  const field = useRaceStore((s) => s.r2RaceField);
  const rainfall = useRaceStore((s) => s.rainfall);
  const loading = usePanelFeedLoading();
  const ready = useAnalyticsReady();

  const trend = useMemo(() => {
    const rows = field?.weather ?? [];
    const cap = Math.max(1, currentLap);
    return rows
      .filter((w) => w.lap <= cap)
      .map((w) => ({
        lap: w.lap,
        trackTempC: w.track_temp_c,
        airTempC: w.air_temp_c,
        rain: w.rainfall ? 1 : 0,
      }));
  }, [field, currentLap]);

  const wetLaps = trend.filter((t) => t.rain).map((t) => t.lap);

  if (!ready) {
    return (
      <PanelEmpty
        title="Weather"
        detail="Track/air temperature and rainfall over race distance. Empty until you click Start Race."
      />
    );
  }

  if (loading && trend.length === 0 && totalLaps <= 0) {
    return <PanelSkeleton />;
  }

  if (trend.length === 0) {
    return (
      <PanelEmpty
        title="Weather"
        detail={
          rainfall
            ? "Rain is flagged on the live feed, but per-lap weather samples are not in this pack."
            : "No per-lap weather samples in this session pack."
        }
      />
    );
  }

  return (
    <div className="flex h-full flex-col bg-carbon p-2">
      <div className="mb-2 font-mono-data text-[10px] text-muted">
        {wetLaps.length
          ? `Rainfall on laps ${wetLaps[0]}–${wetLaps[wetLaps.length - 1]}`
          : "No rainfall in session weather"}
        {rainfall ? " · currently wet" : ""}
      </div>
      <div className="min-h-0 flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={trend} margin={{ top: 8, right: 8, bottom: 4, left: 4 }}>
            <CartesianGrid stroke="#2a2a2a" strokeDasharray="2 4" />
            <XAxis dataKey="lap" stroke="#888888" tick={AXIS_TICK} label={xAxisLabel("Lap")} />
            <YAxis stroke="#888888" tick={AXIS_TICK} width={40} label={yAxisLabel("Temperature (°C)")} />
            <Tooltip
              contentStyle={{ background: "#1a1a1a", border: "1px solid #2a2a2a", fontFamily: "var(--font-jbmono)", fontSize: 11 }}
            />
            <Area
              type="monotone"
              dataKey="trackTempC"
              name="Track °C"
              stroke="#E8002D"
              fill="#E8002D"
              fillOpacity={0.12}
              isAnimationActive={false}
            />
            <Line type="monotone" dataKey="airTempC" name="Air °C" stroke="#39FF14" dot={false} strokeWidth={1.5} isAnimationActive={false} />
            <ReferenceLine x={currentLap} stroke="#888888" strokeDasharray="3 3" />
            <Legend wrapperStyle={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
