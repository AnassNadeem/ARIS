"use client";

import { useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  ReferenceArea,
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

type RainBand = { startLap: number; endLap: number };

/** Collapse consecutive wet laps into chart bands. */
function rainBandsFromTrend(trend: { lap: number; rain: number }[]): RainBand[] {
  const bands: RainBand[] = [];
  let start: number | null = null;
  let prev = -1;
  for (const row of trend) {
    if (row.rain) {
      if (start === null) start = row.lap;
      else if (row.lap > prev + 1) {
        bands.push({ startLap: start, endLap: prev });
        start = row.lap;
      }
      prev = row.lap;
    } else if (start !== null) {
      bands.push({ startLap: start, endLap: prev });
      start = null;
    }
  }
  if (start !== null) bands.push({ startLap: start, endLap: prev });
  return bands;
}

function formatRainCaption(bands: RainBand[]): string {
  if (!bands.length) return "No rainfall in session weather";
  const parts = bands.map((b) =>
    b.startLap === b.endLap ? `L${b.startLap}` : `L${b.startLap}-${b.endLap}`,
  );
  if (parts.length === 1) return `Rainfall on ${parts[0]}`;
  if (parts.length <= 3) return `Rainfall on ${parts.join(", ")}`;
  return `Rainfall on ${parts.slice(0, 2).join(", ")} +${parts.length - 2} more`;
}

export function WeatherForecast() {
  const totalLaps = useRaceStore((s) => s.totalLaps);
  const currentLap = useRaceStore((s) => s.currentLap);
  const field = useRaceStore((s) => s.r2RaceField);
  const liveWeather = useRaceStore((s) => s.liveWeather);
  const rainfall = useRaceStore((s) => s.rainfall);
  const loading = usePanelFeedLoading();
  const ready = useAnalyticsReady();

  const trend = useMemo(() => {
    const rows = field?.weather?.length ? field.weather : liveWeather;
    const cap = Math.max(1, currentLap);
    return rows
      .filter((w) => w.lap <= cap)
      .map((w) => ({
        lap: w.lap,
        trackTempC: w.track_temp_c,
        airTempC: w.air_temp_c,
        rain: w.rainfall ? 1 : 0,
      }));
  }, [field, liveWeather, currentLap]);

  const rainBands = useMemo(() => rainBandsFromTrend(trend), [trend]);

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
      <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono-data text-[10px] text-muted">
        <span>
          {formatRainCaption(rainBands)}
          {rainfall ? " · currently wet" : ""}
        </span>
        {rainBands.length > 0 && (
          <span className="inline-flex items-center gap-1.5 text-muted">
            <span className="inline-block h-2 w-3 rounded-sm bg-[#1E90FF]/20" aria-hidden />
            Rain periods
          </span>
        )}
      </div>
      <div className="min-h-0 flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={trend} margin={{ top: 8, right: 8, bottom: 4, left: 4 }}>
            <CartesianGrid stroke="#2a2a2a" strokeDasharray="2 4" />
            <XAxis dataKey="lap" stroke="#888888" tick={AXIS_TICK} label={xAxisLabel("Lap")} />
            <YAxis stroke="#888888" tick={AXIS_TICK} width={40} label={yAxisLabel("Temperature (°C)")} />
            {rainBands.map((band) => (
              <ReferenceArea
                key={`rain-${band.startLap}-${band.endLap}`}
                x1={band.startLap}
                x2={band.endLap}
                fill="#1E90FF"
                fillOpacity={0.22}
                ifOverflow="extendDomain"
              />
            ))}
            <Tooltip
              cursor={{ strokeDasharray: "3 3" }}
              contentStyle={{ background: "#1a1a1a", border: "1px solid #2a2a2a", fontFamily: "var(--font-jbmono)", fontSize: 11 }}
              formatter={(value, name) => {
                if (name === "Rain") return [Number(value) ? "Yes" : "No", "Rain"];
                return [value, name];
              }}
              labelFormatter={(lap) => `Lap ${lap}`}
            />
            <Area
              type="monotone"
              dataKey="trackTempC"
              name="Track °C"
              stroke="#E8002D"
              fill="#E8002D"
              fillOpacity={0.12}
              animationDuration={280}
            />
            <Line
              type="monotone"
              dataKey="airTempC"
              name="Air °C"
              stroke="#39FF14"
              dot={false}
              activeDot={{ r: 3 }}
              strokeWidth={1.5}
              animationDuration={280}
            />
            {/* Invisible series so tooltip can report rain on hover */}
            <Line type="stepAfter" dataKey="rain" name="Rain" stroke="transparent" dot={false} legendType="none" />
            <ReferenceLine x={currentLap} stroke="#888888" strokeDasharray="3 3" />
            <Legend wrapperStyle={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
