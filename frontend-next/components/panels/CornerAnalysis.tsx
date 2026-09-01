"use client";

import { useMemo, useState } from "react";
import { useRaceStore } from "@/store/raceStore";
import { useFocusDriver } from "@/lib/useFocusDriver";
import { posSamplesFor, speedKphFromPath } from "@/lib/r2Replay";
import { PanelEmpty, PanelSkeleton, usePanelFeedLoading } from "@/components/ui/PanelStates";
import { useAnalyticsReady, useFollowRaceLap } from "@/lib/usePanelHistory";

interface CornerRow {
  corner: number;
  distPct: number;
  minSpeed: number;
}

function cornersFromSpeeds(dist: number[], speed: number[]): CornerRow[] {
  if (speed.length < 8) return [];
  const max = Math.max(...speed);
  const floor = max * 0.72;
  const out: CornerRow[] = [];
  for (let i = 2; i < speed.length - 2; i++) {
    const v = speed[i];
    if (v >= floor) continue;
    if (v <= speed[i - 1] && v <= speed[i + 1] && v <= speed[i - 2] && v <= speed[i + 2]) {
      const last = out[out.length - 1];
      if (last && Math.abs(dist[i] - last.distPct) < 4) {
        if (v < last.minSpeed) {
          last.distPct = dist[i];
          last.minSpeed = v;
        }
        continue;
      }
      out.push({ corner: out.length + 1, distPct: dist[i], minSpeed: v });
    }
  }
  return out;
}

export function CornerAnalysis() {
  const focused = useFocusDriver();
  const [driver, setDriver] = useState(focused);
  const field = useRaceStore((s) => s.r2RaceField);
  const ready = useAnalyticsReady();
  const loading = usePanelFeedLoading();
  const drivers = useRaceStore((s) => s.gridDrivers);
  const { lap, setLap, pinned, follow, currentLap } = useFollowRaceLap();

  const rows = useMemo(() => {
    if (!field || !ready) return [];
    const samples = posSamplesFor(field, driver);
    const start = lap;
    const slice = samples.filter((s) => s.lap_frac >= start - 0.02 && s.lap_frac < start + 1);
    const dist = slice.map((s) => ((s.lap_frac - start + 1) % 1) * 100);
    const speed = slice.map((s) =>
      s.speed_kph != null && Number.isFinite(s.speed_kph)
        ? s.speed_kph
        : speedKphFromPath(samples, s.lap_frac, 90, field.meta.total_laps),
    );
    return cornersFromSpeeds(dist, speed);
  }, [field, driver, lap, ready]);

  if (!ready) {
    return (
      <PanelEmpty
        title="Corner analysis"
        detail="Minimum speed at each detected corner for the selected lap. Empty until you click Start Race."
      />
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-carbon p-2 font-mono-data text-xs">
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
      <div className="min-h-0 flex-1 overflow-y-auto">
        {rows.length === 0 && loading ? (
          <PanelSkeleton rows={8} />
        ) : rows.length === 0 ? (
          <PanelEmpty title="Corner analysis" detail="Not enough speed samples to detect corners on this lap." />
        ) : (
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-border font-sans text-[10px] uppercase text-muted">
                <th className="py-1.5">Corner</th>
                <th>Track pos</th>
                <th className="text-right">Min speed</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.corner} className="border-b border-border/60">
                  <td className="py-1.5 text-white">T{r.corner}</td>
                  <td className="text-muted">{r.distPct.toFixed(1)}% of lap</td>
                  <td className="text-right text-white">{r.minSpeed.toFixed(0)} km/h</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
