"use client";

import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useRaceStore } from "@/store/raceStore";
import { useFocusDriver } from "@/lib/useFocusDriver";
import { posSamplesFor, speedKphFromPath } from "@/lib/r2Replay";
import { AXIS_TICK, xAxisLabel, yAxisLabel } from "@/lib/chartAxis";
import { PanelEmpty, PanelSkeleton, usePanelFeedLoading } from "@/components/ui/PanelStates";
import { useAnalyticsReady, useFollowRaceLap } from "@/lib/usePanelHistory";

export function ThrottleBrake() {
  const focused = useFocusDriver();
  const [driver, setDriver] = useState(focused);
  const field = useRaceStore((s) => s.r2RaceField);
  const ready = useAnalyticsReady();
  const loading = usePanelFeedLoading();
  const drivers = useRaceStore((s) => s.gridDrivers);
  const { lap, setLap, pinned, follow, currentLap } = useFollowRaceLap();

  const data = useMemo(() => {
    if (!field || !ready) return [];
    const samples = posSamplesFor(field, driver);
    const start = lap;
    const slice = samples.filter((s) => s.lap_frac >= start - 0.02 && s.lap_frac < start + 1);
    const speeds = slice.map((s) =>
      s.speed_kph != null && Number.isFinite(s.speed_kph)
        ? s.speed_kph
        : speedKphFromPath(samples, s.lap_frac, 90, field.meta.total_laps),
    );
    return slice.map((s, i) => {
      const prev = speeds[i - 1] ?? speeds[i];
      const dv = speeds[i] - prev;
      const throttle = Math.max(0, Math.min(100, dv > 0 ? Math.min(100, dv * 8) : 40));
      const brake = Math.max(0, Math.min(100, dv < 0 ? Math.min(100, -dv * 10) : 0));
      return {
        dist: Number((((s.lap_frac - start + 1) % 1) * 100).toFixed(2)),
        throttle: Number(throttle.toFixed(0)),
        brake: Number(brake.toFixed(0)),
      };
    });
  }, [field, driver, lap, ready]);

  if (!ready) {
    return (
      <PanelEmpty
        title="Throttle / brake"
        detail="Throttle and brake versus track distance, derived from speed samples. Empty until you click Start Race."
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
        <span className="text-muted">Lap</span>
        <input
          type="number"
          min={1}
          max={field?.meta.total_laps ?? currentLap}
          value={lap}
          onChange={(e) => setLap(Math.max(1, Number(e.target.value) || 1))}
          className="w-16 rounded border border-border bg-surface px-2 py-0.5 font-mono-data text-xs text-white"
        />
        {pinned && (
          <button
            type="button"
            onClick={follow}
            className="rounded border border-border px-2 py-0.5 font-mono-data text-[10px] uppercase text-muted hover:text-white"
          >
            Follow
          </button>
        )}
        <span className="font-mono-data text-[10px] text-muted-2">Derived from speed (no pedal telemetry in the pack)</span>
      </div>
      <div className="relative min-h-0 flex-1">
        {data.length === 0 && loading ? (
          <PanelSkeleton />
        ) : data.length === 0 ? (
          <PanelEmpty title="Throttle / brake" detail="No speed samples for this lap yet." />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: 4 }}>
              <CartesianGrid stroke="#2a2a2a" strokeDasharray="2 4" />
              <XAxis
                dataKey="dist"
                stroke="#888888"
                tick={AXIS_TICK}
                tickFormatter={(v) => `${Math.round(Number(v))}%`}
                label={xAxisLabel("Track distance (% of lap)")}
              />
              <YAxis
                stroke="#888888"
                tick={AXIS_TICK}
                domain={[0, 100]}
                width={40}
                label={yAxisLabel("Pedal (%)")}
              />
              <Tooltip
                contentStyle={{ background: "#1a1a1a", border: "1px solid #2a2a2a", fontFamily: "var(--font-jbmono)", fontSize: 11 }}
              />
              <Area type="monotone" dataKey="throttle" name="Throttle" stroke="#39ff14" fill="#39ff14" fillOpacity={0.25} isAnimationActive={false} />
              <Area type="monotone" dataKey="brake" name="Brake" stroke="#e8002d" fill="#e8002d" fillOpacity={0.3} isAnimationActive={false} />
              <Legend wrapperStyle={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
