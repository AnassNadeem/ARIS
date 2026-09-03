"use client";

import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
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

export function SpeedTrace() {
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
    const end = lap + 1;
    const slice = samples.filter((s) => s.lap_frac >= start - 0.02 && s.lap_frac < end);
    const lapDur = 90;
    return slice.map((s) => {
      const distPct = ((s.lap_frac - start + 1) % 1) * 100;
      const speed =
        s.speed_kph != null && Number.isFinite(s.speed_kph)
          ? s.speed_kph
          : speedKphFromPath(samples, s.lap_frac, lapDur, field.meta.total_laps);
      return { dist: Number(distPct.toFixed(2)), speed: Number(speed.toFixed(1)) };
    });
  }, [field, driver, lap, ready]);

  if (!ready) {
    return (
      <PanelEmpty
        title="Speed trace"
        detail="Speed versus track distance for a selected lap. Empty until you click Start Race."
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
      </div>
      <div className="relative min-h-0 flex-1">
        {data.length === 0 && loading ? (
          <PanelSkeleton />
        ) : data.length === 0 ? (
          <PanelEmpty
            title="Speed trace"
            detail="No GPS/speed samples for this lap. Pick another lap once the car has completed it."
          />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: 4 }}>
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
                width={44}
                label={yAxisLabel("Speed (km/h)")}
              />
              <Tooltip
                cursor={{ strokeDasharray: "3 3" }}
                contentStyle={{ background: "#1a1a1a", border: "1px solid #2a2a2a", fontFamily: "var(--font-jbmono)", fontSize: 11 }}
                formatter={(v) => [`${Number(v).toFixed(0)} km/h`, "Speed"]}
                labelFormatter={(v) => `${Number(v).toFixed(1)}% lap`}
              />
              <Line type="monotone" dataKey="speed" name="Speed" stroke="#e8002d" dot={false} activeDot={{ r: 3 }} strokeWidth={1.8} animationDuration={280} />
              <Legend wrapperStyle={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
